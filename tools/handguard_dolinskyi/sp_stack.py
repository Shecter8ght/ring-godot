# Цевьё Dolinskyi: стек Substance Painter как в ролике «Realistic Hard-Anodized Metal in Substance Painter» (кадр 13:20,
# папки сверху вниз: CC_GLoss, shapen, AO, Dirt, edges, weathering, decals, Height/Normal, Color variations, BASE).
# Числа, видимые в ролике, — как есть (см. docs/assets/handguard_dolinskyi_plan.md, «видно»); остальное — подбор по кадрам.
# Где у автора мазок кистью (Paint в маске), здесь — пустой слой рисования «РУКАМИ: …» на том же месте (для ручной
# доработки) и под ним маска-картинка из masks.py, которая делает то же, что мазок. Каналы — Diffuse / Specular /
# Glossiness / Height (шаблон PBR Specular Glossiness, как у автора); нормали папок смешиваются в Normal Map Detail.
#   python -X utf8 tools/handguard_dolinskyi/sp_run.py -c "import sp_stack; print(sp_stack.build())" 600
import os

import sp_lib
import substance_painter.colormanagement as CM
import substance_painter.layerstack as L
import substance_painter.resource as R
import substance_painter.textureset as TS
from substance_painter.levels import LevelsParamsMono
from substance_painter.textureset import ChannelType as CH

MASKS = "E:/Games/RING-godot/_asset_src/handguard_dolinskyi/masks"
CHK = {"diff": CH.Diffuse, "spec": CH.Specular, "gloss": CH.Glossiness, "height": CH.Height}
COLOR_CH = ("diff", "spec")
BM = L.BlendingMode
# износ кромок: у автора — тонкие светлые кромки и мягкие вмятины; по умолчанию генератор кладёт широкую кайму
EDGE_THIN = {"Wear_Level": 0.12, "Wear_Contrast": 0.85, "Grunge_Amount": 0.3}
EDGE_SOFT = {"Wear_Level": 0.1, "Wear_Contrast": 0.7, "Grunge_Amount": 0.6}
_TEX = {}


