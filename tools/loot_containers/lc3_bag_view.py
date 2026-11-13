"""Сумка v02, отделка v03: файл просмотра со студией и кадры Cycles.

  blender --background "<RING_Loot_MedBag_uv_v02.blend>" --python tools/loot_containers/lc3_bag_view.py -- build|shots [имена кадров]

build — материалы Principled с картами (пути относительные), студия: светло-серый бесшовный фон, мягкий ключевой свет и
скользящий заполняющий; сохраняет models/RING_Loot_MedBag_finish_v03.blend. shots — кадры Просмотр/medbag_v02/finish_*.png.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector as V

MODELS = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/models"
TEXDIR = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/textures/finish_v03/lc_bag"
SHOTS = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers/Просмотр/medbag_v02"
OUT = MODELS + "/RING_Loot_MedBag_finish_v03.blend"
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
A_OBJ = ("МС_корпус", "МС_клапан", "МС_карман", "МС_лента_низа")


def base_name(n):
    return n.rsplit(".", 1)[0] if n.rsplit(".", 1)[-1].isdigit() else n


def img(name, color=True):
    im = bpy.data.images.load(f"{TEXDIR}/{name}", check_existing=True)
    im.colorspace_settings.name = "sRGB" if color else "Non-Color"
    return im


def principled(name, prefix, trim=False, inner=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bs = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bs.outputs["BSDF"], out.inputs["Surface"])

    def tex(fname, color):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img(fname, color)
        t.interpolation = "Linear"
        return t
    tb = tex(f"{prefix}_basecolor.png", True)
    tr = tex(f"{prefix}_roughness.png", False)
    tn = tex(f"{prefix}_normal.png", False)
    nt.links.new(tb.outputs["Color"], bs.inputs["Base Color"])
    nt.links.new(tr.outputs["Color"], bs.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 1.0
    nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["Specular IOR Level"].default_value = 0.5
    if not inner and not trim:
        bs.inputs["Sheen Weight"].default_value = 0.25
        bs.inputs["Sheen Roughness"].default_value = 0.5
    if trim:
        tm = tex(f"{prefix}_metallic.png", False)
        ta = tex(f"{prefix}_alpha.png", False)
        nt.links.new(tm.outputs["Color"], bs.inputs["Metallic"])
        nt.links.new(ta.outputs["Color"], bs.inputs["Alpha"])
        m.surface_render_method = "DITHERED"
        m.use_backface_culling = False
    return m


def studio():
    sc = bpy.context.scene
    for ob in list(bpy.data.objects):
        if ob.type in ("LIGHT", "CAMERA") or ob.name.startswith("студия"):
            bpy.data.objects.remove(ob)
    w = bpy.data.worlds.get("Студия_МС") or bpy.data.worlds.new("Студия_МС")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.62, 0.62, 0.64, 1)
    bg.inputs[1].default_value = 0.16
    sc.world = w
    # циклорама: пол и плавный подъём стены
    bm = bmesh.new()
    prof = [(-3.0, 0.0)] + [(1.2 + 0.9 * math.sin(a), 0.9 - 0.9 * math.cos(a)) for a in [i * math.pi / 2 / 12 for i in range(13)]] + [(2.1, 3.5)]
    for k, (y, z) in enumerate(prof):
        for x in (-3.0, 4.0):
            bm.verts.new((x, y, z))
    bm.verts.ensure_lookup_table()
    for k in range(len(prof) - 1):
        bm.faces.new((bm.verts[2 * k], bm.verts[2 * k + 1], bm.verts[2 * k + 3], bm.verts[2 * k + 2]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("студия_цикл")
    bm.to_mesh(me)
    ob = bpy.data.objects.new("студия_цикл", me)
    bpy.context.scene.collection.objects.link(ob)
    for p in me.polygons:
        p.use_smooth = True
    gm = bpy.data.materials.new("студия_серый")
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.50, 0.50, 0.52, 1)
    gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    me.materials.append(gm)

    def area(name, loc, rot, energy, size, sy=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        if sy:
            ld.shape = "RECTANGLE"
            ld.size_y = sy
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = tuple(math.radians(a) for a in rot)
        bpy.context.scene.collection.objects.link(lo)
    area("студия_ключ", (-1.4, -1.9, 2.0), (50, 0, -32), 110, 1.6, 1.2)
    area("студия_скользящий", (1.7, -0.2, 0.55), (84, 0, 62), 55, 0.7, 1.6)
    area("студия_заполняющий", (0.4, -2.6, 0.9), (82, 0, 8), 14, 2.5)
    cd = bpy.data.cameras.new("кам")
    co = bpy.data.objects.new("студия_кам", cd)
    bpy.context.scene.collection.objects.link(co)
    sc.camera = co


def build():
    mA = principled("Нейлон_корпус", "lc_bag")
    mIn = principled("Подкладка", "lc_bag_in", inner=True)
    mB = principled("Фурнитура_стропы", "lc_bag_trim", trim=True)
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        n = base_name(ob.name)
        slots = len(ob.data.materials)
        ob.data.materials.clear()
        if n in A_OBJ:
            ob.data.materials.append(mA)
            ob.data.materials.append(mIn)
        else:
            for _ in range(max(1, slots)):
                ob.data.materials.append(mB)
    studio()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    try:
        sc.cycles.denoising_use_gpu = False
    except Exception:
        pass
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = -0.5
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    sc.render.film_transparent = False
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].shading.type = "RENDERED"
    # относительные пути
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True, relative_remap=True)
    for im in bpy.data.images:
        if im.filepath:
            im.filepath = bpy.path.relpath(bpy.path.abspath(im.filepath), start=MODELS)
    bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
    print("saved", OUT)


VIEWS = [
    ("34_closed", False, (0.0, 0.0, 0.17), 1.15, 28, 14, 50),
    ("open", True, (0.0, 0.0, 0.2), 1.35, 25, 30, 42),
    ("zip", False, (-0.14, -0.112, 0.30), 0.27, 25, 35, 55),
    ("strap", False, (0.0, -0.15, 0.085), 0.36, 18, 10, 55),
    ("bottom", False, (-0.18, -0.14, 0.03), 0.30, 30, 8, 50),
]


def shots(only):
    sc = bpy.context.scene
    try:
        pr = bpy.context.preferences.addons["cycles"].preferences
        pr.compute_device_type = "OPTIX"
        pr.get_devices()
        for dv in pr.devices:
            dv.use = dv.type != "CPU"
        sc.cycles.device = "GPU"
    except Exception as e:
        print("GPU не включён:", e)
    sc.cycles.use_denoising = True
    try:
        sc.cycles.denoising_use_gpu = False
    except Exception:
        pass
    sc.cycles.samples = 96
    cam = sc.camera
    roots = {False: bpy.data.objects["МС_сумка_укладка"], True: bpy.data.objects["МС_сумка_укладка_раскрыта"]}
    os.makedirs(SHOTS, exist_ok=True)
    for name, open_, tgt, dist, az, el, lens in VIEWS:
        if only and name not in only:
            continue
        for st, r in roots.items():
            for o in [r] + list(r.children_recursive):
                o.hide_render = st != open_
        c = V(roots[open_].location) + V(tgt)
        a, e = math.radians(az), math.radians(el)
        cam.location = c + V((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        cam.data.clip_start = 0.01
        sc.render.filepath = f"{SHOTS}/finish_{name}.png"
        bpy.ops.render.render(write_still=True)
        print("shot", name, flush=True)


if argv and argv[0] == "build":
    build()
elif argv and argv[0] == "shots":
    shots(set(argv[1:]))
