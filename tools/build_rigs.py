"""Разгрузки RING (предметы rig_belt / rig_chest / rig_assault / rig_heavy): модели в Blender для иконок
и вида предмета в мире. Формы и ткань — те же приёмы, что у рюкзаков (tools/build_backpacks.py).
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_rigs.py [-- --shape] [-- --preview DIR]

Образцы (по памяти о реальных изделиях, без скачанных моделей): поясная РПС с парой подсумков и
сумкой сброса; нагрудная «лифчик» на четыре магазина с Х-образными лямками; штурмовая на шесть
магазинов с подсумками сверху и Н-образными мягкими лямками; тяжёлая — жилет с передней и задней
панелью, четыре сдвоенных подсумка, боковые подсумки и сумка сброса.
Число подсумков под магазины совпадает с данными предмета (data/items.json, rig.pouches).

Оси Blender: X — ширина, −Y — перёд (лицо), +Y — спина, Z — вверх. Экспорт glTF: в Godot перёд — +Z.
Пишет assets/items/models/rig_*.glb; затем --import и icon_bake -- rig_belt rig_chest rig_assault rig_heavy.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_backpacks as B  # noqa: E402

V = Vector
X = Vector((1, 0, 0))
Z = Vector((0, 0, 1))

# цвета (sRGB 0..255): ткань, стропа, фурнитура, магазин в подсумке, сумка сброса; ткань Poly Haven
LOOKS = {
	"rig_belt": {"fabric": (44, 46, 50), "strap": (28, 29, 32), "hw": (14, 14, 15), "mag": (22, 23, 25), "dump": (54, 56, 60), "tex": "terlenka"},
	"rig_chest": {"fabric": (58, 64, 44), "strap": (40, 44, 32), "hw": (16, 16, 16), "mag": (22, 23, 24), "dump": (50, 55, 38), "tex": "stretch_poplin"},
	"rig_assault": {"fabric": (100, 80, 52), "strap": (76, 62, 42), "hw": (20, 19, 18), "mag": (24, 24, 25), "dump": (88, 70, 46), "tex": "book_pattern"},
	"rig_heavy": {"fabric": (44, 50, 43), "strap": (30, 34, 30), "hw": (15, 15, 15), "mag": (22, 23, 24), "dump": (38, 43, 37), "tex": "book_pattern"},
}


def make_mats(key: str) -> dict:
	c = LOOKS[key]
	return {
		"fabric": B.material(f"{key}_fabric", c["fabric"], c["tex"], 0.9),
		"strap": B.material(f"{key}_strap", c["strap"], c["tex"], 0.85, 0.5),
		"dump": B.material(f"{key}_dump", c["dump"], c["tex"], 0.95, 1.0),
		"hw": B.material(f"{key}_hw", c["hw"], None, 0.5),
		"mag": B.material(f"{key}_mag", c["mag"], None, 0.42),
	}


def smooth(pts: list, closed: bool = False, times: int = 2) -> list:
	"""Срезание углов (Чайкин): ломаная → плавная линия лямки."""
	for _ in range(times):
		out = []
		n = len(pts)
		last = n if closed else n - 1
		if not closed:
			out.append(pts[0])
		for i in range(last):
			a, b = pts[i], pts[(i + 1) % n]
			out += [a.lerp(b, 0.25), a.lerp(b, 0.75)]
		if not closed:
			out.append(pts[-1])
		pts = out
	return pts


def band(name: str, pts: list, width: float, thick: float, side: Vector, mat, closed: bool = False) -> bpy.types.Object:
	"""Стропа или мягкая лямка по точкам: ширина — вдоль side (сколько можно поперёк пути), толщина —
	поперёк обоих. closed — кольцо (пояс)."""
	bm = bmesh.new()
	rings = []
	n = len(pts)
	for i, p in enumerate(pts):
		t = (pts[(i + 1) % n] - pts[(i - 1) % n]) if closed else (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
		t.normalize()
		w = (side - t * side.dot(t)).normalized()
		nr = t.cross(w).normalized()
		hw = w * width * 0.5
		hn = nr * thick * 0.5
		rings.append([bm.verts.new(p - hw - hn), bm.verts.new(p + hw - hn), bm.verts.new(p + hw + hn), bm.verts.new(p - hw + hn)])
	pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
	for a, b in pairs:
		for k in range(4):
			bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
	if not closed:
		bm.faces.new(list(reversed(rings[0])))
		bm.faces.new(rings[-1])
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
	me = bpy.data.meshes.new(name)
	bm.to_mesh(me)
	bm.free()
	o = bpy.data.objects.new(name, me)
	bpy.context.collection.objects.link(o)
	bv = o.modifiers.new("bevel", "BEVEL")
	bv.width = min(thick, width) * 0.3
	bv.segments = 2
	B.assign(o, mat)
	return o


def soft(name: str, size: tuple, center: tuple, mat, bevel: float = 0.012, cast: float = 0.08, sub: int = 1, taper: float = 0.0) -> bpy.types.Object:
	o = B.soft_box(name, size, center, bevel=bevel, cast=cast, sub=sub, taper=taper, wrinkle=0.0012)
	B.assign(o, mat)
	return o


def hard(name: str, size: tuple, center: tuple, mat, bevel: float = 0.004) -> bpy.types.Object:
	o = B.block(name, size, center, bevel)
	B.assign(o, mat)
	return o


def mag_pouch(name: str, x: float, y_face: float, z: float, m: dict, w: float = 0.07, d: float = 0.036, h: float = 0.125, mags: int = 1) -> list:
	"""Открытый подсумок под магазин на лицевой стороне (y_face — плоскость панели): из него торчит
	магазин (mags — сколько в глубину), сверху — удерживающая стропа с кнопкой."""
	yc = y_face - d * 0.5
	parts = [soft(name, (w, d, h), (x, yc, z), m["fabric"])]
	top = z + h * 0.5
	for k in range(mags):
		my = yc + (k - (mags - 1) * 0.5) * (d / mags) * 0.92
		parts.append(hard(f"{name}_mag{k}", (w * 0.74, min(0.024, d / mags * 0.72), 0.056), (x, my, top + 0.012), m["mag"], 0.005))
	keep = smooth([V((x, y_face - 0.002, top - 0.02)), V((x, y_face - 0.004, top + 0.047)), V((x, y_face - d + 0.004, top + 0.047)),
		V((x, y_face - d - 0.005, top - 0.012)), V((x, y_face - d - 0.005, z + h * 0.08))], times=1)
	parts.append(band(f"{name}_keep", keep, 0.022, 0.003, X, m["strap"]))
	parts.append(hard(f"{name}_snap", (0.012, 0.004, 0.012), (x, y_face - d - 0.008, z + h * 0.14), m["hw"], 0.002))
	return parts


def flap_pouch(name: str, size: tuple, center: tuple, m: dict, mat_key: str = "fabric") -> list:
	"""Закрытый подсумок с клапаном (аптечка, рация, мелочь): тело, клапан на треть высоты, стропа с пряжкой."""
	w, d, h = size
	x, y, z = center
	body = soft(name, size, center, m[mat_key], bevel=0.014, cast=0.12)
	flap = soft(f"{name}_flap", (w * 1.03, d * 0.5, h * 0.36), (x, y - d * 0.32, z + h * 0.33), m[mat_key], bevel=0.008, cast=0.05)
	web = band(f"{name}_web", [V((x, y - d * 0.6, z + h * 0.3)), V((x, y - d * 0.61, z - h * 0.3))], 0.022, 0.003, X, m["strap"])
	bk = hard(f"{name}_bk", (0.03, 0.008, 0.02), (x, y - d * 0.62, z + h * 0.05), m["hw"])
	return [body, flap, web, bk]


def dump_pouch(name: str, size: tuple, center: tuple, m: dict) -> list:
	"""Сумка сброса: мягкий мешок, сверху открыт — кант по горлу и шнур с фиксатором."""
	w, d, h = size
	x, y, z = center
	bag = soft(name, size, center, m["dump"], bevel=0.02, cast=0.18, taper=-0.12)
	rim = [V((x + math.cos(a) * w * 0.5, y + math.sin(a) * d * 0.5, z + h * 0.44)) for a in [math.tau * i / 20 for i in range(20)]]
	parts = [bag, band(f"{name}_rim", rim, 0.02, 0.006, Z, m["strap"], closed=True)]
	parts.append(hard(f"{name}_lock", (0.014, 0.014, 0.022), (x, y - d * 0.5 - 0.008, z + h * 0.4), m["hw"]))
	return parts


def waist(name: str, rx: float, ry: float, z: float, width: float, m: dict, mat_key: str = "strap", half: bool = True) -> bpy.types.Object:
	"""Стропа вокруг корпуса: полукольцо от края панели через спину или целое кольцо (пояс)."""
	if half:
		pts = [V((math.cos(a) * rx, math.sin(a) * ry, z)) for a in [math.pi * i / 24 for i in range(25)]]
		return band(name, pts, width, 0.004, Z, m[mat_key])
	pts = [V((math.cos(a) * rx, math.sin(a) * ry, z)) for a in [math.tau * i / 48 for i in range(48)]]
	return band(name, pts, width, 0.004, Z, m[mat_key], closed=True)


# ------------------------------------------------------------------ четыре разгрузки

def build_belt(m: dict) -> bpy.types.Object:
	"""Поясная: мягкий пояс со стропой и пряжкой, два подсумка под магазин, сбоку сумка сброса."""
	a, b, zc = 0.165, 0.118, 0.12
	ring = [V((math.cos(t) * a, math.sin(t) * b, zc)) for t in [math.tau * i / 48 for i in range(48)]]
	parts = [band("pad", ring, 0.078, 0.014, Z, m["fabric"], closed=True)]
	parts.append(waist("web", a + 0.009, b + 0.009, zc, 0.045, m, half=False))
	parts.append(hard("buckle", (0.062, 0.016, 0.052), (0, -(b + 0.014), zc), m["hw"], 0.006))
	parts.append(hard("buckle_in", (0.03, 0.02, 0.03), (0, -(b + 0.016), zc), m["mag"], 0.004))
	for i, sx in enumerate((-1, 1)):
		x = sx * 0.088
		yf = -b * math.sqrt(1.0 - (x / a) ** 2) - 0.012
		parts += mag_pouch(f"pouch{i}", x, yf, zc - 0.022, m)
	parts += dump_pouch("dump", (0.06, 0.14, 0.17), (a + 0.04, 0.02, zc - 0.055), m)
	return B.finish("rig_belt", parts)


def build_chest(m: dict) -> bpy.types.Object:
	"""Нагрудная: панель на четыре магазина, Х-образные лямки через плечи, стропа вокруг спины."""
	W, D, H, zc = 0.40, 0.03, 0.17, 0.24
	yf = -D * 0.5 + 0.004
	parts = [soft("panel", (W, D, H), (0, 0, zc), m["fabric"], bevel=0.02, cast=0.04)]
	for i in range(4):
		parts += mag_pouch(f"pouch{i}", (i - 1.5) * 0.094, yf, zc - 0.012, m, w=0.08)
	parts.append(band("molle", [V((-W * 0.46, -D * 0.5 - 0.003, zc + 0.068)), V((W * 0.46, -D * 0.5 - 0.003, zc + 0.068))], 0.022, 0.003, Z, m["strap"]))
	for sx in (-1, 1):
		pts = smooth([V((sx * 0.14, 0.004, zc + H * 0.42)), V((sx * 0.145, 0.03, zc + 0.26)), V((sx * 0.13, 0.11, zc + 0.31)),
			V((sx * 0.085, 0.2, zc + 0.22)), V((0.0, 0.236, zc + 0.10)), V((-sx * 0.15, 0.2, zc - 0.03))])
		parts.append(band(f"strap{sx}", pts, 0.042, 0.005, X, m["strap"]))
		parts.append(hard(f"side_bk{sx}", (0.012, 0.03, 0.046), (sx * (W * 0.5 + 0.012), 0.01, zc - 0.03), m["hw"]))
	parts.append(waist("waist", W * 0.5 + 0.012, 0.236, zc - 0.03, 0.04, m))
	parts.append(hard("back_bk", (0.05, 0.012, 0.05), (0.0, 0.244, zc + 0.10), m["hw"], 0.005))
	return B.finish("rig_chest", parts)


def build_assault(m: dict) -> bpy.types.Object:
	"""Штурмовая: высокая панель, внизу шесть подсумков под магазины, сверху аптечный и радиоподсумок,
	Н-образные мягкие лямки с перемычкой на спине."""
	W, D, H, zc = 0.45, 0.035, 0.28, 0.27
	yf = -D * 0.5 + 0.004
	parts = [soft("panel", (W, D, H), (0, 0, zc), m["fabric"], bevel=0.025, cast=0.04)]
	for i in range(6):
		parts += mag_pouch(f"pouch{i}", (i - 2.5) * 0.071, yf, zc - 0.066, m, w=0.064)
	parts += flap_pouch("admin", (0.16, 0.034, 0.085), (-0.125, yf - 0.017, zc + 0.082), m)
	parts += flap_pouch("small", (0.085, 0.04, 0.085), (0.02, yf - 0.02, zc + 0.082), m)
	parts += flap_pouch("radio", (0.075, 0.048, 0.125), (0.155, yf - 0.024, zc + 0.07), m)
	for sx in (-1, 1):
		pts = smooth([V((sx * 0.15, 0.004, zc + H * 0.42)), V((sx * 0.15, 0.03, zc + 0.3)), V((sx * 0.145, 0.12, zc + 0.36)),
			V((sx * 0.14, 0.21, zc + 0.3)), V((sx * 0.14, 0.25, zc + 0.15)), V((sx * 0.16, 0.24, zc - 0.09))])
		parts.append(band(f"pad{sx}", pts[:len(pts) * 2 // 3], 0.066, 0.016, X, m["fabric"]))
		parts.append(band(f"strap{sx}", pts, 0.03, 0.02, X, m["strap"]))
		parts.append(hard(f"side_bk{sx}", (0.012, 0.03, 0.05), (sx * (W * 0.5 + 0.012), 0.01, zc - 0.09), m["hw"]))
	parts.append(band("yoke", [V((-0.14, 0.255, zc + 0.16)), V((0.14, 0.255, zc + 0.16))], 0.06, 0.012, Z, m["fabric"]))
	parts.append(waist("waist", W * 0.5 + 0.012, 0.245, zc - 0.09, 0.045, m))
	return B.finish("rig_assault", parts)


def build_heavy(m: dict) -> bpy.types.Object:
	"""Тяжёлая: жилет с передней и задней панелью, четыре сдвоенных подсумка (восемь магазинов), над
	ними аптечный, гранатные и радиоподсумок, широкий пояс по бокам с подсумком и сумкой сброса."""
	W, D, H, zc = 0.46, 0.045, 0.42, 0.3
	yf = -D * 0.5 + 0.004
	yb = 0.26
	parts = [soft("front", (W, D, H), (0, 0, zc), m["fabric"], bevel=0.035, cast=0.05),
		soft("back", (W * 0.95, 0.04, H * 1.04), (0, yb, zc + 0.01), m["fabric"], bevel=0.035, cast=0.05)]
	for i in range(4):
		parts += mag_pouch(f"pouch{i}", (i - 1.5) * 0.108, yf, zc - 0.115, m, w=0.092, d=0.062, mags=2)
	parts += flap_pouch("radio", (0.078, 0.05, 0.14), (-0.172, yf - 0.025, zc + 0.085), m)
	parts += flap_pouch("admin", (0.17, 0.036, 0.1), (-0.035, yf - 0.018, zc + 0.065), m)
	for i in range(2):
		parts += flap_pouch(f"nade{i}", (0.062, 0.05, 0.095), (0.105 + i * 0.072, yf - 0.025, zc + 0.062), m)
	for k in range(2):
		parts.append(band(f"molle{k}", [V((-W * 0.44, -D * 0.5 - 0.004, zc + 0.15 + k * 0.035)), V((W * 0.44, -D * 0.5 - 0.004, zc + 0.15 + k * 0.035))], 0.024, 0.003, Z, m["strap"]))
	for k in range(5):
		z = zc - 0.13 + k * 0.07
		parts.append(band(f"back_molle{k}", [V((-W * 0.42, yb + 0.024, z)), V((W * 0.42, yb + 0.024, z))], 0.024, 0.003, Z, m["strap"]))
	parts.append(band("drag", smooth([V((-0.05, yb + 0.01, zc + H * 0.5)), V((-0.035, yb + 0.012, zc + H * 0.5 + 0.045)),
		V((0.035, yb + 0.012, zc + H * 0.5 + 0.045)), V((0.05, yb + 0.01, zc + H * 0.5))], times=1), 0.03, 0.008, V((0, 1, 0)), m["strap"]))
	for sx in (-1, 1):
		pts = smooth([V((sx * 0.155, 0.0, zc + H * 0.44)), V((sx * 0.155, 0.045, zc + 0.3)), V((sx * 0.155, 0.13, zc + 0.325)),
			V((sx * 0.155, 0.215, zc + 0.3)), V((sx * 0.155, yb, zc + H * 0.46))])
		parts.append(band(f"shoulder{sx}", pts, 0.085, 0.02, X, m["fabric"]))
		side = smooth([V((sx * W * 0.49, 0.0, zc - 0.07)), V((sx * (W * 0.5 + 0.035), 0.06, zc - 0.07)), V((sx * (W * 0.5 + 0.04), 0.13, zc - 0.07)),
			V((sx * (W * 0.5 + 0.03), 0.2, zc - 0.07)), V((sx * W * 0.46, yb, zc - 0.07))])
		parts.append(band(f"cummerbund{sx}", side, 0.17, 0.012, Z, m["fabric"]))
	parts += flap_pouch("side", (0.05, 0.1, 0.12), (-(W * 0.5 + 0.075), 0.13, zc - 0.07), m)
	parts += dump_pouch("dump", (0.07, 0.15, 0.2), (W * 0.5 + 0.085, 0.13, zc - 0.1), m)
	return B.finish("rig_heavy", parts)


BUILDERS = {"rig_belt": build_belt, "rig_chest": build_chest, "rig_assault": build_assault, "rig_heavy": build_heavy}


def main() -> None:
	B.OUT.mkdir(parents=True, exist_ok=True)
	only = [a for a in B.ARGS if a in BUILDERS]
	for key, fn in BUILDERS.items():
		if only and key not in only:
			continue
		B.reset()
		o = fn(make_mats(key))
		size, tris = B.measure(o)
		print("RIG", key, "size", size, "tris", tris, flush=True)
		if B.PREVIEW:
			B.render_preview(o, str(Path(B.PREVIEW) / key))
		if not B.SHAPE:
			bpy.ops.object.select_all(action="DESELECT")
			o.select_set(True)
			bpy.ops.export_scene.gltf(filepath=str(B.OUT / f"{key}.glb"), use_selection=True, export_format="GLB",
				export_yup=True, export_apply=True)


if __name__ == "__main__":
	main()
