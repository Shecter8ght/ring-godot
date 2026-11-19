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
# целик (отчёт part_sights, всё — оценки): хомутик идёт вперёд по планке, планка поднимает задний конец с диоптром
SIGHT_RUN, SIGHT_LEAF_DEG, WINDAGE, SIGHT_BUTTON = 24.2, 11.0, 0.65, 0.6
# возвратная пружина v13 (X 17,3…182,7) сжимается к заднему концу; передний конец едет с рамой
SPRING_SQUEEZE = CARRIER_TRAVEL / (182.7 - 17.3)

# ---- затвор (отчёт part_bolt): рама идёт 2,5 мм свободно, на 2,5…8 мм поворачивает затвор на −35° (отпирание),
# дальше затвор едет с рамой, отставая на 8 мм ----
BOLT_FREE, BOLT_LAG, BOLT_UNLOCK_DEG = 2.5, 8.0, -35.0
BOLT_FACE_X = 239.35           # зеркало затвора (дно чашечки) в запертом положении
CASE_BASE_X = 239.4            # дно гильзы в патроннике
EJECT_AT = 72.35               # ход рамы, на котором дно гильзы встречает отражатель
LUG_AHEAD = 0.55               # досылающий гребень выступает вперёд зеркала (X 239,9)
# ---- магазин (отчёт part_magazine): стопка под затвором утоплена; когда затвор ушёл назад за верхний патрон, она
# поднимается вдоль дуги ещё на STACK_FREE_DEG вокруг центра дуги ----
STACK_CENTER = (524.18, 9.24)   # (X, Z) центра дуги стопки, мм (подгонка по донцам 30 патронов, R 374,3)
STACK_FREE_DEG = 0.353           # добавочный угол свободного положения (тот же знак, что transfer.ROT_Y)
TOP_BASE = (151.66, 4.15, -16.29)   # центр дна верхнего патрона в утопленном положении (X, Y, Z), мм
TOP_PITCH = 6.66                # наклон верхнего патрона носом вверх в утопленном положении, градусы
TOP_ROUND = ("Magazine • loaded case 1", "Magazine • loaded projectile 1")
# пока гребень-досылатель идёт над патронами (ход рамы 30…96 мм), он утапливает стопку ещё на STACK_PUSH мм:
# нос верхнего патрона поднят и без этого задевал гребень
STACK_PUSH, PUSH_T0, PUSH_T1 = 3.7, 30.0, 44.0

# выражения входов приводов: доля хода рамы (ползунок carrier или «пила» цикла), то же без возврата, вторая половина цикла
CF = "max(carrier, 1-abs(2*cycle-1))"
CU = "max(carrier, min(2*cycle, 1))"

# (имя ползунка, подсказка, значение по умолчанию)
SLIDERS = [
    ("cycle", "Цикл перезаряжания: 0 → 0,5 — рама идёт назад (гильза извлекается и вылетает), 0,5 → 1 — вперёд "
              "(затвор цепляет верхний патрон магазина и досылает в патронник)", 0.0),
    ("live_round", "В патроннике: 0 — стреляная гильза, 1 — патрон с пулей", 0.0),
    ("carrier", "Затворная рама отдельно от цикла: 1 — отведена назад до упора (с ней рукоятка, затвор, шток с поршнем)", 0.0),
    ("selector", f"Переводчик: 0 — предохранитель, {SEL_AB:.2f} — «АВ», {SEL_TWO:.2f} — «2», 1 — «ОД»; перед отведением "
                 "рамы снять с предохранителя", 0.0),
    ("trigger", "Спусковой крючок: 1 — выжат", 0.0),
    ("mag_catch", "Защёлка магазина: 1 — отжата", 0.0),
    ("mag", "Магазин: 1 — вынут (вниз из шахты); сначала отжать защёлку", 0.0),
    ("cover_button", "Кнопка крышки: 1 — нажата", 0.0),
    ("stock_fold", "Приклад: 1 — сложен влево", 0.0),
    ("hinge_latch", "Защёлка шарнира приклада: 1 — нажата", 0.0),
    ("stock_len", "Длина приклада: 0 — «1» (короткий), 0,5 — «2», 1 — «3» (длинный)", 0.0),
    ("stock_lever", "Рычаг регулировки длины приклада: 1 — нажат", 0.0),
    ("hg_latch", "Защёлка цевья: 1 — отведена", 0.0),
    ("sight_range", "Целик, дальность: 0 — «П», 1 — «8» (хомутик вперёд, планка с диоптром вверх)", 0.0),
    ("windage", "Целик, боковая поправка: 0,5 — середина", 0.5),
    ("sight_buttons", "Кнопки хомутика целика: 1 — сжаты", 0.0),
]


