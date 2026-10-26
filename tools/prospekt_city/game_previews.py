"""«Проспект», ограждения и город: проверочные снимки игровой версии (с картами) — лист видов.

    python -X utf8 tools/prospekt_city/game_previews.py <модуль> <игровой .blend>

Ракурсы — META["game_shots"] модуля (или META["shots"]): у варианта i — от X = i·step; варианты в порядке game.py
(VARIANTS, затем GAME["extra"]), коллекции «LOD0 | <вариант>». Eevee, солнце и небо. Лист →
<папка выдачи>/previews/<name>_game_v01_sheet.jpg (сверка вида, не презентация).
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


def consts(mod: str) -> dict:
    tree = ast.parse((HERE / f"{mod}.py").read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("META", "VARIANTS", "GAME"):
                try:
                    out[node.targets[0].id] = ast.literal_eval(node.value)
                except ValueError:
                    pass
    return out


def main() -> None:
    mod, blend = sys.argv[1], sys.argv[2]
    k = consts(mod)
    meta, variants, game = k["META"], k["VARIANTS"], k.get("GAME", {})
    order = list(variants.items()) + list(game.get("extra", {}).items())
    out = ROOT / meta["folder"] / "previews"
    tmp = out / "_tmp_game"
    tmp.mkdir(parents=True, exist_ok=True)
    cells = []
    for i, (key, title) in enumerate(order):
        x0 = i * meta["step"]
        spec = meta.get("game_shots_by", {}).get(key) or meta.get("game_shots") or meta["shots"]
        shots = [f"s{j}:{c[0] + x0},{c[1]},{c[2]}:{t[0] + x0},{t[1]},{t[2]}:{lens}" for j, (_l, c, t, lens) in enumerate(spec)]
        args = [BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(HERE / "review.py"), "--",
                blend, str(tmp), f"v{i}", "eevee", f"solo:LOD0 | {title}"] + shots
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode:
            print(r.stdout[-1500:], r.stderr[-1500:])
            raise SystemExit(1)
        for j, (label, *_r) in enumerate(spec):
            cells.append((tmp / f"v{i}_s{j}.png", f"{title} · {label}"))
    W = 640
    cols = max(len(meta.get("game_shots") or meta["shots"]), 1)
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
    p = out / f"{meta['name']}_game_v01_sheet.jpg"
    sheet.save(p, quality=88)
    for f in tmp.glob("*.png"):
        f.unlink()
    tmp.rmdir()
    print(p)


if __name__ == "__main__":
    main()
