# ИЗЛОМ-45 (wpn_smg_03), текстуры этап 1 — заводская отделка в Substance Painter прямо на игровой сетке (владелец
# 2026-11-05: текстурировать low-poly). Выполняется внутри Painter через мост (tools/asset_kit/finish/sp_run.py, своя
# папка заданий FINISH_SP_JOBS=_asset_src/smg03/tex/sp_jobs):
#   python -X utf8 tools/asset_kit/finish/sp_run.py start
#   python -X utf8 tools/asset_kit/finish/sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/smg03'); import sp_smg03; print(sp_smg03.create())"
#   … print(sp_smg03.bake())  → метка _bake_done.txt (по набору, проект сохраняется после каждого)
#   … print(sp_smg03.stack()) → метка _stack_done.txt;  … print(sp_smg03.export(<папка>))
# Вход — tools/smg03/game_tex.py (SMG03_low.fbx / SMG03_high.fbx, meshes.json) и tools/smg03/tex_masks.py (маски корпуса).
# Наборы — атласы игровой сетки; слоты отделки — сетки «<узел>__<слот>_low» (маска слоя по имени сетки); корпус — два
# набора по линии шва (v2: Upper — металл, Lower — полимер); поверх — красная заливка меток предохранителя и переводчика.
# Отделки — карточки каталога по finish-spec.json, теми же функциями и числами (sp_finish.build_set).
import json
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

import sp_finish

ROOT = "E:/Games/RING-godot"
TEX = ROOT + "/_asset_src/smg03/tex"
SPEC = "E:/Models Blender/WEAPONS/Vector — модель/finish-spec.json"
PROJECT = TEX + "/sp/SMG03_finish_v2.spp"   # v1 (корпус одним атласом) — SMG03_finish.spp
LOW = TEX + "/SMG03_low.fbx"
HIGH = TEX + "/SMG03_high.fbx"
RES = {"Upper": 4096, "Lower": 4096, "Steel": 4096, "Stock": 2048, "Mag13": 2048, "Mag30": 2048}
# наибольший размер набора, мм (для трёхпроекционных узоров каталога)
BBOX_MM = {"Upper": 380.0, "Lower": 300.0, "Steel": 330.0, "Stock": 230.0, "Mag13": 130.0, "Mag30": 260.0}
# наборы с красными метками (маска <набор>_red.png, tools/smg03/tex_masks.py)
RED_SETS = ("Upper", "Lower")
# красная заливка гравировки (эмаль по металлу, полумат): цвет sRGB, шероховатость
RED = {"color": (0.62, 0.07, 0.05), "rough": 0.5, "metal": 0.0}
# луч запекания вперёд и назад — доля габарита сцены (RelativeScale): FBX из Blender — в метрах (UnitScaleFactor 100),
# как Painter переводит единицы, не проверено, а доля от них не зависит. Сцена с опущенными магазинами ~0.96 × 0.62 м:
# 0.002 ≈ 2 мм — отклонение игровой сетки до 0.47 мм (одна вершина у канала ствола 1.77), гравировки 0.25–0.45,
# шагрень и рифление ~0.3; пары low/high отобраны по имени — чужая деталь в луч не попадает
RAY_REL = 0.002
JOBS = os.environ.get("SP_BRIDGE_DIR", "")
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


def _meshes():
    with open(TEX + "/meshes.json", encoding="utf-8") as f:
        return json.load(f)


def _px_mm():
    with open(ROOT + "/_asset_src/smg03/game/lp/parts.json", encoding="utf-8") as f:
        a = json.load(f)["atlases"]
    return {k: v["report"]["px_mm"] for k, v in a.items()}


def create():
    """Проект из игровой сетки: нормали OpenGL, касательные в вершинах (как считает Godot — справка mesh-bake навыка
    godot-asset-preparation), разрешение по атласу; метка _project_ready.txt."""
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


