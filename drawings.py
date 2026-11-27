"""Чертежи по комнатам: для каждой комнаты — план с размерами и по листу на каждую стену (вид из комнаты и полоса плана
под ним, как «Зеркало» и «Полотенцесушитель»). На стенах — проёмы, мебель и сантехника, розетки и выключатели с номерами,
высотами и расстояниями от левого угла. Толщина плитки: на плане — слой плитки с клеем у стены и черновые размеры, на
стенах — плитка соседних стен в разрезе у углов и плитка пола, цепочки по плитке и по черновой стене. Всё в см.

    .venv/bin/python drawings.py                  # renders/Рендеры/Чертежи/<NN Комната>/<NN Лист>.png
    .venv/bin/python drawings.py --room bathroom  # одна комната

Данные: rooms/apartment.json (геометрия, мебель, электрика), plan.json (слой плитки, выводы кабеля, предложенные розетки).
"""
import argparse
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from plans import BOLD, FONT, FURNITURE_NAMES, Model, in_polygon, num
from tile_layout import PV

OUT = Path("renders/Рендеры/Чертежи")
PLANS = Path("renders/Рендеры/Планы")
INK, GREY, LIGHT, BLUE, RED = (30, 30, 30), (110, 105, 100), (175, 170, 165), (30, 90, 200), (200, 40, 40)
GREEN, ROUGH_INK = (30, 140, 80), (120, 120, 120)
WALL_BODY, WALL_FACE, FURN, FURN_EDGE = (95, 95, 95), (250, 248, 244), (240, 237, 232), (120, 112, 104)
SIDE, TILE_BAND, TILE_EDGE = (228, 228, 228), (222, 206, 176), (150, 130, 100)
GLASS, OPENING = (222, 236, 250), (255, 255, 255)
FRAME, PITCH = 8.3, 7.1          # AtlasDesign: frame 83 mm, 71 mm per extra post
CASING = 7
FLOOR_TILE = 1.5                 # floor tile with adhesive: assumed (plan.json finishes.floor.build_up)
SPLASH_TILE = 1.5                # backsplash: the floor tile with adhesive, as on the wet-room walls (assumed)
ROOM_ORDER = ["hall", "kitchen_living", "bedroom_1", "study", "bedroom_2", "bathroom", "toilet", "loggia_kitchen",
              "loggia_bedroom_1"]
ROOM_NAMES = {"hall": "Прихожая", "kitchen_living": "Кухня-гостиная", "bedroom_1": "Спальня 1", "study": "Кабинет",
              "bedroom_2": "Спальня 2", "bathroom": "Ванная", "toilet": "Туалет",
              "loggia_kitchen": "Лоджия кухни-гостиной", "loggia_bedroom_1": "Лоджия спальни 1"}
START = {"hall": "entrance", "kitchen_living": "kitchen"}      # the first sheet; elsewhere the wall with the door
WALL_NAMES = {"entrance": "Входная стена", "hall_right": "Правая стена", "hall_right_br1": "Правая стена — дверь в спальню 1",
              "hall_far": "Дальняя стена — двери в ванную и туалет",
              "hall_left": "Левая стена — двери в кабинет и спальню 2", "kitchen": "Кухонная стена",
              "tv": "Стена с ТВ", "window": "Стена с окном и дверью на лоджию", "sofa": "Стена с диваном и мойкой",
              "niche_step": "Ниша у входа — торец", "niche_side": "Ниша у входа — боковая", "pier_back": "Простенок у арки",
              "st_pocket_end": "Карман со шкафом-купе — дальняя стена",
              "st_pocket_side": "Карман со шкафом-купе — боковая стена",
              "lgk_room": "Стена кухни-гостиной — окно и дверь", "lgb_room": "Стена спальни 1 — окно и дверь"}
DOOR_TO = {"entrance": "входная дверь", "br1": "дверь в спальню 1", "bath": "дверь в ванную", "toilet": "дверь в туалет",
           "br2": "дверь в спальню 2", "study": "дверь в кабинет"}
EXTRA_SHEETS = {"hall": ["Развёртка — Прихожая, стена с зеркалом"],
                "bathroom": ["Зеркало — Ванная", "Полотенцесушитель — Ванная", "Каркас короба — Ванная"],
                "toilet": ["Зеркало — Туалет", "Полотенцесушитель — Туалет", "Каркас короба — Туалет",
                           "Короб с бойлером — Туалет"]}
NAMES = {**FURNITURE_NAMES, "tv": "ТВ", "mirror": "зеркало", "radiator": "радиатор", "air_conditioner": "кондиционер",
         "intercom": "домофон", "towel_warmer": "полотенцесушитель", "basin_top": "раковина", "bath_mixer": "смеситель",
         "bidet_shower": "гиг. душ", "appliance_column": "колонна стирки и сушки", "desk": "стол",
         "drawer_unit": "тумба", "swing_wardrobe": "шкаф"}
BASE_NAMES = {"blind": "угловой", "filler": "", "door": "дверка", "drawers": "ящики", "oven": "духовка + варка",
              "sink": "мойка"}
UPPER_NAMES = {"door": "дверка", "doors2": "2 дверки", "microwave": "СВЧ", "hood": "вытяжка", "filler": "", "end": "торец"}


MOUNT_BAND = (5, 15)   # a backlit mirror's wall brackets usually sit this far below its top edge (model not chosen)
NO_DRILL = 3           # drill holes keep this far from a tile joint


def mirror_mounts(d, a, b, z0, z1, Z, sc):
    """Over a mirror on a tiled wall (pixel columns a..b, heights z0..z1): the usual band of its brackets (blue,
    dashed) and each tile joint behind it with ±NO_DRILL where not to drill (red hatching). Returns the boxes used."""
    boxes = []
    for k in range(1, 6):
        zj = k * PV
        if not z0 - NO_DRILL < zj < z1 + NO_DRILL:
            continue
        y0, y1 = Z(zj + NO_DRILL), Z(zj - NO_DRILL)
        h = y1 - y0
        x = a - h
        while x < b:
            xs0, xs1 = max(x, a), min(x + h, b)
            d.line([xs0, y1 - (xs0 - x), xs1, y1 - (xs1 - x)], fill=(225, 120, 120), width=1)
            x += 9
        d.line([a, Z(zj), b, Z(zj)], fill=RED, width=2)
        t = f"шов {num(zj)}: не сверлить {num(zj - NO_DRILL)}–{num(zj + NO_DRILL)}"
        f = font(14)
        if f.getlength(t) + 8 > b - a:
            t = f"шов {num(zj)} ±{NO_DRILL}"
        tb = d.textbbox(((a + b) / 2, y1 + 11), t, font=f, anchor="mm")
        d.rectangle([tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2], fill="white")
        d.text(((a + b) / 2, y1 + 11), t, fill=RED, font=f, anchor="mm")
        boxes += [(a, y0, b, y1), (tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2)]
    ya, yb = Z(z1 - MOUNT_BAND[0]), Z(z1 - MOUNT_BAND[1])
    xa, xb = a + 5 * sc, b - 5 * sc
    for (p0, p1) in (((xa, ya), (xb, ya)), ((xb, ya), (xb, yb)), ((xb, yb), (xa, yb)), ((xa, yb), (xa, ya))):
        n = max(abs(p1[0] - p0[0]), abs(p1[1] - p0[1]))
        k = 0.0
        while k < n:
            e = min(k + 8, n)
            d.line([p0[0] + (p1[0] - p0[0]) * k / n, p0[1] + (p1[1] - p0[1]) * k / n,
                    p0[0] + (p1[0] - p0[0]) * e / n, p0[1] + (p1[1] - p0[1]) * e / n], fill=BLUE, width=2)
            k += 13
    t = f"крепления ~{num(z1 - MOUNT_BAND[1])}–{num(z1 - MOUNT_BAND[0])}"
    tb = d.textbbox(((xa + xb) / 2, (ya + yb) / 2), t, font=font(14), anchor="mm")
    d.rectangle([tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2], fill="white")
    d.text(((xa + xb) / 2, (ya + yb) / 2), t, fill=BLUE, font=font(14), anchor="mm")
    boxes += [(xa, ya, xb, yb)]
    return boxes


