import base64
import ipaddress
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from .outfit_ai_service import scene_context_for

logger = logging.getLogger(__name__)
DETAIL_IMAGE_PROMPT_VERSION = "wearcue-detail-image-v3.2"


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
        outfit_dna: Dict[str, Any] | None = None,
        locked_features: List[str] | None = None,
        image_direction: Dict[str, Any] | None = None,
        style_tags: List[str] | None = None,
    ) -> bytes:
        if not self.configured:
            raise OutfitImageServiceError("AI 生图模型尚未配置")
        items = [
            item for item in items
            if item.get("functional_icon_key") not in {
                "acc_umbrella", "umbrella", "acc_sunscreen", "sunscreen", "sun_protection"
            }
            and item.get("asset_key") not in {"acc_umbrella", "acc_sunscreen"}
        ]
        if not items:
            raise OutfitImageServiceError("没有可用于人物生图的穿搭单品")
        scene_context = scene_context_for(scene, audience)
        scene_requirements = scene_context["scene_requirements"]
        thickness_names = {"thin": "薄款", "regular": "常规", "thick": "厚款"}
        garment_lines = []
        for index, item in enumerate(items, 1):
            details = [
                item.get("color_name"),
                thickness_names.get(str(item.get("thickness")), item.get("thickness")),
                item.get("variant_type"),
                item.get("fit"),
                item.get("shoulder"),
                item.get("length"),
                item.get("waistline"),
                item.get("bottom_shape"),
                item.get("material"),
                item.get("wearing_method"),
                "、".join(str(value) for value in item.get("structure_details") or []),
            ]
            garment_lines.append(
                f"{index}. {item.get('slot')}："
                + "；".join(str(value) for value in details if value and value != "不适用")
            )
        garment_list = "\n".join(garment_lines)
        slots = {str(item.get("slot")) for item in items}
        forbidden = []
        if "outerwear" not in slots:
            forbidden.append("输入没有 outerwear：禁止开衫、夹克、大衣及任何外套")
        if "equipment" not in slots:
            forbidden.append("输入没有 equipment：禁止帽子、包、手套、雨伞及其他配饰，双手空置")
        dna_lines = "；".join(
            f"{key}={value}" for key, value in (outfit_dna or {}).items() if value
        )
        direction = image_direction or {}
        direction_lines = "；".join(
            f"{key}={value}"
            for key, value in direction.items()
            if key not in {"must_show", "must_avoid"} and value
        )
        must_show = "；".join(str(value) for value in (locked_features or []))
        style_names = "、".join(style_tags or []) or "由服装廓形自然决定"
        prompt = (
            self.prompt
            + f"\n\n本次主题：{label}。人物："
            + ("青年感中国男性" if audience == "mens" else "青年感中国女性")
            + f"，{person_profile['height_group']}身高、{person_profile['weight_group']}体重段。"
            + f"\n场景：{scene_context['scene_name']}。主风格：{style_names}。"
            + f"\n场景约束：{scene_requirements}"
            + f"\n\n唯一允许出现的 {len(items)} 件服装与配饰：\n{garment_list}"
            + (f"\n\n廓形与造型DNA：{dna_lines}" if dna_lines else "")
            + (f"\n必须清楚呈现：{must_show}" if must_show else "")
            + (f"\n拍摄执行：{direction_lines}" if direction_lines else "")
            + ("\n明确禁止：" + "；".join(forbidden) if forbidden else "")
            + "\n场景仅控制背景、姿态与活动感，不能改动上述服装。"
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": 1,
            "size": "1024x1536",
            "thinking_mode": True,
            "watermark": False,
        }
        started_at = time.perf_counter()
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
                logger.info(
                    "AI outfit image %s completed in %dms",
                    DETAIL_IMAGE_PROMPT_VERSION,
                    round((time.perf_counter() - started_at) * 1000),
                )
                return image
            except OutfitImageServiceError:
                raise
            except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
                raise OutfitImageServiceError("AI 穿搭参考图生成失败") from error
