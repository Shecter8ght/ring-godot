extends Node3D
## Стенд звуков: одна страница со сворачиваемыми разделами — оружие (классы → карточки стволов,
## общие наборы и обращение), дальше разделы каталога (data/sound_catalog.json) → подгруппы →
## карточки событий: что звучит записью, что синтезом или чужим набором, где тишина. Справа —
## выбранное событие: прослушать (улица, магазин, зал, атриум; вдали, за стеной, очередью), свои
## записи, назначенные из других наборов (одна запись — сколько угодно событий), системный звук
## (запасной набор, синтез) — снять или вернуть; назначения — data/sound_active.json. Вкладка
## «Входящие» — новые файлы из _sound_try: назначить событию, одобрить, указать источник и
## лицензию — и перенести в assets/audio (следующий номер, строка в CREDITS.md).
## Запуск: tools/godot.cmd res://tools/sound_bench.tscn. После переноса — tools/godot.cmd --headless --import.

const CATALOG := "res://data/sound_catalog.json"
const ACTIVE_SELECTION := "res://data/sound_active.json"
const EXTS := ["ogg", "wav", "mp3"]
const CREDITS_HEAD := "## Звук — отобрано на стенде (tools/sound_bench)"
const COL_REC := Color(0.55, 0.85, 0.5)
const COL_SYNTH := Color(0.95, 0.75, 0.35)
const COL_NONE := Color(0.92, 0.45, 0.4)
const COL_DIM := Color(0.62, 0.63, 0.66)
const COL_NEW := Color(0.45, 0.8, 1.0)
## Порядок классов на вкладке оружия.
const CLASS_ORDER := ["PISTOL", "SMG", "PDW", "ASSAULT_RIFLE", "CARBINE", "BATTLE_RIFLE", "DMR", "SNIPER", "SPECIAL", "LMG", "SHOTGUN"]
const TYPE_NAMES := {"one": "разовый", "loop": "луп", "layer": "слой поверх другого звука"}
const PRIO_NAMES := {1: "база", 2: "важно", 3: "детали"}
const FILTERS := ["все звуки", "без записей", "только синтез", "не подключены в коде", "с новыми файлами",
	"база (важность 1)", "есть записи", "в игре нет", "назначено или снято на стенде"]
const LEGEND := ("▶ звучат свои или назначенные записи · ▷ звучит запасной набор другого события · ≈ синтез · "
	+ "○ тишина · ◇ в коде ещё не вызывается · голубым — новые файлы во входящих. Щелчок по карточке — "
	+ "событие справа: прослушать, назначить запись из проекта, снять системный звук.")
## Заголовки классов стволов на странице (во множественном числе).
const CLASS_TITLES := {"PISTOL": "Пистолеты", "SMG": "Пистолеты-пулемёты", "PDW": "PDW", "ASSAULT_RIFLE": "Автоматы",
	"CARBINE": "Карабины", "BATTLE_RIFLE": "Боевые винтовки", "DMR": "Марксманские винтовки", "SNIPER": "Снайперские винтовки",
	"SPECIAL": "Специальное", "LMG": "Пулемёты", "SHOTGUN": "Ружья"}
## Раздел событий семейств (WeaponDb.family_sound_events).
const FAMILY_CAT := "Оружие — семейства"
## Разделы каталога, которые показываются внутри «Оружия».
const WEAPON_CATS := ["Оружие — выстрел", "Оружие — обращение"]
## Какие разделы свёрнуты — между запусками стенда.
var ui_state_path: String = "user://sound_bench_ui.json"
const MODES := {"near": "вблизи", "far": "вдали", "wall": "за стеной"}
## Слоты выстрела у модели (слои дистанции — WeaponDb.SHOT_LAYER_SLOTS).
const GUN_SLOTS := ["shot", "shot_suppressed", "shot_self", "shot_mid", "shot_far", "shot_distant"]
## «Как в игре» по дистанции, м: у дула (свой выстрел) и дальше, до предела слышимости винтовки.
const GAME_DISTANCES := [0.5, 5.0, 15.0, 40.0, 80.0, 120.0, 250.0, 400.0, 700.0]
const LICENSE_OPTIONS := [
	{"key": "", "name": "— выбери право —", "credit": "", "needs_source": true},
	{"key": "own_recorded", "name": "Собственная запись", "credit": "Записано владельцем проекта · собственный звук", "needs_source": false},
	{"key": "own_generated", "name": "Собственная генерация", "credit": "Сгенерировано владельцем проекта · собственный звук", "needs_source": false},
	{"key": "cc0_1", "name": "CC0 1.0", "credit": "CC0 1.0", "needs_source": true},
	{"key": "cc_by_4", "name": "CC-BY 4.0", "credit": "CC-BY 4.0", "needs_source": true},
	{"key": "cc_by_3", "name": "CC-BY 3.0", "credit": "CC-BY 3.0", "needs_source": true},
	{"key": "cc_by_25", "name": "CC-BY 2.5", "credit": "CC-BY 2.5", "needs_source": true},
	{"key": "cc_by_2", "name": "CC-BY 2.0", "credit": "CC-BY 2.0", "needs_source": true},
	{"key": "cc_by_1", "name": "CC-BY 1.0", "credit": "CC-BY 1.0", "needs_source": true},
	{"key": "royalty_free", "name": "Royalty-free (лицензия библиотеки)", "credit": "Royalty-free по лицензии библиотеки", "needs_source": true},
]
const LICENSE_HELP := ("Собственная запись — записал сам, без чужих фрагментов. Собственная генерация — "
	+ "сгенерировал сам в сервисе, который разрешает использование; название сервиса можно указать в источнике. "
	+ "CC0 — можно использовать без указания автора, но источник сохраняем для истории. CC-BY — можно использовать "
	+ "с обязательным указанием автора, ссылки и версии лицензии. Royalty-free — коммерческая библиотека или бесплатный "
	+ "набор (Sonniss GDC, Boom Library, Soundsnap): в источнике — название библиотеки и ссылка, текст её лицензии — "
	+ "файлом в assets/audio/LICENSES/ с тем же названием (например sonniss_gdc_2024.txt). NC, ND и SA проект не принимает.")

## Папки (тест подменяет своими): новые файлы, записи игры, файл авторов.
var try_dir: String = ProjectSettings.globalize_path("res://_sound_try")
var assets_dir: String = ProjectSettings.globalize_path("res://assets/audio")
var credits_path: String = ProjectSettings.globalize_path("res://assets/CREDITS.md")
## Тексты лицензий royalty-free библиотек (файл на библиотеку; имя упоминается в источнике записи).
var licenses_dir: String = ProjectSettings.globalize_path("res://assets/audio/LICENSES")
var active_selection_path: String = ProjectSettings.globalize_path(ACTIVE_SELECTION)
var catalog_doc_script: String = ProjectSettings.globalize_path("res://tools/sound_catalog_md.py")
var split_tool_path: String = ProjectSettings.globalize_path("res://tools/split_audio.py")

var sounds: Array[Dictionary] = []
var by_id: Dictionary = {}
var cats: Array[String] = []
var weapon_sounds: Array[Dictionary] = []
## Действия семейств механики (магазин, затвор, спуск у АК, AR, пистолетов…).
var family_sounds: Array[Dictionary] = []
## Отбор новых файлов: путь относительно try_dir → {assigned, use, source, license, seen, moved}.
var selection: Dictionary = {}
## Уже импортированные записи, которые владелец исключил из случайного набора игры.
var disabled_assets: Dictionary = {}
## Записи проекта, назначенные событию сверх его собственного набора: id события → [путь в
## assets/audio]. Одна запись может звучать в любом числе событий.
var links: Dictionary = {}
## Что снято с события: id → ["synth"] (синтез) / ["fallback"] (запасной набор другого события).
var removals: Dictionary = {}
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
## Дистанция для «очереди как в игре» — последняя нажатая на панели события, м.
var _game_dist: float = 15.0
var _players: Array[AudioStreamPlayer] = []
var _rng := RandomNumberGenerator.new()
var _license_re := RegEx.create_from_string("(?i)\\b(nc|nd|sa)\\b|non-?commercial|некоммерч")
var _license_ok_re := RegEx.create_from_string("(?i)cc[ _-]?(0|by)\\b|собствен|сгенерирован|own(?: work)?|generated by me")

var _filter: OptionButton
var _search: LineEdit
## Страница разделов слева (см. _refresh_page) и её прокрутка.
var _page: VBoxContainer
var _page_scroll: ScrollContainer
## Свёрнут ли раздел (ключ → bool); _bulk — «развернуть / свернуть всё» для незапомненных.
var _collapsed: Dictionary = {}
var _bulk: String = ""
## Карточки событий на странице: id → [карточка] — подсветить выбранную без перестройки.
var _cards: Dictionary = {}
var _weapon_summary: Label
var _details: VBoxContainer
var _new_list: VBoxContainer
var _tabs: TabContainer
var _bulk_source: LineEdit
var _bulk_license: OptionButton
var _status: Label
var _burst_n: SpinBox
var _rpm: SpinBox
var _inbox_tree: Tree
var _inbox_pick: String = "dir:"
var _building_inbox_tree: bool = false
## Окно выбора: «events» — где ещё звучит запись, «assets» — какие записи назначить событию.
var _picker: PopupPanel
var _picker_title: Label
var _picker_hint: Label
var _picker_search: LineEdit
var _picker_tree: Tree
var _picker_count: Label
var _picker_mode: String = ""
var _picker_key: String = ""
var _picker_checked: Dictionary = {}
var _delete_dialog: ConfirmationDialog
var _delete_scope: String = ""
var _delete_path: String = ""
var _split_popup: PopupPanel
var _split_path_label: Label
var _split_result_label: Label
var _split_threshold: SpinBox
var _split_silence: SpinBox
var _split_padding: SpinBox
var _split_min_clip: SpinBox
var _split_approve: CheckBox
var _split_remove_source: CheckBox
var _split_create_button: Button
var _split_rel: String = ""
var _split_analysis: Dictionary = {}


func _ready() -> void:
	_rng.randomize()
	_load_catalog()
	_ensure_try_dir()
	_load_selection()
	_restore_legacy_paths()
	_load_active_selection()
	_make_buses()
	_load_ui_state()
	# слушатель для «как в игре» (Audio.play — объёмный звук в точке мира)
	var cam := Camera3D.new()
	add_child(cam)
	cam.make_current()
	_build_ui()
	rescan(true)
	var capture_path := OS.get_environment("SOUND_BENCH_CAPTURE")
	var capture_pick := OS.get_environment("SOUND_BENCH_SELECT")
	var capture_split := OS.get_environment("SOUND_BENCH_SPLIT")
	var capture_tab := int(OS.get_environment("SOUND_BENCH_TAB")) if OS.get_environment("SOUND_BENCH_TAB").is_valid_int() else -1
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("capture:"):
			capture_path = arg.trim_prefix("capture:")
		elif arg.begins_with("select:"):
			capture_pick = arg.trim_prefix("select:")
		elif arg.begins_with("tab:") and arg.trim_prefix("tab:").is_valid_int():
			capture_tab = int(arg.trim_prefix("tab:"))
		elif arg.begins_with("open:"):
			# раскрыть разделы для снимка: open:weapons,class:PISTOL
			for key in arg.trim_prefix("open:").split(","):
				if key == "all":
					_bulk = "open"
				_collapsed[key] = false
	if capture_path != "":
		call_deferred("_capture_ui", capture_path, capture_pick, capture_tab, capture_split)


func _process(delta: float) -> void:
	_t += delta
	if _t >= float(Balance.AUDIO_BENCH.rescan_sec):
		_t = 0.0
		rescan()


func _unhandled_key_input(event: InputEvent) -> void:
	if event is InputEventKey and (event as InputEventKey).pressed and (event as InputEventKey).keycode == KEY_ESCAPE:
		stop_all()


## Снимок для проверки вёрстки: `-- capture:res://_sound_try/bench.png select:thunder tab:1 open:weapons`
## (или те же SOUND_BENCH_CAPTURE / SOUND_BENCH_SELECT / SOUND_BENCH_TAB; SOUND_BENCH_SPLIT открывает нарезку).
## Обычный запуск ветку не затрагивает.
func _capture_ui(path: String, pick: String, tab: int, split_rel: String = "") -> void:
	_refresh_page()
	if by_id.has(pick):
		select_event(pick)
		await get_tree().process_frame
		var shown: Array = _cards.get(pick, [])
		if not shown.is_empty():
			_page_scroll.ensure_control_visible(shown[0] as Control)
	if tab >= 0 and tab < _tabs.get_tab_count():
		_tabs.current_tab = tab
	if split_rel != "" and files.has(split_rel):
		_tabs.current_tab = 1
		_open_split_popup(split_rel)
	for _i in 5:
		await get_tree().process_frame
	var out := ProjectSettings.globalize_path(path) if path.begins_with("res://") or path.begins_with("user://") else path
	var err := get_viewport().get_texture().get_image().save_png(out)
	print("sound_bench: снимок %s (%s)" % [out, error_string(err)])
	get_tree().quit()


# ---------------------------------------------------------------- данные

func _load_catalog() -> void:
	var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(CATALOG))
	for c in d.cats:
		cats.append(String(c))
	for e in d.sounds:
		sounds.append(e as Dictionary)
		by_id[String(e.id)] = e
	weapon_sounds = WeaponDb.weapon_sound_events()
	for e in weapon_sounds:
		by_id[String(e.id)] = e
	family_sounds = WeaponDb.family_sound_events()
	for e in family_sounds:
		by_id[String(e.id)] = e


func _ensure_try_dir() -> void:
	if not DirAccess.dir_exists_absolute(try_dir):
		DirAccess.make_dir_recursive_absolute(try_dir)
	# редактор Godot эту папку не импортирует (это сырьё на пробу, не ассеты)
	if not FileAccess.file_exists(try_dir.path_join(".gdignore")):
		FileAccess.open(try_dir.path_join(".gdignore"), FileAccess.WRITE).store_string("")
	var readme := ("Кидай сюда звуки на пробу (ogg, wav, mp3) — стенд tools/sound_bench подхватит их сам.\n"
		+ "Можно копировать целые папки любой вложенности: стенд всегда сохраняет и показывает исходное дерево.\n"
		+ "Назначение игровому событию хранится в _selection.json и не перемещает исходный файл.\n"
		+ "Если один файл содержит несколько вариантов, кнопка «Разрезать по паузам» создаст отдельные WAV.\n"
		+ "Старые папки с id каталога (например shot_rifle/file.wav) по-прежнему распознаются. В git эта папка не попадает.\n")
	var readme_path := try_dir.path_join("ПРОЧТИ.txt")
	if not FileAccess.file_exists(readme_path) or FileAccess.get_file_as_string(readme_path) != readme:
		FileAccess.open(readme_path, FileAccess.WRITE).store_string(readme)


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


## Старый стенд переносил назначенный файл в папку <id>. Возвращаем такие файлы в сохранённый
## исходный путь, а назначение оставляем отдельным полем — пользовательское дерево больше не ломается.
func _restore_legacy_paths() -> void:
	var restored := false
	for key in selection.keys().duplicate():
		var rel := String(key)
		var picked: Dictionary = selection[key]
		var origin := String(picked.get("origin", rel)).replace("\\", "/")
		if origin == rel or origin == "":
			continue
		var src := try_dir.path_join(rel)
		var dst := try_dir.path_join(origin)
		if not FileAccess.file_exists(src) or FileAccess.file_exists(dst):
			continue
		var legacy_id := rel.get_base_dir() if rel.contains("/") else ""
		if by_id.has(legacy_id) and not picked.has("assigned"):
			picked.assigned = legacy_id
		DirAccess.make_dir_recursive_absolute(dst.get_base_dir())
		if DirAccess.rename_absolute(src, dst) != OK:
			continue
		selection[origin] = picked
		selection.erase(key)
		restored = true
	if restored:
		save_selection()


