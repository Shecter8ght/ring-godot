"""Купе Ильи: отделка (PBR) нативными стеками UCUPaint на принятой форме v04.

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/texture_coupe.py -- \
        <форма v04.blend> <выход.blend>

Решения по отделке (владелец согласился с рекомендацией 2026-10-18): серый неметаллик под глянцем;
машина недели стояла в ангаре после угона — пыль на горизонталях, грязь внизу и за колёсами,
тормозная пыль на дисках, разводы на стёклах, следы ладоней у ручек и на кромке капота (капот
открывали), пара тонких царапин у ручек; без ржавчины и вмятин. Карбон: губа, лопатки, пороги,
диффузор, корпуса зеркал. Салон — чёрная кожа. Стёкла прозрачные.

Маски по месту — атрибуты цвета вершин (считаются здесь: пыль сверху с проверкой «открыто небу»,
грязь снизу и брызги за колёсами, касания, тормозная пыль, дуги дворников). Рисунок — маски
владельца (E:/Models Blender/Маски_АЛЬФА, проекция кубом в метрах) и шумы с локальным порогом.
"""
from __future__ import annotations

import importlib
import math
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:]
SRC, OUT = Path(argv[0]), Path(argv[1])
MASKS = Path(r"E:\Models Blender\Маски_АЛЬФА")
TEX = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\textures")
WHEEL_Y, WHEEL_Z = 1.4355, 0.343

bpy.ops.wm.open_mainfile(filepath=str(SRC))
bpy.context.preferences.use_preferences_save = False
addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
U = importlib.import_module("bl_ext.blender_org.ucupaint")
assert U.common.get_current_version_str() == "2.4.9", "проверено на UCUPaint 2.4.9"
MM = importlib.import_module(U.__name__ + ".MaskModifier")
ROOT = importlib.import_module(U.__name__ + ".Root")


def mat(name: str) -> bpy.types.Material:
    return bpy.data.materials[name]


# --- 1. Материалы по решению: карбон на порогах, диффузоре и корпусах зеркал ------------------------
for obn in ("Skirt_L", "Skirt_R", "Diffuser", "Mirror_Housing_L", "Mirror_Housing_R"):
    ob = bpy.data.objects.get(obn)
    if ob:
        ob.data.materials.clear()
        ob.data.materials.append(mat("carbon"))

meshes = [o for o in bpy.data.objects if o.type == "MESH"]


# --- 2. Развёртки (стеку нужен UV; проекции рисунка — кубом в координатах детали) -----------------
done = set()
for ob in meshes:
    me = ob.data
    if me.name in done or me.uv_layers:
        continue
    done.add(me.name)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = ob
    ob.hide_set(False)
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.002)
    bpy.ops.object.mode_set(mode="OBJECT")
print("развёртки:", len(done))

# Номера: плоская развёртка по лицу (подложка с рамкой, флагом и RUS)
for obn in ("Plate_Front", "Plate_Rear"):
    ob = bpy.data.objects.get(obn)
    if not ob:
        continue
    me = ob.data
    xs = [v.co.x for v in me.vertices]
    zs = [v.co.z for v in me.vertices]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    uv = me.uv_layers[0].data
    flip = obn == "Plate_Rear"
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            u = (co.x - x0) / (x1 - x0)
            uv[li].uv = ((1 - u) if flip else u, (co.z - z0) / (z1 - z0))

# --- 3. Маски по месту: атрибуты цвета вершин --------------------------------------------------------
def world_arrays(ob):
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    nr = np.empty(n * 3)
    me.vertices.foreach_get("normal", nr)
    M = np.array(ob.matrix_world)
    R = np.array(ob.matrix_world.to_3x3())
    P = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    N = nr.reshape(-1, 3) @ R.T
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return P, N


# Общая BVH кузова и деталей (без салона и колёс) — для проверки «открыто сверху»
occ_v, occ_f, base = [], [], 0
for ob in meshes:
    if ob.users_collection and ob.users_collection[0].name in ("Interior",):
        continue
    P, _ = world_arrays(ob)
    occ_v.append(P)
    occ_f += [[base + i for i in p.vertices] for p in ob.data.polygons]
    base += len(P)
