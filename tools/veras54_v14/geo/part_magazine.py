# ВЕРАС-54 v14: магазин на 30 патронов по образцу (полимерный «вафельный» магазин АК-12 2018 года) — корпус с рисунком
# боков, окнами-указателями и цифрами, «лесенкой» на спинке, рёбрами спереди, скошенной пяткой; крышка, подаватель,
# пружина.
# Снято с мозаики плиток правого и левого бока (trace/mag/my_R12.png, my_L12.png — 12 пикс/мм, глубина 13) и с её
# развёртки в полярных координатах (trace/mag/polar.py): рисунок бока образца — прямоугольники в координатах (радиус ρ,
# угол ψ) вокруг одной точки CP, т. е. ряды повёрнуты друг относительно друга вокруг неё на 4,48°. Низ — R_x-0.02_z0.07,
# крышка снизу — U_x0.02, спинка снизу — U_x-0.09, перед — F_z0.25, объём — P07, P08, P11, Q03.
import math

import numpy as np

from dims import *
from sdf import *

# ---------------- оси и дуги (мм ВЕРАС) ----------------
CF, RF = (494.3, -20.3), 278.2        # передняя кромка — дуга (подгонка по силуэту Z −80…−180, отклонение 0,5)
C2, R2 = (630.42, 36.95), 491.3       # задний силуэт (торцы рёбер «лесенки») — дуга (Z −82…−212, отклонение 0,4)
CP = (499.8, -7.5)                    # центр развёртки рисунка бока (окна на одной окружности, столбцы ровные)
TILT = 0.0068                         # рисунок чуть повёрнут в развёртке: ψ' = ψ − TILT·(ρ − 326), °/мм
RHO0 = 326.0                          # радиус отсчёта: V = ψ'·RHO0·π/180 — мм вдоль ряда у середины бока
KV = RHO0 * math.pi / 180.0

HW = 14.5                             # полуширина корпуса по полю бока (F_z0.25: ±15 с закруглением передней грани)
FRONT_R = 2.6                         # скругление передней грани (F_z0.25: плоская ±12)
SPINE_HW = 13.5                       # «лесенка» на спинке уже корпуса (U_x-0.09: ±13,5)
SPINE_C = 5.0                         # средняя полоса спинки (U_x-0.09: ±5)
NECK_HW = 13.6                        # горловина в шахте (окно шахты MAGWELL_HW 14,2)
CAV_HW = 9.3                          # полость под патроны: патроны v13 по |Y| до 8,75
D_POCKET = 0.9                        # глубина «вафель» и желобов (оценка по теням P07, Q03)
SH_Z = -34.6                          # плечо корпуса под ствольной коробкой (R_x-0.10_z0.20)
REAR_X = 144.0                        # задняя грань прилива у защёлки (стойка защёлки — до X 143,6)
NECK_X0, NECK_X1 = 148.6, 205.9       # горловина: задняя (окно шахты с X 148) и передняя стенки
CAV_X0, CAV_X1 = 150.6, 204.5         # полость в горловине: донца патронов с X 151,5, пули — до X 204,1
PSI_B = 36.95                         # дно корпуса — радиус под углом ψ_B (R_x-0.02_z0.07, развёртка)
PSI_RAIL = 35.86                      # верх бортика над крышкой
PSI_P = 37.45                         # низ крышки
HEEL_Z = -212.5                       # пятка: низ крышки сзади горизонтален (R_x-0.02_z0.07)
HEEL_A, HEEL_B = (207.2, -209.9), (224.1, -206.7)    # скос пятки корпуса: кромка над крышкой (развёртка, ψ 34,7 → 35,9)
RHO_STEP = 340.0                      # задний конец бортика и плоской части крышки
FP_HW = 15.3                          # полуширина крышки и бортика (U_x0.02)

