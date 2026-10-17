"""Купе Ильи, этап силуэта: объём кузова полем расстояний и сетка по нулевому уровню.

Запуск (системный Python с numpy, scipy, scikit-image, trimesh, Pillow):
    python -X utf8 tools/coupe_ilya/body_field.py [выход.ply] [шаг_м]

Кузов = гладкое объединение нижнего корпуса и кабины минус колёсные арки.
Нижний корпус — пересечение бокового профиля (низ, капот/пояс/багажник, перёд и зад)
с планом (ширина по длине, расширенная под CLE 53) и сечением по высоте g(z).
Кабина — профиль крыши, стёкол и стоек сбоку с завалом боковин внутрь.
Это черновой объём для сверки силуэта нейтральным материалом, а не финальная сетка.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.interpolate import PchipInterpolator
from skimage import measure

sys.path.insert(0, str(Path(__file__).parent))
import drawing  # noqa: E402

OUT_DEFAULT = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\checks\body_field_v01.ply")

# --- Принятые размеры и решения (asset-state.md) ---------------------------------------------
HALF_FRONT_FLARE = 0.957     # полуширина по передним крыльям CLE 53 (+29 мм к обычному CLE)
HALF_REAR_FLARE = 0.9675     # по задним крыльям (габарит 1935 мм)
HALF_DOOR = 0.918            # по дверям
ARCH_R = 0.388               # радиус выреза арки: шина 0,343 + зазор
WELL_X = 0.50                # глубина колёсной ниши от оси машины
WS_BASE = (-0.855, 1.021)    # низ лобового стекла (Y, Z) — по чертежу
BL_BASE = (1.968, 1.103)     # низ заднего стекла
# Пояс (низ боковых окон, чуть ниже окантовки): Y → Z
BELT = [(-0.855, 1.015), (-0.37, 0.990), (0.87, 1.030), (1.395, 1.110), (1.968, 1.103)]
# Ширина кабины у пояса по длине (план: стойки сходятся к лобовому и сильнее к заднему стеклу)
GH_HALF = [(-0.90, 0.68), (-0.60, 0.735), (-0.20, 0.755), (0.80, 0.755), (1.40, 0.725), (2.00, 0.62)]
GH_TUMBLE = 0.50             # завал боковых стёкол: на метр высоты внутрь
# Сечение нижнего корпуса: доля полуширины по высоте
G_SECTION = [(0.00, 0.70), (0.10, 0.80), (0.18, 0.90), (0.25, 0.955), (0.35, 0.985), (0.55, 0.998),
             (0.70, 1.000), (0.80, 0.992), (0.90, 0.968), (0.98, 0.935), (1.06, 0.895), (1.20, 0.83)]
CROWN_HOOD = 0.045           # выпуклость капота и багажника к середине
CROWN_ROOF = 0.040           # выпуклость крыши
R_SHOULDER = 0.055           # скругление плеча (верх — борт)
R_ROOF = 0.075               # скругление края крыши
R_UNION = 0.030              # переход кабины в корпус
R_ARCH = 0.012               # кромка арки

GRID_RES = 0.002             # шаг растров двумерных профилей
SD_BLUR = 1.5                # размытие растровых расстояний (в пикселях) — убирает ступеньки

# Свои кривые концов и низа (Y, Z), м. Перёд: нижняя часть бампера уходит назад, верх — к капоту.
NOSE_TIP = (-2.337, 0.585)
NOSE_BOT = [(-2.333, 0.47), (-2.325, 0.40), (-2.300, 0.30), (-2.255, 0.205), (-2.20, 0.195)]
NOSE_TOP = [(-2.334, 0.66), (-2.318, 0.74), (-2.280, 0.795), (-2.220, 0.828)]
TAIL_TIP = (2.517, 0.55)
TAIL_BOT = [(2.20, 0.29), (2.43, 0.34), (2.50, 0.37), (2.514, 0.45)]
TAIL_TOP = [(2.30, 1.042), (2.335, 1.034), (2.40, 0.905), (2.46, 0.80), (2.50, 0.70), (2.514, 0.62)]
BOTTOM = [(-1.90, 0.19), (-1.00, 0.185), (1.00, 0.19), (1.85, 0.22)]
# Насколько перёд и корма уходят назад/вперёд к углам (по плану): полуширина X → сдвиг, м
NOSE_SWEEP = [(0.0, 0.0), (0.30, 0.010), (0.50, 0.045), (0.65, 0.105), (0.75, 0.175), (0.85, 0.270), (0.95, 0.40)]
TAIL_SWEEP = [(0.0, 0.0), (0.37, 0.010), (0.55, 0.060), (0.68, 0.130), (0.77, 0.225), (0.90, 0.360)]
R_NOSE = 0.035               # скругление носка и кромок бампера сбоку
# Расширенные крылья CLE 53: выпуклость борта вокруг колеса (Y центра, амплитуда, м)
FLARES = [(-1.4355, HALF_FRONT_FLARE - HALF_DOOR), (1.4355, HALF_REAR_FLARE - HALF_DOOR)]
FLARE_R0, FLARE_R1 = 0.40, 0.68   # от кромки арки до слияния с бортом
# Линия плеча — острое ребро вдоль борта (Y, Z): спереди от фары, через дверь, над задним колесом
CREASE = [(-2.10, 0.785), (-1.745, 0.817), (-0.96, 0.860), (-0.40, 0.868), (0.35, 0.900), (0.84, 0.925),
          (1.50, 0.935), (2.00, 0.925)]
CREASE_AMP, CREASE_W = 0.006, 0.045
# Нижняя линия двери — мягкая впадина
DOOR_LINE = [(-1.00, 0.410), (0.12, 0.449), (0.90, 0.480)]
DOOR_AMP, DOOR_W = -0.004, 0.06


def smin(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    h = np.clip(k - np.abs(a - b), 0.0, None) / k
    return np.minimum(a, b) - h * h * k * 0.25


def smax(a: np.ndarray, b: np.ndarray, k: float) -> np.ndarray:
    return -smin(-a, -b, k)


class Raster2D:
    """Знаковое расстояние до двумерной фигуры на растре (минус — внутри)."""

    def __init__(self, mask: np.ndarray, u0: float, v0: float, res: float) -> None:
        inside = ndimage.distance_transform_edt(mask) * res
        outside = ndimage.distance_transform_edt(~mask) * res
        self.sd = ndimage.gaussian_filter((outside - inside).astype(np.float32), SD_BLUR)
        self.u0, self.v0, self.res = u0, v0, res

    def __call__(self, u: np.ndarray, v: np.ndarray) -> np.ndarray:
        iu = (u - self.u0) / self.res
        iv = (v - self.v0) / self.res
        return ndimage.map_coordinates(self.sd, [iu.ravel(), iv.ravel()], order=1, mode="nearest").reshape(u.shape)


def poly_mask(poly_uv: np.ndarray, u0: float, v0: float, nu: int, nv: int, res: float) -> np.ndarray:
    """Заливка многоугольника в растр [u, v]."""
    img = Image.new("1", (nu, nv), 0)
    pts = [((p[0] - u0) / res, (p[1] - v0) / res) for p in poly_uv]
    ImageDraw.Draw(img).polygon(pts, fill=1)
    return np.array(img, dtype=bool).T  # PIL: [v, u] → [u, v]


def bump(y: np.ndarray, c: float, half: float) -> np.ndarray:
    """Гладкий горб 0..1..0 на отрезке c±half."""
    t = np.clip(np.abs(y - c) / half, 0.0, 1.0)
    return (1 - t * t) ** 2


def build_profiles(layers: dict) -> dict:
    ol = drawing.outlines(layers)
    side, plan = ol["side"], ol["plan"]

    # Боковой силуэт: верх — с чертежа (сглаженный), перёд, зад и низ — свои гладкие кривые.
    # По колонке Y тело занимает bot(Y)..top(Y); на концах верх и низ сходятся в носке.
    y0, z0 = -2.45, 0.0
    ny, nz = int(5.10 / GRID_RES), int(1.50 / GRID_RES)
    m = poly_mask(side, y0, z0, ny, nz, GRID_RES)
    ys = y0 + (np.arange(ny) + 0.5) * GRID_RES
    zs = z0 + (np.arange(nz) + 0.5) * GRID_RES
    has = m.any(axis=1)
    top_raw = np.where(has, zs[np.clip(nz - 1 - np.argmax(m[:, ::-1], axis=1), 0, nz - 1)], np.nan)
    ok = ~np.isnan(top_raw)
    top_s = top_raw.copy()
    top_s[ok] = ndimage.gaussian_filter1d(top_raw[ok], 6.0, mode="nearest")
    mid = (ys > NOSE_TOP[-1][0] + 0.01) & (ys < TAIL_TOP[0][0] - 0.01)
    step = max(1, int(0.02 / GRID_RES))
    mid_pts = list(zip(ys[mid][::step], top_s[mid][::step]))
    top_pts = NOSE_TOP + mid_pts + TAIL_TOP
    bot_pts = NOSE_BOT + BOTTOM + TAIL_BOT
    y_tip0, y_tip1 = NOSE_TIP[0], TAIL_TIP[0]
    tp = PchipInterpolator([NOSE_TIP[0]] + [p[0] for p in top_pts] + [TAIL_TIP[0]],
                           [NOSE_TIP[1]] + [p[1] for p in top_pts] + [TAIL_TIP[1]])
    bp = PchipInterpolator([NOSE_TIP[0]] + [p[0] for p in bot_pts] + [TAIL_TIP[0]],
                           [NOSE_TIP[1]] + [p[1] for p in bot_pts] + [TAIL_TIP[1]])
    inside = (ys > y_tip0) & (ys < y_tip1)
    top = np.where(inside, tp(np.clip(ys, y_tip0, y_tip1)), np.nan)
    bot = np.where(inside, bp(np.clip(ys, y_tip0, y_tip1)), np.nan)

    belt = PchipInterpolator([p[0] for p in BELT], [p[1] for p in BELT], extrapolate=True)(ys)
    in_gh = (ys > WS_BASE[0]) & (ys < BL_BASE[0])
    z_low_top = np.where(in_gh, belt, top)

    # План: полуширина по Y, зеркала убрать, расширить под CLE 53
    xs0 = -1.1
    nx = int(2.2 / GRID_RES)
    pm = poly_mask(plan, xs0, y0, nx, ny, GRID_RES)  # [x, y]
    xs = xs0 + (np.arange(nx) + 0.5) * GRID_RES
    half = np.array([xs[pm[:, j]].max() if pm[:, j].any() else 0.0 for j in range(ny)])
    mirror = (ys > -0.62) & (ys < -0.05)
    keep = ~mirror
    half[mirror] = np.interp(ys[mirror], ys[keep], half[keep])
    # Крылья CLE на плане срезаем до ширины двери: расширение даёт FLARES вокруг колёс
    half_amg = np.where(half > 0, np.minimum(half + (HALF_DOOR - 0.914), HALF_DOOR), 0.0)

    # Растровая ступенька контуров даёт поперечные полосы на сетке — сгладить в пределах машины
    def smooth(a: np.ndarray, sigma: float = 4.0) -> np.ndarray:
        ok = ~np.isnan(a) & (a != 0) if a is half_amg else ~np.isnan(a)
        r = a.copy()
        r[ok] = ndimage.gaussian_filter1d(a[ok], sigma, mode="nearest")
        return r

    z_low_top, half_amg = smooth(z_low_top, 3.0), smooth(half_amg, 8.0)
    return {"ys": ys, "zs": zs, "top": top, "bot": bot, "z_low_top": z_low_top, "in_gh": in_gh,
            "half": half_amg, "side": side, "plan": plan, "outlines": ol}


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Profile1D:
    """Кривая v(Y) на мелкой сетке; расстояние до неё по нормали в первом приближении."""

    def __init__(self, ys: np.ndarray, v: np.ndarray) -> None:
        self.ys, self.v = ys, v
        self.k = 1.0 / np.sqrt(1.0 + np.gradient(v, ys) ** 2)

    def at(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return np.interp(y, self.ys, self.v), np.interp(y, self.ys, self.k)


def extend(ys: np.ndarray, v: np.ndarray, valid: np.ndarray, slope: float) -> np.ndarray:
    """За носком и хвостом кривая круто уходит (slope на метр) — тело кончается."""
    r = v.copy()
    i0, i1 = np.where(valid)[0][[0, -1]]
    r[:i0] = v[i0] + slope * (ys[i0] - ys[:i0])
    r[i1 + 1:] = v[i1] + slope * (ys[i1 + 1:] - ys[i1])
    return r


def build_field(pr: dict, h: float):
    ys, top, bot, zlt, half = pr["ys"], pr["top"], pr["bot"], pr["z_low_top"], pr["half"]
    valid = ~np.isnan(top)
    t_low = Profile1D(ys, extend(ys, zlt, valid, -30.0))
    b_low = Profile1D(ys, extend(ys, bot, valid, 30.0))
    t_gh_raw = np.where(pr["in_gh"], top, zlt - 0.15)
    t_gh = Profile1D(ys, extend(ys, t_gh_raw, valid, -30.0))
    zlt_e = extend(ys, zlt, valid, 0.0)
    plan = Profile1D(ys, extend(ys, half, valid & (half > 0), -30.0))

    gx = np.arange(-1.06, 1.06 + h / 2, h)
    gy = np.arange(-2.42, 2.60 + h / 2, h)
    gz = np.arange(-0.02, 1.48 + h / 2, h)
    F = np.empty((len(gx), len(gy), len(gz)), dtype=np.float32)
    Y, Z = np.meshgrid(gy, gz, indexing="ij")

    g_z = np.interp(gz, [p[0] for p in G_SECTION], [p[1] for p in G_SECTION])[None, :]
    gh_half = np.interp(gy, [p[0] for p in GH_HALF], [p[1] for p in GH_HALF])[:, None]
    zlt_y = np.interp(gy, ys, zlt_e)[:, None]
    w_f = smoothstep(-1.55, -2.05, gy)
    w_r = smoothstep(1.75, 2.20, gy)
    sw_f = [p[0] for p in NOSE_SWEEP], [p[1] for p in NOSE_SWEEP]
    sw_r = [p[0] for p in TAIL_SWEEP], [p[1] for p in TAIL_SWEEP]
    kt = 1.0 / np.sqrt(1.0 + GH_TUMBLE ** 2)
    crease_z = PchipInterpolator([p[0] for p in CREASE], [p[1] for p in CREASE], extrapolate=True)(gy)
    crease_on = smoothstep(CREASE[0][0], CREASE[0][0] + 0.15, gy) * (1 - smoothstep(CREASE[-1][0] - 0.15, CREASE[-1][0], gy))
    door_z = np.interp(gy, [p[0] for p in DOOR_LINE], [p[1] for p in DOOR_LINE])
    door_on = smoothstep(-1.05, -0.85, gy) * (1 - smoothstep(0.80, 0.98, gy))

    for i, x in enumerate(gx):
        ax = abs(x)
        # Профиль носа и кормы к углам уходит назад (по плану), а не обрезается планом
        yq = gy - np.interp(ax, *sw_f) * w_f + np.interp(ax, *sw_r) * w_r
        pv, pk = plan.at(gy)
        crown = CROWN_HOOD * np.clip(ax / np.maximum(pv, 0.05), 0, 1.2)[:, None] ** 2
        tv, tk = t_low.at(yq)
        bv, bk = b_low.at(yq)
        d_top = (Z + crown - tv[:, None]) * tk[:, None]
        d_bot = (bv[:, None] - Z) * bk[:, None]
        d_side = smax(d_top, d_bot, R_NOSE)
        d_plan = (ax / g_z - pv[:, None]) * pk[:, None] * g_z
        # Крылья: выпуклость борта кольцом вокруг оси колеса, ниже порога — нет
        for yc, amp in FLARES:
            r = np.sqrt((Y - yc) ** 2 + (Z - drawing.WHEEL_Z) ** 2)
            ring = 1.0 - smoothstep(FLARE_R0, FLARE_R1, r)
            d_plan = d_plan - amp * ring * smoothstep(0.16, 0.30, Z)
        # Линия плеча (острое ребро) и нижняя линия двери (впадина)
        zc = crease_z[:, None]
        d_plan = d_plan - CREASE_AMP * np.clip(1 - np.abs(Z - zc) / CREASE_W, 0, None) * crease_on[:, None]
        zd = door_z[:, None]
        d_plan = d_plan - DOOR_AMP * np.clip(1 - np.abs(Z - zd) / DOOR_W, 0, None) * door_on[:, None]
        lower = smax(d_side, d_plan, R_SHOULDER)
        # Кабина: крыша и стёкла сбоку, боковины с завалом внутрь
        crown_r = CROWN_ROOF * (ax / 0.60) ** 2
        gv, gk = t_gh.at(gy)
        d_gtop = (Z + crown_r - gv[:, None]) * gk[:, None]
        wg = gh_half - GH_TUMBLE * np.clip(Z - zlt_y, 0, None)
        d_gside = (ax - wg) * kt
        d_gbot = (zlt_y - 0.25) - Z
        # Кабина только над поясом между лобовым и задним стёклами (иначе тянется под капот
        # в нос вровень с корпусом и плавное объединение даёт тонкую «скорлупу» перед бампером)
        d_gy = np.maximum(WS_BASE[0] - 0.12 - Y, Y - (BL_BASE[0] + 0.12))
        cabin = smax(smax(smax(d_gtop, d_gside, R_ROOF), d_gbot, 0.02), d_gy, 0.02)
        body = smin(lower, cabin, R_UNION)
        # Колёсные арки: цилиндры поперёк, только снаружи от ниши
        for c in (-drawing.WHEEL_Y, drawing.WHEEL_Y):
            d_c = np.sqrt((Y - c) ** 2 + (Z - drawing.WHEEL_Z) ** 2) - ARCH_R
            arch = smax(d_c, np.full_like(Y, WELL_X - ax), 0.02)
            body = smax(body, -arch, R_ARCH)
        F[i] = body
    return F, (gx[0], gy[0], gz[0])


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    layers = drawing.load_layers()
    pr = build_profiles(layers)
    print(f"полуширина: перед {pr['half'][np.argmin(abs(pr['ys'] + drawing.WHEEL_Y))]:.3f}, "
          f"дверь {pr['half'][np.argmin(abs(pr['ys']))]:.3f}, зад {pr['half'][np.argmin(abs(pr['ys'] - drawing.WHEEL_Y))]:.3f}")
    F, origin = build_field(pr, h)
    verts, faces, normals, _ = measure.marching_cubes(F, level=0.0, spacing=(h, h, h))
    verts += np.array(origin)
    import trimesh
    mesh = trimesh.Trimesh(verts, faces, process=True)
    mesh.fix_normals()  # наружу: поле отрицательно внутри, а обход граней у marching cubes обратный
    print(f"сетка: {len(mesh.vertices)} вершин, {len(mesh.faces)} треугольников; "
          f"габарит {mesh.extents.round(3)}; замкнута {mesh.is_watertight}")
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out)
    print(out)


if __name__ == "__main__":
    main()
