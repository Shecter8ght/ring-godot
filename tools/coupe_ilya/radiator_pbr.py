"""Купе Ильи, радиатор с патрубками: PBR в нативном UCUPaint на принятой форме v01.

Решения владельца (2026-10-18): образец отделки — тот же, что у кузова купе (ещё не получен); состояние
«рабочий, с машины 2–3 лет»; бирка — крафт с чёрным маркером. Рабочий: светлый алюминий с матовым налётом
флюса пайки, спереди дорожная пыль и мошки в ламелях, у горловин засохший антифриз, патрубки матовые,
хомуты из нержавейки со следами ключа (их откручивали), грязные отпечатки там, где радиатор снимали и несли,
пыль на верхних гранях — лежал в кладовой.

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
        --python tools/coupe_ilya/radiator_pbr.py -- build | preview | render | inspect
  build   → models/items/Radiator_Ilya_v01_pbr.blend из развёртки Radiator_Ilya_v01_uv.blend
            (radiator_uv.py); маски-картинки владельца упакованы в файл
  preview → то же в памяти, без сохранения, сразу снимки (RAD_SHOTS=01,03 — выборочно; RAD_SAMPLES)
  render  → снимки из сохранённого файла в checks/radiator/pbr_v01
  inspect → стеки, слои, маски, подключение групп к BSDF, упаковка картинок → checks/radiator/pbr_v01/stack.json

Форма не меняется: пишутся только цветовые атрибуты (где копится пыль, грязь, антифриз, где брали руками).
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

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import radiator as rad  # noqa: E402

LIB = Path("E:/Models Blender/VEHICLES/Купе Ильи")
UVSRC = LIB / "models/items/Radiator_Ilya_v01_uv.blend"
MASTER = LIB / "models/items/Radiator_Ilya_v01_pbr.blend"
VIEW = LIB / "checks/radiator/pbr_v01"
MASKS = Path("E:/Models Blender/Маски_АЛЬФА")
SKILL = Path("C:/Users/Schecter_8ght/.claude/skills/weapon-asset-texturing")
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "build"
UV = "UVMap"
U = H = None

# линейные цвета
ALU = (0.50, 0.51, 0.52)
FLUX = (0.60, 0.60, 0.58)
PA_BLACK = (0.020, 0.020, 0.021)
EPDM = (0.025, 0.025, 0.026)
ROAD = (0.11, 0.09, 0.065)
GRIME = (0.035, 0.03, 0.024)
DUST = (0.30, 0.28, 0.25)
BUGS = (0.03, 0.025, 0.015)
COOL_CRUST = (0.56, 0.45, 0.47)        # засохший розово-фиолетовый антифриз (G12-подобный): белёсая корка
COOL_FILM = (0.26, 0.10, 0.14)         # он же гуще по краю корки — приглушённый розовый
KRAFT = (0.41, 0.24, 0.12)

MASK_FILES = {
    "splash": "05_Брызги_и_высохшие_капли/Брызги_средние_01.png",
    "drops": "05_Брызги_и_высохшие_капли/Капли_тонкие_контуры_01.png",
    "dust": "03_Пыль_и_частицы/Пыль_пятнами_01.png",
    "dust_sparse": "03_Пыль_и_частицы/Пыль_редкая_01.png",
    "grime": "04_Грязь_и_налёт/Грязь_пятнами_01.png",
    "film": "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png",
    "print": "01_Отпечатки_пальцев/Отпечаток_грязный_01.png",
    "print_smear": "01_Отпечатки_пальцев/Отпечаток_смазанный_по_диагонали_01.png",
    "wipe": "06_Разводы_и_следы_протирания/Разводы_редкие_01.png",
}


def native() -> None:
    global U, H
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
    spec = importlib.util.spec_from_file_location("ucupaint_helpers", SKILL / "scripts/ucupaint_helpers.py")
    H = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(H)
    U = H.load_ucupaint()
    print("RAD ucupaint", U.common.get_current_version_str(), flush=True)


def activate(ob, slot: int = 0) -> None:
    for o in bpy.context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    ob.active_material_index = slot


# ---------------------------------------------------------------- где что копится: атрибуты по геометрии

def _corners(ob):
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
    return world[idx], nrm


def _write(me, name: str, arr: np.ndarray) -> None:
    attr = me.color_attributes.get(name) or me.color_attributes.new(name=name, type="FLOAT_COLOR", domain="CORNER")
    rgba = np.ones((len(me.loops), 4), np.float32)
    rgba[:, :3] = np.clip(arr, 0, 1).astype(np.float32)[:, None]
    attr.data.foreach_set("color", rgba.ravel())


def paint_attrs() -> None:
    """FaceUp — верхние грани (пыль), Low — низ (брызги с дороги), Front — грани вперёд, Coolant — антифриз
    у горловин и потёки, Grab — где брали руками, HoseInner — внутренность патрубков."""
    off = rad.CAR_POS
    back_y = rad.TANK_YC + rad.TANK_D / 2 - off[1]
    necks = [(np.array([rad.NECK_UP[0], back_y - 0.004, rad.NECK_UP[1] - off[2]]), rad.NECK_UP[2] / 2),
             (np.array([rad.NECK_LO[0], back_y - 0.004, rad.NECK_LO[1] - off[2]]), rad.NECK_LO[2] / 2)]
    paths = {k: p - off for k, p in rad.hose_paths().items()}
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        p, n = _corners(ob)
        x, y, z = p[:, 0], p[:, 1], p[:, 2]
        up = np.clip(n[:, 2], 0, 1) ** 1.5
        low = np.clip(1 - z / 0.10, 0, 1)
        front = np.clip(-n[:, 1], 0, 1)
        coolant = np.zeros(len(p))
        grab = np.zeros(len(p))
        inner = np.zeros(len(p))
        if ob.name.startswith("Radiator_Tank"):
            for c, r in necks:
                if np.sign(c[0]) != np.sign(x.mean()):
                    continue
                d_ax = np.hypot(x - c[0], z - c[2])
                on_neck = (y > back_y - 0.002) & (d_ax < r + 0.006)
                joint = on_neck * np.exp(-((y - (c[1] + 0.014)) / 0.010) ** 2)
                ring = (n[:, 1] > 0.5) * np.exp(-((d_ax - (r + 0.006)) / 0.007) ** 2) * (y > back_y - 0.003)
                dz = c[2] - z
                drip = ((n[:, 1] > 0.4) * (dz > 0.01) * np.exp(-((x - c[0] - 0.004) / 0.009) ** 2)
                        * np.clip(1 - dz / 0.13, 0, 1) ** 0.7)
                coolant = np.maximum.reduce([coolant, 0.85 * joint, 0.7 * ring, 0.9 * drip])
            grab = np.clip((z - 0.30) / 0.06, 0, 1) * (np.abs(n[:, 0]) > 0.4)
        elif ob.name in ("Hose_Upper", "Hose_Lower"):
            path = paths["upper" if ob.name == "Hose_Upper" else "lower"]
            s_path = np.r_[0, np.cumsum(np.linalg.norm(np.diff(path, axis=0), axis=1))]
            L = s_path[-1]
            d2 = ((p[:, None, :] - path[None, :, :]) ** 2).sum(-1)
            k = d2.argmin(1)
            dist, s = np.sqrt(d2[np.arange(len(p)), k]), s_path[k]
            od = rad.HOSE_UP_OD if ob.name == "Hose_Upper" else rad.HOSE_LO_OD
            inner = (dist < od / 2 - rad.HOSE_WALL + 0.001).astype(float)
            coolant = np.maximum(inner * np.exp(-(L - s) / 0.03), (1 - inner) * (s < 0.005) * 0.6)
            grab = (1 - inner) * np.maximum(np.exp(-((s - (L - 0.045)) / 0.03) ** 2), 0.6 * np.exp(-((s - 0.03) / 0.025) ** 2))
        elif "Clamps" in ob.name:
            grab = np.full(len(p), 0.6)
        me = ob.data
        for name, arr in (("FaceUp", up), ("Low", low), ("Front", front), ("Coolant", coolant), ("Grab", grab),
                          ("HoseInner", inner)):
            _write(me, name, arr)
        me.update()


# ---------------------------------------------------------------- маски бачков по развёртке (попиксельно)
# У бачков большие плоские грани: вершины только вверху и внизу, атрибут на вершинах не нарисует потёк
# посередине грани. Поэтому эти маски считаются в каждом пикселе развёртки по настоящей точке поверхности.

def _necks():
    off = rad.CAR_POS
    back_y = rad.TANK_YC + rad.TANK_D / 2 - off[1]
    return back_y, [(np.array([rad.NECK_UP[0], back_y - 0.004, rad.NECK_UP[1] - off[2]]), rad.NECK_UP[2] / 2),
                    (np.array([rad.NECK_LO[0], back_y - 0.004, rad.NECK_LO[1] - off[2]]), rad.NECK_LO[2] / 2)]


def coolant_tank(p: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Засохший антифриз: тонкая корка по краю патрубка на горловине, у основания бобышки, два потёка вниз."""
    back_y, necks = _necks()
    x, y, z = p[:, 0], p[:, 1], p[:, 2]
    out = np.zeros(len(p))
    for c, r in necks:
        side = np.sign(x) == np.sign(c[0])
        d_ax = np.hypot(x - c[0], z - c[2])
        hose_edge = c[1] + 0.014                                    # где кончается надетый патрубок
        joint = (d_ax < r + 0.0015) * np.exp(-((y - hose_edge + 0.0015) / 0.0022) ** 2)
        root = (n[:, 1] > 0.4) * (y > back_y - 0.002) * np.exp(-((d_ax - (r + 0.0052)) / 0.0022) ** 2)
        dz = c[2] - z
        wob = 0.0018 * np.sin(dz * 95.0)
        back = (n[:, 1] > 0.4) * (y > back_y - 0.002)
        drip1 = back * (dz > r) * np.exp(-((x - c[0] - 0.007 - wob) / 0.0034) ** 2) * np.clip(1 - (dz - r) / 0.10, 0, 1) ** 0.6
        drip2 = back * (dz > r) * np.exp(-((x - c[0] + 0.009 + 0.7 * wob) / 0.0024) ** 2) * np.clip(1 - (dz - r) / 0.05, 0, 1) ** 0.8
        out = np.maximum.reduce([out, side * 0.9 * joint, side * 0.6 * root, side * 0.9 * drip1, side * 0.7 * drip2])
    return out