# ряды «вафель» (развёртка вокруг CP, ψ' в градусах; ρ — мм)
ROW_PITCH = 4.48
ROW1_TOP = 12.42
ROW_H = 2.72
POCKET_U = [(335.5, 346.6), (320.6, 331.4), (305.8, 316.3)]   # столбцы: задний, средний, с цифрой
WIN_U = (293.6, 301.0)                # окна-указатели
DRIFT_U = 0.25                        # ряды ниже чуть сдвинуты назад по ρ (мм на ряд)
NUMS = ["10", "15", "20", "25", "30", None]
DIGIT_H = 4.4                         # высота цифр (R_x-0.10_z0.20, крупно: тонкие, ≈ 4,4 мм)
# ряд 0 под плечом: верх «вафель» скошен (ρ, ψ' слева и справа)
ROW0 = [((346.6, 9.40), (335.5, 9.02)), ((331.4, 8.50), (320.6, 8.30)), ((316.3, 7.76), (305.8, 7.35))]
ROW0_TOP, ROW0_BOT = 7.94, 10.65
# «лесенка» спинки: рёбра по ψ (вокруг CP), толщина ребра
LAD_PSI0, LAD_STEP, LAD_N = 13.28, 2.32, 9
LAD_RIB = 2.0
# пазы на передней грани вверху (Z середины, ширина) — R_x-0.10_z0.20 у передней кромки, F_z0.25
FRONT_SLOTS = [(-46.0, 2.0), (-50.8, 3.6), (-56.3, 2.4), (-85.3, 2.0)]
FRONT_SLOT_D = 1.8
# зацепы: задний выступ над зубом защёлки (зуб part_controls: верх (142,6; −49,4) … (144,5; −49,9))
LUG_X0, LUG_Z0, LUG_Z1, LUG_HW = 142.9, -49.1, -45.6, 5.5
NOTCH_X, NOTCH_Z0, NOTCH_HW = 145.2, -56.6, 8.2      # выемка под зуб и лицо защёлки
HOOK = (NECK_X1, 227.4, -30.65, -27.2, 6.0)          # передний зацеп над передней кромкой окна шахты (лист Z −31)
# стопка патронов v13 поднята вдоль своей дуги (центр — подгонка по донцам 30 патронов, отклонение 0,9): в сборке
# патроны поворачиваются вокруг оси Y через STACK_C по часовой (вид справа) на STACK_DEG — «затвор впереди, стопка
# утоплена»: верх патрона 1 на Z −8,7; ещё на STACK_FREE_DEG (2,3 мм по дуге) — «затвор сзади, стопка свободна»
STACK_C = (524.18, 9.24)
STACK_DEG = 1.939
STACK_FREE_DEG = 0.353
# верхний патрон в свободном положении (по нему губки): центр дна, подъём носа, ось по Y, радиус гильзы
CART1_DNO, CART1_DEG, CART1_Y = (151.51, -14.00), 6.31, 4.15
# мешает сверху затвор: идёт над горловиной (голова от X 240 до 139) отпертым, досылающий гребень Y ±2,6 с низом Z −12,6
RAMMER_HW, RAMMER_Z = 2.6, -12.6
NECK_TOP = -10.0                      # верх стенок горловины (|Y| 9,3…13,6)
FW_TOP = -13.0                        # верх передней стенки горловины (между стенками): патрон уходит над ней в патронник
LIP_GAP = 3.5                         # щель между губками сзади (гребень затвора ±2,6)
LIP_X0, LIP_X1, LIP_T = 149.2, 183.0, 1.0


def _case_r(s):
    """Радиус патрона 5,45 по расстоянию s от дна (гильза v13 r 4,6, ствол гильзы к плечу, дульце, пуля)."""
    return np.interp(s, [0.0, 0.3, 30.0, 33.0, 39.0, 41.0, 50.0], [4.3, 4.65, 4.65, 3.2, 3.2, 2.8, 1.3])


def _clear_top(ay):
    """Наибольшая высота верха губки по |Y| = ay под затвором с зазором 0,3. Затвор (part_bolt) идёт над горловиной
    отпертым — повёрнутым на −35°: тогда нижний боевой упор внизу посередине (досылающий гребень |Y| < 3, низ −12,6),
    дальше — тело и второй упор; огибающая снята с сетки затвора по полосам |Y| в 1 мм (меньшее из соседних)."""
    return np.interp(ay, [3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0],
                     [-7.8, -7.8, -7.2, -6.6, -5.7, -5.8, -5.9, -5.9, -5.0]) - 0.3


# ---------------- геометрия на плоскости XZ ----------------

def _pt(rho, psi):
    a = math.radians(psi)
    return CP[0] - rho * math.cos(a), CP[1] - rho * math.sin(a)


def _polar(X, Z):
    dx = CP[0] - X; dz = CP[1] - Z
    return np.sqrt(dx * dx + dz * dz), np.degrees(np.arctan2(dz, dx))


def _uv(X, Z):
    rho, psi = _polar(X, Z)
    return rho, (psi - TILT * (rho - RHO0)) * KV


def _psi_of(psi_p, rho):
    """Настоящий угол ψ точки рисунка с углом ψ' на радиусе ρ."""
    return psi_p + TILT * (rho - RHO0)


def _arc_x(c, r, z):
    return c[0] - math.sqrt(r * r - (z - c[1]) ** 2)


def _bisect(f, a, b, n=60):
    fa = f(a)
    for _ in range(n):
        m = (a + b) / 2; fm = f(m)
        if (fm > 0) == (fa > 0):
            a, fa = m, fm
        else:
            b = m
    return (a + b) / 2


def _front_bottom():
    """Угол передней кромки и дна (дуга CF ∩ радиус ψ_B)."""
    rho = _bisect(lambda r: math.hypot(_pt(r, PSI_B)[0] - CF[0], _pt(r, PSI_B)[1] - CF[1]) - RF, 270.0, 310.0)
    return rho, _pt(rho, PSI_B)


def _heel_pts():
    """Скос пятки: точки на ρ = RHO_STEP и на заднем силуэте."""
    ax, az = HEEL_A; bx, bz = HEEL_B
    L = math.hypot(bx - ax, bz - az); ux, uz = (bx - ax) / L, (bz - az) / L

    def P(t):
        return ax + ux * t, az + uz * t
    t1 = _bisect(lambda t: math.hypot(P(t)[0] - CP[0], P(t)[1] - CP[1]) - RHO_STEP, 0.0, 40.0)
    t0 = _bisect(lambda t: math.hypot(P(t)[0] - C2[0], P(t)[1] - C2[1]) - R2, -10.0, 10.0)
    return P(t1), P(t0)


