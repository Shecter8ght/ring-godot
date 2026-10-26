"""«Проспект», ограждения и город: группы «вперемешку» в индексе моделей (MallFiller выбирает модель группы по
позиции экземпляра — одна и та же при каждой сборке; повтор члена в списке — его доля больше).

    python -X utf8 tools/prospekt_city/index_groups.py

Пишет в data/urban95_models.json (общий с Urban 95, транспортом и растениями; чужие записи не трогает) записи групп с
габаритом — объединением габаритов членов. Член, которого ещё нет в индексе, пропускается; группа без членов — не пишется.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

INDEX = Path(__file__).resolve().parents[2] / "data" / "urban95_models.json"

GROUPS = {
    # опоры 0,4 кВ во дворах: на каждой третьей — консоль с фонарём
    "PC_pole04_any": ("Опоры 0,4 кВ вперемешку (с фонарём — каждая третья)",
                      ["PC04_POLE04", "PC04_POLE04", "PC04_POLE04_LAMP"]),
    # остановки: одна из трёх — с выбитыми стёклами
    "PC_busstop_any": ("Остановочные павильоны вперемешку (целые и разбитые)",
                       ["PC06_BUSSTOP", "PC06_BUSSTOP", "PC06_BUSSTOP_BROKEN"]),
    # контейнеры разных цветов: основной — ржаво-красный, копии — containers_colors.py
    "PC_container20_any": ("Контейнеры 20 футов вперемешку по цвету",
                           ["PC03_C20", "PC03_C20_BLUE", "PC03_C20_GREEN", "PC03_C20_BEIGE"]),
    "PC_container40_any": ("Контейнеры 40 футов вперемешку по цвету",
                           ["PC03_C40", "PC03_C40_BLUE", "PC03_C40_GREEN", "PC03_C40_BEIGE"]),
}


def union(boxes: list) -> dict:
    lo = [min(b["center"][i] - b["size"][i] / 2 for b in boxes) for i in range(3)]
    hi = [max(b["center"][i] + b["size"][i] / 2 for b in boxes) for i in range(3)]
    return {"center": [round((lo[i] + hi[i]) / 2, 4) for i in range(3)], "size": [round(hi[i] - lo[i], 4) for i in range(3)]}


def main() -> None:
    for attempt in range(10):
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
            models = index["models"]
            for gid, (name, members) in GROUPS.items():
                have = [m for m in members if m in models and models[m].get("file")]
                if not have:
                    models.pop(gid, None)
                    continue
                models[gid] = {"id": gid, "name": name, "file": "", "variants": have,
                               "triangles": max(models[m]["triangles"] for m in have), "materials": 0,
                               "aabb": union([models[m]["aabb"] for m in have]), "root_offset": [0, 0, 0],
                               "source": "tools/prospekt_city"}
                print(gid, "←", have)
            INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
            return
        except OSError as e:
            print("индекс занят, повтор:", e)
            time.sleep(1.0 + attempt)


if __name__ == "__main__":
    main()
