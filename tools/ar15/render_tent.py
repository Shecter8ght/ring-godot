# AR-15 «ГРАНЬ-15»: рендер для владельца — винтовка лежит на армейской раскладушке в армейской палатке (владелец
# 30.10: «красивый рендер реалистичный, как эта винтовка лежит на армейской раскладушке в армейской палатке»).
# Всё окружение — свои модели здесь же (раскладушка, палатка, фонарь); текстуры — CC0 Poly Haven, уже в проекте
# (лён — npc_kit, фанера — assets/textures, небо — assets/sky).
#   blender -b <файл износа.blend> --python tools/ar15/render_tent.py -- <out.blend> <out.png> [ширина высота сэмплы] [вид]
# Винтовка лежит на правом боку, магазин горизонтально; брезент провисает и продавливается под ней (лунка по
# самым низким точкам винтовки, магазина и патронов). Свет: солнце снаружи через вход и сквозь брезент, тёплый фонарь
# внутри.
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

ROOT = "E:/Games/RING-godot"
LINEN = ROOT + "/_asset_src/npc_kit/tex/rough_linen/rough_linen_"
PLY = ROOT + "/assets/textures/plywood/"
HDRI = ROOT + "/assets/sky/kloppenheim_06_puresky.hdr"

a = sys.argv[sys.argv.index("--") + 1:]
OUT_BLEND, OUT_PNG = a[0], a[1]
RX, RY, SAMPLES = (int(a[2]), int(a[3]), int(a[4])) if len(a) > 4 else (2560, 1440, 512)
VIEW = a[5] if len(a) > 5 else "main"

H = 0.47            # высота брезента у трубок, м
HALF_W = 0.31       # полуширина брезента
HALF_L = 0.95       # полудлина
SAG = 0.03          # провис посередине
YAW = math.radians(-14.0)
TILT = math.radians(-9.0)       # винтовка на правом боку чуть завалена к магазину: лежат и коробка, и магазин
RIFLE_AT = Vector((0.06, -0.05, 0.0))
SINK = 0.007        # насколько винтовка продавливает брезент в самой низкой точке


def sag(x, y):
    """Провисший брезент: парабола поперёк, к торцам меньше (натянут на поперечины)."""
    return H - SAG * (1.0 - (y / HALF_W) ** 2) * (1.0 - 0.6 * (x / HALF_L) ** 2)


