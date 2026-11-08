"""Пожарная АЦ в Substance Painter: проекты по узлам (tex_sets.PROJECTS), запекание с машиной целиком, стек этапа 1
(заводская отделка) по finish-spec.json и ливрея плёнкой поверх.

Задания — через мост (tools/asset_kit/finish/sp_run.py):
    sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/fire_truck'); import sp_truck; print(sp_truck.create('cab'))"
    … sp_truck.bake('cab')            # метка _bake_done.txt
    … sp_truck.build('cab_panels')    # стек набора: отделки слотов теми же числами, что карточки (sp_finish.build_set)
    … sp_truck.save('cab')            # метка _saved.txt
    … sp_truck.export('cab', <папка>) # карты наборов (glTF: baseColor, ORM, normal), метка _export_done.txt

Запекание: сетка проекта — low, вся машина своего варианта (tex_export: high_closed / high_open.fbx, без стёкол) —
high, сопоставление «всегда»: сетка та же, поэтому нормаль не печётся (плоская), а затенённость, толщина и кривизна
учитывают соседние узлы (кабину от кузова, шасси от надстройки); у наружных наборов — плоскость земли.
"""
from __future__ import annotations

import importlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (HERE, os.path.join(ROOT, "tools", "asset_kit", "finish"), os.path.join(ROOT, "tools", "vss_m_v8")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import substance_painter.baking as B  # noqa: E402
import substance_painter.event as E  # noqa: E402
import substance_painter.layerstack as L  # noqa: E402
import substance_painter.project as P  # noqa: E402
import substance_painter.textureset as TS  # noqa: E402
from substance_painter.baking import MeshMapUsage as U  # noqa: E402
from substance_painter.textureset import ChannelType as CH  # noqa: E402

import sp_finish  # noqa: E402
import sp_lib  # noqa: E402
import tex_sets as T  # noqa: E402

importlib.reload(T)
SPEC = T.MODEL_DIR + "/finish-spec.json"
LIVERY = T.WORK + "/livery"
FILM = {"rough": 0.30, "height": 0.02}           # плёнка надписей и полос: полуглянец, кромка 0,1 мм
TAPE = {"rough": 0.20, "height": 0.03}           # светоотражающая лента — глаже и толще


def ours(tname: str) -> str:
    """Набор Painter называется по материалу развёртки: FT_<набор>."""
    return tname[3:] if tname.startswith("FT_") else tname


def theirs(set_name: str) -> str:
    return set_name if set_name.startswith("FT_") else "FT_" + set_name


def project_path(proj: str) -> str:
    return f"{T.SP}/FireTanker_{proj}.spp"


def info() -> dict:
    with open(f"{T.SP}/meshes.json", encoding="utf-8") as f:
        return json.load(f)


def spec_finish() -> dict:
    with open(SPEC, encoding="utf-8") as f:
        sp = json.load(f)
    return {s["id"]: s for s in sp["slots"]}


def uv_report() -> dict:
    out = {}
    for name in os.listdir(T.WORK):
        if name.startswith("uv_report") and name.endswith(".json"):
            with open(os.path.join(T.WORK, name), encoding="utf-8") as f:
                out.update(json.load(f))
    return out


def create(proj: str):
    return sp_finish.create(f"{T.SP}/{proj}.fbx", res=4096)


def open_project(proj: str):
    return sp_finish.open_project(project_path(proj))


def bake(proj: str, only=None):
    """Очередь запекания наборов проекта: нормали мира, затенённость, кривизна, положение, толщина."""
    sets = [t for t in TS.all_texture_sets() if not only or ours(t.name()) in only]
    for t in sets:
        nm = ours(t.name())
        var = T.HIGH_OF.get(nm, "closed")
        high = f"{T.SP}/high_{var}.fbx".replace("\\", "/")
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.WorldSpaceNormal, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        ao = bp.baker(U.AO)
        n = T.SETS[nm][0].bit_length() - 1
        B.BakingParameters.set({c["OutputSize"]: (n, n), c["LowAsHigh"]: False, c["HipolyMesh"]: "file:///" + high,
                                c["FilterMethod"]: 0, c["MaxDepth"]: 0.0005, c["MaxHeight"]: 0.0005,
                                c["SubSampling"]: 1, ao["MaxDistance"]: 0.04, ao["NbSecondary"]: 128,
                                ao["GroundPlane"]: nm in T.GROUND, ao["FilterMethodSecondary"]: 0})
    queue = list(sets)
    log = []

    def nxt(e=None):
        if e is not None:
            log.append(str(e.status))
        if not queue:
            E.DISPATCHER.disconnect(E.BakingProcessEnded, nxt)
            sp_finish.mark("_bake_done.txt", " ".join(log))
            return
        B.bake_async(queue.pop(0))
    E.DISPATCHER.connect(E.BakingProcessEnded, nxt)
    nxt()
    return "bake queue " + " ".join(t.name() for t in sets)


def _proj_of(set_name: str) -> str:
    for proj, sets in T.PROJECTS.items():
        if set_name in sets:
            return proj
    raise KeyError(set_name)


def _fill_bitmap(pos, name, color_png, rough, height, mask_png):
    f = L.insert_fill(pos)
    f.set_name(name)
    f.active_channels = {CH.BaseColor, CH.Roughness, CH.Metallic, CH.Height}
    f.set_source(CH.BaseColor, sp_finish._bitmap(color_png))
    f.set_source(CH.Roughness, sp_lib._val(rough, data=True))
    f.set_source(CH.Metallic, sp_lib._val(0.0, data=True))
    f.set_source(CH.Height, sp_lib._val(height, data=True))
    f.set_projection_mode(L.ProjectionMode.UV)
    sp_finish.bitmap_mask(f, mask_png)
    return f


def livery(set_name: str, above):
    """Ливрея плёнкой поверх заводской отделки: надписи и полосы (полуглянец, кромка плёнки рельефом), сверху —
    светоотражающая лента. Картинки — tools/fire_truck/livery.py."""
    base = f"{LIVERY}/{set_name}"
    if not os.path.exists(base + "_mask.png"):
        return ""
    g = L.insert_group(L.InsertPosition.above_node(above))
    g.set_name("Ливрея — плёнка")
    f = _fill_bitmap(L.InsertPosition.inside_node(g, L.NodeStack.Substack), "Надписи и полосы", base + "_color.png",
                     FILM["rough"], FILM["height"], base + "_mask.png")
    if os.path.exists(base + "_tape.png"):
        _fill_bitmap(L.InsertPosition.above_node(f), "Светоотражающая лента", base + "_color.png", TAPE["rough"],
                     TAPE["height"], base + "_tape.png")
    return " +ливрея"


def build(set_name: str):
    """Стек набора: группа «Этап 1 — заводская отделка» (подгруппа на отделку слота, meshes — детали слота), ливрея."""
    proj = _proj_of(set_name)
    inf = info()[proj]
    slots = spec_finish()
    by_slot = {}
    for mesh, slot in inf["sets"][set_name].items():
        by_slot.setdefault(slot, []).append(mesh)
    have = set()
    for t in TS.all_texture_sets():
        if t.name() == theirs(set_name):
            have = set(t.all_mesh_names()) if hasattr(t, "all_mesh_names") else set()
    parts = []
    for slot, meshes in sorted(by_slot.items(), key=lambda kv: -len(kv[1])):
        code = (slots.get(slot) or {}).get("finish")
        if not code:
            raise RuntimeError(f"слот {slot} без отделки")
        ov = (slots.get(slot) or {}).get("overrides") or {}
        f = sp_finish.finish(code)
        if ov:
            f = json.loads(json.dumps(f))
            for k, v in ov.items():
                f[k] = {**f.get(k, {}), **v} if isinstance(v, dict) else v
        if have:
            meshes = [m for m in meshes if m in have]
            if not meshes:
                continue                     # деталей слота в проекте нет (не выгрузились) — не падать
        parts.append({"finish": f, "meshes": meshes})
    rep = uv_report().get(set_name, {})
    px_mm = float(rep.get("px_mm") or 1.0)
    log = sp_finish.build_set(theirs(set_name), parts, px_mm, inf["bbox_mm"])
    st = sp_lib.stack_by_name(theirs(set_name))
    top = [n for n in L.get_root_layer_nodes(st)][0]
    log += livery(set_name, top)
    return log


def save(proj: str):
    def run():
        os.makedirs(T.SP, exist_ok=True)
        P.save_as(project_path(proj))
        return project_path(proj)
    sp_lib.when_idle(run, "_saved.txt")
    return "saving"


def export(proj: str, out_dir: str, sets=None):
    def run():
        out = []
        for t in TS.all_texture_sets():
            if sets and ours(t.name()) not in sets:
                continue
            status, tex = sp_lib.export(out_dir, t.name())
            out.append(f"{t.name()}:{status}")
        return " ".join(out)
    sp_lib.when_idle(run, "_export_done.txt")
    return "exporting"


def meshes_of(set_name: str):
    for t in TS.all_texture_sets():
        if t.name() == theirs(set_name):
            return sorted(t.all_mesh_names())
    return []
