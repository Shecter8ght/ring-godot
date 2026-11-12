# АСТЕН-919, текстуры этап 1 — заводская отделка в Substance Painter на принятой high-poly с развёрткой (tex_uv.py).
# Выполняется внутри Painter через мост (tools/asset_kit/finish/sp_run.py, своя папка заданий
# FINISH_SP_JOBS=_asset_src/asten919/tex/sp_jobs):
#   python -X utf8 tools/asset_kit/finish/sp_run.py start
#   python -X utf8 tools/asset_kit/finish/sp_run.py -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/asten919'); import sp_asten; print(sp_asten.create())"
#   … print(sp_asten.bake())   → метка _bake_done.txt (по набору, проект сохраняется после каждого)
#   … print(sp_asten.stack())  → метка _stack_done.txt;  … print(sp_asten.export(<папка>)) → _export_done.txt
# Вход — tools/asten919/sp_export.py (ASTEN919_sp.fbx, _meshes.json, _scene.json), tools/asten919/tex_marks.py (маски
# краски прицельных и цифр магазина), отчёт развёртки (плотность наборов).
# Наборы — tex_sets.SETS; слоты отделки — детали из finish-spec.json (маска слоя по имени сетки «<деталь>__sp»).
# Отделки — карточки каталога теми же функциями и числами (sp_finish.build_set); слот без выбора владельца строится
# по кандидату CANDIDATES и помечается в отчёте «кандидат» — до решения владельца это проба, не выбор.
# Правки чисел карточки под эту модель — overrides слота (причина — в его note); список layers заменяется целиком.
import json
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

import sp_finish
import tex_sets as T

SPEC = T.MODEL_DIR + "/finish-spec.json"
PROJECT = T.WORK + "/sp/ASTEN919_v2.spp"      # на развёртке v02; прежний — ASTEN919_finish_v1.spp (развёртка v01)
FBX = T.WORK + "/sp/ASTEN919_sp.fbx"
MASKS = T.WORK + "/masks"
# слот без выбора владельца → отделка-кандидат (см. note слота в finish-spec.json)
CANDIDATES = {"slide": "NT-BLK-SAT", "barrel": "NT-BLK-SAT", "steel_small": "PH-BLK-MAT", "polymer_small": "PL-BLK-SMO",
              "magazine": "PL-BLK-SMO", "springs": "SS-BRU", "steel_bare": "NI-PLT-SAT", "bullet": "CU-PRM"}
# краска прицельных: белая матовая эмаль (обводка целика, точка мушки) — без рельефа
SIGHT_PAINT = {"color": (0.84, 0.84, 0.82), "rough": 0.55, "metal": 0.0}
# стальной вкладыш корпуса магазина, видимый в окошках счёта (фаски и стенки отверстий): светлая сталь
LINER = {"color": (0.70, 0.70, 0.71), "rough": 0.26, "metal": 1.0}
# цифры у окошек магазина: литой рельеф корпуса, вдавлены
NUM_DEPTH = 0.06
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


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def create():
    """Проект из FBX: нормали OpenGL, касательные по фрагменту, наборы по tex_sets; метка _project_ready.txt."""
    os.environ["OCIO"] = sp_finish.OCIO
    if P.is_open():
        P.close()
    s = P.Settings(default_texture_resolution=2048, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerFragment)
    P.create(FBX, settings=s)

    def ready(e):
        for t in TS.all_texture_sets():
            n = T.SETS.get(t.name(), (2048,))[0]
            t.set_resolution(TS.Resolution(n, n))

        def save_now():
            os.makedirs(os.path.dirname(PROJECT), exist_ok=True)
            P.save_as(PROJECT)
            sp_finish.mark("_project_ready.txt", "OK " + " ".join(
                f"{t.name()}:{t.get_resolution().width}" for t in TS.all_texture_sets()))
        P.execute_when_not_busy(save_now)
    _connect(E.ProjectEditionEntered, ready, "create")
    return "creating"


def open_project():
    """Открыть проект; метка _project_ready.txt. Обработчик держится сильной ссылкой (слабая терялась — метки не
    было, хотя проект открывался); если проект уже в работе к концу вызова — метка сразу."""
    os.environ["OCIO"] = sp_finish.OCIO
    if P.is_open():
        if P.file_path().replace("\\", "/").lower() == PROJECT.lower() and P.is_in_edition_state():
            sp_finish.mark("_project_ready.txt", "OK already open")
            return "already open"
        P.close()

    def ready(e):
        sp_finish.mark("_project_ready.txt", "OK opened")
    _connect(E.ProjectEditionEntered, ready, "open")
    P.open(PROJECT)
    if P.is_open() and P.is_in_edition_state():
        sp_finish.mark("_project_ready.txt", "OK opened")
    return "opening"