bvh = BVHTree.FromPolygons([tuple(v) for v in np.vstack(occ_v)], occ_f)
print("BVH:", base, "вершин")


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def sphere(P, c, r):
    d = np.linalg.norm(P - np.asarray(c), axis=1)
    return 1 - smooth(r * 0.35, r, d)


# Места касаний: ручки дверей, кромка капота (открывали), крышка багажника у знака
TOUCH = [((0.835, 0.39, 0.862), 0.16), ((-0.835, 0.39, 0.862), 0.16), ((0.0, -2.16, 0.84), 0.30),
         ((0.36, -2.10, 0.84), 0.16), ((-0.36, -2.10, 0.84), 0.16), ((0.0, 2.44, 0.86), 0.22)]
# Дворники: оси и длина щёток (дуги стёртой пыли на лобовом)
WIPERS = [((0.30, -0.865, 1.00), 0.62), ((-0.38, -0.865, 1.00), 0.52)]


def relax(me, vals, iters: int = 4):
    """Сгладить маску по рёбрам: на длинных треугольниках у кромок (стёкла) иначе «пила» из вершин."""
    if not len(me.edges):
        return vals
    e = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    deg = np.bincount(e.ravel(), minlength=len(vals)).astype(float)
    v = vals.astype(float)
    for _ in range(iters):
        acc = v.copy()
        np.add.at(acc, e[:, 0], v[e[:, 1]])
        np.add.at(acc, e[:, 1], v[e[:, 0]])
        v = acc / (1.0 + deg)
    return v


def put_attr(me, name, vals):
    vals = relax(me, vals)
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT_COLOR", "POINT")
    col = np.repeat(np.clip(vals, 0, 1)[:, None], 4, axis=1)
    col[:, 3] = 1.0
    a.data.foreach_set("color", col.astype(np.float32).ravel())


seen = set()
for ob in meshes:
    me = ob.data
    if me.name in seen:
        continue
    seen.add(me.name)
    P, N = world_arrays(ob)
    in_wheel = ob.parent is not None and ob.parent.name.startswith("Wheel_")
    # под капотом: грязь «снизу» и брызги по высоте сюда не относятся — у отсека свой налёт (m_bay)
    in_bay = any(c.name == "EngineBay" for c in ob.users_collection) or \
        ob.name.startswith(("Battery", "Cable_"))
    # пыль: обращено вверх и открыто небу (луч вверх ни во что не упирается)
    top = np.clip(N[:, 2], 0, 1) ** 1.6
    sky = np.ones(len(P))
    if not in_wheel:
        for i in np.where(top > 0.05)[0]:
            hit = bvh.ray_cast(Vector(P[i] + N[i] * 0.004), Vector((0, 0, 1)), 4.0)
            if hit[0] is not None:
                sky[i] = 0.0
    dust = top * sky
    # грязь: низ кузова, сильнее у арок и сзади колёс (брызги), меньше на верхних гранях
    low = smooth(0.66, 0.18, P[:, 2])
    spray = np.zeros(len(P))
    for yc in (-WHEEL_Y, WHEEL_Y):
        dy, dz = P[:, 1] - yc, P[:, 2] - WHEEL_Z
        r = np.sqrt(dy * dy + dz * dz)
        behind = smooth(-0.1, 0.5, dy)
        spray = np.maximum(spray, (1 - smooth(0.36, 0.80, r)) * (0.55 + 0.45 * behind))
    grime = np.clip(low ** 1.3 + 0.7 * spray * np.sqrt(low + 0.05), 0, 1) * (1 - 0.6 * top)
    spray = spray * np.sqrt(low + 0.05) * (1 - 0.6 * top)
    if in_wheel:
        grime = np.full(len(P), 0.6)
        spray = np.zeros(len(P))
    if in_bay:
        grime = np.zeros(len(P))
        spray = np.zeros(len(P))
    touch = np.zeros(len(P))
    for c, r in TOUCH:
        touch = np.maximum(touch, sphere(P, c, r))
    if me.materials and me.materials[0] and me.materials[0].name == "glass":
        for (px, py, pz), L in WIPERS:
            d = np.hypot(P[:, 0] - px, (P[:, 1] - py) * 1.0 + (P[:, 2] - pz) * 0.5)
            ang_ok = (P[:, 1] - py) > -0.02
            wiped = (1 - smooth(L - 0.03, L + 0.02, d)) * (1 - smooth(0.10, 0.06, d)) * ang_ok
            dust = dust * (1 - 0.85 * wiped)
    # тормозная пыль на диске: к ободу и в углах (ниже нормаль от оси — в «тени» спиц)
    rr = np.hypot(P[:, 1] - (ob.matrix_world.translation.y if in_wheel else 0), P[:, 2] - WHEEL_Z)
    brake = smooth(0.15, 0.25, rr) if in_wheel else np.zeros(len(P))
    put_attr(me, "m_dust", dust)
    put_attr(me, "m_grime", grime)
    put_attr(me, "m_spray", spray)
    put_attr(me, "m_bay", np.full(len(P), 1.0 if in_bay else 0.0))
    put_attr(me, "m_touch", touch)
    put_attr(me, "m_brake", brake)
