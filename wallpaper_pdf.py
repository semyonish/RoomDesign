"""«Раскладка обоев.pdf»: A4 landscape, every drawing vector (inline SVG), from renders/layout/wallpaper.json
(wallpaper_layout.py). A summary page; for each room its unfolded walls, then its plan — every piece with its size
and its roll in both variants, and the rolls it is cut from; then the cutting of all the rolls of each article.
Variant А: each room from its own rolls; Б: offcuts go on to the other rooms of the article. pdfs.py prints it.
"""
import html

H = 270.0
INK, MUTED, LINE, SOFT = "#1F1D1A", "#77706A", "#E3DDD4", "#F5F2ED"
ART = {"54355-3": dict(fill="#E9E3D7", swatch="#ECE9E1", edge="#B9AE9C"),
       "54355-7": dict(fill="#CAD2C5", swatch="#BCC3B8", edge="#8E9A89")}
VAR = {"a": ("А", "#2E5577"), "b": ("Б", "#B0582B")}
ROOM_FILL = {"hall": "#F2DCC4", "kitchen_living": "#D2E2F2", "bedroom_1": "#D6E9D1", "bedroom_2": "#EED5E7",
             "study": "#DCD6F1"}
FONT = '-apple-system, "SF Pro Text", "Helvetica Neue", Helvetica, Arial, sans-serif'

