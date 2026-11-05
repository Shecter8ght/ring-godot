# «Осока»: ракета ЗР-36 (по образцу 9М336) — Ø72 (КБМ), длина корпуса 1545 мм по пропорциям снимка захваченной ракеты
# (cap_01: при этой длине диаметр выходит 72.2 мм). Отсеки по снимку: хвостовой блок с соплом и четырьмя изогнутыми
# стабилизаторами на шарнирах (17…111 мм), двигатель, серебристый пояс (875…920), БЧ (920…1062), отсек с окнами
# оптического датчика цели (1062…1225, окна на 1097 и 1142), чёрное кольцо (1225…1255), два руля (корень 1237…1277,
# складываются назад в продольные пазы), чёрное кольцо (1321…1345), головка самонаведения (1345…1540) с куполом в
# обечайке и иглой. Локальная ось +X от торца сопла; в трубе — X = MISSILE_X0.
import math
import bmesh
import bpy
from mathutils import Matrix, Vector
from lib import MM, v, lathe, cyl, boolean_safe, _obj, fillet, rounded_prism, set_origin, join, finish_small, empty
import dims as D

R = D.MISSILE_R
L = D.MISSILE_LEN
TAIL_R = 29.5                 # хвостовой блок под сложенными стабилизаторами
FIN_CHORD = (19.0, 109.0)     # стабилизаторы: от 19 до 109 мм от торца сопла
FIN_SPAN_DEG = 86.0           # сложенный охватывает 86° окружности (R 31) → размах ~47 мм
RUDDER_X = 1283.0             # передняя кромка корня руля (ось шарнира): корень 1262…1283 — за кольцом 1
RUDDER_CHORD = 21.0
RUDDER_SPAN = 118.0
WINDOWS_X = (1097.0, 1142.0)
WINDOW_ANG = 28.0             # окна выше и ниже бокового меридиана
NOSE_X = 1540.0


def body(coll):
    prof = [
        (0.0, 0.0), (0.0, 17.5), (1.0, 19.0), (6.0, 21.5), (16.0, 24.0),          # сопло снаружи
        (17.0, TAIL_R - 1.5), (18.0, TAIL_R),                                          # хвостовой блок
        (108.0, TAIL_R), (110.0, TAIL_R + 1.0),
        (124.0, R - 2.2), (138.0, R - 0.3), (142.0, R),                               # переход к двигателю
        (873.0, R), (875.0, R - 0.25), (920.0, R - 0.25), (922.0, R),                # место пояса
        (1223.0, R), (1224.0, R - 0.3), (1257.0, R - 0.3), (1258.0, R),              # место кольца 1
        (1319.0, R), (1320.0, R - 0.3), (1346.0, R - 0.3), (1347.0, R),              # место кольца 2
        (NOSE_X - 22.0, R), (NOSE_X - 9.0, R - 1.6), (NOSE_X - 2.0, R - 5.0), (NOSE_X, R - 8.5),   # плечо обечайки
        (NOSE_X, R - 11.0), (NOSE_X - 12.0, R - 11.5), (NOSE_X - 12.0, 0.0),
    ]
    o = lathe("Missile_body", prof, coll, "Missile_grey", seg=144)
    # горловина сопла внутри
    noz = lathe("_noz", [(-1.0, 0.0), (-1.0, 15.5), (3.0, 15.0), (14.0, 9.0), (16.0, 0.0)], coll, None, seg=64)
    boolean_safe(o, noz, name="nozzle")
    return o


def rings(coll):
    out = []
    for name, x0, x1, mat, r in (("Missile_band", 875.0, 920.0, "Fin_steel", R + 0.1),
                                 ("Missile_ring_1", 1224.0, 1257.0, "Missile_band", R + 0.5),
                                 ("Missile_ring_2", 1320.0, 1346.0, "Missile_band", R + 0.5)):
        prof = [(x0, R - 0.5), (x0, r - 0.4), (x0 + 0.4, r), (x1 - 0.4, r), (x1, r - 0.4), (x1, R - 0.5)]
        out.append(lathe(name, prof, coll, mat, seg=144))
    return out


