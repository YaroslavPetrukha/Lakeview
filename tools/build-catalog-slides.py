#!/usr/bin/env python3
"""
Нові слайди для Canva-каталогу «План квартир Lake View» (1920×1080).

  A. Титульний            — рендер aerial + скрими + лого + назва + контакти
  B. Розділювач           — «ПІДЗЕМНИЙ / ПАРКІНГ» у стилі наявних розділювачів
  C. Паркінг, рівень −2   — креслення зліва, темна інфопанель справа
  D. Паркінг, рівень −1   — те саме, 64 місця

Вихід:
  tools/parking/slides/*.png                    растрові підкладки (фон кожного слайда)
  tools/parking/Lakeview-catalog-additions.pptx  4 редаговані слайди для імпорту в Canva

Архітектура: усе, що людина ніколи не редагує (фото, скрими, панель, лого, лінійки,
креслення, міні-схема, смуга дисклеймера), запікається у фонове зображення слайда.
Усе, що людина може захотіти змінити (заголовки, цифри, контакти, дата, дисклеймер),
кладеться справжніми текстовими блоками PPTX → після імпорту в Canva лишається
редагованим текстом.

Геометрія знята піпеткою з експортів самої презентації (ref-divider.png / ref-plan.png),
а не вигадана: ліва межа панелі 1274, контент-колонка 1362…1830, лого 1351…1840 × 69…213,
лінійки на y 670 / 908 / 974, смуга дисклеймера y 972…1079.

Запуск:
    ./.venv/bin/python tools/build-catalog-slides.py [--refs <dir>]
"""

import argparse
import pathlib
import sys

import fitz
from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "tools" / "parking" / "slides"
PPTX_OUT = ROOT / "tools" / "parking" / "Lakeview-catalog-additions.pptx"
PARKING_PDF = ROOT / "tools" / "parking" / "Lakeview-parking-plan.pdf"
AERIAL = ROOT / "img" / "renders" / "aerial.jpg"
FONT_FILE = ROOT / "tools" / "parking" / "Montserrat.ttf"   # Montserrat, OFL

# ── Полотно ────────────────────────────────────────────────────────────────────
W, H = 1920, 1080

# ── Палітра (виміряна з експортів каталогу) ────────────────────────────────────
NAVY = (47, 54, 64)        # #2F3640  фон розділювача, темна панель
LIME = (193, 243, 61)      # #C1F33D  акцент: показники, риска
WHITE = (255, 255, 255)
FOOT_BG = (211, 215, 221)  # #D3D7DD  смуга дисклеймера
FOOT_TX = (74, 81, 92)     # #4A515C  текст дисклеймера (7,0:1 замість 1,35:1 в еталоні)
WATERMARK = (247, 253, 231)  # #F7FDE7  (не використовується: тло лівого поля біле)

# ── Гарнітура ──────────────────────────────────────────────────────────────────
# Не здогадка: PPTX-експорт самої презентації містить рівно дві гарнітури —
# `Montserrat` (заголовки, значення) і `Montserrat Medium` (лейбли, мета-рядки).
FONT = "Montserrat"
FONT_MED = "Montserrat Medium"

# Полотно слайда в EMU — те саме, що віддає експорт Canva (18288000×10287000),
# тобто рівно 1920×1080 px @96 dpi. Завдяки цьому імпортовані сторінки
# збігаються з наявними без перерахунку масштабу.
EMU_PER_PX = 9525

# ── Геометрія слайда плану (еталон ref-plan.png) ───────────────────────────────
PANEL_X = 1274            # ліва межа темної панелі
COL_L, COL_R = 1362, 1830  # контент-колонка панелі
LOGO_BOX = (1351, 69, 490, 145)   # x, y, w, h
RULE_Y = (356, 670, 908, 974)     # горизонтальні лінійки в панелі
FOOT_Y, FOOT_H = 972, 108
DISCLAIMER_W = 928          # решта смуги (x 987…1227, 240 px) — під рядок ред./аркуш:
                            # сам рядок займає 208 px у Montserrat 14, решта — запас
PLAN_FRAME = (84, 60, 1105, 872)  # рамка вписування креслення: x, y, w, h

# ── Геометрія розділювача (еталон ref-divider.png) ─────────────────────────────
DIV_TEXT_X = 1224
DIV_LINE1_TOP, DIV_LINE2_TOP = 461, 546   # cap-top рядків заголовка
DIV_PATCH = (1180, 415, 760, 220)          # зона, яку перефарбовуємо під новий текст

