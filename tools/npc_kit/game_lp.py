"""NPC «мародёр» v03 — игровая версия: ретопология LOD0, развёртка, запекание карт с принятого исходника.

Решения владельца 2026-10-22: «с ретопологии всего, начиная с персонажа»; бюджет — 60 тыс. треугольников на NPC
в полном снаряжении (тело с одеждой ~25 тыс.), три LOD, одежда 2K, остальное 1K; скелет — `mixamorig_*` (как у
Persona: клипы, BodyMotion, ИК рук и сокеты оружия переходят без переделки).

Исходник не трогается: `npc_scav_v03_tex.blend` → `_asset_src/npc_kit/game/npc_scav_v03_game.blend`.
- куртка, брюки — QuadriFlow (ровные четырёхугольники по принятой форме, края сохранены), прижаты к исходнику;
  у открытых краёв куртки — отворот внутрь: толщина и изнанка видны в проёмах;
- брюки: под курткой и в ботинках скрытая часть убрана с запасом на движение; карманы — упрощены, на атласе брюк;
- балаклава и ботинки — упрощением (QuadriFlow их не берёт): ботинок — оболочкой всех деталей вокселями
  (шнурки, люверсы, рант — в карты), правый — зеркало левого и та же карта;
- тело — кисти и лицо у прорези балаклавы (скрытое балаклавой и курткой убрано, у краёв — запас);
- молния куртки, шнурки, строчка, складки мельче сетки — запеканием.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/game_lp.py -- [lp] [uv] [bake] [lods] [deliver=<папка>]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "game"
GAME = OUT / f"npc_scav_{kc.VERSION}_game.blend"
COL = "GAME_LOD0"
# игровая деталь: (источники в исходнике, размер карты, луч запекания м)
PARTS = {
    "G_Jacket": (("Jacket", "Jacket_Zipper"), 2048, 0.020),
    "G_Pants": (("Pants", "Pants_Pocket_L", "Pants_Pocket_R"), 2048, 0.015),
    "G_Balaclava": (("Balaclava", "Balaclava_SlotRim"), 1024, 0.010),
    "G_Boot": (("Boots_L",), 1024, 0.012),
    "G_Body": (("NPC_Body",), 1024, 0.012),
}
TARGET = {"Jacket": 3300, "Pants": 1900}          # QuadriFlow, четырёхугольников
TRIS = {"Balaclava": 2600, "Balaclava_SlotRim": 480, "Boot": 1600, "Pocket": 160, "Body": 4600}


def dup(src: bpy.types.Object, name: str, col: bpy.types.Collection, keep_mods: bool = False) -> bpy.types.Object:
    o = src.copy()
    o.data = src.data.copy()
    o.name = name
    o.data.name = name
    o.parent = None
    o.matrix_world = src.matrix_world.copy()
    col.objects.link(o)
    if not keep_mods:
        for m in list(o.modifiers):
            o.modifiers.remove(m)
    o.hide_render = o.hide_viewport = False
    o.hide_set(False)
    return o


def apply_mods(o: bpy.types.Object) -> None:
    kc.make_active(o)
    for m in list(o.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def quadriflow(o: bpy.types.Object, faces: int) -> None:
    kc.make_active(o)
    r = bpy.ops.object.quadriflow_remesh(use_mesh_symmetry=False, use_preserve_sharp=False, use_preserve_boundary=True,
                                         preserve_attributes=False, smooth_normals=False, mode="FACES",
                                         target_faces=faces, seed=0)
    assert r == {"FINISHED"}, f"QuadriFlow не взял {o.name}"


def decimate_to(o: bpy.types.Object, tris: int) -> None:
    n = sum(len(p.vertices) - 2 for p in o.data.polygons)
    if n <= tris:
        return
    m = o.modifiers.new("Dec", "DECIMATE")
    m.decimate_type = "COLLAPSE"
    m.ratio = tris / n
    apply_mods(o)


def snap_to(o: bpy.types.Object, target: bpy.types.Object) -> None:
    m = o.modifiers.new("Snap", "SHRINKWRAP")
    m.target = target
    m.wrap_method = "NEAREST_SURFACEPOINT"
    apply_mods(o)


def bvh_world(objs: list[bpy.types.Object]) -> BVHTree:
    dg = bpy.context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in objs:
        tmp = bmesh.new()
        tmp.from_object(o, dg)
        tmp.transform(o.matrix_world)
        me = bpy.data.meshes.new("_tmp")
        tmp.to_mesh(me)
        tmp.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    out = BVHTree.FromBMesh(bm)
    bm.free()
    return out


def lip(o: bpy.types.Object, depth: float, width: float, only=None) -> int:
    """Отворот по открытым краям: кромка толщиной depth и полоса изнанки шириной width внутрь по ткани
    (в проёме рукава и подола видна изнанка, а не пустота). Возвращает число новых граней."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    edges = [e for e in bm.edges if e.is_boundary and (only is None or all(only(v.co) for v in e.verts))]
    rim, inner = {}, {}
    for e in edges:
        for v in e.verts:
            if v in rim:
                continue
            n = v.normal
            into = Vector()
            for le in v.link_edges:
                if not le.is_boundary:
                    d = le.other_vert(v).co - v.co
                    into += d - n * d.dot(n)
            into = into.normalized() if into.length > 1e-9 else -n
            rim[v] = bm.verts.new(v.co - n * depth)
            inner[v] = bm.verts.new(v.co - n * depth + into * width)
    made = 0
    for e in edges:
        a, b = e.verts
        f = e.link_faces[0]
        # порядок обхода как у соседней грани — согласованные нормали
        la = next(lp for lp in f.loops if lp.vert == a)
        if la.link_loop_next.vert != b:
            a, b = b, a
        for quad in ((b, a, rim[a], rim[b]), (rim[b], rim[a], inner[a], inner[b])):
            try:
                bm.faces.new(quad)
                made += 1
            except ValueError:
                pass
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()
    return made


