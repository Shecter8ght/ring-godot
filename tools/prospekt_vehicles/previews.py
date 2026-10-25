"""Транспорт «Проспекта»: проверочные виды формы для каждой машины партии (Eevee, нейтральный свет).

    python -X utf8 tools/prospekt_vehicles/previews.py [ключ …]

Для каждого варианта (коллекции) — 3/4 спереди и 3/4 сзади; лист видов → <папка>/previews/<Имя>_v01_sheet.jpg.
Это не презентация: снимки для сверки формы, сам файл владелец смотрит в Blender.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(r"E:\Models Blender\VEHICLES\Город_партия1")
BL = r"D:\ПРОГРАММЫ\Blender 5\blender.exe"
REVIEW = Path(__file__).with_name("review.py")
# ключ: папка, файл, варианты (заголовки), шаг по X между вариантами, длина, высота
CARS = {
    "sedan": ("Седан", "Sedan", ["Целый", "Открыт", "Битый", "Сгоревший"], 3.2, 4.4, 1.47),
    "hatch": ("Хэтчбек", "Hatchback", ["Целый", "Открыт", "Битый", "Сгоревший"], 3.2, 4.3, 1.47),
    "wagon": ("Универсал", "Wagon", ["Целый", "Открыт", "Битый", "Сгоревший"], 3.2, 4.7, 1.47),
    "suv": ("Внедорожник", "SUV", ["Целый", "Открыт", "Битый", "Сгоревший"], 3.2, 4.8, 1.84),
    "bus12": ("Автобус_12м", "CityBus12", ["Целый", "Двери открыты"], 4.0, 12.4, 2.9),
    "paz": ("ПАЗ", "PAZ", ["Целый", "Двери открыты"], 3.98, 7.0, 2.96),
    "gazel": ("ГАЗель_маршрутка", "Gazel_Minibus", ["Целый", "Двери открыты"], 3.54, 5.5, 2.2),
}


def main() -> None:
    keys = sys.argv[1:] or list(CARS)
    for k in keys:
        folder, name, variants, step, length, height = CARS[k]
        blend = ROOT / folder / "models" / f"{name}_geometry_v01.blend"
        out = ROOT / folder / "previews"
        out.mkdir(parents=True, exist_ok=True)
        d = max(length * 0.95, 5.0)
        shots = []
        for i, v in enumerate(variants):
            x = i * step
            zc = height * 0.45
            shots.append(f"v{i}_front:{x + d * 0.62},{-d * 0.95},{height * 1.25}:{x},{-length * 0.05},{zc}:35")
            shots.append(f"v{i}_rear:{x - d * 0.62},{d * 0.95},{height * 1.35}:{x},{length * 0.05},{zc}:35")
        # другие варианты в кадре мешают: прячем все коллекции, кроме снимаемой — по одному запуску на вариант
        for i, v in enumerate(variants):
            hide = [f"hide:{o}" for o in variants if o != v]
            my = [s for s in shots if s.startswith(f"v{i}_")]
            subprocess.run([BL, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(REVIEW),
                            "--", str(blend), str(out), name, "eevee"] + hide + my, check=True, capture_output=True)
        W = 720
        cells = []
        for i, v in enumerate(variants):
            for side in ("front", "rear"):
                im = Image.open(out / f"{name}_v{i}_{side}.png").convert("RGB")
                im = im.resize((W, int(im.height * W / im.width)))
                dr = ImageDraw.Draw(im)
                try:
                    font = ImageFont.truetype("arial.ttf", 26)
                except OSError:
                    font = ImageFont.load_default()
                dr.text((14, 10), v, fill=(255, 255, 255), font=font)
                cells.append(im)
        h = cells[0].height
        sheet = Image.new("RGB", (2 * W, h * len(variants)), (30, 30, 30))
        for j, im in enumerate(cells):
            sheet.paste(im, ((j % 2) * W, (j // 2) * h))
        p = out / f"{name}_v01_sheet.jpg"
        sheet.save(p, quality=86)
        for i in range(len(variants)):
            for side in ("front", "rear"):
                (out / f"{name}_v{i}_{side}.png").unlink()
        print(p)


if __name__ == "__main__":
    main()
