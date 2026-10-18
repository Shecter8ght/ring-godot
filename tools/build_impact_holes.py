"""Дырки от пуль для ImpactFx: рельеф воронки лепится по материалу и запекается в Blender.

У каждого материала своя форма (сантиметры, миллиметры — в реальном масштабе):
  hole_concrete — скол конусом уступами (откололись слои), щебень на изломе, дырка, сколы и волосяные
                  трещины вокруг, пыль;
  hole_tile     — глазурь сколота, ракушечный излом в черепке, длинные трещины по плитке;
  hole_asphalt  — выбоина, щебень торчит из тёмного вяжущего, светлая пыль;
  hole_metal    — вмятина, рваная пробоина с загнутыми лепестками, краска сбита до металла,
                  налёт оболочки; два варианта — рикошет: борозда со сбитой краской;
  hole_wood     — рваная дыра, вырванные волокна вдоль древесины, щепки;
  hole_plastic  — дырка с трещинками и белёсым кольцом напряжения;
  hole_cardboard — рваная дыра, загнутые внутрь клочья, видны гофры.
Рельеф — сетка вершин в центрах пикселей карты (высота по нормали, м); с неё Cycles запекает
нормали (касательные, OpenGL — как в Godot) и затенение (AO) на плоскость декали. Цвет, прозрачность,
шероховатость и металличность берутся из тех же данных лепки, по тем же пикселям.

Выход в assets/textures/impacts: <вид>_N.png (цвет + прозрачность), <вид>_N_normal.png,
<вид>_N_orm.png (R — затенение, G — шероховатость, B — металл). Для просмотра владельцем —
E:\\Models Blender\\ENVIRONMENT\\RING_Impact_Holes_Debris\\models\\impact_holes.blend: у каждого варианта
рельеф (прорежен) и плитка с запечёнными картами на подложке своего материала.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/build_impact_holes.py -- [вид …] [--res 512] [--no-blend]
затем tools/godot.cmd --headless --import
"""

import math
import os
import shutil
import sys
import time
import zlib

import bpy
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "assets", "textures", "impacts")
LIBRARY = r"E:\Models Blender\ENVIRONMENT\RING_Impact_Holes_Debris"

# вид: (сторона декали, м; вариантов; цвет подложки для просмотра)
KINDS = {
	"hole_concrete": (0.16, 6, (0.55, 0.53, 0.5)),
	"hole_tile": (0.18, 4, (0.9, 0.89, 0.86)),
	"hole_asphalt": (0.14, 4, (0.16, 0.16, 0.15)),
	"hole_metal": (0.10, 6, (0.24, 0.32, 0.27)),
	"hole_wood": (0.14, 5, (0.45, 0.3, 0.17)),
	"hole_plastic": (0.10, 3, (0.2, 0.22, 0.25)),
	"hole_cardboard": (0.12, 3, (0.55, 0.42, 0.26)),
}


# ------------------------------------------------------------------ шум и поля

def value_noise(rng, n, cells):
	"""Плавный шум n×n, cells ячеек на сторону (случайные узлы не зависят от n)."""
	cells = max(1, int(cells))
	g = rng.random((cells + 2, cells + 2))
	t = (np.arange(n) + 0.5) / n * cells
	i = t.astype(int)
	f = t - i
	f = f * f * (3.0 - 2.0 * f)
	a = g[np.ix_(i, i)]
	b = g[np.ix_(i, i + 1)]
	c = g[np.ix_(i + 1, i)]
	d = g[np.ix_(i + 1, i + 1)]
	fx = f[None, :]
	fy = f[:, None]
	return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(rng, n, cells, octaves, gain=0.5):
	total = np.zeros((n, n))
	amp = 1.0
	norm = 0.0
	for o in range(octaves):
		total += amp * value_noise(rng, n, cells * (2 ** o))
		norm += amp
		amp *= gain
	return total / norm


def stretched_noise(rng, n, cells_x, cells_y):
	"""Шум, вытянутый вдоль X (волокна древесины, борозды)."""
	g = rng.random((int(cells_y) + 2, int(cells_x) + 2))
	tx = (np.arange(n) + 0.5) / n * cells_x
	ty = (np.arange(n) + 0.5) / n * cells_y
	ix = tx.astype(int)
	iy = ty.astype(int)
	fx = tx - ix
	fy = ty - iy
	fx = (fx * fx * (3 - 2 * fx))[None, :]
	fy = (fy * fy * (3 - 2 * fy))[:, None]
	a = g[np.ix_(iy, ix)]
	b = g[np.ix_(iy, ix + 1)]
	c = g[np.ix_(iy + 1, ix)]
	d = g[np.ix_(iy + 1, ix + 1)]
	return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def smoothstep(e0, e1, x):
	t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
	return t * t * (3.0 - 2.0 * t)


