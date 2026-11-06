# «Осока»: тепловизионный прицел — короб с окуляром по мотивам 1ПН97 «Маугли-2М» (ночной прицел «Вербы»), своё
# название и маркировка (решение владельца 2026-11-06). Форма high-poly на приёмку: прицел и сборка на принятой
# «Осоке» (Осока_геометрия_v07.blend). Запуск (из папки RING):
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
#     --python tools/osoka/sight_build.py -- <Осока_геометрия_v07.blend> <сборка.blend> <прицел.blend>
#
# Оси — как у «Осоки» (мм): +X вперёд по трубе, +Z вверх, +Y — левая сторона стрелка. Габарит настоящего 1ПН97М
# 256 × 135 × 109 мм, ≤ 1,5 кг (missilery.info «Верба» со ссылкой на ЛОМО); доли объектива, корпуса, окуляра и
# высоты осей — по снимкам Кузьмина «Армия-2016» 02 и «МАКС-2015» 49 (вид слева, масштаб по длине 256 мм).
# Ставится как настоящий: лапа кронштейна — на основание ночного прицела сверху трубы (Mount_plate «Осоки»), короб
# вынесен влево к глазу стрелка (снимок ЛОМО: стрелок с «Вербой», прицел слева над трубой); целик и мушка сложены.
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import lib  # noqa: E402
from lib import MM, v, lathe, loft_yz, fillet, finish, finish_small, material, empty, set_parent, boolean  # noqa: E402

# ---------- размеры (мм, оси «Осоки») ----------
YC = 48.0            # середина корпуса и ось окуляра: влево от оси трубы, как линия открытого прицела (диоптр y ≈ 49)
ZB = 78.0            # низ корпуса (над кронштейном; v02: на 4.9 мм выше сложенного целика)
H, L, W = 133.0, 115.0, 109.0          # корпус: высота, длина, ширина (габарит 1ПН97М: высота 135, ширина 109)
XR = 1125.0          # задняя стенка корпуса. v02 (владелец: «как стрелок дотянется глазом»): раструб наглазника
                     # x ≈ 1068 — там, где глаз с открытым прицелом (в игре 1071: хват 1258.6 − ads_z 188); у настоящего
                     # (снимок «МАКС-2015» 48) наглазник над коробом пускового механизма, ~8 см впереди его заднего края
XF = XR + L          # передняя стенка (крышка)
R_FRONT = 18.0       # передний верхний угол корпуса скруглён (снимок 02: дуга ~18 мм)
Z_OBJ = ZB + 75.0    # ось объектива (снимок 02: центр на 58 мм ниже верха корпуса)
Z_EYE = ZB + 58.0    # ось окуляра (75 мм ниже верха)
R_TOP, R_BOT = 30.0, 8.0               # скругление сечения корпуса: верх (крыша округлая, снимок 49), низ
CHAMFER = (36.0, 24.0)                 # скос заднего низа (снимок 02 крупно: от окуляра вниз-вперёд): высота, длина
# нижний цилиндр под объективом (отсек питания с рифлёной крышкой) и окно дневного канала
YB, ZBT, RB = 22.0, ZB + 17.0, 21.0
YD, ZD = 82.0, ZB + 18.0
# переключатель «ВЫКЛ — ДЕНЬ — ТЕПЛО» на левом боку у переднего низа
SW = (XF - 49.0, ZB + 34.0)
CONN = (XF - 17.0, ZB + 23.0)          # круглый разъём с крышкой — левый бок у переднего низа (снимок 02)
SW_DEG = 50.0        # ход рычажка от среднего положения
# откидная крышка объектива (владелец 2026-11-06: «крышку объектива тоже давай сделаем», выбрал откидную на петле):
# кольцо на оправе, петля сверху, крышка открывается вверх-вперёд
CAP_PIVOT = (XF + 88.5, Z_OBJ + 49.0)
CAP_OPEN_DEG = 150.0
# кронштейн: лапа на основании (Mount_plate «Осоки»: x 1200.6…1316.6, y −11…15, верх 49.5; на нём ремень до y −19,
# верх 53.2 — лапа мостом над ремнём, за пряжкой x ≥ 1230), верхняя площадка с ласточкиным хвостом под корпусом
FOOT_X = (1201.0, 1227.0)
PLATE_TOP = 49.5
SADDLE_TOP = 45.9
BRIDGE_Z = (55.0, 65.0)
# площадка — только под передней частью корпуса (как у настоящего, снимок 02): сзади под корпусом лежит сложенный
# целик (x ≤ 1177, верх 73) и колпачок индикатора (x ≤ 1181.5, верх 66.5)
TOP_PLATE = (1184.0, 1236.0, -25.0, 74.0, 65.0, 72.0)     # x0, x1, y0, y1, z0, z1
RAIL_X = (1186.0, 1234.0)
ROOT = (1214.0, 2.0, PLATE_TOP)        # точка крепления: середина лапы на основании

