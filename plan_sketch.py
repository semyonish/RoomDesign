"""Quick 2D sketch of plan.json: inner wall faces, openings, door swings and segment lengths.

    .venv/bin/python plan_sketch.py                      # → renders/plan/plan.png
    .venv/bin/python plan_sketch.py --focus bedroom_1    # room highlighted (default: the last one)

Walls are drawn as their inner faces; every wall is split by its openings and each piece is
labelled with its length. A room whose outline is not closed yet (status mentions "unknown") gets
dashed stubs with "?" at its open ends — that is where the next measurement goes.
"""

import argparse
import json
import math
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

PX = 2.0          # pixels per cm
PAD = 110         # cm of free space around the drawing (labels outside the walls)
LABEL_OFF = 16    # cm from the wall face to its length labels
STUB = 120        # cm, dashed continuation of an open outline

FONTS = Path("/System/Library/Fonts/Supplemental")
INK, MUTED, ACCENT, OPENING, GHOST = "#222222", "#8A8A8A", "#C2410C", "#2563EB", "#B8B8B8"
LIGHT = "#D9A400"


def font(size, bold=False):
    try:
        return ImageFont.truetype(str(FONTS / ("Arial Bold.ttf" if bold else "Arial.ttf")), size)
    except OSError:
        return ImageFont.load_default(size)


def sub(a, b): return (a[0] - b[0], a[1] - b[1])
def add(a, b): return (a[0] + b[0], a[1] + b[1])
def mul(a, s): return (a[0] * s, a[1] * s)
def norm(a): return math.hypot(*a)
def unit(a): return mul(a, 1 / norm(a))
def left(a): return (-a[1], a[0])          # interior side: outlines run counter-clockwise


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


def walls(plan):
    """(room id, wall) for every wall: the hall walls are top level, rooms carry their own."""
    for w in plan["walls"]:
        yield "hall", w
    for r in plan["rooms"]:
        for w in r.get("walls", []):
            yield r["id"], w


def openings(plan):
    yield from plan.get("openings", [])
    yield from plan.get("_openings_continued", [])
    for r in plan["rooms"]:
        yield from r.get("openings", [])


def footprints(node, name=None, hanging=False, depth=0):
    """(item, name, hanging) for every dict with a "footprint" anywhere in a room's data; nested pieces
    inherit the name and the wall-hung flag of their group (e.g. two nightstands listed under "items")."""
    if depth > 6:
        return
    if isinstance(node, dict):
        name, hanging = node.get("name", name), node.get("hanging", hanging)
        if "footprint" in node:
            yield node, name, hanging
        for k, v in node.items():
            if isinstance(v, (dict, list)) and not k.endswith("footprint"):
                yield from footprints(v, name, hanging, depth + 1)
    elif isinstance(node, list):
        for v in node:
            yield from footprints(v, name, hanging, depth + 1)


def light_items(lighting):
    """(fixture, its group) for a room's lighting, whichever way the plan lists it: groups with "items",
    "points" with orientation text (кухня-гостиная), or "rows" × "y" (прихожая, double fixtures along y)."""
    for key, group in lighting.items():
        if isinstance(group, dict) and isinstance(group.get("items"), list):
            for lt in group["items"]:
                if all(isinstance(lt.get(k), (int, float)) for k in "xy"):
                    yield lt, group
    for pt in lighting.get("points", []):
        kind = "chandelier" if "chandelier" in pt.get("id", "") else "double"
        axis = "y" if "вдоль y" in pt.get("orientation", "") else "x"
        yield {"x": pt["x"], "y": pt["y"], "type": kind, "axis": axis}, {}
    for row in lighting.get("rows", []):
        ys = row.get("y", lighting.get("y", []))
        xs = row["x"] if isinstance(row["x"], list) else [row["x"]] * len(ys)   # a row along a skewed wall
        for x, y in zip(xs, ys):
            yield {"x": x, "y": y, "type": "double", "axis": "y"}, {}


