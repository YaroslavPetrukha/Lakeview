#!/usr/bin/env python3
"""
Веб-план паркінгу для секції «Машиномісця у продажу» (26.10.2026).

Вхід : tools/parking/Lakeview-parking-plan.pdf  (стор. 1 = рівень −2, місця 1–74;
                                                  стор. 2 = рівень −1, місця 75–138)
Вихід: img/parking/level-2.{png,webp,avif}, level-1.{png,webp,avif}  — 2400×1711
       img/parking/spots.json                                         — геометрія 138 місць, % зображення
       tools/parking/sale-2026-10/qa-level-*.png                      — перевірка збігу контурів
       tools/parking/sale-2026-10/slide-level-*-sale.png              — слайди каталогу з виділеними місцями

Геометрія місця береремося з векторів, не на око: кожне місце — це штриховка
(21–22 сірих діагональних лінії кольору 0.753, обрізаних контуром місця);
габарит зв'язаної групи ліній = прямокутник місця. Номер (Arial-Bold 10.9 pt)
призначається групі, що містить його центр.

Запуск: ./.venv/bin/python tools/build-parking-web.py
"""
import collections
import json
import pathlib
import shutil
import subprocess
import sys

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF = ROOT / "tools" / "parking" / "Lakeview-parking-plan.pdf"
OUT = ROOT / "img" / "parking"
SALE_DIR = ROOT / "tools" / "parking" / "sale-2026-10"
FONT = ROOT / "tools" / "parking" / "Montserrat.ttf"
# Слайди клієнта (Canva-експорт 26.10.2026, 1920×1080). Область креслення пікселя-в-піксель
# збігається з tools/parking/slides/{c,d}-*-flat.png; відрізняється лише текст панелі/підвалу.
CLIENT_SLIDES = {
    "-2": ROOT / "tools" / "parking" / "sale-2026-10" / "client" / "client-level-2.png",
    "-1": ROOT / "tools" / "parking" / "sale-2026-10" / "client" / "client-level-1.png",
}
# Для іншого слайда: --client-2 <png> / --client-1 <png>
CLIP = fitz.Rect(26, 84, 932, 730)      # той самий, що в build-catalog-slides.py
W, H = 2400, 1711
SALE = {"-2": [23, 24, 28, 29, 32, 34, 35, 37, 39, 40, 43, 48, 56, 59, 61, 62, 63, 67],
        "-1": [110, 117, 118, 127, 130, 134, 135, 138]}
LEVELS = {"-2": dict(page=0, name="level-2", lo=1, hi=74),
          "-1": dict(page=1, name="level-1", lo=75, hi=138)}
GOLD = (0xC5, 0xA5, 0x5A)
LIME = (0xC1, 0xF3, 0x3D)


