extends Node
## Обновления сборки для друзей: патч-PCK из папки patches рядом с RING.exe (tools/build_patch.cmd).
## Автозагрузка стоит первой и подключает патч в _init — раньше, чем грузятся скрипты остальных
## автозагрузок и сцены, поэтому патч заменяет и их (проверено на 4.7.2: данные, скрипты, новые
## class_name, сцены). Не меняются патчем только этот скрипт и project.godot (настройки, автозагрузки,
## клавиши) — для них нужен полный выпуск, tools/release_patch.py check это не пропустит.
## На скрипты проекта не ссылается: всё, что он загрузил бы до патча, осталось бы старым.

## папка патчей рядом с RING.exe; метку основы в неё пишет tools/build_release.cmd
const DIR_NAME := "patches"
const BASE_FILE := "base.txt"
## имя патча: RING_patch_<номер>_<метка основы>.pck
const PREFIX := "RING_patch_"

## метка полной сборки, на которую ставятся патчи; пусто — запуск не из выпуска (редактор, тесты)
var base_id: String = ""
## номер подключённого патча; 0 — без патча
var patch_number: int = 0


func _init() -> void:
	var dir := OS.get_executable_path().get_base_dir().path_join(DIR_NAME)
	var marker := dir.path_join(BASE_FILE)
	if not FileAccess.file_exists(marker):
		return
	base_id = FileAccess.get_file_as_string(marker).strip_edges()
	if base_id == "":
		return
	# Патчи от прежней основы (распаковали новый выпуск поверх старого) не подходят: у них другая метка.
	var suffix := "_" + base_id + ".pck"
	var found: Dictionary[int, String] = {}
	for file_name: String in DirAccess.get_files_at(dir):
		if not (file_name.begins_with(PREFIX) and file_name.ends_with(suffix)):
			continue
		var number := file_name.substr(PREFIX.length(), file_name.length() - PREFIX.length() - suffix.length())
		if number.is_valid_int() and int(number) > 0:
			found[int(number)] = dir.path_join(file_name)
	# Патчи накопительные — каждый несёт все изменения от основы, поэтому подключается только последний.
	var numbers: Array[int] = []
	numbers.assign(found.keys())
	numbers.sort()
	numbers.reverse()
	for number: int in numbers:
		if ProjectSettings.load_resource_pack(found[number]):
			patch_number = number
			print("[сборка] основа %s, патч %d" % [base_id, number])
			return
		push_warning("[сборка] не удалось подключить патч %s" % found[number])
	print("[сборка] основа %s, без патча" % base_id)


## Подпись для главного меню: друзьям видно, одна ли у них сборка; вне выпуска — пусто.
func label() -> String:
	if base_id == "":
		return ""
	return "сборка %s · %s" % [base_id, ("патч %d" % patch_number) if patch_number > 0 else "без патчей"]
