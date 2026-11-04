# ПП по мотивам KRISS Vector Gen II: профили деталей из перенесённого силуэта (trace_photos.py → silhouette_A.json).
# Силуэт снимка растеризуется в мм (RES пикс/мм), пересекается с областями деталей (линии швов со снимков, мм модели)
# и обводится снова — так наружный край каждой детали берётся со снимка, а не рисуется «на глаз».
#   python -X utf8 tools/smg03/profiles.py <папка trace>
# Пишет profiles.json (контуры деталей и отверстия, мм) и profiles_overlay.png (контуры на снимке A).
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

RES = 10.0                       # пикс/мм растра
X0, X1, Z0, Z1 = -300.0, 150.0, -260.0, 75.0

# ---- линии швов и границы (мм модели, сняты с участков снимков g3A_*/g3B_*) ----
SEAM_Z = 15.0                    # низ корпуса (ствольной коробки) над шахтой (с правой стороны — по низу окна выброса)
SEAM_REAR_Z = 15.0               # позади проёма скобы — тот же уровень: верх проёма скобы вырезан в коробке
RAIL_BASE_Z = 51.0               # верх корпуса под планкой (по кромкам снимков A/B планка до Z 57.5 — проверка 04.11)
FRONT_LOW_Z = -21.0              # низ переднего блока над нижней планкой
FRONT_BLOCK_REAR_X = 22.0        # задняя грань переднего блока внизу (дальше — оребрённый перёд шахты)
FRONT_FACE_X = 107.8
REAR_X = -266.0                  # задний торец коробки (дальше — шарнир приклада)
# линия между корпусом шахты и спусковой коробкой: дуга от шва вниз, затем вдоль заднего края шахты
# задний прилив снизу коробки (позади выреза за рукоятью) — часть коробки
TANG_X = -240.0
TANG_Z = 8.0
SEAM_STEP_X = -112.0             # передний верхний угол проёма скобы: шаг шва 15 → 17.5
# по снимку: шов касательно уходит с горизонтали Z 15 у X −78 дугой R 28 и дальше прямой под 21° от вертикали
# (параллельно магазину) до низа у оси (−143.5, −105.7)
PANEL_START_X = -78.0
PANEL_R = 28.0
PANEL_DEG = 21.2                 # прямая после дуги — от вертикали назад


def _panel_line():
    turn = math.radians(90.0 - PANEL_DEG)
    cx, cz = PANEL_START_X, SEAM_Z - PANEL_R
    pts = [(cx - PANEL_R * math.sin(turn * k / 10), cz + PANEL_R * math.cos(turn * k / 10)) for k in range(11)]
    ex, ez = pts[-1]
    t = (ez - (-112.0)) / math.cos(math.radians(PANEL_DEG))
    pts.append((ex - t * math.sin(math.radians(PANEL_DEG)), -112.0))
    return [(round(x, 2), round(z, 2)) for x, z in pts]


PANEL_LINE = _panel_line()
MAG_TOP_Z = -110.0               # низ шахты (горловина) — ниже магазин
BAR_TOP_Z = -107.5               # верх нижней тяги спусковой коробки под шахтой (от X −78 назад)
BAR_FRONT_X = -78.0
# спуск — отдельная деталь: вырезаем его из спусковой коробки
CLOSE_MM = {"magwell": 2.6, "trigger_housing": 2.2}
# части спусковой коробки (вид сбоку): рукоять — позади переда рукояти и ниже верха скобы; перекладина скобы — между
# проёмом скобы и окном для пальцев
STRIP_ZONE = [(-60.0, 30.0), (-150.0, 30.0), (-150.0, -200.0), (-60.0, -200.0)]
GRIP_ZONE = [(-150.0, 30.0), (-300.0, 30.0), (-300.0, -200.0), (-150.0, -200.0)]
# нижняя тяга: от горловины шахты (X −76, под корпусом шахты) до низа рукояти — тонкая (6–8 мм), своим телом
BAR_ZONE = [(-76.0, -104.0), (-140.0, -104.0), (-140.0, -72.0), (-204.0, -72.0), (-214.0, -86.0), (-214.0, -140.0),
            (-76.0, -140.0)]
