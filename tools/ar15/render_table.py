# AR-15 «ГРАНЬ-15»: серия рендеров для владельца — две винтовки на полевом столе в армейской палатке, идёт чистка
# (владелец 30.10: «где-то 5 общих, две винтовки, одна в собранном виде, другая разобранная на детали, лежат на одном
# столе достаточно хаотично — процесс чистки; потом у собранной множество средних и ближних ракурсов; пара — с оттянутым
# затвором, вытащенным магазином, крупно гильза, выбрасыватель, открытая шторка — динамика»).
#   blender -b -y <файл износа.blend> --python tools/ar15/render_table.py -- <папка кадров> <сцена.blend> <сцена_B.blend>
#           [ширина высота сэмплы] [кадры через запятую]
# -y — драйверы механики (AR15_Controls) на выражениях Python. Разобранная винтовка — копии деталей (общие сетки) группами
# неполной разборки; детали падают на стол физикой (жёсткие тела по выпуклой оболочке группы — на плоскости тело и
# лежит на своей оболочке) и ложатся сами, без ручной раскладки. Собранная: A — закрыта, на правом боку (левый — вверх);
# B — разряжание: рукоятка заряжания и рама назад, шторка открыта, магазин вынут и лежит рядом, патрон вылетает из окна
# (размытие движения).
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tent_scene as T  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
OUT_DIR, OUT_BLEND, OUT_BLEND_B = a[0], a[1], a[2]
RX, RY, SAMPLES = (int(a[3]), int(a[4]), int(a[5])) if len(a) > 5 else (1920, 1080, 160)
ONLY = set(a[6].split(",")) if len(a) > 6 else None
os.makedirs(OUT_DIR, exist_ok=True)
rng = np.random.default_rng(30)
d = math.radians

TOP = 0.76                              # высота столешницы
TC = Vector((0.10, -0.92))              # центр стола
THX, THY = 0.88, 0.43                   # полуразмеры столешницы
sc = bpy.context.scene
COLL = bpy.data.collections.new("Стол и палатка")
sc.collection.children.link(COLL)
PARTS = bpy.data.collections.new("Разобранная винтовка и реквизит")
sc.collection.children.link(PARTS)
O = bpy.data.objects


# ── общее ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def subtree(name):
    res, st = [], [O[name]]
    while st:
        o = st.pop()
        res.append(o)
        st.extend(o.children)
    return {o for o in res if o.type == "MESH"}


def world_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        if o.type != "MESH":
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        M = np.array(o.matrix_world, dtype=np.float64)
        out.append(co.reshape(-1, 3).astype(np.float64) @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3))


def hull_proxy(name, objs, coll, attach):
    """Выпуклая оболочка деталей objs — тело для физики; attach — что повесить на оболочку (с сохранением положения)."""
    V = world_verts(objs)
    if len(V) > 30000:
        V = V[rng.choice(len(V), 30000, replace=False)]
    cen = V.mean(0)
    bm = bmesh.new()
    for v in V:
        bm.verts.new(v - cen)
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    p = bpy.data.objects.new(name, me)
    coll.objects.link(p)
    p.location = cen
    p.hide_render = True
    p.display_type = "WIRE"
    bpy.context.view_layer.update()
    for o in attach:
        mw = o.matrix_world.copy()
        o.parent = p
        o.matrix_parent_inverse = Matrix()
        o.matrix_world = mw
    bpy.context.view_layer.update()
    return p


def copy_group(objs, coll):
    """Копии деталей (общие сетки) без драйверов механики — для разобранной винтовки и реквизита."""
    out = []
    for o in sorted(objs, key=lambda o: o.name):
        c = o.copy()
        c.animation_data_clear()
        c.parent = None
        c.hide_render = False
        c.hide_set(False)
        coll.objects.link(c)
        c.matrix_world = o.matrix_world.copy()
        out.append(c)
    bpy.context.view_layer.update()
    return out


def pose(p, xy, rot, lift, base=TOP):
    """Тело над поверхностью: поворот вокруг центра оболочки, низ оболочки — на lift выше base."""
    p.matrix_world = Matrix.Translation((xy[0], xy[1], 0.0)) @ rot.to_matrix().to_4x4()
    bpy.context.view_layer.update()
    co = np.array([p.matrix_world @ v.co for v in p.data.vertices])
    p.location.z += base + lift - co[:, 2].min()
    bpy.context.view_layer.update()


