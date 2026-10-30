# AR-15 «ГРАНЬ-15», этап 2 (износ): метки владельца со страницы разметки (tools/ar15/mark_server.py) → маски по
# развёртке наборов текстур. Пиксели метки на рендере → мировые точки (карта точек вида, tools/ar15/mark_views.py) →
# места развёртки рядом с ними (карты наборов, tools/ar15/wear_maps.py), только смотрящие в камеру — обратная сторона
# тонкой детали метку не получает. Вид износа в Painter зависит от материала под меткой — класс места:
# fde (песочный Cerakote), anod (чёрное анодирование), steel (сталь: фосфат, нитрид, хром, пружины), poly (полимер,
# резина), brass (латунь, оболочка пули).
# Сила метки: у «до металла» и «протёрто» — как далеко от кромок детали внутри метки заходят рваные пятна полной силы
# (0,2 — ниточка по кромке, 0,5 — до ~4 мм, 0,7 — до ~7 мм); у «царапин» и «сколов» — их число; не прозрачность:
# полупрозрачный металл поверх песка не читался (первые метки владельца 30.10). У «заглажено», «масло», «грязь»,
# «пыль», «отпечатки» — плотность (прозрачность слоя).
#   python -X utf8 tools/ar15/mark_apply.py [папка разметки]
# Пишет <набор>_zone_mark_<тип>_<класс>_L.png в _asset_src/ar15/tex/wear и marks_index.json (что есть — для
# sp_ar15_wear.build_marks()).
import itertools
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import map_coordinates
from scipy.spatial import cKDTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tex_sets  # noqa: E402
from wear_lower import WEAR, lint, sstep  # noqa: E402
from wear_magazine import strokes  # noqa: E402

ROOT = sys.argv[1] if len(sys.argv) > 1 else "E:/Models Blender/WEAPONS/AR-15 — модель/Разметка_износа"
BASE = "E:/Models Blender/WEAPONS/AR-15 — модель/Текстуры_этап1_v6_песок"
SEED = 3101
LENS, SENSOR = 50.0, 36.0
_cache = {}


def load_set(name):
    """Карты набора и класс материала в каждом пикселе развёртки."""
    if name in _cache:
        return _cache[name]
    d = np.load(os.path.join(WEAR, f"{name}_maps.npz"))
    pos, nrm, ids = d["pos"], d["nrm"].astype(np.float32), d["ids"]
    mats = list(d["ids_mats"]) if "ids_mats" in d else [""] * len(d["ids_names"])
    lut = np.zeros(len(mats), dtype=np.uint8)            # 0 — пусто, 1 fde, 2 anod, 3 steel, 4 poly, 5 brass
    for i, m in enumerate(mats):
        if i == 0:
            continue
        lut[i] = 4 if m in ("Polymer", "Rubber") else 5 if m in ("Brass", "Bullet_jacket") else 1 if m == "Alu_anodized" else 3
    cls = lut[ids]
    if (cls == 1).any():
        # анодированный алюминий: песочный Cerakote или чёрное анодирование — по заводскому цвету этапа 1
        base = np.asarray(Image.open(os.path.join(BASE, f"{name}_baseColor.png")).convert("RGB")).astype(np.float32) / 255
        if base.shape[0] != ids.shape[0]:
            base = np.asarray(Image.fromarray((base * 255).astype(np.uint8)).resize(ids.shape[::-1])).astype(np.float32) / 255
        dark = base.mean(-1) < 0.25
        cls = np.where((cls == 1) & dark, 2, cls)
    # пикселей на мм — по соседям в развёртке (для ворсинок)
    m = ids > 0
    dx = np.linalg.norm(pos[:, 1:] - pos[:, :-1], axis=-1)[m[:, 1:] & m[:, :-1]]
    px_mm = 1.0 / max(float(np.median(dx[dx > 0])), 1e-3)
    _cache[name] = (pos, nrm, ids, cls, px_mm)
    return _cache[name]


