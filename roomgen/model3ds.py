"""Minimal reader of 3D Studio (.3ds) meshes, for manufacturers' models of sanitary ware and the like:
named triangle meshes with their vertices and faces (local matrices are ignored: 3ds stores vertices in world
space). Blender no longer bundles a 3ds importer."""

import struct

MAIN, EDITOR, OBJECT, TRIMESH, VERTICES, FACES = 0x4D4D, 0x3D3D, 0x4000, 0x4100, 0x4110, 0x4120


def _chunks(data, start, end):
    pos = start
    while pos + 6 <= end:
        cid, length = struct.unpack_from("<HI", data, pos)
        if length < 6 or pos + length > end:
            break
        yield cid, pos + 6, pos + length
        pos += length


def load(path):
    """[(name, [(x, y, z), ...], [(a, b, c), ...])] for every triangle mesh in the file."""
    data = open(path, "rb").read()
    meshes = []
    for cid, s, e in _chunks(data, 0, len(data)):
        if cid != MAIN:
            continue
        for cid2, s2, e2 in _chunks(data, s, e):
            if cid2 != EDITOR:
                continue
            for cid3, s3, e3 in _chunks(data, s2, e2):
                if cid3 != OBJECT:
                    continue
                name_end = data.index(b"\0", s3)
                name = data[s3:name_end].decode("latin-1")
                for cid4, s4, e4 in _chunks(data, name_end + 1, e3):
                    if cid4 != TRIMESH:
                        continue
                    verts, faces = [], []
                    for cid5, s5, e5 in _chunks(data, s4, e4):
                        if cid5 == VERTICES:
                            n, = struct.unpack_from("<H", data, s5)
                            verts = [struct.unpack_from("<3f", data, s5 + 2 + 12 * i) for i in range(n)]
                        elif cid5 == FACES:
                            n, = struct.unpack_from("<H", data, s5)
                            faces = [struct.unpack_from("<3H", data, s5 + 2 + 8 * i) for i in range(n)]
                    if verts and faces:
                        meshes.append((name, verts, faces))
    return meshes
