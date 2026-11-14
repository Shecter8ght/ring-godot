# «Частокол», текстуры этап 1 — заводская отделка в Substance Painter на принятой high-poly с развёрткой (tex_uv.py).
# Три проекта (tex_sets.PROJECTS: body, front, box) — свой FBX у каждого (sp_export.py). Выполняется внутри Painter
# через мост (tools/asset_kit/finish/sp_run.py, своя папка заданий FINISH_SP_JOBS=_asset_src/pkp/tex/sp_jobs):
#   … -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/pkp'); import sp_pkp; print(sp_pkp.create('body'))"
#   … print(sp_pkp.bake())      → метка _bake_done.txt (по набору, проект сохраняется после каждого)
#   … print(sp_pkp.stack())     → _stack_done.txt;  … print(sp_pkp.export(<папка>)) → _export_done.txt
# Рабочее разрешение наборов — tex_sets.WORK_RES (4K); карты сетки печём, а слои выгружаем в разрешении набора SETS
# (8K у коробки, крышки и коробок для ленты): стек процедурный и маски — картинками в полном разрешении.
# Отделки — карточки каталога теми же функциями и числами (sp_finish.build_set); слот без выбора владельца строится по
# предложению агента (recommended) и помечается в отчёте «предложение» — до решения владельца это проба, не выбор.
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
MASKS = T.WORK + "/masks"
# белая эмаль заливки гравировки («ОГОНЬ», цифры и деления прицела) — матовая, без рельефа
PAINT_WHITE = {"color": (0.82, 0.82, 0.79), "rough": 0.5, "metal": 0.0}
# клеймо донца — вдавленный рельеф, лак в нём темнее
STAMP_DEPTH = 0.05
# насечка рукоятки — матовее глянцевого пластика (образец 04)
GRIP_CHECKER_ROUGH = 0.42
# обработчики событий Painter живут между заданиями и переживают importlib.reload модуля — реестр держим на модуле
# событий (иначе после перезагрузки старый обработчик запекания срабатывает на чужом наборе и ставит метку раньше)
_handlers = E.__dict__.setdefault("_pkp_handlers", {})
CUR = E.__dict__.setdefault("_pkp_cur", {"proj": None})


def paths(proj):
    return T.WORK + f"/sp/PKP_{proj}.fbx", T.WORK + f"/sp/PKP_{proj}_v1.spp"


def _disconnect(event, key):
    old = _handlers.pop(key, None)
    if old is not None:
        try:
            E.DISPATCHER.disconnect(event, old)
        except Exception:      # noqa: BLE001
            pass


def _connect(event, fn, key, once=False):
    """Обработчик события по ключу (прежний с тем же ключом снимается). once — снять себя после первого срабатывания:
    обработчик открытия проекта, оставшийся висеть, срабатывал при открытии СЛЕДУЮЩЕГО проекта и сохранял его в свой
    файл (14.11: «коробки» записались в файл «переда»)."""
    for k in [k for k in _handlers if k in ("create", "open")] if event is E.ProjectEditionEntered else []:
        _disconnect(event, k)
    _disconnect(event, key)
    if once:
        def wrap(e, _fn=fn, _key=key):
            _disconnect(event, _key)
            _fn(e)
        h = wrap
    else:
        h = fn
    _handlers[key] = h
    E.DISPATCHER.connect_strong(event, h)


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _proj():
    if CUR["proj"]:
        return CUR["proj"]
    if P.is_open():
        for p in T.PROJECTS:
            if os.path.basename(paths(p)[1]).lower() in P.file_path().replace("\\", "/").lower():
                CUR["proj"] = p
                return p
    raise RuntimeError("неизвестен проект")


def create(proj):
    """Проект из FBX: нормали OpenGL, касательные по фрагменту, рабочее разрешение 4K; метка _project_ready.txt."""
    fbx, spp = paths(proj)
    CUR["proj"] = proj
    os.environ["OCIO"] = sp_finish.OCIO
    if P.is_open():
        P.close()
    s = P.Settings(default_texture_resolution=T.WORK_RES, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerFragment)
    P.create(fbx, settings=s)

    def ready(e):
        for t in TS.all_texture_sets():
            t.set_resolution(TS.Resolution(T.WORK_RES, T.WORK_RES))

        def save_now():
            os.makedirs(os.path.dirname(spp), exist_ok=True)
            P.save_as(spp)
            sp_finish.mark("_project_ready.txt", "OK " + " ".join(
                f"{t.name()}:{t.get_resolution().width}" for t in TS.all_texture_sets()))
        P.execute_when_not_busy(save_now)
    _connect(E.ProjectEditionEntered, ready, "create", once=True)
    return "creating " + proj