func _load_active_selection() -> void:
	disabled_assets.clear()
	links.clear()
	removals.clear()
	if not FileAccess.file_exists(active_selection_path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(active_selection_path))
	if not parsed is Dictionary:
		return
	for rel in (parsed as Dictionary).get("disabled", []):
		disabled_assets[String(rel).replace("\\", "/")] = true
	var l: Variant = (parsed as Dictionary).get("links", {})
	if l is Dictionary:
		for id in l:
			var arr: Array[String] = []
			for rel in (l as Dictionary)[id]:
				arr.append(String(rel).replace("\\", "/"))
			links[String(id)] = arr
	var r: Variant = (parsed as Dictionary).get("removed", {})
	if r is Dictionary:
		for id in r:
			var arr: Array[String] = []
			for what in (r as Dictionary)[id]:
				arr.append(String(what))
			removals[String(id)] = arr


func save_active_selection() -> void:
	var disabled: Array[String] = []
	for rel in disabled_assets:
		disabled.append(String(rel))
	disabled.sort()
	var link_out := {}
	for id in links:
		if not (links[id] as Array).is_empty():
			link_out[id] = links[id]
	var removed_out := {}
	for id in removals:
		if not (removals[id] as Array).is_empty():
			removed_out[id] = removals[id]
	var data := {
		"_comment": "Стенд звуков (tools/sound_bench). Пути относительно assets/audio. disabled — записи, исключённые из игры везде (файл остаётся, можно включить обратно). links — id события → записи из других наборов, которые тоже звучат в этом событии (одна запись — сколько угодно событий). removed — id события → что с него снято: synth (синтез), fallback (запасной набор другого события); без своих записей такое событие молчит.",
		"disabled": disabled,
		"links": link_out,
		"removed": removed_out,
	}
	var f := FileAccess.open(active_selection_path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(data, "\t") + "\n")


func _asset_rel(path: String) -> String:
	return path.trim_prefix(assets_dir + "/").replace("\\", "/")


func asset_enabled(path: String) -> bool:
	return not disabled_assets.has(_asset_rel(path))


func set_asset_enabled(path: String, enabled: bool) -> void:
	var rel := _asset_rel(path)
	if enabled:
		disabled_assets.erase(rel)
	else:
		disabled_assets[rel] = true
	save_active_selection()
	Audio.reload_samples()
	_refresh_all()


## Отбор файла (заводится при первой встрече: ещё не слушали, не отмечен).
func sel(rel: String) -> Dictionary:
	if not selection.has(rel):
		selection[rel] = {"use": false, "source": "", "license": "", "seen": false, "moved": "", "origin": rel}
	var picked: Dictionary = selection[rel]
	if not picked.has("origin"):
		picked.origin = rel
	if not picked.has("license"):
		picked.license = ""
	return picked


## Новые файлы любой вложенности. Назначенные стендом лежат прямо в подпапке <id звука>;
## произвольные деревья от генератора остаются входящими и показываются с исходным путём.
func try_files() -> Array[String]:
	var out: Array[String] = []
	if not DirAccess.dir_exists_absolute(try_dir):
		return out
	_collect_try_files(try_dir, "", out)
	out.sort()
	return out


func _collect_try_files(dir: String, rel_dir: String, out: Array[String]) -> void:
	for f in DirAccess.get_files_at(dir):
		if _is_audio(f):
			out.append(f if rel_dir == "" else rel_dir.path_join(f))
	for d in DirAccess.get_directories_at(dir):
		if d.begins_with("_") or d.begins_with("."):
			continue
		var child_rel := d if rel_dir == "" else rel_dir.path_join(d)
		_collect_try_files(dir.path_join(d), child_rel, out)


func _is_audio(f: String) -> bool:
	return EXTS.has(f.get_extension().to_lower())


func assigned_id(rel: String) -> String:
	var picked: Dictionary = selection.get(rel, {})
	if picked.has("assigned"):
		var explicit := String(picked.assigned)
		return explicit if by_id.has(explicit) else ""
	# Совместимость с прежним стендом: папка <id>/file означала назначение.
	var base := rel.get_base_dir() if rel.contains("/") else ""
	return base if by_id.has(base) else ""


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
	var installed := asset_files(String(e.file))
	var active := 0
	for path in installed:
		if asset_enabled(String(path)):
			active += 1
	var linked := 0
	for rel in links.get(id, []):
		var path := assets_dir.path_join(String(rel))
		if asset_enabled(path) and FileAccess.file_exists(path):
			linked += 1
	var no_synth := is_removed(id, "synth")
	var no_fallback := is_removed(id, "fallback")
	var st := {"rec": active, "rec_total": installed.size(), "disabled": installed.size() - active,
		"linked": linked, "no_synth": no_synth, "no_fallback": no_fallback,
		"fallback_rec": 0, "fallback_name": "", "wired": kind != "", "synth": false,
		"try": 0, "new": 0, "use": 0, "pending": 0, "absent": false}
	var fallback := {} if no_fallback else _event_for_ref(String(e.get("fallback", "")))
	for _i in 8:
		if fallback.is_empty() or String(fallback.id) == id:
			break
		for path in asset_files(String(fallback.file)):
			if asset_enabled(String(path)):
				st.fallback_rec = int(st.fallback_rec) + 1
		st.fallback_name = String(fallback.name)
		if int(st.fallback_rec) > 0:
			break
		fallback = _event_for_ref(String(fallback.get("fallback", "")))
	if kind.begins_with("loop:"):
		st.synth = true
	elif kind != "" and not no_synth:
		var base := Audio.kind_base(kind)
		st.synth = Audio.has_own_synth(base) if no_fallback else Audio.has_synth(base)
	# в игре такого звука нет: своей записи нет и код его не зовёт (где-то пока звучит замена — «now»)
	st.absent = kind == "" and int(st.rec) == 0 and linked == 0
	for rel in files:
		if assigned_id(rel) != id:
			continue
		st.try += 1
		var s := sel(rel)
		if not bool(s.seen):
			st.new += 1
		if bool(s.use):
			st.use += 1
			if String(s.get("moved", "")) == "":
				st.pending += 1
	return st


## Все варианты звука для прослушивания: сначала свои записи и отмеченные кандидаты. Если своих
## ещё нет, модель временно пользуется указанным в каталоге общим запасным набором.
func streams_of(id: String, with_fallback: bool = true) -> Array[AudioStream]:
	var out: Array[AudioStream] = []
	for path in asset_files(String(by_id[id].file)):
		if not asset_enabled(path):
			continue
		var st := load_stream(path)
		if st:
			out.append(st)
	for rel in links.get(id, []):
		var path := assets_dir.path_join(String(rel))
		if asset_enabled(path) and FileAccess.file_exists(path):
			var st := load_stream(path)
			if st:
				out.append(st)
	for rel in files:
		if assigned_id(rel) == id and bool(sel(rel).use):
			var st := load_stream(try_dir.path_join(rel))
			if st:
				out.append(st)
	if out.is_empty() and with_fallback and not is_removed(id, "fallback"):
		var fallback := _event_for_ref(String((by_id[id] as Dictionary).get("fallback", "")))
		if not fallback.is_empty() and String(fallback.id) != id:
			return streams_of(String(fallback.id), true)
	return out


## Назначить запись проекта (путь в assets/audio) ещё одному событию. В собственный набор
## события запись уже входит — второй раз не назначается.
func link_asset(rel: String, id: String) -> bool:
	rel = rel.replace("\\", "/")
	if not by_id.has(id) or not _safe_audio_rel(rel) or not FileAccess.file_exists(assets_dir.path_join(rel)):
		return false
	if owner_of_asset(rel) == id:
		return false
	var arr: Array[String] = []
	arr.assign(links.get(id, []))
	if rel in arr:
		return false
	arr.append(rel)
	links[id] = arr
	_bench_changed()
	return true


## Снять назначенную запись с события (сам файл и другие события не трогаются).
func unlink_asset(rel: String, id: String) -> bool:
	var arr: Array[String] = []
	arr.assign(links.get(id, []))
	if not rel in arr:
		return false
	arr.erase(rel)
	links[id] = arr
	_bench_changed()
	return true


## События, которым запись назначена сверх своего набора.
func linked_events(rel: String) -> Array[String]:
	var out: Array[String] = []
	for id in links:
		if rel in (links[id] as Array):
			out.append(String(id))
	out.sort()
	return out


## Событие, в чей собственный набор входит запись («guns/carbine_03.wav» → shot_rifle).
func owner_of_asset(rel: String) -> String:
	var stem := rel.get_basename()
	for id in by_id:
		var prefix := String((by_id[id] as Dictionary).get("file", ""))
		if prefix != "" and stem.begins_with(prefix) and stem.trim_prefix(prefix).is_valid_int():
			return String(id)
	return ""


func is_removed(id: String, what: String) -> bool:
	return what in (removals.get(id, []) as Array)


## Снять с события синтез («synth») или запасной набор («fallback»); on = false — вернуть.
func set_removed(id: String, what: String, on: bool) -> void:
	var arr: Array[String] = []
	arr.assign(removals.get(id, []))
	if on and not what in arr:
		arr.append(what)
	elif not on:
		arr.erase(what)
	removals[id] = arr
	_bench_changed()


func _bench_changed() -> void:
	save_active_selection()
	Audio.reload_samples()
	_refresh_all()


## Все записи проекта (пути относительно assets/audio) — для «назначить запись из проекта».
func all_assets() -> Array[String]:
	var out: Array[String] = []
	if not DirAccess.dir_exists_absolute(assets_dir):
		return out
	for d in DirAccess.get_directories_at(assets_dir):
		for f in DirAccess.get_files_at(assets_dir.path_join(d)):
			if _is_audio(f):
				out.append(d + "/" + f)
	out.sort()
	return out


## fallback в данных может ссылаться как на ID каталога, так и прямо на игровой kind. Второе
## нужно оружию: у старой марксманской записи ID `shot_marksman`, а игровой kind — `shot_bolt`.
func _event_for_ref(ref: String) -> Dictionary:
	if ref == "":
		return {}
	if by_id.has(ref):
		return by_id[ref]
	for e in by_id.values():
		if String((e as Dictionary).get("kind", "")) == ref:
			return e as Dictionary
	return {}


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


## Назначить файл звуку, не меняя пользовательское дерево папок. Новый путь равен исходному.
func assign(rel: String, id: String, refresh: bool = true) -> String:
	var picked := sel(rel)
	# После добавления в проект назначение — часть истории авторства: его нельзя молча переписать.
	if String(picked.moved) != "":
		return rel
	if id != "" and not by_id.has(id):
		return rel
	if assigned_id(rel) == id and picked.has("assigned"):
		return rel
	# Одобрение относится к конкретному игровому событию. После переназначения нужно
	# прослушать выбор в новом контексте и одобрить его снова.
	picked.assigned = id
	picked.use = false
	if refresh:
		save_selection()
		_refresh_all()
	return rel


## Папка генератора обычно содержит несколько вариантов одного звука: назначаем её целиком,
## но интерфейс и сканирование перестраиваем только один раз после всех перемещений.
func assign_many(rels: Array[String], id: String) -> void:
	if not by_id.has(id):
		return
	for rel in rels:
		assign(rel, id, false)
	save_selection()
	_refresh_all()


## Следующий свободный номер у префикса в assets/audio.
func next_number(prefix: String) -> int:
	var head := prefix.split("/")[1]
	var mx := 0
	for f in asset_files(prefix):
		mx = maxi(mx, int(f.get_file().get_basename().trim_prefix(head)))
	return mx + 1


func _license_index(key: String) -> int:
	for i in LICENSE_OPTIONS.size():
		if String((LICENSE_OPTIONS[i] as Dictionary).key) == key:
			return i
	return 0


func _license_at(index: int) -> Dictionary:
	if index < 0 or index >= LICENSE_OPTIONS.size():
		return LICENSE_OPTIONS[0]
	return LICENSE_OPTIONS[index]


func _license_for(key: String) -> Dictionary:
	return _license_at(_license_index(key))


func _legacy_license_key(source: String) -> String:
	if _license_re.search(source) != null:
		return ""
	var lower := source.to_lower()
	if lower.contains("сгенерирован") or lower.contains("generated by me"):
		return "own_generated"
	if lower.contains("собствен") or lower.contains("own work"):
		return "own_recorded"
	if lower.contains("cc0") or lower.contains("cc 0") or lower.contains("cc-0"):
		return "cc0_1"
	if lower.contains("cc-by 4") or lower.contains("cc by 4"):
		return "cc_by_4"
	if lower.contains("cc-by 3") or lower.contains("cc by 3"):
		return "cc_by_3"
	if lower.contains("cc-by 2.5") or lower.contains("cc by 2.5"):
		return "cc_by_25"
	if lower.contains("cc-by 2") or lower.contains("cc by 2"):
		return "cc_by_2"
	if lower.contains("cc-by 1") or lower.contains("cc by 1"):
		return "cc_by_1"
	if lower.contains("cc-by") or lower.contains("cc by"):
		return "cc_by_4"
	return ""


func _selected_license_key(picked: Dictionary) -> String:
	var key := String(picked.get("license", ""))
	return key if key != "" else _legacy_license_key(String(picked.get("source", "")))


func _fill_license_options(option: OptionButton, selected_key: String = "") -> void:
	for raw in LICENSE_OPTIONS:
		var item := raw as Dictionary
		option.add_item(String(item.name))
	option.select(_license_index(selected_key))
	option.tooltip_text = LICENSE_HELP


## Строка, которая попадёт в CREDITS: для новых карточек право выбирается списком, старые
## объединённые записи остаются читаемыми без принудительной миграции.
func _credit_source(picked: Dictionary) -> String:
	var source := String(picked.get("source", "")).strip_edges()
	var key := String(picked.get("license", ""))
	if key == "":
		return source
	var license := _license_for(key)
	var credit := String(license.credit)
	var lower := source.to_lower()
	if key.begins_with("own_") and (lower.contains("собствен") or lower.contains("own work")):
		return source
	if key.begins_with("cc") and _legacy_license_key(source) == key:
		return source
	return credit if source == "" else "%s · %s" % [source, credit]


## Отмеченные файлы — в assets/audio под следующим номером, источник — строкой в CREDITS.md.
## Без источника, без назначенного звука или с лицензией NC/ND — отказ. Возвращает журнал.
func transfer_block_reason(rel: String) -> String:
	var s := sel(rel)
	var id := assigned_id(rel)
	if not by_id.has(id):
		return "не назначен звук"
	var key := String(s.get("license", ""))
	var src := String(s.source).strip_edges()
	if _license_re.search(src) != null:
		return "лицензии NC / ND / SA не подходят (AGENTS.md, п. 6)"
	if key != "":
		var license := _license_for(key)
		if String(license.key) != key:
			return "выбери право использования из списка"
		if bool(license.needs_source) and src == "":
			return "для CC-лицензии укажи источник, автора или ссылку"
		var source_key := _legacy_license_key(src)
		if source_key != "" and source_key != key:
			return "в источнике указано другое право; исправь текст или выбор в списке"
		if key == "royalty_free" and library_license(src) == "":
			return "royalty-free: положи текст лицензии библиотеки в assets/audio/LICENSES/<название>.txt и укажи это название в источнике"
		return ""
	if src == "":
		return "укажи источник и выбери право использования"
	if _license_ok_re.search(src) == null:
		return "выбери право использования из списка"
	return ""


## Файл лицензии библиотеки, чьё название есть в источнике («Sonniss GDC 2024 …» ↔
## sonniss_gdc_2024.txt; сравнение без регистра, пробелов и знаков). Пусто — не найден.
func library_license(source: String) -> String:
	if not DirAccess.dir_exists_absolute(licenses_dir):
		return ""
	var norm := func(t: String) -> String:
		var out := ""
		for ch in t.to_lower():
			if (ch >= "a" and ch <= "z") or (ch >= "0" and ch <= "9") or (ch >= "а" and ch <= "я") or ch == "ё":
				out += ch
		return out
	var src: String = norm.call(source)
	for f in DirAccess.get_files_at(licenses_dir):
		var stem: String = norm.call(String(f).get_basename())
		if stem.length() >= 4 and src.contains(stem):
			return String(f)
	return ""


