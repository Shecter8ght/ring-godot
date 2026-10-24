@tool
class_name IlyaCar
extends Node3D
## Машина Ильи (заказ «Вернуть машину»): неподвижное купе assets/models/props/coupe_ilya/coupe_ilya.glb
## (сборка — tools/coupe_ilya/game_*.py). Игрок её не водит; состояния ставит сцена ангара по Quests.durable /
## Quests.flag (логика заказа — отдельно): колесо стоит или машина на кирпичах, аккумулятор стоит (экраны
## горят) или снят, капот открыт. Узлы модели — Body, Hood, Wheel_FL…RR, WheelOff_FL, Battery_Installed,
## Battery_Missing; в каждом — сетки <узел>_LOD0/1/2, дальности — Balance.VEHICLE_LOD.

const INFO: String = "res://assets/models/props/coupe_ilya/coupe_ilya.json"
## Низ шин в модели — плоское пятно контакта ровно на уровне земли (y = 0, 12 вершин на каждом колесе):
## на любом ровном полу оно мерцает с поверхностью (z-fighting «под всеми машинами», владелец 2026-10-24).
## Модель опускается на сантиметр — шина чуть «вдавлена» в землю, пятно под полом. Геометрия, не баланс.
const GROUND_SINK_M: float = 0.01

## Переднее левое колесо на месте (иначе — кирпичи и поворотный кулак).
@export var wheel_fitted: bool = false:
	set(value):
		wheel_fitted = value
		_apply()
## Аккумулятор стоит, клеммы на нём, экраны в салоне горят.
@export var battery_installed: bool = false:
	set(value):
		battery_installed = value
		_apply()
## Капот открыт (угол петли — из coupe_ilya.json, как в модели Blender).
@export var hood_open: bool = true:
	set(value):
		hood_open = value
		_apply()

var _hood_open_rad: float = 0.0


func _ready() -> void:
	var model: Node3D = get_node_or_null("Model") as Node3D
	if model != null:
		model.position.y = -GROUND_SINK_M
	var info: Variant = JSON.parse_string(FileAccess.get_file_as_string(INFO))
	if info is Dictionary:
		_hood_open_rad = float(((info as Dictionary).get("hood", {}) as Dictionary).get("open_rad", 0.0))
	_set_lod_ranges()
	_apply()


func _apply() -> void:
	if not is_inside_tree():
		return
	_show("Wheel_FL", wheel_fitted)
	_show("WheelOff_FL", not wheel_fitted)
	_show("Battery_Installed", battery_installed)
	_show("Battery_Missing", not battery_installed)
	var hood: Node3D = find_child("Hood", true, false) as Node3D
	if hood != null:
		hood.rotation.x = _hood_open_rad if hood_open else 0.0


func _show(node_name: String, visible_now: bool) -> void:
	var node: Node3D = find_child(node_name, true, false) as Node3D
	if node != null:
		node.visible = visible_now


## Ближняя / средняя / дальняя сетка каждого узла — по расстоянию до камеры, с запасом на возврат.
func _set_lod_ranges() -> void:
	if Engine.is_editor_hint():
		# в редакторе — только ближняя модель (автозагрузки Balance там нет)
		for node: Node in find_children("*_LOD?", "GeometryInstance3D", true, false):
			(node as GeometryInstance3D).visible = String(node.name).ends_with("_LOD0")
		return
	var near: float = float(Balance.VEHICLE_LOD.lod1_m)
	var far: float = float(Balance.VEHICLE_LOD.lod2_m)
	var margin: float = float(Balance.VEHICLE_LOD.margin_m)
	for node: Node in find_children("*_LOD?", "GeometryInstance3D", true, false):
		var geometry: GeometryInstance3D = node as GeometryInstance3D
		var lod: int = int(String(geometry.name).right(1))
		geometry.visibility_range_begin = [0.0, near, far][lod]
		geometry.visibility_range_end = [near, far, 0.0][lod]
		geometry.visibility_range_begin_margin = margin if lod > 0 else 0.0
		geometry.visibility_range_end_margin = margin if lod < 2 else 0.0
