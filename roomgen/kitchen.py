"""Fitted kitchen from the plan: base, tall and upper cabinet modules along walls, milled fronts,
glass doors with glazing bars, handles, a countertop cut from an outline with a sink bowl,
built-in appliances and a backsplash."""

import math

import bpy

from . import geo, materials, plan
from .geo import WallFrame, Z

FRONT_T = 0.018   # front thickness; carcasses stop this short of the module depth
GAP = 0.003       # gap between fronts
FIELD = 0.008     # how far the panel of a milled front sits below its frame
GROOVE = 0.0012   # depth of the two decorative grooves along the outer edge


def _edge_grooves(top):
    """Two thin grooves 4-6 mm and 8-10 mm in from the edge, at height `top`."""
    return [(0.004, top), (0.0045, top - GROOVE), (0.0055, top - GROOVE), (0.006, top),
            (0.008, top), (0.0085, top - GROOVE), (0.0095, top - GROOVE), (0.010, top)]


def classic_profile(band):
    """Milled frame of a solid front: grooves, flat frame, slope down to the panel, small bead.
    a = inward from the front's edge, b = height above the panel."""
    flat, slope = band * 0.6, band * 0.3
    x = flat + slope
    return geo.profile(
        (0.0, 0.0), (0.0, FIELD - 0.001), (0.001, FIELD), *_edge_grooves(FIELD), (flat, FIELD),
        (x, 0.0035), (x, 0.0012),                       # quirk: a step that throws a shadow line
        geo.arc((x + 0.0022, 0.0012), 0.0022, 180, 0, 8),  # bead around the panel
        (x + 0.0055, 0.0),
    )


def glass_frame_profile(stile):
    """Frame of a glass door: grooves along the outer edge, chamfer toward the glass."""
    return geo.profile(
        (0.0, 0.0), (0.0, FRONT_T - 0.0008), (0.0008, FRONT_T), *_edge_grooves(FRONT_T),
        (stile - 0.007, FRONT_T), (stile, FRONT_T - 0.007), (stile, 0.0),
    )


def bar_profile(width):
    """Glazing bar chamfered on both sides; a runs across the bar."""
    h = width / 2
    return [(-h, 0.0), (-h, FRONT_T - 0.006), (-h + 0.006, FRONT_T), (h - 0.006, FRONT_T), (h, FRONT_T - 0.006), (h, 0.0)]


def front_frame(f, s0, s1, d0, d1):
    """Frame on a cabinet's front plane; handles fronts set at an angle to the wall."""
    p0, p1 = f.world(s0, d0, 0.0), f.world(s1, d1, 0.0)
    u = p1 - p0
    length = u.length
    u.normalize()
    nrm = Z.cross(u)
    if nrm.dot(f.nrm) < 0:
        nrm = -nrm
    return WallFrame("front", p0, u, nrm, length)


def _module_span(f, m, default_depth):
    """Wall positions of a module and its depth at each end (`taper` follows the span's order)."""
    c0, c1 = m["span"]
    t0, t1 = m.get("taper") or (m.get("depth") or default_depth,) * 2
    a, b = (f.s_at(c0), t0), (f.s_at(c1), t1)
    return (a, b) if a[0] <= b[0] else (b, a)