func transfer() -> Array[String]:
	var journal: Array[String] = []
	var rows: Array[String] = []
	for rel in files:
		var s := sel(rel)
		if not bool(s.use) or String(s.moved) != "":
			continue
		var issue := transfer_block_reason(rel)
		if issue != "":
			journal.append("%s — %s" % [rel, issue])
			continue
		var id := assigned_id(rel)
		var src := _credit_source(s)
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
		rows.append("| %s | %s | %s — %s |" % [src.replace("|", "/"), rel.get_file(), s.moved, String(e.name)])
		if String(e.kind) == "":
			journal.append("%s → assets/audio/%s — запись сохранена, но игровой код этот звук пока не вызывает" % [rel, s.moved])
		else:
			journal.append("%s → assets/audio/%s — готово, игра вызывает «%s»" % [rel, s.moved, String(e.kind)])
	if not rows.is_empty():
		_append_credits(rows)
		Audio.reload_samples()
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


## Удалить отвергнутый входящий файл. Если он уже был добавлен в проект, удаляется и копия
## в assets/audio со служебными записями. Публичный метод нужен автотесту; интерфейс зовёт его
## только после явного подтверждения.
func delete_incoming_permanently(rel: String) -> bool:
	rel = rel.replace("\\", "/")
	if not _safe_audio_rel(rel):
		return false
	stop_all()
	var picked: Dictionary = selection.get(rel, {})
	var moved := String(picked.get("moved", ""))
	var removed := _remove_file(try_dir.path_join(rel))
	if moved != "":
		removed = _remove_project_asset(moved) or removed
	selection.erase(rel)
	_remove_empty_try_dirs(try_dir.path_join(rel).get_base_dir())
	_finish_permanent_delete()
	return removed


## Удалить уже импортированную запись и, если она пришла через стенд, её исходный кандидат.
## Каталоговое событие и игровой вызов остаются: удаляется именно плохая запись, а не механика.
func delete_asset_permanently(rel: String) -> bool:
	rel = rel.replace("\\", "/")
	if not _safe_audio_rel(rel):
		return false
	stop_all()
	var removed := _remove_project_asset(rel)
	for id in links:
		(links[id] as Array).erase(rel)
	save_active_selection()
	for key in selection.keys().duplicate():
		var incoming_rel := String(key)
		var picked: Dictionary = selection[key]
		if String(picked.get("moved", "")) != rel:
			continue
		removed = _remove_file(try_dir.path_join(incoming_rel)) or removed
		selection.erase(key)
		_remove_empty_try_dirs(try_dir.path_join(incoming_rel).get_base_dir())
	_finish_permanent_delete()
	return removed


func _remove_project_asset(rel: String) -> bool:
	rel = rel.replace("\\", "/")
	if not _safe_audio_rel(rel):
		return false
	var path := assets_dir.path_join(rel)
	var removed := _remove_file(path)
	# Godot хранит рядом описание импорта. Кэш в .godot не является исходником и будет очищен движком.
	_remove_file(path + ".import")
	disabled_assets.erase(rel)
	_remove_credit_for_asset(rel)
	return removed


func _safe_audio_rel(rel: String) -> bool:
	return rel != "" and not rel.contains("..") and not rel.is_absolute_path() \
		and EXTS.has(rel.get_extension().to_lower())


func _remove_file(path: String) -> bool:
	if not FileAccess.file_exists(path):
		return false
	return DirAccess.remove_absolute(path) == OK


func _remove_empty_try_dirs(start: String) -> void:
	var root := try_dir.replace("\\", "/").trim_suffix("/")
	var dir := start.replace("\\", "/").trim_suffix("/")
	while dir != root and dir.begins_with(root + "/"):
		var opened := DirAccess.open(dir)
		if opened == null or not opened.get_files().is_empty() or not opened.get_directories().is_empty():
			return
		if DirAccess.remove_absolute(dir) != OK:
			return
		dir = dir.get_base_dir()


func _remove_credit_for_asset(rel: String) -> void:
	if not FileAccess.file_exists(credits_path):
		return
	var needle := "| %s — " % rel
	var kept := PackedStringArray()
	for line in FileAccess.get_file_as_string(credits_path).split("\n", true):
		if line.begins_with("|") and line.contains(needle):
			continue
		kept.append(line)
	FileAccess.open(credits_path, FileAccess.WRITE).store_string("\n".join(kept))


func _finish_permanent_delete() -> void:
	save_selection()
	save_active_selection()
	_asset_cache.clear()
	_cache.clear()
	Audio.reload_samples()
	_regenerate_catalog_doc()
	rescan(true)


func _regenerate_catalog_doc() -> void:
	if catalog_doc_script == "" or not FileAccess.file_exists(catalog_doc_script):
		return
	var output: Array = []
	OS.execute("python", PackedStringArray([catalog_doc_script]), output, true)


## Найти отдельные звуки во входящем файле. Параметры те же, что видит пользователь в окне нарезки.
func analyze_incoming(rel: String, threshold_db: float = -36.0, min_silence_ms: float = 180.0,
		padding_ms: float = 35.0, min_clip_ms: float = 60.0) -> Dictionary:
	rel = rel.replace("\\", "/")
	if not _safe_audio_rel(rel) or not FileAccess.file_exists(try_dir.path_join(rel)):
		return {"ok": false, "error": "входящий файл не найден"}
	return _run_split_tool("analyze", try_dir.path_join(rel), threshold_db, min_silence_ms,
		padding_ms, min_clip_ms)


## Создать рядом с исходником отдельные WAV. Назначение, источник и лицензия наследуются;
## одобрение исходного многозвучного файла всегда снимается, чтобы он не попал в игру случайно.
func split_incoming(rel: String, threshold_db: float = -36.0, min_silence_ms: float = 180.0,
		padding_ms: float = 35.0, min_clip_ms: float = 60.0, approve_parts: bool = false,
		remove_source: bool = false) -> Dictionary:
	rel = rel.replace("\\", "/")
	if not _safe_audio_rel(rel) or not FileAccess.file_exists(try_dir.path_join(rel)):
		return {"ok": false, "error": "входящий файл не найден"}
	var prefix := _next_split_prefix(rel)
	var result := _run_split_tool("split", try_dir.path_join(rel), threshold_db, min_silence_ms,
		padding_ms, min_clip_ms, prefix)
	if not bool(result.get("ok", false)):
		return result
	var original: Dictionary = sel(rel).duplicate(true)
	var id := assigned_id(rel)
	var original_live := sel(rel)
	original_live.use = false
	var original_moved := String(original.get("moved", ""))
	# Если длинный исходник уже успели добавить в assets/audio, одной снятой галочки входящего
	# недостаточно: исключаем готовую копию из случайного выбора до решения пользователя.
	if original_moved != "" and not remove_source:
		disabled_assets[original_moved] = true
		save_active_selection()
		Audio.reload_samples()
	var made: Array[String] = []
	for raw_path in result.get("files", []):
		var new_rel := _try_relative(String(raw_path))
		if new_rel == "":
			continue
		var picked: Dictionary = original.duplicate(true)
		picked.assigned = id
		picked.use = approve_parts
		picked.seen = false
		picked.moved = ""
		picked.origin = new_rel
		picked.split_from = rel
		selection[new_rel] = picked
		made.append(new_rel)
	result["rel_files"] = made
	if remove_source:
		delete_incoming_permanently(rel)
	else:
		save_selection()
		rescan(true)
	return result


func _run_split_tool(mode: String, input: String, threshold_db: float, min_silence_ms: float,
		padding_ms: float, min_clip_ms: float, output_prefix: String = "") -> Dictionary:
	if not FileAccess.file_exists(split_tool_path):
		return {"ok": false, "error": "не найден tools/split_audio.py"}
	var args := PackedStringArray([
		split_tool_path, mode, input,
		"--threshold-db", str(threshold_db),
		"--min-silence-ms", str(min_silence_ms),
		"--padding-ms", str(padding_ms),
		"--min-clip-ms", str(min_clip_ms),
	])
	if output_prefix != "":
		args.append("--output-prefix")
		args.append(output_prefix)
	var output: Array = []
	var exit_code := OS.execute("python", args, output, true)
	var text := "\n".join(output)
	var lines := text.split("\n", false)
	for index in range(lines.size() - 1, -1, -1):
		var parsed: Variant = JSON.parse_string(String(lines[index]).strip_edges())
		if parsed is Dictionary:
			var result := parsed as Dictionary
			if exit_code != 0 and bool(result.get("ok", false)):
				result.ok = false
				result.error = "инструмент нарезки завершился с кодом %d" % exit_code
			return result
	return {"ok": false, "error": text.strip_edges() if text.strip_edges() != "" else "инструмент нарезки не вернул результат"}


func _next_split_prefix(rel: String) -> String:
	var input := try_dir.path_join(rel)
	var dir := input.get_base_dir()
	var base := rel.get_file().get_basename() + "_part"
	var batch := 1
	while true:
		var suffix := "" if batch == 1 else "_%d" % batch
		var prefix := dir.path_join(base + suffix)
		var head := prefix.get_file() + "_"
		var occupied := false
		for file in DirAccess.get_files_at(dir):
			if file.begins_with(head) and file.get_extension().to_lower() == "wav":
				occupied = true
				break
		if not occupied:
			return prefix
		batch += 1
	return dir.path_join(base)


func _try_relative(path: String) -> String:
	var root := try_dir.replace("\\", "/").trim_suffix("/")
	var normalized := path.replace("\\", "/")
	if not normalized.begins_with(root + "/"):
		return ""
	return normalized.trim_prefix(root + "/")


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


## Как звучит в игре сейчас: тот же вызов Audio.play (запись, если есть, иначе синтез), вместе с
## одобренными, но ещё не добавленными кандидатами; слой дистанции — с его расстояния
## (Balance.AUDIO_LAYERS), лупы — тем, что отдаёт звуковая система.
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
	var layer := Audio.kind_layer(kind)
	return play_game_at(id, Audio.layer_at_m(layer) if layer != "" else 3.0)


## Выстрел события «как в игре» на расстоянии dist, м, перед слушателем: слои дистанции
## сменяются, как в рейде (и звук приходит с задержкой — 343 м/с).
func play_game_at(id: String, dist: float) -> bool:
	var kind := String(by_id[id].kind) if by_id.has(id) else ""
	if kind == "" or kind.begins_with("loop:"):
		return false
	sync_preview()
	var cam := get_viewport().get_camera_3d()
	var at := (cam.global_position if cam else Vector3.ZERO) + Vector3(0.0, 0.0, -maxf(dist, 0.3))
	Audio.play(Audio.kind_base(kind), at)
	return true


## Очередь «как в игре»: count выстрелов с темпом rpm на расстоянии dist — хвосты внахлёст, как в рейде.
func play_game_burst(id: String, dist: float, count: int, rpm: float) -> void:
	_burst_id += 1
	var my := _burst_id
	for i in count:
		if my != _burst_id or not is_inside_tree() or not play_game_at(id, dist):
			return
		await get_tree().create_timer(60.0 / maxf(rpm, 1.0)).timeout


## Пройти все дистанции по очереди: от дула до предела слышимости, с паузой на хвост.
func play_game_walk(id: String) -> void:
	_burst_id += 1
	var my := _burst_id
	for d in GAME_DISTANCES:
		if my != _burst_id or not is_inside_tree() or not play_game_at(id, float(d)):
			return
		if _status:
			_status.text = "Как в игре: %s" % _distance_name(float(d))
		await get_tree().create_timer(float(Balance.AUDIO_BENCH.walk_gap_sec) + float(d) / float(Balance.AUDIO_FAR.sound_mps)).timeout


func _distance_name(d: float) -> String:
	return "у дула — свой выстрел" if d < 1.0 else "%d м" % int(d)


## Одобренные, но ещё не добавленные кандидаты — в звуковую систему, чтобы «как в игре» их слышало.
func sync_preview() -> void:
	var map: Dictionary = {}
	for rel in files:
		var id := assigned_id(rel)
		var s: Dictionary = selection.get(rel, {})
		if id == "" or not bool(s.get("use", false)) or String(s.get("moved", "")) != "":
			continue
		var kind := String(by_id[id].kind)
		if kind == "" or kind.begins_with("loop:"):
			continue
		var st := load_stream(try_dir.path_join(rel))
		if st == null:
			continue
		if not map.has(kind):
			map[kind] = []
		(map[kind] as Array).append(st)
	Audio.set_preview(map)


func _preview_game(id: String) -> void:
	if not play_game(id):
		_status.text = "Этот звук ещё не подключён к событию в коде. Кандидаты ниже всё равно можно подготовить."
		return
	var st := status_of(id)
	if int(st.pending) > 0:
		_status.text = "«Как в игре» — записи игры и одобренные кандидаты (ещё не добавлено: %d). В саму игру они попадут после шага 4." % int(st.pending)
	else:
		_status.text = "Проигран текущий игровой звук из assets/audio%s." % (" (запасной набор или синтез)" if int(st.rec) == 0 else "")


func _is_loop(id: String) -> bool:
	return by_id.has(id) and String(by_id[id].type) == "loop"


func _is_gun(id: String) -> bool:
	if id.begins_with("shot_"):
		return true
	return by_id.has(id) and String((by_id[id] as Dictionary).get("slot", "")) in GUN_SLOTS


func _build_split_popup(layer: CanvasLayer) -> void:
	_split_popup = PopupPanel.new()
	layer.add_child(_split_popup)
	var margin := MarginContainer.new()
	for side in ["left", "right", "top", "bottom"]:
		margin.add_theme_constant_override("margin_" + side, 16)
	_split_popup.add_child(margin)
	var box := VBoxContainer.new()
	box.custom_minimum_size.x = 700
	box.add_theme_constant_override("separation", 10)
	margin.add_child(box)
	box.add_child(_label("Разрезать один файл на отдельные варианты", 20, Color(1.0, 0.86, 0.6)))
	_split_path_label = _label("", 14, Color(0.85, 0.86, 0.88))
	_split_path_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(_split_path_label)
	var help := _label("Стенд ищет громкие участки, разделённые тишиной. Если частей слишком мало — подними порог; "
		+ "если один выстрел распался на несколько — опусти порог или увеличь минимальную паузу.", 13, COL_DIM)
	help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(help)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 6)
	box.add_child(grid)
	_split_threshold = _split_setting(grid, "Порог тишины", -60.0, -6.0, 1.0, -36.0, " dB")
	_split_silence = _split_setting(grid, "Минимальная пауза", 40.0, 2000.0, 10.0, 180.0, " мс")
	_split_padding = _split_setting(grid, "Запас до/после звука", 0.0, 300.0, 5.0, 35.0, " мс")
	_split_min_clip = _split_setting(grid, "Минимальная длина части", 20.0, 2000.0, 10.0, 60.0, " мс")
	for spin in [_split_threshold, _split_silence, _split_padding, _split_min_clip]:
		spin.value_changed.connect(func(_value: float) -> void: _split_settings_changed())
	_split_approve = CheckBox.new()
	_split_approve.text = "Сразу одобрить все созданные части к добавлению"
	_split_approve.button_pressed = false
	box.add_child(_split_approve)
	_split_remove_source = CheckBox.new()
	_split_remove_source.text = "После успешной нарезки удалить исходный длинный файл"
	_split_remove_source.button_pressed = false
	_split_remove_source.tooltip_text = "По умолчанию исходник остаётся, но его одобрение всё равно снимается"
	box.add_child(_split_remove_source)
	_split_result_label = _label("", 14, COL_DIM)
	_split_result_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_split_result_label.custom_minimum_size.y = 80
	box.add_child(_split_result_label)
	var actions := HBoxContainer.new()
	actions.add_theme_constant_override("separation", 8)
	box.add_child(actions)
	actions.add_child(_button("Найти части", _analyze_split_popup))
	_split_create_button = _button("Создать отдельные варианты", _create_split_popup)
	_split_create_button.disabled = true
	actions.add_child(_split_create_button)
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_child(spacer)
	actions.add_child(_button("Отмена", func() -> void: _split_popup.hide()))


