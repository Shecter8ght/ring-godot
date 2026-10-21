"""NPC: кожаная куртка-бомбер (как у мародёра на референсе) — оболочкой вокруг тела и симуляцией.

Оболочка: тело, раздутое на запас и пересобранное ровной сеткой (без пальцев, щелей и подмышечных
провалов), ниже груди — «коробкой» по обхвату. Разрезы: низ (над резинкой), край рукава, горловина,
бок и низ рукава — плоскостью y, центр переда — x = 0 (застёжка). Каждая деталь разворачивается в
лекало с припуском; пояс и манжеты — трикотажные полосы, они стягиваются и собирают кожу в сборку.
Капюшон — оболочка вокруг головы с вырезом для лица, две половины; пришит к горловине и в
симуляции падает на спину (голова из препятствия убрана).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/jacket.py [-- render]
→ _asset_src/npc_kit/jacket/jacket_sim.blend (читает pants/pants_sim.blend)
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import garment as gm  # noqa: E402
import kit_common as kc  # noqa: E402
import shell as sh  # noqa: E402

OUT = kc.WORK / "jacket"
VOXEL = 0.012
MARGIN = 0.024          # запас оболочки от тела
Z_HEM = 0.925           # низ кожи; ниже — резинка
RIB_H = 0.065
CUFF_H = 0.07
SLEEVE_END = 0.075      # кожа рукава кончается за столько до запястья, дальше манжета
HOOD = False            # капюшон — пока отдельной сменной деталью на будущее; сейчас воротник-стойка
HOOD_FOLD = 150.0       # на сколько градусов откинут капюшон (0 — надет)
COLLAR_H = 0.05         # высота трикотажного воротника
SPLIT_Y = -0.03         # плоскость бока и низа рукава: руки в A-позе лежат почти в ней
EASE = (1.08, 1.03)     # припуск лекал: по ширине, по длине


def arm_points(rig: bpy.types.Object, side: str) -> tuple[Vector, Vector, Vector]:
    b = rig.data.bones
    return (b["upperarm_" + side].head_local.copy(), b["lowerarm_" + side].head_local.copy(),
            b["hand_" + side].head_local.copy())


def build_shell(body: bpy.types.Object, pants: bpy.types.Object, rig: bpy.types.Object,
                col: bpy.types.Collection) -> bpy.types.Object:
    shell = sh.evaluated_copy(body, "Jacket_Shell", col)
    bm = bmesh.new()
    bm.from_mesh(shell.data)
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * MARGIN
    bm.to_mesh(shell.data)
    bm.free()
    # Пересборка ровной сеткой: раздутые пальцы, подмышки и пах сливаются — нужен только торс и руки.
    sh.voxel_remesh(shell, VOXEL)
    sh.delete_faces(shell, lambda c: c.z < Z_HEM - 0.06 or c.z > 1.72)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        sho, elb, wr = arm_points(rig, side)
        d = (elb - wr).normalized()          # от кисти к локтю
        cut = wr + d * SLEEVE_END
        sh.bisect(shell, cut, -d, clear_outer=True, region=lambda c, s=sgn: c.x * s > 0.30)
    sh.keep_largest(shell)
    sh.smooth(shell, 28, 0.5, only=lambda c: c.z > Z_HEM - 0.05)
    # Ниже груди — по обхвату (выпуклой оболочке сечения): куртка висит «коробкой», а не по талии.
    union = sh.evaluated_copy(body, "Body_Pants_Union", col)
    bm = bmesh.new()
    bm.from_mesh(union.data)
    pm = sh.evaluated_copy(pants, "Pants_Tmp", col)
    bm.from_mesh(pm.data)
    bm.to_mesh(union.data)
    bm.free()
    bpy.data.objects.remove(pm)
    rings = gm.RingStack(union, Z_HEM - 0.07, 1.37, lambda z: MARGIN + 0.006, lambda x, y: abs(x) < 0.215)
    bpy.data.objects.remove(union)
    arms = [arm_points(rig, s) for s in ("l", "r")]
    for v in shell.data.vertices:
        p = v.co
        if p.z > 1.36:
            continue
        d_arm = min(min(sh.seg_dist(p, a, b), sh.seg_dist(p, b, c)) for a, b, c in arms) / 0.065
        if d_arm < 1.2:
            continue
        f = (p.z - rings.z0) / rings.step
        i = max(0, min(len(rings.rings) - 1, int(round(f))))
        ring = rings.rings[i]
        cx, cy = ring.c
        ang = math.degrees(math.atan2(p.y - cy, p.x - cx))
        rx, ry = ring.point(ang)
        r_ring = math.hypot(rx - cx, ry - cy)
        r = math.hypot(p.x - cx, p.y - cy)
        if r < r_ring:
            k = r_ring / max(r, 1e-6)
            w = gm.smoothstep((1.36 - p.z) / 0.06)
            v.co.x = cx + (p.x - cx) * (1 + (k - 1) * w)
            v.co.y = cy + (p.y - cy) * (1 + (k - 1) * w)
    shell.data.update()
    sh.smooth(shell, 4, 0.4, only=lambda c: c.z > Z_HEM - 0.05)
    sh.offset_from(shell, body, MARGIN * 0.75)
    sh.offset_from(shell, pants, 0.010, only=lambda c: c.z < 1.12)
    sh.smooth(shell, 3, 0.4, only=lambda c: c.z < 1.15)
    # Низ над резинкой.
    sh.bisect(shell, Vector((0, 0, Z_HEM)), Vector((0, 0, -1)), clear_outer=True)

    def above_neck(c: Vector) -> bool:
        """Горловина: сзади на основании шеи, спереди ниже на 8,5 см."""
        dx, dy = c.x, c.y + 0.055
        r = math.hypot(dx, dy)
        if r > 0.125 or c.z < 1.40:
            return False
        front = max(0.0, -dy / max(r, 1e-6))
        return c.z > 1.556 - 0.085 * front ** 1.5
    sh.delete_faces(shell, above_neck)
    sh.keep_largest(shell)
    sh.smooth_boundary(shell, 8, only=lambda c: c.z > 1.40)
    sh.fill_small_holes(shell, 30)
    # Бок и низ рукава; центр переда.
    sh.bisect(shell, Vector((0, SPLIT_Y, 0)), Vector((0, 1, 0)))
    sh.bisect(shell, Vector((0, 0, 0)), Vector((1, 0, 0)))
    for poly in shell.data.polygons:
        poly.use_smooth = True
    return shell


def neckline_z(c: Vector) -> float:
    """Высота горловины над точкой: сзади на основании шеи, спереди ниже на 8,5 см."""
    dx, dy = c.x, c.y + 0.055
    r = math.hypot(dx, dy)
    front = max(0.0, -dy / max(r, 1e-6))
    return 1.556 - 0.085 * front ** 1.5


def build_hood(body: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    """Капюшон «надетым»: голова с запасом 3 см, ровная сетка, низ — по горловине, вырез для лица."""
    hood = sh.evaluated_copy(body, "Hood_Shell", col)
    sh.delete_faces(hood, lambda c: c.z < 1.44 or abs(c.x) > 0.17)
    bm = bmesh.new()
    bm.from_mesh(hood.data)
    bmesh.ops.holes_fill(bm, edges=[e for e in bm.edges if e.is_boundary], sides=0)
    bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.normal_update()
    for v in bm.verts:
        v.co += v.normal * 0.030
    bm.to_mesh(hood.data)
    bm.free()
    sh.voxel_remesh(hood, VOXEL)
    sh.keep_largest(hood)
    sh.smooth(hood, 14, 0.5)
    # Капюшону нужен объём над макушкой и сзади: чуть вытягиваем верх назад.
    for v in hood.data.vertices:
        t = gm.smoothstep((v.co.z - 1.62) / 0.2)
        v.co.y += 0.025 * t * gm.smoothstep((v.co.y + 0.02) / 0.1)
        v.co.z += 0.012 * t
    hood.data.update()

    def face_open(c: Vector) -> bool:
        return c.y < -0.02 and (c.x / 0.105) ** 2 + ((c.z - 1.645) / 0.19) ** 2 < 1.0
    sh.delete_faces(hood, lambda c: c.z < neckline_z(c) + 0.004 or face_open(c))
    sh.keep_largest(hood)
    sh.smooth_boundary(hood, 8)
    sh.bisect(hood, Vector((0, 0, 0)), Vector((1, 0, 0)))
    for poly in hood.data.polygons:
        poly.use_smooth = True
    return hood


def fold_down(verts) -> None:
    """Откинуть капюшон на спину: низ (у горловины) остаётся, верх поворачивается вокруг оси X
    через основание шеи сзади назад и вниз на HOOD_FOLD — тем сильнее, чем дальше от горловины.
    Делается после развёртки: лекало — от надетого капюшона."""
    pivot = Vector((0.0, 0.045, 1.556))
    for v in verts:
        p = v.co
        h = max(0.0, p.z - neckline_z(p))
        t = gm.smoothstep(h / 0.16)
        phi = -math.radians(HOOD_FOLD) * t
        d = p - pivot
        y = d.y * math.cos(phi) - d.z * math.sin(phi)
        z = d.y * math.sin(phi) + d.z * math.cos(phi)
        # Откинутый капюшон шире ложится по плечам и отходит от спины на пару сантиметров.
        v.co = Vector((p.x * (1.0 + 0.15 * t), pivot.y + y + 0.02 * t, pivot.z + z))


def neck_loop_ordered(me: bpy.types.Mesh, loop: list[int]) -> list[int]:
    """Горловина начиная от центра переда (там шов воротника совпадёт с застёжкой)."""
    k = min(range(len(loop)), key=lambda i: (me.vertices[loop[i]].co.x ** 2 + 4 * max(0.0, me.vertices[loop[i]].co.y + 0.2) ** 2
                                             - me.vertices[loop[i]].co.y * 0.0))
    front = min(range(len(loop)), key=lambda i: me.vertices[loop[i]].co.y)
    return loop[front:] + loop[:front]


def loop_info(shell: bpy.types.Object) -> dict[str, list[int]]:
    """Края оболочки: низ, горловина, левый и правый край рукава."""
    me = shell.data
    out = {}
    for loop in sh.boundary_loops(shell):
        pts = [me.vertices[i].co for i in loop]
        c = sum(pts, Vector()) / len(pts)
        if abs(c.z - Z_HEM) < 0.02 and abs(c.x) < 0.1:
            out["hem"] = loop
        elif c.z > 1.40 and abs(c.x) < 0.1:
            out["neck"] = loop
        elif c.x > 0.3:
            out["cuff_l"] = loop
        elif c.x < -0.3:
            out["cuff_r"] = loop
    return out


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "pants" / "pants_sim.blend"))
    body = bpy.data.objects["NPC_Body"]
    rig = bpy.data.objects["NPC_Skeleton"]
    pants = bpy.data.objects["Pants"]
    work = kc.collection("96_Jacket_Work")
    t0 = time.time()
    shell = build_shell(body, pants, rig, work)
    loops = loop_info(shell)
    for loop in sh.boundary_loops(shell):
        pts = [shell.data.vertices[i].co for i in loop]
        kc.log("  контур", len(loop), "x", round(min(p.x for p in pts), 2), round(max(p.x for p in pts), 2),
               "z", round(min(p.z for p in pts), 2), round(max(p.z for p in pts), 2),
               "скачок", round(max((pts[i] - pts[i - 1]).length for i in range(len(pts))), 3))
    kc.log("JACKET_SHELL", len(shell.data.vertices), "verts", {k: len(v) for k, v in loops.items()},
           f"{time.time() - t0:.0f} с")

    # Капюшон — отдельный кусок в той же оболочке (свои вершины), низ пришьём к горловине.
    n_shell_v = len(shell.data.vertices)
    n_shell_f = len(shell.data.polygons)
    if HOOD:
        hood = build_hood(body, work)
        bm = bmesh.new()
        bm.from_mesh(shell.data)
        bm.from_mesh(hood.data)
        bm.to_mesh(shell.data)
        bm.free()
        shell.data.update()
    me = shell.data
    neck = loops["neck"]
    hood_sew = []
    hood_bottom = []
    for loop in sh.boundary_loops(shell):
        if loop[0] < n_shell_v:
            continue
        for i in loop:
            c = me.vertices[i].co
            if abs(c.z - neckline_z(c)) < 0.02:
                hood_bottom.append(i)
    # Пары по углу вокруг шеи (не по расстоянию): по порядку, без повторов — иначе несколько точек
    # капюшона садятся на одну точку горловины и низ стягивается в ком.
    def neck_angle(i: int) -> float:
        c = me.vertices[i].co
        return math.atan2(c.x, c.y + 0.055)           # 0 — сзади, ±π — спереди
    neck_sorted = sorted(neck, key=neck_angle)
    neck_ang = [neck_angle(k) for k in neck_sorted]
    used: set[int] = set()
    for i in sorted(hood_bottom, key=neck_angle):
        a = neck_angle(i)
        j = min(range(len(neck_sorted)), key=lambda k: abs(neck_ang[k] - a) + (1.0 if neck_sorted[k] in used else 0.0))
        used.add(neck_sorted[j])
        hood_sew.append((i, neck_sorted[j]))
    kc.log("JACKET_HOOD", len(me.vertices) - n_shell_v, "verts", len(hood_bottom), "на горловине")

    pieces: dict[str, sh.ShellPiece] = {}
    for poly in me.polygons:
        c = Vector(poly.center)
        if poly.index >= n_shell_f:
            name = "hood_l" if c.x > 0 else "hood_r"
        elif c.y > SPLIT_Y:
            name = "back_l" if c.x > 0 else "back_r"
        else:
            name = "front_l" if c.x > 0 else "front_r"
        pieces.setdefault(name, sh.ShellPiece(name, "Jacket_Leather")).faces.append(list(poly.vertices))
    for pc in pieces.values():
        pc.material = "Jacket_Leather"
        sh.flatten(shell, pc, (1.03, 1.03) if pc.name.startswith("hood") else EASE, work)
        xs = [p[0] for p in pc.flat.values()]
        ys = [p[1] for p in pc.flat.values()]
        kc.log("JACKET_FLAT", pc.name, len(pc.faces), "граней", f"{max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} м")

    fold_down([v for v in me.vertices if v.index >= n_shell_v])
    me.update()
    extras = []
    if not HOOD:
        # Воротник-стойка: трикотажная полоса вверх от горловины, чуть к шее.
        loop = neck_loop_ordered(me, neck)
        pts = [me.vertices[i].co.copy() for i in loop]
        strip = sh.strip_along(pts, loop, lambda i, p: Vector((0, -0.25, 1)).normalized() if p.y < -0.08 else Vector((0, 0, 1)),
                               COLLAR_H, 5, outward=lambda p: -Vector((p.x, p.y + 0.055, 0)).normalized() * 0.6)
        strip.update(name="collar", material="Jacket_Rib", groups=["rib"])
        extras.append(strip)
    # Пояс-резинка: вниз от края, чуть наружу.
    # Пояс начинается и кончается у застёжки (как у настоящей куртки), а не где попало.
    hem = neck_loop_ordered(me, loops["hem"])
    pts = [me.vertices[i].co.copy() for i in hem]
    strip = sh.strip_along(pts, hem, lambda i, p: Vector((0, 0, -1)), RIB_H, 6,
                           outward=lambda p: Vector((p.x, p.y + 0.03, 0)).normalized())
    strip.update(name="band", material="Jacket_Rib", groups=["rib"])
    extras.append(strip)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        loop = loops["cuff_" + side]
        sho, elb, wr = arm_points(rig, side)
        d = (wr - elb).normalized()
        pts = [me.vertices[i].co.copy() for i in loop]
        axis_c = wr - d * SLEEVE_END
        strip = sh.strip_along(pts, loop, lambda i, p, d=d: d, CUFF_H, 6,
                               outward=lambda p, c=axis_c, d=d: ((p - c) - d * (p - c).dot(d)).normalized())
        strip.update(name="cuff_" + side, material="Jacket_Rib", groups=["rib"])
        extras.append(strip)
    col = kc.collection("03_Jacket")
    kc.clay("Jacket_Leather", (0.075, 0.045, 0.03), 0.42)
    kc.clay("Jacket_Rib", (0.035, 0.032, 0.03), 0.9)
    obj, sew = sh.assemble("Jacket", shell, list(pieces.values()), extras, col, VOXEL, extra_sew=hood_sew)
    kc.log("JACKET_MESH", len(obj.data.vertices), "verts", len(obj.data.polygons), "faces", len(sew), "sew")
    OUT.mkdir(parents=True, exist_ok=True)

    sim_col = bpy.data.collections.get("98_Sim_Colliders") or kc.collection("98_Sim_Colliders")
    sim_col.hide_viewport = False
    for o in list(sim_col.objects):
        bpy.data.objects.remove(o)
    gm.make_collider(body, "Body_Collider", sim_col, offset=0.0015, thickness=0.003, friction=15.0)
    gm.make_collider(pants, "Pants_Collider", sim_col, offset=0.001, thickness=0.003, friction=15.0)
    work.hide_viewport = True
    work.hide_render = True
    if "place_only" in args:
        kc.save(OUT / "jacket_placed.blend")
        cams = kc.view_cameras(1.8)
        for view in ["front", "side", "three_quarter", "back"]:
            kc.render(cams[view], OUT / f"placed_{view}.png", (700, 900), 16)
        return
    frames = int(next((a.split("=")[1] for a in args if a.startswith("frames=")), 90))
    # Капюшон мягче (тонкая кожа на подкладке): общая жёсткость на изгиб — его, у остальной
    # кожи — по группе "stiff" (наибольшая).
    leather = gm.FABRICS["leather"]
    stiff = obj.vertex_groups.new(name="stiff")
    hood_ids = set()
    for nm in ("piece_hood_l", "piece_hood_r"):
        if nm not in obj.vertex_groups:
            continue
        gi = obj.vertex_groups[nm].index
        hood_ids |= {v.index for v in obj.data.vertices if any(g.group == gi for g in v.groups)}
    stiff.add([v.index for v in obj.data.vertices if v.index not in hood_ids], 1.0, "REPLACE")
    soft = gm.Fabric(leather.mass, leather.tension, leather.compression, leather.shear, 4.0, quality=leather.quality)
    gm.simulate(obj, soft, frames=frames, sew_frames=20, shrink_group="rib", shrink=0.05,
                stiff_group="stiff", stiff_bending=leather.bending,
                collide_collection=sim_col, debug=tuple(args), log=kc.log)
    gm.freeze(obj, sew, kc.log)
    # Швы сварены — досадка со столкновениями по всей вещи: складки, проткнувшие друг друга у швов
    # (там самостолкновения были выключены), расправляются.
    gm.relax(obj, gm.Fabric(leather.mass, leather.tension, leather.compression, leather.shear, 20.0,
                            quality=leather.quality), 14, collide_collection=sim_col, log=kc.log)
    gm.smooth_noise(obj, 3, 0.4)
    kc.log("JACKET_SIM", round(time.time() - t0, 1), "s")
    sim_col.hide_viewport = True
    sim_col.hide_render = True
    kc.save(OUT / "jacket_sim.blend")
    if "render" in args:
        cams = kc.view_cameras(1.8)
        for view in ["front", "back", "side", "three_quarter"]:
            kc.render(cams[view], OUT / f"jacket_{view}.png", (900, 1200), 48)
    snap_col = bpy.data.collections.get("97_Snapshots")
    if snap_col:
        obj.hide_render = True
        cam = kc.camera("Cam_Snap", (0.0, -3.2, 1.25), (0.0, 0.0, 1.2), 60)
        for snap in sorted(snap_col.objects, key=lambda o: o.name):
            snap.hide_render = False
            kc.render(cam, OUT / "snaps" / f"{snap.name}.png", (600, 400), 12)
            snap.hide_render = True


if __name__ == "__main__":
    main()
