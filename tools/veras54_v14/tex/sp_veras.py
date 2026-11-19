# ВЕРАС-54 v14, текстуры этап 1 — заводская отделка в Substance Painter на принятой high-poly с развёрткой (tex_uv.py),
# по образцу tools/pkp/sp_pkp.py («Частокол»). Три проекта (tex_sets.PROJECTS: body, front, rear) — свой FBX у каждого
# (sp_export.py). Выполняется внутри Painter через мост (tools/asset_kit/finish/sp_run.py, своя папка заданий
# FINISH_SP_JOBS=_asset_src/veras54_v14/tex/sp_jobs):
#   … -c "import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/veras54_v14/tex'); import sp_veras; print(sp_veras.create('body'))"
#   … print(sp_veras.bake())      → метка _bake_done.txt (по набору, проект сохраняется после каждого)
#   … print(sp_veras.stack())     → _stack_done.txt;  … print(sp_veras.export(<папка>)) → _export_done.txt
# Наборы работают в своём разрешении (tex_sets.SETS, не больше WORK_RES = 4K) — карты сетки и выгрузка в нём же.
# Отделки — finish-spec.json рядом с моделью (пишет tex_spec.py): слот → карточка каталога + overrides; карточки
# строятся теми же функциями и числами (sp_finish.build_set). Капсюль и красный лак — подгруппы по маскам развёртки
# гильзы (tex_marks.py). Маркировка — гравировкой в сетке без заливки (решение владельца).
import json
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

import sp_finish
import tex_sets as T

SPEC = T.MODEL_DIR + "/Карты v14/finish-spec.json"
MASKS = T.WORK + "/masks"
# слоты, которые лежат на части сетки — по маске (не по сеткам)
MASK_SLOTS = {"primer": ("ammo", MASKS + "/ammo_primer.png"), "sealant": ("ammo", MASKS + "/ammo_sealant.png")}
CASE_MESHES = ["Round_Case", "Chambered_Case"]
# поправки агента поверх спецификации (числа — в отчёт, в спецификацию вносит владелец работы).
# Пятна тона (gradients.hue_mm) на автомате длиной 940 мм — крупнее карточки (70 мм давали «камуфляж»): действующий
# размер hue_mm / scale = 150 мм, 2–4 пятна на крышку. Самопроверка v01 (review.py): корпус, ствол и дульное,
# рукоятка и магазин однотонны на 1 и 4 см — как у «Частокола»: крупные градиенты мельче карточки (scale 1,7) и лёгкая
# неровность покрытия (mottle ~26 мм; у полимера — 30 мм в блеске, слои литья карточки сохранены).
# неровность покрытия двумя размерами: ~4 см (самопроверка «издали») и ~1,2 см («средне»); при одном слое 26 мм как у
# «Частокола» чёрная краска оставалась однотонной на 4 см (100 %) — на чёрном разброс тона мал, держит блеск
_MOTTLE_STEEL = [{"type": "mottle", "mm": 80.0, "color": 0.02, "rough": 0.07},
                 {"type": "mottle", "mm": 40.0, "color": 0.01, "rough": 0.03}]
_GRAD = {"color": 0.04, "rough": 0.05, "scale": 1.7, "hue_mm": 255.0}
_POLY_LAYERS = [{"type": "stipple", "dots_mm": 0.1, "rough": 0.25, "height": 0.003}, {"type": "flow", "rough": -0.05},
                {"type": "mottle", "mm": 150.0, "color": 0.015, "rough": 0.05},
                {"type": "mottle", "mm": 40.0, "color": 0.0, "rough": 0.03}]
# сила оттенков (gradients.hue): на чёрном умножение каналов даёт малую разницу в уровнях — при умолчаниях рода
# (покрытие 0,3, металл 0,18) у корпуса R−B ±3 из 255, глазом не видно; владелец просит, чтобы тёплое и холодное читалось
EXTRA = {}  # поправки первого прохода перенесены в спецификацию (tex_spec.py, 2026-11-19)
# второй проход (заводская v03, 2026-11-19): палитра стали владельца — подбор размера и доли пятен тонов на модели
# (при 160 мм / 0,38 у крышки 90 % пикселей укладывались в 40…50 из 255 — почти один тон; у его кадра — от почти
# чёрного до тёплого серого). Числа — агентская поправка поверх finish-spec.json (спецификацию правит владелец работы).
_PAL = {"gradients": {"palette_mm": float(os.environ.get("VERAS_PALETTE_MM", "120")),
                      "palette_cover": float(os.environ.get("VERAS_PALETTE_COVER", "0.5"))}}
