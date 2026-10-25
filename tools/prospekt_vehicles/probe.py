"""Проба поверхности поля: точка вида → точка кузова (для подбора раскладки)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from specs import CLASSES
from vfield import CarField

def hit(f, O, D):
    O = np.array(O, float); D = np.array(D, float)
    t = np.linspace(0, 4.0, 8001)
    P = O + t[:, None] * D
    v = f.eval(P[:, 0], P[:, 1], P[:, 2])
    i = int(np.argmax(v < 0))
    return P[i].round(3) if v[i] < 0 else None

def main():
    f = CarField(CLASSES[sys.argv[1]])
    for q in sys.argv[2:]:
        k, a, b = q.split(":"); a, b = float(a), float(b)
        if k == "side": r = hit(f, (2, a, b), (-1, 0, 0))
        elif k == "top": r = hit(f, (a, b, 3), (0, 0, -1))
        elif k == "front": r = hit(f, (a, -3.5, b), (0, 1, 0))
        elif k == "rear": r = hit(f, (a, 3.5, b), (0, -1, 0))
        print(q, "->", r)

if __name__ == "__main__":
    main()