def _rb(o, op, **kw):
    with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
        getattr(bpy.ops.rigidbody, op)(**kw)


def simulate(active, passive, frames=150):
    """Жёсткие тела: active падают и ложатся, passive — опора (столешница — коробкой). Положение в конце — без
    физики в файле."""
    if sc.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rbw = sc.rigidbody_world
    rbw.enabled = True
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 40
    rbw.point_cache.frame_start, rbw.point_cache.frame_end = 1, frames
    items = [(o, "ACTIVE", m) for o, m in active] + [(o, "PASSIVE", 1.0) for o in passive]
    for o, kind, mass in items:
        _rb(o, "object_add", type=kind)
        rb = o.rigid_body
        rb.collision_shape = "CONVEX_HULL" if kind == "ACTIVE" else ("BOX" if o.name == "Столешница" else "MESH")
        rb.mass = mass
        rb.friction = 0.8
        rb.restitution = 0.02
        rb.use_margin = True
        rb.collision_margin = 0.0004
        rb.linear_damping, rb.angular_damping = 0.35, 0.6
    sc.frame_start, sc.frame_end = 1, frames
    for f in range(1, frames + 1):
        sc.frame_set(f)
    mats = {o.name: o.matrix_world.copy() for o, _ in active}
    for o, _, _ in items:
        _rb(o, "object_remove")
    bpy.ops.rigidbody.world_remove()
    sc.frame_set(1)
    for o, _ in active:
        o.matrix_world = mats[o.name]
    bpy.context.view_layer.update()


# ── винтовка: что прячется, группы разборки ──────────────────────────────────────────────────────────────────────────
for c in bpy.data.collections:
    if c.name == "Студия просмотра":
        c.hide_render = c.hide_viewport = True
root = O["AR15"]
ctrl = O["AR15_Controls"]
LOOSE = {O["Cartridge_556"], O["Case_556"]}
SUPP = subtree("Suppressor_mover")
for o in SUPP | LOOSE:
    o.hide_render = True
    o.hide_set(True)
bpy.context.view_layer.update()
visible = {o for o in subtree("AR15") if o.visible_get() and not o.hide_render}
up_all = subtree("Upper_group_pivot")
GROUPS = {
    "Верхний ресивер": up_all - subtree("Bolt_carrier_mover") - subtree("Bolt_mover") - subtree("Charging_handle_mover")
    - SUPP,
    "Нижний ресивер с прикладом": subtree("Lower_group") - subtree("Buffer_mover") - subtree("Magazine_mover")
    - {O["Buffer_spring"]} - LOOSE,
    "Затворная рама": {O["Bolt_carrier"], O["Gas_key"], O["Gas_key_screw0"], O["Gas_key_screw1"]},
    "Шплинт ударника": {O["Firing_pin_retainer"]},
    "Затвор": {O["Bolt"], O["Ejector"], O["Extractor"]},
    "Ось затвора": {O["Cam_pin"]},
    "Ударник": {O["Firing_pin"]},
    "Рукоятка заряжания": subtree("Charging_handle_mover"),
    "Буфер": subtree("Buffer_mover"),
    "Возвратная пружина": {O["Buffer_spring"]},
    "Магазин": subtree("Magazine_mover"),
}
GROUPS = {k: {o for o in v if o in visible} for k, v in GROUPS.items()}
GROUPS["Глушитель"] = SUPP
# место (x, y), поворот (вокруг оси винтовки X, затем курс), подъём над столом при сбросе, масса, кг
LAYOUT = {
    "Верхний ресивер": ((0.36, -1.15), (-90, 0, -12), 0.02, 1.5),
    "Нижний ресивер с прикладом": ((0.33, -0.72), (90, 0, 168), 0.02, 1.2),
    "Затворная рама": ((0.73, -0.90), (30, 0, 58), 0.05, 0.3),
    "Шплинт ударника": ((0.83, -0.74), (10, 90, 20), 0.10, 0.01),
    "Затвор": ((0.62, -0.84), (70, 0, 22), 0.08, 0.1),
    "Ось затвора": ((0.70, -0.70), (90, 0, -35), 0.10, 0.01),
    "Ударник": ((0.58, -0.66), (15, 0, 80), 0.09, 0.02),
    "Рукоятка заряжания": ((0.66, -1.07), (0, 0, -28), 0.04, 0.05),
    "Буфер": ((0.86, -1.17), (40, 0, 73), 0.04, 0.09),
    "Возвратная пружина": ((0.70, -1.28), (0, 0, 4), 0.03, 0.05),
    "Магазин": ((-0.04, -0.62), (90, 0, 103), 0.02, 0.45),
    "Глушитель": ((0.02, -1.25), (25, 0, -6), 0.02, 0.5),
}

