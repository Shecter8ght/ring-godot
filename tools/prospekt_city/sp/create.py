# Задание Painter: новый проект из игровой сетки семьи (ARGS: low — FBX, tag — имя метки готовности).
# Открытый проект сохраняется и закрывается; готовность — файл-метка «_proj_<tag>.txt» по ProjectEditionEntered.
import os

import substance_painter.event as E
import substance_painter.project as P

# без OCIO проект создаётся «старым» (legacy) — цвета заливок через API в нём не ставятся
os.environ["OCIO"] = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"

csp.unmark("_proj_" + ARGS["tag"] + ".txt")
if P.is_open():
    if P.file_path():
        P.save()
    P.close()


def _ready(e):
    csp.mark("_proj_" + ARGS["tag"] + ".txt")


_old = globals().get("_ready_handler")
if _old is not None:
    try:
        E.DISPATCHER.disconnect(E.ProjectEditionEntered, _old)
    except Exception:
        pass
_ready_handler = _ready
E.DISPATCHER.connect_strong(E.ProjectEditionEntered, _ready)
s = P.Settings(default_texture_resolution=2048, normal_map_format=P.NormalMapFormat.OpenGL,
               tangent_space_mode=P.TangentSpace.PerFragment)
P.create(ARGS["low"].replace("\\", "/"), settings=s)
print("create:", ARGS["low"], "open:", P.is_open())
