"""Room config loading: JSON on top of defaults, with "@name" palette references."""

import json
from copy import deepcopy
from pathlib import Path

DEFAULTS = {
    "name": "room",
    # Interior dimensions in meters. X = width, Y = depth, Z = up; floor at z=0.
    "room": {"width": 3.0, "depth": 4.0, "height": 2.7, "wall_thickness": 0.2},
    "palette": {},
    "walls": {"finish": "wallpaper", "color": "#EEE6D3", "roughness": 0.75},
    "floor": {
        "type": "porcelain",
        "color": "#CFC8BE",
        "grout_color": "#B3AA9F",
        "tile": [0.6, 0.6],
        "grout": 0.002,
        "roughness": 0.18,
    },
    "ceiling": {"color": "#F7F7F7"},
    "baseboard": {"enabled": True, "height": 0.08, "thickness": 0.016, "color": "#F2F0EA"},
    # Measured plan instead of a rectangle: wall segments listed counter-clockwise around the
    # interior, {"id", "from": [x, y], "to": [x, y], "thickness"}; see plan.py.
    "outline": None,
    # More measured rooms next to the main outline (e.g. a bedroom behind a door), each with its own
    # outline and floor: {"id", "outline": [...], "floor": {...}, "doorways": [{"wall", "span", "depth"}]}.
    "extra_rooms": [],
    # Wall lights (бра): {"wall", "centers": [...], "z", "group"}; see lights.build_wall_lights.
    "wall_lights": [],
    "doors": [],
    "openings": [],
    "windows": [],
    "furniture": [],
    "electrical": [],
    "pendants": [],
    "kitchen": None,          # fitted kitchen, see kitchen.py
    "ceiling_lights": None,
    "cameras": [],
    "render": {
        "resolution": [1600, 2000],
        # Quality modes: preview (--preview) for seconds, review (default) for checking,
        # final (--final) for full resolution with "samples".
        "samples": 384,
        "review_scale": 0.6,
        "review_samples": 128,
        "hd_scale": 0.64,       # --hd: 3000 px cameras come out 1920 wide, with final-grade noise
        "hd_samples": 192,      # A/B 2026-10-23: half the time of 384, the same picture (--samples 384 for one-offs)
        "preview_scale": 0.4,
        "preview_samples": 48,
        "exposure": 0.0,
        "white_balance": None,  # K; e.g. 3800 keeps 3500K lights slightly warm
        "look": "AgX - Medium High Contrast",
        "denoise": True,
        "gpu_denoise": True,    # OpenImageDenoise on the GPU (Metal) instead of the CPU
        "persistent_data": True,  # reuse the scene/BVH across cameras in one run
        "save_blend": True,
        "clay": False,          # uniform grey materials to check geometry (also --clay)
    },
}

# Placement along a wall (doors, arches, wall-mounted furniture), as seen from inside the room:
# "from_left" / "from_right" = gap between that wall end and the item's edge (for doors: the
# opening's edge); without them the item is centered on the wall and shifted by "offset".
# In plan configs "span": [c0, c1] gives both ends as plan coordinates along the wall instead.
PLACEMENT = {"span": None, "from_left": None, "from_right": None, "offset": 0.0}

DOOR_DEFAULTS = {
    **PLACEMENT,
    "wall": "back",           # back | front | left | right
    "kind": "entrance",       # entrance (threshold, locks, peephole) | interior (handle only)
    "width": 0.9,             # leaf width; the opening is 9 cm wider (frame + linings)
    "height": 2.05,           # leaf height
    "opening_height": None,   # set instead of height when the plan gives the opening
    "leaf_width": None,       # with span / opening_height: the leaf; the frame fills the rest
    "leaf_height": None,
    "leaf_thickness": 0.07,
    "color": "#EEE6D3",
    "style": "classic",       # classic (two raised panels) | flat
    "panels": None,           # classic: [[bottom, top], ...] fractions of the leaf height (default: two panels)
    "stile": 0.15,            # with panels: side margin as a fraction of the leaf width
    "moulding_scale": 1.0,    # size of the panel moulding
    "raised": True,           # raised fields inside the mouldings (False: flat fields)
    "frame_color": None,      # door frame color if it differs from the leaf (e.g. dark steel frame)
    "handle_side": "right",   # lock side as seen from inside
    "hardware": "brass",      # brass | chrome | black
    "reveal_depth": 0.12,     # how deep the leaf sits inside the opening
    "open": 0,                # degrees the leaf stands open, swung to the side it opens to (0: closed)
    "casing": {"enabled": True, "profile": "simple", "width": 0.07, "depth": 0.012, "outer_round": 0.008},  # profile: simple | classic
    "portal": {
        "enabled": False,
        "pilasters": False,   # False: frieze + cornice over the casings
        "pilaster_width": 0.14,
        "pilaster_depth": 0.03,
        "frieze_height": 0.12,
    },
}

