class_name Door
extends Node3D
## Дверь-створка: петля в начале координат узла, полотно уходит вдоль +X. E рядом — открыть/закрыть.
## Створка поворачивается на 90° от игрока (в ту сторону, с которой он подошёл), коллайдер едет с ней.

@export var width: float = 1.0
@export var height: float = 2.2
@export var thickness: float = 0.05
## Смещение центра полотна относительно обычной створки, если модель имеет собственный отступ от петли.
@export var leaf_offset: Vector3 = Vector3.ZERO
## В тесном помещении зону можно укоротить, чтобы F у лестницы не задевала дверь.
@export_range(0.3, 5.0) var interaction_depth: float = 3.0
## Заперта для тех, у кого в рюкзаке нет этого ключа (data/items.json); пусто — обычная дверь.
## Мародёры открывают любые двери — у них свои ключи; чужим отрядам (RivalRaids) нужен тот же ключ.
@export var required_key: String = ""
## Электрозамок: без включённого рубильника с этим id (PowerSwitch) не открыть никому — ни с ключом, ни
## мародёрам; пусто — питание не нужно. Решётка хранилища банка «Проспекта» — ключ-карта и питание КТП.
@export var required_switch: String = ""

var is_open: bool = false
var _target_angle: float = 0.0
var _players_near: Array[Node3D] = []

@onready var _leaf: StaticBody3D = $Leaf
@onready var _mesh: MeshInstance3D = $Leaf/Mesh
@onready var _shape: CollisionShape3D = $Leaf/Shape
@onready var _zone: Area3D = $Zone
@onready var _zone_shape: CollisionShape3D = $Zone/Shape


func _ready() -> void:
	add_to_group("doors")
	var box := BoxMesh.new()
	box.size = Vector3(width, height, thickness)
	_mesh.mesh = box
	_mesh.position = Vector3(width * 0.5, height * 0.5, 0.0) + leaf_offset
	_mesh.material_override = SectorMaterials.get_material("metal_plate")
	_leaf.collision_layer = Hitscan.LAYER_DOOR
	_leaf.collision_mask = 0
	var col := BoxShape3D.new()
	col.size = box.size
	_shape.shape = col
	_shape.position = _mesh.position
	var zone := BoxShape3D.new()
	zone.size = Vector3(width + 1.6, height, interaction_depth)
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
	Net.scope_sync(self, sync)
	add_child(sync)


func _on_body_entered(body: Node3D) -> void:
	if body is Player:
		_players_near.append(body)
	elif body is Marauder and not is_open and is_multiplayer_authority():
		# Мародёр открывает дверь сам — и это слышно. Тело мародёра реплицировано на всех peer,
		# поэтому Area3D сработает у каждого; открывает только хост (он авторитет двери).
		# Чужим отрядам запертая на ключ дверь без ключа не открывается — как игрокам.
		if not RivalRaids.may_open(body as Marauder, required_key) or not _powered():
			return
		toggle(body.global_position)
		# слышно всем, кроме его отряда (свои знают, что дверь открыл свой)
		Marauder.emit_own(body as Marauder, global_position, 10.0, "door")


func _on_body_exited(body: Node3D) -> void:
	_players_near.erase(body)


func _process(delta: float) -> void:
	if not _players_near.is_empty() and Input.is_action_just_pressed("interact"):
		# F жмёт свой игрок — даже если напарник подошёл к двери первым
		var who := _local_near()
		if who:
			if not _can_open(who):
				Audio.play("door_locked", global_position, 0.0, 0.0, self)
				Raid.current.notify("Нет питания — электрозамок" if not _powered() else "Заперто: нужен " + Raid.current.key_name(required_key))
				return
			if required_key != "" and not is_open:
				Audio.play("door_unlock", global_position, 0.0, 0.0, self)
			toggle(who.global_position)
			NoiseBus.emit(global_position, 8.0, "door")
	# Анимацию ведёт только авторитет (хост) — иначе локальный лерп к _target_angle=0 у клиента
	# каждый кадр тянул бы створку обратно, деря с прилетающим по сети углом.
	if is_multiplayer_authority():
		_leaf.rotation.y = lerp_angle(_leaf.rotation.y, _target_angle, minf(1.0, Balance.DOOR_SWING_SPEED * delta))


func _local_near() -> Player:
	for b in _players_near:
		if is_instance_valid(b) and (b as Player).is_local():
			return b as Player
	return null


## Ключ — предмет в рюкзаке того, кто открывает (закрыть открытую можно всегда).
func _can_open(who: Player) -> bool:
	if is_open:
		return true
	if not _powered():
		return false
	if required_key == "":
		return true
	return who != null and who.inventory.has(required_key)


## Электрозамок под питанием (или питание не нужно).
func _powered() -> bool:
	return required_switch == "" or (Raid.current != null and bool(Raid.current.switches.get(required_switch, false)))


## Открыть от того, кто открывает: сторона выбирается по знаку локального Z подошедшего.
## Сеть: если мы не авторитет двери — просим хост, а не толкаем состояние сами.
func toggle(from_world: Vector3) -> void:
	if Net.is_networked() and not is_multiplayer_authority():
		_request_toggle.rpc_id(1, from_world)
		return
	is_open = not is_open
	Audio.play("door_metal", global_position, 0.0, 0.0, self)
	if is_open:
		var local := to_local(from_world)
		_target_angle = (PI * 0.5) if local.z > 0.0 else (-PI * 0.5)
	else:
		_target_angle = 0.0


## Мародёр упёрся в открытую створку: она распахнута в его сторону и стоит поперёк пути вдоль стены (сетка путей
## створок не знает). Толкнул — створка уходит на другую сторону проёма. true — толкнул. Только авторитет (хост).
func push_from(from_world: Vector3) -> bool:
	if not is_open or (Net.is_networked() and not is_multiplayer_authority()):
		return false
	# распахнута от подошедшего — угол со знаком его стороны (как в toggle)
	var away := (PI * 0.5) if to_local(from_world).z > 0.0 else (-PI * 0.5)
	if is_equal_approx(_target_angle, away):
		return false
	_target_angle = away
	Audio.play("door_metal", global_position, 0.0, 0.0, self)
	return true


@rpc("any_peer", "call_remote", "reliable")
func _request_toggle(from_world: Vector3) -> void:
	if is_multiplayer_authority() and (Raid.current == null or _can_open(Raid.current.player_of(multiplayer.get_remote_sender_id()))):
		toggle(from_world)
