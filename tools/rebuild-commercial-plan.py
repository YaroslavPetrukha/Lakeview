#!/usr/bin/env python3
"""
Перегенерація одного плану комерції з вихідного ARCHICAD-PDF у повний набір
файлів для сайту: `jpg` + `webp` + `avif` і 720-піксельні варіанти.

Потрібно щоразу, коли архітектор надсилає зміну (файл із суфіксом «Зм»).
Розміри й параметри стиснення повторюють уже наявні файли комплекту:
1400×990 (аркуш A3/A4 альбом дає той самий аспект 1,414) і 720×509.

    ./.venv/bin/python tools/rebuild-commercial-plan.py <src.pdf> <ключ>

Приклад:
    ./.venv/bin/python tools/rebuild-commercial-plan.py \
        img/plans/commercial/_pdf-source/1-й\\ пов/11.pdf c-1-11-67m2
"""

import pathlib
import subprocess
import sys

import fitz
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "img" / "plans" / "commercial"
# Точні розміри наявного комплекту: аркуші A3 і A4 дають 1,414, але через
# округлення рендер інколи віддає 991/510 — приводимо до спільного знаменника,
# бо в розмітці сайту розміри зашиті атрибутами width/height.
FULL = (1400, 990)
THUMB = (720, 509)


def render(pdf: pathlib.Path, size) -> Image.Image:
    page = fitz.open(pdf)[0]
    scale = size[0] / page.rect.width
    pm = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    return img if img.size == size else img.resize(size, Image.LANCZOS)


def emit(img: Image.Image, stem: str, keep_jpg=True):
    jpg = OUT / f"{stem}.jpg"
    img.save(jpg, quality=86, subsampling=0, optimize=True)
    img.save(OUT / f"{stem}.webp", quality=82, method=6)
    # avifenc дає помітно менший файл, ніж Pillow, і саме ним зроблено решту комплекту
    subprocess.run(["avifenc", "--min", "24", "--max", "36", "-s", "4",
                    str(jpg), str(OUT / f"{stem}.avif")],
                   check=True, capture_output=True)
    if not keep_jpg:      # у 720-варіантах комплекту jpg немає — лише webp і avif
        jpg.unlink()
    print(f"    {stem}: {img.width}×{img.height}")


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pdf, key = pathlib.Path(sys.argv[1]), sys.argv[2]
    if not pdf.exists():
        sys.exit(f"Немає {pdf}")
    emit(render(pdf, FULL), key)
    emit(render(pdf, THUMB), f"{key}-720", keep_jpg=False)
    print(f"  ✓ {key}: 5 файлів оновлено")


if __name__ == "__main__":
    main()
