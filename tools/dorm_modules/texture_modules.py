"""Модули общежития, этап 3: материалы на принятой форме v01 (узловые, с повторением, развёртка в метрах).

Запуск (поверх файла, собранного build_modules.py с развёрткой):
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background <v02.blend> --python-exit-code 1 \
      --python tools/dorm_modules/texture_modules.py

Стены, потолок и пол в игре — материалы с повторением на поверхности любой длины, поэтому здесь не слои UCUPaint,
а узлы, которые потом повторит шейдер Godot. Текстуры — CC0: Poly Haven (assets/textures) и ambientCG
(_asset_src/dorm_textures); копии лежат в папке textures рядом с моделью, пути в .blend относительные.
"""
import math
import os
import shutil

import bmesh
import bpy
from mathutils import Vector

REPO = "E:/Games/RING-godot"
KIT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules"
SOURCES = {
    "plaster": (f"{REPO}/assets/textures/painted_plaster_wall", {"albedo": "albedo.jpg", "arm": "arm.jpg", "normal": "normal.jpg"}),
    "metal": (f"{REPO}/assets/textures/green_metal_rust", {"albedo": "albedo.jpg", "arm": "arm.jpg", "normal": "normal.jpg"}),
    "sapele": (f"{REPO}/assets/textures/sapele_veneer", {"albedo": "albedo.jpg", "arm": "arm.jpg", "normal": "normal.jpg"}),
    "wood_paint": (f"{REPO}/_asset_src/dorm_textures/PaintedWood008A", {
        "albedo": "PaintedWood008A_2K-JPG_Color.jpg", "rough": "PaintedWood008A_2K-JPG_Roughness.jpg",
        "normal": "PaintedWood008A_2K-JPG_NormalGL.jpg", "ao": "PaintedWood008A_2K-JPG_AmbientOcclusion.jpg"}),
    "terrazzo": (f"{REPO}/_asset_src/dorm_textures/Terrazzo005", {
        "albedo": "Terrazzo005_2K-JPG_Color.jpg", "rough": "Terrazzo005_2K-JPG_Roughness.jpg",
        "normal": "Terrazzo005_2K-JPG_NormalGL.jpg"}),
}
PAINT_LINE = 2.0      # граница масляной краски: 2/3 потолка 3,0 (как в сером плане)


def srgb(h: str) -> tuple:
    """Цвет из шестнадцатеричной записи sRGB в линейный."""
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


def copy_textures() -> dict:
    out = {}
    for key, (src, files) in SOURCES.items():
        dst = os.path.join(KIT, "textures", key)
        os.makedirs(dst, exist_ok=True)
        out[key] = {}
        for role, name in files.items():
            target = os.path.join(dst, f"{key}_{role}.jpg")
            if not os.path.exists(target):
                shutil.copy2(os.path.join(src, name), target)
            out[key][role] = target
    return out


# ---------------------------------------------------------------- маленький помощник для узлов

