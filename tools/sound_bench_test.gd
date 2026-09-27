extends Node
## Стенд звуков (tools/sound_bench): каталог покрывает все звуки, которые зовёт игра, и все её
## папки записей; новые файлы подхватываются, назначаются звуку, отмечаются, отбор сохраняется;
## перенос — следующий номер у префикса, строка в CREDITS, отказ без источника, без разрешённой
## лицензии и с NC; импортированную запись можно обратимо исключить; модели пистолетов имеют свои
## наборы с общим запасным; звук играет (одиночный, «как в игре», луп, очередь с хвостом). Папки — свои в user://.

const ALIASES := {"shot_ai": "shot_pistol", "step": "step_stone", "step_ai": "step_stone",
	"step_run": "step_stone_run", "reload": "reload_pistol"}

var _fails: int = 0
var _root: String = ProjectSettings.globalize_path("user://sound_bench_test")


func _ready() -> void:
	_run.call_deferred()


func _check(what: String, ok: bool, detail: String = "") -> void:
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, detail])
	if not ok:
		_fails += 1


func _wav(path: String) -> void:
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = 22050
	var n := 4410
	var data := PackedByteArray()
	data.resize(n * 2)
	for i in n:
		data.encode_s16(i * 2, int(sin(float(i) * 0.3) * 8000.0 * (1.0 - float(i) / n)))
	w.data = data
	w.save_to_wav(path)


func _rm(dir: String) -> void:
	if not DirAccess.dir_exists_absolute(dir):
		return
	for d in DirAccess.get_directories_at(dir):
		_rm(dir.path_join(d))
	for f in DirAccess.get_files_at(dir):
		DirAccess.remove_absolute(dir.path_join(f))
	DirAccess.remove_absolute(dir)


