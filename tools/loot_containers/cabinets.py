"""Оружейный шкаф и картотечный шкаф."""
import math

import bmesh
from mathutils import Matrix

import lc
from lc import L, V, part, shell_part, cyl, plug, tray_door, rot_box


def _rz(ob, deg):
    ob.rotation_euler = (0, 0, math.radians(deg))


# ================================================================ оружейный шкаф

def gun_cabinet(coll, m, at, open_: bool):
    """Оружейный шкаф 800 × 1800 × 450: корпус из листа 1,2 мм на цоколе, отбортовка проёма, две створки врезные
    (лист 1,5 мм с отбортовкой; сверху жалюзийные просечки), наружные петли-штыри, ручка-замок на правой створке,
    тяги ригельного запора вверх-вниз на внутренней стороне (направляющие, концы-ригели, ответные скобы на корпусе);
    внутри — ложемент на пять длинных стволов (нижняя планка с выемками, верхняя гребёнка), верхняя полка и
    запираемый ящик для патронов. Оружия нет."""
    r = L.root("ОШ_шкаф_оружейный" + ("_открыт" if open_ else ""), coll, at)
    W, D, H, zb = 0.80, 0.45, 1.80, 0.05
    hw, yf = W / 2, -D / 2
    body = shell_part("ОШ_корпус", coll, [m["steel_b"]], r, (W, D, H - zb), 0.008, (0, 0, (H + zb) / 2), "-y", 0.0012, seg=2, flat=(2, 2, 6))
    # цоколь: утопленная плита, нижняя обвязка и ножки
    pb = bmesh.new()
    lc.rbox(pb, (W - 0.03, D - 0.05, zb - 0.012), 0.004, (0, 0.012, (zb - 0.012) / 2 + 0.012 - 0.0), seg=2)
    lc.obj(pb, "ОШ_цоколь", coll, [m["steel_c"]], r, smooth=45)
    ft = bmesh.new()
    for x in (-hw + 0.04, hw - 0.04):
        for y in (yf + 0.05, -yf - 0.05):
            cyl(ft, (x, y, 0.0), (x, y, 0.014), 0.02, segs=20)
    lc.obj(ft, "ОШ_ножки", coll, [m["rubber"]], r, smooth=50)
    # отбортовка проёма внутрь: полоса 20 мм по периметру, в верхней и нижней — скобы под ригели (по паре стоек)
    t = 0.0015
    lip = bmesh.new()
    zt, zbt = H - 0.0012, zb + 0.0012
    ln = 0.020
    L.bm_box(lip, (-hw, yf, zbt), (-hw + ln, yf + t, zt))
    L.bm_box(lip, (hw - ln, yf, zbt), (hw, yf + t, zt))
    L.bm_box(lip, (-hw + ln, yf, zt - ln), (hw - ln, yf + t, zt))
    L.bm_box(lip, (-hw + ln, yf, zbt), (hw - ln, yf + t, zbt + ln))
    bolt_x = (-0.33, 0.33)
    for bx in bolt_x:
        for zz, sg in ((zt - ln, -1), (zbt + ln, 1)):
            for dx in (-0.011, 0.011):
                z0_, z1_ = (zz - 0.04, zz) if sg < 0 else (zz, zz + 0.04)
                L.bm_box(lip, (bx + dx - 0.0012, yf, z0_), (bx + dx + 0.0012, yf + 0.026, z1_))
    lc.obj(lip, "ОШ_отбортовка_скобы", coll, [m["steel_b"]], r, bevel=0.0004, segs=1, smooth=45)
    # ---- ложемент
    rk = bmesh.new()
    xs = [-0.30, -0.15, 0.0, 0.15, 0.30]
    # нижняя планка с выемками под приклады: основание + зубцы между выемками
    yb0, yb1 = -0.17, -0.02
    zl = zb + 0.0012
    lc.rbox(rk, (W - 0.03, yb1 - yb0, 0.010), 0.003, (0, (yb0 + yb1) / 2, zl + 0.005), seg=2)
    edges = [-hw + 0.012] + sum([[x - 0.038, x + 0.038] for x in xs], []) + [hw - 0.012]
    for k in range(0, len(edges), 2):
        L.bm_box(rk, (edges[k], yb0, zl + 0.010), (edges[k + 1], yb1, zl + 0.045))
    # верхняя гребёнка под стволы: задняя полоса и зубцы между U-образными пазами
    zc = 1.20
    yc0, yc1 = -0.14, -0.06
    L.bm_box(rk, (-hw + 0.012, yc1 - 0.014, zc), (hw - 0.012, yc1, zc + 0.030))
    edges = [-hw + 0.012] + sum([[x - 0.024, x + 0.024] for x in xs], []) + [hw - 0.012]
    for k in range(0, len(edges), 2):
        L.bm_box(rk, (edges[k], yc0, zc), (edges[k + 1], yc1 - 0.014, zc + 0.030))
    # кронштейны гребёнки к боковинам
    for s in (-1, 1):
        L.bm_box(rk, (s * (hw - 0.0012) - (0.012 if s > 0 else 0), yc0, zc - 0.05), (s * (hw - 0.0012) + (0 if s > 0 else 0.012), yc1, zc + 0.030))
    lc.obj(rk, "ОШ_ложемент", coll, [m["steel_c"]], r, bevel=0.0012, segs=2, smooth=45)
    # накладки-мягкие (войлок) в выемках и пазах
    fl = bmesh.new()
    for x in xs:
        L.bm_box(fl, (x - 0.036, yb0 + 0.002, zl + 0.0105), (x + 0.036, yb1 - 0.002, zl + 0.0125))
        L.bm_box(fl, (x - 0.022, yc0 + 0.002, zc + 0.030), (x + 0.022, yc1 - 0.016, zc + 0.032))
    lc.obj(fl, "ОШ_ложемент_войлок", coll, [m["felt"]], r, smooth=45)
    # верхняя полка и ящик для патронов
    zs = 1.50
    sh = bmesh.new()
    lc.rbox(sh, (W - 0.012, D - 0.06, 0.0025), 0.001, (0, 0.012, zs), seg=2)
    L.bm_box(sh, (-hw + 0.03, yf + 0.0, zs), (hw - 0.03, yf + 0.003, zs + 0.025))
    lc.obj(sh, "ОШ_полка", coll, [m["steel_c"]], r, bevel=0.0006, segs=1, smooth=45)
    ax, aw, ad, ah = 0.20, 0.34, 0.30, 0.22
    ay0 = yf + 0.03
    abox = shell_part("ОШ_ящик_патроны", coll, [m["steel_c"]], r, (aw, ad, ah), 0.004, (ax, ay0 + ad / 2, zs + 0.0013 + ah / 2), "-y", 0.0015, seg=2)
    apiv = (ax - aw / 2 - 0.002, ay0 - 0.006, 0.0)
    ad_door = bmesh.new()
    tray_door(ad_door, ax - aw / 2 + 0.001, ax + aw / 2 - 0.001, zs + 0.0013, zs + 0.0013 + ah, ay0 - 0.012, 0.0105, 0.0015)
    plug(ad_door, (ax + aw / 2 - 0.035, ay0 - 0.012, zs + 0.0013 + ah / 2), depth=0.003, r=0.006, axis="-y")
    L.bm_cyl(ad_door, (ax + aw / 2 - 0.035, ay0 - 0.012, zs + 0.0013 + ah / 2), (ax + aw / 2 - 0.035, ay0 - 0.0135, zs + 0.0013 + ah / 2), 0.012, segs=18)
    part(ad_door, "ОШ_ящик_патроны_дверца", coll, [m["steel_a"]], r, (0, 0, 0), apiv, bevel=0.0004, segs=1, smooth=45, mover=True)
    # ---- створки
    dz0, dz1 = zb + 0.016, H - 0.016
    dd, dt = 0.030, 0.0015
    ch = (dz0 + dz1) / 2
    lx = (-hw + ln + 0.002, -0.0015)       # левая: x от…до
    rx = (0.0015, hw - ln - 0.002)
    doors = {}
    for side, (x0, x1), s in (("лев", lx, -1), ("прав", rx, 1)):
        pivx = x0 - 0.0035 if s < 0 else x1 + 0.0035
        piv = (pivx, yf - 0.006, 0.0)
        wx0, wx1 = x0 + 0.05, x1 - 0.05
        win = (wx0, wx1, dz1 - 0.36, dz1 - 0.12)
        db = bmesh.new()
        tray_door(db, x0, x1, dz0, dz1, yf - 0.0015, dd, dt, win=win)
        # рамка окна изнутри (отбортовка просечек)
        L.bm_box(db, (wx0, yf + 0.0, win[2] - 0.0), (wx0 + dt, yf + 0.014, win[3]))
        L.bm_box(db, (wx1 - dt, yf + 0.0, win[2] - 0.0), (wx1, yf + 0.014, win[3]))
        L.bm_box(db, (wx0, yf + 0.0, win[2]), (wx1, yf + 0.014, win[2] + dt))
        L.bm_box(db, (wx0, yf + 0.0, win[3] - dt), (wx1, yf + 0.014, win[3]))
        d = part(db, f"ОШ_створка_{side}", coll, [m["steel_b"]], r, (0, 0, 0), piv, bevel=0.0005, segs=1, smooth=45, mover=True)
        doors[side] = (d, piv, x0, x1, s)
        # жалюзи: наклонные пластины в окне, заглублены на 6 мм
        nb = 10
        jb = bmesh.new()
        for k in range(nb):
            zk = win[2] + 0.012 + k * (win[3] - win[2] - 0.024) / (nb - 1)
            n0 = len(jb.verts)
            rot_box(jb, (wx0 + dt, -0.0009, -0.0155), (wx1 - dt, 0.0009, 0.0155), (0, 0, 0), Matrix.Rotation(math.radians(40), 3, "X"))
            jb.verts.ensure_lookup_table()
            for v in jb.verts[n0:]:
                v.co += V((0, yf + 0.006, zk))
        part(jb, f"ОШ_жалюзи_{side}", coll, [m["steel_b"]], d, piv, piv, bevel=0.0003, segs=1, smooth=45)
        # петли: звенья на оси (дверные + корпусные)
        hb = bmesh.new()
        kb = bmesh.new()
        for z in (0.30, 0.90, 1.50):
            cyl(hb, (piv[0], piv[1], z - 0.04), (piv[0], piv[1], z + 0.04), 0.0065, segs=16)
            ex = x0 if s < 0 else x1
            L.bm_box(hb, (min(piv[0], ex), piv[1] - 0.0035, z - 0.04), (max(piv[0], ex), piv[1] + 0.0055, z + 0.04))
            for zz in (z - 0.07, z + 0.07):
                cyl(kb, (piv[0], piv[1], zz - 0.015), (piv[0], piv[1], zz + 0.015), 0.0065, segs=16)
                L.bm_box(kb, (min(piv[0], s * hw), piv[1] - 0.0035, zz - 0.015), (max(piv[0], s * hw), yf + 0.0, zz + 0.015))
        part(hb, f"ОШ_петли_{side}", coll, [m["chrome"]], d, piv, piv, bevel=0.0008, smooth=50)
        lc.obj(kb, f"ОШ_петли_корпус_{side}", coll, [m["chrome"]], r, bevel=0.0008, smooth=50)
        # тяги: вертикальный пруток, направляющие, концы-ригели; на правой — рычаг от ручки
        rb = bmesh.new()
        bx = s * 0.33
        cyl(rb, (bx, yf + 0.014, dz0 + 0.015), (bx, yf + 0.014, dz1 - 0.015), 0.0045, segs=12)
        for z in (0.40, 0.90, 1.40):
            L.bm_box(rb, (bx - 0.012, yf + 0.003, z - 0.012), (bx + 0.012, yf + 0.020, z + 0.012))
        # ригели-концы выходят за кромку створки, входят между скобами корпуса
        cyl(rb, (bx, yf + 0.014, dz1 - 0.015), (bx, yf + 0.014, dz1 + 0.012), 0.0042, segs=10)
        cyl(rb, (bx, yf + 0.014, dz0 + 0.015), (bx, yf + 0.014, dz0 - 0.012), 0.0042, segs=10)
        part(rb, f"ОШ_тяги_{side}", coll, [m["steel_raw"]], d, piv, piv, bevel=0.0004, smooth=50)
    # ручка-замок на правой створке: накладка, личинка, поворотный рычаг; тяга — планка к прутку
    dR, pivR, x0, x1, s = doors["прав"]
    hp = (0.28, yf - 0.0015, 0.98)
    hb = bmesh.new()
    lc.rbox(hb, (0.05, 0.003, 0.17), 0.008, (hp[0], hp[1] - 0.0015, hp[2]), seg=3)
    part(hb, "ОШ_накладка_замка", coll, [m["steel_a"]], dR, pivR, pivR, bevel=0.0004, smooth=45)
    lv = bmesh.new()
    lc.lathe(lv, [(0.0, 0.0), (0.017, 0.0), (0.017, 0.004), (0.0145, 0.006), (0.0, 0.006)], segs=24, origin=(hp[0], hp[1] - 0.003, hp[2]), axis=(0, -1, 0))
    lc.rbox(lv, (0.11, 0.012, 0.024), 0.006, (hp[0] - 0.045, hp[1] - 0.012, hp[2]), seg=3)
    plug(lv, (hp[0] - 0.045 - 0.04, hp[1] - 0.018, hp[2]), depth=0.0015, r=0.0045, axis="-y")
    part(lv, "ОШ_ручка_замок", coll, [m["chrome"]], dR, pivR, (hp[0], hp[1] - 0.003, hp[2]), smooth=50, mover=True)
    lk = bmesh.new()
    L.bm_box(lk, (0.23, yf + 0.0, 0.95), (0.33, yf + 0.014, 1.00))
    part(lk, "ОШ_замок_тяга", coll, [m["steel_raw"]], dR, pivR, pivR, bevel=0.0005, smooth=45)
    if open_:
        _rz(doors["лев"][0], -100)
        _rz(doors["прав"][0], 85)
    return r


