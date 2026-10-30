"""Оставленный свет, этап 1 текстур: проекты Painter по предметам (свой экземпляр, мост — tools/asset_kit/finish/sp_run.py,
папка заданий _asset_src/dorm_found_lights/sp_jobs), запекание карт сетки, стек отделок по finish-spec.json и выгрузка.

  set FINISH_SP_JOBS=E:/Games/RING-godot/_asset_src/dorm_found_lights/sp_jobs
  python -X utf8 tools/dorm_modules/found_lights_sp.py projects [предмет …]   # создать, запечь, сохранить .spp
  python -X utf8 tools/dorm_modules/found_lights_sp.py stack [предмет …]      # стек по выбору владельца + выгрузка карт

Плотность набора (пикс/мм) — по развёртке предмета; отделки — sp_finish.build_set теми же числами, что на карточке.
Детали набора — сетки по слотам (имя сетки = слот материала, у налобника с суффиксом .001).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "dorm_found_lights" / "sp_jobs"))
import sp_run  # noqa: E402

SRC = ROOT / "_asset_src" / "dorm_found_lights"
LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_FoundLights")
SPEC = LIB / "finish-spec.json"
RES = 2048
# предмет: наибольший размер, мм (для трёхпроекционных узоров), плотность развёртки, пикс/мм (по площади упаковки)
ITEMS = {"found_flashlight": 155, "found_headlamp": 193, "found_chemlight": 162, "found_lantern": 194,
         "found_candles": 317, "found_beacon": 262}
PX = {}  # плотность развёртки, пикс/мм, если замерена (clutter_sp.py); иначе — оценка по габариту


def projects(names: list[str]) -> None:
    jobs = sp_run.SP_JOBS
    for name in names:
        for mark in ("_project_ready.txt", "_bake_done.txt"):
            (jobs / mark).unlink(missing_ok=True)
        print(sp_run.run(f"print(sp_finish.create(r'{(SRC / 'sp' / (name + '.fbx')).as_posix()}', {RES}))", 180, "create_" + name))
        print(sp_run.wait(jobs / "_project_ready.txt", 400))
        print(sp_run.run("print(sp_finish.bake())", 60, "bake_" + name))
        print(sp_run.wait(jobs / "_bake_done.txt", 1800))
        out = SRC / "sp" / f"{name}.spp"
        print(sp_run.run(f"print(sp_finish.save_as(r'{out.as_posix()}'))", 180, "save_" + name))


def wait_shelves(tries: int = 60) -> None:
    """Свежий Painter ещё обходит полки: генераторы масок (mg_curvature…) находятся не сразу — ждать снаружи."""
    import time
    for _ in range(tries):
        out = sp_run.run("import substance_painter.resource as R\nprint(len(R.search('u:generator')))", 30, "shelves")
        n = out.strip().split("\n")[-1]
        if n.isdigit() and int(n) > 5:
            return
        time.sleep(3)


def stack(names: list[str]) -> None:
    wait_shelves()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    by_part = {}
    for slot in spec["slots"]:
        for part in slot.get("parts", []):
            by_part[part] = slot
    jobs = sp_run.SP_JOBS
    for name in names:
        (jobs / "_project_ready.txt").unlink(missing_ok=True)
        (jobs / f"_stack_{name}.txt").unlink(missing_ok=True)  # метка прошлого прогона дала бы ложный успех
        print(sp_run.run(f"print(sp_finish.open_project(r'{(SRC / 'sp' / (name + '.spp')).as_posix()}'))", 180, "open_" + name))
        print(sp_run.wait(jobs / "_project_ready.txt", 400))
        meshes = sp_run.run("import substance_painter.textureset as TS\n"
                            "st = TS.all_texture_sets()[0]\nprint('|'.join(st.all_mesh_names()))", 60, "meshes_" + name)
        mesh_names = meshes.split("\n", 1)[1].strip().split("|") if "\n" in meshes else []
        groups = {}
        skipped = []
        for mesh in mesh_names:
            base = mesh.split(".")[0].replace("__sp", "")
            slot = by_part.get(base)
            if slot is None or not slot.get("finish"):
                skipped.append(mesh)
                continue
            f = slot["finish"] if not slot.get("overrides") else {"code": slot["finish"], **slot["overrides"]}
            groups.setdefault(json.dumps(f, ensure_ascii=False, sort_keys=True), []).append(mesh)
        parts = [{"finish": json.loads(k) if k.startswith("{") else json.loads(k), "meshes": v} for k, v in groups.items()]
        print(name, "детали без отделки (светятся в игре или не выбраны):", skipped)
        px_mm = PX.get(name, RES / ITEMS[name] * 0.55)
        code = (f"import json\nparts = json.loads(r'''{json.dumps(parts, ensure_ascii=False)}''')\n"
                f"name = TS.all_texture_sets()[0].name() if False else None\n"
                "import substance_painter.textureset as TS\n"
                f"print(sp_finish.build_set(TS.all_texture_sets()[0].name(), parts, {px_mm:.3f}, {ITEMS[name]}))\n"
                f"def _exp():\n    s, t = sp_lib.export(r'{(SRC / 'maps' / name).as_posix()}', TS.all_texture_sets()[0].name())\n"
                f"    sp_finish.save_as(r'{(SRC / 'sp' / (name + '.spp')).as_posix()}')\n    return str(s)\n"
                f"sp_lib.when_idle(_exp, '_stack_{name}.txt')\n")
        print(sp_run.run(code, 600, "stack_" + name))
        print(sp_run.wait(jobs / f"_stack_{name}.txt", 900))


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    names = rest or list(ITEMS)
    {"projects": projects, "stack": stack}[mode](names)
