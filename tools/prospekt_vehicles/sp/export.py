# Задание Painter: выгрузка карт всех наборов (ARGS: out — папка) пресетом glTF (цвет, AO+шероховатость+металл, нормали)
# и сохранение проекта рядом (ARGS: spp — путь .spp). Выполняется, когда Painter досчитает стек (sp_lib.when_idle):
# сразу после сборки тяжёлого стека save_as давал «Painter is busy», а следующее задание поверх занятого Painter его
# роняло. Итог — в файл-метку ARGS["mark"] (по умолчанию _export_done.txt) в папке заданий.
import os

import substance_painter.project as P
import substance_painter.textureset as TS

import sp_lib

out = ARGS["out"].replace("\\", "/")
mark = ARGS.get("mark", "_export_done.txt")
vsp.unmark(mark)


def _run():
    os.makedirs(out, exist_ok=True)
    lines = []
    for t in TS.all_texture_sets():
        status, tex = sp_lib.export(out, t.name())
        lines.append(f"{t.name()} {status} {sum(len(v) for v in tex.values())} карт")
    if ARGS.get("spp"):
        os.makedirs(os.path.dirname(ARGS["spp"]), exist_ok=True)
        P.save_as(ARGS["spp"].replace("\\", "/"), P.ProjectSaveMode.Full)
        lines.append("проект: " + ARGS["spp"])
    return "; ".join(lines)


sp_lib.when_idle(_run, mark)
print("выгрузка поставлена в очередь:", mark)
