# ПП по мотивам KRISS Vector Gen II: головки осей разборки и винтов на бортах (снимки KRISS A и B: положения и
# диаметры колец). Большие — оси разборки (4 оси Vector + оси спусковой коробки): фланец Ø13 с кольцевой канавкой,
# бобышка Ø7 с шлицем-«крестом» под ключ; малые Ø9 — винты с шестигранным гнездом. Головки на своём борту, стержни
# скрыты в корпусе и не моделируются (навык: скрытое ради числа объектов не добавлять).
import math
import bpy
from lib import MM, HALF_W, lathe, prism_xy, cyl, boolean, finish_small, apply_transform, v
from part_receiver import GRIP_HALF_W

# (x, z, тип, стороны, деталь-хозяин): тип big — ось Ø13, small — винт Ø9; стороны: «LR» — обе, «L» — только слева
PINS = [
    (40.5, 38.0, "big", "LR", "Receiver"), (90.0, 0.0, "big", "LR", "Receiver"),
    (40.5, 0.0, "big", "LR", "Receiver"), (-105.0, 37.5, "big", "LR", "Receiver"),
    (0.0, 46.0, "small", "L", "Receiver"),
    (20.0, -5.0, "small", "LR", "Receiver"), (-55.0, -36.0, "small", "LR", "Receiver"),
    (-70.0, -88.0, "small", "LR", "Receiver"), (-93.0, -100.0, "big", "LR", "Receiver"),
    (-158.0, -100.0, "big", "LR", "Receiver"),
]


def head(name, x, z, kind, side, ys, C):
    """Головка на борту: ys — полуширина детали в этом месте (борт), side = ±1."""
    from lib import apply_transform, prism_xz
    r = 6.5 if kind == "big" else 4.5
    s = 1 if side > 0 else -1
    # профиль головки вдоль её оси (от борта наружу): фланец, кольцевая канавка, бобышка
    if kind == "big":
        prof = [(0.0, 0.0), (0.0, r), (0.55, r), (0.9, r - 0.4), (0.9, 4.6), (0.75, 4.2), (0.75, 3.7), (1.45, 3.5),
                (1.55, 3.2), (1.55, 0.0)]
    else:
        prof = [(0.0, 0.0), (0.0, r), (0.5, r), (0.8, r - 0.4), (0.8, 0.0)]
    top = prof[-1][0] - 0.4
    o = lathe(name, [(-0.4 + p, rr) for p, rr in prof], C, "Steel_black", seg=64)
    # ось токарного профиля — X; поворачиваем к борту (±Y)
    o.rotation_euler = (0, 0, math.pi / 2 if s > 0 else -math.pi / 2)
    o.location = v(x, ys * s, z)
    apply_transform(o)
    y_out = (ys + top) * s
    if kind == "big":
        # полый штифт: отверстие Ø4.6 глубиной 2.2, в нём — проволочная пружинка поперёк (снимок владельца 04)
        h = cyl("_ph", min(y_out - 2.2 * s, y_out + 2 * s), max(y_out - 2.2 * s, y_out + 2 * s), 2.3, C, seg=48,
                cy=x, cz=z, axis="Y")
        boolean(o, h)
        w = cyl(name + "_spring", -2.0, 2.0, 0.45, C, "Spring_steel", seg=16, cy=0.0, cz=0.0, axis="X")
        w.rotation_euler = (0, math.radians(35.0), 0)
        w.location = v(x, y_out - 1.3 * s, z)
        apply_transform(w)
        w["owner"] = name
    else:
        hexp = [(x + 1.5 * math.cos(math.pi / 3 * k), z + 1.5 * math.sin(math.pi / 3 * k)) for k in range(6)]
        c = prism_xz("_hex", hexp, min(y_out - 1.0 * s, y_out + 2 * s), max(y_out - 1.0 * s, y_out + 2 * s), C)
        boolean(o, c)
    finish_small(o, w=0.15, seg=2)
    return o


def build(ctx):
    C = ctx["coll"]["Pins"]
    objs = []
    for i, (x, z, kind, sides, owner) in enumerate(PINS):
        ys = GRIP_HALF_W if x < -150.0 and z < -60.0 else HALF_W
        for side, tag in ((1, "L"), (-1, "R")):
            if tag in sides:
                o = head(f"Pin_{i:02d}_{tag}", x, z, kind, side, ys, C)
                o["owner"] = owner
                objs.append(o)
    return {"pins": objs}
