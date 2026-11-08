"""Общее для пожарной машины: подключение sand3d, рамки построения, палитра проверочных материалов.

sand3d (https://github.com/Sandflow-ai/sand3d, Apache-2.0) лежит в _asset_src/sand3d (клон тега v1.6.3,
в git не идёт). Все размеры — spec.py, метры.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "_asset_src" / "sand3d" / "src"))

import sand3d as s3d  # noqa: E402
from sand3d import _core  # noqa: E402

# Крупные круглые детали у глаза (колёса, ступицы) — до 128 сечений на оборот вместо 64.
_core.TURN_MAX = 128


def side(x: float = 0.0, sign: float = 1.0, y: float = 0.0, z: float = 0.0) -> s3d.Frame:
    """Плоскость борта: профиль (Y, Z), выдавливание вдоль ±X. При sign = −1 профильная ось x идёт по −Y.

    Деталь, выдавленная на рамке, помнит её: `s3d.at(деталь, y=…)` двигает вдоль осей рамки, а не мира —
    такие детали строить сразу на месте (начало рамки в (x, y, z))."""
    return s3d.Frame((x, y, z), (sign, 0, 0), up=(0, 0, 1))


def front(y: float, x: float = 0.0, z: float = 0.0) -> s3d.Frame:
    """Плоскость, смотрящая вперёд (−Y): профиль (X, Z), выдавливание вперёд."""
    return s3d.Frame((x, y, z), (0, -1, 0), up=(0, 0, 1))


def rear(y: float, x: float = 0.0, z: float = 0.0) -> s3d.Frame:
    """Плоскость, смотрящая назад (+Y): профильная ось x идёт по −X, y — по Z."""
    return s3d.Frame((x, y, z), (0, 1, 0), up=(0, 0, 1))


def tilted(origin: tuple[float, float, float], normal: tuple[float, float, float]) -> s3d.Frame:
    """Наклонная плоскость (лобовое стекло): x — вдоль X машины, y — вверх по плоскости."""
    return s3d.Frame(origin, normal)


def along_x(ob, x0: float, y: float, z: float):
    """Деталь, построенная вдоль своей Z (цилиндр, выдавливание), — положить осью вдоль +X от x0."""
    return s3d.at(ob, x=x0, y=y, z=z, ry=90)


def along_y(ob, x: float, y0: float, z: float):
    """То же вдоль +Y от y0."""
    return s3d.at(ob, x=x, y=y0, z=z, rx=-90)


def unit(dx: float, dy: float, dz: float) -> tuple[float, float, float]:
    n = math.sqrt(dx * dx + dy * dy + dz * dz)
    return (dx / n, dy / n, dz / n)


# --- проверочные материалы (до текстур — только чтобы читались части) ----------------------------------
def paint_red(ob):
    return s3d.material(ob, "painted_metal", color="#b3141c", roughness=0.35)


def paint_white(ob):
    return s3d.material(ob, "painted_metal", color="#e6e6e1", roughness=0.35)


def alu(ob):
    return s3d.material(ob, "aluminium", color="#b9bcbf", roughness=0.35)


def black_plastic(ob):
    return s3d.material(ob, "plastic", color="#141414", roughness=0.6)


def rubber(ob):
    return s3d.material(ob, "rubber", color="#111111")


def steel_dark(ob):
    return s3d.material(ob, "painted_metal", color="#1d1d1f", roughness=0.55)


def chrome(ob):
    return s3d.material(ob, "chrome")


def glass(ob):
    return s3d.material(ob, "glass", color="#9fb3b8", opacity=0.35)


def lens(ob, color: str):
    return s3d.material(ob, "glass", color=color, opacity=0.8)
