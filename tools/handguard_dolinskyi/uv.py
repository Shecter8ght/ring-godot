# Цевьё Dolinskyi: развёртка low-poly 2K (как у автора, 2D-вид ролика 6:50 — один набор текстур 2048) и FBX для Painter.
# Порядок как у AR-15 (tools/ar15/tex_uv_blender.py): острова по изломам Smart UV → швы по их границам → Minimum Stretch
# (где хуже — проекция) → укладка asset_kit.uv.layout (отступ 8 px, внутри детали 6) → проверка растром → жёсткие
# рёбра только на швах. Отличие от автора: у него правая сторона и планки — копии (внахлёст), у нас всё уникально,
# иначе номера R1… и надпись читались бы зеркально.
#   blender --background <форма.blend> --factory-startup --python-exit-code 1 --python tools/handguard_dolinskyi/uv.py
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "ar15"))
import bpy  # noqa: E402
from asset_kit import uv as kit_uv  # noqa: E402
import tex_uv_blender as TU  # noqa: E402

UV = "UVMap"
RES = 2048
OUT_DIR = "E:/Models Blender/WEAPONS/Цевьё — Dolinskyi, анодирование 2026-11-01"
OUT_BLEND = os.path.join(OUT_DIR, "Цевьё_Dolinskyi_развёртка_v01.blend")
SP_DIR = os.path.join(HERE, "..", "..", "_asset_src", "handguard_dolinskyi", "sp")


def triangulate(o):
    m = o.modifiers.new("tri", "TRIANGULATE")
    m.quad_method = "BEAUTY"
    m.ngon_method = "BEAUTY"
    m.keep_custom_normals = True
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=m.name)


def main():
    os.makedirs(SP_DIR, exist_ok=True)
    lp = bpy.data.objects["handguard_low"]
    hp = bpy.data.objects["handguard_high"]
    for c in bpy.data.collections:
        c.hide_viewport = False
    bpy.ops.object.select_all(action="DESELECT")
    lp.select_set(True)
    bpy.context.view_layer.objects.active = lp
    TU.UV = UV
    kept, total, worst = TU.unwrap([lp], 60.0, None)
    rep = kit_uv.layout([lp], RES, uv=UV, stack=False, margin=8, group_margin=6, log=lambda *a: print("  ", *a))
    ver = kit_uv.verify([lp], RES, uv=UV, margin=8, group_margin=6)
    kit_uv.harden_on_seams([lp], uv=UV)
    triangulate(lp)
    report = dict(res=RES, islands=rep["islands"], fill=rep["fill"], px_mm=rep["px_mm"],
                  projection_kept=f"{kept}/{total}", verify=ver, tris=len(lp.data.polygons))
    print("UV", json.dumps(report, ensure_ascii=False))
    with open(os.path.join(SP_DIR, "uv_report.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
    # FBX для Painter: один low-poly и один high-poly, без преобразования осей (как у ВСС-М / AR-15)
    for o, name in ((lp, "handguard_low.fbx"), (hp, "handguard_high.fbx")):
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.export_scene.fbx(filepath=os.path.join(SP_DIR, name), use_selection=True, object_types={"MESH"},
                                 mesh_smooth_type="FACE", use_tspace=(o is lp), apply_unit_scale=True,
                                 use_mesh_modifiers=True, add_leaf_bones=False, bake_anim=False)
        print("FBX", name)
    print("SAVED", OUT_BLEND)


if __name__ == "__main__":
    main()