func _split_setting(grid: GridContainer, title: String, min_value: float, max_value: float,
		step: float, value: float, suffix: String) -> SpinBox:
	grid.add_child(_label(title, 14, COL_DIM))
	var spin := SpinBox.new()
	spin.min_value = min_value
	spin.max_value = max_value
	spin.step = step
	spin.value = value
	spin.suffix = suffix
	spin.custom_minimum_size.x = 180
	grid.add_child(spin)
	return spin


# ---------------------------------------------------------------- интерфейс

func _build_ui() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	_delete_dialog = ConfirmationDialog.new()
	_delete_dialog.title = "Удалить звук безвозвратно?"
	_delete_dialog.get_ok_button().text = "Удалить навсегда"
	_delete_dialog.confirmed.connect(_confirm_permanent_delete)
	layer.add_child(_delete_dialog)
	_build_split_popup(layer)
	_build_picker(layer)
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
	root.add_theme_constant_override("separation", 8)
	margin.add_child(root)

	# Заголовок и действия — отдельно от прослушивания, чтобы строка не вылезала за экран.
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 10)
	root.add_child(head)
	head.add_child(_label("Стенд звуков", 22, Color(1.0, 0.86, 0.6)))
	var inbox := _label("Входящие: res://_sound_try", 15, COL_DIM)
	inbox.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	inbox.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	head.add_child(inbox)
	head.add_child(_button("1. Открыть папку", func() -> void: OS.shell_open(try_dir)))
	head.add_child(_button("Обновить", func() -> void: rescan(true)))
	head.add_child(_button("4. Добавить одобренные в игру", _on_transfer))

	var listen_panel := PanelContainer.new()
	var listen_style := StyleBoxFlat.new()
	listen_style.bg_color = Color(0.12, 0.125, 0.14)
	listen_style.set_content_margin_all(7)
	listen_panel.add_theme_stylebox_override("panel", listen_style)
	root.add_child(listen_panel)
	var top := HBoxContainer.new()
	top.add_theme_constant_override("separation", 8)
	listen_panel.add_child(top)
	top.add_child(_label("ПРОСЛУШИВАНИЕ", 14, Color(1.0, 0.86, 0.6)))
	top.add_child(_label("Место", 15, COL_DIM))
	var space := OptionButton.new()
	for sp in Balance.AUDIO_SPACES:
		space.add_item(String((Balance.AUDIO_SPACES[sp] as Dictionary).name))
		space.set_item_metadata(space.item_count - 1, String(sp))
	space.item_selected.connect(func(i: int) -> void: set_space(String(space.get_item_metadata(i))))
	top.add_child(space)
	top.add_child(_label("Дистанция", 15, COL_DIM))
	var mode := OptionButton.new()
	for m in MODES:
		mode.add_item(String(MODES[m]))
		mode.set_item_metadata(mode.item_count - 1, String(m))
	mode.item_selected.connect(func(i: int) -> void: set_mode(String(mode.get_item_metadata(i))))
	top.add_child(mode)
	top.add_child(_label("Очередь", 15, COL_DIM))
	_burst_n = _spin(2, 30, int(Balance.AUDIO_BENCH.burst))
	_burst_n.custom_minimum_size.x = 70
	top.add_child(_burst_n)
	top.add_child(_label("выстрелов, темп", 15, COL_DIM))
	_rpm = _spin(30, 1200, int(Balance.AUDIO_BENCH.rpm))
	_rpm.step = 10
	_rpm.custom_minimum_size.x = 95
	top.add_child(_rpm)
	top.add_child(_label("/ мин.", 15, COL_DIM))
	var listen_space := Control.new()
	listen_space.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top.add_child(listen_space)
	top.add_child(_label("Громкость", 15, COL_DIM))
	var vol := HSlider.new()
	vol.min_value = -30.0
	vol.max_value = 6.0
	vol.value = 0.0
	vol.custom_minimum_size = Vector2(170, 0)
	vol.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var vol_value := _label("0 дБ", 14, Color(0.85, 0.86, 0.88))
	vol_value.custom_minimum_size.x = 48
	vol.value_changed.connect(func(v: float) -> void:
		_vol_db = v
		vol_value.text = "%+.0f дБ" % v)
	top.add_child(vol)
	top.add_child(vol_value)
	top.add_child(_button("■ Стоп (Esc)", stop_all))

	# Одна страница: слева — разделы со сворачиванием (оружие → классы → карточки стволов, общие
	# наборы; дальше разделы каталога → подгруппы → карточки событий), справа — выбранное событие
	# и входящие файлы.
	var cols := HBoxContainer.new()
	cols.size_flags_vertical = Control.SIZE_EXPAND_FILL
	cols.add_theme_constant_override("separation", 12)
	root.add_child(cols)

	var left := _column(cols, 1.55)
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 8)
	left.add_child(bar)
	_search = LineEdit.new()
	_search.placeholder_text = "найти: событие, оружие, id, файл"
	_search.clear_button_enabled = true
	_search.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_search.text_changed.connect(func(_q: String) -> void: _refresh_page())
	bar.add_child(_search)
	_filter = OptionButton.new()
	_filter.custom_minimum_size.x = 210
	for f in FILTERS:
		_filter.add_item(f)
	_filter.item_selected.connect(func(_i: int) -> void: _refresh_page())
	bar.add_child(_filter)
	bar.add_child(_button("Развернуть всё", func() -> void: expand_all(true)))
	bar.add_child(_button("Свернуть всё", func() -> void: expand_all(false)))
	var legend := _label(LEGEND, 13, COL_DIM)
	legend.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	left.add_child(legend)
	_page_scroll = ScrollContainer.new()
	_page_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_page_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	left.add_child(_page_scroll)
	_page = VBoxContainer.new()
	_page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_page.add_theme_constant_override("separation", 5)
	_page_scroll.add_child(_page)

	var work := _column(cols, 1.0)
	var guide_panel := PanelContainer.new()
	var guide_style := StyleBoxFlat.new()
	guide_style.bg_color = Color(0.10, 0.19, 0.23)
	guide_style.set_content_margin_all(8)
	guide_panel.add_theme_stylebox_override("panel", guide_style)
	var guide := _label("Новый звук: 1  положи файлы во входящие   →   2  выбери карточку события слева   →   "
		+ "3  во «Входящих» прослушай, назначь и одобри   →   4  «Добавить одобренные в игру». "
		+ "Готовую запись проекта можно назначить любому числу событий — в карточке события.", 14, COL_NEW)
	guide.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	guide_panel.add_child(guide)
	work.add_child(guide_panel)

	_tabs = TabContainer.new()
	_tabs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	work.add_child(_tabs)
	var details_tab := MarginContainer.new()
	details_tab.name = "Событие"
	details_tab.add_theme_constant_override("margin_left", 5)
	details_tab.add_theme_constant_override("margin_right", 5)
	details_tab.add_theme_constant_override("margin_top", 7)
	_tabs.add_child(details_tab)
	var ms := ScrollContainer.new()
	ms.size_flags_vertical = Control.SIZE_EXPAND_FILL
	ms.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	details_tab.add_child(ms)
	_details = VBoxContainer.new()
	_details.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_details.add_theme_constant_override("separation", 7)
	ms.add_child(_details)

	var inbox_tab := MarginContainer.new()
	inbox_tab.name = "Входящие"
	inbox_tab.add_theme_constant_override("margin_left", 5)
	inbox_tab.add_theme_constant_override("margin_right", 5)
	inbox_tab.add_theme_constant_override("margin_top", 7)
	_tabs.add_child(inbox_tab)
	var inbox_box := VBoxContainer.new()
	inbox_box.add_theme_constant_override("separation", 7)
	inbox_tab.add_child(inbox_box)
	var source_tools := HBoxContainer.new()
	source_tools.add_theme_constant_override("separation", 8)
	inbox_box.add_child(source_tools)
	source_tools.add_child(_label("Для всех пустых полей", 14, COL_DIM))
	_bulk_source = LineEdit.new()
	_bulk_source.placeholder_text = "источник / автор / сервис генерации"
	_bulk_source.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	source_tools.add_child(_bulk_source)
	_bulk_license = OptionButton.new()
	_bulk_license.custom_minimum_size.x = 250
	_fill_license_options(_bulk_license)
	source_tools.add_child(_bulk_license)
	source_tools.add_child(_button("Заполнить", _apply_bulk_source))
	var license_help := _label(LICENSE_HELP, 13, COL_DIM)
	license_help.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inbox_box.add_child(license_help)
	var inbox_hint := _label("Слева — точное дерево папок из res://_sound_try. Выбери папку или файл; справа появятся только они.", 14, COL_DIM)
	inbox_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	inbox_box.add_child(inbox_hint)
	var inbox_split := HSplitContainer.new()
	inbox_split.size_flags_vertical = Control.SIZE_EXPAND_FILL
	inbox_split.split_offset = 480
	inbox_box.add_child(inbox_split)
	_inbox_tree = Tree.new()
	_inbox_tree.custom_minimum_size.x = 430
	_inbox_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_inbox_tree.hide_root = false
	_inbox_tree.columns = 2
	_inbox_tree.column_titles_visible = true
	_inbox_tree.set_column_title(0, "Папка / файл")
	_inbox_tree.set_column_title(1, "Назначение")
	_inbox_tree.set_column_expand(0, true)
	_inbox_tree.set_column_expand(1, false)
	_inbox_tree.set_column_custom_minimum_width(1, 125)
	_inbox_tree.add_theme_font_size_override("font_size", 14)
	_inbox_tree.item_selected.connect(_on_inbox_tree_selected)
	inbox_split.add_child(_inbox_tree)
	var rs := ScrollContainer.new()
	rs.size_flags_vertical = Control.SIZE_EXPAND_FILL
	rs.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	inbox_split.add_child(rs)
	_new_list = VBoxContainer.new()
	_new_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_new_list.add_theme_constant_override("separation", 8)
	rs.add_child(_new_list)

	_status = _label("Готово к работе. Папка входящих проверяется автоматически раз в %.0f с." % float(Balance.AUDIO_BENCH.rescan_sec), 14, COL_DIM)
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	root.add_child(_status)


func _on_transfer() -> void:
	var journal := transfer()
	if journal.is_empty():
		_status.text = "Нечего добавлять: назначь файл звуку, прослушай и поставь галочку «Одобрен»."
	else:
		var added := 0
		for line in journal:
			if line.contains("→ assets/audio/"):
				added += 1
		if added == 0:
			_status.text = "НЕ ДОБАВЛЕНО:\n" + "\n".join(journal) \
				+ "\nИсправь причину в карточке и снова нажми шаг 4. «Как в игре» пока проигрывает старый набор или синтез."
		else:
			_status.text = "Добавление в проект:\n" + "\n".join(journal) \
				+ "\nДобавлено: %d. В стенде запись уже доступна через игровой Audio. Перед следующим запуском проекта выполни импорт или открой редактор." % added


func _apply_bulk_source() -> void:
	var source := _bulk_source.text.strip_edges()
	var license := _license_at(_bulk_license.selected)
	var license_key := String(license.key)
	if license_key == "":
		_status.text = "Сначала выбери право использования из выпадающего списка."
		return
	if bool(license.needs_source) and source == "":
		_status.text = "Для CC0 и CC-BY укажи источник, автора или ссылку."
		return
	var source_changed := 0
	var license_changed := 0
	for rel in files:
		var picked := sel(rel)
		if String(picked.license) == "" and _selected_license_key(picked) == "":
			picked.license = license_key
			license_changed += 1
		if source != "" and String(picked.source).strip_edges() == "":
			picked.source = source
			source_changed += 1
	save_selection()
	_refresh_details()
	_refresh_new_list()
	_status.text = "Заполнено: источник у %d, право у %d входящих файлов; уже заполненные поля не изменены." % [source_changed, license_changed]


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


# ---------------------------------------------------------------- страница разделов

## Перестроить страницу. Свёрнутый раздел не строится, пока его не откроют, — страница лёгкая
## даже со всеми стволами и сотнями событий.
func _refresh_page() -> void:
	if _page == null:
		return
	var keep := _page_scroll.scroll_vertical
	for c in _page.get_children():
		_page.remove_child(c)
		c.queue_free()
	_cards.clear()
	var q := _search.text.strip_edges().to_lower()
	var narrowing := q != "" or _filter.selected != 0
	var guns := _weapon_ids_by_class(q)
	var gun_count := 0
	for cls in guns:
		gun_count += (guns[cls] as Array).size()
	var shared: Dictionary = {}
	var shared_count := 0
	for c in WEAPON_CATS:
		shared[c] = _cat_events(c, q)
		shared_count += (shared[c] as Array).size()
	var fam_ids := _family_events(q)
	shared[FAMILY_CAT] = fam_ids
	shared_count += fam_ids.size()
	if not narrowing or gun_count + shared_count > 0:
		_section(_page, "weapons", "Оружие", "стволов %d · общих событий %d" % [gun_count, shared_count], 0, true,
			func(body: VBoxContainer) -> void: _fill_weapons(body, q, guns, shared), narrowing)
	for c in cats:
		if c in WEAPON_CATS:
			continue
		var ids := _cat_events(c, q)
		if narrowing and ids.is_empty():
			continue
		var cat := c
		_section(_page, "cat:" + c, c, _ids_info(ids), 0, true,
			func(body: VBoxContainer) -> void: _fill_cat(body, cat, ids, 1, narrowing), narrowing)
	_restore_scroll.call_deferred(keep)


func _restore_scroll(v: int) -> void:
	if _page_scroll:
		_page_scroll.scroll_vertical = v


## Сворачиваемый раздел: заголовок-кнопка и тело, которое заполняется при первом открытии.
## level: 0 — раздел, 1 — подраздел, 2 — подгруппа.
func _section(parent: Control, key: String, title: String, info: String, level: int, collapsed_default: bool,
		fill: Callable, force_open: bool = false) -> void:
	var lv := mini(level, 2)
	var open := force_open or not _is_collapsed(key, collapsed_default)
	var head := Button.new()
	head.alignment = HORIZONTAL_ALIGNMENT_LEFT
	head.focus_mode = Control.FOCUS_NONE
	head.add_theme_font_size_override("font_size", [19, 16, 15][lv])
	var font_color: Color = [Color(1.0, 0.86, 0.6), Color(0.95, 0.8, 0.55), Color(0.82, 0.72, 0.52)][lv]
	for state in ["font_color", "font_hover_color", "font_pressed_color"]:
		head.add_theme_color_override(state, font_color)
	var bg: Color = [Color(0.19, 0.17, 0.13), Color(0.15, 0.145, 0.135), Color(0.12, 0.122, 0.128)][lv]
	for state in ["normal", "hover", "pressed"]:
		var sb := StyleBoxFlat.new()
		sb.bg_color = bg.lightened(0.06) if state == "hover" else bg
		sb.set_corner_radius_all(3)
		sb.content_margin_left = 10
		sb.content_margin_right = 10
		sb.content_margin_top = 5
		sb.content_margin_bottom = 5
		head.add_theme_stylebox_override(state, sb)
	head.set_meta("section", key)
	var wrap := MarginContainer.new()
	wrap.add_theme_constant_override("margin_left", 16)
	wrap.add_theme_constant_override("margin_top", 2)
	wrap.add_theme_constant_override("margin_bottom", 6)
	var body := VBoxContainer.new()
	body.add_theme_constant_override("separation", 6)
	wrap.add_child(body)
	wrap.visible = open
	var caption := func(o: bool) -> String:
		return ("▾  " if o else "▸  ") + title + ("        " + info if info != "" else "")
	head.text = caption.call(open)
	parent.add_child(head)
	parent.add_child(wrap)
	if open:
		fill.call(body)
	head.pressed.connect(func() -> void:
		var now := not wrap.visible
		_collapsed[key] = not now
		if now and body.get_child_count() == 0:
			fill.call(body)
		wrap.visible = now
		head.text = caption.call(now)
		_save_ui_state())


