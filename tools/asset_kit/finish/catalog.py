"""Каталог заводских отделок: образец → карты стеком Painter → карточки и файл Blender → страница выбора.

    python -X utf8 tools/asset_kit/finish/catalog.py sample              # образец в Blender, проект Painter, запекание
    python -X utf8 tools/asset_kit/finish/catalog.py maps [КОД,КОД]      # карты карточек стеком sp_finish (Painter с мостом)
    python -X utf8 tools/asset_kit/finish/catalog.py cards [КОД,КОД]     # кадры «студия» и «улица» (Blender, Cycles)
    python -X utf8 tools/asset_kit/finish/catalog.py blend               # Каталог_отделок.blend — все образцы рядом
    python -X utf8 tools/asset_kit/finish/catalog.py page                # страница: index.html + catalog.json
    python -X utf8 tools/asset_kit/finish/catalog.py all [КОД,КОД]       # maps → cards → blend → page

Painter запускается отдельно: python -X utf8 tools/asset_kit/finish/sp_run.py start (свой экземпляр, своя папка
заданий). Папка каталога — E:/Models Blender/Каталог отделок (FINISH_CATALOG — другая). Выбор владельца — страницей
(catalog_server.py) в файл спецификации отделки рядом с моделью.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import sp_run  # noqa: E402

CATALOG = Path(os.environ.get("FINISH_CATALOG", r"E:/Models Blender/Каталог отделок"))
WORK = ROOT / "_asset_src" / "finish_catalog"
SAMPLE_DIR = WORK / "sample"
PROJECT = WORK / "sp" / "finish_sample.spp"
BLENDER = r"D:/ПРОГРАММЫ/Blender 5/blender.exe"
RES = 2048            # карты карточек 2K: на образце ~10.9 пикс/мм — плотность оружия в руках в игре (10–12)
BBOX_MM = 165.0       # наибольший размер образца (брусок 120 мм и ствол)


def finishes(codes=None):
    data = json.loads((HERE / "finishes.json").read_text(encoding="utf-8"))
    return [f for f in data["finishes"] if not codes or f["code"] in codes]


def px_mm() -> float:
    s = json.loads((SAMPLE_DIR / "finish_sample.json").read_text(encoding="utf-8"))
    return s["px_mm"] * RES / s["res"]


def blender(*args: str) -> None:
    cmd = [BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", *args]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    for line in r.stdout.splitlines():
        if line.startswith(("CARD", "BLEND", "SAMPLE", "NO MAPS", "Error", "Traceback")) or "Error" in line:
            print(line, flush=True)
    if r.returncode:
        print(r.stdout[-3000:], r.stderr[-3000:])
        raise SystemExit(f"Blender: код {r.returncode}")


def sample() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    blender(str(HERE / "sample_build.py"), "--", str(SAMPLE_DIR))
    jobs = sp_run.SP_JOBS
    for m in ("_project_ready.txt", "_bake_done.txt"):
        (jobs / m).unlink(missing_ok=True)
    print(sp_run.run(f"print(sp_finish.create(r'{(SAMPLE_DIR / 'finish_sample.fbx').as_posix()}', {RES}))", 120, "create"))
    print(sp_run.wait(jobs / "_project_ready.txt", 300))
    print(sp_run.run("print(sp_finish.bake())", 60, "bake"))
    print(sp_run.wait(jobs / "_bake_done.txt", 1800))
    print(sp_run.run(f"print(sp_finish.save_as(r'{PROJECT.as_posix()}'))", 120, "save"))


def ensure_project() -> None:
    """Открыт проект образца — иначе открыть сохранённый."""
    out = sp_run.run("import substance_painter.textureset as TS, substance_painter.project as P\n"
                     "print(P.is_open() and [t.name() for t in TS.all_texture_sets()])", 60, "check")
    if "FinishSample" in out:
        return
    (sp_run.SP_JOBS / "_project_ready.txt").unlink(missing_ok=True)
    print(sp_run.run(f"print(sp_finish.open_project(r'{PROJECT.as_posix()}'))", 120, "open"))
    print(sp_run.wait(sp_run.SP_JOBS / "_project_ready.txt", 300))


def maps(codes=None) -> None:
    ensure_project()
    pm = px_mm()
    for f in finishes(codes):
        code = f["code"]
        out = CATALOG / "Карты" / code
        marker = sp_run.SP_JOBS / f"_card_{code}.txt"
        marker.unlink(missing_ok=True)
        log = sp_run.run(f"print(sp_finish.card('{code}', r'{out.as_posix()}', {pm:.4f}, {BBOX_MM}))", 300, "card_" + code)
        res = sp_run.wait(marker, 600)
        for junk in out.glob("Untitled.*"):         # пресет glTF выгружает и сетку — карточке она не нужна
            junk.unlink()
        ok = res.startswith("OK") and log.startswith("OK")
        print(("MAPS " if ok else "FAIL ") + code, "" if ok else (log + res)[:2000], flush=True)


def cards(codes=None, samples: int = 128) -> None:
    args = [str(HERE / "render_cards.py"), "--", "--catalog", str(CATALOG), "--cards", "--samples", str(samples)]
    if codes:
        args += ["--codes", ",".join(codes)]
    blender(*args)


def blend() -> None:
    blender(str(HERE / "render_cards.py"), "--", "--catalog", str(CATALOG), "--blend", "--samples", "64")


def page() -> None:
    """Страница каталога: index.html (шаблон catalog_page.html) и catalog.json (каталог + пути карточек)."""
    data = json.loads((HERE / "finishes.json").read_text(encoding="utf-8"))
    for f in data["finishes"]:
        f["cards"] = {k: f"Карточки/{f['code']}_{k}.jpg" for k in ("studio", "outdoor")
                      if (CATALOG / "Карточки" / f"{f['code']}_{k}.jpg").exists()}
    data["sample"] = {"px_mm": round(px_mm(), 2), "res": RES, "bbox_mm": BBOX_MM}
    CATALOG.mkdir(parents=True, exist_ok=True)
    (CATALOG / "catalog.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    shutil.copyfile(HERE / "catalog_page.html", CATALOG / "index.html")
    (CATALOG / "Образцы владельца").mkdir(exist_ok=True)
    print("PAGE", CATALOG / "index.html", len(data["finishes"]), "отделок")


def main() -> None:
    a = sys.argv[1:] or ["all"]
    codes = a[1].split(",") if len(a) > 1 else None
    if a[0] == "sample":
        sample()
    elif a[0] == "maps":
        maps(codes)
    elif a[0] == "cards":
        cards(codes)
    elif a[0] == "blend":
        blend()
    elif a[0] == "page":
        page()
    elif a[0] == "all":
        maps(codes)
        cards(codes)
        blend()
        page()


if __name__ == "__main__":
    main()
