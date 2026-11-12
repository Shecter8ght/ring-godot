# АСТЕН-919: полимерная рамка (литая, без острых кромок) и её стальные вкладыши. Боковой силуэт — обводка снимка
# владельца ref_23 (tools/asten919/trace_photo.py), выправленная вручную по сетке 5 мм; толщина меняется по месту:
# скоба 16 мм, рамка у затвора 26,2 мм, рукоять 30 мм; радиус кромки тоже по месту (рамка 1,3 мм, скоба 2,9 мм,
# рукоять 7–10 мм). Вырезы и карманы под органы управления — по их деталям (part_controls.py).
import math

import numpy as np

from dims import *
from sdf import *

BOTTOM_Z = -117.9
SLOPE = 0.43                      # наклон передней грани рукояти (dx/dz)
RIDGES = (-56.0, -72.0, -91.0, -108.5)     # границы выемок под пальцы (снимок ref_23)
GROOVE_D = 2.3
STUD_PITCH = 2.1
STUD_H = 0.42


def bb(x0, x1, y0, y1, z0, z1):
    return ((min(x0, x1), min(y0, y1), min(z0, z1)), (max(x0, x1), max(y0, y1), max(z0, z1)))


def xf(z):
    """Линия вершин рёбер передней грани рукояти."""
    return -16.0 + (z + 72.0) * SLOPE


def front_strap():
    pts = []
    for z in np.arange(-108.0, -56.9, 1.0):
        d = 0.0
        for a, b in zip(RIDGES, RIDGES[1:]):
            if b <= z <= a:
                t = (a - z) / (a - b)
                d = GROOVE_D * (1 - (2 * t - 1) ** 2)
        pts.append((xf(z) - d, float(z)))
    return pts


def outline():
    """Боковой контур рамки (X, Z): сверху, спереди и снизу продлён — там его обрезают плоскости и нижний резец."""
    p = [(-32.7, -130.0), (-32.7, -113.0), (-33.1, -110.0)]
    p += front_strap()
    p += [(-8.0, -55.0), (-6.3, -54.3), (-4.0, -54.6), (-1.0, -55.8), (3.0, -57.0), (8.0, -57.5), (20.0, -57.2),
          (35.0, -56.6), (44.5, -56.1), (46.4, -55.6), (46.9, -54.6), (46.2, -52.5), (44.9, -49.5), (44.4, -46.0),
          (44.3, -37.0), (44.9, -32.5), (46.6, -29.6), (49.5, -28.0), (53.0, -27.4), (106.3, -27.3), (108.6, -26.3),
          (118.0, -14.6), (118.0, 3.0), (-74.3, 3.0), (-74.4, -10.5), (-75.6, -13.2), (-75.9, -15.5), (-75.2, -17.8),
          (-73.6, -19.3), (-71.5, -19.2), (-69.3, -18.4), (-67.3, -18.5), (-65.2, -19.9), (-63.3, -22.2),
          (-61.3, -25.3), (-59.7, -29.0), (-58.6, -33.5), (-58.5, -37.0), (-59.4, -40.5), (-62.0, -47.5),
          (-64.5, -54.0), (-67.2, -60.0), (-70.0, -65.0), (-72.8, -70.0), (-75.5, -74.5), (-78.0, -79.0),
          (-80.2, -83.5), (-82.8, -89.0), (-85.3, -95.0), (-87.1, -100.0), (-88.4, -105.0), (-89.2, -110.0),
          (-89.7, -114.0), (-90.2, -130.0)]
    return smooth_closed(p, step=0.2, sigma=0.75)


def guard_hole():
    return fillet_poly([(38.2, -29.8), (2.5, -29.8), (-4.0, -37.5), (-4.0, -45.0), (3.5, -52.0), (38.2, -52.0)],
                       [5.5, 8, 8, 8, 6, 7], seg=12)


