extends Node3D
## Стенд звуков: каталог всех звуков игры (data/sound_catalog.json) — что звучит записью, что
## синтезом, чего нет совсем; прослушивание в разных местах (улица, магазин, зал, атриум), вдали,
## за стеной, очередью с хвостом места. Справа — новые файлы из папки _sound_try (подхватываются
## сами, раз в пару секунд): назначить звуку, отметить галочкой «в игру», указать источник и
## лицензию — и перенести отмеченные в assets/audio (следующий номер, строка в CREDITS.md).
## Запуск: tools/godot.cmd res://tools/sound_bench.tscn. После переноса — tools/godot.cmd --headless --import.

const CATALOG := "res://data/sound_catalog.json"
const EXTS := ["ogg", "wav", "mp3"]
const CREDITS_HEAD := "## Звук — отобрано на стенде (tools/sound_bench)"
const COL_REC := Color(0.55, 0.85, 0.5)
const COL_SYNTH := Color(0.95, 0.75, 0.35)
const COL_NONE := Color(0.92, 0.45, 0.4)
const COL_DIM := Color(0.62, 0.63, 0.66)
const COL_NEW := Color(0.45, 0.8, 1.0)
const TYPE_NAMES := {"one": "разовый", "loop": "луп", "layer": "слой поверх другого звука"}
const PRIO_NAMES := {1: "база", 2: "важно", 3: "детали"}
const FILTERS := ["все звуки", "без записей", "только синтез", "не подключены в коде", "с новыми файлами",
	"база (важность 1)", "есть записи", "в игре нет"]
const MODES := {"near": "вблизи", "far": "вдали", "wall": "за стеной"}

## Папки (тест подменяет своими): новые файлы, записи игры, файл авторов.
var try_dir: String = ProjectSettings.globalize_path("res://_sound_try")
var assets_dir: String = ProjectSettings.globalize_path("res://assets/audio")
var credits_path: String = ProjectSettings.globalize_path("res://assets/CREDITS.md")

var sounds: Array[Dictionary] = []
var by_id: Dictionary = {}
var cats: Array[String] = []
## Отбор новых файлов: путь относительно try_dir → {use, source, seen, moved}.
var selection: Dictionary = {}
## Новые файлы на последнем поиске (пути относительно try_dir).
var files: Array[String] = []

var _cache: Dictionary = {}
var _asset_cache: Dictionary = {}
var _sig: String = "-"
var _t: float = 0.0
var _current: String = ""
var _space: String = "dry"
var _mode: String = "near"
var _vol_db: float = 0.0
var _burst_id: int = 0
var _players: Array[AudioStreamPlayer] = []
var _rng := RandomNumberGenerator.new()
var _license_re := RegEx.create_from_string("(?i)\\b(nc|nd)\\b|non-?commercial|некоммерч")

var _tree: Tree
var _filter: OptionButton
var _search: LineEdit
var _details: VBoxContainer
var _new_list: VBoxContainer
var _status: Label
var _burst_n: SpinBox
var _rpm: SpinBox


func _ready() -> void:
	_rng.randomize()
	_load_catalog()
	_ensure_try_dir()
	_load_selection()
	_make_buses()
	# слушатель для «как в игре» (Audio.play — объёмный звук в точке мира)
	var cam := Camera3D.new()
	add_child(cam)
	cam.make_current()
	_build_ui()
	rescan(true)


func _process(delta: float) -> void:
	_t += delta
	if _t >= float(Balance.AUDIO_BENCH.rescan_sec):
		_t = 0.0
		rescan()


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and (event as InputEventKey).pressed and (event as InputEventKey).keycode == KEY_ESCAPE:
		stop_all()


# ---------------------------------------------------------------- данные

func _load_catalog() -> void:
	var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for c in d.cats:
		cats.append(String(c))
	for e in d.sounds:
		sounds.append(e as Dictionary)
		by_id[String(e.id)] = e


func _ensure_try_dir() -> void:
	if DirAccess.dir_exists_absolute(try_dir):
		return
	DirAccess.make_dir_recursive_absolute(try_dir)
	# редактор Godot эту папку не импортирует (это сырьё на пробу, не ассеты)
	FileAccess.open(try_dir.path_join(".gdignore"), FileAccess.WRITE).store_string("")
	FileAccess.open(try_dir.path_join("ПРОЧТИ.txt"), FileAccess.WRITE).store_string(
		"Кидай сюда звуки на пробу (ogg, wav, mp3) — стенд tools/sound_bench подхватит их сам.\n"
		+ "В корне — ещё не назначены; в подпапке с id звука из каталога (например shot_rifle) — назначены ему.\n"
		+ "Назначить можно и на стенде. В git эта папка не попадает.\n")