def grab_tank(p: np.ndarray, n: np.ndarray) -> np.ndarray:
    """Где держали руками, снимая и неся: верх наружных боковин бачков."""
    return np.clip((p[:, 2] - 0.29) / 0.05, 0, 1) * (np.abs(n[:, 0]) > 0.4)


def bake_uv_mask(objects: list, func, res: int, name: str):
    """Маска по развёртке: в каждом пикселе — func(точка поверхности, нормаль грани); поля за край островов."""
    img = np.zeros((res, res), np.float32)
    hit = np.zeros((res, res), bool)
    for ob in objects:
        me = ob.data
        me.calc_loop_triangles()
        uv = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[UV].data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2) * res
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        mw = np.array(ob.matrix_world, np.float32)
        co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
        nt = len(me.loop_triangles)
        tl = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("loops", tl)
        tv = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", tv)
        tn = np.empty(nt * 3, np.float32)
        me.loop_triangles.foreach_get("normal", tn)
        tl, tv, tn = tl.reshape(-1, 3), tv.reshape(-1, 3), tn.reshape(-1, 3) @ mw[:3, :3].T
        for t in range(nt):
            a, b, c = uv[tl[t]]
            x0, y0 = np.floor(np.minimum.reduce([a, b, c])).astype(int)
            x1, y1 = np.ceil(np.maximum.reduce([a, b, c])).astype(int)
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
            if x1 < x0 or y1 < y0:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            q = np.c_[gx.ravel(), gy.ravel()]
            m = np.array([[b[0] - a[0], c[0] - a[0]], [b[1] - a[1], c[1] - a[1]]])
            if abs(np.linalg.det(m)) < 1e-12:
                continue
            w = np.linalg.solve(m, (q - a).T).T
            inside = (w[:, 0] >= -1e-4) & (w[:, 1] >= -1e-4) & (w.sum(1) <= 1 + 1e-4)
            if not inside.any():
                continue
            w = w[inside]
            P = co[tv[t, 0]] + w[:, :1] * (co[tv[t, 1]] - co[tv[t, 0]]) + w[:, 1:] * (co[tv[t, 2]] - co[tv[t, 0]])
            vals = func(P, np.broadcast_to(tn[t], P.shape))
            px = (q[inside] - 0.5).astype(int)
            img[px[:, 1], px[:, 0]] = np.maximum(img[px[:, 1], px[:, 0]], vals)
            hit[px[:, 1], px[:, 0]] = True
    for _ in range(4):                                              # поля, чтобы не было шва по краю острова
        grow = img.copy()
        got = hit.copy()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(img, dy, 0), dx, 1)
            shh = np.roll(np.roll(hit, dy, 0), dx, 1)
            take = ~hit & shh
            grow[take] = np.maximum(grow[take], sh[take])
            got |= take
        img, hit = grow, got
    im = bpy.data.images.get(name) or bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    im.colorspace_settings.name = "Non-Color"
    rgba = np.ones((res, res, 4), np.float32)
    rgba[..., :3] = np.clip(img, 0, 1)[..., None]
    im.pixels.foreach_set(rgba.ravel())
    im.pack()
    print("RAD mask", name, "покрыто", round(float((img > 0.3).mean()) * 100, 2), "%", flush=True)
    return im


