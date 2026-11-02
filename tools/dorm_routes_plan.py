"""Общежитие: схема предложения по входам и вертикальным путям (владелец 2026-11-02: 4 жилых этажа открыты, 5-й —
технический, две наружные пожарные лестницы на каждый этаж и крышу, с крыши — на техэтаж и ниже, проломы с
ящиками между этажами — лестницу может держать один отряд). Разрез по связям и планы этажей с метками.

  python -X utf8 tools/dorm_routes_plan.py   # → docs/design/dorm_routes.png

Предложение, не план стройки: метки берут помещения из data/blockouts/dorm.json, перестройка — после решения владельца.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / "data/blockouts/dorm.json").read_text(encoding="utf-8"))
OUT = ROOT / "docs/design/dorm_routes.png"
FONT = "C:/Windows/Fonts/arial.ttf"
FONT_B = "C:/Windows/Fonts/arialbd.ttf"

# предложение: проломы (откуда → куда, помещение, способ), разовые спуски, входы снаружи
BREACHES = [
    ("П1", 1, 2, "f2_room_1_2", "ящики и обломки под дырой в потолке"),
    ("П2", 2, 3, "f2_room_-1_5", "куча обломков перекрытия"),
    ("П3", 3, 4, "f3_room_1_7", "шкаф и кровать штабелем"),
    ("П4", 4, 5, "f4_storage_-1_6", "люк и стальная лестница на техэтаж"),
]
DROPS = [("С1", 4, 3, "f4_room_-1_3", "провал пола — только вниз")]
COLORS = {"stair": (60, 120, 200), "fire": (215, 70, 40), "breach": (40, 150, 70), "drop": (150, 60, 160),
          "entry": (230, 160, 20), "hatch": (120, 120, 120)}


def font(size, bold=False):
    return ImageFont.truetype(FONT_B if bold else FONT, size)


def space(sid):
    return next(s for s in PLAN["spaces"] if s["id"] == sid)


def center(sid):
    x0, z0, x1, z1 = space(sid)["rect"]
    return (x0 + x1) / 2, (z0 + z1) / 2


def elevation(img, d, ox, oy, w, h):
    """Разрез по связям: этажи — полосы, x — вдоль корпуса (хозкрыло — справа), стрелки — пути между уровнями."""
    levels = ["1 этаж", "2 этаж", "3 этаж", "4 этаж", "5 — техэтаж", "Крыша"]
    lh = h / (len(levels) + 0.3)
    xs = lambda x: ox + 150 + (x + 4) / 56 * (w - 190)
    ys = lambda lv: oy + h - (lv + 0.5) * lh
    d.text((ox, oy - 34), "Связи между уровнями (вид вдоль корпуса; хозкрыло — справа)", font=font(24, True), fill=(20, 20, 20))
    for i, name in enumerate(levels):
        y = ys(i)
        d.rectangle([xs(0), y - lh * 0.32, xs(43.4), y + lh * 0.32], outline=(150, 150, 150), width=2,
                    fill=(236, 236, 230) if i < 4 else ((222, 222, 214) if i == 4 else (210, 225, 235)))
        d.text((ox, y - 10), name, font=font(19, i >= 4), fill=(30, 30, 30))

    def link(x, lv0, lv1, color, label, dashed=False, width=6):
        x = xs(x)
        y0, y1 = ys(lv0), ys(lv1)
        if dashed:
            yy = y0
            step = 14 if y1 < y0 else -14
            while (yy - y1) * (1 if y1 < y0 else -1) > 0:
                d.line([x, yy, x, yy - step / 2 * (1 if y1 < y0 else 1)], fill=color, width=width)
                yy -= step
        else:
            d.line([x, y0, x, y1], fill=color, width=width)
        tip = y1
        sgn = 1 if y1 < y0 else -1
        d.polygon([(x - 9, tip + sgn * 14), (x + 9, tip + sgn * 14), (x, tip)], fill=color)
        if label:
            d.text((x + 8, (y0 + y1) / 2 - 10), label, font=font(17, True), fill=color)
    # центральная лестница 1–4 и дальше на техэтаж, выход на крышу будкой
    for lv in range(4):
        link(20.7, lv, lv + 1, COLORS["stair"], "" if lv < 4 else "")
        link(21.6, lv + 1, lv, COLORS["stair"], "")
    link(20.7, 4, 5, COLORS["stair"], "будка выхода на крышу")
    d.text((xs(20.7) - 70, ys(0) + lh * 0.35), "центральная лестница", font=font(16), fill=COLORS["stair"])
    # пожарные лестницы снаружи: с запада и с торца хозкрыла
    for x, name in ((-2.8, "Пожарная А (запад)"), (47.5, "Пожарная Б (торец хозкрыла)")):
        d.line([xs(x), ys(0) + lh * 0.3, xs(x), ys(5)], fill=COLORS["fire"], width=10)
        for lv in range(6):
            d.line([xs(x) - 14, ys(lv), xs(x) + 14, ys(lv)], fill=COLORS["fire"], width=6)
        d.text((xs(x) - 120 if x < 0 else xs(x) - 160, ys(5) - lh * 0.75), name, font=font(17, True), fill=COLORS["fire"])
    for code, f0, f1, sid, how in BREACHES:
        x, _ = center(sid)
        link(x, f0 - 1, f1 - 1, COLORS["breach"] if f1 < 5 else COLORS["hatch"], code)
    for code, f0, f1, sid, how in DROPS:
        x, _ = center(sid)
        link(x, f0 - 1, f1 - 1, COLORS["drop"], code, dashed=True)
    link(3.0, 4, 5, COLORS["hatch"], "люк Л")
    # входы с улицы
    for x, label in ((1.95, "главный вход"), (43.4, "чёрный ход"), (10.6, "окно"), (36.0, "окно")):
        d.ellipse([xs(x) - 9, ys(0) + lh * 0.3 - 9, xs(x) + 9, ys(0) + lh * 0.3 + 9], fill=COLORS["entry"])
        d.text((xs(x) - 30, ys(0) + lh * 0.42), label, font=font(15), fill=(120, 80, 0))


def plans(img, d, ox, oy, cw, ch):
    """Планы 1–5 этажей и крыши: корпус, коридоры, лестница, метки путей."""
    titles = ["1 этаж — входы", "2 этаж", "3 этаж", "4 этаж", "5 — техэтаж", "Крыша"]
    sc = min(cw / 62, ch / 56)
    for i, title in enumerate(titles):
        bx = ox + (i % 3) * (cw + 30)
        by = oy + (i // 3) * (ch + 60)
        X = lambda x: bx + (x + 6) * sc
        Y = lambda z: by + 30 + (12 - z) * sc * 0.82
        d.text((bx, by), title, font=font(20, True), fill=(20, 20, 20))
        outline = [(X(x), Y(z)) for x, z in PLAN["outline"]]
        d.polygon(outline, fill=(238, 238, 232) if i < 5 else (214, 228, 238), outline=(90, 90, 90))
        floor = i + 1
        if i < 5:
            for s in PLAN["spaces"]:
                if s["floor"] != floor:
                    continue
                x0, z0, x1, z1 = s["rect"]
                d.rectangle([X(x0), Y(z1), X(x1), Y(z0)], outline=(175, 175, 170), width=1,
                            fill=(250, 250, 246) if s["kind"] == "room" else None)
        cx0, cz0, cx1, cz1 = PLAN["stair_core"]["rect"]
        d.rectangle([X(cx0), Y(cz1), X(cx1), Y(cz0)], fill=COLORS["stair"] + (0,), outline=COLORS["stair"], width=3)
        # пожарные лестницы
        for x, z, horiz in ((-2.6, 0.0, False), (41.71, -41.2, True)):
            d.rectangle([X(x) - 7, Y(z) - 7, X(x) + 7, Y(z) + 7], fill=COLORS["fire"])
        for code, f0, f1, sid, how in BREACHES:
            if floor in (f0, f1):
                x, z = center(sid.replace(f"f{2 if f0 == 1 else f0}_", f"f{floor}_") if False else sid)
                col = COLORS["breach"] if f1 < 5 else COLORS["hatch"]
                d.ellipse([X(x) - 9, Y(z) - 9, X(x) + 9, Y(z) + 9], fill=col)
                arrow = "↑" if floor == f0 else "↓"
                d.text((X(x) + 10, Y(z) - 11), code + arrow, font=font(16, True), fill=col)
        for code, f0, f1, sid, how in DROPS:
            if floor in (f0, f1):
                x, z = center(sid)
                d.ellipse([X(x) - 9, Y(z) - 9, X(x) + 9, Y(z) + 9], outline=COLORS["drop"], width=4)
                d.text((X(x) + 10, Y(z) - 11), code + ("↓" if floor == f0 else ""), font=font(16, True), fill=COLORS["drop"])
        if floor in (5, 6):
            d.ellipse([X(3.0) - 8, Y(5.0) - 8, X(3.0) + 8, Y(5.0) + 8], fill=COLORS["hatch"])
            d.text((X(3.0) + 10, Y(5.0) - 11), "Л", font=font(16, True), fill=COLORS["hatch"])
        if floor == 1:
            for x, z in ((1.95, 9.6), (44.3, 0.0), (10.6, -9.6), (33.0, -16.0)):
                d.ellipse([X(x) - 8, Y(z) - 8, X(x) + 8, Y(z) + 8], fill=COLORS["entry"])


def legend(d, ox, oy):
    items = [("stair", "центральная лестница (1–4, техэтаж, будка на крышу)"), ("fire", "пожарные лестницы снаружи: каждый этаж и крыша"),
             ("breach", "проломы с подъёмом: ящики, обломки, мебель"), ("hatch", "люки со стальной лестницей (4 → техэтаж, техэтаж → крыша)"),
             ("drop", "провал — только спрыгнуть вниз"), ("entry", "входы с улицы: двери и разбитые окна 1 этажа")]
    for k, (c, t) in enumerate(items):
        y = oy + k * 30
        d.rectangle([ox, y, ox + 22, y + 22], fill=COLORS[c])
        d.text((ox + 32, y), t, font=font(18), fill=(30, 30, 30))


def main() -> None:
    img = Image.new("RGB", (2000, 1500), (255, 255, 255))
    d = ImageDraw.Draw(img, "RGBA")
    d.text((40, 20), "Общежитие: пути внутрь и между этажами — предложение (не стройка)", font=font(30, True), fill=(10, 10, 10))
    elevation(img, d, 40, 110, 1150, 560)
    legend(d, 1260, 140)
    plans(img, d, 40, 730, 600, 330)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUT)
    print("saved", OUT)


if __name__ == "__main__":
    main()
