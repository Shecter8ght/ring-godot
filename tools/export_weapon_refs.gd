extends Node
## Выгрузка моделей оружия игры в GLB — опора для хватов и анимаций рук в Blender.
## Запуск: tools/godot.cmd --headless res://tools/export_weapon_refs.tscn -- out=<папка>
## Каждое оружие — в осях игры (начало — середина пистолетной рукояти, +Z — к дулу, +Y — вверх,
## −X — правая сторона стрелка). Пустышки RightGrip/LeftGrip — где кисти стоят сейчас,
## Muzzle/SightFront/SightRear — дульный срез и линия прицеливания (по meta модели).
## Отдельно — автомат с каждым обвесом, который меняет хват левой руки.

const GRIP_MODS: Array[String] = ["grip_vertical_01", "grip_offset_01", "tac_flashlight_01"]
const GRIP_WEAPON: String = "wpn_ar_02"


func _ready() -> void:
	var out_dir: String = ""
	for argument: String in OS.get_cmdline_user_args():
		if argument.begins_with("out="):
			out_dir = argument.trim_prefix("out=")
	if out_dir == "":
		push_error("export_weapon_refs: нужен аргумент out=<папка>")
		get_tree().quit(1)
		return
	DirAccess.make_dir_recursive_absolute(out_dir)
	var failures: int = 0
	var manifest: Dictionary = {}
	for id: String in WeaponDb.weapon_ids():
		failures += _export(id, {}, out_dir.path_join(id + ".glb"), manifest)
	for mod_id: String in GRIP_MODS:
		var name: String = GRIP_WEAPON + "__" + mod_id
		failures += _export(GRIP_WEAPON, {"underbarrel" if mod_id.begins_with("grip") else "side_left": {"id": mod_id}}, out_dir.path_join(name + ".glb"), manifest, name)
	var file: FileAccess = FileAccess.open(out_dir.path_join("manifest.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(manifest, "  "))
	file.close()
	print("export_weapon_refs: %d файлов, ошибок %d" % [manifest.size(), failures])
	get_tree().quit(1 if failures > 0 else 0)


## Цвет материала с учётом текстуры: средний цвет картинки × albedo_color.
static func _average_color(source: Material) -> Color:
	if not source is BaseMaterial3D:
		return Color(0.3, 0.3, 0.3)
	var material: BaseMaterial3D = source as BaseMaterial3D
	var color: Color = material.albedo_color
	if material.albedo_texture:
		var image: Image = material.albedo_texture.get_image()
		if image:
			image = image.duplicate() as Image
			if image.is_compressed():
				image.decompress()
			image.resize(1, 1, Image.INTERPOLATE_BILINEAR)
			color *= image.get_pixel(0, 0)
	return color


func _export(id: String, mods: Dictionary, path: String, manifest: Dictionary, key: String = "") -> int:
	var model: Node3D = WeaponModels.build(id, mods)
	var root: Node3D = Node3D.new()
	root.name = key if key != "" else id
	add_child(root)
	root.add_child(model)
	# скрытое (LOD1, лишние патроны, снятые обвесы) не выгружаем: импорт Blender не знает
	# расширение видимости узлов glTF и отказывается открывать файл
	for node: Node in model.find_children("*", "Node3D", true, false):
		if is_instance_valid(node) and not (node as Node3D).visible:
			node.get_parent().remove_child(node)
			node.queue_free()
	# деталь «магазин» процедурной модели — по имени, чтобы в Blender её можно было двигать
	for node: Node in model.find_children("*", "MeshInstance3D", true, false):
		if String(node.get_meta("part", "")) == "mag":
			node.name = "Magazine"
	# образцу для хвата текстуры не нужны: простой цвет материала, файл в десятки раз легче
	for node: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mesh_instance: MeshInstance3D = node as MeshInstance3D
		var source: Material = mesh_instance.material_override
		if source == null and mesh_instance.mesh and mesh_instance.mesh.get_surface_count() > 0:
			source = mesh_instance.get_active_material(0)
		var flat: StandardMaterial3D = StandardMaterial3D.new()
		flat.albedo_color = _average_color(source)
		flat.roughness = 0.7
		mesh_instance.material_override = flat
	# meta → пустышки: в glTF meta не попадают
	for meta_name: String in ["muzzle", "sight_front", "sight_rear"]:
		if model.has_meta(meta_name):
			var empty: Marker3D = Marker3D.new()
			empty.name = {"muzzle": "Muzzle", "sight_front": "SightFront", "sight_rear": "SightRear"}[meta_name]
			empty.position = model.get_meta(meta_name) as Vector3
			root.add_child(empty)
	var weapon: Dictionary = WeaponDb.weapon(id)
	var info: Dictionary = {
		"id": id,
		"name": String(weapon.get("name", id)),
		"class": String((weapon.get("weapon", {}) as Dictionary).get("class", "")),
		"model": String((weapon.get("weapon", {}) as Dictionary).get("model", "")),
		"asset": model.get_meta("asset_loaded", false),
		"mods": mods,
		"sight_h": model.get_meta("sight_h", 0.0),
		"ads_z": model.get_meta("ads_z", 0.0),
	}
	var document: GLTFDocument = GLTFDocument.new()
	var state: GLTFState = GLTFState.new()
	var error: Error = document.append_from_scene(root, state)
	if error == OK:
		error = document.write_to_filesystem(state, path)
	root.queue_free()
	if error != OK:
		push_error("export_weapon_refs: %s — ошибка %d" % [path, error])
		return 1
	manifest[root.name] = info
	print("export_weapon_refs: ", path)
	return 0
