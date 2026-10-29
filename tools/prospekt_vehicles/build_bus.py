"""Транспорт «Проспекта»: сборка «коробчатой» машины в Blender — городской автобус 12 м, ПАЗ, ГАЗель-маршрутка.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_bus.py -- \
        <bus12|paz|gazel> <выход.blend> [варианты: intact,open]

Коллекции «Целый» и «Двери открыты» (во втором створки повёрнуты на петлях, сдвижная отъехала назад);
over — «Перевёрнут»: машина лежит на левом борту, смята и побита (overturned), низ подробнее — он на виду.
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


def underbody(spec: dict) -> list:
    """Низ городского автобуса для перевёрнутого: лёжа на боку он на виду. Передняя балка с поворотными кулаками и
    тягой, пневмобаллоны и амортизаторы обеих осей, поддон двигателя и коробки за задней осью, глушитель, топливный
    бак и ресиверы между осями, продольные лонжероны под полом."""
    import parts as pt
    from engine_bay import rounded_block, tube
    yf, yr = spec["wheel_y"]
    zw = spec["wheel_z"]
    zs = spec["lay"]["rim"]["z_sbot"]
    tf, tr = spec["track_f"] / 2, spec["track_r"] / 2
    out = []

    def add(name, mat, mesh):
        out.append((name, mat, mesh[0], mesh[1], "body"))
    add("Front_Axle", "steel_dark", tube([(-tf + 0.16, yf, zw - 0.02), (-0.30, yf, zw - 0.10), (0.30, yf, zw - 0.10),
                                          (tf - 0.16, yf, zw - 0.02)], 0.055, 12, 20))
    add("Knuckles", "steel_dark", pt.merge([rounded_block((s * (tf - 0.14), yf, zw), 0.14, 0.20, 0.30, 0.04)
                                            for s in (1, -1)]))
    add("Tie_Rod", "steel_dark", tube([(-tf + 0.18, yf + 0.22, zw - 0.06), (tf - 0.18, yf + 0.22, zw - 0.06)], 0.018, 8, 4))
    bags, shocks = [], []
    for y0, xs in ((yf, tf - 0.42), (yr - 0.32, tr - 0.36), (yr + 0.32, tr - 0.36)):
        for s in (1, -1):
            bags.append(tube([(s * xs, y0, zw + 0.02), (s * xs, y0, zw + 0.26)], 0.13, 16, 3))
            shocks.append(tube([(s * (xs + 0.12), y0 + 0.18, zw - 0.12), (s * (xs + 0.10), y0 + 0.16, zw + 0.30)],
                               0.03, 8, 3))
    add("Air_Bags", "liner", pt.merge(bags))
    add("Shocks", "steel_dark", pt.merge(shocks))
    rails = [rounded_block((s * 0.48, (yf + yr) / 2, zs - 0.08), 0.08, yr - yf - 1.2, 0.12, 0.01) for s in (1, -1)]
    add("Frame_Rails", "steel_dark", pt.merge(rails))
    y_eng = yr + 1.55
    add("Engine_Sump", "steel_dark", pt.merge([rounded_block((0.25, y_eng, zs - 0.06), 0.80, 1.30, 0.14, 0.04),
                                                rounded_block((0.10, yr + 0.62, zs - 0.05), 0.42, 0.55, 0.12, 0.04)]))
    add("Muffler", "steel_dark", pt.merge([rounded_block((-0.75, y_eng + 0.35, zs - 0.07), 0.55, 0.80, 0.18, 0.06),
                                            tube([(-0.40, y_eng - 0.50, zs - 0.10), (-0.75, y_eng - 0.10, zs - 0.08)],
                                                 0.05, 10, 6)]))
    add("Fuel_Tank", "steel_dark", rounded_block((-0.72, (yf + yr) / 2 + 0.6, zs - 0.08), 0.60, 1.20, 0.16, 0.05))
    add("Air_Tanks", "steel_dark", pt.merge([tube([(0.55 + 0.24 * k, -1.1, zs - 0.10), (0.55 + 0.24 * k, -0.2, zs - 0.10)],
                                                  0.10, 14, 3) for k in (0, 1)]))
    return out


def overturned(parts: list, spec: dict, S: dict, surf) -> list:
    """Перевёрнутый автобус: лёг на левый борт (+X). Деформации — в осях машины до поворота, одним полем на все детали
    (зазоры и кромки панелей сохраняются): борт снизу смят волной на 1,5–6 см, простенки окон этого борта прогнулись,
    кромка крыши со стороны удара сплющена (сильнее спереди), передний левый угол разбит. Стёкла борта снизу и два окна
    сверху выбиты (осколки в рамках), стёкла передней двери (вверху) выбиты — через неё выбирались, лобовое треснуло
    и прогнулось; левое зеркало сорвано, у правого остался кронштейн."""
    import vdamage as vd
    hw, H = spec["width"] / 2, spec["height"]
    noise = vd.Noise3(29)
    allV = np.vstack([V for _, _, V, _, _ in parts if V is not None and len(V)])
    y_f, y_r = float(allV[:, 1].min()), float(allV[:, 1].max())
    out = []
    gone = ("Glass_Side_L", "Mirror_Arm_L", "Mirror_Head_L", "Mirror_Glass_L", "Mirror_Head_R", "Mirror_Glass_R",
            "Glass_Side_R2", "Glass_Side_R4", "Door_R1A_Glass", "Door_R1B_Glass")
    for name, mat, V, F, grp in parts:
        if name.startswith(gone):
            continue
        if name == "Glass_windshield":
            mat = "glass_broken"
        out.append((name, mat, V, F, grp))
    # осколки в рамках выбитых окон (по контурам проёмов борта)
    holes = [("L", k, W) for k, W in enumerate(S.get("wins_L", []))] +             [("R", k, W) for k, W in enumerate(S.get("wins_R", [])) if k in (1, 3)]
    for side, k, W in holes:
        W = np.vstack([W, W[:1]])
        nrm = surf.normal(W)
        inward = W.mean(0) - W
        inward -= nrm * (inward * nrm).sum(1, keepdims=True)
        inward /= np.maximum(np.linalg.norm(inward, axis=1, keepdims=True), 1e-9)
        sv, sf = vd.shards_along(W - nrm * 0.01, inward, nrm, 40 + k + (20 if side == "R" else 0), 0.12)
        out.append((f"Glass_Shards_{side}{k + 1}", "glass_broken", sv, sf, "body"))
    out += underbody(spec)

    def deform(V):
        V = V.copy()
        x, z = V[:, 0], V[:, 2]
        w_side = vd.smoothstep(hw - 0.40, hw - 0.02, x)
        crumple = 0.015 + 0.045 * np.clip(noise.fbm(V, 0.9, 3) * 0.6 + 0.5, 0.0, 1.0)
        band = vd.smoothstep(1.05, 1.40, z) * (1.0 - vd.smoothstep(2.20, 2.50, z))
        dx = -crumple * w_side - 0.05 * band * w_side * (0.6 + 0.4 * noise(V + 5.0, 0.6))
        dist = np.hypot(np.clip(hw - x, 0.0, None), np.clip(H - z, 0.0, None))
        w_edge = 1.0 - vd.smoothstep(0.0, 0.80, dist)
        front = 1.0 - vd.smoothstep(y_f, y_r, V[:, 1]) * 0.6
        # вдоль кромки — рваные вмятины (шум по длине с шагом ~0,7 м), а не ровное скругление
        along = np.c_[np.zeros(len(V)), V[:, 1], np.zeros(len(V))]
        amp = (0.08 + 0.24 * np.clip(noise(along + 3.0, 0.7) * 0.8 + 0.5, 0.0, 1.0)) * front
        V[:, 0] += dx - amp * w_edge * 0.85
        V[:, 2] -= amp * w_edge * 0.50
        # передний левый угол разбит, задний левый — помят; вмятины крыши, кондиционер смят углом к земле
        V = vd.dent(V, (hw, y_f + 0.35, 0.80), 1.05, 0.26, (-0.8, 0.45, 0.0))
        V = vd.dent(V, (hw, y_r - 0.30, 1.40), 0.70, 0.10, (-1.0, -0.2, 0.0))
        for y, xr, rr, dd in ((-3.4, 0.35, 0.65, 0.07), (1.2, 0.60, 0.55, 0.06), (4.6, 0.20, 0.75, 0.05)):
            V = vd.dent(V, (xr, y, H), rr, dd, (0.0, 0.0, -1.0))
        return vd.dent(V, (0.95, 0.25, H + 0.20), 0.75, 0.16, (-1.0, 0.0, -0.35))
    ws = [V for n, _, V, _, _ in out if n == "Glass_windshield"]
    hit = ws[0][np.argmax(ws[0][:, 0] * 0.6 + ws[0][:, 2] * 0.4)] if ws else None
    res = []
    for name, mat, V, F, grp in out:
        if V is None or len(V) == 0:
            res.append((name, mat, V, F, grp))
            continue
        V = deform(np.asarray(V, float))
        if name == "Glass_windshield" and hit is not None:
            V = vd.crack_glass(V, hit, 0.55, 0.08, (0.0, 1.0, 0.0))
        res.append((name, mat, V, F, grp))
    return res


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
    titles = {"intact": "Целый", "open": "Двери открыты", "over": "Перевёрнут"}
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
        for name, mat, V, F, grp in (overturned(parts, spec, S, surf) if v == "over" else parts):
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
        if v == "over":
            # лежит на левом борту: поворот вокруг продольной оси, смятый борт — на земле; передние колёса вывернуты
            for o in col.objects:
                if o.type == "EMPTY" and o.name.startswith(("Wheel_FL_", "Wheel_FR_")):
                    o.rotation_euler.z += math.radians(18.0)
            root.rotation_euler = (0.0, math.radians(90.0), 0.0)
            root.location = (i * (spec["width"] + 1.5), 0.0, spec["width"] / 2 - 0.02)
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
