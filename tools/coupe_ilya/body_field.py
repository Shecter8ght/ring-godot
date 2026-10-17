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
PROFILES = Path(__file__).parent / "field_profiles.npz"
PROFILE_KEYS = ("ys", "top", "bot", "z_low_top", "in_gh", "half")

from fieldcore import *  # noqa: E402,F401,F403 — размеры и поле формы
from fieldcore import BodyField, pchip  # noqa: E402

GRID_RES = 0.002             # шаг растров двумерных профилей
SD_BLUR = 1.5                # размытие растровых расстояний (в пикселях) — убирает ступеньки


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


def build_field(pr: dict, h: float):
    field = BodyField(pr)
    gx = np.arange(-1.06, 1.06 + h / 2, h)
    gy = np.arange(-2.42, 2.60 + h / 2, h)
    gz = np.arange(-0.02, 1.48 + h / 2, h)
    F = np.empty((len(gx), len(gy), len(gz)), dtype=np.float32)
    Y, Z = np.meshgrid(gy, gz, indexing="ij")
    for i, x in enumerate(gx):
        F[i] = field.eval(np.full_like(Y, x), Y, Z)
    return F, (gx[0], gy[0], gz[0])


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    h = float(sys.argv[2]) if len(sys.argv) > 2 else 0.01
    layers = drawing.load_layers()
    pr = build_profiles(layers)
    print(f"полуширина: перед {pr['half'][np.argmin(abs(pr['ys'] + WHEEL_Y))]:.3f}, "
          f"дверь {pr['half'][np.argmin(abs(pr['ys']))]:.3f}, зад {pr['half'][np.argmin(abs(pr['ys'] - WHEEL_Y))]:.3f}")
    # Профили для сборки в Blender (без чертежа и scipy): field_profiles.npz рядом со скриптом
    np.savez_compressed(PROFILES, **{k: np.asarray(pr[k], dtype=float) for k in PROFILE_KEYS})
    print("профили:", PROFILES)
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
