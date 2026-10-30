# AR-15 «ГРАНЬ-15», этап 2 (износ): фото-маски CC0 из библиотеки владельца → рабочие маски Painter (латинский путь,
# уровни). Маски ambientCG тусклые (отпечатки в среднем 0,26, разводы 0,2) и густые: как есть они пропускали четверть
# эффекта, а густые отпечатки и мазки кистью давали «мрамор» по всей рукояти (проба 30.10). Здесь — растяжка уровней,
# порог (редкие отдельные отпечатки, редкие масляные мазки) и размытие (полировка — мягкие пятна, а не штрихи).
# Здесь же — зоны рукояти из tools/ar15/wear_zones.py (16 бит RGBA) в 8-битные ч/б для Painter и их объединения:
# hand (ладонь, пальцы, большой), prints (пальцы + большой), polish (ладонь + большой), hand_edges (hand без площадок
# насечки).
#   python -X utf8 tools/ar15/wear_masks.py
# Пишет <имя>.png (ч/б 8 бит) в _asset_src/ar15/tex/wear/masks, рядом — license.txt с источниками;
# grip_zone_<зона>_L.png — в _asset_src/ar15/tex/wear.
import os

import numpy as np
from PIL import Image, ImageFilter

SRC = "E:/Models Blender/Маски_АЛЬФА/50_Скачанные_CC0_ambientCG_ShareTextures"
WEAR = "E:/Games/RING-godot/_asset_src/ar15/tex/wear"
OUT = WEAR + "/masks"
ZONES = ("palm", "fingers", "thumb", "base", "ribs", "rib_dirt", "rib_dust", "stip_gloss", "stip_dirt", "panels")
UNIONS = {"hand": ("palm", "fingers", "thumb"), "prints": ("fingers", "thumb"), "polish": ("palm", "thumb")}
SIZE = 2048

# имя: (набор, файл, нижний и верхний перцентиль уровней, размытие пикс., пол — минимум после уровней)
MASKS = {
    # отдельные отпечатки: только самые плотные из густого поля
    "prints_a": ("Fingerprints002_2K-PNG", "Fingerprints002_2K-PNG_Opacity.png", 72.0, 99.6, 0, 0.0),
    "prints_b": ("Fingerprints007_2K-PNG", "Fingerprints007_2K-PNG_Opacity.png", 85.0, 99.8, 0, 0.0),
    # масляные мазки ладони — редкие штрихи
    "smear_oil": ("Smear002_2K-JPG", "Smear002_2K-JPG_Roughness.jpg", 78.0, 99.6, 2, 0.0),
    # полировка хватом — мягкие пятна, зона закрыта не меньше чем наполовину
    "polish_var": ("Smear008_2K-PNG", "Smear008_2K-PNG_Roughness.png", 5.0, 95.0, 14, 0.45),
    # пылинки и крапинки грязи
    "dust_specks": ("SurfaceImperfections007_2K-PNG", "SurfaceImperfections007_2K-PNG_Opacity.png", 0.0, 99.5, 0, 0.0),
    # царапины торца
    "scratches": ("Scratches002_2K-PNG", "Scratches002_2K-PNG_Opacity.png", 0.0, 99.7, 0, 0.0),
    # грязь в углах у рёбрышек — рваный гранж (ShareTextures dirt_5), не сплошная обводка
    "grime": ("dirt_5", "dirt_5-2K.png", 20.0, 99.5, 0, 0.3),
    # пыль в углах — частицы (ShareTextures dirt_1)
    "dust_grain": ("dirt_1-1", "dirt_1-2K.png", 30.0, 99.7, 0, 0.2),
}
SOURCES = {"ambientCG": "https://ambientcg.com", "ShareTextures": "https://www.sharetextures.com"}


def find(name, fname):
    for d in (os.path.join(SRC, name), SRC):
        p = os.path.join(d, fname)
        if os.path.exists(p):
            return p
    for root, _, files in os.walk(SRC):
        if fname in files:
            return os.path.join(root, fname)
    raise FileNotFoundError(fname)


def prepare(key, spec):
    name, fname, lo, hi, blur, floor = spec
    im = Image.open(find(name, fname)).convert("L")
    if im.size != (SIZE, SIZE):
        im = im.resize((SIZE, SIZE), Image.LANCZOS)
    if blur:
        im = im.filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32) / 255.0
    a0, a1 = np.percentile(a, [lo, hi])
    a = np.clip((a - a0) / max(a1 - a0, 1e-6), 0.0, 1.0)
    a = floor + (1.0 - floor) * a
    Image.fromarray((a * 255.0 + 0.5).astype(np.uint8)).save(os.path.join(OUT, key + ".png"))
    return f"{key}: {fname} — среднее {a.mean():.2f}, доля > 0,5 {(a > 0.5).mean():.2f}"


def zones():
    z = {}
    for k in ZONES:
        a = np.asarray(Image.open(f"{WEAR}/grip_zone_{k}.png")).astype(np.float32)
        a = a[..., 0] if a.ndim == 3 else a
        z[k] = a / (65535.0 if a.max() > 255.0 else 255.0)
    for k, parts in UNIONS.items():
        z[k] = np.maximum.reduce([z[q] for q in parts])
    # кромки и рёбра в зоне руки — без площадок насечки: пупырышки — своими слоями (слева только большой палец)
    z["hand_edges"] = z["hand"] * (1.0 - z["panels"])
    for k, a in z.items():
        Image.fromarray((np.clip(a, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)).save(f"{WEAR}/grip_zone_{k}_L.png")
    return "зоны: " + ", ".join(z)


def main():
    os.makedirs(OUT, exist_ok=True)
    print(zones())
    for k, spec in MASKS.items():
        print(prepare(k, spec))
    sets = sorted({s[0] for s in MASKS.values()})
    with open(os.path.join(OUT, "license.txt"), "w", encoding="utf-8", newline="\n") as f:
        for src, url in SOURCES.items():
            own = [n for n in sets if n.startswith("dirt") == (src == "ShareTextures")]
            f.write(f"CC0 1.0 — {src} ({url}), наборы: {', '.join(own)}.\n")
        f.write("Скачаны в " + SRC + " (00_ЛИЦЕНЗИЯ_и_источники.txt); здесь — уровни, порог, размытие "
                "(tools/ar15/wear_masks.py).\n")


if __name__ == "__main__":
    main()