def bottom_cutter():
    p = [(-89.6, -112.0), (-89.3, -114.2), (-88.2, -116.0), (-86.4, -117.3), (-84.0, BOTTOM_Z), (-36.3, BOTTOM_Z),
         (-34.4, -117.5), (-33.0, -116.3), (-32.4, -114.5), (-25.0, -114.5), (-25.0, -140.0), (-100.0, -140.0),
         (-100.0, -112.0)]
    return p


OUTER = None
HOLE = None


def polys():
    global OUTER, HOLE
    if OUTER is None:
        OUTER = Poly(outline())
        HOLE = Poly(guard_hole())
    return OUTER, HOLE


def zones(X, Z):
    """Плавные доли зон по месту (X, Z): рукоять g, скоба m."""
    g = smoothstep((-14.0 - Z) / 26.0) * smoothstep((xf(Z) + 7.0 - X) / 9.0)
    m = smoothstep((-26.3 - Z) / 4.4) * smoothstep((X - (xf(Z) + 0.5)) / 6.5)
    return g, m


def half_width(X, Z):
    g, m = zones(X, Z)
    hw = FRAME_HW + (GRIP_HW - FRAME_HW) * g
    hw = hw * (1 - m) + GUARD_HW * m
    # выемка под большой палец над рукоятью (с обеих сторон)
    q = np.sqrt(((X + 30.0) / 24.0) ** 2 + ((Z + 30.2) / 6.8) ** 2)
    hw = hw - 1.0 * np.clip(1 - q * q, 0, 1) ** 2
    return hw


def edge_radius(X, Z):
    g, m = zones(X, Z)
    r_grip = 7.0 + 3.0 * smoothstep((xf(Z) - 20.0 - X) / 25.0)
    r = 1.3 + (r_grip - 1.3) * g
    r = r * (1 - m) + 2.9 * m
    # «бобровый хвост» мягче
    r = r + 2.0 * smoothstep((-62.0 - X) / 8.0) * smoothstep((Z + 27.0) / 6.0)
    return r


def body(X, Y, Z):
    """Сплошное тело рамки: силуэт × переменная полуширина, кромки по месту."""
    outer, hole = polys()
    d2 = np.maximum(outer.sd(X, Z), -hole.sd(X, Z))
    Xb, Zb = np.broadcast_arrays(X, Z)
    hw = half_width(Xb, Zb)
    r = np.minimum(edge_radius(Xb, Zb), hw - 0.6)
    if hw.shape[0] > 1:
        hx = float(X[1, 0, 0] - X[0, 0, 0]); hz = float(Z[0, 0, 1] - Z[0, 0, 0])
        gx = np.gradient(hw, hx, axis=0); gz = np.gradient(hw, hz, axis=2)
        k = 1.0 / np.sqrt(1.0 + gx * gx + gz * gz)
    else:
        k = 1.0
    dy = (np.abs(Y) - hw) * k
    return i_round(d2, dy, r)


def magwell(c=0.35, r=3.0, x_add=0.0):
    """Шахта магазина: сечение 33 × 22,4 + зазор, вдоль наклонной оси."""
    def f(X, Y, Z):
        a = (mag_front_x(Z) - X) * COS
        q1 = np.abs(a - MAG_DEPTH / 2) - (MAG_DEPTH / 2 + c + x_add - r)
        q2 = np.abs(Y) - (MAG_HW + c - r)
        return np.hypot(np.maximum(q1, 0), np.maximum(q2, 0)) + np.minimum(np.maximum(q1, q2), 0) - r
    return f


def rear_cavity():
    """Полость в рукояти позади шахты (открыта снизу)."""
    outer, _ = polys()

    def f(X, Y, Z):
        a = (mag_front_x(Z) - X) * COS
        d_wall = outer.sd(X, Z) + 3.2                     # 3,2 мм от спинки
        d_front = (MAG_DEPTH + 2.6) - a                   # перегородка 2,6 мм за шахтой
        d = i_round(np.maximum(d_wall, d_front), np.abs(Y) - 7.5, 2.0)
        return i_round(d, Z + 62.0, 3.0)
    return f