def bake_params():
    """Имена и значения параметров запекания первого набора — сверка перед запеканием (ключи меняются от версии)."""
    t = TS.all_texture_sets()[0]
    bp = B.BakingParameters.from_texture_set(t)
    out = {"common": {k: str(v.value()) for k, v in bp.common().items()}}
    for u in (U.AO, U.Normal, U.Thickness, U.Curvature):
        out[str(u)] = {k: str(v.value()) for k, v in bp.baker(u).items()}
    try:
        out["enums"] = {k: str(v.enum_values()) for k, v in bp.common().items() if hasattr(v, "enum_values")}
    except Exception as ex:      # noqa: BLE001
        out["enums"] = str(ex)
    return json.dumps(out, ensure_ascii=False)


def bake(only=None, match=1, ray=RAY_REL, sub=1, smooth=False, high=None):
    """Карты сетки с high-poly v06 по наборам очередью: нормаль, нормаль мира, ID, AO, кривизна, положение, толщина.
    match — отбор по имени сетки (FilterMethod «By mesh name», суффиксы _low / _high); AO — тень от всей сборки
    (FilterMethodSecondary «Always»). sub — 2×2 выборки на пиксель. smooth — лучи по усреднённым нормалям Painter
    (SmoothNormals): выключено — лучи по нормалям самой сетки (game_lp.weighted_normals, на плоскостях прямые); с
    усреднёнными на большом треугольнике левого борта луч шёл наискось, и надпись «ИЗЛОМ-45» выходила сжатой и
    смазанной, с веером полос (v1 и v2, 05.11). Проект сохраняется после каждого набора (Painter падал вскоре после
    конца запекания — handguard 2026-11-01); итог — _bake_done.txt."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.Normal, U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = RES.get(t.name(), 2048).bit_length() - 1
        vals = {c["OutputSize"]: (n, n), c["LowAsHigh"]: False, c["HipolyMesh"]: "file:///" + (high or HIGH),
                c["SubSampling"]: sub, c["RelativeScale"]: True, c["MaxHeight"]: ray, c["MaxDepth"]: ray,
                c["IgnoreBackface"]: True, c["FilterMethod"]: match, c["SmoothNormals"]: smooth}
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


def _spec():
    with open(SPEC, encoding="utf-8") as f:
        return json.load(f)


def parts_of(set_name):
    """Подгруппы отделок набора: слоты из meshes.json, отделка — из finish-spec.json (выбор владельца, overrides —
    поверх карточки)."""
    spec = {s["id"]: s for s in _spec()["slots"]}
    out = []
    for sid, rec in _meshes().get(set_name, {}).items():
        out.append({"finish": _finish(spec[sid]), "meshes": rec["meshes"]})
    return out


def _finish(slot):
    f = dict(sp_finish.finish(slot["finish"]))
    for k, v in (slot.get("overrides") or {}).items():
        if isinstance(v, dict) and isinstance(f.get(k), dict):
            f[k] = {**f[k], **v}
        else:
            f[k] = v
    return f


def red_marks(set_name):
    """Красная заливка меток предохранителя и переводчика — слой над отделками в группе этапа 1, маска —
    <набор>_red.png."""
    import substance_painter.layerstack as L
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    grp = [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]
    lay = sp_lib.fill("Красная заливка меток", L.InsertPosition.inside_node(grp, L.NodeStack.Substack),
                      color=RED["color"], rough=RED["rough"], metal=RED["metal"])
    sp_finish.bitmap_mask(lay, f"{TEX}/masks/{set_name}_red.png")
    return lay


def stack(only=None):
    """Стеки этапа 1 по наборам; итог — _stack_done.txt (когда Painter досчитает), проект сохраняется."""
    import sp_lib
    px = _px_mm()
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        parts = parts_of(name)
        if not parts:
            continue
        log.append(sp_finish.build_set(name, parts, px.get(name, 8.0), BBOX_MM.get(name, 200.0)))
        if name in RED_SETS and os.path.exists(f"{TEX}/masks/{name}_red.png"):
            red_marks(name)
            log.append(f"{name}: красные метки")

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