# ── стол, палатка, реквизит ──────────────────────────────────────────────────────────────────────────────────────────
# палатка с обстановкой строится вокруг начала координат и сдвигается так, чтобы стол стоял в ней у входа (центр стола в
# координатах палатки — (0,15; −0,45)): от входа за столом видны раскладушки, печь, окна
TENT = bpy.data.collections.new("Палатка и обстановка")
sc.collection.children.link(TENT)
TC_TENT = Vector((0.15, -0.45))
T.build_tent(TENT)
T.build_interior(TENT, TC_TENT)
T.lights(TENT, (TC_TENT.x + 0.55, TC_TENT.y + 0.40, 1.80), lamp_energy=50.0)
shift = Vector((TC.x - TC_TENT.x, TC.y - TC_TENT.y, 0.0))
for o in TENT.objects:
    if o.parent is None:
        o.location += shift
bpy.context.view_layer.update()
# столешница полевого стола: фанера темнее, затёрта, с пятнами масла от чистки и грязью (фото-маски CC0)
ply = T.mat_wood("Фанера столешницы", T.PLY, 3.2, value=0.40)
T.overlay(ply, "smear_oil.png", 1.4, (0.45, 0.36, 0.26), 0.85, rough=-0.25)
T.overlay(ply, "grime.png", 2.2, (0.55, 0.50, 0.44), 0.7, rough=0.1, loc=(0.3, 0.6))
legs_m = T.mat_plain("Ножки — олив", (0.07, 0.08, 0.045), 0.5, metal=0.35)
top = T.box(COLL, "Столешница", (TC.x, TC.y, TOP - 0.009), (2 * THX, 2 * THY, 0.018), ply, bevel=0.002)
for sx in (-1, 1):
    for sy in (-1, 1):
        T.tube(COLL, "Ножка стола", (TC.x + sx * (THX - 0.06), TC.y + sy * (THY - 0.06), TOP - 0.018),
               (TC.x + sx * (THX - 0.03), TC.y + sy * (THY - 0.03), 0.0), 0.014, legs_m)
    T.tube(COLL, "Распорка", (TC.x + sx * (THX - 0.05), TC.y - THY + 0.05, 0.25), (TC.x + sx * (THX - 0.05), TC.y + THY - 0.05, 0.25),
           0.01, legs_m)
T.tube(COLL, "Распорка", (TC.x - THX + 0.05, TC.y, 0.25), (TC.x + THX - 0.05, TC.y, 0.25), 0.01, legs_m)
# ветошь под деталями затворной группы: смятая ткань с пятнами нагара и масла (рисунок пятен — фото-маски CC0)
rag_m = T.mat_stained("Ветошь", (0.78, 0.76, 0.70), [("grime.png", 3.0, (0.12, 0.11, 0.10), 0.9),
                                                       ("smear_oil.png", 2.0, (0.45, 0.38, 0.25), 0.8)])
nx, ny = 90, 80
gx, gy = np.meshgrid(np.linspace(-0.17, 0.17, nx), np.linspace(-0.13, 0.13, ny))
r2 = (gx / 0.17) ** 2 + (gy / 0.13) ** 2
crump = 0.009 * np.sin(gx * 61 + 2.5 * np.sin(gy * 37)) * np.sin(gy * 53 + 1.7 * np.sin(gx * 29)) \
    + 0.006 * np.sin(gx * 23 + gy * 31) + 0.005 * np.clip(1 - r2, 0, 1) \
    + 0.0025 * np.sin(gx * 140 + 3 * np.sin(gy * 90)) * np.sin(gy * 120 + 2 * np.sin(gx * 70))
