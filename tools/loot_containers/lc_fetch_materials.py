# -*- coding: utf-8 -*-
"""Контейнеры для лута, v02: фото-основы материалов (ambientCG, CC0 1.0) в _asset_src/textures/<id>/ — color, normal (OpenGL),
roughness, metalness (если есть), height, ao + license.txt.

    python -X utf8 tools/loot_containers/lc_fetch_materials.py [id ...]
Роль каждой основы — в словаре MATS (она же попадает в license.txt и в asset-state.md).
"""
from __future__ import annotations

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "textures"
UA = {"User-Agent": "RING-asset-tool/1.0"}
RES = "2K"

MATS = {
    "Metal027": "порошковая краска, чёрная шагрень (основа для сейфа / шкафа / картотеки, перекраска)",
    "Metal028": "порошковая краска, чёрная, другая шагрень (основа листового металла)",
    "Metal029": "порошковая краска, чёрная, мелкая шагрень",
    "Metal030": "серый гладкий окрашенный металл",
    "Metal032": "серый гладкий окрашенный металл (2)",
    "Metal036": "серый гладкий окрашенный металл (3)",
    "Metal014": "чистая серая сталь с микроцарапинами (оцинковка / нейтральный металл)",
    "Metal009": "шлифованная сталь",
    "Metal012": "шлифованная сталь (2)",
    "Metal044A": "блестящий гладкий металл (хром)",
    "Metal045A": "никель блестящий (хром / никелированные детали)",
    "Metal049A": "серебристый гладкий металл",
    "Metal050A": "алюминий чистый",
    "Metal051A": "алюминий шлифованный круговой",
    "Metal052A": "железо гладкое (точёная сталь ригелей)",
    "Metal063": "тёмный состаренный глянцевый металл (лимб, чёрное анодирование)",
    "Plastic006": "чёрный глянцевый пластик",
    "Plastic010": "белый гладкий пластик",
    "Plastic011": "серый гладкий пластик",
    "Plastic012A": "чёрный пластик с мелкой фактурой",
    "Plastic018A": "серый пластик с зерном",
    "Plastic013A": "белый пластик с фактурой",
    "Rubber002": "чёрная резина",
    "Fabric046": "полиэстер (жилет), плотное полотно",
    "Fabric049": "чёрный полиэстер (жилет), полотно",
    "Fabric048": "белый полиэстер, полотно",
    "Fabric082A": "мелкое серое гладкое плетение (подкладка)",
    "Fabric081A": "тонкое плотное плетение",
    "Fabric035": "чистое гладкое плетение",
    "Fabric038": "чистое гладкое плетение (2)",
    "Fabric041": "чистое гладкое плетение (3)",
    "Fabric034": "войлок",
    "Fabric004": "чёрная тканая лента / карбон-полотно (стропа)",
    "Cardboard004": "картон-крафт гладкий",
    "Paper001": "белая бумага",
    "Paper003": "бумага с волокном и заломами",
}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def fetch(asset_id: str, role: str) -> None:
    from PIL import Image
    out = SRC / asset_id
    if (out / "color_2k.jpg").exists() and (out / "license.txt").exists():
        return
    out.mkdir(parents=True, exist_ok=True)
    z = zipfile.ZipFile(io.BytesIO(get(f"https://ambientcg.com/get?file={asset_id}_{RES}-JPG.zip")))
    for tag, name in (("_Color", "color"), ("_NormalGL", "normal"), ("_Roughness", "roughness"),
                      ("_Metalness", "metalness"), ("_Displacement", "height"), ("_AmbientOcclusion", "ao")):
        for n in z.namelist():
            if tag in n and n.lower().endswith((".jpg", ".png")):
                im = Image.open(io.BytesIO(z.read(n)))
                im.convert("RGB" if name in ("color", "normal") else "L").save(out / f"{name}_2k.jpg", quality=95)
                break
    (out / "license.txt").write_text(
        f"title: {asset_id}\nauthor: ambientCG (Lennart Demes)\nlicense: CC0 1.0\n"
        f"source: https://ambientcg.com/view?id={asset_id}\nrole: {role}\n", encoding="utf-8", newline="\n")
    print(asset_id, "ok", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for k, v in MATS.items():
        if not want or k in want:
            try:
                fetch(k, v)
            except Exception as e:  # noqa: BLE001
                print(k, "FAIL", e)
