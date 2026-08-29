"""Bundle confirmed outfits and their images as versioned system defaults."""

import argparse
import json
import shutil
import sqlite3
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULTS_DIR = PROJECT_DIR / "backend" / "app" / "defaults"


def parse_json(row: sqlite3.Row, key: str):
    return json.loads(row[key])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("outfit_ids", nargs="+")
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--database", type=Path, default=PROJECT_DIR / "data" / "outfit-signal.sqlite3")
    args = parser.parse_args()

    manifest_path = DEFAULTS_DIR / "outfits.json"
    images_dir = DEFAULTS_DIR / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"version": 0, "outfits": []}
    existing_entries = {entry["outfit"]["id"]: entry for entry in manifest["outfits"]}

    database = sqlite3.connect(args.database)
    database.row_factory = sqlite3.Row
    for outfit_id in args.outfit_ids:
        outfit = database.execute("SELECT * FROM outfits WHERE id=?", (outfit_id,)).fetchone()
        if not outfit:
            raise SystemExit(f"Outfit not found: {outfit_id}")
        inspiration = database.execute(
            "SELECT * FROM inspirations WHERE id=?", (outfit["inspiration_id"],)
        ).fetchone()
        if not inspiration:
            raise SystemExit(f"Inspiration not found for outfit: {outfit_id}")

        source_path = Path(inspiration["file_path"])
        if not source_path.is_absolute():
            source_path = PROJECT_DIR / source_path
        filenames = {
            "original": f"{inspiration['id']}.jpg",
            "medium": f"{inspiration['id']}_medium.jpg",
            "thumbnail": f"{inspiration['id']}_thumb.jpg",
        }
        source_paths = {
            "original": source_path,
            "medium": source_path.with_name(f"{source_path.stem}_medium{source_path.suffix}"),
            "thumbnail": source_path.with_name(f"{source_path.stem}_thumb{source_path.suffix}"),
        }
        for size, path in source_paths.items():
            if not path.is_file():
                raise SystemExit(f"Image not found: {path}")
            shutil.copy2(path, images_dir / filenames[size])

        existing_entries[outfit_id] = {
            "introduced_in": args.version,
            "inspiration": {
                "id": inspiration["id"],
                "upload_key": inspiration["upload_key"],
                "content_hash": inspiration["content_hash"],
                "original_name": inspiration["original_name"],
                "media_type": inspiration["media_type"],
                "provider": inspiration["provider"],
                "result": parse_json(inspiration, "result_json"),
                "image_files": filenames,
            },
            "outfit": {
                "id": outfit["id"],
                "label": outfit["label"],
                "audience": outfit["audience"],
                "source": "system",
                "components": parse_json(outfit, "components_json"),
                "scene_ids": parse_json(outfit, "scene_ids_json"),
                "suitable_min": outfit["suitable_min"],
                "suitable_max": outfit["suitable_max"],
                "favorite": bool(outfit["favorite"]),
                "in_pool": bool(outfit["in_pool"]),
                "replication_guide": parse_json(outfit, "replication_json"),
                "outfit_analysis": parse_json(outfit, "analysis_json"),
            },
        }

    manifest = {"version": max(args.version, int(manifest["version"])), "outfits": list(existing_entries.values())}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