def housing_space(hw, wall, z0, x1=-28.0):
    """Место колодки спуска в задней части рамки: сзади — стенка толщиной wall от спинки."""
    outer, _ = polys()
    b = box_e((-90.0, -hw, z0), (x1, hw, 5.0), rx=1.5)

    def f(X, Y, Z):
        return i_round(b(X, Y, Z), outer.sd(X, Z) + wall, 1.5)
    return f


def catch_frame():
    """Оси кнопки защёлки магазина: вдоль рукояти (вниз-назад) и поперёк (назад-вверх)."""
    ax = np.array([-SIN, -COS])        # вдоль оси рукояти, вниз
    pr = np.array([-COS, SIN])         # поперёк, назад
    return ax, pr


def catch_rect(cx, cz, half_ax, half_pr, r=0.0):
    """Прямоугольник в плоскости XZ, повёрнутый по осям рукояти: поле по (X, Z)."""
    ax, pr = catch_frame()

    def f(X, Z):
        u = (X - cx) * ax[0] + (Z - cz) * ax[1]
        w = (X - cx) * pr[0] + (Z - cz) * pr[1]
        q1 = np.abs(u) - (half_ax - r); q2 = np.abs(w) - (half_pr - r)
        return np.hypot(np.maximum(q1, 0), np.maximum(q2, 0)) + np.minimum(np.maximum(q1, q2), 0) - r
    return f


CATCH_HEAD = (6.45, 5.3)               # полуразмеры кнопки: поперёк рукояти × вдоль


def catch_shank_center():
    """Перекладина защёлки — перед магазином, на высоте кнопки."""
    z = CATCH_C[1]
    return (mag_front_x(z) + 2.9 / COS, z)


def studs(X, Y, Z):
    """Пупырышки рукояти: смещение поверхности наружу (мм) — усечённые пирамидки с шагом 2,1 мм в осях рукояти.
    Пирамидка ставится целиком, если её центр попадает в поле: края полей ровные, без обрезков."""
    outer, _ = polys()
    ax, pr = catch_frame()
    X2, Z2 = np.broadcast_arrays(X, Z)
    s = X2 * ax[0] + Z2 * ax[1]            # вдоль рукояти
    u = X2 * pr[0] + Z2 * pr[1]            # поперёк (к спинке)
    sc = STUD_PITCH * np.round(s / STUD_PITCH); uc = STUD_PITCH * np.round(u / STUD_PITCH)
    yc = STUD_PITCH * np.round(Y / STUD_PITCH)

    def prof(da, db):
        return np.clip((0.62 - np.maximum(np.abs(da), np.abs(db))) / 0.25, 0, 1) * STUD_H

    # боковые поля: границы — по сетке пупырышков (прямые вдоль оси рукояти), верх — наклонно под выемкой под
    # большой палец, низ — горизонтально; площадка знака и место под кнопкой — без пупырышков
    Xc = sc * ax[0] + uc * pr[0]; Zc = sc * ax[1] + uc * pr[1]
    ok = ((uc > -4.5) & (uc < 30.5) & (sc > 54.0 + 0.267 * (uc - 6.2)) & (Zc > -105.5)
          & (np.maximum(np.abs(Xc - LOGO_C[0]) - 7.5, np.abs(Zc - LOGO_C[1]) - 6.4) > 0)
          & (catch_rect(CATCH_C[0], CATCH_C[1], 8.8, 7.6)(Xc, Zc) > 0))
    b_side = prof(s - sc, u - uc) * ok * smoothstep((np.abs(Y) - 9.0) / 0.5)
    # спинка и передняя грань: ряды вдоль рукояти и поперёк неё (по Y); центр ряда — на той же глубине
    Xs = X2 + (sc - s) * ax[0]; Zs = Z2 + (sc - s) * ax[1]
    d2 = outer.sd(X, Z)
    row = prof(s - sc, Y - yc)
    ok_back = (Zs < -44.0) & (Zs > -108.0) & (Xs < -50.0)
    b_back = row * ok_back * (np.abs(yc) < 5.6) * smoothstep((d2 + 9.0) / 0.8)
    ok_front = np.zeros(Zs.shape, bool)
    for a, b in zip(RIDGES, RIDGES[1:]):
        ok_front |= np.abs(Zs - (a + b) / 2) < (a - b) / 2 - 3.2
    d_front = xf(Z2) - GROOVE_D * 0.5 - X2
    b_front = row * ok_front * (np.abs(yc) < 10.6) * smoothstep((4.6 - d_front) / 0.8)
    return np.maximum(np.maximum(b_side, b_back), b_front)


