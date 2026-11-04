"""Assemble a scene from a room config and set up Cycles."""

import math

import bpy
from mathutils import Euler, Vector

from . import door, electrical, furniture, kitchen, lights, materials, plan, room

NIGHT_SKY = (0.002, 0.003, 0.007, 1.0)


def _collection(name):
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


def _camera(cfg, collection):
    cam = bpy.data.cameras.new(cfg["name"])
    cam.lens = cfg["lens"]
    cam.sensor_fit = "AUTO"
    cam.sensor_width = 36.0
    cam.clip_start = cfg["clip_start"] or 0.05  # e.g. a camera behind a wall, seeing past it
    cam.clip_end = 200.0
    obj = bpy.data.objects.new(f"Camera {cfg['name']}", cam)
    target = Vector(cfg["look_at"])
    if cfg["type"] == "ortho":
        cam.type = "ORTHO"
        cam.ortho_scale = cfg["ortho_scale"]
    elif cfg["type"] == "pano":
        # 360° equirectangular view for the panorama tour: look_at is the middle of the image, horizon level.
        cam.type = "PANO"
        cam.panorama_type = "EQUIRECTANGULAR"
    if cfg["rotation"] is not None:
        # Aimed by angles: stand back from the target along the view direction.
        rot = Euler([math.radians(a) for a in cfg["rotation"]])
        obj.rotation_euler = rot
        obj.location = target - (rot.to_matrix() @ Vector((0.0, 0.0, -1.0))) * 30.0
    else:
        pos = Vector(cfg["position"])
        obj.location = pos
        delta = target - pos
        if cfg["vertical_correction"] or cam.type == "PANO":
            # Level camera + lens shift: verticals stay vertical, the target stays framed.
            flat = math.hypot(delta.x, delta.y)
            obj.rotation_euler = (math.pi / 2, 0.0, math.atan2(delta.y, delta.x) - math.pi / 2)
            if cam.type != "PANO":
                cam.shift_y = (delta.z / flat) * cam.lens / cam.sensor_width
        else:
            obj.rotation_euler = delta.to_track_quat("-Z", "Y").to_euler()
    obj["dollhouse"] = cfg["dollhouse"]
    if cfg["resolution"]:
        obj["resolution"] = cfg["resolution"]
    if cfg["exposure"] is not None:
        obj["exposure"] = cfg["exposure"]
    collection.objects.link(obj)
    return obj


CUBE_FACES = {  # face: (camera tilt, turn from the look_at direction), in the viewer's order front right back left up down
    "f": (math.pi / 2, 0.0), "r": (math.pi / 2, -math.pi / 2), "b": (math.pi / 2, math.pi),
    "l": (math.pi / 2, math.pi / 2), "u": (math.pi, 0.0), "d": (0.0, 0.0),
}


def _cube_cameras(cfg, collection):
    """Six 90° cameras at one point, the faces of a cube panorama: sharper than one equirectangular image, whose
    size phones cap at 4096 px. Files are <name>_<face>; --camera <name> renders all six."""
    pos, target = Vector(cfg["position"]), Vector(cfg["look_at"])
    yaw = math.atan2(target.y - pos.y, target.x - pos.x) - math.pi / 2
    faces = []
    for face, (tilt, turn) in CUBE_FACES.items():
        obj = _camera({**cfg, "name": f"{cfg['name']}_{face}", "type": "persp", "lens": 18,
                       "vertical_correction": False}, collection)
        obj.rotation_euler = (tilt, 0.0, yaw + turn)
        obj["group"] = cfg["name"]
        faces.append(obj)
    return faces


def _rect_architecture(cfg):
    r = cfg["room"]
    width, depth, height = r["width"], r["depth"], r["height"]
    frames = room.wall_frames(width, depth)
    doors = [door.Door(d, frames[d["wall"]]) for d in cfg["doors"]]
    arches = [room.Arch(o, frames[o["wall"]], height) for o in cfg["openings"]]
    items = [furniture.FURNITURE[f["type"]](f, frames, room.neighbors(f["wall"]), height) for f in cfg["furniture"]]
    openings, gaps = {}, {}
    for hole in doors + arches:
        openings.setdefault(hole.f.name, []).append(hole.opening)
        gaps.setdefault(hole.f.name, []).append(hole.footprint)
    for item in items:
        for wall, spans in item.spans.items():
            gaps.setdefault(wall, []).extend(spans)

    room.build_shell(cfg, frames, openings, arches, _collection("Architecture"))
    joinery = _collection("Doors")
    for dr in doors:
        dr.build(joinery)
    room.build_baseboard(cfg, frames, gaps, joinery)
    if items:
        furn = _collection("Furniture")
        for item in items:
            item.build(furn)
    return width, depth, height


