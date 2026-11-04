"""Build the 360° tour: the page with every room, point, door and step of tour.json, plus the panoramas as JPEG.

    .venv/bin/python tour/build.py <out dir>                        # page body for the Artifact tool
    .venv/bin/python tour/build.py --site renders/tour_site         # standalone site for S3 or any static hosting
    .venv/bin/python tour/build.py <out> --renders renders/tests/cube_preview/apartment/all --renders renders/apartment/all

Scenes are the rooms' points, cube cameras of rooms/apartment.json; each face is the newest of <cam>_<face>_hd.png, <cam>_<face>.png and
<cam>_<face>_preview.png in the --renders folders, and a scene without all six faces is left out with its doors.
Door arrows show from every point of a room and lead to the other room's point nearest the door; walking through
turns you to face from the door to that point. Steps join a room's points in order and keep the view. Yaw 0 is the
camera's look_at, positive to the right (the points of a room share one look_at direction).

A room with "switches" (tour.json) is built from the light layers of tour/switch_render.py instead: for each of
its points every on/off combination of the keys is added up, with the "rest" layer (the other rooms' lamps) unless
the day is on, and shown through the scene's view transform (the day key with its scenario's exposure and white
balance); the page gets switches on the walls and a light panel.

Without --site <out>/index.html is the page body as the Artifact tool publishes it (no doctype or head of its own).
With --site it is a complete document that loads its own copy of pannellum.js instead of the CDN one.
"""
import argparse
import json
import math
import shutil
import sys
from pathlib import Path

from PIL import Image

CDN = "https://cdnjs.cloudflare.com/ajax/libs/pannellum/2.5.6/pannellum.js"
FACES = "frblud"  # Pannellum's cubemap order: front right back left up down
QUALITY = {"_hd": "HD", "": "рабочее качество", "_preview": "черновик"}
MOBILE_FACE = 1024

here = Path(__file__).resolve().parent
root = here.parent
ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("out")
ap.add_argument("--site", action="store_true", help="complete standalone page with a local pannellum.js")
ap.add_argument("--renders", action="append", help="folder with the face renders (repeatable; default renders/apartment/all)")
args = ap.parse_args()
folders = [Path(f) for f in args.renders or [root / "renders/apartment/all"]]

cams = {c["name"]: c for c in json.loads((root / "rooms/apartment.json").read_text())["cameras"]}
tour = json.loads((here / "tour.json").read_text())


