"""Resize downloaded images using paths relative to the project root."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

from config import CONFIG, ensure_directories


EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}


def resize_folder(source: Path, destination: Path, max_side: int) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    count = 0
    for source_file in sorted(source.iterdir()):
        if not source_file.is_file() or source_file.suffix.lower() not in EXTENSIONS:
            continue
        try:
            with Image.open(source_file) as image:
                image = ImageOps.exif_transpose(image)
                if max(image.size) > max_side:
                    scale = max_side / max(image.size)
                    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
                target = destination / source_file.name
                if target.suffix.lower() in {".jpg", ".jpeg"} and image.mode in {"RGBA", "LA", "P"}:
                    image = image.convert("RGB")
                image.save(target, quality=95, optimize=True)
                count += 1
                print(f"OK: {source_file.name} -> {image.size}")
        except Exception as error:
            print(f"Ошибка: {source_file.name}: {error}")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Уменьшение изображений")
    parser.add_argument("-i", "--input", type=Path, default=CONFIG.output_dir)
    parser.add_argument("-o", "--output", type=Path, default=CONFIG.resized_dir)
    parser.add_argument(
        "--max-side",
        type=int,
        default=CONFIG.resize_max_side,
        help=f"Максимальная сторона изображения, по умолчанию: {CONFIG.resize_max_side}px",
    )
    args = parser.parse_args()
    ensure_directories()
    if not args.input.exists():
        print(f"Исходная папка не найдена: {args.input.resolve()}")
        return 2
    print(f"Обработано файлов: {resize_folder(args.input, args.output, args.max_side)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
