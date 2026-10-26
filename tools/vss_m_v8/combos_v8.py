# ВСС-М v8: сцены всех сочетаний «прицел × магазин» (просьба владельца 26.10) — ПСО 4×24 на боковом «ласточкином
# хвосте», 4×32 на планке Пикатинни крышки, без прицела; магазины на 10, 20 и 30. Каждое сочетание — своя сцена
# Blender («ПСО · магазин 20» и т. п.); общие винтовка, фон, свет и камера. Фон — тёмная студийная циклорама
# с мягким светом (софтбокс сверху, контровой, заполняющий), панорама — только в отражениях. Свет — в силу студии:
# вдвое сильнее AgX пережимал светлый приклад и высветлял тёмный фон до серого (26.10).
# Посадка (замер 26.10, мм): ПСО — зажим (x −55…55) по центру боковой планки (x 307…415), губки на её рёбрах:
# сдвиг (361, 22, −1.75); 4×32 — низ мостика крепления (z 0) на верх планки (z 51.2), поперечный упор (x −2.9)
# в пазу x 394.75: сдвиг (397.65, 0, 51.2). Магазины на 20 и 30 собраны в той же системе, что вставленный на 10,
# и сдвинуты по Y — вставляются переносом на его место.
# blender --background --factory-startup <ВСС-М_v8_студия.blend> --python-exit-code 1 --python tools/vss_m_v8/combos_v8.py -- <out.blend>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

ROOT = "E:/Games/RING-godot/_asset_src/vss_m_v8"
SIGHTS_SP = ROOT + "/sights_sp.blend"
SIGHTS_EXPORT = ROOT + "/sp_sights/export"
HDRI = ROOT + "/hdri/photo_studio_loft_hall_2k.hdr"
MM = 0.001
SCOPES = {"ПСО": ("PSO_VSS_4x24", (361.0, 22.0, -1.75)), "4×32": ("Rail_4x32", (397.65, 0.0, 51.2))}
MAGS = ("10", "20", "30")


def append_scope(root_name, coll):
    with bpy.data.libraries.load(SIGHTS_SP, link=False) as (src, dst):
        dst.objects = [n for n in src.objects]
    root = None
    for o in dst.objects:
        if o is not None and o.parent is None and o.name.split(".")[0] == root_name:
            root = o
    keep = []
    for o in dst.objects:
        if o is None:
            continue
        r = o
        while r.parent is not None:
            r = r.parent
        if r is root:
            coll.objects.link(o)
            keep.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    return root, keep


def glass():
    g = bpy.data.materials.get("V8_Glass_Coated") or bpy.data.materials.new("V8_Glass_Coated")
    g.use_nodes = True
    b = g.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.85, 0.9, 0.88, 1.0)
    b.inputs["Roughness"].default_value = 0.02
    b.inputs["Transmission Weight"].default_value = 1.0
    b.inputs["IOR"].default_value = 1.52
    if "Thin Film Thickness" in b.inputs:
        b.inputs["Thin Film Thickness"].default_value = 420.0      # просветление: переливы в бликах линз
        b.inputs["Thin Film IOR"].default_value = 1.38
    return g


def scope_materials(objs):
    import sp_apply
    gl = glass()
    for o in objs:
        if o.type != "MESH":
            continue
        for s in o.material_slots:
            if s.material is None:
                continue
            nm = s.material.name.split(".")[0]
            if nm.startswith("optic_"):
                s.material = sp_apply.material(nm, SIGHTS_EXPORT)
            elif "glass" in nm.lower() or "lens" in nm.lower():
                s.material = gl


def cyclorama(coll):
    """Студийный фон: пол, плавно переходящий в стену за винтовкой (радиус 0.35 м), тёмный матовый."""
    import bmesh
    me = bpy.data.meshes.new("Backdrop")
    bm = bmesh.new()
    z0, y_wall, r = -0.34, 0.75, 0.35
    prof = [(-1.6, z0)]
    steps = 16
    for k in range(steps + 1):
        a = math.radians(90.0 * k / steps)
        prof.append((y_wall - r + r * math.sin(a), z0 + r - r * math.cos(a)))
    prof.append((y_wall, 1.4))
    rows = []
    for x in (-1.2, 2.2):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    o = bpy.data.objects.new("Backdrop", me)
    coll.objects.link(o)
    m = bpy.data.materials.new("Backdrop_matte")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.012, 0.0125, 0.014, 1.0)
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Specular IOR Level"].default_value = 0.25     # без блеска: на пологом полу он светлел до серого
    me.materials.append(m)
    return o


