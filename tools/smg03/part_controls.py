# ПП по мотивам KRISS Vector Gen II SMG: органы управления и мелкие детали боков.
# Спуск — контур со снимка KRISS (data/profiles.json, trigger) и ось внутри коробки; предохранитель — двусторонний
# флажок у оси (X −153, Z 39, снимок A); переводчик огня (у SMG отдельный, двусторонний) — флажок у оси (X −50, Z 37,
# лист KRISS SMG); защёлка магазина — лопатка на переднем ребре шахты с обеих сторон (снимок A); справа (X −38, Z −10,
# снимок B) — гладкий квадратный выступ, не орган управления. Затворная задержка — слева под рукояткой заряжания
# (руководство KRISS Vector Gen 2, снимок A): один рычаг-качалка с рифлёными концами на крепёжном блоке, по бокам
# рёбра-«радиатор». Задний конец (к прикладу) при отведённой рукоятке ставит затвор на задержку, передний (к дулу)
# снимает; после последнего патрона затвор встаёт на задержку сам (владелец 05.11, руководство).
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
STUD_R = (-38.0, -10.0)            # гладкий квадратный выступ справа (снимок B) — неподвижный
CATCH_PADS = ((-43.0, -32.0), (-11.5, -2.5))   # рифлёные концы рычага задержки: задний (ставит), передний (снимает)
CATCH_Z = (1.5, 13.5)
CATCH_PIVOT_X = (CATCH_PADS[0][0] + CATCH_PADS[1][1]) / 2   # ось качалки — посередине, вертикальная
CATCH_DEG = 3.0                    # ход качалки: конец утапливается на ~1 мм
MAG_REL = (-15.0, -38.0)           # лопатка защёлки магазина у переднего ребра шахты (на 8 мм назад: перёд шахты скруглён R 14,
                                   # выемка не должна касаться начала скругления — иначе боковина после булевых «перекручивалась»)


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


