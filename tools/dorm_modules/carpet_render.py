"""Ковёр общежития с настоящим ворсом — сцена для показа: угол комнаты, ковёр на стене над кроватью, тумбочка,
паркет «ёлочкой», стены в два цвета (масляная панель снизу, побелка сверху), вечернее солнце из окна скользит по ворсу.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_worn_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/carpet_render.py -- <выход .blend> [<папка кадров> [кадр …]]

Мебель — копии предметов файла просмотра износа (карты maps_worn), ворс ковра — carpet_pile.py (волокна, Cycles),
текстуры комнаты — CC0 Poly Haven из assets/textures (painted_plaster_wall; паркет и его нормаль — dorm_v3, дуб
Oak Veneer 01), небо — assets/sky/belfast_sunset_puresky.hdr. Камеры: «Кадр 1 — комната», «Кадр 2 — ковёр»,
«Кадр 3 — ворс крупно». Владелец 2026-11-01: «сделай этот ковёр из настоящей ткани с настоящим ворсом … пришли 3
красивых рендера, как этот ковёр либо на стене висит, либо на полу лежит».
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import carpet_pile as CP  # noqa: E402

ROOT = "E:/Games/RING-godot"
TEX = ROOT + "/assets/textures"
MAPS = ROOT + "/_asset_src/dorm_furniture/maps_worn"
SCENE = "Сцена ковра"
# комната: задняя стена — плоскость y = 0 (на ней ковёр), комната в y < 0; окно — в правой стене
X0, X1, Y0, H = -2.0, 2.2, -3.6, 2.8
WALL = 0.25
WIN_Y, WIN_Z = (-2.0, -0.7), (0.95, 2.35)
PANEL = 1.45  # высота масляной панели
SUN = V((-0.80, 0.50, -0.22)).normalized()  # куда светит солнце: из окна справа к задней стене, чуть вниз
EXPOSURE = (0.9, 0.35, 0.35)  # по кадрам: комната в тени темнее пятна солнца на ковре
# предметы: коллекция файла просмотра → место (x, y, z) и поворот вокруг Z, градусы
PLACE = {
    "furn_carpet": ((0.0, 0.0, 0.62), 0.0),
    "furn_bed": ((0.0, -0.47, 0.0), 90.0),        # изголовье (+Y кровати) — к −X, к тумбочке
    "furn_mattress": ((0.0, -0.47, 0.425), 90.0),
    "furn_nightstand": ((-1.27, -0.225, 0.0), 0.0),
}


def tex(nt, path, non_color=False, proj="BOX"):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    n.projection = proj
    n.projection_blend = 0.25
    return n


def mapping(nt, scale, rot_z=0.0):
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (scale, scale, scale)
    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rot_z))
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    return mp


def mat_wall() -> bpy.types.Material:
    """Штукатурка под краской: снизу масляная панель (серо-зелёная, полуглянец), сверху побелка, между ними — бордюр."""
    m = bpy.data.materials.new("стена_комнаты")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    mp = mapping(nt, 0.55)
    alb = tex(nt, TEX + "/painted_plaster_wall/albedo.jpg")
    arm = tex(nt, TEX + "/painted_plaster_wall/arm.jpg", True)
    nrm = tex(nt, TEX + "/painted_plaster_wall/normal.jpg", True)
    for t in (alb, arm, nrm):
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    low = nt.nodes.new("ShaderNodeMapRange")
    low.inputs["From Min"].default_value = PANEL + 0.004
    low.inputs["From Max"].default_value = PANEL - 0.004
    nt.links.new(sep.outputs["Z"], low.inputs["Value"])
    stripe = nt.nodes.new("ShaderNodeMath")
    stripe.operation = "COMPARE"
    stripe.inputs[1].default_value = PANEL + 0.012
    stripe.inputs[2].default_value = 0.009
    nt.links.new(sep.outputs["Z"], stripe.inputs[0])
    paint = nt.nodes.new("ShaderNodeMix")
    paint.data_type = "RGBA"
    paint.inputs["A"].default_value = (0.86, 0.85, 0.80, 1)    # побелка
    paint.inputs["B"].default_value = (0.42, 0.55, 0.50, 1)    # масляная краска
    nt.links.new(low.outputs["Result"], paint.inputs["Factor"])
    band = nt.nodes.new("ShaderNodeMix")
    band.data_type = "RGBA"
    nt.links.new(stripe.outputs[0], band.inputs["Factor"])
    nt.links.new(paint.outputs["Result"], band.inputs["A"])
    band.inputs["B"].default_value = (0.20, 0.30, 0.27, 1)
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(band.outputs["Result"], mul.inputs["A"])
    gain = nt.nodes.new("ShaderNodeBrightContrast")
    gain.inputs["Bright"].default_value = 0.22
    nt.links.new(alb.outputs["Color"], gain.inputs["Color"])
    nt.links.new(gain.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    sepr = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(arm.outputs["Color"], sepr.inputs[0])
    rough = nt.nodes.new("ShaderNodeMix")
    rough.data_type = "FLOAT"
    nt.links.new(low.outputs["Result"], rough.inputs["Factor"])
    nt.links.new(sepr.outputs["Green"], rough.inputs["A"])
    rough.inputs["B"].default_value = 0.42
    nt.links.new(rough.outputs["Result"], b.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.7
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_floor() -> bpy.types.Material:
    """Паркет «ёлочкой» (дуб под старым лаком, тайл 2,1 м, раскладка под 45°)."""
    m = bpy.data.materials.new("паркет")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    mp = mapping(nt, 1.0 / 2.1, 45.0)
    alb = tex(nt, TEX + "/dorm_v3/floor_wood.webp", proj="FLAT")
    nrm = tex(nt, TEX + "/dorm_v3/floor_normal.png", True, proj="FLAT")
    for t in (alb, nrm):
        nt.links.new(mp.outputs[0], t.inputs["Vector"])
    hue = nt.nodes.new("ShaderNodeHueSaturation")
    hue.inputs["Value"].default_value = 0.8
    hue.inputs["Saturation"].default_value = 0.9
    nt.links.new(alb.outputs["Color"], hue.inputs["Color"])
    nt.links.new(hue.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.42
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.inputs["Strength"].default_value = 0.8
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    return m


def mat_plain(name, color, rough) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    return m


def box(bm, mn, mx) -> None:
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((V(mn) + V(mx)) / 2) @
                          Matrix.Diagonal((*[b - a for a, b in zip(mn, mx)], 1.0)))


def mesh_obj(name, bm, mat, coll) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.data.materials.append(mat)
    coll.objects.link(ob)
    return ob


def room(coll) -> None:
    wall, floor = mat_wall(), mat_floor()
    ceil = mat_plain("потолок_побелка", (0.82, 0.81, 0.77), 0.9)
    wood = mat_plain("плинтус_краска", (0.23, 0.11, 0.06), 0.45)
    frame = mat_plain("рама_окна", (0.80, 0.80, 0.76), 0.5)
    bm = bmesh.new()
    box(bm, (X0 - WALL, 0.0, 0.0), (X1 + WALL, WALL, H))                       # задняя
    box(bm, (X0 - WALL, Y0, 0.0), (X0, 0.0, H))                                # левая
    # правая с окном
    box(bm, (X1, Y0, 0.0), (X1 + WALL, WIN_Y[0], H))
    box(bm, (X1, WIN_Y[1], 0.0), (X1 + WALL, 0.0, H))
    box(bm, (X1, WIN_Y[0], 0.0), (X1 + WALL, WIN_Y[1], WIN_Z[0]))
    box(bm, (X1, WIN_Y[0], WIN_Z[1]), (X1 + WALL, WIN_Y[1], H))
    box(bm, (X0 - WALL, Y0 - WALL, 0.0), (X1 + WALL, Y0, H))                   # передняя (за камерой)
    mesh_obj("стены", bm, wall, coll)
    bm = bmesh.new()
    box(bm, (X0, Y0, -0.05), (X1, 0.0, 0.0))
    mesh_obj("пол", bm, floor, coll)
    bm = bmesh.new()
    box(bm, (X0 - WALL, Y0 - WALL, H), (X1 + WALL, WALL, H + 0.1))
    mesh_obj("потолок", bm, ceil, coll)
    bm = bmesh.new()
    box(bm, (X0, -0.02, 0.0), (X1, 0.0, 0.07))
    box(bm, (X0, Y0, 0.0), (X0 + 0.02, 0.0, 0.07))
    box(bm, (X1 - 0.02, Y0, 0.0), (X1, WIN_Y[0], 0.07))
    box(bm, (X1 - 0.02, WIN_Y[1], 0.0), (X1, 0.0, 0.07))
    box(bm, (X1 - 0.02, WIN_Y[0], 0.0), (X1, WIN_Y[1], 0.07))
    mesh_obj("плинтус", bm, wood, coll)
    # рама: коробка по проёму, импост и фрамуга — их тени ложатся на ковёр переплётом
    bm = bmesh.new()
    xm, f = X1 + 0.10, 0.05
    box(bm, (xm, WIN_Y[0], WIN_Z[0]), (xm + 0.07, WIN_Y[0] + f, WIN_Z[1]))
    box(bm, (xm, WIN_Y[1] - f, WIN_Z[0]), (xm + 0.07, WIN_Y[1], WIN_Z[1]))
    box(bm, (xm, WIN_Y[0], WIN_Z[0]), (xm + 0.07, WIN_Y[1], WIN_Z[0] + f))
    box(bm, (xm, WIN_Y[0], WIN_Z[1] - f), (xm + 0.07, WIN_Y[1], WIN_Z[1]))
    ymid = (WIN_Y[0] + WIN_Y[1]) / 2
    box(bm, (xm, ymid - 0.03, WIN_Z[0]), (xm + 0.07, ymid + 0.03, WIN_Z[1]))
    zt = WIN_Z[1] - 0.42
    box(bm, (xm, WIN_Y[0], zt - 0.025), (xm + 0.07, WIN_Y[1], zt + 0.025))
    box(bm, (X1 - 0.06, WIN_Y[0] - 0.05, WIN_Z[0] - 0.03), (X1 + 0.1, WIN_Y[1] + 0.05, WIN_Z[0]))  # подоконник
    mesh_obj("окно_рама", bm, frame, coll)


def place_items(src_root, coll) -> dict:
    out = {}
    for game, (at, rz) in PLACE.items():
        src = src_root.children.get(game)
        for ob in src.objects:
            if ob.type != "MESH":
                continue
            new = ob.copy()
            coll.objects.link(new)
            new.matrix_world = Matrix.Translation(at) @ Euler((0, 0, math.radians(rz))).to_matrix().to_4x4()
            new.hide_render = False
            new.hide_viewport = False
            out.setdefault(game, []).append(new)
    return out


def light(scene) -> None:
    w = bpy.data.worlds.new("вечер")
    scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(ROOT + "/assets/sky/belfast_sunset_puresky.hdr", check_existing=True)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(200))
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.6
    sun = bpy.data.objects.new("солнце", bpy.data.lights.new("солнце", "SUN"))
    scene.collection.objects.link(sun)
    sun.data.energy = 5.5
    sun.data.color = (1.0, 0.80, 0.58)
    sun.data.angle = math.radians(0.6)
    # из окна справа, к задней стене, чуть вниз: пятно ложится на ковёр скользом (~30° к стене)
    sun.rotation_euler = SUN.to_track_quat("-Z", "Y").to_euler()


def macro_target(scene, at) -> V:
    """Точка для крупного плана: светлая полоса ромба медальона (по обе стороны), на ворсе солнце, а в 3–6 см —
    тень переплёта окна (на её краю ворс читается лучше всего)."""
    dg = bpy.context.evaluated_depsgraph_get()

    def surface(x, z):
        hit, loc, *_ = scene.ray_cast(dg, V((x, -0.5, z)), V((0, 1, 0)))
        return loc if hit else None

    def lit(p):
        hit, *_ = scene.ray_cast(dg, p + V((0, -0.015, 0)), -SUN)
        return not hit

    best = None
    for side in (1, -1):
        for k in range(-45, 46):
            dy = k * 10.0  # мм от середины медальона вниз
            dx = (0.895 - abs(dy) / 600.0) * 420.0
            if dx < 40:
                continue
            x, z = at[0] + side * dx / 1000.0, at[2] + 1.0 - dy / 1000.0
            p = surface(x, z)
            if p is None or not lit(p):
                continue
            near = [surface(x + ox, z + oz) for ox, oz in ((0, 0.045), (0, -0.045), (0.045, 0), (-0.045, 0))]
            edge = sum(1 for q in near if q is not None and not lit(q))
            score = edge * 10 - abs(z - 1.4)
            if best is None or score > best[0]:
                best = (score, p)
    print("MACRO", best, flush=True)
    return best[1] if best else V((0.18, -0.02, 1.32))


def camera(scene, coll, name, loc, target, lens, fstop=None, focus=None):
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    coll.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (V(target) - V(loc)).to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    cam.data.sensor_width = 36
    cam.data.clip_start = 0.01
    if fstop:
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = fstop
        cam.data.dof.focus_distance = (V(focus or target) - V(loc)).length
    return cam


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:]
    out_blend = argv[0]
    shots_dir = argv[1] if len(argv) > 1 else None
    only = set(argv[2:])
    sc = bpy.context.scene
    src_root = bpy.data.collections["Развёртка_v01"]
    coll = bpy.data.collections.new(SCENE)
    sc.collection.children.link(coll)
    items = place_items(src_root, coll)
    # остальное в файле — не видно и не считается
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = lc.collection != coll
    for ob in sc.collection.objects:
        ob.hide_render = True
        ob.hide_set(True)
    room(coll)
    wool = next(o for o in items["furn_carpet"] if o.name.startswith("Ковёр_шерсть"))
    hair = CP.add_pile(wool, MAPS + "/furn_carpet/furn_carpet_baseColor.png")
    hair.hide_render = False
    for item in hair.modifiers["Ворс"].node_group.interface.items_tree:
        if item.item_type == "SOCKET" and item.name == "Доля во вьюпорте":
            item.default_value = 0.2
    light(sc)
    c1 = camera(sc, coll, "Кадр 1 — комната", (-1.55, -3.25, 1.5), (0.05, -0.2, 1.12), 24)
    c2 = camera(sc, coll, "Кадр 2 — ковёр", (1.05, -1.25, 1.42), (0.05, 0.0, 1.5), 45, 5.6, (0.15, -0.02, 1.55))
    foc = macro_target(sc, (0.0, 0.0, 0.62))
    # слева-спереди — против солнца: кончики ворса светятся по контуру
    c3 = camera(sc, coll, "Кадр 3 — ворс крупно", foc + V((-0.15, -0.26, 0.05)), foc, 85, 8.0, foc)
    sc.camera = c1
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "OPTIX"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "OPTIX"
    sc.cycles.device = "GPU"
    sc.cycles.samples = 384
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 8
    sc.cycles_curves.shape = "THICK"
    sc.cycles_curves.subdivisions = 2
    sc.render.resolution_x, sc.render.resolution_y = 1920, 1280
    sc.render.resolution_percentage = 100
    if os.environ.get("CARPET_QUICK"):  # проба кадров: вдвое меньше и мало выборок
        sc.cycles.samples = 48
        sc.render.resolution_percentage = 50
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.view_settings.exposure = 0.0
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                for sp in area.spaces:
                    if sp.type == "VIEW_3D":
                        sp.shading.type = "RENDERED"
                        sp.region_3d.view_perspective = "CAMERA"
    # ровно в ковёр: фокус — по лучу камеры до поверхности
    dg = bpy.context.evaluated_depsgraph_get()
    for cam in (c2, c3):
        d = cam.matrix_world.to_quaternion() @ V((0, 0, -1))
        hit, loc, *_ = sc.ray_cast(dg, cam.location, d)
        if hit:
            cam.data.dof.focus_distance = (loc - cam.location).length
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
    print("saved", out_blend, flush=True)
    if shots_dir:
        os.makedirs(shots_dir, exist_ok=True)
        for k, cam in enumerate((c1, c2, c3), 1):
            if only and str(k) not in only:
                continue
            sc.camera = cam
            sc.view_settings.exposure = EXPOSURE[k - 1]
            sc.render.filepath = os.path.join(shots_dir, f"carpet_{k}.png")
            bpy.ops.render.render(write_still=True)
            print("SHOT", k, cam.name, flush=True)


if __name__ == "__main__":
    main()
