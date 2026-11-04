"""Wallpaper layout: each room's walls unfolded as seen from inside, cut into strips a roll wide, every strip numbered
with the roll it is cut from, every roll with the pieces it gives; the rolls to buy are the last roll number.
Strips run left to right from the edge of a cabinet that stands to the ceiling (no wallpaper behind it), on across
corners (a strip is cut there, its rest goes on the next wall) and across doors and windows (over a door the strip
is a short piece). Paintable wallpaper without a pattern: a piece is the height it covers + 10 cm to trim. The rolls
of a room stay in it; two narrow strips may share one length of a roll.

    .venv/bin/python wallpaper_layout.py               # → renders/Рендеры/Раскладка обоев/, renders/layout/wallpaper.json
    .venv/bin/python wallpaper_layout.py --width 53    # rolls 0.53 m wide
"""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

from plans import DIM, Model, num
from tile_layout import GREY_TXT, INK, font, hatch, pack, put_label, wrap

H, ALLOW = 270.0, 10.0   # floor to slab; trimming, top and bottom
DOOR_H = 217.0
# full-height furniture: no wallpaper behind it (plan coordinates along the wall)
COVERS = {
    "hall_right": [(0, 240, "шкаф-купе")], "entrance": [(180, 240, "шкаф-купе")],
    "kitchen": [(-402, -111.2, "кухня")], "sofa": [(-181.8, -20, "кухня, холодильник")],
    "riser_side": [(-422, -402, "короб стояка")], "riser_front": [(-20, 0, "короб стояка")],
    "br1_door": [(367, 549, "шкаф")], "br1_head": [(254, 394.3, "шкаф")],
    "st_pocket_end": [(-567, -477, "шкаф-купе")], "st_pocket_side": [(-97, -27, "шкаф-купе")],
    "st_door": [(-24, 106, "шкаф")], "st_left": [(-179, -119, "шкаф")],
    "b2_door": [(371, 551, "шкаф")], "b2_right": [(-179.4, -119, "шкаф")],
}
NICHE = ["niche_step", "niche_side", "niche_top", "niche_jog", "pier_back"]   # the niche cabinet, to the ceiling
WALL_NAMES = {
    "entrance": "входная дверь", "hall_right_br1": "дверь спальни 1", "hall_far": "двери санузлов",
    "hall_left": "двери спальни 2 и кабинета", "tv": "стена ТВ", "window": "окно, балконная дверь",
    "sofa": "у дивана", "kitchen": "кухня", "pier_end": "простенок",
    "br1_door": "стена с дверью", "br1_tv": "стена ТВ", "br1_balcony": "окно, балконная дверь", "br1_head": "изголовье",
    "st_door": "стена с дверью", "st_right": "к спальне 2", "st_far": "окно", "st_left": "к гостиной",
    "b2_door": "стена с дверью", "b2_right": "наружная", "b2_far": "окно", "b2_left": "к кабинету",
}
ROLL_COLORS = [(250, 226, 200), (208, 228, 247), (214, 238, 214), (243, 214, 236), (246, 240, 196),
               (220, 214, 246), (198, 236, 236), (245, 214, 210)]


