"""Ceiling light layouts."""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import geo, materials

# Lamp geometry for double fixtures: ring around the lamp, glowing face, center spacing, plate size.
LAMPS = {
    # GX53: flat frosted 75 mm disc. A diffuse disc emits with a 120° beam (half intensity at ±60°).
    "gx53": {"ring_r": 0.0375, "ring_color": "#EDEDEB", "face_r": 0.033, "spacing": 0.105,
             "plate": (0.215, 0.115), "light": "disk"},
    # Brain&Home BH53 double: two pull-in modules flush with the stretch ceiling, no plate; each a 108 mm white
    # ring around a GX53 lamp.
    "bh53": {"ring_r": 0.054, "ring_color": "#F2F2F0", "face_r": 0.0355, "spacing": 0.125, "plate": None,
             "light": "disk",
             # Brain&Home BH53 под втяжку, seller data (bhdot.ru, svet-nebo.ru): visible part ⌀108, GX53 lamp
             # ⌀78, mounting depth 40/70. The lamp sits in the ceiling plane (user: «рисуй в плоскости потолка»);
             # around it the canvas is drawn in from ⌀108 into a shallow 3 mm groove to the lamp body; the frosted
             # ⌀71 lens a hair proud of the plane: (radius, height above the ceiling plane), m.
             "pull_in": [(0.0540, 0.0000), (0.0505, 0.0001), (0.0473, 0.0004), (0.0445, 0.0009), (0.0423, 0.0015),
                         (0.0410, 0.0022), (0.0405, 0.0030)],
             "housing": (0.0388, 0.0407, 0.0030), "lamp_rim": (0.0390, 0.0), "lens_z": -0.0001},
    # GU5.3 / MR16: reflector spot behind a dark bezel; beam set by cone/blend.
    "gu5.3": {"ring_r": 0.03, "ring_color": "#2B2B2B", "face_r": 0.02, "spacing": 0.09,
              "plate": (0.18, 0.095), "light": "spot"},
}


def _grid(cfg, width, depth):
    """Fixture centers. `columns` (from the left wall) and `rows` (from the back wall) pin them
    explicitly; otherwise each fixture sits at the center of its cell of a uniform grid."""
    nx, ny = cfg["count_x"], cfg["count_y"]
    xs = cfg["columns"] or [(i + 0.5) * width / nx for i in range(nx)]
    ys = cfg["rows"] or [(j + 0.5) * depth / ny for j in range(ny)]
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            yield f"{i + 1}-{j + 1}", Vector((-width / 2 + x, depth / 2 - y, 0.0))


def set_group(obj, group):
    """Mark a lamp or its glowing surface as part of a switch group (see scene.apply_lighting)."""
    if group:
        obj["light_group"] = group
    return obj


def _light(name, kind, cfg, location, radius, collection):
    if kind == "spot":
        light = bpy.data.lights.new(name, "SPOT")
        light.spot_size = math.radians(cfg["cone"])
        light.spot_blend = cfg["blend"]
        light.shadow_soft_size = radius
    else:
        light = bpy.data.lights.new(name, "AREA")
        light.shape = "DISK"
        light.size = radius * 2
        light.spread = math.pi  # fully diffuse, i.e. a 120° beam
    light.energy = cfg["power"]
    light.use_temperature = True
    light.temperature = cfg["temperature"]
    obj = bpy.data.objects.new(name, light)
    obj.location = location
    collection.objects.link(obj)
    return obj


def build_downlights(cfg, width, depth, height, collection):
    """Single round recessed downlights."""
    r = cfg["diameter"] / 2
    lens_r = r - 0.014
    trim = materials.matte("Downlight Trim", "#F2F2F0", 0.35)
    lens = materials.emitter("Downlight Lens", cfg["temperature"], 25.0)
    for tag, c in _grid(cfg, width, depth):
        geo.cylinder(f"Downlight Trim {tag}", (c.x, c.y, height - 0.003), geo.Z, r, 0.006, trim, collection, 48)
        geo.cylinder(f"Downlight Lens {tag}", (c.x, c.y, height - 0.0065), geo.Z, lens_r, 0.001, lens, collection, 48)
        _light(f"Downlight {tag}", "spot", cfg, (c.x, c.y, height - 0.008), lens_r, collection)


