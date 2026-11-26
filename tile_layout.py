"""Full tile layout: every piece of tile on the floors, the wet-room walls, the boxes, the bath screen and the kitchen
backsplash, numbered by the tile it is cut from — «12» a whole tile, «12а», «12б» pieces cut from tile 12 — so the
number of tiles to buy is the last number. Offcuts go back into the same room (a tiler cuts there) and are never
turned (the veins run along the tile). The accent wall behind the bath (Duna) is numbered on its own: Д1, Д2, …
A piece thinner than 3 cm joins its neighbour in the row: that joint moves by it.

    .venv/bin/python tile_layout.py     # sheets → renders/Рендеры/Раскладка плитки/, cut list → renders/layout/tiles.json
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from plans import BOLD, DIM, FONT, GROUT, JOINT, LABEL, TILE, Model, in_polygon, num, sheet

TW, TH = 120.0, 60.0   # the tile: along its veins × across
PU, PV = TW + GROUT, TH + GROUT   # the grid steps by tile + joint (GROUT, 1 mm); a joint is centred on its grid line
STEP = 0.5             # raster, cm: every edge of the rooms lies on it
H_WET = 267.0
SLIVER = 3.0
LETTERS = "абвгдежзиклмнопрстуфхцчшщэюя"
INK, GREY_TXT = (30, 30, 30), (110, 105, 100)
FACE, FACE_EDGE = (234, 226, 212), (95, 85, 72)            # box faces and the bath screen, in front of the wall
DUNA, DUNA_JOINT, DUNA_INK = (252, 251, 248), (196, 168, 104), (140, 105, 40)
HATCH_BG, HATCH = (243, 243, 243), (205, 205, 205)          # no tile


# ---------------- surfaces → pieces ----------------
def rects_mask(U, V, rects):
    m = np.zeros(U.shape, bool)
    for a, b, c, d in rects:
        m |= (U >= a) & (U < b) & (V >= c) & (V < d)
    return m


def poly_mask(U, V, poly):
    m = np.zeros(U.shape, bool)
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if y1 != y2:
            m ^= ((y1 > V) != (y2 > V)) & (U < (x2 - x1) * (V - y1) / (y2 - y1) + x1)
    return m


def components(mask):
    """Connected pieces of a boolean raster (4-neighbours), each as its own mask: scanline runs joined by union-find."""
    runs, parent, prev = [], [], []

    def find(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for r in range(mask.shape[0]):
        d = np.diff(np.r_[0, mask[r].astype(np.int8), 0])
        cur = []
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
            k = len(runs)
            runs.append((r, s, e))
            parent.append(k)
            for pk in prev:
                if runs[pk][1] < e and s < runs[pk][2]:
                    parent[find(pk)] = find(k)
            cur.append(k)
        prev = cur
    groups = {}
    for k, run in enumerate(runs):
        groups.setdefault(find(k), []).append(run)
    for rs in groups.values():
        m = np.zeros(mask.shape, bool)
        for r, s, e in rs:
            m[r, s:e] = True
        yield m


def label_point(m):
    """The point of a piece farthest inside it, for a label wider than tall."""
    a = m.astype(np.int32)

    def run(x):  # run length up to each cell along axis 1
        out = np.zeros_like(x)
        out[:, 0] = x[:, 0]
        for j in range(1, x.shape[1]):
            out[:, j] = (out[:, j - 1] + 1) * x[:, j]
        return out
    lr = np.minimum(run(a), run(a[:, ::-1])[:, ::-1])
    ud = np.minimum(run(a.T), run(a.T[:, ::-1])[:, ::-1]).T
    rr, cc = np.nonzero(m)
    yy, xx = np.mgrid[0:m.shape[0], 0:m.shape[1]]
    score = np.minimum(lr / 2.0, ud) - 1e-3 * np.hypot(yy - (rr.min() + rr.max()) / 2, xx - (cc.min() + cc.max()) / 2)
    score[~m] = -1e9
    return np.unravel_index(np.argmax(score), m.shape)


class Surface:
    """One tiled plane in its own (u, v) cm: u along the tile's 120, v along its 60. Walls and the faces in front of
    them use the wall's s and the height; floors use plan x, y."""

    def __init__(self, key, title, origin, region=(), excl=(), opt=(), polys=None, minus=(), kind="wall", wall=None,
                 duna=False):
        self.key, self.title, self.origin, self.kind, self.wall, self.duna = key, title, origin, kind, wall, duna
        self.region, self.excl, self.opt, self.polys, self.minus = list(region), list(excl), list(opt), polys, minus
        pts = [(r[0], r[2]) for r in self.region] + [(r[1], r[3]) for r in self.region]
        if polys:
            pts = [q for p in polys for q in p]
        self.bounds = (min(p[0] for p in pts), max(p[0] for p in pts), min(p[1] for p in pts), max(p[1] for p in pts))

    def raster(self, opt_out=False):
        u0, u1, v0, v1 = self.bounds
        self.gu = np.arange(math.floor(u0 / STEP) * STEP + STEP / 2, u1, STEP)
        self.gv = np.arange(math.floor(v0 / STEP) * STEP + STEP / 2, v1, STEP)
        U, V = np.meshgrid(self.gu, self.gv)
        if self.polys:
            keep = np.zeros(U.shape, bool)
            for p in self.polys:
                keep |= poly_mask(U, V, list(p))
            for p in self.minus:
                keep &= ~poly_mask(U, V, list(p))
        else:
            keep = rects_mask(U, V, self.region) & ~rects_mask(U, V, self.excl)
        self.optmask = rects_mask(U, V, self.opt)
        if opt_out:
            keep &= ~self.optmask
        return keep

    def cut(self, opt_out=False):
        keep = self.raster(opt_out)
        gu, gv = self.gu, self.gv
        ci = np.floor((gu - self.origin[0]) / PU).astype(int)
        cj = np.floor((gv - self.origin[1]) / PV).astype(int)
        ids = np.zeros(keep.shape, int)
        out = []
        for i in np.unique(ci):
            cs = np.flatnonzero(ci == i)
            c0, c1 = cs[0], cs[-1] + 1
            for j in np.unique(cj):
                rs = np.flatnonzero(cj == j)
                r0, r1 = rs[0], rs[-1] + 1
                sub = keep[r0:r1, c0:c1]
                if not sub.any():
                    continue
                for comp in components(sub):
                    rr, cc = np.nonzero(comp)
                    if len(rr) * STEP ** 2 < 4:
                        continue
                    free = comp & ~self.optmask[r0:r1, c0:c1]   # the label off the part behind a cabinet
                    lr, lc = label_point(free if free.sum() >= 0.3 * comp.sum() else comp)
                    out.append(dict(surf=self, ci=i, cj=j, u0=gu[c0 + cc.min()] - STEP / 2, u1=gu[c0 + cc.max()] + STEP / 2,
                                    v0=gv[r0 + rr.min()] - STEP / 2, v1=gv[r0 + rr.max()] + STEP / 2,
                                    area=len(rr) * STEP ** 2, lu=gu[c0 + lc], lv=gv[r0 + lr],
                                    opt=float(self.optmask[r0:r1, c0:c1][comp].sum()) * STEP ** 2))
                    ids[r0:r1, c0:c1][comp] = len(out)
        su0, su1, sv0, sv1 = self.edges()
        for p in out:   # the raster finds an edge to half a step: snap it onto the tile edge or wall it lies on
            for k, cands in (("u0", su0), ("u1", su1), ("v0", sv0), ("v1", sv1)):
                c = min(cands, key=lambda c: abs(c - p[k]))
                if abs(c - p[k]) <= STEP * 0.7:
                    p[k] = c
            # never past its own tile: where a wall or a doorway joint lies on a grid line, the joint is left to it
            p["u0"] = max(p["u0"], self.origin[0] + p["ci"] * PU + GROUT / 2)
            p["u1"] = min(p["u1"], self.origin[0] + (p["ci"] + 1) * PU - GROUT / 2)
            p["v0"] = max(p["v0"], self.origin[1] + p["cj"] * PV + GROUT / 2)
            p["v1"] = min(p["v1"], self.origin[1] + (p["cj"] + 1) * PV - GROUT / 2)
        out, ids = merge_slivers(out, ids)
        for k, p in enumerate(out, 1):
            p["rid"] = k   # its cells in `ids` (the list gets sorted later)
            p["w"], p["h"] = p["u1"] - p["u0"], p["v1"] - p["v0"]
            p["full"] = p["w"] >= TW - 0.1 and p["h"] >= TH - 0.1 and p["area"] >= TW * TH - 1
        if not opt_out:
            self.pieces, self.ids = out, ids
        return out


