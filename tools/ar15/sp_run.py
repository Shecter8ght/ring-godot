"""AR-15 «ГРАНЬ-15»: задание для Substance Painter через мост sp_bridge (tools/vss_m_v8/sp_bridge) — положить и
дождаться ответа (по образцу tools/prospekt_vehicles/sp_run.py, своя папка заданий).

    python -X utf8 tools/ar15/sp_run.py start                      # свой экземпляр Painter с мостом (ждёт готовности)
    python -X utf8 tools/ar15/sp_run.py -c "<код>" [секунд]         # код в Painter; в нём доступны sp_lib и sp_ar15
    python -X utf8 tools/ar15/sp_run.py wait <метка> [секунд]       # ждать файл-метку длинного действия (запекание)
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

SP_JOBS = Path(r"E:\Games\RING-godot\_asset_src\ar15\tex\sp_jobs")
PAINTER = r"D:\ПРОГРАММЫ\Substance Painter\Adobe Substance 3D Painter\Adobe Substance 3D Painter.exe"
BRIDGE = r"E:\Games\RING-godot\tools\vss_m_v8\sp_bridge"
OCIO = r"D:/ПРОГРАММЫ/Substance Painter/Adobe Substance 3D Painter/resources/ocio/substance/config.ocio"
HEADER = ("import sys\n"
          "for _p in (r'E:/Games/RING-godot/tools/vss_m_v8', r'E:/Games/RING-godot/tools/ar15'):\n"
          "    sys.path.insert(0, _p) if _p not in sys.path else None\n"
          "import importlib, sp_lib, tex_sets, sp_ar15\n"
          "importlib.reload(sp_lib); importlib.reload(tex_sets); importlib.reload(sp_ar15)\n")


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
        time.sleep(0.5)
    time.sleep(0.3)
    return path.read_text(encoding="utf-8")


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
        p = SP_JOBS / a[1]
        print(wait(p, float(a[2]) if len(a) > 2 else 3600))
    elif a[0] == "-c":
        out = submit(a[1], a[3] if len(a) > 3 else "inline")
        print(wait(out, float(a[2]) if len(a) > 2 else 120.0))
    else:
        p = Path(a[0])
        out = submit(p.read_text(encoding="utf-8"), p.stem)
        print(wait(out, float(a[1]) if len(a) > 1 else 120.0))


if __name__ == "__main__":
    main()
