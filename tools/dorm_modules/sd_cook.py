"""Граф Designer (.sbs) → .sbsar → карты PNG без окна (sbscooker, sbsrender).

  python -X utf8 tools/dorm_modules/sd_cook.py <граф.sbs> <папка карт> [размер, степень двойки: 11 = 2048]

Карты — 16 бит (рельеф, поля износа), имя файла — идентификатор выхода графа.
"""
import os
import subprocess
import sys

SD = r"D:\ПРОГРАММЫ\Substance designer\Adobe Substance 3D Designer"


def cook(sbs: str, out_dir: str, size_pow: int = 11) -> list:
    os.makedirs(out_dir, exist_ok=True)
    tmp = os.path.join(out_dir, "_sbsar")
    os.makedirs(tmp, exist_ok=True)
    r = subprocess.run([os.path.join(SD, "sbscooker.exe"), "--inputs", sbs, "--output-path", tmp],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("sbscooker: " + r.stdout + r.stderr)
    sbsar = os.path.join(tmp, os.path.splitext(os.path.basename(sbs))[0] + ".sbsar")
    r = subprocess.run([os.path.join(SD, "sbsrender.exe"), "render", "--inputs", sbsar, "--output-path", out_dir,
                        "--output-name", "{outputNodeName}", "--output-format", "png", "--output-bit-depth", "16",
                        "--set-value", f"$outputsize@{size_pow},{size_pow}"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("sbsrender: " + r.stdout + r.stderr)
    return sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))


if __name__ == "__main__":
    size = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    print(cook(sys.argv[1], sys.argv[2], size))
