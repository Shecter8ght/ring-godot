"""Обломки попаданий для ImpactBurst: лоупольные куски вместо процедурных — по 3–4 варианта на вид.

  chip     — крошка бетона, асфальта, гравия: выпуклый угловатый осколок (оболочка случайных точек);
  flake    — плоский скол (плитка, краска, пластик): неправильный многоугольник толщиной в долю;
  splinter — щепка: вытянутая, с рваными концами, чуть изогнута;
  clod     — ком земли: бугристый, со сглаженными гранями;
  pebble   — камешек гравия: окатанный, приплюснутый;
  blade    — травинка: изогнутая сужающаяся лента с перекрутом;
  shard    — осколок стекла: тонкая острая пластинка;
  paper    — клочок картона: неровный, с перегибом.
Размер — наибольшая сторона 1 (частицы масштабируют сами), центр — в середине куска. Грани чуть
разной яркости (цвет вершин): кусок в 2 см читается объёмным; цвет материала даёт частица.
Выход: assets/models/props/impact_debris/impact_debris.glb (объекты <вид>_<N>); для просмотра —
E:\\Models Blender\\ENVIRONMENT\\RING_Impact_Holes_Debris\\models\\impact_debris.blend.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/build_impact_debris.py
затем tools/godot.cmd --headless --import
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "assets", "models", "props", "impact_debris", "impact_debris.glb")
LIBRARY = r"E:\Models Blender\ENVIRONMENT\RING_Impact_Holes_Debris"
COUNTS = {"chip": 4, "flake": 3, "splinter": 4, "clod": 4, "pebble": 4, "blade": 3, "shard": 4, "paper": 3}


def hull(points):
	bm = bmesh.new()
	for p in points:
		bm.verts.new(p)
	bmesh.ops.convex_hull(bm, input=bm.verts)
	# внутренние точки, не попавшие в оболочку, — убрать
	loose = [v for v in bm.verts if not v.link_faces]
	bmesh.ops.delete(bm, geom=loose, context="VERTS")
	return bm


def chip(rng):
	pts = []
	scale = Vector((1.0, rng.uniform(0.7, 0.95), rng.uniform(0.55, 0.85)))
	for i in range(int(rng.integers(9, 15))):
		d = Vector(rng.normal(size=3)).normalized()
		pts.append(Vector((d.x * scale.x, d.y * scale.y, d.z * scale.z)) * rng.uniform(0.6, 1.0))
	return hull(pts)


def pebble(rng):
	pts = []
	scale = Vector((1.0, rng.uniform(0.7, 0.95), rng.uniform(0.45, 0.65)))
	for i in range(int(rng.integers(18, 26))):
		d = Vector(rng.normal(size=3)).normalized()
		pts.append(Vector((d.x * scale.x, d.y * scale.y, d.z * scale.z)) * rng.uniform(0.92, 1.0))
	# окатанный: много точек почти на одной поверхности, сглаженные грани (shade_smooth)
	return hull(pts)


def clod(rng):
	bm = bmesh.new()
	bmesh.ops.create_icosphere(bm, subdivisions=2, radius=0.5)
	squash = Vector((1.0, rng.uniform(0.75, 1.0), rng.uniform(0.6, 0.85)))
	seeds = [Vector(rng.normal(size=3)).normalized() for i in range(6)]
	for v in bm.verts:
		d = v.co.normalized()
		bump = sum(max(0.0, d.dot(s)) ** 6 * rng.uniform(0.1, 0.25) for s in seeds)
		v.co = Vector((d.x * squash.x, d.y * squash.y, d.z * squash.z)) * (0.5 + bump + rng.uniform(-0.04, 0.04))
	return bm


def slab(rng, sides, thickness, jag):
	"""Плоский многоугольник с толщиной (скол, осколок, клочок)."""
	angles = np.sort(rng.uniform(0, math.tau, sides))
	pts = [Vector((math.cos(a) * rng.uniform(1.0 - jag, 1.0), math.sin(a) * rng.uniform(1.0 - jag, 1.0) * rng.uniform(0.55, 0.9), 0.0)) for a in angles]
	bm = bmesh.new()
	verts = [bm.verts.new(p) for p in pts]
	face = bm.faces.new(verts)
	res = bmesh.ops.extrude_face_region(bm, geom=[face])
	moved = [g for g in res["geom"] if isinstance(g, bmesh.types.BMVert)]
	bmesh.ops.translate(bm, verts=moved, vec=Vector((0, 0, thickness)))
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	return bm


def flake(rng):
	return slab(rng, int(rng.integers(5, 8)), rng.uniform(0.08, 0.14), 0.35)


def shard(rng):
	bm = slab(rng, int(rng.integers(3, 5)), rng.uniform(0.03, 0.05), 0.15)
	# острый: одну вершину вытянуть
	tip = max(bm.verts, key=lambda v: v.co.length)
	tip.co.xy *= rng.uniform(1.3, 1.8)
	return bm


def paper(rng):
	bm = slab(rng, int(rng.integers(5, 7)), 0.02, 0.4)
	fold = rng.uniform(-0.25, 0.25)
	for v in bm.verts:
		if v.co.x > fold:
			v.co.z += (v.co.x - fold) * rng.uniform(0.3, 0.7)
	return bm


def splinter(rng):
	"""Щепка: призма вдоль Y с рваными концами и лёгким изгибом."""
	bm = bmesh.new()
	rings = 6
	w = rng.uniform(0.06, 0.12)
	t = w * rng.uniform(0.4, 0.8)
	bend = rng.uniform(-0.08, 0.08)
	prev = None
	for i in range(rings):
		s = i / (rings - 1)
		y = s - 0.5
		taper = 1.0 - abs(s - 0.45) * rng.uniform(0.6, 1.2)
		taper = max(0.15, taper)
		off = bend * math.sin(s * math.pi)
		ring = [bm.verts.new((off + dx * w * taper, y, dz * t * taper)) for dx, dz in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
		if prev:
			for k in range(4):
				bm.faces.new((prev[k], prev[(k + 1) % 4], ring[(k + 1) % 4], ring[k]))
		prev = ring if i else ring
		if i == 0:
			first = ring
	# концы — рваные: остриё со смещением
	for ring, sign in ((first, -1.0), (prev, 1.0)):
		tip = bm.verts.new((rng.uniform(-w, w) * 0.5, sign * (0.5 + rng.uniform(0.02, 0.08)), rng.uniform(-t, t) * 0.5))
		for k in range(4):
			bm.faces.new((ring[k], ring[(k + 1) % 4], tip))
	bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
	return bm


def blade(rng):
	"""Травинка: лента из 5 звеньев, сужается к кончику, изогнута и чуть перекручена."""
	bm = bmesh.new()
	segs = 5
	curl = rng.uniform(0.15, 0.4)
	twist = rng.uniform(-0.6, 0.6)
	width = rng.uniform(0.07, 0.11)
	prev = None
	for i in range(segs + 1):
		s = i / segs
		w = width * (1.0 - s * 0.9)
		y = s - 0.5
		z = curl * s * s
		a = twist * s
		dx = math.cos(a) * w * 0.5
		dz = math.sin(a) * w * 0.5
		pair = (bm.verts.new((-dx, y, z - dz)), bm.verts.new((dx, y, z + dz)))
		if prev:
			bm.faces.new((prev[0], prev[1], pair[1], pair[0]))
		prev = pair
	return bm


MAKERS = {"chip": chip, "flake": flake, "splinter": splinter, "clod": clod, "pebble": pebble, "blade": blade, "shard": shard, "paper": paper}
SMOOTH = {"clod", "pebble", "blade"}


def finish(name, bm, rng, smooth):
	"""Центр в середину, наибольшая сторона 1, цвет граней чуть разный, объект в сцене."""
	bm.verts.ensure_lookup_table()
	lo = Vector((min(v.co.x for v in bm.verts), min(v.co.y for v in bm.verts), min(v.co.z for v in bm.verts)))
	hi = Vector((max(v.co.x for v in bm.verts), max(v.co.y for v in bm.verts), max(v.co.z for v in bm.verts)))
	center = (lo + hi) * 0.5
	extent = max(hi - lo)
	for v in bm.verts:
		v.co = (v.co - center) / extent
	layer = bm.loops.layers.float_color.new("Col")
	for face in bm.faces:
		shade = rng.uniform(0.82, 1.0)
		for loop in face.loops:
			loop[layer] = (shade, shade, shade, 1.0)
	mesh = bpy.data.meshes.new(name)
	bm.to_mesh(mesh)
	bm.free()
	if smooth:
		mesh.shade_smooth()
	else:
		mesh.shade_flat()
	obj = bpy.data.objects.new(name, mesh)
	bpy.context.scene.collection.objects.link(obj)
	return obj


def main():
	bpy.ops.wm.read_factory_settings(use_empty=True)
	rng = np.random.default_rng(55107)
	objects = []
	for row, (kind, count) in enumerate(COUNTS.items()):
		for index in range(count):
			obj = finish("%s_%d" % (kind, index), MAKERS[kind](rng), rng, kind in SMOOTH)
			obj.location = (index * 1.6, -row * 1.6, 0.0)
			objects.append(obj)
			print(obj.name, len(obj.data.polygons), "граней")
	os.makedirs(os.path.dirname(OUT), exist_ok=True)
	# в GLB — в начале координат (ImpactBurst берёт сетки, а не места)
	places = {o.name: o.location.copy() for o in objects}
	for o in objects:
		o.location = (0, 0, 0)
	kwargs = {"filepath": OUT, "export_format": "GLB", "export_materials": "NONE", "export_yup": True}
	try:
		bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kwargs)
	except TypeError:
		bpy.ops.export_scene.gltf(**kwargs)
	print("GLB:", OUT)
	for o in objects:
		o.location = places[o.name]
	mat = bpy.data.materials.new("debris_clay")
	mat.use_nodes = True
	nt = mat.node_tree
	attr = nt.nodes.new("ShaderNodeVertexColor")
	attr.layer_name = "Col"
	nt.links.new(attr.outputs["Color"], nt.nodes["Principled BSDF"].inputs["Base Color"])
	for o in objects:
		o.data.materials.append(mat)
	for row, kind in enumerate(COUNTS):
		bpy.ops.object.text_add(location=(-2.2, -row * 1.6, 0.0))
		label = bpy.context.active_object
		label.data.body = kind
		label.data.size = 0.4
	bpy.ops.object.light_add(type="SUN", location=(0, 0, 4))
	bpy.context.active_object.rotation_euler = (math.radians(40), 0.0, math.radians(30))
	bpy.context.active_object.data.energy = 4.0
	models = os.path.join(LIBRARY, "models")
	os.makedirs(models, exist_ok=True)
	path = os.path.join(models, "impact_debris.blend")
	bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
	print("просмотр:", path)


if __name__ == "__main__":
	main()
