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
    ("Pistol_grip", "Trigger"), ("Pistol_grip", "End_plate"), ("Pistol_grip", "QD_swivel"), ("Pistol_grip", "Castle_nut"),
    ("Pistol_grip", "Buffer_tube"), ("Pistol_grip", "Stock_body"), ("Pistol_grip", "Magazine_body"), ("Grip_screw", "Lower_receiver"),
    ("Grip_screw", "Pistol_grip"),
    ("Rear_sight_aperture", "Rear_sight_leaf"), ("Rear_sight_aperture", "Rear_sight_spring_L"), ("Rear_sight_aperture", "Rear_sight_spring_R"),
    ("Rear_sight_aperture", "Rear_sight_drum"), ("Rear_sight_aperture_pin", "Rear_sight_aperture"), ("Rear_sight_aperture_pin", "Rear_sight_leaf"),
    ("Rear_sight_aperture_pin", "Rear_sight_drum"), ("Rear_sight_spring_L", "Rear_sight_leaf"), ("Rear_sight_spring_R", "Rear_sight_leaf"),
    ("Rear_sight_drum", "Rear_sight_leaf"), ("Rear_sight_drum", "Rear_sight_base"), ("Rear_sight_leaf", "Charging_handle"),
    ("Rear_sight_aperture", "Charging_handle"), ("Rear_sight_base", "Charging_handle"), ("Rear_sight_base", "CH_latch_L"),
    ("Rear_sight_base", "CH_latch_R"), ("Rear_sight_base_bolt", "Rear_sight_base"), ("Rear_sight_base_button", "Rear_sight_base_bolt"),
    ("Rear_sight_base_button", "Rear_sight_base"), ("Rear_sight_base_hinge_pin", "Rear_sight_leaf"), ("Rear_sight_aperture", "Rear_sight_base"),
    ("Front_sight_base_hinge_pin", "Front_sight_leaf"), ("Front_sight_drum", "Front_sight_leaf"), ("Front_sight_post", "Front_sight_leaf"),
    ("Front_sight_post", "Front_sight_drum"), ("Front_sight_base_button", "Front_sight_base_bolt"), ("Front_sight_base_bolt", "Handguard_rail"),
    ("Rear_sight_base_bolt", "Upper_rail"), ("Front_sight_leaf", "Handguard_rail"), ("Front_sight_drum", "Front_sight_base"),
    ("Front_sight_post", "Front_sight_base"), ("Rear_sight_leaf", "Upper_rail"),
    ("Stock_body", "End_plate"), ("Stock_body", "Castle_nut"), ("Stock_body", "QD_swivel"), ("Stock_body", "Buffer"),
    ("Stock_latch", "Stock_body"), ("Stock_lock_pin", "Stock_body"), ("Stock_buttpad", "Stock_body"), ("Stock_latch_axis", "Stock_body"),
    ("Stock_QD_cup_rear_L", "Stock_body"), ("Stock_QD_cup_rear_R", "Stock_body"), ("Stock_QD_cup_front_L", "Stock_body"),
    ("Stock_QD_cup_front_R", "Stock_body"),
    ("CH_latch_L", "Charging_handle"), ("CH_latch_R", "Charging_handle"), ("CH_latch_L", "Upper_receiver"), ("CH_latch_R", "Upper_receiver"),
    ("CH_latch_R", "Forward_assist"), ("CH_latch_L", "End_plate"), ("CH_latch_R", "End_plate"), ("CH_latch_L", "Castle_nut"),
    ("CH_latch_R", "Castle_nut"), ("Charging_handle", "End_plate"), ("Charging_handle", "Castle_nut"), ("Charging_handle", "Rear_sight_base"),
    ("CH_latch_L", "Rear_sight_base"), ("CH_latch_R", "Rear_sight_base"), ("CH_latch_L", "Rear_sight_leaf"), ("CH_latch_R", "Rear_sight_leaf"),
    ("CH_latch_L", "CH_latch_L_pin"), ("CH_latch_R", "CH_latch_R_pin"), ("CH_latch_L", "Upper_rail"), ("CH_latch_R", "Upper_rail"),
    ("Charging_handle", "Forward_assist"), ("CH_latch_L", "Stock_body"), ("CH_latch_R", "Stock_body"),
    ("Magazine_body", "Pistol_grip"), ("Magazine_floorplate", "Lower_receiver"),
    ("Guard_pin", "Lower_receiver"), ("Guard_pin", "Pistol_grip"), ("Pivot_pin", "Lower_receiver"), ("Pivot_pin", "Upper_receiver"),
    ("End_plate", "Lower_receiver"), ("QD_swivel", "Pistol_grip"), ("QD_swivel_loop", "Castle_nut"), ("QD_swivel_loop", "Buffer_tube"),
    ("QD_swivel_loop", "Stock_QD_cup_front_L"), ("Magazine_body", "Bolt_carrier"), ("Magazine_round_00", "Magazine_body"),
    ("Magazine_round_01", "Magazine_body"), ("Rear_sight_spring_L", "Rear_sight_aperture_pin"), ("Rear_sight_spring_R", "Rear_sight_aperture_pin"),
    ("Grip_screw", "Pistol_grip"), ("Barrel_nut", "Upper_receiver"),
    ("Side_rail", "Handguard"), ("Side_rail_screw0", "Side_rail"), ("Side_rail_screw0", "Handguard"), ("Side_rail_tnut0", "Handguard"),
    ("Side_rail_tnut0", "Side_rail_screw0"), ("Side_rail_tnut0", "Barrel"), ("Side_rail_screw1", "Side_rail"), ("Side_rail_screw1", "Handguard"),
    ("Side_rail_tnut1", "Handguard"), ("Side_rail_tnut1", "Side_rail_screw1"), ("Side_rail_tnut1", "Barrel"), ("Side_rail_R", "Handguard"),
    ("Side_rail_R_screw0", "Side_rail_R"), ("Side_rail_R_screw0", "Handguard"), ("Side_rail_R_tnut0", "Handguard"), ("Side_rail_R_tnut0", "Side_rail_R_screw0"),
    ("Side_rail_R_tnut0", "Barrel"), ("Side_rail_R_screw1", "Side_rail_R"), ("Side_rail_R_screw1", "Handguard"), ("Side_rail_R_tnut1", "Handguard"),
    ("Side_rail_R_tnut1", "Side_rail_R_screw1"), ("Side_rail_R_tnut1", "Barrel"), ("Bottom_rail", "Handguard"), ("Bottom_rail_screw0", "Bottom_rail"),
    ("Bottom_rail_screw0", "Handguard"), ("Bottom_rail_tnut0", "Handguard"), ("Bottom_rail_tnut0", "Bottom_rail_screw0"), ("Bottom_rail_tnut0", "Barrel"),
    ("Bottom_rail_screw1", "Bottom_rail"), ("Bottom_rail_screw1", "Handguard"), ("Bottom_rail_tnut1", "Handguard"), ("Bottom_rail_tnut1", "Bottom_rail_screw1"),
    ("Bottom_rail_tnut1", "Barrel"), ("Handguard_screw0", "Barrel_nut"), ("Handguard_screw1", "Barrel_nut"), ("Handguard_screw0", "Barrel"),
    ("Handguard_screw1", "Barrel"), ("Barrel_nut", "Barrel"), ("Barrel_nut", "Barrel_extension"), ("Barrel_nut", "Gas_tube"),
    ("Handguard", "Barrel"), ("Handguard", "Gas_tube"), ("Front_sight_base", "Handguard"), ("Handguard_screw0", "Handguard"),
    ("Handguard_screw1", "Handguard"),
    ("Mag_release_L", "Lower_receiver"), ("Mag_release_L", "Mag_catch"), ("Mag_release_L", "Mag_release_bracket"),
    ("Mag_release_L", "Mag_release_pin"), ("Mag_release_bracket", "Lower_receiver"), ("Mag_release_L", "Magazine_body"),
    ("Mag_release_L", "Bolt_catch"), ("Mag_release_screw0", "Mag_release_bracket"), ("Mag_release_L", "Upper_receiver"),
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
    "stock_mid": {"stock": 0.6},
    "stock_out_latch": {"stock": 1.0, "stock_latch": 1.0},
    "ap_big": {"rear_aperture": 1.0},
    "ap_half": {"rear_aperture": 0.5},
    "sights_half": {"rear_sight": 0.5, "front_sight": 0.5},
    "auto": {"selector": 1.0},
    "ch_latch": {"ch_latch": 1.0},
    "ch_back_latch": {"charging_handle": 1.0, "ch_latch": 1.0},
    "mag_half_out": {"mag_out": 0.3, "mag_catch": 1.0},
    "mag_release": {"mag_catch": 1.0},
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
