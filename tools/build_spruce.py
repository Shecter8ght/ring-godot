"""Обыкновенная ель (Picea abies) для зоны 1, bpy. Два этапа:

  atlas — из отсканированных веточек Poly Haven (fir_tree_01, CC0; _asset_src/spruce/) собираются
          настоящие лапы в 3D и рендерятся (Cycles) в ячейки атласа: цвет, нормаль (в пространстве
          камеры = касательном карточки), затенение между слоями. Склейка — tools/build_spruce_atlas.py.
  trees — ель по референсам (референсы владельца 2026-10-08): мутовки, ветка отходит от ствола,
          провисает и загибает кончик вверх, под ветками висят «шторки»; ствол с корневыми наплывами,
          у лесной ели снизу сухие сучья, у вершины шишки. Карточки атласа на ветках, нормали кроны
          «наружу», в цветах вершин — затенение, гибкость для ветра, фаза. → assets/zone01/models/spruce_*.glb

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_spruce.py -- atlas
python tools/build_spruce_atlas.py
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_spruce.py -- trees [preview]
"""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/spruce"
RENDER = SRC / "render"
OUT = ROOT / "assets/zone01/models"
TEX = ROOT / "assets/zone01/textures"
TWIGS = json.loads((SRC / "twigs.json").read_text(encoding="utf-8"))
ATLAS_PX = 4096
CELL_W, CELL_H = 2048, 1365

X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


# ------------------------------------------------------------------ накопитель геометрии

class Mesh:
    def __init__(self) -> None:
        self.parts: dict[str, dict] = {}

    def part(self, mat: str) -> dict:
        if mat not in self.parts:
            self.parts[mat] = dict(v=[], f=[], uv=[], col=[], nrm=[])
        return self.parts[mat]

    def quad(self, mat: str, corners, uvs, col=(1, 1, 1, 1), nrm=None) -> None:
        p = self.part(mat)
        i = len(p["v"])
        p["v"].extend(corners)
        p["f"].append([i, i + 1, i + 2, i + 3])
        p["uv"].append(list(uvs))
        p["col"].extend([col] * 4)
        p["nrm"].extend(nrm if nrm else [None] * 4)

    def tube(self, mat: str, pts: list, radii: list, sides: int, uv_u: tuple, v_scale: float, col_fn=None, caps=False) -> None:
        """Труба по ломаной: кольца со своим радиусом, UV — u по окружности в [u0,u1], v вдоль длины."""
        p = self.part(mat)
        base = len(p["v"])
        n = len(pts)
        frames = []
        prev_side = None
        for i in range(n):
            d = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
            ref = prev_side if prev_side is not None else (Z if abs(d.z) < 0.9 else X)
            side = (ref - d * ref.dot(d)).normalized()
            prev_side = side
            frames.append((d, side, d.cross(side)))
        along = 0.0
        for i in range(n):
            if i:
                along += (pts[i] - pts[i - 1]).length
            d, s, b = frames[i]
            for k in range(sides + 1):
                a = 2 * math.pi * k / sides
                p["v"].append(pts[i] + (s * math.cos(a) + b * math.sin(a)) * radii[i])
                p["col"].append(col_fn(i / max(n - 1, 1)) if col_fn else (1, 1, 1, 1))
                p["nrm"].append(None)
            p.setdefault("tube_uv", []).append(None)
        ring = sides + 1
        lengths = [0.0]
        for i in range(1, n):
            lengths.append(lengths[-1] + (pts[i] - pts[i - 1]).length)
        for i in range(n - 1):
            for k in range(sides):
                a0 = base + i * ring + k
                f = [a0, a0 + 1, a0 + ring + 1, a0 + ring]
                p["f"].append(f)
                u0, u1 = uv_u
                p["uv"].append([(u0 + (u1 - u0) * k / sides, lengths[i] * v_scale), (u0 + (u1 - u0) * (k + 1) / sides, lengths[i] * v_scale),
                                (u0 + (u1 - u0) * (k + 1) / sides, lengths[i + 1] * v_scale), (u0 + (u1 - u0) * k / sides, lengths[i + 1] * v_scale)])

    def build(self, name: str, materials: dict) -> bpy.types.Object:
        verts, faces, uvs, cols, mats, nrms = [], [], [], [], [], []
        order = sorted(self.parts)
        for mi, key in enumerate(order):
            p = self.parts[key]
            b = len(verts)
            verts.extend(p["v"])
            faces.extend([[b + i for i in f] for f in p["f"]])
            uvs.extend(p["uv"])
            cols.extend(p["col"])
            nrms.extend(p["nrm"])
            mats.extend([mi] * len(p["f"]))
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in verts], [], faces)
        uvl = me.uv_layers.new(name="UVMap")
        for poly, puv in zip(me.polygons, uvs):
            for k in range(poly.loop_total):
                uvl.data[poly.loop_start + k].uv = puv[k]
        ca = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        for i, c in enumerate(cols):
            ca.data[i].color = c
        for key in order:
            me.materials.append(materials[key])
        for poly, mi in zip(me.polygons, mats):
            poly.material_index = mi
            poly.use_smooth = True
        me.validate()
        me.update()
        if any(n is not None for n in nrms):
            loop_n = []
            for loop in me.loops:
                n = nrms[loop.vertex_index]
                loop_n.append(tuple(n) if n is not None else tuple(me.vertices[loop.vertex_index].normal))
            me.normals_split_custom_set(loop_n)
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


# ------------------------------------------------------------------ карточка веточки

