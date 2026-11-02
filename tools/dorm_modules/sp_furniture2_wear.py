"""Мебель общежития, партия 2 (кухня, умывальня, туалеты), этап 2 — износ (навык weapon-asset-wear) в Substance
Painter через мост. Работает внутри Painter (задание furniture2_sp.py wear; путь tools/dorm_modules добавляет
furniture_sp.py).

Над группой «Этап 1 — заводская отделка» (не меняется) — слой «Печать (этап 1)» и группа «Этап 2 — износ»
(Passthrough) — помощники sp_dorm_wear.py. Интервью 2026-11-02: как у мебели комнат (долго жили, потом бросили);
плита — жир и нагар, сколы эмали плиты и мойки с ржавчиной; тумбы — разбухшая ДСП у мойки, сбитые кромки,
облупленная краска, на столешницах пятна, порезы, кольца и прожоги; умывальня и туалеты — налёт и ржавые потёки,
сколы и трещины фаянса, краска кабинок и трубы облуплена слоями, грязь в чашах и у пола. Закопчённой посуды и
ржавчины на чугунных конфорках и сковороде нет. Места — карты furniture2_wear_zones.py, рисунок — фото-маски CC0
(_asset_src/dorm_clutter/wear/masks, license.txt) и процедуры полки Painter (в игру — только запечённым).
variant — код варианта отделки (furniture2_sp.py wear): у крашеных масляной краской тумб, полки и кабинок износ свой.
"""
import os

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
from sp_dorm_wear import MK, _first_tri, _layer, _new_group, _tri, _zone

DSP = ["ДСП_ламинат", "ДСП_кромка"]
PROFILES = {
    "furn_stove": dict(enamel=["Плита_эмаль"], stove=True, rust_low=["Плита_эмаль"], dust=0.3),
    "furn_sink": dict(enamel=["Мойка_эмаль"], drain=True, cabinet=True, chrome=["Хром"]),
    "furn_counter": dict(cabinet=True, top=["Пластик_столешница"], alu=["Алюминий"]),
    "furn_dining": dict(frame=["Сталь_окраска"], top=["Пластик_столешница"], burns=True, alu=["Алюминий"],
                        plastic=["Пластик_чёрный"]),
    "furn_wallcab": dict(cabinet=True, film=True, dust=0.6),
    "furn_dishrack": dict(wood=["Дерево_лак"], rails=["Ручка_металл"], film=True),
    "furn_pot": dict(dish=["Посуда_эмаль"], dust=0.3),
    "furn_kettle": dict(dish=["Посуда_эмаль"], black=["Чёрная_краска"], dust=0.3),
    "furn_pan": dict(iron=["Конфорка_чугун"], dust=0.3),
    "furn_can": dict(alu_can=["Алюминий"]),
    "furn_bucket": dict(galv=["Оцинковка"]),
    "furn_basin": dict(faience=["Фаянс"], iron_paint=["Чугун_окраска"], chrome=["Хром"], dust=0.3),
    "furn_mirror": dict(mirror=["Зеркало"], chrome=["Хром"], dust=0.2),
    "furn_toilet": dict(faience=["Фаянс"], toilet=True, iron_paint=["Чугун_окраска"], chain=["Цепочка_сталь"],
                        pipe=["Труба_краска"], seat=["Сиденье_пластик"], floor=0.55),
    "furn_stall": dict(partition=["Перегородка_краска"], frame=["Сталь_окраска"], chrome=["Хром"], floor=0.55),
}
RUST = (0.33, 0.15, 0.06)
# кабинки: прежний слой краски под нынешним (перекрашивали) — у зелёных голубой, у голубых зелёный
OLD_PAINT = {None: (0.36, 0.52, 0.60), "PT-OIL-BLU": (0.30, 0.44, 0.30)}


def _scope(layer, setname, names, exact=False):
    """Слой только на сетки этих слотов: имя сетки до «__» и «.» (exact — имя целиком, без отдельных узлов
    «__метка»)."""
    if not names:
        return
    ts = next(t for t in TS.all_texture_sets() if t.name() == setname)
    key = (lambda m: m.split(".")[0]) if exact else (lambda m: m.split(".")[0].split("__")[0])
    ms = [m for m in ts.all_mesh_names() if key(m) in names]
    if ms:
        sp_lib.only_meshes(layer, ms)


