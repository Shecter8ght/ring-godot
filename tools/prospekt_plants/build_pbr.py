"""Растения «Проспекта» — PBR на принятой форме v01 (нативный UCUPaint 2.4.9), bpy:

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_plants/build_pbr.py -- [birch linden poplar lilac hedge] [preview]

Форма — та же (build_forms.build_kind, принята владельцем 2026-10-25), материалы — стеки UCUPaint:
  кора   — фото CC0 (цвет + нормаль), тон модификатором; по атрибутам вершин: тёмная трещиноватая кора у комля
           (берёза), старая бороздчатая внизу ствола (тополь), мох с севера у земли, почва у самого комля;
  побеги — свой цвет с неровностью; лист — фотолист вида (textures.py: скан ambientCG, переформованный под контур),
           нормаль жилок, разброс тона по листьям (цвет вершин Col), лёгкая городская пыль. Вырез листа — альфа той же
           картинки прямо в материале (канал Alpha UCUPaint 2.4.9 из скрипта не подключается к слоям).
Картинки встроены. → models/NN_<Вид>_PBR_v01.blend, снимки previews/<вид>_pbr_*.png
"""
from __future__ import annotations

import importlib
import importlib.util
import math
import os
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_forms as BF  # noqa: E402
import plib  # noqa: E402
import species as S  # noqa: E402

ROOT = HERE.parents[1]
SKILL = ROOT / "tools/asset_skills/weapon-asset-texturing"
LEAVES = ROOT / "_asset_src/prospekt_plants/leaves"
UV = "UVMap"
VERSION = "v01"
U = None
H = None

# кора по видам: фото (цвет, нормаль), шероховатость, тон (насыщенность, яркость), плитка, м (u, v)
BARK_TEX = {
    "birch": dict(albedo=ROOT / "assets/zone01/textures/birch_bark_albedo.png", normal=ROOT / "assets/zone01/textures/birch_bark_normal.png",
                  rough=0.62, sat=1.0, val=1.0, tile=(1.0, 2.0)),
    "linden": dict(albedo=ROOT / "assets/textures/bark_brown_02/albedo.jpg", normal=ROOT / "assets/textures/bark_brown_02/normal.jpg",
                   rough=0.88, sat=0.6, val=0.92, tile=(1.0, 1.0)),
    "poplar": dict(albedo=ROOT / "_asset_src/prospekt_plants/textures/poplar_bark_young_albedo.png",
                   normal=ROOT / "_asset_src/prospekt_plants/textures/poplar_bark_young_normal.png", rough=0.7, sat=1.0, val=1.0, tile=(1.0, 1.0)),
    "lilac": dict(albedo=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_albedo.png", normal=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_normal.png",
                  rough=0.75, sat=1.0, val=1.0, tile=(0.5, 0.5)),
    "hedge": dict(albedo=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_albedo.png", normal=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_normal.png",
                  rough=0.78, sat=1.15, val=0.8, tile=(0.5, 0.5)),
}
# тонкие ветви: берёза — тёмные буро-серые, остальным — гладкая кора своего вида
BRANCH_TEX = {
    "birch": dict(albedo=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_albedo.png", normal=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_normal.png",
                  rough=0.7, sat=0.9, val=0.55, tile=(0.5, 0.5)),
    "linden": dict(albedo=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_albedo.png", normal=ROOT / "_asset_src/prospekt_plants/textures/shrub_bark_normal.png",
                   rough=0.75, sat=1.1, val=0.85, tile=(0.5, 0.5)),
}
OLD_BARK = dict(albedo=ROOT / "assets/textures/bark001/albedo.jpg", normal=ROOT / "assets/textures/bark001/normal.jpg")
# лист: тон фотолиста (сдвиг тона, насыщенность, яркость), шероховатость, светлее/темнее, пыль
LEAF = {
    "birch": dict(hue=0.5, sat=1.05, val=1.0, rough=0.6, light=(0.42, 0.56, 0.16), dark=(0.1, 0.2, 0.05), dust=0.08),
    "linden": dict(hue=0.51, sat=0.95, val=0.62, rough=0.62, light=(0.36, 0.5, 0.12), dark=(0.07, 0.15, 0.04), dust=0.12),
    "poplar": dict(hue=0.5, sat=1.0, val=0.82, rough=0.45, light=(0.38, 0.5, 0.16), dark=(0.07, 0.15, 0.05), dust=0.1),
    "lilac": dict(hue=0.505, sat=1.0, val=0.62, rough=0.55, light=(0.3, 0.45, 0.12), dark=(0.06, 0.13, 0.04), dust=0.1),
    "hedge": dict(hue=0.5, sat=1.05, val=0.7, rough=0.4, light=(0.25, 0.38, 0.1), dark=(0.04, 0.1, 0.03), dust=0.12),
}
# изнанка листа (насыщенность, яркость): светлее и матовее лица; у тополя — белёсая, у липы — сизоватая
UNDER = {"birch": (0.8, 1.2), "linden": (0.55, 1.3), "poplar": (0.5, 1.45), "lilac": (0.75, 1.2), "hedge": (0.6, 1.35)}
LEAF_FILE = {"birch": "birch", "linden": "linden", "poplar": "poplar", "lilac": "lilac", "hedge": "cotoneaster"}
# высота тёмного низа берёзы и старой коры тополя по экземплярам, м (у молодой берёзы береста почти до земли)
DARK_H = {"birch_a": 1.8, "birch_b": 1.3, "birch_c": 0.3}
OLD_H = {"poplar_a": 7.5, "poplar_b": 6.0}
TWIG = {"birch": (0.17, 0.12, 0.1), "linden": (0.36, 0.22, 0.13), "poplar": (0.42, 0.38, 0.26), "lilac": (0.33, 0.34, 0.24),
        "hedge": (0.26, 0.18, 0.13)}


