# ПП по мотивам KRISS Vector Gen II: затворная группа (видна в окне выброса справа и в пазу рукоятки слева) и рукоятка
# заряжания слева (в пазу коробки, при стрельбе не ходит — тянет затвор только рукой, за выступ-тягу затвора).
# Затвор: головка вокруг канала выступает вперёд, верх затвора отнесён назад ступенькой; зеркало с чашкой под донце
# .45 ACP, ударник в канале (видно остриё), штифт ударника поперёк; выбрасыватель справа — рычаг в пазу с когтем,
# заходящим в проточку гильзы, на вертикальной оси; слева снизу — паз под отражатель (неподвижный, стоит на дне полости
# позади шахты: гильза бьёт в него в конце хода и вылетает вправо-вверх в окно); слева сверху — тяга, за которую
# рукоятка тянет затвор (в покое — зазор 4 мм, при стрельбе рукоятка стоит). Владелец 04.11: «внутри почти пусто —
# затворную группу, гильзу, выбрасыватель, ход затвора проработать максимально подробно».
# Рукоятка: ползун в пазу, плоский рычаг по борту, выступ под пальцы спереди; в покое — на 34 мм дальше от дула, чем
# в v03 (h1ggs: X 6…70; владелец: «затвор дальше от дула»).
import math
import bpy
from lib import (MM, HALF_W, prism_xz, prism_xy, prism_yz, box, cyl, lathe, boolean, fillet, finish_small, v)
from part_receiver import CH_SLOT_Z, rounded_rect_xz

BOLT_X = (-64.3, -0.3)            # затвор в переднем положении: зеркало — на казённом срезе (X 0) с зазором 0.3
BOLT_HALF_W = 13.2
BOLT_Z = (-10.5, 30.0)
BOLT_HEAD_TOP = 12.0             # выше — верх затвора отнесён назад на 6 мм (головка выступает)
BOLT_TRAVEL = 45.0               # ход затвора назад (зеркало за задней кромкой окна)
CH_X = (6.0, 70.0)               # рукоятка заряжания в переднем положении (h1ggs; было 40…104)
CH_TRAVEL = BOLT_TRAVEL + 3.9    # рукоятка выбирает зазор 4 мм до тяги и тянет затвор на весь ход
CH_KNOB_X = (49.0, 69.0)
CH_KNOB_OUT = 7.5                # выступ наружу от борта в покое (был 12: теперь рычаг откидывается — владелец 05.11)
CH_PIVOT = (9.5, 1.9)            # ось откидывания рычага: X и вынос от борта (вертикальная, в середине толщины рычага)
CH_SWING = 22.0                  # на сколько градусов носок рычага отходит влево при оттяжке (part_rig)
ARM_X = (-12.0, 2.0)             # тяга затвора под рукоятку (слева сверху, выходит в паз)
ARM_Z = (18.2, 22.8)
ARM_Y = (12.0, 17.9)
EJECTOR_X = (-62.0, -42.0)       # отражатель: носок — X −42 (зеркало в заднем положении — X −45.3)
EJECTOR_Y = (2.9, 4.5)
EJECTOR_Z = (-16.0, -3.0)          # основание утоплено в дно полости (сверка v04b Н8: висел в 0.47 мм)
EXT_Z = (-2.3, 5.3)              # выбрасыватель по высоте
FP_X = (-19.0, -1.8)             # ударник: остриё в 0.2 мм за дном чашки
FPR_X, FPR_Z = -12.0, 2.2        # штифт ударника — слева, глухой (справа — паз выбрасывателя), над осью ударника
FPR_Y = (-4.5, BOLT_HALF_W - 0.25)


