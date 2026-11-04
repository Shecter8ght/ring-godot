# ПП по мотивам KRISS Vector: файл выдачи владельцу из собранного — вьюпорт «глина» с цветами материалов, камера 3/4,
# выбрана пустышка SMG03_Controls (подвижное — её свойствами 0…1), коллекция магазина на 30 включена (видимость — mag30).
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" -b <собранный.blend> --python tools/smg03/delivery.py -- <выдача.blend>
import math
import sys
import bpy
from mathutils import Vector

out = sys.argv[sys.argv.index("--") + 1]
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            for sp in area.spaces:
                if sp.type == "VIEW_3D":
                    sp.shading.type = "SOLID"
                    sp.shading.color_type = "MATERIAL"
                    sp.shading.light = "STUDIO"
                    sp.shading.show_cavity = True
                    sp.clip_start = 0.001
cam = bpy.data.objects.get("Camera_view") or bpy.data.objects.new("Camera_view", bpy.data.cameras.new("Camera_view"))
if cam.name not in bpy.context.scene.collection.objects:
    bpy.context.scene.collection.objects.link(cam)
cam.location = Vector((0.45, 0.62, 0.32))
d = (Vector((-0.12, 0.0, -0.03)) - cam.location).normalized()
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 50
cam.data.clip_start = 0.005
bpy.context.scene.camera = cam
ctrl = bpy.data.objects["SMG03_Controls"]
for o in bpy.context.view_layer.objects:
    o.select_set(False)
ctrl.select_set(True)
bpy.context.view_layer.objects.active = ctrl
bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
print("DELIVERED", out)
