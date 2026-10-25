"""Транспорт «Проспекта»: черновой объём легковой по полю формы — для сверки пропорций.

    python -X utf8 tools/prospekt_vehicles/blockout.py <класс> <выход.ply> [шаг_м]

Сетка нулевого уровня поля (marching cubes) и колёса цилиндрами по размеру шин. Это не модель,
а проверка силуэта: виды — tools/coupe_ilya/check_views.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from skimage import measure

sys.path.insert(0, str(Path(__file__).parent))
from specs import CLASSES  # noqa: E402
from specs_bus import BOXES  # noqa: E402
from vfield import BoxField, CarField  # noqa: E402


def body_mesh(spec: dict, h: float) -> trimesh.Trimesh:
    f = BoxField(spec) if "kind" in spec else CarField(spec)
    hw = spec["width"] / 2 + 0.12
    y0 = min(p[1] for p in spec["front"]) - 0.25
    y1 = max(p[1] for p in spec["rear"]) + 0.25
    gx = np.arange(-hw, hw + h / 2, h)
    gy = np.arange(y0, y1, h)
    gz = np.arange(0.05, spec["height"] + 0.12, h)
    F = np.empty((len(gx), len(gy), len(gz)), dtype=np.float32)
    Y, Z = np.meshgrid(gy, gz, indexing="ij")
    for i, x in enumerate(gx):
        F[i] = f.eval(np.full_like(Y, x), Y, Z)
    v, fc, _, _ = measure.marching_cubes(F, level=0.0, spacing=(h, h, h))
    v += np.array([gx[0], gy[0], gz[0]])
    m = trimesh.Trimesh(v, fc, process=True)
    m.fix_normals()
    return m


def wheels(spec: dict) -> list[trimesh.Trimesh]:
    out = []
    for y in spec["wheel_y"]:
        for side in (-1, 1):
            c = trimesh.creation.cylinder(radius=spec["tire_r"], height=spec["tire_w"], sections=64)
            c.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
            tr = spec.get("track", spec.get("track_f", 1.5))
            c.apply_translation([side * (tr / 2), y, spec["wheel_z"]])
            out.append(c)
    return out


def main() -> None:
    spec = {**CLASSES, **BOXES}[sys.argv[1]]
    out = Path(sys.argv[2])
    h = float(sys.argv[3]) if len(sys.argv) > 3 else 0.012
    body = body_mesh(spec, h)
    ext = body.bounds
    print(f"кузов: {len(body.faces)} треугольников; X {ext[0][0]:.3f}..{ext[1][0]:.3f}, "
          f"Y {ext[0][1]:.3f}..{ext[1][1]:.3f}, Z {ext[0][2]:.3f}..{ext[1][2]:.3f}; "
          f"габарит {(ext[1] - ext[0]).round(3)}")
    m = trimesh.util.concatenate([body] + wheels(spec))
    out.parent.mkdir(parents=True, exist_ok=True)
    m.export(out)
    print(out)


if __name__ == "__main__":
    main()
