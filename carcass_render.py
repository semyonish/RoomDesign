"""3D render of a box frame (каркас) from plan_carcass.json, assembled as it would be built and checked for physics:
the 27-series profiles as real U channels nested into each other, the Grohe Rapid SL frame after the manufacturer's
datasheet, the drain with its fall, the rough walls and floor; no plasterboard yet.

Assembly: studs and crossbars sit inside their tracks (between the ПН flanges, on the bottom web, 5 mm short of the
top web), as they go in on site. Check: no two solids may overlap (manufacturer assemblies excepted), every profile
must rest on the floor, a wall, the Grohe frame or a profile that does; the Grohe frame must be within its datasheet
limits. The report goes next to the picture.

    .venv/bin/python carcass_render.py bathroom          # renders/carcass/bathroom.png + bathroom_check.txt
    .venv/bin/python carcass_render.py bathroom --small  # framing check: 800 × 600, 16 samples
    .venv/bin/python carcass_render.py bathroom --view low
    .venv/bin/python carcass_render.py bathroom --view nodes  # the connections to the frame: one annotated sheet

Local frame: X = s (along the wall, left to right from the room), Y = −d (the back wall at 0, the room at negative Y),
Z = z (over the finished floor); cm in the JSON, metres in the scene.
"""

import argparse
import fcntl
import json
import math
from pathlib import Path

import bpy  # before bmesh and mathutils: the bpy wheel provides them
import bmesh
from mathutils import Vector

from roomgen import geo, materials

ROOT = Path(__file__).resolve().parent
T = 0.06    # profile steel, cm
LIP = 0.45  # ПП flange lips folded inward, cm
CUT = 0.5   # studs are cut this much short of the top track's web
EPS, TOL = 0.005, 0.02  # overlap that counts as a collision; gap that still counts as contact, cm
# Rough rooms in the box's local frame: the wall at s 0 / s S / d D carries the door (span along that wall, height).
ROOMS = {
    "bathroom": {"S": 189, "D": 181, "door": ("s0", (67, 147), 210),
                 "views": {"main": ((100, 120, 150), (42, 6, 50)), "low": ((105, 75, 70), (55, 6, 12))}},
    "toilet": {"S": 150.5, "D": 189, "door": ("dD", (9, 89), 210),
               "views": {"main": ((120, 175, 165), (60, 5, 50)), "low": ((110, 90, 70), (60, 6, 15))}},
}


class Solids:
    """Every axis-aligned part (cm) with its object and group, for the overlap and support checks."""

    def __init__(self):
        self.items = []   # (object, group, (s0, s1, d0, d1, z0, z1))

    def add(self, obj, group, s, d, z):
        self.items.append((obj, group, (min(s), max(s), min(d), max(d), min(z), max(z))))


def P(s, d, z):
    return Vector((s / 100, -d / 100, z / 100))


def block(name, s, d, z, mat, col, solids=None, group=None):
    if solids is not None:
        solids.add(name, group, s, d, z)
    return geo.box(name, P(s[0], d[0], z[0]), P(s[1], d[1], z[1]), mat, col)


def pipe(name, a, b, r, mat, col, solids=None, group=None, step=10.0):
    """A cylinder between two points (s, d, z); for the checks it is cut into short boxes along its axis."""
    a, b = Vector(a), Vector(b)
    axis = b - a
    geo.cylinder(name, P(*((a + b) / 2)), (axis.x, -axis.y, axis.z), r / 100, axis.length / 100, mat, col, 32)
    if solids is not None:
        n = max(1, math.ceil(axis.length / step))
        ext = [r * math.sqrt(max(0.0, 1 - (axis[k] / axis.length) ** 2)) for k in range(3)]
        for i in range(n):
            p, q = a + axis * (i / n), a + axis * ((i + 1) / n)
            lo = [min(p[k], q[k]) - ext[k] for k in range(3)]
            hi = [max(p[k], q[k]) + ext[k] for k in range(3)]
            solids.add(name, group, (lo[0], hi[0]), (lo[1], hi[1]), (lo[2], hi[2]))


