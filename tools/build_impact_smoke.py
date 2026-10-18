"""Листы кадров дыма и пыли для ImpactBurst: симуляция дыма Blender (Mantaflow), рендер объёма, лист 8×8.

Пресеты (у каждого своя симуляция):
  puff_a, puff_b — клуб пыли от удара: бугристая сфера-источник за несколько кадров раздувается и гаснет,
                   дым ложится рваной оболочкой (несжимаемая жидкость сама из точки не расширяется — её
                   гасит давление), завихрения рвут её в клубы; пыль тяжелее воздуха — оседает и тает;
  wisp           — дымок от металла: тонкая тёплая струйка, поднимается и рвётся.
Кадры — облако с прозрачным фоном, цвет нейтрально-серый (оттенок даёт частица): светлее сверху,
темнее в плотной середине — объём читается и при ровном свете. Лист 8×8 (кадры слева направо,
сверху вниз — как у частиц Godot), к нему карта нормалей из сглаженной плотности — облако
освещают солнце и лампы игры.

Выход: assets/textures/impacts/fx_<пресет>.png и fx_<пресет>_normal.png. Симуляции для просмотра —
E:\\Models Blender\\ENVIRONMENT\\RING_Impact_Holes_Debris\\models\\impact_smoke_<пресет>.blend
(кэш — сотни МБ — не хранится: в Blender область Domain → Bake All).

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/build_impact_smoke.py -- [пресет …] [--res 64] [--frame 128]
затем tools/godot.cmd --headless --import
"""

import math
import os
import shutil
import sys
import time

import bpy
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
OUT = os.path.join(ROOT, "assets", "textures", "impacts")
LIBRARY = r"E:\Models Blender\ENVIRONMENT\RING_Impact_Holes_Debris"
FRAMES = 64
GRID = 8

# пресет: скорость выброса от поверхности и вверх (м/с), плавучесть плотности и тепла, тепло струи,
# сколько кадров бьёт струя, завихрённость, сколько кадров тает, радиус источника, где источник (Z),
# плотность в рендере
# shell — раздувание источника: во сколько раз за сколько кадров, бугры (м), масштаб бугров, сдвиг узора,
# подъём за раздувание (м)
PRESETS = {
	"puff_a": {"normal": 0.0, "up": 0.0, "alpha": -0.12, "beta": 0.0, "heat": 0.0, "emit": 7, "vort": 1.2,
		"dissolve": 45, "radius": 0.06, "z": -0.1, "density": 9.0,
		"shell": {"grow": 5.0, "frames": 7, "lumps": 0.028, "scale": 0.12, "offset": (0.0, 0.0, 0.0), "lift": 0.08, "patches": 0.35}},
	"puff_b": {"normal": 0.0, "up": 0.0, "alpha": -0.08, "beta": 0.0, "heat": 0.0, "emit": 9, "vort": 1.4,
		"dissolve": 50, "radius": 0.055, "z": -0.14, "density": 8.0,
		"shell": {"grow": 5.5, "frames": 9, "lumps": 0.032, "scale": 0.1, "offset": (3.1, 1.7, 0.4), "lift": 0.14, "patches": 0.28}},
	"wisp": {"normal": 0.25, "up": 0.9, "alpha": 0.2, "beta": 1.4, "heat": 1.2, "emit": 30, "vort": 0.9,
		"dissolve": 32, "radius": 0.03, "z": -0.45, "density": 7.0},
}
# сторона области симуляции (м) — она же кадр
DOMAIN = 1.2


