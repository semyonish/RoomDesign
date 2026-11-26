"""«Раскладка обоев.pdf»: A4 landscape, every drawing vector (inline SVG), from renders/layout/wallpaper.json
(wallpaper_layout.py). First the rolls in big numbers — each room on its own, the hall and the kitchen-living room
together, what to buy; then how to read the sheets; for each room its unfolded walls and its plan (every piece with its
size and roll, the rolls it is cut from); then the cutting of all the rolls of each article. One numbering of rolls,
Р1…: the plan, the hall and the kitchen-living room from shared rolls, every other room from its own. pdfs.py prints it.
From wallpaper_seams.json (wallpaper_layout.py --seams) the same plan for the layout by walls; with compare=True,
how that layout changes the joints of the main one, room by room.
"""
import html

H = 270.0
INK, MUTED, LINE, SOFT = "#1F1D1A", "#77706A", "#E3DDD4", "#F5F2ED"
ROLL = "#2E5577"    # the roll chip
ACCENT = "#B0582B"  # the start marker, notes
ART = {"54355-3": dict(fill="#E9E3D7", swatch="#ECE9E1", edge="#B9AE9C", tile="#F4F0E9"),
       "54355-7": dict(fill="#CAD2C5", swatch="#BCC3B8", edge="#8E9A89", tile="#E6EBE3")}
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
h2 small {{ font-weight: 400; color: {MUTED}; font-size: 7pt; margin-left: 2mm; }}
h3 {{ font-size: 8pt; margin: 0 0 1.5mm; color: {MUTED}; font-weight: 600; text-transform: uppercase;
      letter-spacing: .08em; }}
.kpis {{ display: flex; gap: 2mm; }}
.kpi {{ background: {SOFT}; border-radius: 2mm; padding: 1.8mm 3mm; text-align: right; min-width: 22mm; }}
.kpi b {{ display: block; font-size: 13pt; line-height: 1.1; }}
.kpi span {{ font-size: 6.8pt; color: {MUTED}; }}
.kpi.dark {{ background: {ROLL}; color: #fff; }} .kpi.dark span {{ color: rgba(255,255,255,.82); }}
.foot {{ margin-top: auto; display: flex; justify-content: space-between; font-size: 6.8pt; color: {MUTED};
         padding-top: 2mm; border-top: 0.25mm solid {LINE}; }}
.body {{ flex: 1; min-height: 0; display: flex; flex-direction: column; }}
.drawing {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; }}
.cols {{ display: grid; grid-template-columns: 1.32fr 1fr; gap: 7mm; flex: 1; min-height: 0; }}
.cols2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8mm; flex: 1; min-height: 0; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ text-align: left; font-size: 6.8pt; color: {MUTED}; font-weight: 600; padding: 0 1.6mm 1.2mm;
      border-bottom: 0.35mm solid {INK}; }}
