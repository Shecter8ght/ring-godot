"""Транспорт «Проспекта»: сборка «коробчатой» машины в Blender — городской автобус 12 м, ПАЗ, ГАЗель-маршрутка.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_bus.py -- \
        <bus12|paz|gazel> <выход.blend> [варианты: intact,open]

Коллекции «Целый» и «Двери открыты» (во втором створки повёрнуты на петлях, сдвижная отъехала назад).
Створки, двери и люк висят на пустышках-петлях (Hinge_*): повернуть по оси Z пустышки — откроется.
Колёса: передние одинарные, задние двускатные (внутреннее колесо пары развёрнуто лицом внутрь).
Материалы проверочные (REVIEW_*); производственные UV и отделка — после принятия формы.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import vlib  # noqa: E402,F401
from build_car import link, make_mesh  # noqa: E402
from specs_bus import BOXES  # noqa: E402
from surface import Surface  # noqa: E402
from vfield import BoxField  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CLS = argv[0] if argv else "bus12"
OUT = Path(argv[1]) if len(argv) > 1 else None
VARIANTS = argv[2].split(",") if len(argv) > 2 else ["intact", "open"]


def hinges(spec: dict, S: dict, surf, views) -> dict:
    """Петли: створки «гармошки» — у наружных кромок проёма; дверь кабины — по передней кромке;
    задние распашные — по наружным кромкам; знак — куда поворот открывает."""
    lay = spec["lay"]
    h = {}
    for side, sgn, vname, doors in (("l", 1.0, "side", lay["doors_l"]), ("r", -1.0, "side_r", lay["doors_r"])):
        for j, d in enumerate(doors):
            grp = f"door_{side}{j + 1}"
            zm = (lay["rim"]["z_sbot"] + d["z_top"]) / 2
            p0 = views[vname].lift(surf, np.array([[d["y0"], zm]]))[0]
            p1 = views[vname].lift(surf, np.array([[d["y1"], zm]]))[0]
            z0 = lay["rim"]["z_sbot"]
            if d["kind"] == "fold2":
                x = p0[0] - sgn * 0.035
                h[grp + "a"] = (np.array([x, d["y0"] + 0.03, z0]), np.array([0, 0, 1.0]), -sgn)
                h[grp + "b"] = (np.array([x, d["y1"] - 0.03, z0]), np.array([0, 0, 1.0]), sgn)
            elif d["kind"] == "car":
                h[grp] = (np.array([p0[0] - sgn * 0.03, d["y0"] + 0.02, z0]), np.array([0, 0, 1.0]), -sgn)
    if "rear_doors" in S:
        u0, u1, v0, v1, r = S["rear_doors"]
        yb = float(views["rear"].lift(surf, np.array([[0.0, (v0 + v1) / 2]]))[0][1])
        h["rdoor_l"] = (np.array([u1 - 0.02, yb - 0.02, v0]), np.array([0, 0, 1.0]), -1.0)
        h["rdoor_r"] = (np.array([u0 + 0.02, yb - 0.02, v0]), np.array([0, 0, 1.0]), 1.0)
    return h


def wheels(spec: dict, col, root, meshes: dict, variant: str) -> None:
    import vbus  # noqa: F401
    yf, yr = spec["wheel_y"]
    places = []
    for sgn in (1.0, -1.0):
        places.append(("F", sgn, sgn * spec["track_f"] / 2, yf, "outer"))
        if spec.get("dual_rear"):
            g = spec["dual_gap"] / 2
            places.append(("R", sgn, sgn * (spec["track_r"] / 2 + g), yr, "outer"))
            places.append(("Ri", sgn, sgn * (spec["track_r"] / 2 - g), yr, "inner"))
        else:
            places.append(("R", sgn, sgn * spec["track_r"] / 2, yr, "outer"))
    for nm, sgn, x, y, kind in places:
        key = nm + ("L" if sgn > 0 else "R")
        hub = bpy.data.objects.new(f"Wheel_{key}_{variant}", None)
        hub.empty_display_size = 0.3
        col.objects.link(hub)
        hub.parent = root
        hub.location = (x, y, spec["wheel_z"])
        hub.rotation_euler = (0, 0, 0 if sgn > 0 else math.pi)
        for pname, me in meshes[kind]:
            link(f"{pname}_{key}_{variant}", me, col, hub)


def main() -> None:
    import vbus

    spec = BOXES[CLS]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    t0 = time.time()
    field = BoxField(spec)
    surf = Surface(field)
    views = vlib.make_views(spec)
    parts, S = vbus.build(surf, field, spec, views)
    for name, view, outer, holes in vbus.DEBUG:
        print("  НЕ СОБРАНА:", name, view)
    if vbus.DEBUG and OUT:
        dbg = {}
        for i, (name, view, outer, holes) in enumerate(vbus.DEBUG):
            dbg[f"{i}_{name}_{view}_outer"] = outer
            for j, hh in enumerate(holes):
                dbg[f"{i}_{name}_{view}_hole{j}"] = hh
        np.savez(str(OUT.with_suffix(".debug.npz")), **dbg)
    parts += vbus.details(surf, field, spec, views, S)
    parts += vbus.interior(field, spec, S)
    print(f"деталей: {len(parts)}, {time.time() - t0:.1f} с")
    hg = hinges(spec, S, surf, views)
    meshes = {k: [(n, make_mesh("W_" + n, m, V, F)) for n, m, V, F in vbus.truck_wheel(spec, inner=(k == "inner"))]
              for k in ("outer", "inner")}
    titles = {"intact": "Целый", "open": "Двери открыты"}
    for i, v in enumerate(VARIANTS):
        col = bpy.data.collections.new(titles[v])
        bpy.context.scene.collection.children.link(col)
        root = bpy.data.objects.new(f"{spec['name']}_{v}", None)
        root.empty_display_type = "ARROWS"
        col.objects.link(root)
        root.location = (i * (spec["width"] + 1.5), 0, 0)
        hobs = {}
        for grp, (a, axis, sgn) in hg.items():
            e = bpy.data.objects.new(f"Hinge_{grp}_{v}", None)
            e.empty_display_type = "SINGLE_ARROW"
            e.empty_display_size = 0.4
            col.objects.link(e)
            e.parent = root
            q = Vector(axis).normalized().to_track_quat("Z", "Y")
            e.matrix_basis = Matrix.Translation(Vector(a)) @ q.to_matrix().to_4x4()
            hobs[grp] = (e, sgn)
        bpy.context.view_layer.update()
        for name, mat, V, F, grp in parts:
            if V is None or len(V) == 0:
                continue
            parent = hobs[grp][0] if grp in hobs else root
            ob = link(f"{name}_{v}", make_mesh(name, mat, V, F), col, parent)
            if parent is not root:
                ob.matrix_parent_inverse = parent.matrix_basis.inverted()
            if v == "open" and grp.startswith("door_") and grp not in hobs:
                # сдвижная дверь: наружу и назад по направляющей
                d = [dd for dd in spec["lay"]["doors_r"] + spec["lay"]["doors_l"] if dd["kind"] == "slide"]
                if d:
                    sgn = -1.0 if grp.startswith("door_r") else 1.0
                    ob.location.x += sgn * 0.07
                    ob.location.y += (d[0]["y1"] - d[0]["y0"]) - 0.08
        wheels(spec, col, root, meshes, v)
        if v == "open":
            for grp, (e, sgn) in hobs.items():
                deg = 82.0 if grp[-1] in "ab" else (70.0 if grp.startswith("rdoor") else 60.0)
                e.matrix_basis = e.matrix_basis @ Matrix.Rotation(math.radians(deg) * sgn, 4, "Z")
    if OUT:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.preferences.filepaths.save_version = 0      # без .blend1 рядом с выдачей (только в этом запуске)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
        print("сохранено:", OUT, f"{time.time() - t0:.1f} с")


if __name__ == "__main__":
    main()