func _is_collapsed(key: String, collapsed_default: bool) -> bool:
	if _collapsed.has(key):
		return bool(_collapsed[key])
	if _bulk == "open":
		return false
	if _bulk == "closed":
		return true
	return collapsed_default


## «Развернуть всё» / «Свернуть всё»: сбросить запомненное и задать всем одно состояние.
func expand_all(open: bool) -> void:
	_collapsed.clear()
	_bulk = "open" if open else "closed"
	_save_ui_state()
	_refresh_page()


func _load_ui_state() -> void:
	if not FileAccess.file_exists(ui_state_path):
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(ui_state_path))
	if d is Dictionary:
		_collapsed = ((d as Dictionary).get("collapsed", {}) as Dictionary).duplicate()
		_bulk = String((d as Dictionary).get("bulk", ""))


func _save_ui_state() -> void:
	var f := FileAccess.open(ui_state_path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify({"collapsed": _collapsed, "bulk": _bulk}))


## События раздела каталога, прошедшие поиск и фильтр (порядок — как в файле).
func _cat_events(cat: String, q: String) -> Array[String]:
	var out: Array[String] = []
	for e in sounds:
		if String(e.cat) == cat and _passes(e, status_of(String(e.id)), q):
			out.append(String(e.id))
	return out


func _ids_info(ids: Array) -> String:
	var rec := 0
	var silent := 0
	for id in ids:
		var st := status_of(String(id))
		if int(st.rec) + int(st.linked) > 0:
			rec += 1
		elif _is_silent(st):
			silent += 1
	return "событий %d · с записями %d%s" % [ids.size(), rec, " · тишина %d" % silent if silent > 0 else ""]


## Событие вызывается игрой, но звучать нечему: ни своих, ни назначенных, ни системного звука.
func _is_silent(st: Dictionary) -> bool:
	return bool(st.wired) and int(st.rec) + int(st.linked) + int(st.fallback_rec) == 0 and not bool(st.synth)


## Раздел каталога: подгруппы (поле group) — свои сворачиваемые блоки с карточками.
func _fill_cat(body: VBoxContainer, cat: String, ids: Array, level: int, force_open: bool) -> void:
	var groups: Dictionary = {}
	for id in ids:
		var g := String((by_id[id] as Dictionary).get("group", ""))
		if not groups.has(g):
			groups[g] = []
		(groups[g] as Array).append(String(id))
	for g in groups:
		var list: Array = groups[g]
		if String(g) == "":
			body.add_child(_card_flow(list))
			continue
		_section(body, "grp:%s/%s" % [cat, g], String(g), _ids_info(list), level, false,
			func(b: VBoxContainer) -> void: b.add_child(_card_flow(list)), force_open)


func _card_flow(ids: Array) -> HFlowContainer:
	var flow := HFlowContainer.new()
	flow.add_theme_constant_override("h_separation", 8)
	flow.add_theme_constant_override("v_separation", 8)
	for id in ids:
		flow.add_child(_event_card(String(id)))
	return flow


## Карточка события: название, чем звучит сейчас, когда звучит; щелчок — событие справа.
func _event_card(id: String) -> PanelContainer:
	var e: Dictionary = by_id[id]
	var st := status_of(id)
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 262
	card.mouse_filter = Control.MOUSE_FILTER_STOP
	card.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	card.tooltip_text = "%s\nID: %s" % [String(e.when), id]
	card.set_meta("event", id)
	_style_card(card, id == _current, _status_color(st))
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 3)
	box.mouse_filter = Control.MOUSE_FILTER_IGNORE
	card.add_child(box)
	var title := _label(String(e.name), 15, Color(0.94, 0.93, 0.9))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.custom_minimum_size.x = 240
	box.add_child(title)
	box.add_child(_label(_card_state(st), 13, _status_color(st)))
	var when := _label(String(e.when), 12, COL_DIM)
	when.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	when.custom_minimum_size.x = 240
	when.max_lines_visible = 2
	box.add_child(when)
	var play := _button("▶ как в игре" if bool(st.wired) else "▶ послушать", func() -> void: _quick_play(id))
	play.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	box.add_child(play)
	card.gui_input.connect(func(ev: InputEvent) -> void:
		var mb := ev as InputEventMouseButton
		if mb and mb.pressed and mb.button_index == MOUSE_BUTTON_LEFT:
			select_event(id))
	if not _cards.has(id):
		_cards[id] = []
	(_cards[id] as Array).append(card)
	return card


func _style_card(card: PanelContainer, selected: bool, color: Color) -> void:
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.15, 0.135, 0.1) if selected else Color(0.085, 0.09, 0.1)
	sb.border_color = Color(1.0, 0.86, 0.6) if selected else color.darkened(0.5)
	sb.set_border_width_all(2 if selected else 1)
	sb.set_corner_radius_all(4)
	sb.set_content_margin_all(8)
	card.add_theme_stylebox_override("panel", sb)


## Короткое «чем звучит сейчас» для карточки.
func _card_state(st: Dictionary) -> String:
	var t := ""
	if int(st.rec) + int(st.linked) > 0:
		if int(st.linked) == 0:
			t = "▶ своих записей: %d" % int(st.rec)
		elif int(st.rec) == 0:
			t = "▶ назначено записей: %d" % int(st.linked)
		else:
			t = "▶ записей: %d + назначено %d" % [int(st.rec), int(st.linked)]
		if not bool(st.wired):
			t += " · в коде не вызывается"
	elif int(st.fallback_rec) > 0:
		t = "▷ звучит как «%s»" % String(st.fallback_name).get_slice(" — ", 0)
	elif bool(st.synth):
		t = "≈ синтез"
	elif not bool(st.wired):
		t = "◇ в коде ещё не вызывается"
	else:
		t = "○ тишина"
	if int(st.new) > 0:
		t += " · новых: %d" % int(st.new)
	if int(st.pending) > 0:
		t += " · одобрено, не добавлено: %d" % int(st.pending)
	return t


## ▶ на карточке: подключённое — как в игре, иначе случайный из записей и одобренных кандидатов.
func _quick_play(id: String) -> void:
	if bool(status_of(id).wired):
		_preview_game(id)
		return
	var all := streams_of(id)
	if all.is_empty():
		_status.text = "У «%s» пока нет ни записей, ни одобренных кандидатов." % String(by_id[id].name)
		return
	play_stream(all[_rng.randi_range(0, all.size() - 1)], true, _is_loop(id))


## Выбрать событие: подсветить карточку, показать его справа.
func select_event(id: String) -> void:
	if not by_id.has(id):
		return
	var prev := _current
	_current = id
	for pid in [prev, id]:
		for card in _cards.get(pid, []):
			if is_instance_valid(card):
				_style_card(card as PanelContainer, pid == id, _status_color(status_of(String(pid))))
	if _tabs:
		_tabs.current_tab = 0
	_refresh_details()
	_refresh_inbox_cards()


func _select_weapon_sound(id: String) -> void:
	select_event(id)


# ---------------------------------------------------------------- оружие

## Стволы по классам (порядок CLASS_ORDER), прошедшие поиск и фильтр.
func _weapon_ids_by_class(q: String) -> Dictionary:
	var by_class: Dictionary = {}
	for wid in WeaponDb.weapon_ids():
		var w := WeaponDb.weapon(String(wid))
		var item: Dictionary = WeaponDb.items().get(wid, {})
		var haystack := "%s %s %s %s" % [wid, String(item.get("name", "")), String(WeaponDb.CLASS_NAMES.get(String(w.get("class", "")), "")), WeaponDb.caliber_name(String(w.get("caliber", "")))]
		if q != "" and not haystack.to_lower().contains(q):
			continue
		if _filter.selected != 0:
			var any := false
			for e in WeaponDb.weapon_sound_layout(String(wid)):
				if bool(e.get("shared", false)) or not bool(e.get("available", true)) or not by_id.has(String(e.id)):
					continue
				if _passes(by_id[String(e.id)], status_of(String(e.id)), ""):
					any = true
					break
			if not any:
				continue
		var cls := String(w.get("class", ""))
		if not by_class.has(cls):
			by_class[cls] = []
		(by_class[cls] as Array).append(String(wid))
	var out: Dictionary = {}
	for cls in CLASS_ORDER:
		if by_class.has(cls):
			out[cls] = by_class[cls]
	for cls in by_class:
		if not out.has(cls):
			out[cls] = by_class[cls]
	return out


func _fill_weapons(body: VBoxContainer, q: String, guns: Dictionary, shared: Dictionary) -> void:
	_weapon_summary = _label(_weapon_summary_text(), 14, Color(0.94, 0.86, 0.62))
	_weapon_summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_child(_weapon_summary)
	var narrowing := q != "" or _filter.selected != 0
	for cls in guns:
		var list: Array = guns[cls]
		var c := String(cls)
		_section(body, "class:" + c, String(CLASS_TITLES.get(c, WeaponDb.CLASS_NAMES.get(c, c))), "моделей %d" % list.size(), 1, true,
			func(b: VBoxContainer) -> void: _fill_weapon_class(b, list), q != "")
	# действия по семействам механики: магазин, затвор, спуск у АК — свои, у AR — свои
	var fam_ids: Array = shared[FAMILY_CAT]
	if not narrowing or not fam_ids.is_empty():
		_section(body, "families", "Магазин, затвор, спуск — по семействам механики", _ids_info(fam_ids), 1, true,
			func(b: VBoxContainer) -> void: _fill_families(b, fam_ids, narrowing), narrowing)
	for c in WEAPON_CATS:
		var ids: Array = shared[c]
		if narrowing and ids.is_empty():
			continue
		var cat := String(c)
		var title := "Выстрел — общие и запасные наборы" if cat == WEAPON_CATS[0] else "Обращение с оружием — общее для всех стволов"
		_section(body, "cat:" + cat, title, _ids_info(ids), 1, true,
			func(b: VBoxContainer) -> void: _fill_cat(b, cat, ids, 2, narrowing), narrowing)


## События семейств, прошедшие поиск и фильтр.
func _family_events(q: String) -> Array[String]:
	var out: Array[String] = []
	for e in family_sounds:
		var st := status_of(String(e.id))
		# поиск по семейству («АК») показывает все его действия
		if _passes(e, st, "") and (q == "" or String(e.group).to_lower().contains(q) or _passes(e, st, q)):
			out.append(String(e.id))
	return out


## Семейство — подраздел: какие стволы в нём и карточки его действий. Своя запись ствола
## перекрывает семейство (в карточке ствола — «Магазин, затвор, спуск»).
func _fill_families(body: VBoxContainer, ids: Array, force_open: bool) -> void:
	body.add_child(_wrap_label("Без своих записей ствол звучит своим семейством, семейство без записей — общим звуком "
		+ "(раздел «Обращение с оружием — общее»). Ствол, который звучит иначе, получает свою запись в своей карточке.", 13, COL_DIM))
	var by_fam: Dictionary = {}
	for id in ids:
		var fid := String((by_id[id] as Dictionary).family)
		if not by_fam.has(fid):
			by_fam[fid] = []
		(by_fam[fid] as Array).append(String(id))
	var fams := WeaponDb.sound_families()
	for fid in fams:
		if not by_fam.has(fid):
			continue
		var list: Array = by_fam[fid]
		var guns: Array[String] = []
		for wid in (fams[fid] as Dictionary).get("weapons", []):
			guns.append(String((WeaponDb.items().get(wid, {}) as Dictionary).get("name", wid)))
		var who := ", ".join(guns)
		_section(body, "fam:" + String(fid), WeaponDb.sound_family_name(String(fid)), _ids_info(list), 2, true,
			func(b: VBoxContainer) -> void:
				b.add_child(_wrap_label("Стволы: " + who, 13, COL_DIM))
				b.add_child(_card_flow(list)), force_open)


func _fill_weapon_class(body: VBoxContainer, list: Array) -> void:
	var flow := HFlowContainer.new()
	flow.add_theme_constant_override("h_separation", 10)
	flow.add_theme_constant_override("v_separation", 10)
	body.add_child(flow)
	for wid in list:
		flow.add_child(_weapon_card(String(wid), WeaponDb.items().get(wid, {}), WeaponDb.weapon(String(wid))))


func _weapon_summary_text() -> String:
	var totals := {"own": 0, "borrowed": 0, "silent": 0, "guns_own_shot": 0, "guns": 0}
	for wid in WeaponDb.weapon_ids():
		var tally := _weapon_tally(String(wid))
		totals.guns += 1
		for k in ["own", "borrowed", "silent"]:
			totals[k] = int(totals[k]) + int(tally[k])
		if bool(tally.own_shot):
			totals.guns_own_shot += 1
	return ("Свои выстрелы у %d из %d стволов. Звуков моделей: со своими записями %d, звучат чужим набором %d, тишина %d. "
		+ "В карточке ствола — только его собственные звуки; общее для всех стволов (магазин, затвор, спуск) — в разделе ниже.") % [
		int(totals.guns_own_shot), int(totals.guns), int(totals.own), int(totals.borrowed), int(totals.silent)]


## Карточки стволов на странице (в открытых разделах).
func weapon_cards() -> Array[Control]:
	var out: Array[Control] = []
	_collect_meta(_page, "weapon", out)
	return out


## Карточки событий на странице (в открытых разделах).
func event_cards() -> Array[Control]:
	var out: Array[Control] = []
	_collect_meta(_page, "event", out)
	return out


func _collect_meta(node: Node, key: String, out: Array[Control]) -> void:
	if node == null:
		return
	for c in node.get_children():
		if c.is_queued_for_deletion():
			continue
		if c.has_meta(key):
			out.append(c as Control)
		else:
			_collect_meta(c, key, out)


## Свои звуки модели по состоянию: свои записи / звучит чужим набором / тишина (слоты, которые
## игра зовёт и которые у этой конструкции есть).
func _weapon_tally(wid: String) -> Dictionary:
	var out := {"own": 0, "borrowed": 0, "silent": 0, "own_shot": false}
	for e in WeaponDb.weapon_sound_layout(wid):
		if bool(e.get("shared", false)) or bool(e.get("via_family", false)) or not bool(e.get("available", true)) or String(e.get("kind", "")) == "":
			continue
		var sid := String(e.id)
		if not by_id.has(sid):
			continue
		var st := status_of(sid)
		if int(st.rec) + int(st.linked) > 0:
			out.own += 1
			if String(e.slot) == "shot":
				out.own_shot = true
		elif int(st.fallback_rec) > 0 or bool(st.synth):
			out.borrowed += 1
		else:
			out.silent += 1
	return out


