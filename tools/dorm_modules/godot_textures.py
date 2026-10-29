"""Карты материалов общежития v03 → Godot: assets/textures/dorm_v3 (+ .import), шум износа по миру.

  python -X utf8 tools/dorm_modules/godot_textures.py

Берёт карты комплекта модулей (gen_paint_v3 / gen_plaster_v3 / gen_floor_v3 / gen_tiles_v3 → textures/*_v3) и пишет:
- поля отслоения (E краски, побелки, штукатурки) — EXR половинной точности без сжатия: расстояние до кромки
  считается из них в миллиметрах, 8 бит дали бы ступени на загибах кромки;
- маски с тонкими трещинами и швами — 4K без потерь (PNG), остальные маски и нормали — 2K без потерь (PNG),
  фотосканы — WebP с потерями; в игре — BC7 / BC5 (нормали), EXR — без сжатия;
- dorm_wear_noise — четыре гладких бесшовных шума (тайл 8 м): износ по месту, «плохие места», проход.
Имена файлов — как имена параметров шейдеров src/blockout/dorm_v3 (без суффикса _tex).
"""
import os
import sys
from pathlib import Path

os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
import cv2  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KIT = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/textures")
OUT = ROOT / "assets/textures/dorm_v3"
RES = "res://assets/textures/dorm_v3"

