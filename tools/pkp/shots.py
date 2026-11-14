# ПКП: проверочные виды в глине (Workbench) из собранного .blend.
#   blender --background <файл.blend> --python tools/pkp/shots.py -- <папка> [вид,…] [--res 2400] [--pose имя,…]
#       [--hide имя,…] [--show коллекция,…] [--tag приставка]
# Виды ref13 и ref14 — камерами образцов владельца (перспектива и поворот из привязки refmap.py): кадр ложится на
# рендер-образец один в один (compare.py). Свой вид: «имя:x:y:z:куда_x:куда_y:куда_z:ширина_мм[:pNN]» (pNN —
# перспектива с объективом NN мм).
import math
import os
import sys

import bpy
from mathutils import Vector, Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import refmap  # noqa: E402

MM = 0.001
VIEWS = {
    # имя: (откуда, куда, ширина кадра мм)
    "right": ((-80, -3000, -30), (-80, 0, -30), 1240),
    "left": ((-80, 3000, -30), (-80, 0, -30), 1240),
    "top": ((-80, 0, 3000), (-80, 0, 0), 1240),
    "bottom": ((-80, 0, -3000), (-80, 0, 0), 1240),
    "front": ((3000, 0, -40), (0, 0, -40), 420),
    "rear": ((-3000, 0, -40), (0, 0, -40), 420),
    "q_front_r": ((900, -900, 420), (-60, 0, -40), 1150),
    "q_rear_r": ((-1200, -900, 420), (-120, 0, -40), 1150),
    "q_rear_l": ((-1200, 900, 420), (-120, 0, -40), 1150),
    "q_front_l": ((900, 900, 420), (-60, 0, -40), 1150),
    "recv_r": ((-180, -800, 20), (-180, 0, -10), 420),
    "recv_l": ((-180, 800, 20), (-180, 0, -10), 420),
    "stock_r": ((-510, -800, -40), (-510, 0, -45), 330),
    "muzzle_r": ((440, -600, 5), (440, 0, 5), 150),
    "shroud_r": ((150, -700, 10), (150, 0, 5), 340),
    "box_r": ((-103, -800, -140), (-103, 0, -140), 220),
}
POSES = {}


def ref_camera(cam_ob, cam, img):
    """Камера образца: расстояние, поворот вокруг вертикали и главная точка — из привязки refmap.py."""
    eye, tgt, f = refmap.camera(img)
    eye = Vector(eye); tgt = Vector(tgt)
    cam_ob.location = eye * MM
    cam_ob.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
    cam.type = "PERSP"; cam.sensor_fit = "HORIZONTAL"; cam.sensor_width = 36.0
    cam.lens = f * 36.0 / 1920.0
    cam.shift_x = 0.0; cam.shift_y = 0.0
    return 1920, 1080


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    names = None; res = 2400; pose = None; hide = []; show = []; tag = ""
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--res": res = int(argv[i + 1]); i += 2
        elif a == "--pose": pose = argv[i + 1]; i += 2
        elif a == "--hide": hide = argv[i + 1].split(","); i += 2
        elif a == "--show": show = argv[i + 1].split(","); i += 2
        elif a == "--tag": tag = argv[i + 1]; i += 2
        else: names = a.split(","); i += 1
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    vl = bpy.context.view_layer

    def walk(lc):
        yield lc
        for c in lc.children:
            yield from walk(c)
    for lc in walk(vl.layer_collection):
        if lc.name in hide: lc.exclude = True
        if lc.name in show: lc.exclude = False
    for o in bpy.data.objects:
        if o.name in hide: o.hide_render = True
    if pose:
        try:
            import part_rig
            table = part_rig.POSES
        except ImportError:
            table = POSES
        ctrl = bpy.data.objects["PKP_Controls"]
        for pz in pose.split(","):
            for k, val in table[pz].items():
                ctrl[k] = val
        ctrl.update_tag()
        bpy.context.view_layer.update()
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.62, 0.62, 0.64)
    sh.show_specular_highlight = True; sh.show_cavity = True; sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 0.6; sh.curvature_valley_factor = 0.9
    sh.show_shadows = False; sh.show_object_outline = False
    sc.display.render_aa = "16"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.0, 0.0, 0.0)
    sc.render.film_transparent = False
    cam = bpy.data.cameras.new("shot_cam"); co = bpy.data.objects.new("shot_cam", cam)
    sc.collection.objects.link(co); sc.camera = co
    cam.clip_start = 0.05; cam.clip_end = 20.0
    views = dict(VIEWS)
    todo = names or ["right", "left", "top", "front", "rear", "q_front_r", "q_rear_l"]
    for n in todo:
        if n in ("ref13", "ref14"):
            rx, ry = ref_camera(co, cam, n[3:])
            sc.render.resolution_x = rx; sc.render.resolution_y = ry
        else:
            if ":" in n:
                q = n.split(":")
                lens = float(q[8][1:]) if len(q) > 8 and q[8].startswith("p") else 0.0
                views[q[0]] = (tuple(map(float, q[1:4])), tuple(map(float, q[4:7])), float(q[7]), lens); n = q[0]
            loc, tgt, w = views[n][:3]
            lens = views[n][3] if len(views[n]) > 3 else 0.0
            co.location = Vector(loc) * MM
            d = Vector(tgt) - Vector(loc)
            up = "Y" if abs(d.normalized().z) < 0.99 else "X"
            co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
            cam.type = "PERSP" if lens > 0 else "ORTHO"
            cam.ortho_scale = w * MM
            if lens > 0:
                cam.lens = lens; cam.sensor_width = 36.0
            sc.render.resolution_x = res
            sc.render.resolution_y = int(res * (0.42 if w >= 1000 else 0.7))
        sc.render.filepath = os.path.join(out, tag + n + (("_" + pose.replace(",", "_")) if pose else "") + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", sc.render.filepath)


main()
