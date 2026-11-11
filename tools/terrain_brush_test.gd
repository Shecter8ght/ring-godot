extends Node3D
## «Кисть земли» без редактора (addons/ring_level_tools): у земель «Пригорода» и «Санатория» — маски грунта, пути
## сохранения, показ правки маски в шейдере, правка высот с пересборкой плиток, сохранение без впекания выемок.
##   tools/godot.cmd --headless res://tools/terrain_brush_test.tscn
## Файлы не пишет.

const LEVELS: Array = [
	["Пригород", "res://scenes/levels/zone01/zone01_world.tscn", "Terrain", 5],
	["Санаторий", "res://scenes/levels/sanatorium_study.tscn", "Terrain", 8],
]

var fails: int = 0
var checks: int = 0


func _ready() -> void:
	Profile.use_file("user://terrain_brush_test.json", true)
	for job: Array in LEVELS:
		var level: Node3D = (load(String(job[1])) as PackedScene).instantiate() as Node3D
		if level.get_script() != null and String(job[0]) == "Пригород":
			level.set_script(null)
		add_child(level)
		await get_tree().physics_frame
		await get_tree().physics_frame
		_check_terrain(String(job[0]), level.get_node(String(job[2])), int(job[3]))
		level.queue_free()
		await get_tree().physics_frame
	print("terrain_brush_test: проверок %d, провалов %d" % [checks, fails])
	get_tree().quit(mini(fails, 255))


func _check(label: String, ok: bool, details: String = "") -> void:
	checks += 1
	if not ok:
		fails += 1
	print("terrain_brush_test: %s · %s %s" % ["PASS" if ok else "FAIL", label, details])


func _check_terrain(title: String, t: Node, grounds: int) -> void:
	_check("%s: земля в группе blockout_terrain" % title, t.is_in_group("blockout_terrain"))
	var names: PackedStringArray = t.call("brush_grounds")
	_check("%s: грунтов %d" % [title, grounds], names.size() == grounds, str(names))
	var masks: Array = t.call("brush_masks")
	var channels: PackedInt32Array = t.call("brush_mask_channels")
	var paths: PackedStringArray = t.call("brush_mask_paths")
	var total: int = 0
	for c: int in channels:
		total += c
	_check("%s: каналов масок = грунтов − 1" % title, total == grounds - 1 and masks.size() == channels.size(), "%d" % total)
	var exist: bool = not paths.is_empty()
	for p: String in paths:
		exist = exist and p != "" and FileAccess.file_exists(p)
	_check("%s: маски есть на диске" % title, exist, str(paths))
	var img: Image = masks[0]
	_check("%s: маска — живая картинка без мипов, RGBA8" % title, img != null and not img.has_mipmaps() and img.get_format() == Image.FORMAT_RGBA8)
	var c0: Color = img.get_pixel(10, 10)
	img.set_pixel(10, 10, Color(1, 0, 0, 0))
	t.call("brush_push_masks")
	var mat: ShaderMaterial = t.get("_material") as ShaderMaterial
	var tex: Variant = mat.get_shader_parameter("splat")
	_check("%s: правка маски — в шейдере" % title, tex is ImageTexture and (tex as ImageTexture).get_image().get_pixel(10, 10).r > 0.99)
	img.set_pixel(10, 10, c0)
	# высоты: клетка посреди сетки +1 м, плитки пересобраны, сохраняется — тоже +1
	var cells: Vector2i = t.call("cells")
	var origin: Vector2 = t.call("cell_origin")
	var step: float = float(t.call("cell_step"))
	var i: int = cells.x / 2
	var j: int = cells.y / 2
	var x: float = origin.x + float(i) * step
	var z: float = origin.y + float(j) * step
	var before: float = float(t.call("height_at", x, z))
	var data: PackedFloat32Array = (t.call("heights_data") as PackedFloat32Array).duplicate()
	var saved_before: float = (t.call("heights_for_save") as PackedFloat32Array)[j * cells.x + i]
	data[j * cells.x + i] += 1.0
	t.call("set_heights_data", data)
	t.call("rebuild_area", Rect2(x - 2.0, z - 2.0, 4.0, 4.0))
	var after: float = float(t.call("height_at", x, z))
	var saved_after: float = (t.call("heights_for_save") as PackedFloat32Array)[j * cells.x + i]
	_check("%s: высота +1 м в клетке" % title, absf(after - before - 1.0) < 0.01, "%.3f → %.3f" % [before, after])
	_check("%s: к сохранению — тоже +1 м" % title, absf(saved_after - saved_before - 1.0) < 0.01)
	_check("%s: путь карты высот" % title, FileAccess.file_exists(String(t.call("heights_path"))), String(t.call("heights_path")))