# имя в игре: (папка, файл, каналы источника → в игру, размер, вид) ; вид: data | normal | color | field
MAPS = {
    # краска
    "paint_peel_e": ("paint_v3", "peel.png", (0,), 2048, "field"),
    "paint_peel_dir": ("paint_v3", "peel.png", (1, 2, 3), 2048, "data"),
    "paint_masks": ("paint_v3", "paint_masks.png", (0, 1, 2, 3), 4096, "data"),
    "paint_tone": ("paint_v3", "paint_tone.png", (0, 1, 2, 3), 2048, "data"),
    "paint_normal": ("paint_v3", "paint_normal.png", (0, 1, 2), 4096, "normal"),
    "paint_cup_normal": ("paint_v3", "cup_normal.png", (0, 1, 2), 2048, "normal"),
    "paint_under": ("paint_v3", "under_masks.png", (0, 1, 2, 3), 2048, "data"),
    "paint_under_cells": ("paint_v3", "under_cells.png", (0, 1, 2, 3), 2048, "data"),
    "plaster_albedo": ("paint_v3", "plaster_albedo.jpg", (0, 1, 2), 2048, "color"),
    "plaster_normal": ("paint_v3", "plaster_normal.jpg", (0, 1, 2), 2048, "normal"),
    "plaster_rough": ("paint_v3", "plaster_rough.jpg", (0,), 1024, "data"),
    # побелка, штукатурка, кирпич
    "wash_peel_e": ("plaster_v3", "wash_peel.png", (0,), 2048, "field"),
    "wash_peel_dir": ("plaster_v3", "wash_peel.png", (1, 2, 3), 2048, "data"),
    "loss_peel_e": ("plaster_v3", "loss_peel.png", (0,), 1024, "field"),
    "loss_peel_dir": ("plaster_v3", "loss_peel.png", (1, 2, 3), 1024, "data"),
    "wash_masks": ("plaster_v3", "wash_masks.png", (0, 1, 2, 3), 4096, "data"),
    "wash_tone": ("plaster_v3", "wash_tone.png", (0, 1, 2, 3), 2048, "data"),
    "loss_masks": ("plaster_v3", "loss_masks.png", (0, 1, 2, 3), 2048, "data"),
    "wash_normal": ("plaster_v3", "wash_normal.png", (0, 1, 2), 2048, "normal"),
    "wash_cup_normal": ("plaster_v3", "wash_cup_normal.png", (0, 1, 2), 2048, "normal"),
    "brick_albedo": ("plaster_v3", "brick_albedo.jpg", (0, 1, 2), 2048, "color"),
    "brick_normal": ("plaster_v3", "brick_normal.jpg", (0, 1, 2), 2048, "normal"),
    "brick_rough": ("plaster_v3", "brick_rough.jpg", (0,), 1024, "data"),
    # паркет
    "floor_wood": ("floor_v3", "floor_wood.png", (0, 1, 2), 4096, "color"),
    "floor_normal": ("floor_v3", "floor_normal.png", (0, 1, 2), 4096, "normal"),
    "floor_masks": ("floor_v3", "floor_masks.png", (0, 1, 2, 3), 4096, "data"),
    "floor_wear": ("floor_v3", "floor_wear.png", (0, 1, 2, 3), 2048, "data"),
    "floor_mastic": ("floor_v3", "floor_mastic.png", (0, 1, 2, 3), 2048, "data"),
    "floor_break": ("floor_v3", "floor_break.png", (0, 1, 2, 3), 2048, "data"),
    "floor_break_normal": ("floor_v3", "floor_break_normal.png", (0, 1, 2), 2048, "normal"),
    # крашеное дерево модулей (ambientCG PaintedWood008A, CC0) — по развёртке модулей; «@папка» — _asset_src/dorm_textures
    "painted_wood_albedo": ("@PaintedWood008A", "PaintedWood008A_2K-JPG_Color.jpg", (0, 1, 2), 2048, "color"),
    "painted_wood_rough": ("@PaintedWood008A", "PaintedWood008A_2K-JPG_Roughness.jpg", (0,), 2048, "data"),
    "painted_wood_normal": ("@PaintedWood008A", "PaintedWood008A_2K-JPG_NormalGL.jpg", (0, 1, 2), 2048, "normal"),
    "painted_wood_ao": ("@PaintedWood008A", "PaintedWood008A_2K-JPG_AmbientOcclusion.jpg", (0,), 2048, "data"),
    # мозаичные ступени и площадки лестницы (ambientCG Terrazzo005, CC0) — по миру, шаг 0,5 м
    "terrazzo_albedo": ("@Terrazzo005", "Terrazzo005_2K-JPG_Color.jpg", (0, 1, 2), 2048, "color"),
    "terrazzo_rough": ("@Terrazzo005", "Terrazzo005_2K-JPG_Roughness.jpg", (0,), 1024, "data"),
    "terrazzo_normal": ("@Terrazzo005", "Terrazzo005_2K-JPG_NormalGL.jpg", (0, 1, 2), 2048, "normal"),
    # плитка
    "tile_masks": ("tiles_v3", "tile_masks.png", (0, 1, 2, 3), 4096, "data"),
    "tile_normal": ("tiles_v3", "tile_normal.png", (0, 1, 2), 2048, "normal"),
    "tile_tone": ("tiles_v3", "tile_tone.png", (0, 1, 2, 3), 2048, "data"),
    "tile_glue": ("tiles_v3", "tile_glue.png", (0, 1, 2, 3), 2048, "data"),
}

TEX_IMPORT = """[remap]

importer="texture"
type="CompressedTexture2D"

[deps]

source_file="{src}"

[params]

compress/mode={mode}
compress/high_quality=true
compress/lossy_quality=0.7
compress/hdr_compression=0
compress/normal_map={nm}
compress/channel_pack=0
mipmaps/generate=true
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
"""


def load(path: Path) -> np.ndarray:
    """Каналы в порядке RGBA, float 0…1 (8 и 16 бит)."""
    a = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if a is None:
        raise FileNotFoundError(path)
    scale = 65535.0 if a.dtype == np.uint16 else 255.0
    a = a.astype(np.float32) / scale
    if a.ndim == 2:
        return a[..., None]
    if a.shape[2] == 3:
        return a[..., ::-1]
    return np.concatenate([a[..., 2::-1], a[..., 3:]], axis=-1)


def resize(a: np.ndarray, size: int) -> np.ndarray:
    if a.shape[0] == size:
        return a
    out = cv2.resize(a, (size, size), interpolation=cv2.INTER_AREA)
    return out if out.ndim == 3 else out[..., None]


