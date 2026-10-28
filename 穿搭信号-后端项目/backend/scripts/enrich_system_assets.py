"""Precompute detail content for reviewed system photos.

The discovery manifest is the production source of truth. This command analyzes
the existing photos once and writes the resulting garment breakdown and copy
back to the manifest, so opening a detail page never starts an AI request.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import httpx

from app.services.vision_service import VisionService, VisionServiceError


DEFAULTS_DIR = Path(__file__).resolve().parents[1] / "app" / "defaults"
MANIFEST_PATH = DEFAULTS_DIR / "system_assets.json"


def complete(entry: dict) -> bool:
    return bool(
        entry.get("content_ready")
        and entry.get("components")
        and entry.get("outfit_analysis", {}).get("summary")
        and entry.get("replication_guide", {}).get("steps")
    )


def write_manifest(payload: dict) -> None:
    temporary = MANIFEST_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(MANIFEST_PATH)


def failure_detail(error: Exception) -> str:
    cause = error.__cause__
    if isinstance(cause, httpx.HTTPStatusError):
        body = cause.response.text.replace("\n", " ")[:500]
        return f"HTTP {cause.response.status_code}: {body}"
    if cause:
        return f"{type(cause).__name__}: {cause}"
    return str(error)


async def analyze_entry(service: VisionService, entry: dict) -> dict:
    result = await service.analyze(DEFAULTS_DIR / entry["image"])
    guide = dict(result["replication_guide"])
    guide["weather_note"] = (
        f"适穿温度为 {entry['suitable_min']}～{entry['suitable_max']}℃，"
        "按当天体感增减外层。"
    )
    return {
        "components": result["components"],
        "outfit_analysis": result["outfit_analysis"],
        "replication_guide": guide,
        "reference_outfit": result.get("reference_outfit", {}),
        "outfit_dna": result.get("outfit_dna", {}),
        "signature_features": result.get("signature_features", []),
        "locked_features": result.get("locked_features", []),
        "content_ready": True,
        "content_version": result.get("model_version", "wearcue-vision-v3"),
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=3)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    pending = [entry for entry in payload["assets"] if not complete(entry)]
    if args.limit > 0:
        pending = pending[: args.limit]
    service = VisionService()
    if not service.configured:
        raise SystemExit("Vision service is not configured")

    semaphore = asyncio.Semaphore(max(1, args.concurrency))

    async def run(entry: dict) -> tuple[dict, dict | Exception]:
        async with semaphore:
            try:
                return entry, await analyze_entry(service, entry)
            except (VisionServiceError, KeyError, TypeError, ValueError) as error:
                return entry, error

    completed_count = 0
    failed: list[str] = []
    for start in range(0, len(pending), max(1, args.concurrency)):
        batch = pending[start : start + max(1, args.concurrency)]
        for entry, result in await asyncio.gather(*(run(entry) for entry in batch)):
            if isinstance(result, Exception):
                detail = failure_detail(result)
                failed.append(f"{entry['asset_id']}: {detail}")
                print(f"failed {entry['asset_id']}: {detail}", flush=True)
                continue
            entry.update(result)
            completed_count += 1
            print(
                f"ready {entry['asset_id']} "
                f"({len(result['components'])} components)",
                flush=True,
            )
        if not args.dry_run:
            write_manifest(payload)

    print(
        f"completed={completed_count} failed={len(failed)} "
        f"dry_run={args.dry_run}",
        flush=True,
    )
    if failed:
        raise SystemExit("\n".join(failed))


if __name__ == "__main__":
    asyncio.run(main())