def point_on_wall(item, walls_by_name):
    """Plan position of a switch or outlet: x and y as given, or the missing one taken from its wall
    (a wall id, or "y = …" / "x = …" written in the wall description)."""
    x = next((item[k] for k in ("x", "x_center", "x_first") if isinstance(item.get(k), (int, float))), None)
    if x is None and item.get("x_centers"):
        x = sum(item["x_centers"]) / len(item["x_centers"])
    y = item.get("y") if isinstance(item.get("y"), (int, float)) else None
    if x is not None and y is not None:
        return (x, y)
    text = item.get("wall", "")
    w = walls_by_name.get(text.split(" ")[0])
    if w:
        (ax, ay), (bx, by) = w["from"], w["to"]
        if y is None and x is not None and abs(by - ay) < abs(bx - ax):
            return (x, ay + (by - ay) * (x - ax) / (bx - ax))
        if x is None and y is not None and abs(bx - ax) <= abs(by - ay):
            return (ax + (bx - ax) * (y - ay) / (by - ay), y)
    for axis, val in re.findall(r"([xy])\s*=\s*(-?\d+(?:\.\d+)?)", text):
        if axis == "y" and y is None and x is not None:
            return (x, float(val))
        if axis == "x" and x is None and y is not None:
            return (float(val), y)
    return None


class Wall:
    def __init__(self, w):
        self.id, self.a, self.b = w["id"], tuple(w["from"]), tuple(w["to"])
        self.d = unit(sub(self.b, self.a))
        self.n = left(self.d)
        self.len = norm(sub(self.b, self.a))
        self.axis = 0 if abs(self.d[0]) >= abs(self.d[1]) else 1
        self.thickness = w.get("thickness")

    def t(self, v):
        """Wall parameter 0..1 of the point whose dominant-axis coordinate is v."""
        return (v - self.a[self.axis]) / (self.b[self.axis] - self.a[self.axis])

    def at(self, t):
        return add(self.a, mul(sub(self.b, self.a), t))

    def span(self, o):
        ax = "xy"[self.axis]
        return tuple(sorted((self.t(o[f"{ax}_from"]), self.t(o[f"{ax}_to"]))))


def leaf_width(o):
    leaf = o.get("door_leaf") or o.get("model", {}).get("leaf_width", {}).get("value")
    return leaf or o["width"] - 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan", nargs="?", default="plan.json")
    ap.add_argument("--focus", help="room id to highlight; without it the whole apartment, nothing highlighted")
    ap.add_argument("-o", "--out", default="renders/plan/plan.png")
    ap.add_argument("--crop", action="store_true", help="also save the focus room alone: renders/plan/<room>.png")
    ap.add_argument("--rooms", action="store_true",
                    help="the whole plan, plus every room on its own (highlighted): renders/plan/<room>.png")
    args = ap.parse_args()

    plan = json.loads(Path(args.plan).read_text())
    sketch(plan, args.focus, Path(args.out), args.crop)
    if args.rooms:
        for rid in ["hall"] + [r["id"] for r in plan["rooms"] if r.get("walls")]:
            sketch(plan, rid, Path(args.out).with_name(f"{rid}_full.png"), True, working=False)
            Path(args.out).with_name(f"{rid}_full.png").unlink()