CSS = f"""
@page {{ size: 297mm 210mm; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; background: #fff; }}
body {{ font-family: {FONT}; color: {INK}; font-size: 8.5pt; line-height: 1.35;
       -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 297mm; height: 210mm; padding: 10mm 12mm 7mm; display: flex; flex-direction: column;
         break-after: page; overflow: hidden; }}
.page:last-child {{ break-after: auto; }}
.top {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 8mm;
        padding-bottom: 3mm; border-bottom: 0.45mm solid {INK}; margin-bottom: 5mm; }}
.eyebrow {{ font-size: 7pt; letter-spacing: .14em; text-transform: uppercase; color: {MUTED}; font-weight: 600; }}
h1 {{ font-size: 22pt; line-height: 1.05; margin: 1.2mm 0 0; letter-spacing: -.015em; }}
h2 {{ font-size: 10.5pt; margin: 0 0 2.5mm; }}
h3 {{ font-size: 8.5pt; margin: 0 0 1.5mm; color: {MUTED}; font-weight: 600; text-transform: uppercase;
      letter-spacing: .08em; }}
.kpis {{ display: flex; gap: 2mm; }}
.kpi {{ background: {SOFT}; border-radius: 2mm; padding: 1.8mm 3mm; text-align: right; min-width: 22mm; }}
.kpi b {{ display: block; font-size: 13pt; line-height: 1.1; }}
.kpi span {{ font-size: 6.8pt; color: {MUTED}; }}
.kpi.a {{ background: {VAR["a"][1]}; color: #fff; }} .kpi.b {{ background: {VAR["b"][1]}; color: #fff; }}
.kpi.a span, .kpi.b span {{ color: rgba(255,255,255,.82); }}
.foot {{ margin-top: auto; display: flex; justify-content: space-between; font-size: 6.8pt; color: {MUTED};
         padding-top: 2mm; border-top: 0.25mm solid {LINE}; }}
.body {{ flex: 1; min-height: 0; display: flex; flex-direction: column; }}
.drawing {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }}
.cols {{ display: grid; grid-template-columns: 1.32fr 1fr; gap: 7mm; flex: 1; min-height: 0; }}
.sum {{ display: grid; grid-template-columns: 1.45fr 1fr; gap: 8mm; flex: 1; min-height: 0; }}
.cols3 {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 4mm; margin-bottom: 6mm; }}
.cols2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; flex: 1; min-height: 0; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; font-size: 6.8pt; color: {MUTED}; font-weight: 600; padding: 0 1.6mm 1.2mm;
      border-bottom: 0.35mm solid {INK}; }}
td {{ padding: 0.95mm 1.6mm; border-bottom: 0.2mm solid {LINE}; vertical-align: middle; }}
table.cut {{ font-size: 7.9pt; }} table.cut td {{ padding: 0.62mm 1.4mm; }} table.cut td.n {{ font-size: 8.8pt; }}
table.cut .chip {{ font-size: 6.6pt; padding: 0.2mm 1.2mm; }}
h2 small {{ font-weight: 400; color: {MUTED}; font-size: 7pt; margin-left: 2mm; }}
td.nw {{ white-space: nowrap; }} td.sm {{ font-size: 7.4pt; }}
td.r, th.r {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
td.n {{ font-weight: 700; font-size: 9.5pt; }}
td.muted {{ color: {MUTED}; }}
tr.total td {{ font-weight: 700; border-top: 0.35mm solid {INK}; border-bottom: none; }}
.chip {{ display: inline-block; min-width: 6.4mm; padding: 0.35mm 1.3mm; border-radius: 3mm; color: #fff;
         font-weight: 600; font-size: 7pt; text-align: center; line-height: 1.25; }}
.chip.a {{ background: {VAR["a"][1]}; }} .chip.b {{ background: {VAR["b"][1]}; }}
.chip.ghost {{ background: none; color: {VAR["b"][1]}; box-shadow: inset 0 0 0 0.25mm {VAR["b"][1]}; }}
.sw {{ display: inline-block; width: 3mm; height: 3mm; border-radius: 0.6mm; vertical-align: -0.4mm; margin-right: 1.4mm; }}
.card {{ background: {SOFT}; border-radius: 2.5mm; padding: 4mm 4.5mm; }}
.card.dark {{ background: {INK}; color: #fff; }}
.card .k {{ font-size: 7.5pt; color: {MUTED}; }} .card.dark .k {{ color: rgba(255,255,255,.7); }}
.card .t {{ font-size: 12pt; font-weight: 700; margin: 0.6mm 0 3mm; display: flex; align-items: center; }}
.big {{ display: flex; gap: 6mm; align-items: flex-end; }}
.big div {{ display: flex; flex-direction: column; }}
.big b {{ font-size: 26pt; line-height: 1; letter-spacing: -.02em; }}
.big span {{ font-size: 7pt; color: {MUTED}; margin-top: 1mm; }}
.big span.chip {{ color: #fff; margin: 0 0 1.4mm; font-size: 7pt; }} .card.dark .big span {{ color: rgba(255,255,255,.7); }}
.big .chip {{ align-self: flex-start; }}
.big span.pair {{ margin: 0 0 1.4mm; }} .big span.pair .chip {{ margin: 0; }}
ul {{ margin: 0; padding-left: 4mm; }} li {{ margin: 0 0 1.4mm; }}
.note {{ font-size: 7pt; color: {MUTED}; margin-top: 1.5mm; }}
.flag {{ border-left: 0.8mm solid {VAR["b"][1]}; background: #FBF4EE; padding: 2mm 3mm; font-size: 7.5pt;
         border-radius: 0 1.5mm 1.5mm 0; margin-top: 3mm; }}
.legend {{ display: flex; gap: 4mm; flex-wrap: wrap; font-size: 7.5pt; margin-bottom: 3mm; }}
svg text {{ font-family: {FONT}; }}
"""


def c(v, d=2):
    return f"{v:.{d}f}".replace(".", ",")


def n0(v):  # 280.0 → «280», 59.7 → «59,7»
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def plural(n, one, few, many):
    if n % 10 == 1 and n % 100 != 11:
        return one
    return few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many


def rolls_w(n):
    return plural(n, "рулон", "рулона", "рулонов")


def spans(pre, ns):
    """[1, 2, 3, 5] → «Б1–Б3, Б5»."""
    out = []
    for k in sorted(ns):
        if out and k == out[-1][1] + 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return ", ".join(f"{pre}{a}" if a == b else f"{pre}{a}–{pre}{b}" for a, b in out)


def chip(v, n):
    return f'<span class="chip {v}">{VAR[v][0]}{n}</span>'


def esc(t):
    return html.escape(str(t))


# ---------------- SVG ----------------
def tw(text, fs):
    """Approximate text width, mm."""
    return len(str(text)) * fs * 0.58


def svg_text(x, y, text, fs, fill=INK, weight=400, anchor="middle", extra=""):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{fs:.2f}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" dominant-baseline="central" {extra}>{esc(text)}</text>')