class Field:
	"""Координаты пикселей карты (строка 0 — низ, как у картинок Blender), м от центра."""

	def __init__(self, n, size):
		self.n = n
		self.size = size
		c = (np.arange(n) + 0.5) / n * size - size * 0.5
		self.x = np.broadcast_to(c[None, :], (n, n))
		self.y = np.broadcast_to(c[:, None], (n, n))
		self.r = np.sqrt(self.x ** 2 + self.y ** 2)
		self.ang = np.arctan2(self.y, self.x)


def ragged_radius(rng, ang, base, amp, harmonics=8):
	"""Неровный край по углу: гармоники со случайной силой и фазой."""
	w = np.ones_like(ang)
	for k in range(2, harmonics + 1):
		w += rng.uniform(0.0, amp) / (k ** 0.75) * np.sin(ang * k + rng.uniform(0, math.tau))
	return base * w


def polyline_distance(f, points):
	"""Расстояние от каждого пикселя до ломаной (м)."""
	best = np.full((f.n, f.n), 1e9)
	for (ax, ay), (bx, by) in zip(points[:-1], points[1:]):
		dx = bx - ax
		dy = by - ay
		ll = dx * dx + dy * dy + 1e-12
		t = np.clip(((f.x - ax) * dx + (f.y - ay) * dy) / ll, 0.0, 1.0)
		d = np.sqrt((f.x - ax - t * dx) ** 2 + (f.y - ay - t * dy) ** 2)
		best = np.minimum(best, d)
	return best


def wander(rng, start, angle, length, step, jitter, kink=0.35):
	"""Путь трещины: блуждает и изредка ломается."""
	pts = [start]
	x, y = start
	a = angle
	travelled = 0.0
	while travelled < length:
		a += rng.uniform(-jitter, jitter)
		if rng.random() < 0.12:
			a += rng.uniform(-kink, kink)
		x += math.cos(a) * step
		y += math.sin(a) * step
		pts.append((x, y))
		travelled += step
	return pts


def crack_lines(rng, f, count, r_from, length, width, jitter=0.25):
	"""Волосяные трещины от края скола наружу: (маска линии 0..1, бороздка по высоте)."""
	line = np.zeros((f.n, f.n))
	for i in range(count):
		a = rng.uniform(0, math.tau)
		r0 = r_from * rng.uniform(0.9, 1.1)
		pts = wander(rng, (math.cos(a) * r0, math.sin(a) * r0), a, length * rng.uniform(0.4, 1.0), f.size / 120.0, jitter)
		d = polyline_distance(f, pts)
		line = np.maximum(line, 1.0 - smoothstep(width * 0.3, width, d))
	return line


def blobs(rng, f, count, center_r, spread, rad_range, stretch=1.0, angular=False, soft=5.0):
	"""Пятна (щебень, сколы): высота-шапочка 0..1 и номер пятна (для своего цвета). angular — скол:
	многоугольник с плоским дном и крутыми стенками, а не круглая шапочка."""
	cap = np.zeros((f.n, f.n))
	tone = np.zeros((f.n, f.n))
	for i in range(count):
		a = rng.uniform(0, math.tau)
		d = center_r + rng.uniform(0, 1) ** 0.8 * spread
		cx = math.cos(a) * d
		cy = math.sin(a) * d
		rad = rng.uniform(*rad_range)
		t = rng.uniform(0, math.pi)
		du = (f.x - cx) * math.cos(t) + (f.y - cy) * math.sin(t)
		dv = -(f.x - cx) * math.sin(t) + (f.y - cy) * math.cos(t)
		du = du / (rad * stretch * rng.uniform(0.7, 1.4))
		dv = dv / rad
		if angular:
			# неправильный восьмиугольник: два квадрата под углом
			# неправильный многоугольник: случайные полуплоскости вокруг центра, край рваный
			q = np.zeros_like(du)
			for j in range(int(rng.integers(5, 8))):
				a = rng.uniform(0, math.tau)
				q = np.maximum(q, (du * math.cos(a) + dv * math.sin(a)) * rng.uniform(0.8, 1.25))
			q += (value_noise(rng, f.n, f.size / rad * 1.5) - 0.5) * 0.35
			c = np.clip((1.0 - q) * soft, 0.0, 1.0) ** (0.7 if soft < 4.0 else 1.0)
		else:
			q = np.sqrt(du ** 2 + dv ** 2)
			c = np.clip(1.0 - q * q, 0.0, 1.0) ** 0.5
		take = c > cap
		tone = np.where(take, rng.uniform(0.0, 1.0), tone)
		cap = np.maximum(cap, c)
	return cap, tone


