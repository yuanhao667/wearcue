from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps


SIZES = {"original": (2400, 2400), "medium": (800, 800), "thumbnail": (400, 400)}


class ImageService:
    """Adapted from Wardrowbe: EXIF correction plus three private JPEG sizes."""

    def __init__(self, storage_path: Path) -> None:
        self.storage_path = storage_path
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def process_and_store(self, image_data: bytes, digest: str) -> dict[str, str]:
        image = ImageOps.exif_transpose(Image.open(BytesIO(image_data)))
        if image.mode in ("RGBA", "LA", "P"):
            source = image.convert("RGBA")
            background = Image.new("RGBA", source.size, "white")
            background.alpha_composite(source)
            image = background.convert("RGB")
        elif image.mode != "RGB":
            image = image.convert("RGB")

        paths: dict[str, str] = {}
        for name, size in SIZES.items():
            suffix = "" if name == "original" else "_medium" if name == "medium" else "_thumb"
            path = self.storage_path / (digest + suffix + ".jpg")
            resized = image.copy()
            resized.thumbnail(size, Image.Resampling.LANCZOS)
            quality = {"original": 95, "medium": 75, "thumbnail": 82}[name]
            resized.save(path, "JPEG", quality=quality, optimize=True)
            paths[name] = str(path)
        return paths

    @staticmethod
    def sized_path(original: Path, size: str) -> Path:
        suffix = "" if size == "original" else "_medium" if size == "medium" else "_thumb"
        return original.with_name(original.stem + suffix + original.suffix)
