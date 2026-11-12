# АСТЕН-919, текстуры: наборы текстур (= материал в Blender, набор в Painter) и детали в них.
# Набор собирает детали одного узла: маски по детали и запекание идут вместе. Материал детали внутри набора —
# исходный материал геометрии (Steel_nitride, Polymer, ...), он остаётся в свойстве «asten_mat» объекта.
# Без bpy: модуль читают и Blender (tex_uv.py, sp_export.py), и Painter.

WORK = "E:/Games/RING-godot/_asset_src/asten919/tex"       # рабочая папка (латиница)
MODEL_DIR = "E:/Models Blender/WEAPONS/АСТЕН-919"
SOURCE = MODEL_DIR + "/АСТЕН-919_геометрия_v03.blend"       # принятая геометрия (владелец, 2026-11-12)
UV_BLEND = MODEL_DIR + "/АСТЕН-919_развёртка_v02.blend"      # та же геометрия с развёрткой под Painter
#                                                              (v02 — плотнее: скрытое ужато, ствол с резьбой отдельно)

# набор: (разрешение, детали)
SETS = {
    "slide": (4096, ["Slide", "Slide_Cover_Plate", "Extractor", "MOS_Cover_Plate", "MOS_Screw_L", "MOS_Screw_R",
                     "Front_Sight", "Rear_Sight"]),
    "frame": (4096, ["Frame", "Locking_Block", "Trigger_Housing", "Ejector", "Serial_Plate", "Pin_Locking_Block",
                     "Pin_Trigger", "Pin_Trigger_Housing"]),
    # штатный ствол, возвратный механизм и все органы управления
    "parts": (4096, ["Barrel", "Guide_Rod", "Recoil_Spring_Outer", "Recoil_Spring_Inner", "Slide_Stop", "Slide_Lock",
                     "Mag_Catch", "Trigger", "Trigger_Safety", "Trigger_Safety_Pin"]),
    # вариант ствола с резьбой и его гайка — свой набор: в общем он занимал треть атласа (владелец 2026-11-12:
    # развёртку плотнее)
    "barrel_t": (2048, ["Barrel_Threaded", "Thread_Protector"]),
    # 17 патронов в магазине и отдельный — одна сетка Round_9x19; гильза отдельно
    "magazine": (4096, ["Magazine_Body", "Magazine_Floorplate", "Magazine_Insert", "Magazine_Follower",
                        "Magazine_Spring", "Round_9x19_loose", "Case_9x19"]),
}
SHARED = "Round_9x19"          # сетка патрона: копии в магазине (Round_01…17) берут её развёртку

# отступы развёртки в пикселях карты: между островами и от края
PADDING_PX = 12
MARGIN_PX = 8

# сторона острова скрытой поверхности (полости рамки и затвора, шахта, труба магазина, канал ствола) против видимой:
# 0,4 → в 6 раз меньше пикселей; такие места видны только в разборке или в глубине окна
HIDDEN_K = 0.4

# излом, по которому Smart UV делит острова; у рамки шире — пупырышки рукояти не рвутся на отдельные острова
ANGLE = 60.0
ANGLES = {"frame": 80.0}


def set_of(name):
    """Набор детали по имени объекта или None."""
    for s, (_res, names) in SETS.items():
        if name in names:
            return s
    return None
