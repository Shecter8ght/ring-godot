# -*- coding: utf-8 -*-
"""Опоры касс v01, отделка: производные фото-основ CC0 и рабочие копии масок владельца (повторяемо).

    python -X utf8 -I tools/loot_containers/counters_derive.py

Производные (в _asset_src/textures/<id>_<суффикс>/, license.txt с описанием изменений, CC0 сохраняется):
  Chipboard001_pale, Chipboard003_pale — сердечник ДСП: насыщенность ×0,38, яркость ×1,12 (светлая ДСП, не оранжевая OSB);
  Wood092_decor, Wood066_decor — печатный декор ЛДСП: серое (без розового), высокие частоты рисунка (вычтено размытие
      σ 48 пикс — нет продольных «досок» и пятен тона), контраст ×0,55 вокруг середины; цвет даёт плоский тон слоя под ним.
Маски (серые 8 бит ≤ 2K) → _asset_src/loot_containers/masks_v03 (там же лежат копии lc3_masks.py):
  Rubber07 «Тонкие риски», Rubber09 «Прерывистое трение» (18_Следы_резины_и_контакта владельца);
  SI014_soft — SurfaceImperfections014 (ambientCG, CC0) размыто σ 24 пикс и растянуто на весь диапазон: неоднородность
      тона краски крупными мягкими пятнами без мелкой «крупы» (у SI014 с поднятым контрастом панель читалась гранитом).
"""
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
TEX = ROOT / "_asset_src" / "textures"
MASKS = ROOT / "_asset_src" / "loot_containers" / "masks_v03"
OWN = Path("E:/Models Blender/Маски_АЛЬФА")


def _copy_rest(src: Path, dst: Path) -> None:
    for f in ("roughness_2k.jpg", "height_2k.jpg", "normal_2k.jpg", "ao_2k.jpg"):
        if (src / f).exists():
            shutil.copy(src / f, dst / f)


def _license(dst: Path, src_id: str, change: str, role: str) -> None:
    (dst / "license.txt").write_text(
        f"title: {dst.name} (производная {src_id}: {change})\nauthor: ambientCG (Lennart Demes)\nlicense: CC0 1.0\n"
        f"source: https://ambientcg.com/view?id={src_id}\nrole: {role}\n", encoding="utf-8", newline="\n")


def pale(src_id: str) -> None:
    src, dst = TEX / src_id, TEX / f"{src_id}_pale"
    dst.mkdir(exist_ok=True)
    im = Image.open(src / "color_2k.jpg").convert("RGB")
    im = ImageEnhance.Brightness(ImageEnhance.Color(im).enhance(0.38)).enhance(1.12)
    im.save(dst / "color_2k.jpg", quality=95)
    _copy_rest(src, dst)
    _license(dst, src_id, "насыщенность x0,38, яркость x1,12", "сердечник ДСП на сколах ЛДСП (counters_stacks.py)")


def decor(src_id: str, contrast: float = 0.55, sigma: float = 48.0) -> None:
    src, dst = TEX / src_id, TEX / f"{src_id}_decor"
    dst.mkdir(exist_ok=True)
    g = np.asarray(Image.open(src / "color_2k.jpg").convert("L")).astype(np.float32)
    low = np.asarray(Image.fromarray(g.astype(np.uint8)).filter(ImageFilter.GaussianBlur(sigma))).astype(np.float32)
    hp = g - low
    hp = hp / (np.percentile(np.abs(hp), 99) + 1e-3)
    out = np.clip(128 + hp * 128 * contrast, 0, 255).astype(np.uint8)
    Image.fromarray(out).convert("RGB").save(dst / "color_2k.jpg", quality=95)
    _copy_rest(src, dst)
    _license(dst, src_id, f"серое, высокие частоты (минус размытие σ {sigma:g} пикс), контраст x{contrast:g}",
             "печатный декор ЛДСП (counters_stacks.py)")


def masks() -> None:
    MASKS.mkdir(parents=True, exist_ok=True)
    for name, f in (("Rubber07", "Резина_07_Тонкие_риски.png"), ("Rubber09", "Резина_09_Прерывистое_трение.png")):
        im = Image.open(OWN / "18_Следы_резины_и_контакта" / f).convert("L")
        if max(im.size) > 2048:
            im = im.resize((2048, 2048), Image.LANCZOS)
        im.save(MASKS / f"{name}.png")


def soft_si014() -> None:
    a = np.asarray(Image.open(MASKS / "SI014.png").convert("L").filter(ImageFilter.GaussianBlur(24))).astype(np.float32)
    lo, hi = np.percentile(a, 2), np.percentile(a, 98)
    Image.fromarray(np.clip((a - lo) / max(hi - lo, 1) * 255, 0, 255).astype(np.uint8)).save(MASKS / "SI014_soft.png")


if __name__ == "__main__":
    pale("Chipboard001")
    pale("Chipboard003")
    decor("Wood092")
    decor("Wood066")
    masks()
    soft_si014()
    print("ok")