def frame(h):
    F = Field("Frame", (-92.0, -GRIP_HW - 1.2, BOTTOM_Z - 1.0), (114.2, GRIP_HW + 3.2, DECK_Z + 1.0), h)
    polys()
    F.add(body)
    # обрезка: верх под затвором, перёд, низ с округлой пяткой
    F.apply(half("Z", DECK_Z, 1), "inter", 0.5)
    F.apply(half("X", SLIDE_X1, 1), "inter", 0.9, bbox=bb(108, 115, -20, 20, -30, 0))
    F.sub(prism(Poly(smooth_closed(bottom_cutter(), 0.2, 0.35)), "XZ", -40, 40), 1.3, bbox=bb(-92, -24, -20, 20, BOTTOM_Z - 1, -108))

    # --- шов сменной спинки: тонкая канавка вдоль спинки ---
    outer, _ = polys()

    def seam(X, Y, Z):
        d2 = outer.sd(X, Z)
        m = smoothstep((-41.0 - Z) / 2.0) * smoothstep((Z + 113.0) / 2.0) * smoothstep((-52.0 - X) / 2.0) * smoothstep((np.abs(Y) - 6.5) / 1.0)
        return -0.3 * np.exp(-((d2 + 8.6) / 0.33) ** 2) * m
    F.displace(seam, bbox=bb(-91, -55, -17, 17, -114, -40))
    # --- пупырышки рукояти ---
    F.displace(studs, bbox=bb(-92, -5, -17, 17, -112, -42))

    # --- литая площадка со знаком марки на щёчках рукояти (углубление, знак — вровень с поверхностью) ---
    for s_ in (1, -1):
        engrave(F, rect2(-6.6, 6.6, -5.5, 5.5, 1.6), "XZ", LOGO_C, -s_, s_ * GRIP_HW, s_, depth=0.4, wall=0.25,
                bbox=bb(LOGO_C[0] - 9, LOGO_C[0] + 9, s_ * 13.5, s_ * 16, LOGO_C[1] - 7.5, LOGO_C[1] + 7.5))
        engrave(F, sign2(7.8, 0.8), "XZ", LOGO_C, -s_, s_ * GRIP_HW, s_, depth=-0.4, wall=0.2,
                bbox=bb(LOGO_C[0] - 9, LOGO_C[0] + 9, s_ * 13.5, s_ * 16, LOGO_C[1] - 7.5, LOGO_C[1] + 7.5))

    # --- верх: жёлоб под «нос» затвора и возвратную пружину, полость под вкладыш и колодку ---
    chan = union(cyl("X", (0, GUIDE_Z - 0.4), 7.5, 26.0, 120.0), box((26.0, -7.5, GUIDE_Z - 0.4), (120.0, 7.5, 5.0), 0.0))
    F.sub(chan, 0.5, bbox=bb(25, 115, -9, 9, GUIDE_Z - 9, DECK_Z + 1))
    F.sub(box_e((-6.0, -8.3, -25.0), (30.0, 8.3, 5.0), rx=1.5, rz=1.5), 0.5, bbox=bb(-7, 31, -9.5, 9.5, -26, DECK_Z + 1))
    F.sub(housing_space(8.6, 3.0, -30.0), 0.5, bbox=bb(-70, -27, -9.5, 9.5, -31, DECK_Z + 1))
    # гнёзда под стойки направляющих вкладыша и колодки
    for s_ in (-1, 1):
        for xa, xb in ((16.6, 29.0), (-58.4, -45.1)):
            F.sub(box((xa, s_ * 8.0, -13.6), (xb, s_ * 9.75, 5.0), 0.3), 0.3, bbox=bb(xa - 1, xb + 1, s_ * 7.5, s_ * 10.5, -14.5, DECK_Z + 1))
    # --- шахта магазина (сквозная) и полость позади неё ---
    F.sub(magwell(), 0.6, bbox=bb(-80, 8, -12.5, 12.5, BOTTOM_Z - 1, DECK_Z + 1))
    F.sub(rear_cavity(), 0.8, bbox=bb(-90, -60, -9, 9, BOTTOM_Z - 1, -58))
    # --- проём спускового крючка ---
    F.sub(box_e((-4.3, -3.9, -37.5), (17.0, 3.9, -15.5), rz=2.0), 0.6, bbox=bb(-5.5, 18.5, -5, 5, -38.5, -14.5))
    # --- оси ---
    for (px, pz), rr in ((PIN_TRIGGER, 2.02), (PIN_BLOCK, 1.52), (PIN_HOUSING, 2.02)):
        F.sub(cyl("Y", (px, pz), rr, -30, 30), 0.25, bbox=bb(px - 3, px + 3, -17, 17, pz - 3, pz + 3))
    # --- защёлка затвора: сквозной паз с наклоном и лунки под пальцы с обеих сторон ---
    lx, lz = LOCK_C
    slot = rot(box((lx - 1.3, -30, lz - 5.0 - LOCK_DOWN - 0.2), (lx + 1.3, 30, lz + 5.0), 0.3), "Y", (lx, 0, lz), LOCK_DEG)
    F.sub(slot, 0.3, bbox=bb(lx - 6, lx + 5, -15, 15, lz - 10, lz + 7))
    for s in (-1, 1):
        F.sub(sphere((lx - 0.5, s * (FRAME_HW + 24.4), lz - 0.5), 26.1), 0.9, bbox=bb(lx - 12, lx + 11, s * 9, s * 14.5, lz - 12, DECK_Z + 1))
    # --- затворная задержка (слева): щель под рычаг внутри стенки, окно под перемычку, площадка под рычаг, полка ---
    (px0, px1), (pz0, pz1) = (STOP_PAD[0], STOP_PAD[1])
    F.sub(box((-23.6, 9.75, -16.1), (6.5, 11.8, 5.0), 0.3), 0.3, bbox=bb(-26.5, 7.5, 9, 13, -17.5, DECK_Z + 1))
    F.sub(box((-0.5, 9.75, -24.8), (14.8, 11.8, 5.0), 0.3), 0.3, bbox=bb(-1.5, 16, 9, 13, -26, DECK_Z + 1))
    F.sub(box((1.8, 7.9, -12.7), (6.6, 10.4, 5.0), 0.3), 0.3, bbox=bb(1, 7.5, 7, 11, -13.8, DECK_Z + 1))
    F.sub(box((px0 - 0.5, 10.9, -16.1), (px1 + 1.4, 20.0, 5.0), 0.4), 0.4, bbox=bb(px0 - 2, px1 + 3, 10.4, 16, -17.5, DECK_Z + 1))
    F.sub(box((px0 - 1.8, FRAME_HW - 0.7, pz0 - 1.0), (px1 + 2.4, 20.0, 5.0), 1.3), 0.6, bbox=bb(px0 - 4, px1 + 4, 11.5, 16, pz0 - 2.5, DECK_Z + 1))
    F.add(box((px0 - 2.2, FRAME_HW - 2.0, pz0 - 3.4), (px1 + 2.8, FRAME_HW + 1.2, pz0 - 1.15), 0.7), 0.7,
          bbox=bb(px0 - 4.5, px1 + 5, 11, 16, pz0 - 5.5, pz0 + 0.3))
    # --- защёлка магазина: карман под кнопку слева (с ходом 2,5 мм), сквозное окно перекладины перед магазином ---
    cx, cz = CATCH_C
    sx, sz = catch_shank_center()
    pocket = catch_rect(cx, cz, CATCH_HEAD[1] + 0.3, CATCH_HEAD[0] + 0.3, 1.6)
    F.sub(lambda X, Y, Z: i_round(pocket(X, Z), 12.3 - Y, 0.5), 0.5, bbox=bb(cx - 10, cx + 10, 11.3, 18.5, cz - 10, cz + 10))
    # закрытый канал перемычки под наружной стенкой (с запасом на ход кнопки внутрь)
    tunnel = catch_rect(sx - 2.75, sz, 2.5, 2.2, 0.5)
    F.sub(lambda X, Y, Z: np.maximum(tunnel(X, Z), np.abs(Y - 11.05) - 2.35), 0.0, bbox=bb(sx - 7, sx + 2, 8, 14, sz - 5, sz + 5))
    shank = catch_rect(sx, sz, 2.9, 2.3, 0.6)
    F.sub(lambda X, Y, Z: np.maximum(shank(X, Z), Y - 11.6), 0.35, bbox=bb(sx - 5, sx + 5, -17, 13, sz - 5, sz + 5))
    # гнездо под зацеп справа (зацеп уходит в стенку при нажатии кнопки)
    ax_, pr_ = catch_frame()
    ledge = catch_rect(sx + pr_[0] * 2.7, sz + pr_[1] * 2.7, 2.5, 1.25, 0.4)
    F.sub(lambda X, Y, Z: np.maximum(ledge(X, Z), np.abs(Y + 11.4) - 2.2), 0.0, bbox=bb(sx - 7, sx + 2, -14.5, -8.5, sz - 5, sz + 5))
    # --- планка под фонарь: поперечный паз снизу и продольные пазы по бокам ---
    F.sub(box((87.6, -30, -40.0), (92.0, 30, -24.9), 0.4), 0.4, bbox=bb(86.5, 93, -15, 15, -29, -24))
    rail = box((56.5, FRAME_HW - 1.5, -21.7), (125.0, 30.0, -19.2), 1.1)
    F.sub(both(rail), 0.35, bbox=bb(55, 115, -15, 15, -23, -18))
    # --- гнездо пластины с номером снизу, перед скобой ---
    F.sub(box((61.0, -3.7, -40.0), (84.0, 3.7, -26.45), 0.3), 0.25, bbox=bb(60, 85, -5, 5, -28.5, -25.5))
    # --- рифление передней грани скобы ---
    for k in range(7):
        z = -34.5 - k * 2.3
        F.sub(box((43.6, -5.6, z - 0.55), (60.0, 5.6, z + 0.55), 0.3), 0.2, bbox=bb(43, 48, -7, 7, z - 1.2, z + 1.2))
    return F


