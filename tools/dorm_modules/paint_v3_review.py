"""Студия проверки краски v03 (REVIEW_KIND=wash — побелка и штукатурка до кирпича v03): стена 2,4 × 2,0 м, износ растёт слева направо (атрибут «Износ» + пятна по месту),
свет скользящий слева, как на образце «Cracked Paint», заполняющий от камеры и лампа сверху, как в коридоре.
Камеры: вблизи наискось (кадр ~40 см), кромка отслоения вблизи, средний план (~1,3 м), общий (~3 м).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 \
      --python tools/dorm_modules/paint_v3_review.py -- <выход.blend> <папка кадров> [вблизи кромка средний общий …]
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paint_v3  # noqa: E402
from texture_layers import param, wear_attr, world_noise  # noqa: E402
from texture_modules import G  # noqa: E402

W, H = 2.4, 2.0


def wall() -> bpy.types.Object:
    """Плоская стена в плоскости XZ лицом к −Y, сетка 5 см под кисть износа, развёртка в метрах."""
    nx, nz = 48, 40
    verts, faces = [], []
    for j in range(nz + 1):
        for i in range(nx + 1):
            verts.append((W * i / nx, 0.0, H * j / nz))
    for j in range(nz):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    me = bpy.data.meshes.new("Стена_проба")
    me.from_pydata(verts, [], faces)
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, co.z)
    attr = me.color_attributes.new("Износ", "FLOAT_COLOR", "POINT")
    for i, v in enumerate(me.vertices):
        attr.data[i].color = (0.42 * v.co.x / W, 0.0, 0.0, 1.0)
    me.update()
    # Лицом к −Y: грани собраны против часовой при взгляде с +Y, поэтому переворачиваем.
    me.flip_normals()
    ob = bpy.data.objects.new("Стена_проба", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material() -> bpy.types.Material:
    m = bpy.data.materials.new("Краска_v3")
    g = G(m)
    w = wear_attr(g)
    base = param(g, "Износ краски, база", 0.03)
    var = g.math("SUBTRACT", g.math("MULTIPLY", world_noise(g, 0.45), 1.4), 0.55)
    wear = g.math("ADD", g.math("ADD", base, g.math("MULTIPLY", w[0], 1.0)), g.math("MULTIPLY", var, 0.22), True)
    vec = g.uv(0.5)
    color, rough, nrm = paint_v3.paint_v3(g, vec, wear)
    g.out_bsdf(color, rough, nrm)
    return m


def material_wash() -> bpy.types.Material:
    """Побелка → штукатурка → кирпич: тот же атрибут «Износ» ведёт и облетание, и (слабее) отвал до кирпича."""
    import plaster_v3
    m = bpy.data.materials.new("Побелка_v3")
    g = G(m)
    w = wear_attr(g)
    base = param(g, "Облетание побелки, база", 0.04)
    base_l = param(g, "Штукатурка до кирпича, база", 0.0)
    var = g.math("SUBTRACT", g.math("MULTIPLY", world_noise(g, 0.45), 1.4), 0.55)
    wash = g.math("ADD", g.math("ADD", base, g.math("MULTIPLY", w[0], 1.0)), g.math("MULTIPLY", var, 0.22), True)
    loss = g.math("ADD", g.math("ADD", base_l, g.math("MULTIPLY", w[0], 0.22)), g.math("MULTIPLY", var, 0.06), True)
    import tiles_v3
    vec, frame = tiles_v3.surface_coords(g, 0.5)
    color, rough, nrm = plaster_v3.wash_v3(g, vec, wash, loss, frame,
                                           coords=lambda pos: tiles_v3.surface_coords(g, 0.5, pos)[0])
    g.out_bsdf(color, rough, nrm)
    return m


def floor_plane() -> bpy.types.Object:
    """Пол 2,4 × 2,4 м на z = 0 лицом вверх."""
    me = bpy.data.meshes.new("Пол_проба")
    me.from_pydata([(-1.2, -1.2, 0), (1.2, -1.2, 0), (1.2, 1.2, 0), (-1.2, 1.2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (co.x, co.y)
    me.update()
    ob = bpy.data.objects.new("Пол_проба", me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def material_floor() -> bpy.types.Material:
    import floor_v3
    m = bpy.data.materials.new("Паркет_v3")
    g = G(m)
    color, rough, nrm = floor_v3.floor_v3(g)
    g.out_bsdf(color, rough, nrm)
    return m


def scene_floor() -> dict:
    """Студия пола: лампа под потолком 3 м, слабый скользящий свет из «окна», камеры с высоты глаз и вблизи."""
    ob = floor_plane()
    ob.data.materials.append(material_floor())
    light("Лампа_сверху", "AREA", (0.2, 0.3, 2.95), (0.2, 0.3, 0.0), 120, (1.0, 0.82, 0.62), (0.3, 0.3))
    light("Свет_окно", "AREA", (-3.0, 0.0, 1.2), (0.0, 0.0, 0.0), 260, (0.9, 0.95, 1.0), (1.0, 1.0))
    return {
        "вблизи": cam("Камера_пол_вблизи", (0.0, -0.75, 0.55), (0.25, 0.05, 0.0), 35),
        "средний": cam("Камера_пол_средний", (0.0, -1.6, 1.62), (0.1, 0.5, 0.0), 30),
        "общий": cam("Камера_пол_общий", (0.0, -0.4, 2.4), (0.0, 0.25, 0.0), 24),
    }


def quad(name: str, verts) -> bpy.types.Object:
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], [(0, 1, 2, 3)])
    me.uv_layers.new(name="UVMap")
    me.update()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def scene_tiles() -> dict:
    """Угол душевой 2,4 × 2,4 м: пол и две стены, плитка на стенах — на всю высоту (верх с побелкой — в модулях)."""
    import tiles_v3
    mw = bpy.data.materials.new("Плитка_стена_v3")
    g = G(mw)
    c, r, n = tiles_v3.tiles_v3(g)
    g.out_bsdf(c, r, n)
    mf = bpy.data.materials.new("Плитка_пол_v3")
    g = G(mf)
    c, r, n = tiles_v3.tiles_v3(g, "7d5f4c", 1.0, "6a4f3f")
    g.out_bsdf(c, r, n)
    fl = quad("Пол_душевой", [(0, 0, 0), (2.4, 0, 0), (2.4, 2.4, 0), (0, 2.4, 0)])
    fl.data.materials.append(mf)
    wa = quad("Стена_А", [(0, 2.4, 0), (2.4, 2.4, 0), (2.4, 2.4, 2.4), (0, 2.4, 2.4)])     # лицом к −Y
    wa.data.flip_normals()
    wa.data.materials.append(mw)
    wb = quad("Стена_Б", [(2.4, 0, 0), (2.4, 2.4, 0), (2.4, 2.4, 2.4), (2.4, 0, 2.4)])     # лицом к −X
    wb.data.materials.append(mw)
    light("Лампа_душевая", "AREA", (1.2, 1.2, 2.9), (1.2, 1.2, 0.0), 90, (0.92, 0.95, 1.0), (0.5, 0.15))
    light("Свет_дверь", "AREA", (0.0, -1.0, 1.4), (1.6, 1.6, 1.0), 120, (1.0, 0.85, 0.65), (0.8, 1.6))
    return {
        "общий": cam("Камера_душевая", (0.3, 0.2, 1.62), (2.2, 2.2, 0.9), 22),
        "средний": cam("Камера_душевая_стена", (1.0, 1.25, 1.5), (1.6, 2.4, 1.2), 30),
        "вблизи": cam("Камера_душевая_пол", (1.0, 0.8, 0.9), (1.7, 1.6, 0.0), 35),
    }


def light(name, kind, at, target, energy, color, size):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = energy
    ld.color = color
    if kind == "AREA":
        ld.shape = "RECTANGLE"
        ld.size, ld.size_y = size
    ob = bpy.data.objects.new(name, ld)
    ob.location = at
    ob.rotation_euler = (Vector(target) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cam(name, eye, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    ob = bpy.data.objects.new(name, cd)
    ob.location = eye
    ob.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def scene() -> dict:
    sc = bpy.context.scene
    for ob in list(sc.objects):
        bpy.data.objects.remove(ob)
    sc.render.engine = "BLENDER_EEVEE"
    sc.eevee.taa_render_samples = 64
    try:
        sc.eevee.use_raytracing = True
        sc.eevee.use_shadows = True
    except AttributeError:
        pass
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast"
    sc.render.resolution_x, sc.render.resolution_y = 1600, 900
    world = bpy.data.worlds.new("Студия_краска")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.30, 0.32, 0.34, 1.0)
    bg.inputs[1].default_value = 0.06
    sc.world = world
    if os.environ.get("REVIEW_KIND") == "tiles":
        cams = scene_tiles()
        sc.camera = cams["общий"]
        return cams
    if os.environ.get("REVIEW_KIND") == "floor":
        cams = scene_floor()
        sc.camera = cams["средний"]
        return cams
    ob = wall()
    ob.data.materials.append(material_wash() if os.environ.get("REVIEW_KIND") == "wash" else material())
    light("Свет_скользящий", "AREA", (-0.35, -0.2, 1.5), (1.2, 0.0, 1.0), 280, (1.0, 0.95, 0.88), (0.4, 0.4))
    light("Свет_от_камеры", "AREA", (1.2, -2.2, 1.4), (1.2, 0.0, 1.0), 14, (0.92, 0.96, 1.0), (1.2, 1.2))
    light("Лампа_сверху", "AREA", (1.2, -0.9, 2.95), (1.2, -0.9, 0.0), 55, (1.0, 0.8, 0.58), (0.25, 0.25))
    cams = {
        "вблизи": cam("Камера_вблизи", (1.22, -0.33, 1.42), (1.6, 0.0, 1.3), 35),
        "кромка": cam("Камера_кромка", (0.84, -0.32, 1.26), (1.2, 0.0, 1.12), 35),
        "средний": cam("Камера_средний", (1.2, -1.25, 1.15), (1.2, 0.0, 1.0), 35),
        "общий": cam("Камера_общий", (1.2, -2.7, 1.6), (1.2, 0.0, 1.0), 30),
    }
    sc.camera = cams["вблизи"]
    return cams


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_blend = argv[0]
    shots = argv[1] if len(argv) > 1 else None
    views = argv[2:] or ["вблизи", "кромка", "средний", "общий"]
    cams = scene()
    os.makedirs(os.path.dirname(out_blend), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=out_blend, compress=True)
    if shots:
        os.makedirs(shots, exist_ok=True)
        sc = bpy.context.scene
        for v in views:
            if v not in cams:
                continue
            sc.camera = cams[v]
            kind = {"wash": "wash_v3", "floor": "floor_v3", "tiles": "tiles_v3"}.get(os.environ.get("REVIEW_KIND", ""), "paint_v3")
            sc.render.filepath = os.path.join(shots, f"{kind}_{v}.png")
            bpy.ops.render.render(write_still=True)
            print("кадр", sc.render.filepath)


if __name__ == "__main__":
    main()
