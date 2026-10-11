"""Текстурирование ракетницы Claude: нативные слои UCUPaint на принятой геометрии v02 (форма не меняется).

Образец вида — две картинки владельца (_asset_src/flare_gun_claude/refs/tex_ref_01/02.webp): ярко-красная матовая
эмаль с шагренью, сколы до тёмной стали по кромкам, редкие царапины и сколы на плоскостях, голая сталь с пятнами
на курке, спуске и осях, чёрная зернистая накладка, грязь в углублениях.

Источник — замороженная принятая копия approved/FlareGun_Claude_v02_game_APPROVED.blend. Вершины, топология,
иерархия и оси не трогаются; добавляются только цветовые атрибуты-маски (Wear_Contact, Wear_Muzzle, Wear_Bore).
Слои — настоящие группы UCUPaint 2.4.9 (Color / Metallic / Roughness / Normal), всё правится в Blender.
Маски-картинки свои: tools/flare_gun_claude_wear_masks.py (сначала запустить его).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/texture_flare_gun_claude.py -- build | render | inspect
  build   → _asset_src/flare_gun_claude/FlareGun_Claude_v02_ucupaint_worn_v01.blend
  render  → _asset_src/flare_gun_claude/Просмотр_текстуры/*.png (FLARE_SHOTS=01,05 — только эти кадры)
  inspect → checks/ucupaint_stack.json: стеки, слои, маски, сверка значений с фактическими входами групп
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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
APPROVED = SRC / "approved/FlareGun_Claude_v02_game_APPROVED.blend"
MASTER = SRC / "FlareGun_Claude_v02_ucupaint_worn_v01.blend"
TEX = SRC / "textures/worn_v01"
VIEW = SRC / "Просмотр_текстуры"
CHECKS = SRC / "checks"
SKILL = Path("C:/Users/Schecter_8ght/.claude/skills/weapon-asset-texturing")
PROF = json.loads((SRC / "trace/profiles.json").read_text(encoding="utf-8"))
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "build"
UV = "UVMap"
MM = 0.001
U0, V0 = -62.0, -57.0                       # те же оси чертежа, что в build_flare_gun_claude.py
R_OUT, R_BORE = 14.0, 10.3
LEN = float(PROF["muzzle_u"])
U = H = None

# линейные цвета оснований и покрытий
RED = (0.52, 0.013, 0.012)
PRIMER = (0.04, 0.034, 0.03)
STEEL = (0.17, 0.175, 0.185)                # сталь под краской: потемневшая, не зеркало
STEEL_FRESH = (0.5, 0.51, 0.52)             # свежая зарубка
STEEL_DARK = (0.15, 0.155, 0.165)
GRIME = (0.03, 0.022, 0.015)


def P(u: float, v: float, x: float = 0.0) -> Vector:
    return Vector((x * MM, -(u - U0) * MM, (v - V0) * MM))


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


# ---------------------------------------------------------------- маски по геометрии (цветовые атрибуты)

def paint_masks() -> None:
    """Где предмет трут: спинка и пятка рукоятки, скоба, низ коробки, дульная часть; дульный срез; канал ствола.
    Форма не меняется — пишутся только цветовые атрибуты на углах граней."""
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        me = ob.data
        n = len(me.loops)
        contact, muzzle, bore = (np.zeros(n, np.float32) for _ in range(3))
        if ob.name in ("Frame", "Barrel"):
            co = np.empty(len(me.vertices) * 3, np.float32)
            me.vertices.foreach_get("co", co)
            mw = np.array(ob.matrix_world, np.float32)
            world = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
            idx = np.empty(n, np.int32)
            me.loops.foreach_get("vertex_index", idx)
            w = world[idx] * 1000.0
            x, u, v = w[:, 0], U0 - w[:, 1], V0 + w[:, 2]
            pn = np.empty(len(me.polygons) * 3, np.float32)
            me.polygons.foreach_get("normal", pn)
            total = np.empty(len(me.polygons), np.int32)
            me.polygons.foreach_get("loop_total", total)
            nrm = np.repeat(pn.reshape(-1, 3) @ mw[:3, :3].T, total, axis=0)
            if ob.name == "Frame":
                side = np.abs(nrm[:, 0])                             # 1 — боковая плоскость, 0 — торцевая лента рамы
                band = np.clip(1.0 - side * 1.2, 0.0, 1.0)
                shoulder = np.where(u < -30.0, np.clip(1.0 - np.abs(side - 0.6) / 0.4, 0.0, 1.0) * 0.35, 0.0)
                region = np.where(u < -26.0, 1.0, np.where((v < -41.0) & (u < 24.0), 0.7, np.where(v < -34.0, 0.4, np.where(u > 50.0, 0.45, 0.2))))
                contact = np.clip((band + shoulder) * region, 0.0, 1.0)
            else:
                r = np.hypot(x, v)
                radial = (x * nrm[:, 0] + v * nrm[:, 2]) / np.maximum(r, 1e-6)
                forward = -nrm[:, 1]
                bore = (((r < R_BORE + 1.3) & (radial < -0.5)) | ((r < 11.6) & (u < 2.3))).astype(np.float32)
                muzzle = (((u > LEN - 0.05) & (forward > 0.5)) | ((u > LEN - 1.5) & (forward > 0.25))).astype(np.float32)
                outer = (radial > 0.5) & (r > R_OUT - 0.4)
                contact = np.where(outer, np.clip(1.0 - (LEN - u) / 9.0, 0.0, 1.0) * 0.8, 0.0)
                contact = np.maximum(contact, np.where((v > 14.6) & (nrm[:, 2] > 0.7), 0.35, 0.0))
                contact = np.where(bore > 0, 0.0, contact)
        for name, arr in (("Wear_Contact", contact), ("Wear_Muzzle", muzzle), ("Wear_Bore", bore)):
            attr = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="CORNER")
            rgba = np.ones((n, 4), np.float32)
            rgba[:, :3] = arr.astype(np.float32)[:, None]
            attr.data.foreach_set("color", rgba.ravel())
        me.update()


# ---------------------------------------------------------------- UCUPaint: стек, слой, маски

def make_stack(material_name: str, label: str):
    mat = bpy.data.materials[material_name]
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and mat in list(o.data.materials))
    activate(ob, list(ob.data.materials).index(mat))
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    for node in list(nt.nodes):                                      # узлы-заглушки проверки формы больше не нужны
        if node.type in ("TEX_NOISE", "BUMP"):
            nt.nodes.remove(node)
    for link in list(bsdf.inputs["Normal"].links):
        nt.links.remove(link)
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=label, color=True, metallic=True, roughness=True, normal=True, ao=False,
                                         switch_to_material_view=False, target_bsdf_name=bsdf.name)
    group = next(n for n in nt.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    normal.enable_smooth_bump = False
    normal.main_uv = UV
    bevel = next((n for n in nt.nodes if n.type == "BEVEL"), None)   # скругление мелких кромок — базовая нормаль под слоями
    if bevel is not None and "Normal" in group.inputs:
        nt.links.new(bevel.outputs["Normal"], group.inputs["Normal"])
    group.label = label
    mat["authoring"] = "Нативный UCUPaint 2.4.9; Claude; образец износа — картинки владельца"
    return tree


def layer(tree, name: str, color=None, metal=None, rough=None, height=None, source: str = "COLOR", scale: float = 0.0,
          amount: float = 1.0, distance: float = 0.00003, detail: float = 2.0):
    """Слой наверх стека. color/metal/rough — постоянные значения каналов; height: число — постоянная высота
    (0 — утоплено, скол), "source" — рельеф из рисунка источника (шум)."""
    tree.yp.halt_update = True
    result = U.Layer.add_new_layer(tree, name, source, -1, "MIX", "OVERLAY", "BUMP_MAP", "Object", UV,
                                   use_designated_idx=True, designated_index=0)
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


def noise(target, name: str, scale: float, lo: float | None = None, hi: float | None = None, offset: tuple = (0.0, 0.0, 0.0)):
    """Нерегулярность. Порог — внутри самой маски шума: накопленную маску слоя он не режет."""
    result = U.Mask.add_new_mask(target, name, "NOISE", "Object", UV)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = 2.4
    src.inputs["Roughness"].default_value = 0.66
    result.translation = offset
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


def image(target, filename: str, label: str, lo: float | None = None, hi: float | None = None, offset: tuple = (0.0, 0.0, 0.0)):
    """Собственная маска-картинка 200 × 200 мм, объёмной проекцией в настоящем масштабе."""
    img = bpy.data.images.load(str(TEX / filename), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    result = U.Mask.add_new_mask(target, label, "IMAGE", "Object", UV, image=img)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.projection = "BOX"
    src.projection_blend = 0.15
    result.scale = (5.0, 5.0, 5.0)
    result.translation = offset
    if lo is not None:
        ramp(result, lo, hi)
    return result


def dirt(tree, amount: float, color: tuple = GRIME) -> None:
    result = layer(tree, "70 • Грязь в углублениях", color, 0.0, 0.86, amount=amount)
    ao = U.Mask.add_new_mask(result, "Защищённые углы — близость поверхностей", "AO", "Object", UV, ao_distance=0.004, hemi_use_prev_normal=False)
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(ao, "INVERT")
    noise(result, "Отложения неровные", 760.0, 0.28, 0.56, (0.012, 0.031, 0.003))


# ---------------------------------------------------------------- материалы

def body():
    tree = make_stack("FlareGun_Body_Metal", "Claude • Красная эмаль по стали • поношенная")
    layer(tree, "00 • Красная матовая эмаль", RED, 0.0, 0.46)
    layer(tree, "10 • Шагрень краски — 90 мкм", height="source", source="NOISE", scale=2400.0, distance=0.00009)
    lay = layer(tree, "12 • Неровная шероховатость краски", rough=0.62, amount=0.55)
    noise(lay, "Мелкая неравномерность покрытия", 1500.0)
    lay = layer(tree, "14 • Тёмные пятна краски", (0.4, 0.01, 0.01), 0.0, 0.6, amount=0.5)
    image(lay, "stains.png", "Крупные мягкие пятна — 200 мм", 0.45, 0.85)
    lay = layer(tree, "15 • Выгоревшие места", (0.62, 0.03, 0.024), 0.0, 0.58, amount=0.2)
    image(lay, "stains.png", "Пятна со сдвигом — 200 мм", 0.5, 0.9, offset=(0.083, 0.047, 0.061))
    lay = layer(tree, "20 • Тёмный грунт на сбитых кромках", PRIMER, 0.2, 0.6, height=0.0, distance=0.00003, amount=0.9)
    edges(lay, 0.0011, 0.03, 0.1)
    noise(lay, "Край скола рваный", 900.0, 0.5, 0.6, (0.039, 0.012, 0.041))
    lay = layer(tree, "30 • Сталь на кромках — мелкие сколы", STEEL, 1.0, 0.42, height=0.0, distance=0.00005, amount=0.9)
    edges(lay, 0.0008, 0.04, 0.12)
    noise(lay, "Оголено не сплошь", 1000.0, 0.5, 0.58)
    lay = layer(tree, "31 • Свежие зарубки на кромках", STEEL_FRESH, 1.0, 0.26, height=0.0, distance=0.00006, amount=0.85)
    edges(lay, 0.0007, 0.05, 0.14)
    noise(lay, "Редкие точки", 1700.0, 0.6, 0.66, (0.017, 0.063, 0.029))
    lay = layer(tree, "32 • Вытерто рукой и кобурой: спинка, пятка, скоба, дуло", STEEL, 1.0, 0.4, height=0.0, distance=0.00004, amount=0.8)
    vcol(lay, "Wear_Contact", "Где трут — по геометрии")
    noise(lay, "Потёртость пятнами", 520.0, 0.5, 0.66, (0.02, 0.041, 0.013))
    noise(lay, "Пятна рваные", 2200.0, 0.3, 0.62, (0.05, 0.02, 0.07))
    lay = layer(tree, "40 • Царапины до металла", (0.2, 0.205, 0.215), 1.0, 0.42, height=0.0, distance=0.00004, amount=0.85)
    image(lay, "scratches_deep.png", "Редкие длинные царапины — 200 мм")
    lay = layer(tree, "42 • Поверхностные риски по краске", (0.7, 0.07, 0.06), 0.0, 0.7, amount=0.4)
    image(lay, "scratches_fine.png", "Волосяные риски — 200 мм", offset=(0.031, 0.007, 0.019))
    lay = layer(tree, "44 • Мелкие сколы на плоскостях", (0.06, 0.055, 0.05), 0.5, 0.55, height=0.0, distance=0.00005, amount=0.9)
    image(lay, "chips.png", "Россыпь сколов — 200 мм", offset=(0.011, 0.043, 0.027))
    lay = layer(tree, "46 • Дульный срез до металла", (0.3, 0.31, 0.33), 1.0, 0.36, height=0.0, distance=0.00005)
    vcol(lay, "Wear_Muzzle", "Торец и скругление дула")
    noise(lay, "Остатки краски на срезе", 700.0, 0.16, 0.4)
    lay = layer(tree, "48 • Канал ствола: сталь с нагаром", (0.035, 0.03, 0.028), 0.6, 0.7)
    vcol(lay, "Wear_Bore", "Внутренность ствола")
    lay = layer(tree, "50 • Заполировано рукой", rough=0.4, amount=0.35)
    vcol(lay, "Wear_Contact", "Где трут — по геометрии")
    noise(lay, "Хват неравномерный", 60.0, 0.35, 0.65)
    lay = layer(tree, "60 • Пыль в углах и на уступах", (0.3, 0.26, 0.22), 0.0, 0.9, amount=0.12)
    dust = U.Mask.add_new_mask(lay, "Защищённые места", "AO", "Object", UV, ao_distance=0.006, hemi_use_prev_normal=False)
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(dust, "INVERT")
    image(lay, "stains.png", "Пыль лежит пятнами — 200 мм", 0.4, 0.8, offset=(0.02, 0.09, 0.05))
    dirt(tree, 0.8)
    H.reconnect(U, tree)
    return tree


def steel(material_name: str, label: str, base: tuple, rough: float, patina: float):
    tree = make_stack(material_name, label)
    layer(tree, "00 • Сталь, обработанная", base, 1.0, rough)
    layer(tree, "10 • Микрорельеф стали", height="source", source="NOISE", scale=3500.0, distance=0.00003)
    lay = layer(tree, "12 • Пятнистая шероховатость", rough=min(rough + 0.2, 0.8), amount=0.5)
    noise(lay, "Неровность отделки", 1100.0)
    lay = layer(tree, "14 • Раковины и поры", height="source", source="NOISE", scale=1700.0, distance=0.00007, amount=0.8)
    noise(lay, "Поры местами", 600.0, 0.48, 0.62, (0.03, 0.02, 0.05))
    lay = layer(tree, "18 • Тёмные пятна окисла", (0.07, 0.072, 0.078), 1.0, 0.6, amount=patina)
    noise(lay, "Пятна окисла — 3–5 мм", 260.0, 0.42, 0.62, (0.012, 0.054, 0.009))
    lay = layer(tree, "19 • Бурый налёт в порах", (0.11, 0.055, 0.03), 0.3, 0.75, amount=patina * 0.6)
    noise(lay, "Редкие точки налёта", 900.0, 0.56, 0.68, (0.07, 0.01, 0.03))
    lay = layer(tree, "30 • Заполированные кромки", (0.4, 0.41, 0.43), 1.0, 0.28, amount=0.7)
    edges(lay, 0.0007, 0.01, 0.05)
    noise(lay, "Полировка прерывистая", 1100.0, 0.36, 0.5)
    lay = layer(tree, "40 • Волосяные риски", (0.40, 0.41, 0.43), 1.0, 0.33, height=0.0, distance=0.00003, amount=0.7)
    image(lay, "scratches_fine.png", "Риски от носки — 200 мм")
    dirt(tree, 0.4, (0.018, 0.013, 0.01))
    H.reconnect(U, tree)
    return tree


def grip():
    tree = make_stack("FlareGun_Grip_Plastic", "Claude • Чёрный формованный пластик • поношенный")
    layer(tree, "00 • Чёрный пластик", (0.016, 0.016, 0.017), 0.0, 0.6)
    layer(tree, "10 • Зерно «под кожу» — 0.8 мм", height="source", source="NOISE", scale=1500.0, distance=0.00026, detail=1.0)
    layer(tree, "11 • Мелкое зерно пластика", height="source", source="NOISE", scale=5200.0, distance=0.00005)
    lay = layer(tree, "12 • Неровная шероховатость", rough=0.8, amount=0.35)
    noise(lay, "Мелкая неравномерность", 2600.0)
    lay = layer(tree, "30 • Затёртый край накладки", (0.035, 0.036, 0.037), 0.0, 0.42, amount=0.5)
    edges(lay, 0.0006, 0.014, 0.085)
    noise(lay, "Затёрто неровно", 1400.0, 0.3, 0.55)
    lay = layer(tree, "50 • Заполировано ладонью", rough=0.4, amount=0.4)
    noise(lay, "Пятно хвата", 40.0, 0.45, 0.68)
    lay = layer(tree, "60 • Пыль в зерне", (0.2, 0.17, 0.13), 0.0, 0.9, amount=0.32)
    noise(lay, "Пыль в ямках зерна", 3000.0, 0.52, 0.64)
    image(lay, "stains.png", "Пыль лежит пятнами — 200 мм", 0.4, 0.8)
    dirt(tree, 0.3)
    H.reconnect(U, tree)
    return tree


def ammo() -> list:
    trees = []
    tree = make_stack("Flare_Case_Brass", "Claude • Латунь донца")
    layer(tree, "00 • Латунь", (0.55, 0.36, 0.12), 1.0, 0.34)
    layer(tree, "10 • Микрорельеф латуни", height="source", source="NOISE", scale=6000.0, distance=0.00001)
    lay = layer(tree, "20 • Потемнение латуни", (0.16, 0.1, 0.04), 1.0, 0.58, amount=0.3)
    noise(lay, "Пятна окисла", 500.0, 0.4, 0.65)
    lay = layer(tree, "40 • Мелкие следы обращения", (0.6, 0.42, 0.18), 1.0, 0.3, amount=0.35)
    image(lay, "scratches_fine.png", "Риски — 200 мм")
    dirt(tree, 0.3, (0.03, 0.02, 0.01))
    H.reconnect(U, tree)
    trees.append(tree)
    for name, label, color in (("Flare_Hull_Red", "Красная гильза — осветительный", (0.5, 0.012, 0.012)),
                               ("Flare_Hull_Green", "Зелёная гильза — вызов груза", (0.02, 0.22, 0.05))):
        tree = make_stack(name, "Claude • " + label)
        layer(tree, "00 • Пластик гильзы", color, 0.0, 0.45)
        layer(tree, "10 • Микрофактура гильзы", height="source", source="NOISE", scale=5500.0, distance=0.000012)
        lay = layer(tree, "30 • Потёртости от хранения", tuple(min(c * 1.25 + 0.03, 1.0) for c in color), 0.0, 0.7, amount=0.3)
        image(lay, "scratches_fine.png", "Риски — 200 мм")
        dirt(tree, 0.25)
        H.reconnect(U, tree)
        trees.append(tree)
    tree = make_stack("Flare_Wad", "Claude • Картонный пыж")
    layer(tree, "00 • Картон", (0.42, 0.39, 0.32), 0.0, 0.88)
    layer(tree, "10 • Волокно картона", height="source", source="NOISE", scale=4200.0, distance=0.00003)
    lay = layer(tree, "20 • Пятна и потемнение", (0.26, 0.21, 0.14), 0.0, 0.9, amount=0.45)
    image(lay, "stains.png", "Пятна — 200 мм", 0.4, 0.8)
    H.reconnect(U, tree)
    trees.append(tree)
    return trees


def build() -> None:
    native()
    bpy.ops.wm.open_mainfile(filepath=str(APPROVED))
    paint_masks()
    trees = [body(),
             steel("FlareGun_Small_Steel", "Claude • Голая сталь курка, спуска и осей • поношенная", STEEL_DARK, 0.54, 0.7),
             steel("FlareGun_Bright_Steel", "Claude • Сталь защёлок, винта и бойка • поношенная", (0.22, 0.225, 0.235), 0.44, 0.45),
             grip()] + ammo()
    gun = bpy.data.objects["FlareGun_Claude"]
    gun["texture_version"] = "worn_v01; геометрия v02 принята владельцем 2026-10-11"
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    for tree in trees:
        print("TEX stack", tree.name, "layers", len(tree.yp.layers), flush=True)
    print("TEX build done", flush=True)


# ---------------------------------------------------------------- проверка сохранённого файла

def inspect() -> None:
    native()
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    report: dict = {"file": MASTER.name, "ucupaint": U.common.get_current_version_str(), "stacks": {}}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        group = next((n for n in mat.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None) and n.node_tree.yp.is_ypaint_node), None)
        if group is None:
            continue
        tree = group.node_tree
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        wired = {name: bool(bsdf.inputs[name].links) and bsdf.inputs[name].links[0].from_node == group for name in ("Base Color", "Metallic", "Roughness", "Normal")}
        layers = []
        for lay in tree.yp.layers:
            actual = U.common.get_entity_prop_value(lay, "intensity_value")
            assert abs(actual - lay.intensity_value) < 1e-6, (lay.name, actual, lay.intensity_value)
            layers.append({"name": lay.name, "type": lay.type, "enabled": lay.enable, "intensity": round(lay.intensity_value, 3),
                           "channels": [root.name for root, ch in zip(tree.yp.channels, lay.channels) if ch.enable],
                           "masks": [{"name": m.name, "type": m.type, "modifiers": [mod.type for mod in m.modifiers]} for m in lay.masks]})
        assert all(wired.values()), (mat.name, wired)
        report["stacks"][mat.name] = {"tree": tree.name, "wired_to_bsdf": wired, "layers": layers}
    images = [{"name": im.name, "packed": im.packed_file is not None, "size": list(im.size)} for im in bpy.data.images if im.type == "IMAGE" and im.size[0] > 0]
    assert all(i["packed"] for i in images), images
    report["images"] = images
    CHECKS.mkdir(exist_ok=True)
    (CHECKS / "ucupaint_stack.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("TEX inspect ok: стеков", len(report["stacks"]), "слоёв", sum(len(s["layers"]) for s in report["stacks"].values()), "картинок", len(images), flush=True)


# ---------------------------------------------------------------- рендер

def render() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene = bpy.context.scene
    gun = bpy.data.objects["FlareGun_Claude"]
    barrel, hammer = bpy.data.objects["Barrel"], bpy.data.objects["Hammer"]
    red, green = bpy.data.objects["Flare_Red_Claude"], bpy.data.objects["Flare_Green_Claude"]
    cock, open_deg = float(gun["cock_deg"]), float(gun["open_deg"])
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(os.environ.get("FLARE_SAMPLES", "96"))
    scene.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        for kind in ("OPTIX", "CUDA"):
            try:
                prefs.compute_device_type = kind
                prefs.get_devices()
                if any(d.type == kind for d in prefs.devices):
                    for d in prefs.devices:
                        d.use = True
                    scene.cycles.device = "GPU"
                    break
            except TypeError:
                continue
    except Exception as exc:
        print("TEX gpu off:", exc, flush=True)
    k = float(os.environ.get("FLARE_RES", "1.0"))
    scene.render.resolution_x, scene.render.resolution_y = int(1500 * k), int(1500 * k)
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"                  # без приглушения насыщенности: красный остаётся красным
    scene.view_settings.exposure = float(os.environ.get("FLARE_EXPOSURE", "-0.8"))
    world = bpy.data.worlds.new("Студия")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.045, 0.047, 0.05, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 1.0
    scene.world = world
    centre = Vector((0.0, -0.052, 0.012))

    def area(name: str, loc: tuple, size: float, energy: float) -> None:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.size = size
        light.data.energy = energy
        z = (Vector(loc) - centre).normalized()
        x = Vector((0, 0, 1)).cross(z).normalized()
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = Vector(loc)
        light.matrix_world = m
        scene.collection.objects.link(light)

    area("Ключ", (-0.35, -0.45, 0.75), 0.9, 30.0)                    # мягкий верхний свет, как на образцах
    area("Заполнение", (-0.8, 0.3, 0.2), 0.9, 10.0)
    area("Контур", (0.5, 0.55, 0.5), 0.6, 22.0)
    area("Снизу", (-0.1, -0.2, -0.6), 1.0, 4.0)
    cam = bpy.data.objects.new("Камера", bpy.data.cameras.new("Камера"))
    cam.data.clip_start = 0.01
    scene.collection.objects.link(cam)
    scene.camera = cam
    VIEW.mkdir(exist_ok=True)
    only = [s for s in os.environ.get("FLARE_SHOTS", "").split(",") if s]

    def shot(name: str, offset: tuple, target: Vector, ortho: float = 0.0, lens: float = 90.0) -> None:
        if only and not any(name.startswith(s) for s in only):
            return
        off = Vector(offset)
        cam.data.type = "ORTHO" if ortho > 0.0 else "PERSP"
        cam.data.ortho_scale = ortho
        cam.data.lens = lens
        z = off.normalized()
        up = Vector((0, 0, 1)) if abs(z.z) < 0.98 else Vector((1, 0, 0))
        x = up.cross(z).normalized()
        m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
        m.translation = target + off
        cam.matrix_world = m
        scene.render.filepath = str(VIEW / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        print("TEX shot", name, flush=True)

    for ob in (red, green):
        ob.hide_render = True
    shot("01_kak_na_obrazce_speredi", (-0.3, -0.29, 0.14), centre + Vector((0, 0.005, 0.004)), lens=85.0)
    shot("02_kak_na_obrazce_szadi", (-0.36, 0.22, 0.14), centre + Vector((0, 0.0, 0.004)), lens=85.0)
    shot("03_sprava", (-0.6, 0, 0), centre + Vector((0, 0, 0.006)), ortho=0.2)
    shot("04_sleva", (0.6, 0, 0), centre + Vector((0, 0, 0.006)), ortho=0.2)
    shot("05_dulo_krupno", (-0.1, -0.22, 0.07), P(LEN - 12.0, 0.0), lens=100.0)
    shot("06_kurok_i_kazennik", (-0.19, 0.11, 0.13), P(-14.0, 2.0), lens=110.0)
    shot("07_rukoyat_krupno", (-0.26, 0.06, -0.02), P(-62.0, -58.0), lens=110.0)
    shot("08_skoba_i_spusk", (-0.24, -0.1, -0.1), P(0.0, -48.0), lens=110.0)
    shot("09_szadi_sverhu", (0.12, 0.4, 0.34), centre, lens=85.0)
    barrel.rotation_euler = (math.radians(open_deg), 0, 0)
    hammer.rotation_euler = (math.radians(-cock), 0, 0)
    bpy.context.view_layer.update()
    red.hide_render = False
    green.hide_render = False
    chamber = bpy.data.objects["Chamber"]
    red.matrix_world = barrel.matrix_world @ Matrix.Translation(chamber.location + Vector((0.0, 0.026, 0.0)))
    green.matrix_world = Matrix.Translation(Vector((-0.02, -0.118, -0.062))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    shot("10_otkryta_s_patronom", (-0.42, 0.42, 0.3), centre + Vector((0, 0.0, 0.01)), lens=85.0)
    barrel.rotation_euler = (0, 0, 0)
    hammer.rotation_euler = (0, 0, 0)
    for ob in gun.children_recursive:
        ob.hide_render = True
    red.matrix_world = Matrix.Translation(Vector((-0.016, 0.0, 0.0))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    green.matrix_world = Matrix.Translation(Vector((0.016, 0.0, 0.0))) @ Matrix.Rotation(math.radians(-90), 4, "X")
    shot("11_patrony", (-0.13, -0.3, 0.14), Vector((0, 0, 0.03)), lens=100.0)
    print("TEX render done", flush=True)


if MODE == "render":
    render()
elif MODE == "inspect":
    inspect()
else:
    build()