def locking_block(h):
    """Стальной вкладыш с передними направляющими: виден сверху при отведённом затворе."""
    F = Field("Locking_Block", (-6.5, -11.3, -25.5), (30.5, 11.3, -5.6), h)
    F.add(box_e((-5.6, -8.0, -24.6), (29.6, 8.0, -12.2), rx=0.6, ry=0.6, rz=1.2))
    # гнездо под прилив ствола и наклонная площадка отпирания
    F.sub(box_e((-2.5, -4.7, -21.8), (40.0, 4.7, 0.0), rx=1.0, ry=1.5), 0.4)
    F.sub(magwell(c=0.5), 0.4)
    ramp = Poly([(-6, -12.0), (4.5, -12.0), (11.0, -19.6), (11.0, -30), (-6, -30)])
    F.sub(prism(ramp, "XZ", -4.6, 4.6), 0.4)
    F.sub(box_e((-7.0, -3.9, -30.0), (16.0, 3.9, -17.0), rz=1.5), 0.3)
    # передние направляющие: стойки и полки наружу
    for s in (-1, 1):
        F.add(box((17.0, s * 7.6, -13.2), (28.6, s * 9.5, -12.2), 0.3), 0.3)
        F.add(box((17.0, s * 8.85, -13.2), (28.6, s * 9.5, -7.05), 0.25), 0.3)
        F.add(box((17.0, s * 8.85, -8.25), (28.6, s * 10.85, -7.05), 0.25), 0.25)
    F.sub(cyl("Y", PIN_BLOCK, 1.52, -20, 20), 0.2)
    F.sub(cyl("Y", PIN_TRIGGER, 2.02, -20, 20), 0.2)
    lx, lz = LOCK_C
    F.sub(rot(box((lx - 1.3, -30, lz - 5.0 - LOCK_DOWN - 0.2), (lx + 1.3, 30, lz + 5.0), 0.3), "Y", (lx, 0, lz), LOCK_DEG), 0.2)
    return F


