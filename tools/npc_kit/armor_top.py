"""NPC: тяжёлая броня «крутая» (уровень 3 из 3) по фото владельца — плитоносец с надставками.

База — тот же плитоносец (armor_mid.build_carrier: передний пакет — карман со сменой плиты сверху)
с высоким клапаном на пять рядов MOLLE и высоким толстым камербандом (в нём боковые плиты, вертикальные
фастексы сброса); на заднем пакете по бокам молнии под пристёгиваемую заднюю панель. Надставки: высокий
мягкий воротник — сплошное кольцо вокруг шеи с застёжкой-клапаном спереди; от воротника по плечам —
мягкие погоны поверх лямок, к ним снизу на кнопках пристёгнуты наплечники (два сегмента внахлёст,
нижний — с велкро под нашивку), ремень вокруг руки; на лямках — коробки аварийного сброса и трос
с петлёй; спереди — панель живота с MOLLE и паховая защита из двух лопастей с косыми стропами,
между ними центральная лента; сзади — панель поясницы и фартук; по бокам поясной ремень, на нём
на стропах — щитки бёдер, огибающие бедро снаружи, внизу — ремень вокруг ноги с фастексом.
Устройство деталей сверено с фото серийных тяжёлых комплектов (погон с воротником и наплечником —
как у IOTV и Warmor, щитки бёдер с ножным ремнём). Нашивки и марки с фото не переносятся.

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

SPEC = am.CarrierSpec(prefix="Top", flap_h=0.215, flap_rows=5, front_rows=[], cummer_h=0.185, cummer_t=0.020,
                      cummer_rows=3, pad=(0.080, 0.020), admin=(-0.070, 0.070, 0.232, 0.300, 4, 3),
                      side_buckles=False, cable_loops=False, back_molle_u=0.096,
                      back_velcro=(-0.096, 0.096, 0.215, 0.352), keeper_v=(0.232, 0.285))
COLLAR_H, COLLAR_T = 0.120, 0.024
DELT_T = 0.020
YOKE_T = 0.012                      # погон от воротника к наплечнику
SKIRT_T = 0.016                     # лопасти паха, фартук, щитки бёдер
BELT_H = 0.088                      # мягкий пояс по бокам
THIGH_U = (-0.025, 0.330)           # щиток бедра: от пояса (выше тазобедренного сустава) до середины бедра и ниже


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
    # Прямая по замерам (0…22 см): радиус плавный — иначе на наплечнике и велкро ступеньки.
    pts = []
    for k, rs in bins.items():
        if 0 <= k <= 22 and len(rs) > 4:
            rs.sort()
            pts.append((k * 0.01, rs[int(len(rs) * 0.9)]))
    n = len(pts)
    mu = sum(u for u, _ in pts) / n
    mr = sum(r for _, r in pts) / n
    slope = sum((u - mu) * (r - mr) for u, r in pts) / max(sum((u - mu) ** 2 for u, _ in pts), 1e-9)

    def r(u: float) -> float:
        return mr + slope * (max(0.0, min(0.22, u)) - mu) + 0.005
    return r


def collar_outline(length: float) -> list[tuple[float, float]]:
    """Воротник — кольцо от середины переда вокруг шеи обратно к середине переда: сзади 11 см,
    спереди 8,5 см (стык спереди закрывает клапан застёжки)."""
    top = []
    n = 32
    for i in range(n, -1, -1):
        u = length * i / n
        top.append((u, 0.085 + 0.025 * math.sin(math.pi * u / length) ** 2))
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

    # Воротник вокруг шеи поверх трикотажного воротника куртки и балаклавы.
    neck_objs = [jacket] + [o for o in bpy.data.objects if o.name == "Balaclava"]
    neck = ak.Hull(neck_objs, 1.46, 1.64, x_max=0.14)
    collar = ak.NeckFrame(neck, 1.47, COLLAR_H, -90.0, 270.0, 0.004)
    ak.padded_panel(cordura, ak.OffsetFrame(collar, COLLAR_T / 2), collar_outline(collar.length), COLLAR_T,
                    bulge=0.006, binding=0.014, step=0.006)
    # Застёжка спереди: клапан поверх стыка, на нём велкро.
    flap = ak.OffsetFrame(collar, COLLAR_T + 0.004)
    tab = am.rect(collar.length - 0.035, collar.length + 0.035, 0.010, 0.078, 0.012)
    ak.padded_panel(cordura, flap, tab, 0.006, bulge=0.001, binding=0.008, step=0.004)
    ak.padded_panel(velc, ak.OffsetFrame(collar, COLLAR_T + 0.0085), am.rect(collar.length - 0.022, collar.length + 0.022,
                    0.024, 0.064, 0.006), 0.003, bulge=0.0, binding=0.0, step=0.003)
    kc.log(f"  воротник: длина {collar.length:.3f} м")

    # Плечо: погон от воротника поверх накладки лямки к верху наплечника; наплечник — два сегмента
    # внахлёст, верхний заходит под конец погона и пристёгнут к нему кнопками (так он держится на броне,
    # а не висит на рукаве), нижний — с велкро под нашивку; ремень вокруг руки.
    rig = bpy.data.objects["NPC_Skeleton"]
    jco = [jacket.matrix_world @ v.co for v in jacket.data.vertices]
    sleeve_bvh = ak.BVHTree.FromPolygons(jco, [list(pp.vertices) for pp in jacket.data.polygons])
    torso_parts = ak.mesh_parts(jacket, ("piece_collar", "piece_sleeve", "piece_cuff"))
    torso_bvh = ak.bvh_of([torso_parts])
    pads_bvh = ak.bvh_of([ak.mesh_parts(bpy.data.objects[f"{SPEC.prefix}_Shoulder_Pads"])])
    shoulders = ak.Mesh()                           # погоны и наплечники — отдельный объект (снимаются)
    for side, sp, sgn in zip(("l", "r"), base["straps"], (1.0, -1.0)):
        a = rig.matrix_world @ rig.data.bones[f"upperarm_{side}"].head_local
        b = rig.matrix_world @ rig.data.bones[f"lowerarm_{side}"].head_local
        arm = ak.ArmFrame(a, b, sleeve_radius(jacket, side, a, b))
        delt = ak.Mesh()
        upper = ak.rounded_poly([(-0.070, -0.095), (0.075, -0.110), (0.075, 0.110), (-0.070, 0.095)],
                                [0.040, 0.020, 0.020, 0.040])
        ak.padded_panel(delt, ak.OffsetFrame(arm, DELT_T / 2 + 0.002), upper, DELT_T, bulge=0.005, binding=0.012)
        delt_bvh = ak.bvh_of([(delt.verts, delt.faces)])
        lower = ak.rounded_poly([(0.055, -0.110), (0.180, -0.095), (0.180, 0.095), (0.055, 0.110)],
                                [0.015, 0.045, 0.045, 0.015])
        ak.padded_panel(delt, ak.OffsetFrame(arm, DELT_T * 1.5 + 0.003), lower, DELT_T, bulge=0.005, binding=0.012)
        n0 = len(shoulders.verts)
        shoulders.verts += delt.verts
        shoulders.faces += [[n0 + i for i in fc] for fc in delt.faces]
        shoulders.uvs += delt.uvs
        shoulders.mats += delt.mats
        ak.padded_panel(velc, ak.OffsetFrame(arm, DELT_T * 2 + 0.003 + 0.005 + 0.0012),
                        am.rect(0.085, 0.165, -0.045, 0.045, 0.006), 0.003, bulge=0.0, binding=0.0, step=0.003)
        ak.webbing_rows(web, ak.RotFrame(arm, 90.0, 0.0, 0.0), -0.06, 0.06, [-0.045], DELT_T + 0.002 + 0.0025)
        # ремень вокруг руки (под мышкой) — по самому рукаву
        r_u = arm.radius(0.165)
        pts, nrm = [], []
        for k in range(41):
            v = 0.085 + (2 * math.pi * r_u - 0.17) * k / 40
            q = arm.point(0.165, v, 0.0)
            loc, n, _, _ = sleeve_bvh.find_nearest(q)
            out = arm.normal(0.165, v)
            pts.append(loc + out * 0.004)
            nrm.append(out)
        ak.strap(web, ak.RibbonFrame(pts, nrm), 0.025, 0.003)

        # Погон: оболочка вокруг оси «основание шеи → плечевой сустав», ложится по плечу поверх куртки,
        # накладки лямки и верха наплечника; внутренний конец уходит под воротник.
        y_c = sp.point(sp.length * 0.48, 0.0, 0.0).y
        c0 = Vector((sgn * 0.02, y_c, a.z - 0.01))
        u_start = (a - c0).length - 0.080                           # под воротником
        u_end = (a - c0).length + 0.025                             # над верхом наплечника
        yoke = ak.ShellFrame(c0, a, [(torso_bvh, 0.008), (pads_bvh, 0.0025),
                             (delt_bvh, 0.0015)], u_start - 0.01, u_end + 0.01, math.radians(-80.0), math.radians(80.0),
                             0.10, ref=Vector((0.0, 0.0, 1.0)), side_hint=Vector((0.0, -1.0, 0.0)), fill="valleys", convex=True)
        yf = ak.OffsetFrame(yoke, YOKE_T / 2)
        yo = ak.rounded_poly([(u_start, -0.066), (u_end, -0.058), (u_end, 0.058), (u_start, 0.066)],
                             [0.010, 0.026, 0.026, 0.010])
        ak.padded_panel(shoulders, yf, yo, YOKE_T, bulge=0.003, binding=0.010)
        for w in (-0.030, 0.030):                                    # кнопки к наплечнику
            ak.torus(metal, yf.point(u_end - 0.022, w, YOKE_T / 2 + 0.0012), yf.normal(u_end - 0.022, w),
                     0.0045, 0.0019, seg=14, sides=6)
        kc.log(f"  погон {side}: u {u_start:.3f}…{u_end:.3f}, радиус по оси {yoke.radius(u_start, 0):.3f}…"
               f"{yoke.radius(u_end, 0):.3f}; наплечник: радиус рукава {arm.radius(0.0):.3f}…{arm.radius(0.17):.3f}")

    # Аварийный сброс: коробки на передней части лямок; трос от коробки идёт по лямке и уходит за пакет
    # (внутри брони — клапан кармана им не перекрыт), ручка сброса — петля из-за клапана «кенгуру» справа.
    flap_base = ak.OffsetFrame(front, SPEC.bag_t / 2 + SPEC.cummer_t + 0.003)
    for sgn, sp in zip((1.0, -1.0), base["straps"]):
        u = 0.075
        p = sp.point(u, 0.0, 0.012)
        tan = (sp.point(u + 0.01, 0, 0) - sp.point(u, 0, 0)).normalized()
        n = sp.normal(u, 0)
        ak.rbox(plastic, p, n.cross(tan).normalized(), tan, n, (0.040, 0.034, 0.016), 0.006)
        if sgn > 0:
            ak.tube(metal, [sp.point(uu, 0.012, oo) for uu, oo in ((u - 0.012, 0.009), (u - 0.035, 0.0065),
                                                                  (u - 0.055, 0.0055), (u - 0.070, 0.005))], 0.0022)
            uc = 0.135
            ak.tube(metal, [flap_base.point(uc, SPEC.flap_h - 0.025, SPEC.flap_t * 0.5),
                            flap_base.point(uc, SPEC.flap_h + 0.004, SPEC.flap_t * 0.55)], 0.0022)
            ak.torus(metal, flap_base.point(uc, SPEC.flap_h + 0.019, SPEC.flap_t * 0.55), Vector((1, 0, 0)), 0.016, 0.0035)

    # Вертикальные фастексы боковой защиты (по два на бок).
    for band in base["bands"]:
        u_b = band.length - 0.105
        for v in (0.055, 0.140):
            c = band.point(u_b, v, SPEC.cummer_t + 0.005)
            tan = (band.point(u_b + 0.01, v, 0) - band.point(u_b, v, 0)).normalized()
            nrm = band.normal(u_b, v)
            ak.side_release(plastic, c, tan, nrm.cross(tan).normalized(), nrm, 0.025)

    # Сзади на пакете — молнии под пристёгиваемую заднюю панель (рюкзак, панель с подсумками).
    for uc in (-0.112, 0.112):
        vs = [0.035 + 0.215 * k / 40 for k in range(41)]
        rib = ak.RibbonFrame([back.point(uc, v, face + 0.0006) for v in vs], [back.normal(uc, v) for v in vs])
        ak.zipper(web, plastic, rib, 0.0, pull_at=rib.length - 0.010)

    # Спереди: панель живота под пакетом и паховая защита из двух лопастей с косыми стропами.
    abd = ak.PlateFrame(low, True, 0.990, 0.125, 0.27, 0.30, 0.009, 0.006)
    ak.padded_panel(cordura, abd, am.rect(-0.135, 0.135, 0.0, 0.125, 0.015), 0.018, bulge=0.003)
    ak.webbing_rows(web, abd, -0.11, 0.11, [0.022, 0.022 + am.MOLLE_PITCH], 0.009 + 0.0025)
    lobes = []
    for sgn in (1.0, -1.0):
        lobe = ak.PlateFrame(low, True, 0.700, 0.300, 0.15, 0.25, SKIRT_T / 2, 0.004, x0=sgn * 0.083)
        lobes.append(lobe)
        out = ak.rounded_poly([(-0.055, 0.0), (0.055, 0.0), (0.075, 0.300), (-0.075, 0.300)], [0.040, 0.040, 0.008, 0.008])
        ak.padded_panel(cordura, lobe, out, SKIRT_T, bulge=0.003)
        rot = ak.RotFrame(lobe, -sgn * 40.0, 0.0, 0.175)
        ak.webbing_rows(web, rot, -0.040, 0.040, [-0.052, -0.012, 0.028], SKIRT_T / 2 + 0.0025)
    # Центральная лента: из-под панели живота вниз по стыку лопастей, с лестничной пряжкой.
    pts = []
    for k in range(29):
        z = 1.010 - 0.280 * k / 28
        if z >= 0.995:
            y = abd.point(0.0, z - 0.990, 0.009 + 0.0035).y
        else:
            y = min(lobes[0].point(-0.068, z - 0.700, SKIRT_T / 2 + 0.0045).y,
                    lobes[1].point(0.068, z - 0.700, SKIRT_T / 2 + 0.0045).y)
        pts.append(Vector((0.0, y, z)))
    for _ in range(2):
        pts = [pts[0]] + [pts[i - 1] * 0.25 + pts[i] * 0.5 + pts[i + 1] * 0.25 for i in range(1, len(pts) - 1)] + [pts[-1]]
    cen = ak.RibbonFrame(pts, [Vector((0.0, -1.0, 0.0))] * len(pts))
    ak.strap(web, cen, 0.038, 0.003)
    ul = cen.length * 0.42
    ak.ladder_lock(plastic, cen.point(ul, 0.0, 0.004), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, -1, 0)), 0.038)
    # Сзади: панель поясницы и фартук.
    lum = ak.PlateFrame(low, False, 0.990, 0.125, 0.28, 0.40, 0.009, 0.006)
    ak.padded_panel(cordura, lum, am.rect(-0.140, 0.140, 0.0, 0.125, 0.015), 0.018, bulge=0.003)
    ak.webbing_rows(web, lum, -0.115, 0.115, [0.022, 0.022 + am.MOLLE_PITCH], 0.009 + 0.0025)
    butt = ak.PlateFrame(low, False, 0.750, 0.250, 0.30, 0.24, SKIRT_T / 2, 0.006)
    ak.padded_panel(cordura, butt, ak.rounded_poly([(-0.155, 0.0), (0.155, 0.0), (0.150, 0.250), (-0.150, 0.250)],
                                                   [0.050, 0.050, 0.010, 0.010]), SKIRT_T, bulge=0.003)
    ak.webbing_rows(web, butt, -0.12, 0.12, [0.160, 0.160 + am.MOLLE_PITCH], SKIRT_T / 2 + 0.0025)

    # По бокам — мягкий пояс с двумя рядами MOLLE (между панелью живота и поясницы), на нём висят щитки бёдер.
    for a0, a1 in ((-52.0, 52.0), (128.0, 232.0)):
        belt = ak.BandFrame(low, 0.962, BELT_H, a0, a1, 0.005)
        ak.padded_panel(cordura, ak.OffsetFrame(belt, 0.006), am.rect(0.0, belt.length, 0.0, BELT_H, 0.010), 0.012,
                        bulge=0.0015, binding=0.009)
        ak.webbing_rows(web, ak.OffsetFrame(belt, 0.012), 0.02, belt.length - 0.02, [0.014, 0.014 + am.MOLLE_PITCH], 0.0005)

    # Щитки бёдер: огибают бедро снаружи (от передне-наружной стороны до задне-наружной), висят на двух
    # стропах с пояса, внизу — ремень вокруг ноги с фастексом (щиток не болтается при беге).
    pants_objs = [o for o in bpy.data.collections["02_Pants"].all_objects if o.type == "MESH"]
    pants_bvh = ak.bvh_of([ak.mesh_parts(o) for o in pants_objs])
    ring = low.ring(0.992)
    th_top, th_bot = (math.radians(45.0), math.radians(150.0)), (math.radians(35.0), math.radians(145.0))
    R0 = 0.12                                       # опорный радиус развёртки щитка
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        a = rig.matrix_world @ rig.data.bones[f"thigh_{side}"].head_local
        b = rig.matrix_world @ rig.data.bones[f"calf_{side}"].head_local
        u0, u1 = THIGH_U
        # по штанам с карманами — зазор 6 мм, куртку у бедра щиток поджимает на 1 см
        leg = ak.ShellFrame(a, b, [(pants_bvh, 0.006), (torso_bvh, -0.010)], u0 - 0.01, u1 + 0.01,
                            math.radians(25.0), math.radians(160.0), R0, ref=Vector((0.0, -1.0, 0.0)),
                            side_hint=Vector((sgn, 0.0, 0.0)), fill="taper", convex=True)

        def th_at(u: float, k: int) -> float:
            t = (u - u0) / (u1 - u0)
            return th_top[k] + (th_bot[k] - th_top[k]) * t
        n_side = 10
        right = [(u1 - (u1 - u0) * i / n_side, th_at(u1 - (u1 - u0) * i / n_side, 1)) for i in range(n_side + 1)]
        left = [(u0 + (u1 - u0) * i / n_side, th_at(u0 + (u1 - u0) * i / n_side, 0)) for i in range(n_side + 1)]
        corners = left + right                                   # вниз по передне-наружному краю, вверх по заднему
        uv = [(u, th * R0) for u, th in corners]
        radii = [0.0] * len(uv)
        radii[0], radii[n_side], radii[n_side + 1], radii[-1] = 0.012, 0.035, 0.035, 0.012
        guard = ak.OffsetFrame(leg, SKIRT_T / 2)
        ak.padded_panel(cordura, guard, ak.rounded_poly(uv, radii), SKIRT_T, bulge=0.003, step=0.007)
        # два ряда MOLLE поперёк щитка вверху
        um = 0.075
        ak.webbing_rows(web, ak.RotFrame(leg, 90.0, 0.0, 0.0), math.radians(62.0) * R0, math.radians(140.0) * R0,
                        [-0.060, -0.060 - am.MOLLE_PITCH], SKIRT_T + 0.0035)
        # стропы к поясу
        cx, cy = ring.c
        for thd in (70.0, 135.0):
            th = math.radians(thd)
            top = leg.point(u0 + 0.014, th * R0, SKIRT_T + 0.0045)
            ang = math.degrees(math.atan2(top.y - cy, top.x - cx))
            bx, by = ring.point(ang)
            radial = Vector((bx - cx, by - cy, 0.0)).normalized()
            end = Vector((bx, by, 0.995)) + radial * 0.017
            pts = [top.lerp(end, k / 8) for k in range(9)]
            nn = (leg.normal(u0, th * R0) + radial).normalized()
            ak.strap(web, ak.RibbonFrame(pts, [nn] * len(pts)), 0.025, 0.003)
            mid_p = top.lerp(end, 0.45) + nn * 0.003
            ak.ladder_lock(plastic, mid_p, nn.cross((end - top).normalized()).normalized(), (end - top).normalized(), nn, 0.025)
        # ремень вокруг ноги: от заднего края щитка через внутреннюю сторону к переднему, фастекс спереди
        us = u1 - 0.040
        pts, nrm = [], []
        th_a, th_b = th_at(us, 1) - math.radians(8.0), th_at(us, 0) + 2 * math.pi + math.radians(8.0)
        for k in range(49):
            th = th_a + (th_b - th_a) * k / 48
            d = (leg.e_up * math.cos(th) + leg.e_side * math.sin(th)).normalized()
            inside = leg.a + leg.d * us + d * 0.045
            loc, _, _, _ = pants_bvh.find_nearest(inside)
            pts.append(loc + d * 0.0035)
            nrm.append(d)
        strap_rib = ak.RibbonFrame(pts, nrm)
        ak.strap(web, strap_rib, 0.025, 0.003)
        ub = strap_rib.length * ((math.radians(345.0) - th_a) / (th_b - th_a))
        p, tan, nn = strap_rib._at(ub)
        ak.side_release(plastic, p + nn * 0.005, nn.cross(tan).normalized(), tan, nn, 0.025)
        kc.log(f"  щиток бедра {side}: радиус {leg.radius(u0, 1.6):.3f} вверху … {leg.radius(u1, 1.6):.3f} внизу (снаружи)")

    cordura.build("Top_Collar_Skirts", col, [mats["cordura"]])
    shoulders.build("Top_Shoulders", col, [mats["cordura"]])
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
            "close_shoulder": ((0.55, -0.55, 1.66), (0.18, -0.02, 1.47)),
            "close_thigh": ((0.85, -0.55, 0.85), (0.15, -0.02, 0.78)),
            "close_back": ((0.40, 0.85, 1.30), (0.0, 0.12, 1.25)),
        })
    dest = next((a.split("=", 1)[1] for a in args if a.startswith("deliver=")), None)
    if dest:
        am.deliver(Path(dest), "Броня_крутая_v03_форма.blend", (
            "Тяжёлая броня «крутая» (уровень 3 из 3) — ФОРМА v03 (принята с исправлением кармана), материал нейтральный.\n"
            "По фото владельца (voenform.ru) и фото серийных тяжёлых комплектов: плитоносец с карманом смены плиты\n"
            "спереди (горловина-подкова; клапан Top_Pocket_Lid с язычком — ключ формы «Открыт»; плита Top_Plate_Front\n"
            "вынимается по своей оси Z, выше воротника её надо наклонить вперёд или отстегнуть клапан воротника),\n"
            "высоким клапаном\n"
            "и камербандом (боковые плиты, вертикальные фастексы), молнии сзади под панель; сплошной воротник,\n"
            "погоны от воротника, к ним на кнопках наплечники, аварийный сброс с тросом, панель живота, пах из\n"
            "двух лопастей с центральной лентой, поясница и фартук, щитки бёдер вокруг ноги с ножным ремнём.\n"
            "Коллекция 06_Armor_Top; надета на мародёра v02 поверх куртки. Марки и нашивки с фото не переносятся.\n"
            "Скрипт: tools/npc_kit/armor_top.py.\n"), focus_z=1.12)


if __name__ == "__main__":
    main()