def native() -> None:
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    spec = importlib.util.spec_from_file_location("ucupaint_helpers", SKILL / "scripts/ucupaint_helpers.py")
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    U = H.load_ucupaint()


def image(path: Path, color: bool) -> bpy.types.Image:
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = "sRGB" if color else "Non-Color"
    return img


def activate(mat: bpy.types.Material) -> None:
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and mat.name in [m.name for m in o.data.materials if m])
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.active_material_index = [m.name if m else "" for m in ob.data.materials].index(mat.name)


def make_stack(mat: bpy.types.Material, label: str):
    activate(mat)
    nt = mat.node_tree
    for n in list(nt.nodes):
        if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL"):
            nt.nodes.remove(n)
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=label, color=True, metallic=False, roughness=True, normal=True, ao=False,
                                         alpha=False, switch_to_material_view=False, target_bsdf_name=bsdf.name)
    group = next(n for n in nt.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    normal.main_uv = UV
    group.label = label
    mat["authoring"] = "Нативный UCUPaint 2.4.9; Claude; растения «Проспекта», PBR v01 на форме v01"
    return tree


def reconnect(tree) -> None:
    U.input_outputs.check_all_channel_ios(tree.yp, reconnect=True)
    U.input_outputs.check_start_end_root_ch_nodes(tree)
    for lay in tree.yp.layers:
        U.node_connections.reconnect_layer_nodes(lay)
    U.node_connections.reconnect_yp_nodes(tree)


def layer(tree, name: str, source: str = "COLOR", color=None, rough=None, normal=None, img=None, amount: float = 1.0,
          normal_type: str = "BUMP_MAP", distance: float = 0.002):
    """Слой наверх. color/rough — значение или "source" (из картинки); normal="map" — картинка как карта нормалей,
    "source" — как высота."""
    tree.yp.halt_update = True
    lay = U.Layer.add_new_layer(tree, name, source, -1, "MIX", "MIX", normal_type, "UV" if img is not None else "Object", UV,
                                image=img, use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    values = {"Color": color, "Roughness": rough, "Normal": normal}
    for root, ch in zip(tree.yp.channels, lay.channels):
        v = values.get(root.name)
        ch.enable = v is not None
        if v is None:
            continue
        if v not in ("source", "map"):
            ch.override = True
            ch.override_type = "DEFAULT"
            H.sync_property(U, ch, "override_color" if root.type == "RGB" else "override_value", v)
        if root.type == "NORMAL" and v == "source":
            H.sync_property(U, ch, "bump_distance", distance)
            H.sync_property(U, ch, "bump_midlevel", 0.5)
    H.sync_property(U, lay, "intensity_value", amount)
    return lay


def huesat(lay, hue: float, sat: float, val: float) -> None:
    importlib.import_module(U.__name__ + ".Modifier").add_new_modifier(lay, "HUE_SATURATION")
    node = U.common.get_mod_tree(lay).nodes[lay.modifiers[-1].huesat]
    node.inputs["Hue"].default_value = hue
    node.inputs["Saturation"].default_value = sat
    node.inputs["Value"].default_value = val


def ramp(mask, lo: float, hi: float, invert: bool = False) -> None:
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(mask, "RAMP")
    node = U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp]
    e0, e1 = node.color_ramp.elements
    e0.position, e1.position = lo, hi
    e0.color = (1, 1, 1, 1) if invert else (0, 0, 0, 1)
    e1.color = (0, 0, 0, 1) if invert else (1, 1, 1, 1)


def vcol(lay, name: str, label: str, lo=None, hi=None, invert=False):
    m = U.Mask.add_new_mask(lay, label, "VCOL", "Object", UV, vcol_name=name)
    if lo is not None:
        ramp(m, lo, hi, invert)
    return m


def noise(lay, label: str, scale: float, lo: float, hi: float, k: float = 1.0):
    m = U.Mask.add_new_mask(lay, label, "NOISE", "Object", UV)
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = 3.0
    src.inputs["Roughness"].default_value = 0.6
    H.local_noise_ramp(U, m, lo, hi)
    if k != 1.0:
        m.intensity_value = k
        U.common.set_entity_prop_value(m, "intensity_value", k)
    return m


# ---------------------------------------------------------------- атрибуты коры по геометрии

def corners(ob):
    me = ob.data
    n = len(me.loops)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get("co", co)
    idx = np.empty(n, np.int32)
    me.loops.foreach_get("vertex_index", idx)
    nrm = np.empty(n * 3, np.float32)
    me.corner_normals.foreach_get("vector", nrm)
    return co.reshape(-1, 3)[idx], nrm.reshape(-1, 3)


def write_attr(ob, name: str, val: np.ndarray) -> None:
    me = ob.data
    attr = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="CORNER")
    rgba = np.ones((len(me.loops), 4), np.float32)
    rgba[:, :3] = np.clip(val, 0, 1).astype(np.float32)[:, None]
    attr.data.foreach_set("color", rgba.ravel())


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def bark_attrs(ob, kind: str, key: str) -> None:
    """Низ_ствола (берёза: чёрная трещиноватая кора, граница рваная языками), Старая_кора (тополь: бороздчатая внизу),
    Мох_север (у земли, с севера: +Y Blender = −Z Godot), Почва (самый комель)."""
    p, n = corners(ob)
    ang = np.arctan2(p[:, 1], p[:, 0])
    z = p[:, 2]
    wav = 0.5 + 0.25 * np.sin(3 * ang + 1.3) * np.cos(z * 1.7) + 0.25 * np.sin(7 * ang + z * 2.9)
    if kind == "birch":
        edge = DARK_H.get(key, 1.6) * (0.55 + 0.9 * wav)
        write_attr(ob, "Низ_ствола", 1.0 - smooth(edge - 0.18, edge + 0.05, z))
    if kind == "poplar":
        edge = OLD_H.get(key, 6.0) * (0.75 + 0.5 * wav)
        write_attr(ob, "Старая_кора", 1.0 - smooth(edge - 0.6, edge + 0.3, z))
    write_attr(ob, "Мох_север", (1.0 - smooth(0.25, 1.4, z)) * smooth(0.05, 0.6, n[:, 1]))
    write_attr(ob, "Почва", 1.0 - smooth(0.02, 0.32, z))


