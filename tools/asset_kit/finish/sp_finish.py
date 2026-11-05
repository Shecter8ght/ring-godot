# Заводская отделка (этап 1 текстурирования) в Substance Painter — общий стек для каталога отделок и для модели.
# Выполняется внутри Painter через мост (tools/asset_kit/finish/sp_run.py). Отделка — запись каталога
# tools/asset_kit/finish/finishes.json (код, основа, кромки, углубления, градиенты, зерно, особые слои); карточка
# каталога и деталь модели собираются ОДНОЙ функцией build_finish, поэтому выбранное на карточке ложится на модель
# теми же слоями и числами. Порядок слоёв — рецепт «металл слоями» навыка weapon-asset-texturing
# (references/metal-layers.md), числа и запреты — по AR-15 «ГРАНЬ-15» (tools/ar15/sp_ar15.py, этап 1 v5):
# без пятен тона мельче детали (читаются отпечатками), без тексельных точек с порогом («крошка»), без «апельсиновой
# корки» («бугристость»), без сканов и токарных рисок на мелком крепеже («слоистость»); зерно — в мм, масштаб
# процедуры gaussian_noise считается от плотности развёртки (32 ячейки на плитку).
import json
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

ROOT = "E:/Games/RING-godot"
CATALOG = ROOT + "/tools/asset_kit/finish/finishes.json"
OCIO = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"
JOBS = os.environ.get("SP_BRIDGE_DIR", "")
GROUP = "Этап 1 — заводская отделка"
GAUSS_CELLS = 32        # у noise_gaussian_noise 32 ячейки на плитку: масштаб = разрешение / (32 · ячейка в текселях)
H0 = 0.5                # уровень высоты основы: рельеф Overlay работает вокруг 0.5
# зерно и литьё в мм трёхпроекционно, а не по развёртке (ставит задание модели перед build_set): у игровых развёрток
# плотность островов разная, и по развёртке зерно меняло размер на швах. Каталог и прежние модели — по развёртке.
WORLD_GRAIN = False
# кромки (генератор кривизны) — только мелкие масштабы (sharp, fine; ставит задание модели перед build_set): крупные
# масштабы размывают кривизну по развёртке, и у игровой сетки с многими островами давали широкие мягкие полосы блеска
# по плоским граням и ступеньку на каждом шве («рёбра» на борту ИЗЛОМ-45 у затвора, 05.11). У карточек — один остров.
FINE_EDGES = False
_COARSE_CURVATURE = {"curvature_soft": 0.0, "curvature_medium": 0.0, "curvature_large": 0.0, "curvature_big": 0.0,
                     "curvature_huge": 0.0}


def _curv(params):
    """Параметры генератора кривизны с учётом FINE_EDGES."""
    return {**params, **_COARSE_CURVATURE} if FINE_EDGES else params


def mark(name, text):
    with open(os.path.join(JOBS, name), "w", encoding="utf-8") as f:
        f.write(text)


def catalog():
    with open(CATALOG, encoding="utf-8") as f:
        return json.load(f)


def finish(code):
    for f in catalog()["finishes"]:
        if f["code"] == code:
            return f
    raise KeyError("нет отделки " + code)


# ------------------------------------------------------------------------------------------------ проект и запекание
def create(fbx, res=2048):
    """Новый проект из FBX: нормали OpenGL, касательные по фрагменту; метка _project_ready.txt."""
    os.environ["OCIO"] = OCIO
    if P.is_open():
        P.close()
    s = P.Settings(default_texture_resolution=res, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerFragment)
    P.create(fbx, settings=s)

    def ready(e):
        E.DISPATCHER.disconnect(E.ProjectEditionEntered, ready)
        for t in TS.all_texture_sets():
            t.set_resolution(TS.Resolution(res, res))
        mark("_project_ready.txt", "OK " + " ".join(t.name() for t in TS.all_texture_sets()))
    E.DISPATCHER.connect(E.ProjectEditionEntered, ready)
    return "creating"


def bake(only=None):
    """Карты сетки, сетка сама себе high-poly: нормали мира, ID, AO, кривизна, положение, толщина. Нормаль «на себя»
    не печётся — она спорит с нормалями сетки на фасках (полосы вдоль кромок, AR-15 30.10). Метка _bake_done.txt."""
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
        if not queue:
            E.DISPATCHER.disconnect(E.BakingProcessEnded, nxt)
            mark("_bake_done.txt", " ".join(log))
            return
        B.bake_async(queue.pop(0))
    E.DISPATCHER.connect(E.BakingProcessEnded, nxt)
    nxt()
    return "bake queue " + " ".join(t.name() for t in sets)