class Room:
    def __init__(self, key, name, m, windows, wall_ids, W):
        self.key, self.name, self.W = key, name, W
        segs, t = [], 0.0
        for wid in reversed(wall_ids):   # seen from inside, left to right: against the outline's direction
            w = m.walls[wid]
            segs.append(dict(w=w, t0=t, L=w.len))
            t += w.len
        P = t
        covers, opens = [], []
        for g in segs:
            w = g["w"]

            def T(s, g=g):
                return g["t0"] + g["L"] - s
            if w.id in NICHE:
                covers.append((g["t0"], g["t0"] + g["L"], "шкаф в нише"))
            for c0, c1, label in COVERS.get(w.id, []):
                a, b = sorted((T(w.s(c0)), T(w.s(c1))))
                covers.append((max(a, g["t0"]), min(b, g["t0"] + g["L"]), label))
            for s0, s1 in m.gaps.get(w.id, []):
                opens.append((T(s1), T(s0), 0.0, DOOR_H, "дверь"))
            for win in windows:
                if win["wall"] == w.id:
                    for p in win["parts"]:
                        a, b = sorted(T(w.s(c)) for c in p["span"])
                        opens.append((a, b, *p["z"], "балконная дверь" if p["z"][0] < 1 else "окно"))
        # runs of wall between cabinets; the drawing starts at the end of the first cabinet
        covers.sort()
        free, at = [], 0.0
        for a, b, _ in covers:
            if a > at + 0.5:
                free.append([at, a])
            at = max(at, b)
        if at < P - 0.5:
            free.append([at, P])
        if covers and free and free[0][0] < 0.5 and free[-1][1] > P - 0.5 and len(free) > 1:
            free[-1][1] = P + free.pop(0)[1]   # the run across the start of the unfolding
        self.rot = free[0][0] if covers else 0.0
        self.P, self.segs, self.covers, self.opens = P, segs, covers, opens
        self.runs = [(a - self.rot, b - self.rot) for a, b in free]

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

    def strips(self, first):
        self.pieces, n = [], first
        for a, b in self.runs:
            x = a
            while x < b - 0.5:
                x1 = min(x + self.W, b)
                for z0, z1 in self.visible(x, x1):
                    self.pieces.append(dict(strip=n, x0=x, x1=x1, z0=z0, z1=z1, w=z1 - z0 + ALLOW, h=x1 - x))
                n += 1
                x = x1
        return n

    def rolls(self, first, length):
        for i, p in enumerate(self.pieces):
            p["order"] = i
        rolls = pack(self.pieces, length, self.W)
        rolls.sort(key=lambda r: min(p["order"] for p, _, _ in r))
        self.rolls_ = []
        for n, r in enumerate(rolls, first):
            for p, x, y in r:
                p["roll"], p["at"] = n, (x, y)
            self.rolls_.append((n, sorted(r, key=lambda e: (e[1], e[2]))))
        return first + len(rolls)


