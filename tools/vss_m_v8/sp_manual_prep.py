# ВСС-М v8: проект Painter — к ручной работе владельца (2026-10-27, «износ в тех местах, где я хочу»). В маску каждого
# слоя износа, грязи и следов (имена «05 …», «13 …», «М4 …» — их строят sp_stacks.py и contact_marks) кладётся сверху
# пустой слой рисования «РУКАМИ»: белым — добавить этот слой (износ, грязь, блеск) там, где проведена кисть, чёрным —
# убрать; где не рисовали — маска прежняя. Наборы, где такие слои есть, записываются в метаданные проекта
# (ring / manual_sets): пересборка стека скриптом (sp_lib.clear) на них останавливается — она стёрла бы ручную работу.
# Задание моста в открытом проекте: exec(open(...).read()); сохраняет проект.
import re
import sys

TOOLS = "E:/Games/RING-godot/tools/vss_m_v8"
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import sp_lib  # noqa: E402
import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.textureset as T

NAME = "РУКАМИ"
TARGET = re.compile(r"^(\d\d[а-яё]?|М\d) ")


def walk(nodes):
    for n in nodes:
        yield n
        if n.get_type() == L.NodeType.GroupLayer:
            yield from walk(n.sub_layers())


done = {}
for ts in T.all_texture_sets():
    st = ts.get_stack()
    names = []
    for n in walk(L.get_root_layer_nodes(st)):
        if not TARGET.match(n.get_name()) or not n.has_mask():
            continue
        ef = n.mask_effects()                       # верх маски — первый
        if any(e.get_name() == NAME for e in ef):
            names.append(n.get_name())
            continue
        pos = L.InsertPosition.above_node(ef[0]) if ef else L.InsertPosition.inside_node(n, L.NodeStack.Mask)
        p = L.insert_paint(pos)
        p.set_name(NAME)
        names.append(n.get_name())
    if names:
        done[ts.name()] = names
md = P.Metadata("ring")
old = md.get("manual_sets") if "manual_sets" in md.list() else []
md.set("manual_sets", sorted(set(old or []) | set(done)))
for k, v in done.items():
    print(k, len(v), v)
print("manual_sets", md.get("manual_sets"))


def _save():
    P.save()
    return "saved"


sp_lib.when_idle(_save)
