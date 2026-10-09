"""Сосна обыкновенная (Pinus sylvestris) для зоны 1, bpy. Как у ели (tools/build_spruce.py), два этапа:

  atlas — хвоя своя, без сканов: побеги по годам (мутовки, у вершины побега почка), на побегах
          последних трёх лет — пары игл 4–7 см (у основания бурое влагалище, старые иглы осенью желтеют).
          Из побегов — кисти и «облака» (пады) ветвей; рендер Cycles в ячейки атласа: цвет, нормаль, затенение.
          Склейка — tools/build_spruce_atlas.py --pine.
  trees — сосна по референсам владельца (2026-10-09): от тонких высоких лесных (крона — верхняя треть,
          ствол голый, кое-где сухие сучки) до толстых старых с широкой «зонтичной» кроной и кривыми
          сучьями — за стволом можно укрыться. Хвоя — пучками на концах ветвей, внутри кроны голые
          оранжевые ветви. Кора: снизу толстая серо-бурая плитчатая, выше — тонкая оранжевая
          (доля плитчатой — альфа цвета вершин, у толстых сосен выше). → assets/zone01/models/pine_*.glb
          (+ _far — дальний силуэт).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_pine.py -- atlas
python tools/build_spruce_atlas.py --pine
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_pine.py -- trees [preview] [pine_…]
python tools/build_spruce_atlas.py --pine --far
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_spruce as sp  # noqa: E402

Mesh, gpu, image, rolled = sp.Mesh, sp.gpu, sp.image, sp.rolled
X, Y, Z = sp.X, sp.Y, sp.Z
ROOT = sp.ROOT
SRC = ROOT / "_asset_src/pine"
RENDER = SRC / "render"
OUT, TEX = sp.OUT, sp.TEX
CELL_W, CELL_H = sp.CELL_W, sp.CELL_H


# ------------------------------------------------------------------ хвоя: веточки из скана (в 3D)

TWIGS = json.loads((SRC / "twigs.json").read_text(encoding="utf-8")) if (SRC / "twigs.json").exists() else {}


def twig(m: Mesh, key: str, base: Vector, d: Vector, side: Vector, length: float, col=(1, 1, 1, 1)) -> None:
    """Веточка скана: основание черенка — в base, вдоль d на length м, плоскость — d×side.
    Цвет вершин: r — яркость, g — сколько жёлтых игл позеленить (осень у разных кистей разная), b — сухая."""
    t = TWIGS["twigs"][key]
    size = TWIGS["size"]
    bx, by = t["base"]
    tx, ty = t["tip"]
    up = Vector((tx - bx, -(ty - by)))
    k = length / up.length
    up.normalize()
    right = Vector((up.y, -up.x))
    x0, y0, x1, y1 = t["box"]
    corners, uvs = [], []
    for (cx, cy) in [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]:
        rel = Vector((cx - bx, -(cy - by)))
        corners.append(base + d * (rel.dot(up) * k) + side * (rel.dot(right) * k))
        uvs.append((cx / size, 1.0 - cy / size))
    m.quad("twig", corners, uvs, col)


def stick(m: Mesh, pts: list, r0: float, r1: float, dead: bool = False) -> None:
    n = len(pts) - 1
    tone = (0.62, 0.6, 0.58, 1) if dead else (1, 1, 1, 1)
    m.tube("stick", pts, [r0 + (r1 - r0) * i / n for i in range(n + 1)], 6, (0.0, 0.25), 3.0, col_fn=lambda t: tone)


def twig_col(rng: random.Random, green: float, dead: bool = False):
    return (rng.uniform(0.72, 0.98), min(1.0, max(0.0, green + rng.uniform(-0.2, 0.2))), 1.0 if dead else 0.0, 1)


def whorl(m: Mesh, rng: random.Random, node: Vector, d: Vector, flat: float, up: float, green: float,
          dead: bool = False) -> None:
    """Побег этого года на конце: верхушечный (две скрещённые веточки скана) и 2–4 боковых. Длины — настоящие:
    побег с хвоей 11–15 см."""
    d = (d + Z * up * 0.3).normalized()
    side = d.cross(Z if abs(d.z) < 0.95 else X).normalized()
    upv = side.cross(d).normalized()
    ln = rng.uniform(0.12, 0.15)
    for roll in (0.0, math.pi / 2 + rng.uniform(-0.3, 0.3)):
        twig(m, "a", node, d, rolled(d, side, roll + rng.uniform(-0.2, 0.2)), ln, twig_col(rng, green, dead))
    k = rng.randint(2, 4)
    az0 = rng.uniform(0, 2 * math.pi)
    for j in range(k):
        az = az0 + 2 * math.pi * j / k + rng.uniform(-0.4, 0.4)
        lat = (side * math.cos(az) + upv * math.sin(az) * (1 - 0.7 * flat)).normalized()
        a = math.radians(rng.uniform(30, 55))
        nd = (d * math.cos(a) + lat * math.sin(a) + Z * up * 0.15).normalized()
        twig(m, rng.choice(["a", "b", "b"]), node, nd,
             rolled(nd, nd.cross(Z if abs(nd.z) < 0.95 else X).normalized(), rng.uniform(-0.9, 0.9)),
             rng.uniform(0.09, 0.13), twig_col(rng, green, dead))


def old_needles(m: Mesh, rng: random.Random, p0: Vector, p1: Vector, flat: float, green: float, dead: bool) -> None:
    """Хвоя прошлых лет вдоль прута: веточки скана под большим углом в обе стороны."""
    d = (p1 - p0).normalized()
    side = d.cross(Z if abs(d.z) < 0.95 else X).normalized()
    for t in (0.3, 0.75):
        p = p0.lerp(p1, t)
        for sgn in (-1, 1):
            nd = (d * 0.5 + side * sgn * 0.8 + Z * rng.uniform(-0.2, 0.3) * (1 - flat)).normalized()
            twig(m, "b", p, nd, rolled(nd, nd.cross(Z if abs(nd.z) < 0.95 else X).normalized(), rng.uniform(-0.7, 0.7)),
                 rng.uniform(0.08, 0.11), twig_col(rng, green * 0.6, dead))


def grow(m: Mesh, rng: random.Random, node: Vector, d: Vector, depth: int, flat: float, up: float, green: float,
         dead: bool = False) -> None:
    """Ветвление по годам: на старом узле — продолжение вперёд и 2–3 боковых побега, на концах — побеги этого года."""
    if depth == 0:
        whorl(m, rng, node, d, flat, up, green, dead)
        return
    d = (d + Z * up * 0.12).normalized()
    side = d.cross(Z if abs(d.z) < 0.95 else X).normalized()
    upv = side.cross(d).normalized()
    r = 0.0026 + 0.0012 * depth
    nf = node + (d + Vector((rng.uniform(-0.1, 0.1), rng.uniform(-0.1, 0.1), 0))).normalized() * rng.uniform(0.1, 0.13)
    stick(m, [node, nf], r, r * 0.85, dead)
    old_needles(m, rng, node, nf, flat, green, dead)
    grow(m, rng, nf, (nf - node).normalized(), depth - 1, flat, up, green, dead)
    k = rng.randint(2, 3)
    az0 = rng.uniform(0, 2 * math.pi)
    for j in range(k):
        az = az0 + 2 * math.pi * j / k + rng.uniform(-0.5, 0.5)
        lat = (side * math.cos(az) + upv * math.sin(az) * (1 - 0.75 * flat)).normalized()
        a = math.radians(rng.uniform(35, 60))
        nd = (d * math.cos(a) + lat * math.sin(a)).normalized()
        nl = node + nd * rng.uniform(0.07, 0.11)
        stick(m, [node, nl], r * 0.8, r * 0.7, dead)
        old_needles(m, rng, node, nl, flat, green, dead)
        grow(m, rng, nl, nd, depth - 1, flat, up, green, dead)


def tuft(m: Mesh, rng: random.Random, L: float, flat: float, up: float, green: float = 0.6, dead: bool = False) -> None:
    """Кисть на конце ветви: короткий голый отрезок и плотный ком побегов трёх последних лет."""
    node = Vector((L * 0.22, 0, 0))
    stick(m, [Vector((0, 0, 0)), node * 0.5, node], 0.0055, 0.0045, dead)
    grow(m, rng, node, X, 2, flat, up, green, dead)


def place(m: Mesh, sub: Mesh, at: Vector, d: Vector) -> None:
    """Перенести собранную в осях (+X — вперёд) кисть в точку at по направлению d."""
    dh = Vector((d.x, d.y, 0)).normalized()
    rot = Matrix(((dh.x, -dh.y, 0), (dh.y, dh.x, 0), (0, 0, 1)))
    for key, p in sub.parts.items():
        q = m.part(key)
        b = len(q["v"])
        q["v"].extend([at + rot @ v for v in p["v"]])
        q["f"].extend([[b + i for i in f] for f in p["f"]])
        q["uv"].extend(p["uv"])
        q["col"].extend(p["col"])
        q["nrm"].extend(p["nrm"])


def pad(m: Mesh, rng: random.Random, L: float, flat: float, up: float) -> None:
    """«Облако» хвои: ветвь вдоль +X, часто в стороны — короткие веточки, на каждой ком побегов."""
    pts = [Vector((L * i / 6, 0, 0.01 * math.sin(i * 1.3))) for i in range(7)]
    stick(m, pts, 0.01, 0.005)
    s = 0.1
    sgn = 1
    green = rng.uniform(0.3, 0.9)
    while s < L * 0.78:
        p = pts[0].lerp(pts[-1], s / L)
        a = math.radians(rng.uniform(40, 70))
        lat = Vector((0, sgn, 0)) if flat > 0.5 else Vector((0, sgn * 0.85, 0.5 * rng.choice([-1, 1])))
        d = (X * math.cos(a) + lat.normalized() * math.sin(a)).normalized()
        ln = rng.uniform(0.05, 0.16) * (1 - 0.5 * s / L)
        q = p + d * ln
        stick(m, [p, q], 0.005, 0.004)
        grow(m, rng, q, d, 2 if rng.random() < 0.45 else 1, flat, up, min(1.0, green + rng.uniform(-0.2, 0.2)))
        sgn = -sgn
        s += rng.uniform(0.07, 0.12)
    grow(m, rng, pts[-1], X, 2, flat, up, green)


def brush(m: Mesh, rng: random.Random, L: float) -> None:
    """Ветвь молодой сосны (вид сбоку): хвоя по всей длине, на конце мутовка."""
    pts = [Vector((L * 0.75 * i / 4, 0, 0.03 * (i / 4) ** 2)) for i in range(5)]
    stick(m, pts, 0.006, 0.004)
    for i in range(1, 9):
        p = pts[0].lerp(pts[-1], i / 9)
        for sgn in (-1, 1):
            nd = (X * 0.6 + Y * sgn * 0.45 + Z * rng.uniform(0.0, 0.5)).normalized()
            twig(m, rng.choice(["a", "b"]), p, nd, rolled(nd, nd.cross(Z).normalized(), rng.uniform(-1.2, 1.2)),
                 rng.uniform(0.1, 0.14), twig_col(rng, 0.7))
    grow(m, rng, pts[-1], (pts[-1] - pts[-2]).normalized(), 1, 0.2, 0.6, 0.7)


def dead_twig(m: Mesh, rng: random.Random, L: float) -> None:
    """Сухой сучок (вид сверху): серые голые прутья, на концах — редкие порыжевшие веточки."""
    def br(p0: Vector, d: Vector, ln: float, r: float, depth: int) -> None:
        pts = [p0]
        dd = d.copy()
        for _ in range(4):
            dd = (dd + Vector((rng.uniform(-0.2, 0.2), rng.uniform(-0.2, 0.2), 0))).normalized()
            pts.append(pts[-1] + dd * ln / 4)
        stick(m, pts, r, r * 0.4, True)
        if depth >= 2:
            if rng.random() < 0.35:
                twig(m, "b", pts[-1], dd, Z.cross(dd).normalized(), ln * 0.6, twig_col(rng, 0.0, True))
            return
        for _ in range(rng.randint(2, 4)):
            t = rng.uniform(0.3, 0.9)
            a = math.radians(rng.uniform(30, 60)) * rng.choice([-1, 1])
            nd = Vector((dd.x * math.cos(a) - dd.y * math.sin(a), dd.x * math.sin(a) + dd.y * math.cos(a), 0))
            br(pts[min(int(t * 4), 3)], nd, ln * rng.uniform(0.35, 0.55), r * 0.55, depth + 1)
    br(Vector((0, 0, 0)), X, L, 0.012, 0)


# имя, построитель, вид (top — сверху, side — сбоку), длина оси, ширина кадра (м), якорь по вертикали
CELLS = [
    ("tuft_top", lambda m, r: tuft(m, r, 0.4, 0.7, 0.2), "top", 0.5, 1.0, 0.5),
    ("tuft_side", lambda m, r: tuft(m, r, 0.4, 0.4, 1.6), "side", 0.5, 0.78, 0.6),
    ("pad_top", lambda m, r: pad(m, r, 0.8, 0.85, 0.2), "top", 0.9, 1.6, 0.5),
    ("pad_side", lambda m, r: pad(m, r, 0.8, 0.85, 1.6), "side", 0.9, 1.3, 0.6),
    ("brush", lambda m, r: brush(m, r, 0.7), "side", 0.75, 1.0, 0.56),
    ("dead", lambda m, r: dead_twig(m, r, 0.9), "top", 0.9, 1.1, 0.5),
]


def _link_normal_pass(nt, src):
    """Нормаль в пространстве камеры (к зрителю — +z), упакованная в цвет — как у атласа ели."""
    vt = nt.nodes.new("ShaderNodeVectorTransform")
    vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
    nt.links.new(src, vt.inputs[0])
    spn = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(vt.outputs[0], spn.inputs[0])
    neg = nt.nodes.new("ShaderNodeMath")
    neg.operation = "MULTIPLY"
    neg.inputs[1].default_value = -1.0
    nt.links.new(spn.outputs[2], neg.inputs[0])
    cb = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(spn.outputs[0], cb.inputs[0])
    nt.links.new(spn.outputs[1], cb.inputs[1])
    nt.links.new(neg.outputs[0], cb.inputs[2])
    ma = nt.nodes.new("ShaderNodeVectorMath")
    ma.operation = "MULTIPLY_ADD"
    ma.inputs[1].default_value = (0.5, 0.5, 0.5)
    ma.inputs[2].default_value = (0.5, 0.5, 0.5)
    nt.links.new(cb.outputs[0], ma.inputs[0])
    return ma.outputs[0]


def atlas_materials(mode: str) -> dict:
    """Рендер атласа: веточки скана (цвет × яркость, жёлтые иглы частично зеленеют, сухие — бурые;
    маска и нормаль скана) и прутья (кора скана)."""
    diff = image("pd", SRC / "twig_diff_2k.jpg", False)
    alpha = image("pa", SRC / "twig_alpha_2k.png", True)
    nor = image("pn", SRC / "twig_nor_gl_2k.jpg", True)
    bark = image("pk", SRC / "bark_diff_2k.jpg", False)
    mats = {}
    for key in ("twig", "stick"):
        mt = bpy.data.materials.get(key) or bpy.data.materials.new(key)
        mt.use_nodes = True
        nt = mt.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attr.outputs["Color"], sep.inputs[0])
        tc = nt.nodes.new("ShaderNodeTexImage")
        tc.image = diff if key == "twig" else bark
        nt.links.new(uv.outputs[0], tc.inputs[0])
        alpha_out = normal_out = None
        bright = nt.nodes.new("ShaderNodeMix")
        bright.data_type = "RGBA"
        bright.blend_type = "MULTIPLY"
        bright.inputs[0].default_value = 1.0
        if key == "twig":
            # жёлтые иглы (тон 0.12–0.17, насыщенные) → в зелень на долю g; сухая веточка (b) — в бурое
            hsv = nt.nodes.new("ShaderNodeSeparateColor")
            hsv.mode = "HSV"
            nt.links.new(tc.outputs["Color"], hsv.inputs[0])
            m1 = nt.nodes.new("ShaderNodeMapRange")
            m1.inputs["From Min"].default_value, m1.inputs["From Max"].default_value = 0.17, 0.12
            nt.links.new(hsv.outputs[0], m1.inputs["Value"])
            m2 = nt.nodes.new("ShaderNodeMapRange")
            m2.inputs["From Min"].default_value, m2.inputs["From Max"].default_value = 0.3, 0.5
            nt.links.new(hsv.outputs[1], m2.inputs["Value"])
            yel = nt.nodes.new("ShaderNodeMath")
            yel.operation = "MULTIPLY"
            nt.links.new(m1.outputs[0], yel.inputs[0])
            nt.links.new(m2.outputs[0], yel.inputs[1])
            k = nt.nodes.new("ShaderNodeMath")
            k.operation = "MULTIPLY"
            nt.links.new(yel.outputs[0], k.inputs[0])
            nt.links.new(sep.outputs[1], k.inputs[1])
            green = nt.nodes.new("ShaderNodeCombineColor")
            green.mode = "HSV"
            green.inputs[0].default_value = 0.24
            green.inputs[1].default_value = 0.42
            vv = nt.nodes.new("ShaderNodeMath")
            vv.operation = "MULTIPLY"
            vv.inputs[1].default_value = 0.62
            nt.links.new(hsv.outputs[2], vv.inputs[0])
            nt.links.new(vv.outputs[0], green.inputs[2])
            mx = nt.nodes.new("ShaderNodeMix")
            mx.data_type = "RGBA"
            nt.links.new(k.outputs[0], mx.inputs[0])
            nt.links.new(tc.outputs["Color"], mx.inputs[6])
            nt.links.new(green.outputs[0], mx.inputs[7])
            dry = nt.nodes.new("ShaderNodeHueSaturation")
            dry.inputs["Hue"].default_value = 0.47
            dry.inputs["Saturation"].default_value = 0.6
            dry.inputs["Value"].default_value = 0.75
            nt.links.new(tc.outputs["Color"], dry.inputs["Color"])
            mdry = nt.nodes.new("ShaderNodeMix")
            mdry.data_type = "RGBA"
            nt.links.new(sep.outputs[2], mdry.inputs[0])
            nt.links.new(mx.outputs[2], mdry.inputs[6])
            nt.links.new(dry.outputs[0], mdry.inputs[7])
            nt.links.new(mdry.outputs[2], bright.inputs[6])
            nt.links.new(sep.outputs[0], bright.inputs[7])
            ta = nt.nodes.new("ShaderNodeTexImage")
            ta.image = alpha
            nt.links.new(uv.outputs[0], ta.inputs[0])
            alpha_out = ta.outputs["Color"]
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            normal_out = nm.outputs[0]
        else:
            nt.links.new(tc.outputs["Color"], bright.inputs[6])
            nt.links.new(attr.outputs["Color"], bright.inputs[7])
        em = nt.nodes.new("ShaderNodeEmission")
        if mode == "albedo":
            nt.links.new(bright.outputs[2], em.inputs["Color"])
        elif mode == "normal":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            nt.links.new(_link_normal_pass(nt, normal_out if normal_out else geo.outputs["Normal"]), em.inputs["Color"])
        else:
            ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao.samples = 32
            ao.inputs["Distance"].default_value = 0.08
            nt.links.new(ao.outputs["AO"], em.inputs["Color"])
        if alpha_out is not None:
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(alpha_out, mix.inputs[0])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], out.inputs["Surface"])
        mats[key] = mt
    return mats


def render_atlas(only: list) -> None:
    RENDER.mkdir(parents=True, exist_ok=True)
    meta_path = RENDER / "cells.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    for ci, (name, fn, view, L, width, ay) in enumerate(CELLS):
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        sc = bpy.context.scene
        sc.render.engine = "CYCLES"
        gpu()
        sc.cycles.use_denoising = False
        sc.cycles.max_bounces = 0
        sc.cycles.transparent_max_bounces = 128
        sc.render.film_transparent = True
        sc.view_settings.view_transform = "Standard"
        sc.render.resolution_x, sc.render.resolution_y = CELL_W, CELL_H
        sc.render.image_settings.file_format = "PNG"
        sc.render.image_settings.color_mode = "RGBA"
        sc.render.image_settings.color_depth = "16"
        sc.render.filter_size = 1.2
        m = Mesh()
        fn(m, random.Random(3000 + ci))
        height = width * CELL_H / CELL_W
        margin = 0.03
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = width
        # ось ячейки — на доле ay от верхнего края кадра
        c = (ay - 0.5) * height
        if view == "top":
            cam.location = (width / 2 - margin, c, 3)
            cam.rotation_euler = (0, 0, 0)
        else:
            cam.location = (width / 2 - margin, -3, c)
            cam.rotation_euler = (math.pi / 2, 0, 0)
        cam.data.clip_start, cam.data.clip_end = 0.5, 6
        print("PINE cell", name, "веточек", len(m.parts.get("twig", {}).get("f", [])), flush=True)
        for mode in ("albedo", "normal", "ao"):
            for o in [o for o in sc.objects if o.type == "MESH"]:
                bpy.data.objects.remove(o, do_unlink=True)
            m.build(name, atlas_materials(mode))
            sc.cycles.samples = 96 if mode == "ao" else 48
            sc.render.filepath = str(RENDER / f"{name}_{mode}.png")
            bpy.ops.render.render(write_still=True)
            print("PINE render", name, mode, flush=True)
        meta[name] = dict(cell=ci, view=view, axis_len=L, width=width, height=round(height, 4), anchor=(margin / width, ay))
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ дерево

# H — высота; r0 — радиус ствола над комлем; crown — доля высоты без кроны; form — очертание кроны
# (cone — молодая, ovoid — лесная, umbrella — старая на просторе); Lmax — самая длинная ветвь;
# crook — кривизна ветвей и ствола в кроне; lean — наклон, °; stems — стволов от одного корня;
# plate — до какой доли высоты толстая плитчатая кора; leaders — ствол в кроне делится на N вершин.
VARIANTS = {
    "pine_young": dict(H=6.5, r0=0.075, crown=0.04, form="cone", Lmax=1.7, crook=0.25, lean=2, stems=1, plate=0.0,
                       leaders=0, seed=7),
    "pine_slim_a": dict(H=20.0, r0=0.11, crown=0.7, form="ovoid", Lmax=2.2, crook=0.5, lean=3, stems=1, plate=0.08,
                        leaders=0, seed=13),
    "pine_slim_b": dict(H=23.5, r0=0.15, crown=0.64, form="ovoid", Lmax=2.8, crook=0.6, lean=2, stems=1, plate=0.12,
                        leaders=0, seed=29),
    "pine_forest": dict(H=26.0, r0=0.25, crown=0.58, form="ovoid", Lmax=3.8, crook=0.75, lean=1.5, stems=1, plate=0.22,
                        leaders=0, seed=41),
    "pine_thick": dict(H=28.0, r0=0.37, crown=0.52, form="ovoid", Lmax=5.0, crook=0.9, lean=1, stems=1, plate=0.32,
                       leaders=2, seed=53),
    "pine_old": dict(H=21.0, r0=0.48, crown=0.24, form="umbrella", Lmax=7.0, crook=1.0, lean=4, stems=1, plate=0.4,
                     leaders=3, seed=67),
    # во дворе: росла на просторе — крона с трети высоты, широкая, ствол толстый
    "pine_yard": dict(H=17.0, r0=0.3, crown=0.3, form="ovoid", Lmax=4.6, crook=0.85, lean=3, stems=1, plate=0.3,
                      leaders=0, seed=91),
    "pine_twin": dict(H=21.0, r0=0.16, crown=0.5, form="ovoid", Lmax=3.4, crook=0.7, lean=7, stems=2, plate=0.14,
                      leaders=0, seed=79),
}


def envelope(form: str, rel: float) -> float:
    """Длина ветви (доля Lmax) по высоте в кроне: rel 0 — низ кроны, 1 — вершина."""
    rel = min(max(rel, 0.0), 1.0)
    if form == "cone":
        return 0.12 + 0.88 * (1 - rel) ** 0.95
    if form == "umbrella":
        return (1 - rel) ** 0.3 * min(1.0, 0.65 + rel * 1.3)
    return (1 - rel) ** 0.38 * min(1.0, 0.55 + rel * 2.2)


class Tree:
    def __init__(self, v: dict) -> None:
        self.v = v
        self.rng = random.Random(v["seed"])
        self.m = Mesh()
        self.H = v["H"]
        self.hb = self.H * v["crown"]
        self.center = Vector((0, 0, self.hb + (self.H - self.hb) * 0.45))
        self.spines: list = []

    # ---------------- ствол
    def stem(self, base: Vector, lean_dir: Vector, lean: float, H: float, r0: float, top_z: float) -> list:
        rng, v = self.rng, self.v
        spine = []
        z = -0.5
        wob = [rng.uniform(0, 6.28) for _ in range(4)]
        tilt = math.tan(math.radians(lean))
        while z < top_z:
            h = max(z, 0.0)
            # в кроне ствол кривее (у старых сосен — заметно)
            k = 0.04 + v["crook"] * 0.16 * max(0.0, (h - self.hb) / max(H - self.hb, 1.0))
            off = lean_dir * (tilt * h * (0.6 + 0.4 * h / H))
            off += Vector((math.sin(h * 0.21 + wob[0]) + 0.5 * math.sin(h * 0.55 + wob[1]),
                           math.sin(h * 0.17 + wob[2]) + 0.5 * math.sin(h * 0.49 + wob[3]), 0)) * k * min(1.0, h / 3 + 0.15)
            spine.append(base + off + Z * z)
            z += 0.12 if z < 1.8 else 0.5
        spine.append(spine[-1].copy() + Z * 0.0)
        spine[-1].z = base.z + top_z
        sides = 18 if r0 > 0.3 else (14 if r0 > 0.14 else 10)
        p = self.m.part("trunk")
        start = len(p["v"])
        tile = 0.9
        reps = max(1, round(2 * math.pi * r0 / tile))
        ph = rng.uniform(0, 6.28)
        plate_z = v["plate"] * H + (1.2 if r0 > 0.1 else 0.0)
        for c in spine:
            h = max(c.z - base.z, 0.0)
            r = self.radius_at(h, H, r0)
            flare = max(0.0, 1 - max(c.z - base.z, -0.5) / (0.9 + 1.5 * r0))
            for kk in range(sides + 1):
                a = 2 * math.pi * kk / sides
                lobe = 1 + flare ** 2 * (0.35 + 0.55 * max(0.0, math.cos(4 * a + ph)) ** 2)
                bump = 1 + 0.025 * math.sin(7 * a + h * 1.3 + ph) * min(1.0, r0 * 4)
                p["v"].append(c + Vector((math.cos(a), math.sin(a), 0)) * r * lobe * bump)
                ao = 0.6 if self.hb < h < H - 1 else 0.92
                # граница плитчатой коры — неровная, «языками» вверх
                edge = plate_z * (1 + 0.22 * math.sin(3 * a + ph) + 0.12 * math.sin(8 * a + ph * 2))
                plate = 1.0 - min(1.0, max(0.0, (h - edge) / max(1.5, plate_z * 0.35) + 0.5)) if plate_z > 0 else 0.0
                p["col"].append((ao, (h / H) ** 2 * 0.25, 0.0, plate))
                p["nrm"].append(None)
        ring = sides + 1
        for i in range(len(spine) - 1):
            for kk in range(sides):
                a0 = start + i * ring + kk
                p["f"].append([a0, a0 + 1, a0 + ring + 1, a0 + ring])
                p["uv"].append([(reps * kk / sides, spine[i].z / tile), (reps * (kk + 1) / sides, spine[i].z / tile),
                                (reps * (kk + 1) / sides, spine[i + 1].z / tile), (reps * kk / sides, spine[i + 1].z / tile)])
        self.spines.append((spine, H, r0, base))
        self.reach = max(getattr(self, "reach", 0.0), Vector((base.x, base.y, 0)).length + self.radius_at(1.3, H, r0))
        return spine

    @staticmethod
    def radius_at(h: float, H: float, r0: float) -> float:
        return r0 * max(1 - h / H, 0.0) ** 0.62 + 0.012

    # ---------------- ветви
    def limb(self, start: Vector, d: Vector, L: float, r: float, level: int, rel: float, flex0: float, phase: float) -> None:
        """Ветвь сосны: изломанная (crook), поднимается и выходит к горизонтали, кончик вверх.
        Хвоя — пучками на концах её веточек; внутри кроны ветви голые."""
        rng, v = self.rng, self.v
        segs = 7 if L > 2.5 else (5 if L > 1.0 else 3)
        hor = Vector((d.x, d.y, 0))
        hor = hor.normalized() if hor.length > 1e-4 else X.copy()
        e = math.asin(max(-1.0, min(1.0, d.z)))
        az = math.atan2(hor.y, hor.x)
        young = v["form"] == "cone"
        pts = [start]
        for i in range(segs):
            s = (i + 0.5) / segs
            e_target = math.radians(8 + 30 * rel) if not young else math.radians(38 + 20 * rel)
            e_i = e + (e_target - e) * s + math.radians(14) * s ** 3
            e_i += math.radians(rng.gauss(0, 9 * v["crook"]))
            az_i = az + rng.gauss(0, 0.12 * v["crook"])
            az = az_i
            dd = Vector((math.cos(az_i) * math.cos(e_i), math.sin(az_i) * math.cos(e_i), math.sin(e_i)))
            pts.append(pts[-1] + dd * (L / segs))
        radii = [max(r * (1 - 0.72 * i / segs), 0.005) for i in range(segs + 1)]
        fk = min(1.0, 0.35 + 0.65 * L / max(v["Lmax"], 0.1))
        plate = 0.6 if r > 0.12 else 0.0
        self.m.tube("branch", pts, radii, 7 if r > 0.08 else (5 if r > 0.025 else 4), (0.0, 1.0), 1.4,
                    col_fn=lambda t, a=fk, b=phase, f0=flex0, pl=plate: (0.55 + 0.4 * t, f0 + (a - f0) * t, b, pl * (1 - t)))

        def at(s: float):
            seg = s * segs
            i = min(int(seg), segs - 1)
            return pts[i].lerp(pts[i + 1], seg - i), (pts[i + 1] - pts[i]).normalized()

        tip, tdir = at(1.0)
        if young:
            # молодая: хвоя по всей ветви кистями
            s = 0.25
            while s < 0.98:
                p, t = at(s)
                self.cluster(p, t, 0.5 + 0.4 * L / v["Lmax"], rel, fk * s, phase, kind="brush")
                s += 0.45 / max(L, 0.3) * rng.uniform(0.8, 1.2)
            self.cluster(tip, tdir, min(0.9, 0.35 + L * 0.3), rel, fk, phase)
            return
        # веточки: на внешних 2/3 ветви, поочерёдно в стороны, у старых — длиннее и сами ветвятся
        n_side = min(int(L * (2.6 if level == 0 else 1.8)) + rng.randint(1, 2), 5 if level == 0 else 3)
        sgn = rng.choice([-1, 1])
        for j in range(n_side):
            s = rng.uniform(0.3, 0.92) if level == 0 else rng.uniform(0.25, 0.85)
            p, t = at(s)
            th = Vector((t.x, t.y, 0)).normalized() if abs(t.z) < 0.97 else X
            side = th.cross(Z) * sgn
            sgn = -sgn
            a = math.radians(rng.uniform(30, 65))
            nd = (t * math.cos(a) + side * math.sin(a) + Z * rng.uniform(-0.05, 0.3)).normalized()
            ln = L * rng.uniform(0.3, 0.5) * (1 - 0.35 * s)
            if level < 1 and ln > 1.1:
                self.limb(p, nd, ln, radii[min(int(s * segs), segs)] * 0.55, level + 1, rel, flex0 + (fk - flex0) * s, phase)
            else:
                q = [p, p + nd * ln * 0.5 + Z * 0.03, p + nd * ln]
                self.m.tube("branch", q, [max(0.012 * ln, 0.006), 0.006, 0.004], 4, (0.0, 1.0), 1.4,
                            col_fn=lambda tt, b=phase, f=flex0 + (fk - flex0) * s: (0.75, f + 0.2 * tt, b, 0.0))
                self.cluster(q[-1], nd, min(1.5, 0.75 + ln * 0.55), rel, min(1.0, flex0 + (fk - flex0) * s + 0.2), phase)
        self.cluster(tip, tdir, min(1.6, 0.8 + L * 0.2), rel, fk, phase)
        if L > 2.6:
            p, t = at(0.78)
            self.cluster(p, t, min(1.1, 0.5 + L * 0.12), rel, fk * 0.8, phase)

    def cluster(self, pt: Vector, d: Vector, size: float, rel: float, flex: float, phase: float, kind: str = "") -> None:
        """Пучок хвои: «облако» сверху + вид сбоку (кисти вверх) + косой вид — объём с любого ракурса."""
        rng = self.rng
        hor = Vector((d.x, d.y, 0))
        hor = hor.normalized() if hor.length > 1e-3 else Vector((1, 0, 0))
        lat = hor.cross(Z)
        big = size > 1.0 and kind != "brush"
        top, side = ("pad_top", "pad_side") if big else ("tuft_top", "tuft_side")
        if kind == "brush":
            top, side = "tuft_top", "brush"
        outward = Vector((pt.x - self.center.x, pt.y - self.center.y, 0))
        dist = outward.length
        out_n = (outward.normalized() * 0.75 + Z * 0.65).normalized() if dist > 1e-3 else Z.copy()
        crown_r = max(self.v["Lmax"] * 0.9, 1.0)
        ao = (0.58 + 0.42 * min(1.0, dist / crown_r) ** 0.7) * (0.82 + 0.18 * rel)
        col = (ao, min(flex, 1.0), phase, 1.0)
        L_top = sp.ATLAS[top]["axis_len"]
        L_side = sp.ATLAS[side]["axis_len"]
        back = 0.3
        # сверху: ось вдоль ветви, слегка вверх
        tilt = math.radians(rng.uniform(4, 18))
        u = (hor * math.cos(tilt) + Z * math.sin(tilt)).normalized()
        vv = rolled(u, lat * rng.choice([-1, 1]), math.radians(rng.uniform(-18, 18)))
        sc = size / L_top * rng.uniform(0.9, 1.1)
        sp.card(self.m, top, pt - u * size * back, u, vv, sc, col, out_n, 0.6)
        # сбоку: кисти вверх
        for k in range(1):
            yaw = math.radians(rng.uniform(-25, 25) + (0 if k == 0 else rng.choice([-1, 1]) * rng.uniform(55, 80)))
            hh = (hor * math.cos(yaw) + lat * math.sin(yaw)).normalized()
            u2 = (hh * math.cos(math.radians(rng.uniform(5, 20))) + Z * math.sin(math.radians(rng.uniform(5, 20)))).normalized()
            down = -Z - u2 * (-Z).dot(u2)
            v2 = rolled(u2, down.normalized(), math.radians(rng.uniform(-15, 15)))
            sc2 = size / L_side * rng.uniform(0.85, 1.05)
            sp.card(self.m, side, pt - u2 * size * back + Z * 0.02, u2, v2, sc2, (ao * 0.95, col[1], phase, 1.0), out_n, 0.55)

    def dead_stubs(self, spine: list, base: Vector, H: float, r0: float) -> None:
        """Сухие сучья и сучки на голом стволе лесной сосны — редкие, короткие."""
        rng = self.rng
        z = 2.2
        while z < self.hb - 0.4:
            if rng.random() < 0.55:
                c = sp.trunk_at(spine, base.z + z)
                az = rng.uniform(0, 2 * math.pi)
                hor = Vector((math.cos(az), math.sin(az), 0))
                r_t = self.radius_at(z, H, r0)
                L = rng.uniform(0.08, 0.25) if rng.random() < 0.65 else rng.uniform(0.4, 1.3) * min(1.0, 0.5 + r0 * 2)
                e = math.radians(rng.uniform(-30, 5))
                dd = hor * math.cos(e) + Z * math.sin(e)
                p0 = c + hor * r_t * 0.85
                pts = [p0 + dd * L * i / 3 for i in range(4)]
                rr = rng.uniform(0.015, 0.035) * min(1.0, 0.5 + r0 * 2)
                self.m.tube("deadbranch", pts, [rr, rr * 0.8, rr * 0.55, rr * 0.3], 5, (0.0, 1.0), 2.0,
                            col_fn=lambda t: (0.85, 0.0, 0.0, 0.0))
                if L > 0.6 and rng.random() < 0.6:
                    u = dd
                    vv = rolled(u, u.cross(Z).normalized(), rng.uniform(-1.0, 1.0))
                    sp.card(self.m, "dead", pts[1], u, vv, L * 0.9 / sp.ATLAS["dead"]["axis_len"], (0.8, 0.0, 0.0, 1.0), Z, 0.3)
            z += rng.uniform(0.35, 0.8)

    # ---------------- сборка
    def build(self) -> Mesh:
        v, rng = self.v, self.rng
        golden = math.radians(137.5)
        for si in range(v["stems"]):
            az_lean = rng.uniform(0, 2 * math.pi) + si * math.pi
            lean_dir = Vector((math.cos(az_lean), math.sin(az_lean), 0))
            base = lean_dir * (0.14 * si if v["stems"] > 1 else 0.0)
            H = self.H * (1.0 if si == 0 else rng.uniform(0.85, 0.93))
            r0 = v["r0"] * (1.0 if si == 0 else 0.85)
            lean = v["lean"] * (1 if v["stems"] == 1 else 1.3)
            top_z = H * 0.72 if v["leaders"] else H
            spine = self.stem(base, lean_dir, lean, H, r0, top_z)
            self.dead_stubs(spine, base, H, r0)
            # вершины: ствол в кроне делится на 2–3 толстых сука, уходящих вверх
            if v["leaders"]:
                fork = spine[-1]
                rf = self.radius_at(top_z, H, r0)
                for k in range(v["leaders"]):
                    a = rng.uniform(0, 2 * math.pi) if k == 0 else a + 2 * math.pi / v["leaders"] + rng.uniform(-0.5, 0.5)
                    e = math.radians(rng.uniform(48, 68))
                    d = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
                    self.limb(fork, d, (H - top_z) * rng.uniform(1.0, 1.25), rf * 0.72, 0, 0.92, 0.1, rng.random())
            # живые ветви: мутовки от низа кроны до вершины
            z = self.hb
            whorl = 0
            az0 = rng.uniform(0, 6.28)
            step = 0.55 if v["form"] == "cone" else (0.75 if v["form"] == "umbrella" else 0.55)
            top_live = top_z if v["leaders"] else H - 0.4
            while z < top_live:
                rel = (z - self.hb) / max(H - self.hb, 0.1)
                L0 = v["Lmax"] * envelope(v["form"], rel)
                n = rng.randint(3, 5) if v["form"] == "cone" else rng.randint(3, 4)
                for k in range(n):
                    if v["form"] != "cone" and rng.random() < 0.12:
                        continue
                    az = az0 + whorl * golden + 2 * math.pi * k / n + rng.uniform(-0.4, 0.4)
                    L = L0 * rng.uniform(0.75, 1.08)
                    if L < 0.25:
                        continue
                    c = sp.trunk_at(spine, base.z + z)
                    hor = Vector((math.cos(az), math.sin(az), 0))
                    r_t = self.radius_at(z, H, r0)
                    e = math.radians((45 + 15 * rel) if v["form"] == "cone" else (8 + 42 * rel ** 1.3 + rng.uniform(-8, 8)))
                    d = hor * math.cos(e) + Z * math.sin(e)
                    rb = min(r_t * 0.55, 0.012 + 0.035 * (L / v["Lmax"]) ** 1.1 * (1 + v["r0"] * 2))
                    self.limb(c + hor * r_t * 0.8, d, L, rb, 0, rel, 0.05, rng.random())
                z += step * rng.uniform(0.8, 1.25)
                whorl += 1
            if not v["leaders"]:
                # вершина: побег-лидер и кисти вокруг
                top = sp.trunk_at(spine, base.z + H - 0.35)
                cell = "brush" if v["form"] == "cone" else "tuft_side"
                for k in range(3):
                    a = k * math.pi / 3
                    side = Vector((math.cos(a), math.sin(a), 0))
                    sp.card(self.m, cell, top - Z * 0.25, Z, side.cross(Z).normalized(), (0.9 if v["form"] == "cone" else 1.2) /
                            sp.ATLAS[cell]["axis_len"], (1.0, 0.3, 0.5, 1.0), (side * 0.3 + Z * 0.7).normalized(), 0.5)
        return self.m


MAT_NAMES = {"needles": "PineNeedles", "trunk": "PineTrunk", "branch": "PineBranch", "deadbranch": "SpruceDeadBranch"}


def preview(name: str, ob, H: float, r_trunk: float) -> None:
    """Превью (Cycles): атлас, кора (плитчатая ↔ оранжевая по альфе цвета вершин), небо, солнце."""
    sc = bpy.context.scene
    alb = image("pa", TEX / "pine_atlas_albedo.png", False)
    nor = image("pn", TEX / "pine_atlas_normal.png", True)
    bark = image("pb", ROOT / "assets/textures/pine_bark/albedo.jpg", False)
    for mt in ob.data.materials:
        mt.use_nodes = True
        nt = mt.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attr.outputs["Color"], sep.inputs[0])
        t = nt.nodes.new("ShaderNodeTexImage")
        nt.links.new(uv.outputs[0], t.inputs[0])
        if mt.name.startswith("PineNeedles"):
            t.image = alb
            pw = nt.nodes.new("ShaderNodeMath")
            pw.operation = "POWER"
            pw.inputs[1].default_value = 0.6
            nt.links.new(sep.outputs[0], pw.inputs[0])
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs[0].default_value = 1.0
            nt.links.new(t.outputs["Color"], mul.inputs[6])
            nt.links.new(pw.outputs[0], mul.inputs[7])
            nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
            bsdf.inputs["Roughness"].default_value = 0.8
            continue
        t.image = bark
        # плитчатая — серо-бурая; тонкая верхняя — оранжевая по яркости той же коры
        hs = nt.nodes.new("ShaderNodeHueSaturation")
        hs.inputs["Saturation"].default_value = 0.5
        hs.inputs["Value"].default_value = 0.85
        nt.links.new(t.outputs["Color"], hs.inputs["Color"])
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(t.outputs["Color"], bw.inputs[0])
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.05
        ramp.color_ramp.elements[0].color = (0.11, 0.035, 0.014, 1)
        ramp.color_ramp.elements[1].position = 0.32
        ramp.color_ramp.elements[1].color = (0.62, 0.24, 0.1, 1)
        nt.links.new(bw.outputs[0], ramp.inputs[0])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(attr.outputs["Alpha"], mix.inputs[0])
        nt.links.new(ramp.outputs[0], mix.inputs[6])
        nt.links.new(hs.outputs[0], mix.inputs[7])
        if mt.name.startswith("SpruceDeadBranch"):
            nt.links.new(hs.outputs[0], bsdf.inputs["Base Color"])
        else:
            nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.55, 0.66, 0.85, 1)
    sc.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(55), 0, math.radians(35))
    sc.collection.objects.link(sun)
    gme = bpy.data.meshes.new("g")
    gme.from_pydata([(-80, -80, 0), (80, -80, 0), (80, 80, 0), (-80, 80, 0)], [], [[0, 1, 2, 3]])
    gm = bpy.data.materials.new("gm")
    gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.14, 0.12, 0.06, 1)
    gme.materials.append(gm)
    sc.collection.objects.link(bpy.data.objects.new("g", gme))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.lens = 50
    cam.location = (0, -H * 1.75, H * 0.48)
    cam.rotation_euler = (math.radians(90), 0, 0)
    sc.render.engine = "CYCLES"
    gpu()
    sc.cycles.samples = 64
    sc.cycles.transparent_max_bounces = 256
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 900, 1200
    sc.render.filepath = str(RENDER / f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)
    # ствол вблизи — кора и комель на уровне глаз
    cam.data.lens = 35
    cam.location = (0.4, -max(3.2, r_trunk * 9), 1.7)
    cam.rotation_euler = (math.radians(80), 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 900, 900
    sc.render.filepath = str(RENDER / f"preview_{name}_trunk.png")
    bpy.ops.render.render(write_still=True)
    print("PINE preview", name, flush=True)


def build_trees(do_preview: bool, only: list) -> None:
    sp.ATLAS.clear()
    sp.ATLAS.update(json.loads((TEX / "pine_atlas.json").read_text(encoding="utf-8")))
    path = OUT / "pine.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, v in VARIANTS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        tree = Tree(v)
        ob = tree.build().build(name, {k: bpy.data.materials.new(n) for k, n in MAT_NAMES.items()})
        n = sp.export_tree(name, ob)
        r13 = tree.reach
        manifest[name] = dict(triangles=n, height=v["H"], trunk_radius=round(r13, 3),
                              collisions=[dict(pos=[0, 2.0, 0], size=[round(r13 * 2, 3), 4.0, round(r13 * 2, 3)], yaw=0)])
        print("PINE tree", name, n, "треугольников, ствол r", round(r13, 3), flush=True)
        if do_preview:
            preview(name, ob, v["H"], r13)
        width = max(abs(c) for vtx in ob.data.vertices for c in (vtx.co.x, vtx.co.y))
        manifest[name]["far"] = sp.render_impostor(name, ob, v["H"], width, atlas="pine_atlas",
                                                   bark_path=ROOT / "assets/textures/pine_bark/albedo.jpg",
                                                   foliage_prefix="PineNeedles")
        sp.far_mesh(name, manifest[name]["far"], "PineFar")
    path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "atlas" in args:
        render_atlas([a for a in args if a in {c[0] for c in CELLS}])
    if "trees" in args:
        sp.RENDER = RENDER
        build_trees("preview" in args, [a for a in args if a.startswith("pine_")])
