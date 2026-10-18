"""Текстуры Мосина 1891/30 ПУ, состояние 20 %: нативные слои UCUPaint 2.4.9 на принятой геометрии (форма не меняется).
Винтовка — рецепт v02 (лак с отражениями, полированный затвор, копоть у клейм, отпечатки — см. блок v02), с 2026-10-18
на форме v08 (ход затвора 110 мм, направляющие обоймы, номер на стебле читается нормально) → файл tex20_v03;
прицел, крепление, патрон и обойма — v01.

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
          studio  — в сохранённый файл: свет для Rendered (HDRI, софтбоксы, камера) отдельной коллекцией
Принятые копии формы (не меняются) — models/approved/*.blend, их SHA-256 — checks/approved_SHA256.txt. С 2026-10-18
папка approved в карантине E:/RING_карантин_2026-10-18 (уборка по просьбе владельца) — для перетекстуровки вернуть по пути.
Принятая форма винтовки v08 лежит в models/01_Винтовка (без текстур, SHA-256 там же, в checks/approved_SHA256.txt).
MOSIN_VIEW_DIR — папка для кадров render/look вместо renders/ библиотеки.
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
MASKS = Path("E:/Models Blender/Маски_АЛЬФА")
WOOD = ASSET / "textures/wood"
VIEW = ASSET / "renders/tex20"                       # прицел, крепление, патрон, обойма (v01)
VIEW2 = ASSET / "renders/tex20_v02"                  # винтовка v07 и сборка (v02)
CHECKS = ASSET / "checks"
SKILL = Path("C:/Users/Schecter_8ght/.claude/skills/weapon-asset-texturing")
UV = "UVMap"
MM = 0.001

MODELS = {
    # исходная форма (от папки библиотеки) → файл с текстурами. Винтовка: v03 — рецепт v02 на форме v08 (принята
    # 2026-10-18); прежние v02 (форма v07) и v01 (форма v06) этим скриптом больше не пишутся
    "rifle": ("models/01_Винтовка/Mosin_9130PU_Rifle_v08.blend", "models/01_Винтовка/Mosin_9130PU_Rifle_v08_tex20_v03.blend"),
    "scope": ("models/approved/Mosin_PU_Scope_v01.blend", "models/02_Прицел/Mosin_PU_Scope_v01_tex20_v01.blend"),
    "mount": ("models/approved/Mosin_PU_Mount_v01.blend", "models/03_Крепление/Mosin_PU_Mount_v01_tex20_v01.blend"),
    "cartridge": ("models/approved/Mosin_Cartridge_762x54R_v01.blend",
                  "models/04_Патрон/Mosin_Cartridge_762x54R_v01_tex_v01.blend"),
    "clip": ("models/approved/Mosin_StripperClip_v01.blend", "models/05_Обойма/Mosin_StripperClip_v01_tex_v01.blend"),
    "assembly": (None, "models/00_Сборка/Mosin_9130PU_Assembly_tex20_v03.blend"),   # только render
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
    skip = [p for p in os.environ.get("MOSIN_SKIP", "").split(",") if p]      # проба: выключить слои по номеру
    if any(name.startswith(p + " ") for p in skip):
        result.enable = False
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
    "Bolt_Knob": 1.0, "Bolt_FiringPin_End": 0.7, "Bolt_Extractor": 0.6, "Bolt_ConnectingBar": 0.5,
    "Bolt_FiringPin": 0.4, "Stock_CrossScrew": 0.7,
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


# ---------------------------------------------------------------- v02 (винтовка v07): доводка 20 % по замечаниям владельца 2026-10-17
# Дерево: целый лак глянцевый (чёткие отражения), местами истончён и стёрт до сухого дерева, грязь в порах и у металла,
# хорошо видные царапины сквозь лак и тонкие царапины в самом лаке; затвор полированный, слегка потрёпанный; вокруг клейм
# копоть, в буквах и прорезях грязь; отпечатки пальцев и ладоней — отдельными штампами там, где берут руками.
WOOD8K = ASSET / "textures/src/polyhaven_dark_wood_8k"
GEN = ASSET / "textures/gen"                         # синтетические маски (gen_wood_scratches.py)
WOOD_SCALE = (1.0 / 1.0, 1.0 / 0.5, 1.0 / 0.5)        # плитка 1 м вдоль ложи, 0,5 м поперёк (как в v01)
FAR = 5.0                                              # координата вне [0, 1]: обрезанная (CLIP) маска там пуста

P2 = {
    "bolt": (0.27, 0.27, 0.28),            # полированная сталь затвора: светлая, но не хром (образец темнее)
    "bolt_haze": (0.13, 0.125, 0.12),      # потускнение плёнкой окисла и масла
    "bolt_warm": (0.30, 0.27, 0.23),       # тёплый налёт (пот, старое масло)
    "lacquer_tint": (0.030, 0.011, 0.007), # шеллак/лак — тёмный красно-коричневый тон образца
    "wood_bare": (0.055, 0.027, 0.017),    # дерево без лака — светлее основы, суше и глуше
    "wood_bare_dirty": (0.020, 0.010, 0.0065),
    "wood_scratch": (0.11, 0.06, 0.035),   # царапина сквозь лак до светлого волокна (не белая)
    "pore_dirt": (0.012, 0.007, 0.005),
    "soot": (0.007, 0.0065, 0.006),        # копоть
    "print_oil": (0.03, 0.025, 0.02),
}


def chan_intensity(lay, channel: str, value: float) -> None:
    """Сила отдельного канала слоя (например, отпечаток: шероховатость полностью, цвет — слегка)."""
    for root, ch in zip(lay.id_data.yp.channels, lay.channels):
        if root.name == channel:
            H.sync_property(U, ch, "intensity_value", value)


def image_mask(target, path: Path, label: str, scale=(1.0, 1.0, 1.0), blend: float = 0.2, lo=None, hi=None,
               invert: bool = False, colorspace: str = "Non-Color"):
    """Маска-картинка объёмной проекцией с явным масштабом (раз на метр по осям X, Y, Z)."""
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = colorspace
    result = U.Mask.add_new_mask(target, label, "IMAGE", "Object", UV, image=img)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.projection = "BOX"
    src.projection_blend = blend
    src.extension = "REPEAT"
    result.enable_uniform_scale = False
    U.common.set_entity_prop_value(result, "scale", Vector(scale))
    if invert:
        importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(result, "INVERT")
    if lo is not None:
        ramp(result, lo, hi)
    return result


def stamp_mask(target, rel: str, label: str, centre_mm, size_mm: float, angle_deg: float, axis: str,
               lo: float = 0.12, hi: float = 0.8, stretch: float = 1.0):
    """Один штамп (отпечаток) из Маски_АЛЬФА в точке centre_mm детали: проекция вдоль оси axis (X/Y/Z), картинка
    size_mm в поперечнике, поворот angle_deg вокруг оси проекции, вне картинки пусто (CLIP). Проекции по другим осям
    уходят за картинку — на гранях, повёрнутых от оси, штамп плавно сходит на нет."""
    from mathutils import Euler
    img = bpy.data.images.load(str(rel if isinstance(rel, Path) else MASKS / rel), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    result = U.Mask.add_new_mask(target, label, "IMAGE", "Object", UV, image=img)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.projection = "BOX"
    src.projection_blend = 0.3
    src.extension = "CLIP"
    s = 1.0 / (size_mm * MM)
    a = math.radians(angle_deg)
    k = {"X": 0, "Y": 1, "Z": 2}[axis]
    scale = [s, s, s]
    scale[k] = 0.0
    scale[(k + 1) % 3] *= stretch                        # вытянуть мазок вдоль одной из осей картинки
    rot = [0.0, 0.0, 0.0]
    rot[k] = a
    centre = [0.5, 0.5, 0.5]
    centre[k] = FAR
    p = Vector(centre_mm) * MM
    scaled = Vector((p.x * scale[0], p.y * scale[1], p.z * scale[2]))
    t = Vector(centre) - Euler(rot, "XYZ").to_matrix() @ scaled
    result.enable_uniform_scale = False
    U.common.set_entity_prop_value(result, "scale", Vector(scale))
    U.common.set_entity_prop_value(result, "rotation", Vector(rot))
    U.common.set_entity_prop_value(result, "translation", t)
    ramp(result, lo, hi)
    return result


def print_layer(tree, name: str, rel: str, centre_mm, size_mm: float, angle_deg: float, axis: str, facing: str,
                rough: float = 0.32, darken: float = 0.12, amount: float = 1.0, lo: float = 0.12, hi: float = 0.8,
                stretch: float = 1.0):
    """Отпечаток: жир меняет шероховатость (на глянце — матовое пятно, на сухом — блестящее), цвет — чуть темнее."""
    debug = os.environ.get("MOSIN_DEBUG_PRINTS") == "1"          # проба: где легли штампы (красным)
    lay = layer(tree, name, (1.0, 0.0, 0.0) if debug else P2["print_oil"], None, rough, amount=amount)
    chan_intensity(lay, "Color", 1.0 if debug else darken)
    stamp_mask(lay, rel, "Штамп — " + rel.split("/")[-1], centre_mm, size_mm, angle_deg, axis, lo, hi, stretch)
    vcol(lay, facing, "Только грани, обращённые туда")
    return lay


def cavity_grime(tree, amount: float, distance: float = 0.00035) -> None:
    """Грязь в клеймах, рисках шкал, шлицах и мелких прорезях: близость поверхностей в доли миллиметра."""
    dbg = os.environ.get("MOSIN_DEBUG_STAMPS") == "1"           # проба: где маски (зелёный — прорези, синий — копоть)
    lay = layer(tree, "74 • Грязь в буквах клейм и мелких прорезях", (0, 1, 0) if dbg else P["grime"], 0.0, 0.9,
                amount=amount)
    ao_inv(lay, "Мелкие углубления — 0,35 мм", distance)
    noise(lay, "Не равномерно", 2000.0, 0.25, 0.6, (0.013, 0.07, 0.021))


HALOS: dict = {}            # объект → (картинка ореола, центр мм, размер мм, ось проекции); заполняет stamp_halos()


def _blur(a, sigma_px: float):
    """Гауссово размытие через БПФ (в Python Blender нет PIL)."""
    n = a.shape[0]
    f = np.fft.fftfreq(n)
    g = np.exp(-2.0 * (np.pi * sigma_px) ** 2 * (f[:, None] ** 2 + f[None, :] ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * g))


def stamp_halos() -> None:
    """Ореол копоти вокруг клейм по их настоящей форме: дно букв (вершины ниже поверхности) проецируется на плоскость
    (ствол — сверху, номер на гребне — сбоку) и размывается на ~1 мм; картинка → маска-штамп (CLIP) по той же оси.
    Заодно атрибут Stamp_Cavity — дно букв (грязь внутри клейм)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_rifle as R
    bx, br = zip(*R.BARREL_OUT[2:])
    GEN.mkdir(parents=True, exist_ok=True)
    specs = {"Barrel": ((56.0, 0.0, 0.0), 32.0, "Z"), "Bolt_Body": ((-54.0, R.RIB_Y[0], 0.55), 32.0, "Y")}
    for name, (centre, size, axis) in specs.items():
        ob = bpy.data.objects[name]
        me = ob.data
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        v = co.reshape(-1, 3).astype(np.float64) * 1000.0
        if name == "Barrel":
            rr = np.hypot(v[:, 1], v[:, 2]) - np.interp(v[:, 0], bx, br)        # < 0 — ниже наружной поверхности
            cav = (rr < -0.04) & (rr > -0.5) & (v[:, 0] > 40) & (v[:, 0] < 72)   # только буквы, не канал ствола
        else:
            cav = (v[:, 1] > R.RIB_Y[0] + 0.04) & (v[:, 1] < R.RIB_Y[0] + 0.4) & (v[:, 0] > -70) & (v[:, 0] < -38)                   & (np.abs(v[:, 2] - 0.55) < 3.0)
        idx = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", idx)
        write_attr(ob, "Stamp_Cavity", cav[idx].astype(np.float32))
        px = 48.0                                            # пикселей на мм
        n = int(size * px)
        u_ax, v_ax = (0, 1) if axis == "Z" else (0, 2)
        u0, v0 = centre[u_ax] - size / 2, centre[v_ax] - size / 2
        uv = np.stack(((v[:, u_ax] - u0) * px, (v[:, v_ax] - v0) * px), axis=1)   # строки снизу вверх, как в Blender
        me.calc_loop_triangles()
        tri = np.empty(len(me.loop_triangles) * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tri)
        tri = tri.reshape(-1, 3)
        tri = tri[cav[tri].all(axis=1)]
        mask = np.zeros((n, n), np.float64)
        for a, b, c in tri:
            pa, pb, pc = uv[a], uv[b], uv[c]
            x0, x1 = int(max(0, np.floor(min(pa[0], pb[0], pc[0])))), int(min(n - 1, np.ceil(max(pa[0], pb[0], pc[0]))))
            y0, y1 = int(max(0, np.floor(min(pa[1], pb[1], pc[1])))), int(min(n - 1, np.ceil(max(pa[1], pb[1], pc[1]))))
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            d = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
            if abs(d) < 1e-12:
                continue
            l1 = ((pb[1] - pc[1]) * (gx - pc[0]) + (pc[0] - pb[0]) * (gy - pc[1])) / d
            l2 = ((pc[1] - pa[1]) * (gx - pc[0]) + (pa[0] - pc[0]) * (gy - pc[1])) / d
            inside = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
            mask[y0:y1 + 1, x0:x1 + 1] = np.maximum(mask[y0:y1 + 1, x0:x1 + 1], inside)
        core, wide = _blur(mask, 0.35 * px), _blur(mask, 1.1 * px)
        halo = np.clip(np.maximum(core * 1.2, wide * 2.4), 0.0, 1.0).astype(np.float32)
        path = GEN / f"stamp_halo_{name}.png"
        img = bpy.data.images.get(path.name) or bpy.data.images.new(path.name, n, n, alpha=False)
        rgba = np.ones((n, n, 4), np.float32)
        rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = halo
        img.pixels.foreach_set(rgba.ravel())
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()
        HALOS[name] = (path, centre, size, axis)
        me.update()
        print("TEX halo", name, "треугольников букв", len(tri), flush=True)