def _ss_l(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _renormal(me):
    """После переноса вершин (с зеркалом) — нормали наружу заново."""
    import bmesh
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    me.update()


def lever(name, pivot, hub_r, tail, side, C, mat="Steel_black"):
    """Флажок на оси (как у прототипа, h1ggs и снимок владельца 04): круглая ступица с осью, плоский рычаг к хвосту tail
    (x, z), конец загнут крючком вверх; на конце — упор под палец: рампа, поднимающаяся от рычага наружу на 3.6 мм, с
    поперечным рифлением (владелец 04.11: «удобные выступы для пальцев»). side = ±1 (борт)."""
    from lib import apply_transform
    px, pz = pivot
    tx, tz = tail
    ang = math.atan2(tz - pz, tx - px)
    L = math.hypot(tx - px, tz - pz)
    hs = 1.0 if math.cos(ang) > 0 else -1.0          # крючок — вверх (к +Z) при любом направлении рычага
    ca, sa = math.cos(ang), math.sin(ang)

    def W(u, w):
        w = w * hs
        return (px + u * ca - w * sa, pz + u * sa + w * ca)
    w_hub, w_tip = hub_r * 0.8, 2.4
    # контур в осях рычага (u — к хвосту, w — к крючку): ступица, нижняя кромка, носок, крючок, верхняя кромка
    loc = []
    for k in range(15):
        a = math.pi / 2 + math.pi * k / 14
        loc.append((hub_r * math.cos(a), hub_r * math.sin(a)))
    loc += [(L * 0.45, -w_tip - 0.4), (L + 1.4, -w_tip), (L + 2.0, 1.5), (L + 0.6, 5.2), (L - 1.6, 5.4),
            (L - 2.6, 3.0), (L * 0.5, w_tip + 0.2)]
    radii = [0.0] * 15 + [6.0, 1.6, 1.8, 1.4, 1.2, 1.4, 6.0]
    pts = [W(u, w) for u, w in fillet(loc, radii, 5)]
    if hs < 0:
        pts.reverse()
    y0, y1 = (HALF_W + 0.3, HALF_W + 0.3 + LEVER_T) if side > 0 else (-HALF_W - 0.3 - LEVER_T, -HALF_W - 0.3)
    o = rounded_prism(name, pts, y0, y1, 0.9, C, mat, seg=4)
    # упор под палец (сверка v04 Д14: был брусок, приставленный к хвосту; у прототипа упор гладкий, отогнут наружу):
    # наружная половина пластины к носку плавно отгибается наружу на 3.4 мм — упор из самого рычага, без булевых
    H = 3.4
    ymid = (y0 + y1) / 2
    # крышки рычага — сеткой (иначе изогнутый многоугольник затеняется диагональю)
    import bmesh
    bm = bmesh.new(); bm.from_mesh(o.data)
    caps = [f for f in bm.faces if len(f.verts) > 8]
    tri = bmesh.ops.triangulate(bm, faces=caps, quad_method="BEAUTY", ngon_method="BEAUTY")["faces"]
    edges = list({e for f in tri for e in f.edges})
    bmesh.ops.subdivide_edges(bm, edges=edges, cuts=3, use_grid_fill=True)
    bm.to_mesh(o.data); bm.free()
    for vv in o.data.vertices:
        x, y, z = vv.co.x / MM, vv.co.y / MM, vv.co.z / MM
        u = (x - px) * ca + (z - pz) * sa
        h = H * _ss_l((u - (L - 7.5)) / 6.3)
        if h > 0 and (y - ymid) * side > 0:
            vv.co.y = (y + side * h) * MM
    o.data.update()
    # ось — шайба в ступице
    axle = cyl(f"{name}_axle", (y1 - 0.2) if side > 0 else (y0 - 0.7), (y1 + 0.7) if side > 0 else (y0 + 0.2),
               hub_r * 0.5, C, mat, seg=48, cy=px, cz=pz, axis="Y", ch=0.3)
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


def right_stud(C):
    """Справа под окном выброса — гладкий квадратный выступ (снимок KRISS B, владельца 04): без гнезда и рисок, не
    кнопка. Прежде он был сделан «кнопкой задержки», которой у Vector справа нет (руководство KRISS, сверка 05.11)."""
    x, z = STUD_R
    o = rounded_prism("Stud_R", rounded_rect_xz(x - 4.3, x + 4.3, z - 3.9, z + 3.9, 1.2), -HALF_W - 1.8, -HALF_W + 0.3,
                      0.6, C, "Steel_black", seg=4)
    finish_small(o, w=0.2, seg=2)
    o["owner"] = "Receiver"
    return o


def _knurl_pad(name, xa, xb, yin, yout, za, zb, C):
    """Рифлёный конец рычага: вид сверху (XY) — прямоугольник, наружная грань волной (рёбра поперёк, шаг 1.6, глубина
    0.35, к краям на нет), выдавлен по высоте (Z). Рифление — в самом контуре: прорези резцами рвали рёбра (v05)."""
    import mathutils
    P, dep = 1.6, 0.35
    # волна — между углами (по 1 мм от концов ровно), углы скруглены 0.8
    n = int((xb - xa - 2.0) / 0.2)
    outer = []
    for k in range(n + 1):
        x = (xb - 1.0) - (xb - xa - 2.0) * k / n
        edge = min(x - xa, xb - x)
        taper = max(0.0, min(1.0, (edge - 1.2) / 0.6))
        y = yout - dep * (0.5 - 0.5 * math.cos(2 * math.pi * (x - xa) / P)) * taper
        outer.append((x, y))
    pts = [(xa, yin), (xb, yin), (xb, yout)] + outer + [(xa, yout)]
    radii = [0.8, 0.8, 0.8] + [0.0] * len(outer) + [0.8]
    pts = fillet(pts, radii, 4)
    o = rounded_prism(name, pts, za, zb, 0.25, C, "Steel_black", seg=3, smooth=(0.2, 0))
    # контур строился в (x, «z» = y), выдавлен по «y» = высота — меняем местами Y и Z
    o.data.transform(mathutils.Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1))))
    _outward(o)
    return o


