extends CanvasLayer
## Диагностика на настоящем рейдовом уровне. Берёт тот же луч и набор, что и игровой шаг.

const LAB: String = "res://scenes/debug/surface_audio_lab.tscn"
var _player: Player
var _label: Label


static func open(path: String, title: String) -> void:
	if Net.is_networked() or Profile.pending_raid or Loading.active:
		return
	Net.scene_transition_finished.connect(func(loaded: String) -> void:
		if loaded == path and Raid.current and Raid.current.local_player():
			var readout: CanvasLayer = load("res://src/debug/surface_map_readout.gd").new() as CanvasLayer
			readout.set("_player", Raid.current.local_player())
			readout.set_meta("map", title)
			get_scene_tree().current_scene.add_child(readout), CONNECT_ONE_SHOT)
	Net.change_scene(path, "Покрытия · " + title)


static func get_scene_tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


func _ready() -> void:
	layer = 25
	_player.health.invulnerable = true
	_player.combat_enabled = false
	for enemy: Node in get_tree().get_nodes_in_group("marauders"):
		_quiet_enemy(enemy)
	get_tree().node_added.connect(_quiet_enemy)
	var panel: PanelContainer = PanelContainer.new()
	panel.anchor_left = 1.0
	panel.anchor_right = 1.0
	panel.offset_left = -510
	panel.offset_right = -24
	panel.offset_top = 24
	panel.offset_bottom = 165
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(panel)
	_label = Label.new()
	_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_label.add_theme_font_size_override("font_size", 19)
	panel.add_child(_label)


func _quiet_enemy(node: Node) -> void:
	if node is Marauder:
		var enemy: Marauder = node as Marauder
		enemy.set_deferred("process_mode", Node.PROCESS_MODE_DISABLED)
		enemy.set_deferred("collision_layer", 0)
		enemy.set_deferred("visible", false)


func _process(_delta: float) -> void:
	if not is_instance_valid(_player):
		return
	var pos: Vector3 = _player.global_position
	var hit: Dictionary = Audio.ground_hit(pos)
	var shape: String = ""
	var body: CollisionObject3D = hit.get("collider") as CollisionObject3D
	if body:
		var owner: Node = body.shape_owner_get_owner(body.shape_find_owner(int(hit.get("shape", 0)))) as Node
		shape = "%s / %s" % [body.get_parent().name, owner.name if owner else body.name]
	var surface: String = Audio.step_surface_at(pos, Surfaces.kind_at(hit))
	var running: bool = Vector2(_player.velocity.x, _player.velocity.z).length() > Balance.STEP_RUN_SPEED
	var kind: String = Audio.step_kind_at(pos, surface, running)
	_label.text = "%s  ·  F6 — назад на стенд\n%s\nТип · %s\n%s" % [get_meta("map"), shape,
		Audio.step_surface_name(surface), Audio.step_event_name(kind)]
	var layers: PackedStringArray = PackedStringArray()
	for patch: Node in Audio.step_layers_at(pos):
		var id: String = String(patch.get("layer"))
		if Balance.STEP_LAYERS.has(id) and Balance.lab_number("step_layers", id + "_on") >= 0.5:
			var title: String = String(Balance.STEP_LAYERS[id])
			if not layers.has(title):
				layers.append(title)
	if not layers.is_empty():
		_label.text += "\nСлои · " + " + ".join(layers)


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and (event as InputEventKey).keycode == KEY_F6 and event.is_pressed() and not event.is_echo():
		get_viewport().set_input_as_handled()
		Net.change_scene(LAB, "Поверхности и звуки карт")
