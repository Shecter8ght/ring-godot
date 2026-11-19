# ВЕРАС-54 v14: маски патрона в развёртку набора ammo (обычный Python: numpy, PIL) — по образцу tools/pkp/tex_marks.py.
#   python -X utf8 tools/veras54_v14/tex/tex_marks.py [папка geo] [папка масок]
# Вход — <Деталь>_geo.npz из tex_geo_dump.py в осях самой сетки (Round_Case@local, Chambered_Case@local): тексель знает
# своё положение на гильзе в мм. Капсюль в форме не выделен (донце — одна плоскость гильзы), поэтому его место —
# по радиусу на донце. Выход — ч/б PNG размера набора (tex_sets.SETS["ammo"]), белое — зона:
#   ammo_primer.png  — капсюль (медь, слот primer): круг радиуса PRIMER_R на донце;
#   ammo_sealant.png — красный лак (слот sealant): кольцо по краю капсюля и полоска у дульца.
# Маркировка («ВЕРАС-54», «5,45×39», «АВ / 2 / ОД», «0547», цифры магазина) — гравировка в сетке без заливки краской
# (решение владельца 2026-11-19): масок надписей нет.
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tex_sets as T  # noqa: E402

GEO = sys.argv[1] if len(sys.argv) > 1 else T.WORK + "/geo"
OUT = sys.argv[2] if len(sys.argv) > 2 else T.WORK + "/masks"

PRIMER_R = 2.65          # капсюль 5,45×39 — Ø 5,3 мм
SEAL_IN, SEAL_OUT = 0.30, 0.40         # кольцо лака: внутрь капсюля и наружу от его края, мм
MOUTH_BAND = 0.8         # полоска лака у дульца, мм (вдоль оси от торца)
CASES = ("Round_Case", "Chambered_Case")


def load(name):
    z = np.load(os.path.join(GEO, name + "_geo.npz"))
    return {k: z[k] for k in z.files}


class Canvas:
    """Маска набора res × res; тексели треугольников получают value(положение текселя) (максимум с прежним)."""

    def __init__(self, res):
        self.res = res
        self.img = np.zeros((res, res), np.uint8)

    def raster(self, geo, sel, value):
        n = self.res
        uv, pos = geo["uv"][sel].astype(np.float64), geo["pos"][sel].astype(np.float64)
        for i in range(len(uv)):
            t = uv[i] * n
            x0, x1 = int(np.floor(t[:, 0].min())), int(np.ceil(t[:, 0].max())) + 1
            y0, y1 = int(np.floor(t[:, 1].min())), int(np.ceil(t[:, 1].max())) + 1
            x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, n), min(y1, n)
            if x1 <= x0 or y1 <= y0:
                continue
            px, py = np.meshgrid(np.arange(x0, x1) + 0.5, np.arange(y0, y1) + 0.5)
            a, b, c = t
            den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
            if abs(den) < 1e-14:
                continue
            w0 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / den
            w1 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / den
            w2 = 1.0 - w0 - w1
            e = -0.08                       # тексели на кромке треугольника не теряются
            ins = (w0 >= e) & (w1 >= e) & (w2 >= e)
            if not ins.any():
                continue
            p = w0[..., None] * pos[i, 0] + w1[..., None] * pos[i, 1] + w2[..., None] * pos[i, 2]
            v = np.uint8(np.clip(value(p), 0.0, 1.0) * 255)
            blk = self.img[n - y1:n - y0, x0:x1][::-1]           # v развёртки — снизу вверх
            blk[ins] = np.maximum(blk[ins], v[ins])

    def save(self, path):
        Image.fromarray(self.img).save(path)
        print("MASK", path, f"{(self.img > 127).mean():.5f} площади атласа")


def frame(g):
    """Ось гильзы (главная ось вершин), донце — конец с наибольшим радиусом у торца; t от донца к дульцу, мм."""
    p = g["pos"].reshape(-1, 3).astype(np.float64)
    c = p.mean(0)
    w, v = np.linalg.eigh(np.cov((p - c).T))
    ax = v[:, 2]
    t = (p - c) @ ax
    r = np.linalg.norm((p - c) - np.outer(t, ax), axis=1)
    lo, hi = t.min(), t.max()
    if r[t < lo + 1.0].max() < r[t > hi - 1.0].max():
        ax, t, lo, hi = -ax, -t, -hi, -lo
    # главная ось вершин у сужающейся гильзы наклонена на несколько градусов — ось уточняется по нормали плоского донца,
    # центр — середина донца
    cc = g["pos"].mean(1).astype(np.float64)
    e1 = g["pos"][:, 1] - g["pos"][:, 0]
    e2 = g["pos"][:, 2] - g["pos"][:, 0]
    a = 0.5 * np.linalg.norm(np.cross(e1, e2), axis=1)
    nr = g["nrm"].astype(np.float64)
    base = ((cc - c) @ ax < lo + 2.0) & (nr @ ax < -0.9)
    ax = -(nr[base] * a[base, None]).sum(0)
    ax /= np.linalg.norm(ax)
    c = (cc[base] * a[base, None]).sum(0) / a[base].sum()
    t = (p - c) @ ax
    return c, ax, float(t.min()), float(t.max())


def main():
    os.makedirs(OUT, exist_ok=True)
    res = T.SETS["ammo"][0]
    prim, seal = Canvas(res), Canvas(res)
    for name in CASES:
        g = load(name)
        c, ax, lo, hi = frame(g)

        def tt(p):
            return (p - c) @ ax - lo

        def rr(p):
            q = p - c
            return np.linalg.norm(q - ((q @ ax)[..., None]) * ax, axis=-1)
        cc = g["pos"].mean(1).astype(np.float64)
        cn = g["nrm"].astype(np.float64) @ ax
        # донце: грани у торца, нормаль назад вдоль оси
        head = np.nonzero((tt(cc) < 0.6) & (cn < -0.7) & (rr(cc) < PRIMER_R + SEAL_OUT + 0.6))[0]
        prim.raster(g, head, lambda p: (rr(p) < PRIMER_R - SEAL_IN).astype(np.float32))
        seal.raster(g, head, lambda p: ((rr(p) >= PRIMER_R - SEAL_IN) & (rr(p) < PRIMER_R + SEAL_OUT)).astype(np.float32))
        # дульце: всё у переднего торца (наружная полоска и кромка)
        L = hi - lo
        mouth = np.nonzero(tt(cc) > L - MOUTH_BAND - 0.5)[0]
        seal.raster(g, mouth, lambda p: (tt(p) > L - MOUTH_BAND).astype(np.float32))
        print(f"   {name}: длина {L:.2f} мм, граней донца {len(head)}, у дульца {len(mouth)}")
    prim.save(f"{OUT}/ammo_primer.png")
    seal.save(f"{OUT}/ammo_sealant.png")


if __name__ == "__main__":
    main()
