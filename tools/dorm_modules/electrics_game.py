"""Электрика общежития, игровые версии (навык godot-asset-preparation), бюджет «средне» (владелец 2026-11-01): карты
износа этапа 2 уменьшены — светильники, трубка, лампа 1K, настенное и провода 512; тяжёлые детали (резьба цоколя, нить,
держатели, карболит патрона, шнур, провода) упрощены схлопыванием рёбер с той же развёрткой, их рельеф запечён в нормаль
набора (Cycles на процессоре). Модели собраны из наборов текстур так же, как в форме: светильник — корпус и трубки,
плафон и патрон — с лампой; подвижное — своими узлами с осью в шарнире (рассеиватель, рычажок, клавиша).

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Electrics_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/electrics_game.py

→ assets/models/dorm/electrics/<модель>.gltf (+ textures/<набор>_*.webp, общие у моделей), варианты отделки и закраски —
textures/<набор>__<код>_*.webp (стенд подменяет ими карты материала набора); electrics.json — треугольники, габарит,
наборы, варианты, шарниры и у проводов — где модуль кончается (ports, оси Godot). Низкие сетки — копией рядом с
исходником: RING_Dorm_Electrics_game_v01.blend. Ступени детализации — автоматические при импорте Godot; настройки карт —
electrics_imports.py после первого --import.
"""
import json
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture_game as FG  # noqa: E402

ROOT = "E:/Games/RING-godot"
SRC = ROOT + "/_asset_src/dorm_electrics/maps_worn"
GAME_MAPS = ROOT + "/_asset_src/dorm_electrics/game_maps"
OUT = ROOT + "/assets/models/dorm/electrics"
TEX = OUT + "/textures"
# размер карт набора в игре (остальные — 512)
RES = {"el_tube": 1024, "el_bulb": 1024, "el_lsp": 1024, "el_lpo": 1024, "el_plafond": 1024, "el_pendant": 1024}
# упрощение: набор → {слот[__метка]: треугольников}
DECIMATE = {"el_bulb": {"Лампа_цоколь": 420, "Нить_вольфрам": 160},
            "el_lsp": {"Ламподержатель_пластик": 640},
            "el_lpo": {"Ламподержатель_пластик": 600},
            "el_plafond": {"Карболит": 640},
            "el_pendant": {"Карболит": 820, "Шнур_витой": 460},
            "el_wire_flat": {"Провод_ПВХ__прямой_1м": 620, "Провод_ПВХ__залом_вниз": 480,
                             "Провод_ПВХ__стена_потолок": 560},
            "el_wire_twisted": {"Провод_витой_оплётка": 2400, "Ролик_фарфор": 720, "Гвоздик_сталь": 420}}
# стекло: прозрачное (колба) и молочное (плафон, рассеиватель) — свои материалы «<набор>_стекло» / «<набор>_опал»
GLASS = {"Лампа_стекло": "стекло", "Плафон_стекло": "опал", "Рассеиватель_опал": "опал"}
# варианты закраски (electrics_sp.py wear) — в именах файлов латиницей
PAINT_FILE = {"краска": "paint", "побелка": "whitewash"}
TUBE_Y = 0.045  # трубки ЛСП — на ±45 мм от оси (набор el_tube взят из «одна и обломок»: целая на −Y)


def key(ob) -> str:
    return ob.name.split(".")[0]


def slot(ob) -> str:
    return key(ob).split("__")[0]


def root_local(ob):
    """Вершины детали формы в осях её корня (корень — пустышка СВ_* / ВК_* …)."""
    r = ob
    while r.parent is not None:
        r = r.parent
    m = r.matrix_world.inverted() @ ob.matrix_world
    return np.array([m @ v.co for v in ob.data.vertices]), m


def kabsch(a: np.ndarray, b: np.ndarray) -> Matrix:
    """Жёсткое преобразование, переводящее точки a в b (вершины одной сетки в одном порядке)."""
    ca, cb = a.mean(0), b.mean(0)
    u, _, vt = np.linalg.svd((a - ca).T @ (b - cb))
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1, 1, d]) @ u.T
    t = cb - r @ ca
    m = Matrix.Identity(4)
    for i in range(3):
        for j in range(3):
            m[i][j] = r[i, j]
        m[i][3] = t[i]
    return m


