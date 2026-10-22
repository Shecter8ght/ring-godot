"""NPC: шлемы — текстуры в нативном UCUPaint 2.4.9 (форма v02 принята владельцем 2026-10-22).

Тем же приёмом, что принятая броня (armor_texture.py, образец вида — Sketchfab «Tactical Body Armor Pack1»):
ткань чехлов, стропа, велкро и фурнитура — рецептами брони своего уровня, чтобы комплект совпадал.
Расцветка (решение владельца 2026-10-22): простой — зелёная краска по стали, ношеная (выгорание, царапины, сколы
до стали по кромке и редкие на куполе, ржавчина в части сколов); средний — оливковый чехол, как средняя броня;
крутой — чехол «пиксельный лес», как крутая броня, планки, площадка ПНВ, фонарь и фурнитура чёрные.
Износ у всех — «ношеный», как у брони.

Маски «где» — атрибуты вершин брони (ArmorEdge/Up/Low/Under/Front по геометрии каждого шлема), AO — впадины,
пятна и сколы — «Маски_АЛЬФА» владельца. Развёртка шлемов приведена к метрам (площадь развёртки = площади
поверхности, исходная сохранена слоем UV_Форма) — плетение и камуфляж в том же масштабе, что на броне.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/helmet_texture.py -- [shots] [deliver=<папка>]
→ _asset_src/npc_kit/helmets/helmets_tex.blend (читает helmets.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_texture as at  # noqa: E402
import kit_common as kc  # noqa: E402
from ucup import H, U, ao_mask, image, image_layer, layer, noise, owner_mask, proc_layer, srgb, stack, vmask  # noqa: E402

HELMETS = kc.WORK / "helmets"
TIERS = {"06_Helmet_Simple": "Simple", "06_Helmet_Mid": "Mid", "06_Helmet_Top": "Top"}
VERSION = "v01"

at.PALETTE["simple"] = {"webbing": srgb(86, 80, 56)}       # хлопковый подбородочный ремень хаки
at.PALETTE["black"] = {"plastic": srgb(27, 27, 28)}        # чёрный полимер: планки, рычаги забрала, фурнитура

PAINT = srgb(62, 70, 48)          # защитный зелёный каски
STEEL = srgb(92, 90, 86)
RUST = srgb(96, 60, 38)
CHIPS = "10_Сколы_и_потёртости_покрытия/"


# ---------- развёртка в метрах ----------

def metric_uv(obj: bpy.types.Object) -> float:
    """Развёртку детали — в метры (купол развёрнут «шапкой» в своих единицах); исходная остаётся слоем UV_Форма."""
    me = obj.data
    uv = me.uv_layers.get("UV")
    if uv is None or not me.polygons:
        return 1.0
    if "UV_Форма" not in me.uv_layers:
        keep = me.uv_layers.new(name="UV_Форма", do_init=True)
        for a, b in zip(keep.data, uv.data):
            a.uv = b.uv
    # масштаб — медиана по граням: шов замкнутой трубки и мелочь с условной развёрткой (кнопки, винты) не в счёт
    ratios = []
    for p in me.polygons:
        pts = [uv.data[li].uv for li in p.loop_indices]
        a2 = abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
                     for i in range(len(pts)))) / 2
        if a2 > 1e-14 and p.area > 1e-12:
            ratios.append(p.area / a2)
    if not ratios:
        return 1.0
    ratios.sort()
    k = math.sqrt(ratios[len(ratios) // 2])
    for d in uv.data:
        d.uv = d.uv * k
    me.uv_layers.active = uv
    uv.active_render = True
    return k


def helmet_masks(obj: bpy.types.Object) -> None:
    """Маски брони, пересчитанные под шлем: у брони «верх» — плечи и кромки, у шлема вверх смотрит весь купол —
    пыль и выгорание только на макушке; «книзу» — нижняя треть каждой детали (у купола — у кромки, у забрала —
    низ, у ремня — у подбородка); брызг спереди внизу на шлеме нет."""
    import numpy as np
    me = obj.data
    n = len(me.vertices)
    if n == 0:
        return
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", co)
    nrm = np.empty(n * 3, np.float32)
    me.vertex_normals.foreach_get("vector", nrm)
    mw = np.array(obj.matrix_world, np.float32)
    world = co.reshape(n, 3) @ mw[:3, :3].T + mw[:3, 3]
    wn = nrm.reshape(n, 3) @ np.linalg.inv(mw[:3, :3])
    wn /= np.maximum(np.linalg.norm(wn, axis=1), 1e-9)[:, None]
    z = world[:, 2]
    z_lo, z_hi = float(z.min()), float(z.max())
    masks = {
        "ArmorUp": at.smoothstep((wn[:, 2] - 0.62) / 0.33),
        "ArmorLow": at.smoothstep((z_hi - z) / max(z_hi - z_lo, 1e-6) * 1.5 - 0.75),
        "ArmorFront": np.zeros(n, np.float32),
    }
    for name, val in masks.items():
        a = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="BYTE_COLOR", domain="POINT")
        rgba = np.ones((n, 4), np.float32)
        rgba[:, :3] = val[:, None]
        a.data.foreach_set("color", rgba.ravel())
    me.update()


# ---------- рецепты, которых нет у брони ----------

def mat_steel_paint(mat: bpy.types.Material, tier: str) -> None:
    t, _ = stack(mat, PAINT, 0.0, 0.72)
    layer(t, "00 • Краска по стали, защитный зелёный (матовая)", PAINT, 0.0, 0.72)
    lay = layer(t, "05 • Неровный слой краски", at.GRIME, None, None, 0.12)
    noise(lay, "Пятна толщины 4–10 см", 12.0, 0.35, 0.80)
    proc_layer(t, "08 • Шагрень краски", "NOISE", "Normal", 350.0, bump=0.00012)
    lay = layer(t, "20 • Выгорание сверху", at.FADE, None, 0.70, 0.20)
    vmask(lay, "ArmorUp")
    noise(lay, "Неровно, пятнами", 6.0, 0.30, 0.85, shift=(0.3, 0.1, 0.2))
    lay = layer(t, "25 • Мелкие царапины по краске (до грунта не доходят)", srgb(112, 116, 98), None, 0.55, 0.55)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 0.22, 0.35, 0.75)
    lay = layer(t, "30 • Сколы до стали по кромке", STEEL, 1.0, 0.48, 0.95)
    vmask(lay, "ArmorEdge", 0.04, 0.30)
    owner_mask(lay, CHIPS + "Сколы_с_потёртостями_01.png", 0.14, 0.22, 0.60)
    lay = layer(t, "31 • Ржавчина в сколах кромки", RUST, 0.0, 0.85, 0.55)
    vmask(lay, "ArmorEdge", 0.04, 0.30)
    owner_mask(lay, CHIPS + "Сколы_с_потёртостями_01.png", 0.18, 0.45, 0.75)
    noise(lay, "Не во всех сколах", 30.0, 0.40, 0.70)
    lay = layer(t, "32 • Редкие сколы на куполе (удары)", STEEL, 1.0, 0.50, 0.75)
    owner_mask(lay, CHIPS + "Сколы_пятнами_01.png", 0.30, 0.62, 0.80)
    lay = layer(t, "33 • Ржавчина в сколах купола", RUST, 0.0, 0.85, 0.40)
    owner_mask(lay, CHIPS + "Сколы_пятнами_01.png", 0.30, 0.68, 0.82)
    noise(lay, "Не во всех сколах", 30.0, 0.40, 0.70, shift=(0.2, 0.4, 0.1))
    lay = layer(t, "40 • Пыль сверху", at.DUST, None, 0.95, 0.22)
    vmask(lay, "ArmorUp")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.35, 0.12, 0.75)
    lay = layer(t, "50 • Грязь во впадинах и под отгибом", at.GRIME, None, 0.90, 0.60)
    ao_mask(lay, 0.02)
    noise(lay, "Неровный край осадка", 40.0, 0.25, 0.75)
    lay = layer(t, "60 • Грязь по низу", at.DIRT, None, 0.92, 0.50)
    vmask(lay, "ArmorLow")
    owner_mask(lay, "04_Грязь_и_налёт/Грязь_пятнами_01.png", 0.40, 0.10, 0.70)
    lay = layer(t, "65 • Затёрто руками по краю (сальный блеск)", None, None, 0.42, 0.50)
    vmask(lay, "ArmorLow")
    owner_mask(lay, "02_Отпечатки_ладоней/Ладонь_растёртая_01.png", 0.25, 0.20, 0.70)
    H.reconnect(U, t)


def mat_rivets(mat: bpy.types.Material, tier: str) -> None:
    t, _ = stack(mat, PAINT, 0.0, 0.62)
    layer(t, "00 • Заклёпки, крашены с каской", PAINT, 0.0, 0.62)
    lay = layer(t, "30 • Шляпки стёрты до стали", STEEL, 1.0, 0.45, 0.70)
    noise(lay, "Стёртость пятнами", 260.0, 0.35, 0.65)
    lay = layer(t, "35 • Ржавчина у шляпок", RUST, 0.0, 0.85, 0.40)
    ao_mask(lay, 0.003)
    H.reconnect(U, t)


def mat_leatherette(mat: bpy.types.Material, tier: str) -> None:
    col = srgb(48, 33, 24)
    t, _ = stack(mat, col, 0.0, 0.60)
    layer(t, "00 • Кожзам подтулейника", col, 0.0, 0.60)
    image_layer(t, "10 • Фактура кожзама (Poly Haven brown_leather)",
                image(at.TEX / "brown_leather" / "brown_leather_nor_gl_2k.png", False), "Normal", 0.25)
    lay = layer(t, "20 • Пот и сало (темнее, блестит)", at.GRIME, None, 0.38, 0.45)
    noise(lay, "Пятна пота", 14.0, 0.35, 0.80)
    lay = layer(t, "30 • Потёртые кромки", srgb(84, 62, 46), None, 0.70, 0.40)
    vmask(lay, "ArmorEdge")
    noise(lay, "Разрыв потёртости", 120.0, 0.35, 0.70)
    lay = layer(t, "50 • Грязь в складках", at.GRIME, None, 0.90, 0.50)
    ao_mask(lay, 0.01)
    H.reconnect(U, t)


def mat_anodized(mat: bpy.types.Material, tier: str) -> None:
    col = srgb(34, 34, 36)
    t, _ = stack(mat, col, 1.0, 0.42)
    layer(t, "00 • Алюминий, чёрное анодирование", col, 1.0, 0.42)
    lay = layer(t, "10 • Зерно анодирования", None, None, 0.50, 0.50)
    noise(lay, "Зерно", 900.0, 0.40, 0.70)
    lay = layer(t, "30 • Кромки стёрты до алюминия", srgb(168, 168, 170), 1.0, 0.30, 0.80)
    vmask(lay, "ArmorEdge", 0.20, 0.70)
    owner_mask(lay, "24_Износ_кромок_до_металла/Кромка_05_Прямая_мелкие_сколы.png", 0.08, 0.30, 0.70)
    lay = layer(t, "35 • Царапины", srgb(120, 120, 122), 1.0, 0.35, 0.50)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 0.12, 0.50, 0.80)
    lay = layer(t, "50 • Пыль в пазах", at.DUST, 0.0, 0.90, 0.55)
    ao_mask(lay, 0.005)
    lay = layer(t, "55 • Жирные следы пальцев", None, None, 0.25, 0.50)
    owner_mask(lay, "01_Отпечатки_пальцев/Отпечаток_смазанный_вправо_01.png", 0.06, 0.30, 0.70)
    H.reconnect(U, t)


def mat_rubber(mat: bpy.types.Material, tier: str) -> None:
    col = srgb(26, 26, 26)
    t, _ = stack(mat, col, 0.0, 0.78)
    layer(t, "00 • Резина окантовки", col, 0.0, 0.78)
    lay = layer(t, "10 • Зерно резины", None, None, 0.86, 0.50)
    noise(lay, "Зерно", 600.0, 0.40, 0.70)
    lay = layer(t, "30 • Белёсые потёртости на кромке", srgb(70, 70, 68), None, 0.85, 0.50)
    vmask(lay, "ArmorEdge")
    noise(lay, "Разрыв потёртости", 180.0, 0.32, 0.70)
    lay = layer(t, "40 • Пыль сверху", at.DUST, None, 0.95, 0.30)
    vmask(lay, "ArmorUp")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_пятнами_01.png", 0.30, 0.12, 0.75)
    lay = layer(t, "60 • Грязь снизу", at.DIRT, None, 0.92, 0.50)
    vmask(lay, "ArmorUnder")
    owner_mask(lay, "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png", 0.25, 0.08, 0.65)
    H.reconnect(U, t)


def mat_glass(mat: bpy.types.Material, tier: str) -> None:
    """Поликарбонат забрала и стекло фонаря: прозрачный (пропускание 1), износ — в шероховатости и пыли."""
    col = (0.90, 0.93, 0.92)
    t, p = stack(mat, col, 0.0, 0.04)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = 1.58
    layer(t, "00 • Поликарбонат", col, 0.0, 0.04)
    lay = layer(t, "20 • Мелкие царапины (протирали рукавом)", None, None, 0.22, 0.60)
    owner_mask(lay, "09_Царапины/Царапины_мелкие_01.png", 0.15, 0.40, 0.80)
    lay = layer(t, "25 • Разводы от протирания", None, None, 0.16, 0.60)
    owner_mask(lay, "06_Разводы_и_следы_протирания/Протирание_дугами_с_грязью_01.png", 0.30, 0.30, 0.80)
    lay = layer(t, "40 • Пыль по низу забрала", at.DUST, None, 0.60, 0.45)
    vmask(lay, "ArmorLow")
    owner_mask(lay, "03_Пыль_и_частицы/Пыль_редкая_01.png", 0.20, 0.20, 0.70)
    lay = layer(t, "45 • Отпечатки пальцев у краёв", None, None, 0.30, 0.50)
    vmask(lay, "ArmorEdge")
    owner_mask(lay, "01_Отпечатки_пальцев/Отпечаток_растёртый_01.png", 0.07, 0.30, 0.70)
    H.reconnect(U, t)


# (уровень, вид материала) → рецепт: ткань, стропа, велкро, фурнитура — рецептами брони того же уровня
RECIPES = {
    ("Simple", "Steel_Paint"): mat_steel_paint,
    ("Simple", "Metal"): mat_rivets,
    ("Simple", "Leatherette"): mat_leatherette,
    ("Simple", "Webbing"): lambda m, t: at.mat_webbing(m, "simple"),
    ("Simple", "Plastic"): lambda m, t: at.mat_metal(m, "simple"),          # пряжка ремня — стальная
    ("Mid", "Cover"): lambda m, t: at.mat_cordura(m, "mid"),
    ("Mid", "Velcro"): lambda m, t: at.mat_velcro(m, "mid"),
    ("Mid", "Webbing"): lambda m, t: at.mat_webbing(m, "mid"),
    ("Mid", "Plastic"): lambda m, t: at.mat_plastic(m, "mid"),
    ("Mid", "Metal"): lambda m, t: at.mat_metal(m, "mid"),
    ("Mid", "Anodized"): mat_anodized,
    ("Top", "Shell"): lambda m, t: at.mat_cordura(m, "top"),                # чехол «пиксельный лес»
    ("Top", "Rubber"): mat_rubber,
    ("Top", "Plastic"): lambda m, t: at.mat_plastic(m, "black"),
    ("Top", "Velcro"): lambda m, t: at.mat_velcro(m, "top"),
    ("Top", "Metal"): lambda m, t: at.mat_metal(m, "top"),
    ("Top", "Webbing"): lambda m, t: at.mat_webbing(m, "top"),
    ("Top", "Anodized"): mat_anodized,
    ("Top", "Visor_Glass"): mat_glass,
}


def split_materials(col: bpy.types.Collection, prefix: str) -> set[bpy.types.Material]:
    """Общие материалы формы (Helmet_*) — свои у каждого шлема (Simple_*, Mid_*, Top_*); площадка ПНВ и фонарь —
    анодированный алюминий, а не пластик."""
    out = set()
    for o in col.objects:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            m = slot.material
            if m is None:
                continue
            kind = m.name.split("_", 1)[1]
            if "NVG_Mount" in o.name or "Flashlight" in o.name:
                kind = "Anodized"
            name = f"{prefix}_{kind}"
            new = bpy.data.materials.get(name) or m.copy()
            new.name = name
            slot.material = new
            out.add(new)
    return out


def local_ao(mat: bpy.types.Material) -> int:
    """Маски «впадины» (AO) — только по своей детали: забрало в 3 см перед куполом и рычаги не делают из лба
    «впадину» с грязью. Узел Ambient Occlusion источника маски — Only Local."""
    tree = next((n.node_tree for n in mat.node_tree.nodes if n.type == "GROUP" and n.node_tree
                 and n.node_tree.yp.is_ypaint_node), None)
    if tree is None:
        return 0
    done = 0
    for lay in tree.yp.layers:
        for m in lay.masks:
            if m.type != "AO":
                continue
            node = U.common.get_mask_tree(m).nodes.get(m.source)
            if node is not None and hasattr(node, "only_local"):
                node.only_local = True
                done += 1
    return done


# ---------- снимки ----------

def shots() -> None:
    import numpy as np
    import helmets as hm
    at.sample_studio()
    out = HELMETS / "previews"
    views = {"34": ((0.50, -0.70, 1.82), (0.0, -0.05, 1.71)), "back": ((-0.45, 0.70, 1.84), (0.0, -0.03, 1.71)),
             "macro": ((0.16, -0.40, 1.80), (0.02, -0.14, 1.75))}
    paths = []
    for col_name in TIERS:
        hm.show_only(col_name)
        for v, (pos, tgt) in views.items():
            p = out / f"{col_name[10:].lower()}_tex_{v}.png"
            kc.render(kc.camera("Tex_h_" + v, pos, tgt, 60), p, (900, 900), at.SAMPLES)
            paths.append(p)
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    grid = np.zeros((h * 3, w * 3, 4), np.float32)
    for k, im in enumerate(imgs):
        r, c = divmod(k, 3)
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        grid[(2 - r) * h:(3 - r) * h, c * w:(c + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("helmets_tex_grid", w * 3, h * 3, alpha=False)
    res.pixels.foreach_set(grid.ravel())
    s = bpy.context.scene.render.image_settings
    s.file_format = "JPEG"
    s.quality = 90
    s.color_mode = "RGB"
    res.save_render(str(out / f"helmets_tex_{VERSION}.jpg"))
    kc.log("SHOTS", out / f"helmets_tex_{VERSION}.jpg")


README = (
    "Шлемы трёх уровней — ТЕКСТУРЫ {ver} на просмотр (форма v02 принята), на мародёре v03.\n"
    "Нативный UCUPaint 2.4.9 тем же приёмом, что броня: у каждого материала свой стек слоёв. Простой — зелёная\n"
    "краска по стали, ношеная (выгорание, царапины, сколы до стали по кромке и редкие на куполе, ржавчина в части\n"
    "сколов), кожзам подтулейника, ремень хаки; средний — оливковый чехол, стропа и велкро как у средней брони,\n"
    "площадка ПНВ — чёрный анодированный алюминий; крутой — чехол «пиксельный лес» как крутая броня, резиновая\n"
    "окантовка, чёрные планки и фурнитура, фонарь и площадка ПНВ — анодированный алюминий, забрало — прозрачный\n"
    "поликарбонат с царапинами и разводами.\n"
    "Переключение — галочки (глаз) коллекций в Outliner: 06_Helmet_Simple / 06_Helmet_Mid / 06_Helmet_Top,\n"
    "по одному. Смотреть в Rendered (Cycles): маски AO (грязь во впадинах) в Material Preview не видны.\n"
    "Скрипт: tools/npc_kit/helmet_texture.py (форма — helmets.py).\n")


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(HELMETS / "helmets.blend"))
    for col_name in TIERS:
        lc = bpy.context.view_layer.layer_collection.children.get(col_name)
        if lc is not None:
            lc.hide_viewport = False
    for col_name, prefix in TIERS.items():
        col = bpy.data.collections[col_name]
        objs = [o for o in col.objects if o.type == "MESH"]
        zs = [(o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box]
        for o in objs:
            at.geometry_masks(o, min(zs), max(zs))
            helmet_masks(o)
            k = metric_uv(o)
            kc.log(f"  {o.name}: развёртка ×{k:.2f}")
        for mat in sorted(split_materials(col, prefix), key=lambda m: m.name):
            kind = mat.name.split("_", 1)[1]
            recipe = RECIPES.get((prefix, kind))
            if recipe is None:
                kc.log("  материал без рецепта:", mat.name)
                continue
            recipe(mat, prefix)
            kc.log("  стек UCUPaint:", mat.name, "| AO только по детали:", local_ao(mat))
    for name in [m.name for m in bpy.data.materials if m.name.startswith("Helmet_") and m.users == 0]:
        bpy.data.materials.remove(bpy.data.materials[name])
    bpy.context.scene.render.engine = "CYCLES"
    import helmets as hm
    hm.show_only("06_Helmet_Mid")
    out = HELMETS / "helmets_tex.blend"
    kc.save(out)
    kc.log("HELMET_TEX →", out)
    if "shots" in args:
        shots()
        hm.show_only("06_Helmet_Mid")
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        am.deliver(Path(dest), f"Шлемы_{VERSION}_текстуры.blend", README.format(ver=VERSION), focus_z=1.66, near=0.45)


if __name__ == "__main__":
    main()