def scene_setup(name, res, frame_px, preset, cache):
	bpy.ops.wm.read_factory_settings(use_empty=True)
	scene = bpy.context.scene
	scene.frame_start = 1
	scene.frame_end = FRAMES + 1
	scene.render.fps = 30
	# область симуляции — кадр целиком, открытые стенки — дым уходит, а не отражается
	bpy.ops.mesh.primitive_cube_add(size=DOMAIN, location=(0, 0, 0))
	domain = bpy.context.active_object
	domain.name = "Domain_" + name
	mod = domain.modifiers.new("Fluid", "FLUID")
	mod.fluid_type = "DOMAIN"
	ds = mod.domain_settings
	ds.domain_type = "GAS"
	ds.resolution_max = res
	ds.cache_type = "ALL"
	ds.cache_directory = cache
	ds.cache_frame_start = 1
	ds.cache_frame_end = FRAMES + 1
	ds.alpha = preset["alpha"]
	ds.beta = preset["beta"]
	ds.vorticity = preset["vort"]
	ds.use_dissolve_smoke = True
	ds.dissolve_speed = preset["dissolve"]
	ds.use_dissolve_smoke_log = True
	ds.use_noise = True
	ds.noise_scale = 2
	ds.noise_strength = 1.6
	for side in ("front", "back", "right", "left", "top", "bottom"):
		setattr(ds, "use_collision_border_" + side, False)
	# источник: маленькая сфера, бьёт несколько кадров
	bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=preset["radius"], location=(0, 0, preset["z"]))
	flow = bpy.context.active_object
	flow.name = "Flow_" + name
	fmod = flow.modifiers.new("Fluid", "FLUID")
	fmod.fluid_type = "FLOW"
	fs = fmod.flow_settings
	fs.flow_type = "SMOKE"
	fs.flow_behavior = "INFLOW"
	fs.flow_source = "MESH"
	fs.use_initial_velocity = True
	fs.velocity_normal = preset["normal"]
	fs.velocity_coord = (0.0, 0.0, preset["up"])
	fs.temperature = preset["heat"]
	fs.subframes = 2
	fs.density = 1.0
	fs.keyframe_insert("density", frame=1)
	fs.keyframe_insert("density", frame=preset["emit"])
	fs.density = 0.0
	fs.keyframe_insert("density", frame=preset["emit"] + 1)
	flow.hide_render = True
	if "shell" in preset:
		expanding_shell(flow, fs, preset["shell"])
	# материал дыма: плотность из симуляции, рассеяние нейтрально-серое
	mat = bpy.data.materials.new("smoke")
	mat.use_nodes = True
	nt = mat.node_tree
	nt.nodes.clear()
	out = nt.nodes.new("ShaderNodeOutputMaterial")
	vol = nt.nodes.new("ShaderNodeVolumePrincipled")
	vol.inputs["Color"].default_value = (0.82, 0.82, 0.82, 1.0)
	vol.inputs["Density"].default_value = preset["density"]
	vol.inputs["Anisotropy"].default_value = 0.25
	attr = nt.nodes.new("ShaderNodeAttribute")
	attr.attribute_name = "density"
	mul = nt.nodes.new("ShaderNodeMath")
	mul.operation = "MULTIPLY"
	mul.inputs[1].default_value = preset["density"]
	nt.links.new(attr.outputs["Fac"], mul.inputs[0])
	nt.links.new(mul.outputs["Value"], vol.inputs["Density"])
	nt.links.new(vol.outputs["Volume"], out.inputs["Volume"])
	domain.data.materials.append(mat)
	# свет: ровный белый мир и мягкое солнце сверху-спереди — объём читается, но не «нарисован» светом
	world = bpy.data.worlds.new("World")
	world.use_nodes = True
	world.node_tree.nodes["Background"].inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
	world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
	scene.world = world
	bpy.ops.object.light_add(type="SUN", location=(0, -3, 3))
	sun = bpy.context.active_object
	sun.rotation_euler = (math.radians(35), 0.0, 0.0)
	sun.data.energy = 2.2
	cam_data = bpy.data.cameras.new("cam")
	cam_data.type = "ORTHO"
	cam_data.ortho_scale = DOMAIN
	cam = bpy.data.objects.new("cam", cam_data)
	scene.collection.objects.link(cam)
	cam.location = (0, -5, 0)
	cam.rotation_euler = (math.radians(90), 0.0, 0.0)
	scene.camera = cam
	scene.render.engine = "CYCLES"
	scene.cycles.samples = 64
	scene.cycles.use_denoising = True
	scene.cycles.volume_bounces = 1
	scene.render.film_transparent = True
	scene.render.resolution_x = frame_px
	scene.render.resolution_y = frame_px
	scene.render.image_settings.file_format = "PNG"
	scene.render.image_settings.color_mode = "RGBA"
	scene.view_settings.view_transform = "Standard"
	setup_gpu(scene)
	return domain


