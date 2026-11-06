# «Осока», тепловизионный прицел: проверка сборки — пересечения деталей прицела с «Осокой» и между собой (BVH),
# зазоры у лапы (ремень, пряжка, основание, накладка), положения переключателя, габарит и треугольники.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <сборка.blend> --python-exit-code 1 --python tools/osoka/sight_check.py
import sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

MM = 0.001
# намеренные стыки (касание по плоскости, посадка с натягом в пределах долей мм)
ALLOWED = {
    ("Thermal_bracket", "Mount_plate"), ("Thermal_bracket", "Saddle_body"), ("Thermal_bracket", "Thermal_rail"),
    ("Thermal_rail", "Thermal_body"), ("Thermal_obj_housing", "Thermal_body"),
    ("Thermal_focus_ring", "Thermal_obj_housing"), ("Thermal_obj_bezel", "Thermal_focus_ring"),
    ("Thermal_batt_housing", "Thermal_body"), ("Thermal_batt_cap", "Thermal_batt_housing"),
    ("Thermal_batt_cap_face", "Thermal_batt_cap"), ("Thermal_day_bezel", "Thermal_body"),
    ("Thermal_eye_tube", "Thermal_body"), ("Thermal_diopter_ring", "Thermal_eye_tube"), ("Thermal_diopter_ring", "Thermal_body"), ("Thermal_eye_screw", "Thermal_eye_tube"), ("Thermal_eyecup", "Thermal_eye_tube"), ("Thermal_conn_", "Thermal_body"), ("Thermal_conn_", "Thermal_conn_"), ("Thermal_batt_knob", "Thermal_batt_cap_face"), ("Thermal_batt_screw", "Thermal_batt_knob"),
    ("Thermal_eyecup", "Thermal_diopter_ring"), ("Thermal_eye_lens", "Thermal_eyecup"),
    ("Thermal_key_pad", "Thermal_body"), ("Thermal_switch_base", "Thermal_body"),
    ("Thermal_switch_lever", "Thermal_switch_base"), ("Thermal_switch_knob", "Thermal_switch_lever"),
    ("Thermal_switch_screw", "Thermal_switch_lever"), ("Thermal_foot_knob", "Thermal_bracket"),
    ("Thermal_foot_knob_end", "Thermal_foot_knob"), ("Thermal_rail_knob", "Thermal_bracket"),
    ("Thermal_rail_knob_end", "Thermal_rail_knob"), ("Thermal_obj_lens", "Thermal_obj_bezel"),
    ("Thermal_day_lens", "Thermal_day_bezel"), ("Thermal_cap_lug", "Thermal_cap_ring"), ("Thermal_cap_pin", "Thermal_cap_"),
    ("Thermal_cap_web", "Thermal_cap"), ("Thermal_cap_knuckle", "Thermal_cap"), ("Thermal_cap_tab", "Thermal_cap"),
    ("Thermal_cap_ring", "Thermal_obj_bezel"),
}


def allowed(a, b):
    for x, y in ALLOWED:
        if (a.startswith(x) and b.startswith(y)) or (a.startswith(y) and b.startswith(x)):
            return True
    if a.startswith(("Thermal_key", "Thermal_bracket_screw")) or \
            b.startswith(("Thermal_key", "Thermal_bracket_screw")):
        return True      # кнопки в рамках и площадке, винты в крышке и площадке — посадка
    return False


