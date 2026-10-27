# ВСС-М v8: высококачественные рендеры для владельца (износ и блеск): «в воздухе» в студии и на столе.
# blender --background "<папка сдачи>/ВСС-М_v8_студия.blend" --python-exit-code 1 --python tools/vss_m_v8/render_hq.py -- \
#   studio <файл.png> [ширина высота сэмплы]
# blender --background "<папка сдачи>/ВСС-М_v8_на_столе.blend" … -- table <файл.png> [ширина высота сэмплы]
# Студия: свой свет вместо студии осмотра — большой софтбокс сверху (блик по крышке, гребню приклада, муфте), узкая
# полоса сбоку под скользящим углом (сатиновый блеск боковин и протёртые кромки), контровая полоса сзади, фон —
# тёмно-серый, не чёрный (силуэт и износ на чёрном металле видны). Магазины на 20 и 30 спрятаны (в студии висят на
# месте магазина на 10). Стол: свет и окружение сцены, своя низкая камера со стороны приклада.
import math
import sys

import bpy
from mathutils import Vector


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    mode, out = a[0], a[1]
    w = int(a[2]) if len(a) > 2 else 3840
    h = int(a[3]) if len(a) > 3 else 2160
    spp = int(a[4]) if len(a) > 4 else 512
    return mode, out, w, h, spp


def descendants(o):
    out = [o]
    for c in o.children:
        out += descendants(c)
    return out


def bounds(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


def area(coll, name, loc, tgt, size, power, color=(1.0, 1.0, 1.0)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.shape = "RECTANGLE"
    ld.size, ld.size_y = size
    ld.energy = power
    ld.color = color
    lo = bpy.data.objects.new(name, ld)
    coll.objects.link(lo)
    lo.location = loc
    lo.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return lo


def camera(name, eye, tgt, lens, fstop=None, focus=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_start = 0.01
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    cam.location = eye
    cam.rotation_euler = (Vector(tgt) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = (Vector(focus or tgt) - Vector(eye)).length
    bpy.context.scene.camera = cam
    return cam


def rifle_meshes():
    root = bpy.data.objects["VSS_M_v8"]
    spare = ("Magazine_20", "Magazine_30")
    return [o for o in descendants(root) if o.type == "MESH" and o.visible_get()
            and not any(p.name.startswith(spare) for p in [o] + list(_parents(o)))]


def _parents(o):
    while o.parent:
        o = o.parent
        yield o


def studio():
    sc = bpy.context.scene
    # магазины на 20 и 30 в студии висят на месте магазина на 10 — прячем
    for name in ("Magazine_20", "Magazine_30"):
        o = bpy.data.objects.get(name)
        if o:
            for d in descendants(o):
                d.hide_render = True
                d.hide_viewport = True
    for o in list(bpy.data.collections["Studio"].objects) if "Studio" in bpy.data.collections else []:
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    lc = bpy.data.collections.get("Studio") or bpy.data.collections.new("Studio")
    if lc.name not in sc.collection.children:
        sc.collection.children.link(lc)
    lo, hi = bounds(rifle_meshes())
    c = (lo + hi) / 2
    print("HQ bounds", [round(v, 3) for v in lo], [round(v, 3) for v in hi])
    # фон камеры — тёмно-серый; отражения — студийная панорама слабо
    nt = sc.world.node_tree
    for n in nt.nodes:
        if n.bl_idname == "ShaderNodeBackground":
            col = tuple(n.inputs[0].default_value)[:3]
            if max(col) < 0.05 and not n.inputs[0].is_linked:
                n.inputs[0].default_value = (0.03, 0.031, 0.034, 1.0)
            elif n.inputs[0].is_linked:
                n.inputs[1].default_value = 0.12
    # свет: камера слева спереди сверху (+Y — левая сторона стрелка)
    # софтбокс сверху чуть за винтовкой: блик ложится по верхним граням полосой, а не заливает цилиндры серым
    area(lc, "HQ_Key_top", c + Vector((0.05, -0.3, 1.0)), c, (1.9, 0.5), 230.0, (1.0, 0.96, 0.9))
    area(lc, "HQ_Side_strip", c + Vector((0.75, 1.05, 0.15)), c + Vector((0.0, 0.0, 0.02)), (0.16, 1.5), 35.0, (1.0, 0.98, 0.95))
    # узкая полоса в зеркальном положении для боковин: блеск воронения и лака читается полосой поперёк левой стороны
    area(lc, "HQ_Gloss_strip", c + Vector((-0.55, 1.1, 0.1)), c, (0.12, 1.2), 35.0, (1.0, 0.98, 0.95))
    area(lc, "HQ_Rim_back", c + Vector((-0.1, -1.0, 0.45)), c, (2.4, 0.25), 190.0, (0.9, 0.95, 1.0))
    sc.view_settings.exposure = -0.35
    camera("HQ_Cam_Studio", c + Vector((0.5, 1.3, 0.4)), c + Vector((0.03, 0.0, -0.02)), 55.0)


def table():
    sc = bpy.context.scene
    objs = rifle_meshes()
    lo, hi = bounds(objs)
    rl = bpy.data.objects["Receiver_lower"]
    rlo, rhi = bounds([rl])
    rc = (rlo + rhi) / 2
    top = lo.z
    print("HQ bounds", [round(v, 3) for v in lo], [round(v, 3) for v in hi], "receiver", [round(v, 3) for v in rc])
    # с угла стола со стороны приклада, сверху под ~30°: винтовка по диагонали целиком, прицелы и магазины рядом;
    # резкость — на коробке
    eye = Vector((rc.x - 0.55, rc.y - 0.68, rc.z + 0.47))
    tgt = Vector((rc.x + 0.03, rc.y - 0.01, rc.z - 0.01))
    camera("HQ_Cam_Table", eye, tgt, 38.0, 8.0, rc)


def main():
    mode, out, w, h, spp = args()
    sc = bpy.context.scene
    {"studio": studio, "table": table}[mode]()
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = spp
    sc.cycles.use_adaptive_sampling = True
    sc.cycles.adaptive_threshold = 0.008
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
    sc.cycles.denoising_use_gpu = True
    sc.cycles.caustics_reflective = False
    sc.cycles.caustics_refractive = False
    sc.render.resolution_x = w
    sc.render.resolution_y = h
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = False
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGB"
    sc.render.image_settings.color_depth = "8"
    sc.render.filepath = out
    bpy.ops.render.render(write_still=True)
    print("HQ saved", out, w, h, spp)


main()