def _plan_architecture(cfg):
    height = cfg["room"]["height"]
    frames = plan.wall_frames([w for ol in plan.outlines(cfg) for w in ol])
    doors = [door.Door(d, frames[d["wall"]]) for d in cfg["doors"]]
    items = [furniture.FURNITURE[f["type"]](f, frames, None, height) for f in cfg["furniture"]]
    blockers = plan.build_shell(cfg, frames, doors, _collection("Architecture"), _collection("Ceiling"),
                                _collection("Cutters"))
    joinery = _collection("Doors")
    for dr in doors:
        dr.build(joinery)
    blockers += [dr.footprint_rect for dr in doors]
    blockers += [dr.far_footprint_rect for dr in doors if dr.far_footprint_rect]
    blockers += [it.footprint_rect for it in items if it.footprint_rect]
    plan.build_baseboard(cfg, blockers, joinery)
    if items:
        furn = _collection("Furniture")
        for item in items:
            item.build(furn)
    if cfg.get("dining_table"):
        furniture.build_dining(cfg["dining_table"], _collection("Furniture"))
    if cfg["kitchen"]:
        cutters = _collection("Kitchen Cutters")
        kitchen.Kitchen(cfg["kitchen"], frames, height, cfg["floor"]).build(_collection("Kitchen"), cutters)
        cutters.hide_render = True
    electrical.build(cfg["electrical"], frames, _collection("Electrical"))
    cfg["_frames"] = frames  # wall lights are placed on walls too
    return 0.0, 0.0, height


def _worlds(scene):
    night = bpy.data.worlds.new("World")
    night.node_tree.nodes["Background"].inputs["Color"].default_value = NIGHT_SKY
    studio = bpy.data.worlds.new("Studio")
    studio.node_tree.nodes["Background"].inputs["Color"].default_value = (0.9, 0.9, 0.9, 1.0)
    scene.world = night
    # Sun for dollhouse views only; hidden otherwise.
    col = _collection("Studio")
    sun = bpy.data.lights.new("Studio Sun", "SUN")
    sun.energy = 2.5
    sun.angle = math.radians(4)
    obj = bpy.data.objects.new("Studio Sun", sun)
    obj.rotation_euler = (math.radians(22), 0.0, math.radians(-40))
    col.objects.link(obj)
    col.hide_render = True


def _daylight(lighting):
    """Day sky and sun for daylight scenarios; both stay off until a scenario asks for them."""
    sky = lighting.get("sky", {})
    day = bpy.data.worlds.new("Day")
    bg = day.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (*sky.get("color", (0.62, 0.74, 0.95)), 1.0)
    bg.inputs["Strength"].default_value = sky.get("strength", 1.5)
    sun_cfg = lighting.get("sun", {})
    col = _collection("Daylight")
    sun = bpy.data.lights.new("Day Sun", "SUN")
    sun.energy = sun_cfg.get("energy", 4.0)
    sun.angle = math.radians(0.6)
    sun.color = sun_cfg.get("color", (1.0, 0.93, 0.84))
    el, az = math.radians(sun_cfg.get("elevation", 30)), math.radians(sun_cfg.get("azimuth", 0))
    travel = Vector((math.cos(el) * math.cos(az), math.cos(el) * math.sin(az), -math.sin(el)))  # sunlight direction
    obj = bpy.data.objects.new("Day Sun", sun)
    obj.rotation_euler = travel.to_track_quat("-Z", "Y").to_euler()
    col.objects.link(obj)
    col.hide_render = True


def apply_lighting(scene, scenario):
    """Lighting scenario: lamps and glowing surfaces outside the `on` switch groups go dark;
    `daylight` turns on the day sky and sun (taken up by stage())."""
    on, dark = set(scenario.get("on", [])), scenario.get("off")  # `off` instead of `on`: only these go dark
    off = materials.matte("Lamp Off", "#EDEDEA", 0.4)
    lenses = {}  # a lamp lens keeps its own frosted look, only without the glow

    def unlit(mat):
        if mat is None or not mat.get("lens"):
            return off
        if mat.name not in lenses:
            lenses[mat.name] = mat.copy()
            lenses[mat.name].name = f"{mat.name} Off"
            lenses[mat.name].node_tree.nodes["Principled BSDF"].inputs["Emission Strength"].default_value = 0.0
        return lenses[mat.name]

    for obj in bpy.data.objects:
        group = obj.get("light_group")
        if group is None or (group not in dark if dark is not None else group in on):
            continue
        if obj.type == "LIGHT":
            obj.hide_render = True
        else:
            for slot in obj.material_slots:
                slot.material = unlit(slot.material)
    scene["daylight"] = bool(scenario.get("daylight"))
    if scenario.get("sky_strength"):  # e.g. a window that never gets direct sun needs a brighter sky
        bpy.data.worlds["Day"].node_tree.nodes["Background"].inputs["Strength"].default_value = scenario["sky_strength"]