def stamp_soot(tree, amount: float, names: tuple, film: bool = False) -> None:
    """Копоть и грязь вокруг клейм — ореол по форме букв; внутри букв — тёмная грязь. film — на полированной стали
    копоть тонкой плёнкой: сталь темнеет и тускнеет, но остаётся металлом (матовая грязь там светлеет в бликах)."""
    dbg = os.environ.get("MOSIN_DEBUG_STAMPS") == "1"
    for name in names:
        path, centre, size, axis = HALOS[name]
        soot, metal, rough = ((0.035, 0.033, 0.031), 0.85, 0.36) if film else (P2["soot"], 0.35, 0.6)
        lay = layer(tree, f"76 • Копоть вокруг клейм — {name}", (0, 0, 1) if dbg else soot, metal, rough,
                    amount=amount)
        stamp_mask(lay, path, "Ореол по форме букв", centre, size, 0.0, axis, 0.03, 0.75)
        noise(lay, "Неровно, разводами", 260.0, 0.22, 0.75, (0.04, 0.012, 0.07))
    soot, metal, rough = ((0.035, 0.033, 0.031), 0.85, 0.36) if film else (P2["soot"], 0.35, 0.6)
    lay = layer(tree, "77 • Копоть пятнами у клейм", soot, metal, rough, amount=amount * 0.35)
    vcol(lay, "Stamp_Zone", "Около надписей")
    owner_mask(lay, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 45.0, "Налёт — 45 мм", 0.25, 0.75, (0.031, 0.02, 0.05))
    lay = layer(tree, "78 • Грязь внутри букв клейм", (0, 1, 0) if dbg else (0.004, 0.0037, 0.0034), 0.2, 0.75,
                amount=0.92)
    vcol(lay, "Stamp_Cavity", "Дно букв")


