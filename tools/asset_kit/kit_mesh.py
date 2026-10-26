# Развёртка ассета для проверки карт: треугольники UV (в пикселях карты) и их площадь на модели (см²).
# Источник — glTF/glb (читается здесь, без Blender) или выгрузка Blender (review.py uvdump: .blend, .fbx, .obj).
# Ключ набора карт — имя файла карты без суффикса канала: receiver_baseColor.png → receiver,
# veras54_Steel_100_albedo.png → veras54_Steel_100.
import base64
import json
import os
import re
import struct

import cv2
import numpy as np

SUFFIX = re.compile(
    r"[_\-. ](basecolor|base_color|albedo|diffuse|color|col|occlusionroughnessmetallic|orm|arm|roughness|rough|"
    r"metallic|metalness|metal|normal|normal_opengl|nor_gl|nrm|nor|height|ao|occlusion|coat|emission|emissive)$",
    re.IGNORECASE)


def set_key(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return SUFFIX.sub("", stem)


def channel_of(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    m = SUFFIX.search(stem)
    if not m:
        return ""
    s = m.group(1).lower()
    if s in ("basecolor", "base_color", "albedo", "diffuse", "color", "col"):
        return "color"
    if s in ("occlusionroughnessmetallic", "orm", "arm"):
        return "orm"
    if s in ("roughness", "rough"):
        return "rough"
    if s in ("metallic", "metalness", "metal"):
        return "metal"
    if s in ("normal", "normal_opengl", "nor_gl", "nrm", "nor"):
        return "normal"
    return s


# ---------- glTF ----------

_CT = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def _load_gltf(path: str):
    with open(path, "rb") as f:
        data = f.read()
    bins = []
    if data[:4] == b"glTF":
        off = 12
        js = None
        while off < len(data):
            ln, typ = struct.unpack_from("<II", data, off)
            chunk = data[off + 8: off + 8 + ln]
            if typ == 0x4E4F534A:
                js = json.loads(chunk.decode("utf-8"))
            elif typ == 0x004E4942:
                bins.append(chunk)
            off += 8 + ln
        g = js
    else:
        g = json.loads(data.decode("utf-8"))
    buffers = []
    for i, b in enumerate(g.get("buffers", [])):
        uri = b.get("uri")
        if uri is None:
            buffers.append(bins[0] if bins else b"")
        elif uri.startswith("data:"):
            buffers.append(base64.b64decode(uri.split(",", 1)[1]))
        else:
            with open(os.path.join(os.path.dirname(path), uri), "rb") as f:
                buffers.append(f.read())
    return g, buffers


def _accessor(g, buffers, idx):
    a = g["accessors"][idx]
    n = _NC[a["type"]]
    dt = np.dtype(_CT[a["componentType"]])
    cnt = a["count"]
    if "bufferView" not in a:
        return np.zeros((cnt, n), dtype=np.float32)
    bv = g["bufferViews"][a["bufferView"]]
    buf = buffers[bv["buffer"]]
    start = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    stride = bv.get("byteStride", 0) or dt.itemsize * n
    raw = np.frombuffer(buf, dtype=np.uint8, count=stride * (cnt - 1) + dt.itemsize * n, offset=start)
    if stride == dt.itemsize * n:
        arr = raw.view(dt).reshape(cnt, n)
    else:
        arr = np.lib.stride_tricks.as_strided(raw, shape=(cnt, dt.itemsize * n), strides=(stride, 1))
        arr = np.ascontiguousarray(arr).view(dt).reshape(cnt, n)
    arr = arr.astype(np.float32)
    if a.get("normalized"):
        arr /= float(np.iinfo(dt).max)
    return arr


def _trs(node):
    if "matrix" in node:
        return np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    t = node.get("translation", [0, 0, 0])
    r = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    x, y, z, w = r
    rot = np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])
    m = np.eye(4)
    m[:3, :3] = rot * np.array(s)[None, :]
    m[:3, 3] = t
    return m


def _material_images(g, mi):
    """Имена файлов карт материала (basename) — по ним находится набор карт."""
    out = []
    mat = g["materials"][mi]
    refs = []
    pbr = mat.get("pbrMetallicRoughness", {})
    for k in ("baseColorTexture", "metallicRoughnessTexture"):
        if k in pbr:
            refs.append(pbr[k]["index"])
    for k in ("normalTexture", "occlusionTexture", "emissiveTexture"):
        if k in mat:
            refs.append(mat[k]["index"])
    for ti in refs:
        src = g["textures"][ti].get("source")
        if src is None:
            continue
        im = g["images"][src]
        nm = im.get("uri") or im.get("name") or ""
        out.append(os.path.basename(nm.split("?")[0]))
    return out


# уровни детализации лежат в той же развёртке поверх LOD0 — в плотность и наложение их не брать
LOD_SKIP = r"(?i)[_.]LOD[1-9]\d*$"


