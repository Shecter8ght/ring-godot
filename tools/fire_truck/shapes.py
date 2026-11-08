"""Общие формы пожарной машины: рифлёные панели (рольставни, короб воздухозаборника), кольца уплотнителей, швы."""
from __future__ import annotations

import lib
from lib import s3d


def ribbed_profile(x_out: float, z0: float, z1: float, pitch: float, groove: float, thick: float,
                   outward: float) -> list[tuple[float, float]]:
    """Сечение рифлёной панели в плоскости (X, Z): лицо в x_out с V-канавками через `pitch`,
    обратная сторона плоская на `thick` внутрь. `outward` = ±1 — куда смотрит лицо."""
    n = max(1, round((z1 - z0) / pitch))
    p = (z1 - z0) / n
    back = x_out - outward * thick
    pts: list[tuple[float, float]] = [(back, z1), (x_out - outward * groove, z1)]
    for i in range(n):
        top = z1 - i * p
        pts += [(x_out, top - 0.18 * p), (x_out, top - 0.82 * p), (x_out - outward * groove, top - p)]
    pts.append((back, z0))
    return pts


def ribbed_panel(name: str, x_out: float, outward: float, y0: float, y1: float, z0: float, z1: float,
                 pitch: float = 0.032, groove: float = 0.0045, thick: float = 0.014):
    """Рифлёная панель вдоль Y (полосы горизонтальные): рольставня, рифлёный короб."""
    pts = ribbed_profile(x_out, z0, z1, pitch, groove, thick, outward)
    # плоскость, смотрящая назад: профильная x идёт по −X мира
    prof = s3d.poly([(-x, z) for x, z in pts])
    return s3d.extrude(name, prof, y1 - y0, on=lib.rear(y0))


def ribbed_panel_x(name: str, y_out: float, outward: float, x0: float, x1: float, z0: float, z1: float,
                   pitch: float = 0.032, groove: float = 0.0045, thick: float = 0.014):
    """Рифлёная панель на торце (лицо смотрит по ±Y, полосы вдоль X): задняя рольставня."""
    pts = ribbed_profile(y_out, z0, z1, pitch, groove, thick, outward)
    # плоскость борта (x → +Y мира, y → Z), выдавливание вдоль +X
    prof = s3d.poly(pts)
    return s3d.extrude(name, prof, x1 - x0, on=lib.side(x0))


def outline(pts: list[tuple[float, float]], r: float):
    return s3d.poly(pts, fillet=r)


def box_pts(a0: float, a1: float, b0: float, b1: float) -> list[tuple[float, float]]:
    return [(a0, b0), (a1, b0), (a1, b1), (a0, b1)]


def ring_tool(name: str, prof_pts: list[tuple[float, float]], r: float, gap: float, depth: float, on):
    """Кольцевой резец по контуру (шов двери, канавка): ширина `gap`, глубина `depth` от плоскости `on`."""
    outer = s3d.extrude(name, s3d.offset(outline(prof_pts, r), gap / 2), depth * 2, both=True, on=on)
    inner = s3d.extrude(name + "_in", s3d.offset(outline(prof_pts, r), -gap / 2), depth * 4, both=True, on=on)
    return s3d.cut(outer, inner)


def seal_ring(name: str, prof_pts: list[tuple[float, float]], r: float, band: float, depth: float, on):
    """Резиновый уплотнитель вокруг стекла: кольцо шириной `band` внутрь от контура, толщиной `depth`."""
    outer = s3d.extrude(name, outline(prof_pts, r), depth, on=on)
    inner = s3d.extrude(name + "_in", s3d.offset(outline(prof_pts, r), -band), depth * 3, both=True, on=on)
    ring = s3d.cut(outer, inner)
    lib.rubber(ring)
    return ring
