"""Следы использования из данных игры, шаг 3: маски по каждому текселю high-poly (без кисти и без декалей на глаз).

Источники — то, что игра уже знает об оружии:
  * клипы рук (clip_contacts.py): где перчатка касается детали — в осях этой детали, поэтому магазин в руке и рама
    в отводе получают след на своих местах. Ногтевые фаланги (подушечки) → hand_prints, остальные фаланги слабее —
    только если палец лёг и не поехал; проехавший палец и ладонь → hand_palms (растёртый жир). Жир переносится при
    каждом новом касании и понемногу, пока держат. Скольжение перчатки по детали (мм пути в касании, по касательной)
    → hand_rub (заполировано). Касания считаются на выборке текселей и растекаются на остальные гауссовым средним. Стойка — первый кадр тактической
    перезарядки (так её берёт игра), её вес — сколько держат и сколько раз берут в руки за «цикл пользования»;
    веса клипов — как часто их делают (конфиг).
  * магазин (кости Magazine / SpareMag в клипах): его путь в шахту и из неё, повторённый с разбросом захода
    (наклон и сдвиг, к посадке сходят на нет) → mag_rub на горловине шахты и на самом магазине.
  * планки обвесов (сокеты data/weapons.json): где на планке стоит опора обвеса (по пазам вокруг сокета и где угодно)
    × какой гранью планка её держит: косые грани «ласточкина хвоста» под прижимом, верх зубьев (опору двигают),
    стенки пазов, обращённые назад (упор поперечины при отдаче) → mount_wear.
  * ремень: антабки и гнёзда QD — внутри отверстия и край вокруг; лента 25 мм, выходящая из антабки по многим
    направлениям (от оружия, к другой точке ремня, вниз), — где она ложится на соседние поверхности → sling_wear.
Значения копятся в физических единицах (касания, секунды, мм скольжения) и сжимаются логарифмом к 0…1 одним
масштабом на все наборы текстур — маски разных наборов сопоставимы.

python -X utf8 tools/wear_from_use/wear_masks.py <конфиг.json> <папка данных> <папка масок> [hand,mag,mount,sling]
  папка данных: texels_<набор>.npz, objects.json (hp_texels.py), clips/<клип>.npz (clip_contacts.py)
  → <набор>_<маска>.png (16 бит, развёртка WearUV копии), сырые суммы raw_<набор>.npz, masks.json.
  Можно пересчитать часть: сырые суммы остальных каналов берутся из прошлого raw_<набор>.npz.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from scipy.spatial import cKDTree

CFG = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
DATA = Path(sys.argv[2])
OUT = Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
ONLY = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else {"hand", "mag", "mount", "sling"}
MM = 0.001
CELL = 0.004
NB = np.array([(i, j, k) for i in (-1, 0, 1) for j in (-1, 0, 1) for k in (-1, 0, 1)], np.int64)
CHANNELS = ("hand_prints", "hand_palms", "hand_rub", "mag_rub", "mount_wear", "sling_wear")
OF = {"hand": ("hand_prints", "hand_palms", "hand_rub"), "mag": ("mag_rub",), "mount": ("mount_wear",), "sling": ("sling_wear",)}
# перенос жира: новое касание — 1; пока держат — в секунду (подушечки / ладонь)
PRINT_PER_S, PALM_PER_S = 0.05, 0.10
STILL_MM = 3.0          # палец проехал за кадр больше — отпечатка нет, только мазок
SMEAR_PER_MM = 0.04     # мазок от проехавшего пальца — на мм пути
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:6.1f} с]", *a, flush=True)


# ------------------------------------------------------------------ тексели
OBJ = {int(k): v for k, v in json.loads((DATA / "objects.json").read_text(encoding="utf-8")).items()}
SETS = {}
for s in CFG["sets"]:
    d = np.load(DATA / f"texels_{s}.npz")
    t = {k: d[k] for k in d.files}
    ids = np.arange(t["obj"].max() + 1)
    t["bone"] = np.array([OBJ.get(int(i), {}).get("bone", "") for i in ids])[t["obj"]]
    t["name"] = np.array([OBJ.get(int(i), {}).get("name", "") for i in ids])[t["obj"]]
    t["acc"] = {c: np.zeros(len(t["pos"]), np.float64) for c in CHANNELS}
    raw = OUT / f"raw_{s}.npz"
    if raw.exists():
        old = np.load(raw)
        for c in CHANNELS:
            if c in old.files and len(old[c]) == len(t["pos"]) and not any(c in OF.get(k, ()) for k in ONLY):
                t["acc"][c] = old[c].astype(np.float64)
    SETS[s] = t
    log("тексели", s, len(t["pos"]))


class Group:
    """Тексели одного набора на одной кости: координаты в осях покоя кости и сеточный индекс для отбора по близости."""

    def __init__(self, s, bone, keep=None):
        t = SETS[s]
        self.set, self.bone = s, bone
        self.idx = np.nonzero((t["bone"] == bone) & (True if keep is None else keep))[0]
        self.pos = t["pos"][self.idx].astype(np.float64)
        self.nrm = t["nrm"][self.idx].astype(np.float64)
        self.lo = self.pos.min(axis=0) - 0.02
        self.hi = self.pos.max(axis=0) + 0.02
        self.dims = np.ceil((self.hi - self.lo) / CELL).astype(np.int64) + 1
        c = np.floor((self.pos - self.lo) / CELL).astype(np.int64)
        key = c[:, 0] + self.dims[0] * (c[:, 1] + self.dims[1] * c[:, 2])
        self.order = np.argsort(key, kind="stable")
        self.keys, self.start, self.count = np.unique(key[self.order], return_index=True, return_counts=True)
        self.nbk = NB[:, 0] + self.dims[0] * (NB[:, 1] + self.dims[1] * NB[:, 2])

    def near(self, pts):
        """Номера (в группе) текселей в клетках вокруг точек pts (оси кости). Клетки — одномерным ключом; соседи
        у края сетки «заворачиваются» в чужую клетку, но сетка с запасом 2 см — это лишь лишние кандидаты."""
        inside = np.all((pts > self.lo) & (pts < self.hi), axis=1)
        if not inside.any():
            return np.zeros(0, np.int64)
        c = np.floor((pts[inside] - self.lo) / CELL).astype(np.int64)
        k = np.unique(c[:, 0] + self.dims[0] * (c[:, 1] + self.dims[1] * c[:, 2]))
        k = np.unique((k[:, None] + self.nbk[None]).ravel())
        j = np.searchsorted(self.keys, k)
        ok = j < len(self.keys)
        j, k = j[ok], k[ok]
        j = j[self.keys[j] == k]
        if not len(j):
            return np.zeros(0, np.int64)
        st, ct = self.start[j], self.count[j]
        rep = np.repeat(st - np.concatenate(([0], np.cumsum(ct)[:-1])), ct)
        return self.order[np.arange(ct.sum()) + rep]


GROUPS = {}
for s, t in SETS.items():
    for b in np.unique(t["bone"]):
        if b:
            GROUPS[(s, b)] = Group(s, b)
# касания кистей считаются на выборке текселей (доля hand_texels) и переносятся на остальные по ближайшему в 3D:
# пятно касания плавное на миллиметрах, а тексели стали — 0,36 мм
HAND_GROUPS = {}
if "hand" in ONLY:
    _rng = np.random.default_rng(3)
    for (s, b) in GROUPS:
        HAND_GROUPS[(s, b)] = Group(s, b, _rng.random(len(SETS[s]["pos"])) < CFG["contact"].get("hand_texels", 0.3))


def to_local(p, m):
    """Точки в осях покоя коробки → оси покоя кости (m: покой кости → покой коробки, жёсткая)."""
    return (p - m[:3, 3]) @ m[:3, :3]


def to_root(p, m):
    return p @ m[:3, :3].T + m[:3, 3]


def smooth_w(dist, r_in, r_out):
    x = np.clip((r_out - dist) / max(r_out - r_in, 1e-9), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def orthonormal(m):
    u, _, vt = np.linalg.svd(m[:3, :3])
    out = m.copy()
    out[:3, :3] = u @ vt
    return out


def tangential(d, n):
    return d - np.einsum("ij,ij->i", d, n)[:, None] * n


def spread(src_pos, vals, dst_pos, radius=0.002, sigma=0.0008, k=12):
    """Значения с точек выборки на все тексели: гауссово среднее k ближайших в пределах radius (сглаживает и шаг
    выборки, и ступеньки шагов движения)."""
    d, j = cKDTree(src_pos).query(dst_pos, k=k, distance_upper_bound=radius, workers=-1)
    ok = np.isfinite(d)
    w = np.where(ok, np.exp(-0.5 * (np.where(ok, d, 0) / sigma) ** 2), 0.0)
    j = np.where(ok, j, 0)
    ws = w.sum(axis=1)
    out = []
    for v in vals:
        out.append(np.where(ws > 1e-9, (w * v[j]).sum(axis=1) / np.maximum(ws, 1e-9), 0.0))
    return out, ws > 1e-9


# ------------------------------------------------------------------ кисти
CC = CFG["contact"]
R_IN, R_OUT, R_DEEP = CC["r_in_mm"] * MM, CC["r_out_mm"] * MM, CC["inside_max_mm"] * MM


def load_clip(name):
    d = np.load(DATA / "clips" / f"{name}.npz")
    return {k: d[k] for k in d.files}


class HandSampler:
    """Точки на поверхности перчаток: барицентрические точки треугольников с шагом sample_mm (по первому кадру)."""

    def __init__(self, clip):
        tris = clip["tris"]
        v = clip["hand"][0].astype(np.float64)
        a = 0.5 * np.linalg.norm(np.cross(v[tris[:, 1]] - v[tris[:, 0]], v[tris[:, 2]] - v[tris[:, 0]]), axis=1)
        k = np.maximum(1, np.ceil(a / (CC["sample_mm"] * MM) ** 2)).astype(np.int64)
        rng = np.random.default_rng(7)
        self.tri = np.repeat(np.arange(len(tris)), k)
        r1, r2 = rng.random(len(self.tri)), rng.random(len(self.tri))
        s1 = np.sqrt(r1)
        self.bary = np.stack([1 - s1, s1 * (1 - r2), s1 * r2], axis=1)
        self.tris = tris
        self.vt = tris[self.tri]
        self.region = np.median(clip["region"][tris], axis=1).astype(np.int8)[self.tri]
        self.side = clip["side"][tris[:, 0]][self.tri]
        self.flip = 1.0
        log("точек на перчатках", len(self.tri))

    def points(self, v):
        p = v[self.vt[:, 0]] * self.bary[:, :1] + v[self.vt[:, 1]] * self.bary[:, 1:2] + v[self.vt[:, 2]] * self.bary[:, 2:]
        tv = v[self.tris]
        n = np.cross(tv[:, 1] - tv[:, 0], tv[:, 2] - tv[:, 0])
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        return p, n[self.tri] * self.flip


CLIPS = {name: load_clip(name) for name in list(CFG["clips"]) + [CFG["hold"]["clip"]]}
HS = HandSampler(CLIPS[CFG["hold"]["clip"]])
# отпечаток — подушечки (ногтевые фаланги) полностью, остальные фаланги слабее; ладонь — свой канал
PRINT_W = np.where(HS.region == 3, 1.0, np.where(HS.region == 2, 0.45, 0.0))
PALM_W = np.where(HS.region == 1, 1.0, np.where(HS.region == 2, 0.25, 0.0))


def interp_frames(clip):
    """Кадры с промежуточными шагами там, где кисть или деталь за кадр сдвигается больше substep_mm.
    → [(вершины кистей, матрицы костей, доля кадра)]"""
    hand = clip["hand"].astype(np.float64)
    mats = clip["mats"].astype(np.float64)
    out = []
    for f in range(len(hand)):
        n = 1
        if f + 1 < len(hand):
            mv = np.abs(hand[f + 1] - hand[f]).max()
            mm = np.abs(mats[f + 1][:, :3, 3] - mats[f][:, :3, 3]).max()
            n = int(min(8, max(1, np.ceil(max(mv, mm) / (CC["substep_mm"] * MM)))))
        out.append((hand[f], mats[f], 1.0 / n))
        for i in range(1, n):
            a = i / n
            m = np.stack([orthonormal(x) for x in mats[f] * (1 - a) + mats[f + 1] * a])
            out.append((hand[f] * (1 - a) + hand[f + 1] * a, m, 1.0 / n))
    return out


def hand_frame(pts, nrm, mats, bones):
    """Касания одного (промежуточного) кадра: {(набор, кость): (тексели группы, вес, номер точки перчатки)}."""
    tree = cKDTree(pts)
    lo, hi = pts.min(axis=0) - R_DEEP, pts.max(axis=0) + R_DEEP
    res = {}
    for (s, b), g in HAND_GROUPS.items():
        if b not in bones:
            continue
        mb = mats[bones.index(b)]
        corners = np.array([[x, y, z] for x in (g.lo[0], g.hi[0]) for y in (g.lo[1], g.hi[1]) for z in (g.lo[2], g.hi[2])])
        cr = to_root(corners, mb)
        if np.any(cr.max(axis=0) < lo) or np.any(cr.min(axis=0) > hi):
            continue
        cand = g.near(to_local(pts, mb))
        if not len(cand):
            continue
        x = to_root(g.pos[cand], mb)
        xn = g.nrm[cand] @ mb[:3, :3].T
        dist, j = tree.query(x, distance_upper_bound=R_DEEP, workers=-1)
        ok = np.isfinite(dist)
        if not ok.any():
            continue
        cand, x, xn, dist, j = cand[ok], x[ok], xn[ok], dist[ok], j[ok]
        sd = np.einsum("ij,ij->i", x - pts[j], nrm[j])
        facing = np.einsum("ij,ij->i", xn, nrm[j])
        # перчатка вдавлена в деталь (точка детали внутри кисти) — касание; снаружи — по расстоянию;
        # поверхности должны смотреть друг на друга (иначе это обратная сторона тонкой детали)
        w = np.where(sd < 0, 1.0, smooth_w(dist, R_IN, R_OUT))
        w *= np.clip((0.35 - facing) / 0.5, 0.0, 1.0)
        keep = w > 1e-3
        if keep.any():
            res[(s, b)] = (cand[keep], w[keep], j[keep])
    return res


def orient_normals():
    """Нормали перчатки должны смотреть наружу: у текселей рядом с кистью вектор от кисти к текселю — по нормали."""
    clip = CLIPS[CFG["hold"]["clip"]]
    pts, nrm = HS.points(clip["hand"][CFG["hold"]["frame"]].astype(np.float64))
    tree = cKDTree(pts)
    sgn = []
    for g in HAND_GROUPS.values():
        cand = g.near(pts)
        if not len(cand):
            continue
        dist, j = tree.query(g.pos[cand], distance_upper_bound=0.004)
        ok = np.isfinite(dist) & (dist > 0.0015)
        sgn.append(np.sign(np.einsum("ij,ij->i", g.pos[cand][ok] - pts[j[ok]], nrm[j[ok]])))
    sgn = np.concatenate(sgn)
    if sgn.mean() < 0:
        HS.flip = -1.0
    log("нормали перчатки:", "наружу" if HS.flip > 0 else "перевёрнуты", f"(среднее {sgn.mean():+.2f} по {len(sgn)})")


def accumulate_hands():
    hold = CFG["hold"]
    clip = CLIPS[hold["clip"]]
    bones = list(clip["bones"])
    pts, nrm = HS.points(clip["hand"][hold["frame"]].astype(np.float64))
    res = hand_frame(pts, nrm, clip["mats"][hold["frame"]].astype(np.float64), bones)
    hold_state = {s: np.zeros(len(SETS[s]["pos"]), bool) for s in SETS}
    for (s, b), (cand, w, j) in res.items():
        a = SETS[s]["acc"]
        idx = HAND_GROUPS[(s, b)].idx[cand]
        np.add.at(a["hand_prints"], idx, w * PRINT_W[j] * (hold["grabs"] + hold["dwell_s"] * PRINT_PER_S))
        np.add.at(a["hand_palms"], idx, w * PALM_W[j] * (hold["grabs"] + hold["dwell_s"] * PALM_PER_S))
        np.add.at(a["hand_rub"], idx, w * hold["slip_mm"])
        hold_state[s][idx[w > 0.15]] = True
    log("стойка:", {s: int(v.sum()) for s, v in hold_state.items()}, "текселей в касании")
    for name, cw in CFG["clips"].items():
        clip = CLIPS[name]
        bones = list(clip["bones"])
        sec = 1.0 / float(clip["fps"])
        steps = interp_frames(clip)
        prev = {s: v.copy() for s, v in hold_state.items()}
        pts, nrm = HS.points(steps[0][0])
        n_on = 0
        for si, (v, m, dt) in enumerate(steps):
            nxt, nxt_n = HS.points(steps[si + 1][0]) if si + 1 < len(steps) else (None, None)
            res = hand_frame(pts, nrm, m, bones)
            cur = {s: np.zeros(len(SETS[s]["pos"]), bool) for s in SETS}
            for (s, b), (cand, w, j) in res.items():
                a = SETS[s]["acc"]
                g = HAND_GROUPS[(s, b)]
                idx = g.idx[cand]
                slide = np.zeros(len(cand))
                if nxt is not None:
                    # скольжение: путь той же точки перчатки к следующему шагу в осях детали, по касательной к текселю
                    bi = bones.index(b)
                    dq = to_local(nxt[j], steps[si + 1][1][bi]) - to_local(pts[j], m[bi])
                    slide = np.linalg.norm(tangential(dq, g.nrm[cand]), axis=1) / MM
                    np.add.at(a["hand_rub"], idx, cw * w * slide)
                # отпечаток остаётся, если палец лёг и не поехал (скорость — мм за шаг в долях кадра)
                still = np.clip(1.0 - slide / max(dt, 1e-3) / STILL_MM, 0.0, 1.0)
                # новое касание — уверенное там, где на прошлом шаге не было даже слабого (без дребезга на подшагах)
                on = ((w > 0.5) & ~prev[s][idx]).astype(np.float64)
                n_on += int(on.sum())
                np.add.at(a["hand_prints"], idx, cw * PRINT_W[j] * still * (on + w * dt * sec * PRINT_PER_S))
                # ладонь и проехавший палец — растёртый жир (мазок)
                np.add.at(a["hand_palms"], idx, cw * (PALM_W[j] * (on + w * dt * sec * PALM_PER_S)
                                                      + PRINT_W[j] * w * slide * SMEAR_PER_MM))
                cur[s][idx[w > 0.15]] = True
            prev = cur
            if nxt is not None:
                pts, nrm = nxt, nxt_n
        log(f"клип {name}: {len(steps)} шагов, новых касаний (текселей выборки) {n_on}")
    # с выборки — на все тексели детали той же кости: гауссово среднее соседей выборки в пределах 2 мм
    for (s, b), g in GROUPS.items():
        hg = HAND_GROUPS[(s, b)]
        if not len(hg.idx):
            continue
        accs = [SETS[s]["acc"][c] for c in OF["hand"]]
        vals, ok = spread(hg.pos, [a[hg.idx] for a in accs], g.pos)
        for a, v in zip(accs, vals):
            a[g.idx[ok]] = v[ok]
    log("касания перенесены с выборки на все тексели")


# ------------------------------------------------------------------ магазин в шахте
def accumulate_magazine():
    """Касание считается на выборке точек (магазин ~90 тыс., горловина ~120 тыс.) с неподвижными деревьями в осях
    каждой стороны, затем растекается на все тексели по ближайшей точке выборки."""
    mc = CFG["magazine"]
    rng = np.random.default_rng(11)
    mag = [g for (s, b), g in GROUPS.items() if b == "Magazine"]
    mag_pos = np.concatenate([g.pos for g in mag])
    mag_nrm = np.concatenate([g.nrm for g in mag])
    ms = rng.choice(len(mag_pos), min(len(mag_pos), 90000), replace=False)
    mp, mn = mag_pos[ms], mag_nrm[ms]
    top = mp[:, 2].max()
    zlo = np.array([mp[:, 0].min(), mp[:, 1].min(), top - 0.10]) - mc["zone_mm"] * MM
    zhi = np.array([mp[:, 0].max(), mp[:, 1].max(), top]) + mc["zone_mm"] * MM
    zone = []
    for (s, b), g in GROUPS.items():
        if b != "WeaponRoot":
            continue
        k = np.nonzero(np.all((g.pos > zlo) & (g.pos < zhi), axis=1))[0]
        if len(k):
            zone.append((g, k))
    zpos = np.concatenate([g.pos[k] for g, k in zone])
    znrm = np.concatenate([g.nrm[k] for g, k in zone])
    zs = rng.choice(len(zpos), min(len(zpos), 120000), replace=False)
    rp, rn = zpos[zs], znrm[zs]
    tree_r = cKDTree(rp)               # горловина, оси коробки
    tree_m = cKDTree(mp)               # магазин, оси магазина
    acc_r = np.zeros(len(rp))
    acc_m = np.zeros(len(mp))
    pivot = np.array([mp[:, 0].mean(), 0.0, top])
    jit = [(np.array([1.0, 0, 0]), 0.0, np.zeros(3))]          # путь клипа как есть
    for _ in range(mc["jitter"]):
        ax = rng.normal(size=3)
        ax /= np.linalg.norm(ax)
        jit.append((ax, np.radians(rng.normal(0, mc["jitter_deg"])),
                    np.array([rng.normal(0, mc["jitter_mm"]), rng.normal(0, mc["jitter_mm"]), 0.0]) * MM))
    r_c = mc["contact_mm"] * MM

    def pose(m, j, amp):
        ax, ang, tr = j
        c, s_ = np.cos(ang * amp), np.sin(ang * amp)
        kx = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
        r = np.eye(3) + s_ * kx + (1 - c) * kx @ kx
        t = np.eye(4)
        t[:3, :3] = r
        t[:3, 3] = pivot - r @ pivot + tr * amp
        return t @ m

    def step(m0, m1, cw):
        # горловина ← магазин: точки горловины в осях магазина, ближайшая точка магазина
        q0 = to_local(rp, m0)
        q1 = to_local(rp, m1)
        d, j = tree_m.query(q0, distance_upper_bound=0.006, workers=-1)
        ok = np.isfinite(d)
        if ok.any():
            sd = np.einsum("ij,ij->i", q0[ok] - mp[j[ok]], mn[j[ok]])
            w = np.where(sd < 0, 1.0, smooth_w(d[ok], 0.0, r_c))
            dd = tangential(to_root(q1[ok], m0) - rp[ok], rn[ok])      # сдвиг горловины относительно магазина
            acc_r[np.nonzero(ok)[0]] += cw * w * np.linalg.norm(dd, axis=1) / MM
        # магазин ← горловина: точки магазина в осях коробки, ближайшая точка горловины
        s0 = to_root(mp, m0)
        s1 = to_root(mp, m1)
        d, j = tree_r.query(s0, distance_upper_bound=0.006, workers=-1)
        ok = np.isfinite(d)
        if ok.any():
            sd = np.einsum("ij,ij->i", s0[ok] - rp[j[ok]], rn[j[ok]])
            w = np.where(sd < 0, 1.0, smooth_w(d[ok], 0.0, r_c))
            dd = tangential(s1[ok] - s0[ok], mn[ok] @ m0[:3, :3].T)
            acc_m[np.nonzero(ok)[0]] += cw * w * np.linalg.norm(dd, axis=1) / MM

    for name, cw in CFG["clips"].items():
        clip = CLIPS[name]
        bones = list(clip["bones"])
        mats = clip["mats"].astype(np.float64)
        for bn in mc["bones"]:
            if bn not in bones:
                continue
            bi = bones.index(bn)
            disp = np.array([np.abs(to_root(mp[::50], m[bi]) - mp[::50]).max() for m in mats])
            if disp.min() > 0.002:
                log(f"  {name}/{bn}: в шахте не бывает (мин. сдвиг {disp.min() * 1000:.0f} мм)")
                continue
            near = disp < 0.07
            steps = 0
            for jt in jit:
                for f in range(1, len(mats)):
                    if not (near[f] or near[f - 1]):
                        continue
                    a0 = float(np.clip(disp[f - 1] / (mc["free_mm"] * MM), 0, 1))
                    a1 = float(np.clip(disp[f] / (mc["free_mm"] * MM), 0, 1))
                    p0, p1 = pose(mats[f - 1, bi], jt, a0), pose(mats[f, bi], jt, a1)
                    move = np.abs(to_root(mp[::50], p1) - to_root(mp[::50], p0)).max()
                    if move < 1e-6:
                        continue
                    # заход в клипе — несколько кадров, за кадр магазин проходит сантиметры: шаг не длиннее 1 мм
                    n = int(np.clip(np.ceil(move / 0.001), 1, 120))
                    for sub in range(n):
                        m0 = orthonormal(p0 * (1 - sub / n) + p1 * (sub / n))
                        m1 = orthonormal(p0 * (1 - (sub + 1) / n) + p1 * ((sub + 1) / n))
                        step(m0, m1, cw / len(jit))
                        steps += 1
            log(f"  {name}/{bn}: кадров у шахты {int(near.sum())}, шагов движения {steps}")
    # с выборки — на все тексели: гауссово среднее соседей выборки (точки выборки реже текселей)
    for g, k in zone:
        (v,), ok = spread(rp, [acc_r], g.pos[k], radius=0.003, sigma=0.0012)
        SETS[g.set]["acc"]["mag_rub"][g.idx[k[ok]]] += v[ok]
    for g in mag:
        (v,), ok = spread(mp, [acc_m], g.pos, radius=0.003, sigma=0.0012)
        SETS[g.set]["acc"]["mag_rub"][g.idx[ok]] += v[ok]
    log(f"магазин: горловина {int((acc_r > 0).sum())} / {len(rp)} точек, магазин {int((acc_m > 0).sum())} / {len(mp)}")


# ------------------------------------------------------------------ планки и обвесы
def accumulate_mounts():
    for rail in CFG["rails"]:
        out = np.array(rail["out"], float)
        ax = np.array([1.0, 0.0, 0.0])
        side = np.cross(out, ax)
        hits = []
        for s, t in SETS.items():
            sel = np.zeros(len(t["pos"]), bool)
            for o in rail["objects"]:
                sel |= np.char.startswith(t["name"], o)
            k = np.nonzero(sel)[0]
            if len(k):
                hits.append((s, k))
        if not hits:
            log("планка без деталей:", rail["name"])
            continue
        allp = np.concatenate([SETS[s]["pos"][k] for s, k in hits]).astype(np.float64)
        h_top = np.percentile(allp @ out, 99.5)
        x0, x1 = allp[:, 0].min(), allp[:, 0].max()
        # где стоит опора обвеса: по пазам вокруг сокета (норм. распределение) и где угодно (равномерно) — свёртка с её длиной
        xs = np.linspace(x0, x1, 512)
        dens = 0.6 * np.exp(-0.5 * ((xs - rail["socket_x"]) / rail["spread_m"]) ** 2) / (rail["spread_m"] * 2.5066)
        dens += 0.4 / max(x1 - x0, 1e-3)
        cover = np.array([dens[np.abs(xs - x) < rail["foot_m"] / 2].sum() for x in xs])
        cover /= cover.max()
        for s, k in hits:
            t = SETS[s]
            p, n = t["pos"][k].astype(np.float64), t["nrm"][k].astype(np.float64)
            h = p @ out
            nu, nb, na = n @ out, np.abs(n @ side), n @ ax
            f = np.full(len(k), 0.03)
            f[(nu > 0.85) & (h > h_top - 0.0008)] = 0.45                     # верх зубьев: опору двигают по планке
            f[(nu > 0.35) & (nu <= 0.85) & (nb > 0.35)] = 0.7                # верхние фаски
            f[(nu > -0.9) & (nu < 0.05) & (nb > 0.35)] = 1.0                 # косые грани под прижимом
            vert = (np.abs(nu) < 0.3) & (nb > 0.9)
            f[vert] = np.maximum(f[vert], 0.5)
            wall = (np.abs(na) > 0.75) & (h > h_top - 0.0035)
            f[wall & (na < 0)] = 0.9                                         # стенка паза, обращённая назад: упор поперечины
            f[wall & (na > 0)] = 0.35
            t["acc"]["mount_wear"][k] += rail["weight"] * f * np.interp(p[:, 0], xs, cover)
        log(f"планка {rail['name']}: {sum(len(k) for _, k in hits)} текселей, x {x0:.3f}…{x1:.3f}, верх {h_top * 1000:.1f} мм")


# ------------------------------------------------------------------ ремень и антабки
def accumulate_sling():
    st = CFG["strap"]
    sets = list(SETS)
    allp = np.concatenate([SETS[s]["pos"] for s in sets]).astype(np.float64)
    alln = np.concatenate([SETS[s]["nrm"] for s in sets]).astype(np.float64)
    owner = np.concatenate([np.full(len(SETS[s]["pos"]), i) for i, s in enumerate(sets)])
    names = np.concatenate([SETS[s]["name"] for s in sets])
    tree = cKDTree(allp)
    acc = np.zeros(len(allp))
    gold = np.pi * (3 - np.sqrt(5))
    i = np.arange(st["dirs"])
    zz = 1 - 2 * (i + 0.5) / st["dirs"]
    rr = np.sqrt(1 - zz * zz)
    dirs = np.stack([rr * np.cos(gold * i), rr * np.sin(gold * i), zz], axis=1)
    s_ = np.arange(3.0, st["length_mm"], 1.5) * MM
    uu = np.arange(-st["width_mm"] / 2, st["width_mm"] / 2 + 0.1, 2.5) * MM
    fall = np.repeat(1.0 / (1.0 + s_ / (st["falloff_mm"] * MM)), len(uu))
    for sp in CFG["sling"]:
        k = np.nonzero(names == sp["object"])[0]
        kp = np.nonzero(names == sp["partner"])[0]
        if not len(k) or not len(kp):
            log("нет точки ремня:", sp["object"], sp["partner"])
            continue
        p, n = allp[k], alln[k]
        c = p.mean(axis=0)
        _, _, vt = np.linalg.svd(p - c, full_matrices=False)
        hole = vt[2]                                   # ось отверстия — направление наименьшего разброса точек
        partner = allp[kp].mean(axis=0)
        outward = c.copy()
        outward[0] = 0.0
        outward /= max(np.linalg.norm(outward), 1e-9)
        # сама антабка: изнутри отверстия (нормаль к оси) и край вокруг — крючок / вертлюг трётся при каждом движении
        rad = (p - c) - np.outer((p - c) @ hole, hole)
        rlen = np.linalg.norm(rad, axis=1)
        inner = -np.einsum("ij,ij->i", n, rad / np.maximum(rlen[:, None], 1e-9))
        rim = np.clip(np.abs(n @ hole) - 0.6, 0, 1) * np.exp(-rlen / (0.6 * rlen.max() + 1e-9))
        acc[k] += sp["weight"] * (0.25 + np.clip(inner, 0, 1) + 0.8 * rim) * 3.0
        # лента: из антабки по направлениям, где она бывает (от оружия, к другой точке ремня, вниз)
        to_p = (partner - c) / np.linalg.norm(partner - c)
        wd = np.clip(dirs @ outward + 0.35, 0, None) * (1 + 2.0 * np.clip(dirs @ to_p, 0, None)) * (1 + 0.8 * np.clip(-dirs[:, 2], 0, None))
        hit_j, hit_w = [], []
        for d, w in zip(dirs, wd):
            if w <= 0:
                continue
            b = np.cross(d, hole)
            if np.linalg.norm(b) < 0.3:
                b = np.cross(d, outward)
            b /= np.linalg.norm(b)
            pts = (c + s_[:, None, None] * d + uu[None, :, None] * b).reshape(-1, 3)
            dist, j = tree.query(pts, distance_upper_bound=0.003, workers=-1)
            ok = np.isfinite(dist)
            if not ok.any():
                continue
            sd = np.einsum("ij,ij->i", pts[ok] - allp[j[ok]], alln[j[ok]])
            ww = np.where(sd < 0, 1.0, smooth_w(dist[ok], 0.0, 0.0015)) * fall[ok]
            hit_j.append(j[ok][ww > 0.02])
            hit_w.append(w * ww[ww > 0.02])
        if hit_j:
            hj, hw = np.concatenate(hit_j), np.concatenate(hit_w)
            uj, inv = np.unique(hj, return_inverse=True)
            uw = np.bincount(inv, weights=hw)
            # лента прилегает полосой: растекание по соседним текселям в пределах 2,5 мм
            near = tree.query_ball_point(allp[uj], r=0.0025, workers=-1)
            ln = np.fromiter((len(x) for x in near), np.int64, len(near))
            flat = np.concatenate(near)
            np.add.at(acc, flat, np.repeat(uw * st["strap_gain"] * sp["weight"] / np.maximum(ln, 1), ln))
        log(f"ремень {sp['object']}: ось отверстия {np.round(hole, 2)}, касаний ленты {len(np.unique(hj)) if hit_j else 0}")
    for i, s in enumerate(sets):
        SETS[s]["acc"]["sling_wear"] += acc[owner == i]


# ------------------------------------------------------------------ сжатие и запись
def finish():
    meta = {}
    for c in CHANNELS:
        v = np.concatenate([SETS[s]["acc"][c] for s in SETS])
        pos = v[v > 1e-9]
        if not len(pos):
            continue
        # суммы касаний — логарифмом от верхней четверти (слабые хвосты растекания почти не видны), доли граней
        # обвесов — линейно, ремень — корнем (лента много слабее самой антабки)
        linear = c in ("mount_wear", "sling_wear")
        v0, vmax = np.quantile(pos, 0.75), np.quantile(pos, 0.995 if not linear else 0.99)
        meta[c] = {"v0": float(v0), "vmax": float(vmax), "texels": int(len(pos)), "scale": "linear" if linear else "log"}
        for s, t in SETS.items():
            if linear:
                m = np.clip(t["acc"][c] / vmax, 0, 1) ** (0.5 if c == "sling_wear" else 1.0)
            else:
                m = np.clip(np.log1p(t["acc"][c] / v0) / np.log1p(vmax / v0), 0, 1)
            size = int(t["size"])
            img = np.zeros((size, size), np.uint16)
            img[size - 1 - t["ys"].astype(np.int64), t["xs"].astype(np.int64)] = np.round(m * 65535).astype(np.uint16)
            cv2.imwrite(str(OUT / f"{s}_{c}.png"), img)
    for s, t in SETS.items():
        np.savez_compressed(OUT / f"raw_{s}.npz", **{c: t["acc"][c].astype(np.float32) for c in CHANNELS})
    (OUT / "masks.json").write_text(json.dumps({"channels": meta, "config": CFG}, ensure_ascii=False, indent=1), encoding="utf-8")
    log("маски записаны:", OUT, json.dumps(meta, ensure_ascii=False))


if __name__ == "__main__":
    if "hand" in ONLY:
        orient_normals()
        accumulate_hands()
    if "mag" in ONLY:
        accumulate_magazine()
    if "mount" in ONLY:
        accumulate_mounts()
    if "sling" in ONLY:
        accumulate_sling()
    finish()
