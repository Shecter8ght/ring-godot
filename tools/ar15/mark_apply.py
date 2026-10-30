# AR-15 «ГРАНЬ-15», этап 2 (износ): метки владельца со страницы разметки (tools/ar15/mark_server.py) → маски по
# развёртке наборов текстур. Пиксели метки на рендере → мировые точки (карта точек вида, tools/ar15/mark_views.py) →
# места развёртки рядом с ними (карты наборов, tools/ar15/wear_maps.py), только смотрящие в камеру — обратная сторона
# тонкой детали метку не получает. Вид износа в Painter зависит от материала под меткой — класс места:
# fde (песочный Cerakote), anod (чёрное анодирование), steel (сталь: фосфат, нитрид, хром, пружины), poly (полимер,
# резина), brass (латунь, оболочка пули).
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

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tex_sets  # noqa: E402
from wear_lower import WEAR, lint  # noqa: E402

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


CLASS = {1: "fde", 2: "anod", 3: "steel", 4: "poly", 5: "brass"}


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
        for c in np.unique(cls[rr, cc]):
            if c == 0:
                continue
            k = (name, mk["type"], CLASS[int(c)])
            if k not in acc:
                acc[k] = np.zeros(ids.shape, dtype=np.float32)
            sc = cls[rr, cc] == c
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
        report.append(f"{name}: {int(hit.sum())} пикс. развёртки")
    print("метка", mk["id"], mk["type"], "→", "; ".join(report) or "мимо деталей")


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
        if typ != "lint":
            img = img.filter(ImageFilter.GaussianBlur(1.0))
        fn = f"{name}_zone_mark_{typ}_{cl}_L.png"
        img.save(os.path.join(WEAR, fn))
        items.append({"set": name, "type": typ, "class": cl, "file": fn})
        print("маска", fn, "пикселей > 0,1:", int((np.asarray(img) > 25).sum()))
    with open(os.path.join(WEAR, "marks_index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"items": items, "marks": len(marks)}, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
