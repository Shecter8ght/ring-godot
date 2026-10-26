"""«Проспект», ограждения и город: помощники заданий Substance Painter (внутри Painter, мост sp_bridge).

Метки готовности в папке заданий, имена сеток проекта для масок по детали (сетки FBX «<набор>__<материал>», game.py).
"""
import os

JOBS = os.environ.get("SP_BRIDGE_DIR", "")


def mark(name, text="ok"):
    with open(os.path.join(JOBS, name), "w", encoding="utf-8") as f:
        f.write(text)


def unmark(name):
    p = os.path.join(JOBS, name)
    if os.path.exists(p):
        os.remove(p)
