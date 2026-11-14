extends Node
## Движок выбирает запись места и считает, как звук дошёл до игрока.

const REGISTRY: String = "res://data/audio_events.json"
const STEP_BASE: String = "step_base"
const STEP_MATERIALS := {
	"step_concrete": "step_layer_concrete",
	"step_gravel": "step_layer_gravel",
	"step_water": "step_layer_water",
}
const MIX_PATH: String = "res://data/audio_mix.json"
const MAP_AMBIENCE_PATH: String = "user://map_ambience.cfg"
const AcousticPlace := preload("res://src/audio/acoustic_place.gd")
const SoundPropagation := preload("res://src/audio/sound_propagation.gd")
const StepLayerPatch := preload("res://src/audio/step_layer_patch.gd")

enum SoundPathPreview { SCENE, OPEN, WALL }

class SoundPath:
	var player: AudioStreamPlayer3D
	var profile: Vector4
	var checks_walls: bool
	var refresh_left: float
	var current: Vector2
	var target: Vector2
	var follow: Node3D
	var offset: Vector3
	var source: Vector3
	var door: Vector3 = Vector3.INF
	var via_door: bool
	var door_share: float

signal stepped(kind: String, surface: String, pos: Vector3)
signal event_played(event_id: String, hook: String, pos: Vector3)

var _events: Dictionary = {}
var _bindings: Dictionary = {}
var _samples: Dictionary = {}
var _last_pick: Dictionary = {}
var _rng: RandomNumberGenerator = RandomNumberGenerator.new()
var _place_cache: Dictionary = {}
var _shooters: Array[Dictionary] = []
var _triggered: Dictionary = {}
var _ambient: AudioStreamPlayer
var _preview: Dictionary = {}
var _step_preview: Dictionary = {}
var _layer_revision: int = -1
var _layer_samples: Dictionary = {}
var _scan_needed: bool = true
var _scene_paths: Dictionary = {}
var _object_bindings: Dictionary = {}
var _surface_steps: Dictionary = {}
var _step_slots: Array = []
var _surface_shells: Dictionary = {}
var _stream_files: Dictionary = {}
var _mix: Dictionary = {"schemaVersion": 1, "events": {}, "files": {}}
var mix_save_path: String = MIX_PATH
var _map_ambient: AudioStreamPlayer
var _map_scene_id: int = 0
var _map_scene_path: String = ""
var _map_paths: Dictionary = {}
var _local_map_files: Dictionary = {}
var _local_map_streams: Dictionary = {}
var map_ambience_save_path: String = MAP_AMBIENCE_PATH
var _voice_events: Dictionary = {}
var _sound_paths: Array[SoundPath] = []
var _near_sound_doors: Array[Node] = []
var _sound_doors_frame: int = -1
var _sound_path_frame: int = -1
var _sound_path_samples: Dictionary = {}


func _load_voice_lines() -> void:
	_voice_events.clear()
	var path := "res://data/npc_voice_map.json"
	if not FileAccess.file_exists(path):
		return
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not raw is Dictionary or int((raw as Dictionary).get("schemaVersion", 0)) != 1:
		return
	for value: Variant in (raw as Dictionary).get("lines", []):
		if not value is Dictionary:
			continue
		var row: Dictionary = value as Dictionary
		var speaker := String(row.get("speaker", ""))
		var text := String(row.get("text", ""))
		var event_id := String(row.get("event", ""))
		if speaker == "" or text == "" or event_id == "":
			continue
		_voice_events[speaker + "\n" + text] = event_id


func voice_event_for(speaker: String, text: String) -> String:
	return String(_voice_events.get(speaker + "\n" + text, _voice_events.get("*\n" + text, "")))


func play_voice_line(speaker: String, text: String, pos: Vector3 = Vector3.INF, radio: bool = false, follow: Node3D = null) -> bool:
	var event_id := voice_event_for(speaker, text)
	if event_id == "" or not has_sound(event_id):
		return false
	if pos.is_finite():
		play(event_id, pos, 0.0, 0.0, null, null, follow)
	else:
		play_ui(event_id, 0.0, &"Radio" if radio else &"")
	return true


func _ready() -> void:
	_rng.randomize()
	_load_mix()
	_load_voice_lines()
	var local: ConfigFile = ConfigFile.new()
	if local.load(map_ambience_save_path) == OK:
		var files: Variant = local.get_value("ambient", "files", {})
		if files is Dictionary:
			_local_map_files = files
	var surface_data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio_surfaces.json")) as Dictionary
	_step_slots = surface_data.get("footsteps", [])
	for entry: Dictionary in _step_slots:
		for surface: String in entry.surfaces:
			_surface_steps[surface] = String(entry.hook)
	for entry: Dictionary in surface_data.get("casings", []):
		for surface: String in entry.surfaces:
			_surface_shells[surface] = String(entry.hook)
	reload_events()
	get_tree().node_added.connect(_on_audio_node_added)
	for node: Node in get_tree().root.find_children("*", "", true, false):
		_on_audio_node_added(node)
	set_process(true)

func reload_events() -> void:
	_scan_needed = true
	_events.clear()
	_bindings.clear()
	_samples.clear()
	_stream_files.clear()
	_triggered.clear()
	_map_scene_id = 0
	if is_instance_valid(_map_ambient):
		_map_ambient.stop()
		_map_ambient.queue_free()
	_scene_paths.clear()
	_object_bindings.clear()
	_map_paths.clear()
	_last_pick.clear()
	var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(REGISTRY))
	if not raw is Dictionary or int((raw as Dictionary).get("schemaVersion", 0)) != 2:
		push_warning("Sonora: не найден каталог назначений audio_events.json версии 2")
		return
	for value: Variant in (raw as Dictionary).get("events", []):
		if not value is Dictionary:
			continue
		var event: Dictionary = value as Dictionary
		var id: String = String(event.get("id", ""))
		if id == "" or not bool(event.get("enabled", true)):
			continue
		_events[id] = event
		if event.has("map_scene"):
			_map_paths[String(event.map_scene)] = id
		var binding: Dictionary = event.get("binding", {}) as Dictionary
		if String(binding.get("type", "action")) == "action":
			_bindings[String(binding.get("hook", id))] = id
		elif String(binding.get("type", "")) == "object_action":
			var hook: String = String(binding.get("hook", ""))
			if not _object_bindings.has(hook):
				_object_bindings[hook] = []
			(_object_bindings[hook] as Array).append(id)
		else:
			_scene_paths[String(binding.get("scene", ""))] = true
		var streams: Array[AudioStream] = []
		for relative: Variant in event.get("files", []):
			var rel: String = String(relative)
			if rel.begins_with("/") or rel.contains(":") or ".." in rel.split("/"):
				continue
			var stream: AudioStream = load_audio_file("res://assets/audio/" + rel)
			if stream != null:
				streams.append(stream)
				_stream_files[stream.get_instance_id()] = rel
		_samples[id] = streams
	for node: Node in get_tree().root.find_children("*", "Node3D", true, false):
		if _map_paths.has(node.scene_file_path) or _local_map_files.has(node.scene_file_path):
			node.add_to_group("sonora_map_roots")
	if is_instance_valid(_ambient):
		_ambient.queue_free()
	var background: AudioStream = _pick("loop:ambient", Vector3.ZERO)
	if background != null:
		make_loop(background)
		_ambient = AudioStreamPlayer.new()
		_ambient.stream = background
		_ambient.bus = &"Ambient"
		_ambient.volume_db = float(Balance.SONORA_AUDIO.ambient_db)
		add_child(_ambient)
		_ambient.play()

