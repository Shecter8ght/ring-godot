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
## Открыта, только когда включён рубильник с этим id (PowerSwitch.switch_id); пусто — не нужен.
@export var required_switch: String = ""
## Открыта, только когда у группы есть ключ с этим id (KeyPickup.key_id); пусто — не нужен.
@export var required_key: String = ""
## Вместо рубильника: ключ с этим id у кого-то в зоне открывает и без питания (брелок ворот); пусто — нет.
@export var alt_key: String = ""
## В какой доле рейдов открыта (1 — всегда); бросает хост при старте рейда.
@export_range(0.0, 1.0, 0.05) var chance: float = 1.0
## Только без рюкзака (лаз, труба): с надетым рюкзаком игрок в зоне не считается.
@export var no_backpack: bool = false

var _vis: Node3D
var _disc_mat: StandardMaterial3D
var _open_shown: int = -1


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("extractions")
	_rebuild()


## Точка внутри зоны: по плану — радиус, по высоте — Balance.EXTRACT_ZONE_HEIGHT.
func contains(p: Vector3) -> bool:
	var d := p - global_position
	return Vector2(d.x, d.z).length() <= radius and absf(d.y) <= Balance.EXTRACT_ZONE_HEIGHT


## Цвет зоны по состоянию: зелёная — открыта, красная — закрыта (рубильник/ключ).
func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or Raid.current == null or _disc_mat == null:
		return
	var open := 1 if Raid.current.extraction_block_reason(self) == "" else 0
	if open == _open_shown:
		return
	_open_shown = open
	_disc_mat.albedo_color = Color(0.2, 0.85, 0.35, 0.28) if open == 1 else Color(0.9, 0.25, 0.2, 0.28)


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
	_disc_mat = m
	_open_shown = -1
	disc.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	disc.position.y = 0.03
	_vis.add_child(disc)
	var label := Label3D.new()
	label.text = "ЭВАКУАЦИЯ · " + display_name
	label.pixel_size = 0.007
	label.font_size = 48
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color(0.45, 1.0, 0.55)
	label.outline_size = 10
	label.position.y = 3.0
	label.add_to_group(Settings.MAP_LABEL_GROUP)
	_vis.add_child(label)
