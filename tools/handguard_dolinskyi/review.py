# Цевьё Dolinskyi: файл просмотра со студией и снимки самопроверки в ракурсах кадров ролика.
# Материал — карты Painter (Spec/Gloss) в Principled BSDF: цвет = Diffuse, металличность 0, шероховатость = 1 − Glossiness,
# сила блика (IOR Level) = Specular (линейный) / 0.08 (у неметалла 0.04 → 0.5), нормаль — Normal OpenGL.
# Свет как в окне Painter у автора (0:25): окружение Studio Tomoco, поворот 234° вслед за камерой (Environment alignment
# Camera), фон чёрный (Opacity 0), без теней от источников — только окружение.
#   blender --background <развёртка.blend> --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/review.py
#     -- <папка карт> <выход.blend> [папка снимков] [вид,…]
import math
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MAPS = argv[0]
OUT_BLEND = argv[1]
SHOTS = argv[2] if len(argv) > 2 else None
ONLY = set(argv[3].split(",")) if len(argv) > 3 else None
TOMOCO = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/starter_assets/environments/Studio/Studio Tomoco.exr"
PREFIX = "Alu_anodized_"
MM = 0.001
ENV_OFFSET = float(os.environ.get("HG_ENV_OFFSET", "180"))
# ракурсы кадров ролика: (точка взгляда в мм, направление на камеру, расстояние в мм, фокусное)
VIEWS = {
    "t066": ((95.0, 0.0, 4.0), (-0.42, -0.80, 0.42), 400.0, 50),     # 1:06 — 3/4 сзади сверху, сторона L
    "t080": ((92.0, 0.0, 2.0), (-0.22, -0.92, 0.32), 480.0, 50),     # 1:20 — дальше и больше сбоку
    "t118": ((90.0, 0.0, 2.0), (-0.45, -0.80, 0.42), 440.0, 50),     # 1:58 — белая форма (для сверки формы)
    "t474": ((10.0, 0.0, 4.0), (-0.75, -0.40, 0.52), 160.0, 50),     # 7:54 — задний торец
    "t446": ((105.0, -8.0, 22.0), (-0.10, -0.75, 0.65), 110.0, 50),   # 7:26 — надпись крупно
    "t766": ((140.0, -24.0, 0.0), (0.0, -1.0, 0.05), 95.0, 50),      # 12:46 — L11, площадка с гнездом QD крупно
    "t005": ((88.0, 0.0, 2.0), (0.0, -1.0, 0.12), 480.0, 50),        # 0:05 — рендер автора сбоку
}


def image(name, colorspace):
    path = os.path.join(MAPS, PREFIX + name)
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = colorspace
    return im


