"""Сборка для проверки посадки: винтовка + крепление + прицел (дописываются из своих .blend).

blender --background --factory-startup --python tools/mosin_pu/assemble.py -- [rifle_ver] [mount_ver] [scope_ver] | tex
Крепление ставится без сдвига (общее начало с винтовкой), прицел — в пустышку Mount_ScopeSocket.
Файл сборки только для проверки и показа: правится в своих моделях, сборка пересобирается этим скриптом.
"""
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mosin_lib as L  # noqa: E402

A = L.ASSET_DIR
args = L.script_args()
RV = args[0] if len(args) > 0 and args[0] != "tex" else "v06"
MV = args[1] if len(args) > 1 else "v01"
SV = args[2] if len(args) > 2 else "v01"
TEX = "tex" in args          # сборка из текстурных файлов (состояние 20 %) — для просмотра отделки
if TEX:
    FILES = {
        "rifle": os.path.join(A, "models", "01_Винтовка", "Mosin_9130PU_Rifle_v06_tex20_v01.blend"),
        "mount": os.path.join(A, "models", "03_Крепление", "Mosin_PU_Mount_v01_tex20_v01.blend"),
        "scope": os.path.join(A, "models", "02_Прицел", "Mosin_PU_Scope_v01_tex20_v01.blend"),
    }
    OUT = os.path.join(A, "models", "00_Сборка", "Mosin_9130PU_Assembly_tex20_v01.blend")
else:
    FILES = {
        "rifle": os.path.join(A, "models", "01_Винтовка", f"Mosin_9130PU_Rifle_{RV}.blend"),
        "mount": os.path.join(A, "models", "03_Крепление", f"Mosin_PU_Mount_{MV}.blend"),
        "scope": os.path.join(A, "models", "02_Прицел", f"Mosin_PU_Scope_{SV}.blend"),
    }
    OUT = os.path.join(A, "models", "00_Сборка", "Mosin_9130PU_Assembly_check.blend")


def append_all(path, col_name):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    col = L.collection(col_name)
    for ob in dst.objects:
        if ob is not None:
            col.objects.link(ob)
    return [o for o in dst.objects if o is not None]


def main():
    L.reset_scene()
    append_all(FILES["rifle"], "Rifle")
    mount = append_all(FILES["mount"], "Mount")
    scope = append_all(FILES["scope"], "Scope")
    bpy.context.view_layer.update()
    socket = next(o for o in mount if o.name.startswith("Mount_ScopeSocket"))
    sroot = next(o for o in scope if o.name == "PU_Scope")
    sroot.matrix_world = socket.matrix_world.copy()
    bpy.context.view_layer.update()
    lo, hi = L.world_bbox_mm([o for o in bpy.context.scene.objects if o.type == "MESH"])
    print("ASSEMBLY bbox mm", tuple(round(v, 1) for v in lo), tuple(round(v, 1) for v in hi))
    if TEX:
        bpy.ops.file.pack_all()
    L.save_blend(OUT)


main()