def bay_rects(page):
    """{номер: fitz.Rect} з векторної штриховки."""
    segs = [fitz.Rect(x["rect"]) for x in page.get_drawings()
            if x["type"] == "s" and x.get("color") and abs(x["color"][0] - 0.7529) < 0.01
            and len(x["items"]) == 1 and x["items"][0][0] == "l"]
    par = list(range(len(segs)))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i, a in enumerate(segs):
        for j in range(i + 1, len(segs)):
            b = segs[j]
            if min(a.x1, b.x1) - max(a.x0, b.x0) > 0.3 and min(a.y1, b.y1) - max(a.y0, b.y0) > 0.3:
                par[find(i)] = find(j)
    box, cnt = {}, collections.Counter()
    for i, s in enumerate(segs):
        k = find(i)
        r = box.get(k, fitz.Rect(1e9, 1e9, -1e9, -1e9))
        box[k] = fitz.Rect(min(r.x0, s.x0), min(r.y0, s.y0), max(r.x1, s.x1), max(r.y1, s.y1))
        cnt[k] += 1
    groups = [box[k] for k in box if cnt[k] in (21, 22)]   # штриховка одного місця
    nums = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t.isdigit() and s["size"] > 8:          # жирні номери місць, не розміри
                    bb = fitz.Rect(s["bbox"])
                    nums.append((int(t), (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2))
    out = {}
    for n, cx, cy in nums:
        hit = [g for g in groups if g.x0 <= cx <= g.x1 and g.y0 <= cy <= g.y1]
        if len(hit) != 1:
            sys.exit(f"bay {n}: {len(hit)} candidate rects (need exactly 1)")
        out[n] = hit[0]
    if len(set(map(tuple, out.values()))) != len(out):
        sys.exit("two bays share one rect")
    return out


def render(page):
    sx, sy = W / CLIP.width, H / CLIP.height
    pm = page.get_pixmap(matrix=fitz.Matrix(sx, sy), clip=CLIP, alpha=False)
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    return img


def encode(img, base):
    png, webp, avif = (OUT / f"{base}.{e}" for e in ("png", "webp", "avif"))
    img.save(png, optimize=True)
    subprocess.run(["cwebp", "-quiet", "-q", "82", "-m", "6", "-sharp_yuv", str(png), "-o", str(webp)], check=True)
    subprocess.run(["avifenc", "-q", "60", "-s", "4", "-y", "444", str(png), str(avif)],
                   check=True, stdout=subprocess.DEVNULL)


def px(r):
    return ((r.x0 - CLIP.x0) * W / CLIP.width, (r.y0 - CLIP.y0) * H / CLIP.height,
            (r.x1 - CLIP.x0) * W / CLIP.width, (r.y1 - CLIP.y0) * H / CLIP.height)


def qa(img, rects, sale, path):
    base = img.convert("RGBA")
    fill = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fd = ImageDraw.Draw(fill)
    for n in sale:
        fd.rectangle(px(rects[n]), fill=GOLD + (115,))
    base = Image.alpha_composite(base, fill)
    d = ImageDraw.Draw(base)
    for r in rects.values():
        d.rectangle(px(r), outline=(255, 0, 0, 255), width=1)
    base.convert("RGB").save(path, optimize=True)


def slide(client_png, rects, sale, path):
    """Слайд клієнта + лайм-заливка місць у продажу + легенда. Усе, що поза кресленням, не змінюється."""
    img = Image.open(client_png).convert("RGB")
    # геометрія з build-catalog-slides.py: креслення contain у рамку (84,60,1105,872)
    fx, fy, fw, fh = 84, 60, 1105, 872
    pw, ph = CLIP.width * 300 / 72, CLIP.height * 300 / 72      # px при 300 dpi
    k = min(fw / pw, fh / ph)
    sw, sh = round(pw * k), round(ph * k)
    ox, oy = fx + (fw - sw) // 2, fy + (fh - sh) // 2
    kx, ky = sw / CLIP.width, sh / CLIP.height
    over = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(over)
    for n in sale:
        r = rects[n]
        od.rectangle([ox + (r.x0 - CLIP.x0) * kx, oy + (r.y0 - CLIP.y0) * ky,
                      ox + (r.x1 - CLIP.x0) * kx, oy + (r.y1 - CLIP.y0) * ky], fill=LIME + (140,))
    img = Image.alpha_composite(img.convert("RGBA"), over)
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype(str(FONT), 22)
    x, y = 900, 96            # вільне поле над кресленням, в межах області креслення (x<1274, y<972)
    d.rectangle([x, y, x + 30, y + 22], fill=LIME + (255,), outline=(47, 54, 64, 255))
    d.text((x + 42, y + 11), "У продажу", font=f, fill=(47, 54, 64, 255), anchor="lm")
    img.convert("RGB").save(path, optimize=True)


def main():
    client = {}
    a = sys.argv[1:]
    for key, flag in (("-2", "--client-2"), ("-1", "--client-1")):
        client[key] = pathlib.Path(a[a.index(flag) + 1]) if flag in a else CLIENT_SLIDES[key]
    OUT.mkdir(parents=True, exist_ok=True)
    SALE_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(PDF)
    spec = {"version": "2026-10-26", "levels": {}}
    for lv, cfg in LEVELS.items():
        page = doc[cfg["page"]]
        rects = bay_rects(page)
        want = set(range(cfg["lo"], cfg["hi"] + 1))
        if set(rects) != want:
            sys.exit(f"level {lv}: bays {sorted(set(rects) ^ want)} mismatch")
        miss = [n for n in SALE[lv] if n not in rects]
        if miss:
            sys.exit(f"sale bays missing: {miss}")
        img = render(page)
        encode(img, cfg["name"])
        spots = {}
        for n in sorted(rects):
            x0, y0, x1, y1 = px(rects[n])
            spots[str(n)] = [round(x0 / W * 100, 2), round(y0 / H * 100, 2),
                             round((x1 - x0) / W * 100, 2), round((y1 - y0) / H * 100, 2)]
        spec["levels"][lv] = {"w": W, "h": H, "spots": spots}
        qa(img, rects, SALE[lv], SALE_DIR / f"qa-{cfg['name']}.png")
        slide(client[lv], rects, SALE[lv], SALE_DIR / f"slide-{cfg['name']}-sale.png")
        print(f"level {lv}: {len(rects)} bays matched from vector hatching, 0 manual fixes")
    (OUT / "spots.json").write_text(json.dumps(spec, ensure_ascii=False, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