# цвета нейтральные — форма на приёмку (отделка — этап текстур)
lib._MAT_COLORS.update({
    "Sight_paint_black": ((0.030, 0.030, 0.032), 0.55, 0.0),   # корпус: чёрная краска (на снимках — шагрень)
    "Sight_metal_black": ((0.028, 0.028, 0.030), 0.45, 0.6),   # оправы, фланцы: анодированный алюминий
    "Germanium": ((0.045, 0.045, 0.055), 0.08, 0.85),          # линза объектива тепловизора
})


def coll_new(name, parent):
    c = bpy.data.collections.new(name)
    parent.children.link(c)
    return c


def knurl_ring(name, x0, x1, R, Ri, depth, n_around, coll, mat, cy, cz, rows=0, spp=4, ch=0.8, seg_min=0):
    """Рифлёное кольцо вокруг оси || X через (cy, cz): rows = 0 — продольные рифли, rows > 0 — сетка квадратиков
    (резиновое кольцо фокуса объектива, снимок 02). Полое: внутренняя стенка на Ri (закрыта корпусом)."""
    seg = max(n_around * spp, seg_min)
    xs = []                      # (x, тип): 'o' — наружная поверхность (с рифлением), 'c' — фаска, 'i' — внутренняя
    xs.append((x0, Ri + 0.3, "i0"))
    xs.append((x0, R - ch, "c"))
    nx = max(rows * spp, 4)
    for i in range(nx + 1):
        xx = x0 + ch + (x1 - x0 - 2 * ch) * i / nx
        groove = rows > 0 and i % spp == 0 and 0 < i < nx
        xs.append((xx, R, "g" if groove else "o"))
    xs.append((x1, R - ch, "c"))
    xs.append((x1, Ri + 0.3, "i0"))
    xs.append((x1 - 0.3, Ri, "i0"))
    xs.append((x0 + 0.3, Ri, "i0"))
    bm = bmesh.new()
    rings = []
    for xx, r0, kind in xs:
        ring = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            r = r0
            if kind in ("o", "g"):
                rib = (k % spp == 0)
                if kind == "g" or rib:
                    r = r0 - depth
            ring.append(bm.verts.new(v(xx, cy + r * math.cos(a), cz + r * math.sin(a))))
        rings.append(ring)
    m = len(rings)
    for i0 in range(m):
        i1 = (i0 + 1) % m
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((rings[i0][k], rings[i0][j], rings[i1][j], rings[i1][k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = lib._obj(name, me, coll, mat)
    lib.auto_sharp(o, 40)
    return o


def lathe_axis(name, prof, coll, mat, axis, center, seg=96):
    """Тело вращения вокруг оси axis ('Y' или 'Z') через center (мм): prof = [(t, r)], t — вдоль оси."""
    o = lathe(name, prof, coll, mat, seg=seg)
    if axis == "Y":
        o.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
    elif axis == "Z":
        o.data.transform(Matrix.Rotation(-math.pi / 2, 4, "Y"))
    o.data.transform(Matrix.Translation(v(*center)))
    return o


def catmull_closed(pts, sub):
    """Замкнутый профиль сглаженной кривой Катмулла — Рома через точки (sub отрезков на участок): у тела вращения
    из редких точек на силуэте видны изломы (наглазник, проба v01)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2, p3 = (Vector(pts[(i + k) % n]) for k in (-1, 0, 1, 2))
        for j in range(sub):
            t = j / sub
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((q.x, q.y))
    return out


def knob_y(name, x, z, y0, y1, r, coll):
    """Рифлёная головка винта с осью ‖ Y (y0 — у детали, y1 — наружу) и торцевой крышкой."""
    ln = y1 - y0
    k = knurl_ring(name, -ln / 2, ln / 2, r, 1.2, 0.5, 24, coll, "Steel_black", 0.0, 0.0, rows=0, spp=4, ch=0.6)
    cap = lathe(name + "_end", [(ln / 2 - 0.4, 0.0), (ln / 2 - 0.4, r - 0.8), (ln / 2 + 0.2, r - 1.5),
                                (ln / 2 + 0.35, 0.0)], coll, "Steel_black", seg=48)
    for o in (k, cap):
        o.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
        o.data.transform(Matrix.Translation(v(x, (y0 + y1) / 2, z)))
    return [k, cap]


def section(zb, zt, y0, y1, rt, rb, seg=10):
    """Сечение корпуса (Y, Z): прямоугольник со скруглением верха rt и низа rb."""
    return fillet([(y1, zb), (y1, zt), (y0, zt), (y0, zb)], [rb, rt, rt, rb], seg=seg)


# ---------- корпус ----------

def body(coll):
    y0, y1 = YC + W / 2, YC - W / 2         # y0 — левая (+Y), y1 — правая
    zt = ZB + H
    ch_z, ch_x = CHAMFER
    secs = [(XR, section(ZB + ch_z, zt, y1, y0, R_TOP, R_BOT)),
            (XR + ch_x, section(ZB, zt, y1, y0, R_TOP, R_BOT))]
    # передний верх — дугой R_FRONT: сечения опускают верх к передней стенке
    n = 8
    for i in range(n + 1):
        a = i / n * math.pi / 2
        x = XF - R_FRONT + R_FRONT * math.sin(a)
        drop = R_FRONT * (1.0 - math.cos(a))
        secs.append((x, section(ZB, zt - drop, y1, y0, R_TOP, R_BOT)))
    main = loft_yz("Thermal_body", secs, coll, "Sight_paint_black")
    finish(main, w=1.8, seg=4, angle=25)
    out = [main]
    # прилив под рельс ласточкина хвоста (низ корпуса) — сам рельс: шире книзу
    rail = loft_yz("Thermal_rail", [(RAIL_X[0], [(YC + 13, ZB + 0.5), (YC + 16, ZB - 5.9), (YC - 16, ZB - 5.9),
                                                 (YC - 13, ZB + 0.5)]),
                                    (RAIL_X[1], [(YC + 13, ZB + 0.5), (YC + 16, ZB - 5.9), (YC - 16, ZB - 5.9),
                                                 (YC - 13, ZB + 0.5)])], coll, "Sight_metal_black")
    finish(rail, w=0.5, seg=3, angle=25)
    out.append(rail)
    # блок кнопок сверху у заднего края (на снимке 02 — выступ над задней стенкой), две резиновые кнопки
    pad_pts = fillet([(XR - 6.0, zt - 4.0), (XR + 30.0, zt - 4.0), (XR + 30.0, zt + 4.0), (XR - 6.0, zt + 4.0)],
                     [2.0, 2.0, 3.0, 3.0], seg=4)
    pad = lib.rounded_prism("Thermal_key_pad", pad_pts, YC - 23.0, YC + 23.0, 2.4, coll, "Sight_paint_black")
    out.append(pad)
    for i, xx in enumerate((XR + 5.0, XR + 19.0)):
        out.append(lathe_axis(f"Thermal_key_bezel_{i}", [(zt + 3.0, 0.0), (zt + 3.0, 6.6), (zt + 5.0, 6.6),
                                                          (zt + 5.4, 6.0), (zt + 5.4, 0.0)],
                              coll, "Sight_metal_black", "Z", (xx, YC, 0.0), seg=64))
        out.append(lathe_axis(f"Thermal_key_{i}", [(zt + 4.0, 0.0), (zt + 4.0, 5.2), (zt + 6.4, 5.0),
                                                   (zt + 7.3, 4.0), (zt + 7.8, 2.2), (zt + 7.9, 0.0)],
                              coll, "Rubber_black", "Z", (xx, YC, 0.0), seg=64))
    return out


# ---------- объектив, отсек питания, дневной канал ----------

def objective(coll):
    out = []
    x = XF
    out.append(lathe("Thermal_obj_housing", [(x - 1.0, 0.0), (x - 1.0, 40.2), (x + 1.5, 40.2), (x + 2.5, 39.5),
                                             (x + 20.0, 39.5), (x + 20.6, 40.1), (x + 23.4, 40.1), (x + 24.0, 39.5),
                                             (x + 35.0, 39.5), (x + 36.0, 38.6), (x + 38.6, 38.6), (x + 38.6, 0.0)],
                     coll, "Sight_metal_black", seg=128, cy=YC, cz=Z_OBJ))
    # кольцо фокуса — резина с сеткой квадратиков ~2.6 мм (снимок 02)
    out.append(knurl_ring("Thermal_focus_ring", x + 38.6, x + 72.0, 42.0, 38.6, 0.9, 100, coll, "Rubber_black",
                          YC, Z_OBJ, rows=12, spp=4, ch=1.0))
    out.append(lathe("Thermal_obj_bezel", [(x + 72.0, 34.0), (x + 72.0, 43.0), (x + 73.0, 43.6), (x + 85.5, 43.6),
                                           (x + 87.0, 42.2), (x + 87.0, 37.8), (x + 86.4, 37.0), (x + 79.5, 37.0),
                                           (x + 79.5, 34.0)], coll, "Sight_metal_black", seg=128, cy=YC, cz=Z_OBJ))
    # линза — германий, мениск выпуклостью вперёд, утоплена в оправе на 6 мм
    out.append(lathe("Thermal_obj_lens", [(x + 82.6, 0.0), (x + 82.4, 10.0), (x + 81.9, 20.0), (x + 81.2, 30.0),
                                          (x + 80.8, 36.9), (x + 79.6, 36.9), (x + 79.9, 20.0), (x + 80.1, 0.0)],
                     coll, "Germanium", seg=128, cy=YC, cz=Z_OBJ))
    # отсек питания под объективом: короткий корпус, рифлёная крышка сеткой (снимок 02), на торце — головка винта
    out.append(lathe("Thermal_batt_housing", [(x - 1.0, 0.0), (x - 1.0, RB), (x + 7.6, RB), (x + 8.4, RB - 0.8),
                                              (x + 9.0, RB - 0.8), (x + 9.0, 0.0)],
                     coll, "Sight_metal_black", seg=96, cy=YB, cz=ZBT))
    out.append(knurl_ring("Thermal_batt_cap", x + 9.0, x + 35.0, RB + 1.4, RB - 3.0, 0.8, 52, coll,
                          "Rubber_black", YB, ZBT, rows=8, spp=4, ch=1.0))
    out.append(lathe("Thermal_batt_cap_face", [(x + 34.6, 0.0), (x + 34.6, RB - 0.2), (x + 35.6, RB - 0.4),
                                               (x + 36.4, RB - 2.2), (x + 36.6, 0.0)],
                     coll, "Sight_metal_black", seg=96, cy=YB, cz=ZBT))
    out.append(lathe("Thermal_batt_knob", [(x + 36.2, 0.0), (x + 36.2, 6.5), (x + 40.6, 6.5), (x + 41.4, 5.7),
                                           (x + 41.4, 0.0)], coll, "Plastic_black", seg=48, cy=YB + 9.0, cz=ZBT + 3.0))
    from part_launcher import slotted_screw
    out.append(slotted_screw("Thermal_batt_screw", (x + 41.4, YB + 9.0, ZBT + 3.0), (1, 0, 0), 4.0, coll,
                             "Steel_black", slot_ang=25))
    # окно дневного канала: оправа и тёмное стекло
    out.append(lathe("Thermal_day_bezel", [(x - 1.0, 0.0), (x - 1.0, 9.5), (x + 3.6, 9.5), (x + 5.0, 8.6),
                                           (x + 5.0, 6.8), (x + 4.4, 6.1), (x + 3.4, 6.1), (x + 3.4, 0.0)],
                     coll, "Sight_metal_black", seg=64, cy=YD, cz=ZD))
    out.append(lathe("Thermal_day_lens", [(x + 4.1, 0.0), (x + 4.0, 3.5), (x + 3.8, 6.0), (x + 3.45, 6.0),
                                          (x + 3.45, 0.0)], coll, "Lens", seg=64, cy=YD, cz=ZD))
    return out


def lens_cap(coll):
    """Откидная крышка объектива: жёсткое кольцо на передней оправе (не на кольце фокуса — оно вращается) с двумя
    ушками петли сверху, ось — стальной штифт поперёк (‖ Y); резиновая крышка с юбкой, выпуклым кольцом на лице, своим
    ушком посередине и язычком снизу под большой палец. Крышка — с началом на оси петли (поворот вокруг Y)."""
    out = []
    x = XF
    px_, pz = CAP_PIVOT
    out.append(lathe("Thermal_cap_ring", [(x + 76.0, 43.75), (x + 76.0, 45.6), (x + 76.6, 46.2), (x + 84.4, 46.2),
                                          (x + 85.0, 45.6), (x + 85.0, 43.75)], coll, "Plastic_black", seg=128,
                     cy=YC, cz=Z_OBJ))
    # ушки кольца: перемычка от кольца к оси и проушина вокруг оси
    for i, (ya, yb) in enumerate(((YC - 12.0, YC - 4.6), (YC + 4.6, YC + 12.0))):
        pts = [(x + 79.0, Z_OBJ + 43.9), (px_, Z_OBJ + 43.9), (px_, pz - 3.2)]
        for k in range(1, 12):
            a = -math.pi / 2 + math.pi * k / 12
            pts.append((px_ + 3.2 * math.cos(a), pz + 3.2 * math.sin(a)))
        pts += [(px_, pz + 3.2), (x + 79.0, pz + 3.2)]
        pts = fillet(pts, [1.0, 0.0, 0.0] + [0.0] * 11 + [0.0, 1.2], seg=3)
        out.append(lib.rounded_prism(f"Thermal_cap_lug_{i}", pts, ya, yb, 0.6, coll, "Plastic_black",
                                     smooth=(0.4, 0)))
    pin = lathe_axis("Thermal_cap_pin", [(YC - 12.6, 0.0), (YC - 12.6, 1.6), (YC - 12.0, 1.6), (YC - 12.0, 1.3),
                                         (YC + 12.0, 1.3), (YC + 12.0, 1.6), (YC + 12.6, 1.6), (YC + 12.6, 0.0)],
                     coll, "Steel_black", "Y", (px_, 0.0, pz), seg=32)
    out.append(pin)
    # крышка: юбка, лицо с выпуклым кольцом; сверху вырез под ушки кольца
    lid = lathe("Thermal_cap", [(x + 88.2, 0.0), (x + 88.2, 44.1), (x + 85.6, 44.1), (x + 85.6, 45.7), (x + 86.4, 46.4),
                                (x + 90.2, 46.4), (x + 91.3, 45.4), (x + 91.5, 41.0), (x + 92.3, 40.2), (x + 92.3, 37.0),
                                (x + 91.6, 36.2), (x + 91.8, 20.0), (x + 92.0, 0.0)],
                coll, "Rubber_black", seg=128, cy=YC, cz=Z_OBJ)
    cut = lib.box("_cap_notch", x + 84.5, x + 94.0, YC - 12.5, YC + 12.5, Z_OBJ + 41.6, Z_OBJ + 60.0, coll)
    boolean(lid, cut)
    finish_small(lid, w=0.5, seg=2, angle=40)
    web = lib.rounded_prism("Thermal_cap_web", fillet([(x + 88.0, Z_OBJ + 40.6), (x + 91.2, Z_OBJ + 40.6),
                                                        (x + 91.2, pz), (x + 88.0, pz)], [0.8, 0.8, 0.0, 0.0], seg=3),
                            YC - 4.2, YC + 4.2, 0.6, coll, "Rubber_black", smooth=(0.4, 0))
    knuckle = lathe_axis("Thermal_cap_knuckle", [(YC - 4.2, 0.0), (YC - 4.2, 2.6), (YC - 3.7, 3.2), (YC + 3.7, 3.2),
                                                 (YC + 4.2, 2.6), (YC + 4.2, 0.0)], coll, "Rubber_black", "Y",
                         (px_, 0.0, pz), seg=48)
    tab = lib.rounded_prism("Thermal_cap_tab", fillet([(x + 88.4, Z_OBJ - 51.0), (x + 91.2, Z_OBJ - 51.0),
                                                        (x + 91.2, Z_OBJ - 44.0), (x + 88.4, Z_OBJ - 44.0)],
                                                       [1.2, 1.2, 0.0, 0.0], seg=4),
                            YC - 7.0, YC + 7.0, 0.8, coll, "Rubber_black", smooth=(0.4, 0))
    lib.set_origin(lid, (px_, YC, pz))
    for o in (web, knuckle, tab):
        set_parent(o, lid)
    out += [lid, web, knuckle, tab]
    return out


# ---------- окуляр ----------

def eyepiece(coll):
    """Окуляр (снимок 02 крупно): рифлёное кольцо диоптрий выходит из скоса заднего низа корпуса, гладкое кольцо
    с винтиком, наглазник — резиновая «луковица», шейка и плоский раструб; край наглазника чуть длиннее с правой
    (височной) стороны — стрелок смотрит правым глазом (труба на правом плече, прицел слева над ней)."""
    out = []
    x = XR
    out.append(lathe("Thermal_eye_tube", [(x + 22.0, 0.0), (x + 22.0, 26.0), (x - 9.2, 26.0), (x - 9.2, 27.6),
                                          (x - 13.4, 27.6), (x - 14.0, 27.0), (x - 14.0, 0.0)],
                     coll, "Sight_metal_black", seg=128, cy=YC, cz=Z_EYE))
    out.append(knurl_ring("Thermal_diopter_ring", x - 9.0, x + 4.0, 30.5, 26.0, 0.7, 80, coll, "Sight_metal_black",
                          YC, Z_EYE, rows=4, spp=4, ch=0.9))
    from part_launcher import slotted_screw
    out.append(slotted_screw("Thermal_eye_screw", (x - 11.6, YC, Z_EYE - 27.6), (0, 0, -1), 2.4, coll,
                             "Steel_black", slot_ang=0))
    prof = [(x - 13.6, 24.0), (x - 13.6, 26.0), (x - 17.0, 27.8), (x - 23.0, 29.0), (x - 29.0, 28.5),
            (x - 35.0, 25.0), (x - 40.0, 19.5), (x - 43.0, 17.5), (x - 46.0, 19.5), (x - 49.0, 24.0),
            (x - 52.0, 27.4), (x - 54.4, 28.5), (x - 56.0, 28.1), (x - 56.5, 26.8), (x - 55.8, 25.2),
            (x - 52.0, 21.0), (x - 47.0, 15.5), (x - 42.0, 13.6), (x - 34.0, 13.6), (x - 26.0, 14.5),
            (x - 20.0, 15.0), (x - 14.6, 15.0), (x - 14.0, 18.0)]
    cup = lathe("Thermal_eyecup", catmull_closed(prof, 6), coll, "Rubber_black", seg=128, cy=YC, cz=Z_EYE)
    k = math.tan(math.radians(8.0))
    for vv in cup.data.vertices:
        xx = vv.co.x / MM
        if xx < x - 44.0:
            t = min(1.0, (x - 44.0 - xx) / 12.5)
            vv.co.x += k * (vv.co.y / MM - YC) * t * MM
    out.append(cup)
    out.append(lathe("Thermal_eye_lens", [(x - 22.4, 0.0), (x - 22.6, 8.0), (x - 23.0, 15.1), (x - 21.4, 15.1),
                                          (x - 21.2, 0.0)], coll, "Lens", seg=96, cy=YC, cz=Z_EYE))
    return out


# ---------- переключатель режимов ----------

def connector(coll):
    """Круглый разъём в латунном корпусе с резиновой крышкой — левый бок у переднего низа (снимок 02 крупно:
    латунный разъём с чёрной крышкой на ремешке; ремешок не делаем — крышка надета)."""
    yl = YC + W / 2
    cx, cz = CONN
    out = [lathe_axis("Thermal_conn_flange", [(yl - 1.0, 0.0), (yl - 1.0, 12.5), (yl + 1.2, 12.5), (yl + 1.6, 12.0),
                                               (yl + 1.6, 0.0)], coll, "Brass", "Y", (cx, 0.0, cz), seg=64),
           lathe_axis("Thermal_conn_shell", [(yl + 1.6, 0.0), (yl + 1.6, 7.6), (yl + 4.2, 7.6), (yl + 4.2, 0.0)],
                      coll, "Brass", "Y", (cx, 0.0, cz), seg=64)]
    cap = knurl_ring("Thermal_conn_cap", -3.7, 3.7, 8.8, 7.0, 0.5, 30, coll, "Rubber_black", 0.0, 0.0,
                     rows=0, spp=4, ch=0.8)
    cap.data.transform(Matrix.Rotation(math.pi / 2, 4, "Z"))
    cap.data.transform(Matrix.Translation(v(cx, yl + 4.0 + 3.7, cz)))
    out.append(cap)
    out.append(lathe_axis("Thermal_conn_cap_end", [(yl + 11.0, 0.0), (yl + 11.0, 7.6), (yl + 11.7, 7.0),
                                                    (yl + 12.0, 0.0)], coll, "Rubber_black", "Y", (cx, 0.0, cz), seg=64))
    from part_launcher import slotted_screw
    for i, (dx, dz) in enumerate(((-7.5, 7.5), (7.5, 7.5), (7.5, -7.5), (-7.5, -7.5))):
        out.append(slotted_screw(f"Thermal_conn_screw_{i}", (cx + dx, yl + 1.6, cz + dz), (0, 1, 0), 2.4, coll,
                                 "Steel_black", slot_ang=30 + 60 * i))
    return out


def mode_switch(coll):
    """Поворотный переключатель «ВЫКЛ — ДЕНЬ — ТЕПЛО» на левом боку (на снимках 02, 49 — латунное основание
    с чёрным рычажком у переднего низа). Рычажок — отдельно, ось вращения ‖ Y через центр."""
    out = []
    from part_launcher import slotted_screw
    yl = YC + W / 2
    sx, sz = SW
    out.append(lathe_axis("Thermal_switch_base", [(yl - 1.0, 0.0), (yl - 1.0, 11.5), (yl + 1.6, 11.5),
                                                   (yl + 2.4, 10.8), (yl + 2.4, 9.0), (yl + 3.6, 8.4),
                                                   (yl + 3.6, 0.0)], coll, "Brass", "Y", (sx, 0.0, sz), seg=96))
    pts = fillet([(sx + 7.0, sz - 4.6), (sx - 19.0, sz - 3.2), (sx - 19.0, sz + 3.2), (sx + 7.0, sz + 4.6)],
                 [4.0, 3.0, 3.0, 4.0], seg=6)
    lever = lib.rounded_prism("Thermal_switch_lever", pts, yl + 3.6, yl + 8.2, 1.4, coll, "Plastic_black")
    knob = lathe_axis("Thermal_switch_knob", [(yl + 3.6, 0.0), (yl + 3.6, 3.4), (yl + 9.6, 3.4), (yl + 10.6, 2.6),
                                              (yl + 10.9, 0.0)], coll, "Plastic_black", "Y", (sx - 15.0, 0.0, sz),
                      seg=48)
    screw = slotted_screw("Thermal_switch_screw", (sx, yl + 8.2, sz), (0, 1, 0), 5.0, coll, "Steel_black",
                          slot_ang=20)
    lib.set_origin(lever, (sx, yl, sz))
    for o in (knob, screw):
        set_parent(o, lever)
    out += [lever, knob, screw]
    return out


# ---------- кронштейн ----------

def bracket(coll):
    """Лапа на основании ночного прицела (мостом над ремнём, губки обжимают кромки основания), верхняя площадка
    с губками ласточкина хвоста под рельсом корпуса — консолью влево, под ней ребро."""
    out = []
    xf0, xf1 = FOOT_X
    b0, b1 = BRIDGE_Z
    # лапа: сечение (Y, Z) — правая губка снаружи ремня (ремень до y −19, низ 48.6) с выступом под его краем к
    # кромке основания y −11; левая губка — к кромке y 15 (ремень до 11.5)
    # выступ правой губки под краем ремня (низ ремня там 48.55…48.9) — верх 47.5: зазор ≥ 1 мм (владелец: «чтобы
    # сквозь ремень не проходило крепление»)
    prof = [(-25.0, SADDLE_TOP + 0.05), (-11.2, SADDLE_TOP + 0.05), (-11.2, 47.5), (-21.0, 47.5), (-21.0, b0),
            (15.2, b0), (15.2, SADDLE_TOP + 0.3), (19.0, SADDLE_TOP + 0.3), (19.0, b1 + 0.5), (-25.0, b1 + 0.5)]
    prof = fillet(prof, [1.2, 0.4, 0.4, 0.6, 1.0, 1.0, 0.4, 1.2, 0.0, 0.0], seg=4)
    foot = loft_yz("Thermal_foot", [(xf0, prof), (xf1, prof)], coll, "Alu_anodized")
    x0, x1, y0, y1, z0, z1 = TOP_PLATE
    tp = loft_yz("_top", [(x0, fillet([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], 3.0, seg=4)),
                          (x1, fillet([(y0, z0), (y1, z0), (y1, z1), (y0, z1)], 3.0, seg=4))], coll, "Alu_anodized")
    boolean(foot, tp, op="UNION")
    # губки ласточкина хвоста: правая неподвижная, левая — прижимная (винт слева)
    for nm, sec in (("_jaw_r", [(YC - 21.0, z1 - 0.5), (YC - 16.45, z1 - 0.5), (YC - 14.12, z1 + 4.5),
                                (YC - 21.0, z1 + 4.5)]),
                    ("_jaw_l", [(YC + 21.0, z1 - 0.5), (YC + 16.45, z1 - 0.5), (YC + 14.12, z1 + 4.5),
                                (YC + 21.0, z1 + 4.5)])):
        sec = fillet(sec, [0.0, 0.4, 0.8, 1.2], seg=3)
        j = loft_yz(nm, [(RAIL_X[0] - 2.0, sec), (RAIL_X[1] + 2.0, sec)], coll, "Alu_anodized")
        boolean(foot, j, op="UNION")
    # ребро под консолью: от наружной грани левой губки лапы вверх-влево к площадке
    gx0, gx1 = 1217.0, 1225.0
    gsec = fillet([(18.0, SADDLE_TOP + 1.2), (66.0, z0 + 0.5), (18.0, z0 + 0.5)], [2.0, 2.0, 0.0], seg=4)
    g = loft_yz("_gusset", [(gx0, gsec), (gx1, gsec)], coll, "Alu_anodized")
    boolean(foot, g, op="UNION")
    foot.name = "Thermal_bracket"
    finish(foot, w=0.6, seg=3, angle=30)
    out.append(foot)
    from part_launcher import slotted_screw
    # винты площадки к лапе (сверху справа, где площадка не закрыта корпусом)
    for i, xx in enumerate((1206.0, 1222.0)):
        out.append(slotted_screw(f"Thermal_bracket_screw_{i}", (xx, -16.0, z1), (0, 0, 1), 5.0, coll, "Steel_black",
                                 slot_ang=30 + 50 * i))
    # прижимной винт лапы с рифлёной головкой — слева, между трубой и консолью; винт губки ласточкина хвоста — слева
    out += knob_y("Thermal_foot_knob", 1207.0, 53.4, 19.0, 30.0, 6.4, coll)
    out += knob_y("Thermal_rail_knob", 1228.0, (z0 + z1) / 2, y1 - 0.4, y1 + 10.6, 6.0, coll)
    return out


# ---------- сборка ----------

def build(src, out_asm, out_sight):
    bpy.ops.wm.open_mainfile(filepath=src)
    sc = bpy.context.scene
    top = coll_new("THERMAL", sc.collection)
    c_body = coll_new("Thermal_body", top)
    c_mount = coll_new("Thermal_mount", top)
    c_rig = coll_new("Thermal_rig", top)
    objs = []
    objs += body(c_body)
    objs += objective(c_body)
    objs += lens_cap(c_body)
    objs += eyepiece(c_body)
    objs += connector(c_body)
    sw = mode_switch(c_body)
    objs += sw
    objs += bracket(c_mount)
    root = empty("THERMAL_root", ROOT, c_rig, size=0.03, kind="ARROWS")
    ctrl = empty("THERMAL_Controls", (XR + L / 2, YC, ZB + H + 40.0), c_rig, parent=root, size=0.02, kind="SPHERE")
    ctrl["mode"] = 1.0
    ui = ctrl.id_properties_ui("mode")
    ui.update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
              description="Переключатель: 0 — ВЫКЛ, 0.5 — ДЕНЬ, 1 — ТЕПЛО")
    ctrl["cap"] = 0.0
    ctrl.id_properties_ui("cap").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0,
                                        description="Крышка объектива: 0 — закрыта, 1 — откинута")
    # метки для игры: глаз (за наглазником на оси окуляра), ось объектива
    empty("Thermal_eye_point", (XR - 62.0, YC, Z_EYE), c_rig, parent=root, size=0.01)
    empty("Thermal_obj_axis", (XF + 87.0, YC, Z_OBJ), c_rig, parent=root, size=0.01)
    lever = bpy.data.objects["Thermal_switch_lever"]
    for o in objs:
        if o.parent is None:
            set_parent(o, root)
    from part_rig import add_driver
    add_driver(lever, "rotation_euler", 1, f"radians({SW_DEG})*(1.0-2.0*mode)", ctrl, ["mode"])
    add_driver(bpy.data.objects["Thermal_cap"], "rotation_euler", 1, f"-radians({CAP_OPEN_DEG})*cap", ctrl, ["cap"])
    for o in objs:
        if o.type == "MESH":
            for p in o.data.polygons:
                p.use_smooth = True
    # «Осока»: с прицелом целик и мушка сложены
    oc = bpy.data.objects.get("OSOKA_Controls")
    if oc is not None:
        oc["rear_sight"] = 0.0
        oc["front_sight"] = 0.0
        oc.update_tag()
    ctrl.update_tag()
    sc.frame_set(1)
    bpy.context.view_layer.update()
    tri = sum(len(o.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh().loop_triangles)
              for o in objs if o.type == "MESH")
    print("THERMAL_OBJECTS", len(objs), "TRIS", tri)
    os.makedirs(os.path.dirname(out_asm), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_asm, compress=True)
    print("SAVED", out_asm)
    # прицел отдельно: только THERMAL, точка крепления — в начало координат
    keep = {o.name for o in bpy.data.objects if any(c.name.startswith(("THERMAL", "Thermal_")) for c in o.users_collection)}
    for o in list(bpy.data.objects):
        if o.name not in keep:
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(bpy.data.collections):
        if not c.name.startswith(("THERMAL", "Thermal_")):
            bpy.data.collections.remove(c)
    root.location = (0.0, 0.0, 0.0)
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_sight, compress=True)
    print("SAVED", out_sight)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    build(*argv[:3])
