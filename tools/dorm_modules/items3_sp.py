"""Вещи общежития, партия 3, текстуры: тот же конвейер Painter, что у мебели (furniture_sp.py) — свои папки,
спецификация finish-spec-3.json, наборы items3_uv.py.

  python -X utf8 tools/dorm_modules/items3_sp.py projects|stack|variants|prints [набор …]

Свой экземпляр Painter (папка заданий _asset_src/dorm_items3/sp_jobs), проекты 2K (мышь и тетради — 1K), стек отделок
по finish-spec-3.json, печать слоем (items3_prints.py), варианты отделки (чемодан, сумка, ящик для инструментов,
ноутбук) → maps/<набор>__<код>; prints — другие картинки того же листа, обложки, картины (наборы печати
<набор>__<картинка>) → maps/<набор>__<картинка>.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "dorm_items3" / "sp_jobs"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import furniture_sp as F  # noqa: E402

F.SRC = ROOT / "_asset_src" / "dorm_items3"
F.LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Items")
F.SPEC = F.LIB / "finish-spec-3.json"
F.RES = 2048
F.RES_ITEM = {"it_mouse": 1024, "it_notebook": 1024, "it_notebook48": 1024, "it_notebook_open": 1024}
F.PAIRS = {}
# набор: наибольший размер, мм — с вариантами, сдвинутыми на время текстур (items3_uv.OFFSETS): по нему Painter
# ставит трёхпроекционные узоры
F.ITEMS = {"it_ammo": 490, "it_zip": 1000, "it_trunk": 800, "it_toolbox": 460, "it_suitcase": 650, "it_duffel": 1500,
           "it_carton": 1600, "it_poster": 900, "it_poster_torn": 900, "it_poster_curl": 900, "it_poster_s": 594,
           "it_poster_s_curl": 594, "it_clip": 297, "it_calendar": 450, "it_chart": 1700, "it_drawing": 841,
           "it_drawing_roll": 841, "it_frame": 1000, "it_frame_pl": 400, "it_pc": 480, "it_monitor": 1350,
           "it_keyboard": 440, "it_mouse": 130, "it_laptop": 860, "it_tube": 750, "it_notebook": 205,
           "it_notebook_open": 340, "it_notebook_stack": 230, "it_notebook48": 205, "it_book": 240, "it_book_open": 340,
           "it_book_stack": 260, "it_book_row": 260}


def prints(names: list[str]) -> None:
    """Варианты печати набора (prints/uv/<набор>__<ключ>_print.json): основной стек, печать варианта, выгрузка в
    maps/<набор>__<ключ>; основной проект не пересохраняется."""
    F.wait_shelves()
    spec = json.loads(F.SPEC.read_text(encoding="utf-8"))
    uv = F.SRC / "prints" / "uv"
    for name in names:
        keys = sorted(p.name[len(name) + 2:-len("_print.json")] for p in uv.glob(f"{name}__*_print.json"))
        if not keys:
            continue
        meshes = F.open_and_meshes(name)
        parts, _ = F.parts_for(spec, name, meshes)
        for key in keys:
            marker = f"_print_{name}_{key}.txt"
            (F.sp_run.SP_JOBS / marker).unlink(missing_ok=True)
            F.build_and_export(name, parts, F.SRC / "maps" / f"{name}__{key}", marker, save=False,
                               print_key=f"{name}__{key}")


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    todo = rest or list(F.ITEMS)
    {"projects": F.projects, "stack": F.stack, "variants": F.variants, "prints": prints}[mode](todo)
