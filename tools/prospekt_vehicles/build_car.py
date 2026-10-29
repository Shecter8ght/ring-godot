"""Транспорт «Проспекта»: сборка легковой в Blender — кузов панелями, детали, колёса, салон, варианты.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/build_car.py -- \
        <класс> <выход.blend> [варианты через запятую: intact,open,wreck,burnt]

Класс — ключ specs.CLASSES. Каждый вариант — своя коллекция («Целый», «Открыт», «Битый», «Сгоревший»),
машины стоят рядом вдоль X через 3 м; у каждой свой корень-пустышка (низ колёс — Z = 0, перёд — −Y).
Двери, капот и крышка багажника висят на пустышках-петлях (Hinge_*): повернуть петлю по её оси Z —
деталь откроется (так и сделан вариант «Открыт»).
Материалы — проверочные (REVIEW_*): форма до текстур; производственные UV и отделка — после принятия.
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
import vlib  # noqa: E402 — подключает модули купе (domain, surface, parts)
from specs import CLASSES  # noqa: E402
from surface import Surface  # noqa: E402
from vfield import CarField  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CLS = argv[0] if argv else "sedan"
OUT = Path(argv[1]) if len(argv) > 1 else None
VARIANTS = argv[2].split(",") if len(argv) > 2 else ["intact"]

# Проверочные материалы: цвет, шероховатость, металл
MATERIALS = {
    "paint": ((0.36, 0.40, 0.46), 0.35, 0.0),
    "bumper": ((0.36, 0.40, 0.46), 0.40, 0.0),
    "trim_black": ((0.025, 0.025, 0.025), 0.6, 0.0),
    "trim_gloss_black": ((0.015, 0.015, 0.016), 0.15, 0.0),
    "rubber": ((0.03, 0.03, 0.03), 0.85, 0.0),
    "glass": ((0.05, 0.06, 0.065), 0.03, 0.0),
    "lamp_glass": ((0.80, 0.82, 0.85), 0.02, 0.0),
    "lamp_red": ((0.55, 0.03, 0.03), 0.06, 0.0),
    "lamp_amber": ((0.85, 0.45, 0.05), 0.08, 0.0),
    "lamp_inner": ((0.30, 0.30, 0.31), 0.25, 0.8),
    "lamp_red_inner": ((0.25, 0.01, 0.01), 0.3, 0.3),
    "chrome": ((0.8, 0.8, 0.8), 0.1, 1.0),
    "mesh_black": ((0.01, 0.01, 0.01), 0.7, 0.0),
    "plate": ((0.92, 0.92, 0.90), 0.4, 0.0),
    "liner": ((0.035, 0.035, 0.035), 0.9, 0.0),
    "steel_dark": ((0.12, 0.12, 0.13), 0.45, 0.8),
    "rim_steel": ((0.30, 0.30, 0.31), 0.4, 0.8),
    "rim_alloy": ((0.55, 0.56, 0.58), 0.3, 1.0),
    "hubcap": ((0.45, 0.46, 0.48), 0.35, 0.6),
    "brake": ((0.35, 0.35, 0.36), 0.45, 1.0),
    "interior": ((0.06, 0.06, 0.065), 0.75, 0.0),
    "seat": ((0.08, 0.08, 0.085), 0.85, 0.0),
    "carpet": ((0.03, 0.03, 0.03), 0.95, 0.0),
    "headliner": ((0.35, 0.34, 0.32), 0.9, 0.0),
    "paint_inner": ((0.33, 0.37, 0.43), 0.5, 0.0),
    "burnt": ((0.09, 0.075, 0.065), 0.9, 0.3),
    "burnt_light": ((0.30, 0.27, 0.24), 0.9, 0.2),
    "rust": ((0.25, 0.12, 0.06), 0.85, 0.2),
    "ash": ((0.20, 0.19, 0.18), 0.95, 0.0),
    "glass_broken": ((0.05, 0.06, 0.065), 0.05, 0.0),
    "display": ((0.02, 0.025, 0.02), 0.1, 0.0),
    "bumper_plastic": ((0.06, 0.06, 0.065), 0.6, 0.0),
    "floor_rubber": ((0.12, 0.12, 0.12), 0.85, 0.0),
    "seat_plastic": ((0.10, 0.16, 0.30), 0.5, 0.0),
    "rail_yellow": ((0.75, 0.55, 0.05), 0.4, 0.3),
    "lamp_blue": ((0.04, 0.12, 0.70), 0.06, 0.0),      # колпаки маячков (скорая, полиция)
    "sign_plastic": ((0.86, 0.80, 0.42), 0.35, 0.0),   # плафон такси
}
TRANSPARENT = {"glass": 0.25, "lamp_glass": 0.15, "lamp_red": 0.6, "glass_broken": 0.35, "lamp_blue": 0.6}


def material(name: str) -> bpy.types.Material:
    m = bpy.data.materials.get("REVIEW_" + name)
    if m:
        return m
    rgb, rough, metal = MATERIALS.get(name, ((0.5, 0.5, 0.5), 0.5, 0.0))
    m = bpy.data.materials.new("REVIEW_" + name)
    m.diffuse_color = (*rgb, 1.0)
    m.roughness = rough
    m.metallic = metal
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if name in TRANSPARENT:
        a = TRANSPARENT[name]
        m.diffuse_color = (*rgb, a)
        b.inputs["Alpha"].default_value = a
        try:
            m.surface_render_method = "BLENDED"
        except AttributeError:
            m.blend_method = "BLEND"
    return m


def make_mesh(name: str, mat: str, V, F) -> bpy.types.Mesh:
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in V], [], [tuple(int(i) for i in f) for f in F])
    me.validate()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(material(mat))
    return me


def link(name: str, me: bpy.types.Mesh, col: bpy.types.Collection, parent=None) -> bpy.types.Object:
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def build_kit(spec: dict):
    """Все детали машины в одном положении (закрыто): список (имя, материал, V, F, узел), петли, швы."""
    import carbody
    import carparts as cp

    t0 = time.time()
    field = CarField(spec)
    surf = Surface(field)
    views = vlib.make_views(spec)
    parts, S = carbody.build(surf, field, spec, views)
    if carbody.DEBUG:
        dbg = {}
        for i, (name, view, outer, holes) in enumerate(carbody.DEBUG):
            print("  НЕ СОБРАНА:", name, view)
            dbg[f"{i}_{name}_{view}_outer"] = outer
            for j, hh in enumerate(holes):
                dbg[f"{i}_{name}_{view}_hole{j}"] = hh
        if OUT:
            np.savez(str(OUT.with_suffix(".debug.npz")), **dbg)
    print(f"панели: {len(parts)}, {time.time() - t0:.1f} с")
    lay = spec["lay"]
    kit = list(parts)

    def both(name, mat, mesh, group="body"):
        kit.append((name + "_L", mat, mesh[0], mesh[1], group + ("l" if group != "body" else "")))
        Vm, Fm = vlib.mirror_mesh(mesh[0], mesh[1])
        kit.append((name + "_R", mat, Vm, Fm, group + ("r" if group != "body" else "")))

    # --- низ: подкрылки, днище, выхлоп
    yf, yr = spec["wheel_y"]
    for nm, yc in (("F", yf), ("R", yr)):
        both(f"Liner_{nm}", "liner", cp.wheel_liner(yc, spec["wheel_z"], spec["arch_r"] + 0.012, spec["well_x"],
                                                    spec["width"] / 2 - 0.015))
    kit.append(("Under_Tray", "liner", *cp.under_tray(field, spec), "body"))
    ex, tip = cp.exhaust(spec)
    kit.append(("Exhaust", "steel_dark", *ex, "body"))
    kit.append(("Exhaust_Tip", "chrome", *tip, "body"))
    # --- фары, фонари, решётка, номера
    back, lens, refl, amber = cp.headlamp_inner(surf, views, S["_lamp_loop"])
    both("Headlamp_Back", "lamp_inner", back)
    both("Headlamp_Lens", "lamp_glass", lens)
    both("Headlamp_Reflector", "chrome", refl)
    if len(amber[0]):
        both("Headlamp_Turn", "lamp_amber", amber)
    tb, td = cp.taillamp_inner(surf, views, S["_tl_loop"])
    both("Taillamp_Back", "lamp_red_inner", tb)
    both("Taillamp_Divider", "chrome", td)
    for item in cp.grille_parts(surf, views, S, lay):
        kit.append(item)
    pf = views["front"].lift(surf, np.array([lay["plate_f"]]))[0]
    nf = surf.normal(pf[None])[0]
    nf[2] = 0
    kit.append(("Plate_Front", "plate", *cp.plate(pf + nf * 0.006, nf), "body"))
    pr_loop = S["_plate_r"]
    floor_loop = vlib.loop_on_surface(surf, views["rr"], pr_loop, 0.012, 0.012, True)
    kit.append(("Plate_Recess", "bumper", *vlib_backing(surf, views["rr"], floor_loop, 0.032), "body"))
    pc = pr_loop.mean(0)
    pc = views["rear"].lift(surf, np.array([[0.0, pc[2]]]))[0]
    kit.append(("Plate_Rear", "plate", *cp.plate(pc + np.array([0, -0.026, 0]), np.array([0, 1.0, 0])), "body"))
    # --- зеркала, ручки, дворники, уплотнители, антенна
    housing, glass, arm = cp.mirror(surf, views, lay["mirror_at"], spec)
    both("Mirror_Housing", "paint", housing, "door_f")
    both("Mirror_Glass", "chrome", glass, "door_f")
    both("Mirror_Arm", "trim_black", arm, "door_f")
    for grp, (y0, y1) in (("door_f", lay["handle_f"]), ("door_r", lay["handle_r"])):
        bar, cup = cp.handle(surf, views, y0, y1, lay["handle_z"])
        both("Handle_" + grp[-1].upper(), "paint", bar, grp)
        both("Handle_Cup_" + grp[-1].upper(), "trim_black", cup, grp)
    for nm, (a, b_, c) in lay["wipers"].items():
        kit.append((f"Wiper_{nm}", "trim_black", *cp.wiper(surf, views, a, b_, c), "body"))
    for grp, key in (("door_f", "belt_f_parts"), ("door_r", "belt_r_parts")):
        A, B, C = S[key]
        belt = np.vstack([A, B[1:], C[1:]])
        both("Belt_Seal_" + grp[-1].upper(), "rubber", cp.seal_along(surf, belt[2:-2], 0.012, 0.009, 0.0, r=0.004), grp)
    for grp, key in (("door_f", "_win_f"), ("door_r", "_win_r")):
        W = S[key]
        both("Window_Seal_" + grp[-1].upper(), "rubber", cp.seal_along(surf, W, 0.010, 0.004, 0.0, r=0.0018), grp)
    # накладки стойки B: чёрный глянец на рамках обеих дверей
    bu = S["b_up"]
    for grp, dy in (("door_f", -0.024), ("door_r", 0.024)):
        line = surf.project(bu + np.array([0, dy, 0]))[3:-3]
        both("B_Applique_" + grp[-1].upper(), "trim_gloss_black", cp.seal_along(surf, line, 0.038, 0.0015, 0.0, r=0.0007), grp)
    kit.append(("Antenna", "trim_black", *cp.antenna(surf, views, lay["antenna_y"]), "body"))
    # --- салон, обивка дверей, проёмы, багажник
    for item in cp.interior(field, spec, S):
        kit.append(item)
    for name, mat, V, F, grp in cp.door_cards(surf, views, S, spec, field):
        both(name, mat, (V, F), grp)
    for name, mat, V, F, grp in cp.door_jambs(surf, views, S, spec):
        both(name, mat, (V, F), grp)
    roof = [p for p in kit if p[0] == "Roof"][0]
    nrm = surf.normal(roof[2])
    kit.append(("Headliner", "headliner", roof[2] - nrm * 0.03, [f[::-1] for f in roof[3]], "body"))
    for item in cp.trunk_parts(surf, views, S, spec, field):
        kit.append(item)
    if spec.get("roof_rails"):
        both("Roof_Rail", "trim_black", cp.roof_rail(surf, views, S, spec))
    if "_quarter_win" in S:
        both("Quarter_Seal", "rubber", cp.seal_along(surf, np.vstack([S["_quarter_win"], S["_quarter_win"][:1]]), 0.010, 0.004,
                                                     0.0, r=0.0018))
    if spec["rear_style"] == "hatch":
        kit.append(("Spoiler", "paint", *cp.spoiler(surf, views, S), "lid"))
    if spec.get("side_steps"):
        both("Side_Step", "trim_black", cp.side_step(spec, field))
    if spec.get("arch_flares"):
        for nm, mesh in cp.arch_flares(surf, views, S, spec):
            both(nm, "trim_black", mesh)
    if spec.get("frame_rails"):
        for nm, mat, mesh in cp.chassis(spec, field):
            kit.append((nm, mat, *mesh, "body"))
    if spec.get("spare_on_door"):
        for nm, mat, mesh in cp.spare_wheel(spec, S, surf):
            kit.append((nm, mat, *mesh, "lid"))
    if spec["rear_style"] != "sedan":
        kit.append(("Wiper_Rear", "trim_black", *cp.rear_wiper(surf, views, S, spec), "lid"))
    hinges = compute_hinges(surf, S, spec)
    print(f"деталей: {len(kit)}, {time.time() - t0:.1f} с")
    return kit, hinges, S, (field, surf, views)


def vlib_backing(surf, view, loop3, depth):
    import parts as pt
    return pt.backing(surf, view, loop3, depth)


def compute_hinges(surf, S: dict, spec: dict) -> dict:
    """Оси петель: передняя дверь — по передней кромке, задняя — по стыку дверей, крышка — по переднему краю."""
    lay = spec["lay"]

    def on_curve(P, z):
        return P[np.argmin(np.abs(P[:, 2] - z))]

    h = {}
    for grp, P in (("door_fl", S["door_front"].P), ("door_rl", S["b_low"])):
        a, b = on_curve(P, 0.45), on_curve(P, 0.85)
        a, b = a - np.array([0.025, -0.01, 0]), b - np.array([0.025, -0.01, 0])
        h[grp] = (a, b - a, -1.0)                 # левая дверь открывается поворотом против оси
        h[grp[:-1] + "r"] = (a * [-1, 1, 1], (b - a) * [-1, 1, 1], 1.0)
    if "_lid_loop" in S and spec["rear_style"] == "suv":
        # распашная задняя дверь: петли справа (−X), ось вертикальная у правой кромки
        L = S["_lid_loop"]
        edge = L[np.argsort(L[:, 0])[:30]]
        a = np.array([edge[:, 0].mean() + 0.03, edge[:, 1].mean() + 0.03, edge[:, 2].min()])
        h["lid"] = (a, np.array([0, 0, 1.0]), 1.0)
    elif "_lid_loop" in S:
        L = S["_lid_loop"]
        front = L[np.argsort(L[:, 1])[:20]].mean(0)
        a = np.array([0.0, front[1] + 0.02, front[2] - 0.03])
        h["lid"] = (a, np.array([1.0, 0, 0]), 1.0)
    return h


def place_wheels(spec: dict, col, root, wheel_sets: dict, variant: str, wcfg: dict | None = None):
    """Четыре колеса: левые — как есть (ось +X наружу), правые — развёрнуты на 180°.

    wheel_sets: место (FL, FR, RL, RR) → [(имя, сетка)]; wcfg: z — высота центра, steer — поворот передних (°).
    """
    wcfg = wcfg or {}
    z = wcfg.get("z", spec["wheel_z"])
    for nm, y in (("F", spec["wheel_y"][0]), ("R", spec["wheel_y"][1])):
        for side in (1, -1):
            key = nm + ("L" if side > 0 else "R")
            hub = bpy.data.objects.new(f"Wheel_{key}_{variant}", None)
            hub.empty_display_size = 0.2
            col.objects.link(hub)
            hub.parent = root
            hub.location = (side * spec["track"] / 2, y, z)
            steer = math.radians(wcfg.get("steer", 0.0)) if nm == "F" else 0.0
            hub.rotation_euler = (0, 0, (0 if side > 0 else math.pi) + steer)
            for pname, me in wheel_sets[key]:
                link(f"{pname}_{key}_{variant}", me, col, hub)


def assemble(kit, hinges, spec: dict, variant: str, title: str, offset_x: float, open_cfg: dict | None = None,
             wheel_sets=None, wcfg=None):
    col = bpy.data.collections.new(title)
    bpy.context.scene.collection.children.link(col)
    root = bpy.data.objects.new(f"{spec['name']}_{variant}", None)
    root.empty_display_type = "ARROWS"
    col.objects.link(root)
    root.location = (offset_x, 0, 0)
    groups = {}
    for name, mat, V, F, grp in kit:
        groups.setdefault(grp, []).append((name, mat, V, F))
    hinge_obs = {}
    for grp, (a, axis, sgn) in hinges.items():
        e = bpy.data.objects.new(f"Hinge_{grp}_{variant}", None)
        e.empty_display_type = "SINGLE_ARROW"
        e.empty_display_size = 0.3
        col.objects.link(e)
        e.parent = root
        q = Vector(axis).normalized().to_track_quat("Z", "Y")
        e.matrix_basis = Matrix.Translation(Vector(a)) @ q.to_matrix().to_4x4()
        hinge_obs[grp] = (e, sgn)
    bpy.context.view_layer.update()
    for grp, items in groups.items():
        parent = root
        if grp in hinge_obs:
            parent = hinge_obs[grp][0]
        for name, mat, V, F in items:
            ob = link(f"{name}_{variant}", make_mesh(name, mat, V, F), col, parent)
            if parent is not root:
                ob.matrix_parent_inverse = parent.matrix_basis.inverted()
    if wheel_sets:
        place_wheels(spec, col, root, wheel_sets, variant, wcfg)
    if open_cfg:
        for grp, deg in open_cfg.items():
            if grp in hinge_obs:
                e, sgn = hinge_obs[grp]
                e.rotation_mode = "QUATERNION"
                base = e.matrix_basis.copy()
                rot = Matrix.Rotation(math.radians(deg) * sgn, 4, "Z")
                e.matrix_basis = base @ rot
    return col, root


def _drop(kit, names: tuple) -> list:
    return [p for p in kit if not p[0].startswith(names)]


def _apply(kit, fn, names: tuple | None = None) -> list:
    """Деформация fn(V) для деталей с именами из names (None — для всех)."""
    out = []
    for name, mat, V, F, grp in kit:
        if names is None or name.startswith(names):
            V = fn(V)
        out.append((name, mat, V, F, grp))
    return out


def make_wreck(kit, spec: dict, field, surf, views, S):
    """«Битый»: удар спереди слева, капот домиком, провисший угол бампера, разбитые левая фара и правое
    переднее стекло (осколки в рамке), трещина лобового, вмятина на правой задней двери, сорванное левое
    зеркало, спущенное переднее левое колесо (машина присела на угол), передние колёса вывернуты."""
    import vdamage as vd

    lay = spec["lay"]
    nz = vd.Noise3(11)
    hw = spec["width"] / 2
    kit = _drop(kit, ("Headlamp_L", "Headlamp_Lens_L", "Headlamp_Turn_L", "Glass_Door_F_R", "Mirror_Housing_L",
                      "Mirror_Glass_L"))
    kit = _apply(kit, lambda V: vd.droop(V, 0.20, 1.0, 0.10), ("Bumper_F", "Grille", "Intake", "Fog", "Plate_Front"))
    kit = _apply(kit, lambda V: vd.hood_buckle(V, lay["hood_front_y"] + 0.15, lay["cowl_y"] - 0.10, 0.075, 1.0, hw),
                 ("Hood",))
    kit = _apply(kit, lambda V: vd.crash_front(V, spec, 0.24, 1.0, nz, 0.012))
    # вмятина на правой задней двери, трещина лобового — пятном справа внизу
    c = views["side_r"].lift(surf, np.array([[0.62, 0.70]]))[0]
    kit = _apply(kit, lambda V: vd.dent(V, c, 0.24, 0.045, (1.0, 0, 0)), ("Door_R_Skin_R", "Handle_R_R", "Handle_Cup_R_R"))
    ws_pt = views["top"].lift(surf, np.array([[-0.32, float(field.ws(lay["ws_base_z"] + 0.12))]]))[0]
    kit = _apply(kit, lambda V: vd.crack_glass(V, ws_pt, 0.20, 0.018, -surf.normal(ws_pt[None])[0]), ("Glass_Windshield",))
    # осколки в рамке правого переднего окна
    W = S["_win_f"].copy()
    W[:, 0] *= -1
    nrm = surf.normal(W)
    cen = W.mean(0)
    inward = cen - W
    inward -= nrm * (inward * nrm).sum(1, keepdims=True)
    inward /= np.maximum(np.linalg.norm(inward, axis=1, keepdims=True), 1e-9)
    sv, sf = vd.shards_along(W - nrm * 0.008, inward, nrm, 5, 0.09)
    kit.append(("Glass_Shards_Door_F_R", "glass_broken", sv, sf, "door_fr"))
    # машина присела на переднее левое (спущенное) колесо: кузов наклонён к этому углу
    yf, yr = spec["wheel_y"]
    drop = 0.05

    def corner(V):
        wx = np.clip((V[:, 0] + hw) / (2 * hw), 0, 1)
        wy = np.clip((yr - V[:, 1]) / (yr - yf), 0, 1.3)
        out = V.copy()
        out[:, 2] -= drop * wx * wy
        return out
    return _apply(kit, corner)


def make_burnt(kit, spec: dict, field, surf, views, S):
    """«Сгоревший»: стёкла, резина, пластик и обивка сгорели; кузов в окалине, крыша просела, лист повело;
    передний бампер сгорел (видно брус и рамку радиатора), задний потёк; салон — каркасы; машина на дисках."""
    import carparts as cp
    import vdamage as vd

    lay = spec["lay"]
    nz = vd.Noise3(23)
    gone = ("Glass_", "Headlamp_L", "Headlamp_R", "Headlamp_Lens", "Headlamp_Turn", "Taillamp_L", "Taillamp_R",
            "Fog_Lens", "Mirror_Housing", "Mirror_Glass", "Wiper_", "Belt_Seal", "Window_Seal", "Grille_Bars",
            "Grille_Surround", "Grille_Back", "Intake_Bar", "Intake_Back", "Seat_", "Headrest_", "Steering_",
            "Dashboard", "Instrument_Hood", "Center_", "Console", "Floor", "Headliner", "Door_Card", "Parcel_Shelf",
            "Visor_", "Mirror_Inner", "Trunk_Tub", "Trunk_Wall", "Liner_", "Handle_L", "Handle_R", "Handle_F",
            "B_Applique", "Cowl", "Bumper_F", "Antenna", "Plate_Front", "Fog_Back", "Spare_Tire", "Spare_Cover",
            "Cargo_Cover", "Quarter_Seal", "Flare_")
    kit = _drop(kit, gone)
    swap = {"paint": "burnt", "bumper": "burnt", "paint_inner": "burnt", "lamp_inner": "burnt", "lamp_red_inner": "burnt",
            "chrome": "burnt", "trim_black": "burnt", "liner": "burnt", "steel_dark": "rust", "plate": "burnt_light",
            "trim_gloss_black": "burnt", "interior": "burnt", "rubber": "burnt", "rim_steel": "rust", "seat": "burnt"}
    kit = [(n, swap.get(m, m), V, F, g) for n, m, V, F, g in kit]
    out = []
    for name, mat, V, F, grp in kit:
        if name.startswith("Roof"):
            V = vd.sag(V, (0.0, (lay["a_top_y"] + lay["c_top_y"]) / 2), 0.75, 0.045)
        if name.startswith(("Hood", "Roof", "Trunk_Lid", "Door_", "Bodyside", "Fender")):
            V = vd.warp(V, nz, 0.005, 0.22, vd.vertex_normals_fast(V, F))
        if name.startswith("Bumper_R"):
            V = vd.melt(V, nz, 0.95, 0.07)
        out.append((name, mat, V, F, grp))
    kit = out
    beam, frame, rad = cp.crash_beam(spec, field)
    kit += [("Crash_Beam", "rust", *beam, "body"), ("Radiator_Frame", "burnt", *frame, "body"),
            ("Radiator_Burnt", "burnt", *rad, "body")]
    kit += cp.burnt_interior(field, spec, S)
    # без шин машина легла на диски: кузов ниже на разницу высот
    rim_r = spec["rim_d_in"] * 0.0127
    dz = spec["wheel_z"] - (rim_r + 0.013)
    kit = _apply(kit, lambda V: V - np.array([0, 0, dz]))
    return kit, dz


def main() -> None:
    import carparts as cp
    import vdamage as vd

    spec = CLASSES[CLS]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    kit, hinges, S, (field, surf, views) = build_kit(spec)
    wparts = cp.wheel_parts(spec)
    std = [(n, make_mesh("W_" + n, m, V, F)) for n, m, V, F in wparts]
    titles = {"intact": "Целый", "open": "Открыт", "wreck": "Битый", "burnt": "Сгоревший"}
    for i, v in enumerate(VARIANTS):
        sets = {k: std for k in ("FL", "FR", "RL", "RR")}
        wcfg, cfg, k2, h2 = None, None, kit, dict(hinges)
        if v == "open":
            cfg = spec.get("open_cfg")
        elif v == "wreck":
            k2 = make_wreck(kit, spec, field, surf, views, S)
            flat = []
            for n, m, V, F in wparts:
                if n == "Tire":
                    V = vd.flat_tire(V, spec["tire_r"], 0.05)
                flat.append((n, make_mesh("WF_" + n, m, V, F)))
            sets["FL"] = flat
            wcfg = {"steer": spec.get("wreck_steer", 14.0)}
            cfg = spec.get("wreck_open")
        elif v == "burnt":
            k2, dz = make_burnt(kit, spec, field, surf, views, S)
            keep = ("Rim_Barrel", "Rim_Face", "Rim_Holes", "Brake_Disc", "Caliper", "Rim_Spokes", "Rim_Hub", "Lug_Nuts")
            recolor = {"rim_steel": "rust", "rim_alloy": "burnt_light", "brake": "rust", "steel_dark": "rust"}
            rims = [(n, make_mesh("WB_" + n, recolor.get(m, m), V, F)) for n, m, V, F in wparts if n.startswith(keep)]
            sets = {k: rims for k in sets}
            wcfg = {"z": spec["wheel_z"] - dz}
            h2 = {g: (a - np.array([0, 0, dz]), ax, sg) for g, (a, ax, sg) in hinges.items()}
            cfg = spec.get("burnt_open")
        assemble(k2, h2, spec, v, titles[v], i * 3.2, cfg, sets, wcfg)
    if OUT:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        bpy.context.preferences.filepaths.save_version = 0      # без .blend1 рядом с выдачей (только в этом запуске)
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
        print("сохранено:", OUT)


if __name__ == "__main__":
    main()