def blued_steel_v2(material: str, label: str):
    tree = blued_steel(material, label)
    cavity_grime(tree, 0.95)
    stamp_soot(tree, 0.85, ("Barrel",))
    H.reconnect(U, tree)
    return tree


def bright_steel_v2(material: str, label: str):
    """Затвор: полированная светлая сталь, продольные риски от хода, тонкие царапины, лёгкое потускнение пятнами,
    кромки заполированы, тёмное масло и грязь в пазах и кулачке, редкие точки окисла в укрытых местах; отпечатки."""
    tree = make_stack(material, label)
    layer(tree, "00 • Сталь полированная", P2["bolt"], 1.0, 0.22)
    layer(tree, "02 • Микрофактура полировки", height="source", source="NOISE", scale=9000.0, distance=0.000006)
    lay = layer(tree, "04 • Блеск неровный — полировка пятнами", rough=0.2, amount=0.6)
    noise(lay, "Пятна 2–4 см", 35.0, 0.4, 0.75)
    lay = layer(tree, "06 • Продольная шлифовка (вдоль хода)", rough=0.18, amount=0.7)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 90.0, "Шлифовка вдоль оси", 0.3, 0.9, stretch=(0.08, 1.0, 1.0))
    lay = layer(tree, "08 • Потускнение плёнкой — пятна 3–6 см", P2["bolt_haze"], 1.0, 0.26, amount=0.55)
    noise(lay, "Пятна потускнения", 20.0, 0.42, 0.8)
    lay = layer(tree, "10 • Тёплый налёт в стороне от хвата", P2["bolt_warm"], 1.0, 0.32, amount=0.3)
    ao_inv(lay, "Укрытые места", 0.004)
    noise(lay, "Неровно", 90.0, 0.4, 0.7)
    lay = layer(tree, "12 • Риски от хода затвора — светлые", (0.62, 0.61, 0.6), 1.0, 0.1, height=0.0, distance=0.000012,
                amount=0.75)
    owner_mask(lay, "09_Царапины/Царапины_длинные_плотные_01.png", 120.0, "Риски вдоль оси", 0.5, 0.85, stretch=(0.15, 1.0, 1.0))
    lay = layer(tree, "14 • Тонкие царапины во все стороны", (0.3, 0.3, 0.3), 1.0, 0.24, height=0.0, distance=0.000008,
                amount=0.55)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 45.0, "Мелкие царапины — 45 мм", 0.5, 0.88, (0.021, 0.011, 0.033))
    lay = layer(tree, "16 • Кромки заполированы до блеска", (0.6, 0.6, 0.6), 1.0, 0.08, amount=0.75)
    edges(lay, 0.0006, 0.03, 0.1)
    noise(lay, "Участками", 160.0, 0.35, 0.58)
    lay = layer(tree, "20 • Точки окисла в укрытых местах", P["rust"], 0.3, 0.8, height=0.0, distance=0.00002, amount=0.5)
    ao_inv(lay, "Укрытые места", 0.003)
    noise(lay, "Редкие точки", 1300.0, 0.66, 0.7, (0.03, 0.08, 0.02))
    lay = layer(tree, "30 • Тёмное масло в пазах и кулачке", (0.03, 0.026, 0.02), 0.0, 0.35, amount=0.75)
    ao_inv(lay, "Пазы и щели", 0.0025)
    noise(lay, "Потёками", 220.0, 0.3, 0.62, (0.04, 0.03, 0.06))
    grime(tree, 0.8, scale=1400.0)
    cavity_grime(tree, 0.95)
    stamp_soot(tree, 0.7, ("Bolt_Body",), film=True)
    # отпечатки (координаты детали = мировые в закрытом затворе; штампы ездят с деталями)
    F = "01_Отпечатки_пальцев/"
    print_layer(tree, "80 • Отпечаток большого пальца на шаре рукояти", F + "Отпечаток_чёткий_01.png",
                (-85.0, -39.0, -48.0), 20.0, 25.0, "Y", "Face_R", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "81 • Отпечаток указательного на шаре спереди", F + "Отпечаток_смазанный_по_диагонали_01.png",
                (-76.0, -30.0, -47.0), 22.0, -40.0, "X", "Face_F", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "82 • Отпечаток на стебле рукояти", F + "Отпечаток_смазанный_вниз_01.png",
                (-85.0, -34.0, -26.0), 22.0, 0.0, "Y", "Face_R", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "83 • Мазок пальца на гребне", F + "Отпечаток_смазанный_вправо_02.png",
                (-76.0, -16.0, 0.6), 22.0, 8.0, "Y", "Face_R", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "84 • Отпечаток на гребне у рукояти", F + "Отпечаток_грязный_02.png",
                (-35.0, -16.0, 0.0), 18.0, 95.0, "Y", "Face_R", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "85 • Большой палец на торце грибка", F + "Отпечаток_растёртый_01.png",
                (-178.0, 0.0, 0.5), 22.0, 15.0, "X", "Face_B", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "86 • Отпечаток на гребне курка", F + "Отпечаток_смазанный_по_диагонали_02.png",
                (-128.0, 0.0, 14.5), 22.0, -70.0, "Z", "Face_U", rough=0.32, darken=0.2, amount=0.85)
    print_layer(tree, "87 • Отпечаток на стебле затвора сверху", F + "Отпечаток_грязный_03.png",
                (-80.0, 2.0, 9.0), 20.0, 80.0, "Z", "Face_U", rough=0.32, darken=0.2, amount=0.85)
    H.reconnect(U, tree)
    return tree