def svg_chip(cx, cy, text, color, fs=2.1):
    w, h = tw(text, fs) + fs * 1.0, fs * 1.5
    return (f'<rect x="{cx - w / 2:.2f}" y="{cy - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{h / 2:.2f}" '
            f'fill="{color}"/>' + svg_text(cx, cy, text, fs, "#fff", 600))


def chip_w(text, fs=2.1):
    return tw(text, fs) + fs * 1.0


HATCH = (f'<defs><pattern id="hatch" width="1.4" height="1.4" patternUnits="userSpaceOnUse" '
         f'patternTransform="rotate(45)"><rect width="1.4" height="1.4" fill="#F3F1EE"/>'
         f'<line x1="0" y1="0" x2="0" y2="1.4" stroke="#B8B1A7" stroke-width="0.25"/></pattern></defs>')


def strip_label(cx, cy, bw, bh, num, a, b):
    """The strip number, its rolls under it as chips; smaller, or the number alone, in a narrow box (mm)."""
    na, nb = f"А{a}", f"Б{b}"
    wa, wb = chip_w(na), chip_w(nb)
    if bw >= wa + wb + 1.4 and bh >= 9.5:
        return (svg_text(cx, cy - 2.1, num, 4.1, INK, 700) +
                svg_chip(cx - (wb + 0.8) / 2, cy + 2.3, na, VAR["a"][1]) +
                svg_chip(cx + (wa + 0.8) / 2, cy + 2.3, nb, VAR["b"][1]))
    if bw >= max(wa, wb) + 1.5 and bh >= 15:
        return (svg_text(cx, cy - 4.2, num, 4.1, INK, 700) +
                svg_chip(cx, cy + 0.6, na, VAR["a"][1]) + svg_chip(cx, cy + 4.3, nb, VAR["b"][1]))
    fs = max(1.9, min(4.1, bw * 0.55, bh * 0.55))
    if bw < tw(num, fs) + 0.6 and bh > bw * 2:   # along a narrow upright strip
        fs = max(1.9, min(3.2, bh * 0.3, bw * 0.9))
        return svg_text(cx, cy, num, fs, INK, 700, extra=f'transform="rotate(-90 {cx:.2f} {cy:.2f})"')
    return svg_text(cx, cy, num, fs, INK, 700)


