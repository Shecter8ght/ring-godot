@tool
class_name ExtractionPoint
extends Marker3D
## Точка эвакуации: зона радиусом radius, условие (текстом, пока без механики) и время канала.
## Двигается мышкой в сцене уровня; круг зоны виден и в редакторе, и в игре (блокаут).

@export var display_name: String = "":
	set(v):
		display_name = v
		_rebuild()
@export var radius: float = 4.0:
	set(v):
		radius = maxf(1.0, v)
		_rebuild()
## Условие открытия — для дизайна; механику добавит цикл рейда (лут/ключи/рубильник).
@export_multiline var rule: String = ""
## Сколько стоять в зоне до эвакуации, с.
@export var channel_s: float = 8.0

var _vis: Node3D


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("extractions")
	_rebuild()


func _rebuild() -> void:
	if not is_inside_tree():
		return
	if _vis:
		_vis.free()
	_vis = Node3D.new()
	_vis.name = "_Visual"
	add_child(_vis)
	var disc := MeshInstance3D.new()
	var cyl := CylinderMesh.new()
	cyl.top_radius = radius
	cyl.bottom_radius = radius
	cyl.height = 0.04
	cyl.radial_segments = 48
	disc.mesh = cyl
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.2, 0.85, 0.35, 0.28)
	m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	disc.material_override = m
	disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	disc.position.y = 0.03
	_vis.add_child(disc)
	var label := Label3D.new()
	label.text = "ЭВАКУАЦИЯ · " + display_name
	label.pixel_size = 0.02
	label.font_size = 48
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color(0.45, 1.0, 0.55)
	label.outline_size = 10
	label.position.y = 3.0
	_vis.add_child(label)
