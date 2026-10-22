"""NPC: мародёр — текстуры тела и одежды в нативном UCUPaint 2.4.9 (тем же приёмом, что броня: armor_texture.py).

Читает npc_scav_<версия>.blend (форма не меняется) → npc_scav_<версия>_tex.blend. Вид — как у принятой брони
(образец владельца Sketchfab «Tactical Body Armor Pack1», направление Тарков / Deadside): вещи ношеные, фото-фактура
4K (Poly Haven CC0), выгорание и затёртость там, где вещь трут, грязь во впадинах, у швов и книзу.

- Куртка: кожа (fabric_leather_01 без шва, окраска модификатором оттенка UCUPaint), стёртая до светлой основы
  отделка на краях, локтях, гребнях складок, у швов и в сборках, заломы (leather_red_02), жирные следы рук,
  пыль сверху; швы и отстрочка — карты details.py (рельеф, нитка, грязь в шве). Трикотаж — вязка и рубчик.
- Брюки и карманы: свой камуфляж «Лесополоса» (gen_npc_camo.py), саржа denim_fabric_05, выгорание на коленях,
  сиденье и бёдрах, жир на бёдрах, грязь книзу и брызги; отстрочка карманов — по атрибуту bd.
- Балаклава — вязка knitted_fleece, катышки, влажная у рта. Берцы — кожа fabric_leather_02, сбитый носок и сгиб,
  заломы, грязь снизу; подошва, рант, шнурки, люверсы. Молния и кнопки — металл.
- Тело: текстура MakeHuman (CC0), обветренная кожа открытых мест, румянец пятнами, тени под глазами, поры
  и мелкие морщины, грязь в складках рук; подповерхностное рассеяние.
- Глаза: у глаза MakeHuman поверх яблока — оболочка роговицы с прозрачной развёрткой; без учёта прозрачности она
  была чёрным стеклом поверх радужки («чёрные глаза»). Теперь роговица прозрачная с бликом.

Маски «где» — атрибуты вершин wear.py, переложенные в цветовые (W_*), плюс W_Up/W_Low/W_BootLow по геометрии и
маски тела (W_Hands, W_Face, W_Exposed, W_UnderEye) по костям и положению глаз; AO смотреть в Rendered (Cycles).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/npc_texture.py -- [shots] [deliver=<папка>]
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402
from ucup import (MM, U, ao_mask, image, image_layer, layer, noise, owner_mask, proc_layer, reconnect,  # noqa: E402
                  srgb, stack, vmask)

TEX = kc.WORK / "tex"
GEN = kc.WORK / "tex_gen"
MPFB = Path(bpy.utils.resource_path("USER")) / "extensions" / ".user" / "blender_org" / "mpfb" / "data"
PX_PER_M = 1600.0              # как в details.py

DUST = srgb(122, 112, 94)
GRIME = srgb(34, 28, 22)
MUD = srgb(84, 68, 50)


def tex(asset: str, kind: str, res: str = "4k") -> Path:
    d = TEX / asset
    for ext in ("png", "jpg"):
        p = d / f"{asset}_{kind}_{res}.{ext}"
        if p.exists():
            return p
    raise FileNotFoundError(f"{asset} {kind} {res}")


# ---------- маски ----------

def smoothstep(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def put(me: bpy.types.Mesh, name: str, vals: np.ndarray) -> None:
    a = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="BYTE_COLOR", domain="POINT")
    rgba = np.ones((len(vals), 4), np.float32)
    rgba[:, :3] = np.clip(vals, 0.0, 1.0)[:, None]
    a.data.foreach_set("color", rgba.ravel())


def world(obj: bpy.types.Object) -> tuple[np.ndarray, np.ndarray]:
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    nr = np.empty(n * 3, np.float32)
    me.vertex_normals.foreach_get("vector", nr)
    mw = np.array(obj.matrix_world, np.float32)
    w = co.reshape(n, 3) @ mw[:3, :3].T + mw[:3, 3]
    wn = nr.reshape(n, 3) @ np.linalg.inv(mw[:3, :3])
    wn /= np.maximum(np.linalg.norm(wn, axis=1), 1e-9)[:, None]
    return w, wn


def cloth_masks(obj: bpy.types.Object) -> None:
    """Атрибуты износа wear.py (FLOAT) → цветовые W_* (UCUPaint берёт маски из цветовых атрибутов)."""
    me = obj.data
    n = len(me.vertices)

    def f(name: str) -> np.ndarray | None:
        a = me.attributes.get(name)
        if a is None or a.data_type != "FLOAT" or a.domain != "POINT":
            return None
        v = np.empty(n, np.float32)
        a.data.foreach_get("value", v)
        return v
    fold = f("fold")
    if fold is not None:
        put(me, "W_Ridge", np.clip(fold, 0, 1))
        put(me, "W_Valley", np.clip(-fold, 0, 1))
    for src, dst, gain in (("edge", "W_Edge", 1.0), ("seam", "W_Seam", 1.0), ("joint", "W_Joint", 1.0),
                           ("seat", "W_Seat", 1.0), ("touch", "W_Touch", 1.0), ("sun", "W_Sun", 1.0),
                           ("cmp", "W_Cmp", 3.3), ("toe", "W_Toe", 1.0), ("flex", "W_Flex", 1.0),
                           ("breath", "W_Breath", 1.0), ("bd", "W_Bd", 50.0)):
        v = f(src)
        if v is not None:
            put(me, dst, v * gain)
    w, wn = world(obj)
    put(me, "W_Up", smoothstep((wn[:, 2] - 0.15) / 0.6))
    put(me, "W_Low", smoothstep((0.62 - w[:, 2]) / 0.50))
    put(me, "W_BootLow", smoothstep((0.11 - w[:, 2]) / 0.09))
    me.update()


def body_masks(body: bpy.types.Object, eyes: bpy.types.Object) -> None:
    me = body.data
    n = len(me.vertices)
    w, wn = world(body)
    hand_groups = {g.index for g in body.vertex_groups if g.name.startswith(("hand_", "thumb_", "index_", "middle_",
                                                                             "ring_", "pinky_"))}
    hands = np.zeros(n, np.float32)
    for v in me.vertices:
        for g in v.groups:
            if g.group in hand_groups:
                hands[v.index] += g.weight
    hands = np.clip(hands * 1.5, 0, 1)
    bb = [eyes.matrix_world @ Vector(c) for c in eyes.bound_box]
    ec = sum(bb, Vector()) / 8
    half = (max(p.x for p in bb) - min(p.x for p in bb)) / 2
    face = smoothstep((w[:, 2] - (ec.z - 0.09)) / 0.03) * smoothstep((-wn[:, 1] - 0.1) / 0.4)
    under = np.zeros(n, np.float32)
    for sx in (1.0, -1.0):
        cx, cz = sx * half * 0.67, ec.z - 0.017
        d = np.sqrt(((w[:, 0] - cx) / 0.020) ** 2 + ((w[:, 2] - cz) / 0.010) ** 2)
        under = np.maximum(under, smoothstep(1.0 - d) * smoothstep((-wn[:, 1] - 0.2) / 0.4))
    put(me, "W_Hands", hands)
    put(me, "W_Face", face)
    put(me, "W_Exposed", np.maximum(hands, face))
    put(me, "W_UnderEye", under)
    me.update()
    kc.log(f"  тело: руки {int((hands > 0.5).sum())} вершин, лицо {int((face > 0.5).sum())}, под глазами {int((under > 0.3).sum())}")


# ---------- швы и отстрочка (карты details.py) ----------

def detail_maps(obj: bpy.types.Object, name: str) -> dict:
    """Карты details.py и их привязка к развёртке UV_Pattern (тот же холст: границы развёртки ± 1 см)."""
    us = np.array([tuple(lp.uv) for lp in obj.data.uv_layers["UV_Pattern"].data], np.float32)
    umin, umax = us.min(axis=0), us.max(axis=0)
    o = umin - 0.01
    size = (umax - umin) + 0.02
    w, h = int(size[0] * PX_PER_M) + 1, int(size[1] * PX_PER_M) + 1
    height = image(GEN / f"{name}_height.png", color=False)
    assert tuple(height.size) == (w, h), f"{name}: холст {w}×{h}, карта {tuple(height.size)}"
    mask = bpy.data.images.load(str(GEN / f"{name}_mask.png"), check_existing=True)
    mask.colorspace_settings.name = "Non-Color"
    px = np.empty(w * h * 4, np.float32)
    mask.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    out = {}
    settings = bpy.context.scene.render.image_settings
    settings.file_format = "PNG"
    settings.color_depth = "8"
    settings.color_mode = "BW"
    for ch, key in ((0, "thread"), (1, "seamgrime")):
        path = GEN / f"{name}_{key}.png"
        img = bpy.data.images.new(f"{name}_{key}", w, h, alpha=False, float_buffer=False)
        arr = np.ones((h, w, 4), np.float32)
        arr[..., :3] = px[..., ch:ch + 1]
        img.pixels.foreach_set(arr.ravel())
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save_render(str(path))
        bpy.data.images.remove(img)
        out[key] = image(path, color=False)
    s = Vector((PX_PER_M / w, PX_PER_M / h, 1.0))
    out.update(height=height, scale=s, loc=Vector((-o[0] * s.x, -o[1] * s.y, 0.0)))
    return out


def place(entity, scale: Vector, loc: Vector) -> None:
    entity.enable_uniform_scale = False
    U.common.set_entity_prop_value(entity, "scale", scale)
    U.common.set_entity_prop_value(entity, "translation", loc)


def seams(t, d: dict, thread_color, strength: float) -> None:
    """Рельеф шва, грязь в шве, нитка — поверх всего остального (как hook_material в details.py)."""
    lay = image_layer(t, "70 • Швы и отстрочка — рельеф (details.py)", d["height"], "Normal", 1.0, bump=0.0012 * strength)
    place(lay, d["scale"], d["loc"])
    lay = layer(t, "71 • Грязь в шве", GRIME, None, 0.9, amount=0.55)
    m = U.Mask.add_new_mask(lay, "seamgrime", "IMAGE", "UV", "UV_Pattern", image=d["seamgrime"], socket_input_name="Color")
    U.common.get_mask_tree(m).nodes[m.source].extension = "CLIP"
    place(m, d["scale"], d["loc"])
    lay = layer(t, "72 • Нитка отстрочки", thread_color, None, 0.72, amount=0.8)
    m = U.Mask.add_new_mask(lay, "thread", "IMAGE", "UV", "UV_Pattern", image=d["thread"], socket_input_name="Color")
    U.common.get_mask_tree(m).nodes[m.source].extension = "CLIP"
    place(m, d["scale"], d["loc"])


# ---------- рецепты одежды ----------

LEATHER = "fabric_leather_01_clean"
LEATHER_TILE = (0.31, 0.40)


def mat_jacket_leather(mat, details: dict) -> None:
    t, p = stack(mat, srgb(80, 54, 38), 0.0, 0.58, uv="UV_Pattern")
    p.inputs["Specular IOR Level"].default_value = 0.38
    image_layer(t, "00 • Кожа (Poly Haven fabric_leather_01, без шва), окраска", image(tex(LEATHER, "diff"), True),
                "Color", LEATHER_TILE, hsv=(0.515, 0.92, 0.26))
    image_layer(t, "01 • Рельеф кожи", image(tex(LEATHER, "nor_gl"), False), "Normal", LEATHER_TILE, normal_strength=1.25)
    image_layer(t, "02 • Шероховатость кожи", image(tex(LEATHER, "rough"), False), "Roughness", LEATHER_TILE, amount=0.45)
    crease = image(tex("leather_red_02", "nor_gl"), False)
    for attr, label, amount in (("W_Cmp", "в сборках (под мышками, у резинки)", 1.0), ("W_Joint", "на локтях", 0.8)):
        lay = image_layer(t, f"03 • Заломы кожи {label} (leather_red_02)", crease, "Normal", 0.42, amount=amount)
        vmask(lay, attr)
        noise(lay, "Неровно", 30.0, 0.25, 0.75)
    exposed = image(tex(LEATHER, "diff"), True)
    for attr, label, amount, lo, hi in (("W_Edge", "на краях", 0.85, 0.3, 0.7), ("W_Joint", "на локтях", 0.7, 0.35, 0.75),
                                        ("W_Ridge", "на гребнях складок", 0.6, 0.35, 0.7),
                                        ("W_Seam", "у швов", 0.45, 0.3, 0.7), ("W_Cmp", "в сборках", 0.5, 0.35, 0.75)):
        lay = image_layer(t, f"10 • Стёртая до основы отделка {label}", exposed, "Color", LEATHER_TILE,
                          amount=amount, hsv=(0.51, 0.85, 0.62))
        vmask(lay, attr, *((0.55, 1.0) if attr == "W_Ridge" else (None, None)))
        noise(lay, "Пятнами, не по трафарету", 90.0, lo, hi)
    lay = layer(t, "20 • Грязь во впадинах складок", GRIME, None, 0.7, amount=0.55)
    vmask(lay, "W_Valley", 0.5, 1.0)
    ao_mask(lay, 0.05)
    lay = layer(t, "21 • Жирные следы рук (у карманов, полы)", srgb(36, 26, 19), None, 0.42, amount=0.45)
    vmask(lay, "W_Touch")
    noise(lay, "Пятна касаний", 25.0, 0.4, 0.8)
    lay = layer(t, "30 • Пыль сверху (плечи, верх рукавов)", DUST, None, 0.85, amount=0.30)
    vmask(lay, "W_Sun")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.30, 0.10, 0.75)
    seams(t, details, srgb(60, 48, 38), 1.0)
    reconnect(t)


def mat_rib(mat, details: dict) -> None:
    t, p = stack(mat, srgb(30, 29, 27), 0.0, 0.93, uv="UV_Pattern")
    p.inputs["Sheen Weight"].default_value = 0.12
    p.inputs["Sheen Roughness"].default_value = 0.45
    layer(t, "00 • Трикотаж тёмно-серый", srgb(30, 29, 27), 0.0, 0.93)
    image_layer(t, "01 • Вязка (Poly Haven knitted_fleece)", image(tex("knitted_fleece", "diff"), True), "Color", 0.12,
                amount=0.7, hsv=(0.5, 0.12, 0.30))
    image_layer(t, "02 • Петли вязки", image(tex("knitted_fleece", "nor_gl"), False), "Normal", 0.12, normal_strength=0.8)
    lay = proc_layer(t, "03 • Рубчик ~4 мм", "WAVE", "Normal", 78.0, bump=0.0015, box_uv=False)
    src = U.common.get_layer_source(lay)
    if hasattr(src, "bands_direction"):
        src.bands_direction = "X"
    lay = layer(t, "10 • Катышки на трущихся местах", srgb(72, 70, 66), None, 0.97, amount=0.55)
    vmask(lay, "W_Edge")
    noise(lay, "Катышки 2–4 мм", 260.0, 0.62, 0.70)
    lay = layer(t, "20 • Грязь в складках", GRIME, None, 0.95, amount=0.6)
    ao_mask(lay, 0.03)
    seams(t, details, srgb(48, 48, 48), 0.6)
    reconnect(t)


def mat_camo(mat, details: dict | None, pocket: bool = False) -> None:
    t, p = stack(mat, srgb(79, 77, 58), 0.0, 0.86, uv="UV_Pattern")
    p.inputs["Sheen Weight"].default_value = 0.06
    p.inputs["Sheen Roughness"].default_value = 0.5
    image_layer(t, "00 • Камуфляж «Лесополоса» (свой, gen_npc_camo.py)", image(GEN / "camo_lesopolosa_4k.png", True),
                "Color", (1.0, 1.6))
    image_layer(t, "01 • Саржа (Poly Haven denim_fabric_05)", image(tex("denim_fabric_05", "nor_gl"), False), "Normal",
                0.27, normal_strength=0.75)
    image_layer(t, "02 • Шероховатость саржи", image(tex("denim_fabric_05", "rough"), False), "Roughness", 0.27,
                amount=0.35)
    fade = srgb(150, 146, 118)
    for attr, label, amount, lo, hi in (("W_Joint", "на коленях", 0.30, 0.3, 0.8), ("W_Seat", "на сиденье", 0.28, 0.3, 0.8),
                                        ("W_Ridge", "на гребнях складок", 0.18, 0.4, 0.75),
                                        ("W_Edge", "на краях", 0.22, 0.3, 0.75), ("W_Sun", "сверху", 0.14, 0.3, 0.8)):
        lay = layer(t, f"10 • Выгорание и потёртость {label}", fade, None, 0.9, amount=amount)
        vmask(lay, attr, *((0.55, 1.0) if attr == "W_Ridge" else (None, None)))
        noise(lay, "Пятнами", 12.0, lo, hi)
    lay = layer(t, "20 • Грязь во впадинах", GRIME, None, 0.92, amount=0.5)
    ao_mask(lay, 0.05)
    lay = layer(t, "21 • Жирные пятна на бёдрах (вытирают руки)", srgb(40, 37, 26), None, 0.62, amount=0.55)
    vmask(lay, "W_Touch")
    noise(lay, "Пятна", 16.0, 0.55, 0.78)
    lay = layer(t, "29 • Сплошная грязь у самого низа", MUD, None, 0.96, amount=0.7)
    vmask(lay, "W_Low", 0.80, 1.0)
    noise(lay, "Неровная граница", 10.0, 0.2, 0.7)
    lay = layer(t, "30 • Грязь книзу пятнами", MUD, None, 0.96, amount=0.85)
    vmask(lay, "W_Low", 0.35, 0.95)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.45, 0.05, 0.6)
    lay = layer(t, "31 • Брызги выше колен", MUD, None, 0.96, amount=0.7)
    vmask(lay, "W_Low", 0.05, 0.6)
    owner_mask(lay, "05_Брызги_и_высохшие_капли/Брызги_средние_01.png", 0.35, 0.15, 0.6)
    lay = layer(t, "32 • Пыль", DUST, None, 0.95, amount=0.22)
    vmask(lay, "W_Up")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.35, 0.10, 0.75)
    if details is not None:
        seams(t, details, srgb(84, 80, 62), 0.9)
    if pocket:
        # Отстрочка кармана в 4 мм от края: bd (расстояние до края по ткани) / 2 см → полоса 0,2 ± 0,035.
        lay = layer(t, "72 • Нитка отстрочки кармана", srgb(84, 80, 62), None, 0.75)
        m = vmask(lay, "W_Bd")
        MM.add_new_mask_modifier(m, "RAMP")
        ramp = U.common.get_mask_tree(m).nodes[m.modifiers[-1].ramp].color_ramp
        ramp.elements[0].position, ramp.elements[0].color = 0.165, (0, 0, 0, 1)
        ramp.elements[1].position, ramp.elements[1].color = 0.235, (0, 0, 0, 1)
        e = ramp.elements.new(0.20)
        e.color = (1, 1, 1, 1)
    reconnect(t)


def mat_balaclava(mat) -> None:
    t, p = stack(mat, srgb(30, 31, 27), 0.0, 1.0, uv="UVMap")
    p.inputs["Sheen Weight"].default_value = 0.08
    p.inputs["Sheen Roughness"].default_value = 0.6
    p.inputs["Specular IOR Level"].default_value = 0.3
    layer(t, "00 • Вязка тёмно-оливковая", srgb(30, 31, 27), 0.0, 1.0)
    image_layer(t, "01 • Вязка (Poly Haven knitted_fleece)", image(tex("knitted_fleece", "diff"), True), "Color", 0.10,
                amount=0.55, box=True, hsv=(0.5, 0.15, 0.16))
    image_layer(t, "02 • Петли вязки", image(tex("knitted_fleece", "nor_gl"), False), "Normal", 0.10, box=True,
                normal_strength=1.6)
    lay = layer(t, "10 • Катышки", srgb(68, 66, 60), None, 1.0, amount=0.5)
    noise(lay, "Катышки 2–4 мм", 420.0, 0.63, 0.70)
    lay = layer(t, "20 • Влажная от дыхания у рта", srgb(18, 19, 16), None, 0.75, amount=0.6)
    vmask(lay, "W_Breath")
    lay = layer(t, "30 • Грязь в складках", GRIME, None, 1.0, amount=0.5)
    ao_mask(lay, 0.02)
    reconnect(t)


BOOT = "fabric_leather_02_clean"
BOOT_TILE = (0.217, 0.50)


def mat_boot_leather(mat) -> None:
    t, p = stack(mat, srgb(70, 46, 32), 0.0, 0.64, uv="UVMap")
    p.inputs["Specular IOR Level"].default_value = 0.4
    image_layer(t, "00 • Кожа берцев (Poly Haven fabric_leather_02, без шва), окраска", image(tex(BOOT, "diff"), True),
                "Color", BOOT_TILE, box=True, hsv=(0.48, 0.80, 0.24))
    image_layer(t, "01 • Рельеф кожи", image(tex(BOOT, "nor_gl"), False), "Normal", BOOT_TILE, box=True, normal_strength=1.9)
    image_layer(t, "02 • Шероховатость кожи", image(tex(BOOT, "rough"), False), "Roughness", BOOT_TILE, box=True, amount=0.45)
    lay = image_layer(t, "03 • Заломы на сгибе союзки (leather_red_02)", image(tex("leather_red_02", "nor_gl"), False),
                      "Normal", 0.22, box=True)
    vmask(lay, "W_Flex")
    for attr, label, amount in (("W_Toe", "сбитый носок", 0.9), ("W_Flex", "сгиб союзки", 0.6), ("W_Ridge", "гребни", 0.5)):
        lay = image_layer(t, f"10 • Стёртая кожа: {label}", image(tex(BOOT, "diff"), True), "Color", BOOT_TILE, box=True,
                          amount=amount, hsv=(0.5, 0.7, 0.6))
        vmask(lay, attr)
        noise(lay, "Пятнами", 60.0, 0.3, 0.75)
    lay = layer(t, "20 • Грязь во впадинах", GRIME, None, 0.8, amount=0.6)
    ao_mask(lay, 0.02)
    lay = image_layer(t, "30 • Засохшая грязь снизу (Poly Haven brown_mud_dry)", image(tex("brown_mud_dry", "diff"), True),
                      "Color", 0.5, box=True, amount=0.95, hsv=(0.5, 0.8, 0.8))
    vmask(lay, "W_BootLow", 0.1, 0.8)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.25, 0.05, 0.55)
    lay = image_layer(t, "31 • Рельеф засохшей грязи", image(tex("brown_mud_dry", "nor_gl"), False), "Normal", 0.5, box=True)
    vmask(lay, "W_BootLow", 0.1, 0.8)
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.25, 0.05, 0.55)
    lay = layer(t, "32 • Пыль на голенище", DUST, None, 0.9, amount=0.3)
    vmask(lay, "W_Up")
    reconnect(t)


def mat_simple(mat, color, metal: float, rough: float, uv: str, label: str, nor: tuple | None = None,
               mud: bool = False, edge: bool = False) -> None:
    t, p = stack(mat, color, metal, rough, uv=uv)
    layer(t, "00 • " + label, color, metal, rough)
    if nor is not None:
        asset, tile, strength = nor
        image_layer(t, f"01 • Рельеф ({asset})", image(tex(asset, "nor_gl"), False), "Normal", tile, box=True,
                    normal_strength=strength)
    if edge:
        lay = layer(t, "10 • Потёртое на кромках", tuple(min(1.0, c * 1.8 + 0.02) for c in color), metal,
                    max(0.2, rough - 0.12), amount=0.6)
        noise(lay, "Потёртости", 300.0, 0.55, 0.75)
    lay = layer(t, "20 • Грязь во впадинах", GRIME, 0.0, 0.9, amount=0.6)
    ao_mask(lay, 0.012)
    if mud:
        lay = layer(t, "30 • Засохшая грязь снизу", MUD, 0.0, 0.96, amount=0.85)
        vmask(lay, "W_BootLow", 0.1, 0.8)
        owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.25, 0.05, 0.55)
    reconnect(t)


# ---------- тело и глаза ----------

def mat_skin(mat, body: bpy.types.Object) -> None:
    s = body.matrix_world.to_scale().x
    t, p = stack(mat, srgb(196, 150, 128), 0.0, 0.5, uv="UVMap")
    p.inputs["Subsurface Weight"].default_value = 0.25
    p.inputs["Subsurface Radius"].default_value = (1.0, 0.35, 0.2)
    p.inputs["Subsurface Scale"].default_value = 0.006
    diff = MPFB / "skins" / "middleage_caucasian_male" / "middleage_lightskinned_male_diffuse.png"
    image_layer(t, "00 • Кожа (MakeHuman middleage, CC0)", image(diff, True), "Color", 1.0, hsv=(0.5, 1.05, 0.92))
    lay = layer(t, "05 • Обветренная, загорелая кожа открытых мест", srgb(134, 88, 64), None, None, amount=0.62)
    vmask(lay, "W_Exposed")
    lay = layer(t, "06 • Румянец и сосуды пятнами", srgb(165, 82, 70), None, None, amount=0.14)
    vmask(lay, "W_Exposed")
    noise(lay, "Пятна 2–4 см", 30.0 * s, 0.45, 0.80)
    lay = layer(t, "07 • Тени под глазами (недосып)", srgb(92, 66, 66), None, None, amount=0.40)
    vmask(lay, "W_UnderEye")
    proc_layer(t, "10 • Поры", "NOISE", "Normal", 2600.0 * s, bump=0.00012 / s, detail=2.0)
    lay = proc_layer(t, "11 • Мелкие морщины", "NOISE", "Normal", 700.0 * s, bump=0.0002 / s, stretch=(1.0, 0.18, 1.0))
    vmask(lay, "W_Exposed")
    lay = layer(t, "20 • Жирный блеск лица", None, None, 0.36, amount=0.6)
    vmask(lay, "W_Face")
    noise(lay, "Неровно", 40.0 * s, 0.4, 0.8)
    lay = layer(t, "21 • Грязь в складках рук и у ногтей", srgb(52, 40, 30), None, 0.7, amount=0.8)
    vmask(lay, "W_Hands")
    ao_mask(lay, 0.008 / s)
    lay = layer(t, "22 • Разводы грязи на руках", srgb(70, 54, 40), None, 0.65, amount=0.55)
    vmask(lay, "W_Hands")
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.12 / s, 0.15, 0.7)
    reconnect(t)


def mat_eye(mat) -> None:
    """Яблоко — текстура MakeHuman с влажным покрытием; роговица (прозрачные пиксели развёртки) — прозрачная
    с бликом. Раньше прозрачность не учитывалась, и роговица была чёрным стеклом поверх радужки."""
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = image(MPFB / "eyes" / "materials" / "brownlight_eye.png", True)
    nt.links.new(uv.outputs["UV"], img.inputs["Vector"])
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 0.8
    hsv.inputs["Value"].default_value = 0.85
    nt.links.new(img.outputs["Color"], hsv.inputs["Color"])
    eye = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(hsv.outputs["Color"], eye.inputs["Base Color"])
    eye.inputs["Roughness"].default_value = 0.35
    eye.inputs["Coat Weight"].default_value = 1.0
    eye.inputs["Coat Roughness"].default_value = 0.03
    eye.inputs["Subsurface Weight"].default_value = 0.1
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    gloss = nt.nodes.new("ShaderNodeBsdfGlossy")
    gloss.inputs["Roughness"].default_value = 0.02
    cornea = nt.nodes.new("ShaderNodeMixShader")
    cornea.inputs["Fac"].default_value = 0.08
    nt.links.new(clear.outputs[0], cornea.inputs[1])
    nt.links.new(gloss.outputs[0], cornea.inputs[2])
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(img.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(cornea.outputs[0], mix.inputs[1])
    nt.links.new(eye.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    for i, n in enumerate((uv, img, hsv, eye, clear, gloss, cornea, mix, out)):
        n.location = (i * 220 - 900, 0)


def lashes(mat, k: float) -> None:
    """Ресницы MakeHuman тоньше: множитель прозрачности на входе Alpha (мужские ресницы короче и реже)."""
    if mat is None or not mat.node_tree:
        return
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None or not bsdf.inputs["Alpha"].links:
        return
    src = bsdf.inputs["Alpha"].links[0].from_socket
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = k
    nt.links.new(src, mul.inputs[0])
    nt.links.new(mul.outputs[0], bsdf.inputs["Alpha"])
    bsdf.inputs["Base Color"].default_value = (0.02, 0.014, 0.01, 1.0)


# ---------- сборка ----------

def main() -> None:
    args = kc.args_after_dashes()
    src = kc.WORK / f"npc_scav_{kc.VERSION}.blend"
    bpy.ops.wm.open_mainfile(filepath=str(src))
    objs = {o.name: o for o in bpy.data.objects if o.type == "MESH"}
    for name in ("Jacket", "Pants", "Pants_Pocket_L", "Pants_Pocket_R", "Balaclava", "Balaclava_SlotRim", "Boots_L",
                 "Boots_R", "Jacket_Zipper"):
        if name in objs:
            cloth_masks(objs[name])
    body_masks(objs["NPC_Body"], objs["NPC_Eyes"])
    jd = detail_maps(objs["Jacket"], "jacket")
    pd = detail_maps(objs["Pants"], "pants")
    M = bpy.data.materials
    mat_jacket_leather(M["Jacket_Leather"], jd)
    mat_rib(M["Jacket_Rib"], jd)
    mat_camo(M["Pants_Fabric"], pd)
    mat_camo(M["Pocket_Fabric"], None, pocket=True)
    mat_balaclava(M["Balaclava_Knit"])
    mat_boot_leather(M["Boot_Leather"])
    mat_simple(M["Boot_Sole"], srgb(34, 33, 32), 0.0, 0.76, "UVMap", "Подошва, резина", mud=True)
    mat_simple(M["Boot_Rubber"], srgb(30, 29, 28), 0.0, 0.72, "UVMap", "Рант, резина", mud=True)
    mat_simple(M["Boot_Mesh"], srgb(44, 41, 34), 0.0, 0.9, "UVMap", "Вставки из ткани", nor=("waffle_pique_cotton", 0.12, 1.0),
               mud=True)
    mat_simple(M["Boot_Metal"], srgb(58, 56, 52), 1.0, 0.45, "UVMap", "Люверсы, крючки — сталь, чернение", edge=True)
    mat_simple(M["Boot_Lace"], srgb(32, 30, 26), 0.0, 0.85, "UVMap", "Шнурки", nor=("denim_fabric_05", 0.05, 0.8))
    mat_simple(M["Zipper_Tape"], srgb(26, 26, 25), 0.0, 0.85, "UVMap", "Тесьма молнии", nor=("denim_fabric_05", 0.06, 0.7))
    mat_simple(M["Zipper_Metal"], srgb(160, 158, 150), 1.0, 0.32, "UVMap", "Звенья и бегунок — никель", edge=True)
    mat_simple(M["Snap_Metal"], srgb(120, 108, 84), 1.0, 0.38, "UVMap", "Кнопки — латунь, старая", edge=True)
    mat_skin(M["NPC_Skin"], objs["NPC_Body"])
    mat_eye(M["NPC_Eye"])
    lashes(M.get("NPC_Body.eyelashes01"), 0.55)
    bpy.context.scene.render.engine = "CYCLES"
    out = kc.WORK / f"npc_scav_{kc.VERSION}_tex.blend"
    kc.save(out)
    kc.log("NPC_TEX →", out)
    if "shots" in args:
        shots()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(Path(dest))


def shots() -> None:
    kc.studio()
    kc.gpu_cycles(192)
    scene = bpy.context.scene
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.denoising_prefilter = "ACCURATE"
    out = kc.WORK / "previews"
    eyes = bpy.data.objects["NPC_Eyes"]
    ec = sum((eyes.matrix_world @ Vector(c) for c in eyes.bound_box), Vector()) / 8
    views = {
        "tex_front": ((0.0, -3.6, 1.0), (0.0, 0.0, 0.95), 50, (1000, 1400)),
        "tex_34": ((2.2, -2.9, 1.15), (0.0, 0.0, 0.95), 50, (1000, 1400)),
        "tex_eyes": ((ec.x + 0.05, ec.y - 0.30, ec.z + 0.02), (ec.x, ec.y, ec.z), 70, (1400, 800)),
        "tex_chest": ((0.35, -0.75, 1.22), (0.05, -0.08, 1.12), 70, (1400, 1100)),
        "tex_legs": ((0.45, -1.05, 0.55), (0.05, 0.0, 0.45), 60, (1100, 1400)),
        "tex_hand": ((0.75, -0.45, 0.95), (0.42, -0.02, 0.90), 55, (1200, 1000)),
    }
    for name, (pos, tgt, lens, size) in views.items():
        kc.render(kc.camera("C_" + name, pos, tgt, lens), out / f"scav_{kc.VERSION}_{name}.png", size, 192)


def deliver(folder: Path) -> None:
    """Файл на просмотр: студия, камеры, вьюпорт в Rendered (Cycles), всё упаковано."""
    import armor_mid as am
    readme = (f"NPC «мародёр» {kc.VERSION} — ТЕКСТУРЫ v01 на просмотр (тело и одежда, нативный UCUPaint 2.4.9).\n"
              "Куртка сшита ближе к телу (была «толстой»), молния вшита под кромки полочек, глаза — прозрачная роговица.\n"
              "Слои у каждого материала: фото 4K (Poly Haven CC0), камуфляж «Лесополоса» (свой), износ по маскам вещи\n"
              "(атрибуты W_*), грязь во впадинах (AO), «Маски_АЛЬФА» владельца. Смотреть в Rendered (Cycles).\n"
              "Скрипт: tools/npc_kit/npc_texture.py.\n")
    am.deliver(folder, f"NPC_Marauder_{kc.VERSION}_текстуры.blend", readme, focus_z=1.0)


if __name__ == "__main__":
    main()
