"""Build the fixed 30-case Prompt V3 regression matrix for human image review."""

from __future__ import annotations

import json
from pathlib import Path


SCENES = ("commute", "date", "travel")
SEASONS = ("spring-autumn", "summer", "winter")
STYLES = (("minimal",), ("sport",), ("outdoor",), ("minimal", "sport"))
WEATHER = (
    {"current_apparent_temperature": 22, "weather": "clear"},
    {"current_apparent_temperature": 31, "weather": "high_uv"},
    {"current_apparent_temperature": 12, "weather": "light_rain"},
    {"current_apparent_temperature": 3, "weather": "windy"},
    {"current_apparent_temperature": -4, "weather": "snow"},
)


def main() -> None:
    cases = []
    for index in range(30):
        mode = "reference_recreation" if index % 5 == 0 else "original_generation"
        cases.append({
            "id": f"v3-{index + 1:02d}",
            "mode": mode,
            "audience": "womens" if index % 2 else "mens",
            "season": SEASONS[index % len(SEASONS)],
            "scene": SCENES[(index // 2) % len(SCENES)],
            "style_tags": list(STYLES[index % len(STYLES)]),
            "weather": WEATHER[index % len(WEATHER)],
            "reference_required": mode == "reference_recreation",
            "review": {
                "status": "pending_human_image_review",
                "pass": None,
                "severe_issue": None,
                "checks": [
                    "outfit_dna_consistent",
                    "locked_features_preserved",
                    "text_image_consistent",
                    "no_extra_visible_accessory",
                    "blogger_70_editorial_30",
                ],
            },
        })
    target = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "prompt_v3_samples.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
