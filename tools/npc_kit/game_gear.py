"""Снаряжение NPC — игровая версия: ретопология LOD0, развёртка, запекание карт с принятого исходника, LOD1–2.

Решения владельца 2026-10-22: «с ретопологии всего, начиная с персонажа» (персонаж — game_lp.py); бюджет NPC в полном
снаряжении 60 тыс. треугольников: броня до 12 тыс., шлем до 5, рюкзак до 10, подсумки ~1; три LOD (100/40/12 %);
снаряжение — карта 2K на вещь.

Приём (как у мародёра): исходник не трогается; каждая деталь вещи упрощается до своей доли бюджета; тонкое (винты,
заклёпки, велкро, ряды MOLLE, зубцы молний) в игровой сетке не нужно — запекается в карту поверхности под ним; все
детали вещи — одна сетка и одна карта (цвет, нормали, ORM); стекло — отдельной деталью с прозрачным материалом.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/game_gear.py -- <вещь> [deliver=<папка>]
  вещь: helmets
→ _asset_src/npc_kit/game/<вещь>_game.blend, карты — _asset_src/npc_kit/game/maps/<деталь>_{color,normal,orm}.png
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import game_lp as gl  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = gl.OUT
MAPS = gl.MAPS
DROP = 0                      # деталь не идёт в игровую сетку — только в карты

# вещь: исходник, [(игровая деталь, {деталь исходника: треугольников или DROP}, карта, луч м)], стекло {исходник: игровая}
ITEMS = {
    "helmets": ("helmets/helmets_tex.blend", [
        ("G_Helmet_Simple", {"Helmet_Simple_Shell": 3000, "Helmet_Simple_Liner": 700, "Helmet_Simple_Strap": 500,
                             "Helmet_Simple_Rivets": DROP, "Helmet_Simple_Buckle": 120}, 2048, 0.006),
        ("G_Helmet_Mid", {"Helmet_Mid_Shell": 1900, "Helmet_Mid_Cover_Hem": 600, "Helmet_Mid_NVG_Mount": 900,
                          "Helmet_Mid_Harness": 900, "Helmet_Mid_Buckles": 300, "Helmet_Mid_Velcro": DROP,
                          "Helmet_Mid_Screws": DROP}, 2048, 0.006),
        ("G_Helmet_Top", {"Helmet_Top_Shell": 1400, "Helmet_Top_Rails": 800, "Helmet_Top_NVG_Mount": 800,
                          "Helmet_Top_Harness": 800, "Helmet_Top_Edge_Trim": 500, "Helmet_Top_Hardware": 300,
                          "Helmet_Top_Flashlight": 192, "Helmet_Top_Velcro": DROP, "Helmet_Top_Screws": DROP}, 2048, 0.006),
    ], {"Helmet_Top_Visor": ("G_Helmet_Top_Visor", 400)}, "Шлемы"),
    # броня: велкро — в карты; плита в кармане не видна; клапан кармана плиты — закрытым (ключ «Открыт» снят)
    "armor_poor": ("armor/armor_poor_tex.blend", [
        ("G_Armor_Poor", {"Poor_Panel_Bib_Yoke": 5000, "Poor_Webbing": 3500, "Poor_Belt_Mesh": 1800,
                          "Poor_Buckles": 600, "Poor_Velcro": DROP}, 2048, 0.010),
    ], {}, "Броня_бомжовская"),
    "armor_mid": ("armor/armor_mid_tex.blend", [
        ("G_Armor_Mid", {"Mid_Front_Bag": 2400, "Mid_Back_Bag": 1500, "Mid_Cummerbund": 2000, "Mid_Flap": 900,
                         "Mid_Pocket_Lid": 1000, "Mid_Straps": 900, "Mid_Tabs": 400, "Mid_Shoulder_Pads": 400,
                         "Mid_Buckles": 500, "Mid_Rings": 200, "Mid_MOLLE": 1000, "Mid_Velcro": DROP,
                         "Mid_Plate_Front": DROP}, 2048, 0.010),
    ], {}, "Броня_средняя"),
    "armor_top": ("armor/armor_top_tex.blend", [
        ("G_Armor_Top", {"Top_Collar_Skirts": 2400, "Top_Shoulders": 1200, "Top_Front_Bag": 1600, "Top_Back_Bag": 1000,
                         "Top_Cummerbund": 1400, "Top_Flap": 700, "Top_Pocket_Lid": 700, "Top_Release": 500,
                         "Top_MOLLE": 500, "Top_MOLLE_Extra": 500, "Top_Straps": 500, "Top_Tabs": 300,
                         "Top_Shoulder_Pads": 300, "Top_Buckles": 300, "Top_Rings": 150, "Top_Cable": 150,
                         "Top_Velcro": DROP, "Top_Velcro_Extra": DROP, "Top_Plate_Front": DROP}, 2048, 0.010),
    ], {}, "Броня_крутая"),
    "belt": ("armor/armor_belt_tex.blend", [
        ("G_Armor_Belt", {"Belt_Sleeve": 900, "Belt_Webbing": 300, "Belt_Buckle": 150}, 1024, 0.008),
    ], {}, "Пояс"),
}

# рюкзаки (до 10 тыс. на посадку, карта 2K): у каждой из четырёх посадок своя сетка и карта — мешок между посадками
# не сводится к сдвигу и наклону (складки и продавливание под стропами свои, у рейдового и число вершин другое)
PACK_FITS = ("", "_Poor", "_Mid", "_Top")
PACK_PARTS = {
    "Daypack": ({"Bag": 3500, "Padding": 1800, "Webbing": 1400, "Hardware": 700, "Mesh": 600}, "Рюкзак_городской"),
    "Tourist": ({"Bag": 3500, "Padding": 1600, "Webbing": 1800, "Hardware": 2000, "Mesh": 400, "Molle": 100,
                 "Velcro": 300}, "Рюкзак_туристический"),
    "Raid": ({"Bag": 3500, "Padding": 1500, "Webbing": 1700, "Hardware": 2000, "Mesh": 300, "Molle": 500},
             "Рюкзак_рейдовый"),
}
# мелкие отдельные кусочки (зубцы молний, ~5 мм) упрощение собирает в шипы — из игровой сетки прочь, они в картах
SMALL_PART = {"daypack": 0.012, "tourist": 0.012, "raid": 0.012}
# фурнитура (деталь *_Hardware: фастексы, «лестницы», кольца) — десятки отдельных кусочков; свёртка всей детали до доли
# бюджета (8 % у рейдового) оставляла от брусков пряжек шипы. Поэтому каждый кусочек отдельно: плоские грани брусков —
# планарным упрощением (угол 30°: скругления рёбер по 22,5° уходят в карту нормалей, брусок — коробка с фаской),
# кольца (всё, что после него больше HW_PART_CAP) — свёрткой до потолка; бюджет фурнитуры взят с запасом (2 000 у рейдового
# и туристического при ~1 900 по кусочкам), чтобы общая свёртка до бюджета бруски не трогала
HW_PLANAR_DEG = 30.0
HW_PART_CAP = 64
PACK_PARTS_LOWER = {k.lower() for k in PACK_PARTS}
for _pack, (_parts, _folder) in PACK_PARTS.items():
    ITEMS[_pack.lower()] = ("backpacks/backpacks_tex.blend", [
        (f"G_{_pack}{fit}", {f"{_pack}{fit}_{k}": v for k, v in _parts.items()}, 2048, 0.010) for fit in PACK_FITS
    ], {}, _folder)


def build(item: str) -> Path:
    src, parts, glass, _ = ITEMS[item]
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / src))
    col = kc.collection("GAME_LOD0")
    for game_name, pieces, _, _ in parts:
        made = []
        for name, budget in pieces.items():
            if budget == DROP:
                continue
            o = gl.dup(bpy.data.objects[name], f"W_{name}", col, keep_mods=True)
            if o.data.shape_keys:                              # клапан «Открыт» — игровая сетка закрытая
                o.shape_key_clear()
            gl.apply_mods(o)
            if item in SMALL_PART:
                n = drop_small_parts(o, SMALL_PART[item])
                if n:
                    kc.log(f"    {name}: мелких кусочков в карты — {n}")
            if name.endswith("_Hardware") and item in PACK_PARTS_LOWER:
                before = gl.tris(o)
                simplify_hardware(o)
                kc.log(f"    {name}: фурнитура по кусочкам {before} → {gl.tris(o)} треугольников (бюджет {budget})")
            gl.decimate_to(o, budget)
            made.append(o)
        kc.make_active(made[0])
        for o in made[1:]:
            o.select_set(True)
        bpy.ops.object.join()
        g = made[0]
        g.name = g.data.name = game_name
        smooth(g)
        kc.log(f"  {game_name}: {gl.tris(g)} треугольников из {len(made)} деталей")
    for name, (game_name, budget) in glass.items():
        o = gl.dup(bpy.data.objects[name], game_name, col, keep_mods=True)
        gl.apply_mods(o)
        gl.decimate_to(o, budget)
        smooth(o)
        kc.log(f"  {game_name}: {gl.tris(o)} треугольников (стекло, материал исходника)")
    for game_name, _, size, _ in parts:
        gl.unwrap(bpy.data.objects[game_name], size)
    path = OUT / f"{item}_game.blend"
    OUT.mkdir(parents=True, exist_ok=True)
    kc.save(path)
    return path


def simplify_hardware(o: bpy.types.Object) -> None:
    """Фурнитура по отдельным кусочкам: планарное упрощение (бруски → коробки с фаской), кривое — свёрткой до потолка."""
    kc.make_active(o)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    pieces = [x for x in bpy.context.selected_objects if x.type == "MESH"]
    for x in pieces:
        m = x.modifiers.new("Planar", "DECIMATE")
        m.decimate_type = "DISSOLVE"
        m.angle_limit = math.radians(HW_PLANAR_DEG)
        m.delimit = set()
        gl.apply_mods(x)
        gl.decimate_to(x, HW_PART_CAP)
    kc.make_active(o)
    for x in pieces:
        x.select_set(True)
    bpy.ops.object.join()


def drop_small_parts(o: bpy.types.Object, diag: float) -> int:
    """Убрать отдельные кусочки сетки с габаритом меньше diag (м); остаются в исходнике — в картах."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    seen, dead = set(), []
    for v in bm.verts:
        if v.index in seen:
            continue
        stack, part = [v], []
        seen.add(v.index)
        while stack:
            a = stack.pop()
            part.append(a)
            for e in a.link_edges:
                b = e.other_vert(a)
                if b.index not in seen:
                    seen.add(b.index)
                    stack.append(b)
        lo = [min(p.co[i] for p in part) for i in range(3)]
        hi = [max(p.co[i] for p in part) for i in range(3)]
        if sum((h - l) ** 2 for h, l in zip(hi, lo)) ** 0.5 < diag:
            dead.append(part)
    for part in dead:
        bmesh.ops.delete(bm, geom=part, context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    return len(dead)


def smooth(o: bpy.types.Object) -> None:
    o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
    if "sharp_face" in o.data.attributes:
        o.data.attributes.remove(o.data.attributes["sharp_face"])
    o.data.update()


def bake(item: str, path: Path) -> None:
    import ucup  # noqa: F401  (стеки UCUPaint исходника)
    _, parts, glass, _ = ITEMS[item]
    bpy.ops.wm.open_mainfile(filepath=str(path))
    items = [(bpy.data.objects[g], tuple(pieces), size, ray, g[2:].lower()) for g, pieces, size, ray in parts]
    # по одной детали: варианты вещи стоят на одном месте (шлемы на голове, посадки рюкзака), и в AO при общем
    # запекании каждый затенялся оболочками соседних
    for it in items:
        gl.bake_set([it], MAPS, ao_distance=0.03)
    for name, (game_name, _) in glass.items():
        o = bpy.data.objects[game_name]
        o.data.materials.clear()
        o.data.materials.append(glass_material())
    gl.make_lods()
    kc.save(path)


def glass_material() -> bpy.types.Material:
    """Стекло как в Godot: полупрозрачное, без преломления (у исходника стекло с толщиной и преломлением — упрощённая
    толщина слипалась, и в Cycles забрало выходило зеркалом)."""
    m = bpy.data.materials.get("GAME_Glass") or bpy.data.materials.new("GAME_Glass")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.62, 0.62, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.04
    bsdf.inputs["Alpha"].default_value = 0.16
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m


# раскладка на просмотр: сдвиг вариантов вещи по x, сдвиг уровня LOD (x, z), фокус камеры по высоте, дальность
LAYOUT = {"helmets": ({"Simple": 0.0, "Mid": 0.45, "Top": 0.9}, (0.0, -0.40), 1.45, 1.1),
          "armor_poor": ({}, (0.75, 0.0), 1.28, 1.4), "armor_mid": ({}, (0.75, 0.0), 1.28, 1.4),
          "armor_top": ({}, (0.75, 0.0), 1.20, 1.5), "belt": ({}, (0.6, 0.0), 0.95, 1.2)}
for _pack in PACK_PARTS:                 # посадки рядом по x (без брони, бомжовская, средняя, крутая), LOD — дальше вбок
    LAYOUT[_pack.lower()] = ({"Poor": 0.6, "Mid": 1.2, "Top": 1.8}, (2.6, 0.0), 1.25, 1.8)


def deliver(item: str, path: Path, folder: Path) -> None:
    import armor_mid as am
    bpy.ops.wm.open_mainfile(filepath=str(path))
    keep = {"GAME_LOD0", "GAME_LOD1", "GAME_LOD2", "99_Studio"}
    for o in list(bpy.data.objects):
        if o.type in ("MESH", "ARMATURE") and not any(c.name in keep for c in o.users_collection):
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name not in keep and not c.objects and not c.children:
            bpy.data.collections.remove(c)
    shift, (lod_dx, lod_dz), focus_z, near = LAYOUT[item]
    for lvl in range(3):
        for o in bpy.data.collections[f"GAME_LOD{lvl}"].objects:
            dx = next((v for k, v in shift.items() if f"_{k}" in o.name), 0.0)
            o.location.x += dx + lod_dx * lvl
            o.location.z += lod_dz * lvl
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    total = {lvl: sum(gl.tris(o) for o in bpy.data.collections[f"GAME_LOD{lvl}"].objects) for lvl in range(3)}
    fits = ("Посадки рюкзака — слева направо: без брони, бомжовская, средняя, крутая (в игре выбирается по броне).\n"
            if item in LAYOUT and item.capitalize() in PACK_PARTS else "")
    readme = (f"Снаряжение «{item}» — ИГРОВАЯ ВЕРСИЯ (ретопология), на просмотр. Решения владельца 2026-10-22: бюджет NPC\n"
              "60 тыс. в полном снаряжении (шлем до 5 тыс., броня до 12, рюкзак до 10), три LOD, карта 2K на вещь.\n"
              f"LOD0 / LOD1 / LOD2 — рядом (всего {total[0]} / {total[1]} / {total[2]} треугольников); варианты вещи —\n"
              "рядом по горизонтали.\n" + fits +
              "Тонкое (винты, заклёпки, велкро) — в картах; стекло — полупрозрачное, как будет в Godot.\n"
              "Карты: цвет, нормали, ORM (R — AO, G — шероховатость, B — металл). Смотреть в Rendered (Cycles).\n"
              "Скрипт: tools/npc_kit/game_gear.py.\n")
    am.deliver(folder, f"{ITEMS[item][3]}_игровые.blend", readme, focus_z=focus_z, near=near)


def main() -> None:
    args = kc.args_after_dashes()
    item = args[0]
    path = OUT / f"{item}_game.blend"
    if "deliver_only" not in args:
        if "bake_only" not in args:
            path = build(item)
        bake(item, path)
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(item, path, Path(dest))


if __name__ == "__main__":
    main()