def twig_card(m: Mesh, mat: str, key: str, base: Vector, d: Vector, side: Vector, length: float, col=(1, 1, 1, 1),
              uv_rect=None, sprite=None) -> None:
    """Веточка из скана: основание черенка — в base, растёт вдоль d на length м, плоскость — d×side."""
    t = TWIGS["twigs"][key] if sprite is None else sprite
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
        a, c = rel.dot(up) * k, rel.dot(right) * k
        corners.append(base + d * a + side * c)
        uvs.append((cx / size, 1.0 - cy / size))
    m.quad(mat, corners, uvs, col)


def rolled(d: Vector, side: Vector, roll: float) -> Vector:
    return (side * math.cos(roll) + d.cross(side) * math.sin(roll)).normalized()


# ------------------------------------------------------------------ лапы для атласа (локально, ось вдоль +X)

BIG = ["t6", "t7", "t1", "t3"]
SMALL = ["t2", "t4", "t5"]


def axis_curve(L: float, rng: random.Random, droop: float = 0.0) -> list:
    pts = []
    w = rng.uniform(0, 6)
    for i in range(13):
        s = L * i / 12
        pts.append(Vector((s, 0.012 * math.sin(s * 7 + w), -droop * (s / L) ** 2)))
    return pts


def at(pts: list, s: float) -> Vector:
    seg = s / (pts[-1] - pts[0]).length * (len(pts) - 1)
    i = min(int(seg), len(pts) - 2)
    return pts[i].lerp(pts[i + 1], seg - i)


def spray(m: Mesh, rng: random.Random, L: float, density: float = 1.0) -> None:
    """Плоская лапа: ось, боковые побеги ёлочкой (длиннее у основания), мелкие побеги сверху и снизу, лидер."""
    pts = axis_curve(L, rng)
    m.tube("stick", pts, [0.008 - 0.006 * i / 12 for i in range(13)], 6, (60 / 4096, 780 / 4096), 2.0)
    s = 0.04
    side = 1
    while s < L * 0.93:
        b = at(pts, s) + Vector((0, 0, rng.uniform(-0.006, 0.006)))
        ang = math.radians(rng.uniform(44, 62))
        d = Vector((math.cos(ang), side * math.sin(ang), rng.uniform(-0.12, 0.12))).normalized()
        frac = s / L
        length = 0.4 * math.sqrt(L) * (1.0 - 0.6 * frac ** 1.2) * rng.uniform(0.78, 1.1)
        key = rng.choice(BIG if length > 0.16 else ["t1", "t3", "t5"])
        sd = rolled(d, Z.cross(d).normalized(), math.radians(rng.uniform(-22, 22)))
        tone = 0.7 + 0.3 * frac + rng.uniform(-0.07, 0.07)
        twig_card(m, "twig", key, b, d, sd, length, (tone, tone, tone, 1))
        side = -side
        s += rng.uniform(0.032, 0.05) / density
    for _ in range(int(26 * L * density)):
        s = rng.uniform(0.05, 0.9) * L
        z = rng.choice([-1, 1]) * rng.uniform(0.006, 0.02)
        ang = math.radians(rng.uniform(-70, 70))
        d = Vector((math.cos(ang), math.sin(ang), rng.uniform(-0.2, 0.2))).normalized()
        sd = rolled(d, Z.cross(d).normalized(), math.radians(rng.uniform(-40, 40)))
        tone = (0.62 if z < 0 else 0.92) + rng.uniform(-0.06, 0.06)
        twig_card(m, "twig", rng.choice(SMALL), at(pts, s) + Vector((0, 0, z)), d, sd, rng.uniform(0.07, 0.15), (tone, tone, tone, 1))
    tip = at(pts, L * 0.97)
    twig_card(m, "twig", rng.choice(["t1", "t3"]), tip, X, Y, 0.2 * math.sqrt(L), (1.05, 1.05, 1.05, 1))


def curtain(m: Mesh, rng: random.Random, L: float, hang: float) -> None:
    """«Шторка» (вид сбоку): ось вдоль +X, с неё свисают побеги в 2 звена, глубина слоями по Y."""
    pts = axis_curve(L, rng)
    m.tube("stick", pts, [0.009 - 0.006 * i / 12 for i in range(13)], 6, (60 / 4096, 780 / 4096), 2.0)
    s = 0.06
    while s < L * 0.96:
        top = at(pts, s) + Vector((0, rng.uniform(-0.05, 0.05), 0))
        h = hang * (1.0 - 0.35 * s / L) * rng.uniform(0.55, 1.15)
        d = Vector((rng.uniform(0.04, 0.35), rng.uniform(-0.1, 0.1), -1)).normalized()
        sd = rolled(d, (d.cross(Y)).normalized(), math.radians(rng.uniform(-35, 35)))
        tone = 0.72 + rng.uniform(-0.06, 0.06)
        twig_card(m, "twig", rng.choice(BIG), top, d, sd, h * 0.55, (tone, tone, tone, 1))
        mid = top + d * h * 0.5
        d2 = Vector((rng.uniform(0.0, 0.25), rng.uniform(-0.1, 0.1), -1)).normalized()
        sd2 = rolled(d2, (d2.cross(Y)).normalized(), math.radians(rng.uniform(-35, 35)))
        tone2 = 0.88 + rng.uniform(-0.06, 0.08)
        twig_card(m, "twig", rng.choice(BIG + ["t5"]), mid, d2, sd2, h * 0.5, (tone2, tone2, tone2, 1))
        s += rng.uniform(0.028, 0.045)
    # полоса лапы сверху: побеги вдоль оси, повёрнутые к камере
    for _ in range(int(30 * L)):
        s = rng.uniform(0.02, 0.95) * L
        ang = math.radians(rng.uniform(-60, 60))
        d = Vector((math.cos(ang), 0, math.sin(ang) * 0.4)).normalized()
        sd = rolled(d, (d.cross(Y)).normalized(), math.radians(rng.uniform(-30, 30)))
        twig_card(m, "twig", rng.choice(SMALL + ["t1"]), at(pts, s) + Vector((0, rng.uniform(-0.04, 0.04), 0)), d, sd,
                  rng.uniform(0.08, 0.17), (0.8, 0.8, 0.8, 1))


