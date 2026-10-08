"""Рюкзаки RING (предметы bp_daypack / bp_tourist / bp_raid): модели в Blender по фото-референсам.
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_backpacks.py [-- --shape] [-- --preview DIR]

Референсы (Wikimedia Commons, просмотрены): патрульный MOLLE 40 л (ряды стропы по всему переду,
округлый верх), армейский рюкзак MOLLE на солдате (основной мешок, боковые подсумки, клапан),
трекинговый с клапаном, стяжками и поясным ремнём, городской со скруглённым верхом и карманом.
Размеры — как у реальных: городской ~25 л 47×30×20 см (Ferrino Rocker 25), туристический ~50 л
64×31×24, рейдовый ~60 л 65×35×30 (5.11 RUSH100, Brandit MOLLE 66L).

Ткань — Poly Haven CC0 (terlenka, stretch_poplin, book_pattern), перекрашена под рюкзак
(_asset_src/backpacks/tex, не в git). Оси Blender: X — ширина, −Y — перёд рюкзака (лицо), +Y —
спинка, Z — вверх; низ рюкзака — z = 0. Экспорт glTF (+Y вверх): в Godot перёд — +Z, спинка — −Z.
Пишет assets/items/models/bp_*.glb.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "_asset_src/backpacks/tex"
OUT = ROOT / "assets/items/models"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
SHAPE = "--shape" in ARGS
PREVIEW = ARGS[ARGS.index("--preview") + 1] if "--preview" in ARGS else ""

# цвета (sRGB 0..255): основа, стропа/лямки, фурнитура, молния/акцент, сетка/низ
COLORS = {
	"bp_daypack": {"fabric": (44, 46, 50), "strap": (30, 31, 33), "hw": (18, 18, 19), "accent": (128, 32, 26), "mesh": (24, 25, 27)},
	"bp_tourist": {"fabric": (66, 76, 66), "strap": (34, 35, 37), "hw": (20, 20, 21), "accent": (150, 92, 40), "mesh": (36, 37, 39)},
	"bp_raid": {"fabric": (88, 86, 60), "strap": (76, 75, 52), "hw": (24, 24, 22), "accent": (70, 68, 48), "mesh": (60, 59, 42)},
}
FABRIC_TEX = {"bp_daypack": "terlenka", "bp_tourist": "stretch_poplin", "bp_raid": "book_pattern"}
TILE_M = 0.22  # метров на повтор ткани


def reset() -> None:
	bpy.ops.wm.read_factory_settings(use_empty=True)
	bpy.context.scene.unit_settings.system = "METRIC"


# ------------------------------------------------------------------ материалы

def tinted_np(tex_id: str, color: tuple, out_name: str, contrast: float = 0.7) -> Path:
	"""То же без PIL — средствами Blender (картинка → пиксели → своя картинка)."""
	path = TEX / f"{out_name}.png"
	img = bpy.data.images.load(str(TEX / f"{tex_id}_diff.jpg"))
	w, h = img.size
	px = list(img.pixels)
	lum = [0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2] for i in range(0, len(px), 4)]
	mean = sum(lum) / len(lum)
	col = [((c / 255.0) ** 2.2) for c in color]
	out = [0.0] * len(px)
	for j, l in enumerate(lum):
		k = 1.0 + contrast * (l / mean - 1.0)
		for c in range(3):
			out[j * 4 + c] = max(0.0, min(1.0, (col[c] * k) ** (1 / 2.2)))
		out[j * 4 + 3] = 1.0
	o = bpy.data.images.new(out_name, w, h)
	o.pixels = out
	o.filepath_raw = str(path)
	o.file_format = "PNG"
	o.save()
	bpy.data.images.remove(img)
	return path


def material(name: str, color: tuple, tex_id: str | None, rough: float = 0.9, contrast: float = 0.7) -> bpy.types.Material:
	m = bpy.data.materials.new(name)
	m.use_nodes = True
	nt = m.node_tree
	bsdf = nt.nodes["Principled BSDF"]
	bsdf.inputs["Roughness"].default_value = rough
	if SHAPE or tex_id is None:
		bsdf.inputs["Base Color"].default_value = (*[(c / 255.0) ** 2.2 for c in color], 1.0) if not SHAPE else (0.5, 0.5, 0.5, 1.0)
		return m
	img = nt.nodes.new("ShaderNodeTexImage")
	img.image = bpy.data.images.load(str(tinted_np(tex_id, color, name, contrast)))
	nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
	nimg = nt.nodes.new("ShaderNodeTexImage")
	nimg.image = bpy.data.images.load(str(TEX / f"{tex_id}_nor.jpg"))
	nimg.image.colorspace_settings.name = "Non-Color"
	nmap = nt.nodes.new("ShaderNodeNormalMap")
	nt.links.new(nimg.outputs["Color"], nmap.inputs["Color"])
	nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
	rimg = nt.nodes.new("ShaderNodeTexImage")
	rimg.image = bpy.data.images.load(str(TEX / f"{tex_id}_rough.jpg"))
	rimg.image.colorspace_settings.name = "Non-Color"
	nt.links.new(rimg.outputs["Color"], bsdf.inputs["Roughness"])
	return m


# ------------------------------------------------------------------ формы

def soft_box(name: str, size: tuple, center: tuple, bevel: float = 0.05, cast: float = 0.2, sub: int = 2,
			 taper: float = 0.0, wrinkle: float = 0.0025) -> bpy.types.Object:
	"""Мягкий объём ткани: коробка → фаска → сглаживание → «подушка» (Cast к сфере) → лёгкие складки.
	taper — насколько верх уже низа (доля)."""
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
	o = bpy.context.object
	o.name = name
	o.scale = size
	bpy.ops.object.transform_apply(scale=True)
	if taper:
		for v in o.data.vertices:
			if v.co.z > 0:
				v.co.x *= 1.0 - taper
				v.co.y *= 1.0 - taper * 0.6
	b = o.modifiers.new("bevel", "BEVEL")
	b.width = bevel
	b.segments = 3
	b.limit_method = "NONE"
	s = o.modifiers.new("sub", "SUBSURF")
	s.levels = sub
	s.render_levels = sub
	c = o.modifiers.new("cast", "CAST")
	c.factor = cast
	c.cast_type = "SPHERE"
	if wrinkle > 0:
		t = bpy.data.textures.new(name + "_wr", "CLOUDS")
		t.noise_scale = 0.06
		d = o.modifiers.new("wr", "DISPLACE")
		d.texture = t
		d.strength = wrinkle
		d.mid_level = 0.5
	return o


def block(name: str, size: tuple, center: tuple, bevel: float = 0.004) -> bpy.types.Object:
	"""Жёсткая мелочь: пряжка, фиксатор, ручка-скоба."""
	bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
	o = bpy.context.object
	o.name = name
	o.scale = size
	bpy.ops.object.transform_apply(scale=True)
	b = o.modifiers.new("bevel", "BEVEL")
	b.width = bevel
	b.segments = 2
	return o


def bake(o: bpy.types.Object) -> None:
	"""Модификаторы — в сетку (дальше по ней кладём лямки и стропы)."""
	dg = bpy.context.evaluated_depsgraph_get()
	ev = o.evaluated_get(dg)
	me = bpy.data.meshes.new_from_object(ev)
	o.modifiers.clear()
	old = o.data
	o.data = me
	bpy.data.meshes.remove(old)


def bvh(objs: list) -> BVHTree:
	bm = bmesh.new()
	for o in objs:
		tmp = bmesh.new()
		tmp.from_mesh(o.data)
		tmp.transform(o.matrix_world)
		me = bpy.data.meshes.new("tmp")
		tmp.to_mesh(me)
		bm.from_mesh(me)
		bpy.data.meshes.remove(me)
		tmp.free()
	tree = BVHTree.FromBMesh(bm)
	bm.free()
	return tree


def on_surface(tree: BVHTree, p: Vector, d: Vector, lift: float, keep: bool = True) -> Vector | None:
	"""Точку p — на поверхность, луч по направлению d (к телу); приподнять на lift. Промах — p
	(keep) или None."""
	hit = tree.ray_cast(p - d * 0.5, d, 2.0)
	if hit[0] is None:
		return p if keep else None
	return hit[0] + hit[1] * lift


def ribbon(name: str, pts: list, width: float, thick: float, out_hint: Vector, round_k: int = 1) -> bpy.types.Object:
	"""Лента по точкам (лямка, стропа, молния): ширина — поперёк пути и «наружу» (out_hint), толщина
	— наружу. Мягкие края — фаска и сглаживание."""
	bm = bmesh.new()
	rings = []
	for i, p in enumerate(pts):
		t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
		w = t.cross(out_hint).normalized()
		n = w.cross(t).normalized()
		hw = w * width * 0.5
		hn = n * thick * 0.5
		rings.append([bm.verts.new(p - hw - hn), bm.verts.new(p + hw - hn), bm.verts.new(p + hw + hn), bm.verts.new(p - hw + hn)])
	for a, b in zip(rings, rings[1:]):
		for k in range(4):
			bm.faces.new((a[k], a[(k + 1) % 4], b[(k + 1) % 4], b[k]))
	bm.faces.new(list(reversed(rings[0])))
	bm.faces.new(rings[-1])
	me = bpy.data.meshes.new(name)
	bm.to_mesh(me)
	bm.free()
	o = bpy.data.objects.new(name, me)
	bpy.context.collection.objects.link(o)
	if round_k:
		b = o.modifiers.new("bevel", "BEVEL")
		b.width = min(thick, width) * 0.3
		b.segments = 2
	return o


def path_on(tree: BVHTree, a: Vector, b: Vector, d: Vector, lift: float, n: int = 16, bulge: float = 0.0, bulge_dir: Vector | None = None) -> list:
	"""Путь из a в b по поверхности (лучи по d); bulge — выгиб наружу (лямка отходит от спинки)."""
	out = []
	for i in range(n + 1):
		t = i / n
		p = a.lerp(b, t)
		# мимо поверхности (край клапана) — точку пропускаем, а не вешаем в воздухе
		q = on_surface(tree, p, d, lift, keep=False)
		if q is None:
			continue
		if bulge and bulge_dir is not None:
			q += bulge_dir * bulge * math.sin(math.pi * t)
		out.append(q)
	return out


# ------------------------------------------------------------------ сборка

def assign(o: bpy.types.Object, m: bpy.types.Material) -> None:
	o.data.materials.clear()
	o.data.materials.append(m)


def uv_box(o: bpy.types.Object) -> None:
	"""UV по ведущей оси нормали (ткань без растяжек), повтор — TILE_M метров."""
	bm = bmesh.new()
	bm.from_mesh(o.data)
	uv = bm.loops.layers.uv.new("UVMap") if not bm.loops.layers.uv else bm.loops.layers.uv[0]
	for f in bm.faces:
		n = f.normal
		ax = max(range(3), key=lambda i: abs(n[i]))
		for lp in f.loops:
			p = o.matrix_world @ lp.vert.co
			if ax == 0:
				lp[uv].uv = (p.y / TILE_M, p.z / TILE_M)
			elif ax == 1:
				lp[uv].uv = (p.x / TILE_M, p.z / TILE_M)
			else:
				lp[uv].uv = (p.x / TILE_M, p.y / TILE_M)
	bm.to_mesh(o.data)
	bm.free()


def finish(name: str, parts: list) -> bpy.types.Object:
	"""Всё — в одну сетку с несколькими материалами, сглаживание, UV, низ в нуле."""
	for o in parts:
		bpy.context.view_layer.objects.active = o
		bake(o)
		uv_box(o)
	bpy.ops.object.select_all(action="DESELECT")
	for o in parts:
		o.select_set(True)
	bpy.context.view_layer.objects.active = parts[0]
	bpy.ops.object.join()
	o = bpy.context.object
	o.name = name
	for p in o.data.polygons:
		p.use_smooth = True
	mn = min((o.matrix_world @ v.co).z for v in o.data.vertices)
	o.location.z -= mn
	bpy.ops.object.transform_apply(location=True)
	return o


def shoulder_straps(tree, body_w, top_z, bot_z, back_y, m_strap, m_hw, pad_w=0.065, gap=0.11):
	parts = []
	for sx in (-1, 1):
		a = Vector((sx * gap * 0.55, back_y, top_z))
		b = Vector((sx * gap * 1.55, back_y, bot_z))
		pts = path_on(tree, a, b, Vector((0, -1, 0)), 0.012, 18, bulge=0.06, bulge_dir=Vector((0, 1, 0)))
		s = ribbon(f"strap_{sx}", pts, pad_w, 0.018, Vector((0, 1, 0)))
		s.modifiers.new("sub", "SUBSURF").levels = 1
		assign(s, m_strap)
		parts.append(s)
		# регулировочная стропа снизу и пряжка
		lo = pts[-1]
		web = ribbon(f"strap_web_{sx}", [lo, lo + Vector((sx * 0.02, -0.01, -0.07))], 0.025, 0.004, Vector((0, 1, 0)))
		assign(web, m_strap)
		bk = block(f"strap_bk_{sx}", (0.032, 0.008, 0.02), tuple(lo + Vector((0, 0.004, -0.015))))
		assign(bk, m_hw)
		parts += [web, bk]
	return parts


def grab_handle(tree, top_z, back_y, m_strap):
	pts = [Vector((-0.04, back_y - 0.02, top_z - 0.01)), Vector((-0.025, back_y - 0.02, top_z + 0.025)),
		   Vector((0.025, back_y - 0.02, top_z + 0.025)), Vector((0.04, back_y - 0.02, top_z - 0.01))]
	h = ribbon("handle", pts, 0.025, 0.008, Vector((0, 1, 0)))
	assign(h, m_strap)
	return [h]


def molle_rows(tree, x0, x1, z0, z1, y_front, m_web, step=0.038, h=0.025, face=Vector((0, 1, 0)), name="molle"):
	"""Ряды стропы MOLLE по поверхности (лицо — луч по +Y к телу)."""
	parts = []
	z = z0
	i = 0
	while z <= z1:
		pts = path_on(tree, Vector((x0, y_front, z)), Vector((x1, y_front, z)), face, 0.0035, 20)
		r = ribbon(f"{name}_{i}", pts, h, 0.0035, -face, round_k=1)
		assign(r, m_web)
		parts.append(r)
		z += step
		i += 1
	return parts


def build_daypack(mats) -> bpy.types.Object:
	W, D, H = 0.30, 0.20, 0.47
	body = soft_box("body", (W, D, H), (0, 0, H / 2), bevel=0.07, cast=0.22, taper=0.08)
	bake(body)
	assign(body, mats["fabric"])
	tree = bvh([body])
	parts = [body]
	# передний карман: нижняя половина, пухлый
	pk = soft_box("pocket", (W * 0.82, 0.06, H * 0.42), (0, -D * 0.47, H * 0.3), bevel=0.04, cast=0.25)
	bake(pk)
	assign(pk, mats["fabric"])
	parts.append(pk)
	tree = bvh([body, pk])
	# молнии: верх основного отделения (дуга через верх) и кармана
	arc = []
	for i in range(25):
		a = math.pi * i / 24
		p = Vector((-math.cos(a) * W * 0.46, -D * 0.1, H * 0.6 + math.sin(a) * H * 0.38))
		arc.append(on_surface(tree, p, (Vector((0.0, p.y, H * 0.5)) - p).normalized(), 0.003))
	z1 = ribbon("zip1", arc, 0.009, 0.003, Vector((0, -1, 0)))
	z2 = ribbon("zip2", path_on(tree, Vector((-W * 0.36, -0.2, H * 0.48)), Vector((W * 0.36, -0.2, H * 0.48)), Vector((0, 1, 0)), 0.003, 16), 0.009, 0.003, Vector((0, -1, 0)))
	for z in (z1, z2):
		assign(z, mats["hw"])
	pulls = [block("pull1", (0.012, 0.006, 0.03), tuple(arc[4] + Vector((0, -0.006, -0.012)))),
			 block("pull2", (0.012, 0.006, 0.03), tuple(on_surface(tree, Vector((W * 0.3, -0.2, H * 0.45)), Vector((0, 1, 0)), 0.006)))]
	for p in pulls:
		assign(p, mats["accent"])
	# боковые сетчатые карманы под бутылку
	sides = []
	for sx in (-1, 1):
		sp = soft_box(f"side_{sx}", (0.035, D * 0.7, H * 0.32), (sx * W * 0.5, 0, H * 0.18), bevel=0.015, cast=0.2)
		assign(sp, mats["mesh"])
		sides.append(sp)
	parts += [z1, z2] + pulls + sides
	parts += shoulder_straps(tree, W, H * 0.9, H * 0.12, D * 0.6, mats["strap"], mats["hw"])
	parts += grab_handle(tree, H * 0.98, D * 0.3, mats["strap"])
	return finish("bp_daypack", parts)


def build_tourist(mats) -> bpy.types.Object:
	W, D, H = 0.31, 0.24, 0.64
	body = soft_box("body", (W, D, H * 0.86), (0, 0, H * 0.43), bevel=0.06, cast=0.16, taper=0.1)
	bake(body)
	assign(body, mats["fabric"])
	# низ — отделение спальника, тёмное
	bottom = soft_box("bottom", (W * 1.01, D * 1.01, H * 0.2), (0, 0, H * 0.1), bevel=0.05, cast=0.15)
	bake(bottom)
	assign(bottom, mats["mesh"])
	# клапан сверху, свисает вперёд
	# клапан лежит на горловине (с нахлёстом, без щели)
	lid = soft_box("lid", (W * 0.95, D * 1.05, 0.1), (0, -0.015, H * 0.845), bevel=0.04, cast=0.22)
	bake(lid)
	assign(lid, mats["accent"])
	tree = bvh([body, bottom, lid])
	parts = [body, bottom, lid]
	# стяжки клапана — две вертикальные стропы по переду с пряжками
	for sx in (-1, 1):
		pts = path_on(tree, Vector((sx * W * 0.25, -0.3, H * 0.86)), Vector((sx * W * 0.25, -0.3, H * 0.5)), Vector((0, 1, 0)), 0.004, 14)
		s = ribbon(f"lidstrap_{sx}", pts, 0.022, 0.004, Vector((0, -1, 0)))
		assign(s, mats["strap"])
		bk = block(f"lidbk_{sx}", (0.034, 0.01, 0.022), tuple(pts[len(pts) // 2] + Vector((0, -0.006, 0))))
		assign(bk, mats["hw"])
		parts += [s, bk]
	# боковые стяжки — по две на сторону
	for sx in (-1, 1):
		for zk in (0.35, 0.62):
			pts = path_on(tree, Vector((sx * 0.3, D * 0.4, H * zk)), Vector((sx * 0.3, -D * 0.4, H * zk)), Vector((-sx, 0, 0)), 0.004, 12)
			s = ribbon(f"comp_{sx}_{zk}", pts, 0.02, 0.004, Vector((sx, 0, 0)))
			assign(s, mats["strap"])
			bk = block(f"compbk_{sx}_{zk}", (0.01, 0.034, 0.022), tuple(pts[len(pts) // 2] + Vector((sx * 0.006, 0, 0))))
			assign(bk, mats["hw"])
			parts += [s, bk]
	# спинка с каркасом — плотная тёмная панель
	back = soft_box("back", (W * 0.86, 0.035, H * 0.7), (0, D * 0.5, H * 0.45), bevel=0.015, cast=0.05)
	assign(back, mats["mesh"])
	parts.append(back)
	tree = bvh([body, bottom, lid, back])
	parts += shoulder_straps(tree, W, H * 0.82, H * 0.2, D * 0.8, mats["strap"], mats["hw"], pad_w=0.07)
	# поясной ремень — «крылья» вперёд по бокам
	for sx in (-1, 1):
		# плавная дуга от спинки вперёд вокруг корпуса
		pts = []
		for i in range(13):
			th = math.radians(18.0 + 92.0 * i / 12)
			pts.append(Vector((sx * W * 0.62 * math.sin(th), D * 0.08 + D * 0.55 * math.cos(th), H * 0.11)))
		hb = ribbon(f"hip_{sx}", pts, 0.09, 0.022, Vector((0, 0, 1)))
		hb.modifiers.new("sub", "SUBSURF").levels = 1
		assign(hb, mats["strap"])
		parts.append(hb)
	parts += grab_handle(tree, H * 0.86, D * 0.45, mats["strap"])
	return finish("bp_tourist", parts)


def build_raid(mats) -> bpy.types.Object:
	W, D, H = 0.35, 0.30, 0.65
	body = soft_box("body", (W, D, H * 0.9), (0, 0, H * 0.45), bevel=0.05, cast=0.1, taper=0.04, wrinkle=0.002)
	bake(body)
	assign(body, mats["fabric"])
	lid = soft_box("lid", (W * 1.02, D * 1.02, 0.11), (0, -0.01, H * 0.885), bevel=0.035, cast=0.15)
	bake(lid)
	assign(lid, mats["fabric"])
	# передний подсумок
	fp = soft_box("front_pouch", (W * 0.75, 0.09, H * 0.38), (0, -D * 0.55, H * 0.32), bevel=0.025, cast=0.08)
	bake(fp)
	assign(fp, mats["fabric"])
	# боковые подсумки
	sps = []
	for sx in (-1, 1):
		sp = soft_box(f"side_pouch_{sx}", (0.1, D * 0.62, H * 0.5), (sx * (W * 0.5 + 0.05), -0.01, H * 0.36), bevel=0.025, cast=0.08)
		bake(sp)
		assign(sp, mats["fabric"])
		sps.append(sp)
	tree = bvh([body, lid, fp] + sps)
	parts = [body, lid, fp] + sps
	# MOLLE: перед основного мешка над подсумком, перед подсумков, бока подсумков
	parts += molle_rows(tree, -W * 0.44, W * 0.44, H * 0.55, H * 0.82, -0.6, mats["strap"], name="m_front")
	parts += molle_rows(tree, -W * 0.33, W * 0.33, H * 0.18, H * 0.45, -0.6, mats["strap"], name="m_fpouch")
	# бока подсумков — ряды поперёк по глубине
	for sx in (-1, 1):
		z = H * 0.16
		i = 0
		while z <= H * 0.56:
			pts = path_on(tree, Vector((sx * 0.5, D * 0.2, z)), Vector((sx * 0.5, -D * 0.35, z)), Vector((-sx, 0, 0)), 0.0035, 12)
			r = ribbon(f"ms_{sx}_{i}", pts, 0.025, 0.0035, Vector((sx, 0, 0)))
			assign(r, mats["strap"])
			parts.append(r)
			z += 0.038
			i += 1
	# стяжки клапана с пряжками
	for sx in (-1, 1):
		pts = path_on(tree, Vector((sx * W * 0.28, -0.6, H * 0.9)), Vector((sx * W * 0.28, -0.6, H * 0.6)), Vector((0, 1, 0)), 0.006, 14)
		s = ribbon(f"lidstrap_{sx}", pts, 0.025, 0.004, Vector((0, -1, 0)))
		assign(s, mats["strap"])
		bk = block(f"lidbk_{sx}", (0.038, 0.012, 0.026), tuple(pts[len(pts) // 2] + Vector((0, -0.007, 0))))
		assign(bk, mats["hw"])
		parts += [s, bk]
	back = soft_box("back", (W * 0.85, 0.03, H * 0.72), (0, D * 0.5, H * 0.45), bevel=0.012, cast=0.04)
	assign(back, mats["mesh"])
	parts.append(back)
	tree = bvh([body, lid, back])
	parts += shoulder_straps(tree, W, H * 0.85, H * 0.15, D * 0.75, mats["strap"], mats["hw"], pad_w=0.075)
	parts += grab_handle(tree, H * 0.9, D * 0.4, mats["strap"])
	return finish("bp_raid", parts)


BUILDERS = {"bp_daypack": build_daypack, "bp_tourist": build_tourist, "bp_raid": build_raid}


def make_mats(key: str) -> dict:
	c = COLORS[key]
	tex = FABRIC_TEX[key]
	return {
		"fabric": material(f"{key}_fabric", c["fabric"], tex, 0.9),
		"strap": material(f"{key}_strap", c["strap"], tex, 0.85, 0.5),
		"hw": material(f"{key}_hw", c["hw"], None, 0.55),
		"accent": material(f"{key}_accent", c["accent"], tex, 0.85),
		"mesh": material(f"{key}_mesh", c["mesh"], tex, 0.95, 1.0),
	}


def measure(o) -> tuple:
	vs = [o.matrix_world @ v.co for v in o.data.vertices]
	mn = Vector((min(v.x for v in vs), min(v.y for v in vs), min(v.z for v in vs)))
	mx = Vector((max(v.x for v in vs), max(v.y for v in vs), max(v.z for v in vs)))
	return tuple(round(x, 3) for x in (mx - mn)), sum(len(p.vertices) - 2 for p in o.data.polygons)


def render_preview(o, out_png: str) -> None:
	sc = bpy.context.scene
	sc.render.engine = "CYCLES"
	sc.cycles.samples = 48
	sc.cycles.device = "GPU"
	sc.render.resolution_x = 900
	sc.render.resolution_y = 700
	world = bpy.data.worlds.new("w")
	world.color = (0.35, 0.36, 0.38)
	sc.world = world
	size, _ = measure(o)
	h = size[2]
	cam_data = bpy.data.cameras.new("cam")
	cam = bpy.data.objects.new("cam", cam_data)
	bpy.context.collection.objects.link(cam)
	sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
	sun.data.energy = 3.5
	sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(30))
	bpy.context.collection.objects.link(sun)
	sc.camera = cam
	views = [("front", (0.9, -1.6, h * 0.75)), ("back", (-0.9, 1.6, h * 0.75)), ("side", (1.7, -0.2, h * 0.6))]
	for tag, pos in views:
		cam.location = Vector(pos)
		d = Vector((0, 0, h * 0.45)) - cam.location
		cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
		cam_data.lens = 50
		sc.render.filepath = f"{out_png}_{tag}.png"
		bpy.ops.render.render(write_still=True)
	bpy.data.objects.remove(cam, do_unlink=True)
	bpy.data.objects.remove(sun, do_unlink=True)


def main() -> None:
	OUT.mkdir(parents=True, exist_ok=True)
	for key, fn in BUILDERS.items():
		reset()
		mats = make_mats(key)
		o = fn(mats)
		size, tris = measure(o)
		print("BACKPACK", key, "size", size, "tris", tris, flush=True)
		if PREVIEW:
			render_preview(o, str(Path(PREVIEW) / key))
		if not SHAPE:
			bpy.ops.object.select_all(action="DESELECT")
			o.select_set(True)
			bpy.ops.export_scene.gltf(filepath=str(OUT / f"{key}.glb"), use_selection=True, export_format="GLB",
									  export_yup=True, export_apply=True)


main()
