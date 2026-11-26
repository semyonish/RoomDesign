"""Стены с полотенцесушителями (ванная и туалет, левые стены): чертёж с размерами без плитки. Вверху — вид на стену
из комнаты (короба, унитаз, ванна, прибор; высоты от пола), под ним в той же привязке — план сверху (глубины коробов
и прибора, проход). Размеры коробов, низ / центр / верх полотенцесушителя, расстояния от угла у двери. Всё по чистовой
(по плитке), см.

    .venv/bin/python towel_walls.py     # renders/plan/towel_bathroom.png, towel_toilet.png
                                        # → export.py → Рендеры/Планы/Полотенцесушитель — Ванная|Туалет.png
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from plans import BOLD, FONT

INK, GREY, LIGHT, BLUE, RED = (30, 30, 30), (110, 105, 100), (170, 165, 160), (30, 90, 200), (200, 40, 40)
WALL, FACE, FACE_EDGE = (250, 248, 244), (234, 226, 212), (95, 85, 72)
BATH, OTHER = (238, 242, 246), (246, 245, 243)
SC, LEFT, TOP = 4.0, 330, 230
H = 267.0                                         # wet rooms, finished ceiling


def num(v):
    """cm with up to two decimals: 6.25, 91.25, 120."""
    return f"{v:.2f}".rstrip("0").rstrip(".")


def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)


class Sheet:
    """One wall: elevation on top, plan under it; both run along the wall with the door corner on the left."""

    def __init__(self, y_door, y_far, depth, title, sub):
        self.y0, self.L, self.D = y_door, y_far - y_door, depth
        self.R = LEFT + self.L * SC                        # right edge of the wall
        self.EB = TOP + H * SC                             # elevation floor line
        self.PT = self.EB + 310                            # plan: the wall line
        self.PB = self.PT + depth * SC
        self.width = int(self.R + 300)
        self.img = Image.new("RGB", (self.width, int(self.PB + 700)), "white")
        self.d = ImageDraw.Draw(self.img)
        self.d.text((LEFT, 40), title, fill=INK, font=font(34, True))
        self.d.text((LEFT, 92), sub, fill=GREY, font=font(21))
        self.d.rectangle([LEFT, TOP, self.R, self.EB], fill=WALL)

    # coordinates: plan y along the wall, height z, distance d from the wall into the room
    def X(self, y):
        return LEFT + (y - self.y0) * SC

    def Z(self, z):
        return TOP + (H - z) * SC

    def Dp(self, d):
        return self.PT + d * SC

    def erect(self, y0, y1, z0, z1, **kw):
        self.d.rectangle([self.X(y0), self.Z(z1), self.X(y1), self.Z(z0)], **kw)

    def prect(self, y0, y1, d0, d1, **kw):
        self.d.rectangle([self.X(y0), self.Dp(d0), self.X(y1), self.Dp(d1)], **kw)

    # ---- text and dimensions ----
    def text(self, xy, lines, size=19, fill=INK, anchor="mm", bold_first=False, bg=None):
        x, y = xy
        y -= (len(lines) - 1) * (size + 7) / 2 if anchor[1] == "m" else 0
        for k, t in enumerate(lines):
            f = font(size, bold_first and k == 0)
            if bg:
                tb = self.d.textbbox((x, y), t, font=f, anchor=anchor)
                self.d.rectangle([tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2], fill=bg)
            self.d.text((x, y), t, fill=fill, font=f, anchor=anchor)
            y += size + 7

    def vtext(self, x, y, t, size=19, fill=INK):
        f = font(size)
        im = Image.new("RGBA", (int(f.getlength(t)) + 10, size + 10), (255, 255, 255, 255))
        ImageDraw.Draw(im).text((im.width / 2, im.height / 2), t, fill=fill, font=f, anchor="mm")
        im = im.rotate(90, expand=True)
        self.img.paste(im, (int(x - im.width / 2), int(y - im.height / 2)))

    def tick(self, x, y, color):
        self.d.line([x - 6, y + 6, x + 6, y - 6], fill=color, width=3)

    def chain_h(self, ys, at, ext_from, color=INK, labels=None):
        """Horizontal chain at pixel row `at` through plan y's; extension lines from pixel row ext_from (or a list)."""
        xs = [self.X(y) for y in ys]
        froms = ext_from if isinstance(ext_from, list) else [ext_from] * len(xs)
        for x, f in zip(xs, froms):
            self.d.line([x, f, x, at + (8 if at > f else -8)], fill=LIGHT, width=1)
            self.tick(x, at, color)
        self.d.line([xs[0] - 10, at, xs[-1] + 10, at], fill=color, width=2)
        for k, (a, b) in enumerate(zip(xs, xs[1:])):
            t = labels[k] if labels else num((b - a) / SC)
            w = font(19).getlength(t)
            self.text(((a + b) / 2, at - 15 if w + 8 < b - a else at - 15 - 22 * (k % 2)), [t], 19, color)

    def chain_v(self, ps, at, ext_from, color=INK, labels=None):
        """Vertical chain at pixel column `at` through pixel rows ps; extension lines from columns ext_from."""
        froms = ext_from if isinstance(ext_from, list) else [ext_from] * len(ps)
        for p, f in zip(ps, froms):
            self.d.line([f, p, at + (8 if at > f else -8), p], fill=LIGHT, width=1)
            self.tick(at, p, color)
        self.d.line([at, min(ps) - 10, at, max(ps) + 10], fill=color, width=2)
        for k, (a, b) in enumerate(zip(ps, ps[1:])):
            self.vtext(at - 16, (a + b) / 2, labels[k] if labels else num(abs(b - a) / SC), 19, color)

    def heights(self, zs, at, ext_from, labels, color=INK):
        """Heights from the floor, each its own dimension line (from the floor up), side by side from `at` outward."""
        step = 46 if at > self.R else -46
        for k, (z, t) in enumerate(zip(zs, labels)):
            x = at + k * step
            f = ext_from[k] if isinstance(ext_from, list) else ext_from
            self.chain_v([self.Z(0), self.Z(z)], x, [x, f], color, [t])

    def axis(self, y0, y1, z0, z1, yc, zc):
        """Dash-dot centre lines through (yc, zc)."""
        for (a, b, horiz) in ((self.X(y0) - 22, self.X(y1) + 22, True), (self.Z(z1) - 22, self.Z(z0) + 22, False)):
            k = a
            while k < b:
                for seg in ((k, min(k + 18, b)), (k + 24, min(k + 27, b))):
                    if seg[0] < seg[1]:
                        if horiz:
                            self.d.line([seg[0], self.Z(zc), seg[1], self.Z(zc)], fill=BLUE, width=2)
                        else:
                            self.d.line([self.X(yc), seg[0], self.X(yc), seg[1]], fill=BLUE, width=2)
                k += 33

    # ---- objects ----
    def warmer(self, it, plan_depth):
        y0, y1 = sorted(it["span"])
        z0, z1 = it["elevation"], it["elevation"] + it["height"]
        n = it["bars"]
        if it["style"] == "bars":
            bw = 3.0
            pitch = (y1 - y0 - bw) / (n - 1)
            for zt in [z1 - zh + 3.5 for zh in it["hooks"]] + [z0 + 6]:
                self.erect(y0 + bw / 2, y1 - bw / 2, zt - 0.85, zt + 0.85, fill="white", outline=INK, width=1)
            for k in range(n):
                a = y0 + k * pitch
                self.erect(a, a + bw, z0, z1, fill="white", outline=INK, width=2)
        else:
            rw = 3.0
            for a in (y0, y1 - rw):            # wall plates 40 × 40 behind the rails, 12 from the ends (assumed)
                for zz in (z0 + 12, z1 - 12):
                    c = a + rw / 2
                    self.erect(c - 2, c + 2, zz - 2, zz + 2, fill=(225, 235, 250), outline=BLUE, width=2)
            for zc in [z0 + 4 + k * (it["height"] - 8) / (n - 1) for k in range(n)]:
                self.erect(y0 + rw, y1 - rw, zc - 1.1, zc + 1.1, fill="white", outline=INK, width=2)
            for a in (y0, y1 - rw):
                self.erect(a, a + rw, z0, z1, fill="white", outline=INK, width=2)
        self.prect(y0, y1, 0, plan_depth, fill="white", outline=INK, width=3)
        return y0, y1, z0, z1

    def room_plan(self, door):
        """The room outline in the plan, with the door opening in the door wall (the left edge)."""
        x0, x1, a, b = LEFT, self.R, self.PT, self.PB
        self.d.line([x0, a, x1, a], fill=INK, width=5)
        self.d.line([x1, a, x1, b], fill=INK, width=5)
        self.d.line([x0, b, x1, b], fill=INK, width=5)
        self.d.line([x0, a, x0, self.Dp(door[0])], fill=INK, width=5)
        self.d.line([x0, self.Dp(door[1]), x0, b], fill=INK, width=5)
        self.d.line([x0, self.Dp(door[0]), x0, self.Dp(door[1])], fill=LIGHT, width=2)
        self.text((x0 - 14, self.Dp(sum(door) / 2)), ["дверь"], 17, GREY, "rm")

    def finish(self, notes, y):
        for t in notes:
            words, line = t.split(), ""
            for w in words:
                if font(20).getlength(line + " " + w) > self.width - LEFT - 60:
                    self.d.text((LEFT, y), line, fill=GREY, font=font(20))
                    y, line = y + 30, w
                else:
                    line = (line + " " + w).strip()
            self.d.text((LEFT, y), line, fill=GREY, font=font(20))
            y += 38
        self.img = self.img.crop((0, 0, self.width, int(y + 20)))


