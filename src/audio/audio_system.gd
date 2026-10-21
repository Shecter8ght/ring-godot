extends Node
## Только явно назначенные записи. Пустое действие молчит; расстояние и помещение считает движок.

const REGISTRY: String = "res://data/audio_events.json"
const AcousticPlace := preload("res://src/audio/acoustic_place.gd")

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
var _scan_needed: bool = true
var _scene_paths: Dictionary = {}
var _object_bindings: Dictionary = {}

func _ready() -> void:
	_rng.randomize()
	reload_events()
	get_tree().node_added.connect(_on_audio_node_added)
	for node: Node in get_tree().root.find_children("*", "BaseButton", true, false):
		_on_audio_node_added(node)
	set_process(true)

func reload_events() -> void:
	_scan_needed = true
	_events.clear()
	_bindings.clear()
	_samples.clear()
	_scene_paths.clear()
	_object_bindings.clear()
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
			var stream: AudioStream = _load_audio_file("res://assets/audio/" + rel)
			if stream != null:
				streams.append(stream)
		_samples[id] = streams
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
	var actual: String = hook
	if _is_weapon_shot(hook) and place != "":
		var specific: String = String(_bindings.get(hook + "_" + place, ""))
		if not (_samples.get(specific, []) as Array).is_empty():
			return specific
	if _events.has(actual):
		return actual
	return String(_bindings.get(actual, ""))

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

func play(hook: String, pos: Vector3, extra_db: float = 0.0, pitch: float = 0.0, emitter: Node = null) -> void:
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
	var stream: AudioStream = _pick(id if id != "" and not _preview.has(hook) else hook, pos)
	if stream == null:
		return
	var baked_place: bool = place != "" and id == String(_bindings.get(hook + "_" + place, ""))
	var delay: float = distance / float(Balance.AUDIO_FAR.sound_mps) if _has_ears() and bool(spec.get("far", false)) and distance > float(Balance.AUDIO_FAR.delay_from_m) else 0.0
	if delay > 0.0:
		get_tree().create_timer(delay).timeout.connect(func() -> void: _play_now(hook, id, stream, pos, extra_db, pitch, spec, place, baked_place))
	else:
		_play_now(hook, id, stream, pos, extra_db, pitch, spec, place, baked_place)

func _matches_object(emitter: Node, binding: Dictionary) -> bool:
	var ancestor: Node = emitter
	while ancestor != null:
		if ancestor.scene_file_path == String(binding.scene):
			var target: Node = ancestor.get_node_or_null(NodePath(String(binding.node)))
			if target != null and (target == emitter or target.is_ancestor_of(emitter)):
				return true
		ancestor = ancestor.get_parent()
	return false

func _play_now(hook: String, id: String, stream: AudioStream, pos: Vector3, extra_db: float, pitch: float, spec: Dictionary, place: String, baked_place: bool) -> void:
	if get_tree().current_scene == null:
		return
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.stream = stream
	player.volume_db = float(spec.db) + extra_db
	player.unit_size = float(spec.unit) * float(Settings.headset.get("hear_k", 1.0))
	player.max_distance = float(spec["max"])
	player.attenuation_model = AudioStreamPlayer3D.ATTENUATION_INVERSE_DISTANCE
	player.pitch_scale = pitch if pitch > 0.0 else 1.0
	if bool(spec.get("far", false)):
		player.attenuation_filter_cutoff_hz = float(Balance.AUDIO_FAR.cutoff_hz)
		player.attenuation_filter_db = float(Balance.AUDIO_FAR.filter_db)
	if _has_ears() and _occluded(_listener_pos(), pos):
		player.volume_db -= float(Balance.AUDIO_OCCLUDED_DB)
		player.attenuation_filter_cutoff_hz = float(Balance.AUDIO_OCCLUDED_CUTOFF)
	player.bus = _acoustic_bus(hook, place) if not baked_place else Settings.bus_for(hook)
	player.finished.connect(player.queue_free)
	get_tree().current_scene.add_child(player)
	player.global_position = pos
	player.play()
	event_played.emit(id, hook, pos)
	if _is_weapon_shot(hook):
		_track_burst(pos, [player])