def assemble(box):
    """Seat the pieces as built: ПП studs and crossbars in the gap of the ПН they meet, studs on the bottom web and a
    cut short of the top one. Returns new piece dicts; the drawing data stays nominal."""
    pieces = [{**p, "s": list(p["s"]), "d": list(p["d"]), "z": list(p["z"])} for p in box["pieces"]]
    tracks = [p for p in pieces if p["profile"] == "ПН" and p["d"][0] > 0]   # tracks along the front plane
    for p in pieces:
        if p["profile"] != "ПП" or p["d"][1] != box["front"]:
            continue
        hosts = [t for t in tracks if t["s"][0] < p["s"][1] and p["s"][0] < t["s"][1]]
        p["d"] = [box["front"] - 2.8 + T, box["front"] - T]
        if p["z"][1] - p["z"][0] > p["s"][1] - p["s"][0]:   # an upright: seat it in the tracks at its ends
            below = [t for t in hosts if t["z"][0] <= p["z"][0] + 0.5 and t["z"][1] - t["z"][0] < 5]
            above = [t for t in hosts if abs(t["z"][1] - p["z"][1]) < 0.5 and t["z"][1] - t["z"][0] < 5]
            if below:
                p["z"][0] = below[0]["z"][0] + T
            if above:
                p["z"][1] = above[0]["z"][1] - T - CUT
    return pieces


def fasteners(box, pieces, mats, col):
    """Where profiles meet the Grohe frame (plan_carcass.json connections): the end of a profile laid 3 cm over the face
    of a post and held by self-drilling screws from the front; screws down through a track's web into the top bar.
    Returns the points to number on the overview, (id, (s, d, z))."""
    marks = []
    screw, galv = mats["screw"], mats["galv"]
    front = box["front"]

    def screw_along(a, b, head_at, r_head=0.38):
        pipe("Screw Shank", a, b, 0.17, screw, col)
        pipe("Screw Head", head_at[0], head_at[1], r_head, screw, col)

    for c in box.get("connections", []):
        if c["type"] == "overlap":
            p = next(q for q in pieces if q["id"] == c["piece"])
            at, zc = c["at"]
            tail = (at, at + 3) if p["s"][0] < at else (at - 3, at)   # over the post, away from the piece
            if p["profile"] == "ПП":                                   # the web runs on over the post's face
                z0, z1 = p["z"][0] + 0.3, p["z"][1] - 0.3
                spots = [(sum(tail) / 2, (z0 + z1) / 2 + dz) for dz in (-1.4, 1.4)]
            else:                                                      # a top track: its front flange runs on
                z0, z1 = p["z"][0], p["z"][1] - T
                spots = [(sum(tail) / 2, (z0 + z1) / 2)]
            block(f"{p['profile']} {p['id']} Tail", tail, (front, front + T), (z0, z1), galv, col)
            for s_, z in spots:
                screw_along((s_, front + T, z), (s_, front - 1.4, z),
                            ((s_, front + T, z), (s_, front + T + 0.25, z)))
            marks.append((c["id"], (sum(tail) / 2, front, (z0 + z1) / 2)))
        elif c["type"] == "screw_down":
            p = next(q for q in pieces if q["id"] == c["piece"])
            d = sum(p["d"]) / 2
            for s_, z in c["at"]:
                screw_along((s_, d, z), (s_, d, z - 4.0), ((s_, d, z), (s_, d, z + 0.12)), 0.42)
            marks.append((c["id"], (c["at"][0][0], p["d"][1], c["at"][0][1])))
        else:
            s_, z = c["at"]
            marks.append((c["id"], (s_, front, z)))
    return marks