def _outer_poly():
    """Силуэт корпуса сбоку: плечо, скос переднего верха, передняя дуга, дно, ступень бортика, скос пятки, задний
    силуэт («лесенка»), прилив у защёлки."""
    pts, rad = [], []

    def put(p, r=0.0):
        pts.append((float(p[0]), float(p[1]))); rad.append(r)
    put((REAR_X, SH_Z), 0.8)
    put((205.5, SH_Z), 2.0)
    put((214.6, -42.3), 2.0)
    rho_fb, fb = _front_bottom()
    for z in np.arange(-44.0, fb[1] + 1.0, -2.0):
        put((_arc_x(CF, RF, z), z))
    put(fb, 3.0)
    put(_pt(RHO_STEP, PSI_B), 0.8)
    h1, h0 = _heel_pts()
    put(h1, 1.0)
    put(h0, 1.2)
    zs = np.arange(math.ceil(h0[1]) + 1.0, -82.0, 2.0)
    for z in zs:
        put((_arc_x(C2, R2, z), z))
    for p in [(153.73, -82.0), (151.5, -77.0), (148.5, -72.0), (146.0, -66.0), (144.6, -60.0)]:
        put(p, 0.0)
    put((REAR_X, -56.0), 3.0)
    return Poly(fillet_poly(pts, rad, seg=8))


def _face_poly():
    """Область «внутри лица бока» сзади: всё, что впереди линии, где поле бока переходит в спинку (на 4 мм внутрь
    от силуэта; у прилива — X 148,8, R_x-0.10_z0.20)."""
    pts = [(148.8, -20.0), (148.8, -55.0), (150.5, -62.0), (153.0, -74.0)]
    for z in np.arange(-80.0, -228.0, -2.0):
        pts.append((_arc_x(C2, R2 - 4.0, z), z))
    pts += [(320.0, -228.0), (320.0, -20.0)]
    return Poly(fillet_poly(pts, [0, 3.0, 4.0, 4.0] + [0] * (len(pts) - 4), seg=8))


def _cavity_poly():
    """Полость под патроны, подаватель и пружину: стенки 3 мм спереди, 2,6 мм от лица спинки; внизу открыта."""
    pb = PSI_B + 1.6
    # передняя стенка: дуга на 3 мм внутрь от передней кромки до радиуса ψ_B + 1,6 (ниже дна)
    rf = _bisect(lambda r: math.hypot(_pt(r, pb)[0] - CF[0], _pt(r, pb)[1] - CF[1]) - (RF + 3.0), 270.0, 320.0)
    rr = _bisect(lambda r: math.hypot(_pt(r, pb)[0] - C2[0], _pt(r, pb)[1] - C2[1]) - (R2 - 6.6), 320.0, 380.0)
    zf, zr = _pt(rf, pb)[1], _pt(rr, pb)[1]
    pts = [(CAV_X1, -5.0), (CAV_X1, -35.06), (213.95, -43.06)]   # спереди вверху — скос стенкой 1 мм (пуля 4)
    for z in np.arange(-46.0, zf + 0.5, -2.0):
        pts.append((_arc_x(CF, RF + 3.0, z), z))
    pts += [_pt(rf, pb), _pt(rr, pb)]
    for z in np.arange(math.ceil(zr + 0.5), -5.0, 2.0):
        x = _arc_x(C2, R2 - 6.6, z)
        if x < CAV_X0:
            pts.append((CAV_X0, z))
            break
        pts.append((x, z))
    pts.append((CAV_X0, -5.0))
    return Poly(pts)


def _neck_poly():
    """Горловина над плечом (входит в шахту) до верха стенок NECK_TOP; передняя стенка ниже — вырезом в body()."""
    pts = [(NECK_X0, SH_Z - 1.0), (NECK_X0, NECK_TOP), (NECK_X1, NECK_TOP), (NECK_X1, SH_Z - 1.0)]
    return Poly(fillet_poly(pts, [0.0, 0.8, 0.8, 0.0], seg=8))


# ---------------- рисунок бока ----------------

def _rows():
    """Ряды «вафель»: (k, верх ψ', низ ψ', сдвиг ρ)."""
    out = [(0, ROW0_TOP, ROW0_BOT, 0.0)]
    for k in range(1, 6):
        t = ROW1_TOP + ROW_PITCH * (k - 1)
        out.append((k, t, t + ROW_H, DRIFT_U * k))
    return out


def _slant(p0, p1):
    """Верх «вафли» по прямой через (ρ, ψ') p0, p1: внутри — ниже прямой (больше V)."""
    (u0, a0), (u1, a1) = p0, p1
    v0, v1 = a0 * KV, a1 * KV
    nu, nv = (v1 - v0), -(u1 - u0)
    L = math.hypot(nu, nv); nu /= L; nv /= L
    if nv > 0:
        nu, nv = -nu, -nv

    def f(U, V):
        return (U - u0) * nu + (V - v0) * nv
    return f


