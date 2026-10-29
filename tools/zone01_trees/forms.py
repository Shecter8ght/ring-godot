"""Клёны и тополя зоны 1 — формы на просмотр владельцу (без PBR), bpy:

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/zone01_trees/forms.py -- [maple poplar] [preview]

Файлы E:/Models Blender/ENVIRONMENT/RING_Zone01_Trees/models/NN_<Вид>_форма_v01.blend: экземпляры в ряд (пустышка с ключом
зоны 1 у земли, под ней ствол с ветвями и листва модулями по точкам), модули веточек рядом для осмотра вблизи, мерка 1,75 м,
пол и солнце. В файле клёна — оба вида (остролистный и ясенелистный). Замеры — checks/forms_v01.json, снимки — previews/.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prospekt_plants"))
import build_forms as PBF  # noqa: E402  (камера и рендер — как у «Проспекта»)
import plib  # noqa: E402
import species_z1 as S  # noqa: E402

LIB = Path(os.environ.get("ZONE01_TREES_LIB", "E:/Models Blender/ENVIRONMENT/RING_Zone01_Trees"))
VERSION = "v01"
# файл → виды в нём
GROUPS = {"maple": ("01", "Клён", ["maple", "negundo"]), "poplar": ("02", "Тополь", ["poplar"])}
GAP = 3.0
MOD_X0 = 0.5
MOD_STEP = 1.0


def materials(kind: str) -> dict:
    lab = S.LABEL[kind]
    wood = S.WOOD[kind]
    mats = {k: plib.diag_material(f"{lab}_{n}", wood[k]) for k, n in
            (("bark", "кора"), ("branch", "ветви"), ("twig", "побеги"), ("seed", "крылатки"), ("dead", "сухие"))}
    for k, n in (("leaf_g", "лист_зелёный"), ("leaf_y", "лист_жёлтый"), ("leaf_o", "лист_осенний")):
        mats[k] = plib.leaf_material(f"{lab}_{n}", S.LEAF_RGB[kind][k])
    return mats


def build_group(group: str) -> tuple:
    _, title, kinds = GROUPS[group]
    return build_set(title, kinds)


def build_set(title: str, kinds: list) -> tuple:
    """Сцена осмотра: экземпляры видов kinds в ряд, модули веточек впереди, мерка, пол и солнце."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    root = plib.new_collection(title)
    x = 0.0
    out = []
    mods_all = {}
    for ki, kind in enumerate(kinds):
        mats = materials(kind)
        mods_coll = plib.new_collection(f"{S.LABEL[kind]}_модули_веточек", root)
        mod_y = -7.0
        mod_x0 = MOD_X0 + ki * 7.0
        mod_info = []
        for i, (name, mm) in enumerate(S.MODULES[kind]()):
            ob = mm.build(name, mats, mods_coll)
            # для осмотра: модуль стоит, листья лицом к камере (−Y); узлы берут модуль без этого поворота
            ob.rotation_mode = "QUATERNION"
            ob.rotation_quaternion = plib.frame_quat(plib.Z, -plib.Y)
            ob.location = (mod_x0 + i * MOD_STEP, mod_y, 0.35)
            mod_info.append(dict(name=name, triangles=mm.tris(), leaves=mm.leaves))
        mods_all[kind] = dict(info=mod_info, y=mod_y, x0=mod_x0)
        ng = plib.instancer_group(f"{S.LABEL[kind]}_листва_по_точкам", mods_coll)
        for pl in [p for p in S.PLANTS if p.kind == kind]:
            m, tw, env = S.BUILDERS[kind](pl)
            coll = plib.new_collection(pl.key, root)
            empty = bpy.data.objects.new(pl.key, None)
            empty.empty_display_type = "ARROWS"
            empty.empty_display_size = 0.6
            coll.objects.link(empty)
            wood_ob = m.build(f"{pl.key}_ствол_и_ветви", mats, coll)
            pts_ob = plib.twig_points_object(f"{pl.key}_листва", tw, coll)
            mod = pts_ob.modifiers.new("Листва", "NODES")
            mod.node_group = ng
            for ob in (wood_ob, pts_ob):
                ob.parent = empty
            xs = [v.x for part in m.parts.values() for v in part["v"][::7]] + [p.x for p in tw.pts]
            half = max(1.0, max(abs(min(xs)), abs(max(xs))) + 0.8)
            x += half
            empty.location = (x, 0.0, 0.0)
            empty["Описание"] = pl.label
            x += half + GAP
            out.append(dict(key=pl.key, label=pl.label, kind=kind, empty=empty, wood=wood_ob, pts=pts_ob, wood_tris=m.tris(),
                            twigs=len(tw.ids), leaves=sum(mod_info[t]["leaves"] for t in tw.ids),
                            twig_tris=sum(mod_info[t]["triangles"] for t in tw.ids), params=pl.params, seed=pl.seed))
    plib.scale_figure(root, Vector((-1.5, 0, 0)))
    plib.studio(plib.new_collection("_Студия_осмотра"), size=max(80.0, x + 40))
    plib.set_viewports()
    return out, mods_all, x