def game_maps(setname: str) -> str:
    """Карты износа набора в размере игры → _asset_src/dorm_electrics/game_maps/<набор>/ (нормаль упрощённых —
    запекается позже поверх)."""
    res = RES.get(setname, 512)
    out = f"{GAME_MAPS}/{setname}"
    os.makedirs(out, exist_ok=True)
    for suffix, nc in (("baseColor", False), ("occlusionRoughnessMetallic", True), ("normal", True)):
        img = bpy.data.images.load(f"{SRC}/{setname}/{setname}_{suffix}.png", check_existing=False)
        if nc:
            img.colorspace_settings.name = "Non-Color"
        _ = img.pixels[0]
        img.scale(res, res)
        img.filepath_raw = f"{out}/{setname}_{suffix}.png"
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)
    return out


def variant_maps(setname: str) -> list[str]:
    """Варианты отделки и закраски набора → textures/<набор>__<код>_*.webp в размере игры: цвет и ORM; нормаль у всех
    вариантов — набора (у упрощённых в ней запечён рельеф high, отделка рельефа почти не меняет)."""
    res = RES.get(setname, 512)
    codes = []
    for d in sorted(os.listdir(SRC)):
        if not d.startswith(setname + "__"):
            continue
        code = PAINT_FILE.get(d.split("__", 1)[1], d.split("__", 1)[1])
        for suffix, nc in (("baseColor", False), ("occlusionRoughnessMetallic", True)):
            img = bpy.data.images.load(f"{SRC}/{d}/{setname}_{suffix}.png", check_existing=False)
            if nc:
                img.colorspace_settings.name = "Non-Color"
            _ = img.pixels[0]
            img.scale(res, res)
            img.filepath_raw = f"{TEX}/{setname}__{code}_{suffix}.webp"
            img.file_format = "WEBP"
            img.save()
            bpy.data.images.remove(img)
        codes.append(code)
    return codes


def prepare_set(setname: str, store) -> dict:
    """Низкие детали набора (по ключу «слот[__метка]») с материалами из карт игры; упрощённые — нормаль запечена."""
    coll = bpy.data.collections[setname]
    highs = [o for o in coll.objects if o.type == "MESH"]
    for h in highs:
        h.matrix_world = Matrix.Identity(4)
    maps_dir = game_maps(setname)
    # карты игры грузятся первыми: экспорт называет файлы по имени картинки, у карт high имена получат «.001»
    mats = {"": FG.maps_material(setname, maps_dir, setname)}
    for g, kind in GLASS.items():
        if any(slot(h) == g for h in highs):
            mats[kind] = FG.maps_material(f"{setname}_{kind}", maps_dir, setname, glass=True)
    hmat = FG.maps_material(f"{setname}__high", f"{SRC}/{setname}", setname)
    for h in highs:
        h.data.materials.clear()
        h.data.materials.append(hmat)
    dec = DECIMATE.get(setname, {})
    parts = {}
    for h in highs:
        me = h.data.copy()
        me.materials.clear()
        me.materials.append(mats[GLASS.get(slot(h), "")])
        ob = bpy.data.objects.new(f"{setname}:{key(h)}", me)
        store.objects.link(ob)
        target = dec.get(key(h)) or dec.get(slot(h))
        if target:
            FG.decimate(ob, target)
        for p in ob.data.polygons:
            p.use_smooth = True
        parts[key(h)] = ob
    if dec:
        # нормаль упрощённых: запекание всей развёртки набора с high (на временной склейке копий)
        tmp = []
        for ob in parts.values():
            c = ob.copy()
            c.data = ob.data.copy()
            store.objects.link(c)
            tmp.append(c)
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for c in tmp:
            c.select_set(True)
        bpy.context.view_layer.objects.active = tmp[0]
        bpy.ops.object.join()
        low = tmp[0]
        nmap = f"{maps_dir}/{setname}_normal.png"
        bake_normal(low, highs, RES.get(setname, 512), nmap)
        bpy.data.objects.remove(low)
        img = bpy.data.images.get(f"{setname}_normal.png")
        if img is not None and img.filepath and os.path.normpath(bpy.path.abspath(img.filepath)) == os.path.normpath(nmap):
            img.reload()
    print("SET", setname, {k: FG.tris(o.data) for k, o in parts.items()}, flush=True)
    return parts


