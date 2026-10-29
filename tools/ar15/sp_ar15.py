# AR-15 «ГРАНЬ-15», текстуры этапа 1 (заводское покрытие без износа) в Substance Painter — выполняется внутри Painter
# через мост (tools/ar15/sp_run.py). Порядок слоёв — рецепт «металл слоями» навыка weapon-asset-texturing
# (references/metal-layers.md): основа в вариантах → надписи → кромки и AO → вариации тона → градиенты → сканы →
# вариации блеска → шумы → заводская фактура (фрезеровка, токарка, литьё) → резкость. Износа на этапе 1 нет: ни
# отпечатков, ни пыли, ни царапин, ни вытертых кромок (задание владельца 2026-10-29).
import os

import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.textureset as TS
from substance_painter.textureset import MeshMapUsage as U

import tex_sets as T

JOBS = os.environ.get("SP_BRIDGE_DIR", "")
PROJECT = T.WORK + "/sp/AR15_tex_stage1.spp"


def mark(name, text):
    with open(os.path.join(JOBS, name), "w", encoding="utf-8") as f:
        f.write(text)


def create(fbx):
    """Новый проект из FBX (sp_export.py): нормали OpenGL, касательные по фрагменту, разрешение — по набору."""
    os.environ["OCIO"] = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"
    if P.is_open():
        P.close()
    s = P.Settings(default_texture_resolution=4096, normal_map_format=P.NormalMapFormat.OpenGL,
                   tangent_space_mode=P.TangentSpace.PerFragment)
    P.create(fbx, settings=s)

    def ready(e):
        E.DISPATCHER.disconnect(E.ProjectEditionEntered, ready)
        out = []
        for t in TS.all_texture_sets():
            r = T.SETS.get(t.name(), (4096, None))[0]
            t.set_resolution(TS.Resolution(r, r))
            out.append(f"{t.name()}:{r}")
        mark("_project_ready.txt", "OK " + " ".join(out))
    E.DISPATCHER.connect(E.ProjectEditionEntered, ready)
    return "creating"


def bake(only=None):
    """Карты сетки по наборам очередью: нормаль (своя же сетка — короткие лучи, отбор по имени сетки: иначе лучи
    с тонких деталей ловят соседние), нормали мира, ID, AO, кривизна, положение, толщина. Детали в FBX разложены
    врозь — AO и толщина не берут тень от соседних деталей."""
    sets = [t for t in TS.all_texture_sets() if not only or t.name() in only]
    for t in sets:
        bp = B.BakingParameters.from_texture_set(t)
        bp.set_enabled_bakers([U.Normal, U.WorldSpaceNormal, U.ID, U.AO, U.Curvature, U.Position, U.Thickness])
        c = bp.common()
        n = T.SETS.get(t.name(), (4096, None))[0].bit_length() - 1
        idp = bp.baker(U.ID)
        B.BakingParameters.set({c["OutputSize"]: (n, n), c["LowAsHigh"]: True, c["SubSampling"]: 1,
                                c["MaxDepth"]: 0.0005, c["MaxHeight"]: 0.0005, c["FilterMethod"]: 1,
                                idp["ColorSource"]: 3})
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


def save():
    os.makedirs(os.path.dirname(PROJECT), exist_ok=True)
    P.save_as(PROJECT)
    return PROJECT


def open_project():
    """Открыть сохранённый проект (OCIO — как при создании, иначе Painter висит «busy»); метка _project_ready.txt."""
    os.environ["OCIO"] = "D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"
    if P.is_open():
        P.close()

    def ready(e):
        E.DISPATCHER.disconnect(E.ProjectEditionEntered, ready)
        mark("_project_ready.txt", "OK opened")
    E.DISPATCHER.connect(E.ProjectEditionEntered, ready)
    P.open(PROJECT)
    return "opening"