def drivers():
    """[(объект, свойство, индекс, выражение, [ползунки])] — углы в радианах, сдвиги в метрах."""
    T = CARRIER_TRAVEL
    cc = ["carrier", "cycle"]
    return [
        ("Bolt_Carrier", "delta_location", 0, f"-{T * MM:.6f}*{CF}", cc),
        ("Recoil spring • coil", "delta_scale", 0, f"1-{SPRING_SQUEEZE:.5f}*{CF}", cc),
        # затвор — ребёнок рамы: пока рама выбирает свободный ход и поворачивает его, он стоит на месте
        ("Bolt", "delta_location", 0, f"min({T * MM:.6f}*{CF}, {BOLT_LAG * MM:.6f})", cc),
        ("Bolt", "delta_rotation_euler", 0,
         f"{_deg(BOLT_UNLOCK_DEG)}*clamp(({T:.2f}*{CF}-{BOLT_FREE})/{BOLT_LAG - BOLT_FREE}, 0, 1)", cc),
        ("Chambered_Bullet", "delta_scale", 0, "max(live_round, 0.001)", ["live_round"]),
        ("Chambered_Bullet", "delta_scale", 1, "max(live_round, 0.001)", ["live_round"]),
        ("Chambered_Bullet", "delta_scale", 2, "max(live_round, 0.001)", ["live_round"]),
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
        ("Rear_Sight_Slider", "delta_location", 0, f"{SIGHT_RUN * MM:.6f}*sight_range", ["sight_range"]),
        ("Rear_Sight_Leaf", "delta_rotation_euler", 1, f"{_deg(SIGHT_LEAF_DEG)}*sight_range", ["sight_range"]),
        ("Rear_Sight_Drum", "delta_location", 1, f"{2 * WINDAGE * MM:.6f}*(windage-0.5)", ["windage"]),
        ("Rear_Sight_Knob", "delta_rotation_euler", 1, f"{2 * math.pi * 3:.5f}*(windage-0.5)", ["windage"]),
        ("Rear_Sight_Button_L", "delta_location", 1, f"-{SIGHT_BUTTON * MM:.6f}*sight_buttons", ["sight_buttons"]),
        ("Rear_Sight_Button_R", "delta_location", 1, f"{SIGHT_BUTTON * MM:.6f}*sight_buttons", ["sight_buttons"]),
    ]


def _ss(a, b, x):
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def _face(t):
    """X зеркала затвора при ходе рамы t (мм)."""
    return BOLT_FACE_X - max(0.0, t - BOLT_LAG)


def case_path(u):
    """Гильза из патронника при доле хода u: (dx, dy, dz мм; поворот вокруг Y и Z, рад; масштаб).
    До отражателя едет на зеркале затвора; после удара дульце уходит вправо-вверх, гильза вылетает в окно и пропадает."""
    T = CARRIER_TRAVEL
    t = T * u
    if t <= EJECT_AT:
        return -max(0.0, t - BOLT_LAG), 0.0, 0.0, 0.0, 0.0, 1.0
    e = (t - EJECT_AT) / (T - EJECT_AT)
    dx = -(EJECT_AT - BOLT_LAG) - 12.0 * e
    dz = 13.0 * _ss(0.0, 0.3, e) + 45.0 * e * e
    dy = -110.0 * _ss(0.08, 1.0, e)
    return dx, dy, dz, -math.radians(28.0) * _ss(0.0, 0.4, e), -math.radians(150.0) * _ss(0.0, 0.9, e), 1.0 - 0.999 * _ss(0.8, 1.0, e)