func _is_weapon_shot(hook: String) -> bool:
	var id: String = String(_bindings.get(hook, hook))
	var event: Dictionary = _events.get(id, {}) as Dictionary
	return String(event.get("weapon", "")) != "" and String(event.get("action", "")) in ["shot", "shot_suppressed"]

func _kind_spec(hook: String) -> Dictionary:
	var event: Dictionary = _events.get(resolve_event(hook), {}) as Dictionary
	var profile: String = String(event.get("profile", ""))
	if String(event.get("weapon", "")) != "":
		if String(event.get("action", "")).begins_with("shot"):
			return Balance.SONORA_AUDIO.shot
		return Balance.SONORA_AUDIO.weapon_action
	return Balance.AUDIO_EVENT_PROFILES.get(profile, Balance.AUDIO_EVENT_PROFILES.get(hook, Balance.SONORA_AUDIO.world)) as Dictionary

func _acoustic_bus(hook: String, place: String) -> StringName:
	if not _is_weapon_shot(hook) or place not in ["room", "hall"]:
		return Settings.bus_for(hook)
	var bus_name: StringName = StringName("Sonora_" + place)
	if AudioServer.get_bus_index(bus_name) < 0:
		var index: int = AudioServer.bus_count
		AudioServer.add_bus(index)
		AudioServer.set_bus_name(index, bus_name)
		AudioServer.set_bus_send(index, &"Shots")
		var effect: AudioEffectReverb = AudioEffectReverb.new()
		var cfg: Dictionary = Balance.SONORA_AUDIO.get(place, {}) as Dictionary
		effect.room_size = float(cfg.size)
		effect.damping = float(cfg.damping)
		effect.wet = float(cfg.wet)
		effect.dry = 1.0
		AudioServer.add_bus_effect(index, effect)
	return bus_name

func play_ui(hook: String, extra_db: float = 0.0) -> void:
	var stream: AudioStream = _pick(hook, _listener_pos())
	if stream == null:
		return
	var player: AudioStreamPlayer = AudioStreamPlayer.new()
	player.stream = stream
	player.volume_db = extra_db
	player.bus = &"World"
	player.finished.connect(player.queue_free)
	add_child(player)
	player.play()
	event_played.emit(resolve_event(hook), hook, _listener_pos())

func start_loop(hook: String, parent: Node3D, extra_db: float = 0.0) -> AudioStreamPlayer3D:
	var stream: AudioStream = _pick(hook, parent.global_position)
	if stream == null:
		return null
	make_loop(stream)
	var spec: Dictionary = _kind_spec(hook)
	var player: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	player.stream = stream
	player.volume_db = float(spec.db) + extra_db
	player.unit_size = float(spec.unit)
	player.max_distance = float(spec["max"])
	player.bus = Settings.bus_for(hook)
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

func _on_audio_node_added(node: Node) -> void:
	if node is Node3D and _scene_paths.has(node.scene_file_path):
		_scan_needed = true
	if node is BaseButton and not node.has_meta("sound_wired"):
		var button: BaseButton = node as BaseButton
		button.set_meta("sound_wired", true)
		button.pressed.connect(func() -> void: play_ui("ui_click", -5.0))
		button.mouse_entered.connect(func() -> void:
			if not button.disabled:
				play_ui("ui_hover", -11.0))

func _process(_delta: float) -> void:
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

func _load_audio_file(path: String) -> AudioStream:
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


## Хвост места к выстрелу: тот же стрелок, та же дальность и шина; громкость — от выстрела по месту
## (Balance.SHOT_TAIL). null — записей хвоста нет или слушатель слишком далеко.


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
	var tw := p.create_tween()
	tw.tween_property(p, "volume_db", p.volume_db - 40.0, sec)
	tw.tween_callback(p.queue_free)