def channel(name, kind, s, d, z, rough, mat, col, solids):
    """A U channel filling the piece's box: the web on the side the piece is fixed by, flanges to the open side."""
    rng = {"s": list(s), "d": list(d), "z": list(z)}
    run = max(rng, key=lambda a: rng[a][1] - rng[a][0])
    if kind == "ПП":
        web, side = ("d", 1) if run != "d" else ("z", 1)   # the 60 web carries the plasterboard; ties: web up
    elif d[0] == 0:
        web, side = ("d", 0)                                # on the back wall
    elif z[0] == rough:
        web, side = ("z", 0)                                # on the floor
    else:
        web, side = ("z", 1)                                # along the top
    flange = next(a for a in "sdz" if a not in (run, web))
    bm = bmesh.new()

    def add(over):
        r = {a: over.get(a, rng[a]) for a in "sdz"}
        geo.add_box(bm, P(r["s"][0], r["d"][0], r["z"][0]), P(r["s"][1], r["d"][1], r["z"][1]))
        solids.add(name, "profile", r["s"], r["d"], r["z"])

    w0, w1 = rng[web]
    f0, f1 = rng[flange]
    add({web: [w1 - T, w1] if side else [w0, w0 + T]})
    add({flange: [f0, f0 + T]})
    add({flange: [f1 - T, f1]})
    if kind == "ПП":
        open_end = [w0, w0 + T] if side else [w1 - T, w1]
        add({web: open_end, flange: [f0, f0 + LIP]})
        add({web: open_end, flange: [f1 - LIP, f1]})
    return geo.mesh_object(name, bm, mat, col)


def rapid_sl(box, inst, rough, mats, col, solids):
    """Grohe Rapid SL 38 528 001 after its datasheet: 500 wide, top 1130 over the finished floor, legs down to the
    rough floor, wall brackets at the top, cistern GD 2 with the inspection shaft at 1000, flush inlet, M12 bolts
    180 apart, PP outlet bend Ø90 at 230 dropping 135 behind the face. Returns the drop's axis depth."""
    face, (f0, f1), ax = box["front"], box["frame"], box["axis"]
    pw, pd = inst["post"]
    top = inst["top"]
    finish = face + 2.5 + box["tile"]   # the finished wall in front of the frame
    g = "grohe"
    frame, plastic, bend, caps, chrome = mats["frame"], mats["cistern"], mats["bend"], mats["caps"], mats["chrome"]
    for i, p in enumerate((f0, f1 - pw)):
        block(f"Rapid Post {i}", (p, p + pw), (face - pd, face), (12, top), frame, col, solids, g)
        block(f"Rapid Leg {i}", (p + 0.5, p + pw - 0.5), (face - pd + 0.5, face - 0.5), (rough + 0.3, 12), frame, col,
              solids, g)
        block(f"Rapid Foot {i}", (p - 1, p + pw + 1), (face - 9, face), (rough, rough + 0.3), frame, col, solids, g)
        block(f"Rapid Bracket Arm {i}", (p + 0.5, p + pw - 0.5), (0.4, face - pd), (104, 106.5), frame, col, solids, g)
        block(f"Rapid Wall Plate {i}", (p - 0.5, p + pw + 0.5), (0, 0.4), (100, 110), frame, col, solids, g)
    span = (f0 + pw, f1 - pw)
    block("Rapid Top Bar", span, (face - pd, face), (top - 4, top), frame, col, solids, g)
    block("Rapid Bolt Bar", span, (face - 3, face), (28.5, 31.5), frame, col, solids, g)
    block("Rapid Bend Support", span, (face - 3, face), (16, 18), frame, col, solids, g)
    block("Rapid Low Bar", span, (face - 3, face), (8, 10.5), frame, col, solids, g)
    block("Rapid Cistern", (ax - 18.5, ax + 18.5), (face - 13, face - 1), (78, 108.5), plastic, col, solids, g)
    block("Rapid Cistern Low", (ax - 14, ax + 14), (face - 12, face - 1.5), (57, 78), plastic, col, solids, g)
    block("Rapid Inspection Shaft", (ax - 8.5, ax + 8.5), (face - 1, finish - 0.1), (93.5, 106.5), plastic, col,
          solids, g)
    zi = inst["flush_inlet_z"]
    pipe("Rapid Flush Pipe", (ax, face - 7, 57), (ax, face - 7, zi), 2.2, plastic, col, solids, g)
    pipe("Rapid Flush Inlet", (ax, face - 7, zi), (ax, finish + 3, zi), 2.75, plastic, col, solids, g)
    pipe("Rapid Inlet Cap", (ax, finish + 3, zi), (ax, finish + 4.5, zi), 3.1, caps, col, solids, g)
    zb = inst["bolt_z"]
    for ds in (-inst["bolt_spacing"] / 2, inst["bolt_spacing"] / 2):
        block("Rapid Bolt Clamp", (ax + ds - 1.5, ax + ds + 1.5), (face - 3, face), (31.5, 35), frame, col, solids, g)
        pipe("Rapid Bolt M12", (ax + ds, face - 3, zb), (ax + ds, finish + 9, zb), 0.6, chrome, col, solids, g)
        pipe("Rapid Bolt Cap", (ax + ds, finish + 7, zb), (ax + ds, finish + 9.5, zb), 0.9, caps, col, solids, g)
    zd = inst["drain_axis"]
    drop_d = face - inst["depth_behind_face"]["Ø90"][0] + 4.5   # the bend's back 135 behind the face
    pipe("Rapid Outlet Stub", (ax, drop_d - 4.5, zd), (ax, finish + 4, zd), 4.5, bend, col, solids, g)
    pipe("Rapid Outlet Cap", (ax, finish + 4, zd), (ax, finish + 5.5, zd), 5.0, caps, col, solids, g)
    return drop_d


