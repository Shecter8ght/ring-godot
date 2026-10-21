"""Скачать CC0-текстуры Poly Haven для одежды NPC в _asset_src/npc_kit/tex/<id> (2K: цвет, нормаль GL, шероховатость,
высота, AO, если есть) + info.json и общий license.txt. Повторный запуск докачивает только недостающее.

python tools/npc_kit/fetch_textures.py [id …]
"""
from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "npc_kit" / "tex"
IDS = [
    "fabric_leather_01",    # старая мятая кожа — куртка
    "fabric_leather_02",    # кожа со стёжкой, винтаж — берцы
    "leather_red_02",       # кожа с заломами — рисунок заломов (только рельеф)
    "knitted_fleece",       # вязка — балаклава, трикотаж
    "cotton_jersey",        # хлопковый трикотаж
    "denim_fabric_05",      # тёмная саржа — плетение брюк
    "rough_linen",          # грубая ткань — подклад, сетка
    "brown_mud_dry",        # сухая грязь — пятна грязи
    "brushed_concrete_2",   # пятна и разводы — маски износа
]
MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "Displacement": "disp", "AO": "ao"}
UA = {"User-Agent": "RING-npc-kit/1.0 (texture fetch)"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
        return r.read()


def fetch(asset: str, res: str = "2k") -> None:
    d = OUT / asset
    d.mkdir(parents=True, exist_ok=True)
    info = json.loads(get(f"https://api.polyhaven.com/info/{asset}"))
    (d / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    files = json.loads(get(f"https://api.polyhaven.com/files/{asset}"))
    for key, short in MAPS.items():
        if key not in files or res not in files[key]:
            continue
        fmt = files[key][res]
        kind = "jpg" if "jpg" in fmt else "png"
        if short in ("nor_gl", "rough", "disp", "ao") and "png" in fmt:
            kind = "png"
        url = fmt[kind]["url"]
        dst = d / f"{asset}_{short}_{res}.{kind}"
        if dst.exists() and dst.stat().st_size == fmt[kind].get("size", dst.stat().st_size):
            continue
        dst.write_bytes(get(url))
        print(asset, short, dst.stat().st_size // 1024, "КБ")


def main() -> None:
    ids = sys.argv[1:] or IDS
    for a in ids:
        fetch(a)
    lic = OUT / "license.txt"
    lic.write_text("Poly Haven textures: CC0 1.0 (https://polyhaven.com/license). Authors — info.json in each folder.\n",
                   encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
