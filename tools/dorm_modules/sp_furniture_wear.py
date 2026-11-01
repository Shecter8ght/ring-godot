"""Мебель общежития, этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост.
Работает внутри Painter (задание furniture_sp.py wear; путь tools/dorm_modules добавляет он же).

Над группой «Этап 1 — заводская отделка» (не меняется) — слой «Печать (этап 1)» и группа «Этап 2 — износ»
(Passthrough) — помощники sp_dorm_wear.py. Интервью 2026-10-31: как в Таркове — долго жили, потом бросили (сколы,
затёртости, пыль сверху, грязь у пола, пятна — заметно, но не в труху); сколы эмали и ржавчина на кроватях; пятна на
матрасе и диване; прожоги сигаретами и кольца от кружек; выцветание заметное (ковёр, рогожка; лак и полировка
затёрты до мата в местах касания); крови нет. Места — карты furniture_wear_zones.py, рисунок — фото-маски CC0
ambientCG / ShareTextures (_asset_src/dorm_clutter/wear/masks, license.txt) и процедуры полки Painter (в игру — только
запечённым). Узоры — под мебельный масштаб (плитка в сотни миллиметров). Каждый слой меняет и цвет, и блеск.
"""
import substance_painter.layerstack as L

import sp_lib
from sp_dorm_wear import MK, _first_tri, _layer, _new_group, _scope, _tri, _zone

# предмет: детали по виду отделки и особые следы
ENAMEL, ROD = ["Кровать_эмаль"], ["Сетка_проволока"]
DSP = ["ДСП_ламинат", "ДСП_кромка"]
PROFILES = {
    "furn_bunk_bed": dict(enamel=ENAMEL, rust=ENAMEL, wire=ROD, plastic=["Заглушка_пластик"], touch="enamel"),
    "furn_bed": dict(enamel=ENAMEL, rust=ENAMEL, wire=ROD, plastic=["Заглушка_пластик"], touch="enamel"),
    "furn_mattress": dict(fabric=["Матрас_тик", "Матрас_кант"], fade=0.14, stains=True, greasy=True, burns=True),
    "furn_nightstand": dict(polish=DSP, kromka=["ДСП_кромка"], touch="polish", burns=True, rings=True, scratches=DSP,
                            handles=["Ручка_металл"]),
    "furn_wardrobe": dict(polish=DSP, kromka=["ДСП_кромка"], touch="polish", scratches=DSP, handles=["Ручка_металл"]),
    "furn_table": dict(laminate=DSP, kromka=["ДСП_кромка"], lacquer=["Дерево_лак"], touch="laminate", burns=True,
                       rings=True, rings_water=True, scratches=["ДСП_ламинат"], handles=["Ручка_металл"]),
    "furn_chair": dict(enamel=["Стул_каркас_эмаль"], rust=["Стул_каркас_эмаль"], lacquer=["Фанера_лак"], touch="lacquer",
                       scuff=True, plastic=["Резина"]),
    "furn_stool": dict(lacquer=["Дерево_лак"], touch="lacquer", scuff=True),
    "furn_shelf": dict(laminate=DSP, kromka=["ДСП_кромка"], glass=["Стекло"], handles=["Ручка_металл"]),
    "furn_fridge": dict(appliance=["Холодильник_эмаль"], rust=["Холодильник_эмаль", "Чёрная_краска"],
                        yellowed=["Холодильник_эмаль"], gasket=["Уплотнитель"], touch="grime", handles=["Хром"]),
    "furn_sofa": dict(fabric=["Диван_ткань"], fade=0.16, stains=True, greasy=True, touch="fabric", lacquer=["Диван_дерево"]),
    "furn_carpet": dict(fabric=["Ковёр_шерсть"], fade=0.10, rust=["Гвоздь_сталь"]),
    "furn_tv": dict(polish=["Телевизор_корпус"], glass=["Кинескоп"], plastic=["Телевизор_панель", "Телевизор_задняя_крышка"],
                    touch="grime", handles=["Хром"]),
    "furn_hotplate": dict(appliance=["Плитка_корпус"], chips=False, heat=True, grease=True, touch="grime"),
}