def leader(m: Mesh, rng: random.Random, L: float) -> None:
    """Верхушка (вид сбоку, ствол вдоль +X): лидер и две мутовки побегов вокруг оси."""
    pts = axis_curve(L, rng)
    m.tube("stick", pts, [0.012 - 0.009 * i / 12 for i in range(13)], 6, (60 / 4096, 780 / 4096), 2.0)
    for wx, n, ln in [(0.22, 6, 0.36), (0.55, 5, 0.26), (0.8, 4, 0.14)]:
        for k in range(n):
            az = 2 * math.pi * k / n + rng.uniform(-0.3, 0.3)
            radial = Vector((0, math.cos(az), math.sin(az)))
            ang = math.radians(rng.uniform(42, 60))
            d = (X * math.cos(ang) + radial * math.sin(ang)).normalized()
            sd = rolled(d, d.cross(-Y).normalized() if abs(d.dot(Y)) < 0.95 else Z, math.radians(rng.uniform(-30, 30)))
            tone = 0.85 + rng.uniform(-0.08, 0.08)
            twig_card(m, "twig", rng.choice(BIG), at(pts, L * wx), d, sd, ln * rng.uniform(0.85, 1.1), (tone, tone, tone, 1))
    for _ in range(int(24 * L)):
        s = rng.uniform(0.05, 0.9) * L
        az = rng.uniform(0, 2 * math.pi)
        d = (X * 0.7 + Vector((0, math.cos(az), math.sin(az))) * 0.7).normalized()
        sd = d.cross(-Y).normalized()
        twig_card(m, "twig", rng.choice(SMALL), at(pts, s), d, sd, rng.uniform(0.06, 0.12), (0.95, 0.95, 0.95, 1))
    twig_card(m, "twig", "t2", at(pts, L * 0.94), X, Z, 0.22, (1.1, 1.1, 1.1, 1))


def dead(m: Mesh, rng: random.Random, L: float) -> None:
    """Сухой сук (вид сверху): голые ветвящиеся прутья, кое-где обломки."""
    def branch(p0: Vector, d: Vector, length: float, r: float, depth: int) -> None:
        pts = [p0]
        dd = d.copy()
        for i in range(6):
            dd = (dd + Vector((rng.uniform(-0.15, 0.15), rng.uniform(-0.15, 0.15), 0))).normalized()
            pts.append(pts[-1] + dd * length / 6)
        m.tube("deadwood", pts, [r * (1 - 0.7 * i / 6) for i in range(7)], 5, (0.0, 1.0), 3.0)
        if depth >= 2:
            return
        for k in range(rng.randint(4, 8) - depth * 2):
            t = rng.uniform(0.15, 0.85)
            base = pts[int(t * 6)]
            ang = math.radians(rng.uniform(35, 65)) * rng.choice([-1, 1])
            nd = Vector((dd.x * math.cos(ang) - dd.y * math.sin(ang), dd.x * math.sin(ang) + dd.y * math.cos(ang), 0))
            branch(base, nd, length * rng.uniform(0.25, 0.45), r * 0.45, depth + 1)
    branch(Vector((0, 0, 0)), X, L, 0.014, 0)


# ------------------------------------------------------------------ материалы рендера атласа

def image(name: str, path: Path, non_color: bool):
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    return img


def atlas_materials(mode: str) -> dict:
    mats = {}
    diff = image("diff", SRC / "twig_diff_4k.png", False)
    alpha = image("alpha", SRC / "twig_alpha_4k.png", True)
    nor = image("nor", SRC / "twig_nor_gl_4k.png", True)
    aoi = image("ao", SRC / "twig_ao_4k.png", True)
    bark = image("bark", ROOT / "_asset_src/pine_forest/fir_tree_01/textures/fir_tree_01_bark_diff_2k.jpg", False)
    for key in ("twig", "stick", "deadwood"):
        mt = bpy.data.materials.get(key) or bpy.data.materials.new(key)
        mt.use_nodes = True
        nt = mt.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        tc = nt.nodes.new("ShaderNodeTexImage")
        tc.image = bark if key == "deadwood" else diff
        nt.links.new(uv.outputs[0], tc.inputs[0])
        col = nt.nodes.new("ShaderNodeMix")
        col.data_type = "RGBA"
        col.blend_type = "MULTIPLY"
        col.inputs[0].default_value = 1.0
        nt.links.new(tc.outputs["Color"], col.inputs[6])
        nt.links.new(attr.outputs["Color"], col.inputs[7])
        if key == "deadwood":
            grey = nt.nodes.new("ShaderNodeHueSaturation")
            grey.inputs["Saturation"].default_value = 0.35
            grey.inputs["Value"].default_value = 0.85
            nt.links.new(col.outputs[2], grey.inputs["Color"])
            color_out = grey.outputs[0]
        else:
            color_out = col.outputs[2]
        if key == "twig":
            ta = nt.nodes.new("ShaderNodeTexImage")
            ta.image = alpha
            nt.links.new(uv.outputs[0], ta.inputs[0])
            ramp = nt.nodes.new("ShaderNodeMapRange")
            ramp.inputs["From Min"].default_value = 0.25
            ramp.inputs["From Max"].default_value = 0.6
            nt.links.new(ta.outputs["Color"], ramp.inputs["Value"])
            alpha_out = ramp.outputs[0]
            tao = nt.nodes.new("ShaderNodeTexImage")
            tao.image = aoi
            nt.links.new(uv.outputs[0], tao.inputs[0])
            mul = nt.nodes.new("ShaderNodeMix")
            mul.data_type = "RGBA"
            mul.blend_type = "MULTIPLY"
            mul.inputs[0].default_value = 0.6
            nt.links.new(color_out, mul.inputs[6])
            nt.links.new(tao.outputs["Color"], mul.inputs[7])
            color_out = mul.outputs[2]
        else:
            alpha_out = None
        normal_out = None
        if key == "twig":
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            normal_out = nm.outputs[0]
        if mode == "albedo":
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(color_out, em.inputs["Color"])
        elif mode == "normal":
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            vt = nt.nodes.new("ShaderNodeVectorTransform")
            vt.vector_type = "NORMAL"
            vt.convert_from = "WORLD"
            vt.convert_to = "CAMERA"
            nt.links.new(normal_out if normal_out else geo.outputs["Normal"], vt.inputs[0])
            # камера Blender смотрит вдоль −Z: к зрителю — −Z камеры → инвертировать z
            sep = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(vt.outputs[0], sep.inputs[0])
            neg = nt.nodes.new("ShaderNodeMath")
            neg.operation = "MULTIPLY"
            neg.inputs[1].default_value = -1.0
            nt.links.new(sep.outputs[2], neg.inputs[0])
            comb = nt.nodes.new("ShaderNodeCombineXYZ")
            nt.links.new(sep.outputs[0], comb.inputs[0])
            nt.links.new(sep.outputs[1], comb.inputs[1])
            nt.links.new(neg.outputs[0], comb.inputs[2])
            sc = nt.nodes.new("ShaderNodeVectorMath")
            sc.operation = "MULTIPLY_ADD"
            sc.inputs[1].default_value = (0.5, 0.5, 0.5)
            sc.inputs[2].default_value = (0.5, 0.5, 0.5)
            nt.links.new(comb.outputs[0], sc.inputs[0])
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(sc.outputs[0], em.inputs["Color"])
        else:
            ao = nt.nodes.new("ShaderNodeAmbientOcclusion")
            ao.samples = 32
            ao.inputs["Distance"].default_value = 0.12
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


