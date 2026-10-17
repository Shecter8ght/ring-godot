"""Купе Ильи: раскладка панелей — швы, контуры и проёмы (свой дизайн по мотивам CLE 53).

Все размеры в метрах, левый борт (+X); правый получается зеркалом. Точки швов — на видах
(см. seams.py). Числа сняты с чертежа CLE и подправлены под концепт владельца: своя решётка
(высокая, скруглённая, с вертикальными рёбрами), трапеции боковых воздухозаборников, широкий
нижний, фара под кромкой капота с заходом на борт.
"""
from __future__ import annotations

import math

import numpy as np

from domain import domain_panel
from fieldcore import WHEEL_Y, WHEEL_Z
from seams import VIEWS, Seam, loop
from surface import Surface, resample

GAP = 0.0045                 # обычный зазор панелей
GAP_TIGHT = 0.0035           # бампер — крыло, фары
ARCH_LIP_R = 0.392           # кромка арки (вырез поля — 0,388)


def _sym(half: list[tuple[float, float]], closed_at_axis: bool) -> list[tuple[float, float]]:
    """Симметричный контур вида спереди/сзади из левой половины (от оси сверху к оси снизу)."""
    tail = half[1:-1] if closed_at_axis else half[1:]
    return half + [(-x, z) for x, z in reversed(tail)]


# Проёмы переднего бампера, вид спереди (X, Z): решётка, левый боковой, нижний
GRILLE = _sym([(0.0, 0.790), (0.30, 0.788), (0.40, 0.776), (0.437, 0.745), (0.447, 0.68), (0.441, 0.60),
               (0.415, 0.537), (0.36, 0.507), (0.20, 0.498)], False)
INTAKE_L = [(0.555, 0.585), (0.70, 0.620), (0.808, 0.635), (0.842, 0.600), (0.850, 0.45), (0.835, 0.300),
            (0.780, 0.262), (0.640, 0.270), (0.545, 0.320), (0.515, 0.420), (0.525, 0.530)]
LOWER = _sym([(0.0, 0.432), (0.32, 0.428), (0.415, 0.408), (0.462, 0.352), (0.448, 0.288), (0.385, 0.265),
              (0.0, 0.262)], True)
EXHAUST_L = [(0.470, 0.438), (0.672, 0.440), (0.686, 0.425), (0.665, 0.388), (0.482, 0.388), (0.462, 0.415)]


def arch_pts(yc: float, phi0: float, phi1: float, n: int = 9, r: float = ARCH_LIP_R):
    """Точки дуги арки на виде сбоку: φ в градусах, 0 — назад (+Y), 90 — вверх."""
    return [("side", yc + r * math.cos(math.radians(p)), WHEEL_Z + r * math.sin(math.radians(p)))
            for p in np.linspace(phi0, phi1, n)]


def phi_at_z(z: float, front_side: bool) -> float:
    s = math.degrees(math.asin((z - WHEEL_Z) / ARCH_LIP_R))
    return 180.0 - s if front_side else s


def rf_pt(theta_deg: float, z: float):
    """Точка на углу носа: угол от оси машины к левому борту (вокруг вертикали Y = −1,55) и высота."""
    return ("rf", math.radians(theta_deg), z)


def rr_pt(theta_deg: float, z: float):
    """Точка на углу кормы: угол от оси машины к левому борту (вокруг вертикали Y = 1,60) и высота."""
    return ("rr", math.radians(theta_deg), -z)


def mirror_curve(c: np.ndarray) -> np.ndarray:
    m = c.copy()
    m[:, 0] *= -1
    return m


def sym_loop(left: list[np.ndarray]) -> np.ndarray:
    """Контур симметричной панели: левая половина от оси до оси, правая — зеркально обратно."""
    return loop(left + [mirror_curve(c)[::-1] for c in reversed(left)])


def mirror_mesh(V: np.ndarray, F: list) -> tuple[np.ndarray, list]:
    W = V.copy()
    W[:, 0] *= -1
    return W, [f[::-1] for f in F]


