"""NPC: балаклава (вязаная, одна прорезь для глаз) — по форме головы, складки на шее симуляцией.

Оболочка головы и шеи на 3 мм от кожи, пересобранная ровной сеткой и сглаженная: трикотаж
натянут поверх носа и губ, не повторяет их. Прорезь — эллипс по глазам тела, край подвёрнут
валиком. Низ (горловина) длиннее, чем нужно: в симуляции он садится складками на шею —
дальше его прячет ворот куртки.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/balaclava.py [-- render]
→ _asset_src/npc_kit/balaclava/balaclava.blend (читает body/body_M.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import shell as sh  # noqa: E402

OUT = kc.WORK / "balaclava"
GAP = 0.003
Z_BOTTOM = 1.49        # низ горловины (уходит под ворот куртки)
Z_NECK_TOP = 1.62      # выше — голова, ниже — шея со складками
NECK_EXCESS = 1.22     # во сколько раз горловина длиннее шеи
SLOT_HALF_W = 0.064
SLOT_HALF_H = 0.019


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "body" / "body_M.blend"))
    body = bpy.data.objects["NPC_Body"]
    eyes = bpy.data.objects["NPC_Eyes"]
    dg = bpy.context.evaluated_depsgraph_get()
    ev = eyes.evaluated_get(dg)
    em = ev.to_mesh()
    ep = [ev.matrix_world @ v.co for v in em.vertices]
    ev.to_mesh_clear()
    eye_c = Vector((0.0, min(p.y for p in ep), sum(p.z for p in ep) / len(ep)))
    col = kc.collection("05_Balaclava")
    work = kc.collection("96_Balaclava_Work")
    head = sh.evaluated_copy(body, "Balaclava", work)
    head.data.materials.clear()
    sh.delete_faces(head, lambda c: c.z < Z_BOTTOM - 0.03 or (c.z < 1.60 and abs(c.x) > 0.13))
    bm = bmesh.new()
    bm.from_mesh(head.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * GAP
    bm.to_mesh(head.data)
    bm.free()
    sh.voxel_remesh(head, 0.0045)
    sh.keep_largest(head)
    # Лицо: трикотаж идёт поверх носа, губ и глазниц мостом — сглаживаем сильнее спереди.
    sh.smooth(head, 6, 0.5)
    sh.smooth(head, 18, 0.5, only=lambda c: c.y < -0.09 and c.z < 1.72)
    sh.offset_from(head, body, GAP, reach=0.03)
    sh.bisect(head, Vector((0, 0, Z_BOTTOM)), Vector((0, 0, -1)), clear_outer=True)

    def slot(c: Vector) -> bool:
        if c.y > eye_c.y + 0.05:
            return False
        return (c.x / SLOT_HALF_W) ** 2 + ((c.z - eye_c.z) / SLOT_HALF_H) ** 4 < 1.0
    sh.delete_faces(head, slot)
    sh.keep_largest(head)
    sh.smooth_boundary(head, 10)
    kc.move_to(head, col)
    # Валик по краю прорези: подвёрнутый край трикотажа.
    loops = sh.boundary_loops(head)
    slot_loop = max(loops, key=lambda lp: sum(head.data.vertices[i].co.z for i in lp) / len(lp))

    # Складки на шее — «скульптом»: неровные кольцевые валики, книзу крупнее (трикотаж собирается
    # на шее, низ уходит под ворот). Плотная вязка на голове складок не даёт — там только фактура.
    neck_folds(head, body)
    pts = [head.data.vertices[i].co.copy() for i in slot_loop]
    c = sum(pts, Vector()) / len(pts)
    rim_pts = [p + (p - c).normalized() * 0.0015 + Vector((0, -0.0012, 0)) for p in pts[::2]]
    rim = shtube(rim_pts, 0.0026, "Balaclava_SlotRim", col)
    mat = kc.clay("Balaclava_Knit", (0.035, 0.036, 0.03), 0.95)
    for o in (head, rim):
        o.data.materials.clear()
        o.data.materials.append(mat)
    kc.make_active(rim)
    bpy.ops.object.convert(target="MESH")
    for o in (head, rim):
        for p in o.data.polygons:
            p.use_smooth = True
    for o in list(work.objects):
        bpy.data.objects.remove(o)
    kc.log("BALACLAVA", len(head.data.vertices), "verts")
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(OUT / "balaclava.blend")
    if "render" in args:
        kc.studio()
        cams = {
            "bala_front": kc.camera("Cam_BalaFront", (0.0, -0.75, 1.68), (0, -0.04, 1.64), 85),
            "bala_34": kc.camera("Cam_Bala34", (0.45, -0.6, 1.70), (0, -0.03, 1.64), 85),
            "bala_side": kc.camera("Cam_BalaSide", (0.75, -0.03, 1.66), (0, -0.03, 1.64), 85),
            "bala_eyes": kc.camera("Cam_BalaEyes", (0.10, -0.42, 1.70), (0, -0.12, 1.69), 85),
        }
        for k, cam in cams.items():
            kc.render(cam, OUT / f"{k}.png", (800, 800), 64)


def neck_folds(head: bpy.types.Object, body: bpy.types.Object) -> None:
    import random
    rnd = random.Random(7)
    waves = [(rnd.uniform(0.014, 0.020), rnd.uniform(0, 6.28), rnd.uniform(0.3, 1.0), rnd.randint(1, 3)) for _ in range(4)]
    me = head.data
    cx, cy = 0.0, -0.06
    for v in me.vertices:
        p = v.co
        if p.z > Z_NECK_TOP:
            continue
        t = 1.0 - (p.z - Z_BOTTOM) / (Z_NECK_TOP - Z_BOTTOM)          # 1 — низ горловины
        ang = math.atan2(p.y - cy, p.x - cx)
        h = 0.0
        for lam, ph, amp, k in waves:
            # Валик идёт вокруг шеи с небольшим наклоном и меняет толщину по кругу.
            phase = 2 * math.pi * (p.z + 0.004 * math.sin(k * ang + ph)) / lam + ph
            h += amp * max(0.0, math.sin(phase)) ** 2 * (0.6 + 0.4 * math.sin(k * ang + 2 * ph))
        h /= sum(w[2] for w in waves)
        # Под подбородком и сзади на шее трикотаж собирается сильнее.
        front = max(0.0, -(p.y - cy) / max(math.hypot(p.x - cx, p.y - cy), 1e-6))
        amp = (0.0012 + 0.0042 * t) * (0.8 + 0.4 * front)
        r = Vector((p.x - cx, p.y - cy, 0.0))
        if r.length > 1e-6:
            r.normalize()
        v.co = p + r * (h * amp + 0.0012 * t)
    me.update()
    sh.offset_from(head, body, GAP * 0.8, reach=0.02)


def shtube(points: list[Vector], radius: float, name: str, col: bpy.types.Collection) -> bpy.types.Object:
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    sp = cu.splines.new("NURBS")
    sp.points.add(len(points) - 1)
    for p, q in zip(sp.points, points):
        p.co = (q.x, q.y, q.z, 1.0)
    sp.order_u = 3
    sp.use_cyclic_u = True
    obj = bpy.data.objects.new(name, cu)
    col.objects.link(obj)
    return obj


if __name__ == "__main__":
    main()
