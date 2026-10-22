"""NPC и игрок: места под подсумки на броне (решение владельца 2026-10-22: бомжовская 3, средняя 5, крутая 8;
docs/design/gear_v2.md) и подсумки на них — примерочная.

Раскладка (только куда дотянется рука при перезарядке — спереди и по бокам, не на спине):
- бомжовская (3): в ряд на поясе спереди (у неё спереди ряды стропы на поясе);
- средняя (5): 3 на нижнем переднем клапане с MOLLE, по 1 на камербанде спереди-сбоку (35° от бока — ровно сбоку
  под рукой идут нижние стропы рюкзака);
- крутая (8): 4 на переднем клапане (он шире), по 1 на камербанде спереди-сбоку, по 1 на наружной стороне щитков
  бёдер (на щитках MOLLE). Пояс крутой не занят: магазины из поясных подсумков упирались бы в подсумки камербанда.
Большой подсумок (два места) — только на два соседних места спереди; пистолетных — два в одно место (половины).

Место — точка с положением и поворотом на поверхности брони: x — поперёк подсумка, y — наружу, z — вверх; начало —
середина низа задней стороны подсумка. Поверхность под местом — лучами снаружи по брони (только броня), задняя
сторона подсумка встаёт на самую выступающую точку (подсумок не утопает в изгибе). Проверка печатает пересечения:
подсумки между собой и с бронёй, с телом и одеждой, с лямками рюкзаков той же посадки — всё с магазином на 45
(самый длинный).

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/pouch_places.py -- [render] [deliver=<папка>]
→ _asset_src/npc_kit/pouches/pouch_places.blend, places.json (читает примерочную брони, pouches.blend, backpacks.blend)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "pouches"
VERSION = "v01"
GAP = 0.001                     # задняя сторона подсумка — над самой выступающей точкой брони
WALL_Z = 0.004                  # магазин в подсумке стоит на дне (как в pouches.py: WALL + 1,5 мм)

# место: (имя, вид, параметры) — front: x и низ z; side: угол вокруг торса (0 — левый бок +X, −90 — перёд) и низ z;
# thigh: угол вокруг оси бедра (−1 / +1 — левое / правое) и низ z. Пары под большой подсумок — соседние спереди.
LAYOUT = {
    "poor": {"armor": "06_Armor_Poor", "places": [
        ("Пояс 1", "front", (-0.095, 1.112)), ("Пояс 2", "front", (0.0, 1.112)), ("Пояс 3", "front", (0.095, 1.112))],
        "pairs": [(0, 1), (1, 2)]},
    "mid": {"armor": "06_Armor_Mid", "places": [
        ("Перёд 1", "front", (-0.092, 1.106)), ("Перёд 2", "front", (0.0, 1.106)), ("Перёд 3", "front", (0.092, 1.106)),
        ("Бок левый", "side", (-35.0, 1.118)), ("Бок правый", "side", (-145.0, 1.118))],
        "pairs": [(0, 1), (1, 2)]},
    "top": {"armor": "06_Armor_Top", "places": [
        ("Перёд 1", "front", (-0.137, 1.108)), ("Перёд 2", "front", (-0.046, 1.108)), ("Перёд 3", "front", (0.046, 1.108)),
        ("Перёд 4", "front", (0.137, 1.108)), ("Бок левый", "side", (-35.0, 1.120)), ("Бок правый", "side", (-145.0, 1.120)),
        ("Бедро левое", "thigh", (1.0, -28.0, 0.715)), ("Бедро правое", "thigh", (-1.0, -152.0, 0.715))],
        "pairs": [(0, 1), (1, 2), (2, 3)]},
    # пояс с подсумками — вместо брони (решение владельца): 2 места спереди-сбоку; подсумок висит — верх у верхнего края
    # пояса, корпус ниже; соседних мест нет — большой подсумок на пояс не встаёт
    "belt": {"armor": "06_Armor_Belt", "places": [
        ("Пояс левый", "side", (-50.0, 0.883)), ("Пояс правый", "side", (-130.0, 0.883))], "pairs": []},
}
TIER_RU = {"poor": "бомжовская", "mid": "средняя", "top": "крутая", "belt": "пояс"}
POUCH_OBJS = {"rifle": ("Pouch_Rifle_Body", "Pouch_Rifle_Webbing", "Pouch_Rifle_Velcro", "Pouch_Rifle_Snaps", "Pouch_Rifle_Tab"),
              "pistol": ("Pouch_Pistol_Body", "Pouch_Pistol_Webbing", "Pouch_Pistol_Velcro", "Pouch_Pistol_Snaps",
                         "Pouch_Pistol_Tab"),
              "big": ("Pouch_Big_Body", "Pouch_Big_Webbing", "Pouch_Big_Velcro", "Pouch_Big_Snaps", "Pouch_Big_Flap")}
MAGS = ("Mag_VERAS54_30", "Mag_VERAS54_45", "Mag_Glock_17", "Mag_PM_8", "Mag_VERAS54_Drum60")


def bvh_world(objs: list[bpy.types.Object]) -> BVHTree:
    co, faces = [], []
    for o in objs:
        b = len(co)
        co += [o.matrix_world @ v.co for v in o.data.vertices]
        faces += [[b + i for i in p.vertices] for p in o.data.polygons]
    return BVHTree.FromPolygons(co, faces)


def append(path: Path, names: tuple[str, ...]) -> dict[str, bpy.types.Object]:
    with bpy.data.libraries.load(str(path)) as (src, dst):
        dst.objects = [n for n in src.objects if n in names]
    return {o.name.split(".")[0]: o for o in dst.objects}


# ---------- места ----------

MAG_UP = 0.15                   # сколько над подсумком торчит самый длинный магазин (на 45)


def place_frame(bvh: BVHTree, kind: str, par: tuple, W: float, H: float, thigh_c: dict) -> tuple[Matrix, bool]:
    """Рамка места. Лучи снаружи по ширине подсумка и по высоте — от низа до верха торчащего магазина — дают профиль
    брони и одежды (самая выступающая точка на каждой высоте). Задняя сторона подсумка — прямая, касающаяся профиля:
    низ прижат к броне, верх наклонён наружу, чтобы торчащий магазин не упирался в броню выше (нагрудник, язычки,
    трос сброса). Возвращает (рамка, зеркально): у боковых и бедренных слева подсумок зеркальный — изгиб длинного
    магазина уходит назад, а не в соседний подсумок спереди."""
    up = Vector((0, 0, 1))
    if kind == "front":
        x, z0 = par
        out = Vector((0, -1, 0))
        base = Vector((x, 0.0, 0.0))
    elif kind == "side":
        a, z0 = par
        out = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        base = Vector((0.0, -0.01, 0.0))
    else:
        sgn, a, z0 = par
        out = Vector((math.cos(math.radians(a)), math.sin(math.radians(a)), 0))
        cx, cy = thigh_c[sgn]
        base = Vector((cx, cy, 0.0))
    side_t = out.cross(up).normalized()
    rows = []                                             # (высота, наибольшее «наружу»)
    nrms = []
    for j in range(16):
        z = z0 + (H + MAG_UP) * j / 15
        best = None
        for i in range(7):
            du = (i / 6 - 0.5) * W
            o = base + side_t * du + out * 0.6 + up * z
            hit = bvh.ray_cast(o, -out, 1.2)
            if hit[0] is None:
                continue
            d = (hit[0] - base).dot(out)
            best = d if best is None else max(best, d)
            if z <= z0 + H:
                nrms.append(hit[1] if hit[1].dot(out) > 0 else -hit[1])
        if best is not None:
            rows.append((z, best))
    if not nrms:
        raise RuntimeError(f"место {kind} {par}: лучи не попали в броню")
    # прямая d(z) = a + k (z − z0) не глубже профиля нигде; из таких — с наименьшим зазором у самого подсумка
    best = None
    for k1000 in range(-100, 401, 5):
        k = k1000 / 1000
        a = max(d - k * (z - z0) for z, d in rows)
        gap = sum(a + k * (z - z0) - d for z, d in rows if z <= z0 + H)
        if best is None or gap < best[0]:
            best = (gap, a, k)
    _, a, k = best
    # поворот вокруг вертикали — по средней нормали у самого подсумка (броня изогнута поперёк)
    n_avg = sum(nrms, Vector())
    n_h = Vector((n_avg.x, n_avg.y, 0.0)).normalized()
    if n_h.dot(out) < 0.5:
        n_h = out
    side_h = n_h.cross(up).normalized()
    zax = (up + n_h * k).normalized()
    n = (n_h - up * k).normalized()
    xax = n.cross(zax).normalized()
    origin = base + side_t * 0.0 + out * (a + GAP) + up * z0
    if kind == "front":
        origin = Vector((base.x, -(a + GAP), z0))
    _ = side_h
    mirror = kind != "front" and xax.dot(Vector((0, -1, 0))) > 0.3
    if mirror:
        xax = -xax
    m = Matrix(((xax.x, n.x, zax.x, origin.x), (xax.y, n.y, zax.y, origin.y), (xax.z, n.z, zax.z, origin.z), (0, 0, 0, 1)))
    return m, mirror


def put(src: bpy.types.Object, col: bpy.types.Collection, m: Matrix, local: Vector, name: str,
        own_data: bool = False) -> bpy.types.Object:
    o = src.copy()
    if own_data:
        o.data = src.data.copy()
    o.name = name
    col.objects.link(o)
    o.matrix_world = m @ Matrix.Translation(local)
    return o


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"armor_fitting_{kc.VERSION}.blend"))
    with bpy.data.libraries.load(str(kc.WORK / "armor" / "armor_belt.blend")) as (lsrc, ldst):
        ldst.collections = ["06_Armor_Belt"]
    bpy.context.scene.collection.children.link(ldst.collections[0])
    names = tuple(n for v in POUCH_OBJS.values() for n in v) + MAGS
    src = append(OUT / "pouches.blend", names)
    hold = kc.collection("98_Pouch_Sources")
    for o in src.values():
        hold.objects.link(o)
        o.location = (0, 0, 0)
        if o.type == "MESH" and o.data.shape_keys:          # язычки — застёгнуты по магазину на 30
            for kb in o.data.shape_keys.key_blocks[1:]:
                kb.value = 0.0
    bpy.context.view_layer.layer_collection.children["98_Pouch_Sources"].exclude = True
    dims = {}
    for kind, objs in POUCH_OBJS.items():
        body = src[objs[0]]
        xs = [v.co.x for v in body.data.vertices]
        ys = [v.co.y for v in body.data.vertices]
        zs = [v.co.z for v in body.data.vertices]
        dims[kind] = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    kc.log("  подсумки (ш, т, в):", {k: tuple(round(x * 1000) for x in v) for k, v in dims.items()})
    # оси бёдер — середины сечений брюк
    pants = bpy.data.objects["Pants"]
    pc = [pants.matrix_world @ v.co for v in pants.data.vertices]
    thigh_c = {}
    for sgn in (1.0, -1.0):
        sl = [p for p in pc if abs(p.z - 0.78) < 0.01 and p.x * sgn > 0.02]
        thigh_c[sgn] = ((min(p.x for p in sl) + max(p.x for p in sl)) / 2, (min(p.y for p in sl) + max(p.y for p in sl)) / 2)
    body_objs = [bpy.data.objects[n] for n in ("Jacket", "Pants", "Balaclava") if n in bpy.data.objects]
    # для проверки — куртка без рукавов: руки в A-позе не игровая поза, их обходит анимация
    jacket = bpy.data.objects["Jacket"]
    gi = {g.index for g in jacket.vertex_groups if g.name.startswith(("piece_sleeve", "piece_cuff"))}
    sleeve = {v.index for v in jacket.data.vertices if any(g.group in gi and g.weight > 0.5 for g in v.groups)}
    co, faces = [], []
    for o in body_objs:
        b = len(co)
        co += [o.matrix_world @ v.co for v in o.data.vertices]
        faces += [[b + i for i in pp.vertices] for pp in o.data.polygons
                  if not (o is jacket and any(i in sleeve for i in pp.vertices))]
    body_bvh = BVHTree.FromPolygons(co, faces)
    places_json = {}
    Wr, Tr, Hr = dims["rifle"]
    for tier, spec in LAYOUT.items():
        armor_objs = [o for o in bpy.data.collections[spec["armor"]].all_objects if o.type == "MESH"]
        abvh = bvh_world(armor_objs)
        col = kc.collection(f"09_Pouches_{tier.capitalize()}")
        frames = []
        recs = []
        env = bvh_world(armor_objs + [o for o in body_objs if o.name != "NPC_Body"])
        for k, (name, kind, par) in enumerate(spec["places"]):
            m, mirror = place_frame(env, kind, par, Wr, Hr, thigh_c)
            frames.append(m)
            e = bpy.data.objects.new(f"{tier.capitalize()}_Место_{k + 1}", None)
            e.empty_display_type = "ARROWS"
            e.empty_display_size = 0.03
            e.matrix_world = m
            e["место"] = name
            e["номер"] = k + 1
            e["зеркально"] = mirror
            col.objects.link(e)
            for on in POUCH_OBJS["rifle"]:
                put(src[on], col, m, Vector((0, Tr / 2, 0)), f"{tier.capitalize()}_{k + 1}_{on[6:]}")
            put(src["Mag_VERAS54_30"], col, m, Vector((0, Tr / 2, WALL_Z)), f"{tier.capitalize()}_{k + 1}_Mag30")
            loc, rot, _ = (m @ Matrix.Scale(-1.0, 4, (1.0, 0.0, 0.0)) if mirror else m).decompose()
            recs.append({"номер": k + 1, "имя": name, "вид": kind, "положение": [round(c, 4) for c in loc],
                         "поворот_wxyz": [round(c, 5) for c in rot], "зеркально": mirror})
        # смешанный пример: большой на местах 1–2, два пистолетных (Глок и ПМ) в соседнем; на поясе — пистолетные в месте 1
        mix = kc.collection(f"09_Pouches_{tier.capitalize()} · смешанный")
        if spec["pairs"]:
            a, b = spec["pairs"][0]
            mab = frames[a].lerp(frames[b], 0.5)
            Tb = dims["big"][1]
            for on in POUCH_OBJS["big"]:
                put(src[on], mix, mab, Vector((0, Tb / 2, 0)), f"{tier.capitalize()}_Mix_{on[6:]}")
            put(src["Mag_VERAS54_Drum60"], mix, mab, Vector((0, Tb / 2, WALL_Z)), f"{tier.capitalize()}_Mix_Drum")
        k3 = spec["pairs"][-1][1] if spec["pairs"] else 0
        Wp, Tp, _ = dims["pistol"]
        for half, (mag, key) in zip((-1, 1), (("Mag_Glock_17", None), ("Mag_PM_8", "ПМ"))):
            for on in POUCH_OBJS["pistol"]:
                o = put(src[on], mix, frames[k3], Vector((half * (Wp / 2 + 0.001), Tp / 2, 0)),
                        f"{tier.capitalize()}_Mix_P{half + 2}_{on[6:]}", own_data=on.endswith("Tab"))
                if on.endswith("Tab") and key:
                    o.data.shape_keys.key_blocks[key].value = 1.0
            put(src[mag], mix, frames[k3], Vector((half * (Wp / 2 + 0.001), Tp / 2, WALL_Z)), f"{tier.capitalize()}_Mix_{mag}")
        bpy.context.view_layer.layer_collection.children[mix.name].hide_viewport = True
        mix.hide_render = True
        places_json[tier] = {"броня": spec["armor"], "места": recs,
                             "пары_под_большой": [[a + 1, b + 1] for a, b in spec["pairs"]]}
        check(tier, col, frames, src, armor_objs, body_bvh, Tr)
    (OUT / "places.json").write_text(json.dumps(places_json, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    show_tier("mid")
    kc.save(OUT / "pouch_places.blend")
    if "render" in args:
        render()
        show_tier("mid")
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        import armor_mid as am
        show_tier("mid")
        am.deliver(Path(dest), f"Подсумки_на_броне_{VERSION}.blend", README.format(ver=VERSION), focus_z=1.10, near=0.75)


def check(tier: str, col: bpy.types.Collection, frames: list[Matrix], src: dict, armor_objs: list, body_bvh: BVHTree,
          Tr: float) -> None:
    """Пересечения на худший случай — автоматный подсумок с магазином на 45 в каждом месте."""
    bvhs = []
    for m in frames:
        objs = []
        for on in ("Pouch_Rifle_Body", "Mag_VERAS54_45"):
            o = src[on]
            mw = m @ Matrix.Translation(Vector((0, Tr / 2, WALL_Z if on.startswith("Mag") else 0.0)))
            co = [mw @ v.co for v in o.data.vertices]
            objs.append((co, [list(p.vertices) for p in o.data.polygons]))
        co, faces = [], []
        for c, f in objs:
            b = len(co)
            co += c
            faces += [[b + i for i in ff] for ff in f]
        bvhs.append(BVHTree.FromPolygons(co, faces))
    abvh = bvh_world(armor_objs)
    msg = []
    for i in range(len(bvhs)):
        for j in range(i + 1, len(bvhs)):
            if bvhs[i].overlap(bvhs[j]):
                msg.append(f"места {i + 1} и {j + 1} пересекаются")
        if bvhs[i].overlap(abvh):
            parts = [o.name for o in armor_objs if bvhs[i].overlap(bvh_world([o]))]
            msg.append(f"место {i + 1} — в броне ({len(bvhs[i].overlap(abvh))} пар граней: {', '.join(parts)})")
        if bvhs[i].overlap(body_bvh):
            msg.append(f"место {i + 1} — в теле/одежде ({len(bvhs[i].overlap(body_bvh))})")
    # лямки рюкзаков этой посадки
    packs = kc.WORK / "backpacks" / "backpacks.blend"
    suffix = {"poor": "_Poor", "mid": "_Mid", "top": "_Top", "belt": ""}[tier]      # пояс — посадка «без брони»
    want = tuple(f"{p}{suffix}_{part}" for p in ("Daypack", "Tourist", "Raid") for part in ("Padding", "Webbing", "Hardware"))
    got = append(packs, want)
    for p in ("Daypack", "Tourist", "Raid"):
        pobjs = [o for n, o in got.items() if n.startswith(p)]
        pb = bvh_world(pobjs)
        hit = [k + 1 for k, b in enumerate(bvhs) if b.overlap(pb)]
        if hit:
            msg.append(f"лямки/стропы рюкзака {p} проходят через места {hit}")
    for o in got.values():
        bpy.data.objects.remove(o, do_unlink=True)
    kc.log(f"  броня {TIER_RU[tier]}: {len(frames)} мест; " + ("; ".join(msg) if msg else "пересечений нет"))


def show_tier(tier: str | None) -> None:
    vl = bpy.context.view_layer.layer_collection
    for t, spec in LAYOUT.items():
        on = t == tier
        vl.children[spec["armor"]].hide_viewport = not on
        bpy.data.collections[spec["armor"]].hide_render = not on
        cn = f"09_Pouches_{t.capitalize()}"
        vl.children[cn].hide_viewport = not on
        bpy.data.collections[cn].hide_render = not on


def render() -> None:
    import numpy as np
    kc.studio()
    kc.gpu_cycles(96)
    scene = bpy.context.scene
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    out = kc.WORK / "previews"
    views = {"front34": ((0.75, -1.35, 1.35), (0.0, -0.05, 1.05)), "side": ((1.45, -0.25, 1.20), (0.0, -0.05, 1.05))}
    paths = []
    for tier in LAYOUT:
        show_tier(tier)
        for v, (pos, tgt) in views.items():
            p = out / f"pouch_places_{tier}_{v}.png"
            kc.render(kc.camera("C_pp_" + v, pos, tgt, 50), p, (700, 900), 96)
            paths.append(p)
    imgs = [bpy.data.images.load(str(p)) for p in paths]
    w, h = imgs[0].size
    grid = np.zeros((h, w * len(imgs), 4), np.float32)
    for k, im in enumerate(imgs):
        px = np.empty(w * h * 4, np.float32)
        im.pixels.foreach_get(px)
        grid[:, k * w:(k + 1) * w] = px.reshape(h, w, 4)
    res = bpy.data.images.new("pouch_places_grid", w * len(imgs), h, alpha=False)
    res.pixels.foreach_set(grid.ravel())
    s = scene.render.image_settings
    s.file_format = "JPEG"
    s.quality = 90
    s.color_mode = "RGB"
    res.save_render(str(out / f"pouch_places_{VERSION}.jpg"))


README = (
    "Места под подсумки на броне — {ver} на согласование: бомжовская 3, средняя 5, крутая 8 (спереди и по бокам —\n"
    "куда дотянется рука), пояс с подсумками вместо брони — 2 (06_Armor_Belt / 09_Pouches_Belt). Во всех местах — автоматный подсумок с магазином ВЕРАС-54 на 30. Места — пустышки\n"
    "<броня>_Место_N (стрелки: y — наружу, z — вверх). Коллекции 09_Pouches_<броня> и 06_Armor_<броня> включать\n"
    "вместе; «· смешанный» — пример: большой подсумок с барабаном на двух соседних местах спереди и два пистолетных\n"
    "(Глок и ПМ) в одном месте. Смотреть в Rendered (Cycles). Скрипт: tools/npc_kit/pouch_places.py.\n")


if __name__ == "__main__":
    main()
