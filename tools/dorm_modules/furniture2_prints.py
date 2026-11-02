"""Мебель общежития, партия 2: печать этапа 1 слоем для Painter — тёмно-синий ободок эмалированной посуды (край
кастрюли и крышки, кнопка, край крышки и кончик носика чайника), шкалы ручек и надписи панели плиты, марка на дверце
духовки. Марка выдумана («РУСЛО»), «ЭП-4» — тип, не марка.

  python -X utf8 tools/dorm_modules/furniture2_prints.py   # → _asset_src/dorm_furniture2/prints/uv/<набор>_print_*

Карты геометрии — print_bake.py (furniture2_uv) в _asset_src/dorm_furniture2/prints/geo; слой кладёт Painter над
заводской отделкой (sp_dorm_wear._print_layer). Шрифт DejaVu.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as A  # noqa: E402
import print_designs as PD  # noqa: E402
from wear_zones import smooth  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "dorm_furniture2"
RIM = (0.07, 0.11, 0.3)        # тёмно-синяя эмаль ободка (sRGB-доли)


def zone_layer(mask: np.ndarray) -> np.ndarray:
    prn = np.zeros(mask.shape + (4,), np.float32)
    prn[..., :3] = RIM
    prn[..., 3] = np.clip(mask, 0, 1)
    return prn


def pot() -> None:
    game = "furn_pot"
    g = A.load_geo(BASE, game)
    p = g["pos"]
    enamel = A.part_mask(g, "Посуда_эмаль")
    r = np.hypot(p[..., 0], p[..., 1])
    z = p[..., 2]
    # край кастрюли — закатанный борт и 4 мм ниже; край крышки — внешние 9 мм; кнопка крышки целиком
    body_rim = smooth(z, 0.131, 0.1335) * (r > 0.098) * (z < 0.1435)
    lid_rim = smooth(r, 0.101, 0.1035) * (z > 0.1325)
    knob = (z > 0.152) * (r < 0.0175)
    A.save_layer(BASE, game, [(zone_layer(enamel * np.maximum.reduce([body_rim, lid_rim, knob])), 0.0, 0.09, 1.0)])


def kettle() -> None:
    game = "furn_kettle"
    g = A.load_geo(BASE, game)
    p = g["pos"]
    enamel = A.part_mask(g, "Посуда_эмаль")
    r = np.hypot(p[..., 0], p[..., 1])
    z = p[..., 2]
    # горловина и край крышки, кнопка, кончик носика (последние 12 мм), нижний край дна
    neck = (z > 0.159) * (r < 0.05) * (r > 0.035)
    lid = smooth(r, 0.034, 0.038) * (z > 0.163) * (r < 0.048)
    knob = (z > 0.174) * (r < 0.013)
    spout = smooth(p[..., 0], 0.153, 0.157) * (z > 0.13)
    foot = (z < 0.006) * (r > 0.08)
    A.save_layer(BASE, game, [(zone_layer(enamel * np.maximum.reduce([neck, lid, knob, spout, foot])), 0.0, 0.09, 1.0)])


def stove_panel() -> np.ndarray:
    """Панель плиты 490 × 68 мм: шкалы «0–3» над ручками конфорок, у ручки духовки — градусы, значки конфорок."""
    im, d = PD.canvas(490, 68)
    ink = (40, 42, 46, 235)
    f = PD.font(PD.SANS_B, 4.6)
    fs = PD.font(PD.SANS, 3.2)
    for k in range(5):
        cx, cy = 245 - 180 + k * 90, 34 + 3.5
        marks = ["0", "1", "2", "3"] if k != 2 else ["0", "150", "200", "250"]
        for i, s in enumerate(marks):
            a = math.radians(160 - i * 46.7)
            x0, y0 = cx + 22.5 * math.cos(a), cy - 22.5 * math.sin(a)
            x1, y1 = cx + 25.5 * math.cos(a), cy - 25.5 * math.sin(a)
            d.line([(PD.mm(x0), PD.mm(y0)), (PD.mm(x1), PD.mm(y1))], fill=ink, width=PD.mm(0.6))
            PD.text(d, cx + 29.5 * math.cos(a), cy - 29.5 * math.sin(a), s, fs if k == 2 else f, ink)
        if k != 2:
            # значок конфорки: квадрат плиты, у включаемой — закрашенный круг
            bx, by = cx - 33, cy + 20
            d.rectangle([PD.mm(bx - 4.5), PD.mm(by - 4.5), PD.mm(bx + 4.5), PD.mm(by + 4.5)], outline=ink, width=PD.mm(0.4))
            spots = [(-2.2, -2.2), (2.2, -2.2), (-2.2, 2.2), (2.2, 2.2)]
            for j, (sx, sy) in enumerate(spots):
                on = j == [2, 0, 1, 3][k if k < 2 else k - 1]
                box = [PD.mm(bx + sx - 1.4), PD.mm(by + sy - 1.4), PD.mm(bx + sx + 1.4), PD.mm(by + sy + 1.4)]
                d.ellipse(box, fill=ink if on else None, outline=ink, width=PD.mm(0.3))
        else:
            PD.text(d, cx - 36, cy + 20, "ДУХОВКА", fs, ink)
    return A_to(im)


def oven_mark() -> np.ndarray:
    """Марка на дверце духовки 120 × 18 мм: «РУСЛО» и «ЭП-4» хромированной краской."""
    im, d = PD.canvas(120, 18)
    ink = (176, 178, 180, 240)
    PD.text(d, 48, 9.5, "РУСЛО", PD.font(PD.SANS_B, 9.0), ink)
    PD.text(d, 102, 10.5, "ЭП-4", PD.font(PD.SANS, 5.0), ink)
    return A_to(im)


def A_to(im) -> np.ndarray:
    return np.asarray(im.convert("RGBA"), np.float32) / 255.0


def stove() -> None:
    game = "furn_stove"
    g = A.load_geo(BASE, game)
    body = A.part_mask(g, "Плита_эмаль")
    door = A.part_mask(g, "Плита_эмаль__дверца")
    yf = -0.3 + 0.02
    w = np.array([0.0, -0.25, 0.97])
    w /= np.linalg.norm(w)
    n = np.array([0.0, -w[2], w[1]])     # нормаль наклонной панели — вперёд и чуть вниз
    c = np.array([0.0, yf - 0.004, 0.85 - 0.08]) + w * 0.035
    panel = A.decal(g, body, stove_panel(), tuple(c + n * 0.0), tuple(n), (1, 0, 0), 490, 68, depth=0.01, cos_min=0.6)
    mark = A.decal(g, door, oven_mark(), (0.0, yf - 0.035, 0.2 + 0.318), (0, -1, 0), (1, 0, 0), 120, 18, depth=0.008)
    A.save_layer(BASE, game, [(panel, 0.0, 0.3, 1.0), (mark, 0.6, 0.25, 1.0)])


ITEMS = {"furn_pot": pot, "furn_kettle": kettle, "furn_stove": stove}

if __name__ == "__main__":
    only = sys.argv[1:]
    for k, fn in ITEMS.items():
        if not only or k in only:
            fn()
