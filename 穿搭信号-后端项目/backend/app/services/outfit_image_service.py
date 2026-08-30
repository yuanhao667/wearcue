import base64
import ipaddress
import json
import os
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from .outfit_ai_service import scene_context_for


class OutfitImageServiceError(RuntimeError):
    pass


MAX_GENERATED_IMAGE_BYTES = 20 * 1024 * 1024


def safe_image_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    try:
        return ipaddress.ip_address(parsed.hostname).is_global
    except ValueError:
        return parsed.hostname.lower() != "localhost"


class OutfitImageService:
    def __init__(self) -> None:
        self.url = (os.getenv("AI_IMAGE_API_URL") or os.getenv("AI_API_URL") or "").rstrip("/")
        self.key = os.getenv("AI_API_KEY") or os.getenv("VISION_API_KEY") or ""
        self.model = os.getenv("AI_IMAGE_MODEL", "wan2.7-image")
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "outfit_image.txt"
        self.prompt = prompt_path.read_text(encoding="utf-8")

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key and self.model)

    async def generate(
        self,
        label: str,
        audience: str,
        scene: str,
        items: List[Dict[str, Any]],
        constraints: Dict[str, Any],
        person_profile: Dict[str, Any],
    ) -> bytes:
        if not self.configured:
            raise OutfitImageServiceError("AI 生图模型尚未配置")
        scene_context = scene_context_for(scene, audience)
        scene_requirements = scene_context["scene_requirements"]
        context = {
            "穿搭名称": label,
            "人物": "成年男性" if audience == "mens" else "成年女性",
            "场景": {
                "代码": scene,
                "名称": scene_context["scene_name"],
                "风格侧重点": scene_requirements,
            },
            "衣物": [
                {
                    "品类": item.get("variant_type"),
                    "配色": item.get("color_name"),
                    "厚度": {"thin": "薄款", "regular": "常规", "thick": "厚款"}.get(
                        str(item.get("thickness")), item.get("thickness")
                    ),
                    "位置": item.get("slot"),
                }
                for item in items
            ],
            "天气约束": constraints,
            "人物信息": {
                "身高段": person_profile["height_group"],
                "体重段": person_profile["weight_group"],
            },
        }
        thickness_names = {"thin": "薄款", "regular": "常规", "thick": "厚款"}
        garment_list = "\n".join(
            f"{index}. {item.get('slot')}：{item.get('color_name')}、"
            f"{thickness_names.get(str(item.get('thickness')), item.get('thickness'))}、"
            f"{item.get('variant_type')}"
            for index, item in enumerate(items, 1)
        )
        slots = {str(item.get("slot")) for item in items}
        forbidden = []
        if "outerwear" not in slots:
            forbidden.append("输入没有 outerwear：禁止开衫、夹克、大衣及任何外套")
        if "equipment" not in slots:
            forbidden.append("输入没有 equipment：禁止帽子、包、手套、雨伞及其他配饰，双手空置")
        payload = {
            "model": self.model,
            "prompt": (
                self.prompt
                + f"\n\n最高优先级服装清单：本次只能出现以下 {len(items)} 件衣物，"
                + f"最终画面也必须恰好是 {len(items)} 件，不多不少。\n{garment_list}"
                + ("\n明确禁止：\n" + "\n".join(forbidden) if forbidden else "")
                + "\n人物信息：青年中国人，"
                + f"{person_profile['height_group']}身高，体重{person_profile['weight_group']}。"
                + "自然呈现相应年龄感和体态比例，禁止夸张或评价身材。"
                + f"\n场景风格要求：{scene_requirements}"
                + "场景要求只控制整体气质、姿态、背景及既有衣物的穿法，"
                + "不得为此新增、删除或替换衣物。"
                + "\n\n完整结构化输入：\n"
                + json.dumps(context, ensure_ascii=False)
            ),
            "n": 1,
            "size": "1024x1536",
            "thinking_mode": True,
            "watermark": False,
        }
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            try:
                response = await client.post(
                    self.url + "/images/generations",
                    headers={"Authorization": "Bearer " + self.key},
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
                outputs = body.get("data") or body.get("output") or []
                output = outputs[0]
                if output.get("b64_json"):
                    image = base64.b64decode(output["b64_json"], validate=True)
                else:
                    image_url = output.get("url") or output.get("content_url")
                    if not image_url or not safe_image_url(image_url):
                        raise OutfitImageServiceError("AI 生图未返回图片")
                    api_host = urlparse(self.url).hostname

                    async def download_image(headers: dict[str, str] | None = None) -> bytes | None:
                        async with client.stream("GET", image_url, headers=headers) as download:
                            if download.status_code == 401:
                                return None
                            download.raise_for_status()
                            declared = int(download.headers.get("content-length", "0") or "0")
                            if declared > MAX_GENERATED_IMAGE_BYTES:
                                raise OutfitImageServiceError("AI 生图结果无效")
                            content = bytearray()
                            async for chunk in download.aiter_bytes():
                                content.extend(chunk)
                                if len(content) > MAX_GENERATED_IMAGE_BYTES:
                                    raise OutfitImageServiceError("AI 生图结果无效")
                            return bytes(content)

                    image = await download_image()
                    if image is None and urlparse(image_url).hostname == api_host:
                        image = await download_image({"Authorization": "Bearer " + self.key})
                    if image is None:
                        raise OutfitImageServiceError("AI 生图下载未授权")
                if not image or len(image) > MAX_GENERATED_IMAGE_BYTES:
                    raise OutfitImageServiceError("AI 生图结果无效")
                return image
            except OutfitImageServiceError:
                raise
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
                raise OutfitImageServiceError("AI 穿搭参考图生成失败") from error
