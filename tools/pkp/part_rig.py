# ПКП: риг подвижных деталей — ползунки пустышки PKP_Controls и приводы на delta-трансформы (исходные места деталей
# не тронуты, простые выражения работают без разрешения на скрипты). Этим же описанием пользуются сборщик
# (assemble.py), съёмка поз (shots.py --pose) и проверка пересечений (check_overlaps.py).
# У каждой подвижной детали начало координат стоит на её оси (pivot в parts()), оси объектов совпадают с мировыми:
# +X к дулу, +Z вверх, −Y — правая сторона. Поворот вокруг +Y на положительный угол поднимает то, что позади оси.
import math

from dims import *

MM = 0.001


def _deg(a):
    return f"{math.radians(a):.6f}"


# (имя ползунка, подсказка, значение по умолчанию)
SLIDERS = [
    ("cover", "Крышка ствольной коробки: 1 — открыта", 0.0),
    ("tray", "Лоток (основание приёмника): 1 — поднят", 0.0),
    ("charge", "Рукоятка перезаряжания: 1 — отведена назад до упора", 0.0),
    ("carrier", "Затворная рама: 1 — в заднем положении", 0.0),
    ("feed", "Рычаг подачи: 1 — отведён (рама сзади); двигать без ленты", 0.0),
    ("port_cover", "Щиток окна выброса гильз: 1 — открыт", 0.0),
    ("feed_flap", "Щиток окна приёмника: 0 — поднят (лента вставлена), 1 — закрыт", 0.0),
    ("exit_flap", "Щиток окна выхода ленты: 0 — откинут, 1 — закрыт", 0.0),
    ("trigger", "Спусковой крючок: 1 — выжат", 0.0),
    ("safety", "Флажок предохранителя: 0 — «огонь», 1 — предохранение", 0.0),
    ("rest", "Плечевой упор: 1 — откинут на плечо", 0.0),
    ("bipod_fold", "Сошки: 1 — сложены назад вдоль ствола", 0.0),
    ("bipod_close", "Ноги сошек: 1 — сведены вместе", 0.0),
    ("sight_range", "Хомутик прицела: 0 — деление «1», 1 — «15»", 5.6 / 39.2),
    ("windage", "Целик, боковая поправка: 0,5 — середина", 0.5),
    ("box_lid", "Крышка коробки с лентой: 1 — открыта", 0.0),
    ("box_flap", "Заслонка выхода ленты на коробке: 0 — закрыта, 1 — откинута до упора", 0.7),
]

COVER_DEG = COVER_OPEN_DEG
TRAY_DEG = 88.0                # как у крышки: лоток поднимается вплотную к ней
PORT_DEG = 100.0
TRIGGER_DEG = 12.0
SAFETY_DEG = 75.0              # оценка: на образцах флажок только в положении «огонь»
REST_DEG = 75.0
BIPOD_FOLD_DEG = 90.0
BOX_LID_DEG = 110.0             # крышка коробки открывается на снятой коробке
BOX_FLAP_DEG = 150.0
BIPOD_SPREAD_DEG = 30.0        # разведение ног от отвеса; ползунок bipod_close сводит их
SIGHT_RUN = 39.2               # ход хомутика от «1» до «15» вдоль планки
SIGHT_DIR = (0.9971, 0.0759)   # направление планки (X, Z)
SIGHT_LEAF_DEG = 11.0          # подъём планки на полном ходе хомутика (оценка)
WINDAGE = 1.9
CARRIER_TRAVEL = CH_TRAVEL
BOLT_UNLOCK_DEG = 35.0
BOLT_LAG = 10.0                # затвор отстаёт от рамы на её свободный ход
SPRING_SQUEEZE = 0.6586        # доля длины возвратной пружины, на которую она сжимается за ход рамы
FEED_LEVER_DEG = 26.0


