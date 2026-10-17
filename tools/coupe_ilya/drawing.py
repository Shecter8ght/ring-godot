"""Купе Ильи: линии чертежа CLE (dimensions.com) в метрах машины.

Чертёж лежит у владельца в библиотеке моделей (references/web), в репозиторий не кладётся —
это чужая иллюстрация, только для сверки силуэта. Отсюда берутся контуры четырёх видов
(слой OUTLINE) и линии кузова (TRANSPORT, DETAILS).

Оси машины: X — вбок (левый борт +X), Y — вдоль (перёд к −Y), Z — вверх от земли.
Y = 0 — середина колёсной базы. Масштаб — длина CLE 53 (4,853 м) на ширину бокового контура.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

SVG_DEFAULT = Path(r"E:\Models Blender\VEHICLES\Купе Ильи\references\web\cle_coupe_dimensions_dimensions-com.svg")

LENGTH_M = 4.853
SIDE_X0, SIDE_X1 = 60.0, 651.1          # края бокового контура на чертеже
GROUND_SIDE = 242.2                      # земля бокового и переднего видов
GROUND_REAR = 515.8                      # земля вида сзади
REAR_WHEEL_X, FRONT_WHEEL_X = 191.55, 541.45
PLAN_CY = (328.5 + 581.3) / 2            # ось машины на плане
VIEW_CX = (694.2 + 945.1) / 2            # ось на видах спереди и сзади
S = LENGTH_M / (SIDE_X1 - SIDE_X0)       # метров в единице чертежа
MID_X = (REAR_WHEEL_X + FRONT_WHEEL_X) / 2
WHEEL_Y = (FRONT_WHEEL_X - REAR_WHEEL_X) / 2 * S   # колёса на ±WHEEL_Y
WHEEL_Z = (GROUND_SIDE - 200.4) * S                 # центр колеса над землёй

_TOK = re.compile(r"[MmLlHhVvCcSsQqTtAaZz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


def _sample_path(d: str, steps: int = 12) -> list[np.ndarray]:
    """d-атрибут SVG → список ломаных (кривые Безье семплируются)."""
    toks = _TOK.findall(d)
    i = 0
    cmd = ""
    x = y = sx = sy = 0.0
    lc: tuple[float, float] | None = None
    subs: list[list[tuple[float, float]]] = []
    cur: list[tuple[float, float]] = []

    def num() -> float:
        nonlocal i
        v = float(toks[i])
        i += 1
        return v

    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t
            i += 1
            if cmd in "Zz":
                if cur:
                    cur.append((sx, sy))
                    subs.append(cur)
                cur = []
                x, y = sx, sy
                continue
        rel = cmd.islower()
        c = cmd.upper()
        ox, oy = (x, y) if rel else (0.0, 0.0)
        if c == "M":
            if cur:
                subs.append(cur)
            x, y = num() + ox, num() + oy
            sx, sy = x, y
            cur = [(x, y)]
            cmd = "l" if rel else "L"
            lc = None
        elif c == "L":
            x, y = num() + ox, num() + oy
            cur.append((x, y))
            lc = None
        elif c == "H":
            x = num() + (x if rel else 0.0)
            cur.append((x, y))
            lc = None
        elif c == "V":
            y = num() + (y if rel else 0.0)
            cur.append((x, y))
            lc = None
        elif c in "CS":
            if c == "C":
                x1, y1 = num() + ox, num() + oy
            else:
                x1, y1 = (2 * x - lc[0], 2 * y - lc[1]) if lc else (x, y)
            x2, y2 = num() + ox, num() + oy
            ex, ey = num() + ox, num() + oy
            for k in range(1, steps + 1):
                u = k / steps
                a, b, cc, dd = (1 - u) ** 3, 3 * u * (1 - u) ** 2, 3 * u * u * (1 - u), u ** 3
                cur.append((a * x + b * x1 + cc * x2 + dd * ex, a * y + b * y1 + cc * y2 + dd * ey))
            lc = (x2, y2)
            x, y = ex, ey
        elif c in "QT":
            if c == "Q":
                x1, y1 = num() + ox, num() + oy
            else:
                x1, y1 = (2 * x - lc[0], 2 * y - lc[1]) if lc else (x, y)
            ex, ey = num() + ox, num() + oy
            for k in range(1, steps + 1):
                u = k / steps
                cur.append(((1 - u) ** 2 * x + 2 * u * (1 - u) * x1 + u * u * ex,
                            (1 - u) ** 2 * y + 2 * u * (1 - u) * y1 + u * u * ey))
            lc = (x1, y1)
            x, y = ex, ey
        elif c == "A":
            for _ in range(5):
                num()
            x, y = num() + ox, num() + oy
            cur.append((x, y))
            lc = None
        else:
            i += 1
    if cur:
        subs.append(cur)
    return [np.array(s, dtype=float) for s in subs if len(s) > 1]


def load_layers(svg: Path = SVG_DEFAULT) -> dict[str, dict[str, list[np.ndarray]]]:
    """Слой → {id ломаной → список ломаных в координатах чертежа}."""
    s = svg.read_text(encoding="utf-8")
    marks = [(m.group(1), m.start()) for m in re.finditer(r'<g id="(_x32_D_x24_AG-[A-Z]+|N-DIMENSIONS)"', s)]
    marks.append(("END", len(s)))
    out: dict[str, dict[str, list[np.ndarray]]] = {}
    for (name, a), (_, b) in zip(marks, marks[1:]):
        layer: dict[str, list[np.ndarray]] = {}
        for pm in re.finditer(r'<g id="(POLYLINE\d*|LINE\d*)"[^>]*>(.*?)</g>', s[a:b], re.S):
            polys: list[np.ndarray] = []
            for d in re.findall(r'\sd="([^"]+)"', pm.group(2)):
                polys += _sample_path(d)
            if polys:
                layer[pm.group(1)] = polys
        out[name.replace("_x32_D_x24_AG-", "")] = layer
    return out


def side_to_m(p: np.ndarray) -> np.ndarray:
    """Боковой вид → (Y, Z) машины."""
    return np.c_[-(p[:, 0] - MID_X) * S, (GROUND_SIDE - p[:, 1]) * S]


def plan_to_m(p: np.ndarray) -> np.ndarray:
    """План → (X, Y) машины."""
    return np.c_[(p[:, 1] - PLAN_CY) * S, -(p[:, 0] - MID_X) * S]


def front_to_m(p: np.ndarray) -> np.ndarray:
    """Вид спереди → (X, Z)."""
    return np.c_[(p[:, 0] - VIEW_CX) * S, (GROUND_SIDE - p[:, 1]) * S]


def rear_to_m(p: np.ndarray) -> np.ndarray:
    """Вид сзади → (X, Z)."""
    return np.c_[(p[:, 0] - VIEW_CX) * S, (GROUND_REAR - p[:, 1]) * S]


def view_of(poly: np.ndarray) -> str:
    """Какому виду принадлежит ломаная (по положению на листе)."""
    cx, cy = poly[:, 0].mean(), poly[:, 1].mean()
    if cx < 670:
        return "side" if cy < 270 else "plan"
    return "front" if cy < 270 else "rear"


def outlines(layers: dict) -> dict[str, np.ndarray]:
    """Внешние контуры четырёх видов в метрах (каждый — одна длинная ломаная)."""
    res: dict[str, np.ndarray] = {}
    conv = {"side": side_to_m, "plan": plan_to_m, "front": front_to_m, "rear": rear_to_m}
    for polys in layers["OUTLINE"].values():
        p = max(polys, key=len)
        v = view_of(p)
        res[v] = conv[v](p)
    return res


def lines(layers: dict, view: str) -> dict[str, list[np.ndarray]]:
    """Линии кузова одного вида (TRANSPORT + DETAILS) в метрах."""
    conv = {"side": side_to_m, "plan": plan_to_m, "front": front_to_m, "rear": rear_to_m}[view]
    res: dict[str, list[np.ndarray]] = {}
    for layer in ("TRANSPORT", "DETAILS"):
        for pid, polys in layers.get(layer, {}).items():
            mine = [conv(p) for p in polys if view_of(p) == view]
            if mine:
                res[pid] = mine
    return res
