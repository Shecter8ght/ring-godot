# ПП по мотивам KRISS Vector: складной приклад (как у Gen I / Gen II до 2017 со встроенным шарниром на коробке, по
# снимкам владельца 02/04/06/08 и снимку товара KVA-FSBL00): ложе — контур со снимка (trace_stock.py →
# data/stock_profile.json), затыльник с резиновой накладкой, шарнир справа на заднем торце коробки (вертикальная
# ось), защёлка-кнопка с рифлением слева у шарнира, антабка снизу ложа (в контуре). Складывается вправо на 180°.
import json
import math
import os
import bpy
from lib import (MM, HALF_W, REAR_X, HERE, rounded_prism, prism_xz, prism_xy, prism_yz, cyl, box, lathe, boolean, fillet,
                 finish_small, set_origin, apply_transform, v)
from part_receiver import rounded_rect_xz, side_recess, pill_xz

SP = json.load(open(os.path.join(HERE, "data", "stock_profile.json"), encoding="utf-8"))
HINGE_X = SP["hinge_x"]           # −271
HINGE_Y = -21.6                   # ось на правом борту: сложенный затыльник (±19) проходит мимо борта и кнопок
HINGE_Z = (19.0, 51.0)            # по высоте коробки над рукоятью
STOCK_HALF_W = 11.0               # ложе 22 мм (оценка по снимкам владельца)
PAD_HALF_W = 19.0                 # затыльник 38 мм
CORE_HALF_W = 9.8                 # жёсткий сердечник затыльника между проушинами — уже ложа (22), заходит в проушины
CORE_X = (-448.0, -440.5)         # сердечник: от резины (−447.4) вперёд; окно ложа сзади закрывает он
CORE_Z = (-15.5, -66.0)           # заходит в верхнюю (низ −19.8) и нижнюю (верх −62.1) проушины на 3.5
PIN_X = -441.0                    # оси затыльника в проушинах: головка Ø7 целиком на плоском боку проушины
PAD_GROOVES = (-86.0, 6.6, 10)    # канавки тыльной стороны: первая (Z), шаг, число — поперёк всей ширины


def _slot(c, length, width, ang):
    """Прорезь со скруглёнными концами: центр, длина, ширина, наклон (град)."""
    a = math.radians(ang)
    ux, uz = math.cos(a), math.sin(a)
    hw = width / 2
    pts = []
    for end, a0 in ((1, -90.0), (-1, 90.0)):
        cx, cz = c[0] + end * (length / 2 - hw) * ux, c[1] + end * (length / 2 - hw) * uz
        for k in range(9):
            t = math.radians(a0 + 180.0 * k / 8) + a
            pts.append((cx + hw * math.cos(t), cz + hw * math.sin(t)))
    return pts


def _smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def buttplate_core(C):
    """Сердечник затыльника (снимок владельца 5, фото 02): вертикальная перемычка между проушинами ложа перед резиной —
    закрывает окно ложа сзади, затыльник держится на всей высоте, а не «прилеплен» к концам проушин. На боках — X:
    утоплены верхний и нижний треугольники, крестовина остаётся."""
    x0, x1 = CORE_X
    za, zb = CORE_Z
    c = rounded_prism("Stock_buttplate_core", fillet([(x0, za), (x1, za), (x1, zb), (x0, zb)], 2.0, 5), -CORE_HALF_W,
                      CORE_HALF_W, 1.2, C, "Polymer", seg=4)
    # X в видимой части окна (Z −24…−57): верхний и нижний треугольники утоплены на 0.7
    xa, xb = x0 + 1.4, x1 - 1.0
    zt, zbm = -24.0, -57.0
    xm, zm = (xa + xb) / 2, (zt + zbm) / 2
    w = 0.9
    for tri in ([(xa + w, zt), (xb - w, zt), (xm, zm + w * 2.2)], [(xm, zm - w * 2.2), (xb - w, zbm), (xa + w, zbm)]):
        side_recess(c, fillet(tri, [0.6, 0.6, 0.5], 3), 0.7, C, half=CORE_HALF_W, name="_x")
    finish_small(c, w=0.25, seg=2)
    return c