def windows(target, coll):
    """Окна датчика цели: Ø10 в латунной оправе, по два ряда (выше и ниже бокового меридиана) с обеих сторон."""
    lenses = []
    k = 0
    for x in WINDOWS_X:
        for side in (1, -1):
            for up in (1, -1):
                ang = math.radians(90.0 * (1 - side) + side * up * WINDOW_ANG)   # от +Y по кругу
                d = Vector((0.0, math.cos(ang), math.sin(ang)))
                if side < 0:
                    d = Vector((0.0, -math.cos(math.radians(up * WINDOW_ANG)), math.sin(math.radians(up * WINDOW_ANG))))
                rot = Vector((1, 0, 0)).rotation_difference(d).to_matrix().to_4x4()
                cut = lathe("_win", [(R - 2.0, 0.0), (R - 2.0, 5.6), (R + 3.0, 5.6), (R + 3.0, 0.0)], coll, None, seg=40)
                cut.data.transform(rot)
                cut.data.transform(Matrix.Translation(v(x, 0, 0)))
                boolean_safe(target, cut, name="window")
                rim = lathe(f"Missile_window_rim_{k}", [(R - 2.0, 4.0), (R - 2.0, 5.6), (R - 0.4, 5.6), (R - 0.1, 5.2),
                                                         (R - 0.1, 4.4), (R - 0.6, 4.0)], coll, "Brass", seg=40)
                lens = lathe(f"Missile_window_lens_{k}", [(R - 2.2, 0.0), (R - 2.2, 4.1), (R - 1.2, 4.1), (R - 1.0, 0.0)],
                             coll, "Lens", seg=40)
                for o in (rim, lens):
                    o.data.transform(rot)
                    o.data.transform(Matrix.Translation(v(x, 0, 0)))
                lenses += [rim, lens]
                k += 1
    return lenses


def rudder_slots(target, coll, extra=()):
    """Продольные пазы под сложенные рули (сверху и снизу): от оси шарнира назад на размах, глубина — хорда."""
    for s in (1, -1):
        # резец выше поверхности на 2 мм — прорезает и кольцо 1 (оно на 0.5 мм над корпусом)
        pts = fillet([(RUDDER_X - RUDDER_SPAN - 2.0, -2.0), (RUDDER_X + 1.0, -2.0), (RUDDER_X + 1.0, RUDDER_CHORD + 1.5),
                      (RUDDER_X - RUDDER_SPAN - 2.0, RUDDER_CHORD + 1.5)], [1.4] * 4, seg=3)
        pts = [(x, s * (R - z)) for x, z in pts]
        from lib import prism_xz
        c = prism_xz("_slot", pts, -1.6, 1.6, coll)
        for o in extra:
            c2 = c.copy(); c2.data = c.data.copy(); coll.objects.link(c2)
            boolean_safe(o, c2, name="rudder_slot_" + o.name)
        boolean_safe(target, c, name="rudder_slot")


def rudder(name, s, coll):
    """Руль: плоская трапеция в плоскости XZ; корень на поверхности, передняя кромка — ось шарнира (по Y).
    Строится в раскрытом положении (s = 1 — вверх, −1 — вниз)."""
    root_z = R - 1.0
    pts = [(RUDDER_X, root_z), (RUDDER_X, root_z + RUDDER_SPAN - 4.0), (RUDDER_X - 3.0, root_z + RUDDER_SPAN),
           (RUDDER_X - 13.0, root_z + RUDDER_SPAN), (RUDDER_X - RUDDER_CHORD, root_z + 6.0),
           (RUDDER_X - RUDDER_CHORD, root_z)]
    pts = fillet(pts, [1.2, 1.5, 1.5, 2.0, 1.5, 1.2], seg=4)
    o = rounded_prism(name, [(x, z) for x, z in pts], -1.2, 1.2, 1.0, coll, "Fin_steel")
    if s < 0:
        o.data.transform(Matrix.Scale(-1, 4, Vector((0, 0, 1))))
        o.data.flip_normals()
    # ось шарнира — у передней кромки корня, чуть ниже поверхности: сложенный руль уходит в паз целиком
    set_origin(o, (RUDDER_X - 1.2, 0.0, s * (R - 2.2)))
    return o


