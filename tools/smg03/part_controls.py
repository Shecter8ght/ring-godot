# ПП по мотивам KRISS Vector Gen II SMG: органы управления и мелкие детали боков.
# Спуск — контур со снимка KRISS (data/profiles.json, trigger) и ось внутри коробки; предохранитель — двусторонний
# флажок у оси (X −153, Z 39, снимок A); переводчик огня (у SMG отдельный, двусторонний) — флажок у оси (X −50, Z 37,
# лист KRISS SMG); защёлка магазина — лопатка на переднем ребре шахты с обеих сторон (снимок A); кнопка затворной
# задержки — квадратная справа (X −38, Z −10, снимок B); слева у шахты — площадка с двумя рифлёными кнопками,
# планками с винтами и рёбрами-«радиатором» спереди и сзади (снимок A, «как есть»).
import math
import bpy
from lib import (MM, HALF_W, PROFILES, rounded_prism, prism_xz, prism_xy, prism_yz, box, cyl, lathe, boolean, fillet,
                 finish, finish_small, set_origin, v)
from part_receiver import rounded_rect_xz, pill_xz, mag_frame, MAG_CENTER

TRIGGER_PIVOT = (-150.0, 22.0)     # ось спуска (внутри коробки, оценка)
TRIGGER_HALF_W = 3.2
SAFETY_PIVOT = (-183.5, 39.0)      # снимок A (проверка v02: было на 31 мм впереди)
SELECTOR_PIVOT = (-72.0, 38.5)     # лист KRISS SMG (проверка v02: хвост был над окном выброса)
LEVER_T = 2.6                       # толщина флажков
BOLT_REL = (-38.0, -10.0)          # кнопка задержки справа
MAG_REL = (-7.0, -38.0)            # лопатка защёлки магазина у переднего ребра шахты


def trigger(C):
    pts = [tuple(p) for p in PROFILES["parts"]["trigger"][0]["outer"]]
    t = rounded_prism("Trigger", pts, -TRIGGER_HALF_W, TRIGGER_HALF_W, 1.0, C, "Steel_black")
    # хвост внутри коробки — к оси: перо продолжается вверх до оси с отверстием
    px, pz = TRIGGER_PIVOT
    up = prism_xz("_tup", fillet([(px + 9.0, 16.0), (px - 13.0, 16.0), (px - 9.0, pz + 6.0), (px + 6.0, pz + 6.0)],
                                 [1.0, 1.0, 3.0, 3.0], 4), -TRIGGER_HALF_W + 0.2, TRIGGER_HALF_W - 0.2, C)
    boolean(t, up, op="UNION")
    hole = cyl("_th", -5, 5, 1.6, C, seg=32, cy=px, cz=pz, axis="Y")
    boolean(t, hole)
    finish_small(t, w=0.3, seg=3)
    set_origin(t, (px, 0, pz))
    return t