func _sel_path() -> String:
	return try_dir.path_join("_selection.json")


func _load_selection() -> void:
	if FileAccess.file_exists(_sel_path()):
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(_sel_path()))
		if d is Dictionary:
			selection = d


func save_selection() -> void:
	var f := FileAccess.open(_sel_path(), FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(selection, "\t"))


## Отбор файла (заводится при первой встрече: ещё не слушали, не отмечен).
func sel(rel: String) -> Dictionary:
	if not selection.has(rel):
		selection[rel] = {"use": false, "source": "", "seen": false, "moved": ""}
	return selection[rel]


## Новые файлы: в корне try_dir — не назначены, в подпапке <id звука> — назначены ему.
func try_files() -> Array[String]:
	var out: Array[String] = []
	if not DirAccess.dir_exists_absolute(try_dir):
		return out
	for f in DirAccess.get_files_at(try_dir):
		if _is_audio(f):
			out.append(f)
	for d in DirAccess.get_directories_at(try_dir):
		if d.begins_with("_") or d.begins_with("."):
			continue
		for f in DirAccess.get_files_at(try_dir.path_join(d)):
			if _is_audio(f):
				out.append(d + "/" + f)
	out.sort()
	return out


func _is_audio(f: String) -> bool:
	return EXTS.has(f.get_extension().to_lower())


func assigned_id(rel: String) -> String:
	return rel.get_base_dir() if rel.contains("/") else ""


## Записи игры для «группа/префикс_»: файлы «префикс + номер» (как их берёт Audio).
func asset_files(prefix: String) -> Array[String]:
	if _asset_cache.has(prefix):
		return _asset_cache[prefix]
	var out: Array[String] = []
	var parts := prefix.split("/")
	var dir := assets_dir.path_join(parts[0])
	if DirAccess.dir_exists_absolute(dir):
		for f in DirAccess.get_files_at(dir):
			if not _is_audio(f):
				continue
			var stem := f.get_basename()
			if stem.begins_with(parts[1]) and stem.trim_prefix(parts[1]).is_valid_int():
				out.append(dir.path_join(f))
	out.sort()
	_asset_cache[prefix] = out
	return out


## Состояние звука: записей в игре, есть ли синтез, зовёт ли его код, новых файлов (всего,
## непрослушанных, отмеченных).
func status_of(id: String) -> Dictionary:
	var e: Dictionary = by_id[id]
	var kind := String(e.kind)
	var st := {"rec": asset_files(String(e.file)).size(), "wired": kind != "", "synth": false,
		"try": 0, "new": 0, "use": 0, "absent": false}
	if kind.begins_with("loop:"):
		st.synth = true
	elif kind != "":
		st.synth = Audio.has_synth(kind.trim_suffix("@far"))
	# в игре такого звука нет: своей записи нет и код его не зовёт (где-то пока звучит замена — «now»)
	st.absent = kind == "" and int(st.rec) == 0
	for rel in files:
		if assigned_id(rel) != id:
			continue
		st.try += 1
		var s := sel(rel)
		if not bool(s.seen):
			st.new += 1
		if bool(s.use):
			st.use += 1
	return st


## Все варианты звука для прослушивания: записи игры + отмеченные новые файлы.
func streams_of(id: String) -> Array[AudioStream]:
	var out: Array[AudioStream] = []
	for path in asset_files(String(by_id[id].file)):
		var st := load_stream(path)
		if st:
			out.append(st)
	for rel in files:
		if assigned_id(rel) == id and bool(sel(rel).use):
			var st := load_stream(try_dir.path_join(rel))
			if st:
				out.append(st)
	return out


## Файл с диска как есть, без импорта (перечитывается, если файл заменили).
func load_stream(path: String) -> AudioStream:
	var mt := FileAccess.get_modified_time(path)
	if _cache.has(path) and int(_cache[path][0]) == mt:
		return _cache[path][1]
	var st: AudioStream = null
	match path.get_extension().to_lower():
		"ogg":
			st = AudioStreamOggVorbis.load_from_file(path)
		"wav":
			st = AudioStreamWAV.load_from_file(path)
		"mp3":
			st = AudioStreamMP3.load_from_file(path)
	_cache[path] = [mt, st]
	return st