def edge_dist(pos, nrm, ids, cand, rr, cc, px_mm):
    """Расстояние (мм) от мест метки до ближайшей выпуклой кромки той же детали — острой или скруглённой (радиус до
    ~3 мм, низ раструба шахты магазина). Кромка — выпуклость по соседям в пространстве (радиус ~0,8 мм): средняя
    ((n_q − n_p)·(q − p)) / |q − p|², у сферы радиуса R это 1/R, у плоскости 0, у вогнутого угла меньше нуля — во
    внутренних углах металл не протирается. Соседи в пространстве, а не в развёртке: рёбра обычно лежат на швах
    развёртки; соседи — из всего габарита метки, с обеих сторон ребра, и смотрящие от камеры."""
    r = max(0.8, 6.0 / px_mm)
    big = 1.0e5                                       # номер детали — четвёртая координата: соседи только своей детали
    ar, ac = np.nonzero(cand)
    P, N, I = pos[ar, ac], nrm[ar, ac], ids[ar, ac].astype(np.float64)
    # запас развёртки (EXTEND) повторяет пиксели края, а плотная сетка точек не нужна — прореживание по 0,1 мм
    step = max(0.1, 1.0 / px_mm)
    _, u = np.unique(np.c_[np.round(P / step).astype(np.int64), I.astype(np.int64)], axis=0, return_index=True)
    P, N, I = P[u], N[u], I[u]
    tree = cKDTree(np.c_[P, I * big])
    p0, n0 = pos[rr, cc], nrm[rr, cc]
    q = np.c_[p0, ids[rr, cc].astype(np.float64) * big]
    dd, jj = tree.query(q, k=48, distance_upper_bound=r)
    ok = (jj < len(P)) & (dd > 1e-3)
    jj = np.where(ok, jj, 0)
    dp = P[jj] - p0[:, None, :]
    k = ((N[jj] - n0[:, None, :]) * dp).sum(-1) / np.maximum((dp * dp).sum(-1), 1e-6)
    kappa = np.where(ok, k, 0.0).sum(1) / np.maximum(ok.sum(1), 1)
    e = kappa > 0.15
    if not e.any():
        return np.full(len(rr), np.inf, dtype=np.float32)
    d, _ = cKDTree(q[e]).query(q, k=1)
    return d.astype(np.float32)


CLASS = {1: "fde", 2: "anod", 3: "steel", 4: "poly", 5: "brass"}


COVER = ("bare", "wear_through")                 # сила — доля пятен полной силы
DRAWN = ("scratches", "chips")                     # сила — число штрихов / сколов


_masks = {}


def photo(name, blur=0.0):
    """Фото-маска CC0 (wear_masks.py → _asset_src/ar15/tex/wear/masks), 0…1."""
    if (name, blur) not in _masks:
        im = Image.open(os.path.join(WEAR, "masks", name + ".png")).convert("L")
        if blur:
            im = im.filter(ImageFilter.GaussianBlur(blur))
        _masks[(name, blur)] = np.asarray(im).astype(np.float32) / 255.0
    return _masks[(name, blur)]


def tri(p, n, img, tile_mm, seed):
    """Фото-маска на детали трипланарно по мировой точке (мм), как трипланар Painter: одна и та же на соседних
    гранях, швы развёртки её не рвут. Три проекции сдвинуты, чтобы не повторять друг друга."""
    h = img.shape[0]
    w = np.abs(n) ** 4
    w /= w.sum(1, keepdims=True) + 1e-8
    off = np.random.default_rng(seed).random((3, 2)) * h
    out = np.zeros(len(p), dtype=np.float32)
    for ax, (u, v) in enumerate(((1, 2), (0, 2), (0, 1))):
        rc = np.stack([p[:, v] / tile_mm * h + off[ax, 0], p[:, u] / tile_mm * h + off[ax, 1]])
        out += w[:, ax] * map_coordinates(img, rc, order=1, mode="grid-wrap")
    return out


