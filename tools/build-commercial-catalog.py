#!/usr/bin/env python3
"""
Каталог комерційних приміщень ЖК Lakeview — 35 слайдів 1920×1080.

  A  титульний            рендер closeup + лого + заголовок + контакти
  B  розділювачі          ПЕРШИЙ/ДРУГИЙ ПОВЕРХ, ДУПЛЕКС 412 М², ВІДДІЛ ПРОДАЖУ
  C  master-план поверху  розкладка всіх лотів + зведення в панелі
  D  приміщення (×28)     креслення зліва, панель справа
  E  контактний слайд

Виходить `Lakeview-commercial-catalog.pptx` — Canva імпортує його як редагований
дизайн (текст лишається текстом). Растрові підкладки — у `slides-commercial/`.

Джерело креслень — ВЕКТОРНІ `img/plans/commercial/_pdf-source/**/*.pdf`, а не
готові JPG: у JPG уже вкладено власну верстку архітектора (фірмова смуга зверху
y 48…141 і сіра інфопанель праворуч від x=973), яка дублювала б нашу панель.

Масштаб креслень — ЄДИНИЙ для всіх лотів (глобальний k), тому 42-метрове
приміщення на слайді дрібніше за 163-метрове. Це і є товар: порівнювати площі
на око можна лише в одному масштабі.

Запуск:
    ./.venv/bin/python tools/build-commercial-catalog.py
"""

import importlib.util
import json
import pathlib
import sys

import fitz
import numpy as np
from PIL import Image, ImageDraw
from pptx import Presentation

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Спільні примітиви (px/pt, скрим, контраст, вписування, емісія тексту) беремо
# з уже перевіреного складальника каталогу квартир — щоб два каталоги фізично
# не могли розійтися в одиницях і в способі емісії тексту.
_spec = importlib.util.spec_from_file_location("bcs", ROOT / "tools" / "build-catalog-slides.py")
bcs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcs)

W, H = bcs.W, bcs.H
NAVY, LIME, WHITE = bcs.NAVY, bcs.LIME, bcs.WHITE
FOOT_BG, FOOT_TX = bcs.FOOT_BG, bcs.FOOT_TX
FONT, FONT_MED = bcs.FONT, bcs.FONT_MED
PANEL_X, COL_L, COL_R = bcs.PANEL_X, bcs.COL_L, bcs.COL_R
LOGO_BOX, RULE_Y, FOOT_Y = bcs.LOGO_BOX, bcs.RULE_Y, bcs.FOOT_Y
DIV_TEXT_X, DIV_PATCH = bcs.DIV_TEXT_X, bcs.DIV_PATCH
DIV_L1, DIV_L2 = bcs.DIV_LINE1_TOP, bcs.DIV_LINE2_TOP

OUT_DIR = ROOT / "tools" / "commercial" / "slides"
PPTX_OUT = ROOT / "tools" / "commercial" / "Lakeview-commercial-catalog.pptx"
REFS = ROOT / "tools" / "parking" / "slides" / "_refs"
MANIFEST = ROOT / "img" / "plans" / "commercial" / "_manifest.json"
PDF_SRC = ROOT / "img" / "plans" / "commercial" / "_pdf-source"
RENDER = ROOT / "img" / "renders" / "closeup.jpg"

REV = "08.2026 · ред. 01"

# ── Геометрія ──────────────────────────────────────────────────────────────────
UNIT_FRAME = (84, 60, 1105, 872)     # рамка креслення лота — з еталона квартири
MASTER_FRAME = (40, 44, 1194, 888)   # master ширший, тому власна рамка
PAD = 20                             # поле навколо креслення всередині кропу