def hexc(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def tex(path):
    """Картинка проекта (маска, фото) — один раз на проект."""
    if path in _TEX:
        return _TEX[path]
    name = os.path.splitext(os.path.basename(path))[0]
    for r in R.search("u:texture"):
        if r.identifier().name == name and "project" in r.identifier().url():
            _TEX[path] = r.identifier()
            return _TEX[path]
    _TEX[path] = R.import_project_resource(path, R.Usage.TEXTURE).identifier()
    return _TEX[path]


def proc(name):
    return sp_lib.rid(name, "u:procedural")


def _src(f, ch, v):
    if isinstance(v, str):
        if v.endswith((".png", ".jpg")):
            return f.set_source(ch, tex(v))
        return f.set_source(ch, proc(v))
    if ch is None or ch in (CH.Diffuse, CH.Specular):
        return f.set_source(ch, sp_lib._val(hexc(v) if isinstance(v, str) else v))
    return f.set_source(ch, CM.Color(v, v, v, color_space=CM.GenericColorSpace.Raw))


def fill(name, pos, opacity=1.0, **ch):
    """Заливка: diff / spec — «#rrggbb» (sRGB) или имя ресурса; gloss / height — число."""
    f = L.insert_fill(pos)
    f.set_name(name)
    f.active_channels = {CHK[k] for k in ch}
    for k, v in ch.items():
        if k in COLOR_CH and isinstance(v, str) and v.startswith("#"):
            f.set_source(CHK[k], sp_lib._val(hexc(v)))
        else:
            _src(f, CHK[k], v)
    if opacity != 1.0:
        for c in f.active_channels:
            f.set_opacity(opacity, c)
    return f


def group(name, pos, passthrough=False, visible=True):
    g = L.insert_group(pos)
    g.set_name(name)
    st = g.get_stack()
    for c in st.all_channels():
        if passthrough:
            g.set_blending_mode(BM.Passthrough, c)
    try:
        if not passthrough:
            g.set_blending_mode(BM.NormalMapDetail, CH.Normal)     # у автора все папки в канале Normal — NMdt
    except Exception:          # noqa: BLE001
        pass
    g.set_visible(visible)
    return g


def top(st):
    return L.InsertPosition.from_textureset_stack(st)


def inside(g):
    return L.InsertPosition.inside_node(g, L.NodeStack.Substack)


class Mask:
    """Маска слоя снизу вверх, как в списке Painter (первый вызов — самый нижний эффект)."""

    def __init__(self, layer, white=False):
        self.layer = layer
        layer.add_mask(L.MaskBackground.White if white else L.MaskBackground.Black)
        self.last = None

    def _pos(self):
        return (L.InsertPosition.above_node(self.last) if self.last is not None
                else L.InsertPosition.inside_node(self.layer, L.NodeStack.Mask))

    def _done(self, e, blend, opacity, name):
        if blend is not None:
            e.set_blending_mode(blend)
        if opacity != 1.0:
            e.set_opacity(opacity)
        if name:
            e.set_name(name)
        self.last = e
        return e

    def fill(self, source, blend=None, opacity=1.0, tri=None, rot=0.0, params=None, name=None, invert=False):
        e = L.insert_fill(self._pos())
        if isinstance(source, L.AnchorPointEffectNode):
            src = e.set_source(None, source)
        elif isinstance(source, (int, float)):
            src = e.set_source(None, CM.Color(source, source, source, color_space=CM.GenericColorSpace.Raw))
        else:
            src = _src(e, None, source)
            for k, v in (params or {}).items():       # у процедур нет общего зерна — несуществующее пропускаем
                try:
                    src.set_parameters({k: v})
                except KeyError:
                    print("нет параметра", k, "у", source)
            if tri:
                sp_lib.triplanar(e, tri, rot)
            if invert:
                try:
                    src.set_parameters({"invert": True})
                except Exception:      # noqa: BLE001
                    pass
        return self._done(e, blend, opacity, name), src

    def gen(self, name, blend=None, opacity=1.0, params=None):
        e = L.insert_generator_effect(self._pos(), sp_lib.rid(name, "u:generator"))
        if params:
            e.get_source().set_parameters(params)
        return self._done(e, blend, opacity, None)

    def filt(self, name, params=None, blend=None, opacity=1.0):
        e = L.insert_filter_effect(self._pos(), sp_lib.rid(name + "/" + name, "u:filter"))
        if params:
            e.get_source().set_parameters(params)
        return self._done(e, blend, opacity, None)

    def levels(self, lo=0.0, hi=1.0, gamma=1.0, out_lo=0.0, out_hi=1.0, visible=True):
        e = L.insert_levels_effect(self._pos())
        e.set_parameters(LevelsParamsMono(input_min=lo, input_max=hi, gamma=gamma, output_min=out_lo,
                                          output_max=out_hi, clamp=False))
        e.set_visible(visible)
        self.last = e
        return e

    def paint(self, what, blend=None, visible=True):
        """Место мазка автора: пустой слой рисования — сюда владелец кладёт мазки руками."""
        e = L.insert_paint(self._pos())
        e.set_name("РУКАМИ: " + what)
        if blend is not None:
            e.set_blending_mode(blend)
        e.set_visible(visible)
        self.last = e
        return e

    def anchor(self, name):
        e = L.insert_anchor_point_effect(self._pos(), name)
        self.last = e
        return e


def mask_png(name):
    return f"{MASKS}/{name}.png"


# ---------- папки снизу вверх ----------

def base(st):
    g = group("BASE", top(st))
    fill("Color", inside(g), diff="#1D1D1E", spec="#383838", gloss=0.40)          # 4:50, видно
    mf = L.insert_paint(inside(g))
    mf.set_name("MatFinish Powder Coated")
    for c in st.all_channels():
        mf.set_blending_mode(BM.Passthrough, c)
    fx = L.insert_filter_effect(L.InsertPosition.inside_node(mf, L.NodeStack.Content),
                                sp_lib.rid("matfinish_powder_coated/matfinish_powder_coated", "u:filter"))
    # у автора Scale 6 (видно) — при его плотности развёртки; у нас 6,6 пикс/мм, и 6 даёт ячейку ~1,2 мм — кляксы.
    # На его кадре маски (6:00) зерно ~0,15 мм; у нас ячейка в тексель (Scale 40) крупным планом — квадраты и песок
    # (владелец 01.11: «шумная, грязная, как будто поломанная»): Scale 24 — ячейка ~2 текселя (0,3 мм)
    fx.get_source().set_parameters({"tile": 24, "Normal_Slope_Max": 0.5})
    anc = L.insert_anchor_point_effect(L.InsertPosition.above_node(fx), "MatFinish Powder Coated")
    # в нормаль зерно — на четверть: на крупном плане автора (12:46) грань гладкая, зерно у него уходит через якорь
    # в блеск и цвет (якорь берёт выход фильтра до прозрачности слоя — «noise» ниже не меняется)
    for c in (CH.Normal, CH.Height):
        mf.set_opacity(0.25, c)
    n = fill("noise", inside(g), opacity=0.44, diff="#3F4145", gloss=0.6704)       # 44 %, видно
    m = Mask(n)
    _, src = m.fill(anc)
    src.referenced_channel = CH.Normal                                              # канал Normal, Keep alpha — видно
    src.set_levels(LevelsParamsMono(input_min=0.004, input_max=0.788, gamma=1.0, output_min=0.0, output_max=1.0,
                                    clamp=False))                                   # 0.004 / 1 / 0.788 — видно
    return g


def color_variations(st):
    g = group("Color variations", top(st), passthrough=True)
    f = fill("oclussion", inside(g), opacity=0.55, diff="#0D0E10")                 # оценка: тёмная глубина
    m = Mask(f)
    m.paint("добавить глубины, где мало")
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.LinearDodge)
    m.fill("grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", BM.Subtract, 0.6, tri=3.0)
    m.fill("grunge_wipe_smudgy_soft/grunge_wipe_smudgy_soft", BM.LinearDodge, 0.35, tri=5.0, rot=0.37,
           params={"$randomseed": 7})
    m.paint("пятна тона")
    m.gen("mg_curvature/mg_curvature", BM.Subtract, 0.5)
    m.paint("убрать лишнее")
    return g


