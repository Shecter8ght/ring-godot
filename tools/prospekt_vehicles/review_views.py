"""Транспорт «Проспекта»: проверочные виды машины для review.py — четыре камеры от габарита.

    python -X utf8 tools/prospekt_vehicles/review_views.py <Имя> <X варианта>   → «f34:… r34:… low:… top:…»

Легковая — прежние камеры (масштаб 1); автобус, ПАЗ, ГАЗель — те же ракурсы, растянутые на длину и высоту кузова.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from specs_bus import BOXES  # noqa: E402

def views(name: str, x: float) -> str:
    if "over" in name.lower():
        # перевёрнутый автобус лежит на левом борту: корень повёрнут, по X — высота кузова, по Z — ширина
        v = [("f34", (x + 8.0, -12.0, 5.0), (x + 1.4, -1.0, 1.0), 32), ("r34", (x + 12.0, 2.0, 2.6), (x + 1.4, 0.0, 1.2), 30),
             ("low", (x - 7.0, -8.0, 3.2), (x + 1.2, 0.0, 1.0), 30), ("top", (x + 1.4, -2.0, 16.0), (x + 1.4, 0.0, 0.0), 30)]
        return " ".join(f"{n}:{a[0]:.2f},{a[1]:.2f},{a[2]:.2f}:{b[0]:.2f},{b[1]:.2f},{b[2]:.2f}:{lens}" for n, a, b, lens in v)
    spec = next((v for k, v in BOXES.items() if k in name.lower()), None)
    s, h = (spec["length"] / 4.5, spec["height"] / 1.45) if spec else (1.0, 1.0)
    v = [("f34", (x + 4.2 * s, -4.6 * s, 1.3 * h), (x, -0.3 * s, 0.6 * h), 42),
         ("r34", (x - 3.4 * s, 4.6 * s, 1.5 * h), (x, 0.4 * s, 0.6 * h), 42),
         ("low", (x + 2.6 * h, -2.8 * s, 0.5 * h), (x + 0.4 * h, -1.2 * s, 0.45 * h), 35),
         ("top", (x + 2.2 * s, -1.2 * s, 3.2 * h), (x, 0.2 * s, 0.9 * h), 40)]

    def f(p):
        return ",".join(f"{c:.2f}" for c in p)
    return " ".join(f"{n}:{f(a)}:{f(b)}:{lens}" for n, a, b, lens in v)


if __name__ == "__main__":
    print(views(sys.argv[1], float(sys.argv[2])))