def _lathe(name, center, profile, material, collection, segments=48):
    """Solid of revolution about the vertical through `center`; profile: (radius, height above center) pairs."""
    bm = bmesh.new()
    verts = [bm.verts.new((center.x + r, center.y, center.z + h)) for r, h in profile]
    edges = [bm.edges.new(pair) for pair in zip(verts, verts[1:])]
    bmesh.ops.spin(bm, geom=verts + edges, cent=center, axis=(0.0, 0.0, 1.0), angle=2 * math.pi, steps=segments,
                   use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return geo.mesh_object(name, bm, material, collection, smooth_angle=40)


def _pair_axis(axis, width, depth):
    if axis == "long":
        axis = "y" if depth >= width else "x"
    elif axis == "short":
        axis = "x" if depth >= width else "y"
    return Vector((1, 0, 0)) if axis == "x" else Vector((0, 1, 0))


def build_double(cfg, width, depth, height, collection):
    """Double fixtures (on a plate, or flush pull-in modules); the lamps line up along `pair_axis`."""
    lamp = LAMPS[cfg["lamp"]]
    spacing = cfg["pair_spacing"] or lamp["spacing"]
    trim = materials.matte("Fixture Plate", "#F4F4F2", 0.35)
    ring = materials.matte("Lamp Ring", lamp["ring_color"], 0.4)
    pull_in = lamp.get("pull_in")
    face = (materials.lamp_lens("Lamp Lens", cfg["temperature"], 25.0) if pull_in
            else materials.emitter("Lamp Face", cfg["temperature"], 25.0))
    rim = materials.matte("Lamp Rim", "#F4F4F2", 0.35)
    canvas = bpy.data.materials.get("Ceiling Paint") or materials.matte("Ceiling Paint", "#F7F7F5", 0.9)
    holes = []  # cut out of the ceiling slab: the tucked canvas shows inside
    if cfg["fixtures"]:
        # Explicit plan positions, each with its own lamp axis.
        # "count": lamps in the fixture (2, or 3 for a triple); "groups": one per lamp from the -axis end,
        # when the lamps of one fixture sit on different keys.
        placed = [(str(k + 1), Vector((*fx["at"], 0.0)), fx.get("axis") or cfg["pair_axis"],
                   fx.get("groups") or [fx.get("group")] * fx.get("count", 2), fx.get("power"))
                  for k, fx in enumerate(cfg["fixtures"])]
    else:
        placed = [(name, c, cfg["pair_axis"], [None, None], None) for name, c in _grid(cfg, width, depth)]
    for name, c, axis_name, groups, power in placed:
        lamp_cfg = {**cfg, "power": power} if power is not None else cfg  # e.g. one room's lamps differ
        axis = _pair_axis(axis_name, width, depth)
        across = geo.Z.cross(axis)
        c = c + geo.Z * height
        if lamp["plate"]:
            plate_len, plate_w = lamp["plate"]
            corner = axis * (plate_len + spacing - lamp["spacing"]) / 2 + across * plate_w / 2
            geo.box(f"Fixture Plate {name}", c - corner - geo.Z * 0.006, c + corner, trim, collection, bevel=0.002)
        z = height - (0.006 if lamp["plate"] else 0.0)  # under the plate, or flush with the ceiling
        n = len(groups)
        for k in range(n):
            p = c + axis * (k - (n - 1) / 2) * spacing
            if pull_in:  # canvas tucked into the hole, the module's housing on top, the lamp in it
                at = Vector((p.x, p.y, z))
                _lathe(f"Lamp Canvas {name}.{k + 1}", at, pull_in, canvas, collection)
                r0, r1, top = lamp["housing"]
                _lathe(f"Lamp Housing {name}.{k + 1}", at, [(r1, top), (r0, top)], rim, collection)
                r_rim, z_rim = lamp["lamp_rim"]  # the lamp body: from its face up into the housing
                geo.cylinder(f"Lamp Rim {name}.{k + 1}", (p.x, p.y, z + (z_rim + top) / 2), geo.Z, r_rim,
                             max(top - z_rim, 0.0008), rim, collection, 48)
                set_group(geo.cylinder(f"Lamp Face {name}.{k + 1}", (p.x, p.y, z + lamp["lens_z"]), geo.Z,
                                       lamp["face_r"], 0.0008, face, collection, 48), groups[k])
                hole = geo.cylinder(f"Cutter Lamp Hole {name}.{k + 1}", (p.x, p.y, z + top / 2), geo.Z,
                                    pull_in[0][0] + 0.0002, top + 0.004, canvas, collection, 48)
                hole.hide_render = True
                hole.display_type = "WIRE"
                holes.append(hole)
                below = lamp["lens_z"] - 0.003  # in the recess, under the lens
            else:
                geo.cylinder(f"Lamp Ring {name}.{k + 1}", (p.x, p.y, z - 0.0005), geo.Z, lamp["ring_r"], 0.001,
                             ring, collection, 48)
                set_group(geo.cylinder(f"Lamp Face {name}.{k + 1}", (p.x, p.y, z - 0.0015), geo.Z, lamp["face_r"],
                                       0.001, face, collection, 48), groups[k])
                below = -0.0025
            light = set_group(_light(f"Lamp {name}.{k + 1}", lamp["light"], lamp_cfg, (p.x, p.y, z + below),
                                     lamp["face_r"], collection), groups[k])
            light.visible_camera = False  # the lens shows the lamp; the light itself only lights
    ceiling = bpy.data.objects.get("Ceiling")
    if holes and ceiling is not None:  # one boolean for all the holes
        cutters = bpy.data.collections.new("Lamp Holes")
        bpy.context.scene.collection.children.link(cutters)
        for hole in holes:
            for col in hole.users_collection:
                col.objects.unlink(hole)
            cutters.objects.link(hole)
        cutters.hide_render = True
        mod = ceiling.modifiers.new("Lamp Holes", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.operand_type = "COLLECTION"
        mod.collection = cutters
        mod.solver = "EXACT"


def _sticks(p, tag, height, temperature, collection):
    """Close-to-ceiling LED chandelier: straight glowing bars in two crossing layers, hung on a chrome cross.
    Each layer has `bars` parallel bars `bar_spacing` apart, alternately shifted by `stagger` along their length."""
    x, y = p["at"]
    c = Vector((x, y, 0.0))
    chrome = materials.metal(f"{tag} Chrome", p["finish"])
    glow = materials.emitter(f"{tag} Diffuser", temperature, p["glow"])
    bw, bh = p["bar"]
    n, gap, length, cap = p["bars"], p["bar_spacing"], p["length"], 0.012
    mount_t = 0.012
    a0 = math.radians(p["angle"])
    layers = ((a0, height - p["drop"] + bh + 0.02), (a0 + math.radians(p["cross"]), height - p["drop"]))
    for k, (a, z0) in enumerate(layers):
        u = Vector((math.cos(a), math.sin(a), 0.0))
        across = geo.Z.cross(u)
        reach = (n - 1) * gap / 2 + 0.03
        mount = geo.WallFrame(f"{tag} Mount {k + 1}", c - across * reach, across, -u, 2 * reach)
        geo.frame_box(f"{tag} Mount {k + 1}", mount, 0.0, -0.015, height - mount_t, 2 * reach, 0.015, height, chrome,
                      collection, bevel=0.002)
        for i in range(n):
            off = (i - (n - 1) / 2) * gap
            shift = p["stagger"] * (1 if i % 2 else -1)
            mid = c + across * off + u * shift
            f = geo.WallFrame(f"{tag} Bar", mid - u * length / 2, u, across, length)
            name = f"{tag} Bar {k + 1}.{i + 1}"
            set_group(geo.frame_box(f"{name} Diffuser", f, cap, -bw / 2, z0, length - cap, bw / 2, z0 + bh - 0.004,
                              glow, collection), p["group"])
            geo.frame_box(f"{name} Spine", f, cap, -bw / 2, z0 + bh - 0.004, length - cap, bw / 2, z0 + bh, chrome,
                          collection)
            for s0 in (0.0, length - cap):
                geo.frame_box(f"{name} Cap", f, s0, -bw / 2 - 0.001, z0 - 0.001, s0 + cap, bw / 2 + 0.001,
                              z0 + bh + 0.001, chrome, collection, bevel=0.002)
            top = height - mount_t
            post = c + across * off
            geo.cylinder(f"{name} Post", (post.x, post.y, (z0 + bh + top) / 2), geo.Z, 0.004, top - z0 - bh, chrome,
                         collection, 12)
            light = bpy.data.lights.new(name, "AREA")
            light.shape = "RECTANGLE"
            light.size, light.size_y = length - 2 * cap, bw
            light.energy = p["power"]
            light.use_temperature = True
            light.temperature = temperature
            obj = bpy.data.objects.new(name, light)
            obj.location = (mid.x, mid.y, z0 - 0.002)
            obj.rotation_euler = (0.0, 0.0, a)
            collection.objects.link(obj)
            set_group(obj, p["group"])


def _crystal(p, tag, height, temperature, collection):
    """Round flush crystal chandelier: a chrome disc on the ceiling, a drum of hanging crystal prisms in concentric
    rings of alternating length, bulbs inside. `rings`: [{"radius", "count", "drop": [short, long]}, ...]."""
    x, y = p["at"]
    r_base = p["diameter"] / 2
    chrome = materials.metal(f"{tag} Chrome", p.get("finish", "chrome"))
    crystal = materials.crystal(f"{tag} Crystal")
    geo.cylinder(f"{tag} Base", (x, y, height - 0.02), geo.Z, r_base, 0.04, chrome, collection, 96)
    geo.cylinder(f"{tag} Rim", (x, y, height - 0.05), geo.Z, r_base - 0.01, 0.02, chrome, collection, 96)
    bm = bmesh.new()
    top = height - 0.06
    for ring in p["rings"]:
        radius, count, (short, long) = ring["radius"], int(ring["count"]), ring["drop"]
        for i in range(count):
            a = 2 * math.pi * (i + 0.5 * (radius < r_base - 0.05)) / count
            length = long if i % 2 else short
            cx, cy = x + radius * math.cos(a), y + radius * math.sin(a)
            # a slim prism with a pointed bottom, its wide face toward the outside
            u = Vector((math.cos(a), math.sin(a), 0.0))
            v = Vector((-math.sin(a), math.cos(a), 0.0))
            w, t = 0.009, 0.006
            ring_top = [Vector((cx, cy, top)) + v * sv * w + u * su * t for sv, su in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            ring_bot = [q - geo.Z * length for q in ring_top]
            tip = Vector((cx, cy, top - length - 0.02))
            vt = [bm.verts.new(q) for q in ring_top]
            vb = [bm.verts.new(q) for q in ring_bot]
            vtip = bm.verts.new(tip)
            bm.faces.new(vt[::-1])
            for k in range(4):
                bm.faces.new((vb[k], vb[(k + 1) % 4], vt[(k + 1) % 4], vt[k]))
                bm.faces.new((vb[(k + 1) % 4], vb[k], vtip))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    geo.mesh_object(f"{tag} Prisms", bm, crystal, collection)
    bulb = materials.emitter(f"{tag} Bulb", temperature, 40.0)
    n = p.get("bulbs", 6)
    for i in range(n):
        a = 2 * math.pi * i / n
        bx, by, bz = x + 0.09 * math.cos(a), y + 0.09 * math.sin(a), height - 0.11
        bmb = bmesh.new()
        bmesh.ops.create_uvsphere(bmb, u_segments=16, v_segments=8, radius=0.018, matrix=Matrix.Translation((bx, by, bz)))
        set_group(geo.mesh_object(f"{tag} Bulb {i + 1}", bmb, bulb, collection, smooth_angle=60), p["group"])
        light = bpy.data.lights.new(f"{tag} Bulb {i + 1}", "POINT")
        light.energy = p["power"] / n
        light.shadow_soft_size = 0.018
        light.use_temperature = True
        light.temperature = temperature
        obj = bpy.data.objects.new(f"{tag} Bulb {i + 1}", light)
        obj.location = (bx, by, bz)
        collection.objects.link(obj)
        set_group(obj, p["group"])


def _globes(p, tag, height, temperature, collection):
    """Mid-century chandelier: a rod from a ceiling cup to a hub, `count` arms reaching out and up by `tilt` degrees,
    each ending in a cup that holds an opal globe on its side, a bulb inside every globe."""
    x, y = p["at"]
    metal = materials.metal(f"{tag} Metal", p.get("finish", "brass"))
    opal = materials.emitter(f"{tag} Opal", temperature, p.get("glow", 3.0))
    hub_z = height - p["drop"]
    r_g, reach, n, tilt = p["diameter"] / 2, p["reach"], p["count"], math.radians(p.get("tilt", 20))
    geo.cylinder(f"{tag} Canopy", (x, y, height - 0.012), geo.Z, 0.06, 0.024, metal, collection, 48)
    geo.cylinder(f"{tag} Rod", (x, y, (hub_z + height - 0.024) / 2), geo.Z, 0.007, height - 0.024 - hub_z, metal,
                 collection, 16)
    geo.cylinder(f"{tag} Hub", (x, y, hub_z), geo.Z, 0.05, 0.03, metal, collection, 48)
    hub = Vector((x, y, hub_z))
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        u = Vector((math.cos(a) * math.cos(tilt), math.sin(a) * math.cos(tilt), math.sin(tilt)))
        end = hub + u * reach
        geo.cylinder(f"{tag} Arm {i + 1}", hub + u * (reach / 2), u, 0.005, reach, metal, collection, 12)
        geo.cylinder(f"{tag} Cup {i + 1}", end + u * 0.012, u, 0.022, 0.024, metal, collection, 32)
        g = end + u * (0.024 + r_g * 0.95)  # the globe sits on its side, continuing the arm
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r_g, matrix=Matrix.Translation(g))
        globe = geo.mesh_object(f"{tag} Globe {i + 1}", bm, opal, collection, smooth_angle=60)
        globe.visible_shadow = False  # the bulb inside lights the room
        set_group(globe, p["group"])
        light = bpy.data.lights.new(f"{tag} Globe {i + 1}", "POINT")
        light.energy = p["power"] / n
        light.shadow_soft_size = r_g * 0.6
        light.use_temperature = True
        light.temperature = temperature
        obj = bpy.data.objects.new(f"{tag} Globe {i + 1}", light)
        obj.location = g
        collection.objects.link(obj)
        set_group(obj, p["group"])


def build_pendants(items, height, temperature, collection):
    """Pendants on a rod: "globe" (glowing sphere) or "disc" (flat body, opal diffuser underneath);
    "sticks" is a close-to-ceiling chandelier of crossing LED bars."""
    canopy = materials.matte("Pendant Metal", "#F2F2F0", 0.3)
    shade = materials.emitter("Pendant Shade", temperature, 4.0)
    diffuser = materials.emitter("Pendant Diffuser", temperature, 20.0)
    for i, p in enumerate(items):
        x, y = p["at"]
        r = p["diameter"] / 2
        tag = f"Pendant {i + 1}"
        if p["style"] == "sticks":
            _sticks(p, tag, height, temperature, collection)
            continue
        if p["style"] == "crystal":
            _crystal(p, tag, height, temperature, collection)
            continue
        if p["style"] == "globes":
            _globes(p, tag, height, temperature, collection)
            continue
        geo.cylinder(f"{tag} Canopy", (x, y, height - 0.012), geo.Z, 0.06, 0.024, canopy, collection)
        geo.cylinder(f"{tag} Rod", (x, y, height - p["drop"] / 2), geo.Z, 0.004, p["drop"], canopy, collection, 12)
        if p["style"] == "disc":
            t = p["thickness"]
            bottom = height - p["drop"] - t
            geo.cylinder(f"{tag} Body", (x, y, bottom + t / 2), geo.Z, r, t, canopy, collection, 96)
            geo.cylinder(f"{tag} Diffuser", (x, y, bottom - 0.001), geo.Z, r - 0.012, 0.002, diffuser, collection, 96)
            light = bpy.data.lights.new(tag, "AREA")
            light.shape = "DISK"
            light.size = 2 * (r - 0.012)
            light.energy = p["power"]
            light.use_temperature = True
            light.temperature = temperature
            obj = bpy.data.objects.new(tag, light)
            obj.location = (x, y, bottom - 0.003)
            collection.objects.link(obj)
            continue
        zc = height - p["drop"] - r
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=48, v_segments=24, radius=r, matrix=Matrix.Translation((x, y, zc)))
        globe = geo.mesh_object(f"{tag} Shade", bm, shade, collection, smooth_angle=60)
        globe.visible_shadow = False  # let the bulb inside light the room
        light = bpy.data.lights.new(tag, "POINT")
        light.energy = p["power"]
        light.shadow_soft_size = r * 0.6
        light.use_temperature = True
        light.temperature = temperature
        obj = bpy.data.objects.new(tag, light)
        obj.location = (x, y, zc)
        collection.objects.link(obj)


def build_wall_lights(items, frames, collection):
    """Wall sconces (бра): round wall plate, short arm, an opal cylinder shade glowing up and down.
    Item: {"wall", "centers": plan coordinates along the wall, "z": shade center, "group", "power", "temperature"}."""
    plate = materials.matte("Sconce Metal", "#E9E7E2", 0.35)
    for i, it in enumerate(items):
        f = frames[it["wall"]]
        temperature = it.get("temperature", 3000)
        shade = materials.emitter(f"Sconce Shade {i + 1}", temperature, it.get("glow", 3.0))
        for k, c in enumerate(it["centers"]):
            s, z, tag = f.s_at(c), it["z"], f"Sconce {i + 1}.{k + 1}"
            geo.cylinder(f"{tag} Plate", f.world(s, 0.006, z), f.nrm, 0.055, 0.012, plate, collection, 48)
            geo.frame_box(f"{tag} Arm", f, s - 0.008, 0.012, z - 0.008, s + 0.008, 0.075, z + 0.008, plate, collection)
            glow = geo.cylinder(f"{tag} Shade", f.world(s, 0.13, z), geo.Z, 0.055, 0.16, shade, collection, 48)
            glow.visible_shadow = False
            set_group(glow, it.get("group"))
            light = bpy.data.lights.new(tag, "POINT")
            light.energy = it.get("power", 8.0)
            light.shadow_soft_size = 0.04
            light.use_temperature = True
            light.temperature = temperature
            obj = bpy.data.objects.new(tag, light)
            obj.location = f.world(s, 0.13, z)
            collection.objects.link(obj)
            set_group(obj, it.get("group"))


LAYOUTS = {"downlight": build_downlights, "double": build_double}
