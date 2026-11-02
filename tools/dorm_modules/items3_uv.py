"""Вещи общежития, партия 3: производственная развёртка принятых форм и FBX для Painter (этап 1 текстур).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "E:/Models Blender/ENVIRONMENT/RING_Dorm_Items/models/RING_Dorm_Items_v01.blend" \
      --python-exit-code 1 --python tools/dorm_modules/items3_uv.py [-- набор …]

Форма всех четырёх групп принята владельцем 2026-11-02 — сетки не меняются (вырезы-модификаторы применяются). На вещь —
один набор текстур (материал с его игровым именем), детали — сетками по слотам материалов. Что в игре открывается,
снимается или прячется отдельно — своя сетка уже здесь: «<слот>__<метка>» (крышки ящиков и сундука, чека, лотки и рычаги
ящика для инструментов, створка чемодана, клапаны коробки, стекло корпуса ПК, крышка ноутбука и тубуса, полотно учебной
таблицы, тросик картины); слот finish-spec-3.json — часть имени до «__». Открытое — те же сетки в другом положении
(игровой этап). Варианты с другой геометрией: бумага (целый / надорван / угол, свернулся) и стопки, ряд, раскрытые книги
и тетради — свои наборы (печать во весь лист); остальные (разбитые стекло картины и экраны, полупустая сумка, клапаны и
скотч открытой коробки, шнур сорванной таблицы, листы в открытом тубусе) — сетками в наборе основной вещи, сдвинутыми
на время текстур (OFFSETS).

Бумага: развёртка печати — второй слой «Печать» из формы (build_items3.sheet); у изнанки и торцов листа он гасится (−1),
лицо остаётся — print_bake.py запекает его картой «prm», и печать (картинки владельца) кладётся по нему без искажений
и на завёрнутом угле. Изнанка — мельче (её почти не видно), скрытые листы календаря и подложка — тоже. Сумка — развёртка
выкройкой из формы (труба и торцы), не smart; внутренняя оболочка ткани (закрытая сумка) — крошечным островом.
FBX — только с основной развёрткой. Выход: RING_Dorm_Items_uv_v01.blend рядом с формой и
_asset_src/dorm_items3/sp/<набор>.fbx.
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import electrics_uv as E  # noqa: E402
from furniture2_uv import uv_islands  # noqa: E402

OUT_FBX = "E:/Games/RING-godot/_asset_src/dorm_items3/sp"
PRINT = "Печать"
FLAPS = {f"КК_коробка_клапан_{t}": f"клапан_{t}" for t in ("перед", "зад", "лев", "прав")}

# набор: [(корень формы, начала имён деталей или None — все, метка: {деталь: метка} — она и всё под ней, строка — всем)]
ITEMS = {
    "it_ammo": [("ЯП_ящик_патроны", None, {"ЯП_ящик_патроны_крышка": "крышка", "ЯП_ящик_патроны_чека": "чека"})],
    "it_zip": [("ЯЗ_ящик_ЗИП", None, {"ЯЗ_ящик_ЗИП_крышка": "крышка", "ЯЗ_ящик_ЗИП_чека": "чека"})],
    "it_trunk": [("МС_сундук", None, {"МС_крышка": "крышка"})],
    "it_toolbox": [("ИЯ_ящик_инструменты", None, {"ИЯ_лоток_перед": "лоток_перед", "ИЯ_лоток_зад": "лоток_зад",
                                                 "ИЯ_рычаги_лоток_перед": "рычаги_перед", "ИЯ_рычаги_лоток_зад": "рычаги_зад"})],
    "it_suitcase": [("ЧМ_чемодан", None, {"ЧМ_створка": "створка"})],
    "it_duffel": [("СС_сумка", None, None), ("СС_сумка_полупустая", None, "полупустая")],
    "it_carton": [("КК_коробка", None, FLAPS), ("КК_коробка_открыта", ("КК_коробка_клапан", "КК_коробка_скотч"), "открыта")],
    "it_poster": [("ПЛ_плакат", None, None)],
    "it_poster_torn": [("ПЛ_плакат_надорван", None, None)],
    "it_poster_curl": [("ПЛ_плакат_угол", None, None)],
    "it_poster_s": [("ПС_плакат", None, None)],
    "it_poster_s_curl": [("ПС_плакат_угол", None, None)],
    "it_clip": [("ВР_вырезка", None, None)],
    "it_calendar": [("КЛ_календарь", None, None)],
    "it_chart": [("УТ_таблица", None, {"УТ_полотно": "полотно"}),
                 ("УТ_таблица_сорвана", ("УТ_шнур_гвоздь", "УТ_обрывок"), "сорвана")],
    "it_drawing": [("ЧР_чертёж", None, None)],
    "it_drawing_roll": [("ЧР_чертёж_свернулся", None, None)],
    "it_frame": [("КР_картина", None, {"КР_картина_тросик_гвоздь": "тросик"}), ("КР_картина_разбито", ("КР_картина_стекло",), "разбито")],
    "it_frame_pl": [("КР_картина_пластик", None, None)],
    # у вскрытого память и видеокарта вынуты — у целого это свои узлы (игра их прячет)
    "it_pc": [("ПК_системный_блок", None, {"ПК_стекло": "стекло", "ПК_память": "память", "ПК_видеокарта": "видеокарта",
                                           "ПК_видеокарта_вент": "видеокарта", "ПК_видеокарта_лопасти": "видеокарта"})],
    "it_monitor": [("МН_монитор", None, None), ("МН_монитор_разбит", ("МН_экран",), "разбит")],
    "it_keyboard": [("КВ_клавиатура", None, None)],
    "it_mouse": [("МШ_мышь", None, None)],
    "it_laptop": [("НБ_ноутбук", None, {"НБ_крышка": "крышка"}), ("НБ_ноутбук_разбит", ("НБ_экран",), "разбит")],
    "it_tube": [("ТБ_тубус", None, {"ТБ_крышка": "крышка"}), ("ТБ_тубус_открыт", ("ТБ_чертежи",), "открыт")],
    "it_notebook": [("ТТ_тетрадь", None, None)],
    "it_notebook_open": [("ТТ_тетрадь_раскрыта", None, None)],
    "it_notebook_stack": [("ТТ_тетрадь_стопка", None, None)],
    "it_notebook48": [("ТО_тетрадь_общая", None, None)],
    "it_book": [("УЧ_учебник", None, None)],
    "it_book_open": [("УЧ_учебник_раскрыт", None, None)],
    "it_book_stack": [("УЧ_учебник_стопка", None, None)],
    "it_book_row": [("УЧ_учебник_ряд", None, None)],
}
GAMES = list(ITEMS)  # для print_bake.py
# мелкое — 1K (тетрадь 170 × 205, мышь); остальное — 2K
RES = {"it_mouse": 1024, "it_notebook": 1024, "it_notebook48": 1024, "it_notebook_open": 1024}
# сдвиг сеток-вариантов на время текстур (м): лёжа на месте основной детали, они затеняли бы её при запекании; игровой
# этап и файл просмотра возвращают их на место (вычитают сдвиг)
OFFSETS = {
    "it_duffel": {k: (0.9, 0.0, 0.0) for k in ("Ткань_сумка__полупустая", "Молния__полупустая", "Стропа__полупустая")},
    "it_carton": {k: (1.0, 0.0, 0.0) for k in ("Картон__открыта", "Картон_срез__открыта", "Скотч__открыта")},
    "it_chart": {"Верёвка__сорвана": (1.0, 0.0, 0.0)},
    "it_frame": {"Стекло__разбито": (0.6, 0.0, 0.0)},
    "it_monitor": {"Экран__разбит": (0.8, 0.0, 0.0)},
    "it_laptop": {"Экран__разбит": (0.5, 0.0, 0.0)},
    "it_tube": {"Бумага__открыт": (0.0, 0.4, 0.0)},
}
E.OFFSETS.update(OFFSETS)
# развёртка из формы, не smart (ключ сетки без «__метки»)
KEEP_UV = {"Ткань_сумка"}
# изнанка и торцы листа — мельче лица: у висящего их почти не видно; у завёрнутого угла и рулона изнанка на виду
BACK = {"it_poster_curl": 0.5, "it_poster_s_curl": 0.5, "it_drawing_roll": 0.75}
BACK_DEFAULT = 0.35
# доски — волокна вдоль длины, картон — гофра поперёк длинной стороны (вертикально на стенках): острова по U, укладка
# без поворота (align)
ALIGN = {"Дерево_окраска", "Картон"}


def resolve(spec):
    """Метки деталей → функция (имя объекта, центр грани) → метка: деталь и все её потомки."""
    out = []
    for root_name, prefixes, tag in spec:
        if isinstance(tag, dict):
            names = {}
            root = bpy.data.objects[root_name]
            for ob in root.children_recursive:
                t = tag.get(ob.name.split(".")[0])
                if t:
                    for o in [ob] + list(ob.children_recursive):
                        names[o.name] = t
            out.append((root_name, prefixes, lambda n, c, names=names: names.get(n, "")))
        elif isinstance(tag, str):
            out.append((root_name, prefixes, lambda n, c, tag=tag: tag))
        else:
            out.append((root_name, prefixes, None))
    return out


def face_area(uvs) -> float:
    a = 0.0
    for i in range(len(uvs)):
        x0, y0 = uvs[i]
        x1, y1 = uvs[(i + 1) % len(uvs)]
        a += x0 * y1 - x1 * y0
    return a / 2


def base_name(ob) -> str:
    """Слот сетки: имя без «.NNN» (одинаковые слоты разных наборов) и без «__метки»."""
    return ob.name.split(".")[0].split("__")[0]


def mark_print(ob) -> None:
    """Слой «Печать»: у граней, где картинка читается (лицо листа: площадь в развёртке печати больше нуля), он
    остаётся; изнанка и торцы — (−1, −1). Лист без толщины (календарь), повёрнутый нормалью к стене, разворачивается
    лицом наружу: иначе в игре (задние грани не рисуются) его не видно, а печать считалась бы изнанкой."""
    if PRINT not in ob.data.uv_layers:
        return
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    pr = bm.loops.layers.uv[PRINT]
    for comp in components(bm):
        signs = [face_area([tuple(lp[pr].uv) for lp in f.loops]) for f in comp]
        if not any(s > 1e-9 for s in signs) and sum(1 for s in signs if s < -1e-9) > len(comp) // 2:
            bmesh.ops.reverse_faces(bm, faces=comp)
    for f in bm.faces:
        if face_area([tuple(lp[pr].uv) for lp in f.loops]) <= 1e-9:
            for lp in f.loops:
                lp[pr].uv = (-1.0, -1.0)
    bm.to_mesh(ob.data)
    bm.free()


def reset_layers(ob) -> None:
    """Слои развёртки заново: первым — основной «UVMap» (Painter, игра), вторым — «Печать» (если был); у KEEP_UV
    основной — прежний (выкройка из формы)."""
    me = ob.data
    n = len(me.loops)
    keep = {}
    for name in (PRINT, "UVMap"):
        lay = me.uv_layers.get(name)
        if lay is not None and (name == PRINT or base_name(ob) in KEEP_UV):
            buf = [0.0] * (2 * n)
            lay.data.foreach_get("uv", buf)
            keep[name] = buf
    for lay in list(me.uv_layers):
        me.uv_layers.remove(lay)
    for name in ("UVMap", PRINT):
        if name == PRINT and PRINT not in keep:
            continue
        lay = me.uv_layers.new(name=name)
        if name in keep:
            lay.data.foreach_set("uv", keep[name])
    me.uv_layers.active = me.uv_layers["UVMap"]


def components(bm):
    """Связные куски сетки (по рёбрам)."""
    seen, out = set(), []
    for start in bm.faces:
        if start in seen:
            continue
        comp, stack = [], [start]
        seen.add(start)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g not in seen:
                        seen.add(g)
                        stack.append(g)
        out.append(comp)
    return out


def shrink_rules(game, ob):
    """Грани, которым меньше или больше места (выбор → множитель): изнанка листа, скрытые листы календаря и подложка,
    внутренняя оболочка закрытой сумки — мельче; верх клавиш — втрое крупнее (подписи 3–4 мм читаются)."""
    me = ob.data
    base = base_name(ob)
    rules = []
    if PRINT in me.uv_layers:
        k = BACK.get(game, BACK_DEFAULT)
        rules.append(("back", k))
    if game == "it_calendar" and base == "Бумага":
        rules.append(("calendar", 0.25))
    if base == "Ткань_сумка":
        rules.append(("inner", 0.05))
    if base == "Клавиши":
        rules.append(("keytops", 3.0))
    if base == "Переплёт" and game != "it_book_open":
        rules.append(("spine", 2.5))
    return rules


def second_axis(cov) -> Vector:
    """Вторая главная ось облака точек по его ковариации 3 × 3 (у переплёта — ширина книги)."""
    import numpy as np
    w, v = np.linalg.eigh(np.array(cov))
    a = v[:, int(np.argsort(w)[-2])]
    return Vector((float(a[0]), float(a[1]), float(a[2])))


def shrink(objs, game) -> None:
    """Масштаб островов целиком (остров не рвётся) по правилам shrink_rules: у острова — самый крупный множитель, если
    он больше 1, иначе самый мелкий."""
    for ob in objs:
        rules = shrink_rules(game, ob)
        if not rules:
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.normal_update()
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv["UVMap"]
        pr = bm.loops.layers.uv.get(PRINT)
        factor = {f.index: 1.0 for f in bm.faces}
        comps = components(bm)
        for kind, k in rules:
            if kind == "back":
                for f in bm.faces:
                    if f.loops[0][pr].uv.x < -0.5:
                        factor[f.index] = min(factor[f.index], k)
            elif kind == "calendar":
                # фронтальный лист — кусок с наименьшим средним y (ближе всех к смотрящему); подложка — без печати
                sheets = [c for c in comps if pr is not None and any(f.loops[0][pr].uv.x >= 0 for f in c)]
                front = min(sheets, key=lambda c: sum(f.calc_center_median().y for f in c) / len(c)) if sheets else None
                for c in comps:
                    if c is not front:
                        for f in c:
                            factor[f.index] = min(factor[f.index], k)
            elif kind == "keytops":
                for f in bm.faces:
                    if f.normal.z > 0.85:
                        factor[f.index] = max(factor[f.index], k)
            elif kind == "spine":
                # корешок книги: у куска переплёта вторая главная ось — ширина, корешок — на той её стороне, куда
                # смещена средняя вершина (дуга гуще вершинами); его грани смотрят туда же
                for comp in comps:
                    vs = list({v for f in comp for v in f.verts})
                    pts = [v.co for v in vs]
                    c = sum(pts, Vector()) / len(pts)
                    lo = Vector([min(q[i] for q in pts) for i in range(3)])
                    hi = Vector([max(q[i] for q in pts) for i in range(3)])
                    mid = (lo + hi) / 2
                    cov = [[sum((q[i] - c[i]) * (q[j] - c[j]) for q in pts) for j in range(3)] for i in range(3)]
                    w = second_axis(cov)
                    if (c - mid).dot(w) > 0:
                        w = -w          # теперь w — от корешка к обрезу
                    for f in comp:
                        if f.normal.dot(-w) > 0.45:
                            factor[f.index] = max(factor[f.index], k)
            elif kind == "inner":
                # закрытая ткань с толщиной — два куска: наружный и внутренний (меньший по размаху)
                if len(comps) >= 2:
                    def span(c):
                        vs = {v for f in c for v in f.verts}
                        return sum(max(v.co[i] for v in vs) - min(v.co[i] for v in vs) for i in range(3))
                    outer = max(comps, key=span)
                    for c in comps:
                        if c is not outer:
                            for f in c:
                                factor[f.index] = min(factor[f.index], k)
        for island in uv_islands(bm, uv):
            ks = [factor[f.index] for f in island]
            k = max(ks) if max(ks) > 1.0 else min(ks)
            if k == 1.0:
                continue
            loops = [lp for f in island for lp in f.loops]
            c = sum((lp[uv].uv for lp in loops), Vector((0.0, 0.0))) / len(loops)
            for lp in loops:
                lp[uv].uv = c + (lp[uv].uv - c) * k
        bm.to_mesh(ob.data)
        bm.free()


def orient(objs, game) -> None:
    """Тонкие листы без толщины — лицом наружу: в игре задние грани не рисуются, а Painter запёк бы затенение не с той
    стороны. Обложка тетради — от блока листов (у раскрытой — вверх), скотч на стене — от стены (к −Y)."""
    blocks = []
    for ob in objs:
        if base_name(ob) == "Бумага" and game.startswith("it_notebook"):
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            for comp in components(bm):
                vs = {v for f in comp for v in f.verts}
                blocks.append(sum((v.co for v in vs), Vector()) / len(vs))
            bm.free()
    for ob in objs:
        b = base_name(ob)
        if b not in ("Обложка_тетради", "Скотч_прозрачный"):
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.normal_update()
        flipped = 0
        for comp in components(bm):
            if b == "Скотч_прозрачный":
                score = sum(-f.normal.y * f.calc_area() for f in comp)
            elif game == "it_notebook_open" or not blocks:
                score = sum(f.normal.z * f.calc_area() for f in comp)
            else:
                vs = {v for f in comp for v in f.verts}
                cc = sum((v.co for v in vs), Vector()) / len(vs)
                bc = min(blocks, key=lambda q: (q - cc).length)
                score = sum(f.normal.dot(f.calc_center_median() - bc) * f.calc_area() for f in comp)
            if score < 0:
                bmesh.ops.reverse_faces(bm, faces=comp)
                flipped += 1
        bm.to_mesh(ob.data)
        bm.free()
        if flipped:
            print(f"  {game}: {ob.name} — развёрнуто лицом наружу кусков: {flipped}", flush=True)


def unwrap(objs, game) -> None:
    """Smart UV (66°) по всему, кроме KEEP_UV; общий масштаб островов; мельче — изнанка и скрытое; укладка."""
    orient(objs, game)
    for ob in objs:
        mark_print(ob)
        reset_layers(ob)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    for ob in objs:
        bm = bmesh.from_edit_mesh(ob.data)
        keep = base_name(ob) in KEEP_UV
        for f in bm.faces:
            f.select_set(not keep)
        bmesh.update_edit_mesh(ob.data)
    if any(base_name(ob) not in KEEP_UV for ob in objs):
        bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=0.004, area_weight=0.0,
                                 correct_aspect=True, scale_to_bounds=False)
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    shrink(objs, game)
    aligned = align(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    # выровненные доски укладываются без поворота: иначе волокна фото легли бы поперёк
    bpy.ops.uv.pack_islands(rotate=not aligned, margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")


def align(objs) -> bool:
    """Доски — волокна вдоль длины: остров повёрнут так, чтобы его длинная сторона в пространстве шла по U (фото
    пиленой сосны в отделке кладётся по развёртке, волокнами вдоль U)."""
    done = False
    for ob in objs:
        if base_name(ob) not in ALIGN:
            continue
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.faces.ensure_lookup_table()
        uv = bm.loops.layers.uv["UVMap"]
        for island in uv_islands(bm, uv):
            vs = list({v for f in island for v in f.verts})
            # длинная ось — наибольший разброс вершин (у доски — длина, у бруска — высота)
            best, axis = -1.0, None
            for d in (Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))):
                span = max(v.co.dot(d) for v in vs) - min(v.co.dot(d) for v in vs)
                if span > best:
                    best, axis = span, d
            f = max(island, key=lambda q: q.calc_area())
            lp = list(f.loops)
            e1, e2 = lp[1].vert.co - lp[0].vert.co, lp[2].vert.co - lp[0].vert.co
            d1, d2 = lp[1][uv].uv - lp[0][uv].uv, lp[2][uv].uv - lp[0][uv].uv
            # ось в базисе грани (наименьшие квадраты) → её направление в развёртке
            a11, a12, a22 = e1.dot(e1), e1.dot(e2), e2.dot(e2)
            b1, b2 = axis.dot(e1), axis.dot(e2)
            det = a11 * a22 - a12 * a12
            if abs(det) < 1e-14:
                continue
            al, be = (b1 * a22 - b2 * a12) / det, (a11 * b2 - a12 * b1) / det
            d = d1 * al + d2 * be
            if d.length < 1e-9:
                continue
            ang = -math.atan2(d.y, d.x)
            ca, sa = math.cos(ang), math.sin(ang)
            loops = [q for g in island for q in g.loops]
            cu = sum((q[uv].uv for q in loops), Vector((0.0, 0.0))) / len(loops)
            for q in loops:
                x, y = q[uv].uv - cu
                q[uv].uv = (cu.x + x * ca - y * sa, cu.y + x * sa + y * ca)
            done = True
        bm.to_mesh(ob.data)
        bm.free()
    return done


def export_fbx(objs, game) -> None:
    """FBX для Painter — с одной основной развёрткой: «Печать» снимается на время выгрузки и возвращается."""
    saved = {}
    for ob in objs:
        lay = ob.data.uv_layers.get(PRINT)
        if lay is not None:
            buf = [0.0] * (2 * len(ob.data.loops))
            lay.data.foreach_get("uv", buf)
            saved[ob.name] = buf
            ob.data.uv_layers.remove(lay)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in objs:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.export_scene.fbx(filepath=f"{OUT_FBX}/{game}.fbx", use_selection=True, apply_unit_scale=True,
                             bake_space_transform=False, object_types={"MESH"}, mesh_smooth_type="FACE",
                             use_mesh_modifiers=False, axis_forward="-Z", axis_up="Y")
    for ob in objs:
        if ob.name in saved:
            lay = ob.data.uv_layers.new(name=PRINT)
            lay.data.foreach_set("uv", saved[ob.name])
            ob.data.uv_layers.active = ob.data.uv_layers["UVMap"]


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = set(argv)
    os.makedirs(OUT_FBX, exist_ok=True)
    top = bpy.data.collections.get("Развёртка_v01") or bpy.data.collections.new("Развёртка_v01")
    if top.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(top)
    for game, spec in ITEMS.items():
        if only and game not in only:
            continue
        old = bpy.data.collections.get(game)
        if old is not None:
            for ob in list(old.objects):
                bpy.data.objects.remove(ob)
            bpy.data.collections.remove(old)
        coll = bpy.data.collections.new(game)
        top.children.link(coll)
        objs = E.build_item(game, resolve(spec), coll)
        unwrap(objs, game)
        mat = bpy.data.materials.get(game) or bpy.data.materials.new(game)
        for ob in objs:
            ob.data.materials.clear()
            ob.data.materials.append(mat)
        export_fbx(objs, game)
        tris = sum(len(p.vertices) - 2 for ob in objs for p in ob.data.polygons)
        printed = [o.name for o in objs if PRINT in o.data.uv_layers]
        print(f"UV {game}: {sorted(o.name for o in objs)}, {tris} треуг., печать: {printed}", flush=True)
        coll.hide_viewport = True
    # с формы — новый файл развёртки; на файле развёртки (переделка отдельных наборов) — он же
    path = bpy.data.filepath
    out = path if path.endswith("_uv_v01.blend") else path.replace("_v01.blend", "_uv_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