def _pockets2(k, top, bot, du):
    shapes = []
    for j, (u0, u1) in enumerate(POCKET_U):
        r = rect2(u0 + du, u1 + du, (top if k else 0.0) * KV, bot * KV, 1.6)
        if k == 0:
            p0, p1 = ROW0[j]
            sl = _slant((p0[0] + du, p0[1]), (p1[0] + du, p1[1]))
            r = (lambda U, V, r=r, sl=sl: i_round(r(U, V), sl(U, V), 1.6))
        shapes.append(r)
    return shapes


def _channel2(k):
    """Желоб под рядом k: клин — низ по радиусу, верх скошен (тоньше сзади)."""
    du = DRIFT_U * k
    vb = (ROW1_TOP + ROW_PITCH * k - 0.55) * KV
    ua, ub = 346.6 + du, 306.4 + du
    va, vb_ = vb - 0.40 * KV, vb - 0.80 * KV

    def f(U, V):
        t = (U - ub) / (ua - ub)
        vt = vb_ + (va - vb_) * t
        band = np.maximum(vt - V, V - vb)
        return i_round(band, np.abs(U - (ua + ub) / 2) - (ua - ub) / 2, 1.0)
    return f


def _win2(top):
    return rect2(WIN_U[0], WIN_U[1], (top + 0.02) * KV, (top + 1.98) * KV, 1.3)


def _row_bb(k, top, bot, s, u0=288.0, u1=352.0):
    p0 = _psi_of(top - 1.2, u1) - 0.3; p1 = _psi_of(bot + 1.0, u0) + 0.3
    pts = [_pt(r, p) for r in (u0, u1, (u0 + u1) / 2) for p in (p0, p1)]
    xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
    y0, y1 = (-HW - 1.0, -CAV_HW + 1.5) if s < 0 else (CAV_HW - 1.5, HW + 1.0)
    return bb(min(xs) - 1, max(xs) + 1, y0, y1, min(zs) - 1, max(zs) + 1)


def _recess(f2, s, depth, draft=0.45, rf=0.35):
    """Тело выемки в бок s (−1 правый, +1 левый): плоская фигура f2 в развёртке, глубина depth, стенки с уклоном."""
    fl = HW - depth

    def fn(X, Y, Z):
        U, V = _uv(X, Z)
        w = s * Y
        return i_round(f2(U, V) - draft * (w - fl), fl - w, rf)
    return fn


def _side_pattern(F, s):
    # 1. ступеньки передней полосы (между окнами и передней кромкой): каждая ступень смотрит вниз (Q03)
    def shingle(X, Y, Z):
        U, V = _uv(X, Z)
        psi = V / KV
        t = (psi - (ROW1_TOP - 0.55)) / ROW_PITCH
        fr = t - np.floor(t)
        rec = 0.4 * (1.0 - fr) * smoothstep(fr / 0.05)
        band = smoothstep((psi - 7.6) / 0.3) * smoothstep((33.6 - psi) / 0.3)
        m = smoothstep((303.6 - U) / 0.8) * band * smoothstep((1.0 - np.abs(s * Y - HW)) / 0.5)
        return -rec * m
    z_top = _pt(300.0, 7.0)[1]; z_bot = _pt(290.0, 34.5)[1]
    y0, y1 = (-HW - 1.0, -HW + 2.0) if s < 0 else (HW - 2.0, HW + 1.0)
    F.displace(shingle, bbox=bb(_pt(305, 7.0)[0] - 2, _pt(285, 34.5)[0] + 4, y0, y1, z_bot - 2, z_top + 2), fine=False)
    font = font_path(False)
    for k, top, bot, du in _rows():
        rb = _row_bb(k, top, bot, s)
        # 2. «вафли» и желоб под рядом — одной выемкой
        shapes = _pockets2(k, top, bot, du)
        if k < 5:
            shapes.append(_channel2(k))
        F.sub(_recess(union2(*shapes), s, D_POCKET), 0.35, bbox=rb)
        # 3. дорожка от «вафли» с цифрой к окну
        vc = (bot - 1.75) * KV
        conn = seg2((WIN_U[1] - 0.6, vc), (POCKET_U[2][0] + du + 1.0, vc), 0.45)
        F.sub(_recess(conn, s, 0.55, draft=0.3, rf=0.2), 0.25, bbox=rb)
        # 4. окно — насквозь в полость
        win = _win2(top)

        def wfn(X, Y, Z, win=win):
            U, V = _uv(X, Z)
            w = s * Y
            return i_round(win(U, V) - 0.12 * (w - CAV_HW), (CAV_HW - 1.2) - w, 0.0)
        F.sub(wfn, 0.35, bbox=rb)
        # 5. цифры остатка — выпуклые на дне «вафли» (на левом боку читаются слева)
        if NUMS[k]:
            f2, wt = text2(NUMS[k], font, DIGIT_H, track=0.15)
            rc = 310.0 + du
            pc = bot - 1.45
            pb = pc + (DIGIT_H / 2) / (rc * math.pi / 180.0)
            fl = HW - D_POCKET

            def dig(X, Y, Z, f2=f2, wt=wt, rc=rc, pb=pb, fl=fl):
                rho, psi = _polar(X, Z)
                psi_p = psi - TILT * (rho - RHO0)
                ut = (rc + wt / 2 - rho) if s < 0 else (rho - (rc - wt / 2))
                vt = (pb - psi_p) * math.pi / 180.0 * rho
                w = s * Y
                return i_round(f2(ut, vt), np.abs(w - (fl + 0.14)) - 0.2, 0.08)
            pr0, pr1 = rc - wt / 2 - 1, rc + wt / 2 + 1
            pts = [_pt(r, _psi_of(p, r)) for r in (pr0, pr1) for p in (pc - 1.0, pc + 1.0)]
            xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
            y0, y1 = sorted((s * (fl - 0.3), s * (fl + 0.6)))
            F.add(dig, 0.1, bbox=bb(min(xs) - 1, max(xs) + 1, y0, y1, min(zs) - 1, max(zs) + 1))


