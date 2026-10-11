@tool
class_name ShelterExitDoor
extends Interactable
## Гермодверь выхода из котельной: F — открыть / закрыть. Створка (узел leaf) поворачивается на петлях
## за Balance.SHELTER_YARD.door_sec, коллизия едет вместе с ней. Состояние общее для всех, кто в
## убежище: решает хост, остальным — рассылка (как рубильник генератора, ShelterPower).

## Створка: её ноль — ось петель.
@export var leaf: NodePath = NodePath("Leaf")

var opened: bool = false
var _known: Array[int] = []


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	Net.scenes_changed.connect(_share_state)


func prompt() -> String:
	return "закрыть дверь" if opened else "открыть дверь"


func can_use() -> bool:
	return not Net.is_networked() or Net.visible_in(1, "hideout")


func request_use() -> void:
	if can_use():
		super.request_use()


func _use(_peer_id: int) -> void:
	Net.broadcast_scene(self, &"_set_open", [not opened])


@rpc("any_peer", "call_remote", "reliable")
func _request() -> void:
	if not multiplayer.is_server():
		return
	var peer: int = multiplayer.get_remote_sender_id()
	if not Net.visible_in(peer, "hideout"):
		return
	var level: Node = get_tree().get_first_node_in_group("hideout_level")
	var player: Player = level.get_node_or_null("Player_%d" % peer) as Player if level else null
	if player and player.global_position.distance_to(global_position) <= Balance.INTERACT_RADIUS + 2.0:
		_use(peer)


@rpc("authority", "call_local", "reliable")
func _set_open(value: bool) -> void:
	if opened == value:
		return
	opened = value
	Audio.play("door", global_position, 2.0, 0.72)


## Пришедшему позже — как стоит дверь сейчас.
func _share_state() -> void:
	if not Net.is_host():
		return
	for peer: int in Net.peer_scene:
		if peer != 1 and Net.visible_in(peer, "hideout") and not peer in _known:
			_set_open.rpc_id(peer, opened)
	_known.clear()
	for peer: int in Net.peer_scene:
		if Net.visible_in(peer, "hideout"):
			_known.append(peer)


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var node: Node3D = get_node_or_null(leaf) as Node3D
	if node == null:
		return
	var cfg: Dictionary = Balance.SHELTER_YARD
	var target: float = deg_to_rad(float(cfg.door_open_deg)) if opened else 0.0
	node.rotation.y = move_toward(node.rotation.y, target, deg_to_rad(float(cfg.door_open_deg)) / float(cfg.door_sec) * delta)
