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
    "cover_rear_r": ((320, -150, 75), (305, 0, 22), 45),
    "sleeve_low": ((780, -170, -45), (610, 0, 10), 40),
    "slope_top": ((250, -120, 95), (300, 0, 28), 45),
    "stock_rear": ((40, -150, 40), (90, 0, -30), 45),
    "comb_top": ((180, -90, 130), (230, 0, 0), 45),
    "screw": ((300, -75, -20), (300, -18, -36), 60),
    "sight_line": ((120, 0, 56.3), (879.5, 0, 56.3), 160),
    "front_sight_34": ((930, -110, 85), (879.5, 0, 48), 60),
    "cover_hdri": ((330, -230, 140), (390, 0, 20), 40),
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
    if os.environ.get("LOOK_HDRI"):
        # осмотр при свете окружения (как во вьюпорте владельца): панорама вместо студии, свет студии выключен
        wd = bpy.data.worlds.new("LookHDRI"); sc.world = wd; wd.use_nodes = True
        nt = wd.node_tree; nt.nodes.clear()
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(os.environ["LOOK_HDRI"], check_existing=True)
        bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 1.0
        o = nt.nodes.new("ShaderNodeOutputWorld")
        nt.links.new(env.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], o.inputs[0])
        for ob in bpy.data.objects:
            if ob.type == "LIGHT":
                ob.hide_render = True
        sc.view_settings.exposure = 0.0
    sc.cycles.samples = spp
    sc.cycles.denoising_use_gpu = False      # видеопамять может держать Substance Painter
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