MOUNT_NOTE = ("Крепления зеркала: модель не выбрана — синим пунктиром обычная зона кронштейнов (5–15 ниже верха "
              "зеркала), красной штриховкой — швы плитки за зеркалом и по 3 см от них, там не сверлить. Точные точки — по "
              "шаблону выбранного зеркала; если отверстие попадает в штриховку, зеркало сдвинуть на 2–3 см.")


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


def wrap(text, f, width):
    lines, line = [], ""
    for w in text.split():
        if line and f.getlength(line + " " + w) > width:
            lines.append(line)
            line = w
        else:
            line = (line + " " + w).strip()
    return lines + [line]


# ------------------------------------------------------------------ data ------------------------------------------------

class Item:
    """Something standing at or hanging on a wall: along the wall s0..s1, out from it d0..d1, from the floor z0..z1."""

    def __init__(self, wall, s0, s1, d0, d1, z0, z1, label="", size="", kind="furniture", lines=()):
        self.wall, self.s0, self.s1, self.d0, self.d1, self.z0, self.z1 = wall, s0, s1, d0, d1, z0, z1
        self.label, self.size, self.kind, self.lines = label, size, kind, lines   # lines: heights of inner joints

    def poly(self):
        w = self.wall
        return [w.pt(self.s0, self.d0), w.pt(self.s1, self.d0), w.pt(self.s1, self.d1), w.pt(self.s0, self.d1)]


class Point:
    """An electrical point on a wall: a frame of posts, a sconce, a cable outlet."""

    def __init__(self, wall, posts, kind, keys=1, note="", color=BLUE, d=0.0):
        self.wall, self.posts, self.kind, self.keys, self.note, self.color, self.d = wall, posts, kind, keys, note, color, d
        # posts: [(s, z, what)], what: switch | outlet | outlet_ip44 | data | sconce | cable

    @property
    def s(self):
        return sum(p[0] for p in self.posts) / len(self.posts)

    @property
    def z(self):
        return sum(p[1] for p in self.posts) / len(self.posts)


def items_of(cfg, m, height):
    """Every Item in plan terms, from apartment.json furniture and the kitchen."""
    out = []
    for it in cfg["furniture"]:
        t, w = it["type"], m.walls.get(it.get("wall"))
        if w is None or "span" not in it or t in ("curtains", "ceiling_fan", "desk_gear", "chair", "office_chair",
                                                  "appliance"):
            continue
        H = height(w)
        s0, s1 = sorted(w.s(c) for c in it["span"])
        gap = it.get("gap", 0)
        dflt = {"wardrobe": 60, "cabinet": 30, "sofa": 95, "tv": 3, "intercom": 2.7, "radiator": 9, "niche_cabinet": 36.7,
                "pouf": 35, "mirror": 2, "swing_wardrobe": 60, "drawer_unit": 40, "bed": 215, "air_conditioner": 20,
                "desk": 80, "bathtub": 80, "towel_warmer": 7, "appliance_column": 60}
        depth = it.get("depth", dflt.get(t, 10))
        z0, z1, lines = it.get("elevation", 0), None, ()
        label, size = it.get("label", NAMES.get(t, t)), f"{num(s1 - s0)} × {num(depth)}"
        if t in ("wardrobe", "niche_cabinet", "appliance_column"):
            z1 = H if it.get("height", "ceiling") == "ceiling" else it["height"]
            if t == "niche_cabinet":
                label = "пенал" if depth <= 30 else "шкаф в нише"
                lines = tuple(sec["z"][1] for sec in it.get("sections", []) if sec["z"][1] != "ceiling")
            if t == "appliance_column":
                lines = (it.get("niche_height", 174),)
        elif t == "swing_wardrobe":
            carcass = it.get("height", 250)
            z1, lines = H, (carcass,)                   # the filler runs to the ceiling
            size = f"{num(s1 - s0)} × {num(depth)}, корпус {num(carcass)} + добор"
        elif t == "bed":
            z1, size = 110, f"{num(s1 - s0)} × {num(depth)}, изголовье ~110"
        elif t == "sofa":
            z1 = it.get("back_height", 85)
        elif t == "desk":
            z1 = it.get("height", 75)
        elif t == "pouf":
            z1 = it.get("height", 42)
        elif t == "bathtub":
            z1, size = it.get("height", 60), f"{num(s1 - s0)} × {num(depth)}, борт {num(it.get('height', 60))}"
        elif t == "wall_toilet":
            z0, z1, size = 7, it["seat_height"], f"сиденье {num(it['seat_height'])}"
            pz, (pw, ph) = it["plate"]["z"], it["plate"]["size"]
            c = (s0 + s1) / 2
            out.append(Item(w, c - pw / 2, c + pw / 2, gap, gap + 1, pz - ph / 2, pz + ph / 2, "", "", "small"))
        elif t == "tiled_box":
            z1, label = it["height"], "короб"
            size = f"{num(s1 - s0)} × {num(depth)}, h {num(it['height'])}"
        elif t == "basin_top":
            z0, z1, label, size = it["height"] - it.get("thickness", 4), it["height"], "раковина", f"верх {num(it['height'])}"
        elif t == "bath_mixer":
            z = it["z"]
            out.append(Item(w, s0, s1, 0, 6, z - 3, z + 3, "смеситель", f"на {num(z)}", "small"))
            rain = it.get("rain")
            if rain:
                c = (s0 + s1) / 2
                out.append(Item(w, c - 1, c + 1, 3, 5, z + 3, rain[0], "", "", "pipe"))
                out.append(Item(w, c - rain[2] / 2, c + rain[2] / 2, 3, rain[1], rain[0] - 1.5, rain[0] + 0.5,
                                "тропическая лейка", f"Ø{num(rain[2])}, на {num(rain[0])}", "small"))
            continue
        elif t == "bidet_shower":
            z = it["z"]
            out.append(Item(w, s0, s1, gap, gap + 3, z - 3, z + 3, "гиг. душ", f"вывод на {num(z)}", "small"))
            continue
        else:   # cabinet, drawer_unit, tv, mirror, radiator, air_conditioner, intercom, towel_warmer
            hd = {"cabinet": 45, "drawer_unit": 46, "tv": 81, "mirror": 90, "radiator": 57.7, "air_conditioner": 28,
                  "intercom": 12.7, "towel_warmer": 80}
            zd = {"cabinet": 35, "tv": 75, "mirror": 100, "radiator": 10, "air_conditioner": 227, "intercom": 153}
            z0 = it.get("elevation", zd.get(t, 0))
            z1 = z0 + it.get("height", hd.get(t, 40))
            if t == "cabinet" and it.get("label"):
                label = it["label"].split(" + ")[0]
            if t in ("mirror", "tv", "towel_warmer", "radiator", "air_conditioner", "intercom"):
                size = f"{num(s1 - s0)} × {num(z1 - z0)}"
            if t == "drawer_unit" or (t == "cabinet" and it.get("drawers")):
                n = it.get("drawers", 2)
                lines = tuple(z0 + (z1 - z0) * k / n for k in range(1, n))
        out.append(Item(w, s0, s1, gap, gap + depth, z0, z1, label, size,
                        "glass" if t == "mirror" else "tile" if t == "tiled_box" else "furniture", lines))

    k = cfg.get("kitchen") or {}
    if k:
        top, ct, plinth, dep = k["base_top"], k["countertop_thickness"], k["plinth"], k["depth"]
        runs = {}
        for b in k["base"]:
            w = m.walls[b["wall"]]
            s0, s1 = sorted(w.s(c) for c in b["span"])
            runs.setdefault(w.id, []).append((s0, s1))
            out.append(Item(w, s0, s1, 0, dep, plinth, top - ct, BASE_NAMES.get(b["type"], ""),
                            f"{num(s1 - s0)}" if s1 - s0 >= 20 else "", "kitchen"))
        for t in k.get("tall", []):
            w = m.walls[t["wall"]]
            s0, s1 = sorted(w.s(c) for c in t["span"])
            out.append(Item(w, s0, s1, 0, dep, 0, height(w), "холодильник", f"встроенный, {num(s1 - s0)}", "kitchen",
                            tuple(t.get("splits", ()))))
            runs.setdefault(w.id, []).append((s0, s1))
        for wid, spans in runs.items():   # the plinth along each run
            w = m.walls[wid]
            out.append(Item(w, min(s[0] for s in spans), max(s[1] for s in spans), 0, dep - 5, 0, plinth, "", "",
                            "plinth"))
        for wid in {b["wall"] for b in k["base"]}:
            w = m.walls[wid]
            sp = [sorted(w.s(c) for c in b["span"]) for b in k["base"] if b["wall"] == wid]
            out.append(Item(w, min(s[0] for s in sp), max(s[1] for s in sp), 0, dep + 2, top - ct, top,
                            "столешница", f"верх {num(top)}", "counter"))
        up = k.get("upper") or {}
        ub, tiers, ud = up.get("bottom", 151), up.get("tiers", [80]), up.get("depth", 35)
        for u in k.get("upper_modules", []):
            w = m.walls[u["wall"]]
            s0, s1 = sorted(w.s(c) for c in u["span"])
            out.append(Item(w, s0, s1, 0, ud, ub, ub + sum(tiers), UPPER_NAMES.get(u["type"], ""), "", "kitchen",
                            (ub + tiers[0],) if len(tiers) > 1 else ()))
        for bs in k.get("backsplash", []):
            w = m.walls[bs["wall"]]
            s0, s1 = sorted(w.s(c) for c in bs["span"])
            out.append(Item(w, s0, s1, -SPLASH_TILE, 0, top, ub, "фартук — плитка", f"{num(top)}–{num(ub)}", "splash"))
    return out


