# ВСС-М v8: органы управления — спусковой крючок, предохранитель (рычаг справа, как у АК), переводчик огня
# (поперечная кнопка позади спуска внутри скобы), защёлка магазина (лопатка перед скобой).
# Все детали строятся в исходном положении; оси вращения — пустышки в part_rig.
import math
from mathutils import Matrix, Vector
from lib import (LOWER_W, MM, apply_transform, auto_sharp, box, boolean, cyl, fillet, finish, join, lathe, prism_xz, set_origin)

TRIGGER_PIVOT = (372.0, -9.0)
SAFETY_PIVOT = (347.0, -11.0)
SAFETY_FIRE_DEG = 6.5          # рычаг поднят над горизонталью в положении «огонь»
SAFETY_SAFE_DEG = 16.0         # «предохранитель»: выступ рычага встаёт на пути рукоятки взведения
SELECTOR_C = (352.0, -29.5)
CATCH_PIVOT = (408.2, -38.0)


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

    # --- предохранитель: ступица на оси, плечо вперёд, на конце отогнутый наружу выступ с насечкой ---
    px, pz = SAFETY_PIVOT
    arm = fillet([(px - 7.0, pz - 1.5), (px - 4.0, pz - 6.6), (px + 6.0, pz - 5.6), (px + 52.0, pz - 3.1), (px + 58.5, pz - 2.4),
                  (px + 59.5, pz + 2.6), (px + 52.0, pz + 3.1), (px + 8.0, pz + 5.4), (px - 4.0, pz + 6.6)],
                 [3.0, 3.5, 6.0, 2.0, 1.4, 1.4, 2.0, 6.0, 3.5], 5)
    lever = prism_xz("Safety_lever", arm, -(LOWER_W + 2.2), -(LOWER_W + 0.15), C, "Steel_black")
    tab = prism_xz("_stab", fillet([(px + 50.5, pz - 3.0), (px + 59.5, pz - 2.4), (px + 59.5, pz + 2.6), (px + 50.5, pz + 3.1)], [0.8, 1.2, 1.2, 0.8], 3),
                   -(LOWER_W + 7.3), -(LOWER_W + 1.5), C)
    boolean(lever, tab, op="UNION")
    ser = [box(f"_ss{i}", px + 51.4 + 1.25 * i, px + 51.9 + 1.25 * i, -(LOWER_W + 8.5), -(LOWER_W + 6.4), pz - 5, pz + 5, C) for i in range(7)]
    boolean(lever, join(ser, "_sser"))
    finish(lever, 0.7, 3, 30)
    head = lathe("Safety_axis_head", [(0, 0), (0, 5.2), (0.6, 5.0), (1.4, 4.2), (1.7, 0)], C, "Steel_black", 32, 0, 0)
    head.rotation_euler = (0, 0, -math.pi / 2)
    head.location = (px * MM, -(LOWER_W + 2.1) * MM, pz * MM)
    apply_transform(head)
    boolean(head, box("_hsl", px - 0.4, px + 0.4, -30, -(LOWER_W + 3.1), pz - 6, pz + 6, C))
    auto_sharp(head, 35)
    # исходное положение «огонь»: рычаг повернут вверх на SAFETY_FIRE_DEG вокруг оси
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

    # --- переводчик огня: поперечная кнопка; в положении «одиночный» выступает справа ---
    sx, sz = SELECTOR_C
    e_r, e_l = -(LOWER_W + 3.1), LOWER_W - 1.7
    sel = lathe("Fire_selector", [(e_r, 0.0), (e_r, 2.3), (e_r + 0.4, 2.75), (-12.4, 2.75), (-12.0, 2.45), (-11.4, 2.45),
                                  (-11.0, 2.75), (e_l - 0.4, 2.75), (e_l, 2.3), (e_l, 0.0)], C, "Steel_bare", 32, 0, 0)
    sel.rotation_euler = (0, 0, math.pi / 2)
    sel.location = (sx * MM, 0, sz * MM)
    apply_transform(sel)
    # торец кнопки справа (−Y) — с выпуклой шляпкой, слева — плоский
    auto_sharp(sel, 30)
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
