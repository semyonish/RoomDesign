"""Render a tour panorama with each light switch group as its own denoised layer, for switches in the tour.

    .venv/bin/python tour/switch_render.py br1_360 --groups br1_spots_1 br1_spots_2 sconces --day br1_day
    .venv/bin/python tour/switch_render.py lr_360 --groups chandelier ambient=cornice+kitchen_led --day day

Light adds up, so one render gives every on/off combination: tour/build.py sums the layers per combination.
Writes renders/apartment/switch/<cam>/<cam>_<face>_<group>.exr, scene-linear. --day adds a "day" layer: the
sky (with that scenario's sky strength) and the sun through the windows. Lamps outside --groups are left out.
A layer `name=g1+g2` puts several switch groups on one key. --open swings those doors (by id) open 90°; --rest
adds a "rest" layer with every other lamp of the flat (but the ones off by default), the neighbouring rooms seen
through an arch or an open door.
"""

import argparse
import fcntl
import sys
import time
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from roomgen import config, scene as scene_builder  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("camera", help="a cube camera of the config, e.g. br1_360")
ap.add_argument("--groups", nargs="+", required=True, help="switch groups (light_group of the lamps), or name=g1+g2")
ap.add_argument("--day", help="lighting scenario for the day layer, e.g. br1_day")
ap.add_argument("--config", default=str(ROOT / "rooms/apartment.json"))
ap.add_argument("--mode", default="hd", choices=["preview", "review", "hd"])
ap.add_argument("--samples", type=int, help="override the mode's samples")
ap.add_argument("--threshold", type=float, help="override the mode's adaptive noise threshold")
ap.add_argument("--open", nargs="*", default=[], help="door ids to render open 90°")
ap.add_argument("--rest", action="store_true", help="a layer for the other rooms' lamps")
args = ap.parse_args()

cfg = config.load(args.config)
for door in cfg["doors"]:
    if door.get("id") in args.open:
        door["open"] = 90
rcfg = cfg["render"]
scene, cameras = scene_builder.build(cfg, False)
lock = open(ROOT / ".render.lock", "w")  # one Cycles process on the GPU at a time (see render.py)
fcntl.flock(lock, fcntl.LOCK_EX)
device = scene_builder.configure_render(scene, rcfg, args.mode, args.samples)
if args.threshold:
    scene.cycles.adaptive_threshold = args.threshold

members = {}  # layer → the switch groups it carries
for spec in args.groups:
    name, _, groups = spec.partition("=")
    members[name] = set(groups.split("+")) if groups else {name}
layer_of = {g: name for name, groups in members.items() for g in groups}
layers = list(members)
if args.rest:  # everything else that is on by default
    off = set(cfg["lighting"].get("default_off", []))
    for obj in bpy.data.objects:
        g = obj.get("light_group")
        if g and g not in layer_of and g not in off:
            layer_of[g] = "rest"
    layers.append("rest")
if args.day:
    day = cfg["lighting"]["scenarios"][args.day]
    scene["daylight"] = True
    if day.get("sky_strength"):
        bpy.data.worlds["Day"].node_tree.nodes["Background"].inputs["Strength"].default_value = day["sky_strength"]
    layers.append("day")
view_layer = scene.view_layers[0]
for name in layers:
    view_layer.lightgroups.add(name=name)
for obj in bpy.data.objects:  # lamps and their glowing surfaces
    if obj.get("light_group") in layer_of:
        obj.lightgroup = layer_of[obj["light_group"]]
if args.day:
    for name in ("Daylight", "Portals"):
        col = bpy.data.collections.get(name)
        for obj in col.all_objects if col else []:
            obj.lightgroup = "day"
view_layer.cycles.denoising_store_passes = True

# Compositor: each layer through the denoiser (with albedo and normals), saved as its own linear EXR.
tree = bpy.data.node_groups.new("Switch Layers", "CompositorNodeTree")
scene.compositing_node_group = tree
scene.render.use_compositing = True
rl = tree.nodes.new("CompositorNodeRLayers")
out = tree.nodes.new("CompositorNodeOutputFile")
out.format.media_type = "IMAGE"
out.format.file_format = "OPEN_EXR"
out.format.color_depth = "32"
out.save_as_render = False  # raw scene-linear light: the view transform is applied once, after adding the layers up
for name in layers:
    dn = tree.nodes.new("CompositorNodeDenoise")
    tree.links.new(rl.outputs[f"Combined_{name}"], dn.inputs["Image"])
    tree.links.new(rl.outputs["Denoising Albedo"], dn.inputs["Albedo"])
    tree.links.new(rl.outputs["Denoising Normal"], dn.inputs["Normal"])
    out.file_output_items.new("RGBA", name)
    tree.links.new(dn.outputs["Image"], out.inputs[name])

folder = ROOT / "renders" / cfg["name"] / "switch" / args.camera
folder.mkdir(parents=True, exist_ok=True)
out.directory = str(folder)
faces = [c for c in cameras if c.get("group") == args.camera]
if not faces:
    sys.exit(f"{args.camera}: no cube camera of that name")
for cam_obj in faces:
    name = cam_obj.data.name
    scene.camera = cam_obj
    scene_builder.stage(scene, rcfg, False)
    if args.day:
        scene.world.lightgroup = "day"
    res = cam_obj.get("resolution") or rcfg["resolution"]
    scene.render.resolution_x, scene.render.resolution_y = int(res[0]), int(res[1])
    out.file_name = f"{name}_"
    t0 = time.time()
    bpy.ops.render.render(write_still=False)
    print(f"rendered {name} layers {', '.join(layers)} on {device} in {time.time() - t0:.1f}s -> {folder}", flush=True)
