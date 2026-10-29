"""Транспорт «Проспекта»: свои дальние уровни детализации — LOD1 и LOD2 с одним запечённым атласом на вариант.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_vehicles/game_lods.py -- [класс …]

Зачем: машины «Проспекта» стоят сотнями экземпляров по 21–55 тыс. треугольников и 7–9 поверхностей (кузов, салон,
колесо, низ, стёкла окон и фар) — около 1,3 мс кадра, на паркинге −1 до 2,6 мс (tools/prospekt_vehicles_perf.tscn).
Автоматические LOD движка упрощают каждую поверхность отдельно и не уменьшают число вызовов отрисовки.

Источник — «<Имя>_textured_v01.blend» машины (как у game_export.py: варианты коллекциями «Целый», «Открыт», «Битый»,
«Сгоревший»). На каждый вариант:
- LOD1 — сетка варианта без невидимого низа (остаются подкрылки, брызговики, рама), упрощённая схлопыванием рёбер до
  LOD1_K от LOD0 (у коробчатых — с закреплёнными краями листов, см. decimate); своя развёртка, атлас ATLAS² — цвет,
  ORM и нормаль запечены с LOD0 в Cycles («выбранное на активное»: краска, салон, колёса, фары — один материал);
  стёкла окон — прежний прозрачный материал, сквозь окна виден салон. Две поверхности.
- LOD2 — LOD1, упрощённый до LOD2_K от LOD0 (сколько позволят закреплённые края), тот же атлас; окна тоже из атласа
  (тёмные непрозрачные), у целой закрытой машины салон убран — за тёмным стеклом его не видно. Одна поверхность.
Выход: assets/models/prospekt_vehicles/PV_<вариант>_lod1.gltf и _lod2.gltf, карты PV_<вариант>_lod_* в textures/; в
индексе data/urban95_models.json у записей PV_* — «lods» (MallFiller: на уровень своя пачка MultiMesh с дальностями),
клетка пачек CELL и «lod_fade»: false (смена уровня без плавного перехода — переход стоил дороже самих уровней).
Запускать после game_export.py (он пишет записи заново, «lods» сохраняет); затем --import,
python -X utf8 tools/prospekt_vehicles/game_imports.py, --import. Сравнение уровней рядом — tools/prospekt_vehicles_perf.tscn
-- lodcmp.
Просмотр в Blender: <машина>/game/<Имя>_lods_v01.blend (LOD1 и LOD2 вариантов рядом), карты — <машина>/game/lod_maps.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
LIB = Path("E:/Models Blender/VEHICLES/Город_партия1")
OUT = ROOT / "assets" / "models" / "prospekt_vehicles"
INDEX = ROOT / "data" / "urban95_models.json"

CARS = {"sedan": ("Седан", "Sedan"), "hatch": ("Хэтчбек", "Hatchback"), "wagon": ("Универсал", "Wagon"),
        "suv": ("Внедорожник", "SUV"), "bus12": ("Автобус_12м", "Bus12"), "paz": ("ПАЗ", "PAZ"),
        "gazel": ("ГАЗель_маршрутка", "Gazel")}
VARIANTS = {"Целый": "", "Открыт": "_open", "Битый": "_wreck", "Сгоревший": "_burnt"}
# коробчатые: кузов — открытые листы с вырезами окон; и в LOD1 упрощаются с закреплёнными краями (иначе «зубцы» стоек)
BOXES = ("bus12", "paz", "gazel")

LOD1_K = 0.27                # треугольников от LOD0
LOD2_K = 0.075
LOD2_MIN = 1500
ATLAS = 1024
UNDER_KEEP = ("Liner_", "Mudflap", "Frame")      # из низа видно сбоку; остальное (поддон, выхлоп, мосты) — нет
UNDER = ("Liner_", "Under_Tray", "Exhaust", "Frame", "Rear_Axle", "Fuel_Tank", "Rear_Springs", "Mudflap")
WINDOWS = ("GLASS_glass", "GLASS_glass_broken")  # стёкла окон: в LOD1 прозрачные, в LOD2 — атлас
# окна в атласе (только LOD2, непрозрачные): у LOD0 стекло полупрозрачное (альфа 0,3), и отражение неба на нём
# ослаблено той же долей; непрозрачное с той же гладкостью — тёмное зеркало. AO гасит отражение окружения, как альфа
WINDOW_ROUGH, WINDOW_AO = 0.3, 0.35
# стекло фары: у LOD0 сквозь светлое стекло блестит отражатель — издали серебристо-серая фара; первое попадание луча —
# само стекло (белое пятно), без стекла — чёрный корпус фонаря. В атлас — среднее: серый полуметалл
LAMP = {"base": (0.32, 0.33, 0.35), "rough": 0.2, "metal": 0.6, "ao": 1.0}
# доля площади атласа по наборам (масштаб островов до упаковки): салон, низ и стёкла вдали почти не видны
UV_K = {"Interior": 0.5, "Under": 0.5, "Wheel": 0.8, "glass": 0.4}
CELL = 12.0                  # м: клетка пачек MallFiller — дальность уровня считается до центра пачки
EXTRUDE, RAY = 0.04, 0.12    # м: луч запекания — от упрощённой поверхности наружу и обратно до LOD0
SAMPLES = 8


def ends(length: float) -> tuple[float, float]:
    """Дальности смены уровней по длине машины (по размеру на экране): легковая ≈ 25 / 60 м, автобус 12 м — 45 / 120."""
    return min(max(5.5 * length, 25.0), 45.0), min(max(13.0 * length, 60.0), 120.0)


def gpu() -> str:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for kind in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = kind
        except TypeError:
            continue
        prefs.get_devices()
        if any(d.type == kind for d in prefs.devices):
            for d in prefs.devices:
                d.use = d.type == kind
            bpy.context.scene.cycles.device = "GPU"
            return kind
    bpy.context.scene.cycles.device = "CPU"
    return "CPU"


def part_name(ob: bpy.types.Object) -> str:
    """«clean:Liner_FL.002» → «Liner_FL»."""
    n = ob.name.split(":", 1)[-1]
    return n.rsplit(".", 1)[0] if n[-4:-3] == "." and n[-3:].isdigit() else n


def joined(col: bpy.types.Collection, name: str, keep) -> bpy.types.Object:
    """Сетки варианта, прошедшие keep, → одна сетка в осях корня варианта (как game_export.variant_mesh)."""
    root = next(o for o in col.objects if o.type == "EMPTY" and o.parent is None)
    inv = root.matrix_world.inverted()
    copies = []
    for o in col.objects:
        if o.type != "MESH" or not keep(o):
            continue
        c = o.copy()
        c.data = o.data.copy()
        c.parent = None
        c.matrix_world = Matrix.Identity(4)
        c.data.transform(inv @ o.matrix_world)
        if (inv @ o.matrix_world).determinant() < 0:      # зеркальная копия колеса — нормали наружу
            c.data.flip_normals()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = ob.data.name = name
    return ob


def tris(ob: bpy.types.Object) -> int:
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


def _collapse(ob: bpy.types.Object, ratio: float, keep_edges: bool) -> None:
    """Схлопывание рёбер модификатором; keep_edges — вершины краёв открытых оболочек не трогаются."""
    mod = ob.modifiers.new("lod", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = min(1.0, ratio)
    mod.use_collapse_triangulate = True
    if keep_edges:
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        edge = sorted({v.index for e in bm.edges if e.is_boundary for v in e.verts})
        bm.free()
        group = ob.vertex_groups.new(name="edges")
        group.add(edge, 1.0, "REPLACE")
        mod.vertex_group = group.name
        mod.invert_vertex_group = True          # в группе — край: упрощается только остальное
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    ob.modifiers.clear()
    ob.vertex_groups.clear()
    old = ob.data
    ob.data = me
    me.name = ob.name
    me.validate()
    bpy.data.meshes.remove(old)


def decimate(ob: bpy.types.Object, target: int, split: bool = False) -> None:
    """Схлопывание рёбер по квадрикам на всей сетке сразу: детали варианта не связаны, мелкие уходят первыми.

    split — для глубокого упрощения (LOD2): открытые оболочки (листы кузова автобуса и ГАЗели с вырезами окон, без
    изнанки) схлопывание без опоры на краях рвёт в осколки, а при закреплённых краях общий бюджет «съедает» замкнутые
    детали (колёса) целиком. Поэтому замкнутые и открытые части — отдельно, с одной долей; у открытых края закреплены.
    """
    n = tris(ob)
    if n <= target:
        return
    if not split:
        _collapse(ob, target / n, False)
        return
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.faces.ensure_lookup_table()
    comp = [-1] * len(bm.faces)
    opened: set = set()
    for f0 in bm.faces:
        if comp[f0.index] >= 0:
            continue
        stack, members, edge = [f0], [], False
        comp[f0.index] = f0.index
        while stack:
            f = stack.pop()
            members.append(f.index)
            for e in f.edges:
                edge = edge or e.is_boundary
                for g in e.link_faces:
                    if comp[g.index] < 0:
                        comp[g.index] = f0.index
                        stack.append(g)
        if edge:
            opened.update(members)
    bm.free()
    parts = []
    for want_open in (False, True):
        c = ob.copy()
        c.data = ob.data.copy()
        bpy.context.scene.collection.objects.link(c)
        bm = bmesh.new()
        bm.from_mesh(c.data)
        bm.faces.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if (f.index in opened) != want_open], context="FACES")
        bm.to_mesh(c.data)
        bm.free()
        if c.data.polygons:
            _collapse(c, target / n, want_open)
            parts.append(c)
        else:
            bpy.data.objects.remove(c, do_unlink=True)
    bpy.ops.object.select_all(action="DESELECT")
    for c in parts:
        c.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    old = ob.data
    ob.data = parts[0].data
    ob.data.name = ob.name
    bpy.data.objects.remove(parts[0], do_unlink=True)
    bpy.data.meshes.remove(old)


def mat_kind(name: str) -> str:
    """Набор по имени материала: SP_<семья>_<набор> или GLASS_<вид>."""
    if name in WINDOWS:
        return "glass"
    if name.startswith("GLASS_"):
        return "lamp"
    ts = name.split("_", 2)[-1]
    return "Body" if ts.startswith("Body") else ts


def uv_islands(bm, uv) -> list:
    """Острова развёртки: грани, связанные ребром с совпадающими координатами на обеих сторонах."""
    parent = list(range(len(bm.faces)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        a, b = lf
        la = {lp.vert: lp[uv].uv for lp in a.loops}
        lb = {lp.vert: lp[uv].uv for lp in b.loops}
        if all((la[v] - lb[v]).length < 1e-6 for v in e.verts):
            parent[find(a.index)] = find(b.index)
    out: dict = {}
    for f in bm.faces:
        out.setdefault(find(f.index), []).append(f)
    return list(out.values())


def unwrap(ob: bpy.types.Object, kinds: list[str]) -> None:
    """Своя развёртка LOD: проекция по граням, острова невидимого мельче (UV_K), упаковка Blender."""
    for layer in list(ob.data.uv_layers):
        ob.data.uv_layers.remove(layer)
    ob.data.uv_layers.new(name="UVMap")
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60.0), island_margin=0.0, area_weight=0.0, correct_aspect=True,
                             scale_to_bounds=False)
    bm = bmesh.from_edit_mesh(ob.data)
    uv = bm.loops.layers.uv.active
    for faces in uv_islands(bm, uv):
        k = UV_K.get(kinds[faces[0].material_index], 1.0)
        if k == 1.0:
            continue
        pts = [lp[uv].uv.copy() for f in faces for lp in f.loops]
        c = sum(pts, pts[0] * 0.0) / len(pts)
        for f in faces:
            for lp in f.loops:
                lp[uv].uv = c + (lp[uv].uv - c) * k
    bmesh.update_edit_mesh(ob.data)
    bpy.ops.uv.pack_islands(udim_source="CLOSEST_UDIM", rotate=True, rotate_method="ANY", scale=True,
                            merge_overlap=False, margin_method="FRACTION", margin=0.006, pin=False,
                            shape_method="CONCAVE")
    bpy.ops.object.mode_set(mode="OBJECT")


def channel(m: bpy.types.Material, ch: str) -> bpy.types.Material:
    """Копия материала LOD0, где канал ch (base, rough, metal, ao) выведен излучением — для запекания EMIT."""
    fixed = None
    if m.name in WINDOWS and ch in ("rough", "ao"):
        fixed = WINDOW_ROUGH if ch == "rough" else WINDOW_AO
    elif m.name == "GLASS_lamp_glass":
        fixed = LAMP[ch]
    if fixed is not None:
        c = bpy.data.materials.new(f"{m.name}__{ch}")
        c.use_nodes = True
        rgb = fixed if isinstance(fixed, tuple) else (fixed, fixed, fixed)
        em = c.node_tree.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (*rgb, 1.0)
        c.node_tree.links.new(em.outputs[0], c.node_tree.nodes["Material Output"].inputs["Surface"])
        return c
    c = m.copy()
    c.name = f"{m.name}__{ch}"
    nt = c.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    b = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")
    em = nt.nodes.new("ShaderNodeEmission")
    if ch == "ao":
        sep = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeSeparateColor"), None)
        if sep is not None:
            nt.links.new(sep.outputs["Red"], em.inputs["Color"])
        else:
            em.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    else:
        s = b.inputs[{"base": "Base Color", "rough": "Roughness", "metal": "Metallic"}[ch]]
        if s.is_linked:
            nt.links.new(s.links[0].from_socket, em.inputs["Color"])
        elif ch == "base":
            em.inputs["Color"].default_value = tuple(s.default_value)
        else:
            v = float(s.default_value)
            em.inputs["Color"].default_value = (v, v, v, 1.0)
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return c


def bake_material(img: bpy.types.Image) -> bpy.types.Material:
    m = bpy.data.materials.get("LOD_bake") or bpy.data.materials.new("LOD_bake")
    m.use_nodes = True
    nt = m.node_tree
    node = next((n for n in nt.nodes if n.bl_idname == "ShaderNodeTexImage"), None) or nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.nodes.active = node
    return m


def bake(src: bpy.types.Object, dst: bpy.types.Object, kind: str, img: bpy.types.Image) -> None:
    for i in range(len(dst.data.materials)):
        dst.data.materials[i] = bake_material(img)
    bpy.ops.object.select_all(action="DESELECT")
    src.select_set(True)
    dst.select_set(True)
    bpy.context.view_layer.objects.active = dst
    bpy.ops.object.bake(type=kind, normal_space="TANGENT", use_selected_to_active=True, cage_extrusion=EXTRUDE,
                        max_ray_distance=RAY, margin=12, margin_type="EXTEND", use_clear=True, target="IMAGE_TEXTURES")


def new_image(name: str, color: bool) -> bpy.types.Image:
    img = bpy.data.images.get(name)
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, ATLAS, ATLAS, alpha=False)
    img.colorspace_settings.name = "sRGB" if color else "Non-Color"
    return img


def occlusion_group() -> bpy.types.NodeTree:
    """Группа «glTF Material Output»: экспортёр берёт из её входа Occlusion карту AO (канал R той же ORM)."""
    g = bpy.data.node_groups.get("glTF Material Output")
    if g:
        return g
    g = bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    g.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    return g


def atlas_material(mid: str, base: bpy.types.Image, orm: bpy.types.Image, nrm: bpy.types.Image) -> bpy.types.Material:
    m = bpy.data.materials.new(f"{mid}_lod")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    t_b, t_o, t_n = (nt.nodes.new("ShaderNodeTexImage") for _ in range(3))
    t_b.image, t_o.image, t_n.image = base, orm, nrm
    nt.links.new(t_b.outputs[0], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_o.outputs[0], sep.inputs[0])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(t_n.outputs[0], nm.inputs["Color"])
    nt.links.new(nm.outputs[0], b.inputs["Normal"])
    grp = nt.nodes.new("ShaderNodeGroup")
    grp.node_tree = occlusion_group()
    nt.links.new(sep.outputs["Red"], grp.inputs["Occlusion"])
    return m


def set_materials(ob: bpy.types.Object, names: list[str], atlas: bpy.types.Material, windows: bool) -> None:
    """Грани — материал атласа; при windows стёкла окон остаются своими прозрачными материалами."""
    keep = [n for n in dict.fromkeys(names) if windows and n in WINDOWS]
    mats = [atlas] + [bpy.data.materials[n] for n in keep]
    remap = [mats.index(bpy.data.materials[n]) if n in keep else 0 for n in names]
    idx = np.zeros(len(ob.data.polygons), dtype=np.int32)
    ob.data.polygons.foreach_get("material_index", idx)
    idx = np.array(remap, dtype=np.int32)[idx]
    ob.data.materials.clear()
    for m in mats:
        ob.data.materials.append(m)
    ob.data.polygons.foreach_set("material_index", idx)
    ob.data.update()


def export(ob: bpy.types.Object, path: Path) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLTF_SEPARATE", export_texture_dir="textures",
                              use_selection=True, export_apply=True, export_yup=True, export_texcoords=True,
                              export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=90, export_cameras=False, export_lights=False,
                              export_animations=False)


def lod_variant(col: bpy.types.Collection, mid: str, maps: Path, review: bpy.types.Collection, x: float,
                box: bool) -> dict:
    t0 = time.time()
    src = joined(col, f"{mid}_src", lambda o: True)
    n0 = tris(src)
    base = joined(col, f"{mid}_lod1",
                  lambda o: not part_name(o).startswith(UNDER) or part_name(o).startswith(UNDER_KEEP))
    lod1 = base
    decimate(lod1, int(n0 * LOD1_K), split=box)
    names = [m.name for m in lod1.data.materials]
    kinds = [mat_kind(n) for n in names]
    # затенение упрощённой сетки — гладкое с острыми рёбрами по углу; разницу с LOD0 несёт запечённая нормаль
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = lod1
    lod1.select_set(True)
    bpy.ops.mesh.customdata_custom_splitnormals_clear()
    lod1.data.shade_smooth()
    lod1.data.set_sharp_from_angle(angle=math.radians(50.0))
    unwrap(lod1, kinds)
    # запекание: нормаль — с настоящими материалами LOD0 (карты нормалей Painter), каналы — излучением
    imgs = {k: new_image(f"{mid}_lod_{k}", k == "base") for k in ("normal", "base", "rough", "metal", "ao")}
    bake(src, lod1, "NORMAL", imgs["normal"])
    orig = [s.material for s in src.material_slots]
    for ch in ("base", "rough", "metal", "ao"):
        for i, m in enumerate(orig):
            src.data.materials[i] = channel(m, ch)
        bake(src, lod1, "EMIT", imgs[ch])
        for i, m in enumerate(orig):
            tmp = src.data.materials[i]
            src.data.materials[i] = m
            bpy.data.materials.remove(tmp)
    # ORM: R — AO, G — шероховатость, B — металл (как у карт Painter)
    px = ATLAS * ATLAS * 4
    orm_px = np.empty(px, dtype=np.float32)
    ch_px = {}
    for ch in ("ao", "rough", "metal"):
        a = np.empty(px, dtype=np.float32)
        imgs[ch].pixels.foreach_get(a)
        ch_px[ch] = a[0::4]
    orm_px[0::4], orm_px[1::4], orm_px[2::4], orm_px[3::4] = ch_px["ao"], ch_px["rough"], ch_px["metal"], 1.0
    orm = new_image(f"{mid}_lod_occlusionRoughnessMetallic", False)
    orm.pixels.foreach_set(orm_px)
    imgs["base"].name = f"{mid}_lod_baseColor"
    maps.mkdir(parents=True, exist_ok=True)
    final = {"base": imgs["base"], "orm": orm, "normal": imgs["normal"]}
    for img in final.values():
        img.filepath_raw = str(maps / f"{img.name}.png")
        img.file_format = "PNG"
        img.save()
    for ch in ("rough", "metal", "ao"):
        bpy.data.images.remove(imgs[ch])
    atlas = atlas_material(mid, final["base"], final["orm"], final["normal"])
    # LOD2 — из LOD1 с той же развёрткой (копия до замены материалов: грани ещё знают свой набор)
    lod2 = lod1.copy()
    lod2.data = lod1.data.copy()
    lod2.name = lod2.data.name = f"{mid}_lod2"
    bpy.context.scene.collection.objects.link(lod2)
    set_materials(lod1, names, atlas, windows=True)
    if col.name == "Целый":
        # у целой закрытой машины салона за тёмными непрозрачными окнами не видно
        bm = bmesh.new()
        bm.from_mesh(lod2.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if kinds[f.material_index] == "Interior"], context="FACES")
        bm.to_mesh(lod2.data)
        bm.free()
    decimate(lod2, max(int(n0 * LOD2_K), LOD2_MIN), split=True)
    set_materials(lod2, names, atlas, windows=False)
    out = {}
    for lv, ob in ((1, lod1), (2, lod2)):
        path = OUT / f"{mid}_lod{lv}.gltf"
        export(ob, path)
        out[lv] = {"file": f"res://assets/models/prospekt_vehicles/{mid}_lod{lv}.gltf", "triangles": tris(ob)}
        for c in list(ob.users_collection):
            c.objects.unlink(ob)
        review.objects.link(ob)
        ob.location = (x, 0.0 if lv == 1 else -16.0, 0.0)
    bpy.data.objects.remove(src, do_unlink=True)
    print(f"LOD {mid}: LOD0 {n0}, LOD1 {out[1]['triangles']}, LOD2 {out[2]['triangles']} треуг., "
          f"{time.time() - t0:.0f} с")
    return {"lod0": n0, **out}


def lod_class(cls: str, index: dict) -> None:
    folder, fname = CARS[cls]
    src = LIB / folder / "game" / f"{fname}_textured_v01.blend"
    if not src.exists():
        print("нет файла:", src)
        return
    bpy.ops.wm.open_mainfile(filepath=str(src))
    scn = bpy.context.scene
    scn.render.engine = "CYCLES"
    print("Cycles:", gpu())
    scn.cycles.samples = SAMPLES
    scn.render.bake.use_selected_to_active = True
    review = bpy.data.collections.new("LOD")
    scn.collection.children.link(review)
    maps = LIB / folder / "game" / "lod_maps"
    cols = [c for c in bpy.data.collections if c.name in VARIANTS]
    for i, col in enumerate(cols):
        mid = f"PV_{cls}{VARIANTS[col.name]}"
        res = lod_variant(col, mid, maps, review, i * 5.0, cls in BOXES)
        entry = index["models"].get(mid)
        if entry is None:
            print("нет записи в индексе:", mid)
            continue
        size = entry["aabb"]["size"]
        e0, e1 = ends(max(size[0], size[2]))
        entry["lods"] = [{"file": entry["file"], "end": round(e0, 1), "triangles": entry["triangles"]},
                         {"file": res[1]["file"], "end": round(e1, 1), "triangles": res[1]["triangles"]},
                         {"file": res[2]["file"], "end": 520.0, "triangles": res[2]["triangles"]}]
        entry["cell"] = CELL
        # без плавного перехода: пачка в полосе перехода рисуется прозрачной — на паркинге −1 это дороже самих уровней
        entry["lod_fade"] = False
    # файл для просмотра: только уровни детализации, карты — рядом в lod_maps
    for c in list(scn.collection.children):
        if c != review:
            for o in list(c.all_objects):
                bpy.data.objects.remove(o, do_unlink=True)
            scn.collection.children.unlink(c)
    bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(LIB / folder / "game" / f"{fname}_lods_v01.blend"), compress=True)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    wanted = argv or list(CARS)
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    for cls in wanted:
        lod_class(cls, index)
    # индекс общий (Urban 95, растения других сессий): перечитать и заменить только «lods» и «cell» своих записей
    fresh = json.loads(INDEX.read_text(encoding="utf-8"))
    for k, v in index["models"].items():
        if k.startswith("PV_") and "lods" in v and k in fresh["models"]:
            for key in ("lods", "cell", "lod_fade"):
                fresh["models"][k][key] = v[key]
    INDEX.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


main()