def trigger_housing(h):
    """Колодка спускового механизма в задней части рамки (полимер) с задними направляющими."""
    F = Field("Trigger_Housing", (-66.5, -11.3, -30.5), (-27.5, 11.3, -6.4), h)
    polys()
    F.add(housing_space(8.3, 3.4, -29.6, x1=-33.0))
    F.apply(half("Z", -12.4, 1), "inter", 0.8)
    # жёлоб посередине (тяга, зуб ударника)
    F.sub(box_e((-80.0, -3.0, -19.0), (-25.0, 3.0, 0.0), rx=0.8), 0.4)
    # передняя стенка скошена под магазин
    F.sub(magwell(c=0.5), 0.4)
    for s in (-1, 1):
        F.add(box((-58.0, s * 7.6, -13.2), (-45.5, s * 9.5, -12.4), 0.3), 0.3)
        F.add(box((-58.0, s * 8.85, -13.2), (-45.5, s * 9.5, -7.05), 0.25), 0.3)
        F.add(box((-58.0, s * 8.85, -8.25), (-45.5, s * 10.85, -7.05), 0.25), 0.25)
    F.sub(cyl("Y", PIN_HOUSING, 2.02, -20, 20), 0.2)
    return F


def ejector(h):
    """Отражатель: гнутая стальная пластина слева на колодке, остриё — у зеркала затвора."""
    F = Field("Ejector", (-45.5, 4.2, -14.0), (-28.0, 7.3, -4.4), h)
    side = Poly(fillet_poly([(-44.5, -13.2), (-36.0, -13.2), (-29.2, -7.3), (-28.8, -5.3), (-30.6, -5.2), (-36.5, -9.6), (-44.5, -9.6)],
                            [0.5, 1.5, 0.4, 0.4, 0.5, 2.0, 0.5]))
    F.add(prism(side, "XZ", 5.0, 6.5, rim=0.3))
    return F


def serial_plate(h):
    """Стальная пластина с номером в рамке снизу."""
    F = Field("Serial_Plate", (60.6, -4.1, -27.8), (84.4, 4.1, -26.0), h)
    F.add(box((61.1, -3.6, -27.2), (83.9, 3.6, -26.5), 0.2))
    ser, ws = text2(MARK_SERIAL, font_path(True), 2.2, track=0.2)
    engrave(F, ser, "XY", (72.5 + ws / 2, -1.1), -1, -27.2, -1, depth=0.14, wall=0.1)
    return F


def parts():
    return [
        dict(name="Frame", build=frame, h=0.125, coll="Frame", mat="Polymer", weight=40, adapt=0.08),
        dict(name="Locking_Block", build=locking_block, h=0.08, coll="Frame", mat="Steel_black", parent="Frame", weight=2),
        dict(name="Trigger_Housing", build=trigger_housing, h=0.08, coll="Frame", mat="Polymer", parent="Frame", weight=2),
        dict(name="Ejector", build=ejector, h=0.05, coll="Frame", mat="Steel_bare", parent="Trigger_Housing"),
        dict(name="Serial_Plate", build=serial_plate, h=0.04, coll="Frame", mat="Steel_bare", parent="Frame"),
    ]