def elevation(r, w_mm, h_mm, row_max=1250):
    """The unfolded walls of a room as seen from inside, in rows; each strip numbered with its rolls (А, Б)."""
    U, art = r["unfolded"], ART[r["article"]]
    walls, opens, pieces = U["walls"], U["opens"], r["plan"]
    rows, cur = [], []
    for g in walls:
        if cur and g["x"][1] - cur[0]["x"][0] > row_max:
            rows.append(cur)
            cur = []
        cur.append(g)
    rows.append(cur)
    span = max(rw[-1]["x"][1] - rw[0]["x"][0] for rw in rows)
    top, dim, gap = 5.0, 13.0, 8.0
    s = min(w_mm / span, (h_mm - top - len(rows) * dim - (len(rows) - 1) * gap) / (len(rows) * H))
    row_h = H * s + dim + gap
    out = [HATCH]
    for ri, row in enumerate(rows):
        r0, r1 = row[0]["x"][0], row[-1]["x"][1]
        y0 = top + ri * row_h

        def X(x):
            return (x - r0) * s

        def Y(z):
            return y0 + (H - z) * s
        out.append(f'<rect x="0" y="{Y(H):.2f}" width="{X(r1):.2f}" height="{H * s:.2f}" fill="#fff"/>')
        for p in pieces:
            x0, x1 = max(p["x"][0], r0), min(p["x"][1], r1)
            if x1 - x0 > 0.1:
                out.append(f'<rect x="{X(x0):.2f}" y="{Y(p["z"][1]):.2f}" width="{(x1 - x0) * s:.2f}" '
                           f'height="{(p["z"][1] - p["z"][0]) * s:.2f}" fill="{art["fill"]}" stroke="#fff" '
                           f'stroke-width="0.45"/>')
        for o in opens:
            lo, hi = max(o["x"][0], r0), min(o["x"][1], r1)
            if hi - lo < 0.1:
                continue
            splash = o["label"] == "фартук"
            fill = "url(#hatch)" if splash else ("#F2F6F9" if "окно" in o["label"] else "#FFFFFF")
            out.append(f'<rect x="{X(lo):.2f}" y="{Y(o["z"][1]):.2f}" width="{(hi - lo) * s:.2f}" '
                       f'height="{(o["z"][1] - o["z"][0]) * s:.2f}" fill="{fill}" stroke="#8F887E" stroke-width="0.25"/>')
            label = "фартук — плитка" if splash else o["label"]
            for t in (label, label.replace("балконная", "балк."), "фартук" if splash else None):
                if t and tw(t, 2.0) < (hi - lo) * s - 1.5 and (o["z"][1] - o["z"][0]) * s > 3.5:
                    out.append(svg_text(X((lo + hi) / 2), Y((o["z"][0] + o["z"][1]) / 2), t, 2.0, MUTED))
                    break
        for g in row[1:]:   # corners
            out.append(f'<line x1="{X(g["x"][0]):.2f}" y1="{Y(H):.2f}" x2="{X(g["x"][0]):.2f}" y2="{Y(0):.2f}" '
                       f'stroke="{INK}" stroke-width="0.3"/>')
        out.append(f'<rect x="0" y="{Y(H):.2f}" width="{X(r1):.2f}" height="{H * s:.2f}" fill="none" '
                   f'stroke="{INK}" stroke-width="0.5"/>')
        for p in pieces:   # labels in the roomiest part of each piece clear of openings
            x0, x1 = max(p["x"][0], r0), min(p["x"][1], r1)
            if x1 - x0 < 0.5:
                continue
            cuts = sorted({x0, x1} | {e for o in opens for e in o["x"] if x0 < e < x1})
            best = None
            for u, v in zip(cuts, cuts[1:]):
                zs = [tuple(p["z"])]
                for o in opens:
                    if o["x"][0] <= (u + v) / 2 <= o["x"][1]:
                        zs = [q for z0, z1 in zs for q in ((z0, min(z1, o["z"][0])), (max(z0, o["z"][1]), z1))
                              if q[1] - q[0] > 0.5]
                for z0, z1 in zs:
                    if best is None or min((v - u) / 1.5, z1 - z0) > best[0]:
                        best = (min((v - u) / 1.5, z1 - z0), u, v, z0, z1)
            if best:
                _, u, v, z0, z1 = best
                out.append(strip_label(X((u + v) / 2), Y((z0 + z1) / 2), (v - u) * s, (z1 - z0) * s, p["strip"],
                                       p["a"], p["b"]))
        yd = Y(0) + 3.2   # dimensions and names under the walls
        groups = []
        for g in row:
            if groups and g["name"] and g["name"] == groups[-1][0]:
                groups[-1][2] = g["x"][1]
            else:
                groups.append([g["name"], g["x"][0], g["x"][1]])
            a, b = X(g["x"][0]), X(g["x"][1])
            out.append(f'<line x1="{a:.2f}" y1="{yd:.2f}" x2="{b:.2f}" y2="{yd:.2f}" stroke="{INK}" stroke-width="0.2"/>')
            for e in (a, b):
                out.append(f'<line x1="{e:.2f}" y1="{yd - 1:.2f}" x2="{e:.2f}" y2="{yd + 1:.2f}" stroke="{INK}" '
                           f'stroke-width="0.2"/>')
            if tw(n0(g["x"][1] - g["x"][0]), 2.2) < b - a - 0.6:
                out.append(svg_text((a + b) / 2, yd + 2.4, n0(g["x"][1] - g["x"][0]), 2.2))
        for name, a, b in groups:
            if name and tw(name, 2.1) < (b - a) * s:
                out.append(svg_text(X((a + b) / 2), yd + 6.0, name, 2.1, MUTED))
        if ri == 0:   # where the strips start
            x, y = X(0), Y(H) - 1.6
            out.append(f'<path d="M {x:.2f} {y - 1.1:.2f} L {x + 2.2:.2f} {y:.2f} L {x:.2f} {y + 1.1:.2f} Z" '
                       f'fill="{VAR["b"][1]}"/>' + svg_text(x + 3.0, y, "старт, полосы слева направо", 2.1,
                                                            VAR["b"][1], 600, "start"))
    width, height = span * s, top + len(rows) * row_h - gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="0 0 {width:.2f} {height:.2f}">{"".join(out)}</svg>')


