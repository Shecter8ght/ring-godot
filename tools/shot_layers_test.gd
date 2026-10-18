extends Node3D
## Слои дистанции выстрела и очереди (Audio): какой слой звучит на каком расстоянии, переход без
## провала громкости, свой выстрел — только у набора, что звучит вблизи, очередь не копит плееры сверх
## предела, выстрелы моделей — на шине «Выстрелы» с потолком, кандидаты нарезки
## (tools/prepare_firearm_layers.py) назначены существующим событиям стенда.
## tools/godot.cmd --headless res://tools/shot_layers_test.tscn

const RECIPE := "res://data/audio_recipes/firearm_layers.json"

var _fails: int = 0


## Считает ошибки движка и скриптов за кусок прогона: ошибка внутри Audio сама тест не роняет.
class ErrorCatcher extends Logger:
	var errors: int = 0

	func _log_error(_function: String, _file: String, _line: int, _code: String, _rationale: String,
			_editor_notify: bool, _error_type: int, _script_backtraces: Array[ScriptBacktrace]) -> void:
		errors += 1


func _ready() -> void:
	var cam := Camera3D.new()
	add_child(cam)
	cam.current = true
	await get_tree().process_frame
	var w := _silence(1.5)
	Audio.set_preview({"shot_rifle@self": [w], "shot_rifle@mid": [w], "shot_rifle@far": [w], "shot_rifle@distant": [w],
		"shot_pistol@self": [w], "shot_pistol@mid": [w]})

	_check("0.5 м — только свой выстрел", _layers("shot_rifle", 0.5) == ["self"], str(_layers("shot_rifle", 0.5)))
	_check("5 м — только вблизи", _layers("shot_rifle", 5.0) == ["near"], str(_layers("shot_rifle", 5.0)))
	_check("15 м — вблизи и средняя вместе", _layers("shot_rifle", 15.0) == ["mid", "near"], str(_layers("shot_rifle", 15.0)))
	_check("40 м — средняя", _layers("shot_rifle", 40.0) == ["mid"], str(_layers("shot_rifle", 40.0)))
	_check("80 м — средняя и вдали", _layers("shot_rifle", 80.0) == ["far", "mid"], str(_layers("shot_rifle", 80.0)))
	_check("400 м — очень далеко", _layers("shot_rifle", 400.0) == ["distant"], str(_layers("shot_rifle", 400.0)))
	var worst := 0.0
	for d in [2.0, 3.0, 8.0, 15.0, 25.0, 60.0, 100.0, 180.0, 300.0]:
		worst = maxf(worst, absf(_power("shot_rifle", float(d)) - 1.0))
	_check("переход по дистанции — без провала и всплеска громкости (равная мощность)", worst < 0.05, "%.3f" % worst)
	_check("свой выстрел Glock — не чужим пистолетом: своя запись вблизи есть, «свой» общий не берётся",
		not "self" in _layers("wpn_hg_02_shot", 0.5) and "mid" in _layers("wpn_hg_02_shot", 40.0), str(_layers("wpn_hg_02_shot", 0.5)))
	_check("у ствола без своих записей слои — общего набора", "self" in _layers("wpn_ar_04_shot", 0.5), str(_layers("wpn_ar_04_shot", 0.5)))
	_check("звук без слоёв (дверь) — один, как раньше", (Audio.call("_layer_mix", "door", 30.0) as Array).is_empty(), "")
	_check("вид и слой из каталожного вида", Audio.kind_base("shot_rifle@mid") == "shot_rifle" and Audio.kind_layer("shot_rifle@mid") == "mid"
		and Audio.kind_layer("shot_rifle") == "" and Audio.kind_layer("a@b") == "", "")

	# очередь: 12 выстрелов подряд с одного места — хвосты внахлёст, но не больше voices
	var at := cam.global_position + Vector3(0.0, 0.0, -15.0)
	for i in 12:
		Audio.play("shot_rifle", at + Vector3(0.05 * i, 0.0, 0.0))
	var shooters: Array = Audio.get("_shooters")
	var voices := int(Balance.AUDIO_BURST.voices)
	_check("очередь — один стрелок, звучат последние %d выстрелов" % voices,
		shooters.size() == 1 and ((shooters[0] as Dictionary).shots as Array).size() == voices, str(shooters.size()))
	await get_tree().create_timer(float(Balance.AUDIO_BURST.fade_sec) + 0.15).timeout
	var players := 0
	for c in get_children():
		if c is AudioStreamPlayer3D:
			players += 1
	_check("старые хвосты погасли и убраны", players <= voices * 2, "%d плееров" % players)
	Audio.play("shot_rifle", at + Vector3(10.0, 0.0, 0.0))
	_check("другой стрелок в стороне — своя очередь", (Audio.get("_shooters") as Array).size() == 2, "")

	# очередь коротких выстрелов: первый уже доиграл и освобождён, когда очередь перевалила за voices
	# (в игре так и было: приведение освобождённого плеера к типу — ошибка скрипта, игра из редактора вставала)
	var short := _silence(0.05)
	Audio.set_preview({"shot_rifle@self": [short], "shot_rifle@mid": [short], "shot_rifle@far": [short], "shot_rifle@distant": [short]})
	var at2 := cam.global_position + Vector3(0.0, 0.0, 15.0)
	var catcher := ErrorCatcher.new()
	OS.add_logger(catcher)
	Audio.play("shot_rifle", at2)
	await get_tree().create_timer(0.25).timeout
	for i in voices:
		Audio.play("shot_rifle", at2 + Vector3(0.05 * i, 0.0, 0.0))
	OS.remove_logger(catcher)
	var tail_shots := -1
	for s in Audio.get("_shooters") as Array:
		if ((s as Dictionary).pos as Vector3).distance_to(at2) < 2.0:
			tail_shots = ((s as Dictionary).shots as Array).size()
	_check("очередь, где первые выстрелы уже доиграли, — без ошибки, звучат последние %d" % voices,
		catcher.errors == 0 and tail_shots == voices, "ошибок %d, выстрелов %d" % [catcher.errors, tail_shots])

	_check("выстрелы моделей и общих наборов — на шине «Выстрелы», механика — нет",
		Settings.bus_for("wpn_ar_01_shot") == &"Shots" and Settings.bus_for("wpn_sp_01_shot_suppressed") == &"Shots"
		and Settings.bus_for("shot_rifle") == &"Shots" and Settings.bus_for("wpn_ar_01_mechanism") == &"World", "")
	var bus := AudioServer.get_bus_index("Shots")
	_check("у шины «Выстрелы» потолок — очереди не хрипят",
		bus >= 0 and AudioServer.get_bus_effect_count(bus) > 0 and AudioServer.get_bus_effect(bus, 0) is AudioEffectHardLimiter, "")

	var kinds: Array[String] = []
	for e in WeaponDb.weapon_sound_events("wpn_ar_01"):
		kinds.append(String(e.kind))
	_check("у ствола слоты слоёв: свой, средняя, вдали, очень далеко",
		"wpn_ar_01_shot@self" in kinds and "wpn_ar_01_shot@mid" in kinds and "wpn_ar_01_shot@far" in kinds
		and "wpn_ar_01_shot@distant" in kinds, str(kinds.slice(0, 6)))
	var map := WeaponDb.weapon_sound_map("wpn_ar_01")
	var layered := false
	for slot in map:
		layered = layered or String(map[slot]).contains("@")
	_check("карта звуков ствола — без слоёв (их выбирает Audio по расстоянию)", not layered and String(map.shot) == "wpn_ar_01_shot", str(map.shot))

	_check_recipe()
	Audio.set_preview({})
	print("shot_layers_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


## Кандидаты нарезки назначены событиям, которые есть на стенде (каталог + события моделей).
func _check_recipe() -> void:
	if not FileAccess.file_exists(RECIPE):
		_check("карта нарезки есть", false, RECIPE)
		return
	var ids: Dictionary = {}
	var cat: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/sound_catalog.json"))
	for e in cat.sounds:
		ids[String(e.id)] = true
	for e in WeaponDb.weapon_sound_events():
		ids[String(e.id)] = true
	var recipe: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(RECIPE))
	var missing: Array[String] = []
	var total := 0
	for key in recipe.sets:
		for o in (recipe.sets[key] as Dictionary).outputs:
			total += 1
			if not ids.has(String(o.event)) and not String(o.event) in missing:
				missing.append(String(o.event))
	_check("кандидаты нарезки (%d) назначены существующим событиям" % total, total > 0 and missing.is_empty(), str(missing))


func _layers(kind: String, dist: float) -> Array[String]:
	var out: Array[String] = []
	for m in Audio.call("_layer_mix", kind, dist):
		out.append(String(m.layer))
	out.sort()
	return out


func _power(kind: String, dist: float) -> float:
	var p := 0.0
	for m in Audio.call("_layer_mix", kind, dist):
		var g := db_to_linear(float(m.db) - float((Balance.AUDIO_LAYERS[String(m.layer)] as Dictionary).get("db", 0.0)))
		p += g * g
	return p


func _silence(sec: float) -> AudioStreamWAV:
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = 22050
	var data := PackedByteArray()
	data.resize(int(22050 * sec) * 2)
	w.data = data
	return w


func _check(name: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", name, info])