td {{ padding: 1.1mm 1.6mm; border-bottom: 0.2mm solid {LINE}; vertical-align: middle; }}
td.r, th.r {{ text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
td.n {{ font-weight: 700; font-size: 9.5pt; }} td.muted {{ color: {MUTED}; }}
td.nw {{ white-space: nowrap; }} td.sm {{ font-size: 7.4pt; }}
tr.total td {{ font-weight: 700; border-top: 0.35mm solid {INK}; border-bottom: none; }}
tr.plan td {{ background: #EEF3F8; font-weight: 700; }}
table.cut {{ font-size: 7.9pt; }} table.cut td {{ padding: 0.62mm 1.4mm; }} table.cut td.n {{ font-size: 8.8pt; }}
.chip {{ display: inline-block; min-width: 6.4mm; padding: 0.3mm 1.3mm; border-radius: 3mm; color: #fff;
         background: {ROLL}; font-weight: 600; font-size: 7pt; text-align: center; line-height: 1.25; }}
.sw {{ display: inline-block; width: 3mm; height: 3mm; border-radius: 0.6mm; vertical-align: -0.4mm; margin-right: 1.4mm; }}
.tiles {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 3mm; }}
.tile {{ border-radius: 3mm; padding: 4mm 4.5mm 3.5mm; display: flex; flex-direction: column; min-height: 47mm; }}
.tile .room {{ font-size: 11pt; font-weight: 700; }}
.tile .art {{ font-size: 7pt; color: {MUTED}; margin-top: 0.5mm; }}
.tile .num {{ font-size: 50pt; font-weight: 800; line-height: .95; letter-spacing: -.03em; margin-top: auto; }}
.tile .unit {{ font-size: 8.5pt; color: {MUTED}; }}
.joint {{ grid-column: 1 / span 2; background: {ROLL}; color: #fff; border-radius: 3mm; padding: 2.6mm 4.5mm;
          display: flex; align-items: center; gap: 4mm; }}
.joint b {{ font-size: 24pt; line-height: 1; }} .joint span {{ font-size: 8pt; line-height: 1.3; }}
.jnote {{ grid-column: 3 / span 3; align-self: center; font-size: 7.5pt; color: {MUTED}; padding-left: 1mm; }}
.buy {{ display: grid; grid-template-columns: 1fr 1fr 1.25fr; gap: 3mm; margin-top: 5mm; }}
.card {{ background: {SOFT}; border-radius: 3mm; padding: 3.5mm 4.5mm; }}
.card.dark {{ background: {INK}; color: #fff; }}
.card .k {{ font-size: 7.5pt; color: {MUTED}; }} .card.dark .k {{ color: rgba(255,255,255,.7); }}
.card .v {{ font-size: 26pt; font-weight: 800; line-height: 1.05; letter-spacing: -.02em; margin-top: 1mm; }}
.card .v small {{ font-size: 10pt; font-weight: 600; letter-spacing: 0; }}
.card .d {{ font-size: 7pt; color: {MUTED}; margin-top: 0.8mm; }} .card.dark .d {{ color: rgba(255,255,255,.7); }}
ul {{ margin: 0; padding-left: 4mm; }} li {{ margin: 0 0 1.6mm; }}
.note {{ font-size: 7pt; color: {MUTED}; margin-top: 1.5mm; }}
.flag {{ border-left: 0.8mm solid {ACCENT}; background: #FBF4EE; padding: 2mm 3mm; font-size: 7.5pt;
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


def spans(ns, pre="Р"):
    """[1, 2, 3, 5] → «Р1–Р3, Р5»."""
    out = []
    for k in sorted(ns):
        if out and k == out[-1][1] + 1:
            out[-1][1] = k
        else:
            out.append([k, k])
    return ", ".join(f"{pre}{a}" if a == b else f"{pre}{a}–{pre}{b}" for a, b in out)


def chip(n):
    return f'<span class="chip">Р{n}</span>'


def esc(t):
    return html.escape(str(t))


def swatch(art):
    return f'<span class="sw" style="background:{ART[art]["swatch"]};box-shadow:inset 0 0 0 0.2mm {ART[art]["edge"]}"></span>'


def zone_of(w, key):
    return next(z for z in w["zones"] if key in z["rooms"])


def lower_list(names):
    return ", ".join(n[0].lower() + n[1:] for n in names)


# ---------------- SVG ----------------
def tw(text, fs):
    """Approximate text width, mm."""
    return len(str(text)) * fs * 0.58


def svg_text(x, y, text, fs, fill=INK, weight=400, anchor="middle", extra=""):
    return (f'<text x="{x:.2f}" y="{y:.2f}" font-size="{fs:.2f}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" dominant-baseline="central" {extra}>{esc(text)}</text>')


def chip_w(text, fs=2.3):
    return tw(text, fs) + fs * 1.0


def svg_chip(cx, cy, text, color=ROLL, fs=2.3):
    w, h = chip_w(text, fs), fs * 1.5
    return (f'<rect x="{cx - w / 2:.2f}" y="{cy - h / 2:.2f}" width="{w:.2f}" height="{h:.2f}" rx="{h / 2:.2f}" '
            f'fill="{color}"/>' + svg_text(cx, cy, text, fs, "#fff", 600))


HATCH = ('<defs><pattern id="hatch" width="1.4" height="1.4" patternUnits="userSpaceOnUse" '
         'patternTransform="rotate(45)"><rect width="1.4" height="1.4" fill="#F3F1EE"/>'
         '<line x1="0" y1="0" x2="0" y2="1.4" stroke="#B8B1A7" stroke-width="0.25"/></pattern></defs>')


def strip_label(cx, cy, bw, bh, num, roll):
    """The strip number, its roll under it as a chip; the number alone, smaller, in a narrow box (mm)."""
    r = f"Р{roll}"
    if bw >= chip_w(r) + 1.2 and bh >= 9:
        return svg_text(cx, cy - 2.1, num, 4.1, INK, 700) + svg_chip(cx, cy + 2.4, r)
    fs = max(1.9, min(4.1, bw * 0.55, bh * 0.55))
    if bw < tw(num, fs) + 0.6 and bh > bw * 2:   # along a narrow upright strip
        fs = max(1.9, min(3.2, bh * 0.3, bw * 0.9))
        return svg_text(cx, cy, num, fs, INK, 700, extra=f'transform="rotate(-90 {cx:.2f} {cy:.2f})"')
    return svg_text(cx, cy, num, fs, INK, 700)


def elevation(r, w_mm, h_mm, row_max=1250, plan=None, labels=True, seams=None, start=True):
    """The unfolded walls of a room as seen from inside, in rows; each strip numbered with its roll. plan: other
    strips to draw (no rolls, labels=False); seams: the joints marked by how much of each is seen, and the cabinets
    that hide them outlined."""
    U, art = r["unfolded"], ART[r["article"]]
    walls, opens, pieces = U["walls"], U["opens"], plan or r["plan"]
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
        for cab in (U.get("cabinets", []) if seams is not None else []):   # cabinets to the ceiling, outlined
            lo, hi = max(cab["x"][0], r0), min(cab["x"][1], r1)
            if hi - lo > 0.1:
                out.append(f'<rect x="{X(lo):.2f}" y="{Y(H):.2f}" width="{(hi - lo) * s:.2f}" height="{H * s:.2f}" '
                           f'fill="none" stroke="{MUTED}" stroke-width="0.3" stroke-dasharray="1 0.8"/>')
                if tw("шкаф", 1.9) < (hi - lo) * s - 1:
                    out.append(svg_text(X((lo + hi) / 2), Y(H) + 2.2, "шкаф", 1.9, MUTED))
        for sm in (seams or []):   # the joints: solid — seen full height or near it, dashed — in part, dotted — hidden
            if r0 - 0.5 < sm["x"] < r1 + 0.5:
                x = X(sm["x"])
                style = (f'stroke="{ACCENT}" stroke-width="0.7"' if sm["seen"] >= 150 else
                         f'stroke="{ACCENT}" stroke-width="0.5" stroke-dasharray="1.6 0.9"' if sm["seen"] > 1 else
                         'stroke="#9C958C" stroke-width="0.35" stroke-dasharray="0.4 0.8"')
                out.append(f'<line x1="{x:.2f}" y1="{Y(H):.2f}" x2="{x:.2f}" y2="{Y(0):.2f}" {style}/>')
        for p in (pieces if labels else []):   # labels in the roomiest part of each piece clear of openings
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
                                       p["roll"]))
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
        if ri == 0 and start:   # where the strips start
            x, y = X(0), Y(H) - 1.6
            out.append(f'<path d="M {x:.2f} {y - 1.1:.2f} L {x + 2.2:.2f} {y:.2f} L {x:.2f} {y + 1.1:.2f} Z" '
                       f'fill="{ACCENT}"/>' + svg_text(x + 3.0, y, "старт, полосы слева направо", 2.1, ACCENT, 600,
                                                       "start"))
    width, height = span * s, top + len(rows) * row_h - gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="0 0 {width:.2f} {height:.2f}">{"".join(out)}</svg>')


def roll_bars(rolls, w_mm, L, W, fill, bh=5.4, gap=2.4, ghost=None):
    """Rolls as bars, pieces along each from its start: strip number and length; fill(piece) → color; ghost(piece)
    → True greys a piece out (another room's). Pieces too narrow to label are listed in a line under their roll."""
    lab, tail = 9.5, 13.0
    bw = w_mm - lab - tail
    k = bw / L
    out, y = [HATCH], 0.0
    for x in rolls:
        out.append(svg_chip(lab / 2 - 0.5, y + bh / 2, f"Р{x['roll']}", ROLL, 2.2))
        out.append(f'<rect x="{lab:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{bh:.2f}" fill="url(#hatch)"/>')
        unlabeled = []
        for q in x["pieces"]:
            px, py = lab + q["at"][0] * k, y + q["at"][1] / W * bh
            pw, ph = q["length"] * k, q["width"] / W * bh
            g = ghost and ghost(q)
            out.append(f'<rect x="{px:.2f}" y="{py:.2f}" width="{pw:.2f}" height="{ph:.2f}" '
                       f'fill="{"#E4E1DC" if g else fill(q)}" stroke="#fff" stroke-width="0.3"/>')
            t = f'{q["strip"]} · {n0(q["length"])}' + ("" if q["width"] >= W - 0.1 else f' × {n0(q["width"])}')
            for tt in (t, f'{q["strip"]} · {n0(q["length"])}', str(q["strip"])):
                if tw(tt, 2.15) < pw - 0.8 and ph > 2.4:
                    out.append(svg_text(px + pw / 2, py + ph / 2, tt, 2.15, MUTED if g else INK, 400 if g else 600))
                    break
            else:
                if not g:
                    unlabeled.append(t)
        out.append(f'<rect x="{lab:.2f}" y="{y:.2f}" width="{bw:.2f}" height="{bh:.2f}" fill="none" stroke="{INK}" '
                   f'stroke-width="0.3"/>')
        out.append(svg_text(lab + bw + 1.5, y + bh / 2, f"ост. {n0(x['rest'])}", 2.1, MUTED, anchor="start"))
        y += bh
        if unlabeled:   # too narrow to label on the bar
            out.append(svg_text(lab, y + 1.9, "ещё: " + ", ".join(unlabeled), 2.0, MUTED, anchor="start"))
            y += 3.0
        y += gap
    height = y - gap
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w_mm:.1f}mm" height="{height:.1f}mm" '
            f'viewBox="0 0 {w_mm:.2f} {height:.2f}">{"".join(out)}</svg>')


# ---------------- pages ----------------
def page(eyebrow, title, right, body):
    return (f'<div class="page"><div class="top"><div><div class="eyebrow">{eyebrow}</div><h1>{title}</h1></div>'
            f'{right}</div><div class="body">{body}</div><div class="foot">{{FOOT}}</div></div>')


def kpis(items):
    return '<div class="kpis">' + "".join(f'<div class="kpi {cls}"><b>{v}</b><span>{k}</span></div>'
                                          for v, k, cls in items) + "</div>"


def product_line(w):
    return (f'<div style="text-align:right;font-size:8pt;color:{MUTED}">{esc(w["product"])}<br>'
            f'рулон {c(w["width"] / 100)} × {c(w["length"] / 100)} м · однотонные · раппорт 0</div>')


def rolls_page(w):
    """The rolls in big numbers: each room on its own, the hall and the kitchen-living room together, what to buy."""
    joint = next(z for z in w["zones"] if len(z["rooms"]) > 1)
    R = {r["key"]: r for r in w["rooms"]}
    sep = sum(R[k]["own"] for k in joint["rooms"])
    tiles = "".join(
        f'<div class="tile" style="background:{ART[r["article"]]["tile"]}"><div class="room">{r["name"]}</div>'
        f'<div class="art">{swatch(r["article"])}обои {r["article"]} · {c(r["wall_area"], 1)} м²</div>'
        f'<div class="num">{r["own"]}</div><div class="unit">{rolls_w(r["own"])}, если клеить отдельно</div></div>'
        for r in w["rooms"])
    others = [r for r in w["rooms"] if r["key"] not in joint["rooms"]]
    joint_html = (f'<div class="joint"><b>{joint["rolls"]}</b><span><b style="font-size:9pt">'
                  f'{joint["names"][0]} и {lower_list(joint["names"][1:])} вместе</b><br>'
                  f'{rolls_w(joint["rolls"])} на обе комнаты вместо {sep}: подрезки одной идут в другую</span></div>'
                  + (f'<div class="jnote">Переносить подрезки между остальными комнатами смысла нет — '
                     f'{lower_list(r["name"] for r in others)}: по {others[0]["own"]} {rolls_w(others[0]["own"])} '
                     f'в любом случае.</div>' if w["shared"] >= w["rolls"] else
                     f'<div class="jnote">Если переносить подрезки и между остальными комнатами — {w["shared"]} '
                     f'{rolls_w(w["shared"])}, ещё на {w["rolls"] - w["shared"]} меньше, но тогда куски одной комнаты '
                     f'режутся из рулонов другой. План ниже посчитан без этого.</div>'))
    buy = "".join(
        f'<div class="card"><div class="k">{swatch(a["article"])}Купить {a["article"]}</div>'
        f'<div class="v">{a["rolls"]} <small>{rolls_w(a["rolls"])}</small></div>'
        f'<div class="d">{lower_list(a["names"])}</div></div>' for a in w["articles"])
    arts = w["articles"]
    compare = (
        '<table><tr><th>Как клеить</th>' + "".join(f'<th class="r">{a["article"]}</th>' for a in arts) +
        '<th class="r">Всего</th></tr>'
        '<tr><td>Каждая комната отдельно</td>' + "".join(f'<td class="r">{a["separate"]}</td>' for a in arts) +
        f'<td class="r">{w["separate"]}</td></tr>'
        f'<tr class="plan"><td>{joint["names"][0]} и {lower_list(joint["names"][1:])} вместе, остальные отдельно — '
        f'так посчитан план</td>' + "".join(f'<td class="r">{a["rolls"]}</td>' for a in arts) +
        f'<td class="r">{w["rolls"]}</td></tr>'
        '<tr><td>Подрезки переносятся между всеми комнатами</td>' + "".join(f'<td class="r">{a["shared"]}</td>' for a in arts) +
        f'<td class="r">{w["shared"]}</td></tr></table>')
    body = f"""
<div class="tiles">{tiles}{joint_html}</div>
<div class="buy">{buy}
  <div class="card dark"><div class="k">Всего купить</div><div class="v">{w["rolls"]} <small>{rolls_w(w["rolls"])}</small></div>
    <div class="d">если каждую комнату клеить отдельно — {w["separate"]}</div></div>
</div>
<div style="margin-top:5mm">{compare}</div>"""
    return page("Квартира · отделка стен", "Обои: сколько рулонов", product_line(w), body)


def info_page(w):
    """How to read the sheets, what is counted, each room in numbers."""
    z0, z1 = w["splash"]
    joint = next(z for z in w["zones"] if len(z["rooms"]) > 1)
    rows = ""
    for z in w["zones"]:
        rs = [r for r in w["rooms"] if r["key"] in z["rooms"]]
        for i, r in enumerate(rs):
            span = f' rowspan="{len(rs)}"' if len(rs) > 1 else ""
            rows += (f'<tr><td class="nw">{swatch(r["article"])}{r["name"]}</td><td class="muted">{r["article"]}</td>'
                     f'<td class="r">{c(r["wall_area"])}</td><td class="r">{r["strips"]}</td>'
                     f'<td class="r">{r["pieces"]}</td>' +
                     (f'<td{span} class="nw">{spans(range(z["first"], z["last"] + 1))}'
                      f'{"<br><span style=color:" + MUTED + ">общие</span>" if len(rs) > 1 else ""}</td>'
                      f'<td{span} class="r"><b>{z["rolls"]}</b></td>' if i == 0 else "") + '</tr>')
    rows += (f'<tr class="total"><td>Всего</td><td></td><td class="r">{c(sum(r["wall_area"] for r in w["rooms"]))}</td>'
             f'<td class="r">{sum(r["strips"] for r in w["rooms"])}</td><td class="r">{sum(r["pieces"] for r in w["rooms"])}</td>'
             f'<td>Р1–Р{w["rolls"]}</td><td class="r">{w["rolls"]}</td></tr>')
    sample = ('<svg style="flex:none" width="34mm" height="26mm" viewBox="5 9.5 20 15" xmlns="http://www.w3.org/2000/svg">'
              f'<rect x="1" y="1" width="28" height="32" fill="{ART["54355-3"]["fill"]}"/>' + strip_label(15, 16, 28, 32, 12, 4)
              + '</svg>')
    body = f"""
<div class="cols2">
  <div>
    <h2>Как читать листы</h2>
    <div style="display:flex;gap:4mm;align-items:center;margin-bottom:4mm">{sample}
      <div><b>12</b> — номер полосы. {"Полосы идут слева направо от метки «старт», на углу полоса режется вдоль, её остаток начинает следующую стену." if w["mode"] == "main" else "Каждая стена клеится слева направо от своего угла; первая полоса стены может быть уже рулона — её ширина в таблице."}<br><span class="chip">Р4</span> — рулон, из которого режется полоса.
        Номера стоит написать на рулонах.</div></div>
    <ul>
      <li>У каждой комнаты два листа: <b>развёртка стен</b> (вид изнутри) и <b>план</b> — каждый кусок, его ширина,
        сколько отрезать и из какого рулона, рядом — раскрой этих рулонов.</li>
      <li>{joint["names"][0]} и {lower_list(joint["names"][1:])} клеятся из общих рулонов
        {spans(range(joint["first"], joint["last"] + 1))}: на раскрое куски другой комнаты серые.</li>
      <li>В конце — раскрой всех рулонов по артикулам, цвет куска — комната.</li>
    </ul>
    <h2 style="margin-top:5mm">Что учтено</h2>
    <ul>
      <li><b>Полоса</b> = высота 270 + 10 на подрезку = 280 см. Из рулона {c(w["length"] / 100)} м — 3 полосы и остаток
        165: на куски над дверями (63), под окнами (88), под фартуком ({n0(z0 + 10)}) и над ним ({n0(H - z1 + 10)}).</li>
      <li><b>Обои клеим и за шкафами</b>, за кухней и холодильником. Без обоев только фартук кухни — {n0(z0)}–{n0(z1)} см
        от пола, там плитка. Двери (до 217) и окна вычтены, откосы не считаны.</li>
      <li>{"Прихожая и кухня-гостиная разделены на внешнем углу у арки. Узкая полоса в конце стены переносится в начало: в кухне-гостиной она в нише за шкафом." if w["mode"] == "main" else "Каждая стена — от своего угла, стыки сдвинуты под и над окна, над двери, к наличникам и за шкафы до потолка; полос уже 15 см нет. Короткие участки — ниши, короб стояка, простенок — огибает полоса соседней стены. Прихожая и кухня-гостиная разделены на внешнем углу у арки."}</li>
    </ul>
    <div class="flag">Размер рулона и раппорт 0 — по карточкам магазинов, сверьте с этикеткой. Все рулоны одного
      артикула — из одной партии, иначе на стыках бывает разница в оттенке.</div>
  </div>
  <div>
    <h2>Комнаты</h2>
    <table>
      <tr><th>Комната</th><th>Обои</th><th class="r">Стены, м²</th><th class="r">Полос</th><th class="r">Кусков</th>
        <th>Рулоны</th><th class="r">Рулонов</th></tr>
      {rows}
    </table>
  </div>
</div>"""
    return page("Квартира · отделка стен", "Как читать и что учтено", product_line(w), body)


def room_pages(i, n, r, w):
    """The room's unfolded walls; then its pieces and the rolls they are cut from."""
    names = {x["key"]: x["name"] for x in w["rooms"]}
    W, L = w["width"], w["length"]
    z = zone_of(w, r["key"])
    shared = len(z["rooms"]) > 1
    other = lower_list(names[k] for k in z["rooms"] if k != r["key"])
    head = kpis([(c(r["wall_area"]), "м² стен", ""), (r["strips"], "полос", ""),
                 (r["own"], f"{rolls_w(r['own'])}, если отдельно", ""),
                 (spans(range(z["first"], z["last"] + 1)),
                  f"{z['rolls']} {rolls_w(z['rolls'])}, общие: {other}" if shared else
                  f"{z['rolls']} {rolls_w(z['rolls'])} по плану", "dark")])
    eyebrow = f"Комната {i} из {n} · обои {r['article']}"
    p1 = page(eyebrow, f'{swatch(r["article"])}{r["name"]}', head,
              f'<div class="drawing">{elevation(r, 273, 166, start=w["mode"] == "main")}</div>')
    rows = "".join(
        f'<tr><td class="n r">{p["strip"]}</td><td class="sm">{esc(p["where"])}</td><td class="muted nw">{esc(p["kind"])}</td>'
        f'<td class="r">{"<b>" + n0(p["width"]) + "</b>" if p["width"] < W - 0.1 else n0(W)}</td>'
        f'<td class="r"><b>{n0(p["length"])}</b></td><td class="r">{chip(p["roll"])}</td></tr>' for p in r["plan"])
    fill = ART[r["article"]]["fill"]
    bars = roll_bars(z["list"], 112, L, W, lambda q: fill, ghost=lambda q: q["room"] != r["key"])
    body = f"""
<div class="cols">
  <div>
    <h2>Куски по порядку поклейки <small>ширина — по рулону {n0(W)} см, жирным — полоса, которую режут по ширине;
      «отрезать» — с запасом 10 см</small></h2>
    <table class="cut">
      <tr><th class="r">Полоса</th><th>Стена</th><th>Где на стене, см от пола</th><th class="r">Ширина</th>
        <th class="r">Отрезать</th><th class="r">Рулон</th></tr>
      {rows}
    </table>
  </div>
  <div>
    <h3>{"Общие рулоны (" + other + ")" if shared else "Рулоны комнаты"}: {z["rolls"]} {rolls_w(z["rolls"])}</h3>
    {bars}
    <div class="note">Что режется из каждого рулона, от его начала: номер полосы · длина куска, см.
      {"Серым — куски: " + other + "." if shared else ""}</div>
  </div>
</div>"""
    p2 = page(eyebrow + " · план", f'{swatch(r["article"])}{r["name"]} — куски и рулоны', head, body)
    return p1 + p2


def roll_pages(w):
    """The cutting of all the rolls of each article, by zone, the rooms in their colors."""
    W, L = w["width"], w["length"]
    names = {x["key"]: x["name"] for x in w["rooms"]}
    out = []

    def fill(q):
        return ROOM_FILL[q["room"]]

    def col(blocks):
        return "".join(h + roll_bars(lst, 128, L, W, fill, bh=6.0, gap=2.6) + '<div style="height:4mm"></div>'
                       for h, lst in blocks)
    for a in w["articles"]:
        zs = [z for z in w["zones"] if z["article"] == a["article"]]
        blocks = [(f'<h3>{" и ".join(z["names"])} · {spans(range(z["first"], z["last"] + 1))}</h3>', z["list"])
                  for z in zs]
        cols = [blocks[:1], blocks[1:]]
        if len(blocks) == 1 and len(blocks[0][1]) > 6:   # one long zone: in two columns
            h, lst = blocks[0]
            half = (len(lst) + 1) // 2
            cols = [[(h, lst[:half])], [("<h3>&nbsp;</h3>", lst[half:])]]
        legend = '<div class="legend">' + "".join(
            f'<span><span class="sw" style="background:{ROOM_FILL[k]}"></span>{names[k]}</span>' for k in a["rooms"]) + "</div>"
        out.append(page(f"Раскрой рулонов · обои {a['article']}", f'{swatch(a["article"])}{a["article"]} — раскрой рулонов',
                        kpis([(a["rolls"], rolls_w(a["rolls"]), "dark")]),
                        legend + f'<div class="cols2"><div>{col(cols[0])}</div><div>{col(cols[1])}</div></div>'))
    return "".join(out)


def seams_summary_page(w):
    """What the layout by walls changes: the joints seen, room by room, and how it is done."""
    R = w["rooms"]
    tot = {k: (sum(r["seams_main"][k] for r in R), sum(r["seams"][k] for r in R)) for k in ("count", "seen", "length")}
    strips = (sum(len({p["strip"] for p in r["main_plan"]}) for r in R), sum(r["strips"] for r in R))
    st = next(r for r in R if r["key"] == "study")

    def arrow(a, b, d=0):
        f = (lambda v: c(v, 1)) if d else str
        return f'{f(a)} <span style="color:{MUTED};font-weight:400">→</span> {f(b)}'
    rows = "".join(
        f'<tr><td class="nw">{swatch(r["article"])}{r["name"]}</td>'
        f'<td class="r">{arrow(r["seams_main"]["count"], r["seams"]["count"])}</td>'
        f'<td class="r"><b>{arrow(r["seams_main"]["seen"], r["seams"]["seen"])}</b></td>'
        f'<td class="r">{arrow(r["seams_main"]["length"], r["seams"]["length"], 1)}</td>'
        f'<td class="r">{arrow(len({p["strip"] for p in r["main_plan"]}), r["strips"])}</td></tr>' for r in R)
    rows += (f'<tr class="total"><td>Всего</td><td class="r">{arrow(*tot["count"])}</td><td class="r">{arrow(*tot["seen"])}</td>'
             f'<td class="r">{arrow(*tot["length"], 1)}</td><td class="r">{arrow(*strips)}</td></tr>')
    cards = (f'<div class="card"><div class="k">Видимых стыков</div><div class="v">{tot["seen"][0]} → {tot["seen"][1]}</div>'
             f'<div class="d">на {tot["seen"][0] - tot["seen"][1]} меньше</div></div>'
             f'<div class="card"><div class="k">Видимая длина стыков</div><div class="v">{c(tot["length"][0], 0)} → '
             f'{c(tot["length"][1], 0)} <small>м</small></div><div class="d">на '
             f'{round(100 * (1 - tot["length"][1] / tot["length"][0]))}% меньше</div></div>'
             f'<div class="card dark"><div class="k">Рулонов</div><div class="v">{w["rolls"]} <small>{rolls_w(w["rolls"])}</small></div>'
             f'<div class="d">столько же, сколько в основном документе</div></div>')
    body = f"""
<div class="buy" style="grid-template-columns:1fr 1fr 1fr;margin:0 0 6mm">{cards}</div>
<div class="cols2">
  <div>
    <h2>По комнатам <small>было (основной документ) → стало</small></h2>
    <table>
      <tr><th>Комната</th><th class="r">Стыков</th><th class="r">Видно</th><th class="r">Видимая длина, м</th>
        <th class="r">Полос</th></tr>
      {rows}
    </table>
    <div class="note">Стык — граница двух полос посреди стены, в углу — не стык. Видимый — тот, что виден хоть
      где-то по высоте: не за дверью или окном, не под наличником и не за шкафом до потолка.</div>
  </div>
  <div>
    <h2>Как сделано</h2>
    <ul>
      <li><b>Было:</b> полосы идут одной лентой от старта и огибают углы — где на стене окажется стык, решает случай;
        полоса, разрезанная на углу, добавляет стене лишний стык.</li>
      <li><b>Стало:</b> каждая стена клеится от своего угла — полос ровно столько, сколько нужно по её длине, и вся
        сетка сдвинута так, чтобы стыки ушли под и над окна, над двери, под наличник ({n0(w["casing"])} см у проёма)
        и за шкафы до потолка.</li>
      <li>Короткие участки — ниши, короб стояка, простенок — огибает полоса соседней стены. Полос уже 15 см нет.</li>
      <li><b>Цена:</b> больше полос режется по ширине ({strips[0]} → {strips[1]} полос) — больше работы ножом; рулонов
        столько же.</li>
      <li><b>Пример — кабинет</b> (следующий лист): стыков {st["seams_main"]["count"]} → {st["seams"]["count"]}, видно
        {st["seams_main"]["seen"]} → {st["seams"]["seen"]}. На стене к спальне 2 (475 см) четыре стыка неизбежны — она
        глухая; на стене с окном два стыка уходят под окно, на стене с дверью — к наличнику и за шкаф.</li>
    </ul>
  </div>
</div>"""
    return page("Раскладка обоев · вариант", "Меньше стыков: что изменилось", product_line(w), body)


def seams_room_page(r, w):
    """A room before and after: the joints marked by how much of each is seen."""
    a, b = r["seams_main"], r["seams"]
    head = kpis([(f'{a["count"]} → {b["count"]}', "стыков", ""), (f'{a["seen"]} → {b["seen"]}', "видно", "dark"),
                 (f'{c(a["length"], 1)} → {c(b["length"], 1)}', "м видимых стыков", "")])
    legend = (f'<div class="legend" style="margin:0 0 2mm"><span><svg width="8mm" height="3mm"><line x1="0" y1="1.5mm" '
              f'x2="8mm" y2="1.5mm" stroke="{ACCENT}" stroke-width="0.7mm"/></svg> стык виден почти во всю высоту</span>'
              f'<span><svg width="8mm" height="3mm"><line x1="0" y1="1.5mm" x2="8mm" y2="1.5mm" stroke="{ACCENT}" '
              f'stroke-width="0.5mm" stroke-dasharray="1.6mm 0.9mm"/></svg> виден частично: над дверью, под окном</span>'
              f'<span><svg width="8mm" height="3mm"><line x1="0" y1="1.5mm" x2="8mm" y2="1.5mm" stroke="#9C958C" '
              f'stroke-width="0.35mm" stroke-dasharray="0.4mm 0.8mm"/></svg> скрыт: за шкафом, под наличником</span>'
              f'<span style="color:{MUTED}">пунктир — шкафы до потолка</span></div>')
    one = 99999
    body = (legend + f'<h3>Было — основной документ: {a["count"]} стыков, видно {a["seen"]}</h3>'
            f'<div class="drawing" style="flex:none">{elevation(r, 273, 70, one, r["main_plan"], False, a["list"], False)}</div>'
            f'<h3 style="margin-top:4mm">Стало — каждая стена от своего угла: {b["count"]} стыков, видно {b["seen"]}</h3>'
            f'<div class="drawing" style="flex:none">{elevation(r, 273, 70, one, None, False, b["list"], False)}</div>')
    return page(f"Меньше стыков · обои {r['article']}", f'{swatch(r["article"])}{r["name"]}: было и стало', head, body)


def document(w, date, compare=False):
    """The whole PDF as one HTML page: the plan of the layout in w; compare (a seams layout): instead, how it
    changes the joints of the main layout — the summary, then each room before and after, the study first."""
    if compare:
        body = seams_summary_page(w) + "".join(
            seams_room_page(r, w) for r in sorted(w["rooms"], key=lambda r: r["key"] != "study"))
        title = "Стыки обоев — сравнение раскладок"
    else:
        body = rolls_page(w) + info_page(w)
        for i, r in enumerate(w["rooms"], 1):
            body += room_pages(i, len(w["rooms"]), r, w)
        body += roll_pages(w)
        title = "Раскладка обоев"
    n = body.count("{FOOT}")
    for i in range(1, n + 1):
        body = body.replace("{FOOT}", f'<span>{title} · {esc(w["product"])} · рулон {c(w["width"] / 100)} × '
                                      f'{c(w["length"] / 100)} м · {date}</span><span>{i} / {n}</span>', 1)
    return (f'<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>{title}</title>'
            f'<style>{CSS}</style></head><body>{body}</body></html>')