# перекладина скобы — только ниже кончика спуска (Z −10.7): к рукояти примыкает под крючком, вверх по ней не идёт
GUARD_ZONE = [(-130.0, -8.0), (-176.0, -11.5), (-176.0, -26.0), (-130.0, -34.0)]
OVERLAP = 3.0
# радиус скругления углов контура в плоскости — с запасом над радиусом кромок в 3D (rounded_prism): иначе во
# вогнутых углах кольца сдвига сходятся в точку, грани вырождаются и булевы EXACT ломаются
ROUND_MM = {"upper": 3.8, "magwell": 4.4, "trigger_housing": 3.4, "trigger": 1.6}


def round_mask(m, r):
    if r <= 0:
        return m
    k = int(round(r * RES)) * 2 + 1
    el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, el)
    return cv2.morphologyEx(m, cv2.MORPH_CLOSE, el)
TRIGGER_CUT = [(-139.0, 16.5), (-171.0, 16.5), (-171.0, -4.0), (-163.0, -10.0), (-152.0, -12.6),
               (-139.0, -12.6)]


def to_px(x, z):
    return int(round((x - X0) * RES)), int(round((Z1 - z) * RES))


def to_mm(px, py):
    return round(px / RES + X0, 3), round(Z1 - py / RES, 3)


def poly_mask(pts, shape):
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.array([to_px(x, z) for x, z in pts], np.int32)], 255)
    return m


def silhouette_mask(sil, shape):
    m = poly_mask(sil["outer"], shape)
    for h in sil["holes"]:
        m[poly_mask(h, shape) > 0] = 0
    return m


def contours(m, eps_mm=0.12, min_area_mm2=4.0):
    cnts, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    if hier is None:
        return out
    for i, c in enumerate(cnts):
        if hier[0][i][3] >= 0:
            continue
        if cv2.contourArea(c) < min_area_mm2 * RES * RES:
            continue
        holes = []
        k = hier[0][i][2]
        while k >= 0:
            if cv2.contourArea(cnts[k]) >= min_area_mm2 * RES * RES:
                holes.append(simplify(cnts[k], eps_mm))
            k = hier[0][k][0]
        out.append({"outer": simplify(c, eps_mm), "holes": holes})
    return out


def simplify(c, eps_mm):
    # сглаживание лестницы растра (скользящее среднее по контуру), затем упрощение с допуском eps
    p = c[:, 0, :].astype(float)
    n = len(p)
    k = 5
    sm = np.array([p[(np.arange(i - k, i + k + 1)) % n].mean(0) for i in range(n)])
    ap = cv2.approxPolyDP(sm.astype(np.float32).reshape(-1, 1, 2), eps_mm * RES, True)[:, 0, :]
    return [to_mm(px, py) for px, py in ap]


def regions():
    upper = [(FRONT_FACE_X, RAIL_BASE_Z), (FRONT_FACE_X, FRONT_LOW_Z), (FRONT_BLOCK_REAR_X, FRONT_LOW_Z),
             (FRONT_BLOCK_REAR_X, SEAM_Z), (SEAM_STEP_X, SEAM_Z), (SEAM_STEP_X, SEAM_REAR_Z), (TANG_X, SEAM_REAR_Z),
             (TANG_X, TANG_Z), (REAR_X, TANG_Z), (REAR_X, RAIL_BASE_Z)]
    # корпус шахты: под швом, позади переднего блока, перед линией панели; снизу — горловина, затем верх тяги
    # спусковой коробки; обход — по часовой: шов → перёд → горловина → тяга → вверх по линии панели
    tail = [p for p in PANEL_LINE if p[1] >= BAR_TOP_Z]
    a, b = PANEL_LINE[-2], PANEL_LINE[-1]
    t = (BAR_TOP_Z - a[1]) / (b[1] - a[1])
    bar_pt = (a[0] + (b[0] - a[0]) * t, BAR_TOP_Z)        # линия панели на высоте верха тяги
    magwell = [(FRONT_BLOCK_REAR_X, SEAM_Z), (FRONT_BLOCK_REAR_X, FRONT_LOW_Z), (40.0, FRONT_LOW_Z), (40.0, -60.0),
               (0.0, MAG_TOP_Z),
               (BAR_FRONT_X, MAG_TOP_Z), (BAR_FRONT_X, BAR_TOP_Z), bar_pt] + list(reversed(tail))
    # спусковая коробка: всё позади линии панели и под швом, плюс нижняя тяга под шахтой до X −78
    trigger = tail + [bar_pt, (BAR_FRONT_X, BAR_TOP_Z),
                                                     (BAR_FRONT_X, -117.0), (REAR_X, -117.0), (REAR_X, TANG_Z),
                                                     (TANG_X, TANG_Z), (TANG_X, SEAM_REAR_Z),
                                                     (SEAM_STEP_X, SEAM_REAR_Z), (SEAM_STEP_X, SEAM_Z)]
    return {"upper": upper, "magwell": magwell, "trigger_housing": trigger}