def buttpad(C):
    """Резиновая накладка: контур со снимка товара, выправленный, — спина ровной наклонной линией с лёгким утолщением
    к верху (на снимке «пятка» уступом 3 мм читалась горбом). Рёбра тыльной стороны — волной в самом контуре: идут
    поперёк всей ширины и сами огибают скругления боков (снимок владельца 5). Резцами с фаской концы канавок на
    скруглениях рвались — «прорези как будто сломаны», владелец 05.11. Кромки: спереди R 1.6, сзади R 3, на рёбрах R 1.5
    (волна мельче радиуса не держит сдвиг внутрь)."""
    pts = [(-447.4, 2.6), (-447.4, -95.0), (-471.0, -95.0), (-477.6, -10.0), (-478.6, 0.0), (-474.0, 4.2),
           (-460.0, 6.2), (-451.5, 4.8)]
    pad = fillet(pts, [1.8, 2.2, 4.5, 6.0, 5.0, 8.0, 8.0, 4.0], 8)
    (xa, za), (xb, zb) = (-471.0, -95.0), (-477.6, -10.0)
    L = math.hypot(xb - xa, zb - za)
    nx, nz = (zb - za) / L, -(xb - xa) / L           # нормаль спины внутрь (к +X)
    if nx < 0:
        nx, nz = -nx, -nz
    z0, step, n = PAD_GROOVES
    centers = [z0 + step * k for k in range(n)]
    w, a = 2.6, 0.8                                  # полуширина и глубина канавки (волна косинусом)

    def on_back(p):
        return p[0] < -466.0
    dense = []
    m = len(pad)
    for i in range(m):
        p0, p1 = pad[i], pad[(i + 1) % m]
        dense.append(p0)
        seg_len = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        if on_back(p0) and on_back(p1) and seg_len > 0.5:
            k = int(seg_len / 0.3)
            for j in range(1, k):
                t = j / k
                dense.append((p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t))
    out = []
    for x, z in dense:
        d = 0.0
        if on_back((x, z)):
            for c in centers:
                if abs(z - c) < w:
                    d = max(d, a * (0.5 + 0.5 * math.cos(math.pi * (z - c) / w)))
        out.append((x + nx * d, z + nz * d))

    def r_fn(x, z):
        r = 1.6 + 1.4 * _smoothstep((-452.0 - x) / 12.0)
        if x < -464.0:
            # переход радиуса 3 → 1.5 растянут на 8 мм: на 4 мм у верхнего ребра на боку читалась «талия»
            rib = _smoothstep((z + 96.0) / 8.0) * _smoothstep((-14.0 - z) / 8.0)
            r = min(r, 3.0 - 1.5 * rib)
        return r
    p = rounded_prism("Stock_buttplate", out, -PAD_HALF_W, PAD_HALF_W, 3.0, C, "Rubber", seg=6, r_fn=r_fn,
                      smooth=(0.3, 0))
    return p


def hinge_block(C):
    """Шарнир на правом заднем углу коробки: верхний и нижний кулаки — цилиндры Ø13 на оси (вместе с кулаком приклада —
    один высокий цилиндр, как у настоящего), утоплены в торец коробки на 1.5 мм."""
    z0, z1 = HINGE_Z
    plate = None
    for za, zb in ((z0, z0 + 8.5), (z1 - 8.5, z1)):
        k = lathe("Stock_hinge_block" if plate is None else "_lug",
                  [(za, 2.7), (za, 5.7), (za + 0.8, 6.5), (zb - 0.8, 6.5), (zb, 5.7), (zb, 2.7)], C, "Alu_anodized", seg=64)
        k.rotation_euler = (0, -math.pi / 2, 0)
        k.location = v(HINGE_X, HINGE_Y, 0)
        apply_transform(k)
        web = rounded_prism("_web", rounded_rect_xz(HINGE_X - 1.0, REAR_X + 2.0, za, zb, 1.5), HINGE_Y - 5.5,
                            HINGE_Y + 6.5, 1.2, C, seg=4)
        boolean(k, web, op="UNION")
        if plate is None:
            plate = k
        else:
            boolean(plate, k, op="UNION")
    plate["owner"] = "Receiver"
    plate["_fin"] = 1
    pin = cyl("Stock_hinge_pin", z0 - 0.6, z1 + 0.6, 2.5, C, "Steel_black", seg=40, cy=HINGE_X, cz=HINGE_Y, axis="Z")
    cap = lathe("_cap", [(z1 + 0.6, 0.0), (z1 + 0.6, 4.2), (z1 + 1.6, 4.2), (z1 + 2.4, 3.2), (z1 + 2.4, 0.0)], C, seg=48)
    cap.rotation_euler = (0, -math.pi / 2, 0)
    cap.location = v(HINGE_X, HINGE_Y, 0)
    apply_transform(cap)
    boolean(pin, cap, op="UNION")
    finish_small(pin, w=0.3, seg=3)
    pin["owner"] = "Stock_hinge_block,Stock_body"
    return plate, pin


def _flat_rear(pts, x_rear=-447.7, tol=4.0):
    """Задняя кромка обеих проушин ложа по снимку гуляет (−444.7…−448.3): затыльник прилегал одной проушиной и отходил
    от другой на 2.7 мм (сверка v04 Д11) — точки задних граней (касательная почти вертикальна) ровно на X −447.7
    (с заходом 0.3 в затыльник); углы потом сглаживает rounded_prism."""
    n = len(pts)
    out = []
    for i, (x, z) in enumerate(pts):
        (xa, za), (xb, zb) = pts[i - 1], pts[(i + 1) % n]
        vertical = abs(zb - za) > 1.4 * abs(xb - xa)        # точка на задней грани, а не на верхней / нижней
        out.append((x_rear, z) if abs(x - x_rear) < tol and vertical else (x, z))
    return out


