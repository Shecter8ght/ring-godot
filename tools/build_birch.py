"""Берёза повислая (Betula pendula) для зоны 1, bpy. Как у ели (tools/build_spruce.py), два этапа:

  atlas — веточки в 3D (тонкие тёмные прутья, листья — скан ambientCG LeafSet024, переформованный в
          берёзовый лист tools/build_birch_textures.py), рендер Cycles в ячейки атласа: цвет, нормаль,
          затенение. Поздняя осень: листья редкие, от зеленовато-жёлтых до золотых, часть с бурыми
          пятнами; есть ячейки голых прутьев — «дымка» берёзы в тумане. Склейка — build_spruce_atlas.py --birch.
  trees — берёза по референсам владельца: волнистые стволы, кустом по 2–3 из одного корня, ветви
          уходят вверх под 40–55° и дугой опускаются к концам, с них висят пряди тонких веточек;
          крона яйцевидная, рыхлая. → assets/zone01/models/birch_*.glb (+ _far — дальний силуэт).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_birch.py -- atlas
python tools/build_spruce_atlas.py --birch
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_birch.py -- trees [preview]
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_spruce as sp  # noqa: E402

Mesh, gpu, image, rolled = sp.Mesh, sp.gpu, sp.image, sp.rolled
X, Y, Z = sp.X, sp.Y, sp.Z
ROOT = sp.ROOT
SRC = ROOT / "_asset_src/birch"
RENDER = SRC / "render"
OUT, TEX = sp.OUT, sp.TEX
LEAVES = json.loads((SRC / "leaves_birch.json").read_text(encoding="utf-8"))
CELL_W, CELL_H = sp.CELL_W, sp.CELL_H


# ------------------------------------------------------------------ веточки атласа

def leaf(m: Mesh, rng: random.Random, base: Vector, d: Vector, side: Vector, autumn: float) -> None:
    """Лист: черешок в base, кончик вдоль d. Цвет вершин: r — яркость, g — пожелтение, b — бурые пятна."""
    lf = rng.choice(LEAVES)
    size = lf["size"]
    bx, by = lf["base"]
    tx, ty = lf["tip"]
    up = Vector((tx - bx, -(ty - by)))
    k = rng.uniform(0.045, 0.068) / up.length
    up.normalize()
    right = Vector((up.y, -up.x))
    x0, y0, x1, y1 = lf["box"]
    pts, uvs = [], []
    for cx, cy in [(x0, y1), (x1, y1), (x1, y0), (x0, y0)]:
        rel = Vector((cx - bx, -(cy - by)))
        pts.append(base + d * (rel.dot(up) * k) + side * (rel.dot(right) * k))
        uvs.append((cx / size, 1.0 - cy / size))
    yellow = min(1.0, max(0.0, rng.gauss(autumn, 0.22)))
    col = (rng.uniform(0.82, 1.05), yellow, rng.uniform(0.0, 0.35) if rng.random() < 0.35 else 0.0, 1.0)
    m.quad("leaf", pts, uvs, col)


def strand(m: Mesh, rng: random.Random, start: Vector, out: Vector, length: float, leafy: float, autumn: float,
           depth: int = 0) -> None:
    """Повислая прядь: короткий выход вбок-вниз, затем почти отвесно; по ней — побеги с листьями парами."""
    pts = [start]
    d = (out * rng.uniform(0.4, 0.9) + Vector((0, 0, -0.5))).normalized()
    n = 9
    pull = rng.uniform(0.25, 0.6)
    for i in range(n):
        d = (d * (1 - pull * 0.5) + Vector((rng.uniform(-0.12, 0.12), rng.uniform(-0.12, 0.12), -pull))).normalized()
        pts.append(pts[-1] + d * (length / n))
    m.tube("twig", pts, [(0.0016 if depth == 0 else 0.0011) * (1 - 0.55 * i / n) for i in range(n + 1)], 3, (0.0, 1.0), 6.0)
    s = 0.04
    while s < length:
        i = min(int(s / length * n), n - 1)
        p = pts[i].lerp(pts[i + 1], s / length * n - i)
        tang = (pts[i + 1] - pts[i]).normalized()
        lat = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
        if rng.random() < leafy:
            for _ in range(rng.choice([1, 2, 2, 3])):
                dd = (tang * 0.35 + lat * rng.uniform(0.3, 0.8) + Vector((0, 0, -0.35))).normalized()
                sd = rolled(dd, dd.cross(Y).normalized() if abs(dd.dot(Y)) < 0.9 else X, math.radians(rng.uniform(-65, 65)))
                leaf(m, rng, p + lat * 0.008, dd, sd, autumn)
        elif rng.random() < 0.6:
            # голый побег: прутик вбок-вниз
            q = p + (lat * 0.7 + Vector((0, 0, -0.45))).normalized() * rng.uniform(0.03, 0.1)
            m.tube("twig", [p, (p + q) * 0.5 + Vector((0, 0, -0.005)), q], [0.0009, 0.0007, 0.0004], 3, (0.0, 1.0), 6.0)
        if depth == 0 and rng.random() < 0.22:
            strand(m, rng, p, lat, length * rng.uniform(0.3, 0.55), leafy, autumn, 1)
        s += rng.uniform(0.022, 0.04)


def hang_cell(m: Mesh, rng: random.Random, L: float, leafy: float, autumn: float) -> None:
    """Вид сбоку: ветка вдоль +X у верхнего края кадра, с неё висят пряди (длиннее к середине)."""
    pts = [Vector((L * i / 12, 0, -0.03 * math.sin(math.pi * i / 12))) for i in range(13)]
    m.tube("twig", pts, [0.0045 - 0.003 * i / 12 for i in range(13)], 5, (0.0, 1.0), 6.0)
    s = 0.03
    while s < L * 0.97:
        i = min(int(s / L * 12), 11)
        p = pts[i].lerp(pts[i + 1], s / L * 12 - i) + Vector((0, rng.uniform(-0.03, 0.03), 0))
        hang = (0.18 + 0.4 * math.sin(math.pi * min(1.0, s / L + 0.1))) * rng.uniform(0.45, 1.05)
        strand(m, rng, p, Vector((0.5, rng.uniform(-0.6, 0.6), 0)).normalized(), hang, leafy, autumn)
        s += rng.uniform(0.025, 0.06)


def upright_cell(m: Mesh, rng: random.Random, L: float, leafy: float, autumn: float) -> None:
    """Вид сбоку: побег вдоль +X (в дереве — вверх-наружу), веточки под 30–50°, листья вдоль."""
    pts = [Vector((L * i / 12, 0, 0.02 * math.sin(i))) for i in range(13)]
    m.tube("twig", pts, [0.0045 - 0.0033 * i / 12 for i in range(13)], 5, (0.0, 1.0), 6.0)
    for i in [x * 0.5 for x in range(2, 24)]:
        i = int(i)
        if rng.random() < 0.85:
            base = pts[i]
            ang = math.radians(rng.uniform(25, 50))
            side = rng.choice([-1, 1])
            d = Vector((math.cos(ang), rng.uniform(-0.4, 0.4), side * math.sin(ang))).normalized()
            ln = L * (1.0 - i / 14) * rng.uniform(0.25, 0.45)
            q = [base + d * ln * k / 5 + Vector((0, 0, -0.04 * (k / 5) ** 2)) for k in range(6)]
            m.tube("twig", q, [0.0014 * (1 - 0.6 * k / 5) for k in range(6)], 3, (0.0, 1.0), 6.0)
            for k in range(1, 6):
                if rng.random() < 0.5:
                    dd = (d + Vector((0, rng.uniform(-0.8, 0.8), rng.uniform(-0.5, 0.5)))).normalized()
                    m.tube("twig", [q[k], q[k] + dd * ln * 0.3], [0.0008, 0.0004], 3, (0.0, 1.0), 6.0)
                    if rng.random() < leafy:
                        leaf(m, rng, q[k] + dd * ln * 0.3, dd, rolled(dd, dd.cross(Y).normalized(), math.radians(rng.uniform(-60, 60))), autumn)
                if rng.random() < leafy:
                    dd = (d * 0.4 + Vector((0, rng.uniform(-0.7, 0.7), rng.uniform(-0.6, 0.3)))).normalized()
                    leaf(m, rng, q[k], dd, rolled(dd, dd.cross(Y).normalized(), math.radians(rng.uniform(-60, 60))), autumn)
    for k in range(1, 12):
        if rng.random() < leafy * 0.8:
            dd = Vector((0.3, rng.uniform(-0.5, 0.5), rng.choice([-1, 1]) * 0.8)).normalized()
            leaf(m, rng, pts[k], dd, rolled(dd, dd.cross(Y).normalized(), math.radians(rng.uniform(-60, 60))), autumn)


def spray_cell(m: Mesh, rng: random.Random, L: float, leafy: float, autumn: float) -> None:
    """Вид сверху: веер прутьев вдоль +X, листья лицом вверх."""
    pts = [Vector((L * i / 12, 0.015 * math.sin(i * 0.9), 0)) for i in range(13)]
    m.tube("twig", pts, [0.004 - 0.003 * i / 12 for i in range(13)], 5, (0.0, 1.0), 6.0)
    side = 1
    for i in [int(x * 0.5) for x in range(2, 24)]:
        base = pts[i]
        ang = math.radians(rng.uniform(30, 60))
        d = Vector((math.cos(ang), side * math.sin(ang), rng.uniform(-0.1, 0.1))).normalized()
        ln = L * (1.0 - i / 14) * rng.uniform(0.3, 0.5)
        q = [base + d * ln * k / 5 for k in range(6)]
        m.tube("twig", q, [0.0013 * (1 - 0.6 * k / 5) for k in range(6)], 3, (0.0, 1.0), 6.0)
        for k in range(1, 6):
            if rng.random() < leafy:
                dd = (d * 0.6 + Vector((rng.uniform(-0.4, 0.4), rng.uniform(-0.4, 0.4), 0))).normalized()
                leaf(m, rng, q[k], dd, rolled(dd, Z.cross(dd).normalized(), math.radians(rng.uniform(-35, 35))), autumn)
        side = -side


CELLS = [
    ("hang_a", lambda m, r: hang_cell(m, r, 1.0, 0.5, 0.62), "side_hang", 1.0, 1.24),
    ("hang_b", lambda m, r: hang_cell(m, r, 0.8, 0.38, 0.78), "side_hang", 0.8, 1.0),
    ("bare_a", lambda m, r: hang_cell(m, r, 1.0, 0.05, 0.85), "side_hang", 1.0, 1.24),
    ("bare_b", lambda m, r: hang_cell(m, r, 0.8, 0.02, 0.85), "side_hang", 0.8, 1.0),
    ("upright", lambda m, r: upright_cell(m, r, 1.0, 0.45, 0.6), "side", 1.0, 1.36),
    ("spray", lambda m, r: spray_cell(m, r, 0.9, 0.5, 0.7), "top", 0.9, 1.24),
]


def materials(mode: str) -> dict:
    """Рендер атласа: лист (цвет скана → осенний по цвету вершин, альфа), прут (тёмно-бурый)."""
    col_img = image("bl_c", SRC / "birch_leaves_color.png", False)
    op_img = image("bl_o", SRC / "birch_leaves_opacity.png", True)
    nor_img = image("bl_n", SRC / "birch_leaves_normal.png", True)
    mats = {}
    for key in ("leaf", "twig"):
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
        if key == "leaf":
            tc = nt.nodes.new("ShaderNodeTexImage")
            tc.image = col_img
            nt.links.new(uv.outputs[0], tc.inputs[0])
            # пожелтение: сдвиг тона к жёлтому, чуть ярче и насыщеннее
            hue = nt.nodes.new("ShaderNodeMath")
            hue.operation = "MULTIPLY_ADD"
            hue.inputs[1].default_value = -0.105
            hue.inputs[2].default_value = 0.5
            nt.links.new(sep.outputs[1], hue.inputs[0])
            hs = nt.nodes.new("ShaderNodeHueSaturation")
            nt.links.new(hue.outputs[0], hs.inputs["Hue"])
            sat = nt.nodes.new("ShaderNodeMath")
            sat.operation = "MULTIPLY_ADD"
            sat.inputs[1].default_value = 0.25
            sat.inputs[2].default_value = 0.95
            nt.links.new(sep.outputs[1], sat.inputs[0])
            nt.links.new(sat.outputs[0], hs.inputs["Saturation"])
            val = nt.nodes.new("ShaderNodeMath")
            val.operation = "MULTIPLY_ADD"
            val.inputs[1].default_value = 0.35
            val.inputs[2].default_value = 0.9
            nt.links.new(sep.outputs[1], val.inputs[0])
            vmul = nt.nodes.new("ShaderNodeMath")
            vmul.operation = "MULTIPLY"
            nt.links.new(val.outputs[0], vmul.inputs[0])
            nt.links.new(sep.outputs[0], vmul.inputs[1])
            nt.links.new(vmul.outputs[0], hs.inputs["Value"])
            nt.links.new(tc.outputs["Color"], hs.inputs["Color"])
            # бурые пятна
            nz = nt.nodes.new("ShaderNodeTexNoise")
            nz.inputs["Scale"].default_value = 40.0
            nt.links.new(uv.outputs[0], nz.inputs["Vector"])
            spot = nt.nodes.new("ShaderNodeMapRange")
            spot.inputs["From Min"].default_value = 0.55
            spot.inputs["From Max"].default_value = 0.62
            nt.links.new(nz.outputs["Fac"], spot.inputs["Value"])
            spm = nt.nodes.new("ShaderNodeMath")
            spm.operation = "MULTIPLY"
            nt.links.new(spot.outputs[0], spm.inputs[0])
            nt.links.new(sep.outputs[2], spm.inputs[1])
            brown = nt.nodes.new("ShaderNodeMix")
            brown.data_type = "RGBA"
            brown.inputs[7].default_value = (0.25, 0.14, 0.06, 1)
            nt.links.new(spm.outputs[0], brown.inputs[0])
            nt.links.new(hs.outputs[0], brown.inputs[6])
            color_out = brown.outputs[2]
            ta = nt.nodes.new("ShaderNodeTexImage")
            ta.image = op_img
            nt.links.new(uv.outputs[0], ta.inputs[0])
            alpha_out = ta.outputs["Color"]
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor_img
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            normal_out = nm.outputs[0]
        else:
            rgb = nt.nodes.new("ShaderNodeRGB")
            rgb.outputs[0].default_value = (0.055, 0.035, 0.03, 1)
            color_out = rgb.outputs[0]
            alpha_out = None
            normal_out = None
        if mode == "albedo":
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(color_out, em.inputs["Color"])
        elif mode == "normal":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            vt = nt.nodes.new("ShaderNodeVectorTransform")
            vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
            nt.links.new(normal_out if normal_out else geo.outputs["Normal"], vt.inputs[0])
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
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(ma.outputs[0], em.inputs["Color"])
        else:
            ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao.samples = 32
            ao.inputs["Distance"].default_value = 0.08
            em = nt.nodes.new("ShaderNodeEmission")
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


def render_atlas() -> None:
    RENDER.mkdir(parents=True, exist_ok=True)
    meta = {}
    for ci, (name, fn, view, L, width) in enumerate(CELLS):
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
        fn(m, random.Random(2000 + ci))
        height = width * CELL_H / CELL_W
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = width
        margin = 0.03 if view != "side_hang" else 0.05
        if view == "top":
            cam.location = (width / 2 - margin, 0, 3)
            cam.rotation_euler = (0, 0, 0)
            anchor = (margin / width, 0.5)
        elif view == "side":
            cam.location = (width / 2 - margin, -3, 0)
            cam.rotation_euler = (math.pi / 2, 0, 0)
            anchor = (margin / width, 0.5)
        else:
            cam.location = (width / 2 - margin, -3, -height / 2 + margin)
            cam.rotation_euler = (math.pi / 2, 0, 0)
            anchor = (margin / width, margin / height)
        cam.data.clip_start, cam.data.clip_end = 0.5, 6
        for mode in ("albedo", "normal", "ao"):
            mats = materials(mode)
            for o in [o for o in sc.objects if o.type == "MESH"]:
                bpy.data.objects.remove(o, do_unlink=True)
            m.build(name, mats)
            sc.cycles.samples = 96 if mode == "ao" else 32
            sc.render.filepath = str(RENDER / f"{name}_{mode}.png")
            bpy.ops.render.render(write_still=True)
            print("BIRCH render", name, mode, flush=True)
        meta[name] = dict(cell=ci, view=view, axis_len=L, width=width, height=round(height, 4), anchor=anchor)
    (RENDER / "cells.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ дерево

VARIANTS = {
    # stems: число стволов; lean — наклон стволов кустом, град; leafy — доля прядей с листьями
    "birch_a": dict(H=17.0, r0=0.2, stems=1, lean=3.0, crown_base=0.33, Lmax=4.2, leafy=0.55, seed=5),
    "birch_b": dict(H=16.0, r0=0.15, stems=2, lean=8.0, crown_base=0.36, Lmax=3.4, leafy=0.5, seed=9),
    "birch_c": dict(H=14.0, r0=0.12, stems=3, lean=13.0, crown_base=0.4, Lmax=3.0, leafy=0.45, seed=17),
    "birch_bare": dict(H=15.0, r0=0.17, stems=1, lean=5.0, crown_base=0.38, Lmax=3.6, leafy=0.12, seed=31),
    "birch_young": dict(H=7.5, r0=0.06, stems=1, lean=4.0, crown_base=0.25, Lmax=1.8, leafy=0.6, seed=43),
}
BARK_TILE_U, BARK_TILE_V = 1.0, 2.0


def stem(m: Mesh, rng: random.Random, base: Vector, lean_dir: Vector, lean: float, H: float, r0: float, crown_z: float) -> list:
    """Ствол: волнистый, с наклоном; UV — береста 1 × 2 м; r цвета вершин — затенение в кроне."""
    spine = []
    wob = [rng.uniform(0, 6.28) for _ in range(4)]
    tilt = math.radians(lean)
    z = -0.3
    while z < H:
        k = min(1.0, max(z, 0) / 3 + 0.25)
        off = lean_dir * (math.tan(tilt) * max(z, 0) * (1 - 0.25 * z / H))
        wav = Vector((0.12 * math.sin(z * 0.45 + wob[0]) + 0.05 * math.sin(z * 1.3 + wob[1]),
                      0.12 * math.sin(z * 0.38 + wob[2]) + 0.05 * math.sin(z * 1.1 + wob[3]), 0)) * k
        spine.append(base + off + wav + Vector((0, 0, z)))
        z += 0.15 if z < 1.2 else 0.4
    spine.append(spine[-1] + Vector((0, 0, H - spine[-1].z)))
    sides = 12 if r0 > 0.1 else 8
    p = m.part("trunk")
    b0 = len(p["v"])
    reps = max(1, round(2 * math.pi * r0 / BARK_TILE_U))
    for c in spine:
        h = max(c.z, 0.0)
        r = r0 * max(1 - h / H, 0.0) ** 0.8 + 0.006
        flare = max(0.0, 1 - max(c.z, -0.3) / 0.9)
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            rr = r * (1 + 0.35 * flare ** 2 * (0.6 + 0.4 * math.cos(4 * a + wob[0])))
            p["v"].append(c + Vector((math.cos(a), math.sin(a), 0)) * rr)
            p["col"].append((0.6 if c.z > crown_z else 0.92, (h / H) ** 2 * 0.2, wob[0] / 6.28, 1.0))
            p["nrm"].append(None)
    ring = sides + 1
    for i in range(len(spine) - 1):
        for k in range(sides):
            a0 = b0 + i * ring + k
            p["f"].append([a0, a0 + 1, a0 + ring + 1, a0 + ring])
            p["uv"].append([(reps * k / sides, spine[i].z / BARK_TILE_V), (reps * (k + 1) / sides, spine[i].z / BARK_TILE_V),
                            (reps * (k + 1) / sides, spine[i + 1].z / BARK_TILE_V), (reps * k / sides, spine[i + 1].z / BARK_TILE_V)])
    return spine


def along(spine: list, z: float) -> Vector:
    return sp.trunk_at(spine, z)


def arch(start: Vector, az: float, L: float, rel: float, rng: random.Random, segs: int = 7) -> list:
    """Ветвь берёзы: вверх под 40–60°, дугой к горизонтали и вниз у конца (повислые концы)."""
    e0 = math.radians(rng.uniform(40, 58) + 12 * rel)
    e1 = math.radians(-35 + 45 * rel + rng.uniform(-8, 8))
    horiz = Vector((math.cos(az), math.sin(az), 0))
    pts = [start]
    for i in range(1, segs + 1):
        t = (i - 0.5) / segs
        e = e0 + (e1 - e0) * t ** 1.4
        pts.append(pts[-1] + (horiz * math.cos(e) + Z * math.sin(e)) * (L / segs))
    return pts


def point_on(pts: list, s: float):
    seg = s * (len(pts) - 1)
    i = min(int(seg), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], seg - i), (pts[i + 1] - pts[i]).normalized()


def build_tree(v: dict) -> Mesh:
    rng = random.Random(v["seed"])
    m = Mesh()
    H, Lmax = v["H"], v["Lmax"]
    hb = H * v["crown_base"]
    stems = []
    az0 = rng.uniform(0, 6.28)
    for si in range(v["stems"]):
        a = az0 + 2 * math.pi * si / v["stems"]
        d = Vector((math.cos(a), math.sin(a), 0))
        Hs = H * (1.0 if si == 0 else rng.uniform(0.82, 0.95))
        base = d * (0.06 * (v["stems"] > 1))
        stems.append((stem(m, rng, base, d, v["lean"] * (1 if v["stems"] > 1 else rng.uniform(0.3, 1)), Hs,
                           v["r0"] * (1 if si == 0 else 0.85), hb), Hs, d))
    leafy = v["leafy"]

    def pick(kind: str) -> str:
        if kind == "hang":
            return rng.choice(["hang_a", "hang_b"]) if rng.random() < min(1.0, leafy * 1.5) else rng.choice(["bare_a", "bare_b"])
        return kind

    for spine, Hs, lean_d in stems:
        z = hb
        whorl = 0
        while z < Hs - 0.6:
            rel = (z - hb) / max(Hs - hb, 0.1)
            for _bi in range(rng.choice([1, 2, 2, 3]) if v["stems"] == 1 else rng.choice([1, 1, 2])):
                # яйцевидная крона: шире на трети высоты кроны
                prof = math.sin(math.pi * min(1.0, 0.18 + 0.82 * (1 - rel) ** 0.85)) ** 0.7
                az = rng.uniform(0, 6.28) if v["stems"] == 1 else math.atan2(lean_d.y, lean_d.x) + rng.uniform(-1.9, 1.9)
                L = max(0.5, Lmax * prof * rng.uniform(0.75, 1.1))
                root = along(spine, z)
                r_tr = v["r0"] * max(1 - z / Hs, 0) ** 0.8
                pts = arch(root + Vector((math.cos(az), math.sin(az), 0)) * r_tr * 0.7, az, L, rel, rng)
                rb = max(0.012, 0.045 * (L / Lmax) ** 1.1 * (v["r0"] / 0.2) ** 0.5)
                mat = "trunk" if rb > 0.03 else "branch"
                phase = rng.random()
                fk = 0.35 + 0.65 * L / Lmax
                m.tube(mat, pts, [rb * (1 - 0.8 * i / (len(pts) - 1)) for i in range(len(pts))], 6 if rb > 0.03 else 4,
                       (0.0, 1.0), 1.5, col_fn=lambda t, ph=phase, f=fk: (0.55 + 0.4 * t, t * f, ph, 1.0))
                # боковые ветви второго порядка — тоже дугой, короче
                subs = [(pts, 1.0)]
                for _ in range(rng.randint(3, 6)):
                    s = rng.uniform(0.2, 0.85)
                    p, tan = point_on(pts, s)
                    saz = math.atan2(tan.y, tan.x) + rng.choice([-1, 1]) * rng.uniform(0.5, 1.1)
                    sl = L * rng.uniform(0.3, 0.5)
                    spts = arch(p, saz, sl, rel, rng, 5)
                    m.tube("branch", spts, [rb * 0.45 * (1 - 0.8 * i / 5) for i in range(6)], 4, (0.0, 1.0), 1.5,
                           col_fn=lambda t, ph=phase, f=fk, s0=s: (0.6 + 0.35 * t, (s0 + t * 0.5) * f, ph, 1.0))
                    subs.append((spts, 0.6))
                # пряди и побеги по внешним 60 % ветвей
                for bpts, scale in subs:
                    total = sum((b - a).length for a, b in zip(bpts, bpts[1:]))
                    s = 0.22 if scale < 1 else 0.3
                    while s < 0.98:
                        p, tan = point_on(bpts, s)
                        hor = Vector((tan.x, tan.y, 0))
                        hor = hor.normalized() if hor.length > 1e-3 else Vector((math.cos(az), math.sin(az), 0))
                        out_n = (Vector((p.x - root.x, p.y - root.y, 0)).normalized() * 0.85 + Z * 0.35).normalized()
                        ao = (0.4 + 0.6 * s) * (0.75 + 0.25 * rel)
                        col = (ao, s * fk, phase, 1.0)
                        if rel > 0.78 and rng.random() < 0.6:
                            u = (tan + Z * 0.8).normalized()
                            sp.card(m, "upright", p, u, u.cross(Z).normalized() if abs(u.z) < 0.98 else X, scale * rng.uniform(0.7, 1.0),
                                    col, out_n, 0.6)
                        else:
                            vd = rolled(hor, -Z, math.radians(rng.uniform(-30, 30)))
                            if vd.z > 0:
                                vd = -vd
                            sp.card(m, pick("hang"), p + hor.cross(Z) * rng.uniform(-0.15, 0.15), hor, vd,
                                    scale * rng.uniform(0.75, 1.1) * (0.85 + 0.3 * (1 - rel)), col, out_n, 0.7)
                        s += 0.3 / max(total, 0.4) * rng.uniform(0.75, 1.2)
                    p, tan = point_on(bpts, 0.98)
                    if rng.random() < 0.7:
                        sp.card(m, "spray", p, tan, tan.cross(Z).normalized() if abs(tan.z) < 0.98 else X, scale * 0.8,
                                (0.9, fk, phase, 1.0), (Z * 0.7 + tan * 0.3).normalized(), 0.6)
            z += rng.uniform(0.28, 0.45) * (0.85 if rel < 0.5 else 1.0)
            whorl += 1
        # вершина: несколько вертикальных побегов
        top = spine[-1]
        for k in range(3):
            a = k * 2.1 + rng.uniform(-0.3, 0.3)
            side = Vector((math.cos(a), math.sin(a), 0))
            sp.card(m, "upright", top - Z * 1.1, (Z + side * 0.25).normalized(), side.cross(Z).normalized(), 1.1,
                    (1.0, 0.35, 0.5, 1.0), (side * 0.3 + Z * 0.7).normalized(), 0.5)
    return m


MAT_NAMES = {"needles": "BirchLeaves", "trunk": "BirchTrunk", "branch": "BirchBranch"}


def preview(name: str, ob, H: float) -> None:
    sc = bpy.context.scene
    alb = image("ba", TEX / "birch_atlas_albedo.png", False)
    nor = image("bn", TEX / "birch_atlas_normal.png", True)
    bark = image("bb", TEX / "birch_bark_albedo.png", False)
    for mt in ob.data.materials:
        mt.use_nodes = True
        nt = mt.node_tree
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        t = nt.nodes.new("ShaderNodeTexImage")
        nt.links.new(uv.outputs[0], t.inputs[0])
        if mt.name.startswith("BirchLeaves"):
            t.image = alb
            nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
            bsdf.inputs["Transmission Weight"].default_value = 0.15
        else:
            t.image = bark
            if mt.name.startswith("BirchBranch"):
                mul = nt.nodes.new("ShaderNodeMix")
                mul.data_type = "RGBA"
                mul.blend_type = "MULTIPLY"
                mul.inputs[0].default_value = 1.0
                mul.inputs[7].default_value = (0.35, 0.3, 0.28, 1)
                nt.links.new(t.outputs["Color"], mul.inputs[6])
                nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
            else:
                nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.62, 0.66, 0.72, 1)
    sc.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sc.collection.objects.link(sun)
    gme = bpy.data.meshes.new("g")
    gme.from_pydata([(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)], [], [[0, 1, 2, 3]])
    gm = bpy.data.materials.new("gm")
    gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.16, 0.13, 0.08, 1)
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
    print("BIRCH preview", name, flush=True)


def build_trees(do_preview: bool, only: list) -> None:
    sp.ATLAS.clear()
    sp.ATLAS.update(json.loads((TEX / "birch_atlas.json").read_text(encoding="utf-8")))
    path = OUT / "birch.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, v in VARIANTS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ob = build_tree(v).build(name, {k: bpy.data.materials.new(n) for k, n in MAT_NAMES.items()})
        n = sp.export_tree(name, ob)
        manifest[name] = dict(triangles=n, height=v["H"],
                              collisions=[dict(pos=[0, 2.0, 0], size=[round(v["r0"] * 2.2, 3), 4.0, round(v["r0"] * 2.2, 3)], yaw=0)])
        print("BIRCH tree", name, n, flush=True)
        if do_preview:
            preview(name, ob, v["H"])
        width = max(abs(c) for vtx in ob.data.vertices for c in (vtx.co.x, vtx.co.y))
        manifest[name]["far"] = sp.render_impostor(name, ob, v["H"], width, atlas="birch_atlas",
                                                   bark_path=TEX / "birch_bark_albedo.png", foliage_prefix="BirchLeaves")
        sp.far_mesh(name, manifest[name]["far"], "BirchFar")
    path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "atlas" in args:
        render_atlas()
    if "trees" in args:
        sp.RENDER = RENDER
        build_trees("preview" in args, [a for a in args if a.startswith("birch_")])