## Подставить записи поверх assets/audio (см. _preview); пустой словарь — только assets/audio.


func step(pos: Vector3, run: bool, ai: bool, extra_db: float, left: bool, right: Vector3 = Vector3.ZERO) -> void:
	# дальше, чем слышно бег, — не считаем (24 мародёра шагают всё время)
	if _has_ears() and _listener_pos().distance_to(pos) > float(Balance.AUDIO_EVENT_PROFILES.step_stone_run["max"]):
		return
	var surf := _surface_under(pos)
	# вброд — плеск, что бы ни было на дне
	if WaterBody.depth_at(pos) > float(Balance.WATER.ankle):
		surf = "water"
	var sset := String(STEP_SET.get(surf, "stone"))
	var pitch := (0.97 if left else 1.02) * (0.93 if ai else 1.0) * _rng.randf_range(0.97, 1.03)
	var db := extra_db + (1.5 if ai else 0.0)
	var has_run_set := sset in ["stone", "dirt", "snow"]
	var kind := "step_%s%s" % [sset, "_run" if run and has_run_set else ""]
	if surf == "asphalt" and not run and _wet_asphalt_at(pos):
		kind = "step_asphalt_wet"
	# Записи моно: направление определяют стопа и уши в мире, а не панорама внутри файла.
	var sound_pos: Vector3 = pos + right.normalized() * Balance.STEP_FOOT_SIDE_M * (-1.0 if left else 1.0)
	play(kind, sound_pos, db, pitch)
	if run:
		play("gear_rattle", pos, db - 5.0, pitch)
	stepped.emit(kind, surf, pos)


## Гильза упала рядом со стрелком (from — его ноги, right — вправо от него): звук по полу под ней,
## на твёрдом иногда ещё катится. Физической гильзы нет, только звук. Записей нет — молчит.


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
	var cfg: Dictionary = Balance.SHELL_DROP
	var surf := _surface_under(land)
	var kind := "shell_soft"
	if surf in (cfg.metal as Array):
		kind = "shell_metal"
	elif surf in (cfg.hard as Array):
		kind = "shell_hard"
	play(weapon_id + "_" + kind if weapon_id != "" else kind, land, float(cfg.db) + extra_db)
	if kind != "shell_soft" and _rng.randf() < float(cfg.roll_chance):
		get_tree().create_timer(float(cfg.roll_delay)).timeout.connect(
			func() -> void: play(weapon_id + "_shell_roll" if weapon_id != "" else "shell_roll", land, float(cfg.db) + extra_db))


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
	var world := get_viewport().find_world_3d() if get_viewport() else null
	if world == null:
		return "concrete"
	var q := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.4, pos + Vector3.DOWN * 0.6, Hitscan.LAYER_WORLD)
	var hit := world.direct_space_state.intersect_ray(q)
	# бесконечная «земля» (WorldBoundary) лежит над полами двора — смотрим, что под ней
	if not hit.is_empty() and _is_boundary(hit):
		q.exclude = [(hit.collider as CollisionObject3D).get_rid()]
		hit = world.direct_space_state.intersect_ray(q)
	return Surfaces.kind_at(hit) if not hit.is_empty() else "concrete"


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
	if world == null or listener.distance_to(pos) < 1.5:
		return false
	var q := PhysicsRayQueryParameters3D.create(listener, pos + Vector3.UP * 0.4, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
	return not world.direct_space_state.intersect_ray(q).is_empty()


## Запись (или дальняя запись), иначе синтетика.


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
	"tile": "stone", "concrete": "stone", "plastic": "stone", "wood": "wood", "glass": "glass",
	"metal": "metal", "asphalt": "dirt", "cardboard": "cardboard", "fabric": "carpet", "snow": "snow",
	"water": "water", "trash": "trash", "rubble": "rubble", "gravel": "gravel", "grass": "grass",
	"dirt": "dirt", "mud": "dirt",
}
