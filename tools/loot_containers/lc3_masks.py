"""Маски износа владельца (E:/Models Blender/Маски_АЛЬФА) → рабочие копии для Painter: серые 8-бит не больше 2K
(4K-маски ShareTextures и десятки слоёв подряд на 4K-наборе давали «GPU Device lost» в Painter, 2026-11-13).
Копии — _asset_src/loot_containers/masks_v03/<имя>.png; имена те же, что в lc3_stacks.py и в asset-state.md.

  python -X utf8 tools/loot_containers/lc3_masks.py
"""
import glob
from pathlib import Path

from PIL import Image

OWN = Path("E:/Models Blender/Маски_АЛЬФА")
CC0 = OWN / "50_Скачанные_CC0_ambientCG_ShareTextures"
OUT = Path(__file__).resolve().parents[2] / "_asset_src" / "loot_containers" / "masks_v03"


def first(pattern: str) -> Path:
    return Path(glob.glob(str(CC0 / pattern))[0])


SRC = {
    "SI007": first("ambientCG/SurfaceImperfections007/*Opacity.png"),
    "SI012": first("ambientCG/SurfaceImperfections012/*Opacity.png"),
    "SI013": first("ambientCG/SurfaceImperfections013/*Opacity.png"),
    "SI014": first("ambientCG/SurfaceImperfections014/*Color.png"),
    "SI015": first("ambientCG/SurfaceImperfections015/*Color.png"),
    "SI016": first("ambientCG/SurfaceImperfections016/*Color.png"),
    "Scratches002": first("ambientCG/Scratches002/*Opacity.png"),
    "Scratches003": first("ambientCG/Scratches003/*Opacity.png"),
    "Smear006": first("ambientCG/Smear006/*Color.*"),
    "Fingerprints001": first("ambientCG/Fingerprints001/*Opacity.png"),
    "dirt_4": first("ShareTextures/dirt_4/*.png"),
    "dirt_5": first("ShareTextures/dirt_5/*.png"),
    "grunge_3": first("ShareTextures/grunge_3/*.png"),
    "scratches_5": first("ShareTextures/scratches_5/*.png"),
    "Corrosion02": OWN / "12_Пористая_коррозия" / "Коррозия_02_Плотные_колонии.png",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, src in SRC.items():
        im = Image.open(src).convert("L")
        if max(im.size) > 2048:
            im = im.resize((2048, 2048), Image.LANCZOS)
        im.save(OUT / f"{name}.png")
        print(name, im.size, "<-", src.name)


if __name__ == "__main__":
    main()