def expanding_shell(flow, fs, cfg):
	"""Источник раздувается с замедлением и чуть поднимается; бугры — смещение по шуму; дым — у поверхности."""
	tex = bpy.data.textures.new("lumps", "CLOUDS")
	tex.noise_scale = cfg["scale"]
	tex.noise_depth = 2
	origin = bpy.data.objects.new("lumps_origin", None)
	bpy.context.scene.collection.objects.link(origin)
	origin.location = cfg["offset"]
	disp = flow.modifiers.new("Lumps", "DISPLACE")
	disp.texture = tex
	disp.strength = cfg["lumps"]
	disp.mid_level = 0.5
	disp.texture_coords = "OBJECT"
	disp.texture_coords_object = origin
	z0 = flow.location.z
	flow.keyframe_insert("scale", frame=1)
	flow.keyframe_insert("location", frame=1)
	g = cfg["grow"]
	flow.scale = (g, g, g * 0.85)
	flow.location.z = z0 + cfg["lift"]
	flow.keyframe_insert("scale", frame=cfg["frames"])
	flow.keyframe_insert("location", frame=cfg["frames"])
	# раздувание с замедлением: быстро в начале, плавно в конце
	for kp in keyframes(flow):
		kp.interpolation = "EXPO"
		kp.easing = "EASE_OUT"
	fs.flow_source = "MESH"
	fs.surface_distance = 2.0
	fs.volume_density = 0.35
	# выброс пятнами: клочья и просветы, а не ровный шар
	patches = bpy.data.textures.new("patches", "CLOUDS")
	patches.noise_scale = cfg["patches"]
	patches.contrast = 2.2
	fs.use_texture = True
	fs.noise_texture = patches
	fs.texture_map_type = "AUTO"
	fs.texture_offset = cfg["offset"][0] * 0.3
	fs.use_initial_velocity = True
	fs.velocity_factor = 0.4


def keyframes(obj):
	"""Ключи анимации объекта (в Blender 5 кривые лежат в слоях действия)."""
	action = obj.animation_data.action
	curves = []
	if hasattr(action, "fcurves"):
		curves = list(action.fcurves)
	else:
		for layer in action.layers:
			for strip in layer.strips:
				for bag in strip.channelbags:
					curves.extend(bag.fcurves)
	return [kp for fc in curves for kp in fc.keyframe_points]


def setup_gpu(scene):
	try:
		prefs = bpy.context.preferences.addons["cycles"].preferences
		for backend in ("OPTIX", "CUDA", "HIP"):
			try:
				prefs.compute_device_type = backend
				prefs.get_devices()
				if any(d.type == backend for d in prefs.devices):
					for d in prefs.devices:
						d.use = d.type == backend
					scene.cycles.device = "GPU"
					return
			except TypeError:
				continue
	except Exception as error:
		print("GPU недоступна:", error)


def bake(domain):
	with bpy.context.temp_override(object=domain, active_object=domain, selected_objects=[domain], selected_editable_objects=[domain]):
		bpy.ops.fluid.bake_all()


def render_frames(scene, folder):
	os.makedirs(folder, exist_ok=True)
	paths = []
	for i in range(FRAMES):
		scene.frame_set(i + 2)
		path = os.path.join(folder, "f%03d.png" % i)
		scene.render.filepath = path
		bpy.ops.render.render(write_still=True)
		paths.append(path)
	return paths


def load_rgba(path, size):
	img = bpy.data.images.load(path, check_existing=False)
	if img.size[0] != size:
		img.scale(size, size)
	px = np.empty(size * size * 4, dtype=np.float32)
	img.pixels.foreach_get(px)
	bpy.data.images.remove(img)
	return px.reshape(size, size, 4)


def blur(a, radius):
	"""Размытие квадратом (дважды — почти гаусс), по краям — нули."""
	for _ in range(2):
		k = 2 * radius + 1
		p = np.pad(a, radius, mode="constant")
		c = np.cumsum(np.cumsum(p, axis=0), axis=1)
		c = np.pad(c, ((1, 0), (1, 0)), mode="constant")
		a = (c[k:, k:] - c[:-k, k:] - c[k:, :-k] + c[:-k, :-k]) / (k * k)
	return a


