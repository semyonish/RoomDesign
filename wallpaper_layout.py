"""Wallpaper layout: each room's walls unfolded as seen from inside, cut into strips a roll wide, every strip numbered
with the rolls it is cut from, every roll with the pieces it gives; the rolls to buy are counted per article.
Wallpaper goes behind the cabinets too; only the kitchen backsplash (countertop to the upper cabinets) has none.
Strips run left to right from a corner, on across corners (a strip is cut there, its rest goes on the next wall) and
across doors, windows and the backsplash (over a door the strip is a short piece). Andrea Rossi Spectrum Plus, plain,
rapport 0: a piece is the height it covers + 10 cm to trim. The study is 54355-7, every other room 54355-3 (ARTICLE).
The hall and the kitchen-living room share one outline; they are split at the outer corner by the arch.
The rolls of a zone stay in it (ZONES): the hall and the kitchen-living room are papered together from shared rolls,
every other room from its own; for comparison, the rolls each room takes on its own and those all the rooms of an
article take with offcuts carried between them. Two narrow strips may share one length of a roll.
The PDF is wallpaper_pdf.py (pdfs.py wallpaper), from the json.

    .venv/bin/python wallpaper_layout.py               # → renders/Рендеры/Раскладка обоев/, renders/layout/wallpaper.json
    .venv/bin/python wallpaper_layout.py --count       # just the counts
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from plans import DIM, Model, num
from tile_layout import GREY_TXT, INK, font, hatch, pack, put_label, wrap

H, ALLOW = 270.0, 10.0   # floor to slab; trimming, top and bottom
DOOR_H = 217.0
MIN_STRIP = 15.0   # cm: no narrower strip at the end of a run
SPLASH = "фартук"   # the kitchen backsplash (tiled) is the only wall without wallpaper; behind cabinets it is papered
WALL_NAMES = {
    "entrance": "входная дверь", "hall_right_br1": "дверь спальни 1", "hall_far": "двери санузлов",
    "hall_left": "двери спальни 2 и кабинета", "tv": "стена ТВ", "window": "окно, балконная дверь",
    "sofa": "у дивана", "kitchen": "кухня", "pier_end": "простенок",
    "br1_door": "стена с дверью", "br1_tv": "стена ТВ", "br1_balcony": "окно, балконная дверь", "br1_head": "изголовье",
    "st_door": "стена с дверью", "st_right": "к спальне 2", "st_far": "окно", "st_left": "к гостиной",
    "b2_door": "стена с дверью", "b2_right": "наружная", "b2_far": "окно", "b2_left": "к кабинету",
    "hall_right": "шкаф-купе", "riser_side": "короб стояка", "riser_front": "короб стояка", "niche_step": "ниша шкафа",
    "niche_side": "ниша шкафа", "niche_top": "ниша шкафа", "niche_jog": "ниша шкафа", "pier_back": "ниша шкафа",
    "st_pocket_end": "ниша шкафа-купе", "st_pocket_side": "ниша шкафа-купе",
}
ROLL_COLORS = [(250, 226, 200), (208, 228, 247), (214, 238, 214), (243, 214, 236), (246, 240, 196),
               (220, 214, 246), (198, 236, 236), (245, 214, 210)]
PRODUCT = "Andrea Rossi Spectrum Plus"
ARTICLE = {"hall": "54355-3", "kitchen_living": "54355-3", "bedroom_1": "54355-3", "bedroom_2": "54355-3",
           "study": "54355-7"}
ZONES = [["hall", "kitchen_living"], ["bedroom_1"], ["bedroom_2"], ["study"]]   # rooms papered from shared rolls
# seams (--seams): full-height cabinets hide a seam behind them (plan coordinates along the wall), so does the casing
# of a door; walls at least MAJOR long are laid out each from its own corner, shorter ones are wrapped
CABINETS = {
    "hall_right": [(0, 240)], "entrance": [(180, 240)], "kitchen": [(-402, -111.2)], "sofa": [(-181.8, -20)],
    "riser_side": [(-422, -402)], "riser_front": [(-20, 0)], "br1_door": [(367, 549)], "br1_head": [(254, 394.3)],
    "st_pocket_end": [(-567, -477)], "st_pocket_side": [(-97, -27)], "st_door": [(-24, 106)], "st_left": [(-179, -119)],
    "b2_door": [(371, 551)], "b2_right": [(-179.4, -119)],
}
NICHE = ["niche_step", "niche_side", "niche_top", "niche_jog", "pier_back"]   # the niche cabinet, to the ceiling
CASING = 5.0    # cm of a door casing on the wall, beside the opening and over it
MAJOR = 30.0


def chain(ids, first, last):
    """The walls of a closed outline from first to last, in outline order, wrapping around its start."""
    i = ids.index(first)
    ids = ids[i:] + ids[:i]
    return ids[:ids.index(last) + 1]


class Room:
    def __init__(self, key, name, m, windows, wall_ids, W, splash=(), closed=True):
        """wall_ids: round the room (closed), or a run of walls from one open end to the other (the hall, the
        kitchen-living room); the strips go from the start of the unfolding to its end. splash: (wall, span, z0, z1)
        of the kitchen backsplash."""
        self.key, self.name, self.W, self.article, self.closed = key, name, W, ARTICLE[key], closed
        segs, t = [], 0.0
        for wid in reversed(wall_ids):   # seen from inside, left to right: against the outline's direction
            w = m.walls[wid]
            segs.append(dict(w=w, t0=t, L=w.len))
            t += w.len
        P = t
        opens = []
        for g in segs:
            w = g["w"]

            def T(s, g=g):
                return g["t0"] + g["L"] - s
            for s0, s1 in m.gaps.get(w.id, []):
                opens.append((T(s1), T(s0), 0.0, DOOR_H, "дверь"))
            for win in windows:
                if win["wall"] == w.id:
                    for p in win["parts"]:
                        a, b = sorted(T(w.s(c)) for c in p["span"])
                        opens.append((a, b, *p["z"], "балконная дверь" if p["z"][0] < 1 else "окно"))
            for wid, span, z0, z1 in splash:
                if wid == w.id:
                    a, b = sorted(T(w.s(c)) for c in span)
                    opens.append((a, b, z0, z1, SPLASH))
        self.rot, self.P, self.segs, self.opens = 0.0, P, segs, opens
        self.runs = [(0.0, P)]
        cabinets = []   # where a seam is not seen: behind full-height cabinets
        for g in segs:
            w = g["w"]
            if w.id in NICHE:
                cabinets.append((g["t0"], g["t0"] + g["L"]))
            for c0, c1 in CABINETS.get(w.id, []):
                a, b = sorted(g["t0"] + g["L"] - w.s(c) for c in (c0, c1))
                cabinets.append((max(a, g["t0"]), min(b, g["t0"] + g["L"])))
        self.cabinets = cabinets
        self.hidden = [(a, b, 0.0, H) for a, b in cabinets]
        for a, b, z0, z1, label in opens:
            self.hidden.append((a, b, z0, z1))
            if label == "дверь":
                self.hidden += [(a - CASING, a, 0.0, z1 + CASING), (b, b + CASING, 0.0, z1 + CASING),
                                (a, b, z1, z1 + CASING)]

    def at(self, t):
        """Unfolded position (rotated) → original t."""
        return (t + self.rot) % self.P

    def spans(self, a, b):
        """A rotated range as original ranges (split where the unfolding wraps)."""
        a0 = self.at(a)
        if a0 + (b - a) <= self.P + 1e-6:
            return [(a0, a0 + (b - a))]
        return [(a0, self.P), (0.0, a0 + (b - a) - self.P)]

    def visible(self, a, b):
        """Height ranges a strip over the rotated range a..b has to cover: the wall less doors and windows."""
        cuts = {a, b}
        for g in self.segs:
            cuts |= {g["t0"], g["t0"] + g["L"]}
        for o in self.opens:
            cuts |= {o[0], o[1]}
        out = []
        for x0, x1 in self.spans(a, b):
            pts = sorted(c for c in cuts if x0 <= c <= x1) or [x0, x1]
            pts = sorted(set([x0, x1] + pts))
            for u, v in zip(pts, pts[1:]):
                if v - u < 0.2:
                    continue
                mid = (u + v) / 2
                zs = [(0.0, H)]
                for o in self.opens:
                    if o[0] <= mid <= o[1]:
                        zs = [r for z0, z1 in zs for r in ((z0, min(z1, o[2])), (max(z0, o[3]), z1)) if r[1] - r[0] > 0.5]
                out += zs
        out.sort()
        merged = []
        for z0, z1 in out:
            if merged and z0 <= merged[-1][1] + 0.5:
                merged[-1][1] = max(merged[-1][1], z1)
            else:
                merged.append([z0, z1])
        return merged

    def seam_seen(self, x):
        """cm of a seam at x that is seen: the wall less openings, the backsplash, casings, cabinets (at the edge of an
        opening, the wall beside it counts)."""
        best = 0.0
        for xx in (x - 0.05, x + 0.05):
            cov, top = 0.0, 0.0
            for z0, z1 in sorted((max(z0, 0.0), min(z1, H)) for a, b, z0, z1 in self.hidden if a <= xx <= b):
                if z1 > top:
                    cov += z1 - max(z0, top)
                    top = z1
            best = max(best, H - cov)
        return best

    def seams(self):
        """The joints of the strips inside the walls (not in the corners), with the cm of each that is seen."""
        corners = [g["t0"] for g in self.segs] + [self.P]
        xs = sorted({round(e, 2) for p in self.pieces for e in (p["x0"], p["x1"])})
        return [(x, self.seam_seen(x)) for x in xs if all(abs(x - c) > 1 for c in corners)]

    def wall_runs(self):
        """Runs between the corners of two walls at least MAJOR long; a shorter wall is wrapped with its neighbours."""
        segs, n = self.segs, len(self.segs)
        cut = [i for i in range(n) if (i == 0 and not self.closed) or
               ((i > 0 or self.closed) and segs[i]["L"] >= MAJOR and segs[i - 1]["L"] >= MAJOR)]
        assert cut[0] == 0, f"{self.key}: the unfolding should start at a corner of two long walls"
        return [(segs[i]["t0"], segs[cut[k + 1]]["t0"] if k + 1 < len(cut) else self.P) for k, i in enumerate(cut)]

    def best_grid(self, a, b):
        """The strip joints of a run a..b: as few strips as it takes, shifted so the joints are seen the least
        (under windows, over doors, at casings, behind cabinets); no strip narrower than MIN_STRIP."""
        R, best = b - a, None
        cands = {k * 0.5 for k in range(int(self.W * 2))} | {round((e - a) % self.W, 2)
                                                            for h in self.hidden for e in h[:2] if a < e < b}
        for o in sorted(cands):
            xs = ([a + o] if o > 0.01 else []) + [a + o + k * self.W for k in range(1, int(R / self.W) + 2)
                                                   if a + o + k * self.W < b - 0.01]
            bounds = [a] + xs + [b]
            if R >= 2 * MIN_STRIP and min(v - u for u, v in zip(bounds, bounds[1:])) < MIN_STRIP:
                continue
            score = (round(sum(self.seam_seen(x) for x in xs), 1), len(bounds), o > 0.01)
            if best is None or score < best[0]:
                best = (score, bounds)
        return best[1]

    def strips(self, first, per_wall=False):
        """Strips a roll wide. By default from the start of each run on round the corners; a run that would end in a
        strip narrower than MIN_STRIP starts with it instead (in the kitchen-living room: in the niche, behind the
        cabinet). per_wall: each wall from its own corner, the joints where they are seen the least (best_grid)."""
        bounds = []
        if per_wall:
            for a, b in self.wall_runs():
                g = self.best_grid(a, b)
                bounds += list(zip(g, g[1:]))
        else:
            for a, b in self.runs:
                x, r = a, (b - a) % self.W
                head = r if 0.5 < r < MIN_STRIP else self.W
                while x < b - 0.5:
                    x1 = min(x + (head if x == a else self.W), b)
                    bounds.append((x, x1))
                    x = x1
        self.pieces, n = [], first
        for x, x1 in bounds:
            for z0, z1 in self.visible(x, x1):
                self.pieces.append(dict(strip=n, x0=x, x1=x1, z0=z0, z1=z1, w=z1 - z0 + ALLOW, h=x1 - x))
            n += 1
        return n

    def wall_area(self):
        """m² of wall under wallpaper: the walls less doors, windows and the backsplash (window parts overlap)."""
        xs = sorted({e for o in self.opens for e in o[:2]})
        holes = 0.0
        for u, v in zip(xs, xs[1:]):
            zs = sorted((max(o[2], 0.0), min(o[3], H)) for o in self.opens if o[0] <= u and o[1] >= v)
            top = 0.0
            for z0, z1 in zs:
                holes += (v - u) * max(0.0, z1 - max(z0, top))
                top = max(top, z1)
        return (self.P * H - holes) / 1e4

    def where(self, p):
        """The walls a strip lies on, by name (or length)."""
        out = []
        for g in self.segs:
            if min(p["x1"], g["t0"] + g["L"]) - max(p["x0"], g["t0"]) > 0.5:
                name = WALL_NAMES.get(g["w"].id) or f"стена {num(g['L'])}"
                if name not in out:
                    out.append(name)
        return ", ".join(out)

    def kind(self, p):
        """Where a piece goes on the wall: full height, over a door / window / the backsplash, under a window."""
        if p["z0"] < 0.5 and p["z1"] > H - 0.5:
            return "во всю высоту"
        near = [o for o in self.opens if min(p["x1"], o[1]) - max(p["x0"], o[0]) > 0.5]
        over = next((o[4] for o in near if abs(o[3] - p["z0"]) < 0.5), None)
        under = next((o[4] for o in near if abs(o[2] - p["z1"]) < 0.5), None)
        case = {"дверь": "двер", "окно": "окн", "балконная дверь": "балконн", SPLASH: "фартук"}
        word = lambda o: {"дверь": "дверью", "окно": "окном", "балконная дверь": "балконной дверью",
                          SPLASH: "фартуком"}[o]
        z = f"{num(p['z0'])}–{num(p['z1'])}"
        if over and under:
            return f"между: {word(over)} и {word(under)}, {z}"
        if over:
            return f"над {word(over)}, {z}"
        if under:
            return f"под {word(under)}, {z}"
        return z


def pack_rooms(groups, length, W):
    """Variant Б: room after room, the biggest pieces first, each piece into the offcut of any roll opened so far
    that fits it best (guillotine cuts, never turned), else into a new roll. → rolls as lists of (piece, x, y)"""
    rolls, free = [], []
    for pieces in groups:
        for p in sorted(pieces, key=lambda p: (-p["w"] * p["h"], -p["w"])):
            best = None
            for ri, fr in enumerate(free):
                for fi, (fx, fy, fw, fh) in enumerate(fr):
                    if p["w"] <= fw + 1e-6 and p["h"] <= fh + 1e-6 and (best is None or
                                                                          min(fw - p["w"], fh - p["h"]) < best[0]):
                        best = (min(fw - p["w"], fh - p["h"]), ri, fi)
            if best is None:
                rolls.append([])
                free.append([(0.0, 0.0, length, W)])
                best = (0, len(rolls) - 1, 0)
            _, ri, fi = best
            fx, fy, fw, fh = free[ri].pop(fi)
            rolls[ri].append((p, fx, fy))
            rw, rh = fw - p["w"], fh - p["h"]
            new = ([(fx + p["w"], fy, rw, fh), (fx, fy + p["h"], p["w"], rh)] if rw * fh >= fw * rh else
                   [(fx + p["w"], fy, rw, p["h"]), (fx, fy + p["h"], fw, rh)])
            free[ri] += [r for r in new if r[2] >= 3 and r[3] >= 3]
    return rolls


def cut_rolls(groups, length, W, first):
    """The pieces of a zone (its rooms in gluing order) cut from as few rolls as it takes: room after room onto the
    offcuts of the rolls opened before, or packed all at once if that takes fewer. Rolls are numbered from first in
    the order of their first piece; each piece gets p["roll"] and p["at"], its place on the roll.
    → [(n, [(piece, x, y)])]"""
    pieces = [p for g in groups for p in g]
    for i, p in enumerate(pieces):
        p["order"] = i
    rolls = pack_rooms(groups, length, W)
    if len(groups) > 1:
        alt = pack(pieces, length, W)
        rolls = alt if len(alt) < len(rolls) else rolls
    else:
        rolls = pack(pieces, length, W)
    rolls.sort(key=lambda r: min(p["order"] for p, _, _ in r))
    out = []
    for n, r in enumerate(rolls, first):
        for p, x, y in r:
            p["roll"], p["at"] = n, (x, y)
        out.append((n, sorted(r, key=lambda e: (e[1], e[2]))))
    return out


def least_rolls(groups, length, W):
    """How many rolls the pieces of these groups take at the fewest (for the comparison)."""
    pieces = [p for g in groups for p in g]
    return min(len(pack(pieces, length, W)), len(pack_rooms(groups, length, W)))


def rest(r, length):
    """What is left at the end of a roll, the full width."""
    return length - max((x + p["w"] for p, x, y in r if y < 0.1), default=0.0)


def dec(v):
    return f"{v:.2f}".replace(".", ",")


ROOM_COLORS = {"hall": (250, 226, 200), "kitchen_living": (208, 228, 247), "bedroom_1": (214, 238, 214),
               "bedroom_2": (243, 214, 236), "study": (220, 214, 246)}


def draw_room(room, path, length, sc=1.0, row_max=1250):
    """The unfolded walls in rows, each strip numbered, its roll under the number and in its color."""
    segs = sorted(((g, g["t0"], g["t0"] + g["L"]) for g in room.segs), key=lambda e: e[1])
    rows, cur = [], []
    for e in segs:
        if cur and e[2] - cur[0][1] > row_max:
            rows.append(cur)
            cur = []
        cur.append(e)
    rows.append(cur)
    left, top, row_h = 120, 150, H * sc + 170
    title = f"Раскладка обоев — {room.name}, {room.article} (развёртка, вид изнутри)"
    width = int(left * 2 + max(max(r[-1][2] - r[0][1] for r in rows) * sc, font(34, True).getlength(title)))
    notes = wrap(f"{PRODUCT} {room.article}: рулон {dec(room.W / 100)} × {dec(length / 100)} м, однотонные, раппорт 0 — "
                 "полоса = высота + 10 на подрезку. Номер — полоса (слева направо от красной стрелки), под ним — "
                 "рулон, из которого она режется; цвет — рулон. Обои клеятся и за шкафами; нет их только на фартуке "
                 "кухни (заштрихован).", font(20), width - 2 * left)
    img = Image.new("RGB", (width, int(top + len(rows) * row_h + 40 + 32 * len(notes))), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 50), title, fill=INK, font=font(34, True))
    for ri, row in enumerate(rows):
        r0, r1 = row[0][1], row[-1][2]
        y0 = top + ri * row_h

        def P(x, z):
            return left + (x - r0) * sc, y0 + (H - z) * sc
        a, b = P(r0, H), P(r1, 0)
        d.rectangle([a, b], fill="white")
        for p in room.pieces:   # strips in the color of their roll
            x0, x1 = max(p["x0"], r0), min(p["x1"], r1)
            if x1 - x0 > 0.1:
                q0, q1 = P(x0, p["z1"]), P(x1, p["z0"])
                d.rectangle([q0, q1], fill=ROLL_COLORS[(p["roll"] - 1) % len(ROLL_COLORS)], outline=(120, 110, 100),
                            width=1)
        for x0, x1, z0, z1, label in room.opens:
            lo, hi = max(x0, r0), min(x1, r1)
            if hi - lo > 0.1:
                q0, q1 = P(lo, z1), P(hi, z0)
                if label == SPLASH:
                    hatch(d, (q0[0], q0[1], q1[0], q1[1]))
                    d.rectangle([q0, q1], outline=INK, width=2)
                else:
                    d.rectangle([q0, q1], fill="white", outline=INK, width=2)
                fits = [t for t in (label, label.replace("балконная", "балк.")) if font(17).getlength(t) < q1[0] - q0[0] - 6]
                if fits and z1 - z0 > 30:
                    d.text(((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2), fits[0], fill=GREY_TXT, font=font(17),
                           anchor="mm")
        for p in room.pieces:   # labels: the strip and its rolls, in the roomiest part of the strip clear of openings
            x0, x1 = max(p["x0"], r0), min(p["x1"], r1)
            if x1 - x0 < 0.5:
                continue
            cuts = sorted({x0, x1} | {e for o in room.opens for e in o[:2] if x0 < e < x1})
            best = None
            for u, v in zip(cuts, cuts[1:]):
                zs = [(p["z0"], p["z1"])]
                for o in room.opens:
                    if o[0] <= (u + v) / 2 <= o[1]:
                        zs = [r for z0, z1 in zs for r in ((z0, min(z1, o[2])), (max(z0, o[3]), z1))
                              if r[1] - r[0] > 0.5]
                for z0, z1 in zs:
                    if best is None or min((v - u) / 1.5, z1 - z0) > best[0]:
                        best = (min((v - u) / 1.5, z1 - z0), u, v, z0, z1)
            if best:
                _, u, v, z0, z1 = best
                put_label(img, P((u + v) / 2, (z0 + z1) / 2), [str(p["strip"]), f"Р{p['roll']}"],
                          (v - u) * sc, (z1 - z0) * sc, INK, 24)
        for g, x0, x1 in row:   # walls: corners, lengths and names under them
            q0, q1 = P(x0, H), P(x1, 0)
            d.line([q0[0], q0[1], q0[0], q1[1]], fill=INK, width=3)
            yy = q1[1] + 22
            d.line([q0[0], yy - 8, q0[0], yy + 8], fill=INK, width=2)
            d.line([q1[0], yy - 8, q1[0], yy + 8], fill=INK, width=2)
            d.line([q0[0], yy, q1[0], yy], fill=INK, width=2)
            if x1 - x0 > 25:
                d.text(((q0[0] + q1[0]) / 2, yy + 16), num(x1 - x0), fill=INK, font=font(18), anchor="mm")
            name = WALL_NAMES.get(g["w"].id, "")
            if name and x1 - x0 > 90:
                d.text(((q0[0] + q1[0]) / 2, yy + 40), name, fill=GREY_TXT, font=font(17), anchor="mm")
        d.rectangle([a, b], outline=INK, width=3)
        for a0, b0 in room.runs:   # where the strips start: a red arrow
            if r0 - 0.5 <= a0 < r1:
                x, y = P(a0, H)
                d.polygon([(x, y - 12), (x + 24, y - 12), (x + 24, y - 20), (x + 46, y - 8), (x + 24, y + 4),
                           (x + 24, y - 4), (x, y - 4)], fill=DIM)
    y = img.height - 32 * len(notes) - 20
    for t in notes:
        d.text((left, y), t, fill=GREY_TXT, font=font(20))
        y += 32
    img.save(path)


def draw_rolls(title, sub, groups, path, length, W, color, legend=()):
    """Rolls as cut: pieces along each in order from its start, the strip number and length on each.
    groups: (heading, [(n, [(piece, x, y)])]); color(piece, n) → fill; legend: (label, fill)."""
    sc, left = 1.3, 60
    bar_h = max(46, W * 0.9)
    n = sum(len(r) for _, r in groups)
    width = int(left * 2 + length * sc + 220)
    img = Image.new("RGB", (width, int(170 + (50 if legend else 0) + len(groups) * 70 + n * (bar_h + 26))), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 40), title, fill=INK, font=font(34, True))
    d.text((left, 92), sub, fill=GREY_TXT, font=font(22))
    y = 160
    if legend:
        x = left
        for label, fill in legend:
            d.rectangle([x, y, x + 34, y + 26], fill=fill, outline=INK, width=1)
            d.text((x + 44, y + 13), label, fill=INK, font=font(20), anchor="lm")
            x += 44 + font(20).getlength(label) + 34
        y += 50
    pre = "Р"
    for heading, rolls in groups:
        d.text((left, y), heading, fill=INK, font=font(24, True))
        y += 50
        for n_, r in rolls:
            d.text((left, y + bar_h / 2), f"{pre}{n_}", fill=INK, font=font(22, True), anchor="lm")
            x0 = left + 60
            hatch(d, (x0, y, x0 + length * sc, y + bar_h))
            for p, px, py in r:
                a = (x0 + px * sc, y + py * bar_h / W)
                b = (a[0] + p["w"] * sc, a[1] + p["h"] * bar_h / W)
                d.rectangle([a, b], fill=color(p, n_), outline=INK, width=1)
                put_label(img, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                          [str(p["strip"]), f"{num(p['w'])}" + ("" if p["h"] >= W - 0.1 else f" × {num(p['h'])}")],
                          b[0] - a[0], b[1] - a[1], INK, 20)
            d.rectangle([x0, y, x0 + length * sc, y + bar_h], outline=INK, width=2)
            d.text((x0 + length * sc + 14, y + bar_h / 2), f"остаток {num(rest(r, length))}", fill=GREY_TXT,
                   font=font(18), anchor="lm")
            y += bar_h + 26
        y += 20
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--width", type=float, default=106.0, help="roll width, cm")
    ap.add_argument("--length", type=float, default=1005.0, help="roll length, cm")
    ap.add_argument("--seams", action="store_true",
                    help="each wall from its own corner, the joints where they are seen the least (another document)")
    ap.add_argument("--out", help="sheets; default renders/Рендеры/Раскладка обоев[ — меньше стыков]")
    ap.add_argument("--json", help="default renders/layout/wallpaper[_seams].json")
    ap.add_argument("--count", action="store_true", help="only print the counts")
    args = ap.parse_args()
    args.out = args.out or "renders/Рендеры/Раскладка обоев" + (" — меньше стыков" if args.seams else "")
    args.json = args.json or f"renders/layout/wallpaper{'_seams' if args.seams else ''}.json"
    L, W = args.length, args.width
    cfg = json.loads(Path(args.config).read_text())
    m = Model(cfg, json.loads(Path(args.plan).read_text()))
    k = cfg["kitchen"]
    splash = [(b["wall"], b["span"], k["base_top"], k["upper"]["bottom"]) for b in k["backsplash"]]
    XR = {r["id"]: r for r in cfg["extra_rooms"]}
    main_ids = [w["id"] for w in cfg["outline"]]
    hall, living = chain(main_ids, "pier_end", "hall_left"), chain(main_ids, "tv", "pier_back")
    assert sorted(hall + living) == sorted(main_ids), "hall + kitchen-living must be the whole outline"
    rooms = [Room("hall", "Прихожая", m, cfg["windows"], hall, W, closed=False),
             Room("kitchen_living", "Кухня-гостиная", m, cfg["windows"], living, W, splash, closed=False)]
    rooms += [Room(rid, name, m, cfg["windows"], [w["id"] for w in XR[rid]["outline"]], W)
              for rid, name in (("bedroom_1", "Спальня 1"), ("bedroom_2", "Спальня 2"), ("study", "Кабинет"))]
    rooms.sort(key=lambda room: room.article)   # one article's rolls in a row: 54355-3 first, then 54355-7
    names = {room.key: room.name for room in rooms}
    for room in rooms:   # the main layout, round the corners: its joints, to compare with
        room.strips(1)
        room.seams_main = room.seams()
        room.main_plan = [dict(x=[round(p["x0"], 1), round(p["x1"], 1)], z=[round(p["z0"], 1), round(p["z1"], 1)],
                               strip=p["strip"]) for p in room.pieces]
    n = 1
    for room in rooms:
        n = room.strips(n, per_wall=args.seams)
        for p in room.pieces:
            p["room"] = room.key
    zones = []
    first = 1
    for keys in ZONES:   # the plan: the rolls of a zone stay in it
        rs = [room for room in rooms if room.key in keys]
        zones.append(dict(rs=rs, rolls=cut_rolls([room.pieces for room in rs], L, W, first)))
        first += len(zones[-1]["rolls"])

    def roll_list(rolls):
        return [dict(roll=k_, rest=round(rest(r, L), 1),
                     pieces=[dict(strip=p["strip"], room=p["room"], length=round(p["w"], 1), width=round(p["h"], 1),
                                  at=[round(x, 1), round(y, 1)]) for p, x, y in r]) for k_, r in rolls]
    summary = []
    for room in rooms:
        z = next(z for z in zones if room in z["rs"])

        def seam_stats(seams):
            return dict(list=[dict(x=round(x, 1), seen=round(v)) for x, v in seams], count=len(seams),
                        seen=sum(1 for _, v in seams if v > 1), length=round(sum(v for _, v in seams) / 100, 1))
        summary.append(dict(
            key=room.key, name=room.name, article=room.article, zone=[r.key for r in z["rs"]],
            wall_area=round(room.wall_area(), 2), strips=len({p["strip"] for p in room.pieces}),
            pieces=len(room.pieces), rolls=sorted({p["roll"] for p in room.pieces}),
            own=least_rolls([room.pieces], L, W),   # rolls it takes papered on its own
            seams=seam_stats(room.seams()), seams_main=seam_stats(room.seams_main),
            main_plan=room.main_plan if args.seams else None,
            plan=[dict(strip=p["strip"], where=room.where(p), kind=room.kind(p), z=[round(p["z0"], 1), round(p["z1"], 1)],
                       x=[round(p["x0"], 1), round(p["x1"], 1)], width=round(p["h"], 1), length=round(p["w"], 1),
                       roll=p["roll"]) for p in room.pieces],
            # the unfolding, for drawing: walls left to right, doors / windows / the backsplash on them
            unfolded=dict(length=round(room.P, 1),
                          walls=[dict(id=g["w"].id, x=[round(g["t0"], 1), round(g["t0"] + g["L"], 1)],
                                      name=WALL_NAMES.get(g["w"].id, "")) for g in room.segs],
                          opens=[dict(x=[round(o[0], 1), round(o[1], 1)], z=[round(o[2], 1), round(min(o[3], H), 1)],
                                      label=o[4]) for o in room.opens],
                          cabinets=[dict(x=[round(a, 1), round(b, 1)]) for a, b in room.cabinets])))
    zone_list = [dict(rooms=[r.key for r in z["rs"]], names=[r.name for r in z["rs"]], article=z["rs"][0].article,
                      rolls=len(z["rolls"]), first=z["rolls"][0][0], last=z["rolls"][-1][0], list=roll_list(z["rolls"]))
                 for z in zones]
    for r in summary:
        a, b = r["seams_main"], r["seams"]
        print(f"{r['name']:16s} стыков {a['count']:2d} → {b['count']:2d}, видно {a['seen']:2d} → {b['seen']:2d}, "
              f"видимая длина {a['length']:5.1f} → {b['length']:5.1f} м, полос {r['strips']}")
    for z in zone_list:
        print(f"{' и '.join(z['names']):34s} {z['article']}  {z['rolls']} рул. (Р{z['first']}–Р{z['last']})")
    articles = []
    for art in dict.fromkeys(room.article for room in rooms):   # and how many it would take papered otherwise
        rs = [room for room in rooms if room.article == art]
        articles.append(dict(article=art, rooms=[room.key for room in rs], names=[room.name for room in rs],
                             wall_area=round(sum(room.wall_area() for room in rs), 2),
                             strips=sum(len({p["strip"] for p in room.pieces}) for room in rs),
                             rolls=sum(z["rolls"] for z in zone_list if z["article"] == art),
                             separate=sum(least_rolls([room.pieces], L, W) for room in rs),
                             shared=least_rolls([room.pieces for room in rs], L, W)))
        a = articles[-1]
        print(f"{art}: по плану {a['rolls']} рул.; каждая комната отдельно — {a['separate']}; остатки между всеми "
              f"комнатами — {a['shared']}")
    total = {k_: sum(a[k_] for a in articles) for k_ in ("rolls", "separate", "shared")}
    print(f"всего: по плану {total['rolls']}, каждая комната отдельно {total['separate']}, с переносом остатков "
          f"{total['shared']}")
    if args.count:
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    files = []
    for i, room in enumerate(rooms, 1):
        f = out / f"{i:02d} {room.name} ({room.article}).png"
        draw_room(room, f, L)
        files.append(f)
    size = f"{dec(W / 100)} × {dec(L / 100)} м"
    for a in articles:
        zs = [z for z in zones if z["rs"][0].article == a["article"]]
        f = out / f"{len(files) + 1:02d} Раскрой рулонов {a['article']}.png"
        draw_rolls(f"Раскрой рулонов {a['article']} — {a['rolls']} рул. {size}", f"{PRODUCT} {a['article']}; цвет — комната",
                   [(f"{' и '.join(r.name for r in z['rs'])} — {len(z['rolls'])} рул. (Р{z['rolls'][0][0]}–"
                     f"Р{z['rolls'][-1][0]})", z["rolls"]) for z in zs],
                   f, L, W, lambda p, n_: ROOM_COLORS[p["room"]],
                   legend=[(r.name, ROOM_COLORS[r.key]) for z in zs for r in z["rs"]])
        files.append(f)
    js = Path(args.json)
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(dict(product=PRODUCT, mode="seams" if args.seams else "main", width=W, length=L,
                                  height=H, allow=ALLOW, casing=CASING,
                                  splash=[k["base_top"], k["upper"]["bottom"]], rooms=summary, zones=zone_list,
                                  articles=articles, **total, sheets=[str(f) for f in files]),
                             ensure_ascii=False, indent=1))
    for f in files:
        print(f)


if __name__ == "__main__":
    main()
