"""Пожарная АЦ: цепочка Painter по проектам — создать, запечь, собрать стеки этапа 1, сохранить, выгрузить карты.

Работает с уже запущенным Painter с мостом (tools/asset_kit/finish/sp_run.py start). Каждый шаг ждёт свою метку;
старые метки удаляются перед шагом (иначе ожидание находит прошлую).

    python -X utf8 tools/fire_truck/sp_pipeline.py body,roof,chassis,interior [шаги: create,bake,build,save,export]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
sys.path.insert(0, str(HERE))
import sp_run  # noqa: E402
import tex_sets as T  # noqa: E402

MAPS = T.WORK + "/maps"
PRE = ("import sys; sys.path.insert(0, r'E:/Games/RING-godot/tools/fire_truck')\n"
       "import importlib, sp_truck; importlib.reload(sp_truck)\n")


def marker(name: str) -> Path:
    p = sp_run.SP_JOBS / name
    if p.exists():
        p.unlink()
    return p


def step(code: str, mark: str | None, timeout: float, label: str) -> str:
    m = marker(mark) if mark else None
    out = sp_run.run(PRE + code, 600, label)
    print(" ", label, out.strip().splitlines()[-1] if out.strip() else "", flush=True)
    if out.startswith("ERROR"):
        raise SystemExit(out)
    if m:
        res = sp_run.wait(m, timeout)
        print(" ", label, "→", res.strip()[:300], flush=True)
        if res.startswith("ERROR"):
            raise SystemExit(res)
        return res
    return out


def main():
    projs = sys.argv[1].split(",")
    steps = sys.argv[2].split(",") if len(sys.argv) > 2 else ["create", "bake", "build", "save", "export"]
    os.makedirs(MAPS, exist_ok=True)
    for proj in projs:
        print("ПРОЕКТ", proj, flush=True)
        if "open" in steps:
            step(f"print(sp_truck.open_project('{proj}'))", "_project_ready.txt", 900, f"open_{proj}")
        if "create" in steps:
            step(f"print(sp_truck.create('{proj}'))", "_project_ready.txt", 900, f"create_{proj}")
        if "bake" in steps:
            step(f"print(sp_truck.bake('{proj}'))", "_bake_done.txt", 5400, f"bake_{proj}")
        if "build" in steps:
            only = [x.split("=", 1)[1].split("+") for x in steps if x.startswith("sets=")]
            for st in T.PROJECTS[proj]:
                if only and st not in only[0]:
                    continue
                step(f"print(sp_truck.build('{st}'))", None, 600, f"build_{st}")
        if "save" in steps:
            step(f"print(sp_truck.save('{proj}'))", "_saved.txt", 1800, f"save_{proj}")
        if "export" in steps:
            step(f"print(sp_truck.export('{proj}', r'{MAPS}'))", "_export_done.txt", 3600, f"export_{proj}")
            for ext in ("gltf", "glb", "bin"):
                p = Path(MAPS) / f"FireTanker_{proj}.{ext}"
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    main()
