"""Каталог отделок: задание для Substance Painter через мост sp_bridge (tools/vss_m_v8/sp_bridge) — свой экземпляр
и своя папка заданий (по образцу tools/ar15/sp_run.py).

    python -X utf8 tools/asset_kit/finish/sp_run.py start                 # Painter с мостом (ждёт готовности)
    python -X utf8 tools/asset_kit/finish/sp_run.py -c "<код>" [секунд]    # код в Painter; доступны sp_lib и sp_finish
    python -X utf8 tools/asset_kit/finish/sp_run.py wait <метка> [секунд]  # ждать файл-метку длинного действия
    python -X utf8 tools/asset_kit/finish/sp_run.py quit                   # сохранить нечего — закрыть свой Painter
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SP_JOBS = Path(os.environ.get("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "finish_catalog" / "sp_jobs")))
PAINTER = r"D:\ПРОГРАММЫ\Substance Painter\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe"
BRIDGE = str(ROOT / "tools" / "vss_m_v8" / "sp_bridge")
OCIO = r"D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"
HEADER = ("import sys\n"
          f"for _p in (r'{(ROOT / 'tools' / 'vss_m_v8').as_posix()}', r'{(ROOT / 'tools' / 'asset_kit' / 'finish').as_posix()}'):\n"
          "    sys.path.insert(0, _p) if _p not in sys.path else None\n"
          "import importlib, sp_lib, sp_finish\n"
          "importlib.reload(sp_lib); importlib.reload(sp_finish)\n")


def submit(code: str, name: str) -> Path:
    SP_JOBS.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(p.name[:3]) for p in SP_JOBS.glob("[0-9][0-9][0-9]_*")] + [0])
    stem = f"{n:03d}_{name}"
    tmp = SP_JOBS / (stem + ".tmp")
    tmp.write_text(HEADER + code, encoding="utf-8", newline="\n")
    os.replace(tmp, SP_JOBS / (stem + ".py"))
    return SP_JOBS / (stem + ".out")


def wait(path: Path, timeout: float) -> str:
    t0 = time.time()
    while not path.exists():
        if time.time() - t0 > timeout:
            raise SystemExit(f"нет ответа за {timeout:.0f} с: {path.name}")
        time.sleep(0.3)
    time.sleep(0.2)
    return path.read_text(encoding="utf-8")


def run(code: str, timeout: float = 120.0, name: str = "inline") -> str:
    return wait(submit(code, name), timeout)


def start() -> None:
    SP_JOBS.mkdir(parents=True, exist_ok=True)
    ready = SP_JOBS / "_bridge_ready.txt"
    if ready.exists():
        ready.unlink()
    env = dict(os.environ, SUBSTANCE_PAINTER_PLUGINS_PATH=BRIDGE, SP_BRIDGE_DIR=str(SP_JOBS), OCIO=OCIO)
    p = subprocess.Popen([PAINTER], env=env, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    (SP_JOBS / "_painter_pid.txt").write_text(str(p.pid), encoding="utf-8")
    print("PID", p.pid)
    print(wait(ready, 300))


def main() -> None:
    a = sys.argv[1:]
    if a[0] == "start":
        start()
    elif a[0] == "wait":
        print(wait(SP_JOBS / a[1], float(a[2]) if len(a) > 2 else 3600))
    elif a[0] == "quit":
        print(run("import substance_painter.project as P\nfrom PySide6 import QtWidgets\n"
                  "P.close() if P.is_open() else None\nQtWidgets.QApplication.instance().quit()\n", 60, "quit"))
    elif a[0] == "-c":
        print(run(a[1], float(a[2]) if len(a) > 2 else 120.0, a[3] if len(a) > 3 else "inline"))
    else:
        p = Path(a[0])
        print(run(p.read_text(encoding="utf-8"), float(a[1]) if len(a) > 1 else 120.0, p.stem))


if __name__ == "__main__":
    main()
