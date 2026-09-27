@tool
class_name KeyPickup
extends Interactable
## Ключ / карта-ключ на полу. Подобрал — предмет key_id в рюкзаке подобравшего (data/items.json):
## открывает двери помещений с тем же "key" в данных кольца и точки эвакуации с required_key.
## Лежит один: подобран — пропадает у всех (флаг taken реплицируется).

@export var key_id: String = "key":
	set(v):
		key_id = v
		_rebuild()
@export var display_name: String = "Ключ":
	set(v):
		display_name = v
		_rebuild()

var taken: bool = false


func _ready() -> void:
	super._ready()
	if not Engine.is_editor_hint():
		add_to_group("key_pickups")
		if Net.is_networked():
			var sync := MultiplayerSynchronizer.new()
			sync.name = "Sync"
			var config := SceneReplicationConfig.new()
			var path := NodePath(".:taken")
			config.add_property(path)
			config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
			sync.replication_config = config
			sync.set_multiplayer_authority(get_multiplayer_authority())
			Net.scope_sync(self, sync)
			add_child(sync)


func can_use() -> bool:
	return not taken


func prompt() -> String:
	return "взять: " + display_name


func _use(peer_id: int) -> void:
	var pl := Raid.current.player_of(peer_id)
	if pl == null or pl.inventory.add(key_id, 1) == 0:
		return
	taken = true
	Audio.play("key_pickup", global_position)


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or _vis == null:
		return
	_vis.visible = not taken


func _build_visual(parent: Node3D) -> void:
	_box(parent, Vector3(0, 0.45, 0), Vector3(0.7, 0.9, 0.5), Color(0.3, 0.3, 0.32))
	_box(parent, Vector3(0, 0.93, 0), Vector3(0.22, 0.04, 0.14), Color(1.0, 0.8, 0.2), 1.5)
	_label(parent, display_name, 1.5, Color(1.0, 0.85, 0.4))
