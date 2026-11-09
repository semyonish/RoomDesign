"""Doors in wall openings: reveal linings, frame, paneled leaf, hardware, mitered casings
and an optional classical portal (frieze and cornice, optionally on pilasters)."""

import math

import bpy
from mathutils import Matrix

from . import geo, materials
from .geo import arc, profile

LINING = 0.012      # reveal lining boards (доборы) covering the opening sides
FRAME_W = 0.03      # visible width of the door frame (коробка)
GAP = 0.003         # leaf-to-frame clearance
FLOOR_GAP = 0.008   # clearance under the leaf
CASING_REVEAL = 0.006  # casing stands back from the lining face by this much
PLINTH_H = 0.22     # pilaster base block height
CAPITAL_H = 0.07    # pilaster top block height
BLOCK_PAD = 0.008   # base/capital blocks overhang the pilaster by this much

PANEL_MOULDING = profile(
    (0.0, 0.0), (0.0, 0.004),
    arc((0.005, 0.004), 0.005, 180, 90, 6),
    (0.008, 0.009),
    arc((0.016, 0.009), 0.008, 180, 270, 6),
    (0.02, 0.001), (0.02, 0.0),
)
PANEL_MOULDING_W = 0.02


def casing_profile(style, width, depth, outer_round=0.008):
    """a = distance from the opening edge outward, b = projection from the wall."""
    if style == "simple":
        # Standard MDF casing: flat face, small round on the inner edge, larger round outside.
        r = min(outer_round, depth * 0.7)
        return profile(
            (0.0, 0.0), (0.0, depth - 0.003),
            arc((0.003, depth - 0.003), 0.003, 180, 90, 4),
            (width - r, depth),
            arc((width - r, depth - r), r, 90, 0, 6),
            (width, 0.0),
        )
    sa, sb = width / 0.09, depth / 0.022
    pts = profile(
        (0.0, 0.0), (0.0, 0.012),
        arc((0.006, 0.012), 0.006, 180, 90, 6),   # inner bead
        (0.012, 0.018), (0.012, 0.016), (0.016, 0.016),
        (0.062, 0.022),                           # sloped field
        arc((0.062, 0.012), 0.010, 90, 0, 8),     # outer ovolo
        (0.072, 0.009), (0.082, 0.009),
        arc((0.082, 0.004), 0.005, 90, 0, 5),
        (0.09, 0.004), (0.09, 0.0),
    )
    return [(a * sa, b * sb) for a, b in pts]


def cornice_profile(base_projection):
    """Crown profile: a = height above the frieze, b = projection from the wall."""
    b0 = base_projection
    return profile(
        (0.0, 0.0), (0.0, b0), (0.008, b0),
        arc((0.008, b0 + 0.02), 0.02, -90, 0, 8),   # cove
        (0.034, b0 + 0.02), (0.034, b0 + 0.033),
        (0.068, b0 + 0.033),                        # corona
        arc((0.068, b0 + 0.023), 0.010, 90, 0, 6),  # top ovolo
        (0.078, b0 + 0.018), (0.09, b0 + 0.018),
        (0.09, 0.0),
    )