def probe(names):
    """Параметры генераторов и процедур (имена ключей для set_parameters): временный слой, вывод, удаление."""
    import substance_painter.layerstack as L
    import sp_lib
    st = TS.all_texture_sets()[0].get_stack()
    out = []
    for n in names:
        f = L.insert_fill(L.InsertPosition.from_textureset_stack(st))
        try:
            if n.startswith("mg_") or n.startswith("3d_"):
                f.add_mask(L.MaskBackground.Black)
                g = L.insert_generator_effect(L.InsertPosition.inside_node(f, L.NodeStack.Mask), sp_lib.rid(n, "u:generator"))
                src = g.get_source()
            else:
                src = f.set_source(sp_lib.CH.BaseColor, sp_lib.rid(n, "u:procedural"))
            props = src.get_properties()
            out.append(f"{n}: " + ", ".join(f"{k}={v.value() if hasattr(v, 'value') else v}" for k, v in props.items()))
        except Exception as e:
            out.append(f"{n}: ERROR {e}")
        L.delete_node(f)
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------- материалы и стек
# Класс отделки детали: материал геометрии (Alu_anodized, Steel_black, ...) уточнён по детали — у настоящей AR-15
# ствол, дульный узел и затворная группа нитрированы (атласно-чёрные), мелкая сталь фосфатирована (матовая),
# ударник, ось затвора и отражатель — хромированные, корпус глушителя — термостойкий Cerakote, перегородки — голая
# жаропрочная сталь, подаватель магазина — серый полимер.
NITRIDE = {"Barrel", "Barrel_extension", "Barrel_nut", "Gas_block", "Muzzle_brake", "Muzzle_jam_nut", "Muzzle_lock_collar",
           "Bolt", "Bolt_carrier", "Extractor", "Gas_key"}
CERAKOTE = {"Suppressor_body", "Suppressor_latch"}
# варианты основы — вариант В оставляет чёрными прицелы и рукоятку заряжания (их обычно не красят в цвет коробки)
C_BLACK = {"Charging_handle", "CH_latch_L", "CH_latch_R"}
# рукоять — песочный полимер во всех вариантах (владелец 29.10: «рукоятку ожидаю в таком материале, но в песочном
# цвете», образец — 3DG Modeling, «Курс текстурирование рукоятки», ч. 1–2)
SAND_ALWAYS = {"Pistol_grip"}
SAND_POLY = ((0.53, 0.44, 0.33), 0.62, 0.0)
H0 = 0.5          # уровень высоты основы: рельеф в режиме Overlay работает вокруг 0.5 (на 0 он пропадал целиком)


def klass(info):
    obj, mat = info["obj"], info["mat"]
    if mat == "Alu_anodized":
        return "anod"
    if obj in CERAKOTE:
        return "cerakote"
    if obj.startswith("Suppressor_baffle"):
        return "baffle"
    if obj in NITRIDE or mat == "Steel_nitride":
        return "nitride"
    return {"Steel_black": "phos", "Steel_bare": "bare", "Spring_steel": "spring", "Rubber": "rubber",
            "Brass": "brass", "Bullet_jacket": "jacket",
            "Polymer": "follower" if obj == "Magazine_follower" else "poly"}.get(mat, "phos")


# основа: (цвет sRGB, шероховатость, металличность); неметалл не темнее ~0.06 sRGB (самопроверка review.py: темнее 14/255
# на четверти площади — «исправить»); тёмная сталь ~0.15 sRGB при металле 0.9 (память проекта:
# темнее — читается краской), анодирование — тёмно-серое с атласным блеском, не чёрное (ВСС-М 26.10); при 0.06 на
# пробе AR-15 29.10 отражало меньше чёрного пластика — сплошной чёрный силуэт без фактуры
BASE = {
    "anod": ((0.130, 0.133, 0.142), 0.42, 0.85),
    "nitride": ((0.175, 0.175, 0.18), 0.34, 0.9),
    "phos": ((0.150, 0.150, 0.145), 0.60, 0.75),
    "bare": ((0.60, 0.60, 0.61), 0.20, 1.0),
    "spring": ((0.30, 0.30, 0.31), 0.38, 1.0),
    "cerakote": ((0.085, 0.085, 0.09), 0.58, 0.0),
    "baffle": ((0.42, 0.41, 0.40), 0.45, 1.0),
    "poly": ((0.072, 0.072, 0.072), 0.62, 0.0),
    "follower": ((0.18, 0.18, 0.18), 0.60, 0.0),
    "rubber": ((0.085, 0.085, 0.085), 0.85, 0.0),
    "brass": ((0.80, 0.62, 0.34), 0.24, 1.0),
    "jacket": ((0.78, 0.48, 0.33), 0.25, 1.0),
}
VARIANTS = [
    ("A", "Основа А — чёрное анодирование", {}),
    ("B", "Основа Б — графит, матовее", {"anod": ((0.210, 0.213, 0.222), 0.55, 0.8),
                                       "nitride": ((0.21, 0.21, 0.215), 0.40, 0.9),
                                       "phos": ((0.18, 0.18, 0.175), 0.66, 0.75),
                                       "poly": ((0.105, 0.105, 0.105), 0.68, 0.0)}),
    ("C", "Основа В — песок FDE (Cerakote)", {"anod": ((0.58, 0.49, 0.37), 0.55, 0.0),
                                             "poly": ((0.53, 0.44, 0.33), 0.62, 0.0)}),
]
# надписи лазером: по анодированию — светлый осветлённый оксид; по песочному Cerakote — проступает чёрное
# анодирование под ним; по Cerakote глушителя — светло-серое
LASER = {"A": ((0.55, 0.55, 0.56), 0.62, 0.0), "B": ((0.58, 0.58, 0.59), 0.64, 0.0),
         "C": ((0.06, 0.06, 0.066), 0.45, 0.85), "sup": ((0.50, 0.50, 0.50), 0.60, 0.0)}
