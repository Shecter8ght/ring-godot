# «Частокол»: проба карт на файле просмотра без пересборки — карты указанных наборов берутся из другой папки
# (выгрузка пробы), кадры по видам tex_review.VIEWS; файл не сохраняется.
# blender -b "<Частокол_текстуры_этап1_v02.blend>" --factory-startup --python-exit-code 1 --python tools/pkp/tex_try.py -- <папка карт> <набор,набор> <папка кадров> <вид,вид> [samples]
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import tex_review as R  # noqa: E402

a = sys.argv[sys.argv.index("--") + 1:]
maps, sets, out, views = a[0], a[1].split(","), a[2], a[3].split(",")
samples = int(a[4]) if len(a) > 4 else 48
for img in bpy.data.images:
    fp = bpy.path.abspath(img.filepath)
    name = os.path.basename(fp)
    s = name.split("_")[0]
    if s in sets and os.path.exists(os.path.join(maps, name)):
        img.filepath = os.path.join(maps, name)
        img.reload()
import addon_utils
addon_utils.enable("cycles")
cp = bpy.context.preferences.addons["cycles"].preferences
cp.compute_device_type = "OPTIX"
cp.get_devices()
for dv in cp.devices:
    dv.use = dv.type != "CPU"
bpy.context.scene.cycles.device = "GPU"
R.shots(out, samples, views)
