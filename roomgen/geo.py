"""Mesh primitives: boxes, cylinders, profile sweeps and walls with openings."""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

Z = Vector((0.0, 0.0, 1.0))


class WallFrame:
    """Local frame of a wall's interior face.

    s runs along the wall from its left end to its right end (as seen from inside),
    d points into the room (negative d goes into the wall), z is height above the floor.
    """

    def __init__(self, name, origin, u, nrm, length, thickness=0.2):
        self.name = name
        self.origin = Vector(origin)
        self.u = Vector(u)
        self.nrm = Vector(nrm)
        self.length = length
        self.thickness = thickness

    def world(self, s, d, z):
        return self.origin + self.u * s + self.nrm * d + Z * z

    def s_at(self, c):
        """Wall position of plan coordinate c: x on walls running along x, y on walls along y."""
        if abs(self.u.x) >= abs(self.u.y):
            return (c - self.origin.x) * self.u.x
        return (c - self.origin.y) * self.u.y

    def span(self, width, cfg):
        """Place something along the wall: `span` gives the plan coordinates of both ends;
        `from_left` / `from_right` is the gap between a wall end and the item's edge;
        otherwise it is centered, shifted by `offset`."""
        if cfg.get("span") is not None:
            return tuple(sorted(self.s_at(c) for c in cfg["span"]))
        if cfg.get("from_left") is not None:
            s0 = cfg["from_left"]
        elif cfg.get("from_right") is not None:
            s0 = self.length - cfg["from_right"] - width
        else:
            s0 = self.length / 2 + cfg.get("offset", 0.0) - width / 2
        return s0, s0 + width


def mesh_object(name, bm, material, collection, smooth_angle=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth_angle is not None:
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    if material is not None:
        me.materials.append(material)
    obj = bpy.data.objects.new(name, me)
    collection.objects.link(obj)
    return obj


def add_bevel(obj, width, segments=3):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    return mod


def rect(p, q):
    """2D footprint (xmin, xmax, ymin, ymax) of two opposite corners."""
    return (min(p.x, q.x), max(p.x, q.x), min(p.y, q.y), max(p.y, q.y))


def add_box(bm, p0, p1):
    """Add an axis-aligned box between two opposite corners to a bmesh."""
    lo = Vector(map(min, p0, p1))
    hi = Vector(map(max, p0, p1))
    verts = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.scale(bm, vec=hi - lo, verts=verts)
    bmesh.ops.translate(bm, vec=(lo + hi) / 2, verts=verts)


def box(name, p0, p1, material, collection, bevel=0.0, bevel_segments=3):
    """Axis-aligned box between two opposite corners given in world space."""
    bm = bmesh.new()
    add_box(bm, p0, p1)
    obj = mesh_object(name, bm, material, collection)
    if bevel:
        add_bevel(obj, bevel, bevel_segments)
    return obj


def frame_box(name, frame, s0, d0, z0, s1, d1, z1, material, collection, bevel=0.0, bevel_segments=3):
    """Box aligned to a (possibly rotated) frame, given in its s/d/z coordinates."""
    bm = bmesh.new()
    v = [bm.verts.new(frame.world(s, d, z)) for z in (z0, z1) for d in (d0, d1) for s in (s0, s1)]
    for quad in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([v[i] for i in quad])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = mesh_object(name, bm, material, collection)
    if bevel:
        add_bevel(obj, bevel, bevel_segments)
    return obj


def prism(name, points, z0, z1, material, collection):
    """Vertical prism over a polygon footprint of (x, y) points; concave outlines are fine."""
    bm = bmesh.new()
    bot = [bm.verts.new((p[0], p[1], z0)) for p in points]
    top = [bm.verts.new((p[0], p[1], z1)) for p in points]
    bm.faces.new(list(reversed(bot)))
    bm.faces.new(top)
    n = len(points)
    for i in range(n):
        bm.faces.new((bot[i], bot[(i + 1) % n], top[(i + 1) % n], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, material, collection)


def cylinder(name, center, axis, radius, depth, material, collection, segments=40, radius2=None):
    bm = bmesh.new()
    rot = Z.rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=segments,
        radius1=radius,
        radius2=radius if radius2 is None else radius2,
        depth=depth,
        matrix=Matrix.Translation(Vector(center)) @ rot,
    )
    return mesh_object(name, bm, material, collection, smooth_angle=40)


def arc(center, radius, a0, a1, steps=8):
    """Points of a circular arc in profile space, degrees, excluding the start point."""
    cx, cy = center
    return [
        (cx + radius * math.cos(math.radians(a0 + (a1 - a0) * i / steps)),
         cy + radius * math.sin(math.radians(a0 + (a1 - a0) * i / steps)))
        for i in range(1, steps + 1)
    ]


def profile(*parts):
    """Flatten points/arc lists into a profile polygon, dropping consecutive duplicates."""
    pts = []
    for part in parts:
        for p in part if isinstance(part, list) else [part]:
            if not pts or (abs(pts[-1][0] - p[0]) > 1e-6 or abs(pts[-1][1] - p[1]) > 1e-6):
                pts.append(p)
    return pts


def sweep(name, path, plane_normal, prof, material, collection, side=1.0, closed=False, smooth_angle=35):
    """Sweep a closed 2D profile along a planar polyline with mitered corners.

    Profile point (a, b): a is the offset within the path plane, perpendicular to the path
    (direction plane_normal x tangent, flipped by side); b is the offset along plane_normal.
    """
    pts = [Vector(p) for p in path]
    nrm = Vector(plane_normal).normalized()
    n = len(pts)
    nseg = n if closed else n - 1
    perps = [nrm.cross((pts[(i + 1) % n] - pts[i]).normalized()).normalized() * side for i in range(nseg)]

    miters = []
    for i in range(n):
        if closed:
            pa, pb = perps[i - 1], perps[i % nseg]
        else:
            pa = perps[max(i - 1, 0)]
            pb = perps[min(i, nseg - 1)]
        m = (pa + pb).normalized()
        miters.append(m / max(m.dot(pa), 1e-4))

    bm = bmesh.new()
    rings = [[bm.verts.new(pts[i] + miters[i] * a + nrm * b) for a, b in prof] for i in range(n)]
    k = len(prof)
    for i in range(nseg):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for j in range(k):
            bm.faces.new((r0[j], r0[(j + 1) % k], r1[(j + 1) % k], r1[j]))
    if not closed:
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[-1])))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, material, collection, smooth_angle=smooth_angle)


