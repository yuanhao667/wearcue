import asyncio
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
from .style_guidance import style_guidance

logger = logging.getLogger(__name__)
DETAIL_IMAGE_PROMPT_VERSION = "wearcue-detail-image-v3.4"


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


def first_image_output(body: Dict[str, Any], style: str) -> Dict[str, Any]:
    """按供应商的返回结构取出第一张图（DashScope 原生 / OpenAI images 兼容）。"""
    if style == "dashscope":
        choices = (body.get("output") or {}).get("choices") or []
        for choice in choices:
            content = (choice.get("message") or {}).get("content") or []
            for part in content:
                if isinstance(part, dict) and part.get("image"):
                    return {"url": part["image"], "b64_json": part.get("b64_json")}
        raise OutfitImageServiceError("AI 生图未返回图片")
    outputs = body.get("data") or body.get("output") or []
    return outputs[0]


class OutfitImageService:
    def __init__(self) -> None:
        self.url = (os.getenv("AI_IMAGE_API_URL") or os.getenv("AI_API_URL") or "").rstrip("/")
        self.key = (
            os.getenv("AI_IMAGE_API_KEY")
            or os.getenv("AI_API_KEY")
            or os.getenv("VISION_API_KEY")
            or ""
        )
        self.model = os.getenv("AI_IMAGE_MODEL", "wan2.7-image")
        self.fallback_model = os.getenv("AI_IMAGE_FALLBACK_MODEL", "")
        # "openai"：POST /images/generations；"dashscope"：千问平台原生生图接口。
        self.style = (os.getenv("AI_IMAGE_API_STYLE") or "openai").strip().lower()
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
                item.get("pattern_description"),
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
        guidance = style_guidance(audience, style_tags or [])
        height_description = {
            "偏矮": "身材相对矮小，保持自然的头身和四肢比例，不拉成长腿高个模特",
            "中等": "身高中等，头身与四肢比例自然",
            "偏高": "身材相对高挑，躯干与四肢自然修长，不靠低机位或拉伸制造高个",
        }[person_profile["height_group"]]
        build_description = {
            "偏轻": "体型偏瘦，躯干与四肢围度较纤细",
            "偏瘦": "体型偏瘦，躯干与四肢围度较纤细",
            "稍瘦": "体型略瘦，比中等体型稍纤细，不画成极瘦",
            "中等": "体型中等，躯干与四肢围度适中",
            "稍重": "体型略丰润，腰腹与四肢围度比中等稍大，不通过宽松衣服代替真实体型",
            "偏重": "体型较丰润，保留腰腹、上臂和腿部的真实体积，不自动瘦身",
        }[person_profile["weight_group"]]
        prompt = (
            f"用户已保存的体型设定：{person_profile['height_group']}身高、{person_profile['weight_group']}体型。{height_description}；{build_description}。\n\n"
            + self.prompt
            + f"\n\n本次主题：{label}。人物："
            + ("青年感中国男性" if audience == "mens" else "青年感中国女性")
            + f"，{person_profile['height_group']}身高、{person_profile['weight_group']}体型。保持该体型的真实轮廓，不夸张拉伸高矮或改变体型。"
            + f"\n场景：{scene_context['scene_name']}。主风格：{style_names}。"
            + f"\n场景约束：{scene_requirements}"
            + ("\n\n本套穿搭的风格执行指引（按标签顺序，以第一种为主）：\n" + guidance if guidance else "")
            + "\n风格定义仅指导清单内衣物的视觉表达；已确认的单品、颜色、版型、厚度与锁定特征优先。不得照搬展示图换装或增添鞋包配饰，也不得为了风格牺牲已确定的适温层次。"
            + f"\n\n唯一允许出现的 {len(items)} 件服装与配饰：\n{garment_list}"
            + (f"\n\n廓形与造型DNA：{dna_lines}" if dna_lines else "")
            + (f"\n必须清楚呈现：{must_show}" if must_show else "")
            + (f"\n拍摄执行：{direction_lines}" if direction_lines else "")
            + ("\n明确禁止：" + "；".join(forbidden) if forbidden else "")
            + "\n场景仅控制背景、姿态与活动感，不能改动上述服装。"
        )
        models = list(dict.fromkeys(filter(None, [self.model, self.fallback_model])))
        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            for index, model in enumerate(models):
                started_at = time.perf_counter()
                try:
                    image = await asyncio.wait_for(
                        self._generate_image(client, prompt, model), timeout=90
                    )
                    logger.info(
                        "AI outfit image model=%s completed in %dms",
                        model, round((time.perf_counter() - started_at) * 1000),
                    )
                    return image
                except httpx.HTTPStatusError as error:
                    status = error.response.status_code
                    retryable = status == 429 or status >= 500
                    failure = error
                except (TimeoutError, httpx.RequestError, OutfitImageServiceError,
                        KeyError, IndexError, TypeError, ValueError) as error:
                    retryable = True
                    failure = error
                logger.warning(
                    "AI outfit image model=%s failed type=%s status=%s fallback=%s",
                    model, type(failure).__name__,
                    failure.response.status_code if isinstance(failure, httpx.HTTPStatusError) else None,
                    retryable and index < len(models) - 1,
                )
                if not retryable or index == len(models) - 1:
                    raise OutfitImageServiceError("AI 穿搭参考图生成失败，请稍后重试") from failure
        raise OutfitImageServiceError("AI 生图模型尚未配置")

    async def _generate_image(self, client: httpx.AsyncClient, prompt: str, model: str) -> bytes:
        if self.style == "dashscope":
            request_url = self.url + "/services/aigc/multimodal-generation/generation"
            payload = {
                "model": model,
                "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
                "parameters": {"size": "1024*1536", "n": 1, "watermark": False},
            }
        else:
            request_url = self.url + "/images/generations"
            payload = {
                "model": model,
                "prompt": prompt,
                "n": 1,
                "size": "1024x1536",
                "thinking_mode": True,
                "watermark": False,
            }
        response = await client.post(
            request_url,
            headers={"Authorization": "Bearer " + self.key},
            json=payload,
        )
        response.raise_for_status()
        body = response.json()
        output = first_image_output(body, self.style)
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