## Искать новые файлы; если что-то изменилось — перестроить списки. Истина — было изменение.
func rescan(force: bool = false) -> bool:
	_ensure_try_dir()
	var found := try_files()
	var parts: PackedStringArray = []
	for rel in found:
		parts.append("%s:%d" % [rel, FileAccess.get_modified_time(try_dir.path_join(rel))])
	var sig := "|".join(parts)
	if sig == _sig and not force:
		return false
	_sig = sig
	files = found
	_asset_cache.clear()
	for rel in files:
		sel(rel)
	for k in selection.keys():
		if not files.has(String(k)):
			selection.erase(k)
	save_selection()
	_refresh_all()
	return true


## Назначить файл звуку (перенос в подпапку с его id; "" — обратно в корень). Новый путь.
func assign(rel: String, id: String) -> String:
	var fname := rel.get_file()
	var to_dir := try_dir if id == "" else try_dir.path_join(id)
	if (try_dir.path_join(rel)).get_base_dir() == to_dir:
		return rel
	DirAccess.make_dir_recursive_absolute(to_dir)
	var dst := to_dir.path_join(fname)
	var n := 2
	while FileAccess.file_exists(dst):
		dst = to_dir.path_join("%s_%d.%s" % [fname.get_basename(), n, fname.get_extension()])
		n += 1
	DirAccess.rename_absolute(try_dir.path_join(rel), dst)
	var new_rel := dst.trim_prefix(try_dir + "/")
	if selection.has(rel):
		selection[new_rel] = selection[rel]
		selection.erase(rel)
	save_selection()
	rescan(true)
	return new_rel


## Следующий свободный номер у префикса в assets/audio.
func next_number(prefix: String) -> int:
	var head := prefix.split("/")[1]
	var mx := 0
	for f in asset_files(prefix):
		mx = maxi(mx, int(f.get_file().get_basename().trim_prefix(head)))
	return mx + 1


## Отмеченные файлы — в assets/audio под следующим номером, источник — строкой в CREDITS.md.
## Без источника, без назначенного звука или с лицензией NC/ND — отказ. Возвращает журнал.
func transfer() -> Array[String]:
	var journal: Array[String] = []
	var rows: Array[String] = []
	for rel in files:
		var s := sel(rel)
		if not bool(s.use) or String(s.moved) != "":
			continue
		var id := assigned_id(rel)
		if not by_id.has(id):
			journal.append("%s — не назначен звук" % rel)
			continue
		var src := String(s.source).strip_edges()
		if src == "":
			journal.append("%s — укажи источник и лицензию" % rel)
			continue
		if _license_re.search(src) != null:
			journal.append("%s — лицензии NC / ND не подходят (AGENTS.md, п. 6)" % rel)
			continue
		var e: Dictionary = by_id[id]
		var parts := String(e.file).split("/")
		var dir := assets_dir.path_join(parts[0])
		DirAccess.make_dir_recursive_absolute(dir)
		var dst := "%s%02d.%s" % [parts[1], next_number(String(e.file)), rel.get_extension().to_lower()]
		if DirAccess.copy_absolute(try_dir.path_join(rel), dir.path_join(dst)) != OK:
			journal.append("%s — не удалось скопировать" % rel)
			continue
		_asset_cache.erase(String(e.file))
		s.moved = parts[0] + "/" + dst
		rows.append("| %s | %s | %s — %s |" % [src, rel.get_file(), s.moved, String(e.name)])
		journal.append("%s → assets/audio/%s" % [rel, s.moved])
	if not rows.is_empty():
		_append_credits(rows)
	save_selection()
	_refresh_all()
	return journal


func _append_credits(rows: Array[String]) -> void:
	var text := FileAccess.get_file_as_string(credits_path) if FileAccess.file_exists(credits_path) else ""
	if not text.contains(CREDITS_HEAD):
		text = text.rstrip("\n") + "\n\n" + CREDITS_HEAD + "\n\n| Источник, лицензия | Исходный файл | Куда — звук |\n|---|---|---|\n"
	var at := text.find(CREDITS_HEAD)
	var next := text.find("\n## ", at + CREDITS_HEAD.length())
	var block := "\n".join(rows) + "\n"
	if next < 0:
		text = text.rstrip("\n") + "\n" + block
	else:
		text = text.substr(0, next).rstrip("\n") + "\n" + block + text.substr(next)
	FileAccess.open(credits_path, FileAccess.WRITE).store_string(text)


