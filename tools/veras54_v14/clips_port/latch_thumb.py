"""ВЕРАС-54 v02: поза 91 «на магазине, большой на защёлке» — большой палец левой подушечкой на лапку защёлки магазина.

Перенос ставил палец временным IK без пределов суставов — фаланги выворачивались («палец ломается»). Здесь палец
сгибается только так, как сгибается живой: основание (thumb.01) — в двух плоскостях в пределах ±45° от позы 41,
средняя и концевая фаланги — только сгиб по своей оси, от −10° до 75°. Подбор — поиском по образцу (без IK).

Как модуль: place(arms, wr, glove, T41) → (позы трёх фаланг, промах мм); отдельно (для своей проверки):
blender -b <файл v02.blend> --factory-startup --python tools/veras54_v14/clips_port/latch_thumb.py -- <папка кадров>
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "clips"))

THUMB = ("thumb.01.L", "thumb.02.L", "thumb.03.L")
LIMITS = ((-45, 45), (-45, 45), (-10, 75), (-10, 75))        # основание X, Z; средняя X; концевая X — градусы от позы 41


def press_point(wr):
    """Лапка защёлки v14: задняя грань низа рычага (большой давит вперёд), оси рига оружия → мир."""
    import numpy as np
    o = bpy.data.objects["Mag_Catch__Body"]
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    me = e.to_mesh()
    M = wr.matrix_world.inverted() @ e.matrix_world
    a = np.array([(M @ v.co)[:] for v in me.vertices])
    e.to_mesh_clear()
    low = a[a[:, 2] < a[:, 2].min() + 0.016]
    p = Vector((low[:, 0].min() + 0.0015, 0.0, low[:, 2].mean()))
    return wr.matrix_world @ p


def place(arms, glove, base, target_w):
    """base — {кость: matrix_basis} позы 41 (руки стоят по ней); → ({фаланга: matrix_basis}, промах мм)."""
    from vcommon import pad_world
    pbs = [arms.pose.bones[n] for n in THUMB]
    base_t = [base[n].copy() for n in THUMB]

    def apply(p):
        a1x, a1z, a2, a3 = (math.radians(v) for v in p)
        pbs[0].matrix_basis = base_t[0] @ Matrix.Rotation(a1x, 4, "X") @ Matrix.Rotation(a1z, 4, "Z")
        pbs[1].matrix_basis = base_t[1] @ Matrix.Rotation(a2, 4, "X")
        pbs[2].matrix_basis = base_t[2] @ Matrix.Rotation(a3, 4, "X")
        bpy.context.view_layer.update()

    def cost(p):
        apply(p)
        d = (pad_world(arms, glove, "thumb.03.L") - target_w).length * 1000
        return d + 0.004 * sum(v * v for v in p)              # при равном промахе — ближе к позе 41

    best = [0.0, 0.0, 0.0, 0.0]
    fb = cost(best)
    for a in (-30, 0, 30):                                    # грубо: основание
        for z in (-30, 0, 30):
            for s in (0, 30, 60):
                p = [a, z, s, s * 0.6]
                c = cost(p)
                if c < fb:
                    best, fb = p, c
    step = 8.0
    while step > 0.25:
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
    miss = (pad_world(arms, glove, "thumb.03.L") - target_w).length * 1000
    return {n: pb.matrix_basis.copy() for n, pb in zip(THUMB, pbs)}, round(miss, 1), [round(v, 1) for v in best]


if __name__ == "__main__":
    import clip_tools_v14 as CT
    args = sys.argv[sys.argv.index("--") + 1:]
    OUTD = Path(args[0])
    OUTD.mkdir(parents=True, exist_ok=True)
    S = bpy.context.scene
    arms, wr = CT.rigs()
    glove = bpy.data.objects["FPS_Arms"]
    for m in glove.modifiers:
        if m.type == "ARMATURE":
            m.show_viewport = True
    T = CT.pose_table(bpy.data.actions[CT.POSES], arms)
    for ob in (arms, wr, bpy.data.objects["VERAS54"], bpy.data.objects["Magazine"]):
        if ob.animation_data:
            ob.animation_data.action = None
    for pb in wr.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    for n in ("SpareMag", "JamCase", "Suppressor_Control"):
        wr.pose.bones[n].scale = (0.001,) * 3
    for pb in arms.pose.bones:
        pb.matrix_basis = T["mag"][pb.name].copy()
    bpy.data.objects["VERAS54"]["Magazine latch press"] = 1.0
    bpy.context.view_layer.update()
    tgt = press_point(wr)
    poses, miss, p = place(arms, glove, T["mag"], tgt)
    print("THUMB промах мм", miss, "углы", p, flush=True)
    S.render.engine = "BLENDER_WORKBENCH"
    S.render.resolution_x, S.render.resolution_y = 900, 700
    cam_d = bpy.data.cameras.new("_c")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = 0.30
    cam = bpy.data.objects.new("_c", cam_d)
    S.collection.objects.link(cam)
    W = wr.matrix_world
    c = W @ Vector((0.15, 0.0, -0.09))
    for name, d in (("right", Vector((0, -1, 0))), ("below", Vector((0, -0.6, -1))), ("rear", Vector((-1, -0.5, -0.4)))):
        eye = c + (W.to_3x3() @ d).normalized() * 0.6
        z = (eye - c).normalized()
        up = (W.to_3x3() @ Vector((0, 0, 1))).normalized()
        if abs(up.dot(z)) > 0.95:
            up = (W.to_3x3() @ Vector((1, 0, 0))).normalized()
        x = up.cross(z).normalized()
        y = z.cross(x)
        cam.matrix_world = Matrix((x, y, z)).transposed().to_4x4()
        cam.matrix_world.translation = eye
        S.camera = cam
        S.render.filepath = str(OUTD / f"thumb91_{name}.png")
        bpy.ops.render.render(write_still=True)
    fps = bpy.data.objects.get("FPS • Camera")
    if fps:
        S.camera = fps
        S.render.filepath = str(OUTD / "thumb91_eye.png")
        bpy.ops.render.render(write_still=True)