EXTRA = {sid: _PAL for sid in ("corpus", "dark", "carrier", "alu")}
_handlers = E.__dict__.setdefault("_veras_handlers", {})
CUR = E.__dict__.setdefault("_veras_cur", {"proj": None})


def paths(proj):
    return T.WORK + f"/sp/VERAS_{proj}.fbx", T.WORK + f"/sp/VERAS_{proj}_v1.spp"


def _disconnect(event, key):
    old = _handlers.pop(key, None)
    if old is not None:
        try:
            E.DISPATCHER.disconnect(event, old)
        except Exception:      # noqa: BLE001
            pass


def _connect(event, fn, key, once=False):
    """Обработчик события по ключу (прежний с тем же ключом снимается); once — одноразовый (обработчик открытия,
    оставшийся висеть, у «Частокола» сохранил следующий проект в чужой файл)."""
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


def _res(set_name):
    return min(T.SETS[set_name][0], T.WORK_RES)


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
    """Проект из FBX: нормали OpenGL, касательные по фрагменту, разрешение набора; метка _project_ready.txt."""
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
            r = _res(t.name())
            t.set_resolution(TS.Resolution(r, r))

        def save_now():
            os.makedirs(os.path.dirname(spp), exist_ok=True)
            P.save_as(spp)
            sp_finish.mark("_project_ready.txt", "OK " + " ".join(
                f"{t.name()}:{t.get_resolution().width}" for t in TS.all_texture_sets()))
        P.execute_when_not_busy(save_now)
    _connect(E.ProjectEditionEntered, ready, "create", once=True)
    return "creating " + proj


def open_project(proj):
    """Открыть проект (открытый закрывается без сохранения); метка _project_ready.txt — когда открыт именно он."""
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
    proj = _proj()
    names = sorted(t.name() for t in TS.all_texture_sets())
    if names != sorted(T.PROJECTS[proj]) or P.file_path().replace("\\", "/").lower() != paths(proj)[1].lower():
        raise RuntimeError(f"открыт не тот проект: {P.file_path()} {names}, ожидался {proj}")