def extra(objs, ctrl, driver, curve_driver):
    """Приводы цикла, которым нужны места готовых деталей: гильза из патронника, стопка патронов, верхний патрон."""
    import numpy as np
    T = CARRIER_TRAVEL
    cc = ["carrier", "cycle"]
    N = 161
    # --- стреляная гильза (или патрон) из патронника ---
    case = objs.get("Chambered_Case")
    if case is not None:
        us = np.linspace(0.0, 1.0, N)
        rows = np.array([case_path(float(u)) for u in us])
        for i in range(3):
            curve_driver(case, "delta_location", i, CU, ctrl, cc, list(zip(us, rows[:, i] * MM)))
            curve_driver(case, "delta_scale", i, CU, ctrl, cc, list(zip(us, rows[:, 5])))
        curve_driver(case, "delta_rotation_euler", 1, CU, ctrl, cc, list(zip(us, rows[:, 3])))
        curve_driver(case, "delta_rotation_euler", 2, CU, ctrl, cc, list(zip(us, rows[:, 4])))
    if not (STACK_CENTER and TOP_BASE):
        return
    # --- стопка: утоплена затвором; свободна, когда гребень-досылатель ушёл назад за закраину верхнего патрона ---
    cx, cz = STACK_CENTER
    a = math.radians(STACK_FREE_DEG)
    ca, sa = math.cos(a), math.sin(a)

    def rise(p):
        # сдвиг точки p (X, Z) при повороте на добавочный угол вокруг центра дуги (плюс опускает то, что впереди центра)
        x, z = p[0] - cx, p[1] - cz
        return (x * ca + z * sa) - x, (-x * sa + z * ca) - z

    kx, kz = rise((TOP_BASE[0], TOP_BASE[2]))
    xs, ys, zs = TOP_BASE[0] + kx, TOP_BASE[1], TOP_BASE[2] + kz          # свободное положение верхнего патрона
    t_c = BOLT_FACE_X + BOLT_LAG + LUG_AHEAD - xs                          # ход рамы, при котором гребень у закраины
    a0, a1 = (t_c + 0.6) / T, min(0.999, (t_c + 3.6) / T)
    D = STACK_PUSH / 2.3                                                   # в долях свободного подъёма (2,3 мм)
    p0, p1 = PUSH_T0 / T, PUSH_T1 / T
    R = f"({1 + D:.4f}*smoothstep({a0:.5f},{a1:.5f},{CF})-{D:.4f}*smoothstep({p0:.5f},{p1:.5f},{CF}))"

    def off(cf):
        # положение стопки в долях свободного подъёма: 0 — под запертым затвором, −D — под гребнем, 1 — свободна
        return (1 + D) * _ss(a0, a1, cf) - D * _ss(p0, p1, cf)
    top = objs.get(TOP_ROUND[0])
    for name, o in objs.items():
        if not (name.startswith("Magazine • loaded") or name in ("Magazine_Follower",)) or name == TOP_ROUND[1]:
            continue
        M = o.matrix_world
        bb = [M @ __import__("mathutils").Vector(c) for c in o.bound_box]
        cxo = sum(v.x for v in bb) / 8.0 / MM; czo = sum(v.z for v in bb) / 8.0 / MM
        dx, dz = rise((cxo, czo))
        if o is top:
            # у верхнего патрона подъём стопки сидит на самих координатах (не на delta): delta занят путём досылания
            driver(o, "location", 0, f"{o.location.x:.7f}+{dx * MM:.7f}*{R}", ctrl, cc)
            driver(o, "location", 2, f"{o.location.z:.7f}+{dz * MM:.7f}*{R}", ctrl, cc)
        else:
            driver(o, "delta_location", 0, f"{dx * MM:.7f}*{R}", ctrl, cc)
            driver(o, "delta_location", 2, f"{dz * MM:.7f}*{R}", ctrl, cc)
    if top is None:
        return
    # --- досылание верхнего патрона на обратном ходе (вторая половина цикла) ---
    cs = np.linspace(0.0, 1.0, 2 * N - 1)
    out = []
    for c in cs:
        if c <= 0.5:
            out.append((0.0, 0.0, 0.0, 0.0)); continue
        t = T * (2.0 - 2.0 * c)                         # рама возвращается
        r = off(t / T)                                  # стопка под ним снова утапливается — это уже сидит в location
        push = _face(t) + LUG_AHEAD
        if push <= xs:
            out.append((0.0, 0.0, 0.0, 0.0)); continue
        s = min(1.0, (push - xs) / (CASE_BASE_X + (LUG_AHEAD - 0.05) - xs))
        x = xs + s * (CASE_BASE_X - xs)                 # гребень толкает дно; у патронника дно садится в чашечку
        # пока закраина под губками (до X ≈ 183, s ≈ 0,36), дно идёт прямо, а нос поднимается по скосу к патроннику;
        # дальше дно поднимается на ось ствола и патрон выравнивается
        y = ys * (1.0 - _ss(0.15, 0.6, s))
        z = zs * (1.0 - _ss(0.36, 0.95, s))
        pitch = TOP_PITCH + 5.7 * _ss(0.12, 0.42, s) - (TOP_PITCH + 5.7) * _ss(0.5, 1.0, s)
        out.append((x - TOP_BASE[0] - kx * r, y - TOP_BASE[1], z - TOP_BASE[2] - kz * r, math.radians(TOP_PITCH - pitch)))
    out = np.array(out)
    for i in range(3):
        curve_driver(top, "delta_location", i, "cycle", ctrl, ["cycle"], list(zip(cs, out[:, i] * MM)))
    curve_driver(top, "delta_rotation_euler", 1, "cycle", ctrl, ["cycle"], list(zip(cs, out[:, 3])))


