"""«Осока»: студийные рендеры 4K в военной тематике для владельца (2026-11-05: «несколько красивых студийных изображений
4к в военной тематике»). Текстурированная игровая сетка (Осока_текстуры_этап1_v1.blend) — на двух деревянных ящиках под
боеприпасы (свои модели общежития, assets/models/dorm/furniture/it_ammo*.gltf) поверх оливкового брезента (лён Poly Haven
CC0 — tools/ar15/tent_scene.mat_canvas) в тёмной студии-циклораме; рядом открытый ящик с цинками. Свет — тёплый ключевой,
холодный контровой, луч сверху сквозь лёгкую дымку, слабая заливка; отражения — студийная HDRI (Poly Haven CC0).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/osoka/render_military.py -- <папка> [кадр,кадр] [ширина высота выборки] [сцена.blend]
"""
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "tools", "ar15"))
import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import tent_scene as TS  # noqa: E402

# файл с текстурами: заводская отделка или износ (OSOKA_RENDER_SRC=<…/Осока_износ_этап2_v1.blend>)
SRC = os.environ.get("OSOKA_RENDER_SRC", "E:/Models Blender/WEAPONS/Верба — модель/Осока_текстуры_этап1_v1.blend")
CRATE = ROOT + "/assets/models/dorm/furniture/it_ammo.gltf"
CRATE_OPEN = ROOT + "/assets/models/dorm/furniture/it_ammo_open.gltf"
HDRI = ROOT + "/_asset_src/pm_game/sources/studio_small_09_1k.hdr"
CRATE_H = 0.175


def log(*a):
    print("MIL", *a, flush=True)


def controls(**kw):
    c = bpy.data.objects["OSOKA_Controls"]
    for k in list(c.keys()):
        if not k.startswith("_"):
            c[k] = {"front_sight": 1.0, "rear_sight": 1.0}.get(k, 0.0)
    for k, v in kw.items():
        c[k] = v
    c.update_tag()
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    return (Vector(map(min, *[(p.x, p.y, p.z) for p in pts])), Vector(map(max, *[(p.x, p.y, p.z) for p in pts])))


def import_gltf(path, coll, loc, rot_z=0.0):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new("ящик", None)
    coll.objects.link(root)
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if o.parent is None:
            o.parent = root
    root.location = Vector(loc)
    root.rotation_euler = (0.0, 0.0, rot_z)
    return root, new


def cyclorama(coll):
    """Студийная циклорама: пол и задник одной дугой (R 0.8 м), тёмно-серый мат."""
    W, D, H, R = 9.0, 7.0, 4.0, 0.8
    prof = [(-D / 2, 0.0), (D / 2 - R, 0.0)]
    for k in range(1, 12):
        a = math.pi / 2 * k / 12
        prof.append((D / 2 - R + R * math.sin(a), R - R * math.cos(a)))
    prof += [(D / 2, R), (D / 2, H)]
    bm = bmesh.new()
    rows = []
    for x in (-W / 2, W / 2):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    me = bpy.data.meshes.new("циклорама")
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("циклорама", me)
    coll.objects.link(o)
    o.data.materials.append(TS.mat_plain("Студия · фон", (0.010, 0.011, 0.010), 0.85))
    return o