class Door:
    def __init__(self, cfg, frame):
        self.cfg = cfg
        self.f = frame
        self.entrance = cfg["kind"] == "entrance"
        self.rd, self.lt = cfg["reveal_depth"], cfg["leaf_thickness"]
        side_allowance = 2 * (LINING + FRAME_W + GAP)
        top_allowance = FLOOR_GAP + GAP + FRAME_W + LINING
        if cfg["span"] is not None:
            # Opening given by plan coordinates; the leaf is whatever fits inside frame and linings.
            self.s0, self.s1 = frame.span(None, cfg)
            self.ow = self.s1 - self.s0
            self.w = cfg["leaf_width"] or self.ow - side_allowance
        else:
            self.w = cfg["width"]
            self.ow = self.w + side_allowance
            self.s0, self.s1 = frame.span(self.ow, cfg)
        if cfg["opening_height"] is not None:
            self.oh = cfg["opening_height"]
            self.h = cfg["leaf_height"] or self.oh - top_allowance
        else:
            self.h = cfg["height"]
            self.oh = self.h + top_allowance
        # The frame fills whatever the leaf leaves of the opening.
        self.fw = (self.ow - self.w) / 2 - LINING - GAP
        self.ft = self.oh - self.h - FLOOR_GAP - GAP - LINING

        cas, por = cfg["casing"], cfg["portal"]
        self.cw = cas["width"] if cas["enabled"] else 0.0
        self.cd, self.cstyle, self.cround = cas["depth"], cas["profile"], cas["outer_round"]
        self.cs0, self.cs1 = self.s0 + CASING_REVEAL, self.s1 - CASING_REVEAL
        self.cz = self.oh - CASING_REVEAL
        self.portal = por["enabled"]
        self.pilasters = self.portal and por["pilasters"]
        self.pw, self.pd, self.fh = por["pilaster_width"], por["pilaster_depth"], por["frieze_height"]
        # Pilasters tuck 3 mm under the casing's outer edge.
        self.pil_in = (self.cs0 - self.cw + 0.003, self.cs1 + self.cw - 0.003)
        self.pil_out = (self.pil_in[0] - self.pw, self.pil_in[1] + self.pw)

    @property
    def opening(self):
        return (self.s0, self.s1, 0.0, self.oh)

    @property
    def floor_depth(self):
        """How far the room's floor runs into the opening: under the threshold, or to the middle of the leaf."""
        if self.cfg.get("floor_depth") is not None:  # measured joint, e.g. tile 8 cm into the doorway
            return self.cfg["floor_depth"]
        return self.rd if self.entrance else self.rd + self.lt / 2

    def floor_depths(self):
        """The floor patch's depth at both ends of the opening: up to a straight tile joint `floor_to` (a plan x or y)
        across a skewed wall, else floor_depth at both."""
        c = self.cfg.get("floor_to")
        if c is None:
            return self.floor_depth, self.floor_depth
        k = 0 if abs(self.f.nrm.x) > abs(self.f.nrm.y) else 1
        return tuple((self.f.world(s, 0.0, 0.0)[k] - c) / self.f.nrm[k] for s in (self.s0, self.s1))

    @property
    def footprint(self):
        """Span along the wall occupied at floor level; the baseboard stops here."""
        if self.pilasters:
            return (self.pil_out[0] - BLOCK_PAD, self.pil_out[1] + BLOCK_PAD)
        return (self.cs0 - self.cw, self.cs1 + self.cw)

    @property
    def footprint_rect(self):
        a, b = self.footprint
        return geo.rect(self.f.world(a, -0.05, 0.0), self.f.world(b, 0.05, 0.0))

    @property
    def far_footprint_rect(self):
        """The other room's floor line under the far casing: that room's baseboard butts into its outer edge."""
        if not self.cfg.get("far_casing") or not self.cw:
            return None
        ov, t = self.cfg["far_casing"].get("overlap", 0.02), self.f.thickness + self.cfg["far_casing"].get("finish_depth", 0.0)
        a, b = self.s0 + ov - self.cw, self.s1 - ov + self.cw
        return geo.rect(self.f.world(a, -t - 0.05, 0.0), self.f.world(b, -t + 0.05, 0.0))

    def build(self, collection):
        tag = f"{self.cfg['kind']} {self.f.name}"
        if self.cfg.get("finish") == "oak":
            self.paint = materials.veneer(f"Door Oak {tag}", self.cfg["color"])
        else:
            self.paint = materials.paint(f"Door Paint {tag}", self.cfg["color"])
        self.metal = materials.metal(f"Door Hardware {tag}", self.cfg["hardware"])
        self.glass = materials.glass_dark(f"Door Glass {tag}")
        frame_color = self.cfg["frame_color"]  # door frame (коробка) in its own color, e.g. a dark steel frame
        self.frame_mat = materials.paint(f"Door Frame {tag}", frame_color, 0.45) if frame_color else self.paint
        self.col = collection
        self.tag = tag.title()
        before = set(collection.objects)  # this door's parts: two doors on one wall share their names
        self._reveal()
        self._leaf()
        self._hardware()
        if self.cw:
            self._casing()
        if self.cfg.get("far_casing"):
            self._far_side()
        if self.portal:
            self._portal()
        self.parts = [o for o in collection.objects if o not in before]
        if self.cfg["open"]:
            self._swing(math.radians(self.cfg["open"]))

    def _swing(self, angle):
        """Open the leaf by `angle` about its hinges, into the room it opens to: the far one when the leaf is flush
        with the far face (hinges on that side), else toward us. Leaf, mouldings and handles turn; the frame,
        casings and hinge knuckles stay."""
        ls0, ls1, _, _ = self.leaf
        hinge_s = ls0 if self.cfg["handle_side"] == "right" else ls1  # hinges opposite the lock
        far = self.cfg.get("far_casing")
        opens_far = bool(far) and abs(self.f.thickness + far.get("finish_depth", 0.0) - self.rd - self.lt) < 0.005
        pivot = self.f.world(hinge_s, -self.rd - self.lt if opens_far else -self.rd, 0.0)
        along = self.f.u * (1.0 if hinge_s == ls0 else -1.0)      # hinge → lock while closed
        into = -self.f.nrm if opens_far else self.f.nrm            # the room it swings into
        hinge = bpy.data.objects.new(f"{self.tag} Swing", None)
        hinge.location = pivot
        self.col.objects.link(hinge)
        names = tuple(f"{self.tag} {p}" for p in ("Leaf", "Handle", "Far Leaf", "Far Handle", "Thumbturn", "Night Latch",
                                                  "Lever Lock", "Peephole"))
        for obj in self.parts:
            if obj.name.startswith(names):
                obj.parent = hinge
                obj.matrix_parent_inverse = Matrix.Translation(pivot).inverted()
        hinge.rotation_euler.z = math.copysign(angle, along.cross(into).z)

    def _box(self, name, s0, d0, z0, s1, d1, z1, mat=None, bevel=0.0015, segments=3):
        return geo.frame_box(f"{self.tag} {name}", self.f, s0, d0, z0, s1, d1, z1, mat or self.paint, self.col,
                             bevel, segments)  # follows the wall even when it is slightly skewed

    def _reveal(self):
        s0, s1, oh = self.s0, self.s1, self.oh
        front = -self.rd + 0.006          # frame face stands slightly proud of the leaf
        back = -self.rd - self.lt
        lined = self.rd >= 0.02
        if lined:
            self._box("Reveal L", s0, front, 0.0, s0 + LINING, 0.0, oh)
            self._box("Reveal R", s1 - LINING, front, 0.0, s1, 0.0, oh)
            self._box("Reveal Top", s0 + LINING, front, oh - LINING, s1 - LINING, 0.0, oh)  # butts between the sides
        # A leaf flush with the wall (opens toward us) has no reveal to line: the frame fills the opening.
        inset = LINING if lined else 0.0
        fw, ft = self.fw + LINING - inset, self.ft + LINING - inset
        fi0, fi1, ftop = s0 + inset, s1 - inset, oh - inset
        fm = self.frame_mat
        self._box("Frame L", fi0, back, 0.0, fi0 + fw, front, ftop, mat=fm, bevel=0.002)
        self._box("Frame R", fi1 - fw, back, 0.0, fi1, front, ftop, mat=fm, bevel=0.002)
        # The head butts between the jambs: overlapping coplanar faces would shadow each other black in Cycles.
        self._box("Frame Top", fi0 + fw, back, ftop - ft, fi1 - fw, front, ftop, mat=fm, bevel=0.002)
        if not lined and not self.entrance:  # the leaf opens toward us: its hinges show on the jamb
            ls0, ls1 = s0 + LINING + self.fw + GAP, s1 - LINING - self.fw - GAP
            s_hinge = ls0 - GAP / 2 if self.cfg["handle_side"] == "right" else ls1 + GAP / 2
            for i, zc in enumerate((FLOOR_GAP + 0.25, FLOOR_GAP + self.h - 0.25)):
                geo.cylinder(f"{self.tag} Hinge {i + 1}", self.f.world(s_hinge, front + 0.004, zc), geo.Z, 0.0065,
                             0.10, materials.metal(f"Door Hinge {self.tag}", self.cfg["hardware"]), self.col, 16)
        if self.entrance:
            self._box("Threshold", fi0 + fw, back, 0.0, fi1 - fw, -self.rd + 0.02, 0.012,
                      mat=fm if self.cfg["frame_color"] else self.metal, bevel=0.002)

    def _leaf(self):
        rd = self.rd
        ls0 = self.s0 + LINING + self.fw + GAP
        ls1 = self.s1 - LINING - self.fw - GAP
        lz0, lz1 = FLOOR_GAP, FLOOR_GAP + self.h
        self.leaf = (ls0, ls1, lz0, lz1)
        self._box("Leaf", ls0, -rd - self.lt, lz0, ls1, -rd, lz1, bevel=0.003)
        if self.cfg["style"] != "classic":
            return
        cfg = self.cfg
        if cfg["panels"]:  # [[bottom, top], ...] as fractions of the leaf height, side margins as a fraction
            stile = cfg["stile"] * (ls1 - ls0)
            panels = [(lz0 + a * self.h, lz0 + b * self.h) for a, b in cfg["panels"]]
        else:
            stile = 0.12 if self.w >= 0.8 else 0.1
            panels = [(lz0 + 0.20, lz0 + 0.85), (lz0 + 1.00, lz1 - 0.12)]
        k = cfg["moulding_scale"]
        moulding = [(a * k, b * k) for a, b in PANEL_MOULDING]
        self.panels = [(ls0 + stile, ls1 - stile, pz0, pz1) for pz0, pz1 in panels]  # the far side mirrors them
        for i, (pz0, pz1) in enumerate(panels):
            ps0, ps1 = ls0 + stile, ls1 - stile
            geo.sweep_rect(f"{self.tag} Leaf Moulding {i + 1}", self.f, -rd, ps0, ps1, pz0, pz1,
                           moulding, self.paint, self.col)
            if cfg["raised"]:
                m = PANEL_MOULDING_W * k + 0.004
                geo.raised_panel(f"{self.tag} Leaf Panel {i + 1}", self.f, -rd, ps0 + m, ps1 - m, pz0 + m, pz1 - m,
                                 inset=0.035, rise=0.007, material=self.paint, collection=self.col)

    def _cyl(self, name, s, d, z, r, depth, mat):
        geo.cylinder(f"{self.tag} {name}", self.f.world(s, d, z), self.f.nrm, r, depth, mat, self.col)

    def _hardware(self):
        rd = self.rd
        ls0, ls1, lz0, _ = self.leaf
        lock_right = self.cfg["handle_side"] == "right"
        s_lock = ls1 - 0.065 if lock_right else ls0 + 0.065
        toward_hinge = -1.0 if lock_right else 1.0
        zh = lz0 + 1.0

        self._cyl("Handle Rosette", s_lock, -rd + 0.005, zh, 0.026, 0.01, self.metal)
        self._cyl("Handle Stem", s_lock, -rd + 0.032, zh, 0.008, 0.044, self.metal)
        self._box("Handle Lever", s_lock, -rd + 0.044, zh - 0.009, s_lock + toward_hinge * 0.135, -rd + 0.062,
                  zh + 0.009, mat=self.metal, bevel=0.006, segments=4)
        if not self.entrance:
            return

        # Inside face of a steel entrance door, all on the lock vertical: cylinder thumbturn under the handle,
        # night latch knob above it, lever-lock (сувальдный) keyhole higher up, peephole on top.
        dark = self.glass
        zc = zh - 0.085
        self._cyl("Thumbturn Rosette", s_lock, -rd + 0.004, zc, 0.022, 0.008, self.metal)
        self._box("Thumbturn", s_lock - 0.006, -rd + 0.008, zc - 0.017, s_lock + 0.006, -rd + 0.028, zc + 0.017,
                  mat=self.metal, bevel=0.004, segments=4)
        zn = zh + 0.14
        self._cyl("Night Latch Rosette", s_lock, -rd + 0.003, zn, 0.017, 0.006, self.metal)
        self._cyl("Night Latch Knob", s_lock, -rd + 0.013, zn, 0.009, 0.014, self.metal)
        zs = zh + 0.30
        self._cyl("Lever Lock Escutcheon", s_lock, -rd + 0.003, zs, 0.021, 0.006, self.metal)
        self._cyl("Lever Lock Keyhole", s_lock, -rd + 0.0062, zs + 0.005, 0.0045, 0.001, dark)
        self._box("Lever Lock Slot", s_lock - 0.0022, -rd + 0.0057, zs - 0.012, s_lock + 0.0022, -rd + 0.0063,
                  zs + 0.004, mat=dark, bevel=0.0)
        zp = lz0 + 1.5  # peephole above the locks, on their vertical
        self._cyl("Peephole", s_lock, -rd + 0.006, zp, 0.013, 0.012, self.metal)
        self._cyl("Peephole Lens", s_lock, -rd + 0.0125, zp, 0.007, 0.002, self.glass)

    def _casing(self):
        w = self.f.world
        path = [w(self.cs0, 0, 0), w(self.cs0, 0, self.cz), w(self.cs1, 0, self.cz), w(self.cs1, 0, 0)]
        geo.sweep(f"{self.tag} Casing", path, self.f.nrm, casing_profile(self.cstyle, self.cw, self.cd, self.cround),
                  self.paint, self.col, side=1.0)

    def _far_side(self):
        """The other room's side: linings from the frame to that wall face, and a casing whose inner edge
        sits `overlap` inside the opening, over the frame (so a 7 cm casing takes ~5 cm of wall).
        `finish_depth`: that room's wall finish past the wall (e.g. tile), the casing sits on top of it."""
        f, t = self.f, self.f.thickness + self.cfg["far_casing"].get("finish_depth", 0.0)
        back = -self.rd - self.lt                       # back face of the frame
        if t + back > 0.002:
            self._box("Far Reveal L", self.s0, -t, 0.0, self.s0 + LINING, back, self.oh)
            self._box("Far Reveal R", self.s1 - LINING, -t, 0.0, self.s1, back, self.oh)
            self._box("Far Reveal Top", self.s0, -t, self.oh - LINING, self.s1, back, self.oh)
        far = geo.WallFrame(f"{f.name} far", f.world(f.length, -t, 0.0), -f.u, -f.nrm, f.length, t)
        k = self.cfg["moulding_scale"]
        moulding = [(a * k, b * k) for a, b in PANEL_MOULDING]
        # the leaf's other face, in the far frame (d grows into that room): flush (0) when the door opens that way,
        # recessed into the opening (< 0) when it opens toward us
        leaf_back = self.rd + self.lt - t
        for i, (ps0, ps1, pz0, pz1) in enumerate(getattr(self, "panels", [])):
            a, b = f.length - ps1, f.length - ps0
            geo.sweep_rect(f"{self.tag} Far Leaf Moulding {i + 1}", far, leaf_back, a, b, pz0, pz1, moulding,
                           self.paint, self.col)
            if self.cfg["raised"]:
                m = PANEL_MOULDING_W * k + 0.004
                geo.raised_panel(f"{self.tag} Far Leaf Panel {i + 1}", far, leaf_back, a + m, b - m, pz0 + m, pz1 - m,
                                 inset=0.035, rise=0.007, material=self.paint, collection=self.col)
        ls0, ls1, lz0, _ = self.leaf                        # lever handle on this side too, mirrored
        s_lock = ls1 - 0.065 if self.cfg["handle_side"] == "right" else ls0 + 0.065
        toward_hinge = 1.0 if self.cfg["handle_side"] == "right" else -1.0
        sl, zh = f.length - s_lock, lz0 + 1.0
        geo.cylinder(f"{self.tag} Far Handle Rosette", far.world(sl, leaf_back + 0.005, zh), far.nrm, 0.026, 0.01,
                     self.metal, self.col)
        geo.cylinder(f"{self.tag} Far Handle Stem", far.world(sl, leaf_back + 0.032, zh), far.nrm, 0.008, 0.044,
                     self.metal, self.col)
        geo.frame_box(f"{self.tag} Far Handle Lever", far, sl, leaf_back + 0.044, zh - 0.009,
                      sl + toward_hinge * 0.135, leaf_back + 0.062, zh + 0.009, self.metal, self.col, 0.006, 4)
        if abs(leaf_back) < 0.005:  # the leaf is flush with this face: the door opens this way, hinges show
            s_hinge = f.length - (ls0 if self.cfg["handle_side"] == "right" else ls1)
            for zc in (lz0 + 0.25, lz0 + self.h - 0.25):
                geo.cylinder(f"{self.tag} Hinge", far.world(s_hinge, leaf_back + 0.007, zc), geo.Z, 0.007, 0.1,
                             self.metal, self.col, 24)
                for dz in (-0.05, 0.05):
                    geo.cylinder(f"{self.tag} Hinge Cap", far.world(s_hinge, leaf_back + 0.007, zc + dz), geo.Z,
                                 0.0075, 0.004, self.metal, self.col, 24)
        ov = self.cfg["far_casing"].get("overlap", 0.02)
        c0, c1 = f.length - (self.s1 - ov), f.length - (self.s0 + ov)
        cz = self.oh - ov
        w = far.world
        path = [w(c0, 0, 0), w(c0, 0, cz), w(c1, 0, cz), w(c1, 0, 0)]
        geo.sweep(f"{self.tag} Far Casing", path, far.nrm, casing_profile(self.cstyle, self.cw, self.cd, self.cround),
                  self.paint, self.col, side=1.0)

    def _portal(self):
        pd, top = self.pd, self.cz + self.cw + self.fh
        if self.pilasters:
            for side, (s_out, s_in) in (("L", (self.pil_out[0], self.pil_in[0])),
                                        ("R", (self.pil_out[1], self.pil_in[1]))):
                lo, hi = min(s_out, s_in), max(s_out, s_in)
                pad_lo = BLOCK_PAD if s_out < s_in else 0.0
                pad_hi = 0.0 if s_out < s_in else BLOCK_PAD
                self._box(f"Pilaster {side}", lo, 0.0, 0.0, hi, pd, top, bevel=0.002)
                self._box(f"Pilaster Base {side}", lo - pad_lo, 0.0, 0.0, hi + pad_hi, pd + 0.012, PLINTH_H,
                          bevel=0.003)
                self._box(f"Pilaster Capital {side}", lo - pad_lo, 0.0, top - CAPITAL_H, hi + pad_hi, pd + 0.01,
                          top, bevel=0.003)
                geo.sweep_rect(f"{self.tag} Pilaster Moulding {side}", self.f, pd, lo + 0.022, hi - 0.022,
                               PLINTH_H + 0.05, top - CAPITAL_H - 0.05, PANEL_MOULDING, self.paint, self.col)
            frieze = (self.pil_in[0], self.pil_in[1], pd - 0.008)
            ends = (self.pil_out[0] - 0.03, self.pil_out[1] + 0.03)
        else:
            frieze = (self.cs0 - self.cw, self.cs1 + self.cw, self.cd + 0.002)
            ends = (frieze[0] - 0.012, frieze[1] + 0.012)
        self._box("Frieze", frieze[0], 0.0, self.cz + self.cw - 0.003, frieze[1], frieze[2], top, bevel=0.002)
        w = self.f.world
        geo.sweep(f"{self.tag} Cornice", [w(ends[0], 0, top), w(ends[1], 0, top)], self.f.nrm,
                  cornice_profile(frieze[2] + 0.01), self.paint, self.col, side=1.0)
