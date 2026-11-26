"""Architecture from a measured plan.

The interior is an outline of wall segments listed counter-clockwise (interior on the left of
each from -> to). Every segment gets a wall slab outward; the interior volume, doorways and
windows are then cut out with one boolean, so L-shapes, niches and open passages need no
special cases.
"""

from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from . import geo, materials
from .room import baseboard_profile

WINDOW_FRAME_W = 0.065   # visible PVC profile width
WINDOW_FRAME_D = 0.07    # PVC profile depth
SILL_T = 0.04            # Möller LD-40 window sill: 40 mm thick


def sill_profile(depth):
    """LD-40 cross-section: a = from the window frame toward the room, b = up from the underside;
    rounded nose with a small drip lip underneath."""
    r = 0.012
    return geo.profile(
        (0.0, 0.0), (depth - 0.006, 0.0), (depth - 0.006, 0.004), (depth, 0.008), (depth, SILL_T - r),
        geo.arc((depth - r, SILL_T - r), r, 0, 90, 8), (0.0, SILL_T),
    )


def wall_frames(outline):
    frames = {}
    for w in outline:
        a, b = Vector((*w["from"], 0.0)), Vector((*w["to"], 0.0))
        nrm = geo.Z.cross((b - a).normalized())
        frames[w["id"]] = geo.WallFrame(w["id"], b, geo.Z.cross(nrm), nrm, (b - a).length, w["thickness"])
    return frames


def _hide(obj):
    obj.hide_render = True
    obj.display_type = "WIRE"
    return obj


def _cutter(name, p0, p1, material, collection):
    return _hide(geo.box(name, p0, p1, material, collection))


def outlines(cfg):
    """The main outline and those of the extra rooms (each its own closed interior)."""
    return [cfg["outline"]] + [r["outline"] for r in cfg.get("extra_rooms", [])]


def _interior_prism(outline, height, material, collection, grow=0.0):
    """Cutter of a room's interior. `grow` pushes it into the walls, so its faces become the wall surfaces and
    give them its material (the slabs' own faces sit exactly on the outline and would keep theirs)."""
    pts = [Vector((*w["from"], 0.0)) for w in outline]
    if grow:
        n = len(pts)
        out = []
        for i in range(n):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % n]
            n1, n2 = (b - a).normalized().cross(geo.Z), (c - b).normalized().cross(geo.Z)  # outward (CCW outline)
            m = (n1 + n2).normalized()
            out.append(b + m * (grow / max(m.dot(n1), 1e-3)))
        pts = out
    return _hide(geo.prism("Cutter Interior", [(p.x, p.y) for p in pts], -0.02, height + 0.02, material, collection))


def floor_material(name, fl, origin):
    if fl.get("type") == "laminate":
        texture = fl.get("texture") and Path(__file__).resolve().parent.parent / fl["texture"]
        if texture and not texture.exists():
            print(f"laminate texture not found, using procedural oak: {texture}")
            texture = None
        tint = None
        if texture and fl.get("tint_to"):  # recolor the photo: its average `color` becomes `tint_to`
            tint = tuple(t / c for t, c in zip(materials.rgba(fl["tint_to"])[:3], materials.rgba(fl["color"])[:3]))
        return materials.laminate(name, fl["color"], fl["plank"], fl.get("chamfer", 0.0015), fl.get("roughness", 0.55),
                                  origin=origin, along=fl.get("along", "x"), stagger=fl.get("stagger"), texture=texture,
                                  tint=tint)
    return tile_material(name, fl, origin)


