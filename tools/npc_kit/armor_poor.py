"""NPC: облегчённая броня «бомжовская» (уровень 1 из 3) по фото владельца — без плит, тёмно-синяя.

Передняя мягкая панель (бронепакет без плит) с велкро-решёткой 4×5 и язычком сверху; под ней широкий
нагрудник пояса с четырьмя рядами MOLLE; пояс вокруг всего торса — сетка и три стропы поверх неё;
H-лямки из стропы с лестничными пряжками, к панели — фастексы на верхних углах; на спине — мягкое
ярмо, от него две стропы вниз к поясу (задней панели нет); внизу спереди — две петли.
Цвет — тёмно-синий (решение владельца: не камуфляж). Форма на согласование, материал без текстур.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_poor.py [-- render] [deliver=<папка>]
→ _asset_src/npc_kit/armor/armor_poor.blend (читает npc_scav_<версия>.blend)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import armor_kit as ak  # noqa: E402
import armor_mid as am  # noqa: E402
import kit_common as kc  # noqa: E402

PANEL_BOT, PANEL_H, PANEL_W, PANEL_T = 1.150, 0.300, 0.265, 0.018
BIB_H, BIB_W, BIB_T = 0.150, 0.340, 0.012
BELT_BOT, BELT_H = 1.105, 0.150
YOKE_BOT, YOKE_H = 1.370, 0.140


def materials() -> dict[str, bpy.types.Material]:
    navy = (0.018, 0.024, 0.045)
    return {
        "cordura": kc.clay("Poor_Cordura", navy, 0.85),
        "webbing": kc.clay("Poor_Webbing", (0.014, 0.018, 0.034), 0.8),
        "velcro": kc.clay("Poor_Velcro", (0.012, 0.015, 0.027), 0.95),
        "mesh": kc.clay("Poor_Mesh", (0.010, 0.012, 0.020), 0.9),
        "plastic": kc.clay("Poor_Plastic", (0.02, 0.02, 0.02), 0.45),
    }


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"npc_scav_{kc.VERSION}.blend"))
    f = am.fit()
    col = kc.collection("06_Armor_Poor")
    mats = materials()
    hull = f.hull
    panel = ak.PlateFrame(hull, True, PANEL_BOT, PANEL_H, PANEL_W, 0.30, PANEL_T / 2, 0.010)
    yoke = ak.PlateFrame(hull, False, YOKE_BOT, YOKE_H, 0.30, 0.35, 0.006, 0.006)
    face = PANEL_T / 2 + 0.0025
    cordura, web, velc, mesh, plastic = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()

    # Передняя панель с велкро-решёткой и язычком.
    out = ak.rounded_poly([(-PANEL_W / 2, 0.0), (PANEL_W / 2, 0.0), (PANEL_W / 2, PANEL_H), (-PANEL_W / 2, PANEL_H)],
                          [0.010, 0.010, 0.030, 0.030])
    ak.padded_panel(cordura, panel, out, PANEL_T, bulge=0.003)
    vu0, vu1, vv0, vv1 = -0.085, 0.085, 0.105, 0.285
    ak.padded_panel(velc, ak.OffsetFrame(panel, face + 0.0012 + 0.0015), am.rect(vu0, vu1, vv0, vv1, 0.006), 0.003,
                    bulge=0.0, binding=0.0, relief=am.grid_relief(vu0, vu1, vv0, vv1, 4, 5), step=0.002)
    tab = [panel.point(0.012 * math.cos(math.pi * k / 8), PANEL_H - 0.005 + 0.022 * math.sin(math.pi * k / 8), face + 0.003)
           for k in range(9)]
    ak.strap(web, ak.RibbonFrame(tab, [panel.normal(0, PANEL_H)] * len(tab)), 0.025, 0.003)

    # Пояс вокруг торса: сетка и три стропы; спереди — нагрудник с MOLLE поверх концов пояса.
    def push(p: Vector, n: Vector) -> Vector:
        if p.y > -0.05 or abs(p.x) > PANEL_W / 2 + 0.03:
            return p
        u = max(-PANEL_W / 2, min(PANEL_W / 2, p.x))
        y_out = panel.point(u, max(0.0, p.z - PANEL_BOT), PANEL_T / 2 + 0.001).y
        t = ak.gm.smoothstep((PANEL_W / 2 + 0.03 - abs(p.x)) / 0.04)
        q = p.copy()
        q.y = p.y + (min(p.y, y_out) - p.y) * t
        return q
    belt = ak.BandFrame(hull, BELT_BOT, BELT_H, -62.0, 242.0, 0.004, push, rows=16, samples=200)
    ak.padded_panel(mesh, ak.OffsetFrame(belt, 0.0015), am.rect(0.0, belt.length, 0.004, BELT_H - 0.004, 0.01), 0.003,
                    bulge=0.0, binding=0.0, step=0.008)
    for v in (0.010, 0.060, 0.110):
        pts = [belt.point(belt.length * k / 120, v + 0.02, 0.004) for k in range(121)]
        nrm = [belt.normal(belt.length * k / 120, v + 0.02) for k in range(121)]
        ak.strap(web, ak.RibbonFrame(pts, nrm), 0.040, 0.0035)
    bib_frame = ak.OffsetFrame(panel, PANEL_T / 2 + 0.010)
    ak.padded_panel(cordura, ak.OffsetFrame(bib_frame, BIB_T / 2), am.rect(-BIB_W / 2, BIB_W / 2, BELT_BOT - PANEL_BOT,
                    BELT_BOT - PANEL_BOT + BIB_H, 0.018), BIB_T, bulge=0.003)
    ak.webbing_rows(web, ak.OffsetFrame(bib_frame, BIB_T), -BIB_W / 2 + 0.015, BIB_W / 2 - 0.015,
                    [BELT_BOT - PANEL_BOT + 0.010 + 0.035 * i for i in range(4)], 0.003)
    for sgn in (1.0, -1.0):                    # петли внизу
        u = sgn * 0.10
        v0 = BELT_BOT - PANEL_BOT
        pts = [bib_frame.point(u + 0.012 * math.sin(math.pi * k / 10), v0 + 0.01 - 0.05 * math.sin(math.pi * k / 20),
                               BIB_T + 0.002) for k in range(11)]
        ak.strap(web, ak.RibbonFrame(pts, [bib_frame.normal(u, v0)] * len(pts)), 0.025, 0.003)

    # Ярмо на спине и две стропы вниз к поясу.
    yoke_out = ak.rounded_poly([(-0.150, 0.100), (-0.060, 0.020), (0.060, 0.020), (0.150, 0.100),
                                (0.120, 0.140), (0.0, 0.085), (-0.120, 0.140)], [0.04, 0.04, 0.04, 0.04, 0.025, 0.05, 0.025])
    ak.padded_panel(cordura, yoke, yoke_out, 0.012, bulge=0.003)
    for sgn in (1.0, -1.0):
        # стропа ложится на спину куртки (ближайшая точка поверхности + 6 мм), а не идёт по плоскости ярма
        pts, nrm = [], []
        for k in range(31):
            tt = k / 30
            p = yoke.point(sgn * (0.060 - 0.01 * tt), 0.05 - (YOKE_BOT - BELT_BOT - 0.03) * tt, 0.0)
            loc, n, _, _ = f.jacket_bvh.find_nearest(p)
            if n.y < 0:
                n = -n
            if k == 0:
                pts.append(p + yoke.normal(0, 0) * 0.012)
                nrm.append(yoke.normal(0, 0))
                continue
            pts.append(loc + n * 0.008)
            nrm.append(n)
        rib = ak.RibbonFrame(pts, nrm)
        ak.strap(web, rib, 0.040, 0.0035)
        ul = rib.length * 0.45
        tan = (rib.point(ul + 0.01, 0, 0) - rib.point(ul, 0, 0)).normalized()
        n = rib.normal(ul, 0)
        ak.ladder_lock(plastic, rib.point(ul, 0.0, 0.006), n.cross(tan).normalized(), tan, n, 0.040)

    # H-лямки: от фастексов на углах панели по плечу к ярму.
    spec = am.CarrierSpec(front_h=PANEL_H, back_h=YOKE_H)
    for sgn in (1.0, -1.0):
        sp = am.shoulder_path(f.jacket_bvh, panel, yoke, sgn, face, spec)
        ak.strap(web, sp, 0.040, 0.0035, 0.0)
        u = 0.03
        c = sp.point(u, 0.0, 0.008)
        tan = (sp.point(u + 0.01, 0, 0) - sp.point(u, 0, 0)).normalized()
        n = sp.normal(u, 0)
        ak.side_release(plastic, c, n.cross(tan).normalized(), tan, n, 0.040)
        u2 = 0.11
        c2 = sp.point(u2, 0.0, 0.006)
        tan2 = (sp.point(u2 + 0.01, 0, 0) - sp.point(u2, 0, 0)).normalized()
        n2 = sp.normal(u2, 0)
        ak.ladder_lock(plastic, c2, n2.cross(tan2).normalized(), tan2, n2, 0.040)

    cordura.build("Poor_Panel_Bib_Yoke", col, [mats["cordura"]])
    velc.build("Poor_Velcro", col, [mats["velcro"]])
    mesh.build("Poor_Belt_Mesh", col, [mats["mesh"]])
    web.build("Poor_Webbing", col, [mats["webbing"]])
    plastic.build("Poor_Buckles", col, [mats["plastic"]])
    kc.log("ARMOR_POOR", len(col.objects), "объектов,", am.triangles(col), "треугольников")
    am.OUT.mkdir(parents=True, exist_ok=True)
    kc.save(am.OUT / "armor_poor.blend")
    if "render" in args:
        am.render_previews(col, "poor", extra={
            "close_front": ((0.30, -0.75, 1.40), (0.0, -0.2, 1.28)),
            "close_back": ((0.35, 0.80, 1.45), (0.0, 0.1, 1.33)),
        })
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        am.deliver(Path(dest), "Броня_бомжовская_v01_форма.blend", (
            "Облегчённая броня «бомжовская» (уровень 1 из 3, без плит) — ФОРМА на согласование, цвет тёмно-синий.\n"
            "По фото владельца (voenform.ru): передняя мягкая панель с велкро-решёткой, нагрудник с MOLLE,\n"
            "пояс — сетка и три стропы, H-лямки с фастексами и лестничными пряжками, ярмо на спине (задней панели нет).\n"
            "Коллекция 06_Armor_Poor; надета на мародёра v02 поверх куртки.\n"
            "Скрипт: tools/npc_kit/armor_poor.py.\n"))


if __name__ == "__main__":
    main()
