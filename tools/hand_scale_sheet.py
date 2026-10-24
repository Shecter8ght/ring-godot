"""Листы сравнения пробы размера кистей: по стволу — строки стоек, столбцы масштабов.

Снимки — tools/hand_scale_shots.tscn (docs/screens/hand_scale/hand_<ствол>_<стойка>_<k>.png).
Запуск: python -X utf8 tools/hand_scale_sheet.py → docs/screens/hand_scale/sheet_<ствол>.png
"""
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SHOTS = ROOT / "docs" / "screens" / "hand_scale"
NAMES = {"wpn_hg_01": "ПМ", "wpn_hg_02": "Glock 17", "wpn_ar_01": "ВЕРАС-54"}
POSES = [("low", "наискосок"), ("hip", "от бедра"), ("ads", "в прицеле"), ("check", "магазин\nу глаз")]
TILE = (640, 360)
HEAD = 44
SIDE = 150


def font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> int:
    pattern = re.compile(r"hand_(.+)_(low|hip|ads|check)_(\d{3})\.png$")
    shots: dict[str, dict[tuple[str, int], Path]] = {}
    for path in SHOTS.glob("hand_*.png"):
        match = pattern.match(path.name)
        if match:
            shots.setdefault(match[1], {})[(match[2], int(match[3]))] = path
    if not shots:
        print("нет снимков в", SHOTS)
        return 1
    title = font(26)
    label = font(22)
    for weapon, frames in sorted(shots.items()):
        scales = sorted({k for _, k in frames}, reverse=True)
        poses = [p for p in POSES if any((p[0], k) in frames for k in scales)]
        sheet = Image.new("RGB", (SIDE + TILE[0] * len(scales), HEAD + TILE[1] * len(poses)), (24, 26, 30))
        draw = ImageDraw.Draw(sheet)
        draw.text((12, 8), NAMES.get(weapon, weapon), font=title, fill=(235, 235, 235))
        for col, k in enumerate(scales):
            text = "кисть × %.2f" % (k / 100.0) + ("  (сейчас)" if k == 100 else "")
            draw.text((SIDE + col * TILE[0] + 12, 10), text, font=label, fill=(235, 235, 235))
        for row, (pose, pose_name) in enumerate(poses):
            y = HEAD + row * TILE[1]
            draw.multiline_text((12, y + TILE[1] // 2 - 14), pose_name, font=label, fill=(200, 200, 200))
            for col, k in enumerate(scales):
                path = frames.get((pose, k))
                if path is None:
                    continue
                with Image.open(path) as image:
                    sheet.paste(image.convert("RGB").resize(TILE, Image.LANCZOS), (SIDE + col * TILE[0], y))
        out = SHOTS / f"sheet_{weapon}.png"
        sheet.save(out)
        print(out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
