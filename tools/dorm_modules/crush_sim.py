"""Мятые банки симуляцией: дно стоит, а жёсткая крышка с плечом опускается и наклоняется (пустышка на крючке),
тонкая стенка между ними складывается сама — с вмятины-затравки, крупными гранями. Ткань с жёсткостью тонкого листа,
самостолкновения включены (стенка не проходит сквозь себя). Пачку сигарет так смять не вышло — плита собирает её верх
в мелкий «гравий» при любом трении и жёсткости (пробы 2026-10-30), её заломы заданы в build_clutter.soft_pack.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Clutter_v0N.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/crush_sim.py -- [CL_банка_мятая CL_банка_раздавлена]

Банка — плотная сетка той же формы (профиль build_clutter.CAN_PROF, кольца через 2 мм): мятая — верх ниже на 25 мм
с наклоном 16°, раздавленная — на 118 мм с наклоном 24°. Результат кадра 60 заменяет сетку объекта; файл сохраняется на место.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_clutter as C  # noqa: E402
import build_found_lights as F  # noqa: E402
import mlib as L  # noqa: E402

FRAMES = 60
# алюминиевая стенка: пробы 2026-10-30 — при 60 мнётся мелкой «фольгой», при 900 рябит; 300 и изгиб 30 дают крупные грани
CAN_CLOTH = {"tension_stiffness": 300.0, "compression_stiffness": 300.0, "bending_stiffness": 30.0}


def dense_can(seed: int, step: float = 0.002, segs: int = 64, jitter: float = 0.0002, dent: tuple = None) -> bpy.types.Object:
    """Банка для симуляции: кольца через step, segs по кругу, jitter — случайный сдвиг вершин;
    dent — (высота, угол, глубина, полуширина по высоте) вмятины-затравки: с неё стенка начинает складываться."""
    prof = []
    for (r0, z0), (r1, z1) in zip(C.CAN_PROF, C.CAN_PROF[1:]):
        n = max(1, int(math.hypot(r1 - r0, z1 - z0) / step))
        for i in range(n):
            t = i / n
            prof.append((r0 + (r1 - r0) * t, z0 + (z1 - z0) * t))
    prof.append(C.CAN_PROF[-1])
    bm = bmesh.new()
    F.lathe(bm, prof, segs)
    rnd = random.Random(seed)
    for v in bm.verts:  # небольшая неправильность — складки не идут ровными кольцами; над полом 3 мм (не в коллайдере)
        v.co.x += rnd.uniform(-jitter, jitter)
        v.co.y += rnd.uniform(-jitter, jitter)
        if dent:
            h, a, depth, half = dent
            r = math.hypot(v.co.x, v.co.y)
            if r > 0.03:
                k = max(0.0, 1.0 - abs(v.co.z - h) / half) * max(0.0, math.cos(math.atan2(v.co.y, v.co.x) - a)) ** 2
                v.co.x -= v.co.x / r * depth * k
                v.co.y -= v.co.y / r * depth * k
        v.co.z += 0.003
    me = bpy.data.meshes.new("sim")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("sim", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def collider(name, size, at, rot=(0, 0, 0)) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = at
    ob.rotation_euler = rot
    ob.modifiers.new("Collision", "COLLISION")
    ob.collision.thickness_outer = 0.0008
    ob.collision.cloth_friction = 8.0
    return ob


def simulate(ob, drop: float, tilt: float, stiff: float, mass: float, rigid: tuple, cloth: dict = None) -> bpy.types.Mesh:
    """Дно стоит, верх (крышка с плечом) опускается на drop и наклоняется на tilt как жёсткое целое: толстые донце
    и крышка не мнутся, складывается только тонкая стенка между ними.
    rigid — (высота жёсткого низа от дна, высота жёсткого верха от макушки);
    cloth — поправки настроек ткани поверх общих (имя свойства ClothSettings → значение)."""
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    zs = [v.co.z for v in ob.data.vertices]
    low, high = min(zs), max(zs)
    pin = ob.vertex_groups.new(name="жёстко")
    pin.add([v.index for v in ob.data.vertices if v.co.z < low + rigid[0]], 1.0, "REPLACE")
    top = ob.vertex_groups.new(name="верх")
    idx = [v.index for v in ob.data.vertices if v.co.z > high - rigid[1]]
    top.add(idx, 1.0, "REPLACE")
    pin.add(idx, 1.0, "REPLACE")
    ground = collider("пол_сим", 0.5, (0, 0, 0))
    # верх ведёт пустышка: поворот вокруг центра крышки + опускание (закреплённые вершины идут за ней)
    end = FRAMES - 12
    c = Vector((0.0, 0.0, high))
    rot = Matrix.Rotation(tilt, 4, Vector((math.cos(0.7), math.sin(0.7), 0.0)))
    m = Matrix.Translation(c + Vector((0.004, 0.0, -drop))) @ rot @ Matrix.Translation(-c)
    e = bpy.data.objects.new("верх_сим", None)
    sc.collection.objects.link(e)
    e.keyframe_insert("location", frame=1)
    e.keyframe_insert("rotation_euler", frame=1)
    e.matrix_world = m
    e.keyframe_insert("location", frame=end)
    e.keyframe_insert("rotation_euler", frame=end)
    hook = ob.modifiers.new("верх", "HOOK")
    hook.object = e
    hook.vertex_group = top.name
    hook.matrix_inverse = Matrix.Identity(4)  # при назначении object Blender берёт обратную текущего положения пустышки
    extra = [ground, e]
    cl = ob.modifiers.new("Cloth", "CLOTH")
    s = cl.settings
    s.vertex_group_mass = pin.name
    s.quality = 12
    s.mass = mass
    s.tension_stiffness = stiff
    s.compression_stiffness = stiff
    s.shear_stiffness = stiff * 0.5
    s.bending_stiffness = stiff  # лист алюминия / картон ломается крупными гранями, а не мелкой «фольгой»
    s.tension_damping = 5.0
    s.compression_damping = 5.0
    s.bending_damping = 0.5
    s.air_damping = 1.0
    s.use_pressure = True  # воздух внутри выдавливает складки наружу
    s.uniform_pressure_force = 0.2
    for k, v in (cloth or {}).items():
        setattr(s, k, v)
    cc = cl.collision_settings
    cc.use_collision = True
    cc.distance_min = 0.0008
    cc.use_self_collision = True
    cc.self_distance_min = 0.0006
    cc.collision_quality = 4
    cl.point_cache.frame_start = 1
    cl.point_cache.frame_end = FRAMES
    for f in range(1, FRAMES + 1):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    low = min(v.co.z for v in me.vertices)
    me.transform(Matrix.Translation((0, 0, -low)))  # низом на пол
    for o in extra + [ob]:
        bpy.data.objects.remove(o)
    return me


def replace(target_name: str, me: bpy.types.Mesh) -> None:
    target = bpy.data.objects[target_name]
    old = target.data
    target.data = me
    me.name = old.name
    for mat in old.materials:
        me.materials.append(mat)
    for p in me.polygons:
        p.use_smooth = True
    bpy.data.meshes.remove(old)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    jobs = argv or ["CL_банка_мятая", "CL_банка_раздавлена"]
    for job in jobs:
        if job == "CL_банка_мятая":
            me = simulate(dense_can(2, jitter=0.0, dent=(0.06, 0.0, 0.0015, 0.012)), 0.025, math.radians(16), 60.0, 0.002,
                          (0.012, 0.016), CAN_CLOTH)
            replace("CL_банка_мятая_банка", me)
        elif job == "CL_банка_раздавлена":
            me = simulate(dense_can(5, jitter=0.0, dent=(0.05, 1.0, 0.0015, 0.012)), 0.118, math.radians(24), 60.0, 0.002,
                          (0.012, 0.016), CAN_CLOTH)
            replace("CL_банка_раздавлена_банка", me)
        print("crushed", job)
    bpy.ops.wm.save_mainfile(compress=True)
    print("saved", bpy.data.filepath)


if __name__ == "__main__":
    main()