MARKS_KIND = {"lower": "laser", "upper": "laser", "handguard": "laser", "suppressor": "laser", "stock": "mold",
              "magazine": "mold"}
METALS = ("anod", "nitride", "phos", "bare", "spring", "baffle", "brass", "jacket")
AO_PARAMS = {"ao_invert": 1}         # маска — углубления (белое там, где AO тёмное)
CURV_PARAMS = {"global_balance": 0.6, "global_contrast": 0.3}   # уже, только сами кромки
SCANS = T.WORK + "/scans"
LATHE_KEYS = ("Barrel", "pin", "screw", "nut", "Buffer", "Gas_tube", "Bolt", "Muzzle", "tube", "Suppressor_body",
              "baffle", "axis", "Firing", "Cam_", "QD", "Selector")
CYL = ("Barrel", "Buffer_tube", "Suppressor_body", "Gas_tube", "Barrel_nut", "Castle_nut", "Muzzle_brake",
       "Muzzle_lock_collar", "Bolt_carrier", "Buffer")


def meshes_info():
    import json
    return json.load(open(T.WORK + "/sp/AR15_sp_meshes.json", encoding="utf-8"))


def _names(st, info, pred):
    have = list(st.material().all_mesh_names())
    out = []
    for m in have:
        key = m if m in info else (m + "__sp" if m + "__sp" in info else None)
        if key and pred(info[key]):
            out.append(m)
    return out


