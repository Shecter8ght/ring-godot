# ВЕРАС-54 v14: риг подвижных деталей — ползунки пустышки VERAS54_Controls и приводы на delta-трансформы (исходные
# места деталей не тронуты, простые выражения работают без разрешения на скрипты). Этим же описанием пользуются
# сборщик (assemble.py), съёмка поз (shots.py --pose) и проверка пересечений (check_overlaps.py).
# У каждой подвижной детали начало координат стоит на её оси (pivot в parts()), оси объектов совпадают с мировыми:
# +X к дулу, +Z вверх, −Y — правая сторона. Поворот вокруг +Y на положительный угол опускает то, что впереди оси.
import math

from dims import *

MM = 0.001


def _deg(a):
    return f"{math.radians(a):.6f}"


# переводчик построен в положении «АВ»; углы от него — отчёт part_controls (лунки фиксатора на коробке)
SEL_SAFE_DEG, SEL_TWO_DEG, SEL_ONE_DEG = -9.0, 3.6, 7.3
SEL_SPAN = SEL_ONE_DEG - SEL_SAFE_DEG
SEL_AB = -SEL_SAFE_DEG / SEL_SPAN          # значение ползунка в «АВ» (0,552)
SEL_TWO = (SEL_TWO_DEG - SEL_SAFE_DEG) / SEL_SPAN

TRIGGER_DEG = 11.0             # выжим: нижний конец крючка назад
MAG_CATCH_DEG = -13.0          # отжатие: лапка вперёд, зуб назад на 1,55 мм — отпускает выступ магазина
MAG_DROP = 150.0               # магазин вынут: вниз из шахты (оценка, для проверки и показа)
COVER_BUTTON = 1.2             # кнопка крышки вниз
FOLD_DEG = -180.0              # приклад складывается влево вдоль левого борта
HINGE_LATCH_DROP = 1.2         # защёлка шарнира вниз по оси (оценка)
STOCK_RUN = 40.0               # регулировка длины: корпус приклада назад по трубе, три положения через 20 мм (оценка)
STOCK_LEVER_DEG = 2.0          # рычаг регулировки: хвост вверх до упора в корпус (оценка)
HG_LATCH_DEG = 25.0            # защёлка цевья: задний конец наружу (оценка)
# возвратная пружина v13 (X 17,3…182,7) сжимается к заднему концу; передний конец едет с рамой
SPRING_SQUEEZE = CARRIER_TRAVEL / (182.7 - 17.3)

# (имя ползунка, подсказка, значение по умолчанию)
SLIDERS = [
    ("carrier", "Затворная рама: 1 — отведена назад до упора (с ней рукоятка, затвор, шток с поршнем)", 0.0),
    ("selector", f"Переводчик: 0 — предохранитель, {SEL_AB:.2f} — «АВ», {SEL_TWO:.2f} — «2», 1 — «ОД»", SEL_AB),
    ("trigger", "Спусковой крючок: 1 — выжат", 0.0),
    ("mag_catch", "Защёлка магазина: 1 — отжата", 0.0),
    ("mag", "Магазин: 1 — вынут (вниз из шахты); сначала отжать защёлку", 0.0),
    ("cover_button", "Кнопка крышки: 1 — нажата", 0.0),
    ("stock_fold", "Приклад: 1 — сложен влево", 0.0),
    ("hinge_latch", "Защёлка шарнира приклада: 1 — нажата", 0.0),
    ("stock_len", "Длина приклада: 0 — «1» (короткий), 0,5 — «2», 1 — «3» (длинный)", 0.0),
    ("stock_lever", "Рычаг регулировки длины приклада: 1 — нажат", 0.0),
    ("hg_latch", "Защёлка цевья: 1 — отведена", 0.0),
]


def drivers():
    """[(объект, свойство, индекс, выражение, [ползунки])] — углы в радианах, сдвиги в метрах."""
    return [
        ("Bolt_Carrier", "delta_location", 0, f"-{CARRIER_TRAVEL * MM:.6f}*carrier", ["carrier"]),
        ("Recoil spring • coil", "delta_scale", 0, f"1-{SPRING_SQUEEZE:.5f}*carrier", ["carrier"]),
        ("Selector_Lever", "delta_rotation_euler", 1, f"{_deg(SEL_SPAN)}*(selector-{SEL_AB:.5f})", ["selector"]),
        ("Trigger", "delta_rotation_euler", 1, f"{_deg(TRIGGER_DEG)}*trigger", ["trigger"]),
        ("Mag_Catch", "delta_rotation_euler", 1, f"{_deg(MAG_CATCH_DEG)}*mag_catch", ["mag_catch"]),
        ("Magazine_Body", "delta_location", 2, f"-{MAG_DROP * MM:.6f}*mag", ["mag"]),
        ("Cover_Button", "delta_location", 2, f"-{COVER_BUTTON * MM:.6f}*cover_button", ["cover_button"]),
        ("Stock_Knuckle", "delta_rotation_euler", 2, f"{_deg(FOLD_DEG)}*stock_fold", ["stock_fold"]),
        ("Hinge_Latch", "delta_location", 2, f"-{HINGE_LATCH_DROP * MM:.6f}*hinge_latch", ["hinge_latch"]),
        ("Stock_Body", "delta_location", 0, f"-{STOCK_RUN * MM:.6f}*stock_len", ["stock_len"]),
        ("Stock_Latch", "delta_rotation_euler", 1, f"{_deg(STOCK_LEVER_DEG)}*stock_lever", ["stock_lever"]),
        ("Handguard_Latch", "delta_rotation_euler", 2, f"{_deg(HG_LATCH_DEG)}*hg_latch", ["hg_latch"]),
    ]


# Крышка ригом не открывается: её передний шарнир на колодке собран по снимкам снаружи, механика подъёма (что
# поднимается вместе с крышкой и на какой угол) по образцу не видна — в клипах рук она не нужна.
# позы для проверочных кадров и проверки пересечений
POSES = {
    "charged": {"carrier": 1.0},
    "half": {"carrier": 0.5},
    "safe": {"selector": 0.0},
    "two": {"selector": SEL_TWO},
    "single": {"selector": 1.0},
    "fire": {"trigger": 1.0},
    "catch": {"mag_catch": 1.0},
    "mag_out": {"mag_catch": 1.0, "mag": 1.0},
    "cover_button": {"cover_button": 1.0},
    "folded": {"stock_fold": 1.0, "hinge_latch": 1.0},
    "stock_long": {"stock_len": 1.0},
    "stock_lever": {"stock_lever": 1.0},
    "hg_latch": {"hg_latch": 1.0},
}