# ================================================================ картотечный шкаф

def file_cabinet(coll, m, at, open_: bool):
    """Картотечный шкаф на четыре ящика 460 × 1320 × 620: корпус из листа 1 мм на цоколе, телескопические
    направляющие (неподвижная, промежуточная, ящичная), ящики — лицевая панель-лоток с утопленной ручкой-скобой и
    рамкой под этикетку, коробка, рейки для подвесных папок; центральный замок вверху справа. Открыт: второй сверху
    выдвинут на 420 мм, в нём восемь подвесных папок."""
    r = L.root("КШ_шкаф_картотечный" + ("_открыт" if open_ else ""), coll, at)
    W, D, H = 0.46, 0.62, 1.32
    hw, yf = W / 2, -D / 2
    z0b = 0.03
    body = shell_part("КШ_корпус", coll, [m["steel_c"]], r, (W, D, H - z0b), 0.006, (0, 0, (H + z0b) / 2), "-y", 0.001, seg=2, flat=(1, 2, 5))
    pb = bmesh.new()
    lc.rbox(pb, (W - 0.02, D - 0.04, z0b - 0.01), 0.004, (0, 0.01, z0b / 2 + 0.005), seg=2)
    lc.obj(pb, "КШ_цоколь", coll, [m["steel_b"]], r, smooth=45)
    ft = bmesh.new()
    for x in (-hw + 0.03, hw - 0.03):
        for y in (yf + 0.04, -yf - 0.04):
            cyl(ft, (x, y, 0.0), (x, y, 0.011), 0.016, segs=18)
    lc.obj(ft, "КШ_ножки", coll, [m["rubber"]], r, smooth=50)
    pitch = (H - z0b - 0.012) / 4
    ph, pt = pitch - 0.0035, 0.0012
    pw = W - 0.016
    open_k = 2                     # второй сверху (снизу: 0…3)
    pull = 0.42
    names = ["нижний", "третий", "второй", "верхний"]
    for k in range(4):
        zk = z0b + 0.006 + k * pitch
        is_open = open_ and k == open_k
        off = -pull if is_open else 0.0
        dpiv = (0.0, yf, zk + ph / 2)
        wz0, wz1 = zk + ph - 0.060, zk + ph - 0.036
        wx0, wx1 = -0.07, 0.07
        fb = bmesh.new()
        tray_door(fb, -pw / 2, pw / 2, zk, zk + ph, yf, 0.032, pt, win=(wx0, wx1, wz0, wz1))
        # стакан ручки-скобы за окном
        L.bm_box(fb, (wx0, yf + pt, wz0 - pt), (wx1, yf + 0.030, wz0))
        L.bm_box(fb, (wx0, yf + 0.030 - pt, wz0), (wx1, yf + 0.030, wz1))
        L.bm_box(fb, (wx0, yf + pt, wz0), (wx0 + pt, yf + 0.030, wz1))
        L.bm_box(fb, (wx1 - pt, yf + pt, wz0), (wx1, yf + 0.030, wz1))
        # скоба — закруглённый валик на дне стакана
        L.bm_cyl(fb, (wx0 + 0.006, yf + 0.016, wz0 + 0.0035), (wx1 - 0.006, yf + 0.016, wz0 + 0.0035), 0.0035, segs=12)
        # рамка этикетки: приподнятый на 2 мм бортик 90 × 36 мм
        fx0, fx1, fz0, fz1 = -0.045, 0.045, zk + ph - 0.125, zk + ph - 0.089
        for (a0, b0, a1, b1) in ((fx0, fz0, fx1, fz0 + 0.003), (fx0, fz1 - 0.003, fx1, fz1), (fx0, fz0, fx0 + 0.003, fz1), (fx1 - 0.003, fz0, fx1, fz1)):
            L.bm_box(fb, (a0, yf - 0.002, b0), (a1, yf, b1))
        fr = part(fb, f"КШ_ящик_{names[k]}_лицо", coll, [m["steel_a"]], r, (0, 0, 0), dpiv, bevel=0.0004, segs=1, smooth=45, mover=True)
        # карточка в рамке — бумага чуть утоплена
        cb = bmesh.new()
        L.bm_box(cb, (fx0 + 0.003, yf + 0.0003, fz0 + 0.003), (fx1 - 0.003, yf + 0.0015, fz1 - 0.003))
        part(cb, f"КШ_ящик_{names[k]}_карточка", coll, [m["paper"]], fr, dpiv, dpiv, smooth=45)
        # коробка ящика (оболочка, открыта сверху), рамка для папок
        bw, bd, bh = 0.404, 0.540, 0.255
        by0 = yf + 0.030
        bbox = shell_part(f"КШ_ящик_{names[k]}_коробка", coll, [m["steel_c"]], fr, (bw, bd, bh), 0.004,
                          (0, by0 + bd / 2, zk + 0.012 + bh / 2), "+z", 0.0008, ppiv=dpiv, piv=dpiv, seg=2, flat=(1, 3, 1), bevel=0.0003)
        rl = bmesh.new()
        for s in (-1, 1):
            # рейки под подвесные папки: уголок по верхней кромке бортов (полка 12 мм внутрь)
            L.bm_box(rl, (s * (bw / 2 - 0.0008) - (0.012 if s > 0 else 0), by0 + 0.01, zk + 0.012 + bh - 0.008),
                     (s * (bw / 2 - 0.0008) + (0 if s > 0 else 0.012), by0 + bd - 0.01, zk + 0.012 + bh - 0.0065))
            L.bm_box(rl, (s * (bw / 2 - 0.0008) - (0.0014 if s > 0 else 0), by0 + 0.01, zk + 0.012 + bh - 0.022),
                     (s * (bw / 2 - 0.0008) + (0 if s > 0 else 0.0014), by0 + bd - 0.01, zk + 0.012 + bh - 0.0065))
        part(rl, f"КШ_ящик_{names[k]}_рейки", coll, [m["steel_a"]], fr, dpiv, dpiv, bevel=0.0003, segs=1, smooth=45)
        # направляющие: ящичная (на ящике), промежуточная и неподвижная (на корпусе) — по обе стороны на середине высоты
        zr = zk + 0.012 + 0.09
        rr = bmesh.new()
        rm = bmesh.new()
        rf = bmesh.new()
        ln = 0.50
        for s in (-1, 1):
            def xr(a, b):
                return (min(s * a, s * b), max(s * a, s * b))
            xa, xb = xr(bw / 2, bw / 2 + 0.0055)
            L.bm_box(rr, (xa, by0 + 0.02, zr - 0.011), (xb, by0 + 0.02 + ln, zr + 0.011))
            xa, xb = xr(bw / 2 + 0.0055, bw / 2 + 0.011)
            L.bm_box(rm, (xa, by0 + 0.015 + off / 2, zr - 0.011), (xb, by0 + 0.015 + off / 2 + ln, zr + 0.011))
            xa, xb = xr(bw / 2 + 0.011, bw / 2 + 0.0165)
            L.bm_box(rf, (xa, by0 + 0.01, zr - 0.011), (xb, by0 + 0.01 + ln + 0.02, zr + 0.011))
        part(rr, f"КШ_ящик_{names[k]}_направляющая", coll, [m["steel_raw"]], fr, dpiv, dpiv, bevel=0.0004, segs=1, smooth=45)
        lc.obj(rm, f"КШ_направляющая_пром_{names[k]}", coll, [m["steel_raw"]], r, bevel=0.0004, segs=1, smooth=45)
        lc.obj(rf, f"КШ_направляющая_корп_{names[k]}", coll, [m["steel_raw"]], r, bevel=0.0004, segs=1, smooth=45)
        if is_open:
            _fold_files(coll, m, fr, dpiv, by0, bd, bw, zk + 0.012, bh)
        if is_open:
            fr.location = V(dpiv) + V((0, off, 0))
    # центральный замок: накладка и личинка на верхнем ящике справа
    lb = bmesh.new()
    ztop = z0b + 0.006 + 3 * pitch
    lcx, lcz = pw / 2 - 0.04, ztop + ph - 0.03
    lc.rbox(lb, (0.036, 0.003, 0.036), 0.007, (lcx, yf - 0.0015, lcz), seg=3)
    L.bm_cyl(lb, (lcx, yf - 0.003, lcz), (lcx, yf - 0.0065, lcz), 0.011, segs=20)
    plug(lb, (lcx, yf - 0.0065, lcz), depth=0.0015, r=0.0062, axis="-y")
    top_fr = [o for o in coll.objects if o.name.startswith("КШ_ящик_верхний_лицо")][0]
    dp3 = V((0, yf, ztop + ph / 2))
    part(lb, "КШ_замок_центральный", coll, [m["chrome"]], top_fr, dp3, dp3, bevel=0.0004, smooth=50)
    return r