# ---------------------------------------------------------------- стеки

def bark_stack(mat, kind: str, tex: dict, base: bool) -> None:
    tree = make_stack(mat, f"{S.LABEL[kind]} • {'кора ствола' if base else 'кора ветвей'}")
    lay = layer(tree, "01 • Кора — фото CC0", "IMAGE", color="source", rough=tex["rough"], img=image(tex["albedo"], True))
    if tex["sat"] != 1.0 or tex["val"] != 1.0:
        huesat(lay, 0.5, tex["sat"], tex["val"])
    layer(tree, "02 • Рельеф коры — нормаль фото", "IMAGE", normal="map", normal_type="NORMAL_MAP", img=image(tex["normal"], False))
    if base and kind == "birch":
        lay = layer(tree, "03 • Чёрная трещиноватая кора у комля", "IMAGE", color="source", rough=0.95, img=image(OLD_BARK["albedo"], True))
        huesat(lay, 0.5, 0.25, 0.32)
        vcol(lay, "Низ_ствола", "Высота тёмного низа (рваная)")
        lay = layer(tree, "04 • Рельеф трещин у комля", "IMAGE", normal="map", normal_type="NORMAL_MAP", img=image(OLD_BARK["normal"], False))
        vcol(lay, "Низ_ствола", "Высота тёмного низа (рваная)")
    if base and kind == "poplar":
        lay = layer(tree, "03 • Старая бороздчатая кора внизу ствола", "IMAGE", color="source", rough=0.92, img=image(OLD_BARK["albedo"], True))
        huesat(lay, 0.5, 0.45, 0.78)
        vcol(lay, "Старая_кора", "Граница старой коры")
        lay = layer(tree, "04 • Рельеф борозд", "IMAGE", normal="map", normal_type="NORMAL_MAP", img=image(OLD_BARK["normal"], False))
        vcol(lay, "Старая_кора", "Граница старой коры")
    if base and kind in ("birch", "linden", "poplar"):
        lay = layer(tree, "05 • Мох с севера у земли", color=(0.12, 0.17, 0.05), rough=0.95, amount=0.85)
        vcol(lay, "Мох_север", "Север и низ")
        noise(lay, "Пятна мха", 9.0, 0.35, 0.7)
    if base:
        lay = layer(tree, "06 • Почва у комля (брызги, пыль)", color=(0.16, 0.12, 0.08), rough=0.95, amount=0.7)
        vcol(lay, "Почва", "Самый низ")
        noise(lay, "Неровный край", 14.0, 0.3, 0.7)
    reconnect(tree)


