extends Node
## «Трава издали» (Balance.GRASS.far_look, приём Road to Vostok — docs/research/road_to_vostok.md): рельеф зоны 1
## получает от DistrictGrass карту густоты травы и тот же отрезок, где травинки уходят в землю (far − fade_m … far
## по качеству графики), и обновляет его при смене качества; множители — из Balance. Без окна (только параметры).
## tools/godot.cmd --headless res://tools/far_grass_test.tscn

const ZONE01 := "res://scenes/levels/zone01_mall.tscn"

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	var before: String = Settings.quality
	Settings.set_quality("high")
	await get_tree().process_frame
	var level: Node = (load(ZONE01) as PackedScene).instantiate()
	add_child(level)
	await _frames(3)
	var terrain: DistrictTerrain = level.find_children("*", "DistrictTerrain", true, false).front() as DistrictTerrain
	var grass: DistrictGrass = level.find_children("*", "DistrictGrass", true, false).front() as DistrictGrass
	_check("в зоне 1 есть рельеф и трава", terrain != null and grass != null)
	if terrain and grass:
		var m: ShaderMaterial = terrain._material
		var g: Dictionary = Balance.GRASS
		for q: String in ["high", "low", "medium"]:
			Settings.set_quality(q)
			await _frames(2)
			var far: float = float((g.quality as Dictionary)[q].far)
			var start: float = float(m.get_shader_parameter("grass_far_start"))
			var end: float = float(m.get_shader_parameter("grass_far_end"))
			_check("%s: «трава издали» с края кольца травинок (%.0f–%.0f м)" % [q, far - float(g.fade_m), far],
				is_equal_approx(start, far - float(g.fade_m)) and is_equal_approx(end, far), "%.1f–%.1f" % [start, end])
		var tex: Texture2D = m.get_shader_parameter("grass_density") as Texture2D
		_check("карта густоты травы — та же, что у травинок", tex != null and tex.resource_path == grass.density_map,
			tex.resource_path if tex else "нет")
		_check("размер карты — в метрах, начало — как у травы",
			m.get_shader_parameter("grass_size") == Vector2(tex.get_width(), tex.get_height()) and m.get_shader_parameter("grass_origin") == grass.origin)
		var look: Dictionary = g.far_look
		_check("множители — из Balance.GRASS.far_look", m.get_shader_parameter("grass_far_tint") == look.tint
			and m.get_shader_parameter("grass_far_clumps") == look.clumps)
	Settings.set_quality(before)
	print("far_grass_test: провалено %d" % _fails)
	get_tree().quit(_fails)


func _frames(n: int) -> void:
	for i: int in n:
		await get_tree().process_frame


func _check(what: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_fails += 1
	print("%s %s%s" % ["OK  " if ok else "FAIL", what, ("  (" + detail + ")") if detail != "" else ""])