def sweep_rect(name, frame, d, s0, s1, z0, z1, prof, material, collection):
    """Moulding frame on a plane parallel to a wall, profile pointing inward."""
    path = [frame.world(s0, d, z0), frame.world(s1, d, z0), frame.world(s1, d, z1), frame.world(s0, d, z1)]
    center = frame.world((s0 + s1) / 2, d, (z0 + z1) / 2)
    first_perp = frame.nrm.cross((path[1] - path[0]).normalized())
    side = 1.0 if first_perp.dot(center - path[0]) > 0 else -1.0
    return sweep(name, path, frame.nrm, prof, material, collection, side=side, closed=True)


def raised_panel(name, frame, d, s0, s1, z0, z1, inset, rise, material, collection):
    """Raised door panel: a flat field lifted by `rise` with sloped margins of width `inset`."""
    bm = bmesh.new()
    base = [frame.world(s, d, z) for s, z in ((s0, z0), (s1, z0), (s1, z1), (s0, z1))]
    top = [frame.world(s, d + rise, z) for s, z in
           ((s0 + inset, z0 + inset), (s1 - inset, z0 + inset), (s1 - inset, z1 - inset), (s0 + inset, z1 - inset))]
    vb = [bm.verts.new(p) for p in base]
    vt = [bm.verts.new(p) for p in top]
    bm.faces.new(vb)
    bm.faces.new(vt)
    for i in range(4):
        bm.faces.new((vb[i], vb[(i + 1) % 4], vt[(i + 1) % 4], vt[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return mesh_object(name, bm, material, collection)


def wall_solid(name, frame, height, thickness, openings, material, collection, extend=0.0):
    """Wall slab behind the interior face, with rectangular holes (s0, s1, z0, z1)."""
    s_cuts = sorted({-extend, frame.length + extend, *(o[0] for o in openings), *(o[1] for o in openings)})
    z_cuts = sorted({0.0, height, *(o[2] for o in openings), *(o[3] for o in openings)})
    bm = bmesh.new()
    grid = [[bm.verts.new(frame.world(s, 0.0, z)) for z in z_cuts] for s in s_cuts]
    for i in range(len(s_cuts) - 1):
        for j in range(len(z_cuts) - 1):
            sc = (s_cuts[i] + s_cuts[i + 1]) / 2
            zc = (z_cuts[j] + z_cuts[j + 1]) / 2
            if any(o[0] < sc < o[1] and o[2] < zc < o[3] for o in openings):
                continue
            # Counter-clockwise in (u, z), so the face normal points into the room.
            bm.faces.new((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]))
    obj = mesh_object(name, bm, material, collection)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = -1.0
    mod.use_even_offset = True
    mod.use_rim = True
    return obj