def tail_fin(name, phi0_deg, coll):
    """Стабилизатор: изогнутая пластина вокруг хвостового блока (сложенное положение — охватывает FIN_SPAN_DEG от
    угла phi0 против часовой со стороны сопла). Шарнир — линия по X на корне; раскрытие — поворот на −90° вокруг X."""
    r0, t = TAIL_R + 0.6, 1.4
    x0, x1 = FIN_CHORD
    n_a, n_x = 24, 10
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    grid = {}
    for side, rr in ((0, r0), (1, r0 + t)):
        for i in range(n_a + 1):
            a = math.radians(phi0_deg + FIN_SPAN_DEG * i / n_a)
            # передняя кромка у вершины пластины скошена: хорда к концу размаха короче (как на снимке)
            frac = i / n_a
            xa = x0 + 8.0 * frac
            xb = x1 - 26.0 * frac ** 1.5
            for j in range(n_x + 1):
                x = xa + (xb - xa) * j / n_x
                grid[(side, i, j)] = bm.verts.new(v(x, rr * math.cos(a), rr * math.sin(a)))
    for side in (0, 1):
        for i in range(n_a):
            for j in range(n_x):
                q = (grid[(side, i, j)], grid[(side, i + 1, j)], grid[(side, i + 1, j + 1)], grid[(side, i, j + 1)])
                bm.faces.new(q if side else tuple(reversed(q)))
    for i in range(n_a):
        for j in (0, n_x):
            bm.faces.new((grid[(0, i, j)], grid[(0, i + 1, j)], grid[(1, i + 1, j)], grid[(1, i, j)]))
    for j in range(n_x):
        for i in (0, n_a):
            bm.faces.new((grid[(0, i, j)], grid[(0, i, j + 1)], grid[(1, i, j + 1)], grid[(1, i, j)]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = _obj(name, me, coll, "Fin_steel")
    finish_small(o, 0.35, 2, 30)
    a0 = math.radians(phi0_deg)
    set_origin(o, (x0, (r0 + t / 2) * math.cos(a0), (r0 + t / 2) * math.sin(a0)))
    # шарнир — проушины на хвостовом блоке
    return o


def hinge_blocks(coll):
    out = []
    for k in range(4):
        # проушина шарнира — перед корнем стабилизатора (корень на 47° + 90°·k), пластину не задевает
        a = math.radians(37.0 + 90.0 * k)
        pts = fillet([(20.0, -3.0), (104.0, -3.0), (104.0, 3.0), (20.0, 3.0)], [2.5] * 4, seg=3)
        from lib import prism_xy
        b = prism_xy(f"Missile_fin_hinge_{k}", pts, TAIL_R - 1.0, TAIL_R + 4.0, coll, "Fin_steel")
        # блок вдоль X на поверхности: повернуть с +Z на угол a
        b.data.transform(Matrix.Rotation(a - math.pi / 2, 4, "X"))
        finish_small(b, 0.5, 2, 35)
        out.append(b)
    return out


def nose(coll):
    """Купол ГСН в обечайке и игла (снимок cap_03: купол в обечайке, игла с колпачком)."""
    dome = lathe("Missile_dome", [(NOSE_X - 12.0, 0.0), (NOSE_X - 12.0, R - 11.6)] +
                 [(NOSE_X - 12.0 + 14.0 * math.sin(t), (R - 11.6) * math.cos(t)) for t in
                  [math.radians(a) for a in range(8, 89, 8)]] + [(NOSE_X + 2.0, 0.0)], coll, "Lens", seg=96)
    needle = lathe("Missile_needle", [(NOSE_X - 1.0, 0.0), (NOSE_X - 1.0, 3.4), (NOSE_X + 4.0, 3.0), (NOSE_X + 8.0, 2.2),
                                      (NOSE_X + D.NEEDLE_LEN - 9.0, 2.0), (NOSE_X + D.NEEDLE_LEN - 7.0, 3.1),
                                      (NOSE_X + D.NEEDLE_LEN - 4.0, 2.4), (NOSE_X + D.NEEDLE_LEN, 0.0)], coll,
                   "Fin_steel", seg=32)
    return [dome, needle]


def build(ctx):
    C = ctx["coll"]["Missile"]
    b = body(C)
    rg = rings(C)
    # паз руля проходит под кольцом 1 — режем и его
    rudder_slots(b, C, extra=[r for r in rg if r.name == "Missile_ring_1"])
    parts = [b] + rg + windows(b, C) + hinge_blocks(C) + nose(C)
    fins = [tail_fin(f"Missile_fin_{k}", 45.0 + 90.0 * k + 2.0, C) for k in range(4)]
    rudders = [rudder("Missile_rudder_top", 1, C), rudder("Missile_rudder_bottom", -1, C)]
    # всё — в локальных осях ракеты; корень ракеты ставит part_rig (X = MISSILE_X0 в трубе)
    return {"parts": parts, "fins": fins, "rudders": rudders}