def build_all(surf: Surface) -> list[tuple[str, str, np.ndarray, list]]:
    out: list[tuple[str, str, np.ndarray, list]] = []
    YF = -WHEEL_Y
    # --- Углы (левый борт) -------------------------------------------------------------------
    hood_rear_c = ("top", 0.0, -0.900)
    hood_rear_l = ("top", 0.830, -0.950)
    hood_lamp_in = ("top", 0.455, -2.110)        # A: передний угол капота над фарой
    hood_lamp_out = ("top", 0.720, -1.880)       # B: здесь верх фары уходит от капота на борт
    hood_front_c = ("top", 0.0, -2.150)
    lamp_tip = ("side", -1.748, 0.778)           # D: хвост фары на борту
    lamp_in_low = ("front", 0.470, 0.765)        # H: нижний внутренний носик фары (фара узкая, как на концепте)
    # Шов бампера подходит к арке по радиусу (почти под прямым углом), а не по касательной
    PHI_BUMP = 122.0
    arch_bump = ("side", YF + ARCH_LIP_R * math.cos(math.radians(PHI_BUMP)), WHEEL_Z + ARCH_LIP_R * math.sin(math.radians(PHI_BUMP)))
    phi_fb = phi_at_z(0.235, True)               # низ бампера у арки
    arch_bot_f = ("side", YF + ARCH_LIP_R * math.cos(math.radians(phi_fb)), 0.235)
    phi_sf = phi_at_z(0.300, False)              # верх порога у передней арки
    arch_sill_f = ("side", YF + ARCH_LIP_R * math.cos(math.radians(phi_sf)), 0.300)
    door_fb = ("side", -0.700, 0.335)
    door_ft = ("side", -0.680, 0.955)
    door_rb = ("side", 0.400, 0.352)
    door_rt = ("side", 0.590, 1.005)
    phi_sr = phi_at_z(0.360, True)
    arch_sill_r = ("side", WHEEL_Y + ARCH_LIP_R * math.cos(math.radians(phi_sr)), 0.360)

    # --- Швы ---------------------------------------------------------------------------------
    S = {}
    S["cowl"] = Seam(surf, [hood_rear_c, ("top", 0.42, -0.915), hood_rear_l], "top")
    S["hood_side"] = Seam(surf, [hood_rear_l, ("top", 0.812, -1.20), ("top", 0.795, -1.50), ("top", 0.770, -1.74),
                                 hood_lamp_out], "top")
    S["hood_lamp"] = Seam(surf, [hood_lamp_out, ("top", 0.640, -1.975), ("top", 0.540, -2.065), hood_lamp_in], "top")
    S["hood_front"] = Seam(surf, [hood_lamp_in, ("top", 0.330, -2.140), ("top", 0.160, -2.148), hood_front_c], "top")
    S["lamp_top_out"] = Seam(surf, [hood_lamp_out, rf_pt(69.7, 0.845), ("side", -1.82, 0.802), lamp_tip], "rf")
    S["lamp_bottom"] = Seam(surf, [lamp_tip, ("side", -1.80, 0.766), ("side", -1.92, 0.752), ("front", 0.800, 0.745),
                                   ("front", 0.690, 0.748), ("front", 0.580, 0.755), lamp_in_low], "rf")
    S["lamp_inner"] = Seam(surf, [lamp_in_low, ("front", 0.460, 0.795), hood_lamp_in], "rf")
    S["bump_fender"] = Seam(surf, [lamp_tip, ("side", -1.700, 0.745), arch_bump], "side")
    S["arch_f_front"] = Seam(surf, [arch_bump] + arch_pts(YF, PHI_BUMP, phi_fb, 9)[1:-1] + [arch_bot_f], "side")
    S["arch_f_top"] = Seam(surf, [arch_bump] + arch_pts(YF, PHI_BUMP, phi_sf, 13)[1:-1] + [arch_sill_f], "side")
    S["sill_f"] = Seam(surf, [arch_sill_f, ("side", -0.90, 0.318), door_fb], "side")
    S["door_front"] = Seam(surf, [door_fb, ("side", -0.728, 0.45), ("side", -0.752, 0.632), ("side", -0.742, 0.80),
                                  ("side", -0.715, 0.90), door_ft], "side")
    S["fender_apillar"] = Seam(surf, [door_ft, ("top", 0.86, -0.78), hood_rear_l], "rs")
    S["door_top"] = Seam(surf, [door_ft, ("side", -0.37, 0.972), ("side", 0.20, 0.992), door_rt], "side")
    S["door_rear"] = Seam(surf, [door_rb, ("side", 0.470, 0.376), ("side", 0.525, 0.445), ("side", 0.572, 0.567),
                                 ("side", 0.617, 0.75), ("side", 0.633, 0.85), ("side", 0.630, 0.92), door_rt], "side")
    S["door_bottom"] = Seam(surf, [door_fb, ("side", -0.30, 0.333), ("side", 0.10, 0.337), door_rb], "side")
    S["sill_r"] = Seam(surf, [door_rb, ("side", 0.75, 0.357), arch_sill_r], "side")

    # --- Капот (целиком, обе половины) -------------------------------------------------------
    left = [S["cowl"].P, S["hood_side"].P, S["hood_lamp"].P, S["hood_front"].P]
    right = [mirror_curve(c)[::-1] for c in reversed(left)]
    hood_loop = loop(left + right)
    S["_hood_loop"] = hood_loop
    V, F = domain_panel(surf, VIEWS["top"], hood_loop, h=0.014, gap=GAP)
    out.append(("Hood", "paint", V, F))

    # --- Крыло левое ---------------------------------------------------------------------------
    fender = loop([S["door_front"].reversed(), S["sill_f"].reversed(), S["arch_f_top"].reversed(),
                   S["bump_fender"].reversed(), S["lamp_top_out"].reversed(), S["hood_side"].reversed(),
                   S["fender_apillar"].reversed()])
    V, F = domain_panel(surf, VIEWS["rs"], fender, h=0.012, gap=GAP)
    out.append(("Fender_L", "paint", V, F))
    out.append(("Fender_R", "paint", *mirror_mesh(V, F)))

    # --- Дверь левая -----------------------------------------------------------------------------
    door = loop([S["door_bottom"].P, S["door_rear"].P, S["door_top"].reversed(), S["door_front"].reversed()])
    V, F = domain_panel(surf, VIEWS["side"], door, h=0.012, gap=GAP)
    out.append(("Door_L", "paint", V, F))
    out.append(("Door_R", "paint", *mirror_mesh(V, F)))

    # --- Порог левый (между арками, под дверью) -------------------------------------------------
    phi_fs_low = phi_at_z(0.205, False)
    phi_rs_low = phi_at_z(0.205, True)
    sk_f_low = ("side", YF + ARCH_LIP_R * math.cos(math.radians(phi_fs_low)), 0.205)
    sk_r_low = ("side", WHEEL_Y + ARCH_LIP_R * math.cos(math.radians(phi_rs_low)), 0.205)
    S["arch_f_sill"] = Seam(surf, [sk_f_low] + arch_pts(YF, phi_fs_low, phi_sf, 5)[1:-1] + [arch_sill_f], "side")
    S["arch_r_sill"] = Seam(surf, [("p", *S["sill_r"].P[-1])] + arch_pts(WHEEL_Y, phi_sr, phi_rs_low, 5)[1:-1] + [sk_r_low], "side")
    S["skirt_bottom"] = Seam(surf, [sk_r_low, ("side", 0.40, 0.200), ("side", -0.40, 0.199), sk_f_low], "side")
    skirt = loop([S["sill_f"].P, S["door_bottom"].P, S["sill_r"].P, S["arch_r_sill"].P, S["skirt_bottom"].P,
                  S["arch_f_sill"].P])
    V, F = domain_panel(surf, VIEWS["side"], skirt, h=0.010, gap=GAP)
    out.append(("Skirt_L", "trim_black", V, F))
    out.append(("Skirt_R", "trim_black", *mirror_mesh(V, F)))

    # --- Фара левая (стекло в своём проёме) ------------------------------------------------------
    lamp = loop([S["hood_lamp"].P, S["lamp_inner"].reversed(), S["lamp_bottom"].reversed(), S["lamp_top_out"].reversed()])
    V, F = domain_panel(surf, VIEWS["rf"], lamp, h=0.008, gap=GAP_TIGHT, flange=0.03)
    out.append(("Headlamp_L", "lamp_glass", V, F))
    out.append(("Headlamp_R", "lamp_glass", *mirror_mesh(V, F)))

    # --- Передний бампер (целиком) с решёткой и воздухозаборниками -------------------------------
    splitter_c = ("front", 0.0, 0.225)
    S["bump_bottom"] = Seam(surf, [arch_bot_f, rf_pt(66.0, 0.228), ("front", 0.70, 0.226),
                                   ("front", 0.35, 0.225), splitter_c], "rf")
    bl = [S["hood_front"].reversed(), S["lamp_inner"].reversed(), S["lamp_bottom"].reversed(),
          S["bump_fender"].P, S["arch_f_front"].P, S["bump_bottom"].P]
    # Левая половина идёт от центра верха к центру низа; правая — зеркально обратно
    br = [mirror_curve(c)[::-1] for c in reversed(bl)]
    bumper = loop(bl + br)
    grille = [("front", x, z) for x, z in GRILLE]
    intake_l = [("front", x, z) for x, z in INTAKE_L]
    intake_r = [("front", -x, z) for _, x, z in reversed(intake_l)]
    lower = [("front", x, z) for x, z in LOWER]

    def hole(pts):
        return Seam(surf, pts, "rf", n=500, closed=True).P

    V, F = domain_panel(surf, VIEWS["rf"], bumper, holes=[hole(grille), hole(intake_l), hole(intake_r), hole(lower)],
                        h=0.012, gap=GAP_TIGHT, hole_depth=0.06)
    out.append(("Bumper_F", "paint", V, F))
    build_rear(surf, S, out)
    build_parts(surf, S, out)
    return out


