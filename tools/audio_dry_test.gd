extends Node3D
## Измеряет реальный выход Audio: прямой звук, воздух и преграды.

var checked: int = 0
var failed: int = 0
var probe: AudioStreamWAV
var recordings: Dictionary = {}
var output_folder: String = ""

func check(condition: bool, label: String) -> void:
	checked += 1
	if not condition:
		failed += 1
		push_error(label)

func _ready() -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if not args.is_empty():
		output_folder = args[0]
		DirAccess.make_dir_recursive_absolute(output_folder)
	for bus: String in Settings.BUSES:
		check(AudioServer.get_bus_effect_count(AudioServer.get_bus_index(bus)) == 0, bus + ": шина без постэффектов")
	var camera: Camera3D = Camera3D.new()
	add_child(camera)
	camera.current = true
	probe = _make_probe()
	var old_preview: Dictionary = Audio._preview.duplicate()
	Audio.set_preview({"wpn_hg_02_shot": [probe]})
	var reference: PackedVector2Array = await _capture("reference", 1.0, "outdoor", true)
	check(_energy(reference) > 0.00001, "Микшер действительно выдал тестовый сигнал")
	for item: Dictionary in [{"name":"near", "distance":1.0, "place":"outdoor"}, {"name":"room", "distance":1.0, "place":"room"}, {"name":"hall", "distance":1.0, "place":"hall"}, {"name":"far", "distance":20.0, "place":"outdoor"}]:
		var recorded: PackedVector2Array = await _capture(String(item.name), float(item.distance), String(item.place), false)
		var measurement: Dictionary = _compare(reference, recorded)
		recordings[String(item.name)] = measurement
		print("DRY_WAVE ", item.name, " ", JSON.stringify(measurement))
		check(float(measurement.error) < 0.015, String(item.name) + ": форма сигнала сохранена после поправки громкости")
		check(float(measurement.late) < 0.000001, String(item.name) + ": движок не добавляет хвост")
	check(float(recordings.far.gain) < float(recordings.near.gain), "Расстояние уменьшает громкость")
	await _test_propagation()
	var far_shot := await _capture("ordinary_625m", 625.0, "outdoor", false, true)
	var original_profile: Dictionary = Balance.SONORA_AUDIO.shot.duplicate()
	original_profile.erase("far_gain_k")
	var far_original := await _capture("ordinary_625m_original", 625.0, "outdoor", false, true, original_profile)
	var far_gain: float = _tone(far_shot, 200.0) / maxf(0.000001, _tone(far_original, 200.0))
	print("SHOT_RANGE far_amplitude_ratio=%.3f" % far_gain)
	check(absf(far_gain - 2.0) < 0.08, "Микшер удваивает амплитуду дальнего выстрела")
	var near_shot := await _capture("ordinary_25m", 25.0, "outdoor", false)
	var range_loss := linear_to_db(_tone(far_shot, 200.0) / maxf(0.000001, _tone(near_shot, 200.0)))
	print("SHOT_RANGE ordinary_625m_relative_to_25m_db=%.2f" % range_loss)
	check(range_loss > -27.0 and range_loss < -15.0, "Дальний выстрел сохраняет низ и заметно тише ближнего")
	Audio.play("wpn_hg_02_shot", Vector3(0, 0, -1), 0.0, 0.72)
	var pitched: AudioStreamPlayer3D = find_children("*", "AudioStreamPlayer3D", true, false).back() as AudioStreamPlayer3D
	check(pitched.pitch_scale == 1.0, "Прежний параметр pitch не меняет готовую запись")
	pitched.stop()
	pitched.queue_free()
	var source: AudioStreamPlayer3D = AudioStreamPlayer3D.new()
	source.pitch_scale = 0.76
	source.emission_angle_enabled = true
	source.area_mask = 1
	add_child(source)
	check(is_equal_approx(source.pitch_scale, 1.0), "Источники сцены сохраняют высоту записи")
	check(source.attenuation_filter_db == 0.0 and source.area_mask == 0, "Источники сцены без встроенного фильтра и зон FX")
	check(not source.emission_angle_enabled, "Конус источника не меняет спектр")
	source.queue_free()
	var loop: AudioStreamPlayer3D = Audio.start_loop("wpn_hg_02_shot", self)
	check(loop != null and loop.attenuation_filter_db == 0.0 and loop.pitch_scale == 1.0, "Петли проходят тем же чистым маршрутом")
	if loop != null:
		loop.stop()
		loop.queue_free()
	Audio.set_preview(old_preview)
	Audio._place_cache.clear()
	var shots: int = AudioServer.get_bus_index("Shots")
	AudioServer.add_bus_effect(shots, AudioEffectReverb.new())
	Settings._make_buses()
	check(AudioServer.get_bus_effect_count(shots) == 0, "Инициализация очищает прежние эффекты шин")
	for bus_name: String in ["Sonora_room", "Sonora_hall", "ShelterLiving", "ShelterUtility"]:
		check(AudioServer.get_bus_index(bus_name) < 0, "Нет автоматической шины " + bus_name)
	var summary: Dictionary = {"checked":checked,"failed":failed,"recordings":recordings}
	if output_folder != "":
		var report: FileAccess = FileAccess.open(output_folder.path_join("report.json"), FileAccess.WRITE)
		report.store_string(JSON.stringify(summary, "  "))
	print("AUDIO_DRY_TEST checked=", checked, " failed=", failed)
	get_tree().quit(1 if failed else 0)

