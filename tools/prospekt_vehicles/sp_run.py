"""Задание для Substance Painter через мост sp_bridge (tools/vss_m_v8/sp_bridge): положить и дождаться ответа.

    python -X utf8 tools/prospekt_vehicles/sp_run.py <задание.py> [секунд] [-- ключ=значение …]
    python -X utf8 tools/prospekt_vehicles/sp_run.py -c "<код>" [секунд]

Задание копируется в папку заданий (SP_JOBS ниже) под следующим номером — через временный файл и переименование
(мост не прочтёт его недописанным); в начало вставляются пути к помощникам и словарь ARGS. Ждём <имя>.out и печатаем.
Длинные действия (запекание) задание запускает асинхронно и пишет файл-метку — его ждать отдельно (wait_mark).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

SP_JOBS = Path(r"E:\Games\RING-godot\_asset_src\prospekt_vehicles\sp_jobs")
HEADER = ("import sys\n"
          "for _p in (r'E:/Games/RING-godot/tools/vss_m_v8', r'E:/Games/RING-godot/tools/prospekt_vehicles'):\n"
          "    sys.path.insert(0, _p) if _p not in sys.path else None\n"
          "import importlib, sp_lib, vsp\n"
          "importlib.reload(sp_lib); importlib.reload(vsp)\n")


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
    time.sleep(0.2)
    return path.read_text(encoding="utf-8")


def wait_mark(name: str, timeout: float) -> str:
    return wait(SP_JOBS / name, timeout)


def main() -> None:
    a = sys.argv[1:]
    args = {}
    if "--" in a:
        i = a.index("--")
        for kv in a[i + 1:]:
            k, v = kv.split("=", 1)
            args[k] = v
        a = a[:i]
    if a[0] == "-c":
        code, name = a[1], "inline"
        a = a[2:]
    else:
        p = Path(a[0])
        code, name = p.read_text(encoding="utf-8"), p.stem
        a = a[1:]
    timeout = float(a[0]) if a else 120.0
    out = submit(code, name, args)
    print(wait(out, timeout))


if __name__ == "__main__":
    main()
