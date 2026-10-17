"""Декали попаданий в грунт для ImpactFx (assets/textures/impacts/soil_N.png и soil_N_normal.png):
воронка от пули в земле, траве, грязи и щебне. Собственные процедурные текстуры, без внешних
источников; цвет под поверхность даёт оттенок Balance.IMPACT_DECALS (здесь — тёплый серый).

Рельеф: чаша в центре (выбитая земля), неровный вал по краю, комья вокруг — разлетаются
неравномерно по углу (не идеальная звезда). RGB — земля: в чаше темнее (сырой слой снизу), на валу
светлее, комья с подсветкой сверху; A — где декаль: чаша и вал целиком, выброс пятнами, край тает.
_normal — OpenGL normal map из рельефа (как у tools/import_impact_decals.py).

python tools/gen_impact_soil.py   (numpy, scipy, Pillow), затем tools/godot.cmd --headless --import
"""

import os

import numpy as np
from PIL import Image
from scipy import ndimage

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "textures", "impacts")
SIZE = 256
VARIANTS = 4


def _noise(rng: np.random.Generator, scale: float) -> np.ndarray:
	"""Плавный шум 0..1 заданного масштаба (в пикселях)."""
	field = ndimage.gaussian_filter(rng.random((SIZE, SIZE)), scale, mode="wrap")
	field -= field.min()
	return field / max(field.max(), 1e-6)


def _soil(index: int) -> tuple[Image.Image, Image.Image]:
	rng = np.random.default_rng(7301 + index * 97)
	ys, xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float32)
	u = (xs - SIZE / 2 + 0.5) / (SIZE / 2)
	v = (ys - SIZE / 2 + 0.5) / (SIZE / 2)
	r = np.sqrt(u * u + v * v)
	ang = np.arctan2(v, u)
	fine = _noise(rng, 1.2)
	mid = _noise(rng, 4.0)
	big = _noise(rng, 12.0)
	# край воронки неровный по углу: гармоники со случайной силой и фазой, мелкие — слабее
	wobble = np.ones_like(ang)
	for k in range(2, 9):
		wobble += (rng.random() * 0.22 / k ** 0.8) * np.sin(ang * k + rng.random() * 6.28)
	r0 = (0.17 + 0.05 * rng.random()) * wobble * (0.88 + 0.24 * mid)
	bowl = np.where(r < r0, -(1.0 - (r / r0) ** 2), 0.0)
	rim = 0.55 * np.exp(-(((r - r0 * 1.15) / (0.07 + 0.04 * big)) ** 2))
	height = bowl + rim * (0.6 + 0.8 * mid)
	# выброс: сектора гуще и реже, к краю реже
	spray = np.clip(0.55 + 0.45 * np.sin(ang * 2 + rng.random() * 6.28) * np.sin(ang * 5 + rng.random() * 6.28), 0.0, 1.0)
	ejecta = np.clip(1.0 - (r - r0) / 0.6, 0.0, 1.0) * (r > r0 * 1.05) * spray
	# комья — капли разного размера вокруг вала
	clods = np.zeros((SIZE, SIZE), np.float32)
	lump = _noise(rng, 2.2)
	for _ in range(34 + int(rng.integers(0, 18))):
		a = rng.random() * np.pi * 2
		dist = 0.2 + rng.random() ** 1.5 * 0.6
		cx = np.cos(a) * dist
		cy = np.sin(a) * dist
		rad = 0.008 + rng.random() ** 2.5 * 0.04
		# ком не круглый: эллипс под случайным углом и рваный край по шуму
		t = rng.random() * np.pi
		du = (u - cx) * np.cos(t) + (v - cy) * np.sin(t)
		dv = -(u - cx) * np.sin(t) + (v - cy) * np.cos(t)
		d = np.sqrt((du / (0.6 + 0.8 * rng.random())) ** 2 + dv ** 2) / rad + (lump - 0.5) * 1.1
		clods = np.maximum(clods, np.clip(1.0 - d, 0.0, 1.0) ** 0.6 * (0.45 + 0.55 * rng.random()))
	height = height + clods * 0.7 + (fine - 0.5) * 0.12
	height = ndimage.gaussian_filter(height, 0.7)

	# цвет: чаша темнее и сырая, вал и выброс светлее, зерно
	shade = 0.72 + 0.1 * (mid - 0.5) + 0.1 * (fine - 0.5)
	shade = np.where(r < r0, 0.3 + 0.28 * (r / r0) ** 2 + 0.07 * (fine - 0.5), shade)
	shade = shade + 0.05 * np.clip(rim, 0.0, 1.0) - 0.1 * clods
	# свет сверху-слева по рельефу: комья и вал объёмнее
	gy, gx = np.gradient(height)
	shade = shade + np.clip(-(gx + gy) * 1.6, -0.08, 0.08)
	shade = np.clip(shade, 0.0, 1.0)
	rgb = np.stack([shade * 1.0, shade * 0.94, shade * 0.86], axis=-1)

	core = (r < r0 * 1.35).astype(np.float32)
	speckle = np.clip((fine * 0.6 + mid * 0.6 - 0.45) * 2.5, 0.0, 1.0)
	alpha = np.maximum(core, ejecta * speckle)
	alpha = np.maximum(alpha, np.clip(clods * 3.0, 0.0, 1.0))
	alpha *= 1.0 - np.clip((r - 0.8) / 0.18, 0.0, 1.0)
	alpha = ndimage.gaussian_filter(np.clip(alpha, 0.0, 1.0), 0.8)

	albedo = np.dstack([rgb, alpha])
	albedo_img = Image.fromarray((np.clip(albedo, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8), "RGBA")

	strength = 14.0
	nx = -gx * strength
	ny = gy * strength
	nz = np.ones_like(nx)
	length = np.sqrt(nx * nx + ny * ny + nz * nz)
	normal = np.dstack([nx / length, ny / length, nz / length]) * 0.5 + 0.5
	normal_img = Image.fromarray((normal * 255.0 + 0.5).astype(np.uint8), "RGB")
	return albedo_img, normal_img


def main() -> None:
	os.makedirs(OUT, exist_ok=True)
	for index in range(VARIANTS):
		albedo, normal = _soil(index)
		albedo.save(os.path.join(OUT, f"soil_{index}.png"), optimize=True)
		normal.save(os.path.join(OUT, f"soil_{index}_normal.png"), optimize=True)
		print(f"soil_{index}: готово")


if __name__ == "__main__":
	main()
