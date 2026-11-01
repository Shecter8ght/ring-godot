"""Цевьё Dolinskyi: задания Substance Painter через мост (как tools/asset_kit/finish/sp_run.py — тот же HEADER и папка
заданий), но Painter стартует без неявных слоёв Vulkan. 2026-11-01 Painter 12.1 падал в nvoglv64.dll на первом кадре
3D-вида (создание и открытие проекта, даже чужая сетка) при запущенных RivaTuner (MSI Afterburner), оверлеях Steam и Epic:
их слои Vulkan встраиваются в каждое приложение. Выключаются только для этого процесса Painter.

    python -X utf8 tools/handguard_dolinskyi/sp_run.py start
    python -X utf8 tools/handguard_dolinskyi/sp_run.py -c "<код>" [секунд]      # доступны sp_lib и sp_handguard
    python -X utf8 tools/handguard_dolinskyi/sp_run.py wait <метка> [секунд]
    python -X utf8 tools/handguard_dolinskyi/sp_run.py quit
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault("FINISH_SP_JOBS", str(ROOT / "_asset_src" / "handguard_dolinskyi" / "sp_jobs"))
sys.path.insert(0, str(ROOT / "tools" / "asset_kit" / "finish"))
import sp_run as base  # noqa: E402

base.HEADER += (f"sys.path.insert(0, r'{HERE.as_posix()}') if r'{HERE.as_posix()}' not in sys.path else None\n"
                "import sp_handguard\nimportlib.reload(sp_handguard)\n")
NO_LAYERS = {
    "VK_LOADER_LAYERS_DISABLE": "~implicit~",       # загрузчик Vulkan ≥ 1.3.234: все неявные слои
    "DISABLE_RTSS_LAYER": "1",
    "DISABLE_VK_LAYER_VALVE_steam_overlay_1": "1",
    "DISABLE_VK_LAYER_VALVE_steam_fossilize_1": "1",
    "DISABLE_EOS_OVERLAY": "1",
}


def start() -> None:
    jobs = base.SP_JOBS
    jobs.mkdir(parents=True, exist_ok=True)
    ready = jobs / "_bridge_ready.txt"
    if ready.exists():
        ready.unlink()
    env = dict(os.environ, SUBSTANCE_PAINTER_PLUGINS_PATH=base.BRIDGE, SP_BRIDGE_DIR=str(jobs), OCIO=base.OCIO,
               **NO_LAYERS)
    p = subprocess.Popen([base.PAINTER], env=env, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    (jobs / "_painter_pid.txt").write_text(str(p.pid), encoding="utf-8")
    print("PID", p.pid)
    print(base.wait(ready, 300))


if __name__ == "__main__":
    if sys.argv[1:2] == ["start"]:
        start()
    else:
        base.main()