ARCH_DEFAULTS = {
    **PLACEMENT,
    "type": "arch",
    "wall": "front",
    "width": 1.1,
    "height": "ceiling",      # "ceiling" or meters
    "beyond": True,           # model a lit space behind the opening
}

CEILING_LIGHT_DEFAULTS = {
    "type": "downlight",   # downlight (single round spot) | double (two lamps per plate)
    "lamp": "gx53",        # double only: gx53 (flat disc, 120° beam) | gu5.3 (MR16 spot, uses cone/blend)
    "count_x": 2,          # along the room width
    "count_y": 3,          # along the room depth
    "power": 40.0,         # W per lamp (Blender light units)
    "temperature": 3500,   # K
    "cone": 100,           # spots only: cone angle, degrees
    "blend": 0.6,          # spots only: edge softness
    "diameter": 0.09,      # downlight only
    "pair_axis": "long",   # double only: x | y | long | short
    "pair_spacing": None,  # double only: lamp center-to-center, m (None = lamp default)
    "columns": None,       # fixture centers, m from the left wall (overrides count_x spacing)
    "rows": None,          # fixture centers, m from the back wall (overrides count_y spacing)
    "fixtures": None,      # plan configs: [{"at": [x, y], "axis": "x" | "y"}, ...]
}

# "posts" mixes mechanisms in one frame, e.g. ["switch", "outlet"]; "d" lifts it off the wall (a backsplash).
ELECTRICAL_DEFAULTS = {"type": "switch", "wall": None, "centers": [], "z": 0.9, "keys": 1, "posts": None, "d": 0.0}
# style: globe | disc (flat body with an opal diffuser; thickness = body height)
PENDANT_DEFAULTS = {"at": [0.0, 0.0], "style": "globe", "drop": 0.5, "diameter": 0.45, "thickness": 0.06,
                    "power": 60.0,
                    # sticks: bars per layer, bar length, spacing, shift, section [w, h], layer angles (deg), finish
                    "bars": 4, "length": 1.0, "bar_spacing": 0.14, "stagger": 0.12, "bar": [0.03, 0.025],
                    "angle": 45.0, "cross": 90.0, "finish": "chrome", "glow": 6.0, "group": "chandelier"}
WINDOW_DEFAULTS = {"wall": None, "parts": [],  # parts: {"type": door | window, "span", "z": [z0, z1]}
                   "frame_depth": None,   # frame plane from the room face (default: 40% of the wall, at most 15 cm)
                   "light_portal": True}  # sky portal outside; off when the window looks into a loggia, not at the sky

