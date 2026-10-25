# Проект «parts» (все детали, кроме коробки) в Substance Painter: стек по каждому набору текстур (sp_stacks),
# экспорт glTF-карт в _asset_src/vss_m_v8/sp_parts/export. Задание моста: exec(open(...).read()).
# Можно ограничить наборы: перед exec задать ONLY = ["wood", ...].
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

OUT = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_parts"
BUILD = {
    "steel_parts": lambda st: sp_stacks.steel(st),
    "suppressor": sp_stacks.suppressor,
    "bare_steel": sp_stacks.bare_steel,
    "handguard": lambda st: sp_stacks.polymer(st),
    "magazine": lambda st: sp_stacks.polymer(st, (0.035, 0.035, 0.037), rough=0.42, stipple=0.012, stipple_scale=60.0, pores=0.15,
                                                spots="noise_bnw_spots_2/bnw_spots_2"),
    "sleeve": sp_stacks.anodized,
    "wood": sp_stacks.wood,
    "rubber": sp_stacks.rubber,
    "rounds": sp_stacks.rounds,
}
only = globals().get("ONLY") or list(BUILD)
ONLY = None                      # глобальные переменные моста общие для заданий — сбрасываем выбор
for name in only:
    st = sp_lib.stack_by_name(name)
    sp_lib.clear(st)
    BUILD[name](st)
    sp_stacks.contact_marks(st, name)
    print(name, [n.get_name() for n in L.get_root_layer_nodes(st)])
sp_lib.P.save_as(OUT + "/parts.spp")
for name in only:
    status, tex = sp_lib.export(OUT + "/export", name)
    print("export", name, status)