func _weapon_card(wid: String, item: Dictionary, w: Dictionary) -> PanelContainer:
	var card := PanelContainer.new()
	card.custom_minimum_size.x = 310
	card.set_meta("weapon", wid)
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.075, 0.078, 0.086)
	style.border_color = Color(0.32, 0.28, 0.19)
	style.set_border_width_all(1)
	style.set_corner_radius_all(4)
	style.set_content_margin_all(9)
	card.add_theme_stylebox_override("panel", style)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 5)
	card.add_child(box)
	var image_bg := PanelContainer.new()
	var image_style := StyleBoxFlat.new()
	image_style.bg_color = Color(0.29, 0.275, 0.25)
	image_style.set_corner_radius_all(3)
	image_bg.add_theme_stylebox_override("panel", image_style)
	box.add_child(image_bg)
	var icon := TextureRect.new()
	icon.custom_minimum_size.y = 100
	icon.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	var icon_path := "res://assets/icons/%s.png" % wid
	if ResourceLoader.exists(icon_path):
		icon.texture = load(icon_path) as Texture2D
		icon.tooltip_text = icon_path
	else:
		icon.tooltip_text = "Нет иконки: запусти tools/godot.cmd res://tools/icon_bake.tscn -- %s" % wid
	image_bg.add_child(icon)
	var title := _label(String(item.get("name", wid)), 17, Color(0.94, 0.93, 0.9))
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.custom_minimum_size.y = 42
	box.add_child(title)
	var meta := "%s · %s · %s" % [String(item.get("code", wid)), String(WeaponDb.CLASS_NAMES.get(String(w.get("class", "")), String(w.get("class", "")))), WeaponDb.caliber_name(String(w.get("caliber", "")))]
	box.add_child(_label(meta, 13, COL_DIM))
	var tally := _weapon_tally(wid)
	var total := int(tally.own) + int(tally.borrowed) + int(tally.silent)
	var progress := _label("своих записей: %d из %d%s" % [int(tally.own), total, "" if int(tally.silent) == 0 else " · тишина: %d" % int(tally.silent)],
		13, COL_REC if int(tally.own) == total else (COL_NONE if int(tally.silent) > 0 else COL_SYNTH))
	box.add_child(progress)
	var last_group := ""
	var fam_rows: Array[Dictionary] = []
	for e in WeaponDb.weapon_sound_layout(wid):
		if bool(e.get("shared", false)):
			continue
		# чего у этой конструкции нет (глушитель, ручной цикл…) — не показываем, это шум
		if not bool(e.get("available", true)):
			continue
		var sound_id := String(e.id)
		if sound_id == "" or not by_id.has(sound_id):
			continue
		if bool(e.get("via_family", false)):
			fam_rows.append(e)
			continue
		var group := String(e.group)
		if group != last_group:
			last_group = group
			box.add_child(_label(group.to_upper(), 12, Color(0.78, 0.67, 0.45)))
		box.add_child(_weapon_row(wid, item, e))
	if not fam_rows.is_empty():
		_weapon_family_rows(box, wid, item, fam_rows)
	return card


## Магазин, затвор, спуск модели — свёрнуто: по умолчанию звучат семейством.
func _weapon_family_rows(box: VBoxContainer, wid: String, item: Dictionary, rows: Array[Dictionary]) -> void:
	var own := 0
	for e in rows:
		var st := status_of(String(e.id))
		if int(st.rec) + int(st.linked) > 0:
			own += 1
	var fid := WeaponDb.sound_family(wid)
	var fam := ("как «%s»" % WeaponDb.sound_family_name(fid)) if fid != "" else "общий звук"
	var list := VBoxContainer.new()
	list.add_theme_constant_override("separation", 5)
	list.visible = bool(_collapsed.get("wfam:" + wid, true)) == false
	var caption := func(o: bool) -> String:
		return "%s МАГАЗИН, ЗАТВОР, СПУСК · %s · своих %d из %d" % ["▾" if o else "▸", fam, own, rows.size()]
	var toggle := Button.new()
	toggle.flat = true
	toggle.alignment = HORIZONTAL_ALIGNMENT_LEFT
	toggle.add_theme_font_size_override("font_size", 12)
	toggle.add_theme_color_override("font_color", Color(0.78, 0.67, 0.45))
	toggle.text = caption.call(list.visible)
	toggle.tooltip_text = "Без своей записи модель звучит семейством; своя запись перекрывает семейство только у этой модели."
	toggle.pressed.connect(func() -> void:
		list.visible = not list.visible
		_collapsed["wfam:" + wid] = not list.visible
		toggle.text = caption.call(list.visible)
		_save_ui_state())
	box.add_child(toggle)
	box.add_child(list)
	for e in rows:
		list.add_child(_weapon_row(wid, item, e))


func _weapon_row(wid: String, item: Dictionary, e: Dictionary) -> Button:
	var sound_id := String(e.id)
	var st := status_of(sound_id)
	var row_name := String(e.get("name", "")).trim_prefix(String(item.get("name", wid)) + " — ")
	var button := _button(_weapon_sound_button_text(row_name, st),
		func() -> void: _select_weapon_sound(sound_id))
	button.alignment = HORIZONTAL_ALIGNMENT_LEFT
	button.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	button.custom_minimum_size.y = 31
	button.add_theme_color_override("font_color", _status_color(st))
	button.tooltip_text = "%s\n%s\nID: %s\nФайлы: assets/audio/%sNN" % [String(e.when), _status_text(st), sound_id, String(e.file)]
	return button


func _weapon_sound_button_text(name: String, st: Dictionary) -> String:
	if int(st.rec) + int(st.linked) > 0:
		return "▶ %s  ·  %d зап." % [name, int(st.rec) + int(st.linked)]
	if int(st.fallback_rec) > 0:
		# чем звучит сейчас: короткое имя набора-замены («Пистолет 9×18 / 9×19»)
		var like := String(st.fallback_name).get_slice(" — ", 0)
		return "▷ %s  ·  как «%s»" % [name, like] if like != "" else "▷ %s  ·  общий набор" % name
	if not bool(st.wired):
		return "◇ %s  ·  ещё не в коде" % name
	if bool(st.synth):
		return "≈ %s  ·  синтез" % name
	return "○ %s  ·  тишина" % name


func _refresh_all() -> void:
	if _page == null:
		return
	if _tabs != null and _tabs.get_tab_count() > 1:
		_tabs.set_tab_title(1, "Входящие (%d)" % files.size())
	_refresh_page()
	_refresh_details()
	_refresh_new_list()


func _status_text(st: Dictionary) -> String:
	var t := "%d зап." % (int(st.rec) + int(st.linked)) if int(st.rec) + int(st.linked) > 0 else ("синтез" if bool(st.synth) else "нет записи")
	if int(st.rec) + int(st.linked) == 0 and int(st.fallback_rec) > 0:
		t = "общий набор: %d" % int(st.fallback_rec)
	if bool(st.absent):
		t = "в игре нет"
	elif not bool(st.wired):
		t += " · не подключён"
	if int(st.linked) > 0:
		t += " · назначено %d" % int(st.linked)
	if int(st.disabled) > 0:
		t += " · выкл. %d" % int(st.disabled)
	if int(st.pending) > 0:
		t += " · одобрено, НЕ добавлено: %d" % int(st.pending)
	if int(st.try) > 0:
		t += " · +%d" % int(st.try)
	return t


func _status_color(st: Dictionary) -> Color:
	if int(st.new) > 0 or int(st.pending) > 0:
		return COL_NEW
	if int(st.rec) + int(st.linked) > 0:
		return COL_REC
	return COL_SYNTH if bool(st.synth) or int(st.fallback_rec) > 0 else COL_NONE


func _passes(e: Dictionary, st: Dictionary, q: String) -> bool:
	if q != "" and not (String(e.name).to_lower().contains(q) or String(e.id).contains(q) or String(e.file).contains(q)
			or String(e.get("group", "")).to_lower().contains(q)):
		return false
	match _filter.selected:
		1:
			return int(st.rec) + int(st.linked) == 0
		2:
			return int(st.rec) + int(st.linked) == 0 and bool(st.synth)
		3:
			return not bool(st.wired)
		4:
			return int(st.try) > 0
		5:
			return int(e.prio) == 1
		6:
			return int(st.rec) + int(st.linked) > 0
		7:
			return bool(st.absent)
		8:
			return int(st.linked) > 0 or bool(st.no_synth) or bool(st.no_fallback)
	return true


# ---------------------------------------------------------------- выбранное событие

## Путь события на странице: «Оружие › Пистолеты › ПМ» или «Раздел › подгруппа».
func _event_path(e: Dictionary) -> String:
	if e.has("family") and not e.has("weapon"):
		return "Оружие › семейство «%s»" % WeaponDb.sound_family_name(String(e.family))
	if e.has("weapon"):
		var w := WeaponDb.weapon(String(e.weapon))
		var item: Dictionary = WeaponDb.items().get(String(e.weapon), {})
		return "Оружие › %s › %s" % [String(WeaponDb.CLASS_NAMES.get(String(w.get("class", "")), "")), String(item.get("name", e.weapon))]
	var cat := String(e.get("cat", ""))
	var head := ("Оружие › " + ("выстрел, общее" if cat == WEAPON_CATS[0] else "обращение, общее")) if cat in WEAPON_CATS else cat
	var group := String(e.get("group", ""))
	return head + (" › " + group if group != "" else "")


func _wrap_label(text: String, size: int, color: Color) -> Label:
	var l := _label(text, size, color)
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	return l


func _heading(text: String) -> Label:
	var l := _label(text, 16, Color(1.0, 0.86, 0.6))
	l.add_theme_constant_override("line_spacing", 2)
	return l


func _verdict(e: Dictionary, st: Dictionary) -> String:
	var kind := String(e.kind)
	if kind == "":
		return "◇ В коде это событие ещё не вызывается. Записи можно подготовить заранее — зазвучат, когда механика его позовёт."
	if kind.begins_with("loop:"):
		return "Фоновый луп: %s." % ("звучит запись" if int(st.rec) > 0 else "звучит синтез")
	var own := int(st.rec) + int(st.linked)
	if own > 0:
		return "✓ В игре: случайная из %d записей (своих %d, назначенных %d)." % [own, int(st.rec), int(st.linked)]
	if int(st.fallback_rec) > 0:
		return "▷ Своих записей нет — звучит запасной набор «%s» (%d зап.)." % [String(st.fallback_name), int(st.fallback_rec)]
	if Audio.kind_layer(kind) != "":
		return "▷ Своих записей слоя нет — на этой дистанции звучат соседние слои."
	if bool(st.synth):
		return "≈ Своих записей нет — звучит синтез."
	return "○ В игре тишина: своих записей нет, системный звук снят или отсутствует."


func _refresh_details() -> void:
	if _details == null:
		return
	for c in _details.get_children():
		_details.remove_child(c)
		c.queue_free()
	if not by_id.has(_current):
		_details.add_child(_wrap_label("Щёлкни карточку события слева.\n\nЗдесь будет: как оно звучит сейчас, свои записи, "
			+ "записи, назначенные из других наборов, и системный звук (запасной набор, синтез) — любой можно снять с события "
			+ "или вернуть. Одну запись проекта можно назначить сколько угодно событиям.\n\n"
			+ "Зелёный — звучат записи. Жёлтый — запасной набор или синтез. Красный — тишина. "
			+ "Голубой — во входящих есть непрослушанные кандидаты.", 16, COL_DIM))
		return
	var id := _current
	var e: Dictionary = by_id[id]
	var st := status_of(id)
	var kind := String(e.kind)
	_details.add_child(_wrap_label(String(e.name), 20, Color(1.0, 0.86, 0.6)))
	_details.add_child(_wrap_label(_event_path(e), 13, COL_DIM))
	_details.add_child(_wrap_label("Когда звучит: " + String(e.when), 15, Color(0.85, 0.86, 0.88)))
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 8)
	_details.add_child(bar)
	bar.add_child(_button("▶ как в игре", func() -> void: _preview_game(id)))
	bar.add_child(_button("▶ случайный вариант", func() -> void:
		var all := streams_of(id)
		if all.is_empty():
			_status.text = "Нет записей и одобренных кандидатов."
		else:
			play_stream(all[_rng.randi_range(0, all.size() - 1)], true, _is_loop(id))
			if _is_gun(id):
				play_tail()))
	if _is_gun(id):
		bar.add_child(_button("▶▶ очередь", func() -> void: play_burst(streams_of(id), int(_burst_n.value), _rpm.value)))
	if _is_gun(id) and kind != "":
		_details.add_child(_game_distance_bar(id))
	_details.add_child(_wrap_label(_verdict(e, st), 16, _status_color(st)))

	# свои записи: файлы набора события в assets/audio
	_details.add_child(HSeparator.new())
	_details.add_child(_heading("Свои записи · assets/audio/%sNN" % String(e.file)))
	var own := asset_files(String(e.file))
	if own.is_empty():
		_details.add_child(_wrap_label("Пока нет. Добавь из входящих (вкладка «Входящие») или назначь готовую запись проекта ниже.", 14, COL_DIM))
	for path in own:
		_details.add_child(_asset_row(id, _asset_rel(path), true))

	# назначенные из других наборов
	_details.add_child(HSeparator.new())
	_details.add_child(_heading("Назначены из других наборов"))
	var linked: Array = links.get(id, [])
	if linked.is_empty():
		_details.add_child(_wrap_label("Нет. Любую запись проекта можно назначить этому событию — она останется и в своём наборе.", 14, COL_DIM))
	for rel in linked:
		_details.add_child(_asset_row(id, String(rel), false))
	var add := _button("+ Назначить запись из проекта…", func() -> void: _open_asset_picker(id))
	add.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	_details.add_child(add)

	# системный звук — что играет, пока своих записей нет; любой можно снять
	if kind != "" and not kind.begins_with("loop:") and Audio.kind_layer(kind) == "":
		_details.add_child(HSeparator.new())
		_details.add_child(_heading("Системный звук — когда своих записей нет"))
		_system_rows(id, e, st)
	elif Audio.kind_layer(kind) != "":
		_details.add_child(_wrap_label(("Слой дистанции (%s): пока своих записей нет, тут звучат соседние слои этого "
			+ "ствола или тот же слой общего набора. «Свой выстрел» берётся только у того набора, что звучит вблизи.")
			% _distance_name(Audio.layer_at_m(Audio.kind_layer(kind))), 14, COL_DIM))

	# кандидаты из входящих
	_details.add_child(HSeparator.new())
	var mine: Array[String] = []
	for rel in files:
		if assigned_id(rel) == id:
			mine.append(rel)
	_details.add_child(_wrap_label(("Кандидаты из входящих (%d). Прослушай ▶ и отметь «Одобрен к добавлению» — кандидат сразу "
		+ "участвует в «случайном варианте» и очереди; «Добавить одобренные в игру» наверху скопирует его в assets/audio.") % mine.size(), 15, COL_NEW))
	if not mine.is_empty():
		_details.add_child(_wrap_label(LICENSE_HELP, 13, COL_DIM))
	if mine.size() > 1:
		var bulk := HBoxContainer.new()
		bulk.add_theme_constant_override("separation", 8)
		bulk.add_child(_button("Одобрить все (%d)" % mine.size(), func() -> void: _approve_all(mine, true)))
		bulk.add_child(_button("Снять все", func() -> void: _approve_all(mine, false)))
		_details.add_child(bulk)
	for rel in mine:
		_details.add_child(_file_row(rel, false))

	_details.add_child(HSeparator.new())
	_details.add_child(_wrap_label(("ID: %s · вид в коде: %s\nСейчас по каталогу: %s\nТип: %s · нужно вариантов: %d · важность: %s") % [
		id, kind if kind != "" else "—", String(e.get("now", "")),
		String(TYPE_NAMES.get(String(e.get("type", "")), String(e.get("type", "")))), int(e.get("variants", 1)),
		String(PRIO_NAMES.get(int(e.get("prio", 3)), ""))], 13, COL_DIM))


## «Как в игре» по дистанции: выстрел события на каждом расстоянии, пройти все подряд, очередь на
## выбранном (последнем нажатом) расстоянии — слои сменяются плавно, хвосты очереди внахлёст.
func _game_distance_bar(id: String) -> VBoxContainer:
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 4)
	box.add_child(_wrap_label("Как в игре по дистанции (с одобренными кандидатами; дальний звук приходит позже — 343 м/с):", 14, COL_DIM))
	var row := HFlowContainer.new()
	row.add_theme_constant_override("h_separation", 6)
	row.add_theme_constant_override("v_separation", 6)
	box.add_child(row)
	for d in GAME_DISTANCES:
		var dist := float(d)
		row.add_child(_button(_distance_name(dist) if dist < 1.0 else "%d м" % int(dist), func() -> void:
			_game_dist = dist
			stop_all()
			play_game_at(id, dist)
			_status.text = "Как в игре: %s" % _distance_name(dist)))
	var row2 := HBoxContainer.new()
	row2.add_theme_constant_override("separation", 8)
	box.add_child(row2)
	row2.add_child(_button("▶ пройти все дистанции", func() -> void:
		stop_all()
		play_game_walk(id)))
	row2.add_child(_button("▶▶ очередь как в игре", func() -> void:
		stop_all()
		_status.text = "Очередь как в игре: %s, %d выстр., %d/мин" % [_distance_name(_game_dist), int(_burst_n.value), int(_rpm.value)]
		play_game_burst(id, _game_dist, int(_burst_n.value), _rpm.value)))
	return box


