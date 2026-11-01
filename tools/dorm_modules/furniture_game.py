"""Мебель общежития, игровые версии (навык godot-asset-preparation), бюджет «подробнее» (владелец 2026-11-01: «мебель
видна крупно»): карты износа этапа 2 без уменьшения (2K, ковёр 4K), лёгкие сетки — как есть, тяжёлые ткань и спираль
упрощаются схлопыванием рёбер с той же развёрткой, их рельеф запекается в нормали (Cycles на процессоре). Панцирная
сетка кроватей (150 тыс. треугольников проволоки) — прозрачная плоскость по форме провиса с плиткой ячеек (своя
текстура: ромбы 34 мм из проволоки Ø1,8, тускло-оцинкованная, ржавые точки), окантовка и пружины — облегчённые.

  "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background "<RING_Dorm_Furniture_uv_v01.blend>" --python-exit-code 1 \
      --python tools/dorm_modules/furniture_game.py -- [предмет …]

→ assets/models/dorm/furniture/<предмет>.gltf (+ textures/*.webp); варианты отделки — textures/<предмет>__<код>_*.webp
(стенд подменяет ими карты материала предмета); furniture.json — треугольники, габарит, варианты, особые материалы.
Низкие сетки — копией рядом с исходником: RING_Dorm_Furniture_game_v01.blend. Ступени детализации — автоматические
при импорте Godot; настройки карт — furniture_imports.py после первого --import.
"""
import json
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector as V
from mathutils.kdtree import KDTree

ROOT = "E:/Games/RING-godot"
SRC = ROOT + "/_asset_src/dorm_furniture/maps_worn"
OUT = ROOT + "/assets/models/dorm/furniture"
TEX = OUT + "/textures"
CATALOG = ROOT + "/tools/asset_kit/finish/finishes.json"
# упрощение: предмет → {деталь: треугольников}; остальные детали — как есть
DECIMATE = {"furn_mattress": {"Матрас_тик": 4000}, "furn_sofa": {"Диван_ткань": 7000},
            "furn_carpet": {"Ковёр_шерсть": 6000}, "furn_hotplate": {"Спираль_нихром": 1400}}
# кровати: верх рамы яруса (сетка на 12 мм ниже), панцирная сетка — плоскостью
NETS = {"furn_bed": (0.44,), "furn_bunk_bed": (0.37, 1.32)}
NET_PART = "Сетка_проволока"
CELL = 0.034                 # ромб панцирной сетки, м (build_furniture.bed_mesh)
WIRE = 0.0009                # радиус проволоки сетки
TILE_PERIODS = 2             # плитка текстуры — два шага ромба
GLASS = ("Стекло",)          # прозрачное (полка); кинескоп — непрозрачное стекло, как в каталоге
RIM = {"furn_carpet": (0.6, 0.5)}  # блеск ворса в Godot (rim, rim_tint) — карточка CP-WOL-RED


def tris(me) -> int:
    return sum(len(p.vertices) - 2 for p in me.polygons)


def part(name: str) -> str:
    return name.split(".")[0]


def finish(code: str) -> dict:
    return next(f for f in json.load(open(CATALOG, encoding="utf-8"))["finishes"] if f["code"] == code)


def decimate(ob, target: int) -> None:
    n = tris(ob.data)
    if n <= target:
        return
    md = ob.modifiers.new("dec", "DECIMATE")
    md.decimate_type = "COLLAPSE"
    md.ratio = max(0.002, target / n)
    md.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    ob.modifiers.remove(md)
    old = ob.data
    ob.data = me
    bpy.data.meshes.remove(old)


def maps_material(name, maps_dir, game, glass=False):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        if n.type not in ("OUTPUT_MATERIAL", "BSDF_PRINCIPLED"):
            nt.nodes.remove(n)
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def img(suffix, non_color):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = bpy.data.images.load(f"{maps_dir}/{game}_{suffix}.png", check_existing=True)
        n.image.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
        return n
    nt.links.new(img("baseColor", False).outputs["Color"], b.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(img("occlusionRoughnessMetallic", True).outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], b.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], b.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    if glass:
        b.inputs["Alpha"].default_value = 0.3
        m.surface_render_method = "BLENDED"
    return m


def plain_material(name, color, rough, metal):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    return m


# ---------------------------------------------------------------- панцирная сетка: плитка, плоскость, пружины

