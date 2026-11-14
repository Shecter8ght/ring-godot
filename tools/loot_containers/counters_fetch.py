# -*- coding: utf-8 -*-
"""Опоры касс v01, отделка: фото-основы CC0 (ambientCG) в _asset_src/textures/<id>/ (приём lc_fetch_materials.fetch).

    python -X utf8 tools/loot_containers/counters_fetch.py [id ...]
Роль каждой основы — в словаре MATS (и в license.txt, и в asset-state.md).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lc_fetch_materials as F  # noqa: E402

MATS = {
    "Chipboard001": "ДСП: сердечник из стружки на сколах кромок ЛДСП (проверить по превью)",
    "Chipboard003": "ДСП: сердечник (вариант)",
    "Chipboard004": "ДСП: сердечник (вариант 2)",
    "Wood066": "ламинат под дерево (накладка прилавка, кандидат)",
    "Wood092": "ламинат под дерево (кандидат 2)",
    "Wood051": "ламинат под дерево (кандидат 3)",
    "Wood052": "ламинат под дерево (кандидат 4)",
    "Metal010": "шлифованная сталь (кандидат для нержавейки)",
    "Metal011": "шлифованная сталь (кандидат 2)",
    "Metal035": "металл (кандидат)",
    "Metal037": "металл (кандидат 2)",
    "Metal038": "металл (кандидат 3)",
    "Plastic005": "пластик (кандидат)",
    "Rubber001": "резина (кандидат: лента)",
    "Rubber004": "резина (кандидат 2: лента)",
    "Plastic014A": "пластик (кандидат: борта)",
}

if __name__ == "__main__":
    want = set(sys.argv[1:])
    for k, v in MATS.items():
        if not want or k in want:
            try:
                F.fetch(k, v)
            except Exception as e:  # noqa: BLE001
                print(k, "FAIL", e)
