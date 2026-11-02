"""Вещи общежития, партия 3, игровые версии (навык godot-asset-preparation), бюджет «средне» (владелец 2026-11-02):
карты износа этапа 2 уменьшены — крупное и бумага 1K, мышь, тетради и учебник 512; тяжёлое (листы плакатов и
чертежей, ткань сумки, корпус и подкладка чемодана, тубус, мышь) упрощено схлопыванием рёбер с той же развёрткой, рельеф
запечён в нормаль набора (Cycles на процессоре, furniture2_game.prepare_set).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Items_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/items3_game.py [-- набор …]

Каждое состояние формы — своя модель (it_ammo и it_ammo_open, it_frame_fallen, it_pc_opened …): детали набора в позе
корня формы — у неупрощённых вершины берутся у сеток формы (топология та же, как в файле просмотра), у упрощённых —
тем же жёстким переносом (лучший поворот и сдвиг по вершинам high); свои сетки состояния (разбитое стекло, полупустая
сумка, открытая коробка) — без сдвига на время текстур. У открытых ящиков и раскрытого чемодана крышка и створка —
узлы с осью в шарнире и углом открытия (index movers: open): стенд при обыске ставит открытую модель вместо закрытой и
доводит крышку от закрытого положения до открытого.

→ assets/models/dorm/furniture/<модель>.gltf (+ textures/<набор>_*.webp — общие у состояний набора); варианты отделки и
картинки — textures/<набор>__<ключ>_*.webp (у упрощённых наборов без нормали — в нормали набора запечён рельеф);
записи — в общий furniture.json (material — набор). Низкие сетки — копией RING_Dorm_Items_game_v01.blend рядом с
исходником; настройки карт — furniture_imports.py после первого --import.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture_game as FG  # noqa: E402
import furniture2_game as F2  # noqa: E402
import items3_review as RV  # noqa: E402
import items3_uv as U  # noqa: E402

ROOT = "E:/Games/RING-godot"
F2.SRC = ROOT + "/_asset_src/dorm_items3/maps_worn"
F2.GAME_MAPS = ROOT + "/_asset_src/dorm_items3/game_maps"
F2.RES = {"it_mouse": 512, "it_notebook": 512, "it_notebook48": 512, "it_book": 512}
F2.DECIMATE = {"it_suitcase": {"Пластик_корпус": 2600, "Пластик_корпус__створка": 2600, "Подкладка_ткань": 1200,
                               "Подкладка_ткань__створка": 1200},
               "it_duffel": {"Ткань_сумка": 5000, "Ткань_сумка__полупустая": 5000},
               "it_poster": {"Бумага": 2400}, "it_poster_torn": {"Бумага": 4000}, "it_poster_curl": {"Бумага": 3000},
               "it_poster_s": {"Бумага": 1600}, "it_poster_s_curl": {"Бумага": 1800}, "it_clip": {"Бумага": 900},
               "it_calendar": {"Бумага": 1800, "Кнопка_сталь": 1200}, "it_chart": {"Бумага__полотно": 2000},
               "it_drawing": {"Бумага": 2000}, "it_drawing_roll": {"Бумага": 3000},
               "it_tube": {"Тубус_пластик": 2400, "Тубус_пластик__крышка": 1000},
               "it_mouse": {"Пластик_чёрный": 1400}}
F2.GLASS = RV.SEE
# состояния формы → имя модели (основной корень набора — имя набора)
NAMES = {"ЯП_ящик_патроны_открыт": "it_ammo_open", "ЯЗ_ящик_ЗИП_открыт": "it_zip_open", "МС_сундук_открыт": "it_trunk_open",
         "ИЯ_ящик_инструменты_открыт": "it_toolbox_open", "ЧМ_чемодан_раскрыт": "it_suitcase_open",
         "СС_сумка_полупустая": "it_duffel_half", "КК_коробка_открыта": "it_carton_open",
         "УТ_таблица_сорвана": "it_chart_fallen", "КР_картина_разбито": "it_frame_broken",
         "КР_картина_упала": "it_frame_fallen", "ПК_системный_блок_вскрыт": "it_pc_opened",
         "МН_монитор_разбит": "it_monitor_broken", "НБ_ноутбук_разбит": "it_laptop_broken",
         "НБ_ноутбук_закрыт": "it_laptop_closed", "ТБ_тубус_открыт": "it_tube_open"}
# шарниры открытых моделей: набор → (метка узла, деталь формы с точкой оси); ось и угол — по повороту детали у корня
# открытого состояния
HINGES = {"it_ammo": ("крышка", "ЯП_ящик_патроны_крышка"), "it_zip": ("крышка", "ЯЗ_ящик_ЗИП_крышка"),
          "it_trunk": ("крышка", "МС_крышка"), "it_suitcase": ("створка", "ЧМ_створка")}


def key(ob) -> str:
    return ob.name.split(".")[0]


def tag(k: str) -> str:
    return k.split("__")[1] if "__" in k else ""


def unshift(s: str, k: str) -> Matrix:
    return Matrix.Translation(-V(U.OFFSETS.get(s, {}).get(k, (0.0, 0.0, 0.0))))


def coords(me) -> np.ndarray:
    co = np.empty(3 * len(me.vertices))
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def rigid(a: np.ndarray, b: np.ndarray) -> tuple[Matrix, float]:
    """Лучший поворот и сдвиг a → b (Кабш) и наибольшее расхождение, м."""
    ca, cb = a.mean(0), b.mean(0)
    h = (a - ca).T @ (b - cb)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    t = cb - r @ ca
    err = float(np.abs(a @ r.T + t - b).max())
    m = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            m[i][j] = r[i][j]
        m[i][3] = t[i]
    return m, err


def state_meshes(s: str, root_name: str, prefixes, state_tag, P: dict, highs: dict) -> dict:
    """Сетки модели состояния (ключ → новая сетка в осях корня состояния): детали набора в позе корня, свои сетки
    состояния — без сдвига. Основной корень — детали как есть."""
    spec = U.ITEMS[s]
    state_tags = {t for _, _, t in spec[1:] if isinstance(t, str)}
    base_keys = [k for k in P if tag(k) not in state_tags]
    out = {}
    if root_name == spec[0][0]:
        for k in base_keys:
            out[k] = P[k].data.copy()
        return out
    exclude = None if not isinstance(state_tag, str) else (prefixes or ())
    posed, tmp = RV.pose_meshes(s, root_name, exclude)
    for k in base_keys:
        src = posed.get(k)
        if src is None:
            continue  # детали нет в этом состоянии (чека открытого ящика, память вскрытого корпуса)
        hi = highs[k].data
        if len(src.data.vertices) != len(hi.vertices):
            print("ПОЗА: другая топология", s, root_name, k, flush=True)
            continue
        me = P[k].data.copy()
        if len(me.vertices) == len(hi.vertices):
            me.vertices.foreach_set("co", coords(src.data).ravel())
            me.update()
        else:
            m, err = rigid(coords(hi), coords(src.data))
            if err > 0.002:
                print("ПОЗА: не жёсткий перенос", s, root_name, k, round(err, 4), flush=True)
            me.transform(m)
        out[k] = me
    RV.drop(tmp)
    if isinstance(state_tag, str):
        for k in P:
            if tag(k) == state_tag:
                me = P[k].data.copy()
                me.transform(unshift(s, k))
                out[k] = me
    return out


def placement(s: str, root_name: str) -> Matrix:
    """Модель состояния — в осях своего корня формы с его поворотом; сдвиг от основного корня — только на той же опоре
    (раскрытый чемодан лёг на пол рядом), у упавшей со стены картины начало — у её корня на полу."""
    base = bpy.data.objects[U.ITEMS[s][0][0]].matrix_world
    mw = bpy.data.objects[root_name].matrix_world
    d = V((0.0, 0.0, 0.0))
    if (base.translation.z < 0.5) == (mw.translation.z < 0.5):
        d = V((0.0, mw.translation.y - base.translation.y, mw.translation.z - base.translation.z))
    return Matrix.Translation(d) @ mw.to_3x3().normalized().to_4x4()


def hinge(s: str, root_name: str, m: Matrix):
    """Шарнир открытой модели: точка оси (оси модели), ось (так, что плюс открывает) и угол открытия, градусы."""
    node, part = HINGES[s]
    closed = bpy.data.objects[part]
    opened = next(o for o in bpy.data.objects[root_name].children if key(o) == part)
    rot = opened.rotation_euler
    i = max(range(3), key=lambda j: abs(rot[j]))
    axis = V([0.0, 0.0, 0.0])
    axis[i] = -1.0 if rot[i] < 0 else 1.0
    pivot = m @ closed.matrix_local.translation
    axis = (m.to_3x3() @ axis).normalized()
    return node, pivot, axis, round(abs(math.degrees(rot[i])), 2)


def main() -> None:
    os.makedirs(F2.TEX, exist_ok=True)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    for c in top.children:
        c.hide_viewport = False
        c.hide_render = False
    store = bpy.data.collections.new("Игровые_детали")
    bpy.context.scene.collection.children.link(store)
    game = bpy.data.collections.new("Игровая_v01")
    bpy.context.scene.collection.children.link(game)
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    sets = [s for s in U.ITEMS if not only or s in only]
    # высокие сетки — до prepare_set (он их прячет), по ключу
    highs = {s: {key(o): o for o in bpy.data.collections[s].objects if o.type == "MESH"} for s in sets}
    P = {s: F2.prepare_set(s, store) for s in sets}
    variants = {s: F2.variant_maps(s, with_normal=s not in F2.DECIMATE) for s in sets}
    idx_path = f"{F2.OUT}/furniture.json"
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    for s in sets:
        spec = U.ITEMS[s]
        states = [(spec[0][0], None, None)] + spec[1:] + [(p, None, None) for p in RV.POSES.get(s, [])]
        for root_name, prefixes, state_tag in states:
            name = s if root_name == spec[0][0] else NAMES[root_name]
            mes = state_meshes(s, root_name, prefixes, state_tag, P[s], highs[s])
            m = Matrix.Identity(4) if name == s else placement(s, root_name)
            for me in mes.values():
                me.transform(m)
            root = bpy.data.objects.new(name, None)
            game.objects.link(root)
            movers = []
            node = None
            if name != s and s in HINGES:
                node, pivot, axis, angle = hinge(s, root_name, m)
                movers.append({"node": node, "kind": "hinge", "pivot": F2.gd(pivot), "axis": F2.gd(axis),
                               "open": angle})
            body = [me for k, me in mes.items() if tag(k) != node]
            F2.mesh_from(body, f"{name}_корпус", game, root)
            if node is not None:
                F2.mesh_from([me for k, me in mes.items() if tag(k) == node], node, game, root, pivot)
            for me in mes.values():
                bpy.data.meshes.remove(me)
            F2.export(root, name)
            tris = sum(FG.tris(c.data) for c in root.children_recursive if c.type == "MESH")
            index[name] = {"file": f"res://assets/models/dorm/furniture/{name}.gltf", "triangles": tris,
                           "aabb": F2.aabb(root), "material": s, "variants": variants[s]}
            if movers:
                index[name]["movers"] = movers
            for c in root.children:
                c.name = f"{name}:{c.name}"
            print("MODEL", name, tris, [mv["node"] for mv in movers], flush=True)
    with open(idx_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    if only:
        return  # выборочная пересборка: копия низких сеток не перезаписывается неполной
    out = bpy.data.filepath.replace("_uv_v01.blend", "_game_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
