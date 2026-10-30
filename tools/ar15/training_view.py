# AR-15, тренировочная копия Painter: файл просмотра в Blender для владельца. Берёт принятый файл износа со студией,
# переводит все карты наборов (<набор>_baseColor / _occlusionRoughnessMetallic / _normal.png) на папку «Карты» рядом с
# новым файлом и кладёт туда те же карты, что были. Владелец выгружает из тренировочного проекта Painter в «Карты»
# (пресет glTF PBR Metal Roughness) — файл просмотра показывает его работу: открыть заново или Image → Reload All.
# Геометрия, студия и камеры — как в исходном файле; исходный файл и его карты не меняются.
#   blender -b <AR-15_износ_этап2_v1.blend> --factory-startup --python-exit-code 1 --python tools/ar15/training_view.py -- <out.blend>
import os
import re
import shutil
import sys

import bpy

out = os.path.abspath(sys.argv[sys.argv.index("--") + 1])
maps = os.path.join(os.path.dirname(out), "Карты")
os.makedirs(maps, exist_ok=True)
pattern = re.compile(r"^[a-z_]+_(baseColor|occlusionRoughnessMetallic|normal)\.png$")
moved = []
for im in bpy.data.images:
    if im.source != "FILE" or not im.filepath:
        continue
    src = bpy.path.abspath(im.filepath)
    name = os.path.basename(src)
    if not pattern.match(name):
        continue
    dst = os.path.join(maps, name)
    if os.path.normcase(os.path.abspath(src)) != os.path.normcase(dst):
        shutil.copy2(src, dst)
    im.filepath = dst
    im.reload()
    moved.append(name)
# пути к картам — относительные (//Карты/…): папку тренировки можно перенести целиком
bpy.ops.wm.save_as_mainfile(filepath=out)
bpy.ops.file.make_paths_relative()
bpy.ops.wm.save_mainfile()
print("карт:", len(moved), "→", maps)
print("файл:", out)
