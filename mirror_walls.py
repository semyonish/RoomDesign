"""Стены с зеркалами (ванная и туалет, правые стены): чертёж с размерами без плитки, как «Полотенцесушитель». Вверху —
вид на стену из комнаты (пенал или колонна, тумба с раковиной, зеркало, ванна или короб; высоты от пола), под ним в той
же привязке — план сверху. Главное — вывод кабеля зеркала: высота от пола и расстояние от угла у двери. В ванной — зоны
электробезопасности у ванны (ГОСТ Р 50571.7.701). Всё по чистовой (по плитке), см.

Стена правая, поэтому, глядя на неё из комнаты, дверь справа; план повёрнут так же (стена сверху).

    .venv/bin/python mirror_walls.py    # renders/plan/mirror_bathroom.png, mirror_toilet.png
                                        # → export.py → Рендеры/Планы/Зеркало — Ванная|Туалет.png
"""
import json
from pathlib import Path

from plans import num
from towel_walls import BATH, BLUE, FACE, FACE_EDGE, GREY, INK, LEFT, LIGHT, OTHER, RED, SC, TOP, H, Sheet

GLASS, GLOW, CHROME = (214, 226, 232), (255, 238, 170), (190, 192, 196)
ZONE, OFFER = (150, 70, 180), (30, 140, 80)       # electrical zones; a proposed point (assumed in plan.json)
FRAME = 8.3                                       # AtlasDesign frame