def points_of(cfg, plan, m, items):
    """Electrical points per wall: apartment.json electrical and wall lights; from plan.json the mirror cable outlets,
    and sockets proposed there but not built yet."""
    out = []
    for e in cfg.get("electrical", []):
        w = m.walls[e["wall"]]
        kinds = e.get("posts") or [e["type"]] * len(e["centers"])
        if e.get("vertical"):
            s = w.s(e["centers"][0])
            posts = [(s, e["z"] - k * PITCH, kd) for k, kd in enumerate(kinds)]
        else:
            posts = sorted(((w.s(c), e["z"], kd) for c, kd in zip(e["centers"], kinds)), key=lambda p: p[0])
        out.append(Point(w, posts, e["type"], e.get("keys", 1), d=e.get("d", 0)))
    for wl in cfg.get("wall_lights", []):
        w = m.walls[wl["wall"]]
        for c in wl["centers"]:
            out.append(Point(w, [(w.s(c), wl["z"], "sconce")], "sconce", note="бра"))
    rooms = {r["id"]: r for r in plan["rooms"]}
    mirrors = {it["wall"]: it for it in cfg["furniture"] if it["type"] == "mirror"}
    for rid, mir in (("bathroom", (rooms["bathroom"].get("furniture") or {}).get("mirror")),
                     ("toilet", rooms["toilet"].get("mirror"))):
        pw = (mir or {}).get("power")
        if not pw:
            continue
        wid = next(wd for wd in mirrors if wd.startswith("bath" if rid == "bathroom" else "toilet"))
        w = m.walls[wid]
        out.append(Point(w, [(w.s(pw["y"]), pw["z"], "cable")], "cable", note="вывод кабеля зеркала, без коробки",
                         color=RED))
    for it in cfg["furniture"]:   # towel warmers: the cable at the connection end, 5 above the bottom (assumed)
        if it["type"] != "towel_warmer":
            continue
        w = m.walls[it["wall"]]
        s0, s1 = sorted(w.s(c) for c in it["span"])
        right = s0          # seen from the room s runs right to left: the right-hand end is the smaller s
        end = right if it.get("connection", "right") == "right" else s1
        s = end + (1.5 if end == s0 else -1.5)
        how = "подрозетник под плиткой, в плитке отверстие ~Ø12; "   # plan.json towel_warmer.cable_outlet
        out.append(Point(w, [(s, it["elevation"] + 5, "cable")], "cable",
                         note=f"вывод кабеля полотенцесушителя ({how}место сверить с паспортом)", color=RED))
    known = [(p.wall.pt(p.s, p.d), p.z) for p in out]
    for o in plan.get("outlets", {}).get("items", []):   # proposed in plan.json, not in the 3D model yet
        x, y, z = o.get("x"), o.get("y"), o.get("z")
        if not all(isinstance(v, (int, float)) for v in (x, y, z)):
            continue
        w = min(m.walls.values(), key=lambda w: abs((x - w.a[0]) * w.n[0] + (y - w.a[1]) * w.n[1])
                + (0 if -1 <= (x - w.a[0]) * w.u[0] + (y - w.a[1]) * w.u[1] <= w.len + 1 else 1e6))
        s = (x - w.a[0]) * w.u[0] + (y - w.a[1]) * w.u[1]
        if any(math.dist(k[0], (x, y)) < 6 and abs(k[1] - z) < 6 for k in known):
            continue
        out.append(Point(w, [(s, z, "outlet")], "outlet", note="предложено, не решено" if "assumed" in o.get("status", "")
                         else "", color=GREEN))
    return out


# ------------------------------------------------------------------ drawing helpers ------------------------------------

class Canvas:
    def __init__(self, w, h):
        self.img = Image.new("RGB", (int(w), int(h)), "white")
        self.d = ImageDraw.Draw(self.img)

    def text(self, xy, lines, size=19, fill=INK, anchor="mm", bold_first=False, bg=None):
        x, y = xy
        if isinstance(lines, str):
            lines = [lines]
        y -= (len(lines) - 1) * (size + 7) / 2 if anchor[1] == "m" else 0
        for k, t in enumerate(lines):
            f = font(size, bold_first and k == 0)
            if bg:
                tb = self.d.textbbox((x, y), t, font=f, anchor=anchor)
                self.d.rectangle([tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2], fill=bg)
            self.d.text((x, y), t, fill=fill, font=f, anchor=anchor)
            y += size + 7

    def vtext(self, x, y, t, size=19, fill=INK, bg=(255, 255, 255, 255)):
        f = font(size)
        im = Image.new("RGBA", (int(f.getlength(t)) + 10, size + 10), bg)
        ImageDraw.Draw(im).text((im.width / 2, im.height / 2), t, fill=fill, font=f, anchor="mm")
        im = im.rotate(90, expand=True)
        self.img.paste(im, (int(x - im.width / 2), int(y - im.height / 2)), im)

    def tick(self, x, y, color):
        self.d.line([x - 6, y + 6, x + 6, y - 6], fill=color, width=3)

    def chain_h(self, xs, at, ext, color=INK, labels=None, size=18):
        """Dimension chain at pixel row `at` through pixel columns xs (ascending); extension lines from rows ext."""
        ext = ext if isinstance(ext, list) else [ext] * len(xs)
        for x, f in zip(xs, ext):
            if f is not None:
                self.d.line([x, f, x, at + (8 if at > f else -8)], fill=LIGHT, width=1)
            self.tick(x, at, color)
        self.d.line([xs[0] - 10, at, xs[-1] + 10, at], fill=color, width=2)
        f = font(size)
        prev_right = -1e9
        for k, (a, b) in enumerate(zip(xs, xs[1:])):
            t = labels[k] if labels else None
            if t is None or t == "":
                continue
            w = f.getlength(t)
            c = (a + b) / 2
            y = at - 14
            if w + 6 > b - a or c - w / 2 < prev_right + 4:   # no room between the ticks: under the line
                y = at + 16 + 20 * (k % 2)
            self.d.text((c, y), t, fill=color, font=f, anchor="mm")
            prev_right = c + w / 2 if y == at - 14 else prev_right

    def chain_v(self, ys, at, ext, color=INK, labels=None, size=18):
        """Vertical chain at pixel column `at` through pixel rows ys (descending heights = ascending rows)."""
        ext = ext if isinstance(ext, list) else [ext] * len(ys)
        for y, f in zip(ys, ext):
            if f is not None:
                self.d.line([f, y, at + (8 if at > f else -8), y], fill=LIGHT, width=1)
            self.tick(at, y, color)
        self.d.line([at, min(ys) - 10, at, max(ys) + 10], fill=color, width=2)
        for k, (a, b) in enumerate(zip(ys, ys[1:])):
            t = labels[k] if labels else None
            if not t:
                continue
            off = -16 if abs(b - a) > font(size).getlength(t) + 6 else -16 - 20 * (1 + k % 2)
            self.vtext(at + off, (a + b) / 2, t, size, color)


# ------------------------------------------------------------------ one wall --------------------------------------------

