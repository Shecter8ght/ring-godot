"""Контейнеры для лута, партия 1: печать этапа 1 слоем для Painter — вымышленные марки, шильдики, наклейки, знаки; маской в
развёртке (надпись — часть поверхности своей детали, без воздушного зазора).

  python -X utf8 tools/loot_containers/lc_prints.py [набор …]   # → _asset_src/loot_containers/prints/uv/<набор>_print_*

Карты геометрии — lc_print_bake.py (положение, нормаль, деталь в каждом пикселе развёртки, поза открытого состояния);
положения шильдиков и якорей (лимб, дверца аптечки, клапан сумки) — plates.json из lc_uv.py. Слой кладёт Painter над
заводской отделкой (sp_dorm_wear._print_layer). Шрифт DejaVu Sans (у Inter «А» без перекладины). Список надписей — в
asset-state.md. Реальных брендов и логотипов нет; красный крест на белом не используется (белый на красном — сумка,
зелёный на белом — аптечка).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dorm_modules"))
import print_apply as A  # noqa: E402
import print_designs as PD  # noqa: E402

BASE = Path(__file__).resolve().parents[2] / "_asset_src" / "loot_containers"


def load_geo(base: Path, game: str):
    """Карты геометрии .npy (lc_print_bake.py): положение, нормаль, номер детали; строки сверху вниз."""
    g = {k: np.load(base / "prints" / "geo" / f"{game}_{k}.npy") for k in ("pos", "nrm", "part")}
    parts = json.loads((base / "prints" / "geo" / f"{game}_parts.json").read_text(encoding="utf-8"))
    g["part_id"] = np.rint(g["part"][..., 0]).astype(np.int32)
    g["names"] = {int(k): v for k, v in parts.items()}
    return g


A.load_geo = load_geo
PLATES = json.loads((BASE / "plates.json").read_text(encoding="utf-8"))
INK = (28, 29, 32, 240)
WHITE = (236, 236, 230, 245)
ROUGH, METAL = 0.5, 0.0    # краска печати: полуматовая, не металл

SANS_B, SANS = PD.SANS_B, PD.SANS


def arr(im) -> np.ndarray:
    return np.asarray(im.convert("RGBA"), np.float32) / 255.0


def fm(size: float, bold: bool = True):
    return PD.font(SANS_B if bold else SANS, size)


def center_text(d, w, y, s, size, fill, bold=True) -> None:
    PD.text(d, w / 2, y, s, fm(size, bold), fill)


def nameplate(w, h, brand, model, serial) -> np.ndarray:
    """Алюминиевая пластинка: рамка, марка, модель, номер — тёмная краска."""
    im, d = PD.canvas(w, h)
    d.rectangle([PD.mm(0.9), PD.mm(0.9), PD.mm(w - 0.9), PD.mm(h - 0.9)], outline=INK, width=PD.mm(0.3))
    big = min(h * 0.40, w / (len(brand) * 0.78))
    center_text(d, w, h * 0.34, brand, big, INK)
    center_text(d, w, h * 0.67, model, h * 0.15, INK)
    center_text(d, w, h * 0.86, serial, h * 0.11, INK, bold=False)
    return arr(im)


def sticker_instruction(w, h) -> np.ndarray:
    """Наклейка-инструкция на нутре дверцы сейфа: красная шапка, четыре строки, знак «внимание»."""
    im, d = PD.canvas(w, h)
    d.rectangle([PD.mm(1), PD.mm(1), PD.mm(w - 1), PD.mm(h - 1)], outline=(30, 30, 34, 255), width=PD.mm(0.35))
    d.rectangle([PD.mm(1), PD.mm(1), PD.mm(w - 1), PD.mm(13)], fill=(176, 28, 24, 255))
    PD.text(d, w / 2, 7.2, "ВНИМАНИЕ", fm(7.0), (240, 238, 232, 255))
    rows = ["1. Закройте дверцу до упора.", "2. Поверните штурвал по часовой.", "3. Сбросьте код: четыре оборота",
            "    лимба влево, затем набор заново.", "Код не хранить в сейфе."]
    for k, s in enumerate(rows):
        PD.text(d, 4, 20 + k * 8.0, s, fm(4.0, bold=False), (26, 26, 30, 255), anchor="lm")
    # знак «внимание»: жёлтый треугольник с восклицательным знаком
    cx, cy = w - 14, h - 14
    tri = [(PD.mm(cx), PD.mm(cy - 9)), (PD.mm(cx + 10), PD.mm(cy + 8)), (PD.mm(cx - 10), PD.mm(cy + 8))]
    d.polygon(tri, fill=(240, 196, 32, 255), outline=(26, 26, 30, 255))
    d.line(tri + [tri[0]], fill=(26, 26, 30, 255), width=PD.mm(0.8))
    PD.text(d, cx, cy + 2, "!", fm(10.0), (26, 26, 30, 255))
    PD.text(d, 4, h - 6, "КРЕПЬ · С-70", fm(3.2), (90, 90, 96, 255), anchor="lm")
    return arr(im)


def sticker_inventory(w, h) -> np.ndarray:
    """Наклейка-опись на створке оружейного шкафа: шапка, графы «№ / Наименование / Кол.», пустые строки."""
    im, d = PD.canvas(w, h)
    col = (30, 30, 34, 255)
    d.rectangle([PD.mm(1), PD.mm(1), PD.mm(w - 1), PD.mm(h - 1)], outline=col, width=PD.mm(0.4))
    d.rectangle([PD.mm(1), PD.mm(1), PD.mm(w - 1), PD.mm(14)], fill=(28, 70, 40, 255))
    PD.text(d, w / 2, 7.6, "ОПИСЬ ХРАНЕНИЯ", fm(7.5), (240, 238, 232, 255))
    x1, x2 = 14, w - 24
    y0 = 20
    d.line([(PD.mm(1), PD.mm(y0)), (PD.mm(w - 1), PD.mm(y0))], fill=col, width=PD.mm(0.35))
    for x, s in ((8, "№"), ((x1 + x2) / 2, "Наименование"), (w - 12, "Кол.")):
        PD.text(d, x, y0 - 3.4, s, fm(3.6), col)
    rows = 8
    step = (h - 12 - y0) / rows
    for k in range(rows + 1):
        y = y0 + k * step
        d.line([(PD.mm(1), PD.mm(y)), (PD.mm(w - 1), PD.mm(y))], fill=(80, 80, 86, 255), width=PD.mm(0.25))
    for x in (x1, x2):
        d.line([(PD.mm(x), PD.mm(y0 - 6)), (PD.mm(x), PD.mm(h - 12))], fill=(80, 80, 86, 255), width=PD.mm(0.25))
    for k in range(rows):
        PD.text(d, 8, y0 + (k + 0.5) * step, str(k + 1), fm(3.4, bold=False), (60, 60, 66, 255))
    PD.text(d, 4, h - 6, "Ответственный: ____________", fm(3.4, bold=False), col, anchor="lm")
    return arr(im)


def dial_strip() -> np.ndarray:
    """Шкала лимба в полярной развёртке: ширина — окружность 210 мм (угол от верха по часовой), высота — радиус 40 → 30 мм.
    50 рисок (каждая пятая длиннее, как на модели), цифры 0…90 у длинных."""
    w, h = 210.0, 10.0
    im, d = PD.canvas(w, h)
    for i in range(50):
        x = w * i / 50
        ln = 4.2 if i % 5 == 0 else 2.8
        d.rectangle([PD.mm(x - 0.5), PD.mm(0.4), PD.mm(x + 0.5), PD.mm(0.4 + ln)], fill=WHITE)
        if i % 5 == 0:
            PD.text(d, x, 7.0, str(i * 2), fm(3.6), WHITE)
    return arr(im)


def key_legend(s: str, ink, size=4.4) -> np.ndarray:
    im, d = PD.canvas(21, 25)
    PD.text(d, 10.5, 12.5, s, fm(size), ink)
    return arr(im)


def cross_aid(w, h) -> np.ndarray:
    """Дверца аптечки: зелёный крест, «АПТЕЧКА», «ПЕРВАЯ ПОМОЩЬ» (зелёный на белом)."""
    im, d = PD.canvas(w, h)
    g = (0, 104, 50, 255)
    cx, cy, arm, half = w / 2, h * 0.31, 30.0, 62.0
    d.rectangle([PD.mm(cx - arm / 2), PD.mm(cy - half), PD.mm(cx + arm / 2), PD.mm(cy + half)], fill=g)
    d.rectangle([PD.mm(cx - half), PD.mm(cy - arm / 2), PD.mm(cx + half), PD.mm(cy + arm / 2)], fill=g)
    PD.text(d, cx, h * 0.68, "АПТЕЧКА", fm(34.0), g)
    PD.text(d, cx, h * 0.83, "ПЕРВАЯ ПОМОЩЬ", fm(12.5), g)
    return arr(im)


def cross_bag(w, h) -> np.ndarray:
    """Клапан сумки: белый крест в белом кольце, под ним «ПЕРВАЯ ПОМОЩЬ»."""
    im, d = PD.canvas(w, h)
    cx, cy, R = w / 2, h * 0.38, 50.0
    d.ellipse([PD.mm(cx - R), PD.mm(cy - R), PD.mm(cx + R), PD.mm(cy + R)], outline=WHITE, width=PD.mm(3.4))
    arm, half = 11.0, 30.0
    d.rectangle([PD.mm(cx - arm / 2), PD.mm(cy - half), PD.mm(cx + arm / 2), PD.mm(cy + half)], fill=WHITE)
    d.rectangle([PD.mm(cx - half), PD.mm(cy - arm / 2), PD.mm(cx + half), PD.mm(cy + arm / 2)], fill=WHITE)
    PD.text(d, cx, h * 0.80, "ПЕРВАЯ ПОМОЩЬ", fm(15.0), WHITE)
    return arr(im)


def A_decal(g, mask, img, info, w, h, depth=0.02, cos_min=0.5, shift=(0.0, 0.0)) -> np.ndarray:
    c = np.array(info["center"]) + np.array(info["right"]) * shift[0] / 1000 - np.array(info.get("up", [0, 0, 0])) * shift[1] / 1000
    return A.decal(g, mask, img, tuple(c), tuple(info["normal"]), tuple(info["right"]), w, h, depth=depth, cos_min=cos_min)


def plate_layer(g, game, name, img) -> np.ndarray:
    info = PLATES[game][name]
    return A.decal(g, A.part_mask(g, name), img, tuple(info["center"]), tuple(info["normal"]), tuple(info["right"]),
                   info["w"], info["h"], depth=0.0012, cos_min=0.6)


def L(a):
    return (a, METAL, ROUGH, 1.0)


def safe() -> None:
    game = "lc_safe"
    g = A.load_geo(BASE, game)
    pl = PLATES[game]
    lay = [L(plate_layer(g, game, "СН_шильдик", nameplate(80, 22, "КРЕПЬ", "С-70 · КЛАСС II", "№ 004217 · 2026"))),
           L(plate_layer(g, game, "СН_наклейка_инструкция", sticker_instruction(110, 70)))]
    # шкала лимба
    c = np.array(pl["dial"]["center"])
    right, up, n = np.array(pl["dial"]["right"]), np.array(pl["dial"]["up"]), np.array(pl["dial"]["normal"])
    d = g["pos"] - c
    dx, dz = d @ right, d @ up
    r = np.hypot(dx, dz)
    ang = np.arctan2(dx, dz) % (2 * math.pi)
    ok = A.part_mask(g, "СН_лимб__шкала") & (r > 0.0300) & (r < 0.0400) & ((g["nrm"] @ n) > 0.5)
    lay.append(L(A.sample(dial_strip(), ang / (2 * math.pi), (0.0400 - r) / 0.0100, ok)))
    A.save_layer(BASE, game, lay)


def cell() -> None:
    game = "lc_cell"
    g = A.load_geo(BASE, game)
    A.save_layer(BASE, game, [L(plate_layer(g, game, "СЯ_шильдик", nameplate(46, 14, "КРЕПЬ", "ЯС-1", "№ 0731")))])


def gun() -> None:
    game = "lc_gun"
    g = A.load_geo(BASE, game)
    A.save_layer(BASE, game, [L(plate_layer(g, game, "ОШ_шильдик", nameplate(80, 24, "РУБЕЖ", "ОШ-5 · НА 5 СТВОЛОВ", "№ 013582"))),
                              L(plate_layer(g, game, "ОШ_наклейка_опись", sticker_inventory(150, 110)))])


def file_() -> None:
    game = "lc_file"
    g = A.load_geo(BASE, game)
    A.save_layer(BASE, game, [L(plate_layer(g, game, "КШ_шильдик", nameplate(60, 16, "АРХИВ-4", "ШК-4 · 4 ЯЩИКА", "№ 20817")))])


KB_P0 = np.array([0.0, -0.20, 0.135])
KB_SL = np.array([0.0, 0.23, 0.043])


def cash() -> None:
    game = "lc_cash"
    g = A.load_geo(BASE, game)
    lay = [L(plate_layer(g, game, "КМ_шильдик", nameplate(70, 14, "ТОРГ-410", "КАССОВЫЙ АППАРАТ", "№ 7-20193")))]
    sl = KB_SL / np.linalg.norm(KB_SL)
    t = math.atan2(KB_SL[2], KB_SL[1])
    n = np.array([0.0, -math.sin(t), math.cos(t)])
    legends = {}
    for k, s in enumerate(["КОД", "ЧЕК", "ВОЗВР", "СКД", "НАЦ", "ОТМ", "ПРОМ", "ВВОД"]):
        legends[(0, k)] = (s, 3.4, "dark")
    for (row, col), s in {(4, 8): "7", (4, 9): "8", (4, 10): "9", (3, 8): "4", (3, 9): "5", (3, 10): "6", (2, 8): "1", (2, 9): "2",
                          (2, 10): "3", (1, 8): "0", (1, 9): ",", (1, 10): "00", (4, 11): "+", (3, 11): "−", (2, 11): "×",
                          (1, 11): "="}.items():
        legends[(row, col)] = (s, 5.2, "light")
    legends[(5, 0)] = ("СБРОС", 3.4, "color")
    legends[(5, 1)] = ("ОПЛАТА", 3.2, "color")
    legends[(5, 2)] = ("ИТОГ", 3.6, "color")
    groups = {"dark": A.part_mask(g, "КМ_клавиатура__тёмные"), "light": A.part_mask(g, "КМ_клавиатура__светлые"),
              "color": A.part_mask(g, "КМ_клавиатура__красная") | A.part_mask(g, "КМ_клавиатура__зелёная")
              | A.part_mask(g, "КМ_клавиатура__синяя")}
    inks = {"dark": (222, 222, 216, 235), "light": (26, 26, 30, 240), "color": (244, 244, 238, 245)}
    acc = {k: np.zeros(g["pos"].shape[:2] + (4,), np.float32) for k in groups}
    for (row, col), (s, size, grp) in legends.items():
        u = 0.018 + row * 0.0345
        p = KB_P0 + sl * u
        c = (-0.15 + col * 0.0273, p[1], p[2] + 0.0085)
        dec = A.decal(g, groups[grp], key_legend(s, inks[grp], size), c, tuple(n), (1.0, 0.0, 0.0), 21, 25, depth=0.0016, cos_min=0.9)
        a = dec[..., 3:4]
        acc[grp] = acc[grp] * (1 - a) + dec * a
    for k in acc:
        lay.append(L(acc[k]))
    A.save_layer(BASE, game, lay)


def bag() -> None:
    game = "lc_bag"
    g = A.load_geo(BASE, game)
    info = PLATES[game]["flap"]
    ok = A.part_mask(g, "МС_клапан")
    lay = [L(A_decal(g, ok, cross_bag(480, 290), info, 480, 290, depth=0.03, cos_min=0.6))]
    A.save_layer(BASE, game, lay)


def aid() -> None:
    game = "lc_aid"
    g = A.load_geo(BASE, game)
    info = PLATES[game]["door"]
    ok = A.part_mask(g, "АП_дверца")
    A.save_layer(BASE, game, [L(A_decal(g, ok, cross_aid(340, 440), info, 340, 440, depth=0.004, cos_min=0.8))])


ITEMS = {"lc_safe": safe, "lc_cell": cell, "lc_gun": gun, "lc_file": file_, "lc_cash": cash, "lc_bag": bag, "lc_aid": aid}

if __name__ == "__main__":
    only = sys.argv[1:]
    for k, fn in ITEMS.items():
        if not only or k in only:
            fn()