# Вихідні A4-альбом 841,89×595,28 pt; готові JPG зроблено з коефіцієнтом 1400/841,89
K = 1400 / 841.89                    # px/pt — той самий масштаб, що в готових JPG
BAND_Y_SRC = 141 / K                 # низ фірмової смуги архітектора, у pt
PANEL_X_SRC = 968 / K                # ліва межа сірої панелі, у pt (лише аркуші лотів);
                                     # 968, а не 974: на 971…973 стоїть рамка панелі,
                                     # інакше вона потрапляє в кроп вертикальною лінією


def sheet_clip(page):
    """Кадр без фірмової смуги і без сірої панелі архітектора.

    Аркуші лотів — A4 альбом (841,89 pt) із панеллю праворуч від 974 px.
    Master-плани поверхів — A3 альбом (1190,55 pt) і панелі не мають взагалі:
    обрізати їх по A4-координаті означало б відрізати половину поверху."""
    right = PANEL_X_SRC if page.rect.width < 1000 else page.rect.width
    return fitz.Rect(0, BAND_Y_SRC, right, page.rect.height)

TITLE = {
    "eyebrow": "ЖК LAKEVIEW · ЛЬВІВ",
    "h1": "КОМЕРЦІЙНІ ПРИМІЩЕННЯ",
    "sub": "Каталог планувань · 08.2026",
    "contacts": "вул. Володимира Великого, 2а, Львів · +38 096 990 03 90 · lakeview.com.ua",
}

CONTACTS = [
    ("+38 096 990 03 90", 34, LIME, True, 575),
    ("вул. В. Великого, 4, каб. 406, Львів", 22, WHITE, False, 631),
    ("vygoda.sales@gmail.com", 22, WHITE, False, 673),
    ("lakeview.com.ua · @lakeviewlviv", 22, WHITE, False, 715),
    ("© ПП «ДІК \"Вигода +\"», ЄДРПОУ 44876801", 14, (167, 175, 188), False, 790),
]

DISCLAIMER = (
    "Розміри наведені в міліметрах. Площі та габарити приміщень є проєктними; "
    "фактичні визначаються за результатами технічної інвентаризації. Креслення "
    "виконано не в масштабі та має ілюстративний характер. Матеріал є інформаційним, "
    "не є публічною офертою і не є частиною договору. Забудовник залишає "
    "за собою право вносити зміни до проєктних рішень, нумерації та конфігурації "
    "приміщень. Актуальну інформацію щодо наявності, площ і умов придбання уточнюйте "
    "у відділі продажу: +38 096 990 03 90.   "
    "© ПП «ДІК \"Вигода +\"», ЄДРПОУ 44876801."
)


# ── Витяг креслення з векторного джерела ───────────────────────────────────────
def _ink_bbox(page, clip, dpi_scale):
    """bbox чорнила без рамки аркуша: суцільні лінії на всю ширину/висоту зони
    (рамка, смуга, межа панелі) відкидаються, інакше вони «роздувають» кроп."""
    pm = page.get_pixmap(clip=clip, matrix=fitz.Matrix(dpi_scale, dpi_scale), alpha=False)
    a = np.asarray(Image.frombytes("RGB", (pm.width, pm.height), pm.samples).convert("L"), int)
    ink = a < 245
    h, w = ink.shape
    solid_rows = ink.sum(axis=1) > 0.95 * w
    solid_cols = ink.sum(axis=0) > 0.95 * h
    core = ink.copy()
    core[solid_rows, :] = False
    core[:, solid_cols] = False
    ys, xs = np.where(core)
    if not len(ys):
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def drawing(pdf_path: pathlib.Path, scale: float) -> Image.Image:
    """Креслення без брендової смуги, сірої панелі та рамки аркуша."""
    page = fitz.open(pdf_path)[0]
    clip = sheet_clip(page)
    box = _ink_bbox(page, clip, K)
    if box is None:
        sys.exit(f"У {pdf_path.name} не знайдено креслення")
    x0, y0, x1, y1 = box
    tight = fitz.Rect(clip.x0 + (x0 - PAD) / K, clip.y0 + (y0 - PAD) / K,
                      clip.x0 + (x1 + PAD) / K, clip.y0 + (y1 + PAD) / K) & clip
    pm = page.get_pixmap(clip=tight, matrix=fitz.Matrix(K * scale * 3, K * scale * 3), alpha=False)
    img = Image.frombytes("RGB", (pm.width, pm.height), pm.samples)
    return img.resize((round(img.width / 3), round(img.height / 3)), Image.LANCZOS)


