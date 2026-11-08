"""Пожарная АЦ: правки владельца в файле просмотра отделки (2026-11-08) — перенести в файл развёртки.

Владелец поправил FireTanker_finish_v01.blend руками: удалил дефлекторы стоек кабины, переставил бордюрное зеркало
(кронштейн на 13,9 см назад, зеркало на 2,9 см вперёд и 2,3 см ниже), сдвинул задние угловые стойки внутрь (~2,5 см).
Заклёпки на боковине стоек при этом висели бы в воздухе — сдвигаются вместе со стойкой. Развёртка не меняется
(детали переезжают целиком), карты остаются верными. То же — в генераторе (cab_body.py, cab.py, body.py).

blender --background <FireTanker_uv_v01.blend> --factory-startup --python-exit-code 1 --python tools/fire_truck/owner_edits.py
"""
from __future__ import annotations

import bpy
from mathutils import Vector

MOVE = {"kerb_arm": (0.0, 0.139, 0.0),
        "mirror_kerb": (-1.01, -3.3186, 2.7768)}          # зеркало — место владельца целиком
COLUMNS = {1: 1.0813, -1: -1.0791}                         # x стоек по стороне (было ±1.105)


def centre(o):
    me = o.data
    return o.matrix_world @ (sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices)))


def main():
    for name in ("Pillar_Deflector_L", "Pillar_Deflector_R"):
        o = bpy.data.objects.get(name)
        if o:
            bpy.data.objects.remove(o)
            print("удалён", name)
    o = bpy.data.objects["kerb_arm"]
    o.location = Vector(MOVE["kerb_arm"])
    o = bpy.data.objects["mirror_kerb"]
    o.location = Vector(MOVE["mirror_kerb"])
    shift = {}
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name.split(".")[0] == "rear_column"]:
        side = 1 if o.location.x > 0 else -1
        shift[side] = COLUMNS[side] - o.location.x
        o.location.x = COLUMNS[side]
        print(o.name, "x →", COLUMNS[side])
    for o in [o for o in bpy.data.objects if o.type == "MESH" and o.name.split(".")[0] == "rivets_column"]:
        side = 1 if centre(o).x > 0 else -1
        o.location.x += shift.get(side, 0.0)
        print(o.name, "сдвиг", round(shift.get(side, 0.0), 4))
    bpy.ops.wm.save_as_mainfile(filepath=bpy.data.filepath, compress=True)
    print("SAVED", bpy.data.filepath)


if __name__ == "__main__":
    main()