CELLS = [
    # имя, построитель, вид (top|side), длина оси, ширина кадра, м
    ("spray_a", lambda m, r: spray(m, r, 1.0), "top", 1.0, 1.36),
    ("spray_b", lambda m, r: spray(m, r, 0.72, 1.25), "top", 0.72, 1.02),
    ("curtain_a", lambda m, r: curtain(m, r, 1.0, 0.75), "side_hang", 1.0, 1.24),
    ("curtain_b", lambda m, r: curtain(m, r, 0.75, 0.55), "side_hang", 0.75, 0.96),
    ("leader", lambda m, r: leader(m, r, 1.0), "side", 1.0, 1.36),
    ("dead", lambda m, r: dead(m, r, 1.0), "top", 1.0, 1.24),
]


def gpu() -> None:
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    bpy.context.scene.cycles.device = "GPU"
                    print("SPRUCE GPU", kind, flush=True)
                    return
            except TypeError:
                continue
    except Exception as e:
        print("SPRUCE GPU нет:", e)


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
        fn(m, random.Random(1000 + ci))
        height = width * CELL_H / CELL_W
        cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = width
        margin = 0.03 if view != "side_hang" else 0.07
        if view == "top":
            cam.location = (width / 2 - margin, 0, 3)
            cam.rotation_euler = (0, 0, 0)
            anchor = (margin / width, 0.5)
        elif view == "side":
            cam.location = (width / 2 - margin, -3, 0)
            cam.rotation_euler = (math.pi / 2, 0, 0)
            anchor = (margin / width, 0.5)
        else:
            # шторка: ось у верхнего края кадра
            cam.location = (width / 2 - margin, -3, -height / 2 + margin)
            cam.rotation_euler = (math.pi / 2, 0, 0)
            anchor = (margin / width, margin / height)
        cam.data.clip_start, cam.data.clip_end = 0.5, 6
        for mode in ("albedo", "normal", "ao"):
            mats = atlas_materials(mode)
            for o in [o for o in sc.objects if o.type == "MESH"]:
                bpy.data.objects.remove(o, do_unlink=True)
            m.build(name, mats)
            sc.cycles.samples = 96 if mode == "ao" else 32
            sc.render.filepath = str(RENDER / f"{name}_{mode}.png")
            bpy.ops.render.render(write_still=True)
            print("SPRUCE render", name, mode, flush=True)
        meta[name] = dict(cell=ci, view=view, axis_len=L, width=width, height=round(height, 4), anchor=anchor)
    (RENDER / "cells.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ дерево

ATLAS: dict = {}

# вариант: высота, доля бескронного низа, макс. длина ветки, радиус комля, шаг мутовок, шишки
VARIANTS = {
    "spruce_forest_a": dict(H=24.0, crown_base=0.42, Lmax=3.3, r0=0.27, step=0.5, cones=26, seed=11),
    "spruce_forest_b": dict(H=20.0, crown_base=0.36, Lmax=3.0, r0=0.22, step=0.46, cones=14, seed=23),
    "spruce_open": dict(H=16.5, crown_base=0.015, Lmax=4.3, r0=0.3, step=0.42, cones=60, seed=37),
    "spruce_young_a": dict(H=7.5, crown_base=0.0, Lmax=1.9, r0=0.09, step=0.48, cones=0, seed=51),
    "spruce_young_b": dict(H=4.2, crown_base=0.0, Lmax=1.25, r0=0.055, step=0.4, cones=0, seed=67),
}


def card(m: Mesh, cell: str, anchor_pt: Vector, u_dir: Vector, v_dir: Vector, scale: float, col, out_n: Vector,
         bend: float = 0.65) -> None:
    """Карточка атласа: якорь ячейки — в anchor_pt, ось u ячейки вдоль u_dir, ось v (вниз по картинке) — вдоль v_dir.
    Нормали — между нормалью плоскости (к внешней стороне) и направлением out_n «наружу из кроны»."""
    c = ATLAS[cell]
    u0, v0, du, dv = c["uv"]
    w, h = c["width"] * scale, c["height"] * scale
    ax, ay = c["anchor"]
    pts, uvs = [], []
    for cu, cv in [(0, 0), (1, 0), (1, 1), (0, 1)]:
        pts.append(anchor_pt + u_dir * ((cu - ax) * w) + v_dir * ((cv - ay) * h))
        # glTF: v вниз от верха; UV Blender: v вверх → 1 − v
        uvs.append((u0 + cu * du, 1.0 - (v0 + cv * dv)))
    face_n = u_dir.cross(v_dir).normalized()
    if face_n.dot(out_n) < 0:
        face_n = -face_n
    n = (face_n * (1 - bend) + out_n * bend).normalized()
    m.quad("needles", pts, uvs, col, [n] * 4)


def branch_path(base: Vector, az: float, L: float, rel: float, rng: random.Random, segs: int = 6) -> list:
    """Ветка ели: отходит под углом (вверх у вершины, вниз у основания кроны), провисает, кончик вверх."""
    e0 = math.radians(-20 + 72 * rel ** 1.5 + rng.uniform(-6, 6))
    droop = math.radians(12 + 46 * (1 - rel))
    upturn = math.radians(18 + 62 * (1 - rel))
    horiz = Vector((math.cos(az), math.sin(az), 0))
    pts = [base]
    for i in range(1, segs + 1):
        sfrac = (i - 0.5) / segs
        e = e0 - droop * sfrac + upturn * sfrac ** 3
        pts.append(pts[-1] + (horiz * math.cos(e) + Z * math.sin(e)) * (L / segs))
    return pts


def trunk(m: Mesh, H: float, r0: float, rng: random.Random, crown_z: float) -> list:
    """Ствол: кривизна, сбег, корневые наплывы; UV — кора в метрах (u по окружности, кратно плитке)."""
    spine = []
    z = -0.4
    wob = [rng.uniform(0, 6.28) for _ in range(4)]
    while z < H:
        k = min(1.0, max(z, 0.0) / 4 + 0.2)
        spine.append(Vector((k * (0.06 * math.sin(z * 0.23 + wob[0]) + 0.03 * math.sin(z * 0.61 + wob[1])),
                             k * (0.06 * math.sin(z * 0.19 + wob[2]) + 0.03 * math.sin(z * 0.57 + wob[3])), z)))
        z += 0.12 if z < 1.6 else (0.45 if z < H - 2 else 0.3)
    spine.append(Vector((spine[-1].x, spine[-1].y, H)))
    sides = 14 if r0 > 0.15 else 9
    p = m.part("trunk")
    base = len(p["v"])
    tile = 0.9
    reps = max(1, round(2 * math.pi * r0 / tile))
    phase = rng.uniform(0, 6.28)
    for c in spine:
        h = max(c.z, 0.0)
        r = r0 * max(1 - h / H, 0.0) ** 0.85 + 0.008
        flare = max(0.0, 1 - max(c.z, -0.4) / 1.3)
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            buttress = 1 + flare ** 2 * (0.45 + 0.5 * max(0.0, math.cos(5 * a + phase)) ** 2)
            p["v"].append(c + Vector((math.cos(a), math.sin(a), 0)) * r * buttress)
            ao = 0.55 if crown_z < c.z < H - 1 else 0.9
            p["col"].append((ao, (h / H) ** 2 * 0.25, 0.0, 1.0))
            p["nrm"].append(None)
    ring = sides + 1
    for i in range(len(spine) - 1):
        for k in range(sides):
            a0 = base + i * ring + k
            p["f"].append([a0, a0 + 1, a0 + ring + 1, a0 + ring])
            p["uv"].append([(reps * k / sides, spine[i].z / tile), (reps * (k + 1) / sides, spine[i].z / tile),
                            (reps * (k + 1) / sides, spine[i + 1].z / tile), (reps * k / sides, spine[i + 1].z / tile)])
    return spine


def trunk_at(spine: list, z: float) -> Vector:
    for a, b in zip(spine, spine[1:]):
        if a.z <= z <= b.z:
            return a.lerp(b, (z - a.z) / max(b.z - a.z, 1e-6))
    return spine[-1].copy()


def build_tree(v: dict) -> Mesh:
    rng = random.Random(v["seed"])
    m = Mesh()
    H, Lmax = v["H"], v["Lmax"]
    hb = H * v["crown_base"]
    spine = trunk(m, H, v["r0"], rng, hb)
    young = H < 9
    z = H - 0.35
    golden = math.radians(137.5)
    az0 = rng.uniform(0, 6.28)
    whorl = 0
    branches = []
    # живая крона: мутовки сверху вниз (у вершины шаг больше — быстрый рост)
    while z > hb:
        t = H - z
        rel = (z - hb) / max(H - hb, 0.1)
        n = rng.randint(4, 6) if t > 1.0 else rng.randint(3, 4)
        for k in range(n):
            az = az0 + whorl * golden + 2 * math.pi * k / n + rng.uniform(-0.35, 0.35)
            L = min(0.44 * t ** 0.95, Lmax) * rng.uniform(0.8, 1.08)
            if hb > 0.5:
                L *= 0.72 + 0.28 * min(1.0, rel / 0.22)
            branches.append((z + rng.uniform(-0.05, 0.05), az, L, rel, True))
        for _ in range(rng.randint(0, 2)):
            branches.append((z - v["step"] * rng.uniform(0.3, 0.7), rng.uniform(0, 6.28),
                             min(0.3 * t, Lmax * 0.55) * rng.uniform(0.6, 1), rel, True))
        z -= v["step"] * rng.uniform(0.85, 1.15) * (1.25 if t < 3 else 1.0)
        whorl += 1
    # сухие сучья ниже кроны (лесная ель)
    zz = hb - 0.25
    while zz > 1.4 and hb > 1.5:
        for _ in range(rng.randint(3, 6)):
            frac = (zz - 1.4) / max(hb - 1.4, 0.1)
            L = rng.uniform(0.15, 0.5) if rng.random() < 0.45 else Lmax * rng.uniform(0.25, 0.6) * (0.4 + 0.6 * frac)
            branches.append((zz, rng.uniform(0, 6.28), L, 0.0, False))
        zz -= rng.uniform(0.25, 0.45)

    cones = []
    for (bz, az, L, rel, alive) in branches:
        root = trunk_at(spine, bz)
        r_trunk = v["r0"] * max(1 - bz / H, 0) ** 0.85 + 0.008
        horiz = Vector((math.cos(az), math.sin(az), 0))
        start = root + horiz * r_trunk * 0.8
        if alive:
            pts = branch_path(start, az, L, rel, rng)
        else:
            e = math.radians(-25 + rng.uniform(-10, 10))
            pts = [start + (horiz * math.cos(e) + Z * math.sin(e)) * L * i / 4 for i in range(5)]
        rb = 0.012 + 0.022 * (L / max(Lmax, 0.1)) ** 0.9
        phase = rng.random()
        flex_k = 0.4 + 0.6 * L / max(Lmax, 0.1)
        m.tube("branch" if alive else "deadbranch", pts, [rb * (1 - 0.8 * i / (len(pts) - 1)) for i in range(len(pts))],
               4 if L < 1.4 else 5, (0.0, 1.0), 2.5,
               col_fn=lambda t, fk=flex_k, ph=phase: (0.5 + 0.4 * t, t * fk, ph, 1.0))
        if not alive:
            if L > 0.35:
                for _ in range(rng.randint(2, 3)):
                    s = rng.uniform(0.25, 0.9)
                    i = min(int(s * 4), 3)
                    pt = pts[i].lerp(pts[i + 1], s * 4 - i)
                    d = (pts[-1] - pts[0]).normalized()
                    d = (d + Vector((rng.uniform(-0.5, 0.5), rng.uniform(-0.5, 0.5), rng.uniform(-0.3, 0.1)))).normalized()
                    card(m, "dead", pt, d, rolled(d, d.cross(Z).normalized(), rng.uniform(-1.2, 1.2)), max(0.3, L) * rng.uniform(0.45, 0.75),
                         (0.7, s * flex_k, phase, 1), Z, 0.3)
            continue
        total = sum((b - a).length for a, b in zip(pts, pts[1:]))

        def point(sfrac: float):
            seg = sfrac * (len(pts) - 1)
            i = min(int(seg), len(pts) - 2)
            return pts[i].lerp(pts[i + 1], seg - i), (pts[i + 1] - pts[i]).normalized()

        def outward(pt: Vector, up: float = 0.6) -> Vector:
            return (Vector((pt.x - root.x, pt.y - root.y, 0)).normalized() * 0.8 + Z * up).normalized()

        sc = max(0.5, min(1.15, L / 2.6)) * rng.uniform(0.88, 1.08)
        # на каждом шаге вдоль ветки — пучок карточек под разными углами: плоская лапа в сторону,
        # лапа, повёрнутая почти вертикально (видна сбоку), и «шторка» снизу — объём с любого ракурса
        s = 0.16 if L > 1.2 else 0.05
        side = 1
        k = 0
        while s < 0.9:
            pt, tan = point(s)
            hor = Vector((tan.x, tan.y, 0)).normalized()
            lat = hor.cross(Z) * side
            ao = (0.35 + 0.65 * s ** 0.8) * (0.75 + 0.25 * rel)
            col = (ao, s * flex_k, phase, 1)
            ang = math.radians(rng.uniform(18, 40))
            u_dir = (tan * math.cos(ang) + lat * math.sin(ang)).normalized()
            v_dir = rolled(u_dir, u_dir.cross(Z).normalized(), math.radians(rng.uniform(-28, 28)))
            card(m, rng.choice(["spray_a", "spray_b"]), pt, u_dir, v_dir, sc * rng.uniform(0.85, 1.05), col, outward(pt))
            ang2 = math.radians(rng.uniform(10, 30))
            u2 = (tan * math.cos(ang2) - lat * math.sin(ang2)).normalized()
            v2 = rolled(u2, u2.cross(Z).normalized(), math.radians(rng.choice([-1, 1]) * rng.uniform(50, 80)))
            card(m, rng.choice(["spray_a", "spray_b"]), pt + Z * 0.03, u2, v2, sc * rng.uniform(0.75, 0.95), col, outward(pt, 0.4))
            if rel < 0.93 and k % 2 == 0 and L > 0.6:
                vd = rolled(hor, -Z, math.radians(rng.uniform(-25, 25)))
                if vd.z > 0:
                    vd = -vd
                card(m, rng.choice(["curtain_a", "curtain_b"]), pt + lat * rng.uniform(-0.06, 0.06), hor, vd,
                     sc * rng.uniform(0.8, 1.05) * (0.7 + 0.3 * (1 - rel)), (ao * 0.9, s * flex_k, phase, 1), outward(pt, 0.15), 0.75)
            side = -side
            k += 1
            s += (0.3 * sc) / max(total, 0.3) * rng.uniform(0.8, 1.15)
        pt, tan = point(0.86)
        card(m, "spray_a", pt, tan, tan.cross(Z).normalized(), sc * 0.9, (0.95 * (0.75 + 0.25 * rel), flex_k, phase, 1), outward(pt))
        if v["cones"] and rel > 0.72 and rng.random() < 0.6:
            for _ in range(rng.randint(1, 3)):
                cones.append(point(rng.uniform(0.7, 0.95))[0])
    # верхушка: три скрещенные карточки лидера (ось ячейки — вверх)
    top = trunk_at(spine, H - (0.9 if young else 1.05))
    for k in range(3):
        a = k * math.pi / 3
        side = Vector((math.cos(a), math.sin(a), 0))
        card(m, "leader", top, Z, side, 0.8 if young else 1.05, (1.0, 0.35, 0.5, 1), (side.cross(Z) * 0.3 + Z * 0.7).normalized(), 0.5)
    rng.shuffle(cones)
    for pt in cones[: v["cones"]]:
        L = rng.uniform(0.1, 0.15)
        m.tube("cone", [pt, pt + Vector((rng.uniform(-0.02, 0.02), rng.uniform(-0.02, 0.02), -L * 0.5)), pt + Vector((0, 0, -L))],
               [0.012, 0.024, 0.008], 6, (0.0, 1.0), 6.0, col_fn=lambda t: (0.8, 0.9, 0.3, 1.0))
    return m


MAT_NAMES = {"needles": "SpruceNeedles", "trunk": "SpruceTrunk", "branch": "SpruceBranch",
             "deadbranch": "SpruceDeadBranch", "cone": "SpruceCone"}


def tree_materials(young: bool = False) -> dict:
    # у молодой ели весь ствол в гладкой коре — свой материал
    names = dict(MAT_NAMES, trunk="SpruceTrunkYoung") if young else MAT_NAMES
    return {k: bpy.data.materials.new(v) for k, v in names.items()}


def export_tree(name: str, ob) -> int:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    kw = dict(filepath=str(OUT / f"{name}.glb"), export_format="GLB", use_selection=True, export_yup=True,
              export_texcoords=True, export_normals=True, export_tangents=True, export_materials="EXPORT",
              export_animations=False)
    try:
        bpy.ops.export_scene.gltf(**kw, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(**kw, export_colors=True)
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def preview_render(name: str, ob, H: float) -> None:
    """Превью (Cycles): атлас и кора на материалах, небо, солнце — для сверки с референсами."""
    sc = bpy.context.scene
    alb = image("alb", TEX / "spruce_atlas_albedo.png", False)
    nor = image("nor", TEX / "spruce_atlas_normal.png", True)
    bark = image("bark", ROOT / "assets/textures/pine_bark/albedo.jpg", False)
    smooth = image("smooth", ROOT / "assets/textures/knotted_pine_bark/albedo.jpg", False)
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
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = "RGBA"
        mul.blend_type = "MULTIPLY"
        mul.inputs[0].default_value = 1.0
        nt.links.new(t.outputs["Color"], mul.inputs[6])
        pw = nt.nodes.new("ShaderNodeMath")
        pw.operation = "POWER"
        pw.inputs[1].default_value = 0.6
        nt.links.new(sep.outputs[0], pw.inputs[0])
        nt.links.new(pw.outputs[0], mul.inputs[7])
        nt.links.new(mul.outputs[2], bsdf.inputs["Base Color"])
        if mt.name.startswith("SpruceNeedles"):
            t.image = alb
            nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = nor
            nt.links.new(uv.outputs[0], tn.inputs[0])
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.uv_map = "UVMap"
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs[0], bsdf.inputs["Normal"])
            bsdf.inputs["Roughness"].default_value = 0.8
            bsdf.inputs["Subsurface Weight"].default_value = 0.0
        else:
            t.image = smooth if (mt.name.startswith("SpruceBranch") or H < 9) else bark
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.6, 0.68, 0.8, 1)
    bg.inputs[1].default_value = 1.0
    sc.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(50), 0, math.radians(35))
    sc.collection.objects.link(sun)
    gme = bpy.data.meshes.new("g")
    gme.from_pydata([(-60, -60, 0), (60, -60, 0), (60, 60, 0), (-60, 60, 0)], [], [[0, 1, 2, 3]])
    gm = bpy.data.materials.new("gm")
    gm.use_nodes = True
    next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = (0.12, 0.14, 0.07, 1)
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
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = 900, 1200
    sc.render.filepath = str(RENDER / f"preview_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("SPRUCE preview", name, flush=True)


# ------------------------------------------------------------------ дальний вид: два скрещённых силуэта

def impostor_materials(ob, mode: str) -> None:
    """Материалы дерева в режим «цвет» или «нормаль камеры» (как в атласе) для рендера силуэта."""
    alb = image("alb", TEX / "spruce_atlas_albedo.png", False)
    nor = image("nor", TEX / "spruce_atlas_normal.png", True)
    bark = image("smooth", ROOT / "assets/textures/knotted_pine_bark/albedo.jpg", False)
    for mt in ob.data.materials:
        mt.use_nodes = True
        nt = mt.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        t = nt.nodes.new("ShaderNodeTexImage")
        nt.links.new(uv.outputs[0], t.inputs[0])
        needles = mt.name.startswith("SpruceNeedles")
        t.image = alb if needles else bark
        attr = nt.nodes.new("ShaderNodeAttribute")
        attr.attribute_name = "Col"
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(attr.outputs["Color"], sep.inputs[0])
        if mode == "albedo":
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
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(mul.outputs[2], em.inputs["Color"])
        else:
            geo = nt.nodes.new("ShaderNodeNewGeometry")
            src = geo.outputs["Normal"]
            if needles:
                tn = nt.nodes.new("ShaderNodeTexImage")
                tn.image = nor
                nt.links.new(uv.outputs[0], tn.inputs[0])
                nm = nt.nodes.new("ShaderNodeNormalMap")
                nm.uv_map = "UVMap"
                nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
                src = nm.outputs[0]
            vt = nt.nodes.new("ShaderNodeVectorTransform")
            vt.vector_type, vt.convert_from, vt.convert_to = "NORMAL", "WORLD", "CAMERA"
            nt.links.new(src, vt.inputs[0])
            sp = nt.nodes.new("ShaderNodeSeparateXYZ")
            nt.links.new(vt.outputs[0], sp.inputs[0])
            neg = nt.nodes.new("ShaderNodeMath")
            neg.operation = "MULTIPLY"
            neg.inputs[1].default_value = -1.0
            nt.links.new(sp.outputs[2], neg.inputs[0])
            cb = nt.nodes.new("ShaderNodeCombineXYZ")
            nt.links.new(sp.outputs[0], cb.inputs[0])
            nt.links.new(sp.outputs[1], cb.inputs[1])
            nt.links.new(neg.outputs[0], cb.inputs[2])
            ma = nt.nodes.new("ShaderNodeVectorMath")
            ma.operation = "MULTIPLY_ADD"
            ma.inputs[1].default_value = (0.5, 0.5, 0.5)
            ma.inputs[2].default_value = (0.5, 0.5, 0.5)
            nt.links.new(cb.outputs[0], ma.inputs[0])
            em = nt.nodes.new("ShaderNodeEmission")
            nt.links.new(ma.outputs[0], em.inputs["Color"])
        if needles:
            tr = nt.nodes.new("ShaderNodeBsdfTransparent")
            mix = nt.nodes.new("ShaderNodeMixShader")
            nt.links.new(t.outputs["Alpha"], mix.inputs[0])
            nt.links.new(tr.outputs[0], mix.inputs[1])
            nt.links.new(em.outputs[0], mix.inputs[2])
            nt.links.new(mix.outputs[0], out.inputs["Surface"])
        else:
            nt.links.new(em.outputs[0], out.inputs["Surface"])


def render_impostor(name: str, ob, H: float, width: float) -> dict:
    """Два вида (спереди и сбоку) — две полосы 512×1024, склейку делает build_spruce_atlas.py."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    gpu()
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 0
    sc.cycles.transparent_max_bounces = 256
    sc.cycles.samples = 24
    sc.render.film_transparent = True
    sc.view_settings.view_transform = "Standard"
    sc.render.resolution_x, sc.render.resolution_y = 512, 1024
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    for o in [o for o in sc.objects if o.type != "MESH" or o.name == "g"]:
        bpy.data.objects.remove(o, do_unlink=True)
    cam = bpy.data.objects.new("icam", bpy.data.cameras.new("icam"))
    sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.type = "ORTHO"
    size = max(H * 1.02, width * 4.0)
    cam.data.ortho_scale = size
    cam.data.clip_start, cam.data.clip_end = 0.1, 200
    for mode in ("albedo", "normal"):
        impostor_materials(ob, mode)
        for vi, yaw in enumerate((0.0, 90.0)):
            a = math.radians(yaw)
            cam.location = (-math.sin(a) * 60, -math.cos(a) * 60, size * 0.5 - 0.3)
            cam.rotation_euler = (math.pi / 2, 0, -a)
            sc.render.filepath = str(RENDER / f"imp_{name}_{mode}_{vi}.png")
            bpy.ops.render.render(write_still=True)
    print("SPRUCE impostor", name, flush=True)
    return dict(size=round(size, 3), base=0.3)


def far_mesh(name: str, info: dict) -> None:
    """Два скрещённых квада с половинами текстуры силуэта."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s, b = info["size"], info["base"]
    m = Mesh()
    for vi, yaw in enumerate((0.0, 90.0)):
        a = math.radians(yaw)
        right = Vector((math.cos(a), -math.sin(a), 0))
        out = Vector((-math.sin(a), -math.cos(a), 0))
        u0 = 0.5 * vi
        pts = [right * (-s / 4) + Z * (-b), right * (s / 4) + Z * (-b), right * (s / 4) + Z * (s - b), right * (-s / 4) + Z * (s - b)]
        m.quad("needles", pts, [(u0, 0), (u0 + 0.5, 0), (u0 + 0.5, 1), (u0, 1)], (1, 0.0, 0.5, 1), [out] * 4)
    mt = bpy.data.materials.new(f"SpruceFar_{name}")
    ob = m.build(f"{name}_far", {"needles": mt})
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    kw = dict(filepath=str(OUT / f"{name}_far.glb"), export_format="GLB", use_selection=True, export_yup=True,
              export_texcoords=True, export_normals=True, export_tangents=True, export_materials="EXPORT", export_animations=False)
    try:
        bpy.ops.export_scene.gltf(**kw, export_vertex_color="ACTIVE")
    except TypeError:
        bpy.ops.export_scene.gltf(**kw, export_colors=True)


def build_trees(preview: bool, only: list) -> None:
    ATLAS.update(json.loads((TEX / "spruce_atlas.json").read_text(encoding="utf-8")))
    path = OUT / "spruce.json"
    manifest = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for name, v in VARIANTS.items():
        if only and name not in only:
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        ob = build_tree(v).build(name, tree_materials(v["H"] < 9))
        n = export_tree(name, ob)
        manifest[name] = dict(triangles=n, height=v["H"],
                              collisions=[dict(pos=[0, 2.0, 0], size=[round(v["r0"] * 2.2, 3), 4.0, round(v["r0"] * 2.2, 3)], yaw=0)])
        print("SPRUCE tree", name, n, flush=True)
        if preview:
            preview_render(name, ob, v["H"])
        width = max(abs(c) for vtx in ob.data.vertices for c in (vtx.co.x, vtx.co.y))
        manifest[name]["far"] = render_impostor(name, ob, v["H"], width)
        far_mesh(name, manifest[name]["far"])
    path.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "atlas" in args:
        render_atlas()
    if "trees" in args:
        build_trees("preview" in args, [a for a in args if a.startswith("spruce_")])
