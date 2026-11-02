"""Мебель общежития, партия 2 (кухня, умывальня, туалеты), игровые версии (навык godot-asset-preparation), бюджет
«средне, как электрика» (владелец 2026-11-02): карты износа этапа 2 уменьшены — крупное 1K, посуда, бидон и бак 512;
тяжёлые детали (конфорки, чаша мойки, фаянс, сиденье, посуда, бидон, бак) упрощены схлопыванием рёбер с той же
развёрткой, их рельеф запечён в нормаль набора (Cycles на процессоре). Подвижное — своими узлами с осью в шарнире
(дверцы и ящик тумб, дверца духовки, дверца кабинки, сиденье унитаза; оси и точки — из build_furniture2.py); варианты
формы — свои модели: отбитая раковина, унитаз без бачка, крайняя перегородка кабинок.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture2_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/furniture2_game.py [-- набор …]

→ assets/models/dorm/furniture/<модель>.gltf (+ textures/<набор>_*.webp, общие у моделей набора); варианты отделки —
textures/<набор>__<код>_*.webp (стенд подменяет ими карты материала набора; у упрощённых наборов нормаль варианта не
пишется — в нормали набора запечён рельеф); записи моделей — в общий furniture.json (material — набор, movers — узлы
с осью, оси Godot). Низкие сетки — копией рядом с исходником: RING_Dorm_Furniture2_game_v01.blend. Ступени детализации —
автоматические при импорте Godot; настройки карт — furniture_imports.py после первого --import.
"""
import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector as V

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import furniture_game as FG  # noqa: E402

ROOT = "E:/Games/RING-godot"
SRC = ROOT + "/_asset_src/dorm_furniture2/maps_worn"
GAME_MAPS = ROOT + "/_asset_src/dorm_furniture2/game_maps"
OUT = ROOT + "/assets/models/dorm/furniture"
TEX = OUT + "/textures"
# карты набора в игре (остальные — 1K)
RES = {"furn_pot": 512, "furn_kettle": 512, "furn_pan": 512, "furn_can": 512, "furn_bucket": 512}
# упрощение: набор → {слот[__метка]: треугольников}
DECIMATE = {"furn_stove": {"Конфорка_чугун": 2400},
            "furn_sink": {"Мойка_эмаль": 3200},
            "furn_basin": {"Фаянс": 2600, "Фаянс__отбита": 2700, "Хром": 1100},
            "furn_toilet": {"Фаянс": 3400, "Сиденье_пластик__сиденье": 1000},
            "furn_pot": {"Посуда_эмаль": 1400},
            "furn_kettle": {"Посуда_эмаль": 1000},
            "furn_can": {"Алюминий": 1400},
            "furn_bucket": {"Оцинковка": 1400}}
GLASS = ("Стекло",)
# сдвиги вариантов формы на время текстур (furniture2_uv.OFFSETS) — модели собираются в своих осях
OFFSETS = {"Фаянс__отбита": (0.8, 0.0, 0.0), "Труба_краска__оборвана": (0.6, 0.0, 0.0),
           "Перегородка_краска__крайняя": (1.0, 0.0, 0.0), "Сталь_окраска__крайняя": (1.0, 0.0, 0.0)}
# подвижное: набор → {метка узла: (вид, точка оси в осях набора, ось Blender)}; build_furniture2: hinged_doors —
# ось у наружной кромки дверцы (x_outer, y_face, z0), drawer — у лица ящика, плита — дверца духовки на петлях внизу
# (0, yf, 0,2), кабинка — петли у левой перегородки (hinge_x, −D − 0,002, 0,2), унитаз — шарниры сиденья сзади
DOORS = {"furn_sink": (0.398, -0.28, 0.082), "furn_counter": (0.398, -0.28, 0.082), "furn_wallcab": (0.398, -0.284, -0.597)}
MOVERS = {"furn_stove": {"дверца": ("hinge", (0.0, -0.28, 0.2), "X")},
          "furn_counter": {"ящик": ("slide", (0.0, -0.28, 0.67), "-Y")},
          "furn_stall": {"дверца": ("hinge", (-0.5335, -1.202, 0.2), "Z")},
          "furn_toilet": {"сиденье": ("hinge", (0.0, -0.105, 0.418), "-X")}}
