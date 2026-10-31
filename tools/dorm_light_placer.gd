extends Node
## Расстановка оставленного людьми света в прогулке по стенду (владелец 2026-10-31: свет ставит сам, по месту).
## L — режим; колесо — вид; Shift + колесо — поворот на 15°; [ / ] — заряд батареек фонаря и налобника;
## ЛКМ — поставить туда, куда смотришь (на стену — падает на пол под точкой взгляда); ПКМ — убрать ближайший к точке.
## Каждая правка сразу пишется в data/blockouts/dorm_found_lights.json — при следующем запуске свет там же.

const FoundLight = preload("res://src/blockout/dorm_found_light.gd")
const PATH: String = "res://data/blockouts/dorm_found_lights.json"
const KINDS: Array[String] = ["flashlight", "headlamp", "lantern", "candles", "chem_green", "chem_yellow", "chem_orange",
	"beacon"]
const LABELS: Dictionary = {"flashlight": "фонарь", "headlamp": "налобник", "lantern": "кемпинговый фонарь",
	"candles": "свечи", "chem_green": "химсвет зелёный", "chem_yellow": "химсвет жёлтый", "chem_orange": "химсвет оранжевый",
	"beacon": "мигалка"}
## Дальше этого точку не берём; убрать — свет не дальше этого от точки взгляда.
const REACH: float = 8.0
const PICK_RADIUS: float = 1.2

var camera: Camera3D
var world: Node3D
var active: bool = false
var kind_index: int = 0
var yaw_offset: float = 0.0
var charge: float = 0.6
var label: Label
var marker: MeshInstance3D
var marker_material: StandardMaterial3D
var data: Dictionary = {}


func setup(view: Camera3D, level: Node3D, hud_root: Control) -> void:
	camera = view
	world = level
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(PATH)) if FileAccess.file_exists(PATH) else null
	data = parsed as Dictionary if parsed is Dictionary else {}
	if not data.has("lights"):
		data["lights"] = []
	label = Label.new()
	label.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	label.position = Vector2(28, -135)
	label.add_theme_font_size_override("font_size", 20)
	label.add_theme_color_override("font_shadow_color", Color.BLACK)
	label.add_theme_constant_override("shadow_offset_x", 1)
	label.add_theme_constant_override("shadow_offset_y", 1)
	label.hide()
	hud_root.add_child(label)
	var sphere: SphereMesh = SphereMesh.new()
	sphere.radius = 0.045
	sphere.height = 0.09
	marker_material = StandardMaterial3D.new()
	marker_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_material.no_depth_test = true
	sphere.material = marker_material
	marker = MeshInstance3D.new()
	marker.name = "LightPlacerMarker"
	marker.mesh = sphere
	marker.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	marker.hide()
	world.add_child(marker)


func toggle() -> void:
	active = not active
	label.visible = active
	marker.visible = active
	_update_label()


func _process(_delta: float) -> void:
	if not active:
		return
	var target: Dictionary = _target()
	marker.visible = not target.is_empty()
	if not target.is_empty():
		marker.global_position = (target.at as Vector3) + Vector3.UP * 0.05
	marker_material.albedo_color = (FoundLight.KINDS[KINDS[kind_index]] as Dictionary).color


## Перехват колеса и кнопок мыши, пока режим включён; true — событие съедено.
func handle(event: InputEvent) -> bool:
	if not active or not event is InputEventMouseButton or not (event as InputEventMouseButton).pressed:
		return false
	if Input.mouse_mode != Input.MOUSE_MODE_CAPTURED:
		return false
	var button: InputEventMouseButton = event as InputEventMouseButton
	match button.button_index:
		MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN:
			var step: int = 1 if button.button_index == MOUSE_BUTTON_WHEEL_DOWN else -1
			if button.shift_pressed:
				yaw_offset = wrapf(yaw_offset + 15.0 * step, -180.0, 180.0)
			else:
				kind_index = posmod(kind_index + step, KINDS.size())
		MOUSE_BUTTON_LEFT:
			_place()
		MOUSE_BUTTON_RIGHT:
			_remove()
		_:
			return false
	_update_label()
	return true


func change_charge(step: float) -> void:
	charge = clampf(snappedf(charge + step, 0.05), 0.1, 1.0)
	_update_label()


