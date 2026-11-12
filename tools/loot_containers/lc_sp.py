"""Контейнеры для лута, партия 1, текстуры этап 1: проекты Painter по предметам, запекание, стек по finish-spec.json,
печать слоем (lc_prints.py), выгрузка карт. Драйвер мебели общежития (furniture_sp.py) с настройками партии: свой экземпляр
Painter (папка заданий _asset_src/loot_containers/sp_jobs), слот спецификации — по ПОЛНОМУ имени сетки (у нас один объект формы
бывает в разных отделках: «<объект>__внутри»), плотность развёртки — по замеру lc_uv.py.

  python -X utf8 tools/asset_kit/finish/sp_run.py start            # со своей папкой: FINISH_SP_JOBS задаётся здесь же
  python -X utf8 tools/loot_containers/lc_sp.py projects|stack [предмет …]

Карты — _asset_src/loot_containers/maps/<предмет>/<предмет>_{baseColor,normal,occlusionRoughnessMetallic}.png, проекты —
_asset_src/loot_containers/sp/<предмет>.spp.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["FINISH_SP_JOBS"] = str(ROOT / "_asset_src" / "loot_containers" / "sp_jobs")
sys.path.insert(0, str(ROOT / "tools" / "dorm_modules"))
import furniture_sp as F  # noqa: E402

F.SRC = ROOT / "_asset_src" / "loot_containers"
F.LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Loot_Containers")
F.SPEC = F.LIB / "finish-spec.json"
F.RES = 2048
F.RES_ITEM = {"lc_cell": 1024, "lc_aid": 1024, "lc_gun": 4096, "lc_file": 4096}
F.PAIRS = {}
# предмет: наибольший размер, мм (трёхпроекционные узоры)
F.ITEMS = {"lc_safe": 700, "lc_cell": 360, "lc_gun": 1800, "lc_file": 1320, "lc_cash": 425, "lc_bag": 540, "lc_aid": 510}
# плотность развёртки, пикс/мм (замер lc_uv.py: DENS …)
PXMM = {"lc_safe": 0.698, "lc_cell": 0.823, "lc_gun": 0.846, "lc_file": 0.690, "lc_cash": 0.671, "lc_bag": 0.945, "lc_aid": 0.623}
F.WEAR = "sp_furniture_wear"   # не используется (этап 2)


def slot_for(spec: dict, game: str, mesh: str) -> dict | None:
    """Слот сетки: по полному имени «<объект>[__<метка>]» (в развёртке метка — часть имени отделки)."""
    name = mesh.split(".")[0] if mesh.count(".") and mesh.rsplit(".", 1)[-1].isdigit() else mesh
    for slot in spec["slots"]:
        if name in slot.get("parts", []) and (not slot.get("items") or game in slot["items"]):
            return slot
    return None


F.slot_for = slot_for


def build_and_export(name: str, parts: list, out_dir: Path, marker: str, save: bool, wear: bool = False,
                     wear_args: str = "", print_key: str | None = None) -> None:
    px_mm = PXMM[name]
    code = "\n".join([
        "import json",
        f"sys.path.insert(0, r'{F.HERE}') if r'{F.HERE}' not in sys.path else None",
        "import importlib, sp_dorm_wear",
        "importlib.reload(sp_dorm_wear)",
        "import substance_painter.textureset as TS",
        "import substance_painter.layerstack as L",
        "set_name = TS.all_texture_sets()[0].name()",
        f"parts = json.loads(r'''{json.dumps(parts, ensure_ascii=False)}''')",
        f"print(sp_finish.build_set(set_name, parts, {px_mm:.3f}, {F.ITEMS[name]}))",
        "st = sp_lib.stack_by_name(set_name)",
        "for n in L.get_root_layer_nodes(st):",
        "    if n.get_name() == sp_dorm_wear.PRINT:",
        "        L.delete_node(n)",
        f"sp_dorm_wear._print_layer(set_name, r'{F.SRC.as_posix()}', '{print_key or name}', "
        "L.InsertPosition.from_textureset_stack(st))",
        "def _exp():",
        f"    s, t = sp_lib.export(r'{out_dir.as_posix()}', set_name)",
        (f"    sp_finish.save_as(r'{(F.SRC / 'sp' / (name + '.spp')).as_posix()}')" if save else "    pass"),
        "    return str(s)",
        f"sp_lib.when_idle(_exp, '{marker}')", ""])
    print(F.sp_run.run(code, 900, "stack_" + name))
    print(F.sp_run.wait(F.sp_run.SP_JOBS / marker, 1800))


F.build_and_export = build_and_export


def stack(names: list[str]) -> None:
    F.wait_shelves()
    spec = json.loads(F.SPEC.read_text(encoding="utf-8"))
    for name in names:
        marker = f"_stack_{name}.txt"
        (F.sp_run.SP_JOBS / marker).unlink(missing_ok=True)
        meshes = F.open_and_meshes(name)
        parts, skipped = F.parts_for(spec, name, meshes)
        print(name, "детали без отделки:", skipped)
        F.build_and_export(name, parts, F.SRC / "maps" / name, marker, save=True)


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    todo = rest or list(F.ITEMS)
    {"projects": F.projects, "stack": stack}[mode](todo)
