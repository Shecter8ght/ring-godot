class_name Door
extends Node3D
## Дверь-створка: петля в начале координат узла, полотно уходит вдоль +X. E рядом — открыть/закрыть.
## Створка поворачивается на 90° от игрока (в ту сторону, с которой он подошёл), коллайдер едет с ней.

@export var width: float = 1.0
@export var height: float = 2.2
@export var thickness: float = 0.05
## Заперта, пока у группы нет этого ключа (Raid.team_keys); пусто — обычная дверь.
## Мародёры открывают любые двери — у них свои ключи.
@export var required_key: String = ""

var is_open: bool = false
var _target_angle: float = 0.0
var _players_near: Array[Node3D] = []

@onready var _leaf: StaticBody3D = $Leaf
@onready var _mesh: MeshInstance3D = $Leaf/Mesh
@onready var _shape: CollisionShape3D = $Leaf/Shape
@onready var _zone: Area3D = $Zone
@onready var _zone_shape: CollisionShape3D = $Zone/Shape


func _ready() -> void:
	var box := BoxMesh.new()
	box.size = Vector3(width, height, thickness)
	_mesh.mesh = box
	_mesh.position = Vector3(width * 0.5, height * 0.5, 0.0)
	_mesh.material_override = SectorMaterials.get_material("metal_plate")
	_leaf.collision_layer = Hitscan.LAYER_DOOR
	_leaf.collision_mask = 0
	var col := BoxShape3D.new()
	col.size = box.size
	_shape.shape = col
	_shape.position = _mesh.position
	var zone := BoxShape3D.new()
	zone.size = Vector3(width + 1.6, height, 3.0)
	_zone_shape.shape = zone
	_zone_shape.position = Vector3(width * 0.5, height * 0.5, 0.0)
	_zone.collision_layer = 0
	_zone.collision_mask = Hitscan.LAYER_PLAYER | Hitscan.LAYER_MARAUDER
	_zone.body_entered.connect(_on_body_entered)
	_zone.body_exited.connect(_on_body_exited)
	if Net.is_networked():
		_setup_sync()


## Дверь строится одинаково на каждом peer из тех же данных сектора (детерминированно),
## поэтому спавнер не нужен — просто синхронизируем состояние. Авторитет — хост по умолчанию.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:is_open", "Leaf:rotation"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	add_child(sync)


func _on_body_entered(body: Node3D) -> void:
	if body is Player:
		_players_near.append(body)
	elif body is Marauder and not is_open and is_multiplayer_authority():
		# Мародёр открывает дверь сам — и это слышно. Тело мародёра реплицировано на всех peer,
		# поэтому Area3D сработает у каждого; открывает только хост (он авторитет двери).
		toggle(body.global_position)
		NoiseBus.emit(global_position, 10.0, "door")


func _on_body_exited(body: Node3D) -> void:
	_players_near.erase(body)


func _process(delta: float) -> void:
	if not _players_near.is_empty() and Input.is_action_just_pressed("interact"):
		var who := _players_near[0]
		if (who as Player).is_local():
			if _locked():
				Raid.current.notify("Заперто: нужен " + Raid.current.key_name(required_key))
				return
			toggle(who.global_position)
			NoiseBus.emit(global_position, 8.0, "door")
	# Анимацию ведёт только авторитет (хост) — иначе локальный лерп к _target_angle=0 у клиента
	# каждый кадр тянул бы створку обратно, деря с прилетающим по сети углом.
	if is_multiplayer_authority():
		_leaf.rotation.y = lerp_angle(_leaf.rotation.y, _target_angle, minf(1.0, Balance.DOOR_SWING_SPEED * delta))


func _locked() -> bool:
	return required_key != "" and Raid.current != null and not Raid.current.has_key(required_key)


## Открыть от того, кто открывает: сторона выбирается по знаку локального Z подошедшего.
## Сеть: если мы не авторитет двери — просим хост, а не толкаем состояние сами.
func toggle(from_world: Vector3) -> void:
	if Net.is_networked() and not is_multiplayer_authority():
		_request_toggle.rpc_id(1, from_world)
		return
	is_open = not is_open
	Audio.play("door", global_position)
	if is_open:
		var local := to_local(from_world)
		_target_angle = (PI * 0.5) if local.z > 0.0 else (-PI * 0.5)
	else:
		_target_angle = 0.0


@rpc("any_peer", "call_remote", "reliable")
func _request_toggle(from_world: Vector3) -> void:
	if is_multiplayer_authority() and not _locked():
		toggle(from_world)
