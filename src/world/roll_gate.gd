@tool
class_name RollGate
extends Interactable
## Ворота-роллета в проёме (рампа склада «Яруса», docs/design/prologue.md §4.6): закрыты — засов изнутри
## (с локальной −Z); F у засова — полотно с грохотом уходит вверх, шум далеко. В обычных рейдах подняты
## (start_open); пролог опускает их на старте (Prologue, хост). Открывает хост, состояние — всем.

@export var width: float = 4.0:
	set(v):
		width = v
		_rebuild()
@export var height: float = 3.8:
	set(v):
		height = v
		_rebuild()
@export var start_open: bool = true

var is_open: bool = true
var _body: StaticBody3D
var _lift: float = 1.0


func _ready() -> void:
	is_open = start_open
	_lift = 1.0 if is_open else 0.0
	super._ready()
	if Engine.is_editor_hint():
		return
	if Net.is_networked():
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		config.add_property(NodePath(".:is_open"))
		config.property_set_replication_mode(NodePath(".:is_open"), SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
		sync.replication_config = config
		sync.set_multiplayer_authority(get_multiplayer_authority())
		Net.scope_sync(self, sync)
		add_child(sync)


## Хост: опустить и запереть изнутри (пролог).
func close() -> void:
	is_open = false


func can_use() -> bool:
	if is_open:
		return false
	var me: Player = Raid.current.local_player() if Raid.current else null
	return me == null or _inside(me.global_position)


func prompt() -> String:
	return "открыть засов — поднять ворота"


func _inside(p: Vector3) -> bool:
	return to_local(p).z < 0.3


func _use(peer_id: int) -> void:
	if is_open:
		return
	var pl: Player = Raid.current.player_of(peer_id) if Raid.current else null
	if pl and not _inside(pl.global_position):
		return
	is_open = true
	# грохот роллеты слышно далеко — последний шум склада
	NoiseBus.emit(global_position, 30.0, "door")


func _process(delta: float) -> void:
	if Engine.is_editor_hint() or _vis == null:
		return
	var target := 1.0 if is_open else 0.0
	if not is_equal_approx(_lift, target):
		if target > _lift and _lift <= 0.0:
			Audio.play("door_metal", global_position)
		_lift = move_toward(_lift, target, delta / 2.2)
		_place()


func _place() -> void:
	var panel := _vis.get_node_or_null("Panel") as Node3D
	if panel:
		panel.position.y = height * 0.5 + _lift * (height - 0.35)
	if _body:
		_body.collision_layer = 0 if _lift > 0.6 else (Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)


func _build_visual(parent: Node3D) -> void:
	var panel := MeshInstance3D.new()
	panel.name = "Panel"
	var box := BoxMesh.new()
	box.size = Vector3(width, height, 0.08)
	panel.mesh = box
	if not Engine.is_editor_hint():
		panel.material_override = SectorMaterials.get_material("metal_plate")
	parent.add_child(panel)
	# засов изнутри — ориентир, куда жать F
	var bolt := MeshInstance3D.new()
	var bb := BoxMesh.new()
	bb.size = Vector3(0.5, 0.08, 0.1)
	bolt.mesh = bb
	bolt.position = Vector3(width * 0.3, 1.1, -0.1)
	panel.add_child(bolt)
	_body = StaticBody3D.new()
	_body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var bs := BoxShape3D.new()
	bs.size = Vector3(width, height, 0.12)
	shape.shape = bs
	_body.add_child(shape)
	panel.add_child(_body)
	_place()