class Mirrored(Sheet):
    """A right-hand wall: seen from the room the door corner is on the right, so plan y runs right to left."""

    def __init__(self, y_door, y_far, depth, title, sub, gap=0):
        self.yf = y_far
        super().__init__(y_door, y_far, depth, title, sub)
        self.PT += gap                                  # more room for chains between the elevation and the plan
        self.PB += gap

    def X(self, y):
        return LEFT + (self.yf - y) * SC

    def erect(self, y0, y1, z0, z1, **kw):
        a, b = sorted((self.X(y0), self.X(y1)))
        self.d.rectangle([a, self.Z(z1), b, self.Z(z0)], **kw)

    def prect(self, y0, y1, d0, d1, **kw):
        a, b = sorted((self.X(y0), self.X(y1)))
        self.d.rectangle([a, self.Dp(d0), b, self.Dp(d1)], **kw)

    def room_plan(self, door):
        """The outline with the door opening in the door wall, the right edge here."""
        x0, x1, a, b = LEFT, self.R, self.PT, self.PB
        self.d.line([x0, a, x1, a], fill=INK, width=5)
        self.d.line([x0, a, x0, b], fill=INK, width=5)
        self.d.line([x0, b, x1, b], fill=INK, width=5)
        self.d.line([x1, a, x1, self.Dp(door[0])], fill=INK, width=5)
        self.d.line([x1, self.Dp(door[1]), x1, b], fill=INK, width=5)
        self.d.line([x1, self.Dp(door[0]), x1, self.Dp(door[1])], fill=LIGHT, width=2)
        self.text((x1 + 14, self.Dp(sum(door) / 2)), ["дверь"], 17, GREY, "lm")

    def dashed(self, pts, fill, width=3, dash=12, gap=8):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(abs(x1 - x0), abs(y1 - y0))
            k = 0.0
            while k < n:
                e = min(k + dash, n)
                self.d.line([x0 + (x1 - x0) * k / n, y0 + (y1 - y0) * k / n,
                             x0 + (x1 - x0) * e / n, y0 + (y1 - y0) * e / n], fill=fill, width=width)
                k += dash + gap

    # ---- objects ----
    def vanity(self, cab, top):
        y0, y1 = sorted(cab["span"])
        z0, z1 = cab["elevation"], cab["elevation"] + cab["height"]
        self.erect(y0, y1, z0, z1, fill=OTHER, outline=GREY, width=2)
        for k in range(1, cab["drawers"]):
            z = z0 + (z1 - z0) * k / cab["drawers"]
            self.d.line([self.X(y1), self.Z(z), self.X(y0), self.Z(z)], fill=LIGHT, width=2)
        self.erect(y0, y1, top["height"] - top["thickness"], top["height"], fill="white", outline=GREY, width=2)
        zt = z1 - (z1 - z0) / cab["drawers"] / 2         # in the upper drawer, clear of the drawer joint
        self.text((self.X((y0 + y1) / 2), self.Z(zt)), [f"тумба {num(y1 - y0)} × {num(top['depth'])}"], 17, GREY)
        self.prect(y0, y1, 0, top["depth"], fill=OTHER, outline=LIGHT, width=2)
        self.text((self.X((y0 + y1) / 2), self.Dp(top["depth"] / 2)), ["тумба"], 17, GREY)
        return y0, y1, z0, top["height"]

    def mirror(self, it):
        y0, y1 = sorted(it["span"])
        z0, z1 = it["elevation"], it["elevation"] + it["height"]
        self.erect(y0, y1, z0, z1, fill=GLASS, outline=INK, width=3)
        bl = it.get("backlight") or {}
        i, b = bl.get("inset", 3), bl.get("band", 2.5)
        xa, xb = sorted((self.X(y0), self.X(y1)))
        for k in range(int(b * SC)):                    # the lit band around the glass
            e = i * SC + k
            self.d.rectangle([xa + e, self.Z(z1) + e, xb - e, self.Z(z0) - e], outline=GLOW)
        self.prect(y0, y1, 0, 3, fill=GLASS, outline=INK, width=2)
        return y0, y1, z0, z1

    def cable(self, y, z, tag):
        """The cable end behind the mirror (no box: the mirror's own terminals take it), and the same point in plan."""
        x, zz = self.X(y), self.Z(z)
        self.d.ellipse([x - 13, zz - 13, x + 13, zz + 13], fill="white", outline=RED, width=4)
        self.d.line([x - 8, zz - 8, x + 8, zz + 8], fill=RED, width=3)
        self.d.line([x - 8, zz + 8, x + 8, zz - 8], fill=RED, width=3)
        self.text((x, zz - 44), tag, 17, RED, bg="white")
        p = self.Dp(0)
        self.d.ellipse([x - 10, p - 10, x + 10, p + 10], fill="white", outline=RED, width=4)

    def socket(self, y, z, color, hidden=False):
        """A one-post socket frame on the wall; dashed when it is hidden inside a cabinet; and its mark in plan."""
        x0, x1 = sorted((self.X(y - FRAME / 2), self.X(y + FRAME / 2)))
        z0, z1 = self.Z(z + FRAME / 2), self.Z(z - FRAME / 2)
        self.d.rounded_rectangle([x0, z0, x1, z1], 5, fill="white", outline=color, width=3)
        if hidden:
            for k in range(int(x0), int(x1), 10):
                self.d.line([k, z0, min(k + 5, x1), z0], fill="white", width=3)
                self.d.line([k, z1, min(k + 5, x1), z1], fill="white", width=3)
        r = 5.6 / 2 * SC * 0.7
        xc, zc = (x0 + x1) / 2, (z0 + z1) / 2
        self.d.ellipse([xc - r, zc - r, xc + r, zc + r], outline=color, width=2)
        self.d.rectangle([x0, self.Dp(0), x1, self.Dp(1.5)], fill="white", outline=color, width=2)