def build_shell(cfg, frames, doors, arch, ceiling_col, cutters):
    """Walls, floor, ceiling and windows. Returns floor-level blockers for the baseboard."""
    outline, h = cfg["outline"], cfg["room"]["height"]
    walls = cfg["walls"]
    if walls["finish"] == "wallpaper":
        wall_mat = materials.wallpaper("Wallpaper", walls["color"], walls["roughness"])
    else:
        wall_mat = materials.matte("Wall Paint", walls["color"], walls["roughness"])

    bm = bmesh.new()
    for w in (w for ol in outlines(cfg) for w in ol):
        a, b = Vector((*w["from"], 0.0)), Vector((*w["to"], 0.0))
        d = (b - a).normalized()
        t = w["thickness"]
        # Extended past both ends so neighbouring slabs overlap at the corners; `past_ends` reaches further,
        # to an outer corner beyond a jog such as the riser box.
        e0, e1 = w.get("past_ends", (0.0, 0.0))
        geo.add_box(bm, a - d * (t + e0), b + d * (t + e1) + d.cross(geo.Z) * t + geo.Z * h)
    walls_obj = geo.mesh_object("Walls", bm, wall_mat, arch)

    for ol, room in zip(outlines(cfg), [None, *cfg.get("extra_rooms", [])]):
        # The interior cutter's material becomes the finish of that room's wall faces (boolean TRANSFER),
        # so a tiled room (walls.finish = "tile") gets tile laid in the plane of each wall.
        # A room with its own wallpaper color (walls.color, e.g. another wallpaper in the study) works the same way.
        rw = (room or {}).get("walls") or {}
        tiled = rw.get("finish") == "tile"
        own = not tiled and bool(rw.get("color"))
        if tiled:
            mat = tile_material(f"Wall Tile {room['id']}", rw, tuple(rw.get("origin", (0.0, 0.0, 0.0))), axes="box")
        elif own:
            mat = materials.wallpaper(f"Wallpaper {room['id']}", rw["color"], rw.get("roughness", walls["roughness"]))
        else:
            mat = wall_mat
        cutter = _interior_prism(ol, h, mat, cutters, grow=0.001 if tiled or own else 0.0)
        accent = rw.get("accent")
        if tiled and accent:  # another tile on some walls: the cutter's side face of each (in outline order)
            cutter.data.materials.append(tile_material(f"Wall Tile {room['id']} Accent", {**rw, **accent},
                                                       tuple(rw.get("origin", (0.0, 0.0, 0.0))), axes="box"))
            for i, w in enumerate(ol):
                if w["id"] in accent["walls"]:
                    cutter.data.polygons[2 + i].material_index = 1
    for i, dr in enumerate(doors):
        f = dr.f
        _hide(geo.frame_box(f"Cutter Door {i + 1}", f, dr.s0, 0.02, -0.02, dr.s1, -f.thickness - 0.05, dr.oh,
                            wall_mat, cutters))
    blockers = []
    for i, win in enumerate(cfg["windows"]):
        blockers += build_window(f"Window {i + 1}", win, frames[win["wall"]], wall_mat, arch, cutters)

    mod = walls_obj.modifiers.new("Openings", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.operand_type = "COLLECTION"
    mod.collection = cutters
    mod.solver = "EXACT"
    mod.use_self = True  # the wall slabs overlap each other
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"  # cut faces take the cutters' wall finish
    cutters.hide_render = True

    every = [w for ol in outlines(cfg) for w in ol]
    xs = [p[0] for w in every for p in (w["from"], w["to"])]
    ys = [p[1] for w in every for p in (w["from"], w["to"])]
    pad = max(w["thickness"] for w in every) + 0.1
    lo, hi = (min(xs) - pad, min(ys) - pad), (max(xs) + pad, max(ys) + pad)
    fl = cfg["floor"]
    floor_mat = tile_material("Floor Tile", fl, tuple(fl.get("origin", (0.0, 0.0))))  # grid start (x, y)
    # Floor only inside the outline, plus a patch into each doorway up to the threshold or leaf.
    floor = geo.prism("Floor", [w["from"] for w in outline], -0.05, 0.0, floor_mat, arch)
    for i, dr in enumerate(doors):
        f = dr.f
        d0, d1 = dr.floor_depths()
        pts = [f.world(dr.s0, 0.001, 0.0), f.world(dr.s1, 0.001, 0.0), f.world(dr.s1, -d1, 0.0), f.world(dr.s0, -d0, 0.0)]
        geo.prism(f"Floor Doorway {i + 1}", [(p.x, p.y) for p in pts], -0.05, 0.0, floor_mat, arch).parent = floor
    for room in cfg.get("extra_rooms", []):
        # Its own floor; from its side the doorway gets the rest of the wall depth, up to the main floor's patch.
        rf = room["floor"]
        mat = floor_material(f"Floor {room['id']}", rf, tuple(rf.get("origin", (0.0, 0.0))))
        own = geo.prism(f"Floor {room['id']}", [w["from"] for w in room["outline"]], -0.05, 0.0, mat, arch)
        for k, dw in enumerate(room.get("doorways", [])):
            f = frames[dw["wall"]]
            s0, s1 = f.span(None, dw)
            geo.frame_box(f"Floor {room['id']} Doorway {k + 1}", f, s0, 0.001, -0.05, s1, -dw["depth"], 0.0, mat,
                          arch).parent = own
            blockers.append(geo.rect(f.world(s0, -0.05, 0.0), f.world(s1, 0.05, 0.0)))
    ceiling_mat = materials.matte("Ceiling Paint", cfg["ceiling"]["color"], 0.9)
    geo.box("Ceiling", (*lo, h), (*hi, h + 0.2), ceiling_mat, ceiling_col)  # thick enough for recesses
    build_ceiling_details(cfg, ceiling_col)
    return blockers


def build_ceiling_details(cfg, collection):
    """Stretch-ceiling details: a shadow gap along the walls and seams between canvases."""
    c, h = cfg["ceiling"], cfg["room"]["height"]
    gap = c.get("shadow_gap")
    for m, outline in enumerate(outlines(cfg) if gap else []):
        dark = materials.matte("Shadow Gap", "#1C1C1C", 0.8)
        skip = set(gap.get("skip_walls", []))
        n = len(outline)
        start = next((i + 1 for i, w in enumerate(outline) if w["id"] in skip), 0) % n
        runs, cur = [], []
        for k in range(n):  # walk the outline from just after a skipped wall, so runs are unbroken
            w = outline[(start + k) % n]
            if w["id"] in skip:
                if cur:
                    runs.append(cur)
                cur = []
                continue
            cur = cur or [w["from"]]
            cur.append(w["to"])
        if cur:
            runs.append(cur)
        prof = [(0.0, -0.0006), (gap["width"], -0.0006), (gap["width"], 0.0), (0.0, 0.0)]
        for k, run in enumerate(runs):
            pts = [Vector((x, y, h)) for x, y in run]
            closed = not skip
            geo.sweep(f"Shadow Gap {m + 1}.{k + 1}", pts[:-1] if closed else pts, geo.Z, prof, dark, collection,
                      side=1.0, closed=closed, smooth_angle=None)
    seam = materials.matte("Ceiling Seam", "#D9D9D5", 0.8)
    for k, s in enumerate(c.get("seams", [])):
        (x0, y0), (x1, y1) = s["from"], s["to"]
        geo.box(f"Ceiling Seam {k + 1}", (min(x0, x1) - 0.001, min(y0, y1) - 0.001, h - 0.0008),
                (max(x0, x1) + 0.001, max(y0, y1) + 0.001, h), seam, collection)


def tile_material(name, fl, origin, axes=("X", "Y")):
    """Material of the floor tile (photo texture if present), laid from `origin` in the `axes` plane."""
    texture = fl.get("texture")
    if texture:
        texture = Path(__file__).resolve().parent.parent / texture
        if not texture.exists():
            print(f"tile texture not found, using flat color: {texture}")
            texture = None
    return materials.porcelain(name, fl["color"], fl["grout_color"], fl["tile"], fl["grout"], fl["roughness"],
                               origin=origin, texture=texture, texture_rotate=fl.get("texture_rotate", False),
                               texture_gloss=fl.get("texture_gloss"), axes=axes, faces=fl.get("faces"))


def build_window(name, cfg, frame, wall_mat, collection, cutters):
    """Window / balcony block: PVC frames set into the reveal, glass, a sill under window parts."""
    pvc = materials.matte(f"{name} PVC", "#F3F3F1", 0.35)
    sill = materials.matte(f"{name} Sill", "#F2F2EF", 0.65)  # Möller LD-40 Clean Touch, white matt
    glass = materials.glass(f"{name} Glass")
    w, t = frame.world, frame.thickness
    plane = -(cfg["frame_depth"] if cfg.get("frame_depth") is not None else min(0.15, t * 0.4))
    d0, d1 = plane - WINDOW_FRAME_D / 2, plane + WINDOW_FRAME_D / 2
    fw = WINDOW_FRAME_W
    blockers = []
    for i, part in enumerate(cfg["parts"]):
        tag = f"{name}.{i + 1}"
        s0, s1 = frame.span(None, part)
        z0, z1 = part["z"]
        is_door = part["type"] == "door"
        _cutter(f"Cutter {tag}", w(s0, 0.02, z0 - 0.02 if is_door else z0), w(s1, -t - 0.05, z1), wall_mat, cutters)
        bottom = fw * (0.5 if is_door else 1.0)
        bars = [(s0, z0, s0 + fw, z1), (s1 - fw, z0, s1, z1),
                (s0 + fw, z1 - fw, s1 - fw, z1), (s0 + fw, z0, s1 - fw, z0 + bottom)]
        for k, (a0, b0, a1, b1) in enumerate(bars):
            geo.box(f"{tag} Frame {k + 1}", w(a0, d0, b0), w(a1, d1, b1), pvc, collection, bevel=0.002)
        # Horizontal imposts split the part into panes; "solid" lists panes that are opaque panels.
        edges = [z0 + bottom, *part.get("splits", []), z1 - fw]
        for k, (lo, hi) in enumerate(zip(edges, edges[1:])):
            if k > 0:
                geo.box(f"{tag} Impost {k}", w(s0 + fw, d0, lo - fw / 2), w(s1 - fw, d1, lo + fw / 2), pvc, collection,
                        bevel=0.002)
            pane_lo = lo + (fw / 2 if k > 0 else 0.0)
            pane_hi = hi - (fw / 2 if k < len(edges) - 2 else 0.0)
            solid = k in part.get("solid", [])
            geo.box(f"{tag} {'Panel' if solid else 'Glass'} {k + 1}", w(s0 + fw, plane - 0.012, pane_lo),
                    w(s1 - fw, plane + 0.012, pane_hi), pvc if solid else glass, collection)
        if is_door:
            blockers.append(geo.rect(w(s0, -0.05, 0), w(s1, 0.05, 0)))
        elif part.get("sill") is not False:  # an upper tier of a window has no sill of its own
            # Sill from the window frame to `proud` past the wall face; ears 4 cm past the opening, or `span` ends.
            sc = part.get("sill", {})
            depth = sc.get("proud", 0.05) - d1
            a, b = frame.span(None, sc) if sc.get("span") else (s0 - 0.04, s1 + 0.04)
            geo.sweep(f"{tag} Sill", [w(a, d1, z0 - SILL_T), w(b, d1, z0 - SILL_T)], geo.Z,
                      sill_profile(depth), sill, collection, side=-1.0)
        if cfg.get("light_portal", True):
            _portal(f"{tag} Portal", w, s0, s1, z0, z1, plane - 0.05)
    return blockers


def _portal(name, w, s0, s1, z0, z1, d):
    """Light portal just outside a window opening: tells Cycles where the sky light comes in, so sky-lit rooms
    (no direct sun) render without blotchy noise. Used in day scenes only (see scene.stage)."""
    col = bpy.data.collections.get("Portals")
    if col is None:
        col = bpy.data.collections.new("Portals")
        bpy.context.scene.collection.children.link(col)
    light = bpy.data.lights.new(name, "AREA")
    light.shape = "RECTANGLE"
    light.size, light.size_y = s1 - s0, z1 - z0
    light.cycles.is_portal = True
    obj = bpy.data.objects.new(name, light)
    obj.location = w((s0 + s1) / 2, d, (z0 + z1) / 2)
    inward = Vector(w(0.0, 1.0, 0.0)) - Vector(w(0.0, 0.0, 0.0))
    obj.rotation_euler = inward.to_track_quat("-Z", "Y").to_euler()  # an area light shines along its -Z
    col.objects.link(obj)


def _clip(a, b, r):
    """Parameter interval of segment a-b inside the rectangle r (Liang-Barsky), or None."""
    xmin, xmax, ymin, ymax = r
    t0, t1 = 0.0, 1.0
    dx, dy = b.x - a.x, b.y - a.y
    for p, q in ((-dx, a.x - xmin), (dx, xmax - a.x), (-dy, a.y - ymin), (dy, ymax - a.y)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
    return (t0, t1) if t0 < t1 else None


def build_baseboard(cfg, blockers, collection):
    """Baseboard along the outline, broken wherever a door, wardrobe etc. stands on the floor line."""
    bb = cfg["baseboard"]
    if not bb["enabled"]:
        return
    mat = (materials.veneer("Baseboard Wood", bb["color"]) if bb.get("finish") == "oak"
           else materials.paint("Baseboard Paint", bb["color"]))
    prof = baseboard_profile(bb["height"], bb["thickness"])
    rects = [(r[0] - 0.002, r[1] + 0.002, r[2] - 0.002, r[3] + 0.002) for r in blockers]
    for m, (outline, room) in enumerate(zip(outlines(cfg), [None, *cfg.get("extra_rooms", [])])):
        if room and room.get("baseboard") is False:  # e.g. a tiled bathroom
            continue
        _baseboard_outline(f"Baseboard {m + 1}", outline, rects, prof, mat, collection)


def _baseboard_outline(name, outline, rects, prof, mat, collection):
    pts = [Vector((*w["from"], 0.0)) for w in outline]
    n = len(pts)

    runs = []
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        t, free = 0.0, []
        for c0, c1 in sorted(c for c in (_clip(a, b, r) for r in rects) if c):
            if c0 > t:
                free.append((t, c0))
            t = max(t, c1)
        if t < 1.0:
            free.append((t, 1.0))
        for t0, t1 in free:
            if (t1 - t0) * (b - a).length < 0.005:
                continue
            last = runs[-1] if runs else None
            if last and last["edge"] == i - 1 and last["open_end"] and t0 == 0.0:
                last["pts"].append(a.lerp(b, t1))  # continues around the corner
            else:
                runs.append({"pts": [a.lerp(b, t0), a.lerp(b, t1)], "first": i, "open_start": t0 == 0.0})
            runs[-1]["edge"], runs[-1]["open_end"] = i, t1 == 1.0

    closed = False
    if runs and runs[0]["first"] == 0 and runs[0]["open_start"] and runs[-1]["edge"] == n - 1 and runs[-1]["open_end"]:
        if len(runs) == 1:
            closed = True
            runs[0]["pts"].pop()
        else:
            runs[0]["pts"] = runs[-1]["pts"][:-1] + runs[0]["pts"]
            runs.pop()
    for k, run in enumerate(runs):
        geo.sweep(f"{name}.{k + 1}", run["pts"], geo.Z, prof, mat, collection, side=1.0, closed=closed)