# ------------------------------------------------------------------ материалы

def gen_concrete(rng, f):
	n = f.n
	R = ragged_radius(rng, f.ang, 0.021 * rng.uniform(0.8, 1.25), 0.32) * (1.0 + 0.18 * (fbm(rng, n, 7, 3) - 0.5))
	D = rng.uniform(0.010, 0.018)
	t = np.clip(1.0 - f.r / R, 0.0, 1.0)
	layers = int(rng.integers(2, 5))
	terr = np.clip(np.floor(t * layers + (fbm(rng, n, 9, 3) - 0.5) * 1.4) / layers, 0.0, 1.0)
	inside = smoothstep(0.0, 0.04, t)
	h = -D * (0.55 * t ** 1.3 + 0.45 * terr) + (fbm(rng, n, 36, 4) - 0.5) * 0.0014 * inside
	stones, tone = blobs(rng, f, int(rng.integers(8, 16)), 0.0, 0.024, (0.0012, 0.0045))
	h += stones * 0.0016 * inside
	# сколы и пыль вокруг
	chips, _ = blobs(rng, f, int(rng.integers(4, 10)), 0.022, 0.016, (0.0015, 0.005), angular=True)
	h -= chips * 0.0012 * (1.0 - inside)
	cracks = crack_lines(rng, f, int(rng.integers(1, 4)), 0.02, 0.03, 0.00035)
	h -= cracks * 0.0004
	pit_r = rng.uniform(0.003, 0.005) * (1.0 + 0.3 * (fbm(rng, n, 20, 2) - 0.5))
	pit = 1.0 - smoothstep(pit_r * 0.75, pit_r, f.r)
	h = h * (1 - pit) + pit * (-D - 0.018)
	grain = fbm(rng, n, 60, 3)
	fresh = np.stack([0.72, 0.7, 0.66]) * (0.86 + 0.24 * grain)[..., None]
	stone_col = (0.42 + 0.45 * tone)[..., None] * np.array([1.0, 0.98, 0.95])
	albedo = np.where((stones > 0.05)[..., None] & (inside > 0.5)[..., None], stone_col, fresh)
	dust_band = np.clip(1.0 - (f.r - R) / (R * 1.4), 0.0, 1.0) * (f.r > R)
	speck = smoothstep(0.35, 0.75, fbm(rng, n, 45, 3))
	dust = dust_band * (0.25 + 0.5 * speck)
	albedo = np.where((inside < 0.5)[..., None], np.array([0.84, 0.82, 0.78]), albedo)
	albedo = albedo * (1 - cracks[..., None] * 0.3)
	albedo = albedo * (1 - pit[..., None]) + pit[..., None] * 0.05
	mask = np.clip(np.maximum.reduce([inside, chips, cracks * 0.6, dust]), 0, 1)
	rough = np.full((n, n), 0.92)
	return h, albedo, rough, np.zeros((n, n)), mask


def gen_tile(rng, f):
	n = f.n
	glaze = 0.0012
	R = ragged_radius(rng, f.ang, 0.022 * rng.uniform(0.75, 1.3), 0.38) * (1.0 + 0.12 * (fbm(rng, n, 8, 3) - 0.5))
	t = np.clip(1.0 - f.r / R, 0.0, 1.0)
	inside = smoothstep(0.0, 0.03, t)
	Dc = rng.uniform(0.003, 0.007)
	# ракушечный излом: гладкие волны от центра
	waves = np.sin(t * rng.uniform(5, 9) * math.pi + (fbm(rng, n, 6, 2) - 0.5) * 3.0) * 0.00035
	h = (-glaze - Dc * t ** 1.2 + waves * t) * inside
	cracks = crack_lines(rng, f, int(rng.integers(3, 7)), 0.018, 0.09, 0.0005, jitter=0.1)
	# по трещине половинки плитки чуть разошлись — ступенька
	h -= cracks * 0.0003
	pit_r = rng.uniform(0.003, 0.0045)
	pit = 1.0 - smoothstep(pit_r * 0.75, pit_r, f.r)
	h = h * (1 - pit) + pit * (-0.02)
	biscuit = np.array([0.86, 0.8, 0.71]) * (0.9 + 0.15 * fbm(rng, n, 50, 3))[..., None]
	albedo = np.where((inside > 0.02)[..., None], biscuit, np.array([0.95, 0.95, 0.93]))
	albedo = albedo * (1 - cracks[..., None] * 0.55)
	albedo = albedo * (1 - pit[..., None]) + pit[..., None] * 0.05
	mask = np.clip(np.maximum(inside, cracks * 0.85), 0, 1)
	rough = np.where(inside > 0.5, 0.8, 0.25) + cracks * 0.2
	return h, albedo, np.clip(rough, 0, 1), np.zeros((n, n)), mask