def heading(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


def wrap(deg):
    return round((deg + 180) % 360 - 180, 1)


def point_view(cam, at):
    """Yaw and pitch of a plan point [x, y, z] from a cube camera (yaw 0 = its look_at, positive to the right)."""
    pa = cam["position"]
    return (wrap(heading(pa, cam["look_at"]) - heading(pa, at)),
            round(math.degrees(math.atan2(at[2] - pa[2], math.hypot(at[0] - pa[0], at[1] - pa[1]))), 1))


def save_face(im, jpg):
    """A face as JPEG with a power-of-two side (some phone browsers refuse other cube sizes), plus <name>_m.jpg
    at 1024 for phones: 6 × 2048² textures are ~100 MB, too much for some of them."""
    side = 2 ** int(math.log2(im.width))
    if side != im.width:
        im = im.resize((side, side), Image.LANCZOS)
    im.save(jpg, quality=90, optimize=True, progressive=True)
    im.resize((MOBILE_FACE, MOBILE_FACE), Image.LANCZOS).save(jpg.with_name(jpg.stem + "_m.jpg"), quality=88,
                                                             optimize=True, progressive=True)


def compose(cam, keys, layers, rest, day_scenario):
    """Every on/off combination of the light layers (EXR, scene-linear) as faces <cam>_<face>__<mask>.jpg, where
    the mask has a 1 per key that is on, in key order. Returns the face size."""
    import bpy
    import numpy as np
    sys.path.insert(0, str(root))
    from roomgen import config

    masks = [format(i, f"0{len(keys)}b") for i in range(2 ** len(keys))]
    sources = [q for by_group in layers.values() for q in by_group.values()] + (list(rest.values()) if rest else [])
    newest = max(q.stat().st_mtime for q in sources)
    targets = [out / f"{cam}_{f}__{m}{s}.jpg" for f in FACES for m in masks for s in ("", "_m")]
    if all(t.exists() and t.stat().st_mtime >= newest for t in targets):  # already composed from these layers
        return Image.open(targets[0]).width
    cfg = config.load(root / "rooms/apartment.json")
    rcfg, lighting = cfg["render"], cfg["lighting"]
    day = lighting["scenarios"][day_scenario] if day_scenario else {}
    scene = bpy.context.scene
    vs = scene.view_settings
    vs.view_transform, vs.look, vs.use_white_balance = "AgX", rcfg["look"], True
    scene.render.image_settings.file_format = "PNG"
    tmp = out / "_compose.png"
    for f in FACES:
        px = {}
        for g, path in [*layers[f].items(), *([("rest", rest[f])] if rest else [])]:
            im = bpy.data.images.load(str(path))
            size = tuple(im.size)
            px[g] = np.empty(size[0] * size[1] * 4, np.float32)
            im.pixels.foreach_get(px[g])
            bpy.data.images.remove(im)
        for m in masks:
            on = [g for g, bit in zip(keys, m) if bit == "1"]
            daylight = "day" in on
            if rest and not daylight:  # the other rooms keep their lights on in the evening
                on.append("rest")
            acc = sum((px[g] for g in on), np.zeros_like(px[keys[0]]))
            acc.reshape(-1, 4)[:, 3] = 1.0
            vs.exposure = rcfg["exposure"] + (day.get("exposure", 0.0) if daylight else lighting.get("default_exposure", 0.0))
            vs.white_balance_temperature = (day.get("white_balance") if daylight else None) or rcfg["white_balance"]
            img = bpy.data.images.new("Combination", *size, float_buffer=True)
            img.pixels.foreach_set(acc)
            img.save_render(str(tmp), scene=scene)
            bpy.data.images.remove(img)
            save_face(Image.open(tmp).convert("RGB"), out / f"{cam}_{f}__{m}.jpg")
    tmp.unlink()
    return size[0]


def faces(cam):
    """Face → render, all six from one quality and folder (the viewer shows a cube of mixed sizes black): the set
    finished last wins, so a running HD render does not mix its first faces into the draft. None if no full set."""
    sets = []
    for d in folders:
        for q in QUALITY:
            found = {f: d / f"{cam}_{f}{q}.png" for f in FACES}
            if all(p.exists() for p in found.values()):
                sets.append((min(p.stat().st_mtime for p in found.values()), found))
    return max(sets, key=lambda s: s[0])[1] if sets else None


out = Path(args.out)
out.mkdir(parents=True, exist_ok=True)


def at(point):
    return cams[point["camera"]]["position"]


rooms, scenes, sources = {}, {}, {}
for rid, room in tour["rooms"].items():
    sw = room.get("switches")
    keys = [k["group"].partition("=")[0] for k in sw["keys"]] if sw else []  # "layer=g1+g2": one key, several groups
    default = "".join("1" if g in sw["default"] else "0" for g in keys) if sw else None
    masks = [format(i, f"0{len(keys)}b") for i in range(2 ** len(keys))]
    rooms[rid] = {"title": room["title"], "main": room["main"]}
    if sw:
        rooms[rid]["switches"] = {"keys": [{"label": k["label"], "hint": k.get("hint", "")} for k in sw["keys"]],
                                  "default": default}
    for pt in room["points"]:
        cam = pt["camera"]
        scene = {"room": rid, "doors": [], "steps": []}
        folder = root / "renders/apartment/switch" / cam
        layers = {f: {g: folder / f"{cam}_{f}_{g}.exr" for g in keys} for f in FACES}
        rest = {f: folder / f"{cam}_{f}_rest.exr" for f in FACES}
        if sw and all(q.exists() for by_group in layers.values() for q in by_group.values()):
            side = compose(cam, keys, layers, rest if all(q.exists() for q in rest.values()) else None,
                           next((k.get("scenario") for k in sw["keys"] if k["group"] == "day"), None))
            variants = {m: {"faces": [f"{cam}_{f}__{m}.jpg" for f in FACES],
                            "facesMobile": [f"{cam}_{f}__{m}_m.jpg" for f in FACES]} for m in masks}
            panels = []
            for panel in sw["panels"]:
                x, y, z = panel["at"]
                yaw, pitch = point_view(cams[cam], [x, y, z + tour.get("plate_lift", 0)])  # above the real switch
                panels.append({"yaw": yaw, "pitch": pitch, "keys": [keys.index(g) for g in panel["keys"]]})
            scene.update(variants[default], quality="HD" if side >= 2048 else QUALITY["_preview"], variants=variants,
                         panels=panels)
        else:
            src = faces(cam)
            if src is None:
                print(f"skipped {pt['id']}: {cam} has neither light layers nor a full set of faces")
                continue
            sources[pt["id"]] = (cam, src)
            worst = max((q.stem.removeprefix(f"{cam}_{f}") for f, q in src.items()), key=list(QUALITY).index)
            scene.update(quality=QUALITY[worst], faces=[f"{cam}_{f}.jpg" for f in FACES],
                         facesMobile=[f"{cam}_{f}_m.jpg" for f in FACES])
        scenes[pt["id"]] = scene
    present = [pt for pt in room["points"] if pt["id"] in scenes]
    for a, b in zip(present, present[1:]):  # steps between neighbouring points, both ways
        for p_, q_ in ((a, b), (b, a)):
            yaw, pitch = point_view(cams[p_["camera"]], [*at(q_)[:2], tour.get("step_z", 50)])
            scenes[p_["id"]]["steps"].append({"to": q_["id"], "yaw": yaw, "pitch": pitch})
    if not present:
        del rooms[rid]
    elif rooms[rid]["main"] not in scenes:
        rooms[rid]["main"] = present[0]["id"]


def nearest(rid, xy):
    pts = [pt for pt in tour["rooms"][rid]["points"] if pt["id"] in scenes]
    return min(pts, key=lambda pt: math.hypot(at(pt)[0] - xy[0], at(pt)[1] - xy[1]))


for door in tour["doors"]:  # from every point of a room to the nearest point beyond the door
    for a, b in (door["between"], door["between"][::-1]):
        if a not in rooms or b not in rooms:
            continue
        target = nearest(b, door["at"])
        cb = cams[target["camera"]]
        for pt in (pt for pt in tour["rooms"][a]["points"] if pt["id"] in scenes):
            yaw, pitch = point_view(cams[pt["camera"]], door["at"])
            scenes[pt["id"]]["doors"].append({
                "to": target["id"], "room": b, "yaw": yaw, "pitch": pitch,
                "targetYaw": wrap(heading(cb["position"], cb["look_at"]) - heading(door["at"], cb["position"]))})

first = tour["first"] if tour["first"] in rooms else next(iter(rooms))
data = json.dumps({"first": first, "rooms": rooms, "scenes": scenes}, ensure_ascii=False, indent=1)
page = (here / "template.html").read_text().replace("/*PANNELLUM_CSS*/", (here / "pannellum.css").read_text())
page = page.replace("/*TOUR*/", data)
if args.site:
    head, body = page.split("</style>\n", 1)
    page = ('<!doctype html>\n<html lang="ru">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'{head}</style>\n</head>\n<body>\n{body.replace(CDN, "pannellum.js")}</body>\n</html>\n')
    shutil.copy(here / "pannellum.js", out / "pannellum.js")
(out / "index.html").write_text(page)

for sid, scene in scenes.items():
    cam, src = sources.get(sid, (None, {}))
    for f, png in src.items():
        save_face(Image.open(png).convert("RGB"), out / f"{cam}_{f}.jpg")
    print(f"{sid}: {scene['quality']}, doors to {', '.join(d['to'] for d in scene['doors']) or '—'}, "
          f"steps to {', '.join(st['to'] for st in scene['steps']) or '—'}"
          + (f", {len(scene['variants'])} light combinations" if scene.get("variants") else ""))