def material():
    m = bpy.data.materials.new("Цевьё — анодированный алюминий (карты Painter)")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    b.location = (300, 0)
    out.location = (600, 0)
    nt.links.new(b.outputs[0], out.inputs[0])

    def tex(name, cs, y):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = image(name, cs)
        t.location = (-700, y)
        t.label = name
        return t
    d = tex("Diffuse_sRGB.png", "sRGB", 300)
    nt.links.new(d.outputs["Color"], b.inputs["Base Color"])
    g = tex("Glossiness_Raw.png", "Non-Color", 0)
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.location = (-300, 0)
    nt.links.new(g.outputs["Color"], inv.inputs[1])
    nt.links.new(inv.outputs[0], b.inputs["Roughness"])
    s = tex("Specular_sRGB.png", "sRGB", -300)
    bw = nt.nodes.new("ShaderNodeRGBToBW")
    bw.location = (-400, -300)
    nt.links.new(s.outputs["Color"], bw.inputs[0])
    lvl = nt.nodes.new("ShaderNodeMath")
    lvl.operation = "DIVIDE"
    lvl.inputs[1].default_value = 0.08
    lvl.location = (-200, -300)
    nt.links.new(bw.outputs[0], lvl.inputs[0])
    nt.links.new(lvl.outputs[0], b.inputs["Specular IOR Level"])
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["IOR"].default_value = 1.5
    n = tex("Normal_OpenGL_Raw.png", "Non-Color", -600)
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.location = (-300, -600)
    nt.links.new(n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def world():
    w = bpy.data.worlds.new("Студия • Studio Tomoco (как окно Painter у автора)")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(TOMOCO, check_existing=True)
    # Environment alignment Camera: окружение привязано к камере целиком — направление мира переводится в оси камеры
    # (обратный поворот камеры), затем «вверх» камеры → вверх окружения и поворот по азимуту (ENV_OFFSET)
    cam_m = nt.nodes.new("ShaderNodeMapping")
    cam_m.name = "Камера"
    cam_m.vector_type = "TEXTURE"
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "Окружение"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nt.links.new(tc.outputs["Generated"], cam_m.inputs["Vector"])
    nt.links.new(cam_m.outputs["Vector"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.label = "Окружение (сила)"
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    black = nt.nodes.new("ShaderNodeBackground")
    black.label = "Фон (Opacity 0 у автора)"
    black.inputs["Color"].default_value = (0.0, 0.0, 0.0, 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(black.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    bpy.context.scene.world = w
    return mp


def camera():
    cd = bpy.data.cameras.new("Камера просмотра")
    cd.clip_start = 0.002
    cam = bpy.data.objects.new("Камера просмотра", cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


def aim(cam, mp, view):
    tgt, d, dist, lens = VIEWS[view]
    tgt = Vector(tgt) * MM
    d = Vector(d).normalized()
    cam.data.lens = lens
    cam.location = tgt + d * dist * MM
    cam.rotation_euler = (tgt - cam.location).to_track_quat("-Z", "Y").to_euler()
    # окружение вслед за камерой (Environment alignment Camera). У автора Rotation 234 — в счёте Painter; в Blender
    # азимут ENV_OFFSET подобран по кадру 1:06 (бока ровно освещены, зубья не пересвечены)
    bpy.context.view_layer.update()
    w = bpy.context.scene.world.node_tree.nodes
    w["Камера"].inputs["Rotation"].default_value = cam.matrix_world.to_euler("XYZ")
    mp.inputs["Rotation"].default_value = (math.pi / 2, 0.0, math.radians(ENV_OFFSET))


def main():
    sc = bpy.context.scene
    lp = bpy.data.objects["handguard_low"]
    hp = bpy.data.objects.get("handguard_high")
    if hp is not None:
        bpy.data.objects.remove(hp, do_unlink=True)
    for c in bpy.data.collections:
        c.hide_render = False
        c.hide_viewport = False
    lp.data.materials.clear()
    lp.data.materials.append(material())
    for p in lp.data.polygons:
        p.use_smooth = True
    mp = world()
    cam = camera()
    sc.render.engine = "CYCLES"
    sc.cycles.device = "GPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(x.type == dev for x in prefs.devices):
                for x in prefs.devices:
                    x.use = x.type == dev
                break
        except Exception:      # noqa: BLE001
            continue
    sc.cycles.samples = 96
    sc.cycles.preview_samples = 64
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = False           # видеопамять держит Painter
    # во вьюпорте тоже: без шумоподавления 32 сэмпла давали «песок» поверх текстуры (владелец 01.11: «шумная»);
    # по цвету и нормалям — иначе шумодав смывает мелкое зерно покрытия вместе с шумом рендера
    sc.cycles.use_preview_denoising = True
    for pre in ("", "preview_"):
        setattr(sc.cycles, pre + "denoising_input_passes", "RGB_ALBEDO_NORMAL")
    sc.view_settings.view_transform = "Standard"  # тонкривая Linear, как у автора в Painter
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    sc.render.film_transparent = False
    aim(cam, mp, "t066")
    for img in bpy.data.images:
        if img.filepath and not img.packed_file:
            img.pack()
    for a in bpy.data.screens:
        for ar in a.areas:
            if ar.type == "VIEW_3D":
                for sp in ar.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND, compress=True)
    print("SAVED", OUT_BLEND)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        for v in VIEWS:
            if ONLY and v not in ONLY:
                continue
            aim(cam, mp, v)
            sc.render.filepath = os.path.join(SHOTS, f"ours_{v}.png")
            bpy.ops.render.render(write_still=True)
            print("SHOT", sc.render.filepath)


main()
