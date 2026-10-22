"""NPC: текстуры рюкзаков, подсумков и пояса — нативный UCUPaint 2.4.9 (формы приняты владельцем 2026-10-22).

Тем же приёмом, что принятая броня (armor_texture.py): ткань с плетением 4K, выгорание, затёртые кромки, пыль,
грязь во впадинах и книзу; стропа, велкро, сетка, фурнитура — рецептами брони со своими цветами.
Расцветки (решения владельца 2026-10-22):
- городской — тёмно-серый (графит, чёрные стропа и молнии);
- туристический — по образцу владельца: рейнджер-грин, сетка темнее, пряжки серо-зелёные (скатки нет — убрана владельцем);
- рейдовый — «как тактические рюкзаки: ярко-зелёные, насыщенные, камуфляжные» (владелец, вместо прежнего серо-зелёного
  ношеного): свой лесной камуфляж «Чаща» (tools/npc_kit/gen_pack_camo.py), стропа и велкро оливковые, износ обычный;
- подсумки и пояс — койот.
Маски «где» — атрибуты брони (ArmorEdge/Up/Low/Under), «брызги спереди» — на лицевой стороне (у рюкзака и подсумка
это +Y, а не перёд тела); AO — только по своей детали.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/gear_texture.py -- packs|pouches|belt [shots] [deliver=<папка>]
→ _asset_src/npc_kit/backpacks/backpacks_tex.blend, pouches/pouches_tex.blend, armor/armor_belt_tex.blend
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_texture as at  # noqa: E402
import helmet_texture as ht  # noqa: E402
import kit_common as kc  # noqa: E402
from ucup import H, U, image, image_layer, layer, noise, owner_mask, srgb, stack, vmask, ao_mask  # noqa: E402

at.PALETTE.update({
    # под выгоранием и пылью основа светлеет на глаз — цвета взяты темнее образцов
    "day": {"cordura": srgb(40, 42, 45), "webbing": srgb(24, 25, 27), "velcro": srgb(34, 35, 38),
            "plastic": srgb(20, 20, 21), "mesh": srgb(26, 27, 30)},
    "tour": {"cordura": srgb(54, 58, 43), "webbing": srgb(51, 55, 41), "velcro": srgb(55, 59, 45),
             "plastic": srgb(86, 94, 88), "mesh": srgb(38, 42, 30)},
    "raid": {"cordura": srgb(60, 88, 26), "webbing": srgb(40, 54, 24), "velcro": srgb(42, 56, 26),
             "plastic": srgb(26, 28, 24), "mesh": srgb(38, 46, 30)},
    "coyote": {"cordura": srgb(114, 96, 70), "webbing": srgb(102, 86, 62), "velcro": srgb(108, 92, 68),
               "plastic": srgb(48, 44, 37), "mesh": srgb(96, 82, 60)},
})
TIER_OF = {"Daypack": "day", "Tourist": "tour", "Raid": "raid", "Pouch": "coyote", "Belt": "coyote"}
TEX_GEN = at.ROOT / "_asset_src" / "npc_kit" / "tex_gen"
CAMO_RAID = TEX_GEN / "camo_chascha_4k.png"
MOLLE_PITCH = 0.0381


def tree_of(mat: bpy.types.Material):
    return next(n.node_tree for n in mat.node_tree.nodes if n.type == "GROUP" and n.node_tree and n.node_tree.yp.is_ypaint_node)


def gear_masks(objs: list[bpy.types.Object]) -> None:
    """Маски брони по всей вещи (низ — у дна вещи); «брызги» — на лицевой стороне (+Y) внизу."""
    zs = [(o.matrix_world @ Vector(c)).z for o in objs for c in o.bound_box]
    z_lo, z_hi = min(zs), max(zs)
    for o in objs:
        if o.type != "MESH" or not o.data.polygons:
            continue
        at.geometry_masks(o, z_lo, z_hi)
        me = o.data
        key = me.shape_keys.key_blocks.get("Без складок") if me.shape_keys else None
        if key is not None:
            # мятая ткань: выпуклость складок — это гребни (лёгкая потёртость), а не кромки; кромки — по гладкой форме
            nv = len(me.vertices)
            crest = np.empty(nv * 4, np.float32)
            me.color_attributes["ArmorEdge"].data.foreach_get("color", crest)
            co = np.empty(nv * 3, np.float32)
            key.data.foreach_get("co", co)
            at.geometry_masks(o, z_lo, z_hi, edge_co=co.reshape(nv, 3))
            edge = np.empty(nv * 4, np.float32)
            me.color_attributes["ArmorEdge"].data.foreach_get("color", edge)
            val = np.clip(crest.reshape(nv, 4)[:, 0] - edge.reshape(nv, 4)[:, 0], 0.0, 1.0)
            a = me.color_attributes.get("FoldCrest") or me.color_attributes.new(name="FoldCrest", type="BYTE_COLOR",
                                                                                domain="POINT")
            rgba = np.ones((nv, 4), np.float32)
            rgba[:, :3] = val[:, None]
            a.data.foreach_set("color", rgba.ravel())
        n = len(me.vertices)
        nrm = np.empty(n * 3, np.float32)
        me.vertex_normals.foreach_get("vector", nrm)
        mw = np.array(o.matrix_world, np.float32)
        wn = nrm.reshape(n, 3) @ np.linalg.inv(mw[:3, :3])
        wn /= np.maximum(np.linalg.norm(wn, axis=1), 1e-9)[:, None]
        low = np.empty(n * 4, np.float32)
        me.color_attributes["ArmorLow"].data.foreach_get("color", low)
        front = at.smoothstep((wn[:, 1] - 0.3) / 0.5) * low.reshape(n, 4)[:, 0]
        a = me.color_attributes["ArmorFront"]
        rgba = np.ones((n, 4), np.float32)
        rgba[:, :3] = front[:, None]
        a.data.foreach_set("color", rgba.ravel())
        me.update()


def mat_cordura(mat: bpy.types.Material, tier: str) -> None:
    if tier != "raid":
        at.mat_cordura(mat, tier)
        return
    # рейдовый — сочный лесной камуфляж; износ обычный, без выцветания до серого (владелец: «блеклый»)
    col = at.PALETTE[tier]["cordura"]
    t, _ = stack(mat, col, 0.0, 0.86)
    layer(t, "00 • Ткань", col, 0.0, 0.86)
    image_layer(t, "01 • Камуфляж «Чаща» (свой, gen_pack_camo.py)", image(CAMO_RAID, True), "Color", 0.8)
    lay = layer(t, "05 • Неровный прокрас (темнее пятнами)", at.GRIME, None, None, 0.08)
    noise(lay, "Пятна прокраса 5–15 см", 9.0, 0.35, 0.80)
    image_layer(t, "10 • Плетение кордуры (Poly Haven book_pattern)",
                image(at.TEX / "book_pattern" / "book_pattern_nor_gl_4k.png", False), "Normal", 0.30)
    image_layer(t, "11 • Микрошероховатость плетения", image(at.TEX / "book_pattern" / "book_pattern_rough_4k.png", False),
                "Roughness", 0.30, amount=0.30)
    at.wear_fabric(t, 0.86, dirt_amount=0.7, edge_amount=0.12)
    lay = layer(t, "32 • Потёртость на гребнях складок", at.FADE, None, 0.9, 0.10)
    vmask(lay, "FoldCrest")
    H.reconnect(U, t)


def mat_molle(mat: bpy.types.Material, tier: str) -> None:
    """Ряды MOLLE (по фото владельца): плоская тканая стропа 25 мм, у рейдового — с тем же камуфляжем, что ткань
    (напечатан на стропе), поперёк — закрепки через 38 мм (tools/npc_kit/gen_molle_tack.py), делят её на прямоугольники."""
    col = at.PALETTE[tier]["cordura" if tier == "raid" else "webbing"]
    t, _ = stack(mat, col, 0.0, 0.8)
    layer(t, "00 • Стропа MOLLE, нейлон", col, 0.0, 0.8)
    if tier == "raid":
        image_layer(t, "01 • Камуфляж «Чаща» на стропе (свой кусок ткани — рисунок не совпадает)", image(CAMO_RAID, True), "Color", 0.71,
                    box=True)
        layer(t, "02 • Стропа плотнее ткани — краска чуть темнее", at.GRIME, None, None, 0.12)
    image_layer(t, "10 • Саржевое плетение стропы (Poly Haven denim_fabric_05)",
                image(at.TEX / "denim_fabric_05" / "denim_fabric_05_nor_gl_4k.png", False), "Normal", 0.08)
    image_layer(t, "20 • Закрепки через 38 мм (рельеф)", image(TEX_GEN / "molle_tack_height.png", False), "Normal",
                (MOLLE_PITCH, 0.025), bump=0.0007)
    image_layer(t, "21 • Тень в закрепках", image(TEX_GEN / "molle_tack_shade.png", True), "Color", (MOLLE_PITCH, 0.025),
                amount=0.7, blend="MULTIPLY")
    at.wear_fabric(t, 0.8, edge_amount=0.14)
    H.reconnect(U, t)


RECIPES = {
    "Cordura": mat_cordura,
    "Webbing": at.mat_webbing,
    "Velcro": at.mat_velcro,
    "Mesh": at.mat_mesh,
    "Plastic": at.mat_plastic,
    "Metal": at.mat_metal,
    "Molle": mat_molle,
}


def texture(objs_by_owner: dict[str, list[bpy.types.Object]], prefix_mat: str) -> None:
    """Материалы формы (prefix_mat_<вид>) — свои у каждой вещи (<вещь>_<вид>), стек по рецепту её расцветки."""
    for owner, objs in objs_by_owner.items():
        tier = TIER_OF[owner]
        made = {}
        for o in objs:
            for slot in o.material_slots:
                m = slot.material
                if m is None or not (m.name.startswith(prefix_mat + "_") or m.name.startswith(owner + "_")):
                    continue
                kind = m.name.split("_", 1)[1]
                name = f"{owner}_{kind}"
                if name not in made:
                    new = bpy.data.materials.get(name) or m.copy()
                    new.name = name
                    made[name] = (new, kind)
                slot.material = made[name][0]
        for name, (mat, kind) in sorted(made.items()):
            recipe = RECIPES.get(kind)
            if recipe is None:
                kc.log("  материал без рецепта:", name)
                continue
            recipe(mat, tier)
            kc.log("  стек UCUPaint:", name, "| AO только по детали:", ht.local_ao(mat))


def main() -> None:
    args = kc.args_after_dashes()
    what = args[0]
    if what == "packs":
        test = "test" in args                 # проба на backpacks_test.blend (backpacks.py -- only=… fit=…)
        src = kc.WORK / "backpacks" / ("backpacks_test.blend" if test else "backpacks.blend")
        out = kc.WORK / "backpacks" / ("backpacks_test_tex.blend" if test else "backpacks_tex.blend")
    elif what == "pouches":
        src = kc.WORK / "pouches" / "pouches.blend"
        out = kc.WORK / "pouches" / "pouches_tex.blend"
    else:
        src = kc.WORK / "armor" / "armor_belt.blend"
        out = kc.WORK / "armor" / "armor_belt_tex.blend"
    bpy.ops.wm.open_mainfile(filepath=str(src))
    vl = bpy.context.view_layer.layer_collection

    def unhide(lc) -> None:
        lc.hide_viewport = False
        for c in lc.children:
            unhide(c)
    for lc in vl.children:
        if lc.name.startswith(("07_", "08_", "06_Armor_Belt")):
            unhide(lc)
    groups: dict[str, list[bpy.types.Object]] = {}
    if what == "packs":
        for o in bpy.data.objects:
            if o.type == "MESH" and o.name.split("_")[0] in ("Daypack", "Tourist", "Raid"):
                groups.setdefault(o.name.split("_")[0], []).append(o)
        # маски — по каждой посадке отдельно (низ — у дна этой посадки), материалы — общие на вид
        for owner in list(groups):
            fits = {}
            for o in groups[owner]:
                fits.setdefault(o.users_collection[0].name, []).append(o)
            for objs in fits.values():
                gear_masks(objs)
        texture(groups, "Pack")
    elif what == "pouches":
        groups["Pouch"] = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith("Pouch_")]
        for pref in ("Pouch_Rifle", "Pouch_Pistol", "Pouch_Big"):
            gear_masks([o for o in groups["Pouch"] if o.name.startswith(pref)])
        texture(groups, "Pouch")
    else:
        groups["Belt"] = [o for o in bpy.data.collections["06_Armor_Belt"].objects if o.type == "MESH"]
        gear_masks(groups["Belt"])
        texture(groups, "Armor")
    bpy.context.scene.render.engine = "CYCLES"
    kc.save(out)
    kc.log("GEAR_TEX", what, "→", out)
    if "shots" in args:
        shots(what)
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        deliver(what, Path(dest))


def shots(what: str) -> None:
    at.sample_studio()
    prev = kc.WORK / "previews"
    if what == "packs":
        import backpacks as bp
        for name in ("Daypack", "Tourist", "Raid"):
            if f"07_Backpack_{name}" not in bpy.data.collections:
                continue
            bp.show(name, "none")
            for v, (pos, tgt) in {"back34": ((-0.95, 1.30, 1.50), (0.0, 0.18, 1.22)),
                                  "macro": ((0.40, 0.85, 1.30), (0.05, 0.25, 1.22)),
                                  "ear": ((-0.80, 0.80, 1.38), (-0.24, 0.26, 1.26))}.items():
                kc.render(kc.camera("Tex_b_" + v, pos, tgt, 50), prev / f"pack_tex_{name.lower()}_{v}.png", (900, 1000),
                          at.SAMPLES)
        bp.show("Daypack", "none")
    elif what == "pouches":
        import pouches as pu
        for prefix, x0, mag, key, tag in pu.SHOTS:
            if tag not in ("rifle_30", "pistol_glock", "big_drum"):
                continue
            pu.set_state(prefix, mag, key)
            tgt = (x0, 0.0, 0.10 if prefix != "Pouch_Pistol" else 0.07)
            kc.render(kc.camera("Tex_p_" + tag, (x0 + 0.20, 0.32, tgt[2] + 0.12), tgt, 60), prev / f"pouch_tex_{tag}.png",
                      (900, 900), at.SAMPLES)
        pu.set_state("", None, None)


def deliver(what: str, folder: Path) -> None:
    if what == "packs":
        import armor_mid as am
        import backpacks as bp
        bp.show("Daypack", "none")
        am.deliver(folder, f"Рюкзаки_{bp.VERSION}_текстуры.blend", bp.README.format(ver=bp.VERSION).replace(
            "ФОРМА", "ТЕКСТУРЫ (нативный UCUPaint 2.4.9; городской — тёмно-серый, туристический — рейнджер-грин,\n"
            "рейдовый — свой лесной камуфляж «Чаща», по решениям владельца) на форме"), focus_z=1.25, near=0.75)
    elif what == "pouches":
        import pouches as pu
        pu.README = pu.README.replace("ФОРМА {ver} на согласование (нейтральный материал)",
                                      "ТЕКСТУРЫ {ver} (койот, нативный UCUPaint 2.4.9) на принятой форме")
        pu.deliver(folder, f"Подсумки_{pu.VERSION}_текстуры.blend")


if __name__ == "__main__":
    main()