def _edges(self):
    """Where piece edges can lie exactly: a tile starts half a joint past a grid line and ends half a joint before the
    next; and the edges of the surface and what is cut out of it. → starts and ends along u, starts and ends along v."""
    u0, u1, v0, v1 = self.bounds
    ku = range(math.floor((u0 - self.origin[0]) / PU) - 1, math.ceil((u1 - self.origin[0]) / PU) + 2)
    kv = range(math.floor((v0 - self.origin[1]) / PV) - 1, math.ceil((v1 - self.origin[1]) / PV) + 2)
    lu = [self.origin[0] + k * PU for k in ku]
    lv = [self.origin[1] + k * PV for k in kv]
    walls_u, walls_v = set(), set()
    for r in self.region + self.excl + self.opt:
        walls_u |= {r[0], r[1]}
        walls_v |= {r[2], r[3]}
    for poly in (self.polys or []) + list(self.minus):
        walls_u |= {q[0] for q in poly}
        walls_v |= {q[1] for q in poly}
    return (sorted(walls_u | {x + GROUT / 2 for x in lu}), sorted(walls_u | {x - GROUT / 2 for x in lu}),
            sorted(walls_v | {y + GROUT / 2 for y in lv}), sorted(walls_v | {y - GROUT / 2 for y in lv}))


Surface.edges = _edges


def merge_slivers(pieces, ids):
    """A piece under 3 cm joins the piece next to it in the row, if the two still fit one tile."""
    for k, p in enumerate(pieces):
        if p is None or min(p["u1"] - p["u0"], p["v1"] - p["v0"]) >= SLIVER:
            continue
        for qk, q in enumerate(pieces):
            if q is None or qk == k:
                continue
            near = GROUT + 1e-6   # the two sides of a joint
            across_u = (abs(q["u1"] - p["u0"]) < near or abs(q["u0"] - p["u1"]) < near) and \
                q["v0"] < p["v1"] and p["v0"] < q["v1"]
            across_v = (abs(q["v1"] - p["v0"]) < near or abs(q["v0"] - p["v1"]) < near) and \
                q["u0"] < p["u1"] and p["u0"] < q["u1"]
            u0, u1 = min(p["u0"], q["u0"]), max(p["u1"], q["u1"])
            v0, v1 = min(p["v0"], q["v0"]), max(p["v1"], q["v1"])
            if (across_u or across_v) and u1 - u0 <= TW + 1e-6 and v1 - v0 <= TH + 1e-6:
                q.update(u0=u0, u1=u1, v0=v0, v1=v1, area=q["area"] + p["area"], opt=q["opt"] + p["opt"])
                ids[ids == k + 1] = qk + 1
                pieces[k] = None
                break
    remap, out = np.zeros(len(pieces) + 1, int), []
    for k, p in enumerate(pieces):
        if p is not None:
            out.append(p)
            remap[k + 1] = len(out)
    return out, remap[ids]


# ---------------- pieces → tiles ----------------
CUT_MIN = 0.25   # cm: a thinner leftover is not cut off, it goes into the joint


