"""Quantities for «Расчёт материалов»: wallpaper wall areas, loggia paint, stretch ceiling canvas and profile, lamps.
Reads plan.json + rooms/apartment.json; tile is counted piece by piece in tile_layout.py, wallpaper rolls in
wallpaper_layout.py.

    .venv/bin/python stats.py
"""
import json
import math
from pathlib import Path

from plans import Model, in_polygon

ROOT = Path(__file__).resolve().parent
cfg = json.loads((ROOT / "rooms/apartment.json").read_text())
plan = json.loads((ROOT / "plan.json").read_text())
m = Model(cfg, plan)
W = m.walls
H_DRY = 270.0
SEAM_Y = -16.0   # stretch ceiling seam between the hall and the kitchen-living room


def area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def rect_union(rects):
    """Exact area of a union of axis-aligned rectangles (s0, s1, z0, z1)."""
    rects = [r for r in rects if r[1] > r[0] and r[3] > r[2]]
    if not rects:
        return 0.0
    xs = sorted({v for r in rects for v in r[:2]})
    tot = 0.0
    for a, b in zip(xs, xs[1:]):
        iv = sorted((r[2], r[3]) for r in rects if r[0] <= a and r[1] >= b)
        cov, cur = 0.0, None
        for z0, z1 in iv:
            if cur is None or z0 > cur[1]:
                if cur:
                    cov += cur[1] - cur[0]
                cur = [z0, z1]
            else:
                cur[1] = max(cur[1], z1)
        if cur:
            cov += cur[1] - cur[0]
        tot += (b - a) * cov
    return tot


def clip(r, L, H):
    return (max(0, r[0]), min(L, r[1]), max(0, r[2]), min(H, r[3]))


def s_of(w, c0, c1):
    return tuple(sorted((w.s(c0), w.s(c1))))


# ---------------- openings per wall (s0, s1, z0, z1) ----------------
openings = {}
for wid, gaps in m.gaps.items():
    for s0, s1 in gaps:
        openings.setdefault(wid, []).append((s0, s1, 0.0, 217.0))
for win in cfg["windows"]:
    w = W[win["wall"]]
    for p in win["parts"]:
        s0, s1 = sorted(w.s(c) for c in p["span"])
        openings.setdefault(w.id, []).append((s0, s1, p["z"][0], p["z"][1]))

# ---------------- the kitchen backsplash: the only wall without wallpaper (behind cabinets it is papered) ----------------
K = cfg["kitchen"]
splash_spec = {b["wall"]: b["span"] for b in K["backsplash"]}   # countertop to the upper cabinets
SPLASH_Z = (K["base_top"], K["upper"]["bottom"])
NICHE = ["niche_step", "niche_side", "niche_top", "niche_jog", "pier_back"]   # the niche of the kitchen-living room

rooms_dry = {
    "Прихожая": ["entrance", "hall_right", "hall_right_br1", "hall_far", "hall_left", "pier_end"],
    "Кухня-гостиная": ["tv", "window", "sofa", "riser_side", "riser_front", "kitchen"] + NICHE,
}
XR = {r["id"]: r for r in cfg["extra_rooms"]}
NAMES = {"bedroom_1": "Спальня 1", "study": "Кабинет", "bedroom_2": "Спальня 2", "bathroom": "Ванная",
         "toilet": "Туалет", "loggia_kitchen": "Лоджия кухни-гостиной", "loggia_bedroom_1": "Лоджия спальни 1"}
for rid in ("bedroom_1", "study", "bedroom_2"):
    rooms_dry[NAMES[rid]] = [w["id"] for w in XR[rid]["outline"]]

print("=" * 30, "ОБОИ (высота", H_DRY, ")")
tot = dict(gross=0, op=0, net=0, cov=0, vis=0, perim=0)
for name, wids in rooms_dry.items():
    g = op = cov = vis = per = 0
    rows = []
    for wid in wids:
        w = W[wid]
        L = w.len
        ops = [clip(r, L, H_DRY) for r in openings.get(wid, [])]
        covs = [(*s_of(w, *splash_spec[wid]), *SPLASH_Z)] if wid in splash_spec else []
        a_op = rect_union(ops)
        a_free = L * H_DRY - rect_union(ops + covs)
        g += L * H_DRY
        op += a_op
        vis += a_free
        per += L
        rows.append((wid, L, a_op, L * H_DRY - a_op, a_free))
    net = g - op
    cov = net - vis
    print(f"\n{name}: периметр {per/100:.2f} м | стены {g/1e4:.2f} | проёмы {op/1e4:.2f} | за вычетом проёмов {net/1e4:.2f} "
          f"| фартук {cov/1e4:.2f} | под обои {vis/1e4:.2f}")
    for wid, L, a_op, n, v in rows:
        print(f"   {wid:16s} L={L:6.1f}  проёмы {a_op/1e4:5.2f}  нетто {n/1e4:5.2f}  под обои {v/1e4:5.2f}")
    for k, v in zip(("gross", "op", "net", "cov", "vis", "perim"), (g, op, net, cov, vis, per)):
        tot[k] += v
