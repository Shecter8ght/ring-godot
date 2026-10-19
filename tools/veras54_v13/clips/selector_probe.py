"""Промер: кончик указательного пальца правой руки (боевой хват владельца) и полочка лепестка переводчика v13.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup ".../Риг v13/VERAS54_Rig_v13.blend" --python tools/veras54_v13/clips/selector_probe.py
Печатает точки в осях VERAS54 (мм) и расстояния — для клипов переключения режима огня.
"""
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rig_common as rc  # noqa: E402

arms = bpy.data.objects['FPS_ArmsRig']
wr = bpy.data.objects['VERAS54_WeaponRig']
root = bpy.data.objects['VERAS54']
for o in (arms, wr, root):
    if o.animation_data:
        o.animation_data.action = None
pose = rc.ready_pose(arms)
for n, m in pose.items():
    arms.pose.bones[n].matrix_basis = m
bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get()
inv = root.matrix_world.inverted()
mm = lambda v: [round(c * 1000, 1) for c in v]

# кончик указательного: вершины перчатки, где кость f_index.03.R главная, — дальняя от головы кости
glove = bpy.data.objects['FPS_Arms']
eo = glove.evaluated_get(dg)
me = eo.to_mesh()
gi = glove.vertex_groups['f_index.03.R'].index
pts = []
for v in glove.data.vertices:
    w = {g.group: g.weight for g in v.groups}
    if w.get(gi, 0.0) > 0.5 and max(w.values()) == w[gi]:
        pts.append(inv @ (eo.matrix_world @ me.vertices[v.index].co))
pb = arms.pose.bones['f_index.03.R']
head = inv @ (arms.matrix_world @ pb.head)
tip = max(pts, key=lambda p: (p - head).length)
pad = sum(pts, Vector()) / len(pts)
eo.to_mesh_clear()
print('PROBE index tip mm', mm(tip), 'pad', mm(pad), 'verts', len(pts))
# кончик большого пальца — так же, по группе thumb.03.R
eo = glove.evaluated_get(dg)
me = eo.to_mesh()
ti = glove.vertex_groups['thumb.03.R'].index
tpts = []
for v in glove.data.vertices:
    w = {g.group: g.weight for g in v.groups}
    if w.get(ti, 0.0) > 0.5 and max(w.values()) == w[ti]:
        tpts.append(inv @ (eo.matrix_world @ me.vertices[v.index].co))
th = inv @ (arms.matrix_world @ arms.pose.bones['thumb.03.R'].head)
ttip = max(tpts, key=lambda p: (p - th).length)
tpad = sum(tpts, Vector()) / len(tpts)
eo.to_mesh_clear()
print('PROBE thumb tip mm', mm(ttip), 'pad', mm(tpad), 'verts', len(tpts))
for b in ('f_index.01.R', 'f_index.02.R', 'f_index.03.R', 'thumb.01.R', 'thumb.02.R', 'thumb.03.R', 'hand.R', 'forearm.R'):
    p = arms.pose.bones[b]
    print('PROBE bone', b, mm(inv @ (arms.matrix_world @ p.head)), mm(inv @ (arms.matrix_world @ p.tail)))
# полочка лепестка: вершины детали переводчика с x 134…152 мм — середина и низ
sel = bpy.data.objects['Selector_Steel']
eo = sel.evaluated_get(dg)
me = eo.to_mesh()
sp = [inv @ (eo.matrix_world @ v.co) for v in me.vertices]
shelf = [p for p in sp if 0.134 <= p.x <= 0.152]
eo.to_mesh_clear()
c = sum(shelf, Vector()) / len(shelf)
print('PROBE shelf centre mm', mm(c), 'z', round(min(p.z for p in shelf) * 1000, 1), round(max(p.z for p in shelf) * 1000, 1),
      'y', round(min(p.y for p in shelf) * 1000, 1), round(max(p.y for p in shelf) * 1000, 1))
print('PROBE tip→shelf mm', round((c - tip).length * 1000, 1), 'pad→shelf', round((c - pad).length * 1000, 1))
print('PROBE thumb tip→shelf mm', round((c - ttip).length * 1000, 1), 'thumb pad→shelf', round((c - tpad).length * 1000, 1))
trig = bpy.data.objects['Trigger_Steel']
eo = trig.evaluated_get(dg)
me = eo.to_mesh()
tp = [inv @ (eo.matrix_world @ v.co) for v in me.vertices]
eo.to_mesh_clear()
print('PROBE trigger centre mm', mm(sum(tp, Vector()) / len(tp)))
