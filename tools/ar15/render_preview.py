# AR-15: снимки как в Material Preview Blender — Eevee, освещение HDRI forest.exr (стандартное в Material Preview),
# ровный серый фон, материалы файла. Запуск на собранном .blend:
# blender -b <file.blend> --python tools/ar15/render_preview.py -- <out_dir> [вид,вид,...] [ширина]
import os
import sys
import bpy
from mathutils import Vector

HDRI = os.path.join(os.path.dirname(bpy.app.binary_path), f"{bpy.app.version[0]}.{bpy.app.version[1]}",
                    "datafiles", "studiolights", "world", "forest.exr")
# имя → (камера мм, цель мм, фокусное, положения управления)
VIEWS = {
    "01_full_right": ((540, -1020, 270), (35, 0, -40), 50, {}),
    "02_full_left": ((-430, 1020, 230), (45, 0, -40), 50, {"suppressor_on": 1.0}, 180),
    "03_receiver_right": ((-15, -330, 95), (-92, 0, -12), 55, {}),
    "04_receiver_left": ((-175, 320, 70), (-78, 0, -22), 55, {}, 180),
    "05_port_bolt_back": ((-5, -175, 55), (-42, 0, 4), 60, {"charging_handle": 0.75}),
    "06_trigger_grip": ((-55, -210, -85), (-128, 0, -62), 55, {}),
    "07_front_end": ((385, -245, 95), (245, 0, 0), 55, {}),
    "08_brake_suppressor": ((520, 175, 65), (360, 0, 0), 55, {"suppressor_on": 1.0}, 180),
    "09_stock": ((-235, -250, 45), (-300, 0, -32), 50, {}),
    "10_opened": ((-35, -265, 150), (-110, 0, -2), 45, {"upper_open": 1.0, "takedown_pin": 1.0}),
}


def world():
    w = bpy.data.worlds.new("Preview_world")
    bpy.context.scene.world = w
    w.use_nodes = True
    # как в Material Preview: свет окружения без извлечённого «солнца» с картой теней — иначе рваная тень на гладком
    if hasattr(w, "use_sun_shadow"):
        w.use_sun_shadow = False
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "HDRI_rot"
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    flat = nt.nodes.new("ShaderNodeBackground")
    flat.inputs["Color"].default_value = (0.32, 0.33, 0.34, 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(flat.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])


def look(cam, eye, tgt):
    d = Vector(tgt) - Vector(eye)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    names = a[1].split(",") if len(a) > 1 and a[1] else list(VIEWS)
    w = int(a[2]) if len(a) > 2 else 1600
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            continue
    ee = sc.eevee
    for k, v in (("taa_render_samples", 64), ("use_raytracing", True), ("use_shadows", True)):
        if hasattr(ee, k):
            setattr(ee, k, v)
    sc.render.resolution_x = w
    sc.render.resolution_y = int(w * 0.5625)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.exposure = 0.8
    world()
    cd = bpy.data.cameras.new("PreviewCam")
    cam = bpy.data.objects.new("PreviewCam", cd)
    sc.collection.objects.link(cam)
    sc.camera = cam
    for n in ("Cartridge_556", "Case_556"):
        o = bpy.data.objects.get(n)
        if o is not None:
            o.hide_render = True
    ctrl = bpy.data.objects.get("AR15_Controls")
    # снятый глушитель лежит в стороне под цевьём — на снимках без него его не показываем
    sup = []
    root = bpy.data.objects.get("Suppressor_body")
    stack = [root] if root is not None else []
    while stack:
        o = stack.pop()
        sup.append(o)
        stack += list(o.children)
    base = {k: ctrl[k] for k in ctrl.keys() if not k.startswith("_")} if ctrl else {}
    for n in names:
        eye, tgt, lens, state = VIEWS[n][:4]
        rot = VIEWS[n][4] if len(VIEWS[n]) > 4 else 0.0
        import math
        sc.world.node_tree.nodes["HDRI_rot"].inputs["Rotation"].default_value[2] = math.radians(rot)
        if ctrl:
            for k, v in base.items():
                ctrl[k] = v
            for k, v in state.items():
                ctrl[k] = v
            ctrl.update_tag()
        sc.frame_set(1)
        bpy.context.view_layer.update()
        on = float(ctrl["suppressor_on"]) if ctrl and "suppressor_on" in ctrl.keys() else 0.0
        for o in sup:
            o.hide_render = on < 0.5
        cam.location = Vector(eye) * 0.001
        look(cam, Vector(eye) * 0.001, Vector(tgt) * 0.001)
        cd.lens = lens
        cd.clip_start = 0.005
        sc.render.filepath = os.path.join(out, n + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDERED", n)


main()
