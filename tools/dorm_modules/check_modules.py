"""Проверка модулей общежития: размеры и замкнутость каждой детали, рабочие кадры Workbench.

Запуск:
  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background <файл .blend> --python-exit-code 1 \
      --python tools/dorm_modules/check_modules.py -- <папка кадров> [вид …]
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

# Имя → (откуда, куда, фокусное, мм).
VIEWS = {
    "door_corridor": ((0.9, 3.2, 1.55), (0.0, 0.0, 1.35), 35),
    "door_room": ((-1.0, -3.2, 1.5), (0.0, -0.1, 1.3), 35),
    "door_handle": ((0.78, -0.62, 1.12), (0.52, -0.22, 1.03), 50),
    "door_hinge": ((-0.35, -0.75, 2.32), (-0.6, -0.2, 2.16), 50),
    "door_top": ((0.35, 1.0, 2.75), (0.0, 0.19, 2.5), 35),
    "window_room": ((4.7, 3.2, 1.45), (4.0, 0.2, 1.45), 35),
    "window_sash": ((3.75, 0.9, 2.25), (3.45, -0.1, 2.15), 45),
    "window_outside": ((4.6, -3.6, 1.7), (4.0, -0.3, 1.6), 35),
    "radiator": ((4.65, 1.35, 0.75), (4.15, 0.38, 0.45), 40),
    "skirting": ((8.2, 1.7, 0.45), (7.9, 0.55, 0.04), 45),
    "glazed_door": ((11.8, 3.6, 1.6), (11.0, 0.0, 1.45), 30),
    "corridor_bay": ((-0.9, -8.0, 1.62), (5.5, -8.4, 1.5), 20),
    "corridor_bay_up": ((1.0, -8.6, 1.62), (3.6, -7.8, 2.9), 18),
    "stair_core": ((14.8, -11.6, 2.9), (12.0, -7.3, 1.3), 22),
    "stair_rail": ((10.9, -5.5, 3.0), (12.0, -6.95, 2.5), 28),
    "ceiling_seam": ((2.6, -8.9, 1.7), (2.2, -7.6, 3.0), 24),
    "wall_close": ((0.4, -8.4, 1.3), (-0.3, -9.7, 1.2), 28),
    "wall_upper": ((3.9, -7.6, 1.7), (4.6, -6.3, 2.5), 30),
    "floor_close": ((1.0, -7.4, 1.4), (2.0, -8.3, 0.0), 30),
    "shower": ((42.3, -7.6, 1.6), (40.4, -5.6, 1.0), 22),
    "shower_floor": ((41.6, -7.0, 1.2), (41.0, -5.9, 0.0), 30),
    "flight_side": ((16.0, 2.5, 1.2), (17.0, -0.5, 0.9), 28),
}


def audit() -> dict:
    dg = bpy.context.evaluated_depsgraph_get()
    report = {}
    for ob in bpy.data.objects:
        if ob.type != "MESH":
            continue
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        open_edges = sum(1 for e in bm.edges if not e.is_manifold)
        pts = [ob.matrix_world @ v.co for v in me.vertices]
        mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
        mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
        report[ob.name] = {"tris": sum(len(p.vertices) - 2 for p in me.polygons), "open_edges": open_edges,
                           "min": [round(c, 4) for c in mn], "max": [round(c, 4) for c in mx],
                           "size": [round(c, 4) for c in (mx - mn)]}
        bm.free()
        ev.to_mesh_clear()
    return report


def render(out_dir: str, names: list, eevee: bool = False) -> None:
    """Workbench — для формы; eevee — с материалами и светом студии файла (кадры tex_*)."""
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE" if eevee else "BLENDER_WORKBENCH"
    sc.render.resolution_x, sc.render.resolution_y = 1280, 800
    prefix = "tex_" if eevee else "check_"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "MATERIAL"
    sh.show_cavity = True
    sh.cavity_type = "BOTH"
    sh.show_shadows = True
    sh.show_specular_highlight = True
    sc.display.shadow_focus = 0.4
    cam = bpy.data.objects.get("check_cam") or bpy.data.objects.new("check_cam", bpy.data.cameras.new("check_cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam
    cam.data.clip_start = 0.01
    for name in names:
        eye, target, lens = VIEWS[name]
        cam.location = eye
        cam.rotation_euler = (Vector(target) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        cam.data.lens = lens
        sc.render.filepath = os.path.join(out_dir, f"{prefix}{name}.png")
        bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    eevee = "--eevee" in argv
    argv = [a for a in argv if a != "--eevee"]
    out_dir = argv[0]
    os.makedirs(out_dir, exist_ok=True)
    rep = audit()
    with open(os.path.join(out_dir, "audit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    bad = {k: v["open_edges"] for k, v in rep.items() if v["open_edges"]}
    print("objects", len(rep), "tris", sum(v["tris"] for v in rep.values()), "open", json.dumps(bad, ensure_ascii=False))
    render(out_dir, argv[1:] or list(VIEWS), eevee)
