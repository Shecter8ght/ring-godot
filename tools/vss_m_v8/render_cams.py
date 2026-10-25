# Рендер камер сцены: -- <out_dir> <камера,камера> [ширина] [сэмплы]
import os
import sys
import bpy

a = sys.argv[sys.argv.index("--") + 1:]
out, cams = a[0], a[1].split(",")
w = int(a[2]) if len(a) > 2 else 1280
spp = int(a[3]) if len(a) > 3 else 64
sc = bpy.context.scene
prefs = bpy.context.preferences.addons["cycles"].preferences
for dev_type in ("OPTIX", "CUDA"):
    try:
        prefs.compute_device_type = dev_type
        prefs.get_devices()
        if any(d.type == dev_type for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == dev_type
            sc.cycles.device = "GPU"
            break
    except Exception:
        continue
sc.render.resolution_x = w
sc.render.resolution_y = int(w * 9 / 16)
sc.cycles.samples = spp
sc.cycles.denoising_use_gpu = False      # видеопамять может держать Substance Painter
os.makedirs(out, exist_ok=True)
for c in cams:
    sc.camera = bpy.data.objects[c]
    sc.render.filepath = os.path.join(out, c + ".png")
    bpy.ops.render.render(write_still=True)
