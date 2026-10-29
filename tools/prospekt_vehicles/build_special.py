"""Транспорт «Проспекта», партия 2: такси и полиция на принятом седане (форма v01) — навесные детали на крышу.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_special.py -- \
        <taxi|police> <выход.blend>

Кузов — без изменений из Sedan_geometry_v01.blend (принят владельцем 2026-10-25); раскраска (шашки, полосы, надписи,
бортовой номер) — отделкой. Навесное — vspecial.py (то же ставит game_kit.py на игровую сетку):
- такси — плафон «шашечки» на магнитных лапках поперёк крыши, провод к двери водителя;
- полиция — балка проблесковых маячков (синий слева, красный справа, громкоговоритель посередине) на кронштейнах,
  зацепленных за проёмы дверей, и антенна рации на задней части крыши (не на крышке багажника: у «Открыт» она поднята).
Варианты — коллекции седана «Целый», «Открыт», «Битый» (у битого такси плафон опрокинут, провод оборван);
«Сгоревший» не берётся — пластик плафона и балки сгорел бы вместе с салоном. Детали — дочерние к корню варианта.
Форма принята владельцем 2026-10-29 («Да, к текстурам»).
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401 — подключает модули купе (engine_bay, parts)
import vspecial  # noqa: E402
from build_car import link, make_mesh  # noqa: E402

SEDAN = Path("E:/Models Blender/VEHICLES/Город_партия1/Седан/models/Sedan_geometry_v01.blend")
KEEP = ("Целый", "Открыт", "Битый")


def roof_vertices(col: bpy.types.Collection, root: bpy.types.Object) -> np.ndarray:
    """Вершины крыши варианта в осях его корня (оси машины)."""
    roof = next(o for o in col.objects if o.type == "MESH" and o.name.startswith("Roof"))
    inv = root.matrix_world.inverted()
    return np.array([tuple(inv @ (roof.matrix_world @ v.co)) for v in roof.data.vertices])


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    kind, out = argv[0], Path(argv[1])
    bpy.ops.wm.open_mainfile(filepath=str(SEDAN))
    for c in list(bpy.data.collections):
        if c.name not in KEEP:
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.collections.remove(c)
    for name in KEEP:
        col = bpy.data.collections[name]
        root = next(o for o in col.objects if o.parent is None)
        roof = roof_vertices(col, root)
        for nm, mat, (V, F) in vspecial.accessories(kind, roof, knocked=(kind == "taxi" and name == "Битый")):
            link(f"{nm}_{name}", make_mesh(nm, mat, V, F), col, root)
        yc, z, half = vspecial.roof_top(roof)
        print(f"{kind} {name}: крыша y={yc:.2f} z={z:.3f}, полуширина плоской части {half:.2f}")
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("сохранено:", out)


if __name__ == "__main__":
    main()
