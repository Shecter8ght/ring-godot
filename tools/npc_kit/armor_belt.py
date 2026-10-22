"""NPC и игрок: пояс с подсумками — вместо брони (решение владельца 2026-10-22: боец без бронежилета носит магазины
на поясе; пояс занимает слот брони, защиты нет, два места под подсумки; docs/design/gear_v2.md) — форма v01.

Мягкий пояс-«рукав» вокруг талии поверх куртки (на высоте пояса брюк), по нему один ряд MOLLE; спереди — несущая
стропа 45 мм с большой пряжкой. Места под подсумки — спереди-сбоку слева и справа (tools/npc_kit/pouch_places.py).
Марок нет. Коллекция 06_Armor_Belt.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_belt.py
→ _asset_src/npc_kit/armor/armor_belt.blend (читает мародёра kit_common.npc_file())
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import kit_common as kc  # noqa: E402

OUT = kc.WORK / "armor" / "armor_belt.blend"
Z_BOT, BELT_H = 0.948, 0.055        # низ и высота пояса
INNER_W = 0.045                     # несущая стропа
GAP_A = 13.0                        # спереди по середине — разрыв под пряжку (градусы)


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(kc.npc_file()))
    col = kc.collection("06_Armor_Belt")
    mats = {"cordura": kc.clay("Armor_Cordura", (0.20, 0.20, 0.17), 0.85),
            "webbing": kc.clay("Armor_Webbing", (0.12, 0.12, 0.10), 0.8),
            "plastic": kc.clay("Armor_Plastic", (0.04, 0.04, 0.04), 0.5)}
    hull = ak.Hull([bpy.data.objects["Jacket"], bpy.data.objects["Pants"]], 0.88, 1.06)
    sleeve, web, hw = ak.Mesh(), ak.Mesh(), ak.Mesh()
    a0, a1 = -90.0 + GAP_A, 270.0 - GAP_A
    band = ak.BandFrame(hull, Z_BOT, BELT_H, a0, a1, 0.004, rows=8, samples=220, vsmooth=10, press=0.005)
    L = band.length
    ak.padded_panel(sleeve, ak.OffsetFrame(band, 0.007), ak.rounded_poly([(0.0, 0.0), (L, 0.0), (L, BELT_H), (0.0, BELT_H)],
                                                                         [0.012] * 4), 0.014, bulge=0.002, binding=0.007,
                    step=0.006)
    ak.webbing_rows(web, ak.OffsetFrame(band, 0.0145), 0.03, L - 0.03, [BELT_H / 2 - 0.0125], 0.0005)
    # спереди: несущая стропа выходит из рукава и сходится в пряжке
    zf = Z_BOT + (BELT_H - INNER_W) / 2
    front = ak.BandFrame(hull, zf, INNER_W, a0 + 3.0, a1 - 3.0 - 360.0, 0.006, rows=3, samples=40)
    ak.padded_panel(web, front, ak.rounded_poly([(0.0, 0.0), (front.length, 0.0), (front.length, INNER_W), (0.0, INNER_W)],
                                                [0.003] * 4), 0.0022, bulge=0.0, binding=0.0, step=0.004)
    u = front.length / 2
    p = front.point(u, INNER_W / 2, 0.006)
    nn = front.normal(u, INNER_W / 2)
    tan = (front.point(u + 0.01, INNER_W / 2) - front.point(u - 0.01, INNER_W / 2)).normalized()
    ak.side_release(hw, p, nn.cross(tan).normalized(), tan, nn, INNER_W)
    sleeve.build("Belt_Sleeve", col, [mats["cordura"]])
    web.build("Belt_Webbing", col, [mats["webbing"]])
    hw.build("Belt_Buckle", col, [mats["plastic"]])
    kc.log(f"  пояс: длина рукава {L:.2f} м, граней {sum(len(o.data.polygons) for o in col.objects)}")
    kc.save(OUT)


if __name__ == "__main__":
    main()
