extends Node3D
## Измеряет реальный выход Audio: запись проходит без окраски и добавленного хвоста.

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
			value = envelope * (0.32 * sin(TAU * 200.0 * time) + 0.18 * sin(TAU * 3000.0 * time) + 0.12 * sin(TAU * 9000.0 * time))
		data.encode_s16(i * 2, int(round(value * 32767.0)))
	var stream: AudioStreamWAV = AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = data
	return stream

func _capture(label: String, distance: float, place: String, direct: bool) -> PackedVector2Array:
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
		Audio.play("wpn_hg_02_shot", pos)
		var players: Array[Node] = find_children("*", "AudioStreamPlayer3D", true, false)
		check(not players.is_empty(), label + ": источник создан")
		if not players.is_empty():
			var player: AudioStreamPlayer3D = players.back() as AudioStreamPlayer3D
			check(player.pitch_scale == 1.0 and player.attenuation_filter_db == 0.0, label + ": высота и спектр без обработки")
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

func _energy(data: PackedVector2Array) -> float:
	var sum: float = 0.0
	for value: Vector2 in data:
		sum += value.length_squared()
	return sum

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
