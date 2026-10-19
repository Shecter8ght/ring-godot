"""Улики заказа «Вернуть машину» на карте ТЦ (scenes/levels/mall/car_recovery_sites.tscn) → assets/textures/car_clues.

    python -X utf8 tools/gen_car_clue_textures.py   (numpy, scipy, Pillow), затем tools/godot.cmd --headless --import

Пятна и следы — из альфа-масок владельца (E:/Models Blender/Маски_АЛЬФА, по просьбе владельца 2026-10-19), остальное —
своё процедурное. Карты для Decal / материалов Godot: albedo (sRGB, в альфе — где есть), normal (OpenGL), ORM
(R — AO, G — шероховатость, B — металл).

coolant_stain_*   пятно на стоянке у доков, где из машины текло (масло с антифризом): почти чёрная глянцевая лужа —
                  «Масло_01_Тонкая_плёнка», подтёки по уклону — «Масло_05_Капля_размазанная», капли рядом —
                  «Масло_07_Полупрозрачные_пятна», вокруг пропитанный бетон с сиреневым налётом антифриза.
tire_drag_*       почти чёрные следы машины, которую утащили на заблокированных колёсах, — маски владельца
                  «23_Следы_заблокированных_шин» (2026-10-19): под машиной «Шины_06_Четыре_следа_сильное_перекрытие»,
                  дальше «Шины_05_Четыре_следа_поворот_вправо» и «Шины_03_Две_полосы_затухающие».
plate_<код>_*     номера в таре скупки (520×112 мм, 2 пикс/мм): подложка как у купе (tools/coupe_ilya/gen_textures.py),
                  выдавленные знаки и окантовка — в карте нормалей; среди чужих — К 417 МР 77.
invoice_*         накладная А4 на запчасти, партия «ЮР / 8»; бумага мятая.
tag_yur8_albedo   бирка партии — крафт, печатное «ПАРТИЯ», маркером «ЮР / 8» (как на радиаторе), отверстие.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/textures/car_clues"
OUT.mkdir(parents=True, exist_ok=True)
MASKS = Path(r"E:\Models Blender\Маски_АЛЬФА")
USED = {
    "stain": MASKS / "20_Масляные_плёнки_и_смазка/Масло_01_Тонкая_плёнка.png",
    "run": MASKS / "20_Масляные_плёнки_и_смазка/Масло_05_Капля_размазанная.png",
    "drips": MASKS / "20_Масляные_плёнки_и_смазка/Масло_07_Полупрозрачные_пятна.png",
    "drag_06": MASKS / "23_Следы_заблокированных_шин/Шины_06_Четыре_следа_сильное_перекрытие.png",
    "drag_05": MASKS / "23_Следы_заблокированных_шин/Шины_05_Четыре_следа_поворот_вправо.png",
    "drag_03": MASKS / "23_Следы_заблокированных_шин/Шины_03_Две_полосы_затухающие.png",
}
PLATES = [("K417MP77", "К", "417", "МР", "77"), ("A921BC50", "А", "921", "ВС", "50"), ("E305TK199", "Е", "305", "ТК", "199"),
          ("O774HA77", "О", "774", "НА", "77"), ("M158PY750", "М", "158", "РУ", "750"), ("T640XO190", "Т", "640", "ХО", "190")]
rng = np.random.default_rng(418)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(name, size)


def mask(key: str, size: int) -> np.ndarray:
    """Маска владельца 0..1 (белое — есть), обрезана по содержимому с полями, квадрат size."""
    a = np.asarray(Image.open(USED[key]).convert("L"), dtype=np.float32) / 255.0
    ys, xs = np.nonzero(a > 0.06)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    c = max(y1 - y0, x1 - x0) // 2 + 12
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    a = np.pad(a, c)[cy:cy + 2 * c, cx:cx + 2 * c]
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((size, size), Image.LANCZOS), dtype=np.float32) / 255.0


def fbm(size: tuple[int, int], octaves: int, base: int) -> np.ndarray:
    h, w = size
    out = np.zeros(size, np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        cells = base * 2 ** o
        g = rng.random((max(2, cells * h // max(h, w)) + 1, max(2, cells * w // max(h, w)) + 1)).astype(np.float32)
        out += np.asarray(Image.fromarray(g).resize((w, h), Image.BICUBIC)) * amp
        total += amp
        amp *= 0.55
    out /= total
    return (out - out.min()) / max(out.max() - out.min(), 1e-6)


def normal_from(height: np.ndarray, strength: float) -> np.ndarray:
    """Нормали OpenGL (зелёный — вверх по текстуре) из высоты 0..1."""
    gy, gx = np.gradient(height.astype(np.float32))
    n = np.dstack([-gx * strength, gy * strength, np.ones_like(height)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


def save_rgb(arr: np.ndarray, name: str) -> None:
    Image.fromarray((np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)).save(OUT / name)
    print("car_clues:", name, arr.shape[1], "×", arr.shape[0])


def srgb(c: tuple[float, float, float]) -> np.ndarray:
    return np.array(c, np.float32)


def mask_rect(key: str, w: int, h: int) -> np.ndarray:
    """Маска владельца 0..1, обрезана вплотную по содержимому и растянута в w × h (капля с хвостом — хвост вдоль w)."""
    a = np.asarray(Image.open(USED[key]).convert("L"), dtype=np.float32) / 255.0
    ys, xs = np.nonzero(a > 0.06)
    a = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS), dtype=np.float32) / 255.0


def paste(canvas: np.ndarray, m: np.ndarray, x: int, y: int) -> None:
    h, w = m.shape
    canvas[y:y + h, x:x + w] = np.maximum(canvas[y:y + h, x:x + w], m)


# --- пятно: масло с антифризом ----------------------------------------------------------------------------------
def coolant_stain() -> None:
    """Владелец 2026-10-19: «почти чёрное, глянцевое, с подтёками, контрастнее». Лужа — «Масло_01_Тонкая_плёнка», от неё
    по уклону к +u два подтёка — «Масло_05_Капля_размазанная», вокруг капли — «Масло_07_Полупрозрачные_пятна»; бетон вокруг
    пропитан шире лужи, по краю пропитки — сиреневый налёт антифриза."""
    n = 1024
    body = np.zeros((n, n), np.float32)
    paste(body, mask("stain", 640), 40, 190)
    runs = np.zeros((n, n), np.float32)
    paste(runs, mask_rect("run", 600, 190), 400, 400)
    paste(runs, mask_rect("run", 430, 130)[::-1], 430, 590)
    drips = mask("drips", n) * 0.8
    # лужа целиком: просветы маски внутри залиты — середина самая толстая и тёмная
    solid = ndimage.binary_fill_holes(ndimage.binary_closing(body > 0.08, iterations=6))
    body = np.maximum(body, ndimage.gaussian_filter(solid.astype(np.float32), 3.0) * 0.85)
    core = ndimage.gaussian_filter(np.maximum(body, runs), 1.0)
    reach = ndimage.gaussian_filter((core > 0.1).astype(np.float32), 40)
    drips *= np.clip(1.0 - reach * 3.0, 0, 1) * np.clip(reach * 6.0, 0, 1)         # капли — рядом с лужей, не на ней
    t = np.clip((np.maximum(core, ndimage.gaussian_filter(drips, 1.0)) - 0.06) / 0.45, 0, 1)
    soaked = np.clip(ndimage.gaussian_filter((t > 0.05).astype(np.float32), 14) * 1.6, 0, 1)
    grain = fbm((n, n), 4, 24)
    oil = srgb((0.014, 0.012, 0.011))                                             # толстый слой — почти чёрный
    thin = srgb((0.045, 0.038, 0.034))
    halo = srgb((0.10, 0.085, 0.09))                                              # пропитанный бетон, чуть в сирень
    k = t[..., None] ** 0.6
    col = np.where(t[..., None] > 0.02, thin * (1 - k) + oil * k, halo)
    # радужная плёнка на тонком краю
    hue = fbm((n, n), 3, 10) * 6.283
    film = np.clip(t * (1 - t) * 4.0, 0, 1)[..., None] * 0.035
    col = col + film * np.dstack([np.sin(hue), np.sin(hue + 2.1), np.sin(hue + 4.2)])
    col = col * (0.9 + 0.2 * grain[..., None])
    alpha = np.clip(np.maximum(soaked * 0.55, t * 1.4), 0, 0.97)
    save_rgb(np.dstack([col, alpha]), "coolant_stain_albedo.png")
    rough = np.where(t > 0.02, 0.05 + 0.2 * (1 - t) + 0.05 * grain, 0.72)        # лужа блестит, пропитка — матовая
    save_rgb(np.dstack([np.ones_like(rough), rough, np.zeros_like(rough)]), "coolant_stain_orm.png")
    height = ndimage.gaussian_filter(np.clip(t * 1.5, 0, 1), 2.0)                 # мениск по краю лужи
    save_rgb(normal_from(height, 3.0), "coolant_stain_normal.png")


# --- следы шин -----------------------------------------------------------------------------------------------
def tire_drag() -> None:
    """Маски владельца «Следы заблокированных шин»: машину тащили на заблокированных колёсах. Маска — обе колеи целиком,
    квадрат; декаль растягивает её так, чтобы колея совпала с купе (1,66 м), — в сцене. Резина почти чёрная (владелец:
    «почти чёрными, заметно»)."""
    n = 1024
    for key in ("drag_06", "drag_05", "drag_03"):
        a = np.asarray(Image.open(USED[key]).convert("L").resize((n, n), Image.LANCZOS), dtype=np.float32) / 255.0
        a = np.clip((a - 0.05) * 1.8, 0, 1)
        a = np.clip(ndimage.gaussian_filter(a, 0.6), 0, 0.96)
        col = srgb((0.012, 0.012, 0.012)) * (0.8 + 0.4 * fbm((n, n), 3, 16))[..., None]
        save_rgb(np.dstack([col, a]), f"tire_{key}_albedo.png")


# --- номера ---------------------------------------------------------------------------------------------------
def plate(code: str, l1: str, digits: str, l2: str, region: str) -> None:
    W, H = 1040, 224
    paper = Image.new("RGB", (W, H), (236, 236, 232))
    d = ImageDraw.Draw(paper)
    raised = Image.new("L", (W, H), 0)
    r = ImageDraw.Draw(raised)
    for dd in (d, r):
        dd.rounded_rectangle([3, 3, W - 4, H - 4], radius=16, outline=(18, 18, 18) if dd is d else 255, width=7)
    x_reg = int(W * 0.765)
    for dd in (d, r):
        dd.line([(x_reg, 10), (x_reg, H - 10)], fill=(18, 18, 18) if dd is d else 255, width=6)
    fx0, fy0, fw, fh = x_reg + 92, H - 58, 44, 30
    for k, col in enumerate(((245, 245, 245), (0, 57, 166), (213, 43, 30))):
        d.rectangle([fx0, fy0 + k * fh // 3, fx0 + fw, fy0 + (k + 1) * fh // 3], fill=col)
    d.rectangle([fx0, fy0, fx0 + fw, fy0 + fh], outline=(60, 60, 60), width=1)
    d.text((x_reg + 26, H - 60), "RUS", font=font("arialbd.ttf", 28), fill=(18, 18, 18))
    big, small, reg = font("bahnschrift.ttf", 168), font("bahnschrift.ttf", 128), font("bahnschrift.ttf", 112)
    base = 186                                                                    # общая нижняя линия знаков
    x = 64
    for txt, f in ((l1, small), (digits, big), (l2, small)):
        for ch in txt:
            bb = f.getbbox(ch)
            for dd in (d, r):
                dd.text((x - bb[0], base - bb[3]), ch, font=f, fill=(16, 16, 16) if dd is d else 255)
            x += (bb[2] - bb[0]) + 14
        x += 22
    bb = reg.getbbox(region)
    rx = x_reg + (W - x_reg - (bb[2] - bb[0])) // 2 - bb[0]
    for dd in (d, r):
        dd.text((rx, 118 - bb[3]), region, font=reg, fill=(16, 16, 16) if dd is d else 255)
    for cx in (int(W * 0.12), int(W * 0.66)):
        d.ellipse([cx - 9, 16, cx + 9, 34], fill=(150, 150, 150), outline=(90, 90, 90))
    col = np.asarray(paper, np.float32) / 255.0
    # грязь скупки: пыль пятнами, потёки снизу, следы пальцев по краю
    dirt = fbm((H, W), 5, 6) ** 2.2 * 0.45 + np.clip(np.linspace(-0.3, 0.35, H), 0, 1)[:, None] * fbm((H, W), 3, 30) * 0.6
    col = col * (1 - dirt[..., None] * 0.55) + srgb((0.30, 0.26, 0.21)) * dirt[..., None] * 0.55
    save_rgb(col, f"plate_{code}_albedo.png")
    hgt = ndimage.gaussian_filter(np.asarray(raised, np.float32) / 255.0, 2.2)
    save_rgb(normal_from(hgt + fbm((H, W), 3, 40) * 0.05, 9.0), f"plate_{code}_normal.png")


# --- накладная и бирка ----------------------------------------------------------------------------------------
def invoice() -> None:
    W, H = 840, 1188                                                              # А4, 4 пикс/мм
    im = Image.new("RGB", (W, H), (233, 230, 219))
    d = ImageDraw.Draw(im)
    f_head, f_txt, f_small = font("arialbd.ttf", 30), font("arial.ttf", 21), font("arial.ttf", 17)
    d.text((70, 70), "ТОВАРНАЯ НАКЛАДНАЯ № 418", font=f_head, fill=(25, 25, 30))
    d.text((70, 118), "Грузоотправитель: пункт приёма запчастей «АЗС-12», бокс 2", font=f_txt, fill=(30, 30, 35))
    d.text((70, 150), "Грузополучатель: ремонтные площадки ЮР", font=f_txt, fill=(30, 30, 35))
    d.text((70, 182), "Партия:", font=f_txt, fill=(30, 30, 35))
    d.rectangle([160, 176, 330, 214], outline=(30, 30, 35), width=2)
    d.text((176, 180), "ЮР / 8", font=font("arialbd.ttf", 26), fill=(20, 20, 25))
    cols = [70, 130, 560, 660, 770]
    rows = ["Колесо R19 в сборе", "Радиатор охлаждения с патрубками", "Аккумулятор 70 А·ч", "Фара левая", "Блок предохранителей",
            "Накладка порога, хром", "Номерной знак, 2 шт."]
    y0, rh = 250, 46
    for k in range(len(rows) + 2):
        d.line([(cols[0], y0 + k * rh), (cols[-1], y0 + k * rh)], fill=(40, 40, 45), width=2)
    for x in cols:
        d.line([(x, y0), (x, y0 + (len(rows) + 1) * rh)], fill=(40, 40, 45), width=2)
    for x, t in zip(cols, ("№", "Наименование", "Кол.", "Ед.")):
        d.text((x + 10, y0 + 12), t, font=f_small, fill=(30, 30, 35))
    for i, t in enumerate(rows):
        y = y0 + (i + 1) * rh + 12
        d.text((cols[0] + 14, y), str(i + 1), font=f_txt, fill=(30, 30, 35))
        d.text((cols[1] + 10, y), t, font=f_txt, fill=(30, 30, 35))
        d.text((cols[2] + 30, y), "1" if i < 6 else "2", font=f_txt, fill=(30, 30, 35))
        d.text((cols[3] + 22, y), "шт", font=f_txt, fill=(30, 30, 35))
    yy = y0 + (len(rows) + 1) * rh + 60
    d.text((70, yy), "Сдал ____________        Принял ____________", font=f_txt, fill=(30, 30, 35))
    d.text((70, yy + 44), "Номер кузова и VIN не указаны", font=f_small, fill=(70, 70, 75))
    # подпись и штамп ручкой / синей краской
    pen = Image.new("L", (W, H), 0)
    p = ImageDraw.Draw(pen)
    pts = [(190 + i * 9, yy + 14 - 10 * np.sin(i * 0.9) + rng.normal(0, 1.5)) for i in range(18)]
    p.line(pts, fill=255, width=3)
    p.text((520, yy - 6), "ЮР/8", font=font("segoepr.ttf", 34), fill=255)
    stamp = Image.new("L", (W, H), 0)
    s = ImageDraw.Draw(stamp)
    s.ellipse([560, yy + 70, 760, yy + 270], outline=255, width=7)
    s.ellipse([590, yy + 100, 730, yy + 240], outline=255, width=3)
    s.text((598, yy + 152), "ПРИЁМ", font=font("arialbd.ttf", 30), fill=255)
    stamp = stamp.rotate(-14, center=(660, yy + 170))
    a = np.asarray(im, np.float32) / 255.0
    pa = np.asarray(pen, np.float32)[..., None] / 255.0
    sa = (np.asarray(stamp, np.float32) / 255.0 * np.clip(fbm((H, W), 3, 40) * 1.4, 0, 1))[..., None] * 0.8
    a = a * (1 - pa) + srgb((0.08, 0.12, 0.35)) * pa
    a = a * (1 - sa) + srgb((0.25, 0.32, 0.62)) * sa
    # бумага: желтизна, грязные пальцы, кольцо от кружки, сгибы
    stain = fbm((H, W), 4, 5) ** 2.5 * 0.35
    a = a * (1 - stain[..., None] * 0.4) + srgb((0.55, 0.46, 0.32)) * stain[..., None] * 0.4
    folds = np.zeros((H, W), np.float32)
    folds[H // 3 - 1:H // 3 + 2, :] = 1.0
    folds[2 * H // 3 - 1:2 * H // 3 + 2, :] = 1.0
    crumple = fbm((H, W), 5, 8)
    a *= (0.95 + 0.05 * crumple)[..., None]
    a *= (1 - ndimage.gaussian_filter(folds, 2.0) * 0.08)[..., None]
    save_rgb(a, "invoice_albedo.png")
    save_rgb(normal_from(crumple * 0.6 + ndimage.gaussian_filter(folds, 3.0) * 0.5, 7.0), "invoice_normal.png")


def tag() -> None:
    W, H = 240, 400                                                               # 60 × 100 мм, 4 пикс/мм
    shape = Image.new("L", (W, H), 0)
    s = ImageDraw.Draw(shape)
    s.polygon([(40, 0), (W - 40, 0), (W, 40), (W, H), (0, H), (0, 40)], fill=255)
    s.ellipse([W // 2 - 22, 28, W // 2 + 22, 72], fill=0)                       # отверстие
    ring = Image.new("L", (W, H), 0)
    ImageDraw.Draw(ring).ellipse([W // 2 - 34, 16, W // 2 + 34, 84], fill=255)
    ImageDraw.Draw(ring).ellipse([W // 2 - 22, 28, W // 2 + 22, 72], fill=0)
    ink = Image.new("L", (W, H), 0)
    k = ImageDraw.Draw(ink)
    k.text((48, 120), "ПАРТИЯ", font=font("arialbd.ttf", 30), fill=255)
    marker = font("segoeprb.ttf", 50)
    bb = marker.getbbox("ЮР / 8")
    k.text(((W - (bb[2] - bb[0])) // 2 - bb[0], 200), "ЮР / 8", font=marker, fill=255)
    kraft = srgb((0.55, 0.38, 0.22)) * (0.85 + 0.3 * fbm((H, W), 4, 12))[..., None]
    rg = np.asarray(ring, np.float32)[..., None] / 255.0
    col = kraft * (1 - rg) + srgb((0.70, 0.68, 0.62)) * rg
    ia = np.asarray(ink, np.float32)[..., None] / 255.0
    col = col * (1 - ia) + srgb((0.02, 0.02, 0.025)) * ia
    alpha = np.asarray(shape, np.float32) / 255.0
    save_rgb(np.dstack([col, alpha]), "tag_yur8_albedo.png")


coolant_stain()
tire_drag()
for p in PLATES:
    plate(*p)
invoice()
tag()
record = {k: {"path": str(v), "sha256": hashlib.sha256(v.read_bytes()).hexdigest()} for k, v in USED.items()}
(OUT / "masks_used.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
print("car_clues: готово")
