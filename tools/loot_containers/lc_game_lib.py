"""Контейнеры лута, игровые версии: общие части конвейера (медсумка medbag_game.py и шесть контейнеров lc_game.py).

Низкие сетки — схлопывание рёбер деталей high-poly; развёртка — укладчик проекта tools/asset_kit/uv.py (один атлас на оба
состояния); запекание — Cycles, выбранные high → активная низкая, по одной детали в общую картинку; экспорт — glTF
(WebP, один материал), индекс loot_containers_models.json (aabb, movers, lod, треугольники).
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector as V

ROOT = "E:/Games/RING-godot"
LIB = "E:/Models Blender/ENVIRONMENT/RING_Loot_Containers"
OUT = ROOT + "/assets/models/loot_containers"
TEX = OUT + "/textures"
INDEX = OUT + "/loot_containers_models.json"
LOD1_RATIO = 0.25
sys.path.insert(0, ROOT + "/tools")
from asset_kit import uv as kit  # noqa: E402


def tris(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def coords(me) -> np.ndarray:
    a = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def eval_co(ob) -> np.ndarray:
    """Вершины с модификаторами, в осях объекта."""
    e = ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
    me = e.to_mesh()
    c = coords(me)
    e.to_mesh_clear()
    return c


def gd(v) -> list[float]:
    """Точка Blender → оси Godot (y вверх, z = −y)."""
    return [round(float(v[0]), 4), round(float(v[2]), 4), round(-float(v[1]), 4)]


def copy_props(src, dst) -> None:
    for p in src.bl_rna.properties:
        if p.is_readonly or p.identifier in ("name", "type"):
            continue
        try:
            setattr(dst, p.identifier, getattr(src, p.identifier))
        except Exception:
            pass


def low_mesh(ob, target: int, solidify: bool = True):
    """Низкая сетка детали: схлопывание рёбер до target треугольников (основа до утолщения), затем то же утолщение, что у
    high-poly (если у него есть модификатор). Материалы и развёртка сняты."""
    n = tris(ob.data)
    tmp = bpy.data.objects.new("tmp", ob.data.copy())
    bpy.context.scene.collection.objects.link(tmp)
    if n > target:
        md = tmp.modifiers.new("dec", "DECIMATE")
        md.decimate_type = "COLLAPSE"
        md.ratio = max(0.003, target / n)
        md.use_collapse_triangulate = True
    if solidify:
        for m in ob.modifiers:
            if m.type == "SOLIDIFY":
                copy_props(m, tmp.modifiers.new("sol", "SOLIDIFY"))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    bpy.data.objects.remove(tmp)
    me.materials.clear()
    for uv in list(me.uv_layers):
        me.uv_layers.remove(uv)
    return me


def rigid(a: np.ndarray, b: np.ndarray):
    """Лучший поворот и сдвиг a → b (Кабш): (R 3×3, t, наибольшее расхождение)."""
    ca, cb = a.mean(0), b.mean(0)
    h = (a - ca).T @ (b - cb)
    u, _, vt = np.linalg.svd(h)
    d = np.sign(np.linalg.det(vt.T @ u.T))
    r = vt.T @ np.diag([1.0, 1.0, d]) @ u.T
    t = cb - r @ ca
    return r, t, float(np.abs(a @ r.T + t - b).max())


def apply_rigid(me, r: np.ndarray, t: np.ndarray):
    out = me.copy()
    out.vertices.foreach_set("co", (coords(out) @ r.T + t).ravel())
    out.update()
    return out


def displaced(me, open_co: np.ndarray, closed_co: np.ndarray):
    """Копия сетки раскрытого состояния, сдвинутая в закрытое: сдвиг ближайшей вершины high (мягкая ткань)."""
    from mathutils import kdtree
    kd = kdtree.KDTree(len(open_co))
    for i, p in enumerate(open_co):
        kd.insert(p, i)
    kd.balance()
    out = me.copy()
    co = coords(out)
    for i, p in enumerate(co):
        _, j, _ = kd.find(p)
        co[i] = p + (closed_co[j] - open_co[j])
    out.vertices.foreach_set("co", co.ravel())
    out.update()
    return out


def finish_shading(objs, uv: str = "GameUV") -> None:
    """Гладкое затенение; жёсткое ребро — только на шве развёртки с изломом больше 30° (бинормаль Godot — в вершинах)."""
    for o in objs:
        o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
        o.data.update()
    kit.harden_on_seams(objs, uv=uv)


def layout_uv(objs, size: int, uv: str = "GameUV", margin: int = 8, group_margin: int = 4, angle_deg: float = 80.0, **pack) -> dict:
    """Развёртка укладчиком проекта: острова по изломам (Smart UV), ровная плотность, плотная укладка в один атлас."""
    kit.smart_unwrap(objs, uv=uv, angle=math.radians(angle_deg))
    rep = kit.layout(objs, size, uv=uv, stack=False, margin=margin, group_margin=group_margin, **pack, log=lambda *a: print("UVKIT", *a, flush=True))
    lo, hi = stretch_report(objs, uv)
    print("РАЗВЁРТКА: заполнение %.1f %%, плотность %.3f пикс/мм, островов %d, искажение площади 5–95 %%: %.2f…%.2f" % (rep["fill"] * 100, rep["px_mm"], rep["islands"], lo, hi), flush=True)
    return rep


def stretch_report(objs, uv: str = "GameUV") -> tuple[float, float]:
    """Искажение развёртки: отношение площади грани в UV к площади в 3D, 5-й и 95-й процентили к медиане (1,0 — без искажения)."""
    ratios, weights = [], []
    for o in objs:
        me = o.data
        n = len(me.loops)
        uvs = np.empty(n * 2, np.float32)
        me.uv_layers[uv].data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        for p in me.polygons:
            pts = uvs[p.loop_start:p.loop_start + p.loop_total]
            x, y = pts[:, 0], pts[:, 1]
            a_uv = 0.5 * abs(float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum()))
            if p.area > 1e-9 and a_uv > 0:
                ratios.append(a_uv / p.area)
                weights.append(p.area)
    r, w = np.array(ratios), np.array(weights)
    order = np.argsort(r)
    cw = np.cumsum(w[order]) / w.sum()
    q = lambda f: float(r[order][np.searchsorted(cw, f)])
    med = q(0.5)
    return q(0.05) / med, q(0.95) / med


def pack_uv_to_twin(src_objs: list, dst_objs: list, uv: str = "GameUV") -> None:
    """UV от сеток одного состояния — другому (топология та же, петли по номеру)."""
    for s, d in zip(src_objs, dst_objs):
        a = np.empty(len(s.data.loops) * 2, np.float32)
        s.data.uv_layers[uv].data.foreach_get("uv", a)
        if uv not in d.data.uv_layers:
            d.data.uv_layers.new(name=uv)
        d.data.uv_layers[uv].data.foreach_set("uv", a)
        d.data.uv_layers.active = d.data.uv_layers[uv]


def bake_image(label: str, btype: str, size: int, highs: list, lows: list, samples: int, hi_prepare=None, hi_restore=None,
               srgb: bool = False, extra: dict | None = None, extrusion: float = 0.012, max_dist: float = 0.03,
               margin: int = 6) -> np.ndarray:
    """Одна карта: выбранные high → активная низкая, по одной детали в общую картинку. hi_prepare / hi_restore — подмена
    материалов high на время прохода. Возврат — (size, size, 3) в порядке строк Blender (снизу вверх)."""
    sc = bpy.context.scene
    sc.cycles.samples = samples
    if hi_prepare:
        hi_prepare()
    img = bpy.data.images.new("b_" + label, size, size, alpha=False, float_buffer=not srgb)
    img.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    for lo in lows:
        nt = lo.data.materials[0].node_tree
        node = next(n for n in nt.nodes if n.type == "TEX_IMAGE")
        node.image = img
        nt.nodes.active = node
    first = True
    for lo in lows:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for h in highs:
            h.select_set(True)
        lo.select_set(True)
        bpy.context.view_layer.objects.active = lo
        bpy.ops.object.bake(type=btype, use_selected_to_active=True, cage_extrusion=extrusion, max_ray_distance=max_dist,
                            margin=margin, use_clear=first, **(extra or {}))
        first = False
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    if hi_restore:
        hi_restore()
    print("запечено", label, flush=True)
    return px.reshape(size, size, 4)[..., :3].copy()


def bake_target_material(lows: list):
    """Материал-приёмник запекания у всех низких деталей."""
    tgt = bpy.data.materials.new("запекание")
    tgt.use_nodes = True
    tgt.node_tree.nodes.new("ShaderNodeTexImage")
    for lo in lows:
        lo.data.materials.clear()
        lo.data.materials.append(tgt)
    return tgt


def save_png(path: str, arr: np.ndarray, size: int, srgb: bool) -> None:
    im = bpy.data.images.new("out_" + os.path.basename(path), size, size, alpha=False)
    im.colorspace_settings.name = "sRGB" if srgb else "Non-Color"
    a = np.ones((size, size, 4), np.float32)
    a[..., :3] = np.clip(arr, 0, 1)
    im.pixels.foreach_set(a.ravel())
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()


def write_maps(maps_dir: str, name: str, size: int, color, rough, metal, normal, ao, emissive=None) -> None:
    os.makedirs(maps_dir, exist_ok=True)
    orm = np.stack([ao[..., 0], rough[..., 0], metal[..., 0]], -1)
    save_png(f"{maps_dir}/{name}_baseColor.png", color, size, True)
    save_png(f"{maps_dir}/{name}_occlusionRoughnessMetallic.png", orm, size, False)
    save_png(f"{maps_dir}/{name}_normal.png", normal, size, False)
    if emissive is not None:
        save_png(f"{maps_dir}/{name}_emissive.png", emissive, size, True)
    for fn, arr in (("color", color), ("orm", orm), ("normal", normal)):
        print("карта", fn, "среднее", [round(float(x), 3) for x in arr.reshape(-1, 3).mean(0)], flush=True)


def game_material(name: str, maps_dir: str, emissive: bool = False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL", "BSDF_PRINCIPLED"):
            nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def img(suffix, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(f"{maps_dir}/{name}_{suffix}.png", check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        return n
    nt.links.new(img("baseColor", False).outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("occlusionRoughnessMetallic", True).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    # затенение из канала R той же карты: экспортёр glTF читает его из группы «glTF Material Output» (occlusionTexture)
    grp = bpy.data.node_groups.get("glTF Material Output") or bpy.data.node_groups.new("glTF Material Output", "ShaderNodeTree")
    if "Occlusion" not in [i.name for i in grp.interface.items_tree]:
        grp.interface.new_socket("Occlusion", in_out="INPUT", socket_type="NodeSocketFloat")
    gn = nt.nodes.new("ShaderNodeGroup")
    gn.node_tree = grp
    nt.links.new(sep.outputs["Red"], gn.inputs["Occlusion"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if emissive:
        nt.links.new(img("emissive", False).outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = 1.0
    return m


def join(objs: list, name: str):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    ob.data.name = name
    return ob


def decimate_copy(ob, ratio: float, name: str):
    """Копия объекта с упрощением ≈ ratio (LOD1); развёртка сохраняется (шов и гладкость — как у исходной)."""
    c = ob.copy()
    c.data = ob.data.copy()
    bpy.context.scene.collection.objects.link(c)
    md = c.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = ratio
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(c.evaluated_get(dg), depsgraph=dg)
    c.modifiers.remove(md)
    old = c.data
    c.data = me
    bpy.data.meshes.remove(old)
    c.name = name
    c.data.name = name
    return c


def export_gltf(root, model: str) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    root.select_set(True)
    for c in root.children_recursive:
        c.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{model}.gltf", export_format="GLTF_SEPARATE", export_texture_dir="textures",
                              use_selection=True, export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_tangents=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=92, export_cameras=False, export_lights=False, export_animations=False)


def aabb_of(objs: list) -> dict:
    pts = []
    for c in objs:
        pts += [c.matrix_world @ v.co for v in c.data.vertices]
    glo = gd([min(p[i] for p in pts) for i in range(3)])
    ghi = gd([max(p[i] for p in pts) for i in range(3)])
    lo, hi = [min(glo[i], ghi[i]) for i in range(3)], [max(glo[i], ghi[i]) for i in range(3)]
    return {"center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)], "size": [round(hi[i] - lo[i], 4) for i in range(3)]}


def write_index(entries: dict) -> None:
    index = json.load(open(INDEX, encoding="utf-8")) if os.path.exists(INDEX) else {}
    index.update(entries)
    with open(INDEX, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")


def fill_blender(objs, size: int, uv: str = "GameUV", margin_px: int = 3) -> float:
    """Запасная укладка Blender (вогнутая форма, острова по осям): если укладчик проекта не дал 70 %. Возврат — заполнение, доля."""
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.data.uv_layers.active = o.data.uv_layers[uv]
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(rotate=True, rotate_method="AXIS_ALIGNED", margin_method="FRACTION", margin=margin_px / size,
                            shape_method="CONCAVE", scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    return uv_coverage(objs, size, uv)


def uv_coverage(objs, size: int, uv: str = "GameUV") -> float:
    """Доля площади квадрата UV под гранями (грубо: сумма площадей без учёта наложений)."""
    tot = 0.0
    for o in objs:
        me = o.data
        uvs = np.empty(len(me.loops) * 2, np.float32)
        me.uv_layers[uv].data.foreach_get("uv", uvs)
        uvs = uvs.reshape(-1, 2)
        for p in me.polygons:
            pts = uvs[p.loop_start:p.loop_start + p.loop_total]
            x, y = pts[:, 0], pts[:, 1]
            tot += 0.5 * abs(float((x * np.roll(y, -1) - np.roll(x, -1) * y).sum()))
    return tot
