"""Readable copy of the renders: renders/Рендеры/<Комната>/<NN Сценарий>/<вид (камера)> — глаз|широкий.jpg,
each frame captioned in the corner with room, scenario and view; plans go to renders/Рендеры/Планы/,
the lighting plans with wall sizes also to renders/Рендеры/Освещение/, the floor tile layouts to renders/Рендеры/Плитка/.

    .venv/bin/python export.py                          # everything that is rendered
    .venv/bin/python export.py --since "2026-10-21 23:30"   # only frames rendered after that time

The technical folders (renders/apartment/eye/all/…) stay as they are; frames already exported
and not re-rendered since are skipped; a --hd frame (<cam>_hd.png) is used when it is newer than the review one.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC, OUT, PLANS = Path("renders/apartment"), Path("renders/Рендеры"), Path("renders/plan")
FONT = "/System/Library/Fonts/Supplemental/Arial.ttf"  # has Cyrillic
BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

ROOMS = {"hall": "Прихожая", "kitchen_living": "Кухня-гостиная", "bedroom_1": "Спальня 1",
         "bedroom_2": "Спальня 2", "study": "Кабинет", "bathroom": "Ванная", "toilet": "Туалет", "overview": "Общий вид",
         "loggia_kitchen": "Лоджия кухни-гостиной", "loggia_bedroom_1": "Лоджия спальни 1"}
WALLS = {"entrance": "Прихожая, стена с зеркалом"}  # elevation.py sheets by wall id
TITLES = {  # lighting scenario (render folder) → folder title
    "all": "Весь свет", "day": "День", "chandelier": "Вечер — только люстра", "spots": "Вечер — все точечные",
    "ambient": "Вечер — подсветка карниза и кухни", "kitchen_spots": "Клавиша — кухонная линия точечных",
    "sofa_spots": "Клавиша — точечные у дивана", "tv_spots": "Клавиша — точечные у ТВ",
    "cornice": "Клавиша — подсветка карниза", "kitchen_led": "Клавиша — подсветка кухни",
    "hall_1": "Клавиша 1 — 2 пары вдоль шкафа-купе", "hall_2": "Клавиша 2 — остальные 4 пары",
    "br1_day": "День", "br1_spots_1": "Клавиша 1 — 4 крайние лампы",
    "br1_spots_2": "Клавиша 2 — остальные 8 ламп", "br1_sconces": "Вечер — только бра",
    "st_day": "День", "st_spots_1": "Клавиша 1 — 2 над столом и 1 у шкафа", "st_spots_2": "Клавиша 2 — остальные 6 ламп",
    "bath_evening": "Вечер — весь свет", "toilet_evening": "Вечер — свет и подсветка зеркала",
    "overview": "Сверху и аксонометрия",
}
# Scenarios of each room in folder order; "Весь свет" already is the evening with every lamp on.
ROOM_SCENARIOS = {
    "hall": ["all", "hall_1", "hall_2"],
    "kitchen_living": ["all", "day", "chandelier", "spots", "ambient", "kitchen_spots", "sofa_spots", "tv_spots",
                       "cornice", "kitchen_led"],
    "bedroom_1": ["all", "br1_day", "br1_spots_1", "br1_spots_2", "br1_sconces"],
    "study": ["all", "st_day", "st_spots_1", "st_spots_2"],
    "bedroom_2": ["all"],
    "bathroom": ["all", "bath_evening"],
    "toilet": ["all", "toilet_evening"],
    "overview": ["overview"],
}
VIEWS = {  # cameras without a usable "_" in the config
    "axo": "Аксонометрия", "plan": "Вид сверху",
    "hall_c1": "Угол у входа → санузлы и спальни", "hall_c2": "Угол у санузла и спальни 1 → арка",
    "hall_c3": "Угол у спальни 2 → входная дверь", "hall_c4": "От арки → санузел и спальня 1",
    "entrance": "Входная дверь", "arch": "Из прихожей через арку → гостиная",
    "wiring": "Выключатели и розетки у входа", "kitchen": "Кухня из гостиной",
    "living": "От окна → кухня и арка", "kitchen_window": "Середина кухни → окно",
}


def room_of(cam):
    if cam in ("axo", "plan"):
        return "overview"
    if cam.startswith(("hall_", "entrance", "arch", "wiring")):
        return "hall"
    if cam.startswith(("br1_", "br2_")):
        return "bedroom_" + cam[2]
    if cam.startswith("st_"):
        return "study"
    if cam.startswith("bath_"):
        return "bathroom"
    if cam.startswith("toilet_"):
        return "toilet"
    return "kitchen_living"


def view_names(cfg):
    """Camera → (view name, eye height in cm for the human-eye render)."""
    names = {}
    eye = cfg.get("render", {}).get("eye", {}).get("height", 160)
    for c in cfg["cameras"]:
        if c.get("type") in ("pano", "cube"):
            continue  # 360° panoramas go to the tour, uncaptioned
        note = c.get("_", "").split(": ", 1)[-1].replace(" / ", " и ").replace("/", " и ")
        names[c["name"]] = (VIEWS.get(c["name"]) or (note[:1].upper() + note[1:] if note else c["name"]),
                            c.get("eye_height") or eye)
    return names


def caption(src, dst, title, sub):
    im = Image.open(src).convert("RGB")
    s = im.width / 1800
    f1, f2 = ImageFont.truetype(BOLD, round(32 * s)), ImageFont.truetype(FONT, round(24 * s))
    pad, gap, margin = round(16 * s), round(8 * s), round(24 * s)
    probe = ImageDraw.Draw(im)
    w = max(probe.textlength(title, font=f1), probe.textlength(sub, font=f2)) + 2 * pad
    h = f1.size + gap + f2.size + 2 * pad
    box = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(box)
    x0, y0 = margin, im.height - margin - h
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], round(10 * s), fill=(20, 20, 20, 150))
    d.text((x0 + pad, y0 + pad), title, fill=(255, 255, 255, 255), font=f1)
    d.text((x0 + pad, y0 + pad + f1.size + gap), sub, fill=(225, 225, 225, 255), font=f2)
    im = Image.alpha_composite(im.convert("RGBA"), box).convert("RGB")
    dst.parent.mkdir(parents=True, exist_ok=True)
    im.save(dst, quality=92)


def export_renders(cfg, since):
    views = view_names(cfg)
    eye_lens = cfg.get("render", {}).get("eye", {}).get("lens", 24)
    done = []
    for room, keys in ROOM_SCENARIOS.items():
        for i, key in enumerate(keys):
            for eye in (True, False):
                src_dir = SRC / "eye" / key if eye else SRC / key
                newest = {}  # camera → its newest frame, review (<cam>.png) or --hd (<cam>_hd.png)
                for src in sorted(src_dir.glob("*.png")) if src_dir.is_dir() else []:
                    cam = src.stem.removesuffix("_hd")
                    if cam not in views or room_of(cam) != room or src.stat().st_mtime < since:
                        continue  # skips *_preview, *_final, old cameras and frames from before `since`
                    if cam not in newest or src.stat().st_mtime > newest[cam].stat().st_mtime:
                        newest[cam] = src
                for cam, src in newest.items():
                    lens = "" if room == "overview" else " — глаз" if eye else " — широкий"
                    view, eye_h = views[cam]
                    dst = OUT / ROOMS[room] / f"{i + 1:02d} {TITLES[key]}" / f"{view} ({cam}){lens}.jpg"
                    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                        continue
                    sub = view + ("" if room == "overview" else
                                  f" · как видит глаз: {eye_lens:g} мм, {eye_h:g} см" if eye else " · широкий объектив")
                    caption(src, dst, f"{ROOMS[room]} · {TITLES[key]}", sub)
                    done.append(dst)
    return done


def export_plans():
    done = []
    for src in sorted(PLANS.glob("*.png")):
        stem = src.stem
        kind = "Обмерный план"
        for prefix, k in (("furniture", "Мебель"), ("lights_edges", "Освещение по краям"), ("lights", "Освещение"),
                          ("tiles", "Плитка"), ("elevation", "Развёртка"), ("frame", "Каркас короба")):
            if stem == prefix or stem.startswith(prefix + "_"):
                kind, stem = k, stem[len(prefix) + 1:]
        full = stem.endswith("_full")
        stem = stem.removesuffix("_full")
        names = WALLS if kind == "Развёртка" else ROOMS
        where = "вся квартира" if stem in ("", "plan") else names.get(stem, stem)
        dst = OUT / "Планы" / f"{kind} — {where}{' на общем плане' if full else ''}.png"
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        done.append(dst)
    return done


LIGHT_SHEETS = ["", "hall", "kitchen_living", "bedroom_1", "study", "bedroom_2", "bathroom", "toilet",
                "loggia_kitchen", "loggia_bedroom_1"]  # added at the end: the numbers of the older sheets stay


def export_lighting(prefix="lights", folder="Освещение"):
    """Lighting plans with wall sizes in a folder of their own: Освещение/00 Вся квартира.png, 01 Прихожая.png, …;
    the same for the floor tile layouts (prefix "tiles") in Плитка/, the sheets for the tilers."""
    done = []
    sheets = [rid for rid in LIGHT_SHEETS if (PLANS / (f"{prefix}_{rid}.png" if rid else f"{prefix}.png")).exists()]
    for i, rid in enumerate(sheets):  # numbered without gaps: only the rooms that have such a sheet
        src = PLANS / (f"{prefix}_{rid}.png" if rid else f"{prefix}.png")
        dst = OUT / folder / f"{i:02d} {ROOMS.get(rid, 'Вся квартира')}.png"
        if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(src.read_bytes())
        done.append(dst)
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default="rooms/apartment.json")
    ap.add_argument("--since", help="only frames rendered after this time, e.g. \"2026-10-21 23:30\"")
    args = ap.parse_args()
    cfg = json.loads(Path(args.config).read_text())
    since = datetime.fromisoformat(args.since).timestamp() if args.since else 0.0
    for p in export_renders(cfg, since) + export_plans() + export_lighting() + export_lighting("lights_edges", "Освещение по краям") + \
            export_lighting("tiles", "Плитка"):
        print(p)


if __name__ == "__main__":
    main()
