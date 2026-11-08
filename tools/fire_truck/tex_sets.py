"""Пожарная АЦ, текстуры: наборы текстур (= материал в Blender, набор в Painter) и слоты отделки.

Без bpy: модуль читают Blender (tex_uv.py, просмотр) и Painter (стек). Набор — узел машины, чтобы маски, запекание
и плотность шли вместе; кузов (`body`) и верхняя полоса (`top_band`) — одной деталью на три набора по граням
(левая и правая половины по оси машины). Деталь, не попавшая ни в одно правило, идёт по месту
(`by_place`). Слот отделки — по имени детали, иначе по проверочному материалу формы (цвет метки sand3d).
"""
from __future__ import annotations

import re

MODEL_DIR = "E:/Models Blender/VEHICLES/Пожарная_АЦ"
SOURCE = MODEL_DIR + "/models/FireTanker_geometry_v06.blend"        # принятая форма (владелец, 2026-11-08)
UV_BLEND = MODEL_DIR + "/models/FireTanker_uv_v01.blend"            # та же форма с развёрткой по наборам
WORK = "E:/Games/RING-godot/_asset_src/fire_truck/tex"              # рабочая папка (латиница)
UV = "UVMap"
PADDING_PX = 12
SP = WORK + "/sp"                                                    # FBX, проекты Painter, карты

# проекты Painter: по 3–4 набора (видеопамяти RTX 4050 6 ГБ хватает на стек), запекание — с машиной целиком
PROJECTS = {
    "cab": ["cab_panels", "cab_parts", "glass"],
    "body": ["body_L", "body_R", "body_parts", "shutters"],
    "roof": ["roof", "trim", "pump"],
    "chassis": ["chassis", "wheels"],
    "interior": ["cab_interior", "crew_interior", "lockers"],
}
# какой вариант машины затеняет набор при запекании (остальные — «Целая»); земля — у наружных
HIGH_OF = {"lockers": "open", "cab_interior": "open", "crew_interior": "open", "pump": "open"}
GROUND = {"chassis", "wheels", "body_L", "body_R", "body_parts", "shutters", "pump", "trim", "cab_parts", "cab_panels"}

# набор: (разрешение, заголовок)
SETS = {
    "cab_panels": (4096, "Кабина: панели"),
    "cab_parts": (4096, "Кабина: фары, зеркала, бампер, подкрылки"),
    "body_L": (4096, "Кузов и верхняя полоса: левая половина"),
    "body_R": (4096, "Кузов и верхняя полоса: правая половина"),
    "body_parts": (4096, "Кузов: двери экипажа, стойки, короба, полосы"),
    "shutters": (4096, "Рольставни"),
    "roof": (4096, "Крыша: настил, лестница, рукава, ствол"),
    "trim": (4096, "Профили, подножки, лестница сзади"),
    "pump": (4096, "Насосный отсек и подножка"),
    "chassis": (4096, "Шасси"),
    "wheels": (4096, "Колёса"),
    "cab_interior": (4096, "Салон кабины"),
    "crew_interior": (4096, "Отсек экипажа"),
    "lockers": (4096, "Отсеки изнутри"),
    "glass": (4096, "Стёкла и линзы"),
}