def footprint(pdf_path: pathlib.Path):
    page = fitz.open(pdf_path)[0]
    clip = sheet_clip(page)
    box = _ink_bbox(page, clip, K)
    return (box[2] - box[0] + 2 * PAD, box[3] - box[1] + 2 * PAD) if box else (0, 0)


# ── Дані ───────────────────────────────────────────────────────────────────────
def load_units():
    man = json.loads(MANIFEST.read_text())
    units = []
    for key, m in man.items():
        if key.startswith("c-floor"):
            continue
        code = int(m["code"])
        pdf = PDF_SRC / ("1-й пов" if m["floor"] == "1" else "2-й пов") / f"{code:02d}.pdf"
        if key == "c-duplex-06-floor2":
            pdf = PDF_SRC / "1-й пов" / "06 (2п.).pdf"
        units.append(dict(key=key, code=code, floor=m["floor"], section=m["section"],
                          area=m["area"], height=m["height"], pdf=pdf,
                          duplex=key.startswith("c-duplex")))
    units.sort(key=lambda u: (u["floor"] != "1", u["code"], u["key"]))
    missing = [u["pdf"].name for u in units if not u["pdf"].exists()]
    if missing:
        sys.exit(f"Немає вихідних креслень: {', '.join(missing)}")
    return units


# ── Підкладки ──────────────────────────────────────────────────────────────────
def bg_title():
    photo = Image.open(RENDER).convert("RGB").crop((0, 180, 2400, 1530)).resize((W, H), Image.LANCZOS)
    canvas = photo.convert("RGBA")
    canvas.alpha_composite(Image.new("RGBA", (W, H), NAVY + (31,)))
    canvas.alpha_composite(bcs.scrim([(0, 0.76), (240, 0.65), (330, 0.06),
                                      (600, 0.55), (700, 0.88), (1080, 0.94)]))
    prelogo = canvas.convert("RGB")
    logo = Image.open(REFS / "logo-light.png").convert("RGBA")
    canvas.alpha_composite(logo.resize((490, 145), Image.LANCZOS), (120, 80))
    ImageDraw.Draw(canvas).rectangle([120, 652, 122, 953], fill=LIME + (255,))
    return canvas.convert("RGB"), prelogo


def bg_divider(tall=False):
    canvas = Image.open(REFS / "ref-divider.png").convert("RGB")
    x, y, w, h = DIV_PATCH
    if tall:
        h = 420
    ImageDraw.Draw(canvas).rectangle([x, y, x + w, y + h], fill=NAVY)
    return canvas