class Tile(list):
    """A tile's pieces as (piece, x, y), and `cuts`: the straight cuts that free them, each (x0, y0, x1, y1) on the
    tile, cm, made through the whole offcut being split, as a tile cutter does."""

    def __init__(self):
        super().__init__()
        self.cuts = []


def pack(pieces, bw=TW, bh=TH):
    """Guillotine cutting: each piece (w along the tile's bw, h along bh) into the offcut it fits best, never turned;
    the leftover is split so the bigger offcut stays whole. A few orders and split rules, the fewest tiles wins.
    Returns tiles as Tile lists of (piece, x, y)."""
    best = None
    orders = [lambda p: (-p["w"] * p["h"], -p["w"]), lambda p: (-p["w"], -p["h"]), lambda p: (-p["h"], -p["w"])]
    for key in orders:
        for rule in (0, 1):
            tiles, free = [], []
            for p in sorted(pieces, key=key):
                w, h = p["w"], p["h"]
                pick = None
                for ti, fr in enumerate(free):
                    for fi, (fx, fy, fw, fh) in enumerate(fr):
                        if w <= fw + 1e-6 and h <= fh + 1e-6:
                            score = min(fw - w, fh - h)
                            if pick is None or score < pick[0]:
                                pick = (score, ti, fi)
                if pick is None:
                    tiles.append(Tile())
                    free.append([(0.0, 0.0, bw, bh)])
                    pick = (0, len(tiles) - 1, 0)
                _, ti, fi = pick
                fx, fy, fw, fh = free[ti].pop(fi)
                tiles[ti].append((p, fx, fy))
                rw, rh = fw - w, fh - h
                across, down = (fx, fy + h, fx + w, fy + h), (fx + w, fy, fx + w, fy + fh)   # first down, then across
                if (rw * fh >= fw * rh) == (rule == 0):
                    new = [(fx + w, fy, rw, fh), (fx, fy + h, w, rh)]
                else:   # first across the whole offcut, then down the piece
                    new = [(fx + w, fy, rw, h), (fx, fy + h, fw, rh)]
                    across, down = (fx, fy + h, fx + fw, fy + h), (fx + w, fy, fx + w, fy + h)
                tiles[ti].cuts += [c for c, r in ((down, rw), (across, rh)) if r > CUT_MIN]
                free[ti] += [r for r in new if r[2] >= 3 and r[3] >= 3]
            if best is None or len(tiles) < len(best):
                best = tiles
    return best


class Group:
    def __init__(self, key, title, surfaces, prefix=""):
        self.key, self.title, self.surfaces, self.prefix = key, title, surfaces, prefix

    def layout(self, first):
        """Cut, pack and number from `first`: tiles in the order their first piece is laid."""
        self.pieces = []
        for s in self.surfaces:
            ps = s.cut()
            if s.kind == "floor" and getattr(s, "rows_down", False):   # from the far rows toward v falling
                ps.sort(key=lambda p: (-p["cj"], p["u0"]))   # row by row of the grid, each left to right
            elif s.kind == "floor":
                ps.sort(key=lambda p: (round(p["v0"]), p["u0"]))
            elif s.kind == "part":
                ps.sort(key=lambda p: (round(p["v0"]), p["u0"]))
            else:   # seen from the room: rows from the floor, left to right (s falls)
                ps.sort(key=lambda p: (round(p["v0"]), -p["u1"]))
            self.pieces += ps
        for i, p in enumerate(self.pieces):
            p["order"] = i
        tiles = pack(self.pieces)
        if any(getattr(s, "rows_down", False) for s in self.surfaces):   # a tile takes the number of its biggest piece
            tiles.sort(key=lambda t: max(t, key=lambda e: (e[0]["area"], -e[0]["order"]))[0]["order"])
        else:   # in the order its first piece is laid
            tiles.sort(key=lambda t: min(p["order"] for p, _, _ in t))
        self.tiles = []
        for n, t in enumerate(tiles, first):
            t.sort(key=lambda e: e[0]["order"])
            for k, (p, x, y) in enumerate(t):
                p["tile"] = n
                p["label"] = f"{self.prefix}{n}" + (LETTERS[k] if len(t) > 1 else "")
                p["at"] = (x, y)
            self.tiles.append((n, t))
        self.area = sum(p["area"] for p in self.pieces)
        return first + len(tiles)

    def without_opt(self):
        """Tiles needed with no tile behind the cabinets that stand to the ceiling."""
        ps = sum((s.cut(opt_out=True) for s in self.surfaces), [])
        return len(pack(ps)), sum(p["area"] for p in ps)


