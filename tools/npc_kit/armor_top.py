"""NPC: тяжёлая броня «крутая» (уровень 3 из 3) по фото владельца — плитоносец с надставками.

База — тот же плитоносец (armor_mid.build_carrier) с высоким клапаном на пять рядов MOLLE и толстым
камербандом (в нём боковые плиты, вертикальные фастексы сброса). Надставки: высокий мягкий воротник
вокруг шеи (спереди разомкнут), наплечники на плечо и верх руки с велкро под нашивку, на лямках —
коробки аварийного сброса и трос с петлёй; спереди под пакетом — панель живота с MOLLE и паховая
защита из двух лопастей с косыми стропами; сзади — панель поясницы и фартук на ягодицы.
Щитки бёдер с фото — следующим шагом. Нашивки и марки с фото не переносятся.

blender --background --factory-startup --python-exit-code 1 --python tools/npc_kit/armor_top.py [-- render] [deliver=<папка>]
→ _asset_src/npc_kit/armor/armor_top.blend (читает npc_scav_<версия>.blend)
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

SPEC = am.CarrierSpec(prefix="Top", flap_h=0.215, flap_rows=5, front_rows=[], cummer_t=0.020,
                      pad=(0.080, 0.020), admin=(-0.070, 0.070, 0.262, 0.336, 4, 3))
COLLAR_H, COLLAR_T = 0.120, 0.024
DELT_T = 0.020
SKIRT_T = 0.016                     # лопасти паха, фартук


def sleeve_radius(jacket: bpy.types.Object, side: str, a: Vector, b: Vector) -> callable:
    """Радиус рукава куртки вокруг оси плеча по длине (90-й процентиль по верхней стороне) + 4 мм."""
    me = jacket.data
    gi = {g.index for g in jacket.vertex_groups if g.name.startswith(f"piece_sleeve_{side}")}
    d = (b - a).normalized()
    up = Vector((0.0, 0.0, 1.0))
    e_up = (up - d * up.dot(d)).normalized()
    bins: dict[int, list[float]] = {}
    for v in me.vertices:
        if not any(g.group in gi for g in v.groups):
            continue
        p = jacket.matrix_world @ v.co
        t = (p - a).dot(d)
        r = p - a - d * t
        if r.length < 1e-6 or r.normalized().dot(e_up) < -0.3:
            continue
        bins.setdefault(int(round(t / 0.01)), []).append(r.length)
    table = {}
    for k, rs in bins.items():
        rs.sort()
        table[k] = rs[int(len(rs) * 0.9)]
    keys = sorted(table)

    def r(u: float) -> float:
        k = max(keys[0], min(keys[-1], u / 0.01))
        k0 = int(math.floor(k))
        k1 = k0 + 1
        r0 = table.get(k0, table[min(keys, key=lambda q: abs(q - k0))])
        r1 = table.get(k1, r0)
        return r0 + (r1 - r0) * (k - k0) + 0.004
    return r


def collar_outline(length: float) -> list[tuple[float, float]]:
    """Воротник: выше всего сзади (12 см), к передним концам ниже (7,5 см)."""
    top = []
    n = 24
    for i in range(n, -1, -1):
        u = length * i / n
        top.append((u, 0.075 + 0.045 * math.sin(math.pi * u / length) ** 0.8))
    pts = [(0.0, 0.0), (length, 0.0)] + top
    radii = [0.015, 0.015] + [0.015] + [0.0] * (len(top) - 2) + [0.015]
    return ak.rounded_poly(pts, radii)


def main() -> None:
    args = kc.args_after_dashes()
    bpy.ops.wm.open_mainfile(filepath=str(kc.WORK / f"npc_scav_{kc.VERSION}.blend"))
    f = am.fit()
    col = kc.collection("06_Armor_Top")
    mats = am.materials()
    base = am.build_carrier(f, SPEC, col, mats)
    front, back, face = base["front"], base["back"], base["face"]
    jacket = f.jacket
    pants = bpy.data.objects["Pants"]
    low = ak.Hull([jacket, pants], 0.64, 1.14)

    cordura, web, velc, plastic, metal = ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh(), ak.Mesh()

    # Воротник вокруг шеи поверх трикотажного воротника куртки и балаклавы; спереди разомкнут.
    neck_objs = [jacket] + [o for o in bpy.data.objects if o.name == "Balaclava"]
    neck = ak.Hull(neck_objs, 1.46, 1.64, x_max=0.14)
    collar = ak.NeckFrame(neck, 1.47, COLLAR_H, -58.0, 238.0, 0.004)
    ak.padded_panel(cordura, ak.OffsetFrame(collar, COLLAR_T / 2), collar_outline(collar.length), COLLAR_T,
                    bulge=0.006, binding=0.014, step=0.006)
    kc.log(f"  воротник: длина {collar.length:.3f} м")

    # Наплечники: на плечо и верх руки, снаружи — велкро под нашивку.
    rig = bpy.data.objects["NPC_Skeleton"]
    for side in ("l", "r"):
        a = rig.matrix_world @ rig.data.bones[f"upperarm_{side}"].head_local
        b = rig.matrix_world @ rig.data.bones[f"lowerarm_{side}"].head_local
        arm = ak.ArmFrame(a, b, sleeve_radius(jacket, side, a, b))
        shield = ak.rounded_poly([(-0.015, -0.115), (0.175, -0.100), (0.175, 0.100), (-0.015, 0.115)],
                                 [0.030, 0.050, 0.050, 0.030])
        ak.padded_panel(cordura, ak.OffsetFrame(arm, DELT_T / 2 + 0.002), shield, DELT_T, bulge=0.005, binding=0.012)
        ak.padded_panel(velc, ak.OffsetFrame(arm, DELT_T + 0.002 + 0.006 + 0.0012), am.rect(0.055, 0.150, -0.045, 0.045, 0.006),
                        0.003, bulge=0.0, binding=0.0, step=0.003)
        kc.log(f"  наплечник {side}: радиус рукава {arm.radius(0.0):.3f}…{arm.radius(0.17):.3f}")

    # Аварийный сброс: коробки на передней части лямок, трос с петлёй вниз по левому краю пакета.
    for sgn, sp in zip((1.0, -1.0), base["straps"]):
        u = 0.075
        p = sp.point(u, 0.0, 0.012)
        tan = (sp.point(u + 0.01, 0, 0) - sp.point(u, 0, 0)).normalized()
        n = sp.normal(u, 0)
        ak.rbox(plastic, p, n.cross(tan).normalized(), tan, n, (0.040, 0.034, 0.016), 0.006)
        if sgn > 0:
            pts = [sp.point(u - 0.010, 0.012, 0.010)]
            for vv, uu in ((0.31, 0.112), (0.27, 0.118), (0.235, 0.121), (0.215, 0.121)):
                pts.append(front.point(uu, vv, face + 0.004))
            ak.tube(metal, pts, 0.0022)
            end = front.point(0.121, 0.197, face + 0.006)
            ak.torus(metal, end, Vector((1, 0, 0)), 0.016, 0.0035)

    # Вертикальные фастексы боковой защиты (по два на бок).
    for band in base["bands"]:
        u_b = band.length - 0.105
        for v in (0.048, 0.118):
            c = band.point(u_b, v, SPEC.cummer_t + 0.005)
            tan = (band.point(u_b + 0.01, v, 0) - band.point(u_b, v, 0)).normalized()
            nrm = band.normal(u_b, v)
            ak.side_release(plastic, c, tan, nrm.cross(tan).normalized(), nrm, 0.025)

    # Спереди: панель живота под пакетом и паховая защита из двух лопастей с косыми стропами.
    abd = ak.PlateFrame(low, True, 0.990, 0.125, 0.27, 0.30, 0.009, 0.006)
    ak.padded_panel(cordura, abd, am.rect(-0.135, 0.135, 0.0, 0.125, 0.015), 0.018, bulge=0.003)
    ak.webbing_rows(web, abd, -0.11, 0.11, [0.022, 0.022 + am.MOLLE_PITCH], 0.009 + 0.0025)
    for sgn in (1.0, -1.0):
        lobe = ak.PlateFrame(low, True, 0.700, 0.300, 0.15, 0.25, SKIRT_T / 2, 0.004, x0=sgn * 0.083)
        out = ak.rounded_poly([(-0.055, 0.0), (0.055, 0.0), (0.075, 0.300), (-0.075, 0.300)], [0.040, 0.040, 0.008, 0.008])
        ak.padded_panel(cordura, lobe, out, SKIRT_T, bulge=0.003)
        rot = ak.RotFrame(lobe, -sgn * 40.0, 0.0, 0.175)
        ak.webbing_rows(web, rot, -0.040, 0.040, [-0.052, -0.012, 0.028], SKIRT_T / 2 + 0.0025)
    # Сзади: панель поясницы и фартук.
    lum = ak.PlateFrame(low, False, 0.990, 0.125, 0.28, 0.40, 0.009, 0.006)
    ak.padded_panel(cordura, lum, am.rect(-0.140, 0.140, 0.0, 0.125, 0.015), 0.018, bulge=0.003)
    ak.webbing_rows(web, lum, -0.115, 0.115, [0.022, 0.022 + am.MOLLE_PITCH], 0.009 + 0.0025)
    butt = ak.PlateFrame(low, False, 0.750, 0.250, 0.30, 0.24, SKIRT_T / 2, 0.006)
    ak.padded_panel(cordura, butt, ak.rounded_poly([(-0.155, 0.0), (0.155, 0.0), (0.150, 0.250), (-0.150, 0.250)],
                                                   [0.050, 0.050, 0.010, 0.010]), SKIRT_T, bulge=0.003)
    ak.webbing_rows(web, butt, -0.12, 0.12, [0.160, 0.160 + am.MOLLE_PITCH], SKIRT_T / 2 + 0.0025)

    cordura.build("Top_Collar_Shoulders_Skirts", col, [mats["cordura"]])
    web.build("Top_MOLLE_Extra", col, [mats["webbing"]])
    velc.build("Top_Velcro_Extra", col, [mats["velcro"]])
    plastic.build("Top_Release", col, [mats["plastic"]])
    metal.build("Top_Cable", col, [mats["metal"]])

    kc.log("ARMOR_TOP", len(col.objects), "объектов,", am.triangles(col), "треугольников")
    am.OUT.mkdir(parents=True, exist_ok=True)
    kc.save(am.OUT / "armor_top.blend")
    if "render" in args:
        am.render_previews(col, "top", focus_z=1.12, extra={
            "close_collar": ((0.45, -0.70, 1.70), (0.05, -0.05, 1.52)),
            "close_skirt": ((0.45, -0.95, 0.95), (0.0, -0.12, 0.88)),
        })
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        am.deliver(Path(dest), "Броня_крутая_v01_форма.blend", (
            "Тяжёлая броня «крутая» (уровень 3 из 3) — ФОРМА на согласование, материал нейтральный.\n"
            "По фото владельца (voenform.ru): плитоносец с высоким клапаном и толстым камербандом (боковые плиты,\n"
            "вертикальные фастексы), высокий воротник, наплечники с велкро, аварийный сброс с тросом,\n"
            "панель живота, паховая защита из двух лопастей, панель поясницы и фартук. Щитки бёдер — следующим шагом.\n"
            "Коллекция 06_Armor_Top; надета на мародёра v02 поверх куртки. Марки и нашивки с фото не переносятся.\n"
            "Скрипт: tools/npc_kit/armor_top.py.\n"), focus_z=1.12)


if __name__ == "__main__":
    main()
