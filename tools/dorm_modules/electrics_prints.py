"""Электрика общежития, печать этапа 1 слоем для Painter: надпись на трубке ЛБ-40 у цоколя и травление на колбе
лампы А60. Марки выдуманы («ЛУЧЕЗАР», «СВЕТЛЯК»); тип лампы и напряжение — обозначения ГОСТ, не марки.

  python -X utf8 tools/dorm_modules/electrics_prints.py   # → _asset_src/dorm_electrics/prints/uv/<набор>_print_*

Карты геометрии — print_bake.py (electrics_uv) в _asset_src/dorm_electrics/prints/geo; слой кладёт Painter над
заводской отделкой (sp_dorm_wear._print_layer). Шрифт DejaVu (как у мусора и мебели).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import print_apply as A  # noqa: E402
import print_designs as PD  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "dorm_electrics"


def to_array(im: Image.Image) -> np.ndarray:
    return np.asarray(im.convert("RGBA"), np.float32) / 255.0


def tube_label() -> np.ndarray:
    """Штамп у цоколя 46 × 8 мм: тип, напряжение, знак завода — серой краской."""
    im, d = PD.canvas(46, 8)
    ink = (70, 74, 70, 235)
    PD.text(d, 23, 4.2, "ЛБ40 · 220В · ЛУЧЕЗАР", PD.font(PD.SANS_B, 3.2), ink)
    return to_array(im)


def bulb_etch() -> np.ndarray:
    """Травление на маковке колбы 22 × 12 мм: напряжение и мощность, марка — матовым по прозрачному."""
    im, d = PD.canvas(22, 12)
    ink = (235, 235, 232, 150)
    PD.text(d, 11, 4.0, "220В 60Вт", PD.font(PD.SANS_B, 3.0), ink)
    PD.text(d, 11, 8.6, "СВЕТЛЯК", PD.font(PD.SANS, 2.6), ink)
    return to_array(im)


def tube() -> None:
    game = "el_tube"
    g = A.load_geo(BASE, game)
    layers = []
    # целая трубка — на −Y, обломок — на +Y (цоколь у −X у обоих): штамп снизу, в 85 мм от торца
    for name, y in (("Трубка_люминофор", -0.045), ("Трубка_люминофор__обломок", 0.045)):
        prn = A.decal(g, A.part_mask(g, name), tube_label(), (-0.52, y, -0.092 - 0.02025), (0, 0, -1), (1, 0, 0), 46, 8,
                      depth=0.008)
        layers.append((prn, None, None, 1.0))
    A.save_layer(BASE, game, layers)


def bulb() -> None:
    game = "el_bulb"
    g = A.load_geo(BASE, game)
    # маковка колбы смотрит вниз (лампа в патроне на шнуре); травление матовое
    prn = A.decal(g, A.part_mask(g, "Лампа_стекло"), bulb_etch(), (0.0, 0.0, -0.8125), (0, 0, -1), (1, 0, 0), 22, 12,
                  depth=0.008)
    A.save_layer(BASE, game, [(prn, 0.0, 0.5, 1.0)])


ITEMS = {"el_tube": tube, "el_bulb": bulb}

if __name__ == "__main__":
    only = sys.argv[1:]
    for k, fn in ITEMS.items():
        if not only or k in only:
            fn()
