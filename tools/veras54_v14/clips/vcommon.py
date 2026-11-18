"""ВЕРАС-54, клипы рук: общее для poses.py и build_clips.py (в файл владельца не кладётся — панель самостоятельна).

Положение автомата — как в клипах v13 (tools/veras54_v13/clips/build_clips.py): (крен°, тангаж°, рыскание°, x, y, z) —
повороты Euler XYZ вокруг мировых осей в точке пистолетной рукоятки, сдвиг — в мире (м). Автомат смотрит по −Y мира:
тангаж плюс — дуло вниз, рыскание плюс — дуло влево (к середине кадра), x плюс — влево, y плюс — к глазам, z — вверх.
"""
import math

import bpy
from mathutils import Euler, Matrix, Vector


def about(p, rot3):
    return Matrix.Translation(p) @ rot3.to_4x4() @ Matrix.Translation(-p)


def gun_delta(pose, grip_w):
    """Сдвиг автомата в мире от хвата: pose = (крен, тангаж, рыскание, x, y, z)."""
    r, p, yw, x, y, z = pose
    rot = Euler((math.radians(p), math.radians(r), math.radians(yw)), "XYZ").to_matrix()
    return Matrix.Translation(Vector((x, y, z))) @ about(grip_w, rot)


class Gun:
    """Пересчёт положения автомата в matrix_basis кости Weapon_CTRL (руки — рига FPS_ArmsRig)."""

    def __init__(self, arms, grip_basis, grip_local, wr):
        self.arms = arms
        self.AW = arms.matrix_world.copy()
        self.AWI = self.AW.inverted()
        wc = arms.pose.bones["Weapon_CTRL"]
        wc.matrix_basis = grip_basis
        bpy.context.view_layer.update()
        self.WC_REST = wc.matrix.copy()
        self.WC_PARENT = self.WC_REST @ grip_basis.inverted()
        self.GRIP_W = wr.matrix_world @ Vector(grip_local)
        self.WR_REST = wr.matrix_world.copy()           # риг оружия в мире при хвате

    def basis(self, pose, base=None):
        """pose — (крен, тангаж, рыскание, x, y, z) от хвата; base — сдвиг в мире (матрица), к которому он добавляется."""
        D = gun_delta(pose, self.GRIP_W)
        if base is not None:
            D = D @ base
        return self.WC_PARENT.inverted() @ self.AWI @ D @ self.AW @ self.WC_REST

    def shift_of(self, basis):
        """matrix_basis Weapon_CTRL → сдвиг автомата в мире относительно хвата."""
        return self.AW @ self.WC_PARENT @ basis @ self.WC_REST.inverted() @ self.AWI


def lerp_m(a, b, t):
    la, ra, _ = a.decompose()
    lb, rb, _ = b.decompose()
    return Matrix.Translation(la.lerp(lb, t)) @ ra.slerp(rb, t).to_matrix().to_4x4()


def pad_world(arms, glove, bone):
    """Середина подушечки пальца: вершины перчатки, где главная кость — bone (концевая фаланга)."""
    dg = bpy.context.evaluated_depsgraph_get()
    eo = glove.evaluated_get(dg)
    me = eo.to_mesh()
    gi = glove.vertex_groups[bone].index
    pts = []
    for v in glove.data.vertices:
        w = {g.group: g.weight for g in v.groups}
        if w.get(gi, 0.0) > 0.5 and max(w.values()) == w[gi]:
            pts.append(eo.matrix_world @ me.vertices[v.index].co)
    eo.to_mesh_clear()
    return sum(pts, Vector()) / max(len(pts), 1)


def finger_to(arms, glove, side, finger, point_w, chain=3, iters=5):
    """Палец (три фаланги) подушечкой в точку мира — временным IK; поза фаланг пишется в matrix_basis.
    → промах, мм."""
    tip = f"{finger}.03.{side}"
    tgt = bpy.data.objects.new("_tmp_target", None)
    bpy.context.scene.collection.objects.link(tgt)
    ik = arms.pose.bones[tip].constraints.new("IK")
    ik.target = tgt
    ik.chain_count = chain
    ik.use_tail = True
    ik.use_rotation = False
    tgt.location = point_w
    miss = 0.0
    for _ in range(iters):
        bpy.context.view_layer.update()
        d = point_w - pad_world(arms, glove, tip)
        miss = d.length
        tgt.location = tgt.location + d
    bpy.context.view_layer.update()
    miss = (point_w - pad_world(arms, glove, tip)).length
    names = [f"{finger}.{j:02d}.{side}" for j in range(1, 4)][-chain:]
    vis = {n: arms.convert_space(pose_bone=arms.pose.bones[n], matrix=arms.pose.bones[n].matrix,
                                 from_space="POSE", to_space="LOCAL").copy() for n in names}
    arms.pose.bones[tip].constraints.remove(ik)
    bpy.data.objects.remove(tgt, do_unlink=True)
    for n, m in vis.items():
        arms.pose.bones[n].matrix_basis = m
    bpy.context.view_layer.update()
    return miss * 1000