def open_project(proj):
    """Открыть проект; метка _project_ready.txt — только когда открыт именно он (наборы проекта на месте). Открытый
    проект закрывается БЕЗ сохранения: стек и выгрузка сохраняют сами. (14.11: метка сразу после P.open стояла раньше
    загрузки — стек собрался на прежнем проекте и сохранился в чужой файл.)"""
    spp = paths(proj)[1]
    CUR["proj"] = proj
    os.environ["OCIO"] = sp_finish.OCIO

    def ok():
        return (P.is_open() and P.is_in_edition_state()
                and P.file_path().replace("\\", "/").lower() == spp.lower()
                and sorted(t.name() for t in TS.all_texture_sets()) == sorted(T.PROJECTS[proj]))
    if ok():
        sp_finish.mark("_project_ready.txt", "OK already open")
        return "already open"
    if P.is_open():
        P.close()

    def ready(e):
        if ok():
            sp_finish.mark("_project_ready.txt", "OK opened " + proj)
    _connect(E.ProjectEditionEntered, ready, "open", once=True)
    P.open(spp)
    return "opening " + proj


def check_open():
    """Стек и выгрузка — только на своём проекте: наборы открытого проекта = наборы CUR."""
    proj = _proj()
    names = sorted(t.name() for t in TS.all_texture_sets())
    if names != sorted(T.PROJECTS[proj]) or P.file_path().replace("\\", "/").lower() != paths(proj)[1].lower():
        raise RuntimeError(f"открыт не тот проект: {P.file_path()} {names}, ожидался {proj}")


