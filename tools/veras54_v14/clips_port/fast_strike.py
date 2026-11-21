"""ВЕРАС-54 v02, быстрые перезарядки: удар новым магазином по защёлке — по фазам, принятым владельцем 21.11.

  1. подвёл — новый магазин позади и ниже старого, верхом под спусковой скобой;
  2. прицелился — пауза: передняя кромка нового в 12 мм позади кончика лапки защёлки (видно, куда ударит);
  3. удар — резкий тычок вперёд за 2 кадра: кромка бьёт в лапку, защёлка уходит вперёд, этот же толчок выбивает старый;
  4. старый вываливается — качается вперёд вокруг зацепа ровно настолько, насколько его выталкивает новый (по
     пересечению сеток), и улетает вперёд-вниз; кисть замирает на FREEZE кадров — видно, как старый уходит;
  5. вставка нового — зацеп, «прислонение», доворот до щелчка (как в неполной).
«Застрял»: после первого удара старый чуть качнулся и встал; новый отходит, пауза — заметил; второй удар сильнее.

Лапка защёлки v14 выступает ниже спусковой скобы всего на ~4 мм: новый магазин идёт верхом под скобой и бьёт
передней верхней кромкой в самый кончик лапки. Высота — по геометрии (скоба, лапка) — считается здесь же.

Вызывается из mag_path_fix.py: rebuild(act, stuck, env) — env: его глобальные имена (риги, conv, solve_hand …).
Кадры клипа после выпадения старого сдвигаются на FREEZE (один раз: метка strike_v2 у действия).
"""
import json
import math

import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

FREEZE = 3                                            # кадров кисть замирает, пока старый уходит
FLAG = "strike_v2"
AIM_GAP = 0.012                                       # прицел: кромка нового позади лапки, м
PRESS = 0.007                                         # ход лапки до отпускания старого, м
YAW, TILT = -50.0, -5.0                               # новый магазин: поворот вокруг вертикали (корпус — влево-назад, к левой
                                                      # кисти) и наклон; подобрано перебором: ни скобы, ни старого магазина
YC = 0.004                                            # угол нового — на 4 мм левее середины лапки
CONTACT_UP = 0.002                                    # выше низа кончика лапки, м (лапка ниже скобы всего ~4 мм)
AIM_LOW = -0.005                                      # в прицеле угол на 5 мм ниже удара: подходит снизу-сзади, мимо рукоятки


def all_curves(act):
    out = []
    for layer in act.layers:
        for st in layer.strips:
            for bag in st.channelbags:
                out.extend(bag.fcurves)
    return out


def insert_frames(act, at, H):
    """Остановка: всё после кадра at — на H кадров позже, на at и at+H — то, что было на at (все кривые всех объектов)."""
    for fc in all_curves(act):
        kps = fc.keyframe_points
        if not len(kps):
            continue
        v = fc.evaluate(at)
        prev = [k for k in kps if k.co[0] <= at + 1e-3]
        interp = prev[-1].interpolation if prev else kps[0].interpolation
        for kp in sorted(kps, key=lambda k: -k.co[0]):
            if kp.co[0] > at + 1e-3:
                kp.co[0] += H
                kp.handle_left[0] += H
                kp.handle_right[0] += H
        if not any(abs(k.co[0] - at) < 1e-3 for k in kps):
            kps.insert(at, v).interpolation = interp
        kps.insert(at + H, v).interpolation = interp
        fc.update()
    marks = json.loads(act.get("marks", "{}"))
    act["marks"] = json.dumps({k: (v + H if v > at else v) for k, v in marks.items()}, ensure_ascii=False)


# ---------------------------------------------------------------- геометрия v14 (оси рига оружия, м)
def rest_mesh(name, wr):
    o = bpy.data.objects[name]
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    M = wr.matrix_world.inverted() @ e.matrix_world
    v = [M @ x.co for x in me.vertices]
    f = [list(p.vertices) for p in me.polygons]
    e.to_mesh_clear()
    return v, f


