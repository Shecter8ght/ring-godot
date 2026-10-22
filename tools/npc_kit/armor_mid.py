"""NPC: плитоносец «средний» (уровень брони 2 из 3) по фото владельца — на мародёре поверх куртки.

Состав (_asset_src/npc_kit/armor/asset-state.md): передний пакет с вырезом «под приклад» и вогнутым
верхом — карман под плиту: полость, открытая сверху, клапан через верх на велкро (сменить плиту —
открыть клапан, вынуть плиту вверх; плита и клапан — отдельные объекты с опорными точками под
анимацию; на краю клапана — язычок, за который его открывают); задний пакет; спереди велкро-панель
с решёткой прорезей и резинками-держателями по краям, два ряда MOLLE; плечевые лямки с мягкими накладками,
кольцами и петлями под провод гарнитуры / трубку питья; камербанд с тремя рядами MOLLE заходит спереди
под откидной клапан «кенгуру» (четыре ряда MOLLE, над ним — язычки резинок вставки под магазины); на левом
боку два фастекса сброса; по нижним углам клапана — язычки с пряжками; сзади — ручка эвакуации и люверсы
стока воды внизу. Мелочи сверены с фото серийных плитоносцев (2026-10-22).
Сборка — build_carrier(CarrierSpec): та же основа у «крутой» (armor_top.py) с другими размерами.
Форма — нейтральным материалом (на согласование), текстуры — после принятия.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_mid.py [-- render] [deliver=<папка>]
→ _asset_src/npc_kit/armor/armor_mid.blend (читает npc_scav_<версия>.blend)
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "armor"
PRESS = 0.012            # пакет поджимает куртку не больше чем на столько
MOLLE_PITCH = 0.042      # ряды MOLLE: лента 25 мм через 17 мм


@dataclass
class CarrierSpec:
    prefix: str = "Mid"
    front_bot: float = 1.105
    front_h: float = 0.370
    front_w: float = 0.285
    back_bot: float = 1.100
    back_h: float = 0.390
    back_w: float = 0.290
    cav: float = 0.024                   # полость под плиту (керамика / композит до 21 мм)
    wall: float = 0.007                  # стенка пакета (ткань с подкладкой)
    bag_t: float = 0.038                 # толщина пакета: полость + две стенки
    pocket: bool = True                  # передний пакет — карман со сменой плиты сверху
    lid_over: float = 0.022              # клапан кармана заходит на лицевую сторону
    flap_h: float = 0.178                # клапан «кенгуру»
    flap_w: float = 0.330
    flap_t: float = 0.022
    flap_rows: int = 4
    cummer_h: float = 0.165
    cummer_t: float = 0.007              # у «крутой» толще: в камербанде боковые плиты
    cummer_rows: int = 3
    front_rows: list[float] = field(default_factory=lambda: [0.184, 0.212])
    admin: tuple = (-0.075, 0.075, 0.243, 0.309, 4, 3)       # велкро-панель: u0, u1, v0, v1, столбцов, рядов
    top_strip: bool = True               # полоса велкро по верху переднего пакета
    back_velcro: tuple = (-0.112, 0.112, 0.205, 0.352)
    back_rows: int = 4
    back_molle_u: float = 0.115          # ряды MOLLE сзади — от −u до u
    side_buckles: bool = True
    bottom_tabs: bool = True
    drag_handle: bool = True
    pad: tuple = (0.074, 0.016)           # плечевая накладка: ширина, толщина
    keepers: bool = True                 # резинки-держатели по краям велкро-панели (жгут, фонарь)
    cable_loops: bool = True             # петли на плечевых накладках под провод рации и трубку питья
    kangaroo_tabs: bool = True           # язычки резинок вставки под магазины над клапаном «кенгуру»
    grommets: bool = True                # люверсы для стока воды внизу заднего пакета


@dataclass
class Fit:
    jacket: bpy.types.Object
    jacket_bvh: BVHTree
    hull: ak.Hull


def fit() -> Fit:
    """Мародёр: торс куртки сечениями (без рукавов) и плечо куртки для лямок (без воротника и рукавов —
    воротник у шеи стоит выше плеча, и лямка по нему висела бы аркой)."""
    jacket = bpy.data.objects["Jacket"]
    jm = jacket.data
    groups = {g.index for g in jacket.vertex_groups if g.name.startswith(("piece_collar", "piece_sleeve"))}
    skip = {v.index for v in jm.vertices if any(g.group in groups and g.weight > 0.5 for g in v.groups)}
    jco = [jacket.matrix_world @ v.co for v in jm.vertices]
    bvh = BVHTree.FromPolygons(jco, [list(p.vertices) for p in jm.polygons if not any(i in skip for i in p.vertices)])
    return Fit(jacket, bvh, ak.Hull([jacket], 1.04, 1.56))


def materials() -> dict[str, bpy.types.Material]:
    return {
        "cordura": kc.clay("Armor_Cordura", (0.20, 0.19, 0.15), 0.85),
        "webbing": kc.clay("Armor_Webbing", (0.16, 0.15, 0.12), 0.8),
        "velcro": kc.clay("Armor_Velcro", (0.12, 0.115, 0.095), 0.95),
        "plastic": kc.clay("Armor_Plastic", (0.05, 0.05, 0.045), 0.45),
        "metal": kc.clay("Armor_Metal", (0.35, 0.34, 0.32), 0.35),
        "plate": kc.clay("Armor_Plate", (0.06, 0.06, 0.058), 0.6),
    }


def front_outline(w: float, h: float) -> list[tuple[float, float]]:
    """Перед: низ прямой, бока до 58 % высоты, косой вырез к плечам, вогнутый верх у шеи."""
    hw = w / 2
    pts = [(-hw, 0.0), (hw, 0.0), (hw, 0.58 * h), (0.106, 0.952 * h), (0.096, h),
           (0.05, h - 0.010), (0.0, h - 0.014), (-0.05, h - 0.010), (-0.096, h), (-0.106, 0.952 * h), (-hw, 0.58 * h)]
    radii = [0.022, 0.022, 0.035, 0.010, 0.005, 0.0, 0.0, 0.0, 0.005, 0.010, 0.035]
    return ak.rounded_poly(pts, radii)


def front_top_v(u: float, h: float) -> float:
    """Верх переднего пакета по лекалу: вогнутый вырез у шеи (0 — середина, ±0,096 — углы под лямки)."""
    t = min(1.0, abs(u) / 0.096)
    return h - 0.014 + 0.014 * t * t


def plate_outline(v0: float) -> list[tuple[float, float]]:
    """Плита 24 × 31 см с вырезом «под приклад» по верхним углам (низ — на v0)."""
    pts = [(-0.120, v0), (0.120, v0), (0.120, v0 + 0.220), (0.075, v0 + 0.310), (-0.075, v0 + 0.310), (-0.120, v0 + 0.220)]
    return ak.rounded_poly(pts, [0.015, 0.015, 0.020, 0.020, 0.020, 0.020])


def back_outline(w: float, h: float) -> list[tuple[float, float]]:
    hw = w / 2
    pts = [(-hw, 0.0), (hw, 0.0), (hw, 0.66 * h), (0.118, 0.96 * h), (0.105, h), (-0.105, h), (-0.118, 0.96 * h), (-hw, 0.66 * h)]
    radii = [0.022, 0.022, 0.035, 0.010, 0.006, 0.006, 0.010, 0.035]
    return ak.rounded_poly(pts, radii)


def rect(u0: float, u1: float, v0: float, v1: float, r: float) -> list[tuple[float, float]]:
    return ak.rounded_poly([(u0, v0), (u1, v0), (u1, v1), (u0, v1)], [r] * 4)


def grid_relief(u0: float, u1: float, v0: float, v1: float, cols: int, rows: int, depth: float = 0.0012):
    """Прорези велкро-панели: решётка канавок (лазерная резка поверх MOLLE)."""
    def f(u: float, v: float) -> float:
        d = 1.0
        for i in range(1, cols):
            d = min(d, abs(u - (u0 + (u1 - u0) * i / cols)))
        for j in range(1, rows):
            d = min(d, abs(v - (v0 + (v1 - v0) * j / rows)))
        return -depth * gm.smoothstep((0.0016 - d) / 0.0008)
    return f


def shoulder_path(jacket_bvh: BVHTree, front: ak.PlateFrame, back: ak.PlateFrame, sgn: float,
                  bag_face: float, spec: CarrierSpec) -> ak.RibbonFrame:
    """Лямка: от верхнего угла переднего пакета по плечу (над курткой) к верхнему углу заднего."""
    c = Vector((sgn * 0.122, -0.01, 1.40))
    arc = []
    for k in range(41):
        th = math.radians(15 + 150 * k / 40)
        d = Vector((0.0, -math.cos(th), math.sin(th)))
        hit = jacket_bvh.ray_cast(c + d * 0.4, -d, 0.5)
        if hit[0] is not None:
            arc.append(hit[0] + (hit[0] - c).normalized() * 0.006)
    p_f = front.point(sgn * 0.097, spec.front_h - 0.006, bag_face)
    p_b = back.point(sgn * 0.102, spec.back_h - 0.006, bag_face)
    arc = [p for p in arc if p.z > p_f.z + 0.012 and (p.y < 0 or p.z > p_b.z + 0.012)]
    pts = [p_f] + arc + [p_b]
    for _ in range(3):                      # сгладить (Чайкин)
        sm = [pts[0]]
        for i in range(len(pts) - 1):
            sm.append(pts[i].lerp(pts[i + 1], 0.25))
            sm.append(pts[i].lerp(pts[i + 1], 0.75))
        sm.append(pts[-1])
        pts = sm
    return ak.RibbonFrame(pts, [(p - c).normalized() for p in pts])


def build_carrier(f: Fit, spec: CarrierSpec, col: bpy.types.Collection, mats: dict) -> dict:
    """Плитоносец по размерам spec. Возвращает рамки для надстроек: front, back, flap (лицевая сторона
    клапана), bands (камербанд), straps (оси лямок), face (лицевая сторона пакета от его середины)."""
    P = spec.prefix
    hull = f.hull
    front = ak.PlateFrame(hull, True, spec.front_bot, spec.front_h, spec.front_w, 0.32, spec.bag_t / 2, PRESS)
    back = ak.PlateFrame(hull, False, spec.back_bot, spec.back_h, spec.back_w, 0.40, spec.bag_t / 2, PRESS)
    kc.log(f"  перёд: наклон {front.k:.3f}, верх y {front.a:.3f}; зад: наклон {back.k:.3f}, верх y {back.a:.3f}")
    face = spec.bag_t / 2 + 0.0025               # лицевая сторона пакета (с набивкой)
    velcro = spec.bag_t / 2 + 0.003 + 0.0012     # велкро поверх ткани на 1,2 мм (вровень — поверхности мерцают)

    m = ak.Mesh()
    if spec.pocket:
        # Карман: горловина сверху между лямками; плита — отдельный объект, клапан — отдельный, на шарнире.
        ak.pocket_bag(m, front, front_outline(spec.front_w, spec.front_h), spec.cav, spec.wall,
                      lambda u, v: v > spec.front_h - 0.05 and abs(u) < 0.092, bulge=0.003)
        m.build(f"{P}_Front_Bag", col, [mats["cordura"]])
        pm = ak.Mesh()
        ak.padded_panel(pm, front, plate_outline(0.020), spec.cav - 0.003, bulge=0.0, binding=0.0, step=0.008)
        pm.build(f"{P}_Plate_Front", col, [mats["plate"]], origin=front.point(0.0, 0.175, 0.0))
        r_bag = spec.bag_t / 2
        lid = ak.LidFrame(front, lambda u: front_top_v(u, spec.front_h) - r_bag + 0.002, r_bag + 0.004, spec.lid_over)
        lm = ak.Mesh()
        ak.padded_panel(lm, ak.OffsetFrame(lid, 0.0025), rect(-0.088, 0.088, 0.0, lid.length, 0.008), 0.004,
                        bulge=0.0005, binding=0.006, step=0.004)
        # Язычок посередине края клапана — за него берутся рукой, открывая карман (часть клапана).
        ss = [lid.length - 0.012 + 0.040 * k / 16 for k in range(17)]
        tab_off = [0.0058 if s <= lid.length else 0.0058 - 0.0022 * gm.smoothstep((s - lid.length) / 0.008) for s in ss]
        ak.strap(lm, ak.RibbonFrame([lid.point(0.0, s, o) for s, o in zip(ss, tab_off)], [lid.normal(0.0, s) for s in ss]),
                 0.025, 0.003, mat=1)
        lm.build(f"{P}_Pocket_Lid", col, [mats["cordura"], mats["webbing"]], origin=lid.hinge())
    else:
        ak.padded_panel(m, front, front_outline(spec.front_w, spec.front_h), spec.bag_t, bulge=0.003)
        m.build(f"{P}_Front_Bag", col, [mats["cordura"]])
    m = ak.Mesh()
    ak.padded_panel(m, back, back_outline(spec.back_w, spec.back_h), spec.bag_t, bulge=0.003)
    m.build(f"{P}_Back_Bag", col, [mats["cordura"]])

    # Велкро: панель с решёткой спереди, полоса по верху, большое поле сзади.
    m = ak.Mesh()
    u0, u1, v0, v1, cols, rows = spec.admin
    ak.padded_panel(m, ak.OffsetFrame(front, velcro), rect(u0, u1, v0, v1, 0.006), 0.003, bulge=0.0,
                    binding=0.0, relief=grid_relief(u0, u1, v0, v1, cols, rows), step=0.002)
    if spec.top_strip:
        # Полоса велкро по верху лицевой стороны — на неё застёгивается клапан кармана.
        ak.padded_panel(m, ak.OffsetFrame(front, velcro - 0.0005), rect(-0.085, 0.085, spec.front_h - 0.055,
                        spec.front_h - 0.035, 0.003), 0.0025, bulge=0.0, binding=0.0, step=0.003)
    bu0, bu1, bv0, bv1 = spec.back_velcro
    ak.padded_panel(m, ak.OffsetFrame(back, velcro), rect(bu0, bu1, bv0, bv1, 0.008), 0.003,
                    bulge=0.0, binding=0.0, step=0.004)
    m.build(f"{P}_Velcro", col, [mats["velcro"]])

    # Клапан «кенгуру» поверх камербанда.
    flap_base = ak.OffsetFrame(front, spec.bag_t / 2 + spec.cummer_t + 0.003)
    m = ak.Mesh()
    ak.padded_panel(m, ak.OffsetFrame(flap_base, spec.flap_t / 2),
                    rect(-spec.flap_w / 2, spec.flap_w / 2, -0.006, spec.flap_h, 0.02), spec.flap_t, bulge=0.004)
    m.build(f"{P}_Flap", col, [mats["cordura"]])
    flap = ak.OffsetFrame(flap_base, spec.flap_t)

    # Камербанд: с боков по куртке, спереди — поверх переднего пакета, под клапан.
    def push(p: Vector, n: Vector) -> Vector:
        if p.y > -0.05:
            return p
        u = max(-spec.front_w / 2, min(spec.front_w / 2, p.x))
        y_out = front.point(u, p.z - spec.front_bot, spec.bag_t / 2 + 0.001).y
        t = gm.smoothstep((spec.front_w / 2 + 0.025 - abs(p.x)) / 0.035)
        q = p.copy()
        q.y = p.y + (min(p.y, y_out) - p.y) * t
        return q
    m = ak.Mesh()
    bands = []
    for a0, a1 in ((52.0, -60.0), (128.0, 240.0)):
        band = ak.BandFrame(hull, spec.front_bot + 0.008, spec.cummer_h, a0, a1, 0.003, push, vsmooth=12, press=0.010)
        bands.append(band)
        ak.padded_panel(m, ak.OffsetFrame(band, spec.cummer_t / 2), rect(0.0, band.length, 0.0, spec.cummer_h, 0.012),
                        spec.cummer_t, bulge=0.0006 + 0.1 * max(0.0, spec.cummer_t - 0.01), binding=0.009)
    m.build(f"{P}_Cummerbund", col, [mats["cordura"]])

    # Стропа MOLLE.
    m = ak.Mesh()
    if spec.front_rows:
        ak.webbing_rows(m, front, -0.112, 0.112, spec.front_rows, face)
    ak.webbing_rows(m, flap, -spec.flap_w / 2 + 0.015, spec.flap_w / 2 - 0.015,
                    [0.010 + MOLLE_PITCH * i for i in range(spec.flap_rows)], 0.003)
    ak.webbing_rows(m, back, -spec.back_molle_u, spec.back_molle_u,
                    [0.035 + MOLLE_PITCH * i for i in range(spec.back_rows)], face)
    for band in bands:
        ak.webbing_rows(m, ak.OffsetFrame(band, spec.cummer_t), 0.025, band.length - 0.06,
                        [0.018 + 0.05 * i for i in range(spec.cummer_rows)], 0.0)
    m.build(f"{P}_MOLLE", col, [mats["webbing"]])

    # Лямки и плечевые накладки, кольца на передних концах накладок.
    straps, pads, metal = ak.Mesh(), ak.Mesh(), ak.Mesh()
    paths = []
    for sgn in (1.0, -1.0):
        sp = shoulder_path(f.jacket_bvh, front, back, sgn, face, spec)
        paths.append(sp)
        ak.strap(straps, sp, 0.045, 0.004, 0.0)
        mid = sp.length * 0.48
        ak.strap(pads, sp, spec.pad[0], spec.pad[1], 0.003, u0=mid - 0.115, u1=mid + 0.105, taper=0.04)
        u_ring = mid - 0.105
        p = sp.point(u_ring, sgn * 0.030, spec.pad[1] + 0.005)
        tan = (sp.point(u_ring + 0.01, 0, 0) - sp.point(u_ring, 0, 0)).normalized()
        ak.torus(metal, p, sp.normal(u_ring, 0).cross(tan).normalized(), 0.011, 0.0025)
        if spec.cable_loops:
            # Петли поперёк накладки (провод гарнитуры, трубка питьевой системы) — спереди и сзади плеча.
            hw = spec.pad[0] / 2
            top = 0.003 + spec.pad[1]
            for uc in (mid - 0.065, mid + 0.055):
                ws = [-hw - 0.001] + [-hw + 0.004 + (2 * hw - 0.008) * k / 12 for k in range(13)] + [hw + 0.001]
                offs = [top * 0.55] + [top + 0.0004 + 0.0045 * math.sin(math.pi * k / 12) for k in range(13)] + [top * 0.55]
                ak.strap(straps, ak.RibbonFrame([sp.point(uc, w, o) for w, o in zip(ws, offs)], [sp.normal(uc, 0)] * len(ws)),
                         0.020, 0.0022)
    straps.build(f"{P}_Straps", col, [mats["webbing"]])
    pads.build(f"{P}_Shoulder_Pads", col, [mats["cordura"]])

    # Фурнитура: фастексы на левом боку, язычки с пряжками внизу клапана, ручка сзади.
    plastic, web = ak.Mesh(), ak.Mesh()
    if spec.side_buckles:
        band = bands[0]
        u_b = band.length - 0.085
        for v in (0.045, 0.118):
            c = band.point(u_b, v, spec.cummer_t + 0.005)
            tan = (band.point(u_b + 0.01, v, 0) - band.point(u_b, v, 0)).normalized()
            nrm = band.normal(u_b, v)
            ak.side_release(plastic, c, nrm.cross(tan).normalized(), tan, nrm, 0.025)
    if spec.bottom_tabs:
        ff = ak.OffsetFrame(flap_base, 0.004)
        for sgn in (1.0, -1.0):
            u = sgn * (spec.flap_w / 2 - 0.02)
            vs = (0.03, 0.0, -0.025, -0.045)
            ak.strap(web, ak.RibbonFrame([ff.point(u, v, 0.0) for v in vs], [ff.normal(u, v) for v in vs]), 0.025, 0.003)
            ak.ladder_lock(plastic, ff.point(u, -0.042, 0.004), Vector((1, 0, 0)), Vector((0, 0, 1)), ff.normal(u, -0.042), 0.025)
    if spec.drag_handle:
        hp = [back.point(0.04 * math.cos(math.pi * k / 12), spec.back_h - 0.02 + 0.038 * math.sin(math.pi * k / 12),
                         face + 0.004) for k in range(13)]
        ak.strap(web, ak.RibbonFrame(hp, [back.normal(0, spec.back_h)] * len(hp)), 0.025, 0.003)
    if spec.keepers:
        # Резинки-держатели по краям велкро-панели: пришиты концами, посередине чуть приподняты.
        u0, u1, v0, v1, _, _ = spec.admin
        for uc in (u0 - 0.024, u1 + 0.024):
            vs = [v0 + 0.004 + (v1 - v0 - 0.008) * k / 16 for k in range(17)]
            offs = [face + 0.0008 + 0.0035 * math.sin(math.pi * k / 16) ** 0.6 for k in range(17)]
            ak.strap(web, ak.RibbonFrame([front.point(uc, v, o) for v, o in zip(vs, offs)],
                                         [front.normal(uc, v) for v in vs]), 0.018, 0.0025)
    if spec.kangaroo_tabs:
        # Над клапаном «кенгуру» — язычки резинок вставки под магазины (магазины вынимаются вверх).
        for uc in (-0.075, 0.0, 0.075):
            vs = [spec.flap_h - 0.030 + 0.050 * k / 10 for k in range(11)]
            ak.strap(web, ak.RibbonFrame([flap_base.point(uc, v, -0.0012) for v in vs],
                                         [flap_base.normal(uc, v) for v in vs]), 0.020, 0.0025)
    if spec.grommets:
        for uc in (-(spec.back_w / 2 - 0.038), spec.back_w / 2 - 0.038):
            ak.torus(metal, back.point(uc, 0.020, face + 0.0012), back.normal(uc, 0.020), 0.0048, 0.0014, seg=14, sides=6)
    if plastic.faces:
        plastic.build(f"{P}_Buckles", col, [mats["plastic"]])
    if web.faces:
        web.build(f"{P}_Tabs", col, [mats["webbing"]])
    metal.build(f"{P}_Rings", col, [mats["metal"]])
    return {"front": front, "back": back, "flap": flap, "bands": bands, "straps": paths, "face": face,
            "velcro": velcro, "metal": metal}


def triangles(col: bpy.types.Collection) -> int:
    n = 0
    for o in col.objects:
        o.data.calc_loop_triangles()
        n += len(o.data.loop_triangles)
    return n


def deliver(folder: Path, filename: str, readme: str, focus_z: float = 1.28) -> None:
    """Файл на просмотр формы владельцу: студия, камеры, вьюпорт в Rendered, всё упаковано."""
    from mathutils import Quaternion
    scene = bpy.context.scene
    kc.studio()
    kc.gpu_cycles(64)
    scene.cycles.preview_samples = 24
    scene.cycles.use_preview_denoising = True
    for cam in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(cam)
    scene.camera = kc.camera("Camera_3-4", (1.5, -1.9, focus_z + 0.17), (0.0, 0.0, focus_z), 60)
    kc.camera("Camera_Front", (0.0, -2.3, focus_z + 0.04), (0.0, 0.0, focus_z + 0.02), 60)
    kc.camera("Camera_Back", (0.0, 2.3, focus_z + 0.06), (0.0, 0.0, focus_z + 0.02), 60)
    for o in bpy.data.objects:
        if o.type == "ARMATURE":
            o.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type == "VIEW_3D":
                sp = area.spaces.active
                sp.shading.type = "RENDERED"
                sp.overlay.show_floor = False
                r3 = sp.region_3d
                r3.view_location = (0.0, 0.0, focus_z)
                r3.view_distance = 1.6
                r3.view_rotation = Quaternion((0.78, 0.47, 0.20, 0.36))
    text = bpy.data.texts.new("00_ПРОЧТИ")
    text.use_fake_user = True
    text.write(readme)
    bpy.ops.file.pack_all()
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    kc.save(path)
    kc.log("DELIVERED", str(path))


def render_previews(col: bpy.types.Collection, tag: str, focus_z: float = 1.28, extra: dict | None = None) -> None:
    kc.studio()
    cams = {
        "on_34": kc.camera("Cam_A34", (1.5, -1.9, focus_z + 0.17), (0.0, 0.0, focus_z), 60),
        "on_front": kc.camera("Cam_AF", (0.0, -2.3, focus_z + 0.04), (0.0, 0.0, focus_z + 0.02), 60),
        "on_side": kc.camera("Cam_AS", (2.3, -0.1, focus_z + 0.04), (0.0, -0.02, focus_z + 0.02), 60),
        "on_back": kc.camera("Cam_AB", (0.0, 2.3, focus_z + 0.06), (0.0, 0.0, focus_z + 0.02), 60),
    }
    for name, cam in cams.items():
        kc.render(cam, OUT / "previews" / f"{tag}_{name}.png", (900, 1000), 48)
    hidden = []
    for o in bpy.data.objects:
        if o.type == "MESH" and o.users_collection and o.users_collection[0] != col and o.name != "Studio_Floor":
            hidden.append((o, o.hide_render))
            o.hide_render = True
    for name in ("on_34", "on_front", "on_back"):
        kc.render(cams[name], OUT / "previews" / f"{tag}_alone_{name[3:]}.png", (900, 1000), 48)
    for name, (pos, tgt) in (extra or {}).items():
        kc.render(kc.camera("Cam_" + name, pos, tgt, 60), OUT / "previews" / f"{tag}_{name}.png", (1000, 800), 64)
    for o, h in hidden:
        o.hide_render = h


README = (
    "Плитоносец «средний» (броня уровня 2 из 3) — ФОРМА v02 на согласование, материал нейтральный.\n"
    "По фото владельца (voenform.ru) и фото серийных плитоносцев: передний пакет — карман смены плиты сверху\n"
    "(клапан на велкро с язычком; плита Mid_Plate_Front и клапан Mid_Pocket_Lid — отдельные объекты с опорными\n"
    "точками под анимацию), задний пакет, велкро-панель с решёткой и резинками-держателями, MOLLE, плечевые\n"
    "накладки с кольцами и петлями под провод, камербанд под клапаном «кенгуру» (над ним язычки вставки под\n"
    "магазины), фастексы на левом боку, язычки с пряжками внизу, ручка и люверсы сзади.\n"
    "Коллекция 06_Armor_Mid; надет на мародёра v02 поверх куртки.\n"
    "Текстуры (расцветка) — после принятия формы. Марки и нашивки с фото не переносятся.\n"
    "Скрипт: tools/npc_kit/armor_mid.py (детали — armor_kit.py).\n")


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"npc_scav_{kc.VERSION}.blend"))
    f = fit()
    col = kc.collection("06_Armor_Mid")
    build_carrier(f, CarrierSpec(), col, materials())
    kc.log("ARMOR_MID", len(col.objects), "объектов,", triangles(col), "треугольников")
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(OUT / "armor_mid.blend")
    if "render" in args:
        render_previews(col, "mid", extra={
            "close_chest": ((0.28, -0.75, 1.42), (0.0, -0.2, 1.33)),
            "close_side": ((0.75, -0.45, 1.25), (0.15, -0.08, 1.22)),
            "close_shoulder": ((0.45, -0.55, 1.68), (0.11, -0.05, 1.50)),
        })
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(Path(dest), "Броня_средняя_v02_форма.blend", README)


if __name__ == "__main__":
    main()
