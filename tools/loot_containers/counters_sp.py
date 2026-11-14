"""Опоры касс v01, отделка (Painter через мост): проекты из FBX (counters_uv.py), запекание, стек (counters_stacks.py), карты.

  tools/loot_containers/counters_start.cmd                         # Painter с мостом (папка заданий sp_jobs_counters)
  python -X utf8 tools/loot_containers/counters_sp.py projects [набор …]   # проект из FBX + запекание + сохранение
  python -X utf8 tools/loot_containers/counters_sp.py stack [набор …] [k=1.0]  # стек, выгрузка карт, сохранение
  python -X utf8 tools/loot_containers/counters_sp.py quit          # сохранить и закрыть СВОЙ Painter

Проекты — _asset_src/loot_containers/sp_counters/<набор>.spp, карты — _asset_src/loot_containers/maps_counters/<набор>/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
JOBS = ROOT / "_asset_src" / "loot_containers" / "sp_jobs_counters"
os.environ["FINISH_SP_JOBS"] = str(JOBS)
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
import sp_run  # noqa: E402

SRC = ROOT / "_asset_src" / "loot_containers"
SP = SRC / "sp_counters"
RES = {"cn_counter": 2048, "cn_checkout": 2048}
BBOX = {"cn_counter": 1500, "cn_checkout": 2445}
HERE = Path(__file__).resolve().parent


def wait_shelves(tries: int = 60) -> None:
    code = "import substance_painter.resource as R\nprint(len(R.search('u:generator')), len(R.search('u:procedural')))"
    for _ in range(tries):
        n = sp_run.run(code, 30, "shelves").strip().split("\n")[-1].split()
        if len(n) == 2 and all(x.isdigit() for x in n) and int(n[0]) > 5 and int(n[1]) > 20:
            return
        time.sleep(3)


def projects(names: list[str]) -> None:
    for name in names:
        for mark in ("_project_ready.txt", "_bake_done.txt"):
            (JOBS / mark).unlink(missing_ok=True)
        print(sp_run.run(f"print(sp_finish.create(r'{(SP / (name + '.fbx')).as_posix()}', {RES[name]}))", 180, "create_" + name))
        print(sp_run.wait(JOBS / "_project_ready.txt", 600))
        print(sp_run.run("print(sp_finish.bake())", 60, "bake_" + name))
        print(sp_run.wait(JOBS / "_bake_done.txt", 2400))
        print(sp_run.run(f"print(sp_finish.save_as(r'{(SP / (name + '.spp')).as_posix()}'))", 180, "save_" + name))


def open_and_meshes(name: str, spp: str) -> list[str]:
    (JOBS / "_project_ready.txt").unlink(missing_ok=True)
    print(sp_run.run(f"print(sp_finish.open_project(r'{(SP / spp).as_posix()}'))", 180, "open_" + name))
    print(sp_run.wait(JOBS / "_project_ready.txt", 600))
    meshes = sp_run.run("import substance_painter.textureset as TS\n"
                        "st = TS.all_texture_sets()[0]\nprint('|'.join(st.all_mesh_names()))", 60, "meshes_" + name)
    return meshes.split("\n", 1)[1].strip().split("|") if "\n" in meshes else []


def stack(names: list[str], k: float = 1.0) -> None:
    wait_shelves()
    out_root = SRC / "maps_counters"
    for name in names:
        marker = f"_stack_{name}.txt"
        (JOBS / marker).unlink(missing_ok=True)
        meshes = open_and_meshes(name, name + ".spp")
        out_dir = out_root / name
        code = "\n".join([
            "import json",
            f"sys.path.insert(0, r'{HERE.as_posix()}') if r'{HERE.as_posix()}' not in sys.path else None",
            f"sys.path.insert(0, r'{(ROOT / 'tools' / 'dorm_modules').as_posix()}') if r'{(ROOT / 'tools' / 'dorm_modules').as_posix()}' not in sys.path else None",
            "import importlib, lc3_stacks, counters_stacks",
            "importlib.reload(lc3_stacks); importlib.reload(counters_stacks)",
            "import substance_painter.textureset as TS",
            "sp_finish.FINE_EDGES = True",
            "set_name = TS.all_texture_sets()[0].name()",
            f"print(counters_stacks.build(set_name, '{name}', {BBOX[name]}, {k}))",
            "def _exp():",
            f"    s, t = sp_lib.export(r'{out_dir.as_posix()}', set_name)",
            f"    sp_finish.save_as(r'{(SP / (name + '_fin.spp')).as_posix()}')",
            "    return str(s)",
            f"sp_lib.when_idle(_exp, '{marker}')", ""])
        print(sp_run.run(code, 900, "stack_" + name))
        print(sp_run.wait(JOBS / marker, 1800))


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    opts = {a.split("=")[0]: float(a.split("=")[1]) for a in rest if "=" in a}
    todo = [a for a in rest if "=" not in a] or list(RES)
    if mode == "projects":
        projects(todo)
    elif mode == "stack":
        stack(todo, opts.get("k", 1.0))
    elif mode == "quit":
        print(sp_run.run("import substance_painter.project as P\nfrom PySide6 import QtWidgets\n"
                         "P.save() if P.is_open() and P.needs_saving() else None\n"
                         "P.close() if P.is_open() else None\nQtWidgets.QApplication.instance().quit()\n", 60, "quit"))