def write_import(dst: Path, kind: str) -> None:
    imp = dst.with_name(dst.name + ".import")
    mode = 0 if kind == "field" else 2
    text = TEX_IMPORT.format(src=f"{RES}/{dst.name}", mode=mode, nm=1 if kind == "normal" else 0)
    if imp.exists():
        # готовый .import хранит uid и путь импорта — меняем только параметры
        old = imp.read_text(encoding="utf-8")
        head = old.split("[params]")[0]
        imp.write_text(head + "[params]" + text.split("[params]")[1], encoding="utf-8", newline="\n")
    else:
        imp.write_text(text, encoding="utf-8", newline="\n")


SCANS = ROOT / "_asset_src/dorm_textures"


def save(name: str, folder: str, file: str, chans: tuple, size: int, kind: str) -> Path:
    src = SCANS / folder[1:] / file if folder.startswith("@") else KIT / folder / file
    a = resize(load(src), size)[..., list(chans)]
    if kind == "field":
        dst = OUT / f"{name}.exr"
        cv2.imwrite(str(dst), a[..., 0].astype(np.float32), [cv2.IMWRITE_EXR_TYPE, cv2.IMWRITE_EXR_TYPE_HALF])
    else:
        # Данные и нормали — PNG: WebP «без потерь» выбрасывает цвет под нулевой альфой (маски с альфой портятся).
        dst = OUT / (f"{name}.webp" if kind == "color" else f"{name}.png")
        u8 = (np.clip(a, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        bgr = u8[..., ::-1] if u8.shape[2] == 3 else np.concatenate([u8[..., 2::-1], u8[..., 3:]], axis=-1)
        if kind == "color":
            cv2.imwrite(str(dst), bgr, [cv2.IMWRITE_WEBP_QUALITY, 92])
        else:
            cv2.imwrite(str(dst), bgr, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    write_import(dst, kind)
    return dst


def wear_noise(n: int = 1024, tile_m: float = 8.0, seed: int = 31) -> Path:
    """Четыре гладких бесшовных шума (тайл 8 м): R ~3 м — износ по месту, G ~1 м, B ~0,5 м — пятна,
    A ~1,6 м — «плохие места» плитки. Среднее 0,5, разброс как у шума Blender (σ ≈ 0,1)."""
    rng = np.random.default_rng(seed)
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.rfftfreq(n)[None, :]
    px_m = n / tile_m
    chans = []
    for sigma_m in (0.9, 0.3, 0.15, 0.45):
        w = rng.standard_normal((n, n))
        k = np.exp(-2.0 * np.pi ** 2 * (sigma_m * px_m) ** 2 * (fx ** 2 + fy ** 2))
        a = np.fft.irfft2(np.fft.rfft2(w) * k, s=(n, n))
        a = (a - a.mean()) / (a.std() + 1e-9)
        chans.append(np.clip(0.5 + 0.1 * a, 0, 1))
    u8 = (np.stack(chans, -1) * 255 + 0.5).astype(np.uint8)
    dst = OUT / "dorm_wear_noise.png"
    cv2.imwrite(str(dst), np.concatenate([u8[..., 2::-1], u8[..., 3:]], axis=-1), [cv2.IMWRITE_PNG_COMPRESSION, 9])
    write_import(dst, "data")
    return dst


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    only = set(sys.argv[1:])
    total = 0
    for name, (folder, file, chans, size, kind) in MAPS.items():
        if only and name not in only:
            continue
        dst = save(name, folder, file, chans, size, kind)
        total += dst.stat().st_size
        print(f"{name:20s} {size:5d} {kind:6s} {dst.stat().st_size / 1e6:6.1f} МБ")
    if not only or "dorm_wear_noise" in only:
        total += wear_noise().stat().st_size
    print(f"всего {total / 1e6:.0f} МБ → {OUT}")


if __name__ == "__main__":
    main()