FURNITURE_DEFAULTS = {
    "wardrobe": {
        "wall": "left",
        "anchor": "back",      # neighbouring wall it is pushed against; anything else = centered + offset
        "span": None,
        "offset": 0.0,
        "length": 2.0,
        "depth": 0.6,
        "height": "ceiling",   # "ceiling" or meters
        "doors": 2,
        "color": "#8B6A55",
        "profile": "champagne",  # champagne | brass | chrome | black | slim (thin, in the body color)
        "fronts": None,          # per door: panel | mirror | fluted
        "handles": None,         # finish of vertical bar handles on the end doors
    },
    "cabinet": {  # wall-hung тумба
        **PLACEMENT,
        "wall": "front",
        "width": 0.5,
        "depth": 0.3,
        "height": 0.45,
        "elevation": 0.35,     # bottom edge above the floor
        "drawers": 2,
        "columns": 1,          # fronts side by side in each drawer row
        "color": "#8B6A55",
    },
    "sofa": {**PLACEMENT, "wall": "front", "depth": 0.95, "gap": 0.03, "seat_height": 0.45, "back_height": 0.85,
             "arm_height": 0.62, "arm_width": 0.2, "cushions": 3, "color": "#8F877C"},
    "tv": {**PLACEMENT, "wall": "front", "elevation": 0.75, "height": 0.81, "depth": 0.03},
    "intercom": {**PLACEMENT, "wall": "front", "elevation": 1.53, "height": 0.127, "depth": 0.027, "color": "#F5F5F3"},
    "curtains": {"wall": "front", "stacks": [], "color": "#CDBFA6", "tulle_color": "#F4F2EC",
                 "cornice": "box", "niche_width": 0.15, "niche_depth": 0.10,  # cornice: box | concealed | slot
                 "slot_width": 0.08, "slot_offset": 0.12,  # slot: recess in the ceiling, offset from the wall
                 "led": True},              # LED strip in the cornice recess
    "radiator": {**PLACEMENT, "wall": "front", "sections": 10, "height": 0.577, "depth": 0.09, "elevation": 0.1,
                 "gap": 0.04, "connection_at": 0.0, "color": "#F4F4F2"},
    "niche_cabinet": {**PLACEMENT, "wall": "front", "depth": 0.367, "sections": [], "color": "#E9E2D2"},
    "pouf": {
        **PLACEMENT,
        "wall": "entrance",
        "width": 0.4,
        "depth": 0.35,
        "height": 0.42,
        "gap": 0.03,           # clearance from the wall
        "color": "#CDBFA6",
        "legs": "brass",
    },
    "mirror": {
        **PLACEMENT,
        "wall": "front",
        "width": 0.5,
        "height": 0.9,
        "elevation": 1.0,      # bottom edge above the floor
        "frame": "brass",      # none | brass | champagne | chrome | black | "#hex" paint
        "frame_width": 0.018,
    },
    # Hinged-door cabinet run (распашной шкаф), one arm of a corner wardrobe per entry: the carcass fills
    # `span`, the doors cover `doors_span` (the part not hidden behind the other arm).
    "swing_wardrobe": {**PLACEMENT, "wall": "front", "depth": 0.6, "height": 2.5, "filler": True, "plinth": 0.06,
                       "doors_span": None, "doors": 2, "fluted": None,  # fluted: "start" | "end" of doors_span
                       "flute_width": 0.2, "knobs": "platinum", "knob_z": 1.05, "handles": None,  # handles: "bar" (long vertical)
                       "handle_finish": "black", "color": "#76604F"},
    # Drawer unit: a nightstand on a plinth, or wall-hung (elevation > 0, no plinth); half-moon finger pulls.
    "drawer_unit": {**PLACEMENT, "wall": "front", "depth": 0.4, "height": 0.46, "elevation": 0.0, "plinth": 0.08,
                    "gap": 0.015, "drawers": 2, "columns": 1, "fluted": None,  # left | right | outer
                    "flute_width": 0.16, "color": "#76604F"},
    "bed": {**PLACEMENT, "wall": "front", "depth": 2.15, "gap": 0.015, "mattress": [1.8, 2.0, 0.22],
            "headboard": [1.1, 0.1], "frame_height": 0.3, "color": "#76604F", "bedding": "#EFEBE4",
            "throw": "#CDBFA6"},
    "chair": {**PLACEMENT, "wall": "front", "gap": 0.4, "depth": 0.5, "seat_height": 0.47, "back_height": 0.85,
              "color": "#76604F", "legs": "#2A2623"},
    "air_conditioner": {**PLACEMENT, "wall": "front", "elevation": 2.27, "height": 0.28, "depth": 0.2},
    "desk": {**PLACEMENT, "wall": "front", "depth": 0.8, "height": 0.75, "gap": 0.0, "color": "#E9E6DF",
             "legs": "#2A2A2A"},
    "office_chair": {**PLACEMENT, "wall": "front", "gap": 0.7, "depth": 0.5, "seat_height": 0.48, "back_height": 1.05,
                     "color": "#2E2F31"},
    # Bathtub against the walls (`gap` < 0: pushed to the bare wall, the tile laps over the rim); `height` = rim.
    # screen: tiled front panel in the finish of that room's walls, with a toe recess `kick` [height, depth].
    "bathtub": {**PLACEMENT, "wall": "front", "depth": 0.8, "height": 0.6, "gap": 0.0, "color": "#F6F6F4",
                "drain": "end", "screen": None},  # drain: "start" | "end" of the span
    # Ceiling exhaust fan face, flush under the ceiling: `span` along the wall = its diameter, `gap` = from the wall.
    "ceiling_fan": {**PLACEMENT, "wall": "front", "gap": 0.3, "color": "#F4F4F2"},
    # Boxed-in installation (короб) faced with the tile of `room`'s walls.
    "tiled_box": {**PLACEMENT, "wall": "front", "gap": 0.0, "depth": 0.3, "height": 1.2, "room": None, "color": "#CFC8BE"},
    # Wall-hung toilet: bowl `depth` long from `gap` (the face it hangs on), seat top at `seat_height`; flush plate above.
    "wall_toilet": {**PLACEMENT, "wall": "front", "gap": 0.0, "depth": 0.54, "seat_height": 0.4, "color": "#F7F7F5",
                    "plate": {"finish": "chrome", "z": 1.0, "size": [0.197, 0.156]}},
    # Front-loading washer / dryer (kind), `gap` = space behind it, `elevation` = stacked on another machine.
    "appliance": {**PLACEMENT, "wall": "front", "kind": "washer", "gap": 0.05, "depth": 0.45, "height": 0.85,
                  "elevation": 0.0, "door": 0.5, "color": "#F2F2F0"},  # door: outer diameter of the black door
    # Column for stacked machines: open niche up to `niche_height`, flat doors above it up to the ceiling.
    "appliance_column": {**PLACEMENT, "wall": "front", "depth": 0.6, "niche_height": 1.74, "doors": 2,
                         "color": "#CFC8BE"},
    # Ceramic basin slab on a vanity: top at `height`, bowl [width, depth, deep], mixer behind the bowl.
    # Hygienic shower set: wall outlet with stop valve and holder at `z`, hand shower, hose loop; `gap` = mount face.
    "bidet_shower": {**PLACEMENT, "wall": "front", "gap": 0.0, "z": 0.8},
    "basin_top": {**PLACEMENT, "wall": "front", "depth": 0.45, "height": 0.85, "thickness": 0.12,
                  "bowl": [0.56, 0.32, 0.11], "color": "#F7F7F5"},
    # Electric towel warmer of flat tubes: "bars" (vertical, hooks in rows `hooks` below the top) or "ladder"
    # (`bars` = rungs); `depth` from the wall to the front, control unit low at the `connection` end (facing it).
    "towel_warmer": {**PLACEMENT, "wall": "front", "style": "bars", "bars": 4, "height": 1.2, "elevation": 0.4,
                     "depth": 0.07, "hooks": [0.05, 0.58], "connection": "right", "color": "#F4F4F2"},
    # Exposed wall bath mixer at `z` with a hand shower and hose, and either a slide rail [bottom, top] above it or,
    # with `rain` [top, arm reach, head diameter], a riser pipe with a rain shower head (a shower system).
    "bath_mixer": {**PLACEMENT, "wall": "front", "z": 0.8, "rail": [1.1, 1.8], "rain": None, "finish": "chrome"},
    "desk_gear": {**PLACEMENT, "wall": "front", "desk_height": 0.75, "monitor_offset": 0.0, "laptop_offset": 0.48,
                  "stand": "dark", "laptop": "space_grey"},
}