def bg_sheet(pdf_path, frame, scale, rules=None):
    """Спільна підкладка слайдів C і D: креслення зліва, панель справа."""
    canvas = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(canvas)
    fx, fy, fw, fh = frame
    plan = drawing(pdf_path, scale)
    if plan.width > fw or plan.height > fh:      # страховка від виходу за рамку
        plan = bcs.fit(plan, fw, fh)
    canvas.paste(plan, (fx + (fw - plan.width) // 2, fy + (fh - plan.height) // 2))
    d.rectangle([0, FOOT_Y, PANEL_X - 1, H], fill=FOOT_BG)
    d.rectangle([PANEL_X, 0, W, H], fill=NAVY)
    lx, ly, lw, lh = LOGO_BOX
    logo = Image.open(REFS / "logo-light.png").convert("RGBA").resize((lw, lh), Image.LANCZOS)
    canvas.paste(logo, (lx, ly), logo)
    for y in (RULE_Y if rules is None else rules):
        d.rectangle([COL_L, y, COL_R, y], fill=WHITE)
    return canvas


# ── Текст ──────────────────────────────────────────────────────────────────────
def t(txt, x, y, w, size, color, **kw):
    return dict(t=txt, x=x, y=y, w=w, size=size, color=color, **kw)


def fit_size(txt, size, avail, bold=True, floor=32):
    """Зменшує кегль, поки рядок не влізе у вільну ширину поруч із лейблом.
    Потрібно для діапазонів на кшталт «42,4–162,9», які в 68 px налазять на підпис."""
    from PIL import ImageDraw, Image
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    while size > floor and d.textlength(txt, font=bcs._font(size, bold)) > avail:
        size -= 2
    return size


def texts_title():
    return [
        t(TITLE["eyebrow"], 200, 652, 700, 22, LIME, font=FONT_MED, tracking=2.0),
        t(TITLE["h1"], 200, 700, 1560, 104, WHITE, bold=True),
        t(TITLE["sub"], 200, 826, 1500, 36, LIME, font=FONT_MED),
        t(TITLE["contacts"], 200, 936, 1500, 24, (214, 217, 222), font=FONT_MED),
    ]


def texts_divider(l1, l2=None):
    if l2 is None:
        return [t(l1, DIV_TEXT_X, 503, 660, 70, WHITE, bold=True)]
    return [t(l1, DIV_TEXT_X, DIV_L1, 660, 70, WHITE, bold=True),
            t(l2, DIV_TEXT_X, DIV_L2, 660, 70, WHITE, bold=True)]


def texts_contact():
    items = [t("ВІДДІЛ", DIV_TEXT_X, DIV_L1, 660, 70, WHITE, bold=True),
             t("ПРОДАЖУ", DIV_TEXT_X, DIV_L2, 660, 70, WHITE, bold=True)]
    for txt, size, color, bold, y in CONTACTS:
        items.append(t(txt, DIV_TEXT_X, y + 120, 700, size, color,
                       bold=bold, font=FONT if bold else FONT_MED))
    return items


def _footer(sheet_no, total):
    return [t(DISCLAIMER, 39, 985, bcs.DISCLAIMER_W, 14, FOOT_TX,
              spacing=1.31, font=FONT_MED, wrap=True),
            t(f"{REV} · аркуш {sheet_no} з {total}", 987, 985, 240, 14, FOOT_TX,
              align="right", font=FONT_MED)]


def texts_master(floor, stats, sheet_no, total):
    colw = COL_R - COL_L
    items = [t(stats["title"], COL_L, 290, colw, 34, WHITE, bold=True, tracking=0.68),
             t("ПРИМІЩЕНЬ", COL_L, 565, colw // 2, 34, WHITE, font=FONT_MED),
             t(stats["count"], COL_L, 575, colw, 68, LIME, bold=True, align="right"),
             t(stats["range_label"], COL_L, 700, colw // 2, 34, WHITE,
               font=FONT_MED, spacing=1.26),
             t(stats["range"], COL_L, 726, colw,
               fit_size(stats["range"], 68, colw - 235), LIME, bold=True, align="right")]
    for y, (lbl, val) in zip((864, 930, 998), stats["meta"]):
        items.append(t(lbl, COL_L, y, colw, 22, WHITE, font=FONT_MED))
        items.append(t(val, COL_L, y, colw, 22, WHITE, align="right"))
    return items + _footer(sheet_no, total)


def texts_unit(u, sheet_no, total):
    colw = COL_R - COL_L
    title = f"ДУПЛЕКС №{u['code']:02d}" if u["duplex"] else f"ПРИМІЩЕННЯ №{u['code']:02d}"
    items = [
        t(title, COL_L, 290, colw, 34, WHITE, bold=True, tracking=0.68),
        t("ЗАГАЛЬНА\nПЛОЩА, М²", COL_L, 565, colw // 2, 34, WHITE, spacing=1.26, font=FONT_MED),
        t(u["area"], COL_L, 575, colw, 68, LIME, bold=True, align="right"),
        t("ВИСОТА\nСТЕЛІ, М", COL_L, 708, colw // 2, 34, WHITE, spacing=1.26, font=FONT_MED),
        t(u["height"], COL_L, 719, colw, 68, LIME, bold=True, align="right"),
    ]
    # Номер переїхав у заголовок панелі — у мета-рядках він дублювався б.
    # Для дуплекса це «РІВЕНЬ 1 / 2» (два аркуші одного об'єкта) і спільні секції.
    meta = ((("РІВЕНЬ", u["floor"]), ("СЕКЦІЇ", "1–2")) if u["duplex"]
            else (("ПОВЕРХ", u["floor"]), ("СЕКЦІЯ", u["section"])))
    for y, (lbl, val) in zip((864, 930), meta):
        items.append(t(lbl, COL_L, y, colw, 22, WHITE, font=FONT_MED))
        items.append(t(val, COL_L, y, colw, 22, WHITE, align="right"))
    return items + _footer(sheet_no, total)


# ── Збірка ─────────────────────────────────────────────────────────────────────
def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    units = load_units()

    # Єдиний масштаб для всіх лотів: найбільший футпринт має вписатися в рамку.
    foots = {u["key"]: footprint(u["pdf"]) for u in units}
    fw, fh = UNIT_FRAME[2], UNIT_FRAME[3]
    k_unit = min(min(fw / w, fh / h) for w, h in foots.values())
    print(f"  глобальний масштаб лотів k = {k_unit:.4f} "
          f"(найбільший футпринт {max(w for w,_ in foots.values())}×"
          f"{max(h for _,h in foots.values())} px)")

    f1 = [u for u in units if u["floor"] == "1" and not u["duplex"]]
    f2 = [u for u in units if u["floor"] == "2" and not u["duplex"]]
    dup = [u for u in units if u["duplex"]]

    def stats(floor_units, title, meta):
        areas = sorted(float(u["area"].replace(",", ".")) for u in floor_units)
        rng = f"{areas[0]:.1f}–{areas[-1]:.1f}".replace(".", ",")
        return dict(title=title, count=str(len(floor_units)), range=rng, meta=meta,
                    range_label="ПЛОЩІ, М²")

    # №06 (дуплекс) фізично займає обидва поверхи, тож у кількість він входить,
    # а в діапазон площ — ні: 412,4 м² розтягнув би діапазон і зробив його марним.
    s1 = stats(f1, "ПЕРШИЙ ПОВЕРХ",
               (("ВИСОТА СТЕЛІ, М", "3,6"), ("СЕКЦІЇ", "1–4"), ("НОМЕРИ", "№01–15")))
    s1["count"] = str(len(f1) + 1)
    # №06 входить у кількість (він фізично на цьому поверсі), але не в діапазон:
    # 412,4 м² розтягнув би його і зробив марним. Підпис це проговорює вголос.
    s1["range_label"] = "ПЛОЩІ БЕЗ\n№06, М²"
    s2 = stats(f2, "ДРУГИЙ ПОВЕРХ",
               (("ВИСОТА СТЕЛІ, М", "4,05"), ("СЕКЦІЇ", "1, 3, 4"), ("НОМЕРИ", "№16–27")))

    plan = [("title", None), ("div", ("ПЕРШИЙ", "ПОВЕРХ")),
            ("master", ("1-й пов", s1))]
    plan += [("unit", u) for u in f1]
    plan += [("div", ("ДУПЛЕКС", "412,4 М²"))]
    plan += [("unit", u) for u in dup]
    plan += [("div", ("ДРУГИЙ", "ПОВЕРХ")), ("master", ("2-й пов", s2))]
    plan += [("unit", u) for u in f2]
    plan += [("contact", None)]

    sheets = sum(1 for kind, _ in plan if kind in ("unit", "master"))
    prs = Presentation()
    prs.slide_width, prs.slide_height = bcs.px(W), bcs.px(H)
    prs._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
    ).set("type", "screen16x9")

    title_prelogo = None
    sheet_no = 0
    checks = []
    for i, (kind, payload) in enumerate(plan, 1):
        if kind == "title":
            bg, title_prelogo = bg_title()
            items = texts_title()
        elif kind == "div":
            bg, items = bg_divider(), texts_divider(*payload)
        elif kind == "contact":
            bg, items = bg_divider(tall=True), texts_contact()
        elif kind == "master":
            name, st = payload
            sheet_no += 1
            bg = bg_sheet(PDF_SRC / name / f"{name}.pdf", MASTER_FRAME, 1.0)
            items = texts_master(name, st, sheet_no, sheets)
        else:
            sheet_no += 1
            bg = bg_sheet(payload["pdf"], UNIT_FRAME, k_unit, rules=(356, 670, 908))
            items = texts_unit(payload, sheet_no, sheets)

        name = f"{i:02d}-{kind}"
        bg.save(OUT_DIR / f"{name}.png")
        flat = bg.copy()
        for it in items:
            n = bcs.emit_png(flat, it)
            if it.get("wrap"):
                step = round(it["size"] * it["spacing"])
                if it["y"] + (n - 1) * step + it["size"] > H - 8:
                    checks.append(f"{name}: дисклеймер у {n} рядків не вміщується")
        flat.save(OUT_DIR / f"{name}-flat.png")

        slide = bcs.add_slide(prs, OUT_DIR / f"{name}.png")
        for it in items:
            bcs.emit_pptx(slide, it)

    prs.save(PPTX_OUT)
    print(f"  ✓ {PPTX_OUT.relative_to(ROOT)} — {len(plan)} слайдів "
          f"({len(f1)} лотів 1-го пов., {len(dup)} рівні дуплекса, {len(f2)} лотів 2-го пов.)")
    gate(title_prelogo, checks)


def gate(title_prelogo, checks):
    first_unit = sorted(OUT_DIR.glob("*-unit.png"))[0]
    imgs = {
        "title": Image.open(OUT_DIR / "01-title.png"),
        "title_prelogo": title_prelogo,
        "div": Image.open(OUT_DIR / "02-div.png"),
        "unit": Image.open(first_unit),
    }
    tests = [
        ("титул · ейбрау", "title", (200, 645, 900, 680), LIME),
        ("титул · заголовок", "title", (200, 690, 1700, 800), WHITE),
        ("титул · підзаголовок", "title", (200, 815, 1600, 870), LIME),
        ("титул · контакти", "title", (200, 925, 1700, 970), (214, 217, 222)),
        ("титул · зона логотипа", "title_prelogo", (120, 80, 610, 225), WHITE),
        ("розділювач · заголовок", "div", (1224, 450, 1900, 600), WHITE),
        ("лот · заголовок панелі", "unit", (1362, 280, 1830, 320), WHITE),
        ("лот · лаймові значення", "unit", (1600, 570, 1830, 630), LIME),
        ("лот · дисклеймер", "unit", (39, 980, 1227, 1070), FOOT_TX),
    ]
    print("\n  Контроль контрасту (WCAG 2.1 AA, поріг 4,5:1):")
    failed = 0
    for label, key, box, fg in tests:
        got = bcs.worst_contrast(imgs[key], box, fg)
        failed += got < 4.5
        print(f"    {'✓' if got >= 4.5 else '✗'} {label:<26} {got:5.2f}:1")
    for c in checks:
        print(f"    ✗ {c}")
    if failed or checks:
        sys.exit(f"\n  ✗ {failed + len(checks)} перевірок не пройдено — каталог не видано.")
    print("  ✓ усі перевірки пройдено")


if __name__ == "__main__":
    build()
