class_name Saves
extends RefCounted
## Сохранения (профили) для главного меню: каждое — свой файл user://saves/<id>.json (Profile).
## Новая игра — новый файл со стартовым набором; загрузка — выбрать файл; последнее выбранное
## помнится в настройках (Продолжить). Старое единственное сохранение (user://profile.json)
## переносится как «Основной».

const DIR := "user://saves"
const LEGACY := "user://profile.json"


static func _ensure_dir() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR))


## Старое сохранение — в список, если он пуст (один раз).
static func migrate_legacy() -> void:
	_ensure_dir()
	if not FileAccess.file_exists(LEGACY) or not list().is_empty():
		return
	var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(LEGACY))
	if not d is Dictionary:
		return
	(d as Dictionary)["name"] = "Основной"
	var f := FileAccess.open(DIR + "/main.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(d, "  "))
		f.close()
		remember(DIR + "/main.json")


## Все сохранения: [{path, name, money, trust, extractions, time}], свежие сверху.
static func list() -> Array:
	_ensure_dir()
	var out: Array = []
	for fn in DirAccess.get_files_at(DIR):
		if not fn.ends_with(".json"):
			continue
		var path := DIR + "/" + fn
		var d: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if not d is Dictionary:
			continue
		var dd: Dictionary = d
		out.append({"path": path, "name": String(dd.get("name", fn.get_basename())), "money": int(dd.get("money", 0)),
			"trust": int(dd.get("trust", 0)), "extractions": int(dd.get("extractions", 0)),
			"time": FileAccess.get_modified_time(path)})
	out.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return int(a.time) > int(b.time))
	return out


## Новая игра: файл со стартовым набором, имя — как назвал игрок.
static func create(display_name: String) -> String:
	_ensure_dir()
	var base := display_name.strip_edges().to_lower().validate_filename().replace(" ", "_")
	if base == "":
		base = "save"
	var path := "%s/%s.json" % [DIR, base]
	var k := 2
	while FileAccess.file_exists(path):
		path = "%s/%s_%d.json" % [DIR, base, k]
		k += 1
	Profile.use_file(path, true)
	Profile.profile_name = display_name.strip_edges() if display_name.strip_edges() != "" else "Выживший"
	# новая игра — с короткого обучения в убежище (data/quests/tutorial_basics.json)
	Profile.flags["new_game"] = true
	Profile.save()
	remember(path)
	return path


static func open(path: String) -> void:
	Profile.use_file(path, false)
	remember(path)


static func remove(path: String) -> void:
	if FileAccess.file_exists(path):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
	if last() == path:
		remember("")


## Последнее выбранное (Продолжить); "" — нет или файла больше нет.
static func last() -> String:
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	var p := String(cfg.get_value("profile", "last", ""))
	return p if p != "" and FileAccess.file_exists(p) else ""


static func remember(path: String) -> void:
	var cfg := ConfigFile.new()
	cfg.load(CameraRig.SETTINGS_PATH)
	cfg.set_value("profile", "last", path)
	cfg.save(CameraRig.SETTINGS_PATH)