def wood_stock_v2(material: str, label: str):
    """Ложа и накладка: волокно 8K под глянцевым лаком (чёткие отражения); лак местами истончён и стёрт до сухого
    дерева, потемневшего от рук; грязь в порах и у металла; хорошо видные царапины сквозь лак, тонкие царапины лака,
    забоины; отпечатки пальцев и ладоней на шейке и цевье."""
    tree = make_stack(material, label)
    img = bpy.data.images.load(str(WOOD8K / "dark_wood_diff_8k.jpg"), check_existing=True)
    img.colorspace_settings.name = "sRGB"
    lay = layer(tree, "00 • Дерево — Poly Haven Dark Wood 8K (CC0) под лаком", color="source", rough=0.08, metal=0.0,
                source="IMAGE", image=img)
    src = U.common.get_layer_source(lay)
    src.projection = "BOX"
    src.projection_blend = 0.3
    lay.enable_uniform_scale = False
    U.common.set_entity_prop_value(lay, "scale", Vector(WOOD_SCALE))
    ao_img = bpy.data.images.load(str(WOOD8K / "dark_wood_ao_8k.jpg"), check_existing=True)
    ao_img.colorspace_settings.name = "Non-Color"
    lay = layer(tree, "01 • Поры волокна — рельеф под лаком", height="source", source="IMAGE", image=ao_img,
                distance=0.000018)
    src = U.common.get_layer_source(lay)
    src.projection = "BOX"
    src.projection_blend = 0.3
    lay.enable_uniform_scale = False
    U.common.set_entity_prop_value(lay, "scale", Vector(WOOD_SCALE))
    layer(tree, "02 • Тон лака — к образцу (красно-коричневый)", P2["lacquer_tint"], amount=0.62)
    # фото волокна очень рыжее: по замеру образец вдвое темнее в линейных значениях и глуше по насыщенности
    layer(tree, "02b • Темнее и глуше — к образцу (умножение)", (0.55, 0.62, 0.75), blend="MULTIPLY")
    lay = layer(tree, "03 • Грязь в порах волокна", P2["pore_dirt"], 0.0, 0.5, amount=0.7)
    image_mask(lay, WOOD8K / "dark_wood_ao_8k.jpg", "Поры — AO волокна", WOOD_SCALE, 0.3, 0.55, 0.85, invert=True)
    noise(lay, "Местами больше", 14.0, 0.25, 0.75)
    lay = layer(tree, "04 • Лак неровный — блеск пятнами", rough=0.22, amount=0.55)
    noise(lay, "Пятна 2–5 см", 30.0, 0.45, 0.8)
    layer(tree, "05 • Шагрень лака — мелкие волны", height="source", source="NOISE", scale=900.0, distance=0.000006,
          amount=0.6)
    lay = layer(tree, "06 • Тёмные пятна — неровный тон старого дерева", (0.016, 0.007, 0.0045), 0.0, None, amount=0.35)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 220.0, "Пятна — 220 мм", 0.15, 0.7)
    lay = layer(tree, "10 • Лак истончился — полуглянец (хват, щека, низ)", (0.03, 0.013, 0.008), 0.0, 0.45, amount=0.55)
    chan_intensity(lay, "Color", 0.35)
    vcol(lay, "Wood_Wear", "Где держат и трут")
    noise(lay, "Пятнами", 18.0, 0.3, 0.68, (0.07, 0.02, 0.11))
    lay = layer(tree, "12 • Лак стёрт до дерева", P2["wood_bare"], 0.0, 0.62, height=0.0, distance=0.00001, amount=0.85)
    vcol(lay, "Wood_Wear", "Где держат и трут")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png", 260.0, "Потёртости — 260 мм", 0.35, 0.85)
    noise(lay, "Края мягкие", 25.0, 0.3, 0.7)
    lay = layer(tree, "14 • Голое дерево потемнело от рук и грязи", P2["wood_bare_dirty"], 0.0, 0.5, amount=0.55)
    vcol(lay, "Wood_Wear", "Где держат")
    owner_mask(lay, "06_Разводы_и_следы_протирания/" + _first(MASKS / "06_Разводы_и_следы_протирания"), 140.0,
               "Разводы — 140 мм", 0.2, 0.7)
    lay = layer(tree, "16 • Затёртые кромки — лак снят", P2["wood_bare"], 0.0, 0.6, height=0.0, distance=0.00006,
                amount=0.85)
    edges(lay, 0.0016, 0.03, 0.12)
    noise(lay, "С перерывами", 300.0, 0.4, 0.6)
    lay = layer(tree, "20 • Вмятины и забоины", P["wood_dent"], 0.0, 0.62, height=0.0, distance=0.00025, amount=1.0)
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_пятнами_01.png", 150.0, "Забоины — 150 мм", 0.35, 0.75)
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Сколы_с_потёртостями_01.png", 230.0, "Вторая сетка — без повтора",
               0.2, 0.6, (0.073, 0.031, 0.052))
    noise(lay, "Гнёздами — 10–15 см", 7.0, 0.35, 0.7, (0.21, 0.09, 0.04))
    lay = layer(tree, "22 • Царапины сквозь лак — светлое волокно (синтетика)", P2["wood_scratch"], 0.0, 0.55,
                height=0.0, distance=0.00004, amount=0.95)
    image_mask(lay, GEN / "wood_scratches_deep.png", "Царапины — плитка 400 мм", (2.5, 2.5, 2.5), 0.2, 0.12, 0.55)
    noise(lay, "Не везде", 12.0, 0.3, 0.6, (0.13, 0.05, 0.09))
    lay = layer(tree, "24 • Мелкие забоинки с грязью", P["wood_dent"], 0.0, 0.6, height=0.0, distance=0.00004,
                amount=0.55)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 60.0, "Забоинки — 60 мм", 0.72, 0.95, (0.02, 0.05, 0.01))
    lay = layer(tree, "26 • Волосяные царапины в лаке — видны в бликах (синтетика)", (0.08, 0.06, 0.05), 0.0, 0.3,
                amount=0.9)
    chan_intensity(lay, "Color", 0.3)
    image_mask(lay, GEN / "wood_scratches_fine.png", "Волосяные — плитка 250 мм", (4.0, 4.0, 4.0), 0.2, 0.1, 0.5)
    lay = layer(tree, "28 • Потёртости лака о снаряжение (матовые)", rough=0.42, amount=0.6)
    vcol(lay, "Wear_Rest", "Низ приклада")
    owner_mask(lay, "10_Сколы_и_потёртости_покрытия/Потёртости_горизонтальные_01.png", 90.0, "Потёртости — 90 мм", 0.2, 0.7,
               (0.011, 0.043, 0.02))
    lay = layer(tree, "30 • Тёмное масло у металла", (0.022, 0.011, 0.007), 0.0, 0.3, amount=0.6)
    ao_inv(lay, "У стыков с металлом", 0.008)
    noise(lay, "Пятнами", 35.0, 0.4, 0.7)
    lay = layer(tree, "32 • Затемнение хвата — пот и грязь", (0.03, 0.015, 0.009), 0.0, None, amount=0.4)
    vcol(lay, "Wood_Wear", "Где держат")
    noise(lay, "Пятнами", 18.0, 0.45, 0.75)
    dust(tree, 0.14)
    grime(tree, 0.9, ao=0.006, scale=500.0)
    cavity_grime(tree, 0.7, distance=0.0008)
    # отпечатки: правая рука держит шейку (ладонь справа, пальцы обхватывают слева снизу, большой палец сверху),
    # левая — цевьё снизу (пальцы справа в пазу, большой палец слева); щекой — гребень приклада
    F, Pm = "01_Отпечатки_пальцев/", "02_Отпечатки_ладоней/"
    print_layer(tree, "80 • Ладонь на шейке справа (пальцы уходят вниз под шейку)", Pm + "Ладонь_растёртая_01.png",
                (-230.0, -18.0, -44.0), 115.0, 180.0, "Y", "Face_R", rough=0.27, darken=0.2, amount=0.9)
    print_layer(tree, "81 • Основание ладони — шейка справа сзади", Pm + "Ладонь_частичная_01.png", (-258.0, -18.0, -58.0),
                85.0, 160.0, "Y", "Face_R", rough=0.27, darken=0.18, amount=0.8)
    for i, (x, z, a, img) in enumerate(((-214.0, -62.0, 110.0, "Отпечаток_смазанный_вправо_01.png"),
                                       (-228.0, -66.0, 118.0, "Отпечаток_грязный_01.png"),
                                       (-242.0, -68.0, 125.0, "Отпечаток_смазанный_вправо_03.png"))):
        print_layer(tree, f"8{2 + i} • Палец на шейке слева", F + img, (x, 18.0, z), 24.0, a, "Y", "Face_L",
                    rough=0.27, darken=0.18, amount=0.9)
    print_layer(tree, "85 • Большой палец на шейке сверху", F + "Отпечаток_смазанный_по_диагонали_01.png",
                (-226.0, 3.0, -28.0), 26.0, -15.0, "Z", "Face_U", rough=0.27, darken=0.18, amount=0.9)
    for i, (x, img) in enumerate(((38.0, "Отпечаток_смазанный_вниз_01.png"), (57.0, "Отпечаток_грязный_02.png"),
                                  (76.0, "Отпечаток_смазанный_по_диагонали_02.png"))):
        print_layer(tree, f"8{6 + i} • Палец левой руки в пазу цевья справа", F + img, (x, -20.0, -19.0), 22.0, 95.0 + 8 * i,
                    "Y", "Face_R", rough=0.27, darken=0.18, amount=0.9)
    print_layer(tree, "89 • Большой палец на цевье слева", F + "Отпечаток_растёртый_01.png", (66.0, 20.0, -21.0), 26.0,
                -80.0, "Y", "Face_L", rough=0.27, darken=0.18, amount=0.9)
    print_layer(tree, "90 • Ладонь под цевьём", Pm + "Ладонь_смазанная_вправо_01.png", (85.0, 0.0, -44.0), 110.0, 90.0,
                "Z", "Face_D", rough=0.27, darken=0.18, amount=0.9)
    print_layer(tree, "91 • Жирный след щеки на гребне приклада", Pm + "Ладонь_растёртая_01.png", (-385.0, 0.0, -35.0),
                130.0, 90.0, "Z", "Face_U", rough=0.3, darken=0.1, amount=0.55)
    H.reconnect(U, tree)
    return tree


