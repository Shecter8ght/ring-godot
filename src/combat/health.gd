class_name Health
extends Node
## Здоровье сущности. Узел-компонент: вешается на игрока и мародёра.

signal damaged(amount: float, from: Vector3)
signal died

@export var max_hp: float = 100.0

var hp: float
var alive: bool = true


func _ready() -> void:
	hp = max_hp
	if Net.is_networked():
		_setup_sync()


## hp/alive реплицируются от того, кто авторитет ИМЕННО для Health (у Marauder это тот же хост,
## что и для всего узла; у Player — хост, хотя сам Player отдан во владение своему peer,
## см. sector_level._spawn_player_node). Без этого урон применяется, но остальные его не видят.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:hp", ".:alive"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	add_child(sync)


func take_damage(amount: float, from: Vector3) -> void:
	if not alive:
		return
	hp = maxf(0.0, hp - amount)
	damaged.emit(amount, from)
	if hp <= 0.0:
		alive = false
		died.emit()


## Точка входа для Hitscan: применяет урон сама, если мы авторитет по этому узлу (сингл/хост),
## иначе просит хост — так урон всегда считается один раз и в одном месте (правило AGENTS.md).
func apply_or_request_damage(amount: float, from: Vector3) -> void:
	if not Net.is_networked() or is_multiplayer_authority():
		take_damage(amount, from)
	else:
		request_damage.rpc_id(1, amount, from)


@rpc("any_peer", "call_remote", "reliable")
func request_damage(amount: float, from: Vector3) -> void:
	if is_multiplayer_authority():
		take_damage(amount, from)