def roll_bars(rolls, w_mm, L, W, fill, pre, color, bh=5.4, gap=2.4, ghost=None):
    """Rolls as bars, pieces along each from its start: strip number and length; fill(piece) → color; ghost(piece)
    → True greys a piece out (another room's)."""
    lab, tail = 9.5, 13.0
    bw = w_mm - lab - tail
    k = bw / L
    out = [HATCH]
    for i, x in enumerate(rolls):
        y = i * (bh + gap)
        out.append(svg_chip(lab / 2 - 0.5, y + bh / 2, f"{pre}{x['roll']}", color, 2.2))
        out.append(f'<rect x="{lab:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{bh:.2f}" fill="url(#hatch)"/>')
        for q in x["pieces"]:
            px, py = lab + q["at"][0] * k, y + q["at"][1] / W * bh
            pw, ph = q["length"] * k, q["width"] / W * bh
            g = ghost and ghost(q)
            out.append(f'<rect x="{px:.2f}" y="{py:.2f}" width="{pw:.2f}" height="{ph:.2f}" '
                       f'fill="{"#E4E1DC" if g else fill(q)}" stroke="#fff" stroke-width="0.3"/>')
            t = f'{q["strip"]} · {n0(q["length"])}' + ("" if q["width"] >= W - 0.1 else f' × {n0(q["width"])}')
            fs = 2.15
            for tt in (t, f'{q["strip"]} · {n0(q["length"])}', str(q["strip"])):
                if tw(tt, fs) < pw - 0.8 and ph > 2.4:
                    out.append(svg_text(px + pw / 2, py + ph / 2, tt, fs, MUTED if g else INK, 400 if g else 600))
                    break
        out.append(f'<rect x="{lab:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{bh:.2f}" fill="none" stroke="{INK}" '
                   f'stroke-width="0.3"/>')
        out.append(svg_text(lab + bw + 1.5, y + bh / 2, f"ост. {n0(x['rest'])}", 2.1, MUTED, anchor="start"))
    height = len(rolls) * (bh + gap) - gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="0 0 {w_mm:.2f} {height:.2f}">{"".join(out)}</svg>')


# ---------------- pages ----------------
def page(eyebrow, title, right, body, foot):
    return (f'<div class="page"><div class="top"><div><div class="eyebrow">{eyebrow}</div><h1>{title}</h1></div>'
            f'{right}</div><div class="body">{body}</div><div class="foot">{foot}</div></div>')


def kpis(items):
    return '<div class="kpis">' + "".join(f'<div class="kpi {cls}"><b>{v}</b><span>{k}</span></div>'
                                          for v, k, cls in items) + "</div>"


def swatch(art):
    return f'<span class="sw" style="background:{ART[art]["swatch"]};box-shadow:inset 0 0 0 0.2mm {ART[art]["edge"]}"></span>'