# ---------------- корпус ----------------

def body(h):
    F = Field("Magazine_Body", (141.0, -FP_HW - 1.2, -216.0), (273.0, FP_HW + 1.2, -4.0), h)
    outer = _outer_poly()
    # 1. корпус: силуэт сбоку × ширина; передняя грань скруглена сильнее
    F.add(prism(outer, "XZ", -HW, HW, rim=0.8))

    def front_round(X, Y, Z):
        df = np.sqrt((X - CF[0]) ** 2 + (Z - CF[1]) ** 2)
        return i_round(RF - df, np.abs(Y) - HW, FRONT_R)
    F.apply(front_round, "inter", 0.0, bbox=bb(200.0, 273.0, -HW - 1, HW + 1, -192.0, -36.0))
    # 2. горловина (в шахте) — уже корпуса; губки над верхним патроном
    neck = _neck_poly()
    F.add(prism(neck, "XZ", -NECK_HW, NECK_HW, rim=0.6), 0.6, bbox=bb(NECK_X0 - 1, NECK_X1 + 1, -NECK_HW - 1, NECK_HW + 1, SH_Z - 1.5, NECK_TOP + 1.0))
    hx0, hx1, hz0, hz1, hhw = HOOK
    hook = Poly(fillet_poly([(hx0 - 1.0, hz0), (hx1, hz0), (hx1, hz1 - 0.6), (hx1 - 2.0, hz1), (hx0 - 1.0, hz1)],
                            [0, 0.6, 0.6, 1.0, 0], seg=6))
    F.add(prism(hook, "XZ", -hhw, hhw, rim=0.5), 0.6, bbox=bb(hx0 - 2, hx1 + 1, -hhw - 1, hhw + 1, hz0 - 1, hz1 + 1))
    # 3. спинка: вдоль всей задней кромки — полоса уже корпуса, ниже прилива — «лесенка»: рёбра поперёк, средняя
    #    полоса, между рёбрами карманы открыты в стороны (P07, P11, R_x-0.10_z0.20)
    face = _face_poly()
    bbr = bb(141.0, 214.0, -HW - 1, HW + 1, -214.0, SH_Z + 1.0)

    def narrow(X, Y, Z):
        return i_round(-face.sd(X, Z), SPINE_HW - np.abs(Y), 0.4)
    F.sub(narrow, 0.4, bbox=bbr)
    psis = [LAD_PSI0 + LAD_STEP * i for i in range(LAD_N + 1)]

    def ladder(X, Y, Z):
        rho, psi = _polar(X, Z)
        d = np.full(np.broadcast(X, Z).shape, 1e3, np.float32)
        for a, b in zip(psis[:-1], psis[1:]):
            mid = (a + b) / 2; half = (b - a) / 2 * math.pi / 180.0
            d = np.minimum(d, np.abs(psi - mid) * math.pi / 180.0 * rho - (half * rho - LAD_RIB / 2))
        return i_round(i_round(-face.sd(X, Z), d, 0.5), SPINE_C - np.abs(Y), 0.5)
    F.sub(ladder, 0.4, bbox=bb(150.0, 214.0, -HW - 1, HW + 1, -212.0, -80.0))
    # 4. прилив у защёлки: выступ над зубом и выемка под зуб (по середине, сбоку не видны)
    F.sub(box((REAR_X - 3.0, -NOTCH_HW, NOTCH_Z0), (NOTCH_X, NOTCH_HW, LUG_Z0), 0.0), 0.3,
          bbox=bb(REAR_X - 2, NOTCH_X + 1.5, -NOTCH_HW - 1, NOTCH_HW + 1, NOTCH_Z0 - 1.5, LUG_Z0 + 1))
    F.add(box_e((LUG_X0, -LUG_HW, LUG_Z0), (REAR_X + 1.5, LUG_HW, LUG_Z1), rx=0.4, ry=0.4, rz=0.4), 0.3,
          bbox=bb(LUG_X0 - 1, REAR_X + 2, -LUG_HW - 1, LUG_HW + 1, LUG_Z0 - 1, LUG_Z1 + 1))
    # 5. бортик над крышкой (по обе стороны дна): задняя часть и передний блок
    for (r0, r1) in ((314.8, RHO_STEP), (305.0, 314.2)):
        def rail(X, Y, Z, r0=r0, r1=r1):
            rho, psi = _polar(X, Z)
            v = (psi - (PSI_RAIL + PSI_B + 0.6) / 2) * math.pi / 180.0 * rho
            hv = (PSI_B + 0.6 - PSI_RAIL) / 2 * math.pi / 180.0 * rho
            d2 = i_round(np.abs(v) - hv, np.abs(rho - (r0 + r1) / 2) - (r1 - r0) / 2, 0.6)
            return i_round(d2, np.abs(np.abs(Y) - (FP_HW + HW - 1.0) / 2) - (FP_HW - HW + 1.0) / 2, 0.45)
        pts = [_pt(r, p) for r in (r0, r1) for p in (PSI_RAIL, PSI_B + 0.6)]
        xs = [p[0] for p in pts]; zs = [p[1] for p in pts]
        F.add(rail, 0.3, bbox=bb(min(xs) - 1.5, max(xs) + 1.5, -FP_HW - 1, FP_HW + 1, min(zs) - 1.5, max(zs) + 1.5))
    nb = (math.sin(math.radians(PSI_B)), 0.0, -math.cos(math.radians(PSI_B)))
    F.apply(plane((CP[0], 0.0, CP[1]), nb), "inter", 0.0, bbox=bb(226.0, 273.0, -FP_HW - 1, FP_HW + 1, -216.0, -180.0))
    # 6. шов литья по середине передней грани (половинки корпуса)
    def seam(X, Y, Z):
        df = np.sqrt((X - CF[0]) ** 2 + (Z - CF[1]) ** 2)
        d = np.maximum(np.maximum(np.abs(Y) - 0.35, (RF - 0.22) - df), df - (RF + 0.6))
        return np.maximum(d, np.maximum(-178.0 - Z, Z + 43.0))
    F.add(seam, 0.15, bbox=bb(212.0, 272.0, -1.5, 1.5, -178.0, -42.0))
    # 7. пазы на передней грани вверху («рёбра спереди»), открыты в стороны
    for zc, wd in FRONT_SLOTS:
        th = math.asin((CF[1] - zc) / RF)

        def slot(X, Y, Z, th=th, wd=wd):
            df = np.sqrt((X - CF[0]) ** 2 + (Z - CF[1]) ** 2)
            a = np.arctan2(CF[1] - Z, CF[0] - X)
            d = np.maximum(np.abs(a - th) * RF - wd / 2, 2.5 - np.abs(Y))
            return i_round(d, df - (RF + FRONT_SLOT_D), 0.4)
        F.sub(slot, 0.3, bbox=bb(208.0, 228.0, -HW - 1, HW + 1, zc - wd / 2 - 2, zc + wd / 2 + 2))
    # 8. рисунок обоих боков
    for s in (-1, 1):
        _side_pattern(F, s)
    # 9. полость под патроны (внизу открыта — закрывает крышка), губки
    cav = _cavity_poly()
    F.sub(prism(cav, "XZ", -CAV_HW, CAV_HW, rim=0.8), 0.0)
    # передняя стенка горловины ниже стенок: верхний патрон, толкаемый за дно, уходит над ней носом вверх; сзади
    # верх стенки скошен — направляющая для пули
    ramp = Poly([(CAV_X1 - 2.0, FW_TOP - 2.2), (CAV_X1, FW_TOP - 2.2), (NECK_X1, FW_TOP), (NECK_X1 + 3.0, FW_TOP),
                 (NECK_X1 + 3.0, NECK_TOP + 3.0), (CAV_X1 - 2.0, NECK_TOP + 3.0)])
    F.sub(prism(ramp, "XZ", -CAV_HW, CAV_HW, rim=0.0), 0.5, bbox=bb(CAV_X1 - 3, NECK_X1 + 1, -CAV_HW - 1, CAV_HW + 1, FW_TOP - 3.5, NECK_TOP + 1))
    # задняя стенка: прорезь под досылающий гребень затвора
    F.sub(box((NECK_X0 - 2.0, -LIP_GAP, RAMMER_Z - 0.3), (CAV_X0 + 1.0, LIP_GAP, NECK_TOP + 3.0), 0.0), 0.4,
          bbox=bb(NECK_X0 - 1, CAV_X0 + 1.5, -LIP_GAP - 1, LIP_GAP + 1, RAMMER_Z - 1.5, NECK_TOP + 1))
    # губки: снизу — по верхнему патрону в свободном положении (+0,3), сверху — под затвором и упорами; сзади щель
    # ±LIP_GAP под гребень, дальше губки отходят к бортам (над затвором места нет — держат патрон за плечо)
    cx0, cz0 = CART1_DNO
    ca, ta = math.cos(math.radians(CART1_DEG)), math.tan(math.radians(CART1_DEG))

    def lips(X, Y, Z):
        ay = np.abs(Y)
        s_ = (X - cx0) / ca
        r = _case_r(s_)
        za = cz0 + (X - cx0) * ta
        under = za + np.sqrt(np.clip(r * r - (ay - CART1_Y) ** 2, 0.0, None)) + 0.3
        top = np.minimum(under + LIP_T, _clear_top(ay))
        yin = np.interp(X, [154.0, 159.0], [LIP_GAP, 7.6])
        d = np.maximum(under - Z, Z - top)
        d = np.maximum(d, yin - ay)
        d = np.maximum(d, ay - (CAV_HW + 0.8))
        return np.maximum(d, np.maximum(LIP_X0 - X, X - LIP_X1))
    for s in (-1, 1):
        y0, y1 = sorted((s * (LIP_GAP - 0.5), s * (CAV_HW + 1.0)))
        F.add(lips, 0.4, bbox=bb(LIP_X0 - 1, LIP_X1 + 1, y0, y1, -16.0, -4.0))
    return F


