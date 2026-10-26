# Проект «sights» (прицелы ПСО 4×24 и 4×32, sights_sp.py) в Substance Painter: стек по каждому набору текстур
# (sp_stacks.optic_*, резина — sp_stacks.rubber), экспорт glTF-карт в _asset_src/vss_m_v8/sp_sights/export.
# Задание моста: exec(open(...).read()).
import importlib
import sys

TOOLS = "E:/Games/RING-godot/tools/vss_m_v8"
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import sp_lib  # noqa: E402
import sp_stacks  # noqa: E402
importlib.reload(sp_lib)
importlib.reload(sp_stacks)
from sp_lib import L  # noqa: E402

OUT = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_sights"
BUILD = {
    # процедуры в координатах развёртки: у муфты 1 = 263 мм, у ПСО 430, у 4×32 343 мм — мельче на столько же
    "optic_body": lambda st: sp_stacks.optic_body(st, tile=1.6),
    "optic_body_432": lambda st: sp_stacks.optic_body(st, tile=1.3),
    "optic_rim": sp_stacks.optic_rim,
    "optic_engraving": sp_stacks.optic_engraving,
    "optic_inner": sp_stacks.optic_inner,
    "optic_rubber": sp_stacks.rubber,
}
for name, fn in BUILD.items():
    st = sp_lib.stack_by_name(name)
    sp_lib.clear(st)
    fn(st)
    print(name, [n.get_name() for n in L.get_root_layer_nodes(st)])


def _finish():
    sp_lib.P.save_as(OUT + "/sights.spp")
    return [(n, str(sp_lib.export(OUT + "/export", n)[0])) for n in BUILD]


sp_lib.when_idle(_finish)               # сохранить и выгрузить, когда Painter досчитает стек (метка _stack_done.txt)
