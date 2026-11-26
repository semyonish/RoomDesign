"""Floor plans of the apartment: furniture plans, lighting plans and floor tile layouts, for the whole apartment and
for each room.
Drawn from rooms/apartment.json; rooms so far only measured in plan.json (e.g. the study) are taken from there.
Sizes are in cm, plan coordinates.

    .venv/bin/python plans.py                 # every sheet into renders/plan/
    .venv/bin/python plans.py --only lights   # just the lighting sheets
    .venv/bin/python plans.py --only tiles    # just the floor tile layouts: joints, cuts at every wall
"""

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
DIM = (200, 40, 40)
WALL_DIM = (25, 25, 25)   # wall and opening sizes; lamp distances stay red
GREY, GREY_LINE, LABEL = (238, 235, 230), (160, 150, 140), (95, 85, 75)
CURTAIN, CURTAIN_FILL = (120, 80, 150), (236, 228, 244)   # curtains in the ceiling cornice niche
WALL, GLASS = (70, 70, 70), (222, 236, 250)   # wall bodies at their thickness; window frames in their openings
BELOW = (196, 196, 196)   # under a window the wall below the cut shows from above: the bottom reveal
FRAME_D = 7               # PVC frame depth, cm (roomgen.plan.WINDOW_FRAME_D)
EDGE_R = 5.4              # BH53 visible part ⌀108: the edges the "по краям" lighting sheet measures to, cm
TILE, JOINT = (244, 240, 232), (150, 140, 128)   # tile layout sheets: the tile and its joints
GROUT = 0.1   # cm, the joint between tiles (user 2026-11-24: «стыки считай 1 мм»): the grid steps by tile + joint
TILE_WALL, ROUGH = (222, 206, 176), (135, 135, 135)   # wall tile with adhesive on lighting sheets; sizes on rough walls
COLORS = [(214, 120, 40), (40, 110, 200), (60, 160, 90), (170, 70, 160), (200, 170, 20), (20, 160, 170),
          (230, 80, 120), (110, 90, 200), (120, 140, 60), (150, 100, 60), (90, 90, 90), (190, 40, 40),
          (0, 110, 110), (240, 170, 120), (90, 50, 20), (130, 180, 230), (160, 160, 30), (60, 60, 140)]
LIGHT_NAMES = {
    "hall_1": "прихожая, клавиша 1", "hall_2": "прихожая, клавиша 2",
    "kitchen_spots": "кухонная линия", "sofa_spots": "точечные у дивана", "tv_spots": "точечные у ТВ",
    "chandelier": "люстра", "cornice": "лента карниза 20 Вт/м", "kitchen_led": "подсветка кухни",
    "br1_spots_1": "спальня, клавиша 1", "br1_spots_2": "спальня, клавиша 2", "sconces": "бра",
    "loggia_lr": "лоджия кухни-гостиной", "loggia_br1": "лоджия спальни 1",
    "st_spots_1": "кабинет, клавиша 1 (2 над столом + 1 у шкафа)", "st_spots_2": "кабинет, клавиша 2",
    "br2_spots_1": "спальня 2, клавиша 1", "br2_spots_2": "спальня 2, клавиша 2",
    "bathroom_1": "ванная, клавиша 1 (у двери)", "bathroom_2": "ванная, клавиша 2 (над ванной + вентилятор)",
    "toilet_1": "туалет, клавиша 1 (3 лампы)", "toilet_2": "туалет, клавиша 2 (вентилятор)",
    "curtains": "шторы в нише карниза; у окна размеры — от плоскости штор, 25 от окна",
    "tile": "плитка с клеем 1,5; серым — стены по черновой",
}
FURNITURE_NAMES = {
    "wardrobe": "шкаф-купе", "swing_wardrobe": "шкаф", "sofa": "диван", "bed": "кровать", "drawer_unit": "тумба",
    "niche_cabinet": "шкаф в нише", "cabinet": "тумба", "pouf": "пуф", "chair": "стул",
    "desk": "стол", "office_chair": "кресло", "bathtub": "ванна",
    "wall_toilet": "унитаз", "tiled_box": "короб", "appliance_column": "стирка + сушка",
}
# The hall and the kitchen-living room share one outline; it is split along the TV wall line across the passage.
HALL_WALLS = ("entrance", "hall_right", "hall_right_br1", "hall_far", "hall_left")