# ---------------------------------------------------------------- звук

func _make_buses() -> void:
	for sp in Balance.AUDIO_SPACES:
		var idx := _bus("Bench_" + String(sp))
		var d: Dictionary = Balance.AUDIO_SPACES[sp]
		if d.has("room") and AudioServer.get_bus_effect_count(idx) == 0:
			var r := AudioEffectReverb.new()
			r.room_size = float(d.room)
			r.damping = float(d.damping)
			r.wet = float(d.wet)
			r.dry = 1.0
			r.predelay_msec = float(d.predelay)
			r.predelay_feedback = float(d.feedback)
			AudioServer.add_bus_effect(idx, r)
		AudioServer.set_bus_send(idx, &"Master")
	var b: Dictionary = Balance.AUDIO_BENCH
	_filter_bus("Bench_far", float(b.far_cutoff), float(b.far_db))
	_filter_bus("Bench_wall", Balance.AUDIO_OCCLUDED_CUTOFF, -Balance.AUDIO_OCCLUDED_DB)
	_route()


func _bus(bus_name: String) -> int:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx >= 0:
		return idx
	AudioServer.add_bus()
	idx = AudioServer.bus_count - 1
	AudioServer.set_bus_name(idx, bus_name)
	return idx


func _filter_bus(bus_name: String, cutoff: float, db: float) -> void:
	var idx := _bus(bus_name)
	if AudioServer.get_bus_effect_count(idx) > 0:
		return
	var lp := AudioEffectLowPassFilter.new()
	lp.cutoff_hz = cutoff
	AudioServer.add_bus_effect(idx, lp)
	var amp := AudioEffectAmplify.new()
	amp.volume_db = db
	AudioServer.add_bus_effect(idx, amp)


## «Вдали» и «за стеной» уходят в шину выбранного места — эхо места слышно и там.
func _route() -> void:
	var target := StringName("Bench_" + _space)
	AudioServer.set_bus_send(AudioServer.get_bus_index("Bench_far"), target)
	AudioServer.set_bus_send(AudioServer.get_bus_index("Bench_wall"), target)


func _out_bus() -> StringName:
	match _mode:
		"far":
			return &"Bench_far"
		"wall":
			return &"Bench_wall"
	return StringName("Bench_" + _space)


func set_space(sp: String) -> void:
	_space = sp
	_route()


func set_mode(m: String) -> void:
	_mode = m


## Сыграть запись через выбранное место и слышимость. jitter — разброс тона и громкости, как у
## выстрелов в игре; loop — луп (играет до «Стоп»).
func play_stream(st: AudioStream, jitter: bool = true, loop: bool = false) -> AudioStreamPlayer:
	if st == null:
		return null
	if loop:
		Audio.make_loop(st)
	var b: Dictionary = Balance.AUDIO_BENCH
	var p := AudioStreamPlayer.new()
	p.stream = st
	p.bus = _out_bus()
	p.volume_db = _vol_db + (_rng.randf_range(-float(b.db_jitter), float(b.db_jitter)) if jitter else 0.0)
	p.pitch_scale = 1.0 + (_rng.randf_range(-float(b.pitch_jitter), float(b.pitch_jitter)) if jitter else 0.0)
	add_child(p)
	_players.append(p)
	p.finished.connect(func() -> void:
		_players.erase(p)
		p.queue_free())
	p.play()
	return p


func stop_all() -> void:
	_burst_id += 1
	for p in _players:
		if is_instance_valid(p):
			p.queue_free()
	_players.clear()


## Очередь: по выстрелу на патрон с темпом rpm, варианты вперемешку (подряд один не повторяется),
## в конце — хвост места (если у места есть хвост и для него есть записи).
func play_burst(streams: Array[AudioStream], count: int, rpm: float) -> void:
	if streams.is_empty():
		return
	_burst_id += 1
	var my := _burst_id
	var last := -1
	for i in count:
		if my != _burst_id or not is_inside_tree():
			return
		var k := _rng.randi_range(0, streams.size() - 1)
		if streams.size() > 1 and k == last:
			k = (k + 1) % streams.size()
		last = k
		play_stream(streams[k])
		await get_tree().create_timer(60.0 / maxf(rpm, 1.0)).timeout
	if my == _burst_id:
		play_tail()