def bake_normal(low, highs, size: int, path: str) -> None:
    """Как у мебели (furniture_game.bake_normal), но с выносом лучей по мелкой электрике: 3 мм (у мебели — 0,8 %
    габарита: у проводов 1,5–2 м это 12–16 мм, луч ловил бы соседнюю жилу и гвоздик)."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    img = bpy.data.images.new(os.path.basename(path) + ".bake", size, size, alpha=False, float_buffer=False)
    img.generated_color = (0.5, 0.5, 1.0, 1.0)
    img.colorspace_settings.name = "Non-Color"
    for s in low.material_slots:
        nt = s.material.node_tree
        n = nt.nodes.new("ShaderNodeTexImage")
        n.name = "bake_target"
        n.image = img
        nt.nodes.active = n
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for h in highs:
        h.hide_set(False)
        h.hide_render = False
        h.select_set(True)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.003, max_ray_distance=0.009,
                        margin=8, use_clear=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    for s in low.material_slots:
        s.material.node_tree.nodes.remove(s.material.node_tree.nodes["bake_target"])
    bpy.data.images.remove(img)


def place(part, name: str, coll, m: Matrix = Matrix.Identity(4), parent=None, pivot: Matrix | None = None):
    """Копия детали в модель: вершины переводятся матрицей m; pivot — узел с осью в шарнире (вершины — в его осях)."""
    me = part.data.copy()
    me.transform(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if pivot is not None:
        me.transform(pivot.inverted())
        ob.matrix_world = pivot
    if parent is not None:
        ob.parent = parent
        ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob


def export(root, model: str) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{model}.gltf", export_format="GLTF_SEPARATE", export_texture_dir="textures",
                              use_selection=True, export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=90, export_cameras=False, export_lights=False, export_animations=False)


def gd(v) -> list[float]:
    """Точка Blender → оси Godot (y вверх, z = −y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def aabb(root) -> dict:
    pts = []
    for c in [root] + list(root.children_recursive):
        if c.type == "MESH":
            pts += [c.matrix_world @ v.co for v in c.data.vertices]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    glo, ghi = gd(lo), gd(hi)
    glo, ghi = [min(glo[i], ghi[i]) for i in range(3)], [max(glo[i], ghi[i]) for i in range(3)]
    return {"center": [round((glo[i] + ghi[i]) / 2, 4) for i in range(3)], "size": [round(ghi[i] - glo[i], 4) for i in range(3)]}


def main() -> None:
    os.makedirs(TEX, exist_ok=True)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    for c in top.children:
        c.hide_viewport = False
        c.hide_render = False
    store = bpy.data.collections.new("Игровые_детали")
    bpy.context.scene.collection.children.link(store)
    game = bpy.data.collections.new("Игровая_v01")
    bpy.context.scene.collection.children.link(game)
    P = {s: prepare_set(s, store) for s in [c.name for c in top.children]}
    variants = {s: variant_maps(s) for s in P}
    index = {}

    def model(name: str, kind: str, sets: list[str], build, **extra) -> None:
        root = bpy.data.objects.new(name, None)
        game.objects.link(root)
        build(root)
        export(root, name)
        tris = sum(FG.tris(c.data) for c in root.children_recursive if c.type == "MESH")
        index[name] = {"file": f"res://assets/models/dorm/electrics/{name}.gltf", "kind": kind, "triangles": tris,
                       "aabb": aabb(root), "sets": sets, **extra}
        print("MODEL", name, tris, flush=True)

    def add_set(root, s, skip=(), only=None, m=Matrix.Identity(4)):
        for k, ob in P[s].items():
            if k in skip or (only is not None and k not in only):
                continue
            place(ob, k, game, m, root)

    t = P["el_tube"]
    whole = ("Трубка_люминофор", "Цоколь_алюминий", "Штырьки_латунь")
    stub = tuple(k + "__обломок" for k in whole)

    def tube(root, m, tag):
        for k in whole:
            place(t[k], f"{k}_{tag}", game, m, root)

    # ЛСП: корпус и отражатель; трубки — две / целая и обломок / нет
    up = Matrix.Translation((0, 2 * TUBE_Y, 0))
    model("el_lsp_2", "ceiling", ["el_lsp", "el_tube"],
          lambda r: (add_set(r, "el_lsp"), tube(r, Matrix.Identity(4), "1"), tube(r, up, "2")), tubes=2)
    model("el_lsp_1", "ceiling", ["el_lsp", "el_tube"],
          lambda r: (add_set(r, "el_lsp"), tube(r, Matrix.Identity(4), "1"),
                     [place(t[k], k, game, Matrix.Identity(4), r) for k in stub]), tubes=1)
    model("el_lsp_0", "ceiling", ["el_lsp"], lambda r: add_set(r, "el_lsp"), tubes=0)

    # ЛПО: трубки — по их месту в форме (половины «ЛПО_трубки_закрыт» по знаку Y), рассеиватель — узел с осью в петле
    lpo_tubes, _ = root_local(bpy.data.objects["ЛПО_трубки_закрыт"])
    src_c = np.array([0.0, -TUBE_Y, (-0.1123 - 0.0718) / 2])
    shifts = []
    for sign in (-1, 1):
        half = lpo_tubes[np.sign(lpo_tubes[:, 1]) == sign]
        c = (half.min(0) + half.max(0)) / 2
        shifts.append(Matrix.Translation(V(c - src_c)))
    _, closed = root_local(bpy.data.objects["ЛПО_рассеиватель_закрыт"])
    _, hanging = root_local(bpy.data.objects["ЛПО_рассеиватель_висит"])
    diff_key = "Рассеиватель_опал__рассеиватель"

    def lpo(root, pose):
        add_set(root, "el_lpo", skip=(diff_key,))
        tube(root, shifts[0], "1")
        tube(root, shifts[1], "2")
        if pose is not None:
            d = place(P["el_lpo"][diff_key], "рассеиватель", game, Matrix.Identity(4), root, pivot=closed)
            d.matrix_world = pose
    model("el_lpo_closed", "ceiling", ["el_lpo", "el_tube"], lambda r: lpo(r, closed), tubes=2)
    model("el_lpo_hanging", "ceiling", ["el_lpo", "el_tube"], lambda r: lpo(r, hanging), tubes=2)
    model("el_lpo_torn", "ceiling", ["el_lpo", "el_tube"], lambda r: lpo(r, None), tubes=2)

    # лампа А60: в наборе — как в патроне на шнуре; в плафоне лежит — перенос по вершинам колбы обеих форм
    a, _ = root_local(bpy.data.objects["Патрон_лампа_лампа_колба"])
    b, _ = root_local(bpy.data.objects["Плафон_лампа_стекло_колба"])
    to_plafond = kabsch(a, b)
    bulb = ("Лампа_изолятор", "Лампа_стекло", "Нить_вольфрам", "Лампа_цоколь")
    broken_back = Matrix.Translation((-0.12, 0.0, 0.0))  # electrics_uv.OFFSETS: битая колба сдвинута на время текстур

    def lamp(root, m, broken=False):
        for k in bulb:
            if broken and k == "Лампа_стекло":
                place(P["el_bulb"]["Лампа_стекло__разбита"], "Лампа_стекло__разбита", game, m @ broken_back, root)
            else:
                place(P["el_bulb"][k], k, game, m, root)
    model("el_plafond_glass", "ceiling", ["el_plafond", "el_bulb"],
          lambda r: (add_set(r, "el_plafond"), lamp(r, to_plafond)))
    model("el_plafond_open", "ceiling", ["el_plafond", "el_bulb"],
          lambda r: (add_set(r, "el_plafond", skip=("Плафон_стекло",)), lamp(r, to_plafond)))
    model("el_pendant_bulb", "ceiling", ["el_pendant", "el_bulb"], lambda r: (add_set(r, "el_pendant"), lamp(r, Matrix.Identity(4))))
    model("el_pendant_broken", "ceiling", ["el_pendant", "el_bulb"],
          lambda r: (add_set(r, "el_pendant"), lamp(r, Matrix.Identity(4), broken=True)))
    model("el_pendant_empty", "ceiling", ["el_pendant"], lambda r: add_set(r, "el_pendant"))

    # настенное: рычажок и клавиша — узлы с осью в шарнире (поза формы: «вверх — включено»)
    _, lever = root_local(bpy.data.objects["ВК_круглый_рычажок"])
    _, key_m = root_local(bpy.data.objects["ВК_белый_клавиша"])

    def switch(root, s, mover, m):
        add_set(root, s, skip=(mover,))
        place(P[s][mover], mover.split("__")[1], game, Matrix.Identity(4), root, pivot=m)
    model("el_switch_round", "wall", ["el_switch_round"], lambda r: switch(r, "el_switch_round", "Карболит__рычажок", lever),
          mover={"node": "рычажок", "axis": "x", "on_deg": round(np.degrees(lever.to_euler().x), 2)})
    model("el_switch_white", "wall", ["el_switch_white"], lambda r: switch(r, "el_switch_white", "Пластик_белый__клавиша", key_m),
          mover={"node": "клавиша", "axis": "x", "on_deg": round(np.degrees(key_m.to_euler().x), 2)})
    for s in ("el_socket_round", "el_socket_white", "el_box"):
        model(s, "wall", [s], lambda r, s=s: add_set(r, s))

    # провода: модуль от начала (порт 0) — вдоль +X по стене (стена — плоскость y = 0, провод на −Y)
    w = P["el_wire_flat"]

    def wire_ports(prefix):
        pts = np.array([v.co for v in w[prefix].data.vertices])
        return pts

    straight = wire_ports("Провод_ПВХ__прямой_1м")
    s0 = V((0.0, 0.0, 0.0))
    fold = wire_ports("Провод_ПВХ__залом_вниз")
    f0 = V((fold[:, 0].min(), 0.0, 0.0))
    leg = fold[fold[:, 2] < -0.2]
    f1 = V((float((leg[:, 0].min() + leg[:, 0].max()) / 2), 0.0, float(fold[:, 2].min())))
    corner = wire_ports("Провод_ПВХ__стена_потолок")
    c0 = V((float((corner[:, 0].min() + corner[:, 0].max()) / 2), 0.0, float(corner[:, 2].min())))
    c1 = V((c0.x, float(corner[:, 1].min()), 0.0))

    def wire(root, tag, origin, cut=None):
        m = Matrix.Translation(-origin)
        for k, ob in w.items():
            if k.endswith("__" + tag):
                o = place(ob, k, game, m, root)
                if cut is not None:
                    bm = bmesh.new()
                    bm.from_mesh(o.data)
                    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=(cut, 0, 0),
                                           plane_no=(1, 0, 0), clear_outer=True)
                    bm.to_mesh(o.data)
                    bm.free()
    model("el_wire_1m", "wire", ["el_wire_flat"], lambda r: wire(r, "прямой_1м", s0),
          ports={"end": gd((1.0, 0, 0)), "out": gd((1, 0, 0))}, length=1.0)
    model("el_wire_05m", "wire", ["el_wire_flat"], lambda r: wire(r, "прямой_1м", s0, cut=0.5),
          ports={"end": gd((0.5, 0, 0)), "out": gd((1, 0, 0))}, length=0.5)
    model("el_wire_fold", "wire", ["el_wire_flat"], lambda r: wire(r, "залом_вниз", f0),
          ports={"end": gd(f1 - f0), "out": gd((0, 0, -1))})
    model("el_wire_ceiling", "wire", ["el_wire_flat"], lambda r: wire(r, "стена_потолок", c0),
          ports={"end": gd(c1 - c0), "out": gd((0, -1, 0))})
    model("el_wire_twisted", "wire", ["el_wire_twisted"], lambda r: add_set(r, "el_wire_twisted"), length=1.5)

    for name, info in index.items():
        info["variants"] = {s: variants[s] for s in info["sets"] if variants[s]}
    with open(f"{OUT}/electrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    store.hide_viewport = True
    out = bpy.data.filepath.replace("_uv_v01.blend", "_game_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
