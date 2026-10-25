# ВСС-М v8: органы управления — спусковой крючок, предохранитель (штампованный рычаг справа под козырьком),
# переводчик огня (флажок из задней стенки скобы, образец владельца с Fab), защёлка магазина.
# Все детали строятся в исходном положении («огонь», одиночный); оси вращения — пустышки в part_rig.
import math
from mathutils import Matrix, Vector
from lib import (LOWER_W, MM, SAFETY_FIRE_DEG, SAFETY_PIVOT, SEL_HALF_T, SEL_X0, SEL_X1, SEL_Y0, SEL_Z0, SEL_Z1, apply_transform,
                 auto_sharp, box, boolean, cyl,
                 fillet, finish, join, lathe, prism_xy, prism_xz)

TRIGGER_PIVOT = (372.0, -9.0)
SAFETY_R = 6.2                 # пластина рычага вокруг оси
CATCH_PIVOT = (408.2, -38.0)


def safety_outline():
    """Контур пластины предохранителя в осях рычага (u вперёд от оси, v вверх), положение «огонь»:
    верхняя кромка поднимается к ~17 мм и плавно опускается к выемке под зуб козырька, впереди — площадка
    под палец с отогнутыми наружу полками (образец владельца с Fab)."""
    pts, rad = [], []
    for k in range(14):
        a = math.radians(75.0 + 195.0 * k / 13)
        pts.append((SAFETY_R * math.cos(a), SAFETY_R * math.sin(a)))
        rad.append(0.0)
    rad[0] = 3.0
    pts += [(12.0, -6.0), (57.2, -5.7), (59.5, -3.6), (59.5, 4.0), (58.4, 4.5), (47.8, 4.5), (46.2, 2.8), (44.6, 4.7), (17.0, 8.6)]
    rad += [2.0, 1.2, 1.0, 1.0, 0.6, 0.5, 0.4, 0.5, 7.0]
    return pts, rad


def strip(center, widths, tip_r=None):
    """Полоса вдоль ломаной center (x,z) с шириной widths[i]; возвращает замкнутый контур."""
    left, right = [], []
    n = len(center)
    for i in range(n):
        p = Vector(center[i])
        a = Vector(center[max(i - 1, 0)]); b = Vector(center[min(i + 1, n - 1)])
        t = (b - a).normalized()
        nrm = Vector((-t.y, t.x))
        left.append(tuple(p + nrm * widths[i] / 2))
        right.append(tuple(p - nrm * widths[i] / 2))
    return left + list(reversed(right))


