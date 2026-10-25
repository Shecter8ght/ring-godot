# ВСС-М v8: сцена «винтовка на столе и обвесы рядом». Открывает геометрию v8, накладывает материалы,
# добавляет прицелы (ПСО и 4×32 из исходников комплекта), стол, свет, камеры; каждый предмет кладётся на грань своей
# выпуклой оболочки, над которой лежит его центр масс (устойчивая поза, без висения).
# blender --background --factory-startup <VSS_M_v8_geometry.blend> --python-exit-code 1 --python tools/vss_m_v8/scene_v8.py -- <out.blend> [table|studio] [painter]
# painter — поверх процедурных материалов карты Substance Painter (запускать на _asset_src/vss_m_v8/VSS_M_v8_sp.blend:
# там развёртки деталей, по которым запечены карты; см. sp_export.py, sp_apply.py)
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402
import materials_v8 as MV  # noqa: E402
import tex_v8  # noqa: E402

KIT = "E:/Models Blender/WEAPONS/ВСС Винторез — полный комплект/01_Blender/02_Оптика"
PSO_SRC = f"{KIT}/01_ПСО_4x24/ПСО_4x24_Исходник_геометрии.blend"
SCOPE_SRC = f"{KIT}/02_Прицел_4x32/Прицел_4x32_Исходник_геометрии.blend"
TABLE = "E:/Games/RING-godot/_asset_src/vss_m_v8/table_brown_planks_09"
HDRI = "E:/Games/RING-godot/_asset_src/vss_m_v8/hdri/artist_workshop_2k.hdr"


# ---------------- обвесы из комплекта ----------------

def append_root(path, root_name, coll):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    root = None
    for o in dst.objects:
        if o is None:
            continue
        if o.name.split(".")[0] in (root_name,) or (o.parent is None and o.type == "EMPTY" and o.name.startswith(root_name)):
            root = o
    keep = []
    for o in dst.objects:
        if o is None:
            continue
        # в файле ПСО лежит и копия 4×32 — берём только потомков нужного корня
        r = o
        while r.parent is not None:
            r = r.parent
        if r is root:
            coll.objects.link(o)
            keep.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    return root, keep


def remap_optic_materials(objs, M):
    table = {"Coated aluminium": M["Alu_anodized"], "Machined rim": M["Alu_bare"], "Engraving": M["Engraving_fill"],
             "Inner black": M["Inner_black"], "Rubber": M["Rubber"]}
    unknown = set()
    for o in objs:
        if o.type != "MESH":
            continue
        for k, v in {"wear": 1.0, "dust": 1.0, "grime": 1.0, "oil": 1.0}.items():
            o[k] = v
        for s in o.material_slots:
            if s.material is None:
                continue
            nm = s.material.name.split(".")[0]
            low = nm.lower()
            if nm in table:
                s.material = table[nm]
            elif "glass" in low or "lens" in low or "стекл" in low:
                s.material = M["Glass"]
            elif "reticle" in low or "сетк" in low:
                pass
            else:
                unknown.add(nm)
                s.material = M["Alu_anodized"]
    if unknown:
        print("OPTIC_UNKNOWN_MATS", sorted(unknown))


# ---------------- устойчивая поза на столе ----------------

def world_points(objs, step=1):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        if o.type != "MESH" or o.hide_render:
            continue
        e = o.evaluated_get(dg)
        me = e.to_mesh()
        mw = e.matrix_world
        pts.extend(mw @ v.co for i, v in enumerate(me.vertices) if i % step == 0)
        e.to_mesh_clear()
    return pts