## Хвост выстрела выбранного места (каталог: tail_outdoor / tail_room / tail_hall).
func play_tail() -> void:
	var tid := String((Balance.AUDIO_SPACES[_space] as Dictionary).get("tail", ""))
	if not by_id.has(tid):
		return
	var tails := streams_of(tid)
	if not tails.is_empty():
		play_stream(tails[_rng.randi_range(0, tails.size() - 1)])


## Как звучит в игре сейчас: тот же вызов Audio.play (запись, если есть, иначе синтез),
## «дальние» — с 60 м, лупы — тем, что отдаёт звуковая система.
func play_game(id: String) -> bool:
	var kind := String(by_id[id].kind)
	if kind == "":
		return false
	if kind.begins_with("loop:"):
		var st: AudioStream = null
		match kind:
			"loop:rain":
				st = Audio.rain_loop()
			"loop:siren":
				st = Audio.siren_loop()
			"loop:hum":
				st = Audio.hum_loop()
			"loop:ambient":
				st = Audio.ambient_stream()
		play_stream(st, false)
		return st != null
	var far := kind.ends_with("@far")
	var cam := get_viewport().get_camera_3d()
	var at := (cam.global_position if cam else Vector3.ZERO) + Vector3(0.0, 0.0, -60.0 if far else -3.0)
	Audio.play(kind.trim_suffix("@far"), at)
	return true


func _is_loop(id: String) -> bool:
	return by_id.has(id) and String(by_id[id].type) == "loop"


func _is_gun(id: String) -> bool:
	return id.begins_with("shot_")


# ---------------------------------------------------------------- интерфейс

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	var bg := Panel.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.1, 0.105, 0.115)
	bg.add_theme_stylebox_override("panel", sb)
	layer.add_child(bg)
	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	layer.add_child(margin)
	var root := VBoxContainer.new()
	root.add_theme_constant_override("separation", 10)
	margin.add_child(root)

	# верх: место, слышимость, очередь, громкость
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 10)
	root.add_child(top)
	top.add_child(_label("Стенд звуков", 22, Color(1.0, 0.86, 0.6)))
	top.add_child(_label("   Место:", 16, COL_DIM))
	var space := OptionButton.new()
	for sp in Balance.AUDIO_SPACES:
		space.add_item(String((Balance.AUDIO_SPACES[sp] as Dictionary).name))
		space.set_item_metadata(space.item_count - 1, String(sp))
	space.item_selected.connect(func(i: int) -> void: set_space(String(space.get_item_metadata(i))))
	top.add_child(space)
	top.add_child(_label("Слышно:", 16, COL_DIM))
	var mode := OptionButton.new()
	for m in MODES:
		mode.add_item(String(MODES[m]))
		mode.set_item_metadata(mode.item_count - 1, String(m))
	mode.item_selected.connect(func(i: int) -> void: set_mode(String(mode.get_item_metadata(i))))
	top.add_child(mode)
	top.add_child(_label("Очередь:", 16, COL_DIM))
	_burst_n = _spin(2, 30, int(Balance.AUDIO_BENCH.burst))
	top.add_child(_burst_n)
	top.add_child(_label("выстр., темп", 16, COL_DIM))
	_rpm = _spin(30, 1200, int(Balance.AUDIO_BENCH.rpm))
	_rpm.step = 10
	top.add_child(_rpm)
	top.add_child(_label("в мин.   Громкость:", 16, COL_DIM))
	var vol := HSlider.new()
	vol.min_value = -30.0
	vol.max_value = 6.0
	vol.value = 0.0
	vol.custom_minimum_size = Vector2(140, 0)
	vol.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	vol.value_changed.connect(func(v: float) -> void: _vol_db = v)
	top.add_child(vol)
	top.add_child(_button("■ Стоп (Esc)", stop_all))

	# три колонки: каталог | выбранный звук | новые файлы
	var cols := HBoxContainer.new()
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols.add_theme_constant_override("separation", 12)
	root.add_child(cols)

	var left := _column(cols, 1.7)
	var fbar := HBoxContainer.new()
	left.add_child(fbar)
	_filter = OptionButton.new()
	for f in FILTERS:
		_filter.add_item(f)
	_filter.item_selected.connect(func(_i: int) -> void: _refresh_tree())
	fbar.add_child(_filter)
	_search = LineEdit.new()
	_search.placeholder_text = "поиск: название, id, файл"
	_search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_search.text_changed.connect(func(_t2: String) -> void: _refresh_tree())
	fbar.add_child(_search)
	_tree = Tree.new()
	_tree.columns = 3
	_tree.hide_root = true
	_tree.column_titles_visible = true
	_tree.set_column_title(0, "Звук")
	_tree.set_column_title(1, "Сейчас")
	_tree.set_column_title(2, "Важн.")
	_tree.set_column_expand(0, true)
	_tree.set_column_expand(1, false)
	_tree.set_column_custom_minimum_width(1, 200)
	_tree.set_column_expand(2, false)
	_tree.set_column_custom_minimum_width(2, 60)
	_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_tree.item_selected.connect(_on_tree_selected)
	left.add_child(_tree)

	var mid := _column(cols, 1.0)
	var ms := ScrollContainer.new()
	ms.size_flags_vertical = Control.SIZE_EXPAND_FILL
	ms.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	mid.add_child(ms)
	_details = VBoxContainer.new()
	_details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_details.add_theme_constant_override("separation", 6)
	ms.add_child(_details)

	var right := _column(cols, 1.25)
	right.add_child(_label("Новые звуки — папка _sound_try", 18, Color(1.0, 0.86, 0.6)))
	var rbar := HBoxContainer.new()
	right.add_child(rbar)
	rbar.add_child(_button("Открыть папку", func() -> void: OS.shell_open(try_dir)))
	rbar.add_child(_button("Найти новые", func() -> void: rescan(true)))
	rbar.add_child(_button("Перенести отмеченные в игру", _on_transfer))
	var rs := ScrollContainer.new()
	rs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	rs.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	right.add_child(rs)
	_new_list = VBoxContainer.new()
	_new_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rs.add_child(_new_list)

	_status = _label("Кидай файлы в %s — появятся справа сами. Esc — остановить звук." % try_dir, 15, COL_DIM)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(_status)