func _run() -> void:
	_rm(_root)
	DirAccess.make_dir_recursive_absolute(_root.path_join("assets/guns"))
	_wav(_root.path_join("assets/guns/carbine_01.wav"))
	_wav(_root.path_join("assets/guns/carbine_07.wav"))
	_wav(_root.path_join("assets/guns/pistol_01.wav"))
	_wav(_root.path_join("assets/guns/pistol_02.wav"))
	FileAccess.open(_root.path_join("CREDITS.md"), FileAccess.WRITE).store_string("# Авторы\n\n## Модели\n\n| a | b |\n")
	var bench := (load("res://tools/sound_bench.tscn") as PackedScene).instantiate()
	bench.set("try_dir", _root.path_join("try"))
	bench.set("assets_dir", _root.path_join("assets"))
	bench.set("credits_path", _root.path_join("CREDITS.md"))
	bench.set("active_selection_path", _root.path_join("sound_active.json"))
	bench.set("catalog_doc_script", "")
	add_child(bench)
	await get_tree().process_frame

	# --- каталог
	var sounds: Array[Dictionary] = bench.get("sounds")
	var cats: Array[String] = bench.get("cats")
	var ids := {}
	var files := {}
	var bad: Array[String] = []
	var re := RegEx.create_from_string("^[a-z]+/[a-z0-9_]+_$")
	for e in sounds:
		if ids.has(e.id) or files.has(e.file) or re.search(String(e.file)) == null or not cats.has(String(e.cat)) \
				or not ["one", "loop", "layer"].has(String(e.type)) or not [1, 2, 3].has(int(e.prio)) or int(e.variants) < 1:
			bad.append(String(e.id))
		ids[e.id] = true
		files[e.file] = true
	_check("каталог: %d звуков в %d разделах, id и файлы уникальны, поля в порядке" % [sounds.size(), cats.size()],
		sounds.size() >= 150 and bad.is_empty(), str(bad))
	var kinds := {}
	for e in sounds:
		kinds[String(e.kind)] = true
	var miss: Array[String] = []
	for k in Audio.KINDS:
		var want := String(ALIASES.get(k, k))
		if not kinds.has(want) and not kinds.has(want + "@far"):
			miss.append(String(k))
	_check("каталог: есть каждый вид звука, который зовёт игра (Audio.KINDS)", miss.is_empty(), str(miss))
	var prefixes: Array[String] = []
	for k in Audio.SAMPLES:
		for p in Audio.SAMPLES[k]:
			prefixes.append(String(p))
	for d in [Audio.FAR, Audio.OWN, Audio.LOOPS]:
		for k in d:
			prefixes.append(String(d[k]))
	var nofile: Array[String] = []
	for p in prefixes:
		if not files.has(p):
			nofile.append(p)
	_check("каталог: есть каждая папка записей игры (SAMPLES, FAR, OWN, LOOPS)", nofile.is_empty(), str(nofile))
	var death_prefixes: Array = (Audio.get("_catalog_prefixes") as Dictionary).get("death", [])
	_check("один игровой вызов собирает записи из нескольких папок каталога",
		death_prefixes.has("voice/rattle_groan_") and death_prefixes.has("voice/rattle_gurgle_"), str(death_prefixes))
	var noloop: Array[String] = []
	for k in Audio.LOOPS:
		if not kinds.has("loop:" + String(k)):
			noloop.append(String(k))
	_check("каталог: фоновые лупы игры", noloop.is_empty(), str(noloop))
	var weapons: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/weapons.json"))
	var pistol_sounds: Array[String] = []
	for id in ["wpn_hg_01", "wpn_hg_02", "wpn_hg_03", "wpn_hg_04"]:
		pistol_sounds.append(String(weapons.weapons[id].weapon.sound))
	_check("четыре пистолета назначены четырём отдельным звуковым наборам",
		pistol_sounds == ["shot_hg_01", "shot_hg_02", "shot_hg_03", "shot_hg_04"], str(pistol_sounds))
	var pistol_model: Dictionary = bench.call("status_of", "shot_hg_01")
	var pistol_streams: Array[AudioStream] = bench.call("streams_of", "shot_hg_01")
	_check("пока своих записей нет, модель пистолета использует общий запасной набор",
		int(pistol_model.rec) == 0 and int(pistol_model.fallback_rec) == 2 and pistol_streams.size() == 2,
		str(pistol_model))
	_wav(_root.path_join("assets/guns/hg01_01.wav"))
	(bench.get("_asset_cache") as Dictionary).clear()
	pistol_model = bench.call("status_of", "shot_hg_01")
	pistol_streams = bench.call("streams_of", "shot_hg_01")
	_check("первая своя запись заменяет общий набор только у выбранной модели",
		int(pistol_model.rec) == 1 and pistol_streams.size() == 1
		and (bench.call("streams_of", "shot_hg_02") as Array).size() == 2, str(pistol_model))

	# --- действующие записи можно убрать из игры без удаления файла
	var carbine_01 := _root.path_join("assets/guns/carbine_01.wav")
	bench.call("set_asset_enabled", carbine_01, false)
	var active_state: Dictionary = bench.call("status_of", "shot_rifle")
	var active_file: Variant = JSON.parse_string(FileAccess.get_file_as_string(_root.path_join("sound_active.json")))
	_check("запись исключается из случайного выбора, но файл остаётся на месте",
		int(active_state.rec) == 1 and int(active_state.disabled) == 1
		and (bench.call("streams_of", "shot_rifle") as Array).size() == 1
		and FileAccess.file_exists(carbine_01), str(active_state))
	_check("исключение сохраняется в явном файле проекта", active_file is Dictionary
		and (active_file as Dictionary).disabled.has("guns/carbine_01.wav"), str(active_file))
	bench.call("set_asset_enabled", carbine_01, true)
	active_state = bench.call("status_of", "shot_rifle")
	_check("галочка возвращает запись в игру", int(active_state.rec) == 2 and int(active_state.disabled) == 0,
		str(active_state))

	# --- новые файлы
	var try_dir := _root.path_join("try")
	_check("папка для проб создана, редактор её не импортирует", FileAccess.file_exists(try_dir.path_join(".gdignore")))
	DirAccess.make_dir_recursive_absolute(try_dir.path_join("shot_rifle"))
	DirAccess.make_dir_recursive_absolute(try_dir.path_join("batch/from_oleg"))
	for f in ["a.wav", "c.wav", "d.wav", "batch/from_oleg/e.wav", "batch/from_oleg/f.wav", "shot_rifle/b.wav"]:
		_wav(try_dir.path_join(f))
	bench.call("rescan", true)
	var found: Array[String] = bench.get("files")
	_check("новые файлы подхвачены: в корне, папке звука и произвольном дереве генератора",
		found.has("a.wav") and found.has("shot_rifle/b.wav") and found.has("batch/from_oleg/e.wav")
		and String(bench.call("assigned_id", "batch/from_oleg/e.wav")) == "", str(found))
	var nested: Array[String] = bench.call("inbox_files", "dir:batch/from_oleg")
	var one_file: Array[String] = bench.call("inbox_files", "file:batch/from_oleg/e.wav")
	_check("входящие показываются деревом: папка даёт только своё поддерево, файл — одну карточку",
		nested == ["batch/from_oleg/e.wav", "batch/from_oleg/f.wav"] and one_file == ["batch/from_oleg/e.wav"],
		str(nested))
	var st: Dictionary = bench.call("status_of", "shot_rifle")
	_check("у звука — записи игры и новый непрослушанный файл", int(st.rec) == 2 and int(st.try) == 1 and int(st.new) == 1, str(st))
	var loose_a: Dictionary = bench.call("sel", "a.wav")
	loose_a.use = true
	var a: String = bench.call("assign", "a.wav", "flyby")
	bench.call("assign", "c.wav", "flyby")
	bench.call("assign", "d.wav", "flyby")
	var batch: Array[String] = ["batch/from_oleg/e.wav", "batch/from_oleg/f.wav"]
	bench.call("assign_many", batch, "flyby")
	_check("назначить звуку — исходная папка и имя не меняются", a == "a.wav" and FileAccess.file_exists(try_dir.path_join(a))
		and String(bench.call("assigned_id", a)) == "flyby", a)
	_check("после назначения нужно одобрить файл именно для нового события", not bool((bench.call("sel", a) as Dictionary).use), "")
	_check("целая папка вариантов назначается разом без разрушения дерева",
		FileAccess.file_exists(try_dir.path_join("batch/from_oleg/e.wav")) and FileAccess.file_exists(try_dir.path_join("batch/from_oleg/f.wav"))
		and String(bench.call("assigned_id", "batch/from_oleg/e.wav")) == "flyby", "")
	var sb: Dictionary = bench.call("sel", "shot_rifle/b.wav")
	sb.use = true
	sb.source = "freesound: тест, CC0"
	var sa: Dictionary = bench.call("sel", "a.wav")
	sa.use = true
	sa.source = "OpenGameArt: автор, CC-BY 4.0"
	var sc: Dictionary = bench.call("sel", "c.wav")
	sc.use = true
	var sd: Dictionary = bench.call("sel", "d.wav")
	sd.use = true
	sd.source = "freesound: кто-то, CC BY-NC 4.0"
	var se: Dictionary = bench.call("sel", "batch/from_oleg/e.wav")
	se.use = true
	se.source = "неизвестный сайт"
	bench.call("save_selection")
	var streams: Array[AudioStream] = bench.call("streams_of", "shot_rifle")
	_check("отмеченный новый файл слышен вместе с записями игры", streams.size() == 3, str(streams.size()))

	# --- перенос
	var journal: Array[String] = bench.call("transfer")
	var credits := FileAccess.get_file_as_string(_root.path_join("CREDITS.md"))
	_check("перенос: следующий номер у префикса (01, 07 → 08)", FileAccess.file_exists(_root.path_join("assets/guns/carbine_08.wav")), str(journal))
	_check("перенос: новый префикс — с 01 в своей папке", FileAccess.file_exists(_root.path_join("assets/bullets/flyby_01.wav")))
	_check("перенос: без источника — отказ", "\n".join(journal).contains("c.wav — укажи источник"), "")
	_check("перенос: лицензия NC — отказ", "\n".join(journal).contains("d.wav — лицензии NC") and not FileAccess.file_exists(_root.path_join("assets/bullets/flyby_02.wav")), "")
	_check("перенос: неизвестная лицензия — отказ", "\n".join(journal).contains("e.wav — укажи CC0")
		and not FileAccess.file_exists(_root.path_join("assets/bullets/flyby_02.wav")), "")
	_check("CREDITS: свой раздел, строки источников, прежние разделы целы",
		credits.contains("## Звук — отобрано на стенде") and credits.contains("freesound: тест, CC0") and credits.contains("CC-BY 4.0")
		and credits.contains("## Модели") and not credits.contains("BY-NC"), "")
	bench.call("transfer")
	_check("второй перенос не копирует то же ещё раз", not FileAccess.file_exists(_root.path_join("assets/guns/carbine_09.wav")))
	var saved: Variant = JSON.parse_string(FileAccess.get_file_as_string(try_dir.path_join("_selection.json")))
	_check("отбор сохранён на диск: галочка, источник, куда перенесён", saved is Dictionary
		and bool((saved as Dictionary)["shot_rifle/b.wav"].use) and String((saved as Dictionary)["shot_rifle/b.wav"].moved) == "guns/carbine_08.wav", "")
	(bench.get("_bulk_source") as LineEdit).text = "сгенерировано Олегом · собственный звук"
	bench.call("_apply_bulk_source")
	_check("общий источник заполняет только пустые поля у всей партии",
		String((bench.call("sel", "batch/from_oleg/f.wav") as Dictionary).source).contains("собственный")
		and String((bench.call("sel", "shot_rifle/b.wav") as Dictionary).source) == "freesound: тест, CC0", "")
	st = bench.call("status_of", "shot_rifle")
	_check("после переноса у звука 3 записи", int(st.rec) == 3, str(st))

	# --- прослушивание
	var p: AudioStreamPlayer = bench.call("play_stream", bench.call("load_stream", try_dir.path_join("shot_rifle/b.wav")))
	_check("новый файл играет через шину места", p != null and p.playing and String(p.bus).begins_with("Bench_"), str(p.bus) if p else "")
	bench.call("set_mode", "wall")
	p = bench.call("play_stream", bench.call("load_stream", try_dir.path_join("shot_rifle/b.wav")))
	_check("«за стеной» — своя шина со срезом верхов", p != null and p.bus == &"Bench_wall", "")
	bench.call("set_space", "hall")
	_check("шина «за стеной» уходит в эхо выбранного места", AudioServer.get_bus_send(AudioServer.get_bus_index("Bench_wall")) == &"Bench_hall", "")
	_check("«как в игре» — зовёт звуковую систему; незвучащий в игре — нет",
		bool(bench.call("play_game", "shot_rifle")) and bool(bench.call("play_game", "shot_rifle_far"))
		and bool(bench.call("play_game", "flyby")) and not bool(bench.call("play_game", "ricochet")), "")
	_check("«как в игре» для лупа (дождь)", bool(bench.call("play_game", "rain_out")), "")
	await bench.call("play_burst", streams, 3, 1200.0)
	_check("очередь отыграла", true, "")
	bench.call("stop_all")
	await get_tree().process_frame
	_check("«Стоп» глушит всё", (bench.get("_players") as Array).is_empty(), "")

	# --- окончательное удаление: файл, импорт, отбор, CREDITS и исключение
	var imported := _root.path_join("assets/guns/carbine_08.wav")
	FileAccess.open(imported + ".import", FileAccess.WRITE).store_string("тестовый импорт")
	bench.call("set_asset_enabled", imported, false)
	_check("удалить запись проекта — операция выполнена", bool(bench.call("delete_asset_permanently", "guns/carbine_08.wav")), "")
	var after_delete_credits := FileAccess.get_file_as_string(_root.path_join("CREDITS.md"))
	var after_delete_active: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(_root.path_join("sound_active.json")))
	_check("удалить запись проекта — нет аудио, .import, входящего исходника и строки CREDITS",
		not FileAccess.file_exists(imported) and not FileAccess.file_exists(imported + ".import")
		and not FileAccess.file_exists(try_dir.path_join("shot_rifle/b.wav"))
		and not (bench.get("selection") as Dictionary).has("shot_rifle/b.wav")
		and not after_delete_credits.contains("guns/carbine_08.wav"), "")
	_check("удалить запись проекта — очищено исключение из sound_active.json",
		not (after_delete_active.get("disabled", []) as Array).has("guns/carbine_08.wav"), str(after_delete_active))
	_check("удалить входящий навсегда — нет файла и данных отбора",
		bool(bench.call("delete_incoming_permanently", "c.wav"))
		and not FileAccess.file_exists(try_dir.path_join("c.wav"))
		and not (bench.get("selection") as Dictionary).has("c.wav"), "")
	_check("удалить уже перенесённый входящий — удалена и готовая копия",
		bool(bench.call("delete_incoming_permanently", "a.wav"))
		and not FileAccess.file_exists(try_dir.path_join("a.wav"))
		and not FileAccess.file_exists(_root.path_join("assets/bullets/flyby_01.wav"))
		and not FileAccess.get_file_as_string(_root.path_join("CREDITS.md")).contains("bullets/flyby_01.wav"), "")
	_check("удаление не принимает путь за пределами звуковых папок",
		not bool(bench.call("delete_asset_permanently", "../CREDITS.md"))
		and FileAccess.file_exists(_root.path_join("CREDITS.md")), "")

	# --- совместимость: старое назначение возвращается в исходную папку без потери цели
	DirAccess.make_dir_recursive_absolute(try_dir.path_join("flyby"))
	_wav(try_dir.path_join("flyby/legacy.wav"))
	(bench.get("selection") as Dictionary)["flyby/legacy.wav"] = {
		"use": false, "source": "", "seen": true, "moved": "", "origin": "old_batch/legacy.wav"}
	bench.call("_restore_legacy_paths")
	_check("старое назначение восстановило исходное дерево, а цель сохранилась отдельно",
		FileAccess.file_exists(try_dir.path_join("old_batch/legacy.wav"))
		and not FileAccess.file_exists(try_dir.path_join("flyby/legacy.wav"))
		and String(bench.call("assigned_id", "old_batch/legacy.wav")) == "flyby", "")

	# --- список слева
	var tree: Tree = bench.get("_tree")
	var top := tree.get_root().get_children()
	_check("список: все разделы каталога", top.size() == cats.size(), "%d из %d" % [top.size(), cats.size()])
	(bench.get("_filter") as OptionButton).select(3)
	bench.call("_refresh_tree")
	var wired := 0
	for c in tree.get_root().get_children():
		for it in c.get_children():
			if String((bench.get("by_id") as Dictionary)[String(it.get_metadata(0))].kind) != "":
				wired += 1
	_check("фильтр «не подключены в коде» — только такие", wired == 0 and tree.get_root().get_child_count() > 0, "")
	(bench.get("_filter") as OptionButton).select(7)
	bench.call("_refresh_tree")
	var absent := 0
	var other := 0
	for c in tree.get_root().get_children():
		for it in c.get_children():
			if bool((bench.call("status_of", String(it.get_metadata(0))) as Dictionary).absent):
				absent += 1
			else:
				other += 1
	_check("фильтр «в игре нет»: гильзы, мусор, далёкие звуки…", absent >= 80 and other == 0
		and bool((bench.call("status_of", "ricochet") as Dictionary).absent) and bool((bench.call("status_of", "trash_wind") as Dictionary).absent)
		and not bool((bench.call("status_of", "shot_rifle") as Dictionary).absent), "%d звуков" % absent)

	_rm(_root)
	print("sound_bench_test: провалено %d" % _fails)
	get_tree().quit()