# правила по началу имени (без суффикса .001); порядок важен — первое совпадение
RULES = [
    ("glass", ["Cab_Windshield", "Cab_Door_Glass", "crew_glass", "mirror_glass", "mirror_wide_glass", "Cab_Beacon_Lens",
               "floodlight_lens", "work_light_lens", "projector_lens", "led_strip", "lamp_bulb", "rear_lamp", "indicator",
               "foglight", "drl_strip", "beacon_led", "rear_beacon", "cap_marker", "marker", "side_marker",
               "side_repeater", "rear_reflector", "reflector", "pump_bay_led", "gauge_window", "dome_light",
               "crew_ceiling_lamp", "plate_lamp"]),
    ("cab_interior", ["Cab_DoorCard", "Cab_DoorReveal", "Cab_Jamb", "Cab_Front_Mask_Lining", "Cab_Quarter_L_Lining",
                      "Cab_Quarter_R_Lining", "dashboard", "dash_lower", "seat_", "steering", "column_", "pedal",
                      "gear_", "park_brake", "door_card", "door_pocket", "door_armrest", "door_speaker", "door_inner",
                      "window_crank", "door_lock_knob", "a_pillar", "b_pillar", "sun_visor", "visor_mount", "headliner",
                      "cab_floor_mat", "engine_hump", "kick_panel", "cab_rear_trim", "door_sill_plate", "radio_",
                      "cluster_", "gauge_", "center_console", "head_unit", "glovebox", "vent_", "siren_controller",
                      "siren_button", "cab_extinguisher", "extinguisher", "handheld_", "grab_handle"]),
    ("crew_interior", ["crew_floor", "crew_ceiling", "crew_wall_trim", "crew_side_trim", "crew_seat", "crew_headrest",
                       "scba_", "crew_door_card", "crew_door_armrest", "crew_inner_handle", "crew_grab_rail",
                       "radio_charger", "pull_strap"]),
    ("lockers", ["locker_liner", "shelf"]),
    ("wheels", ["tyre", "tread_lug", "rim", "hub", "valve_stem", "valve_cap"]),
    ("shutters", ["shutter_", "rear_shutter", "shutter"]),
    ("roof", ["roof_deck", "hose_tray", "tray_post", "suction_hose", "hose_head", "hose_strap", "ladder_1", "ladder_2",
              "ladder_3", "ladder_guide", "ladder_pulley", "ladder_rope", "ladder_pawl", "ladder_support",
              "ladder_clamp", "support_leg", "roller", "monitor_", "floodlight", "flood_post", "work_light",
              "roof_rail", "rail_post", "antenna", "antenna_base"]),
    ("pump", ["pump_", "outlet_", "suction_", "manifold_", "tow_fork", "rear_step", "wheel_chock", "chock_holder",
              "hose_reel", "hose_coil", "valve_", "drain_valve", "throttle_knob", "rear_camera", "plate_rear"]),
    ("trim", ["body_corner_profile", "roof_edge_profile", "sill_profile", "crew_step", "ladder_rail", "ladder_rung",
              "rivets_", "crew_grab", "step_strap"]),
    ("chassis", ["frame_rail", "crossmember", "front_axle", "rear_axle", "engine", "driveshaft", "u_joint",
                 "center_bearing", "muffler", "exhaust", "air_tank", "spring", "leaf", "shock", "brake_", "u_bolt",
                 "steering_box", "tie_rod", "drag_link", "spring_hanger", "mudflap", "cab_gap_cover", "Cab_Back",
                 "transmission", "gearbox", "fuel", "battery", "rear_step_bracket"]),
    ("cab_panels", ["Cab_Roof_Cap", "Cab_Roof", "Cab_Front_Mask", "Cab_Grille_Panel", "Cab_Door_L", "Cab_Door_R",
                    "Cab_DoorEdge", "Cab_Fender", "Cab_Quarter", "Cab_Bumper", "Cab_Windshield_Frit"]),
    ("cab_parts", ["Cab_", "mirror", "Wiper_", "Pillar_Deflector", "grille_", "headlight", "projector", "plate_front",
                   "plate_frame", "bumper_", "tow_hook", "arch_flare", "wheel_house", "step", "door_handle",
                   "hinge_", "door_belt_rubber", "door_lock", "rain_gutter", "washer_nozzle", "siren_speaker",
                   "cab_antenna", "beacon_", "kerb_arm", "lamp_reflector", "lamp_rim", "rear_lamp_bezel"]),
    ("body_parts", ["crew_door", "crew_hinge", "crew_handle", "crew_lock", "crew_win_seal", "crew_vent", "rear_column",
                    "intake", "rub_strip", "arch_trim", "rear_wheel_house", "top_band", "lower_door", "paddle_handle",
                    "flap_hinge", "intake_"]),
]