def height_normal(st):
    g = group("Height/Normal", top(st))
    mil = group("milling", inside(g))
    # следы торцевой фрезы на площадках и торцах (у автора — десятки заливок «milling» в Linear Dodge по местам)
    for nm, png in (("milling left", "milling_arcs"), ("milling top", "milling_arcs")):
        f = fill(nm, inside(mil), height=-0.003 if nm == "milling left" else -0.002)
        m = Mask(f)
        m.fill(mask_png(png), BM.LinearDodge)
        m.paint("места следов фрезы", BM.Multiply)
        m.levels(0.05, 0.9)
        if nm == "milling top":
            f.set_visible(False)        # у автора два слоя одного рода — второй держим про запас
    ln = group("lines", inside(mil))
    m = Mask(ln, white=True)
    m.paint("где рисок нет")
    m.gen("mg_curvature/mg_curvature", BM.Subtract, 0.4)
    m.fill("grunge_dust_wide/grunge_dust_wide", BM.Subtract, 0.3, tri=3.0)
    f = fill("lines", inside(ln), height=-0.005)
    Mask(f).fill(mask_png("milling_lines"))
    ln2 = group("lines 02", inside(mil))
    f = fill("lines 02", inside(ln2), height=-0.003)
    m = Mask(f)
    m.fill(mask_png("milling_lines"))
    m.fill("noise_clouds_2/clouds_2", BM.Multiply, tri=2.0)
    # неровность металла: анизотропный шум вдоль оси (полировка, вытяжка профиля)
    f = fill("metal imperfection", inside(g), opacity=0.3, height=-0.002)
    m = Mask(f)
    m.fill("noise_anisotropic_noise/anisotropic_noise", tri=4.0)
    m.paint("убрать на мелочи", BM.Multiply)
    m.paint("добавить пятнами")
    m.anchor("metal imperfection mask")
    # мягкие вмятины на кромках: «металл никогда не бывает таким прямым и ровным»
    f = fill("soft", inside(g), opacity=0.7, height=-0.015)
    m = Mask(f)
    m.gen("mg_metal_edge_wear/mg_metal_edge_wear", params=EDGE_SOFT)
    m.fill("grunge_pebbles_spots/grunge_pebbles_spots", BM.Multiply, tri=4.0)
    m.filt("blur", {"intensity": 0.6})
    ed = group("edge damage", inside(g))
    for nm, thr, h in (("hard+height", 0.5, -0.03), ("hard+height 1", 0.18, -0.08)):
        f = fill(nm, inside(ed), diff="#2B2C2E", gloss=0.55, height=h)               # сколы: чуть светлее, глаже
        m = Mask(f)
        m.fill(mask_png("chips"))
        m.filt("histogram_scan", {"Position": thr, "Contrast": 0.85})
        m.filt("warp", {"intensity": 0.6})
        m.fill("grunge_pebbles_dirt/grunge_pebbles_dirt", BM.Subtract, 0.5, tri=6.0)
        m.filt("blur", {"intensity": 0.3})
        m.filt("histogram_scan", {"Position": 0.45, "Contrast": 0.9})
        m.paint("убрать сколы, где удара не было", BM.Multiply)
        m.paint("добавить сколы")
        m.filt("sharpen", {"intensity": 0.4})
        m.paint("убрать лишнее", BM.Multiply)
    return g


