"""Кабина пожарной АЦ генератором кузовов «Проспекта» (поле формы + панели по видам), а не sand3d.

Тот же способ, что у принятых ГАЗели, ПАЗа и легковых (tools/prospekt_vehicles, tools/coupe_ilya): форма кабины —
гладкое поле BoxField по профилям (сбоку, спереди, сверху), панели — области на видах, поднятые лучами на поверхность,
с завёрнутыми внутрь кромками и зазорами по общим швам. Швы, общие для двух панелей, строятся одной кривой на кузове.

Панели: передняя маска (рамка лобового стекла с заходом на углы до дверей, низ над бампером), откидная облицовка
с двумя щелями решётки, двери с проёмами окон, узкие задние стойки, крылья с аркой и нишей подножки, крыша
(с кромками), задняя стенка; стёкла по поверхности с уплотнителями; дворники и дефлекторы стоек — накладками по
поверхности. Остальная кабина (бампер, зеркала, колпак, ручки) — в cab.py.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PV = HERE.parent / "prospekt_vehicles"
if str(PV) not in sys.path:
    sys.path.append(str(PV))

import vlib  # noqa: E402  (добавляет tools/coupe_ilya в путь)
from vlib import View, ViewR, domain_panel, fillet_poly, lift_poly, loop, mirror_mesh, sym_loop  # noqa: E402
from vfield import BoxField  # noqa: E402
from surface import Surface  # noqa: E402
import parts as pt  # noqa: E402  (tools/coupe_ilya/parts.py)

import bpy  # noqa: E402
import lib  # noqa: E402
import spec as S  # noqa: E402

F, B = S.CAB_FRONT, S.CAB_BACK
HW = S.CAB_W / 2
GAP = 0.005
Z_SEAM = S.DOOR["z0"]            # линия низа дверей = верх крыльев
Z_TOP_SIDE = S.DOOR["z1"]        # верх дверей = край крыши на борту
Y_DOOR0, Y_DOOR1 = S.DOOR["y0"], S.DOOR["y1"]
Y_QUARTER = B - 0.032            # задний край стойки — до скругления заднего угла
Y_FENDER0, Y_FENDER1 = S.FENDER["y0"], S.FENDER["y1"]
Z_FENDER0 = S.FENDER["z0"]
Z_MASK_LOW = S.BUMPER["z1"]      # низ маски спереди — по верху бампера
Z_MASK_TOP = 2.93                # верх маски спереди (на скруглении к крыше)
ARCH_PANEL_R = S.ARCH_R_F + 0.022


def field_spec() -> dict:
    """Профили кабины: лицо почти отвесное до низа стекла, стекло завалено назад; перед слегка выпуклый
    (уходит назад к углам), боковины выше пояса чуть завалены внутрь; снизу сзади — продолжение под подножки."""
    ws0, ws1 = S.WS_BOTTOM, S.WS_TOP
    yw0 = F + 0.012
    yw1 = yw0 + S.WS_LEAN
    return dict(
        name="kamaz_cab",
        top=[(F - 0.4, S.CAB_ROOF), (B + 0.6, S.CAB_ROOF)],
        bottom=[(F - 0.4, Z_FENDER0 - 0.06), (B + 0.6, Z_FENDER0 - 0.06)],
        front=[(0.30, F + 0.02), (0.98, F + 0.004), (1.40, F + 0.004), (ws0, yw0), (ws1, yw1),
               (3.30, yw1 + (yw1 - yw0) / (ws1 - ws0) * (3.30 - ws1))],
        rear=[(0.30, Y_FENDER1 + 0.01), (Z_SEAM + 0.02, Y_FENDER1 + 0.01), (Z_SEAM + 0.11, B), (3.30, B)],
        plan=[(F - 0.4, HW), (B + 0.6, HW)],
        section=[(0.30, 1.0), (1.95, 1.0), (S.CAB_ROOF, 0.988), (3.30, 0.98)],
        nose_sweep=[(0.0, 0.0), (0.4, 0.004), (0.7, 0.016), (0.9, 0.040), (1.0, 0.062), (1.2, 0.12)],
        r_corner=0.075, r_corner_rear=0.03, r_roof=0.09, r_bot=0.01,
        wheel_y=[S.YF], wheel_z=S.WHEEL_Z, arch_r=S.ARCH_R_F, well_x=0.95, r_arch=0.015,
        curve_kind="pchip",
    )


def views() -> dict:
    """Виды: борт, перед, зад, вокруг носа (маска заходит на углы), лобовое стекло, крыша с кромками."""
    reach = 5.0
    V = {k: ViewR(k, reach=reach) for k in ("side", "front", "rear")}
    V["rf"] = View("cyl", c=(0.0, F + 0.60, 0.0), a=(0, 0, 1), e0=(0, -1, 0))
    dy, dz = S.WS_LEAN, S.WS_TOP - S.WS_BOTTOM
    n = math.hypot(dy, dz)
    vv = (0.0, dy / n, dz / n)
    p = np.array([0.0, -dz, dy]) / n                   # нормаль стекла наружу (вперёд и вверх)
    V["ws"] = ViewR("plane", u=(1, 0, 0), v=vv, d=tuple(-p), reach=reach)
    V["roof"] = View("cyl", c=(0.0, 0.0, 1.60), a=(0, 1, 0), e0=(0, 0, 1))
    return V


def rf_u(x: float, y: float) -> float:
    """Угол точки борта/лица на виде «вокруг носа» (радианы, r0 = 1)."""
    return math.atan2(x, -(y - (F + 0.60)))


def ws_v(z: float) -> float:
    """Координата вдоль стекла на виде лобового для высоты z (по профилю лица)."""
    dy, dz = S.WS_LEAN, S.WS_TOP - S.WS_BOTTOM
    n = math.hypot(dy, dz)
    y = F + 0.012 + dy * (z - S.WS_BOTTOM) / dz
    return (y * dy + z * dz) / n


def line_on(surf, view, a, b, step: float = 0.004) -> np.ndarray:
    return lift_poly(surf, view, np.array([a, b], float), step)


DOOR_T = 0.075          # толщина двери от наружной панели до обивки
JAMB_D = 0.085          # глубина откоса проёма
PIVOT = (HW + 0.010, Y_DOOR0 - 0.005)     # ось петель левой двери: снаружи у передней кромки (дверь не задевает маску)


def side_shift(surf, L: np.ndarray, d: float) -> np.ndarray:
    """Контур на борту, сдвинутый в плоскости вида сбоку на d внутрь своей области (d < 0 — наружу), на поверхность."""
    uv = L[:, 1:3]
    area = 0.5 * float(np.sum(uv[:, 0] * np.roll(uv[:, 1], -1) - np.roll(uv[:, 0], -1) * uv[:, 1]))
    t = np.roll(uv, -1, axis=0) - np.roll(uv, 1, axis=0)
    left = np.c_[-t[:, 1], t[:, 0]]
    left /= np.maximum(np.linalg.norm(left, axis=1, keepdims=True), 1e-12)
    into = left if area > 0 else -left
    P = L.copy()
    P[:, 1:3] += into * d
    P = surf.project(P)
    for _ in range(3):                                   # углы: убрать петельки от сдвига
        P = (np.roll(P, 1, axis=0) + 2 * P + np.roll(P, -1, axis=0)) / 4
    return P


def push(surf, L: np.ndarray, depth: float) -> np.ndarray:
    """Контур, утопленный внутрь кузова по нормали поверхности."""
    return L - surf.normal(L) * depth


def band(A: np.ndarray, B: np.ndarray, outward: bool) -> tuple[np.ndarray, list]:
    """Лента между двумя замкнутыми контурами одинаковой длины; грани — от центра контура (outward) или к нему."""
    n = len(A)
    V = np.vstack([A, B])
    Fc = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
    c = A.mean(axis=0)
    i = int(np.argmax(A[:, 2]))
    nrm = np.cross(A[(i + 1) % n] - A[i], B[i] - A[i])
    radial = (A[i] + A[(i + 1) % n]) / 2 - c
    radial[0] = 0.0
    if (float(nrm @ radial) > 0) != outward:
        Fc = [f[::-1] for f in Fc]
    return V, Fc


def tube_loop(P: np.ndarray, r: float, n_sec: int = 8) -> tuple[np.ndarray, list]:
    """Резиновый жгут по замкнутому контуру (уплотнитель проёма)."""
    n = len(P)
    T = np.roll(P, -1, axis=0) - np.roll(P, 1, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    up = np.tile([1.0, 0.0, 0.0], (n, 1))
    Bn = np.cross(T, up)
    Bn /= np.maximum(np.linalg.norm(Bn, axis=1, keepdims=True), 1e-12)
    Nn = np.cross(Bn, T)
    ang = np.linspace(0, 2 * math.pi, n_sec, endpoint=False)
    V = np.vstack([P + r * (math.cos(a) * Nn + math.sin(a) * Bn) for a in ang])
    Fc = []
    for k in range(n_sec):
        k2 = (k + 1) % n_sec
        for i in range(n):
            i2 = (i + 1) % n
            Fc.append((k * n + i, k * n + i2, k2 * n + i2, k2 * n + i))
    return V, Fc


def fill_side(outer: np.ndarray, holes: list, face_x: float) -> tuple[np.ndarray, list]:
    """Почти плоская панель по контуру с проёмами (обивка): разбиение на виде сбоку, грани смотрят по знаку face_x."""
    loops = [outer] + list(holes)
    V3 = np.vstack(loops)
    v2, tris = pt.poly_mesh(outer[:, 1:3], [h[:, 1:3] for h in holes])
    if len(v2) != len(V3):
        idx = [int(np.argmin(np.sum((V3[:, 1:3] - p) ** 2, axis=1))) for p in v2]
        V3 = V3[idx]
    t0 = tris[0]
    nrm = np.cross(V3[t0[1]] - V3[t0[0]], V3[t0[2]] - V3[t0[0]])
    if nrm[0] * face_x < 0:
        tris = [t[::-1] for t in tris]
    return V3, tris


def door_inner(surf, door_outer: np.ndarray, win_loop: np.ndarray) -> list:
    """Левая дверь изнутри и её проём: торец двери, откос окна, обивка; откос проёма с уплотнителем."""
    out = []
    door = vlib.resample_closed(door_outer, 0.008)
    win = vlib.resample_closed(win_loop, 0.008)
    eA = push(surf, side_shift(surf, door, 0.008), 0.010)
    eB = push(surf, eA, DOOR_T - 0.010)
    out.append(("Cab_DoorEdge_L", "white", *band(eA, eB, outward=True)))
    wA = push(surf, side_shift(surf, win, -0.006), 0.040)
    wB = push(surf, wA, DOOR_T - 0.040)
    out.append(("Cab_DoorReveal_L", "black", *band(wA, wB, outward=False)))
    out.append(("Cab_DoorCard_L", "trim", *fill_side(eB, [wB[::-1]], -1.0)))
    aA = push(surf, side_shift(surf, door, -0.008), 0.012)
    aB = push(surf, aA, JAMB_D)
    out.append(("Cab_Jamb_L", "white", *band(aA, aB, outward=False)))
    seal = push(surf, side_shift(surf, door, -0.001), 0.045)
    out.append(("Cab_JambSeal_L", "rubber", *tube_loop(seal, 0.008)))
    return out


def build_panels() -> list:
    """[(имя, покраска, V, F)] панелей левой половины + симметричных; правые — зеркалом."""
    field = BoxField(field_spec())
    surf = Surface(field)
    Vw = views()
    out: list = []

    def panel(name, paint, view, outer, holes=(), h=0.022, **kw):
        err = None
        for k in range(5):
            try:
                V, Fc = domain_panel(surf, Vw[view], outer, holes=holes, h=h * (1 + 0.07 * k), **kw)
                out.append((name, paint, V, Fc))
                return V, Fc
            except Exception as e:  # совпадение узлов с контуром — другой шаг
                err = e
        raise RuntimeError(f"панель {name} не собрана: {err}")

    side = Vw["side"]
    # --- общие швы на левом борту ---------------------------------------------------------------
    door_front = line_on(surf, side, (Y_DOOR0, Z_SEAM), (Y_DOOR0, Z_TOP_SIDE))
    door_rear = line_on(surf, side, (Y_DOOR1, Z_SEAM), (Y_DOOR1, Z_TOP_SIDE))
    seam_low_mask = line_on(surf, side, (Y_FENDER0, Z_SEAM), (Y_DOOR0, Z_SEAM))
    seam_low_door = line_on(surf, side, (Y_DOOR0, Z_SEAM), (Y_DOOR1, Z_SEAM))
    seam_low_q = line_on(surf, side, (Y_DOOR1, Z_SEAM), (Y_QUARTER, Z_SEAM))
    top_door = line_on(surf, side, (Y_DOOR0, Z_TOP_SIDE), (Y_DOOR1, Z_TOP_SIDE))
    top_q = line_on(surf, side, (Y_DOOR1, Z_TOP_SIDE), (Y_QUARTER, Z_TOP_SIDE))
    q_rear = line_on(surf, side, (Y_QUARTER, Z_SEAM), (Y_QUARTER, Z_TOP_SIDE))
    fender_front = line_on(surf, side, (Y_FENDER0, Z_MASK_LOW), (Y_FENDER0, Z_SEAM))

    # --- передняя маска: от оси снизу, по углу, вдоль крыла, по шву двери, поверху — к оси ------------------
    rf = Vw["rf"]
    u_fe = rf_u(HW, Y_FENDER0)
    u_door = rf_u(HW, Y_DOOR0)
    m_bottom = lift_poly(surf, rf, np.array([(0.0, Z_MASK_LOW), (u_fe, Z_MASK_LOW)]), 0.004)
    m_top = lift_poly(surf, rf, fillet_poly([(u_door, Z_TOP_SIDE), (1.20, Z_TOP_SIDE + 0.01), (0.95, Z_MASK_TOP),
                                             (0.0, Z_MASK_TOP)], 0.10, closed=False, n_arc=10), 0.004)
    m_top[0] = door_front[-1]
    m_bottom[-1] = fender_front[0]
    mask_outer = sym_loop([m_bottom, fender_front, seam_low_mask, door_front, m_top])
    # проёмы маски: лобовое (по виду стекла) и облицовка (по виду спереди)
    wsv = Vw["ws"]
    wsw, wv0, wv1 = 1.03, ws_v(S.WS_BOTTOM + 0.04), ws_v(S.WS_TOP - 0.03)
    ws_uv = vlib.fillet_poly([(-wsw, wv0), (wsw, wv0), (wsw, wv1), (-wsw, wv1)], [0.10, 0.10, 0.14, 0.14],
                             closed=True, n_arc=10)
    ws_loop = lift_poly(surf, wsv, np.vstack([ws_uv, ws_uv[:1]]), 0.004)[:-1]
    fp = dict(x=1.02, z0=1.13, z1=1.84)
    grille_uv = vlib.fillet_poly([(-fp["x"], fp["z0"]), (fp["x"], fp["z0"]), (fp["x"], fp["z1"]), (-fp["x"], fp["z1"])],
                                 0.05, closed=True, n_arc=8)
    front = Vw["front"]
    grille_loop = lift_poly(surf, front, np.vstack([grille_uv, grille_uv[:1]]), 0.004)[:-1]
    panel("Cab_Front_Mask", "red", "rf", mask_outer, holes=[ws_loop, grille_loop], h=0.022, gap=GAP, hole_depth=0.035)

    # --- откидная облицовка с двумя щелями решётки --------------------------------------------------------
    slots = []
    for w, z, hgt in ((1.46, 1.50, 0.085), (1.30, 1.33, 0.085)):
        su = vlib.fillet_poly([(-w / 2, z - hgt / 2), (w / 2, z - hgt / 2), (w / 2, z + hgt / 2), (-w / 2, z + hgt / 2)],
                              0.035, closed=True, n_arc=8)
        slots.append(lift_poly(surf, front, np.vstack([su, su[:1]]), 0.003)[:-1])
    panel("Cab_Grille_Panel", "red", "front", grille_loop, holes=slots, h=0.02, gap=GAP, hole_depth=0.05)

    # --- лобовое стекло и его уплотнитель ------------------------------------------------------------------
    panel("Cab_Windshield", "glass", "ws", ws_loop, h=0.05, gap=0.004, flange=0.02, fit_deg=2, fit_blend=0.03)
    out.append(("Cab_Windshield_Seal", "rubber", *pt.strip_on_surface(surf, np.vstack([ws_loop, ws_loop[:1]]), 0.022, 0.008,
                                                                         0.0, r=0.003)))
    frit = vlib.offset_loop(surf, wsv, ws_loop, 0.034)
    out.append(("Cab_Windshield_Frit", "black", *pt.strip_on_surface(surf, np.vstack([frit, frit[:1]]), 0.05, 0.0012,
                                                                        -0.0045, r=0.0004)))

    # --- борт (левый; правый — зеркалом) -------------------------------------------------------------------
    left: list = []
    win = S.SIDE_WIN
    win_uv = vlib.fillet_poly([(win["y0"], win["z0"]), (win["y1"], win["z0"]), (win["y1"], win["z1"]), (win["y0"], win["z1"])],
                              [0.04, 0.06, 0.08, 0.10], closed=True, n_arc=8)
    win_loop = lift_poly(surf, side, np.vstack([win_uv, win_uv[:1]]), 0.004)[:-1]
    door_outer = loop([seam_low_door, door_rear, top_door[::-1], door_front[::-1]], tol=0.015)
    n0 = len(out)
    panel("Cab_Door_L", "white", "side", door_outer, holes=[win_loop], h=0.022, gap=GAP, hole_depth=0.04)
    panel("Cab_Door_Glass_L", "glass", "side", win_loop, h=0.05, gap=0.004, flange=0.02, fit_deg=2, fit_blend=0.03)
    out.append(("Cab_Door_Seal_L", "rubber", *pt.strip_on_surface(surf, np.vstack([win_loop, win_loop[:1]]), 0.018, 0.007,
                                                                     0.0, r=0.0025)))
    out += door_inner(surf, door_outer, win_loop)
    q_outer = loop([seam_low_q, q_rear, top_q[::-1], door_rear[::-1]], tol=0.015)
    panel("Cab_Quarter_L", "white", "side", q_outer, h=0.018, gap=GAP)
    # крыло: перед — за бампером, верх — по шву низа дверей, сзади — подножки, низ — по арке
    a_r = ARCH_PANEL_R
    zb = Z_FENDER0
    dz = zb - S.WHEEL_Z
    y_af = S.YF - math.sqrt(max(a_r * a_r - dz * dz, 0.0))
    y_ar = S.YF + math.sqrt(max(a_r * a_r - dz * dz, 0.0))
    arch = []
    n_arc = 48
    a0 = math.atan2(dz, y_ar - S.YF)               # задний низ арки
    a1 = math.pi - a0                               # передний низ арки
    for k in range(n_arc + 1):
        a = a0 + (a1 - a0) * k / n_arc
        arch.append((S.YF + a_r * math.cos(a), S.WHEEL_Z + a_r * math.sin(a)))
    # точки арки идут от заднего низа через верх к переднему: в контуре — обратно (перед → верх → зад)
    fender_uv = [(Y_FENDER0, zb), (y_af, zb)] + arch[::-1] + [(y_ar, zb), (Y_FENDER1, zb), (Y_FENDER1, Z_SEAM),
                                                              (Y_FENDER0, Z_SEAM)]
    fender_uv = fillet_poly(fender_uv, [0.03, 0.0] + [0.0] * (n_arc + 1) + [0.0, 0.03, 0.03, 0.03], closed=True, n_arc=6)
    step_uv = vlib.fillet_poly([(S.STEP_Y - 0.08, S.STEPS_Z[1]), (S.STEP_Y + 0.08, S.STEPS_Z[1]),
                                (S.STEP_Y + 0.08, S.STEPS_Z[1] + 0.19), (S.STEP_Y - 0.08, S.STEPS_Z[1] + 0.19)],
                               0.02, closed=True, n_arc=6)
    step_loop = lift_poly(surf, side, np.vstack([step_uv, step_uv[:1]]), 0.003)[:-1]
    fender_loop = lift_poly(surf, side, np.vstack([fender_uv, fender_uv[:1]]), 0.004)[:-1]
    panel("Cab_Fender_L", "white", "side", fender_loop, holes=[step_loop], h=0.02, gap=GAP, hole_depth=0.11, smooth=False)
    left = out[n0:]

    # --- крыша и задняя стенка (общие для обеих сторон) ------------------------------------------------------
    rear_v = Vw["rear"]
    z_back_top = Z_TOP_SIDE + 0.03
    # крыша: перед — верх маски, борта — верх дверей и стоек, зад — по верху задней стенки; обход от оси к оси
    back_top_l = lift_poly(surf, rear_v, np.array([(HW - 0.03, z_back_top), (0.0, z_back_top)]), 0.004)
    link_l = np.array([top_q[-1], back_top_l[0]])
    roof_outer = sym_loop([m_top[::-1], top_door, top_q, link_l, back_top_l])
    panel("Cab_Roof", "white", "roof", roof_outer, h=0.03, gap=GAP)
    back_uv = vlib.fillet_poly([(-(HW - 0.03), Z_SEAM + 0.06), (HW - 0.03, Z_SEAM + 0.06), (HW - 0.03, z_back_top),
                                (-(HW - 0.03), z_back_top)], 0.02, closed=True, n_arc=6)
    panel("Cab_Back", "dark", "rear", back_uv, h=0.04, gap=GAP)

    # правая сторона — зеркалом левой
    for name, paint, V, Fc in left:
        W, G = mirror_mesh(np.asarray(V), Fc)
        out.append((name[:-2] + "_R", paint, W, G))

    # --- дворники и дефлекторы стоек — накладками по поверхности ---------------------------------------------
    for k, (xp, ang) in enumerate(((-0.86, 9.0), (0.04, 9.0))):
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        p0 = np.array([xp, wv0 + 0.04])
        arm = lift_poly(surf, wsv, np.array([p0, p0 + 0.60 * np.array([c, s_])]), 0.006)
        tip = p0 + 0.60 * np.array([c, s_])
        c2, s2 = math.cos(math.radians(ang - 2)), math.sin(math.radians(ang - 2))
        blade = lift_poly(surf, wsv, np.array([tip - 0.33 * np.array([c2, s2]), tip + 0.33 * np.array([c2, s2])]), 0.006)
        out.append((f"Wiper_Arm_{k}", "black", *pt.strip_on_surface(surf, arm, 0.022, 0.010, 0.012, r=0.004)))
        out.append((f"Wiper_Blade_{k}", "black", *pt.strip_on_surface(surf, blade, 0.016, 0.014, 0.003, r=0.004)))
        out.append((f"Wiper_Rubber_{k}", "rubber", *pt.strip_on_surface(surf, blade, 0.008, 0.006, -0.001, r=0.002)))
    for sgn in (1, -1):
        u = sgn * rf_u(HW - 0.06, F + 0.10)
        line = lift_poly(surf, rf, np.array([(u, S.WS_BOTTOM + 0.05), (u, S.WS_TOP - 0.02)]), 0.006)
        out.append((f"Pillar_Deflector_{'L' if sgn > 0 else 'R'}", "black",
                    *pt.strip_on_surface(surf, line, 0.13, 0.012, 0.0, r=0.005)))
    return out


def _trim(ob):
    return lib.s3d.material(ob, "plastic", color="#34373a", roughness=0.65)


PAINT = {"red": lib.paint_red, "white": lib.paint_white, "glass": lib.glass, "rubber": lib.rubber,
         "black": lib.black_plastic, "dark": lib.steel_dark, "trim": _trim}
DOOR_PARTS = ("Cab_Door_", "Cab_DoorEdge_", "Cab_DoorReveal_", "Cab_DoorCard_")
LINED = ("Cab_Front_Mask", "Cab_Quarter_L", "Cab_Quarter_R")      # изнанка видна из салона — тёмная подкладка


def lining(ob, name: str):
    """Подкладка листовой панели изнутри: та же сетка, сдвинутая на 4 мм внутрь по нормалям, грани развёрнуты,
    цвет обивки — чтобы из салона не была видна краска наружной стороны."""
    import meshfix
    meshfix.clean(ob, verbose=False)              # подкладка — с уже чистой сетки (без осколков разбиения)
    me = ob.data
    me.update()
    V = np.array([v.co[:] for v in me.vertices]) - np.array([v.normal[:] for v in me.vertices]) * 0.004
    Fc = [tuple(p.vertices)[::-1] for p in me.polygons]
    m2 = bpy.data.meshes.new(name)
    m2.from_pydata([tuple(map(float, v)) for v in V], [], Fc)
    m2.validate()
    m2.polygons.foreach_set("use_smooth", [True] * len(m2.polygons))
    o2 = bpy.data.objects.new(name, m2)
    bpy.context.scene.collection.objects.link(o2)
    _trim(o2)
    return o2


def build() -> dict:
    """Панели кабины объектами Blender (материалы — метками sand3d): {"common": […], "door_L": […], "door_R": […]}."""
    got = {"common": [], "door_L": [], "door_R": []}
    for name, paint, V, Fc in build_panels():
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(map(float, v)) for v in np.asarray(V)], [], [tuple(int(i) for i in f) for f in Fc])
        me.validate()
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        PAINT[paint](ob)
        if name in LINED:
            got["common"].append(lining(ob, name + "_Lining"))
        key = "common"
        if name.startswith(DOOR_PARTS):
            key = "door_L" if name.endswith("_L") else "door_R"
        got[key].append(ob)
    return got