def cover(items, typ, strength, seed):
    """Пятна «до металла» / «протёрто» по местам метки во всех наборах: от кромок детали внутрь на расстояние по силе.
    Рисунок — с фото-масок CC0, не из шума: ширина кромки — мягкие облака (местами кромка цела), край — рваный по мелким
    крапинам; «протёрто» (покрытие до основания) заходит внутрь формами настоящих сколов, «до металла» — заполированная
    кромка без хлопьев, с мягким краем. Круглые пятна гладкого шума читались процедурой, а сколы на стальной кромке —
    облупленной краской («выглядит процедурно», владелец 30.10).
    Если метка обводит кромку (у кромок хотя бы десятая часть её площади), пятна — только у кромок: плоские детали,
    захваченные кистью при обводке (рама затвора в окне ствольной коробки), чисты — до этого на них ложился «камуфляж».
    Метка на гладком месте без кромок — пятна долей силы на главной детали метки (больше половины площади), кроме
    видной в глубине проёма (дальше передней детали метки на 4 мм).
    items: (набор, rr, cc, region, d, pos, nrm, ids, px_mm, до камеры) → [(набор, rr, cc, покрытие)]."""
    dl = 3.0 * strength / max(1.05 - strength, 0.05)
    area, depth = {}, {}
    for name, rr, cc, reg, d, p, nn, pid, px, dist in items:
        for i in np.unique(pid):
            m = pid == i
            area[(name, int(i))] = area.get((name, int(i)), 0.0) + float(m.sum()) / px ** 2
            depth.setdefault((name, int(i)), []).append(dist[m])
    total = max(sum(area.values()), 1e-6)
    depth = {k: float(np.median(np.concatenate(v))) for k, v in depth.items()}
    front = min(depth[k] for k in depth if area[k] / total >= 0.1)
    at_edge = sum(float((d < 0.5).sum()) / px ** 2 for _, _, _, _, d, _, _, _, px, _ in items) / total >= 0.1
    out = []
    for name, rr, cc, reg, d, p, nn, pid, px, dist in items:
        cloudy = tri(p, nn, photo("cloudy", 2.0), 25.0, seed)
        fine = tri(p, nn, photo("fine"), 12.0, seed + 2)
        if typ == "wear_through":
            chips = tri(p, nn, photo("chips", 3.0), 30.0, seed + 1)
            band = dl * (0.75 * cloudy - 0.12 + 1.5 * chips)
            tw = max(0.06, 0.7 / px)
            jit = (fine - 0.15) * min(0.35, 0.3 * dl)
        else:
            # заполированная кромка уже и без зубцов по краю: рваный край крапинами читался «лесом» на крышке окна
            chips = tri(p, nn, photo("chips", 6.0), 30.0, seed + 1)
            band = 0.6 * dl * (0.9 * cloudy - 0.1 + 0.3 * chips)
            tw = max(0.06, 0.7 / px, 0.15 * dl)
            jit = 0.0
        cov = 1.0 - sstep(band - tw, band + tw, d + jit)
        for i in np.unique(pid):
            m = pid == i
            if not at_edge and area[(name, int(i))] / total >= 0.5 and depth[(name, int(i))] <= front + 4.0:
                sc = 0.7 * chips[m] + 0.3 * cloudy[m]
                t = np.quantile(sc, 1.0 - strength) if m.sum() > 10 else 0.5
                cov[m] = sstep(t - 0.03, t + 0.03, sc)
        out.append((name, rr, cc, reg * cov))
    return out


def encode(k):
    k = k.astype(np.int64) + (1 << 16)
    return (k[..., 0] << 34) | (k[..., 1] << 17) | k[..., 2]