func _update_label() -> void:
	if not is_instance_valid(label):
		return
	var kind: String = KINDS[kind_index]
	var parts: Array[String] = ["Свет: %s" % String(LABELS[kind])]
	if kind in ["flashlight", "headlamp"]:
		parts.append("заряд %d %% ([ / ])" % roundi(charge * 100.0))
	parts.append("поворот %+d° (Shift + колесо)" % roundi(yaw_offset))
	parts.append("поставлено %d" % (data.lights as Array).size())
	label.text = " · ".join(parts) + "\nколесо — вид · ЛКМ — поставить · ПКМ — убрать ближайший · L — выйти"


## Куда встанет предмет: точка взгляда на полу, подоконнике, столе; со стены — на пол под ней. Узел стенда — тот,
## чья коллизия под предметом.
func _target() -> Dictionary:
	var from: Vector3 = camera.global_position
	var hit: Dictionary = _ray(from, from - camera.global_basis.z * REACH)
	if hit.is_empty():
		return {}
	if (hit.normal as Vector3).y < 0.7:
		var start: Vector3 = (hit.position as Vector3) + (hit.normal as Vector3) * 0.12
		hit = _ray(start, start + Vector3.DOWN * 4.0)
		if hit.is_empty() or (hit.normal as Vector3).y < 0.7:
			return {}
	var node: Node = hit.collider as Node
	while node != null and node.get("section_id") == null:
		node = node.get_parent()
	if node == null:
		return {}
	return {"at": hit.position as Vector3, "section": node as Node3D}


func _place() -> void:
	var target: Dictionary = _target()
	if target.is_empty():
		return
	var section: Node3D = target.section as Node3D
	var kind: String = KINDS[kind_index]
	# луч фонаря (−Z предмета) — туда, куда смотришь, плюс поворот колесом
	var look: Vector3 = -camera.global_basis.z
	var yaw: float = rad_to_deg(atan2(-look.x, -look.z)) + yaw_offset
	var local: Vector3 = section.to_local(target.at as Vector3)
	var id: String = _free_id("%s_%s" % [String(section.get("section_id")), kind])
	var item: Dictionary = {"id": id, "note": "поставил владелец в прогулке", "kind": kind,
		"section": String(section.get("section_id")),
		"at": [snappedf(local.x, 0.01), snappedf(local.y, 0.005), snappedf(local.z, 0.01)], "yaw": roundi(wrapf(yaw, -180.0, 180.0))}
	if kind in ["flashlight", "headlamp"]:
		item["charge"] = charge
	(data.lights as Array).append(item)
	var source: Node3D = FoundLight.new() as Node3D
	source.name = id
	source.set("kind", kind)
	source.set("charge", float(item.get("charge", 0.6)))
	source.set("seed_value", id.hash())
	source.position = local
	source.rotation_degrees.y = float(item.yaw)
	section.add_child(source)
	_save()


func _remove() -> void:
	var target: Dictionary = _target()
	var aim: Vector3 = target.at if not target.is_empty() else camera.global_position - camera.global_basis.z * 2.0
	var best: Node3D = null
	var best_distance: float = PICK_RADIUS
	for node: Node in get_tree().get_nodes_in_group("dorm_found_lights"):
		var light: Node3D = node as Node3D
		var distance: float = light.global_position.distance_to(aim)
		if distance < best_distance:
			best = light
			best_distance = distance
	if best == null:
		return
	var id: String = String(best.name)
	var kept: Array = []
	for item: Dictionary in data.lights:
		if String(item.id) != id:
			kept.append(item)
	data["lights"] = kept
	best.queue_free()
	_save()


func _free_id(base: String) -> String:
	var taken: Dictionary = {}
	for item: Dictionary in data.lights:
		taken[String(item.id)] = true
	var n: int = 1
	while taken.has("%s_%d" % [base, n]):
		n += 1
	return "%s_%d" % [base, n]


func _save() -> void:
	var file: FileAccess = FileAccess.open(PATH, FileAccess.WRITE)
	if file == null:
		push_error("dorm: не записать %s (%s)" % [PATH, error_string(FileAccess.get_open_error())])
		return
	file.store_string(JSON.stringify(data, " ", false) + "\n")
	file.close()


func _ray(a: Vector3, b: Vector3) -> Dictionary:
	return camera.get_world_3d().direct_space_state.intersect_ray(PhysicsRayQueryParameters3D.create(a, b, 1))