def measure(entries: list) -> list:
    bpy.context.view_layer.update()
    res = []
    for e in entries:
        lo, hi = plib.evaluated_bounds([e["wood"], e["pts"]])
        base = e["empty"].location
        tr_lo, tr_hi = plib.evaluated_bounds([e["wood"]])
        p = e["params"]
        res.append(dict(key=e["key"], label=e["label"], kind=e["kind"], seed=e["seed"],
                        height_m=round(hi.z, 2), below_ground_m=round(lo.z, 2),
                        crown_x_m=round(hi.x - lo.x, 2), crown_y_m=round(hi.y - lo.y, 2),
                        offset_from_base_m=[round((lo.x + hi.x) * 0.5 - base.x, 2), round((lo.y + hi.y) * 0.5 - base.y, 2)],
                        trunk_d_1_3m=round(p["r1"] * 2, 3) if "r1" in p else [round(s[1] * 2, 3) for s in p.get("stems", [])],
                        wood_bounds_m=[round(tr_hi.x - tr_lo.x, 2), round(tr_hi.y - tr_lo.y, 2), round(tr_hi.z, 2)],
                        wood_triangles=e["wood_tris"], twig_modules=e["twigs"], leaves=e["leaves"],
                        leaf_triangles_instanced=e["twig_tris"], origin="у земли под стволом, Z вверх, метры"))
    return res


def previews(group: str, entries: list, mods: dict, row_len: float) -> None:
    pv = LIB / "previews"
    pv.mkdir(parents=True, exist_ok=True)
    H = max(e["res"]["height_m"] for e in entries)
    cx = row_len * 0.5
    dist = max(H * 2.4, row_len * 1.4) + 3
    PBF.render(PBF.camera("кадр_спереди", Vector((cx, -dist, H * 0.48)), Vector((cx, 0, H * 0.48)), 50), pv / f"{group}_front_{VERSION}.png")
    PBF.render(PBF.camera("кадр_сбоку", Vector((cx + dist * 0.62, -dist * 0.72, H * 0.9 + 1.0)), Vector((cx, 0, H * 0.4)), 50),
               pv / f"{group}_34_{VERSION}.png")
    PBF.render(PBF.camera("кадр_сзади", Vector((cx - dist * 0.3, dist * 0.95, H * 0.45)), Vector((cx, 0, H * 0.45)), 50),
               pv / f"{group}_back_{VERSION}.png")
    for e in entries:
        b = e["empty"].location
        h0 = e["res"]["height_m"]
        PBF.render(PBF.camera("кадр_комель", Vector((b.x + 1.6, b.y - 3.6, 1.7)), Vector((b.x, b.y, 1.2)), 35),
                   pv / f"{e['key']}_base_{VERSION}.png", (1400, 1000), 32)
        PBF.render(PBF.camera("кадр_снизу_в_крону", Vector((b.x + 2.2, b.y - 4.2, 1.7)), Vector((b.x, b.y, h0 * 0.62)), 22),
                   pv / f"{e['key']}_crown_{VERSION}.png", (1000, 1400), 32)
    for kind, mi in mods.items():
        n = len(mi["info"])
        mx = mi["x0"] + (n - 1) * MOD_STEP * 0.5
        PBF.render(PBF.camera("кадр_модули", Vector((mx, mi["y"] - 4.6, 0.62)), Vector((mx, mi["y"], 0.6)), 40),
                   pv / f"{kind}_modules_{VERSION}.png", (1800, 900), 32)
        # вблизи: густая веточка и веточка с крылатками (или пучок у тополя)
        for i in (0, 2):
            x = mi["x0"] + i * MOD_STEP
            PBF.render(PBF.camera("кадр_веточка", Vector((x + 0.15, mi["y"] - 1.25, 0.72)), Vector((x, mi["y"], 0.62)), 50),
                       pv / f"{kind}_module{i + 1:02d}_close_{VERSION}.png", (1200, 1200), 48)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    groups = [g for g in GROUPS if g in argv] or list(GROUPS)
    do_prev = "preview" in argv
    (LIB / "models").mkdir(parents=True, exist_ok=True)
    (LIB / "checks").mkdir(parents=True, exist_ok=True)
    report_path = LIB / "checks" / f"forms_{VERSION}.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    for group in groups:
        entries, mods, row = build_group(group)
        res = measure(entries)
        for e, r in zip(entries, res):
            e["res"] = r
        idx, title, _ = GROUPS[group]
        path = LIB / "models" / f"{idx}_{title}_форма_{VERSION}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
        report[group] = dict(file=str(path), modules={k: v["info"] for k, v in mods.items()}, plants=res)
        for r in res:
            print("TREES %s: %.1f м, крона %.1f × %.1f м, ветви %d тр., модулей %d, листьев %d" % (
                r["key"], r["height_m"], r["crown_x_m"], r["crown_y_m"], r["wood_triangles"], r["twig_modules"], r["leaves"]),
                flush=True)
        if do_prev:
            previews(group, entries, mods, row)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
