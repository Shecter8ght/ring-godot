"""NPC: броня — текстуры в нативном UCUPaint (2.4.9) по образцу владельца (Sketchfab «Tactical Body Armor Pack1»).

Принятая форма не меняется (armor_<уровень>.blend → armor_<уровень>_tex.blend). Вид как у образца: ткань с
видимым плетением, выгоревшая и запылённая, кромки и окантовка светлее и затёрты, грязь книзу, на нижних
кромках и во впадинах, брызги спереди внизу; стропа с грязью в складках, ворсистое велкро, матовая фурнитура.
Расцветки (решение владельца 2026-10-22): бомжовская — тёмно-синяя, средняя — олива, крутая — свой пиксельный
лесной камуфляж (tools/npc_kit/gen_armor_camo.py). Износ у всех трёх одинаковый — ношеные.

Маски «где» — атрибуты вершин из геометрии (ArmorEdge — выпуклые кромки и окантовка, ArmorUp — смотрит вверх,
ArmorLow — ниже по телу, ArmorUnder — нижние кромки, ArmorFront — перёд живота и паха), AO (Cycles) — впадины;
рисунок пятен — маски владельца «Маски_АЛЬФА» (кубическая проекция) и шум UCUPaint. Плетение — нормали фото CC0
Poly Haven в масштабе ткани. Маски AO смотреть в Rendered (Cycles): в Material Preview их нет.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_texture.py -- poor|mid|top [shots]
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402
from ucup import (H, U, ao_mask, image, image_layer, layer, noise, owner_mask, srgb,  # noqa: E402,F401
                  stack, vmask)

ROOT = Path(__file__).resolve().parents[2]
ARMOR = ROOT / "_asset_src" / "npc_kit" / "armor"
TEX = ROOT / "_asset_src" / "npc_kit" / "tex"
TIERS = {"poor": ("Poor", "06_Armor_Poor"), "mid": ("Mid", "06_Armor_Mid"), "top": ("Top", "06_Armor_Top")}


# Расцветка уровня: ткань, стропа, велкро, пластик (sRGB с образцов ткани).
PALETTE = {
    "poor": {"cordura": srgb(36, 46, 68), "webbing": srgb(30, 34, 46), "velcro": srgb(33, 39, 54),
             "plastic": srgb(26, 26, 27), "mesh": srgb(24, 28, 38)},
    "mid": {"cordura": srgb(66, 69, 44), "webbing": srgb(60, 62, 41), "velcro": srgb(66, 68, 49),
            "plastic": srgb(38, 39, 33)},
    "top": {"cordura": None, "webbing": srgb(88, 88, 62), "velcro": srgb(90, 91, 74),
            "plastic": srgb(76, 74, 56)},
}
DUST = srgb(136, 132, 120)
FADE = srgb(150, 148, 136)
DIRT = srgb(56, 50, 40)
GRIME = srgb(40, 35, 28)
MUD = srgb(64, 60, 52)


# ---------- маски из геометрии ----------

def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def geometry_masks(obj: bpy.types.Object, z_lo: float, z_hi: float, edge_co: np.ndarray | None = None) -> None:
    """z_lo…z_hi — высота всей брони: грязь копится книзу самой вещи (у средней низ — пояс, у крутой — колени).
    edge_co — координаты, по которым считать кромки (у мятой ткани рюкзака — гладкая форма до складок)."""
    me = obj.data
    n = len(me.vertices)
    if n == 0:
        return
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    co = co.reshape(n, 3)
    nrm = np.empty(n * 3, np.float32)
    me.vertex_normals.foreach_get("vector", nrm)
    nrm = nrm.reshape(n, 3)
    e = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get("vertices", e)
    e = e.reshape(-1, 2)
    deg = np.bincount(e.ravel(), minlength=n).astype(np.float32)
    src = co if edge_co is None else edge_co
    sm = src.copy()
    for _ in range(4):                                    # выпуклость: вершина над сглаженной формой (локально — кромки, а не вся лямка)
        acc = np.zeros_like(co)
        np.add.at(acc, e[:, 0], sm[e[:, 1]])
        np.add.at(acc, e[:, 1], sm[e[:, 0]])
        avg = np.where(deg[:, None] > 0, acc / np.maximum(deg, 1)[:, None], sm)
        sm = sm + 0.5 * (avg - sm)
    fold = ((src - sm) * nrm).sum(1) / 0.0025
    mw = np.array(obj.matrix_world, np.float32)
    world = co @ mw[:3, :3].T + mw[:3, 3]
    wn = nrm @ np.linalg.inv(mw[:3, :3])
    wn /= np.maximum(np.linalg.norm(wn, axis=1), 1e-9)[:, None]
    z = world[:, 2]
    masks = {
        "ArmorEdge": np.clip(fold * 0.9, 0.0, 1.0),
        "ArmorUp": smoothstep((wn[:, 2] - 0.15) / 0.6),
        "ArmorLow": smoothstep((z_hi - z) / (z_hi - z_lo) * 1.6 - 0.45),
        "ArmorUnder": smoothstep((-wn[:, 2] - 0.25) / 0.5),
        "ArmorFront": smoothstep((-wn[:, 1] - 0.3) / 0.5) * smoothstep((z_hi - z) / (z_hi - z_lo) * 1.8 - 0.6),
    }
    for name, val in masks.items():
        a = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="BYTE_COLOR", domain="POINT")
        rgba = np.ones((n, 4), np.float32)
        rgba[:, :3] = val[:, None]
        a.data.foreach_set("color", rgba.ravel())
    me.update()


# ---------- рецепты ----------

def wear_fabric(t, rough: float, dirt_amount: float = 1.0, edge_amount: float = 0.30) -> None:
    """Общая история ношеной ткани (кордура, стропа, велкро, сетка): одинаковая на всех уровнях."""
    lay = layer(t, "15 • Застиранность и разводы по всей вещи", GRIME, None, None, amount=0.30)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.60, 0.15, 0.85)
    lay = layer(t, "20 • Выгорание сверху", FADE, None, min(1.0, rough + 0.04), amount=0.12)
    vmask(lay, "ArmorUp")
    noise(lay, "Неровно, пятнами 10–20 см", 6.0, 0.30, 0.85, shift=(0.3, 0.1, 0.2))
    lay = layer(t, "30 • Затёртые кромки и окантовка", FADE, None, min(1.0, rough + 0.06), amount=edge_amount)
    vmask(lay, "ArmorEdge")
    noise(lay, "Разрыв затёртости 2–5 мм", 180.0, 0.32, 0.70)
    lay = layer(t, "40 • Пыль на верхних плоскостях", DUST, None, 0.97, amount=0.24)
    vmask(lay, "ArmorUp")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.35, 0.12, 0.75)
    lay = layer(t, "50 • Грязь во впадинах и под клапанами", GRIME, None, 0.93, amount=0.65 * dirt_amount)
    ao_mask(lay, 0.025)
    noise(lay, "Неровный край осадка", 40.0, 0.25, 0.75)
    lay = layer(t, "60 • Грязь книзу", DIRT, None, 0.94, amount=0.75 * dirt_amount)
    vmask(lay, "ArmorLow")
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.40, 0.10, 0.70)
    lay = layer(t, "61 • Грязь на нижних кромках", DIRT, None, 0.95, amount=0.70 * dirt_amount)
    vmask(lay, "ArmorUnder")
    owner_mask(lay, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 0.25, 0.08, 0.65)
    lay = layer(t, "62 • Брызги спереди внизу (лёжа, на коленях)", MUD, None, 0.95, amount=0.50 * dirt_amount)
    vmask(lay, "ArmorFront")
    owner_mask(lay, "05_Брызги_и_высохшие_капли/Брызги_средние_01.png", 0.30, 0.10, 0.85)


def mat_cordura(mat: bpy.types.Material, tier: str) -> None:
    col = PALETTE[tier]["cordura"]
    t, _ = stack(mat, col or srgb(110, 108, 80), 0.0, 0.86)
    layer(t, "00 • Ткань", col or srgb(110, 108, 80), 0.0, 0.86)
    if col is None:
        image_layer(t, "01 • Камуфляж «пиксельный лесной» (свой)", image(ARMOR / "tex" / "camo_pixel_forest_4k.png", True),
                    "Color", 0.768)
    lay = layer(t, "05 • Неровный прокрас (темнее пятнами)", GRIME, None, None, 0.14)
    noise(lay, "Пятна прокраса 5–15 см", 9.0, 0.35, 0.80)
    image_layer(t, "10 • Плетение кордуры (Poly Haven book_pattern)",
                image(TEX / "book_pattern" / "book_pattern_nor_gl_4k.png", False), "Normal", 0.30)
    image_layer(t, "11 • Микрошероховатость плетения", image(TEX / "book_pattern" / "book_pattern_rough_4k.png", False),
                "Roughness", 0.30, amount=0.30)
    wear_fabric(t, 0.86)
    H.reconnect(U, t)


def mat_webbing(mat: bpy.types.Material, tier: str) -> None:
    col = PALETTE[tier]["webbing"]
    t, _ = stack(mat, col, 0.0, 0.82)
    layer(t, "00 • Стропа нейлон", col, 0.0, 0.82)
    image_layer(t, "10 • Саржевое плетение стропы (Poly Haven denim_fabric_05)",
                image(TEX / "denim_fabric_05" / "denim_fabric_05_nor_gl_4k.png", False), "Normal", 0.22)
    image_layer(t, "11 • Микрошероховатость стропы", image(TEX / "denim_fabric_05" / "denim_fabric_05_rough_4k.png", False),
                "Roughness", 0.22, amount=0.30)
    wear_fabric(t, 0.82, edge_amount=0.14)
    H.reconnect(U, t)


def mat_velcro(mat: bpy.types.Material, tier: str) -> None:
    col = PALETTE[tier]["velcro"]
    t, _ = stack(mat, col, 0.0, 0.95)
    layer(t, "00 • Велкро «петля»", col, 0.0, 0.95)
    image_layer(t, "10 • Ворс петель (Poly Haven terry_cloth)",
                image(TEX / "terry_cloth" / "terry_cloth_nor_gl_4k.png", False), "Normal", 0.18)
    lay = layer(t, "15 • Катышки и ворсинки", DUST, None, 0.98, amount=0.35)
    noise(lay, "Отдельные катышки 1–2 мм", 420.0, 0.62, 0.78)
    wear_fabric(t, 0.95)
    H.reconnect(U, t)


def mat_mesh(mat: bpy.types.Material, tier: str) -> None:
    col = PALETTE[tier]["mesh"]
    t, _ = stack(mat, col, 0.0, 0.9)
    layer(t, "00 • Сетка", col, 0.0, 0.9)
    image_layer(t, "10 • Ячейка сетки (Poly Haven waffle_pique_cotton)",
                image(TEX / "waffle_pique_cotton" / "waffle_pique_cotton_nor_gl_4k.png", False), "Normal", 0.12)
    wear_fabric(t, 0.9)
    H.reconnect(U, t)


def mat_plastic(mat: bpy.types.Material, tier: str) -> None:
    col = PALETTE[tier]["plastic"]
    t, _ = stack(mat, col, 0.0, 0.58)
    layer(t, "00 • Литой пластик (полиацеталь)", col, 0.0, 0.58)
    lay = layer(t, "10 • Литьевая шероховатость", None, None, 0.66, amount=0.5)
    noise(lay, "Зерно литья", 900.0, 0.4, 0.7)
    lay = layer(t, "30 • Потёртые кромки (заполированы пальцами и стропой)", tuple(min(1.0, c * 1.6 + 0.02) for c in col),
                None, 0.38, amount=0.6)
    vmask(lay, "ArmorEdge")
    noise(lay, "Разрыв потёртости", 300.0, 0.35, 0.7)
    lay = layer(t, "50 • Пыль в пазах", DUST, None, 0.9, amount=0.5)
    ao_mask(lay, 0.006)
    lay = layer(t, "60 • Грязь книзу", DIRT, None, 0.9, amount=0.35)
    vmask(lay, "ArmorLow")
    H.reconnect(U, t)


def mat_metal(mat: bpy.types.Material, tier: str) -> None:
    col = srgb(58, 58, 60)
    t, _ = stack(mat, col, 1.0, 0.42)
    layer(t, "00 • Сталь, чёрное оксидирование", col, 1.0, 0.42)
    lay = layer(t, "30 • Стёртое до стали на кромках", srgb(150, 150, 152), 1.0, 0.30, amount=0.7)
    vmask(lay, "ArmorEdge")
    noise(lay, "Отдельные потёртости", 400.0, 0.4, 0.7)
    lay = layer(t, "50 • Грязь в изгибах", GRIME, 0.0, 0.85, amount=0.5)
    ao_mask(lay, 0.004)
    H.reconnect(U, t)


def mat_plate(mat: bpy.types.Material, tier: str) -> None:
    col = srgb(30, 31, 30)
    t, _ = stack(mat, col, 0.0, 0.8)
    layer(t, "00 • Чехол плиты (баллистический нейлон)", col, 0.0, 0.8)
    image_layer(t, "10 • Плетение чехла", image(TEX / "book_pattern" / "book_pattern_nor_gl_4k.png", False), "Normal", 0.25)
    lay = layer(t, "30 • Затёртые кромки", FADE, None, 0.86, amount=0.25)
    vmask(lay, "ArmorEdge")
    H.reconnect(U, t)


RECIPES = {"Cordura": mat_cordura, "Webbing": mat_webbing, "Velcro": mat_velcro, "Mesh": mat_mesh,
           "Plastic": mat_plastic, "Metal": mat_metal, "Plate": mat_plate}


# ---------- студия образца и снимки ----------

SAMPLES = 192
README = (
    "Броня «{name}» — ТЕКСТУРЫ v02: приняты владельцем; надета на мародёра v03 (куртка ближе к телу, с текстурами).\n"
    "Нативный UCUPaint 2.4.9: у каждого материала (ткань, стропа, велкро, пластик, металл, плита) свой стек слоёв —\n"
    "основа, плетение 4K (Poly Haven CC0), выгорание, затёртые кромки, пыль, грязь во впадинах и книзу, брызги.\n"
    "Маски «где» — атрибуты вершин ArmorEdge/Up/Low/Under/Front, пятна — «Маски_АЛЬФА» владельца.\n"
    "Смотреть в Rendered (Cycles): маски AO (грязь во впадинах) в Material Preview не видны.\n"
    "Коллекция {col}; мародёр v03 — тело и одежда в UCUPaint (npc_texture.py).\n"
    "Образец вида — Sketchfab «Tactical Body Armor Pack1». Скрипт: tools/npc_kit/armor_texture.py.\n")


def sample_studio() -> None:
    """Как у образца на Sketchfab: серо-зелёный фон, мягкий свет; броня без мародёра."""
    kc.studio()
    scene = bpy.context.scene
    bg = next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (*srgb(132, 158, 146), 1.0)
    bg.inputs[1].default_value = 0.9
    if "Studio_Floor" in bpy.data.objects:
        bpy.data.objects["Studio_Floor"].hide_render = True
    kc.gpu_cycles(SAMPLES)
    # шумодав с проходами альбедо и нормалей и точной предфильтрацией — иначе смазывает плетение («мыло»)
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.denoising_prefilter = "ACCURATE"


def shots(col: bpy.types.Collection, tag: str) -> None:
    sample_studio()
    out = ARMOR / "previews"
    hidden = []
    for o in bpy.data.objects:
        if o.type == "MESH" and o.users_collection and o.users_collection[0] != col and not o.hide_render:
            hidden.append(o)
            o.hide_render = True
    zc = 1.12 if tag == "top" else 1.28
    views = {
        "34": ((1.05, -1.45, zc + 0.20), (0.0, 0.0, zc)),
        "back": ((-0.9, 1.6, zc + 0.15), (0.0, 0.0, zc)),
        "macro": ((0.32, -0.62, 1.42), (0.03, -0.17, 1.32)),
    }
    for name, (pos, tgt) in views.items():
        kc.render(kc.camera("Tex_" + name, pos, tgt, 55 if name != "macro" else 60), out / f"{tag}_tex_{name}.png",
                  (1400, 1270) if name != "macro" else (1800, 1200), SAMPLES)
    for o in hidden:
        o.hide_render = False


def main() -> None:
    args = kc.args_after_dashes()
    tier = args[0]
    prefix, col_name = TIERS[tier]
    src = ARMOR / f"armor_{tier}.blend"
    bpy.ops.wm.open_mainfile(filepath=str(src))
    col = bpy.data.collections[col_name]
    objs = [o for o in col.objects if o.type == "MESH"]
    zs = [(o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box]
    z_lo, z_hi = min(zs), max(zs)
    for o in objs:
        geometry_masks(o, z_lo, z_hi)
    mats = {s.material for o in objs for s in o.material_slots if s.material}
    for mat in sorted(mats, key=lambda m: m.name):
        kind = mat.name.split("_", 1)[1]
        if mat.name.startswith("Armor_"):
            mat.name = f"{prefix}_{kind}"
        recipe = RECIPES.get(kind)
        if recipe is None:
            kc.log("  материал без рецепта:", mat.name)
            continue
        recipe(mat, tier)
        kc.log("  стек UCUPaint:", mat.name)
    bpy.context.scene.render.engine = "CYCLES"
    out = ARMOR / f"armor_{tier}_tex.blend"
    kc.save(out)
    kc.log("ARMOR_TEX", tier, len(objs), "объектов,", len(mats), "материалов →", out)
    if "shots" in args:
        shots(col, tier)
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        name = {"poor": "бомжовская", "mid": "средняя", "top": "крутая"}[tier]
        am.deliver(Path(dest), f"Броня_{name}_v02_текстуры.blend", README.format(name=name, col=col_name),
                   focus_z=1.12 if tier == "top" else 1.28)


if __name__ == "__main__":
    main()
