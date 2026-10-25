"""Транспорт «Проспекта»: помощники заданий Substance Painter (выполняются внутри Painter через мост sp_bridge).

Слои — заливки (sp_lib из tools/vss_m_v8: однотонные каналы, процедурные источники, генераторы в масках);
по детали — маска геометрии: сетки в FBX названы «<набор>__<материал детали>» (game_kit.py), слой краски кладётся
только на «Body__paint» и т. п.
"""
import os

import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS

JOBS = os.environ.get("SP_BRIDGE_DIR", "")


def mark(name, text="ok"):
    with open(os.path.join(JOBS, name), "w", encoding="utf-8") as f:
        f.write(text)


def unmark(name):
    p = os.path.join(JOBS, name)
    if os.path.exists(p):
        os.remove(p)


def meshes():
    """Имена сеток проекта (для масок по детали)."""
    import substance_painter.textureset as T
    out = []
    for t in T.all_texture_sets():
        for st in [t.get_stack()]:
            pass
    try:
        import substance_painter.project as PP
        return list(PP.get_mesh_names()) if hasattr(PP, "get_mesh_names") else out
    except Exception:
        return out


def texture_set(name):
    for t in TS.all_texture_sets():
        if t.name() == name:
            return t
    raise RuntimeError("нет набора " + name)


def on_project_ready(tag):
    def cb(e):
        mark(tag)
    E.DISPATCHER.connect_strong(E.ProjectEditionEntered, cb)