def build(setname, base, game, bbox_mm):
    p = PROFILES[game]
    pos = _new_group(setname, base, game)
    made = []

    def nxt():
        return L.InsertPosition.above_node(made[-1]) if made else pos

    def add(layer, scope=None):
        if scope:
            _scope(layer, setname, scope)
        made.append(layer)
        return layer

    fabric = p.get("fabric") or []
    # 1. грязь в углублениях — генератор Dirt: темнее и матовее
    l1 = add(_layer("Грязь в углублениях", nxt(), color=(0.20, 0.16, 0.12), cop=0.55, rough=0.85, rop=0.45, metal=0.0))
    g = sp_lib.mask_generator(l1, "mg_dirt/mg_dirt", {"dirt_level": 0.4, "dirt_contrast": 0.6, "grunge_amount": 0.45,
                                                      "Grunge_Scale": 5, "Use_Triplanar": 1})
    _tri(g, f"{MK}/grime.png", 250, bbox_mm, rot=0.4, opacity=0.6)
    # 2. пыль сверху — светлая, матовая, гуще в неровностях; металл под пылью не блестит
    # на мебели пыль слабее, чем на мусоре: при 0,75 столешница уходила в сплошной серый налёт (проба 2026-11-01)
    dust = 0.2 if fabric and not p.get("enamel") else 0.45
    l2 = add(_layer("Пыль сверху", nxt(), color=(0.60, 0.57, 0.51), cop=dust, rough=0.9, rop=dust, metal=0.0))
    m = _first_tri(l2, "grunge_dust_spread/grunge_dust_spread", 600, bbox_mm, rot=0.7, proc=True)
    m = _tri(m, f"{MK}/dust_specks.png", 200, bbox_mm, rot=1.3, blend=L.BlendingMode.Lighten, opacity=0.6)
    _zone(l2, base, game, "up", above=m)
    # 3. грязь у пола — брызги и разводы снизу (ножки, цоколь, низ рамы)
    l3 = add(_layer("Грязь у пола", nxt(), color=(0.17, 0.13, 0.10), cop=0.35, rough=0.8, rop=0.35, metal=0.0))
    m = _first_tri(l3, "grunge_dirt_splats/grunge_dirt_splats", 500, bbox_mm, rot=0.2, proc=True)
    _zone(l3, base, game, "floor", above=m)

    # 4. кромки и сколы — по виду отделки
    if p.get("enamel"):
        # эмаль сбита до стали там, где бьют и хватают (низ стоек, верх спинок, удары); в сколах — ржавчина
        lc = add(_layer("Сколы эмали до стали", nxt(), color=(0.34, 0.33, 0.31), cop=1.0, rough=0.45, rop=1.0, metal=1.0),
                 p["enamel"])
        g = sp_lib.mask_generator(lc, "mg_curvature/mg_curvature", {"global_balance": 0.62, "global_contrast": 0.8})
        m = _tri(g, f"{MK}/chips.png", 120, bbox_mm, rot=0.9)
        _zone(lc, base, game, "hits", above=m)
        lr = add(_layer("Ржавчина в сколах", nxt(), color=(0.33, 0.15, 0.06), cop=1.0, rough=0.88, rop=1.0, metal=0.0),
                 p["enamel"])
        g = sp_lib.mask_generator(lr, "mg_curvature/mg_curvature", {"global_balance": 0.68, "global_contrast": 0.85})
        m = _tri(g, f"{MK}/chips.png", 120, bbox_mm, rot=0.9)
        m = _tri(m, "grunge_rust_fine/grunge_rust_fine", 90, bbox_mm, rot=0.5, proc=True)
        _zone(lr, base, game, "hits", above=m)
    if p.get("appliance") and p.get("chips", True):
        # эмаль техники — мелкие сколы до чёрного грунта по кромкам
        la = add(_layer("Сколы эмали до грунта", nxt(), color=(0.06, 0.06, 0.06), cop=0.9, rough=0.5, rop=0.9, metal=0.0),
                 p["appliance"])
        g = sp_lib.mask_generator(la, "mg_curvature/mg_curvature", {"global_balance": 0.88, "global_contrast": 0.97})
        _tri(g, f"{MK}/chips.png", 35, bbox_mm, rot=0.4)
    if p.get("polish"):
        # полировка вытерта по кромкам до светлого шпона, кромки матовые
        lp = add(_layer("Полировка вытерта по кромкам", nxt(), color=(0.62, 0.46, 0.30), cmode=L.BlendingMode.Screen,
                        cop=0.18, rough=0.15, rmode="add", rop=0.8), p["polish"])
        g = sp_lib.mask_generator(lp, "mg_curvature/mg_curvature", {"global_balance": 0.84, "global_contrast": 0.96})
        _tri(g, f"{MK}/chips.png", 50, bbox_mm, rot=0.7)
    if p.get("laminate"):
        # ламинат по кромкам стёрт до печати светлее
        ll = add(_layer("Ламинат стёрт по кромкам", nxt(), color=(0.80, 0.70, 0.55), cmode=L.BlendingMode.Screen,
                        cop=0.18, rough=0.1, rmode="add", rop=0.8), p["laminate"])
        g = sp_lib.mask_generator(ll, "mg_curvature/mg_curvature", {"global_balance": 0.84, "global_contrast": 0.96})
        _tri(g, f"{MK}/chips.png", 50, bbox_mm, rot=0.3)
    if p.get("kromka"):
        # кромка сбита у углов — видна ДСП: светлая, матовая крошка
        lk = add(_layer("Кромка сбита до ДСП", nxt(), color=(0.62, 0.52, 0.38), cop=1.0, rough=0.88, rop=1.0, metal=0.0),
                 p["kromka"])
        g = sp_lib.mask_generator(lk, "mg_curvature/mg_curvature", {"global_balance": 0.8, "global_contrast": 0.9})
        _tri(g, f"{MK}/chips.png", 90, bbox_mm, rot=1.1)
    if p.get("lacquer"):
        # лак вытерт по кромкам до светлого дерева
        lq = add(_layer("Лак вытерт по кромкам", nxt(), color=(0.78, 0.64, 0.46), cmode=L.BlendingMode.Screen, cop=0.2,
                        rough=0.15, rmode="add", rop=0.8), p["lacquer"])
        g = sp_lib.mask_generator(lq, "mg_curvature/mg_curvature", {"global_balance": 0.82, "global_contrast": 0.95})
        _tri(g, f"{MK}/chips.png", 50, bbox_mm, rot=0.5)

    # 5. где трогают и сидят
    t = p.get("touch")
    if t in ("polish", "laminate", "lacquer"):
        scope = p.get(t) or None
        lt = add(_layer("Затёрто до мата руками", nxt(), color=(0.86, 0.84, 0.80), cmode=L.BlendingMode.Multiply, cop=0.35,
                        rough=0.28 if t == "polish" else 0.18, rmode="add", rop=1.0), scope)
        m = _first_tri(lt, f"{MK}/cloudy.png", 300, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)
    elif t == "enamel":
        lt = add(_layer("Эмаль заглажена руками", nxt(), color=(0.82, 0.80, 0.78), cmode=L.BlendingMode.Multiply, cop=0.5,
                        rough=-0.12, rmode="add", rop=0.9), p["enamel"])
        m = _first_tri(lt, f"{MK}/prints_a.png", 120, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)
    elif t == "fabric":
        lt = add(_layer("Обивка вытерта, где сидят", nxt(), color=(0.30, 0.27, 0.24), cmode=L.BlendingMode.Screen, cop=0.35,
                        rough=-0.06, rmode="add", rop=0.7), fabric)
        m = _first_tri(lt, f"{MK}/cloudy.png", 350, bbox_mm, rot=0.9)
        _zone(lt, base, game, "touch", above=m)
    elif t == "grime":
        lt = add(_layer("Захватано руками", nxt(), color=(0.74, 0.71, 0.66), cmode=L.BlendingMode.Multiply, cop=0.7,
                        rough=-0.1, rmode="add", rop=0.7))
        m = _first_tri(lt, f"{MK}/prints_a.png", 60, bbox_mm, rot=0.6)
        _zone(lt, base, game, "touch", above=m)
    if p.get("handles"):
        lh = add(_layer("Ручки захватаны", nxt(), color=(0.80, 0.78, 0.74), cmode=L.BlendingMode.Multiply, cop=0.5,
                        rough=0.12, rmode="add", rop=0.8), p["handles"])
        _first_tri(lh, f"{MK}/prints_b.png", 50, bbox_mm, rot=1.4)
    # 6. царапины по верху — светлее и матовее
    if p.get("scratches"):
        ls = add(_layer("Царапины", nxt(), color=(0.80, 0.78, 0.74), cmode=L.BlendingMode.Screen, cop=0.28, rough=0.1,
                        rmode="add", rop=1.0), p["scratches"])
        m = _first_tri(ls, f"{MK}/scratches.png", 350, bbox_mm, rot=0.3)
        _zone(ls, base, game, "up", above=m)
    # 7. ткань выгорела пятнами
    if p.get("fade"):
        # краски гаснут (насыщенность серым) и чуть светлеют нейтральным тоном; Screen светлым цветом тянул тёмную
        # рогожку к бежевому (медиана 62/42/28 → 92/76/60, проба 2026-11-01)
        lf = add(_layer("Выгорело: краски", nxt(), color=(0.5, 0.5, 0.5), cmode=L.BlendingMode.Saturation,
                        cop=min(p["fade"] * 1.2, 0.3), rough=0.04, rmode="add", rop=0.5), fabric)
        _first_tri(lf, f"{MK}/cloudy.png", 600, bbox_mm, rot=0.2)
        lf2 = add(_layer("Выгорело: светлее", nxt(), color=(0.22, 0.21, 0.19), cmode=L.BlendingMode.Screen, cop=p["fade"] * 0.5),
                  fabric)
        _first_tri(lf2, f"{MK}/cloudy.png", 600, bbox_mm, rot=0.2)
    # 8. пятна с ободком, засаленность
    if p.get("stains"):
        lw = add(_layer("Пятна с ободком", nxt(), color=(0.80, 0.66, 0.42), cmode=L.BlendingMode.Multiply, cop=0.85,
                        rough=0.05, rmode="add", rop=0.6), fabric)
        m = _first_tri(lw, f"{MK}/cloudy.png", 250, bbox_mm, rot=0.8)
        _zone(lw, base, game, "stains", above=m)
    if p.get("greasy"):
        lg = add(_layer("Засалено", nxt(), color=(0.70, 0.66, 0.60), cmode=L.BlendingMode.Multiply, cop=0.75, rough=-0.15,
                        rmode="add", rop=0.7), fabric)
        m = _first_tri(lg, f"{MK}/smear_oil.png", 300, bbox_mm, rot=0.2)
        _zone(lg, base, game, "greasy", above=m)
    # 9. прожоги сигаретами и кольца от кружек
    if p.get("burns"):
        lb = add(_layer("Ореол прожога", nxt(), color=(0.48, 0.32, 0.18), cmode=L.BlendingMode.Multiply, cop=0.85,
                        rough=0.15, rmode="add", rop=0.8))
        _zone(lb, base, game, "burn_ring")
        lb2 = add(_layer("Прожог", nxt(), color=(0.035, 0.028, 0.022), cop=1.0, rough=0.92, rop=1.0, metal=0.0))
        _zone(lb2, base, game, "burns")
    if p.get("rings"):
        lr2 = add(_layer("Кольца от кружек", nxt(), color=(0.55, 0.40, 0.25), cmode=L.BlendingMode.Multiply, cop=0.8,
                         rough=0.1, rmode="add", rop=0.8))
        _zone(lr2, base, game, "rings")
    if p.get("rings_water"):
        lr3 = add(_layer("Кольцо от воды", nxt(), color=(0.92, 0.90, 0.86), cmode=L.BlendingMode.Screen, cop=0.35,
                         rough=0.15, rmode="add", rop=0.9))
        _zone(lr3, base, game, "rings_water")
    # 10. техника: пожелтевшая эмаль, жар и пригар, грязный уплотнитель
    if p.get("yellowed"):
        ly = add(_layer("Эмаль пожелтела", nxt(), color=(0.96, 0.91, 0.78), cmode=L.BlendingMode.Multiply, cop=0.7),
                 p["yellowed"])
        _first_tri(ly, f"{MK}/cloudy.png", 500, bbox_mm, rot=1.2)
    if p.get("heat"):
        lh2 = add(_layer("Побурела от жара", nxt(), color=(0.74, 0.56, 0.34), cmode=L.BlendingMode.Multiply, cop=0.8,
                         rough=0.1, rmode="add", rop=0.6), p.get("appliance"))
        m = _first_tri(lh2, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.3)
        _zone(lh2, base, game, "heat", above=m)
    if p.get("grease"):
        lgr = add(_layer("Жир и пригар", nxt(), color=(0.60, 0.46, 0.30), cmode=L.BlendingMode.Multiply, cop=0.7,
                         rough=-0.08, rmode="add", rop=0.6), p.get("appliance"))
        m = _first_tri(lgr, f"{MK}/smear_oil.png", 120, bbox_mm, rot=0.9)
        _zone(lgr, base, game, "up", above=m)
    if p.get("gasket"):
        lu = add(_layer("Уплотнитель грязный", nxt(), color=(0.45, 0.44, 0.40), cmode=L.BlendingMode.Multiply, cop=0.85,
                        rough=0.05, rmode="add", rop=0.5), p["gasket"])
        _first_tri(lu, f"{MK}/grime.png", 80, bbox_mm, rot=0.5)
    # 11. стекло и экран в пыли, проножки в следах обуви
    if p.get("glass"):
        lgl = add(_layer("Пыль на стекле", nxt(), color=(0.62, 0.60, 0.56), cop=0.22, rough=0.55, rop=0.6), p["glass"])
        _first_tri(lgl, f"{MK}/dust_grain.png", 150, bbox_mm, rot=0.8)
    if p.get("scuff"):
        lsc = add(_layer("Следы обуви", nxt(), color=(0.16, 0.13, 0.11), cmode=L.BlendingMode.Multiply, cop=0.45,
                         rough=0.1, rmode="add", rop=0.5))
        m = _first_tri(lsc, "grunge_dirt_splats/grunge_dirt_splats", 180, bbox_mm, rot=1.7, proc=True)
        _zone(lsc, base, game, "scuff", above=m)
    # 12. ржавчина: у пола (ножки, низ корпуса), гвозди, сетка
    if p.get("rust"):
        # где есть зона rust_low — только у пола; у гвоздей ковра — пятнами по всей шляпке
        lrl = add(_layer("Ржавчина", nxt(), color=(0.32, 0.15, 0.06), cop=1.0, rough=0.88, rop=1.0, metal=0.0), p["rust"])
        m = _first_tri(lrl, "grunge_rust_fine/grunge_rust_fine", 80, bbox_mm, rot=0.5, proc=True)
        _zone(lrl, base, game, "rust_low", above=m)
    if p.get("wire"):
        lwi = add(_layer("Сетка потускнела, ржавые точки", nxt(), color=(0.30, 0.16, 0.07), cop=0.75, rough=0.85, rop=0.8,
                         metal=0.0), p["wire"])
        _first_tri(lwi, "grunge_rust_fine/grunge_rust_fine", 220, bbox_mm, rot=0.7, proc=True)
    if p.get("plastic"):
        lpl = add(_layer("Пластик затёрт", nxt(), color=(0.70, 0.70, 0.70), cmode=L.BlendingMode.Screen, cop=0.2,
                         rough=0.12, rmode="add", rop=0.8), p["plastic"])
        g = sp_lib.mask_generator(lpl, "mg_curvature/mg_curvature", {"global_balance": 0.72, "global_contrast": 0.85})
        _tri(g, f"{MK}/chips.png", 60, bbox_mm, rot=0.2)
    return f"{game}: {len(made)} слоёв износа"
