#!/usr/bin/env python3
"""
Стисла комерційна презентація ЖК Lakeview — 14 слайдів для першого контакту.

Повний каталог (35 слайдів, кожне приміщення окремо) збирає
`build-commercial-catalog.py` — це довідник, який менеджер надсилає ПІСЛЯ розмови.
Ця презентація — навпаки, перший дотик: вона має довести лід до дзвінка, а не
показати всі 27 планів.

  01 титул                    05 дуплекс 412 м² (якір)     09–12 чотири типорозміри
  02 об'єкт у цифрах          06 master 1-го поверху       13 забудовник
  03 комерція в цифрах        07 master 2-го поверху       14 заклик
  04 хто ваш клієнт           08 зведена таблиця 27 лотів

Анатомія нових слайдів — та сама, що в каталозі: ліворуч зображення або таблиця,
праворуч темна панель Вигоди. Нічого нового в бренд не вводиться.

Запуск:
    ./.venv/bin/python tools/build-commercial-deck.py
"""

import importlib.util
import pathlib
import sys

from PIL import Image, ImageDraw
from pptx import Presentation

ROOT = pathlib.Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bcc", ROOT / "tools" / "build-commercial-catalog.py")
bcc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bcc)
bcs = bcc.bcs

W, H = bcc.W, bcc.H
NAVY, LIME, WHITE = bcc.NAVY, bcc.LIME, bcc.WHITE
FOOT_BG, FOOT_TX = bcc.FOOT_BG, bcc.FOOT_TX
FONT, FONT_MED = bcc.FONT, bcc.FONT_MED
PANEL_X, COL_L, COL_R = bcc.PANEL_X, bcc.COL_L, bcc.COL_R
LOGO_BOX, RULE_Y, FOOT_Y = bcc.LOGO_BOX, bcc.RULE_Y, bcc.FOOT_Y
COLW = COL_R - COL_L

OUT_DIR = ROOT / "tools" / "commercial" / "deck"
PPTX_OUT = ROOT / "tools" / "commercial" / "Lakeview-commercial-deck.pptx"
RENDERS = ROOT / "img" / "renders"

# ── Наративні слайди: рендер ліворуч, факти праворуч ───────────────────────────
# Кожен факт нижче простежується до файлу: CLAUDE.md (Key Business Facts) або
# _manifest.json. Тверджень про трафік, дохідність і кількість мешканців тут
# свідомо немає — вони не підтверджені жодним файлом проєкту.
NARRATIVE = [
    dict(key="02-object", render="aerial.jpg", crop=(0, 160, 2400, 1510),
         title="ЖК LAKEVIEW",
         big=[("СЕКЦІЙ", "4"), ("ПОВЕРХІВ", "до 16")],
         meta=[("АДРЕСА", "В. Великого, 2а"),
               ("ПАРКІНГ", "138 місць"),
               ("ЗДАЧА", "2027")]),
    dict(key="03-numbers", render="closeup.jpg", crop=(0, 180, 2400, 1530),
         title="КОМЕРЦІЯ В ЦИФРАХ",
         big=[("ПРИМІЩЕНЬ", "27"), ("ПЛОЩІ, М²", "42,4–412,4")],
         meta=[("ПОВЕРХИ", "1 і 2"),
               ("ВИСОТА СТЕЛІ, М", "3,6 і 4,05")]),
    dict(key="04-client", render="lake-bridge.jpg", crop=(0, 0, 2400, 1350),
         title="ПЕРШІ ДВА ПОВЕРХИ\nЖИТЛОВОГО БУДИНКУ",
         big=[],
         meta=[("ФОРМАТ", "вбудована комерція"),
               ("ЖИТЛОВІ ПОВЕРХИ", "3–16")]),
    dict(key="13-developer", render="semi-aerial.jpg", crop=(0, 100, 2400, 1450),
         title="ЗАБУДОВНИК",
         big=[],
         meta=[("БРЕНД", "Вигода"),
               ("ЮРОСОБА", "ПП «ДІК \"Вигода +\"»"),
               ("ЄДРПОУ", "44876801")]),
]

