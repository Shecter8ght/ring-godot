"""Транспорт «Проспекта»: колёсные диски v2 — форма на просмотр владельцу (vwheels.py).

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_wheels.py -- <выход.blend>

Три колеса рядом вдоль Y, лицом к +X: колпак на штамповке (R15, как у седана), штамповка без колпака (R15), литой
(R16, как у хэтчбека); шина, обод, тормозной диск и суппорт — прежние (carparts), меняется только лицо колеса.
Каждое колесо — своя коллекция, детали — дочерние к пустышке колеса. Материалы REVIEW_* — только для формы.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401 — модули купе (wheel, parts)
import carparts as cp  # noqa: E402
import vwheels  # noqa: E402
from build_car import link, make_mesh  # noqa: E402
from specs import CLASSES  # noqa: E402

DESIGNS = [("Колпак", "cap", "sedan"), ("Штамповка", "steel", "sedan"), ("Литой", "alloy", "hatch")]


def main() -> None:
    out = Path(sys.argv[sys.argv.index("--") + 1])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for i, (title, style, cls) in enumerate(DESIGNS):
        spec = CLASSES[cls]
        R, W, rim_r = spec["tire_r"], spec["tire_w"], spec["rim_d_in"] * 0.0127
        parts = [("Tire", "rubber", *cp.tire(R, W, rim_r)),
                 ("Rim_Barrel", "rim_alloy" if style == "alloy" else "rim_steel", *cp.rim_barrel(rim_r, W))]
        disc, cal = cp.brake(rim_r)
        parts += [("Brake_Disc", "brake", *disc), ("Caliper", "steel_dark", *cal)]
        parts += vwheels.face(style, rim_r, W, spec)
        col = bpy.data.collections.new(title)
        bpy.context.scene.collection.children.link(col)
        hub = bpy.data.objects.new(f"Wheel_{style}", None)
        hub.empty_display_type = "ARROWS"
        hub.empty_display_size = 0.25
        col.objects.link(hub)
        hub.location = (0.0, i * 0.85, R)
        tris = 0
        for name, mat, V, F in parts:
            me = make_mesh(name, mat, V, F)
            me.set_sharp_from_angle(angle=math.radians(35.0))   # кромки вырезов — острые (как smooth_normals игровой)
            link(f"{name}_{style}", me, col, hub)
            tris += sum(len(f) - 2 for f in F)
        print(f"{title}: деталей {len(parts)}, треугольников ≈ {tris:,}, R{spec['rim_d_in']}")
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(out))
    print("сохранено:", out)


if __name__ == "__main__":
    main()
