"""Мусор общежития, партия 2: чёрные мешки для мусора 60 л с синими завязками-лентами — форма на просмотр владельцем.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/build_trash_bags.py -- "E:/Models Blender/ENVIRONMENT/RING_Dorm_Clutter/models/RING_Dorm_Bags_v01.blend" [вариант …]

Мешок — плёнка (ткань с малой жёсткостью на изгиб и самостолкновениями): рукав Ø (2 × 600 мм) / π = 382 мм с донцем,
внутри — куча мусора (коробки, бутылки, свёртки — неподвижные коллайдеры, после симуляции удаляются). Горловину
стягивает лента: пояс закреплённых вершин на крючке пустышки, пустышка сжимается в 9 раз и уходит в своё место —
излишек плёнки собирается складками сам, хвост над завязкой опадает. Завязка — лента 9 × 0,6 мм: пояс на горле,
узел, две петли и концы. Варианты: полный стоит, полный лежит на боку, полупустой с завалившимся верхом.
Корень — точка опоры на полу, Z вверх. Материалы — нейтральные слоты; текстуры после принятия формы.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import build_found_lights as F  # noqa: E402
import mlib as L  # noqa: E402

V = Vector
TAU = 2 * math.pi
R_BAG = 2 * 0.60 / TAU  # плоский мешок 600 мм шириной — рукав такого обхвата
LEN_BAG = 0.80  # от дна до края горловины (700 мм мешка + донце)
SEGS = 96
STEP = 0.012
FRAMES = 110
GATHER_END = 50
# плёнка ПНД 20 мкм: тянется мало, гнётся легко
FILM = {"quality": 10, "mass": 0.01, "tension_stiffness": 15.0, "compression_stiffness": 5.0, "shear_stiffness": 5.0,
        "bending_stiffness": 0.02, "tension_damping": 5.0, "compression_damping": 5.0, "air_damping": 1.0}

VARIANTS = {
    # имя: куча (центр, полуоси эллипсоида, сколько), лежит ли рукав, конец горла (место, наклон рад, ось наклона)
    "CL_мешок_полный": {"heap": ((0, 0, 0.24), (0.18, 0.18, 0.23), 52), "lying": False,
                        "neck": ((0.02, 0.0, 0.50), 0.25, (0, 1, 0)), "seed": 3},  # горло ниже кучи + слабина: мешок осел на пол
    "CL_мешок_лежит": {"heap": ((-0.06, 0, 0.16), (0.27, 0.16, 0.15), 48), "lying": True,
                       "neck": ((0.36, 0.02, 0.07), math.radians(80), (0, 1, 0)), "seed": 8},
    "CL_мешок_полупустой": {"heap": ((0, 0, 0.13), (0.17, 0.17, 0.12), 28), "lying": False,
                            "neck": ((0.12, 0.03, 0.30), math.radians(65), (0.2, 1, 0)), "seed": 13},
}


def mats() -> dict:
    return {"bag": L.material("Мешок_плёнка_чёрная", (0.018, 0.018, 0.02), 0.35),
            "tie": L.material("Мешок_завязка_синяя", (0.04, 0.16, 0.62), 0.45)}


def sleeve(lying: bool) -> tuple:
    """Рукав с донцем: донце — круг из колец, стенка до края горловины. Возвращает объект и номера вершин пояса горла."""
    bm = bmesh.new()
    rings = []
    for k in range(1, 7):  # донце
        rr = R_BAG * k / 6
        rings.append([bm.verts.new((rr * math.cos(TAU * i / SEGS), rr * math.sin(TAU * i / SEGS), 0.0)) for i in range(SEGS)])
    z = STEP
    while z <= LEN_BAG + 1e-6:
        rings.append([bm.verts.new((R_BAG * math.cos(TAU * i / SEGS), R_BAG * math.sin(TAU * i / SEGS), z)) for i in range(SEGS)])
        z += STEP
    c = bm.verts.new((0, 0, 0))
    for i in range(SEGS):
        bm.faces.new((c, rings[0][i], rings[0][(i + 1) % SEGS]))
    for r0, r1 in zip(rings, rings[1:]):
        for i in range(SEGS):
            j = (i + 1) % SEGS
            bm.faces.new((r0[i], r0[j], r1[j], r1[i]))
    neck_z = LEN_BAG - 0.12  # над завязкой остаётся «хвост» 120 мм
    if lying:  # рукав лёжа вдоль +X, низом над полом
        L.transform(bm, bm.verts, Matrix.Translation((-0.42, 0, R_BAG + 0.006)) @ Matrix.Rotation(math.radians(90), 4, "Y")
                    @ Matrix.Rotation(math.radians(180), 4, "Z"))
        # после поворота ось рукава — +X: «высота» вдоль рукава = x + 0.42 (дно в x = −0.42 → смотрим по исходной z)
    else:
        L.transform(bm, bm.verts, Matrix.Translation((0, 0, 0.006)))
    me = bpy.data.meshes.new("мешок_сим")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("мешок_сим", me)
    bpy.context.scene.collection.objects.link(ob)
    # пояс горла: кольца исходной высоты neck_z ± 8 мм (по порядку построения: 6 колец донца, затем стенка)
    first = 6 * SEGS  # центр донца создан последним
    neck = []
    k = 0
    z = STEP
    while z <= LEN_BAG + 1e-6:
        if abs(z - neck_z) <= 0.0081:
            neck += list(range(first + k * SEGS, first + (k + 1) * SEGS))
        k += 1
        z += STEP
    return ob, neck


def heap(center, half, count, seed) -> list:
    """Куча мусора внутри мешка: коробки, бутылки, свёртки — неподвижные коллайдеры."""
    rnd = random.Random(seed)
    obs = []
    for n in range(count):
        bm = bmesh.new()
        kind = rnd.choice(("box", "box", "bottle", "lump", "lump"))
        if kind == "box":
            s = (rnd.uniform(0.04, 0.14), rnd.uniform(0.03, 0.10), rnd.uniform(0.02, 0.08))
            L.bm_box(bm, (-s[0] / 2, -s[1] / 2, -s[2] / 2), (s[0] / 2, s[1] / 2, s[2] / 2))
        elif kind == "bottle":
            L.bm_cyl(bm, (0, 0, -0.10), (0, 0, 0.10), rnd.uniform(0.025, 0.04), 12)
        else:
            L.bm_sphere(bm, (0, 0, 0), rnd.uniform(0.03, 0.065), 10, 6)
            sq = (rnd.uniform(0.7, 1.3), rnd.uniform(0.7, 1.3), rnd.uniform(0.5, 1.0))
            for v in bm.verts:
                v.co = V((v.co.x * sq[0], v.co.y * sq[1], v.co.z * sq[2]))
        # точка в «скруглённом бруске» кучи (|x|⁴ + |y|⁴ + |z|⁴ ≤ 1 — полно и у дна, не яйцом), ниже — гуще
        while True:
            p = V((rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)))
            if p.x ** 4 + p.y ** 4 + p.z ** 4 <= 1.0:
                break
        p.z = -1.0 + (p.z + 1.0) ** 1.2 * 2 ** -0.2
        pos = V(center) + V((p.x * half[0], p.y * half[1], p.z * half[2]))
        rot = Matrix.Rotation(rnd.uniform(0, TAU), 4, "Z") @ Matrix.Rotation(rnd.uniform(-0.6, 0.6), 4, "X")
        L.transform(bm, bm.verts, Matrix.Translation(pos) @ rot)
        for v in bm.verts:
            v.co.z = max(v.co.z, 0.004)
        me = bpy.data.meshes.new(f"куча_{n}")
        bm.to_mesh(me)
        bm.free()
        ob = bpy.data.objects.new(me.name, me)
        bpy.context.scene.collection.objects.link(ob)
        ob.modifiers.new("Collision", "COLLISION")
        ob.collision.thickness_outer = 0.004
        ob.collision.cloth_friction = 5.0
        obs.append(ob)
    return obs


def simulate(ob, neck_idx: list, neck_to: tuple, lying: bool, extra: list) -> tuple:
    """Горло стягивается и уходит на место neck_to, плёнка падает на кучу и пол. Возвращает сетку и матрицу горла."""
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 1, FRAMES
    bm = bmesh.new()
    L.bm_box(bm, (-1.0, -1.0, -0.02), (1.0, 1.0, 0.0))
    me = bpy.data.meshes.new("пол_сим")
    bm.to_mesh(me)
    bm.free()
    ground = bpy.data.objects.new("пол_сим", me)
    sc.collection.objects.link(ground)
    ground.modifiers.new("Collision", "COLLISION")
    ground.collision.thickness_outer = 0.002
    ground.collision.cloth_friction = 10.0
    grp = ob.vertex_groups.new(name="горло")
    grp.add(neck_idx, 1.0, "REPLACE")
    pts = [ob.data.vertices[i].co for i in neck_idx]
    c0 = sum(pts, V()) / len(pts)
    axis0 = V((1, 0, 0)) if lying else V((0, 0, 1))
    e = bpy.data.objects.new("горло_сим", None)
    sc.collection.objects.link(e)
    e.location = c0
    e.keyframe_insert("location", frame=1)
    e.keyframe_insert("rotation_euler", frame=1)
    e.keyframe_insert("scale", frame=1)
    hook = ob.modifiers.new("горло", "HOOK")
    hook.object = e
    hook.vertex_group = grp.name
    hook.center = c0
    hook.matrix_inverse = Matrix.Translation(-c0)  # пустышка в c0 при кадре 1 — без сдвига
    pos, tilt, tax = neck_to
    rot = Matrix.Rotation(tilt, 4, V(tax).normalized())
    if lying:  # ось горла у лежачего — +X; наклон задан от вертикали — поворачиваем ось так, чтобы смотрела вбок-вверх
        rot = Matrix.Rotation(-math.radians(90), 4, "Y") @ rot
    # сжатие в плоскости поперёк оси горла: масштаб в осях пустышки (её Z — ось горла)
    to_axis = axis0.to_track_quat("Z", "Y").to_matrix().to_4x4()
    e.matrix_world = Matrix.Translation(V(pos)) @ rot @ to_axis @ Matrix.Diagonal((0.11, 0.11, 1.0, 1.0)) @ to_axis.inverted()
    for f in (GATHER_END,):
        e.keyframe_insert("location", frame=f)
        e.keyframe_insert("rotation_euler", frame=f)
        e.keyframe_insert("scale", frame=f)
    cl = ob.modifiers.new("Cloth", "CLOTH")
    s = cl.settings
    for k, v in FILM.items():
        setattr(s, k, v)
    s.vertex_group_mass = grp.name
    cc = cl.collision_settings
    cc.use_collision = True
    cc.distance_min = 0.003
    cc.use_self_collision = True
    cc.self_distance_min = 0.0025
    cc.collision_quality = 3
    cl.point_cache.frame_start = 1
    cl.point_cache.frame_end = FRAMES
    for f in range(1, FRAMES + 1):
        sc.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    m_neck = e.matrix_world.copy()
    for o in extra + [ground, e, ob]:
        bpy.data.objects.remove(o)
    return out, m_neck, to_axis


def tape(bm, path, width=0.009, thick=0.0006, up=(0, 0, 1)) -> None:
    L.bm_sweep(bm, path, [(-width / 2, -thick / 2), (width / 2, -thick / 2), (width / 2, thick / 2), (-width / 2, thick / 2)],
               up=up)


def tie(bm, m_neck: Matrix, to_axis: Matrix, seed: int) -> None:
    """Завязка у горла в осях пустышки (Z — ось горла наружу): пояс ленты, узел, две петли и концы, петли провисают."""
    rnd = random.Random(seed)
    frame = m_neck @ to_axis
    loc, rot, _ = frame.decompose()
    basis = rot.to_matrix()
    ax, ay, az = basis.col[0], basis.col[1], basis.col[2]

    def at(x, y, z):
        return loc + ax * x + ay * y + az * z
    # пояс — лента вокруг стянутого горла
    belt = [at(0.024 * math.cos(TAU * i / 20) * (1 + 0.15 * math.sin(3 * TAU * i / 20)), 0.024 * math.sin(TAU * i / 20), 0.002 * math.sin(2 * TAU * i / 20))
            for i in range(20)]
    L.bm_sweep(bm, belt, [(-0.0045, -0.0003), (0.0045, -0.0003), (0.0045, 0.0003), (-0.0045, 0.0003)], closed=True, up=tuple(az))
    # узел — комок ленты сбоку горла
    kc = V((0.03, 0.0, 0.006))
    for k in range(3):
        ring = []
        for i in range(10):
            t = TAU * i / 10
            ring.append(at(kc.x + 0.009 * math.cos(t), kc.y + 0.009 * math.sin(t) * math.cos(k), kc.z + 0.006 * math.sin(t) * math.sin(k + 0.5)))
        L.bm_sweep(bm, ring, [(-0.0045, -0.0003), (0.0045, -0.0003), (0.0045, 0.0003), (-0.0045, 0.0003)], closed=True, up=tuple(az))
    # петли и концы: из узла наружу, провисают к полу
    down = V((0, 0, -1))
    for side, length, loop in ((1, rnd.uniform(0.07, 0.09), True), (-1, rnd.uniform(0.06, 0.08), True),
                               (1, rnd.uniform(0.04, 0.06), False), (-1, rnd.uniform(0.03, 0.05), False)):
        a0 = rnd.uniform(-0.5, 0.5) + (0.0 if side > 0 else math.pi * 0.35)
        path = []
        n = 12
        for i in range(n + 1):
            t = i / n
            if loop:  # петля-капля: уходит и возвращается к узлу
                ang = TAU * t
                r = length * 0.5 * (1 - math.cos(ang)) * 0.9
                w = 0.012 * math.sin(ang)
                d = V((math.cos(a0) * r - math.sin(a0) * w, math.sin(a0) * r + math.cos(a0) * w, 0.004 * math.sin(ang)))
                sag = 0.35 * (r / length) ** 2 * length
            else:  # конец ленты
                d = V((math.cos(a0 + 0.6 * side) * length * t, math.sin(a0 + 0.6 * side) * length * t, 0.0))
                sag = 0.5 * t * t * length
            p = at(kc.x + d.x, kc.y + d.y, kc.z + d.z) + down * sag
            path.append(p)
        if loop:
            path[-1] = path[0] + (path[1] - path[0]) * 0.02
        tape(bm, path, up=tuple(az))


def build(out: str, names: list) -> None:
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    top = L.collection("Мусор_партия2_мешки_v01")
    m = mats()
    for k, name in enumerate(names):
        v = VARIANTS[name]
        ob, neck = sleeve(v["lying"])
        extra = heap(*v["heap"], v["seed"])
        me, m_neck, to_axis = simulate(ob, neck, v["neck"], v["lying"], extra)
        low = min(p.co.z for p in me.vertices)
        me.transform(Matrix.Translation((0, 0, -low)))
        r = L.root(name, top, (k * 0.9, 0.0, 0.0))
        bag = bpy.data.objects.new(name + "_плёнка", me)
        top.objects.link(bag)
        bag.parent = r
        me.materials.append(m["bag"])
        for p in me.polygons:
            p.use_smooth = True
        sub = bag.modifiers.new("Сглаживание", "SUBSURF")
        sub.levels = sub.render_levels = 1
        bm = bmesh.new()
        tie(bm, Matrix.Translation((0, 0, -low)) @ m_neck, to_axis, v["seed"])
        L.finish_bm(bm, name + "_завязка", top, m["tie"], r, smooth_angle=60)
        print("bag", name, len(me.vertices), "верш.", flush=True)
    F.studio(L.collection("Студия"))
    floor = bpy.data.objects.get("студия_пол")
    if floor:
        floor.scale = (2.4, 2.0, 1.0)
        floor.location = (0.9, 0.1, 0)
    sc = bpy.context.scene
    cam = sc.camera
    cam.location = (0.9, -2.6, 1.3)
    cam.rotation_euler = (V((0.9, 0.0, 0.2)) - V(cam.location)).to_track_quat("-Z", "Y").to_euler()
    os.makedirs(os.path.dirname(out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("saved", out)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    build(argv[0], argv[1:] or list(VARIANTS))
