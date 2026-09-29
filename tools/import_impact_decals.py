"""Собирает CC0-декали попаданий из _asset_src/impact_decals в assets/textures/impacts.

Сырьё и license.txt скачиваются один раз в _asset_src/impact_decals (папка не входит в git).
Скрипт режет атласы на варианты, восстанавливает альфу у JPEG и строит normal-карты из маски.

Использование: python tools/import_impact_decals.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "_asset_src" / "impact_decals"
OUT = ROOT / "assets" / "textures" / "impacts"
CREDITS = ROOT / "assets" / "CREDITS.md"
SIZE = 256

# Берём разные по силуэту ячейки; одинаковые повороты уже даёт ImpactFx.
METAL_CELLS = (0, 6, 11, 18, 27, 34, 45, 60)
WOOD_CELLS = (0, 1, 3, 4, 5, 8, 10, 15)


def _cell(image: Image.Image, columns: int, index: int) -> Image.Image:
	"""Вырезает квадратную ячейку атласа без захвата соседей."""
	w = image.width // columns
	h = image.height // columns
	x = (index % columns) * w
	y = (index // columns) * h
	return image.crop((x, y, x + w, y + h))


def _fit(image: Image.Image, size: int = SIZE, padding: int = 12) -> Image.Image:
	"""Оставляет безопасный прозрачный край, чтобы mipmap не подтягивал соседнюю декаль."""
	inner = size - padding * 2
	resized = image.resize((inner, inner), Image.Resampling.LANCZOS)
	out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
	out.alpha_composite(resized, (padding, padding))
	return out


def _white_to_alpha(image: Image.Image) -> Image.Image:
	"""Белый фон JPEG становится прозрачным, тёмный скол и волокна остаются цветными."""
	rgba = image.convert("RGBA")
	inv = ImageOps.invert(ImageOps.grayscale(image))
	alpha = inv.point(lambda value: round(255.0 * math.pow(value / 255.0, 0.62)))
	rgba.putalpha(alpha)
	return rgba


def _black_to_alpha(image: Image.Image) -> Image.Image:
	"""Чёрный фон стеклянного атласа становится прозрачным, белые трещины — непрозрачными."""
	alpha = ImageOps.grayscale(image)
	rgba = Image.new("RGBA", image.size, (238, 246, 255, 0))
	rgba.putalpha(alpha)
	return rgba


def _normal_from_alpha(image: Image.Image, strength: float = 2.6) -> Image.Image:
	"""Строит OpenGL normal map из границы маски декали."""
	height = image.getchannel("A")
	src = height.load()
	w, h = height.size
	out = Image.new("RGB", (w, h), (128, 128, 255))
	dst = out.load()
	for y in range(1, h - 1):
		for x in range(1, w - 1):
			dx = float(src[x + 1, y]) - float(src[x - 1, y])
			dy = float(src[x, y + 1]) - float(src[x, y - 1])
			nx = -dx / 255.0 * strength
			ny = dy / 255.0 * strength
			nz = 1.0
			length = math.sqrt(nx * nx + ny * ny + nz * nz)
			dst[x, y] = (
				round((nx / length * 0.5 + 0.5) * 255.0),
				round((ny / length * 0.5 + 0.5) * 255.0),
				round((nz / length * 0.5 + 0.5) * 255.0),
			)
	return out


def _save_variant(kind: str, index: int, image: Image.Image) -> None:
	image = _fit(image)
	path = OUT / f"{kind}_{index}.png"
	image.save(path, optimize=True)
	_normal_from_alpha(image).save(OUT / f"{kind}_{index}_normal.png", optimize=True)


def _update_credits() -> None:
	heading = "## Декали попаданий (tools/import_impact_decals.py)"
	block = (
		f"{heading}\n\n"
		"- `assets/textures/impacts/concrete_*.png` — Bullet Decal, musdasch, CC0 1.0, "
		"https://opengameart.org/content/bullet-decal — бетонный скол и производная normal-карта\n"
		"- `assets/textures/impacts/metal_*.png`, `wood_*.png`, `glass_cracks.png` — "
		"Bullet holes sprites, mitaywalle, CC0 1.0, "
		"https://realtimevfx.com/t/share-bullet-holes-sprites/21203 — атласы металла, дерева и стекла, "
		"прозрачность и normal-карты собраны импортёром\n\n"
	)
	text = CREDITS.read_text(encoding="utf-8")
	if heading in text:
		start = text.index(heading)
		end = text.find("\n## ", start + len(heading))
		text = text[:start] + block + (text[end + 1 :] if end >= 0 else "")
	else:
		marker = "## Иконки оружия"
		if marker not in text:
			raise RuntimeError(f"В {CREDITS} не найден раздел {marker!r}")
		text = text.replace(marker, block + marker, 1)
	CREDITS.write_text(text, encoding="utf-8")


def main() -> None:
	required = (
		"bullet_hole_concrete.png",
		"bullet_decal_metal.png",
		"bullet_decal_wood.jpeg",
		"bullet_decal_glass.jpeg",
	)
	missing = [name for name in required if not (SRC / name).exists()]
	if missing:
		raise FileNotFoundError(f"Нет сырья в {SRC}: {', '.join(missing)}")
	OUT.mkdir(parents=True, exist_ok=True)

	concrete = Image.open(SRC / "bullet_hole_concrete.png").convert("RGBA")
	_save_variant("concrete", 0, concrete)

	metal = Image.open(SRC / "bullet_decal_metal.png").convert("RGBA")
	for out_index, cell_index in enumerate(METAL_CELLS):
		_save_variant("metal", out_index, _cell(metal, 8, cell_index))

	wood = Image.open(SRC / "bullet_decal_wood.jpeg").convert("RGB")
	for out_index, cell_index in enumerate(WOOD_CELLS):
		_save_variant("wood", out_index, _white_to_alpha(_cell(wood, 4, cell_index)))

	glass = Image.open(SRC / "bullet_decal_glass.jpeg").convert("L")
	_black_to_alpha(glass).save(OUT / "glass_cracks.png", optimize=True)
	_update_credits()
	print(f"Декали собраны: {OUT.relative_to(ROOT)} (1 бетон, 8 металл, 8 дерево, атлас стекла)")


if __name__ == "__main__":
	main()