def build(ctx):
    C = ctx["coll"]["Controls"]
    out = {}

    # --- спусковой крючок: изогнутое перо, вогнутое спереди, носик вперёд ---
    cl = []
    for i in range(13):
        t = i / 12
        x = 380.6 - 6.8 * math.sin(math.pi * t * 0.92) + 4.6 * t * t
        z = -12.5 - 29.5 * t
        cl.append((x, z))
    w = [6.0 - 2.0 * (i / 12) for i in range(13)]
    blade = strip(cl, w)
    trig = prism_xz("Trigger", fillet(blade, [1.0] + [0.6] * (len(blade) - 2) + [1.0], 3), -2.55, 2.55, C, "Steel_black")
    # ступица на оси: внутри коробки, соединена с пером
    hub = prism_xz("_thub", fillet([(366.5, -14.2), (382.0, -14.2), (382.0, -8.0), (378.0, -3.8), (369.0, -3.8), (366.5, -6.5)], 2.0, 3),
                   -2.4, 2.4, C)
    boolean(trig, hub, op="UNION")
    boolean(trig, cyl("_tp", -5, 5, 1.55, C, axis="Y", cy=TRIGGER_PIVOT[0], cz=TRIGGER_PIVOT[1], seg=20))
    finish(trig, 0.9, 3, 30)
    out["trigger"] = trig

    # --- предохранитель: штампованная пластина 2 мм с выдавленным ребром жёсткости «с изломом»,
    # впереди площадка с отогнутыми наружу верхней (под палец) и нижней полками; ось — кольцевая головка ---
    px, pz = SAFETY_PIVOT
    # рычаг отстоит от боковины на 0.85 мм (под ним головки штифтов), к оси прижат шайбой-ступицей
    y_in, y_out = -(LOWER_W + 0.85), -(LOWER_W + 2.9)
    uv, rad = safety_outline()
    lever = prism_xz("Safety_lever", [(px + u, pz + w) for u, w in fillet(uv, rad, 5)], y_out, y_in, C, "Steel_black")
    rib_c = [(px + 5.0, pz + 0.6), (px + 16.5, pz + 4.4), (px + 41.5, pz + 1.3)]
    rib = strip(rib_c, [4.6, 5.0, 4.4])
    rib = prism_xz("_srib", fillet(rib, [2.0, 3.5, 2.0, 2.0, 1.5, 2.0], 5), y_out - 0.85, y_out + 0.2, C)
    boolean(lever, rib, op="UNION")
    top_flange = prism_xy("_sfl_t", fillet([(px + 47.9, y_in - 1.0), (px + 58.6, y_in - 1.0), (px + 59.5, y_out - 4.0),
                                            (px + 48.6, y_out - 4.4)], [0.3, 0.3, 1.8, 1.8], 4), pz + 3.0, pz + 4.5, C)
    boolean(lever, top_flange, op="UNION")
    low_flange = prism_xy("_sfl_b", fillet([(px + 46.0, y_in - 1.0), (px + 57.0, y_in - 1.0), (px + 56.6, y_out - 2.6),
                                            (px + 46.6, y_out - 2.8)], [0.3, 0.3, 1.4, 1.4], 4), pz - 5.95, pz - 4.6, C)
    boolean(lever, low_flange, op="UNION")
    # керн на площадке (как на образце)
    boolean(lever, cyl("_sdim", y_out - 1.0, y_out + 0.35, 0.8, C, axis="Y", cy=px + 50.6, cz=pz - 0.6, seg=16))
    boolean(lever, cyl("_shub", -(LOWER_W - 0.05), y_in + 0.3, 4.2, C, axis="Y", cy=px, cz=pz, seg=32), op="UNION")
    finish(lever, 0.55, 3, 30)
    # головка оси: кольцо, канавка, выпуклая середина
    head = lathe("Safety_axis_head", [(0, 0), (0, 4.5), (0.55, 4.45), (0.95, 4.1), (1.0, 3.5), (0.75, 3.2), (0.75, 2.9),
                                      (1.25, 2.75), (1.55, 2.3), (1.65, 0)], C, "Steel_black", 40, 0, 0)
    head.rotation_euler = (0, 0, -math.pi / 2)
    head.location = (px * MM, (y_out + 0.1) * MM, pz * MM)
    apply_transform(head)
    auto_sharp(head, 35)
    # положение «огонь»: контур повернут передом вверх на SAFETY_FIRE_DEG вокруг оси
    for o in (lever, head):
        o.data.transform(Matrix.Translation((-px * MM, 0, -pz * MM)))
        o.data.transform(Matrix.Rotation(math.radians(-SAFETY_FIRE_DEG), 4, "Y"))
        o.data.transform(Matrix.Translation((px * MM, 0, pz * MM)))
    out["safety"] = join([lever, head], "Safety_lever")
    # ось предохранителя: торец слева
    lpin = lathe("Safety_axis_end_L", [(0, 0), (0, 3.0), (0.4, 2.8), (0.7, 2.2), (0.8, 0)], C, "Steel_black", 24, 0, 0)
    lpin.rotation_euler = (0, 0, math.pi / 2)
    lpin.location = (px * MM, (LOWER_W - 0.05) * MM, pz * MM)
    apply_transform(lpin)
    auto_sharp(lpin, 40)
    out["safety_axis_L"] = lpin

    # --- переводчик огня: флажок в скобе (образец владельца), хвостовик в пазу задней стенки; на боках флажка —
    # вертикальная насечка под палец (его сдвигают вбок) ---
    prof = fillet([(SEL_X0, SEL_Z0 + 0.6), (SEL_X1 - 1.6, SEL_Z0), (SEL_X1, SEL_Z0 + 1.8), (SEL_X1, SEL_Z1 - 1.2),
                   (SEL_X1 - 1.2, SEL_Z1), (SEL_X0, SEL_Z1)], [0.4, 1.0, 1.0, 1.0, 0.8, 0.4], 4)
    sel = prism_xz("Fire_selector", prof, SEL_Y0 - SEL_HALF_T, SEL_Y0 + SEL_HALF_T, C, "Steel_black")
    grooves = []
    for s_ in (-1, 1):
        y_face = SEL_Y0 + s_ * SEL_HALF_T
        for k in range(4):
            x = SEL_X1 - 1.9 - 1.25 * k
            ya, yb = sorted((y_face - s_ * 0.3, y_face + s_ * 1.0))
            grooves.append(box(f"_selg{s_}_{k}", x - 0.3, x + 0.3, ya, yb, SEL_Z0 + 1.6, SEL_Z1 - 1.4, C))
    boolean(sel, join(grooves, "_selg"))
    finish(sel, 0.35, 3, 30)
    out["selector"] = sel

    # --- защёлка магазина: верхнее плечо с зубом в шахте, лопатка вниз перед скобой ---
    cx, cz = CATCH_PIVOT
    paddle = fillet([(cx - 2.2, cz + 2.5), (cx - 0.5, cz + 9.0), (cx + 9.0, cz + 9.2), (cx + 9.0, cz + 7.6), (cx + 2.4, cz + 6.8),
                     (cx + 2.4, cz - 4.0), (cx + 1.2, cz - 22.5), (cx + 2.6, cz - 25.8), (cx - 1.4, cz - 26.6), (cx - 2.6, cz - 23.0),
                     (cx - 1.4, cz - 5.0)],
                    [2.0, 1.0, 0.6, 0.5, 0.8, 3.0, 2.5, 1.2, 1.2, 2.5, 3.0], 4)
    catch = prism_xz("Magazine_catch", paddle, -7.0, 7.0, C, "Steel_black")
    # сужение верхнего плеча до ширины паза
    for s in (-1, 1):
        boolean(catch, box(f"_cn{s}", cx - 5, cx + 8, s * 3.6, s * 9, cz - 6.5, cz + 12, C))
    # рифление на лопатке спереди
    rib = [box(f"_cr{i}", cx - 4.0, cx - 1.9, -8, 8, cz - 24.5 + 1.6 * i, cz - 23.9 + 1.6 * i, C) for i in range(6)]
    boolean(catch, join(rib, "_crib"))
    boolean(catch, cyl("_cp", -8, 8, 1.6, C, axis="Y", cy=cx, cz=cz, seg=20))
    finish(catch, 0.6, 3, 30)
    out["catch"] = catch
    return out