def _curv(layer, balance, contrast):
    return sp_lib.mask_generator(layer, "mg_curvature/mg_curvature", {"global_balance": balance, "global_contrast": contrast})


def _edge(layer, base, game):
    """Кромка картой «edge» (furniture2_wear_zones.py) первым слоем маски: генератор кривизны на плоских панелях
    давал полосу в ладонь шириной при любых числах."""
    return _zone(layer, base, game, "edge")


def build(setname, base, game, bbox_mm, variant=None):
    p = PROFILES[game]
    painted = bool(variant and variant.startswith("PT-OIL"))
    pos = _new_group(setname, base, game)
    made = []

    def has(zone):
        """Зона есть у набора: без её карты слой лёг бы на весь предмет (грязь у пола на навесном шкафчике)."""
        return os.path.exists(f"{base}/wear/{game}_{zone}.png")

    def nxt():
        return L.InsertPosition.above_node(made[-1]) if made else pos

    def add(layer, scope=None, exact=False):
        _scope(layer, setname, scope, exact)
        made.append(layer)
        return layer

    def chips_rust(scope, under, zone="hits", period=90, rust=True, flat=True, tube=False):
        """Сколы покрытия до основания (under: цвет, блеск, металл) по кромкам, где бьют; flat — ещё отбитое на
        плоском в тех же местах (удары посудой, обувью); в сколах — ржавчина."""
        col, rough, metal = under
        lc = add(_layer("Сколы до основания", nxt(), color=col, cop=1.0, rough=rough, rop=1.0, metal=metal), scope)
        m = _tri(_curv(lc, 0.62, 0.8) if tube else _edge(lc, base, game), f"{MK}/chips.png", period, bbox_mm, rot=0.9)
        _zone(lc, base, game, zone, above=m)
        flat = flat and has("impact")   # отбитое на плоском — только в точках ударов
        if flat:
            lf = add(_layer("Отбито на плоском", nxt(), color=col, cop=1.0, rough=rough, rop=1.0, metal=metal), scope)
            m = _first_tri(lf, f"{MK}/chips.png", period * 0.8, bbox_mm, rot=2.1)
            _zone(lf, base, game, "impact", above=m)
        if rust:
            lr = add(_layer("Ржавчина в сколах", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), scope)
            m = _tri(_curv(lr, 0.68, 0.85) if tube else _edge(lr, base, game), f"{MK}/chips.png", period, bbox_mm, rot=0.9)
            m = _tri(m, "grunge_rust_fine/grunge_rust_fine", 90, bbox_mm, rot=0.5, proc=True)
            _zone(lr, base, game, zone, above=m)
            if flat:
                lr2 = add(_layer("Ржавчина в отбитом", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), scope)
                m = _first_tri(lr2, f"{MK}/chips.png", period * 0.8, bbox_mm, rot=2.1)
                m = _tri(m, "grunge_rust_fine/grunge_rust_fine", 60, bbox_mm, rot=0.5, proc=True)
                _zone(lr2, base, game, "impact", above=m)

    # 1. грязь в углублениях — генератор Dirt: темнее и матовее. Умножением: цвет заливки Painter читает линейным,
    # 0,2 в обычном режиме — светло-бурый, и на тёмном орехе грязь выходила светлым крапом полосой по краю панелей
    l1 = add(_layer("Грязь в углублениях", nxt(), color=(0.58, 0.50, 0.42), cmode=L.BlendingMode.Multiply, cop=0.65,
                    rough=0.85, rop=0.45, metal=0.0))
    g = sp_lib.mask_generator(l1, "mg_dirt/mg_dirt", {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.45,
                                                      "Grunge_Scale": 5, "Use_Triplanar": 1})
    _tri(g, f"{MK}/grime.png", 250, bbox_mm, rot=0.4, opacity=0.6)
    # 2. пыль сверху (на верху навесного шкафчика её не вытирали никогда — гуще)
    dust = p.get("dust", 0.45)
    l2 = add(_layer("Пыль сверху", nxt(), color=(0.60, 0.57, 0.51), cop=dust, rough=0.9, rop=dust, metal=0.0))
    m = _first_tri(l2, "grunge_dust_spread/grunge_dust_spread", 600, bbox_mm, rot=0.7, proc=True)
    m = _tri(m, f"{MK}/dust_specks.png", 200, bbox_mm, rot=1.3, blend=L.BlendingMode.Lighten, opacity=0.6)
    _zone(l2, base, game, "up", above=m)
    # 3. грязь у пола — брызги и разводы снизу (у унитаза и кабинок — сильнее: мыли плохо)
    fl = p.get("floor", 0.35)
    if has("floor"):
        l3 = add(_layer("Грязь у пола", nxt(), color=(0.17, 0.13, 0.10), cop=fl, rough=0.8, rop=fl, metal=0.0))
        m = _first_tri(l3, "grunge_dirt_splats/grunge_dirt_splats", 500, bbox_mm, rot=0.2, proc=True)
        _zone(l3, base, game, "floor", above=m)

    # 4. эмаль плиты и мойки: сколы до тёмного грунта и ржавчина в них
    if p.get("enamel"):
        chips_rust(p["enamel"], ((0.07, 0.075, 0.09), 0.55, 0.0))
    if p.get("rust_low"):
        lrl = add(_layer("Ржавчина у пола", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), p["rust_low"])
        m = _first_tri(lrl, "grunge_rust_fine/grunge_rust_fine", 80, bbox_mm, rot=0.5, proc=True)
        _zone(lrl, base, game, "rust_low", above=m)

    # 5. плита: жир, пригар, нагар на конфорках, копоть в духовке, жир на стекле, хром побурел
    if p.get("stove"):
        # жир — плёнкой, мягким облаком (мазки smear_oil мелким шагом давали гранит)
        lg = add(_layer("Жир на плите", nxt(), color=(0.62, 0.48, 0.28), cmode=L.BlendingMode.Multiply, cop=0.55,
                        rough=-0.12, rmode="add", rop=0.6), ["Плита_эмаль", "Хром"], exact=True)
        m = _first_tri(lg, f"{MK}/cloudy.png", 200, bbox_mm, rot=0.9)
        _zone(lg, base, game, "grease", above=m)
        lb = add(_layer("Пригар вокруг конфорок", nxt(), color=(0.16, 0.10, 0.05), cop=0.75, rough=0.7, rop=0.8, metal=0.0),
                 ["Плита_эмаль"], exact=True)
        m = _first_tri(lb, f"{MK}/cloudy.png", 60, bbox_mm, rot=0.3)
        _zone(lb, base, game, "burnt", above=m)
        ln = add(_layer("Нагар на конфорках", nxt(), color=(0.09, 0.07, 0.05), cop=0.8, rough=0.85, rop=0.8, metal=0.0),
                 ["Конфорка_чугун"])
        m = _first_tri(ln, f"{MK}/grime.png", 60, bbox_mm, rot=1.1)
        _tri(m, f"{MK}/cloudy.png", 90, bbox_mm, rot=0.4, blend=L.BlendingMode.Lighten, opacity=0.5)
        la = add(_layer("Зола на конфорках", nxt(), color=(0.36, 0.34, 0.31), cop=0.45, rough=0.95, rop=0.5, metal=0.0),
                 ["Конфорка_чугун"])
        _first_tri(la, f"{MK}/dust_specks.png", 50, bbox_mm, rot=0.8)
        lh = add(_layer("Кольца побурели от жара", nxt(), color=(0.56, 0.42, 0.28), cmode=L.BlendingMode.Multiply, cop=0.6,
                        rough=0.15, rmode="add", rop=0.7), ["Хром"], exact=True)
        _first_tri(lh, f"{MK}/cloudy.png", 60, bbox_mm, rot=0.6)
        lo = add(_layer("Копоть и жир в духовке", nxt(), color=(0.05, 0.04, 0.03), cop=0.85, rough=0.6, rop=0.6, metal=0.0),
                 ["Духовка_эмаль"])
        m = _first_tri(lo, f"{MK}/grime.png", 60, bbox_mm, rot=0.2)
        _zone(lo, base, game, "oven", above=m)
        lgl = add(_layer("Жирная плёнка на стекле", nxt(), color=(0.58, 0.47, 0.30), cmode=L.BlendingMode.Multiply,
                         cop=0.25, rough=0.1, rmode="add", rop=0.8), ["Стекло"])
        _first_tri(lgl, f"{MK}/cloudy.png", 200, bbox_mm, rot=0.9)

    # 6. мойка: ржавчина и грязь у выпуска, хром смесителя в извести
    if p.get("drain"):
        ld = add(_layer("Ржавчина у выпуска", nxt(), color=(0.36, 0.17, 0.07), cop=0.9, rough=0.8, rop=0.9, metal=0.0),
                 p["enamel"])
        m = _first_tri(ld, "grunge_rust_fine/grunge_rust_fine", 50, bbox_mm, rot=0.3, proc=True)
        _zone(ld, base, game, "drain", above=m)
    if p.get("chrome"):
        lc = add(_layer("Хром потускнел, известь", nxt(), color=(0.86, 0.85, 0.80), cmode=L.BlendingMode.Screen, cop=0.3,
                        rough=0.25, rmode="add", rop=0.9), p["chrome"])
        _first_tri(lc, f"{MK}/dust_grain.png", 30, bbox_mm, rot=0.7)

    # 7. тумбы и шкафчик: ламинат (кромки, вытерто у ручек) или масляная краска (облупилась); разбухшая ДСП
    if p.get("cabinet"):
        if painted:
            lp = add(_layer("Краска облупилась до ДСП", nxt(), color=(0.52, 0.42, 0.30), cop=1.0, rough=0.85, rop=1.0,
                            metal=0.0), DSP)
            _tri(_edge(lp, base, game), f"{MK}/chips.png", 90, bbox_mm, rot=1.1)
            lp2 = add(_layer("Краска облупилась у ручек", nxt(), color=(0.52, 0.42, 0.30), cop=1.0, rough=0.85, rop=1.0,
                             metal=0.0), DSP)
            m = _first_tri(lp2, f"{MK}/chips.png", 60, bbox_mm, rot=0.4)
            _zone(lp2, base, game, "touch", above=m)
            ly = add(_layer("Краска пожелтела", nxt(), color=(0.92, 0.87, 0.76), cmode=L.BlendingMode.Multiply, cop=0.5),
                     DSP)
            _first_tri(ly, f"{MK}/cloudy.png", 400, bbox_mm, rot=1.2)
            if has("swell"):
                ls = add(_layer("Краска вздулась, ДСП разбухла", nxt(), color=(0.32, 0.25, 0.18), cop=0.95, rough=0.85,
                                rop=1.0, metal=0.0), DSP)
                m = _first_tri(ls, f"{MK}/chips.png", 70, bbox_mm, rot=1.7)
                _zone(ls, base, game, "swell", above=m)
        else:
            ll = add(_layer("Ламинат стёрт по кромкам", nxt(), color=(0.80, 0.70, 0.55), cmode=L.BlendingMode.Screen,
                            cop=0.18, rough=0.1, rmode="add", rop=0.8), ["ДСП_ламинат"])
            _tri(_edge(ll, base, game), f"{MK}/chips.png", 70, bbox_mm, rot=0.3)
            lk = add(_layer("Кромка сбита до ДСП", nxt(), color=(0.62, 0.52, 0.38), cop=1.0, rough=0.88, rop=1.0, metal=0.0),
                     ["ДСП_кромка"])
            _tri(_edge(lk, base, game), f"{MK}/chips.png", 90, bbox_mm, rot=1.1)
            lt = add(_layer("Ламинат затёрт у ручек", nxt(), color=(0.86, 0.84, 0.80), cmode=L.BlendingMode.Multiply,
                            cop=0.35, rough=0.2, rmode="add", rop=1.0), DSP)
            m = _first_tri(lt, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.6)
            _zone(lt, base, game, "touch", above=m)
            if has("swell"):
                ls = add(_layer("ДСП разбухла от воды", nxt(), color=(0.58, 0.48, 0.38), cmode=L.BlendingMode.Multiply,
                                cop=0.8, rough=0.35, rmode="add", rop=1.0), DSP)
                m = _first_tri(ls, f"{MK}/cloudy.png", 150, bbox_mm, rot=0.8)
                _zone(ls, base, game, "swell", above=m)
                le = add(_layer("Ламинат отстал по краю", nxt(), color=(0.64, 0.54, 0.40), cop=1.0, rough=0.88, rop=1.0,
                                metal=0.0), DSP)
                m = _tri(_edge(le, base, game), f"{MK}/grime.png", 80, bbox_mm, rot=0.5)
                _zone(le, base, game, "swell", above=m)
        lh = add(_layer("Ручки захватаны", nxt(), color=(0.78, 0.75, 0.70), cmode=L.BlendingMode.Multiply, cop=0.55,
                        rough=0.12, rmode="add", rop=0.8), ["Ручка_металл"])
        _first_tri(lh, f"{MK}/prints_b.png", 50, bbox_mm, rot=1.4)
        lg = add(_layer("Захватано у ручек", nxt(), color=(0.70, 0.64, 0.55), cmode=L.BlendingMode.Multiply, cop=0.6,
                        rough=-0.06, rmode="add", rop=0.5), DSP)
        m = _first_tri(lg, f"{MK}/prints_a.png", 80, bbox_mm, rot=0.6)
        _zone(lg, base, game, "touch", above=m)
    if p.get("film"):
        # кухонный жир оседает налётом на всём, что висит над плитой и столом
        lf = add(_layer("Кухонный жир налётом", nxt(), color=(0.86, 0.79, 0.63), cmode=L.BlendingMode.Multiply, cop=0.35,
                        rough=-0.05, rmode="add", rop=0.4))
        _first_tri(lf, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.4)

    # 8. столешницы: пятна, кольца от кастрюль, порезы ножом, затёрто руками, прожоги
    if p.get("top"):
        t = p["top"]
        lw = add(_layer("Пятна на столешнице", nxt(), color=(0.72, 0.60, 0.44), cmode=L.BlendingMode.Multiply, cop=0.75,
                        rough=0.08, rmode="add", rop=0.6), t)
        m = _first_tri(lw, f"{MK}/cloudy.png", 200, bbox_mm, rot=0.8)
        _zone(lw, base, game, "stains", above=m)
        lr = add(_layer("Кольца от кастрюль", nxt(), color=(0.52, 0.40, 0.26), cmode=L.BlendingMode.Multiply, cop=0.8,
                        rough=0.15, rmode="add", rop=0.8), t)
        _zone(lr, base, game, "rings")
        lc = add(_layer("Порезы ножом", nxt(), color=(0.86, 0.85, 0.80), cmode=L.BlendingMode.Screen, cop=0.35, rough=0.15,
                        rmode="add", rop=1.0), t)
        m = _first_tri(lc, f"{MK}/scratches.png", 120, bbox_mm, rot=0.3)
        _zone(lc, base, game, "cuts", above=m)
        lt = add(_layer("Столешница затёрта руками", nxt(), color=(0.92, 0.91, 0.88), cmode=L.BlendingMode.Multiply,
                        cop=0.5, rough=0.12, rmode="add", rop=1.0), t)
        m = _first_tri(lt, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)
    if p.get("burns"):
        lb = add(_layer("Ореол прожога", nxt(), color=(0.48, 0.32, 0.18), cmode=L.BlendingMode.Multiply, cop=0.85,
                        rough=0.15, rmode="add", rop=0.8))
        _zone(lb, base, game, "burn_ring")
        lb2 = add(_layer("Прожог", nxt(), color=(0.035, 0.028, 0.022), cop=1.0, rough=0.92, rop=1.0, metal=0.0))
        _zone(lb2, base, game, "burns")
    if p.get("alu"):
        la = add(_layer("Алюминий потускнел", nxt(), color=(0.62, 0.62, 0.60), cmode=L.BlendingMode.Multiply, cop=0.5,
                        rough=0.2, rmode="add", rop=0.9), p["alu"])
        _first_tri(la, f"{MK}/grime.png", 60, bbox_mm, rot=0.9)
    if p.get("plastic"):
        lpl = add(_layer("Пластик затёрт", nxt(), color=(0.70, 0.70, 0.70), cmode=L.BlendingMode.Screen, cop=0.2,
                         rough=0.12, rmode="add", rop=0.8), p["plastic"])
        _tri(_curv(lpl, 0.72, 0.85), f"{MK}/chips.png", 60, bbox_mm, rot=0.2)

    # 9. крашеная сталь (каркас стола, ножки кабинок): сколы до стали, ржавчина в сколах и у пола
    if p.get("frame"):
        chips_rust(p["frame"], ((0.34, 0.33, 0.31), 0.45, 1.0), period=120, flat=False, tube=True)
        lrl = add(_layer("Ржавчина у пола", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), p["frame"])
        m = _first_tri(lrl, "grunge_rust_fine/grunge_rust_fine", 80, bbox_mm, rot=0.5, proc=True)
        _zone(lrl, base, game, "rust_low", above=m)

    # 10. сушилка: вода с посуды — лак помутнел, дерево потемнело (крашеная — краска отстала), рейки в ржавых точках
    if p.get("wood"):
        w = p["wood"]
        if painted:
            lp = add(_layer("Краска отстала от воды", nxt(), color=(0.50, 0.40, 0.28), cop=1.0, rough=0.85, rop=1.0,
                            metal=0.0), w)
            m = _first_tri(lp, f"{MK}/chips.png", 60, bbox_mm, rot=0.7)
            _zone(lp, base, game, "wet", above=m)
            lp2 = add(_layer("Краска облупилась по кромкам", nxt(), color=(0.50, 0.40, 0.28), cop=1.0, rough=0.85, rop=1.0,
                             metal=0.0), w)
            _tri(_edge(lp2, base, game), f"{MK}/chips.png", 70, bbox_mm, rot=1.3)
        else:
            lw = add(_layer("Лак помутнел от воды", nxt(), color=(0.90, 0.88, 0.84), cmode=L.BlendingMode.Screen, cop=0.25,
                            rough=0.3, rmode="add", rop=1.0), w)
            m = _first_tri(lw, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.5)
            _zone(lw, base, game, "wet", above=m)
            ld = add(_layer("Дерево потемнело от воды", nxt(), color=(0.58, 0.47, 0.36), cmode=L.BlendingMode.Multiply,
                            cop=0.7), w)
            m = _first_tri(ld, f"{MK}/grime.png", 90, bbox_mm, rot=0.2)
            _zone(ld, base, game, "wet", above=m)
            lq = add(_layer("Лак вытерт по кромкам", nxt(), color=(0.78, 0.64, 0.46), cmode=L.BlendingMode.Screen, cop=0.2,
                            rough=0.15, rmode="add", rop=0.8), w)
            _tri(_edge(lq, base, game), f"{MK}/chips.png", 50, bbox_mm, rot=0.5)
    if p.get("rails"):
        lr = add(_layer("Ржавые точки на рейках", nxt(), color=RUST, cop=0.75, rough=0.85, rop=0.8, metal=0.0), p["rails"])
        m = _first_tri(lr, "grunge_rust_fine/grunge_rust_fine", 40, bbox_mm, rot=0.6, proc=True)
        _zone(lr, base, game, "wet", above=m)

    # 11. посуда, сковорода, бидон, бак: жирная плёнка, захватанные ручки, окисел алюминия, белая ржавчина цинка
    if p.get("dish"):
        lg = add(_layer("Жирная плёнка", nxt(), color=(0.86, 0.81, 0.70), cmode=L.BlendingMode.Multiply, cop=0.35,
                        rough=-0.04, rmode="add", rop=0.4), p["dish"])
        _first_tri(lg, f"{MK}/smear_oil.png", 80, bbox_mm, rot=0.3)
    if p.get("black"):
        lb = add(_layer("Краска ручки вытерта", nxt(), color=(0.30, 0.30, 0.30), cop=1.0, rough=0.4, rop=1.0, metal=1.0),
                 p["black"])
        _tri(_curv(lb, 0.86, 0.96), f"{MK}/chips.png", 30, bbox_mm, rot=0.8)
    if p.get("iron"):
        li = add(_layer("Жир на чугуне", nxt(), color=(0.72, 0.62, 0.46), cmode=L.BlendingMode.Multiply, cop=0.4,
                        rough=-0.15, rmode="add", rop=0.6), p["iron"])
        _first_tri(li, f"{MK}/smear_oil.png", 100, bbox_mm, rot=0.7)
    if p.get("alu_can"):
        lo = add(_layer("Алюминий окислился", nxt(), color=(0.82, 0.82, 0.80), cmode=L.BlendingMode.Screen, cop=0.2,
                        rough=0.25, rmode="add", rop=0.9), p["alu_can"])
        _first_tri(lo, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.4)
        lw = add(_layer("Белые точки окисла", nxt(), color=(0.88, 0.88, 0.86), cop=0.5, rough=0.9, rop=0.6, metal=0.0),
                 p["alu_can"])
        _first_tri(lw, f"{MK}/dust_specks.png", 80, bbox_mm, rot=1.1)
    if p.get("galv"):
        lz = add(_layer("Белая ржавчина цинка", nxt(), color=(0.84, 0.84, 0.81), cop=0.4, rough=0.9, rop=0.6, metal=0.0),
                 p["galv"])
        m = _first_tri(lz, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.6)
        _tri(m, f"{MK}/dust_grain.png", 60, bbox_mm, rot=0.2)
    if game in ("furn_pot", "furn_kettle", "furn_pan", "furn_stove", "furn_dishrack"):
        lt = add(_layer("Захватано руками", nxt(), color=(0.74, 0.70, 0.64), cmode=L.BlendingMode.Multiply, cop=0.7,
                        rough=-0.1, rmode="add", rop=0.7))
        m = _first_tri(lt, f"{MK}/prints_a.png", 60, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)

    # 12. фаянс: сколы до черепка, сетка трещин глазури, грязь в чаше, налёт, ржавые потёки
    if p.get("faience"):
        f = p["faience"]
        lc = add(_layer("Сколы фаянса", nxt(), color=(0.78, 0.75, 0.68), cop=1.0, rough=0.85, rop=1.0, metal=0.0), f)
        m = _tri(_edge(lc, base, game), f"{MK}/chips.png", 50, bbox_mm, rot=0.7)
        _zone(lc, base, game, "hits", above=m)
        lk = add(_layer("Трещины глазури", nxt(), color=(0.40, 0.36, 0.30), cmode=L.BlendingMode.Multiply, cop=0.75,
                        rough=0.05, rmode="add", rop=0.5), f)
        _zone(lk, base, game, "craze")
        toilet = p.get("toilet")
        lb = add(_layer("Грязь в чаше", nxt(), color=(0.32, 0.27, 0.21) if toilet else (0.48, 0.44, 0.38),
                        cmode=L.BlendingMode.Multiply, cop=0.8, rough=0.2, rmode="add", rop=0.8), f)
        m = _first_tri(lb, f"{MK}/grime.png", 80, bbox_mm, rot=0.4)
        _zone(lb, base, game, "bowl", above=m)
        # налёт: в раковине — известь (белёсый), в унитазе — мочевой камень (жёлто-бурый)
        ls = add(_layer("Налёт", nxt(), color=(0.60, 0.50, 0.30) if toilet else (0.86, 0.83, 0.74), cop=0.7,
                        rough=0.75, rop=0.9, metal=0.0), f)
        m = _first_tri(ls, f"{MK}/grime.png", 40, bbox_mm, rot=1.2)
        _zone(ls, base, game, "scale", above=m)
        lr = add(_layer("Ржавые потёки", nxt(), color=(0.62, 0.38, 0.20), cmode=L.BlendingMode.Multiply, cop=0.9,
                        rough=0.05, rmode="add", rop=0.5), f)
        m = _first_tri(lr, f"{MK}/cloudy.png", 40, bbox_mm, rot=0.3)
        _zone(lr, base, game, "streak", above=m)

    # 13. чугун под краской (кронштейны, бачок, рычаг): ржавчина пятнами и по кромкам, потёки вниз
    if p.get("iron_paint"):
        ip = p["iron_paint"]
        li = add(_layer("Краска чугуна облупилась", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), ip)
        m = _tri(_edge(li, base, game), f"{MK}/chips.png", 70, bbox_mm, rot=1.4)
        _tri(m, "grunge_rust_fine/grunge_rust_fine", 60, bbox_mm, rot=0.5, proc=True)
        # бачок ржавый, но чёрная краска читается (0,85 — весь бачок уходил в бурый)
        lsp = add(_layer("Ржавчина пятнами", nxt(), color=RUST, cop=0.45, rough=0.88, rop=0.6, metal=0.0), ip)
        m = _first_tri(lsp, f"{MK}/chips.png", 45, bbox_mm, rot=0.5)
        _tri(m, f"{MK}/cloudy.png", 200, bbox_mm, rot=0.8)
    if p.get("toilet"):
        ld = add(_layer("Ржавые потёки по чугуну и трубе", nxt(), color=(0.36, 0.17, 0.07), cop=0.75, rough=0.85, rop=0.8,
                        metal=0.0), (p.get("iron_paint") or []) + (p.get("pipe") or []))
        m = _first_tri(ld, "grunge_rust_fine/grunge_rust_fine", 40, bbox_mm, rot=0.2, proc=True)
        _zone(ld, base, game, "drip", above=m)
    if p.get("chain"):
        lch = add(_layer("Цепочка заржавела", nxt(), color=RUST, cop=0.85, rough=0.8, rop=0.9, metal=0.0), p["chain"])
        _first_tri(lch, "grunge_rust_fine/grunge_rust_fine", 20, bbox_mm, rot=0.4, proc=True)
    if p.get("pipe"):
        pp = p["pipe"]
        ly = add(_layer("Краска трубы пожелтела", nxt(), color=(0.92, 0.86, 0.70), cmode=L.BlendingMode.Multiply, cop=0.6),
                 pp)
        _first_tri(ly, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.9)
        lp = add(_layer("Краска трубы облупилась", nxt(), color=RUST, cop=1.0, rough=0.88, rop=1.0, metal=0.0), pp)
        m = _first_tri(lp, f"{MK}/chips.png", 80, bbox_mm, rot=0.6)
        _tri(m, f"{MK}/cloudy.png", 250, bbox_mm, rot=1.6)
        lt = add(_layer("Ржавый рваный конец", nxt(), color=RUST, cop=1.0, rough=0.9, rop=1.0, metal=0.0), pp)
        m = _first_tri(lt, "grunge_rust_fine/grunge_rust_fine", 30, bbox_mm, rot=0.3, proc=True)
        _zone(lt, base, game, "torn", above=m)
    if p.get("seat"):
        lse = add(_layer("Сиденье исцарапано", nxt(), color=(0.70, 0.70, 0.70), cmode=L.BlendingMode.Screen, cop=0.2,
                         rough=0.2, rmode="add", rop=1.0), p["seat"])
        _first_tri(lse, f"{MK}/scratches.png", 150, bbox_mm, rot=0.5)
    if game == "furn_toilet":
        lt = add(_layer("Захватано руками", nxt(), color=(0.70, 0.64, 0.56), cmode=L.BlendingMode.Multiply, cop=0.7,
                        rough=-0.08, rmode="add", rop=0.6))
        m = _first_tri(lt, f"{MK}/prints_a.png", 60, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)

    # 14. кабинки: краска облуплена слоями — под нынешней прежняя, в середине больших чешуек — основа; низ дверцы
    # в следах обуви, у щеколды захватано
    if p.get("partition"):
        pt = p["partition"]
        lc = add(_layer("Краска потускнела", nxt(), color=(0.88, 0.88, 0.84), cmode=L.BlendingMode.Multiply, cop=0.4,
                        rough=0.1, rmode="add", rop=1.0), pt)
        _first_tri(lc, f"{MK}/cloudy.png", 500, bbox_mm, rot=0.4)
        lo = add(_layer("Облуплено: прежний слой", nxt(), color=OLD_PAINT.get(variant, OLD_PAINT[None]), cop=1.0, rough=0.55,
                        rop=1.0, metal=0.0), pt)
        # форма чешуек — сама карта места (furniture2_wear_zones.flakes)
        _zone(lo, base, game, "peel")
        lb = add(_layer("Облуплено до основы", nxt(), color=(0.48, 0.42, 0.34), cop=1.0, rough=0.88, rop=1.0, metal=0.0),
                 pt)
        _zone(lb, base, game, "peel_deep")
        lk = add(_layer("Следы обуви", nxt(), color=(0.16, 0.13, 0.11), cmode=L.BlendingMode.Multiply, cop=0.55,
                        rough=0.1, rmode="add", rop=0.5), pt)
        m = _first_tri(lk, "grunge_dirt_splats/grunge_dirt_splats", 180, bbox_mm, rot=1.7, proc=True)
        _zone(lk, base, game, "kick", above=m)
        lt = add(_layer("Захватано у щеколды", nxt(), color=(0.62, 0.58, 0.50), cmode=L.BlendingMode.Multiply, cop=0.7,
                        rough=-0.08, rmode="add", rop=0.6), pt)
        m = _first_tri(lt, f"{MK}/prints_a.png", 80, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)

    # 15. зеркало: амальгама облезла по краям, брызги внизу
    if p.get("mirror"):
        # амальгамы нет — сквозь стекло тёмная изнанка, блеск стекла остаётся (рисунок поверх гасил её наполовину и
        # пятна выходили светлее зеркала)
        lm = add(_layer("Амальгама облезла", nxt(), color=(0.025, 0.023, 0.02), cop=1.0, rough=0.06, rop=1.0, metal=0.0),
                 p["mirror"])
        _zone(lm, base, game, "desilver")
        ls = add(_layer("Брызги на зеркале", nxt(), color=(0.82, 0.82, 0.80), cop=0.5, rough=0.6, rop=0.8, metal=0.2),
                 p["mirror"])
        _zone(ls, base, game, "spots")
    return f"{game}: {len(made)} слоёв износа{' (' + variant + ')' if variant else ''}"