def neighbours(outline_walls, w):
    """The walls meeting w at its start and end, and whether each corner is an inside one (the neighbour comes toward
    the viewer, so it is cut in the elevation)."""
    prev = next((v for v in outline_walls if math.dist(v.b, w.a) < 0.5), None)
    nxt = next((v for v in outline_walls if math.dist(v.a, w.b) < 0.5), None)

    def inside(p, q):   # a left turn from p to q keeps the room inside: an inside corner
        return p is not None and q is not None and (p.u[0] * q.u[1] - p.u[1] * q.u[0]) > 0.3
    return (prev, inside(prev, w)), (nxt, inside(w, nxt))


def wall_sheet(m, w, room, idx, title, items, points, cfg, H, tiles, floor_tile, out):
    """Elevation of wall w seen from the room with a plan strip under it."""
    L = w.len
    SC = min(4.0, 1700 / max(L, 1))
    room_walls = room["walls"]
    (prev, prev_in), (nxt, nxt_in) = neighbours(room_walls, w)
    t_end0 = tiles.get(prev.id, 0) if prev is not None and prev_in else 0   # the side tile at s = 0 (right on the sheet)
    t_end1 = tiles.get(nxt.id, 0) if nxt is not None and nxt_in else 0     # at s = L (left on the sheet)
    t_self = tiles.get(w.id, 0)

    front = [it for it in items if it.wall is w]
    side = []
    for it in items:
        if it.wall is w or it.wall.id not in {v.id for v in room_walls} or it.kind in ("plinth", "splash"):
            continue
        pts = [((p[0] - w.a[0]) * w.u[0] + (p[1] - w.a[1]) * w.u[1], (p[0] - w.a[0]) * w.n[0] + (p[1] - w.a[1]) * w.n[1])
               for p in it.poly()]
        ss, dd = [p[0] for p in pts], [p[1] for p in pts]
        if min(dd) <= 2.5 and max(dd) > 2.5 and min(ss) < L - 0.5 and max(ss) > 0.5 and \
                abs(it.wall.u[0] * w.u[0] + it.wall.u[1] * w.u[1]) < 0.2:
            side.append((max(0, min(ss)), min(L, max(ss)), it))
    pts_here = sorted([p for p in points if p.wall is w], key=lambda p: -p.s)   # left to right on the sheet

    el_z = sorted({round(p.z, 2) for p in pts_here})
    LEFT = 330
    right_w = max(330, 70 + 52 * len(el_z) + 60)
    Wpx = LEFT + L * SC + right_w
    Wpx = max(Wpx, 1100)
    R = LEFT + L * SC
    TOP = 230
    EB = TOP + H * SC
    depth = max([it.d1 for it in front if it.kind not in ("splash",)] + [40])
    D = min(max(depth + 25, 60), 170)
    chains = 4 + (1 if pts_here else 0)
    PT = EB + 70 + 64 * chains
    t_wall = w.t
    d_min = -(t_wall + 8)
    PB = PT + (D - d_min) * SC
    cv = Canvas(Wpx, PB + 900)
    d = cv.d

    def X(s):
        return LEFT + (L - s) * SC

    def Z(z):
        return TOP + (H - z) * SC

    def xs(a, b):
        return sorted((X(a), X(b)))

    cv.text((LEFT, 40), [title], 34, INK, "lm", True)
    cv.text((LEFT, 90), ["вид на стену из комнаты и полоса плана под ним;",
                         "размеры по чистовой отделке (по плитке), высоты от чистового пола, см"], 20, GREY, "lm")

    # ---- elevation: the wall, the neighbours cut at the corners, the floor
    d.rectangle([X(L), Z(H), X(0), Z(0)], fill=WALL_FACE, outline=INK, width=3)
    for s_at, t_tile, nb, inside in ((0, t_end0, prev, prev_in), (L, t_end1, nxt, nxt_in)):
        if nb is None or not inside:
            continue
        sign = -1 if s_at == 0 else 1          # outward along the wall, past the corner
        body = nb.t
        a0, a1 = s_at + sign * t_tile, s_at + sign * (t_tile + min(body, 10))
        if t_tile:
            x0, x1 = xs(s_at, a0)
            d.rectangle([x0, Z(H), x1, Z(0)], fill=TILE_BAND, outline=TILE_EDGE, width=1)
        x0, x1 = xs(a0, a1)
        d.rectangle([x0, Z(H), x1, Z(0)], fill=WALL_BODY)
    if floor_tile:
        d.rectangle([X(L), Z(0), X(0), Z(-floor_tile)], fill=TILE_BAND, outline=TILE_EDGE, width=1)
        d.rectangle([X(L), Z(-floor_tile), X(0), Z(-floor_tile - 5)], fill=(200, 200, 200))
    else:
        d.rectangle([X(L), Z(0), X(0), Z(-5)], fill=(200, 200, 200))
    if t_self:
        cv.text(((X(L) + X(0)) / 2, Z(H) + 22), [f"плитка с клеем {num(t_self)} по всей стене"], 16, TILE_EDGE,
                bg=WALL_FACE)

    # openings: doors (opening and casing) and windows (sashes, sill)
    opens = []
    for dr in cfg["doors"]:
        dw = m.walls[dr["wall"]]
        if dw is not w and not (abs(dw.u[0] * w.u[0] + dw.u[1] * w.u[1]) > 0.999 and
                                abs((dw.a[0] - w.a[0]) * w.n[0] + (dw.a[1] - w.a[1]) * w.n[1]) < 45):
            continue
        s0, s1 = sorted(w.s(c) for c in dr["span"])
        if s1 < 0.5 or s0 > L - 0.5:
            continue
        s0, s1 = max(0.0, s0), min(L, s1)
        oh = dr.get("opening_height", 217)
        own = dw is w
        casing = own or dr.get("far_casing") is not None
        if casing:
            a, b = xs(s0 - CASING, s1 + CASING)
            d.rectangle([a, Z(oh + CASING), b, Z(0)], fill=(246, 246, 244), outline=GREY, width=2)
        a, b = xs(s0, s1)
        d.rectangle([a, Z(oh), b, Z(0)], fill=OPENING, outline=INK, width=2)
        who = DOOR_TO.get(dr["id"], "дверь") if own else "дверь в прихожую"
        cv.text(((a + b) / 2, Z(oh * 0.62)), [who, f"проём {num(s1 - s0)} × {num(oh)}"] +
                ([f"наличник {CASING}"] if casing else []), 17, GREY)
        opens.append((s0, s1, 0, oh, casing))
    for win in cfg.get("windows", []):
        ww = m.walls[win["wall"]]
        if ww is not w and not (abs(ww.u[0] * w.u[0] + ww.u[1] * w.u[1]) > 0.999 and
                                abs((ww.a[0] - w.a[0]) * w.n[0] + (ww.a[1] - w.a[1]) * w.n[1]) < 45):
            continue
        parts = [([max(0.0, a), min(L, b)], p["z"], p) for (a, b), p in
                 ((sorted(w.s(c) for c in p["span"]), p) for p in win["parts"])]
        parts = [q for q in parts if q[0][1] - q[0][0] > 0.5]
        if not parts:
            continue
        for (s0, s1), (z0, z1), p in parts:
            a, b = xs(s0, s1)
            d.rectangle([a, Z(z1), b, Z(z0)], fill=GLASS if p["type"] == "window" else (236, 244, 252),
                        outline=(90, 140, 200), width=2)
            sill = p.get("sill")
            if sill and ww is w:
                q0, q1 = sorted(w.s(c) for c in sill["span"])
                a2, b2 = xs(q0, q1)
                d.rectangle([a2, Z(z0), b2, Z(z0 - 3)], fill=(246, 246, 244), outline=GREY, width=2)
        s0 = min(p[0][0] for p in parts)
        s1 = max(p[0][1] for p in parts)
        z0 = min(p[1][0] for p in parts)
        z1 = max(p[1][1] for p in parts)
        doors = [p for p in parts if p[2]["type"] == "door"]
        wins = [p for p in parts if p[2]["type"] == "window"]
        if wins:
            ws0, ws1 = min(p[0][0] for p in wins), max(p[0][1] for p in wins)
            wz0, wz1 = min(p[1][0] for p in wins), max(p[1][1] for p in wins)
            a, b = xs(ws0, ws1)
            cv.text(((a + b) / 2, Z((wz0 + wz1) / 2)), ["окно", f"{num(ws1 - ws0)} × {num(wz1 - wz0)}",
                                                         f"низ {num(wz0)}"], 17, (60, 100, 160), bg=GLASS)
            opens.append((ws0, ws1, wz0, wz1, False))
        for (q0, q1), (qz0, qz1), p in doors:
            a, b = xs(q0, q1)
            cv.text(((a + b) / 2, Z((qz0 + qz1) / 2)), ["балконная", "дверь", f"{num(q1 - q0)} × {num(qz1 - qz0)}"],
                    17, (60, 100, 160), bg=(236, 244, 252))
            opens.append((q0, q1, qz0, qz1, False))

    # items: neighbours' ends first (cut), then this wall's, big ones under small ones
    for a0, a1, it in side:
        a, b = xs(a0, a1)
        d.rectangle([a, Z(it.z1), b, Z(it.z0)], fill=SIDE, outline=LIGHT, width=2)
        if b - a > 40 and (it.z1 - it.z0) * SC > 40 and it.label:
            cv.vtext((a + b) / 2, Z((it.z0 + it.z1) / 2), f"{it.label} (сбоку)", 15, GREY, (0, 0, 0, 0))
    fills = {"glass": (214, 226, 232), "tile": (234, 226, 212), "counter": (110, 106, 102),
             "plinth": (150, 145, 140), "pipe": (190, 192, 196), "small": (225, 225, 225)}
    rects = {}
    for it in sorted(front, key=lambda it: -(it.s1 - it.s0) * (it.z1 - it.z0)):
        a, b = xs(it.s0, it.s1)
        rects[id(it)] = (a, Z(it.z1), b, Z(it.z0))
        if it.kind == "splash":
            d.rectangle([a, Z(it.z1), b, Z(it.z0)], fill=TILE_BAND, outline=TILE_EDGE, width=1)
            continue
        d.rectangle([a, Z(it.z1), b, Z(it.z0)], fill=fills.get(it.kind, FURN), outline=FURN_EDGE, width=2)
        for zl in it.lines:
            if it.z0 < zl < it.z1:
                d.line([a, Z(zl), b, Z(zl)], fill=FURN_EDGE, width=1)
    obstacles = []      # electrical frames and badges, then each placed label
    mounts = False
    if t_self:          # mirrors on tile: where their brackets usually go, the joints not to drill at
        for it in front:
            if it.kind == "glass":
                a, top, b, bot = rects[id(it)]
                obstacles += mirror_mounts(d, a, b, it.z0, it.z1, Z, SC)
                mounts = True

    # electrical: frames, numbered
    legend = []
    for n, p in enumerate(pts_here, 1):
        col = p.color
        if p.kind in ("sconce", "cable"):
            x, y = X(p.posts[0][0]), Z(p.posts[0][1])
            r = 13 if p.kind == "cable" else 10
            d.ellipse([x - r, y - r, x + r, y + r], fill="white", outline=col, width=4)
            if p.kind == "cable":
                d.line([x - 8, y - 8, x + 8, y + 8], fill=col, width=3)
                d.line([x - 8, y + 8, x + 8, y - 8], fill=col, width=3)
            else:
                d.ellipse([x - 4, y - 4, x + 4, y + 4], fill=col)
            bx, by = x + r + 4, y - 24
            obstacles.append((x - r, y - r, x + r, y + r))
        else:
            ss, zz = [q[0] for q in p.posts], [q[1] for q in p.posts]
            a, b = xs(max(ss) + FRAME / 2, min(ss) - FRAME / 2)
            top, bot = Z(max(zz) + FRAME / 2), Z(min(zz) - FRAME / 2)
            d.rounded_rectangle([a, top, b, bot], 5, fill="white", outline=col, width=3)
            for s, z, what in p.posts:
                x, y = X(s), Z(z)
                r = 5.6 / 2 * SC
                if what == "switch":
                    kw = 2 * r / p.keys
                    for i in range(p.keys):
                        d.rectangle([x - r + i * kw + 2, y - r, x - r + (i + 1) * kw - 2, y + r], outline=GREY, width=1)
                elif what == "data":
                    d.rectangle([x - r * 0.5, y - r * 0.4, x + r * 0.5, y + r * 0.4], outline=GREY, width=2)
                else:
                    d.ellipse([x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7], outline=GREY, width=2)
            bx, by = b + 4, top - 22
            obstacles.append((a, top, b, bot))
        d.ellipse([bx, by, bx + 24, by + 24], fill=col)
        obstacles.append((bx, by, bx + 24, by + 24))
        d.text((bx + 12, by + 12), str(n), fill="white", font=font(16, True), anchor="mm")
        kinds = [q[2] for q in p.posts]
        what = {"sconce": "бра (вывод)", "cable": p.note}.get(p.kind)
        if what is None:
            parts = []
            for kd, nm in (("switch", f"выключатель {p.keys}-клав."), ("outlet", "розетка"),
                           ("outlet_ip44", "розетка IP44 с крышкой"), ("data", "интернет")):
                c = kinds.count(kd)
                if c:
                    parts.append(nm if c == 1 else f"{nm} ×{c}")
            what = " + ".join(parts) + (" (вертикальная рамка)" if len(p.posts) > 1 and p.posts[0][0] == p.posts[-1][0]
                                         else "")
            if p.note:
                what += f" — {p.note}"
            if p.d:
                what += f"; на лице {'фартука' if p.d < 3 else 'короба'} ({num(p.d)} от стены)"
        cs = sorted({round(L - q[0], 1) for q in p.posts})
        where = (f"центр на {num(p.z)}, от левого угла {num(L - p.s)}" +
                 (f" (посты {', '.join(num(c) for c in cs)})" if len(cs) > 1 else ""))
        legend.append((n, col, f"{what}: {where}"))

    # item labels: inside the item where nothing smaller lies over it, else just above or below it
    def hit(box, boxes):
        return any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in boxes)

    def area(it):
        return (it.s1 - it.s0) * (it.z1 - it.z0)
    f16 = font(16)
    for it in sorted(front, key=area):
        lab = [t for t in (it.label, it.size) if t]
        if not lab or it.kind in ("counter", "plinth", "pipe", "splash"):
            continue
        a, top, b, bot = rects[id(it)]
        tw, th = max(f16.getlength(t) for t in lab) + 10, 23 * len(lab) + 4
        over = [rects[id(o)] for o in front if o is not it and area(o) < area(it) and o.kind != "plinth"]
        spot = None
        if b - a >= tw and bot - top >= th and it.kind != "small":
            y = top + 10 + th / 2
            while y + th / 2 <= bot - 6:
                box = ((a + b - tw) / 2, y - th / 2, (a + b + tw) / 2, y + th / 2)
                if not hit(box, over + obstacles):
                    spot = ((a + b) / 2, y, fills.get(it.kind, FURN) if it.kind != "glass" else (214, 226, 232), INK)
                    break
                y += 12
        if spot is None:   # outside it: above, below, right, left; what it hangs on (a box face) does not count
            others = [r for k2, r in rects.items() if k2 != id(it) and not
                      (r[0] <= a and r[1] <= top and r[2] >= b and r[3] >= bot)]
            for cx, y in (((a + b) / 2, top - 8 - th / 2), ((a + b) / 2, bot + 8 + th / 2),
                          (b + 8 + tw / 2, (top + bot) / 2), (a - 8 - tw / 2, (top + bot) / 2)):
                box = (cx - tw / 2, y - th / 2, cx + tw / 2, y + th / 2)
                if not hit(box, others + obstacles) and TOP < y < EB and LEFT < box[0] and box[2] < R:
                    spot = (cx, y, "white", GREY)
                    break
        if spot is None:
            continue
        cv.text((spot[0], spot[1]), lab, 16, spot[3], bg=spot[2])
        obstacles.append(((spot[0] - tw / 2), spot[1] - th / 2, spot[0] + tw / 2, spot[1] + th / 2))

    for it in front:   # the backsplash: its name in a free stretch of the band
        if it.kind != "splash":
            continue
        a, top, b, bot = rects[id(it)]
        t = f"фартук — плитка с клеем ≈{num(SPLASH_TILE)}"
        tw = f16.getlength(t) + 10
        y = (top + bot) / 2
        cx = a + 10 + tw / 2
        while cx + tw / 2 < b - 6:
            box = (cx - tw / 2, y - 12, cx + tw / 2, y + 12)
            if not hit(box, obstacles):
                cv.text((cx, y), [t], 16, TILE_EDGE, bg=TILE_BAND)
                obstacles.append(box)
                break
            cx += 20

    # ---- chains under the elevation
    row = EB + 70
    marks = {0.0, round(L, 1)}
    for s0, s1, *_ in opens:
        marks |= {round(max(0, s0), 1), round(min(L, s1), 1)}
    for it in front:
        if it.kind not in ("small", "pipe", "plinth", "counter", "splash") and it.s1 - it.s0 > 3:
            marks |= {round(it.s0, 1), round(it.s1, 1)}
    ms = sorted(marks, reverse=True)       # left to right on the sheet
    cv.chain_h([X(s) for s in ms], row, Z(0), INK, [num(a - b) for a, b in zip(ms, ms[1:])])
    cv.text((LEFT - 14, row), ["по стене"], 16, GREY, "rm")
    row += 64
    if pts_here:
        ps = [L] + sorted({round(p.s, 2) for p in pts_here}, reverse=True)
        ext = [Z(0)] + [None] * (len(ps) - 1)
        cv.chain_h([X(s) for s in ps], row, ext, BLUE, [num(a - b) for a, b in zip(ps, ps[1:])])
        for s in ps[1:]:
            d.line([X(s), row + 8, X(s), Z(0)], fill=(200, 215, 240), width=1)
        cv.text((LEFT - 14, row), ["электрика"], 16, BLUE, "rm")
        row += 64
    cv.chain_h([X(L), X(0)], row, Z(0), INK, [f"{num(L)} по чистовой"])
    row += 64
    rough0, rough1 = t_end0, t_end1
    if rough0 or rough1:
        rs = [L + rough1, L, 0, -rough0]
        rs = [s for i, s in enumerate(rs) if i in (0, 3) or (i == 1 and rough1) or (i == 2 and rough0)]
        lab = []
        for a, b in zip(rs, rs[1:]):
            lab.append(num(a - b))
        cv.chain_h([X(s) for s in rs], row, Z(0), ROUGH_INK, lab)
        cv.text((LEFT - 14, row), ["черновая"], 16, ROUGH_INK, "rm")
        row += 64
        cv.chain_h([X(L + rough1), X(-rough0)], row, None, ROUGH_INK, [f"{num(L + rough0 + rough1)} по черновой"])

    # heights: geometry on the left, electrical on the right
    zs = {0.0, float(H)}
    for _, _, z0, z1, casing in opens:
        zs |= {round(z0, 1), round(z1, 1)}
        if casing:
            zs.add(round(z1 + CASING, 1))
    for it in front:
        if it.kind not in ("pipe", "plinth", "small", "splash") and it.z1 - it.z0 > 2:
            zs |= {round(it.z0, 1), round(min(it.z1, H), 1)}
    zl = sorted(zs, reverse=True)
    cv.chain_v([Z(z) for z in zl], LEFT - 85, X(L), INK, [num(a - b) for a, b in zip(zl, zl[1:])])
    cv.vtext(LEFT - 150, Z(H / 2), f"потолок {num(H)}" + (" (натяжной, ~)" if H >= 270 else ""), 18, GREY)
    if floor_tile:
        cv.text((LEFT - 14, Z(-floor_tile / 2) + 12), [f"плитка пола {num(floor_tile)}"], 15, TILE_EDGE, "rt")
    for k, z in enumerate(el_z):
        x = R + 60 + 52 * k
        cols = [p.color for p in pts_here if round(p.z, 2) == z]
        col = cols[0] if len(set(cols)) == 1 else BLUE
        cv.chain_v([Z(z), Z(0)], x, None, col, [num(z)])
        d.line([R + 6, Z(z), x + 8, Z(z)], fill=(200, 215, 240) if col == BLUE else LIGHT, width=1)

    cv.text((LEFT, TOP - 30), ["← левый угол"], 17, GREY, "lm")
    cv.text((R, TOP - 30), ["правый угол →"], 17, GREY, "rm")

    # ---- plan strip: this wall on top, the room below it, cut at depth D
    strip = Canvas(Wpx, (D - d_min) * SC + 2)
    sd = strip.d

    def T(p):
        s = (p[0] - w.a[0]) * w.u[0] + (p[1] - w.a[1]) * w.u[1]
        dd = (p[0] - w.a[0]) * w.n[0] + (p[1] - w.a[1]) * w.n[1]
        return X(s), (dd - d_min) * SC

    def poly(ps, **kw):
        sd.polygon([T(p) for p in ps], **kw)

    def slab(v, s0, s1, pad=0.0):
        return [v.pt(s0, pad), v.pt(s1, pad), v.pt(s1, -v.t - pad), v.pt(s0, -v.t - pad)]
    for v in m.walls.values():
        poly(slab(v, -v.t - v.e0, v.len + v.t + v.e1), fill=WALL_BODY)
    for _, _, rp in m.rooms:
        poly(rp, fill="white")
    for wid, t in tiles.items():
        v = m.walls[wid]
        poly([v.pt(-t), v.pt(v.len + t), v.pt(v.len + t, -t), v.pt(-t, -t)], fill=TILE_BAND)
        sd.line([T(v.pt(-t, -t)), T(v.pt(v.len + t, -t))], fill=TILE_EDGE, width=1)
    for v in m.walls.values():
        for s0, s1 in m.gaps.get(v.id, []):
            poly(slab(v, s0, s1, 0.5), fill="white")
            sd.line([T(v.pt(s0)), T(v.pt(s1))], fill=(185, 185, 185), width=2)
    for v, (s0, s1), door, plane in m.window_parts:
        poly(slab(v, s0, s1), fill="white" if door else (196, 196, 196))
        a, b = -plane + 3.5, -plane - 3.5
        poly([v.pt(s0, a), v.pt(s1, a), v.pt(s1, b), v.pt(s0, b)], fill=GLASS, outline=(120, 170, 220))
    room_ids = {v.id for v in room_walls}
    for it in items:
        if it.wall.id not in room_ids or it.kind in ("pipe", "plinth", "small"):
            continue
        if it.kind == "splash":
            poly(it.poly(), fill=TILE_BAND, outline=TILE_EDGE)
            continue
        if it.z0 >= 140 and it.kind == "kitchen":     # wall cabinets: outlines over what stands below
            continue
        fill = {"glass": (214, 226, 232), "counter": (200, 196, 190)}.get(it.kind, FURN)
        poly(it.poly(), fill=fill, outline=FURN_EDGE, width=2)
    for it in items:
        if it.wall.id in room_ids and it.z0 >= 140 and it.kind == "kitchen":
            q = [T(p) for p in it.poly()]
            for p0, p1 in zip(q, q[1:] + q[:1]):
                sd.line([p0, p1], fill=GREY, width=1)
    taken = []
    for it in sorted(front, key=lambda it: -(it.s1 - it.s0) * (it.d1 - it.d0)):
        if it.kind in ("pipe", "plinth", "splash", "small", "counter") or not it.label or \
                (it.kind == "kitchen" and it.z0 >= 140):
            continue
        cx, cy = T(w.pt((it.s0 + it.s1) / 2, (it.d0 + min(it.d1, D)) / 2))
        tw = font(15).getlength(it.label) + 6
        box = (cx - tw / 2, cy - 11, cx + tw / 2, cy + 11)
        if (it.s1 - it.s0) * SC > tw and (min(it.d1, D) - it.d0) * SC > 18 and \
                not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3] for q in taken):
            strip.text((cx, cy), [it.label], 15, GREY)
            taken.append(box)
    for p in pts_here:
        x = X(p.s)
        y0 = (p.d - d_min) * SC
        sd.rectangle([x - 5, y0, x + 5, y0 + 6], fill=p.color)
    sd.line([0, (D - d_min) * SC - 1, Wpx, (D - d_min) * SC - 1], fill="white", width=3)
    k = 0
    while k < Wpx:     # the cut across the room
        sd.line([k, (D - d_min) * SC - 2, k + 12, (D - d_min) * SC - 2], fill=GREY, width=2)
        k += 20
    sd.rectangle([0, 0, LEFT - 40, strip.img.height], fill="white")
    sd.rectangle([R + 40, 0, Wpx, strip.img.height], fill="white")
    cv.img.paste(strip.img, (0, int(PT)))
    cv.text((LEFT, PT - 24), ["план (вид сверху), стена сверху"], 17, GREY, "lm")
    if t_self or t_end0 or t_end1:
        cv.text((R + 50, PT + (0 - d_min) * SC), ["плитка с клеем", f"{num(t_self or t_end0 or t_end1)} (бежевым)"], 16,
                TILE_EDGE, "lm")
    # depths of what stands at this wall
    deps = sorted({round(it.d1, 1) for it in front if it.kind in ("furniture", "kitchen", "tile", "counter")
                   and it.d1 <= D and it.d1 - it.d0 > 5}, reverse=True)
    if deps:
        ys = [PT + (dd - d_min) * SC for dd in [0.0] + sorted(deps)]
        cv.chain_v(ys, LEFT - 60, LEFT - 40, INK, [num(b - a) for a, b in zip([0.0] + sorted(deps), sorted(deps))])
        cv.text((LEFT - 90, PT + (0 - d_min) * SC - 18), ["глубины"], 15, GREY, "rm")

    # ---- legend and notes
    y = PB + 50
    f = font(19)
    for n, col, t in legend:
        d.ellipse([LEFT, y - 12, LEFT + 24, y + 12], fill=col)
        d.text((LEFT + 12, y), str(n), fill="white", font=font(16, True), anchor="mm")
        for k2, line in enumerate(wrap(t, f, Wpx - LEFT - 100)):
            d.text((LEFT + 36, y), line, fill=INK, font=f, anchor="lm")
            y += 28
        y += 6
    notes = []
    if t_self or t_end0 or t_end1 or floor_tile or any(it.kind == "splash" for it in front):
        bits = []
        if t_self:
            bits.append(f"на этой стене плитка с клеем {num(t_self)}")
        if t_end0 or t_end1:
            bits.append("у углов в разрезе — плитка соседних стен")
        if floor_tile:
            bits.append(f"под полом — плитка пола с клеем ≈{num(floor_tile)} (уточнить)")
        if any(it.kind == "splash" for it in front):
            bits.append(f"фартук — плитка с клеем ≈{num(SPLASH_TILE)} (уточнить)")
        notes.append("Толщина плитки: " + "; ".join(bits) + ". Размеры — по плитке (чистовые), серым — по черновой "
                     "стене до укладки плитки.")
    if any(p.kind == "outlet" or p.kind == "switch" for p in pts_here):
        notes.append("Розетки и выключатели: высота и расстояние от левого угла — до центра рамки (AtlasDesign 83 × 83, "
                     "следующий пост +71 мм). Номера — по списку выше.")
    if side:
        notes.append("Серым сбоку — то, что стоит у соседних стен и упирается в эту (вид с торца).")
    if mounts:
        notes.append(MOUNT_NOTE)
    for t in notes:
        for line in wrap(t, font(18), Wpx - LEFT - 60):
            d.text((LEFT, y), line, fill=GREY, font=font(18), anchor="lm")
            y += 27
        y += 8
    cv.img = cv.img.crop((0, 0, int(Wpx), int(y + 30)))
    cv.img.save(out)


