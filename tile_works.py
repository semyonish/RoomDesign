"""The tiler's quantities for «Расчёт плитки.pdf», from the layout of tile_layout.py (same numbering): tiles of each
kind, cut length, holes (each found on its tile), 45° miters.

Cut length: the straight cuts of the cut maps («Раскрой»), each through the whole offcut being split, as a tile
cutter makes them (tile_layout.Tile.cuts); plus the edges of the notches in pieces that are not rectangles (around a
door, into a doorway), cut with a grinder.

    .venv/bin/python tile_works.py      # → renders/layout/tile_works.json; then .venv/bin/python pdfs.py works
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

import tile_layout as T
from plans import Model

# hole kinds: (what, hole in the tile, price class); a class is how tilers price holes
KINDS = {
    "wc_drain": ("слив унитаза, труба Ø90", "Ø 100–110", "big"),
    "wc_flush": ("промывочная труба унитаза ≈ Ø45", "Ø 50–55", "mid"),
    "wc_stud": ("шпилька крепления унитаза М12", "Ø 14–16", "small"),
    "water": ("водорозетка ½″", "Ø 30–35", "small"),
    "drain": ("канализация Ø50", "Ø 55–60", "mid"),
    "box": ("подрозетник", "Ø 68", "mid"),
    "plate": ("вырез по защитной коробке инсталляции", "вырез < 15,6 × 19,7", "cutout"),
    "hatch": ("люк-невидимка под плитку", "вырез ≈ 30 × 30", "cutout"),
    "cable": ("кабель датчика протечки", "Ø 8–10 (или в шов)", "small"),
}
CLASSES = [("small", "до Ø 50"), ("mid", "Ø 50–100 (вкл. подрозетники Ø 68)"), ("big", "от Ø 100"),
           ("cutout", "прямоугольные вырезы")]
RADIUS = {"wc_drain": 5.25, "wc_flush": 2.6, "wc_stud": 0.75, "water": 1.75, "drain": 2.9, "box": 3.4}
PLACE = {"plan": "по плану", "assumed": "предложено", "none": "места в плане нет"}


def num(v):   # Russian decimal comma
    return T.num(v).replace(".", ",")


def notch(p):
    """Cut edges of a piece that is not a rectangle, cm: its outline inside its bounding box."""
    mk = p["surf"].ids == p["rid"]
    rr, cc = np.nonzero(mk)
    sub = mk[rr.min():rr.max() + 1, cc.min():cc.max() + 1]
    return float((sub[:, 1:] != sub[:, :-1]).sum() + (sub[1:, :] != sub[:-1, :]).sum()) * T.STEP


def cut_len(tiles):
    return sum(abs(c[2] - c[0]) + abs(c[3] - c[1]) for t in tiles for c in t.cuts)


def pieces_at(surf, u, v, du, dv=None):
    """Labels of the pieces a hole (radius du) or a cutout (half sizes du × dv) at u, v falls on."""
    out = []
    for a in np.linspace(0, 2 * math.pi, 48, endpoint=False):
        for k in (0.0, 0.5, 1.0):
            if dv is None:
                pu, pv = u + k * du * math.cos(a), v + k * du * math.sin(a)
            else:
                pu, pv = u + k * du * max(-1, min(1, 1.5 * math.cos(a))), v + k * dv * max(-1, min(1, 1.5 * math.sin(a)))
            i = int((pu - (surf.gu[0] - T.STEP / 2)) // T.STEP)
            j = int((pv - (surf.gv[0] - T.STEP / 2)) // T.STEP)
            if 0 <= j < surf.ids.shape[0] and 0 <= i < surf.ids.shape[1] and surf.ids[j, i]:
                lab = next(p["label"] for p in surf.pieces if p["rid"] == surf.ids[j, i])
                if lab not in out:
                    out.append(lab)
    return out


def holes(cfg, plan, carcass, m, S):
    """Every hole and cutout in the tile: (room, item, kind, n, place, where, [(surface, plan coordinate, z)])."""
    W = m.walls
    R = {r["id"]: r for r in plan["rooms"]}
    bath, toilet = R["bathroom"]["furniture"], R["toilet"]
    inst = carcass["installation"]
    box = carcass["boxes"]
    out = []

    def add(room, item, kind, place, where, pts=(), n=None):
        out.append(dict(room=room, item=item, kind=kind, n=n or max(1, len(pts)), place=place, where=where,
                        pts=list(pts)))

    def wc(room, surf, axis):   # Grohe Rapid SL: drain, flush pipe, two studs, the plate (plan_carcass installation)
        b = inst["bolt_spacing"] / 2
        add(room, "унитаз подвесной", "wc_drain", "plan", f"лицо короба, ось унитаза, на {num(inst['drain_axis'])}",
            [(surf, axis, inst["drain_axis"])])
        add(room, "унитаз подвесной", "wc_flush", "plan", f"над сливом, на {num(inst['flush_inlet_z'])}",
            [(surf, axis, inst["flush_inlet_z"])])
        add(room, "унитаз подвесной", "wc_stud", "plan",
            f"по бокам слива через {num(inst['bolt_spacing'])}, на {num(inst['bolt_z'])}",
            [(surf, axis - b, inst["bolt_z"]), (surf, axis + b, inst["bolt_z"])])
        add(room, "клавиша смыва", "plate", "plan", f"по оси унитаза, центр на {num(inst['plate_center'])}",
            [(surf, axis, inst["plate_center"])])

    # bathroom: the installation box face (x 82) carries the toilet and the hygienic shower; the right wall the
    # vanity, the mixer over the bath, the mirror; the left wall over the low box the towel warmer
    fp = bath["toilet"]["footprint"]
    wc("ванная", "box_high", (fp[0][1] + fp[2][1]) / 2)
    for h in box["bathroom"]["holes"]:   # s from the rough door wall, y 365
        add("ванная", "гигиенический душ", "water", "plan", f"лицо короба, на {num(h['z'])}",
            [("box_high", 365 + h["s"], h["z"])])
    y = bath["vanity"]["outlets"]["y"]
    add("ванная", "тумба с раковиной: вода", "water", "plan",
        f"правая стена, ось y {num(y)}; высота — по сантехнику (тумба 40–85)", n=2)
    add("ванная", "тумба с раковиной: слив", "drain", "plan", "там же", n=1)
    my = sum(p[1] for p in bath["mixer"]["footprint"]) / 4
    add("ванная", "смеситель над ванной (эксцентрики 150)", "water", "plan", "правая стена, на 80",
        [("bath_right", my - 7.5, 80), ("bath_right", my + 7.5, 80)])
    co = bath["towel_warmer"]["heating"]["cable_outlet"]   # the user's: 5 above the bottom, on the right bar's axis
    add("ванная", "полотенцесушитель электрический: скрытое подключение", "box", "plan",
        f"левая стена, ось правой трубы прибора, на {num(co['z'])} ({num(co['from_bottom'])} от низа прибора)",
        [("bath_left", co["y"], co["z"])])
    add("ванная", "зеркало с подсветкой: питание", "box", "assumed", "правая стена, за зеркалом")

    # toilet: the box face (y 526) carries the toilet, the hygienic shower and the IP44 outlet
    fp = toilet["toilet"]["footprint"]
    wc("туалет", "box_toilet", (fp[0][0] + fp[1][0]) / 2)
    for h in box["toilet"]["holes"]:     # s from the rough left wall, x −103
        kind = "box" if "подрозетник" in h["name"] else "water"
        add("туалет", "розетка IP44 у раковины" if kind == "box" else "гигиенический душ", kind, "plan",
            f"лицо короба, на {num(h['z'])}", [("box_toilet", -103 + h["s"], h["z"])])
    add("туалет", "тумба с раковиной: вода", "water", "none", "правый дальний угол: правая стена или лицо короба",
        n=2)
    add("туалет", "тумба с раковиной: слив", "drain", "none", "там же", n=1)
    add("туалет", "стиральная машина: вода", "water", "none", "правая стена за колонной", n=1)
    add("туалет", "стиральная и сушильная: слив", "drain", "none", "правая стена за колонной", n=1)
    add("туалет", "стиральная и сушильная: розетки", "box", "none", "правая стена за колонной", n=2)
    co = toilet["furniture"]["towel_warmer"]["heating"]["cable_outlet"]   # 5 above the bottom, right rail's axis
    add("туалет", "полотенцесушитель электрический: скрытое подключение", "box", "plan",
        f"левая стена, ось правой стойки прибора, на {num(co['z'])} ({num(co['from_bottom'])} от низа прибора)",
        [("toilet_left", co["y"], co["z"])])
    add("туалет", "зеркало с подсветкой: питание", "box", "assumed", "правая стена, за зеркалом")

    # kitchen backsplash: frames of AtlasDesign posts, 71 mm apart, 86 mm frame
    k = R["kitchen_living"]["furniture_assumed"]["kitchen"]["backsplash_outlets"]
    z = k["bottom_z"] + 4.3
    for it in k["items"]:
        n = round((it["d_to"] - it["d_from"] - 8.6) / 7.1) + 1
        c = (it["d_from"] + it["d_to"]) / 2
        pts = [("splash_kitchen", -422 + c + (i - (n - 1) / 2) * 7.1, z) for i in range(n)]
        add("кухня", f"фартук: {it['item']}", "box", "plan", f"кухонная стена, низ рамки на {num(k['bottom_z'])}",
            pts)

    # bath screen hatch and the leak sensor cables: proposals in plan.json → leak_protection, not decided
    for h in plan["leak_protection"]["hatches"]:
        add("ванная", "люк в экране ванны (если будет)", "hatch", "assumed",
            f"экран, x {num(h['x_from'])}–{num(h['x_to'])}, над подступенком")
    add("ванная, туалет", "кабели датчиков протечки В2, Т1 (если проводные)", "cable", "assumed",
        "у пола: под тумбой ванной, под стиральной", n=2)

    for h in out:   # the tile each hole falls on
        labs = []
        for sk, c, zz in h["pts"]:
            s = S[sk]
            u = W[s.wall].s(c)
            labs.append(pieces_at(s, u, zz, 7.8, 9.85) if h["kind"] == "plate" else
                        pieces_at(s, u, zz, RADIUS[h["kind"]]))
        h["tiles"] = labs
        h["pts"] = [(sk, round(c, 2), round(zz, 2)) for sk, c, zz in h["pts"]]
    return out


# ---------------- joints: grout and corners ----------------
def frames(plan, m, surfaces):
    """Each surface placed in the room: point(u, v) = o + u·eu + v·ev, n — its normal into the room."""
    R = {r["id"]: r for r in plan["rooms"]}
    bath, toilet = R["bathroom"]["furniture"], R["toilet"]
    hi = bath["installation_box"]["footprint"]
    x0, x1, y0, y1 = hi[0][0], hi[1][0], hi[0][1], hi[2][1]          # 61.5, 82, 366.5, 442.5
    h_hi, h_lo = bath["installation_box"]["height"]["value"], bath["pipe_box"]["height"]["value"]
    front = bath["bathtub"]["footprint"][0][1]                       # 474: the screen
    kick = front + bath["bathtub"]["screen"]["kick_depth"]["value"]   # 481: the kick plate
    tbox = toilet["installation_box"]["lower"]["footprint"][0][1]      # 526: the toilet box face
    plane = {"box_high": (x1, None), "box_low": (x1, None), "screen": (None, front), "kick": (None, kick),
             "box_toilet": (None, tbox)}
    parts = {   # box tops and the end, in the u, v of tile_layout.build
        "box_high_top": ((x0, y0, h_hi), (0, 1, 0), (1, 0, 0), (0, 0, 1)),
        "box_high_end": ((0, y1, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
        "box_low_top": ((x0, y1, h_lo), (0, 1, 0), (1, 0, 0), (0, 0, 1)),
    }
    out = {}
    for s in surfaces:
        if s.kind == "floor":
            f = ((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
        elif s.key in parts:
            f = parts[s.key]
        else:
            w = m.walls[s.wall]
            px, py = plane.get(s.key, (None, None))
            d = 0.0 if s.key not in plane else ((px - w.a[0]) * w.n[0] if px is not None else (py - w.a[1]) * w.n[1])
            o = w.pt(0, d)
            f = ((o[0], o[1], 0), (w.u[0], w.u[1], 0), (0, 0, 1), (w.n[0], w.n[1], 0))
        out[s.key] = tuple(np.array(v, float) for v in f)
    return out


def edges(s, f):
    """The outline of a surface's tile as 0.5 cm segments: (midpoint, axis, direction into the tile), in the room."""
    o, eu, ev, _ = f
    t = np.pad(s.ids > 0, 1)
    u0, v0 = s.gu[0] - 1.5 * T.STEP, s.gv[0] - 1.5 * T.STEP   # where cell 0 of the padded raster starts
    out = []
    dv = t[1:, :] != t[:-1, :]                    # between rows j and j+1: a segment along u
    for j, i in zip(*np.nonzero(dv)):
        mid = o + (u0 + (i + 0.5) * T.STEP) * eu + (v0 + (j + 1) * T.STEP) * ev
        out.append((mid, eu, ev if t[j + 1, i] else -ev))
    du = t[:, 1:] != t[:, :-1]                    # between columns i and i+1: a segment along v
    for j, i in zip(*np.nonzero(du)):
        mid = o + (u0 + (i + 1) * T.STEP) * eu + (v0 + (j + 0.5) * T.STEP) * ev
        out.append((mid, ev, eu if t[j, i + 1] else -eu))
    return out