def bake(only=None):
    """Карты сетки, сетка сама себе high-poly: нормали мира, ID, AO, кривизна, положение, толщина — в разрешении
    набора SETS (8K у крупных); тень AO — только от своей детали (детали в FBX разложены врозь). Очередью по наборам,
    проект сохраняется после каждого; итог — _bake_done.txt."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = T.SETS[t.name()][0].bit_length() - 1
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
    """Запись отделки слота: выбор владельца или предложение агента, overrides — поверх карточки."""
    code = slot.get("finish") or slot["recommended"]
    f = dict(sp_finish.finish(code))
    for k, v in (slot.get("overrides") or {}).items():
        if isinstance(v, dict) and isinstance(f.get(k), dict):
            f[k] = {**f[k], **v}
        else:
            f[k] = v
    return f, (not slot.get("finish"))


def _match(rec, parts):
    return (rec["obj"] in parts or rec["mesh"] in parts or f"{rec['obj']}:{rec['mat']}" in parts
            or f"{rec['mesh']}:{rec['mat']}" in parts)


def parts_of(set_name, meshes):
    """Подгруппы отделок набора: [{finish, meshes}] и слоты по предложению. Слот sealant (красный лак) — не подгруппа,
    а слой по маске (sealant())."""
    out, cand = [], []
    for slot in _json(SPEC)["slots"]:
        if slot["id"] == "sealant":
            continue
        ms = sorted(n for n, r in meshes.items() if r["set"] == set_name and _match(r, slot["parts"]))
        if ms:
            f, is_cand = _finish(slot)
            out.append({"finish": f, "meshes": ms, "slot": slot["id"]})
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


def paint_fill(set_name, title, mask):
    """Белая эмаль в гравировке — слой над отделками в группе этапа 1 по маске развёртки."""
    import substance_painter.layerstack as L
    import sp_lib
    lay = sp_lib.fill(title, L.InsertPosition.inside_node(_group(set_name), L.NodeStack.Substack),
                      color=PAINT_WHITE["color"], rough=PAINT_WHITE["rough"], metal=PAINT_WHITE["metal"])
    sp_finish.bitmap_mask(lay, mask)
    return lay


def headstamp(set_name, meshes):
    """Клеймо донца «ЧК» / «27» — вдавлено, лак в знаках чуть темнее."""
    import substance_painter.layerstack as L
    import sp_lib
    lay = sp_lib.fill("Клеймо донца «ЧК» / «27» — вдавлено", L.InsertPosition.inside_node(_group(set_name),
                                                                                           L.NodeStack.Substack),
                      color=(0.55, 0.55, 0.55), height=STAMP_DEPTH)
    lay.set_blending_mode(L.BlendingMode.Multiply, sp_lib.CH.BaseColor)
    lay.set_opacity(0.35, sp_lib.CH.BaseColor)
    lay.set_blending_mode(L.BlendingMode.Subtract, sp_lib.CH.Height)
    sp_finish.bitmap_mask(lay, MASKS + "/belt_headstamp.png")
    sp_lib.only_meshes(lay, meshes)
    return lay


def sealant(set_name, meshes, slot):
    """Красный лак — отделка слота sealant подгруппой с маской кольца и полоски у дульца."""
    import substance_painter.layerstack as L
    f, _ = _finish(slot)
    sub = L.insert_group(L.InsertPosition.inside_node(_group(set_name), L.NodeStack.Substack))
    sub.set_name(f"{f['code']} — {f['title']}")
    res = [x for x in TS.all_texture_sets() if x.name() == set_name][0].get_resolution().width
    sp_finish.build_finish(L.InsertPosition.inside_node(sub, L.NodeStack.Substack), f, meshes,
                           _px(set_name), res, _scene())
    sp_finish.bitmap_mask(sub, MASKS + "/belt_sealant.png")
    return sub


def _px(set_name):
    return _json(f"{T.WORK}/uv/{set_name}_report.json")["px_mm"] * T.WORK_RES / T.SETS[set_name][0]


def _scene():
    return _json(os.path.splitext(paths(_proj())[0])[0] + "_scene.json")["size_mm"]


def stack(only=None):
    """Стеки этапа 1 по наборам открытого проекта; итог — _stack_done.txt (когда Painter досчитает), проект сохраняется."""
    import sp_lib
    check_open()
    # зерно и литьё — в мм трёхпроекционно: развёртка high-poly в тысячи островов, по развёртке зерно рвётся на швах
    sp_finish.WORLD_GRAIN = True
    sp_finish.FINE_EDGES = True
    meshes = _json(os.path.splitext(paths(_proj())[0])[0] + "_meshes.json")
    spec = _json(SPEC)
    slots = {s["id"]: s for s in spec["slots"]}
    scene = _scene()
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        parts, cand = parts_of(name, meshes)
        log.append(sp_finish.build_set(name, parts, _px(name), scene))
        if cand:
            log.append("предложение: " + ", ".join(cand))
        if name == "receiver" and os.path.exists(MASKS + "/receiver_fire_paint.png"):
            paint_fill(name, "Белая эмаль в гравировке «ОГОНЬ»", MASKS + "/receiver_fire_paint.png")
            log.append("receiver: «ОГОНЬ» белым")
        if name == "sight" and os.path.exists(MASKS + "/sight_scale_paint.png"):
            paint_fill(name, "Белая эмаль в цифрах и делениях планки", MASKS + "/sight_scale_paint.png")
            log.append("sight: шкала белым")
        if name == "grip" and os.path.exists(MASKS + "/grip_checker.png"):
            import substance_painter.layerstack as L
            lay = sp_lib.fill("Насечка рукоятки — матовее гладкого", L.InsertPosition.inside_node(_group(name),
                                                                                              L.NodeStack.Substack),
                              rough=GRIP_CHECKER_ROUGH)
            sp_finish.bitmap_mask(lay, MASKS + "/grip_checker.png")
            log.append("grip: насечка матовее")
        if name == "belt":
            case = sorted(n for n, r in meshes.items() if r["set"] == "belt" and r["mat"] == "Case_lacquer")
            ring = sorted(n for n, r in meshes.items() if r["set"] == "belt" and r["mat"] in ("Case_lacquer", "Primer"))
            if os.path.exists(MASKS + "/belt_sealant.png"):
                sealant(name, ring, slots["sealant"])
                log.append("belt: красный лак")
            if os.path.exists(MASKS + "/belt_headstamp.png"):
                headstamp(name, case)
                log.append("belt: клеймо донца")

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_stack_done.txt")
    return " | ".join(log)


def export(out_dir, only=None):
    """Карты наборов (glTF PBR: baseColor, ORM, normal) в разрешении набора SETS в out_dir; итог — _export_done.txt."""
    import substance_painter.export as X
    check_open()
    os.makedirs(out_dir, exist_ok=True)
    names = [t.name() for t in TS.all_texture_sets() if not only or t.name() in only]
    pr = [p for p in X.list_predefined_export_presets() if p.name == "glTF PBR Metal Roughness"][0]

    def run():
        n = 0
        for nm in names:
            size = T.SETS[nm][0].bit_length() - 1
            cfg = {"exportShaderParams": False, "exportPath": out_dir, "defaultExportPreset": pr.url,
                   "exportList": [{"rootPath": nm}],
                   "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8",
                                                        "paddingAlgorithm": "infinite", "sizeLog2": size}}]}
            r = X.export_project_textures(cfg)
            n += sum(len(v) for v in r.textures.values())
        for junk in os.listdir(out_dir):          # пресет glTF кладёт и сетку — не нужна
            if junk.startswith("Untitled.") or junk.endswith((".gltf", ".glb", ".bin")):
                os.remove(os.path.join(out_dir, junk))
        return f"{n} карт → {out_dir}"
    import sp_lib
    sp_lib.when_idle(run, "_export_done.txt")
    return "export " + " ".join(names)
