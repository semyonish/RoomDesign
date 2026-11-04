"""Leak sensors in the wet rooms: a separate sheet, kept off the final plans.
Draws the bathroom and the toilet (furniture from plans.py) with plan.json → leak_protection on top:
sensors, the motorised valves, the controller and the access hatches.

    .venv/bin/python leaks.py    # → renders/Рендеры/Датчики протечки/Санузлы.png
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import plans

SENSOR, OPTIONAL, VALVE, HATCH = (30, 120, 220), (140, 180, 230), (200, 40, 40), (230, 140, 20)
# furniture labels moved off the markers on this sheet only
LABEL_AT = {"короб + шкаф над ним": (-66, 539), "тумба": (18, 486), "тумба с раковиной": (205, 452),
            "смеситель": (196, 495), "стирка + сушка": (16, 422)}


def sensor(d, x, y, s, font):   # on the floor: a filled dot; on a shelf: a ring; optional: pale
    if s.get("z"):
        d.ellipse([x - 15, y - 15, x + 15, y + 15], outline=SENSOR, width=3, fill="white")
        d.text((x, y), s["id"], fill=SENSOR, font=font, anchor="mm")
    else:
        d.ellipse([x - 15, y - 15, x + 15, y + 15], fill=OPTIONAL if s.get("optional") else SENSOR)
        d.text((x, y), s["id"], fill="white", font=font, anchor="mm")


def valve(d, x, y):
    d.ellipse([x - 13, y - 13, x + 13, y + 13], outline=VALVE, width=3, fill="white")
    d.line([x - 9, y - 9, x + 9, y + 9], fill=VALVE, width=3)
    d.line([x - 9, y + 9, x + 9, y - 9], fill=VALVE, width=3)


def controller(d, x, y, font):
    d.rectangle([x - 13, y - 13, x + 13, y + 13], fill=VALVE)
    d.text((x, y), "К", fill="white", font=font, anchor="mm")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--plan", default="plan.json")
    ap.add_argument("--out", default="renders/Рендеры/Датчики протечки/Санузлы.png")
    args = ap.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    lp = plan["leak_protection"]
    m = plans.Model(json.loads(Path(args.config).read_text()), plan)
    m.furniture = [(lb, size, poly, LABEL_AT.get(lb, at)) for lb, size, poly, at in m.furniture]
    polys = [poly for rid, _, poly in m.rooms if rid in ("bathroom", "toilet")]
    x0, x1 = min(p[0] for q in polys for p in q) - 25, max(p[0] for q in polys for p in q) + 25
    y0, y1 = min(p[1] for q in polys for p in q) - 25, max(p[1] for q in polys for p in q) + 25
    scale, margin = 3.0, 140   # as plans.sheet draws a furniture sheet: margin, 120 below for the title band
    plan_img = plans.sheet(m, (x0, x1, y0, y1), scale, "Датчики протечки — ванная и туалет", "furniture")
    W, H = plan_img.size

    def P(x, y):
        return (margin + (x - x0) * scale, H - margin - 120 - (y - y0) * scale)

    f_s, f_m = ImageFont.truetype(plans.FONT, 17), ImageFont.truetype(plans.FONT, 20)
    f_b = ImageFont.truetype(plans.BOLD, 20)
    top = P(x0, y0)[1] + 10   # the legend under the rooms, past the strip of the hall
    img = Image.new("RGB", (W, H + 1500), "white")
    img.paste(plan_img.crop((0, 0, W, int(top))), (0, 0))
    d = ImageDraw.Draw(img)

    for h in lp["hatches"]:   # a thick band on the tiled face
        a, b = P(h["x_from"], h["wall_y"]), P(h["x_to"], h["wall_y"])
        d.rectangle([a[0], a[1] - 5, b[0], b[1] + 5], fill=HATCH)
        d.text(((a[0] + b[0]) / 2, a[1] + 9), "люк", fill=HATCH, font=f_s, anchor="mt")
    v, c = lp["valves"], lp["controller"]
    valve(d, *P(v["x"], v["y"]))
    controller(d, *P(c["x"], c["y"]), f_b)
    for s in lp["sensors"]:
        sensor(d, *P(s["x"], s["y"]), s, f_s)

    def wrapped(x, y, text, col, font, step):
        lines = [""]
        for word in text.split(" "):   # wrapped to the sheet width
            if lines[-1] and d.textlength(f"{lines[-1]} {word}", font=font) > W - margin - x:
                lines.append(word)
            else:
                lines[-1] = f"{lines[-1]} {word}".strip()
        for line in lines:
            d.text((x, y), line, fill=col, font=font)
            y += step
        return y

    y = top
    y = wrapped(margin, y, "синий кружок — датчик на полу; кольцо — датчик выше пола (на полке); бледный — по желанию. "
                "Расстояния — до центра датчика от чистовой стены (плитки), см", plans.LABEL, f_s, 24) + 12
    for rid, name in (("bathroom", "Ванная"), ("toilet", "Туалет")):
        d.text((margin, y), name, fill=(20, 20, 20), font=f_b)
        y += 34
        for s in (s for s in lp["sensors"] if s["room"] == rid):
            sensor(d, margin + 15, y + 12, s, f_s)
            tag = (f", на {s['z']}" if s.get("z") else "") + (" — по желанию" if s.get("optional") else "")
            y = wrapped(margin + 45, y, f"{s['value']}{tag}", SENSOR, f_m, 26)
            y = wrapped(margin + 45, y, s["why"], plans.LABEL, f_s, 22) + 14
        y += 6
    for icon, col, text in (("valve", VALVE, v["value"]), ("controller", VALVE, c["value"])) + tuple(
            ("hatch", HATCH, h["value"]) for h in lp["hatches"]):
        if icon == "valve":
            valve(d, margin + 15, y + 12)
        elif icon == "controller":
            controller(d, margin + 15, y + 12, f_b)
        else:
            d.rectangle([margin, y + 7, margin + 30, y + 17], fill=HATCH)
        y = wrapped(margin + 45, y, text, col, f_m, 26) + 12
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.crop((0, 0, W, int(y) + 30)).save(out)
    print(out)


if __name__ == "__main__":
    main()