def joints(groups, plan, m, cfg):
    """Grout and corners, cm, per group key: between tiles; between two tiled zones in one plane (a doorway, two box
    faces); inside and outside corners where two tiled planes meet; tile against the bath and the countertop."""
    surfaces = [(g, s) for g in groups for s in g.surfaces]
    F = frames(plan, m, [s for _, s in surfaces])
    res = {g.key: dict(between=0.0, flat=0.0, inner=0.0, outer=0.0, seal=0.0) for g in groups}
    segs, grid = [], {}
    for gi, (g, s) in enumerate(surfaces):
        a = s.ids
        res[g.key]["between"] += float(((a[:, 1:] != a[:, :-1]) & (a[:, 1:] > 0) & (a[:, :-1] > 0)).sum() +
                                       ((a[1:, :] != a[:-1, :]) & (a[1:, :] > 0) & (a[:-1, :] > 0)).sum()) * T.STEP
        for mid, ax, into in edges(s, F[s.key]):
            k = len(segs)
            segs.append((gi, mid, ax, into))
            grid.setdefault(tuple(np.floor(mid / 2).astype(int)), []).append(k)
    used = set()
    order = {g.key: i for i, g in enumerate(groups)}
    seal_keys = {"bath_left", "bath_right", "bath_far", "screen"}
    z_rim = plan["rooms"][[r["id"] for r in plan["rooms"]].index("bathroom")]["furniture"]["bathtub"]["rim_height"]["value"]
    for k, (gi, mid, ax, into) in enumerate(segs):
        if k in used:
            continue
        cell = np.floor(mid / 2).astype(int)
        best = None
        for d in np.ndindex(3, 3, 3):
            for q in grid.get(tuple(cell + np.array(d) - 1), []):
                gq, mq, aq, iq = segs[q]
                if q in used or gq == gi or abs(abs(ax @ aq) - 1) > 1e-6:
                    continue
                dist = np.linalg.norm(mid - mq)
                if dist <= 0.6 and (best is None or dist < best[0]):
                    best = (dist, q)
        g, s = surfaces[gi]
        if best is None:   # an edge against something else: the bath rim and the countertop take sealant
            if (s.key in seal_keys and abs(mid[2] - z_rim) < 0.3 and abs(ax[2]) < 0.5) or \
                    (s.key.startswith("splash_") and abs(mid[2] - cfg["kitchen"]["base_top"]) < 0.3 and abs(ax[2]) < 0.5):
                res[g.key]["seal"] += T.STEP
            continue
        q = best[1]
        used |= {k, q}
        gq, s2 = surfaces[segs[q][0]]
        n1, n2 = F[s.key][3], F[s2.key][3]
        kind = "flat" if n1 @ n2 > 0.99 else ("outer" if into @ n2 < 0 else "inner")
        res[max(g.key, gq.key, key=order.get)][kind] += T.STEP
    return res


