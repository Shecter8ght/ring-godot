# «Осока» (ПЗРК), текстуры этап 1 — заводская отделка в Substance Painter прямо на игровой сетке (по образцу
# tools/smg03/sp_smg03.py, все его уроки 05.11 сохранены). Выполняется внутри Painter через мост
# (tools/asset_kit/finish/sp_run.py, своя папка заданий FINISH_SP_JOBS=_asset_src/osoka/tex/sp_jobs):
#   python -X utf8 tools/asset_kit/finish/sp_run.py start
#   python -X utf8 tools/asset_kit/finish/sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/osoka'); import sp_osoka; print(sp_osoka.create())"
#   … sp_osoka.bake() → _bake_done.txt;  … sp_osoka.use_blender_normals();  … sp_osoka.stack() → _stack_done.txt;
#   … sp_osoka.export(<папка>) → _export_done.txt
# Вход — tools/osoka/game_tex.py (Osoka_low.fbx / Osoka_high.fbx, meshes.json, normals/) и tools/osoka/tex_masks.py
# (трафарет трубы, отсек датчика ракеты). Наборы — атласы игровой сетки (Tube, Launcher, Missile); слоты отделки — сетки
# «<набор>__<слот>_low». Отделки — карточки каталога по finish-spec.json теми же функциями и числами.
import json
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

import sp_finish

ROOT = "E:/Games/RING-godot"
TEX = ROOT + "/_asset_src/osoka/tex"
SPEC = "E:/Models Blender/WEAPONS/Верба — модель/finish-spec.json"
PROJECT = TEX + "/sp/Osoka_finish_v1.spp"
LOW = TEX + "/Osoka_low.fbx"
HIGH = TEX + "/Osoka_high.fbx"
RES = {"Tube": 4096, "Launcher": 4096, "Missile": 2048}
# луч запекания — доля габарита сцены (труба 1.7 м): 0.0015 ≈ 2.6 мм — отклонение игровой сетки до 0.9 мм, буквы 1.55
RAY_REL = 0.0015
# трафарет трубы — белая краска (полумат, по эмали трубы); отсек датчика ракеты — светлая серо-голубая эмаль по маске
STENCIL = {"color": (0.82, 0.82, 0.78), "rough": 0.6, "metal": 0.0}
SENSOR_FINISH = "EN-MBL-MAT"
_handlers = {}


def _connect(event, fn, key):
    old = _handlers.pop(key, None)
    if old is not None:
        try:
            E.DISPATCHER.disconnect(event, old)
        except Exception:      # noqa: BLE001
            pass
    _handlers[key] = fn
    E.DISPATCHER.connect_strong(event, fn)


def _json(name):
    with open(TEX + "/" + name, encoding="utf-8") as f:
        return json.load(f)


def create():
    """Проект из игровой сетки: нормали OpenGL, касательные в вершинах (как считает Godot), разрешение по набору."""
    os.environ["OCIO"] = sp_finish.OCIO
    if P.is_open():
        P.close()
    s = P.Settings(default_texture_resolution=2048, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerVertex)
    P.create(LOW, settings=s)

    def ready(e):
        for t in TS.all_texture_sets():
            n = RES.get(t.name(), 2048)
            t.set_resolution(TS.Resolution(n, n))

        def save_now():
            os.makedirs(os.path.dirname(PROJECT), exist_ok=True)
            P.save_as(PROJECT)
            sp_finish.mark("_project_ready.txt", "OK " + " ".join(
                f"{t.name()}:{t.get_resolution().width}" for t in TS.all_texture_sets()))
        P.execute_when_not_busy(save_now)
    _connect(E.ProjectEditionEntered, ready, "create")
    return "creating"


