"""Procedural materials. Colors come in as sRGB hex and are converted to linear."""

import bpy


def rgba(hex_color, scale=1.0):
    h = hex_color.lstrip("#")
    out = []
    for i in (0, 2, 4):
        c = int(h[i:i + 2], 16) / 255.0
        c = c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
        out.append(min(c * scale, 1.0))
    return (*out, 1.0)


def _principled(name, color, roughness, **inputs):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Roughness"].default_value = roughness
    for key, value in inputs.items():
        bsdf.inputs[key.replace("_", " ")].default_value = value
    return mat, nt.nodes, nt.links, bsdf


def _noise(nodes, links, vector_socket, scale, detail=4.0, roughness=0.5):
    tex = nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = detail
    tex.inputs["Roughness"].default_value = roughness
    links.new(vector_socket, tex.inputs["Vector"])
    return tex


def _ramp(nodes, links, fac_socket, c0, c1):
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = c0
    ramp.color_ramp.elements[1].color = c1
    links.new(fac_socket, ramp.inputs["Fac"])
    return ramp


def wallpaper(name, hex_color, roughness=0.75):
    """Matte paper with faint tonal variation and a fine embossed grain."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_color), roughness)
    coords = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    tone = _noise(nodes, links, coords, scale=1.2, detail=2.0)
    ramp = _ramp(nodes, links, tone.outputs["Fac"], rgba(hex_color, 0.96), rgba(hex_color))
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    grain = _noise(nodes, links, coords, scale=900.0, detail=6.0, roughness=0.6)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.25
    bump.inputs["Distance"].default_value = 0.0004
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def veneer(name, hex_color, roughness=0.45, axis="z"):
    """Oak veneer: fine grain streaks running along `axis` (up a door: z; along a table top: x or y)
    and a faint pore bump."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_color), roughness)
    coords = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    stretch = nodes.new("ShaderNodeMapping")
    stretch.inputs["Scale"].default_value = {"x": (0.04, 1.0, 1.0), "y": (1.0, 0.04, 1.0)}.get(axis, (1.0, 1.0, 0.04))
    links.new(coords, stretch.inputs["Vector"])
    grain = _noise(nodes, links, stretch.outputs["Vector"], scale=90.0, detail=8.0, roughness=0.65)
    ramp = _ramp(nodes, links, grain.outputs["Fac"], rgba(hex_color, 0.72), rgba(hex_color, 1.1))
    ramp.color_ramp.elements[0].position, ramp.color_ramp.elements[1].position = 0.35, 0.65
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.15
    bump.inputs["Distance"].default_value = 0.0003
    links.new(grain.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def fabric(name, hex_color):
    """Upholstery: matte with sheen and a fine weave bump."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_color), 0.85, Sheen_Weight=0.6)
    weave = _noise(nodes, links, nodes.new("ShaderNodeTexCoord").outputs["Object"], scale=1200.0, detail=3.0)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.2
    bump.inputs["Distance"].default_value = 0.0005
    links.new(weave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def sheer(name, hex_color):
    """Tulle: thin translucent fabric."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_color), 0.8, Alpha=0.22)  # see-through voile
    return _keep_in_clay(mat)


def paint(name, hex_color, roughness=0.32):
    """Satin enamel for doors and joinery."""
    mat, *_ = _principled(name, rgba(hex_color), roughness)
    return mat


def matte(name, hex_color, roughness=0.9):
    mat, *_ = _principled(name, rgba(hex_color), roughness)
    return mat


def _socket(sockets, identifier):
    return next(s for s in sockets if s.identifier == identifier)


def _box_tile_vector(nodes, links, coords, origin):
    """2D tile-grid coordinates of a face in its own plane, picked by its normal (walls along x: x-z, along y:
    y-z, horizontal: x-y), measured from `origin` (x, y, z)."""
    shift = nodes.new("ShaderNodeVectorMath")
    shift.operation = "SUBTRACT"
    links.new(coords, shift.inputs[0])
    shift.inputs[1].default_value = origin
    p = nodes.new("ShaderNodeSeparateXYZ")
    links.new(shift.outputs["Vector"], p.inputs["Vector"])
    n = nodes.new("ShaderNodeSeparateXYZ")
    links.new(nodes.new("ShaderNodeNewGeometry").outputs["Normal"], n.inputs["Vector"])

    def plane(a, b):
        comb = nodes.new("ShaderNodeCombineXYZ")
        links.new(p.outputs[a], comb.inputs["X"])
        links.new(p.outputs[b], comb.inputs["Y"])
        return comb.outputs["Vector"]

    def facing(axis):  # 1 where the normal runs mostly along this axis
        ab = nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        links.new(n.outputs[axis], ab.inputs[0])
        gt = nodes.new("ShaderNodeMath")
        gt.operation = "GREATER_THAN"
        links.new(ab.outputs["Value"], gt.inputs[0])
        gt.inputs[1].default_value = 0.5
        return gt.outputs["Value"]

    def pick(fac, a, b):
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "VECTOR"
        links.new(fac, _socket(mix.inputs, "Factor_Float"))
        links.new(a, _socket(mix.inputs, "A_Vector"))
        links.new(b, _socket(mix.inputs, "B_Vector"))
        return _socket(mix.outputs, "Result_Vector")

    wall = pick(facing("X"), plane("X", "Z"), plane("Y", "Z"))
    return pick(facing("Z"), wall, plane("X", "Y"))


def _tile_photo(nodes, links, vector, tile, path, rotate, faces=None):
    """Color from a photo of one tile face, repeated per tile. Each tile is randomly mirrored along
    either axis (4 variants) and shifted a little in tone, so the repeat does not show.
    faces = (columns, rows): the photo is an atlas of that many different faces, one picked per tile at random.
    Returns (color, luminance) sockets; the luminance drives gloss on bright veins."""
    def math(op, a, b, c=None):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b, c)[: 3 if c is not None else 2]):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                links.new(v, n.inputs[i])
        return n.outputs["Value"]

    def vmath(op, a, b=None):
        n = nodes.new("ShaderNodeVectorMath")
        n.operation = op
        links.new(a, n.inputs[0])
        if b is not None:
            n.inputs[1].default_value = b
        return n.outputs["Vector"]

    scaled = vmath("DIVIDE", vector, (tile[0], tile[1], 1.0))
    noise = nodes.new("ShaderNodeTexWhiteNoise")
    noise.noise_dimensions = "3D"
    links.new(vmath("FLOOR", scaled), noise.inputs["Vector"])
    rnd = nodes.new("ShaderNodeSeparateColor")
    links.new(_socket(noise.outputs, "Color"), rnd.inputs["Color"])
    uv = nodes.new("ShaderNodeSeparateXYZ")
    links.new(vmath("FRACTION", scaled), uv.inputs["Vector"])

    def mirror(coord, chance):  # coord, or 1 - coord for about half of the tiles
        return math("MULTIPLY_ADD", math("GREATER_THAN", chance, 0.5), math("MULTIPLY_ADD", coord, -2.0, 1.0), coord)

    u, v = mirror(uv.outputs["X"], rnd.outputs["Red"]), mirror(uv.outputs["Y"], rnd.outputs["Green"])
    if rotate:  # photo shot in portrait: swap axes so its long side runs along the tile's
        u, v = v, u
    if faces:
        cols, rows = faces
        k = math("FLOOR", math("MULTIPLY", noise.outputs["Value"], cols * rows), 0.0)
        col, row = math("MODULO", k, cols), math("FLOOR", math("DIVIDE", k, cols), 0.0)
        # a hair inside each face, so the neighbouring face does not bleed in at the tile edges
        u = math("DIVIDE", math("ADD", col, math("MULTIPLY_ADD", u, 0.994, 0.003)), cols)
        v = math("DIVIDE", math("ADD", row, math("MULTIPLY_ADD", v, 0.994, 0.003)), rows)
    comb = nodes.new("ShaderNodeCombineXYZ")
    links.new(u, comb.inputs["X"])
    links.new(v, comb.inputs["Y"])

    img = nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(str(path), check_existing=True)
    img.extension = "EXTEND"
    img.interpolation = "Cubic"
    links.new(comb.outputs["Vector"], img.inputs["Vector"])

    hsv = nodes.new("ShaderNodeHueSaturation")
    links.new(math("MULTIPLY_ADD", rnd.outputs["Blue"], 0.08, 0.96), hsv.inputs["Value"])  # tone 0.96 .. 1.04
    links.new(img.outputs["Color"], hsv.inputs["Color"])
    lum = nodes.new("ShaderNodeRGBToBW")
    links.new(img.outputs["Color"], lum.inputs["Color"])
    return hsv.outputs["Color"], lum.outputs["Val"]