print("маски вершин:", len(seen), "сеток")

# --- 4. Стеки UCUPaint ---------------------------------------------------------------------------
IMGS: dict[str, bpy.types.Image] = {}


def img(path: Path, non_color: bool = True) -> bpy.types.Image:
    key = str(path)
    if key not in IMGS:
        im = bpy.data.images.load(key, check_existing=True)
        im.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        IMGS[key] = im
    return IMGS[key]


def mask_path(rel: str) -> Path:
    return MASKS / rel


def user_of(m: bpy.types.Material):
    for ob in meshes:
        if ob.data.materials and m.name in [x.name for x in ob.data.materials if x]:
            return ob
    return None


def stack(m: bpy.types.Material):
    """Нативный стек: Color, Metallic, Roughness, Normal поверх существующего Principled."""
    ob = user_of(m)
    if ob is None:
        return None, None, None
    bpy.ops.object.select_all(action="DESELECT")
    ob.hide_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    ob.active_material_index = [x.name for x in ob.data.materials].index(m.name)
    pr = m.node_tree.nodes.get("Principled BSDF")
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=f"Отделка • {m.name}", color=True, metallic=True,
                                         roughness=True, normal=True, ao=False,
                                         switch_to_material_view=False, target_bsdf_name=pr.name)
    grp = [n for n in m.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
           and n.node_tree.yp.is_ypaint_node][0]
    return grp.node_tree, ob.data.uv_layers[0].name, pr


def coat_channels(m: bpy.types.Material, tree, pr, weight: float, rough: float) -> None:
    """Прозрачный лак — свои каналы стека (Coat Weight, Coat Roughness): автоэмаль — база под лаком.

    Пыль и грязь лежат на лаке и гасят его блеск, жир ладоней и тонкие царапины его мутят.
    """
    node = [n for n in m.node_tree.nodes if n.type == "GROUP" and n.node_tree == tree][0]
    for name, val in (("Coat Weight", weight), ("Coat Roughness", rough)):
        ch = ROOT.create_new_yp_channel(tree, name, "VALUE", non_color=True)
        U.input_outputs.check_all_channel_ios(tree.yp, yp_node=node)
        m.node_tree.links.new(node.outputs[ch.name], pr.inputs[name])
        ROOT.set_input_default_value(node, ch, val)


def set_ch(layer, idx: int, value) -> None:
    """Включить канал слоя со своим значением (цвет — кортеж, остальное — число)."""
    ch = layer.channels[idx]
    ch.enable = True
    if idx == 0:
        return
    if idx == 3:
        return
    ch.override = True
    ch.override_type = "DEFAULT"
    ch.override_value = value
    U.common.set_entity_prop_value(ch, "override_value", value)


