"""Built-in furniture placed against walls."""

import math
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from . import geo, materials, model3ds

PANEL_T = 0.016      # carcass board thickness
TOP_BAND = 0.07      # front band hiding the top rail
DOOR_T = 0.04        # sliding door thickness (profile depth)
TRACK_GAP = 0.006    # clearance between the two door tracks
PROFILE_W = 0.022    # visible width of the vertical handle profiles
RAIL_H = 0.03        # height of the horizontal door profiles


class SlidingWardrobe:
    """Шкаф-купе: carcass sides, top band, bottom rail and framed sliding doors on two tracks."""

    def __init__(self, cfg, frames, neighbors, room_height):
        self.cfg = cfg
        self.f = frames[cfg["wall"]]
        prev_wall, next_wall = neighbors or (None, None)
        length, wall_len = cfg["length"], self.f.length
        self.depth = cfg["depth"]
        self.h = room_height if cfg["height"] == "ceiling" else cfg["height"]
        self.room_h = room_height

        # Which wall the wardrobe is pushed against at its end (a corner), if any.
        self.spans = {}
        if cfg["span"] is not None:
            self.s0, self.s1 = self.f.span(None, cfg)
        elif cfg["anchor"] == next_wall:
            self.s0, self.s1 = wall_len - length, wall_len
            self.spans[next_wall] = [(0.0, self.depth)]
        elif cfg["anchor"] == prev_wall:
            self.s0, self.s1 = 0.0, length
            prev_len = frames[prev_wall].length
            self.spans[prev_wall] = [(prev_len - self.depth, prev_len)]
        else:
            center = wall_len / 2 + cfg["offset"]
            self.s0, self.s1 = center - length / 2, center + length / 2
        self.spans.setdefault(cfg["wall"], []).append((self.s0, self.s1))

    @property
    def footprint_rect(self):
        return geo.rect(self.f.world(self.s0, 0.0, 0.0), self.f.world(self.s1, self.depth, 0.0))

    def build(self, collection):
        cfg, f, d, h = self.cfg, self.f, self.depth, self.h
        self.col = collection
        self.body = materials.paint("Wardrobe Body", cfg["color"], 0.4)
        slim = cfg["profile"] == "slim"  # thin profiles in the body color, almost frameless doors
        self.metal = self.body if slim else materials.metal("Wardrobe Profile", cfg["profile"])
        self.pw, self.rh = (0.008, 0.012) if slim else (PROFILE_W, RAIL_H)
        self.mirror = materials.mirror("Wardrobe Mirror")
        self.grip = materials.metal("Wardrobe Handles", cfg["handles"]) if cfg.get("handles") else None
        s0, s1 = self.s0, self.s1
        self._box("Wardrobe Side A", s0, 0.0, 0.0, s0 + PANEL_T, d, h, bevel=0.0015)
        self._box("Wardrobe Side B", s1 - PANEL_T, 0.0, 0.0, s1, d, h, bevel=0.0015)
        is0, is1 = s0 + PANEL_T, s1 - PANEL_T
        self._box("Wardrobe Top", is0, 0.0, h - PANEL_T, is1, d - 0.1, h, bevel=0.0)
        self._box("Wardrobe Top Band", is0, d - 0.1, h - TOP_BAND, is1, d, h, bevel=0.0015)
        self._box("Wardrobe Bottom Rail", is0, d - 0.1, 0.0, is1, d - 0.01, 0.008, mat=self.metal, bevel=0.001)
        if cfg.get("filler") and self.room_h - h > 0.005:  # filler panel from the top up to the ceiling
            self._box("Wardrobe Filler", s0, 0.0, h, s1, d, self.room_h - 0.004, bevel=0.001)

        n = cfg["doors"]
        door_w = (is1 - is0 + (n - 1) * self.pw) / n
        z0, z1 = 0.012, h - TOP_BAND - 0.003
        fronts = cfg.get("fronts") or ["panel"] * n
        for i in range(n):
            a = is0 + i * (door_w - self.pw)
            # Doors alternate between the back and the front track and overlap by one profile.
            front = d - 0.004 - (0.0 if i % 2 else DOOR_T + TRACK_GAP)
            self._door(i + 1, n, fronts[i], a, a + door_w, front - DOOR_T, front, z0, z1)

    def _box(self, name, s0, d0, z0, s1, d1, z1, mat=None, bevel=0.002):
        w = self.f.world
        return geo.box(name, w(s0, d0, z0), w(s1, d1, z1), mat or self.body, self.col, bevel)

    def _door(self, i, n, kind, a, b, back, front, z0, z1):
        """Sliding door: edge profiles and rails around a panel, mirror or fluted (ribbed) infill."""
        tag, pw, rh, w = f"Wardrobe Door {i}", self.pw, self.rh, self.f.world
        self._box(f"{tag} Profile L", a, back, z0, a + pw, front, z1, mat=self.metal, bevel=0.002)
        self._box(f"{tag} Profile R", b - pw, back, z0, b, front, z1, mat=self.metal, bevel=0.002)
        self._box(f"{tag} Rail Bottom", a + pw, back + 0.005, z0, b - pw, front - 0.008, z0 + rh, mat=self.metal)
        self._box(f"{tag} Rail Top", a + pw, back + 0.005, z1 - rh, b - pw, front - 0.008, z1, mat=self.metal)
        ia, ib, iz0, iz1 = a + pw - 0.002, b - pw + 0.002, z0 + rh - 0.002, z1 - rh + 0.002
        if kind == "mirror":
            self._box(f"{tag} Backer", ia, back + 0.004, iz0, ib, front - 0.008, iz1, bevel=0.0)
            self._box(f"{tag} Mirror", ia, front - 0.008, iz0, ib, front - 0.003, iz1, mat=self.mirror, bevel=0.0)
        elif kind == "fluted":
            self._box(f"{tag} Backer", ia, back + 0.004, iz0, ib, front - 0.012, iz1, bevel=0.0)
            side = 1.0 if self.f.nrm.cross(geo.Z).dot(self.f.u) > 0 else -1.0  # profile runs across the door
            geo.sweep(f"{tag} Flutes", [w(ia, front - 0.012, iz0), w(ia, front - 0.012, iz1)], self.f.nrm,
                      fluted_profile(ib - ia), self.body, self.col, side=side, smooth_angle=60)
        else:
            mid = (back + front) / 2
            self._box(f"{tag} Panel", ia, mid - 0.005, iz0, ib, mid + 0.005, iz1, bevel=0.0)
        if self.grip is not None and kind != "fluted" and i in (1, n):
            # Vertical bar handle on the outer edge of the end doors.
            s = a + 0.035 if i == 1 else b - 0.035
            self._box(f"{tag} Handle", s - 0.006, front + 0.014, 0.95, s + 0.006, front + 0.03, 1.4, mat=self.grip,
                      bevel=0.003)
            for zp in (1.0, 1.35):
                self._box(f"{tag} Handle Post", s - 0.004, front - 0.003, zp - 0.006, s + 0.004, front + 0.015,
                          zp + 0.006, mat=self.grip, bevel=0.0)


def fluted_profile(width, pitch=0.016, height=0.006):
    """Ribbed (fluted) panel cross-section: rounded ribs side by side; a = across, b = out of the door."""
    n = max(1, round(width / pitch))
    pitch = width / n
    pts = [(0.0, 0.0)]
    for k in range(n):
        for j in range(9):
            tt = j / 8
            pts.append((k * pitch + tt * pitch, height * math.sin(math.pi * tt) ** 0.5))
    pts.append((width, 0.0))
    return geo.profile(*pts)


class WallCabinet:
    """Wall-hung cabinet (подвесная тумба) with stacked handleless drawer fronts."""

    def __init__(self, cfg, frames, neighbors, room_height):
        self.cfg = cfg
        self.f = frames[cfg["wall"]]
        self.s0, self.s1 = self.f.span(cfg["width"], cfg)
        self.spans = {}  # off the floor: the baseboard runs underneath
        self.footprint_rect = None

    def build(self, collection):
        cfg, w = self.cfg, self.f.world
        body = materials.paint("Cabinet Body", cfg["color"], 0.4)
        s0, s1 = self.s0, self.s1
        d, h, z0 = cfg["depth"], cfg["height"], cfg["elevation"]
        front_t, gap = 0.018, 0.003
        if cfg.get("open_top"):  # panels without a top: a basin's bowl hangs down into it
            t = 0.016
            for name, a, b in (("Side L", s0, s0 + t), ("Side R", s1 - t, s1)):
                geo.box(f"Cabinet {name}", w(a, 0.0, z0), w(b, d - front_t, z0 + h), body, collection, 0.001)
            geo.box("Cabinet Bottom", w(s0 + t, 0.0, z0), w(s1 - t, d - front_t, z0 + t), body, collection)
            geo.box("Cabinet Back", w(s0 + t, 0.0, z0 + t), w(s1 - t, t, z0 + h), body, collection)
        else:
            geo.box("Cabinet Carcass", w(s0, 0.0, z0), w(s1, d - front_t, z0 + h), body, collection, 0.0015)
        n, cols = cfg["drawers"], cfg["columns"]
        fh = (h - gap * (n - 1)) / n
        cw = (s1 - s0) / cols
        for i in range(n):
            za = z0 + i * (fh + gap)
            for j in range(cols):
                a = s0 + j * cw
                geo.box(f"Cabinet Front {i + 1}.{j + 1}", w(a + 0.0015, d - front_t, za),
                        w(a + cw - 0.0015, d, za + fh), body, collection, 0.002)


def mirror_frame_profile(width):
    """a = inward from the outer edge, b = projection from the wall."""
    return geo.profile(
        (0.0, 0.0), (0.0, 0.014),
        geo.arc((0.006, 0.014), 0.006, 180, 90, 6),
        (width - 0.003, 0.02), (width, 0.012), (width, 0.0),
    )


class WallMirror:
    """Wall mirror, optionally in a thin metal or painted frame."""

    def __init__(self, cfg, frames, neighbors, room_height):
        self.cfg = cfg
        self.f = frames[cfg["wall"]]
        self.s0, self.s1 = self.f.span(cfg["width"], cfg)
        self.spans = {}
        self.footprint_rect = None

    def build(self, collection):
        cfg, f = self.cfg, self.f
        s0, s1 = self.s0, self.s1
        z0, z1 = cfg["elevation"], cfg["elevation"] + cfg["height"]
        fw = 0.0 if cfg["frame"] == "none" else cfg["frame_width"]
        inset = max(fw - 0.003, 0.0)
        geo.box("Mirror Glass", f.world(s0 + inset, 0.004, z0 + inset), f.world(s1 - inset, 0.01, z1 - inset),
                materials.mirror("Mirror"), collection)
        if fw:
            frame_mat = (materials.metal("Mirror Frame", cfg["frame"]) if cfg["frame"] in materials.HARDWARE
                         else materials.paint("Mirror Frame", cfg["frame"]))
            geo.sweep_rect("Mirror Frame", f, 0.0, s0, s1, z0, z1, mirror_frame_profile(fw), frame_mat, collection)
        bl = cfg.get("backlight")
        if bl:  # built-in light: a frosted band around the glass, glowing; a switch group of its own
            glow = materials.emitter("Mirror Backlight", bl.get("temperature", 4000), bl.get("strength", 10.0))
            b, m = bl.get("band", 0.025), bl.get("inset", 0.03)
            a0, a1, c0, c1 = s0 + inset + m, s1 - inset - m, z0 + inset + m, z1 - inset - m
            for k, (p, q) in enumerate((((a0, c0), (a1, c0 + b)), ((a0, c1 - b), (a1, c1)),
                                        ((a0, c0 + b), (a0 + b, c1 - b)), ((a1 - b, c0 + b), (a1, c1 - b)))):
                band = geo.box(f"Mirror Backlight {k + 1}", f.world(p[0], 0.0101, p[1]), f.world(q[0], 0.0104, q[1]),
                               glow, collection)
                if bl.get("group"):
                    band["light_group"] = bl["group"]


class Pouf:
    """Upholstered ottoman on short metal legs, standing just off a wall."""

    def __init__(self, cfg, frames, neighbors, room_height):
        self.cfg = cfg
        self.f = frames[cfg["wall"]]
        self.s0, self.s1 = self.f.span(cfg["width"], cfg)
        self.spans = {}
        self.footprint_rect = None  # clear of the wall: the baseboard runs behind it

    def build(self, collection):
        cfg, w = self.cfg, self.f.world
        d0, d1, h = cfg["gap"], cfg["gap"] + cfg["depth"], cfg["height"]
        legs_h = 0.05
        geo.box("Pouf Body", w(self.s0, d0, legs_h), w(self.s1, d1, h), materials.fabric("Pouf Fabric", cfg["color"]),
                collection, bevel=0.035, bevel_segments=8)
        metal = materials.metal("Pouf Legs", cfg["legs"])
        inset = 0.04
        for s in (self.s0 + inset, self.s1 - inset):
            for d in (d0 + inset, d1 - inset):
                geo.cylinder("Pouf Leg", w(s, d, legs_h / 2 + 0.002), geo.Z, 0.012, legs_h, metal, collection, 16)


