"""Листы визуального сравнения стенда и тестового газона.

    python -X utf8 tools/prospekt_grass/contact_sheet.py
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "screens" / "prospekt_grass"
VARIANTS = [("current", "0 — сейчас"), ("leafy", "A — Leafy Grass"), ("grass001", "B — Grass 001"), ("mixed", "C — Leafy + проплешины")]
VIEWS = [("eye", "глаза"), ("close", "0,5 м"), ("far", "17 м")]
FONT = "C:/Windows/Fonts/arial.ttf"


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size)


def tile(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    image.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, (24, 26, 22))
    canvas.paste(image, ((size[0] - image.width) // 2, (size[1] - image.height) // 2))
    return canvas


def probe() -> None:
    folder = OUT / "probe"
    if not (folder / "models.png").exists():
        return
    width, height, header = 480, 270, 42
    sheet = Image.new("RGB", (width * len(VARIANTS), (height + 34) * len(VIEWS) + header), (20, 23, 19))
    draw = ImageDraw.Draw(sheet)
    for col, (_key, label) in enumerate(VARIANTS):
        draw.text((col * width + 12, 6), label, font=font(25), fill=(238, 240, 228))
    for row, (view, view_label) in enumerate(VIEWS):
        y = header + row * (height + 34)
        for col, (key, _label) in enumerate(VARIANTS):
            sheet.paste(tile(folder / f"{key}_{view}.png", (width, height)), (col * width, y))
            draw.text((col * width + 10, y + height + 4), view_label, font=font(20), fill=(201, 207, 191))
    sheet.save(folder / "00_contact_sheet.jpg", quality=94)
    for view, view_label in VIEWS:
        grid = Image.new("RGB", (1600, 1000), (20, 23, 19))
        gd = ImageDraw.Draw(grid)
        for index, (key, label) in enumerate(VARIANTS):
            x, y = (index % 2) * 800, (index // 2) * 500
            gd.text((x + 12, y + 8), f"{label} · {view_label}", font=font(27), fill=(238, 240, 228))
            grid.paste(tile(folder / f"{key}_{view}.png", (800, 450)), (x, y + 50))
        grid.save(folder / f"{view}.jpg", quality=95)
    if (folder / "relief_flat.png").exists() and (folder / "relief_pom.png").exists():
        comparison = Image.new("RGB", (1600, 500), (20, 23, 19))
        cd = ImageDraw.Draw(comparison)
        for index, (name, label) in enumerate((("relief_flat", "БЕЗ ПАРАЛЛАКСА"), ("relief_pom", "С ПАРАЛЛАКСОМ · 35 мм"))):
            x = index * 800
            cd.text((x + 12, 8), label, font=font(27), fill=(238, 240, 228))
            comparison.paste(tile(folder / f"{name}.png", (800, 450)), (x, 50))
        comparison.save(folder / "relief_compare.jpg", quality=95)
    perf = folder / "performance.json"
    if perf.exists():
        data = json.loads(perf.read_text(encoding="utf-8"))
        lines = ["Вариант | FPS | GPU, мс | треугольники в кадре"]
        for key, label in VARIANTS:
            row = data.get(key, {})
            lines.append(f"{label} | {row.get('fps', 0):.1f} | {row.get('gpu_ms', 0):.3f} | {row.get('triangles', 0)}")
        (folder / "performance.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def maps() -> None:
    before, after = OUT / "map_before", OUT / "map_after"
    if not (before / "performance.json").exists() or not (after / "performance.json").exists():
        return
    views = [("lawn", "исходный кадр"), *VIEWS]
    width, height = 800, 450
    sheet = Image.new("RGB", (1600, len(views) * 500 + 50), (20, 23, 19))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 8), "ДО", font=font(28), fill=(238, 240, 228))
    draw.text((812, 8), "ПОСЛЕ · один газон рощи", font=font(28), fill=(238, 240, 228))
    for row, (view, label) in enumerate(views):
        y = 50 + row * 500
        sheet.paste(tile(before / f"{view}.png", (width, height)), (0, y))
        sheet.paste(tile(after / f"{view}.png", (width, height)), (800, y))
        draw.text((12, y + 454), label, font=font(24), fill=(215, 221, 204))
    sheet.save(OUT / "map_comparison.jpg", quality=95)
    old = json.loads((before / "performance.json").read_text(encoding="utf-8"))
    new = json.loads((after / "performance.json").read_text(encoding="utf-8"))
    lines = ["Кадр | FPS до | FPS после | изменение | GPU до, мс | GPU после, мс"]
    for view, _label in views:
        a, b = old[view], new[view]
        delta = (b["fps"] / a["fps"] - 1.0) * 100.0
        lines.append(f"{view} | {a['fps']:.1f} | {b['fps']:.1f} | {delta:+.1f}% | {a['gpu_ms']:.3f} | {b['gpu_ms']:.3f}")
    (OUT / "map_performance.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def raid() -> None:
    folder = OUT / "raid"
    conditions = [("day", "ДЕНЬ"), ("dusk", "ЗАКАТ"), ("day_rain", "ДОЖДЬ")]
    if not all((folder / f"{key}__lawn_eye.png").exists() for key, _label in conditions):
        return
    sheet = Image.new("RGB", (1920, 840), (20, 23, 19))
    draw = ImageDraw.Draw(sheet)
    for row, (view, label) in enumerate((("eye", "глаза"), ("close", "близко"))):
        for col, (key, condition) in enumerate(conditions):
            x, y = col * 640, row * 420
            draw.text((x + 12, y + 8), f"{condition} · {label}", font=font(25), fill=(238, 240, 228))
            sheet.paste(tile(folder / f"{key}__lawn_{view}.png", (640, 360)), (x, y + 50))
    sheet.save(folder / "raid_conditions.jpg", quality=95)


def refinement() -> None:
    before, after = OUT / "map_candidate_c", OUT / "map_after"
    if not (before / "close.png").exists() or not (after / "close.png").exists():
        return
    views = [("lawn", "исходный кадр"), *VIEWS]
    width, height = 800, 450
    sheet = Image.new("RGB", (1600, len(views) * 500 + 50), (20, 23, 19))
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 8), "C · ДО УПЛОТНЕНИЯ", font=font(28), fill=(238, 240, 228))
    draw.text((812, 8), "C · ПОСЛЕ УПЛОТНЕНИЯ", font=font(28), fill=(238, 240, 228))
    for row, (view, label) in enumerate(views):
        y = 50 + row * 500
        sheet.paste(tile(before / f"{view}.png", (width, height)), (0, y))
        sheet.paste(tile(after / f"{view}.png", (width, height)), (800, y))
        draw.text((12, y + 454), label, font=font(24), fill=(215, 221, 204))
    sheet.save(OUT / "refine_comparison.jpg", quality=95)


if __name__ == "__main__":
    probe()
    maps()
    raid()
    refinement()