ang = d(18)
X = TC.x + 0.62 + gx * math.cos(ang) - gy * math.sin(ang)
Y = TC.y + 0.05 + gx * math.sin(ang) + gy * math.cos(ang)
rag = T.obj_from(COLL, "Ветошь", np.stack([X, Y, TOP + 0.0015 + np.clip(crump, -0.001, None)], -1).reshape(-1, 3),
                 T.grid(nx, ny), rag_m, uv=np.stack([gx, gy], -1).reshape(-1, 2))
rag.modifiers.new("Толщина", "SOLIDIFY").thickness = 0.0012
# патчи: чистые и в нагаре
patch_m = T.mat_stained("Патч в нагаре", (0.85, 0.84, 0.80), [("grime.png", 9.0, (0.06, 0.06, 0.06), 1.0)])
patch_c = T.mat_canvas("Патч чистый", (0.90, 0.89, 0.86), 18.0, nstrength=1.0)
for k, (px, py, rz, dirty) in enumerate([(0.42, -0.53, 10, True), (0.47, -0.57, 47, True), (0.18, -0.55, -20, False),
                                         (0.88, -0.53, 33, True), (0.23, -0.52, 70, False)]):
    p = T.box(COLL, "Патч", (px, py, TOP + 0.0004), (0.025, 0.025, 0.0007), patch_m if dirty else patch_c, rot_z=d(rz))
# масленка, шомпол из трёх колен, Т-ручка, ёршики, щётка
steel_dark = T.mat_plain("Шомпол — воронёная сталь", (0.05, 0.05, 0.055), 0.35, metal=0.9)
brass = T.mat_plain("Латунь ёршика", (0.70, 0.50, 0.25), 0.45, metal=1.0)
T.lathe(COLL, "Масленка", [(0.0, 0.0), (0.019, 0.0), (0.02, 0.003), (0.02, 0.075), (0.016, 0.085), (0.007, 0.09),
                           (0.007, 0.1), (0.0035, 0.102), (0.002, 0.125), (0.0, 0.126)],
        T.mat_plain("Масленка — пластик", (0.03, 0.06, 0.035), 0.3, coat=0.4), at=(TC.x + 0.80, TC.y + 0.33, TOP))
T.lathe(COLL, "Этикетка", [(0.0202, 0.018), (0.0202, 0.06)], T.mat_plain("Этикетка", (0.65, 0.62, 0.52), 0.6),
        at=(TC.x + 0.80, TC.y + 0.33, TOP))
for k, (x0, y0, yaw) in enumerate([(-0.02, -0.535, 2), (0.20, -0.555, -4), (0.30, -0.585, 9)]):
    ax = Vector((math.cos(d(yaw)), math.sin(d(yaw)), 0))
    p0 = Vector((x0, y0, TOP + 0.003))
    T.tube(COLL, "Колено шомпола", p0, p0 + ax * 0.19, 0.0028, steel_dark, seg=16)
    T.tube(COLL, "Резьба колена", p0 + ax * 0.19, p0 + ax * 0.2, 0.0019, T.mat_plain("Резьба", (0.5, 0.5, 0.5), 0.3, 1.0), seg=12)
T.tube(COLL, "Т-ручка", (-0.21, -0.58, TOP + 0.009), (-0.21 + 0.03, -0.58 + 0.11, TOP + 0.009), 0.009,
       T.mat_plain("Т-ручка", (0.02, 0.02, 0.02), 0.5, coat=0.2), seg=20)
T.tube(COLL, "Ёршик калибровый", (0.53, -0.62, TOP + 0.0045), (0.56, -0.60, TOP + 0.0045), 0.0042, brass, seg=24)
T.tube(COLL, "Стержень ёршика", (0.56, -0.60, TOP + 0.0045), (0.62, -0.565, TOP + 0.0045), 0.0013, brass, seg=10)
T.tube(COLL, "Ёршик патронника", (0.05, -0.76, TOP + 0.0095), (0.085, -0.745, TOP + 0.0095), 0.0095, brass, seg=24)
T.box(COLL, "Щётка — ручка", (-0.62, -0.60, TOP + 0.004), (0.17, 0.012, 0.008), T.mat_plain("Щётка", (0.02, 0.02, 0.02), 0.45),
      bevel=0.002, rot_z=d(-25))