def decals(st):
    g = group("decals", top(st))
    d = fill("decal", inside(g), diff="#5E5340", gloss=0.42, height=-0.02)          # ободок: тёмно-жёлтый (фото 3:16)
    m = Mask(d)
    m.fill(mask_png("decal_mask"))
    anc = m.anchor("decal mask")
    m.filt("warp", {"intensity": 0.04})                                            # неровная структура букв (0.35 рвал цифры)
    t = fill("Fill layer 2", inside(g), diff="#AFA9A1", gloss=0.36)                 # середина букв (замер кадра 7:17)
    m = Mask(t)
    m.fill(anc)
    m.filt("blur", {"intensity": 0.2})
    m.levels(0.35, 0.65)                                                             # буквы тоньше — ободок снаружи
    return g


def weathering(st):
    g = group("weathering", top(st))
    f = fill("ao dust", inside(g), diff="#161616", gloss=0.30)                    # видно (8:56)
    m = Mask(f)
    m.gen("mg_dirt/mg_dirt")
    m.fill("grunge_dust_wide/grunge_dust_wide", BM.Multiply, tri=3.0)
    m.fill(mask_png("contact_clean"), BM.Subtract)
    m.paint("убрать пыль, где её не должно быть", BM.Subtract)
    f = fill("dust", inside(g), opacity=0.5, diff="#3B3A37", gloss=0.25)
    m = Mask(f)
    m.fill("grunge_dust_small/grunge_dust_small", BM.LinearDodge, tri=5.0)
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Subtract, 0.5)
    m.gen("mg_curvature/mg_curvature", BM.Subtract, 0.6)
    m.fill(mask_png("contact_clean"), BM.Subtract)
    m.paint("вычистить выступы", visible=False)
    f = fill("glossy smudges", inside(g), opacity=0.35, gloss=0.55)
    m = Mask(f)
    m.fill("grunge_wipe_smudgy_heavy/grunge_wipe_smudgy_heavy", tri=2.5)
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Multiply)
    m.paint("замазать резкие стыки островов")
    f = fill("glossy stains", inside(g), opacity=0.35, gloss=0.62)
    m = Mask(f)
    m.fill(mask_png("ext_smear004"), tri=1.5)
    m.fill(mask_png("ext_smear007"), BM.LinearDodge, 0.5, tri=2.2, rot=0.6)
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Multiply)
    m.paint("убрать из углов")
    m.levels(0.25, 0.9)
    f = fill("rail wearing", inside(g), opacity=0.6, diff="#0F0F0F", spec="#696765", gloss=0.65)  # видно (10:20)
    m = Mask(f)
    m.fill(mask_png("rail_wear"))                                                  # у автора — фото износа кистью
    m.levels(0.0, 0.85)
    f = fill("gloss variations", inside(g), opacity=0.25, gloss=0.52)
    m = Mask(f)
    m.fill("grunge_dirt_scratchy/grunge_dirt_scratchy", tri=2.0)
    m.levels(0.2, 0.8, visible=False)
    f = fill("gloss variations 02", inside(g), opacity=0.25, gloss=0.30)
    m = Mask(f)
    m.fill("grunge_concrete/grunge_concrete", tri=1.6)
    m.filt("blur", {"intensity": 0.5})
    f = fill("rail scratches", inside(g), opacity=0.5, gloss=0.72)                 # только блеск (11:05)
    m = Mask(f)
    # у автора снизу Paint (Normal); белой зоной планок его заменять нельзя — блеск вставал на планках целиком
    # (2026-11-01): царапины сначала, планки и AO — умножением
    m.fill(mask_png("ext_scratches001"), None, 1.0, tri=1.2, name="scratches")
    m.fill(mask_png("ext_scratches003"), BM.LinearDodge, 0.9, tri=1.7, rot=1.57, name="scratches")
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Multiply)
    e, _ = m.fill("grunge_dust_wide/grunge_dust_wide", BM.Subtract, tri=3.0)
    e.set_visible(False)
    m.fill(mask_png("rail_zones"), BM.Multiply, name="Paint (только планки)")
    m.paint("добавить царапины")
    c = group("circles", inside(g))
    m = Mask(c, white=True)
    m.paint("где колец нет")
    m.gen("mg_curvature/mg_curvature", BM.Subtract, 0.3)
    f = fill("circles", inside(c), gloss=0.68)
    Mask(f).fill(mask_png("circles"))
    f = fill("High_matte", inside(g), diff="#2A1814", gloss=0.12)                 # тёмно-красный в диффузе (12:00)
    m = Mask(f)
    m.gen("mg_dirt/mg_dirt", opacity=0.35)
    m.fill("grunge_dust_wide/grunge_dust_wide", BM.Subtract, tri=3.0)
    m.paint("пятна")
    m.fill("grunge_plaster_faded/grunge_plaster_faded", BM.Subtract, tri=2.0)
    m.paint("пятна")
    m.filt("histogram_scan", {"Position": 0.2, "Contrast": 0.8})
    m.fill(mask_png("spots_matte"), BM.LinearDodge, name="Paint (альфы пятен)")
    m.paint("убрать лишнее")
    m.anchor("matte02 mask")
    f = fill("High_Gloss", inside(g), gloss=0.78)
    m = Mask(f)
    m.fill(mask_png("spots_gloss"), name="Paint (альфы пятен)")
    m.paint("пятна альфами")
    return g


