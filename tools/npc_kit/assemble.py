"""NPC «мародёр»: сборка всех вещей на теле и материалы для просмотра в Blender.

Читает куртку (в её файле уже тело, скелет, брюки, берцы) и балаклаву, убирает тело под одеждой
(остаются кисти и кожа в прорези балаклавы), назначает материалы:
- кожа куртки — фото CC0 (Poly Haven brown_leather), темнее в заломах, потёрта на выпуклых складках;
- трикотаж (воротник, манжеты, пояс) — рубчик;
- брюки — свой камуфляж «чешуя» (крупные пятна + ячейки с тёмной каймой), саржа, пыль книзу, колени;
- берцы — кожа, сотовый рант, резина подошвы, металл, сетка языка, пыль;
- балаклава — трикотаж CC0 (jersey_melange) с ворсом;
- кожа рук — текстура ядра MakeHuman (CC0) с подповерхностным рассеянием.
Материалы узлами (Cycles/EEVEE); для игры потом — запекание в атласы на развёртках лекал.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/assemble.py [-- render]
→ _asset_src/npc_kit/npc_scav_v01.blend (+ снимки в previews/)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

TEX = kc.WORK / "tex"
MPFB_USER = Path(bpy.utils.resource_path("USER")) / "extensions" / ".user" / "blender_org" / "mpfb" / "data"
OUT = kc.WORK / "npc_scav_v01.blend"


# ---------- узлы ----------

def is_link(v) -> bool:
    """(узел, выход) — связь; кортеж чисел — цвет."""
    return isinstance(v, tuple) and len(v) == 2 and hasattr(v[0], "outputs")


class NodeBuilder:
    def __init__(self, mat: bpy.types.Material):
        mat.use_nodes = True
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.out = self.node("ShaderNodeOutputMaterial", 900, 0)
        self.bsdf = self.node("ShaderNodeBsdfPrincipled", 600, 0)
        self.link(self.bsdf, "BSDF", self.out, "Surface")
        self.x = -1200

    def node(self, kind: str, x: float = 0, y: float = 0) -> bpy.types.Node:
        n = self.nt.nodes.new(kind)
        n.location = (x, y)
        return n

    def link(self, a, a_out, b, b_in) -> None:
        # У узла смешивания три выхода «Result» (число, вектор, цвет) — цветной третий.
        if a.bl_idname == "ShaderNodeMix" and a_out == "Result":
            a_out = 2
        self.nt.links.new(a.outputs[a_out], b.inputs[b_in])

    def math(self, op: str, a=None, b=None, x=0, y=0) -> bpy.types.Node:
        n = self.node("ShaderNodeMath", x, y)
        n.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if is_link(v):
                self.link(v[0], v[1], n, k)
            else:
                n.inputs[k].default_value = v
        return n

    def mix(self, fac, a, b, blend: str = "MIX", x=0, y=0) -> bpy.types.Node:
        n = self.node("ShaderNodeMix", x, y)
        n.data_type = "RGBA"
        n.blend_type = blend
        for sock, v in ((0, fac), (6, a), (7, b)):
            if is_link(v):
                self.link(v[0], v[1], n, sock)
            elif sock == 0:
                n.inputs[0].default_value = v
            else:
                n.inputs[sock].default_value = (*v, 1.0) if len(v) == 3 else v
        return n

    def image(self, path: Path, non_color: bool, vector, box: bool = False, x=0, y=0) -> bpy.types.Node:
        n = self.node("ShaderNodeTexImage", x, y)
        n.image = bpy.data.images.load(str(path), check_existing=True)
        if non_color:
            n.image.colorspace_settings.name = "Non-Color"
        if box:
            n.projection = "BOX"
            n.projection_blend = 0.35
        self.link(vector[0], vector[1], n, "Vector")
        return n

    def ramp(self, src, stops: list[tuple[float, tuple]], interp: str = "LINEAR", x=0, y=0) -> bpy.types.Node:
        n = self.node("ShaderNodeValToRGB", x, y)
        cr = n.color_ramp
        cr.interpolation = interp
        while len(cr.elements) > len(stops):
            cr.elements.remove(cr.elements[-1])
        while len(cr.elements) < len(stops):
            cr.elements.new(0.5)
        for e, (pos, col) in zip(cr.elements, stops):
            e.position = pos
            e.color = (*col, 1.0) if len(col) == 3 else col
        self.link(src[0], src[1], n, "Fac")
        return n


def uv_metres(nb: NodeBuilder, uv_name: str, tile_m: float, rot: float = 0.0, x=-1100, y=0):
    """Координаты лекала (метры) → повтор текстуры с реальным размером плитки."""
    uv = nb.node("ShaderNodeUVMap", x, y)
    uv.uv_map = uv_name
    mp = nb.node("ShaderNodeMapping", x + 200, y)
    s = 1.0 / tile_m
    mp.inputs["Scale"].default_value = (s, s, s)
    mp.inputs["Rotation"].default_value = (0, 0, rot)
    nb.link(uv, "UV", mp, "Vector")
    return (mp, "Vector")


def obj_metres(nb: NodeBuilder, tile_m: float, x=-1100, y=0):
    tc = nb.node("ShaderNodeTexCoord", x, y)
    mp = nb.node("ShaderNodeMapping", x + 200, y)
    s = 1.0 / tile_m
    mp.inputs["Scale"].default_value = (s, s, s)
    nb.link(tc, "Object", mp, "Vector")
    return (mp, "Vector")


def pbr_set(nb: NodeBuilder, folder: str, stem: str, vec, box: bool = False, y: float = 0):
    d = TEX / folder
    files = {p.name: p for p in d.iterdir()}
    pick = lambda key: next(files[n] for n in files if key in n)
    col = nb.image(pick("_diff") if any("_diff" in n for n in files) else pick("_albedo"), False, vec, box, -700, y + 300)
    nor = nb.image(pick("_nor_gl"), True, vec, box, -700, y)
    rough = nb.image(pick("_rough"), True, vec, box, -700, y - 300)
    return col, nor, rough


def normal_map(nb: NodeBuilder, img, strength: float, x=200, y=-300) -> bpy.types.Node:
    n = nb.node("ShaderNodeNormalMap", x, y)
    n.inputs["Strength"].default_value = strength
    nb.link(img, "Color", n, "Color")
    return n


def ao(nb: NodeBuilder, dist: float, x=-400, y=600) -> bpy.types.Node:
    n = nb.node("ShaderNodeAmbientOcclusion", x, y)
    n.inputs["Distance"].default_value = dist
    n.samples = 8
    return n


def curvature(nb: NodeBuilder, lo: float, hi: float, x=-400, y=800):
    """Выпуклость складок (pointiness в Cycles): 0 — впадина, 1 — гребень."""
    g = nb.node("ShaderNodeNewGeometry", x - 200, y)
    r = nb.node("ShaderNodeMapRange", x, y)
    r.inputs["From Min"].default_value = lo
    r.inputs["From Max"].default_value = hi
    nb.link(g, "Pointiness", r, "Value")
    return r


def world_z_below(nb: NodeBuilder, z_top: float, z_bottom: float, x=-400, y=1000):
    """1 — у пола (пыль, грязь), 0 — выше z_top."""
    g = nb.node("ShaderNodeNewGeometry", x - 400, y)
    sep = nb.node("ShaderNodeSeparateXYZ", x - 200, y)
    nb.link(g, "Position", sep, "Vector")
    r = nb.node("ShaderNodeMapRange", x, y)
    r.inputs["From Min"].default_value = z_top
    r.inputs["From Max"].default_value = z_bottom
    nb.link(sep, "Z", r, "Value")
    return r


def noise(nb: NodeBuilder, vec, scale: float, detail: float = 4.0, rough: float = 0.55, x=-700, y=1200):
    n = nb.node("ShaderNodeTexNoise", x, y)
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = rough
    if vec:
        nb.link(vec[0], vec[1], n, "Vector")
    return n


# ---------- материалы ----------

def mat_leather_jacket(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    vec = uv_metres(nb, "UV_Pattern", 0.32)
    col, nor, rough = pbr_set(nb, "brown_leather", "brown_leather", vec)
    hs = nb.node("ShaderNodeHueSaturation", -400, 300)
    hs.inputs["Hue"].default_value = 0.49
    hs.inputs["Saturation"].default_value = 0.8
    hs.inputs["Value"].default_value = 0.30
    nb.link(col, "Color", hs, "Color")
    occ = ao(nb, 0.06)
    dark = nb.mix((occ, "AO"), (0.02, 0.012, 0.008), (hs, "Color"), x=-100, y=400)
    # Потёртости на гребнях складок и по крупным пятнам — светлее и матовее.
    cur = curvature(nb, 0.50, 0.56)
    blot = noise(nb, vec, 1.6, 6.0, 0.6, x=-700, y=1000)
    blot_r = nb.ramp((blot, "Fac"), [(0.45, (0, 0, 0)), (0.75, (1, 1, 1))], x=-400, y=1000)
    wear = nb.math("MULTIPLY", (cur, "Result"), (blot_r, "Color"), x=-150, y=900)
    wear_c = nb.math("MULTIPLY", (wear, 0), 0.8, x=0, y=900)
    worn = nb.mix((wear_c, 0), (dark, "Result"), (0.16, 0.115, 0.085), x=150, y=500)
    nb.link(worn, "Result", nb.bsdf, "Base Color")
    rr = nb.node("ShaderNodeMapRange", -350, -300)
    rr.inputs["To Min"].default_value = 0.30
    rr.inputs["To Max"].default_value = 0.62
    nb.link(rough, "Color", rr, "Value")
    r2 = nb.math("ADD", (rr, "Result"), (wear_c, 0), x=0, y=-300)
    nb.link(r2, 0, nb.bsdf, "Roughness")
    nb.link(normal_map(nb, nor, 0.9), "Normal", nb.bsdf, "Normal")
    nb.bsdf.inputs["Coat Weight"].default_value = 0.12
    nb.bsdf.inputs["Coat Roughness"].default_value = 0.35


def mat_rib(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    vec = uv_metres(nb, "UV_Pattern", 1.0)
    wave = nb.node("ShaderNodeTexWave", -600, 0)
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = 78.0          # рубчик ~4 мм
    wave.inputs["Distortion"].default_value = 0.4
    nb.link(vec[0], vec[1], wave, "Vector")
    fuzz = noise(nb, vec, 900.0, 2.0, 0.5, x=-600, y=-300)
    bump = nb.node("ShaderNodeBump", 200, -300)
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.0015
    h = nb.math("ADD", (wave, "Fac"), (fuzz, "Fac"), x=0, y=-200)
    nb.link(h, 0, bump, "Height")
    nb.link(bump, "Normal", nb.bsdf, "Normal")
    c = nb.ramp((wave, "Fac"), [(0.0, (0.008, 0.007, 0.006)), (1.0, (0.024, 0.021, 0.018))], x=0, y=200)
    nb.link(c, "Color", nb.bsdf, "Base Color")
    nb.bsdf.inputs["Roughness"].default_value = 0.92
    nb.bsdf.inputs["Sheen Weight"].default_value = 0.12


def mat_camo(mat: bpy.types.Material) -> None:
    """Свой камуфляж «чешуя»: крупные пятна четырёх тонов, поверх — ячейки с тёмной каймой."""
    nb = NodeBuilder(mat)
    vec = uv_metres(nb, "UV_Pattern", 1.0)
    big = noise(nb, vec, 3.2, 3.0, 0.5, x=-800, y=600)
    tones = nb.ramp((big, "Fac"), [(0.0, (0.27, 0.26, 0.19)), (0.42, (0.19, 0.19, 0.12)),
                                   (0.53, (0.11, 0.10, 0.075)), (0.62, (0.34, 0.32, 0.24))], "CONSTANT", x=-500, y=600)
    vor = nb.node("ShaderNodeTexVoronoi", -800, 200)
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 22.0
    vor.inputs["Randomness"].default_value = 0.85
    nb.link(vec[0], vec[1], vor, "Vector")
    edge = nb.ramp((vor, "Distance"), [(0.0, (1, 1, 1)), (0.06, (0, 0, 0))], x=-500, y=200)
    mask_n = noise(nb, vec, 5.5, 2.0, 0.5, x=-800, y=0)
    mask = nb.ramp((mask_n, "Fac"), [(0.45, (0, 0, 0)), (0.55, (1, 1, 1))], "CONSTANT", x=-500, y=0)
    lines = nb.math("MULTIPLY", (edge, "Color"), (mask, "Color"), x=-250, y=150)
    base = nb.mix((lines, 0), (tones, "Color"), (0.075, 0.07, 0.05), x=-50, y=500)
    # Плетение саржи (CC0 deniм, обесцвечено): светлые и тёмные нити.
    tw = uv_metres(nb, "UV_Pattern", 0.135, y=-700)
    col, nor, rough = pbr_set(nb, "denim_fabric_03", "denim_fabric_03", tw, y=-700)
    bw = nb.node("ShaderNodeRGBToBW", -400, -400)
    nb.link(col, "Color", bw, "Color")
    weave = nb.ramp((bw, "Val"), [(0.2, (0.78, 0.78, 0.78)), (0.8, (1.12, 1.12, 1.12))], x=-200, y=-400)
    woven = nb.mix(1.0, (base, "Result"), (weave, "Color"), "MULTIPLY", x=150, y=300)
    # Пыль книзу, грязь в заломах, потёртые гребни на коленях.
    occ = ao(nb, 0.05, x=-200, y=900)
    dusty = world_z_below(nb, 0.45, 0.24, x=-200, y=1100)
    dust_n = noise(nb, None, 18.0, 5.0, 0.6, x=-500, y=1300)
    dust = nb.math("MULTIPLY", (dusty, "Result"), (dust_n, "Fac"), x=0, y=1200)
    dust_w = nb.math("MULTIPLY", (dust, 0), 0.45, x=150, y=1200)
    dirty = nb.mix((occ, "AO"), (0.05, 0.045, 0.035), (woven, "Result"), x=350, y=600)
    final = nb.mix((dust_w, 0), (dirty, "Result"), (0.30, 0.26, 0.20), x=550, y=600)
    nb.link(final, "Result", nb.bsdf, "Base Color")
    rr = nb.node("ShaderNodeMapRange", -150, -700)
    rr.inputs["To Min"].default_value = 0.75
    rr.inputs["To Max"].default_value = 0.95
    nb.link(rough, "Color", rr, "Value")
    nb.link(rr, "Result", nb.bsdf, "Roughness")
    nb.link(normal_map(nb, nor, 0.8, x=300, y=-700), "Normal", nb.bsdf, "Normal")
    nb.bsdf.inputs["Sheen Weight"].default_value = 0.25


def mat_boot_leather(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    vec = obj_metres(nb, 0.16)
    col, nor, rough = pbr_set(nb, "brown_leather", "brown_leather", vec, box=True)
    hs = nb.node("ShaderNodeHueSaturation", -400, 300)
    hs.inputs["Hue"].default_value = 0.5
    hs.inputs["Saturation"].default_value = 0.8
    hs.inputs["Value"].default_value = 0.55
    nb.link(col, "Color", hs, "Color")
    occ = ao(nb, 0.02)
    dark = nb.mix((occ, "AO"), (0.02, 0.013, 0.008), (hs, "Color"), x=-100, y=400)
    dusty = world_z_below(nb, 0.10, 0.0)
    dn = noise(nb, None, 60.0, 6.0, 0.65, x=-600, y=1300)
    dust = nb.math("MULTIPLY", (dusty, "Result"), (dn, "Fac"), x=0, y=1100)
    dust2 = nb.math("MULTIPLY", (dust, 0), 0.14, x=150, y=1100)
    fin = nb.mix((dust2, 0), (dark, "Result"), (0.24, 0.20, 0.15), x=250, y=500)
    nb.link(fin, "Result", nb.bsdf, "Base Color")
    rr = nb.node("ShaderNodeMapRange", -350, -300)
    rr.inputs["To Min"].default_value = 0.35
    rr.inputs["To Max"].default_value = 0.7
    nb.link(rough, "Color", rr, "Value")
    nb.link(rr, "Result", nb.bsdf, "Roughness")
    nb.link(normal_map(nb, nor, 1.0), "Normal", nb.bsdf, "Normal")


def mat_rubber(mat: bpy.types.Material, honeycomb: bool) -> None:
    nb = NodeBuilder(mat)
    vec = obj_metres(nb, 1.0)
    base = (0.028, 0.027, 0.026)
    if honeycomb:
        vor = nb.node("ShaderNodeTexVoronoi", -600, -200)
        vor.feature = "DISTANCE_TO_EDGE"
        vor.inputs["Scale"].default_value = 260.0
        vor.inputs["Randomness"].default_value = 0.05
        nb.link(vec[0], vec[1], vor, "Vector")
        bump = nb.node("ShaderNodeBump", 200, -300)
        bump.inputs["Strength"].default_value = 0.8
        bump.inputs["Distance"].default_value = 0.0008
        nb.link(vor, "Distance", bump, "Height")
        nb.link(bump, "Normal", nb.bsdf, "Normal")
    dusty = world_z_below(nb, 0.05, -0.03)
    dn = noise(nb, None, 80.0, 6.0, 0.65, x=-600, y=1300)
    dust = nb.math("MULTIPLY", (dusty, "Result"), (dn, "Fac"), x=0, y=1100)
    dust_w = nb.math("MULTIPLY", (dust, 0), 0.18, x=150, y=1100)
    fin = nb.mix((dust_w, 0), base, (0.20, 0.17, 0.13), x=250, y=500)
    nb.link(fin, "Result", nb.bsdf, "Base Color")
    nb.bsdf.inputs["Roughness"].default_value = 0.78


def mat_simple(mat: bpy.types.Material, color, rough: float, metal: float = 0.0, bump_scale: float = 0.0,
               grid: bool = False) -> None:
    nb = NodeBuilder(mat)
    nb.bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    nb.bsdf.inputs["Roughness"].default_value = rough
    nb.bsdf.inputs["Metallic"].default_value = metal
    if bump_scale or grid:
        vec = obj_metres(nb, 1.0)
        if grid:
            wx = nb.node("ShaderNodeTexWave", -600, 0)
            wx.bands_direction = "X"
            wx.inputs["Scale"].default_value = 200.0
            wy = nb.node("ShaderNodeTexWave", -600, -250)
            wy.bands_direction = "Z"
            wy.inputs["Scale"].default_value = 200.0
            for w in (wx, wy):
                nb.link(vec[0], vec[1], w, "Vector")
            h = nb.math("MULTIPLY", (wx, "Fac"), (wy, "Fac"), x=-300, y=-100)
        else:
            nz = noise(nb, vec, bump_scale, 3.0, 0.5, x=-600, y=0)
            h = (nz, "Fac")
        bump = nb.node("ShaderNodeBump", 200, -300)
        bump.inputs["Strength"].default_value = 0.5
        nb.link(h[0] if isinstance(h, tuple) else h, h[1] if isinstance(h, tuple) else 0, bump, "Height")
        nb.link(bump, "Normal", nb.bsdf, "Normal")


def mat_knit(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    vec = obj_metres(nb, 0.09)
    col, nor, rough = pbr_set(nb, "jersey_melange", "jersey_melange", vec, box=True)
    bw = nb.node("ShaderNodeRGBToBW", -400, 300)
    nb.link(col, "Color", bw, "Color")
    c = nb.ramp((bw, "Val"), [(0.2, (0.006, 0.0065, 0.005)), (0.8, (0.024, 0.026, 0.020))], x=-150, y=300)
    occ = ao(nb, 0.03)
    dark = nb.mix((occ, "AO"), (0.005, 0.005, 0.004), (c, "Color"), x=150, y=400)
    nb.link(dark, "Result", nb.bsdf, "Base Color")
    nb.bsdf.inputs["Roughness"].default_value = 0.95
    nb.bsdf.inputs["Sheen Weight"].default_value = 0.35
    nb.bsdf.inputs["Sheen Roughness"].default_value = 0.4
    nb.link(normal_map(nb, nor, 1.4), "Normal", nb.bsdf, "Normal")


def mat_skin(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    uv = nb.node("ShaderNodeUVMap", -1100, 0)
    diff = MPFB_USER / "skins" / "middleage_caucasian_male" / "middleage_lightskinned_male_diffuse.png"
    img = nb.node("ShaderNodeTexImage", -700, 300)
    if diff.exists():
        img.image = bpy.data.images.load(str(diff), check_existing=True)
        nb.link(uv, "UV", img, "Vector")
        nb.link(img, "Color", nb.bsdf, "Base Color")
    else:
        nb.bsdf.inputs["Base Color"].default_value = (0.62, 0.45, 0.37, 1)
    nb.bsdf.inputs["Subsurface Weight"].default_value = 0.25
    nb.bsdf.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    nb.bsdf.inputs["Subsurface Scale"].default_value = 0.006
    nb.bsdf.inputs["Roughness"].default_value = 0.5
    tc = nb.node("ShaderNodeTexCoord", -1100, -400)
    pores = nb.node("ShaderNodeTexNoise", -700, -400)
    pores.inputs["Scale"].default_value = 900.0
    pores.inputs["Detail"].default_value = 2.0
    nb.link(tc, "Object", pores, "Vector")
    bump = nb.node("ShaderNodeBump", 200, -400)
    bump.inputs["Strength"].default_value = 0.15
    nb.link(pores, "Fac", bump, "Height")
    nb.link(bump, "Normal", nb.bsdf, "Normal")


def mat_eye(mat: bpy.types.Material) -> None:
    nb = NodeBuilder(mat)
    uv = nb.node("ShaderNodeUVMap", -1100, 0)
    img = nb.node("ShaderNodeTexImage", -700, 300)
    p = MPFB_USER / "eyes" / "materials" / "brownlight_eye.png"
    img.image = bpy.data.images.load(str(p), check_existing=True)
    nb.link(uv, "UV", img, "Vector")
    hs = nb.node("ShaderNodeHueSaturation", -400, 300)
    hs.inputs["Saturation"].default_value = 0.55
    hs.inputs["Value"].default_value = 0.9
    nb.link(img, "Color", hs, "Color")
    nb.link(hs, "Color", nb.bsdf, "Base Color")
    nb.bsdf.inputs["Roughness"].default_value = 0.25
    nb.bsdf.inputs["Coat Weight"].default_value = 1.0
    nb.bsdf.inputs["Coat Roughness"].default_value = 0.03


# ---------- молния ----------

def add_zipper(jacket: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    """Молния по центру переда: линия застёжки — вершины куртки у x = 0 спереди, по высоте через 1 см;
    тесьма 2,2 см, зубцы через 3 мм (вперемешку слева и справа), бегунок с язычком у ворота."""
    from mathutils.bvhtree import BVHTree
    me = jacket.data
    pts = [v.co.copy() for v in me.vertices if abs(v.co.x) < 0.005 and v.co.y < -0.04 and 0.90 < v.co.z < 1.52]
    if len(pts) < 10:
        return None
    bins: dict[int, list[Vector]] = {}
    for p in pts:
        bins.setdefault(int(p.z / 0.01), []).append(p)
    line = []
    for k in sorted(bins):
        front = min(bins[k], key=lambda q: q.y)
        line.append(Vector((0.0, front.y, front.z)))
    for _ in range(4):
        line = [line[0]] + [(line[i - 1] + line[i] * 2 + line[i + 1]) / 4 for i in range(1, len(line) - 1)] + [line[-1]]
    bvh = BVHTree.FromObject(jacket, bpy.context.evaluated_depsgraph_get())
    # Равномерно через 3 мм.
    cum = [0.0]
    for a, b in zip(line, line[1:]):
        cum.append(cum[-1] + (b - a).length)
    step = 0.003
    samples = []
    t = 0.0
    j = 0
    while t < cum[-1]:
        while cum[j + 1] < t:
            j += 1
        f = (t - cum[j]) / max(cum[j + 1] - cum[j], 1e-9)
        samples.append(line[j].lerp(line[j + 1], f))
        t += step
    bm = bmesh.new()
    tape_rows = []
    for k, p in enumerate(samples):
        tan = (samples[min(k + 1, len(samples) - 1)] - samples[max(k - 1, 0)]).normalized()
        hit = bvh.find_nearest(p)
        nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
        if nrm.y > 0:
            nrm = -nrm
        side = tan.cross(nrm).normalized()
        base = (hit[0] if hit[0] is not None else p) + nrm * 0.0012
        row = []
        for o in (-0.011, -0.004, 0.004, 0.011):
            # Каждую точку тесьмы — на поверхность кожи (складки не прячут тесьму).
            q = base + side * o
            h2 = bvh.find_nearest(q)
            if h2[0] is not None:
                n2 = h2[1] if h2[1].dot(nrm) > 0 else -h2[1]
                q = h2[0] + n2 * 0.0014
            row.append(bm.verts.new(q))
        tape_rows.append(row)
        base = (row[1].co + row[2].co) / 2
        # Зуб: брусок 3,6 × 2,2 × 1,6 мм, через один — с левой и правой ленты (сцепление).
        sgn = 1 if k % 2 else -1
        c = base + side * (0.0012 * sgn) + nrm * 0.0016
        hx, hy, hz = side * 0.0018, tan * 0.0011, nrm * 0.0008
        vs = [bm.verts.new(c + a * hx + b * hy + d * hz) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
    for r0, r1 in zip(tape_rows, tape_rows[1:]):
        for i in range(3):
            bm.faces.new((r0[i], r0[i + 1], r1[i + 1], r1[i]))
    # Бегунок и язычок у верхнего конца.
    top = samples[-4]
    tan = (samples[-1] - samples[-6]).normalized()
    hit = bvh.find_nearest(top)
    nrm = hit[1] if hit[0] is not None else Vector((0, -1, 0))
    if nrm.y > 0:
        nrm = -nrm
    side = tan.cross(nrm).normalized()
    for (c, hs, ht, hn) in ((top + nrm * 0.0035, 0.0065, 0.011, 0.0028),
                            (top + nrm * 0.0055 - tan * 0.022, 0.0045, 0.013, 0.0008)):
        vs = [bm.verts.new(c + side * (a * hs) + tan * (b * ht) + nrm * (d * hn)) for a in (-1, 1) for b in (-1, 1) for d in (-1, 1)]
        for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in f])
    mesh = bpy.data.meshes.new("Jacket_Zipper")
    bm.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Jacket_Zipper", mesh)
    col.objects.link(obj)
    tape = bpy.data.materials.new("Zipper_Tape")
    mat_simple(tape, (0.02, 0.018, 0.016), 0.8, bump_scale=3000.0)
    metal = bpy.data.materials.new("Zipper_Metal")
    mat_simple(metal, (0.30, 0.27, 0.22), 0.38, metal=1.0)
    mesh.materials.append(tape)
    mesh.materials.append(metal)
    # Порядок граней — как создавали: зубцы (6 на точку), тесьма, бегунок с язычком.
    t0 = 6 * len(samples)
    t1 = t0 + 3 * (len(tape_rows) - 1)
    for poly in mesh.polygons:
        poly.material_index = 0 if t0 <= poly.index < t1 else 1
    return obj


# ---------- сборка ----------

def hide_covered_body(body: bpy.types.Object) -> None:
    """Под одеждой тело не рисуется: остаются кисти (с запасом под манжетой) и голова с шеей
    (под балаклавой; кожа видна в прорези)."""
    groups = {vg.index: vg.name for vg in body.vertex_groups}
    hand_bones = ("hand", "thumb", "index", "middle", "ring", "pinky")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    dl = bm.verts.layers.deform.active
    keep_v = set()
    for v in bm.verts:
        w = sum(wt for gi, wt in v[dl].items() if groups.get(gi, "").startswith(hand_bones))
        if w > 0.05 or v.co.z > 1.50:
            keep_v.add(v)
    kill = [f for f in bm.faces if not all(v in keep_v for v in f.verts)]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "jacket" / "jacket_sim.blend"))
    for name in ("96_Jacket_Work", "97_Snapshots", "98_Sim_Colliders"):
        col = bpy.data.collections.get(name)
        if col:
            for o in list(col.objects):
                bpy.data.objects.remove(o)
            bpy.data.collections.remove(col)
    with bpy.data.libraries.load(str(kc.WORK / "balaclava" / "balaclava.blend")) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("Balaclava")]
    bcol = kc.collection("05_Balaclava")
    for o in dst.objects:
        bcol.objects.link(o)
    body = bpy.data.objects["NPC_Body"]
    hide_covered_body(body)
    zip_obj = add_zipper(bpy.data.objects["Jacket"], bpy.data.collections["03_Jacket"])
    kc.log("NPC_ZIPPER", len(zip_obj.data.polygons) if zip_obj else 0, "граней")
    for n in ("NPC_Eyebrows",):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = True            # под балаклавой брови не видны
            o.hide_set(True)
    mats = bpy.data.materials
    mat_leather_jacket(mats["Jacket_Leather"])
    mat_rib(mats["Jacket_Rib"])
    mat_camo(mats["Pants_Fabric"])
    mat_boot_leather(mats["Boot_Leather"])
    mat_rubber(mats["Boot_Rubber"], True)
    mat_rubber(mats["Boot_Sole"], False)
    mat_simple(mats["Boot_Lace"], (0.045, 0.032, 0.022), 0.85, bump_scale=2000.0)
    mat_simple(mats["Boot_Metal"], (0.20, 0.20, 0.21), 0.42, metal=1.0)
    mat_simple(mats["Boot_Mesh"], (0.05, 0.038, 0.028), 0.9, grid=True)
    mat_knit(mats["Balaclava_Knit"])
    skin = mats.new("NPC_Skin")
    mat_skin(skin)
    body.data.materials.clear()
    body.data.materials.append(skin)
    eyes = bpy.data.objects["NPC_Eyes"]
    eye = mats.new("NPC_Eye")
    mat_eye(eye)
    eyes.data.materials.clear()
    eyes.data.materials.append(eye)
    for o in bpy.data.objects:
        if o.type == "MESH" and o.name not in ("Studio_Floor",):
            for p in o.data.polygons:
                p.use_smooth = True
    kc.studio()
    kc.save(OUT)
    kc.log("NPC_ASSEMBLED", str(OUT))
    if "render" in args:
        cams = kc.view_cameras(1.8)
        cams["head"] = kc.camera("Cam_Head", (0.32, -0.95, 1.70), (0, -0.04, 1.62), 85)
        cams["boots"] = kc.camera("Cam_Boots", (0.75, -0.9, 0.35), (0.0, -0.05, 0.18), 70)
        cams["torso"] = kc.camera("Cam_Torso", (0.7, -1.4, 1.35), (0.0, 0.0, 1.22), 75)
        for view, size in (("front", (900, 1300)), ("three_quarter", (900, 1300)), ("back", (900, 1300)),
                           ("head", (900, 900)), ("torso", (1000, 900)), ("boots", (1000, 800))):
            kc.render(cams[view], kc.WORK / "previews" / f"scav_v01_{view}.png", size, 128)


if __name__ == "__main__":
    main()