def num(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")


class Wall:
    def __init__(self, w):
        self.id, self.a, self.b = w["id"], tuple(w["from"]), tuple(w["to"])
        self.len = math.hypot(self.b[0] - self.a[0], self.b[1] - self.a[1])
        self.u = ((self.b[0] - self.a[0]) / self.len, (self.b[1] - self.a[1]) / self.len)
        self.n = (-self.u[1], self.u[0])            # interior side: outlines run counter-clockwise
        self.along_x = abs(self.u[0]) >= abs(self.u[1])
        t = w.get("thickness")
        self.t = t if isinstance(t, (int, float)) else 14   # plan.json walls may not have a measured one yet
        self.e0, self.e1 = w.get("past_ends", (0.0, 0.0))  # wall body past the ends, beyond its thickness

    def s(self, c):                                # wall position of a plan coordinate (x or y)
        return (c - (self.a[0] if self.along_x else self.a[1])) / (self.u[0] if self.along_x else self.u[1])

    def pt(self, s, d=0.0):
        return (self.a[0] + self.u[0] * s + self.n[0] * d, self.a[1] + self.u[1] * s + self.n[1] * d)


class Model:
    """Everything the sheets draw, in plan centimeters."""

    def __init__(self, cfg, plan):
        outlines = [cfg["outline"]] + [r["outline"] for r in cfg.get("extra_rooms", [])]
        self.walls = {w["id"]: Wall(w) for ol in outlines for w in ol}
        have = {"kitchen_living"} | {r["id"] for r in cfg.get("extra_rooms", [])}
        plan_rooms = [r for r in plan.get("rooms", []) if r["id"] not in have and r.get("walls")]
        for r in plan_rooms:
            for w in r["walls"]:
                self.walls[w["id"]] = Wall(w)
        names = {r["id"]: r.get("name", r["id"]) for r in plan.get("rooms", [])}

        # rooms: (id, name, floor polygon); a room sheet shows only what lies inside its polygon
        main = cfg["outline"]
        hall_poly = [tuple(w["from"]) for w in main if w["id"] in HALL_WALLS] + [tuple(main[len(HALL_WALLS) - 1]["to"])]
        hall_poly.append((main[0]["from"][0], hall_poly[-1][1]))     # back along the TV wall line
        rest = [tuple(w["from"]) for w in main if w["id"] not in HALL_WALLS]
        self.rooms = [("hall", "Прихожая", hall_poly),
                      ("kitchen_living", "Кухня-гостиная", rest + [(main[0]["from"][0], rest[0][1])])]
        for r in cfg.get("extra_rooms", []) + plan_rooms:
            poly = [tuple(w["from"]) for w in (r.get("outline") or r["walls"])]
            self.rooms.append((r["id"], names.get(r["id"], r["id"]).capitalize(), poly))

        # door openings cut out of walls, windows over walls
        self.gaps, self.windows = {}, []
        self.window_parts = []  # (wall, span, is a balcony door, frame plane from the room face) for drawing
        for dr in cfg["doors"]:
            w = self.walls[dr["wall"]]
            self.gaps.setdefault(w.id, []).append(sorted(w.s(c) for c in dr["span"]))
            # the same opening in the face of the room behind the door: the parallel wall across the partition
            for o in self.walls.values():
                if o is w or o.along_x != w.along_x or w.u[0] * o.u[0] + w.u[1] * o.u[1] > -0.999:
                    continue
                if abs((o.a[0] - w.a[0]) * w.n[0] + (o.a[1] - w.a[1]) * w.n[1]) > 30:
                    continue
                s = sorted(o.s(c) for c in dr["span"])
                if s[0] >= -0.5 and s[1] <= o.len + 0.5:
                    self.gaps.setdefault(o.id, []).append(s)
        for win in cfg.get("windows", []):
            w = self.walls[win["wall"]]
            plane = win.get("frame_depth") or min(15, w.t * 0.4)  # as roomgen.plan.build_window places the frame
            for part in win["parts"]:
                span = sorted(w.s(c) for c in part["span"])
                self.windows.append((w, span))
                self.window_parts.append((w, span, part["type"] == "door", plane))
        for r in plan_rooms:
            for o in r.get("openings", []):
                w = self.walls.get(o.get("wall"))
                if w is None:
                    continue
                span = (o.get("x_from"), o.get("x_to")) if w.along_x else (o.get("y_from"), o.get("y_to"))
                if None in span:
                    continue
                target = self.windows if "окно" in o.get("type", "") else None
                if target is not None:
                    target.append((w, sorted(w.s(c) for c in span)))
                    self.window_parts.append((w, sorted(w.s(c) for c in span), False, min(15, w.t * 0.4)))
                else:
                    self.gaps.setdefault(w.id, []).append(sorted(w.s(c) for c in span))

        # furniture: (label, size, polygon, label position or None for the middle)
        self.furniture = []
        k = cfg.get("kitchen") or {}
        if k.get("countertop_outline"):
            self.furniture.append(("кухня", "", [tuple(p) for p in k["countertop_outline"]], None))
        for t in k.get("tall", []):
            w = self.walls[t["wall"]]
            s0, s1 = sorted(w.s(c) for c in t["span"])
            self.furniture.append(("холодильник", f"встроенный, {num(s1 - s0)}×{num(k.get('depth', 60))}",
                                   [w.pt(s0), w.pt(s1), w.pt(s1, k.get("depth", 60)), w.pt(s0, k.get("depth", 60))],
                                   None))
        for it in cfg["furniture"]:
            if it["type"] not in FURNITURE_NAMES or it.get("wall") not in self.walls or "span" not in it \
                    or it.get("plan") is False:   # drawn from plan.json instead ("on_sheets")
                continue
            w, gap = self.walls[it["wall"]], it.get("gap", 0)
            s0, s1 = sorted(w.s(c) for c in it["span"])
            depth = it.get("depth", 40)
            poly = [w.pt(s0, gap), w.pt(s1, gap), w.pt(s1, gap + depth), w.pt(s0, gap + depth)]
            self.furniture.append((it.get("label", FURNITURE_NAMES[it["type"]]), f"{num(s1 - s0)}×{num(depth)}",
                                   poly, None))
        # from plan.json: rooms not in apartment.json yet, and pieces of modelled rooms marked "on_sheets" (their 3D twins
        # in apartment.json have "plan": false);
        # "sheet_label_at" moves the label on these sheets ("label_at" is for plan_sketch.py)
        for r in plan.get("rooms", []):
            for it in r.get("furniture", {}).values():
                if isinstance(it, dict) and it.get("footprint") and (r in plan_rooms or it.get("on_sheets")):
                    fp = [tuple(p) for p in it["footprint"]]
                    wx = max(p[0] for p in fp) - min(p[0] for p in fp)
                    wy = max(p[1] for p in fp) - min(p[1] for p in fp)
                    self.furniture.append((it.get("name", ""),
                                           it.get("plan_note", f"{num(max(wx, wy))}×{num(min(wx, wy))}"), fp,
                                           tuple(it["sheet_label_at"]) if it.get("sheet_label_at") else None))

        # lights
        lc = cfg["ceiling_lights"]
        self.spacing = lc.get("pair_spacing", 11)
        self.fixtures = list(lc["fixtures"])
        for r in plan_rooms:
            for it in r.get("lighting", {}).get("spots", {}).get("items", []):
                line = it.get("line") or it["id"].split("_")[1]
                fx = {"at": [it["x"], it["y"]], "axis": it.get("axis", "x"),
                      "count": {"single": 1, "triple": 3}.get(it.get("type"), 2),
                      "group": it.get("group") or f"{r['id']}_{line}"}
                if it.get("lamp_keys"):  # switch key of each lamp, from smaller to larger coordinate
                    fx["groups"] = [f"{r['id']}_{k}" for k in it["lamp_keys"]]
                self.fixtures.append(fx)
        # ceiling exhaust fans: a key of the room switch, like the lamps
        self.fans = [{"at": (v["x"], v["y"]), "diameter": v.get("diameter", 10), "group": f"{r['id']}_{v['key']}"}
                     for r in plan.get("rooms", []) for v in [r.get("ventilation") or {}] if v.get("key")]
        self.pendants = cfg.get("pendants", [])
        self.sconces = cfg.get("wall_lights", [])
        self.strips = []  # (group, wall, d, s0, s1, dashed)
        for it in cfg["furniture"]:
            if it["type"] == "curtains" and it.get("cornice") == "slot" and it.get("led", True):
                w = self.walls[it["wall"]]
                self.strips.append(("cornice", w, it["slot_offset"] + it["slot_width"] - 2.5, 0.0, w.len, True))
        ul = k.get("under_light")
        if ul:
            for run in ul["runs"]:
                w = self.walls[run["wall"]]
                s0, s1 = sorted(w.s(v) for v in run["span"])
                self.strips.append(("kitchen_led", w, ul["d"], s0, s1, False))
        self.guides = [(tuple(g["from"]), tuple(g["to"])) for g in cfg.get("plan_guides", [])]
        self.segs = [(w.a, w.b) for w in self.walls.values()] + self.guides
        # curtain planes (the room-side edge of a ceiling cornice, 25 from the window): lamp rows near windows
        # are measured from them
        self.curtains = []
        self.drapes = []  # (wall, niche from, niche to = curtain plane, tracks, gathered stacks as wall spans)
        for it in cfg["furniture"]:
            if it["type"] == "curtains" and it.get("cornice") == "slot" and it["wall"] in self.walls \
                    and it.get("plan") is not False:   # a bath curtain is no window curtain plane
                w, off = self.walls[it["wall"]], it.get("slot_offset", 12) + it.get("slot_width", 13)
                self.curtains.append((w.pt(0, off), w.pt(w.len, off)))
                self.drapes.append((w, it.get("slot_offset", 12), off, it.get("tracks", [17.5, 21]),
                                    [sorted(w.s(c) for c in st) for st in it.get("stacks", [])]))

        # tiled floors: (grid origin, tile size, polygons it covers: the room plus its patches into the doorways,
        # as deep as the 3D floor runs there)
        self.tiles, self.tiled_rooms = [], set()
        if (cfg.get("floor") or {}).get("type") == "porcelain":
            fl, polys = cfg["floor"], [[tuple(w["from"]) for w in main]]
            for dr in cfg["doors"]:
                rd = dr.get("reveal_depth", 10)
                fd = dr.get("floor_depth", rd if dr.get("kind") == "entrance" else rd + dr.get("leaf_thickness", 4) / 2)
                polys.append(self.patch(self.walls[dr["wall"]], dr["span"], fd, dr.get("floor_to")))
            self.tiles.append((tuple(fl.get("origin", (0, 0))), tuple(t + GROUT for t in fl["tile"]), polys))
            self.tiled_rooms |= {"hall", "kitchen_living"}
        for r in cfg.get("extra_rooms", []):
            rf = r.get("floor") or {}
            if rf.get("type") == "porcelain":
                polys = [[tuple(w["from"]) for w in r["outline"]]]
                polys += [self.patch(self.walls[dw["wall"]], dw["span"], dw["depth"]) for dw in r.get("doorways", [])]
                self.tiles.append((tuple(rf.get("origin", (0, 0))), tuple(t + GROUT for t in rf["tile"]), polys))
                self.tiled_rooms.add(r["id"])

        # tiled walls: the outline is the face of the tile; tile with adhesive (plan.json tile_layer) lies behind it
        layers = {r["id"]: (r.get("tile_layer") or {}).get("value", 1.5) for r in plan.get("rooms", [])}
        self.wall_tile = {w["id"]: layers.get(r["id"], 1.5) for r in cfg.get("extra_rooms", [])
                          if (r.get("walls") or {}).get("finish") == "tile" for w in r["outline"]}

    @staticmethod
    def patch(w, span, depth, to=None):  # floor running into a doorway, from the wall face `depth` into the opening,
        s0, s1 = sorted(w.s(c) for c in span)   # or up to a straight tile joint `to` (a plan x or y) across a skewed wall
        k = 0 if abs(w.n[0]) > abs(w.n[1]) else 1
        d0, d1 = [(w.pt(s)[k] - to) / w.n[k] for s in (s0, s1)] if to is not None else (depth, depth)
        return [w.pt(s0), w.pt(s1), w.pt(s1, -d1), w.pt(s0, -d0)]

    def tile_zone(self, x, y):
        return next((z for z in self.tiles if any(in_polygon(x, y, p) for p in z[2])), None)

    def tile_at(self, x, y):
        """Thickness of the wall tile whose face (x, y) lies on, else None."""
        for wid, t in self.wall_tile.items():
            w = self.walls[wid]
            s = (x - w.a[0]) * w.u[0] + (y - w.a[1]) * w.u[1]
            if abs((x - w.a[0]) * w.n[0] + (y - w.a[1]) * w.n[1]) < 0.3 and -0.5 <= s <= w.len + 0.5:
                return t
        return None

    def openings(self, w):
        """Door and window spans along a wall; the overlapping sash frames of one window merge into one opening,
        a balcony door next to its window stays a separate one."""
        spans = sorted([tuple(g) for g in self.gaps.get(w.id, [])] + [tuple(s) for ww, s in self.windows if ww is w])
        out = []
        for s0, s1 in spans:
            s0, s1 = max(0.0, s0), min(w.len, s1)
            if out and s0 < out[-1][1] - 0.5:
                out[-1] = (out[-1][0], max(out[-1][1], s1))
            else:
                out.append((s0, s1))
        return out

    def hit(self, x, y, dx, dy, curtains=False):
        """Distance along the unit direction (dx, dy) from (x, y) to the nearest wall or guide
        (or curtain plane)."""
        best = None
        for (ax, ay), (bx, by) in self.segs + (self.curtains if curtains else []):
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-9:
                continue
            t = ((ax - x) * ey - (ay - y) * ex) / den
            u = ((ax - x) * dy - (ay - y) * dx) / den
            if t > 0.5 and -1e-6 <= u <= 1 + 1e-6:
                best = t if best is None else min(best, t)
        return best


def sheet(m, box, scale, title, mode, room=None, edges=False):
    x0, x1, y0, y1 = box
    margin = 200 if room and mode in ("lighting", "tiles") else 140   # room lighting / tile sheets: chains outside
    if room and mode == "lighting" and any(in_polygon(*m.walls[wid].pt(m.walls[wid].len / 2, 6), room)
                                           for wid in m.wall_tile):
        margin += 45   # one more chain outside: the rough walls behind the tile
    if room and mode == "furniture":   # wall lengths sit past the wall body: a thick top wall (a loggia's 40)
        t = max((w.t for w in m.walls.values()            # would push its length into the title
                 if w.n[1] < -0.5 and in_polygon(*w.pt(w.len / 2, 6), room)), default=0)
        margin = max(margin, int(110 + (t - 13) * scale))
    short =(ImageFont.truetype(BOLD, 34).getlength(title) + 40 - margin) / scale - (x1 - x0)
    if short > 0:   # a narrow room (a loggia): the sheet widens until its title fits
        x0, x1 = x0 - short / 2, x1 + short / 2
    W, H = int((x1 - x0) * scale) + 2 * margin, int((y1 - y0) * scale) + 2 * margin + 120
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    fs = max(15, int(9 * scale ** 0.5))
    f_s, f_m, f_b = ImageFont.truetype(FONT, fs), ImageFont.truetype(FONT, fs + 4), ImageFont.truetype(BOLD, 34)

    def P(x, y):  # y grows upward on the sheet (away from the entrance)
        return (margin + (x - x0) * scale, H - margin - 120 - (y - y0) * scale)

    def inside(x, y, pad=0.0):
        return x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad

    def dashed(a, b, fill, width, step=8):
        n = max(1, int(math.hypot(b[0] - a[0], b[1] - a[1]) / step))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1.0, (i + 1) / n)
            d.line([P(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                    P(a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=fill, width=width)

    def slab(w, s0, s1, pad=0.0):  # the wall body behind its face, from s0 to s1 along it
        return [P(*w.pt(s0, pad)), P(*w.pt(s1, pad)), P(*w.pt(s1, -w.t - pad)), P(*w.pt(s0, -w.t - pad))]

    # walls at their thickness: each band runs past its ends to fill the corners, the overshoot into a room
    # is cleared by that room's floor; door openings cut through, windows drawn across the wall
    for w in m.walls.values():
        d.polygon(slab(w, -w.t - w.e0, w.len + w.t + w.e1), fill=WALL)
    for _, _, poly in m.rooms:
        d.polygon([P(*p) for p in poly], fill="white")
    if mode == "lighting":  # tile with adhesive between the face and the rough wall, the rough face as a line
        for wid, t in m.wall_tile.items():
            w = m.walls[wid]
            d.polygon([P(*w.pt(-t)), P(*w.pt(w.len + t)), P(*w.pt(w.len + t, -t)), P(*w.pt(-t, -t))], fill=TILE_WALL)
            d.line([P(*w.pt(-t, -t)), P(*w.pt(w.len + t, -t))], fill=JOINT, width=1)
    for w in m.walls.values():
        for s0, s1 in m.gaps.get(w.id, []):
            d.polygon(slab(w, s0, s1, 0.5), fill="white")
    for w, (s0, s1), door, plane in m.window_parts:
        # the opening: a balcony door goes down to the floor; under a window the bottom reveal shows, room side
        # to the outside face; the frame a thin band where it really stands, `plane` from the room face
        d.polygon(slab(w, s0, s1), fill="white" if door else BELOW)
        a, b = -plane + FRAME_D / 2, -plane - FRAME_D / 2
        d.polygon([P(*w.pt(s0, a)), P(*w.pt(s1, a)), P(*w.pt(s1, b)), P(*w.pt(s0, b))], fill=GLASS)
        for dd in (a, -plane, b):
            d.line([P(*w.pt(s0, dd)), P(*w.pt(s1, dd))], fill=(120, 170, 220), width=2)

    if mode == "tiles":  # the tile with its joints over every tiled floor, the joints the layout starts from in red
        for (ox, oy), (tx, ty), polys in m.tiles:
            mask = Image.new("L", (W, H), 0)
            for p in polys:
                ImageDraw.Draw(mask).polygon([P(*q) for q in p], fill=255)
            layer = Image.new("RGB", (W, H), TILE)
            ld = ImageDraw.Draw(layer)
            xs, ys = [q[0] for p in polys for q in p], [q[1] for p in polys for q in p]
            for k in range(math.floor((min(xs) - ox) / tx), math.ceil((max(xs) - ox) / tx) + 1):
                ld.line([P(ox + k * tx, min(ys)), P(ox + k * tx, max(ys))], fill=DIM if k == 0 else JOINT,
                        width=4 if k == 0 else 2)
            for k in range(math.floor((min(ys) - oy) / ty), math.ceil((max(ys) - oy) / ty) + 1):
                ld.line([P(min(xs), oy + k * ty), P(max(xs), oy + k * ty)], fill=DIM if k == 0 else JOINT,
                        width=4 if k == 0 else 2)
            img.paste(layer, (0, 0), mask)
        d = ImageDraw.Draw(img)

    # furniture
    for label, size, poly, at in m.furniture:
        cx, cy = sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)
        if not inside(cx, cy, 20):
            continue
        if mode == "tiles":  # outlines over the tile; no floor tile under the bath and the box
            solid = label == "ванна" or label.startswith("короб")
            d.polygon([P(*p) for p in poly], fill="white" if solid else None, outline=GREY_LINE)
            sides = [math.dist(a, b) for a, b in zip(poly, poly[1:] + poly[:1])]
            if solid and min(sides) >= 30:  # a narrow box goes without a label
                d.text(P(cx, cy), label, fill=LABEL, font=f_m, anchor="mm")
            continue
        d.polygon([P(*p) for p in poly], fill=GREY, outline=GREY_LINE)
        if mode == "furniture" and label:
            px, py = P(*(at or (cx, cy)))
            d.text((px, py - fs * 0.6), label, fill=LABEL, font=f_m, anchor="mm")
            if size:
                d.text((px, py + fs * 0.7), size, fill=LABEL, font=f_s, anchor="mm")

    if mode == "tiles":  # numbered pieces (tile_layout.py): the tile each is cut from, a cut in red with its size
        for x, y, lines, cut, size in getattr(m, "tile_labels", ()):
            fb = ImageFont.truetype(BOLD, max(10, min(fs + 6, int(size * scale))))
            fr = ImageFont.truetype(FONT, max(9, min(fs, int(size * scale * 0.75))))
            px, py = P(x, y)
            py -= (len(lines) - 1) * fb.size * 0.55
            for i, t in enumerate(lines):
                d.text((px, py + i * fb.size * 1.1), t, fill=DIM if cut else LABEL, font=fr if i else fb, anchor="mm")

    # door openings: a thin line across, in the face of the wall
    for w in m.walls.values():
        for s0, s1 in m.gaps.get(w.id, []):
            d.line([P(*w.pt(s0)), P(*w.pt(s1))], fill=(185, 185, 185), width=2)
    for a, b in m.guides:
        dashed(a, b, (150, 150, 150), 2)

    if mode == "lighting":
        def here(x, y, pad=0.0):  # on a room sheet, only what lies in the room
            return inside(x, y, pad) and (room is None or in_polygon(x, y, room))
        legend = draw_lights(m, d, P, here, dashed, f_s, scale, edges)
        if any(here(*m.walls[wid].pt(m.walls[wid].len / 2, 6)) for wid in m.wall_tile):
            legend["tile"] = -1
        if room is None:  # whole apartment: the length of every wall, inside its room
            for w in m.walls.values():
                if w.len < 15 or not inside(*w.pt(w.len / 2)):
                    continue
                t = num(w.len)
                off = (fs + 4) * 0.7 + 6 if w.along_x else d.textlength(t, font=f_m) / 2 + 10
                x, y = P(*w.pt(w.len / 2))
                c = (x + w.n[0] * off, y - w.n[1] * off)
                bb = d.textbbox(c, t, font=f_m, anchor="mm")
                d.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill="white")
                d.text(c, t, fill=WALL_DIM, font=f_m, anchor="mm")

    # room sheets: blank out everything beyond the room (its floor plus the wall band), wall lengths outside
    if room:
        mask = Image.new("L", (W, H), 0)
        md = ImageDraw.Draw(mask)
        pts = [P(*q) for q in room]
        md.polygon(pts, fill=255)
        md.line(pts + [pts[0]], fill=255, width=int(12 * scale), joint="curve")
        for w in m.walls.values():  # and the bodies of its own walls
            if in_polygon(*w.pt(w.len / 2, 6), room):
                md.polygon(slab(w, -w.t - w.e0, w.len + w.t + w.e1), fill=255)
        img.paste(Image.new("RGB", (W, H), "white"), (0, 0), Image.eval(mask, lambda v: 255 - v))
        d = ImageDraw.Draw(img)
        if mode == "furniture":
            for w in m.walls.values():
                mx, my = w.pt(w.len / 2, -w.t - 12)
                cx, cy = w.pt(w.len / 2, 6)
                if w.len >= 25 and in_polygon(cx, cy, room):
                    d.text(P(mx, my), num(w.len), fill=DIM, font=f_m, anchor="mm")
        else:  # outside each wall: corner → door / window edges (tile joints) → corner, then the whole wall
            def upright(c, t, fill=WALL_DIM):  # text along a vertical wall, reading upward
                bb = d.textbbox((0, 0), t, font=f_m)
                tw, th = bb[2] - bb[0] + 6, bb[3] - bb[1] + 6
                im = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
                ImageDraw.Draw(im).text((tw / 2, th / 2), t, font=f_m, fill=fill, anchor="mm")
                im = im.rotate(90, expand=True)
                img.paste(im, (int(c[0] - im.width / 2), int(c[1] - im.height / 2)), im)

            def wall_chain(w, dd, pts, full=None, ink=WALL_DIM):  # full: the whole-tile size; other pieces are cuts, in red
                q = [P(*w.pt(s, dd)) for s in pts]
                for s, p in zip(pts, q):
                    d.line([P(*w.pt(s, -2)), P(*w.pt(s, dd - 3))], fill=(150, 150, 150), width=1)
                    d.line([p[0] - 6, p[1] + 6, p[0] + 6, p[1] - 6], fill=ink, width=2)
                d.line([q[0], q[-1]], fill=ink, width=2)
                ox, oy = -w.n[0], w.n[1]  # outward on the sheet, whose y axis points down
                off = (fs + 4) * 0.7
                for s0, s1, pa, pb in zip(pts, pts[1:], q, q[1:]):
                    c = ((pa[0] + pb[0]) / 2 + ox * off, (pa[1] + pb[1]) / 2 + oy * off)
                    fill = DIM if full and abs(s1 - s0 - full) > 0.3 else ink
                    if w.along_x:
                        d.text(c, num(s1 - s0), fill=fill, font=f_m, anchor="mm")
                    else:
                        upright(c, num(s1 - s0), fill)

            for w in m.walls.values():
                cx, cy = w.pt(w.len / 2, 6)
                if mode != "tiles" or w.len < 40 or not in_polygon(cx, cy, room):   # short jogs: the neighbours show them
                    continue
                z = m.tile_zone(cx, cy)
                if z is None:
                    continue
                (ox, oy), (tx, ty), _ = z  # joints across this wall, where they meet it
                o, step = (ox, tx) if w.along_x else (oy, ty)
                c0, c1 = sorted((w.a[0], w.b[0]) if w.along_x else (w.a[1], w.b[1]))
                joints = {round(w.s(o + k * step), 1) for k in range(math.floor((c0 - o) / step), math.ceil((c1 - o) / step) + 1)}
                wall_chain(w, -w.t - 10, sorted({0.0, round(w.len, 1)} | {s for s in joints if 0.5 < s < w.len - 0.5}), step)
                wall_chain(w, -w.t - 24, [0.0, w.len])

            for w in m.walls.values() if mode == "lighting" else ():
                cx, cy = w.pt(w.len / 2, 6)
                if w.len < 15 or not in_polygon(cx, cy, room):   # skip the 10 cm pier ends and jogs
                    continue
                ops = m.openings(w)
                if ops:  # beyond the wall body
                    wall_chain(w, -w.t - 10, sorted({0.0, w.len} | {round(s, 1) for o in ops for s in o}))
                wall_chain(w, -w.t - (24 if ops else 10), [0.0, w.len])
                if w.id in m.wall_tile:  # tiled: the wall as measured, on the rough face behind the tile
                    t = m.wall_tile[w.id]
                    wall_chain(w, -w.t - (38 if ops else 24), [-t, w.len + t], ink=ROUGH)

    if mode == "lighting":
        cell = max((d.textlength(LIGHT_NAMES.get(g, g), font=f_m) for g in legend), default=0) + 72
        cols = max(1, min(3, int((W - 2 * margin) // cell)))   # narrow sheet: fewer columns, so long names don't overlap
        rows = -(-len(legend) // cols)  # grow the sheet when the legend needs more rows than the bottom band holds
        if H - 130 + rows * 36 + 20 > H:
            tall = Image.new("RGB", (W, H - 130 + rows * 36 + 20), "white")
            tall.paste(img, (0, 0))
            img, d = tall, ImageDraw.Draw(tall)
        lx, ly = margin, H - 130
        for i, g in enumerate(legend):
            x, y = lx + (i % cols) * ((W - 2 * margin) // cols), ly + (i // cols) * 36
            if g == "tile":  # the band as on the plan, the rough face along its back
                d.rectangle([x, y + 4, x + 30, y + 18], fill=TILE_WALL)
                d.line([x, y + 18, x + 30, y + 18], fill=JOINT, width=1)
            elif g == "curtains":  # the niche with a wave, as on the plan
                d.rounded_rectangle([x, y, x + 30, y + 22], 6, fill=CURTAIN_FILL, outline=CURTAIN)
                d.line([(x + 3 + k * 3, y + 11 + 4 * math.sin(k * 1.4)) for k in range(9)], fill=CURTAIN, width=2)
            else:
                d.rounded_rectangle([x, y, x + 30, y + 22], 6, fill=COLORS[legend[g] % len(COLORS)],
                                    outline=(30, 30, 30))
            d.text((x + 42, y + 11), LIGHT_NAMES.get(g, g), fill=(30, 30, 30), font=f_m, anchor="lm")
        note = ("красным — от стен (у окон — от плоскости штор) до краёв светильников (видимая часть Ø10,8) и между "
                "краями, люстра — по центру; чёрным — стены по чистовой отделке и проёмы, см" if edges else
                "красным — от стен (у окон — от плоскости штор) до центров ламп и между лампами; "
                "чёрным — стены по чистовой отделке и проёмы, см")
        if d.textlength(title, font=f_b) + d.textlength(note, font=f_m) + 40 > W - 2 * margin:   # narrow sheet: under the title
            lines = [""]
            for word in note.split(" "):  # wrapped to the sheet width
                if lines[-1] and d.textlength(f"{lines[-1]} {word}", font=f_m) > W - margin - 40:
                    lines.append(word)
                else:
                    lines[-1] = f"{lines[-1]} {word}".strip()
            for i, line in enumerate(lines):
                d.text((margin, 100 + i * (fs + 10)), line, fill=DIM, font=f_m)
        else:
            d.text((W - margin, 60), note, fill=DIM, font=f_m, anchor="rt")
    if mode == "tiles" and m.tiles:
        tx, ty = m.tiles[0][1]
        note = (f"плитка {num(tx - GROUT)} × {num(ty - GROUT)}, шов {num(GROUT * 10)} мм, прямая раскладка, швы в линию; красные линии — опорные швы, "
                "от них ведётся раскладка; размеры — от чистовой стены до швов, см; красные числа — подрезка; "
                "под ванной и коробом плитки нет")
        lines = [""]
        for word in note.split(" "):  # wrapped to the sheet width, under the title
            if lines[-1] and d.textlength(f"{lines[-1]} {word}", font=f_m) > W - 2 * margin:
                lines.append(word)
            else:
                lines[-1] = f"{lines[-1]} {word}".strip()
        top = 100 if room is None else H - 110   # room sheets: chains above the plan, the note goes below
        for i, line in enumerate(lines):
            d.text((margin, top + i * (fs + 10)), line, fill=DIM, font=f_m)
    d.text((margin, 50), title, fill=(20, 20, 20), font=f_b)
    return img


def in_polygon(x, y, poly):
    """Even-odd rule."""
    inside = False
    for (ax, ay), (bx, by) in zip(poly, poly[1:] + poly[:1]):
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay):
            inside = not inside
    return inside


GROUP_INDEX = {}


def color(g):
    GROUP_INDEX.setdefault(g, len(GROUP_INDEX))
    return COLORS[GROUP_INDEX[g] % len(COLORS)]


def draw_lights(m, d, P, inside, dashed, f_s, scale, edges=False):
    """Fixtures, strips, pendants, sconces and dimension chains inside the sheet; returns the legend groups.
    `edges`: the chains run to the edges of the fixtures' visible part (⌀10.8, BH53) instead of the lamp centers."""
    used = {}

    def use(g):
        c = color(g)
        used[g] = GROUP_INDEX[g]
        return c

    def wave(w, dd, s0, s1, amp, period, width):
        n = max(2, int((s1 - s0) / period * 8))
        d.line([P(*w.pt(s0 + (s1 - s0) * i / n, dd + amp * math.sin(2 * math.pi * (s1 - s0) * i / n / period)))
                for i in range(n + 1)], fill=CURTAIN, width=width, joint="curve")

    # curtains: the cornice niche in the ceiling, a wave on each track, the gathered stacks bolder;
    # the room-side edge of the niche is the curtain plane that lamp rows near windows are measured from
    for w, d0, d1, tracks, stacks in m.drapes:
        if not inside(*w.pt(w.len / 2, d1)):
            continue
        used["curtains"] = -1
        d.polygon([P(*w.pt(0, d0)), P(*w.pt(w.len, d0)), P(*w.pt(w.len, d1)), P(*w.pt(0, d1))], fill=CURTAIN_FILL)
        for t in tracks:
            wave(w, t, 0, w.len, 1.0, 8, 2)
        for s0, s1 in stacks:
            wave(w, sum(tracks) / len(tracks), s0, s1, 3.0, 5, 3)
        d.line([P(*w.pt(0, d1)), P(*w.pt(w.len, d1))], fill=CURTAIN, width=3)

    for g, w, dd, s0, s1, dash in m.strips:
        a, b = w.pt(s0, dd), w.pt(s1, dd)
        if not (inside(*a, 20) or inside(*b, 20)):
            continue
        c = use(g)
        if dash:
            dashed(a, b, c, 5, step=7)
        else:
            d.line([P(*a), P(*b)], fill=c, width=5)

    r = 5.4 * scale
    for fx in m.fixtures:
        x, y = fx["at"]
        if not inside(x, y):
            continue
        keys = fx.get("groups") or [fx.get("group")] * fx.get("count", 2)  # same keys as roomgen/lights.py
        n = len(keys)
        for k, g in enumerate(keys):
            off = (k - (n - 1) / 2) * m.spacing
            px, py = P(x + (off if fx.get("axis") == "x" else 0), y + (0 if fx.get("axis") == "x" else off))
            d.ellipse([px - r, py - r, px + r, py + r], fill=use(g), outline=(30, 30, 30), width=2)

    for fan in m.fans:   # ring of the duct with three blades, labelled
        (cx, cy) = fan["at"]
        if not inside(cx, cy):
            continue
        c, rr = use(fan["group"]), max(fan["diameter"] / 2 * scale, 14)
        px, py = P(cx, cy)
        d.ellipse([px - rr, py - rr, px + rr, py + rr], fill=(255, 255, 255), outline=c, width=4)
        for i in range(3):
            a = 2 * math.pi * i / 3
            d.polygon([(px, py), (px + rr * 0.85 * math.cos(a), py + rr * 0.85 * math.sin(a)),
                       (px + rr * 0.85 * math.cos(a + 0.7), py + rr * 0.85 * math.sin(a + 0.7))], fill=c)
        d.text((px, py + rr + 6), f"вентилятор Ø{num(fan['diameter'] * 10)}", fill=(30, 30, 30), font=f_s, anchor="mt")

    for p in m.pendants:
        (cx, cy) = p["at"]
        if not inside(cx, cy):
            continue
        c = use(p.get("group", "chandelier"))
        if p.get("style") == "sticks":
            L, n, gap, st = p["length"], p["bars"], p["bar_spacing"], p["stagger"]
            for a_deg in (p["angle"], p["angle"] + p["cross"]):
                a = math.radians(a_deg)
                u, v = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
                for i in range(n):
                    o, sh = (i - (n - 1) / 2) * gap, st * (1 if i % 2 else -1)
                    mx, my = cx + v[0] * o + u[0] * sh, cy + v[1] * o + u[1] * sh
                    d.line([P(mx - u[0] * L / 2, my - u[1] * L / 2), P(mx + u[0] * L / 2, my + u[1] * L / 2)],
                           fill=c, width=5)
        elif p.get("style") == "globes":
            k = math.cos(math.radians(p.get("tilt", 20)))
            gr = p["diameter"] / 2
            for i in range(p["count"]):
                a = 2 * math.pi * (i + 0.5) / p["count"]
                u = (math.cos(a), math.sin(a))
                arm, gc = p["reach"] * k, (p["reach"] + 2.4 + gr * 0.95) * k
                d.line([P(cx, cy), P(cx + u[0] * arm, cy + u[1] * arm)], fill=c, width=4)
                gx, gy = P(cx + u[0] * gc, cy + u[1] * gc)
                d.ellipse([gx - gr * scale, gy - gr * scale, gx + gr * scale, gy + gr * scale], fill=(255, 255, 255),
                          outline=c, width=4)
        else:
            rr = p["diameter"] / 2 * scale
            px, py = P(cx, cy)
            d.ellipse([px - rr, py - rr, px + rr, py + rr], outline=c, width=5)
        px, py = P(cx, cy)
        d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(30, 30, 30))

    for sc in m.sconces:
        w = m.walls[sc["wall"]]
        for cc in sc["centers"]:
            x, y = w.pt(w.s(cc), 6)
            if inside(x, y):
                px, py = P(x, y)
                d.ellipse([px - 11, py - 11, px + 11, py + 11], fill=use(sc.get("group", "sconces")),
                          outline=(30, 30, 30), width=2)

    # dimension chains, wall to wall through the lamp centers of each row of fixtures
    def ends(points, along_x, curtains=True):
        pts = sorted(points, key=(lambda p: p[0]) if along_x else (lambda p: p[1]))
        dx, dy = (1, 0) if along_x else (0, 1)
        return (pts, m.hit(pts[0][0], pts[0][1], -dx, -dy, curtains),
                m.hit(pts[-1][0], pts[-1][1], dx, dy, curtains))

    def chain(points, along_x, offset, curtains=True, grow=True):
        key = (lambda p: p[0]) if along_x else (lambda p: p[1])
        # each fixture → its lamp centers; lamps side by side across the chain collapse into one point
        points = list({key(q): q for p in points for q in lamps.get(p, [p])}.values())
        dx, dy = (1, 0) if along_x else (0, 1)
        spans = set()  # the visible part of each lamp: ticks, no size (the note gives ⌀10.8)
        if edges and grow:
            points = [(q[0] + dx * e * EDGE_R, q[1] + dy * e * EDGE_R) for q in points for e in (-1, 1)]
            spans = {(round(key(points[i]), 3), round(key(points[i + 1]), 3)) for i in range(0, len(points), 2)}
        pts, t0, t1 = ends(points, along_x, curtains)
        _, w0, w1 = ends(points, along_x, False)  # a chain ending on a curtain plane goes on to the window: 25
        line = ([(pts[0][0] - dx * w0, pts[0][1] - dy * w0)] if t0 and w0 and w0 > t0 + 0.5 else []) + \
               ([(pts[0][0] - dx * t0, pts[0][1] - dy * t0)] if t0 else []) + pts + \
               ([(pts[-1][0] + dx * t1, pts[-1][1] + dy * t1)] if t1 else []) + \
               ([(pts[-1][0] + dx * w1, pts[-1][1] + dy * w1)] if t1 and w1 and w1 > t1 + 0.5 else [])
        # a chain ending on a tiled wall goes on through the tile to the rough wall: 1.5
        t = m.tile_at(*line[0])
        if t:
            line.insert(0, (line[0][0] - dx * t, line[0][1] - dy * t))
        t = m.tile_at(*line[-1])
        if t:
            line.append((line[-1][0] + dx * t, line[-1][1] + dy * t))
        ox, oy = (0, offset) if along_x else (offset, 0)
        q = [P(p[0] + ox, p[1] + oy) for p in line]
        d.line([q[0], q[-1]], fill=DIM, width=2)
        for p in q:
            d.line([p[0] - 6, p[1] + 6, p[0] + 6, p[1] - 6], fill=DIM, width=2)
        for a, b, pa, pb in zip(line, line[1:], q, q[1:]):
            mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
            if (round(key(a), 3), round(key(b), 3)) in spans:
                continue
            if abs(key(b) - key(a)) < 5:  # the tile: too short to hold its size, which goes beside it, into the room
                inner = pb if a == line[0] else pa
                sx, sy = (1 if inner[0] > (pa[0] + pb[0] - inner[0]) else -1), (1 if inner[1] > (pa[1] + pb[1] - inner[1]) else -1)
                if along_x:
                    d.text((inner[0] + sx * 4, my + 8), num(abs(key(b) - key(a))), fill=DIM, font=f_s,
                           anchor="lt" if sx > 0 else "rt")
                else:
                    d.text((mx - 8, inner[1] + sy * 4), num(abs(key(b) - key(a))), fill=DIM, font=f_s,
                           anchor="rt" if sy > 0 else "rb")
            elif along_x:
                d.text((mx, my - 8), num(abs(key(b) - key(a))), fill=DIM, font=f_s, anchor="mb")
            else:
                d.text((mx + 8, my), num(abs(key(b) - key(a))), fill=DIM, font=f_s, anchor="lm")

    def blocked(a, b):  # a wall between two fixtures: different rooms
        dist = math.hypot(b[0] - a[0], b[1] - a[1])
        t = m.hit(a[0], a[1], (b[0] - a[0]) / dist, (b[1] - a[1]) / dist)
        return t is not None and t < dist

    def runs(pts, along_x):
        pts = sorted(pts, key=(lambda p: p[0]) if along_x else (lambda p: p[1]))
        out = [[pts[0]]]
        for a, b in zip(pts, pts[1:]):
            if blocked(a, b):
                out.append([])
            out[-1].append(b)
        return out

    centers, lamps = [], {}
    for fx in m.fixtures:
        x, y = fx["at"]
        if not inside(x, y):
            continue
        n = len(fx.get("groups") or [fx.get("group")] * fx.get("count", 2))
        offs = [(k - (n - 1) / 2) * m.spacing for k in range(n)]
        centers.append((x, y))
        lamps[(x, y)] = [(x + o, y) if fx.get("axis") == "x" else (x, y + o) for o in offs]
    if centers:
        by_x, by_y = {}, {}
        for x, y in centers:
            by_x.setdefault(x, []).append((x, y))
            by_y.setdefault(y, []).append((x, y))
        by_x = {(k, i): rr for k, pts in by_x.items() for i, rr in enumerate(runs(pts, False))}
        by_y = {(k, i): rr for k, pts in by_y.items() for i, rr in enumerate(runs(pts, True))}
        for rows, along_x in ((by_x, False), (by_y, True)):  # row axes, dotted
            for pts in rows.values():
                if len(pts) < 2:
                    continue
                pts_s, t0, t1 = ends(pts, along_x)
                if t0 and t1:
                    dx, dy = (1, 0) if along_x else (0, 1)
                    dashed((pts_s[0][0] - dx * t0, pts_s[0][1] - dy * t0),
                           (pts_s[-1][0] + dx * t1, pts_s[-1][1] + dy * t1), (140, 140, 140), 1, step=4)
        for rows, along_x in ((by_x, False), (by_y, True)):  # one chain per repeated set of positions
            best = {}
            for pts in rows.values():
                if len(pts) < 2:
                    continue
                sig = tuple(sorted(p[0] if along_x else p[1] for p in pts))
                _, t0, t1 = ends(pts, along_x)
                span = (t0 or 1e6) + (t1 or 1e6)
                if sig not in best or span < best[sig][0]:
                    best[sig] = (span, pts)
            for _, pts in best.values():
                chain(pts, along_x=along_x, offset=-20)
    for p in m.pendants:
        if inside(*p["at"]):
            chain([tuple(p["at"])], along_x=True, offset=-28, curtains=False, grow=False)  # a chandelier: its center
            chain([tuple(p["at"])], along_x=False, offset=-28, curtains=False, grow=False)
    return used


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--out", default="renders/plan")
    ap.add_argument("--only", choices=["furniture", "lights", "tiles"])
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    plan = json.loads(Path(args.plan).read_text()) if Path(args.plan).exists() else {"rooms": []}
    m = Model(cfg, plan)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    xs = [p[0] for w in m.walls.values() for p in (w.a, w.b)]
    ys = [p[1] for w in m.walls.values() for p in (w.a, w.b)]
    whole = (min(xs) - 25, max(xs) + 25, min(ys) - 25, max(ys) + 25)
    for mode, stem, title, edges in (("furniture", "furniture", "План мебели", False),
                                     ("lighting", "lights", "План освещения", False),
                                     ("lighting", "lights_edges", "План освещения по краям светильников", True),
                                     ("tiles", "tiles", "Раскладка плитки на полу", False)):
        if args.only and not stem.startswith(args.only[:5]):
            continue
        # the lighting sheet is drawn larger: wall lengths and lamp distances share the rooms
        sheet(m, whole, 2.4 if mode == "lighting" else 1.7, f"{title} — вся квартира", mode,
              edges=edges).save(out / f"{stem}.png")
        print(f"{stem}.png")
        for rid, name, poly in m.rooms:
            if mode == "tiles" and rid not in m.tiled_rooms:
                continue
            box = (min(p[0] for p in poly) - 25, max(p[0] for p in poly) + 25,
                   min(p[1] for p in poly) - 25, max(p[1] for p in poly) + 25)
            sheet(m, box, 3.0, f"{title} — {name}", mode, poly, edges).save(out / f"{stem}_{rid}.png")
            print(f"{stem}_{rid}.png")


if __name__ == "__main__":
    main()