CAMERA_DEFAULTS = {
    "name": "cam",
    "position": [0.0, -1.8, 1.45],
    "look_at": [0.0, 2.0, 1.2],
    "lens": 18,
    "vertical_correction": True,  # keep verticals straight (architectural two-point perspective)
    "type": "persp",              # persp | ortho | pano (360° equirectangular) | cube (360° as 6 faces)
    "rotation": None,             # [x, y, z] degrees; aims the camera at look_at instead of position
    "ortho_scale": 10.0,
    "dollhouse": False,           # hide the ceiling and its lights, light the model from outside
    "resolution": None,           # per-camera override of render.resolution
    "exposure": None,             # per-camera override of render.exposure
    "eye_height": None,           # --eye keeps this height instead of render.eye.height (lying, seated views)
    "clip_start": None,           # near clipping distance: stand behind a wall and cut it (and the door in it) away
}

# Keys holding lengths; a config with "units": "cm" has these converted to meters on load.
LENGTH_KEYS = {
    "from", "to", "thickness", "span", "at", "centers", "z", "position", "look_at", "ortho_scale", "eye_height",
    "width", "depth", "height", "opening_height", "reveal_depth", "leaf_thickness", "elevation", "length",
    "leaf_width", "leaf_height", "gap", "d", "arm_width", "seat_height", "back_height", "arm_height",
    "stacks", "base_top", "countertop_thickness", "plinth", "bottom", "tiers", "taper", "splits", "bowl",
    "countertop_outline", "tile_origin", "origin", "niche_width", "niche_depth", "connection_at",
    "frame_width", "pair_spacing", "drop", "diameter", "tile", "grout", "wall_thickness",
    "frieze_height", "pilaster_width", "pilaster_depth", "slot_width", "slot_offset", "bar", "bar_spacing", "stagger", "proud", "tracks", "center", "size", "radius", "reach", "rise",
    "plank", "chamfer", "doors_span", "flute_width", "knob_z", "mattress", "headboard", "frame_height", "overlap", "floor_depth", "handle_z", "desk_height", "monitor_offset", "laptop_offset", "cutout", "tiers", "hbar_z",
    "finish_depth", "past_ends", "kick", "niche_height", "band", "inset", "door", "clip_start",
    "hooks", "rail", "kick_span", "rain", "outer_round", "frame_depth", "setback", "wing_width", "rim", "front_rim", "drain",
}


