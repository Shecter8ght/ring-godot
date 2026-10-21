"""NPC: файл для просмотра владельцем — всё упаковано, студия, вьюпорт сразу в Rendered.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/deliver.py -- <папка>
(читает _asset_src/npc_kit/npc_scav_v01.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kit_common as kc  # noqa: E402


def main() -> None:
    args = kc.args_after_dashes()
    out = Path(args[0]) if args else kc.WORK / "delivery"
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / "npc_scav_v01.blend"))
    scene = bpy.context.scene
    kc.gpu_cycles(64)
    scene.cycles.preview_samples = 24
    scene.cycles.use_preview_denoising = True
    for cam in [o for o in bpy.data.objects if o.type == "CAMERA"]:
        bpy.data.objects.remove(cam)
    scene.camera = kc.camera("Camera_3-4", (3.4, -4.0, 1.14), (0, 0, 0.94), 70)
    kc.camera("Camera_Front", (0, -5.2, 0.94), (0, 0, 0.94), 70)
    kc.camera("Camera_Back", (0, 5.2, 0.94), (0, 0, 0.94), 70)
    floor = bpy.data.objects.get("Studio_Floor")
    for o in bpy.data.objects:
        if o.type in ("ARMATURE",):
            o.hide_set(True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            sp = area.spaces.active
            sp.shading.type = "RENDERED"
            sp.overlay.show_floor = False
            r3 = sp.region_3d
            r3.view_location = (0.0, 0.0, 0.95)
            r3.view_distance = 3.2
            r3.view_rotation = Quaternion((0.78, 0.47, 0.20, 0.36))
            r3.view_perspective = "PERSP"
    text = bpy.data.texts.new("00_ПРОЧТИ")
    text.use_fake_user = True
    text.write(
        "NPC «мародёр» v01 (Claude, 2026-10-21) — проверочный файл.\n"
        "Тело MPFB/MakeHuman (CC0) 1,80 м, A-поза, скелет game_engine 53 кости (скрыт).\n"
        "Брюки — лекала, сшиты симуляцией ткани, заправлены в берцы с напуском.\n"
        "Куртка — кожа: оболочка вокруг тела, разрез по швам, развёртка в лекала, симуляция;\n"
        "  трикотажные воротник, манжеты и пояс; молния с бегунком; строчка и карманы — картами рельефа.\n"
        "Берцы — по образцу владельца: рант, накладки, D-кольца, крючки, шнуровка с обмоткой.\n"
        "Балаклава — по форме головы, складки на шее.\n"
        "Материалы — узлами для просмотра (фото CC0 Poly Haven + свои процедурные).\n"
        "Игровой версии ещё нет: сетки LOD, атласы и запекание, веса и экспорт — следующий этап.\n"
        "Скрипты: tools/npc_kit в проекте RING.\n")
    bpy.ops.file.pack_all()
    out.mkdir(parents=True, exist_ok=True)
    path = out / "NPC_Marauder_v01.blend"
    kc.save(path)
    kc.log("DELIVERED", str(path))


if __name__ == "__main__":
    main()