def read_gltf(path: str, skip: str = LOD_SKIP):
    """→ список материалов: {name, images, objects, uv (N,3,2) в долях карты, сверху вниз, area_cm2 (N), obj (N)}."""
    g, buffers = _load_gltf(path)
    skip_re = re.compile(skip) if skip else None
    mats = {}
    world = {}

    def walk(ni, parent):
        node = g["nodes"][ni]
        m = parent @ _trs(node)
        world[ni] = m
        for c in node.get("children", []):
            walk(c, m)

    scene = g.get("scenes", [{}])[g.get("scene", 0)] if g.get("scenes") else {"nodes": list(range(len(g["nodes"])))}
    for ni in scene.get("nodes", []):
        walk(ni, np.eye(4))
    for ni, m in world.items():
        node = g["nodes"][ni]
        if "mesh" not in node:
            continue
        name = node.get("name") or g["meshes"][node["mesh"]].get("name", f"mesh{node['mesh']}")
        if skip_re and skip_re.search(name):
            continue
        if "skin" in node:
            m = np.eye(4)   # у сетки со скелетом вершины уже в позе привязки — узел не применяется
        for prim in g["meshes"][node["mesh"]]["primitives"]:
            if prim.get("mode", 4) != 4 or "POSITION" not in prim["attributes"]:
                continue
            mi = prim.get("material")
            tc = 0
            if mi is not None:
                bct = g["materials"][mi].get("pbrMetallicRoughness", {}).get("baseColorTexture")
                tc = bct.get("texCoord", 0) if bct else 0
            key_uv = f"TEXCOORD_{tc}"
            if key_uv not in prim["attributes"]:
                continue
            pos = _accessor(g, buffers, prim["attributes"]["POSITION"])[:, :3].astype(np.float64)
            uv = _accessor(g, buffers, prim["attributes"][key_uv])[:, :2]
            if "indices" in prim:
                idx = _accessor(g, buffers, prim["indices"])[:, 0].astype(np.int64).reshape(-1, 3)
            else:
                idx = np.arange(len(pos), dtype=np.int64).reshape(-1, 3)
            wp = (m[:3, :3] @ pos.T).T + m[:3, 3]
            tri = wp[idx]
            area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) * 1e4
            mname = g["materials"][mi].get("name", f"mat{mi}") if mi is not None else "(нет)"
            rec = mats.setdefault(mname, {"name": mname, "images": _material_images(g, mi) if mi is not None else [],
                                          "objects": [], "uv": [], "area_cm2": [], "obj": []})
            if name not in rec["objects"]:
                rec["objects"].append(name)
            oi = rec["objects"].index(name)
            rec["uv"].append(uv[idx].astype(np.float32))
            rec["area_cm2"].append(area.astype(np.float32))
            rec["obj"].append(np.full(len(idx), oi, dtype=np.int32))
    out = []
    for rec in mats.values():
        rec["uv"] = np.concatenate(rec["uv"])
        rec["area_cm2"] = np.concatenate(rec["area_cm2"])
        rec["obj"] = np.concatenate(rec["obj"])
        out.append(rec)
    return out


def read_dump(json_path: str):
    """Выгрузка review.py uvdump (Blender): json + npz рядом."""
    with open(json_path, encoding="utf-8") as f:
        meta = json.load(f)
    z = np.load(os.path.splitext(json_path)[0] + ".npz")
    out = []
    for i, m in enumerate(meta["materials"]):
        out.append({"name": m["name"], "images": m["images"], "objects": m["objects"],
                    "uv": z[f"m{i}_uv"], "area_cm2": z[f"m{i}_area"], "obj": z[f"m{i}_obj"]})
    return out


def match_sets(materials, set_keys):
    """Материал → ключ набора: по картам материала, иначе по имени материала (FBX для Painter — имя набора)."""
    res = {}
    low = {k.lower(): k for k in set_keys}
    for m in materials:
        key = None
        for im in m["images"]:
            k = set_key(im)
            if k.lower() in low:
                key = low[k.lower()]
                break
        if key is None:
            nm = re.sub(r"^(SP_|GAME[^A-Za-z0-9]+)", "", m["name"])
            for cand in (m["name"], nm, re.sub(r"\W+", "_", nm)):
                if cand.lower() in low:
                    key = low[cand.lower()]
                    break
        if key is not None:
            res.setdefault(key, []).append(m)
    return res


def merge(mats):
    if len(mats) == 1:
        return mats[0]
    objs = []
    uv, ar, ob = [], [], []
    for m in mats:
        base = len(objs)
        objs += m["objects"]
        uv.append(m["uv"])
        ar.append(m["area_cm2"])
        ob.append(m["obj"] + base)
    return {"name": "+".join(m["name"] for m in mats), "images": mats[0]["images"], "objects": objs,
            "uv": np.concatenate(uv), "area_cm2": np.concatenate(ar), "obj": np.concatenate(ob)}


def rasterize(uv, w: int, h: int):
    """Маска покрытия развёртки (uint8 0/1) размером w×h; uv — доли карты, v сверху вниз."""
    mask = np.zeros((h, w), dtype=np.uint8)
    pts = np.round(np.stack([uv[..., 0] * w, uv[..., 1] * h], axis=-1) * 16).astype(np.int32)
    # по треугольнику: fillPoly со всеми сразу заливает по чётности — наложенные острова вычитаются
    for t in pts:
        cv2.fillConvexPoly(mask, t, 1, cv2.LINE_8, 4)
    return mask


def density(m, w: int, h: int):
    """Плотность текселей по треугольникам: пикс/см, вес — площадь на модели."""
    uv = m["uv"].astype(np.float64)
    e1 = (uv[:, 1] - uv[:, 0]) * [w, h]
    e2 = (uv[:, 2] - uv[:, 0]) * [w, h]
    uv_px = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    a = m["area_cm2"].astype(np.float64)
    ok = (a > 1e-6) & (uv_px > 1e-6)
    return np.sqrt(uv_px[ok] / a[ok]), a[ok], m["obj"][ok], uv_px


def wpercentile(v, w, q):
    if len(v) == 0:
        return float("nan")
    o = np.argsort(v)
    c = np.cumsum(w[o])
    c /= c[-1]
    return float(np.interp(q / 100.0, c, v[o]))
