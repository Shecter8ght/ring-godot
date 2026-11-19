"""ВЕРАС-54, разведка: кадры наложения новой игровой сетки v14 на хваты владельца (Workbench, без Cycles).

Только чтение: КОПИЯ файла клипов, новая сетка — в память, файл не сохраняется.
blender -b <копия файла клипов.blend> --factory-startup --python tools/veras54_v14/clips_port/shots.py -- <VERAS54_Game_LP.blend> <папка кадров> [имя …]

Каждый кадр — три панели: слева руки и СТАРАЯ сетка (серая), посередине руки и НОВАЯ (голубая), справа старая с наложенной
новой (голубой полупрозрачной заливкой и контуром).
"""
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "clips"))
sys.path.insert(0, str(HERE))
import clip_tools as CT  # noqa: E402
import newmesh  # noqa: E402

args = sys.argv[sys.argv.index("--") + 1:]
LP, OUTD = args[0], Path(args[1])
ONLY = set(args[2:])
OUTD.mkdir(parents=True, exist_ok=True)
log = lambda *a: print("SHOT", *a, flush=True)  # noqa: E731
S = bpy.context.scene
arms, wr = CT.rigs()
root = bpy.data.objects["VERAS54"]
glove = bpy.data.objects["FPS_Arms"]
fps_cam = bpy.data.objects["FPS • Camera"]
for ob in (arms, wr, root, bpy.data.objects["Magazine"]):
    if ob.animation_data:
        ob.animation_data.action = None
for pb in wr.pose.bones:
    pb.matrix_basis = Matrix.Identity(4)
for n in ("SpareMag", "JamCase", "Suppressor_Control"):
    wr.pose.bones[n].scale = (0.001,) * 3
bpy.context.view_layer.update()
NEW = newmesh.place(LP, wr, S)
new_objs = [o for o in NEW.values() if o.type == "MESH"]
OLD_COLLS = ("VERAS54 v13 • игровая сетка", "Магазин 30 (штатный)")
old_objs = [o for c in OLD_COLLS for o in bpy.data.collections[c].objects if o.type == "MESH"]
old_objs += [bpy.data.objects["Magazine_Follower"]] if bpy.data.objects["Magazine_Follower"] not in old_objs else []
everything = [o for o in bpy.data.objects if o.type == "MESH"]

S.render.engine = "BLENDER_WORKBENCH"
S.render.resolution_x, S.render.resolution_y = 960, 720
S.render.resolution_percentage = 100
S.render.image_settings.file_format = "PNG"
S.render.image_settings.color_mode = "RGBA"
sh = S.display.shading
sh.light = "STUDIO"
sh.color_type = "OBJECT"
sh.show_cavity = True
sh.cavity_type = "WORLD"
sh.show_object_outline = False
sh.show_shadows = False
S.display_settings.display_device = "sRGB"
S.view_settings.view_transform = "Standard"
for o in old_objs:
    o.color = (0.55, 0.55, 0.55, 1)
for o in new_objs:
    o.color = (0.25, 0.75, 0.95, 1)
glove.color = (0.80, 0.62, 0.48, 1)

cam_ob = bpy.data.objects.new("_shot_cam", bpy.data.cameras.new("_shot_cam"))
S.collection.objects.link(cam_ob)


def wr_point(p_mm):
    return wr.matrix_world @ (Vector(p_mm) / 1000.0)


def look(cam, eye, target, up):
    f = (target - eye).normalized()
    r = f.cross(up).normalized()
    u = r.cross(f)
    cam.matrix_world = Matrix(((r.x, u.x, -f.x, eye.x), (r.y, u.y, -f.y, eye.y), (r.z, u.z, -f.z, eye.z), (0, 0, 0, 1)))


def set_pose(frame):
    poses = bpy.data.actions[CT.POSES]
    for ob in (arms, wr):
        ad = ob.animation_data or ob.animation_data_create()
        ad.action = poses
        ad.action_slot = CT.slot_of(poses, ob)
    S.frame_set(frame)
    bpy.context.view_layer.update()


def show(objs):
    vis = set(objs)
    for o in everything:
        o.hide_render = o not in vis


def render(path, transparent=False):
    S.render.film_transparent = transparent
    S.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(str(path), check_existing=False)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(img.size[1], img.size[0], 4)
    bpy.data.images.remove(img)
    return a


def edge(m):
    e = np.zeros_like(m)
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (0, 2)):
        e |= m & ~np.roll(np.roll(m, dy, 0), dx, 1)
    return e