T.box(COLL, "Щётка — ворс", (-0.55, -0.633, TOP + 0.012), (0.03, 0.011, 0.012), T.mat_plain("Ворс", (0.15, 0.15, 0.14), 0.8),
      bevel=0.002, rot_z=d(-25))

# ── разобранная винтовка: копии групп, падают на стол и ветошь ───────────────────────────────────────────────────────
proxies = []
for name, objs in GROUPS.items():
    cp = copy_group(objs, PARTS)
    p = hull_proxy("Оболочка — " + name, cp, PARTS, cp)
    xy, rot, lift, mass = LAYOUT[name]
    pose(p, xy, Euler(tuple(d(v) for v in rot), "XYZ"), lift)
    proxies.append((p, mass))
# россыпь патронов и гильз у магазина
cart_src = O["Cartridge_556"]
case_src = O["Case_556"]
for k, (xy, yaw, src) in enumerate([((-0.20, -0.70), 35, cart_src), ((-0.14, -0.74), -50, cart_src),
                                    ((-0.25, -0.62), 120, cart_src), ((0.12, -0.66), 10, cart_src),
                                    ((0.95, -0.63), 80, case_src), ((-0.10, -0.57), 160, cart_src)]):
    cp = copy_group({src}, PARTS)
    p = hull_proxy("Оболочка — патрон", cp, PARTS, cp)
    pose(p, xy, Euler((d(rng.uniform(0, 360)), 0, d(yaw)), "XYZ"), 0.01 + 0.004 * k)
    proxies.append((p, 0.012))

# собранная винтовка A — на правом боку; на оболочку вешается только корень (механика со своими драйверами внутри)
rifle_vis = {o for o in subtree("AR15") if o.visible_get() and not o.hide_render}
pA = hull_proxy("Оболочка — собранная", rifle_vis, COLL, [root])
pose(pA, (-0.33, -1.00), Euler((d(90), 0, d(6)), "XYZ"), 0.015)
simulate(proxies + [(pA, 3.3)], [top, rag])
print("SIM_A done")

# ── камеры ───────────────────────────────────────────────────────────────────────────────────────────────────────────
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 10
sc.render.resolution_x, sc.render.resolution_y = RX, RY
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast"
sc.view_settings.exposure = 0.8
CAMS = bpy.data.collections.new("Кадры")
sc.collection.children.link(CAMS)


def camera(name, loc, target, lens, fstop):
    cd = bpy.data.cameras.new(name)
    cam = bpy.data.objects.new(name, cd)
    CAMS.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
    cd.lens = lens
    cd.dof.use_dof = True
    cd.dof.focus_distance = (target - loc).length
    cd.dof.aperture_fstop = fstop
    cd.clip_start = 0.01
    return cam


def rifle_view(name, tgt_local, dir_local, dist, lens, fstop):
    """Камера у собранной винтовки: точка и направление — в координатах винтовки (X — к дулу, Y — влево, Z — вверх)."""
    M = root.matrix_world
    t = M @ Vector(tgt_local)
    dv = (M.to_3x3() @ Vector(dir_local)).normalized()
    return camera(name, t + dv * dist, t, lens, fstop)


def render(cam, fname):
    if ONLY and fname.split("_")[0] not in ONLY:
        return
    sc.camera = cam
    sc.render.filepath = os.path.join(OUT_DIR, fname + ".png")
    bpy.ops.render.render(write_still=True)
    print("SHOT", sc.render.filepath)


