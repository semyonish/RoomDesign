"""Wall elevation (развёртка): one wall seen from the room, with its doors, mirror, hanging and standing furniture,
switches and outlets, a wardrobe standing against a side wall at its corner, and dimension chains, cm.

    .venv/bin/python elevation.py entrance "Прихожая, стена с зеркалом"   # renders/plan/elevation_entrance.png
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT, BOLD = "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
INK, RED, BLUE, GREY = (30, 30, 30), (210, 40, 40), (30, 90, 200), (110, 110, 110)
WALL_FILL = (247, 243, 236)
SCALE, MARGIN, TOP = 4.0, 150, 150  # px per cm; room for the chains around the wall
CASING_W = 7                        # drawn from the opening edge, as the plan notes count it (opening 217 + 7 = 224)
FRAME, FACE = 8.3, 5.6              # roomgen.electrical: AtlasDesign frame and key/socket face; posts 7.1 apart
# roomgen.door, entrance hardware on the lock vertical 6.5 from the leaf edge: height over the leaf bottom, radius
LOCK_IN, LEVER = 6.5, 13.5
HARDWARE = [(100, 2.6), (91.5, 2.2), (114, 1.7), (130, 2.1), (150, 1.3)]  # handle, thumbturn, latch, keyhole, peephole


def hexrgb(h, palette):
    h = palette.get(h[1:], h) if h.startswith("@") else h
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wall", help="wall id of rooms/apartment.json, e.g. entrance")
    ap.add_argument("title", help="what the sheet is called, e.g. «Прихожая, стена с зеркалом»")
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--out", default="renders/plan")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    pal = cfg["palette"]
    walls = {w["id"]: w for ol in [cfg["outline"], *[r["outline"] for r in cfg.get("extra_rooms", [])]] for w in ol}
    w = walls[args.wall]
    k = 0 if w["from"][1] == w["to"][1] else 1  # the plan axis the wall runs along
    a, b = w["from"][k], w["to"][k]
    sign = 1 if b > a else -1
    lo, length, height = min(a, b), abs(b - a), cfg["room"]["height"]

    # The outline keeps the room on its left, so seen from the room the wall's own direction runs right to left:
    # a plan coordinate c sits u = (to - c) along the drawing from its left end.
    def u(c):
        return (b - c) * sign

    W, H = int(length * SCALE) + 2 * MARGIN + 60, int(height * SCALE) + TOP + 330
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f_b, f_m, f_s = (ImageFont.truetype(BOLD, 30), ImageFont.truetype(FONT, 21), ImageFont.truetype(FONT, 18))

    def P(uu, z):
        return MARGIN + uu * SCALE, TOP + (height - z) * SCALE

    def box(c0, c1, z0, z1, fill, outline=INK, width=2):
        (x0, y0), (x1, y1) = P(min(u(c0), u(c1)), z1), P(max(u(c0), u(c1)), z0)
        d.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)
        return x0, y0, x1, y1

    def label(c, z, text, fill=INK, font=None, anchor="mm"):
        d.text(P(u(c), z), text, fill=fill, font=font or f_s, anchor=anchor)

    d.text((MARGIN, 34), f"Развёртка стены — {args.title}", fill=INK, font=f_b)
    d.text((MARGIN, 76), "вид из комнаты; размеры в см, высоты от чистового пола", fill=GREY, font=f_m)
    box(lo, lo + length, 0, height, WALL_FILL, width=3)
    # a corner where the outline turns right (the room keeps to its left) sticks out into the room
    for p, q in ((next((v for v in walls.values() if v["to"] == w["from"]), None), w),
                 (w, next((v for v in walls.values() if v["from"] == w["to"]), None))):
        if not p or not q:
            continue
        (px, py), (qx, qy) = [(s["to"][0] - s["from"][0], s["to"][1] - s["from"][1]) for s in (p, q)]
        if px * qy - py * qx < 0:
            c = q["from"][k]
            right = u(c) > length / 2
            d.text((P(u(c), 0)[0] + (-8 if right else 8), P(0, height - 12)[1]), "внешний угол", fill=GREY, font=f_s,
                   anchor="rm" if right else "lm")

    # a wardrobe on a side wall that starts at one of this wall's corners shows its end, floor to ceiling
    bands = []
    for it in cfg["furniture"]:
        sw = walls.get(it["wall"])
        if it["type"] != "wardrobe" or it["wall"] == args.wall or not sw or sw["from"][k] != sw["to"][k]:
            continue
        corner = sw["from"][k]
        if corner not in (a, b) or w["from"][1 - k] not in it["span"]:
            continue
        inward = 1 if corner == lo else -1
        c0, c1 = sorted((corner, corner + inward * it["depth"]))
        top = height if it.get("height") == "ceiling" else it["height"]
        box(c0, c1, 0, top, hexrgb(it.get("color", "#8B6A55"), pal))
        label((c0 + c1) / 2, top / 2 + 5, "шкаф-купе", fill="white", font=f_m)
        label((c0 + c1) / 2, top / 2 - 3, f"торец, глубина {it['depth']:g}", fill="white")
        bands.append((c0, c1))

    doors = [dr for dr in cfg["doors"] if dr["wall"] == args.wall]
    for dr in doors:
        s0, s1 = sorted(dr["span"])
        bands.append((s0 - CASING_W, s1 + CASING_W))
    bb = cfg["baseboard"]["height"]
    start = lo
    for c0, c1 in sorted(bands) + [(lo + length, lo + length)]:
        if c0 > start:
            box(start, c0, 0, bb, hexrgb("@joinery", pal), width=1)
        start = max(start, c1)

    for dr in doors:
        s0, s1 = sorted(dr["span"])
        oh = dr.get("opening_height", 217)
        joinery = hexrgb(dr.get("color", "#F4F4F1"), pal)
        box(s0 - CASING_W, s1 + CASING_W, 0, oh + CASING_W, joinery)
        box(s0, s1, 0, oh, hexrgb(dr["frame_color"], pal) if dr.get("frame_color") else joinery)
        lw = dr.get("leaf_width") or (s1 - s0 - 12)
        l0, lh = (s0 + s1) / 2 - lw / 2, dr.get("leaf_height", oh - 7)
        box(l0, l0 + lw, 1, 1 + lh, joinery)
        st = dr.get("stile", 0.15) * lw
        for p0, p1 in dr.get("panels") or []:
            box(l0 + st, l0 + lw - st, 1 + p0 * lh, 1 + p1 * lh, joinery, outline=(150, 150, 150), width=1)
        # the lock sits 6.5 from the leaf edge on the handle side of the wall's own direction; the lever points
        # toward the hinges
        low_s = dr.get("handle_side", "left") == "left"
        lock = (l0 + LOCK_IN, 1) if low_s == (sign > 0) else (l0 + lw - LOCK_IN, -1)
        cl, to_hinge = lock[0], lock[1] * sign
        for i, (z, r) in enumerate(HARDWARE if dr.get("kind") == "entrance" else HARDWARE[:1]):
            x, y = P(u(cl), 1 + z)
            r *= SCALE
            d.ellipse([x - r, y - r, x + r, y + r], fill=(60, 60, 60))
            if i == 0:
                x1 = P(u(cl + to_hinge * LEVER), 0)[0]
                d.rounded_rectangle([min(x, x1), y - 7, max(x, x1), y + 7], 6, fill=(60, 60, 60))
        label((s0 + s1) / 2, oh + CASING_W + 8, f"проём {s1 - s0:g} × {oh:g}, наличник {CASING_W:g}")
        label((s0 + s1) / 2, 1 + lh * 0.62, "входная дверь" if dr.get("kind") == "entrance" else "дверь",
              fill=GREY, font=f_m)
        label((s0 + s1) / 2, 1 + lh * 0.62 - 7, f"полотно {lw:g} × {lh:g}", fill=GREY)
        label(cl, 1 + HARDWARE[0][0] + 6, f"ручка {1 + HARDWARE[0][0]:g}", fill=GREY)

    furniture = [it for it in cfg["furniture"] if it["wall"] == args.wall]
    for it in furniture:
        c0, c1 = sorted(it["span"])
        t, z0 = it["type"], it.get("elevation", 0)
        if t == "mirror":
            x0, y0, x1, y1 = box(c0, c1, z0, z0 + it["height"], (214, 226, 232))
            for i in range(3):  # a glint
                d.line([x0 + (x1 - x0) * (0.12 + 0.12 * i), y1 - (y1 - y0) * 0.08,
                        x0 + (x1 - x0) * (0.5 + 0.12 * i), y0 + (y1 - y0) * 0.08], fill=(240, 247, 250), width=3)
            label((c0 + c1) / 2, z0 + it["height"] / 2 + 4, "зеркало", font=f_m)
            label((c0 + c1) / 2, z0 + it["height"] / 2 - 3, f"{c1 - c0:g} × {it['height']:g}")
            label((c0 + c1) / 2, z0 + it["height"] / 2 - 9, "без рамы")
        elif t == "cabinet":
            box(c0, c1, z0, z0 + it["height"], hexrgb(it.get("color", "#8B6A55"), pal))
            label((c0 + c1) / 2, z0 + it["height"] / 2 + 3, "консоль", fill="white")
            label((c0 + c1) / 2, z0 + it["height"] / 2 - 3, f"{c1 - c0:g} × {it['depth']:g}", fill="white")
        elif t == "pouf":
            box(c0, c1, 0, it["height"], hexrgb(it.get("color", "#CDBFA6"), pal))
            label((c0 + c1) / 2, it["height"] / 2, f"пуф {c1 - c0:g} × {it['depth']:g}")

    # switches and outlets: numbered, explained under the drawing
    legend = []
    for e in cfg.get("electrical", []):
        if e["wall"] != args.wall:
            continue
        n = len(legend) + 1
        x0, y0 = P(min(u(c) for c in e["centers"]) - FRAME / 2, e["z"] + FRAME / 2)
        x1, y1 = P(max(u(c) for c in e["centers"]) + FRAME / 2, e["z"] - FRAME / 2)
        d.rounded_rectangle([x0, y0, x1, y1], 5, fill="white", outline=INK, width=2)  # one frame for all posts
        for c in e["centers"]:
            x, y = P(u(c), e["z"])
            r = FACE / 2 * SCALE
            if e["type"] == "switch":
                kw = 2 * r / e.get("keys", 1)
                for i in range(e.get("keys", 1)):
                    d.rectangle([x - r + i * kw + 2, y - r, x - r + (i + 1) * kw - 2, y + r], outline=GREY)
            else:
                d.ellipse([x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7], outline=GREY, width=2)
        d.ellipse([x1 + 4, (y0 + y1) / 2 - 12, x1 + 28, (y0 + y1) / 2 + 12], fill=BLUE)
        d.text((x1 + 16, (y0 + y1) / 2), str(n), fill="white", font=f_s, anchor="mm")
        what = (f"выключатель {e.get('keys', 1)}-клавишный" if e["type"] == "switch" else
                "розетка" if len(e["centers"]) == 1 else f"{len(e['centers'])} розетки в общей рамке")
        where = " и ".join(f"{abs(u(c) - u(lo if sign > 0 else lo + length)):g}" for c in e["centers"])
        legend.append(f"{n} — {what}: центр на высоте {e['z']:g}, "
                      f"{'центры' if len(e['centers']) > 1 else 'центр'} в {where} от правого угла")

    # chains: positions along the floor, heights on both sides
    def hchain(cs, dy, color):
        pts = sorted({round(u(c), 2) for c in cs})
        y = TOP + height * SCALE + dy
        d.line([MARGIN + pts[0] * SCALE, y, MARGIN + pts[-1] * SCALE, y], fill=color, width=2)
        for p in pts:
            x = MARGIN + p * SCALE
            d.line([x, y - 14, x, y + 6], fill=color, width=1)
            d.line([x - 6, y + 6, x + 6, y - 6], fill=color, width=2)
        for p0, p1 in zip(pts, pts[1:]):
            d.text((MARGIN + (p0 + p1) / 2 * SCALE, y - 6), f"{p1 - p0:g}", fill=color, font=f_s, anchor="mb")

    def vchain(zs, x, color, side):
        zs = sorted(set(zs))
        d.line([x, P(0, zs[0])[1], x, P(0, zs[-1])[1]], fill=color, width=2)
        for z in zs:
            y = P(0, z)[1]
            d.line([x - 6, y + 6, x + 6, y - 6], fill=color, width=2)
        for z0, z1 in zip(zs, zs[1:]):
            y = (P(0, z0)[1] + P(0, z1)[1]) / 2
            d.text((x + 10 * side, y), f"{z1 - z0:g}", fill=color, font=f_s, anchor="lm" if side > 0 else "rm")

    marks = [lo, lo + length] + [c for s0, s1 in bands for c in (s0, s1)]
    marks += [c for dr in doors for c in dr["span"]]
    marks += [c for it in furniture if it["type"] == "mirror" for c in it["span"]]
    hchain(marks, 44, INK)
    stand = [c for it in furniture if it["type"] in ("cabinet", "pouf") for c in it["span"]]
    hchain(stand + [lo if sign > 0 else lo + length], 88, RED)
    zs = [0, height] + [z for it in furniture for z in (it.get("elevation", 0), it.get("elevation", 0) + it["height"])]
    vchain(zs, MARGIN + length * SCALE + 34, INK, 1)
    vchain([0, height] + [z for dr in doors for z in (dr.get("opening_height", 217),
                                                       dr.get("opening_height", 217) + CASING_W)], MARGIN - 34, RED, -1)

    y = TOP + height * SCALE + 130
    for line in legend + ["красная цепочка снизу — консоль и пуф; слева — проём и верх наличника; "
                          "верх зеркала = верх наличника"]:
        d.text((MARGIN, y), line, fill=INK if line[0].isdigit() else GREY, font=f_m)
        y += 34
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    img.save(out / f"elevation_{args.wall}.png")
    print(out / f"elevation_{args.wall}.png")


if __name__ == "__main__":
    main()