def summary_page(w, foot):
    A = {a["article"]: a for a in w["articles"]}
    a3, a7 = A["54355-3"], A["54355-7"]
    z0, z1 = w["splash"]

    def art_card(a, title, sub):
        same = a["rolls_a"] == a["rolls_b"]
        nums = (f'<div><span class="pair"><span class="chip a">А</span> <span class="chip b">Б</span></span><b>{a["rolls_a"]}</b>'
                f'<span>{rolls_w(a["rolls_a"])} в обоих вариантах</span></div>' if same else
                f'<div><span class="chip a">А</span><b>{a["rolls_a"]}</b><span>{rolls_w(a["rolls_a"])}, каждая '
                f'комната<br>из своих</span></div><div><span class="chip b">Б</span><b>{a["rolls_b"]}</b>'
                f'<span>{rolls_w(a["rolls_b"])} с переносом<br>подрезок</span></div>')
        return (f'<div class="card"><div class="k">{sub}</div><div class="t">{swatch(a["article"])}{title}</div>'
                f'<div class="big">{nums}</div><div class="note">стены под обои {c(a["wall_area"], 1)} м², '
                f'полос {a["strips"]}</div></div>')
    cards = (art_card(a3, "54355-3", "прихожая, кухня-гостиная, спальни 1 и 2") +
             art_card(a7, "54355-7", "кабинет") +
             f'<div class="card dark"><div class="k">Всего купить</div><div class="t">оба артикула</div>'
             f'<div class="big"><div><span class="chip a">А</span><b>{w["rolls_a"]}</b><span>без переноса</span></div>'
             f'<div><span class="chip b">Б</span><b>{w["rolls_b"]}</b><span>с переносом</span></div></div>'
             f'<div class="note" style="color:rgba(255,255,255,.7)">рулон {c(w["width"] / 100)} × {c(w["length"] / 100)} м</div></div>')
    rows = ""
    for a in w["articles"]:
        for r in [r for r in w["rooms"] if r["article"] == a["article"]]:
            took = [k for k in r["rolls_b"] if k not in r["opens_b"]]
            rows += (f'<tr><td class="nw">{swatch(r["article"])}{r["name"]}</td>'
                     f'<td class="r">{c(r["wall_area"])}</td><td class="r">{r["strips"]}</td>'
                     f'<td class="r"><b>{r["rolls_a"]}</b></td><td class="r"><b>{len(r["opens_b"])}</b></td>'
                     f'<td class="muted nw">{spans("А", range(r["first_a"], r["last_a"] + 1))}</td>'
                     f'<td class="muted sm">{spans("Б", r["opens_b"])}{" + подрезки " + spans("Б", took) if took else ""}</td></tr>')
        rows += (f'<tr class="total"><td class="nw">Итого {a["article"]}</td><td class="r">{c(a["wall_area"])}</td>'
                 f'<td class="r">{a["strips"]}</td><td class="r">{a["rolls_a"]}</td><td class="r">{a["rolls_b"]}</td>'
                 f'<td></td><td></td></tr>')
    sample = ('<svg style="flex:none" width="36mm" height="27mm" viewBox="5 9.5 20 15" xmlns="http://www.w3.org/2000/svg">'
              f'<rect x="1" y="1" width="28" height="32" fill="{ART["54355-3"]["fill"]}" stroke="#fff" stroke-width="0.45"/>'
              + strip_label(15, 16, 28, 32, 12, 4, 5) + '</svg>')
    body = f"""
<div class="cols3">{cards}</div>
<div class="sum">
  <div>
    <h2>По комнатам</h2>
    <table>
      <tr><th>Комната</th><th class="r">Стены, м²</th><th class="r">Полос</th>
        <th class="r"><span class="chip a">А</span></th><th class="r"><span class="chip b">Б</span></th>
        <th>Рулоны А</th><th>Рулоны Б</th></tr>
      {rows}
    </table>
    <div class="note"><b>А</b> — сколько рулонов уходит на комнату; <b>Б</b> — сколько рулонов комната вскрывает
      сама, «+ подрезки» — чьи остатки она дорезает.</div>
  </div>
  <div>
    <h2>Как читать</h2>
    <div style="display:flex;gap:4mm;align-items:center;margin-bottom:4mm">{sample}
      <div><b>12</b> — номер полосы: полосы идут слева направо от метки «старт».<br>
        <span class="chip a">А4</span> — рулон в варианте А: каждая комната из своих рулонов.<br>
        <span class="chip b">Б5</span> — рулон в варианте Б: подрезки переносятся в другие комнаты того же
        артикула, комнаты по порядку — прихожая, кухня-гостиная, спальня 1, спальня 2.</div></div>
    <ul>
      <li><b>Полоса</b> = высота 270 + 10 на подрезку = 280 см. Из рулона {c(w["length"] / 100)} м — 3 полосы и
        остаток 165: на куски над дверями (63), под окнами (88), под фартуком ({n0(z0 + 10)}) и над ним
        ({n0(H - z1 + 10)}).</li>
      <li><b>Обои клеим и за шкафами</b>, за кухней и холодильником. Без обоев только фартук кухни —
        {n0(z0)}–{n0(z1)} см от пола, там плитка. Двери (до 217) и окна вычтены, откосы не считаны.</li>
      <li>Прихожая и кухня-гостиная разделены на внешнем углу у арки.</li>
    </ul>
    <div class="flag">Размер рулона и раппорт 0 — по карточкам магазинов, сверьте с этикеткой. Все рулоны одного
      артикула — из одной партии, иначе на стыках бывает разница в оттенке.</div>
  </div>
</div>"""
    right = (f'<div style="text-align:right;font-size:8pt;color:{MUTED}">{esc(w["product"])}<br>'
             f'рулон {c(w["width"] / 100)} × {c(w["length"] / 100)} м · однотонные · раппорт 0</div>')
    return page("Квартира · отделка стен", "Обои — раскладка и расход", right, body, foot)


