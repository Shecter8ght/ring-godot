"""Контейнеры для лута, партия 1, отделка v03 (заводская + износ сразу, Painter): стек по finish-spec.json v01 с заменой
отделок по образцам владельца (Образцы_владельца_2026-11-13) и группой износа поверх (lc3_stacks.py).

  tools/loot_containers/lc3_start.cmd                              # Painter с мостом (своя папка заданий sp_jobs_v03)
  python -X utf8 tools/loot_containers/lc3_sp.py stack [предмет …] [k=1.0] [floor=0.3]   # стек, карты, проект v03

Основа — проекты v01 (_asset_src/loot_containers/sp/<предмет>.spp: сетки с развёрткой и запечёнными картами); результат —
sp/<предмет>_v03.spp и карты _asset_src/loot_containers/maps_v03/<предмет>/ (копия в библиотеку — lc3_review.py).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["FINISH_SP_JOBS"] = str(ROOT / "_asset_src" / "loot_containers" / "sp_jobs_v03")
sys.path.insert(0, str(ROOT / "tools" / "loot_containers"))
import lc_sp as V1  # noqa: E402  (ставит F.SRC, F.LIB, F.ITEMS … — настройки партии)

F = V1.F
SRC = F.SRC
F.sp_run.SP_JOBS = ROOT / "_asset_src" / "loot_containers" / "sp_jobs_v03"   # lc_sp ставит папку заданий v01 — не наша

# ---- отделки v03 (записи в формате каталога; build_finish их берёт как есть) ----
GRAIN_PAINT = {"mm": 0.4, "rough": 0.16, "color": 0.03, "height": 0.006}
V3 = {
    # зелёная армейская краска оружейного шкафа: sRGB ≈ (86, 100, 72) на свету, полуматовая, мелкая фактура
    "V3-GUN-GRN": {"code": "V3-GUN-GRN", "title": "Краска зелёная армейская, полуматовая (шкаф)", "kind": "coating",
                   "base": {"color": [0.34, 0.39, 0.28], "rough": 0.60, "metal": 0.0}, "grain": GRAIN_PAINT},
    # чёрная матовая краска с мелкой фактурой (сейф): не темнее ~30/255 sRGB
    "V3-SAFE-BLK": {"code": "V3-SAFE-BLK", "title": "Краска чёрная матовая, мелкая фактура (сейф)", "kind": "coating",
                    "base": {"color": [0.135, 0.135, 0.130], "rough": 0.62, "metal": 0.0},
                    "grain": {"mm": 0.25, "rough": 0.18, "color": 0.03, "height": 0.008}},
    # лимб и штурвал: тёмный сатиновый металл со светлыми рисками, не зеркальный хром
    "V3-DARKMETAL": {"code": "V3-DARKMETAL", "title": "Металл тёмный сатиновый (лимб, ручка сейфа)", "kind": "metal",
                     "base": {"color": [0.26, 0.26, 0.27], "rough": 0.40, "metal": 1.0},
                     "grain": {"mm": 0.06, "rough": 0.06, "color": 0.0, "height": 0.0002},
                     "layers": [{"type": "brushed", "rough": 0.10, "color": 0.02, "height": 0.0002, "mm": 3.0}]},
    # состаренный бежево-серый АБС (касса)
    "V3-ABS": {"code": "V3-ABS", "title": "АБС бежево-серый, литьё (касса)", "kind": "coating",
               "base": {"color": [0.68, 0.64, 0.56], "rough": 0.50, "metal": 0.0},
               "grain": {"mm": 0.25, "rough": 0.22, "color": 0.05, "height": 0.005},
               "layers": [{"type": "stipple", "dots_mm": 0.12, "rough": 0.22, "height": 0.004},
                          {"type": "flow", "rough": -0.04}]},
    # клавиши кассы: серый АБС (на образце светло-серые, цветные группы — отдельно)
    "V3-KEY-GRAY": {"code": "V3-KEY-GRAY", "title": "АБС серый, клавиши кассы", "kind": "coating",
                    "base": {"color": [0.55, 0.54, 0.51], "rough": 0.48, "metal": 0.0},
                    "grain": {"mm": 0.2, "rough": 0.2, "color": 0.04, "height": 0.003}},
    # денежный ящик кассы: крашеный металл того же тона, темнее
    "V3-CASH-DRAWER": {"code": "V3-CASH-DRAWER", "title": "Краска бежево-серая тёмная (денежный ящик)", "kind": "coating",
                       "base": {"color": [0.50, 0.46, 0.40], "rough": 0.55, "metal": 0.0}, "grain": GRAIN_PAINT},
    # аптечка: белая эмаль, слегка желтоватая
    "V3-AID-WHITE": {"code": "V3-AID-WHITE", "title": "Эмаль белая, пожелтевшая (аптечка)", "kind": "coating",
                     "base": {"color": [0.84, 0.82, 0.74], "rough": 0.40, "metal": 0.0},
                     "grain": {"mm": 0.6, "rough": 0.10, "color": 0.02, "height": 0.003}},
}

# код отделки v01 → (замена, вид износа); замена None — отделка прежняя
BY_CODE = {
    "lc_gun": {"PW-SGN-SAT": ("V3-GUN-GRN", "paint")},
    "lc_safe": {"PW-GRA-SAT": ("V3-SAFE-BLK", "paint"), "PW-LGR-SAT": (None, "paint"), "CR-GLS": ("V3-DARKMETAL", "bare")},
    "lc_cell": {"PW-GRY-SAT": ("V3-SAFE-BLK", "paint")},
    "lc_file": {"PW-LGR-SAT": (None, "paint"), "PT-BLK-SAT": (None, "paint")},
    "lc_cash": {"PL-BGE-TEX": ("V3-ABS", "abs"), "PT-BLK-SAT": ("V3-CASH-DRAWER", "paint")},
    "lc_aid": {"PW-WHT-SMO": ("V3-AID-WHITE", "paint")},
}
# отдельные сетки: (набор, имя сетки) → (замена, вид)
BY_MESH = {
    ("lc_cash", "КМ_клавиатура__тёмные"): ("V3-KEY-GRAY", "abs"),
    ("lc_gun", "ОШ_ложемент"): ("PL-BLK-TEX", "dark"),
    ("lc_gun", "ОШ_петли_корпус_лев"): ("AL-EXT-ANO", "bare"), ("lc_gun", "ОШ_петли_корпус_прав"): ("AL-EXT-ANO", "bare"),
    ("lc_gun", "ОШ_петли_лев"): ("AL-EXT-ANO", "bare"), ("lc_gun", "ОШ_петли_прав"): ("AL-EXT-ANO", "bare"),
}
KIND_PREFIX = [("RB-", "dark"), ("FT-", "dark"), ("PL-BLK", "dark"), ("PL-DGR", "dark"), ("FM-", "dark"), ("PT-BLK-MAT", "dark"),
               ("PL-", "abs"), ("CR-", "bare"), ("SS-", "bare"), ("ZN-", "bare"), ("AL-", "bare"), ("NI-", "bare"),
               ("ST-", "bare"), ("PW-", "paint"), ("PT-", "paint")]


def kind_of(code: str) -> str:
    for pre, kind in KIND_PREFIX:
        if code.startswith(pre):
            return kind
    return "misc"


CATALOG = json.loads((ROOT / "tools" / "asset_kit" / "finish" / "finishes.json").read_text(encoding="utf-8"))["finishes"]


def plain(fin):
    """Отделка без процедурных «облаков»: градиенты и пятна распыла выключены (рисунок старения — маски владельца в
    износе), следы течения пластика (procedural wipe) убраны; зерно, шагрень, шлифовка и точки литья остаются."""
    if isinstance(fin, str):
        fin = next(dict(f) for f in CATALOG if f["code"] == fin)
    fin = dict(fin)
    fin["gradients"] = None
    fin["layers"] = [x for x in (fin.get("layers") or []) if x["type"] not in ("mottle", "flow")]
    return fin


def v3_parts(spec: dict, name: str, meshes: list[str]) -> tuple[list, dict]:
    """Отделки набора v03: группы сеток по (отделка, вид износа); возвращает части для build_set и сетки по видам износа."""
    parts, _ = F.parts_for(spec, name, meshes)
    out, kinds = [], {}
    groups: dict[str, dict] = {}
    for part in parts:
        fin = part["finish"]
        code = fin if isinstance(fin, str) else fin["code"]
        for mesh in part["meshes"]:
            base = mesh.split(".")[0]
            new, kind = BY_MESH.get((name, base), (None, None))
            if new is None and kind is None:
                new, kind = BY_CODE.get(name, {}).get(code, (None, None))
            if kind is None:
                kind = kind_of(code)
            fcode = new or code
            final = plain(V3.get(fcode) or (fin if not new else fcode))
            key = json.dumps(final, ensure_ascii=False, sort_keys=True)
            groups.setdefault(key, {"finish": final, "meshes": []})["meshes"].append(mesh)
            kinds.setdefault(kind, []).append(mesh)
    return list(groups.values()), kinds


def build_and_export(name: str, parts: list, kinds: dict, out_dir: Path, marker: str, k: float, floor: float) -> None:
    px_mm = V1.PXMM[name]
    code = "\n".join([
        "import json",
        f"sys.path.insert(0, r'{F.HERE}') if r'{F.HERE}' not in sys.path else None",
        f"sys.path.insert(0, r'{(ROOT / 'tools' / 'loot_containers').as_posix()}') if r'{(ROOT / 'tools' / 'loot_containers').as_posix()}' not in sys.path else None",
        "import importlib, sp_dorm_wear, lc3_stacks",
        "importlib.reload(sp_dorm_wear); importlib.reload(lc3_stacks)",
        "import substance_painter.textureset as TS",
        "sp_finish.FINE_EDGES = True",
        "set_name = TS.all_texture_sets()[0].name()",
        f"parts = json.loads(r'''{json.dumps(parts, ensure_ascii=False)}''')",
        f"kinds = json.loads(r'''{json.dumps(kinds, ensure_ascii=False)}''')",
        f"print(sp_finish.build_set(set_name, parts, {px_mm:.3f}, {F.ITEMS[name]}))",
        f"print(lc3_stacks.wear(set_name, r'{SRC.as_posix()}', '{name}', {F.ITEMS[name]}, kinds, {k}, {floor}))",
        "def _exp():",
        f"    s, t = sp_lib.export(r'{out_dir.as_posix()}', set_name)",
        f"    sp_finish.save_as(r'{(SRC / 'sp' / (name + '_v03.spp')).as_posix()}')",
        "    return str(s)",
        f"sp_lib.when_idle(_exp, '{marker}')", ""])
    print(F.sp_run.run(code, 900, "stack_" + name))
    print(F.sp_run.wait(F.sp_run.SP_JOBS / marker, 1800))


K_GAME = {"lc_safe": 0.3, "lc_cell": 0.35, "lc_file": 0.7, "lc_aid": 0.8, "lc_cash": 0.6}


def stack(names: list[str], k: float = 0.0, floor: float = 0.2) -> None:
    F.wait_shelves()
    spec = json.loads(F.SPEC.read_text(encoding="utf-8"))
    for name in names:
        marker = f"_stack_{name}.txt"
        (F.sp_run.SP_JOBS / marker).unlink(missing_ok=True)
        meshes = F.open_and_meshes(name)
        parts, kinds = v3_parts(spec, name, meshes)
        print(name, {k_: len(v) for k_, v in kinds.items()})
        build_and_export(name, parts, kinds, SRC / "maps_v03" / name, marker, k or K_GAME.get(name, 1.0), floor)


if __name__ == "__main__":
    args = sys.argv[2:]
    opts = {a.split("=")[0]: float(a.split("=")[1]) for a in args if "=" in a}
    todo = [a for a in args if "=" not in a] or [n for n in F.ITEMS if n != "lc_bag"]
    if sys.argv[1] == "stack":
        stack(todo, opts.get("k", 0.0), opts.get("floor", 0.2))