def _fold_files(coll, m, parent, dpiv, by0, bd, bw, zfloor, bh):
    """Подвесные папки в выдвинутом ящике: прутки на рейках, две стенки (V) и пластиковый ярлычок; наклонены, стоят густо."""
    fb = bmesh.new()
    pb = bmesh.new()
    tb = bmesh.new()
    n = 8
    ztop = zfloor + bh - 0.008
    for i in range(n):
        y = by0 + 0.06 + i * 0.048 + (0.012 if i > 4 else 0.0)
        lean = math.radians(3.0 + (1.5 if i > 4 else 0))   # правые упали на соседей чуть сильнее
        bwid = bw - 0.03
        zb = zfloor + 0.012
        h = ztop - zb
        # стенки V: от прутка вниз, внизу сходятся
        for sg, dy in ((-1, -0.007), (1, 0.007)):
            pts = [(-bwid / 2, y + dy, ztop - 0.004), (bwid / 2, y + dy, ztop - 0.004),
                   (bwid / 2, y + dy * 0.2, zb + 0.004), (-bwid / 2, y + dy * 0.2, zb + 0.004)]
            hh = h if sg > 0 else h - 0.018      # передняя стенка ниже верха — виден ярлык
            vs = [fb.verts.new((p[0], p[1] + (z - ztop) * 0 , p[2] if sg > 0 else p[2] - (0.018 if p[2] > zb + 0.1 else 0))) for z, p in enumerate(pts)]
            fb.faces.new(vs)
            vs2 = [fb.verts.new((p[0], p[1] + 0.0012 * sg, p[2] if sg > 0 else p[2] - (0.018 if p[2] > zb + 0.1 else 0))) for p in pts]
            fb.faces.new(vs2[::-1])
            for k in range(4):
                fb.faces.new((vs[k], vs[(k + 1) % 4], vs2[(k + 1) % 4], vs2[k]))
        L.bm_cyl(pb, (-bw / 2 + 0.005, y, ztop), (bw / 2 - 0.005, y, ztop), 0.0022, segs=10)
        L.bm_cyl(pb, (-bwid / 2, y, zb + 0.002), (bwid / 2, y, zb + 0.002), 0.0032, segs=10)
        # ярлычок
        L.bm_box(tb, (-0.02 + (i % 4 - 1.5) * 0.07, y - 0.0075, ztop - 0.026), (0.02 + (i % 4 - 1.5) * 0.07, y - 0.0055, ztop - 0.002))
    # наклон: всё стопкой повернуть чуть вокруг оси X нельзя (папки отдельны) — оставляем вертикальными
    part(fb, "КШ_папки_листы", coll, [m["folder"]], parent, dpiv, dpiv, smooth=45)
    part(pb, "КШ_папки_прутки", coll, [m["steel_raw"]], parent, dpiv, dpiv, smooth=50)
    part(tb, "КШ_папки_ярлыки", coll, [m["plastic_white"]], parent, dpiv, dpiv, smooth=45)