def build_rear(surf: Surface, S: dict, out: list) -> None:
    """Кабина (стёкла, крыша, боковины со стойками), крышка багажника, фонари, задний бампер, диффузор."""
    YR = WHEEL_Y
    door_ft, door_rt = S["door_front"].P[-1], S["door_top"].P[-1]
    # --- Углы ---------------------------------------------------------------------------------
    ws_base_c, ws_base_l = ("top", 0.0, -0.835), ("top", 0.705, -0.770)
    ws_top_c, ws_top_l = ("top", 0.0, -0.165), ("top", 0.540, -0.150)
    bl_top_c, bl_top_l = ("top", 0.0, 1.345), ("top", 0.470, 1.330)
    bl_bot_c, bl_bot_l = ("top", 0.0, 1.905), ("top", 0.500, 1.860)
    dlo_tip = ("side", 1.399, 1.108)
    bpill_top = ("side", 0.605, 1.308)
    tl_in_top, tl_in_bot = ("rear", 0.640, 0.952), ("rear", 0.600, 0.862)
    tl_tip = ("side", 1.905, 0.915)
    bump_r = ("side", 2.250, 0.798)
    PHI_RB = 40.0
    arch_bump_r = ("side", YR + ARCH_LIP_R * math.cos(math.radians(PHI_RB)),
                   WHEEL_Z + ARCH_LIP_R * math.sin(math.radians(PHI_RB)))
    phi_rd = phi_at_z(0.330, False)
    arch_diff_r = ("side", YR + ARCH_LIP_R * math.cos(math.radians(phi_rd)), 0.330)
    phi_rbot = phi_at_z(0.225, False)
    arch_bot_r = ("side", YR + ARCH_LIP_R * math.cos(math.radians(phi_rbot)), 0.225)
    lid_bot_c = ("rear", 0.0, 0.750)
    diff_c = ("rear", 0.0, 0.468)
    phi_sr = phi_at_z(0.360, True)
    arch_sill_r = S["sill_r"].P[-1]

    # --- Швы кабины ---------------------------------------------------------------------------
    S["ws_base"] = Seam(surf, [ws_base_c, ("top", 0.40, -0.815), ws_base_l], "top")
    S["cowl_side"] = Seam(surf, [("p", *S["cowl"].P[-1]), ("top", 0.77, -0.86), ws_base_l], "top")
    S["ws_side"] = Seam(surf, [ws_base_l, ("top", 0.665, -0.58), ("top", 0.605, -0.36), ws_top_l], "top")
    S["ws_top"] = Seam(surf, [ws_top_l, ("top", 0.30, -0.160), ws_top_c], "top")
    S["roof_side"] = Seam(surf, [ws_top_l, ("top", 0.567, 0.175), ("top", 0.580, 0.80), ("top", 0.576, 1.20),
                                 ("top", 0.535, 1.305), bl_top_l], "top")
    S["bl_top"] = Seam(surf, [bl_top_l, ("top", 0.25, 1.338), bl_top_c], "top")
    S["bl_side"] = Seam(surf, [bl_top_l, ("top", 0.515, 1.45), ("top", 0.528, 1.62), ("top", 0.524, 1.76),
                               bl_bot_l], "rx_rear")
    S["bl_bot"] = Seam(surf, [bl_bot_l, ("top", 0.30, 1.89), bl_bot_c], "top")
    S["q_belt"] = Seam(surf, [("p", *door_rt), ("side", 0.87, 1.030), ("side", 1.252, 1.062), dlo_tip], "side")
    S["dlo_up_r"] = Seam(surf, [dlo_tip, ("side", 1.303, 1.168), ("side", 0.87, 1.292), bpill_top], "side")
    S["dlo_up_f"] = Seam(surf, [bpill_top, ("side", 0.236, 1.329), ("side", -0.193, 1.240), ("side", -0.55, 1.065),
                                ("p", *door_ft)], "side")
    S["bpillar"] = Seam(surf, [("p", *door_rt), ("side", 0.598, 1.16), bpill_top], "side")
    # --- Швы кормы ----------------------------------------------------------------------------
    S["lid_upper"] = Seam(surf, [bl_bot_l, ("top", 0.600, 1.93), ("top", 0.655, 2.03), ("top", 0.652, 2.20),
                                 ("rear", 0.650, 1.010), tl_in_top], "rx_rear")
    S["lid_lamp"] = Seam(surf, [tl_in_top, ("rear", 0.625, 0.905), tl_in_bot], "rear")
    S["lid_lower"] = Seam(surf, [tl_in_bot, ("rear", 0.530, 0.800), ("rear", 0.420, 0.765), ("rear", 0.20, 0.752),
                                 lid_bot_c], "rear")
    S["tl_top"] = Seam(surf, [tl_tip, ("side", 1.960, 0.945), ("side", 2.200, 0.955), ("side", 2.340, 0.962),
                              rr_pt(43.9, 0.955), ("rear", 0.720, 0.955), tl_in_top], "rr")
    S["tl_bot_rear"] = Seam(surf, [tl_in_bot, ("rear", 0.700, 0.808), ("rear", 0.790, 0.808),
                                   rr_pt(48.2, 0.82), bump_r], "rr")
    S["tl_bot_side"] = Seam(surf, [bump_r, ("side", 2.100, 0.822), ("side", 1.960, 0.870), tl_tip], "side")
    S["bump_quarter"] = Seam(surf, [bump_r, ("side", 2.150, 0.722), ("side", 1.900, 0.668), ("side", 1.795, 0.640),
                                    arch_bump_r], "side")
    S["arch_r_top"] = Seam(surf, [arch_bump_r] + arch_pts(YR, PHI_RB, phi_sr, 13)[1:-1] + [("p", *arch_sill_r)], "side")
    S["arch_r_low"] = Seam(surf, [arch_bump_r] + arch_pts(YR, PHI_RB, phi_rd, 7)[1:-1] + [arch_diff_r], "side")
    S["arch_r_diff"] = Seam(surf, [arch_diff_r] + arch_pts(YR, phi_rd, phi_rbot, 5)[1:-1] + [arch_bot_r], "side")
    diff_side_end = ("side", 2.300, 0.420)
    S["diff_top_s"] = Seam(surf, [arch_diff_r, ("side", 2.10, 0.372), diff_side_end], "side")
    S["diff_top_r"] = Seam(surf, [diff_side_end, rr_pt(44.7, 0.450), ("rear", 0.700, 0.462), ("rear", 0.300, 0.468),
                                  diff_c], "rr")
    S["under"] = Seam(surf, [arch_bot_r, ("bottom", 0.86, 2.00), ("bottom", 0.80, 2.28), ("bottom", 0.40, 2.30),
                             ("bottom", 0.0, 2.30)], "bottom")

    # --- Стёкла -----------------------------------------------------------------------------
    ws = sym_loop([S["ws_base"].P, S["ws_side"].P, S["ws_top"].P])
    V, F = domain_panel(surf, VIEWS["ws"], ws, h=0.016, gap=0.006, flange=0.02, fit_deg=4, fit_blend=0.05)
    out.append(("Glass_Windshield", "glass", V, F))
    bl = sym_loop([S["bl_bot"].reversed(), S["bl_side"].reversed(), S["bl_top"].P])
    V, F = domain_panel(surf, VIEWS["bl"], bl, h=0.016, gap=0.006, flange=0.02, fit_deg=4, fit_blend=0.05)
    out.append(("Glass_Rear", "glass", V, F))
    door_g = loop([S["door_top"].P, S["bpillar"].P, S["dlo_up_f"].P])
    V, F = domain_panel(surf, VIEWS["side"], door_g, h=0.014, gap=0.005, flange=0.02, fit_deg=3, fit_blend=0.03)
    out.append(("Glass_Door_L", "glass", V, F))
    out.append(("Glass_Door_R", "glass", *mirror_mesh(V, F)))
    q_g = loop([S["q_belt"].P, S["dlo_up_r"].P, S["bpillar"].reversed()])
    V, F = domain_panel(surf, VIEWS["side"], q_g, h=0.012, gap=0.005, flange=0.02, fit_deg=3, fit_blend=0.03)
    out.append(("Glass_Quarter_L", "glass", V, F))
    out.append(("Glass_Quarter_R", "glass", *mirror_mesh(V, F)))
    # --- Крыша и подлобовой короб ------------------------------------------------------------
    roof = sym_loop([S["ws_top"].reversed(), S["roof_side"].P, S["bl_top"].P])
    V, F = domain_panel(surf, VIEWS["top"], roof, h=0.016, gap=0.003)
    out.append(("Roof", "paint", V, F))
    cowl = sym_loop([S["cowl"].P, S["cowl_side"].P, S["ws_base"].reversed()])
    V, F = domain_panel(surf, VIEWS["top"], cowl, h=0.010, gap=GAP)
    out.append(("Cowl", "trim_black", V, F))
    # --- Боковина: стойки, задние крылья ----------------------------------------------------
    side = loop([S["lid_upper"].P, S["tl_top"].reversed(), S["tl_bot_side"].reversed(), S["bump_quarter"].P,
                 S["arch_r_top"].P, S["sill_r"].reversed(), S["door_rear"].P, S["q_belt"].P, S["dlo_up_r"].P,
                 S["dlo_up_f"].P, S["fender_apillar"].P, S["cowl_side"].P, S["ws_side"].P, S["roof_side"].P,
                 S["bl_side"].P])
    V, F = domain_panel(surf, VIEWS["rs"], side, h=0.013, gap=GAP)
    out.append(("Bodyside_L", "paint", V, F))
    out.append(("Bodyside_R", "paint", *mirror_mesh(V, F)))
    # --- Крышка багажника со световой полосой ------------------------------------------------
    lid = sym_loop([S["bl_bot"].reversed(), S["lid_upper"].P, S["lid_lamp"].P, S["lid_lower"].P])
    bar = [("rear", x, z) for x, z in [(0.0, 0.952), (0.40, 0.950), (0.585, 0.946), (0.598, 0.928), (0.585, 0.908),
                                       (0.40, 0.906), (0.0, 0.905)]]
    bar = bar + [("rear", -x, z) for _, x, z in reversed(bar[1:-1])]
    bar_loop = Seam(surf, bar, "rear", n=400, closed=True).P
    V, F = domain_panel(surf, VIEWS["rx_rear"], lid, holes=[bar_loop], h=0.014, gap=GAP, hole_depth=0.02)
    out.append(("Trunk_Lid", "paint", V, F))
    V, F = domain_panel(surf, VIEWS["rear"], bar_loop, h=0.006, gap=0.0025, flange=0.02)
    out.append(("Lightbar", "lamp_red", V, F))
    # --- Фонари -----------------------------------------------------------------------------
    tl = loop([S["lid_lamp"].P, S["tl_bot_rear"].P, S["tl_bot_side"].P, S["tl_top"].P])
    V, F = domain_panel(surf, VIEWS["rr"], tl, h=0.008, gap=GAP_TIGHT, flange=0.03)
    out.append(("Taillamp_L", "lamp_red", V, F))
    out.append(("Taillamp_R", "lamp_red", *mirror_mesh(V, F)))
    # --- Задний бампер с нишей номера -------------------------------------------------------
    bump = sym_loop([S["lid_lower"].reversed(), S["tl_bot_rear"].P, S["bump_quarter"].P, S["arch_r_low"].P,
                     S["diff_top_s"].P, S["diff_top_r"].P])
    # Ниша номера 544×134 под номер 520×112: номер стоит внутри, за кромками изогнутого бампера
    plate = [("rear", x, z) for x, z in [(0.0, 0.623), (0.255, 0.622), (0.272, 0.606), (0.272, 0.504),
                                         (0.255, 0.488), (0.0, 0.487)]]
    plate = plate + [("rear", -x, z) for _, x, z in reversed(plate[1:-1])]
    plate_loop = Seam(surf, plate, "rear", n=300, closed=True).P
    V, F = domain_panel(surf, VIEWS["rr"], bump, holes=[plate_loop], h=0.013, gap=GAP_TIGHT, hole_depth=0.032)
    out.append(("Bumper_R", "paint", V, F))
    import parts as _pt
    # дно ниши шире проёма на 12 мм — заходит под стенку, без щели по кромке
    import domain as _dm
    floor_loop = _dm.loop_on_surface(surf, VIEWS["rr"], plate_loop, 0.012, 0.012, True)
    out.append(("Plate_Recess_Floor", "paint", *_pt.backing(surf, VIEWS["rr"], floor_loop, 0.036)))
    # --- Диффузор с выхлопом ----------------------------------------------------------------
    diff = sym_loop([S["diff_top_r"].reversed(), S["diff_top_s"].reversed(), S["arch_r_diff"].P, S["under"].P])
    ex_l = [("rear", x, z) for x, z in EXHAUST_L]
    ex_r = [("rear", -x, z) for _, x, z in reversed(ex_l)]
    V, F = domain_panel(surf, VIEWS["rx_rear"], diff, holes=[Seam(surf, ex_l, "rear", n=200, closed=True).P,
                                                             Seam(surf, ex_r, "rear", n=200, closed=True).P],
                        h=0.010, gap=GAP, hole_depth=0.08)
    out.append(("Diffuser", "trim_black", V, F))