def apply_mark(mk, views, sets, acc, rng):
    vname = mk["view"]
    a = np.asarray(Image.open(os.path.join(ROOT, "marks", mk["file"])).convert("RGBA"))[..., 3].astype(np.float32) / 255
    pts = np.load(os.path.join(ROOT, "views", f"{vname}_pts.npz"))
    vpos, vset = pts["pos"], pts["set"]
    cam = np.array(views[vname]["cam"], dtype=np.float32)
    w_all = a * float(mk.get("strength", 0.7))
    sel = (a > 0.05) & (vset > 0)
    report = []
    pending = []                                     # «до металла», «протёрто» — считаются по всей метке разом
    for s in np.unique(vset[sel]):
        name = sets[int(s) - 1]
        m = sel & (vset == s)
        P, Wt = vpos[m], w_all[m]
        dist = np.linalg.norm(P - cam, axis=-1)
        mmpp = float(np.median(dist)) * (SENSOR / LENS) / vpos.shape[1]
        cell = max(0.25, 1.5 * mmpp)
        pos, nrm, ids, cls, px_mm = load_set(name)
        # места развёртки в габарите метки
        lo, hi = P.min(0) - 2 * cell, P.max(0) + 2 * cell
        cand = (ids > 0) & np.all((pos >= lo) & (pos <= hi), axis=-1)
        if not cand.any():
            continue
        # ячейки метки (с соседними — сглаживание по краю), вес — наибольший
        kp = np.floor(P / cell)
        keys, wts = [], []
        for off in itertools.product((-1, 0, 1), repeat=3):
            keys.append(encode(kp + np.array(off)))
            wts.append(Wt)
        keys, wts = np.concatenate(keys), np.concatenate(wts)
        order = np.argsort(keys)
        keys, wts = keys[order], wts[order]
        uk, start = np.unique(keys, return_index=True)
        uw = np.maximum.reduceat(wts, start)
        rr, cc = np.nonzero(cand)
        tp, tn = pos[rr, cc], nrm[rr, cc]
        tk = encode(np.floor(tp / cell))
        j = np.clip(np.searchsorted(uk, tk), 0, len(uk) - 1)
        hit = (uk[j] == tk) & ((tn * (cam - tp)).sum(-1) > 0.0)
        rr, cc, w = rr[hit], cc[hit], uw[j[hit]]
        strength = float(mk.get("strength", 0.7))
        region = np.clip(w / max(strength, 1e-3), 0.0, 1.0)          # прозрачность кисти без силы
        report.append(f"{name}: {int(hit.sum())} пикс. развёртки")
        if mk["type"] in COVER:
            pending.append((name, rr, cc, region, edge_dist(pos, nrm, ids, cand, rr, cc, px_mm), pos[rr, cc], nrm[rr, cc],
                            ids[rr, cc], px_mm, np.linalg.norm(pos[rr, cc] - cam, axis=-1)))
            continue
        for c in np.unique(cls[rr, cc]):
            if c == 0:
                continue
            k = (name, mk["type"], CLASS[int(c)])
            if k not in acc:
                acc[k] = np.zeros(ids.shape, dtype=np.float32)
            sc = cls[rr, cc] == c
            if mk["type"] in DRAWN:
                acc[k] = np.maximum(acc[k], drawn(mk["type"], pos, nrm, ids, rr[sc], cc[sc], region[sc], P, strength,
                                                  px_mm, rng))
                continue
            if mk["type"] == "lint":
                # ворсинки: несколько нитей от случайных мест метки (синтетика — рисунок кодом)
                area = sc.sum() / px_mm ** 2
                n = int(np.clip(area / 30.0, 1, 6))
                pick = rng.choice(int(sc.sum()), size=min(n, int(sc.sum())), replace=False)
                ok = np.zeros(ids.shape, dtype=bool)
                ok[rr[sc], cc[sc]] = True
                ok = np.asarray(Image.fromarray(ok.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(9))) > 0
                fib = lint(ok, [(int(rr[sc][i]), int(cc[sc][i])) for i in pick], px_mm, rng, ids.shape[0])
                np.maximum(acc[k], fib * float(mk.get("strength", 0.7)), out=acc[k])
            else:
                np.maximum.at(acc[k], (rr[sc], cc[sc]), w[sc])
    if pending:
        for name, rr, cc, v in cover(pending, mk["type"], float(mk.get("strength", 0.7)),
                                     SEED + sum(map(ord, mk["id"])) % 1000):
            cls = load_set(name)[3][rr, cc]
            for c in np.unique(cls):
                if c == 0:
                    continue
                k = (name, mk["type"], CLASS[int(c)])
                if k not in acc:
                    acc[k] = np.zeros(cls.shape[:0] + load_set(name)[2].shape, dtype=np.float32)
                sc = cls == c
                np.maximum.at(acc[k], (rr[sc], cc[sc]), v[sc])
    print("метка", mk["id"], mk["type"], "→", "; ".join(report) or "мимо деталей")


