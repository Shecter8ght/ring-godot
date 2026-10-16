"""Текстуры Мосина 1891/30 ПУ, состояние 20 %: нативные слои UCUPaint 2.4.9 на принятой геометрии (форма не меняется).

Образец отделки — Sketchfab «Mosin Nagant 1891» (KusogakiVirus), по износу ≈ 60 %; 20 % — тяжелее, палитра та же:
воронение, вытертое до серой стали на гранях и хвате, светлая сталь затвора, красно-коричневое дерево под лаком
с вмятинами и светлыми царапинами. Решения владельца — asset-state.md.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/mosin_pu/texture_mosin.py -- <модель> <режим>
  модель: rifle | scope | mount | cartridge | clip
  режим:  look    — UV и слои в памяти + кадры, файл не сохраняется (быстрая проба; MOSIN_SHOTS=a,b — выбор кадров)
          build   — UV и слои → models/…_tex20_v01.blend (картинки встроены)
          render  — кадры из сохранённого файла
          inspect — стеки, слои, маски, сверка значений с фактическими входами групп → checks/
Принятые копии формы (не меняются) — models/approved/*.blend, их SHA-256 — в asset-state.md.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import math
import os
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np
from mathutils import Matrix, Vector

ASSET = Path("E:/Models Blender/WEAPONS/Мосин — винтовка и узлы")
APPROVED = ASSET / "models/approved"
MASKS = Path("E:/Models Blender/Маски_АЛЬФА")
WOOD = ASSET / "textures/wood"
VIEW = ASSET / "renders/tex20"
CHECKS = ASSET / "checks"
SKILL = Path("C:/Users/Schecter_8ght/.claude/skills/weapon-asset-texturing")
UV = "UVMap"
MM = 0.001

MODELS = {
    "rifle": ("Mosin_9130PU_Rifle_v06.blend", "models/01_Винтовка/Mosin_9130PU_Rifle_v06_tex20_v01.blend"),
    "scope": ("Mosin_PU_Scope_v01.blend", "models/02_Прицел/Mosin_PU_Scope_v01_tex20_v01.blend"),
    "mount": ("Mosin_PU_Mount_v01.blend", "models/03_Крепление/Mosin_PU_Mount_v01_tex20_v01.blend"),
    "cartridge": ("Mosin_Cartridge_762x54R_v01.blend", "models/04_Патрон/Mosin_Cartridge_762x54R_v01_tex_v01.blend"),
    "clip": ("Mosin_StripperClip_v01.blend", "models/05_Обойма/Mosin_StripperClip_v01_tex_v01.blend"),
    "assembly": (None, "models/00_Сборка/Mosin_9130PU_Assembly_tex20_v01.blend"),   # только render
}
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODEL = ARGS[0] if ARGS else "rifle"
MODE = ARGS[1] if len(ARGS) > 1 else "look"
U = H = None

# ---------------------------------------------------------------- палитра (линейные RGB слоёв, не пиксели снимка)
P = {
    "blued": (0.032, 0.034, 0.041),         # воронение, где цело — серо-синее (образец)
    "blued_mottle": (0.052, 0.055, 0.063),  # неровный тон воронения (крупные пятна)
    "patina": (0.098, 0.090, 0.085),        # вытертое воронение — серая сталь с тёплым налётом (образец буроватый)
    "patina_warm": (0.085, 0.074, 0.060),   # вытертое с бурым оттенком (пот, масло)
    "steel_edge": (0.42, 0.41, 0.39),       # кромки до стали
    "steel_scratch": (0.30, 0.295, 0.285),  # царапины до стали
    "rust": (0.105, 0.042, 0.016),          # бурая ржавчина в карманах и порах
    "rust_dark": (0.035, 0.018, 0.010),
    "grime": (0.011, 0.009, 0.007),         # грязь углублений
    "dust": (0.23, 0.20, 0.165),            # пыль
    "bolt": (0.16, 0.16, 0.168),            # сталь затвора — светлее воронения, серо-синеватая, не хром (образец)
    "bolt_tarnish": (0.045, 0.041, 0.037),
    "blued_thin": (0.068, 0.069, 0.075),    # истончившееся воронение — серо-синее (20 %: почти везде)
    "wood_tint": (0.045, 0.021, 0.014),     # подмес к фото дерева: образец тёмный и розово-коричневый, полосы мягче
    "wood_worn": (0.10, 0.055, 0.038),      # вытертый до дерева лак — светлее и суше
    "wood_dent": (0.030, 0.014, 0.009),     # вмятины и грязь в них
    "wood_scratch": (0.24, 0.145, 0.10),    # светлые царапины по лаку
}


# ---------------------------------------------------------------- UCUPaint
def native() -> None:
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    spec = importlib.util.spec_from_file_location("ucupaint_helpers", SKILL / "scripts/ucupaint_helpers.py")
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    U = H.load_ucupaint()
    print("TEX ucupaint", U.common.get_current_version_str(), flush=True)


def activate(ob, slot: int = 0) -> None:
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.active_material_index = slot


def unwrap() -> None:
    """Развёртка каждой детали (Smart UV) — для каналов UCUPaint и будущего запекания; формы не меняет."""
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        if ob.data.uv_layers.get(UV):
            continue
        ob.data.uv_layers.new(name=UV)
        activate(ob)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    print("TEX uv done", flush=True)


def make_stack(material_name: str, label: str):
    mat = bpy.data.materials[material_name]
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and mat in list(o.data.materials))
    activate(ob, list(ob.data.materials).index(mat))
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for link in list(bsdf.inputs["Normal"].links):
        nt.links.remove(link)
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=label, color=True, metallic=True, roughness=True, normal=True, ao=False,
                                         switch_to_material_view=False, target_bsdf_name=bsdf.name)
    group = next(n for n in nt.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    normal.enable_smooth_bump = False
    normal.main_uv = UV
    group.label = label
    mat["authoring"] = "Нативный UCUPaint 2.4.9; Claude; образец — Sketchfab Mosin Nagant 1891 (KusogakiVirus); состояние 20 %"
    return tree


def layer(tree, name: str, color=None, metal=None, rough=None, height=None, source: str = "COLOR", scale: float = 0.0,
          amount: float = 1.0, distance: float = 0.00003, detail: float = 2.0, image=None, blend: str = "MIX"):
    """Слой наверх стека. color/metal/rough — постоянные значения каналов; height: число — постоянная высота
    (0 — утоплено), "source" — рельеф из рисунка источника (шум или картинка)."""
    tree.yp.halt_update = True
    result = U.Layer.add_new_layer(tree, name, source, -1, blend, "OVERLAY", "BUMP_MAP", "Object", UV,
                                   image=image, use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    values = {"Color": color, "Metallic": metal, "Roughness": rough, "Normal": height}
    for root, ch in zip(tree.yp.channels, result.channels):
        value = values[root.name]
        ch.enable = value is not None
        if not ch.enable:
            continue
        if not isinstance(value, str):
            ch.override = True
            ch.override_type = "DEFAULT"
            H.sync_property(U, ch, "override_color" if root.type == "RGB" else "override_value", value)
        if root.type == "NORMAL":
            H.sync_property(U, ch, "bump_distance", distance)
            H.sync_property(U, ch, "bump_midlevel", 0.5)
    if source == "NOISE":
        src = U.common.get_layer_source(result)
        src.inputs["Scale"].default_value = scale
        src.inputs["Detail"].default_value = detail
        src.inputs["Roughness"].default_value = 0.62
    H.sync_property(U, result, "intensity_value", amount)
    return result


def ramp(mask, lo: float, hi: float) -> None:
    module = importlib.import_module(U.__name__ + ".MaskModifier")
    module.add_new_mask_modifier(mask, "RAMP")
    node = U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp]
    node.color_ramp.elements[0].position = lo
    node.color_ramp.elements[1].position = hi
    node.color_ramp.elements[0].color = (0, 0, 0, 1)
    node.color_ramp.elements[1].color = (1, 1, 1, 1)


def noise(target, name: str, scale: float, lo: float | None = None, hi: float | None = None,
          offset: tuple = (0.0, 0.0, 0.0), stretch: tuple = (1.0, 1.0, 1.0)):
    """Нерегулярность. scale — частота на метр (30 ≈ пятна 3 см). Порог — внутри самой маски шума."""
    result = U.Mask.add_new_mask(target, name, "NOISE", "Object", UV)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = 2.4
    src.inputs["Roughness"].default_value = 0.66
    result.translation = offset
    if stretch != (1.0, 1.0, 1.0):
        result.enable_uniform_scale = False
        U.common.set_entity_prop_value(result, "scale", Vector(stretch))
    if lo is not None:
        H.local_noise_ramp(U, result, lo, hi)
    return result


def edges(target, radius: float, lo: float, hi: float):
    result = U.Mask.add_new_mask(target, "Настоящие кромки — по кривизне", "EDGE_DETECT", "Object", UV,
                                 edge_detect_radius=radius, hemi_use_prev_normal=False)
    ramp(result, lo, hi)
    return result


def vcol(target, name: str, label: str):
    return U.Mask.add_new_mask(target, label, "VCOL", "Object", UV, vcol_name=name)


def ao_inv(target, label: str, distance: float):
    result = U.Mask.add_new_mask(target, label, "AO", "Object", UV, ao_distance=distance, hemi_use_prev_normal=False)
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(result, "INVERT")
    return result


def owner_mask(target, rel: str, tile_mm: float, label: str, lo: float | None = None, hi: float | None = None,
               offset: tuple = (0.0, 0.0, 0.0), stretch: tuple = (1.0, 1.0, 1.0)):
    """Маска владельца (Маски_АЛЬФА) объёмной проекцией: плитка tile_mm в настоящем масштабе; stretch < 1 по оси —
    рисунок вытянут вдоль неё (риски вдоль ствола)."""
    img = bpy.data.images.load(str(MASKS / rel), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    result = U.Mask.add_new_mask(target, label, "IMAGE", "Object", UV, image=img)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.projection = "BOX"
    src.projection_blend = 0.2
    src.extension = "REPEAT"
    k = 1000.0 / tile_mm
    result.enable_uniform_scale = False
    U.common.set_entity_prop_value(result, "scale", Vector((k * stretch[0], k * stretch[1], k * stretch[2])))
    result.translation = offset
    if lo is not None:
        ramp(result, lo, hi)
    return result


# ---------------------------------------------------------------- маски по геометрии (цветовые атрибуты углов граней)
def loops_world(ob):
    me = ob.data
    n = len(me.loops)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    mw = np.array(ob.matrix_world, np.float32)
    world = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    idx = np.empty(n, np.int32)
    me.loops.foreach_get("vertex_index", idx)
    pn = np.empty(len(me.polygons) * 3, np.float32)
    me.polygons.foreach_get("normal", pn)
    total = np.empty(len(me.polygons), np.int32)
    me.polygons.foreach_get("loop_total", total)
    nrm = np.repeat(pn.reshape(-1, 3) @ mw[:3, :3].T, total, axis=0)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
    return world[idx] * 1000.0, nrm


def write_attr(ob, name: str, arr) -> None:
    me = ob.data
    attr = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="CORNER")
    rgba = np.ones((len(me.loops), 4), np.float32)
    rgba[:, :3] = np.clip(arr, 0.0, 1.0).astype(np.float32)[:, None]
    attr.data.foreach_set("color", rgba.ravel())


def smooth_band(x, a, b, soft):
    """1 внутри [a, b], плавно к 0 за soft мм."""
    return np.clip(np.minimum(x - a, b - x) / soft + 1.0, 0.0, 1.0)


# насколько деталь обтирается руками и о снаряжение (0…1); остальное делает кривизна и шум
RIFLE_CONTACT = {
    "Receiver": 1.0, "Receiver_Tang": 0.8, "Receiver_TangScrew": 0.9, "Receiver_Interrupter": 0.5,
    "Barrel": 0.55, "Band_Front": 0.9, "Band_Rear": 0.9, "Band_Spring": 0.6, "Band_Spring.001": 0.6,
    "Magazine_Box": 0.75, "Magazine_Follower": 0.3, "Magazine_Latch": 0.9, "Magazine_FrontScrew": 0.8,
    "TriggerGuard": 0.85, "Trigger": 1.0, "Buttplate": 0.95, "RearSight_Base": 0.55, "RearSight_Leaf_Mesh": 0.75,
    "RearSight_Slider": 0.95, "RearSight_Pin": 0.8, "FrontSight_Base": 0.6, "FrontSight_Block": 0.6,
    "FrontSight_Hood": 0.9, "FrontSight_Post": 0.4, "CleaningRod": 0.7, "Stock_NoseCap": 0.85,
    "Handguard_Ferrule_Rear": 0.8, "Handguard_Ferrule_Front": 0.8, "Sling_Escutcheon": 0.9,
    "Bolt_Body": 1.0, "Bolt_Head": 0.8, "Bolt_Handle": 1.0, "Bolt_Handle_Ball": 1.0, "Bolt_CockingPiece": 0.85,
    "Bolt_Knob": 1.0, "Bolt_FiringPin_End": 0.7,
}


def rifle_masks() -> None:
    """Wear_Contact — где металл вытерт руками и снаряжением; Wear_Rest — низ, которым винтовку ставят и кладут;
    Wood_Wear — где лак ложи стёрт хватом, щекой и о землю."""
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        w, n = loops_world(ob)
        x, y, z = w[:, 0], w[:, 1], w[:, 2]
        base = next((v for k, v in RIFLE_CONTACT.items() if ob.name.startswith(k)), 0.6)
        if ob.name.startswith(("Stock", "Handguard")) and not ob.name.startswith(("Stock_NoseCap", "Stock_CrossScrew", "Handguard_Ferrule")):
            side = np.abs(n[:, 1])
            down = np.clip(-n[:, 2], 0.0, 1.0)
            up = np.clip(n[:, 2], 0.0, 1.0)
            wrist = smooth_band(x, -285.0, -165.0, 35.0) * (0.55 + 0.45 * np.maximum(side, down))
            fore = smooth_band(x, -20.0, 230.0, 60.0) * (0.25 + 0.55 * np.maximum(side, down))
            cheek = smooth_band(x, -440.0, -300.0, 40.0) * up * 0.7
            butt = smooth_band(x, -510.0, -430.0, 30.0) * (0.3 + 0.6 * down)
            hg = (smooth_band(x, 165.0, 520.0, 40.0) * up * 0.55) if ob.name.startswith("Handguard") else 0.0
            wood = np.maximum.reduce([np.full_like(x, 0.28), wrist, fore, cheek, butt, hg + 0 * x])
            write_attr(ob, "Wood_Wear", wood)
            write_attr(ob, "Wear_Contact", wood * 0.0)
            write_attr(ob, "Wear_Rest", np.clip(-n[:, 2] - 0.5, 0.0, 0.5) * 2.0 * smooth_band(x, -520.0, -380.0, 30.0))
            continue
        contact = np.full_like(x, base)
        if ob.name == "Barrel":                     # ствол открыт у коробки и у дула; под накладкой не трётся
            contact = base * np.maximum(smooth_band(x, 0.0, 90.0, 15.0), smooth_band(x, 600.0, 740.0, 30.0) * 1.4)
        up = np.clip(n[:, 2], 0.0, 1.0)
        out = np.clip(-n[:, 1], 0.0, 1.0)          # правый бок — к стрелку и к снаряжению
        contact = contact * (0.75 + 0.25 * np.maximum(up, out))
        rest = np.clip(-n[:, 2] - 0.35, 0.0, 0.65) / 0.65
        rest = rest * (1.0 if ob.name.startswith(("Magazine_Box", "TriggerGuard", "Buttplate", "Stock_NoseCap", "Band")) else 0.3)
        write_attr(ob, "Wear_Contact", contact)
        write_attr(ob, "Wear_Rest", rest)
        write_attr(ob, "Wood_Wear", contact * 0.0)
        ob.data.update()
    print("TEX masks done", flush=True)


# ---------------------------------------------------------------- материалы
def grime(tree, amount: float, color=None, ao: float = 0.004, scale: float = 900.0) -> None:
    lay = layer(tree, "70 • Грязь в углублениях и стыках", color or P["grime"], 0.0, 0.85, amount=amount)
    ao_inv(lay, "Защищённые места — близость поверхностей", ao)
    noise(lay, "Отложения неровные", scale, 0.3, 0.58, (0.012, 0.031, 0.003))


def dust(tree, amount: float) -> None:
    lay = layer(tree, "72 • Пыль на уступах и в карманах", P["dust"], 0.0, 0.95, amount=amount)
    ao_inv(lay, "Защищённые места", 0.008)
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 120.0, "Пыль лежит пятнами — 120 мм", 0.25, 0.8, (0.02, 0.09, 0.05))


def blued_steel(material: str, label: str):
    """Воронёная сталь, 20 %: воронение сохранилось пятнами и в защищённых местах, на хвате и гранях — серая сталь,
    кромки до блеска, царапины, бурый налёт в порах и карманах, грязь в стыках."""
    tree = make_stack(material, label)
    layer(tree, "00 • Воронение", P["blued"], 1.0, 0.36)
    layer(tree, "02 • Микрофактура стали", height="source", source="NOISE", scale=4200.0, distance=0.00002)
    lay = layer(tree, "04 • Неровный тон воронения — пятна 3–6 см", P["blued_mottle"], 1.0, 0.4, amount=0.65)
    noise(lay, "Крупные пятна", 22.0, 0.42, 0.7)
    lay = layer(tree, "06 • Шероховатость пятнами", rough=0.5, amount=0.5)
    noise(lay, "Неровность отделки", 160.0)
    lay = layer(tree, "08 • Воронение истончилось — крупные пятна 5–10 см", P["blued_thin"], 1.0, 0.38, amount=0.8)
    noise(lay, "Пятна общего износа", 12.0, 0.3, 0.75, (0.11, 0.05, 0.02))
    lay = layer(tree, "10 • Вытертое воронение — серая сталь (хват, снаряжение)", P["patina"], 1.0, 0.44, amount=1.0)
    vcol(lay, "Wear_Contact", "Где трут — по детали и стороне")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png", 120.0, "Потёртости — маска владельца 120 мм", 0.0, 0.6)
    noise(lay, "Края проплешин рваные", 60.0, 0.15, 0.55, (0.03, 0.07, 0.01))
    lay = layer(tree, "11 • Вытерто пятнами ещё (20 %)", P["patina"], 1.0, 0.44, amount=0.6)
    vcol(lay, "Wear_Contact", "Где трут — по детали и стороне")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_с_потёртостями_01.png", 110.0, "Сколы с потёртостями — 110 мм", 0.05, 0.65, (0.041, 0.023, 0.067))
    lay = layer(tree, "12 • Тёплый оттенок вытертого (пот, масло)", P["patina_warm"], 1.0, 0.4, amount=0.75)
    vcol(lay, "Wear_Contact", "Где трут")
    noise(lay, "Пятна 4 см", 26.0, 0.5, 0.72, (0.05, 0.02, 0.09))
    lay = layer(tree, "14 • Протёрто о землю и ремень (низ)", P["patina"], 1.0, 0.42, amount=0.8)
    vcol(lay, "Wear_Rest", "Низ детали")
    noise(lay, "Потёртость неровная", 70.0, 0.3, 0.6)
    lay = layer(tree, "20 • Кромки до стали", P["steel_edge"], 1.0, 0.27, height=0.0, distance=0.00003, amount=0.95)
    edges(lay, 0.0009, 0.04, 0.12)
    noise(lay, "Оголено длинными участками", 140.0, 0.36, 0.56)
    lay = layer(tree, "22 • Длинные царапины до стали", P["steel_scratch"], 1.0, 0.3, height=0.0, distance=0.00003, amount=0.6)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 140.0, "Царапины — маска владельца 140 мм", 0.55, 0.88)
    vcol(lay, "Wear_Contact", "Больше там, где трут")
    lay = layer(tree, "24 • Мелкие риски", (0.17, 0.165, 0.16), 1.0, 0.3, amount=0.5)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 70.0, "Мелкие риски — 70 мм", 0.4, 0.85, (0.031, 0.007, 0.019))
    lay = layer(tree, "30 • Бурый налёт в порах и карманах", P["rust"], 0.25, 0.78, amount=0.85)
    ao_inv(lay, "Укрытые места", 0.005)
    owner_mask(lay, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 90.0, "Налёт пятнами — 90 мм", 0.35, 0.8)
    lay = layer(tree, "32 • Точки ржавчины и раковины", P["rust_dark"], 0.2, 0.82, height=0.0, distance=0.00004, amount=0.8)
    noise(lay, "Редкие точки", 900.0, 0.62, 0.68, (0.07, 0.01, 0.03))
    noise(lay, "Гнёздами", 30.0, 0.45, 0.7)
    lay = layer(tree, "40 • Жирный блеск хвата и отпечатки", rough=0.2, amount=0.6)
    vcol(lay, "Wear_Contact", "Где держат")
    owner_mask(lay, "02_Отпечатки_ладоней/Ладонь_растёртая_01.png", 110.0, "Ладонь растёртая — 110 мм", 0.2, 0.7, (0.04, 0.0, 0.02))
    dust(tree, 0.35)
    grime(tree, 0.9)
    H.reconnect(U, tree)
    return tree


def bright_steel(material: str, label: str):
    """Светлая сталь затвора: шлифованная, потускневшая пятнами, продольные риски от хода, грязь и масло в пазах."""
    tree = make_stack(material, label)
    layer(tree, "00 • Сталь шлифованная", P["bolt"], 1.0, 0.3)
    layer(tree, "02 • Микрофактура", height="source", source="NOISE", scale=5200.0, distance=0.000015)
    lay = layer(tree, "04 • Потускнение пятнами 3–6 см", P["bolt_tarnish"], 1.0, 0.42, amount=0.45)
    noise(lay, "Пятна потускнения", 24.0, 0.4, 0.72)
    lay = layer(tree, "06 • Тёмный налёт в стороне от хода", (0.055, 0.05, 0.045), 1.0, 0.5, amount=0.35)
    ao_inv(lay, "Укрытые места", 0.004)
    noise(lay, "Налёт неровно", 120.0, 0.35, 0.65)
    lay = layer(tree, "10 • Продольные риски от хода затвора", (0.52, 0.51, 0.5), 1.0, 0.22, height=0.0, distance=0.00002, amount=0.8)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 120.0, "Риски вдоль оси — маска владельца", 0.4, 0.8,
               stretch=(0.15, 1.0, 1.0))
    lay = layer(tree, "12 • Кромки заполированы", (0.36, 0.355, 0.35), 1.0, 0.22, amount=0.8)
    edges(lay, 0.0007, 0.03, 0.1)
    noise(lay, "Длинными участками", 160.0, 0.36, 0.56)
    lay = layer(tree, "20 • Точки ржавчины", P["rust"], 0.3, 0.8, height=0.0, distance=0.00003, amount=0.75)
    noise(lay, "Редкие точки", 1100.0, 0.64, 0.69, (0.03, 0.08, 0.02))
    noise(lay, "Гнёздами", 40.0, 0.45, 0.7)
    lay = layer(tree, "30 • Масло и отпечатки", (0.2, 0.19, 0.17), 1.0, 0.16, amount=0.5)
    owner_mask(lay, "01_Отпечатки_пальцев/Отпечаток_смазанный_вправо_01.png", 45.0, "Отпечатки — 45 мм", 0.2, 0.7)
    grime(tree, 0.95, scale=1200.0)
    H.reconnect(U, tree)
    return tree


def wood_stock(material: str, label: str):
    """Ложа: фото дерева (CC0) под лаком; 20 %: лак стёрт на шейке, цевье и гребне, вмятины, светлые царапины,
    грязь у металла и в углах, затёртые кромки."""
    tree = make_stack(material, label)
    img = bpy.data.images.load(str(WOOD / "dark_wood_diff_4k.jpg"), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    lay = layer(tree, "00 • Дерево — Poly Haven Dark Wood (CC0)", color="source", rough=0.52, metal=0.0, height="source",
                source="IMAGE", image=img, distance=0.00004)
    src = U.common.get_layer_source(lay)
    src.projection = "BOX"
    src.projection_blend = 0.3
    lay.enable_uniform_scale = False
    U.common.set_entity_prop_value(lay, "scale", Vector((1.0 / 1.0, 1.0 / 0.5, 1.0 / 0.5)))   # плитка 1 м вдоль ложи
    layer(tree, "02 • Тон лака — к образцу (красно-коричневый, полосы мягче)", P["wood_tint"], amount=0.6)
    lay = layer(tree, "04 • Неровность лака", rough=0.55, amount=0.6)
    noise(lay, "Пятна лака", 60.0)
    lay = layer(tree, "06 • Тёмные пятна — неровный тон старого дерева", (0.03, 0.014, 0.009), 0.0, 0.55, amount=0.35)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 220.0, "Пятна — 220 мм", 0.15, 0.7)
    lay = layer(tree, "10 • Лак стёрт хватом и щекой", P["wood_worn"], 0.0, 0.6, amount=0.85)
    vcol(lay, "Wood_Wear", "Где держат")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png", 180.0, "Потёртости — 180 мм", 0.2, 0.7)
    noise(lay, "Края рваные", 40.0, 0.35, 0.62)
    lay = layer(tree, "12 • Затёртые кромки", P["wood_worn"], 0.0, 0.6, height=0.0, distance=0.00008, amount=0.8)
    edges(lay, 0.0016, 0.03, 0.12)
    noise(lay, "С перерывами", 300.0, 0.4, 0.6)
    lay = layer(tree, "20 • Вмятины и забоины", P["wood_dent"], 0.0, 0.8, height=0.0, distance=0.00025, amount=1.0)
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_пятнами_01.png", 150.0, "Забоины — 150 мм", 0.35, 0.75)
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_с_потёртостями_01.png", 230.0, "Вторая сетка — без повтора", 0.2, 0.6,
               (0.073, 0.031, 0.052))
    noise(lay, "Гнёздами — 10–15 см", 7.0, 0.35, 0.7, (0.21, 0.09, 0.04))
    lay = layer(tree, "22 • Светлые царапины и забоинки по лаку", P["wood_scratch"], 0.0, 0.7, height=0.0, distance=0.00004, amount=0.8)
    owner_mask(lay, "09_Царапины/Царапины_перекрёстные_01.png", 110.0, "Царапины — 110 мм", 0.45, 0.85)
    noise(lay, "Не везде", 25.0, 0.3, 0.65)
    lay = layer(tree, "24 • Короткие забоинки (светлые штрихи)", P["wood_scratch"], 0.0, 0.7, height=0.0, distance=0.00006, amount=0.7)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 60.0, "Штрихи — 60 мм", 0.55, 0.9, (0.02, 0.05, 0.01))
    lay = layer(tree, "30 • Тёмное масло у металла и на хвате", (0.025, 0.012, 0.007), 0.0, 0.4, amount=0.55)
    ao_inv(lay, "У стыков с металлом", 0.008)
    noise(lay, "Пятнами", 35.0, 0.4, 0.7)
    lay = layer(tree, "32 • Затемнение хвата — пот и грязь", (0.03, 0.015, 0.009), 0.0, 0.5, amount=0.4)
    vcol(lay, "Wood_Wear", "Где держат")
    noise(lay, "Пятнами", 18.0, 0.45, 0.75)
    dust(tree, 0.12)
    grime(tree, 0.85, ao=0.006, scale=500.0)
    H.reconnect(U, tree)
    return tree


def part_masks(contact: dict, default: float, rest_names: tuple = ()) -> None:
    """Маски для узлов без дерева: Wear_Contact — по детали и стороне (верх и правый бок трутся сильнее),
    Wear_Rest — низ, которым узел ставят."""
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        w, n = loops_world(ob)
        base = next((v for k, v in contact.items() if ob.name.startswith(k)), default)
        up = np.clip(n[:, 2], 0.0, 1.0)
        out = np.clip(-n[:, 1], 0.0, 1.0)
        c = np.full(len(w), base, np.float32) * (0.75 + 0.25 * np.maximum(up, out))
        rest = np.clip(-n[:, 2] - 0.35, 0.0, 0.65) / 0.65 * (1.0 if rest_names and ob.name.startswith(rest_names) else 0.25)
        write_attr(ob, "Wear_Contact", c)
        write_attr(ob, "Wear_Rest", rest)
        write_attr(ob, "Wood_Wear", c * 0.0)
        ob.data.update()
    print("TEX masks done", flush=True)


def black_paint(material: str, label: str):
    """Прицел ПУ: чёрная полуглянцевая эмаль по стали; 20 %: эмаль стёрта на торцах, кромках, маховичках и
    в местах колец, царапины до стали, бурые точки в сколах, грязь у шагов и швов."""
    tree = make_stack(material, label)
    layer(tree, "00 • Чёрная эмаль", (0.016, 0.016, 0.017), 0.0, 0.24)
    layer(tree, "02 • Шагрень эмали — 60 мкм", height="source", source="NOISE", scale=2600.0, distance=0.00006)
    lay = layer(tree, "04 • Выцветшая эмаль пятнами", (0.03, 0.029, 0.028), 0.0, 0.4, amount=0.55)
    noise(lay, "Пятна 3–5 см", 28.0, 0.4, 0.72)
    lay = layer(tree, "10 • Эмаль стёрта до тёмной стали", (0.075, 0.072, 0.07), 1.0, 0.42, height=0.0, distance=0.00004, amount=0.95)
    vcol(lay, "Wear_Contact", "Где трут")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_пятнами_01.png", 70.0, "Сколы пятнами — 70 мм", 0.25, 0.65)
    lay = layer(tree, "12 • Кромки до светлой стали", (0.30, 0.295, 0.29), 1.0, 0.3, height=0.0, distance=0.00004, amount=0.95)
    edges(lay, 0.0007, 0.04, 0.12)
    noise(lay, "Длинными участками", 180.0, 0.36, 0.56)
    lay = layer(tree, "14 • Царапины до стали", (0.24, 0.235, 0.23), 1.0, 0.32, height=0.0, distance=0.00003, amount=0.7)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 90.0, "Царапины — 90 мм", 0.55, 0.88, stretch=(0.35, 1.0, 1.0))
    lay = layer(tree, "16 • Бурые точки в сколах", P["rust"], 0.2, 0.8, amount=0.7)
    ao_inv(lay, "Укрытые места", 0.004)
    owner_mask(lay, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 60.0, "Налёт — 60 мм", 0.4, 0.82)
    lay = layer(tree, "40 • Жир и отпечатки", rough=0.22, amount=0.55)
    owner_mask(lay, "01_Отпечатки_пальцев/Отпечаток_грязный_01.png", 40.0, "Отпечатки — 40 мм", 0.2, 0.7)
    dust(tree, 0.15)
    grime(tree, 0.9, scale=1300.0)
    H.reconnect(U, tree)
    return tree


def lens_glass(material: str, label: str):
    """Стёкла прицела: прозрачность и преломление остаются в материале; слоями — лёгкая пыль и мелкие царапины."""
    tree = make_stack(material, label)
    layer(tree, "00 • Стекло с просветлением (лёгкий сине-зелёный оттенок)", (0.86, 0.93, 0.95), 0.0, 0.02)
    lay = layer(tree, "10 • Пыль", rough=0.35, amount=0.6)
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_редкая_01.png", 30.0, "Пыль — 30 мм", 0.3, 0.8)
    lay = layer(tree, "12 • Тонкие царапины", rough=0.18, amount=0.5)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 25.0, "Царапины — 25 мм", 0.6, 0.9)
    H.reconnect(U, tree)
    return tree


def matte_black(material: str, label: str):
    tree = make_stack(material, label)
    layer(tree, "00 • Чернёная сетка", (0.008, 0.008, 0.008), 0.0, 0.62)
    H.reconnect(U, tree)
    return tree


def lacquered_case(material: str, label: str):
    """Гильза: стальная лакированная (серо-оливковый лак, как на образце); лак протёрт на закраине и корпусе,
    пятна потемнения, продольные риски от обоймы и магазина."""
    tree = make_stack(material, label)
    layer(tree, "00 • Сталь под серо-оливковым лаком", (0.085, 0.082, 0.062), 0.8, 0.36)
    layer(tree, "02 • Микрофактура", height="source", source="NOISE", scale=6000.0, distance=0.00001)
    lay = layer(tree, "04 • Лак неровный — тон пятнами", (0.065, 0.06, 0.04), 0.7, 0.42, amount=0.6)
    noise(lay, "Пятна 1 см", 90.0, 0.4, 0.7)
    lay = layer(tree, "10 • Лак протёрт до стали на кромках", (0.36, 0.35, 0.33), 1.0, 0.28, amount=0.85)
    edges(lay, 0.0005, 0.04, 0.12)
    noise(lay, "С перерывами", 900.0, 0.4, 0.58)
    lay = layer(tree, "12 • Продольные риски от обоймы", (0.3, 0.29, 0.27), 1.0, 0.3, amount=0.6)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 40.0, "Риски вдоль — 40 мм", 0.55, 0.88, stretch=(0.2, 1.0, 1.0))
    lay = layer(tree, "14 • Тёмные пятна окисла", (0.05, 0.045, 0.035), 0.6, 0.6, amount=0.5)
    owner_mask(lay, "07_грязь_пыль_масляные пятна_вокруг_болтов и других крепежей/Кольцевые_пятна_редкие_01.png",
               35.0, "Пятна — 35 мм", 0.3, 0.75)
    grime(tree, 0.6, ao=0.0015, scale=2500.0)
    H.reconnect(U, tree)
    return tree


def copper_metal(material: str, label: str, base: tuple, dark: tuple):
    """Томпаковая оболочка пули и капсюль: медный металл, потускнение пятнами, светлые кромки."""
    tree = make_stack(material, label)
    layer(tree, "00 • Медный сплав", base, 1.0, 0.3)
    layer(tree, "02 • Микрофактура", height="source", source="NOISE", scale=7000.0, distance=0.000008)
    lay = layer(tree, "04 • Потускнение пятнами", dark, 1.0, 0.5, amount=0.6)
    noise(lay, "Пятна 5 мм", 200.0, 0.4, 0.72)
    lay = layer(tree, "10 • Кромки светлее", tuple(min(c * 1.25, 1.0) for c in base), 1.0, 0.22, amount=0.6)
    edges(lay, 0.0003, 0.04, 0.12)
    grime(tree, 0.5, ao=0.001, scale=3000.0)
    H.reconnect(U, tree)
    return tree


def clip_steel(material: str, label: str):
    """Обойма: штампованная тёмная сталь; кромки и язычки вытерты до светлой стали, бурый налёт в сгибах."""
    tree = make_stack(material, label)
    layer(tree, "00 • Тёмная сталь (воронение)", (0.045, 0.045, 0.047), 1.0, 0.45)
    layer(tree, "02 • Микрофактура", height="source", source="NOISE", scale=5000.0, distance=0.000015)
    lay = layer(tree, "04 • Вытерто пятнами", (0.10, 0.096, 0.092), 1.0, 0.42, amount=0.6)
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png", 60.0, "Потёртости — 60 мм", 0.0, 0.7)
    lay = layer(tree, "10 • Кромки до светлой стали", (0.34, 0.33, 0.32), 1.0, 0.28, amount=0.9)
    edges(lay, 0.0004, 0.04, 0.12)
    noise(lay, "С перерывами", 400.0, 0.38, 0.56)
    lay = layer(tree, "12 • Бурый налёт в сгибах", P["rust"], 0.2, 0.8, amount=0.75)
    ao_inv(lay, "Сгибы и щели", 0.002)
    noise(lay, "Пятнами", 300.0, 0.35, 0.65)
    grime(tree, 0.7, ao=0.002, scale=1800.0)
    H.reconnect(U, tree)
    return tree


# ---------------------------------------------------------------- сборка модели
def load_model(model: str):
    native()
    src = APPROVED / MODELS[model][0]
    bpy.ops.wm.open_mainfile(filepath=str(src))
    unwrap()
    if model == "rifle":
        rifle_masks()
        trees = [blued_steel("Steel_Blued", "Claude • Воронёная сталь • 20 %"),
                 bright_steel("Steel_Bright", "Claude • Светлая сталь затвора • 20 %"),
                 wood_stock("Wood_Stock", "Claude • Ложа и накладка • 20 %")]
    elif model == "scope":
        part_masks({"Scope_Body": 0.7, "Scope_TurretElev_Cap": 1.0, "Scope_TurretWind_Cap": 1.0,
                    "Scope_TurretElev_Boss": 0.8, "Scope_TurretWind_Boss": 0.8}, 0.7)
        trees = [black_paint("Scope_Body", "Claude • Эмаль прицела ПУ • 20 %"),
                 lens_glass("Glass_Lens", "Claude • Стёкла прицела • 20 %"),
                 matte_black("Reticle_Black", "Claude • Сетка прицела"),
                 bright_steel("Steel_Bright", "Claude • Шкалы маховичков • 20 %")]
    elif model == "mount":
        part_masks({"Mount_LockScrew": 1.0, "Mount_Bracket": 0.85, "Mount_Base": 0.7}, 0.75, ("Mount_Base",))
        trees = [blued_steel("Steel_Blued", "Claude • Воронёная сталь крепления • 20 %")]
    elif model == "cartridge":
        part_masks({}, 0.5)
        trees = [lacquered_case("Case_Steel_Lacquer", "Claude • Гильза — лакированная сталь"),
                 copper_metal("Bullet_Jacket", "Claude • Оболочка пули — томпак", (0.55, 0.27, 0.15), (0.24, 0.11, 0.06)),
                 copper_metal("Primer_Brass", "Claude • Капсюль", (0.52, 0.33, 0.16), (0.22, 0.13, 0.06))]
    elif model == "clip":
        part_masks({}, 0.6)
        trees = [clip_steel("Clip_Steel", "Claude • Обойма — тёмная сталь")]
    else:
        raise SystemExit(f"модель {model}: неизвестна")
    return trees


# ---------------------------------------------------------------- рендер
def studio(kind: str, centre: Vector, size: float) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(os.environ.get("MOSIN_SAMPLES", "64"))
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for dev in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = dev
                prefs.get_devices()
                if any(d.type == dev for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    break
            except TypeError:
                continue
    except Exception as exc:
        print("TEX gpu off:", exc, flush=True)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Base Contrast"
    scene.view_settings.exposure = float(os.environ.get("MOSIN_EXPOSURE", "0.0"))
    # отражения и мягкий свет — студийная HDRI (как у Sketchfab), фон для камеры — чёрный (образец) или светлый
    world = bpy.data.worlds.new("Студия")
    world.use_nodes = True
    wt = world.node_tree
    env = wt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(ASSET / "textures/hdri/studio_small_09_2k.hdr"), check_existing=True)
    hdri = wt.nodes["Background"]
    hdri.inputs[1].default_value = float(os.environ.get("MOSIN_HDRI", "0.9"))
    wt.links.new(env.outputs["Color"], hdri.inputs["Color"])
    flat = wt.nodes.new("ShaderNodeBackground")
    bg = 0.0 if kind == "sample" else 0.42
    flat.inputs[0].default_value = (bg, bg, bg, 1.0)
    path = wt.nodes.new("ShaderNodeLightPath")
    mix = wt.nodes.new("ShaderNodeMixShader")
    wt.links.new(path.outputs["Is Camera Ray"], mix.inputs[0])
    wt.links.new(hdri.outputs[0], mix.inputs[1])
    wt.links.new(flat.outputs[0], mix.inputs[2])
    out = wt.nodes["World Output"]
    wt.links.new(mix.outputs[0], out.inputs["Surface"])
    scene.world = world

    def area(name: str, d: tuple, sz: float, energy: float) -> None:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.size = sz * size
        light.data.energy = energy * size * size
        loc = centre + Vector(d).normalized() * size * 1.6
        z = (loc - centre).normalized()
        x = Vector((0, 0, 1)).cross(z).normalized() if abs(z.z) < 0.99 else Vector((1, 0, 0))
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = loc
        light.matrix_world = m
        scene.collection.objects.link(light)
    # как на образце: мягкий верхний ключ спереди-слева, заполнение у камеры, контур сзади
    k = float(os.environ.get("MOSIN_LIGHTS", "0.45"))
    area("Ключ", (0.35, -0.55, 1.0), 1.4, 420.0 * k)
    area("Заполнение", (-0.6, -1.0, 0.25), 1.6, 110.0 * k)
    area("Контур", (0.2, 1.0, 0.6), 1.0, 160.0 * k)


def shoot(name: str, target: Vector, offset: Vector, lens: float, res=(1600, 900)) -> None:
    only = [s for s in os.environ.get("MOSIN_SHOTS", "").split(",") if s]
    if only and not any(name.startswith(s) for s in only):
        return
    scene = bpy.context.scene
    cam = scene.camera
    if cam is None:
        cam = bpy.data.objects.new("Камера", bpy.data.cameras.new("Камера"))
        cam.data.clip_start = 0.005
        scene.collection.objects.link(cam)
        scene.camera = cam
    cam.data.lens = lens
    z = offset.normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = target + offset
    cam.matrix_world = m
    scene.render.resolution_x, scene.render.resolution_y = res
    VIEW.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(VIEW / f"{MODEL}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("TEX shot", name, flush=True)


def shots(model: str) -> None:
    kind = os.environ.get("MOSIN_STUDIO", "sample")
    if model == "rifle":
        c = Vector((-40.0, 0.0, -10.0)) * MM
        studio(kind, c, 0.9)
        # как на превью образца: справа спереди сверху, коробка в центре
        shoot("01_kak_obrazec", c + Vector((0.08, 0.0, 0.0)), Vector((-0.36, -0.40, 0.17)), 42.0)
        shoot("02_korobka_sprava", Vector((-90, 0, 0)) * MM, Vector((0.10, -0.32, 0.12)), 60.0)
        shoot("03_sheyka_i_skoba", Vector((-210, 0, -40)) * MM, Vector((0.05, -0.36, 0.10)), 55.0)
        shoot("04_stvol_kazennik", Vector((60, 0, 5)) * MM, Vector((0.06, -0.22, 0.16)), 60.0)
        shoot("05_priklad", Vector((-400, 0, -80)) * MM, Vector((0.12, -0.55, 0.12)), 50.0)
        shoot("07_kak_skrin_rukoyat", Vector((-95, -12, 2)) * MM, Vector((-0.10, -0.17, 0.20)), 50.0, (1600, 1030))
        shoot("06_vsya_sprava", Vector((110, 0, -40)) * MM, Vector((0.0, -1.9, 0.12)), 35.0, (2000, 700))
    elif model == "assembly":
        c = Vector((-40.0, 0.0, -10.0)) * MM
        studio(kind, c, 0.9)
        shoot("01_kak_obrazec", c + Vector((0.08, 0.0, 0.03)), Vector((-0.40, -0.44, 0.22)), 40.0)
        shoot("02_pricel_sleva", Vector((-100, 15, 35)) * MM, Vector((0.12, 0.40, 0.16)), 50.0)
        shoot("03_vsya_sprava", Vector((110, 0, -30)) * MM, Vector((0.0, -1.9, 0.12)), 35.0, (2000, 760))
        shoot("04_vsya_sleva", Vector((110, 0, -30)) * MM, Vector((0.0, 1.9, 0.12)), 35.0, (2000, 760))
    elif model == "scope":
        c = Vector((85.0, 0.0, 0.0)) * MM
        studio(kind, c, 0.25)
        shoot("01_sleva_34", c, Vector((-0.10, 0.22, 0.10)), 50.0)
        shoot("02_sprava_34", c, Vector((0.12, -0.22, 0.12)), 50.0)
        shoot("03_okulyar", Vector((0, 0, 0)), Vector((-0.12, 0.05, 0.05)), 60.0)
        shoot("04_mahovichki", Vector((87, 5, 8)) * MM, Vector((0.02, 0.08, 0.09)), 60.0)
    elif model == "mount":
        c = Vector((-70.0, 12.0, 30.0)) * MM
        studio(kind, c, 0.25)
        shoot("01_sleva_34", c, Vector((0.12, 0.25, 0.12)), 50.0)
        shoot("02_speredi_sverhu", c, Vector((0.22, 0.08, 0.2)), 50.0)
    elif model == "cartridge":
        c = Vector((38.0, 0.0, 0.0)) * MM
        studio(kind, c, 0.12)
        shoot("01_34", c, Vector((0.04, -0.12, 0.05)), 70.0)
        shoot("02_dno", Vector((0, 0, 0)), Vector((-0.06, -0.04, 0.03)), 80.0)
    elif model == "clip":
        c = Vector((7.0, 0.0, 0.0)) * MM
        studio(kind, c, 0.12)
        shoot("01_34", c, Vector((0.08, -0.08, 0.06)), 70.0)
        shoot("02_bok", c, Vector((0.0, -0.14, 0.02)), 70.0)


def inspect() -> None:
    """Проверка сохранённого файла: нативные стеки, значения слоёв совпадают с фактическими входами групп,
    стек подключён к Principled, все картинки встроены."""
    native()
    path = ASSET / MODELS[MODEL][1]
    bpy.ops.wm.open_mainfile(filepath=str(path))
    report: dict = {"file": path.name, "ucupaint": U.common.get_current_version_str(), "stacks": {}}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        group = next((n for n in mat.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
                      and n.node_tree.yp.is_ypaint_node), None)
        if group is None:
            continue
        tree = group.node_tree
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        wired = {name: bool(bsdf.inputs[name].links) and bsdf.inputs[name].links[0].from_node == group
                 for name in ("Base Color", "Metallic", "Roughness", "Normal")}
        layers = []
        for lay in tree.yp.layers:
            actual = U.common.get_entity_prop_value(lay, "intensity_value")
            assert abs(actual - lay.intensity_value) < 1e-6, (lay.name, actual, lay.intensity_value)
            layers.append({"name": lay.name, "type": lay.type, "enabled": lay.enable, "intensity": round(lay.intensity_value, 3),
                           "channels": [root.name for root, ch in zip(tree.yp.channels, lay.channels) if ch.enable],
                           "masks": [{"name": m.name, "type": m.type, "modifiers": [mod.type for mod in m.modifiers]} for m in lay.masks]})
        assert all(wired.values()), (mat.name, wired)
        report["stacks"][mat.name] = {"tree": tree.name, "wired_to_bsdf": wired, "layers": layers}
    images = [{"name": im.name, "packed": im.packed_file is not None, "size": list(im.size),
               "colorspace": im.colorspace_settings.name} for im in bpy.data.images if im.type == "IMAGE" and im.size[0] > 0]
    assert all(i["packed"] for i in images), [i for i in images if not i["packed"]]
    report["images"] = images
    CHECKS.mkdir(exist_ok=True)
    (CHECKS / f"ucupaint_{MODEL}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TEX inspect ok:", MODEL, "стеков", len(report["stacks"]), "слоёв",
          sum(len(v["layers"]) for v in report["stacks"].values()), "картинок", len(images), flush=True)


def main() -> None:
    if MODE in ("look", "build"):
        trees = load_model(MODEL)
        for tree in trees:
            print("TEX stack", tree.name, "layers", len(tree.yp.layers), flush=True)
        if MODE == "build":
            out = ASSET / MODELS[MODEL][1]
            bpy.ops.file.pack_all()
            bpy.ops.wm.save_as_mainfile(filepath=str(out))
            print("TEX saved", out, flush=True)
            return
        shots(MODEL)
    elif MODE == "inspect":
        inspect()
    elif MODE == "render":
        bpy.ops.wm.open_mainfile(filepath=str(ASSET / MODELS[MODEL][1]))
        shots(MODEL)
    print("TEX done", flush=True)


main()