def assemble(name, paths, cell):
	"""Лист 8×8 (кадры сверху вниз — строки картинки Blender идут снизу) и нормали из плотности."""
	size = cell * GRID
	color = np.zeros((size, size, 4), dtype=np.float32)
	normal = np.zeros((size, size, 4), dtype=np.float32)
	for i, path in enumerate(paths):
		px = load_rgba(path, cell)
		col = i % GRID
		row = GRID - 1 - i // GRID
		y0 = row * cell
		x0 = col * cell
		# к краям ячейки прозрачность гаснет: облако, дошедшее до границы области, не режется квадратом
		t = (np.arange(cell) + 0.5) / cell * 2.0 - 1.0
		edge = np.sqrt(t[None, :] ** 2 + t[:, None] ** 2)
		vignette = 1.0 - np.clip((edge - 0.72) / 0.26, 0.0, 1.0) ** 1.5
		raw = px[..., 3]
		alpha = raw * vignette
		# цвет без умножения на прозрачность, светлота кадра — от рендера (объём)
		rgb = np.where(raw[..., None] > 1e-4, px[..., :3] / np.maximum(raw[..., None], 1e-4), 0.0)
		rgb = np.clip(rgb, 0.0, 1.0)
		color[y0:y0 + cell, x0:x0 + cell, :3] = rgb
		color[y0:y0 + cell, x0:x0 + cell, 3] = alpha
		height = blur(alpha, max(1, cell // 40))
		gy, gx = np.gradient(height)
		k = cell / 24.0
		n = np.stack([-gx * k, -gy * k, np.ones_like(gx)], axis=-1)
		n /= np.linalg.norm(n, axis=-1, keepdims=True)
		normal[y0:y0 + cell, x0:x0 + cell, :3] = n * 0.5 + 0.5
		normal[y0:y0 + cell, x0:x0 + cell, 3] = 1.0
	write(name, size, color, "sRGB", os.path.join(OUT, "fx_%s.png" % name))
	write(name + "_normal", size, normal, "Non-Color", os.path.join(OUT, "fx_%s_normal.png" % name))


def write(name, size, pixels, colorspace, path):
	img = bpy.data.images.new(name, size, size, alpha=True)
	img.colorspace_settings.name = colorspace
	img.pixels.foreach_set(np.clip(pixels, 0, 1).astype(np.float32).ravel())
	img.filepath_raw = path
	img.file_format = "PNG"
	img.save()
	bpy.data.images.remove(img)


def main():
	argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
	res = 96
	cell = 128
	only = []
	keep = False
	i = 0
	while i < len(argv):
		if argv[i] == "--keep-frames":
			keep = True
			i += 1
			continue
		if argv[i] == "--res":
			res = int(argv[i + 1])
			i += 2
			continue
		if argv[i] == "--frame":
			cell = int(argv[i + 1])
			i += 2
			continue
		only.append(argv[i])
		i += 1
	os.makedirs(OUT, exist_ok=True)
	models = os.path.join(LIBRARY, "models")
	os.makedirs(models, exist_ok=True)
	for name, preset in PRESETS.items():
		if only and name not in only:
			continue
		t0 = time.time()
		cache = os.path.join(os.environ.get("TEMP", models), "ring_smoke_cache_" + name)
		if os.path.isdir(cache):
			shutil.rmtree(cache)
		domain = scene_setup(name, res, int(cell * 1.25), preset, cache)
		bake(domain)
		t1 = time.time()
		frames = os.path.join(models, "frames_" + name)
		paths = render_frames(bpy.context.scene, frames)
		t2 = time.time()
		assemble(name, paths, cell)
		bpy.ops.wm.save_as_mainfile(filepath=os.path.join(models, "impact_smoke_%s.blend" % name), compress=True)
		if not keep:
			shutil.rmtree(frames)
			shutil.rmtree(cache, ignore_errors=True)
		print("%s: симуляция %.0f с, рендер %.0f с, всего %.0f с" % (name, t1 - t0, t2 - t1, time.time() - t0))


if __name__ == "__main__":
	main()
