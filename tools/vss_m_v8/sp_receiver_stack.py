# Набор текстур «receiver» (коробка с крышкой) в Substance Painter: сталь ВСС-М (sp_stacks.steel).
# Выполняется как задание моста в открытом проекте receiver.spp: exec(open(...).read()). Стек перестраивается целиком.
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

OUT = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_receiver"
st = sp_lib.stack_by_name("receiver")
sp_lib.clear(st)
sp_stacks.steel(st, rail_meshes=["Cover_picatinny__sp"])
sp_stacks.contact_marks(st, "receiver")
print("stack:", [n.get_name() for n in L.get_root_layer_nodes(st)])
sp_lib.P.save_as(OUT + "/receiver.spp")
status, tex = sp_lib.export(OUT + "/export", "receiver")
print("export", status, tex)