def twig_stack(mat, kind: str) -> None:
    tree = make_stack(mat, f"{S.LABEL[kind]} • побеги и черешки")
    layer(tree, "01 • Побег — свой цвет", color=TWIG[kind], rough=0.7)
    lay = layer(tree, "02 • Неровность цвета", color=tuple(c * 0.7 for c in TWIG[kind]), amount=0.6)
    noise(lay, "Пятна", 60.0, 0.4, 0.75)
    reconnect(tree)


def seed_stack(mat) -> None:
    tree = make_stack(mat, "Сирень • сухие метёлки")
    layer(tree, "01 • Сухие коробочки", color=(0.28, 0.2, 0.11), rough=0.8)
    lay = layer(tree, "02 • Посветлевшие на солнце", color=(0.42, 0.33, 0.2), amount=0.7)
    noise(lay, "Пятна", 80.0, 0.45, 0.75)
    reconnect(tree)


def leaf_stack(mat, kind: str) -> None:
    L = LEAF[kind]
    tree = make_stack(mat, f"{S.LABEL[kind]} • лист")
    col_img = image(LEAVES / f"{LEAF_FILE[kind]}_leaf_color.png", True)
    lay = layer(tree, "01 • Лист — фото CC0 (ambientCG), под контур вида", "IMAGE", color="source", rough=L["rough"], img=col_img)
    huesat(lay, L["hue"], L["sat"], L["val"])
    layer(tree, "02 • Жилки — нормаль скана", "IMAGE", normal="map", normal_type="NORMAL_MAP",
          img=image(LEAVES / f"{LEAF_FILE[kind]}_leaf_normal.png", False))
    lay = layer(tree, "03 • Светлее и желтее — часть листьев", color=L["light"], amount=0.35)
    vcol(lay, "Col", "Оттенок листа (r)", 0.62, 1.0)
    lay = layer(tree, "04 • Темнее — часть листьев", color=L["dark"], amount=0.3)
    vcol(lay, "Col", "Оттенок листа (r)", 0.0, 0.32, invert=True)
    lay = layer(tree, "05 • Городская пыль", color=(0.45, 0.43, 0.36), rough=0.8, amount=L["dust"])
    noise(lay, "Пятна пыли", 6.0, 0.35, 0.75)
    reconnect(tree)
    leaf_sides(mat, kind, col_img)