# ── материалы ────────────────────────────────────────────────────────────────────────────────────────────────────────
def img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def mat_canvas(name, tint, scale, translucent=0.0, nstrength=0.8):
    """Брезент оливковый: рисунок полотняного переплетения и шероховатость — rough_linen (Poly Haven, CC0), цвет — серый
    рисунка × олива; у палатки — просвет солнца сквозь ткань."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    N.clear()
    out = N.new("ShaderNodeOutputMaterial")
    bs = N.new("ShaderNodeBsdfPrincipled")
    tc = N.new("ShaderNodeTexCoord")
    mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    Lk.new(tc.outputs["UV"], mp.inputs["Vector"])
    diff = N.new("ShaderNodeTexImage"); diff.image = img(LINEN + "diff_2k.jpg")
    rough = N.new("ShaderNodeTexImage"); rough.image = img(LINEN + "rough_2k.png", True)
    nor = N.new("ShaderNodeTexImage"); nor.image = img(LINEN + "nor_gl_2k.png", True)
    for t in (diff, rough, nor):
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    bw = N.new("ShaderNodeRGBToBW")
    Lk.new(diff.outputs["Color"], bw.inputs["Color"])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"; mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    Lk.new(bw.outputs["Val"], mix.inputs[6])
    mix.inputs[7].default_value = (*tint, 1.0)
    gain = N.new("ShaderNodeMath"); gain.operation = "MULTIPLY"; gain.inputs[1].default_value = 2.2
    Lk.new(mix.outputs[2], bs.inputs["Base Color"])
    Lk.new(rough.outputs["Color"], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = nstrength
    Lk.new(nor.outputs["Color"], nm.inputs["Color"])
    Lk.new(nm.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["Specular IOR Level"].default_value = 0.3
    if translucent > 0:
        tr = N.new("ShaderNodeBsdfTranslucent")
        tr.inputs["Color"].default_value = (tint[0] * 2.2, tint[1] * 2.1, tint[2] * 1.7, 1.0)
        Lk.new(nm.outputs["Normal"], tr.inputs["Normal"])
        ms = N.new("ShaderNodeMixShader"); ms.inputs[0].default_value = translucent
        Lk.new(bs.outputs[0], ms.inputs[1]); Lk.new(tr.outputs[0], ms.inputs[2])
        Lk.new(ms.outputs[0], out.inputs["Surface"])
    else:
        Lk.new(bs.outputs[0], out.inputs["Surface"])
    return m


def mat_plywood():
    m = bpy.data.materials.new("Фанера пола")
    m.use_nodes = True
    nt = m.node_tree
    N, Lk = nt.nodes, nt.links
    bs = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); mp = N.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.8, 0.8, 0.8)
    Lk.new(tc.outputs["UV"], mp.inputs["Vector"])
    al = N.new("ShaderNodeTexImage"); al.image = img(PLY + "albedo.jpg")
    arm = N.new("ShaderNodeTexImage"); arm.image = img(PLY + "arm.jpg", True)
    nor = N.new("ShaderNodeTexImage"); nor.image = img(PLY + "normal.jpg", True)
    for t in (al, arm, nor):
        Lk.new(mp.outputs["Vector"], t.inputs["Vector"])
    hue = N.new("ShaderNodeHueSaturation"); hue.inputs["Value"].default_value = 0.55
    Lk.new(al.outputs["Color"], hue.inputs["Color"])
    Lk.new(hue.outputs["Color"], bs.inputs["Base Color"])
    sep = N.new("ShaderNodeSeparateColor")
    Lk.new(arm.outputs["Color"], sep.inputs["Color"])
    Lk.new(sep.outputs["Green"], bs.inputs["Roughness"])
    nm = N.new("ShaderNodeNormalMap")
    Lk.new(nor.outputs["Color"], nm.inputs["Color"])
    Lk.new(nm.outputs["Normal"], bs.inputs["Normal"])
    return m


def mat_metal(name, color, rough):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*color, 1.0)
    bs.inputs["Metallic"].default_value = 1.0
    bs.inputs["Roughness"].default_value = rough
    return m


def mat_emit(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes["Principled BSDF"]
    bs.inputs["Base Color"].default_value = (*color, 1.0)
    bs.inputs["Emission Color"].default_value = (*color, 1.0)
    bs.inputs["Emission Strength"].default_value = strength
    return m


# ── сетки ────────────────────────────────────────────────────────────────────────────────────────────────────────────
COLL = bpy.data.collections.new("Палатка и раскладушка")
bpy.context.scene.collection.children.link(COLL)


def obj_from(name, verts, faces, mat, uv=None, smooth=True):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        loop_uv = np.array([uv[li] for poly in me.polygons for li in poly.vertices], dtype=np.float32)
        layer.data.foreach_set("uv", loop_uv.ravel())
    me.update()
    if smooth:
        me.shade_smooth()
    o = bpy.data.objects.new(name, me)
    o.data.materials.append(mat)
    COLL.objects.link(o)
    return o


def grid(nx, ny):
    faces = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            k = j * nx + i
            faces.append((k, k + 1, k + nx + 1, k + nx))
    return faces


def tube(name, p0, p1, r, mat, seg=24):
    p0, p1 = Vector(p0), Vector(p1)
    d = (p1 - p0)
    q = d.to_track_quat("Z", "Y")
    verts, faces = [], []
    for e, p in enumerate((p0, p1)):
        for s in range(seg):
            ang = 2 * math.pi * s / seg
            verts.append(p + q @ Vector((r * math.cos(ang), r * math.sin(ang), 0.0)))
    for s in range(seg):
        faces.append((s, (s + 1) % seg, seg + (s + 1) % seg, seg + s))
    faces.append(tuple(range(seg))[::-1]); faces.append(tuple(range(seg, 2 * seg)))
    return obj_from(name, verts, faces, mat)


# ── винтовка: положить ───────────────────────────────────────────────────────────────────────────────────────────────
sc = bpy.context.scene
for c in bpy.data.collections:
    if c.name in ("Студия просмотра", "Suppressor"):
        c.hide_render = True
        c.hide_viewport = True
root = bpy.data.objects["AR15"]
loose = [bpy.data.objects[n] for n in ("Cartridge_556", "Case_556") if n in bpy.data.objects]
orig = {o.name: o.matrix_world.copy() for o in bpy.data.objects}
for o in loose:                               # патрон и гильза для показа — отдельно, лягут на брезент
    mw = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = mw
root.rotation_mode = "XYZ"
root.rotation_euler = Euler((math.radians(90.0) + TILT, 0.0, YAW), "XYZ")
root.location = RIFLE_AT
bpy.context.view_layer.update()


def world_verts(objs, mats=None):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        # выключенная коллекция (короткая штатная планка) не пересчитывается — её старое положение давало яму в брезенте
        if o.type != "MESH" or o.hide_render or not o.visible_get() or any(c.hide_render for c in o.users_collection):
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float32)
        me.vertices.foreach_get("co", co)
        ev.to_mesh_clear()
        M = np.array(mats[o.name] if mats else o.matrix_world, dtype=np.float64)
        co = co.reshape(-1, 3).astype(np.float64)
        out.append(co @ M[:3, :3].T + M[:3, 3])
    return np.concatenate(out) if out else np.zeros((0, 3))


def rifle_objs():
    res, stack = [], [root]
    while stack:
        o = stack.pop()
        res.append(o)
        stack.extend(o.children)
    return [o for o in res if o not in loose]


V = world_verts(rifle_objs())
z0 = sag(V[:, 0], V[:, 1])
root.location.z += -(V[:, 2] - z0).min() - SINK
bpy.context.view_layer.update()

# запасной магазин — копии деталей магазина (общие сетки), лежит на боку рядом с цевьём
mag_src = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(("Magazine_", "Magazine_round"))]
place = Matrix.Translation((0.43, 0.165, 0.0)) @ Matrix.Rotation(math.radians(12), 4, "Z") @ \
    Matrix.Rotation(math.radians(-90), 4, "X")
mag_copy = []
for o in mag_src:
    c = o.copy()
    c.parent = None
    c.matrix_world = place @ orig[o.name]
    COLL.objects.link(c)
    mag_copy.append(c)
bpy.context.view_layer.update()
Vm = world_verts(mag_copy)
dzm = -(Vm[:, 2] - sag(Vm[:, 0], Vm[:, 1])).min() - 0.004
for c in mag_copy:
    c.matrix_world = Matrix.Translation((0, 0, dzm)) @ c.matrix_world

# патроны: показной патрон, гильза и ещё два патрона (общая сетка) — россыпью у магазина
props = []
spots = [((-0.02, 0.235), 35), ((0.03, 0.27), -20), ((-0.07, 0.205), 80), ((0.34, 0.25), 150)]
for k, ((px, py), yaw) in enumerate(spots):
    if k < len(loose):
        o = loose[k]
    else:
        o = loose[0].copy()
        COLL.objects.link(o)
    M0 = orig[loose[min(k, len(loose) - 1)].name]
    cen = Vector(M0.translation)
    bb = [M0 @ Vector(v) for v in o.bound_box]
    c0 = sum(bb, Vector()) / 8.0
    o.matrix_world = Matrix.Translation((px, py, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z") @ \
        Matrix.Translation(-c0) @ M0
    props.append(o)
bpy.context.view_layer.update()
for o in props:
    Vp = world_verts([o])
    o.matrix_world = Matrix.Translation((0, 0, -(Vp[:, 2] - sag(Vp[:, 0], Vp[:, 1])).min() - 0.0015)) @ o.matrix_world
bpy.context.view_layer.update()

# ── раскладушка ──────────────────────────────────────────────────────────────────────────────────────────────────────
canvas_m = mat_canvas("Брезент раскладушки", (0.20, 0.19, 0.085), 5.5, nstrength=2.2)
step = 0.003
xs = np.arange(-HALF_L, HALF_L + 1e-6, step)
ys = np.arange(-HALF_W, HALF_W + 1e-6, step)
GX, GY = np.meshgrid(xs, ys)
Z = sag(GX, GY)
# лунка: самые низкие точки всего, что лежит, по клеткам сетки; ткань натянута — лунка расходится конусом
allv = np.concatenate([world_verts(rifle_objs()), world_verts(mag_copy), world_verts(props)])
ix = np.clip(np.round((allv[:, 0] + HALF_L) / step).astype(int), 0, len(xs) - 1)
iy = np.clip(np.round((allv[:, 1] + HALF_W) / step).astype(int), 0, len(ys) - 1)
low = np.full(Z.shape, 9.0)
np.minimum.at(low, (iy, ix), allv[:, 2] - 0.0006)
dep = np.clip(Z - low, 0.0, None)
for _ in range(60):
    d = dep.copy()
    for sy, sx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        d = np.maximum(d, np.roll(np.roll(dep, sy, 0), sx, 1) - 0.22 * step)
    dep = d
for _ in range(3):
    dep = np.maximum(dep, (dep + np.roll(dep, 1, 0) + np.roll(dep, -1, 0) + np.roll(dep, 1, 1) + np.roll(dep, -1, 1)) / 5.0)
edge = np.minimum(np.minimum(GX + HALF_L, HALF_L - GX), np.minimum(GY + HALF_W, HALF_W - GY))
dep *= np.clip(edge / 0.03, 0.0, 1.0)
# складки: вдоль раскладушки — натяжение у лунки (ткань тянется к трубкам), по всему полотну — слабая мятость
pull = np.clip(dep / 0.008, 0.0, 1.0)
for _ in range(25):
    pull = np.maximum(pull, (np.roll(pull, 1, 0) + np.roll(pull, -1, 0) + np.roll(pull, 1, 1) + np.roll(pull, -1, 1)) / 4.6)
# складки от груза — поперёк раскладушки, по натяжению к трубкам (волна вдоль длины ~5 см, извилистые)
folds = 0.0035 * np.sin(GX * 115.0 + 3.0 * np.sin(GY * 9.0) + 2.0 * np.sin(GX * 13.0 + GY * 21.0)) * pull
crumple = 0.0015 * (np.sin(GX * 23.0 + np.sin(GY * 31.0) * 1.7) * np.sin(GY * 19.0 + np.sin(GX * 13.0) * 2.1))     + 0.0007 * np.sin(GX * 61.0 + np.sin(GY * 47.0) * 2.3) * np.sin(GY * 53.0 + np.sin(GX * 37.0) * 1.9)
Z = Z - dep + folds + crumple
verts = np.stack([GX, GY, Z], -1).reshape(-1, 3)
uv = np.stack([(GX + HALF_L), (GY + HALF_W)], -1).reshape(-1, 2)
cot = obj_from("Брезент раскладушки", verts, grid(len(xs), len(ys)), canvas_m, uv=uv)
# трубки и ноги — крашеные в олив (голый алюминий в фоне читался белыми крестами, проба 30.10)
alu = mat_metal("Трубки — олив", (0.07, 0.08, 0.045), 0.45)
alu.node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.35
for s in (-1, 1):
    tube("Чехол трубки", (-HALF_L - 0.02, s * (HALF_W + 0.012), H - 0.006), (HALF_L + 0.02, s * (HALF_W + 0.012), H - 0.006),
         0.019, canvas_m)
    tube("Поперечина", (s * (HALF_L + 0.025), -HALF_W - 0.02, H - 0.03), (s * (HALF_L + 0.025), HALF_W + 0.02, H - 0.03),
         0.013, alu)
for x in (-0.62, 0.0, 0.62):
    for s in (-1, 1):
        tube("Нога", (x, s * (HALF_W + 0.01), H - 0.02), (x, -s * (HALF_W + 0.04), 0.0), 0.011, alu)

# ── палатка ──────────────────────────────────────────────────────────────────────────────────────────────────────────
tent_m = mat_canvas("Брезент палатки", (0.17, 0.165, 0.075), 2.5, translucent=0.28)
TX, TY, WALL, RIDGE = 2.6, 2.1, 1.7, 2.8
DOOR = (-0.55, 0.45, 1.85)           # проём во входной стене (y = −TY): x0, x1, верх


def tent_surface(name, fn, nu, nv, hole=None):
    us, vs = np.linspace(0, 1, nu), np.linspace(0, 1, nv)
    U, Vv = np.meshgrid(us, vs)
    P = fn(U, Vv)
    verts = P.reshape(-1, 3)
    faces = []
    for j in range(nv - 1):
        for i in range(nu - 1):
            k = j * nu + i
            if hole is not None and hole(P[j, i], P[j + 1, i + 1]):
                continue
            faces.append((k, k + 1, k + nu + 1, k + nu))
    uvv = np.stack([U * 4, Vv * 2], -1).reshape(-1, 2)
    return obj_from(name, verts, faces, tent_m, uv=uvv)


rng = np.random.default_rng(7)


def wrinkle(P, amp):
    """Складки и провис брезента между дугами каркаса (шаг 1,3 м)."""
    x = P[..., 0]
    s = amp * (0.5 + 0.5 * np.cos(2 * math.pi * x / 1.3)) + 0.012 * np.sin(x * 9.0 + P[..., 2] * 4.0)
    return s


def wall(side):
    def fn(U, Vv):
        x = -TX + 2 * TX * U
        z = WALL * Vv
        y = np.full_like(x, side * TY)
        P = np.stack([x, y, z], -1)
        P[..., 1] -= side * wrinkle(P, 0.035) * np.sin(math.pi * Vv)
        return P
    hole = None
    if side < 0:
        hole = lambda p0, p1: DOOR[0] < (p0[0] + p1[0]) / 2 < DOOR[1] and (p0[2] + p1[2]) / 2 < DOOR[2]
    return tent_surface("Стена палатки", fn, 120, 40, hole)


def roof(side):
    def fn(U, Vv):
        x = -TX + 2 * TX * U
        y = side * TY * (1 - Vv)
        z = WALL + (RIDGE - WALL) * Vv
        P = np.stack([x, y, z], -1)
        P[..., 2] -= wrinkle(P, 0.05) * np.sin(math.pi * Vv)
        return P
    return tent_surface("Скат крыши", fn, 120, 40)


def gable(sx):
    def fn(U, Vv):
        y = -TY + 2 * TY * U
        top = WALL + (RIDGE - WALL) * (1 - np.abs(y) / TY)
        z = top * Vv
        x = np.full_like(y, sx * TX)
        return np.stack([x, y, z], -1)
    return tent_surface("Торец палатки", fn, 80, 50)


for s in (-1, 1):
    wall(s)
    roof(s)
    gable(s)
# скатанный полог над входом, каркас: стойки и конёк
tube("Скатанный полог", (DOOR[0] - 0.08, -TY + 0.03, DOOR[2] + 0.05), (DOOR[1] + 0.08, -TY + 0.03, DOOR[2] + 0.05), 0.06,
     tent_m)
pole_m = mat_metal("Стойки каркаса", (0.18, 0.19, 0.15), 0.6)
for x in (-1.3, 1.3):
    tube("Стойка", (x, 0.0, 0.0), (x, 0.0, RIDGE - 0.03), 0.02, pole_m)
tube("Конёк", (-TX, 0.0, RIDGE - 0.04), (TX, 0.0, RIDGE - 0.04), 0.018, pole_m)
floor = obj_from("Пол", [(-TX, -TY, 0), (TX, -TY, 0), (TX, TY, 0), (-TX, TY, 0)], [(0, 1, 2, 3)], mat_plywood(),
                 uv=np.array([(0, 0), (2 * TX, 0), (2 * TX, 2 * TY), (0, 2 * TY)]), smooth=False)
ground = obj_from("Земля снаружи", [(-30, -30, -0.002), (30, -30, -0.002), (30, 30, -0.002), (-30, 30, -0.002)],
                  [(0, 1, 2, 3)], mat_metal("Земля", (0.12, 0.10, 0.07), 0.9), smooth=False)
ground.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.0
# одеяло в ногах раскладушки (сложенное, шерсть) — простой брус со скруглением
blanket_m = mat_canvas("Одеяло", (0.12, 0.12, 0.09), 3.0)
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-0.72, 0.0, H + 0.03))
bl = bpy.context.active_object
bl.name = "Одеяло"
bl.scale = (0.32, 0.56, 0.07)
bl.rotation_euler = (0, 0, math.radians(4))
for c in bl.users_collection:
    c.objects.unlink(bl)
COLL.objects.link(bl)
bv = bl.modifiers.new("Скругление", "BEVEL"); bv.width = 0.025; bv.segments = 4
bl.data.materials.append(blanket_m)
bl.modifiers.new("Сглаживание", "SUBSURF").levels = 2

# фон (в размытии): вторая раскладушка у стены со скатанным спальником, ящик из фанеры, вещмешок
def cot_frame(cx, cy, name):
    top = obj_from(name, [(cx - HALF_L, cy - HALF_W, H - 0.02), (cx + HALF_L, cy - HALF_W, H - 0.02),
                          (cx + HALF_L, cy + HALF_W, H - 0.02), (cx - HALF_L, cy + HALF_W, H - 0.02)],
                   [(0, 1, 2, 3)], canvas_m, uv=np.array([(0, 0), (1.9, 0), (1.9, 0.62), (0, 0.62)]), smooth=False)
    for s_ in (-1, 1):
        tube(name + " трубка", (cx - HALF_L, cy + s_ * HALF_W, H - 0.02), (cx + HALF_L, cy + s_ * HALF_W, H - 0.02), 0.019,
             canvas_m)
        for x in (-0.62, 0.0, 0.62):
            tube(name + " нога", (cx + x, cy + s_ * HALF_W, H - 0.03), (cx + x, cy - s_ * (HALF_W + 0.03), 0.0), 0.011, alu)
    return top


cot_frame(0.3, -1.55, "Вторая раскладушка")
tube("Скатанный спальник", (-0.45, -1.84, H + 0.09), (-0.45, -1.26, H + 0.09), 0.11,
     mat_canvas("Спальник", (0.10, 0.11, 0.07), 3.0))
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(1.45, -0.95, 0.19))
crate = bpy.context.active_object
crate.name = "Ящик"
crate.scale = (0.62, 0.38, 0.38)
crate.rotation_euler = (0, 0, math.radians(-12))
crate.data.materials.append(mat_plywood())
cb = crate.modifiers.new("Скругление", "BEVEL"); cb.width = 0.008; cb.segments = 2
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(-1.35, -1.05, 0.2))
bag = bpy.context.active_object
bag.name = "Вещмешок"
bag.scale = (0.55, 0.32, 0.38)
bag.data.materials.append(mat_canvas("Вещмешок", (0.13, 0.13, 0.07), 3.0, nstrength=1.5))
for o in (crate, bag):
    for c in o.users_collection:
        c.objects.unlink(o)
    COLL.objects.link(o)

# ── свет ─────────────────────────────────────────────────────────────────────────────────────────────────────────────
world = bpy.data.worlds.new("Палатка — небо")
sc.world = world
world.use_nodes = True
wn = world.node_tree.nodes
env = wn.new("ShaderNodeTexEnvironment"); env.image = img(HDRI)
world.node_tree.links.new(env.outputs["Color"], wn["Background"].inputs["Color"])
wn["Background"].inputs["Strength"].default_value = 1.0
sun_d = bpy.data.lights.new("Солнце", "SUN")
sun_d.energy = 3.5
sun_d.angle = math.radians(2.5)
sun_d.color = (1.0, 0.86, 0.70)
# солнце — сбоку сверху на крышу и стену (брезент просвечивает), в проём входа не заходит: косое пятно солнца с резкими
# краями от проёма на брезенте раскладушки читалось дырой (проба 30.10)
sun = bpy.data.objects.new("Солнце", sun_d)
COLL.objects.link(sun)
d = Vector((-0.62, 0.22, -0.75)).normalized()
sun.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
lamp_d = bpy.data.lights.new("Фонарь", "POINT")
lamp_d.energy = 70.0
lamp_d.shadow_soft_size = 0.02
lamp_d.color = (1.0, 0.82, 0.62)
lamp = bpy.data.objects.new("Фонарь", lamp_d)
lamp.location = (0.55, 0.9, 1.75)
COLL.objects.link(lamp)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.035, location=lamp.location)
bulb = bpy.context.active_object
bulb.name = "Колба фонаря"
bulb.data.materials.append(mat_emit("Колба", (1.0, 0.75, 0.45), 6.0))
bulb.visible_shadow = False
# мягкий свет от входа на винтовку (дневной, холоднее) — светлый проём за раскладушкой
fill_d = bpy.data.lights.new("Свет от входа", "AREA")
fill_d.energy = 200.0
fill_d.size = 1.0
fill_d.size_y = 1.8
fill_d.shape = "RECTANGLE"
fill_d.color = (0.92, 0.96, 1.0)
fill = bpy.data.objects.new("Свет от входа", fill_d)
fill.location = (-0.05, -TY + 0.05, 0.95)
fill.rotation_euler = (math.radians(90), 0, 0)
COLL.objects.link(fill)

# ── камера ───────────────────────────────────────────────────────────────────────────────────────────────────────────
target = root.matrix_world @ Vector((-0.07, 0.0, -0.02))
VIEWS = {"main": (Vector((-0.42, 0.95, 0.42)), 58.0, 2.8),
         "low": (Vector((0.45, 0.55, 0.18)), 55.0, 2.0),
         "top": (Vector((-0.05, 0.20, 0.95)), 45.0, 3.5)}
off, lens, fstop = VIEWS[VIEW]
cam_d = bpy.data.cameras.new("Камера палатки")
cam = bpy.data.objects.new("Камера палатки", cam_d)
COLL.objects.link(cam)
cam.location = target + off
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam_d.lens = lens
cam_d.dof.use_dof = True
cam_d.dof.focus_distance = (target - cam.location).length
cam_d.dof.aperture_fstop = fstop
sc.camera = cam

sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_denoising = True
sc.cycles.max_bounces = 10
sc.render.resolution_x, sc.render.resolution_y = RX, RY
sc.render.resolution_percentage = 100
sc.view_settings.view_transform = "AgX"
sc.view_settings.look = "AgX - Base Contrast"
sc.view_settings.exposure = float(os.environ.get("EXPOSURE", "0.8"))
sc.render.filepath = OUT_PNG
bpy.context.preferences.filepaths.save_version = 0
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True, relative_remap=True)
print("SAVED", OUT_BLEND)
if os.environ.get("NO_RENDER") != "1":
    bpy.ops.render.render(write_still=True)
    print("RENDERED", OUT_PNG)
