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
    "Rubber03": OWN / "18_Следы_резины_и_контакта" / "Резина_03_Рваные_полоски.png",
    "Rubber01": OWN / "18_Следы_резины_и_контакта" / "Резина_01_Короткий_мазок.png",
    "Palm": OWN / "02_Отпечатки_ладоней" / "Ладонь_растёртая_01.png",
    "ChipsWorn": OWN / "10_Сколы_и_потёртости_покрытия" / "Сколы_с_потёртостями_01.png",
    "Scratches001": first("ambientCG/Scratches001/*Opacity.png"),
    "Scratches004": first("ambientCG/Scratches004/*Opacity.png"),
    "Smear001": first("ambientCG/Smear001/*Color.*"),
    "Smear004": first("ambientCG/Smear004/*Color.*"),
}


def rank(a, cover: float, soft: float = 0.05):
    """Рисунок маски владельца с заданной долей площади: порог по квантилю, край чуть мягкий (рваный край — от самой
    маски), значения 0…1."""
    import numpy as np
    a = a.astype("float32") / 255.0
    thr = float(np.quantile(a, 1.0 - cover))
    top = float(a.max())
    return np.clip((a - thr) / max(soft * (top - thr), 1e-4) + 0.5, 0, 1)


def derived(raw: dict):
    """Готовые рисунки по замечанию владельца 2026-11-13 (износ собран по форме, плоскости почти чистые): кромочные сколы
    2 плотностей — чешуйки SI013; редкие короткие тонкие царапины — линии Scratches003, порезанные на отрезки пятнами
    SI012; плотнее — Scratches002 (у ручек); все — рисунок владельца, только пороги."""
    import numpy as np
    out = {}
    out["ChipsEdge45"] = rank(raw["SI013"], 0.45)
    out["ChipsEdge14"] = rank(np.rot90(raw["SI013"]), 0.14)
    out["ChipsSpeck"] = rank(raw["SI007"], 0.30)
    brk = rank(np.rot90(raw["SI012"], 2), 0.40)
    out["ScrFew"] = rank(raw["Scratches004"], 0.004) * brk
    out["ScrTouch"] = rank(raw["Scratches001"], 0.02) * rank(np.flipud(raw["SI012"]), 0.55)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    import numpy as np
    raw = {}
    for name, src in SRC.items():
        im = Image.open(src).convert("L")
        if max(im.size) > 2048:
            im = im.resize((2048, 2048), Image.LANCZOS)
        im.save(OUT / f"{name}.png")
        raw[name] = np.array(im.resize((2048, 2048)) if im.size != (2048, 2048) else im)
        print(name, im.size, "<-", src.name)
    for name, a in derived(raw).items():
        Image.fromarray((a * 255).astype("uint8")).save(OUT / f"{name}.png")
        print(name, "доля", round(float((a > 0.5).mean()), 4))


if __name__ == "__main__":
    main()
