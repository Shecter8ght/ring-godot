"""Проверочные рендеры сохранённой модели (ничего не сохраняет в .blend).

blender --background --factory-startup <file.blend> --python tools/mosin_pu/render_views.py -- \
    --out <папка> --prefix <имя> [--views side_r,side_l,top,front,rear,iso,iso_l,bottom]
    [--clay] [--res 1600x900] [--px_per_mm 20 --center x,y,z] [--hide obj1,obj2] [--only obj1,obj2]
    [--transparent] [--samples 64] [--cam view:dx,dy,dz:lens] [--focus x,y,z --dist mm]

Виды: side_r — правая сторона стрелка (камера на −Y, дуло вправо), side_l — левая, top — сверху,
front — с дула, rear — с затылка, iso — 3/4 спереди справа сверху (перспектива).
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

MM = 0.001


def parse():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--prefix", required=True)
    p.add_argument("--views", default="side_r,side_l,top,front,rear,iso")
    p.add_argument("--clay", action="store_true")
    p.add_argument("--res", default="1600x900")
    p.add_argument("--px_per_mm", type=float, default=0.0)
    p.add_argument("--center", default="")
    p.add_argument("--hide", default="")
    p.add_argument("--only", default="")
    p.add_argument("--transparent", action="store_true")
    p.add_argument("--samples", type=int, default=48)
    p.add_argument("--pad", type=float, default=1.08)
    p.add_argument("--focus", default="")
    p.add_argument("--dist", type=float, default=0.0)
    p.add_argument("--lens", type=float, default=50.0)
    p.add_argument("--dir", default="")
    p.add_argument("--name", default="")
    p.add_argument("--bg", type=float, default=0.42)
    return p.parse_args(argv)


VIEWS = {
    # направление взгляда камеры, вектор «вверх» кадра
    "side_r": (Vector((0, 1, 0)), Vector((0, 0, 1))),
    "side_l": (Vector((0, -1, 0)), Vector((0, 0, 1))),
    "top": (Vector((0, 0, -1)), Vector((0, 1, 0))),
    "bottom": (Vector((0, 0, 1)), Vector((0, -1, 0))),
    "front": (Vector((-1, 0, 0)), Vector((0, 0, 1))),
    "rear": (Vector((1, 0, 0)), Vector((0, 0, 1))),
    "iso": (Vector((-0.55, 0.75, -0.38)).normalized(), Vector((0, 0, 1))),
    "iso_l": (Vector((-0.55, -0.75, -0.38)).normalized(), Vector((0, 0, 1))),
    "iso_rear": (Vector((0.6, 0.7, -0.4)).normalized(), Vector((0, 0, 1))),
}


def visible_meshes(args):
    hide = set(filter(None, args.hide.split(",")))
    only = set(filter(None, args.only.split(",")))
    out = []
    for ob in bpy.context.scene.objects:
        if ob.type != "MESH":
            continue
        name_hit = lambda names: ob.name in names or any(  # noqa: E731
            (a.name in names) for a in _ancestors(ob))
        hidden = ob.hide_render or name_hit(hide) or (only and not name_hit(only))
        ob.hide_render = bool(hidden)
        if not hidden:
            out.append(ob)
    return out


def _ancestors(ob):
    p = ob.parent
    while p:
        yield p
        p = p.parent


def bbox(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi, pts


def setup_render(args, w, h):
    sc = bpy.context.scene
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    sc.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = args.transparent
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Base Contrast" if "AgX - Base Contrast" in [
        i.identifier for i in sc.view_settings.bl_rna.properties["look"].enum_items] else "None"
    try:
        sc.eevee.taa_render_samples = args.samples
        sc.eevee.use_shadows = True
        sc.eevee.shadow_ray_count = 3
        sc.eevee.shadow_step_count = 12
        sc.eevee.shadow_pool_size = "1024"
        sc.eevee.use_raytracing = True
    except AttributeError:
        pass
    world = bpy.data.worlds.new("StudioWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (args.bg, args.bg, args.bg, 1)
    bg.inputs["Strength"].default_value = 0.6
    sc.world = world
    if args.clay:
        clay = bpy.data.materials.new("ClayCheck")
        clay.use_nodes = True
        b = clay.node_tree.nodes["Principled BSDF"]
        b.inputs["Base Color"].default_value = (0.35, 0.35, 0.35, 1)
        b.inputs["Roughness"].default_value = 0.42
        bpy.context.view_layer.material_override = clay


def add_lights(center, size):
    def area(name, loc, energy, sz):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = sz
        # мелкая карта теней и разброс по сэмплам: без «пилы» тени на крупных планах
        ld.shadow_maximum_resolution = 0.0001
        ld.use_shadow_jitter = True
        ob = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(ob)
        ob.location = loc
        d = center - ob.location
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        return ob
    s = max(size, 0.05)
    # мощность ∝ квадрату расстояния — освещённость одинакова для патрона и винтовки
    for name, d, e, sz in (("Key", Vector((-0.4, -1.0, 1.1)), 9, 1.4), ("Fill", Vector((0.9, 1.0, 0.5)), 3.5, 1.8),
                           ("Rim", Vector((0.6, -0.3, -0.9)), 2.5, 1.2), ("Top", Vector((0.0, 0.0, 1.6)), 3, 2.0)):
        off = d * s * 1.6
        area(name, center + off, e * off.length_squared, s * sz)


def make_camera(view, args, lo, hi, pts, w, h):
    cam_d = bpy.data.cameras.new("CheckCam")
    cam = bpy.data.objects.new("CheckCam", cam_d)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    if args.dir:
        d = Vector(tuple(float(v) for v in args.dir.split(","))).normalized()
        up = Vector((0, 0, 1))
    else:
        d, up = VIEWS[view]
    center = (lo + hi) / 2
    if args.center:
        center = Vector(tuple(float(v) for v in args.center.split(","))) * MM
    if args.focus:
        center = Vector(tuple(float(v) for v in args.focus.split(","))) * MM
    rot = d.to_track_quat("-Z", "Y")
    # поправка «вверх»: повернуть вокруг оси взгляда так, чтобы up кадра совпал с заданным
    cam_up = rot @ Vector((0, 1, 0))
    up_proj = (up - d * up.dot(d))
    if up_proj.length > 1e-6:
        up_proj.normalize()
        ang = cam_up.angle(up_proj)
        if (cam_up.cross(up_proj)).dot(d) < 0:
            ang = -ang
        from mathutils import Quaternion
        rot = Quaternion(d, -ang) @ rot
    cam.rotation_euler = rot.to_euler()
    right = rot @ Vector((1, 0, 0))
    upv = rot @ Vector((0, 1, 0))
    diag = (hi - lo).length
    persp = view.startswith("iso") or args.dist > 0
    if persp:
        cam_d.type = "PERSP"
        cam_d.lens = args.lens
        if args.dist > 0:
            dist = args.dist * MM
        else:
            # ближайшее расстояние, при котором все точки модели в кадре (с запасом pad)
            half = (cam_d.sensor_width / 2) / args.lens
            tan_u, tan_v = (half, half * h / w) if w >= h else (half * w / h, half)
            dist = 0.0
            for p in pts:
                r = p - center
                depth_off = r.dot(d)
                dist = max(dist, args.pad * abs(r.dot(right)) / tan_u - depth_off,
                           args.pad * abs(r.dot(upv)) / tan_v - depth_off)
        cam.location = center - d * dist
        cam_d.clip_start = dist * 0.02
        cam_d.clip_end = dist * 10
    else:
        cam_d.type = "ORTHO"
        if args.px_per_mm > 0:
            cam_d.ortho_scale = (max(w, h) / args.px_per_mm) * MM
        else:
            us = [(p - center).dot(right) for p in pts]
            vs = [(p - center).dot(upv) for p in pts]
            eu = 2 * max(abs(min(us)), abs(max(us)))
            ev = 2 * max(abs(min(vs)), abs(max(vs)))
            aspect = w / h
            cam_d.ortho_scale = max(eu, ev * aspect) * args.pad if w >= h else max(eu / aspect, ev) * args.pad
        cam.location = center - d * diag * 2
        cam_d.clip_start = 0.001
        cam_d.clip_end = diag * 6
    return cam, center


def main():
    args = parse()
    w, h = (int(v) for v in args.res.split("x"))
    objs = visible_meshes(args)
    lo, hi, pts = bbox(objs)
    setup_render(args, w, h)
    center = (lo + hi) / 2
    add_lights(center, (hi - lo).length)
    os.makedirs(args.out, exist_ok=True)
    views = [args.name] if args.name else args.views.split(",")
    for view in views:
        cam, c = make_camera(view if not args.name else "iso", args, lo, hi, pts, w, h)
        path = os.path.join(args.out, f"{args.prefix}_{view}.png")
        bpy.context.scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("RENDER", path, "ortho_scale_m", round(cam.data.ortho_scale, 6), "center_mm",
              tuple(round(v / MM, 3) for v in c))
        bpy.data.objects.remove(cam, do_unlink=True)


main()