func resolve_event(hook: String, place: String = "") -> String:
	if _is_weapon_shot(hook):
		var suffix: String = "_room" if place in [AcousticPlace.ROOM, AcousticPlace.HALL] else "_outdoor"
		return String(_bindings.get(hook + suffix, ""))
	if _events.has(hook):
		return hook
	return String(_bindings.get(hook, ""))

## Назначена ли действию запись (иначе play() молчит): у «Осоки» без записи звучит процедурная заглушка.
func has_sound(hook: String) -> bool:
	return _preview.has(hook) or not (_samples.get(resolve_event(hook), []) as Array).is_empty()

func _pick(hook: String, _pos: Vector3, place: String = "") -> AudioStream:
	var preview: Array = _preview.get(hook, []) as Array
	if not preview.is_empty():
		return _pick_from(preview, hook)
	var id: String = resolve_event(hook, place)
	var records: Array = _samples.get(id, []) as Array
	return null if records.is_empty() else _pick_from(records, id)

func _pick_from(records: Array, key: String) -> AudioStream:
	var index: int = _rng.randi_range(0, records.size() - 1)
	if records.size() > 1 and index == int(_last_pick.get(key, -1)):
		index = (index + 1 + _rng.randi_range(0, records.size() - 2)) % records.size()
	_last_pick[key] = index
	return records[index] as AudioStream

func play(hook: String, pos: Vector3, extra_db: float = 0.0, _pitch: float = 0.0, emitter: Node = null,
		recording: AudioStream = null, follow: Node3D = null) -> void:
	if hook == "":
		return
	var spec: Dictionary = _kind_spec(hook)
	var distance: float = _listener_pos().distance_to(pos)
	if _has_ears() and distance > float(spec["max"]):
		return
	var place: String = place_at(pos) if _is_weapon_shot(hook) else ""
	var id: String = resolve_event(hook, place)
	if emitter != null:
		for candidate: String in _object_bindings.get(hook, []):
			var binding: Dictionary = (_events[candidate] as Dictionary).binding as Dictionary
			if _matches_object(emitter, binding):
				id = candidate
				break
	var stream: AudioStream = recording if recording != null else _pick(id if id != "" and not _preview.has(hook) else hook, pos)
	if stream == null:
		return
	var delay: float = distance / float(Balance.AUDIO_FAR.sound_mps) if _has_ears() and bool(spec.get("far", false)) and distance > float(Balance.AUDIO_FAR.delay_from_m) else 0.0
	if delay > 0.0:
		var scene := get_tree().current_scene
		get_tree().create_timer(delay).timeout.connect(func() -> void:
			if is_instance_valid(scene) and get_tree().current_scene == scene:
				_play_now(hook, id, stream, pos, extra_db, spec))
	else:
		_play_now(hook, id, stream, pos, extra_db, spec, {}, follow)

func _matches_object(emitter: Node, binding: Dictionary) -> bool:
	var ancestor: Node = emitter
	while ancestor != null:
		if ancestor.scene_file_path == String(binding.scene):
			var target: Node = ancestor.get_node_or_null(NodePath(String(binding.node)))
			if target != null and (target == emitter or target.is_ancestor_of(emitter)):
				return true
		ancestor = ancestor.get_parent()
	return false

func _play_now(hook: String, id: String, stream: AudioStream, pos: Vector3, extra_db: float, spec: Dictionary,
		preview: Dictionary = {}, follow: Node3D = null) -> AudioStreamPlayer3D:
	if get_tree().current_scene == null:
		return null
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.stream = stream
	_tag_mix(player, id, stream, float(spec.db) + extra_db)
	player.unit_size = float(spec.unit)
	player.max_distance = float(spec["max"])
	player.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	var bus := _bus_for(hook)
	player.bus = bus
	player.finished.connect(player.queue_free)
	get_tree().current_scene.add_child(player)
	player.global_position = pos
	_setup_sound_path(player, bus, bool(spec.get("occlude", true)), preview, follow)
	player.play()
	event_played.emit(id, hook, pos)
	if _is_weapon_shot(hook):
		_track_burst(pos, [player])
	return player

func _is_weapon_shot(hook: String) -> bool:
	return (hook.ends_with("_shot") or hook.ends_with("_shot_sup")) \
		and (_bindings.has(hook + "_room") or _bindings.has(hook + "_outdoor"))

func _kind_spec(hook: String) -> Dictionary:
	if _is_weapon_shot(hook):
		return Balance.SONORA_AUDIO.shot
	var event: Dictionary = _events.get(resolve_event(hook), {}) as Dictionary
	var profile: String = String(event.get("profile", ""))
	if profile in ["shell_hard", "shell_metal"]:
		var spec: Dictionary = (Balance.AUDIO_EVENT_PROFILES[profile] as Dictionary).duplicate()
		spec.db = float(spec.db) + float(Balance.SHELL_DROP.db)
		return spec
	if profile.begins_with("osoka_"):
		return Balance.AUDIO_EVENT_PROFILES.get(profile, Balance.SONORA_AUDIO.world)
	if String(event.get("weapon", "")) != "":
		if String(event.get("action", "")).begins_with("shot"):
			return Balance.SONORA_AUDIO.shot
		return Balance.SONORA_AUDIO.weapon_action
	return Balance.AUDIO_EVENT_PROFILES.get(profile, Balance.AUDIO_EVENT_PROFILES.get(hook, Balance.SONORA_AUDIO.world)) as Dictionary

