@tool
class_name RaidStartZone
extends Node3D
## Зона сбора перед рейдом — как зона эвакуации, только на выход: во дворе котельной у ворот. План
## рейда принят у стола планирования и все, кто в убежище, стоят в зоне — идёт короткий отсчёт, и рейд
## начинается (считает HideoutLevel на хосте). Узел ставится в сцену и двигается мышкой.

@export var radius: float = 4.0:
	set(v):
		radius = maxf(1.0, v)
		_rebuild()

var _vis: Node3D
var _mat: StandardMaterial3D
var _label: Label3D


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("raid_start_zones")
	_rebuild()


## Точка внутри зоны: по плану — радиус, по высоте — как у эвакуации.
func contains(p: Vector3) -> bool:
	var d: Vector3 = p - global_position
	return Vector2(d.x, d.z).length() <= radius and absf(d.y) <= Balance.EXTRACT_ZONE_HEIGHT


## Вид зоны: ready — план принят (зелёная), иначе приглушённая; text — надпись над зоной.
func show_state(ready: bool, text: String) -> void:
	if _mat:
		_mat.albedo_color = Color(0.2, 0.85, 0.35, 0.2) if ready else Color(0.85, 0.75, 0.4, 0.08)
	if _label:
		_label.text = text


func _rebuild() -> void:
	if not is_inside_tree():
		return
	if _vis:
		_vis.free()
	_vis = Node3D.new()
	_vis.name = "_Visual"
	add_child(_vis)
	var disc := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = radius
	mesh.bottom_radius = radius
	mesh.height = 0.03
	mesh.radial_segments = 48
	disc.mesh = mesh
	disc.position.y = 0.03
	disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mat = StandardMaterial3D.new()
	_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat.albedo_color = Color(0.85, 0.75, 0.4, 0.08)
	disc.material_override = _mat
	_vis.add_child(disc)
	_label = Label3D.new()
	_label.text = "СБОР ПЕРЕД РЕЙДОМ"
	_label.pixel_size = 0.006
	_label.font_size = 44
	_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_label.modulate = Color(1.0, 0.92, 0.7)
	_label.outline_size = 10
	_label.position.y = 2.6
	_vis.add_child(_label)
