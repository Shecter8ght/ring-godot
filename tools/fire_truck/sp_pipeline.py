"""Пожарная АЦ: цепочка Painter по проектам — создать, запечь, собрать стеки этапа 1, сохранить, выгрузить карты.

Работает с уже запущенным Painter с мостом (tools/asset_kit/finish/sp_run.py start). Каждый шаг ждёт свою метку;
старые метки удаляются перед шагом (иначе ожидание находит прошлую).

    python -X utf8 tools/fire_truck/sp_pipeline.py body,roof,chassis,interior [шаги: create,bake,build,save,export]

Этап 2 (износ, sp_truck_wear.py): шаги wear (группа «Этап 2 — износ» в каждом наборе проекта; sets=a+b — только эти)
и export_worn (карты с износом → WORK/maps_worn; карты этапа 1 в WORK/maps не трогаются).
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
MAPS_WORN = T.WORK + "/maps_worn"
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


def wait_shelf(limit: float = 900) -> None:
    """Полка Painter после запуска ещё индексируется (фильтров и генераторов в поиске нет). Ждать снаружи опросом:
    ожидание внутри задания держит главный поток Painter, и индексация не идёт."""
    import time as _t
    t0 = _t.time()
    while _t.time() - t0 < limit:
        out = sp_run.run("import substance_painter.resource as R" + chr(10) +
                         "print(int(any(s.is_crawling() for s in R.Shelves.all())))", 120, "shelf").strip()
        if out.splitlines() and out.splitlines()[-1].strip() == "0":
            return
        _t.sleep(10)


def main():
    projs = sys.argv[1].split(",")
    steps = sys.argv[2].split(",") if len(sys.argv) > 2 else ["create", "bake", "build", "save", "export"]
    os.makedirs(MAPS, exist_ok=True)
    for proj in projs:
        print("ПРОЕКТ", proj, flush=True)
        if "open" in steps:
            step(f"print(sp_truck.open_project('{proj}'))", "_project_ready.txt", 900, f"open_{proj}")
        if "create" in steps:
            # событие готовности Painter иногда не приходит (проект уже открыт) — ждать и меткой, и опросом наборов
            marker("_project_ready.txt")
            print(" ", "create", sp_run.run(PRE + f"print(sp_truck.create('{proj}'))", 600, f"create_{proj}").strip()[-60:],
                  flush=True)
            want = len(T.PROJECTS[proj])
            import time as _t
            t0 = _t.time()
            while _t.time() - t0 < 1200:
                if (sp_run.SP_JOBS / "_project_ready.txt").exists():
                    break
                out = sp_run.run("import substance_painter.project as P, substance_painter.textureset as TS" + chr(10) +
                                 "print(int(P.is_open() and not P.is_busy()), len(TS.all_texture_sets()) if P.is_open() else 0)",
                                 120, "poll").strip().splitlines()[-1]
                if out.startswith("1 ") and int(out.split()[1]) >= want:
                    break
                _t.sleep(15)
            print("  create →", "готов", flush=True)
        if "bake" in steps:
            step(f"print(sp_truck.bake('{proj}'))", "_bake_done.txt", 5400, f"bake_{proj}")
        if "build" in steps:
            only = [x.split("=", 1)[1].split("+") for x in steps if x.startswith("sets=")]
            for st in T.PROJECTS[proj]:
                if only and st not in only[0]:
                    continue
                step(f"print(sp_truck.build('{st}'))", None, 600, f"build_{st}")
        if "wear" in steps or "build" in steps:
            wait_shelf()
        if "wear" in steps:
            only = [x.split("=", 1)[1].split("+") for x in steps if x.startswith("sets=")]
            for st in T.PROJECTS[proj]:
                if only and st not in only[0]:
                    continue
                step("import sp_truck_wear as W; importlib.reload(W); print(W.build('%s'))" % st, None, 900, f"wear_{st}")
        if "save" in steps:
            step(f"print(sp_truck.save('{proj}'))", "_saved.txt", 1800, f"save_{proj}")
        for key, out in (("export", MAPS), ("export_worn", MAPS_WORN)):
            if key not in steps:
                continue
            os.makedirs(out, exist_ok=True)
            step(f"print(sp_truck.export('{proj}', r'{out}'))", "_export_done.txt", 3600, f"{key}_{proj}")
            for ext in ("gltf", "glb", "bin"):
                p = Path(out) / f"FireTanker_{proj}.{ext}"
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    main()