## Начальные параметры позиционного источника. Приглушение задаётся после размещения в мире.
func _configure_recorded_player(player: AudioStreamPlayer3D) -> void:
	player.attenuation_filter_cutoff_hz = float(Balance.SONORA_AUDIO.unfiltered_hz)
	player.attenuation_filter_db = 0.0
	player.pitch_scale = 1.0
	player.doppler_tracking = AudioStreamPlayer3D.DOPPLER_TRACKING_DISABLED
	player.emission_angle_enabled = false
	player.area_mask = 0
	# Ближний источник не усиливается выше уровня записи; форму пиков никто не обрезает.
	player.max_db = minf(player.max_db, float(Balance.SONORA_AUDIO.max_db))

func _bus_for(hook: String) -> StringName:
	if hook == "radio" or hook.begins_with("voice_rival_radio_") or hook.begins_with("radio_job_"):
		return &"Radio"
	if _is_weapon_shot(hook):
		return &"Shots"
	var event: Dictionary = _events.get(resolve_event(hook), {}) as Dictionary
	if String(event.get("category", "")) == "Голоса ИИ и персонажей":
		return &"Voices"
	if hook.begins_with("ui_") or String(event.get("group", "")) == "Меню и сообщения":
		return Settings.INTERFACE_BUS
	if event.has("map_scene") or String(event.get("profile", "")) == "ambient":
		return &"Ambient"
	if String(event.get("profile", "")) in ["osoka_launch", "osoka_motor"]:
		return &"Shots"
	if String(event.get("weapon", "")) != "" and String(event.get("action", "")).begins_with("shot"):
		return &"Shots"
	return Settings.bus_for(hook)


func _load_mix() -> void:
	if FileAccess.file_exists(MIX_PATH):
		var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(MIX_PATH))
		if saved is Dictionary and int(saved.get("schemaVersion", 0)) == 1:
			_mix = saved
	if not OS.has_feature("editor"):
		mix_save_path = "user://audio_mix.json"
		if FileAccess.file_exists(mix_save_path):
			var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(mix_save_path))
			if saved is Dictionary and int(saved.get("schemaVersion", 0)) == 1:
				_mix = saved

	_mix.erase("headsets")


func mix_gain(id: String, file: String = "") -> float:
	return float((_mix.files if file != "" else _mix.events).get(file if file != "" else id, 0.0))


## Общая громкость события и поправка отдельной записи применяются тем же путём в игре и на стенде.
func set_mix_gain(id: String, db: float, file: String = "") -> void:
	var values: Dictionary = _mix.files if file != "" else _mix.events
	var key: String = file if file != "" else id
	if is_zero_approx(db):
		values.erase(key)
	else:
		values[key] = clampf(db, -60.0, 24.0)
	for node: Node in get_tree().get_nodes_in_group("sonora_mixed_players"):
		_apply_mix(node)