def miters(cfg, S):
    """Outside corners tile meets tile: the tile on each side is cut at 45°. (where, length cm)."""
    top, end, low = S["box_high_top"].bounds, S["box_high_end"].bounds, S["box_low_top"].bounds
    k = cfg["kitchen"]
    return [
        ("ванная", "короб инсталляции: лицо / верх", top[1] - top[0]),
        ("ванная", "короб инсталляции: верх / торец", end[1] - end[0]),
        ("ванная", "короб инсталляции: лицо / торец (над низким коробом)", end[3] - end[2]),
        ("ванная", "низкий короб: лицо / верх", low[1] - low[0]),
        ("кухня", "фартук: внешний угол короба стояка", k["upper"]["bottom"] - k["base_top"]),
    ]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--carcass", default="plan_carcass.json")
    ap.add_argument("--json", default="renders/layout/tile_works.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    plan = json.loads(Path(args.plan).read_text())
    carcass = json.loads(Path(args.carcass).read_text())
    m = Model(cfg, plan)
    groups, duna = T.laid(cfg, m)
    S = {s.key: s for g in groups + [duna] for s in g.surfaces}

    grout = joints(groups + [duna], plan, m, cfg)
    zones = []
    for g in groups + [duna]:
        tiles = [t for _, t in g.tiles]
        notched = [(p["label"], p["surf"].title, round(notch(p), 1)) for p in g.pieces if notch(p) > 0]
        z = dict(key=g.key, title=g.title, kind="duna" if g.prefix else "amrita", first=f"{g.prefix}{g.tiles[0][0]}",
                 last=f"{g.prefix}{g.tiles[-1][0]}", tiles=len(tiles), area=round(g.area / 1e4, 2),
                 whole=sum(1 for t in tiles if len(t) == 1 and t[0][0]["full"]),
                 pieces=len(g.pieces), cuts=sum(len(t.cuts) for t in tiles), straight=round(cut_len(tiles) / 100, 2),
                 notched=notched, notch=round(sum(n[2] for n in notched) / 100, 2))
        z["cut_tiles"] = z["tiles"] - z["whole"]
        z["grout"] = {k: round(v / 100, 2) for k, v in grout[g.key].items()}
        z["cut_m"] = round(z["straight"] + z["notch"], 2)
        if any(s.opt for s in g.surfaces):   # no tile behind the cabinets to the ceiling
            alt = T.pack(sum((s.cut(opt_out=True) for s in g.surfaces), []))
            z["without_cabinets"] = dict(tiles=len(alt), cut_m=round(cut_len(alt) / 100 + z["notch"], 2))
        zones.append(z)

    hs = holes(cfg, plan, carcass, m, S)
    ms = [dict(room=r, where=w, cm=round(c, 1)) for r, w, c in miters(cfg, S)]
    am = [z for z in zones if z["kind"] == "amrita"]
    total = dict(
        amrita=sum(z["tiles"] for z in am), amrita_area=round(sum(z["area"] for z in am), 2),
        duna=sum(z["tiles"] for z in zones if z["kind"] == "duna"),
        shared=len(T.pack(sum((g.pieces for g in groups), []))),
        cut_amrita=round(sum(z["cut_m"] for z in am), 1),
        cut_duna=round(sum(z["cut_m"] for z in zones if z["kind"] == "duna"), 1),
        miter_corner=round(sum(x["cm"] for x in ms) / 100, 2),
        grout={k: round(sum(v[k] for v in grout.values()) / 100, 1) for k in ("between", "flat", "inner", "outer", "seal")},
        holes={c: sum(h["n"] for h in hs if KINDS[h["kind"]][2] == c) for c, _ in CLASSES},
        holes_sure={c: sum(h["n"] for h in hs if KINDS[h["kind"]][2] == c and h["place"] == "plan") for c, _ in CLASSES},
    )
    alt = [z["without_cabinets"] for z in zones if "without_cabinets" in z]
    total["without_cabinets"] = dict(
        amrita=total["amrita"] - sum(z["tiles"] - z["without_cabinets"]["tiles"] for z in zones if "without_cabinets" in z),
        cut_amrita=round(total["cut_amrita"] - sum(z["cut_m"] - z["without_cabinets"]["cut_m"]
                                                   for z in zones if "without_cabinets" in z), 1)) if alt else None
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(dict(zones=zones, holes=hs, miters=ms, total=total,
                                   kinds={k: list(v) for k, v in KINDS.items()}, classes=CLASSES, place=PLACE),
                              ensure_ascii=False, indent=1))

    for z in zones:
        print(f"{z['title']:55s} {z['first']}–{z['last']}: {z['tiles']:3d} плиток (целых {z['whole']}), "
              f"резов {z['cuts']} = {z['straight']} м + вырезы {len(z['notched'])} шт {z['notch']} м")
    for z in zones:
        print(f"  {z['title']:55s} затирка {z['grout']}")
    print("затирка всего", total["grout"])
    print("Amrita", total["amrita"], "| Duna", total["duna"], "| подрезка Amrita", total["cut_amrita"], "м, Duna",
          total["cut_duna"], "м | запил 45°", total["miter_corner"], "м угла")
    for h in hs:
        print(f"  {h['room']:8s} {h['item']:55s} {KINDS[h['kind']][1]:18s} ×{h['n']} {PLACE[h['place']]:18s} {h['tiles']}")
    print("отверстия:", total["holes"], "из них по плану:", total["holes_sure"])
    print(out)


if __name__ == "__main__":
    main()