# ── Кадрування рендера 3:2 → 16:9 ──────────────────────────────────────────────
# 2400×1599 → потрібна висота 1350. Зріз 160 зверху / 89 знизу: дах вежі та
# підніжжя лишаються в кадрі, озеро повністю видно.
AERIAL_CROP = (0, 160, 2400, 1510)

# ── Контент слайдів ────────────────────────────────────────────────────────────
TITLE = {
    "h1": "ЖК LAKEVIEW",
    "sub": "Каталог планувань · 07.2026",
    "contacts": "вул. Володимира Великого, 2а, Львів · +38 096 990 03 90 · lakeview.com.ua",
}

DIVIDER = ("ПІДЗЕМНИЙ", "ПАРКІНГ")

LEVELS = [
    {"level": "−2", "spots": "74", "range": "№1–74", "sheet": "аркуш 1 з 2", "pdf_page": 0},
    {"level": "−1", "spots": "64", "range": "№75–138", "sheet": "аркуш 2 з 2", "pdf_page": 1},
]

DISCLAIMER = (
    "Усі розміри — метричні, наведені в міліметрах. Розміри та площі машиномісць є "
    "проєктними; фактичні можуть незначно відрізнятися за результатами технічної "
    "інвентаризації. Креслення виконано не в масштабі та має ілюстративний характер. "
    "Це зображення не є публічною офертою і не є частиною договору. Забудовник залишає "
    "за собою право вносити зміни до проєктних рішень, нумерації та конфігурації "
    "машиномісць. Актуальну інформацію та наявність машиномісць уточнюйте у відділі "
    "продажу: +38\u00a0096\u00a0990\u00a003\u00a090.   © ПП «ДІК \"Вигода\u00a0+\"», ЄДРПОУ\u00a044876801."
)

# Обрізки з вихідного PDF паркінгу (координати PyMuPDF, pt)
# y1=730, а не 799: нижче йде власний підвал A3-аркуша (дисклеймер, ред./дата,
# контакти) — на слайді його роль виконує смуга y972…1079, дубль неприпустимий.
CLIP_PLAN = fitz.Rect(26, 84, 932, 730)
CLIP_SCHEME = fitz.Rect(971.0, 565.0, 1140.5, 697.4)


# ── Допоміжне ──────────────────────────────────────────────────────────────────
def px(v: float) -> Emu:
    """Піксель полотна 1920×1080 → EMU (як в експорті Canva: 1 px = 9525 EMU)."""
    return Emu(int(round(v * EMU_PER_PX)))


def pt_of(px_size: float) -> Pt:
    """Кегль у пікселях полотна → пункти (96 dpi: 1 px = 0,75 pt)."""
    return Pt(px_size * 0.75)


def render_pdf(page_index: int, clip: fitz.Rect, dpi: int = 300) -> Image.Image:
    doc = fitz.open(PARKING_PDF)
    pm = doc[page_index].get_pixmap(clip=clip, dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pm.width, pm.height), pm.samples)


def fit(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    """Contain-вписування без спотворення пропорцій."""
    k = min(box_w / img.width, box_h / img.height)
    return img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS)


def scrim(stops) -> Image.Image:
    """Вертикальний скрим NAVY на все полотно за списком (y, alpha), лінійно між точками."""
    grad = Image.new("L", (1, H))
    for y in range(H):
        for (y0, a0), (y1, a1) in zip(stops, stops[1:]):
            if y0 <= y <= y1:
                t = (y - y0) / max(y1 - y0, 1)
                grad.putpixel((0, y), int(round(255 * (a0 + (a1 - a0) * t))))
                break
        else:
            grad.putpixel((0, y), int(round(255 * (stops[0][1] if y < stops[0][0]
                                                   else stops[-1][1]))))
    layer = Image.new("RGBA", (W, H), NAVY + (0,))
    layer.putalpha(grad.resize((W, H)))
    return layer


def contrast(fg, bg) -> float:
    """Коефіцієнт контрасту WCAG 2.1 між двома RGB."""
    def lum(c):
        ch = [v / 255 for v in c]
        ch = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in ch]
        return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def worst_contrast(img: Image.Image, box, fg) -> float:
    """Найгірший контраст кольору fg до найсвітлішого пікселя зони box."""
    region = img.convert("RGB").crop(box)
    worst = 21.0
    for pxl in set(region.get_flattened_data() if hasattr(region, "get_flattened_data")
                   else region.getdata()):
        worst = min(worst, contrast(fg, pxl))
    return worst