def bolt(C):
    x0, x1 = BOLT_X
    z0, z1 = BOLT_Z
    hb = BOLT_HALF_W
    # профиль сбоку: головка до X x1 ниже Z 12, выше — ступенька назад на 6 мм со скосом
    prof = fillet([(x0, z0), (x1, z0), (x1, BOLT_HEAD_TOP), (x1 - 3.0, BOLT_HEAD_TOP + 3.0), (x1 - 6.0, BOLT_HEAD_TOP + 3.0),
                   (x1 - 6.0, z1), (x0, z1)], [3.0, 2.0, 1.2, 1.5, 1.5, 2.5, 3.0], 5)
    b = prism_xz("Bolt", prof, -hb, hb, C, "Steel_nitride")
    # зеркало: чашка под донце гильзы (Ø12.4, глубина 1.3) и канал ударника Ø2.4
    boolean(b, cyl("_cup", x1 - 1.3, x1 + 1.0, 6.2, C, seg=64))
    boolean(b, cyl("_fp", -6.0, x1 + 0.5, 1.2, C, seg=24))
    boolean(b, cyl("_fpw", FP_X[0] - 1.5, -5.5, 1.75, C, seg=24))       # за головкой канал шире — под бурт ударника
    # пазы под направляющие коробки по обоим бокам (Z 22–25, глубина 1.4) — справа виден в окне выброса
    for s in (1, -1):
        y0, y1 = (hb - 1.4, hb + 2) if s > 0 else (-hb - 2, -hb + 1.4)
        boolean(b, prism_xz("_rail", rounded_rect_xz(x0 - 2, x1 + 2, 22.0, 25.0, 1.4), y0, y1, C))
    # паз выбрасывателя справа: от боковины до чашки (по контуру рычага с зазором 0.15)
    boolean(b, prism_xy("_extslot", extractor_slot_plan(), EXT_Z[0] - 0.15, EXT_Z[1] + 0.15, C))
    # паз отражателя слева снизу — во всю длину, открыт вниз и в чашку
    boolean(b, box("_ejslot", x0 - 2, x1 + 2, EJECTOR_Y[0] - 0.35, EJECTOR_Y[1] + 0.35, z0 - 2, EJECTOR_Z[1] + 0.5, C))
    # выемка снизу под верхний патрон магазина (затвор проходит над губками)
    u = prism_yz("_feed", fillet([(-7.5, -12.0), (7.5, -12.0), (5.5, -7.5), (-5.5, -7.5)], [0, 0, 2.0, 2.0], 4),
                 x0 + 8.0, x1 - 6.0, C)
    boolean(b, u)
    # тяга под рукоятку заряжания — заодно с затвором
    arm = prism_xz("_arm", rounded_rect_xz(ARM_X[0], ARM_X[1], ARM_Z[0], ARM_Z[1], 1.6), ARM_Y[0], ARM_Y[1], C)
    boolean(b, arm, op="UNION")
    # отверстия штифтов: ударника (поперёк, Z 0 — за чашкой) и тяги (Z 20.5, виден справа в окне)
    boolean(b, cyl("_fph", FPR_Y[0] - 0.1, hb + 1, 1.3, C, seg=24, cy=FPR_X, cz=FPR_Z, axis="Y"))
    boolean(b, cyl("_aph", -hb - 1, -hb + 6.0, 1.55, C, seg=24, cy=-5.0, cz=20.5, axis="Y"))   # глухое, справа
    # облегчающая выборка на правой боковине под пазом (видна в окне, когда затвор открыт)
    boolean(b, prism_xz("_lw", rounded_rect_xz(-58.0, -30.0, 14.0, 19.5, 2.2), -hb - 2, -hb + 1.2, C))
    finish_small(b, w=0.6, seg=3)
    return b


def extractor_plan(gap=0.0):
    """Выбрасыватель в плане (XY): рычаг вдоль правой боковины, спереди — коготь до проточки гильзы (r 5.6), над
    закраиной (r 6.0, X 0…1.2) — зазор, в проточке (X 1.4…2.2) — выступ."""
    hb = BOLT_HALF_W
    g = gap
    pts = [(-23.0 - g, -hb - 0.2 - g), (-23.0 - g, -hb + 2.2 + g), (-6.0, -hb + 2.2 + g), (-3.5, -7.2 + g),
           (1.38 + g, -6.35 + g), (1.44 + g, -5.65 + g), (2.2 + g, -5.65 + g), (2.4 + g, -6.6), (2.4 + g, -hb - 0.2 - g)]
    return fillet(pts, [0.8, 0.8, 2.0, 1.5, 0.15, 0.15, 0.3, 0.4, 0.8], 3)


def extractor_slot_plan():
    """Паз выбрасывателя в затворе (план XY): по рычагу с зазором 0.15, у зеркала — открыт в чашку (внутренняя стенка
    на r 5.4 — без плёнки нулевой толщины между пазом и чашкой r 6.2)."""
    hb = BOLT_HALF_W
    pts = [(-23.15, -hb - 0.4), (-23.15, -hb + 2.35), (-6.0, -hb + 2.35), (-3.6, -7.1), (-1.9, -5.4), (2.6, -5.4),
           (2.6, -hb - 0.4)]
    return fillet(pts, [0.8, 0.9, 2.0, 1.2, 0.4, 0.0, 0.0], 3)