# ---------------- крышка ----------------

def _floor_poly():
    """Крышка сбоку: плоская часть под дном (ψ_B … ψ_P) и пятка — клин под скосом корпуса до горизонтали HEEL_Z."""
    g = 0.2
    rho_k = (CP[1] - HEEL_Z) / math.sin(math.radians(PSI_P))
    x_rear = _arc_x(C2, R2, HEEL_Z)
    h1, h0 = _heel_pts()
    dpsi = lambda r: math.degrees(g / r)
    pts = [(x_rear, HEEL_Z), _pt(rho_k, PSI_P), _pt(293.5, PSI_P), _pt(293.5, PSI_B + dpsi(293.5)),
           _pt(RHO_STEP + g, PSI_B + dpsi(RHO_STEP)), (h1[0] - g, h1[1] - g), (h0[0] + g * 0.2, h0[1] - g)]
    rad = [0.6, 2.5, 1.0, 0.6, 0.0, 0.0, 0.8]
    return Poly(fillet_poly(pts, rad, seg=8))


def floorplate(h):
    F = Field("Magazine_Floorplate", (204.0, -FP_HW - 1.0, -215.0), (270.0, FP_HW + 1.0, -180.0), h)
    F.add(prism(_floor_poly(), "XZ", -FP_HW, FP_HW, rim=0.5))
    # вид снизу: спереди язык уже (U_x0.02: ±10,5), скруглён
    plan = union2(rect2(304.8, 400.0, -FP_HW, FP_HW, 1.2), rect2(290.0, 307.0, -10.5, 10.5, 4.0), r=2.0)

    def plan3(X, Y, Z):
        rho, _ = _polar(X, Z)
        return plan(rho, Y)
    F.apply(plan3, "inter", 0.5, bbox=bb(255.0, 270.0, -FP_HW - 1, FP_HW + 1, -200.0, -180.0))
    # канавки по низу: вдоль бортов и петлёй спереди (U_x0.02); на пятке — прямые
    sp, cp = math.sin(math.radians(PSI_P)), math.cos(math.radians(PSI_P))

    def nbot(X, Z):            # расстояние наружу от низа плоской части
        return (X - CP[0]) * sp - (Z - CP[1]) * cp

    def groove(X, Y, Z):
        rho, _ = _polar(X, Z)
        line = np.where(rho >= 308.6, np.abs(np.abs(Y) - 10.3), np.abs(np.hypot(rho - 308.6, Y) - 10.3))
        return np.maximum(line - 0.45, -0.55 - nbot(X, Z))
    F.sub(groove, 0.2, bbox=bb(228.0, 268.0, -12, 12, -214.0, -184.0))

    def groove_heel(X, Y, Z):
        return np.maximum(np.maximum(np.abs(np.abs(Y) - 10.3) - 0.45, Z - (HEEL_Z + 0.55)), 208.0 - X)
    F.sub(groove_heel, 0.2, bbox=bb(206.0, 236.0, -12, 12, -214.0, -210.0))
    # кнопка-фиксатор: круг в кольцевой канавке и метка рядом
    bx, bz = _pt(331.3, PSI_P)
    def button(X, Y, Z):
        rho, _ = _polar(X, Z)
        r = np.hypot(rho - 331.3, Y)
        return np.maximum(np.abs(r - 2.75) - 0.22, -0.45 - nbot(X, Z))
    F.sub(button, 0.12, bbox=bb(bx - 5, bx + 5, -5, 5, bz - 5, bz + 5))

    def mark(X, Y, Z):
        rho, _ = _polar(X, Z)
        return np.maximum(np.maximum(np.abs(rho - 318.6) - 0.8, np.abs(Y) - 1.6), -0.4 - nbot(X, Z))
    mx, mz = _pt(318.6, PSI_P)
    F.sub(mark, 0.15, bbox=bb(mx - 4, mx + 4, -3, 3, mz - 4, mz + 4))
    return F