class _WallItem:
    """Shared placement: a `span` along a wall; nothing blocks the baseboard."""

    def __init__(self, cfg, frames, neighbors, room_height):
        self.cfg = cfg
        self.f = frames[cfg["wall"]]
        self.h = room_height
        if cfg.get("span") is not None or cfg.get("width") is not None:
            self.s0, self.s1 = self.f.span(cfg.get("width"), cfg)
        self.spans = {}
        self.footprint_rect = None


class Sofa(_WallItem):
    """Box sofa: base, arms, back, loose seat and back cushions on short legs."""

    def build(self, col):
        cfg, w = self.cfg, self.f.world
        fab = materials.fabric("Sofa Fabric", cfg["color"])
        legs = materials.matte("Sofa Legs", "#2A2623", 0.5)
        s0, s1 = self.s0, self.s1
        d0, d1 = cfg["gap"], cfg["gap"] + cfg["depth"]
        arm, seat, back, arm_h, leg = cfg["arm_width"], cfg["seat_height"], cfg["back_height"], cfg["arm_height"], 0.08

        def soft(name, a, b, c, d, e, f, bevel):
            geo.box(name, w(a, b, c), w(d, e, f), fab, col, bevel=bevel, bevel_segments=6)

        soft("Sofa Base", s0 + arm, d0 + 0.02, leg, s1 - arm, d1 - 0.02, seat - 0.12, 0.02)
        soft("Sofa Arm L", s0, d0, leg, s0 + arm, d1, arm_h, 0.04)
        soft("Sofa Arm R", s1 - arm, d0, leg, s1, d1, arm_h, 0.04)
        soft("Sofa Back", s0 + arm, d0, seat - 0.12, s1 - arm, d0 + 0.2, back, 0.04)
        n = cfg["cushions"]
        cw = (s1 - s0 - 2 * arm) / n
        for i in range(n):
            a = s0 + arm + i * cw
            soft(f"Sofa Seat {i + 1}", a + 0.004, d0 + 0.2, seat - 0.12, a + cw - 0.004, d1 - 0.01, seat, 0.045)
            soft(f"Sofa Cushion {i + 1}", a + 0.004, d0 + 0.17, seat, a + cw - 0.004, d0 + 0.38, back - 0.03, 0.06)
        for s in (s0 + 0.06, s1 - 0.06):
            for d in (d0 + 0.06, d1 - 0.06):
                geo.cylinder("Sofa Leg", w(s, d, leg / 2), geo.Z, 0.02, leg, legs, col, 16)


class Tv(_WallItem):
    """Wall-mounted flat TV."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        z0, z1 = cfg["elevation"], cfg["elevation"] + cfg["height"]
        body = materials.matte("TV Body", "#141414", 0.4)
        screen = materials.paint("TV Screen", "#050505", 0.04)
        geo.frame_box("TV", f, self.s0, 0.012, z0, self.s1, 0.012 + cfg["depth"], z1, body, col, bevel=0.002)
        bezel = 0.006
        geo.frame_box("TV Screen", f, self.s0 + bezel, 0.012 + cfg["depth"], z0 + bezel, self.s1 - bezel,
                      0.0125 + cfg["depth"], z1 - bezel, screen, col)


class Intercom(_WallItem):
    """Video intercom panel: white body with a dark screen."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        z0, z1 = cfg["elevation"], cfg["elevation"] + cfg["height"]
        geo.frame_box("Intercom", f, self.s0, 0.0, z0, self.s1, cfg["depth"], z1,
                      materials.matte("Intercom Body", cfg["color"], 0.3), col, bevel=0.003)
        m = 0.02
        geo.frame_box("Intercom Screen", f, self.s0 + m, cfg["depth"], z0 + m, self.s1 - m * 1.6,
                      cfg["depth"] + 0.0006, z1 - m, materials.paint("Intercom Screen", "#0A0A0B", 0.05), col)


def _wave_sheet(name, frame, s0, s1, d_mid, amp, period, z0, z1, material, col):
    """Gathered fabric: a sine-pleated sheet between s0 and s1."""
    n = max(12, int((s1 - s0) / period * 10))
    bm = bmesh.new()
    cols = []
    for i in range(n + 1):
        s = s0 + (s1 - s0) * i / n
        d = d_mid + amp * math.sin(2 * math.pi * (s - s0) / period)
        cols.append((bm.verts.new(frame.world(s, d, z0)), bm.verts.new(frame.world(s, d, z1))))
    for i in range(n):
        bm.faces.new((cols[i][0], cols[i + 1][0], cols[i + 1][1], cols[i][1]))
    obj = geo.mesh_object(name, bm, material, col, smooth_angle=89)
    mod = obj.modifiers.new("Thickness", "SOLIDIFY")
    mod.thickness = 0.003
    return obj


class Curtains(_WallItem):
    """Ceiling cornice with an LED strip, curtains and tulle gathered in stacks at given spans."""

    def build(self, col):
        cfg, f, h = self.cfg, self.f, self.h
        white = materials.matte("Cornice", "#F4F4F2", 0.4)
        if cfg["cornice"] in ("concealed", "slot"):
            # Track hidden in a recess of the ceiling; an LED strip in the recess washes the curtains.
            # concealed: an open niche against the wall; slot: the ceiling runs to the wall, the recess is a slot.
            if cfg["cornice"] == "slot":  # tulle and curtain tracks from the window side, LED on the room side
                d0, d1 = cfg["slot_offset"], cfg["slot_offset"] + cfg["slot_width"]
                tulle_d, curtain_d = cfg.get("tracks") or (d0 + 0.025, d0 + 0.065)
            else:
                d0, d1 = -0.01, cfg["niche_width"]
                tulle_d, curtain_d = d1 - 0.055, d1 - 0.02
            rise = cfg["niche_depth"]
            ceiling = bpy.data.objects.get("Ceiling")
            if ceiling is not None:
                cutter = geo.frame_box("Cutter Curtain Niche", f, -0.01, d0, h - 0.01, f.length + 0.01, d1,
                                       h + rise, white, col)
                cutter.hide_render = True
                cutter.display_type = "WIRE"
                mod = ceiling.modifiers.new("Curtain Niche", "BOOLEAN")
                mod.operation = "DIFFERENCE"
                mod.object = cutter
                mod.solver = "EXACT"
            if cfg.get("led", True):
                led = materials.emitter("Cornice LED", 3000, cfg.get("led_strength", 12.0))
                geo.frame_box("Cornice LED", f, 0.0, d1 - 0.035, h + rise - 0.003, f.length, d1 - 0.015,
                              h + rise - 0.002, led, col)["light_group"] = "cornice"
                if cfg.get("led_power"):  # the strip's real output, W (Blender) per meter, shining down the curtains
                    light = bpy.data.lights.new("Cornice LED", "AREA")
                    light.shape = "RECTANGLE"
                    light.size, light.size_y = f.length, 0.02
                    light.energy = cfg["led_power"] * f.length
                    light.use_temperature = True
                    light.temperature = 3000
                    obj = bpy.data.objects.new("Cornice LED", light)
                    obj.location = f.world(f.length / 2, d1 - 0.025, h + rise - 0.004)
                    obj.rotation_euler = (0.0, 0.0, math.atan2(f.u.y, f.u.x))
                    obj["light_group"] = "cornice"
                    col.objects.link(obj)
            top = h + rise - 0.01
        else:
            geo.frame_box("Cornice", f, 0.0, 0.02, h - 0.08, f.length, 0.14, h - 0.03, white, col, bevel=0.003)
            led = materials.emitter("Cornice LED", 3000, 6.0)
            geo.frame_box("Cornice LED", f, 0.0, 0.04, h - 0.03, f.length, 0.12, h - 0.029, led,
                          col)["light_group"] = "cornice"
            top = h - 0.085
            tulle_d, curtain_d = 0.05, 0.11
        curtain = materials.fabric("Curtain", cfg["color"])
        tulle = materials.sheer("Tulle", cfg["tulle_color"])
        bottom = cfg.get("bottom", 0.01)  # a bath curtain ends inside the tub
        if cfg.get("tulle") == "closed":  # drawn across the whole wall
            _wave_sheet("Tulle", f, 0.03, f.length - 0.03, tulle_d, 0.01, 0.07, 0.01, top, tulle, col)
        for k, stack in enumerate(cfg["stacks"]):
            s0, s1 = f.span(None, {"span": stack})
            if cfg.get("tulle") not in ("closed", "none"):
                _wave_sheet(f"Tulle {k + 1}", f, s0, s1, tulle_d, 0.02, 0.06, 0.01, top, tulle, col)
            _wave_sheet(f"Curtain {k + 1}", f, s0, s1, curtain_d, 0.015, 0.1, bottom, top, curtain, col)


class NicheCabinet(_WallItem):
    """Floor-to-ceiling cabinet filling a niche: closed sections with flat doors, open sections between."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        body = materials.paint("Niche Cabinet", cfg["color"], 0.4)
        s0, s1, depth, t = self.s0, self.s1, cfg["depth"], 0.016
        for sec in cfg["sections"]:
            z0, z1 = (self.h if z == "ceiling" else z for z in sec["z"])
            if sec.get("open"):
                geo.frame_box("Niche Side", f, s0, 0.0, z0, s0 + t, depth, z1, body, col, bevel=0.001)
                geo.frame_box("Niche Side", f, s1 - t, 0.0, z0, s1, depth, z1, body, col, bevel=0.001)
                geo.frame_box("Niche Back", f, s0 + t, 0.0, z0, s1 - t, 0.008, z1, body, col)
                continue
            geo.frame_box("Niche Carcass", f, s0, 0.0, z0, s1, depth - 0.018, z1, body, col)
            n = sec.get("doors", 1)
            step = (s1 - s0) / n
            for i in range(n):
                a = s0 + i * step
                geo.frame_box("Niche Door", f, a + 0.0015, depth - 0.018, z0 + 0.0015, a + step - 0.0015, depth,
                              z1 - 0.0015, body, col, bevel=0.0015)


class Radiator(_WallItem):
    """Sectional bimetal radiator on brackets, with a bottom connection: two pipes from the wall
    into a valve block under one end (`connection_at`, a plan coordinate)."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        paint = materials.paint("Radiator", cfg["color"], 0.3)
        chrome = materials.metal("Radiator Valve", "chrome")
        d0, d1 = cfg["gap"], cfg["gap"] + cfg["depth"]
        z0, z1 = cfg["elevation"], cfg["elevation"] + cfg["height"]
        n = cfg["sections"]
        step = (self.s1 - self.s0) / n
        for i in range(n):
            a = self.s0 + i * step
            geo.frame_box("Radiator Section", f, a + 0.0012, d0 + 0.012, z0, a + step - 0.0012, d1, z1, paint, col,
                          bevel=0.008, bevel_segments=4)
        for zc in (z0 + 0.035, z1 - 0.035):  # collectors joining the sections
            geo.frame_box("Radiator Collector", f, self.s0 + 0.004, d0 + 0.02, zc - 0.018, self.s1 - 0.004, d0 + 0.06,
                          zc + 0.018, paint, col)
        end = f.s_at(cfg["connection_at"])
        inward = 1.0 if end <= (self.s0 + self.s1) / 2 else -1.0
        sv = end + inward * 0.06
        geo.frame_box("Radiator Valve Block", f, sv - 0.045, d0 + 0.02, z0 - 0.045, sv + 0.045, d0 + 0.065, z0 + 0.002,
                      chrome, col, bevel=0.004)
        for ds in (-0.025, 0.025):
            geo.cylinder("Radiator Pipe", f.world(sv + ds, (d0 + 0.04) / 2, z0 - 0.03), f.nrm, 0.008, d0 + 0.04, chrome,
                         col, 16)


def grooved_profile(width, pitch=0.013, groove=0.004, depth=0.004):
    """Milled fluting (рифление): a flat face with round-bottomed vertical grooves; a = across, b = out."""
    n = max(1, round(width / pitch))
    pitch = width / n
    pts = [(0.0, 0.0), (0.0, depth)]
    for k in range(1, n):
        x = k * pitch
        pts += [(x - groove / 2, depth)]
        pts += [(x + groove / 2 * math.cos(math.pi * j / 6), depth - depth * 0.85 * math.sin(math.pi * j / 6))
                for j in range(6, -1, -1)]
    pts += [(width, depth), (width, 0.0)]
    return geo.profile(*pts)


