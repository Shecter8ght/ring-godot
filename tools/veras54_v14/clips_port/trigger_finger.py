"""ВЕРАС-54 v02: указательный правой на спусковом крючке v14 — позы 1 «ХВАТ» и 11 «спуск выжат».

После переноса на v14 кисть сдвинули, а пальцы к новому крючку не подгоняли: указательный проходил сквозь крючок
(кончик — перед ним, крючок — у последнего сустава), при нажатии крючок «скользил» внутри пальца. Здесь палец
сгибается только как живой (основание — сгиб и отвод ±40°, средняя и концевая фаланги — только сгиб) так, чтобы
подушечка легла на переднюю грань крючка (в позе 11 — нажатого), а ни одна фаланга не входила в крючок.

Как модуль: fit(arms, glove, wr, base, pull) → ({фаланга: matrix_basis}, отчёт). Отдельно (кадры для своей проверки):
blender -b <файл v02.blend> --factory-startup --python tools/veras54_v14/clips_port/trigger_finger.py -- <папка кадров>
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "clips"))

INDEX = ("f_index.01.R", "f_index.02.R", "f_index.03.R")
LIMITS = ((-40, 40), (-40, 40), (-45, 80), (-45, 80))         # основание X, Z; средняя X; концевая X — градусы от исходной (минус — разгиб)
PAD_HALF = 6.0                                                # половина толщины концевой фаланги перчатки, мм
PAD_Z = -58.0                                                 # высота подушечки на крючке (оси рига оружия), мм — нижняя часть крючка


def trigger_bvh(wr, root, pull):
    """Крючок (сетки на кости Trigger) в мире при нажатии pull → BVH и точки, оси рига оружия (мм)."""
    root["Trigger pull"] = pull
    root.update_tag()
    wr.update_tag()
    bpy.context.view_layer.update()
    top = [o for o in bpy.data.objects if o.parent == wr and o.parent_bone == "Trigger"]

    def chain(o):
        while o is not None:
            yield o
            o = o.parent
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in bpy.data.objects:
        if o.type != "MESH" or not any(q in top for q in chain(o)):
            continue
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        base = len(verts)
        verts += [e.matrix_world @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        e.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts


def finger_ids(glove):
    """Вершины перчатки, где главная кость — фаланга указательного: {кость: [индексы]}."""
    gi = {glove.vertex_groups[n].index: n for n in INDEX if n in glove.vertex_groups}
    out = {n: [] for n in INDEX}
    for v in glove.data.vertices:
        if not v.groups:
            continue
        g = max(v.groups, key=lambda x: x.weight)
        if g.group in gi and g.weight > 0.4:
            out[gi[g.group]].append(v.index)
    return out


def fit(arms, glove, wr, root, base, pull):
    """base — {кость: matrix_basis} исходной позы (руки стоят по ней); pull — нажатие крючка в этой позе."""
    bvh, tv = trigger_bvh(wr, root, pull)
    WI = wr.matrix_world.inverted()
    ids = finger_ids(glove)
    pbs = [arms.pose.bones[n] for n in INDEX]
    base_i = [base[n].copy() for n in INDEX]
    tl = [WI @ v for v in tv]

    allid = set(i for n in INDEX for i in ids[n])
    fpolys = [list(p.vertices) for p in glove.data.polygons if all(v in allid for v in p.vertices)]

    def glove_pts():
        dg = bpy.context.evaluated_depsgraph_get()
        e = glove.evaluated_get(dg)
        me = e.to_mesh()
        M = e.matrix_world
        out = {n: [M @ me.vertices[i].co for i in ids[n]] for n in INDEX}
        allv = {i: M @ me.vertices[i].co for i in allid}
        e.to_mesh_clear()
        remap = {i: k for k, i in enumerate(allv)}
        out["_bvh"] = BVHTree.FromPolygons(list(allv.values()), [[remap[v] for v in p] for p in fpolys])
        return out

    def apply(p):
        a1x, a1z, a2, a3 = (math.radians(v) for v in p)
        pbs[0].matrix_basis = base_i[0] @ Matrix.Rotation(a1x, 4, "X") @ Matrix.Rotation(a1z, 4, "Z")
        pbs[1].matrix_basis = base_i[1] @ Matrix.Rotation(a2, 4, "X")
        pbs[2].matrix_basis = base_i[2] @ Matrix.Rotation(a3, 4, "X")
        bpy.context.view_layer.update()

    def measure():
        g = glove_pts()
        pen = 0.0
        for n in INDEX:                                    # палец в крючке
            for p in g[n]:
                loc, nrm, _i, d = bvh.find_nearest(p)
                if loc is not None and (p - loc).dot(nrm) < 0:
                    pen += (d * 1000) ** 2
        fb_ = g["_bvh"]
        for q in tv:                                       # крючок в пальце (крючок тонкий — чаще так)
            loc, nrm, _i, d = fb_.find_nearest(q, 0.02)
            if loc is not None and (q - loc).dot(nrm) < 0:
                pen += (d * 1000) ** 2
        tip = g["f_index.03.R"]
        pad = sum(tip, Vector()) / max(len(tip), 1)
        padl = WI @ pad
        # передняя грань крючка на высоте подушечки (оси рига: +X — к дулу)
        near = [q for q in tl if abs(q.z - padl.z) < 0.003 and abs(q.y) < 0.004]
        face = max(q.x for q in near) if near else padl.x
        dmin = min((bvh.find_nearest(p)[3] for p in tip), default=1.0)
        return pen, dmin * 1000, (padl.x - face) * 1000, padl

    def cost(p):
        apply(p)
        pen, dmin, ahead, padl = measure()
        # подушечка — спереди крючка по его середине (а не вдоль боковой грани): центр концевой фаланги на половину
        # толщины пальца впереди передней грани, поперёк — над серединой крючка
        return (40.0 * pen + 4.0 * dmin ** 2 + 1.5 * (ahead - PAD_HALF) ** 2 + 1.5 * (padl.y * 1000) ** 2
                + 1.0 * (padl.z * 1000 - PAD_Z) ** 2 + 0.01 * sum(v * v for v in p))

    best = [0.0, 0.0, 0.0, 0.0]
    fb = cost(best)
    before = measure()
    for z in (-30, -15, 0, 15, 30):                          # грубо: отвод основания и сгиб
        for x in (-20, 0, 20):
            for s in (-30, -15, 0, 25, 50, 75):
                p = [x, z, s, s * 0.7]
                c = cost(p)
                if c < fb:
                    best, fb = p, c
    step = 6.0
    while step > 0.4:
        moved = False
        for i in range(4):
            for sgn in (1, -1):
                p = list(best)
                p[i] = min(max(p[i] + sgn * step, LIMITS[i][0]), LIMITS[i][1])
                c = cost(p)
                if c < fb - 1e-6:
                    best, fb, moved = p, c, True
        if not moved:
            step /= 2
    apply(best)
    pen, dmin, ahead, padl = measure()
    rep = dict(angles=[round(v, 1) for v in best], before_pen=round(before[0], 1), pen=round(pen, 2), contact_mm=round(dmin, 2),
               pad_ahead_mm=round(ahead, 1), pad_mm=[round(v * 1000, 1) for v in padl])
    return {n: pb.matrix_basis.copy() for n, pb in zip(INDEX, pbs)}, rep


def fit_both(arms, glove, wr, root, T):
    """Сначала «спуск выжат» (11) — подушечка спереди нажатого крючка; потом «ХВАТ» (1) — от неё же, крючок отпущен:
    палец лишь чуть разгибается вслед за крючком, а не переставляется. → {поза: (фаланги, отчёт)}."""
    out = {}
    prepare(arms, wr, glove, T["pressed"])
    out["pressed"] = fit(arms, glove, wr, root, T["pressed"], 1.0)
    base = dict(T["grip"])
    base.update(out["pressed"][0])
    prepare(arms, wr, glove, base)
    out["grip"] = fit(arms, glove, wr, root, base, 0.0)
    root["Trigger pull"] = 0.0
    return out


def prepare(arms, wr, glove, pose_basis):
    """Риг в позу (без анимации), детали оружия в покое, перчатка деформируется."""
    for ob in (arms, wr, bpy.data.objects["VERAS54"], bpy.data.objects["Magazine"]):
        if ob.animation_data:
            ob.animation_data.action = None
    for pb in wr.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for n in ("SpareMag", "JamCase", "Suppressor_Control"):
        wr.pose.bones[n].scale = (0.001,) * 3
    for pb in arms.pose.bones:
        pb.matrix_basis = pose_basis[pb.name].copy()
    for m in glove.modifiers:
        if m.type == "ARMATURE":
            m.show_viewport = True
    bpy.context.view_layer.update()


if __name__ == "__main__":
    import clip_tools_v14 as CT
    args = sys.argv[sys.argv.index("--") + 1:]
    OUTD = Path(args[0])
    OUTD.mkdir(parents=True, exist_ok=True)
    S = bpy.context.scene
    arms, wr = CT.rigs()
    root = bpy.data.objects["VERAS54"]
    glove = bpy.data.objects["FPS_Arms"]
    T = CT.pose_table(bpy.data.actions[CT.POSES], arms)
    S.render.engine = "BLENDER_WORKBENCH"
    S.display.shading.show_cavity = True
    S.render.resolution_x, S.render.resolution_y = 700, 500
    cd = bpy.data.cameras.new("_c")
    cd.type = "ORTHO"
    cd.ortho_scale = 0.10
    cam = bpy.data.objects.new("_c", cd)
    S.collection.objects.link(cam)
    S.camera = cam
    fitted = fit_both(arms, glove, wr, root, T)
    for pose, pull in (("grip", 0.0), ("pressed", 1.0)):
        base = dict(T[pose])
        base.update(fitted[pose][0])
        prepare(arms, wr, glove, base)
        root["Trigger pull"] = pull
        root.update_tag()
        wr.update_tag()
        bpy.context.view_layer.update()
        print("TF", pose, fitted[pose][1], flush=True)
        W = wr.matrix_world
        c = W @ Vector((0.090, 0.0, -0.055))
        for name, d in (("left", Vector((0, 1, 0))), ("right", Vector((0, -1, 0))), ("under", Vector((0.3, -0.4, -1)))):
            eye = c + (W.to_3x3() @ d).normalized() * 0.5
            z = (eye - c).normalized()
            up = (W.to_3x3() @ Vector((0, 0, 1))).normalized()
            if abs(up.dot(z)) > 0.9:
                up = (W.to_3x3() @ Vector((1, 0, 0))).normalized()
            x = up.cross(z).normalized()
            y = z.cross(x)
            cam.matrix_world = Matrix((x, y, z)).transposed().to_4x4()
            cam.matrix_world.translation = eye
            S.render.filepath = str(OUTD / f"trig_{pose}_{name}.png")
            bpy.ops.render.render(write_still=True)