func _on_transfer() -> void:
	var journal := transfer()
	if journal.is_empty():
		_status.text = "Перенос: нечего переносить — отметь файлы галочкой «в игру»."
	else:
		_status.text = "Перенос:\n" + "\n".join(journal) + "\nДальше: tools/godot.cmd --headless --import (или открыть редактор)."


func _column(parent: Control, ratio: float) -> VBoxContainer:
	var panel := PanelContainer.new()
	panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	panel.size_flags_stretch_ratio = ratio
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.14, 0.145, 0.16)
	sb.set_content_margin_all(10)
	panel.add_theme_stylebox_override("panel", sb)
	parent.add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 6)
	panel.add_child(v)
	return v


func _label(text: String, size: int, color: Color) -> Label:
	var l := Label.new()
	l.text = text
	l.add_theme_font_size_override("font_size", size)
	l.add_theme_color_override("font_color", color)
	return l


func _button(text: String, cb: Callable) -> Button:
	var b := Button.new()
	b.text = text
	b.pressed.connect(cb)
	return b


func _spin(lo: int, hi: int, v: int) -> SpinBox:
	var s := SpinBox.new()
	s.min_value = lo
	s.max_value = hi
	s.value = v
	return s


func _refresh_all() -> void:
	if _tree == null:
		return
	_refresh_tree()
	_refresh_details()
	_refresh_new_list()


func _status_text(st: Dictionary) -> String:
	var t := "записей: %d" % int(st.rec) if int(st.rec) > 0 else ("синтез" if bool(st.synth) else "нет своего")
	if bool(st.absent):
		t = "в игре нет"
	elif not bool(st.wired):
		t += " · не в коде"
	if int(st.try) > 0:
		t += " · новых %d" % int(st.try)
	return t


func _status_color(st: Dictionary) -> Color:
	if int(st.new) > 0:
		return COL_NEW
	if int(st.rec) > 0:
		return COL_REC
	return COL_SYNTH if bool(st.synth) else COL_NONE