SPLIT = {"body": ("body_L", "body_R"), "top_band": ("body_L", "body_R")}


def base_name(name: str) -> str:
    return re.sub(r"\.\d{3}$", "", name)


def set_of(name: str) -> str | None:
    """Набор детали по имени; None — решать по месту (by_place)."""
    b = base_name(name)
    if b in SPLIT:
        return "split"
    for st, prefixes in RULES:
        for p in prefixes:
            if b == p or b.startswith(p):
                return st
    return None


def by_place(x: float, y: float, z: float) -> str:
    """Набор мелкой детали без правила — по месту в машине (центр детали, м; перёд к −Y)."""
    if z > 3.05:
        return "roof"
    if y < -1.55:
        return "cab_parts" if z < 1.2 or abs(x) > 1.0 else "cab_interior"
    if y > 3.55 and z < 1.1:
        return "pump"
    if z < 0.95 and abs(x) < 0.55:
        return "chassis"
    return "body_parts"


def face_set(obj_name: str, cx: float) -> str:
    """Набор грани кузова / верхней полосы по стороне (X влево): почти вся площадь кузова — ниши под шторками и
    облицовкой, она уходит в скрытое; видимое — борта, зад, перёд, верх — делится пополам."""
    left, right = SPLIT[base_name(obj_name)]
    return left if cx >= 0.0 else right


# слоты отделки: (слот, заголовок, отделка по умолчанию до выбора владельца, начала имён)
SLOTS = [
    ("glass_auto", "Стёкла кабины и экипажа", "GL-AUTO", ["Cab_Windshield", "Cab_Door_Glass", "crew_glass"]),
    ("mirror", "Зеркала (стекло)", "GL-MIR", ["mirror_glass", "mirror_wide_glass"]),
    ("lens_blue", "Линзы маячков", "TL-BLU-GLS", ["Cab_Beacon_Lens", "rear_beacon", "beacon_led"]),
    ("lens_amber", "Поворотники и габариты", "TL-AMB-GLS", ["indicator", "side_repeater", "cap_marker", "marker",
                                                              "side_marker"]),
    ("lens_red", "Задние фонари и катафоты", "TL-RED-GLS", ["rear_reflector", "reflector"]),
    ("lens_clear", "Фары, прожекторы, плафоны", "TL-CLR-GLS", ["projector_lens", "floodlight_lens", "work_light_lens",
                                                               "foglight", "drl_strip", "led_strip", "lamp_bulb",
                                                               "pump_bay_led", "gauge_window", "dome_light",
                                                               "crew_ceiling_lamp", "plate_lamp", "rear_lamp"]),
    ("chrome", "Хром: ободки, отражатели", "CR-GLS", ["lamp_rim", "lamp_reflector", "beacon_reflector", "projector_cup",
                                                     "gauge_bezel", "gauge_ring", "tow_fork_pin"]),
    ("tyre", "Шины", "RB-BLK-MAT", ["tyre", "tread_lug"]),
    ("rubber", "Резина: уплотнители, брызговики, коврик, всасывающие рукава", "RB-BLK-MAT",
     ["Cab_Windshield_Seal", "Cab_Door_Seal", "Cab_JambSeal", "crew_win_seal", "door_belt_rubber", "mudflap",
      "cab_floor_mat", "suction_hose", "Wiper_Rubber", "seal", "_seal"]),
    ("hose_red", "Напорные рукава", "RB-RED-HOS", ["hose_coil"]),
    ("paint_red", "Кузов и кабина: красная автоэмаль", "AP-RED-GLS", []),
    ("paint_white", "Двери кабины, колпак, бампер, полосы: белая автоэмаль", "AP-WHT-GLS", []),
    ("shutter_alu", "Рольставни, кант, поручни: анодированный профиль", "AL-EXT-ANO",
     ["shutter_", "rear_shutter_bar", "shutter", "roof_edge_profile", "roof_rail", "rail_post", "body_corner_profile",
      "sill_profile", "ladder_rail", "ladder_rung", "crew_grab", "ladder_1", "ladder_2", "ladder_3", "ladder_guide"]),
    ("sheet_alu", "Облицовка отсеков, полки, настил, подножки: катаный алюминий", "AL-ROL-SAT",
     ["locker_liner", "shelf", "pump_bay_liner", "roof_deck", "hose_tray", "rear_step", "crew_step", "crew_floor", "step"]),
    ("chassis_black", "Шасси, диски, кронштейны: чёрная полуглянцевая", "PT-BLK-SAT", []),
    ("plastic_black", "Пластик чёрный снаружи: подкрылки, накладки, корпуса фонарей", "PL-BLK-TEX", []),
    ("interior_plastic", "Пластик салона", "PL-GRY-TEX", []),
    ("straps", "Ремни, стропы, тесьма", "FB-BLK-WEB", ["hose_strap", "scba_strap", "scba_band", "pull_strap", "step_strap",
                                                      "seat_driver_belt", "seat_commander_belt", "ladder_rope"]),
    ("headliner", "Потолки кабины и отсека экипажа: войлок", "FB-SEAT-GRY", ["headliner", "crew_ceiling"]),
    ("seat_fabric", "Ткань сидений", "FB-SEAT-GRY", []),
    ("steel_bright", "Нержавейка: панель насоса, поручни", "SS-BRU", ["pump_panel"]),
    ("signal_yellow", "Жёлтое сигнальное: прижимы, рычаги, упоры", "PT-YEL-GLS",
     ["ladder_clamp", "valve_handle", "wheel_chock"]),
    ("fixtures", "Мелкий крепёж и литьё (головки, гайки)", "AL-RAW-BB", ["outlet_coupling", "suction_coupling", "hose_head"]),
]