func _make_probe() -> AudioStreamWAV:
	var rate: int = int(AudioServer.get_mix_rate())
	var data: PackedByteArray = PackedByteArray()
	data.resize(int(rate * 0.2) * 2)
	for i: int in range(data.size() / 2):
		var time: float = float(i) / float(rate) - 0.05
		var value: float = 0.0
		if time >= 0.0 and time < 0.09:
			var envelope: float = sin(PI * time / 0.09) * exp(-time * 24.0)
			value = envelope * (0.18 * sin(TAU * 100.0 * time) + 0.25 * sin(TAU * 200.0 * time)
				+ 0.18 * sin(TAU * 1000.0 * time) + 0.12 * sin(TAU * 9000.0 * time))
		data.encode_s16(i * 2, int(round(value * 32767.0)))
	var stream: AudioStreamWAV = AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = data
	return stream

func _capture(label: String, distance: float, place: String, direct: bool, filtered: bool = false,
		profile: Dictionary = {}) -> PackedVector2Array:
	# Захват только читает отсчёты; в игровом пути этого эффекта нет.
	var master: int = AudioServer.get_bus_index("Master")
	var tap: AudioEffectCapture = AudioEffectCapture.new()
	tap.buffer_length = 1.0
	AudioServer.add_bus_effect(master, tap)
	await get_tree().create_timer(0.06).timeout
	tap.clear_buffer()
	if direct:
		var player: AudioStreamPlayer = AudioStreamPlayer.new()
		player.stream = probe
		player.finished.connect(player.queue_free)
		add_child(player)
		player.play()
	else:
		var pos: Vector3 = Vector3(0, 0, -distance)
		var cell: float = float(Balance.SHOT_PLACE.cell_m)
		var key: Vector3i = Vector3i(roundi(pos.x / cell), roundi(pos.y / cell), roundi(pos.z / cell))
		Audio._place_cache[key] = {"place":place,"t":Time.get_ticks_msec() * 0.001}
		if distance > float(Balance.AUDIO_FAR.delay_from_m):
			Audio._play_now("wpn_hg_02_shot", "wpn_hg_02_shot_outdoor", probe, pos, 0.0,
				Balance.SONORA_AUDIO.shot if profile.is_empty() else profile)
		else:
			Audio.play("wpn_hg_02_shot", pos)
		var players: Array[Node] = find_children("*", "AudioStreamPlayer3D", true, false)
		check(not players.is_empty(), label + ": источник создан")
		if not players.is_empty():
			var player: AudioStreamPlayer3D = players.back() as AudioStreamPlayer3D
			check(player.pitch_scale == 1.0 and (player.attenuation_filter_db < 0.0 if filtered else player.attenuation_filter_db == 0.0),
				label + ": высота записи сохранена, фильтр в нужном состоянии")
			check(player.bus == &"Shots", label + ": обычная шина выстрелов")
	await get_tree().create_timer(0.55).timeout
	var frames: PackedVector2Array = tap.get_buffer(tap.get_frames_available())
	for index: int in range(AudioServer.get_bus_effect_count(master) - 1, -1, -1):
		if AudioServer.get_bus_effect(master, index) == tap:
			AudioServer.remove_bus_effect(master, index)
	if output_folder != "":
		var wav: AudioStreamWAV = AudioStreamWAV.new()
		wav.mix_rate = int(AudioServer.get_mix_rate())
		wav.format = AudioStreamWAV.FORMAT_16_BITS
		wav.stereo = true
		var data: PackedByteArray = PackedByteArray()
		data.resize(frames.size() * 4)
		for i: int in frames.size():
			data.encode_s16(i * 4, int(clampf(frames[i].x, -1.0, 1.0) * 32767))
			data.encode_s16(i * 4 + 2, int(clampf(frames[i].y, -1.0, 1.0) * 32767))
		wav.data = data
		wav.save_to_wav(output_folder.path_join(label + ".wav"))
	return frames


