"""The toilet box with the cabinet over it and the horizontal water heater above the toilet, for the installer, the
plumber and the furniture maker: front elevation from the room (doors off), a section through the heater, notes, cm.

Data: plan_carcass.json → boxes.toilet (the frame of the box below 120, the riser) and boxes.toilet.upper (the
cabinet, the heater, fittings, pipe paths, funnel, outlets, notes). Local coordinates as in boxes.py: s along the far
wall from the rough left wall (x −103), d from the rough far wall (y 554), z over the finished floor.

    .venv/bin/python boiler_box.py      # renders/plan/boiler_toilet.png → «Короб с бойлером — Туалет»
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT, BOLD = "/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
INK, GREY, RED = (30, 30, 30), (120, 120, 120), (210, 40, 40)
PIPE = {"hot": (215, 70, 40), "cold": (40, 110, 210), "drain": (40, 150, 150), "grey": (150, 150, 150)}
WALL, FRAME, GKL, TILE = (95, 95, 95), (175, 175, 175), (236, 226, 205), (205, 215, 222)
WOOD, DOOR, BODY, METAL, VALVE = (196, 168, 140), (118, 96, 79), (226, 228, 232), (150, 150, 155), (240, 200, 60)
RISER = (205, 205, 205)
PROF = {"ПН": (150, 185, 230), "ПП": (150, 205, 170)}
PLAN = json.loads(Path("plan_carcass.json").read_text())
BOX = PLAN["boxes"]["toilet"]
UP = BOX["upper"]
B, C = UP["boiler"], UP["cabinet"]
L, F, TL = BOX["length"], BOX["front"], BOX["tile"]
CEIL = UP["ceiling"]["z"]
SC, SC2 = 4.5, 7.0                       # px per cm: elevation, section


def num(x):
    return f"{x:g}".replace(".", ",")


def main(out=Path("renders/plan")):
    f_b, f_m, f_s, f_xs = (ImageFont.truetype(BOLD, 30), ImageFont.truetype(FONT, 20), ImageFont.truetype(FONT, 17),
                           ImageFont.truetype(FONT, 15))
    ex0, ey0 = 190, 330                  # elevation: s 0 at ex0, z CEIL+3 at ey0
    sx0 = ex0 + (L + 8) * SC + 330       # section: d 0 at sx0
    z_cut = 108                          # the section shows z_cut..CEIL
    W, H = int(sx0 + 40 * SC2 + 560), 3400
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    def E(s, z):
        return ex0 + s * SC, ey0 + (CEIL + 3 - z) * SC

    def S(dd, z):
        return sx0 + dd * SC2, ey0 + (CEIL + 3 - z) * SC2

    def rect(p0, p1, **kw):
        d.rectangle([min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])], **kw)

    def dashed(a, b, color, dash=7, width=2):
        (x0, y0), (x1, y1) = a, b
        n = max(1, int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 // dash))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n)
            d.line([x0 + (x1 - x0) * t0, y0 + (y1 - y0) * t0, x0 + (x1 - x0) * t1, y0 + (y1 - y0) * t1],
                   fill=color, width=width)

    def dashed_rect(p0, p1, color, dash=7, width=2):
        x0, y0, x1, y1 = min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1])
        for a, b in (((x0, y0), (x1, y0)), ((x0, y1), (x1, y1)), ((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))):
            dashed(a, b, color, dash, width)

    def tag(xy, text, color, anchor, font=None):
        font = font or f_xs
        x0, y0, x1, y1 = d.textbbox(xy, text, font=font, anchor=anchor)
        d.rectangle([x0 - 3, y0 - 2, x1 + 3, y1 + 2], fill="white")
        d.text(xy, text, fill=color, font=font, anchor=anchor)

    def chain_h(marks, y, P, above=True, label=None):
        marks = sorted(set(marks))
        d.line([P(marks[0], 0)[0], y, P(marks[-1], 0)[0], y], fill=INK, width=2)
        for m in marks:
            x = P(m, 0)[0]
            d.line([x - 5, y + 5, x + 5, y - 5], fill=INK, width=2)
        lifted = 0
        for a, b in zip(marks, marks[1:]):
            x = (P(a, 0)[0] + P(b, 0)[0]) / 2
            txt = num(round(b - a, 2))
            off = 4
            if d.textlength(txt, font=f_xs) + 4 > P(b, 0)[0] - P(a, 0)[0]:   # no room: lift it, staggered
                lifted += 1
                off = 4 + 18 * (1 + lifted % 2)
                d.line([x, y, x, y - off + 14 if above else y + off - 14], fill=GREY, width=1)
            d.text((x, y - off if above else y + off), txt, fill=INK, font=f_xs, anchor="mb" if above else "mt")
        if label:
            d.text((P(marks[0], 0)[0] - 10, y), label, fill=GREY, font=f_xs, anchor="rm")

    def chain_v(zs, x, P):
        zs = sorted(set(zs))
        d.line([x, P(0, zs[0])[1], x, P(0, zs[-1])[1]], fill=INK, width=1)
        last = -1e9
        for z in reversed(zs):
            y = P(0, z)[1]
            d.line([x - 7, y, x + 7, y], fill=INK, width=2)
            ty = max(y, last + 18)
            d.text((x + 12, ty), num(z), fill=INK, font=f_xs, anchor="lm")
            last = ty

    bs0, bs1 = B["s"]
    bz0, bz1 = B["z"]
    axis = (bz0 + bz1) / 2
    z_stub = bz0 - B["stub_length"]
    stub_s = {st["name"]: round(bs0 + st["from_left"], 2) for st in B["stubs"]}
    z0, z1 = C["z"]
    bd = C["board"]
    part = C["partition"]
    riser = BOX["riser"]
    hooks = B["hooks"]

    # ---------------------------------------------------------------- header
    d.text((ex0, 30), "Короб и шкаф с бойлером — Туалет", fill=INK, font=f_b)
    d.text((ex0, 72), f"{B['short']}: {num(B['length'])} × {num(B['height'])} (с патрубками "
                      f"{num(B['height'] + B['stub_length'])}) × {num(B['depth'])} с кронштейнами; {num(B['weight'])} кг, "
                      f"с водой ~{num(round(B['weight'] + B['volume']))} кг", fill=GREY, font=f_m)
    d.text((ex0, 100), "вид из туалета на дальнюю стену; s — от черновой левой стены (x −103), d — от черновой дальней "
                       "стены (y 554), высоты — от чистового пола", fill=GREY, font=f_m)
    d.text((ex0, 128), UP["status"], fill=GREY, font=f_m)

    # ---------------------------------------------------------------- elevation
    d.text((ex0, ey0 - 140), "Вид спереди: двери шкафа сняты, ГКЛ и плитка короба сняты", fill=INK, font=f_m)
    rect(E(-6, -4), E(0, CEIL + 3), fill=WALL)
    rect(E(L, -4), E(L + 6, CEIL + 3), fill=WALL)
    rect(E(-6, -4), E(L + 6, -2), fill=WALL)
    for s0, s1 in ((0, TL), (L - TL, L)):        # tile on the side walls, in front of the rough faces
        rect(E(s0, -2), E(s1, CEIL), fill=TILE)
    dashed(E(-6, CEIL), E(L + 6, CEIL), GREY)
    d.text(E(-8, CEIL), f"потолок {num(CEIL)}?", fill=GREY, font=f_xs, anchor="rm")
    d.line([E(0, 0), E(L, 0)], fill=GREY, width=1)
    d.text(E(-8, 0), "чист. пол", fill=GREY, font=f_xs, anchor="rm")

    # the box below 120: frame pieces pale, the Grohe frame, the riser behind
    f0, f1 = BOX["frame"]
    rect(E(TL, -2), E(L - TL, 117.5), fill=(250, 250, 250))
    rect(E(*riser["s"][:1], -2), E(riser["s"][1], CEIL), fill=RISER, outline=GREY)
    d.text(E(sum(riser["s"]) / 2, 180), "стояк", fill=INK, font=f_xs, anchor="mm")
    d.text(E(sum(riser["s"]) / 2, 176), "Ø110", fill=INK, font=f_xs, anchor="mm")
    rect(E(f0, -2), E(f1, 113), fill=(238, 238, 238), outline=FRAME, width=2)
    for p in (f0, f1 - 4):
        rect(E(p, -2), E(p + 4, 113), fill=FRAME)
    d.text(E((f0 + f1) / 2, 60), "рама Rapid SL", fill=GREY, font=f_s, anchor="mm")
    d.text(E((f0 + f1) / 2, 55), "на проставках 10", fill=GREY, font=f_xs, anchor="mm")
    for q in BOX["pieces"]:
        s0, s1, qz0, qz1, d0, d1 = *q["s"], *q["z"], *q["d"]
        if d1 - d0 > 10 or d1 <= 3:              # ties and the back track: behind
            continue
        rect(E(s0, qz0), E(s1, qz1), fill=PROF[q["profile"]])
    rect(E(0, 117.5), E(L, 120), fill=GKL, outline=(200, 170, 120))
    tag(E(L / 2 + 8, 112), "короб: ГКЛ 2 слоя + плитка до 120, без люка — см. «Каркас короба — Туалет»", GREY, "mm")

    # the cabinet carcass, the tray, cut-outs
    for s0, s1 in C["sides"] + [part]:
        rect(E(s0, z0), E(s1, z1), fill=WOOD, outline=DOOR)
    rect(E(C["sides"][0][0], z0), E(C["sides"][1][1], z0 + bd), fill=WOOD, outline=DOOR)
    rect(E(C["sides"][0][0], z1 - bd), E(C["sides"][1][1], z1), fill=WOOD, outline=DOOR)
    ts0, ts1 = C["tray"]["s"]
    rect(E(ts0, z0 + bd), E(ts1, z0 + bd + C["tray"]["border"]), fill=(235, 240, 245), outline=PIPE["cold"])
    tag(E(ts0 + 2, z0 + bd + C["tray"]["border"] + 1.5), f"поддон, борт {num(C['tray']['border'])}", PIPE["cold"], "lb")
    rc = C["riser_cutout"]
    for z in (z0, z1 - bd):
        dashed_rect(E(rc["s"][0], z - 0.8), E(rc["s"][1], z + bd + 0.8), RED, dash=5)
    tag(E(rc["s"][1] + 1, z1 - 6), "вырез под стояк", RED, "lm")
    cn = C["cord_notch"]
    dashed_rect(E(part[0] - 0.6, cn["z"][0]), E(part[1] + 0.6, cn["z"][1]), RED, dash=4)
    # door joints and hinges
    for door in C["doors"]:
        s0, s1 = door["s"]
        hs = s0 + 1.2 if door["hinge"] == "left" else s1 - 1.2
        for z in (z0 + 12, (z0 + z1) / 2, z1 - 12):
            x, y = E(hs, z)
            d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=DOOR, width=2)
        for s in (s0, s1):
            dashed(E(s, z0), E(s, z1), DOOR, dash=10, width=1)
    for i, door in enumerate(C["doors"]):
        d.text(E(sum(door["s"]) / 2, CEIL + 8.5), f"дверь {i + 1}", fill=DOOR, font=f_s, anchor="mb")
        d.text(E(sum(door["s"]) / 2, CEIL + 4.5), f"петли {door['on']}", fill=DOOR, font=f_xs, anchor="mb")

    # the heater: body, brackets behind (dashed), hooks, stubs, panel
    d.rounded_rectangle([*E(bs0, bz1), *E(bs1, bz0)], radius=(bz1 - bz0) / 2 * SC * 0.35, fill=BODY, outline=INK,
                        width=3)
    for hs, hz in hooks:
        w = B["brackets"]["width"] / 2
        dashed_rect(E(hs - w, bz0 + 6), E(hs + w, bz1 - 6), GREY, dash=6)
        for z in (hz, hz - B["brackets"]["windows"]):
            x, y = E(hs, z)
            d.rectangle([x - 5, y - 5, x + 5, y + 5], outline=GREY, width=2)
        x, y = E(hs, hz)
        d.line([x - 9, y - 9, x + 9, y + 9], fill=RED, width=3)
        d.line([x - 9, y + 9, x + 9, y - 9], fill=RED, width=3)
        tag(E(hs + 2.5, hz + 1.5), "крюк", RED, "lb")
    dashed(E(bs0 - 3, axis), E(bs1 + 3, axis), GREY, dash=5, width=1)
    d.text(E((bs0 + bs1) / 2, axis - 2.5), B["short"], fill=INK, font=f_s, anchor="mt")
    d.text(E((bs0 + bs1) / 2, axis - 7), f"ось {num(axis)} · патрубки и крюки ±{num(B['tolerance'])} до примерки",
           fill=GREY, font=f_xs, anchor="mt")
    for name, s in stub_s.items():
        rect(E(s - 0.9, bz0), E(s + 0.9, z_stub), fill=METAL, outline=INK)

    # fittings, pipes, the funnel, the outlet
    for fit in UP["fittings"]:
        s, zz = stub_s[fit["stub"]], z_stub
        for kind, h in fit["items"]:
            if kind == "клапан":
                rect(E(s - 1.6, zz), E(s + 1.6, zz - h), fill=VALVE, outline=INK)
                rect(E(s + 1.6, zz - 2.5), E(s + 4.2, zz - 4.5), fill=VALVE, outline=INK)
            else:
                rect(E(s - 1.4, zz), E(s + 1.4, zz - h), fill=METAL, outline=INK)
                x, y = E(s, zz - h / 2)
                d.line([x - 9, y, x + 9, y], fill=RED, width=4)            # butterfly handle
            zz -= h
    tag(E(stub_s["холодная"] + 5, z_stub - 9), "клапан", INK, "lm")
    for pipe in UP["pipes"]:
        pts = [E(s, z) for s, z in pipe["path"]]
        color = PIPE[pipe["color"]]
        if pipe.get("dashed"):
            for a, b in zip(pts, pts[1:]):
                dashed(a, b, color, dash=6, width=2)
        else:
            d.line(pts, fill=color, width=4, joint="curve")
    fn = UP["funnel"]
    x0, y0 = E(fn["s"] - fn["w"] / 2, fn["z"][1])
    x1, y1 = E(fn["s"] + fn["w"] / 2, fn["z"][0])
    d.polygon([(x0, y0), (x1, y0), ((x0 + x1) / 2 + 6, y1), ((x0 + x1) / 2 - 6, y1)], fill="white",
              outline=PIPE["drain"], width=3)
    labels = [("горячая", 80, 100, "hot"), ("холодная", 88, 92, "cold"), ("дренаж Ø32", 95, 84, "drain")]
    for text, s, z, c in labels:
        tag(E(s + 1.2, z), text, PIPE[c], "lm")
    tag(E(fn["s"] - fn["w"] / 2 - 1, fn["z"][1] + 2.5), "воронка, разрыв струи", PIPE["drain"], "rb")
    tag(E(stub_s["слив"] - 2, 185), "шланг слива", GREY, "rm")
    tag(E(72, 152), "дренаж клапана", PIPE["drain"], "lm")
    for o in UP["outlets"]:
        x, y = E(o["s"], o["z"])
        d.ellipse([x - 3.4 * SC, y - 3.4 * SC, x + 3.4 * SC, y + 3.4 * SC], fill="white", outline=RED, width=3)
        tag(E(o["s"], o["z"] - 4.5), o["name"], RED, "mt")
    dashed(E(bs1 - 10, bz0 - 1), E(part[0], cn["z"][0] + 6), RED, dash=4)
    dashed(E(part[1], cn["z"][0] + 6), E(UP["outlets"][0]["s"] - 3.4, UP["outlets"][0]["z"]), RED, dash=4)
    tag(E(part[1] + 1, cn["z"][0] - 2), "шнур — вырез 7×12", RED, "lt")

    # chains under the elevation and heights on the right
    y = E(0, -4)[1] + 40
    chain_h([TL, bs0, bs1, part[0], part[1], C["sides"][1][0], L - TL], y, E, False, "от плитки:")
    y += 64
    chain_h([bs0, *stub_s.values(), bs1], y, E, False, "патрубки:")
    y += 56
    chain_h([bs0, *[h[0] for h in hooks], bs1], y, E, False, "крюки:")
    y += 56
    chain_h([0, 80, 88, fn["s"], *riser["s"], UP["outlets"][0]["s"], L], y, E, False, "трубы, стояк, розетка:")
    chain_v([0, 32, 120, z0 + bd, 126, 133, UP["outlets"][0]["z"], z_stub, bz0, hooks[0][1], bz1, z1 - bd, z1,
             CEIL], E(L + 6, 0)[0] + 40, E)
    el_bottom = y + 40

    # ---------------------------------------------------------------- section through the cold stub
    d.text((sx0 - 60, ey0 - 140), f"Разрез по холодному патрубку (s {num(stub_s['холодная'])}), вид справа: стена "
                                  "слева, комната справа", fill=INK, font=f_m)
    rect(S(-8, z_cut), S(0, CEIL + 3), fill=WALL)
    d.text(S(-8, z_cut - 9), "дальняя стена (тип — пробным сверлением)", fill=GREY, font=f_xs, anchor="lt")
    dashed(S(-8, CEIL), S(36, CEIL), GREY)
    rect(S(0, 117.5), S(F, 120), fill=GKL, outline=(200, 170, 120))
    rect(S(F - 2.7, z_cut), S(F, 117.5), fill=PROF["ПП"], outline=INK)
    rect(S(F, z_cut), S(F + 2.5, 120), fill=GKL, outline=(200, 170, 120))
    rect(S(F + 2.5, z_cut), S(F + 2.5 + TL, 120), fill=TILE, outline=GREY)
    rect(S(0, 114.7), S(2.7, 117.5), fill=PROF["ПН"], outline=INK)
    face = C["face"]
    back_door = face - C["door"]
    rect(S(0, z0), S(back_door, z0 + bd), fill=WOOD, outline=DOOR)
    rect(S(0, z1 - bd), S(back_door, z1), fill=WOOD, outline=DOOR)
    rect(S(0.5, z0 + bd), S(back_door - 0.5, z0 + bd + C["tray"]["border"]), outline=PIPE["cold"], width=2)
    rect(S(back_door, z0), S(face, z1), fill=DOOR)
    d.text(S(face + 1.5, (z0 + z1) / 2), f"дверь МДФ {num(C['door'])}", fill=DOOR, font=f_xs, anchor="lm")
    bx0 = B["depth"] - B["body_depth"]
    rect(S(0, bz0 + 5), S(bx0, bz1 - 5), fill=METAL, outline=INK)
    d.rounded_rectangle([*S(bx0, bz1), *S(B["depth"], bz0)], radius=(B["body_depth"] / 2) * SC2 * 0.9, fill=BODY,
                        outline=INK, width=3)
    hx, hy = S(0, hooks[0][1])
    d.line([hx - 8 * SC2, hy, hx + 1.2 * SC2, hy], fill=RED, width=4)
    d.line([hx + 1.2 * SC2, hy, hx + 1.2 * SC2, hy - 1.4 * SC2], fill=RED, width=4)
    tag(S(-7.5, hooks[0][1] + 2), "анкер + крюк", RED, "lb")
    sd = B["stub_d"]
    rect(S(sd - 0.9, bz0), S(sd + 0.9, z_stub), fill=METAL, outline=INK)
    rect(S(sd - 1.6, z_stub), S(sd + 1.6, z_stub - 8.5), fill=VALVE, outline=INK)
    rect(S(sd - 1.4, z_stub - 8.5), S(sd + 1.4, z_stub - 15.5), fill=METAL, outline=INK)
    cold = next(p for p in UP["pipes"] if p["name"] == "холодная")
    zc = cold["path"][1][1]
    d.line([S(sd, z_stub - 15.5), S(sd, z_stub - 18.5), S(cold["d"], z_stub - 18.5), S(cold["d"], zc)],
           fill=PIPE["cold"], width=5, joint="curve")
    x, y = S(cold["d"], zc)
    d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=PIPE["cold"], width=3)
    tag(S(cold["d"] + 2, zc + 3), f"вправо на z {num(zc)}, к s 88", PIPE["cold"], "lb")
    tag(S(sd + 2.2, z_stub - 4), "клапан, кран", INK, "lm")
    d.text(S(bx0 + B["body_depth"] / 2, axis), "бойлер", fill=INK, font=f_s, anchor="mm")
    chain_h([0, bx0, B["depth"], back_door, face], S(0, CEIL + 3)[1] - 40, S)
    chain_h([0, F, F + 2.5, F + 2.5 + TL], S(0, z_cut)[1] + 40, S, above=False)
    gap = back_door - B["depth"]
    tag(S(B["depth"] + gap / 2, bz1 + 2.5), f"зазор {num(round(gap, 1))}", RED, "mb")
    chain_v([z_cut, 117.5, 120, z0 + bd, zc, z_stub, bz0, hooks[0][1], bz1, z1 - bd, z1], S(face, 0)[0] + 150, S)

    # ---------------------------------------------------------------- notes from the data, three columns
    ty0 = max(el_bottom + 30, S(0, z_cut)[1] + 120)
    fmt = {k: (v if isinstance(v, str) else num(v)) for k, v in B.items() if isinstance(v, (str, int, float))}
    cols = UP["notes"]
    cw = (W - ex0 - 80) // len(cols)
    ends = []
    for i, col in enumerate(cols):
        tx, ty = ex0 + i * (cw + 30), ty0
        d.text((tx, ty), col["title"], fill=INK, font=f_m)
        ty += 32
        for note in col["items"]:
            line = "—"
            for w in note.format(**fmt).split():
                if d.textlength(line + " " + w, font=f_s) > cw - 20:
                    d.text((tx, ty), line, fill=INK, font=f_s)
                    ty += 23
                    line = "  "
                line += " " + w
            d.text((tx, ty), line, fill=INK, font=f_s)
            ty += 31
        ends.append(ty)
    ty = max(ends) + 10
    d.text((ex0, ty), "Открытые вопросы", fill=RED, font=f_m)
    ty += 32
    for q in (q for q in PLAN["open_questions"] if q.startswith("туалет")):
        line = "—"
        for w in q.split():
            if d.textlength(line + " " + w, font=f_s) > W - ex0 - 80:
                d.text((ex0, ty), line, fill=INK, font=f_s)
                ty += 23
                line = "  "
            line += " " + w
        d.text((ex0, ty), line, fill=INK, font=f_s)
        ty += 31

    out.mkdir(parents=True, exist_ok=True)
    img = img.crop((0, 0, W, ty + 30))
    img.save(out / "boiler_toilet.png")
    print(out / "boiler_toilet.png")


if __name__ == "__main__":
    main()