func _passes(e: Dictionary, st: Dictionary, q: String) -> bool:
	if q != "" and not (String(e.name).to_lower().contains(q) or String(e.id).contains(q) or String(e.file).contains(q)):
		return false
	match _filter.selected:
		1:
			return int(st.rec) == 0
		2:
			return int(st.rec) == 0 and bool(st.synth)
		3:
			return not bool(st.wired)
		4:
			return int(st.try) > 0
		5:
			return int(e.prio) == 1
		6:
			return int(st.rec) > 0
		7:
			return bool(st.absent)
	return true


func _refresh_tree() -> void:
	_tree.clear()
	var root := _tree.create_item()
	var q := _search.text.strip_edges().to_lower()
	for c in cats:
		var ci: TreeItem = null
		var total := 0
		var rec := 0
		for e in sounds:
			if String(e.cat) != c:
				continue
			total += 1
			var st := status_of(String(e.id))
			if int(st.rec) > 0:
				rec += 1
			if not _passes(e, st, q):
				continue
			if ci == null:
				ci = _tree.create_item(root)
				for col in 3:
					ci.set_selectable(col, false)
				ci.set_custom_color(0, Color(1.0, 0.86, 0.6))
			var it := _tree.create_item(ci)
			it.set_text(0, String(e.name))
			it.set_metadata(0, String(e.id))
			it.set_tooltip_text(0, "%s\n%s" % [String(e.when), String(e.id)])
			it.set_text(1, _status_text(st))
			it.set_custom_color(1, _status_color(st))
			it.set_text(2, "●".repeat(4 - int(e.prio)))
			if String(e.id) == _current:
				it.select(0)
		if ci:
			ci.set_text(0, "%s — с записями %d из %d" % [c, rec, total])


func _on_tree_selected() -> void:
	var it := _tree.get_selected()
	if it == null or it.get_metadata(0) == null:
		return
	_current = String(it.get_metadata(0))
	_refresh_details()


func _refresh_details() -> void:
	for c in _details.get_children():
		c.queue_free()
	if not by_id.has(_current):
		_details.add_child(_label("Выбери звук слева.\n\nЦвет: зелёный — есть записи, жёлтый — только синтез, "
			+ "красный — своего звука нет (в игре молчит или звучит чужим — см. «Сейчас в игре»), голубой — есть непрослушанные новые файлы.\n«Не в коде» — игра этот звук "
			+ "ещё не зовёт: записи можно готовить заранее.", 16, COL_DIM))
		return
	var e: Dictionary = by_id[_current]
	var st := status_of(_current)
	var title := _label(String(e.name), 20, Color(1.0, 0.86, 0.6))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_details.add_child(title)
	var info := _label("Когда: %s\nФайлы в игре: assets/audio/%sNN.ogg (%s)\nСейчас в игре: %s%s\nТип: %s · вариантов нужно: %d · важность: %s" % [
		String(e.when), String(e.file), _status_text(st), String(e.now),
		"" if String(e.kind) == "" else " (вид «%s»)" % String(e.kind),
		String(TYPE_NAMES.get(String(e.type), String(e.type))), int(e.variants), String(PRIO_NAMES.get(int(e.prio), ""))],
		15, Color(0.85, 0.86, 0.88))
	info.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_details.add_child(info)
	var bar := HBoxContainer.new()
	_details.add_child(bar)
	var id := _current
	bar.add_child(_button("▶ как в игре", func() -> void:
		if not play_game(id):
			_status.text = "Игра этот звук пока не зовёт — слушай варианты ниже."))
	bar.add_child(_button("▶ случайный вариант", func() -> void:
		var all := streams_of(id)
		if all.is_empty():
			_status.text = "Нет записей и отмеченных новых файлов."
		else:
			play_stream(all[_rng.randi_range(0, all.size() - 1)], true, _is_loop(id))
			if _is_gun(id):
				play_tail()))
	if _is_gun(id):
		bar.add_child(_button("▶▶ очередь", func() -> void: play_burst(streams_of(id), int(_burst_n.value), _rpm.value)))
	_details.add_child(_label("Записи в игре (%d):" % int(st.rec), 16, COL_REC))
	for path in asset_files(String(e.file)):
		var row := HBoxContainer.new()
		var p := path
		row.add_child(_button("▶", func() -> void:
			play_stream(load_stream(p), true, _is_loop(id))
			if _is_gun(id):
				play_tail()))
		row.add_child(_label(path.get_file(), 15, Color(0.85, 0.86, 0.88)))
		_details.add_child(row)
	var mine: Array[String] = []
	for rel in files:
		if assigned_id(rel) == id:
			mine.append(rel)
	_details.add_child(_label("Новые для этого звука (%d) — галочка «в игру» добавляет их и к «случайному», и к очереди:" % mine.size(), 16, COL_NEW))
	for rel in mine:
		_details.add_child(_file_row(rel, false))