def main():
    d = Path(sys.argv[1])
    sil = json.loads((d / "silhouette_A.json").read_text(encoding="utf-8"))
    shape = (int((Z1 - Z0) * RES), int((X1 - X0) * RES))
    sm = silhouette_mask(sil, shape)
    out = {"res": RES, "seam_z": SEAM_Z, "seam_rear_z": SEAM_REAR_Z, "seam_step_x": SEAM_STEP_X, "rail_base_z": RAIL_BASE_Z, "front_low_z": FRONT_LOW_Z,
           "front_face_x": FRONT_FACE_X, "rear_x": REAR_X, "panel_line": PANEL_LINE, "parts": {}}
    regs = regions()
    masks = {}
    raw = {}
    for nm, reg in regs.items():
        m = cv2.bitwise_and(sm, poly_mask(reg, shape))
        if nm == "trigger_housing":
            m[poly_mask(TRIGGER_CUT, shape) > 0] = 0
        # рифление переда шахты и рукояти на снимке даёт зубцы по краю силуэта: закрываем впадины кругом (огибающая
        # по вершинам рёбер), сами рёбра режутся в 3D отдельно
        r = CLOSE_MM.get(nm, 0.0)
        if r > 0:
            k = int(round(r * RES)) * 2 + 1
            m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
            m = cv2.bitwise_and(m, poly_mask(reg, shape))
        # углы контура скругляем в плоскости (открытие + закрытие кругом ROUND_MM): острых углов сбоку нет, и фаска
        # кромок в 3D не упирается в радиус меньше своей ширины
        # шов между отдельными деталями — тонкая щель 0.3 мм (каждая сжата на 0.15): без совпадающих граней
        m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        raw[nm] = m.copy()
        m = round_mask(m, ROUND_MM.get(nm, 0.0))
        masks[nm] = m
        out["parts"][nm] = contours(m)
    # спусковая коробка — тремя телами разной ширины (из нескруглённой маски: тонкие тяги скругление съедает):
    # передняя тяга вдоль шва шахты (вровень с шахтой, 43.5 мм), рукоять с нижней тягой и приливом над рукоятью (31 мм),
    # перекладина скобы (13 мм); соседние тела заходят друг в друга на OVERLAP мм — объединение без совпадающих граней
    th = raw["trigger_housing"]
    k = int(round(OVERLAP * RES)) * 2 + 1
    el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    strip_z = poly_mask(STRIP_ZONE, shape)
    grip_z = poly_mask(GRIP_ZONE, shape)
    guard_z = poly_mask(GUARD_ZONE, shape)
    strip = cv2.bitwise_and(th, strip_z)
    strip[guard_z > 0] = 0
    out["parts"]["th_strip"] = contours(round_mask(strip, 4.2))
    bar_z = poly_mask(BAR_ZONE, shape)
    grip_only = grip_z.copy()
    grip_only[bar_z > 0] = 0
    grip = cv2.bitwise_and(th, cv2.dilate(grip_only, el))
    grip[guard_z > 0] = 0
    out["parts"]["th_grip"] = contours(round_mask(grip, 6.0))
    bar = cv2.bitwise_and(th, cv2.dilate(bar_z, el))
    out["parts"]["th_bar"] = contours(round_mask(bar, 2.9))
    out["parts"]["th_guard"] = contours(round_mask(cv2.bitwise_and(th, cv2.dilate(guard_z, el)), 2.4))
    # корпус одним телом (проверка 04.11: на стыке трёх скруглённых корпусов оставалась сквозная щель): коробка, шахта и
    # передняя тяга — один контур, швы потом — тонкими канавками; рукоять с нижней тягой («петля») — второй контур
    kk = int(round(1.0 * RES)) * 2 + 1
    elc = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kk, kk))
    body = cv2.bitwise_or(cv2.bitwise_or(raw["upper"], raw["magwell"]), strip)
    body = cv2.morphologyEx(body, cv2.MORPH_CLOSE, elc)
    out["parts"]["body"] = contours(round_mask(body, 3.8))
    out["parts"]["body_r11"] = contours(round_mask(body, 11.0))
    loop = cv2.bitwise_and(th, cv2.dilate(cv2.bitwise_or(grip_z, bar_z), el))
    loop[guard_z > 0] = 0
    loop[strip_z > 0] = cv2.bitwise_and(loop, bar_z)[strip_z > 0]
    out["parts"]["th_loop"] = contours(round_mask(loop, 3.2))
    # окно петли (отверстие силуэта между передней тягой, перекладиной скобы, рукоятью и нижней тягой), ужатое на 2.5 мм
    box = poly_mask([(-120.0, -16.0), (-215.0, -16.0), (-215.0, -110.0), (-120.0, -110.0)], shape)
    hole = cv2.bitwise_and(cv2.bitwise_not(sm), box)
    k25 = int(round(2.5 * RES)) * 2 + 1
    hole = cv2.erode(hole, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k25, k25)))
    out["parts"]["hand_hole"] = contours(hole)
    # спуск — часть силуэта внутри TRIGGER_CUT
    m = round_mask(cv2.bitwise_and(sm, poly_mask(TRIGGER_CUT, shape)), ROUND_MM["trigger"])
    out["parts"]["trigger"] = contours(m, eps_mm=0.08, min_area_mm2=1.0)
    # магазин 30 (KRISS, как на снимке) — ниже горловины
    m = cv2.bitwise_and(sm, poly_mask([(10, MAG_TOP_Z), (-150, MAG_TOP_Z), (-150, -260), (10, -260)], shape))
    out["parts"]["magazine_photo"] = contours(m)
    (d / "profiles.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8", newline="\n")
    # наложение на снимок A
    src = d.parent / "refs" / "web" / "kriss_usa" / "orig_kv_sbr_5_5in_blk_30rd_A__83111.1707345817.jpg"
    img = cv2.imdecode(np.fromfile(str(src), np.uint8), cv2.IMREAD_COLOR)
    S, BY, MX = 1.797, 451.5, 256.0
    x0 = MX + 139.7 * S
    k = 3
    big = cv2.resize(img, None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
    cols = {"upper": (0, 0, 255), "magwell": (0, 170, 0), "trigger_housing": (255, 0, 0), "trigger": (0, 200, 255),
            "magazine_photo": (200, 0, 200), "th_strip": (255, 120, 0), "th_grip": (120, 0, 255), "th_guard": (0, 120, 255), "th_bar": (0, 200, 120), "body": (0, 0, 0), "th_loop": (0, 90, 0), "hand_hole": (0, 200, 200), "body_r11": (90, 90, 90)}
    for nm, items in out["parts"].items():
        for it in items:
            for poly in [it["outer"]] + it["holes"]:
                pts = np.array([((x0 - x * S) * k, (BY - z * S) * k) for x, z in poly], np.int32)
                cv2.polylines(big, [pts], True, cols[nm], 1, cv2.LINE_AA)
    ok, buf = cv2.imencode(".png", big)
    buf.tofile(str(d / "profiles_overlay.png"))
    for nm, items in out["parts"].items():
        print(nm, [(len(it["outer"]), len(it["holes"])) for it in items])


main()