def _first(folder: Path) -> str:
    return sorted(p.name for p in folder.glob("*.png"))[0]


def stamp_zone_and_facing() -> None:
    """Для v02: Stamp_Zone — около клейм (казённая часть ствола сверху, номер на гребне, шкала прицельной планки);
    Face_R/L/U/D/F/B — куда обращена поверхность (по сглаженным нормалям вершин), чтобы отпечатки ложились только
    на свою сторону."""
    for ob in [o for o in bpy.data.objects if o.type == "MESH"]:
        me = ob.data
        w, _ = loops_world(ob)
        vn = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("normal", vn)
        idx = np.empty(len(me.loops), np.int32)
        me.loops.foreach_get("vertex_index", idx)
        mw = np.array(ob.matrix_world, np.float32)[:3, :3]
        n = vn.reshape(-1, 3)[idx] @ mw.T
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        for name, comp in (("Face_R", -n[:, 1]), ("Face_L", n[:, 1]), ("Face_U", n[:, 2]), ("Face_D", -n[:, 2]),
                           ("Face_F", n[:, 0]), ("Face_B", -n[:, 0])):
            write_attr(ob, name, np.clip((comp - 0.2) / 0.45, 0.0, 1.0))
        x, y, z = w[:, 0], w[:, 1], w[:, 2]
        zone = np.zeros_like(x)
        if ob.name == "Barrel":
            zone = smooth_band(x, 40.0, 72.0, 6.0) * np.clip((n[:, 2] - 0.1) / 0.4, 0.0, 1.0)
        elif ob.name == "Bolt_Body":
            zone = smooth_band(x, -68.0, -40.0, 5.0) * np.clip((-y - 14.0) / 1.5, 0.0, 1.0)
        elif ob.name.startswith("RearSight_Leaf"):
            zone = np.clip((n[:, 2] - 0.3) / 0.4, 0.0, 1.0) * 0.8
        write_attr(ob, "Stamp_Zone", zone)
        me.update()
    print("TEX v2 masks done", flush=True)


