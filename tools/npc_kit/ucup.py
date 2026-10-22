"""Общие помощники нативного UCUPaint 2.4.9 для NPC (броня — armor_texture.py, мародёр — npc_texture.py).

Стек — настоящий UCUPaint (Color, Metallic, Roughness, Normal); слои: сплошные значения (layer), фото-карты по
развёртке в метрах или кубической проекцией (image_layer), процедурные (proc_layer); маски: шум (noise),
атрибуты вершин (vmask), впадины AO (ao_mask), рисунки «Маски_АЛЬФА» владельца (owner_mask).
Значения входов групп сверяются помощником навыка (sync_property): в 2.4.9 запись RNA не всегда доходит до узла.
Развёртка по умолчанию — UV (броня); у мародёра своя — параметр uv.
"""
from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

import addon_utils
import bpy
from mathutils import Color, Vector

import kit_common as kc

MASKS = Path("E:/Models Blender/Маски_АЛЬФА")
SKILL = Path("C:/Users/Schecter_8ght/.claude/skills/weapon-asset-texturing")
UV = "UV"


def srgb(r: int, g: int, b: int) -> tuple[float, float, float]:
    def c(x: float) -> float:
        x /= 255.0
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return (c(r), c(g), c(b))


def load_ucupaint():
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    U = importlib.import_module("bl_ext.blender_org.ucupaint")
    spec = importlib.util.spec_from_file_location("ucupaint_helpers", SKILL / "scripts" / "ucupaint_helpers.py")
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    assert U.common.get_current_version_str() == "2.4.9", U.common.get_current_version_str()
    return U, H


U, H = load_ucupaint()
MM = importlib.import_module(U.__name__ + ".MaskModifier")
MOD = importlib.import_module(U.__name__ + ".Modifier")
IMAGES: dict[str, bpy.types.Image] = {}


def image(path: Path, color: bool) -> bpy.types.Image:
    key = str(path)
    if key not in IMAGES:
        im = bpy.data.images.load(str(path), check_existing=True)
        im.colorspace_settings.name = "sRGB" if color else "Non-Color"
        IMAGES[key] = im
    return IMAGES[key]


def activate(mat: bpy.types.Material) -> None:
    obj = next(o for o in bpy.data.objects if o.type == "MESH" and any(s.material == mat for s in o.material_slots))
    for o in bpy.context.selected_objects:
        o.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.active_material_index = next(i for i, s in enumerate(obj.material_slots) if s.material == mat)


def _mat(tree) -> bpy.types.Material:
    return bpy.data.materials[tree.name.split(" • ")[0]]


