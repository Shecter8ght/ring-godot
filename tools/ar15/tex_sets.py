# AR-15 «ГРАНЬ-15», текстуры: наборы текстур (= материал в Blender, набор в Painter) и детали в них.
# Набор собирает детали одного узла, чтобы маски по детали и запекание шли вместе; материал детали внутри набора —
# по исходному материалу геометрии (Alu_anodized, Steel_black, ...), он остаётся в свойстве «ar15_mat» объекта.
# Без bpy: модуль читают и Blender (tex_uv.py, tex_apply.py), и Painter (sp_ar15.py).

WORK = "E:/Games/RING-godot/_asset_src/ar15/tex"       # рабочая папка (латиница: RizomUV не открывает кириллицу)
MODEL_DIR = "E:/Models Blender/WEAPONS/AR-15 — модель"
SOURCE = MODEL_DIR + "/AR-15_геометрия_v06.blend"      # принятая геометрия (владелец, 2026-10-29)
UV_BLEND = MODEL_DIR + "/AR-15_развёртка_v01.blend"     # та же геометрия с производственной развёрткой

# набор: (разрешение, детали; имя, оканчивающееся на «*», — все детали с этим началом)
SETS = {
    "upper": (4096, ["Upper_receiver", "Upper_rail", "Dust_cover", "Dust_cover_rod", "Dust_cover_spring",
                     "Forward_assist", "Charging_handle", "CH_latch_L", "CH_latch_R", "CH_latch_L_pin", "CH_latch_R_pin"]),
    "lower": (4096, ["Lower_receiver", "Bolt_catch", "Selector", "Selector_lever_L", "Selector_lever_R", "Mag_catch",
                     "Mag_button", "Mag_release_*", "Pivot_pin", "Takedown_pin", "QD_swivel", "QD_swivel_loop",
                     "Guard_pin", "Grip_screw"]),
    "handguard": (4096, ["Handguard", "Handguard_rail", "Handguard_QD_L", "Handguard_QD_R", "Handguard_screw*",
                         "Bottom_rail*", "Side_rail*"]),
    "barrel": (4096, ["Barrel", "Barrel_extension", "Barrel_nut", "Gas_block", "Gas_tube", "Gas_tube_pin",
                      "Muzzle_brake", "Muzzle_jam_nut", "Muzzle_lock_collar"]),
    "bolt": (2048, ["Bolt", "Bolt_carrier", "Extractor", "Gas_key", "Gas_key_screw*", "Cam_pin", "Ejector", "Firing_pin",
                    "Firing_pin_retainer"]),
    "internals": (2048, ["Hammer", "Hammer_pin", "Hammer_spring_*", "Trigger", "Trigger_pin", "Trigger_spring_*",
                         "Disconnector", "Auto_sear", "Auto_sear_pin", "Buffer", "Buffer_bumper", "Buffer_retainer",
                         "Buffer_spring"]),
    "stock": (4096, ["Stock_body", "Stock_buttpad", "Stock_latch", "Stock_latch_axis", "Stock_lock_pin", "Stock_QD_cup_*"]),
    # трубка с каналом внутри — площадь как у половины приклада, отдельным набором
    "tube": (4096, ["Buffer_tube", "Castle_nut", "End_plate"]),
    "grip": (4096, ["Pistol_grip"]),
    "magazine": (4096, ["Magazine_body", "Magazine_floorplate", "Magazine_floorplate_lock", "Magazine_follower",
                        "Magazine_spring"]),
    # 31 патрон — одна сетка (в патроннике и в магазине), гильза отдельно
    "rounds": (2048, ["Cartridge_556", "Case_556"]),
    "sights": (2048, ["Front_sight_*", "Rear_sight_*"]),
    "suppressor": (4096, ["Suppressor_body", "Suppressor_baffle*", "Suppressor_latch", "Suppressor_latch_pin"]),
}

# отступы развёртки в пикселях карты: между островами и от края
PADDING_PX = 12
MARGIN_PX = 8


def match(name, pattern):
    return name.startswith(pattern[:-1]) if pattern.endswith("*") else name == pattern


def set_of(name):
    """Набор детали по имени объекта (первое совпадение) или None."""
    for s, (_res, pats) in SETS.items():
        if any(match(name, p) for p in pats):
            return s
    return None