# ---------------------------------------------------------------- UCUPaint: стек, слой, маски

def make_stack(material_name: str, label: str):
    mat = bpy.data.materials[material_name]
    ob = next(o for o in bpy.data.objects if o.type == "MESH" and mat in list(o.data.materials))
    activate(ob, list(ob.data.materials).index(mat))
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=label, color=True, metallic=True, roughness=True, normal=True, ao=False,
                                         switch_to_material_view=False, target_bsdf_name=bsdf.name)
    group = next(n for n in nt.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None) and n.node_tree.yp.is_ypaint_node)
    tree = group.node_tree
    normal = next(c for c in tree.yp.channels if c.type == "NORMAL")
    normal.enable_smooth_bump = False
    normal.main_uv = UV
    group.label = label
    mat["authoring"] = "Нативный UCUPaint 2.4.9; Claude; состояние «рабочий»; маски — Маски_АЛЬФА владельца"
    return tree


def layer(tree, name: str, color=None, metal=None, rough=None, height=None, source: str = "COLOR", scale: float = 0.0,
          amount: float = 1.0, distance: float = 0.00003, detail: float = 2.0):
    """Слой наверх стека; color/metal/rough — значения каналов, height="source" — рельеф из шума."""
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


def ramp(mask, lo: float, hi: float, invert: bool = False) -> None:
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(mask, "RAMP")
    node = U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp]
    e0, e1 = node.color_ramp.elements
    e0.position, e1.position = lo, hi
    e0.color = (1, 1, 1, 1) if invert else (0, 0, 0, 1)
    e1.color = (0, 0, 0, 1) if invert else (1, 1, 1, 1)