def draw_room(room, path, sc=1.0, row_max=1250):
    """The unfolded walls in rows, each strip in the color of its roll, numbered, its roll under the number."""
    segs = []   # (wall, x0, x1 in rotated coords, s at x0)
    for g in room.segs:
        a = (g["t0"] - room.rot) % room.P
        b = a + g["L"]
        if b <= room.P + 1e-6:
            segs.append((g, a, b))
        else:
            segs += [(g, a, room.P), (g, 0.0, b - room.P)]
    segs.sort(key=lambda e: e[1])
    rows, cur = [], []
    for e in segs:
        if cur and e[2] - cur[0][1] > row_max:
            rows.append(cur)
            cur = []
        cur.append(e)
    rows.append(cur)
    left, top, row_h = 120, 150, H * sc + 170
    width = int(left * 2 + max(r[-1][2] - r[0][1] for r in rows) * sc)
    notes = wrap(f"Рулон {room.W / 100:.2f} × 10 м, обои под покраску без раппорта: полоса = высота + 10 на подрезку. "
                 "Номер — полоса (слева направо от красной стрелки, от края шкафа), под ним — рулон, из которого она "
                 "режется; цвет — рулон. За шкафами и кухней до потолка обоев нет.", font(20), width - 2 * left)
    img = Image.new("RGB", (width, int(top + len(rows) * row_h + 40 + 32 * len(notes))), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 50), f"Раскладка обоев — {room.name} (развёртка, вид изнутри)", fill=INK, font=font(34, True))

    opens = [((o[0] - room.rot) % room.P, (o[0] - room.rot) % room.P + o[1] - o[0], *o[2:]) for o in room.opens]

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
        for c0, c1, label in room.covers:   # cabinets to the ceiling
            x0 = (c0 - room.rot) % room.P
            lo, hi = max(x0, r0), min(x0 + c1 - c0, r1)
            if hi - lo > 0.1:
                q0, q1 = P(lo, H), P(hi, 0)
                hatch(d, (q0[0], q0[1], q1[0], q1[1]))
                if hi - lo > 40:
                    d.text(((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2), label, fill=GREY_TXT, font=font(17),
                           anchor="mm")
        for x0, x1, z0, z1, label in opens:
            lo, hi = max(x0, r0), min(x1, r1)
            if hi - lo > 0.1:
                q0, q1 = P(lo, z1), P(hi, z0)
                d.rectangle([q0, q1], fill="white", outline=INK, width=2)
                if hi - lo > 40 and z1 - z0 > 60:
                    d.text(((q0[0] + q1[0]) / 2, (q0[1] + q1[1]) / 2), label, fill=GREY_TXT, font=font(17),
                           anchor="mm")
        for p in room.pieces:   # labels: the strip and its roll, in the roomiest part of the strip clear of openings
            x0, x1 = max(p["x0"], r0), min(p["x1"], r1)
            if x1 - x0 < 0.5:
                continue
            cuts = sorted({x0, x1} | {e for o in opens for e in o[:2] if x0 < e < x1})
            best = None
            for u, v in zip(cuts, cuts[1:]):
                zs = [(p["z0"], p["z1"])]
                for o in opens:
                    if o[0] <= (u + v) / 2 <= o[1]:
                        zs = [r for z0, z1 in zs for r in ((z0, min(z1, o[2])), (max(z0, o[3]), z1))
                              if r[1] - r[0] > 0.5]
                for z0, z1 in zs:
                    if best is None or min((v - u) / 1.5, z1 - z0) > best[0]:
                        best = (min((v - u) / 1.5, z1 - z0), u, v, z0, z1)
            if best:
                _, u, v, z0, z1 = best
                put_label(img, P((u + v) / 2, (z0 + z1) / 2), [str(p["strip"]), f"Р{p['roll']}"], (v - u) * sc,
                          (z1 - z0) * sc, INK, 24)
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
            if name and x1 - x0 > 90 and abs(x1 - x0 - g["L"]) < 1:
                d.text(((q0[0] + q1[0]) / 2, yy + 40), name, fill=GREY_TXT, font=font(17), anchor="mm")
        d.rectangle([a, b], outline=INK, width=3)
        for a0, b0 in room.runs:   # where the strips start: a red arrow at the cabinet edge
            if r0 - 0.5 <= a0 < r1:
                x, y = P(a0, H)
                d.polygon([(x, y - 12), (x + 24, y - 12), (x + 24, y - 20), (x + 46, y - 8), (x + 24, y + 4),
                           (x + 24, y - 4), (x, y - 4)], fill=DIM)
    y = img.height - 32 * len(notes) - 20
    for t in notes:
        d.text((left, y), t, fill=GREY_TXT, font=font(20))
        y += 32
    img.save(path)


def draw_rolls(rooms, path, length, W):
    """Each roll as cut: pieces along it in order from its start, the strip number and length on each."""
    sc, left = 1.3, 60
    bar_h = max(46, W * 0.9)
    n = sum(len(r.rolls_) for r in rooms)
    width = int(left * 2 + length * sc + 220)
    img = Image.new("RGB", (width, int(130 + len(rooms) * 70 + n * (bar_h + 26))), "white")
    d = ImageDraw.Draw(img)
    d.text((left, 40), f"Раскрой рулонов {W / 100:.2f} × {num(length / 100)} м", fill=INK, font=font(34, True))
    y = 120
    for room in rooms:
        d.text((left, y), f"{room.name} — {len(room.rolls_)} рул. (Р{room.rolls_[0][0]}–Р{room.rolls_[-1][0]}), "
                          f"полос {len({p['strip'] for p in room.pieces})}, кусков {len(room.pieces)}",
               fill=INK, font=font(24, True))
        y += 50
        for n_, r in room.rolls_:
            d.text((left, y + bar_h / 2), f"Р{n_}", fill=INK, font=font(22, True), anchor="lm")
            x0 = left + 60
            hatch(d, (x0, y, x0 + length * sc, y + bar_h))
            for p, px, py in r:
                a = (x0 + px * sc, y + py * bar_h / W)
                b = (a[0] + p["w"] * sc, a[1] + p["h"] * bar_h / W)
                d.rectangle([a, b], fill=ROLL_COLORS[(n_ - 1) % len(ROLL_COLORS)], outline=INK, width=1)
                put_label(img, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2),
                          [str(p["strip"]), f"{num(p['w'])}" + ("" if p["h"] >= W - 0.1 else f" × {num(p['h'])}")],
                          b[0] - a[0], b[1] - a[1], INK, 20)
            d.rectangle([x0, y, x0 + length * sc, y + bar_h], outline=INK, width=2)
            rest = length - max((px + p["w"] for p, px, py in r if py < 0.1), default=0)
            d.text((x0 + length * sc + 14, y + bar_h / 2), f"остаток {num(rest)}", fill=GREY_TXT, font=font(18),
                   anchor="lm")
            y += bar_h + 26
        y += 20
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--width", type=float, default=106.0, help="roll width, cm")
    ap.add_argument("--length", type=float, default=1000.0, help="roll length, cm")
    ap.add_argument("--out", default="renders/Рендеры/Раскладка обоев")
    ap.add_argument("--json", default="renders/layout/wallpaper.json")
    ap.add_argument("--count", action="store_true", help="only print the counts")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    m = Model(cfg, json.loads(Path(args.plan).read_text()))
    XR = {r["id"]: r for r in cfg["extra_rooms"]}
    rooms = [Room("main", "Прихожая и кухня-гостиная", m, cfg["windows"], [w["id"] for w in cfg["outline"]], args.width)]
    rooms += [Room(rid, name, m, cfg["windows"], [w["id"] for w in XR[rid]["outline"]], args.width)
              for rid, name in (("bedroom_1", "Спальня 1"), ("study", "Кабинет"), ("bedroom_2", "Спальня 2"))]
    n, r = 1, 1
    for room in rooms:
        n = room.strips(n)
        r = room.rolls(r, args.length)
    total = pack(sum((room.pieces for room in rooms), []), args.length, args.width)
    summary = []
    for room in rooms:
        area = sum((p["z1"] - p["z0"]) * p["h"] for p in room.pieces)
        summary.append(dict(key=room.key, name=room.name, rolls=len(room.rolls_), first=room.rolls_[0][0],
                            last=room.rolls_[-1][0], strips=len({p["strip"] for p in room.pieces}),
                            pieces=len(room.pieces), area=round(area / 1e4, 2),
                            cut=round(sum(p["w"] * p["h"] for p in room.pieces) / 1e4, 2),
                            list=[dict(roll=k, pieces=[dict(strip=p["strip"], length=p["w"], width=round(p["h"], 1))
                                                       for p, _, _ in rr]) for k, rr in room.rolls_]))
        print(f"{room.name:28s} Р{summary[-1]['first']}–Р{summary[-1]['last']}: {summary[-1]['rolls']} рул., "
              f"полос {summary[-1]['strips']}, кусков {summary[-1]['pieces']}, на стене {summary[-1]['area']} м², "
              f"отрезано {summary[-1]['cut']} м²")
    print(f"всего по комнатам {r - 1} рул.; если остатки носить между комнатами — {len(total)}")
    if args.count:
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    files = []
    for i, room in enumerate(rooms, 1):
        f = out / f"{i:02d} {room.name}.png"
        draw_room(room, f)
        files.append(f)
    f = out / f"{len(rooms) + 1:02d} Раскрой рулонов.png"
    draw_rolls(rooms, f, args.length, args.width)
    files.append(f)
    js = Path(args.json)
    js.parent.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(dict(width=args.width, length=args.length, rooms=summary, rolls=r - 1,
                                  rolls_shared=len(total), sheets=[str(f) for f in files]), ensure_ascii=False, indent=1))
    for f in files:
        print(f)


if __name__ == "__main__":
    main()
