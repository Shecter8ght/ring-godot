"""Вещи общежития, партия 3, этап 2 — износ (навык weapon-asset-wear) в Substance Painter через мост. Работает внутри
Painter (задание items3_sp.py wear; путь tools/dorm_modules добавляет furniture_sp.py).

Над группой «Этап 1 — заводская отделка» (принята 2026-11-02, не меняется) — слой «Печать (этап 1)» (у варианта
картинки — его печать, print_key) и группа «Этап 2 — износ» (Passthrough) — помощники sp_dorm_wear.py. Интервью
2026-11-02: степень «слабее» — брошено недавно (пыль, отпечатки, мелкие следы), всё выбранное — слабо. Ящики и вещи
жильцов: сбитые углы и кромки, ржавчина на металле, пыль и грязь, коробка отсырела; бумага на стенах: выцвела и
пожелтела, пятна сырости, пыль и мухи, карандаш и ручка; техника и учебное: пыль и отпечатки, затёртое от рук,
учебники потрёпаны, пятна и пометки. Места — карты items3_wear_zones.py, рисунок — фото-маски CC0
(_asset_src/dorm_clutter/wear/masks, license.txt) и процедуры полки Painter (в игру — только запечённым).
variant — код варианта отделки: у ящиков из голой сосны вместо сбитой краски — потемневшие кромки.
"""
import os

import substance_painter.layerstack as L
import substance_painter.textureset as TS

import sp_lib
from sp_dorm_wear import GROUP, MK, PRINT, _first_tri, _layer, _print_layer, _tri, _zone

RUST = (0.33, 0.15, 0.06)
DUST = (0.60, 0.57, 0.51)
# чернила шариковой ручки: линейный цвет (Painter), матовые как бумага — с глянцем тонкие штрихи читались тиснением
INK = (0.03, 0.05, 0.26)
PAPER = ("it_poster", "it_poster_torn", "it_poster_curl", "it_poster_s", "it_poster_s_curl", "it_clip", "it_calendar",
         "it_chart", "it_drawing", "it_drawing_roll")
BOOKS = ("it_book", "it_book_stack", "it_book_row", "it_notebook", "it_notebook_stack", "it_notebook48")
OPEN = ("it_book_open", "it_notebook_open")
# пыль: техника стоит дольше всего на виду — слоем; остальное слабо
# (проба 2026-11-02: 0,25–0,5 с крупным рисунком — ящик мраморный, клавиатура каменная)
DUST_K = {"it_pc": 0.3, "it_monitor": 0.25, "it_keyboard": 0.15, "it_laptop": 0.15, "it_mouse": 0.1, "it_trunk": 0.2}


def _scope(layer, setname, names, exact=False):
    """Слой только на сетки этих слотов (имя сетки до «__» и «.»; exact — целиком)."""
    if not names:
        return
    ts = next(t for t in TS.all_texture_sets() if t.name() == setname)
    key = (lambda m: m.split(".")[0]) if exact else (lambda m: m.split(".")[0].split("__")[0])
    ms = [m for m in ts.all_mesh_names() if key(m) in names]
    if ms:
        sp_lib.only_meshes(layer, ms)
    else:
        # слотов нет в наборе (цинки у ящика ЗИП): без ограничения слой лёг бы на всё — налёт мрамором по краске
        layer.set_visible(False)


def _group(setname, base, game, print_key):
    """Отделка — как была; прежние печать и износ удаляются; печать (своего варианта картинки) и новая группа —
    над ней."""
    st = sp_lib.stack_by_name(setname)
    for n in L.get_root_layer_nodes(st):
        if n.get_name() in (GROUP, PRINT):
            L.delete_node(n)
    pos = _print_layer(setname, base, print_key or game, L.InsertPosition.from_textureset_stack(st))
    grp = L.insert_group(pos)
    grp.set_name(GROUP)
    for ch in st.all_channels():
        grp.set_blending_mode(L.BlendingMode.Passthrough, ch)
    return L.InsertPosition.inside_node(grp, L.NodeStack.Substack)