def gen_asphalt(rng, f):
	n = f.n
	R = ragged_radius(rng, f.ang, 0.018 * rng.uniform(0.8, 1.3), 0.3)
	t = np.clip(1.0 - f.r / R, 0.0, 1.0)
	inside = smoothstep(0.0, 0.05, t)
	D = rng.uniform(0.006, 0.012)
	h = -D * t ** 1.1
	stones, tone = blobs(rng, f, int(rng.integers(18, 30)), 0.0, 0.03, (0.0015, 0.005), angular=True, soft=2.5)
	h += stones * 0.0022
	pit_r = rng.uniform(0.003, 0.0045)
	pit = 1.0 - smoothstep(pit_r * 0.7, pit_r, f.r)
	h = h * (1 - pit) + pit * (-D - 0.015)
	binder = np.array([0.13, 0.13, 0.12]) * (0.85 + 0.3 * fbm(rng, n, 40, 3))[..., None]
	stone_col = (0.3 + 0.25 * tone)[..., None] * np.array([1.0, 0.99, 0.96]) * (0.85 + 0.3 * fbm(rng, n, 80, 2))[..., None]
	albedo = np.where((stones > 0.1)[..., None], stone_col, binder)
	dust = np.clip(1.0 - (f.r - R) / (R * 1.3), 0.0, 1.0) * (f.r > R) * (0.2 + 0.5 * smoothstep(0.4, 0.8, fbm(rng, n, 40, 3)))
	albedo = np.where((inside < 0.5)[..., None], np.array([0.42, 0.41, 0.39]), albedo)
	albedo = albedo * (1 - pit[..., None]) + pit[..., None] * 0.04
	mask = np.clip(np.maximum.reduce([inside, stones * (f.r < R * 1.5), dust]), 0, 1)
	return h, albedo, np.full((n, n), 0.9), np.zeros((n, n)), mask


def gen_metal_hole(rng, f):
	n = f.n
	Rd = rng.uniform(0.010, 0.017)
	Dd = rng.uniform(0.0012, 0.0028)
	h = -Dd * np.clip(1.0 - (f.r / Rd) ** 2, 0.0, 1.0) ** 2
	rh = ragged_radius(rng, f.ang, rng.uniform(0.0045, 0.006), 0.35, 9)
	petals = int(rng.integers(4, 8))
	phase = rng.uniform(0, math.tau)
	petal = np.clip(np.cos((f.ang + phase) * petals * 0.5) ** 2 * 1.3 - 0.25, 0.0, 1.0)
	inner = rh * (0.45 + 0.35 * petal)
	# лепестки загнуты внутрь дырки, между ними — пусто
	bend = np.clip((rh - f.r) / (rh - inner + 1e-6), 0.0, 1.0)
	h = np.where(f.r < rh, -Dd - 0.004 * bend ** 1.5, h)
	hole = f.r < inner
	h = np.where(hole, -0.03, h)
	Rp = ragged_radius(rng, f.ang, rng.uniform(0.008, 0.014), 0.45, 10) * (1.0 + 0.35 * (fbm(rng, n, 14, 3) - 0.5))
	bare = 1.0 - smoothstep(Rp - 0.0004, Rp, f.r)
	h += 0.00012 * (1.0 - bare)
	smear = 1.0 - smoothstep(rh * 1.2, rh * 2.0, f.r)
	scratch = stretched_noise(rng, n, 30, 3)
	steel = np.array([0.6, 0.6, 0.62]) * (0.85 + 0.25 * scratch)[..., None]
	albedo = steel * (1 - smear[..., None] * 0.55)
	albedo = np.where(hole[..., None], np.array([0.02, 0.02, 0.02]), albedo)
	metal = np.where(hole, 0.0, 0.8 - smear * 0.35)
	rough = np.where(hole, 1.0, 0.36 + smear * 0.25)
	edge = (1.0 - smoothstep(Rp, Rp + 0.0007, f.r)) * (1.0 - bare)
	# край сбитой краски — тёмная тонкая линия поверх краски (ступенька видна по нормали)
	albedo = albedo * (1 - edge[..., None]) + edge[..., None] * 0.18
	metal = metal * (1 - edge)
	rough = rough * (1 - edge) + edge * 0.6
	mask = np.clip(np.maximum(bare, edge * 0.45), 0.0, 1.0)
	mask = np.where(hole, 1.0, mask)
	return h, albedo, rough, metal, mask