# проверочный материал формы (метка sand3d) → слот, если имя не решило
MAT_SLOT = [
    (r"painted_metal #(b3141c|b01418|c01818|c81010|b00000)", "paint_red"),
    (r"painted_metal #(e6e6e1|f0f0ea)", "paint_white"),
    (r"painted_metal #(1d1d1f|2d2f31)", "chassis_black"),
    (r"painted_metal #(e0b020|c8a018|d8b21c)", "signal_yellow"),
    (r"plastic #(e2b21a|d8b21c)", "signal_yellow"),
    (r"aluminium #8d9093", "sheet_alu"),
    (r"aluminium", "shutter_alu"),
    (r"brushed_steel", "steel_bright"),
    (r"chrome", "chrome"),
    (r"brass", "fixtures"),
    (r"rubber #7a1d1a", "hose_red"),
    (r"rubber", "rubber"),
    (r"fabric #(8d9093|2b2e33|25282c|151515|7d8084)", "seat_fabric"),
    (r"fabric", "seat_fabric"),
    (r"glass #e2f0ea", "glass_auto"),
    (r"glass #(2050d8|2a55e0|3a6cff)", "lens_blue"),
    (r"glass #(f0a020)", "lens_amber"),
    (r"glass #(c81010|b00000)", "lens_red"),
    (r"glass", "lens_clear"),
    (r"plastic #(141414|0d0d0d|0e0e0e|0f0f0f|101010|111111|151515|1a1a1a|1b1b1b|202020)", "plastic_black"),
    (r"plastic", "interior_plastic"),
]


def slot_of(name: str, mat: str, set_name: str) -> str:
    b = base_name(name)
    for sid, _t, _f, prefixes in SLOTS:
        for p in prefixes:
            if b == p or b.startswith(p) or (p.startswith("_") and p in b):
                return sid
    for pat, sid in MAT_SLOT:
        if re.search(pat, mat or ""):
            if sid == "interior_plastic" and set_name not in ("cab_interior", "crew_interior"):
                return "plastic_black"
            return sid
    return "plastic_black"