# ---------------------------------------------------------------- сборка модели
def load_model(model: str):
    native()
    src = ASSET / MODELS[model][0]
    bpy.ops.wm.open_mainfile(filepath=str(src))
    unwrap()
    if model == "rifle":
        rifle_masks()
        stamp_zone_and_facing()
        stamp_halos()
        trees = [blued_steel_v2("Steel_Blued", "Claude • Воронёная сталь • 20 % • v02"),
                 bright_steel_v2("Steel_Bright", "Claude • Полированная сталь затвора • 20 % • v02"),
                 wood_stock_v2("Wood_Stock", "Claude • Ложа и накладка под лаком • 20 % • v02")]
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
def studio(kind: str, centre: Vector, size: float, col=None) -> None:
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
        (col or scene.collection).objects.link(light)
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
    view = Path(os.environ["MOSIN_VIEW_DIR"]) if os.environ.get("MOSIN_VIEW_DIR") else (
        VIEW2 if MODEL in ("rifle", "assembly") else VIEW)
    view.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(view / f"{MODEL}_{name}.png")
    bpy.ops.render.render(write_still=True)
    print("TEX shot", name, flush=True)


def shots(model: str) -> None:
    kind = os.environ.get("MOSIN_STUDIO", "sample")
    saved = bpy.data.collections.get("Студия — свет для просмотра")   # свет просмотра из файла — не удваивать
    if saved:
        for ob in saved.objects:
            if ob.type == "LIGHT":
                ob.hide_render = True
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
        # v02 — крупные планы: лак и отпечатки на шейке, паз цевья, затвор, клейма, номер, царапины приклада
        shoot("08_sheyka_sprava", Vector((-235, -18, -52)) * MM, Vector((0.05, -0.20, 0.07)), 60.0)
        shoot("09_sheyka_sleva", Vector((-232, 18, -55)) * MM, Vector((0.04, 0.20, -0.02)), 60.0)
        shoot("10_cevye_paz", Vector((58, -20, -20)) * MM, Vector((0.06, -0.18, 0.04)), 60.0)
        shoot("11_zatvor", Vector((-80, -20, -10)) * MM, Vector((0.02, -0.17, 0.09)), 70.0)
        shoot("12_kleyma_stvol", Vector((56, 0, 12)) * MM, Vector((-0.03, -0.07, 0.12)), 90.0)
        shoot("13_nomer_greben", Vector((-55, -16, 0.5)) * MM, Vector((0.015, -0.11, 0.05)), 90.0)
        shoot("14_priklad", Vector((-410, -21, -92)) * MM, Vector((0.06, -0.30, 0.05)), 60.0)
        shoot("15_shkala", Vector((150, 0, 22)) * MM, Vector((-0.05, -0.05, 0.12)), 80.0)
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
    tag = "_v03" if MODEL == "rifle" else ""
    (CHECKS / f"ucupaint_{MODEL}{tag}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TEX inspect ok:", MODEL, "стеков", len(report["stacks"]), "слоёв",
          sum(len(v["layers"]) for v in report["stacks"].values()), "картинок", len(images), flush=True)


