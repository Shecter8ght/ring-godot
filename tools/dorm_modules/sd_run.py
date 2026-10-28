"""Отправить задание в Substance Designer через мост tools/sd_bridge и дождаться ответа.

  python -X utf8 tools/dorm_modules/sd_run.py <задание.py> [таймаут, с]   — печатает <задание>.out
  python -X utf8 tools/dorm_modules/sd_run.py --wait-ready                 — ждёт _bridge_ready.txt

Designer должен быть запущен: tools/sd_bridge/designer_open.cmd (папка заданий по умолчанию _asset_src/sd_jobs).
"""
import os
import shutil
import sys
import time

JOBS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "_asset_src", "sd_jobs")


def wait_ready(timeout: float = 90.0) -> bool:
    flag = os.path.join(JOBS, "_bridge_ready.txt")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(flag) and os.path.getmtime(flag) > t0 - 600:
            return True
        time.sleep(0.5)
    return False


def run(job: str, timeout: float = 600.0) -> str:
    name = os.path.splitext(os.path.basename(job))[0] + f"_{int(time.time())}"
    tmp = os.path.join(JOBS, name + ".tmp")
    shutil.copyfile(job, tmp)
    os.replace(tmp, os.path.join(JOBS, name + ".py"))
    out = os.path.join(JOBS, name + ".out")
    t0 = time.time()
    while time.time() - t0 < timeout:
        if os.path.exists(out):
            time.sleep(0.2)
            with open(out, encoding="utf-8") as f:
                return f.read()
        time.sleep(0.5)
    return f"TIMEOUT {timeout}s"


if __name__ == "__main__":
    os.makedirs(JOBS, exist_ok=True)
    if sys.argv[1] == "--wait-ready":
        print("ready" if wait_ready() else "not ready")
    else:
        print(run(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 600.0))
