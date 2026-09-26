@tool
class_name MallBreaker
extends Interactable
## Главный рубильник света ТЦ (электрощитовая): F — следующее положение: выкл → аварийный → весь
## свет → выкл. Генератор стоит — только аварийный (весь свет — после ремонта генератора).
## После «свет погас» (кто-то щёлкнул в щитовой) — поднять обратно; можно и выключить самому,
## чтобы уйти в темноту с ПНВ. Щелчок слышно далеко — мародёры идут проверить щитовую.
## Состояние — RaidEvents (breaker, generator_down), решает хост.

@export var display_name: String = "Главный рубильник ТЦ":
	set(v):
		display_name = v
		_rebuild()

## Лампы положений: выкл, аварийный, весь свет; рычаг.
var _lamps: Array[MeshInstance3D] = []
var _lever: Node3D


func _ready() -> void:
	super._ready()
	if not Engine.is_editor_hint():
		add_to_group("power_points")


func can_use() -> bool:
	return RaidEvents.current != null


func prompt() -> String:
	var ev := RaidEvents.current
	if ev == null:
		return display_name
	var nxt := ev.next_breaker()
	# что будет гореть после щелчка
	var res := "off" if nxt == "off" else ("emergency" if ev.generator_down or nxt == "emergency" else "on")
	var t := String({"off": "выключить свет в ТЦ", "emergency": "включить аварийный свет", "on": "включить весь свет"}.get(res, ""))
	if ev.generator_down and res == "emergency":
		t += " (генератор стоит — весь свет после ремонта %s)" % ev.generator().where
	return "%s: %s" % [display_name, t]


func _use(_peer_id: int) -> void:
	var ev := RaidEvents.current
	if ev == null:
		return
	ev.set_breaker(ev.next_breaker())
	Audio.play("breaker", global_position + Vector3.UP * 1.2)
	NoiseBus.emit(global_position, Balance.NOISE_SWITCH * 1.5, "switch")


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or _lamps.is_empty():
		return
	var ev := RaidEvents.current
	var pos := ev.breaker if ev else "on"
	var eff := ev.effective_power() if ev else "on"
	var lit := {"off": 0, "emergency": 1, "on": 2}
	for i in range(_lamps.size()):
		(_lamps[i] as MeshInstance3D).visible = int(lit.get(eff, 2)) == i
	# рычаг: внизу — выкл, посередине — аварийный, вверху — весь
	_lever.rotation.x = {"off": 0.7, "emergency": 0.0, "on": -0.7}.get(pos, 0.0)


func _build_visual(parent: Node3D) -> void:
	_lamps.clear()
	# шкаф ВРУ на стене (лицом к -Z узла)
	_box(parent, Vector3(0, 1.2, 0), Vector3(1.3, 2.0, 0.45), Color(0.33, 0.36, 0.34))
	_box(parent, Vector3(0, 1.2, -0.23), Vector3(1.2, 1.9, 0.02), Color(0.4, 0.43, 0.41))
	# табличка «ВРУ-0.4» и полосы
	_box(parent, Vector3(0, 2.0, -0.25), Vector3(0.6, 0.12, 0.01), Color(0.9, 0.85, 0.2))
	# рычаг на оси
	_lever = Node3D.new()
	_lever.position = Vector3(0.3, 1.2, -0.27)
	parent.add_child(_lever)
	_box(_lever, Vector3(0, 0, -0.12), Vector3(0.06, 0.06, 0.24), Color(0.12, 0.12, 0.12))
	_box(_lever, Vector3(0, 0, -0.26), Vector3(0.22, 0.07, 0.07), Color(0.75, 0.12, 0.1))
	# три лампы: выкл (красная), аварийный (оранжевая), весь свет (зелёная)
	var cols := [Color(1.0, 0.2, 0.12), Color(1.0, 0.55, 0.1), Color(0.3, 1.0, 0.4)]
	for i in range(3):
		_box(parent, Vector3(-0.35, 1.55 - 0.22 * i, -0.25), Vector3(0.12, 0.12, 0.03), Color(0.15, 0.15, 0.15))
		_lamps.append(_box(parent, Vector3(-0.35, 1.55 - 0.22 * i, -0.27), Vector3(0.1, 0.1, 0.03), cols[i], 3.0))
	_label(parent, display_name, 2.5, Color(1.0, 0.85, 0.6))