VIEW_COL = "Студия — свет для просмотра"


def viewing_setup() -> None:
    """Свет для режима Rendered прямо в сохранённом файле (владелец смотрит сам в Blender: без света там темно):
    студийная HDRI (встроена) с серым фоном, три софтбокса и камера «как у образца» — отдельной коллекцией,
    её можно выключить. Отделку не меняет; повторный запуск заменяет прежнюю студию."""
    bpy.context.preferences.use_preferences_save = False
    path = ASSET / MODELS[MODEL][1]
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    old = bpy.data.collections.get(VIEW_COL)
    if old:
        for ob in list(old.objects):
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.collections.remove(old)
    col = bpy.data.collections.new(VIEW_COL)
    scene.collection.children.link(col)
    os.environ.setdefault("MOSIN_EXPOSURE", "-0.2")
    os.environ.setdefault("MOSIN_SAMPLES", "128")
    centre = Vector((-40.0, 0.0, -10.0)) * MM
    studio("light", centre, 0.9, col)
    scene.world.name = "Студия — HDRI studio_small_09 (CC0), фон серый"
    scene.cycles.preview_samples = 64
    scene.cycles.use_preview_denoising = True
    cam = bpy.data.objects.new("Камера — как у образца", bpy.data.cameras.new("Камера — как у образца"))
    cam.data.lens = 42.0 if MODEL == "rifle" else 40.0
    cam.data.clip_start = 0.005
    target = centre + Vector((0.08, 0.0, 0.0 if MODEL == "rifle" else 0.03))
    offset = Vector((-0.36, -0.40, 0.17)) if MODEL == "rifle" else Vector((-0.40, -0.44, 0.22))
    z = offset.normalized()
    x = Vector((0, 0, 1)).cross(z).normalized()
    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
    m.translation = target + offset
    cam.matrix_world = m
    col.objects.link(cam)
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    print("TEX viewing studio saved", path, flush=True)


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
    elif MODE == "studio":
        viewing_setup()
    elif MODE == "render":
        bpy.ops.wm.open_mainfile(filepath=str(ASSET / MODELS[MODEL][1]))
        shots(MODEL)
    print("TEX done", flush=True)


main()