def _flutes(name, f, s0, s1, d, z0, z1, material, col, pitch=0.032, height=0.005):
    """Reeded strip on a front between s0 and s1 (as on «Санторини»): rounded vertical reeds ~3 cm apart,
    5 mm proud of the face at d."""
    side = 1.0 if f.nrm.cross(geo.Z).dot(f.u) > 0 else -1.0  # profile runs along +s
    geo.sweep(name, [f.world(s0, d, z0), f.world(s0, d, z1)], f.nrm, fluted_profile(s1 - s0, pitch, height),
              material, col, side=side, smooth_angle=60)


def _notch(obj, f, s, d, z, radius, cutters):
    """Half-moon finger pull: a round cut through the top edge of a front."""
    cutter = geo.cylinder(f"{obj.name} Pull Cutter", f.world(s, d, z), f.nrm, radius, 0.06, None, cutters, 48)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    mod = obj.modifiers.new("Pull", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"


def _cutters():
    col = bpy.data.collections.get("Furniture Cutters")
    if col is None:
        col = bpy.data.collections.new("Furniture Cutters")
        bpy.context.scene.collection.children.link(col)
        col.hide_render = True
    return col


class SwingWardrobe(_WallItem):
    """One arm of a hinged-door wardrobe (Вереск «Санторини»): carcass on a recessed plinth, flat fronts,
    a ribbed strip on the outer door, round knobs split between the two doors, a filler up to the ceiling."""

    @property
    def footprint_rect(self):
        return geo.rect(self.f.world(self.s0, 0.0, 0.0), self.f.world(self.s1, self.cfg["depth"], 0.0))

    @footprint_rect.setter
    def footprint_rect(self, _):
        pass

    def build(self, col):
        cfg, f = self.cfg, self.f
        body = materials.paint("Wardrobe Body", cfg["color"], 0.6)  # soft matte film
        d, top, p, t = cfg["depth"], cfg["height"], cfg["plinth"], 0.019
        s0, s1 = self.s0, self.s1
        geo.frame_box("Wardrobe Carcass", f, s0, 0.0, p, s1, d - t, top, body, col, bevel=0.001)
        geo.frame_box("Wardrobe Plinth", f, s0, 0.0, 0.0, s1, d - 0.03, p, body, col)
        if cfg["filler"]:
            geo.frame_box("Wardrobe Filler", f, s0, 0.0, top, s1, d, self.h - 0.004, body, col, bevel=0.001)
        ds0, ds1 = f.span(None, {"span": cfg["doors_span"]}) if cfg["doors_span"] else (s0, s1)
        n, gap = cfg["doors"], 0.003
        step = (ds1 - ds0) / n
        z0, z1 = p + gap, top - gap
        if cfg.get("tiers"):   # «Дарио»: each column split in height, [[z0, z1, "flat" | "fluted"], ...]
            front = materials.paint("Wardrobe Fronts", cfg.get("front_color") or cfg["color"], 0.6)
            grip = materials.metal("Wardrobe Handles", cfg.get("handle_finish", "black"))
            for i in range(n):
                a, b = ds0 + i * step + gap / 2, ds0 + (i + 1) * step - gap / 2
                for k, (tz0, tz1, kind) in enumerate(cfg["tiers"]):
                    tag = f"Wardrobe Door {i + 1}.{k + 1}"
                    geo.frame_box(tag, f, a, d - t, tz0 + gap / 2, b, d, tz1 - gap / 2, front, col, bevel=0.0015)
                    if kind == "fluted":
                        _flutes(f"{tag} Flutes", f, a + 0.004, b - 0.004, d, tz0 + 0.004, tz1 - 0.004, front, col,
                                pitch=0.012, height=0.003)
                    elif cfg.get("handles") == "hbar" and tz0 <= cfg["hbar_z"] <= tz1:   # short horizontal bar
                        m, hz = (a + b) / 2, cfg["hbar_z"]
                        geo.frame_box(f"{tag} Handle", f, m - 0.075, d + 0.018, hz - 0.006, m + 0.075, d + 0.03,
                                      hz + 0.006, grip, col, bevel=0.003)
                        for sp in (m - 0.06, m + 0.06):
                            geo.frame_box(f"{tag} Handle Post", f, sp - 0.005, d, hz - 0.004, sp + 0.005, d + 0.019,
                                          hz + 0.004, grip, col)
            return
        for i in range(n):
            a, b = ds0 + i * step + gap / 2, ds0 + (i + 1) * step - gap / 2
            geo.frame_box(f"Wardrobe Door {i + 1}", f, a, d - t, z0, b, d, z1, body, col, bevel=0.0015)
            fw = cfg["flute_width"]
            if cfg["fluted"] == "all":       # «Катания»: fine fluting over the whole door
                _flutes(f"Wardrobe Door {i + 1} Flutes", f, a + 0.006, b - 0.006, d, z0 + 0.006, z1 - 0.006, body,
                        col, pitch=0.012, height=0.003)
            elif (cfg["fluted"] == "start" and i == 0) or (cfg["fluted"] == "end" and i == n - 1):
                fa = a + 0.012 if i == 0 else b - 0.012 - fw
                _flutes(f"Wardrobe Door {i + 1} Flutes", f, fa, fa + fw, d, z0 + 0.012, z1 - 0.012, body, col)
            if cfg.get("handles") == "bar" and i > 0:   # long vertical bar at the left edge of the doors after the first
                grip = materials.metal("Wardrobe Bar Handles", cfg.get("handle_finish", "black"))
                hs = a + 0.03
                hz0, hz1 = cfg.get("handle_z", (0.25, 1.15))
                proud = 0.004 if cfg["fluted"] == "all" else 0.0
                geo.frame_box(f"Wardrobe Door {i + 1} Handle", f, hs - 0.006, d + proud + 0.018, hz0, hs + 0.006,
                              d + proud + 0.03, hz1, grip, col, bevel=0.003)
                for zp in (hz0 + 0.05, hz1 - 0.05):
                    geo.frame_box(f"Wardrobe Door {i + 1} Handle Post", f, hs - 0.004, d, zp - 0.006, hs + 0.004,
                                  d + proud + 0.019, zp + 0.006, grip, col)
        if cfg["knobs"] and n == 2:  # a round knob over the meeting edge, half on each door
            metal = materials.metal("Wardrobe Knobs", cfg["knobs"])
            geo.cylinder("Wardrobe Knob", f.world(ds0 + step, d + 0.01, cfg["knob_z"]), f.nrm, 0.028, 0.02, metal, col,
                         48)


class DrawerUnit(_WallItem):
    """Drawer unit (тумба «Санторини»): standing on a recessed plinth, or wall-hung; top over the fronts,
    a ribbed strip on the fronts, a half-moon finger pull cut into the top edge of each front."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        body = materials.paint("Drawer Unit Body", cfg["color"], 0.6)
        s0, s1, t = self.s0, self.s1, 0.019
        d0, d1 = cfg["gap"], cfg["gap"] + cfg["depth"]
        z0, z1 = cfg["elevation"], cfg["elevation"] + cfg["height"]
        standing = z0 < 0.001
        base = cfg["plinth"] if standing else z0
        if standing:
            geo.frame_box("Drawer Unit Plinth", f, s0 + 0.01, d0 + 0.02, 0.0, s1 - 0.01, d1 - 0.05, base, body, col)
        geo.frame_box("Drawer Unit Carcass", f, s0, d0, base, s1, d1 - t, z1 - 0.016, body, col, bevel=0.001)
        geo.frame_box("Drawer Unit Top", f, s0, d0, z1 - 0.016, s1, d1, z1, body, col, bevel=0.0015)
        gap = 0.003
        zf0 = base - 0.03 if standing else z0           # the bottom front covers the plinth by 3 cm
        zf1 = z1 - 0.016 - gap
        rows, cols = cfg["drawers"], cfg["columns"]
        fh, cw = (zf1 - zf0 - gap * (rows - 1)) / rows, (s1 - s0) / cols
        cutters, fw = _cutters(), cfg["flute_width"]
        for r in range(rows):
            za = zf0 + r * (fh + gap)
            for c in range(cols):
                a, b = s0 + c * cw + gap / 2, s0 + (c + 1) * cw - gap / 2
                front = geo.frame_box(f"Drawer Front {r + 1}.{c + 1}", f, a, d1 - t, za, b, d1, za + fh, body, col,
                                      bevel=0.0015)
                side = {"left": "left", "right": "right"}.get(cfg["fluted"])
                if cfg["fluted"] == "outer":
                    side = "left" if c == 0 else "right" if c == cols - 1 else None
                if side:
                    fa = a + 0.015 if side == "left" else b - 0.015 - fw
                    _flutes(f"Drawer Front {r + 1}.{c + 1} Flutes", f, fa, fa + fw, d1, za + 0.012, za + fh - 0.02,
                            body, col)
                _notch(front, f, (a + b) / 2, d1 - t / 2, za + fh + 0.012, 0.03, cutters)


class Bed(_WallItem):
    """Upholstered bed against a wall: headboard, base on low legs, mattress, duvet, pillows and a throw."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        fab = materials.fabric("Bed Fabric", cfg["color"])
        linen = materials.fabric("Bed Linen", cfg["bedding"])
        throw = materials.fabric("Bed Throw", cfg["throw"])
        legs = materials.matte("Bed Legs", "#2A2623", 0.5)
        s0, s1 = self.s0, self.s1
        d0, d1 = cfg["gap"], cfg["gap"] + cfg["depth"]
        hb_h, hb_t = cfg["headboard"]
        mw, ml, mt = cfg["mattress"]
        fh, leg = cfg["frame_height"], 0.06
        geo.frame_box("Bed Headboard", f, s0, d0, leg, s1, d0 + hb_t, hb_h, fab, col, bevel=0.03, bevel_segments=6)
        geo.frame_box("Bed Base", f, s0, d0 + hb_t, leg, s1, d1, fh, fab, col, bevel=0.02, bevel_segments=6)
        for s in (s0 + 0.05, s1 - 0.05):
            for d in (d0 + hb_t + 0.05, d1 - 0.05):
                geo.cylinder("Bed Leg", f.world(s, d, leg / 2), geo.Z, 0.015, leg, legs, col, 16)
        c = (s0 + s1) / 2
        m0, m1 = c - mw / 2, c + mw / 2
        md0, md1 = d0 + hb_t + 0.005, d0 + hb_t + 0.005 + ml
        top = fh - 0.05 + mt
        geo.frame_box("Bed Mattress", f, m0, md0, fh - 0.05, m1, md1, top, linen, col, bevel=0.04, bevel_segments=6)
        geo.frame_box("Bed Duvet", f, m0 - 0.03, md0 + 0.5, top - 0.2, m1 + 0.03, md1 + 0.03, top + 0.05, linen, col,
                      bevel=0.045, bevel_segments=6)
        geo.frame_box("Bed Duvet Fold", f, m0 - 0.035, md0 + 0.5, top + 0.02, m1 + 0.035, md0 + 0.78, top + 0.075,
                      linen, col, bevel=0.025, bevel_segments=5)
        geo.frame_box("Bed Throw", f, m0 - 0.05, md1 - 0.55, top + 0.045, m1 + 0.05, md1 + 0.05, top + 0.07, throw,
                      col, bevel=0.012, bevel_segments=4)
        for k in (-1, 1):
            pc = c + k * mw / 4
            geo.frame_box("Bed Pillow", f, pc - 0.34, md0 + 0.04, top - 0.01, pc + 0.34, md0 + 0.48, top + 0.15, linen,
                          col, bevel=0.06, bevel_segments=8)


class Chair(_WallItem):
    """Upholstered chair turned to the wall (a vanity or desk in front of it)."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        fab = materials.fabric("Chair Fabric", cfg["color"])
        legs = materials.matte("Chair Legs", cfg["legs"], 0.5)
        s0, s1 = self.s0, self.s1
        d0, d1 = cfg["gap"], cfg["gap"] + cfg["depth"]
        seat, back = cfg["seat_height"], cfg["back_height"]
        geo.frame_box("Chair Seat", f, s0, d0, seat - 0.1, s1, d1, seat, fab, col, bevel=0.03, bevel_segments=6)
        geo.frame_box("Chair Back", f, s0 + 0.01, d1 - 0.09, seat - 0.05, s1 - 0.01, d1, back, fab, col, bevel=0.035,
                      bevel_segments=6)
        for s in (s0 + 0.04, s1 - 0.04):
            for d in (d0 + 0.04, d1 - 0.04):
                geo.cylinder("Chair Leg", f.world(s, d, (seat - 0.1) / 2), geo.Z, 0.014, seat - 0.1, legs, col, 16)


def build_dining(cfg, col):
    """Free-standing dining table at `center` (plan x, y), `size` [length, width] with the length along `axis`,
    and chairs around it: `chairs_per_side` on each long side, `end_chairs` at the short ends."""
    cx, cy = cfg["center"]
    length, width = cfg["size"]
    along = Vector((1.0, 0.0, 0.0)) if cfg.get("axis", "x") == "x" else Vector((0.0, 1.0, 0.0))
    across = geo.Z.cross(along)
    c = Vector((cx, cy, 0.0))
    wood = materials.veneer("Dining Wood", cfg["color"])
    top_z, top_t, leg, apron = cfg["height"], 0.03, 0.05, 0.08
    f = geo.WallFrame("Dining Table", c - along * length / 2 - across * width / 2, along, across, length)
    geo.frame_box("Dining Top", f, 0.0, 0.0, top_z - top_t, length, width, top_z, wood, col, bevel=0.004)
    geo.frame_box("Dining Apron", f, 0.06, 0.06, top_z - top_t - apron, length - 0.06, width - 0.06, top_z - top_t,
                  wood, col)
    for s in (0.05, length - 0.05 - leg):
        for d in (0.05, width - 0.05 - leg):
            geo.frame_box("Dining Leg", f, s, d, 0.0, s + leg, d + leg, top_z - top_t, wood, col, bevel=0.003)
    fab = materials.fabric("Dining Chair Fabric", cfg["chair_color"])
    legs = materials.matte("Dining Chair Legs", cfg["chair_legs"], 0.5)
    seat, back, cw, cd = 0.47, 0.88, 0.45, 0.48
    spots = []  # (center along the table, offset across, facing direction)
    n = cfg["chairs_per_side"]
    for i in range(n):
        s = length * (i + 0.5) / n
        spots += [(s, -0.12 - cd / 2, across), (s, width + 0.12 + cd / 2, -across)]
    for k in range(cfg.get("end_chairs", 0)):
        spots.append((-0.12 - cd / 2, width / 2, along) if k == 0 else (length + 0.12 + cd / 2, width / 2, -along))
    for i, (s, d, facing) in enumerate(spots):
        p = f.world(s, d, 0.0)
        side = geo.Z.cross(facing)  # chair's own left-right axis
        cf = geo.WallFrame(f"Dining Chair {i + 1}", p - side * cw / 2 - facing * cd / 2, side, facing, cw)
        # d grows toward the table: the back is at d = 0, the front edge of the seat at d = cd
        geo.frame_box(f"Dining Chair {i + 1} Seat", cf, 0.0, 0.0, seat - 0.08, cw, cd, seat, fab, col, bevel=0.025,
                      bevel_segments=5)
        geo.frame_box(f"Dining Chair {i + 1} Back", cf, 0.01, 0.0, seat - 0.04, cw - 0.01, 0.07, back, fab, col,
                      bevel=0.03, bevel_segments=5)
        for ls in (0.04, cw - 0.04):
            for ld in (0.04, cd - 0.04):
                geo.cylinder(f"Dining Chair {i + 1} Leg", cf.world(ls, ld, (seat - 0.08) / 2), geo.Z, 0.013,
                             seat - 0.08, legs, col, 16)


class AirConditioner(_WallItem):
    """Split-system indoor unit: white rounded body, air outlet with a louver along the bottom front."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        white = materials.paint("AC Body", "#F4F4F2", 0.3)
        dark = materials.matte("AC Outlet", "#2A2A2A", 0.6)
        z0, z1, d = cfg["elevation"], cfg["elevation"] + cfg["height"], cfg["depth"]
        geo.frame_box("AC Body", f, self.s0, 0.0, z0 + 0.05, self.s1, d, z1, white, col, bevel=0.02, bevel_segments=6)
        geo.frame_box("AC Base", f, self.s0, 0.0, z0, self.s1, d - 0.06, z0 + 0.06, white, col, bevel=0.01)
        geo.frame_box("AC Outlet", f, self.s0 + 0.04, d - 0.075, z0 + 0.012, self.s1 - 0.04, d - 0.03, z0 + 0.05, dark,
                      col)
        geo.frame_box("AC Louver", f, self.s0 + 0.045, d - 0.06, z0 + 0.025, self.s1 - 0.045, d - 0.025, z0 + 0.035,
                      white, col, bevel=0.003)


class Desk(_WallItem):
    """Writing / computer desk against a wall: a top on four square metal legs with a back rail.
    `top`: paint | wood (veneer, grain along the desk); `cutout`: [width, depth] — a smooth body cutout
    in the middle of the front edge."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        if cfg.get("top") == "wood":
            axis = "x" if abs(f.u.x) >= abs(f.u.y) else "y"
            top = materials.veneer("Desk Top", cfg["color"], 0.4, axis=axis)
        else:
            top = materials.paint("Desk Top", cfg["color"], 0.5)
        metal = materials.matte("Desk Legs", cfg["legs"], 0.45)
        s0, s1 = self.s0, self.s1
        d0, d1, h, t = cfg["gap"], cfg["gap"] + cfg["depth"], cfg["height"], 0.03
        cut = cfg.get("cutout")
        if cut:
            cw, cd = cut
            c = (s0 + s1) / 2
            front = [(s, d1 - cd * (math.cos(math.pi * (s - c) / (cw / 2)) + 1) / 2)
                     for s in (c + cw / 2 - cw * k / 32 for k in range(33))]
            outline = [(s0, d0), (s1, d0), (s1, d1)] + front + [(s0, d1)]
            obj = geo.prism("Desk Top", [tuple(f.world(s, d, 0.0))[:2] for s, d in outline], h - t, h, top, col)
            geo.add_bevel(obj, 0.003, 3)
        else:
            geo.frame_box("Desk Top", f, s0, d0, h - t, s1, d1, h, top, col, bevel=0.003)
        for s in (s0 + 0.03, s1 - 0.07):
            for d in (d0 + 0.03, d1 - 0.07):
                geo.frame_box("Desk Leg", f, s, d, 0.0, s + 0.04, d + 0.04, h - t, metal, col, bevel=0.002)
        geo.frame_box("Desk Rail", f, s0 + 0.07, d0 + 0.03, h - t - 0.08, s1 - 0.07, d0 + 0.05, h - t, metal, col)


class OfficeChair(_WallItem):
    """Office chair turned to the wall (a desk in front of it): five-star base on casters, gas lift,
    upholstered seat and back, armrests."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        fab = materials.fabric("Office Chair Fabric", cfg["color"])
        metal = materials.matte("Office Chair Base", "#1E1E1F", 0.35)
        c = (self.s0 + self.s1) / 2
        w = self.s1 - self.s0
        d0 = cfg["gap"]
        dc = d0 + cfg["depth"] / 2
        seat, back = cfg["seat_height"], cfg["back_height"]
        geo.frame_box("Office Chair Seat", f, c - w / 2 + 0.04, d0, seat - 0.08, c + w / 2 - 0.04, d0 + cfg["depth"],
                      seat, fab, col, bevel=0.025, bevel_segments=5)
        d1 = d0 + cfg["depth"]
        geo.frame_box("Office Chair Back", f, c - w / 2 + 0.07, d1 - 0.07, seat + 0.06, c + w / 2 - 0.07, d1 - 0.01,
                      back, fab, col, bevel=0.03, bevel_segments=5)
        geo.frame_box("Office Chair Back Post", f, c - 0.025, d1 - 0.02, seat - 0.06, c + 0.025, d1 + 0.005, seat + 0.1,
                      metal, col)
        for side in (-1, 1):
            s = c + side * (w / 2 - 0.02)
            geo.frame_box("Office Chair Arm Post", f, s - 0.012, dc + 0.02, seat - 0.02, s + 0.012, dc + 0.06,
                          seat + 0.2, metal, col)
            geo.frame_box("Office Chair Arm Pad", f, s - 0.03, dc - 0.1, seat + 0.2, s + 0.03, dc + 0.14, seat + 0.23,
                          metal, col, bevel=0.008)
        geo.cylinder("Office Chair Lift", f.world(c, dc, (seat - 0.08 + 0.1) / 2), geo.Z, 0.025, seat - 0.18, metal,
                     col, 24)
        for k in range(5):
            a = 2 * math.pi * k / 5
            u, v = math.cos(a), math.sin(a)
            star = geo.WallFrame("Office Chair Star", f.world(c, dc, 0.0), f.u * u + f.nrm * v,
                                 geo.Z.cross(f.u * u + f.nrm * v), 0.32)
            geo.frame_box("Office Chair Star Leg", star, 0.0, -0.018, 0.07, 0.32, 0.018, 0.1, metal, col, bevel=0.006)
            geo.cylinder("Office Chair Caster", star.world(0.3, 0.0, 0.03), star.nrm, 0.03, 0.025, metal, col, 20)


def _oriented_box(name, origin, u, v, w, su, sv, sw, material, col, bevel=0.0):
    """Box spanned from `origin` by su·u, sv·v, sw·w (any orthonormal axes, e.g. a tilted laptop lid)."""
    bm = bmesh.new()
    vs = [bm.verts.new(origin + u * a + v * b + w * c) for c in (0, sw) for b in (0, sv) for a in (0, su)]
    for quad in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in quad])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = geo.mesh_object(name, bm, material, col)
    if bevel:
        geo.add_bevel(obj, bevel, 3)
    return obj