for _s, (_x, _y, _z) in DOORS.items():
    MOVERS.setdefault(_s, {})
    MOVERS[_s]["дверца_лев"] = ("hinge", (-_x, _y, _z), "-Z")
    MOVERS[_s]["дверца_прав"] = ("hinge", (_x, _y, _z), "Z")
# коробки столкновений по доскам (у кабинок коробка по габариту корпуса закрыла бы вход внутрь): модель → слот досок
COLLIDE = {"furn_stall": "Перегородка_краска", "furn_stall_end": "Перегородка_краска"}
TANK_Z = 1.805  # низ бачка (build_furniture2.toilet: z0 = 1,8) — у сорванного остаются только кронштейны ниже


def key(ob) -> str:
    return ob.name.split(".")[0]


def slot(k: str) -> str:
    return k.split("__")[0]


def tag(k: str) -> str:
    return k.split("__")[1] if "__" in k else ""


def resized(src: str, dst: str, res: int, non_color: bool, fmt: str = "PNG") -> None:
    img = bpy.data.images.load(src, check_existing=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    _ = img.pixels[0]  # картинка грузится лениво — без данных save() не пишет
    if img.size[0] != res:
        img.scale(res, res)
    img.filepath_raw = dst
    img.file_format = fmt
    img.save()
    bpy.data.images.remove(img)


def game_maps(s: str) -> str:
    out = f"{GAME_MAPS}/{s}"
    os.makedirs(out, exist_ok=True)
    for suffix, nc in (("baseColor", False), ("occlusionRoughnessMetallic", True), ("normal", True)):
        resized(f"{SRC}/{s}/{s}_{suffix}.png", f"{out}/{s}_{suffix}.png", RES.get(s, 1024), nc)
    return out


def variant_maps(s: str, with_normal: bool) -> list[str]:
    codes = []
    for d in sorted(os.listdir(SRC)):
        if not d.startswith(s + "__"):
            continue
        code = d.split("__", 1)[1]
        chans = [("baseColor", False), ("occlusionRoughnessMetallic", True)] + ([("normal", True)] if with_normal else [])
        for suffix, nc in chans:
            resized(f"{SRC}/{d}/{s}_{suffix}.png", f"{TEX}/{s}__{code}_{suffix}.webp", RES.get(s, 1024), nc, "WEBP")
        codes.append(code)
    return codes


def bake_normal(low, highs, size: int, path: str) -> None:
    """Нормаль упрощённых с high (карта Painter в материале high); вынос лучей 5 мм — у мебели 0,8 % габарита давало
    у унитаза с бачком 17 мм и ловило соседние детали."""
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
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=0.005, max_ray_distance=0.015,
                        margin=8, use_clear=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    for s in low.material_slots:
        s.material.node_tree.nodes.remove(s.material.node_tree.nodes["bake_target"])
    bpy.data.images.remove(img)


def prepare_set(s: str, store) -> dict:
    """Низкие детали набора (по ключу «слот[__метка]», в осях набора, как в развёртке) с материалами из карт игры;
    упрощённые — нормаль набора запечена с high."""
    coll = bpy.data.collections[s]
    highs = [o for o in coll.objects if o.type == "MESH"]
    for h in highs:
        h.matrix_world = Matrix.Identity(4)
    maps_dir = game_maps(s)
    # карты игры грузятся первыми: экспорт называет файлы по имени картинки, у карт high имена получат «.001»
    mats = {"": FG.maps_material(s, maps_dir, s)}
    if any(slot(key(h)) in GLASS for h in highs):
        mats["glass"] = FG.maps_material(f"{s}_стекло", maps_dir, s, glass=True)
    hmat = FG.maps_material(f"{s}__high", f"{SRC}/{s}", s)
    for h in highs:
        h.data.materials.clear()
        h.data.materials.append(hmat)
    dec = DECIMATE.get(s, {})
    parts = {}
    for h in highs:
        k = key(h)
        me = h.data.copy()
        me.materials.clear()
        me.materials.append(mats["glass" if slot(k) in GLASS else ""])
        ob = bpy.data.objects.new(f"{s}:{k}", me)
        store.objects.link(ob)
        if k in dec:
            FG.decimate(ob, dec[k])
        for p in ob.data.polygons:
            p.use_smooth = True
        ob.data.set_sharp_from_angle(angle=math.radians(60))  # бинормаль Godot — в вершинах: круче 60° — жёстко
        parts[k] = ob
    if dec:
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
        nmap = f"{maps_dir}/{s}_normal.png"
        bake_normal(low, highs, RES.get(s, 1024), nmap)
        bpy.data.objects.remove(low)
        img = bpy.data.images.get(f"{s}_normal.png")
        if img is not None and img.filepath and os.path.normpath(bpy.path.abspath(img.filepath)) == os.path.normpath(nmap):
            img.reload()
    for h in highs:
        h.hide_render = True
        h.hide_set(True)
    print("SET", s, {k: FG.tris(o.data) for k, o in parts.items()}, flush=True)
    return parts


def gd(v) -> list[float]:
    """Точка Blender → оси Godot (y вверх, z = −y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


# ось узла — так, чтобы положительный угол открывал: дверцы — наружу (левая — вокруг −Z), дверца духовки — вниз,
# дверца кабинки — внутрь, сиденье — вверх (вокруг −X); ящик выдвигается вперёд (Blender −Y)
GD_AXIS = {"X": [1, 0, 0], "-X": [-1, 0, 0], "Y": [0, 0, -1], "-Y": [0, 0, 1], "Z": [0, 1, 0], "-Z": [0, -1, 0]}


def mesh_from(parts: list, name: str, coll, parent, pivot: V | None = None):
    """Склейка сеток деталей в одну сетку узла (материалы — общим списком); pivot — узел с осью в шарнире, вершины —
    в его осях."""
    bm = bmesh.new()
    mats = []
    for me in parts:
        for mt in me.materials:
            if mt not in mats:
                mats.append(mt)
        remap = [mats.index(mt) for mt in me.materials]
        start = len(bm.faces)
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        for f in list(bm.faces)[start:]:
            f.material_index = remap[f.material_index] if f.material_index < len(remap) else 0
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    if pivot is not None:
        me.transform(Matrix.Translation(-pivot))
        ob.location = pivot
    ob.parent = parent
    ob.matrix_parent_inverse = Matrix.Identity(4)
    return ob


def unshift(k: str) -> Matrix:
    return Matrix.Translation(-V(OFFSETS.get(k, (0.0, 0.0, 0.0))))


def components(me) -> list:
    """Связные куски сетки — списки координат вершин."""
    bm = bmesh.new()
    bm.from_mesh(me)
    seen, out = set(), []
    for v0 in bm.verts:
        if v0.index in seen:
            continue
        stack, comp = [v0], []
        seen.add(v0.index)
        while stack:
            v = stack.pop()
            comp.append(v.co.copy())
            for e in v.link_edges:
                w = e.other_vert(v)
                if w.index not in seen:
                    seen.add(w.index)
                    stack.append(w)
        out.append(comp)
    bm.free()
    return out


def tank_free(ob):
    """Чугун унитаза без бачка и рычага: только кронштейны (связные куски ниже низа бачка)."""
    c = ob.copy()
    c.data = ob.data.copy()
    bm = bmesh.new()
    bm.from_mesh(c.data)
    seen, drop = set(), []
    for f0 in bm.faces:
        if f0.index in seen:
            continue
        stack, comp = [f0], []
        seen.add(f0.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        if max(v.co.z for f in comp for v in f.verts) > TANK_Z:
            drop += comp
    bmesh.ops.delete(bm, geom=list(set(drop)), context="FACES")
    bm.to_mesh(c.data)
    bm.free()
    return c


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


def aabb(root) -> dict:
    pts = []
    for c in root.children_recursive:
        if c.type == "MESH":
            pts += [c.matrix_world @ v.co for v in c.data.vertices]
    glo = gd([min(p[i] for p in pts) for i in range(3)])
    ghi = gd([max(p[i] for p in pts) for i in range(3)])
    lo, hi = [min(glo[i], ghi[i]) for i in range(3)], [max(glo[i], ghi[i]) for i in range(3)]
    return {"center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)], "size": [round(hi[i] - lo[i], 4) for i in range(3)]}


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
    only = set(sys.argv[sys.argv.index("--") + 1:]) if "--" in sys.argv else set()
    sets = [c.name for c in top.children if not only or c.name in only]
    P = {s: prepare_set(s, store) for s in sets}
    variants = {s: variant_maps(s, with_normal=s not in DECIMATE) for s in sets}
    idx_path = f"{OUT}/furniture.json"
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}

    def model(name: str, s: str, keys: list[str], extra=None) -> None:
        """Модель из деталей набора: неподвижное — одной сеткой «корпус», подвижное — узлами по метке с осью."""
        root = bpy.data.objects.new(name, None)
        game.objects.link(root)
        movers = MOVERS.get(s, {})
        body, nodes = [], {}
        for k in keys:
            t = tag(k)
            (nodes.setdefault(t, []) if t in movers else body).append(k)
        info_movers = []

        def build(ks, node_name, pivot=None):
            mes = []
            for k in ks:
                me = (extra[k] if extra and k in extra else P[s][k]).data.copy()
                me.transform(unshift(k))
                mes.append(me)
            out = mesh_from(mes, node_name, game, root, pivot)
            for me in mes:
                bpy.data.meshes.remove(me)
            return out

        build(body, f"{name}_корпус")
        for t, ks in nodes.items():
            kind, at, axis = movers[t]
            build(ks, t, V(at))
            info_movers.append({"node": t, "kind": kind, "pivot": gd(at), "axis": GD_AXIS[axis]})
        colliders = []
        for k in keys if name in COLLIDE else []:
            if slot(k) != COLLIDE[name]:
                continue
            me = P[s][k].data.copy()
            me.transform(unshift(k))
            t = tag(k) if tag(k) in movers else ""
            at = V(movers[t][1]) if t else V((0, 0, 0))
            for comp in components(me):
                lo = V([min(c[i] for c in comp) for i in range(3)]) - at
                hi = V([max(c[i] for c in comp) for i in range(3)]) - at
                size = hi - lo
                colliders.append({"node": t, "center": gd((lo + hi) / 2), "size": [round(size.x, 4), round(size.z, 4),
                                                                                 round(size.y, 4)]})
            bpy.data.meshes.remove(me)
        export(root, name)
        tris = sum(FG.tris(c.data) for c in root.children_recursive if c.type == "MESH")
        index[name] = {"file": f"res://assets/models/dorm/furniture/{name}.gltf", "triangles": tris, "aabb": aabb(root),
                       "material": s, "variants": variants[s]}
        if info_movers:
            index[name]["movers"] = info_movers
        if colliders:
            index[name]["colliders"] = colliders
        # имена узлов свободны для следующей модели (иначе Blender даёт «дверца_лев.001», и стенд узел не найдёт)
        for c in root.children:
            c.name = f"{name}:{c.name}"
        print("MODEL", name, tris, [m["node"] for m in info_movers], len(colliders), flush=True)

    def all_but(s, *drop):
        return [k for k in P[s] if k not in drop]

    for s in sets:
        if s == "furn_basin":
            model("furn_basin", s, all_but(s, "Фаянс__отбита"))
            model("furn_basin_broken", s, all_but(s, "Фаянс"))
        elif s == "furn_toilet":
            model("furn_toilet", s, all_but(s, "Труба_краска__оборвана"))
            brackets = tank_free(P[s]["Чугун_окраска"])
            store.objects.link(brackets)
            model("furn_toilet_torn", s, ["Фаянс", "Чугун_окраска", "Труба_краска__оборвана"],
                  extra={"Чугун_окраска": brackets})
        elif s == "furn_stall":
            model("furn_stall", s, [k for k in P[s] if not k.endswith("__крайняя")])
            model("furn_stall_end", s, [k for k in P[s] if k.endswith("__крайняя")])
        else:
            model(s, s, list(P[s]))
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