def delete_faces(o: bpy.types.Object, test) -> int:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    mw = o.matrix_world
    dead = [f for f in bm.faces if test(f, mw)]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    return len(dead)


def largest_part(o: bpy.types.Object) -> None:
    bm = bmesh.new()
    bm.from_mesh(o.data)
    seen, parts = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        comp, stack = [], [f]
        seen.add(f)
        while stack:
            g = stack.pop()
            comp.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h not in seen:
                        seen.add(h)
                        stack.append(h)
        parts.append(comp)
    parts.sort(key=len, reverse=True)
    dead = [f for comp in parts[1:] for f in comp]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bm.to_mesh(o.data)
    bm.free()


def drop_materials(o: bpy.types.Object, keys: tuple[str, ...]) -> int:
    idx = {i for i, m in enumerate(o.data.materials) if m and any(k in m.name for k in keys)}
    bm = bmesh.new()
    bm.from_mesh(o.data)
    dead = [f for f in bm.faces if f.material_index in idx]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    return len(dead)


def drop_hidden(o: bpy.types.Object, reach: float = 0.12, share: float = 0.97) -> int:
    """Грани, которых не видно снаружи: из центра грани лучи по полусфере над ней почти все (share) упираются
    в свою же сетку — это подкладка и полости, а не наружная поверхность."""
    n_dirs = 48
    golden = math.pi * (3.0 - math.sqrt(5.0))
    dirs = []
    for i in range(n_dirs):
        z = 1.0 - 2.0 * (i + 0.5) / n_dirs
        r = math.sqrt(1.0 - z * z)
        dirs.append(Vector((math.cos(golden * i) * r, math.sin(golden * i) * r, z)))
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    dead = []
    for f in bm.faces:
        c = f.calc_center_median() + f.normal * 1e-4
        ds = [d for d in dirs if d.dot(f.normal) > 0.2]
        hits = sum(1 for d in ds if tree.ray_cast(c, d, reach)[0] is not None)
        if ds and hits >= share * len(ds):
            dead.append(f)
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    return len(dead)