def geometry(env):
    arms, wr = env["arms"], env["wr"]
    env["assign"](None)
    for pb in wr.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
        for c in pb.constraints:
            c.influence = 0.0                         # магазин — в шахте, не в кисти
    env["update"]()
    mv, mf = rest_mesh("Magazine__Mag", wr)
    rv, rf = rest_mesh("Receiver__Body", wr)
    cv, _cf = rest_mesh("Mag_Catch__Body", wr)
    M = np.array([v[:] for v in mv])
    top = M[(M[:, 2] > M[:, 2].max() - 0.003) & (np.abs(M[:, 1]) < 0.010)]
    A = Vector((top[:, 0].max(), 0.0, M[:, 2].max()))            # передняя верхняя кромка магазина
    top_len = top[:, 0].max() - top[:, 0].min()
    C = np.array([v[:] for v in cv])
    tip = C[C[:, 2] < C[:, 2].min() + 0.006]
    paddle_x, paddle_zb = tip[:, 0].min(), C[:, 2].min()          # задняя грань кончика лапки, низ лапки
    R = np.array([v[:] for v in rv])
    lo = paddle_x - AIM_GAP - top_len + 0.002                     # над верхом нового магазина в прицеле — скоба, не рукоятка
    span = R[(R[:, 0] > lo) & (R[:, 0] < paddle_x - 0.004) & (np.abs(R[:, 1]) < 0.025)]
    guard_z = span[:, 2].min() if len(span) else paddle_zb       # низ скобы над верхом нового магазина
    top25 = [Vector(v) for v in M[M[:, 2] > M[:, 2].max() - 0.025]]
    return dict(mv=mv, mf=mf, A=A, top25=top25, paddle_x=float(paddle_x), paddle_zb=float(paddle_zb), guard_z=float(guard_z),
                bvh_r=BVHTree.FromPolygons(rv, rf))


def about_y(P, deg):
    return Matrix.Translation(P) @ Matrix.Rotation(math.radians(deg), 4, "Y") @ Matrix.Translation(-P)


# ---------------------------------------------------------------- путь матрицами: ключи → сплайн
def to_params(E, P, prev=None):
    d = E @ P - P
    eul = E.to_3x3().to_euler("XYZ", prev) if prev is not None else E.to_3x3().to_euler("XYZ")
    return (d.x, d.y, d.z, eul.x, eul.y, eul.z), eul


