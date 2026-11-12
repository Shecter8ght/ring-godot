# АСТЕН-919: рендеры для владельца при уличном свете без сильного солнца (владелец 2026-11-12: «вид справа и слева и
# 3/4 справа и слева, затвор закрытый и открытый крупным планом, рукоятку крупным планом»).
# Пистолет — файл просмотра этапа текстур (карты из Painter), позы — ползунки ASTEN919_Controls. Свет — пасмурное небо
# (панорама Poly Haven kloofendal_overcast_puresky, CC0, assets/sky) и слабое рассеянное «солнце за облаками»; внизу —
# асфальт (фото Poly Haven, CC0, assets/textures/worn_asphalt), он же в отражениях снизу; фон размыт глубиной резкости.
# Студийные источники файла просмотра выключены, сам файл не сохраняется.
# blender -b <АСТЕН-919_текстуры_этап1_v01.blend> --factory-startup --python-exit-code 1 --python tools/asten919/render_street.py -- <папка> [кадр,кадр] [ширина высота выборки]
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SKY = ROOT / "assets/sky/kloofendal_overcast_puresky.hdr"
ASPHALT = ROOT / "assets/textures/worn_asphalt"
SKY_ROT = 40.0               # поворот панорамы, градусы
SKY_POWER = 1.0
SUN_AZ, SUN_EL = -60.0, 55.0  # «солнце за облаками»: справа спереди сверху, очень мягкое
SUN_POWER = 1.6
SUN_ANGLE = 35.0             # угловой размер, градусы: тени без резкого края
GROUND_Z = -1.25             # асфальт под пистолетом (держат на уровне груди)
EXPOSURE = 1.25
CENTER = Vector((0.02, 0.0, -0.045))
SLIDE_BACK = {"slide": 1.0, "stop": 1.0}

# кадр: (направление от точки взгляда к камере, расстояние, фокусное, точка взгляда, диафрагма, поза)
VIEWS = {
    "01_справа": ((0.0, -1.0, 0.16), 0.86, 85, CENTER, 5.6, {}),
    "02_слева": ((0.0, 1.0, 0.16), 0.86, 85, CENTER, 5.6, {}),
    "03_справа_3-4": ((0.50, -0.82, 0.26), 0.86, 85, CENTER, 5.6, {}),
    "04_слева_3-4": ((0.50, 0.82, 0.26), 0.86, 85, CENTER, 5.6, {}),
    "05_затвор_закрыт": ((0.22, 0.92, 0.34), 0.52, 85, Vector((0.02, 0.0, -0.006)), 8.0, {}),
    "06_затвор_открыт": ((0.22, 0.92, 0.34), 0.58, 85, Vector((0.0, 0.0, -0.006)), 8.0, SLIDE_BACK),
    "07_затвор_открыт_справа": ((0.30, -0.86, 0.42), 0.58, 85, Vector((0.0, 0.0, -0.006)), 8.0, SLIDE_BACK),
    "08_рукоять_слева": ((0.18, 0.97, 0.06), 0.36, 85, Vector((-0.045, 0.0, -0.078)), 8.0, {}),
    "09_рукоять_справа": ((0.18, -0.97, 0.06), 0.36, 85, Vector((-0.045, 0.0, -0.078)), 8.0, {}),
}


def gpu():
    import addon_utils
    addon_utils.enable("cycles")
    cp = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):          # при --factory-startup устройства Cycles выключены
        try:
            cp.compute_device_type = kind
            cp.get_devices()
            for dv in cp.devices:
                dv.use = dv.type != "CPU"
            return
        except Exception:      # noqa: BLE001
            continue


def world():
    S = bpy.context.scene
    w = bpy.data.worlds.new("АСТЕН-919 • улица, пасмурно")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(str(SKY), check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(SKY_ROT))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = SKY_POWER
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    S.world = w
    sun = bpy.data.lights.new("Улица • солнце за облаками", "SUN")
    sun.energy = SUN_POWER
    sun.angle = math.radians(SUN_ANGLE)
    sun.color = (1.0, 0.97, 0.93)
    so = bpy.data.objects.new(sun.name, sun)
    S.collection.objects.link(so)
    az, el = math.radians(SUN_AZ), math.radians(SUN_EL)
    d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
    so.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


def ground():
    me = bpy.data.meshes.new("Улица • асфальт")
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=60.0)
    bm.to_mesh(me)
    bm.free()
    m = bpy.data.materials.new("Улица • асфальт")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (0.5, 0.5, 0.5)        # плитка фото 2 м
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])

    def img(name, noncolor):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(str(ASPHALT / name), check_existing=True)
        t.image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
        return t
    nt.links.new(img("albedo.jpg", False).outputs[0], b.inputs["Base Color"])
    sp = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("arm.jpg", True).outputs[0], sp.inputs[0])
    nt.links.new(sp.outputs["Green"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal.jpg", True).outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    me.materials.append(m)
    o = bpy.data.objects.new(me.name, me)
    o.location = (0.0, 0.0, GROUND_Z)
    bpy.context.scene.collection.objects.link(o)


def prepare(w, h, samples):
    S = bpy.context.scene
    st = bpy.data.collections.get("Студия просмотра")
    if st is not None:
        for o in st.objects:
            if o.type == "LIGHT":
                o.hide_render = True
    ammo = bpy.data.collections.get("Ammo")           # отдельный патрон и гильза в кадр не идут
    if ammo is not None:
        ammo.hide_render = True
    world()
    ground()
    S.render.engine = "CYCLES"
    S.cycles.device = "GPU"
    S.cycles.samples = samples
    S.cycles.use_denoising = True
    S.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    S.cycles.denoising_prefilter = "ACCURATE"
    S.render.resolution_x, S.render.resolution_y = w, h
    S.render.resolution_percentage = 100
    S.render.film_transparent = False
    S.view_settings.view_transform = "AgX"
    S.view_settings.look = "AgX - Medium High Contrast"
    S.view_settings.exposure = EXPOSURE


def pose(values):
    ctl = bpy.data.objects.get("ASTEN919_Controls")
    for k in ("slide", "stop", "trigger", "trigger_safety", "mag_catch", "slide_lock", "mag_out"):
        ctl[k] = float(values.get(k, 0.0))
    ctl.update_tag()
    bpy.context.view_layer.update()


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    only = a[1].split(",") if len(a) > 1 and a[1] not in ("", "all") else None
    w, h, samples = (int(a[2]), int(a[3]), int(a[4])) if len(a) > 4 else (2560, 1440, 160)
    os.makedirs(out, exist_ok=True)
    gpu()
    prepare(w, h, samples)
    S = bpy.context.scene
    cam = S.camera
    cam.data.dof.use_dof = True
    for name, (d, dist, lens, at, fstop, values) in VIEWS.items():
        if only and name not in only and name.split("_")[0] not in only:
            continue
        pose(values)
        cam.data.lens = lens
        cam.location = at + Vector(d).normalized() * dist
        cam.rotation_euler = (at - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.dof.focus_distance = dist
        cam.data.dof.aperture_fstop = fstop
        S.render.filepath = os.path.join(out, name + ".png")
        bpy.ops.render.render(write_still=True)
        print("SHOT", name)


main()
