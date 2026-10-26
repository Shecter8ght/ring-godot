# Задание Painter: стек слоёв забора ПО-2 (наборы PO2 и PO2Breach) — старый литой бетон, оцинкованный кронштейн,
# раствор в стакане. Петли и арматура пролома — плиточный пруток Rebar вне Painter (wire_textures.py).
# Стек пересобирается с нуля (sp_lib.clear).
import importlib

import cstacks
import sp_lib

importlib.reload(cstacks)

for ts, sets in (("PO2", ("concrete", "mortar", "steel")), ("PO2Breach", ("concrete",))):
    st = sp_lib.stack_by_name(ts)
    sp_lib.clear(st)
    m = {k: [f"{ts}__{k}"] for k in sets}
    cstacks.concrete(st, m["concrete"], color=(0.54, 0.53, 0.50))
    if "steel" in m:
        cstacks.galvanized(st, m["steel"])
    if "mortar" in m:
        cstacks.mortar(st, m["mortar"])
print("стек ПО-2 собран")