def save_as(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    P.save_as(path)
    return path


def open_project(path):
    os.environ["OCIO"] = OCIO
    if P.is_open():
        P.close()

    def ready(e):
        E.DISPATCHER.disconnect(E.ProjectEditionEntered, ready)
        mark("_project_ready.txt", "OK opened")
    E.DISPATCHER.connect(E.ProjectEditionEntered, ready)
    P.open(path)
    return "opening"


# ------------------------------------------------------------------------------------------------------ стек отделки
def _mfilter(above, name, params):
    """Фильтр в маске над узлом (histogram_scan — порог и мягкость, warp — неровный край)."""
    import substance_painter.layerstack as L
    import sp_lib
    e = L.insert_filter_effect(L.InsertPosition.above_node(above), sp_lib.rid(name + "/" + name, "u:filter"))
    e.get_source().set_parameters(params)
    return e


def _sharpen(grp, amount=0.3):
    """Слабая резкость в конце — эффектом группы и только на цвет и блеск (по высоте «звенит» на краях островов)."""
    import substance_painter.layerstack as L
    import sp_lib
    sh = L.insert_filter_effect(L.InsertPosition.inside_node(grp, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    sh.get_source().set_parameters({"intensity": amount})
    sh.active_channels = {sp_lib.CH.BaseColor, sp_lib.CH.SpecularRoughness}
    return sh


def _params(d):
    """Параметры ресурса из JSON: список из трёх чисел — цвет sRGB, остальное как есть."""
    import sp_lib
    out = {}
    for k, v in d.items():
        if isinstance(v, list) and len(v) == 3:
            out[k] = sp_lib._val(tuple(v))
        else:
            out[k] = tuple(v) if isinstance(v, list) else v
    return out


def resolved(f):
    """Отделка с подставленными умолчаниями её рода (кромки, углубления, градиенты)."""
    kinds = catalog()["kinds"]
    out = dict(kinds.get(f.get("kind", "coating"), {}))
    out.update(f)
    return out


def build_finish(pos, f, meshes=None, px_mm=10.85, res=2048, bbox_mm=170.0):
    """Слои отделки f (запись каталога) в позицию pos, только на сетках meshes (None — весь набор); возвращает
    последний узел. px_mm — плотность развёртки набора (пикселей на мм), res — его разрешение, bbox_mm — наибольший
    размер набора в мм (для трёхпроекционных узоров: шлифовка, карбон, дерево, пятна закалки). Порядок: основа (или
    материал) → особые слои цвета (переход, пятна закалки) → кромки → углубления → крупные градиенты → зерно →
    особые слои фактуры (шлифовка, точки литья, следы течения)."""
    import substance_painter.layerstack as L
    import sp_lib
    CH = sp_lib.CH
    f = resolved(f)
    tag = f["code"]

    def scope(layer):
        if meshes:
            sp_lib.only_meshes(layer, meshes)
        return layer

    def rel(name, pos, color=None, cmode=L.BlendingMode.SoftLight, cop=1.0, rough=None, rmode=None, rop=1.0,
            height=None, hmode=L.BlendingMode.LinearDodge, hop=1.0):
        """Слой-поправка: цвет режимом наложения, шероховатость прибавкой/вычитанием (по знаку), высота; строка —
        процедура."""
        ch = {}
        if color is not None:
            ch["color"] = color
        if rough is not None:
            ch["rough"] = abs(rough) if not isinstance(rough, str) else rough
        if height is not None:
            ch["height"] = height
        lay = sp_lib.fill(f"{tag} · {name}", pos, **ch)
        if color is not None:
            lay.set_blending_mode(cmode, CH.BaseColor)
            lay.set_opacity(cop, CH.BaseColor)
        if rough is not None:
            lay.set_blending_mode(rmode or (L.BlendingMode.Subtract if (not isinstance(rough, str) and rough < 0)
                                            else L.BlendingMode.LinearDodge), CH.SpecularRoughness)
            lay.set_opacity(rop, CH.SpecularRoughness)
        if height is not None:
            lay.set_blending_mode(hmode, CH.Height)
            lay.set_opacity(hop, CH.Height)
        return scope(lay)

    def gauss_uv(layer, cell_mm):
        """Гауссов шум ячейкой cell_mm (32 ячейки на плитку процедуры): по развёртке от средней плотности набора, а при
        WORLD_GRAIN — трёхпроекционно в миллиметрах (игровая развёртка с разной плотностью островов: по развёртке зерно
        меняло размер на швах — линии и «рёбра», ИЗЛОМ-45 05.11)."""
        if WORLD_GRAIN:
            sp_lib.triplanar(layer, bbox_mm / (GAUSS_CELLS * max(cell_mm, 0.01)))
        else:
            sp_lib.uvscale(layer, res / (GAUSS_CELLS * max(cell_mm * px_mm, 0.5)))

    def tri_mm(layer, period_mm, rot=0.0):
        """Трёхпроекционно, плитка узора — period_mm (масштаб Painter — плиток на наибольший размер всей сцены проекта,
        не набора: bbox_mm — габарит сцены; замер ИЗЛОМ-45 05.11)."""
        sp_lib.triplanar(layer, bbox_mm / period_mm, rot)

    # постоянные масштабы процедур (облака градиентов, следы течения) подобраны на карточке — образец ~170 мм; Painter
    # считает плитки на всю сцену, и у игровой сетки (сцена ИЗЛОМ-45 — 1082 мм) пятна выходили в 6 раз крупнее, магазины
    # однотонные (самопроверка v4) — при WORLD_GRAIN масштаб от габарита сцены, пятна того же размера в мм, что на карточке
    card_k = bbox_mm / 170.0 if WORLD_GRAIN else 1.0

    def above(node):
        return L.InsertPosition.above_node(node)

    # 1. основа: однотонная заливка или материал Painter (карбон, дерево) с параметрами каталога
    b = f["base"]
    if f.get("material"):
        m = f["material"]
        n = L.insert_fill(pos)
        n.set_name(f"{tag} · основа — {m['res'].split('/')[0]}")
        src = n.set_material_source(sp_lib.rid(m["res"], "u:material"))
        src.set_parameters(_params(m.get("params", {})))
        tri_mm(n, m.get("mm", 20.0))
        scope(n)
    else:
        n = scope(sp_lib.fill(f"{tag} · основа", pos, color=tuple(b["color"]), rough=b["rough"], metal=b["metal"],
                              height=H0))

    # 2. особые слои цвета
    for sp in f.get("layers") or []:
        if sp["type"] == "ramp":
            # переход цвета вдоль оси: каждая ступень закрывает всё дальше своего порога (положение запечено)
            axis = {"x": "rightleft", "y": "topbottom", "z": "frontback"}[sp.get("axis", "x")]
            gp = {f"position_direction_{a}_opacity": (1.0 if a == axis else 0.0)
                  for a in ("rightleft", "topbottom", "frontback")}
            for p, col, rough, metal in sp["stops"]:
                lay = scope(sp_lib.fill(f"{tag} · переход {p:.2f}", above(n), color=tuple(col), rough=rough, metal=metal))
                g = sp_lib.mask_generator(lay, "mg_position/mg_position", gp)
                last = _mfilter(g, "histogram_scan", {"Position": 1.0 - p, "Contrast": sp.get("contrast", 0.4)})
                if sp.get("warp"):
                    _mfilter(last, "warp", {"intensity": sp["warp"]})
                n = lay
        elif sp["type"] == "blotch":
            # закалка с цветами: пятна цвета крупными шумами с порогом, у каждого — свой шум и поворот
            for i, (col, rough, metal, cover, period, proc) in enumerate(sp["items"]):
                lay = scope(sp_lib.fill(f"{tag} · пятна {i + 1}", above(n), color=tuple(col), rough=rough, metal=metal))
                mf = sp_lib.mask_proc(lay, proc, scale=bbox_mm / (period * 70.0), tri=True, rot=0.7 * i)
                _mfilter(mf, "histogram_scan", {"Position": cover, "Contrast": 0.25})
                _mfilter(mf, "warp", {"intensity": 0.25})
                n = lay

    # 3. объём: кромки (у покрытий — только глаже: светлые кромки цветом читаются вытертыми), углубления (AO)
    e = f.get("edges")
    if e and (e.get("color") or e.get("rough")):
        lay = rel("кромки", above(n), color=(0.80, 0.80, 0.80) if e.get("color") else None, cop=e.get("color") or 0.0,
                  rough=e.get("rough") or None)
        sp_lib.mask_generator(lay, "mg_curvature/mg_curvature", _curv({"global_balance": 0.6, "global_contrast": 0.3}))
        n = lay
    c = f.get("cavity")
    if c:
        lay = rel("углубления (AO)", above(n), color=(0.22, 0.22, 0.23), cmode=L.BlendingMode.Multiply,
                  cop=c.get("color", 0.0), rough=c.get("rough") or None)
        sp_lib.mask_generator(lay, "mg_ambient_occlusion/mg_ambient_occlusion", {"ao_invert": 1})
        n = lay

    # 4. только крупные мягкие градиенты: пятна мельче детали читаются отпечатками пальцев (AR-15, 30.10)
    gr = f.get("gradients")
    if gr:
        k = card_k
        g1 = rel("градиент светлый", above(n), color=(0.75, 0.75, 0.75), cop=gr["color"], rough=-gr["rough"])
        sp_lib.mask_proc(g1, "noise_clouds_1/clouds_1", scale=0.4 * k)
        g2 = rel("градиент тёмный", above(g1), color=(0.25, 0.25, 0.25), cop=gr["color"], rough=gr["rough"])
        sp_lib.mask_proc(g2, "noise_clouds_1/clouds_1", scale=0.35 * k, rot=1.0)
        n = g2

    # 5. зерно отделки — Overlay гауссова шума в блеск, цвет и рельеф; без порога (порог даёт «крошку»)
    gn = f.get("grain")
    if gn:
        kw = {}
        if gn.get("rough"):
            kw.update(rough="noise_gaussian_noise/gaussian_noise", rmode=L.BlendingMode.Overlay, rop=gn["rough"])
        if gn.get("color"):
            kw.update(color="noise_gaussian_noise/gaussian_noise", cmode=L.BlendingMode.Overlay, cop=gn["color"])
        if gn.get("height"):
            kw.update(height="noise_gaussian_noise/gaussian_noise", hmode=L.BlendingMode.Overlay, hop=gn["height"])
        if kw:
            lay = rel(f"зерно {gn['mm']:.2f} мм", above(n), **kw)
            gauss_uv(lay, gn["mm"])
            n = lay

    # 6. особые слои фактуры
    for sp in f.get("layers") or []:
        if sp["type"] == "brushed":
            # шлифовка: продольные риски в блеске (и чуть в цвете и рельефе) вдоль наибольшей оси детали
            proc = "noise_anisotropic_noise/anisotropic_noise"
            lay = rel("шлифовка", above(n), color=proc, cmode=L.BlendingMode.Overlay, cop=sp.get("color", 0.0),
                      rough=proc, rmode=L.BlendingMode.Overlay, rop=sp["rough"], height=proc,
                      hmode=L.BlendingMode.Overlay, hop=sp.get("height", 0.0))
            tri_mm(lay, sp.get("mm", 6.0))
            n = lay
        elif sp["type"] == "stipple":
            # шум литья по 3DG (AR-15, рукоять): светлые точки глаже, тёмные углублённые матовее, на рёбрах шума нет
            dots = max(sp.get("dots_mm", 0.10) * px_mm, 0.8)

            def no_edges(layer):
                g = sp_lib.mask_generator(layer, "mg_curvature/mg_curvature",
                                          _curv({"global_balance": 0.62, "global_contrast": 0.4}))
                g.set_blending_mode(L.BlendingMode.Subtract)
            q1 = rel("литьё — светлые точки (глаже)", above(n), color=(1.0, 1.0, 1.0), cop=0.25,
                     rough=-sp.get("rough", 0.25))
            # белый шум — ячейка на пиксель плитки (res на плитку): по развёртке 1/dots, в мм — набор / (точка × res)
            wscale = bbox_mm / (sp.get("dots_mm", 0.10) * res) if WORLD_GRAIN else 1.0 / dots
            mf = sp_lib.mask_proc(q1, "white_noise_fast/white_noise_fast", scale=wscale, tri=WORLD_GRAIN)
            _mfilter(mf, "histogram_scan", {"Position": 0.15, "Contrast": 0.85})
            no_edges(q1)
            q2 = rel("литьё — тёмные точки (матовее)", above(q1), color=(0.0, 0.0, 0.0), cmode=L.BlendingMode.Multiply,
                     cop=0.18, rough=sp.get("rough", 0.25) * 0.72, height=sp.get("height", 0.003),
                     hmode=L.BlendingMode.Subtract)
            mf = sp_lib.mask_proc(q2, "white_noise_fast/white_noise_fast", scale=wscale, tri=WORLD_GRAIN, rot=0.9)
            _mfilter(mf, "histogram_scan", {"Position": 0.15, "Contrast": 0.85})
            no_edges(q2)
            n = q2
        elif sp["type"] == "flow":
            # следы течения пластика — мягкие разводы в блеске
            lay = rel("литьё — следы течения (блеск)", above(n), rough=sp.get("rough", -0.05))
            sp_lib.mask_proc(lay, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft",
                             {"Balance": 0.55, "Contrast": 0.3}, scale=1.4 * card_k)
            n = lay
        elif sp["type"] == "photo":
            # фотоматериал CC0 по развёртке (сырьё — sp["set"]: <путь>_Color/_Roughness/_Displacement.jpg): тон
            # и волокна — наложением на основу (свой оттенок отделки остаётся), рельеф — картой высоты, блеск — картой
            # шероховатости; волокна идут вдоль U (у досок развёртка выровнена по длине), плитка образца — mm
            stem = f"{ROOT}/{sp['set']}"
            lay = L.insert_fill(above(n))
            lay.set_name(f"{tag} · фото {sp['set'].rsplit('/', 1)[-1]}")
            chans = {CH.BaseColor: _bitmap(f"{stem}_Color.jpg")}
            if sp.get("rough"):
                chans[CH.SpecularRoughness] = _bitmap(f"{stem}_Roughness.jpg")
            if sp.get("height"):
                chans[CH.Height] = _bitmap(f"{stem}_Displacement.jpg")
            lay.active_channels = set(chans)
            for c, src in chans.items():
                lay.set_source(c, src)
            lay.set_blending_mode(L.BlendingMode.Overlay, CH.BaseColor)
            lay.set_opacity(sp.get("color", 0.5), CH.BaseColor)
            if sp.get("rough"):
                lay.set_opacity(sp["rough"], CH.SpecularRoughness)
            if sp.get("height"):
                lay.set_blending_mode(L.BlendingMode.Overlay, CH.Height)
                lay.set_opacity(sp["height"], CH.Height)
            sp_lib.uvscale(lay, res / max(sp.get("mm", 500.0) * px_mm, 1.0))
            n = scope(lay)
    return n


def _bitmap(path):
    """Картинка ресурсом проекта (имя — с отметкой времени файла, чтобы перезаписанная карта не бралась прежней)."""
    import substance_painter.resource as R
    stem = path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    name = f"{stem}_{int(os.path.getmtime(path))}"
    for r in R.search("u:texture"):
        if r.identifier().name == name:
            return r.identifier()
    return R.import_project_resource(path, R.Usage.TEXTURE, name=name).identifier()


def bitmap_mask(node, path):
    """Маска слоя или группы — ч/б карта по развёртке (белое — слой виден); путь — PNG того же размера, что набор."""
    import substance_painter.layerstack as L
    if not node.has_mask():
        node.add_mask(L.MaskBackground.Black)
    m = L.insert_fill(L.InsertPosition.inside_node(node, L.NodeStack.Mask))
    m.set_source(None, _bitmap(path))
    m.set_projection_mode(L.ProjectionMode.UV)
    return m


def build_set(set_name, parts, px_mm, bbox_mm=170.0, sharpen=0.3):
    """Стек набора с нуля: группа «Этап 1 — заводская отделка», в ней по подгруппе на отделку (parts — список
    {"finish": код или запись каталога, "meshes": [...] или None, "mask": путь к ч/б карте или нет}); резкость —
    эффектом группы."""
    import substance_painter.layerstack as L
    import sp_lib
    st = sp_lib.stack_by_name(set_name)
    sp_lib.clear(st)
    res = [t for t in TS.all_texture_sets() if t.name() == set_name][0].get_resolution().width
    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name(GROUP)
    last = None
    log = []
    for part in parts:
        f = part["finish"] if isinstance(part["finish"], dict) else finish(part["finish"])
        sub = L.insert_group(L.InsertPosition.inside_node(grp, L.NodeStack.Substack) if last is None
                             else L.InsertPosition.above_node(last))
        sub.set_name(f"{f['code']} — {f['title']}")
        build_finish(L.InsertPosition.inside_node(sub, L.NodeStack.Substack), f, part.get("meshes"), px_mm, res, bbox_mm)
        if part.get("mask"):
            # граница отделок внутри одной сетки (верх и низ корпуса одним телом) — ч/б карта по развёртке на группе
            bitmap_mask(sub, part["mask"])
        last = sub
        log.append(f"{f['code']}:{len(part.get('meshes') or [])}")
    if sharpen:
        _sharpen(grp, sharpen)
    return f"{set_name}: " + " ".join(log)


def card(code, out_dir, px_mm, bbox_mm=170.0):
    """Карточка каталога: стек образца в отделке code и выгрузка карт (glTF: baseColor, ORM, normal) в out_dir;
    метка _card_<code>.txt — когда Painter досчитает стек и выгрузит."""
    import sp_lib
    name = TS.all_texture_sets()[0].name()
    log = build_set(name, [{"finish": code, "meshes": None}], px_mm, bbox_mm)
    os.makedirs(out_dir, exist_ok=True)

    def run():
        status, tex = sp_lib.export(out_dir, name)
        return f"{status} {sum(len(v) for v in tex.values())}"
    sp_lib.when_idle(run, f"_card_{code}.txt")
    return log