def drain(box, inst, rough, drop_d, mats, col, solids):
    """The Ø90 drop of the Grohe bend into an eccentric adaptor and the Ø110 run along the wall with its fall."""
    dr = box.get("drain")
    if not dr:
        return
    r, ax, s1 = dr["diameter"] / 2, dr["from_s"], dr["to_s"]
    bottom_end = rough + 0.5                          # on a clip just off the rough floor at the far end

    def axis_z(s):
        return bottom_end + r + dr["slope"] * (s1 - s)

    z0 = axis_z(ax)
    pipe("Drain Drop Ø90", (ax, drop_d, inst["drain_axis"] + 4.5), (ax, drop_d, z0 + r + 1.5), 4.5, mats["bend"], col,
         solids, "drain")
    pipe("Drain Adaptor", (ax, dr["axis_d"], z0 + r + 3), (ax, dr["axis_d"], z0 - 1), r + 0.4, mats["pvc"], col,
         solids, "drain")
    pipe("Drain Ø110", (ax + r + 0.4, dr["axis_d"], axis_z(ax + r + 0.4)), (s1, dr["axis_d"], axis_z(s1)), r,
         mats["pvc"], col, solids, "drain")


def build(box, inst, room, rough, col):
    solids = Solids()
    mats = {
        "galv": materials._principled("Galvanised", materials.rgba("#C9CDD1"), 0.32, Metallic=1.0)[0],
        "frame": materials._principled("Grohe Blue", materials.rgba(inst["colors"]["frame"]), 0.45)[0],
        "cistern": materials.matte("Cistern Plastic", inst["colors"]["cistern"], 0.45),
        "bend": materials.matte("Outlet Bend", inst["colors"]["bend"], 0.5),
        "caps": materials.matte("Protective Caps", inst["colors"]["caps"], 0.55),
        "chrome": materials.metal("Chrome", "chrome"),
        "pvc": materials.matte("PVC Grey", "#9EA3A6", 0.45),
        "brass": materials._principled("Brass", materials.rgba("#B8954A"), 0.3, Metallic=1.0)[0],
        "plaster": materials.matte("Rough Plaster", "#9E978D", 0.95),
        "screed": materials.matte("Screed", "#8C8780", 0.95),
        "bath": materials.matte("Bath", "#F2F2EF", 0.35),
        "door": materials.matte("Door", "#DDD8CE", 0.6),
        "screw": materials._principled("Yellow Zinc", materials.rgba("#D8B23A"), 0.35, Metallic=1.0)[0],
    }
    S, D, (door_wall, (o0, o1), oh) = room["S"], room["D"], room["door"]
    block("Floor", (-12, S + 12), (-12, D + 12), (rough - 6, rough), mats["screed"], col, solids, "room")
    walls = {"d0": ((-12, S + 12), (-12, 0)), "dD": ((-12, S + 12), (D, D + 12)),
             "s0": ((-12, 0), (0, D)), "sS": ((S, S + 12), (0, D))}
    for wid, (ws, wd) in walls.items():
        if wid != door_wall:
            block(f"Wall {wid}", ws, wd, (rough, 230), mats["plaster"], col, solids, "room")
            continue
        along = "s" if wid[0] == "d" else "d"  # the door wall runs along this axis
        span = ws if along == "s" else wd
        for a, b, z in ((span[0], o0, (rough, 230)), (o1, span[1], (rough, 230)), (o0, o1, (oh, 230))):
            block(f"Wall {wid}", (a, b) if along == "s" else ws, wd if along == "s" else (a, b), z, mats["plaster"],
                  col, solids, "room")
        # a closed door at the far face of the opening, so the view never looks out into nothing
        leaf = ((ws[0], ws[0] + 4), (o0, o1)) if along == "d" else ((o0, o1), (wd[1] - 4, wd[1]))
        block("Door", *leaf, (rough, oh), mats["door"], col)
    L = box["length"]
    if box.get("right_end") == "экран ванны":   # the bath beyond the low box: tub on legs, screen to the floor
        block("Bath", (L + 2, L + 78), (1.5, 179.5), (15, 58), mats["bath"], col, solids, "room")
        block("Bath Screen", (L, L + 2), (14, 179.5), (rough, 58), mats["bath"], col, solids, "room")
    pieces = assemble(box)
    for p in pieces:
        channel(f"{p['profile']} {p['id']}", p["profile"], p["s"], p["d"], p["z"], rough, mats["galv"], col, solids)
    marks = fasteners(box, pieces, mats, col)
    drop_d = rapid_sl(box, inst, rough, mats, col, solids)
    drain(box, inst, rough, drop_d, mats, col, solids)
    for h in box["holes"]:
        if "водорозетка" in h["name"]:
            pipe("Water Socket", (h["s"], box["front"] - 2.5, h["z"]), (h["s"], box["front"] + 1, h["z"]), 1.2,
                 mats["brass"], col)
    return solids, marks