def tarp(coll, cx, cy, z, sx, sy):
    """Оливковый брезент со складками: сетка со смещением по облакам (складки до ~6 мм)."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=110, size=1.0)
    o = bpy.context.active_object
    o.name = "брезент"
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    o.scale = (sx, sy, 1.0)
    o.location = (cx, cy, z + 0.004)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    tex = bpy.data.textures.new("складки", "CLOUDS")
    tex.noise_scale = 0.35
    tex.noise_depth = 2
    m = o.modifiers.new("складки", "DISPLACE")
    m.texture = tex
    m.strength = 0.012
    m.mid_level = 0.5
    o.modifiers.new("гладко", "SUBSURF").levels = 1
    for p in o.data.polygons:
        p.use_smooth = True
    o.data.materials.append(TS.mat_canvas("Брезент олива", (0.16, 0.17, 0.11), 3.0))
    return o


def area(coll, name, loc, target, size, power, color, size_y=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = power
    d.color = color
    d.shape = "RECTANGLE" if size_y else "DISK"
    d.size = size
    if size_y:
        d.size_y = size_y
    o = bpy.data.objects.new(name, d)
    coll.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
    return o


def spot(coll, name, loc, target, power, color, angle_deg, blend=0.35, radius=0.05):
    d = bpy.data.lights.new(name, "SPOT")
    d.energy = power
    d.color = color
    d.spot_size = math.radians(angle_deg)
    d.spot_blend = blend
    d.shadow_soft_size = radius
    o = bpy.data.objects.new(name, d)
    coll.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
    return o


def haze(coll, density=0.0011):
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    o = bpy.context.active_object
    o.name = "дымка"
    for c in list(o.users_collection):
        c.objects.unlink(o)
    coll.objects.link(o)
    o.scale = (7.0, 6.0, 3.2)
    o.location = (0.9, 0.0, 1.4)
    m = bpy.data.materials.new("Дымка")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    v = nt.nodes.new("ShaderNodeVolumePrincipled")
    v.inputs["Density"].default_value = density
    v.inputs["Anisotropy"].default_value = 0.35
    v.inputs["Color"].default_value = (0.8, 0.82, 0.85, 1.0)
    nt.links.new(v.outputs[0], out.inputs["Volume"])
    o.data.materials.append(m)
    o.visible_shadow = False
    return o


def world():
    w = bpy.data.worlds.new("Студия · мир")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.05
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    dark = nt.nodes.new("ShaderNodeBackground")
    dark.inputs["Color"].default_value = (0.004, 0.004, 0.0045, 1.0)
    lp = nt.nodes.new("ShaderNodeLightPath")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg.outputs[0], mix.inputs[1])
    nt.links.new(dark.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    bpy.context.scene.world = w


def camera(name, loc, look, lens, fstop=None, focus=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    cd.sensor_width = 36.0
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = (Vector(focus or look) - Vector(loc)).length
    o = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(o)
    o.location = Vector(loc)
    o.rotation_euler = (Vector(look) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def setup():
    bpy.ops.wm.open_mainfile(filepath=SRC)
    S = bpy.context.scene
    old = bpy.data.collections.get("Студия просмотра")
    if old is not None:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    controls()
    launcher = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("Missile")]
    # постановка: короб на переднем ящике, труба — на задней стопке из двух; наклон — чтобы опор было обе
    box = bpy.data.objects["Box_lower"]
    blo, bhi = bbox([box])
    z_box, x_box = blo.z, 0.5 * (blo.x + bhi.x)
    x_rear = 0.30
    tube_bottom = -0.0385
    floor = z_box - CRATE_H
    rear_top = floor + 2 * CRATE_H
    # поворот вокруг оси Y через точку опоры короба: задняя опора — на (rear_top - tube_bottom) по z за (x_box - x_rear)
    th = math.atan2(rear_top - tube_bottom, x_box - x_rear)
    place = bpy.data.objects.new("Постановка", None)
    S.collection.objects.link(place)
    roots = [o for o in bpy.data.objects if o.parent is None and o is not place and o.type in ("MESH", "EMPTY")]
    for o in roots:
        mw = o.matrix_world.copy()
        o.parent = place
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_world = mw
    pivot = Vector((x_box, 0.0, z_box))
    place.matrix_world = (Matrix.Translation(pivot) @ Matrix.Rotation(th, 4, "Y") @ Matrix.Translation(-pivot))
    bpy.context.view_layer.update()
    log("наклон", round(math.degrees(th), 2), "град; пол", round(floor, 3), "короб x", round(x_box, 3))
    env = bpy.data.collections.new("Студия · окружение")
    S.collection.children.link(env)
    cyc = cyclorama(env)
    cyc.location = (0.9, -0.3, floor)
    tarp(env, 0.85, 0.05, floor, 2.6, 1.6)
    rot = math.pi / 2
    import_gltf(CRATE, env, (x_box - 0.02, 0.0, floor), rot)
    import_gltf(CRATE, env, (x_rear, 0.0, floor), rot)
    import_gltf(CRATE, env, (x_rear + 0.01, 0.0, floor + CRATE_H), rot + 0.03)
    import_gltf(CRATE_OPEN, env, (-0.55, 0.95, floor), math.radians(18))
    world()
    lights = bpy.data.collections.new("Студия · свет")
    S.collection.children.link(lights)
    tgt = (0.9, 0.0, -0.1)
    area(lights, "Ключевой (тёплый)", (1.9, 1.6, 1.4), tgt, 1.6, 220.0, (1.0, 0.86, 0.72), size_y=0.8)
    area(lights, "Контровой (холодный)", (0.4, -1.8, 0.9), tgt, 2.4, 380.0, (0.70, 0.82, 1.0), size_y=0.25)
    area(lights, "Заливка", (2.8, -0.6, 0.3), tgt, 2.0, 18.0, (0.9, 0.92, 1.0))
    spot(lights, "Луч сквозь дымку", (-0.6, 1.2, 2.9), (1.0, -0.1, floor), 700.0, (0.78, 0.86, 1.0), 26.0)
    area(lights, "Фон (пятно на заднике)", (0.9, 1.0, 0.6), (0.9, 3.2, floor + 1.2), 1.2, 35.0, (0.55, 0.62, 0.55))
    haze(env)
    S.render.engine = "CYCLES"
    # с --factory-startup устройства Cycles не выбраны: device = GPU без них молча считал на процессоре (~10 мин на кадр 4K)
    S.cycles.device = "CPU"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                S.cycles.device = "GPU"
                break
        except Exception:
            continue
    log("устройство", S.cycles.device, prefs.compute_device_type)
    S.cycles.use_denoising = True
    S.cycles.denoiser = "OPENIMAGEDENOISE"
    S.cycles.volume_step_rate = 1.0
    S.cycles.volume_max_steps = 256
    S.view_settings.view_transform = "AgX"
    S.view_settings.look = "AgX - Medium High Contrast"
    S.view_settings.exposure = -0.3
    S.render.film_transparent = False
    S.render.image_settings.file_format = "PNG"
    S.render.image_settings.color_depth = "8"
    return floor


SHOTS = {
    # имя: (камера, точка взгляда, объектив, диафрагма, точка резкости, состояние)
    "1_герой": ((2.55, 1.55, 0.42), (0.95, 0.0, -0.13), 40, 5.6, (1.3, 0.0, -0.1), {}),
    "2_профиль": ((0.86, 2.85, 0.02), (0.86, 0.0, -0.09), 50, None, None, {}),
    "3_механизм": ((1.60, 0.62, 0.02), (1.27, 0.0, -0.11), 85, 2.8, (1.28, 0.03, -0.13), {}),
    "4_раструб": ((2.15, 0.48, 0.12), (1.60, 0.02, -0.01), 70, 4.0, (1.62, 0.03, 0.0), {"front_cap": 1.0}),
    "5_пуск": ((3.6, 1.45, 0.05), (2.45, 0.0, -0.02), 45, 8.0, (2.6, 0.0, 0.0),
               {"front_cap": 1.0, "rear_cap": 1.0, "missile_out": 0.62, "fins": 1.0}),
    "6_справа_сверху": ((2.55, -1.15, 1.05), (0.95, 0.0, -0.14), 40, 8.0, (1.2, 0.0, -0.1), {}),
}


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(a[0])
    names = a[1].split(",") if len(a) > 1 and a[1] else list(SHOTS)
    w, h, samples = (int(a[2]), int(a[3]), int(a[4])) if len(a) > 4 else (3840, 2160, 256)
    scene_path = a[5] if len(a) > 5 else None
    os.makedirs(out, exist_ok=True)
    setup()
    S = bpy.context.scene
    S.render.resolution_x, S.render.resolution_y = w, h
    S.cycles.samples = samples
    place = bpy.data.objects["Постановка"]
    for n in names:
        loc, look, lens, fstop, focus, state = SHOTS[n]
        controls(**state)
        for o in bpy.data.objects:
            if o.name.startswith("Front_cap"):
                o.hide_render = state.get("front_cap", 0.0) > 0.5
            elif o.name.startswith("Rear_cap"):
                o.hide_render = state.get("rear_cap", 0.0) > 0.5
        cam = camera("Кадр " + n, loc, look, lens, fstop, focus)
        S.camera = cam
        S.render.filepath = os.path.join(out, n + ".png")
        bpy.ops.render.render(write_still=True)
        log("SHOT", n)
    controls()
    if scene_path:
        S.camera = bpy.data.objects.get("Кадр 1_герой") or S.camera
        bpy.ops.wm.save_as_mainfile(filepath=scene_path, compress=True)
        log("SAVED", scene_path)


main()