print(f"\nИТОГО: периметр {tot['perim']/100:.2f} м | стены {tot['gross']/1e4:.2f} | проёмы {tot['op']/1e4:.2f} | "
      f"нетто {tot['net']/1e4:.2f} | фартук {tot['cov']/1e4:.2f} | под обои {tot['vis']/1e4:.2f}")

# loggias: painted walls; the room-side wall has the balcony door and window of the room (behind insulation)
print("\n" + "=" * 30, "ПОКРАСКА ЛОДЖИЙ (высота", H_DRY, ")")
room_side = {"lgk_room": "window", "lgb_room": "br1_balcony"}
for rid in ("loggia_kitchen", "loggia_bedroom_1"):
    g = op = per = 0
    for w0 in XR[rid]["outline"]:
        w = W[w0["id"]]
        ops = [clip(r, w.len, H_DRY) for r in openings.get(w.id, [])]
        if w.id in room_side:
            src = next(x for x in cfg["windows"] if x["wall"] == room_side[w.id])
            ops += [clip((*s_of(w, *p["span"]), *p["z"]), w.len, H_DRY) for p in src["parts"]]
        g += w.len * H_DRY
        op += rect_union(ops)
        per += w.len
    print(f"  {NAMES[rid]}: периметр {per/100:.2f} м | стены {g/1e4:.2f} | проёмы {op/1e4:.2f} | под покраску {(g-op)/1e4:.2f}")

# ---------------- ceiling ----------------
print("\n" + "=" * 30, "НАТЯЖНОЙ ПОТОЛОК")
main = cfg["outline"]
main_poly = [tuple(w["from"]) for w in main]
hl = W["hall_left"]
t = (SEAM_Y - hl.a[1]) / (hl.b[1] - hl.a[1])
xs = hl.a[0] + t * (hl.b[0] - hl.a[0])
hall_poly = [(0, 0), (240, 0), (240, 246), (240, 351), (-103, 351), (xs, SEAM_Y), (0, SEAM_Y), (0, -10)]
hall_walls = sum(W[i].len for i in ("entrance", "hall_right", "hall_right_br1", "hall_far", "pier_end")) \
    + math.hypot(hl.a[0] - xs, hl.a[1] - SEAM_Y)
main_per = sum(W[w["id"]].len for w in main)
seam = abs(xs)


def corners(poly):
    inner = outer = 0
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i - 1], poly[i], poly[(i + 1) % n]
        u = (b[0] - a[0], b[1] - a[1])
        v = (c[0] - b[0], c[1] - b[1])
        cr = u[0] * v[1] - u[1] * v[0]
        if abs(cr) < 1e-6 * math.hypot(*u) * math.hypot(*v):
            continue
        if cr > 0:
            inner += 1
        else:
            outer += 1
    return inner, outer


canv = []
a_main = area(main_poly)
a_hall = area(hall_poly)
canv.append(("Прихожая", a_hall, hall_walls))
canv.append(("Кухня-гостиная", a_main - a_hall, main_per - hall_walls))
for r in cfg["extra_rooms"]:
    poly = [tuple(w["from"]) for w in r["outline"]]
    canv.append((r["id"], area(poly), sum(W[w["id"]].len for w in r["outline"])))
print("стены main outline: углы (внутр, наруж):", corners(main_poly))
for r in cfg["extra_rooms"]:
    print(r["id"], "углы", corners([tuple(w["from"]) for w in r["outline"]]))
for name, a, p in canv:
    print(f"  {name:16s} полотно {a/1e4:6.2f} м²   периметр (профиль по стенам) {p/100:6.2f} м")
print(f"  ИТОГО полотно {sum(c[1] for c in canv)/1e4:.2f} м²  профиль {sum(c[2] for c in canv)/100:.2f} м")
print(f"  шов прихожая/гостиная (разделительный) y={SEAM_Y}: {seam/100:.2f} м  (x {xs:.2f}..0)")
for it in cfg["furniture"]:
    if it["type"] == "curtains" and it.get("cornice") == "slot":
        print(f"  карниз в потолке: стена {it['wall']:12s} {W[it['wall']].len/100:.2f} м")

# lights per room
print("  светильники:")
room_polys = {"Прихожая": hall_poly, "Кухня-гостиная": None}
for r in cfg["extra_rooms"]:
    room_polys[r["id"]] = [tuple(w["from"]) for w in r["outline"]]
cnt = {}
for f in cfg["ceiling_lights"]["fixtures"]:
    x, y = f["at"]
    rn = next((k for k, p in room_polys.items() if p and in_polygon(x, y, p)), "Кухня-гостиная")
    c = f.get("count", 2)
    d = cnt.setdefault(rn, {1: 0, 2: 0, 3: 0})
    d[c] += 1
for k, d in cnt.items():
    print(f"    {k:16s} одинарных {d[1]}, двойных {d[2]}, тройных {d[3]} → корпусов {sum(d.values())}, ламп {d[1] + 2*d[2] + 3*d[3]}")
