# Цевьё Dolinskyi: карта нормалей high → low в Blender (Cycles), вместо запечённой Painter.
# Painter 12.1 читает FBX своим импортёром (кэш .assbin) и сам пересчитывает нормали low-poly: ни жёсткие рёбра, ни разрез
# по ним, ни нормали из файла до него не доходят (запекание с FBX «по граням» и с разрезом совпало до пикселя). Его карта
# компенсирует его нормали (разброс 0,24 против 0,03 у Blender) и на нормалях Blender даёт рябь вокруг окон (владелец 01.11).
# Здесь — под нормали самой сетки: 4096 с прореживанием до 2048 (сглаживание краёв), 16 бит, OpenGL.
#   blender --background <развёртка.blend> --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/bake_normal.py
import os

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "_asset_src", "handguard_dolinskyi", "sp", "handguard_normal_blender.png")
BIG, RES = 4096, 2048


def main():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(x.type == dev for x in prefs.devices):
                for x in prefs.devices:
                    x.use = x.type == dev
                sc.cycles.device = "GPU"
                break
        except Exception:      # noqa: BLE001
            continue
    sc.cycles.samples = 1
    lp = bpy.data.objects["handguard_low"]
    hp = bpy.data.objects["handguard_high"]
    for c in bpy.data.collections:
        c.hide_render = False
        c.hide_viewport = False
    img = bpy.data.images.new("bake_normal", BIG, BIG, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color"
    mat = bpy.data.materials.new("bake")
    mat.use_nodes = True
    lp.data.materials.clear()
    lp.data.materials.append(mat)
    t = mat.node_tree.nodes.new("ShaderNodeTexImage")
    t.image = img
    mat.node_tree.nodes.active = t
    bpy.ops.object.select_all(action="DESELECT")
    hp.select_set(True)
    lp.select_set(True)
    bpy.context.view_layer.objects.active = lp
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = 0.0007          # фаски high-poly 0,4 мм; перемычки между окнами ~3 мм — лучи не дальше 1,5 мм
    bk.max_ray_distance = 0.0015
    bk.margin = 16
    bk.normal_space = "TANGENT"
    bk.normal_g = "POS_Y"               # OpenGL, как у проекта Painter
    bpy.ops.object.bake(type="NORMAL")
    a = np.array(img.pixels[:], np.float32).reshape(BIG, BIG, 4)[..., :3]
    n = a * 2.0 - 1.0
    n = n.reshape(RES, 2, RES, 2, 3).mean(axis=(1, 3))     # 4096 → 2048: среднее 2×2 и снова единичная длина
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
    small = bpy.data.images.new("normal_2k", RES, RES, alpha=False, float_buffer=True)
    small.colorspace_settings.name = "Non-Color"
    px = np.concatenate([n * 0.5 + 0.5, np.ones((RES, RES, 1), np.float32)], axis=2)
    small.pixels.foreach_set(px.ravel())
    small.filepath_raw = OUT
    small.file_format = "PNG"
    sc.render.image_settings.color_depth = "16"
    small.save_render(OUT, scene=sc)
    flat = np.abs(n[..., :2]).mean()
    print("NORMAL", OUT, "средний наклон", round(float(flat), 4))


main()