# ---------------- подаватель и пружина ----------------
# Подаватель — в осях патрона 30 (нижний в полном магазине, справа): A — вдоль патрона к пуле, N — вверх от его оси.
# Оси сняты с патронов v13 до подъёма стопки; деталь поворачивается со стопкой (_unstack) в утопленное положение,
# над ней ещё 2,3 мм хода вверх (свободное положение).
F_AX = (0.899, 0.438)                 # ось патрона 30 v13 (25,97°)
F_O = (231.67, -146.92)               # точка на оси патрона 30
F_R = 4.14                            # радиус патрона по сетке v13
F_STEP = 4.83                         # ось патрона 29 (слева) выше на 4,83
F_A0, F_A1 = -44.5, 7.0               # длина подавателя (донце патрона — A −43,1, пуля — до +9,5)
F_B0 = -13.5                          # низ подавателя
F_HW = 9.0                            # полуширина (полость 9,3)


def _unstack(X, Z, deg=None):
    """Точка в положении «стопка утоплена» → та же точка до подъёма стопки (обратный поворот, против часовой)."""
    a = math.radians(STACK_DEG if deg is None else deg)
    dx, dz = X - STACK_C[0], Z - STACK_C[1]
    return STACK_C[0] + dx * math.cos(a) - dz * math.sin(a), STACK_C[1] + dx * math.sin(a) + dz * math.cos(a)