func save_mix() -> Error:
	var target: String = ProjectSettings.globalize_path(mix_save_path)
	var file: FileAccess = FileAccess.open(target + ".tmp", FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(JSON.stringify(_mix, "  ") + "\n")
	file.close()
	return DirAccess.rename_absolute(target + ".tmp", target)


func _tag_mix(player: Node, id: String, stream: AudioStream, base_db: float) -> void:
	player.set_meta("audio_event", id)
	player.set_meta("audio_file", String(_stream_files.get(stream.get_instance_id(), "")))
	player.set_meta("audio_base_db", base_db)
	player.add_to_group("sonora_mixed_players")
	_apply_mix(player)


func _apply_mix(player: Node) -> void:
	var id: String = String(player.get_meta("audio_event", ""))
	var file: String = String(player.get_meta("audio_file", ""))
	var level := float(player.get_meta("audio_base_db", 0.0)) + mix_gain(id) + (mix_gain(id, file) if file != "" else 0.0)
	player.set("volume_db", level - float(player.get_meta("sound_path_loss_db", 0.0)))


func _setup_sound_path(player: AudioStreamPlayer3D, bus: StringName, checks_walls: bool,
		preview: Dictionary = {}, follow: Node3D = null, looped: bool = false) -> void:
	var profile: Vector4 = Balance.SOUND_AIR.get(String(bus), Balance.SOUND_AIR.World)
	var mode := int(preview.get("path", SoundPathPreview.SCENE))
	var spectral := bool(preview.get("spectral", true))
	var ear := _listener_pos()
	var source := player.global_position
	var blocked := Vector2.ZERO
	var door := Vector3.INF
	if mode == SoundPathPreview.WALL:
		blocked = Balance.SOUND_PROPAGATION.wall
	elif mode == SoundPathPreview.SCENE and checks_walls:
		blocked = _sample_sound_path(player, ear, source)
		door = _sound_door(player, ear, source, blocked)
		if door.is_finite():
			blocked = Balance.SOUND_PROPAGATION.door_path
	var heard_at := _sound_position(ear, source, door, 1.0)
	player.global_position = heard_at
	_apply_sound_path(player, profile, ear.distance_to(heard_at), blocked, spectral)
	if not preview.is_empty():
		player.set_meta("preview_sound_path", blocked)
		player.set_meta("preview_air_profile", profile)
		return
	if not looped and bus != &"Voices" and (bus == &"Shots" or player.stream.get_length() < float(Balance.SOUND_PROPAGATION.long_sec)):
		return
	var path := SoundPath.new()
	path.player = player
	path.profile = profile
	path.checks_walls = checks_walls
	path.current = blocked
	path.target = blocked
	path.source = source
	path.door = door
	path.via_door = door.is_finite()
	path.door_share = 1.0 if path.via_door else 0.0
	path.refresh_left = float(_sound_paths.size() % 5 + 1) * 0.02
	if is_instance_valid(follow):
		path.follow = follow
		path.offset = source - follow.global_position
	_sound_paths.append(path)


func _sample_sound_path(player: AudioStreamPlayer3D, ear: Vector3, source: Vector3) -> Vector2:
	var world := player.get_world_3d()
	if world == null or not _has_ears():
		return Vector2.ZERO
	# Один шаг может запустить запись подошвы, снаряжения и мусора в одной точке.
	var frame := Engine.get_process_frames()
	if _sound_path_frame != frame:
		_sound_path_frame = frame
		_sound_path_samples.clear()
	var key := [world.get_instance_id(), ear, source]
	if not _sound_path_samples.has(key):
		_sound_path_samples[key] = SoundPropagation.sample(world.direct_space_state, ear, source)
	return _sound_path_samples[key]


func _sound_door(player: AudioStreamPlayer3D, ear: Vector3, source: Vector3, blocked: Vector2) -> Vector3:
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	if blocked.y < 0.55 or ear.distance_squared_to(source) > pow(float(cfg.door_path_max_m), 2):
		return Vector3.INF
	var frame := Engine.get_process_frames()
	if _sound_doors_frame != frame:
		_sound_doors_frame = frame
		_near_sound_doors.clear()
		var radius_sq := pow(float(cfg.door_path_max_m) + float(cfg.door_path_extra_m), 2)
		for node in get_tree().get_nodes_in_group("doors"):
			var door := node as Door
			if door and door.global_position.distance_squared_to(ear) <= radius_sq:
				_near_sound_doors.append(door)
	return SoundPropagation.through_door(player.get_world_3d().direct_space_state, ear, source, _near_sound_doors)


func _sound_position(ear: Vector3, source: Vector3, door: Vector3, share: float) -> Vector3:
	if not door.is_finite() or share < 0.001:
		return source
	var distance := ear.distance_to(door) + door.distance_to(source)
	return source.lerp(ear + ear.direction_to(door) * distance, share)


func _apply_sound_path(player: AudioStreamPlayer3D, profile: Vector4, distance: float, blocked: Vector2, spectral: bool = true) -> void:
	var prior_loss := float(player.get_meta("sound_path_loss_db", 0.0))
	if absf(prior_loss - blocked.x) > 0.01 or (blocked.x == 0.0 and prior_loss > 0.0):
		if blocked.x == 0.0:
			player.remove_meta("sound_path_loss_db")
		else:
			player.set_meta("sound_path_loss_db", blocked.x)
		player.max_db = float(Balance.SONORA_AUDIO.max_db) - blocked.x
		_apply_mix(player)
	if not spectral:
		player.attenuation_filter_db = 0.0
		player.attenuation_filter_cutoff_hz = float(Balance.SONORA_AUDIO.unfiltered_hz)
		return
	var air := smoothstep(profile.x, profile.y, distance)
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	var wall_hz := float(cfg.wall_hz)
	var air_hz := lerpf(float(Balance.SONORA_AUDIO.unfiltered_hz), profile.z, smoothstep(0.0, 0.2, air))
	var cutoff := lerpf(air_hz, profile.z, smoothstep(0.0, 0.25, blocked.y))
	player.attenuation_filter_cutoff_hz = exp(lerpf(log(cutoff), log(wall_hz), blocked.y))
	# У близкой преграды громкость уже ограничена max_db. Не даём встроенному фильтру
	# почти исчезнуть только из-за того, что сам источник близко к слушателю.
	var close_wall := maxf(0.15, 1.0 - db_to_linear(player.max_db))
	player.attenuation_filter_db = -minf(80.0, air * profile.w + blocked.y * float(cfg.wall_high_db) / close_wall)


func _update_sound_paths(delta: float) -> void:
	if _sound_paths.is_empty():
		return
	var ear := _listener_pos()
	var cfg: Dictionary = Balance.SOUND_PROPAGATION
	var blend := 1.0 - exp(-delta / float(cfg.blend_sec))
	for index in range(_sound_paths.size() - 1, -1, -1):
		var path := _sound_paths[index]
		var player := path.player
		if not is_instance_valid(player) or player.is_queued_for_deletion() or player.has_meta("sound_path_fading"):
			_sound_paths.remove_at(index)
			continue
		if is_instance_valid(path.follow):
			path.source = path.follow.global_position + path.offset
		if not player.playing:
			player.global_position = path.source
			_sound_paths.remove_at(index)
			continue
		var distance := ear.distance_to(path.source)
		if player.max_distance > 0.0 and distance > player.max_distance:
			player.global_position = path.source
			continue
		path.refresh_left -= delta
		if path.checks_walls and path.refresh_left <= 0.0:
			path.refresh_left = float(cfg.rescan_sec)
			path.target = _sample_sound_path(player, ear, path.source)
			var door := _sound_door(player, ear, path.source, path.target)
			path.via_door = door.is_finite()
			if path.via_door:
				path.door = door
				path.target = cfg.door_path
		path.current = path.target if path.current.distance_squared_to(path.target) < 0.0001 else path.current.lerp(path.target, blend)
		path.door_share = lerpf(path.door_share, 1.0 if path.via_door else 0.0, blend)
		player.global_position = _sound_position(ear, path.source, path.door, path.door_share)
		_apply_sound_path(player, path.profile, ear.distance_to(player.global_position), path.current)


## A/B на стенде: тот же звук и преграда, меняются только частоты.
func set_preview_spectral(player: AudioStreamPlayer3D, spectral: bool) -> void:
	var path: Vector2 = player.get_meta("preview_sound_path", Vector2.ZERO)
	var profile: Vector4 = player.get_meta("preview_air_profile", Balance.SOUND_AIR.World)
	_apply_sound_path(player, profile, _listener_pos().distance_to(player.global_position), path, spectral)


func _update_map_ambient() -> void:
	var found: Node = null
	var roots: Array[Node] = get_tree().get_nodes_in_group("sonora_map_roots")
	for scene_path: String in _local_map_files.keys() + _map_paths.keys():
		if not _local_map_files.has(scene_path) and not has_sound(String(_map_paths[scene_path])):
			continue
		for node: Node in roots:
			if node.scene_file_path == scene_path:
				found = node
				break
		if found != null:
			break
	var path: String = found.scene_file_path if found != null else ""
	var scene_id: int = found.get_instance_id() if found != null else 0
	if scene_id == _map_scene_id and path == _map_scene_path:
		return
	_map_scene_id = scene_id
	_map_scene_path = path
	if is_instance_valid(_map_ambient):
		_map_ambient.stop()
		_map_ambient.queue_free()
	if found != null:
		_map_ambient = play_map_ambience(path, found)


func local_map_ambience(scene_path: String) -> String:
	return String(_local_map_files.get(scene_path, ""))


func local_map_scenes() -> PackedStringArray:
	return PackedStringArray(_local_map_files.keys())


func set_map_ambience(scene_path: String, audio_path: String) -> Error:
	if not scene_path.begins_with("res://") or not ResourceLoader.exists(scene_path, "PackedScene"):
		return ERR_INVALID_PARAMETER
	var stream: AudioStream = load_audio_file(audio_path) if audio_path != "" else null
	if audio_path != "" and stream == null:
		return ERR_FILE_UNRECOGNIZED
	var next: Dictionary = _local_map_files.duplicate()
	if audio_path.is_empty():
		next.erase(scene_path)
	else:
		next[scene_path] = audio_path
	var config: ConfigFile = ConfigFile.new()
	config.set_value("ambient", "files", next)
	var result: Error = config.save(map_ambience_save_path)
	if result != OK:
		return result
	_local_map_files = next
	_local_map_streams.erase(scene_path)
	if stream != null:
		_local_map_streams[scene_path] = stream
		for node: Node in get_tree().root.find_children("*", "Node3D", true, false):
			if node.scene_file_path == scene_path:
				node.add_to_group("sonora_map_roots")
	# Перезапустить фон, если назначение поменялось на открытой карте.
	if _map_scene_path == scene_path:
		_map_scene_id = 0
	return OK


func play_map_ambience(scene_path: String, parent: Node) -> AudioStreamPlayer:
	var event_id: String = String(_map_paths.get(scene_path, ""))
	if _local_map_files.has(scene_path) and not _local_map_streams.has(scene_path):
		_local_map_streams[scene_path] = load_audio_file(local_map_ambience(scene_path))
	var stream: AudioStream = _local_map_streams.get(scene_path) as AudioStream
	if stream == null:
		stream = _pick(event_id, Vector3.ZERO)
	if stream == null:
		return null
	var player: AudioStreamPlayer = AudioStreamPlayer.new()
	player.stream = stream.duplicate() as AudioStream
	make_loop(player.stream)
	player.bus = &"Ambient"
	_tag_mix(player, event_id, stream, float(Balance.SONORA_AUDIO.ambient_db))
	parent.add_child(player)
	player.play()
	return player


## Стенд выбирает конкретную запись, но использует тот же профиль, шину и пространственную подачу.
func preview_event(id: String, pos: Vector3, variant: int = -1, looped: bool = false,
		path: int = SoundPathPreview.SCENE, spectral: bool = true) -> Node:
	var records: Array = _samples.get(id, [])
	if records.is_empty():
		return null
	var stream: AudioStream = records[clampi(variant, 0, records.size() - 1)] if variant >= 0 else _pick_from(records, id)
	var spec: Dictionary = _kind_spec(id)
	var bus := _bus_for(id)
	if bus in [&"Ambient", &"Radio", Settings.INTERFACE_BUS] or id in ["osoka_seeker_track", "osoka_seeker_lock"]:
		var player: AudioStreamPlayer = AudioStreamPlayer.new()
		player.stream = stream
		player.bus = bus
		var base_db := 0.0
		if bus == &"Ambient":
			base_db = float(Balance.SONORA_AUDIO.ambient_db)
		elif id in ["osoka_seeker_track", "osoka_seeker_lock"]:
			base_db = float(Balance.OSOKA.tone_db)
		_tag_mix(player, id, stream, base_db)
		player.process_mode = Node.PROCESS_MODE_ALWAYS
		add_child(player)
		if looped:
			player.finished.connect(player.play)
		else:
			player.finished.connect(player.queue_free)
		player.play()
		return player
	var preview := {"path": path, "spectral": spectral}
	var player := _play_now(id, id, stream, pos, 0.0, spec, preview)
	if player == null:
		return null
	player.process_mode = Node.PROCESS_MODE_ALWAYS
	if looped:
		player.finished.disconnect(player.queue_free)
		player.finished.connect(player.play)
	return player

func play_ui(hook: String, extra_db: float = 0.0, bus_override: StringName = &"") -> void:
	var stream: AudioStream = _pick(hook, _listener_pos())
	if stream == null:
		return
	var player: AudioStreamPlayer = AudioStreamPlayer.new()
	player.stream = stream
	_tag_mix(player, resolve_event(hook), stream, extra_db)
	player.bus = _bus_for(hook) if bus_override == &"" else bus_override
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()
	event_played.emit(resolve_event(hook), hook, _listener_pos())

func start_loop(hook: String, parent: Node3D, extra_db: float = 0.0) -> AudioStreamPlayer3D:
	var original: AudioStream = _pick(hook, parent.global_position)
	if original == null:
		return null
	var stream: AudioStream = original.duplicate() as AudioStream
	make_loop(stream)
	var spec: Dictionary = _kind_spec(hook)
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.stream = stream
	_tag_mix(player, resolve_event(hook), original, float(spec.db) + extra_db)
	player.unit_size = float(spec.unit)
	player.max_distance = float(spec["max"])
	_configure_recorded_player(player)
	player.bus = _bus_for(hook)
	parent.add_child(player)
	play_world_loop(player, bool(spec.get("occlude", true)))
	return player


## Уже расставленный источник с циклической записью, например гул генератора.
func play_world_loop(player: AudioStreamPlayer3D, checks_walls: bool = true) -> void:
	if player.stream == null:
		return
	for index in range(_sound_paths.size() - 1, -1, -1):
		if is_instance_valid(_sound_paths[index].player) and _sound_paths[index].player == player:
			player.global_position = _sound_paths[index].source
			_sound_paths.remove_at(index)
	if not player.has_meta("audio_base_db"):
		player.set_meta("audio_base_db", player.volume_db)
	_configure_recorded_player(player)
	if player.has_meta("sound_path_loss_db"):
		player.remove_meta("sound_path_loss_db")
	_apply_mix(player)
	_setup_sound_path(player, player.bus, checks_walls, {}, player.get_parent() as Node3D, true)
	player.play()


func start_ui_loop(hook: String, parent: Node, base_db: float) -> AudioStreamPlayer:
	var original: AudioStream = _pick(hook, Vector3.ZERO)
	if original == null:
		return null
	var stream: AudioStream = original.duplicate() as AudioStream
	make_loop(stream)
	var player: AudioStreamPlayer = AudioStreamPlayer.new()
	player.stream = stream
	player.bus = _bus_for(hook)
	_tag_mix(player, resolve_event(hook), original, base_db)
	parent.add_child(player)
	player.play()
	return player

func rain_loop() -> AudioStream:
	return _loop_record("loop:rain")

func siren_loop() -> AudioStream:
	return _loop_record("loop:siren")

func hum_loop() -> AudioStream:
	return _loop_record("loop:hum")

func _loop_record(hook: String) -> AudioStream:
	var stream: AudioStream = _pick(hook, Vector3.ZERO)
	if stream != null:
		make_loop(stream)
	return stream

func set_preview(streams: Dictionary) -> void:
	_preview = streams
	_last_pick.clear()


func set_step_preview(streams: Dictionary) -> void:
	_step_preview = streams
	_place_cache.clear()

func _on_audio_node_added(node: Node) -> void:
	if _map_paths.has(node.scene_file_path) or _local_map_files.has(node.scene_file_path):
		node.add_to_group("sonora_map_roots")
	if node is AudioStreamPlayer3D:
		_configure_recorded_player(node as AudioStreamPlayer3D)
	if node is Node3D and _scene_paths.has(node.scene_file_path):
		_scan_needed = true
	if node is BaseButton and not node.has_meta("sound_wired"):
		var button: BaseButton = node as BaseButton
		button.set_meta("sound_wired", true)
		button.pressed.connect(func() -> void: play_ui("ui_click", -5.0))
		button.mouse_entered.connect(func() -> void:
			if not button.disabled:
				play_ui("ui_hover", -11.0))

func _process(delta: float) -> void:
	_update_sound_paths(delta)
	_update_map_ambient()
	# Уровни могут создаваться и выгружаться внутри Raid; привязки ищутся в их собственных сценах.
	if not _scan_needed:
		return
	_scan_needed = false
	if _scene_paths.is_empty():
		return
	var scenes: Array[Node] = get_tree().root.find_children("*", "Node3D", true, false)
	for id: String in _events:
		var event: Dictionary = _events[id] as Dictionary
		var binding: Dictionary = event.get("binding", {}) as Dictionary
		var mode: String = String(binding.get("type", "action"))
		if mode not in ["scene_start", "area"] or (_samples.get(id, []) as Array).is_empty():
			continue
		for scene: Node in scenes:
			if scene.scene_file_path != String(binding.get("scene", "")):
				continue
			var anchor: Node3D = scene.get_node_or_null(NodePath(String(binding.get("node", ".")))) as Node3D
			if anchor == null:
				continue
			var key: String = id + ":" + str(anchor.get_instance_id())
			if _triggered.has(key):
				continue
			_triggered[key] = true
			if mode == "scene_start":
				if String(event.get("type", "one")) == "loop":
					start_loop(id, anchor)
				else:
					play(id, anchor.global_position)
			else:
				_add_area(id, anchor, float(binding.get("radius", 3.0)))

func _add_area(id: String, anchor: Node3D, radius: float) -> void:
	var area: Area3D = Area3D.new()
	area.name = "Sonora_" + id
	area.collision_layer = 0
	area.collision_mask = Hitscan.LAYER_PLAYER
	var shape: CollisionShape3D = CollisionShape3D.new()
	var sphere: SphereShape3D = SphereShape3D.new()
	sphere.radius = radius
	shape.shape = sphere
	area.add_child(shape)
	anchor.add_child.call_deferred(area)
	area.body_entered.connect(func(body: Node3D) -> void:
		if body is Player and (body as Player).is_local():
			play(id, anchor.global_position))

func load_audio_file(path: String) -> AudioStream:
	if path.get_extension().to_lower() not in ["wav", "ogg", "mp3"]:
		return null
	if ResourceLoader.exists(path):
		return load(path) as AudioStream
	if not FileAccess.file_exists(path):
		return null
	match path.get_extension().to_lower():
		"wav": return AudioStreamWAV.load_from_file(path)
		"ogg": return AudioStreamOggVorbis.load_from_file(path)
		"mp3": return AudioStreamMP3.load_from_file(path)
	return null


func place_at(pos: Vector3) -> String:
	var cfg: Dictionary = Balance.SHOT_PLACE
	var cell := float(cfg.cell_m)
	var key := Vector3i(roundi(pos.x / cell), roundi(pos.y / cell), roundi(pos.z / cell))
	var now := Time.get_ticks_msec() * 0.001
	var known: Dictionary = _place_cache.get(key, {})
	if not known.is_empty() and now - float(known.t) < float(cfg.ttl_sec):
		return String(known.place)
	var world := get_viewport().find_world_3d() if get_viewport() else null
	var place: String = AcousticPlace.classify(world, pos) if world != null else AcousticPlace.OUTDOOR
	if _place_cache.size() > 512:
		_place_cache.clear()
	_place_cache[key] = {"place": place, "t": now}
	return place


func _track_burst(pos: Vector3, players: Array[AudioStreamPlayer3D]) -> void:
	var cfg: Dictionary = Balance.AUDIO_BURST
	var now := Time.get_ticks_msec() * 0.001
	var mine: Dictionary = {}
	var keep: Array[Dictionary] = []
	for s in _shooters:
		if now - float(s.t) > float(cfg.window_sec):
			continue
		keep.append(s)
		if mine.is_empty() and (s.pos as Vector3).distance_to(pos) <= float(cfg.radius_m):
			mine = s
	_shooters = keep
	if mine.is_empty():
		mine = {"pos": pos, "t": now, "shots": []}
		_shooters.append(mine)
	mine.pos = pos
	mine.t = now
	var shots: Array = mine.shots
	shots.append(players)
	while shots.size() > int(cfg.voices):
		for p: Variant in shots.pop_front():
			# короткий выстрел мог уже доиграть и освободиться — приводить к типу освобождённый объект нельзя
			if is_instance_valid(p):
				_fade_out(p as AudioStreamPlayer3D, float(cfg.fade_sec))


func _fade_out(p: AudioStreamPlayer3D, sec: float) -> void:
	if not p.is_inside_tree():
		return
	p.set_meta("sound_path_fading", true)
	var tw := p.create_tween()
	tw.tween_property(p, "volume_db", p.volume_db - 40.0, sec)
	tw.tween_callback(p.queue_free)


## Подставить записи поверх assets/audio (см. _preview); пустой словарь — только assets/audio.


func step(pos: Vector3, run: bool, ai: bool, extra_db: float, left: bool, right: Vector3 = Vector3.ZERO,
		own: bool = false) -> void:
	# дальше, чем слышно бег, — не считаем (24 мародёра шагают всё время)
	if _has_ears() and _listener_pos().distance_to(pos) > float(Balance.AUDIO_EVENT_PROFILES.step_stone_run["max"]):
		return
	var surf: String = step_surface_at(pos, _surface_under(pos))
	var takes: Dictionary = _step_preview.get(surf, {}) if not ai else {}
	var kind: String = String(takes.get("hook", step_kind_at(pos, surf, run)))
	var db := extra_db + (1.5 if ai else 0.0)
	if run and kind != "step_stone_run":
		db += 3.0
	# Записи моно: направление определяют стопа и уши в мире, а не панорама внутри файла.
	var axis: Vector3 = right
	var side_m: float = Balance.STEP_FOOT_SIDE_M
	if own:
		var listener: Node3D = get_viewport().get_audio_listener_3d()
		if not listener:
			listener = get_viewport().get_camera_3d()
		if listener:
			axis = listener.global_basis.x
			axis.y = 0.0
		side_m *= Balance.lab_number("step_timing", "pan_pct") / 100.0
	var sound_pos: Vector3 = pos + axis.normalized() * side_m * (-1.0 if left else 1.0)
	var recording: AudioStream = _step_recording(takes, surf, pos)
	var material: String = STEP_MATERIALS.get(kind, "")
	if material != "" and recording == null and not _preview.has(kind) and has_sound(STEP_BASE):
		play(STEP_BASE, sound_pos, db)
		play(material, sound_pos, db)
	else:
		play(kind, sound_pos, db, 0.0, null, recording)
	_play_step_layers(pos, sound_pos, kind, db, ai)
	if run:
		play("gear_rattle", pos, db - 5.0)
	stepped.emit(kind, surf, pos)


func _step_recording(takes: Dictionary, key: String, pos: Vector3) -> AudioStream:
	if (takes.get("outdoor", []) as Array).is_empty() and (takes.get("room", []) as Array).is_empty():
		return null
	var place: String = "outdoor" if place_at(pos + Vector3.UP) == AcousticPlace.OUTDOOR else "room"
	var tracks: Array = takes.get(place, [])
	return null if tracks.is_empty() else _pick_from(tracks, "lab:" + key + ":" + place)


func step_layers_at(pos: Vector3) -> Array[Node]:
	var found: Array[Node] = []
	for patch: Node in get_tree().get_nodes_in_group(StepLayerPatch.GROUP):
		if (patch as StepLayerPatch).covers(pos):
			found.append(patch)
	return found


func _play_step_layers(pos: Vector3, sound_pos: Vector3, base: String, db: float, ai: bool) -> void:
	var heard: Dictionary = {}
	for node: Node in step_layers_at(pos):
		var patch: StepLayerPatch = node as StepLayerPatch
		if not Balance.STEP_LAYERS.has(patch.layer) or Balance.lab_number("step_layers", patch.layer + "_on") < 0.5:
			continue
		# Две соседние россыпи стекла не удваивают громкость на стыке.
		var extra: float = Balance.lab_number("step_layers", patch.layer + "_db") + patch.gain_db
		if not heard.has(patch.layer) or extra > float(heard[patch.layer][1]):
			heard[patch.layer] = [patch.sound_event if patch.sound_event != "" else step_hook(patch.layer), extra]
	for layer: String in heard:
		var entry: Array = heard[layer]
		var hook: String = String(entry[0])
		var key: String = "layer_" + layer
		var recording: AudioStream = _layer_recording(layer, key, pos, ai)
		if recording != null or hook != base:
			play(hook, sound_pos, db + float(entry[1]), 0.0, null, recording)


func _layer_recording(layer: String, key: String, pos: Vector3, ai: bool) -> AudioStream:
	if not ai and _step_preview.has(key):
		return _step_recording(_step_preview[key], key, pos)
	if _layer_revision != LabTuning.revision:
		_layer_revision = LabTuning.revision
		_layer_samples.clear()
	if not _layer_samples.has(layer):
		var takes: Array[AudioStream] = []
		for path: String in LabTuning.value("step_layers", layer + "_files"):
			var stream: AudioStream = load_audio_file(path)
			if stream != null:
				takes.append(stream)
		_layer_samples[layer] = takes
	var tracks: Array = _layer_samples[layer]
	return null if tracks.is_empty() else _pick_from(tracks, key)


## Гильза падает рядом со стрелком (from — его ноги, right — вправо от него).
## Запись выбирается по поверхности и калибру оружия.


func shell_drop(from: Vector3, right: Vector3, extra_db: float = 0.0, weapon_id: String = "") -> void:
	var cfg: Dictionary = Balance.SHELL_DROP
	if _has_ears() and _listener_pos().distance_to(from) > float(cfg.hear_m):
		return
	var side := right * _rng.randf_range(float(cfg.side_min), float(cfg.side_max))
	# right × вверх = назад стрелка (взгляд по −Z, вправо +X)
	var land := from + side + right.cross(Vector3.UP) * float(cfg.back)
	var delay := _rng.randf_range(float(cfg.delay_min), float(cfg.delay_max))
	get_tree().create_timer(delay).timeout.connect(func() -> void: _shell_land(land, extra_db, weapon_id))


func _shell_land(land: Vector3, extra_db: float, weapon_id: String = "") -> void:
	var surf := _surface_under(land)
	if WaterBody.depth_at(land) > 0.0:
		surf = "water"
	play(shell_hook(surf, weapon_id), land, extra_db)


func step_hook(surface: String, run: bool = false) -> String:
	var hook: String = String(_surface_steps.get(surface, "step_concrete"))
	if run and hook == "step_stone" and has_sound("step_stone_run"):
		return "step_stone_run"
	return hook


func step_surface_at(pos: Vector3, surface: String) -> String:
	# Вброд слышна вода независимо от того, какое покрытие под ней.
	return "water" if WaterBody.depth_at(pos) > float(Balance.WATER.ankle) else surface


func step_kind_at(pos: Vector3, surface: String, run: bool = false) -> String:
	if surface == "asphalt" and _wet_asphalt_at(pos):
		return "step_water"
	return step_hook(surface, run)


func step_surface_name(surface: String) -> String:
	return String({"asphalt": "асфальт", "concrete": "бетон", "tile": "плитка", "gravel": "гравий / щебень",
		"grass": "трава", "sand": "песок", "dirt": "земля", "mud": "грязь", "leaves": "листья",
		"fabric": "ткань", "wood": "дерево", "metal": "металл", "glass": "стекло",
		"water": "вода", "puddle": "лужи", "carpet": "ковёр", "snow": "снег", "trash": "мусор",
		"rubble": "щебень", "trash_bags": "мусорные пакеты", "plastic": "пластик",
		"cardboard": "картон", "ladder": "лестница", "asphalt_wet": "мокрый асфальт"}.get(surface, surface))


func step_event_name(hook: String) -> String:
	var id: String = resolve_event(hook)
	var event: Dictionary = _events.get(id, {})
	var count: int = (_samples.get(id, []) as Array).size()
	return "%s · %s" % [String(event.get("name", hook)), "%d записей" % count if count > 0 else "без записи"]


func step_catalog() -> Array[Dictionary]:
	var result: Array[Dictionary] = []
	var slots: Array = _step_slots + [
		{"hook": "step_stone_run", "name": "Бег по плитке", "surfaces": ["tile"]},
		{"hook": "crawl", "name": "Ползание", "surfaces": []},
		{"hook": "land", "name": "Приземление", "surfaces": []},
	]
	for slot: Dictionary in slots:
		var id: String = resolve_event(String(slot.hook))
		var event: Dictionary = _events.get(id, {})
		var loaded: Dictionary = {}
		for stream: AudioStream in _samples.get(id, []):
			var path: String = String(_stream_files.get(stream.get_instance_id(), ""))
			if not path.is_empty():
				loaded[path] = stream
		result.append({"hook": slot.hook, "name": event.get("name", slot.name), "surfaces": slot.surfaces,
			"files": event.get("files", []), "loaded": loaded})
	return result


func shell_hook(surface: String, weapon_id: String = "") -> String:
	var weapon: Dictionary = WeaponDb.weapon(weapon_id)
	if weapon.get("class") == "SPECIAL":
		return ""
	var hook: String = String(_surface_shells.get(surface, "shell_concrete"))
	if weapon.get("caliber") == "12x76":
		return "shell_12_" + hook.trim_prefix("shell_")
	return hook


## Под навесом асфальт сухой, как в шейдере покрытия; погода проверяется у шагающего, не у слушателя.


func _wet_asphalt_at(pos: Vector3) -> bool:
	var weather: RaidWeather = RaidWeather.current
	if weather == null:
		return false
	var cfg: Dictionary = Balance.WET_STEPS
	if weather.wet < float(cfg.film_min) and weather.puddles < float(cfg.puddle_min):
		return false
	var world: World3D = get_viewport().find_world_3d() if get_viewport() else null
	if world == null:
		return false
	var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(
		pos + Vector3.UP * float(cfg.roof_lift), pos + Vector3.UP * float(cfg.roof_height), Hitscan.LAYER_WORLD)
	return world.direct_space_state.intersect_ray(q).is_empty()


## Из чего пол под точкой (Surfaces), "concrete" — если не понять.


func _surface_under(pos: Vector3) -> String:
	return Surfaces.kind_at(ground_hit(pos))


func ground_hit(pos: Vector3) -> Dictionary:
	var world := get_viewport().find_world_3d() if get_viewport() else null
	if world == null:
		return {}
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.4, pos + Vector3.DOWN * 0.6, Hitscan.LAYER_WORLD)
	var hit := world.direct_space_state.intersect_ray(q)
	# бесконечная «земля» (WorldBoundary) лежит над полами двора — смотрим, что под ней
	if not hit.is_empty() and _is_boundary(hit):
		q.exclude = [(hit.collider as CollisionObject3D).get_rid()]
		hit = world.direct_space_state.intersect_ray(q)
	return hit