def check(box, inst, solids):
    """Overlaps between solids of different objects, profiles that rest on nothing, Grohe datasheet limits."""
    lines = []
    items = solids.items

    def overlap(a, b):
        return all(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) > EPS for k in range(3))

    def touch(a, b):  # touching on a face (or overlapping)
        gaps = sorted(max(a[2 * k], b[2 * k]) - min(a[2 * k + 1], b[2 * k + 1]) for k in range(3))
        return gaps[2] <= TOL and gaps[1] < -EPS

    connected = {"Rapid Outlet Stub", "Drain Drop Ø90", "Drain Adaptor", "Drain Ø110"}  # joined pipe fittings
    seen = set()
    for i, (oa, ga, a) in enumerate(items):
        for ob, gb, b in items[i + 1:]:
            if oa == ob or (ga == gb and ga in ("grohe", "room", "drain")) or {oa, ob} <= connected:
                continue
            if (oa, ob) not in seen and overlap(a, b):
                seen.add((oa, ob))
                depth = min(min(a[2 * k + 1], b[2 * k + 1]) - max(a[2 * k], b[2 * k]) for k in range(3))
                lines.append(f"ПЕРЕСЕЧЕНИЕ: {oa} × {ob} — на {depth * 10:.1f} мм")
    supported = {o for o, g, _ in items if g in ("room", "grohe")}
    profiles = {o for o, g, _ in items if g == "profile"}
    changed = True
    while changed:
        changed = False
        for o in sorted(profiles - supported):
            mine = [b for oo, _, b in items if oo == o]
            if any(touch(a, b) for a in mine for oo, _, b in items if oo in supported):
                supported.add(o)
                changed = True
    for o in sorted(profiles - supported):
        lines.append(f"НЕ ОПИРАЕТСЯ: {o} — ни на пол, ни на стену, ни на раму или другой профиль")
    face = box["front"]
    if face > inst["max_face_from_wall"]:
        lines.append(f"РАМА: лицо в {face:g} от стены, штатные кронштейны — до {inst['max_face_from_wall']:g}: "
                     "нужна проставка или удлинённые кронштейны")
    need = inst["depth_behind_face"]["Ø90"][0]
    if face < need:
        lines.append(f"РАМА: за лицом рамы {face:g}, отводу Ø90 нужно {need:g}")
    build_up = 2.5 + box["tile"]
    lo, hi = inst["build_up"]
    if not lo <= build_up <= hi:
        lines.append(f"РАМА: облицовка перед рамой {build_up:g}, по Grohe {lo:g}–{hi:g}")
    if box.get("drain"):
        dr = box["drain"]
        post_back = face - inst["post"][1]
        lines.append(f"труба Ø{dr['diameter'] * 10:g}: до стены {dr['axis_d'] - dr['diameter'] / 2:.1f} см, "
                     f"до стойки рамы {post_back - dr['axis_d'] - dr['diameter'] / 2:.1f} см; уклон {dr['slope'] * 100:g} %")
    if not any(line.startswith(("ПЕРЕСЕЧЕНИЕ", "НЕ ОПИРАЕТСЯ")) for line in lines):
        lines.insert(0, f"сборка без пересечений: {len(profiles)} профилей, все опираются")
    return lines