def layer(tree, uv, name: str, color, rough: float | None = None, metal: float | None = None,
          intensity: float = 1.0, coat_w: float | None = None, coat_r: float | None = None):
    ly = U.Layer.add_new_layer(tree, name, "COLOR", 0, "MIX", "MIX", "BUMP_MAP", "UV", uv, solid_color=color)
    names = [c.name for c in tree.yp.channels]
    pairs = [(1, metal), (2, rough)]
    for cname, v in (("Coat Weight", coat_w), ("Coat Roughness", coat_r)):
        if cname in names:
            pairs.append((names.index(cname), v))
    for i, v in pairs:
        if v is not None:
            set_ch(ly, i, v)
        else:
            ly.channels[i].enable = False
    ly.channels[3].enable = False
    if intensity != 1.0:
        ly.intensity_value = intensity
        U.common.set_entity_prop_value(ly, "intensity_value", intensity)
    return ly


def ramp(mask, lo: float, hi: float) -> None:
    MM.add_new_mask_modifier(mask, "RAMP")
    mod = mask.modifiers[-1]
    rn = U.common.get_mask_tree(mask).nodes[mod.ramp]
    els = rn.color_ramp.elements
    els[0].position, els[1].position = lo, hi
    els[0].color, els[1].color = (0, 0, 0, 1), (1, 1, 1, 1)


def m_vcol(ly, uv, attr: str):
    return U.Mask.add_new_mask(ly, attr, "VCOL", "UV", uv, vcol_name=attr)


