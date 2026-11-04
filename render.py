"""Build a room from a JSON config and render it with Cycles.

    .venv/bin/python render.py rooms/apartment.json            # review quality, all cameras
    .venv/bin/python render.py rooms/apartment.json --preview  # quick low-res draft
    .venv/bin/python render.py rooms/apartment.json --hd       # 1920 wide, clean noise, *_hd.png
    .venv/bin/python render.py rooms/apartment.json --final    # full resolution, *_final.png
"""

import argparse
import fcntl
import time
from pathlib import Path

import bpy

from roomgen import config, scene as scene_builder


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("config", help="room config, e.g. rooms/apartment.json")
    quality = ap.add_mutually_exclusive_group()
    quality.add_argument("--preview", action="store_true", help="fast low-resolution draft")
    quality.add_argument("--hd", action="store_true", help="1920 px wide, final samples and noise threshold, *_hd.png")
    quality.add_argument("--final", action="store_true", help="full resolution and samples")
    ap.add_argument("--camera", action="append", help="render only this camera (repeatable)")
    ap.add_argument("--samples", type=int, help="override sample count")
    ap.add_argument("--cpu", action="store_true",
                    help="render on the CPU: slower, but runs alongside a GPU render instead of waiting for it")
    ap.add_argument("--out", default="renders", help="output directory (default: renders)")
    ap.add_argument("--no-render", action="store_true", help="only build the scene and save the .blend")
    ap.add_argument("--variant", help="apply a named variant from the config; files get a _<variant> suffix")
    ap.add_argument("--light", help="lighting scenario from the config's lighting.scenarios (switch groups on, "
                                    "daylight); renders its cameras unless --camera is given; files get a _<name> suffix")
    ap.add_argument("--eye", action="store_true",
                    help="human-eye views: room cameras get render.eye lens and eye height; files go to eye/<folder>/")
    ap.add_argument("--clay", action=argparse.BooleanOptionalAction, default=None,
                    help="uniform grey materials to check geometry (default: render.clay from the config)")
    args = ap.parse_args()

    cfg = config.load(args.config, args.variant)
    rcfg = cfg["render"]
    eye = rcfg.get("eye") or {}
    if args.eye:  # same viewpoints, but a natural field of view at eye height instead of an ultra-wide lens
        for c in cfg["cameras"]:
            if c.get("type") not in ("ortho", "pano", "cube") and c["name"] not in eye.get("skip", []):
                c["lens"] = eye["lens"]
                c["position"] = [*c["position"][:2], c["eye_height"] or eye["height"]]
    clay = rcfg["clay"] if args.clay is None else args.clay
    scene, cameras = scene_builder.build(cfg, clay)
    mode = "preview" if args.preview else "hd" if args.hd else "final" if args.final else "review"
    # One Cycles process on the GPU at a time (two crash it), and that includes setting up the device: a second
    # process, e.g. from another session, waits here before touching the GPU.
    if not args.cpu and not args.no_render:  # the CPU does not share the GPU, so it needs no turn
        lock = open(Path(__file__).resolve().parent / ".render.lock", "w")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("another render is running, waiting for the GPU...", flush=True)
            fcntl.flock(lock, fcntl.LOCK_EX)
    device = scene_builder.configure_render(scene, rcfg, mode, args.samples, cpu=args.cpu)
    scenario = {}
    if args.light:
        scenario = cfg["lighting"]["scenarios"][args.light]
        scene_builder.apply_lighting(scene, scenario)
    elif cfg.get("lighting", {}).get("default_off"):  # the default render: everything on except these groups
        scene_builder.apply_lighting(scene, {"off": cfg["lighting"]["default_off"]})
    if not args.light:  # the default render is an evening one: lamps at real brightness, exposure lifted
        scenario = {"exposure": cfg.get("lighting", {}).get("default_exposure", 0.0)}

    out_dir = (Path(args.out) / cfg["name"]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if cfg["render"]["save_blend"] or args.no_render:
        blend = out_dir / f"{cfg['name']}.blend"
        bpy.context.preferences.filepaths.save_version = 0  # no .blend1 backups
        bpy.ops.wm.save_as_mainfile(filepath=str(blend))
        print(f"scene saved: {blend}")
    if args.no_render:
        return

    wanted = set(args.camera or scenario.get("cameras", []))
    if args.eye:
        wanted = {c["name"] for c in cfg["cameras"] if c.get("type") not in ("ortho", "pano", "cube")
                  and c["name"] not in eye.get("skip", [])
                  and (not wanted or c["name"] in wanted)}
        out_dir = out_dir / "eye"
    # One folder per variant / lighting scenario ("all" = default, every lamp on); dollhouse views in "overview".
    folder = "_".join(x for x in (args.variant, args.light) if x) or "all"
    suffix = ("_clay" if clay else "") + {"preview": "_preview", "review": "", "hd": "_hd", "final": "_final"}[mode]
    for cam_obj in cameras:
        name = cam_obj.data.name
        if wanted and name not in wanted and cam_obj.get("group") not in wanted:  # a cube face: its panorama's name
            continue
        scene.camera = cam_obj
        scene_builder.stage(scene, rcfg, bool(cam_obj.get("dollhouse")))
        res = cam_obj.get("resolution") or rcfg["resolution"]
        scene.render.resolution_x, scene.render.resolution_y = int(res[0]), int(res[1])
        scene.view_settings.exposure = cam_obj.get("exposure", rcfg["exposure"]) + scenario.get("exposure", 0.0)
        if scenario.get("white_balance") and scene.view_settings.use_white_balance:
            scene.view_settings.white_balance_temperature = scenario["white_balance"]
        sub = ("overview" if folder == "all" else f"overview_{folder}") if cam_obj.get("dollhouse") else folder
        (out_dir / sub).mkdir(parents=True, exist_ok=True)
        scene.render.filepath = str(out_dir / sub / f"{name}{suffix}.png")
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f"rendered {name} on {device} in {time.time() - t0:.1f}s -> {scene.render.filepath}")


if __name__ == "__main__":
    main()
