"""方案与生图共用风格特征，不把展示照片当作生成模板。"""

import json
from pathlib import Path

STYLE_GUIDES = json.loads(
    (Path(__file__).resolve().parents[1] / "prompts" / "style_guides.json").read_text(
        encoding="utf-8"
    )
)


def style_guidance(audience: str, style_tags: list[str] | None = None) -> str:
    tags = STYLE_GUIDES if style_tags is None else dict.fromkeys(style_tags)
    sections = []
    for tag in tags:
        guide = STYLE_GUIDES.get(tag)
        if guide is None:
            continue
        sections.append(f"【{guide['name']}（{tag}）】\n" + "\n".join(
            guide[key] for key in ("focus", "garments", audience, "season", "boundary")
            if key in guide
        ))
    if not sections:
        return ""
    return (
        "风格匹配以服装的视觉特征和组合关系为准，与风格选择页的展示照片无关。"
        "展示照片只用于帮助用户理解风格，不是生成参考图或固定穿搭模板；"
        "不得照搬其单品组合、图案、配色、人物、背景或姿态。"
        "同一风格允许不同款式与表达路径，不能把其中一套搭配当作唯一标准。\n\n"
        + "\n\n".join(sections)
    )


PLANNING_STYLE_RULES = (
    "以下是风格定义与可选表达方向，不是固定套装。天气、温度、性别和场景的实际功能要求是硬约束；"
    "在此范围内，当次明确要求优先于preferred_style_tags长期偏好。偏好非空时优先选其中一种作为主风格，"
    "多选不代表把所有风格混穿；为空时不限风格。style_tags第一个必须是衣物实际体现的主风格，"
    "第二个仅在存在清楚衣物证据时添加。场景描述中的审美举例不能覆盖风格选择，"
    "例如出行可生成适合步行的简约穿搭，不必一律户外。单品必须来自available_assets（如有），"
    "不能为符合风格添加没有图标的单品。原创生成先根据当次条件选择表达方向，再确定单品，"
    "不能默认复用展示搭配。用户明确要求还原自己提供的穿搭时，保留该穿搭的单品与锁定特征。\n\n"
)