def main():
    cfg = json.loads(Path("rooms/apartment.json").read_text())
    plan = json.loads(Path("plan.json").read_text())
    items = cfg["furniture"]
    rooms = {r["id"]: r for r in plan["rooms"]}
    out = Path("renders/plan")
    door_y = 366.5

    def find(kind, wall):
        return next(i for i in items if i.get("type") == kind and i["wall"] == wall)

    # ================= bathroom: right wall x 239.5, door wall y 366.5 → far wall y 552.5; room 178 wide =================
    wx, width = 239.5, 178
    W = "bath_right"
    pw = rooms["bathroom"]["furniture"]["mirror"]["power"]
    cy, cz = pw["y"], pw["z"]
    mi, cab, top = find("mirror", W), find("cabinet", W), find("basin_top", W)
    nc, mix = find("niche_cabinet", W), find("bath_mixer", W)
    lo = next(b for b in items if b.get("type") == "tiled_box" and b["wall"] == "bath_left" and b["height"] < 100)
    hi = next(b for b in items if b.get("type") == "tiled_box" and b["wall"] == "bath_left" and b["height"] >= 100)
    wc, tw = find("wall_toilet", "bath_left"), find("towel_warmer", "bath_left")
    bath_y, far = 474.0, 552.5
    z2 = bath_y - 60
    so = next(o for o in plan["outlets"]["items"] if o["id"] == "O_bath_pencil")
    sy, sz = so["y"], so["z"]
    s = Mirrored(door_y, far, width, "Зеркало — Ванная, правая стена",
                 "вид на стену из комнаты и план под ним; размеры по чистовой (по плитке), см", gap=50)
    d = s.d
    # elevation: the tall cabinet by the door, the bath at the far end with the thermostat over it
    s.erect(*nc["span"], 0, H, fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X(sum(nc["span"]) / 2), s.Z(160)), ["пенал", "до потолка"], 17, GREY)
    s.d.line([s.X(nc["span"][1]) + 4, s.Z(sz - 10), s.X(nc["span"][0]) - 4, s.Z(sz - 10)], fill=LIGHT, width=2)
    s.text((s.X(sy), s.Z(sz - 10) + 14), ["полка ~100"], 15, GREY)
    s.erect(bath_y, far, 0, 60, fill=BATH, outline=GREY, width=2)
    s.text((s.X((bath_y + far) / 2), s.Z(30)), ["ванна, борт 60"], 19, GREY)
    m0, m1 = mix["span"]
    mc, (rain_top, _, rain_d) = (m0 + m1) / 2, mix["rain"]
    s.erect(mc - 1, mc + 1, mix["z"], rain_top, fill=CHROME, outline=GREY, width=1)
    s.erect(m0, m1, mix["z"] - 2.5, mix["z"] + 2.5, fill=CHROME, outline=GREY, width=2)
    s.erect(mc - rain_d / 2, mc + rain_d / 2, rain_top - 1.5, rain_top + 0.5, fill=CHROME, outline=GREY, width=2)
    s.text((s.X(mc), s.Z(mix["z"] - 9)), ["смеситель"], 16, GREY)
    v0, v1, vz0, vz1 = s.vanity(cab, top)
    g0, g1, gz0, gz1 = s.mirror(mi)
    s.axis(g1, g0, gz0, gz1, (g0 + g1) / 2, (gz0 + gz1) / 2)
    s.text((s.X((g0 + g1) / 2), s.Z(gz1) - 40), [f"зеркало {num(g1 - g0)} × {num(gz1 - gz0)}", "с подсветкой"], 18,
           INK, bold_first=True, bg="white")
    s.cable(cy, cz, ["вывод", "кабеля"])
    # electrical zones by the bath (to 225 from the floor): 1 over it, 2 within 60 of it; in plan too
    s.dashed([(s.X(z2), s.Z(0)), (s.X(z2), s.Z(225)), (s.X(far), s.Z(225))], ZONE)
    s.dashed([(s.X(bath_y), s.Z(60)), (s.X(bath_y), s.Z(225))], ZONE, 2)
    s.text(((s.X(z2) + s.X(bath_y)) / 2, s.Z(235)), ["зона 2"], 18, ZONE)
    s.text(((s.X(bath_y) + s.X(far)) / 2, s.Z(235)), ["зона 1 (над ванной)"], 18, ZONE)
    # plan: the bath, the left wall's boxes, toilet and warmer for orientation, the zone 2 line
    s.prect(*nc["span"], 0, nc["depth"], fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X(sum(nc["span"]) / 2), s.Dp(nc["depth"] / 2)), ["пенал"], 17, GREY)
    s.socket(sy, sz, OFFER, hidden=True)          # after the cabinet in plan, so its mark stays on top
    s.text((s.X(sy), s.Z(sz) - 44), ["розетка", "в пенале?"], 16, OFFER, bg="white")
    s.prect(bath_y, far, 0, width, fill=BATH, outline=GREY, width=2)
    xa, xb = sorted((s.X(bath_y + 8), s.X(far - 8)))
    d.rounded_rectangle([xa, s.Dp(14), xb, s.Dp(width - 14)], radius=60, outline=LIGHT, width=2)
    s.text((s.X((bath_y + far) / 2), s.Dp(100)), ["ванна 180 × 80"], 19, GREY)
    for b in (hi, lo):
        s.prect(*b["span"], width - b["depth"], width, fill=FACE, outline=FACE_EDGE, width=2)
    s.text((s.X((hi["span"][0] + z2) / 2 + 2), s.Dp(width - hi["depth"] / 2)), ["короб инсталляции"], 16, INK)
    a, b = wc["span"]
    xa, xb = sorted((s.X(a), s.X(b)))
    d.rounded_rectangle([xa, s.Dp(width - wc["gap"] - wc["depth"]), xb, s.Dp(width - wc["gap"])], radius=40,
                        fill="white", outline=GREY, width=2)
    s.text((s.X((a + b) / 2), s.Dp(width - wc["gap"] - 26)), ["унитаз"], 16, GREY, bg="white")
    s.prect(*tw["span"], width - tw["depth"], width, fill="white", outline=GREY, width=2)
    s.room_plan((wx - 207, wx - 127))
    s.dashed([(s.X(z2), s.PT), (s.X(z2), s.PB)], ZONE, 2)
    s.text((s.X(z2) - 8, s.Dp(70)), ["граница", "зоны 2"], 16, ZONE, "rm", bg="white")
    # heights: the mirror and its cable on the right, the vanity and ceiling on the left
    s.heights([gz0, gz1], s.R + 50, s.X(g0), [f"низ {num(gz0)}", f"верх {num(gz1)}"], BLUE)
    s.heights([cz], s.R + 142, s.X(cy) + 13, [f"кабель {num(cz)}"], RED)
    s.heights([sz], s.R + 188, s.X(sy) + FRAME / 2 * SC, [f"розетка {num(sz)}"], OFFER)
    s.heights([vz0, vz1, 225, H], LEFT - 50, [s.X(v1), s.X(v1), s.X(z2), LEFT],
              [f"тумба {num(vz0)}", f"раковина {num(vz1)}", "зона 225", f"потолок {num(H)}"])
    # along the wall, all from the door corner (on the right)
    eb = s.EB
    s.chain_h([bath_y, g1, cy, g0, nc["span"][0], door_y], eb + 45,
              [s.Z(60), s.Z(vz0), s.Z(cz) + 14, s.Z(vz0), eb, eb], BLUE)
    s.chain_h([cy, door_y], eb + 100, [s.Z(cz) + 14, eb], RED, [f"кабель: от угла у двери {num(cy - door_y)}"])
    s.chain_h([sy, door_y], eb + 155, [s.Z(sz) + FRAME / 2 * SC, eb], OFFER,
              [f"розетка: от угла у двери {num(sy - door_y)}"])
    s.chain_h([far, bath_y, z2, door_y], eb + 205, [eb, s.Z(60), s.Z(0), eb], ZONE,
              [f"ванна {num(far - bath_y)}", "зона 2: 60", f"{num(z2 - door_y)}"])
    s.chain_h([far, door_y], eb + 255, eb)
    # plan: depths
    s.chain_v([s.Dp(0), s.Dp(top["depth"])], s.X(v1) - 30, s.X(v1), BLUE, [num(top["depth"])])
    s.chain_v([s.PT, s.PB], LEFT - 110, LEFT, INK)
    s.text((LEFT, s.PT - 26), ["план (вид сверху)"], 19, GREY, "lm")
    s.text((LEFT, TOP - 26), ["вид на правую стену из комнаты   ← дальняя стена (ванна)"], 19, GREY, "lm")
    s.text((s.R, TOP - 26), ["стена с дверью →"], 19, GREY, "rm")
    s.finish([
        f"Вывод кабеля зеркала: на {num(cz)} от чистового пола, в {num(cy - door_y)} от угла у двери (по плитке) — по оси "
        f"зеркала и тумбы. Зеркало {num(g1 - g0)} × {num(gz1 - gz0)} с подсветкой висит на {num(gz0)}–{num(gz1)}: "
        f"вывод в {num(gz1 - cz)} ниже верха и в {num(cz - gz0)} выше низа — закрыт зеркалом и далеко от креплений у "
        "верхнего края; зеркало высотой 60 на 120–180 тоже его закроет.",
        f"Точка в зоне 2 ({num(bath_y - cy)} от ванны, ближе 60): в стене только конец кабеля, без коробки и разъёма, "
        "запас ~40; подключение — в клеммах зеркала. Питание постоянное (зеркало включается своей кнопкой), линия "
        "через УЗО 30 мА. Место сверить с паспортом выбранного зеркала до плитки.",
        f"Фиолетовый пунктир — зоны у ванны до 225 от пола: розетка возможна только ближе к двери, чем {num(z2)} "
        f"({num(z2 - door_y)} от угла у двери).",
        f"Зелёным — розетка внутри пенала (предложено, не решено): на стене за пеналом по его оси, в "
        f"{num(sy - door_y)} от угла у двери, на {num(sz)}; полка в пенале ~100, в задней стенке пенала вырез. "
        f"{num(bath_y - sy)} от ванны — вне зоны 2, брызги за дверкой не попадают. С заземлением, линия через УЗО "
        "30 мА; подрозетник — до укладки плитки.",
    ], s.PB + 60)
    s.img.save(out / "mirror_bathroom.png")
    print(out / "mirror_bathroom.png")

    # ================= toilet: right wall x 46, door wall y 366.5 → far wall y 552.5; room 147.5 wide =================
    wx, width = 46.0, 147.5
    W = "toilet_right"
    pw = rooms["toilet"]["mirror"]["power"]
    cy, cz = pw["y"], pw["z"]
    mi, cab, top = find("mirror", W), find("cabinet", W), find("basin_top", W)
    col, box = find("appliance_column", W), find("tiled_box", "toilet_far")
    wc, tw = find("wall_toilet", "toilet_far"), find("towel_warmer", "toilet_left")
    sock = next(e for e in cfg["electrical"] if e["wall"] == "toilet_far" and e["type"] == "outlet")
    face = far - box["depth"]
    s = Mirrored(door_y, far, width, "Зеркало — Туалет, правая стена",
                 "вид на стену из комнаты и план под ним; размеры по чистовой (по плитке), см")
    d = s.d
    # elevation: the laundry column by the door, the box in section at the far end with the cabinet over it
    s.erect(*col["span"], 0, H, fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X(sum(col["span"]) / 2), s.Z(140)), ["колонна", "стирки и сушки", "до потолка"], 17, GREY)
    s.erect(face, far, 0, box["height"], fill=FACE, outline=FACE_EDGE, width=3)
    s.erect(face, far, box["height"], H, fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X((face + far) / 2), s.Z(60)), ["короб"], 17, INK)
    s.text((s.X((face + far) / 2), s.Z(195)), ["шкаф"], 17, GREY)
    v0, v1, vz0, vz1 = s.vanity(cab, top)
    g0, g1, gz0, gz1 = s.mirror(mi)
    s.axis(g1, g0, gz0, gz1, (g0 + g1) / 2, (gz0 + gz1) / 2)
    s.text((s.X((g0 + g1) / 2), s.Z(gz1) - 40), [f"зеркало {num(g1 - g0)} × {num(gz1 - gz0)}", "с подсветкой"], 18,
           INK, bold_first=True, bg="white")
    s.cable(cy, cz, ["вывод", "кабеля"])
    # the IP44 socket on the box face, edge-on in the elevation, on the face in the plan
    sd, sz = wx - sock["centers"][0], sock["z"]
    s.erect(face - 1.5, face, sz - 4.15, sz + 4.15, fill="white", outline=INK, width=2)
    s.text((s.X(face) + 8, s.Z(sz)), ["розетка"], 16, INK, "lm", bg="white")
    # plan: the column, the box over the whole far wall, the toilet on it, the warmer on the left wall
    s.prect(*col["span"], 0, col["depth"], fill=OTHER, outline=LIGHT, width=2)
    s.text((s.X(sum(col["span"]) / 2), s.Dp(col["depth"] / 2)), ["колонна"], 17, GREY)
    s.prect(face, far, 0, width, fill=FACE, outline=FACE_EDGE, width=2)
    s.vtext(s.X((face + far) / 2), s.Dp(width / 2), "короб на всю стену", 16, INK)
    front = face - wc["depth"]
    tx0, tx1 = sorted(wc["span"])
    xa, xb = sorted((s.X(front), s.X(face)))
    d.rounded_rectangle([xa, s.Dp(wx - tx1), xb, s.Dp(wx - tx0)], radius=40, fill="white", outline=GREY, width=2)
    s.text((s.X((front + face) / 2), s.Dp(wx - (tx0 + tx1) / 2)), ["унитаз"], 16, GREY)
    s.prect(*tw["span"], width - tw["depth"], width, fill="white", outline=GREY, width=2)
    xs = s.X(face)
    d.rectangle([xs, s.Dp(sd - 4.15), xs + 1.5 * SC, s.Dp(sd + 4.15)], fill="white", outline=INK, width=2)
    s.room_plan((wx + 14, wx + 94))
    # heights
    s.heights([gz0, gz1], s.R + 50, s.X(g0), [f"низ {num(gz0)}", f"верх {num(gz1)}"], BLUE)
    s.heights([cz], s.R + 142, s.X(cy) + 13, [f"кабель {num(cz)}"], RED)
    s.heights([vz0, vz1, sz, box["height"], H], LEFT - 50, [s.X(v1), s.X(v1), s.X(face), s.X(face), LEFT],
              [f"тумба {num(vz0)}", f"раковина {num(vz1)}", f"розетка {num(sz)}", f"короб {num(box['height'])}",
               f"потолок {num(H)}"])
    eb = s.EB
    s.chain_h([face, g1, cy, g0, v0, col["span"][1], col["span"][0], door_y], eb + 45,
              [s.Z(0), s.Z(gz0), s.Z(cz) + 14, s.Z(gz0), s.Z(vz0), eb, eb, eb], BLUE)
    s.chain_h([cy, door_y], eb + 100, [s.Z(cz) + 14, eb], RED, [f"кабель: от угла у двери {num(cy - door_y)}"])
    s.chain_h([far, door_y], eb + 155, eb)
    s.chain_v([s.Dp(0), s.Dp(sd)], s.X(face) - 30, s.X(face), INK, [num(sd)])
    s.chain_v([s.PT, s.PB], LEFT - 110, LEFT, INK)
    s.text((LEFT, s.PT - 26), ["план (вид сверху)"], 19, GREY, "lm")
    s.text((LEFT, TOP - 26), ["вид на правую стену из комнаты   ← короб за унитазом"], 19, GREY, "lm")
    s.text((s.R, TOP - 26), ["стена с дверью →"], 19, GREY, "rm")
    s.finish([
        f"Вывод кабеля зеркала: на {num(cz)} от чистового пола, в {num(cy - door_y)} от угла у двери (по плитке), "
        f"{num(face - cy)} до лица короба — по оси зеркала и тумбы. Зеркало {num(g1 - g0)} × {num(gz1 - gz0)} с "
        f"подсветкой висит на {num(gz0)}–{num(gz1)}: вывод в {num(gz1 - cz)} ниже верха и в {num(cz - gz0)} выше низа — "
        "закрыт зеркалом и далеко от креплений у верхнего края.",
        "Конец кабеля, запас ~40; подключение — в клеммах зеркала, без розетки. Питание постоянное (своя кнопка на "
        "зеркале), линия через УЗО 30 мА. Место сверить с паспортом выбранного зеркала до плитки.",
        f"Рядом: влагозащищённая розетка с крышкой на лице короба слева от раковины — на {num(sz)} от пола, центр в "
        f"{num(sd)} от этой стены (на 15 выше раковины).",
    ], s.PB + 60)
    s.img.save(out / "mirror_toilet.png")
    print(out / "mirror_toilet.png")


if __name__ == "__main__":
    main()