def porcelain(name, hex_tile, hex_grout, tile=(0.6, 0.6), grout=0.002, roughness=0.18, origin=(0.0, 0.0),
              texture=None, texture_rotate=False, texture_gloss=None, axes=("X", "Y"), faces=None):
    """Porcelain stoneware tiles; the tile grid starts at `origin` (x, y). With `texture` (a photo
    of one tile face) the color comes from the photo instead of `hex_tile`.
    axes="box": a tiled room, every face takes the grid in its own plane, picked by its normal: walls along x
    in x-z, walls along y in y-z, horizontal faces in x-y; `origin` is then (x, y, z) of a grid corner."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_tile), roughness)
    coords = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    if axes == "box":
        vec = _box_tile_vector(nodes, links, coords, (*origin, 0.0, 0.0)[:3])
    else:
        if tuple(axes) != ("X", "Y"):  # tiles on a wall: lay the grid in that plane, e.g. ("Y", "Z")
            sep = nodes.new("ShaderNodeSeparateXYZ")
            comb = nodes.new("ShaderNodeCombineXYZ")
            links.new(coords, sep.inputs["Vector"])
            links.new(sep.outputs[axes[0]], comb.inputs["X"])
            links.new(sep.outputs[axes[1]], comb.inputs["Y"])
            coords = comb.outputs["Vector"]
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Location"].default_value = (-origin[0], -origin[1], 0.0)
        links.new(coords, mapping.inputs["Vector"])
        vec = mapping.outputs["Vector"]

    brick = nodes.new("ShaderNodeTexBrick")  # tile grid: per-tile color plus the grout mask (Fac)
    brick.offset = 0.0
    brick.squash = 1.0
    links.new(vec, brick.inputs["Vector"])
    tile_rough = roughness
    if texture:
        photo, lum = _tile_photo(nodes, links, vec, tile, texture, texture_rotate, faces)
        links.new(photo, brick.inputs["Color1"])
        links.new(photo, brick.inputs["Color2"])
        if texture_gloss:  # bright veins in the photo are glossy, the rest stays matte
            gloss = nodes.new("ShaderNodeMapRange")
            links.new(lum, gloss.inputs["Value"])
            gloss.inputs["From Min"].default_value, gloss.inputs["From Max"].default_value = texture_gloss
            gloss.inputs["To Min"].default_value, gloss.inputs["To Max"].default_value = roughness, 0.12
            tile_rough = gloss.outputs["Result"]
    else:
        stone = _noise(nodes, links, vec, scale=6.0, detail=8.0, roughness=0.55)
        stone_ramp = _ramp(nodes, links, stone.outputs["Fac"], rgba(hex_tile, 0.95), rgba(hex_tile, 1.02))
        links.new(stone_ramp.outputs["Color"], brick.inputs["Color1"])
        brick.inputs["Color2"].default_value = rgba(hex_tile, 0.975)
    brick.inputs["Mortar"].default_value = rgba(hex_grout)
    brick.inputs["Scale"].default_value = 1.0
    brick.inputs["Mortar Size"].default_value = grout
    brick.inputs["Mortar Smooth"].default_value = 0.2
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Brick Width"].default_value = tile[0]
    brick.inputs["Row Height"].default_value = tile[1]
    links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])

    rough = nodes.new("ShaderNodeMix")  # grout lines are rough
    rough.data_type = "FLOAT"
    links.new(brick.outputs["Fac"], _socket(rough.inputs, "Factor_Float"))
    if isinstance(tile_rough, float):
        _socket(rough.inputs, "A_Float").default_value = tile_rough
    else:
        links.new(tile_rough, _socket(rough.inputs, "A_Float"))
    _socket(rough.inputs, "B_Float").default_value = 0.85
    links.new(_socket(rough.outputs, "Result_Float"), bsdf.inputs["Roughness"])

    bump = nodes.new("ShaderNodeBump")
    bump.invert = True
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0015
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


HARDWARE = {
    "brass": ("#CDB57F", 0.28),
    "champagne": ("#D6C7A6", 0.32),
    "copper": ("#C27C5A", 0.3),
    "dark_copper": ("#7A452E", 0.35),
    "platinum": ("#C9C8C3", 0.25),
    "chrome": ("#E4E6E8", 0.06),
    "black": ("#1B1B1C", 0.45),
}


def metal(name, finish):
    hex_color, roughness = HARDWARE[finish]
    mat, *_ = _principled(name, rgba(hex_color), roughness, Metallic=1.0)
    return mat


def _keep_in_clay(mat):
    """Clay previews replace every material except the ones that make light or let it through."""
    mat["keep_in_clay"] = True
    return mat


def mirror(name):
    mat, *_ = _principled(name, rgba("#F0F0F0"), 0.02, Metallic=1.0)
    return _keep_in_clay(mat)


def glass(name):
    mat, nodes, links, bsdf = _principled(name, (1.0, 1.0, 1.0, 1.0), 0.0, Transmission_Weight=1.0)
    bsdf.inputs["Thin Wall"].default_value = True  # a pane, not a solid block of glass
    # Shadow rays pass straight through, so sun and sky light reach the room through the pane.
    out = next(n for n in nodes if n.type == "OUTPUT_MATERIAL")
    mix = nodes.new("ShaderNodeMixShader")
    links.new(nodes.new("ShaderNodeLightPath").outputs["Is Shadow Ray"], mix.inputs["Fac"])
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(nodes.new("ShaderNodeBsdfTransparent").outputs["BSDF"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return _keep_in_clay(mat)


def crystal(name):
    """Cut crystal: clear, high IOR, sharp highlights."""
    mat, nodes, links, bsdf = _principled(name, (1.0, 1.0, 1.0, 1.0), 0.0, Transmission_Weight=1.0)
    bsdf.inputs["IOR"].default_value = 1.6
    return _keep_in_clay(mat)


def frosted_glass(name):
    """Satin (acid-etched) glass: lets light through, blurs what is behind it."""
    mat, nodes, links, bsdf = _principled(name, rgba("#E6E8EC"), 0.5, Transmission_Weight=0.65)  # milky
    bsdf.inputs["Thin Wall"].default_value = True
    return _keep_in_clay(mat)


def glass_dark(name):
    mat, *_ = _principled(name, rgba("#0E1114"), 0.04)
    return mat


def emitter(name, temperature, strength):
    """Light lens: emission tinted by blackbody temperature."""
    mat, nodes, links, bsdf = _principled(name, (1.0, 1.0, 1.0, 1.0), 0.2)
    bb = nodes.new("ShaderNodeBlackbody")
    bb.inputs["Temperature"].default_value = temperature
    links.new(bb.outputs["Color"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength
    return _keep_in_clay(mat)


def lamp_lens(name, temperature, strength):
    """Frosted GX53 diffuser. Matte, not glossy: an off lamp near a window must not mirror the window and read
    as lit. Off, the LED board shows a shade darker behind the middle; lit, the middle glows a little stronger
    than the rim. `lens` marks it for scene.apply_lighting, which keeps this look with the glow off."""
    mat, nodes, links, bsdf = _principled(name, rgba("#ECECE9"), 0.6)
    gen = nodes.new("ShaderNodeTexCoord").outputs["Generated"]  # 0..1 over the disc: its middle at 0.5
    centered = nodes.new("ShaderNodeVectorMath")
    centered.operation = "MULTIPLY_ADD"
    centered.inputs[1].default_value = (2.0, 2.0, 0.0)
    centered.inputs[2].default_value = (-1.0, -1.0, 0.0)
    links.new(gen, centered.inputs[0])
    radius = nodes.new("ShaderNodeVectorMath")  # 0 in the middle, 1 at the rim
    radius.operation = "LENGTH"
    links.new(centered.outputs["Vector"], radius.inputs[0])
    base = _ramp(nodes, links, radius.outputs["Value"], rgba("#DEDEDA"), rgba("#EFEFEC"))
    links.new(base.outputs["Color"], bsdf.inputs["Base Color"])
    falloff = _ramp(nodes, links, radius.outputs["Value"], (1.0, 1.0, 1.0, 1.0), (0.78, 0.78, 0.78, 1.0))
    bb = nodes.new("ShaderNodeBlackbody")
    bb.inputs["Temperature"].default_value = temperature
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    links.new(bb.outputs["Color"], tint.inputs["A"])
    links.new(falloff.outputs["Color"], tint.inputs["B"])
    links.new(tint.outputs["Result"], bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = strength * 1.12  # the falloff averages about 0.89
    mat["lens"] = True
    return _keep_in_clay(mat)


def laminate(name, hex_color, plank=(1.292, 0.194), chamfer=0.0015, roughness=0.55, origin=(0.0, 0.0), along="x",
             stagger=None, texture=None, tint=None):
    """Laminate planks laid along `along` from `origin`: each row shifts by `stagger` of a plank (e.g. 1/3),
    or by a random amount; a V-groove chamfer on all four edges. With `texture` (a photo of one plank face)
    every plank shows the photo, randomly mirrored and shifted in tone; otherwise a procedural oak.
    `tint` (linear RGB factors) recolors the photo, e.g. a darker wood with the same grain."""
    mat, nodes, links, bsdf = _principled(name, rgba(hex_color), roughness)
    length, width = plank

    def m(op, a, b=None):
        n = nodes.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, b)[: 1 if b is None else 2]):
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                links.new(v, n.inputs[i])
        return n.outputs["Value"]

    def vec(x, y, z):
        n = nodes.new("ShaderNodeCombineXYZ")
        for sock, v in zip(n.inputs, (x, y, z)):
            if isinstance(v, (int, float)):
                sock.default_value = v
            else:
                links.new(v, sock)
        return n.outputs["Vector"]

    def white(vector):
        n = nodes.new("ShaderNodeTexWhiteNoise")
        n.noise_dimensions = "3D"
        links.new(vector, n.inputs["Vector"])
        return n

    coords = nodes.new("ShaderNodeTexCoord").outputs["Object"]
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Location"].default_value = (-origin[0], -origin[1], 0.0)
    links.new(coords, mapping.inputs["Vector"])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(mapping.outputs["Vector"], sep.inputs["Vector"])
    x, y = (sep.outputs["X"], sep.outputs["Y"]) if along == "x" else (sep.outputs["Y"], sep.outputs["X"])

    row = m("FLOOR", m("DIVIDE", y, width))
    shift = m("FRACT", m("MULTIPLY", row, stagger)) if stagger else white(vec(row, 17.0, 0.0)).outputs["Value"]
    u = m("ADD", x, m("MULTIPLY", shift, length))  # row offset
    col = m("FLOOR", m("DIVIDE", u, length))
    rnd = nodes.new("ShaderNodeSeparateColor")
    links.new(_socket(white(vec(col, row, 3.0)).outputs, "Color"), rnd.inputs["Color"])
    fu = m("MULTIPLY", m("FRACT", m("DIVIDE", u, length)), length)    # position inside the plank, m
    fv = m("MULTIPLY", m("FRACT", m("DIVIDE", y, width)), width)
    edge = m("MINIMUM", m("MINIMUM", fv, m("SUBTRACT", width, fv)), m("MINIMUM", fu, m("SUBTRACT", length, fu)))
    groove = nodes.new("ShaderNodeMapRange")      # 0 at the joint, 1 on the flat face: a V chamfer
    links.new(edge, groove.inputs["Value"])
    groove.inputs["From Min"].default_value, groove.inputs["From Max"].default_value = 0.0, chamfer
    flat = groove.outputs["Result"]

    def grain(sx, sy, seed, detail):
        n = nodes.new("ShaderNodeTexNoise")
        n.inputs["Scale"].default_value = 1.0
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = 0.55
        links.new(vec(m("ADD", m("MULTIPLY", fu, sx), m("MULTIPLY", rnd.outputs["Red"], 40.0)),
                      m("MULTIPLY", fv, sy), m("MULTIPLY", seed, 40.0)), n.inputs["Vector"])
        return n.outputs["Fac"]

    plank_tone = nodes.new("ShaderNodeHueSaturation")
    if texture:
        def flip(coord, chance):  # coord, or 1 - coord for about half of the planks
            return m("ADD", coord, m("MULTIPLY", m("GREATER_THAN", chance, 0.5), m("SUBTRACT", 1.0, m("MULTIPLY", coord, 2.0))))

        img = nodes.new("ShaderNodeTexImage")
        img.image = bpy.data.images.load(str(texture), check_existing=True)
        img.extension = "EXTEND"
        img.interpolation = "Cubic"
        links.new(vec(flip(m("DIVIDE", fu, length), rnd.outputs["Green"]),
                      flip(m("DIVIDE", fv, width), rnd.outputs["Blue"]), 0.0), img.inputs["Vector"])
        links.new(m("ADD", m("MULTIPLY", rnd.outputs["Red"], 0.12), 0.94), plank_tone.inputs["Value"])
        links.new(img.outputs["Color"], plank_tone.inputs["Color"])
        lum = nodes.new("ShaderNodeRGBToBW")
        links.new(img.outputs["Color"], lum.inputs["Color"])
        pores = lum.outputs["Val"]                                # bright grain lines stand up a little
        plank_color = plank_tone.outputs["Color"]
        if tint:
            tinted = nodes.new("ShaderNodeMix")
            tinted.data_type, tinted.blend_type = "RGBA", "MULTIPLY"
            _socket(tinted.inputs, "Factor_Float").default_value = 1.0
            links.new(plank_color, _socket(tinted.inputs, "A_Color"))
            _socket(tinted.inputs, "B_Color").default_value = (*tint, 1.0)
            plank_color = _socket(tinted.outputs, "Result_Color")
    else:
        streaks = grain(1.5, 70.0, rnd.outputs["Green"], 5.0)     # tone streaks along the plank
        pores = grain(5.0, 420.0, rnd.outputs["Blue"], 3.0)       # fine embossed grain lines
        tone = _ramp(nodes, links, streaks, rgba(hex_color, 0.78), rgba(hex_color, 1.18))
        tone.color_ramp.elements[0].position, tone.color_ramp.elements[1].position = 0.32, 0.68
        links.new(m("ADD", m("MULTIPLY", rnd.outputs["Red"], 0.16), 0.92), plank_tone.inputs["Value"])
        links.new(tone.outputs["Color"], plank_tone.inputs["Color"])
        lines = _ramp(nodes, links, pores, (0.8, 0.8, 0.8, 1.0), (1.0, 1.0, 1.0, 1.0))
        lines.color_ramp.elements[0].position, lines.color_ramp.elements[1].position = 0.38, 0.55
        grained = nodes.new("ShaderNodeMix")
        grained.data_type, grained.blend_type = "RGBA", "MULTIPLY"
        _socket(grained.inputs, "Factor_Float").default_value = 1.0
        links.new(plank_tone.outputs["Color"], _socket(grained.inputs, "A_Color"))
        links.new(lines.outputs["Color"], _socket(grained.inputs, "B_Color"))
        plank_color = _socket(grained.outputs, "Result_Color")
    joint = nodes.new("ShaderNodeMix")             # the chamfer is a little darker
    joint.data_type = "RGBA"
    links.new(m("MULTIPLY", m("SUBTRACT", 1.0, flat), 0.5), _socket(joint.inputs, "Factor_Float"))
    links.new(plank_color, _socket(joint.inputs, "A_Color"))
    _socket(joint.inputs, "B_Color").default_value = rgba(hex_color, 0.35)
    links.new(_socket(joint.outputs, "Result_Color"), bsdf.inputs["Base Color"])
    links.new(m("ADD", roughness, m("MULTIPLY", m("SUBTRACT", 1.0, flat), 0.3)), bsdf.inputs["Roughness"])

    emboss = nodes.new("ShaderNodeBump")
    emboss.inputs["Strength"].default_value = 0.25
    emboss.inputs["Distance"].default_value = 0.0003
    links.new(pores, emboss.inputs["Height"])
    bevel = nodes.new("ShaderNodeBump")
    bevel.inputs["Strength"].default_value = 1.0
    bevel.inputs["Distance"].default_value = chamfer * 0.6
    links.new(flat, bevel.inputs["Height"])
    links.new(emboss.outputs["Normal"], bevel.inputs["Normal"])
    links.new(bevel.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def glow(name, hex_color, strength):
    """Colored self-lit surface (an LED ring, display digits)."""
    mat, nodes, links, bsdf = _principled(name, rgba("#101010"), 0.3)
    bsdf.inputs["Emission Color"].default_value = rgba(hex_color)
    bsdf.inputs["Emission Strength"].default_value = strength
    return _keep_in_clay(mat)