def _outward(o):
    """Перестановка осей зеркалит сетку — грани внутрь (рычаг выходил вывернутым, торцы чёрные): по знаку объёма
    развернуть."""
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(o.data)
    # пересчёт нормалей у этого рычага сам выворачивал его (объём < 0) — решает знак объёма
    _bm.ops.recalc_face_normals(bm, faces=bm.faces)
    if bm.calc_volume(signed=True) < 0:
        _bm.ops.reverse_faces(bm, faces=bm.faces)
    bm.to_mesh(o.data); bm.free()


def bolt_catch(C, y0):
    """Рычаг затворной задержки — качалка на вертикальной оси посередине: два рифлёных конца, перемычка и накладка
    оси с двумя отверстиями (снимок A). Задний конец утоплен — затвор на задержке, передний — затвор отпущен."""
    from lib import boolean_safe
    yin, yout = y0 + 2.9, y0 + 5.2          # под концами до основания 1.3 мм — ход ~1 мм
    za, zb = CATCH_Z
    (ra, rb), (fa, fb) = CATCH_PADS
    o = _knurl_pad("Bolt_catch", ra, rb, yin, yout, za, zb, C)
    boolean_safe(o, _knurl_pad("_pad_f", fa, fb, yin, yout, za, zb, C), op="UNION", name="конец задержки")
    bar = rounded_prism("_cbar", rounded_rect_xz(rb - 1.0, fa + 1.0, 8.0, 12.0, 1.0), yin + 0.05, yin + 1.6, 0.4, C,
                        seg=3)
    boolean_safe(o, bar, op="UNION", name="перемычка задержки")
    px = CATCH_PIVOT_X
    plate = rounded_prism("_cplate", rounded_rect_xz(px - 6.25, px + 6.25, 6.5, 13.5, 1.5), yin + 0.05, yout - 0.1, 0.5,
                          C, seg=3)
    for xh in (px - 2.75, px + 2.75):
        boolean(plate, cyl("_ch", yout - 0.9, yout + 1.0, 1.3, C, seg=32, cy=xh, cz=10.0, axis="Y"))
    boolean_safe(o, plate, op="UNION", name="накладка оси задержки")
    _outward(o)
    finish_small(o, w=0.15, seg=2)
    # торцы концов у перемычки — большие грани у вогнутого стыка: при сглаживании нормалей чёрные; острыми — рёбра
    # круче 30° (скругления контура и рифление мельче — остаются гладкими)
    from lib import mark_sharp, weighted, apply_all
    mark_sharp(o, 30.0)
    weighted(o)
    apply_all(o)
    set_origin(o, (px, yin, 10.0))
    # ось качалки — бобышка от основания до рычага (скрыта накладкой)
    boss = rounded_prism("Bolt_catch_boss", rounded_rect_xz(px - 2.2, px + 2.2, 7.5, 12.5, 0.8), y0 + 1.3, yin + 0.3, 0.3,
                         C, "Steel_black", seg=2)
    o["owner"] = "Side_block,Bolt_catch_boss"
    boss["owner"] = "Side_block,Bolt_catch"
    return o


def side_block(C, mw):
    """Левая площадка у шахты (снимок A): основание, две рифлёные кнопки, верхняя и нижняя планки с винтами, рёбра
    спереди и сзади. Рёбра и основание — одно тело с корпусом шахты не делаем: отдельная деталь, на винтах."""
    y0 = HALF_W - 0.4
    base = rounded_prism("Side_block", rounded_rect_xz(-45.0, -1.0, -12.5, 14.0, 2.5), y0, y0 + 1.6, 0.6, C, "Steel_black",
                         seg=3)
    # рычаг затворной задержки (качалка) с осью
    bolt_catch(C, y0)
    # крепёжный блок рычага — с двумя винтами (снимок A, руководство: «bolt catch/release lever mounting block»)
    for nm, (xa, xb, za, zb) in (("Side_plate_low", (-29.0, -13.0, -11.0, 0.0)),):
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
    bpy.data.objects["Side_plate_low"]["owner"] = "Side_block"
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
    br = right_stud(C)
    sb = side_block(C, ctx["parts"].get("receiver", {}).get("magwell"))
    return {"trigger": t, "safety": (sl, sr), "selector": (fl, fr), "mag_release": (ml, mr), "stud": br}