def net_tile(size: int = 512) -> dict:
    """Плитка панцирной сетки (два шага ромба): проволока двух направлений, одно над другим, с прозрачностью между;
    тускло-оцинкованная (износ этапа 2: «сетка потускнела с ржавыми точками»), ржавые точки, на перехлёстах темнее."""
    cs = CELL * math.sqrt(2) * 1000.0           # шаг линий по x − y, мм
    period = cs * TILE_PERIODS
    px = period / size
    ys, xs = np.mgrid[0:size, 0:size].astype(np.float32) * px
    r = WIRE * 1000.0
    heights, alphas = [], []
    for fam, lift in ((1, 0.9), (-1, -0.9)):
        t = (xs - ys) if fam == 1 else (xs + ys)
        d = np.abs(((t / cs) % 1.0) - 0.5) * cs / math.sqrt(2)     # до оси проволоки, мм
        h = np.sqrt(np.clip(r * r - d * d, 0, None)) + lift * r
        a = np.clip((r - d) / px + 0.5, 0, 1)
        heights.append(np.where(d < r, h, -9.0))
        alphas.append(a)
    height = np.maximum(heights[0], heights[1])
    alpha = np.maximum(alphas[0], alphas[1])
    height = np.where(alpha > 0, height, 0.0)
    # нормаль из высоты (мм на мм), плитка замкнута — разности по кругу
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2 * px)
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2 * px)
    n = np.stack([-gx, gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rng = np.random.default_rng(5)
    noise = rng.random((size // 16 + 2, size // 16 + 2)).astype(np.float32)
    big = np.kron(noise, np.ones((16, 16), np.float32))[:size, :size]
    rust = (rng.random((size, size)) > 0.985).astype(np.float32)
    rust = np.clip(rust + (big > 0.86) * 0.6, 0, 1)
    zn = finish("ZN-WIR-SAT")["base"]
    base = np.array(zn["color"], np.float32) * 0.8                    # потускнела
    col = base * (0.9 + 0.2 * big)[..., None]
    col = col * (1 - rust[..., None] * 0.8) + np.array([0.33, 0.18, 0.09], np.float32) * rust[..., None] * 0.8
    cross = np.minimum(alphas[0], alphas[1])                           # перехлёсты — темнее
    ao = 1.0 - 0.35 * cross
    rough = 0.5 + 0.1 * big + 0.3 * rust
    metal = 0.9 * (1 - rust)
    return {"color": col, "alpha": alpha, "normal": n, "orm": np.stack([ao, rough, metal], -1)}


def save_rgba(path, rgb, alpha=None, non_color=False):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=alpha is not None, float_buffer=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    a = alpha if alpha is not None else np.ones((h, w), np.float32)
    px = np.concatenate([rgb, a[..., None]], -1)[::-1].astype(np.float32)   # Blender — снизу вверх
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def net_material(game: str) -> bpy.types.Material:
    tile = net_tile()
    d = ROOT + "/_asset_src/dorm_furniture/net"
    os.makedirs(d, exist_ok=True)
    save_rgba(f"{d}/net_baseColor.png", tile["color"], tile["alpha"])
    save_rgba(f"{d}/net_normal.png", tile["normal"] * 0.5 + 0.5, non_color=True)
    save_rgba(f"{d}/net_occlusionRoughnessMetallic.png", tile["orm"], non_color=True)
    m = maps_material(f"{game}_сетка", d, "net")
    m.surface_render_method = "DITHERED"
    m.use_backface_culling = False
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    col = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and "baseColor" in n.image.name)
    # прозрачность отсечением (glTF MASK): экспортёр узнаёт его по «больше 0,5» перед Alpha
    cut = nt.nodes.new("ShaderNodeMath")
    cut.operation = "GREATER_THAN"
    cut.inputs[1].default_value = 0.5
    nt.links.new(col.outputs["Alpha"], cut.inputs[0])
    nt.links.new(cut.outputs[0], b.inputs["Alpha"])
    return m


def net_plane(bm, high_verts, z_top: float, nx: int = 24, ny: int = 54) -> None:
    """Плоскость сетки яруса по форме провиса: высота узла — средняя у проволоки high-poly рядом (в плане 30 мм)."""
    mx, my = 0.45 - 0.07, 1.0 - 0.16
    zm = z_top - 0.012
    pts = [v for v in high_verts if abs(v.z - (zm - 0.02)) < 0.07 and abs(v.x) <= mx + 0.002 and abs(v.y) <= my + 0.002]
    kd = KDTree(len(pts))
    for i, v in enumerate(pts):
        kd.insert((v.x, v.y, 0.0), i)
    kd.balance()
    uv = bm.loops.layers.uv.verify()
    period = CELL * math.sqrt(2) * TILE_PERIODS
    grid = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x, y = -mx + 2 * mx * i / nx, -my + 2 * my * j / ny
            near = kd.find_range((x, y, 0.0), 0.03)
            z = sum(pts[k].z for _, k, _ in near) / len(near) if near else zm
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            for lp in f.loops:
                lp[uv].uv = (lp.vert.co.x / period, lp.vert.co.y / period)
    # окантовка — прутья по краям плоскости
    edge = [[grid[j][0].co.copy() for j in range(ny + 1)], [grid[j][nx].co.copy() for j in range(ny + 1)],
            [grid[0][i].co.copy() for i in range(nx + 1)], [grid[ny][i].co.copy() for i in range(nx + 1)]]
    return edge


def tube(bm, path, r: float, sides: int = 4) -> None:
    """Труба по ломаной (без торцов): окантовка, пружины."""
    rings = []
    for k, p in enumerate(path):
        a = path[min(k + 1, len(path) - 1)] - path[max(k - 1, 0)]
        a.normalize()
        s = a.cross(V((0, 0, 1)))
        if s.length < 1e-4:
            s = a.cross(V((1, 0, 0)))
        s.normalize()
        u = s.cross(a)
        rings.append([bm.verts.new(p + (s * math.cos(2 * math.pi * i / sides) + u * math.sin(2 * math.pi * i / sides)) * r)
                      for i in range(sides)])
    for k in range(len(rings) - 1):
        for i in range(sides):
            bm.faces.new((rings[k][i], rings[k][(i + 1) % sides], rings[k + 1][(i + 1) % sides], rings[k + 1][i]))


def springs(bm, z_top: float) -> None:
    """24 пружины яруса (как build_furniture.bed_level): спираль 9 витков по 3 отрезка, проволока трёхгранником."""
    mx0, mx1 = -0.45 + 0.07, 0.45 - 0.07
    hl = 1.0
    zm = z_top - 0.012
    for i in range(12):
        x = mx0 + 0.01 + (mx1 - mx0 - 0.02) * i / 11
        for s in (-1, 1):
            p0, p1 = V((x, s * (hl - 0.16), zm)), V((x, s * (hl - 0.075), z_top - 0.006))
            ax = (p1 - p0)
            ln = ax.length
            ax.normalize()
            side = ax.cross(V((0, 0, 1))).normalized()
            up = side.cross(ax).normalized()
            hook, coil, turns = 0.008, 0.0045, 9
            path = [p0, p0 + ax * hook * 0.6 + up * coil * 0.8]
            n = turns * 3
            for k in range(n + 1):
                t = k / n
                a = 2 * math.pi * turns * t
                path.append(p0 + ax * (hook + (ln - 2 * hook) * t) + (up * math.cos(a) + side * math.sin(a)) * coil)
            path += [p1 - ax * hook * 0.6 + up * coil * 0.8, p1]
            tube(bm, path, 0.0009, sides=3)


def bed_net(game, high, coll):
    """Сетка кровати: плоскости ярусов (свой материал с плиткой) и прутья с пружинами (простой материал)."""
    hv = [high.matrix_world @ v.co for v in high.data.vertices]
    bm_net, bm_wire = bmesh.new(), bmesh.new()
    for z_top in NETS[game]:
        for e in net_plane(bm_net, hv, z_top):
            tube(bm_wire, e, 0.0013, sides=4)
        springs(bm_wire, z_top)
    out = []
    for bm, name, mat in ((bm_net, f"{game}__сетка", net_material(game)),
                          (bm_wire, f"{game}__пружины", plain_material(f"{game}_проволока", (0.42, 0.42, 0.40), 0.55, 0.8))):
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        out.append(ob)
    return out


# ---------------------------------------------------------------- запекание нормалей high → low

def bake_normal(low, highs, size: int, path: str) -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 4
    img = bpy.data.images.new(os.path.basename(path), size, size, alpha=False, float_buffer=False)
    img.generated_color = (0.5, 0.5, 1.0, 1.0)
    img.colorspace_settings.name = "Non-Color"
    for slot in low.material_slots:
        nt = slot.material.node_tree
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
    low.hide_set(False)
    low.select_set(True)
    bpy.context.view_layer.objects.active = low
    ext = max(0.002, max(low.dimensions) * 0.008)
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=ext, max_ray_distance=ext * 3,
                        margin=12, use_clear=True)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    for slot in low.material_slots:
        nt = slot.material.node_tree
        nt.nodes.remove(nt.nodes["bake_target"])


def export(ob, game) -> None:
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.export_scene.gltf(filepath=f"{OUT}/{game}.gltf", export_format="GLTF_SEPARATE", export_texture_dir="textures",
                              use_selection=True, export_yup=True, export_apply=True, export_texcoords=True,
                              export_normals=True, export_materials="EXPORT", export_image_format="WEBP",
                              export_image_quality=90, export_cameras=False, export_lights=False, export_animations=False)


def webp(src: str, dst: str, non_color: bool) -> None:
    img = bpy.data.images.load(src, check_existing=False)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    _ = img.pixels[0]  # картинка грузится лениво — без данных save() не пишет
    img.filepath_raw = dst
    img.file_format = "WEBP"
    img.save()
    bpy.data.images.remove(img)


def build(game: str, coll, game_coll, index: dict) -> None:
    maps_dir = f"{SRC}/{game}"
    highs = [o for o in coll.objects if o.type == "MESH"]
    for h in highs:
        h.matrix_world = Matrix.Identity(4)
    hmat = maps_material(f"{game}__high", maps_dir, game)
    for h in highs:
        h.data.materials.clear()
        h.data.materials.append(hmat)
    mat = maps_material(game, maps_dir, game)
    glass = maps_material(f"{game}_стекло", maps_dir, game, glass=True) if any(part(h.name) in GLASS for h in highs) else None
    parts, extra = [], []
    dec = DECIMATE.get(game, {})
    for h in highs:
        p = part(h.name)
        if game in NETS and p == NET_PART:
            extra += bed_net(game, h, game_coll)
            continue
        me = h.data.copy()
        me.materials.clear()
        me.materials.append(glass if (glass and p in GLASS) else mat)
        ob = bpy.data.objects.new(f"{game}__{p}", me)
        game_coll.objects.link(ob)
        if p in dec:
            decimate(ob, dec[p])
        parts.append(ob)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for ob in parts:
        ob.select_set(True)
    low = parts[0]
    bpy.context.view_layer.objects.active = low
    if len(parts) > 1:
        bpy.ops.object.join()
    low.name = game
    low.data.name = game
    # нормали: у упрощённых — запекание с high (карта Painter в материале high), у остальных — карта Painter как есть
    nmap = f"{ROOT}/_asset_src/dorm_furniture/game_maps/{game}_normal.png"
    os.makedirs(os.path.dirname(nmap), exist_ok=True)
    if dec:
        size = bpy.data.images.load(f"{maps_dir}/{game}_baseColor.png", check_existing=True).size[0]
        bake_normal(low, [h for h in highs if not (game in NETS and part(h.name) == NET_PART)], size, nmap)
        # запечённая — под именем карты предмета (по имени картинки экспортёр называет файл)
        old = bpy.data.images.get(f"{game}_normal.png")
        new = bpy.data.images.load(nmap, check_existing=False)
        new.colorspace_settings.name = "Non-Color"
        for m in low.data.materials:
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image == old:
                    n.image = new
        hmat_users = [m for m in bpy.data.materials if m.name == f"{game}__high"]
        if old is not None and not any(n.type == "TEX_IMAGE" and n.image == old for m in hmat_users for n in m.node_tree.nodes):
            bpy.data.images.remove(old)
        new.name = f"{game}_normal.png"
    if extra:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for ob in [low] + extra:
            ob.select_set(True)
        bpy.context.view_layer.objects.active = low
        bpy.ops.object.join()
    for p in low.data.polygons:
        p.use_smooth = True
    os.makedirs(TEX, exist_ok=True)
    export(low, game)
    # варианты отделки — карты рядом (сетка та же; нормаль — своя у варианта, сетка варианта не упрощалась)
    variants = []
    for d in sorted(os.listdir(SRC)):
        if d.startswith(game + "__"):
            code = d.split("__", 1)[1]
            for suffix, nc in (("baseColor", False), ("occlusionRoughnessMetallic", True), ("normal", True)):
                webp(f"{SRC}/{d}/{game}_{suffix}.png", f"{TEX}/{game}__{code}_{suffix}.webp", nc)
            variants.append(code)
    xs = [v.co for v in low.data.vertices]
    lo = V((min(c.x for c in xs), min(c.z for c in xs), -max(c.y for c in xs)))   # оси Godot: y — вверх, z = −y
    hi = V((max(c.x for c in xs), max(c.z for c in xs), -min(c.y for c in xs)))
    index[game] = {"file": f"res://assets/models/dorm/furniture/{game}.gltf", "triangles": tris(low.data),
                   "aabb": {"center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)],
                            "size": [round(hi[i] - lo[i], 4) for i in range(3)]},
                   "material": game, "variants": variants}
    if game in RIM:
        index[game]["rim"] = list(RIM[game])
    print("GAME", game, tris(low.data), "треуг., варианты", variants, flush=True)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = set(argv)
    top = bpy.data.collections["Развёртка_v01"]
    top.hide_viewport = False
    game_coll = bpy.data.collections.get("Игровая_v01") or bpy.data.collections.new("Игровая_v01")
    if game_coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(game_coll)
    os.makedirs(OUT, exist_ok=True)
    idx_path = f"{OUT}/furniture.json"
    index = json.load(open(idx_path, encoding="utf-8")) if os.path.exists(idx_path) else {}
    for coll in top.children:
        if only and coll.name not in only:
            continue
        coll.hide_viewport = False
        coll.hide_render = False
        build(coll.name, coll, game_coll, index)
    with open(idx_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
        f.write("\n")
    out = bpy.data.filepath.replace("_uv_v01.blend", "_game_v01.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out, copy=True, compress=True)
    print("saved", out)


if __name__ == "__main__":
    main()