W = lambda x, y, z: Vector((x, y, z))
DOOR_Y = TC.y - TC_TENT.y - 2.1                           # входная стена в мире
GENERAL = [
    ("01_общий_от_входа", W(TC.x - 0.05, DOOR_Y + 0.18, 1.52), W(TC.x + 0.05, TC.y + 0.05, 0.78), 26, 5.6),
    ("02_общий_слева", W(TC.x - 1.95, TC.y - 0.35, 1.35), W(TC.x + 0.25, TC.y + 0.05, 0.80), 30, 5.6),
    ("03_сверху", W(TC.x, TC.y - 0.30, 2.10), W(TC.x, TC.y, 0.76), 24, 8.0),
    ("04_низко_над_столом", W(TC.x + 1.35, TC.y - 0.15, 0.95), W(TC.x - 0.40, TC.y + 0.10, 0.80), 35, 3.2),
    ("05_через_детали", W(TC.x + 0.95, TC.y + 0.65, 1.05), W(TC.x + 0.45, TC.y, 0.79), 45, 2.8),
]
for name, loc, tgt, lens, f in GENERAL:
    render(camera("Кадр " + name, loc, tgt, lens, f), name)
# крупные и средние планы собранной (левый бок вверх: +Y винтовки — вверх)
CLOSE = [
    ("06_ствольная_коробка", (-0.08, 0, -0.01), (0.15, 1, 0.35), 0.40, 50, 4.0),
    ("07_переводчик_и_надписи", (-0.13, 0.008, -0.026), (0.2, 1, 0.2), 0.19, 60, 7.1),
    ("08_шахта_и_магазин", (-0.02, 0, -0.07), (0.4, 1, -0.25), 0.26, 50, 3.5),
    ("09_рукоять", (-0.15, 0, -0.09), (-0.3, 1, -0.4), 0.22, 50, 3.0),
    ("10_цевьё_к_дулу", (0.20, 0, 0.0), (0.6, 1, 0.3), 0.45, 50, 4.0),
    ("11_дтк", (0.31, 0, 0.0), (0.8, 1, 0.4), 0.16, 60, 5.0),
    ("12_целик_и_рукоятка_заряжания", (-0.17, 0, 0.04), (-0.5, 0.8, 0.6), 0.18, 55, 3.0),
    ("13_мушка", (0.268, 0.0, 0.05), (0.5, 1.0, 0.6), 0.21, 55, 5.6),
    ("14_приклад", (-0.29, 0, -0.03), (-0.3, 1, 0.3), 0.36, 50, 4.0),
    ("15_планка_вдоль", (-0.05, 0, 0.03), (-1.0, 0.45, 0.35), 0.35, 50, 2.8),
    ("16_скоба_и_спуск", (-0.09, 0, -0.06), (0.0, 1, -0.5), 0.15, 60, 3.0),
]
for name, tl, dl, dist, lens, f in CLOSE:
    render(rifle_view("Кадр " + name, tl, dl, dist, lens, f), name)
# средние планы (владелец 30.10: «какие-нибудь кадры не такие крупные, как все остальные»)
MID_A = [
    ("21_собранная_целиком", (-0.02, 0.0, -0.03), (0.05, 1.0, 0.22), 1.05, 50, 5.6),
    ("22_собранная_три_четверти", (0.0, 0.0, -0.03), (0.75, 0.85, 0.35), 0.80, 45, 4.5),
]
for name, tl, dl, dist, lens, f in MID_A:
    render(rifle_view("Кадр " + name, tl, dl, dist, lens, f), name)
both = (root.matrix_world.translation + O["Оболочка — Верхний ресивер"].matrix_world.translation) / 2.0
render(camera("Кадр 23_две_винтовки", both + Vector((0.08, -0.62, 0.62)), both, 35, 5.6), "23_две_винтовки")
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True, relative_remap=True)
print("SAVED", OUT_BLEND)

# ── B: разряжание ────────────────────────────────────────────────────────────────────────────────────────────────────
for c in list(CAMS.objects):
    bpy.data.objects.remove(c, do_unlink=True)
ctrl["charging_handle"] = 1.0
ctrl["ch_latch"] = 1.0
ctrl["dust_cover"] = 1.0
ctrl["mag_out"] = 1.0
ctrl.update_tag()
bpy.context.view_layer.update()
mag_objs = subtree("Magazine_mover")
for o in mag_objs:
    o.hide_render = True
    o.hide_set(True)