class DeskGear(_WallItem):
    """What stands on a desk against a wall (span = the desk): a 27" monitor on a stand in the middle,
    a compact mechanical keyboard in front of it, an open 16" laptop to the right (as seen from the chair)."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        h = cfg["desk_height"]
        dark = materials.matte("Monitor Body", "#1C1C1E", 0.4)
        screen = materials.matte("Screen", "#05070B", 0.15)   # switched on: a dim bluish desktop
        bsdf = screen.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Emission Color"].default_value = materials.rgba("#41557A")
        bsdf.inputs["Emission Strength"].default_value = 0.8
        stand = materials.metal("Monitor Stand", "chrome") if cfg.get("stand") == "silver" else dark
        c = (self.s0 + self.s1) / 2 + cfg.get("monitor_offset", 0.0)
        # LG 27" 16:9: panel 61.4 × 36.9 incl. a thin bezel; bottom 11 cm above the desk
        W, H, zb = 0.614, 0.369, h + 0.11
        geo.frame_box("Monitor Base", f, c - 0.12, 0.05, h, c + 0.12, 0.26, h + 0.012, stand, col, bevel=0.004)
        geo.frame_box("Monitor Neck", f, c - 0.03, 0.07, h + 0.01, c + 0.03, 0.095, zb + 0.15, stand, col, bevel=0.003)
        geo.frame_box("Monitor Back", f, c - 0.2, 0.085, zb + 0.06, c + 0.2, 0.11, zb + 0.3, dark, col, bevel=0.01)
        geo.frame_box("Monitor Panel", f, c - W / 2, 0.11, zb, c + W / 2, 0.122, zb + H, dark, col, bevel=0.002)
        geo.frame_box("Monitor Screen", f, c - W / 2 + 0.006, 0.122, zb + 0.018, c + W / 2 - 0.006, 0.1222,
                      zb + H - 0.006, screen, col)
        if cfg.get("keyboard") == "alice":
            self._alice(f, c, h, dark, col)
        else:   # Keychron K2 (75 %): 31.3 × 12.3, keys on a 19 mm grid, rows rising toward the back
            body = materials.matte("Keyboard Body", "#3A3B3F", 0.5)
            caps = materials.matte("Keycaps", "#6A6C72", 0.55)
            accent = materials.matte("Keycaps Accent", "#C8643C", 0.55)
            kd0, kd1 = 0.5, 0.623
            geo.frame_box("Keyboard Case", f, c - 0.1565, kd0, h, c + 0.1565, kd1, h + 0.022, body, col, bevel=0.004)
            for r in range(6):
                dz = 0.022 + 0.004 * r / 5
                d1 = kd1 - 0.008 - r * 0.0185
                for k in range(16):
                    s = c - 0.1565 + 0.008 + k * 0.0186
                    geo.frame_box("Keycap", f, s, d1 - 0.0165, h + dz, s + 0.0165, d1, h + dz + 0.009,
                                  accent if (r, k) == (5, 0) else caps, col, bevel=0.0015)
        # MacBook Pro 16: 35.6 × 24.8 × 1.7, lid open ~105°
        alu = materials.metal("Laptop Aluminium", "platinum") if cfg.get("laptop") == "silver" else \
            materials.matte("Laptop Space Grey", "#4A4B4F", 0.35)
        LW, LD = 0.356, 0.248
        if cfg.get("laptop_state") == "closed":   # closed, in a back corner of the desk (by the wall)
            right = cfg.get("laptop_corner", "right") == "right"
            a0 = self.s1 - 0.03 - LW if right else self.s0 + 0.03
            geo.frame_box("Laptop Closed", f, a0, 0.03, h, a0 + LW, 0.03 + LD, h + 0.017, alu, col, bevel=0.004)
            geo.frame_box("Laptop Lid Seam", f, a0 + 0.002, 0.03 + LD - 0.0005, h + 0.008, a0 + LW - 0.002,
                          0.03 + LD + 0.0003, h + 0.009, dark, col)
            return
        m = c + cfg.get("laptop_offset", 0.48)
        ld0 = 0.36
        geo.frame_box("Laptop Base", f, m - LW / 2, ld0, h, m + LW / 2, ld0 + LD, h + 0.009, alu, col, bevel=0.003)
        geo.frame_box("Laptop Keys", f, m - 0.14, ld0 + 0.03, h + 0.009, m + 0.14, ld0 + 0.13, h + 0.0094, dark, col)
        tilt = math.radians(15)
        up = geo.Z * math.cos(tilt) - f.nrm * math.sin(tilt)          # lid leans back toward the wall
        out = f.nrm * math.cos(tilt) + geo.Z * math.sin(tilt)         # the screen faces the chair
        hinge = f.world(m - LW / 2, ld0 + 0.006, h + 0.009)
        _oriented_box("Laptop Lid", hinge, f.u, up, -out, LW, LD - 0.01, 0.007, alu, col, bevel=0.002)
        _oriented_box("Laptop Screen", hinge + f.u * 0.012 + up * 0.012, f.u, up, out, LW - 0.024, LD - 0.034, 0.0004,
                      screen, col)

    def _alice(self, f, c, h, dark, col):
        """Keychron V10 Max (Alice layout, 38.7 × 14.1 × 1.9): the two key halves turned ±6° about the middle,
        a column of macro keys on the left, a knob at the top right; the case juts out under the split."""
        body = materials.matte("Keyboard Body", "#1E1F21", 0.45)
        caps = materials.matte("Keycaps", "#3C3E42", 0.55)
        knob = materials.metal("Keyboard Knob", "chrome")
        L, D, kd0, kh = 0.387, 0.141, 0.48, 0.019
        out = [(c - L / 2, kd0), (c + L / 2, kd0), (c + L / 2, kd0 + D - 0.022), (c + 0.07, kd0 + D),
               (c - 0.07, kd0 + D), (c - L / 2, kd0 + D - 0.022)]
        case = geo.prism("Keyboard Case", [tuple(f.world(s, d, 0.0))[:2] for s, d in out], h, h + kh, body, col)
        geo.add_bevel(case, 0.003, 3)
        p, k = 0.019, 0.0172                      # key pitch and keycap size
        top = h + kh

        def key(s, d, w=1.0, turn=0.0):
            a = math.radians(turn)
            u = f.u * math.cos(a) + f.nrm * math.sin(a)
            v = f.nrm * math.cos(a) - f.u * math.sin(a)
            o = f.world(s, d, top) - u * (k + (w - 1) * p) / 2 - v * k / 2
            _oriented_box("Keycap", o, u, v, geo.Z, k + (w - 1) * p, k, 0.009, caps, col, bevel=0.0015)

        for r in range(5):                         # macro column
            key(c - L / 2 + 0.018, kd0 + 0.02 + r * p * 1.05)
        rows = [(7, 8), (6, 8), (6, 7), (6, 6)]    # keys per half, top row first (after the F row)
        for side, turn in ((-1, 6.0), (1, -6.0)):
            pivot = (c + side * 0.012, kd0 + 0.13)
            def place(ds, dd, w=1.0):   # position in the half, turned about the pivot
                a = math.radians(turn)
                s = pivot[0] + ds * math.cos(a) - dd * math.sin(a)
                d = pivot[1] + ds * math.sin(a) + dd * math.cos(a)
                key(s, d, w, turn)
            for j in range(7 if side < 0 else 8):  # F row
                place(side * (0.012 + (j + 0.5) * p), -0.105)
            for r, counts in enumerate(rows):
                n = counts[0] if side < 0 else counts[1]
                for j in range(n):
                    place(side * (0.006 + (j + 0.5) * p + 0.004 * r), -0.083 + r * p)
            place(side * (0.006 + 1.5 * p), -0.083 + 4 * p, 3.0 if side < 0 else 1.0)   # space bars
            place(side * (0.006 + 2.5 * p), -0.083 + 4 * p, 2.75)
        geo.cylinder("Keyboard Knob", f.world(c + L / 2 - 0.022, kd0 + 0.018, top + 0.006), geo.Z, 0.009, 0.014,
                     knob, col, 32)


def _rounded_ring(cs, cd, hs, hd, r, steps=8):
    """Rounded rectangle around (cs, cd) with half-sizes hs × hd, counter-clockwise, as (s, d) points."""
    pts = []
    for k, (ks, kd) in enumerate(((1, 1), (-1, 1), (-1, -1), (1, -1))):
        for i in range(steps + 1):
            a = math.radians(90 * k + 90 * i / steps)
            pts.append((cs + ks * (hs - r) + r * math.cos(a), cd + kd * (hd - r) + r * math.sin(a)))
    return pts


def _bake_smooth(obj, angle=40):
    """Apply the modifiers (e.g. a boolean bowl) and shade smooth by angle, so curved cuts are not faceted."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    obj.modifiers.clear()
    obj.data = me
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(angle))


