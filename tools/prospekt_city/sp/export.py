# Задание Painter: выгрузка карт всех наборов (ARGS: out — папка) пресетом glTF (цвет, AO+шероховатость+металл, нормали)
# и сохранение проекта рядом (ARGS: spp — путь .spp).
import os

import substance_painter.project as P
import substance_painter.textureset as TS

import sp_lib

out = ARGS["out"].replace("\\", "/")
os.makedirs(out, exist_ok=True)
for t in TS.all_texture_sets():
    status, tex = sp_lib.export(out, t.name())
    print(t.name(), status, sum(len(v) for v in tex.values()), "карт")
if ARGS.get("spp"):
    os.makedirs(os.path.dirname(ARGS["spp"]), exist_ok=True)
    P.save_as(ARGS["spp"].replace("\\", "/"), P.ProjectSaveMode.Full)
    print("проект:", ARGS["spp"])