def _apply_clay():
    """Swap every material for neutral clay, except glass, mirrors and light emitters."""
    clay = materials.matte("Clay", "#E4E1DB", 0.6)
    clay_floor = materials.matte("Clay Floor", "#CBC6BE", 0.6)
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        target = clay_floor if obj.name.startswith("Floor") else clay
        for slot in obj.material_slots:
            if slot.material is not None and not slot.material.get("keep_in_clay"):
                slot.material = target


def build(cfg, clay=False):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    width, depth, height = _plan_architecture(cfg) if cfg["outline"] else _rect_architecture(cfg)

    light_col = _collection("Lights")
    if cfg["ceiling_lights"]:
        lc = cfg["ceiling_lights"]
        lights.LAYOUTS[lc["type"]](lc, width, depth, height, light_col)
    if cfg["pendants"]:
        temperature = (cfg["ceiling_lights"] or {}).get("temperature", 3000)
        lights.build_pendants(cfg["pendants"], height, temperature, light_col)
    if cfg["wall_lights"]:
        lights.build_wall_lights(cfg["wall_lights"], cfg["_frames"], light_col)

    cams = _collection("Cameras")
    cameras = [cam for c in cfg["cameras"]
               for cam in (_cube_cameras(c, cams) if c["type"] == "cube" else [_camera(c, cams)])]
    _worlds(scene)
    _daylight(cfg.get("lighting", {}))
    if clay:
        _apply_clay()
    return scene, cameras


def stage(scene, rcfg, dollhouse):
    """Switch between the interior setup and the dollhouse one (no ceiling, lit from outside)."""
    for name, hidden in (("Ceiling", dollhouse), ("Lights", dollhouse), ("Studio", not dollhouse)):
        col = bpy.data.collections.get(name)
        if col is not None:
            col.hide_render = hidden
    day = bool(scene.get("daylight")) and not dollhouse
    for name in ("Daylight", "Portals"):
        col = bpy.data.collections.get(name)
        if col is not None:
            col.hide_render = not day
    scene.world = bpy.data.worlds["Studio" if dollhouse else "Day" if day else "World"]
    scene.view_settings.use_white_balance = bool(rcfg["white_balance"]) and not dollhouse


QUALITY = {  # mode: (resolution scale key, samples key, adaptive noise threshold)
    "preview": ("preview_scale", "preview_samples", 0.02),
    "review": ("review_scale", "review_samples", 0.015),
    "hd": ("hd_scale", "hd_samples", 0.008),
    "final": (None, "samples", 0.008),
}


def configure_render(scene, rcfg, mode="review", samples=None, cpu=False):
    scene.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "NONE" if cpu else "METAL"
    prefs.get_devices()
    gpu = False
    for dev in prefs.devices:
        dev.use = dev.type == "METAL" and not cpu
        gpu = gpu or dev.use
    scene.cycles.device = "GPU" if gpu else "CPU"

    cy = scene.cycles
    scale_key, samples_key, threshold = QUALITY[mode]
    cy.samples = samples or rcfg[samples_key]
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = threshold
    cy.use_denoising = rcfg["denoise"]
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.denoising_use_gpu = gpu and rcfg["gpu_denoise"]
    # Keep the synced scene and BVH between the cameras of one run instead of rebuilding them per frame.
    scene.render.use_persistent_data = rcfg["persistent_data"]
    cy.max_bounces = 12
    cy.diffuse_bounces = 6
    cy.glossy_bounces = 4
    cy.transmission_bounces = 4
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.sample_clamp_indirect = 10.0
    cy.blur_glossy = 1.0

    res_x, res_y = rcfg["resolution"]
    scene.render.resolution_x, scene.render.resolution_y = res_x, res_y
    scene.render.resolution_percentage = int(rcfg[scale_key] * 100) if scale_key else 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"

    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = rcfg["look"]
    scene.view_settings.exposure = rcfg["exposure"]
    if rcfg["white_balance"]:
        # Like a camera's WB setting: the illuminant temperature that should render neutral.
        scene.view_settings.use_white_balance = True
        scene.view_settings.white_balance_temperature = rcfg["white_balance"]
    return "GPU (Metal)" if gpu else "CPU"
