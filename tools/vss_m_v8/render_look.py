# Снимки Cycles для осмотра материалов: -- <out_dir> <вид,вид> [ширина] [сэмплы] [свойства=…]
import os
import sys
import bpy
from mathutils import Vector

VIEWS = {
    "hero": ((760, -760, 330), (430, 0, -20), 42),
    "side": ((447, -1650, 0), (447, 0, -20), 50),
    "receiver": ((470, -300, 70), (405, 0, -5), 55),
    "stock": ((120, -420, 60), (220, 0, -40), 45),
    "sleeve": ((700, -240, 110), (620, 0, 15), 55),
    "muzzle": ((1010, -170, 90), (870, 0, 12), 55),
    "mag": ((520, -250, -40), (452, 0, -60), 55),
    "left": ((450, 700, 200), (430, 0, -10), 42),
    "rail_top": ((380, -150, 170), (380, 0, 45), 55),
    "grip": ((330, -260, -40), (330, 0, -60), 55),
    "safety": ((420, -150, -15), (385, 0, -2), 50),
    "nameplate": ((356, -135, 30), (356, 0, 19), 60),
    "latch": ((228, -95, 85), (286, 0, 27), 55),
    "handguard": ((540, -190, 70), (525, 0, 12), 55),
    "left34": ((260, 520, 230), (470, 0, -5), 40),
}


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out, views = a[0], a[1].split(",")
    w = int(a[2]) if len(a) > 2 else 1280
    spp = int(a[3]) if len(a) > 3 else 96
    sc = bpy.context.scene
    if len(a) > 4 and a[4]:
        ctrl = bpy.data.objects["VSS_Controls"]
        for kv in a[4].split(","):
            k, v = kv.split("=")
            ctrl[k] = float(v)
        ctrl.update_tag()
    sc.cycles.samples = spp
    sc.render.resolution_x = w; sc.render.resolution_y = int(w * 0.5625)
    cd = bpy.data.cameras.new("LookCam"); cam = bpy.data.objects.new("LookCam", cd)
    sc.collection.objects.link(cam); sc.camera = cam
    os.makedirs(out, exist_ok=True)
    for v in views:
        eye, tgt, lens = VIEWS[v]
        cam.location = Vector(eye) * 0.001
        cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        cd.lens = lens; cd.clip_start = 0.01
        sc.render.filepath = os.path.join(out, v + ".png")
        bpy.ops.render.render(write_still=True)


main()