def build(set_name, verbose=False):
    """Стек набора текстур с нуля: группа «Этап 1» — варианты основы (А видна), надписи, объём, тон, градиенты,
    сканы, блеск, шумы, заводская фактура; резкость — эффектом группы."""
    import substance_painter.layerstack as L
    import sp_lib
    import sp_stacks as S
    from sp_lib import fill, only_meshes, triplanar, lop
    CH = sp_lib.CH
    info = meshes_info()
    st = sp_lib.stack_by_name(set_name)
    sp_lib.clear(st)
    cls = {m: klass(info[m if m in info else m + "__sp"]) for m in _names(st, info, lambda i: True)}
    objs = {m: info[m if m in info else m + "__sp"]["obj"] for m in cls}
    of = lambda *ks: [m for m, k in cls.items() if k in ks]   # noqa: E731
    log = []

    grp = L.insert_group(L.InsertPosition.from_textureset_stack(st))
    grp.set_name("Этап 1 — заводская отделка")
    inside = L.InsertPosition.inside_node(grp, L.NodeStack.Substack)
    marks_png = f"{T.WORK}/marks/{set_name}_marks.png"
    has_marks = os.path.exists(marks_png) and set_name in MARKS_KIND

    # 1. основа в вариантах: каждая — своя группа, видна только А
    last = None
    for key, title, over in VARIANTS:
        vg = L.insert_group(inside if last is None else L.InsertPosition.above_node(last))
        vg.set_name(title)
        vin = L.InsertPosition.inside_node(vg, L.NodeStack.Substack)
        n = None
        for k in sorted(set(cls.values())):
            col, rough, metal = over.get(k, BASE[k])
            ms = of(k)
            if key == "C" and k == "anod":
                black = [m for m in ms if set_name == "sights" or objs[m] in C_BLACK]
                ms = [m for m in ms if m not in black]
                if black:
                    b = fill("Анодирование чёрное (прицелы, рукоятка заряжания)",
                             vin if n is None else L.InsertPosition.above_node(n), color=BASE["anod"][0],
                             rough=BASE["anod"][1], metal=BASE["anod"][2], height=H0)
                    only_meshes(b, black)
                    n = b
                if not ms:
                    continue
            if k == "poly":
                sand = [m for m in ms if objs[m] in SAND_ALWAYS]
                ms = [m for m in ms if m not in sand]
                if sand:
                    sf = fill("Полимер песочный (рукоять)", vin if n is None else L.InsertPosition.above_node(n),
                              color=SAND_POLY[0], rough=SAND_POLY[1], metal=SAND_POLY[2], height=H0)
                    only_meshes(sf, sand)
                    n = sf
                if not ms:
                    continue
            f = fill(f"{k}", vin if n is None else L.InsertPosition.above_node(n), color=col, rough=rough, metal=metal,
                     height=H0)
            only_meshes(f, ms)
            n = f
        if has_marks and MARKS_KIND[set_name] == "laser":
            lc = LASER["sup"] if set_name == "suppressor" else LASER[key]
            if key == "C" and set_name in ("upper", "lower", "handguard"):
                lc = LASER["C"]
            mk = fill("Надписи лазером — цвет", L.InsertPosition.above_node(n), color=lc[0], rough=lc[1], metal=lc[2])
            S._bmask(mk, marks_png)
            n = mk
        vg.set_visible(key == "A")
        last = vg

    # 2. надписи — рельеф: лазер чуть врезан, литьё полимера выпуклое и глаже
    n = last
    if has_marks:
        mold = MARKS_KIND[set_name] == "mold"
        # лазер по анодированию — сотые доли мм: при 0.35 стенки букв выходили в отвес, с пиксельной каймой
        h = fill("Надписи — рельеф", L.InsertPosition.above_node(n), height=0.12 if mold else 0.06)
        h.set_blending_mode(L.BlendingMode.LinearDodge if mold else L.BlendingMode.Subtract, CH.Height)
        bm = S._bmask(h, marks_png)
        S._mfilter(bm, "blur", {"intensity": 0.06})
        n = h
        if mold:
            g = fill("Литые надписи — глаже", L.InsertPosition.above_node(n), rough=0.1)
            g.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
            S._bmask(g, marks_png)
            n = g

    def rel(name, pos, color=None, cmode=L.BlendingMode.SoftLight, cop=1.0, rough=None, rmode=None, rop=1.0,
            height=None, hmode=L.BlendingMode.LinearDodge, hop=1.0, meshes=None):
        """Слой-поправка: цвет режимом наложения, шероховатость прибавкой/вычитанием, высота."""
        ch = {}
        if color is not None:
            ch["color"] = color
        if rough is not None:
            ch["rough"] = abs(rough) if not isinstance(rough, str) else rough
        if height is not None:
            ch["height"] = height
        f = fill(name, pos, **ch)
        if color is not None:
            f.set_blending_mode(cmode, CH.BaseColor)
            f.set_opacity(cop, CH.BaseColor)
        if rough is not None:
            f.set_blending_mode(rmode or (L.BlendingMode.Subtract if (not isinstance(rough, str) and rough < 0)
                                          else L.BlendingMode.LinearDodge), CH.SpecularRoughness)
            f.set_opacity(rop, CH.SpecularRoughness)
        if height is not None:
            f.set_blending_mode(hmode, CH.Height)
            f.set_opacity(hop, CH.Height)
        if meshes is not None:
            only_meshes(f, meshes)
        return f

    def proc_mask(layer, proc, scale, params=None, rot=0.0, blend=None, above=None):
        return sp_lib.mask_proc(layer, proc, params, scale=scale, tri=True, rot=rot, blend=blend, above=above)

    hard = of("anod", "nitride", "phos", "bare", "spring", "cerakote", "baffle", "poly", "follower", "brass", "jacket")
    metal = of(*METALS)
    # сталь: сканы металла и тёплые/холодные оттенки — ей; у анодирования (и песочного Cerakote) цвет почти ровный,
    # главный канал — блеск (справка навыка, «Твёрдое анодирование»); на песке сканы давали пятна цвета без пары
    steel = of("nitride", "phos", "bare", "spring", "baffle")
    soft = of("poly", "follower", "rubber", "cerakote")

    # 3. объём: кромки светлее и глаже, углубления темнее и матовее (без вытертого до металла)
    # слабее: плоские верхушки зубьев планки целиком «кромка» и серебрились (снимки 29.10)
    e = rel("Кромки — светлее и глаже", L.InsertPosition.above_node(n), color=(0.80, 0.80, 0.80), cop=0.18,
            rough=-0.04, meshes=hard)
    sp_lib.mask_generator(e, "mg_curvature/mg_curvature", CURV_PARAMS)
    n = e
    # слабее: утопленная площадка рукояти целиком попадала в маску и матовым пятном светлела под светом
    a = rel("Углубления — темнее и матовее (AO)", L.InsertPosition.above_node(n), color=(0.22, 0.22, 0.23),
            cmode=L.BlendingMode.Multiply, cop=0.22, rough=0.04, meshes=of(*cls.values()))
    sp_lib.mask_generator(a, "mg_ambient_occlusion/mg_ambient_occlusion", AO_PARAMS)
    n = a

    # 4. вариации тона с противовесом (светлее ↔ темнее) и крупные градиенты
    t1 = rel("Тон — светлее пятнами", L.InsertPosition.above_node(n), color=(0.78, 0.78, 0.78), cop=0.12,
             rough=-0.18, rop=1.0, meshes=hard)
    proc_mask(t1, "noise_clouds_2/clouds_2", 2.0)
    t2 = rel("Тон — темнее пятнами", L.InsertPosition.above_node(t1), color=(0.22, 0.22, 0.22), cop=0.12,
             rough=0.18, meshes=hard)
    proc_mask(t2, "noise_clouds_3/clouds_3", 2.6, rot=0.3)
    t3 = rel("Тон — холоднее", L.InsertPosition.above_node(t2), color=(0.42, 0.46, 0.55), cop=0.06, rough=-0.10,
             meshes=steel)
    proc_mask(t3, "noise_clouds_1/clouds_1", 1.2)
    t4 = rel("Тон — теплее", L.InsertPosition.above_node(t3), color=(0.56, 0.50, 0.44), cop=0.05, rough=0.10,
             meshes=steel)
    proc_mask(t4, "noise_clouds_1/clouds_1", 1.0, rot=0.5)
    g1 = rel("Градиенты — крупные светлые", L.InsertPosition.above_node(t4), color=(0.75, 0.75, 0.75), cop=0.12,
             rough=-0.15, meshes=hard)
    proc_mask(g1, "noise_clouds_1/clouds_1", 0.4)
    g2 = rel("Градиенты — крупные тёмные", L.InsertPosition.above_node(g1), color=(0.25, 0.25, 0.25), cop=0.12,
             rough=0.15, meshes=hard)
    proc_mask(g2, "noise_clouds_1/clouds_1", 0.35, rot=1.0)
    n = g2
    cyl = [m for m in cls if objs[m] in CYL]
    if cyl:
        # на цилиндре блик собирается в полосу и съедает мелкие пятна — один большой мягкий градиент 40–50 %
        # (мировой линейный градиент не годится: детали в FBX разложены врозь)
        c = rel("Градиент цилиндров — крупный", L.InsertPosition.above_node(n), color=(0.72, 0.72, 0.72), cop=0.45,
                rough=-0.04, meshes=cyl)
        proc_mask(c, "noise_clouds_1/clouds_1", 0.18, rot=0.2)
        c2 = rel("Градиент цилиндров — тёмный", L.InsertPosition.above_node(c), color=(0.28, 0.28, 0.28), cop=0.40,
                 rough=0.04, meshes=cyl)
        proc_mask(c2, "noise_clouds_1/clouds_1", 0.22, rot=2.1)
        n = c2

    # 5. фотосканы металла (ambientCG, CC0) поверх цвета: тёплые и холодные вариации настоящей стали
    if steel:
        sc1 = S._bitmap(f"{SCANS}/Metal046A/Metal046A_2K-JPG_Color.jpg")
        s1 = L.insert_fill(L.InsertPosition.above_node(n))
        s1.set_name("Скан металла — Metal046A (Overlay)")
        # скан и в шероховатости: у пятна цвета — пара в блеске (самопроверка, песочный вариант: пар было 14 %)
        s1.active_channels = {CH.BaseColor, CH.SpecularRoughness}
        s1.set_source(CH.BaseColor, sc1)
        s1.set_source(CH.SpecularRoughness, sc1)
        triplanar(s1, 0.6)
        s1.set_blending_mode(L.BlendingMode.Overlay, CH.BaseColor)
        s1.set_opacity(0.12, CH.BaseColor)
        s1.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
        s1.set_opacity(0.35, CH.SpecularRoughness)
        only_meshes(s1, steel)
        sc2 = S._bitmap(f"{SCANS}/Metal052A/Metal052A_2K-JPG_Color.jpg")
        s2 = L.insert_fill(L.InsertPosition.above_node(s1))
        s2.set_name("Скан металла — Metal052A (Soft Light)")
        s2.active_channels = {CH.BaseColor, CH.SpecularRoughness}
        s2.set_source(CH.BaseColor, sc2)
        s2.set_source(CH.SpecularRoughness, sc2)
        triplanar(s2, 0.9, rot=0.7)
        s2.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
        s2.set_opacity(0.10, CH.BaseColor)
        s2.set_blending_mode(L.BlendingMode.Overlay, CH.SpecularRoughness)
        s2.set_opacity(0.30, CH.SpecularRoughness)
        only_meshes(s2, steel)
        n = s2

    # 6. вариации блеска (только шероховатость, больше, чем в цвете)
    r1 = rel("Блеск — пятна глаже", L.InsertPosition.above_node(n), rough=-0.08, meshes=hard)
    proc_mask(r1, "grunge_spots/grunge_spots", 3.0)
    r2 = rel("Блеск — пятна матовее", L.InsertPosition.above_node(r1), rough=0.07, meshes=hard)
    proc_mask(r2, "noise_bnw_spots_1/bnw_spots_1", 4.0)
    r3 = rel("Блеск — протяжки вдоль детали", L.InsertPosition.above_node(r2), rough=-0.035, meshes=metal)
    proc_mask(r3, "grunge_wipe_brushed/grunge_wipe_brushed", 1.6)
    n = r3

    # 7. шумы — много и разных, светлые и тёмные; хлопья — в блеск
    w1 = rel("Шум белый — светлее", L.InsertPosition.above_node(n), color=(1.0, 1.0, 1.0), cop=0.05,
             rough=-0.04, meshes=hard)
    proc_mask(w1, "white_noise_fast/white_noise_fast", 40.0)
    w2 = rel("Шум чёрный — темнее", L.InsertPosition.above_node(w1), color=(0.0, 0.0, 0.0), cmode=L.BlendingMode.Multiply,
             cop=0.06, rough=0.04, meshes=hard)
    proc_mask(w2, "white_noise_fast/white_noise_fast", 33.0, rot=1.3)
    fl = rel("Хлопья — блеск", L.InsertPosition.above_node(w2), rough="noise_gaussian_noise/gaussian_noise",
             rmode=L.BlendingMode.Overlay, rop=0.25, meshes=metal + of("cerakote"))
    sp_lib.uvscale(fl, 0.5)
    d1 = rel("Точки светлые", L.InsertPosition.above_node(fl), color=(0.85, 0.85, 0.85), cop=0.10, rough=-0.05,
             meshes=hard)
    proc_mask(d1, "noise_bnw_spots_3/bnw_spots_3", 9.0)
    d2 = rel("Точки тёмные", L.InsertPosition.above_node(d1), color=(0.1, 0.1, 0.1), cmode=L.BlendingMode.Multiply,
             cop=0.12, rough=0.05, meshes=hard)
    proc_mask(d2, "noise_bnw_spots_2/bnw_spots_2", 8.0, rot=0.8)
    n = d2

    # 8. заводская фактура
    an = of("anod")
    if an:
        # тонкие параллельные риски фрезы вдоль детали (радиальный шум давал «звёзды» в центрах плиток проекции)
        m1 = rel("Фрезеровка — тонкие риски вдоль детали", L.InsertPosition.above_node(n),
                 rough="noise_anisotropic_noise/anisotropic_noise", rmode=L.BlendingMode.Overlay, rop=0.07,
                 height="noise_anisotropic_noise/anisotropic_noise", hmode=L.BlendingMode.Overlay, hop=0.002,
                 meshes=an)
        triplanar(m1, 3.0)
        for ch_ in ("rough", "height"):
            sp_lib.proc_params(m1, ch_, {"Y_Amount": 1024, "X_Amount": 8})
        m2 = rel("Пескоструй под анодированием — зерно", L.InsertPosition.above_node(m1),
                 rough="noise_gaussian_noise/gaussian_noise", rmode=L.BlendingMode.Overlay, rop=0.30,
                 height="noise_gaussian_noise/gaussian_noise", hmode=L.BlendingMode.Overlay, hop=0.02, meshes=an)
        sp_lib.uvscale(m2, 0.5)
        n = m2
    # тела вращения: ствол, оси, винты, гайки, трубки (на листовой крышке окна и плоских рычагах риски не к месту)
    lathe = [m for m in cls if cls[m] in ("nitride", "phos", "bare", "cerakote", "baffle")
             and any(k in objs[m] for k in LATHE_KEYS)]
    if lathe:
        lt = rel("Токарная обработка — тонкие риски", L.InsertPosition.above_node(n),
                 rough="noise_anisotropic_noise/anisotropic_noise", rmode=L.BlendingMode.Overlay, rop=0.12,
                 height="noise_anisotropic_noise/anisotropic_noise", hmode=L.BlendingMode.Overlay, hop=0.008,
                 meshes=lathe)
        triplanar(lt, 4.0, rot=1.5708)
        for ch_ in ("rough", "height"):
            sp_lib.proc_params(lt, ch_, {"Y_Amount": 1024, "X_Amount": 8})
        n = lt
    pl = of("poly", "follower", "rubber")
    poly = of("poly", "follower")
    if poly:
        # шум литья по образцу (3DG, ч. 1, 30–40 мин): контрастные мелкие точки — светлые глаже, тёмные углублённые
        # матовее, редкие выпуклые микроточки; на рёбрах шума нет (кромка из формы гладкая)
        def no_edges(layer):
            g = sp_lib.mask_generator(layer, "mg_curvature/mg_curvature", {"global_balance": 0.62, "global_contrast": 0.4})
            g.set_blending_mode(L.BlendingMode.Subtract)

        q1 = rel("Полимер — светлые точки (глаже)", L.InsertPosition.above_node(n), color=(1.0, 1.0, 1.0), cop=0.50,
                 rough=-0.28, meshes=poly)
        mf = proc_mask(q1, "white_noise_fast/white_noise_fast", 160.0)
        S._mfilter(mf, "histogram_scan", {"Position": 0.82, "Contrast": 0.85})
        no_edges(q1)
        q2 = rel("Полимер — тёмные точки в углублениях (матовее)", L.InsertPosition.above_node(q1),
                 color=(0.0, 0.0, 0.0), cmode=L.BlendingMode.Multiply, cop=0.45, rough=0.25, height=0.015,
                 hmode=L.BlendingMode.Subtract, meshes=poly)
        mf = proc_mask(q2, "white_noise_fast/white_noise_fast", 140.0, rot=0.9)
        S._mfilter(mf, "histogram_scan", {"Position": 0.80, "Contrast": 0.85})
        no_edges(q2)
        q3 = rel("Полимер — редкие выпуклые микроточки", L.InsertPosition.above_node(q2), color=(0.85, 0.85, 0.85),
                 cop=0.20, rough=-0.10, height=0.02, meshes=poly)
        mf = proc_mask(q3, "noise_bnw_spots_2/bnw_spots_2", 60.0)
        S._mfilter(mf, "histogram_scan", {"Position": 0.75, "Contrast": 0.9})
        proc_mask(q3, "noise_clouds_2/clouds_2", 0.8, blend=L.BlendingMode.Subtract)
        n = q3
    seams_png = f"{T.WORK}/marks/{set_name}_seams.png"
    if poly and os.path.exists(seams_png):
        # шов литья: тонкая линия разъёма формы, чуть неровная (warp), рельеф поверх шума — уровень, а не прибавка
        sw = fill("Шов литья — линия разъёма формы", L.InsertPosition.above_node(n), color=(0.62, 0.62, 0.62),
                  rough=0.10, height=H0 + 0.03)
        sw.set_blending_mode(L.BlendingMode.SoftLight, CH.BaseColor)
        sw.set_opacity(0.35, CH.BaseColor)
        sw.set_blending_mode(L.BlendingMode.Subtract, CH.SpecularRoughness)
        bm = S._bmask(sw, seams_png)
        S._mfilter(bm, "warp", {"intensity": 0.6})
        only_meshes(sw, poly)
        n = sw
    if pl:
        p1 = rel("Литьё — мелкая фактура формы", L.InsertPosition.above_node(n),
                 rough="noise_gaussian_noise/gaussian_noise", rmode=L.BlendingMode.Overlay, rop=0.25,
                 height="noise_gaussian_noise/gaussian_noise", hmode=L.BlendingMode.Overlay, hop=0.012, meshes=pl)
        # трёхпроекционно: в развёртке шум рвался на швах островов (полосы вдоль кромок рукояти)
        triplanar(p1, 250.0, hardness=0.9)
        # тон литья вблизи: без зерна в цвете полимер и латунь на ~1 мм однотонны (самопроверка, 81–83 % площади)
        p0 = rel("Литьё — зерно тона", L.InsertPosition.above_node(p1), color="noise_gaussian_noise/gaussian_noise",
                 cmode=L.BlendingMode.Overlay, cop=0.10, meshes=pl + of("brass", "jacket"))
        triplanar(p0, 250.0, hardness=0.9)
        # ячеистая шагрень (cells) на снимках читалась пенопластом и штукатуркой — убрана; фактуру литья дают точки
        # шума литья (выше) и мелкое зерно
        p1 = p0
        p2 = rel("Литьё — следы течения пластика (блеск)", L.InsertPosition.above_node(p1), rough=-0.06, meshes=pl)
        proc_mask(p2, "grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", 1.4, {"Balance": 0.55, "Contrast": 0.3})
        n = p2
    ck = of("cerakote")
    if ck:
        c1 = rel("Cerakote — порошковое зерно", L.InsertPosition.above_node(n),
                 rough="noise_gaussian_noise/gaussian_noise", rmode=L.BlendingMode.Overlay, rop=0.3,
                 height="noise_gaussian_noise/gaussian_noise", hmode=L.BlendingMode.Overlay, hop=0.015, meshes=ck)
        sp_lib.uvscale(c1, 0.4)
        n = c1

    # 9. резкость на цвет и блеск — эффектом группы
    S._sharpen(grp, 0.3)
    log.append(f"{set_name}: классы " + ", ".join(f"{k}:{len(of(k))}" for k in sorted(set(cls.values()))))
    return "\n".join(log)