def edges(st):
    g = group("edges", top(st))
    f = fill("edges", inside(g), gloss=0.66)                                       # только блеск (12:05)
    m = Mask(f)
    m.gen("mg_metal_edge_wear/mg_metal_edge_wear", params=EDGE_THIN)
    m.fill(mask_png("contact_clean"), BM.Multiply, name="Paint (где трётся)")
    m.paint("убрать, где не трётся", BM.Multiply)
    m.filt("blur", {"intensity": 0.25})
    m.fill("grunge_leaks/grunge_leaks", BM.Subtract, 0.6, tri=2.0)
    return g


def dirt(st):
    g = group("Dirt", top(st))
    # точки пыли — белый шум по текселю (≈0,15 мм) и Histogram Scan: у него Position — доля белого (0,99 заливало всё,
    # проверено выгрузкой 2026-11-01), здесь доли процента
    for nm, col, gl, seed, pos in (("dots_white", "#6E6B65", 0.22, 11, 0.0006), ("dots_orange", "#4E3C1E", 0.2, 23, 0.0004)):
        f = fill(nm, inside(g), diff=col, gloss=gl)
        m = Mask(f)
        m.fill("white_noise_fast/white_noise_fast", params={"$randomseed": seed})
        m.filt("histogram_scan", {"Position": pos, "Contrast": 0.95})
        m.fill(mask_png("contact_clean"), BM.Subtract, name="Paint (вычищено у касаний)")
        m.paint("вычистить у мест касания", BM.Subtract)
    f = fill("ao dark", inside(g), diff=f"{MASKS}/dirt_albedo.png" if os.path.exists(f"{MASKS}/dirt_albedo.png")
             else "#2A251C", gloss=0.18)                                           # засохшее масло: матовое, тёмное
    m = Mask(f)
    m.fill(mask_png("oil"), name="Paint (масло)")
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Multiply, 0.5)
    m.paint("масло кистью")
    f = fill("dots ao light", inside(g), diff="#6E6A62", gloss=0.2)
    m = Mask(f)
    m.fill("white_noise_fast/white_noise_fast", params={"$randomseed": 37})
    m.filt("histogram_scan", {"Position": 0.002, "Contrast": 0.95})
    m.gen("mg_ambient_occlusion/mg_ambient_occlusion", BM.Multiply)
    return g