class Bathtub(_WallItem):
    """Built-in acrylic bathtub: one stepped body (rim lip over a narrower base) hollowed by a rounded, tapered
    bowl; chrome drain and overflow at the `drain` end. In front, a tiled screen under the lip with a toe recess."""

    RIM = 0.025     # rim lip thickness seen from the front
    BORDER = 0.06   # rim width around the bowl
    BOWL = 0.42     # bowl depth below the rim
    TAPER = (0.07, 0.05)  # the bowl narrows this much toward the bottom: at the ends, at the sides

    def build(self, col):
        cfg, f = self.cfg, self.f
        acrylic = materials.paint("Bathtub Acrylic", cfg["color"], 0.08)
        chrome = materials.metal("Bathtub Chrome", "chrome")
        s0, s1, d0 = self.s0, self.s1, cfg["gap"]
        d1, zr = d0 + cfg["depth"], cfg["height"]
        zb = zr - self.BOWL
        # body: the lip spans the full depth, the base under it stands back behind the screen
        prof = [(d0, zb - 0.03), (d1 - 0.03, zb - 0.03), (d1 - 0.03, zr - self.RIM), (d1, zr - self.RIM), (d1, zr),
                (d0, zr)]
        bm = bmesh.new()
        rings = [[bm.verts.new(f.world(s, d, z)) for d, z in prof] for s in (s0, s1)]
        bm.faces.new(rings[0])
        bm.faces.new(list(reversed(rings[1])))
        n = len(prof)
        for j in range(n):
            bm.faces.new((rings[0][j], rings[1][j], rings[1][(j + 1) % n], rings[0][(j + 1) % n]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        body = geo.mesh_object("Bathtub", bm, acrylic, col)

        b, (ts, td) = self.BORDER, self.TAPER
        cs, cd = (s0 + s1) / 2, (d0 + d1) / 2
        hs, hd = (s1 - s0) / 2 - b, (d1 - d0) / 2 - b
        top, bottom = _rounded_ring(cs, cd, hs, hd, 0.11), _rounded_ring(cs, cd, hs - ts, hd - td, 0.09)
        ztop = zr + 0.02
        bm = bmesh.new()
        lo = [bm.verts.new(f.world(s, d, zb)) for s, d in bottom]
        hi = [bm.verts.new(f.world(s, d, ztop)) for s, d in top]
        bm.faces.new(lo)
        bm.faces.new(list(reversed(hi)))
        n = len(lo)
        for j in range(n):
            bm.faces.new((lo[j], lo[(j + 1) % n], hi[(j + 1) % n], hi[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        cutter = geo.mesh_object("Bathtub Bowl Cutter", bm, None, _cutters(), smooth_angle=50)
        geo.add_bevel(cutter, 0.06, 5)  # rounded bowl floor
        cutter.hide_render = True
        mod = body.modifiers.new("Bowl", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cutter
        mod.solver = "EXACT"
        _bake_smooth(body)

        end = 1.0 if cfg["drain"] == "end" else -1.0
        s_end = cs + end * hs                                   # bowl end wall at the rim
        geo.cylinder("Bathtub Drain", f.world(cs + end * (hs - ts - 0.14), cd, zb + 0.001), geo.Z, 0.034, 0.004,
                     chrome, col, 48)
        z_of = zr - 0.11
        s_of = s_end - end * (ts * (ztop - z_of) / (ztop - zb) + 0.004)   # on the sloped end wall
        geo.cylinder("Bathtub Overflow", f.world(s_of, cd, z_of), f.u, 0.03, 0.008, chrome, col, 48)

        sc = cfg.get("screen")
        if sc:
            tile = bpy.data.materials.get(f"Wall Tile {sc.get('room')}") or materials.matte("Bathtub Screen",
                                                                                            cfg["color"], 0.5)
            kh, kd = sc.get("kick") or (0.0, 0.0)
            face = d1 - 0.005                                   # just under the lip
            # the toe recess runs only along `kick_span`; elsewhere (e.g. a boxed pipe against it) down to the floor
            k0, k1 = f.span(None, {"span": sc["kick_span"]}) if sc.get("kick_span") else (s0, s1)
            geo.frame_box("Bathtub Screen", f, s0, face - max(kd, 0.02), kh, s1, face, zr - self.RIM, tile, col)
            if kh > 0:
                geo.frame_box("Bathtub Screen Kick", f, k0, face - kd - 0.02, 0.0, k1, face - kd, kh, tile, col)
                for a, b in ((s0, k0), (k1, s1)):
                    if b - a > 0.001:
                        geo.frame_box("Bathtub Screen Foot", f, a, face - max(kd, 0.02), 0.0, b, face, kh, tile, col)


class TiledBox(_WallItem):
    """Boxed-in installation or pipes (короб): a block against the wall, faced with the tile of that room's walls."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        tile = bpy.data.materials.get(f"Wall Tile {cfg['room']}") or materials.matte("Box Finish", cfg["color"], 0.6)
        geo.frame_box("Tiled Box", f, self.s0, -0.01, 0.0, self.s1, cfg["gap"] + cfg["depth"], cfg["height"], tile, col)


class WallToilet(_WallItem):
    """Wall-hung rimless toilet (after Santerika SAN.UNT.01: 49.5 × 36.5 × 36.5 with the seat): a compact rounded
    bowl, straight sides from the wall into a round front, its section narrowing downward like a U and its underside
    rounding back up to the tall back against the wall; a slim seat and a full-size lid, closed, short of the wall
    at the hinges; the chrome flush plate with two buttons above. `gap` = the face it hangs on (wall or box),
    `span` = width, `depth` = length, `seat_height` = top of the closed lid. With `model` (a maker's .3ds mesh)
    that mesh replaces the drawn bowl."""

    BACK, WIDEST, ROUND = 0.9, 0.38, 2.2   # width at the wall, widest point (parts of width / length), front shape
    # body rings below the rim: (depth, width scale, length scale), scaled about the middle of the back
    BODY = [(0.0, 0.985, 0.99), (0.005, 0.997, 0.998), (0.015, 1.0, 1.0), (0.06, 0.998, 0.997), (0.12, 0.985, 0.985),
            (0.18, 0.95, 0.955), (0.23, 0.89, 0.905), (0.27, 0.8, 0.83), (0.30, 0.68, 0.73), (0.32, 0.54, 0.62),
            (0.335, 0.36, 0.5)]

    def outline(self, half, length, v0=0.0, n=24):
        """Plan outline as (u across, v from the wall), the back straight at v0."""
        vm, p = self.WIDEST * length, self.ROUND
        side = [(half * (self.BACK + (1 - self.BACK) * math.sin(math.pi / 2 * min(v / vm, 1.0))), v)
                for v in (v0 + (vm - v0) * i / n for i in range(n + 1))]
        for i in range(1, n + 1):
            t = math.pi / 2 * i / n
            side.append((half * math.cos(t) ** (2 / p), vm + (length - vm) * math.sin(t) ** (2 / p)))
        return side + [(-u, v) for u, v in reversed(side[:-1])]

    def build(self, col):
        cfg, f = self.cfg, self.f
        ceramic = materials.paint("Toilet Ceramic", cfg["color"], 0.06)
        seat = materials.paint("Toilet Seat", cfg["color"], 0.18)
        cs, half, d0, length = (self.s0 + self.s1) / 2, (self.s1 - self.s0) / 2, cfg["gap"], cfg["depth"]
        top = cfg["seat_height"]
        if cfg.get("model"):
            self._model(cfg, f, cs, d0, top, ceramic, seat, col)
        else:
            self._bowl(f, cs, half, d0, length, top, ceramic, seat, col)
        self._plate(cfg, f, cs, d0, col)

    def _model(self, cfg, f, cs, d0, top, ceramic, seat, col):
        """A maker's mesh (.3ds, `model_units` = meters per unit): its flat back against the face `gap`, centered
        on the span, the top at `seat_height`; parts lying in the top 5 cm (seat and lid) get the seat finish.
        The back is the end of the longer horizontal axis with more vertices lying flat in it, unless `model_back`
        ("+x", "-x", "+y", "-y") says."""
        path = Path(__file__).resolve().parent.parent / cfg["model"]
        k = cfg.get("model_units", 0.001)
        meshes = model3ds.load(path)
        pts = [p for _, vs, _ in meshes for p in vs]
        lo = [min(p[i] for p in pts) for i in range(3)]
        hi = [max(p[i] for p in pts) for i in range(3)]
        back = cfg.get("model_back")
        if not back:
            ax = 0 if hi[0] - lo[0] > hi[1] - lo[1] else 1
            flat = lambda c: sum(abs(p[ax] - c) < 2.0 / k * 0.001 for p in pts)
            back = ("+" if flat(hi[ax]) > flat(lo[ax]) else "-") + "xy"[ax]
        ax, sign = "xy".index(back[1]), (1 if back[0] == "+" else -1)
        across = 1 - ax
        mid = (lo[across] + hi[across]) / 2
        z_top = hi[2]

        def place(p):  # model → (along the wall, off the face, height)
            v = (hi[ax] - p[ax]) if sign > 0 else (p[ax] - lo[ax])
            return f.world(cs + (p[across] - mid) * k * sign * (1 if ax == 1 else -1), d0 - 0.002 + v * k,
                           top - (z_top - p[2]) * k)

        for name, vs, faces in meshes:
            bm = bmesh.new()
            verts = [bm.verts.new(place(p)) for p in vs]
            for a, b, c in faces:
                try:
                    bm.faces.new((verts[a], verts[b], verts[c]))
                except ValueError:  # duplicate face
                    pass
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0002)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            lid = (min(p[2] for p in vs) - lo[2]) * k > (hi[2] - lo[2]) * k - 0.05
            geo.mesh_object(f"Toilet {name}", bm, seat if lid else ceramic, col, smooth_angle=35)

    def _bowl(self, f, cs, half, d0, length, top, ceramic, seat, col):
        rim = top - 0.03

        def loft(name, rings, v0, mat):
            base = self.outline(half, length, v0)
            bm = bmesh.new()
            levels = [[bm.verts.new(f.world(cs + u * sw, d0 - 0.003 + v * sl, z)) for u, v in base]
                      for z, sw, sl in rings]
            bm.faces.new(levels[0])
            bm.faces.new(levels[-1])
            n = len(base)
            for a, b in zip(levels, levels[1:]):
                for j in range(n):
                    bm.faces.new((a[j], a[(j + 1) % n], b[(j + 1) % n], b[j]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            return geo.mesh_object(name, bm, mat, col, smooth_angle=60)

        loft("Toilet Bowl", [(rim - dz, sw, sl) for dz, sw, sl in self.BODY], 0.0, ceramic)
        loft("Toilet Seat", [(rim + 0.001, 0.975, 0.982), (rim + 0.006, 0.985, 0.99), (rim + 0.011, 0.978, 0.985)],
             0.035, seat)
        loft("Toilet Lid", [(rim + 0.012, 0.985, 0.99), (rim + 0.02, 0.995, 0.997), (top - 0.004, 0.99, 0.993),
                            (top, 0.965, 0.972)], 0.04, seat)
        for side in (-1, 1):                                    # hinges behind the lid
            geo.add_bevel(geo.frame_box("Toilet Seat Hinge", f, cs + side * 0.085 - 0.014, d0 + 0.006, rim,
                                        cs + side * 0.085 + 0.014, d0 + 0.042, rim + 0.022, seat, col), 0.006)

    def _plate(self, cfg, f, cs, d0, col):
        """Flush plate after Grohe Skate Cosmopolitan (156 × 197, chrome): a plate with rounded corners and a soft
        edge, two rounded buttons in it, the half flush on the left, a dark gap around each."""
        pl = cfg["plate"]
        chrome = materials.metal("Flush Plate", pl["finish"])
        dark = materials.matte("Flush Plate Gap", "#2A2A2A", 0.6)
        (pw, ph), zc = pl["size"], pl["z"]

        def slab(name, a, b, z0, z1, r, d1, d2, mat, bevel):  # rounded rectangle on the wall, from d1 to d2
            ring = _rounded_ring((a + b) / 2, (z0 + z1) / 2, (b - a) / 2, (z1 - z0) / 2, r, 6)
            bm = bmesh.new()
            back = [bm.verts.new(f.world(s_, d0 + d1, z)) for s_, z in ring]
            front = [bm.verts.new(f.world(s_, d0 + d2, z)) for s_, z in ring]
            bm.faces.new(back)
            bm.faces.new(list(reversed(front)))
            for j in range(len(ring)):
                bm.faces.new((back[j], back[(j + 1) % len(ring)], front[(j + 1) % len(ring)], front[j]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            obj = geo.mesh_object(name, bm, mat, col, smooth_angle=40)
            if bevel:
                geo.add_bevel(obj, bevel, 3)

        x0, x1, z0, z1 = cs - pw / 2, cs + pw / 2, zc - ph / 2, zc + ph / 2
        slab("Flush Plate", x0, x1, z0, z1, 0.012, 0.0, 0.008, chrome, 0.003)
        m, g = 0.019, 0.004                                    # margin around the buttons, gap between them
        split = x0 + m + (pw - 2 * m) * 0.38                   # small (half) flush left, full flush right
        for k, (a, b) in enumerate(((x0 + m, split - g / 2), (split + g / 2, x1 - m))):
            slab("Flush Plate Gap", a - 0.0015, b + 0.0015, z0 + m - 0.0015, z1 - m + 0.0015, 0.0075, 0.007, 0.0082,
                 dark, 0.0)
            slab(f"Flush Button {k + 1}", a, b, z0 + m, z1 - m, 0.006, 0.006, 0.0105, chrome, 0.0015)


class Appliance(_WallItem):
    """Haier 979 front loader (washer HW80-B14979 / heat-pump dryer HD70-A2979U1), after the makers' photos:
    white body; a black glass band 10.5 cm high across the top of the front with the drawer on the left
    (washer: slot pull; dryer: water tank with a silver pull), white digits and program marks in the middle,
    a black dial with a glowing cyan ring and the power key on the right; a 53 cm door of black glass with a thin
    silver rim and a chrome crescent pull at the upper right; a round service flap low on the right.
    `depth` = body depth, the door bulges in front of it; `gap` = space behind the body."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        tag = cfg["kind"].title()
        body = materials.paint(f"{tag} Body", cfg["color"], 0.28)
        glass = materials.paint(f"{tag} Black Glass", "#0B0B0C", 0.04)
        seam = materials.matte(f"{tag} Seam", "#2A2A2A", 0.7)
        silver = materials.metal(f"{tag} Silver", "chrome")
        satin = materials.metal(f"{tag} Satin", "platinum")
        white_led = materials.glow(f"{tag} Digits", "#F2F4F8", 2.5)
        label = materials.glow(f"{tag} Labels", "#C9CCD2", 0.6)
        cyan = materials.glow(f"{tag} Cyan", "#28C8F0", 4.0)
        s0, s1, d0 = self.s0, self.s1, cfg["gap"]
        d1, z0 = d0 + cfg["depth"], cfg["elevation"]
        z1 = z0 + cfg["height"]
        W = s1 - s0

        def box(name, a, b, c, e, g, h, mat, bevel=0.0):
            return geo.frame_box(f"{tag} {name}", f, a, b, c, e, g, h, mat, col, bevel=bevel)

        def cyl(name, s, d, zz, axis, r, depth, mat, seg=64, bevel=0.0):
            obj = geo.cylinder(f"{tag} {name}", f.world(s, d, zz), axis, r, depth, mat, col, seg)
            if bevel:
                geo.add_bevel(obj, bevel, 4)
            return obj

        def arc(name, cs_, zc_, r, a0, a1, prof, mat, d):
            pts = [f.world(cs_ + r * math.cos(math.radians(a0 + (a1 - a0) * i / 16)), d,
                           zc_ + r * math.sin(math.radians(a0 + (a1 - a0) * i / 16))) for i in range(17)]
            return geo.sweep(f"{tag} {name}", pts, f.nrm, prof, mat, col, side=1.0, smooth_angle=50)

        if z0 > 0.1:  # stacking kit with a pull-out shelf
            box("Stacking Kit", s0, d0 + 0.02, z0 - 0.012, s1, d1 - 0.002, z0, body, 0.002)
            box("Stacking Shelf", s0 + 0.02, d1 - 0.002, z0 - 0.009, s1 - 0.02, d1 + 0.001, z0 - 0.003, seam)
        for ss in (s0 + 0.04, s1 - 0.04):
            for dd in (d0 + 0.05, d1 - 0.05):
                cyl("Foot", ss, dd, z0 + 0.006, geo.Z, 0.018, 0.012, seam, 24)
        box("Body", s0, d0, z0 + 0.012, s1, d1, z1, body, 0.012)

        # black glass band
        bz0, bz1 = z1 - 0.105, z1 - 0.006
        split = s0 + 0.38 * W
        box("Drawer Front", s0 + 0.004, d1 - 0.002, bz0, split - 0.0015, d1 + 0.004, bz1, glass, 0.003)
        box("Band", split + 0.0015, d1 - 0.002, bz0, s1 - 0.004, d1 + 0.003, bz1, glass, 0.003)
        logo_z = bz1 - 0.022
        box("Logo", s0 + 0.018, d1 + 0.004, logo_z, s0 + 0.058, d1 + 0.0043, logo_z + 0.009, label)
        if cfg["kind"] == "dryer":   # water tank pull: a silver plate
            box("Tank Pull", s0 + 0.03, d1 + 0.004, bz0 + 0.014, s0 + 0.16, d1 + 0.009, bz0 + 0.038, satin, 0.004)
        else:                        # detergent drawer pull: a recessed slot
            box("Drawer Pull", s0 + 0.03, d1 + 0.0035, bz0 + 0.014, s0 + 0.14, d1 + 0.0045, bz0 + 0.036, seam, 0.003)
        zm = (bz0 + bz1) / 2
        sd = split + 0.105                                   # display: digits with marks around
        for k, a in enumerate((sd - 0.03, sd - 0.016, sd + 0.004, sd + 0.018)):   # "88:88" in seven segments
            h, wd, t_, zb = 0.02, 0.011, 0.0018, zm + 0.004
            for (x0, y0, x1, y1) in ((0, 0, wd, t_), (0, h / 2 - t_ / 2, wd, h / 2 + t_ / 2), (0, h - t_, wd, h),
                                     (0, 0, t_, h / 2), (0, h / 2, t_, h), (wd - t_, 0, wd, h / 2), (wd - t_, h / 2, wd, h)):
                box("Digit Segment", a + x0, d1 + 0.0031, zb + y0, a + x1, d1 + 0.0034, zb + y1, white_led)
        for zz in (zm + 0.009, zm + 0.017):
            box("Digit Colon", sd - 0.0015, d1 + 0.0031, zz, sd + 0.0015, d1 + 0.0034, zz + 0.003, white_led)
        for k in range(3):
            box("Icon", sd - 0.085 + k * 0.018, d1 + 0.0031, zm + 0.012, sd - 0.075 + k * 0.018, d1 + 0.0034,
                zm + 0.02, label)
        for row, zr in enumerate((zm - 0.018, zm - 0.034)):  # program list: cyan marks and labels
            for k in range(7):
                a = split + 0.018 + k * 0.028
                box("Program Mark", a, d1 + 0.0031, zr, a + 0.003, d1 + 0.0034, zr + 0.003, cyan)
                box("Program Label", a + 0.005, d1 + 0.0031, zr, a + 0.02, d1 + 0.0034, zr + 0.003, label)
        sk = s1 - 0.105                                      # dial with a glowing ring
        cyl("Dial Ring", sk, d1 + 0.006, zm, f.nrm, 0.035, 0.006, cyan, 64)
        cyl("Dial", sk, d1 + 0.012, zm, f.nrm, 0.031, 0.018, glass, 64, bevel=0.006)
        box("Dial Mark", sk - 0.004, d1 + 0.0215, zm - 0.004, sk + 0.004, d1 + 0.0218, zm + 0.004, cyan)
        box("Power Key", s1 - 0.045, d1 + 0.0031, zm - 0.006, s1 - 0.025, d1 + 0.0036, zm + 0.006, label, 0.001)

        # door: black glass dome in a thin silver rim, chrome crescent pull at the upper right
        cs, zc, r = (s0 + s1) / 2, z0 + 0.46, cfg["door"] / 2
        cyl("Door Rim", cs, d1 + 0.012, zc, f.nrm, r, 0.024, silver, 96)
        cyl("Door", cs, d1 + 0.024, zc, f.nrm, r - 0.006, 0.05, glass, 96, bevel=0.02)
        recess = [(0.0, 0.0), (0.016, 0.0), (0.016, 0.004), (0.0, 0.004)]
        arc("Door Pull Recess", cs, zc, r - 0.04, 12, 62, recess, seam, d1 + 0.0495)
        edge = [(0.0, 0.0), (0.003, 0.0), (0.003, 0.006), (0.0, 0.006)]
        arc("Door Pull Edge", cs, zc, r - 0.024, 10, 64, edge, silver, d1 + 0.0465)
        # service flap, low on the right
        cyl("Flap Gap", s1 - 0.09, d1 + 0.0004, z0 + 0.085, f.nrm, 0.056, 0.0008, seam, 48)
        cyl("Flap", s1 - 0.09, d1 + 0.0015, z0 + 0.085, f.nrm, 0.054, 0.002, body, 48)


class ApplianceColumn(_WallItem):
    """Column for stacked appliances (стирка + сушка): side panels to the ceiling, the machines in an open niche
    below, a shelf over them and flat doors from there up to the ceiling."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        mat = materials.paint("Column Cabinet", cfg["color"], 0.4)
        s0, s1, d, t, top = self.s0, self.s1, cfg["depth"], 0.018, self.h
        zn = cfg["niche_height"]
        for name, a, b in (("L", s0, s0 + t), ("R", s1 - t, s1)):
            geo.frame_box(f"Column Side {name}", f, a, 0.0, 0.0, b, d, top, mat, col, bevel=0.0015)
        geo.frame_box("Column Shelf", f, s0 + t, 0.0, zn, s1 - t, d - t, zn + t, mat, col)
        n, gap = cfg["doors"], 0.003
        w = (s1 - s0 - 2 * t - gap * (n + 1)) / n
        for k in range(n):
            a = s0 + t + gap + k * (w + gap)
            geo.frame_box(f"Column Door {k + 1}", f, a, d - t, zn + gap, a + w, d, top - gap, mat, col, bevel=0.002)


class BasinTop(_WallItem):
    """Ceramic countertop basin over a wall-hung vanity: a slab with a rounded bowl, drain, and a chrome mixer
    at the back. `height` = top of the slab above the floor, `thickness` = its edge; a bowl deeper than that
    hangs below the slab in a body of its own, into the vanity (`open_top`)."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        ceramic = materials.paint("Basin Ceramic", cfg["color"], 0.06)
        chrome = materials.metal("Basin Mixer", "chrome")
        s0, s1, d = self.s0, self.s1, cfg["depth"]
        top, th = cfg["height"], cfg["thickness"]
        slab = geo.frame_box("Basin", f, s0, 0.0, top - th, s1, d, top, ceramic, col)
        cs = (s0 + s1) / 2
        bw, bd, depth = cfg["bowl"]
        cd = d - 0.03 - bd / 2                                  # the bowl sits toward the front
        ring = _rounded_ring(cs, cd, bw / 2, bd / 2, min(0.08, bd / 2 - 0.005))
        shells = [slab]
        if depth + 0.012 > th:  # a thin edge: the bowl's body hangs below the slab, into the vanity
            bm = bmesh.new()
            outer = _rounded_ring(cs, cd, bw / 2 + 0.012, bd / 2 + 0.012, min(0.09, bd / 2 + 0.007))
            lo = [bm.verts.new(f.world(s, dd, top - depth - 0.012)) for s, dd in outer]
            hi = [bm.verts.new(f.world(s, dd, top - th + 0.001)) for s, dd in outer]
            bm.faces.new(lo)
            bm.faces.new(list(reversed(hi)))
            for j in range(len(lo)):
                bm.faces.new((lo[j], lo[(j + 1) % len(lo)], hi[(j + 1) % len(lo)], hi[j]))
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            shells.append(geo.mesh_object("Basin Bowl Body", bm, ceramic, col))
        bm = bmesh.new()
        lo = [bm.verts.new(f.world(s, dd, top - depth)) for s, dd in _rounded_ring(cs, cd, bw / 2 - 0.03, bd / 2 - 0.03,
                                                                                    min(0.06, bd / 2 - 0.035))]
        hi = [bm.verts.new(f.world(s, dd, top + 0.02)) for s, dd in ring]
        bm.faces.new(lo)
        bm.faces.new(list(reversed(hi)))
        for j in range(len(lo)):
            bm.faces.new((lo[j], lo[(j + 1) % len(lo)], hi[(j + 1) % len(lo)], hi[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        cutter = geo.mesh_object("Basin Bowl Cutter", bm, None, _cutters(), smooth_angle=50)
        geo.add_bevel(cutter, 0.03, 4)
        cutter.hide_render = True
        for shell in shells:
            mod = shell.modifiers.new("Bowl", "BOOLEAN")
            mod.operation = "DIFFERENCE"
            mod.object = cutter
            mod.solver = "EXACT"
            _bake_smooth(shell)
        geo.cylinder("Basin Drain", f.world(cs, cd, top - depth + 0.001), geo.Z, 0.02, 0.004, chrome, col, 40)
        dm = cd - bd / 2 - 0.035                                 # mixer behind the bowl
        geo.cylinder("Mixer Base", f.world(cs, dm, top + 0.004), geo.Z, 0.026, 0.008, chrome, col, 48)
        geo.cylinder("Mixer Body", f.world(cs, dm, top + 0.08), geo.Z, 0.018, 0.15, chrome, col, 48)
        geo.frame_box("Mixer Spout", f, cs - 0.012, dm, top + 0.13, cs + 0.012, dm + 0.13, top + 0.15, chrome, col,
                      bevel=0.006)
        geo.frame_box("Mixer Lever", f, cs - 0.006, dm - 0.06, top + 0.158, cs + 0.006, dm + 0.01, top + 0.168, chrome,
                      col, bevel=0.003)


class BidetShower(_WallItem):
    """Hygienic shower set Hansgrohe Bidette S 1jet EcoSmart+ with stop valve (29230000), from the maker's drawing:
    round rosette ⌀76 × 11; a horizontal valve arm ⌀36 reaching 73 mm from the wall, ending in the holder with an
    oval end cap and the round valve knob on its side; the hand shower stands upright in the holder — a flat-oval
    handle, its head bending away from the wall so the 28 mm spray disc faces up and out, 150 mm above the outlet
    axis and 106 mm from the wall; the hose leaves a conical nut under the arm by the wall and hangs in a narrow
    loop up into the shower's end. `span` centers it, `gap` = the face it is fixed to, `z` = outlet axis height."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        chrome = materials.metal("Bidet Shower Chrome", "chrome")
        hose_mat = materials.metal("Bidet Hose", "platinum")
        dark = materials.matte("Bidet Spray Disc", "#2E2E30", 0.45)
        cs, d0, z = (self.s0 + self.s1) / 2, cfg["gap"], cfg["z"]
        w = lambda s, d, zz: f.world(cs + s, d0 + d, z + zz)

        def bev(obj, width, seg=3):
            geo.add_bevel(obj, width, seg)
            return obj

        bev(geo.cylinder("Bidet Rosette", w(0, 0.0055, 0), f.nrm, 0.038, 0.011, chrome, col, 64), 0.003)
        bev(geo.cylinder("Bidet Valve Arm", w(0, 0.045, 0), f.nrm, 0.018, 0.07, chrome, col, 48), 0.003)
        bev(geo.frame_box("Bidet Holder", f, cs - 0.018, d0 + 0.052, z - 0.022, cs + 0.018, d0 + 0.086, z + 0.02, chrome,
                          col), 0.008, 4)
        bev(geo.frame_box("Bidet End Cap", f, cs - 0.019, d0 + 0.084, z - 0.034, cs + 0.019, d0 + 0.099, z + 0.021,
                          chrome, col), 0.0075, 5)
        bev(geo.cylinder("Bidet Valve Knob", w(0.025, 0.066, 0), f.u, 0.0155, 0.014, chrome, col, 48), 0.004)

        # hand shower: flat-oval handle up from inside the holder, head tilted away from the wall
        bm = bmesh.new()
        sections = [(-0.04, 0.070, 0.0125, 0.0145), (0.02, 0.070, 0.013, 0.015), (0.085, 0.071, 0.0135, 0.0155),
                    (0.1, 0.073, 0.0145, 0.016)]
        rings = [[bm.verts.new(w(s, d, zz)) for s, d in _rounded_ring(0.0, dc, hs, hd, min(hs, hd) * 0.95, 6)]
                 for zz, dc, hs, hd in sections]
        bm.faces.new(list(reversed(rings[0])))
        bm.faces.new(rings[-1])
        n = len(rings[0])
        for lo, hi in zip(rings, rings[1:]):
            for j in range(n):
                bm.faces.new((lo[j], lo[(j + 1) % n], hi[(j + 1) % n], hi[j]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        geo.mesh_object("Bidet Hand Shower", bm, chrome, col, smooth_angle=60)
        tilt = math.radians(40)
        axis = (geo.Z * math.cos(tilt) + f.nrm * math.sin(tilt)).normalized()
        p0 = w(0, 0.074, 0.098)
        bev(geo.cylinder("Bidet Shower Head", p0 + axis * 0.026, axis, 0.0175, 0.052, chrome, col, 48, radius2=0.0185),
            0.004, 4)
        tip = p0 + axis * 0.0522
        geo.cylinder("Bidet Spray Disc", tip, axis, 0.0145, 0.0012, dark, col, 48)
        side = axis.cross(f.u).normalized()
        for k in range(9):                                    # nozzles: a ring of 8 and one in the middle
            off = (f.u * math.cos(2 * math.pi * k / 8) + side * math.sin(2 * math.pi * k / 8)) * 0.0085 if k < 8 else f.u * 0.0
            geo.cylinder("Bidet Nozzle", tip + axis * 0.0007 + off, axis, 0.0011, 0.0005, chrome, col, 10)

        # hose: conical nut under the arm by the wall, down in a narrow loop, up into the shower's end
        geo.cylinder("Bidet Outlet Nut", w(0, 0.034, -0.036), geo.Z, 0.0095, 0.036, chrome, col, 32, radius2=0.012)
        geo.cylinder("Bidet Shower Nut", w(0, 0.070, -0.05), geo.Z, 0.0085, 0.022, chrome, col, 32, radius2=0.0105)
        a, b = w(0, 0.034, -0.052), w(0, 0.070, -0.059)
        drop, rad = cfg.get("hose_drop", 0.33), 0.018
        pts = []
        for i in range(13):                                   # down the wall side
            t = i / 12
            pts.append(a - geo.Z * (drop * t) + f.u * (0.012 * math.sin(math.pi * t)))
        c = (a + b) / 2 - geo.Z * drop                        # round bottom of the loop
        rr = (b - a).dot(f.nrm) / 2
        for i in range(1, 12):
            ang = math.pi * i / 12
            pts.append(c - f.nrm * (rr * math.cos(ang)) - geo.Z * (rad * math.sin(ang)))
        for i in range(13):                                   # up into the shower
            t = i / 12
            bottom = b - geo.Z * (drop - (b - a).dot(geo.Z))
            pts.append(bottom.lerp(b, t) - f.u * (0.01 * math.sin(math.pi * t)))
        prof = [(0.0055 * math.cos(2 * math.pi * k / 16), 0.0055 * math.sin(2 * math.pi * k / 16)) for k in range(16)]
        geo.sweep("Bidet Hose", pts, f.u, prof, hose_mat, col, smooth_angle=60)


class TowelWarmer(_WallItem):
    """Electric towel warmer of flat tubes. "bars": vertical bars side by side (Margroid Inaro profile, after the
    maker's drawing: 4 bars 30 mm wide at 50 mm, rows of knob hooks reaching `depth` from the wall); "ladder": two
    side rails with flat rungs (`bars` of them) on wall brackets. The control unit sits low at the `connection` end,
    as seen facing it. `hooks` = rows of hooks below the top."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        paint = materials.paint("Towel Warmer", cfg["color"], 0.45)
        dots = materials.matte("Towel Warmer Control Marks", "#8A8C90", 0.6)
        s0, s1, d1, n = self.s0, self.s1, cfg["depth"], cfg["bars"]
        z0 = cfg["elevation"]
        z1 = z0 + cfg["height"]
        right_end = (-f.nrm).cross(geo.Z).dot(f.u) > 0   # facing it, its right hand is toward s1
        end_s = s1 if (cfg["connection"] == "right") == right_end else s0
        if cfg["style"] == "bars":   # after the maker's photo: caps on the bar ends, round cross tubes between them
            bw, b0, b1 = 0.03, 0.006, 0.028                       # flat tube 30 × 22 just off the wall
            pitch = (s1 - s0 - bw) / (n - 1)
            for k in range(n):
                a = s0 + k * pitch
                geo.frame_box(f"Towel Warmer Bar {k + 1}", f, a, b0, z0 + 0.006, a + bw, b1, z1 - 0.006, paint, col,
                              bevel=0.002)
                for zc in (z0 + 0.003, z1 - 0.003):
                    geo.frame_box("Towel Warmer Cap", f, a - 0.0012, b0 - 0.0012, zc - 0.004, a + bw + 0.0012,
                                  b1 + 0.0012, zc + 0.004, paint, col, bevel=0.0015)
                for zh in cfg["hooks"]:
                    c = a + bw / 2
                    geo.cylinder("Towel Warmer Hook Pin", f.world(c, (b1 + d1) / 2, z1 - zh), f.nrm, 0.0055,
                                 d1 - b1, paint, col, 24)
                    geo.add_bevel(geo.cylinder("Towel Warmer Hook", f.world(c, d1 - 0.004, z1 - zh), f.nrm, 0.012,
                                               0.008, paint, col, 40), 0.002)
            for zt in [z1 - zh + 0.035 for zh in cfg["hooks"]] + [z0 + 0.06]:   # cross tubes behind the hook rows
                geo.cylinder("Towel Warmer Cross Tube", f.world((s0 + s1) / 2, (b0 + b1) / 2, zt), f.u, 0.0085,
                             s1 - s0 - bw, paint, col, 24)
            face, unit = b1, (end_s - bw / 2 if end_s == s1 else end_s + bw / 2)
        else:
            rw, r0 = 0.03, d1 - 0.024                             # side rails: flat tube 30 × 24
            for name, a in (("L", s0), ("R", s1 - rw)):
                geo.frame_box(f"Towel Warmer Rail {name}", f, a, r0, z0, a + rw, d1, z1, paint, col, bevel=0.004)
                for zz in (z0 + 0.12, z1 - 0.12):                 # wall brackets
                    geo.cylinder("Towel Warmer Bracket", f.world(a + rw / 2, r0 / 2, zz), f.nrm, 0.008, r0, paint,
                                 col, 24)
            for k in range(n):
                zc = z0 + 0.04 + k * (cfg["height"] - 0.08) / (n - 1)
                geo.frame_box(f"Towel Warmer Rung {k + 1}", f, s0 + rw - 0.002, r0 + 0.004, zc - 0.011,
                              s1 - rw + 0.002, d1 - 0.004, zc + 0.011, paint, col, bevel=0.003)
            face, unit = d1, (end_s - rw / 2 if end_s == s1 else end_s + rw / 2)
        geo.frame_box("Towel Warmer Control", f, unit - 0.013, face, z0 + 0.1, unit + 0.013, face + 0.006, z0 + 0.15,
                      paint, col, bevel=0.002)
        for k in range(3):
            zz = z0 + 0.113 + k * 0.012
            geo.cylinder("Towel Warmer Control Mark", f.world(unit, face + 0.0062, zz), f.nrm, 0.0022, 0.0006, dots,
                         col, 16)


class BathMixer(_WallItem):
    """Exposed wall bath mixer with a shower set: two eccentrics in round flanges 150 apart, a horizontal body and
    a spout out over the tub; a hand shower in a holder, on a hose from the outlet under the body in a loop.
    Either a single lever on top and a slide rail above (`rail` = its bottom and top), or a shower system (`rain` =
    [top, arm reach, head diameter]): thermostat knobs at the ends, a riser pipe up from the middle with the
    holder on it, and an arm out from the wall at the top with a round rain head.
    `span` centers it, `z` = body axis height."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        chrome = materials.metal("Bath Mixer Chrome", cfg["finish"])
        hose_mat = materials.metal("Bath Shower Hose", "platinum")
        dark = materials.matte("Hand Shower Spray Face", "#2E2E30", 0.45)
        cs, z = (self.s0 + self.s1) / 2, cfg["z"]
        w = lambda s, d, zz: f.world(cs + s, d, zz)
        circle = lambda r: [(r * math.cos(2 * math.pi * k / 16), r * math.sin(2 * math.pi * k / 16)) for k in range(16)]

        for s in (-0.075, 0.075):
            geo.add_bevel(geo.cylinder("Bath Mixer Flange", w(s, 0.006, z), f.nrm, 0.03, 0.012, chrome, col, 48), 0.003)
            geo.cylinder("Bath Mixer Eccentric", w(s, 0.032, z), f.nrm, 0.011, 0.042, chrome, col, 32)
        bd = 0.066                                               # body axis off the wall
        geo.add_bevel(geo.cylinder("Bath Mixer Body", w(0, bd, z), f.u, 0.026, 0.3, chrome, col, 48), 0.008, 4)
        rain = cfg.get("rain")
        if rain:
            for s in (-0.17, 0.17):
                geo.add_bevel(geo.cylinder("Bath Mixer Knob", w(s, bd, z), f.u, 0.03, 0.04, chrome, col, 48), 0.006)
        else:
            geo.cylinder("Bath Mixer Cartridge", w(0, bd, z + 0.035), geo.Z, 0.02, 0.026, chrome, col, 40)
            geo.add_bevel(geo.frame_box("Bath Mixer Lever", f, cs - 0.007, bd - 0.012, z + 0.046, cs + 0.007,
                                        bd + 0.085, z + 0.058, chrome, col), 0.004)
        spout = [w(0, bd + 0.02, z - 0.008), w(0, bd + 0.1, z - 0.018), w(0, bd + 0.15, z - 0.032)]
        geo.sweep("Bath Mixer Spout", spout, f.u, circle(0.012), chrome, col, smooth_angle=60)
        geo.cylinder("Bath Mixer Aerator", w(0, bd + 0.152, z - 0.046), geo.Z, 0.0125, 0.016, chrome, col, 40)
        geo.cylinder("Bath Mixer Aerator Mesh", w(0, bd + 0.152, z - 0.0545), geo.Z, 0.009, 0.001, dark, col, 32)
        geo.cylinder("Bath Mixer Shower Outlet", w(0.11, bd, z - 0.036), geo.Z, 0.011, 0.024, chrome, col, 32)

        if rain:
            top, arm, dia = rain
            rd, zh = bd, z + 0.45
            geo.cylinder("Shower Riser", w(0, rd, (z + top) / 2), geo.Z, 0.011, top - z, chrome, col, 40)
            zb = top - 0.3                                       # wall bracket of the riser
            geo.add_bevel(geo.cylinder("Shower Riser Flange", w(0, 0.005, zb), f.nrm, 0.025, 0.01, chrome, col, 40),
                          0.003)
            geo.cylinder("Shower Riser Bracket", w(0, (0.01 + rd) / 2, zb), f.nrm, 0.009, rd - 0.01, chrome, col, 32)
            geo.cylinder("Shower Riser Clamp", w(0, rd, zb), geo.Z, 0.015, 0.03, chrome, col, 40)
            geo.cylinder("Shower Arm Joint", w(0, rd, top), geo.Z, 0.016, 0.034, chrome, col, 40)
            geo.cylinder("Shower Arm", w(0, rd + arm / 2, top), f.nrm, 0.01, arm, chrome, col, 32)
            geo.cylinder("Rain Head Joint", w(0, rd + arm, top - 0.016), geo.Z, 0.013, 0.032, chrome, col, 32)
            geo.add_bevel(geo.cylinder("Rain Head", w(0, rd + arm, top - 0.038), geo.Z, dia / 2, 0.012, chrome, col,
                                       96), 0.004)
            geo.cylinder("Rain Head Spray Face", w(0, rd + arm, top - 0.0445), geo.Z, dia / 2 - 0.012, 0.001, dark,
                         col, 96)
        else:
            r0, r1 = cfg["rail"]
            rd, zh = 0.05, r0 + 0.65 * (r1 - r0)
            geo.cylinder("Shower Rail", w(0, rd, (r0 + r1) / 2), geo.Z, 0.011, r1 - r0, chrome, col, 40)
            for zz in (r0, r1):
                geo.add_bevel(geo.cylinder("Shower Rail Flange", w(0, 0.005, zz), f.nrm, 0.025, 0.01, chrome, col,
                                           40), 0.003)
                geo.cylinder("Shower Rail Bracket", w(0, (0.01 + rd) / 2, zz), f.nrm, 0.01, rd - 0.01, chrome, col, 32)
                geo.cylinder("Shower Rail Cap", w(0, rd, zz), geo.Z, 0.015, 0.024, chrome, col, 40)
        geo.add_bevel(geo.frame_box("Shower Holder", f, cs - 0.02, rd - 0.016, zh - 0.025, cs + 0.02, rd + 0.045,
                                    zh + 0.025, chrome, col), 0.008, 4)
        tilt = math.radians(18)                                  # the handle leans out from the wall
        axis = (geo.Z * math.cos(tilt) + f.nrm * math.sin(tilt)).normalized()
        base = w(0, 0.1, zh - 0.13)
        geo.cylinder("Hand Shower Handle", base + axis * 0.1, axis, 0.013, 0.2, chrome, col, 40, radius2=0.016)
        face = (f.nrm * 0.55 - geo.Z * 0.835).normalized()       # spray face down and out over the tub
        head = base + axis * 0.215 + face * 0.012
        geo.add_bevel(geo.cylinder("Hand Shower Head", head, face, 0.055, 0.024, chrome, col, 64), 0.007, 4)
        geo.cylinder("Hand Shower Spray Face", head + face * 0.0125, face, 0.046, 0.001, dark, col, 64)

        # down and out from the outlet: no segment may run straight off the wall (the sweep plane's normal)
        hose = [w(0.11, bd + 0.002, z - 0.05), w(0.11, 0.085, z - 0.075), w(0.11, 0.1, 0.70)]
        for i in range(1, 12):                                   # round bottom of the loop
            a = math.pi * i / 12
            hose.append(w(0.075 + 0.035 * math.cos(a), 0.1, 0.70 - 0.035 * math.sin(a)))
        hose += [w(0.04, 0.1, 0.70), w(0.04, 0.1, z + 0.08), w(0.022, 0.1, zh - 0.32), w(0.006, 0.1, zh - 0.19),
                 base - axis * 0.004]
        geo.sweep("Bath Shower Hose", hose, f.nrm, circle(0.0065), hose_mat, col, smooth_angle=60)


class CeilingFan(_WallItem):
    """Exhaust fan on a ceiling duct: round white face flush under the ceiling with a dark ring of slots.
    `span` along the wall gives its diameter, `gap` its distance from that wall."""

    def build(self, col):
        cfg, f = self.cfg, self.f
        r = (self.s1 - self.s0) / 2
        c = f.world((self.s0 + self.s1) / 2, cfg["gap"] + r, self.h)
        ceiling = bpy.data.collections.get("Ceiling") or col     # hidden with the ceiling in dollhouse views
        white = materials.paint("Fan Face", cfg["color"], 0.35)
        dark = materials.matte("Fan Slots", "#3A3A3A", 0.8)
        geo.cylinder("Fan Face", c - geo.Z * 0.006, geo.Z, r, 0.012, white, ceiling, 64)
        geo.cylinder("Fan Slots", c - geo.Z * 0.0125, geo.Z, r * 0.8, 0.001, dark, ceiling, 64)
        geo.cylinder("Fan Cap", c - geo.Z * 0.0145, geo.Z, r * 0.64, 0.003, white, ceiling, 64)


FURNITURE = {"wardrobe": SlidingWardrobe, "cabinet": WallCabinet, "mirror": WallMirror, "pouf": Pouf,
             "radiator": Radiator, "sofa": Sofa, "tv": Tv, "intercom": Intercom, "curtains": Curtains, "niche_cabinet": NicheCabinet,
             "swing_wardrobe": SwingWardrobe, "drawer_unit": DrawerUnit, "bed": Bed, "chair": Chair,
             "air_conditioner": AirConditioner, "desk": Desk, "office_chair": OfficeChair, "desk_gear": DeskGear,
             "bathtub": Bathtub, "ceiling_fan": CeilingFan, "tiled_box": TiledBox, "wall_toilet": WallToilet,
             "appliance": Appliance, "appliance_column": ApplianceColumn, "basin_top": BasinTop,
             "bidet_shower": BidetShower, "towel_warmer": TowelWarmer, "bath_mixer": BathMixer}