def gen_metal_scrape(rng, f):
	"""Рикошет: борозда вдоль X, краска сбита полосой, в конце — глубже."""
	n = f.n
	length = rng.uniform(0.05, 0.075)
	x0 = -length * 0.5
	s = np.clip((f.x - x0) / length, 0.0, 1.0)
	inside_len = (f.x > x0) & (f.x < x0 + length)
	width = 0.0015 + 0.0035 * np.sin(np.clip(s, 0, 1) * math.pi * 0.85) ** 0.7
	wobble = (fbm(rng, n, 4, 2) - 0.5) * 0.002
	dy = np.abs(f.y - wobble)
	groove = np.clip(1.0 - (dy / width) ** 2, 0.0, 1.0) * inside_len
	depth = 0.0006 + 0.0018 * s ** 2
	stri = stretched_noise(rng, n, 2, 90)
	h = -groove * depth * (0.8 + 0.4 * stri)
	paint_w = width * rng.uniform(1.6, 2.4) * (1.0 + 0.4 * (fbm(rng, n, 18, 3) - 0.5))
	bare = (dy < paint_w) & inside_len
	flakes, _ = blobs(rng, f, int(rng.integers(5, 10)), 0.0, length * 0.5, (0.001, 0.003), stretch=2.0)
	bare = bare | ((flakes > 0.2) & (np.abs(f.y) < paint_w.max() * 2.5))
	h += 0.00012 * (~bare)
	steel = np.array([0.66, 0.66, 0.68]) * (0.8 + 0.35 * stri)[..., None]
	edge = (dy < paint_w * 1.25) & inside_len & (~bare)
	mask = np.where(bare, 1.0, np.where(edge, 0.45, 0.0))
	albedo = np.where(edge[..., None], np.array([0.18, 0.18, 0.18]), steel)
	metal = np.where(edge, 0.0, 0.8)
	rough = np.where(edge, 0.6, 0.32)
	return h, albedo, rough, metal, mask


def gen_wood(rng, f):
	n = f.n
	rh0 = rng.uniform(0.004, 0.006)
	rh = ragged_radius(rng, f.ang, rh0, 0.4, 9)
	a = rh0 * rng.uniform(3.0, 5.0)
	b = rh0 * rng.uniform(1.3, 2.0)
	q = np.sqrt((f.x / a) ** 2 + (f.y / b) ** 2) * (1.0 + 0.35 * (stretched_noise(rng, n, 5, 40) - 0.5))
	torn = 1.0 - smoothstep(0.85, 1.0, q)
	fibers = stretched_noise(rng, n, 6, 70)
	h = torn * (-0.0015 + (fibers - 0.5) * 0.0026)
	# щепки по ходу волокон с одной стороны
	side = 1.0 if rng.random() < 0.5 else -1.0
	spl = np.zeros((n, n))
	for i in range(int(rng.integers(3, 7))):
		y0 = rng.uniform(-b, b)
		w = rng.uniform(0.0006, 0.0016)
		ln = rng.uniform(a * 0.8, a * 2.2)
		sx = side * f.x
		strip = (np.abs(f.y - y0) < w) & (sx > a * 0.4) & (sx < a * 0.4 + ln)
		taper = np.clip(1.0 - (sx - a * 0.4) / ln, 0.0, 1.0)
		spl = np.maximum(spl, strip * taper)
	h += spl * 0.0018
	pit = f.r < rh
	h = np.where(pit, -0.02, h)
	streak = stretched_noise(rng, n, 3, 50)
	fresh = np.array([0.8, 0.64, 0.44]) * (0.8 + 0.3 * streak)[..., None]
	albedo = np.where(pit[..., None], np.array([0.05, 0.035, 0.02]), fresh * (0.85 + 0.15 * fibers)[..., None])
	mask = np.clip(np.maximum(torn, spl), 0.0, 1.0)
	mask = np.where(pit, 1.0, mask)
	return h, albedo, np.full((n, n), 0.85), np.zeros((n, n)), mask