# ------------------------------------------------------------------ room plan -------------------------------------------

def room_plan(m, rid, name, poly, walls, sheets, items, points, tiles, floor_tile, out):
    xs_, ys_ = [p[0] for p in poly], [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs_) - 30, max(xs_) + 30, min(ys_) - 30, max(ys_) + 30
    SC = min(3.0, 1500 / (x1 - x0), 1700 / (y1 - y0))
    margin = 230
    W = int((x1 - x0) * SC) + 2 * margin
    W = max(W, 1000)
    Hh = int((y1 - y0) * SC) + 2 * margin + 300
    cv = Canvas(W, Hh)
    d = cv.d

    def P(x, y):
        return margin + (x - x0) * SC, Hh - margin - 300 - (y - y0) * SC

    def slab(v, s0, s1, pad=0.0):
        return [v.pt(s0, pad), v.pt(s1, pad), v.pt(s1, -v.t - pad), v.pt(s0, -v.t - pad)]
    for v in m.walls.values():
        d.polygon([P(*p) for p in slab(v, -v.t - v.e0, v.len + v.t + v.e1)], fill=WALL_BODY)
    for _, _, rp in m.rooms:
        d.polygon([P(*p) for p in rp], fill="white")
    for wid, t in tiles.items():
        v = m.walls[wid]
        d.polygon([P(*v.pt(-t)), P(*v.pt(v.len + t)), P(*v.pt(v.len + t, -t)), P(*v.pt(-t, -t))], fill=TILE_BAND)
        d.line([P(*v.pt(-t, -t)), P(*v.pt(v.len + t, -t))], fill=TILE_EDGE, width=1)
    for v in m.walls.values():
        for s0, s1 in m.gaps.get(v.id, []):
            d.polygon([P(*p) for p in slab(v, s0, s1, 0.5)], fill="white")
            d.line([P(*v.pt(s0)), P(*v.pt(s1))], fill=(185, 185, 185), width=2)
    for v, (s0, s1), door, plane in m.window_parts:
        d.polygon([P(*p) for p in slab(v, s0, s1)], fill="white" if door else (196, 196, 196))
        a, b = -plane + 3.5, -plane - 3.5
        d.polygon([P(*v.pt(s0, a)), P(*v.pt(s1, a)), P(*v.pt(s1, b)), P(*v.pt(s0, b))], fill=GLASS,
                  outline=(120, 170, 220))
    ids = {v.id for v in walls}
    for it in items:
        if it.wall.id not in ids or it.kind in ("pipe", "plinth", "small") or \
                (it.kind == "kitchen" and it.z0 >= 140):
            continue
        if it.kind == "splash":
            d.polygon([P(*p) for p in it.poly()], fill=TILE_BAND, outline=TILE_EDGE)
            continue
        if it.kind == "counter":
            d.polygon([P(*p) for p in it.poly()], outline=FURN_EDGE)
            continue
        fill = {"glass": (214, 226, 232)}.get(it.kind, FURN)
        d.polygon([P(*p) for p in it.poly()], fill=fill, outline=FURN_EDGE)
    for it in items:   # wall cabinets: thin outlines over the base
        if it.wall.id in ids and it.kind == "kitchen" and it.z0 >= 140:
            q = [P(*p) for p in it.poly()]
            for p0, p1 in zip(q, q[1:] + q[:1]):
                d.line([p0, p1], fill=LIGHT, width=1)
    for it in items:   # the kitchen runs and the fridge: one label each
        if it.wall.id in ids and it.kind == "counter":
            c = P(*it.wall.pt((it.s0 + it.s1) / 2, it.d1 / 2))
            cv.text(c, ["кухня", f"глубина {num(it.d1)} (столешница)"], 15, GREY, bg=FURN)
        if it.wall.id in ids and it.kind == "kitchen" and it.label == "холодильник":
            c = P(*it.wall.pt((it.s0 + it.s1) / 2, it.d1 / 2))
            cv.text(c, ["холо-", "дильник"], 14, GREY, bg=FURN)
    taken = []
    for it in sorted(items, key=lambda it: -(it.s1 - it.s0) * (it.d1 - it.d0)):   # labels on top, no overlaps
        if it.wall.id not in ids or it.kind not in ("furniture", "tile", "glass") or not it.label \
                or it.d1 - it.d0 < 6:
            continue
        a, b = P(*it.wall.pt(it.s0, it.d0)), P(*it.wall.pt(it.s1, it.d1))
        wpx, hpx = abs(b[0] - a[0]), abs(b[1] - a[1])
        c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        lab = [it.label] + ([it.size] if hpx > 44 and wpx > font(15).getlength(it.size) + 6 else [])
        tw = max(font(15).getlength(t) for t in lab) + 6
        box = (c[0] - tw / 2, c[1] - 11 * len(lab), c[0] + tw / 2, c[1] + 11 * len(lab))
        if wpx > tw and hpx > 20 and not any(box[0] < q[2] and q[0] < box[2] and box[1] < q[3] and q[1] < box[3]
                                             for q in taken):
            cv.text(c, lab, 15, GREY)
            taken.append(box)
    for p in points:
        if p.wall.id not in ids:
            continue
        x, y = P(*p.wall.pt(p.s, p.d))
        d.rectangle([x - 5, y - 5, x + 5, y + 5], fill=p.color)

    # blank out everything beyond the room and its own walls
    mask = Image.new("L", (W, Hh), 0)
    md = ImageDraw.Draw(mask)
    pts = [P(*q) for q in poly]
    md.polygon(pts, fill=255)
    for v in walls:
        md.polygon([P(*p) for p in slab(v, -v.t - v.e0 - 2, v.len + v.t + v.e1 + 2, 1)], fill=255)
    cv.img.paste(Image.new("RGB", (W, Hh), "white"), (0, 0), Image.eval(mask, lambda v: 255 - v))
    d = cv.d = ImageDraw.Draw(cv.img)

    # chains outside each wall: openings, the whole wall by the finish, the rough wall behind the tile
    def wall_chain(v, dd, ss, ink, labels=None):
        q = [P(*v.pt(s, dd)) for s in ss]
        for s, p in zip(ss, q):
            d.line([P(*v.pt(s, -v.t - 2)), P(*v.pt(s, dd - 3))], fill=(170, 170, 170), width=1)
            d.line([p[0] - 6, p[1] + 6, p[0] + 6, p[1] - 6], fill=ink, width=2)
        d.line([q[0], q[-1]], fill=ink, width=2)
        ox, oy = -v.n[0], v.n[1]
        for k, (s0, s1, pa, pb) in enumerate(zip(ss, ss[1:], q, q[1:])):
            t = labels[k] if labels else num(s1 - s0)
            c = ((pa[0] + pb[0]) / 2 + ox * 15, (pa[1] + pb[1]) / 2 + oy * 15)
            if v.along_x:
                d.text(c, t, fill=ink, font=font(17), anchor="mm")
            else:
                cv.vtext(c[0], c[1], t, 17, ink, (0, 0, 0, 0))

    for v in walls:
        if v.len < 15:
            continue
        ops = sorted({round(max(0.0, s), 1) for o in m.openings(v) for s in o if -0.5 <= s <= v.len + 0.5} |
                     {0.0, round(v.len, 1)})
        off = -v.t - 12
        if len(ops) > 2:
            wall_chain(v, off, ops, INK)
            off -= 16
        wall_chain(v, off, [0.0, v.len], INK)
        if v.id in tiles:
            off -= 16
            t = tiles[v.id]
            wall_chain(v, off, [-t, v.len + t], ROUGH_INK, [f"{num(v.len + 2 * t)} черн."])
    for v in walls:   # the sheet number of each wall, inside the room by it
        if v.id not in sheets:
            continue
        x, y = P(*v.pt(v.len / 2, -v.t / 2))
        d.ellipse([x - 17, y - 17, x + 17, y + 17], fill="white", outline=INK, width=2)
        d.text((x, y), sheets[v.id], fill=INK, font=font(17, True), anchor="mm")

    cv.text((margin, 50), [f"{name} — план с размерами"], 34, INK, "lm", True)
    notes = ["Размеры по чистовой отделке (по плитке), см; в кружках на стенах — номера листов; квадраты у стен — "
             "розетки, выключатели, выводы (подробно на листах стен)."]
    if tiles:
        notes.append(f"Бежевым — плитка с клеем {num(max(tiles.values()))} на стенах; серым снаружи — размеры по "
                     "черновой стене (до плитки).")
    if floor_tile:
        notes.append(f"Пол — плитка; с клеем ≈{num(floor_tile)} (уточнить), высоты на листах — от чистового пола.")
    y = Hh - 300 + 20
    for t in notes:
        for line in wrap(t, font(19), W - 2 * margin):
            d.text((margin, y), line, fill=GREY, font=font(19), anchor="lm")
            y += 28
        y += 6
    cv.img.crop((0, 0, W, int(y + 30))).save(out)