def drop_inner(o: bpy.types.Object, near: float = 0.02, far: float = 0.15) -> int:
    """Изнанка вокселей (внутренняя стенка голенища, полость стопы): луч по нормали упирается в свою же сетку
    дальше near — грань смотрит в полость. Без неё упрощение сводило стенки, и они проходили друг сквозь друга."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    inner = []
    for f in bm.faces:
        c = f.calc_center_median()
        hit = tree.ray_cast(c + f.normal * 1e-4, f.normal, far)
        if hit[0] is not None and hit[3] > near:
            inner.append(f)
    bmesh.ops.delete(bm, geom=inner, context="FACES")
    bm.to_mesh(o.data)
    bm.free()
    return len(inner)


def tris(o: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def stage_lp() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(kc.npc_file()))
    col = kc.collection(COL)
    src = bpy.data.objects
    work = kc.collection("GAME_work")
    # куртка: QuadriFlow по поверхности (без толщины), прижать к ней, отворот у краёв
    jk_base = dup(src["Jacket"], "W_Jacket_base", work)
    jk = dup(src["Jacket"], "G_Jacket", col)
    quadriflow(jk, TARGET["Jacket"])
    snap_to(jk, jk_base)
    kc.log("  куртка: отворот", lip(jk, 0.0025, 0.022), "граней")
    # брюки: QuadriFlow, скрытое под курткой и в ботинках — прочь (запас на движение)
    pt_base = dup(src["Pants"], "W_Pants_base", work)
    pt = dup(src["Pants"], "G_Pants", col)
    quadriflow(pt, TARGET["Pants"])
    snap_to(pt, pt_base)
    hem = min((src["Jacket"].matrix_world @ v.co).z for v in src["Jacket"].data.vertices)
    boot_top = max((src["Boots_L"].matrix_world @ v.co).z for v in src["Boots_L"].data.vertices)
    cut_hi, cut_lo = hem + 0.08, boot_top - 0.06
    gone = delete_faces(pt, lambda f, mw: all((mw @ v.co).z > cut_hi or (mw @ v.co).z < cut_lo for v in f.verts))
    kc.log(f"  брюки: низ куртки {hem:.3f}, верх ботинка {boot_top:.3f} — убрано {gone} граней")
    for side in ("L", "R"):
        pk = dup(src[f"Pants_Pocket_{side}"], f"W_Pocket_{side}", col, keep_mods=True)
        apply_mods(pk)
        decimate_to(pk, TRIS["Pocket"] * 2)
        kc.make_active(pt)
        pk.select_set(True)
        bpy.ops.object.join()
    # балаклава и валик прорези
    bl = dup(src["Balaclava"], "G_Balaclava", col)
    decimate_to(bl, TRIS["Balaclava"])
    rim = dup(src["Balaclava_SlotRim"], "W_SlotRim", col)
    decimate_to(rim, TRIS["Balaclava_SlotRim"])
    kc.make_active(bl)
    rim.select_set(True)
    bpy.ops.object.join()
    # ботинок — наружная оболочка из boots.blend (Boots_L_Outer — столкновитель брюк при симуляции: без изнанки и слоёв).
    # Из самого ботинка (воксели, отсев изнанки, выпуклая оболочка) выходили дыры и «сколы»: подкладка голенища
    # и резиновый носок поверх кожи — тонкие слои, упрощение сводило их друг сквозь друга. Шнурки, люверсы, рант — в карты
    with bpy.data.libraries.load(str(kc.WORK / "boots" / "boots.blend")) as (src_lib, dst_lib):
        dst_lib.objects = ["Boots_L_Outer"]
    outer = dst_lib.objects[0]
    bt = dup(outer, "G_Boot", col)
    bpy.data.objects.remove(outer)
    for vg in list(bt.vertex_groups):
        bt.vertex_groups.remove(vg)
    decimate_to(bt, TRIS["Boot"] - 450)
    top = max((bt.matrix_world @ v.co).z for v in bt.data.vertices)
    kc.log("  ботинок: отворот голенища", lip(bt, 0.003, 0.02, only=lambda co: co.z > top - 0.05), "граней")
    # подошва (у оболочки её нет) — из ботинка, отдельно упрощённая
    sole = dup(src["Boots_L"], "W_Sole", col, keep_mods=True)
    apply_mods(sole)
    drop_materials(sole, ("Leather", "Mesh", "Rubber", "Metal", "Lace"))
    decimate_to(sole, 450)
    kc.make_active(bt)
    sole.select_set(True)
    bpy.ops.object.join()
    # тело: что под балаклавой и курткой — убрать, у краёв запас (голова и кисть двигаются внутри). На голове луч —
    # от её центра: у рта и глазниц грани смотрят внутрь головы, луч по нормали уходил мимо балаклавы
    body = dup(src["NPC_Body"], "G_Body", col)
    cover = bvh_world([src["Balaclava"], src["Balaclava_SlotRim"], src["Jacket"]])
    cover_lp = bvh_world([bl, src["Jacket"]])      # упрощённая балаклава в прорези открывает чуть больше
    head_pts = [body.matrix_world @ v.co for v in body.data.vertices if (body.matrix_world @ v.co).z > 1.50]
    head_c = sum(head_pts, Vector()) / len(head_pts)

    mw = body.matrix_world
    eye_z = 1.58                                    # ниже прорези балаклавы — только кисти

    def hidden(f) -> bool:
        c = mw @ f.calc_center_median()
        if c.z >= eye_z:
            d = (c - head_c).normalized()
            return cover.ray_cast(c, d, 0.08)[0] is not None and cover_lp.ray_cast(c, d, 0.08)[0] is not None
        n = (mw.to_3x3() @ f.normal).normalized()
        return cover.ray_cast(c + n * 0.0005, n, 0.035)[0] is not None
    bm = bmesh.new()
    bm.from_mesh(body.data)
    # шея, рот, подбородок, плечи — всегда под балаклавой и курткой (лучи туда уходили мимо — оставались лишними)
    forced = {f for f in bm.faces if (mw @ f.calc_center_median()).z < eye_z and abs((mw @ f.calc_center_median()).x) < 0.40}
    hid = {f for f in bm.faces if f not in forced and hidden(f)}
    for i in range(6):            # запас у видимого края: кисти — 3 полосы, лицо — 6 (край прорези упрощённой балаклавы)
        keep = {f for f in hid if any(h not in hid and h not in forced for e in f.edges for h in e.link_faces)
                and (i < 3 or (mw @ f.calc_center_median()).z >= eye_z)}
        hid -= keep
    bmesh.ops.delete(bm, geom=list(hid | forced), context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(body.data)
    bm.free()
    decimate_to(body, TRIS["Body"])                      # кисти MakeHuman плотные (по 3,3 тыс. на кисть)
    eyes = dup(src["NPC_Eyes"], "G_Eyes", col)            # без упрощения: оно портило развёртку глаза (радужка «плыла»)
    lashes = dup(src["NPC_Eyelashes"], "G_Eyelashes", col)
    for o in (eyes, lashes):
        o.data.materials.clear()
    total = 0
    for o in col.objects:
        # гладкое затенение: с плоским (наследовалось от исходника) карта нормалей ломалась на каждой грани — огранка
        o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
        if "sharp_face" in o.data.attributes:
            o.data.attributes.remove(o.data.attributes["sharp_face"])
        o.data.update()
        kc.log(f"  {o.name}: {tris(o)} треугольников")
        total += tris(o)
    kc.log(f"LOD0 тело с одеждой: {total} треугольников (бюджет ~25 тыс.)")
    for o in work.objects:
        o.hide_render = True
        o.hide_set(True)
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(GAME)


AXES = [Vector(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
CELL = 0.22                                  # остров не больше клетки 22 см


def unwrap(o: bpy.types.Object, size: int) -> None:
    """Своя развёртка игровой детали под её карту. smart_project на куртке ломается (длинные узкие полосы — кант,
    желобок молнии, отворот — упаковка сжимала всё в полоску 0,04 ширины), поэтому швы — по шести направлениям
    нормали и клеткам 22 см, развёртка по углам (без растяжения), одинаковая плотность, поля ~6 пикселей."""
    kc.make_active(o)
    bm = bmesh.new()                       # вырожденные грани (нулевой площади) — прочь
    bm.from_mesh(o.data)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-5)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_area() < 1e-9], context="FACES")
    bm.normal_update()
    key = {f: (max(range(6), key=lambda k: f.normal.dot(AXES[k])),)
           + tuple(int(math.floor(c / CELL)) for c in f.calc_center_median()) for f in bm.faces}
    for e in bm.edges:
        lf = e.link_faces
        e.seam = len(lf) != 2 or key[lf[0]] != key[lf[1]]
    bm.to_mesh(o.data)
    bm.free()
    for u in list(o.data.uv_layers):
        o.data.uv_layers.remove(u)
    o.data.uv_layers.new(name="UV")
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    margin = 6.0 / size
    bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=margin)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(rotate=True, margin=margin)
    bpy.ops.object.mode_set(mode="OBJECT")
    uv = o.data.uv_layers["UV"].data
    us = [d.uv.x for d in uv]
    vs = [d.uv.y for d in uv]
    kc.log(f"    {o.name}: развёртка {min(us):.2f}…{max(us):.2f} × {min(vs):.2f}…{max(vs):.2f}")


def stage_uv() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(GAME))
    col = bpy.data.collections[COL]
    for name, (_, size, _) in PARTS.items():
        unwrap(bpy.data.objects[name], size)
        kc.log("  развёртка", name, size)
    # правый ботинок — зеркало левого: та же развёртка и карта (исходные ботинки зеркальны с точностью до 0)
    left = bpy.data.objects["G_Boot"]
    right = dup(left, "G_Boot_R", col)
    right.data.transform(__import__("mathutils").Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0)))
    right.data.flip_normals()
    right.data.update()
    kc.save(GAME)


SAMPLES = {"color": 16, "mrh": 16, "normal": 16, "ao": 64}
MAPS = OUT / "maps"


def route(channel: str, saved: dict) -> None:
    """Канал стека исходника → Emission (запекание EMIT); normal — обратно BSDF (как tools/pm_worn/bake.py)."""
    def src_of(nt, inp_name):
        p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if p is None:
            return None, 0.0
        inp = p.inputs[inp_name]
        return (inp.links[0].from_socket, None) if inp.links else (None, inp.default_value)

    def feed(nt, sock_in, src) -> None:
        sock, value = src
        for lk in list(sock_in.links):
            nt.links.remove(lk)
        if sock is not None:
            nt.links.new(sock, sock_in)
        elif hasattr(value, "__len__"):
            sock_in.default_value = value
        else:
            sock_in.default_value = (value, value, value, 1) if sock_in.type == "RGBA" else value
    for m in bpy.data.materials:
        if m.name.startswith("GAME_") or m.node_tree is None:
            continue
        nt = m.node_tree
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
        if out is None:
            continue
        if m.name not in saved:
            lk = out.inputs["Surface"].links[0] if out.inputs["Surface"].links else None
            saved[m.name] = lk.from_socket if lk else None
        if channel == "normal":
            if saved[m.name] is not None:
                nt.links.new(saved[m.name], out.inputs["Surface"])
            continue
        emit = nt.nodes.get("BAKE_EMIT") or nt.nodes.new("ShaderNodeEmission")
        emit.name = "BAKE_EMIT"
        emit.inputs["Strength"].default_value = 1.0
        if channel == "color":
            feed(nt, emit.inputs["Color"], src_of(nt, "Base Color"))
        else:
            comb = nt.nodes.get("BAKE_COMB") or nt.nodes.new("ShaderNodeCombineColor")
            comb.name = "BAKE_COMB"
            feed(nt, comb.inputs["Red"], src_of(nt, "Metallic"))
            feed(nt, comb.inputs["Green"], src_of(nt, "Roughness"))
            comb.inputs["Blue"].default_value = 1.0
            for lk in list(emit.inputs["Color"].links):
                nt.links.remove(lk)
            nt.links.new(comb.outputs["Color"], emit.inputs["Color"])
        nt.links.new(emit.outputs[0], out.inputs["Surface"])


def game_material(o: bpy.types.Object) -> bpy.types.Material:
    m = bpy.data.materials.get("GAME_" + o.name) or bpy.data.materials.new("GAME_" + o.name)
    m.use_nodes = True
    o.data.materials.clear()
    o.data.materials.append(m)
    return m


def bake_target(m: bpy.types.Material, im: bpy.types.Image) -> None:
    nt = m.node_tree
    node = nt.nodes.get("BAKE_TARGET") or nt.nodes.new("ShaderNodeTexImage")
    node.name = "BAKE_TARGET"
    node.image = im
    nt.nodes.active = node


def stage_bake() -> None:
    import ucup  # noqa: F401  (стеки UCUPaint исходника)
    bpy.ops.wm.open_mainfile(filepath=str(GAME))
    S = bpy.context.scene
    kc.gpu_cycles(16)
    bk = S.render.bake
    bk.margin_type = "EXTEND"
    bk.normal_space = "TANGENT"
    lows = [bpy.data.objects[n] for n in PARTS]
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.hide_render = False
    images: dict[tuple[str, str], bpy.types.Image] = {}
    mats = {o.name: game_material(o) for o in lows}
    bpy.data.objects["G_Boot_R"].data.materials.clear()
    bpy.data.objects["G_Boot_R"].data.materials.append(mats["G_Boot"])
    saved: dict = {}
    for ch in ("mrh", "color", "normal"):
        route(ch, saved)
        for o in lows:
            srcs, size, ray = PARTS[o.name]
            im = bpy.data.images.new(f"{o.name}_{ch}", size, size, alpha=False, float_buffer=(ch == "normal"))
            im.colorspace_settings.name = "sRGB" if ch == "color" else "Non-Color"
            images[(o.name, ch)] = im
            bake_target(mats[o.name], im)
            bpy.ops.object.select_all(action="DESELECT")
            for s in srcs:
                so = bpy.data.objects[s]
                so.hide_set(False)
                so.select_set(True)
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            S.cycles.samples = SAMPLES[ch]
            bpy.ops.object.bake(type="NORMAL" if ch == "normal" else "EMIT", use_selected_to_active=True,
                                cage_extrusion=ray * 0.6, max_ray_distance=ray * 1.6, margin=max(4, size // 256))
            kc.log("  запечено", o.name, ch, "←", ", ".join(srcs))
    route("normal", saved)
    # AO — по самой игровой сетке (касания одежды, тени под воротом и в складках); исходники не участвуют
    highs = [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("G_")]
    for o in highs:
        o.hide_render = True
    S.world = S.world or bpy.data.worlds.new("AO")
    S.world.light_settings.distance = 0.08
    for o in lows:
        size = PARTS[o.name][1]
        im = bpy.data.images.new(f"{o.name}_ao", size, size, alpha=False)
        im.colorspace_settings.name = "Non-Color"
        images[(o.name, "ao")] = im
        bake_target(mats[o.name], im)
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        S.cycles.samples = SAMPLES["ao"]
        bpy.ops.object.bake(type="AO", use_selected_to_active=False, margin=max(4, size // 256))
        kc.log("  AO", o.name)
    MAPS.mkdir(parents=True, exist_ok=True)
    import numpy as np
    for o in lows:
        size = PARTS[o.name][1]
        px = {}
        for ch in ("color", "normal", "mrh", "ao"):
            a = np.empty(size * size * 4, np.float32)
            images[(o.name, ch)].pixels.foreach_get(a)
            px[ch] = a.reshape(size, size, 4)
        # нормали «внутрь» (луч попал в изнанку тонкой оболочки — язычок, шнурки, веко): чёрные пятна — ровными
        n = px["normal"][..., :3] * 2.0 - 1.0
        bad = n[..., 2] < 0.25
        px["normal"][bad, :3] = (0.5, 0.5, 1.0)
        images[(o.name, "normal")].pixels.foreach_set(px["normal"].ravel())
        kc.log(f"    {o.name}: нормали внутрь исправлены — {int(bad.sum())} текселей")
        orm = np.ones((size, size, 4), np.float32)              # R — AO, G — шероховатость, B — металл (Godot ORM)
        orm[..., 0] = px["ao"][..., 0]
        orm[..., 1] = px["mrh"][..., 1]
        orm[..., 2] = px["mrh"][..., 0]
        out = {"color": images[(o.name, "color")], "normal": images[(o.name, "normal")]}
        im = bpy.data.images.new(f"{o.name}_orm", size, size, alpha=False)
        im.colorspace_settings.name = "Non-Color"
        im.pixels.foreach_set(orm.ravel())
        out["orm"] = im
        for ch, img in out.items():
            path = MAPS / f"{o.name[2:].lower()}_{ch}.png"
            img.filepath_raw = str(path)
            img.file_format = "PNG"
            img.save()
        preview_material(mats[o.name], out)
        kc.log("  карты", o.name, "→", MAPS)
    for o in highs:
        o.hide_render = False
    simple_materials()
    kc.save(GAME)


def simple_materials() -> None:
    """Глаза и ресницы — материалы исходника (на штатных узлах, без UCUPaint; развёртка та же): роговица прозрачная
    по альфе картинки глаза, ресницы — по альфе своей картинки."""
    for name, src_mat in (("G_Eyes", "NPC_Eye"), ("G_Eyelashes", "NPC_Body.eyelashes01")):
        o = bpy.data.objects[name]
        o.data.materials.clear()
        o.data.materials.append(bpy.data.materials[src_mat])
        kc.log("  материал", name, "←", src_mat)


def preview_material(m: bpy.types.Material, maps: dict) -> None:
    """Просмотр в Blender так же, как в Godot: цвет, ORM (AO в цвет не множим — в Godot это отдельный канал), нормали."""
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.name != "BAKE_TARGET":
            nt.nodes.remove(n)
    nt.nodes.remove(nt.nodes["BAKE_TARGET"])
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = maps["color"]
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    orm = nt.nodes.new("ShaderNodeTexImage")
    orm.image = maps["orm"]
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(orm.outputs["Color"], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = maps["normal"]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    for i, n in enumerate((col, orm, nrm)):
        n.location = (-700, 300 - 300 * i)
    sep.location, nm.location, bsdf.location, out.location = (-400, 0), (-400, -300), (-150, 100), (200, 100)


LODS = ((1, 0.40), (2, 0.12))           # решение владельца 2026-10-22: три уровня — полный, ~40 %, ~12 %


def stage_lods() -> None:
    """LOD1 и LOD2 — упрощение LOD0 с той же развёрткой и картами (у дальних ресницы не нужны)."""
    bpy.ops.wm.open_mainfile(filepath=str(GAME))
    lod0 = [o for o in bpy.data.collections[COL].objects if o.type == "MESH"]
    for lvl, ratio in LODS:
        col = kc.collection(f"GAME_LOD{lvl}")
        for o in list(col.objects):
            bpy.data.objects.remove(o)
        total = 0
        for src in lod0:
            if lvl == 2 and src.name == "G_Eyelashes":
                continue
            o = src.copy()
            o.data = src.data.copy()
            o.name = f"{src.name}_LOD{lvl}"
            col.objects.link(o)
            m = o.modifiers.new("Dec", "DECIMATE")
            m.decimate_type = "COLLAPSE"
            m.ratio = ratio
            apply_mods(o)
            total += tris(o)
        kc.log(f"LOD{lvl}: {total} треугольников")
    kc.save(GAME)


README = (
    "NPC «мародёр» v03 — ИГРОВАЯ ВЕРСИЯ (ретопология), на просмотр. Решения владельца 2026-10-22: 60 тыс. треугольников\n"
    "на NPC в полном снаряжении (тело с одеждой ~25 тыс.), три LOD, одежда 2K, остальное 1K.\n"
    "Коллекции: GAME_LOD0 (полный, ~21 тыс.), GAME_LOD1 (~40 %, сдвинут на 1 м вправо), GAME_LOD2 (~12 %, на 2 м).\n"
    "Детали: куртка и брюки — ровная сетка четырёхугольниками по принятой форме (QuadriFlow), у краёв куртки отворот\n"
    "внутрь; брюки под курткой и в ботинках убраны; балаклава — упрощение; ботинок — наружная оболочка и подошва\n"
    "(правый — зеркало левого, та же карта); тело — кисти и лицо в прорези. Складки, строчка, молния, шнурки —\n"
    "в картах (запечены с принятого исходника): цвет, нормали, ORM (R — AO, G — шероховатость, B — металл).\n"
    "Смотреть в Rendered (Cycles); сетку — Overlays → Wireframe. Исходник для сравнения — NPC_Marauder_v03_текстуры.blend.\n"
    "Скрипт: tools/npc_kit/game_lp.py.\n")


def stage_deliver(folder: Path) -> None:
    import armor_mid as am
    bpy.ops.wm.open_mainfile(filepath=str(GAME))
    keep = {COL, "GAME_LOD1", "GAME_LOD2", "99_Studio"}
    for o in list(bpy.data.objects):
        if o.type in ("MESH", "ARMATURE") and not any(c.name in keep for c in o.users_collection):
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name not in keep and not c.objects and not c.children:
            bpy.data.collections.remove(c)
    for lvl, _ in LODS:
        for o in bpy.data.collections[f"GAME_LOD{lvl}"].objects:
            o.location.x += 1.0 * lvl
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    am.deliver(folder, f"NPC_Marauder_{kc.VERSION}_игровая.blend", README, focus_z=1.0, near=1.7)


def main() -> None:
    args = kc.args_after_dashes()
    if "lp" in args:
        stage_lp()
    if "uv" in args:
        stage_uv()
    if "bake" in args:
        stage_bake()
    if "lods" in args:
        stage_lods()
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        stage_deliver(Path(dest))


if __name__ == "__main__":
    main()