def main():
    cfg = json.loads(Path("rooms/apartment.json").read_text())
    plan = {r["id"]: r for r in json.loads(Path("plan.json").read_text())["rooms"]}
    items = cfg["furniture"]

    def find(kind, wall):
        return next(i for i in items if i.get("type") == kind and i["wall"] == wall)

    out = Path("renders/plan")

    # ================= bathroom: left wall x 61.5, door wall y 366.5 → far wall y 552.5; room 178 wide =================
    wx = 61.5
    boxes = [b for b in items if b.get("type") == "tiled_box" and b["wall"] == "bath_left"]
    hi, lo = sorted(boxes, key=lambda b: -b["height"])
    it, wc, bs = find("towel_warmer", "bath_left"), find("wall_toilet", "bath_left"), find("bidet_shower", "bath_left")
    bath_y = lo["span"][1]                                       # screen face: the bath's long side, y 474.5
    s = Sheet(366.5, 552.5, 178, "Полотенцесушитель — Ванная, левая стена",
              "вид на стену из комнаты и план под ним; размеры по чистовой (по плитке), см")
    d = s.d
    # elevation: boxes, bath, toilet on the box, the warmer
    for b, name in ((hi, "короб инсталляции"), (lo, "низкий короб")):
        y0, y1 = b["span"]
        s.erect(y0, y1, 0, b["height"], fill=FACE, outline=FACE_EDGE, width=3)
        s.prect(y0, y1, 0, b["depth"], fill=FACE, outline=FACE_EDGE, width=3)
    y0, y1 = hi["span"]
    s.text((s.X((y0 + y1) / 2), s.Z(60)), ["короб инсталляции", f"{num(y1 - y0)} × {num(hi['height'])}",
                                           f"глубина {num(hi['depth'])}"], 19, INK, bold_first=True)
    y0, y1 = lo["span"]
    s.text((s.X((y0 + y1) / 2), s.Z(10)), [f"короб {num(y1 - y0)} × {num(lo['height'])}"], 16, INK)
    s.text((s.X((y0 + y1) / 2), s.Dp(14)), ["низкий", "короб"], 16, INK)
    s.erect(bath_y, 552.5, 0, 60, fill=BATH, outline=GREY, width=2)
    s.text((s.X((bath_y + 552.5) / 2), s.Z(30)), ["ванна, борт 60"], 19, GREY)
    s.prect(bath_y, 552.5, 0, 178, fill=BATH, outline=GREY, width=2)
    d.rounded_rectangle([s.X(bath_y + 8), s.Dp(14), s.X(552.5 - 8), s.Dp(178 - 14)], radius=60, outline=LIGHT, width=2)
    s.text((s.X((bath_y + 552.5) / 2), s.Dp(100)), ["ванна 180 × 80"], 19, GREY)
    a, b = wc["span"]
    d.rounded_rectangle([s.X(a), s.Z(wc["seat_height"]), s.X(b), s.Z(7)], radius=22, fill="white", outline=GREY, width=2)
    d.rounded_rectangle([s.X(a), s.Dp(wc["gap"]), s.X(b), s.Dp(wc["gap"] + wc["depth"])], radius=40, fill="white",
                        outline=GREY, width=2)
    s.text((s.X((a + b) / 2), s.Z(25)), ["унитаз"], 16, GREY)
    s.text((s.X((a + b) / 2), s.Dp(wc["gap"] + 26)), ["унитаз"], 16, GREY)
    pw, ph = wc["plate"]["size"]
    s.erect((a + b - pw) / 2, (a + b + pw) / 2, wc["plate"]["z"] - ph / 2, wc["plate"]["z"] + ph / 2, outline=GREY,
            width=2)
    x, y = s.X(sum(bs["span"]) / 2), s.Z(bs["z"])
    d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=GREY, width=2)
    # the right wall in the plan: pencil case and vanity, for orientation
    for kind, name in (("niche_cabinet", "пенал"), ("cabinet", "тумба")):
        o = find(kind, "bath_right")
        s.prect(*o["span"], 178 - o["depth"], 178, fill=OTHER, outline=LIGHT, width=2)
        s.text((s.X(sum(o["span"]) / 2), s.Dp(178 - o["depth"] / 2)), [name], 17, GREY)
    s.room_plan((65.5, 145.5))
    w0, w1, z0, z1 = s.warmer(it, it["depth"])
    yc, zc = (w0 + w1) / 2, (z0 + z1) / 2
    s.axis(w0, w1, z0, z1, yc, zc)
    # the cable outlet, the user's: 5 above the bottom, on the axis of the right outer bar
    co = plan["bathroom"]["furniture"]["towel_warmer"]["heating"]["cable_outlet"]
    x, y = s.X(co["y"]), s.Z(co["z"])
    d.ellipse([x - 13, y - 13, x + 13, y + 13], outline=RED, width=3)
    d.line([x - 8, y, x + 8, y], fill=RED, width=2)
    d.line([x, y - 8, x, y + 8], fill=RED, width=2)
    s.text((x + 20, y - 4), [f"вывод провода, {num(co['z'])}"], 16, RED, "lm", bg="white")
    s.text((s.X(yc), s.Z(z1) - 40), ["полотенцесушитель", f"Inaro {num(w1 - w0)} × {num(z1 - z0)}"], 18, INK, bold_first=True, bg="white")
    # heights: warmer on the right, boxes and ceiling on the left
    s.heights([z0, zc, z1], s.R + 50, s.X(w1), [f"низ {num(z0)}", f"центр {num(zc)}", f"верх {num(z1)}"], BLUE)
    s.chain_v([s.Z(0), s.Z(co["z"])], s.R + 188, [s.R + 188, x], RED, [f"провод {num(co['z'])}"])
    s.heights([lo["height"], hi["height"], H], LEFT - 50,
              [s.X(lo["span"][0]), LEFT, LEFT], [f"короб {num(lo['height'])}", f"короб {num(hi['height'])}",
                                                  f"потолок {num(H)}"])
    # along the wall, from the door corner
    eb = s.EB
    s.chain_h([lo["span"][0], w0, w1, bath_y], eb + 45, [s.Z(lo["height"]), s.Z(z0), s.Z(z0), s.Z(60)], BLUE)
    s.chain_h([366.5, yc], eb + 100, [eb, s.Z(z0) + 30], BLUE, [f"до центра {num(yc - 366.5)}"])
    s.chain_h([366.5, co["y"]], eb + 155, [eb, y], RED, [f"до вывода провода {num(co['y'] - 366.5)}"])
    s.chain_h([366.5, hi["span"][1], lo["span"][1], 552.5], eb + 210, eb)
    s.chain_h([366.5, 552.5], eb + 260, eb)
    # plan: depths from the wall
    s.chain_v([s.Dp(0), s.Dp(hi["depth"])], LEFT - 50, LEFT, INK, [f"короб {num(hi['depth'])}"])
    s.chain_v([s.Dp(0), s.Dp(it["depth"])], s.R + 50, s.X(w1), BLUE, [num(it["depth"])])
    s.text((s.R + 66, s.Dp(it["depth"] / 2)), ["полотенце-", "сушитель"], 16, BLUE, "lm")
    s.chain_v([s.PT, s.PB], LEFT - 110, LEFT, INK)
    s.text((LEFT, s.PT - 26), ["план (вид сверху)"], 19, GREY, "lm")
    s.text((LEFT, TOP - 26), ["вид на левую стену из комнаты   ← стена с дверью"], 19, GREY, "lm")
    s.text((s.R, TOP - 26), ["дальняя стена →"], 19, GREY, "rm")
    s.finish([
        f"Полотенцесушитель Margroid Inaro {num(w1 - w0)} × {num(z1 - z0)} (между осями крайних труб "
        f"{num(w1 - w0 - 3)}): низ {num(z0)}, центр {num(zc)}, верх {num(z1)} от пола; центр в "
        f"{num(yc - 366.5)} от угла у двери, по центру низкого короба; от стены {num(it['depth'])}.",
        f"Короб инсталляции {num(hi['span'][1] - hi['span'][0])} × {num(hi['height'])}, глубина {num(hi['depth'])}; "
        f"низкий короб {num(lo['span'][1] - lo['span'][0])} × {num(lo['height'])}, глубина {num(lo['depth'])} — до "
        "экрана ванны. Торец короба инсталляции: профиль 28×27 на боковую стойку рамы + один лист ГКЛ + плитка с клеем. "
        "Размеры коробов по плитке (каркас и ГКЛ — лист «Каркас короба — Ванная»).",
        "Трубы прибора — 30 в ширину; крепления — плашки 40 × 40 мм к плитке, места — по шаблону из комплекта.",
        f"Вывод провода (красный): {num(co['from_bottom'] * 10)} мм от нижнего края прибора, по центру правой крайней "
        f"трубы — на {num(co['z'])} от пола, в {num(co['y'] - 366.5)} от угла у двери; делать до плитки. Прибор в зоне 2 "
        "у ванны: IPX4, подключение без розетки, УЗО 30 мА.",
    ], s.PB + 60)
    s.img.save(out / "towel_bathroom.png")
    print(out / "towel_bathroom.png")

    # ================= toilet: left wall x −101.5, door wall y 366.5 → far wall y 552.5; room 147.5 wide =================
    wx = -101.5
    it, wc = find("towel_warmer", "toilet_left"), find("wall_toilet", "toilet_far")
    box = find("tiled_box", "toilet_far")
    col, van = find("appliance_column", "toilet_right"), find("cabinet", "toilet_right")
    face = 552.5 - box["depth"]                                   # box face y 526
    s = Sheet(366.5, 552.5, 147.5, "Полотенцесушитель — Туалет, левая стена",
              "вид на стену из комнаты и план под ним; размеры по чистовой (по плитке), см")
    d = s.d
    # elevation: the box in section at the far end, the cabinet over it, the toilet from the side
    s.erect(face, 552.5, 0, box["height"], fill=FACE, outline=FACE_EDGE, width=3)
    s.erect(face, 552.5, box["height"], H, fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X((face + 552.5) / 2), s.Z(box["height"] / 2)), ["короб"], 17, INK)
    s.text((s.X((face + 552.5) / 2), s.Z(195)), ["шкаф"], 17, GREY)
    s.prect(face, 552.5, 0, 147.5, fill=FACE, outline=FACE_EDGE, width=3)
    s.vtext(s.X((face + 552.5) / 2), s.Dp(100), f"короб на всю стену: {num(147.5)} × {num(box['height'])}, "
            f"глубина {num(box['depth'])}", 17, INK)
    front = face - wc["depth"]
    xa, ya, xb, yb = s.X(front), s.Z(wc["seat_height"]), s.X(face), s.Z(7)
    d.rounded_rectangle([xa, ya, xb, yb], radius=22, fill="white", outline=GREY, width=2)
    s.text(((xa + xb) / 2, (ya + yb) / 2), ["унитаз", "(сбоку)"], 16, GREY)
    tx0, tx1 = sorted(wc["span"])
    d.rounded_rectangle([s.X(front), s.Dp(tx0 - wx), s.X(face), s.Dp(tx1 - wx)], radius=40, fill="white", outline=GREY,
                        width=2)
    s.text((s.X((front + face) / 2), s.Dp((tx0 + tx1) / 2 - wx)), ["унитаз"], 16, GREY)
    for o, name, at in ((col, ["колонна", "стирки", "и сушки"], col["span"][0] + 17), (van, ["тумба"], sum(van["span"]) / 2)):
        s.prect(*o["span"], 147.5 - o["depth"], 147.5, fill=OTHER, outline=LIGHT, width=2)
        s.text((s.X(at), s.Dp(147.5 - o["depth"] / 2)), name, 17, GREY)
    s.room_plan((7.5, 87.5))
    w0, w1, z0, z1 = s.warmer(it, it["depth"])
    yc, zc = (w0 + w1) / 2, (z0 + z1) / 2
    s.axis(w0, w1, z0, z1, yc, zc)
    co = plan["toilet"]["furniture"]["towel_warmer"]["heating"]["cable_outlet"]
    x, y = s.X(co["y"]), s.Z(co["z"])
    d.ellipse([x - 13, y - 13, x + 13, y + 13], outline=RED, width=3)
    d.line([x - 8, y, x + 8, y], fill=RED, width=2)
    d.line([x, y - 8, x, y + 8], fill=RED, width=2)
    s.text((x + 20, y - 4), [f"вывод провода, {num(co['z'])}"], 16, RED, "lm", bg="white")
    s.text((s.X(yc), s.Z(z1) - 40), ["полотенцесушитель", "Маргроид 50 × 80"], 18, INK, bold_first=True, bg="white")
    s.heights([z0, zc, z1], s.R + 50, s.X(w1), [f"низ {num(z0)}", f"центр {num(zc)}", f"верх {num(z1)}"], BLUE)
    s.chain_v([s.Z(0), s.Z(co["z"])], s.R + 188, [s.R + 188, x], RED, [f"провод {num(co['z'])}"])
    s.heights([box["height"], H], LEFT - 50, [s.X(face), LEFT], [f"короб {num(box['height'])}", f"потолок {num(H)}"])
    eb = s.EB
    s.chain_h([366.5, w0, w1, front, face, 552.5], eb + 45, [eb, s.Z(z0), s.Z(z0), s.Z(7), eb, eb], BLUE)
    s.chain_h([366.5, yc], eb + 100, [eb, s.Z(z0) + 30], BLUE, [f"до центра {num(yc - 366.5)}"])
    s.chain_h([366.5, co["y"]], eb + 155, [eb, y], RED, [f"до вывода провода {num(co['y'] - 366.5)}"])
    s.chain_h([366.5, 552.5], eb + 210, eb)
    # plan: the warmer, the passage to the column, the column; the room width
    s.chain_v([s.Dp(0), s.Dp(it["depth"]), s.Dp(147.5 - col["depth"]), s.Dp(147.5)], s.X(yc), s.X(yc), BLUE,
              [num(it["depth"]), f"проход {num(147.5 - col['depth'] - it['depth'])}", num(col["depth"])])
    s.chain_v([s.PT, s.PB], LEFT - 110, LEFT, INK)
    s.text((LEFT, s.PT - 26), ["план (вид сверху)"], 19, GREY, "lm")
    s.text((LEFT, TOP - 26), ["вид на левую стену из комнаты   ← стена с дверью"], 19, GREY, "lm")
    s.text((s.R, TOP - 26), ["короб за унитазом →"], 19, GREY, "rm")
    s.finish([
        f"Полотенцесушитель Маргроид 50 × 80 (лесенка): низ {num(z0)}, центр {num(zc)}, верх {num(z1)} от пола; центр в "
        f"{num(yc - 366.5)} от угла у двери; от стены {num(it['depth'])}; напротив колонны стирки и сушки, проход "
        f"{num(147.5 - col['depth'] - it['depth'])}.",
        f"Короб на всю дальнюю стену: {num(147.5)} × {num(box['height'])}, глубина {num(box['depth'])} (лицо короба в "
        f"{num(face - 366.5)} от стены с дверью); над ним шкаф до потолка той же глубины. Размеры по плитке "
        "(каркас и ГКЛ — лист «Каркас короба — Туалет»).",
        f"Вывод провода (красный): {num(co['from_bottom'] * 10)} мм от нижнего края прибора, по центру правой стойки — "
        f"на {num(co['z'])} от пола, в {num(co['y'] - 366.5)} от угла у двери; делать до плитки.",
        f"Стойки — трубы 30 в ширину; крепления — 4 плашки 40 × 40 мм к плитке (голубые квадраты): на осях стоек, "
        f"≈ {num(z0 + 12)} и {num(z1 - 12)} от пола — места предложены, точно по шаблону из комплекта.",
    ], s.PB + 60)
    s.img.save(out / "towel_toilet.png")
    print(out / "towel_toilet.png")


if __name__ == "__main__":
    main()