def build_parts(surf: Surface, S: dict, out: list) -> None:
    """Детали поверх панелей: решётка со знаком, рёбра проёмов, губа, накладки, ручки, выхлоп."""
    import parts as pt

    front = VIEWS["front"]
    # Решётка: вертикальные рёбра, задник, знак «Клин» по центру
    out.append(("Grille_Slats", "trim_gloss_black", *pt.grille_slats(surf, GRILLE, n_slats=13)))
    g_loop = Seam(surf, [("front", x, z) for x, z in GRILLE], "rf", n=400, closed=True).P
    out.append(("Grille_Back", "mesh_black", *pt.backing(surf, VIEWS["rf"], g_loop, 0.075)))
    c = front.lift(surf, np.array([[0.0, 0.648]]))[0]
    out.append(("Badge_Front", "chrome", *pt.badge(c + np.array([0, -0.006, 0]), (0, -1, 0), (0, 0, 1), 0.125)))
    # Боковые воздухозаборники: три карбоновые лопатки и соты за ними
    i_loop = Seam(surf, [("front", x, z) for x, z in INTAKE_L], "rf", n=300, closed=True).P
    fins = pt.fins_in_loop(surf, VIEWS["rf"], i_loop, [0.545, 0.455, 0.365], t=0.010, depth=0.065)
    out.append(("Intake_Fins_L", "carbon", *fins))
    out.append(("Intake_Fins_R", "carbon", *mirror_mesh(*fins)))
    ib = pt.backing(surf, VIEWS["rf"], i_loop, 0.07)
    out.append(("Intake_Back_L", "mesh_black", *ib))
    out.append(("Intake_Back_R", "mesh_black", *mirror_mesh(*ib)))
    # Нижний воздухозаборник: две лопатки и соты
    l_loop = Seam(surf, [("front", x, z) for x, z in LOWER], "rf", n=400, closed=True).P
    out.append(("Lower_Fins", "trim_gloss_black", *pt.fins_in_loop(surf, VIEWS["rf"], l_loop, [0.385, 0.318],
                                                                   t=0.008, depth=0.05)))
    out.append(("Lower_Back", "mesh_black", *pt.backing(surf, VIEWS["rf"], l_loop, 0.06)))
    # Губа под бампером (карбон): плита вдоль нижней кромки, выступает вперёд
    edge = np.vstack([mirror_curve(S["bump_bottom"].P)[::-1], S["bump_bottom"].P[::-1][1:]])
    edge = resample(edge, 260)
    nrm = surf.normal(edge)
    out_h = nrm.copy()
    out_h[:, 2] = 0
    out_h /= np.maximum(np.linalg.norm(out_h, axis=1, keepdims=True), 1e-9)
    path = edge + out_h * 0.012 - np.array([0, 0, 0.010])
    sec = pt.rounded_rect(0.075, 0.011, 0.004, 3)
    out.append(("Splitter", "carbon", *pt.loft(path, out_h, np.broadcast_to(np.array([0, 0, 1.0]), path.shape), sec)))
    # Хромовая накладка порога. Левая треснула: кусок у задней кромки двери отколот (он на стоянке ТЦ)
    side = VIEWS["side"]
    yy = np.linspace(-0.97, 0.97, 200)
    line = side.lift(surf, np.c_[yy, np.full(len(yy), 0.262)])
    gap_y0, gap_y1 = 0.255, 0.335
    keep_a, keep_b = line[yy < gap_y0], line[yy > gap_y1]
    frag = line[(yy >= gap_y0 + 0.004) & (yy <= gap_y1 - 0.004)]
    left = pt.merge([pt.strip_on_surface(surf, keep_a, 0.018, 0.004, 0.001),
                     pt.strip_on_surface(surf, keep_b, 0.018, 0.004, 0.001)])
    out.append(("Sill_Trim_L_cracked", "chrome", *left))
    out.append(("Sill_Trim_R", "chrome", *mirror_mesh(*pt.strip_on_surface(surf, line, 0.018, 0.004, 0.001))))
    out.append(("Sill_Trim_Fragment", "chrome", *pt.strip_on_surface(surf, frag, 0.018, 0.004, 0.001)))
    # Молдинг по верху двери и задней боковины: закрывает стык с ровным стеклом (как уплотнитель на CLE)
    belt = np.vstack([S["door_top"].P, S["q_belt"].P[1:]])
    bm = pt.strip_on_surface(surf, belt, 0.014, 0.006, 0.0, r=0.0026)
    out.append(("Belt_Molding_L", "chrome", *bm))
    out.append(("Belt_Molding_R", "chrome", *mirror_mesh(*bm)))
    # Ручки дверей — заподлицо, тонкая планка у задней кромки двери
    hy = np.linspace(0.30, 0.48, 40)
    hline = side.lift(surf, np.c_[hy, np.full(len(hy), 0.862)])
    h = pt.strip_on_surface(surf, hline, 0.024, 0.006, 0.0005, r=0.0028)
    out.append(("Door_Handle_L", "chrome", *h))
    out.append(("Door_Handle_R", "chrome", *mirror_mesh(*h)))
    # Зеркала
    housing, mglass, arm = pt.mirror_parts(surf)
    for nm, mat, mesh in (("Mirror_Housing", "paint", housing), ("Mirror_Glass", "mirror", mglass),
                          ("Mirror_Arm", "paint", arm)):
        out.append((nm + "_L", mat, *mesh))
        out.append((nm + "_R", mat, *mirror_mesh(*mesh)))
    # Подкрылки и днище
    for nm, yc in (("F", -WHEEL_Y), ("R", WHEEL_Y)):
        liner = pt.wheel_liner(yc, WHEEL_Z)
        out.append((f"Liner_{nm}L", "liner", *liner))
        out.append((f"Liner_{nm}R", "liner", *mirror_mesh(*liner)))
    out.append(("Under_Tray", "liner", *pt.under_tray(surf.field)))
    # Дворники
    out.append(("Wiper_L", "trim_black", *pt.wiper(surf, (-0.02, -0.795), (0.60, -0.765), (0.30, -0.865))))
    out.append(("Wiper_R", "trim_black", *pt.wiper(surf, (-0.60, -0.765), (-0.08, -0.795), (-0.38, -0.865))))
    # Начинка фар
    lamp_loop = loop([S["hood_lamp"].P, S["lamp_inner"].reversed(), S["lamp_bottom"].reversed(), S["lamp_top_out"].reversed()])
    top_edge = np.vstack([S["hood_lamp"].reversed(), S["lamp_top_out"].P[1:]])
    back, drl, lenses = pt.headlamp_inner(surf, lamp_loop, VIEWS["rf"], top_edge)
    for nm, mat, mesh in (("Headlamp_Reflector", "chrome_dark", back), ("Headlamp_DRL", "lamp_drl", drl),
                          ("Headlamp_Lenses", "lens", lenses)):
        out.append((nm + "_L", mat, *mesh))
        out.append((nm + "_R", mat, *mirror_mesh(*mesh)))
    # Знак на крышке багажника
    c = VIEWS["rear"].lift(surf, np.array([[0.0, 0.985]]))[0]
    out.append(("Badge_Rear", "chrome", *pt.badge(c + np.array([0, 0.004, 0]), (0, 1, 0), (0, 0, 1), 0.095)))
    # Выхлоп: по две овальные насадки в каждом проёме
    tips = []
    for xc in (0.522, 0.616):
        cpt = VIEWS["rear"].lift(surf, np.array([[xc, 0.413]]))[0]
        yy0, yy1 = cpt[1] - 0.12, cpt[1] - 0.012
        ys = np.linspace(yy0, yy1, 12)
        P = np.c_[np.full(12, xc), ys, np.full(12, 0.413)]
        U = np.broadcast_to(np.array([1.0, 0, 0]), P.shape)
        Vv = np.broadcast_to(np.array([0, 0, 1.0]), P.shape)
        outer = pt.rounded_rect(0.082, 0.040, 0.018, 5)
        inner = outer * np.array([0.86, 0.78])
        tips.append(pt.loft(P, U, Vv, outer, cap=False))
        tips.append(pt.loft(P[::-1], U, Vv, inner, cap=False))
        # кольцо-торец между наружной и внутренней стенкой
        k = len(outer)
        Vr = np.vstack([P[-1] + outer[:, :1] * U[0] + outer[:, 1:2] * Vv[0], P[-1] + inner[:, :1] * U[0] + inner[:, 1:2] * Vv[0]])
        tips.append((Vr, [(j, (j + 1) % k, k + (j + 1) % k, k + j) for j in range(k)]))
    ex = pt.merge(tips)
    out.append(("Exhaust_Tips_L", "chrome_dark", *ex))
    out.append(("Exhaust_Tips_R", "chrome_dark", *mirror_mesh(*ex)))
