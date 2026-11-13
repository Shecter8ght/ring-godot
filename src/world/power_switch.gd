@tool
class_name PowerSwitch
extends Interactable
## Рубильник: включил — Raid.switches[switch_id] = true (например, питание ворот грузового двора
## для эвакуации с required_switch). Щелчок слышно далеко — мародёры идут проверить.

@export var switch_id: String = "power":
	set(v):
		switch_id = v
		_rebuild()
@export var display_name: String = "Рубильник":
	set(v):
		display_name = v
		_rebuild()
## Туда-сюда (иначе — только включить) и положение до первого щелчка.
@export var toggle: bool = false
@export var default_on: bool = false

var _lamp: MeshInstance3D


func is_on() -> bool:
	return Raid.current != null and bool(Raid.current.switches.get(switch_id, default_on))


func can_use() -> bool:
	return Raid.current != null and (toggle or not is_on())


func prompt() -> String:
	return ("выключить: " if is_on() else "включить: ") + display_name


func _use(_peer_id: int) -> void:
	Raid.current.set_switch(switch_id, not is_on() if toggle else true)
	Audio.play("power_switch", global_position)
	NoiseBus.emit(global_position, Balance.NOISE_SWITCH, "switch")


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or Raid.current == null or _lamp == null:
		return
	var on := is_on()
	var m := _lamp.material_override as StandardMaterial3D
	var c := Color(0.3, 1.0, 0.4) if on else Color(1.0, 0.25, 0.15)
	if m.albedo_color != c:
		m.albedo_color = c
		m.emission = c


func _build_visual(parent: Node3D) -> void:
	# шкаф щита на стене (кладётся у стены, лицом к -Z узла)
	_box(parent, Vector3(0, 1.1, 0), Vector3(0.9, 1.6, 0.35), Color(0.36, 0.38, 0.4))
	_box(parent, Vector3(0.2, 1.2, -0.2), Vector3(0.08, 0.4, 0.08), Color(0.1, 0.1, 0.1))
	_lamp = _box(parent, Vector3(-0.25, 1.75, -0.19), Vector3(0.1, 0.1, 0.04), Color(1.0, 0.25, 0.15), 3.0)
	_label(parent, display_name, 2.3, Color(1.0, 0.85, 0.6), true)
