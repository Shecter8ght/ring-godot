"""Колпак крыши кабины с маячками и передний бампер — генератором кузовов, как кабина (cab_body.py).

Колпак — стеклопластиковая оболочка: выпуклый, с покатым лбом и скруглёнными кромками, маячки — в выступах на передних
углах (поле колпака плавно объединено с полями выступов), под синими линзами — отражатель и светодиодные модули.
Бампер — лепной пластиковый: лицо слегка выпуклое, концы заходят назад на крылья, сверху скругление, снизу чёрная губа;
ниши фар, поворотников, противотуманок, номера и воздухозаборника — проёмами со стенками.
"""
from __future__ import annotations

import math

import numpy as np

import cab_body as cb
import spec as S
from cab_body import View, ViewR, domain_panel, lift_poly, mirror_mesh, pt, sym_loop, vlib
from vfield import BoxField, smin

F, B = S.CAB_FRONT, S.CAB_BACK
HW = S.CAB_W / 2
GAP = 0.005


class PodField(BoxField):
    """Поле коробки с плавно приросшими скруглёнными выступами (маячки на колпаке)."""

    def __init__(self, spec: dict, pods: list, k: float) -> None:
        super().__init__(spec)
        self.pods, self.k = pods, k

    def eval(self, X, Y, Z, arches: bool = True):
        d = super().eval(X, Y, Z, arches=False)
        for cx, cy, cz, hx, hy, hz, r in self.pods:
            qx = np.abs(X - cx) - (hx - r)
            qy = np.abs(Y - cy) - (hy - r)
            qz = np.abs(Z - cz) - (hz - r)
            box = (np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
                   + np.minimum(np.maximum(np.maximum(qx, qy), qz), 0) - r)
            d = smin(d, box, self.k)
        return d


POD = dict(x=0.86, y=F + 0.60, hx=0.24, hy=0.16, top=S.CAP_TOP + 0.085)


def _panel(out, surf, view, name, paint, outer, holes=(), h=0.02, **kw):
    err = None
    for k in range(5):
        try:
            V, Fc = domain_panel(surf, view, outer, holes=holes, h=h * (1 + 0.07 * k), **kw)
            out.append((name, paint, V, Fc))
            return V, Fc
        except Exception as e:
            err = e
    raise RuntimeError(f"панель {name} не собрана: {err}")


def cap() -> list:
    out = []
    spec = dict(
        top=[(F - 0.5, S.CAP_TOP), (B + 0.5, S.CAP_TOP)],
        bottom=[(F - 0.5, S.CAB_ROOF - 0.06), (B + 0.5, S.CAB_ROOF - 0.06)],
        front=[(2.80, F + 0.15), (2.93, F + 0.20), (S.CAP_TOP, F + 0.34), (3.40, F + 0.52)],
        rear=[(2.80, B - 0.03), (3.40, B - 0.03)],
        plan=[(F - 0.5, HW - 0.05), (B + 0.5, HW - 0.05)],
        section=[(2.80, 1.0), (2.95, 1.0), (S.CAP_TOP, 0.97), (3.40, 0.95)],
        nose_sweep=[(0.0, 0.0), (0.6, 0.01), (0.9, 0.05), (1.0, 0.09), (1.2, 0.2)],
        r_corner=0.12, r_corner_rear=0.04, r_roof=0.07, r_bot=0.005,
        wheel_y=[], wheel_z=0.5, arch_r=0.5, well_x=3.0, curve_kind="pchip")
    pods = [(sx * POD["x"], POD["y"], S.CAP_TOP, POD["hx"], POD["hy"], POD["top"] - S.CAP_TOP, 0.06) for sx in (1, -1)]
    surf = cb.Surface(PodField(spec, pods, 0.07))
    vy = View("cyl", c=(0.0, 0.0, 2.55), a=(0, 1, 0), e0=(0, 0, 1))
    top = ViewR("top", reach=5.0)
    # подошва колпака — кольцо на высоте крыши: горизонтальными лучами к оси колпака
    yc = (F + 0.20 + B) / 2
    ring_view = View("cyl", c=(0.0, yc, 0.0), a=(0, 0, 1), e0=(0, -1, 0))
    th = np.linspace(-math.pi, math.pi, 480, endpoint=False)
    ring = ring_view.lift(surf, np.c_[th, np.full(len(th), S.CAB_ROOF - 0.012)])
    holes, lens_loops = [], []
    for sx in (1, -1):
        uv = vlib.fillet_poly([(sx * POD["x"] - 0.20, POD["y"] - 0.125), (sx * POD["x"] + 0.20, POD["y"] - 0.125),
                               (sx * POD["x"] + 0.20, POD["y"] + 0.125), (sx * POD["x"] - 0.20, POD["y"] + 0.125)],
                              0.05, closed=True, n_arc=8)
        L = lift_poly(surf, top, np.vstack([uv, uv[:1]]), 0.003)[:-1]
        holes.append(L)
        lens_loops.append(L)
    _panel(out, surf, vy, "Cab_Roof_Cap", "white", ring, holes=holes, h=0.022, gap=0.0, roll_r=0.004, flange=0.02,
           hole_depth=0.05)
    for k, L in enumerate(lens_loops):
        _panel(out, surf, top, f"Cab_Beacon_Lens_{'L' if k == 0 else 'R'}", "beacon", L, h=0.025, gap=0.004, flange=0.02,
               fit_deg=2, fit_blend=0.02)
    return out