def _scale(mask, s) -> None:
    s = (s, s, s) if isinstance(s, (int, float)) else s
    mask.enable_uniform_scale = False
    mask.scale = s
    U.common.set_entity_prop_value(mask, "scale", Vector(s))


def noise(target, name: str, scale: float, lo: float | None = None, hi: float | None = None,
          offset: tuple = (0.0, 0.0, 0.0), stretch=None):
    """Нерегулярность; порог — внутри самой маски шума. stretch — растяжка координат (потёки — вдоль Z)."""
    result = U.Mask.add_new_mask(target, name, "NOISE", "Object", UV)
    src = U.common.get_mask_tree(result).nodes[result.source]
    src.inputs["Scale"].default_value = scale
    src.inputs["Detail"].default_value = 2.4
    src.inputs["Roughness"].default_value = 0.66
    result.translation = offset
    if stretch is not None:
        _scale(result, stretch)
    if lo is not None:
        H.local_noise_ramp(U, result, lo, hi)
    return result


def vcol(target, name: str, label: str, lo: float | None = None, hi: float | None = None, invert: bool = False):
    result = U.Mask.add_new_mask(target, label, "VCOL", "Object", UV, vcol_name=name)
    if lo is not None:
        ramp(result, lo, hi, invert)
    return result


def ao(target, label: str, distance: float):
    result = U.Mask.add_new_mask(target, label, "AO", "Object", UV, ao_distance=distance, hemi_use_prev_normal=False)
    importlib.import_module(U.__name__ + ".MaskModifier").add_new_mask_modifier(result, "INVERT")
    return result


def uvmask(target, img, label: str, lo: float | None = None, hi: float | None = None):
    """Маска-картинка, посчитанная по развёртке этого материала."""
    result = U.Mask.add_new_mask(target, label, "IMAGE", "UV", UV, image=img)
    if lo is not None:
        ramp(result, lo, hi)
    return result


def edges(target, label: str, radius: float, lo: float, hi: float):
    result = U.Mask.add_new_mask(target, label, "EDGE_DETECT", "Object", UV, edge_detect_radius=radius,
                                 hemi_use_prev_normal=False)
    ramp(result, lo, hi)
    return result


