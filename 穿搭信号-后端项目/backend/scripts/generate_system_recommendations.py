import asyncio
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR / "backend"))

from dotenv import load_dotenv

load_dotenv(PROJECT_DIR / ".env")

from app.services.outfit_ai_service import OutfitAIService  # noqa: E402

BANDS = [
    ("hot", 30, 34),
    ("warm", 26, 30),
    ("mild", 22, 26),
    ("cool", 17, 21),
    ("cold", 12, 16),
    ("freezing", 6, 10),
    ("severe", -2, 3),
]
AUDIENCES = ["mens", "womens"]
OUT_PATH = PROJECT_DIR / "backend" / "app" / "defaults" / "system_ai_outfits.json"


def load_existing():
    if OUT_PATH.is_file():
        try:
            return json.loads(OUT_PATH.read_text(encoding="utf-8")).get("outfits", [])
        except Exception:
            return []
    return []


def save(outfits):
    OUT_PATH.write_text(
        json.dumps({"version": 1, "outfits": outfits}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def main() -> None:
    service = OutfitAIService()
    if not service.configured:
        print("AI 未配置，无法生成系统推荐")
        return

    outfits = load_existing()
    done = {outfit["id"] for outfit in outfits}

    for band, low, high in BANDS:
        for audience in AUDIENCES:
            outfit_id = f"system-ai-{band}-{audience}-01"
            if outfit_id in done:
                continue
            context = {
                "scene": "commute",
                "audience": audience,
                "city_id": "unknown",
                "local_date": "today",
                "thermal_band": band,
                "calibrated_apparent_min": low,
                "apparent_max": high,
                "apparent_delta": round(high - low, 1),
                "needs_waterproof": False,
                "needs_heavy_rain_protection": False,
                "needs_snow_protection": False,
                "needs_windproof": False,
                "needs_sun_protection": False,
                "needs_strong_sun_protection": False,
                "avoid_umbrella": False,
                "equipment": [],
                "warnings": [],
            }
            result = None
            for attempt in range(2):
                try:
                    result = await service.generate(context)
                    break
                except Exception as exc:  # noqa: BLE001
                    print(f"retry {attempt + 1} {band} {audience}: {exc}")
                    await asyncio.sleep(3)
            if result is None:
                print(f"FAIL {band} {audience}")
                continue
            outfits.append(
                {
                    "id": outfit_id,
                    "thermal_band": band,
                    "audience": audience,
                    "label": result["label"],
                    "items": result["items"],
                    "replication_guide": result["replication_guide"],
                    "outfit_analysis": result["outfit_analysis"],
                }
            )
            save(outfits)
            print(f"OK {band} {audience}: {result['label']}")
            await asyncio.sleep(2)

    print(f"done, total {len(outfits)} outfits -> {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
