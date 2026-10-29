# AR-15: проверка пересечений деталей в положениях управления (деревья BVH по оценённым сеткам в мире).
# blender -b <file.blend> --python tools/ar15/check_overlaps.py
# Печатает пары с пересекающимися гранями; касание плоскостями может давать единичные пары — смотреть крупно.
import bpy
from mathutils.bvhtree import BVHTree

PAIRS = [
    ("Bolt", "Magazine_body"), ("Bolt", "Magazine_round_00"), ("Bolt_carrier", "Magazine_body"),
    ("Bolt_carrier", "Magazine_round_00"), ("Bolt_carrier", "Upper_receiver"), ("Bolt", "Upper_receiver"),
    ("Bolt", "Barrel_extension"), ("Bolt_carrier", "Barrel_extension"), ("Magazine_body", "Lower_receiver"),
    ("Magazine_body", "Upper_receiver"), ("Magazine_round_00", "Upper_receiver"), ("Magazine_round_01", "Upper_receiver"),
    ("Hammer", "Bolt_carrier"), ("Hammer", "Lower_receiver"), ("Trigger", "Lower_receiver"), ("Charging_handle", "Upper_receiver"),
    ("Charging_handle", "Gas_key"), ("Gas_tube", "Gas_key"), ("Gas_tube", "Charging_handle"), ("Gas_tube", "Upper_receiver"),
    ("Cam_pin", "Upper_receiver"), ("Gas_key", "Upper_receiver"), ("Pistol_grip", "Lower_receiver"), ("Stock_body", "Buffer_tube"),
    ("Buffer", "Buffer_tube"), ("Bolt_carrier", "Buffer"), ("Front_sight_base", "Handguard_rail"), ("Rear_sight_base", "Upper_rail"),
    ("Muzzle_brake", "Barrel"), ("Suppressor_body", "Muzzle_brake"), ("Handguard", "Barrel_nut"), ("Handguard", "Gas_block"),
    ("Handguard", "Upper_receiver"), ("Handguard", "Lower_receiver"), ("Forward_assist", "Upper_receiver"), ("Forward_assist", "Bolt_carrier"), ("Bolt_catch", "Bolt"), ("Bolt_catch", "Lower_receiver"), ("Bolt_catch", "Upper_receiver"),
    ("Mag_catch", "Magazine_body"), ("Mag_catch", "Lower_receiver"), ("Selector", "Trigger"), ("Dust_cover", "Upper_receiver"),
    ("Dust_cover", "Lower_receiver"), ("Upper_receiver", "Lower_receiver"), ("Takedown_pin", "Upper_receiver"),
    ("Pivot_pin", "Upper_receiver"), ("Disconnector", "Hammer"), ("Buffer_retainer", "Upper_receiver"),
    ("Buffer_retainer", "Buffer_tube"), ("Stock_lock_pin", "Buffer_tube"), ("Stock_latch", "Buffer_tube"), ("Stock_body", "Buffer_tube"), ("Suppressor_body", "Handguard"), ("Suppressor_body", "Magazine_body"), ("Rear_sight_leaf", "Rear_sight_base"),
    ("Front_sight_leaf", "Front_sight_base"), ("Bolt_carrier", "Hammer"), ("Extractor", "Barrel_extension"), ("Hammer_spring_L", "Hammer"), ("Hammer_spring_R", "Hammer"), ("Hammer_spring_L", "Trigger"), ("Hammer_spring_R", "Trigger"), ("Trigger_spring_L", "Trigger"), ("Trigger_spring_R", "Trigger"), ("Trigger_spring_L", "Lower_receiver"), ("Trigger_spring_R", "Lower_receiver"), ("Hammer_spring_L", "Lower_receiver"), ("Hammer_spring_R", "Lower_receiver"), ("Hammer_spring_L", "Disconnector"), ("Trigger_spring_L", "Hammer"),
    ("Selector_lever_L", "Upper_receiver"), ("Selector_lever_L", "Lower_receiver"), ("Selector_lever_R", "Lower_receiver"),
    ("QD_swivel", "End_plate"), ("QD_swivel", "Castle_nut"), ("QD_swivel_loop", "QD_swivel"), ("QD_swivel_loop", "End_plate"),
    ("QD_swivel_loop", "Pistol_grip"), ("QD_swivel_loop", "Stock_body"), ("QD_swivel_loop", "Lower_receiver"),
    ("Pistol_grip", "Trigger"),
]
import sys as _sys
_ONLY = (_sys.argv[_sys.argv.index("--") + 1].split(",") if "--" in _sys.argv else None)
STATES = {
    "battery": {},
    "cycle10": {"bolt_carrier": 0.1},
    "cycle30": {"bolt_carrier": 0.3},
    "cycle55": {"bolt_carrier": 0.55},
    "cycle80_catch": {"bolt_carrier": 0.797, "bolt_catch": 1.0},
    "cycle100": {"bolt_carrier": 1.0, "charging_handle": 1.0},
    "open": {"takedown_pin": 1.0, "upper_open": 1.0},
    "stock_out": {"stock": 1.0},
    "sights_down": {"rear_sight": 0.0, "front_sight": 0.0},
    "fired": {"hammer": 0.0, "trigger": 1.0},
    "fa_pressed": {"forward_assist": 1.0},
    "stock_latch_pressed": {"stock_latch": 1.0, "stock": 0.4},
    "suppressor_on": {"suppressor_on": 1.0},
    "safe": {"selector": 0.0},
    "auto": {"selector": 1.0},
}


def bvh(name, dg):
    o = bpy.data.objects.get(name)
    if o is None:
        return None
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    vs = [oe.matrix_world @ v.co for v in me.vertices]
    polys = [tuple(p.vertices) for p in me.polygons]
    t = BVHTree.FromPolygons(vs, polys, all_triangles=False, epsilon=0.0)
    cents = [sum((vs[i] for i in p), vs[p[0]] * 0) / len(p) for p in polys]
    oe.to_mesh_clear()
    return (t, cents)


def main():
    ctrl = bpy.data.objects["AR15_Controls"]
    base = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    for st, vals in STATES.items():
        if _ONLY and st not in _ONLY:
            continue
        for k, v in base.items():
            ctrl[k] = v
        for k, v in vals.items():
            ctrl[k] = v
        ctrl.update_tag()
        bpy.context.scene.frame_set(1)
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        dg.update()
        cache = {}
        bad = []
        for a, b in PAIRS:
            for n in (a, b):
                if n not in cache:
                    cache[n] = bvh(n, dg)
            if cache[a] is None or cache[b] is None:
                continue
            ov = cache[a][0].overlap(cache[b][0])
            if ov:
                cs = [cache[a][1][i] for i, _ in ov]
                lo = [round(min(c[k] for c in cs) * 1000, 1) for k in range(3)]
                hi = [round(max(c[k] for c in cs) * 1000, 1) for k in range(3)]
                bad.append(f"{a}×{b}:{len(ov)} {lo}..{hi}")
        print("STATE", st, "|", "\n   ".join(bad) if bad else "чисто")


main()