def m_noise(ly, uv, scale: float, lo: float, hi: float, detail: float = 6.0):
    mk = U.Mask.add_new_mask(ly, "шум", "NOISE", "Object", uv)
    src = U.common.get_mask_tree(mk).nodes[mk.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = detail
    src.inputs["Roughness"].default_value = 0.6
    ramp(mk, lo, hi)
    return mk


def m_image(ly, uv, rel: str, tile_m: float, lo: float = 0.15, hi: float = 0.85):
    mk = U.Mask.add_new_mask(ly, Path(rel).stem, "IMAGE", "Object", uv, image=img(mask_path(rel)),
                             socket_input_name="Color")
    src = U.common.get_mask_tree(mk).nodes[mk.source]
    src.projection = "BOX"
    src.projection_blend = 0.3
    src.extension = "REPEAT"
    mk.enable_uniform_scale = False
    s = 1.0 / tile_m
    U.common.set_entity_prop_value(mk, "scale", Vector((s, s, s)))
    ramp(mk, lo, hi)
    return mk


def bump_noise(tree, uv, name: str, scale: float, distance: float):
    ly = U.Layer.add_new_layer(tree, name, "NOISE", 3, "MIX", "MIX", "BUMP_MAP", "Object", uv)
    for i in (0, 1, 2):
        ly.channels[i].enable = False
    ch = ly.channels[3]
    ch.enable = True
    node = U.common.get_layer_source(ly)
    node.inputs["Scale"].default_value = scale
    node.inputs["Detail"].default_value = 4.0
    ch.bump_distance = distance
    U.common.set_entity_prop_value(ch, "bump_distance", distance)
    return ly


DUST = (0.43, 0.42, 0.40)         # пыль ангара: светлая, почти нейтральная (бетон, штукатурка)
GRIME = (0.155, 0.140, 0.118)     # высохшая дорожная плёнка: на сером лаке темнее, на карбоне светлее


def soften(mk, k: float) -> None:
    """Маска-рисунок только разнообразит слой, а не режет его на пятна: доля её влияния k."""
    mk.intensity_value = k
    U.common.set_entity_prop_value(mk, "intensity_value", k)


def effects(tree, uv, base_color, *, dust=0.85, grime=0.9, touch=False, spots=0.0, brake=0.0, film=0.0):
    """Общие слои состояния: грязь снизу, брызги, разводы капель, пыль, касания (снизу вверх по стеку)."""
    if grime > 0:
        # ровная плёнка по высоте (маска вершин), рисунок и шум лишь разнообразят её
        g = layer(tree, uv, "Грязь снизу (дорожная плёнка)", GRIME, rough=0.72, metal=0.0, intensity=grime,
                  coat_w=0.0)
        m_vcol(g, uv, "m_grime")
        soften(m_image(g, uv, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 0.60, 0.0, 0.55), 0.45)
        soften(m_noise(g, uv, 2.2, 0.25, 0.75), 0.5)
        s = layer(tree, uv, "Брызги из-под колёс", (0.20, 0.185, 0.16), rough=0.80, metal=0.0,
                  intensity=0.75 * grime, coat_w=0.0)
        m_vcol(s, uv, "m_spray")
        m_image(s, uv, "05_Брызги_и_высохшие_капли/Брызги_средние_01.png", 0.30, 0.20, 0.75)
    if brake > 0:
        # тормозная пыль: тёмная буро-серая (железо колодок), гуще к ободу и в углах спиц
        b = layer(tree, uv, "Тормозная пыль", (0.055, 0.048, 0.042), rough=0.6, metal=0.0, intensity=brake,
                  coat_w=0.0)
        m_vcol(b, uv, "m_brake")
        soften(m_image(b, uv, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 0.20, 0.0, 0.55), 0.6)
    if spots > 0:
        w = layer(tree, uv, "Высохшие капли (разводы)", (0.42, 0.42, 0.40), rough=0.35, metal=0.0, intensity=spots,
                  coat_r=0.22)
        m_image(w, uv, "05_Брызги_и_высохшие_капли/Капли_тонкие_контуры_01.png", 0.22, 0.15, 0.70)
        soften(m_noise(w, uv, 1.6, 0.35, 0.70), 0.8)
    if film > 0:
        # под капотом: машину гоняли до угона — ровный пыльный налёт по всему отсеку (капот на хранении
        # был закрыт, поэтому маска «открыто небу» тут ничего не даёт)
        f = layer(tree, uv, "Налёт в моторном отсеке", (0.30, 0.29, 0.27), rough=0.8, metal=0.0, intensity=film,
                  coat_w=0.0)
        m_vcol(f, uv, "m_bay")
        soften(m_image(f, uv, "03_Пыль_и_частицы/Пыль_редкая_01.png", 0.30, 0.0, 0.6), 0.5)
        soften(m_noise(f, uv, 3.0, 0.2, 0.8), 0.4)
    if dust > 0:
        d = layer(tree, uv, "Пыль ангара на горизонталях", DUST, rough=0.85, metal=0.0, intensity=dust, coat_w=0.0)
        m_vcol(d, uv, "m_dust")
        soften(m_image(d, uv, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.85, 0.0, 0.65), 0.55)
        soften(m_noise(d, uv, 1.3, 0.20, 0.80), 0.6)
        p = layer(tree, uv, "Пыль: частицы", (0.48, 0.47, 0.45), rough=0.9, metal=0.0, intensity=0.8 * dust,
                  coat_w=0.0)
        m_vcol(p, uv, "m_dust")
        m_image(p, uv, "03_Пыль_и_частицы/Пыль_редкая_01.png", 0.40, 0.20, 0.70)
    if touch:
        # ладони стёрли пыль (лак мутный от жира); угонщики открывали капот грязными руками — тёмные
        # отпечатки пальцев и ладоней; у ручек — тонкие царапины. Два размера плитки — отпечатки не в ряд
        t = layer(tree, uv, "Следы ладоней (стёрта пыль, жир)", base_color, rough=0.34, metal=None, intensity=1.0,
                  coat_w=1.0, coat_r=0.22)
        m_vcol(t, uv, "m_touch")
        m_image(t, uv, "02_Отпечатки_ладоней/Ладонь_смазанная_вправо_01.png", 0.22, 0.15, 0.70)
        t2 = layer(tree, uv, "Следы ладоней: грязные руки", (0.17, 0.16, 0.14), rough=0.5, metal=None,
                   intensity=0.55, coat_w=1.0, coat_r=0.30)
        m_vcol(t2, uv, "m_touch")
        m_image(t2, uv, "02_Отпечатки_ладоней/Ладонь_грязная_01.png", 0.27, 0.20, 0.75)
        sc = layer(tree, uv, "Царапины у ручек", (0.42, 0.42, 0.43), rough=0.35, metal=0.0, intensity=0.55,
                   coat_r=0.35)
        m_vcol(sc, uv, "m_touch")
        m_image(sc, uv, "09_Царапины/Царапины_мелкие_01.png", 0.14, 0.35, 0.85)


def base(tree, uv, color, rough, metal):
    return layer(tree, uv, "Основа", color, rough=rough, metal=metal)


def build(mname: str, color, rough: float, metal: float, *, dust=0.85, grime=0.9, touch=False,
          spots=0.0, brake=0.0, film=0.0, coat: tuple[float, float] | None = None, micro: tuple[float, float] | None = None,
          extra=None):
    m = bpy.data.materials.get(mname)
    if m is None:
        print("нет материала", mname)
        return
    tree, uv, pr = stack(m)
    if tree is None:
        print("никто не носит", mname)
        return
    if coat:
        coat_channels(m, tree, pr, *coat)
    base(tree, uv, color, rough, metal)
    if micro:
        bump_noise(tree, uv, "Микрофактура", micro[0], micro[1])
    if extra:
        extra(tree, uv, pr)
    effects(tree, uv, color, dust=dust, grime=grime, touch=touch, spots=spots, brake=brake, film=film)
    U.input_outputs.check_all_channel_ios(tree.yp, reconnect=True)
    U.input_outputs.check_start_end_root_ch_nodes(tree)
    for ly in tree.yp.layers:
        U.node_connections.reconnect_layer_nodes(ly)
    U.node_connections.reconnect_yp_nodes(tree)
    print("стек:", mname, len(tree.yp.layers), "слоёв")


PAINT = (0.330, 0.336, 0.344)            # светло-серый неметаллик (линейно), как на фото владельца
# автоэмаль: пигментный слой (шероховатость ~0,3) под прозрачным лаком (Coat, ~0,03)


def carbon_extra(tree, uv, pr):
    ly = U.Layer.add_new_layer(tree, "Карбон: саржа 2×2", "IMAGE", 0, "MIX", "MIX", "BUMP_MAP", "Object", uv,
                               image=img(TEX / "carbon_twill_color.png", non_color=False))
    src = U.common.get_layer_source(ly)
    src.projection = "BOX"
    src.projection_blend = 0.25
    ly.enable_uniform_scale = False
    U.common.set_entity_prop_value(ly, "scale", Vector((12.5, 12.5, 12.5)))     # плитка 8 см: жгут 10 мм
    ly.channels[1].enable = False
    ly.channels[2].enable = False
    ly.channels[3].enable = False


def plate_extra(name):
    def f(tree, uv, pr):
        ly = U.Layer.add_new_layer(tree, "Подложка номера", "IMAGE", 0, "MIX", "MIX", "BUMP_MAP", "UV", uv,
                                   image=img(TEX / f"{name}.png", non_color=False))
        for i in (1, 2, 3):
            ly.channels[i].enable = False
    return f


# Кузов и его детали
build("paint", PAINT, 0.32, 0.0, touch=True, spots=0.15, coat=(1.0, 0.03), micro=(420.0, 0.00004))
build("paint_inner", PAINT, 0.42, 0.0, dust=0.6, grime=0.5, film=0.35)
build("carbon", (0.05, 0.05, 0.052), 0.30, 0.0, coat=(1.0, 0.04), extra=carbon_extra, micro=None)
build("trim_black", (0.018, 0.018, 0.019), 0.55, 0.0, film=0.3, micro=(900.0, 0.00008))
build("trim_gloss_black", (0.012, 0.012, 0.013), 0.12, 0.0, film=0.25)
build("chrome", (0.85, 0.85, 0.86), 0.06, 1.0, dust=0.5, grime=0.6)
build("chrome_dark", (0.30, 0.30, 0.31), 0.16, 1.0, dust=0.4, grime=0.8)
build("glass", (0.05, 0.06, 0.065), 0.03, 0.0, dust=0.65, grime=0.35, spots=0.30)
build("lamp_glass", (0.80, 0.82, 0.85), 0.02, 0.0, dust=0.5, grime=0.4)
build("lamp_red", (0.55, 0.03, 0.03), 0.06, 0.0, dust=0.5, grime=0.5)
build("liner", (0.03, 0.03, 0.03), 0.86, 0.0, dust=0.0, grime=1.0, micro=(300.0, 0.0003))
# Колёса
build("rubber", (0.022, 0.022, 0.022), 0.88, 0.0, dust=0.4, grime=0.55, micro=(700.0, 0.0002))
build("rim_black", (0.012, 0.012, 0.013), 0.30, 0.0, dust=0.12, grime=0.0, brake=0.75, coat=(1.0, 0.05))
build("brake_steel", (0.32, 0.31, 0.30), 0.42, 1.0, dust=0.0, grime=0.5, brake=0.5)
build("caliper", (0.07, 0.07, 0.075), 0.40, 0.0, dust=0.0, grime=0.6, brake=0.6)
# Под капотом
build("engine_metal", (0.035, 0.035, 0.037), 0.62, 0.0, dust=0.55, grime=0.4, film=0.3, micro=(800.0, 0.0001))
build("hose", (0.025, 0.025, 0.025), 0.72, 0.0, dust=0.5, grime=0.3, film=0.3)
build("plastic_white", (0.62, 0.60, 0.55), 0.42, 0.0, dust=0.5, grime=0.5, film=0.3)
build("battery", (0.03, 0.03, 0.032), 0.50, 0.0, dust=0.4, grime=0.2, film=0.25)
build("brick", (0.33, 0.12, 0.07), 0.93, 0.0, dust=0.4, grime=0.0, micro=(160.0, 0.0012))
# Салон
build("leather", (0.022, 0.020, 0.019), 0.48, 0.0, dust=0.0, grime=0.0, micro=(650.0, 0.00012))
build("interior_soft", (0.025, 0.025, 0.026), 0.75, 0.0, dust=0.0, grime=0.0, micro=(900.0, 0.00006))
build("headliner", (0.16, 0.16, 0.155), 0.95, 0.0, dust=0.0, grime=0.0, micro=(1200.0, 0.00005))
build("carpet", (0.02, 0.02, 0.02), 1.0, 0.0, dust=0.0, grime=0.25)
# Номера
build("plate", (0.92, 0.92, 0.90), 0.45, 0.0, dust=0.5, grime=0.7, extra=plate_extra("plate_rear"))

# --- 5. Этикетка аккумулятора — наклейка с развёрткой на крышке ---------------------------------
bat = bpy.data.objects.get("Battery")
if bat:
    import bmesh
    bm = bmesh.new()
    cx, cy, top = -0.530, -1.11, 0.515 + 0.190 + 0.0012
    w, h = 0.075, 0.170
    vs = [bm.verts.new((cx - w / 2, cy - h / 2, top)), bm.verts.new((cx + w / 2, cy - h / 2, top)),
          bm.verts.new((cx + w / 2, cy + h / 2, top)), bm.verts.new((cx - w / 2, cy + h / 2, top))]
    f = bm.faces.new(vs)
    uvl = bm.loops.layers.uv.new("UVMap")
    for loop, uvc in zip(f.loops, ((0, 1), (0, 0), (1, 0), (1, 1))):
        loop[uvl].uv = uvc
    lme = bpy.data.meshes.new("Battery_Label")
    bm.to_mesh(lme)
    bm.free()
    lm = bpy.data.materials.new("battery_label")
    lm.use_nodes = True
    nt = lm.node_tree
    tx = nt.nodes.new("ShaderNodeTexImage")
    tx.image = img(TEX / "battery_label.png", non_color=False)
    nt.links.new(tx.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
    nt.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.45
    lme.materials.append(lm)
    lob = bpy.data.objects.new("Battery_Label", lme)
    for c in bat.users_collection:
        c.objects.link(lob)

OUT.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
print("сохранено:", OUT)
