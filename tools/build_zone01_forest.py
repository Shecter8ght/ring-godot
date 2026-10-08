"""Хвойный лес и лесной мусор зоны 1 из коллекции Poly Haven «Pine Forest» (CC0), bpy → GLB.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_zone01_forest.py
Исходники: python tools/fetch_polyhaven_models.py pine_forest fir_tree_01 ... (_asset_src/pine_forest/).

Ель fir_tree_01 — скан на 2–4 млн треугольников (800 тыс. карточек веточек). Игровая версия:
1) атлас веток: участки настоящей кроны рендерятся сверху без света (альбедо + альфа) — 4 плитки;
2) ствол и скелет веток упрощаются (Decimate), на каждую ветку — горизонтальная карточка из атласа
   вдоль ветки и вертикальная поперёк; нормали карточек смотрят от ствола и вверх (объёмный свет).
Пни, корни, сухостой, валежник, камни, папоротник — сплошные сканы: только Decimate.
Пишет assets/zone01/models/forest_*.glb, assets/zone01/textures/fir_branch_atlas.png, forest.json.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/pine_forest"
OUT = ROOT / "assets/zone01/models"
TEX = ROOT / "assets/zone01/textures"
ATLAS = TEX / "fir_branch_atlas.png"
RNG = random.Random(41)


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load(asset: str) -> list:
    bpy.ops.import_scene.gltf(filepath=str(SRC / asset / f"{asset}.gltf"))
    return [o for o in bpy.context.scene.objects if o.type == "MESH"]


def tris(o) -> int:
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def export(obj_list: list, name: str) -> int:
    bpy.ops.object.select_all(action="DESELECT")
    for o in obj_list:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obj_list[0]
    bpy.ops.export_scene.gltf(filepath=str(OUT / f"{name}.glb"), export_format="GLB", use_selection=True,
                              export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT",
                              export_image_format="JPEG", export_animations=False)
    n = sum(tris(o) for o in obj_list)
    print("FOREST", name, "tris", n, flush=True)
    return n


def decimate(o, target: int) -> None:
    t = tris(o)
    if t <= target:
        return
    m = o.modifiers.new("dec", "DECIMATE")
    m.ratio = max(0.002, target / t)
    m.use_collapse_triangulate = True
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier="dec")


def split_by_material(o) -> dict:
    """Отдельный объект на каждый материал (ствол, кора веток, веточки, сухие ветки)."""
    bpy.ops.object.select_all(action="DESELECT")
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.separate(type="MATERIAL")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = {}
    for p in bpy.context.selected_objects:
        parts[p.data.materials[0].name] = p
    return parts


# ------------------------------------------------------------------ атлас веток

def render_atlas() -> None:
    """Четыре участка кроны ели a, вид сверху, без света: альбедо веточек и коры + альфа."""
    reset()
    objs = load("fir_tree_01")
    tree = next(o for o in objs if o.name.startswith("fir_tree_01_a"))
    for o in objs:
        if o is not tree:
            bpy.data.objects.remove(o, do_unlink=True)
    # материалы — только цвет текстуры (emission), альфа веточек сохраняется
    for m in tree.data.materials:
        nt = m.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        col = bsdf.inputs["Base Color"].links[0].from_socket if bsdf.inputs["Base Color"].links else None
        alpha = bsdf.inputs["Alpha"].links[0].from_socket if bsdf.inputs["Alpha"].links else None
        emit = nt.nodes.new("ShaderNodeEmission")
        if col:
            nt.links.new(col, emit.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMixShader")
        transp = nt.nodes.new("ShaderNodeBsdfTransparent")
        if alpha:
            nt.links.new(alpha, mix.inputs["Fac"])
        else:
            mix.inputs["Fac"].default_value = 1.0
        nt.links.new(transp.outputs[0], mix.inputs[1])
        nt.links.new(emit.outputs[0], mix.inputs[2])
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
        m.blend_method = "HASHED" if hasattr(m, "blend_method") else None
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 32
    scene.cycles.device = "CPU"
    scene.render.film_transparent = True
    scene.view_settings.view_transform = "Standard"
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 512
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    world = bpy.data.worlds.new("w")
    scene.world = world
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    # кадры — по настоящим веткам: длина 1.6–2.6 м, почти горизонтальные, на разной высоте
    parts = split_by_material(tree)
    for k, p in list(parts.items()):
        if "trunk" in k:
            bpy.data.objects.remove(p, do_unlink=True)
    bark = parts["fir_tree_01_bark"]
    cands = []
    for (a, b, length) in branch_axes(bark):
        d = (b - a)
        if 1.6 < length < 2.6 and abs(d.normalized().z) < 0.35:
            cands.append((a, b, length))
    cands.sort(key=lambda t: (t[0].z + t[1].z))
    picks = [cands[int(len(cands) * f)] for f in (0.2, 0.4, 0.6, 0.8)]
    tiles = []
    for k, (a, b, length) in enumerate(picks):
        # от ствола к концу ветки — вдоль оси X кадра
        tb = [o.matrix_world @ Vector(c) for o in bpy.context.scene.objects if o.type == "MESH" for c in o.bound_box]
        cx = sum(v.x for v in tb) / len(tb)
        cy = sum(v.y for v in tb) / len(tb)
        base, tip = (a, b) if math.hypot(a.x - cx, a.y - cy) < math.hypot(b.x - cx, b.y - cy) else (b, a)
        d = (tip - base)
        ang = math.atan2(d.y, d.x)
        center = (base + tip) * 0.5
        cam_data.ortho_scale = length * 1.2
        cam.location = Vector((center.x, center.y, center.z + 3.0))
        cam.rotation_euler = (0, 0, ang)
        cam_data.clip_start = 3.0 - 0.45 - abs(d.z) * 0.5
        cam_data.clip_end = 3.0 + 0.45 + abs(d.z) * 0.5
        path = TEX / f"_fir_tile_{k}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        tiles.append(path)
    # склейка 2×2 (2048×1024)
    imgs = [bpy.data.images.load(str(p)) for p in tiles]
    w, h = 1024, 512
    atlas = bpy.data.images.new("atlas", 2 * w, 2 * h, alpha=True)
    px = [0.0] * (4 * w * h * 4)
    for k, img in enumerate(imgs):
        src = list(img.pixels)
        ox, oy = (k % 2) * w, (k // 2) * h
        for y in range(h):
            row = src[y * w * 4:(y + 1) * w * 4]
            start = ((oy + y) * 2 * w + ox) * 4
            px[start:start + w * 4] = row
    # основания соседних веток у ствола (край плитки со стороны ствола) — гасим альфой
    import numpy as np
    arr = np.array(px, dtype=np.float32).reshape(2 * h, 2 * w, 4)
    ramp = np.clip((np.arange(w) / w - 0.04) / 0.14, 0.0, 1.0) ** 1.5
    arr[:, :w, 3] *= ramp[None, :]
    arr[:, w:, 3] *= ramp[None, :]
    atlas.pixels = arr.ravel().tolist()
    atlas.filepath_raw = str(ATLAS)
    atlas.file_format = "PNG"
    atlas.save()
    for p in tiles:
        p.unlink()
    print("FOREST atlas", ATLAS, flush=True)


# ------------------------------------------------------------------ игровая ель

def branch_axes(obj) -> list:
    """Ветки = связные куски коры: начало у ствола, конец, длина (оси по главному направлению)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    seen = set()
    out = []
    mw = obj.matrix_world
    for v in bm.verts:
        if v.index in seen:
            continue
        stack = [v]
        comp = []
        while stack:
            u = stack.pop()
            if u.index in seen:
                continue
            seen.add(u.index)
            comp.append(mw @ u.co)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in seen:
                    stack.append(w)
        if len(comp) < 12:
            continue
        c = sum(comp, Vector()) / len(comp)
        far = max(comp, key=lambda p: (p - c).length)
        far2 = max(comp, key=lambda p: (p - far).length)
        length = (far - far2).length
        if length < 0.35:
            continue
        out.append((far, far2, length))
    bm.free()
    return out