def gen_plastic(rng, f):
	n = f.n
	rh = ragged_radius(rng, f.ang, rng.uniform(0.004, 0.0055), 0.3, 8)
	hole = f.r < rh
	cracks = crack_lines(rng, f, int(rng.integers(3, 6)), 0.005, 0.016, 0.0003, jitter=0.15)
	ring = 1.0 - smoothstep(rh * 1.5, rh * 2.6, f.r)
	h = -0.0008 * ring - cracks * 0.0002
	h = np.where(hole, -0.02, h)
	albedo = np.where(hole[..., None], np.array([0.02, 0.02, 0.02]), np.array([0.86, 0.86, 0.85]))
	mask = np.clip(np.maximum(ring * 0.55 * (0.7 + 0.3 * fbm(rng, n, 30, 2)), cracks * 0.7), 0, 1)
	mask = np.where(hole, 1.0, mask)
	return h, albedo, np.full((n, n), 0.5), np.zeros((n, n)), mask


def gen_cardboard(rng, f):
	n = f.n
	rh = ragged_radius(rng, f.ang, rng.uniform(0.005, 0.008), 0.6, 11) * (1.0 + 0.4 * (fbm(rng, n, 16, 3) - 0.5))
	flap_r = rh * rng.uniform(1.4, 1.9)
	t = np.clip((flap_r - f.r) / (flap_r - rh), 0.0, 1.0)
	h = -0.003 * t ** 1.5
	hole = f.r < rh
	h = np.where(hole, -0.02, h)
	fringe = (1.0 - smoothstep(0.0, 0.0012, np.abs(f.r - rh))) * (~hole)
	flutes = 0.5 + 0.5 * np.sin(f.x * math.tau / 0.0042)
	albedo = np.array([0.6, 0.47, 0.3]) * (0.85 + 0.2 * fbm(rng, n, 40, 3))[..., None]
	albedo = np.where((t > 0.4)[..., None], albedo * (0.75 + 0.25 * flutes)[..., None], albedo)
	albedo = albedo * (1 - fringe[..., None]) + fringe[..., None] * np.array([0.82, 0.74, 0.6])
	albedo = np.where(hole[..., None], np.array([0.04, 0.03, 0.02]), albedo)
	mask = np.clip(np.maximum(t > 0.02, fringe), 0, 1).astype(float)
	mask = np.where(hole, 1.0, mask)
	return h, albedo, np.full((n, n), 0.9), np.zeros((n, n)), mask


def generate(kind, index, n, size):
	rng = np.random.default_rng(91000 + zlib.crc32(kind.encode()) % 1000 * 31 + index * 7)
	f = Field(n, size)
	if kind == "hole_concrete":
		return gen_concrete(rng, f)
	if kind == "hole_tile":
		return gen_tile(rng, f)
	if kind == "hole_asphalt":
		return gen_asphalt(rng, f)
	if kind == "hole_metal":
		return gen_metal_scrape(rng, f) if index >= 4 else gen_metal_hole(rng, f)
	if kind == "hole_wood":
		return gen_wood(rng, f)
	if kind == "hole_plastic":
		return gen_plastic(rng, f)
	return gen_cardboard(rng, f)


# ------------------------------------------------------------------ Blender: сетка, запекание

def heightfield_mesh(name, h, size, step=1):
	hs = h[::step, ::step]
	n = hs.shape[0]
	c = (np.arange(n) * step + 0.5 * step) / h.shape[0] * size - size * 0.5
	xs, ys = np.meshgrid(c, c)
	verts = np.stack([xs.ravel(), ys.ravel(), hs.ravel()], axis=1).astype(np.float32)
	i = np.arange(n - 1)
	a = (i[:, None] * n + i[None, :]).ravel()
	quads = np.stack([a, a + 1, a + n + 1, a + n], axis=1).ravel().astype(np.int32)
	mesh = bpy.data.meshes.new(name)
	mesh.vertices.add(n * n)
	mesh.vertices.foreach_set("co", verts.ravel())
	nq = (n - 1) * (n - 1)
	mesh.loops.add(nq * 4)
	mesh.loops.foreach_set("vertex_index", quads)
	mesh.polygons.add(nq)
	mesh.polygons.foreach_set("loop_start", np.arange(0, nq * 4, 4, dtype=np.int32))
	mesh.update(calc_edges=True)
	mesh.validate()
	mesh.shade_smooth()
	obj = bpy.data.objects.new(name, mesh)
	bpy.context.scene.collection.objects.link(obj)
	return obj