def bumper() -> list:
    out = []
    b = S.BUMPER
    y0, y1, z0, z1 = b["y0"], b["y1"], b["z0"], b["z1"]
    hwb = b["w"] / 2
    spec = dict(
        top=[(y0 - 0.4, z1), (y1 + 0.4, z1)], bottom=[(y0 - 0.4, z0), (y1 + 0.4, z0)],
        front=[(0.30, y0 + 0.035), (0.46, y0 + 0.025), (0.62, y0 + 0.010), (0.80, y0), (0.94, y0 + 0.006), (1.10, y0 + 0.02)],
        rear=[(0.30, y1), (1.10, y1)], plan=[(y0 - 0.4, hwb), (y1 + 0.4, hwb)],
        nose_sweep=[(0.0, 0.0), (0.5, 0.004), (0.8, 0.02), (0.95, 0.06), (1.0, 0.09), (1.2, 0.2)],
        r_corner=0.14, r_corner_rear=0.01, r_roof=0.045, r_bot=0.035,
        wheel_y=[], wheel_z=0.5, arch_r=0.5, well_x=3.0, curve_kind="pchip")
    surf = cb.Surface(BoxField(spec))
    rf = View("cyl", c=(0.0, y0 + 0.60, 0.0), a=(0, 0, 1), e0=(0, -1, 0))
    front = ViewR("front", reach=5.0)
    side = ViewR("side", reach=5.0)
    top = ViewR("top", reach=5.0)
    y_end = y1 - 0.02
    u_end = math.atan2(hwb, -(y_end - (y0 + 0.60)))
    z_seam, z_top, z_low = 0.505, 0.962, z0 + 0.012

    def rf_line(u0, u1, z):
        return lift_poly(surf, rf, np.array([(u0, z), (u1, z)]), 0.004)
    bottom = rf_line(0.0, u_end, z_seam)
    end = cb.line_on(surf, side, (y_end, z_seam), (y_end, z_top))
    end[0] = bottom[-1]
    top_seam = rf_line(u_end, 0.0, z_top)
    top_seam[0] = end[-1]
    holes_uv = []
    for sx in (1, -1):
        holes_uv += [[(sx * 0.70 - 0.19, 0.73), (sx * 0.70 + 0.19, 0.73), (sx * 0.70 + 0.19, 0.88), (sx * 0.70 - 0.19, 0.88), 0.03],
                     [(sx * 0.72 - 0.065, 0.55), (sx * 0.72 + 0.065, 0.55), (sx * 0.72 + 0.065, 0.64), (sx * 0.72 - 0.065, 0.64), 0.012],
                     [(sx * 0.99 - 0.07, 0.75), (sx * 0.99 + 0.07, 0.75), (sx * 0.99 + 0.07, 0.86), (sx * 0.99 - 0.07, 0.86), 0.02]]
    holes_uv += [[(-0.28, 0.52), (0.28, 0.52), (0.28, 0.625), (-0.28, 0.625), 0.01],
                 [(-0.45, 0.655), (0.45, 0.655), (0.45, 0.715), (-0.45, 0.715), 0.02]]
    holes = []
    for h in holes_uv:
        uv = vlib.fillet_poly(h[:4], h[4], closed=True, n_arc=6)
        holes.append(lift_poly(surf, front, np.vstack([uv, uv[:1]]), 0.003)[:-1])
    face = sym_loop([bottom, end, top_seam])
    _panel(out, surf, rf, "Cab_Bumper", "white", face, holes=holes, h=0.02, gap=GAP, hole_depth=0.05)
    # нижняя чёрная губа
    low = rf_line(0.0, u_end, z_low)
    low_end = cb.line_on(surf, side, (y_end, z_low), (y_end, z_seam))
    low_end[0] = low[-1]
    seam_back = bottom[::-1].copy()
    seam_back[0] = low_end[-1]
    lip = sym_loop([low, low_end, seam_back])
    _panel(out, surf, rf, "Cab_Bumper_Lip", "black", lip, h=0.02, gap=GAP)
    # верх бампера: спереди — верхний шов, сзади — поперёк у кабины
    seamL = top_seam[::-1]                                          # центр → левый конец
    left_end = seamL[-1]
    rear_line = lift_poly(surf, top, np.array([(-(hwb - 0.03), y_end + 0.005), (hwb - 0.03, y_end + 0.005)]), 0.004)
    seamR = seamL * np.array([-1.0, 1.0, 1.0])
    loop_pts = np.vstack([seamR[::-1][:-1], seamL[:-1], np.array([left_end]), rear_line[::-1]])
    _panel(out, surf, top, "Cab_Bumper_Top", "white", loop_pts, h=0.025, gap=GAP)
    return out


def build() -> list:
    return cap() + bumper()