class G:
    """Обёртка над деревом узлов материала: короткие вызовы, автоматическая раскладка по столбцам."""

    def __init__(self, mat: bpy.types.Material):
        try:
            mat.use_nodes = True
        except AttributeError:
            pass
        self.mat = mat
        self.nt = mat.node_tree
        self.nt.nodes.clear()
        self.n = 0
        self.out = self.node("ShaderNodeOutputMaterial")
        self.bsdf = self.node("ShaderNodeBsdfPrincipled")
        self.link(self.bsdf.outputs[0], self.out.inputs[0])
        self.tc = self.node("ShaderNodeTexCoord")
        self.geo = self.node("ShaderNodeNewGeometry")

    def node(self, kind: str, **props):
        nd = self.nt.nodes.new(kind)
        nd.location = (-300 * (self.n // 8), -220 * (self.n % 8))
        self.n += 1
        for k, v in props.items():
            setattr(nd, k, v)
        return nd

    def link(self, a, b) -> None:
        self.nt.links.new(a, b)

    def val(self, sock, v) -> None:
        sock.default_value = v

    def math(self, op: str, a, b=None, clamp: bool = False):
        nd = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                nd.inputs[i].default_value = x
            else:
                self.link(x, nd.inputs[i])
        return nd.outputs[0]

    def mix(self, fac, a, b, blend: str = "MIX"):
        nd = self.node("ShaderNodeMix", data_type="RGBA", blend_type=blend)
        for sock, x in ((nd.inputs[0], fac), (nd.inputs[6], a), (nd.inputs[7], b)):
            if isinstance(x, (int, float)):
                # Число в цветовое гнездо — серый цвет этой яркости.
                sock.default_value = x if sock == nd.inputs[0] else (x, x, x, 1.0)
            elif isinstance(x, tuple):
                sock.default_value = x
            else:
                self.link(x, sock)
        return nd.outputs[2]

    def tint(self, color: tuple, factor):
        """Цвет × яркость фактуры (множитель может быть больше 1)."""
        return self.mix(1.0, color, factor, "MULTIPLY")

    def mixf(self, fac, a, b):
        nd = self.node("ShaderNodeMix", data_type="FLOAT")
        for sock, x in ((nd.inputs[0], fac), (nd.inputs[2], a), (nd.inputs[3], b)):
            if isinstance(x, (int, float)):
                sock.default_value = x
            else:
                self.link(x, sock)
        return nd.outputs[0]

    def uv(self, scale: float):
        mp = self.node("ShaderNodeMapping")
        self.link(self.tc.outputs["UV"], mp.inputs["Vector"])
        mp.inputs["Scale"].default_value = (scale, scale, scale)
        return mp.outputs[0]

    def image(self, path: str, vec, color: bool = True):
        nd = self.node("ShaderNodeTexImage")
        img = bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = "sRGB" if color else "Non-Color"
        nd.image = img
        self.link(vec, nd.inputs["Vector"])
        return nd

    def noise(self, vec, scale: float, detail: float = 6.0, rough: float = 0.6, dist: float = 0.0):
        nd = self.node("ShaderNodeTexNoise", noise_dimensions="3D")
        self.link(vec, nd.inputs["Vector"])
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = dist
        return nd.outputs["Fac"]

    def ramp(self, fac, a: float, b: float, ca=(0, 0, 0, 1), cb=(1, 1, 1, 1)):
        nd = self.node("ShaderNodeValToRGB")
        self.link(fac, nd.inputs[0])
        e = nd.color_ramp.elements
        e[0].position, e[0].color = a, ca
        e[1].position, e[1].color = b, cb
        return nd.outputs[0]

    def lum(self, color):
        nd = self.node("ShaderNodeRGBToBW")
        self.link(color, nd.inputs[0])
        return nd.outputs[0]

    def sep(self, vec):
        nd = self.node("ShaderNodeSeparateXYZ")
        self.link(vec, nd.inputs[0])
        return nd.outputs

    def normal_map(self, color_sock, strength: float):
        nd = self.node("ShaderNodeNormalMap")
        nd.inputs["Strength"].default_value = strength
        self.link(color_sock, nd.inputs["Color"])
        return nd.outputs[0]

    def bump(self, height, strength: float, distance: float, normal=None):
        nd = self.node("ShaderNodeBump")
        nd.inputs["Strength"].default_value = strength
        nd.inputs["Distance"].default_value = distance
        self.link(height, nd.inputs["Height"])
        if normal is not None:
            self.link(normal, nd.inputs["Normal"])
        return nd.outputs[0]

    def out_bsdf(self, color, rough, normal=None, metal=0.0) -> None:
        b = self.bsdf.inputs
        for sock, x in ((b["Base Color"], color), (b["Roughness"], rough), (b["Metallic"], metal)):
            if isinstance(x, (int, float, tuple)):
                sock.default_value = x
            else:
                self.link(x, sock)
        if normal is not None:
            self.link(normal, b["Normal"])


def mat(name: str) -> bpy.types.Material:
    return bpy.data.materials.get(name) or bpy.data.materials.new(name)


# ---------------------------------------------------------------- стены

def whitewash_material(T: dict) -> None:
    """Побелка по бетону: плиты, балки, низ маршей. Пятна от протечек, тонкие трещины по шву."""
    g = G(mat("Побелка_потолок"))
    vec = g.uv(0.5)
    alb = g.image(T["plaster"]["albedo"], vec)
    nor = g.image(T["plaster"]["normal"], vec, False)
    lum = g.lum(alb.outputs[0])
    obj = g.tc.outputs["Object"]
    base = g.tint(srgb("dcddd5"), g.math("ADD", g.math("MULTIPLY", lum, 0.8), 0.6))
    leak = g.lum(g.ramp(g.noise(obj, 0.7, 7.0, 0.7, 0.4), 0.58, 0.8))
    color = g.mix(g.math("MULTIPLY", leak, 0.6), base, srgb("a8987a"))
    ring = g.lum(g.ramp(g.noise(obj, 0.7, 7.0, 0.7, 0.4), 0.575, 0.585))
    color = g.mix(g.math("MULTIPLY", ring, 0.5), color, srgb("7d6b52"))
    g.out_bsdf(color, 0.93, g.normal_map(nor.outputs[0], 0.7))


# ---------------------------------------------------------------- дерево, металл, мозаика

def painted_wood(name: str, T: dict, hexcolor: str, rough: float, scale: float = 1.0) -> None:
    """Крашеное дерево: фактура и трещины краски ambientCG PaintedWood008A, краска перекрашена в нужный цвет
    по яркости исходника (тёмные трещины и щели остаются тёмными)."""
    g = G(mat(name))
    vec = g.uv(scale)
    alb = g.image(T["wood_paint"]["albedo"], vec)
    rgh = g.image(T["wood_paint"]["rough"], vec, False)
    nor = g.image(T["wood_paint"]["normal"], vec, False)
    ao = g.image(T["wood_paint"]["ao"], vec, False)
    lum = g.math("MULTIPLY", g.lum(alb.outputs[0]), 1.55, True)
    color = g.mix(lum, (0.012, 0.008, 0.006, 1.0), srgb(hexcolor))
    color = g.mix(1.0, color, ao.outputs[0], "MULTIPLY")
    r = g.math("ADD", g.math("MULTIPLY", rgh.outputs[0], 0.4), rough - 0.15)
    g.out_bsdf(color, r, g.normal_map(nor.outputs[0], 0.8))


def painted_metal(name: str, T: dict, hexcolor: str, rough: float, scale: float = 2.0, rust: float = 0.0) -> None:
    """Краска по металлу (батарея, ограждение): фактура green_metal_rust перекрашена; редкие точки ржавчины внизу."""
    g = G(mat(name))
    vec = g.uv(scale)
    alb = g.image(T["metal"]["albedo"], vec)
    arm = g.image(T["metal"]["arm"], vec, False)
    nor = g.image(T["metal"]["normal"], vec, False)
    sep = g.node("ShaderNodeSeparateColor")
    g.link(arm.outputs[0], sep.inputs[0])
    lum = g.math("MULTIPLY", g.lum(alb.outputs[0]), 3.2, True)
    color = g.tint(srgb(hexcolor), g.math("ADD", g.math("MULTIPLY", lum, 0.35), 0.65))
    if rust > 0:
        obj = g.tc.outputs["Object"]
        spots = g.math("GREATER_THAN", g.noise(obj, 22.0, 6.0, 0.7), 0.69)
        low = g.math("SUBTRACT", 1.0, g.math("MULTIPLY", g.sep(obj)[2], 2.2), True)
        spots = g.math("MULTIPLY", g.math("MULTIPLY", spots, g.math("ADD", low, 0.2)), rust)
        color = g.mix(spots, color, srgb("5a3a22"))
    r = g.math("ADD", g.math("MULTIPLY", sep.outputs[1], 0.3), rough - 0.1)
    g.out_bsdf(color, r, g.normal_map(nor.outputs[0], 0.5))


def handrail_wood(T: dict) -> None:
    g = G(mat("Поручень_дерево"))
    vec = g.uv(1.0)
    alb = g.image(T["sapele"]["albedo"], vec)
    nor = g.image(T["sapele"]["normal"], vec, False)
    obj = g.tc.outputs["Object"]
    color = g.mix(0.75, alb.outputs[0], srgb("3a2416"), "MULTIPLY")
    worn = g.lum(g.ramp(g.noise(obj, 4.0, 4.0), 0.6, 0.8))
    color = g.mix(g.math("MULTIPLY", worn, 0.4), color, srgb("6b4a30"))
    g.out_bsdf(color, g.mixf(worn, 0.32, 0.55), g.normal_map(nor.outputs[0], 0.4))


def terrazzo(T: dict) -> None:
    """Мозаичная крошка ступеней и площадок: серый цементный фон (Terrazzo005 затемнён), затёртый до полуглянца."""
    g = G(mat("Ступени_мозаика"))
    vec = g.uv(2.0)
    alb = g.image(T["terrazzo"]["albedo"], vec)
    rgh = g.image(T["terrazzo"]["rough"], vec, False)
    nor = g.image(T["terrazzo"]["normal"], vec, False)
    obj = g.tc.outputs["Object"]
    color = g.mix(1.0, alb.outputs[0], srgb("8d8a82"), "MULTIPLY")
    dirt = g.lum(g.ramp(g.noise(obj, 1.6, 6.0, 0.6), 0.45, 0.8))
    color = g.mix(g.math("MULTIPLY", dirt, 0.45), color, srgb("4a463e"), "MULTIPLY")
    r = g.math("ADD", g.math("MULTIPLY", rgh.outputs[0], 0.3), g.math("MULTIPLY", dirt, 0.25))
    g.out_bsdf(color, g.math("ADD", r, 0.32), g.normal_map(nor.outputs[0], 0.6))


def simple_metal(name: str, hexcolor: str, rough: float, scale: float = 30.0) -> None:
    g = G(mat(name))
    obj = g.tc.outputs["Object"]
    r = g.math("ADD", g.math("MULTIPLY", g.noise(obj, scale, 8.0, 0.7), 0.18), rough - 0.09)
    g.out_bsdf(srgb(hexcolor), r, None, 1.0)


def glass() -> None:
    g = G(mat("Стекло"))
    obj = g.tc.outputs["Object"]
    dust = g.math("MULTIPLY", g.noise(obj, 6.0, 6.0), 0.25)
    g.out_bsdf((0.85, 0.88, 0.88, 1.0), g.math("ADD", dust, 0.02))
    b = g.bsdf.inputs
    b["Transmission Weight"].default_value = 1.0
    b["IOR"].default_value = 1.52
    try:
        g.mat.surface_render_method = "DITHERED"
    except AttributeError:
        pass


# ---------------------------------------------------------------- назначение по граням

def assign_by_faces(ob: bpy.types.Object, rule) -> None:
    """rule(центр, нормаль) → индекс слота. Слоты материалов уже заданы у объекта."""
    me = ob.data
    for p in me.polygons:
        p.material_index = rule(p.center, p.normal)


def set_slots(ob, names: list) -> None:
    ob.data.materials.clear()
    for n in names:
        ob.data.materials.append(bpy.data.materials[n])


def reassign() -> None:
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        n = ob.name
        if n.startswith(("M14_", "M15_", "балка_")):
            set_slots(ob, ["Побелка_потолок"])
        elif n.startswith(("M09_", "M10_")) and "бетон" in n:
            set_slots(ob, ["Ступени_мозаика", "Побелка_потолок"])
            assign_by_faces(ob, lambda c, nn: 0 if nn.z > 0.5 or (abs(nn.y) > 0.9 and abs(nn.z) < 0.1) else 1)
        elif n.startswith("площадка_бетон"):
            set_slots(ob, ["Ступени_мозаика", "Побелка_потолок"])
            assign_by_faces(ob, lambda c, nn: 0 if nn.z > 0.5 else 1)
        elif n.startswith(("M04_", "стена_глухая_640")):
            set_slots(ob, ["Стена_фасадная"])
        elif n.startswith("сборка_пол"):
            set_slots(ob, ["Пол_паркет"])


def wear_all() -> None:
    """Сетка 10 см и атрибут «Износ» на стенах (по одной сетке на модуль — копии делят её)."""
    import texture_layers as TL
    openings = {"M02_": (-0.622, 0.622, 2.452), "M04_": (-1.048, 1.048, 2.5), "M08_": (-1.26, 1.26, 2.76)}
    done = set()
    for ob in bpy.data.objects:
        if ob.type != "MESH" or ob.data.name in done:
            continue
        n = ob.name
        if not (n.startswith(("M02_", "M04_", "M08_", "стена_глухая", "сборка_стена", "пилястра", "душевая_стена"))):
            continue
        done.add(ob.data.name)
        op = next((v for k, v in openings.items() if n.startswith(k)), None)
        TL.wear_layout(ob, op)


def shower_room() -> None:
    """Сборка для просмотра: угол душевой 2,6 × 2,6 — плитка на полу и на стенах до 2,0 м, выше побелка."""
    import mlib as L
    top = bpy.data.collections["Модули_общежития_этап2"]
    c = bpy.data.collections.get("Сборка_душевая") or bpy.data.collections.new("Сборка_душевая")
    if c.name not in top.children:
        top.children.link(c)
    x0, y0 = 40.0, -8.0
    parts = {
        "душевая_пол": ((x0, y0, -0.1), (x0 + 2.6, y0 + 2.6, 0.0), "Плитка_пол"),
        "душевая_стена_задняя": ((x0, y0 + 2.6, 0.0), (x0 + 2.6, y0 + 2.75, 3.0), "Плитка_стена"),
        "душевая_стена_боковая": ((x0 - 0.15, y0, 0.0), (x0, y0 + 2.75, 3.0), "Плитка_стена"),
    }
    for name, (mn, mx, mname) in parts.items():
        if bpy.data.objects.get(name):
            continue
        bm = bmesh.new()
        L.bm_box(bm, (0, 0, mn[2]), (mx[0] - mn[0], mx[1] - mn[1], mx[2]))
        ob = L.finish_bm(bm, name, c, bpy.data.materials[mname])
        ob.location = (mn[0], mn[1], 0.0)


# ---------------------------------------------------------------- образцы и студия

def swatches() -> None:
    """Образцы покрытий 1 × 1 м: пол (линолеум, плитка, мозаика) и стены (стена с краской, фасад)."""
    import mlib as L
    top = bpy.data.collections["Модули_общежития_этап2"]
    c = bpy.data.collections.get("Образцы_покрытий") or bpy.data.collections.new("Образцы_покрытий")
    if c.name not in top.children:
        top.children.link(c)
    for i, name in enumerate(["Пол_паркет", "Плитка_пол", "Ступени_мозаика"]):
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co.z = v.co.z * 0.02 + 0.01
        L.uv_metric(bm)
        me = bpy.data.meshes.new(f"образец_{name}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(f"образец_{name}", me)
        ob.location = (34.0 + i * 1.3, 0.0, 0.0)
        me.materials.append(bpy.data.materials[name])
        c.objects.link(ob)


def studio() -> None:
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    try:
        sc.eevee.use_raytracing = True
        sc.eevee.ray_tracing_options.resolution_scale = "1"
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    world = bpy.data.worlds.get("Студия") or bpy.data.worlds.new("Студия")
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.36, 0.40, 0.46, 1.0)
    bg.inputs[1].default_value = 0.35
    sc.world = world
    c = bpy.data.collections.get("Студия") or bpy.data.collections.new("Студия")
    if c.name not in sc.collection.children:
        sc.collection.children.link(c)

    def light(name, kind, at, rot, energy, color, size=None):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        if size is not None:
            ld.shape = "RECTANGLE"
            ld.size, ld.size_y = size
        ob = bpy.data.objects.new(name, ld)
        ob.location = at
        ob.rotation_euler = rot
        c.objects.link(ob)
        return ob
    warm = (1.0, 0.78, 0.55)
    # Солнце 12° с наружной стороны окна (как вечер в пробе света), лампы под потолком в сборках.
    sun = light("Солнце_вечер", "SUN", (4.0, -6.0, 4.0), (math.radians(78), 0, math.radians(-25)), 4.0, (1.0, 0.85, 0.68))
    sun.data.angle = math.radians(1.5)
    for i, x in enumerate((0.4, 3.0, 5.2)):
        light(f"Лампа_коридор_{i}", "AREA", (x, -8.0, 2.97), (0, 0, 0), 55, warm, (0.25, 0.25))
    light("Лампа_лестница", "AREA", (12.0, -5.4, 4.5), (0, 0, 0), 120, warm, (0.3, 0.3))
    light("Лампа_душевая", "AREA", (41.3, -6.7, 2.95), (0, 0, 0), 60, (0.92, 0.95, 1.0), (0.6, 0.15))
    light("Свет_обзорный", "AREA", (16.0, 6.0, 6.0), (math.radians(55), 0, math.radians(180)), 2500, (1, 1, 1), (8.0, 4.0))

    def cam(name, eye, target, lens):
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_start = 0.02
        ob = bpy.data.objects.new(name, cd)
        ob.location = eye
        ob.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        c.objects.link(ob)
        return ob
    first = cam("Камера_коридор", (-0.9, -8.0, 1.62), (5.5, -8.4, 1.5), 20)
    cam("Камера_дверь", (1.4, -7.2, 1.5), (1.4, -9.7, 1.3), 24)
    cam("Камера_окно", (4.7, 3.2, 1.45), (4.0, 0.2, 1.45), 30)
    cam("Камера_лестница", (14.8, -11.6, 2.9), (12.0, -7.3, 1.3), 22)
    cam("Камера_образцы", (35.3, -2.2, 1.6), (35.3, 0.0, 0.0), 35)
    cam("Камера_душевая", (42.3, -7.6, 1.6), (40.4, -5.6, 1.0), 22)
    sc.camera = first


def main() -> None:
    import texture_layers as TL
    T = copy_textures()
    for role in ("albedo", "normal", "arm"):
        dst = os.path.join(KIT, "textures", "brick", f"brick_{role}.jpg")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            shutil.copy2(f"{REPO}/assets/textures/red_bricks_04/{role}.jpg", dst)
    P = TL.tex_paths()
    TL.wall(G(mat("Штукатурка")), P)
    TL.wall(G(mat("Стена_фасадная")), P, facade=True)
    TL.parquet(G(mat("Пол_паркет")), P)
    TL.tile(G(mat("Плитка_пол")), P)
    TL.tile(G(mat("Плитка_стена")), P, wall_part=True)
    whitewash_material(T)
    painted_wood("Дверь_краска", T, "6b4c34", 0.42)
    painted_wood("Коробка_наличник_краска", T, "8a7b66", 0.45)
    painted_wood("Окно_краска_белая", T, "e2e0d6", 0.4)
    painted_wood("Плинтус_краска", T, "4a3426", 0.45)
    painted_metal("Батарея_краска", T, "d8d4c4", 0.42, 3.0, rust=1.0)
    painted_metal("Ограждение_краска", T, "2c3230", 0.45, 2.0, rust=0.6)
    handrail_wood(T)
    terrazzo(T)
    simple_metal("Алюминий", "b9bbbd", 0.38)
    simple_metal("Сталь_тёмная", "3a3b3c", 0.48)
    simple_metal("Отлив_оцинковка", "8f9497", 0.5, 8.0)
    glass()
    reassign()
    shower_room()
    wear_all()
    swatches()
    studio()
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile(compress=True)
    print("textured", bpy.data.filepath)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    main()
