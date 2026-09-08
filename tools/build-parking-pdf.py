#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Re-skin the 2020 ЖК "Pictorial" / Rubicon Group underground-parking plans
(вул. Володимира Великого, 2а) into the Вигода / ЖК Lakeview document style.

Source : 201207_VVEL_RPR_AR_Паркінг_REV2.pdf  (ARCHICAD, A3 landscape, 2 pages)
Style  : img/plans/commercial/_pdf-source/1-й пов/01.pdf  (the architect's own
         Вигода template — navy band + vector logo + lime title, A4 landscape)

Everything stays vector. The drawing (linework, 138 space numbers, dimensions)
is never touched; only brand chrome is removed and replaced.
"""
import sys, glob, pathlib, datetime, fitz

ROOT = pathlib.Path(__file__).resolve().parent.parent


def find_template():
    """Locate the architect's Вигода template.

    The path contains Cyrillic ("1-й пов"), which macOS stores in NFD while git
    and most tooling emit NFC — a hardcoded literal silently misses (the same
    normalisation trap documented in .deployignore). Glob on the ASCII part.
    """
    hits = sorted(glob.glob(str(ROOT / "img/plans/commercial/_pdf-source/*/01.pdf")))
    if not hits:
        raise SystemExit("Вигода template not found: img/plans/commercial/_pdf-source/*/01.pdf")
    return pathlib.Path(hits[0])


SRC = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    ROOT / "tools/parking/src-2020-VVEL-parking-REV02.pdf"
TPL = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else find_template()
OUT = pathlib.Path(sys.argv[3]) if len(sys.argv) > 3 else \
    ROOT / "tools/parking/Lakeview-parking-plan.pdf"

ARIAL      = "/System/Library/Fonts/Supplemental/Arial.ttf"
ARIAL_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

# ── page + scale ────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = 1190.55, 841.89          # A3 landscape
K = PAGE_W / 841.89                        # 1.414374 — A4→A3 (√2)

# ── brand palette (sampled from the architect's Вигода template) ────────────
NAVY  = (47 / 255, 54 / 255, 64 / 255)     # #2F3640  header band
LIME  = (193 / 255, 243 / 255, 61 / 255)   # #C1F33D  accent / title
DARK  = (42 / 255, 48 / 255, 56 / 255)     # #2A3038  primary text on light
MUTED = (74 / 255, 74 / 255, 74 / 255)     # #4A4A4A  disclaimer (AA at 6.4pt)
PANEL = (167 / 255, 175 / 255, 188 / 255)  # #A7AFBC  rules / secondary
FOOT  = (237 / 255, 239 / 255, 242 / 255)  # #EDEFF2  footer band

# ── header geometry, = template values × K ─────────────────────────────────
# The template band floats on a 10.33mm top margin. On this denser A3 sheet the
# plan's north arrow sits at y=89, so the band is set full-bleed at y=0 instead:
# that keeps every other brand proportion exact and clears the arrow by 3.4mm.
BAND_TOP = 0.0
BAND_H   = 56.16 * K                       # 79.44pt = 28.0mm

LOGO_CLIP = fitz.Rect(51.36, 38.40, 177.12, 74.88)   # logo bbox inside TPL
LOGO_X, LOGO_W, LOGO_H = 51.36 * K, 125.76 * K, 36.48 * K
LOGO_Y = BAND_TOP + (BAND_H - LOGO_H) / 2

TITLE_RIGHT = PAGE_W - 29.25 * K           # mirrors template's right margin
TITLE_SIZE  = 19.8 * K                     # 28.0pt — template title size
BL1 = BAND_TOP + 24.96 * K                 # baseline, line 1
BL2 = BAND_TOP + 46.68 * K                 # baseline, line 2

# ── footer geometry (reuses the sheet's own inset band) ────────────────────
F_L, F_R = 17.23, 1173.77
F_TOP, F_BOT = 759.79, 827.77

DISCLAIMER = (
    "Усі розміри — метричні, наведені в міліметрах. Розміри та площі машиномісць є проєктними; "
    "фактичні можуть незначно відрізнятися за результатами технічної інвентаризації. Креслення "
    "виконано не в масштабі та має ілюстративний характер. Це зображення не є публічною офертою "
    "і не є частиною договору. Забудовник залишає за собою право вносити зміни до проєктних "
    "рішень, нумерації та конфігурації машиномісць. Актуальну інформацію та наявність "
    "машиномісць уточнюйте у відділі продажу: +38 096 990 03 90.   "
    "© ПП «ДІК \"Вигода +\"», ЄДРПОУ 44876801."
)

PAGES = [
    dict(level="−2", spaces=74,  rng="1–74",   title2="Підземний паркінг"),
    dict(level="−1", spaces=64,  rng="75–138", title2="Підземний паркінг"),
]

REV  = "07.2026 · ред. 01"
ADDR = "ЖК Lakeview · вул. Володимира Великого, 2а, Львів"
CONT = "+38 096 990 03 90 · lakeview.com.ua"

fnt_r = fitz.Font(fontfile=ARIAL)
fnt_b = fitz.Font(fontfile=ARIAL_BOLD)


def w(font, text, size):
    return font.text_length(text, fontsize=size)


def plural_mm(n):
    """машиномісце / машиномісця / машиномісць — Ukrainian count agreement."""
    if n % 100 in (11, 12, 13, 14):
        return "машиномісць"
    if n % 10 == 1:
        return "машиномісце"
    if n % 10 in (2, 3, 4):
        return "машиномісця"
    return "машиномісць"


def extract_logo(tpl_path, bbox=fitz.Rect(50, 37, 179, 76)):
    """Pull the Вигода logo out of the architect's template as native vector
    polygons.

    We deliberately do NOT use show_pdf_page(): a clipped page import embeds the
    *entire* source page, so the commercial-premises data ("Комерційне
    приміщення", "Санвузол", "Загальна площа") and that sheet's own title ride
    along invisibly and stay extractable with pdftotext. The logo is 44 filled
    straight-line polygons with no text, images or curves, so re-emitting it is
    exact and leaks nothing.
    """
    src = fitz.open(tpl_path)
    page = src[0]
    shapes = []
    for d in page.get_drawings():
        r = d["rect"]
        if not bbox.intersects(r):
            continue
        a = r.get_area()
        # NB: Rect.intersect() mutates in place — use the non-mutating & operator
        if a > 0 and (bbox & r).get_area() / a < 0.9:
            continue
        subpaths, cur = [], []
        for it in d["items"]:
            if it[0] != "l":                       # guard: expect lines only
                raise SystemExit(f"unexpected logo primitive {it[0]!r}")
            p1, p2 = fitz.Point(it[1]), fitz.Point(it[2])
            if cur and abs(cur[-1] - p1) > 1e-6:
                subpaths.append(cur)
                cur = []
            if not cur:
                cur = [p1]
            cur.append(p2)
        if cur:
            subpaths.append(cur)
        if not subpaths:
            continue
        shapes.append(dict(
            fill=d.get("fill"),
            even_odd=bool(d.get("even_odd")),
            opacity=d.get("fill_opacity", 1) or 1,
            subpaths=subpaths,
        ))
    src.close()
    if not shapes:
        raise SystemExit("logo not found in template")
    # map from the geometry's own tight bbox, not the padded search box
    tight = fitz.Rect(shapes[0]["subpaths"][0][0], shapes[0]["subpaths"][0][0])
    for sh in shapes:
        for sp in sh["subpaths"]:
            for p in sp:
                tight |= p
    return shapes, tight


def build_logo_pdf(shapes, bbox):
    """Render the logo into a standalone 1-page PDF of raw path operators.

    Built with explicit content-stream ops rather than Shape.draw_polyline():
    finish(closePath=True) closes only the *last* subpath, which breaks every
    glyph counter ("о", "д", the ring) and fills the logo as one solid blob.
    Emitting `h` per subpath plus a single f/f* keeps even-odd holes correct.
    The result contains paths only — no text, no fonts, nothing to leak.
    """
    W, H = bbox.width, bbox.height
    ops = []
    for sh in shapes:
        r, g, b = sh["fill"]
        ops.append(f"{r:.6f} {g:.6f} {b:.6f} rg")
        for sp in sh["subpaths"]:
            for i, p in enumerate(sp):
                x = p.x - bbox.x0
                y = H - (p.y - bbox.y0)          # flip to PDF's bottom-left origin
                ops.append(f"{x:.4f} {y:.4f} {'m' if i == 0 else 'l'}")
            ops.append("h")
        ops.append("f*" if sh["even_odd"] else "f")

    doc = fitz.open()
    page = doc.new_page(width=W, height=H)
    page.draw_rect(fitz.Rect(0, 0, 1, 1), color=None, fill=None)  # force a stream
    xref = page.get_contents()[0]
    doc.update_stream(xref, ("q\n" + "\n".join(ops) + "\nQ\n").encode())
    return doc


def main():
    doc = fitz.open(SRC)
    logo_shapes, logo_bbox = extract_logo(TPL)
    logo_pdf = build_logo_pdf(logo_shapes, logo_bbox)
    print(f"logo: {len(logo_shapes)} vector shapes, bbox {logo_bbox}")
    assert len(logo_shapes) > 30, f"logo extraction looks wrong ({len(logo_shapes)} shapes)"
    assert doc.page_count == 2, f"expected 2 pages, got {doc.page_count}"

    for pno, meta in enumerate(PAGES):
        page = doc[pno]
        page.clean_contents()

        # ── capture baselines of the GothamPro labels we re-typeset ─────────
        keep = {}
        for b in page.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    t = s["text"].strip()
                    if s["font"].startswith("GothamPro") and t in (
                        "ПОВЕРХ", "-2", "-1", "C1", "C2", "C3", "C4"
                    ):
                        keep[t] = dict(origin=s["origin"], size=s["size"],
                                       bbox=s["bbox"])

        # ── PASS 1: remove brand artwork + chrome (text AND vector) ─────────
        for r in (
            fitz.Rect(0, 0, 900, 84),          # gold bar + GothamPro title
            fitz.Rect(940, 0, PAGE_W, 132),    # PICTORIAL mark + wordmark + tagline
            fitz.Rect(0, 750, PAGE_W, PAGE_H), # footer band + Rubicon logo + REV line
        ):
            page.add_redact_annot(r)
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_REMOVE,
            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_TOUCHED,
            text=fitz.PDF_REDACT_TEXT_REMOVE,
        )

        # ── PASS 2: remove only the GothamPro labels, keep the diagram ──────
        for t, d in keep.items():
            page.add_redact_annot(fitz.Rect(d["bbox"]))
        for b in page.get_text("dict")["blocks"]:           # ARCHICAD stamp
            for l in b.get("lines", []):
                for s in l["spans"]:
                    if "GSPublisherVersion" in s["text"]:
                        page.add_redact_annot(fitz.Rect(s["bbox"]))
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_NONE,
            graphics=fitz.PDF_REDACT_LINE_ART_NONE,
            text=fitz.PDF_REDACT_TEXT_REMOVE,
        )

        # ── header band ────────────────────────────────────────────────────
        page.draw_rect(fitz.Rect(0, BAND_TOP, PAGE_W, BAND_TOP + BAND_H),
                       color=None, fill=NAVY)
        page.draw_rect(fitz.Rect(0, BAND_TOP + BAND_H - 1.4, PAGE_W,
                                 BAND_TOP + BAND_H), color=None, fill=LIME)

        # vector Вигода logo, re-emitted from the architect's template
        page.show_pdf_page(
            fitz.Rect(LOGO_X, LOGO_Y, LOGO_X + LOGO_W, LOGO_Y + LOGO_H),
            logo_pdf, 0,
        )

        # lime title, right-aligned — template's specific-then-scope pattern
        t1 = f"Рівень {meta['level']}"
        t2 = meta["title2"]
        for text, bl in ((t1, BL1), (t2, BL2)):
            page.insert_text(
                (TITLE_RIGHT - w(fnt_r, text, TITLE_SIZE), bl), text,
                fontsize=TITLE_SIZE, fontname="ar", fontfile=ARIAL, color=LIME,
            )

        # ── re-typeset the level label in Arial (was GothamPro) ────────────
        if "ПОВЕРХ" in keep:
            d = keep["ПОВЕРХ"]
            page.insert_text(d["origin"], "ПОВЕРХ", fontsize=d["size"],
                             fontname="ar", fontfile=ARIAL, color=DARK)
        lvl_key = "-2" if pno == 0 else "-1"
        if lvl_key in keep:
            d = keep[lvl_key]
            txt = "−2" if pno == 0 else "−1"          # U+2212 typographic minus
            x1 = d["bbox"][2]
            page.insert_text((x1 - w(fnt_r, txt, d["size"]), d["origin"][1]),
                             txt, fontsize=d["size"], fontname="ar",
                             fontfile=ARIAL, color=DARK)

        # ── section labels: Latin C → Cyrillic С, in Arial Bold ────────────
        for i in range(1, 5):
            k = f"C{i}"
            if k in keep:
                d = keep[k]
                txt = f"С{i}"                          # U+0421 Cyrillic ES
                page.insert_text(d["origin"], txt, fontsize=d["size"],
                                 fontname="ab", fontfile=ARIAL_BOLD, color=DARK)

        # ── footer ─────────────────────────────────────────────────────────
        page.draw_rect(fitz.Rect(F_L, F_TOP, F_R, F_BOT), color=None, fill=FOOT)
        page.draw_line(fitz.Point(F_L, F_TOP), fitz.Point(F_R, F_TOP),
                       color=PANEL, width=0.5)

        page.insert_text((32.7, 782.0), REV, fontsize=9,
                         fontname="ab", fontfile=ARIAL_BOLD, color=DARK)
        page.insert_text((32.7, 795.0), ADDR, fontsize=7,
                         fontname="ar", fontfile=ARIAL, color=MUTED)
        n = meta["spaces"]
        page.insert_text((32.7, 806.5), f"{n} {plural_mm(n)} · №{meta['rng']}",
                         fontsize=7, fontname="ar", fontfile=ARIAL, color=MUTED)

        page.insert_textbox(
            fitz.Rect(218.4, 770.0, 824.4, 822.0), DISCLAIMER,
            fontsize=6.4, fontname="ar", fontfile=ARIAL, color=MUTED,
            align=fitz.TEXT_ALIGN_JUSTIFY, lineheight=1.32,
        )

        sheet = f"Аркуш {pno + 1} з 2"
        page.insert_text((1143.7 - w(fnt_b, sheet, 9), 782.0), sheet,
                         fontsize=9, fontname="ab", fontfile=ARIAL_BOLD, color=DARK)
        page.insert_text((1143.7 - w(fnt_r, CONT, 7.5), 795.0), CONT,
                         fontsize=7.5, fontname="ar", fontfile=ARIAL, color=DARK)

    # ── metadata: match the template's clean baseline ───────────────────────
    now = datetime.datetime.now().strftime("D:%Y%m%d%H%M%S")
    doc.set_metadata({
        "title":    "ЖК Lakeview — плани підземного паркінгу (рівні −2, −1)",
        "author":   "Вигода",
        "subject":  f"Підземний паркінг, 138 {plural_mm(138)}",
        "keywords": "",
        "creator":  "",
        "producer": "",
        "creationDate": now,
        "modDate": now,
    })
    doc.del_xml_metadata()
    try:
        doc.subset_fonts(verbose=False)      # Arial embeds full otherwise (~1.5 MB)
    except Exception as exc:
        print(f"note: font subsetting skipped ({exc})")
    doc.save(OUT, garbage=4, clean=True, deflate=True)
    print(f"written {OUT}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