def _scale(node, k):
    if isinstance(node, bool) or not isinstance(node, (int, float, list)):
        return node
    if isinstance(node, list):
        return [_scale(v, k) for v in node]
    return node * k


def _to_meters(node, k=0.01):
    if isinstance(node, dict):
        return {key: _scale(v, k) if key in LENGTH_KEYS else _to_meters(v, k) for key, v in node.items()}
    if isinstance(node, list):
        return [_to_meters(v, k) for v in node]
    return node


def deep_merge(base, over):
    out = deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = deepcopy(value)
    return out


def _resolve(node, palette):
    if isinstance(node, dict):
        return {k: _resolve(v, palette) for k, v in node.items()}
    if isinstance(node, list):
        return [_resolve(v, palette) for v in node]
    if isinstance(node, str) and node.startswith("@"):
        key = node[1:]
        if key not in palette:
            raise KeyError(f"palette has no color named {key!r}")
        return palette[key]
    return node


def load(path, variant=None):
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if variant:  # named set of overrides from the config's "variants", e.g. another palette
        over = deepcopy(raw["variants"][variant])
        rooms = over.pop("rooms", {})  # extra rooms by id, e.g. another floor in one room
        raw = deep_merge(raw, over)
        for patch in raw.pop("furniture_patch", []):  # change items in place, found by their keys, e.g. a shorter wardrobe
            for item in raw["furniture"]:
                if all(item.get(k) == v for k, v in patch["match"].items()):
                    item.update(deepcopy(patch["set"]))
        if rooms:
            raw["extra_rooms"] = [deep_merge(r, rooms.get(r["id"], {})) for r in raw["extra_rooms"]]
    if raw.get("units") == "cm":
        raw = _to_meters(raw)
    cfg = deep_merge(DEFAULTS, raw)
    door_defaults = deep_merge(DOOR_DEFAULTS, cfg.get("door_defaults", {}))  # the config's own defaults for every door
    cfg["doors"] = [deep_merge(door_defaults, d) for d in cfg["doors"]]
    if cfg.get("door_finish"):  # e.g. a variant with oak doors: every leaf and casing in that finish and color
        for d in cfg["doors"]:
            d["finish"], d["color"] = cfg["door_finish"], cfg.get("door_color", d["color"])
    cfg["openings"] = [deep_merge(ARCH_DEFAULTS, o) for o in cfg["openings"]]
    cfg["windows"] = [deep_merge(WINDOW_DEFAULTS, w) for w in cfg["windows"]]
    cfg["electrical"] = [deep_merge(ELECTRICAL_DEFAULTS, e) for e in cfg["electrical"]]
    cfg["pendants"] = [deep_merge(PENDANT_DEFAULTS, p) for p in cfg["pendants"]]
    cfg["furniture"] = [deep_merge(FURNITURE_DEFAULTS[item["type"]], item) for item in cfg["furniture"]]
    if cfg.get("curtains_closed"):  # a variant: heavy curtains drawn across these walls, two panels meeting midway
        walls = {w["id"]: w for ol in [cfg.get("outline") or [], *[r["outline"] for r in cfg.get("extra_rooms", [])]]
                 for w in ol}
        for item in cfg["furniture"]:
            if item["type"] == "curtains" and item["wall"] in cfg["curtains_closed"]:
                w = walls[item["wall"]]
                ax = 0 if abs(w["to"][0] - w["from"][0]) >= abs(w["to"][1] - w["from"][1]) else 1
                a, b = sorted((w["from"][ax], w["to"][ax]))
                item["stacks"] = [[a, (a + b) / 2], [(a + b) / 2, b]]
    cfg["cameras"] = [deep_merge(CAMERA_DEFAULTS, c) for c in cfg["cameras"]]
    if cfg["ceiling_lights"]:
        cfg["ceiling_lights"] = deep_merge(CEILING_LIGHT_DEFAULTS, cfg["ceiling_lights"])
    return _resolve(cfg, cfg["palette"])