def bvh(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    vs = [oe.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    t = BVHTree.FromPolygons(vs, polys)
    lo = Vector(map(min, *vs)) if vs else Vector()
    hi = Vector(map(max, *vs)) if vs else Vector()
    oe.to_mesh_clear()
    return t, lo, hi, vs


def main():
    sc = bpy.context.scene
    for o in bpy.data.objects:
        if o.name.endswith("_Controls"):
            o.update_tag()
    sc.frame_set(1)
    dg = bpy.context.evaluated_depsgraph_get()
    th = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Thermal_")]
    other = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("Thermal_")]
    T = {o.name: bvh(o, dg) for o in th + other}
    errors = []
    checks = 0
    lo = Vector((1e9,) * 3); hi = -lo
    tri = 0
    for o in th:
        t, a, b, _ = T[o.name]
        lo = Vector(map(min, lo, a)); hi = Vector(map(max, hi, b))
        oe = o.evaluated_get(dg); tri += len(oe.to_mesh().loop_triangles); oe.to_mesh_clear()
    print(f"SIZE мм: X {(hi.x - lo.x) / MM:.1f}  Y {(hi.y - lo.y) / MM:.1f}  Z {(hi.z - lo.z) / MM:.1f}   TRIS {tri}")
    names = [o.name for o in th] + [o.name for o in other]
    for i, a in enumerate([o.name for o in th]):
        ta, la, ha, _ = T[a]
        for b in names[i + 1:]:
            tb, lb, hb, _ = T[b]
            if any(ha[k] < lb[k] - 1e-4 or hb[k] < la[k] - 1e-4 for k in range(3)):
                continue
            checks += 1
            pairs = ta.overlap(tb)
            if pairs and not allowed(a, b):
                errors.append(f"пересечение {a} × {b}: {len(pairs)} пар граней")
    # зазоры (мм) — ближайшие точки вершин a к поверхности b
    def gap(a, b):
        # в обе стороны: у большой плоской грани мало вершин — по ним одним зазор завышен
        d = 1e9
        for x, y in ((a, b), (b, a)):
            tb = T[y][0]
            d = min(d, min((tb.find_nearest(p)[3] for p in T[x][3]), default=1e9))
        return d / MM
    for a, b, need in (("Thermal_bracket", "Sling_strap", 1.0), ("Thermal_bracket", "Sling_buckle", 0.5),
                       ("Thermal_rail", "Rear_sight_leaf", 1.0), ("Thermal_rail", "Rear_sight_indicator", 1.0),
                       ("Thermal_body", "Rear_sight_indicator", 3.0),
                       ("Thermal_foot_knob", "Saddle_body", 0.3), ("Thermal_body", "Rear_sight_leaf", 3.0),
                       ("Thermal_eyecup", "Rear_sight_leaf", 3.0), ("Thermal_bracket", "Rear_sight_leaf", 1.0),
                       ("Thermal_bracket", "Rear_sight_indicator", 1.0), ("Thermal_batt_cap", "Lid_top", 3.0),
                       ("Thermal_obj_bezel", "Lid_top", 3.0), ("Thermal_bracket", "Sling_loop_wire", 1.0),
                       ("Thermal_bracket", "Lid_mid", 1.0), ("Thermal_batt_cap", "Thermal_focus_ring", 0.3)):
        if a in T and b in T:
            checks += 1
            g = gap(a, b)
            ok = g >= need
            print(f"GAP {a} — {b}: {g:.2f} мм {'ok' if ok else 'МАЛО (нужно ≥ ' + str(need) + ')'}")
            if not ok:
                errors.append(f"зазор {a} — {b} {g:.2f} < {need}")
    # ремень, пряжка, сложенный целик внутри деталей прицела (и наоборот): вершина одной детали под поверхностью другой
    # — пересечение граней этого не ловит, если кромка ремня целиком ушла в лапу
    def inside_count(a, b):
        _, la, ha, va = T[a]
        tb, lb, hb, _ = T[b]
        n = 0
        worst = 0.0
        for p in va:
            if any(p[k] < lb[k] - 2e-3 or p[k] > hb[k] + 2e-3 for k in range(3)):
                continue
            loc, nor, _, dist = tb.find_nearest(p)
            if loc is not None and (p - loc).dot(nor) < -1e-5:
                n += 1
                worst = max(worst, dist / MM)
        return n, worst
    for a in ("Sling_strap", "Sling_buckle", "Sling_buckle_bar", "Rear_sight_leaf", "Rear_sight_indicator", "Mount_plate"):
        for b in [o.name for o in th]:
            if a not in T or b not in T:
                continue
            checks += 1
            for x, y in ((a, b), (b, a)):
                n, w = inside_count(x, y)
                if n and not (allowed(x, y) and w < 0.6):
                    errors.append(f"{n} вершин {x} внутри {y} (до {w:.2f} мм)")
    # раструб наглазника против места глаза с открытым прицелом
    cup = T.get("Thermal_eyecup")
    if cup:
        print(f"EYECUP раструб x {cup[1].x / MM:.1f}…, глаз с целиком в игре x ≈ 1070.6 (хват 1258.6 − ads_z 188)")
    # переключатель: три положения без пересечения рычажка с корпусом
    ctrl = bpy.data.objects.get("THERMAL_Controls")
    if ctrl is not None:
        for m in (0.0, 0.5, 1.0):
            ctrl["mode"] = m
            ctrl.update_tag(); sc.frame_set(1)
            dg = bpy.context.evaluated_depsgraph_get()
            tl = bvh(bpy.data.objects["Thermal_switch_lever"], dg)[0]
            tk = bvh(bpy.data.objects["Thermal_switch_knob"], dg)[0]
            tb = bvh(bpy.data.objects["Thermal_body"], dg)[0]
            checks += 1
            if tl.overlap(tb) or tk.overlap(tb):
                errors.append(f"рычажок в корпусе при mode {m}")
        ctrl["mode"] = 1.0
        # крышка объектива: закрыта, на полпути, откинута — без пересечений с прицелом и «Осокой»
        lid_parts = ("Thermal_cap", "Thermal_cap_web", "Thermal_cap_knuckle", "Thermal_cap_tab")
        for cval in (0.0, 0.25, 0.5, 0.75, 1.0):
            ctrl["cap"] = cval
            ctrl.update_tag(); sc.frame_set(1)
            dg = bpy.context.evaluated_depsgraph_get()
            tl = {n: bvh(bpy.data.objects[n], dg)[0] for n in lid_parts}
            for o in bpy.data.objects:
                if o.type != "MESH" or o.name in lid_parts or o.name == "Thermal_cap_pin":
                    continue
                if o.name not in T:
                    continue
                tb, lb, hb, _ = T[o.name]
                if hb.x < 1.2 and o.name.startswith("Thermal_") is False:
                    continue      # «Осока» позади объектива — крышка до неё не достаёт
                for n, t in tl.items():
                    checks += 1
                    if t.overlap(tb) and not allowed(n, o.name):
                        errors.append(f"крышка {cval}: {n} × {o.name}")
        ctrl["cap"] = 0.0
        ctrl.update_tag(); sc.frame_set(1)
    print(f"CHECKS {checks}  ERRORS {len(errors)}")
    for e in errors:
        print("ERROR", e)
    print("STATUS", "PASS" if not errors else "FAIL")


main()
