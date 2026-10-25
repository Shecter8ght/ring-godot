"""«Проспект», ограждения и город: проверочные виды формы и лист видов ассета (для сверки, не презентация).

    python -X utf8 tools/prospekt_city/previews.py <модуль> <файл.blend> [eevee|workbench]

Виды берутся из META модуля генератора (читается разбором текста, без импорта bpy): каждый вариант снимается
отдельно (остальные коллекции скрыты), камера и цель — от начала варианта (вариант i стоит на X = i·step).
META["shots_by"][ключ варианта] — свои ракурсы варианта вместо общих META["shots"] (столько же снимков).
Лист видов → <папка выдачи>/previews/<name>_v01_sheet.jpg.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = Path(r"E:\Models Blender\ENVIRONMENT\Проспект_город_партия1")
BL = r"D:\ПРОГРАММЫ\Blender 5\blender.exe"


def module_consts(mod: str) -> dict:
    tree = ast.parse((HERE / f"{mod}.py").read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("META", "VARIANTS"):
                out[node.targets[0].id] = ast.literal_eval(node.value)
    return out


def main() -> None:
    mod, blend = sys.argv[1], sys.argv[2]
    engine = sys.argv[3] if len(sys.argv) > 3 else "eevee"
    k = module_consts(mod)
    meta, variants = k["META"], k["VARIANTS"]
    out = ROOT / meta["folder"] / "previews"
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "_tmp"
    tmp.mkdir(exist_ok=True)
    cells = []
    for i, (key, v) in enumerate(variants.items()):
        x0 = i * meta["step"]
        shots = []
        spec = meta.get("shots_by", {}).get(key, meta["shots"])     # свои ракурсы варианта, если заданы
        for j, (label, cam, tgt, lens) in enumerate(spec):
            c = f"{cam[0] + x0},{cam[1]},{cam[2]}"
            t = f"{tgt[0] + x0},{tgt[1]},{tgt[2]}"
            shots.append(f"s{j}:{c}:{t}:{lens}")
        args = [BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(HERE / "review.py"), "--",
                blend, str(tmp), f"v{i}"] + (["eevee"] if engine == "eevee" else []) + [f"solo:{v}"] + shots
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise SystemExit(1)
        for j, (label, *_rest) in enumerate(spec):
            cells.append((tmp / f"v{i}_s{j}.png", f"{v} · {label}"))
    W = 640
    cols = len(meta["shots"])
    try:
        font = ImageFont.truetype("arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    ims = []
    for p, label in cells:
        im = Image.open(p).convert("RGB")
        im = im.resize((W, int(im.height * W / im.width)))
        d = ImageDraw.Draw(im)
        d.rectangle((0, 0, W, 34), fill=(20, 20, 20))
        d.text((10, 6), label, fill=(240, 240, 240), font=font)
        ims.append(im)
    h = ims[0].height
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * W, rows * h), (30, 30, 30))
    for n, im in enumerate(ims):
        sheet.paste(im, ((n % cols) * W, (n // cols) * h))
    p = out / f"{meta['name']}_v01_sheet.jpg"
    sheet.save(p, quality=88)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    print(p)


if __name__ == "__main__":
    main()