TYPICAL = [  # чотири типорозміри — приклади планувань, а не «найкращі лоти».
    # Межі суміжні, без дір: інакше 67,8 · 74,3 · 106,3 · 114,2 з таблиці на сл. 8
    # не потрапляють у жоден тип.
    ("01", "КОМПАКТ", "до 60 м²"),
    ("09", "СТАНДАРТ", "60–105 м²"),
    ("04", "ПРОСТІР", "понад 105 м²"),
    ("21", "ДРУГИЙ ПОВЕРХ", "стеля 4,05 м"),
]

CTA_TITLE = ("НАЗВІТЬ НОМЕР", "ПРИМІЩЕННЯ")
CTA_LINES = [
    ("Надішлемо план, актуальну ціну та умови оплати", 26, WHITE, False, 700),
    ("+38 096 990 03 90", 40, LIME, True, 772),
    ("vygoda.sales@gmail.com · lakeview.com.ua", 22, WHITE, False, 838),
    ("Відділ продажу: вул. В. Великого, 4, каб. 406, Львів", 22, WHITE, False, 880),
]


# ── Підкладки ──────────────────────────────────────────────────────────────────
def panel_base(canvas):
    d = ImageDraw.Draw(canvas)
    d.rectangle([PANEL_X, 0, W, H], fill=NAVY)
    lx, ly, lw, lh = LOGO_BOX
    logo = Image.open(bcc.REFS / "logo-light.png").convert("RGBA").resize((lw, lh), Image.LANCZOS)
    canvas.paste(logo, (lx, ly), logo)
    return canvas