# ---------------- the apartment ----------------
def build(cfg, m):
    W = m.walls
    XR = {r["id"]: r for r in cfg["extra_rooms"]}

    def S(wid, c0, c1):
        return tuple(sorted((W[wid].s(c0), W[wid].s(c1))))

    def zone(origin):
        return next(z for z in m.tiles if z[0] == tuple(origin))

    def floor(key, title, z, minus=()):
        return Surface(key, title, z[0], polys=z[2], minus=minus, kind="floor")

    def wall(key, wid, title, origin_c, z0=0.0, region=None, excl=(), opt=(), kind="wall", duna=False):
        w = W[wid]
        doors = [(s0, s1, 0, 217) for s0, s1 in m.gaps.get(wid, [])]
        return Surface(key, title, (w.s(origin_c), z0), region or [(0, w.len, 0, H_WET)], list(excl) + doors, opt,
                       kind=kind, wall=wid, duna=duna)

    hall_floor = floor("floor_main", "пол прихожей и кухни-гостиной", m.tiles[0])
    hall_floor.rows_down = True   # numbered from the corridor, as it is laid: from the wet rooms to the exit, then on
    lgk = floor("floor_lgk", "пол лоджии кухни-гостиной", zone(XR["loggia_kitchen"]["floor"]["origin"]))
    lgb = floor("floor_lgb", "пол лоджии спальни 1", zone(XR["loggia_bedroom_1"]["floor"]["origin"]))

    # bathroom: the bath against the far wall (front y 474, its screen there, a 7 deep toe recess 10 high from the
    # low box face x 82); boxes along the left wall: installation y 366.5..442.5 to 120, pipe box 442.5..474.5 to 20
    bo = XR["bathroom"]["walls"]["origin"]
    bath_floor = floor("floor_bath", "пол", zone(XR["bathroom"]["floor"]["origin"]), minus=[
        [(61.5, 366.5), (82, 366.5), (82, 552.5), (61.5, 552.5)],      # under the boxes and the bath behind them
        [(82, 481), (239.5, 481), (239.5, 552.5), (82, 552.5)]])        # under the bath, past the toe recess
    bath = [
        bath_floor,
        wall("bath_door", "bath_door", "стена с дверью", bo[0], excl=[(*S("bath_door", 61.5, 82), 0, 120)]),
        wall("bath_left", "bath_left", "левая стена", bo[1], excl=[(*S("bath_left", 474, 552.5), 0, 60),
                                                                 (*S("bath_left", 442.5, 474.5), 0, 20),
                                                                 (*S("bath_left", 366.5, 442.5), 0, 120)]),
        wall("box_high", "bath_left", "лицо короба инсталляции", bo[1], region=[(*S("bath_left", 366.5, 442.5), 0, 120)],
             kind="face"),
        wall("box_low", "bath_left", "лицо низкого короба", bo[1], region=[(*S("bath_left", 442.5, 474.5), 0, 20)],
             kind="face"),
        wall("screen", "bath_far", "экран ванны", bo[0], region=[(*S("bath_far", 61.5, 82), 20, 60),
                                                                (*S("bath_far", 82, 239.5), 10, 60)], kind="face"),
        wall("kick", "bath_far", "подступенок экрана", bo[0], region=[(*S("bath_far", 82, 239.5), 0, 10)], kind="face"),
        wall("bath_right", "bath_right", "правая стена", bo[1], excl=[(*S("bath_right", 474, 552.5), 0, 60)],
             opt=[(*S("bath_right", 368.5, 403.5), 0, H_WET)]),
        Surface("box_high_top", "верх короба инсталляции", (0, 0), [(0, 76, 0, 20.5)], kind="part"),
        Surface("box_high_end", "торец короба инсталляции", (bo[0], 0), [(61.5, 82, 20, 120)], kind="part"),
        Surface("box_low_top", "верх низкого короба", (0, 0), [(0, 32, 0, 20.5)], kind="part"),
    ]
    duna = [wall("bath_far", "bath_far", "стена за ванной", bo[0], region=[(0, W["bath_far"].len, 60, H_WET)],
                 duna=True)]

    # toilet: the box across the far wall to 120 (its top under the cabinet, no tile), a cabinet over it to the
    # ceiling, the washer + dryer column on the right wall by the door
    to = XR["toilet"]["walls"]["origin"]
    toilet = [
        floor("floor_toilet", "пол", zone(XR["toilet"]["floor"]["origin"]),
              minus=[[(-101.5, 526), (46, 526), (46, 552.5), (-101.5, 552.5)]]),
        wall("toilet_door", "toilet_door", "стена с дверью", to[0], opt=[(*S("toilet_door", -14, 46), 0, H_WET)]),
        wall("toilet_left", "toilet_left", "левая стена", to[1], excl=[(*S("toilet_left", 526, 552.5), 0, 120)],
             opt=[(*S("toilet_left", 526, 552.5), 120, H_WET)]),
        wall("toilet_far", "toilet_far", "стена с коробом", to[0], excl=[(0, W["toilet_far"].len, 0, 120)],
             opt=[(0, W["toilet_far"].len, 120, H_WET)]),
        wall("box_toilet", "toilet_far", "лицо короба", to[0], region=[(0, W["toilet_far"].len, 0, 120)], kind="face"),
        wall("toilet_right", "toilet_right", "правая стена", to[1], excl=[(*S("toilet_right", 526, 552.5), 0, 120)],
             opt=[(*S("toilet_right", 368.5, 436.5), 0, H_WET), (*S("toilet_right", 526, 552.5), 120, H_WET)]),
    ]

    # kitchen backsplash: countertop to the upper cabinets, one row, each run from its own tile_origin
    k = cfg["kitchen"]
    z0, z1 = k["base_top"], k["upper"]["bottom"]
    splash = [wall(f"splash_{b['wall']}", b["wall"], "фартук", b["tile_origin"], z0,
                   region=[(*S(b["wall"], *b["span"]), z0, z1)]) for b in k["backsplash"]]
    return [
        Group("main", "Прихожая и кухня-гостиная: пол", [hall_floor]),
        Group("lgk", "Лоджия кухни-гостиной: пол", [lgk]),
        Group("lgb", "Лоджия спальни 1: пол", [lgb]),
        Group("bath", "Ванная: пол, стены, короба, экран ванны", bath),
        Group("toilet", "Туалет: пол, стены, лицо короба", toilet),
        Group("splash", "Кухня: фартук", splash),
    ], Group("duna", "Ванная: стена за ванной — Duna Magnum White Carving", duna, prefix="Д")


def laid(cfg, m):
    """The groups cut, packed and numbered: Amrita 1… through the groups, Duna Д1… on its own."""
    groups, duna = build(cfg, m)
    n = 1
    for g in groups:
        n = g.layout(n)
    duna.layout(1)
    return groups, duna


# ---------------- drawing ----------------
def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, max(9, int(size)))


def label_lines(p):
    """The number, and under it the size of a cut piece; «вырез» when it is not a plain rectangle."""
    cut = not p["full"]
    notch = p["w"] * p["h"] - p["area"] > max(30.0, 0.01 * p["w"] * p["h"])   # not the slant of a skewed wall
    size = f"{num(p['w'])}×{num(p['h'])}" + (" вырез" if notch else "")
    return [p["label"]] + ([size] if cut else []), cut


