# ВЕРАС-54 v14: показные рендеры формы (Cycles, студийный свет) — файл модели не сохраняется.
#   blender -b <файл.blend> --factory-startup --python tools/veras54_v14/geo/render_views.py -- <папка> [кадр,кадр…]
#       [--res 2400x1350] [--samples 128] [--cpu]
# Кадры: right, left, q_front, q_rear, fp_grip (рукоятка с крючком глазами стрелка), open (рама отведена: видно
# магазин и патронник), open_in (взгляд через окно на патронник и верх магазина). Материалы без текстур: цвета просмотра из assemble.MATS,
# приглушённые — чтобы под студийным светом читалась форма, а не чёрная воронёная сталь.
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import part_rig  # noqa: E402

MM = 0.001
# кадр: (откуда, куда — мм осей ВЕРАС; угол зрения по вертикали, градусы; поза рига; поворот света вокруг Z, градусы)
AB = {"selector": part_rig.SEL_AB}
SHOTS = {
    "right": ((235, -2600, 30), (235, 0, -55), 13.5, {}, 0),
    "left": ((235, 2600, 30), (235, 0, -55), 13.5, {}, 180),
    "q_front": ((1750, -1500, 620), (255, 0, -50), 13.0, {}, 30),
    "q_rear": ((-1500, -1650, 640), (215, 0, -50), 13.0, {}, -40),
    # глаз стрелка: позади и чуть левее-выше оружия, взгляд вдоль него на рукоятку и крючок
    "fp_grip": ((-105, 175, 5), (88, 0, -66), 30.0, dict(AB), 150),
    "open": ((150, -265, 215), (196, -2, -4), 26.0, dict(AB, cycle=0.5), 10),
    "open_in": ((100, -110, 70), (222, -3, -3), 30.0, dict(AB, cycle=0.5), -30),
}
SCALE = 0.62          # множитель к цветам просмотра
BRASS = ("Case_lacquer", "Bullet_jacket", "Primer")


def materials():
    import ast
    src = open(os.path.join(HERE, "assemble.py"), encoding="utf-8").read()
    a = src.index("MATS = {") + len("MATS = "); b = src.index("\n}", a) + 2
    for name, (col, rough, metal, view) in ast.literal_eval(src[a:b]).items():
        m = bpy.data.materials.get(name)
        if m is None or not m.use_nodes:
            continue
        b = m.node_tree.nodes.get("Principled BSDF")
        # полимер и резина — тёмные, как в жизни: иначе под студийным светом они светлее стали
        k = 1.0 if name in BRASS else (SCALE if metal > 0.5 else 0.3)
        c = col if name in BRASS else view
        b.inputs["Base Color"].default_value = (c[0] * k, c[1] * k, c[2] * k, 1.0)
        b.inputs["Roughness"].default_value = max(0.3, rough)
        b.inputs["Metallic"].default_value = metal


