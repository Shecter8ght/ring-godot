"""Подготовка фото-наборов CC0 и фото-масок для материалов дома 7 (system Python, numpy + PIL).
Из наборов _asset_src/textures/<id> делает albedo / rough / height (высота из карты нормалей — Пуассон по БПФ, если её нет),
копирует фото-маски владельца (Маски_АЛЬФА) под ASCII-именами, генерирует карту перфорации.
  python -X utf8 tools/prospekt_houses/prep_textures.py
"""
import os
import shutil
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "_asset_src", "textures")
OUT = "E:/Models Blender/ENVIRONMENT/RING_Prospekt_Houses/textures"
MASKS = "E:/Models Blender/Маски_АЛЬФА"

# id -> (папка, albedo, шероховатость (файл, канал или None), высота (файл, 'height'|'normal'), размер)
SETS = {
    "conc": ("concrete_wall_007", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 2048),
    "plaster": ("painted_plaster_wall", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 1024),
    "metal_dark": ("Metal063", "color_2k.jpg", ("roughness_2k.jpg", 0), ("height_2k.jpg", "height"), 1024),
    "metal_light": ("Metal052A", "color_2k.jpg", ("roughness_2k.jpg", 0), ("height_2k.jpg", "height"), 1024),
    "wood": ("plywood", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 1024),
    "fabric": ("Fabric034", "color_2k.jpg", ("roughness_2k.jpg", 0), ("height_2k.jpg", "height"), 1024),
    "tile": ("large_floor_tiles_02", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 1024),
    "soil": ("mud_forest", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 1024),
    "asphalt": ("asphalt_04", "albedo.jpg", ("arm.jpg", 1), ("height.jpg", "height"), 1024),
    "roof": ("tarred_gravel", "albedo.jpg", ("arm.jpg", 1), ("normal.jpg", "normal"), 1024),
}
MASK_FILES = {
    "m_marble": "04_Грязь_и_налёт/Грязь_пятнами_01.png",
    "m_grain": "04_Грязь_и_налёт/Грязь_зернистая_плотная_01.png",
    "m_plaque": "04_Грязь_и_налёт/Налёт_мелкими_пятнами_01.png",
    "m_streak": "08_Швы_панелей_и_потёки/Швы_панелей_с_потёками_01.png",
    "m_seam": "08_Швы_панелей_и_потёки/Швы_панелей_с_плотным_налётом_01.png",
    "m_smear": "06_Разводы_и_следы_протирания/Разводы_редкие_01.png",
    "m_wipe": "06_Разводы_и_следы_протирания/Протирание_по_диагонали_01.png",
    "m_crack": "14_Микротрещины_покрытия/Микротрещины_02_Редкая_сетка.png",
}


def height_from_normal(nrm):
    n = nrm[..., :3].astype(np.float32) / 127.5 - 1.0
    nz = np.maximum(n[..., 2], 0.2)
    gx = -n[..., 0] / nz
    gy = n[..., 1] / nz
    h, w = gx.shape
    kx = np.fft.fftfreq(w)[None, :] * 2 * np.pi
    ky = np.fft.fftfreq(h)[:, None] * 2 * np.pi
    den = kx ** 2 + ky ** 2
    den[0, 0] = 1.0
    H = (1j * kx * np.fft.fft2(gx) + 1j * ky * np.fft.fft2(gy)) / (-den)
    H[0, 0] = 0
    r = np.real(np.fft.ifft2(H))
    lo, hi = np.percentile(r, 1), np.percentile(r, 99)
    return np.clip((r - lo) / (hi - lo + 1e-9), 0, 1)


def save(a, p, mode="L"):
    Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).save(p, quality=90)


def main():
    os.makedirs(OUT + "/masks", exist_ok=True)
    for k, (folder, alb, rough, hgt, size) in SETS.items():
        d = os.path.join(SRC, folder)
        a = Image.open(os.path.join(d, alb)).convert("RGB").resize((size, size), Image.LANCZOS)
        a.save("%s/%s_albedo.jpg" % (OUT, k), quality=92)
        r = np.asarray(Image.open(os.path.join(d, rough[0])).convert("RGB").resize((size, size), Image.LANCZOS))[..., rough[1]] / 255.0
        save(r, "%s/%s_rough.jpg" % (OUT, k))
        himg = Image.open(os.path.join(d, hgt[0])).convert("RGB").resize((size, size), Image.LANCZOS)
        ha = np.asarray(himg)
        h = height_from_normal(ha) if hgt[1] == "normal" else ha[..., 0] / 255.0
        save(h, "%s/%s_height.jpg" % (OUT, k))
        print("set", k, folder)
    for k, rel in MASK_FILES.items():
        shutil.copyfile(os.path.join(MASKS, rel), "%s/masks/%s.png" % (OUT, k))
    # перфорация: шахматный шаг 24 мм, отверстия Ø 8–17 мм с вариацией, плитка 0,96 м; белое = металл, чёрное = дыра
    size, cells = 2048, 40
    px = size / cells
    rng = np.random.default_rng(11)
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    alpha = np.ones((size, size), np.float32)
    for j in range(cells):
        for i in range(cells):
            cx = (i + (0.5 if j % 2 else 0.0) + 0.5) * px
            cy = (j + 0.5) * px
            r = px * rng.uniform(0.17, 0.36)
            cx += rng.uniform(-0.04, 0.04) * px
            cy += rng.uniform(-0.04, 0.04) * px
            x0, x1 = int(cx - r - 2), int(cx + r + 2)
            y0, y1 = int(cy - r - 2), int(cy + r + 2)
            for ox in (-size, 0, size):
                xa, xb = max(0, x0 + ox), min(size, x1 + ox)
                if xb <= xa:
                    continue
                sub = (xx[y0:y1, xa:xb] - (cx + ox)) ** 2 + (yy[y0:y1, xa:xb] - cy) ** 2
                alpha[y0:y1, xa:xb] = np.minimum(alpha[y0:y1, xa:xb], np.clip((np.sqrt(sub) - r) / 1.5, 0, 1)) if y0 >= 0 and y1 <= size else alpha[y0:y1, xa:xb]
    Image.fromarray((alpha * 255).astype(np.uint8)).save(OUT + "/perf_alpha.png")
    print("perf ok")


main()