def fir(variant: str, name: str) -> dict:
    reset()
    objs = load("fir_tree_01")
    tree = next(o for o in objs if o.name.startswith(f"fir_tree_01_{variant}"))
    for o in objs:
        if o is not tree:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.objects.active = tree
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    parts = split_by_material(tree)
    trunk = next(p for k, p in parts.items() if "trunk" in k)
    bark = parts.get("fir_tree_01_bark")
    dead = parts.get("fir_tree_01_dead_branches")
    twig = parts.get("fir_tree_01_twig")
    # ось ствола
    tb = [trunk.matrix_world @ Vector(c) for c in trunk.bound_box]
    axis_x = sum(v.x for v in tb) / 8
    axis_y = sum(v.y for v in tb) / 8
    branches = branch_axes(bark) if bark else []
    if twig:
        bpy.data.objects.remove(twig, do_unlink=True)
    decimate(trunk, 1800)
    if bark:
        decimate(bark, 2600)
    if dead:
        decimate(dead, 500)
    # карточки веток
    mesh = bpy.data.meshes.new(name + "_cards")
    verts, faces, uvs, normals = [], [], [], []
    for (a, b, length) in branches:
        ra = math.hypot(a.x - axis_x, a.y - axis_y)
        rb = math.hypot(b.x - axis_x, b.y - axis_y)
        base, tip = (a, b) if ra < rb else (b, a)
        d = (tip - base).normalized()
        out_dir = Vector((tip.x - axis_x, tip.y - axis_y, 0)).normalized()
        side = d.cross(Vector((0, 0, 1)))
        if side.length < 1e-3:
            continue
        side.normalize()
        tile = RNG.randrange(4)
        u0, v0 = (tile % 2) * 0.5, (tile // 2) * 0.5
        n_card = (out_dir * 0.55 + Vector((0, 0, 0.85))).normalized()
        # ветка — 2 отрезка; на отрезок две карточки, развёрнутые вокруг оси ветки на ±(20…40)° —
        # не плоская «пластина», а объёмная лапа
        segs = 2 if length > 1.0 else 1
        for sgi in range(segs):
            t0 = sgi / segs
            seg_len = length * 1.15 / segs + 0.25
            start = base + d * (length * t0 + 0.05) + Vector((0, 0, -0.06 * length * t0))
            width = max(0.35, length * 0.6 * (1.0 - 0.35 * t0))
            for k in range(2):
                roll = math.radians((RNG.uniform(20, 40)) * (1 if k == 0 else -1))
                up = Vector((0, 0, 1))
                off_dir = (side * math.cos(roll) + up * math.sin(roll)).normalized()
                off = off_dir * width * 0.5
                droop = Vector((0, 0, -0.07 * seg_len))
                p0, p1 = start - off, start + off
                p2, p3 = start + d * seg_len + off + droop, start + d * seg_len - off + droop
                tile = RNG.randrange(4)
                u0, v0 = (tile % 2) * 0.5, (tile // 2) * 0.5
                # отрезок у ствола берёт левую половину плитки, внешний — правую
                ua, ub = (u0 + 0.25 * t0 * 2 if segs > 1 else u0), (u0 + 0.5 if segs == 1 else u0 + 0.25 * (t0 * 2 + 1))
                i = len(verts)
                verts += [p0, p1, p2, p3]
                faces.append([i, i + 1, i + 2, i + 3])
                uvs.append([(ua, v0), (ua, v0 + 0.5), (ub, v0 + 0.5), (ub, v0)])
                normals += [n_card] * 4
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    uv = mesh.uv_layers.new(name="UVMap")
    for poly, puv in zip(mesh.polygons, uvs):
        for k in range(poly.loop_total):
            uv.data[poly.loop_start + k].uv = puv[k]
    mesh.normals_split_custom_set([tuple(normals[l.vertex_index]) for l in mesh.loops])
    mat = bpy.data.materials.new("FirBranchCards")
    mesh.materials.append(mat)
    cards = bpy.data.objects.new(name + "_cards", mesh)
    bpy.context.scene.collection.objects.link(cards)
    keep = [o for o in (trunk, bark, dead, cards) if o]
    # основание в ноль, вершина вверх
    zmin = min((o.matrix_world @ Vector(c)).z for o in keep for c in o.bound_box)
    for o in keep:
        o.location.x -= axis_x
        o.location.y -= axis_y
        o.location.z -= zmin
    bpy.ops.object.select_all(action="DESELECT")
    for o in keep:
        o.select_set(True)
    bpy.context.view_layer.objects.active = keep[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    bpy.ops.object.transform_apply(location=True, rotation=False, scale=False)
    height = max((joined.matrix_world @ Vector(c)).z for c in joined.bound_box)
    n = export([joined], name)
    return dict(triangles=n, height=round(height, 2), branches=len(branches),
                collisions=[dict(pos=[0, 2.0, 0], size=[0.5, 4.0, 0.5], yaw=0)])


def solid(asset: str, name: str, target: int, pick: str | None = None) -> dict:
    reset()
    objs = load(asset)
    if pick:
        for o in list(objs):
            if not o.name.startswith(pick):
                bpy.data.objects.remove(o, do_unlink=True)
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    for o in objs:
        decimate(o, max(200, target // len(objs)))
    n = export(objs, name)
    bb = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    size = [max(v.x for v in bb) - min(v.x for v in bb), max(v.z for v in bb) - min(v.z for v in bb),
            max(v.y for v in bb) - min(v.y for v in bb)]
    return dict(triangles=n, size=[round(s, 2) for s in size],
                collisions=[dict(pos=[0, size[1] * 0.5, 0], size=[size[0] * 0.8, size[1], size[2] * 0.8], yaw=0)])


def main() -> None:
    TEX.mkdir(parents=True, exist_ok=True)
    # ели — tools/build_spruce.py (своя ель по референсам владельца); отсюда — только лесной мусор
    manifest = {}
    for asset, name, target, pick in [("tree_stump_01", "forest_stump_01", 1500, None), ("tree_stump_02", "forest_stump_02", 1500, None),
                                      ("pine_roots", "forest_roots", 2500, None), ("dead_tree_trunk", "forest_dead_trunk", 2500, None),
                                      ("dry_branches_medium_01", "forest_dry_branches", 1500, None),
                                      ("rock_moss_set_01", "forest_rocks_01", 3000, None), ("rock_moss_set_02", "forest_rocks_02", 3000, None),
                                      ("fern_02", "forest_fern", 2500, None)]:
        manifest[name] = solid(asset, name, target, pick)
    (OUT / "forest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


main()