def finals(st):
    ao = group("AO", top(st), visible=False)                                       # в конце у автора выключена
    f = fill("ao", inside(ao), opacity=0.4, diff="#000000")
    Mask(f).gen("mg_ambient_occlusion/mg_ambient_occlusion")
    sh = L.insert_paint(top(st))
    sh.set_name("shapen")
    sh.active_channels = {CH.Glossiness}
    for c in st.all_channels():
        sh.set_blending_mode(BM.Passthrough, c)
    fx = L.insert_filter_effect(L.InsertPosition.inside_node(sh, L.NodeStack.Content),
                                sp_lib.rid("sharpen/sharpen", "u:filter"))
    fx.get_source().set_parameters({"intensity": 0.35})                            # резкость на блеск (13:40)
    cc = L.insert_paint(top(st))
    cc.set_name("CC_GLoss")
    cc.active_channels = {CH.Glossiness}
    for c in st.all_channels():
        cc.set_blending_mode(BM.Passthrough, c)
    lv = L.insert_levels_effect(L.InsertPosition.inside_node(cc, L.NodeStack.Content))
    lv.set_name("Levels - Glossiness")
    lv.affected_channel = CH.Glossiness
    lv.set_parameters(LevelsParamsMono(input_min=0.04, input_max=0.94, gamma=1.0, output_min=0.0, output_max=1.0,
                                       clamp=False))                               # чуть контраста (13:45)
    f = fill("glossy", top(st), opacity=0.6, gloss=0.80)
    m = Mask(f)
    m.fill(mask_png("spots_gloss2") if os.path.exists(mask_png("spots_gloss2")) else mask_png("spots_gloss"))
    m.paint("глянцевые пятна альфами")
    f = fill("matte", top(st), opacity=0.6, diff="#24130F", gloss=0.10)
    m = Mask(f)
    m.fill(mask_png("spots_matte2") if os.path.exists(mask_png("spots_matte2")) else mask_png("spots_matte"))
    m.paint("матовые пятна альфами")


def build():
    st = TS.all_texture_sets()[0].get_stack()
    for n in L.get_root_layer_nodes(st):
        L.delete_node(n)
    out = []
    for fn in (base, color_variations, height_normal, decals, weathering, edges, dirt, finals):
        fn(st)
        out.append(fn.__name__)
    return " ".join(out)