def fit(lines, w_px, h_px, cap):
    """Font size (px) for a label of these lines inside a w × h box."""
    n = max(len(t) for t in lines)
    return min(cap, 0.36 * h_px if len(lines) > 1 else 0.7 * h_px, 0.85 * w_px / (0.58 * n))


def floor_labels(group, scale):
    out = []
    for p in group.pieces:
        lines, cut = label_lines(p)
        size = fit(lines, p["w"] * scale, p["h"] * scale, 26)
        if len(lines) > 1 and size < 15:   # no room for the size: just the number
            lines = lines[:1]
            size = fit(lines, p["w"] * scale, p["h"] * scale, 26)
        out.append((p["lu"], p["lv"], lines, cut, size / scale))
    return out


def text_box(d, xy, lines, size, fill, anchor_mid=True):
    fb, fr = font(size, True), font(size * 0.78)
    x, y = xy
    y -= (len(lines) - 1) * size * 0.55
    for i, t in enumerate(lines):
        d.text((x, y + i * size * 1.1), t, fill=fill, font=fr if i else fb, anchor="mm")


def put_label(img, xy, lines, wpx, hpx, fill, cap=24):
    """A piece's number (its size under it) centered at xy in a w × h px piece; along a narrow upright strip the
    label turns to run up it."""
    turn = wpx < 34 and hpx > 1.5 * wpx
    bw, bh = (hpx, wpx) if turn else (wpx, hpx)
    size = fit(lines, bw, bh, cap)
    if len(lines) > 1 and size < 13:   # no room for the size: just the number
        lines = lines[:1]
        size = fit(lines, bw, bh, cap)
    size = max(size, 9)
    if not turn:
        text_box(ImageDraw.Draw(img), xy, lines, size, fill)
        return
    f = font(size, True)
    tw, th = int(max(f.getlength(t) for t in lines)) + 6, int(size * 1.15 * len(lines)) + 6
    im = Image.new("RGBA", (tw, th), (255, 255, 255, 0))
    text_box(ImageDraw.Draw(im), (tw / 2, th / 2), lines, size, fill)
    im = im.rotate(90, expand=True)
    img.paste(im, (int(xy[0] - im.width / 2), int(xy[1] - im.height / 2)), im)


def wrap(text, f, width):
    lines = [""]
    for wd in text.split(" "):
        if lines[-1] and f.getlength(f"{lines[-1]} {wd}") > width:
            lines.append(wd)
        else:
            lines[-1] = f"{lines[-1]} {wd}".strip()
    return lines


def hatch(d, box, bg=HATCH_BG, fg=HATCH, step=12):
    x0, y0, x1, y1 = box
    d.rectangle(box, fill=bg)
    for k in range(int(x0 - (y1 - y0)), int(x1), step):
        a, b = (k, y1), (k + (y1 - y0), y0)
        # clip the 45° line to the box
        if a[0] < x0:
            a = (x0, y1 - (x0 - a[0]))
        if b[0] > x1:
            b = (x1, y0 + (b[0] - x1))
        if a[0] <= b[0]:
            d.line([a, b], fill=fg, width=1)


def paint(surf, size_px, color, joint, flip_u, border=None):
    """The surface's pieces as an RGBA image: tile color, a joint along every piece edge, a heavier line around
    the whole surface in `border` (a box face, the bath screen: they stand in front of the wall)."""
    ids = surf.ids[::-1]                           # rows from the top (v falls)
    opt = surf.optmask[::-1]
    if flip_u:
        ids, opt = ids[:, ::-1], opt[:, ::-1]
    im = Image.fromarray(ids.astype(np.int32)).resize(size_px, Image.NEAREST)
    om = Image.fromarray(opt.astype(np.uint8) * 255).resize(size_px, Image.NEAREST)
    a, o = np.array(im), np.array(om) > 0
    on = a > 0
    edge = np.zeros_like(on)
    dx = a[:, 1:] != a[:, :-1]
    dy = a[1:, :] != a[:-1, :]
    edge[:, 1:] |= dx
    edge[:, :-1] |= dx
    edge[1:, :] |= dy
    edge[:-1, :] |= dy
    edge &= on
    rgb = np.zeros(a.shape + (4,), np.uint8)
    rgb[on] = (*color, 255)
    rgb[on & o] = (*[max(0, c - 10) for c in color], 255)
    rgb[edge] = (*joint, 255)
    if border:
        out = np.pad(on, 1, constant_values=False)
        rim = on & ~(out[:-2, 1:-1] & out[2:, 1:-1] & out[1:-1, :-2] & out[1:-1, 2:])
        for _ in range(2):
            r = np.pad(rim, 1, constant_values=False)
            rim |= on & (r[:-2, 1:-1] | r[2:, 1:-1] | r[1:-1, :-2] | r[1:-1, 2:])
        rgb[rim] = (*border, 255)
    return Image.fromarray(rgb, "RGBA")


