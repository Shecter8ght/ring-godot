"""Купе Ильи: раскладка панелей кузова и сборка сетки (OBJ).

    python -X utf8 tools/coupe_ilya/panels.py [выход.obj] [только=имя,имя]

Кромки панелей задаются по осевой линии зазора на видах (сбоку, сверху, спереди, сзади)
и переносятся на поверхность поля BodyField. Левый борт (+X) строится, правый — зеркалом.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import body_field  # noqa: E402
import drawing  # noqa: E402
from patch import MeshBuilder, panel  # noqa: E402
from surface import Surface, from_side, spline2d  # noqa: E402

OUT_DEFAULT = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\checks\panels_v01.obj")
GAP = 0.0045                 # зазор между панелями, м


def side_edges(surf: Surface, edges: dict[str, list[tuple[float, float]]], side: float = 1.0) -> list[np.ndarray]:
    """Четыре кромки панели с вида сбоку: низ, зад(право), верх, перёд(лево) — в порядке лоскута.

    edges: bottom (перёд→зад), rear (низ→верх), top (перёд→зад), front (низ→верх).
    """
    order = ("bottom", "rear", "top", "front")
    return [from_side(surf, spline2d(edges[k], 300), side) for k in order]


# --- Дверь ------------------------------------------------------------------------------------
# Осевая линия зазора двери по чертежу (POLYLINE212, 198), верх — чуть ниже пояса окон.
DOOR = {
    "bottom": [(-0.700, 0.335), (-0.30, 0.333), (0.10, 0.337), (0.400, 0.352)],
    "rear": [(0.400, 0.352), (0.470, 0.376), (0.525, 0.445), (0.572, 0.567), (0.617, 0.75), (0.633, 0.85),
             (0.630, 0.92), (0.590, 1.005)],
    "top": [(-0.680, 0.955), (-0.37, 0.972), (0.20, 0.992), (0.590, 1.005)],
    "front": [(-0.700, 0.335), (-0.728, 0.45), (-0.752, 0.632), (-0.742, 0.80), (-0.715, 0.90), (-0.680, 0.955)],
}


def mirror(V: np.ndarray, F: list[tuple[int, ...]]) -> tuple[np.ndarray, list[tuple[int, ...]]]:
    W = V.copy()
    W[:, 0] *= -1
    return W, [f[::-1] for f in F]


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT_DEFAULT
    pr = body_field.build_profiles(drawing.load_layers())
    surf = Surface(body_field.BodyField(pr))
    mb = MeshBuilder()

    V, F = panel(surf, side_edges(surf, DOOR), nu=110, nv=56, gap=GAP)
    mb.add("Door_L", "paint", V, F)
    mb.add("Door_R", "paint", *mirror(V, F))
    mb.write_obj(out)
    print(out, sum(len(o[3]) for o in mb.objects), "граней")


if __name__ == "__main__":
    main()
