# AR-15: файл выдачи геометрии владельцу — нейтральные материалы, вьюпорт «глина» с кромками и полостями,
# свет студии, камера на 3/4. Запуск на собранном .blend:
# blender -b <AR15_geometry.blend> --python tools/ar15/delivery.py -- <out.blend>
import math
import sys
import bpy
from mathutils import Vector


# цвета вьюпорта (только «Solid»): светлая глина, детали различимы по материалу; цвета рендера не меняются
VIEW_COLORS = {
    "Alu_anodized": (0.42, 0.43, 0.45),
    "Steel_black": (0.30, 0.31, 0.33),
    "Steel_nitride": (0.36, 0.36, 0.38),
    "Steel_bare": (0.62, 0.62, 0.64),
    "Polymer": (0.24, 0.24, 0.23),
    "Rubber": (0.14, 0.14, 0.14),
    "Spring_steel": (0.50, 0.50, 0.52),
    "Brass": (0.78, 0.60, 0.30),
    "Bullet_jacket": (0.72, 0.45, 0.30),
}


def main():
    a = sys.argv[sys.argv.index("--") + 1:]
    out = a[0]
    sc = bpy.context.scene
    for m in bpy.data.materials:
        for key, col in VIEW_COLORS.items():
            if m.name.startswith(key):
                m.diffuse_color = (*col, 1.0)
                m.roughness = 0.5
                m.metallic = 0.0
    # камера на 3/4 справа
    cd = bpy.data.cameras.new("Cam_3q")
    cam = bpy.data.objects.new("Cam_3q", cd)
    sc.collection.objects.link(cam)
    cam.location = Vector((0.40, -0.78, 0.28))
    d = Vector((-0.02, 0.0, -0.04)) - cam.location
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cd.lens = 50
    cd.clip_start = 0.005
    sc.camera = cam
    sc.render.resolution_x = 1920
    sc.render.resolution_y = 1080
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type != "VIEW_3D":
                    continue
                sh = sp.shading
                sh.type = "SOLID"
                sh.light = "STUDIO"
                sh.color_type = "MATERIAL"
                sh.show_cavity = True
                sh.cavity_type = "BOTH"
                sh.curvature_ridge_factor = 0.6
                sh.show_specular_highlight = True
                sp.clip_start = 0.002
                sp.clip_end = 50.0
                sp.overlay.show_relationship_lines = False
                r3 = sp.region_3d
                r3.view_location = Vector((-0.02, 0.0, -0.04))
                r3.view_distance = 0.9
                r3.view_rotation = (cam.rotation_euler.to_quaternion())
                r3.view_perspective = "PERSP"
    # управление — выбранным, чтобы свойства сразу были видны на панели объекта
    ctrl = bpy.data.objects.get("AR15_Controls")
    if ctrl is not None:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        ctrl.select_set(True)
        bpy.context.view_layer.objects.active = ctrl
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


main()