func _refresh_new_list() -> void:
	for c in _new_list.get_children():
		c.queue_free()
	if files.is_empty():
		_new_list.add_child(_label("Пока пусто. Кидай файлы (ogg, wav, mp3) в папку — в корень или в подпапку с id звука.", 15, COL_DIM))
		return
	var loose: Array[String] = []
	var groups: Dictionary = {}
	for rel in files:
		var id := assigned_id(rel)
		if id == "":
			loose.append(rel)
		else:
			if not groups.has(id):
				groups[id] = []
			(groups[id] as Array).append(rel)
	if not loose.is_empty():
		_new_list.add_child(_label("Не назначены (%d):" % loose.size(), 16, COL_SYNTH))
		for rel in loose:
			_new_list.add_child(_file_row(rel, true))
	for id in groups:
		var nm := String(by_id[id].name) if by_id.has(id) else "%s — нет такого звука в каталоге" % String(id)
		_new_list.add_child(_label(nm, 16, Color(1.0, 0.86, 0.6)))
		for rel in groups[id]:
			_new_list.add_child(_file_row(String(rel), true))


## Строка нового файла: ● непрослушан, ▶, ▶▶ (очередь из одного этого файла), галочка «в игру»,
## имя, кому назначен, источник и лицензия (для CREDITS), где уже лежит в игре.
func _file_row(rel: String, show_assign: bool) -> VBoxContainer:
	var s := sel(rel)
	var id := assigned_id(rel)
	var box := VBoxContainer.new()
	var row := HBoxContainer.new()
	box.add_child(row)
	var dot := _label("●" if not bool(s.seen) else "  ", 16, COL_NEW)
	dot.tooltip_text = "новый — ещё не слушал"
	row.add_child(dot)
	var path := try_dir.path_join(rel)
	row.add_child(_button("▶", func() -> void:
		s.seen = true
		dot.text = "  "
		save_selection()
		play_stream(load_stream(path), true, _is_loop(id))
		if _is_gun(id):
			play_tail()))
	if _is_gun(id):
		row.add_child(_button("▶▶", func() -> void:
			s.seen = true
			dot.text = "  "
			save_selection()
			var one: Array[AudioStream] = [load_stream(path)]
			play_burst(one, int(_burst_n.value), _rpm.value)))
	var use := CheckBox.new()
	use.text = "в игру"
	use.button_pressed = bool(s.use)
	use.toggled.connect(func(v: bool) -> void:
		s.use = v
		s.seen = true
		dot.text = "  "
		save_selection()
		_refresh_tree())
	row.add_child(use)
	var fname := _label(rel.get_file(), 15, Color(0.85, 0.86, 0.88))
	fname.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fname.clip_text = true
	fname.tooltip_text = rel
	row.add_child(fname)
	var row2 := HBoxContainer.new()
	box.add_child(row2)
	if show_assign:
		var pick := OptionButton.new()
		pick.add_item("— кому? —")
		pick.set_item_metadata(0, "")
		for e in sounds:
			pick.add_item("%s · %s" % [String(e.cat), String(e.name)])
			pick.set_item_metadata(pick.item_count - 1, String(e.id))
			if String(e.id) == id:
				pick.select(pick.item_count - 1)
		pick.custom_minimum_size = Vector2(260, 0)
		pick.clip_text = true
		pick.item_selected.connect(func(i: int) -> void:
			assign(rel, String(pick.get_item_metadata(i))))
		row2.add_child(pick)
	var src := LineEdit.new()
	src.placeholder_text = "источник, лицензия (freesound: автор, CC0)"
	src.text = String(s.source)
	src.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	src.text_changed.connect(func(t: String) -> void: s.source = t)
	src.focus_exited.connect(save_selection)
	src.text_submitted.connect(func(_t: String) -> void: save_selection())
	row2.add_child(src)
	if String(s.moved) != "":
		box.add_child(_label("   ✓ в игре: assets/audio/%s" % String(s.moved), 14, COL_REC))
	return box
