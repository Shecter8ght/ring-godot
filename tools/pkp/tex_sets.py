# «Частокол», текстуры: наборы текстур (= материал в Blender, набор в Painter) и детали в них. Набор — узел пулемёта:
# маски по деталям и запекание идут вместе. Без bpy: модуль читают Blender (tex_uv.py, tex_uv_apply.py, sp_export.py)
# и Painter. Слоты отделки (какая отделка на какой детали) — finish-spec.json рядом с моделью (tex_spec.py).

WORK = "E:/Games/RING-godot/_asset_src/pkp/tex"            # рабочая папка
MODEL_DIR = "E:/Models Blender/WEAPONS/Печенег — модель"
SOURCE = MODEL_DIR + "/Частокол_геометрия_v03.blend"        # принятая форма (владелец, 2026-11-14: «Принимаю»)
UV_BLEND = MODEL_DIR + "/Частокол_развёртка_v01.blend"      # та же форма с развёрткой под Painter

# набор: (разрешение атласа, ожидаемая плотность пикс/мм — по ней режутся длинные ленты, детали). Разрешение 8192 —
# крупные плоскости у глаза (коробка, крышка, коробки для ленты); Painter ведёт их и в 4K, выгрузка — 8K.
# Площади (формы v03, см²): ствольная коробка с вкладышем ~1900, крышка с лотком ~1200, ствол с газовым узлом ~1360,
# кожух с ручкой ~660, сошки ~800, затворная группа ~480, приклад ~1060, коробка 100 ~3130, коробка 200 ~5070.
SETS = {
    "receiver": (8192, 15.0, ["Receiver", "Breech_Insert", "Barrel_Lock", "Box_Bracket", "Side_Rail", "Sling_Bar",
                              "Trigger_Housing", "Trigger", "Safety_Lever", "Cover_Catch", "Port_Cover",
                              "Cover_Hinge_Pin"]),
    "cover": (8192, 18.0, ["Top_Cover", "Feed_Flap", "Exit_Flap", "Cover_Base_F", "Cover_Base_R", "Cover_Latch",
                           "Cover_Latch_Pin", "Feed_Tray", "Cover_Guide", "Cover_Lever", "Cover_Lever_Bracket",
                           "Cover_Lever_Pin", "Cover_Lever_Spring", "Feed_Lever", "Feed_Lever_Guard", "Feed_Lever_Pin",
                           "Feed_Pawl_Arm", "Feed_Pawl_Shaft", "Retainer_Pawl", "Retainer_Shaft", "Retainer_Spring",
                           "Cartridge_Stop"]),
    "barrel": (8192, 16.0, ["Barrel", "Flash_Hider", "Gas_Block", "Gas_Housing", "Gas_Tube", "Front_Sight_Base",
                            "Front_Sight_Post"]),
    "shroud": (4096, 20.0, ["Shroud", "Shroud_Scoop", "Carry_Handle"]),
    "sight": (4096, 30.0, ["Rear_Sight_Base", "Rear_Sight_Leaf", "Rear_Sight_Slider", "Rear_Sight_Notch",
                           "Rear_Sight_Knob", "Rear_Sight_Button", "Rear_Sight_Pin", "Rear_Sight_Spring"]),
    "bipod": (4096, 12.0, ["Bipod_Yoke", "Bipod_Leg_L", "Bipod_Leg_R", "Bipod_Foot_L", "Bipod_Foot_R",
                           "Bipod_Hinge_Pin_L", "Bipod_Hinge_Pin_R", "Bipod_Pin", "Bipod_Spring"]),
    "bolt": (4096, 16.0, ["Bolt_Carrier", "Bolt", "Bolt_Extractor", "Gas_Piston", "Charging_Handle",
                          "Cartridge_Gripper", "Ejector", "Recoil_Guide", "Recoil_Spring", "Gripper_Pin",
                          "Piston_Pin"]),
    "stock": (4096, 11.0, ["Stock", "Buttplate", "Butt_Screw_L", "Butt_Screw_R", "Rest_Hinge", "Shoulder_Rest"]),
    "grip": (4096, 24.0, ["Pistol_Grip"]),
    "box100": (8192, 12.0, ["Box100_Body", "Box100_Lid", "Box100_Flap", "Box100_Latch", "Box100_Mount",
                            "Box100_Mount_Tooth", "Box100_Turnbutton", "Box100_Flap_Pin", "Box100_Hinge_Pin",
                            "Box100_Latch_Pin", "Box100_Latch_Spring", "Box100_Handle"]),
    "box200": (8192, 10.0, ["Box200_Body", "Box200_Lid", "Box200_Flap", "Box200_Latch", "Box200_Mount",
                            "Box200_Mount_Tooth", "Box200_Turnbutton", "Box200_Flap_Pin", "Box200_Hinge_Pin",
                            "Box200_Latch_Pin", "Box200_Latch_Spring", "Box200_Handle"]),
    # лента: одна сетка звена, спирали и патрона на все копии (Belt_*, Strip_*) — развёртка у сетки общая
    "belt": (4096, 25.0, ["Belt_Link_00", "Belt_Spiral_00", "Belt_Round_00", "Belt_Tip", "Strip_Tip", "Cartridge",
                          "Case_Spent"]),
    # съёмный обвес (две выключенные коллекции «Кронштейн — …»)
    "rails": (4096, 17.0, ["Rail_Cover", "Rail_Cover_Screw_F", "Rail_Cover_Screw_R", "Rail_Forend", "Forend_Bolt_A",
                           "Forend_Bolt_B"]),
}
SHARED = {"Belt_Link_src": "belt", "Belt_Spiral_src": "belt", "Belt_Round_src": "belt"}   # сетки копий ленты

# проекты Painter: 15 млн треугольников одним проектом тяжелы — три проекта по узлам (свой FBX у каждого)
PROJECTS = {
    "body": ["receiver", "cover", "bolt", "sight", "grip", "stock"],
    "front": ["barrel", "shroud", "bipod", "rails"],
    "box": ["box100", "box200", "belt"],
}
# рабочее разрешение наборов в Painter (стек процедурный — выгрузка в разрешении набора SETS без потерь)
WORK_RES = 4096


def project_of(set_name):
    for p, sets in PROJECTS.items():
        if set_name in sets:
            return p
    return None

# отступы развёртки в пикселях карты (на 4K; у 8K — вдвое)
PADDING_PX = 12
GROUP_PX = 6

# изнанка, которую видно только при открытой крышке коробки или в канале ствола: сторона острова против видимой
INNER_K = {"box": 0.6, "bore": 0.25}

# излом, по которому Smart UV делит острова
ANGLE = 60.0
# ствол и кожух: рёбра и окна под 90° дробили их на тысячи узких полос — отступы съедали треть атласа (заполнение 37 %)
ANGLES = {"grip": 75.0, "barrel": 80.0, "shroud": 80.0}
# наборы, где кольца (рёбра охлаждения ствола) режутся на четверти дуги — иначе пустая середина каждого кольца
RING_SPLIT = {"barrel"}


def set_of(name):
    """Набор детали по имени объекта или None."""
    for s, (_res, _aim, names) in SETS.items():
        if name in names:
            return s
    return None


def set_of_object(name, mesh_name):
    """Набор объекта; копии ленты — по сетке."""
    return set_of(name) or SHARED.get(mesh_name)