def bake(only=None, match=1, ray=RAY_REL, sub=1):
    """Карты сетки с принятой формы по наборам очередью (нормаль своя — потом заменяется картой Blender): нормаль мира,
    ID, AO (тень от всей сборки), кривизна, положение, толщина; пары по имени сетки (_low / _high). Проект сохраняется
    после каждого набора; итог — _bake_done.txt."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.Normal, U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = RES.get(t.name(), 2048).bit_length() - 1
        vals = {c["OutputSize"]: (n, n), c["LowAsHigh"]: False, c["HipolyMesh"]: "file:///" + HIGH,
                c["SubSampling"]: sub, c["RelativeScale"]: True, c["MaxHeight"]: ray, c["MaxDepth"]: ray,
                c["IgnoreBackface"]: True, c["FilterMethod"]: match, c["SmoothNormals"]: False}
        vals[bp.baker(U.ID)["ColorSource"]] = 3
        vals[bp.baker(U.AO)["FilterMethodSecondary"]] = 0
        B.BakingParameters.set(vals)
    queue = list(sets)
    log = []

    def nxt(e=None):
        if e is not None:
            log.append(str(e.status))

            def save_now():
                try:
                    P.save()
                except Exception as ex:      # noqa: BLE001
                    log.append("save " + str(ex))
                go()
            P.execute_when_not_busy(save_now)
            return
        go()

    def go():
        if not queue:
            sp_finish.mark("_bake_done.txt", " ".join(log))
            return
        t = queue.pop(0)
        log.append(t.name())
        B.bake_async(t)
    _connect(E.BakingProcessEnded, nxt, "bake")
    nxt()
    return "bake queue " + " ".join(t.name() for t in sets)


def use_blender_normals(only=None):
    """Карта нормалей наборов — из Blender (game_tex.py, стадия normals) вместо своей (урок ИЗЛОМ-45 05.11)."""
    out = []
    for t in TS.all_texture_sets():
        if only and t.name() not in only:
            continue
        path = f"{TEX}/normals/{t.name()}_normal.png"
        if not os.path.exists(path):
            out.append(f"{t.name()}: нет {path}")
            continue
        res = sp_finish._bitmap(path)
        t.set_mesh_map_resource(U.Normal, res)
        out.append(f"{t.name()}: {res.name}")
    return " | ".join(out)


def _spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def _finish(slot):
    f = dict(sp_finish.finish(slot["finish"]))
    for k, v in (slot.get("overrides") or {}).items():
        if isinstance(v, dict) and isinstance(f.get(k), dict):
            f[k] = {**f[k], **v}
        else:
            f[k] = v
    return f


def parts_of(set_name):
    """Подгруппы отделок набора по meshes.json и finish-spec.json; у корпуса ракеты поверх — отсек датчика по маске."""
    spec = {s["id"]: s for s in _spec()["slots"]}
    out = []
    for sid, rec in _json("meshes.json").get(set_name, {}).items():
        out.append({"finish": _finish(spec[sid]), "meshes": rec["meshes"]})
        mask = f"{TEX}/masks/Missile_sensor.png"
        if sid == "missile_body" and os.path.exists(mask):
            out.append({"finish": SENSOR_FINISH, "meshes": rec["meshes"], "mask": mask})
    return out


def stencil(set_name="Tube"):
    """Трафаретные надписи белой краской — слой над отделками в группе этапа 1, маска Tube_stencil.png."""
    import substance_painter.layerstack as L
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    grp = [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]
    lay = sp_lib.fill("Трафарет белой краской", L.InsertPosition.inside_node(grp, L.NodeStack.Substack),
                      color=STENCIL["color"], rough=STENCIL["rough"], metal=STENCIL["metal"])
    sp_finish.bitmap_mask(lay, f"{TEX}/masks/{set_name}_stencil.png")
    return lay


def stack(only=None):
    """Стеки этапа 1 по наборам; итог — _stack_done.txt (когда Painter досчитает), проект сохраняется."""
    import sp_lib
    sp_finish.WORLD_GRAIN = True     # зерно в мм трёхпроекционно (урок ИЗЛОМ-45 v3)
    sp_finish.FINE_EDGES = True      # кромки — только мелкие масштабы кривизны (урок ИЗЛОМ-45)
    px = _json("px_mm.json")
    scene = _json("scene.json")["size_mm"]
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        parts = parts_of(name)
        if not parts:
            continue
        log.append(sp_finish.build_set(name, parts, px.get(name, 5.0), scene))
        if name == "Tube" and os.path.exists(f"{TEX}/masks/Tube_stencil.png"):
            stencil(name)
            log.append("Tube: трафарет")

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_stack_done.txt")
    return " | ".join(log)


def export(out_dir, only=None):
    """Карты наборов (glTF PBR: baseColor, ORM, normal) в out_dir; итог — _export_done.txt."""
    import sp_lib
    os.makedirs(out_dir, exist_ok=True)
    names = [t.name() for t in TS.all_texture_sets() if not only or t.name() in only]

    def run():
        n = 0
        for nm in names:
            status, tex = sp_lib.export(out_dir, nm)
            n += sum(len(v) for v in tex.values())
        return f"{n} карт → {out_dir}"
    sp_lib.when_idle(run, "_export_done.txt")
    return "export " + " ".join(names)


def open_project():
    return sp_finish.open_project(PROJECT)