# ------------------------------------------------------------------ main ------------------------------------------------

def wall_title(w, room_id, room_walls, start, items, cfg, m):
    if w.id in WALL_NAMES:
        return WALL_NAMES[w.id]
    f = start.n
    left = (-f[1], f[0])
    if w is start:
        pos = "Стена с дверью"
    elif w.n[0] * f[0] + w.n[1] * f[1] < -0.7:
        pos = "Дальняя стена"
    elif w.n[0] * left[0] + w.n[1] * left[1] < -0.7:
        pos = "Левая стена"
    elif w.n[0] * left[0] + w.n[1] * left[1] > 0.7:
        pos = "Правая стена"
    else:
        pos = "Стена"
    what = []
    for win in cfg.get("windows", []):
        if win["wall"] == w.id:
            types = {p["type"] for p in win["parts"]}
            what.append("окно и дверь" if types == {"door", "window"} else "окно")
    for it in items:
        if it.wall is w and it.label and it.kind in ("furniture", "glass") and it.label not in what:
            if it.label in ("ТВ", "кровать", "шкаф", "шкаф-купе", "стол", "диван", "зеркало", "ванна", "унитаз",
                            "колонна стирки и сушки", "пенал", "шкаф в нише", "кондиционер", "полотенцесушитель"):
                what.append("изголовье кровати" if it.label == "кровать" else it.label)
    return pos + (" — " + ", ".join(dict.fromkeys(what)) if what else "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--room", help="только эта комната (id), например bathroom")
    args = ap.parse_args()
    cfg = json.loads(Path("rooms/apartment.json").read_text())
    plan = json.loads(Path("plan.json").read_text())
    m = Model(cfg, plan)
    wet = {"bathroom", "toilet"}
    heights = {"bathroom": 267.0, "toilet": 267.0}
    room_of = {}
    rooms = {}
    outline_order = [w["id"] for ol in [cfg["outline"]] + [r["outline"] for r in cfg["extra_rooms"]] for w in ol]
    for rid, name, poly in m.rooms:
        ws = [m.walls[i] for i in outline_order if in_polygon(*m.walls[i].pt(m.walls[i].len / 2, 6), poly)]
        rooms[rid] = {"name": ROOM_NAMES.get(rid, name), "poly": poly, "walls": ws}
        for v in ws:
            room_of[v.id] = rid

    def height(w):
        return heights.get(room_of.get(w.id), float(cfg["room"]["height"]))
    items = items_of(cfg, m, height)
    points = points_of(cfg, plan, m, items)
    tiles = dict(m.wall_tile)
    floor_types = {"hall": cfg["floor"].get("type"), "kitchen_living": cfg["floor"].get("type")}
    floor_types.update({r["id"]: (r.get("floor") or {}).get("type") for r in cfg["extra_rooms"]})

    for n, rid in enumerate(ROOM_ORDER, 1):
        if args.room and rid != args.room or rid not in rooms:
            continue
        r = rooms[rid]
        folder = OUT / f"{n:02d} {r['name']}"
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        ws = r["walls"]
        start = m.walls.get(START.get(rid, "")) or next(
            (v for v in ws if m.gaps.get(v.id)), ws[0])
        k0 = ws.index(start)
        ordered = ws[k0:] + ws[:k0]
        floor_tile = FLOOR_TILE if floor_types.get(rid) == "porcelain" else 0
        show = []
        for v in ordered:
            has = any(it.wall is v for it in items) or any(p.wall is v for p in points) or m.openings(v)
            if v.len >= 60 or (v.len >= 30 and has):
                show.append(v)
        sheets = {v.id: f"{k:02d}" for k, v in enumerate(show, 1)}
        room_tiles = {wid: t for wid, t in tiles.items() if wid in {v.id for v in ws}}
        room_plan(m, rid, r["name"], r["poly"], ws, sheets, items, points, room_tiles, floor_tile,
                  folder / "00 План.png")
        print(folder / "00 План.png")
        for k, v in enumerate(show, 1):
            title = wall_title(v, rid, ws, start, items, cfg, m)
            out = folder / f"{k:02d} {title}.png"
            wall_sheet(m, v, r, k, f"{r['name']} — {k:02d}. {title}", items, points, cfg, height(v), tiles,
                       floor_tile, out)
            print(out)
        for j, name in enumerate(EXTRA_SHEETS.get(rid, []), len(show) + 1):
            src = PLANS / f"{name}.png"
            if src.exists():
                dst = folder / f"{j:02d} {name.split(' — ')[0]}.png"
                shutil.copy(src, dst)
                print(dst)


if __name__ == "__main__":
    main()