def drawn(typ, pos, nrm, ids, rr, cc, region, P, strength, px_mm, rng):
    """Царапины — штрихи 2–8 мм вдоль мазка (главная ось точек метки) ±20°; сколы — отдельные точки 0,3–0,7 мм;
    число — по площади метки и силе."""
    size = ids.shape[0]
    allowed = np.zeros(ids.shape, dtype=bool)
    allowed[rr, cc] = region > 0.3
    area = allowed.sum() / px_mm ** 2
    out = np.zeros(ids.shape, dtype=np.float32)
    if area < 0.5:
        return out
    if typ == "scratches":
        c = P - P.mean(0)
        axis = np.linalg.svd(c[:: max(1, len(c) // 4000)], full_matrices=False)[2][0]
        jit = lambda p, n: axis + np.cross(n, axis) * rng.normal(0.0, 0.35)
        cnt = int(np.clip(area * strength / 1.5, 3, 600))             # сила 0,35 — около 70 штрихов на 300 мм²
        a, b = strokes(pos, nrm, ids, allowed, allowed, jit, rng, count=cnt, length_mm=(2.0, 8.0), deep_frac=0.3)
        return np.maximum(a, b) * allowed
    cnt = int(np.clip(area * strength / 5.0, 2, 400))
    pick = rng.choice(len(rr), size=min(cnt, len(rr)), replace=False)
    for i in pick:
        r0, c0 = rr[i], cc[i]
        p0, rad = pos[r0, c0], rng.uniform(0.3, 0.7)
        h = int(rad * px_mm * 2) + 3
        y0, y1, x0, x1 = max(r0 - h, 0), min(r0 + h, size), max(c0 - h, 0), min(c0 + h, size)
        d = np.linalg.norm(pos[y0:y1, x0:x1] - p0, axis=-1)
        sub = out[y0:y1, x0:x1]
        np.maximum(sub, (1.0 - sstep(rad * 0.6, rad, d)) * (ids[y0:y1, x0:x1] == ids[r0, c0]), out=sub)
    return out * allowed


def main():
    marks = json.load(open(os.path.join(ROOT, "marks", "marks.json"), encoding="utf-8"))["marks"]
    vj = json.load(open(os.path.join(ROOT, "views.json"), encoding="utf-8"))
    sets = vj.get("sets") or list(tex_sets.SETS)
    rng = np.random.default_rng(SEED)
    acc = {}
    for mk in marks:
        apply_mark(mk, vj["views"], sets, acc, rng)
    # прежние маски меток — прочь (это файлы самого конвейера), новые — с лёгким размытием края
    for fn in os.listdir(WEAR):
        if "_zone_mark_" in fn:
            os.remove(os.path.join(WEAR, fn))
    items = []
    for (name, typ, cl), a in sorted(acc.items()):
        img = Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))
        if typ not in ("lint", "scratches", "chips"):
            img = img.filter(ImageFilter.GaussianBlur(1.0 if typ not in COVER else 0.6))
        fn = f"{name}_zone_mark_{typ}_{cl}_L.png"
        img.save(os.path.join(WEAR, fn))
        items.append({"set": name, "type": typ, "class": cl, "file": fn})
        print("маска", fn, "пикселей > 0,1:", int((np.asarray(img) > 25).sum()))
    with open(os.path.join(WEAR, "marks_index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"items": items, "marks": len(marks)}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