def bake(only=None):
    """Карты сетки, сетка сама себе high-poly: нормали мира, ID, AO, кривизна, положение, толщина — по наборам
    очередью; тень AO — только от своей детали (подвижные потом сдвигаются). Проект сохраняется после каждого набора;
    итог — _bake_done.txt."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = t.get_resolution().width.bit_length() - 1
        B.BakingParameters.set({c["OutputSize"]: (n, n), c["LowAsHigh"]: True, c["SubSampling"]: 1,
                                c["MaxDepth"]: 0.0005, c["MaxHeight"]: 0.0005, c["FilterMethod"]: 1})
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


def _finish(slot):
    """Запись отделки слота: выбор владельца или кандидат, overrides — поверх карточки."""
    code = slot.get("finish") or CANDIDATES[slot["id"]]
    f = dict(sp_finish.finish(code))
    for k, v in (slot.get("overrides") or {}).items():
        if isinstance(v, dict) and isinstance(f.get(k), dict):
            f[k] = {**f[k], **v}
        else:
            f[k] = v
    return f, (not slot.get("finish"))


def parts_of(set_name):
    """Подгруппы отделок набора: [{finish, meshes}] и список слотов-кандидатов. Деталь слота — имя объекта или
    «объект:материал» (куски патрона и гильзы)."""
    meshes = _json(os.path.splitext(FBX)[0] + "_meshes.json")
    out, cand = [], []
    for slot in _json(SPEC)["slots"]:
        ms = []
        for name, rec in meshes.items():
            if rec["set"] != set_name:
                continue
            if rec["obj"] in slot["parts"] or f"{rec['obj']}:{rec['mat']}" in slot["parts"]:
                ms.append(name)
        if ms:
            f, is_cand = _finish(slot)
            out.append({"finish": f, "meshes": sorted(ms)})
            if is_cand:
                cand.append(f"{slot['id']}={f['code']}")
    used = {m for p in out for m in p["meshes"]}
    lost = [n for n, r in meshes.items() if r["set"] == set_name and n not in used]
    if lost:
        raise RuntimeError("детали без слота отделки: " + ", ".join(lost))
    return out, cand


def _group(set_name):
    import substance_painter.layerstack as L
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    return [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]


def sight_paint():
    """Белая краска прицельных — слой над отделками в группе этапа 1, маска slide_sight_paint.png."""
    import substance_painter.layerstack as L
    import sp_lib
    lay = sp_lib.fill("Краска прицельных — белая обводка целика и точка мушки",
                      L.InsertPosition.inside_node(_group("slide"), L.NodeStack.Substack),
                      color=SIGHT_PAINT["color"], rough=SIGHT_PAINT["rough"], metal=SIGHT_PAINT["metal"])
    sp_finish.bitmap_mask(lay, MASKS + "/slide_sight_paint.png")
    return lay


def magazine_numbers():
    """Цифры у окошек счёта — вдавленный литой рельеф корпуса магазина, маска magazine_numbers.png."""
    import substance_painter.layerstack as L
    import sp_lib
    lay = sp_lib.fill("Цифры окошек — литой рельеф", L.InsertPosition.inside_node(_group("magazine"), L.NodeStack.Substack),
                      height=NUM_DEPTH)
    lay.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.Height)
    sp_finish.bitmap_mask(lay, MASKS + "/magazine_numbers.png")
    return lay


def magazine_liner():
    """Светлая сталь вкладыша в окошках счёта — слой над отделками магазина, маска magazine_liner.png."""
    import substance_painter.layerstack as L
    import sp_lib
    lay = sp_lib.fill("Вкладыш в окошках — светлая сталь", L.InsertPosition.inside_node(_group("magazine"), L.NodeStack.Substack),
                      color=LINER["color"], rough=LINER["rough"], metal=LINER["metal"])
    sp_finish.bitmap_mask(lay, MASKS + "/magazine_liner.png")
    return lay


def stack(only=None):
    """Стеки этапа 1 по наборам; итог — _stack_done.txt (когда Painter досчитает), проект сохраняется."""
    import sp_lib
    # зерно и литьё — в мм трёхпроекционно: развёртка high-poly в тысячи островов, по развёртке зерно рвётся на швах
    sp_finish.WORLD_GRAIN = True
    sp_finish.FINE_EDGES = True
    px = {k: v["px_mm"] for k, v in _json(T.WORK + "/uv/report.json").items()}
    scene = _json(os.path.splitext(FBX)[0] + "_scene.json")["size_mm"]
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        parts, cand = parts_of(name)
        log.append(sp_finish.build_set(name, parts, px[name], scene))
        if cand:
            log.append("кандидаты: " + ", ".join(cand))
        if name == "slide" and os.path.exists(MASKS + "/slide_sight_paint.png"):
            sight_paint()
            log.append("slide: краска прицельных")
        if name == "magazine" and os.path.exists(MASKS + "/magazine_numbers.png"):
            magazine_numbers()
            log.append("magazine: цифры окошек")
        if name == "magazine" and os.path.exists(MASKS + "/magazine_liner.png"):
            magazine_liner()
            log.append("magazine: вкладыш в окошках")

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
