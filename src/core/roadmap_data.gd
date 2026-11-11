class_name RoadmapData
extends RefCounted
## Дорожная карта до демоверсии: список работ по разделам и этапам из data/roadmap.json.
## Файл правят руками владелец и агенты (разделы, пункты, порядок, «готово, когда», статус) — кода для
## этого не нужно. Отметки статуса из игры пишутся в тот же файл проекта: список общий для владельца и
## всех агентов и идёт в git вместе с остальным. В сборке для друзей файл проекта запечатан в RING.pck —
## там отметки ложатся отдельно, в user://roadmap_marks.json, и на общий список не влияют.

const PATH: String = "res://data/roadmap.json"
const USER_MARKS: String = "user://roadmap_marks.json"
## Статусы по кругу: щелчок по отметке переводит в следующий.
const STATUSES: Array[String] = ["todo", "doing", "done"]
const STATUS_NAMES: Dictionary = {"todo": "не начато", "doing": "в работе", "done": "готово"}

var path: String = PATH
## Отметки пишутся прямо в файл списка (проект открыт из папки) или отдельно в user:// (сборка).
var marks_path: String = ""
var data: Dictionary = {}
## Что не так с файлом — показывается в окне вместо списка или строкой над ним.
var problems: Array[String] = []

var _items: Dictionary = {}
var _marks: Dictionary = {}


func _init(file_path: String = PATH, overlay_path: String = "") -> void:
	path = file_path
	marks_path = overlay_path
	if marks_path == "" and file_path == PATH and not OS.has_feature("editor"):
		marks_path = USER_MARKS
	reload()


## Перечитать файл с диска: его могли поправить руками, пока игра открыта.
func reload() -> bool:
	data = {}
	_items = {}
	_marks = {}
	problems = []
	var parsed: Variant = _read_json(path)
	if not parsed is Dictionary:
		problems.append("Не читается файл списка %s — проверь запятые и кавычки." % path)
		return false
	data = parsed
	var stage_ids: Dictionary = {}
	for st: Variant in stages():
		stage_ids[String((st as Dictionary).get("id", ""))] = true
	for sec: Dictionary in sections():
		for it: Dictionary in section_items(sec):
			var id: String = String(it.get("id", ""))
			if id == "" or _items.has(id):
				problems.append("Пункт «%s»: пустой или повторный id «%s»." % [String(it.get("title", "?")), id])
				continue
			if not String(it.get("status", "todo")) in STATUSES:
				problems.append("Пункт «%s»: неизвестный статус «%s»." % [String(it.get("title", "?")), String(it.get("status", ""))])
			if not stage_ids.is_empty() and not stage_ids.has(String(it.get("stage", ""))):
				problems.append("Пункт «%s»: неизвестный этап «%s»." % [String(it.get("title", "?")), String(it.get("stage", ""))])
			_items[id] = it
	for id: String in _items:
		for need: Variant in (_items[id] as Dictionary).get("needs", []):
			if not _items.has(String(need)):
				problems.append("Пункт «%s» ждёт несуществующий пункт «%s»." % [String((_items[id] as Dictionary).get("title", "?")), String(need)])
	if marks_path != "":
		var marks: Variant = _read_json(marks_path)
		if marks is Dictionary:
			_marks = marks
	return true


func title() -> String:
	return String(data.get("title", "Дорожная карта"))


## Одной-двумя фразами: что входит в демоверсию.
func summary() -> String:
	return String(data.get("demo", ""))


func stages() -> Array:
	return data.get("stages", []) as Array


func sections() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for s: Variant in data.get("sections", []) as Array:
		if s is Dictionary:
			out.append(s)
	return out


func section_items(section: Dictionary) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for it: Variant in section.get("items", []) as Array:
		if it is Dictionary:
			out.append(it)
	return out


## Все пункты в порядке файла; group — "" (все), id раздела или id этапа.
func items(group: String = "") -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for sec: Dictionary in sections():
		for it: Dictionary in section_items(sec):
			if group == "" or group == String(sec.get("id", "")) or group == String(it.get("stage", "")):
				out.append(it)
	return out


## Что отложено за рамки демоверсии: [{title, why}].
func later() -> Array:
	return data.get("later", []) as Array


func item(id: String) -> Dictionary:
	return _items.get(id, {}) as Dictionary


func section_of(id: String) -> Dictionary:
	for sec: Dictionary in sections():
		for it: Dictionary in section_items(sec):
			if String(it.get("id", "")) == id:
				return sec
	return {}


func stage_name(stage_id: String) -> String:
	for st: Variant in stages():
		if String((st as Dictionary).get("id", "")) == stage_id:
			return String((st as Dictionary).get("name", stage_id))
	return stage_id


func status(id: String) -> String:
	var st: String = String(_marks.get(id, item(id).get("status", "todo")))
	return st if st in STATUSES else "todo"


## [сделано, всего] по разделу, этапу или по всему списку.
func count(group: String = "") -> Vector2i:
	var done: int = 0
	var list: Array[Dictionary] = items(group)
	for it: Dictionary in list:
		if status(String(it.get("id", ""))) == "done":
			done += 1
	return Vector2i(done, list.size())


## Названия пунктов, которые надо закончить раньше этого и которые ещё не готовы.
func blockers(id: String) -> Array[String]:
	var out: Array[String] = []
	for need: Variant in item(id).get("needs", []) as Array:
		if _items.has(String(need)) and status(String(need)) != "done":
			out.append(String((_items[String(need)] as Dictionary).get("title", need)))
	return out


static func next_status(st: String) -> String:
	return STATUSES[(STATUSES.find(st) + 1) % STATUSES.size()]


## Куда ложатся отметки — строкой для окна.
func saves_to() -> String:
	if marks_path != "":
		return "Отметки — только на этом компьютере (%s)." % marks_path
	return "Отметки пишутся в файл проекта %s — общий для тебя и агентов." % path.trim_prefix("res://")


## Поставить статус и сохранить. Файл проекта сначала перечитывается: правки, сделанные в нём руками,
## пока игра открыта, не теряются — меняется только одна отметка.
func set_status(id: String, st: String) -> bool:
	if not st in STATUSES or not _items.has(id):
		return false
	if marks_path != "":
		_marks[id] = st
		return _write_json(marks_path, _marks)
	if not reload() or not _items.has(id):
		return false
	(_items[id] as Dictionary)["status"] = st
	return _write_json(path, data)


static func _read_json(file_path: String) -> Variant:
	if not FileAccess.file_exists(file_path):
		return null
	# свой разбор вместо JSON.parse_string: испорченный руками файл — не ошибка движка, а строка в окне
	var json: JSON = JSON.new()
	if json.parse(FileAccess.get_file_as_string(file_path)) != OK:
		return null
	return json.data


## Порядок ключей — как в файле (не по алфавиту): его читают и правят руками.
static func _write_json(file_path: String, value: Variant) -> bool:
	var f: FileAccess = FileAccess.open(file_path, FileAccess.WRITE)
	if f == null:
		return false
	f.store_string(JSON.stringify(value, " ", false) + "\n")
	f.close()
	return true
