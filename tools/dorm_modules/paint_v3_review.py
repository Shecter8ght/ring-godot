"""Студия проверки краски v03: стена 2,4 × 2,0 м, износ растёт слева направо (атрибут «Износ» + пятна по месту),
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
    ob = wall()
    ob.data.materials.append(material())
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
            sc.camera = cams[v]
            sc.render.filepath = os.path.join(shots, f"paint_v3_{v}.png")
            bpy.ops.render.render(write_still=True)
            print("кадр", sc.render.filepath)


if __name__ == "__main__":
    main()