def image(name, n, colorspace, alpha=False):
	old = bpy.data.images.get(name)
	if old:
		bpy.data.images.remove(old)
	img = bpy.data.images.new(name, n, n, alpha=alpha, float_buffer=False)
	img.colorspace_settings.name = colorspace
	return img


def bake_plane(name, size, img):
	bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
	plane = bpy.context.active_object
	plane.name = name
	mat = bpy.data.materials.new(name + "_bake")
	mat.use_nodes = True
	node = mat.node_tree.nodes.new("ShaderNodeTexImage")
	node.image = img
	mat.node_tree.nodes.active = node
	node.select = True
	plane.data.materials.append(mat)
	return plane, node


def bake(high, plane, node, img, kind, depth):
	scene = bpy.context.scene
	node.image = img
	plane.active_material.node_tree.nodes.active = node
	bpy.ops.object.select_all(action="DESELECT")
	high.select_set(True)
	plane.select_set(True)
	bpy.context.view_layer.objects.active = plane
	rb = scene.render.bake
	rb.use_selected_to_active = True
	rb.cage_extrusion = depth[0]
	rb.max_ray_distance = depth[0] + depth[1] + 0.01
	rb.margin = 6
	rb.normal_space = "TANGENT"
	rb.use_clear = True
	bpy.ops.object.bake(type=kind)


def setup_cycles(samples):
	scene = bpy.context.scene
	scene.render.engine = "CYCLES"
	scene.cycles.samples = samples
	scene.cycles.use_denoising = False
	try:
		prefs = bpy.context.preferences.addons["cycles"].preferences
		for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI"):
			try:
				prefs.compute_device_type = backend
				prefs.get_devices()
				if any(d.type == backend for d in prefs.devices):
					for d in prefs.devices:
						d.use = d.type == backend
					scene.cycles.device = "GPU"
					print("Cycles:", backend)
					return
			except TypeError:
				continue
	except Exception as error:
		print("GPU недоступна:", error)
	scene.cycles.device = "CPU"
	print("Cycles: CPU")


def save_png(img, path):
	img.filepath_raw = path
	img.file_format = "PNG"
	img.save()


def write_rgba(name, n, rgba, colorspace, path):
	img = image(name, n, colorspace, alpha=True)
	img.pixels.foreach_set(np.clip(rgba, 0.0, 1.0).astype(np.float32).ravel())
	save_png(img, path)
	return img


def read_pixels(img):
	n = img.size[0]
	px = np.empty(n * n * 4, dtype=np.float32)
	img.pixels.foreach_get(px)
	return px.reshape(n, n, 4)


def review_material(name, albedo_img, normal_img, orm_img, base):
	mat = bpy.data.materials.new(name)
	mat.use_nodes = True
	nt = mat.node_tree
	bsdf = nt.nodes["Principled BSDF"]
	bsdf.inputs["Base Color"].default_value = (*base, 1.0)
	tex = nt.nodes.new("ShaderNodeTexImage")
	tex.image = albedo_img
	mix = nt.nodes.new("ShaderNodeMix")
	mix.data_type = "RGBA"
	# у узла смешивания входы разных типов с одинаковыми именами: цвет — A/B под номерами 6/7
	mix.inputs[6].default_value = (*base, 1.0)
	nt.links.new(tex.outputs["Alpha"], mix.inputs[0])
	nt.links.new(tex.outputs["Color"], mix.inputs[7])
	nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
	orm = nt.nodes.new("ShaderNodeTexImage")
	orm.image = orm_img
	sep = nt.nodes.new("ShaderNodeSeparateColor")
	nt.links.new(orm.outputs["Color"], sep.inputs["Color"])
	nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
	nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
	nrm_tex = nt.nodes.new("ShaderNodeTexImage")
	nrm_tex.image = normal_img
	nrm = nt.nodes.new("ShaderNodeNormalMap")
	nt.links.new(nrm_tex.outputs["Color"], nrm.inputs["Color"])
	nt.links.new(tex.outputs["Alpha"], nrm.inputs["Strength"])
	nt.links.new(nrm.outputs["Normal"], bsdf.inputs["Normal"])
	return mat


