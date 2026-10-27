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
    # задний прицел — Cerakote, как муфта, без продольных сколов (только углы)
    "steel_parts": lambda st: (sp_stacks.steel(st, parts=sp_stacks.STEEL_PARTS_PARTS),
                               sp_stacks.exclude(st, sp_stacks.REAR_SIGHT_IDS),
                               sp_stacks.cerakote(st, rails=False, mask=sp_stacks.REAR_SIGHT_IDS, chip_scale=15.0)),
    "suppressor": sp_stacks.suppressor,
    "bare_steel": sp_stacks.bare_steel,
    "handguard": lambda st: sp_stacks.polymer(st),
    "magazine": sp_stacks.magazine,
    "magazine_30": lambda st: sp_stacks.magazine(st, sp_stacks.MAG_LIPS_30),
    "sleeve": sp_stacks.cerakote,               # Cerakote H-146 (владелец 26.10; прежде — анодирование)
    "wood": sp_stacks.wood,
    "rubber": sp_stacks.rubber,
    "rounds": sp_stacks.rounds,
}
only = globals().get("ONLY") or list(BUILD)
force = bool(globals().get("FORCE_CLEAR"))
ONLY = FORCE_CLEAR = None        # глобальные переменные моста общие для заданий — сбрасываем выбор
for name in only:
    st = sp_lib.stack_by_name(name)
    sp_lib.clear(st, force)      # набор с ручной работой владельца без force не пересобирается
    BUILD[name](st)
    sp_stacks.contact_marks(st, name)
    print(name, [n.get_name() for n in L.get_root_layer_nodes(st)])


def _finish(names=tuple(only)):
    sp_lib.P.save_as(OUT + "/parts.spp")
    return [(n, str(sp_lib.export(OUT + "/export", n)[0])) for n in names]


sp_lib.when_idle(_finish)               # сохранить и выгрузить, когда Painter досчитает стек (метка _stack_done.txt)
