"""Купе Ильи: проверочные рендеры отделки в Cycles (панорама неба, бетонный пол).

    blender --background --factory-startup --python-exit-code 1 --python tools/coupe_ilya/render_tex.py -- \
        <файл.blend> <папка> <префикс> [sky=имя.hdr|bl:имя|путь] [skyrot=град] [samples=64] [hangar|yard] [exposure=EV] [res=ШxВ] \
        [rot:Объект:ось:рад] [show:/hide:Коллекция] [clean] [off:материал:слой] [unlink:материал:Вход[=число]] [hideob:часть_имени] \
        имя:x,y,z:цель_x,цель_y,цель_z[:фокус_мм] ...

Небо — панорамы Poly Haven из assets/sky (CC0, уже в проекте); «bl:имя» — панорамы, что идут с Blender
(datafiles/studiolights/world, CC0: city, courtyard, …) — в них есть дома, глянец краски по ним виден.
Пол — нейтральный серый бетон. «hangar» — ангар без крыши: профлист, колонны, ленты окон, ворота
на солнце, полосы ламп — глянцу краски есть что отражать (на чистом небе без предметов любой лак
выглядит матовым). «yard» — двор как на фото владельца: тёмная брусчатка и дома вокруг (солнце
даёт панорама, лучше kloppenheim_03). off/unlink — выключить слой стека или отцепить вход BSDF для сравнения.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
bpy.ops.wm.open_mainfile(filepath=argv[0])
out, prefix = Path(argv[1]), argv[2]
out.mkdir(parents=True, exist_ok=True)
SKY_DIR = Path(__file__).resolve().parents[2] / "assets" / "sky"
sky_name, sky_rot, samples, shots, hangar, yard = "kloppenheim_06_puresky.hdr", 0.0, 64, [], False, False
exposure, res = 0.0, (1600, 1000)
scene = bpy.context.scene
for spec in argv[3:]:
    if spec.startswith("sky="):
        sky_name = spec[4:]
    elif spec.startswith("unlink:"):
        # unlink:материал:Вход BSDF[=значение] — отцепить вход от стека (найти, какой канал портит вид)
        _, mn, rest = spec.split(":", 2)
        sock, _, val = rest.partition("=")
        pr = bpy.data.materials[mn].node_tree.nodes["Principled BSDF"]
        for ln in list(pr.inputs[sock].links):
            bpy.data.materials[mn].node_tree.links.remove(ln)
        if val and hasattr(pr.inputs[sock].default_value, "__len__"):
            pr.inputs[sock].default_value = (float(val), float(val), float(val), 1.0)
        elif val:
            pr.inputs[sock].default_value = float(val)
        print("отцеплен вход:", mn, sock, val)
    elif spec == "hangar":
        hangar = True
    elif spec == "yard":
        yard = True
    elif spec.startswith("exposure="):
        exposure = float(spec[9:])
    elif spec.startswith("res="):
        res = tuple(int(v) for v in spec[4:].split("x"))
    elif spec.startswith("skyrot="):
        sky_rot = float(spec[7:])
    elif spec.startswith("samples="):
        samples = int(spec[8:])
    elif spec.startswith("rot:"):
        _, obn, ax, val = spec.split(":")
        bpy.data.objects[obn].rotation_euler["xyz".index(ax)] = float(val)
    elif spec == "clean":
        # «как с завода»: выключить все слои состояния во всех стеках (сравнить лак с фото владельца)
        import addon_utils
        addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
        CONDITION = ("Пыль", "Грязь", "Брызги", "капли", "Следы", "Царапины", "Тормозная", "Налёт")
        for m in bpy.data.materials:
            if not m.node_tree:
                continue
            for nd in m.node_tree.nodes:
                if nd.type == "GROUP" and getattr(nd.node_tree, "yp", None) and nd.node_tree.yp.is_ypaint_node:
                    for ly in nd.node_tree.yp.layers:
                        if any(k in ly.name for k in CONDITION):
                            ly.enable = False
    elif spec.startswith("off:"):
        # off:материал:часть_имени_слоя — выключить слой стека UCUPaint (сравнить с ним и без него)
        _, mn, part = spec.split(":", 2)
        import addon_utils
        addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)
        nt = bpy.data.materials[mn].node_tree
        grp = [n for n in nt.nodes if n.type == "GROUP" and getattr(n.node_tree, "yp", None)
               and n.node_tree.yp.is_ypaint_node][0]
        for ly in grp.node_tree.yp.layers:
            if part in ly.name:
                ly.enable = False
                print("выключен слой:", mn, ly.name)
    elif spec.startswith("hideob:"):
        # hideob:часть_имени — спрятать объекты (стёкла — заглянуть в салон)
        for ob in bpy.data.objects:
            if spec[7:] in ob.name:
                ob.hide_render = True
    elif spec.startswith(("show:", "hide:")):
        kind, cn = spec.split(":", 1)
        c = bpy.data.collections[cn]
        c.hide_render = kind == "hide"
        for ob in c.all_objects:
            if ob is not None:
                ob.hide_render = kind == "hide"
    else:
        shots.append(spec)

# Cycles на видеокарте, кэш OptiX — во временной папке задачи
os.environ.setdefault("OPTIX_CACHE_PATH", str(out / "_optix_cache"))
scene.render.engine = "CYCLES"
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type == dev_type
        scene.cycles.device = "GPU"
        break
    except TypeError:
        continue
scene.cycles.samples = samples
scene.cycles.use_denoising = True
scene.render.resolution_x, scene.render.resolution_y = res
scene.view_settings.exposure = exposure
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast" if "AgX - Medium High Contrast" in [
    i.identifier for i in scene.view_settings.bl_rna.properties["look"].enum_items] else "None"

world = bpy.data.worlds.new("sky")
scene.world = world
world.use_nodes = True
nt = world.node_tree
env = nt.nodes.new("ShaderNodeTexEnvironment")
if sky_name.startswith("bl:"):
    sky_path = Path(bpy.utils.system_resource("DATAFILES", path="studiolights/world")) / f"{sky_name[3:]}.exr"
elif Path(sky_name).is_absolute():
    sky_path = Path(sky_name)
else:
    sky_path = SKY_DIR / sky_name
env.image = bpy.data.images.load(str(sky_path))
mp = nt.nodes.new("ShaderNodeMapping")
tc = nt.nodes.new("ShaderNodeTexCoord")
mp.inputs["Rotation"].default_value[2] = sky_rot * 3.14159265 / 180
nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
nt.links.new(env.outputs["Color"], nt.nodes["Background"].inputs["Color"])
nt.nodes["Background"].inputs["Strength"].default_value = 1.0

bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0))
floor = bpy.context.active_object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.20, 0.20, 0.19, 1)
fb.inputs["Roughness"].default_value = 0.85
floor.data.materials.append(fm)

if yard:
    # тёмная брусчатка (как на фото владельца) и дома вокруг: лаку есть что отражать по бокам
    fb.inputs["Base Color"].default_value = (0.03, 0.03, 0.029, 1)
    fb.inputs["Roughness"].default_value = 0.8
    vor = fm.node_tree.nodes.new("ShaderNodeTexVoronoi")
    vor.feature = "DISTANCE_TO_EDGE"
    vor.inputs["Scale"].default_value = 9.0
    fbump = fm.node_tree.nodes.new("ShaderNodeBump")
    fbump.inputs["Strength"].default_value = 0.5
    fbump.invert = True
    fm.node_tree.links.new(vor.outputs["Distance"], fbump.inputs["Height"])
    fm.node_tree.links.new(fbump.outputs["Normal"], fb.inputs["Normal"])

    def facade(name, color, loc, rot_z, width, height):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt_f = m.node_tree
        bsdf = nt_f.nodes["Principled BSDF"]
        bsdf.inputs["Roughness"].default_value = 0.6
        # окна: решётка по координатам грани — тёмное стекло в светлой стене
        tc_f = nt_f.nodes.new("ShaderNodeTexCoord")
        brick = nt_f.nodes.new("ShaderNodeTexBrick")
        brick.offset = 0.0
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Color1"].default_value = (0.02, 0.025, 0.03, 1)
        brick.inputs["Color2"].default_value = (0.02, 0.025, 0.03, 1)
        brick.inputs["Mortar"].default_value = (*color, 1)
        brick.inputs["Mortar Size"].default_value = 0.35
        brick.inputs["Brick Width"].default_value = 2.2
        brick.inputs["Row Height"].default_value = 3.2
        mp_f = nt_f.nodes.new("ShaderNodeMapping")
        mp_f.inputs["Scale"].default_value = (1 / 1.0, 1 / 1.0, 1 / 1.0)
        nt_f.links.new(tc_f.outputs["Object"], mp_f.inputs["Vector"])
        nt_f.links.new(mp_f.outputs["Vector"], brick.inputs["Vector"])
        nt_f.links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
        rgh = nt_f.nodes.new("ShaderNodeMapRange")
        nt_f.links.new(brick.outputs["Fac"], rgh.inputs["Value"])
        rgh.inputs["To Min"].default_value = 0.08
        rgh.inputs["To Max"].default_value = 0.7
        nt_f.links.new(rgh.outputs["Result"], bsdf.inputs["Roughness"])
        bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=(1.5708, 0, rot_z))
        o = bpy.context.active_object
        o.name = name
        o.scale = (width, height, 1)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        o.data.materials.append(m)

    # фасады нейтральные: цветной дом в отражении сквозь пятна пыли читается как ржавчина
    facade("yard_beige", (0.55, 0.50, 0.42), (14.0, 10.0, 6.0), -0.85, 30, 12)
    facade("yard_grey", (0.45, 0.44, 0.41), (-16.0, 6.0, 7.0), 1.35, 34, 14)
    facade("yard_white", (0.72, 0.71, 0.66), (2.0, -18.0, 5.0), 0.05, 34, 10)
    facade("yard_dark", (0.25, 0.24, 0.23), (-4.0, 18.0, 6.0), 0.0, 30, 12)

if hangar:
    # ангар без крыши (небо светит сверху): стены из профлиста, колонны, ленты окон, ворота открыты
    # на солнце, полосы ламп — краске есть что отражать
    def mat_simple(name, color, rough, emit=0.0):
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        b_ = m.node_tree.nodes["Principled BSDF"]
        b_.inputs["Base Color"].default_value = (*color, 1)
        b_.inputs["Roughness"].default_value = rough
        if emit:
            b_.inputs["Emission Color"].default_value = (*color, 1)
            b_.inputs["Emission Strength"].default_value = emit
        return m

    def box(name, loc, size, m):
        bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
        o = bpy.context.active_object
        o.name = name
        o.scale = size
        o.data.materials.append(m)
        return o

    wall = mat_simple("hangar_wall", (0.13, 0.13, 0.125), 0.6)
    nt_w = wall.node_tree
    wave = nt_w.nodes.new("ShaderNodeTexWave")          # профлист: волна вдоль стены
    wave.inputs["Scale"].default_value = 6.0
    bump = nt_w.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    nt_w.links.new(wave.outputs["Fac"], bump.inputs["Height"])
    nt_w.links.new(bump.outputs["Normal"], nt_w.nodes["Principled BSDF"].inputs["Normal"])
    column = mat_simple("hangar_column", (0.35, 0.18, 0.05), 0.5)
    window = mat_simple("hangar_window", (0.75, 0.85, 1.0), 0.1, emit=6.0)
    lamp = mat_simple("hangar_lamp", (1.0, 0.93, 0.82), 0.5, emit=25.0)
    gate = mat_simple("hangar_gate", (1.0, 0.95, 0.88), 0.5, emit=9.0)
    for sx in (-1, 1):
        box("wall", (sx * 9.0, 0, 3.0), (0.2, 24, 6), wall)
        box("window_band", (sx * 8.85, 0, 4.9), (0.05, 22, 0.9), window)
        for y in (-9, -4.5, 0, 4.5, 9):
            box("column", (sx * 8.6, y, 3.0), (0.35, 0.35, 6), column)
    box("wall_back", (0, 12.0, 3.0), (18, 0.2, 6), wall)
    for sx in (-1, 1):
        box("wall_front", (sx * 6.0, -12.0, 3.0), (6, 0.2, 6), wall)
    box("gate_light", (0, -12.2, 2.4), (6.0, 0.05, 4.8), gate)
    for x in (-2.6, 0.0, 2.6):
        box("lamp", (x, 0, 5.2), (0.18, 9.0, 0.05), lamp)

cam_data = bpy.data.cameras.new("_cam")
cam = bpy.data.objects.new("_cam", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
for spec in shots:
    parts = spec.split(":")
    name = parts[0]
    loc = Vector([float(v) for v in parts[1].split(",")])
    tgt = Vector([float(v) for v in parts[2].split(",")])
    cam_data.lens = float(parts[3]) if len(parts) > 3 else 50.0
    cam_data.clip_start = 0.01
    cam.location = loc
    cam.rotation_euler = (tgt - loc).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = str(out / f"{prefix}_{name}.png")
    bpy.ops.render.render(write_still=True)
print("готово:", out)
