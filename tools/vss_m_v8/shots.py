# Проверочные снимки v8 (Workbench, глина/материал): -- <out_dir> <вид,вид,...> [ширина] [режим: clay|mat]
# Виды задаются здесь: имя → (точка камеры мм, цель мм, фокус мм) или "ortho_*".
import math
import os
import sys
import bpy
from mathutils import Vector

VIEWS = {
    "right": ((447, -1400, 10), (447, 0, -20), 70, True),
    "left": ((447, 1400, 10), (447, 0, -20), 70, True),
    "top": ((447, 0, 1400), (447, 0, 0), 70, True),
    "r34": ((700, -620, 260), (430, 0, -10), 50, False),
    "l34": ((260, 600, 220), (450, 0, -10), 50, False),
    "receiver_r": ((420, -330, 60), (400, 0, -5), 60, False),
    "receiver_l": ((420, 330, 60), (400, 0, -5), 60, False),
    "receiver_top_r": ((440, -230, 170), (420, 0, 10), 60, False),
    "trigger_r": ((380, -170, -40), (380, 0, -25), 60, False),
    "trigger_under": ((390, -90, -200), (390, 0, -30), 60, False),
    "front_r": ((640, -330, 90), (620, 0, 10), 60, False),
    "front_l": ((640, 330, 90), (620, 0, 10), 60, False),
    "muzzle": ((1060, -140, 70), (880, 0, 10), 60, False),
    "rear": ((-200, -160, 110), (150, 0, -20), 50, False),
    "mag": ((480, -260, -90), (450, 0, -60), 60, False),
    "mag_top": ((470, -120, 160), (450, 0, -10), 60, False),
    "sight": ((560, -160, 110), (610, 0, 35), 60, False),
    "sleeve_under": ((620, -200, -170), (615, 0, 0), 60, False),
    "stamp_r": ((446, -90, -8), (446, 0, -8), 60, False),
    "stamp_plate": ((424, -70, 10), (424, 0, 9), 60, False),
    "leaf_top": ((606, -20, 90), (606, 0, 38), 70, False),
    "joint_r": ((330, -220, -40), (320, 0, -40), 55, False),
    "joint_under": ((340, -120, -230), (330, 0, -40), 50, False),
    "joint_rear": ((150, -160, 40), (300, 0, -20), 50, False),
    "grip_back": ((250, -60, -120), (330, 0, -70), 50, False),
    "top_widths": ((450, 0, 900), (450, 0, 0), 60, False),
    "front_view": ((1400, 0, 10), (450, 0, 0), 60, False),
    "sight_picture": ((120, 0, 54.9), (879.5, 0, 55.4), 160, False),
    "rear_corner": ((200, -200, 130), (300, 0, 15), 50, False),
    "rear_side": ((290, -330, 20), (300, 0, 10), 55, False),
    "handle_top": ((470, -140, 160), (465, -15, 8), 55, False),
    "safety_r": ((378, -150, 4), (378, 0, -6), 60, False),
    "safety_low": ((440, -95, -45), (385, -20, -6), 50, False),
    "nameplate": ((356, -115, 22), (356, 0, 19), 60, False),
    "selector_front": ((430, -70, -52), (358, 0, -44), 45, False),
    "selector_r": ((356, -90, -50), (356, 0, -44), 55, False),
    "handle_side": ((470, -260, 10), (462, 0, 8), 55, False),
    "sight_side": ((610, -400, 50), (615, 0, 30), 55, False),
    "handle_top2": ((472, -28, 140), (472, -28, 7), 50, False),
    "handle_34": ((520, -120, 60), (472, -28, 7), 55, False),
}


def look(cam, eye, tgt):
    d = (Vector(tgt) - Vector(eye))
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out, views = a[0], a[1].split(",")
    w = int(a[2]) if len(a) > 2 else 1280
    mode = a[3] if len(a) > 3 else "clay"
    frame = int(a[4]) if len(a) > 4 else 1
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    sc.frame_set(frame)
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
            cd.type = "ORTHO"; cd.ortho_scale = 0.98
        else:
            cd.type = "PERSP"; cd.lens = lens
        cd.clip_start = 0.005
        sc.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)


main()
