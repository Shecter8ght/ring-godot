"""Мебель общежития, этап 1 текстур: проекты Painter по предметам (свой экземпляр, мост — tools/asset_kit/finish/sp_run.py,
папка заданий _asset_src/dorm_furniture/sp_jobs), запекание карт сетки, стек отделок по finish-spec.json, печать слоем
(furniture_prints.py) и выгрузка.

  set FINISH_SP_JOBS=E:/Games/RING-godot/_asset_src/dorm_furniture/sp_jobs
  python -X utf8 tools/dorm_modules/furniture_sp.py projects [предмет …]   # создать, запечь, сохранить .spp
  python -X utf8 tools/dorm_modules/furniture_sp.py stack [предмет …]      # стек по finish-spec.json + печать, карты
  python -X utf8 tools/dorm_modules/furniture_sp.py variants [предмет …]   # варианты отделки (variants в слотах):
                                                                            # карты в maps/<предмет>__<код>

Слот finish-spec.json берёт детали по имени сетки (= слот материала формы); items — только у этих предметов: одна и та
же деталь у разных предметов в разных отделках («вперемешку» по интервью 2026-10-31).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "dorm_furniture" / "sp_jobs"))
import sp_run  # noqa: E402

SRC = ROOT / "_asset_src" / "dorm_furniture"
LIB = Path("E:/Models Blender/ENVIRONMENT/RING_Dorm_Furniture")
SPEC = LIB / "finish-spec.json"
RES = 2048
# свой размер набора (как furniture_uv.RES — им же запечены карты геометрии): ковёр — 4K
RES_ITEM = {"furn_carpet": 4096}
# предмет: наибольший размер, мм (трёхпроекционные узоры, плотность развёртки — оценка по нему)
ITEMS = {"furn_bunk_bed": 2000, "furn_bed": 2000, "furn_mattress": 1900, "furn_nightstand": 650, "furn_wardrobe": 2100,
         "furn_table": 1000, "furn_chair": 830, "furn_stool": 450, "furn_shelf": 800, "furn_fridge": 850,
         "furn_sofa": 1940, "furn_carpet": 2000, "furn_tv": 1000, "furn_hotplate": 410}
HERE = Path(__file__).resolve().parent.as_posix()


def wait_shelves(tries: int = 60) -> None:
    """Свежий Painter ещё обходит полки: генераторы масок находятся не сразу — ждать снаружи."""
    for _ in range(tries):
        out = sp_run.run("import substance_painter.resource as R\nprint(len(R.search('u:generator')))", 30, "shelves")
        n = out.strip().split("\n")[-1]
        if n.isdigit() and int(n) > 5:
            return
        time.sleep(3)


def projects(names: list[str]) -> None:
    jobs = sp_run.SP_JOBS
    for name in names:
        for mark in ("_project_ready.txt", "_bake_done.txt"):
            (jobs / mark).unlink(missing_ok=True)
        res = RES_ITEM.get(name, RES)
        print(sp_run.run(f"print(sp_finish.create(r'{(SRC / 'sp' / (name + '.fbx')).as_posix()}', {res}))", 180, "create_" + name))
        print(sp_run.wait(jobs / "_project_ready.txt", 600))
        print(sp_run.run("print(sp_finish.bake())", 60, "bake_" + name))
        print(sp_run.wait(jobs / "_bake_done.txt", 2400))
        out = SRC / "sp" / f"{name}.spp"
        print(sp_run.run(f"print(sp_finish.save_as(r'{out.as_posix()}'))", 180, "save_" + name))


def slot_for(spec: dict, game: str, mesh: str) -> dict | None:
    base = mesh.split(".")[0].replace("__sp", "")
    for slot in spec["slots"]:
        if base in slot.get("parts", []) and (not slot.get("items") or game in slot["items"]):
            return slot
    return None


def parts_for(spec: dict, game: str, meshes: list[str], swap: dict | None = None) -> tuple[list, list]:
    """Отделки набора: группы сеток по коду (swap — {id слота: другой код} для варианта)."""
    groups, skipped = {}, []
    for mesh in meshes:
        slot = slot_for(spec, game, mesh)
        if slot is None or not slot.get("finish"):
            skipped.append(mesh)
            continue
        code = (swap or {}).get(slot["id"], slot["finish"])
        f = code if not slot.get("overrides") else {"code": code, **slot["overrides"]}
        groups.setdefault(json.dumps(f, ensure_ascii=False, sort_keys=True), []).append(mesh)
    return [{"finish": json.loads(k), "meshes": v} for k, v in groups.items()], skipped


def open_and_meshes(name: str) -> list[str]:
    jobs = sp_run.SP_JOBS
    (jobs / "_project_ready.txt").unlink(missing_ok=True)
    print(sp_run.run(f"print(sp_finish.open_project(r'{(SRC / 'sp' / (name + '.spp')).as_posix()}'))", 180, "open_" + name))
    print(sp_run.wait(jobs / "_project_ready.txt", 600))
    meshes = sp_run.run("import substance_painter.textureset as TS\n"
                        "st = TS.all_texture_sets()[0]\nprint('|'.join(st.all_mesh_names()))", 60, "meshes_" + name)
    return meshes.split("\n", 1)[1].strip().split("|") if "\n" in meshes else []


def build_and_export(name: str, parts: list, out_dir: Path, marker: str, save: bool, wear: bool = False) -> None:
    """Стек отделок (sp_finish.build_set), печать этапа 1 слоем сверху (если есть) — или (wear) печать и группа
    «Этап 2 — износ» (sp_furniture_wear.py) над отделкой; выгрузка карт, сохранение."""
    px_mm = RES_ITEM.get(name, RES) / ITEMS[name] * 0.55
    top = ([f"print(sp_furniture_wear.build(set_name, r'{SRC.as_posix()}', '{name}', {ITEMS[name]}))"] if wear else [
        "st = sp_lib.stack_by_name(set_name)",
        "for n in L.get_root_layer_nodes(st):",
        "    if n.get_name() == sp_dorm_wear.PRINT:",
        "        L.delete_node(n)",
        f"sp_dorm_wear._print_layer(set_name, r'{SRC.as_posix()}', '{name}', L.InsertPosition.from_textureset_stack(st))"])
    code = "\n".join([
        "import json",
        f"sys.path.insert(0, r'{HERE}') if r'{HERE}' not in sys.path else None",
        "import importlib, sp_dorm_wear, sp_furniture_wear",
        "importlib.reload(sp_dorm_wear)",
        "importlib.reload(sp_furniture_wear)",
        "import substance_painter.textureset as TS",
        "import substance_painter.layerstack as L",
        "set_name = TS.all_texture_sets()[0].name()",
        f"parts = json.loads(r'''{json.dumps(parts, ensure_ascii=False)}''')",
        f"print(sp_finish.build_set(set_name, parts, {px_mm:.3f}, {ITEMS[name]}))",
        *top,
        "def _exp():",
        f"    s, t = sp_lib.export(r'{out_dir.as_posix()}', set_name)",
        (f"    sp_finish.save_as(r'{(SRC / 'sp' / (name + '.spp')).as_posix()}')" if save else "    pass"),
        "    return str(s)",
        f"sp_lib.when_idle(_exp, '{marker}')", ""])
    print(sp_run.run(code, 900, "stack_" + name))
    print(sp_run.wait(sp_run.SP_JOBS / marker, 1800))


def stack(names: list[str]) -> None:
    wait_shelves()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    for name in names:
        marker = f"_stack_{name}.txt"
        (sp_run.SP_JOBS / marker).unlink(missing_ok=True)  # метка прошлого прогона дала бы ложный успех
        meshes = open_and_meshes(name)
        parts, skipped = parts_for(spec, name, meshes)
        print(name, "детали без отделки:", skipped)
        build_and_export(name, parts, SRC / "maps" / name, marker, save=True)


def variants(names: list[str]) -> None:
    """Каждый вариант слота (variants) — стек с заменой одного кода и выгрузка в maps/<предмет>__<код>; основной стек
    потом восстанавливается и сохраняется."""
    wait_shelves()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    for name in names:
        meshes = open_and_meshes(name)
        slots = {s["id"]: s for m in meshes if (s := slot_for(spec, name, m)) is not None and s.get("variants")}
        if not slots:
            continue
        # ДСП и её кромка меняются вместе: «орех» ↔ «бук» — одной парой
        pairs = {"chip_walnut": "edge_walnut", "chip_beech": "edge_beech"}
        done = set()
        for sid, slot in slots.items():
            if sid in done or sid in pairs.values():
                continue
            for i, code in enumerate(slot["variants"]):
                swap = {sid: code}
                if sid in pairs and pairs[sid] in slots:
                    swap[pairs[sid]] = slots[pairs[sid]]["variants"][i]
                parts, _ = parts_for(spec, name, meshes, swap)
                marker = f"_var_{name}_{code}.txt"
                (sp_run.SP_JOBS / marker).unlink(missing_ok=True)
                build_and_export(name, parts, SRC / "maps" / f"{name}__{code}", marker, save=False)
            done.add(sid)
        marker = f"_stack_{name}.txt"
        (sp_run.SP_JOBS / marker).unlink(missing_ok=True)
        parts, _ = parts_for(spec, name, meshes)
        build_and_export(name, parts, SRC / "maps" / name, marker, save=True)


def variant_swaps(spec: dict, name: str, meshes: list[str]) -> list[tuple[str, dict]]:
    """Варианты предмета: (код, {слот: код}); ДСП и её кромка меняются парой «орех» ↔ «бук»."""
    slots = {s["id"]: s for m in meshes if (s := slot_for(spec, name, m)) is not None and s.get("variants")}
    pairs = {"chip_walnut": "edge_walnut", "chip_beech": "edge_beech"}
    out = []
    for sid, slot in slots.items():
        if sid in pairs.values():
            continue
        for i, code in enumerate(slot["variants"]):
            swap = {sid: code}
            if sid in pairs and pairs[sid] in slots:
                swap[pairs[sid]] = slots[pairs[sid]]["variants"][i]
            out.append((code, swap))
    return out


def wear(names: list[str]) -> None:
    """Этап 2: отделка + печать + износ (sp_furniture_wear.py) для каждого варианта и для основного набора; карты —
    в maps_worn (карты принятого этапа 1 в maps не трогаются), основной стек с износом сохраняется в проект."""
    wait_shelves()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    for name in names:
        meshes = open_and_meshes(name)
        for code, swap in variant_swaps(spec, name, meshes):
            parts, _ = parts_for(spec, name, meshes, swap)
            marker = f"_wear_{name}_{code}.txt"
            (sp_run.SP_JOBS / marker).unlink(missing_ok=True)
            build_and_export(name, parts, SRC / "maps_worn" / f"{name}__{code}", marker, save=False, wear=True)
        parts, _ = parts_for(spec, name, meshes)
        marker = f"_wear_{name}.txt"
        (sp_run.SP_JOBS / marker).unlink(missing_ok=True)
        build_and_export(name, parts, SRC / "maps_worn" / name, marker, save=True, wear=True)


if __name__ == "__main__":
    mode, rest = sys.argv[1], sys.argv[2:]
    todo = rest or list(ITEMS)
    {"projects": projects, "stack": stack, "variants": variants, "wear": wear}[mode](todo)