# Крышка ригом не открывается: её передний шарнир на колодке собран по снимкам снаружи, механика подъёма (что
# поднимается вместе с крышкой и на какой угол) по образцу не видна — в клипах рук она не нужна.
# позы для проверочных кадров и проверки пересечений (рама отводится со снятым предохранителем)
FIRE = {"selector": SEL_AB}
POSES = {
    "ab": dict(FIRE),
    "two": {"selector": SEL_TWO},
    "single": {"selector": 1.0},
    "charged": dict(FIRE, carrier=1.0),
    "half": dict(FIRE, carrier=0.5),
    "cycle_unlock": dict(FIRE, cycle=0.03),
    "cycle_extract": dict(FIRE, cycle=0.25),
    "cycle_eject": dict(FIRE, cycle=0.40),
    "cycle_back": dict(FIRE, cycle=0.5),
    "cycle_strip": dict(FIRE, cycle=0.56),
    "cycle_feed": dict(FIRE, cycle=0.68),
    "cycle_ram": dict(FIRE, cycle=0.85),
    "cycle_done": dict(FIRE, cycle=1.0),
    "fire": {"trigger": 1.0},
    "catch": {"mag_catch": 1.0},
    "mag_out": {"mag_catch": 1.0, "mag": 1.0},
    "cover_button": {"cover_button": 1.0},
    "folded": {"stock_fold": 1.0, "hinge_latch": 1.0},
    "stock_long": {"stock_len": 1.0},
    "stock_lever": {"stock_lever": 1.0},
    "hg_latch": {"hg_latch": 1.0},
    "sight_far": {"sight_range": 1.0, "windage": 1.0, "sight_buttons": 1.0},
}