def area(coll, name, loc, target, size, energy, color=(1.0, 1.0, 1.0), size_y=None):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size = size
    ld.size_y = size_y or size
    ld.energy = energy
    ld.color = color
    o = bpy.data.objects.new(name, ld)
    coll.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def world():
    w = bpy.data.worlds.new("Combos_HDRI")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.12
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(env.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    return w


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    base = bpy.context.scene
    rifle = bpy.data.collections["VSS_M_v8"]
    mags = bpy.data.collections.get("Magazines")
    # магазины — отдельно от винтовки: в каждой сцене свой; 20 и 30 — на место вставленного 10
    if mags and mags.name in [c.name for c in rifle.children]:
        rifle.children.unlink(mags)
    m10 = bpy.data.objects["Magazine_10"]
    for t in ("20", "30"):
        m = bpy.data.objects[f"Magazine_{t}"]
        m.matrix_world = m10.matrix_world.copy()
    mag_colls = {t: bpy.data.collections[f"Magazine_{t}"] for t in MAGS}
    # прицелы — своими коллекциями, посажены на планки
    scope_colls = {}
    for label, (rn, off) in SCOPES.items():
        c = bpy.data.collections.new("Прицел " + label)
        root, objs = append_scope(rn, c)
        scope_materials(objs)
        root.matrix_world = Matrix.Translation(Vector(off) * MM) @ root.matrix_world
        scope_colls[label] = c
    # общие фон, свет и камера
    env = bpy.data.collections.new("Фон и свет")
    cyclorama(env)
    area(env, "Key_softbox", (0.25, -0.75, 0.95), (0.5, 0.0, 0.0), 1.2, 110.0, (1.0, 0.97, 0.92), 0.8)
    area(env, "Rim_strip", (0.55, 0.65, 0.45), (0.5, 0.0, 0.05), 0.15, 70.0, (0.9, 0.95, 1.0), 1.6)
    area(env, "Fill", (1.4, -0.9, 0.05), (0.5, 0.0, 0.0), 0.8, 16.0)
    area(env, "Floor_glow", (0.5, 0.45, -0.3), (0.5, 0.75, 0.3), 1.5, 12.0, (1.0, 0.92, 0.85), 0.5)
    cd = bpy.data.cameras.new("Cam_Combo")
    cd.lens = 46.0
    cam = bpy.data.objects.new("Cam_Combo", cd)
    env.objects.link(cam)
    eye, tgt = Vector((0.52, -1.32, 0.22)), Vector((0.5, 0.0, -0.04))
    cam.location = eye
    cam.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
    cd.clip_start = 0.01
    wd = world()
    # сцены сочетаний
    combos = []
    for label in list(SCOPES) + ["без прицела"]:
        for t in MAGS:
            sc = bpy.data.scenes.new(f"{label} · магазин {t}")
            sc.collection.children.link(rifle)
            sc.collection.children.link(mag_colls[t])
            if label in scope_colls:
                sc.collection.children.link(scope_colls[label])
            sc.collection.children.link(env)
            sc.camera = cam
            sc.world = wd
            sc.render.engine = "CYCLES"
            sc.cycles.samples = 256
            sc.cycles.use_denoising = True
            sc.render.resolution_x, sc.render.resolution_y = 1920, 1080
            sc.view_settings.view_transform = base.view_settings.view_transform
            sc.view_settings.look = base.view_settings.look
            sc.view_settings.exposure = 0.0
            sc.unit_settings.scale_length = base.unit_settings.scale_length
            combos.append(sc)
    base.name = "Студия (исходная)"
    for win in bpy.context.window_manager.windows:      # файл открывается на первом сочетании
        win.scene = combos[0]
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out, [s.name for s in combos])


main()