## Отметить «Одобрен к добавлению» у всех кандидатов события (или снять).
func _approve_all(rels: Array[String], on: bool) -> void:
	for rel in rels:
		var s := sel(rel)
		if String(s.get("moved", "")) != "":
			continue
		s.use = on
		s.seen = true
	save_selection()
	_refresh_page()
	_refresh_details()
	_status.text = ("Одобрено %d — «как в игре» уже слышит их; в игру — шагом 4." % rels.size()) if on else "Кандидаты сняты с добавления."


## Строка записи в событии: ▶, имя, где ещё звучит; своя — «в игре» (везде), «Ещё событиям…»,
## удалить файл; назначенная — «Ещё событиям…», «Снять с события».
func _asset_row(id: String, rel: String, own: bool) -> HBoxContainer:
	var path := assets_dir.path_join(rel)
	var exists := FileAccess.file_exists(path)
	var enabled := asset_enabled(path)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	var play := _button("▶", func() -> void:
		play_stream(load_stream(path), true, _is_loop(id))
		if _is_gun(id):
			play_tail())
	play.disabled = not exists
	row.add_child(play)
	var others: Array[String] = []
	for ev in linked_events(rel):
		if ev != id:
			others.append(String((by_id.get(ev, {}) as Dictionary).get("name", ev)))
	var owner := owner_of_asset(rel)
	var text := rel.get_file()
	if not own:
		text += "  ·  из «%s»" % String((by_id.get(owner, {}) as Dictionary).get("name", rel.get_base_dir())) if owner != "" else "  ·  " + rel.get_base_dir()
	if not others.is_empty():
		text += "  ·  ещё в %d соб." % others.size()
	if not exists:
		text += "  (файла нет)"
	var label := _label(text, 14, (Color(0.85, 0.86, 0.88) if enabled else COL_DIM) if exists else COL_NONE)
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.mouse_filter = Control.MOUSE_FILTER_PASS
	label.tooltip_text = "assets/audio/%s%s" % [rel, ("\nЕщё звучит в: " + ", ".join(others)) if not others.is_empty() else ""]
	row.add_child(label)
	if own:
		var use_in_game := CheckButton.new()
		use_in_game.text = "в игре"
		use_in_game.button_pressed = enabled
		use_in_game.tooltip_text = ("Участвует в случайном выборе — везде, где запись звучит" if enabled
			else "Выключена во всех событиях; файл сохранён. Включи, чтобы вернуть.")
		use_in_game.toggled.connect(func(on: bool) -> void: set_asset_enabled(path, on))
		row.add_child(use_in_game)
	var more := _button("Ещё событиям…", func() -> void: _open_event_picker(rel))
	more.tooltip_text = "Назначить эту запись другим событиям (одна запись — сколько угодно событий)"
	more.disabled = not exists
	row.add_child(more)
	if own:
		var delete_button := _button("Удалить файл", func() -> void: _ask_delete_asset(rel))
		delete_button.modulate = Color(1.0, 0.68, 0.68)
		delete_button.tooltip_text = "Удалить файл навсегда: .import, запись отбора, строку CREDITS и назначения в других событиях"
		row.add_child(delete_button)
	else:
		var off := _button("Снять с события", func() -> void: unlink_asset(rel, id))
		off.tooltip_text = "Запись перестанет звучать в этом событии; файл и другие события не тронуты"
		row.add_child(off)
	return row


## Запасной набор и синтез события: прослушать, снять с события, вернуть.
func _system_rows(id: String, e: Dictionary, st: Dictionary) -> void:
	var kind := String(e.kind)
	var has_own := int(st.rec) + int(st.linked) > 0
	var any := false
	var fb := _event_for_ref(String(e.get("fallback", "")))
	if not fb.is_empty() and String(fb.id) != id:
		any = true
		var fid := String(fb.id)
		var off := is_removed(id, "fallback")
		var fb_streams := streams_of(fid, true)
		var text := "Запасной набор «%s» · записей %d" % [String(fb.name), fb_streams.size()]
		if off:
			text = "Запасной набор «%s» снят" % String(fb.name)
		elif has_own:
			text += " · сейчас не звучит: есть свои"
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		var play := _button("▶", func() -> void:
			if not fb_streams.is_empty():
				play_stream(fb_streams[_rng.randi_range(0, fb_streams.size() - 1)], true, _is_loop(id)))
		play.disabled = fb_streams.is_empty()
		row.add_child(play)
		var label := _label(text, 14, COL_DIM if off else COL_SYNTH)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		label.clip_text = true
		label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		label.mouse_filter = Control.MOUSE_FILTER_PASS
		label.tooltip_text = "Набор другого события, которым это событие звучит, пока у него нет своих записей."
		row.add_child(label)
		row.add_child(_button("Открыть набор", func() -> void: select_event(fid)))
		var toggle := _button("Вернуть" if off else "Убрать с события", func() -> void: set_removed(id, "fallback", not off))
		if not off:
			toggle.modulate = Color(1.0, 0.8, 0.7)
		row.add_child(toggle)
		_details.add_child(row)
	var synth := Audio.synth_stream(kind, is_removed(id, "fallback"))
	if synth != null:
		any = true
		var off := is_removed(id, "synth")
		var text := "Синтез — процедурный звук игры"
		if off:
			text = "Синтез снят"
		elif has_own or int(st.fallback_rec) > 0:
			text += " · сейчас не звучит: есть записи"
		var row := HBoxContainer.new()
		row.add_theme_constant_override("separation", 6)
		row.add_child(_button("▶", func() -> void: play_stream(synth, true, _is_loop(id))))
		var label := _label(text, 14, COL_DIM if off else COL_SYNTH)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(label)
		var toggle := _button("Вернуть" if off else "Убрать с события", func() -> void: set_removed(id, "synth", not off))
		if not off:
			toggle.modulate = Color(1.0, 0.8, 0.7)
		row.add_child(toggle)
		_details.add_child(row)
	if not any:
		_details.add_child(_wrap_label("Системного звука у события нет.", 14, COL_DIM))
	if _is_silent(st):
		_details.add_child(_wrap_label("Сейчас это событие в игре молчит.", 15, COL_NONE))


# ---------------------------------------------------------------- выбор: записи ↔ события

func _build_picker(layer: CanvasLayer) -> void:
	_picker = PopupPanel.new()
	layer.add_child(_picker)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 8)
	_picker.add_child(box)
	_picker_title = _wrap_label("", 18, Color(1.0, 0.86, 0.6))
	box.add_child(_picker_title)
	_picker_hint = _wrap_label("", 13, COL_DIM)
	box.add_child(_picker_hint)
	_picker_search = LineEdit.new()
	_picker_search.placeholder_text = "поиск"
	_picker_search.clear_button_enabled = true
	_picker_search.text_changed.connect(func(_q: String) -> void: _fill_picker())
	box.add_child(_picker_search)
	_picker_tree = Tree.new()
	_picker_tree.hide_root = true
	_picker_tree.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_picker_tree.custom_minimum_size.y = 440
	_picker_tree.add_theme_font_size_override("font_size", 14)
	_picker_tree.item_edited.connect(_on_picker_edited)
	_picker_tree.item_selected.connect(_on_picker_selected)
	box.add_child(_picker_tree)
	var bar := HBoxContainer.new()
	bar.add_theme_constant_override("separation", 8)
	box.add_child(bar)
	_picker_count = _label("", 14, COL_DIM)
	_picker_count.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bar.add_child(_picker_count)
	bar.add_child(_button("Применить", _apply_picker))
	bar.add_child(_button("Отмена", func() -> void: _picker.hide()))


## «Ещё событиям…»: отметить события, где эта запись тоже звучит.
func _open_event_picker(rel: String) -> void:
	_picker_mode = "events"
	_picker_key = rel
	_picker_checked.clear()
	for id in linked_events(rel):
		_picker_checked[id] = true
	var owner := owner_of_asset(rel)
	_picker_title.text = "Где ещё звучит «%s»" % rel.get_file()
	_picker_hint.text = ("Отметь события, в которых эта запись тоже должна звучать. Своё событие записи%s отмечено всегда. "
		+ "Снятая галочка — запись снята с события; файл остаётся.") % (" («%s»)" % String(by_id[owner].name) if by_id.has(owner) else "")
	_picker_search.text = ""
	_fill_picker()
	_picker.popup_centered(Vector2i(860, 720))


## «Назначить запись из проекта…»: отметить записи, которые звучат и в этом событии.
func _open_asset_picker(id: String) -> void:
	_picker_mode = "assets"
	_picker_key = id
	_picker_checked.clear()
	for rel in links.get(id, []):
		_picker_checked[String(rel)] = true
	_picker_title.text = "Записи для события «%s»" % String(by_id[id].name)
	_picker_hint.text = ("Щелчок по строке — прослушать. Отметь записи, которые должны звучать в этом событии вместе с его "
		+ "собственными. Запись остаётся и в своём наборе. Свои записи события здесь не показаны.")
	_picker_search.text = ""
	_fill_picker()
	_picker.popup_centered(Vector2i(860, 720))


func _fill_picker() -> void:
	_picker_tree.clear()
	var root := _picker_tree.create_item()
	var q := _picker_search.text.strip_edges().to_lower()
	var heads: Dictionary = {}
	if _picker_mode == "assets":
		for rel in all_assets():
			var owner := owner_of_asset(rel)
			if owner == _picker_key:
				continue
			var owner_name := String((by_id.get(owner, {}) as Dictionary).get("name", ""))
			if q != "" and not (rel.to_lower().contains(q) or owner_name.to_lower().contains(q)):
				continue
			var it := _picker_item(heads, root, rel.get_base_dir(), q)
			it.set_text(0, rel.get_file() + ("   ·   " + owner_name if owner_name != "" else "")
				+ ("   (выключена)" if not asset_enabled(assets_dir.path_join(rel)) else ""))
			it.set_metadata(0, rel)
			it.set_checked(0, bool(_picker_checked.get(rel, false)))
			if it.is_checked(0):
				it.get_parent().collapsed = false
	else:
		var owner := owner_of_asset(_picker_key)
		var order: Array[String] = []
		for e in sounds:
			order.append(String(e.id))
		for e in family_sounds:
			order.append(String(e.id))
		for e in weapon_sounds:
			order.append(String(e.id))
		for id in order:
			var e: Dictionary = by_id[id]
			var where := _event_path(e)
			if q != "" and not (String(e.name).to_lower().contains(q) or id.contains(q) or where.to_lower().contains(q)):
				continue
			var it := _picker_item(heads, root, where, q)
			var mine := id == owner
			it.set_text(0, String(e.name) + ("   (свой набор записи)" if mine else ""))
			it.set_metadata(0, id)
			it.set_checked(0, mine or bool(_picker_checked.get(id, false)))
			it.set_editable(0, not mine)
			if it.is_checked(0):
				it.get_parent().collapsed = false
	_picker_count_update()


## Строка с галочкой под заголовком-группой (группы свёрнуты, пока нет поиска).
func _picker_item(heads: Dictionary, root: TreeItem, group: String, q: String) -> TreeItem:
	if not heads.has(group):
		var h := _picker_tree.create_item(root)
		h.set_text(0, group)
		h.set_selectable(0, false)
		h.set_custom_color(0, Color(1.0, 0.86, 0.6))
		h.collapsed = q == ""
		heads[group] = h
	var it := _picker_tree.create_item(heads[group] as TreeItem)
	it.set_cell_mode(0, TreeItem.CELL_MODE_CHECK)
	it.set_editable(0, true)
	return it


func _on_picker_edited() -> void:
	var it := _picker_tree.get_edited()
	if it == null or it.get_metadata(0) == null:
		return
	_picker_checked[String(it.get_metadata(0))] = it.is_checked(0)
	_picker_count_update()


func _on_picker_selected() -> void:
	var it := _picker_tree.get_selected()
	if _picker_mode != "assets" or it == null or it.get_metadata(0) == null:
		return
	play_stream(load_stream(assets_dir.path_join(String(it.get_metadata(0)))), true)


func _picker_count_update() -> void:
	var n := 0
	for k in _picker_checked:
		if bool(_picker_checked[k]):
			n += 1
	_picker_count.text = ("отмечено событий: %d" if _picker_mode == "events" else "отмечено записей: %d") % n


## Применить выбор: назначить отмеченное, снять то, с чего галочку убрали.
func _apply_picker() -> void:
	if _picker_mode == "events":
		apply_event_links(_picker_key, _picker_checked)
	else:
		var arr: Array[String] = []
		for rel in _picker_checked:
			if bool(_picker_checked[rel]) and owner_of_asset(String(rel)) != _picker_key:
				arr.append(String(rel))
		links[_picker_key] = arr
		_bench_changed()
	_picker.hide()
	_status.text = "Назначения сохранены в data/sound_active.json — игра слышит их сразу."


## Запись rel звучит ровно в отмеченных событиях (кроме своего — там она всегда).
func apply_event_links(rel: String, wanted: Dictionary) -> void:
	var owner := owner_of_asset(rel)
	for id in by_id:
		var arr: Array[String] = []
		arr.assign(links.get(id, []))
		var want: bool = bool(wanted.get(id, false)) and String(id) != owner
		if want and not rel in arr:
			arr.append(rel)
		elif not want and rel in arr:
			arr.erase(rel)
		else:
			continue
		links[id] = arr
	_bench_changed()


func _refresh_new_list() -> void:
	_refresh_inbox_tree()
	_refresh_inbox_cards()


func _refresh_inbox_tree() -> void:
	if _inbox_tree == null:
		return
	_building_inbox_tree = true
	_inbox_tree.clear()
	var root := _inbox_tree.create_item()
	root.set_metadata(0, "dir:")
	var folders: Dictionary = {"": root}
	var counts: Dictionary = {"": files.size()}
	for rel in files:
		var dir := ""
		var parts := String(rel).split("/")
		for i in range(parts.size() - 1):
			dir = String(parts[i]) if dir == "" else dir.path_join(String(parts[i]))
			counts[dir] = int(counts.get(dir, 0)) + 1
	for rel in files:
		var parent: TreeItem = root
		var dir := ""
		var parts := String(rel).split("/")
		for i in range(parts.size() - 1):
			dir = String(parts[i]) if dir == "" else dir.path_join(String(parts[i]))
			if not folders.has(dir):
				var folder := _inbox_tree.create_item(parent)
				folder.set_metadata(0, "dir:" + dir)
				folders[dir] = folder
			parent = folders[dir]
		var file_item := _inbox_tree.create_item(parent)
		file_item.set_metadata(0, "file:" + String(rel))
		var picked := sel(String(rel))
		var id := assigned_id(String(rel))
		var state := _incoming_state(String(rel))
		file_item.set_text(0, ("● " if not bool(picked.seen) else "") + String(rel).get_file())
		file_item.set_custom_color(0, COL_NEW if not bool(picked.seen) else Color(0.82, 0.83, 0.85))
		file_item.set_text(1, String(state.short))
		file_item.set_custom_color(1, state.color)
		file_item.set_tooltip_text(0, "%s%s" % [String(rel), "\nНазначен: " + String(by_id[id].name) if by_id.has(id) else "\nНе назначен"])
		file_item.set_tooltip_text(1, String(state.text))
		if _inbox_pick == "file:" + String(rel):
			file_item.select(0)
	root.set_text(0, "Все входящие (%d)" % files.size())
	for path in folders:
		if String(path) == "":
			continue
		var folder: TreeItem = folders[path]
		var short_name := String(path).get_file()
		if by_id.has(String(path)):
			short_name += " — " + String(by_id[String(path)].name)
		folder.set_text(0, "%s (%d)" % [short_name, int(counts.get(path, 0))])
		folder.set_tooltip_text(0, String(path))
		if _inbox_pick == "dir:" + String(path):
			folder.select(0)
	if _inbox_tree.get_selected() == null:
		_inbox_pick = "dir:"
		root.select(0)
	root.collapsed = false
	_building_inbox_tree = false