def drop_baked_normal():
    """Запечённая «нормаль на себя» (сетка = high-poly) спорит с нормалями сетки по фаскам — полосы вдоль кромок;
    нормаль сетки даёт Blender, в выгрузку — только рельеф из высоты. Карта снимается из настроек набора."""
    out = []
    for t in TS.all_texture_sets():
        try:
            t.get_mesh_map_resource(U.Normal)
            t.set_mesh_map_resource(U.Normal, None)
            out.append(t.name())
        except Exception as e:
            out.append(f"{t.name()}: {e}")
    return " ".join(out)


def show_variant(key):
    """Видна основа варианта key (A / B / C) во всех наборах."""
    import substance_painter.layerstack as L
    title = dict((k, t) for k, t, _ in VARIANTS)[key]
    n = 0
    for t in TS.all_texture_sets():
        for root in L.get_root_layer_nodes(t.get_stack()):
            if root.get_name() != "Этап 1 — заводская отделка":
                continue
            for ch in root.sub_layers():
                if ch.get_name().startswith("Основа "):
                    ch.set_visible(ch.get_name() == title)
                    n += 1
    return n


def export_variant(key, out_dir, sets=None):
    """Карты варианта key — пресет glTF PBR Metal Roughness (baseColor, occlusionRoughnessMetallic, normal), PNG 8 бит.
    Выгрузка — когда Painter досчитает стек (метка _export_<key>.txt)."""
    import sp_lib
    show_variant(key)
    os.makedirs(out_dir, exist_ok=True)

    def run():
        res = []
        for t in TS.all_texture_sets():
            if sets and t.name() not in sets:
                continue
            st, tex = sp_lib.export(out_dir, t.name())
            res.append(f"{t.name()}:{st}:{sum(len(v) for v in tex.values())}")
        return " ".join(res)
    sp_lib.when_idle(run, f"_export_{key}.txt")
    return "export queued " + key
