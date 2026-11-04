"""Room shell: walls with openings, floor, ceiling and a mitered baseboard."""

import bpy
from mathutils import Vector

from . import geo, materials
from .geo import arc, profile


class Arch:
    """Open doorway without a door; "ceiling" height cuts the wall all the way up."""

    def __init__(self, cfg, frame, room_height):
        self.cfg = cfg
        self.f = frame
        self.h = room_height if cfg["height"] == "ceiling" else cfg["height"]
        self.s0, self.s1 = frame.span(cfg["width"], cfg)

    @property
    def opening(self):
        return (self.s0, self.s1, 0.0, self.h)

    @property
    def footprint(self):
        return (self.s0, self.s1)


def build_beyond(arch, height, thickness, mats, collection, depth=2.5, margin=1.2):
    """A plain lit space behind an arch, so the opening does not look into the void."""
    w = arch.f.world
    a, b = arch.s0 - margin, arch.s1 + margin
    d0, d1 = -thickness - depth, -thickness
    wall_mat, floor_mat, ceiling_mat = mats
    geo.box("Beyond Floor", w(a, d0, -0.05), w(b, d1, 0.0), floor_mat, collection)
    geo.box("Beyond Ceiling", w(a, d0, height), w(b, d1, height + 0.05), ceiling_mat, collection)
    geo.box("Beyond Wall Far", w(a, d0 - 0.1, 0.0), w(b, d0, height), wall_mat, collection)
    geo.box("Beyond Wall A", w(a - 0.1, d0, 0.0), w(a, d1, height), wall_mat, collection)
    geo.box("Beyond Wall B", w(b, d0, 0.0), w(b + 0.1, d1, height), wall_mat, collection)
    light = bpy.data.lights.new("Beyond Light", "AREA")
    light.size = 0.6
    light.energy = 40.0
    light.use_temperature = True
    light.temperature = 3500
    obj = bpy.data.objects.new("Beyond Light", light)
    obj.location = w((a + b) / 2, (d0 + d1) / 2, height - 0.01)
    collection.objects.link(obj)

# Walls in perimeter order; each wall's s=0 end meets the previous wall's s=L end.
PERIMETER = ("back", "right", "front", "left")
NORMALS = {"back": (0, -1, 0), "right": (-1, 0, 0), "front": (0, 1, 0), "left": (1, 0, 0)}


def neighbors(wall):
    """(wall meeting this one at s=0, wall meeting it at s=length)."""
    i = PERIMETER.index(wall)
    return PERIMETER[i - 1], PERIMETER[(i + 1) % len(PERIMETER)]


def wall_frames(width, depth):
    centers = {"back": (0, depth / 2, 0), "right": (width / 2, 0, 0),
               "front": (0, -depth / 2, 0), "left": (-width / 2, 0, 0)}
    lengths = {"back": width, "front": width, "right": depth, "left": depth}
    frames = {}
    for name in PERIMETER:
        nrm = Vector(NORMALS[name])
        u = geo.Z.cross(nrm)
        frames[name] = geo.WallFrame(name, Vector(centers[name]) - u * lengths[name] / 2, u, nrm, lengths[name])
    return frames


def build_shell(cfg, frames, openings, arches, collection):
    r = cfg["room"]
    w, d, h, t = r["width"], r["depth"], r["height"], r["wall_thickness"]

    walls = cfg["walls"]
    if walls["finish"] == "wallpaper":
        wall_mat = materials.wallpaper("Wallpaper", walls["color"], walls["roughness"])
    else:
        wall_mat = materials.matte("Wall Paint", walls["color"], walls["roughness"])
    for name, frame in frames.items():
        geo.wall_solid(f"Wall {name}", frame, h, t, openings.get(name, []), wall_mat, collection, extend=t)

    fl = cfg["floor"]
    floor_mat = materials.porcelain("Floor Tile", fl["color"], fl["grout_color"], fl["tile"], fl["grout"],
                                    fl["roughness"], origin=(-w / 2, d / 2))
    geo.box("Floor", (-w / 2 - t, -d / 2 - t, -0.05), (w / 2 + t, d / 2 + t, 0.0), floor_mat, collection)
    ceiling_mat = materials.matte("Ceiling Paint", cfg["ceiling"]["color"], 0.9)
    geo.box("Ceiling", (-w / 2 - t, -d / 2 - t, h), (w / 2 + t, d / 2 + t, h + 0.05), ceiling_mat, collection)
    for arch in arches:
        if arch.cfg["beyond"]:
            build_beyond(arch, h, t, (wall_mat, floor_mat, ceiling_mat), collection)


def baseboard_profile(height, thickness=0.016):
    """a = projection into the room, b = height. The top is rounded over to a 4 mm lip."""
    r = min(0.012, thickness - 0.004)
    return profile(
        (0.0, 0.0), (thickness, 0.0), (thickness, height - 0.013 - r),
        arc((thickness - r, height - 0.013 - r), r, 0, 90, 8),
        (0.004, height - 0.002), (0.002, height), (0.0, height),
    )


def build_baseboard(cfg, frames, gaps, collection):
    """Run the baseboard around the perimeter, broken where doors or furniture occupy the floor line."""
    bb = cfg["baseboard"]
    if not bb["enabled"]:
        return
    mat = materials.paint("Baseboard Paint", bb["color"])
    prof = baseboard_profile(bb["height"], bb["thickness"])

    starts, total = {}, 0.0
    for name in PERIMETER:
        starts[name] = total
        total += frames[name].length

    def point(p):
        p %= total
        for name in reversed(PERIMETER):
            if p >= starts[name] - 1e-9:
                return frames[name].world(p - starts[name], 0.0, 0.0)

    corners = [starts[n] for n in PERIMETER]
    cuts = sorted((starts[w] + a, starts[w] + b) for w, spans in gaps.items() for a, b in spans)
    if not cuts:
        geo.sweep("Baseboard", [point(c) for c in corners], geo.Z, prof, mat, collection, side=-1.0, closed=True)
        return
    candidates = sorted(c + k * total for k in (0, 1) for c in corners)
    for i, (_, run_start) in enumerate(cuts):
        run_end = cuts[(i + 1) % len(cuts)][0] + (total if i == len(cuts) - 1 else 0.0)
        if run_end - run_start < 0.01:
            continue  # neighbouring cuts touch, e.g. furniture wrapping a corner
        mids = [c for c in candidates if run_start + 1e-6 < c < run_end - 1e-6]
        path = [point(p) for p in (run_start, *mids, run_end)]
        geo.sweep(f"Baseboard {i + 1}", path, geo.Z, prof, mat, collection, side=-1.0)