def _restack(x, z, deg=None):
    """Обратное к _unstack: точка прежней стопки → утопленное положение (по часовой)."""
    a = math.radians(STACK_DEG if deg is None else deg)
    dx, dz = x - STACK_C[0], z - STACK_C[1]
    return STACK_C[0] + dx * math.cos(a) + dz * math.sin(a), STACK_C[1] - dx * math.sin(a) + dz * math.cos(a)


def _fa(X, Z):
    X, Z = _unstack(X, Z)
    ax, az = F_AX
    dx, dz = X - F_O[0], Z - F_O[1]
    return dx * ax + dz * az, -dx * az + dz * ax


def follower(h):
    F = Field("Magazine_Follower", (186.0, -F_HW - 1.0, -176.0), (254.0, F_HW + 1.0, -126.0), h)
    top_lo = -F_R - 0.35                       # под патроном 30 (справа)
    top_hi = F_STEP - F_R - 0.35               # уступ под патроном 29 (слева)
    # профиль в осях патрона: низкая часть (весь подаватель) со скосом спереди
    lo = Poly(fillet_poly([(F_A0, F_B0), (F_A1, F_B0), (F_A1, -9.6), (0.0, top_lo), (F_A0, top_lo)], [1.5, 1.2, 1.5, 3.0, 1.5], seg=8))
    hi = Poly(fillet_poly([(F_A0, top_lo - 1.0), (-9.0, top_lo - 1.0), (-2.5, top_lo), (-6.5, top_hi), (F_A0, top_hi)], [0, 0, 1.0, 1.5, 1.5], seg=8))

    def body_lo(X, Y, Z):
        a, b = _fa(X, Z)
        return i_round(lo.sd(a, b), np.abs(Y) - F_HW, 0.7)

    def body_hi(X, Y, Z):
        a, b = _fa(X, Z)
        return i_round(i_round(hi.sd(a, b), Y - F_HW, 0.7), 0.85 - Y, 0.5)
    F.add(body_lo)
    F.add(body_hi, 0.8)
    # снизу — гнездо под верхний виток пружины
    def socket(X, Y, Z):
        a, b = _fa(X, Z)
        return i_round(np.maximum(np.abs(a - (F_A0 + F_A1) / 2 + 1.0) - 19.0, np.abs(Y) - 7.4), (F_B0 + 1.2) - b, 0.6)
    F.sub(socket, 0.4)
    return F


def _spring_top():
    """Угол ψ (вокруг CP) верхнего витка: 0,45° ниже низа подавателя в утопленном положении."""
    ax, az = F_AX
    nx, nz = -az, ax
    best = 0.0
    for a in np.linspace(F_A0, F_A1, 30):
        x, z = F_O[0] + ax * a + nx * F_B0, F_O[1] + az * a + nz * F_B0
        x, z = _restack(x, z)
        best = max(best, math.degrees(math.atan2(CP[1] - z, CP[0] - x)))
    return best + 0.45


SPR_PSI = (_spring_top(), 36.65)      # пружина: от низа подавателя до крышки (углы вокруг CP)
SPR_RHO = (303.5, 337.6)              # ρ витка
SPR_HW = 7.0                          # полуширина витка
SPR_WIRE = 0.75
SPR_COILS = 6.0


def spring(h):
    """Плоская пружина АК: витки — скруглённые прямоугольники в плоскостях вдоль радиуса CP."""
    r0, r1 = SPR_RHO
    cr = 4.0
    # периметр скруглённого прямоугольника (ρ, Y) — точками по порядку
    loop = fillet_poly([(r0, -SPR_HW), (r1, -SPR_HW), (r1, SPR_HW), (r0, SPR_HW)], [cr] * 4, seg=10)
    loop = np.array(loop + [loop[0]])
    seg = np.linalg.norm(np.diff(loop, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    n = int(SPR_COILS * 120)
    pts = []
    for i in range(n + 1):
        t = i / n * SPR_COILS
        f = (t - math.floor(t)) * s[-1]
        rho = np.interp(f, s, loop[:, 0]); y = np.interp(f, s, loop[:, 1])
        psi = SPR_PSI[0] + (SPR_PSI[1] - SPR_PSI[0]) * t / SPR_COILS
        x, z = _pt(rho, psi)
        pts.append((x, y, z))
    return tube_mesh(np.array(pts), SPR_WIRE, 10)


def parts():
    return [
        dict(name="Magazine_Body", build=body, h=0.13, coll="Магазин", mat="Mag_polymer", adapt=0.06),
        dict(name="Magazine_Floorplate", build=floorplate, h=0.1, coll="Магазин", mat="Polymer", adapt=0.06,
             parent="Magazine_Body"),
        dict(name="Magazine_Follower", build=follower, h=0.1, coll="Магазин", mat="Mag_polymer", adapt=0.06,
             parent="Magazine_Body"),
        dict(name="Magazine_Spring", build=spring, coll="Магазин", mat="Spring_steel", parent="Magazine_Body"),
    ]
