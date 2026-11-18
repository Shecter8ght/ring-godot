# ВЕРАС-54 v14: проверочные виды в глине (Workbench) камерами образца.
#   blender --background <файл.blend> --python tools/veras54_v14/geo/shots.py -- <папка> <вид,вид…> [--pose имя,…]
#       [--hide имя,…] [--show коллекция,…] [--k 1.0] [--tag приставка]
# Вид: имя из refs/views.json (обзорные снимки образца: R02_receiver_right …), имя плитки образца из refs/tiles
# (R_x-0.20_z0.265_f1.0, T_x0.02_f1.0 …) — камера та же, кадр ложится на снимок образца (compare.py), или свой:
# «имя:x:y:z:куда_x:куда_y:куда_z:угол» — откуда и куда в мм осей ВЕРАС, угол зрения по вертикали в градусах.
# Камера всегда перспективная с узким углом (как у снимков образца). --k — множитель размера кадра 1063 × 845.
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ref_tiles  # noqa: E402

MM = 0.001
W, H = 1063, 845
DX, DZ = ref_tiles.DX, ref_tiles.DZ


def to_veras(p):
    """Точка образца (метры) → мм ВЕРАС."""
    return Vector((p[0] * 1000 + DX, p[1] * 1000, p[2] * 1000 + DZ))


def tile_camera(name):
    kind, cu, cv, s, dist, su, sv = ref_tiles.camera(name)
    f = float(name.rsplit("_f", 1)[1])
    if kind == "R":
        return Vector((cu, -dist, cv)), Vector((cu, 0, cv)), f
    if kind == "L":
        return Vector((cu, dist, cv)), Vector((cu, 0, cv)), f
    if kind == "T":
        return Vector((cu, -30, 20.5 + dist)), Vector((cu, 0, 20.5)), f
    if kind == "U":
        return Vector((cu, -30, -79.5 - dist)), Vector((cu, 0, -79.5)), f
    if kind == "B":
        return Vector((DX - dist, 0, cv)), Vector((DX, 0, cv)), f
    return Vector((DX + dist, 0, cv)), Vector((DX, 0, cv)), f


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = os.path.abspath(argv[0])
    names = argv[1].split(",")
    pose = None; hide = []; show = []; tag = ""; k = 1.0
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--pose": pose = argv[i + 1]
        elif a == "--hide": hide = argv[i + 1].split(",")
        elif a == "--show": show = argv[i + 1].split(",")
        elif a == "--tag": tag = argv[i + 1]
        elif a == "--k": k = float(argv[i + 1])
        i += 2
    os.makedirs(out, exist_ok=True)
    known = {v["name"]: v for v in json.load(open(os.path.join(ref_tiles.ROOT, "refs", "views.json"), encoding="utf-8"))}
    sc = bpy.context.scene
    vl = bpy.context.view_layer

    def walk(lc):
        yield lc
        for c in lc.children:
            yield from walk(c)
    for lc in walk(vl.layer_collection):
        if lc.name in hide: lc.exclude = True
        if lc.name in show: lc.exclude = False
    for o in bpy.data.objects:
        if o.name in hide or o.type in ("LIGHT", "FONT"):
            o.hide_render = True
    if pose:
        import part_rig
        ctrl = bpy.data.objects["VERAS54_Controls"]
        for pz in pose.split(","):
            for key, val in part_rig.POSES[pz].items():
                ctrl[key] = val
        ctrl.update_tag()
        vl.update()
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"; sh.color_type = "SINGLE"; sh.single_color = (0.62, 0.62, 0.64)
    sh.show_specular_highlight = True; sh.show_cavity = True; sh.cavity_type = "BOTH"
    sh.curvature_ridge_factor = 0.7; sh.curvature_valley_factor = 1.0
    sh.cavity_ridge_factor = 0.6; sh.cavity_valley_factor = 0.9
    sh.show_shadows = False; sh.show_object_outline = False
    sc.display.render_aa = "16"
    if sc.world is None:
        sc.world = bpy.data.worlds.new("w")
    sc.world.color = (0.03, 0.03, 0.03)
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "JPEG"; sc.render.image_settings.quality = 93
    sc.render.resolution_x = int(W * k); sc.render.resolution_y = int(H * k); sc.render.resolution_percentage = 100
    cam = bpy.data.cameras.new("shot_cam"); co = bpy.data.objects.new("shot_cam", cam)
    sc.collection.objects.link(co); sc.camera = co
    cam.clip_start = 0.05; cam.clip_end = 30.0; cam.sensor_fit = "VERTICAL"
    for n in names:
        if ":" in n:
            q = n.split(":")
            n, eye, tgt, fov = q[0], Vector(map(float, q[1:4])), Vector(map(float, q[4:7])), float(q[7])
        elif n in known:
            v = known[n]
            eye, tgt, fov = to_veras(v["eye"]), to_veras(v["target"]), v["fov"]
        else:
            eye, tgt, fov = tile_camera(n)
        co.location = eye * MM
        co.rotation_euler = (tgt - eye).to_track_quat("-Z", "Y").to_euler()
        cam.angle_y = math.radians(fov)
        sc.render.filepath = os.path.join(out, tag + n + (("_" + pose.replace(",", "_")) if pose else "") + ".jpg")
        bpy.ops.render.render(write_still=True)
        print("SHOT", sc.render.filepath)


main()