def recolor_scheme(img: Image.Image) -> Image.Image:
    """Міні-схему секцій із чорно-білого креслення — під темну панель."""
    img = img.convert("RGBA")
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    src, dst = img.load(), out.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, _ = src[x, y]
            ink = 255 - min(r, g, b)          # темніше за біле = чорнило
            if ink > 30:
                dst[x, y] = WHITE + (min(255, int(ink * 0.55 * 255 / 255)),)
    return out


# ── Підкладки ──────────────────────────────────────────────────────────────────
def bg_title(refs: pathlib.Path) -> Image.Image:
    photo = Image.open(AERIAL).convert("RGB").crop(AERIAL_CROP).resize((W, H), Image.LANCZOS)
    canvas = photo.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), NAVY + (31,)))           # тон 12 %
    # Скрим: під лого (y 80…225) і під текстовим блоком (y 690…960) щільність
    # ≥0,88 — саме там, де білий і лайм інакше провалюють WCAG над яскравим небом.
    canvas.alpha_composite(scrim([(0, 0.76), (240, 0.65), (330, 0.06),
                                  (600, 0.55), (700, 0.88), (1080, 0.94)]))
    prelogo = canvas.convert("RGB")   # підкладка без знаку — для перевірки контрасту
    logo = Image.open(refs / "logo-light.png").convert("RGBA")
    canvas.alpha_composite(logo.resize((490, 145), Image.LANCZOS), (120, 80))
    d = ImageDraw.Draw(canvas)
    d.rectangle([120, 700, 122, 953], fill=LIME + (255,))                     # лаймова риска
    return canvas.convert("RGB"), prelogo


def bg_divider(refs: pathlib.Path) -> Image.Image:
    """Еталонний розділювач із заклеєною текстовою зоною під новий заголовок."""
    canvas = Image.open(refs / "ref-divider.png").convert("RGB")
    x, y, w, h = DIV_PATCH
    ImageDraw.Draw(canvas).rectangle([x, y, x + w, y + h], fill=NAVY)
    return canvas