def extractor(C):
    e = prism_xy("Extractor", extractor_plan(0.0), EXT_Z[0], EXT_Z[1], C, "Steel_bare")
    finish_small(e, w=0.2, seg=2)
    # ось выбрасывателя — вертикальный штифт; пружинный упор — цилиндр за осью, поперёк
    pin = cyl("Extractor_pin", EXT_Z[0] - 0.3, EXT_Z[1] + 0.3, 1.0, C, "Steel_bare", seg=24, cy=-17.0,
              cz=-BOLT_HALF_W + 1.0, axis="Z")
    finish_small(pin, w=0.15, seg=2)
    pin["owner"] = "Extractor,Bolt"
    e["owner"] = "Bolt"
    return e, pin


def firing_pin(C):
    """Ударник: остриё Ø1.8 с полусферой, тело Ø2.3, сзади бурт; поперёк — вырез под штифт."""
    xa, xb = FP_X
    prof = [(xa, 0.0), (xa, 1.6), (xa + 1.5, 1.6), (xa + 1.5, 1.12), (xb - 1.6, 1.12), (xb - 1.2, 0.9)]
    for k in range(1, 7):
        a = math.pi / 2 * k / 6
        prof.append((xb - 1.2 + 1.2 * math.sin(a), 0.9 * math.cos(a)))
    fp = lathe("Firing_pin", prof, C, "Steel_bare", seg=24, cz=0.0)
    # лыска под штифт (штифт Ø2.56 над осью) — ударник ходит на ±2 мм
    boolean(fp, box("_fpn", FPR_X - 3.3, FPR_X + 3.3, -2.0, 2.0, FPR_Z - 1.4, 3.0, C))
    fp["owner"] = "Bolt"
    pin = cyl("Firing_pin_retainer", FPR_Y[0], FPR_Y[1], 1.28, C, "Steel_bare", seg=24, cy=FPR_X, cz=FPR_Z, axis="Y",
              ch=0.25)
    pin["owner"] = "Bolt,Firing_pin"
    # штифт справа (виден в окне выброса) — глухой: сквозное отверстие в тяге давало вывернутую грань (сверка v04 Д3)
    arm_pin = cyl("Bolt_arm_pin", -BOLT_HALF_W + 0.2, -BOLT_HALF_W + 5.8, 1.52, C, "Steel_bare", seg=24, cy=-5.0,
                  cz=20.5, axis="Y", ch=0.3)
    arm_pin["owner"] = "Bolt"
    return fp, pin, arm_pin


def ejector(C):
    """Отражатель — пластина на дне полости позади шахты, носок со скосом (неподвижен; основание утоплено в дно)."""
    xa, xb = EJECTOR_X
    za, zb = EJECTOR_Z
    pl = fillet([(xa, za), (xb, za), (xb, zb - 2.5), (xb - 2.0, zb), (xa + 6.0, zb), (xa, zb - 4.0)],
                [0.5, 0.5, 0.6, 0.6, 2.0, 1.5], 3)
    e = prism_xz("Ejector", pl, EJECTOR_Y[0], EJECTOR_Y[1], C, "Steel_bare")
    finish_small(e, w=0.2, seg=2)
    e["owner"] = "Receiver"
    return e