def room_pages(i, n, r, w, B, foot):
    names = {x["key"]: x["name"] for x in w["rooms"]}
    W, L = w["width"], w["length"]
    took = [k for k in r["rolls_b"] if k not in r["opens_b"]]
    head = kpis([(c(r["wall_area"]), "м² стен", ""), (r["strips"], "полос", ""),
                 (r["rolls_a"], f"{rolls_w(r['rolls_a'])} · вар. А", "a"),
                 (len(r["opens_b"]), f"{rolls_w(len(r['opens_b']))} · вар. Б", "b")])
    eyebrow = f"Комната {i} из {n} · обои {r['article']}"
    p1 = page(eyebrow, f'{swatch(r["article"])}{r["name"]}', head,
              f'<div class="drawing">{elevation(r, 273, 166)}</div>', foot)
    rows = ""
    for p in r["plan"]:
        wd = n0(p["width"]) if p["width"] < W - 0.1 else n0(W)
        narrow = p["width"] < W - 0.1
        rows += (f'<tr><td class="n r">{p["strip"]}</td><td class="sm">{esc(p["where"])}</td><td class="muted nw">{esc(p["kind"])}</td>'
                 f'<td class="r">{"<b>" + wd + "</b>" if narrow else wd}</td><td class="r"><b>{n0(p["length"])}</b></td>'
                 f'<td class="r">{chip("a", p["a"])}</td><td class="r">{chip("b", p["b"])}</td></tr>')
    art_fill = ART[r["article"]]["fill"]
    bars_a = roll_bars(r["list_a"], 110, L, W, lambda q: art_fill, "А", VAR["a"][1])
    bars_b = roll_bars([B[k] for k in r["rolls_b"]], 110, L, W, lambda q: art_fill, "Б", VAR["b"][1],
                       ghost=lambda q: q["room"] != r["key"])
    gave = sorted({names[q["room"]].lower() for k in r["opens_b"] for q in B[k]["pieces"] if q["room"] != r["key"]})
    from_ = sorted({names[B[k]["opened"]].lower() for k in took})
    note_b = "; ".join(x for x in (f"подрезки берёт у: {', '.join(from_)} ({spans('Б', took)})" if took else "",
                                   f"свои подрезки отдаёт: {', '.join(gave)}" if gave else "") if x)
    body = f"""
<div class="cols">
  <div>
    <h2>Куски по порядку поклейки <small>ширина — по рулону {n0(W)} см, жирным — полоса, которую режут по ширине;
      «отрезать» — с запасом 10 см</small></h2>
    <table class="cut">
      <tr><th class="r">Полоса</th><th>Стена</th><th>Где на стене, см от пола</th><th class="r">Ширина</th>
        <th class="r">Отрезать</th><th class="r">Рулон А</th><th class="r">Рулон Б</th></tr>
      {rows}
    </table>
  </div>
  <div>
    <h3><span class="chip a">А</span> свои рулоны: {r["rolls_a"]} {rolls_w(r["rolls_a"])}</h3>
    {bars_a}
    <div class="note" style="margin-bottom:4mm">Остатки остаются в комнате.</div>
    <h3><span class="chip b">Б</span> с переносом: вскрывает {len(r["opens_b"])} {rolls_w(len(r["opens_b"]))}</h3>
    {bars_b}
    <div class="note">Серым — куски других комнат из того же рулона. {note_b + "." if note_b else ""}</div>
  </div>
</div>"""
    p2 = page(eyebrow + " · план", f'{swatch(r["article"])}{r["name"]} — куски и рулоны', head, body, foot)
    return p1 + p2


