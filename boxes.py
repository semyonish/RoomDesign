"""Profile frames (каркас) of the boxes around the wall-hung toilet installations, for the installer: front elevation
from the room, plan section at 60 above the floor, cut list and materials, cm.

The boxes themselves are in plan.json (installation_box of the bathroom and the toilet); how to build them lives apart,
in plan_carcass.json (the user keeps plan.json clean of it): Knauf ПН 28×27 tracks and ПП 60×27 studs, ГКЛВ 12.5 in
two layers screwed to the studs and to the face of the Grohe Rapid SL frame, tile on top. Local coordinates: s runs
along the wall as seen from the room (left to right), d is the depth from the rough back wall, z the height over the
finished floor.

    .venv/bin/python boxes.py      # renders/plan/frame_bathroom.png, frame_toilet.png
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT, BOLD = "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
INK, GREY, RED = (30, 30, 30), (120, 120, 120), (210, 40, 40)
COLORS = {"ПН": (40, 110, 210), "ПП": (30, 150, 85)}
NAMES = {"ПН": "ПН 28×27", "ПП": "ПП 60×27"}
WALL, FRAME, GKL, TILE = (95, 95, 95), (175, 175, 175), (236, 226, 205), (205, 215, 222)
SCALE = 5.0
PLAN = json.loads(Path("plan_carcass.json").read_text())
ROUGH = PLAN["rough_floor"]           # rough floor under the finished one
STOCK = PLAN["system"]["profile_length"]


def load(box):
    """plan_carcass.json box → the tuples draw() works with; pieces: id, profile, s0, s1, z0, z1, d0, d1, cut, where."""
    b = dict(box)
    b["walls"] = tuple(box["walls"])
    b["frame"] = tuple(box["frame"])
    b["tops"] = [(t["s"][0], t["s"][1], t["z"], t["top_tile"], t["label"]) for t in box["tops"]]
    b["holes"] = [(h["name"], h["s"], h["z"], h["r"]) for h in box["holes"]]
    if box.get("hatch"):
        b["hatch"] = (*box["hatch"]["s"], *box["hatch"]["z"])
    b["pieces"] = [(p["id"], p["profile"], *p["s"], *p["z"], *p["d"], p["cut"], p["where"]) for p in box["pieces"]]
    return b


BATH, TOILET = load(PLAN["boxes"]["bathroom"]), load(PLAN["boxes"]["toilet"])


def cut_plan(pieces):
    """First-fit decreasing over 3 m profiles: [[(id, len), ...], ...] per profile bar."""
    bars = []
    for pid, length in sorted(pieces, key=lambda p: -p[1]):
        for bar in bars:
            if sum(n for _, n in bar) + length <= STOCK:
                bar.append((pid, length))
                break
        else:
            bars.append([(pid, length)])
    return bars


def draw(box, out):
    L, F = box["length"], box["front"]
    f_b, f_m, f_s = (ImageFont.truetype(BOLD, 30), ImageFont.truetype(FONT, 20), ImageFont.truetype(FONT, 17))
    left, el_top = 150, 190                                   # elevation origin: s 0 at x left, z 125 at el_top
    plan_top = el_top + (125 - ROUGH) * SCALE + 150           # plan: rough back wall (d 0) here
    W = int(left + L * SCALE + (250 if box["right_end"] else 190) + 940)
    H = int(plan_top + (F + 10) * SCALE + 520)
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    def E(s, z):
        return left + s * SCALE, el_top + (125 - z) * SCALE

    def Pp(s, dd):
        return left + s * SCALE, plan_top + dd * SCALE

    def rect(p0, p1, **kw):
        d.rectangle([min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])], **kw)

    def dashed_rect(p0, p1, color, dash=8):
        x0, y0, x1, y1 = min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])
        for a, b, horiz in (((x0, y0), (x1, y0), True), ((x0, y1), (x1, y1), True), ((x0, y0), (x0, y1), False),
                            ((x1, y0), (x1, y1), False)):
            n = int((b[0] - a[0] if horiz else b[1] - a[1]) // dash)
            for i in range(0, n, 2):
                if horiz:
                    d.line([a[0] + i * dash, a[1], min(a[0] + (i + 1) * dash, b[0]), a[1]], fill=color, width=2)
                else:
                    d.line([a[0], a[1] + i * dash, a[0], min(a[1] + (i + 1) * dash, b[1])], fill=color, width=2)

    def tag(xy, text, color, anchor):  # text on a white plate, over the profiles
        x0, y0, x1, y1 = d.textbbox(xy, text, font=f_s, anchor=anchor)
        d.rectangle([x0 - 3, y0 - 2, x1 + 3, y1 + 2], fill="white")
        d.text(xy, text, fill=color, font=f_s, anchor=anchor)

    d.text((left, 30), box["title"], fill=INK, font=f_b)
    d.text((left, 72), box["sub"], fill=GREY, font=f_m)
    d.text((left, 100), "ПН 28×27 — синим, ПП 60×27 — зелёным, рама Grohe Rapid SL — серым; высоты от чистового пола, "
                        f"черновой пол принят на {-ROUGH} ниже", fill=GREY, font=f_m)

    # ---- elevation
    d.text((left, el_top - 46), "Вид спереди (ГКЛ и плитка сняты)", fill=INK, font=f_m)
    for i, has in enumerate(box["walls"]):
        if has:
            s = 0 if i == 0 else L
            rect(E(s, ROUGH - 3), E(s + (-6 if i == 0 else 6), 127), fill=WALL)
    rect(E(-6 if box["walls"][0] else 0, ROUGH), E(L + (6 if box["walls"][1] else 0), ROUGH - 3), fill=WALL)
    d.line([E(0, 0), E(L, 0)], fill=GREY, width=1)
    d.text(E(-8, 0), "чист. пол", fill=GREY, font=f_s, anchor="rm")
    if box["right_end"]:
        rect(E(L, ROUGH), E(L + 4, 60), fill=TILE, outline=GREY)
        d.text(E(L + 7, 50), box["right_end"], fill=GREY, font=f_s, anchor="lm")
    for s0, s1, t, tt, label in box["tops"]:   # the finished outline: GKL and tile around the frame
        rect(E(s0, ROUGH), E(s1, t + 2.5 + tt), outline=(200, 170, 120), width=2)
        d.text(((E(s0, 0)[0] + E(s1, 0)[0]) / 2, E(0, t + 4 + tt)[1]), label, fill=(170, 130, 70),
               font=f_s, anchor="mb")
    f0, f1 = box["frame"]
    rect(E(f0, ROUGH), E(f1, 113), fill=(238, 238, 238), outline=FRAME, width=2)
    for p in (f0, f1 - 4):
        rect(E(p, ROUGH), E(p + 4, 113), fill=FRAME)
    rect(E(f0, 100), E(f1, 104), fill=FRAME)
    ax = box["axis"]
    dashed_rect(E(ax - 9.85, 100 - 7.8), E(ax + 9.85, 100 + 7.8), RED)
    tag(E(ax, 100 - 10), "клавиша 19.7 × 15.6, центр 100", RED, "mt")
    d.text(E(ax, 55), "рама", fill=GREY, font=f_m, anchor="mm")
    d.text(E(ax, 49), "Rapid SL 50 × 113", fill=GREY, font=f_s, anchor="mm")
    d.text(E(ax, 30), "шпильки, отвод, подвод —", fill=GREY, font=f_s, anchor="mm")
    d.text(E(ax, 25), "вырезы по раме", fill=GREY, font=f_s, anchor="mm")
    uprights = [q for q in box["pieces"] if q[1] == "ПП" and q[5] - q[4] > q[3] - q[2]]
    for pid, kind, s0, s1, z0, z1, d0, d1, n, _ in box["pieces"]:
        if d1 <= F - 5 and kind == "ПН" and z1 - z0 > 6:   # vertical track on the back wall: behind, dashed
            dashed_rect(E(s0, z0), E(s1, z1), COLORS[kind])
        elif d1 - d0 > 10:                                 # ties to the wall: seen end-on, behind the studs
            continue
        elif d1 <= 4 and z1 - z0 <= 6:                    # top tracks on the back wall: hidden behind the front one
            continue
        else:
            rect(E(s0, z0), E(s1, z1), fill=COLORS[kind])
        cx, cz = (s0 + s1) / 2, (z0 + z1) / 2
        hole = next((h for h in box["holes"] if s0 <= h[1] <= s1 and abs(h[2] - cz) < 6), None)
        if hole:  # keep the number off the hole drawn on this piece
            cx = s0 + 3.5 if hole[1] > cx else s1 - 3.5
        elif s1 - s0 > 30:  # a long horizontal piece: label it in the widest gap between the uprights it carries
            cuts = sorted({s0, s1} | {c for q in uprights for c in (q[2], q[3]) if s0 < c < s1}
                          | {c for c in (f0, f1) if s0 < c < s1})
            a, b = max(zip(cuts, cuts[1:]), key=lambda g: g[1] - g[0])
            cx = (a + b) / 2
        x, y = E(cx, cz)
        if z1 - z0 > 30:
            y = E(0, min(z1 - 12, 70 + (int(pid) % 3) * 8))[1]
        d.ellipse([x - 12, y - 12, x + 12, y + 12], fill="white", outline=COLORS[kind], width=2)
        d.text((x, y), pid, fill=COLORS[kind], font=f_s, anchor="mm")
    for name, s, z, r in box["holes"]:
        x, y = E(s, z)
        d.ellipse([x - r * SCALE, y - r * SCALE, x + r * SCALE, y + r * SCALE], outline=RED, width=2)
        tag((x + r * SCALE + 6, y), name, RED, "lm") if s < L / 2 else tag((x - r * SCALE - 6, y), name, RED, "rm")
    if box.get("hatch"):
        s0, s1, z0, z1 = box["hatch"]
        dashed_rect(E(s0, z0), E(s1, z1), RED)
        d.text(E((s0 + s1) / 2, (z0 + z1) / 2), f"люк {s1 - s0:g} × {z1 - z0:g}", fill=RED, font=f_s, anchor="mm")
    for c in box.get("connections", []):   # where profiles meet the Grohe frame: numbered, explained in the notes
        s, z = c["at"][0] if c["type"] == "screw_down" else c["at"]
        x, y = E(s + (1.5 if c["type"] == "overlap" else 0), z + (7 if c["type"] == "overlap" else 0))
        d.rounded_rectangle([x - 20, y - 13, x + 20, y + 13], 6, fill=RED)
        d.text((x, y), c["id"], fill="white", font=f_s, anchor="mm")

    # chains: stud positions under the drawing, heights on the right
    marks = sorted({0, L, f0, f1} | {p[2] for p in uprights} | {p[3] for p in uprights})
    y = E(0, ROUGH - 3)[1] + 40
    d.line([E(marks[0], 0)[0], y, E(marks[-1], 0)[0], y], fill=INK, width=2)
    for m in marks:
        x = E(m, 0)[0]
        d.line([x - 6, y + 6, x + 6, y - 6], fill=INK, width=2)
    for a, b in zip(marks, marks[1:]):
        d.text(((E(a, 0)[0] + E(b, 0)[0]) / 2, y - 5), f"{b - a:g}", fill=INK, font=f_s, anchor="mb")
    zs = sorted({ROUGH, 0, 113} | {t[2] for t in box["tops"]} | {t[2] + 2.5 + t[3] for t in box["tops"]}
                | ({box["hatch"][2], box["hatch"][3]} if box.get("hatch") else set()) | {80, 100})
    x = E(L, 0)[0] + (60 if box["walls"][1] or box["right_end"] else 30) + (90 if box["right_end"] else 0)
    last = -1e9
    for z in reversed(zs):  # top down; close labels step aside so they don't overlap
        yy = E(0, z)[1]
        d.line([x - 8, yy, x + 8, yy], fill=INK, width=2)
        ty_ = max(yy, last + 19)
        d.text((x + 14, ty_), f"{z:g}", fill=INK, font=f_s, anchor="lm")
        last = ty_
    d.line([x, E(0, zs[0])[1], x, E(0, zs[-1])[1]], fill=INK, width=1)

    # ---- plan section at z 60
    d.text((left, plan_top - 70), "Разрез на высоте 60, вид сверху (стена — сверху, комната — снизу)", fill=INK, font=f_m)
    rect(Pp(-6 if box["walls"][0] else 0, -6), Pp(L + (6 if box["walls"][1] else 0), 0), fill=WALL)
    for i, has in enumerate(box["walls"]):
        if has:
            s = 0 if i == 0 else L
            rect(Pp(s, -6), Pp(s + (-6 if i == 0 else 6), F + 8), fill=WALL)
    for s0, s1, t, _, _ in box["tops"]:
        if t < 60:   # the low part is cut below the plane: show its outline only
            dashed_rect(Pp(s0, F), Pp(s1, F + 2.5 + box["tile"]), (200, 170, 120))
            continue
        rect(Pp(s0, F), Pp(s1, F + 2.5), fill=GKL, outline=(200, 170, 120))
        rect(Pp(s0, F + 2.5), Pp(s1, F + 2.5 + box["tile"]), fill=TILE, outline=GREY)
    rect(Pp(f0, 0), Pp(f1, F), fill=(238, 238, 238), outline=FRAME, width=2)
    for p in (f0, f1 - 4):
        rect(Pp(p, F - 4), Pp(p + 4, F), fill=FRAME)
    d.text(Pp((f0 + f1) / 2, F / 2), "рама и кронштейны", fill=GREY, font=f_s, anchor="mm")
    for pid, kind, s0, s1, z0, z1, d0, d1, n, _ in box["pieces"]:
        cut = z0 <= 60 <= z1
        if cut:
            rect(Pp(s0, d0), Pp(s1, d1), outline=COLORS[kind], width=3)
        elif d1 - d0 > 10 or (z1 < 60 and z1 - z0 <= 6):   # ties above and floor tracks under the cut
            dashed_rect(Pp(s0, d0), Pp(s1, d1), COLORS[kind], dash=6)
    d.text(Pp(L / 2, F + 2.5 + box["tile"] + 4), f"лицо каркаса {F:g} от стены · ГКЛВ 2 × 1.25 · плитка с клеем "
           f"{box['tile']:g} → лицо {F + 2.5 + box['tile']:g}", fill=INK, font=f_s, anchor="mt")

    # ---- cut list and materials, on the right
    tx, ty = left + L * SCALE + (250 if box["right_end"] else 190), el_top - 46
    d.text((tx, ty), "Нарезка профилей", fill=INK, font=f_m)
    ty += 34
    for pid, kind, *_, n, where in box["pieces"]:
        d.text((tx, ty), f"{pid}", fill=COLORS[kind], font=f_s)
        d.text((tx + 30, ty), f"{kind}  {n:g}", fill=INK, font=f_s)
        d.text((tx + 130, ty), where, fill=GREY, font=f_s)
        ty += 26
    ty += 14
    for kind in ("ПН", "ПП"):
        bars = cut_plan([(p[0], p[8]) for p in box["pieces"] if p[1] == kind])
        total = sum(p[8] for p in box["pieces"] if p[1] == kind)
        d.text((tx, ty), f"{NAMES[kind]}: {total:g} см — {len(bars)} шт. по 3 м", fill=COLORS[kind], font=f_m)
        ty += 28
        for bar in bars:
            d.text((tx + 20, ty), " + ".join(f"{n:g} ({pid})" for pid, n in bar) +
                   f"  = {sum(n for _, n in bar):g}", fill=INK, font=f_s)
            ty += 24
        ty += 8
    ty += 8
    d.text((tx, ty), "Примечания", fill=INK, font=f_m)
    ty += 30
    for note in box["notes"] + ["стойки — шаг не больше 40 (плитка 60 × 120); ГКЛ — на 1 выше чернового пола",
                                "все профили к стенам и полу — через уплотнительную ленту"] + \
            [f"{c['id']} — {c['to']}: {c['how']}" for c in box.get("connections", [])]:
        line = "—"
        for w in note.split():
            if d.textlength(line + " " + w, font=f_s) > 640:
                d.text((tx, ty), line, fill=INK, font=f_s)
                ty += 23
                line = "  "
            line += " " + w
        d.text((tx, ty), line, fill=INK, font=f_s)
        ty += 30
    out.mkdir(parents=True, exist_ok=True)
    img = img.crop((0, 0, W, max(int(plan_top + (F + 30) * SCALE) + 60, ty + 30)))
    img.save(out / f"{box['file']}.png")
    print(out / f"{box['file']}.png")


def shopping(boxes):
    """Both boxes together: profile bars cut from the same stock, total lengths."""
    for kind in ("ПН", "ПП"):
        pieces = [(f"{b['file'][6]}{p[0]}", p[8]) for b in boxes for p in b["pieces"] if p[1] == kind]
        bars = cut_plan(pieces)
        print(f"{NAMES[kind]}: {sum(n for _, n in pieces):g} см, {len(bars)} шт. по 3 м")
        for bar in bars:
            print("   ", " + ".join(f"{n:g} ({pid})" for pid, n in bar), f"= {sum(n for _, n in bar):g}")


if __name__ == "__main__":
    for b in (BATH, TOILET):
        draw(b, Path("renders/plan"))
    shopping((BATH, TOILET))