def stock(C):
    body = _flat_rear([tuple(p) for p in SP["body"]["outer"]])
    o = rounded_prism("Stock_body", body, -STOCK_HALF_W, STOCK_HALF_W, 3.0, C, "Polymer", seg=5)
    # кулак шарнира: цилиндр по оси между проушинами коробки (с зазором 0.3)
    z0, z1 = HINGE_Z
    # вырезы ложа под проушины коробки — в контуре (trace_stock.py)
    # кулак приклада — цилиндр Ø13 между кулаками коробки (зазоры 0.3) и перемычка к ложу (только внутрь от оси:
    # сложенный приклад не заходит в борт)
    k = lathe("_kn", [(z0 + 8.8, 2.7), (z0 + 8.8, 5.7), (z0 + 9.6, 6.5), (z1 - 9.6, 6.5), (z1 - 8.8, 5.7), (z1 - 8.8, 2.7)],
              C, seg=64)
    k.rotation_euler = (0, -math.pi / 2, 0)
    k.location = v(HINGE_X, HINGE_Y, 0)
    apply_transform(k)
    arm = rounded_prism("_arm", rounded_rect_xz(HINGE_X - 16.0, HINGE_X + 2.0, z0 + 9.2, z1 - 9.2, 3.0), HINGE_Y + 2.0,
                        STOCK_HALF_W - 1.0, 2.0, C, seg=4)
    boolean(k, arm, op="UNION")
    boolean(o, k, op="UNION")
    # выемки на боках ложа (снимок товара): параллелограмм и длинная — на верхней перекладине; длинная — на стойке
    # (сняты со снимка товара в масштабе 5.43 пикс/мм)
    # параллелограмм — на 2.5 мм ниже снимка: верх заходил на скругление кромки ложа и выемка выходила клином (Д15)
    for pts in ([(-322.3, 26.4), (-334.7, 26.4), (-342.5, 16.7), (-328.6, 16.7)],
                [(-350.0, 29.5), (-401.0, 29.5), (-415.0, -8.0), (-408.0, -8.0), (-396.0, 20.0), (-353.0, 20.0)],
                [(-404.0, -18.0), (-412.0, -18.0), (-428.0, -58.0), (-420.0, -58.0)]):
        side_recess(o, fillet(pts, 1.6, 4), 1.2, C, half=STOCK_HALF_W)
    # проушины ложа: круглые оси затыльника (вместо винтов с шестигранником) и прорези рядом (снимок владельца 5)
    side_recess(o, _slot((-433.0, -7.5), 6.0, 2.0, 0.0), 0.9, C, half=STOCK_HALF_W)
    side_recess(o, _slot((-434.5, -89.3), 7.0, 2.0, -12.0), 0.9, C, half=STOCK_HALF_W)
    finish_small(o, w=0.4, seg=3)
    core = buttplate_core(C)
    p = buttpad(C)
    for zc in (-7.5, -83.0):
        for sgn in (1, -1):
            sc = lathe("Stock_screw", [(-0.3, 0.0), (-0.3, 3.5), (0.15, 3.5), (0.85, 2.8), (0.85, 1.9), (0.6, 1.65),
                                       (0.6, 0.0)], C, "Steel_bare", seg=48)
            sc.rotation_euler = (0, 0, math.pi / 2 if sgn > 0 else -math.pi / 2)
            sc.location = v(PIN_X, STOCK_HALF_W * sgn, zc)
            apply_transform(sc)
            finish_small(sc, w=0.3, seg=3)
            sc["owner"] = "Stock_body"
    # защёлка: кнопка с рифлением слева у шарнира (на ложе)
    lt = rounded_prism("Stock_latch", rounded_rect_xz(HINGE_X - 22.0, HINGE_X - 6.0, 35.5, 46.5, 2.0),
                       STOCK_HALF_W - 0.6, STOCK_HALF_W + 2.4, 0.8, C, "Polymer", seg=4)
    for i in range(7):
        xc = HINGE_X - 8.5 - i * 1.9
        g = prism_xz("_lt", rounded_rect_xz(xc - 0.4, xc + 0.4, 37.5, 44.5, 0.4), STOCK_HALF_W + 1.6, STOCK_HALF_W + 4, C)
        boolean(lt, g)
    finish_small(lt, w=0.2, seg=2)
    lt["owner"] = "Stock_body"
    p["owner"] = "Stock_body,Stock_buttplate_core"
    core["owner"] = "Stock_body,Stock_buttplate"
    return o, p, lt


def build(ctx):
    C = ctx["coll"]["Stock"]
    plate, pin = hinge_block(C)
    body, pad, latch = stock(C)
    return {"hinge": plate, "body": body, "pad": pad, "latch": latch}
