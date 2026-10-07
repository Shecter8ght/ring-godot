@tool
class_name ShelterPower
extends Interactable
## Общий рубильник физического генератора. Улучшения Upgrades и топливо рейда не заменяет.
## В профиле добавляется только состояние досуга/питания, как у телевизора и радио.

@export var lights_path: NodePath = NodePath("../../Lights")
var enabled: bool = true
var _known: Array[int] = []
var _refreshing: bool = false

func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	Profile.ensure()
	if not Net.is_networked() or multiplayer.is_server():
		enabled = bool(Profile.hideout_media.get("power", true))
	Net.scenes_changed.connect(_share_state)
	_apply()

func prompt() -> String:
	if not can_use():
		return "питание: хост вне убежища"
	return "генератор: выключить питание" if enabled else "генератор: включить питание"

func can_use() -> bool:
	return not Net.is_networked() or Net.visible_in(1,"hideout")

func request_use() -> void:
	if can_use():
		super.request_use()

func _use(_peer_id: int) -> void:
	Net.broadcast_scene(self, &"_set_power", [not enabled])

@rpc("any_peer", "call_remote", "reliable")
func _request() -> void:
	if not multiplayer.is_server():
		return
	var peer: int = multiplayer.get_remote_sender_id()
	if not Net.visible_in(peer, "hideout"):
		return
	var level: Node = get_tree().get_first_node_in_group("hideout_level")
	var player: Player = level.get_node_or_null("Player_%d" % peer) as Player if level else null
	if player and player.global_position.distance_to(global_position) <= Balance.INTERACT_RADIUS + 1.5:
		_use(peer)

@rpc("authority", "call_local", "reliable")
func _set_power(value: bool) -> void:
	enabled = value
	Profile.hideout_media["power"] = enabled
	Profile.save()
	_apply()

func _share_state() -> void:
	if not Net.is_host():
		return
	for peer: int in Net.peer_scene:
		if peer != 1 and Net.visible_in(peer, "hideout") and not peer in _known:
			_set_power.rpc_id(peer, enabled)
	_known.clear()
	for peer: int in Net.peer_scene:
		if Net.visible_in(peer, "hideout"):
			_known.append(peer)

func _apply() -> void:
	var lights: Node = get_node_or_null(lights_path)
	if not lights:
		return
	for node: Node in lights.get_children():
		var light: Light3D = node as Light3D
		if not light or light.name == &"TvGlow" or String(light.name).begins_with("Emergency") or daylight(light):
			continue
		if not light.has_meta("normal_energy"):
			light.set_meta("normal_energy", light.light_energy)
		light.light_energy = float(light.get_meta("normal_energy")) if enabled else 0.0
	# Emissive diffusors отражают тот же рубильник; расстановка сохранена в сцене.
	var level: Node = get_parent().get_parent()
	var atmosphere: Node = level.get_node_or_null("Atmosphere")
	if atmosphere:
		for effect: Node in atmosphere.get_children():
			if effect.has_method("set_power"):
				effect.call("set_power", enabled)
	for node: Node in level.find_children("Fixture_*", "Node3D", true, false):
		for mesh: Node in node.find_children("*", "MeshInstance3D", true, false):
			var mi: MeshInstance3D = mesh as MeshInstance3D
			for index: int in range(mi.mesh.get_surface_count()):
				var material: StandardMaterial3D = mi.mesh.surface_get_material(index) as StandardMaterial3D
				if material and material.resource_name == "WarmEmitter":
					material.emission_energy_multiplier = 2.4 if enabled else 0.0
	# запечённый рассеянный свет — свой вариант с лампами и без (ShelterWeather)
	var weather: ShelterWeather = level.get_node_or_null("Weather") as ShelterWeather
	if weather:
		weather.refresh.call_deferred(true)
	_refresh_reflections.call_deferred()

## Свет снаружи (солнце, дневной свет из окон) — не от генератора.
static func daylight(light: Light3D) -> bool:
	return light is DirectionalLight3D or String(light.name).begins_with("HallDaylight")

func _refresh_reflections() -> void:
	if _refreshing or not is_inside_tree():
		return
	var probes: Node = get_node_or_null("../../ReflectionProbes")
	if not probes or probes.get_child_count()==0:
		return
	_refreshing = true
	# После рубильника обновить отражения один раз; постоянно рендерить шесть cubemap не нужно.
	for node: Node in probes.get_children():
		(node as ReflectionProbe).update_mode = ReflectionProbe.UPDATE_ALWAYS
	await get_tree().process_frame
	if is_instance_valid(probes):
		for node: Node in probes.get_children():
			(node as ReflectionProbe).update_mode = ReflectionProbe.UPDATE_ONCE
	_refreshing = false