def drivers():
    """[(объект, свойство, индекс, выражение, [ползунки])] — углы в радианах, сдвиги в метрах."""
    s0 = 5.6 / 39.2
    D = [
        ("Top_Cover", "delta_rotation_euler", 1, f"{_deg(COVER_DEG)}*cover", ["cover"]),
        ("Feed_Tray", "delta_rotation_euler", 1, f"{_deg(TRAY_DEG)}*tray", ["tray"]),
        ("Charging_Handle", "delta_location", 0, f"-{CH_TRAVEL * MM:.6f}*charge", ["charge"]),
        ("Bolt_Carrier", "delta_location", 0, f"-{CARRIER_TRAVEL * MM:.6f}*max(carrier, charge)", ["carrier", "charge"]),
        # затвор отпирается поворотом на первых 10 мм хода рамы; пружина сжимается; рычаг подачи качается от штока рамы
        ("Bolt", "delta_rotation_euler", 0, f"{_deg(BOLT_UNLOCK_DEG)}*min(1, max(carrier, charge)*{CARRIER_TRAVEL / 10.0:.2f})", ["carrier", "charge"]),
        ("Recoil_Spring", "delta_scale", 0, f"1-{SPRING_SQUEEZE:.4f}*max(carrier, charge)", ["carrier", "charge"]),
        ("Bolt", "delta_location", 0, f"{BOLT_LAG * MM:.6f}*min(1, max(carrier, charge)*{CARRIER_TRAVEL / 10.0:.2f})", ["carrier", "charge"]),
        # рычаг подачи — своим ползунком: под ним лежит лента, палец подачи при ходе упирается в патрон
        ("Feed_Lever", "delta_rotation_euler", 0, f"{_deg(FEED_LEVER_DEG)}*feed", ["feed"]),
        ("Port_Cover", "delta_rotation_euler", 0, f"{_deg(PORT_DEG)}*port_cover", ["port_cover"]),
        ("Feed_Flap", "delta_rotation_euler", 0, f"{_deg(90.0)}*feed_flap", ["feed_flap"]),
        ("Exit_Flap", "delta_rotation_euler", 0, f"{_deg(90.0)}*exit_flap", ["exit_flap"]),
        ("Trigger", "delta_rotation_euler", 1, f"{_deg(TRIGGER_DEG)}*trigger", ["trigger"]),
        ("Safety_Lever", "delta_rotation_euler", 1, f"{_deg(SAFETY_DEG)}*safety", ["safety"]),
        ("Shoulder_Rest", "delta_rotation_euler", 1, f"{_deg(REST_DEG)}*rest", ["rest"]),
        ("Bipod_Yoke", "delta_rotation_euler", 1, f"{_deg(BIPOD_FOLD_DEG)}*bipod_fold", ["bipod_fold"]),
        ("Bipod_Leg_L", "delta_rotation_euler", 0, f"-{_deg(BIPOD_SPREAD_DEG)}*bipod_close", ["bipod_close"]),
        ("Bipod_Leg_R", "delta_rotation_euler", 0, f"{_deg(BIPOD_SPREAD_DEG)}*bipod_close", ["bipod_close"]),
        # пружина-разжим между ногами: сжимается и чуть опускается вместе со шпеньками ног
        ("Bipod_Spring", "delta_scale", 1, "1-0.62*bipod_close", ["bipod_close"]),
        ("Bipod_Spring", "delta_location", 2, "-0.0028*bipod_close", ["bipod_close"]),
        ("Box100_Lid", "delta_rotation_euler", 0, f"{_deg(BOX_LID_DEG)}*box_lid", ["box_lid"]),
        ("Box200_Lid", "delta_rotation_euler", 0, f"{_deg(BOX_LID_DEG)}*box_lid", ["box_lid"]),
        ("Box100_Flap", "delta_rotation_euler", 0, f"{_deg(BOX_FLAP_DEG)}*box_flap", ["box_flap"]),
        ("Box200_Flap", "delta_rotation_euler", 0, f"{_deg(BOX_FLAP_DEG)}*box_flap", ["box_flap"]),
        ("Rear_Sight_Slider", "delta_location", 0, f"{SIGHT_RUN * SIGHT_DIR[0] * MM:.6f}*({s0:.5f}-sight_range)", ["sight_range"]),
        ("Rear_Sight_Slider", "delta_location", 2, f"{SIGHT_RUN * SIGHT_DIR[1] * MM:.6f}*({s0:.5f}-sight_range)", ["sight_range"]),
        ("Rear_Sight_Leaf", "delta_rotation_euler", 1, f"-{_deg(SIGHT_LEAF_DEG)}*(sight_range-{s0:.5f})", ["sight_range"]),
        ("Rear_Sight_Notch", "delta_location", 1, f"{2 * WINDAGE * MM:.6f}*(windage-0.5)", ["windage"]),
        ("Rear_Sight_Knob", "delta_rotation_euler", 1, f"{2 * math.pi * 6:.5f}*(windage-0.5)", ["windage"]),
    ]
    return D


# позы для проверочных кадров и проверки пересечений
POSES = {
    "open": {"cover": 1.0},
    "open_tray": {"cover": 1.0, "tray": 1.0},
    "charged": {"charge": 1.0, "port_cover": 1.0},
    "fire": {"trigger": 1.0},
    "safe": {"safety": 1.0},
    "rest": {"rest": 1.0},
    "bipod_folded": {"bipod_fold": 1.0, "bipod_close": 0.6},
    "sight_far": {"sight_range": 1.0, "windage": 1.0},
    "box_open": {"box_lid": 1.0},
}
