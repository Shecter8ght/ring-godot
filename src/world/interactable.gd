@tool
class_name Interactable
extends Node3D
## То, с чем игрок что-то делает клавишей F, стоя рядом (Balance.INTERACT_RADIUS): ключ, рубильник.
## Подсказку и нажатие ведёт Raid (ближайший к локальному игроку). Действие всегда выполняет
## хост — клиент только просит. Узлы ставятся в сцену уровня и двигаются мышкой.

var _vis: Node3D


func _ready() -> void:
	if not Engine.is_editor_hint():
		add_to_group("interactables")
	_rebuild()


## Можно ли сейчас что-то сделать (ключ ещё не подобран, рубильник выключен).
func can_use() -> bool:
	return true


## Текст подсказки после «F — ».
func prompt() -> String:
	return ""


## Локальный игрок нажал F: без сети — сразу, в сети — просим хост.
func request_use() -> void:
	if Net.is_networked() and not multiplayer.is_server():
		_request.rpc_id(1)
	else:
		_use()


@rpc("any_peer", "call_remote", "reliable")
func _request() -> void:
	if multiplayer.is_server() and can_use():
		_use()


## Действие на хосте — переопределяют наследники.
func _use() -> void:
	pass


## Видимая часть (блокаут): пересобирается при смене параметров, в сцену не сохраняется.
func _rebuild() -> void:
	if not is_inside_tree():
		return
	if _vis:
		_vis.free()
	_vis = Node3D.new()
	_vis.name = "_Visual"
	add_child(_vis)
	_build_visual(_vis)


func _build_visual(_parent: Node3D) -> void:
	pass


func _box(parent: Node3D, pos: Vector3, size: Vector3, color: Color, glow: float = 0.0) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.position = pos
	var m := StandardMaterial3D.new()
	m.albedo_color = color
	if glow > 0.0:
		m.emission_enabled = true
		m.emission = color
		m.emission_energy_multiplier = glow
	mi.material_override = m
	parent.add_child(mi)
	return mi


func _label(parent: Node3D, text: String, y: float, color: Color) -> void:
	var l := Label3D.new()
	l.text = text
	l.pixel_size = 0.01
	l.font_size = 40
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.modulate = color
	l.outline_size = 8
	l.position.y = y
	parent.add_child(l)