def image(target, key: str, label: str, tile_m: float, lo: float | None = None, hi: float | None = None,
          offset: tuple = (0.0, 0.0, 0.0), coords: str = "Object", uv_unit_m: float = 1.0):
    """Маска-картинка владельца в настоящем масштабе: tile_m — сторона картинки на предмете.
    coords="Object" — объёмная проекция (BOX); "UV" — по развёртке (uv_unit_m — метров на единицу UV)."""
    img = bpy.data.images.load(str(MASKS / MASK_FILES[key]), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    result = U.Mask.add_new_mask(target, label, "IMAGE", coords, UV, image=img)
    src = U.common.get_mask_tree(result).nodes[result.source]
    if coords == "Object":
        src.projection = "BOX"
        src.projection_blend = 0.2
    s = (uv_unit_m if coords == "UV" else 1.0) / tile_m
    result.scale = (s, s, s)
    result.translation = offset
    if lo is not None:
        ramp(result, lo, hi)
    return result


# ---------------------------------------------------------------- материалы

CORE_UV_M = 2 * rad.CORE_X + 0.006          # сердцевина: метров на единицу UV (проекция спереди)


DEBUG_CORE = os.environ.get("RAD_DEBUG_CORE") == "1"


def core():
    road_c = (1.0, 0.0, 0.0) if DEBUG_CORE else ROAD
    bugs_c = (0.0, 1.0, 0.0) if DEBUG_CORE else BUGS
    tree = make_stack("rad_core", "Радиатор • сердцевина: трубки и ламели • рабочий")
    layer(tree, "00 • Алюминий сердцевины", ALU, 1.0, 0.42)
    layer(tree, "05 • Микрорельеф алюминия", height="source", source="NOISE", scale=4000.0, distance=0.00002)
    lay = layer(tree, "10 • Матовый налёт флюса пайки", FLUX, 0.0, 0.85, amount=0.55)
    noise(lay, "Налёт пятнами — 2–4 см", 45.0, 0.3, 0.72)
    noise(lay, "Налёт неровный", 700.0, 0.25, 0.75, (0.03, 0.01, 0.02))
    lay = layer(tree, "15 • Темнее в глубине ламелей", (0.22, 0.22, 0.22), 0.3, 0.7, amount=0.4)
    vcol(lay, "CoreDepth", "Глубина сердцевины", 0.15, 0.9)
    lay = layer(tree, "20 • Дорожная пыль на передней кромке", road_c, 0.0, 0.92, amount=0.55)
    vcol(lay, "CoreDepth", "Передние 3–10 мм", 0.12, 0.38, invert=True)
    image(lay, "dust", "Пыль пятнами — 35 см", 0.35, 0.12, 0.6, coords="UV", uv_unit_m=CORE_UV_M)
    lay = layer(tree, "25 • Грязь снизу — брызги с дороги", GRIME, 0.0, 0.9, amount=0.8)
    vcol(lay, "CoreDepth", "Передняя половина", 0.2, 0.55, invert=True)
    vcol(lay, "Low", "Нижние 10 см", 0.1, 0.9)
    noise(lay, "Брызги неровно", 90.0, 0.35, 0.65, (0.05, 0.02, 0.07))
    lay = layer(tree, "30 • Мошки и мелкие брызги", bugs_c, 0.0, 0.45, amount=0.95)
    vcol(lay, "CoreDepth", "Передние 3–7 мм", 0.12, 0.28, invert=True)
    image(lay, "splash", "Брызги — 12 см", 0.12, 0.3, 0.55, coords="UV", uv_unit_m=CORE_UV_M)
    noise(lay, "Где налипло больше", 6.0, 0.48, 0.72, (0.2, 0.0, 0.1))
    lay = layer(tree, "35 • Мошки — светлые крылья и пыльца", (0.30, 0.24, 0.10), 0.0, 0.7, amount=0.5)
    vcol(lay, "CoreDepth", "Передняя кромка", 0.12, 0.28, invert=True)
    image(lay, "drops", "Мелкие капли — 6 см", 0.06, 0.35, 0.6, offset=(0.21, 0.37, 0.0), coords="UV",
          uv_unit_m=CORE_UV_M)
    noise(lay, "Местами", 9.0, 0.52, 0.74, (0.1, 0.3, 0.2))
    lay = layer(tree, "40 • Пыль на верхних гранях — лежал в кладовой", DUST, 0.0, 0.95, amount=0.35)
    vcol(lay, "FaceUp", "Грани вверх", 0.3, 0.85)
    noise(lay, "Пыль неровно", 160.0, 0.35, 0.7)
    H.reconnect(U, tree)
    return tree


def alu_frame():
    tree = make_stack("rad_alu", "Радиатор • пластины и коллекторы • рабочий")
    layer(tree, "00 • Листовой алюминий", (0.47, 0.48, 0.49), 1.0, 0.38)
    layer(tree, "05 • Микрорельеф", height="source", source="NOISE", scale=3500.0, distance=0.00002)
    lay = layer(tree, "10 • Матовый налёт флюса", FLUX, 0.0, 0.85, amount=0.45)
    noise(lay, "Налёт пятнами", 60.0, 0.3, 0.72)
    noise(lay, "Налёт неровный", 600.0, 0.25, 0.75, (0.02, 0.05, 0.01))
    lay = layer(tree, "20 • Грязь в щелях и под лапками", GRIME, 0.0, 0.9, amount=0.75)
    ao(lay, "Защищённые углы", 0.004)
    noise(lay, "Отложения неровные", 500.0, 0.3, 0.6, (0.01, 0.03, 0.02))
    lay = layer(tree, "25 • Дорожная грязь спереди снизу", ROAD, 0.0, 0.92, amount=0.7)
    vcol(lay, "Front", "Грани вперёд", 0.3, 0.8)
    vcol(lay, "Low", "Низ", 0.0, 0.8)
    noise(lay, "Брызги", 120.0, 0.4, 0.65)
    lay = layer(tree, "40 • Пыль сверху", DUST, 0.0, 0.95, amount=0.4)
    vcol(lay, "FaceUp", "Грани вверх", 0.3, 0.85)
    image(lay, "dust", "Пыль пятнами — 30 см", 0.30, 0.1, 0.6)
    H.reconnect(U, tree)
    return tree


def plastic():
    obs = [o for o in bpy.data.objects if o.type == "MESH" and o.active_material.name == "rad_plastic"]
    cool = bake_uv_mask(obs, coolant_tank, 2048, "RAD_mask_coolant_tanks")
    grab = bake_uv_mask(obs, grab_tank, 1024, "RAD_mask_grab_tanks")
    tree = make_stack("rad_plastic", "Радиатор • бачки PA66-GF30, пробка • рабочий")
    layer(tree, "00 • Чёрный стеклонаполненный полиамид", PA_BLACK, 0.0, 0.55)
    layer(tree, "05 • Зерно стекловолокна", height="source", source="NOISE", scale=2600.0, distance=0.00003)
    lay = layer(tree, "06 • Неровный блеск литья", rough=0.45, amount=0.4)
    noise(lay, "Пятна блеска", 70.0)
    lay = layer(tree, "10 • Выцвело от жара сверху", (0.05, 0.05, 0.052), 0.0, 0.62, amount=0.55)
    vcol(lay, "FaceUp", "Грани вверх", 0.2, 0.9)
    noise(lay, "Неравномерно", 30.0, 0.3, 0.7)
    lay = layer(tree, "20 • Грязь в углах и у рёбер", GRIME, 0.0, 0.85, amount=0.7)
    ao(lay, "Защищённые углы", 0.006)
    noise(lay, "Отложения неровные", 350.0, 0.3, 0.6)
    lay = layer(tree, "30 • Дорожная грязь спереди снизу", ROAD, 0.0, 0.9, amount=0.5)
    vcol(lay, "Front", "Грани вперёд", 0.2, 0.8)
    vcol(lay, "Low", "Низ", 0.0, 0.7)
    image(lay, "grime", "Грязь пятнами — 15 см", 0.15, 0.25, 0.7)
    lay = layer(tree, "40 • Засохший антифриз — корка", COOL_CRUST, 0.0, 0.92, height=1.0, distance=0.00015, amount=0.8)
    uvmask(lay, cool, "Стык патрубка, основание горловины, потёки — по развёртке", 0.38, 0.52)
    noise(lay, "Корка неровно, рваный край", 420.0, 0.34, 0.5, (0.0, 0.0, 0.0), stretch=(2.0, 2.0, 0.6))
    lay = layer(tree, "41 • Антифриз гуще по краю корки", COOL_FILM, 0.0, 0.55, amount=0.45)
    uvmask(lay, cool, "Край потёков — по развёртке", 0.28, 0.4)
    noise(lay, "Плёнка неровно", 300.0, 0.4, 0.58, (0.01, 0.0, 0.03), stretch=(2.0, 2.0, 0.5))
    lay = layer(tree, "50 • Грязные отпечатки — снимали и несли", (0.05, 0.047, 0.042), 0.0, 0.42, amount=0.8)
    uvmask(lay, grab, "Где держали руками — по развёртке", 0.2, 0.8)
    image(lay, "print", "Отпечаток — 18 мм", 0.022, 0.2, 0.6)
    noise(lay, "Не везде", 25.0, 0.5, 0.62)
    lay = layer(tree, "60 • Пыль на горизонталях", DUST, 0.0, 0.95, amount=0.45)
    vcol(lay, "FaceUp", "Грани вверх", 0.35, 0.9)
    image(lay, "dust", "Пыль пятнами — 30 см", 0.30, 0.1, 0.6, offset=(0.13, 0.07, 0.0))
    H.reconnect(U, tree)
    return tree


def hose():
    tree = make_stack("rad_hose", "Патрубки EPDM • рабочие")
    layer(tree, "00 • Резина EPDM", EPDM, 0.0, 0.72)
    layer(tree, "05 • Фактура формованной резины", height="source", source="NOISE", scale=3000.0, distance=0.00002)
    lay = layer(tree, "06 • Сероватый налёт на резине", (0.055, 0.055, 0.056), 0.0, 0.85, amount=0.35)
    noise(lay, "Налёт пятнами", 40.0, 0.4, 0.7)
    lay = layer(tree, "10 • Внутри темнее", (0.015, 0.013, 0.012), 0.0, 0.6)
    vcol(lay, "HoseInner", "Внутренность", 0.3, 0.7)
    lay = layer(tree, "20 • Антифриз внутри у конца и у горловины", COOL_CRUST, 0.0, 0.9, amount=0.5)
    vcol(lay, "Coolant", "Концы", 0.1, 0.6)
    noise(lay, "Корка неровно", 120.0, 0.4, 0.65)
    lay = layer(tree, "30 • Масляные отпечатки у концов", (0.018, 0.018, 0.018), 0.0, 0.35, amount=0.85)
    vcol(lay, "Grab", "Где брали руками", 0.2, 0.8)
    image(lay, "print_smear", "Смазанный отпечаток — 20 мм", 0.024, 0.2, 0.6)
    noise(lay, "Не везде", 30.0, 0.48, 0.62, (0.02, 0.05, 0.0))
    lay = layer(tree, "40 • Пыль сверху", DUST, 0.0, 0.95, amount=0.4)
    vcol(lay, "FaceUp", "Грани вверх", 0.35, 0.9)
    image(lay, "dust_sparse", "Пыль редкая — 25 см", 0.25, 0.1, 0.6)
    H.reconnect(U, tree)
    return tree


def clamp():
    tree = make_stack("rad_clamp", "Хомуты, нержавеющая сталь • рабочие")
    layer(tree, "00 • Нержавеющая сталь", (0.55, 0.55, 0.56), 1.0, 0.3)
    lay = layer(tree, "05 • Неровная шероховатость", rough=0.45, amount=0.5)
    noise(lay, "Неровность", 900.0)
    lay = layer(tree, "10 • Налёт в щелях", GRIME, 0.0, 0.85, amount=0.7)
    ao(lay, "Защищённые углы", 0.003)
    noise(lay, "Налёт неровно", 600.0, 0.3, 0.6)
    lay = layer(tree, "20 • Свежие следы ключа на винте", (0.78, 0.78, 0.79), 1.0, 0.16, amount=0.8)
    edges(lay, "Кромки граней и ленты", 0.0004, 0.05, 0.15)
    noise(lay, "Следы местами", 1200.0, 0.45, 0.6)
    lay = layer(tree, "30 • Пыль сверху", DUST, 0.0, 0.95, amount=0.35)
    vcol(lay, "FaceUp", "Грани вверх", 0.4, 0.9)
    H.reconnect(U, tree)
    return tree


def wire():
    tree = make_stack("rad_wire", "Проволока вязальная • рабочая")
    layer(tree, "00 • Отожжённая сталь, тёмная", (0.05, 0.05, 0.052), 1.0, 0.55)
    lay = layer(tree, "10 • Точки ржавчины", (0.12, 0.05, 0.02), 0.0, 0.9, amount=0.6)
    noise(lay, "Редкие точки", 300.0, 0.55, 0.7)
    H.reconnect(U, tree)
    return tree


def tag():
    tree = make_stack("rad_tag", "Бирка • крафт-картон")
    layer(tree, "00 • Крафт-картон", KRAFT, 0.0, 0.9)
    layer(tree, "05 • Волокно картона", height="source", source="NOISE", scale=3500.0, distance=0.00004)
    layer(tree, "06 • Замятости", height="source", source="NOISE", scale=45.0, distance=0.0004, amount=0.5, detail=1.0)
    lay = layer(tree, "10 • Неровный тон", (0.33, 0.19, 0.09), amount=0.5)
    noise(lay, "Пятна тона", 90.0, 0.3, 0.7)
    lay = layer(tree, "20 • Потемневшие истрёпанные края", (0.22, 0.13, 0.06), 0.0, 0.92, amount=0.7)
    edges(lay, "Края бирки", 0.0012, 0.04, 0.2)
    noise(lay, "Края неровно", 400.0, 0.3, 0.65)
    lay = layer(tree, "30 • Грязные отпечатки", (0.12, 0.08, 0.05), 0.0, 0.8, amount=0.75)
    image(lay, "print", "Отпечаток — 18 мм", 0.02, 0.2, 0.6, offset=(0.3, 0.1, 0.0))
    noise(lay, "Два-три следа", 22.0, 0.55, 0.64, (0.4, 0.2, 0.1))
    lay = layer(tree, "40 • Пыль", (0.45, 0.40, 0.33), 0.0, 0.95, amount=0.3)
    image(lay, "dust_sparse", "Пыль редкая — 12 см", 0.12, 0.1, 0.6)
    H.reconnect(U, tree)
    ring = make_stack("rad_tag_ring", "Бирка • бумажные кольца")
    layer(ring, "00 • Белая бумага", (0.62, 0.60, 0.55), 0.0, 0.9)
    lay = layer(ring, "10 • Захватано", (0.30, 0.27, 0.22), 0.0, 0.9, amount=0.5)
    noise(lay, "Пятна", 300.0, 0.4, 0.7)
    H.reconnect(U, ring)
    ink = make_stack("rad_ink", "Бирка • маркер")
    layer(ink, "00 • Чёрный маркер", (0.010, 0.010, 0.012), 0.0, 0.42)
    lay = layer(ink, "10 • Неровно впиталось", (0.035, 0.032, 0.03), 0.0, 0.75, amount=0.6)
    noise(lay, "Полосы штриха", 600.0, 0.4, 0.7)
    H.reconnect(U, ink)
    return [tree, ring, ink]


VIEWPORT = {  # цвет и шероховатость в окне Blender (Solid) — близко к итоговому
    "rad_core": (ALU, 0.5), "rad_alu": ((0.47, 0.48, 0.49), 0.4), "rad_plastic": (PA_BLACK, 0.55),
    "rad_hose": (EPDM, 0.72), "rad_clamp": ((0.55, 0.55, 0.56), 0.3), "rad_wire": ((0.05, 0.05, 0.052), 0.55),
    "rad_tag": (KRAFT, 0.9), "rad_tag_ring": ((0.62, 0.60, 0.55), 0.9), "rad_ink": ((0.01, 0.01, 0.012), 0.42),
}


def apply() -> list:
    native()
    bpy.ops.wm.open_mainfile(filepath=str(UVSRC))
    paint_attrs()
    trees = [core(), alu_frame(), plastic(), hose(), clamp(), wire()] + tag()
    for name, (rgb, r) in VIEWPORT.items():
        m = bpy.data.materials[name]
        m.diffuse_color = (*rgb, 1.0)
        m.roughness = r
    # краска надписи — в одной плоскости внахлёст (штрихи и кружки на концах): тени от неё дают тёмные точки
    bpy.data.objects["Tag_Text"].visible_shadow = False
    root = bpy.data.objects["Radiator"]
    root["texture_version"] = "pbr_v01; форма v01 принята владельцем 2026-10-18; состояние «рабочий»"
    return trees


def build() -> None:
    trees = apply()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    for tree in trees:
        print("RAD stack", tree.name, "layers", len(tree.yp.layers), flush=True)
    print("RAD build done", flush=True)


# ---------------------------------------------------------------- проверка сохранённого файла

def inspect() -> None:
    native()
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    report: dict = {"file": MASTER.name, "ucupaint": U.common.get_current_version_str(), "stacks": {}}
    for mat in bpy.data.materials:
        if not mat.use_nodes:
            continue
        group = next((n for n in mat.node_tree.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
                      and n.node_tree.yp.is_ypaint_node), None)
        if group is None:
            continue
        tree = group.node_tree
        bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        wired = {k: bool(bsdf.inputs[k].links) and bsdf.inputs[k].links[0].from_node == group
                 for k in ("Base Color", "Metallic", "Roughness", "Normal")}
        layers = []
        for lay in tree.yp.layers:
            actual = U.common.get_entity_prop_value(lay, "intensity_value")
            assert abs(actual - lay.intensity_value) < 1e-6, (lay.name, actual, lay.intensity_value)
            layers.append({"name": lay.name, "type": lay.type, "enabled": lay.enable, "intensity": round(lay.intensity_value, 3),
                           "channels": [root.name for root, ch in zip(tree.yp.channels, lay.channels) if ch.enable],
                           "masks": [{"name": m.name, "type": m.type, "modifiers": [mod.type for mod in m.modifiers]}
                                     for m in lay.masks]})
        assert all(wired.values()), (mat.name, wired)
        report["stacks"][mat.name] = {"tree": tree.name, "wired_to_bsdf": wired, "layers": layers}
    images = [{"name": im.name, "packed": im.packed_file is not None, "size": list(im.size),
               "colorspace": im.colorspace_settings.name}
              for im in bpy.data.images if im.type == "IMAGE" and im.size[0] > 0]
    assert all(i["packed"] for i in images), images
    assert all(i["colorspace"] == "Non-Color" for i in images), images
    report["images"] = images
    VIEW.mkdir(parents=True, exist_ok=True)
    (VIEW / "stack.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("RAD inspect ok: стеков", len(report["stacks"]), "слоёв",
          sum(len(s["layers"]) for s in report["stacks"].values()), "картинок", len(images), flush=True)


# ---------------------------------------------------------------- снимки

def render_shots() -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = int(os.environ.get("RAD_SAMPLES", "64"))
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
        print("RAD gpu off:", exc, flush=True)
    k = float(os.environ.get("RAD_RES", "1.0"))
    scene.render.resolution_x, scene.render.resolution_y = int(1400 * k), int(900 * k)
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = float(os.environ.get("RAD_EXPOSURE", "0.0"))
    world = bpy.data.worlds.new("Студия")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.205, 0.21, 1.0)
    world.node_tree.nodes["Background"].inputs[1].default_value = 0.6
    scene.world = world
    centre = Vector((0.0, 0.04, 0.2))

    def area(name: str, loc: tuple, size: float, energy: float) -> None:
        light = bpy.data.objects.new(name, bpy.data.lights.new(name, "AREA"))
        light.data.size = size
        light.data.energy = energy
        zz = (Vector(loc) - centre).normalized()
        xx = Vector((0, 0, 1)).cross(zz).normalized()
        m = Matrix((xx, zz.cross(xx), zz)).transposed().to_4x4()
        m.translation = Vector(loc)
        light.matrix_world = m
        scene.collection.objects.link(light)

    area("Ключ", (-0.9, -1.0, 1.6), 1.6, 55.0)
    area("Заполнение", (1.6, 0.4, 0.6), 1.6, 22.0)
    area("Контур", (0.6, 1.6, 1.2), 1.2, 38.0)
    area("Снизу", (0.0, -0.6, -1.0), 2.0, 6.0)
    cam = bpy.data.objects.new("Камера", bpy.data.cameras.new("Камера"))
    cam.data.clip_start = 0.01
    scene.collection.objects.link(cam)
    scene.camera = cam
    VIEW.mkdir(parents=True, exist_ok=True)
    only = [s for s in os.environ.get("RAD_SHOTS", "").split(",") if s]
    f = rad.tag_frame()
    tag_c = Vector((f["center"] - rad.CAR_POS).tolist())
    tag_n = Vector(f["n"].tolist())

    def shot(name: str, loc, target, lens: float) -> None:
        if only and not any(name.startswith(s) for s in only):
            return
        loc, target = Vector(loc), Vector(target)
        cam.data.lens = lens
        cam.location = loc
        cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(VIEW / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        print("RAD shot", name, flush=True)

    shot("01_szadi", (1.0, 1.25, 0.62), (-0.02, 0.04, 0.19), 45)
    shot("02_speredi", (-0.95, -1.35, 0.62), (0.02, 0.0, 0.19), 45)
    shot("03_serdcevina_krupno", (0.10, -0.32, 0.30), (0.12, 0.0, 0.22), 85)
    shot("04_gorlovina_antifriz", (0.66, 0.30, 0.32), (0.43, 0.04, 0.19), 60)
    shot("05_birka", tag_c + tag_n * 0.24, tag_c, 60)
    shot("06_konec_patrubka", (0.14, 0.28, 0.24), (0.36, 0.155, 0.21), 70)
    shot("07_nizhniy_bachok_speredi", (-0.70, -0.50, 0.16), (-0.44, -0.02, 0.07), 60)


def preview() -> None:
    apply()
    render_shots()
    print("RAD preview done", flush=True)


def render() -> None:
    native()
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    render_shots()
    print("RAD render done", flush=True)


if __name__ == "__main__":
    {"build": build, "preview": preview, "render": render, "inspect": inspect}[MODE]()