def _cut(target, cutter, name):
    """Subtract a hidden cutter box from `target`."""
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    mod = target.modifiers.new(name, "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = cutter
    mod.solver = "EXACT"
    if hasattr(mod, "material_mode"):
        mod.material_mode = "TRANSFER"


class Kitchen:
    def __init__(self, cfg, frames, room_height, floor_cfg):
        self.cfg, self.frames, self.h, self.floor_cfg = cfg, frames, room_height, floor_cfg
        c = cfg["colors"]
        self.front = materials.paint("Kitchen Fronts", c["fronts"], 0.4)
        self.top = materials.paint("Countertop", c["countertop"], 0.25)
        self.steel = materials.metal("Kitchen Steel", "chrome")
        self.black = materials.paint("Black Glass", "#0B0B0C", 0.05)
        self.glass = materials.frosted_glass("Cabinet Glass")
        self.handle = materials.metal("Kitchen Handles", cfg.get("handles", "dark_copper"))
        up = cfg["upper"]
        self.up_bottom, self.up_tiers, self.up_depth = up["bottom"], up["tiers"], up["depth"]
        self.up_top = self.up_bottom + sum(self.up_tiers)

    def build(self, collection, cutters):
        self.col = collection
        cfg = self.cfg
        for m in cfg["base"]:
            self._base(m)
        for m in cfg["tall"]:
            self._tall(m)
        for m in cfg["upper_modules"]:
            self._upper(m)
        self._upper_fillers()
        self._under_light()
        for p in cfg.get("end_panels", []):  # side fillers closing exposed ends of the runs
            f = self.frames[p["wall"]]
            s0, s1 = f.span(None, p)
            z0, z1 = (self.h if z == "ceiling" else z for z in p["z"])
            geo.frame_box("End Panel", f, s0, 0.0, z0, s1, p["depth"], z1, self.front, collection, bevel=0.001)
        top_z = cfg["base_top"]
        counter = geo.prism("Countertop", cfg["countertop_outline"], top_z - cfg["countertop_thickness"], top_z,
                            self.top, collection)
        for m in cfg["base"]:
            if m["type"] == "sink":
                self._sink(m, counter, cutters)
        self._backsplash(top_z)

    def _backsplash(self, top_z):
        """Backsplash panels; "floor_tile" finish lays the floor's tile in rows from `tile_origin`."""
        cfg = self.cfg
        for i, b in enumerate(cfg["backsplash"]):
            f = self.frames[b["wall"]]
            s0, s1 = f.span(None, b)
            if cfg.get("backsplash_finish") == "floor_tile":
                along = "X" if abs(f.u.x) > abs(f.u.y) else "Y"
                mat = plan.tile_material(f"Backsplash Tile {i + 1}", self.floor_cfg, (b["tile_origin"], top_z),
                                         (along, "Z"))
            else:
                mat = materials.paint("Backsplash", cfg["colors"]["backsplash"], 0.2)
            # An end on an outside corner is mitred at 45°: the face runs past the end by the tile thickness.
            t, miter = 0.008, b.get("miter", [])
            a0 = s0 - (t if "start" in miter else 0.0)
            a1 = s1 + (t if "end" in miter else 0.0)
            pts = [f.world(s0, 0.0, 0.0), f.world(s1, 0.0, 0.0), f.world(a1, t, 0.0), f.world(a0, t, 0.0)]
            geo.prism("Backsplash", [(q.x, q.y) for q in pts], top_z, self.up_bottom, mat, self.col)

    # --- fronts -----------------------------------------------------------------------------

    def _handle(self, ff, a, b, z0, z1, where):
        """Bar handle on two posts, centered across the front near its top or bottom edge."""
        if where is None:
            return
        if z1 - z0 < 0.12:
            z = (z0 + z1) / 2
        else:
            z = z1 - 0.045 if where == "top" else z0 + 0.045
        centers = 0.128 if b - a >= 0.3 else 0.096
        mid = (a + b) / 2
        for s in (mid - centers / 2, mid + centers / 2):
            geo.cylinder("Handle Post", ff.world(s, FRONT_T + 0.0125, z), ff.nrm, 0.005, 0.025, self.handle, self.col,
                         16)
        geo.cylinder("Handle Bar", ff.world(mid, FRONT_T + 0.028, z), ff.u, 0.006, centers + 0.03, self.handle,
                     self.col, 20)

    def _door(self, ff, a, b, z0, z1, handle=None, framed=True):
        a, b, z0, z1 = a + GAP / 2, b - GAP / 2, z0 + GAP / 2, z1 - GAP / 2
        band = min(0.075, (b - a) * 0.2, (z1 - z0) * 0.2)
        if framed and self.cfg["style"] == "classic" and band > 0.02:
            geo.frame_box("Front", ff, a, 0.0, z0, b, FRONT_T - FIELD, z1, self.front, self.col, bevel=0.0008)
            geo.sweep_rect("Front Frame", ff, FRONT_T - FIELD, a, b, z0, z1, classic_profile(band), self.front,
                           self.col)
        else:
            geo.frame_box("Front", ff, a, 0.0, z0, b, FRONT_T, z1, self.front, self.col, bevel=0.0015)
        self._handle(ff, a, b, z0, z1, handle)

    def _doors(self, ff, z0, z1, n=1, handle=None):
        step = ff.length / n
        for i in range(n):
            self._door(ff, i * step, (i + 1) * step, z0, z1, handle)

    def _glass_door(self, ff, a, b, z0, z1, handle="bottom", stile=0.06, bar=0.024, rows=(1.0, 2.1, 1.0), cols=2):
        """Framed door with frosted glass divided by glazing bars (2 x 3 by default)."""
        a, b, z0, z1 = a + GAP / 2, b - GAP / 2, z0 + GAP / 2, z1 - GAP / 2
        geo.sweep_rect("Glass Door Frame", ff, 0.0, a, b, z0, z1, glass_frame_profile(stile), self.front, self.col)
        ia, ib, iz0, iz1 = a + stile, b - stile, z0 + stile, z1 - stile
        unit = (iz1 - iz0 - bar * (len(rows) - 1)) / sum(rows)
        z = iz0
        for r in rows[:-1]:
            z += r * unit
            geo.sweep("Glazing Bar", [ff.world(ia - 0.002, 0.0, z + bar / 2), ff.world(ib + 0.002, 0.0, z + bar / 2)],
                      ff.nrm, bar_profile(bar), self.front, self.col)
            z += bar
        col_w = (ib - ia - bar * (cols - 1)) / cols
        for c in range(1, cols):
            s = ia + c * col_w + (c - 0.5) * bar
            geo.sweep("Glazing Bar", [ff.world(s, 0.0, iz0 - 0.002), ff.world(s, 0.0, iz1 + 0.002)], ff.nrm,
                      bar_profile(bar), self.front, self.col)
        geo.frame_box("Glass Pane", ff, ia - 0.004, 0.006, iz0 - 0.004, ib + 0.004, 0.010, iz1 + 0.004, self.glass,
                      self.col)
        self._handle(ff, a, b, z0, z1, handle)

    def _panel(self, ff, z0, z1, mat=None):
        geo.frame_box("Panel", ff, GAP / 2, 0.0, z0, ff.length - GAP / 2, FRONT_T, z1, mat or self.front, self.col,
                      bevel=0.001)

    def _carcass(self, f, a, b, z0, z1):
        (s0, d0), (s1, d1) = a, b
        pts = [f.world(s0, 0.0, 0.0), f.world(s1, 0.0, 0.0), f.world(s1, d1 - FRONT_T, 0.0), f.world(s0, d0 - FRONT_T, 0.0)]
        geo.prism("Carcass", [(p.x, p.y) for p in pts], z0, z1, self.front, self.col)
        return front_frame(f, s0, s1, d0 - FRONT_T, d1 - FRONT_T)

    def _open_carcass(self, f, a, b, z0, z1, t=0.016):
        """Hollow cabinet box (back, sides, top, bottom, two shelves) for doors you can see through."""
        (s0, d0), (s1, _) = a, b
        inner = d0 - FRONT_T

        def board(name, *box):
            geo.frame_box(name, f, *box, self.front, self.col, bevel=0.0005)

        board("Cabinet Back", s0, 0.0, z0, s1, t, z1)
        board("Cabinet Side", s0, 0.0, z0, s0 + t, inner, z1)
        board("Cabinet Side", s1 - t, 0.0, z0, s1, inner, z1)
        board("Cabinet Bottom", s0 + t, t, z0, s1 - t, inner, z0 + t)
        board("Cabinet Top", s0 + t, t, z1 - t, s1 - t, inner, z1)
        for k in (1, 2):
            zs = z0 + (z1 - z0) * k / 3
            board("Cabinet Shelf", s0 + t, t, zs - t / 2, s1 - t, inner - 0.01, zs + t / 2)
        return front_frame(f, s0, s1, inner, inner)

    # --- modules ----------------------------------------------------------------------------

    def _base(self, m):
        cfg, f = self.cfg, self.frames[m["wall"]]
        a, b = _module_span(f, m, cfg["depth"])
        plinth, top = cfg["plinth"], cfg["base_top"] - cfg["countertop_thickness"]
        # Under an inset sink the (solid) carcass stops below the bowl; the fronts still run to the countertop.
        z1 = top - m["bowl"][2] - 0.04 if m.get("sink") else top
        ff = self._carcass(f, a, b, plinth, z1)
        geo.frame_box("Plinth", ff, 0.0, -0.066, 0.0, ff.length, -0.05, plinth, self.front, self.col)
        kind = m["type"]
        if kind == "blind":
            return
        if kind == "filler":
            self._panel(ff, plinth, top)
        elif kind == "door":
            self._doors(ff, plinth, top, 1, "top")
        elif kind in ("doors2", "sink"):
            self._doors(ff, plinth, top, m.get("doors", 2), "top")
        elif kind == "drawers":
            n = m.get("count", 3)
            step = (top - plinth) / n
            for i in range(n):
                self._door(ff, 0.0, ff.length, plinth + i * step, plinth + (i + 1) * step, "top")
        elif kind == "oven":
            drawer_top = plinth + 0.14
            self._door(ff, 0.0, ff.length, plinth, drawer_top, "top")
            geo.frame_box("Oven Door", ff, 0.004, 0.0, drawer_top + 0.004, ff.length - 0.004, FRONT_T + 0.004,
                          top - 0.004, self.black, self.col, bevel=0.002)
            geo.frame_box("Oven Handle", ff, 0.06, FRONT_T + 0.012, top - 0.05, ff.length - 0.06, FRONT_T + 0.024,
                          top - 0.035, self.steel, self.col, bevel=0.004)
            if m.get("hob"):
                mid_s = (a[0] + b[0]) / 2
                mid_d = (a[1] + b[1]) / 4
                c = f.world(mid_s, mid_d, cfg["base_top"])
                hf = WallFrame("hob", c - f.u * 0.295 - f.nrm * 0.26, f.u, f.nrm, 0.59)
                geo.frame_box("Hob", hf, 0.0, 0.0, 0.0, 0.59, 0.52, 0.006, self.black, self.col, bevel=0.002)

    def _tall(self, m):
        cfg, f = self.cfg, self.frames[m["wall"]]
        a, b = _module_span(f, m, cfg["depth"])
        plinth = cfg["plinth"]
        ff = self._carcass(f, a, b, plinth, self.h)  # to the ceiling: the filler above sits flush with the fronts
        geo.frame_box("Plinth", ff, 0.0, -0.066, 0.0, ff.length, -0.05, plinth, self.front, self.col)
        cuts = [plinth, *m["splits"], self.up_top]
        for i, (z0, z1) in enumerate(zip(cuts, cuts[1:])):
            self._doors(ff, z0, z1, 1, "top" if i == 0 else "bottom")  # lowest door is reached from above
        self._panel(ff, self.up_top, self.h)

    def _upper(self, m):
        f = self.frames[m["wall"]]
        a, b = _module_span(f, m, self.up_depth)
        z0 = self.up_bottom
        z1 = z0 + self.up_tiers[0]
        kind = m["type"]
        if kind == "filler":
            ff = self._carcass(f, a, b, z0, self.up_top)
            self._panel(ff, z0, self.up_top)
            return
        glass = m.get("glass", False)
        ff = self._open_carcass(f, a, b, z0, self.up_top) if glass else self._carcass(f, a, b, z0, self.up_top)
        if kind == "end":
            return
        if m.get("full_height"):  # one door over both tiers
            z1 = self.up_top
        if kind in ("door", "doors2", "hood"):
            n = 2 if kind == "doors2" else 1
            step = ff.length / n
            for i in range(n):
                if glass:
                    self._glass_door(ff, i * step, (i + 1) * step, z0, z1)
                else:
                    self._door(ff, i * step, (i + 1) * step, z0, z1, "bottom")
            if kind == "hood":  # built-in hood: only its underside shows, from below
                geo.frame_box("Hood Underside", ff, 0.02, -self.up_depth + FRONT_T + 0.02, z0 - 0.002, ff.length - 0.02,
                              -0.01, z0, self.steel, self.col)
        elif kind == "microwave":
            mw_top = z0 + 0.40
            geo.frame_box("Microwave", ff, 0.004, 0.0, z0 + 0.004, ff.length - 0.004, FRONT_T + 0.002, mw_top - 0.004,
                          self.black, self.col, bevel=0.002)
            self._doors(ff, mw_top, z1, 1, "bottom")
        z = z1
        for tier in self.up_tiers[1:]:  # lift-up fronts above the main tier
            if z >= self.up_top - 1e-6:
                break
            self._doors(ff, z, z + tier, 1, "bottom")
            z += tier

    def _upper_fillers(self):
        """One continuous filler to the ceiling over each wall's run of upper cabinets."""
        runs = {}
        for m in self.cfg["upper_modules"]:
            f = self.frames[m["wall"]]
            a, b = _module_span(f, m, self.up_depth)
            lo, hi = runs.get(m["wall"], (a[0], b[0]))
            runs[m["wall"]] = (min(lo, a[0]), max(hi, b[0]))
        for wall, (s0, s1) in runs.items():
            geo.frame_box("Upper Filler", self.frames[wall], s0, self.up_depth - FRONT_T, self.up_top, s1,
                          self.up_depth, self.h, self.front, self.col, bevel=0.001)

    def _under_light(self):
        """LED profile under the upper cabinets, `d` from the wall (mid-depth), washing the countertop.
        `runs` give its spans along the walls, so it can skip the hood and meet in the corner."""
        ul = self.cfg.get("under_light")
        if not ul:
            return
        led = materials.emitter("Under Cabinet LED", ul["temperature"], ul["glow"])
        w, d, z = ul["width"], ul["d"], self.up_bottom
        for k, run in enumerate(ul["runs"]):
            f = self.frames[run["wall"]]
            s0, s1 = f.span(None, run)
            tag = f"Under Cabinet LED {k + 1}"
            geo.frame_box(f"{tag} Profile", f, s0, d - w / 2 - 0.002, z - 0.007, s1, d + w / 2 + 0.002, z,
                          self.steel, self.col)
            geo.frame_box(f"{tag} Diffuser", f, s0 + 0.003, d - w / 2, z - 0.0075, s1 - 0.003, d + w / 2, z - 0.0068,
                          led, self.col)["light_group"] = "kitchen_led"
            light = bpy.data.lights.new(tag, "AREA")
            light.shape = "RECTANGLE"
            light.size, light.size_y = s1 - s0, w
            light.energy = ul["power"] * (s1 - s0)  # W per meter of strip
            light.use_temperature = True
            light.temperature = ul["temperature"]
            obj = bpy.data.objects.new(tag, light)
            obj.location = f.world((s0 + s1) / 2, d, z - 0.008)
            obj.rotation_euler = (0.0, 0.0, math.atan2(f.u.y, f.u.x))
            obj["light_group"] = "kitchen_led"
            self.col.objects.link(obj)

    def _sink(self, m, counter, cutters):
        cfg, f = self.cfg, self.frames[m["wall"]]
        a, b = _module_span(f, m, cfg["depth"])
        bw, bd, bh = m.get("bowl", (0.5, 0.4, 0.18))
        top = cfg["base_top"]
        mid_s, mid_d = (a[0] + b[0]) / 2, (a[1] + b[1]) / 4 + 0.03
        if m.get("sink"):
            fs, fd = self._inset_sink(f, m["sink"], (bw, bd, bh), mid_d, top, counter, cutters)
        else:  # the bowl cut into the countertop itself
            _cut(counter, geo.frame_box("Cutter Sink", f, mid_s - bw / 2, mid_d - bd / 2, top - bh, mid_s + bw / 2,
                                        mid_d + bd / 2, top + 0.05, self.steel, cutters), "Sink")
            fs, fd = mid_s, mid_d - bd / 2 - 0.05  # faucet behind the bowl
        geo.cylinder("Faucet Base", f.world(fs, fd, top + 0.025), Z, 0.025, 0.05, self.steel, self.col)
        geo.cylinder("Faucet Column", f.world(fs, fd, top + 0.2), Z, 0.012, 0.3, self.steel, self.col, 24)
        spout_mid = f.world(fs, fd + 0.09, top + 0.34)  # the spout reaches toward the room
        geo.cylinder("Faucet Spout", spout_mid, f.nrm, 0.011, 0.2, self.steel, self.col, 24)
        geo.cylinder("Faucet Nozzle", f.world(fs, fd + 0.18, top + 0.31), Z, 0.012, 0.06, self.steel, self.col, 24)

    def _inset_sink(self, f, s, bowl, mid_d, top, counter, cutters):
        """Inset composite sink set into the countertop: one bowl and a ribbed drainboard ("wing") on a rim.
        `wing` is the drainboard's side as seen facing the wall; the drain sits `drain` from the bowl's wing-side
        edge. Returns the faucet position (s, d): on the back rim behind the bowl."""
        s0, s1 = f.span(None, s)
        sd, rim, front = s["depth"], s["rim"], s["front_rim"]
        bw, bd, bh = bowl
        mat = materials.paint("Sink Composite", s["color"], 0.55)
        d0, d1 = mid_d - sd / 2, mid_d + sd / 2
        lip = 0.008  # the rim stands this proud of the countertop
        _cut(counter, geo.frame_box("Cutter Sink Hole", f, s0 + 0.012, d0 + 0.012, top - 0.25, s1 - 0.012,
                                    d1 - 0.012, top + 0.05, mat, cutters), "Sink Hole")
        body = geo.frame_box("Sink", f, s0, d0, top - bh - 0.012, s1, d1, top + lip, mat, self.col, bevel=0.004)
        # Facing the wall (looking along -nrm) your left is (nrm.y, -nrm.x); is that +s along this wall?
        plus_s_is_left = f.u.x * f.nrm.y - f.u.y * f.nrm.x > 0
        wing_plus_s = (s.get("wing", "left") == "left") == plus_s_is_left
        if wing_plus_s:
            b0, b1 = s0 + rim, s0 + rim + bw
            w0, w1 = b1 + rim, s1 - rim
        else:
            b0, b1 = s1 - rim - bw, s1 - rim
            w0, w1 = s0 + rim, b0 - rim
        bd1 = d1 - front
        bd0 = bd1 - bd
        floor = top + lip - bh
        _cut(body, geo.frame_box("Cutter Sink Bowl", f, b0, bd0, floor, b1, bd1, top + 0.05, mat, cutters,
                                 bevel=0.03, bevel_segments=6), "Bowl")
        wing_floor = top + lip - 0.006
        _cut(body, geo.frame_box("Cutter Sink Wing", f, w0, bd0, wing_floor, w1, bd1, top + 0.05, mat, cutters,
                                 bevel=0.012, bevel_segments=4), "Wing")
        ribs = max(3, round((w1 - w0) / 0.045))
        for i in range(ribs):  # grooves running front to back, draining toward the bowl
            c = w0 + (w1 - w0) * (i + 0.5) / ribs
            _cut(body, geo.frame_box(f"Cutter Sink Rib {i + 1}", f, c - 0.004, bd0 + 0.03, wing_floor - 0.003,
                                     c + 0.004, bd1 - 0.03, wing_floor + 0.01, mat, cutters, bevel=0.003),
                 f"Rib {i + 1}")
        ds = b1 - s["drain"] if wing_plus_s else b0 + s["drain"]
        dd = (bd0 + bd1) / 2
        geo.cylinder("Sink Drain", f.world(ds, dd, floor + 0.002), Z, 0.042, 0.004, self.steel, self.col)
        geo.cylinder("Sink Drain Hole", f.world(ds, dd, floor + 0.003), Z, 0.03, 0.004, mat, self.col)
        return (b0 + b1) / 2, (d0 + bd0) / 2