func _is_boundary(hit: Dictionary) -> bool:
	var co := hit.get("collider") as CollisionObject3D
	if co == null:
		return false
	var sn := co.shape_owner_get_owner(co.shape_find_owner(int(hit.get("shape", 0)))) as CollisionShape3D
	return sn != null and sn.shape is WorldBoundaryShape3D


## Есть кто слушает (камера или AudioListener3D) — иначе расстояние до «ушей» не знаем.


func _has_ears() -> bool:
	var vp := get_viewport()
	return vp != null and (vp.get_audio_listener_3d() != null or vp.get_camera_3d() != null)


## Между ушами и источником — стена или дверь.


func _occluded(listener: Vector3, pos: Vector3) -> bool:
	var world := get_viewport().find_world_3d() if get_viewport() else null
	return world != null and SoundPropagation.sample(world.direct_space_state, listener, pos).x > 0.0


func _listener_pos() -> Vector3:
	var vp := get_viewport()
	var l := vp.get_audio_listener_3d() if vp else null
	if l:
		return l.global_position
	var cam := vp.get_camera_3d() if vp else null
	return cam.global_position if cam else Vector3.ZERO


func make_loop(st: AudioStream) -> void:
	if st is AudioStreamOggVorbis:
		(st as AudioStreamOggVorbis).loop = true
	elif st is AudioStreamMP3:
		(st as AudioStreamMP3).loop = true
	elif st is AudioStreamWAV:
		var w := st as AudioStreamWAV
		var bytes := (1 if w.format == AudioStreamWAV.FORMAT_8_BITS else 2) * (2 if w.stereo else 1)
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_begin = 0
		w.loop_end = w.data.size() / bytes


## Отдельные записи по путям относительно assets/audio (назначенные в data/sound_active.json).

const STEP_SET: Dictionary = {
	"tile": "stone", "concrete": "concrete", "asphalt": "concrete", "plastic": "trash", "wood": "wood", "glass": "glass",
	"metal": "metal", "cardboard": "trash", "fabric": "carpet", "carpet": "carpet", "snow": "dirt", "sand": "sand",
	"water": "water", "trash": "trash", "trash_bags": "trash", "rubble": "gravel", "gravel": "gravel", "grass": "grass", "leaves": "grass",
	"dirt": "dirt", "mud": "dirt",
}
