"""Wall switches and sockets modelled on Schneider / Systeme Electric AtlasDesign, white.

Frames ATN0001xx: 83 mm square plus 71 mm per extra post, 11.5 mm thick, near-square corners.
Socket ATN000143: 56 mm face flush with the frame, round recess about 40 mm across, open pin
holes, earthing clips at 12 and 6 o'clock, fixing screw. Switches ATN000111 / ATN000151: 56 mm key
(or two 28 mm keys) standing 16 mm off the wall. Sizes from the systeme.ru datasheets.
"""

import bmesh
import bpy

from . import geo, materials

FRAME = 0.083
PITCH = 0.071
FRAME_T = 0.0115
FACE = 0.056
KEY_FACE = 0.016      # switch keys stand this far from the wall
RECESS_R = 0.0198


def _boolean_cut(obj, cutter):
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    mod = obj.modifiers.new("Recess", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    mod.use_self = True  # frame and socket face overlap in one mesh


def build(items, frames, collection):
    if not items:
        return
    white = materials.paint("AtlasDesign White", "#F6F6F4", 0.15)
    hole = materials.matte("Socket Hole", "#151515", 0.6)
    metal = materials.metal("Socket Metal", "chrome")
    cutters = bpy.data.collections.new("Wiring Cutters")
    bpy.context.scene.collection.children.link(cutters)
    cutters.hide_render = True

    for i, it in enumerate(items):
        f, d0 = frames[it["wall"]], it["d"]
        kinds = it["posts"] or [it["type"]] * len(it["centers"])
        if it.get("vertical"):  # one column of posts, the first one on top with its center at `z`
            s = f.s_at(it["centers"][0])
            posts = [(s, it["z"] - k * PITCH, kind) for k, kind in enumerate(kinds)]
        else:
            posts = [(s, it["z"], kind) for s, kind in sorted(zip((f.s_at(c) for c in it["centers"]), kinds))]
        tag = f"{it['type'].title()} {f.name} {i + 1}"
        face = d0 + FRAME_T

        bm = bmesh.new()
        geo.add_box(bm, f.world(min(p[0] for p in posts) - FRAME / 2, d0, min(p[1] for p in posts) - FRAME / 2),
                    f.world(max(p[0] for p in posts) + FRAME / 2, face, max(p[1] for p in posts) + FRAME / 2))
        for s, z, kind in posts:
            if kind != "switch":
                geo.add_box(bm, f.world(s - FACE / 2, face - 0.001, z - FACE / 2),
                            f.world(s + FACE / 2, face + 0.0005, z + FACE / 2))
        body = geo.mesh_object(f"{tag} Frame", bm, white, collection)

        for s, z, kind in posts:
            if kind == "switch":
                keys = it["keys"]
                kw = FACE / keys
                for k in range(keys):
                    a = s - FACE / 2 + k * kw
                    geo.box(f"{tag} Key", f.world(a + 0.00035, face - 0.001, z - FACE / 2),
                            f.world(a + kw - 0.00035, d0 + KEY_FACE, z + FACE / 2), white, collection, bevel=0.0015)
                continue
            if kind == "outlet_ip44":  # splash-proof socket (ATN000146): the hinged lid closed over the face
                geo.box(f"{tag} Lid", f.world(s - FACE / 2 + 0.001, face, z - FACE / 2 + 0.001),
                        f.world(s + FACE / 2 - 0.001, face + 0.013, z + FACE / 2 - 0.001), white, collection, bevel=0.004)
                geo.box(f"{tag} Lid Hinge", f.world(s - FACE / 2 + 0.006, face, z + FACE / 2 - 0.006),
                        f.world(s + FACE / 2 - 0.006, face + 0.0145, z + FACE / 2 - 0.002), white, collection,
                        bevel=0.0015)
                continue
            if kind == "data":  # RJ45 module: a square jack in the flat face
                geo.box(f"{tag} Jack", f.world(s - 0.007, face, z - 0.006), f.world(s + 0.007, face + 0.0008, z + 0.006),
                        hole, collection)
                continue
            floor = d0 + 0.001
            depth = face + 0.002 - floor
            cutter = geo.cylinder(f"{tag} Recess Cutter", f.world(s, floor + depth / 2, z), f.nrm, RECESS_R, depth,
                                  white, cutters, 64)
            _boolean_cut(body, cutter)
            for ds in (-0.0095, 0.0095):  # open pin holes, no shutters on ATN000143
                geo.cylinder(f"{tag} Pin Hole", f.world(s + ds, floor + 0.0002, z), f.nrm, 0.0026, 0.0004, hole,
                             collection, 24)
            for dz in (-1, 1):  # earthing clips at 12 and 6 o'clock
                zc = z + dz * (RECESS_R - 0.0008)
                geo.box(f"{tag} Earth Clip", f.world(s - 0.0035, floor, zc - 0.0008),
                        f.world(s + 0.0035, floor + 0.008, zc + 0.0008), metal, collection)
            geo.cylinder(f"{tag} Screw", f.world(s, floor + 0.0003, z - 0.009), f.nrm, 0.003, 0.0006, metal, collection,
                         24)
        geo.add_bevel(body, 0.0006, 2)