def bg_parking(level: dict, refs: pathlib.Path) -> Image.Image:
    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)

    # Ліве поле — чисто біле, як в еталоні: кремовий відтінок там належить
    # заливці кімнат усередині креслення, а не тлу сторінки.

    # креслення — contain у рамку, пропорції A3 недоторкані
    fx, fy, fw, fh = PLAN_FRAME
    plan = fit(render_pdf(level["pdf_page"], CLIP_PLAN), fw, fh)
    canvas.paste(plan, (fx + (fw - plan.width) // 2, fy + (fh - plan.height) // 2))

    # смуга дисклеймера
    d.rectangle([0, FOOT_Y, PANEL_X - 1, H], fill=FOOT_BG)

    # темна панель
    d.rectangle([PANEL_X, 0, W, H], fill=NAVY)

    # лого
    lx, ly, lw, lh = LOGO_BOX
    logo = Image.open(refs / "logo-light.png").convert("RGBA").resize((lw, lh), Image.LANCZOS)
    canvas.paste(logo, (lx, ly), logo)

    # горизонтальні лінійки в ритмі еталона
    for y in RULE_Y:
        d.rectangle([COL_L, y, COL_R, y], fill=WHITE)

    # міні-схема секцій С1–С4
    scheme = recolor_scheme(render_pdf(level["pdf_page"], CLIP_SCHEME, dpi=600))
    scheme = fit(scheme, 248, 186)
    canvas.paste(scheme, (COL_L, 372), scheme)   # 372, а не 348: просвіт під лінійкою y=356

    return canvas


# ── Текст: єдине джерело правди для PPTX і для растрового запасного варіанта ────
# Кожен запис: x, y (cap-top), ширина боксу, кегль, колір, вага, вирівнювання,
# міжрядковий, трекінг, гарнітура. Ті самі числа йдуть і в .pptx, і в .png.
def texts_title():
    return [
        dict(t=TITLE["h1"], x=200, y=700, w=1400, size=104, color=WHITE, bold=True),
        dict(t=TITLE["sub"], x=200, y=826, w=1400, size=36, color=LIME, font=FONT_MED),
        dict(t=TITLE["contacts"], x=200, y=936, w=1500, size=24, color=(214, 217, 222),
             font=FONT_MED),
    ]


def texts_divider():
    return [
        dict(t=DIVIDER[0], x=DIV_TEXT_X, y=DIV_LINE1_TOP, w=660, size=70, color=WHITE, bold=True),
        dict(t=DIVIDER[1], x=DIV_TEXT_X, y=DIV_LINE2_TOP, w=660, size=70, color=WHITE, bold=True),
    ]


def texts_parking(level):
    colw = COL_R - COL_L
    items = [
        dict(t="ПІДЗЕМНИЙ ПАРКІНГ", x=COL_L, y=290, w=colw, size=34, color=WHITE,
             bold=True, tracking=0.68),
        dict(t="РІВЕНЬ", x=COL_L, y=565, w=colw // 2, size=34, color=WHITE, font=FONT_MED),
        dict(t=level["level"], x=COL_L, y=575, w=colw, size=68, color=LIME, bold=True,
             align="right"),
        dict(t="МАШИНО-\nМІСЦЬ", x=COL_L, y=708, w=colw // 2, size=34, color=WHITE,
             spacing=1.26, font=FONT_MED),
        dict(t=level["spots"], x=COL_L, y=719, w=colw, size=68, color=LIME, bold=True,
             align="right"),
    ]
    for y, (lbl, val) in zip((864, 930, 998),
                             (("НУМЕРАЦІЯ", level["range"]),
                              ("ВСЬОГО В ПАРКІНГУ", "138"),
                              ("СЕКЦІЇ", "С1–С4"))):
        items.append(dict(t=lbl, x=COL_L, y=y, w=colw, size=22, color=WHITE, font=FONT_MED))
        items.append(dict(t=val, x=COL_L, y=y, w=colw, size=22, color=WHITE, align="right"))
    items.append(dict(t=DISCLAIMER, x=39, y=985, w=DISCLAIMER_W, size=14, color=FOOT_TX,
                      spacing=1.31, font=FONT_MED, wrap=True))
    # 240 px, а не 187: виміряна ширина рядка в Montserrat 14 = 208 px; при 187
    # Canva переносила його на два рядки
    items.append(dict(t=f"07.2026 · ред. 01 · {level['sheet']}", x=987, y=985, w=240,
                      size=14, color=FOOT_TX, align="right", font=FONT_MED))
    return items


# ── Емісія в PPTX ──────────────────────────────────────────────────────────────
def emit_pptx(slide, item):
    align = {"right": PP_ALIGN.RIGHT, "left": PP_ALIGN.LEFT}[item.get("align", "left")]
    size = item["size"]
    tb = slide.shapes.add_textbox(px(item["x"]), px(item["y"] - size * 0.28),
                                  px(item["w"]), px(size * 1.6))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.TOP
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = item.get("spacing", 1.0)
    run = p.add_run()
    run.text = item["t"]
    f = run.font
    f.name = item.get("font", FONT)
    f.size = pt_of(size)
    f.bold = item.get("bold", False)
    f.color.rgb = RGBColor(*item["color"])
    if item.get("tracking"):
        f._rPr.set("spc", str(int(item["tracking"] * 100)))


# ── Емісія в PNG (запасний варіант + візуальна перевірка) ──────────────────────
def _font(size, bold):
    f = ImageFont.truetype(str(FONT_FILE), size)
    f.set_variation_by_name("Bold" if bold else "Medium")
    return f


def wrap(draw, text, font, width):
    lines, cur = [], ""
    for word in text.split(" "):
        probe = f"{cur} {word}".strip()
        if draw.textlength(probe, font=font) <= width or not cur:
            cur = probe
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    return lines


def emit_png(img, item):
    d = ImageDraw.Draw(img)
    size = item["size"]
    f = _font(size, item.get("bold", False))
    step = round(size * item.get("spacing", 1.0) * 1.0) if item.get("wrap") \
        else round(size * (item.get("spacing", 1.0) + 0.32))
    lines = (wrap(d, item["t"], f, item["w"]) if item.get("wrap")
             else item["t"].split("\n"))
    for i, line in enumerate(lines):
        x = item["x"]
        if item.get("align") == "right":
            x = item["x"] + item["w"] - d.textlength(line, font=f)
        d.text((x, item["y"] - size * 0.26 + i * step), line, font=f, fill=item["color"])
    return len(lines)


def add_slide(prs, bg_path: pathlib.Path):
    slide = prs.slides.add_slide(prs.slide_layouts[6])   # порожній макет
    slide.shapes.add_picture(str(bg_path), 0, 0, px(W), px(H))
    return slide


# ── Збірка ─────────────────────────────────────────────────────────────────────
def build(refs: pathlib.Path):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    title_img, title_prelogo = bg_title(refs)
    backgrounds = {
        "a-title": title_img,
        "b-divider": bg_divider(refs),
        "c-level-2": bg_parking(LEVELS[0], refs),
        "d-level-1": bg_parking(LEVELS[1], refs),
    }
    slides = {
        "a-title": texts_title(),
        "b-divider": texts_divider(),
        "c-level-2": texts_parking(LEVELS[0]),
        "d-level-1": texts_parking(LEVELS[1]),
    }

    for key, img in backgrounds.items():
        img.save(OUT_DIR / f"{key}.png")

    # .pptx — редагований варіант (текст лишається текстом після імпорту в Canva)
    prs = Presentation()
    prs.slide_width, prs.slide_height = px(W), px(H)
    # python-pptx лишає type="screen4x3" від дефолтного шаблону — виправляємо,
    # щоб імпортер не вгадував пропорцію з атрибута замість реальних розмірів.
    prs._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
    ).set("type", "screen16x9")
    for key in ("a-title", "b-divider", "c-level-2", "d-level-1"):
        slide = add_slide(prs, OUT_DIR / f"{key}.png")
        for item in slides[key]:
            emit_pptx(slide, item)
    prs.save(PPTX_OUT)

    # .png — запасний варіант із запеченим текстом + матеріал для перевірки
    flats, overflow = {}, []
    for key, items in slides.items():
        flat = backgrounds[key].copy()
        for item in items:
            n = emit_png(flat, item)
            if item.get("wrap"):
                step = round(item["size"] * item["spacing"])
                bottom = item["y"] + (n - 1) * step + item["size"]
                if bottom > H - 8:
                    overflow.append(f"{key}: дисклеймер у {n} рядків не вміщується у смугу")
        flat.save(OUT_DIR / f"{key}-flat.png")
        flats[key] = flat
        print(f"  ✓ {key}.png / {key}-flat.png  {flat.size[0]}×{flat.size[1]}")

    print(f"  ✓ {PPTX_OUT.relative_to(ROOT)}  ({len(prs.slides._sldIdLst)} слайди)")
    gate({**backgrounds, "a-title-prelogo": title_prelogo}, overflow)


def gate(backgrounds, overflow):
    """Детермінований контроль перед видачею: контраст WCAG + переповнення смуги."""
    checks = [
        ("титул · «ЖК LAKEVIEW»", "a-title", (200, 690, 1400, 800), WHITE, 4.5),
        ("титул · підзаголовок", "a-title", (200, 815, 1400, 870), LIME, 4.5),
        ("титул · контакти", "a-title", (200, 925, 1700, 970), (214, 217, 222), 4.5),
        # зона знаку — по підкладці без самого знаку, інакше міряємо його ж білі пікселі
        ("титул · зона логотипа", "a-title-prelogo", (120, 80, 610, 225), WHITE, 4.5),
        ("розділювач · заголовок", "b-divider", (1224, 450, 1900, 600), WHITE, 4.5),
        ("паркінг · заголовок панелі", "c-level-2", (1362, 280, 1830, 320), WHITE, 4.5),
        # рівно габарити цифр: 1-px хайрлайн на y=670 у зону тексту не входить
        ("паркінг · значення «−2»", "c-level-2", (1600, 570, 1830, 630), LIME, 4.5),
        ("паркінг · значення «74»", "c-level-2", (1600, 714, 1830, 772), LIME, 4.5),
        ("паркінг · дисклеймер", "c-level-2", (39, 980, 1227, 1070), FOOT_TX, 4.5),
    ]
    print("\n  Контроль контрасту (WCAG 2.1 AA, поріг 4,5:1):")
    failed = 0
    for label, key, box, fg, need in checks:
        got = worst_contrast(backgrounds[key], box, fg)
        ok = got >= need
        failed += not ok
        print(f"    {'✓' if ok else '✗'} {label:<32} {got:5.2f}:1")
    for msg in overflow:
        print(f"    ✗ {msg}")
    if failed or overflow:
        sys.exit(f"\n  ✗ {failed + len(overflow)} перевірок(и) не пройдено — слайди не видано.")
    print("  ✓ усі перевірки пройдено")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refs", default=None,
                    help="тека з ref-divider.png, ref-plan.png, logo-light.png")
    args = ap.parse_args()
    refs = pathlib.Path(args.refs) if args.refs else OUT_DIR / "_refs"
    missing = [f for f in ("ref-divider.png", "logo-light.png") if not (refs / f).exists()]
    if missing:
        sys.exit(f"Немає еталонів у {refs}: {', '.join(missing)}")
    if not FONT_FILE.exists():
        sys.exit(f"Немає гарнітури {FONT_FILE} (Montserrat, OFL)")
    build(refs)


if __name__ == "__main__":
    main()
