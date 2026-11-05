# «Осока»: труба ТП-36 — корпус трубы, задняя обойма и кронштейн, антабка ремня, хомуты короба, хомут ГСН, раструб
# с желобками, передняя и задняя крышки (снимаются). Контуры — снимок КБМ (dims.py).
import math
import bmesh
import bpy
from lib import (MM, v, lathe, rounded_prism, finish, finish_small, px, _obj, auto_sharp, collection)
import dims as D


def ring(name, x0, x1, r_in, r_out, coll, mat, rnd=0.8, seg=96):
    """Кольцо (обойма, пояс) со скруглёнными кромками rnd."""
    rr = min(rnd, (r_out - r_in) * 0.45, (x1 - x0) * 0.3)
    prof = [(x0, r_in), (x0, r_out - rr), (x0 + rr * 0.3, r_out - rr * 0.3), (x0 + rr, r_out),
            (x1 - rr, r_out), (x1 - rr * 0.3, r_out - rr * 0.3), (x1, r_out - rr), (x1, r_in)]
    return lathe(name, prof, coll, mat, seg=seg)


def lathe_mod(name, prof, rfun, coll, mat, seg=160):
    """Тело вращения с радиусом, зависящим от угла: rfun(x, угол, r) → r (желобки, рифление)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for x, r in prof:
        ring_ = []
        for k in range(seg):
            a = 2 * math.pi * k / seg
            rr = rfun(x, a, r)
            ring_.append(bm.verts.new(v(x, rr * math.cos(a), rr * math.sin(a))))
        rings.append(ring_)
    n = len(rings)
    for i in range(n):
        r0, r1 = rings[i], rings[(i + 1) % n]
        for k in range(seg):
            j = (k + 1) % seg
            bm.faces.new((r0[k], r0[j], r1[j], r1[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return _obj(name, me, coll, mat)


def tube_body(coll):
    R, Ri = D.TUBE_R, D.TUBE_RIN
    x1 = D.TUBE_FRONT_X
    prof = [(0.0, Ri), (0.0, R - 0.6), (0.6, R), (x1, R), (x1, Ri)]
    o = lathe("Tube_body", prof, coll, "Paint_olive", seg=128)
    return o


def rear_parts(coll):
    x0, x1, r = D.REAR_SLEEVE
    ring("Tube_rear_sleeve", x0, x1, D.TUBE_R - 0.05, r, coll, "Paint_olive", rnd=1.2)
    # кронштейн под задним концом (опора / антабка): контур снимка, ширина — оценка
    pts = [px(x, y) for x, y in D.REAR_BRACKET_PX]
    from lib import fillet
    pts = fillet(pts, [2.5, 2.5, 3.0, 4.0, 4.0, 3.0], seg=5)
    o = rounded_prism("Tube_rear_bracket", pts, -15.0, 15.0, 2.2, coll, "Paint_olive")
    return o


def sling_band(coll):
    x0, x1, r = D.SLING_BAND
    o = ring("Tube_sling_band", x0, x1, D.TUBE_R - 0.05, r, coll, "Paint_olive", rnd=1.2)
    # проушина под пряжку ремня — сверху, чуть правее (ремень лежит по верху трубы)
    from lib import fillet
    pts = fillet([(x0 + 4, 0), (x1 - 4, 0), (x1 - 4, 9), (x0 + 4, 9)], [2.5] * 4, seg=4)
    pts = [(x, z + r - 1.5) for x, z in pts]
    lug = rounded_prism("Tube_sling_lug", pts, -9.0, 3.0, 1.2, coll, "Paint_olive")
    return o, lug


def clamps(coll):
    out = []
    for i, (x0, x1) in enumerate(D.CLAMPS):
        c = ring(f"Tube_clamp_{i}", x0, x1, D.TUBE_R - 0.05, D.CLAMP_R, coll, "Paint_olive", rnd=1.0)
        # ушко хомута вниз — к нему крепится короб пускового механизма (снимок: 454…472 пикс)
        from lib import fillet
        zt = -D.TUBE_R + 4.0
        pts = fillet([(x0 + 0.5, zt), (x1 - 0.5, zt), (x1 - 0.5, -45.0), (x0 + 0.5, -45.0)], [1.5, 1.5, 3.0, 3.0], seg=4)
        ear = rounded_prism(f"Tube_clamp_{i}_ear", pts, 14.0, 30.5, 1.0, coll, "Paint_olive")
        out += [c, ear]
    return out


def collar(coll):
    x0, x1, R = D.COLLAR
    b0, b1 = D.COLLAR_BAND_X
    Ri = 45.0
    prof = [(x0, D.TUBE_R - 0.3), (x0, R - 6.0), (x0 + 1.5, R - 2.2), (x0 + 4.0, R - 0.4), (x0 + 6.0, R),
            (b0 - 0.8, R), (b0, R - 0.9), (b1, R - 0.9), (b1 + 0.8, R),
            (x1 - 5.0, R), (x1 - 2.0, R - 0.8), (x1 - 0.4, R - 3.0), (x1, R - 6.0), (x1, Ri), (x0 + 12.0, Ri),
            (x0 + 8.0, D.TUBE_R - 0.3)]
    o = lathe("Tube_collar", prof, coll, "Paint_olive", seg=128)
    # оранжевая метка и отверстие на левом боку (снимок: 168, 410 и 196, 410)
    return o


def bell(coll):
    x0, x1, r0, r1 = D.BELL
    Ri = 43.0
    n = D.BELL_FLUTES
    xa, xb = x0 + 6.0, x1 - 10.0

    def rfun(x, a, r):
        if r < Ri + 0.5 or x < xa or x > xb:
            return r
        # желобки: впадина ~1.6 мм, ширина ~1/3 шага; концы желобка плавно выходят на поверхность
        ph = (a * n / (2 * math.pi)) % 1.0
        d = min(abs(ph - 0.5) / 0.17, 1.0)
        prof_ = 0.5 * (1 + math.cos(math.pi * d)) if d < 1.0 else 0.0
        t = min((x - xa) / 4.0, (xb - x) / 4.0, 1.0)
        return r - 1.6 * prof_ * t

    prof = []
    k = 24
    for i in range(k + 1):
        x = x0 + (x1 - 3.0 - x0) * i / k
        prof.append((x, r0 + (r1 - r0) * (x - x0) / (x1 - x0)))
    # передний поясок под крышку и скругление кромки
    prof += [(x1 - 1.8, r1 + 0.8), (x1 - 0.6, r1 + 0.5), (x1, r1 - 0.6), (x1, Ri + 0.8), (x1 - 0.8, Ri), (x0 + 2.0, Ri),
             (x0, Ri + 1.0)]
    o = lathe_mod("Tube_bell", prof, rfun, coll, "Paint_olive", seg=200)
    return o


def front_cap(coll):
    x0, x1, R = D.FRONT_CAP
    Rin = 50.9          # садится на поясок раструба R 51.1 — натяг резины
    face_t = 4.0
    prof = [(x0, Rin), (x0, R - 2.5), (x0 + 1.0, R - 1.0), (x0 + 3.0, R - 1.0),
            (x0 + 19.9, R - 1.0), (x0 + 20.0, R), (x1 - 3.0, R), (x1 - 0.8, R - 1.2), (x1, R - 4.0),
            (x1 + 0.6, 30.0), (x1 + 1.2, 0.0), (x1 - face_t + 1.2, 0.0), (x1 - face_t, 30.0), (x1 - face_t - 1.5, Rin),
            ]
    o = lathe("Front_cap", prof, coll, "Rubber_black", seg=128)
    # четыре выступа по ободу (снимок: «ушки» на кромке крышки) и жёлтая защёлка слева (снимки Кузьмина)
    lugs = []
    for k in range(4):
        a = math.radians(45 + 90 * k)
        from lib import fillet
        pts = fillet([(x0 + 21.0, R - 1.5), (x1 - 3.5, R - 1.5), (x1 - 3.5, R + 2.6), (x0 + 21.0, R + 2.6)],
                     [1.0, 1.0, 1.0, 1.0], seg=3)
        lug = rounded_prism(f"Front_cap_lug_{k}", pts, -4.5, 4.5, 0.9, coll, "Rubber_black")
        lug.rotation_euler = (a - math.pi / 2, 0, 0)
        from lib import apply_transform
        apply_transform(lug)
        lugs.append(lug)
    from lib import fillet, apply_transform
    pts = fillet([(x0 + 1.0, R - 3.0), (x0 + 15.0, R - 3.0), (x0 + 15.0, R + 3.5), (x0 + 1.0, R + 3.5)], [1.5] * 4, seg=3)
    latch = rounded_prism("Front_cap_latch", pts, -6.0, 6.0, 1.2, coll, "Plastic_yellow")
    latch.rotation_euler = (math.radians(70) - math.pi / 2, 0, 0)
    apply_transform(latch)
    return [o] + lugs + [latch]


def rear_cap(coll):
    x0, x1, R = D.REAR_CAP          # x0 −37.15 (торец), x1 = 0 (задний торец трубы)
    Rs = D.REAR_SLEEVE[2] + 0.1     # садится на обойму
    prof = [(x1 + 6.0, Rs), (x1 + 6.0, Rs + 2.0), (x1 + 5.0, Rs + 3.2), (x1 + 1.0, R - 2.0), (x1 - 2.0, R),
            (x0 + 6.0, R), (x0 + 1.6, R - 1.0), (x0, R - 5.0), (x0 - 0.8, 25.0), (x0 - 1.4, 0.0),
            (x0 + 3.0, 0.0), (x0 + 3.6, 25.0), (x0 + 5.0, Rs - 1.0), (x1 - 3.0, Rs - 1.5), (x1 - 1.0, Rs)]
    o = lathe("Rear_cap", prof, coll, "Rubber_black", seg=128)
    # прилив защёлки внизу слева (снимок: 2545…2585 × 410…485)
    from lib import fillet, apply_transform
    pts = fillet([(x0 + 6.0, R - 4.0), (x1 + 2.0, R - 4.0), (x1 + 2.0, R + 3.0), (x0 + 8.0, R + 3.0)], [2.0] * 4, seg=3)
    lug = rounded_prism("Rear_cap_latch", pts, -8.0, 8.0, 1.5, coll, "Rubber_black")
    lug.rotation_euler = (math.radians(-110) - math.pi / 2, 0, 0)
    apply_transform(lug)
    return [o, lug]


def build(ctx):
    C = ctx["coll"]["Tube"]
    caps = ctx["coll"]["Caps"]
    parts = [tube_body(C)]
    parts.append(rear_parts(C))
    parts += list(sling_band(C))
    parts += clamps(C)
    parts.append(collar(C))
    parts.append(bell(C))
    fc = front_cap(caps)
    rc = rear_cap(caps)
    return {"front_cap": fc, "rear_cap": rc}
