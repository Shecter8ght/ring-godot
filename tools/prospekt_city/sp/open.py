# Задание Painter: открыть сохранённый проект (ARGS: spp, tag); текущий сохраняется и закрывается.
import substance_painter.event as E
import substance_painter.project as P

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
P.open(ARGS["spp"].replace("\\", "/"))
print("open:", ARGS["spp"])
