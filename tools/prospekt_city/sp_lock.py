"""Замок общего Painter «Проспекта» (ограждения и город): один проект на всех — круг отделки семейства под замком.

    python -X utf8 tools/prospekt_city/sp_lock.py acquire <владелец> [секунд ожидания]
    python -X utf8 tools/prospekt_city/sp_lock.py release <владелец>
    python -X utf8 tools/prospekt_city/sp_lock.py status

Замок — файл _asset_src/prospekt_city/sp_jobs/_lock с именем владельца, создаётся атомарно (O_EXCL). Ждём, пока
освободится; свой замок берётся повторно без ожидания. Держать замок от создания проекта (sp_family.sh) до последней
выгрузки карт; потом — release. Чужой замок не снимать.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

LOCK = Path(r"E:\Games\RING-godot\_asset_src\prospekt_city\sp_jobs\_lock")


def holder() -> str:
    try:
        return LOCK.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def acquire(owner: str, timeout: float) -> None:
    t0 = time.time()
    while True:
        if holder() == owner:
            print("замок уже у", owner)
            return
        try:
            fd = os.open(str(LOCK), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, owner.encode("utf-8"))
            os.close(fd)
            print("замок взят:", owner)
            return
        except FileExistsError:
            if time.time() - t0 > timeout:
                raise SystemExit(f"замок занят ({holder()}) дольше {timeout:.0f} с")
            time.sleep(5)


def release(owner: str) -> None:
    h = holder()
    if h == owner:
        LOCK.unlink()
        print("замок снят:", owner)
    else:
        print("замок не наш:", h or "свободен")


def main() -> None:
    cmd = sys.argv[1]
    if cmd == "acquire":
        acquire(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 7200)
    elif cmd == "release":
        release(sys.argv[2])
    else:
        print(holder() or "свободен")


if __name__ == "__main__":
    main()