def lever(name, pivot, hub_r, tail, side, C, mat="Steel_black"):
    """Флажок на оси: ступица радиуса hub_r и хвост в точку tail (x, z) с упором под палец; side = ±1 (борт)."""
    px, pz = pivot
    tx, tz = tail
    ang = math.atan2(tz - pz, tx - px)
    L = math.hypot(tx - px, tz - pz)
    nx, nz = -math.sin(ang), math.cos(ang)
    w0, w1 = hub_r * 0.85, 3.2
    pts = []
    for k in range(13):
        a = ang + math.pi / 2 + math.pi * k / 12
        pts.append((px + hub_r * math.cos(a), pz + hub_r * math.sin(a)))
    # хвост: сужение к концу и закруглённый носок
    pts += [(px + math.cos(ang) * L * 0.55 - nx * w1 * 1.1, pz + math.sin(ang) * L * 0.55 - nz * w1 * 1.1)]
    for k in range(9):
        a = ang - math.pi / 2 + math.pi * k / 8
        pts.append((tx + w1 * math.cos(a), tz + w1 * math.sin(a)))
    pts += [(px + math.cos(ang) * L * 0.5 + nx * w0, pz + math.sin(ang) * L * 0.5 + nz * w0)]
    y0, y1 = (HALF_W + 0.3, HALF_W + 0.3 + LEVER_T) if side > 0 else (-HALF_W - 0.3 - LEVER_T, -HALF_W - 0.3)
    o = rounded_prism(name, pts, y0, y1, 0.9, C, mat, seg=4)
    # рифление упора под палец: три канавки поперёк хвоста
    for i in range(3):
        cx = tx - math.cos(ang) * (1.2 + 2.0 * i)
        cz = tz - math.sin(ang) * (1.2 + 2.0 * i)
        g = prism_xz("_lg", [(cx - nx * 5 - math.cos(ang) * 0.5, cz - nz * 5 - math.sin(ang) * 0.5),
                             (cx + nx * 5 - math.cos(ang) * 0.5, cz + nz * 5 - math.sin(ang) * 0.5),
                             (cx + nx * 5 + math.cos(ang) * 0.5, cz + nz * 5 + math.sin(ang) * 0.5),
                             (cx - nx * 5 + math.cos(ang) * 0.5, cz - nz * 5 + math.sin(ang) * 0.5)],
                     (y1 - 0.5) if side > 0 else (y0 - 1), (y1 + 1) if side > 0 else (y0 + 0.5), C)
        boolean(o, g)
    # ось — шайба в ступице
    axle = cyl(f"{name}_axle", (y1 - 0.2) if side > 0 else (y0 - 0.6), (y1 + 0.6) if side > 0 else (y0 + 0.2),
               hub_r * 0.45, C, mat, seg=48, cy=px, cz=pz, axis="Y")
    finish_small(o, w=0.3, seg=3)
    finish_small(axle, w=0.15, seg=2)
    boolean(o, axle, op="UNION")
    set_origin(o, (px, 0, pz))
    return o


def mag_release(name, side, C):
    """Лопатка защёлки магазина: вдоль переднего ребра шахты (наклон 21°), две точки-рифления (снимок A)."""
    up, fwd = mag_frame()
    cx, cz = MAG_REL
    a = (cx + up.x * 6.0, cz + up.z * 6.0)
    b = (cx - up.x * 6.0, cz - up.z * 6.0)
    pts = pill_xz(a, b, 5.2)
    y0, y1 = (HALF_W - 0.6, HALF_W + 1.6) if side > 0 else (-HALF_W - 1.6, -HALF_W + 0.6)
    o = rounded_prism(name, pts, y0, y1, 0.8, C, "Polymer", seg=4)
    for k in (-1.5, 1.5):
        d = cyl("_dot", (y1 - 0.4) if side > 0 else (y0 - 1), (y1 + 1) if side > 0 else (y0 + 0.4), 0.6, C, seg=24,
                cy=cx + up.x * k, cz=cz + up.z * k, axis="Y")
        boolean(o, d)
    finish_small(o, w=0.2, seg=3)
    set_origin(o, (a[0], 0, a[1]))
    return o


def mag_tab_right(C):
    """Справа защёлка магазина — лапка в прямоугольном вырезе рифлёной кромки (снимки KRISS B, владельца 04)."""
    up, fwd = mag_frame()
    cx, cz = MAG_REL
    a = (cx + up.x * 4.5, cz + up.z * 4.5)
    b = (cx - up.x * 4.5, cz - up.z * 4.5)
    pts = [(a[0] + fwd.x * 2.4, a[1] + fwd.z * 2.4), (b[0] + fwd.x * 2.4, b[1] + fwd.z * 2.4),
           (b[0] - fwd.x * 2.4, b[1] - fwd.z * 2.4), (a[0] - fwd.x * 2.4, a[1] - fwd.z * 2.4)]
    o = rounded_prism("Mag_release_R", fillet(pts, 1.0, 4), -HALF_W - 0.2, -HALF_W + 1.6, 0.5, C, "Polymer", seg=3)
    set_origin(o, (a[0], 0, a[1]))
    return o


def bolt_release(C):
    x, z = BOLT_REL
    o = rounded_prism("Bolt_release", rounded_rect_xz(x - 4.6, x + 4.6, z - 4.2, z + 4.2, 1.6), -HALF_W - 1.6,
                      -HALF_W + 2.0, 0.9, C, "Steel_black", seg=4)
    # поперечные риски на кнопке
    for i in range(3):
        g = prism_xz("_br", rounded_rect_xz(x - 3.0, x + 3.0, z - 2.4 + i * 2.4 - 0.35, z - 2.4 + i * 2.4 + 0.35, 0.3),
                     -HALF_W - 3, -HALF_W - 1.2, C)
        boolean(o, g)
    finish_small(o, w=0.15, seg=2)
    return o