def stack(mat: bpy.types.Material, color, metal: float, rough: float, uv: str | None = None):
    """Настоящий стек UCUPaint на материале (Color, Metallic, Roughness, Normal). Возвращает (дерево, Principled)."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(p.outputs[0], out.inputs["Surface"])
    p.inputs["Base Color"].default_value = (*color, 1.0)
    p.inputs["Metallic"].default_value = metal
    p.inputs["Roughness"].default_value = rough
    activate(mat)
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=mat.name + " • UCUPaint", color=True, metallic=True, roughness=True,
                                        normal=True, ao=False, switch_to_material_view=False, target_bsdf_name=p.name)
    tree = next(n.node_tree for n in nt.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.yp.is_ypaint_node)
    normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    normal.enable_smooth_bump = False
    normal.main_uv = uv or UV
    mat["Native UCUPaint"] = "2.4.9"
    tree["uv"] = uv or UV
    return tree, p


def _uv(tree) -> str:
    return tree.get("uv", UV)


def layer(tree, name: str, color=None, metal=None, rough=None, amount: float = 1.0, blend: str = "MIX"):
    """Слой сплошных значений (что меняет), его «где» — маски."""
    activate(_mat(tree))
    tree.yp.halt_update = True
    lay = U.Layer.add_new_layer(tree, name, "COLOR", -1, blend, "OVERLAY", "BUMP_MAP", "Object", _uv(tree),
                                use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    values = {"Color": color, "Metallic": metal, "Roughness": rough, "Normal": None}
    for root, ch in zip(tree.yp.channels, lay.channels):
        val = values[root.name]
        ch.enable = val is not None
        if val is None:
            continue
        ch.override = True
        ch.override_type = "DEFAULT"
        H.sync_property(U, ch, "override_color" if root.type == "RGB" else "override_value",
                        Color(val) if root.type == "RGB" else val)
    H.sync_property(U, lay, "intensity_value", amount)
    return lay


def image_layer(tree, name: str, img: bpy.types.Image, channel: str, tile_m: float | tuple[float, float],
                amount: float = 1.0, normal_strength: float = 1.0, box: bool = False, bump: float | None = None,
                blend: str = "MIX", hsv: tuple[float, float, float] | None = None):
    """Фото-карта. По развёртке в метрах (tile_m — метров ткани на повтор, можно (по u, по v)) или кубической
    проекцией в координатах детали (box). Normal: карта нормалей, а с bump — карта высоты (глубина bump, м).
    hsv — модификатор оттенка/насыщенности/яркости слоя (как узел HSV: 0,5 — без сдвига оттенка)."""
    activate(_mat(tree))
    idx = next(i for i, c in enumerate(tree.yp.channels) if c.name == channel)
    tree.yp.halt_update = True
    lay = U.Layer.add_new_layer(tree, name, "IMAGE", idx, blend, "OVERLAY",
                                "BUMP_MAP" if (channel != "Normal" or bump) else "NORMAL_MAP",
                                "Object" if box else "UV", _uv(tree), image=img,
                                use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    for root, ch in zip(tree.yp.channels, lay.channels):
        ch.enable = root.name == channel
        if root.name == "Normal" and channel == "Normal":
            if bump:
                ch.normal_map_type = "BUMP_MAP"
                H.sync_property(U, ch, "bump_distance", bump)
                H.sync_property(U, ch, "bump_midlevel", 0.5)
            else:
                ch.normal_map_type = "NORMAL_MAP"
                try:
                    H.sync_property(U, ch, "normal_strength", normal_strength)
                except Exception as e:  # noqa: BLE001 — имя свойства силы нормали в 2.4.9 сверяется по факту
                    kc.log("  сила нормали не задана:", e)
    tu, tv = (tile_m, tile_m) if isinstance(tile_m, (int, float)) else tile_m
    lay.enable_uniform_scale = False
    sc = Vector((1.0 / tu, 1.0 / tv, 1.0 / tu if box else 1.0))
    lay.scale = sc
    U.common.set_entity_prop_value(lay, "scale", sc)
    if box:
        src = U.common.get_layer_source(lay)
        src.projection = "BOX"
        src.projection_blend = 0.3
    if hsv is not None:
        ch = next(c for r, c in zip(tree.yp.channels, lay.channels) if r.name == channel)
        MOD.add_new_modifier(ch, "HUE_SATURATION")
        mod = ch.modifiers[-1]
        mod.huesat_hue_val, mod.huesat_saturation_val, mod.huesat_value_val = hsv
        node = U.common.get_tree(lay).nodes.get(mod.huesat)
        if node is not None:
            for i, v in enumerate(hsv):
                node.inputs[i].default_value = v
    H.sync_property(U, lay, "intensity_value", amount)
    return lay


def proc_layer(tree, name: str, kind: str, channel: str, scale: float, bump: float = 0.0001, amount: float = 1.0,
               stretch: tuple[float, float, float] = (1.0, 1.0, 1.0), detail: float = 2.5, box_uv: bool = True):
    """Процедурный рельеф (NOISE / WAVE / VORONOI) — источник как высота канала Normal."""
    activate(_mat(tree))
    tree.yp.halt_update = True
    lay = U.Layer.add_new_layer(tree, name, kind, -1, "MIX", "OVERLAY", "BUMP_MAP",
                                "Object" if box_uv else "UV", _uv(tree), use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    for root, ch in zip(tree.yp.channels, lay.channels):
        ch.enable = root.name == channel
        if root.name == "Normal" and channel == "Normal":
            H.sync_property(U, ch, "bump_distance", bump)
            H.sync_property(U, ch, "bump_midlevel", 0.5)
    src = U.common.get_layer_source(lay)
    if "Scale" in src.inputs:
        src.inputs["Scale"].default_value = scale
    if "Detail" in src.inputs:
        src.inputs["Detail"].default_value = detail
    lay.scale = stretch
    H.sync_property(U, lay, "intensity_value", amount)
    return lay


def noise(lay, name: str, scale: float, lo: float | None = None, hi: float | None = None, detail: float = 3.0,
          shift: tuple = (0.0, 0.0, 0.0)):
    m = U.Mask.add_new_mask(lay, name, "NOISE", "Object", _uv(lay.id_data))
    n = U.common.get_mask_tree(m).nodes[m.source]
    n.inputs["Scale"].default_value = scale
    n.inputs["Detail"].default_value = detail
    n.inputs["Roughness"].default_value = 0.62
    m.translation = shift
    if lo is not None:
        H.local_noise_ramp(U, m, lo, hi)
    return m


def vmask(lay, attr: str, lo: float | None = None, hi: float | None = None):
    m = U.Mask.add_new_mask(lay, attr, "VCOL", "Object", _uv(lay.id_data), vcol_name=attr)
    if lo is not None:
        MM.add_new_mask_modifier(m, "RAMP")
        ramp = U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp]
        ramp.color_ramp.elements[0].position = lo
        ramp.color_ramp.elements[1].position = hi
    return m


def ao_mask(lay, distance: float):
    m = U.Mask.add_new_mask(lay, f"Впадины (AO {distance * 100:.0f} см)", "AO", "Object", _uv(lay.id_data),
                            ao_distance=distance)
    MM.add_new_mask_modifier(m, "INVERT")
    return m


def image_mask(lay, img: bpy.types.Image, name: str, lo: float | None = None, hi: float | None = None):
    """Маска-карта по развёртке материала (швы, строчка из details.py)."""
    m = U.Mask.add_new_mask(lay, name, "IMAGE", "UV", _uv(lay.id_data), image=img, socket_input_name="Color")
    U.common.get_mask_tree(m).nodes[m.source].extension = "CLIP"
    if lo is not None:
        MM.add_new_mask_modifier(m, "RAMP")
        ramp = U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp]
        ramp.color_ramp.elements[0].position = lo
        ramp.color_ramp.elements[1].position = hi
    return m


def owner_mask(lay, rel: str, tile_m: float, lo: float | None = None, hi: float | None = None):
    """Рисунок из «Маски_АЛЬФА» кубической проекцией в координатах детали (метры): tile_m — размер повтора."""
    img = image(MASKS / rel, color=False)
    m = U.Mask.add_new_mask(lay, Path(rel).stem, "IMAGE", "Object", _uv(lay.id_data), image=img,
                            socket_input_name="Color")
    src = U.common.get_mask_tree(m).nodes[m.source]
    src.projection = "BOX"
    src.projection_blend = 0.3
    src.extension = "REPEAT"
    m.enable_uniform_scale = False
    s = 1.0 / tile_m
    U.common.set_entity_prop_value(m, "scale", Vector((s, s, s)))
    if lo is not None:
        MM.add_new_mask_modifier(m, "RAMP")
        ramp = U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp]
        ramp.color_ramp.elements[0].position = lo
        ramp.color_ramp.elements[1].position = hi
    return m


def reconnect(tree) -> None:
    H.reconnect(U, tree)