def from_params(p, P):
    from mathutils import Euler
    R = Euler(p[3:], "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(Vector(p[:3])) @ Matrix.Translation(P) @ R @ Matrix.Translation(-P)


def spline(keys, P, pchip):
    """keys — [(кадр, E)] → функция кадр → E (монотонный сплайн по сдвигу зацепа и углам)."""
    rows, prev = [], None
    for f, E in keys:
        par, prev = to_params(E, P, prev)
        rows.append((f, *par))
    return lambda f: from_params(pchip(rows, f), P)


# ---------------------------------------------------------------- клип
def rebuild(act, stuck, env):
    S, CT, arms, wr, root = env["S"], env["CT"], env["arms"], env["wr"], env["root"]
    conv, pchip, P = env["conv"], env["pchip"], env["PIVOT"]
    geo = env.setdefault("_strike_geo", None) or geometry(env)
    env["_strike_geo"] = geo
    rep = {}
    free0 = 39 if stuck else 31                       # кадр выпадения старого в клипе до остановки (как у переноса)
    if not act.get(FLAG):
        insert_frames(act, free0, FREEZE)
        act[FLAG] = True
        rep["inserted"] = [free0, FREEZE]
    env["assign"](act)
    end = int(math.ceil(CT.last_key(act, arms)))

    # ---- прицел: новый повёрнут (YAW, TILT) — передним верхним углом в кончик лапки, корпусом рядом со старым
    rep["guard_z_mm"], rep["paddle_bottom_mm"] = round(geo["guard_z"] * 1000, 1), round(geo["paddle_zb"] * 1000, 1)
    bvh_r = geo["bvh_r"]
    R0 = Matrix.Rotation(math.radians(YAW), 4, "Z") @ Matrix.Rotation(math.radians(TILT), 4, "Y")
    lead = max((R0 @ v for v in geo["top25"]), key=lambda q: q.x)   # угол, которым бьём
    zc = geo["paddle_zb"] + CONTACT_UP

    def Ed(x, dz=0.0):                                # угол — на x м впереди точки прицела (AIM_GAP позади лапки), dz — ниже
        return Matrix.Translation(Vector((geo["paddle_x"] - AIM_GAP + x - lead.x, YC - lead.y, zc - lead.z + dz))) @ R0

    def hits(E, other):
        b = BVHTree.FromPolygons([E @ v for v in geo["mv"]], geo["mf"])
        return len(b.overlap(other))

    bv_old = BVHTree.FromPolygons(geo["mv"], geo["mf"])
    rep["check_overlaps"] = {k: [hits(Ed(x), bvh_r), hits(Ed(x), bv_old)] for k, x in
                             (("aim", 0.0), ("contact", AIM_GAP), ("pressed", AIM_GAP + PRESS))}
    rep["check_overlaps"]["aim_low"] = [hits(Ed(0.0, AIM_LOW), bvh_r), hits(Ed(0.0, AIM_LOW), bv_old)]
    rep["check_overlaps"]["wind"] = [hits(Ed(-0.003, AIM_LOW - 0.001), bvh_r), hits(Ed(-0.003, AIM_LOW - 0.001), bv_old)]

    G = lambda *k: conv(k)  # noqa: E731
    pouch = [(13, G(-10, 35, 0.17, 0.19, -0.4)), (15, G(-12, 32, 0.16, 0.18, -0.36)),
             (21, Matrix.Translation(Vector((-0.025, 0.020, -0.045))) @ Ed(0.0))]
    c1 = AIM_GAP                                      # касание
    s1 = AIM_GAP + PRESS + 0.002                      # конец удара (лапка дожата)
    if not stuck:
        keys = pouch + [(24, Ed(0.0, AIM_LOW)), (26, Ed(0.0, AIM_LOW)), (27, Ed(-0.003, AIM_LOW - 0.001)), (28, Ed(c1)), (29, Ed(s1)), (31, Ed(s1 + 0.004)),
                        (34, Ed(s1 - 0.001)), (35, Ed(s1 - 0.006, -0.022))]      # 35: сперва вниз, от скобы — потом доворот
        free, freeze_end = 31, 34
        # дальше — зацеп ниже шахты (37 — 6 см ниже, 38 — 1,4 см), прислонение 40, доворот до щелчка 46
        keys += [(37, G(-29, 0, 0, -0.004, -0.06)), (38, G(-27, 0, 0, -0.006, -0.014)), (40, G(-22, 0, 0, 0, 0)),
                 (43, G(-22, 0, 0, 0, 0)), (46, G(0.8, 0, 0, 0, 0)), (47, G(0, 0, 0, 0, 0)), (49, G(0, 0, 0, 0, 0))]
        marks = dict(aim=24, strike=28, old_falls=free, mag_toss=free, freeze_end=freeze_end)
    else:
        s2 = s1 + 0.002                               # второй удар — резче (за кадр), чуть глубже
        keys = pouch + [(24, Ed(0.0, AIM_LOW)), (26, Ed(0.0, AIM_LOW)), (27, Ed(-0.003, AIM_LOW - 0.001)), (28, Ed(c1)), (29, Ed(s1)),
                        (30, Ed(s1 + 0.001)), (31, Ed(s1 - 0.006)), (33, Ed(0.004, AIM_LOW)), (36, Ed(0.004, AIM_LOW)), (37, Ed(c1)),
                        (38, Ed(s2)), (39, Ed(s2 + 0.002)),
                        (42, Ed(s2 - 0.002)), (43, Ed(s2 - 0.007, -0.022))]
        free, freeze_end = 39, 42
        keys += [(45, G(-29, 0, 0, -0.004, -0.06)), (47, G(-27, 0, 0, -0.006, -0.014)), (49, G(-22, 0, 0, 0, 0)),
                 (52, G(-22, 0, 0, 0, 0)), (55, G(0.8, 0, 0, 0, 0)), (56, G(0, 0, 0, 0, 0)), (58, G(0, 0, 0, 0, 0))]
        marks = dict(aim=24, strike=28, stuck=30, notice=33, strike_2=37, old_falls=free, mag_toss=free, freeze_end=freeze_end)
    path = spline(keys, P, pchip)
    end_hold = keys[-1][0]

    # ---- новый магазин: ключ кисти на каждом кадре от «подвёл» до посадки (у подсумка — реже)
    cv = CT.bone_curves(CT.bag_of(act, arms))
    ik = arms.pose.bones["ik_hand.L"]
    env["drop_keys"](cv["ik_hand.L"].values(), 13.5, end_hold - 0.5)
    frames = [13, 15, 18] + list(range(21, end_hold + 1))
    plan = [(f, env["solve_hand"](f, path(f))) for f in frames]
    for f, basis in plan:
        CT.write(cv["ik_hand.L"], ik, f, basis, CT.bag_of(act, arms), insert=True)

    # ---- старый: в шахте до касания; качается ровно настолько, насколько его выталкивает новый (без пересечения)
    mv, mf = geo["mv"], geo["mf"]

    def min_angle(f, start=0.0):
        bn = BVHTree.FromPolygons([path(f) @ v for v in mv], mf)
        a = start
        while a > -35.0:
            bo = BVHTree.FromPolygons([about_y(P, a) @ v for v in mv], mf)
            if not bn.overlap(bo):
                return a
            a -= 0.5
        return a

    # старый: защёлка дожата (28,4) — сам качается вперёд вокруг зацепа и падает; новый рядом сбоку — угол не меньше,
    # чем нужно, чтобы не задеть новый
    def sched(fr_ang):
        out, a = [], 0.0
        for f, want in fr_ang:
            a = min(a, want, min_angle(f, min(a, want)))
            out.append((f, a))
        return out
    old = [(1, 0.0), (28.6, 0.0)]
    if not stuck:
        old += sched([(29.0, -3.0), (29.5, -8.0), (30.0, -14.0), (31.0, -24.0)])
    else:
        old += sched([(29.0, -2.0), (30.0, -4.0)])     # застрял: чуть качнулся и встал
        old += [(36.0, old[-1][1])]
        old += sched([(37.4, old[-1][1]), (37.8, -8.0), (38.3, -14.0), (39.0, -24.0)])
    rep["old_deg"] = [(f, round(a, 1)) for f, a in old]
    # весь путь нового (полкадра): пересечения с коробкой и со старым (старый — по своим ключам, пока не выпал)
    bad = []
    fx = [f for f, _a in old]
    for k in range(21 * 2, int(end_hold) * 2 + 1):
        f = k / 2.0
        bn = BVHTree.FromPolygons([path(f) @ v for v in mv], mf)
        nr = len(bn.overlap(bvh_r))
        no = 0
        if f <= free:
            ang = float(np.interp(f, fx, [a for _f, a in old]))
            no = len(bn.overlap(BVHTree.FromPolygons([about_y(P, ang) @ v for v in mv], mf)))
        if nr or no:
            bad.append((f, nr, no))
    rep["path_overlaps"] = bad
    seen = {}
    for f, ang in old:
        seen[f] = ang
    old = sorted(seen.items())
    bag, fcs = env["spare_curves"](act)
    env["drop_keys"](fcs, 2, end)
    env["write_spare"](act, [(f, about_y(P, ang) @ env["REST_SPARE"]) for f, ang in old])
    # вылет вперёд-вниз (как у переноса) — от места на кадре выпадения
    S.frame_set(free)
    env["update"]()
    M0 = wr.matrix_world @ wr.pose.bones["SpareMag"].matrix
    ax_spin = (wr.matrix_world.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
    ax_roll = (wr.matrix_world.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    Grot = wr.matrix_world.to_3x3()
    toss = []
    for f in range(free + 1, min(free + 18, end) + 1, 2):
        t = (f - free) / env["FPS"]
        off = Grot @ Vector((1.3, 0.0, -0.45)) * t + Vector((0, 0, -4.9 * t * t))
        Rm = (Matrix.Rotation(-7.0 * t, 3, ax_spin) @ Matrix.Rotation(1.5 * t, 3, ax_roll)).to_4x4()
        M = Matrix.Translation(M0.translation + off) @ Rm @ M0.to_3x3().to_4x4()
        S.frame_set(f)
        env["update"]()
        toss.append((f, wr.matrix_world.inverted() @ M))
    env["write_spare"](act, toss)
    for fc in fcs:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR" if kp.co[0] > free else "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
        fc.update()

    # ---- защёлка: нажата от касания до выпадения старого (у «застрял» — два нажатия), щелчок при посадке — прежний
    lc = next((fc for fc in CT.bag_of(act, root).fcurves if fc.data_path == '["Magazine latch press"]'), None)
    if lc is not None:
        env["drop_keys"]([lc], 26.5, free + 3)
        presses = [(27.6, 0.0), (28.4, 1.0)]
        if stuck:
            presses += [(30.5, 1.0), (31.5, 0.0), (36.6, 0.0), (37.4, 1.0), (free, 1.0), (free + 1.5, 0.0)]
        else:
            presses += [(free, 1.0), (free + 1.5, 0.0)]
        for f, v in presses:
            lc.keyframe_points.insert(f, v).interpolation = "BEZIER"
        lc.update()

    # ---- плечо, фазы
    ua_cv = CT.bone_curves(CT.bag_of(act, arms)).get("upper_arm.L", {})
    T = env["T"]
    ua_frames = sorted({round(k.co[0], 3) for fc in ua_cv.values() for k in fc.keyframe_points if 13 < k.co[0] < end_hold})
    gone = [f for f in ua_frames
            if not any(CT.close(CT.read(ua_cv, arms.pose.bones["upper_arm.L"], f), T[p]["upper_arm.L"], 2e-4) for p in T)]
    for f in gone:
        env["drop_keys"](ua_cv.values(), f, f)
    rep["reach_mm"] = env["reach_left"](act, list(range(10, min(end, end_hold + 3) + 1)))
    m = json.loads(act.get("marks", "{}"))
    m.update(marks)
    act["marks"] = json.dumps(m, ensure_ascii=False)
    rep["end"] = end
    rep["marks"] = marks
    return rep