def bg_narrative(spec):
    photo = Image.open(RENDERS / spec["render"]).convert("RGB").crop(spec["crop"])
    k = max(PANEL_X / photo.width, H / photo.height)
    photo = photo.resize((round(photo.width * k), round(photo.height * k)), Image.LANCZOS)
    left = photo.crop(((photo.width - PANEL_X) // 2, (photo.height - H) // 2,
                       (photo.width - PANEL_X) // 2 + PANEL_X, (photo.height - H) // 2 + H))
    canvas = Image.new("RGB", (W, H), WHITE)
    canvas.paste(left, (0, 0))
    canvas = panel_base(canvas)
    d = ImageDraw.Draw(canvas)
    # лінійка під заголовком: у двохрядкового заголовка вона на 356 перетинала б
    # другий рядок, тому опускаємо її під нього
    two_line = "\n" in spec["title"]
    rules = RULE_Y if spec["big"] else ((400,) if two_line else (356,))
    for y in rules:
        d.rectangle([COL_L, y, COL_R, y], fill=WHITE)
    return canvas


def bg_table():
    canvas = panel_base(Image.new("RGB", (W, H), WHITE))
    d = ImageDraw.Draw(canvas)
    for y in (356,):
        d.rectangle([COL_L, y, COL_R, y], fill=WHITE)
    # два стовпці по 14 рядків: лінійка під шапкою + розділювачі рядків
    for cx in (60, 700):
        d.rectangle([cx, 168, cx + 560, 169], fill=(167, 175, 188))
        for i in range(1, 14):
            y = 168 + i * 56
            d.rectangle([cx, y, cx + 560, y], fill=(232, 234, 238))
    return canvas


# ── Тексти ─────────────────────────────────────────────────────────────────────
def t(txt, x, y, w, size, color, **kw):
    return dict(t=txt, x=x, y=y, w=w, size=size, color=color, **kw)


def sheet_rules(title):
    """Лінійка під заголовком: у двохрядкового вона на 356 перетинала б другий рядок."""
    return ((400 if "\n" in title else 356), 670, 908, 974)


def texts_panel(title, big, meta, title_size=34):
    items = [t(title, COL_L, 290, COLW, title_size, WHITE, bold=True,
               tracking=0.68, spacing=1.26)]
    for i, (lbl, val) in enumerate(big):
        y_lbl, y_val = (565, 575) if i == 0 else (708, 719)
        if "\n" in lbl:                      # двохрядковий підпис піднімаємо на пів рядка
            y_lbl -= 8
        items.append(t(lbl, COL_L, y_lbl, COLW // 2, 34, WHITE, font=FONT_MED, spacing=1.26))
        items.append(t(val, COL_L, y_val + (7 if len(val) > 4 else 0), COLW,
                       bcc.fit_size(val, 68, COLW - (235 if "\n" in lbl else 220)), LIME, bold=True, align="right"))
    for y, (lbl, val) in zip((864, 930, 998), meta):
        items.append(t(lbl, COL_L, y, COLW, 22, WHITE, font=FONT_MED))
        items.append(t(val, COL_L, y, COLW, 22, WHITE, align="right"))
    return items


def texts_table(units):
    items = [t("УСІ ПРИМІЩЕННЯ", COL_L, 290, COLW, 34, WHITE, bold=True, tracking=0.68),
             t("ПРИМІЩЕНЬ", COL_L, 565, COLW // 2, 34, WHITE, font=FONT_MED),
             t("27", COL_L, 575, COLW, 68, LIME, bold=True, align="right"),
             t("Повний перелік станом на 08.2026.\nПлан будь-якого приміщення надішлемо\n"
               "на запит у відділі продажу.", COL_L, 730, COLW, 22, WHITE,
               font=FONT_MED, spacing=1.5)]
    head = [("№", 0), ("ПОВ.", 190), ("СЕКЦ.", 300), ("ПЛОЩА, М²", 400)]
    for cx in (60, 700):
        for lbl, dx in head:
            items.append(t(lbl, cx + dx, 150, 160, 18, (110, 118, 130), font=FONT_MED))
    for i, u in enumerate(units):
        cx = 60 if i < 14 else 700
        y = 168 + (i % 14) * 56 + 34
        items.append(t(f"{u['code']:02d}", cx, y, 160, 24, (42, 48, 56), bold=True))
        items.append(t(u["floor"], cx + 190, y, 160, 24, (74, 81, 92), font=FONT_MED))
        items.append(t(u["section"], cx + 300, y, 160, 24, (74, 81, 92), font=FONT_MED))
        items.append(t(u["area"], cx + 400, y, 160, 24, (42, 48, 56), bold=True))
    return items


def texts_cta():
    items = [t(CTA_TITLE[0], bcc.DIV_TEXT_X, bcc.DIV_L1, 660, 70, WHITE, bold=True),
             t(CTA_TITLE[1], bcc.DIV_TEXT_X, bcc.DIV_L2, 660, 70, WHITE, bold=True)]
    for txt, size, color, bold, y in CTA_LINES:
        items.append(t(txt, bcc.DIV_TEXT_X, y, 700, size, color,
                       bold=bold, font=FONT if bold else FONT_MED))
    return items


# ── Збірка ─────────────────────────────────────────────────────────────────────
def build():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    units = bcc.load_units()
    by_code = {}
    for u in units:
        by_code.setdefault(u["code"], u)
    table_units = sorted(by_code.values(), key=lambda u: u["code"])
    if len(table_units) != 27:
        sys.exit(f"Очікувалось 27 унікальних приміщень, у манифесті {len(table_units)}")

    f1 = [u for u in units if u["floor"] == "1" and not u["duplex"]]
    f2 = [u for u in units if u["floor"] == "2" and not u["duplex"]]
    dup = next(u for u in units if u["duplex"] and u["floor"] == "1")

    def stats(fu, title, meta, extra):
        s = dict(title=title, count=str(len(fu) + extra), meta=meta)
        areas = sorted(float(u["area"].replace(",", ".")) for u in fu)
        s["range"] = f"{areas[0]:.1f}–{areas[-1]:.1f}".replace(".", ",")
        return s

    s1 = stats(f1, "ПЕРШИЙ ПОВЕРХ", (("ВИСОТА СТЕЛІ, М", "3,6"), ("СЕКЦІЇ", "1–4"),
                                     ("НОМЕРИ", "№01–15")), 1)
    s1["range_label"] = "ПЛОЩІ БЕЗ\n№06, М²"
    s2 = stats(f2, "ДРУГИЙ ПОВЕРХ", (("ВИСОТА СТЕЛІ, М", "4,05"), ("СЕКЦІЇ", "1, 3, 4"),
                                     ("НОМЕРИ", "№16–27")), 0)

    slides = []
    bg_t, prelogo = bcc.bg_title()
    title_items = bcc.texts_title()
    for it in title_items:      # презентацію й довідник треба розрізняти в папці
        if it["t"].startswith("Каталог"):
            it["t"] = "27 приміщень на 1 і 2 поверхах · 08.2026"
    slides.append(("01-title", bg_t, title_items))
    for spec in NARRATIVE[:3]:
        slides.append((spec["key"], bg_narrative(spec),
                       texts_panel(spec["title"], spec["big"], spec["meta"])))
    sheets = 7          # 1 флагман + 2 master + 4 типорозміри
    title = "ДУПЛЕКС №06"
    slides.append(("05-flagship",
                   bcc.bg_sheet(dup["pdf"], bcc.UNIT_FRAME, 1.0, rules=sheet_rules(title)),
                   texts_panel(title,
                               [("ЗАГАЛЬНА\nПЛОЩА, М²", dup["area"])],
                               [("РІВНІ", "1–2"), ("ВИСОТА СТЕЛІ, М", "3,6 і 4,05"),
                                ("СЕКЦІЇ", "1–2")]) + bcc._footer(1, sheets)))
    for n, (key, name, st) in enumerate((("06-master1", "1-й пов", s1),
                                         ("07-master2", "2-й пов", s2)), 2):
        slides.append((key, bcc.bg_sheet(bcc.PDF_SRC / name / f"{name}.pdf",
                                         bcc.MASTER_FRAME, 1.0,
                                         rules=sheet_rules(st["title"])),
                       texts_panel(st["title"],
                                   [("ПРИМІЩЕНЬ", st["count"]),
                                    (st.get("range_label", "ПЛОЩІ, М²"), st["range"])],
                                   st["meta"]) + bcc._footer(n, sheets)))
    slides.append(("08-table", bg_table(), texts_table(table_units)))

    k_unit = min(min(bcc.UNIT_FRAME[2] / w, bcc.UNIT_FRAME[3] / h)
                 for w, h in (bcc.footprint(u["pdf"]) for u in units))
    for i, (code, label, sub) in enumerate(TYPICAL, 9):
        u = by_code[int(code)]
        title = f"{label}\n{sub}"
        slides.append((f"{i:02d}-typical",
                       bcc.bg_sheet(u["pdf"], bcc.UNIT_FRAME, k_unit,
                                    rules=sheet_rules(title)),
                       texts_panel(title,
                                   [("ЗАГАЛЬНА\nПЛОЩА, М²", u["area"])],
                                   [("ПРИМІЩЕННЯ №", f"{u['code']:02d}"),
                                    ("ПОВЕРХ", u["floor"]),
                                    ("ВИСОТА СТЕЛІ, М", u["height"])])
                       + bcc._footer(i - 5, sheets)))
    spec = NARRATIVE[3]
    slides.append((spec["key"], bg_narrative(spec),
                   texts_panel(spec["title"], spec["big"], spec["meta"])))
    slides.append(("14-cta", bcc.bg_divider(tall=True), texts_cta()))

    prs = Presentation()
    prs.slide_width, prs.slide_height = bcs.px(W), bcs.px(H)
    prs._element.find(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldSz"
    ).set("type", "screen16x9")

    for key, bg, items in slides:
        bg.save(OUT_DIR / f"{key}.png")
        flat = bg.copy()
        for it in items:
            bcs.emit_png(flat, it)
        flat.save(OUT_DIR / f"{key}-flat.png")
        slide = bcs.add_slide(prs, OUT_DIR / f"{key}.png")
        for it in items:
            bcs.emit_pptx(slide, it)
    prs.save(PPTX_OUT)
    print(f"  ✓ {PPTX_OUT.relative_to(ROOT)} — {len(slides)} слайдів")

    checks = [("титул · заголовок", "01-title", (200, 690, 1700, 800), WHITE),
              ("об'єкт · панель", "02-object", (1362, 280, 1830, 320), WHITE),
              ("об'єкт · значення", "02-object", (1600, 570, 1830, 630), LIME),
              ("клієнт · панель", "04-client", (1362, 280, 1830, 340), WHITE),
              ("таблиця · рядок", "08-table", (60, 190, 620, 220), (42, 48, 56)),
              ("заклик · телефон", "14-cta", (1224, 760, 1900, 810), LIME)]
    print("\n  Контроль контрасту (WCAG 2.1 AA, поріг 4,5:1):")
    failed = 0
    for label, key, box, fg in checks:
        got = bcs.worst_contrast(Image.open(OUT_DIR / f"{key}.png"), box, fg)
        failed += got < 4.5
        print(f"    {'✓' if got >= 4.5 else '✗'} {label:<22} {got:5.2f}:1")
    if failed:
        sys.exit(f"\n  ✗ {failed} зон не проходять поріг — презентацію не видано.")
    print("  ✓ усі перевірки пройдено")


if __name__ == "__main__":
    build()