func _on_inbox_tree_selected() -> void:
	if _building_inbox_tree:
		return
	var item := _inbox_tree.get_selected()
	if item == null or item.get_metadata(0) == null:
		return
	_inbox_pick = String(item.get_metadata(0))
	_refresh_inbox_cards()


## Файлы выбранного узла дерева: один файл либо всё поддерево папки.
func inbox_files(pick: String = _inbox_pick) -> Array[String]:
	var out: Array[String] = []
	if pick.begins_with("file:"):
		var exact := pick.trim_prefix("file:")
		if files.has(exact):
			out.append(exact)
		return out
	var dir := pick.trim_prefix("dir:")
	for rel in files:
		if dir == "" or String(rel).begins_with(dir + "/"):
			out.append(String(rel))
	return out


func _refresh_inbox_cards() -> void:
	for c in _new_list.get_children():
		c.queue_free()
	var shown := inbox_files()
	var selected_path := _inbox_pick.trim_prefix("dir:").trim_prefix("file:")
	var selected_name := "все входящие" if selected_path == "" else selected_path
	var intro := _label("Выбрано: %s · %d файлов. Неназначенные сохраняют исходный путь; цель назначения — выбранная карточка слева." % [selected_name, shown.size()], 15, COL_DIM)
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_new_list.add_child(intro)
	if files.is_empty():
		var empty := _label("Входящих файлов пока нет. Нажми «Открыть папку» наверху и положи туда .ogg, .wav или .mp3.", 16, COL_DIM)
		empty.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		_new_list.add_child(empty)
		return
	var unassigned: Array[String] = []
	for rel in shown:
		if assigned_id(rel) == "":
			unassigned.append(rel)
	if _inbox_pick.begins_with("dir:") and _inbox_pick != "dir:" and not unassigned.is_empty() and by_id.has(_current):
		var batch: Array[String] = unassigned.duplicate()
		var target := _current
		var batch_button := _button("Назначить все неназначенные из этой папки → %s" % String(by_id[target].name),
			func() -> void: assign_many(batch, target))
		batch_button.tooltip_text = "%d файлов" % batch.size()
		_new_list.add_child(batch_button)
	for rel in shown:
		_new_list.add_child(_file_row(rel, true))


## Карточка кандидата: прослушивание, одобрение, назначение выбранному слева звуку, источник и
## точный итог — уже играет в игре или пока только подготовлен в библиотеке.
func _file_row(rel: String, show_assign: bool) -> PanelContainer:
	var s := sel(rel)
	var id := assigned_id(rel)
	var moved := String(s.moved) != ""
	var card := PanelContainer.new()
	var card_style := StyleBoxFlat.new()
	card_style.bg_color = Color(0.105, 0.11, 0.125)
	card_style.border_color = Color(0.25, 0.27, 0.3)
	card_style.set_border_width_all(1)
	card_style.corner_radius_top_left = 4
	card_style.corner_radius_top_right = 4
	card_style.corner_radius_bottom_left = 4
	card_style.corner_radius_bottom_right = 4
	card_style.set_content_margin_all(8)
	card.add_theme_stylebox_override("panel", card_style)
	var box := VBoxContainer.new()
	box.add_theme_constant_override("separation", 6)
	card.add_child(box)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	box.add_child(row)
	var dot := _label("●" if not bool(s.seen) else "  ", 16, COL_NEW)
	dot.tooltip_text = "новый — ещё не слушал"
	row.add_child(dot)
	var incoming_state := _incoming_state(rel)
	var state_label := _label(String(incoming_state.text), 14, incoming_state.color)
	state_label.tooltip_text = String(incoming_state.text)
	row.add_child(state_label)
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
	use.text = "Добавлен" if moved else "Одобрен к добавлению"
	use.button_pressed = bool(s.use)
	use.disabled = id == "" or moved
	use.tooltip_text = "Сначала назначь файл игровому звуку" if id == "" else \
		("Уже добавлен в проект" if moved else "Только отбор для шага 4; до копирования в assets/audio игра этот файл не использует")
	use.toggled.connect(func(v: bool) -> void:
		s.use = v
		s.seen = true
		dot.text = "  "
		save_selection()
		_refresh_page()
		if v:
			var issue := transfer_block_reason(rel)
			_status.text = ("Одобрено к добавлению, но ещё НЕ в игре: %s. Заполни карточку и нажми шаг 4." % issue) if issue != "" else \
				"Одобрено к добавлению, но ещё НЕ в игре. Нажми шаг 4 — «Добавить одобренные в игру»."
		else:
			_status.text = "Кандидат снят с добавления.")
	row.add_child(use)
	# удаление — на другом краю строки, подальше от ▶ (мимо не нажмёшь)
	var gap := Control.new()
	gap.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(gap)
	var delete_button := _button("Удалить навсегда", func() -> void: _ask_delete_incoming(rel))
	delete_button.modulate = Color(1.0, 0.68, 0.68)
	delete_button.tooltip_text = "Безвозвратно удалить этот кандидат и все его служебные записи"
	row.add_child(delete_button)
	var shown_path := rel if id == "" else rel.get_file()
	var name_row := HBoxContainer.new()
	name_row.add_theme_constant_override("separation", 8)
	box.add_child(name_row)
	var length := load_stream(path).get_length() if load_stream(path) else 0.0
	var fname := _label("Файл: %s%s" % [shown_path, "" if length <= 0.0 else "  ·  %.2f с" % length], 15, Color(0.85, 0.86, 0.88))
	fname.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fname.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	fname.tooltip_text = rel
	name_row.add_child(fname)
	var split_button := _button("✂ Разрезать по паузам", func() -> void: _open_split_popup(rel))
	split_button.tooltip_text = "В файле несколько вариантов подряд? Найти паузы и создать отдельный WAV для каждого"
	name_row.add_child(split_button)
	var origin := String(s.get("origin", rel))
	if origin != rel:
		var origin_label := _label("Исходник: %s" % origin, 13, COL_DIM)
		origin_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		box.add_child(origin_label)

	if show_assign:
		var assignment := HBoxContainer.new()
		assignment.add_theme_constant_override("separation", 8)
		box.add_child(assignment)
		var assigned_name := "не назначен"
		if id != "":
			assigned_name = String(by_id[id].name) if by_id.has(id) else "%s — нет в каталоге" % id
		var assigned_label := _label("Кому: %s" % assigned_name, 14, COL_DIM)
		assigned_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		assigned_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		assignment.add_child(assigned_label)
		if not moved:
			if by_id.has(_current) and _current != id:
				var assign_button := _button("Назначить выбранному", func() -> void: assign(rel, _current))
				assign_button.tooltip_text = String(by_id[_current].name)
				assignment.add_child(assign_button)
			elif _current == id and id != "":
				assignment.add_child(_label("✓ выбран", 14, COL_REC))
			elif not by_id.has(_current):
				assignment.add_child(_label("выбери цель слева", 14, COL_SYNTH))
			if id != "":
				assignment.add_child(_button("Снять", func() -> void: assign(rel, "")))

	var source_row := HBoxContainer.new()
	source_row.add_theme_constant_override("separation", 8)
	box.add_child(source_row)
	var source_label := _label("Источник / автор", 14, COL_DIM)
	source_label.custom_minimum_size.x = 125
	source_row.add_child(source_label)
	var src := LineEdit.new()
	src.placeholder_text = "например: Freesound · автор · ссылка; или название генератора"
	src.text = String(s.source)
	src.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	src.editable = not moved
	src.text_changed.connect(func(t: String) -> void: s.source = t)
	src.focus_exited.connect(save_selection)
	src.text_submitted.connect(func(_t: String) -> void: save_selection())
	source_row.add_child(src)
	var license := OptionButton.new()
	license.custom_minimum_size.x = 245
	_fill_license_options(license, _selected_license_key(s))
	license.disabled = moved
	license.item_selected.connect(func(index: int) -> void:
		s.license = String(_license_at(index).key)
		save_selection()
		var issue := transfer_block_reason(rel)
		_status.text = ("Право выбрано, но кандидат ещё НЕ в игре: %s." % issue) if issue != "" else \
			"Источник и право заполнены. Если звук одобрен, нажми шаг 4 — «Добавить одобренные в игру».")
	source_row.add_child(license)

	var result_text := ""
	var result_color := COL_DIM
	if moved:
		if by_id.has(id) and String(by_id[id].kind) != "":
			result_text = "✓ В проекте: assets/audio/%s · игра вызывает этот звук как «%s»." % [String(s.moved), String(by_id[id].kind)]
			result_color = COL_REC
		else:
			result_text = "✓ В проекте: assets/audio/%s · игровой вызов для этого события ещё не сделан." % String(s.moved)
			result_color = COL_SYNTH
	elif bool(s.use):
		var issue := transfer_block_reason(rel)
		if issue != "":
			result_text = "⚠ Одобрен к добавлению, но ещё НЕ в проекте: %s. После исправления нажми шаг 4." % issue
			result_color = COL_SYNTH
		elif by_id.has(id) and String(by_id[id].kind) != "":
			result_text = "Одобрен к добавлению, но ещё НЕ в проекте. Нажми шаг 4; затем игровой вид «%s» сразу начнёт использовать запись." % String(by_id[id].kind)
			result_color = COL_NEW
		else:
			result_text = "Одобрен к добавлению, но ещё НЕ в проекте; выбранный звук пока не вызывается игровым кодом."
			result_color = COL_SYNTH
	elif id == "":
		result_text = "Сначала назначь кандидата выбранному слева звуку."
	else:
		result_text = "Назначен. Прослушай вариант и отметь «Одобрен», если он подходит."
	var result := _label(result_text, 14, result_color)
	result.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	box.add_child(result)
	return card


func _incoming_state(rel: String) -> Dictionary:
	var id := assigned_id(rel)
	if id == "" or not by_id.has(id):
		return {"short": "не назначен", "text": "Не назначен игровому событию", "color": COL_DIM}
	var e: Dictionary = by_id[id]
	var picked := sel(rel)
	if bool(picked.use) and String(e.kind) != "":
		return {"short": "✓ одобрен", "text": "✓ Одобрен для: %s" % String(e.name), "color": COL_REC}
	if bool(picked.use):
		return {"short": "одобрен", "text": "Одобрен для неподключённого события: %s" % String(e.name), "color": COL_SYNTH}
	return {"short": "→ назначен", "text": "Назначен: %s" % String(e.name), "color": COL_NEW}


func _open_split_popup(rel: String) -> void:
	_split_rel = rel
	_split_analysis.clear()
	_split_path_label.text = "Файл: %s" % rel
	_split_result_label.text = "Ищу отдельные части…"
	_split_result_label.add_theme_color_override("font_color", COL_DIM)
	_split_create_button.disabled = true
	_split_popup.popup_centered(Vector2i(760, 510))
	_analyze_split_popup.call_deferred()


func _split_settings_changed() -> void:
	if _split_popup == null or not _split_popup.visible:
		return
	_split_analysis.clear()
	_split_create_button.disabled = true
	_split_result_label.text = "Параметры изменены. Нажми «Найти части»."
	_split_result_label.add_theme_color_override("font_color", COL_DIM)


func _analyze_split_popup() -> void:
	if _split_rel == "":
		return
	_split_result_label.text = "Анализирую файл…"
	_split_create_button.disabled = true
	_split_analysis = analyze_incoming(_split_rel, _split_threshold.value, _split_silence.value,
		_split_padding.value, _split_min_clip.value)
	if not bool(_split_analysis.get("ok", false)):
		_split_result_label.text = "Не удалось проанализировать: %s" % String(_split_analysis.get("error", "неизвестная ошибка"))
		_split_result_label.add_theme_color_override("font_color", COL_NONE)
		return
	var segments: Array = _split_analysis.get("segments", [])
	var lines: Array[String] = []
	for index in mini(segments.size(), 12):
		var segment := segments[index] as Dictionary
		lines.append("%d. %.2f–%.2f с · %.2f с" % [index + 1, float(segment.start), float(segment.end), float(segment.duration)])
	if segments.size() > 12:
		lines.append("…и ещё %d" % (segments.size() - 12))
	var header := "Найдено частей: %d из файла %.2f с." % [segments.size(), float(_split_analysis.get("duration", 0.0))]
	if segments.size() < 2:
		header += " Нужно минимум две: подними порог тишины или уменьши минимальную паузу."
	_split_result_label.text = header + ("\n" + "\n".join(lines) if not lines.is_empty() else "")
	_split_result_label.add_theme_color_override("font_color", COL_REC if segments.size() >= 2 else COL_SYNTH)
	_split_create_button.disabled = segments.size() < 2


func _create_split_popup() -> void:
	if _split_rel == "":
		return
	_split_create_button.disabled = true
	_split_result_label.text = "Создаю отдельные WAV…"
	var source_rel := _split_rel
	var source_was_added := String(sel(source_rel).get("moved", "")) != ""
	var result := split_incoming(source_rel, _split_threshold.value, _split_silence.value,
		_split_padding.value, _split_min_clip.value, _split_approve.button_pressed,
		_split_remove_source.button_pressed)
	if not bool(result.get("ok", false)):
		_split_result_label.text = "Не удалось разрезать: %s" % String(result.get("error", "неизвестная ошибка"))
		_split_result_label.add_theme_color_override("font_color", COL_NONE)
		_split_create_button.disabled = false
		return
	var made: Array = result.get("rel_files", [])
	_split_popup.hide()
	var added_note := " Готовая многозвучная копия исключена из игры." if source_was_added and not _split_remove_source.button_pressed else ""
	_status.text = ("%s: создано %d отдельных вариантов%s. Исходный файл %s; его одобрение снято.%s" % [
		source_rel, made.size(), " и они одобрены к добавлению" if _split_approve.button_pressed else "",
		"удалён" if _split_remove_source.button_pressed else "оставлен", added_note])


func _ask_delete_incoming(rel: String) -> void:
	_delete_scope = "incoming"
	_delete_path = rel
	var picked: Dictionary = selection.get(rel, {})
	var moved := String(picked.get("moved", ""))
	var extra := ""
	if moved != "":
		extra = "\nТакже будет удалена добавленная в проект копия:\nassets/audio/%s" % moved
	_delete_dialog.dialog_text = ("Файл будет удалён без возможности восстановления:\n%s%s\n\n"
		+ "Исчезнут назначение, одобрение и связанные строки документации.") % [rel, extra]
	_delete_dialog.popup_centered(Vector2i(680, 260))


func _ask_delete_asset(rel: String) -> void:
	_delete_scope = "asset"
	_delete_path = rel
	_delete_dialog.dialog_text = ("Запись будет удалена без возможности восстановления:\nassets/audio/%s\n\n"
		+ "Будут удалены .import, строка CREDITS, запись исключения и связанный входящий исходник. "
		+ "Игровое событие останется и возьмёт другой вариант, запасной звук или синтез.") % rel
	_delete_dialog.popup_centered(Vector2i(680, 280))


func _confirm_permanent_delete() -> void:
	var scope := _delete_scope
	var path := _delete_path
	_delete_scope = ""
	_delete_path = ""
	var removed := delete_incoming_permanently(path) if scope == "incoming" else delete_asset_permanently(path)
	_status.text = ("Удалено безвозвратно: %s" % path) if removed else ("Файл уже отсутствует: %s" % path)
