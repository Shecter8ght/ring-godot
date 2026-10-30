"""Декали общежития из альфа-масок владельца (E:/Models Blender/Маски_АЛЬФА, светлый рисунок на чёрном):
старая засохшая кровь, грязь, пыль, копоть → assets/textures/dorm_decals/<имя>_albedo.png (RGBA),
_normal.png (OpenGL, рельеф корки и наплывов), _orm.png (R — AO, G — шероховатость, B — металл).

  python -X utf8 tools/dorm_modules/gen_dorm_decals.py [имя …]

Маски не меняются; толщина слоя — яркость маски, сглаженная. Цвет крови — давно засохшая: бурая, у толстых мест почти
чёрная и с лёгким блеском корки, тонкие — светлее и прозрачнее. Расстановка — data/blockouts/dorm_decals.json.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MASKS = Path(r"E:\Models Blender\Маски_АЛЬФА")
OUT = ROOT / "assets/textures/dorm_decals"
SIZE = 1024

# имя: (маска, вид, повернуть на 90° раз)
DECALS = {
    "blood_splash": ("22_Кровь/Кровь_05_Локальный_всплеск.png", "blood", 0),
    "blood_smear": ("22_Кровь/Кровь_10_Дуговой_мазок.png", "blood", 0),
    "blood_runs": ("22_Кровь/Кровь_15_Короткие_потёки.png", "blood", 0),
    "blood_crust": ("22_Кровь/Кровь_11_Засохшая_корка.png", "blood", 0),
    "blood_edge": ("22_Кровь/Кровь_13_Высохший_край.png", "blood", 0),
    "blood_drops": ("22_Кровь/Кровь_04_Капли_разного_размера.png", "blood", 0),
    "blood_palm": ("22_Кровь/Кровь_20_Частичный_отпечаток_ладони.png", "blood", 0),
    "blood_fingers": ("22_Кровь/Кровь_19_Смазанные_пальцы.png", "blood", 0),
    "dirt_patches": ("04_Грязь_и_налёт/Грязь_пятнами_01.png", "dirt", 0),
    "dirt_grain": ("04_Грязь_и_налёт/Грязь_зернистая_плотная_01.png", "dirt", 0),
    "dust_patches": ("03_Пыль_и_частицы/Пыль_пятнами_01.png", "dust", 0),
    "dust_dense": ("03_Пыль_и_частицы/Пыль_плотная_с_частицами_01.png", "dust", 0),
    "soot_plume": ("21_Копоть_и_дымовой_налёт/Копоть_05_Дымовая_вуаль.png", "soot", 0),
    "soot_dense": ("21_Копоть_и_дымовой_налёт/Копоть_03_Плотные_очаги.png", "soot", 0),
    "grime_wipe": ("06_Разводы_и_следы_протирания/Протирание_дугами_с_грязью_01.png", "dirt", 0),
}

# вид: (цвет тонкого слоя, цвет толстого — sRGB 0..1, порог, насыщение альфы, шероховатость тонкого / толстого, рельеф)
KINDS = {
    "blood": ((0.30, 0.10, 0.07), (0.09, 0.025, 0.02), 0.07, 0.45, 0.88, 0.42, 3.0),
    "dirt": ((0.30, 0.25, 0.18), (0.16, 0.12, 0.08), 0.06, 0.55, 0.95, 0.85, 1.5),
    "dust": ((0.58, 0.55, 0.50), (0.48, 0.45, 0.40), 0.05, 0.75, 1.0, 1.0, 0.6),
    "soot": ((0.10, 0.09, 0.085), (0.02, 0.02, 0.02), 0.03, 0.30, 0.95, 0.9, 0.3),
}


IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="res://assets/textures/dorm_decals/{name}"

[params]

compress/mode=2
compress/high_quality=true
compress/lossy_quality=0.7
compress/hdr_compression=0
compress/normal_map={nm}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=true
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def write_import(dst: Path, normal: bool) -> None:
    imp = dst.with_name(dst.name + ".import")
    text = IMPORT.format(name=dst.name, nm=1 if normal else 2)
    if imp.exists():
        head = imp.read_text(encoding="utf-8").split("[params]")[0]
        text = head + "[params]" + text.split("[params]")[1]
    imp.write_text(text, encoding="utf-8", newline="\n")


def load_mask(path: Path, turns: int) -> np.ndarray:
    a = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if a is None:
        raise FileNotFoundError(path)
    a = cv2.resize(a, (SIZE, SIZE), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return np.rot90(a, turns).copy()


def build(name: str, file: str, kind: str, turns: int) -> None:
    thin, thick, lo, span, r_thin, r_thick, relief = KINDS[kind]
    m = load_mask(MASKS / file, turns)
    # фон масок слегка серый — порог; толщина — сглаженная яркость (корка толще в середине пятна)
    alpha = np.clip((m - lo) / span, 0.0, 1.0)
    alpha = alpha * alpha * (3 - 2 * alpha)
    if kind != "blood":
        # грязь, пыль, копоть заполняют маску до краёв — спад к краю, неровный по самой маске
        yy, xx = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32) / (SIZE - 1) * 2 - 1
        rr = np.sqrt(xx * xx + yy * yy) + (cv2.GaussianBlur(m, (0, 0), 40.0) - 0.3) * 0.5
        fade = np.clip((1.0 - rr) / 0.45, 0.0, 1.0)
        alpha *= fade * fade * (3 - 2 * fade)
    body = cv2.GaussianBlur(m, (0, 0), 3.0)
    t = np.clip((body - lo) / (span * 1.4), 0.0, 1.0)
    rgb = np.array(thin)[None, None, :] * (1 - t[..., None]) + np.array(thick)[None, None, :] * t[..., None]
    # мелкая неровность цвета из самой маски (без шума — только её рисунок)
    detail = cv2.GaussianBlur(m, (0, 0), 0.8) - cv2.GaussianBlur(m, (0, 0), 6.0)
    rgb = np.clip(rgb * (1.0 + detail[..., None] * 0.6), 0.0, 1.0)
    rgba = np.dstack([rgb, alpha])
    # рельеф: высота — толщина слоя
    h = cv2.GaussianBlur(alpha * (0.4 + 0.6 * t), (0, 0), 1.2) * relief
    dx = cv2.Sobel(h, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(h, cv2.CV_32F, 0, 1, ksize=3)
    n = np.dstack([-dx, dy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    normal = n * 0.5 + 0.5
    rough = r_thin * (1 - t) + r_thick * t
    orm = np.dstack([np.ones_like(h), rough, np.zeros_like(h)])
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix, img in (("albedo", rgba), ("normal", normal), ("orm", orm)):
        u8 = (np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)
        bgr = u8[..., [2, 1, 0, 3]] if u8.shape[2] == 4 else u8[..., ::-1]
        ok, buf = cv2.imencode(".png", bgr, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        dst = OUT / f"{name}_{suffix}.png"
        dst.write_bytes(buf.tobytes())
        write_import(dst, suffix == "normal")
    print(f"{name:14s} {kind:5s} покрытие {alpha.mean() * 100:5.1f} %")


def main() -> None:
    only = set(sys.argv[1:])
    for name, (file, kind, turns) in DECALS.items():
        if not only or name in only:
            build(name, file, kind, turns)


if __name__ == "__main__":
    main()