def build(setname, base, game, bbox_mm, variant=None, print_key=None):
    raw = variant == "WD-PIN-RAW"
    pos = _group(setname, base, game, print_key)
    made = []

    def has(zone):
        return os.path.exists(f"{base}/wear/{game}_{zone}.png")

    def nxt():
        return L.InsertPosition.above_node(made[-1]) if made else pos

    def add(layer, scope=None, exact=False):
        _scope(layer, setname, scope, exact)
        made.append(layer)
        return layer

    def zoned(name, zone, mask, period, rot, scope=None, proc=False, **kw):
        """Слой по месту zone с рисунком mask (фото-маска или процедура)."""
        if not has(zone):
            return None
        lay = add(_layer(name, nxt(), **kw), scope)
        m = _first_tri(lay, mask if proc else f"{MK}/{mask}", period, bbox_mm, rot=rot, proc=proc)
        _zone(lay, base, game, zone, above=m)
        return lay

    def plain_zone(name, zone, scope=None, **kw):
        """Слой самой картой места (штрихи ручки, кольца) без рисунка."""
        if not has(zone):
            return None
        lay = add(_layer(name, nxt(), **kw), scope)
        _zone(lay, base, game, zone)
        return lay

    # 1. грязь в углублениях — слабая (брошено недавно), только в самих углублениях: крупный рисунок поверх давал
    # мраморные пятна по всей краске ящика; на бумаге её нет. Умножением: цвет заливки Painter читает линейным
    if game not in PAPER:
        l1 = add(_layer("Грязь в углублениях", nxt(), color=(0.66, 0.60, 0.52), cmode=L.BlendingMode.Multiply, cop=0.25,
                        rough=0.85, rop=0.2, metal=0.0))
        g = sp_lib.mask_generator(l1, "mg_dirt/mg_dirt", {"dirt_level": 0.2, "dirt_contrast": 0.7, "grunge_amount": 0.2,
                                                          "Grunge_Scale": 5, "Use_Triplanar": 1})
        _tri(g, f"{MK}/grime.png", 120, bbox_mm, rot=0.4, opacity=0.3)
    # 2. пыль сверху — тонким ровным слоем с мелким зерном
    dust = DUST_K.get(game, 0.15)
    l2 = add(_layer("Пыль сверху", nxt(), color=DUST, cop=dust, rough=0.9, rop=dust, metal=0.0))
    m = _first_tri(l2, "grunge_dust_spread/grunge_dust_spread", 900, bbox_mm, rot=0.7, proc=True)
    m = _tri(m, f"{MK}/dust_grain.png", 80, bbox_mm, rot=1.3, blend=L.BlendingMode.Lighten, opacity=0.5)
    _zone(l2, base, game, "up", above=m)
    # 3. грязь у пола
    zoned("Грязь у пола", "floor", "grunge_dirt_splats/grunge_dirt_splats", 500, 0.2, proc=True,
          color=(0.20, 0.16, 0.12), cop=0.25, rough=0.8, rop=0.25, metal=0.0)

    # 4. военные ящики: сбитая краска на углах и у низа (у голой сосны — кромки потемнели), следы сапог, ржавчина
    # фурнитуры, засаленные верёвки, белёсый налёт на цинках
    if game in ("it_ammo", "it_zip"):
        if raw:
            zoned("Кромки потемнели, захватаны", "hits", "grime.png", 80, 0.5, ["Дерево_окраска", "Дерево_торец"],
                  color=(0.62, 0.55, 0.45), cmode=L.BlendingMode.Multiply, cop=0.7, rough=-0.05, rmode="add", rop=0.5)
        else:
            zoned("Краска сбита до дерева", "hits", "chips.png", 80, 0.9, ["Дерево_окраска"],
                  color=(0.70, 0.57, 0.40), cop=1.0, rough=0.85, rop=1.0, metal=0.0)
            zoned("Краска стёрта с фурнитуры", "corner", "chips.png", 50, 1.3, ["Фурнитура_сталь"],
                  color=(0.34, 0.33, 0.31), cop=1.0, rough=0.45, rop=1.0, metal=1.0)
        zoned("Следы сапог", "kick", "grunge_dirt_splats/grunge_dirt_splats", 180, 1.7, proc=True,
              color=(0.30, 0.26, 0.22), cmode=L.BlendingMode.Multiply, cop=0.45, rough=0.1, rmode="add", rop=0.4)
        zoned("Ржавчина на фурнитуре", "rust", "grunge_rust_fine/grunge_rust_fine", 40, 0.6, ["Фурнитура_сталь"], proc=True,
              color=RUST, cop=0.4, rough=0.85, rop=0.5, metal=0.0)
        lrope = add(_layer("Верёвка засалена", nxt(), color=(0.70, 0.63, 0.52), cmode=L.BlendingMode.Multiply, cop=0.5,
                           rough=-0.05, rmode="add", rop=0.4), ["Верёвка"])
        _first_tri(lrope, f"{MK}/grime.png", 40, bbox_mm, rot=0.8)
        ltin = add(_layer("Налёт на цинках", nxt(), color=(0.84, 0.84, 0.81), cop=0.25, rough=0.9, rop=0.4, metal=0.0),
                   ["Цинк_банка"])
        m = _first_tri(ltin, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.6)
        _tri(m, f"{MK}/dust_grain.png", 60, bbox_mm, rot=0.2)

    # 5. сундук и ящик для инструментов: сколы эмали до стали, ржавчина в сколах — слабо; у ящика захватана ручка
    if game in ("it_trunk", "it_toolbox"):
        paint = ["Сталь_окраска"] if game == "it_trunk" else ["Ящик_краска"]
        zoned("Сколы до стали", "hits", "chips.png", 70, 0.9, paint,
              color=(0.34, 0.33, 0.31), cop=1.0, rough=0.45, rop=1.0, metal=1.0)
        zoned("Ржавчина в сколах", "hits", "grunge_rust_fine/grunge_rust_fine", 50, 0.5, paint, proc=True,
              color=RUST, cop=0.45, rough=0.88, rop=0.6, metal=0.0)
        zoned("Фурнитура потускнела, точки ржавчины", "rust", "grunge_rust_fine/grunge_rust_fine", 40, 0.6,
              ["Фурнитура_сталь"], proc=True, color=RUST, cop=0.35, rough=0.75, rop=0.5, metal=0.0)
        zoned("Следы сапог", "kick", "grunge_dirt_splats/grunge_dirt_splats", 180, 1.7, proc=True,
              color=(0.30, 0.26, 0.22), cmode=L.BlendingMode.Multiply, cop=0.4, rough=0.1, rmode="add", rop=0.4)
        zoned("Захватано у ручки", "touch", "prints_a.png", 60, 0.6, color=(0.70, 0.64, 0.56),
              cmode=L.BlendingMode.Multiply, cop=0.5, rough=-0.08, rmode="add", rop=0.5)

    # 6. чемодан: потёртости корпуса на углах (пластик светлеет царапинами), грязь на колёсах, захватана ручка
    if game == "it_suitcase":
        zoned("Потёртости корпуса", "corner", "scratches.png", 120, 0.4, ["Пластик_корпус"],
              color=(0.62, 0.62, 0.62), cmode=L.BlendingMode.Screen, cop=0.3, rough=0.15, rmode="add", rop=0.8)
        zoned("Грязь на колёсах", "wheels", "grime.png", 40, 0.3, ["Резина"],
              color=(0.32, 0.27, 0.21), cop=0.55, rough=0.85, rop=0.6, metal=0.0)
        zoned("Ручка захватана", "touch", "prints_b.png", 50, 1.4, color=(0.75, 0.72, 0.68),
              cmode=L.BlendingMode.Multiply, cop=0.5, rough=-0.1, rmode="add", rop=0.6)

    # 7. сумка: низ в грязи, ткань затёрта, ручки засалены
    if game == "it_duffel":
        zoned("Ткань затёрта", "scuff", "cloudy.png", 120, 0.6, ["Ткань_сумка"],
              color=(0.55, 0.55, 0.55), cmode=L.BlendingMode.Screen, cop=0.15, rough=0.06, rmode="add", rop=0.6)
        zoned("Ручки засалены", "touch", "grime.png", 50, 0.9, ["Стропа"],
              color=(0.80, 0.76, 0.70), cmode=L.BlendingMode.Multiply, cop=0.4, rough=-0.12, rmode="add", rop=0.6)

    # 8. коробка: отсырел низ (темнее, с ободком высохшей воды), потёки, смятые углы, грязные края скотча
    if game == "it_carton":
        zoned("Отсырела снизу", "wet", "cloudy.png", 150, 0.8, ["Картон", "Картон_срез"],
              color=(0.62, 0.50, 0.38), cmode=L.BlendingMode.Multiply, cop=0.75, rough=0.05, rmode="add", rop=0.5)
        zoned("Потёки", "drips", "cloudy.png", 60, 0.3, ["Картон"],
              color=(0.70, 0.58, 0.44), cmode=L.BlendingMode.Multiply, cop=0.55)
        zoned("Углы смяты и затёрты", "corner", "grime.png", 60, 0.5, ["Картон", "Картон_срез"],
              color=(0.66, 0.56, 0.44), cmode=L.BlendingMode.Multiply, cop=0.6, rough=0.04, rmode="add", rop=0.5)
        zoned("Край скотча грязный", "tape_edge", "grime.png", 30, 0.9, ["Скотч"],
              color=(0.45, 0.36, 0.26), cmode=L.BlendingMode.Multiply, cop=0.7, rough=0.3, rmode="add", rop=0.8)

    # 9. бумага: пожелтела и выцвела, пятна сырости, ржавчина у кнопок, пыль на верхней кромке, мухи, захватанные
    # углы, ручка и карандаш
    if game in PAPER:
        zoned("Бумага пожелтела", "yellow", "cloudy.png", 300, 0.4, ["Бумага"],
              color=(0.95, 0.86, 0.66), cmode=L.BlendingMode.Multiply, cop=0.45)
        zoned("Краска выцвела", "yellow", "cloudy.png", 400, 1.1, ["Бумага"],
              color=(0.90, 0.88, 0.82), cmode=L.BlendingMode.Screen, cop=0.15)
        plain_zone("Пятна сырости", "damp", ["Бумага"], color=(0.80, 0.70, 0.52), cmode=L.BlendingMode.Multiply, cop=0.6)
        plain_zone("Ржавчина у кнопок", "rust_pins", ["Бумага"], color=(0.58, 0.40, 0.22), cmode=L.BlendingMode.Multiply,
                   cop=0.7)
        zoned("Пыль на верхней кромке", "top_dust", "grunge_dust_spread/grunge_dust_spread", 300, 0.7, ["Бумага"],
              proc=True, color=DUST, cop=0.35, rough=0.9, rop=0.3, metal=0.0)
        zoned("Мухи", "flies", "dust_specks.png", 500, 0.9, ["Бумага"], color=(0.08, 0.06, 0.04), cop=0.25)
        zoned("Углы захватаны", "corners", "prints_a.png", 120, 0.6, ["Бумага"],
              color=(0.82, 0.76, 0.66), cmode=L.BlendingMode.Multiply, cop=0.5)
        plain_zone("Ручка", "pen", ["Бумага"], color=INK, cop=0.95, rough=0.72, rop=0.6)
        plain_zone("Карандаш", "pencil", ["Бумага"], color=(0.12, 0.12, 0.13), cop=0.7, rough=0.6, rop=0.5)
        if game == "it_chart":
            lr = add(_layer("Рейки захватаны", nxt(), color=(0.74, 0.68, 0.60), cmode=L.BlendingMode.Multiply, cop=0.45),
                     ["Рейка_дерево"])
            _first_tri(lr, f"{MK}/grime.png", 60, bbox_mm, rot=0.5)

    # 10. картины: пыль на багете сверху (общий слой 2), на стекле — пыль и мухи
    if game in ("it_frame", "it_frame_pl"):
        lg = add(_layer("Пыль на стекле", nxt(), color=DUST, cop=0.18, rough=0.5, rop=0.4, metal=0.0), ["Стекло"])
        _first_tri(lg, "grunge_dust_spread/grunge_dust_spread", 300, bbox_mm, rot=0.7, proc=True)
        lf = add(_layer("Мухи на стекле", nxt(), color=(0.08, 0.06, 0.04), cop=0.6), ["Стекло"])
        _first_tri(lf, f"{MK}/dust_specks.png", 180, bbox_mm, rot=0.9)

    # 11. техника: пыль слоем (общий слой 2 сильнее), отпечатки на глянце и стекле, затёртые клавиши
    if game == "it_pc":
        zoned("Пыль в сетке фасада", "mesh_dust", "dust_grain.png", 60, 0.3, ["Сетка_фасад"],
              color=DUST, cop=0.4, rough=0.9, rop=0.4, metal=0.0)
        zoned("Отпечатки на стекле", "glass", "prints_a.png", 120, 0.6, ["Стекло_тёмное"],
              color=(0.55, 0.55, 0.55), cmode=L.BlendingMode.Screen, cop=0.12, rough=0.25, rmode="add", rop=0.7)
        zoned("Кнопка захватана", "touch", "prints_b.png", 40, 0.5, color=(0.30, 0.30, 0.30),
              cmode=L.BlendingMode.Screen, cop=0.12, rough=-0.15, rmode="add", rop=0.6)
    if game in ("it_monitor", "it_laptop"):
        zoned("Пыль на экране", "screen", "grunge_dust_spread/grunge_dust_spread", 300, 0.4, ["Экран"], proc=True,
              color=DUST, cop=0.16, rough=0.35, rmode="add", rop=0.6)
        zoned("Отпечатки на экране", "screen", "prints_b.png", 100, 0.9, ["Экран"],
              color=(0.45, 0.45, 0.45), cmode=L.BlendingMode.Screen, cop=0.1, rough=0.2, rmode="add", rop=0.6)
    if game == "it_monitor":
        zoned("Кнопки захватаны", "touch", "prints_a.png", 40, 0.5, color=(0.30, 0.30, 0.30),
              cmode=L.BlendingMode.Screen, cop=0.1, rough=-0.12, rmode="add", rop=0.5)
    if game in ("it_keyboard", "it_laptop"):
        zoned("Клавиши затёрты до блеска", "keys", "cloudy.png", 40, 0.4, ["Клавиши"],
              rough=-0.25, rmode="add", rop=1.0)
        zoned("Подписи стёрты", "keys", "chips.png", 25, 0.7, ["Клавиши"], color=(0.03, 0.03, 0.03), cop=0.75)
    if game == "it_laptop":
        zoned("Подставка затёрта ладонями", "touch", "cloudy.png", 80, 0.6, ["Корпус_ноутбук"],
              color=(0.80, 0.80, 0.80), cmode=L.BlendingMode.Multiply, cop=0.35, rough=-0.12, rmode="add", rop=0.7)
        zoned("Отпечатки на крышке", "lid", "prints_a.png", 120, 0.3, ["Корпус_ноутбук"],
              color=(0.60, 0.60, 0.60), cmode=L.BlendingMode.Screen, cop=0.1, rough=-0.1, rmode="add", rop=0.6)
    if game == "it_mouse":
        zoned("Мышь затёрта пальцами", "touch", "cloudy.png", 40, 0.5, color=(0.32, 0.32, 0.32),
              cmode=L.BlendingMode.Screen, cop=0.1, rough=-0.2, rmode="add", rop=0.8)

    # 12. тубус: держали за середину (засалено, серее), торцы шаркали о пол
    if game == "it_tube":
        zoned("Тубус захватан", "touch", "grime.png", 80, 0.6, ["Тубус_пластик"],
              color=(0.20, 0.19, 0.18), cop=0.3, rough=-0.08, rmode="add", rop=0.5)
        zoned("Торцы исшарканы", "ends", "scratches.png", 60, 0.4, ["Тубус_пластик"],
              color=(0.45, 0.45, 0.45), cmode=L.BlendingMode.Screen, cop=0.3, rough=0.12, rmode="add", rop=0.7)

    # 13. учебники и тетради: углы и корешок потёрты до картона, обрез пожелтел, кольцо от кружки, надписи ручкой
    if game in BOOKS or game in OPEN:
        cover = ["Переплёт", "Обложка_тетради"]
        zoned("Углы и корешок потёрты", "fray", "chips.png", 40, 0.7, cover,
              color=(0.56, 0.50, 0.42), cop=0.8, rough=0.85, rop=0.8, metal=0.0)
        lp = add(_layer("Обрез пожелтел", nxt(), color=(0.94, 0.86, 0.68), cmode=L.BlendingMode.Multiply, cop=0.55),
                 ["Обрез", "Бумага"])
        _first_tri(lp, f"{MK}/cloudy.png", 120, bbox_mm, rot=0.4)
        plain_zone("Кольцо от кружки", "rings", cover, color=(0.60, 0.46, 0.30), cmode=L.BlendingMode.Multiply, cop=0.6)
        plain_zone("Надписи ручкой", "ink", None, color=INK, cop=0.95, rough=0.72, rop=0.5)
        zoned("Страницы захватаны у края", "touch", "prints_a.png", 60, 0.5, ["Обрез", "Бумага"],
              color=(0.84, 0.78, 0.68), cmode=L.BlendingMode.Multiply, cop=0.45)
    return f"{game}: {len(made)} слоёв износа{' (' + (variant or print_key) + ')' if (variant or print_key) else ''}"