def sketch(plan, focus, out, crop, working=True):
    interior = plan.get("construction", {}).get("interior_walls", {}).get("total_assumed", 14)
    rooms = {"hall": {"id": "hall", "name": "прихожая"}} | {r["id"]: r for r in plan["rooms"]}
    room_data = {"hall": plan.get("hall", {})} | {r["id"]: r for r in plan["rooms"]}
    walls_by_name = {w["id"]: w for _, w in walls(plan)}

    by_room, by_id = {}, {}
    for rid, w in walls(plan):
        by_id[w["id"]] = wall = Wall(w)
        by_room.setdefault(rid, []).append(wall)
    holes = {}
    for o in openings(plan):
        wid = o.get("wall", "").split(" ")[0]
        if wid in by_id:
            holes.setdefault(wid, []).append(o)

    # open outlines of rooms still being measured
    stubs = []
    for rid, ws in by_room.items():
        if rid != "hall" and "unknown" in rooms[rid].get("status", "") and norm(sub(ws[0].a, ws[-1].b)) > 1:
            stubs += [(ws[-1].b, add(ws[-1].b, mul(ws[-1].n, STUB))), (ws[0].a, add(ws[0].a, mul(ws[0].n, STUB)))]

    pts = [p for ws in by_room.values() for w in ws for p in (w.a, w.b)] + [s[1] for s in stubs]
    x0, x1 = min(p[0] for p in pts) - PAD, max(p[0] for p in pts) + PAD
    y0, y1 = min(p[1] for p in pts) - PAD, max(p[1] for p in pts) + PAD + 50   # + title
    img = Image.new("RGB", (round((x1 - x0) * PX), round((y1 - y0) * PX)), "white")
    dr = ImageDraw.Draw(img)

    def P(p):
        return ((p[0] - x0) * PX, (y1 - p[1]) * PX)

    def text(p, s, fill, size=22, bold=False):
        dr.text(P(p), s, fill=fill, font=font(size, bold), anchor="mm", stroke_width=4, stroke_fill="white")

    def free_spot(ws, c, width):
        """Point nearest to c where a room name (two lines) fits inside the room, clear of the walls
        and of everything in `taken`."""
        inside = Image.new("L", img.size, 0)
        dw = ImageDraw.Draw(inside)
        outline = [P(w.a) for w in ws]
        dw.polygon(outline, fill=255)
        dw.line(outline + outline[:1], fill=0, width=60)
        free = ImageChops.subtract(inside, taken)
        cx, cy = P(c)
        bx0, by0, bx1, by1 = inside.getbbox() or (0, 0, 0, 0)
        spots = sorted(((x, y) for x in range(bx0, bx1, 8) for y in range(by0, by1, 8)),
                       key=lambda q: (q[0] - cx) ** 2 + (q[1] - cy) ** 2)
        half = width / 2 + 10
        for x, y in spots:
            if free.crop((int(x - half), y - 22, int(x + half), y + 66)).getextrema()[0] == 255:
                return (x / PX + x0, y1 - y / PX)
        return None

    def dashed(a, b, fill, width=3, dash=8):
        n = max(1, int(norm(sub(b, a)) / dash))
        for i in range(0, n, 2):
            dr.line([P(add(a, mul(sub(b, a), i / n))), P(add(a, mul(sub(b, a), min(i + 1, n) / n)))], fill=fill, width=width)

    labels = []
    taken = Image.new("L", img.size, 0)      # furniture, radiators, door swings: room names avoid them
    tk = ImageDraw.Draw(taken)
    marks = Image.new("L", img.size, 0)      # door swings and text: furniture names avoid them
    mk = ImageDraw.Draw(marks)
    item_labels = []
    for rid, data in room_data.items():   # radiators: a box 4 cm off the wall face
        rad = data.get("radiator")
        w = rad and by_id.get(rad["wall"].split(" ")[0])
        if w:
            ta, tb = w.span(rad)
            depth = rad.get("size_mm", [0, 0, 90])[2] / 10
            box = [add(w.at(t), mul(w.n, k)) for t, k in ((ta, 4), (tb, 4), (tb, 4 + depth), (ta, 4 + depth))]
            dr.polygon([P(q) for q in box], fill="#E5E7EB", outline=MUTED)
            tk.polygon([P(q) for q in box], fill=255)
        for item, name, hanging in footprints(data):   # furniture and equipment with a footprint
            poly = [tuple(q) for q in item["footprint"]]
            if hanging:   # wall-hung: dashed outline over whatever stands below
                for e0, e1 in zip(poly, poly[1:] + poly[:1]):
                    dashed(e0, e1, MUTED, width=2, dash=4)
            else:
                dr.polygon([P(q) for q in poly], fill="#F3EEE6", outline=MUTED)
            tk.polygon([P(q) for q in poly], fill=255)
            for k, inner in item.items():                     # e.g. mattress_footprint
                if k.endswith("_footprint"):
                    dr.polygon([P(tuple(q)) for q in inner], fill="white", outline=MUTED)
            if len(poly) == 4:
                at = mul(tuple(map(sum, zip(*poly))), 1 / 4)
                size = [max(c) - min(c) for c in zip(*poly)]
                k = 0 if size[0] < size[1] else 1
                if size[k] < 15 and by_room.get(rid):    # thin wall-hung piece: label just inside its room
                    ws = by_room[rid]
                    centre = mul(tuple(map(sum, zip(*(w.a for w in ws)))), 1 / len(ws))
                    shift = [0, 0]
                    shift[k] = 24 if centre[k] > at[k] else -24
                    at = add(at, tuple(shift))
            else:   # L-shapes: next to the middle of the longest side
                edges = list(zip(poly, poly[1:] + poly[:1]))
                a, b = max(edges, key=lambda e: norm(sub(e[1], e[0])))
                ccw = sum(p[0] * q[1] - q[0] * p[1] for p, q in edges) > 0
                inward = left(unit(sub(b, a))) if ccw else mul(left(unit(sub(b, a))), -1)
                at = add(mul(add(a, b), 0.5), mul(inward, 30))
            if item.get("label_at"):   # label moved off something drawn inside (e.g. a ceiling vent over a bathtub)
                at = tuple(item["label_at"])
            if name:
                item_labels.append((at, name))

    for rid, ws in by_room.items():
        color = ACCENT if rid == focus else INK
        for w in ws:
            spans = sorted((w.span(o), o) for o in holes.get(w.id, []))
            t = 0.0
            for (ta, tb), o in spans + [((1.0, 1.0), None)]:
                if tb > t:
                    if ta > t:   # solid piece of wall
                        dr.line([P(w.at(t)), P(w.at(ta))], fill=color, width=5)
                        labels.append((add(w.at((t + ta) / 2), mul(w.n, LABEL_OFF)), num((ta - t) * w.len), color))
                    t = tb
                if o is None:
                    continue
                mid = w.at((ta + tb) / 2)
                labels.append((add(mid, mul(w.n, LABEL_OFF)), num(o.get("width", (tb - ta) * w.len)), OPENING))
                kind = o.get("type", "")
                for part in o.get("parts") or ([o] if "окно" in kind or "балкон" in kind else []):
                    pa, pb = w.span(part)
                    for s in (-4, 4) if "окно" in part.get("type", kind) else (0,):   # glass: double line
                        dr.line([P(add(w.at(pa), mul(w.n, s))), P(add(w.at(pb), mul(w.n, s)))], fill=OPENING, width=2)
                    if part is not o:
                        labels.append((add(w.at((pa + pb) / 2), mul(w.n, -34)), f"{part['type'].split()[-1]} {num(part['width'])}", OPENING))
                hinge = re.search(r"петли у ([xy])\s*=\s*(-?\d+(?:\.\d+)?)", o.get("hinge_side", ""))
                if hinge and o.get("swing"):
                    th = w.t(float(hinge.group(2)))
                    other = tb if abs(th - ta) < abs(th - tb) else ta
                    inward = "в прихожую" in o["swing"]
                    side = w.n if inward else mul(w.n, -1)
                    p = add(w.at(th), (0, 0) if inward else mul(side, w.thickness or interior))
                    leaf = leaf_width(o)
                    closed, opened = unit(sub(w.at(other), w.at(th))), side
                    a0, a1 = math.atan2(closed[1], closed[0]), math.atan2(opened[1], opened[0])
                    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                    arc = [add(p, (leaf * math.cos(a0 + da * i / 24), leaf * math.sin(a0 + da * i / 24))) for i in range(25)]
                    dr.line([P(q) for q in arc], fill=OPENING, width=2)
                    tk.polygon([P(q) for q in [p] + arc], fill=255)
                    mk.polygon([P(q) for q in [p] + arc], fill=255)
                    dr.line([P(p), P(add(p, mul(opened, leaf)))], fill=OPENING, width=3)
                target = o.get("leads_to", "").split(" (")[0].split(" — ")[0]
                if target and target not in {r.get("name") for r in rooms.values()}:
                    labels.append((add(mid, mul(w.n, -70)), target, MUTED))

    for o in openings(plan):     # arches: a gap between two wall ends, sized square to the walls
        if "between" in o:
            a, b = map(tuple, o["between"])
            dashed(a, b, GHOST)
            k = 0 if abs(b[0] - a[0]) >= abs(b[1] - a[1]) else 1    # the width is measured along this axis
            mid = (a[1 - k] + b[1 - k]) / 2
            p0, p1 = [(c, mid) if k == 0 else (mid, c) for c in (a[k], b[k])]
            dr.line([P(p0), P(p1)], fill=OPENING, width=2)
            tick = (0, 5) if k == 0 else (5, 0)
            for q in (p0, p1):
                dr.line([P(sub(q, tick)), P(add(q, tick))], fill=OPENING, width=2)
            labels.append((add(mul(add(p0, p1), 0.5), (0, -12) if k == 0 else (14, 0)),
                           f"арка {num(o['width']['value'])}", OPENING))

    for a, b in stubs:
        dashed(a, b, ACCENT)
        text(add(b, mul(unit(sub(b, a)), 14)), "?", ACCENT, 34, True)

    for p, s, fill in labels:
        X, Y = P(p)
        half = font(22).getlength(s) / 2 + 6
        tk.rectangle([X - half, Y - 16, X + half, Y + 16], fill=255)
        mk.rectangle([X - half, Y - 16, X + half, Y + 16], fill=255)

    ring = [(0, 0)] + [(r * math.cos(k * math.pi / 4), r * math.sin(k * math.pi / 4)) for r in range(20, 200, 20) for k in range(8)]
    for p, s in item_labels:     # furniture names: the nearest spot clear of text and door swings
        X0, Y0 = P(p)
        half = font(22).getlength(s) / 2 + 6
        for dx, dy in ring:
            box = [int(X0 + dx - half), int(Y0 + dy - 16), int(X0 + dx + half), int(Y0 + dy + 16)]
            if marks.crop(box).getextrema()[1] == 0:
                break
        else:
            dx = dy = 0
            box = [int(X0 - half), int(Y0 - 16), int(X0 + half), int(Y0 + 16)]
        mk.rectangle(box, fill=255)
        tk.rectangle(box, fill=255)
        labels.append((((X0 + dx) / PX + x0, y1 - (Y0 + dy) / PX), s, MUTED))

    for rid, data in room_data.items():   # light fixtures: room names keep clear of them too
        for lt, _ in light_items(data.get("lighting", {})):
            X, Y = P((lt["x"], lt["y"]))
            tk.rectangle([X - 40, Y - 20, X + 40, Y + 20], fill=255)

    for rid, ws in by_room.items():
        name = rooms[rid].get("name", rid) + (" — в работе" if rid == focus and working else "")
        if len(ws) >= 3:
            c = mul(tuple(map(sum, zip(*(w.a for w in ws)))), 1 / len(ws))
            c = free_spot(ws, c, font(30, True).getlength(name)) or c
        else:
            c = add(ws[0].at(0.5), mul(ws[0].n, 150))
        text(c, name, ACCENT if rid == focus else MUTED, 30, True)
        if norm(sub(ws[0].a, ws[-1].b)) < 1:   # closed outline: shoelace area
            area = abs(sum(w.a[0] * w.b[1] - w.b[0] * w.a[1] for w in ws)) / 2 / 1e4
            text(add(c, (0, -24)), f"{area:.1f} м²".replace(".", ","), ACCENT if rid == focus else MUTED, 24)

    for p, s, fill in labels:
        text(p, s, fill)

    for o in plan.get("outlets", {}).get("items", []):
        q = point_on_wall(o, walls_by_name)
        if q:
            X, Y = P(q)
            dr.ellipse([X - 6, Y - 6, X + 6, Y + 6], fill="white", outline=INK, width=2)
    for sw in plan.get("switches", {}).get("items", []):
        q = point_on_wall(sw, walls_by_name)
        if q:
            X, Y = P(q)
            dr.rectangle([X - 5, Y - 5, X + 5, Y + 5], fill=INK)
    for rid, data in room_data.items():   # lights: wall lights a bit off the wall; ceiling doubles, chandeliers
        for lt, group in light_items(data.get("lighting", {})):
            if True:
                w = by_id.get(group.get("wall", "").split(" ")[0])
                if True:
                    kind = lt.get("type")
                    if kind in ("single", "double", "triple"):   # lamps 11 cm apart along `axis`
                        n = {"single": 1, "double": 2, "triple": 3}[kind]
                        step = (11, 0) if lt.get("axis", "x") == "x" else (0, 11)
                        lamps = [add((lt["x"], lt["y"]), mul(step, i - (n - 1) / 2)) for i in range(n)]
                        keys = lt.get("lamp_keys") or [None] * n      # from the -axis end
                        for q, key in zip(lamps, keys):
                            X, Y = P(q)
                            dr.ellipse([X - 8, Y - 8, X + 8, Y + 8], fill=LIGHT if key == 1 else "white",
                                       outline=LIGHT, width=4)
                    elif kind == "chandelier":
                        X, Y = P((lt["x"], lt["y"]))
                        for dx, dy in ((1, 1), (1, -1)):
                            dr.line([(X - 60 * dx, Y - 60 * dy), (X + 60 * dx, Y + 60 * dy)], fill=LIGHT, width=6)
                        dr.ellipse([X - 10, Y - 10, X + 10, Y + 10], fill=LIGHT)
                    else:
                        X, Y = P(add((lt["x"], lt["y"]), mul(w.n, 14) if w else (0, 0)))
                        dr.polygon([(X, Y - 9), (X + 9, Y), (X, Y + 9), (X - 9, Y)], fill=LIGHT)

    # title and 1 m scale bar
    dr.text((24, 20), "Эскиз по plan.json · см · ■ выключатель · ○ розетка · ◆ бра · ◎ BH53 (● клавиша 1) · ✕ люстра · пунктир с «?» — не измерено", fill=INK, font=ImageFont.truetype(str(FONTS / "Arial Unicode.ttf"), 26))
    bx, by = 24, 70
    dr.line([(bx, by), (bx + 100 * PX, by)], fill=INK, width=4)
    dr.text((bx + 100 * PX + 12, by), "1 м", fill=INK, font=font(22), anchor="lm")

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(out)
    if crop and by_room.get(focus):
        pts = [p for w in by_room[focus] for p in (w.a, w.b)]
        pts += [b for a, b in stubs if a in pts]    # open ends with their "?" stay in the crop
        (X0, Y1), (X1, Y0) = P((min(p[0] for p in pts) - 70, min(p[1] for p in pts) - 70)), \
            P((max(p[0] for p in pts) + 70, max(p[1] for p in pts) + 70))
        room_out = out.with_name(f"{focus}.png")
        img.crop((int(X0), int(Y0), int(X1), int(Y1))).save(room_out)
        print(room_out)


if __name__ == "__main__":
    main()