def shot(name, frame, cam_fn, hands=True, variant=None):
    if ONLY and name not in ONLY:
        return
    set_pose(frame)
    v = variant or CT.POSE_VARIANT.get(next((k for k, f in CT.POSE_FRAMES.items() if f == frame), ""), {})
    CT.show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    cam_fn(cam_ob)
    S.camera = cam_ob
    tmp = OUTD / "_tmp"
    tmp.mkdir(exist_ok=True)
    h = [glove] if hands else []
    show(old_objs + h)
    A = render(tmp / f"{name}_A.png")
    show(new_objs + h)
    C = render(tmp / f"{name}_C.png")
    show(new_objs)
    B = render(tmp / f"{name}_B.png", transparent=True)
    show(old_objs)
    O = render(tmp / f"{name}_O.png", transparent=True)
    m = B[:, :, 3] > 0.5
    mo = O[:, :, 3] > 0.5
    D = A.copy()
    tint = np.array([0.2, 0.75, 1.0, 1.0], dtype=np.float32)
    D[m] = D[m] * 0.55 + tint * 0.45
    D[edge(m)] = tint
    D[edge(mo)] = np.array([1.0, 0.35, 0.1, 1.0], dtype=np.float32)   # контур старой — оранжевый
    H, W = A.shape[:2]
    gap = np.ones((H, 6, 4), dtype=np.float32)
    full = np.concatenate([A, gap, C, gap, D], axis=1)
    full[:, :, 3] = 1.0
    img = bpy.data.images.new(name, full.shape[1], full.shape[0], alpha=True)
    img.pixels = full.ravel()
    img.filepath_raw = str(OUTD / f"{name}.png")
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)
    log("кадр", OUTD / f"{name}.png")


def fps(cam):
    cam.data = fps_cam.data
    cam.matrix_world = fps_cam.matrix_world.copy()


def ortho(target_mm, eye_dir, up_local, scale, dist=0.6):
    def fn(cam):
        cam.data = bpy.data.cameras.new("_o")
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = scale
        cam.data.clip_start, cam.data.clip_end = 0.01, 5.0
        t = wr_point(target_mm)
        d = (wr.matrix_world.to_3x3() @ Vector(eye_dir)).normalized()
        up = (wr.matrix_world.to_3x3() @ Vector(up_local)).normalized()
        look(cam, t + d * dist, t, up)
    return fn


def mag_target_mm():
    """Середина старого магазина в осях рига оружия на текущем кадре."""
    mb = bpy.data.objects["Magazine_Body"]
    dg = bpy.context.evaluated_depsgraph_get()
    e = mb.evaluated_get(dg)
    c = sum((e.matrix_world @ Vector(v) for v in e.bound_box), Vector()) / 8
    return list((wr.matrix_world.inverted() @ c) * 1000)


def mag_cam(cam):
    set_pose(41)
    t = mag_target_mm()
    ortho(t, (0.25, 1.0, -0.35), (0, 0, 1), 0.30)(cam)


def sight(cam):
    cam.data = bpy.data.cameras.new("_s")
    cam.data.type = "PERSP"
    cam.data.lens = 300
    cam.data.sensor_fit = "VERTICAL"
    cam.data.clip_start, cam.data.clip_end = 0.01, 5.0
    look(cam, wr_point((-120, 0, 58.2)), wr_point((518, 0, 58.2)), wr.matrix_world.to_3x3() @ Vector((0, 0, 1)))


shot("01_hvat_kadr1_kamera_igry", 1, fps)
shot("02_hvat_kadr1_pravaya_sboku", 1, ortho((60, 0, -80), (0, -1, 0), (0, 0, 1), 0.26))
shot("03_hvat_kadr1_levaya_snizu", 1, ortho((345, 0, -5), (0.15, 0.75, -0.65), (0, 0, 1), 0.26))
shot("04_poza41_levaya_s_magazinom", 41, mag_cam)
shot("05_poza36_kryuk_na_rukoyatke", 36, ortho((232, -40, 12), (0.3, -1.0, 0.35), (0, 0, 1), 0.20))
shot("06_liniya_pricela", 1, sight, hands=False)
shot("07_poza41_kamera_igry", 41, fps)
# сверка совмещения: задний торец коробки, ось ствола (по кадрам и в лог)
dg = bpy.context.evaluated_depsgraph_get()
for label, objs in (("old", old_objs), ("new", new_objs)):
    xs = []
    for o in objs:
        if o.name.startswith(("Body", "Receiver")):
            e = o.evaluated_get(dg)
            me = e.to_mesh()
            M = wr.matrix_world.inverted() @ e.matrix_world
            for v in me.vertices:
                p = M @ v.co
                if abs(p.y) < 0.012 and -0.02 < p.z < 0.03 and p.x < 0.05:
                    xs.append(p.x)
            e.to_mesh_clear()
    log("задний торец коробки", label, round(min(xs) * 1000, 1) if xs else None)