def leaf_sides(mat, kind: str, col_img) -> None:
    """Поверх стека (на уровне материала): изнанка листа светлее и матовее лица, тонкий лист светится на просвет
    (полупрозрачный BSDF цвета листа), вырез — альфа фотолиста. Стек UCUPaint не меняется; атлас игры берёт его цвет."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    group = next(n for n in nt.nodes if n.type == "GROUP" and "Color" in n.outputs)
    L = nt.links
    base = bsdf.location

    def node(t: str, label: str, dx: float, dy: float):
        n = nt.nodes.new(t)
        n.label = label
        n.location = base + Vector((dx, dy))
        return n

    uvn = node("ShaderNodeUVMap", "Развёртка листа", -700, -520)
    uvn.uv_map = UV
    tex = node("ShaderNodeTexImage", "Вырез листа (альфа фото)", -500, -520)
    tex.image = col_img
    L.new(uvn.outputs[0], tex.inputs[0])
    geo = node("ShaderNodeNewGeometry", "Лицо / изнанка", -500, 260)
    sat, val = UNDER[kind]
    under = node("ShaderNodeHueSaturation", "Изнанка: светлее, менее насыщенная", -300, 300)
    under.inputs["Saturation"].default_value = sat
    under.inputs["Value"].default_value = val
    L.new(group.outputs["Color"], under.inputs["Color"])
    side = node("ShaderNodeMix", "Цвет: лицо или изнанка", -120, 260)
    side.data_type = "RGBA"
    L.new(geo.outputs["Backfacing"], side.inputs[0])
    L.new(group.outputs["Color"], side.inputs[6])
    L.new(under.outputs[0], side.inputs[7])
    L.new(side.outputs[2], bsdf.inputs["Base Color"])
    rough = node("ShaderNodeMix", "Шероховатость изнанки", -120, 60)
    rough.data_type = "FLOAT"
    L.new(geo.outputs["Backfacing"], rough.inputs[0])
    L.new(group.outputs["Roughness"], rough.inputs[2])
    rough.inputs[3].default_value = 0.85
    L.new(rough.outputs[0], bsdf.inputs["Roughness"])
    bsdf.inputs["Transmission Weight"].default_value = 0.0
    # просвет: свет, прошедший сквозь лист, — жёлто-зелёный
    tint = node("ShaderNodeMix", "Цвет на просвет", 120, -300)
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1.0
    tint.inputs[7].default_value = (0.9, 1.0, 0.45, 1.0)
    L.new(group.outputs["Color"], tint.inputs[6])
    trans = node("ShaderNodeBsdfTranslucent", "Тонкий лист на просвет", 320, -300)
    L.new(tint.outputs[2], trans.inputs["Color"])
    L.new(group.outputs["Normal"], trans.inputs["Normal"])
    mix = node("ShaderNodeMixShader", "Отражение + просвет", 520, -100)
    mix.inputs[0].default_value = 0.28
    L.new(bsdf.outputs[0], mix.inputs[1])
    L.new(trans.outputs[0], mix.inputs[2])
    clear = node("ShaderNodeBsdfTransparent", "Вне листа", 520, -320)
    cut = node("ShaderNodeMixShader", "Вырез по альфе", 720, -100)
    L.new(tex.outputs["Alpha"], cut.inputs[0])
    L.new(clear.outputs[0], cut.inputs[1])
    L.new(mix.outputs[0], cut.inputs[2])
    L.new(cut.outputs[0], out.inputs["Surface"])
    mat.surface_render_method = "DITHERED"


def apply(kind: str, entries: list) -> None:
    for e in entries:
        bark_attrs(e["wood"], kind, e["key"])
    lab = S.LABEL[kind]
    mats = bpy.data.materials

    def used(name: str) -> bool:
        return any(name in [m.name for m in o.data.materials if m] for o in bpy.data.objects if o.type == "MESH")

    if used(f"{lab}_кора"):
        bark_stack(mats[f"{lab}_кора"], kind, BARK_TEX[kind], True)
    if used(f"{lab}_ветви"):
        bark_stack(mats[f"{lab}_ветви"], kind, BRANCH_TEX.get(kind, BARK_TEX[kind]), kind == "hedge")
    twig_stack(mats[f"{lab}_побеги"], kind)
    leaf_stack(mats[f"{lab}_лист"], kind)
    if used(f"{lab}_метёлки"):
        seed_stack(mats[f"{lab}_метёлки"])


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kinds = [k for k in BF.ORDER if k in argv] or BF.ORDER
    for kind in kinds:
        plib.BARK.update(tile_u=BARK_TEX[kind]["tile"][0], tile_v=BARK_TEX[kind]["tile"][1])
        entries, mods, row = BF.build_kind(kind)
        native()
        apply(kind, entries)
        bpy.context.view_layer.update()
        res = BF.measure(entries)
        for e, r in zip(entries, res):
            e["res"] = r
        bpy.ops.file.pack_all()
        idx = BF.ORDER.index(kind) + 1
        path = BF.LIB / "models" / f"{idx:02d}_{S.LABEL[kind]}_PBR_{VERSION}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
        print("PLANTS PBR", path.name, flush=True)
        if "preview" in argv:
            BF.VERSION = "pbr_" + VERSION
            BF.previews(kind, entries, row)
            backlit(kind)


def backlit(kind: str) -> None:
    """Модули веточек против солнца: лист на просвет и изнанка (проверка тонкого листа)."""
    sun = bpy.data.objects["Солнце"]
    d = sun.matrix_world.to_quaternion() @ Vector((0, 0, -1))
    flat = Vector((d.x, d.y, 0)).normalized()
    n = len(S.MODULES[kind]())
    mx = BF.MOD_X0 + (n - 1) * BF.MOD_STEP[kind] * 0.5
    target = Vector((mx, BF.MOD_Y, 1.25))
    cam = BF.camera("кадр_на_просвет", target - flat * 4.2 + Vector((0, 0, -0.45)), target, 30)
    BF.render(cam, BF.LIB / "previews" / f"{kind}_backlit_pbr_{VERSION}.png", (1600, 1000), 48)


if __name__ == "__main__":
    main()
