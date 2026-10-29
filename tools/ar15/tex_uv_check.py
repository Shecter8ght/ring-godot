# AR-15: замер развёртки из RizomUV без Blender — острова, заполнение квадрата, плотность (пикс/мм) и разброс
# растяжения по площади, схема островов в PNG. python -X utf8 tools/ar15/tex_uv_check.py <набор> [<набор> ...]
import json
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import tex_sets as T  # noqa: E402

RZ = T.WORK + "/rz"


def read(path):
    V, VT, F, FT, names, fobj = [], [], [], [], [], []
    cur = -1
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("v "):
            V.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            VT.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("o "):
            names.append(line[2:].strip().replace(":", "."))
            cur += 1
        elif line.startswith("f "):
            a = [t.split("/") for t in line.split()[1:]]
            F.append([int(x[0]) - 1 for x in a])
            FT.append([int(x[1]) - 1 for x in a])
            fobj.append(cur)
    return np.array(V), np.array(VT), F, FT, names, fobj


def poly_area2(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def poly_area3(p):
    n = np.zeros(3)
    for i in range(len(p)):
        n += np.cross(p[i], p[(i + 1) % len(p)])
    return 0.5 * np.linalg.norm(n)


def islands(FT, nvt):
    parent = list(range(nvt))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for ft in FT:
        r0 = find(ft[0])
        for t in ft[1:]:
            r = find(t)
            if r != r0:
                parent[r] = r0
    return find, len({find(ft[0]) for ft in FT})


def check(s):
    res = T.SETS[s][0]
    V, VT, F, FT, names, fobj = read(f"{RZ}/{s}_out.obj")
    a3 = np.array([poly_area3(V[f]) for f in F])
    a2 = np.array([poly_area2(VT[t]) for t in FT])
    find, n_isl = islands(FT, len(VT))
    ok = a3 > 1e-6
    ratio = np.sqrt(a2[ok] / a3[ok])           # ед. UV на мм
    med = float(np.median(ratio))
    td = med * res                              # пикс/мм
    dev = np.abs(np.log(ratio / med))
    w = a3[ok] / a3[ok].sum()
    bad = float((w * (dev > np.log(1.25))).sum())
    # острова по деталям
    per = {}
    for fi, ft in enumerate(FT):
        per.setdefault(names[fobj[fi]], set()).add(find(ft[0]))
    out = {"set": s, "res": res, "islands": n_isl, "coverage": round(float(a2.sum()), 3),
           "td_px_mm": round(td, 1), "stretch_gt25pct_area": round(bad, 3),
           "uv_min": VT.min(0).round(3).tolist(), "uv_max": VT.max(0).round(3).tolist(),
           "islands_per_object": {k: len(v) for k, v in sorted(per.items(), key=lambda kv: -len(kv[1]))[:12]}}
    # схема: острова, цвет — отклонение плотности (зелёный — норма, красный/синий — растянуто/сжато)
    W = 1024
    img = Image.new("RGB", (W, W), (24, 24, 24))
    d = ImageDraw.Draw(img)
    for fi, ft in enumerate(FT):
        p = VT[ft] * W
        pts = [(float(x), float(W - y)) for x, y in p]
        if a3[fi] <= 1e-6:
            col = (90, 90, 90)
        else:
            r = np.log(np.sqrt(a2[fi] / a3[fi]) / med)
            k = max(-1.0, min(1.0, r / np.log(1.5)))
            col = (int(80 + 175 * max(k, 0)), int(200 - 150 * abs(k)), int(80 + 175 * max(-k, 0)))
        d.polygon(pts, fill=col)
    img.save(f"{RZ}/{s}_layout.png")
    return out


if __name__ == "__main__":
    allres = {}
    for s in sys.argv[1:]:
        r = check(s)
        allres[s] = r
        print(json.dumps(r, ensure_ascii=False))