func _test_propagation() -> void:
	var wall := StaticBody3D.new()
	wall.collision_layer = Hitscan.LAYER_WORLD
	var box := BoxShape3D.new()
	box.size = Vector3(2.0, 4.0, 0.2)
	var shape := CollisionShape3D.new()
	shape.shape = box
	wall.add_child(shape)
	wall.position = Vector3(0, 0, -4.0)
	add_child(wall)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var blocked := await _capture("behind_wall", 8.0, "outdoor", false, true)
	wall.position.x = 4.0
	await get_tree().physics_frame
	await get_tree().physics_frame
	var clear := await _capture("open_same_distance", 8.0, "outdoor", false)
	_check_spectral_loss("Стена", blocked, clear, 12.0)
	var distant := await _capture("far_air", 170.0, "outdoor", false, true)
	_check_spectral_loss("Воздух на 170 м", distant, clear, 3.0)
	# Во время петли стену можно поставить и убрать, а громкость записи по-прежнему настраивается.
	var source := Node3D.new()
	source.position = Vector3(0, 0, -8.0)
	add_child(source)
	var loop := Audio.start_loop("wpn_hg_02_shot", source)
	check(loop != null and loop.attenuation_filter_db == 0.0, "Петля начинается с чистого пути")
	wall.position.x = 0.0
	await get_tree().create_timer(0.36).timeout
	check(loop.attenuation_filter_db < -12.0 and loop.volume_db < -6.0, "Фильтр и уровень меняются во время звука")
	var blocked_level := loop.volume_db
	var id := String(loop.get_meta("audio_event"))
	var gain := Audio.mix_gain(id)
	Audio.set_mix_gain(id, gain + 2.0)
	check(absf(loop.volume_db - blocked_level - 2.0) < 0.05, "Настройка громкости сохраняет ослабление стены")
	Audio.set_mix_gain(id, gain)
	wall.position.x = 4.0
	await get_tree().create_timer(0.60).timeout
	print("SOUND_PATH reopen filter_db=%.2f level_db=%.2f blocked_level_db=%.2f" % [
		loop.attenuation_filter_db, loop.volume_db, blocked_level])
	check(absf(loop.attenuation_filter_db) < 1.0 and loop.volume_db > blocked_level + 8.0, "После выхода из-за стены звук проясняется")
	source.queue_free()
	wall.queue_free()
	await _test_door_path()


