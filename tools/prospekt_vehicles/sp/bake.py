# Задание Painter: запекание карт сетки с подробной формы (ARGS: high — FBX подробной формы, res — «Набор:лог2,…»,
# tag — метка). Наборы печём по очереди: следующий — в обработчике окончания предыдущего; в конце — «_bake_<tag>.txt».
# Луч ищет подробную поверхность в пределах ~2 % габарита сцены вперёд и назад: панели обеих сборок почти совпадают,
# а салон и кузов далеко друг от друга — чужие детали не попадают.
import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

tag = ARGS["tag"]
vsp.unmark("_bake_" + tag + ".txt")
res = {k: int(v) for k, v in (p.split(":") for p in ARGS["res"].split(","))}
url = "file:///" + ARGS["high"].replace("\\", "/")
queue = [t for t in TS.all_texture_sets() if t.name() in res]
log = []


def _setup(t):
    n = res[t.name()]
    t.set_resolution(TS.Resolution(2 ** n, 2 ** n))
    bp = B.BakingParameters.from_texture_set(t)
    bp.set_enabled_bakers([U.Normal, U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
    c = bp.common()
    vals = {c["OutputSize"]: (n, n), c["LowAsHigh"]: False, c["HipolyMesh"]: url, c["SubSampling"]: 1,
            c["RelativeScale"]: True, c["MaxHeight"]: 0.006, c["MaxDepth"]: 0.006, c["IgnoreBackface"]: True}
    idp = bp.baker(U.ID)
    vals[idp["ColorSource"]] = 3
    B.BakingParameters.set(vals)


def _next(e=None):
    if e is not None:
        log.append(str(e.status))
    if not queue:
        vsp.mark("_bake_" + tag + ".txt", " ".join(log))
        return
    t = queue.pop(0)
    _setup(t)
    B.bake_async(t)


_old = globals().get("_bake_handler")
if _old is not None:
    try:
        E.DISPATCHER.disconnect(E.BakingProcessEnded, _old)
    except Exception:
        pass
_bake_handler = _next
E.DISPATCHER.connect_strong(E.BakingProcessEnded, _next)
print("наборы:", [t.name() for t in queue])
_next()