class Elevations:
    """Walls of a room unfolded side by side as seen from the room, tiles numbered, faces in front drawn on them."""

    def __init__(self, title, panels, parts=(), sc=2.3, notes=()):
        self.title, self.panels, self.parts, self.sc, self.notes = title, panels, parts, sc, notes

    def draw(self, m, path):
        sc, gap, left, top = self.sc, 90, 150, 210
        widths = [(p["L"] - p.get("s0", 0)) * sc for p in self.panels]
        H = max(p["H"] - p.get("z0", 0) for p in self.panels)
        width = int(left + sum(widths) + gap * (len(widths) - 1) + 80)
        parts_h = (max((s.bounds[3] - s.bounds[2]) for s in self.parts) * sc + 160) if self.parts else 0
        notes = [line for t in self.notes for line in wrap(t, font(20), width - 2 * left)]
        height = int(top + H * sc + 150 + parts_h + 32 * len(notes) + 40)
        img = self.img = Image.new("RGB", (width, height), "white")
        d = ImageDraw.Draw(img)
        d.text((left, 50), self.title, fill=INK, font=font(34, True))
        x = left
        for p, wpx in zip(self.panels, widths):
            self.panel(img, d, m, p, x, top, wpx, H)
            x += wpx + gap
        y = top + H * sc + 150
        x = left
        for s in self.parts:   # box tops and ends, each on its own as seen facing it
            u0, u1, v0, v1 = s.bounds
            wpx, hpx = (u1 - u0) * sc, (v1 - v0) * sc
            d.text((x, y), s.title, fill=INK, font=font(20, True))
            box = (x, y + 40, x + wpx, y + 40 + hpx)
            im = paint(s, (int(wpx), int(hpx)), FACE, JOINT, False, FACE_EDGE)
            img.paste(im, (int(box[0]), int(box[1])), im)
            self.labels(d, s, lambda u, v: (x + (u - u0) * sc, y + 40 + (v1 - v) * sc), INK)
            self.chain(d, [u0, u1], lambda u: x + (u - u0) * sc, y + 40 + hpx + 18, True)
            self.chain(d, [v0, v1], lambda v: y + 40 + (v1 - v) * sc, x - 18, False)
            x += max(wpx, d.textlength(s.title, font=font(20, True))) + 120
        y = height - 32 * len(notes) - 20
        for t in notes:
            d.text((left, y), t, fill=GREY_TXT, font=font(20))
            y += 32
        img.save(path)

    def labels(self, d, s, P, ink):
        for p in s.pieces:
            lines, cut = label_lines(p)
            put_label(self.img, P(p["lu"], p["lv"]), lines, p["w"] * self.sc, p["h"] * self.sc, DIM if cut else ink)

    def chain(self, d, pts, X, at, horizontal, full=None):
        pts = sorted(set(round(v, 1) for v in pts))
        f = font(19)
        for a in pts:
            c = X(a)
            if horizontal:
                d.line([c, at - 8, c, at + 8], fill=INK, width=2)
            else:
                d.line([at - 8, c, at + 8, c], fill=INK, width=2)
        if horizontal:
            d.line([X(pts[0]), at, X(pts[-1]), at], fill=INK, width=2)
        else:
            d.line([at, X(pts[0]), at, X(pts[-1])], fill=INK, width=2)
        for a, b in zip(pts, pts[1:]):
            t = num(b - a)
            red = full is not None and abs(b - a - full) > 0.3
            c = (X(a) + X(b)) / 2
            if horizontal:
                d.text((c, at + 16), t, fill=DIM if red else INK, font=f, anchor="mm")
            else:
                im = Image.new("RGBA", (int(f.getlength(t)) + 6, 26), (255, 255, 255, 0))
                ImageDraw.Draw(im).text((im.width / 2, 13), t, fill=DIM if red else INK, font=f, anchor="mm")
                im = im.rotate(90, expand=True)
                self.img.paste(im, (int(at - 18 - im.width / 2), int(c - im.height / 2)), im)

    def panel(self, img, d, m, p, x, top, wpx, H):
        sc, L, s0 = self.sc, p["L"], p.get("s0", 0)   # the panel shows the wall from s0 to L
        z0 = p.get("z0", 0)
        Hp = p["H"] - z0
        y0 = top + (H - Hp) * sc

        def P(s, z):   # wall s, height z → sheet; seen from the room s runs right to left
            return x + (L - s) * sc, y0 + (p["H"] - z) * sc
        box = (x, y0, x + wpx, y0 + Hp * sc)
        hatch(d, box)
        for s in p["surfaces"]:
            u0, u1, v0, v1 = s.bounds
            a, b = P(u1, v1), P(u0, v0)
            col, jnt = (DUNA, DUNA_JOINT) if s.duna else ((FACE, JOINT) if s.kind == "face" else (TILE, JOINT))
            im = paint(s, (round(b[0] - a[0]), round(b[1] - a[1])), col, jnt, True,
                       FACE_EDGE if s.kind == "face" else None)
            img.paste(im, (round(a[0]), round(a[1])), im)
        for o0, o1, t in p.get("openings", []):
            a, b = P(o1, 217), P(o0, 0)
            d.rectangle([a[0], a[1], b[0], b[1]], fill="white", outline=INK, width=2)
            d.text(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), t, fill=GREY_TXT, font=font(20), anchor="mm")
        for r, t in p.get("dashed", []):   # cabinets to the ceiling: tile behind them, could be left out
            a, b = P(r[1], r[3]), P(r[0], r[2])
            for k in range(int(a[0]), int(b[0]), 16):
                d.line([k, a[1], min(k + 8, b[0]), a[1]], fill=INK, width=2)
                d.line([k, b[1], min(k + 8, b[0]), b[1]], fill=INK, width=2)
            for k in range(int(a[1]), int(b[1]), 16):
                d.line([a[0], k, a[0], min(k + 8, b[1])], fill=INK, width=2)
                d.line([b[0], k, b[0], min(k + 8, b[1])], fill=INK, width=2)
            # named over the wall, above the cabinet
            d.line([(a[0] + b[0]) / 2, y0 - 14, (a[0] + b[0]) / 2, y0], fill=INK, width=2)
            d.text(((a[0] + b[0]) / 2, y0 - 26), t, fill=INK, font=font(17), anchor="mm")
        for r, t in [n for n in p.get("notes", []) if n[1]]:   # where there is no tile
            a, b = P(r[1], r[3]), P(r[0], r[2])
            tb = d.textbbox(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), t, font=font(17), anchor="mm")
            d.rectangle([tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2], fill=HATCH_BG)
            d.text(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), t, fill=GREY_TXT, font=font(17), anchor="mm")
        d.rectangle(box, outline=INK, width=3)
        for s in p["surfaces"]:
            self.labels(d, s, P, DUNA_INK if s.duna else INK)
        # joints along the wall where its tile meets the floor or the countertop, and the rows up it
        main = p["surfaces"][0]
        o = main.origin
        js = [o[0] + k * PU for k in range(math.floor(-o[0] / PU), math.ceil((L - o[0]) / PU) + 1)]
        self.chain(d, [s0, L] + [s for s in js if s0 + 0.5 < s < L - 0.5], lambda s: x + (L - s) * sc, box[3] + 22,
                   True, PU)
        self.chain(d, [s0, L], lambda s: x + (L - s) * sc, box[3] + 62, True)
        zs = [z0 + k * PV for k in range(int((p["H"] - z0) // PV) + 1)]
        self.chain(d, [z0, p["H"]] + [z for z in zs if z0 < z < p["H"] - 0.5], lambda z: y0 + (p["H"] - z) * sc,
                   x - 20, False, PV)
        d.text((x, y0 - 80), p["title"], fill=INK, font=font(22, True))


def cut_sheet(groups, path, title):
    """Each tile cut into pieces, as cut: the pieces where they come out of the tile, the rest offcut."""
    sc, gap, cols, left = 2.0, 34, 6, 60
    cw, ch = TW * sc, TH * sc
    blocks = []
    for g in groups:
        cut = [(n, t) for n, t in g.tiles if not (len(t) == 1 and t[0][0]["full"])]
        whole = [n for n, t in g.tiles if len(t) == 1 and t[0][0]["full"]]
        blocks.append((g, cut, whole))
    height = 120 + sum(110 + math.ceil(len(c) / cols) * (ch + 58) for _, c, _ in blocks)
    width = int(left * 2 + cols * cw + (cols - 1) * gap)
    img = Image.new("RGB", (width, int(height)), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 40), title, fill=INK, font=font(34, True))
    y = 120
    for g, cut, whole in blocks:
        duna = g.prefix == "Д"
        d.text((left, y), f"{g.title} — {len(g.tiles)} плиток: целых {len(whole)}, режутся {len(cut)}",
               fill=INK, font=font(24, True))
        d.text((left, y + 36), "целые: " + (ranges(whole, g.prefix) or "—"), fill=GREY_TXT, font=font(19))
        y += 84
        for i, (n, t) in enumerate(cut):
            cx = left + (i % cols) * (cw + gap)
            cy = y + (i // cols) * (ch + 58)
            d.text((cx, cy), f"{g.prefix}{n}", fill=INK, font=font(20, True))
            bx, by = cx, cy + 26
            hatch(d, (bx, by, bx + cw, by + ch))
            for p, px, py in t:
                a = (bx + px * sc, by + py * sc)
                b = (a[0] + p["w"] * sc, a[1] + p["h"] * sc)
                d.rectangle([a, b], fill=DUNA if duna else TILE, outline=DUNA_JOINT if duna else JOINT, width=2)
                put_label(img, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), label_lines(p)[0], b[0] - a[0], b[1] - a[1],
                          DUNA_INK if duna else INK, 20)
            d.rectangle([bx, by, bx + cw, by + ch], outline=INK, width=2)
        y += math.ceil(len(cut) / cols) * (ch + 58) + 26
    img.save(path)


def ranges(ns, prefix=""):
    out, ns = [], sorted(ns)
    i = 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(f"{prefix}{ns[i]}" if i == j else f"{prefix}{ns[i]}–{prefix}{ns[j]}")
        i = j + 1
    return ", ".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--out", default="renders/Рендеры/Раскладка плитки")
    ap.add_argument("--json", default="renders/layout/tiles.json")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    m = Model(cfg, json.loads(Path(args.plan).read_text()))
    groups, duna = laid(cfg, m)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    W = m.walls
    G = {g.key: g for g in groups}
    S = {s.key: s for g in groups + [duna] for s in g.surfaces}

    def sb(wid, c0, c1):
        return tuple(sorted((W[wid].s(c0), W[wid].s(c1))))

    # floors: the tile layout sheets of plans.py with every piece numbered
    sheets = []
    for rid, gk in (("hall", "main"), ("kitchen_living", "main"), ("loggia_kitchen", "lgk"),
                    ("loggia_bedroom_1", "lgb"), ("bathroom", "bath"), ("toilet", "toilet")):
        name, poly = next((nm, p) for r, nm, p in m.rooms if r == rid)
        m.tile_labels = floor_labels(G[gk], 3.0)
        box = (min(p[0] for p in poly) - 25, max(p[0] for p in poly) + 25,
               min(p[1] for p in poly) - 25, max(p[1] for p in poly) + 25)
        sheets.append((f"Пол — {name}", sheet(m, box, 3.0, f"Раскладка плитки на полу — {name}", "tiles", poly)))
    m.tile_labels = ()

    def panel(wid, title, surfs, **kw):
        return dict(L=W[wid].len, H=H_WET, title=title, surfaces=[S[k] for k in surfs], **kw)

    bath = Elevations("Раскладка плитки на стенах — Ванная (развёртка, вид из комнаты)", [
        panel("bath_door", "1. Стена с дверью", ["bath_door"],
              openings=[(*m.gaps["bath_door"][0], "дверь")],
              notes=[((*sb("bath_door", 61.5, 82), 0, 120), "короб")]),
        panel("bath_left", "2. Левая стена: короб инсталляции", ["bath_left", "box_high", "box_low"],
              notes=[((*sb("bath_left", 474.5, 552.5), 0, 60), "за ванной")]),
        panel("bath_far", "3. За ванной: Duna, ниже борта — экран", ["bath_far", "screen", "kick"],
              notes=[((*sb("bath_far", 61.5, 82), 0, 20), "")]),
        panel("bath_right", "4. Правая стена: пенал, раковина", ["bath_right"],
              dashed=[((*sb("bath_right", 368.5, 403.5), 0, H_WET), "за пеналом")],
              notes=[((*sb("bath_right", 474, 552.5), 0, 60), "за ванной")]),
    ], parts=[S["box_high_top"], S["box_high_end"], S["box_low_top"]], notes=[
        "Плитка 120 × 60 горизонтально, шов 1 мм, швы в линию с полом; ряды по 60 от пола. Номер — плитка, из которой "
        "вырезан кусок: «12» — целая, «12а», «12б» — куски плитки 12 (см. лист «Раскрой»); красным — подрезка, с размером.",
        "Стены — по чистовой (по лицу плитки). Лицо коробов, экран и подступенок — в плоскости перед стеной, обведены. "
        "Ниже борта за ванной плитки нет. Пунктир — шкаф до потолка: плитка за ним в счёте, её можно не класть.",
    ])
    bath.draw(m, out / "_bath.png")
    toilet = Elevations("Раскладка плитки на стенах — Туалет (развёртка, вид из комнаты)", [
        panel("toilet_door", "1. Стена с дверью", ["toilet_door"],
              openings=[(*m.gaps["toilet_door"][0], "дверь")],
              dashed=[((*sb("toilet_door", -14, 46), 0, H_WET), "за колонной")]),
        panel("toilet_left", "2. Левая стена", ["toilet_left"],
              dashed=[((*sb("toilet_left", 526, 552.5), 120, H_WET), "шкаф")],
              notes=[((*sb("toilet_left", 526, 552.5), 0, 120), "короб")]),
        panel("toilet_far", "3. Короб и шкаф над ним", ["toilet_far", "box_toilet"],
              dashed=[((0, W["toilet_far"].len, 120, H_WET), "за шкафом над коробом")]),
        panel("toilet_right", "4. Правая стена: колонна, раковина", ["toilet_right"],
              dashed=[((*sb("toilet_right", 368.5, 436.5), 0, H_WET), "за колонной стирки и сушки"),
                      ((*sb("toilet_right", 526, 552.5), 120, H_WET), "шкаф")],
              notes=[((*sb("toilet_right", 526, 552.5), 0, 120), "короб")]),
    ], notes=[
        "Плитка 120 × 60 горизонтально, шов 1 мм; по ширине от левого угла, от лица короба целая 120; ряды по 60 от пола "
        "(шов по верху короба 120). Номер — плитка, из которой вырезан кусок; красным — подрезка, с размером.",
        "Верх короба — без плитки (ГКЛ, на нём шкаф). Пунктир — шкафы до потолка: плитка за ними в счёте, её можно не класть.",
    ])
    toilet.draw(m, out / "_toilet.png")
    k = cfg["kitchen"]
    splash = Elevations("Фартук кухни (развёртка, вид из комнаты)", [
        dict(s0=sb(b["wall"], *b["span"])[0], L=sb(b["wall"], *b["span"])[1], H=k["upper"]["bottom"], z0=k["base_top"],
             surfaces=[S[f"splash_{b['wall']}"]], title=t)
        for b, t in sorted(zip(k["backsplash"], ["стена кухни", "у дивана", "короб, бок", "короб"]),   # unfolded
                           key=lambda e: ["kitchen", "riser_front", "riser_side", "sofa"].index(e[0]["wall"]))
    ], sc=3.0, notes=["Плитка пола 120 × 60, один ряд от столешницы до навесных шкафов; на каждой стене — от своего края "
                      "(tile_origin). Внешний угол короба — запил 45°."])
    splash.draw(m, out / "_splash.png")
    groups_all = groups + [duna]
    cut_sheet(groups[:3] + groups[5:], out / "_cuts1.png", "Раскрой плиток — полы и фартук")
    cut_sheet([groups[3], groups[4], duna], out / "_cuts2.png", "Раскрой плиток — ванная и туалет")

    names = [s[0] for s in sheets] + ["Ванная — стены", "Туалет — стены", "Кухня — фартук", "Раскрой — полы и фартук",
                                      "Раскрой — ванная и туалет"]
    files = []
    for i, (nm, im) in enumerate(sheets, 1):
        f = out / f"{i:02d} {nm}.png"
        im.save(f)
        files.append(f)
    for i, (nm, tmp) in enumerate(zip(names[len(sheets):], ["_bath", "_toilet", "_splash", "_cuts1", "_cuts2"]),
                                  len(sheets) + 1):
        f = out / f"{i:02d} {nm}.png"
        (out / f"{tmp}.png").rename(f)
        files.append(f)

    summary = []
    for g in groups_all:
        whole = sum(1 for _, t in g.tiles if len(t) == 1 and t[0][0]["full"])
        alt = g.without_opt() if any(s.opt for s in g.surfaces) else None
        summary.append(dict(key=g.key, title=g.title, first=g.tiles[0][0], last=g.tiles[-1][0], tiles=len(g.tiles),
                            whole=whole, pieces=len(g.pieces), area=round(g.area / 1e4, 2),
                            without_cabinets=dict(tiles=alt[0], area=round(alt[1] / 1e4, 2)) if alt else None,
                            cuts=[dict(tile=f"{g.prefix}{n}", pieces=[dict(label=p["label"], w=p["w"], h=p["h"],
                                                                            where=p["surf"].title) for p, _, _ in t])
                                  for n, t in g.tiles]))
    js = Path(args.json)
    js.parent.mkdir(parents=True, exist_ok=True)
    shared = len(pack(sum((g.pieces for g in groups), [])))   # offcuts carried from room to room
    js.write_text(json.dumps(dict(groups=summary, shared=shared, sheets=[str(f) for f in files]), ensure_ascii=False,
                             indent=1))
    for s in summary:
        alt = s["without_cabinets"]
        print(f"{s['title']:55s} №{s['first']}–{s['last']}: {s['tiles']:3d} плиток (целых {s['whole']}), "
              f"кусков {s['pieces']}, {s['area']} м²" + (f"; без плитки за шкафами {alt['tiles']} ({alt['area']} м²)"
                                                      if alt else ""))
    print("Amrita всего:", sum(s["tiles"] for s in summary if s["key"] != "duna"), "| с обрезками между комнатами:", shared)
    for f in files:
        print(f)


if __name__ == "__main__":
    main()