func _test_door_path() -> void:
	var door := (load("res://scenes/props/door.tscn") as PackedScene).instantiate() as Door
	door.position = Vector3(2.0, -1.2, -4.0)
	add_child(door)
	var panel := StaticBody3D.new()
	panel.collision_layer = Hitscan.LAYER_WORLD
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(7.0, 4.0, 0.2)
	shape.shape = box
	panel.add_child(shape)
	panel.position = Vector3(-1.5, 0.0, -4.0)
	add_child(panel)
	await get_tree().physics_frame
	await get_tree().physics_frame
	var source := Vector3(1.1, 0, -8)
	var world := get_world_3d()
	check(not Audio.SoundPropagation.through_door(world.direct_space_state, Vector3.ZERO, source, [door]).is_finite(),
		"Закрытая дверь не пропускает обход")
	door.is_open = true
	door._target_angle = PI * 0.5
	(door.get_node("Leaf") as Node3D).rotation.y = PI * 0.5
	await get_tree().physics_frame
	await get_tree().physics_frame
	var player := Audio._play_now("wpn_hg_02_shot", "wpn_hg_02_shot_outdoor", probe, source, 0.0, Balance.SONORA_AUDIO.shot)
	check(is_equal_approx(float(player.get_meta("sound_path_loss_db")), float(Balance.SOUND_PROPAGATION.door_path.x))
		and player.global_position.x > 2.0 and player.global_position.length() > source.length(),
		"С закрытой прямой звук слышен со стороны открытого проёма")
	player.queue_free()
	panel.collision_layer = Hitscan.LAYER_GLASS
	door.is_open = false
	await get_tree().physics_frame
	await get_tree().physics_frame
	check(Audio.SoundPropagation.sample(world.direct_space_state, Vector3.ZERO, source) == Balance.SOUND_PROPAGATION.glass,
		"Целое стекло глушит слабее стены")
	panel.collision_layer = 0
	await get_tree().physics_frame
	await get_tree().physics_frame
	check(Audio.SoundPropagation.sample(world.direct_space_state, Vector3.ZERO, source) == Vector2.ZERO,
		"После исчезновения стекла прямой путь чистый")
	panel.queue_free()
	door.queue_free()


func _check_spectral_loss(label: String, recorded: PackedVector2Array, clear: PackedVector2Array, min_db: float) -> void:
	var low := linear_to_db(_tone(recorded, 200.0) / maxf(0.000001, _tone(clear, 200.0)))
	var high := linear_to_db(_tone(recorded, 9000.0) / maxf(0.000001, _tone(clear, 9000.0)))
	print("SOUND_PATH ", label, " low_db=%.2f high_db=%.2f" % [low, high])
	check(_energy(recorded) > 0.000001 and low < -1.0 and high < low - min_db,
		label + ": верх тише низа после выравнивания громкости")

func _energy(data: PackedVector2Array) -> float:
	var sum: float = 0.0
	for value: Vector2 in data:
		sum += value.length_squared()
	return sum


func _tone(data: PackedVector2Array, hz: float) -> float:
	var rate: float = AudioServer.get_mix_rate()
	var magnitude: Vector2 = Vector2.ZERO
	for i: int in data.size():
		magnitude += (data[i].x + data[i].y) * Vector2.from_angle(TAU * hz * float(i) / rate)
	return magnitude.length()

func _start(data: PackedVector2Array) -> int:
	for i: int in data.size():
		if absf(data[i].x) + absf(data[i].y) > 0.00005:
			return i
	return 0

func _compare(reference: PackedVector2Array, recorded: PackedVector2Array) -> Dictionary:
	var count: int = int(AudioServer.get_mix_rate() * 0.2)
	var a: int = _start(reference)
	var b: int = _start(recorded)
	var best: float = INF
	var best_gain: float = 0.0
	for lag: int in range(-12, 13):
		var xx: float = 0.0
		var xy: float = 0.0
		var yy: float = 0.0
		for i: int in count:
			if a+i >= reference.size() or b+i+lag < 0 or b+i+lag >= recorded.size():
				continue
			var x: float = reference[a+i].x + reference[a+i].y
			var y: float = recorded[b+i+lag].x + recorded[b+i+lag].y
			xx += x*x
			xy += x*y
			yy += y*y
		var gain: float = xy / maxf(xx, 0.000000001)
		var error: float = sqrt(maxf(0.0, yy - xy*xy / maxf(xx, 0.000000001)) / maxf(yy, 0.000000001))
		if error < best:
			best = error
			best_gain = gain
	var late: float = 0.0
	for i: int in range(b + int(AudioServer.get_mix_rate() * 0.25), recorded.size()):
		late += recorded[i].length_squared()
	return {"error":best,"gain":best_gain,"late":late / maxf(_energy(recorded), 0.000000001),"frames":recorded.size()}