def camera_for(c, box):
    """A close-up onto one connection: from the piece's side and the front for a tail on a post, from above the
    track for screws down."""
    front = box["front"]
    if c["type"] == "overlap":
        at, z = c["at"]
        piece = next(p for p in box["pieces"] if p["id"] == c["piece"])
        out = -1 if piece["s"][0] < at else 1
        return (at + out * 15, front + 30, z + 9), (at - out * 1.5, front, z)
    s_, z = c["at"][0]
    return (s_ + 9, front + 17, z + 17), (s_, front - 2, z - 1)


def compose(box, title, overview, marks_px, closeups, rules, out):
    """One sheet: the overview with numbered connections, the close-ups with what to do at each."""
    from PIL import Image, ImageDraw, ImageFont
    f_b, f_m, f_s = (ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 34),
                     ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 24),
                     ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 21))
    W, margin = 2200, 50
    ov = Image.open(overview).convert("RGB")
    ov_w = 1150
    k = ov_w / ov.width
    ov = ov.resize((ov_w, int(ov.height * k)))
    tile_w = (W - 2 * margin - 2 * 30) // 3
    tiles = [(c, Image.open(path).convert("RGB")) for c, path in closeups]
    tiles = [(c, im.resize((tile_w, int(im.height * tile_w / im.width)))) for c, im in tiles]
    sheet = Image.new("RGB", (W, 4000), "white")
    d = ImageDraw.Draw(sheet)

    def wrap(text, x, y, width, font, fill=(30, 30, 30), step=30):
        line = ""
        for w in text.split():
            if d.textlength(line + " " + w, font=font) > width:
                d.text((x, y), line.strip(), fill=fill, font=font)
                y += step
                line = ""
            line += " " + w
        d.text((x, y), line.strip(), fill=fill, font=font)
        return y + step

    d.text((margin, 30), title, fill=(30, 30, 30), font=f_b)
    y0 = 100
    sheet.paste(ov, (margin, y0))
    for cid, (x, y) in marks_px:
        x, y = margin + x * k, y0 + y * k
        d.ellipse([x - 24, y - 24, x + 24, y + 24], fill=(214, 40, 40), outline="white", width=3)
        d.text((x, y), cid, fill="white", font=f_s, anchor="mm")
    tx, ty = margin + ov_w + 40, y0
    for c in box["connections"]:
        d.text((tx, ty), c["id"], fill=(214, 40, 40), font=f_b)
        ty = wrap(f"{c['to']}: {c['how']}", tx + 70, ty + 4, W - margin - tx - 70, f_m, step=31) + 18
    y = y0 + ov.height + 40
    x = margin
    for c, im in tiles:
        sheet.paste(im, (x, y))
        d.ellipse([x + 14, y + 14, x + 70, y + 70], fill=(214, 40, 40), outline="white", width=3)
        d.text((x + 42, y + 42), c["id"], fill="white", font=f_s, anchor="mm")
        wrap(c["to"], x, y + im.height + 10, tile_w, f_s, step=27)
        x += tile_w + 30
    y += max(im.height for _, im in tiles) + 90 if tiles else 0
    d.text((margin, y), "Порядок и правила", fill=(30, 30, 30), font=f_m)
    y += 40
    for r in rules:
        y = wrap("— " + r, margin, y, W - 2 * margin, f_s, step=28) + 6
    sheet.crop((0, 0, W, y + 30)).save(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("box", choices=["bathroom", "toilet"])
    ap.add_argument("--view", default="main", help="main, low, or nodes: the connections to the frame on one sheet")
    ap.add_argument("--small", action="store_true")
    ap.add_argument("--samples", type=int, default=96)
    args = ap.parse_args()
    plan = json.loads((ROOT / "plan_carcass.json").read_text())
    box, rough, inst = plan["boxes"][args.box], plan["rough_floor"], plan["installation"]
    room = ROOMS[args.box]

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    col = bpy.data.collections.new("Carcass")
    scene.collection.children.link(col)
    solids, marks = build(box, inst, room, rough, col)
    report = check(box, inst, solids)
    print("\n".join(report))

    world = bpy.data.worlds.new("Studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.8, 0.8, 0.82, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.08
    scene.world = world
    L = box["length"]
    for name, loc, size, power in (("Ceiling", (L / 2, 100, 250), 1.6, 110), ("Fill", (20, 190, 140), 1.0, 30)):
        light = bpy.data.lights.new(name, "AREA")
        light.size, light.energy = size, power
        obj = bpy.data.objects.new(name, light)
        obj.location = P(*loc)
        obj.rotation_euler = (P(L / 2, 5, 40) - obj.location).to_track_quat("-Z", "Y").to_euler()
        col.objects.link(obj)

    cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
    col.objects.link(cam)
    scene.camera = cam

    def aim(eye, target, lens):
        cam.data.lens = lens
        cam.location = P(*eye)
        cam.rotation_euler = (P(*target) - cam.location).to_track_quat("-Z", "Y").to_euler()

    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for dev in prefs.devices:
        dev.use = dev.type == "METAL"
    scene.cycles.device = "GPU"
    scene.cycles.samples = 16 if args.small else args.samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.view_settings.view_transform = "AgX"
    folder = ROOT / "renders" / "carcass"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{args.box}_check.txt").write_text("\n".join(report) + "\n")

    lock = open(ROOT / ".render.lock", "w")  # one Cycles process on the GPU at a time (see render.py)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another render is running, waiting for the GPU...", flush=True)
        fcntl.flock(lock, fcntl.LOCK_EX)

    def shoot(path, size):
        scene.render.resolution_x, scene.render.resolution_y = (800, 600) if args.small else size
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        print(path)

    if args.view != "nodes":
        aim(*room["views"][args.view], 18)
        shoot(folder / f"{args.box}{'' if args.view == 'main' else '_' + args.view}{'_small' if args.small else ''}.png",
              (1600, 1200))
        return
    from bpy_extras.object_utils import world_to_camera_view
    aim(*room["views"]["main"], 18)
    overview = folder / f"{args.box}_nodes_overview.png"
    shoot(overview, (1600, 1200))
    w, h = (800, 600) if args.small else (1600, 1200)
    marks_px = []
    for cid, pt in marks:
        v = world_to_camera_view(scene, cam, P(*pt))
        marks_px.append((cid, (v.x * w, (1 - v.y) * h)))
    closeups = []
    for c in box["connections"]:
        if c["type"] == "note":
            continue
        aim(*camera_for(c, box), 35)
        path = folder / f"{args.box}_node_{c['id']}.png"
        shoot(path, (1000, 750))
        closeups.append((c, path))
    title = {"bathroom": "Ванная", "toilet": "Туалет"}[args.box]
    out = folder / f"{args.box}_nodes.png"
    compose(box, f"Каркас короба — {title}: как профили крепятся к раме Grohe Rapid SL", overview, marks_px, closeups,
            plan["frame_rules"], out)
    print(out)


if __name__ == "__main__":
    main()
