"""Package the reviewed discovery images without mutating the source folders."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from PIL import Image, ImageOps


AUDIENCE = {"男": "mens", "女": "womens"}


def save_jpeg(image: Image.Image, path: Path, max_size: tuple[int, int], quality: int) -> None:
    resized = image.copy()
    resized.thumbnail(max_size, Image.Resampling.LANCZOS)
    resized.save(path, "JPEG", quality=quality, optimize=True, progressive=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    source = args.source.resolve()
    metadata = json.loads((source / "系统素材标签.json").read_text(encoding="utf-8"))
    output = args.output.resolve()
    image_dir = output / "system_assets"
    image_dir.mkdir(parents=True, exist_ok=True)
    counters: Counter[tuple[str, str, str]] = Counter()
    assets = []

    for entry in metadata["assets"]:
        source_path = source / entry["relative_path"]
        counters[(entry["season"], entry["style_tags"][0], entry["scene"])] += 1
        sequence = counters[(entry["season"], entry["style_tags"][0], entry["scene"])]
        label = f"{entry['season']}{entry['style_tags'][0]}{entry['scene']} {sequence:02d}"
        base_name = entry["asset_id"]
        with Image.open(source_path) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            save_jpeg(image, image_dir / f"{base_name}.jpg", (1024, 1536), 86)
            save_jpeg(image, image_dir / f"{base_name}_medium.jpg", (800, 800), 76)
            save_jpeg(image, image_dir / f"{base_name}_thumb.jpg", (400, 400), 82)
        assets.append({
            "asset_id": entry["asset_id"],
            "label": label,
            "image": f"system_assets/{base_name}.jpg",
            "sha256": entry["sha256"],
            "audience": AUDIENCE[entry["gender"]],
            "season": entry["season_key"],
            "scene": entry["scene_key"],
            "style_tags": entry["style_keys"][:2],
            "suitable_min": entry["temperature_min_c"],
            "suitable_max": entry["temperature_max_c"],
            "components": [],
            "content_ready": False,
            "manual_reviewed": bool(entry.get("manual_reviewed")),
            "source_relative_path": entry["relative_path"],
        })

    manifest = {
        "schema_version": "wearcue-system-assets-v1",
        "count": len(assets),
        "note": "Images and discovery labels are packaged; components and usage-rights evidence still require manual approval.",
        "assets": assets,
    }
    (output / "system_assets.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
