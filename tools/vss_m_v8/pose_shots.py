# Снимки v8 в позах управления: -- <out_dir> <ширина> <поза;поза;...>
# поза = имя:вид:свойство=значение,свойство=значение[:hide=префикс|префикс][:mat]
import os
import sys
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib.util
spec = importlib.util.spec_from_file_location("shots_views", os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots.py"))

VIEWS = {
    "receiver_r": ((420, -330, 60), (400, 0, -5), 60),
    "window": ((440, -170, 40), (440, 0, 8), 60),
    "window_top": ((450, -120, 140), (445, 0, 5), 60),
    "trigger_r": ((380, -170, -40), (380, 0, -25), 60),
    "side": ((447, -1400, 10), (447, 0, -20), 70),
    "mag_cut": ((460, -260, -60), (450, 0, -50), 55),
    "mag_cut_front": ((560, -150, 60), (450, 0, -40), 45),
    "mag_out": ((520, -480, -60), (450, 0, -60), 50),
    "r34": ((700, -620, 260), (430, 0, -10), 50),
    "rear_sight": ((540, -120, 80), (610, 0, 38), 70),
    "breech_l": ((440, 170, 40), (440, 0, 8), 60),
    "safety": ((392, -150, 14), (390, 0, 0), 60),
    "rear_top": ((215, -85, 75), (279, 0, 18), 50),
    "selector_u": ((362, -60, -95), (358, 0, -44), 50),
}


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out, w, poses = a[0], int(a[1]), a[2].split(";")
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.show_cavity = True; sh.cavity_type = "BOTH"
    sh.show_specular_highlight = True
    sc.render.resolution_x = w; sc.render.resolution_y = int(w * 0.5625)
    cd = bpy.data.cameras.new("PoseCam"); cam = bpy.data.objects.new("PoseCam", cd)
    sc.collection.objects.link(cam); sc.camera = cam
    ctrl = bpy.data.objects["VSS_Controls"]
    base = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")}
    for spec_ in poses:
        parts = spec_.split(":")
        name, view = parts[0], parts[1]
        vals = {}
        hide = []
        mat = False
        for extra in parts[2:]:
            if extra.startswith("hide="):
                hide = extra[5:].split("|")
            elif extra == "mat":
                mat = True
            elif extra:
                for kv in extra.split(","):
                    k, v = kv.split("=")
                    vals[k] = float(v)
        for k, v in base.items():
            ctrl[k] = vals.get(k, v)
        hidden = []
        for o in bpy.data.objects:
            if o.type == "MESH" and any((o.name == h[1:]) if h.startswith("=") else o.name.startswith(h) for h in hide if h):
                if not o.hide_render:
                    o.hide_render = True; hidden.append(o)
        sh.color_type = "MATERIAL" if mat else "SINGLE"
        sh.single_color = (0.62, 0.62, 0.64)
        ctrl.update_tag()
        sc.frame_set(sc.frame_current)
        bpy.context.view_layer.update()
        eye, tgt, lens = VIEWS[view]
        cam.location = Vector(eye) * 0.001
        cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens; cd.clip_start = 0.005
        sc.render.filepath = os.path.join(out, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        for o in hidden:
            o.hide_render = False


main()
