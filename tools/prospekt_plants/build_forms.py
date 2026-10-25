"""Растения «Проспекта» — формы на просмотр владельцу (без PBR), bpy:

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/prospekt_plants/build_forms.py -- [birch linden poplar lilac hedge] [preview]

На каждый вид — свой файл E:/Models Blender/ENVIRONMENT/RING_Prospekt_Plants/models/NN_<Вид>_форма_v01.blend:
экземпляры в ряд (каждый — пустышка «<ключ>» у земли, под ней ствол с ветвями и листва модулями), модули веточек
рядом для осмотра вблизи, мерка 1,75 м, пол и солнце. Замеры (габарит с листвой, обхват, треугольники) —
checks/forms_v01.json; preview — снимки для проверки в previews/.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plib  # noqa: E402
import species as S  # noqa: E402

LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Prospekt_Plants")
VERSION = "v01"
ORDER = ["birch", "linden", "poplar", "lilac", "hedge"]
GAP = {"birch": 3.0, "linden": 3.0, "poplar": 3.0, "lilac": 1.5, "hedge": 1.5}
MOD_X0, MOD_Y = 0.5, -7.0
MOD_STEP = {"birch": 1.0, "linden": 1.0, "poplar": 1.0, "lilac": 0.9, "hedge": 0.7}


def build_kind(kind: str) -> tuple:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    root = plib.new_collection(S.LABEL[kind])
    mods_coll = plib.new_collection(f"{S.LABEL[kind]}_модули_веточек", root)
    wood = S.WOOD[kind]
    mats = {k: plib.diag_material(f"{S.LABEL[kind]}_{n}", wood[k] if k in wood else wood["branch"])
            for k, n in (("bark", "кора"), ("branch", "ветви"), ("twig", "побеги"), ("seed", "метёлки"))}
    mats["leaf"] = plib.leaf_material(f"{S.LABEL[kind]}_лист", S.LEAF_RGB[kind])
    # модули веточек: в ряд за экземплярами (для узлов их положение не важно — берутся от своего начала)
    modules = S.MODULES[kind]()
    mod_info = []
    for i, (name, mm) in enumerate(modules):
        ob = mm.build(name, mats, mods_coll)
        # для осмотра: пряди висят, остальное стоит; листья лицом к камере (−Y). Узлы берут модуль без этого поворота.
        hang = kind == "birch" and "прядь" in name
        ob.rotation_mode = "QUATERNION"
        ob.rotation_quaternion = plib.frame_quat(-plib.Z if hang else plib.Z, -plib.Y)
        ob.location = (MOD_X0 + i * MOD_STEP[kind], MOD_Y, 1.95 if hang else 0.55)
        mod_info.append(dict(name=name, triangles=mm.tris(), leaves=mm.leaves))
    ng = plib.instancer_group(f"{S.LABEL[kind]}_листва_по_точкам", mods_coll)
    plants = [p for p in S.PLANTS if p.kind == kind]
    x = 0.0
    out = []
    for pl in plants:
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
        # ширина экземпляра по габариту ствола/ветвей и модулей — для раскладки в ряд
        xs = [v.x for v in m.parts.get("bark", {"v": [Vector()]})["v"]] + [p.x for p in tw.pts]
        half = max(1.0, max(abs(min(xs)), abs(max(xs))) + 1.0)
        x += half
        empty.location = (x, 0.0, 0.0)
        empty["Описание"] = pl.label
        x += half + GAP[kind]
        leaves = sum(mod_info[t]["leaves"] for t in tw.ids)
        inst_tris = sum(mod_info[t]["triangles"] for t in tw.ids)
        out.append(dict(key=pl.key, label=pl.label, empty=empty, wood=wood_ob, pts=pts_ob, wood_tris=m.tris(),
                        twigs=len(tw.ids), leaves=leaves, twig_tris=inst_tris, params=pl.params, seed=pl.seed))
    fig = plib.scale_figure(root, Vector((-1.5, 0, 0)))
    plib.studio(plib.new_collection("_Студия_осмотра"), size=max(80.0, x + 40))
    plib.set_viewports()
    return out, mod_info, x


def measure(entries: list) -> list:
    bpy.context.view_layer.update()
    res = []
    for e in entries:
        lo, hi = plib.evaluated_bounds([e["wood"], e["pts"]])
        base = e["empty"].location
        tr_lo, tr_hi = plib.evaluated_bounds([e["wood"]])
        p = e["params"]
        res.append(dict(key=e["key"], label=e["label"], seed=e["seed"],
                        height_m=round(hi.z, 2), below_ground_m=round(lo.z, 2),
                        crown_x_m=round(hi.x - lo.x, 2), crown_y_m=round(hi.y - lo.y, 2),
                        offset_from_base_m=[round((lo.x + hi.x) * 0.5 - base.x, 2), round((lo.y + hi.y) * 0.5 - base.y, 2)],
                        trunk_d_1_3m=round(p["r1"] * 2, 3) if "r1" in p else None,
                        wood_bounds_m=[round(tr_hi.x - tr_lo.x, 2), round(tr_hi.y - tr_lo.y, 2), round(tr_hi.z, 2)],
                        wood_triangles=e["wood_tris"], twig_modules=e["twigs"], leaves=e["leaves"],
                        leaf_triangles_instanced=e["twig_tris"], origin="у земли под стволом, Z вверх, метры"))
    return res


def camera(name: str, loc: Vector, target: Vector, lens: float = 50.0, ortho: float = 0.0) -> bpy.types.Object:
    cam = bpy.data.objects.new(name, bpy.data.cameras.new(name))
    bpy.context.scene.collection.objects.link(cam)
    if ortho:
        cam.data.type = "ORTHO"
        cam.data.ortho_scale = ortho
    cam.data.lens = lens
    cam.data.clip_end = 2000
    d = (target - loc).normalized()
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.location = loc
    return cam


def render(cam, path: Path, res=(1600, 1000), samples: int = 48) -> None:
    sc = bpy.context.scene
    sc.camera = cam
    sc.render.engine = "CYCLES"
    plib.gpu()
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.view_settings.view_transform = "AgX"
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    print("PLANTS снимок", path.name, flush=True)


def previews(kind: str, entries: list, row_len: float) -> None:
    pv = LIB / "previews"
    pv.mkdir(parents=True, exist_ok=True)
    H = max(e["res"]["height_m"] for e in entries)
    cx = row_len * 0.5
    dist = max(H * 2.6, row_len * 1.55) + 3
    render(camera("кадр_спереди", Vector((cx, -dist, H * 0.5)), Vector((cx, 0, H * 0.5)), 50), pv / f"{kind}_front_{VERSION}.png")
    render(camera("кадр_сбоку", Vector((cx + dist * 0.62, -dist * 0.72, H * 0.9 + 1.0)), Vector((cx, 0, H * 0.4)), 50),
           pv / f"{kind}_34_{VERSION}.png")
    e0 = entries[0]
    b = e0["empty"].location
    h0 = e0["res"]["height_m"]
    if kind in ("hedge", "lilac"):
        render(camera("кадр_вблизи", Vector((b.x + 1.2, b.y - 3.2, 1.4)), Vector((b.x, b.y, 0.8)), 35),
               pv / f"{kind}_close_{VERSION}.png", (1400, 1000))
    else:
        render(camera("кадр_комель", Vector((b.x + 1.5, b.y - 3.5, 1.6)), Vector((b.x, b.y, 1.2)), 35),
               pv / f"{kind}_base_{VERSION}.png", (1400, 1000))
        render(camera("кадр_снизу_в_крону", Vector((b.x + 2.0, b.y - 4.0, 1.7)), Vector((b.x, b.y, h0 * 0.62)), 24),
               pv / f"{kind}_crown_{VERSION}.png", (1000, 1400))
    n = len(S.MODULES[kind]())
    mx = MOD_X0 + (n - 1) * MOD_STEP[kind] * 0.5
    render(camera("кадр_модули", Vector((mx, MOD_Y - 4.2, 1.25)), Vector((mx, MOD_Y, 1.2)), 30),
           pv / f"{kind}_modules_{VERSION}.png", (1600, 1000), 32)


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kinds = [k for k in ORDER if k in argv] or ORDER
    do_prev = "preview" in argv
    (LIB / "models").mkdir(parents=True, exist_ok=True)
    (LIB / "checks").mkdir(parents=True, exist_ok=True)
    report_path = LIB / "checks" / f"forms_{VERSION}.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else {}
    for kind in kinds:
        entries, mods, row = build_kind(kind)
        res = measure(entries)
        for e, r in zip(entries, res):
            e["res"] = r
        idx = ORDER.index(kind) + 1
        path = LIB / "models" / f"{idx:02d}_{S.LABEL[kind]}_форма_{VERSION}.blend"
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
        report[kind] = dict(file=str(path), modules=mods, plants=res)
        for r in res:
            print("PLANTS %s: %.1f м, крона %.1f × %.1f м, ветви %d тр., модулей %d, листьев %d" % (
                r["key"], r["height_m"], r["crown_x_m"], r["crown_y_m"], r["wood_triangles"], r["twig_modules"], r["leaves"]),
                flush=True)
        if do_prev:
            previews(kind, entries, row)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


main()
