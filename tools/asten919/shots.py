# АСТЕН-919: проверочные виды в глине (Workbench, ортография) из собранного .blend.
#   blender --background <файл.blend> --python tools/asten919/shots.py -- <папка> [вид,…] [--res 1800] [--pose имя]
#       [--hide имя,…] [--show коллекция,…] [--tag приставка]
# Позы: slide_back (затвор на задержке), mag_out (магазин вынут), trigger, catch, lock (можно несколько через запятую).
# Свой вид: «имя:x:y:z:куда_x:куда_y:куда_z:ширина_мм»; с девятым полем «pNN» — камера с перспективой, объектив NN мм
# (ширина тогда только задаёт формат кадра): вид глазами стрелка вдоль прицельной линии и т. п.
import math
import os
import sys

import bpy
from mathutils import Vector

MM = 0.001
VIEWS = {
    # имя: (откуда, куда, ширина кадра мм)
    "left": ((20, 400, -55), (20, 0, -55), 230),
    "right": ((20, -400, -55), (20, 0, -55), 230),
    "top": ((20, 0, 400), (20, 0, 0), 230),
    "bottom": ((20, 0, -500), (20, 0, 0), 230),
    "front": ((500, 0, -55), (0, 0, -55), 170),
    "rear": ((-500, 0, -55), (0, 0, -55), 170),
    "q_front_l": ((330, 280, 120), (20, 0, -50), 240),
    "q_rear_r": ((-300, -300, 140), (20, 0, -50), 240),
    "q_rear_l": ((-300, 300, 140), (20, 0, -50), 240),
    "q_low_r": ((260, -300, -220), (20, 0, -50), 240),
    "controls_l": ((-10, 300, 60), (-5, 0, -28), 95),
    "controls_r": ((-10, -300, 60), (-5, 0, -28), 95),
    "stop": ((-60, 200, 40), (-15, 13, -15), 45),
    "catch": ((60, 200, -20), (-17, 15, -45), 50),
    "lock": ((120, 200, 30), (28, 13, -18), 45),
    "trigger": ((120, 200, -80), (8, 0, -40), 70),
    "muzzle": ((300, 90, 30), (112, 0, -8), 60),
    "port": ((40, -220, 160), (14, -4, 4), 80),
    "rearsight": ((-250, 60, 90), (-66, 0, 8), 60),
    "sight_picture": ((-600, 0, 14.6), (100, 0, 14.6), 60),
    "magwell": ((-140, -90, -330), (-55, 0, -118), 90),
    "grip_l": ((-40, 300, -60), (-45, 0, -75), 120),
    "grip_back": ((-400, 80, -40), (-70, 0, -70), 120),
    "grip_front": ((300, 120, -160), (-25, 0, -80), 120),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    names = None; res = 1800; pose = None; hide = []; show = []; tag = ""
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
        # позы — ползунками пустышки управления (приводы из assemble.py)
        ctrl = bpy.data.objects["ASTEN919_Controls"]
        table = {"slide_back": {"slide": 1.0, "stop": 1.0}, "mag_out": {"mag_out": 1.0}, "trigger": {"trigger": 1.0, "trigger_safety": 1.0},
                 "catch": {"mag_catch": 1.0}, "lock": {"slide_lock": 1.0}}
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
    sc.world.color = (0.25, 0.25, 0.26)
    cam = bpy.data.cameras.new("shot_cam"); co = bpy.data.objects.new("shot_cam", cam)
    sc.collection.objects.link(co); sc.camera = co
    cam.type = "ORTHO"; cam.clip_start = 0.01; cam.clip_end = 5.0
    views = dict(VIEWS)
    todo = names or list(VIEWS)
    for n in todo:
        if ":" in n:
            q = n.split(":")
            lens = float(q[8][1:]) if len(q) > 8 and q[8].startswith("p") else 0.0
            views[q[0]] = (tuple(map(float, q[1:4])), tuple(map(float, q[4:7])), float(q[7]), lens); n = q[0]
        loc, tgt, w = views[n][:3]
        lens = views[n][3] if len(views[n]) > 3 else 0.0
        co.location = Vector(loc) * MM
        d = Vector(tgt) - Vector(loc)
        co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cam.type = "PERSP" if lens > 0 else "ORTHO"
        cam.ortho_scale = w * MM
        if lens > 0:
            cam.lens = lens; cam.sensor_width = 36.0
        sc.render.resolution_x = res
        sc.render.resolution_y = int(res * (0.62 if w >= 150 else 0.75))
        sc.render.filepath = os.path.join(out, tag + n + (("_" + pose.replace(",", "_")) if pose else "") + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", sc.render.filepath)


main()
