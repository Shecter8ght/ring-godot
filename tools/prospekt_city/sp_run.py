"""Задание для Substance Painter через мост sp_bridge (tools/vss_m_v8/sp_bridge): положить и дождаться ответа.

    python -X utf8 tools/prospekt_city/sp_run.py <задание.py> [секунд] [-- ключ=значение …]
    python -X utf8 tools/prospekt_city/sp_run.py -c "<код>" [секунд]
    python -X utf8 tools/prospekt_city/sp_run.py --wait <метка> [секунд]

Свой экземпляр Painter со своей папкой заданий (SP_JOBS) — рядом с Painter транспорта и ВСС-М. Задание копируется
под следующим номером через временный файл и переименование; в начало — пути к помощникам и словарь ARGS.
Длинные действия (запекание) задание запускает асинхронно и пишет файл-метку — её ждать отдельно (--wait).
Один проект Painter на всех: помощники-сессии берут замок SP_JOBS/_lock (файл с именем владельца) на весь круг.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

SP_JOBS = Path(r"E:\Games\RING-godot\_asset_src\prospekt_city\sp_jobs")
HEADER = ("import sys\n"
          "for _p in (r'E:/Games/RING-godot/tools/vss_m_v8', r'E:/Games/RING-godot/tools/prospekt_city'):\n"
          "    sys.path.insert(0, _p) if _p not in sys.path else None\n"
          "import importlib, sp_lib, csp\n"
          "importlib.reload(sp_lib); importlib.reload(csp)\n")


def submit(code: str, name: str, args: dict) -> Path:
    SP_JOBS.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(p.name[:3]) for p in SP_JOBS.glob("[0-9][0-9][0-9]_*")] + [0])
    stem = f"{n:03d}_{name}"
    tmp = SP_JOBS / (stem + ".tmp")
    tmp.write_text(HEADER + f"ARGS = {args!r}\n" + code, encoding="utf-8", newline="\n")
    os.replace(tmp, SP_JOBS / (stem + ".py"))
    return SP_JOBS / (stem + ".out")


def wait(path: Path, timeout: float) -> str:
    t0 = time.time()
    while not path.exists():
        if time.time() - t0 > timeout:
            raise SystemExit(f"нет ответа за {timeout:.0f} с: {path.name}")
        time.sleep(0.5)
    time.sleep(0.3)
    return path.read_text(encoding="utf-8", errors="replace")


def main() -> None:
    argv = sys.argv[1:]
    args = {}
    if "--" in argv:
        i = argv.index("--")
        for kv in argv[i + 1:]:
            k, v = kv.split("=", 1)
            args[k] = v
        argv = argv[:i]
    if argv[0] == "--wait":
        p = SP_JOBS / argv[1]
        t = float(argv[2]) if len(argv) > 2 else 1800
        print(wait(p, t))
        return
    if argv[0] == "-c":
        code, name = argv[1], "inline"
        timeout = float(argv[2]) if len(argv) > 2 else 120
    else:
        src = Path(argv[0])
        code, name = src.read_text(encoding="utf-8"), src.stem
        timeout = float(argv[1]) if len(argv) > 1 else 120
    out = wait(submit(code, name, args), timeout)
    print(out)
    if out.startswith("ERROR"):
        sys.exit(1)


if __name__ == "__main__":
    main()
