from io import BytesIO
from pathlib import Path
from statistics import median

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

    @staticmethod
    def outfit_colors(path: Path) -> dict[str, tuple[str, str]]:
        """Estimate each garment colour from the usual full-body photo regions."""
        boxes = {
            "top": (0.40, 0.34, 0.68, 0.54),
            "bottom": (0.39, 0.54, 0.70, 0.75),
            "shoes": (0.40, 0.86, 0.66, 0.96),
        }
        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            width, height = image.size
            colors = {}
            for slot, (left, top, right, bottom) in boxes.items():
                sample = image.crop((width * left, height * top, width * right, height * bottom))
                sample.thumbnail((80, 80))
                pixels = sorted(sample.get_flattened_data(), key=sum)
                pixels = pixels[int(len(pixels) * 0.55):int(len(pixels) * 0.88)] or pixels
                rgb = tuple(int(median(pixel[index] for pixel in pixels)) for index in range(3))
                colors[slot] = ImageService._named_color(rgb)
        return colors

    @staticmethod
    def _named_color(rgb: tuple[int, int, int]) -> tuple[str, str]:
        red, green, blue = rgb
        light = max(rgb)
        spread = light - min(rgb)
        if light >= 180 and spread <= 40:
            return "白色", "#f4f1e8"
        if light <= 55:
            return "黑色", "#242424"
        if red - blue >= 18 and green - blue >= 8:
            return "卡其色", "#a58f63"
        if spread <= 24:
            value = "#d1d1cd" if light >= 165 else "#858782" if light >= 100 else "#555753"
            return "灰色", value
        return "图片近似色", f"#{red:02x}{green:02x}{blue:02x}"