def roll_pages(w, foot):
    """The cutting of all the rolls of each article: variant А by room, variant Б with the rooms in colors."""
    W, L = w["width"], w["length"]
    names = {x["key"]: x["name"] for x in w["rooms"]}
    out = []

    def two_cols(left, right):
        return f'<div class="cols2"><div>{left}</div><div>{right}</div></div>'

    def legend(keys):
        return '<div class="legend">' + "".join(
            f'<span><span class="sw" style="background:{ROOM_FILL[k]}"></span>{names[k]}</span>' for k in keys) + "</div>"
    for a in w["articles"]:
        rs = [r for r in w["rooms"] if r["article"] == a["article"]]
        keys = [r["key"] for r in rs]
        room_fill = lambda q: ROOM_FILL[q["room"]]
        if len(rs) == 1:   # one room: А and Б side by side
            r = rs[0]
            left = (f'<h3><span class="chip a">А</span> {r["rolls_a"]} {rolls_w(r["rolls_a"])}</h3>' +
                    roll_bars(r["list_a"], 128, L, W, room_fill, "А", VAR["a"][1], bh=7, gap=3))
            right = (f'<h3><span class="chip b">Б</span> {a["rolls_b"]} {rolls_w(a["rolls_b"])}</h3>' +
                     roll_bars(a["list_b"], 128, L, W, room_fill, "Б", VAR["b"][1], bh=7, gap=3))
            body = (f'<div class="note" style="margin:0 0 4mm">Одна комната — перенос подрезок счёт не меняет: '
                    f'раскрой в обоих вариантах один, различаются только номера.</div>' + two_cols(left, right))
            out.append(page(f"Раскрой рулонов · обои {a['article']}", f'{swatch(a["article"])}{a["article"]} — '
                            f'{r["name"].lower()}', kpis([(a["rolls_a"], "рулонов · А", "a"), (a["rolls_b"], "рулонов · Б", "b")]),
                            body, foot))
            continue
        # variant А: the rooms in two columns
        blocks = [(f'<h3>{r["name"]} · <span class="chip a">А</span> {spans("А", range(r["first_a"], r["last_a"] + 1))}</h3>',
                   r["list_a"]) for r in rs]
        half = (len(blocks) + 1) // 2
        col = lambda bs: "".join(h + roll_bars(lst, 128, L, W, room_fill, "А", VAR["a"][1], bh=5.2, gap=2.2)
                                 + '<div style="height:3.5mm"></div>' for h, lst in bs)
        out.append(page(f"Раскрой рулонов · обои {a['article']} · вариант А",
                        f'{swatch(a["article"])}{a["article"]} — каждая комната из своих рулонов',
                        kpis([(a["rolls_a"], "рулонов · А", "a")]),
                        legend(keys) + two_cols(col(blocks[:half]), col(blocks[half:])), foot))
        lst = a["list_b"]
        half = (len(lst) + 1) // 2
        bars = lambda part: roll_bars(part, 128, L, W, room_fill, "Б", VAR["b"][1], bh=6.2, gap=2.8)
        out.append(page(f"Раскрой рулонов · обои {a['article']} · вариант Б",
                        f'{swatch(a["article"])}{a["article"]} — с переносом подрезок',
                        kpis([(a["rolls_b"], "рулонов · Б", "b"),
                              (a["rolls_a"] - a["rolls_b"], f'{rolls_w(a["rolls_a"] - a["rolls_b"])} экономии', "")]),
                        legend(keys) + '<div class="note" style="margin:-1mm 0 3mm">Цвет куска — комната. Комнаты по '
                        'порядку: куски над дверями, под окнами и у фартука режутся из остатков уже вскрытых рулонов.</div>'
                        + two_cols(bars(lst[:half]), bars(lst[half:])), foot))
    return "".join(out)


def document(w, date):
    """The whole PDF as one HTML page."""
    B = {x["roll"]: x for a in w["articles"] for x in a["list_b"]}
    body = summary_page(w, "{FOOT}")
    for i, r in enumerate(w["rooms"], 1):
        body += room_pages(i, len(w["rooms"]), r, w, B, "{FOOT}")
    body += roll_pages(w, "{FOOT}")
    n = body.count("{FOOT}")
    for i in range(1, n + 1):
        body = body.replace("{FOOT}", f'<span>Раскладка обоев · {esc(w["product"])} · рулон {c(w["width"] / 100)} × '
                                      f'{c(w["length"] / 100)} м · {date}</span><span>{i} / {n}</span>', 1)
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Раскладка обоев</title>'
            f'<style>{CSS}</style></head><body>{body}</body></html>')