def charging_handle(C):
    z0, z1 = CH_SLOT_Z
    x0, x1 = CH_X
    # Складная рукоятка (владелец 05.11: «цепляются пальцем, при движении на себя она отводится ещё влево»): ползун
    # в пазу берёт тягу затвора; рычаг вдоль борта сидит на вертикальной оси у заднего конца — в покое прилегает,
    # при оттяжке носок с выступом отходит влево на CH_SWING (part_rig), под палец — удобный зацеп
    from lib import boolean_safe, set_origin
    px, pr = CH_PIVOT
    py = HALF_W + pr
    # ползун в пазу (зазор 0.4 по высоте и до дна паза) и ушко оси снизу — из паза наружу под шарнир рычага
    sl = prism_xz("Charging_handle_slider", rounded_rect_xz(x0, x1 - 2.0, z0 + 0.4, z1 - 0.4, 1.6),
                  HALF_W - 4.75, HALF_W + 0.4, C, "Steel_black")
    lug = box("_lug", px - 2.0, px + 2.0, HALF_W - 0.5, py, z0 + 0.5, 19.6, C)
    boolean(lug, cyl("_lugr", z0 + 0.5, 19.6, 2.0, C, seg=40, cy=px, cz=py, axis="Z"), op="UNION")
    boolean_safe(sl, lug, op="UNION", name="ушко ползуна")
    finish_small(sl, w=0.35, seg=3)
    # рычаг вдоль борта: плоская полоса 3 мм, сзади — шарнир (втулка Ø4 на оси), к переду утолщается в выступ под пальцы
    # у оси верх рычага горизонтален (Z 26.5): втулка той же высоты, что и конец рычага, — без ступенек (ступеньки по
    # 0.2 мм ломали мелкую фаску — «шип» в борт)
    arm = prism_xz("Charging_handle", fillet([(px, 20.0), (CH_KNOB_X[0], 20.0), (CH_KNOB_X[0] + 2.0, 21.5),
                                              (CH_KNOB_X[1], 22.0), (CH_KNOB_X[1], 30.6), (CH_KNOB_X[0] + 3.0, 30.8),
                                              (CH_KNOB_X[0], 27.8), (px + 6.0, 26.5), (px, 26.5)],
                                             [0.0, 3.0, 2.0, 2.5, 3.0, 3.0, 4.0, 3.0, 0.0], 5),
                   HALF_W + 0.4, HALF_W + 3.4, C, "Steel_black")
    # втулка Ø3.4 — на 0.2 толще рычага с обеих сторон, до борта остаётся 0.2
    knuckle = cyl("_knuckle", 20.0, 26.5, 1.7, C, seg=48, cy=px, cz=py, axis="Z")
    boolean_safe(arm, knuckle, op="UNION", name="втулка рычага")
    # выступ под пальцы: наружу на CH_KNOB_OUT, клином назад, с поперечными рёбрами по верху
    knob_plan = fillet([(CH_KNOB_X[0] + 1.0, HALF_W + 3.0), (CH_KNOB_X[1], HALF_W + 3.0), (CH_KNOB_X[1], HALF_W + CH_KNOB_OUT),
                        (CH_KNOB_X[1] - 6.0, HALF_W + CH_KNOB_OUT)], [1.5, 1.5, 2.0, 3.5], 5)
    k = prism_xy("_knob", knob_plan, 22.5, 30.4, C)
    boolean(arm, k, op="UNION")
    for i in range(4):
        xg = CH_KNOB_X[1] - 3.5 - i * 3.2
        g = prism_xy("_kg", fillet([(xg - 0.8, HALF_W + 3.9), (xg + 0.8, HALF_W + 3.9), (xg + 0.8, HALF_W + 20.0),
                                     (xg - 0.8, HALF_W + 20.0)], [0.8, 0.8, 0, 0], 3), 29.6, 33.0, C)
        boolean(arm, g)
    finish_small(arm, w=0.6, seg=3)
    set_origin(arm, (px, py, 23.0))
    # ось шарнира с головкой сверху — через ушко ползуна и втулку рычага
    pin = cyl("Charging_handle_pin", z0 + 0.7, 26.8, 0.9, C, "Steel_bare", seg=24, cy=px, cz=py, axis="Z", ch=0.25)
    hd = cyl("_chph", 26.4, 27.1, 1.3, C, seg=32, cy=px, cz=py, axis="Z", ch=0.3)
    boolean(pin, hd, op="UNION")
    finish_small(pin, w=0.15, seg=2)
    sl["owner"] = "Charging_handle,Charging_handle_pin"
    pin["owner"] = "Charging_handle,Charging_handle_slider"
    arm["owner"] = "Charging_handle_slider,Charging_handle_pin"
    return sl, arm


def chambered_round(C):
    """Патрон в патроннике: донце на казённом срезе (X 0) — виден в окне, когда затвор отведён."""
    from part_magazine import cartridge, CART_LEN
    case, bullet = cartridge("Round_chamber", C)
    for o in (case, bullet):
        o.data.transform(__import__("mathutils").Matrix.Translation(v(CART_LEN / 2, 0.0, 0.0)))
        o["owner"] = "Barrel"
    case.name, bullet.name = "Round_chamber_case", "Round_chamber_bullet"
    return case, bullet


def build(ctx):
    C = ctx["coll"]["Bolt_group"]
    b = bolt(C)
    e, pin = extractor(C)
    fp, fpr, ap = firing_pin(C)
    ej = ejector(C)
    rc = chambered_round(C)
    sl, arm = charging_handle(ctx["coll"]["Controls"])
    return {"bolt": b, "extractor": e, "ch": arm, "ch_slider": sl, "firing_pin": fp, "ejector": ej, "round": rc}