def resting_rotation(pts, prefer, com=None):
    """Грань выпуклой оболочки, на которую предмет ляжет устойчиво (центр масс проецируется внутрь грани),
    ближайшая по нормали к prefer (направление «вниз» в координатах предмета). Возвращает матрицу поворота,
    переводящую нормаль грани в −Z."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    r = bmesh.ops.convex_hull(bm, input=vs)
    hull_faces = [f for f in r["geom"] if isinstance(f, bmesh.types.BMFace)]
    bm.faces.ensure_lookup_table()
    if com is None:
        com = sum(pts, Vector()) / len(pts)
    best, best_score = None, -1e9
    # объединяем почти компланарные грани оболочки: проверяем точку опоры по треугольнику и его соседям
    for f in hull_faces:
        n = f.normal.normalized()
        if n.length < 0.5:
            continue
        # проекция центра масс на плоскость грани
        c0 = f.verts[0].co
        d = (com - c0).dot(n)
        if d > 0:
            continue                      # нормаль оболочки — наружу; центр масс должен быть «над» гранью (внутри)
        proj = com - n * d
        # точка внутри грани? (с соседями той же плоскости)
        group = [f]
        for e in f.edges:
            for g2 in e.link_faces:
                if g2 is not f and g2 in hull_faces and g2.normal.normalized().dot(n) > 0.999:
                    group.append(g2)
        inside = False
        for g2 in group:
            vv = [v.co for v in g2.verts]
            ok = True
            for i in range(len(vv)):
                a, b = vv[i], vv[(i + 1) % len(vv)]
                if (b - a).cross(proj - a).dot(n) < -1e-9:
                    ok = False
                    break
            if ok:
                inside = True
                break
        if not inside:
            continue
        score = n.dot(Vector(prefer).normalized()) + 1e-3 * f.calc_area()
        if score > best_score:
            best, best_score = n.copy(), score
    bm.free()
    if best is None:
        best = Vector(prefer).normalized()
    q = best.rotation_difference(Vector((0, 0, -1)))
    return q.to_matrix().to_4x4()


def place(root, objs, prefer, xy, yaw_deg, table_z=0.0, step=1):
    """Кладёт предмет (иерархию от root) на стол: устойчивая грань вниз, поворот вокруг вертикали, точка xy."""
    bpy.context.view_layer.update()
    pts = world_points(objs, step)
    com = sum(pts, Vector()) / len(pts)
    R = resting_rotation(pts, prefer, com)
    Y = Matrix.Rotation(math.radians(yaw_deg), 4, "Z")
    M = Y @ R @ Matrix.Translation(-com)
    root.matrix_world = M @ root.matrix_world
    bpy.context.view_layer.update()
    pts = world_points(objs, step)
    zmin = min(p.z for p in pts)
    cx = sum(p.x for p in pts) / len(pts); cy = sum(p.y for p in pts) / len(pts)
    root.matrix_world = Matrix.Translation((xy[0] - cx, xy[1] - cy, table_z - zmin + 0.00005)) @ root.matrix_world
    bpy.context.view_layer.update()


def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


# ---------------- стол, свет, камеры ----------------

def table(coll):
    import lib
    top = lib.box("Table_top", -900.0, 900.0, -450.0, 450.0, -42.0, 0.0, coll)
    lib.finish(top, 3.0, 4, 30)
    m = bpy.data.materials.new("Table_planks")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping"); mp.inputs["Scale"].default_value = (0.55, 0.55, 0.55)
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    def tex(name, noncolor):
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bpy.data.images.load(f"{TABLE}/brown_planks_09_{name}_4k.jpg", check_existing=True)
        t.image.colorspace_settings.name = "Non-Color" if noncolor else "sRGB"
        t.projection = "BOX"; t.projection_blend = 0.2
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
        return t
    d = tex("diff", False); a = tex("arm", True); n = tex("nor_gl", True)
    cc = nt.nodes.new("ShaderNodeHueSaturation")
    cc.inputs["Value"].default_value = 0.5
    cc.inputs["Saturation"].default_value = 1.1
    nt.links.new(d.outputs[0], cc.inputs["Color"])
    nt.links.new(cc.outputs[0], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(a.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap"); nm.inputs["Strength"].default_value = 1.0
    nt.links.new(n.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    b.inputs["Specular IOR Level"].default_value = 0.4
    top.data.materials.append(m)
    legs = []
    for sx in (-1, 1):
        for sy in (-1, 1):
            legs.append(lib.box(f"Table_leg_{sx}{sy}", sx * 840 - 35, sx * 840 + 35, sy * 390 - 35, sy * 390 + 35, -760.0, -42.0, coll))
    leg = lib.join(legs, "Table_legs")
    leg.data.materials.append(m)
    floor = lib.box("Floor", -4000, 4000, -4000, 4000, -762, -760, coll)
    fm = bpy.data.materials.new("Floor_concrete"); fm.use_nodes = True
    fb = fm.node_tree.nodes.get("Principled BSDF")
    fb.inputs["Base Color"].default_value = (0.09, 0.085, 0.08, 1); fb.inputs["Roughness"].default_value = 0.85
    floor.data.materials.append(fm)
    return top


def lights(coll, bright=1.0):
    sc = bpy.context.scene
    w = bpy.data.worlds.new("V8_Workshop")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(HDRI, check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord"); mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(120))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"]); nt.links.new(mp.outputs[0], env.inputs["Vector"])
    bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs["Strength"].default_value = 0.4 * bright
    nt.links.new(env.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs[0])

    def area(name, loc, size, power, color, tgt=(0.0, 0.0, 0.0)):
        ld = bpy.data.lights.new(name, "AREA"); ld.shape = "RECTANGLE"; ld.size = size[0]; ld.size_y = size[1]
        ld.energy = power * bright; ld.color = color
        lo = bpy.data.objects.new(name, ld); coll.objects.link(lo)
        lo.location = loc
        lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        return lo
    area("Key_softbox", (-0.75, -0.85, 1.25), (1.4, 0.9), 170.0, (1.0, 0.94, 0.86), (0.05, 0.0, 0.0))
    area("Fill_card", (1.1, -0.7, 0.75), (1.4, 1.4), 45.0, (0.88, 0.94, 1.0), (0.05, 0.0, 0.0))
    area("Rim_strip", (0.1, 0.95, 0.85), (2.0, 0.3), 150.0, (1.0, 0.98, 0.95), (0.05, 0.0, 0.0))
    area("Top_soft", (0.0, 0.0, 1.7), (2.2, 1.2), 70.0, (1.0, 1.0, 1.0), (0.0, 0.0, 0.0))


def camera(name, eye, tgt, lens, coll, fstop=None, focus=None):
    cd = bpy.data.cameras.new(name); cd.lens = lens; cd.clip_start = 0.01; cd.clip_end = 50.0
    cam = bpy.data.objects.new(name, cd); coll.objects.link(cam)
    cam.location = eye
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cd.dof.use_dof = True; cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = (Vector(focus or tgt) - Vector(eye)).length
    return cam


def render_settings(samples=256):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            if any(d.type == dev_type for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev_type
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = samples
    sc.cycles.preview_samples = 48
    sc.cycles.use_denoising = True
    sc.cycles.use_preview_denoising = True
    sc.render.resolution_x = 1920; sc.render.resolution_y = 1080
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"


def viewport_rendered(cam):
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.region_3d.view_perspective = "CAMERA"
                        sp.clip_start = 0.005


# ---------------- главное ----------------

def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    mode = a[1] if len(a) > 1 else "table"
    prints = tex_v8.make_decals()
    M = MV.build_all(prints)
    MV.assign(M, tex_v8.TUNE)
    if "painter" in a[2:]:
        import sp_apply
        sp_apply.apply_all()
    sc = bpy.context.scene
    if mode == "studio":
        tex_v8.studio(dark=True)
        viewport_rendered(None)
        render_settings(128)
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print("SAVED", out)
        return
    top = bpy.data.collections["VSS_M_v8"]
    att = bpy.data.collections.new("Attachments_on_table"); sc.collection.children.link(att)
    env = bpy.data.collections.new("Table_scene"); sc.collection.children.link(env)
    root = bpy.data.objects["VSS_M_v8"]
    spare = [bpy.data.objects["Magazine_20"], bpy.data.objects["Magazine_30"]]
    # магазины на 20 и 30 — отдельно от винтовки
    for m_ in spare:
        mw = m_.matrix_world.copy(); m_.parent = None; m_.matrix_world = mw
    # винтовка: правой стороной вверх — вниз левая сторона (+Y)
    rifle_objs = [o for o in descendants(root) if o.type == "MESH" and not o.name.startswith(("Magazine_20", "Magazine_30"))]
    place(root, rifle_objs, (0, 1, 0), (0.02, 0.06), 0.0, step=7)
    place(spare[0], descendants(spare[0]), (0, 1, 0), (0.0, -0.2), 14.0, step=3)
    place(spare[1], descendants(spare[1]), (0, 1, 0), (-0.22, -0.2), -10.0, step=3)
    # патроны россыпью: копии меша патрона
    me = bpy.data.meshes.get("Cartridge_SP5_mesh")
    rnd = random.Random(7)
    spots = [((0.22, -0.2), 70), ((0.26, -0.17), 115), ((0.245, -0.245), 20), ((0.3, -0.215), 160), ((0.205, -0.27), 95)]
    for i, (xy, yaw) in enumerate(spots):
        c = bpy.data.objects.new(f"Loose_round_{i + 1}", me); att.objects.link(c)
        for k, v in {"wear": 1.0, "dust": 0.6, "grime": 1.0, "oil": 1.0}.items():
            c[k] = v
        bpy.context.view_layer.update()
        place(c, [c], (0, 1 if i % 2 else -1, 0.0), xy, yaw + rnd.uniform(-8, 8))
    for i, xy in enumerate(((0.34, -0.15), (0.355, -0.18))):
        c = bpy.data.objects.new(f"Standing_round_{i + 1}", me); att.objects.link(c)
        for k, v in {"wear": 1.0, "dust": 0.6, "grime": 1.0, "oil": 1.0}.items():
            c[k] = v
        bpy.context.view_layer.update()
        place(c, [c], (-1, 0, 0), xy, rnd.uniform(0, 360))
    # прицелы
    pso_root, pso_objs = append_root(PSO_SRC, "PSO_VSS_4x24", att)
    remap_optic_materials(pso_objs, M)
    place(pso_root, [o for o in pso_objs if o.type == "MESH"], (0, 1, 0), (-0.17, 0.27), -8.0, step=2)
    sc_root, sc_objs = append_root(SCOPE_SRC, "Rail_4x32", att)
    remap_optic_materials(sc_objs, M)
    place(sc_root, [o for o in sc_objs if o.type == "MESH"], (0, 1, 0), (0.23, 0.27), 6.0, step=2)
    table(env)
    lights(env)
    cam = camera("Cam_Table_Overview", (0.05, -1.08, 0.86), (0.05, 0.02, -0.02), 40.0, env, 6.3, (0.02, 0.0, 0.02))
    camera("Cam_Rifle_Closeup", (0.62, -0.5, 0.26), (0.1, 0.05, 0.02), 70.0, env, 4.0, (0.1, 0.05, 0.02))
    camera("Cam_Low_Hero", (0.48, -0.42, 0.16), (0.0, 0.05, 0.03), 60.0, env, 5.6, (0.03, 0.04, 0.03))
    # камера над правой стороной коробки (винтовка лежит правой стороной вверх)
    bpy.context.view_layer.update()
    rl = bpy.data.objects["Receiver_lower"]
    pts = [rl.matrix_world @ Vector(c) for c in rl.bound_box]
    rc = sum(pts, Vector()) / 8
    camera("Cam_Receiver_Detail", (rc.x + 0.05, rc.y - 0.16, rc.z + 0.3), (rc.x + 0.03, rc.y + 0.0, rc.z), 60.0, env, 5.6, rc)
    camera("Cam_Front_Detail", (rc.x + 0.35, rc.y - 0.2, rc.z + 0.22), (rc.x + 0.22, rc.y + 0.02, rc.z), 60.0, env, 5.6,
           (rc.x + 0.22, rc.y, rc.z))
    sc.camera = cam
    # стенд-студия осмотра (из tex_v8) не нужна: свет — стол
    for nm in ("Studio",):
        c = bpy.data.collections.get(nm)
        if c:
            for o in list(c.objects):
                bpy.data.objects.remove(o, do_unlink=True)
    render_settings(256)
    viewport_rendered(cam)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


main()