def bake(only=None):
    """Карты сетки, сетка сама себе high-poly: нормали мира, ID, AO, кривизна, положение, толщина — в разрешении набора;
    тень AO только от своей детали (детали в FBX разложены врозь). По одному набору, проект сохраняется после каждого;
    итог — _bake_done.txt."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = _res(t.name()).bit_length() - 1
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
            _disconnect(E.BakingProcessEnded, "bake")
            sp_finish.mark("_bake_done.txt", " ".join(log))
            return
        t = queue.pop(0)
        log.append(t.name())
        B.bake_async(t)
    _connect(E.BakingProcessEnded, nxt, "bake")
    nxt()
    return "bake queue " + " ".join(t.name() for t in sets)


def _merge(a, b):
    out = dict(a)
    for k, v in (b or {}).items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _finish(slot, extra=None):
    """Запись отделки слота с умолчаниями рода (кромки, углубления, градиенты), overrides спецификации и поправки агента
    (EXTRA: «*» — всем слотам, иначе по id слота; extra — поправки вызова) — глубоким слиянием: иначе поправка одного
    числа градиентов стирала бы остальные числа рода."""
    f = sp_finish.resolved(sp_finish.finish(slot["finish"]))
    f = _merge(f, slot.get("overrides") or {})
    for src in (EXTRA, extra or {}):
        f = _merge(f, src.get("*"))
        f = _merge(f, src.get(slot["id"]))
    # род уже подставлен — повторная подстановка в build_finish ничего не стирает (update поверх тех же ключей)
    return f


def parts_of(set_name, meshes, extra=None):
    """Подгруппы отделок набора по сеткам: [{finish, meshes, slot}]."""
    out = []
    for slot in _json(SPEC)["slots"]:
        if slot["id"] in MASK_SLOTS or not slot.get("parts"):
            continue
        ms = sorted(n for n, r in meshes.items() if r["set"] == set_name and r["obj"] in slot["parts"])
        if ms:
            out.append({"finish": _finish(slot, extra), "meshes": ms, "slot": slot["id"]})
    used = {m for p in out for m in p["meshes"]}
    lost = [n for n, r in meshes.items() if r["set"] == set_name and n not in used]
    if lost:
        raise RuntimeError("детали без слота отделки: " + ", ".join(lost))
    return out


def _group(set_name):
    import substance_painter.layerstack as L
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    return [n for n in L.get_root_layer_nodes(st) if n.get_name() == sp_finish.GROUP][0]


def mask_slot(set_name, slot, mask, meshes, extra=None):
    """Отделка слота по маске развёртки (капсюль, красный лак) — подгруппа над отделками набора."""
    import substance_painter.layerstack as L
    f = _finish(slot, extra)
    sub = L.insert_group(L.InsertPosition.inside_node(_group(set_name), L.NodeStack.Substack))
    sub.set_name(f"{f['code']} — {f['title']} (маска)")
    sp_finish.build_finish(L.InsertPosition.inside_node(sub, L.NodeStack.Substack), f, meshes,
                           _px(set_name), _res(set_name), _scene())
    sp_finish.bitmap_mask(sub, mask)
    return sub


def _px(set_name):
    """Плотность развёртки набора в пикселях рабочего разрешения (отчёт tex_uv — в пикселях разрешения набора)."""
    return _json(f"{T.WORK}/uv/{set_name}_report.json")["px_mm"] * _res(set_name) / T.SETS[set_name][0]


def _scene():
    return _json(os.path.splitext(paths(_proj())[0])[0] + "_scene.json")["size_mm"]


def stack(only=None, extra=None):
    """Стеки этапа 1 по наборам открытого проекта; итог — _stack_done.txt (когда Painter досчитает), проект сохраняется.
    extra — поправки поверх спецификации и EXTRA ({"*" или id слота: {...}}) для проб."""
    import sp_lib
    check_open()
    # зерно и литьё — в мм трёхпроекционно (у high-poly тысячи островов: по развёртке зерно рвётся на швах); кривизна —
    # только мелкие масштабы
    sp_finish.WORLD_GRAIN = True
    sp_finish.FINE_EDGES = True
    meshes = _json(os.path.splitext(paths(_proj())[0])[0] + "_meshes.json")
    slots = {s["id"]: s for s in _json(SPEC)["slots"]}
    scene = _scene()
    log = []
    for t in TS.all_texture_sets():
        name = t.name()
        if only and name not in only:
            continue
        log.append(sp_finish.build_set(name, parts_of(name, meshes, extra), _px(name), scene))
        for sid, (sset, mask) in MASK_SLOTS.items():
            if sset == name and sid in slots and os.path.exists(mask):
                case = [m for m in CASE_MESHES if m in meshes]
                mask_slot(name, slots[sid], mask, case, extra)
                log.append(f"{name}: {sid} по маске")

    def done():
        P.save()
        return " | ".join(log)
    sp_lib.when_idle(done, "_stack_done.txt")
    return " | ".join(log)


def export(out_dir, only=None, size=None):
    """Карты наборов (glTF PBR: baseColor, ORM, normal; 8 бит со сглаживанием полос) в разрешении набора в out_dir;
    итог — _export_done.txt."""
    import substance_painter.export as X
    import sp_lib
    check_open()
    os.makedirs(out_dir, exist_ok=True)
    names = [t.name() for t in TS.all_texture_sets() if not only or t.name() in only]
    pr = [p for p in X.list_predefined_export_presets() if p.name == "glTF PBR Metal Roughness"][0]

    def run():
        n = 0
        for nm in names:
            sz = (size or _res(nm)).bit_length() - 1
            cfg = {"exportShaderParams": False, "exportPath": out_dir, "defaultExportPreset": pr.url,
                   "exportList": [{"rootPath": nm}],
                   "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8", "dithering": True,
                                                        "paddingAlgorithm": "infinite", "sizeLog2": sz}}]}
            r = X.export_project_textures(cfg)
            n += sum(len(v) for v in r.textures.values())
        for junk in os.listdir(out_dir):          # пресет glTF кладёт и сетку — не нужна
            if junk.startswith("Untitled.") or junk.endswith((".gltf", ".glb", ".bin")):
                os.remove(os.path.join(out_dir, junk))
        return f"{n} карт → {out_dir}"
    sp_lib.when_idle(run, "_export_done.txt")
    return "export " + " ".join(names)