def world(rot_deg):
    w = bpy.data.worlds.new("Studio"); bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    base = os.path.dirname(bpy.app.binary_path)
    ver = "%d.%d" % bpy.app.version[:2]
    env.image = bpy.data.images.load(os.path.join(base, ver, "datafiles", "studiolights", "world", "studio.exr"))
    mp = nt.nodes.new("ShaderNodeMapping"); tc = nt.nodes.new("ShaderNodeTexCoord")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot_deg))
    lit = nt.nodes.new("ShaderNodeBackground"); lit.inputs["Strength"].default_value = 0.45
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Color"].default_value = (0.045, 0.047, 0.052, 1); bg.inputs["Strength"].default_value = 1.0
    lp = nt.nodes.new("ShaderNodeLightPath"); mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], lit.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(lit.outputs["Background"], mix.inputs[1]); nt.links.new(bg.outputs["Background"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mp


def area(name, loc, target, size, watts, col=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA"); d.shape = "RECTANGLE"; d.size = size[0]; d.size_y = size[1]
    d.energy = watts; d.color = col
    o = bpy.data.objects.new(name, d); bpy.context.scene.collection.objects.link(o)
    o.location = Vector(loc) * MM
    o.rotation_euler = (Vector(target) * MM - o.location).to_track_quat("-Z", "Y").to_euler()
    return o


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    names = None; res = (2400, 1350); samples = 128; cpu = False
    i = 1
    while i < len(argv):
        if argv[i] == "--res": res = tuple(int(v) for v in argv[i + 1].split("x")); i += 2
        elif argv[i] == "--samples": samples = int(argv[i + 1]); i += 2
        elif argv[i] == "--cpu": cpu = True; i += 1
        else: names = argv[i].split(","); i += 1
    os.makedirs(out, exist_ok=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    if not cpu:
        try:
            pr = bpy.context.preferences.addons["cycles"].preferences
            for kind in ("OPTIX", "CUDA"):
                try:
                    pr.compute_device_type = kind; pr.get_devices()
                    devs = [d for d in pr.devices if d.type == kind]
                    if devs:
                        for d in pr.devices:
                            d.use = d.type == kind
                        sc.cycles.device = "GPU"; print("DEVICE", kind, [d.name for d in devs]); break
                except Exception:
                    continue
        except Exception as e:
            print("GPU_OFF", e)
    sc.cycles.samples = samples; sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"; sc.render.film_transparent = False
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.0
    materials()
    for o in sc.objects:
        if o.type in ("LIGHT", "CAMERA"):
            o.hide_render = True
    mp = world(0)
    cam_d = bpy.data.cameras.new("ShowCam"); cam = bpy.data.objects.new("ShowCam", cam_d)
    sc.collection.objects.link(cam); sc.camera = cam
    cam_d.sensor_fit = "VERTICAL"; cam_d.clip_start = 0.01; cam_d.clip_end = 50
    key = fill = rim = None
    ctrl = bpy.data.objects["VERAS54_Controls"]
    defaults = {k: d for k, _, d in part_rig.SLIDERS}
    for n in (names or list(SHOTS)):
        eye, tgt, fov, pose, rot = SHOTS[n]
        for k, d in defaults.items():
            ctrl[k] = float(pose.get(k, d))
        ctrl.update_tag()
        e, t = Vector(eye) * MM, Vector(tgt) * MM
        cam.location = e
        cam.rotation_euler = (t - e).to_track_quat("-Z", "Y").to_euler()
        cam_d.angle_y = math.radians(fov)
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(rot))
        for l in (key, fill, rim):
            if l is not None:
                bpy.data.objects.remove(l, do_unlink=True)
        # свет привязан к камере: ключевой сверху-сбоку, заполняющий с другой стороны, контровой сзади-сверху
        view = (t - e).normalized(); side = view.cross(Vector((0, 0, 1))).normalized(); up = Vector((0, 0, 1))
        dist = max(0.5, (t - e).length * 0.55)
        tm = Vector(tgt)
        kp = (t - view * dist * 0.7 + side * dist * 0.75 + up * dist * 0.8) / MM
        fp = (t - view * dist * 0.8 - side * dist * 0.9 + up * dist * 0.15) / MM
        rp = (t + view * dist * 0.9 - side * dist * 0.3 + up * dist * 0.9) / MM
        s = dist / MM
        key = area("Key", kp, tm, (s * 0.9 * MM, s * 0.6 * MM), 55 * dist * dist, (1.0, 0.97, 0.93))
        fill = area("Fill", fp, tm, (s * 1.2 * MM, s * 0.9 * MM), 14 * dist * dist, (0.90, 0.94, 1.0))
        rim = area("Rim", rp, tm, (s * 0.8 * MM, s * 0.4 * MM), 60 * dist * dist)
        bpy.context.view_layer.update()
        sc.render.filepath = os.path.join(out, n + ".png")
        bpy.ops.render.render(write_still=True)
        print("RENDER", sc.render.filepath)


main()
