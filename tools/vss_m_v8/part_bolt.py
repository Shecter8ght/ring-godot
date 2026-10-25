# ВСС-М v8: затворная группа. Длинный ход поршня над стволом, затвор поворотный с шестью боевыми упорами.
# Закрытое положение: зеркало затвора x=472 (казённый срез патронника), рама x 360…465, ход рамы 74 мм.
# Затвор: свободный ход рамы 6 мм, поворот на 30° на участке 6…14 мм, дальше идёт с рамой (постановочно).
import math
from mathutils import Matrix
from lib import (BORE_Z, MM, apply_transform, auto_sharp, box, boolean, cyl, fillet, finish, join, lathe,
                 prism_xy, prism_xz, prism_yz)

CARRIER_X0, CARRIER_X1 = 360.0, 465.0
PISTON_Z = 27.0
BOLT_FACE_X = 474.5


def rot_x_about_bore(o, deg):
    o.data.transform(Matrix.Translation((0, 0, -BORE_Z * MM)))
    o.data.transform(Matrix.Rotation(math.radians(deg), 4, "X"))
    o.data.transform(Matrix.Translation((0, 0, BORE_Z * MM)))


def build(ctx):
    C = ctx["coll"]["Bolt_group"]
    out = {}

    # --- затворная рама ---
    # сечение: верх скруглён под крышку, низ — полки направляющих; канал затвора снизу
    from lib import CARRIER_W, CAV_W
    sec = fillet([(-CARRIER_W, 3.6), (CARRIER_W, 3.6), (CARRIER_W, 30.5), (7.2, 37.5), (-7.2, 37.5), (-CARRIER_W, 30.5)],
                 [1.0, 1.0, 3.0, 3.0, 3.0, 3.0], 4)
    car = prism_yz("Bolt_carrier", sec, CARRIER_X0, CARRIER_X1, C, "Steel_black")
    boolean(car, cyl("_bb", 350, 470, 7.25, C, seg=48))                              # канал затвора
    boolean(car, cyl("_gr", 340, 400, 4.6, C, cz=28.0, seg=32))                       # гнездо направляющей пружины
    # задний верх рамы скошен: при полном отводе рама проходит под скосом крышки
    boolean(car, prism_xz("_rch", [(350.0, 22.0), (360.0, 22.0), (380.0, 37.6), (380.0, 45.0), (350.0, 45.0)], -20.0, 20.0, C))
    boolean(car, box("_ejg", 350.0, 470.0, 6.3, 12.8, 2.0, 6.6, C))                    # продольный паз под отражатель
    # фигурный паз (кулачок) поворота затвора — справа сверху: прямой участок и наклон
    cam = prism_xz("_cam", [(404.0, 12.5), (411.0, 12.5), (420.0, 19.5), (426.0, 19.5), (426.0, 23.5), (418.0, 23.5),
                            (409.0, 16.5), (404.0, 16.5)], -20.0, -4.0, C)
    boolean(car, cam)
    # облегчающие выборки по бокам рамы
    for s in (-1, 1):
        boolean(car, prism_xz(f"_rl{s}", fillet([(368.0, 16.0), (398.0, 16.0), (398.0, 27.0), (368.0, 27.0)], 2.0, 3),
                              s * (CARRIER_W - 0.5), s * 20.0, C))
    finish(car, 0.7, 3, 35)
    # пылезащитная плита справа: закрывает окно, на ней клеймо номера
    plate = prism_xz("Bolt_carrier_plate", fillet([(405.6, 3.9), (475.0, 3.9), (475.0, 29.4), (405.6, 29.4)], [1.2, 1.2, 1.2, 1.2], 3),
                     -14.45, -12.2, C, "Steel_black")
    boolean(plate, cyl("_ph", -20, -5, 1.7, C, axis="Y", cy=462.0, cz=24.0, seg=20))  # отверстие под выколотку
    from part_stamps import stamp, SUB
    stamp(plate, SUB, 2.2, (424.0, -14.45, 8.4), (0, -1, 0), (0, 0, 1), 0.12, C)
    finish(plate, 0.6, 3, 35)
    # перемычка плиты к раме
    web = box("Bolt_carrier_web", 405.6, 455.0, -12.5, -11.5, 6.0, 26.0, C, "Steel_black")
    finish(web, 0.25, 1, 35)
    # рукоятка взведения: стержень через паз справа, крюк с пологим изгибом вперёд
    # рукоятка взведения — изогнутое перо, как спусковой крючок: выходит из паза наружу и загибается вперёд,
    # вогнутая передняя грань с поперечной насечкой под палец (замечание владельца 25.10)
    from mathutils import Vector as _V
    n_c = 16
    cl, wd = [], []
    for i in range(n_c + 1):
        t = i / n_c
        cl.append((466.5 + 15.0 * t ** 2.2, -12.0 - 29.0 * t + 2.0 * t ** 3))
        wd.append(7.8 - 3.2 * t)
    left, right = [], []
    for i in range(n_c + 1):
        a = _V(cl[max(i - 1, 0)]); b = _V(cl[min(i + 1, n_c)])
        tg = (b - a).normalized()
        nrm = _V((tg.y, -tg.x))                       # назад (−X) от осевой линии
        left.append(tuple(_V(cl[i]) + nrm * wd[i] / 2))
        right.append(tuple(_V(cl[i]) - nrm * wd[i] / 2))
    outline = left + list(reversed(right))
    rad = [0.6] + [0.0] * (n_c - 1) + [2.2, 2.2] + [0.0] * (n_c - 1) + [0.6]
    handle = prism_xy("Charging_handle", fillet(outline, rad, 5), 4.6, 9.7, C, "Steel_black")
    # насечка: поперечные риски на вогнутой передней грани, вдоль высоты
    cuts = []
    for k in range(9):
        t = 0.38 + 0.065 * k
        i = min(int(t * n_c), n_c - 1)
        f = t * n_c - i
        p = _V(cl[i]).lerp(_V(cl[i + 1]), f)
        tg = (_V(cl[i + 1]) - _V(cl[i])).normalized()
        nrm = _V((tg.y, -tg.x))
        w = 7.8 - 3.2 * t
        c = p - nrm * (w / 2)                          # передняя (вогнутая) грань
        g = box(f"_hs{k}", -0.32, 0.32, -0.7, 0.7, 3.0, 11.0, C)
        ang = math.atan2(tg.y, tg.x)
        g.data.transform(Matrix.Rotation(ang, 4, "Z"))
        g.data.transform(Matrix.Translation((c.x * MM, c.y * MM, 0)))
        cuts.append(g)
    boolean(handle, join(cuts, "_hsc"))
    finish(handle, 0.8, 3, 30)
    out["carrier"] = car
    out["plate"] = plate
    out["web"] = web
    out["handle"] = handle

    # --- шток поршня и поршень (над стволом, под цевьём) ---
    rod = lathe("Gas_piston_rod", [(464.0, 0.0), (464.0, 4.0), (470.0, 4.0), (470.0, 3.3), (548.0, 3.3), (549.0, 5.6),
                                   (557.0, 5.6), (557.5, 5.2), (559.0, 5.2), (559.6, 4.6), (559.6, 0.0)],
                C, "Steel_black", 32, 0.0, PISTON_Z)
    # канавки поршня
    for i, x in enumerate((551.0, 553.6)):
        boolean(rod, lathe(f"_pg{i}", [(x, 0), (x, 7), (x + 0.8, 7), (x + 0.8, 0)], C, None, 32, 0, PISTON_Z, closed=True))
    auto_sharp(rod, 30)
    out["piston"] = rod

    # --- затвор ---
    bolt = lathe("Bolt", [(418.0, 0.0), (418.0, 5.4), (419.0, 6.2), (466.5, 6.2), (466.5, 6.8), (BOLT_FACE_X - 0.6, 6.8),
                          (BOLT_FACE_X, 6.2), (BOLT_FACE_X, 0.0)], C, "Steel_bare", 48)
    # чашка под донце гильзы и отверстие ударника
    boolean(bolt, cyl("_cup", BOLT_FACE_X - 1.3, BOLT_FACE_X + 2, 5.85, C, seg=48))
    boolean(bolt, cyl("_fp", BOLT_FACE_X - 10, BOLT_FACE_X + 2, 1.1, C, seg=16))
    # паз выбрасывателя справа и отражателя слева
    boolean(bolt, box("_ext", 458.0, 476.0, -8.0, -4.6, 8.4, 11.6, C))
    boolean(bolt, box("_ejs", 417.0, 476.0, 4.0, 8.0, 8.9, 11.1, C))
    # шесть боевых упоров: в закрытом положении (заперто) — 0°, 60°, … от вертикали
    lugs = []
    for k in range(6):
        l = box(f"_blug{k}", 470.0, 474.0, -2.25, 2.25, BORE_Z + 5.5, BORE_Z + 9.5, C)
        rot_x_about_bore(l, 60 * k)
        lugs.append(l)
    lugobj = join(lugs, "_bolt_lugs")
    boolean(bolt, lugobj, op="UNION")
    # боевой выступ-ведущий (под кулачок рамы), справа сверху
    cam_pin = cyl("_camp", -12.5, -5.0, 2.4, C, axis="Y", cy=407.0, cz=BORE_Z + 4.6, seg=24)
    boolean(bolt, cam_pin, op="UNION")
    finish(bolt, 0.4, 2, 35)
    out["bolt"] = bolt
    # выбрасыватель — отдельная деталь на затворе
    ext = prism_xz("Bolt_extractor", fillet([(457.5, 8.6), (475.1, 8.6), (475.9, 10.2), (474.5, 11.4), (457.5, 11.4)], [1, 0.3, 0.3, 0.3, 1], 3),
                   -7.6, -4.9, C, "Steel_bare")
    finish(ext, 0.2, 1, 35)
    out["extractor"] = ext
    fpin = lathe("Bolt_firing_pin_tip", [(BOLT_FACE_X - 3.0, 0.0), (BOLT_FACE_X - 3.0, 1.0), (BOLT_FACE_X - 1.2, 1.0), (BOLT_FACE_X - 1.0, 0.7), (BOLT_FACE_X - 1.0, 0.0)],
                 C, "Steel_bare", 16)
    out["firing_pin"] = fpin

    # --- возвратный механизм: направляющая и пружина (под крышкой) ---
    guide = lathe("Recoil_spring_guide", [(291.5, 0.0), (291.5, 2.0), (396.0, 2.0), (396.5, 1.5), (396.5, 0.0)], C, "Steel_bare", 20, 0, 28.0)
    auto_sharp(guide, 30)
    out["guide"] = guide
    out["spring"] = spring("Recoil_spring", 292.5, 394.0, 3.6, 0.6, 26, C, cz=28.0)
    # отражатель на левой направляющей коробки (неподвижный)
    ej = prism_xz("Ejector_blade", fillet([(419.0, 2.0), (440.0, 2.0), (440.0, 3.4), (424.0, 3.4), (424.0, 6.0), (419.0, 6.0)], [0.5, 0.5, 0.5, 0.5, 0.8, 0.8], 2),
                  6.6, 12.4, C, "Steel_bare")
    out["ejector"] = ej
    # направляющие рамы на внутренних стенках коробки
    rails = []
    for s in (-1, 1):
        from lib import CAV_W as _CW
        rails.append(box(f"Carrier_rail_{s}", 290.0, 466.0, s * _CW - s * 0.9, s * _CW, 1.6, 3.6, C, "Steel_black"))
    out["rails"] = join(rails, "Receiver_inner_rails")
    return out


def spring(name, x0, x1, r, wire, turns, coll, cy=0.0, cz=BORE_Z):
    """Витая пружина вдоль X: спираль из трубки."""
    import bpy
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    sp = cu.splines.new("POLY")
    n = turns * 16
    sp.points.add(n)
    for i in range(n + 1):
        t = i / n
        a = 2 * math.pi * turns * t
        sp.points[i].co = ((x0 + (x1 - x0) * t) * MM, (cy + r * math.cos(a)) * MM, (cz + r * math.sin(a)) * MM, 1.0)
    cu.bevel_depth = wire * MM
    cu.bevel_resolution = 2
    o = bpy.data.objects.new(name, cu)
    coll.objects.link(o)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.curves.remove(cu)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    from lib import material
    me.materials.append(material("Spring_steel"))
    for p in me.polygons:
        p.use_smooth = True
    return ob