def side_block(C, mw):
    """Левая площадка у шахты (снимок A): основание, две рифлёные кнопки, верхняя и нижняя планки с винтами, рёбра
    спереди и сзади. Рёбра и основание — одно тело с корпусом шахты не делаем: отдельная деталь, на винтах."""
    y0 = HALF_W - 0.4
    base = rounded_prism("Side_block", rounded_rect_xz(-45.0, -1.0, -12.5, 14.0, 2.5), y0, y0 + 1.6, 0.6, C, "Steel_black",
                         seg=3)
    # кнопки: прямоугольные подушки с поперечным рифлением
    for nm, (xa, xb) in (("Side_button_front", (-11.5, -2.5)), ("Side_button_rear", (-43.0, -32.0))):
        b = rounded_prism(nm, rounded_rect_xz(xa, xb, 1.5, 13.5, 1.2), y0 + 1.75, y0 + 4.4, 0.6, C, "Steel_black", seg=3)
        n = int((xb - xa) / 1.6)
        for i in range(n):
            xc = xa + 1.0 + i * (xb - xa - 2.0) / max(1, n - 1)
            g = prism_xz("_kn", rounded_rect_xz(xc - 0.35, xc + 0.35, 1.0, 14.0, 0.3), y0 + 3.6, y0 + 6.0, C)
            boolean(b, g)
        finish_small(b, w=0.15, seg=2)
    # планки с винтами: верхняя (между кнопками) и нижняя
    for nm, (xa, xb, za, zb) in (("Side_plate_top", (-30.0, -13.0, 7.0, 13.5)), ("Side_plate_low", (-29.0, -13.0, -11.0, 0.0))):
        pl = rounded_prism(nm, rounded_rect_xz(xa, xb, za, zb, 1.5), y0 + 1.4, y0 + 3.0, 0.5, C, "Steel_black", seg=3)
        for xs in (xa + 4.0, xb - 4.0):
            zs = (za + zb) / 2
            h = cyl("_sh", y0 + 2.2, y0 + 4.0, 1.5, C, seg=32, cy=xs, cz=zs, axis="Y")
            boolean(pl, h)
        finish_small(pl, w=0.15, seg=2)
    # рёбра-«радиатор»: по 5 спереди (X 4…20) и сзади (X −60…−46), Z −6…10 через 4 мм
    for side_nm, (xa, xb) in (("Side_fins_front", (1.5, 14.5)), ("Side_fins_rear", (-60.0, -46.0))):
        fins = None
        for i in range(5):
            zc = -6.0 + i * 4.0
            f = rounded_prism("_fin" if fins else side_nm, pill_xz((xa + 1.0, zc), (xb - 1.0, zc), 1.0, 8), y0, y0 + 1.8, 0.5,
                              C, "Polymer", seg=3)
            if fins is None:
                fins = f
            else:
                boolean(fins, f, op="UNION")
        fins["_fin"] = 1
        fins["owner"] = "Receiver"
    finish_small(base, w=0.15, seg=2)
    base["owner"] = "Receiver"
    for nm in ("Side_button_front", "Side_button_rear", "Side_plate_top", "Side_plate_low"):
        bpy.data.objects[nm]["owner"] = "Side_block"
    return base


def build(ctx):
    C = ctx["coll"]["Controls"]
    t = trigger(C)
    sl = lever("Safety_L", SAFETY_PIVOT, 4.4, (-197.0, 36.0), 1, C)
    sr = lever("Safety_R", SAFETY_PIVOT, 4.4, (-197.0, 36.0), -1, C)
    fl = lever("Selector_L", SELECTOR_PIVOT, 4.0, (-60.5, 33.5), 1, C)
    fr = lever("Selector_R", SELECTOR_PIVOT, 4.0, (-60.5, 33.5), -1, C)
    ml = mag_release("Mag_release_L", 1, C)
    mr = mag_tab_right(C)
    br = bolt_release(C)
    sb = side_block(C, ctx["parts"].get("receiver", {}).get("magwell"))
    return {"trigger": t, "safety": (sl, sr), "selector": (fl, fr), "mag_release": (ml, mr), "bolt_release": br}
