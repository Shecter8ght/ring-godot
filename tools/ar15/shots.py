# Проверочные снимки AR-15 (Workbench, глина или материал). Запуск на сохранённом .blend:
# blender -b <file.blend> --python tools/ar15/shots.py -- <out_dir> <вид,вид,...> [ширина] [clay|mat] [свойство=значение;...] [скрыть коллекции через +]
# Виды: имя → (камера мм, цель мм, фокус мм | ortho_scale м, орто).
import os
import sys
import bpy
from mathutils import Vector

VIEWS = {
    "right": ((20, -1500, -20), (20, 0, -20), 1.0, True),
    "left": ((20, 1500, -20), (20, 0, -20), 1.0, True),
    "top": ((-60, 0, 1500), (-60, 0, 0), 0.98, True),
    "front": ((1500, 0, -40), (0, 0, -40), 0.4, True),
    "back": ((-1500, 0, -40), (0, 0, -40), 0.4, True),
    "recv_right": ((-80, -1500, -20), (-80, 0, -20), 0.32, True),
    "recv_left": ((-80, 1500, -20), (-80, 0, -20), 0.32, True),
    "recv_top": ((-80, 0, 1500), (-80, 0, 0), 0.32, True),
    "r34": ((260, -520, 200), (-70, 0, -30), 50, False),
    "l34": ((-330, 520, 180), (-40, 0, -30), 50, False),
    "recv_r34": ((60, -260, 120), (-80, 0, -10), 50, False),
    "recv_l34": ((-200, 260, 110), (-70, 0, -10), 50, False),
    "recv_under": ((-60, -160, -260), (-70, 0, -20), 45, False),
    "recv_rear34": ((-330, -160, 120), (-120, 0, 0), 45, False),
    "port": ((-20, -170, 40), (-30, 0, 8), 55, False),
    "trigger": ((-80, -170, -60), (-85, 0, -45), 55, False),
    "fcg_top": ((-60, -90, 140), (-95, 0, -20), 50, False),
    "bcg": ((40, -200, 90), (-80, 0, 5), 45, False),
    "front_r34": ((380, -260, 120), (220, 0, 0), 50, False),
    "muzzle": ((560, -160, 70), (330, 0, 0), 50, False),
    "stock": ((-300, -260, 60), (-300, 0, -20), 50, False),
    "mag": ((60, -260, -120), (-20, 0, -110), 50, False),
    "hg_front_l34": ((400, 200, 60), (230, 0, -5), 50, False),
    "hg_under": ((200, -160, -200), (160, 0, -20), 45, False),
    "hg_front": ((520, -60, 30), (280, 0, 0), 50, False),
    "catch_l": ((-30, 150, -10), (-62, 0, -8), 55, False),
    "catch_front": ((60, 60, 10), (-62, 6, -6), 45, False),
    "upper_bottom": ((-60, -120, -260), (-70, 0, 0), 40, False),
    "sight_picture": ((-330, 0, 64.0), (300, 0, 64.0), 110, False),
    "full_r34": ((620, -1150, 300), (20, 0, -40), 50, False),
    "full_l34": ((-560, 1150, 280), (40, 0, -40), 50, False),
}


def look(cam, eye, tgt):
    d = (Vector(tgt) - Vector(eye))
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out, views = a[0], a[1].split(",")
    w = int(a[2]) if len(a) > 2 else 1280
    mode = a[3] if len(a) > 3 else "clay"
    sets = a[4] if len(a) > 4 else ""
    hide = a[5].split("+") if len(a) > 5 and a[5] else []
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    ctrl = bpy.data.objects.get("AR15_Controls")
    if ctrl is not None and sets:
        for kv in sets.split(";"):
            if "=" in kv:
                k, val = kv.split("=")
                ctrl[k] = float(val)
    for name in hide:
        c = bpy.data.collections.get(name)
        if c is not None:
            c.hide_render = True
    sc.frame_set(1)
    bpy.context.view_layer.update()
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE" if mode == "clay" else "MATERIAL"
    sh.single_color = (0.62, 0.62, 0.64)
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 0.6
    sh.show_shadows = False
    sh.show_specular_highlight = True
    sc.render.resolution_x = w
    sc.render.resolution_y = int(w * 0.5625)
    sc.view_settings.view_transform = "Standard"
    cd = bpy.data.cameras.new("ShotCam")
    cam = bpy.data.objects.new("ShotCam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for name in views:
        eye, tgt, lens, ortho = VIEWS[name]
        cam.location = Vector(eye) * 0.001
        look(cam, Vector(eye) * 0.001, Vector(tgt) * 0.001)
        if ortho:
            cd.type = "ORTHO"; cd.ortho_scale = lens
        else:
            cd.type = "PERSP"; cd.lens = lens
        cd.clip_start = 0.005
        sc.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)


main()