root.parent = None
root.matrix_world = Matrix()
bpy.data.objects.remove(pA, do_unlink=True)
bpy.context.view_layer.update()
rifle_vis = {o for o in subtree("AR15") if o.visible_get() and not o.hide_render}
pB = hull_proxy("Оболочка — разряжание", rifle_vis, COLL, [root])
pose(pB, (-0.33, -1.00), Euler((d(-90), 0, d(-4)), "XYZ"), 0.015)
# вынутый магазин — рядом, на боку
mag_cp = copy_group({o for o in mag_objs}, PARTS)
pM = hull_proxy("Оболочка — вынутый магазин", mag_cp, PARTS, mag_cp)
pose(pM, (-0.42, -0.70), Euler((d(-90), 0, d(-70)), "XYZ"), 0.02)
simulate([(pB, 3.0), (pM, 0.45)], [top, rag] + [p for p, _ in proxies])
print("SIM_B done")
# патрон вылетает из окна: два ключа — размытие движения на кадре 10 (выдержка ~1/600 с при 24 к/с ≈ 0,07 кадра)
M = root.matrix_world
flyer = copy_group({cart_src}, PARTS)[0]
c0 = sum((flyer.matrix_world @ Vector(v) for v in flyer.bound_box), Vector()) / 8.0
base = Matrix.Translation(-c0) @ flyer.matrix_world
port = Vector((-0.045, -0.062, 0.012))                    # вылетел из окна на 4 см (правый борт — −Y винтовки)
vel = M.to_3x3() @ Vector((-0.6, -2.4, 0.5))              # вправо-назад-вверх, м/с
bpy.context.preferences.edit.keyframe_new_interpolation_type = "LINEAR"
for f, dt in ((9, -1 / 24), (11, 1 / 24)):
    rot = Matrix.Rotation(d(35) + d(900) * dt * 24 / 10, 4, (M.to_3x3() @ Vector((0, 0, 1))).normalized())
    flyer.matrix_world = Matrix.Translation(M @ port + vel * dt) @ rot @ M.to_3x3().to_4x4() @ \
        Matrix.Rotation(d(20), 4, "Y") @ base
    flyer.keyframe_insert("location", frame=f)
    flyer.keyframe_insert("rotation_euler", frame=f)
sc.frame_set(10)
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.07
DYN = [
    ("17_окно_патрон_вылетает", (-0.04, -0.035, 0.005), (0.35, -1, 0.5), 0.30, 60, 4.0),
    # рама и рукоятка заряжания назад: окно открыто, рама в глубине, рукоятка торчит за коробкой
    ("18_затвор_назад", (-0.11, -0.012, 0.012), (-0.35, -0.85, 0.55), 0.34, 45, 5.6),
    # зеркало затвора с выбрасывателем — у заднего края окна (затвор отошёл на 78 мм), смотреть в окно спереди
    ("20_зеркало_затвора_выбрасыватель", (-0.074, -0.012, 0.002), (0.75, -1.0, 0.15), 0.15, 60, 6.3),
]
for name, tl, dl, dist, lens, f in DYN:
    render(rifle_view("Кадр " + name, tl, dl, dist, lens, f), name)
# магазин вынут: пустая шахта и магазин рядом на столе в одном кадре — сверху над серединой между ними
well = root.matrix_world @ Vector((-0.02, 0.0, -0.05))
mid = (well + pM.matrix_world.translation) / 2.0
render(camera("Кадр 19_магазин_вынут", mid + Vector((0.08, -0.22, 0.50)), mid, 40, 5.6), "19_магазин_вынут")
# рукоятка заряжания оттянута, в открытом окне — затворная рама (владелец 30.10); средний план разряжания целиком
MID_B = [
    ("24_рукоятка_оттянута_окно", (-0.09, -0.015, 0.01), (0.1, -1.0, 0.45), 0.42, 45, 5.6),
    ("25_рукоятка_сзади", (-0.14, -0.005, 0.018), (-0.8, -0.7, 0.6), 0.40, 45, 5.6),
    ("26_разряжание_целиком", (-0.04, -0.01, -0.02), (0.2, -1.0, 0.4), 0.95, 45, 5.6),
]
for name, tl, dl, dist, lens, f in MID_B:
    render(rifle_view("Кадр " + name, tl, dl, dist, lens, f), name)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND_B, compress=True, relative_remap=True)
print("SAVED", OUT_BLEND_B)