def main():
	argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	res = 512
	make_blend = True
	only = []
	i = 0
	while i < len(argv):
		if argv[i] == "--res":
			res = int(argv[i + 1])
			i += 2
			continue
		if argv[i] == "--no-blend":
			make_blend = False
		else:
			only.append(argv[i])
		i += 1
	kinds = [k for k in KINDS if not only or k in only]
	bpy.ops.wm.read_factory_settings(use_empty=True)
	setup_cycles(16)
	world = bpy.data.worlds.new("World")
	bpy.context.scene.world = world
	os.makedirs(OUT, exist_ok=True)
	review = []
	started = time.time()
	for kind in kinds:
		size, count, base = KINDS[kind]
		for index in range(count):
			t0 = time.time()
			h, albedo, rough, metal, mask = generate(kind, index, res, size)
			high = heightfield_mesh("%s_%d_high" % (kind, index), h, size)
			plane, node = bake_plane("%s_%d" % (kind, index), size, image("tmp", res, "Non-Color"))
			top = float(max(h.max(), 0.0)) + 0.002
			depth = float(-h.min()) + 0.002
			normal_img = image("%s_%d_normal" % (kind, index), res, "Non-Color")
			bake(high, plane, node, normal_img, "NORMAL", (top, depth))
			ao_img = image("%s_%d_ao" % (kind, index), res, "Non-Color")
			world.light_settings.distance = size * 0.06
			bpy.context.scene.cycles.samples = 48
			bake(high, plane, node, ao_img, "AO", (top, depth))
			bpy.context.scene.cycles.samples = 16
			base_path = os.path.join(OUT, "%s_%d" % (kind, index))
			save_png(normal_img, base_path + "_normal.png")
			ao = read_pixels(ao_img)[..., 0]
			ao = np.where(mask > 0.01, ao, 1.0)
			orm = np.stack([ao, rough, metal, np.ones_like(ao)], axis=-1)
			orm_img = write_rgba("%s_%d_orm" % (kind, index), res, orm, "Non-Color", base_path + "_orm.png")
			rgba = np.concatenate([albedo, mask[..., None]], axis=-1)
			albedo_img = write_rgba("%s_%d_albedo" % (kind, index), res, rgba, "sRGB", base_path + ".png")
			bpy.data.objects.remove(high, do_unlink=True)
			if make_blend:
				review.append((kind, index, size, base, h, base_path, plane))
			else:
				bpy.data.objects.remove(plane, do_unlink=True)
			print("%s_%d: %.1f с" % (kind, index, time.time() - t0))
	if make_blend:
		build_review(review, res)
	print("готово за %.0f с" % (time.time() - started))


def build_review(review, res):
	"""Файл для просмотра: в ряд по видам — рельеф (прорежен) и плитка с картами на подложке."""
	models = os.path.join(LIBRARY, "models")
	textures = os.path.join(LIBRARY, "textures")
	os.makedirs(models, exist_ok=True)
	os.makedirs(textures, exist_ok=True)
	row = {}
	for kind, index, size, base, h, base_path, plane in review:
		r = list(KINDS).index(kind)
		x = index * 0.24
		y = -r * 0.5
		maps = []
		for suffix, colorspace in (("", "sRGB"), ("_normal", "Non-Color"), ("_orm", "Non-Color")):
			copy = os.path.join(textures, os.path.basename(base_path) + suffix + ".png")
			shutil.copyfile(base_path + suffix + ".png", copy)
			img = bpy.data.images.load(copy, check_existing=False)
			img.colorspace_settings.name = colorspace
			maps.append(img)
		albedo_img, normal_img, orm_img = maps
		relief = heightfield_mesh("%s_%d_relief" % (kind, index), h, size, step=max(1, res // 160))
		relief.location = (x, y + 0.2, 0.0)
		mat = bpy.data.materials.new("relief_clay")
		mat.use_nodes = True
		mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.6, 0.6, 0.6, 1.0)
		relief.data.materials.append(mat)
		plane.location = (x, y, 0.0)
		plane.data.materials.clear()
		plane.data.materials.append(review_material("%s_%d_view" % (kind, index), albedo_img, normal_img, orm_img, base))
		row[kind] = r
	for kind, r in row.items():
		bpy.ops.object.text_add(location=(-0.25, -r * 0.5, 0.0))
		label = bpy.context.active_object
		label.data.body = kind
		label.data.size = 0.05
	bpy.ops.object.light_add(type="SUN", location=(0, 0, 2))
	bpy.context.active_object.rotation_euler = (math.radians(40), 0.0, math.radians(30))
	path = os.path.join(models, "impact_holes.blend")
	bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
	print("просмотр:", path)


if __name__ == "__main__":
	main()
