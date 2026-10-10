class_name RivalRoster
extends RefCounted
## Постоянный состав чужих отрядов (data/rivals.json) и память о них между рейдами
## (user://rivals.json): сколько раз отряд ходил, ушёл с добычей, был выбит и кем, сколько вынес.
## Память — у хоста рейда (он считает чужие отряды); тесты ставят свой файл через use_file.

const DATA := "res://data/rivals.json"
const PATH := "user://rivals.json"

static var path: String = PATH
static var _data: Dictionary = {}
static var _memory: Dictionary = {}
static var _loaded: bool = false


## Свой файл памяти (тесты); fresh — начать с пустой.
static func use_file(p: String, fresh: bool) -> void:
	path = p
	_loaded = false
	if fresh and FileAccess.file_exists(p):
		DirAccess.remove_absolute(ProjectSettings.globalize_path(p))


static func _ensure() -> void:
	if _data.is_empty() and FileAccess.file_exists(DATA):
		_data = JSON.parse_string(FileAccess.get_file_as_string(DATA)) as Dictionary
	if _loaded:
		return
	_loaded = true
	_memory = {}
	if FileAccess.file_exists(path):
		var raw: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		if raw is Dictionary:
			_memory = raw


## Все отряды состава: [{id, name, style}].
static func squads() -> Array:
	_ensure()
	return _data.get("squads", [])


## Характер отряда: {name, loot_k, goal_k, archs}.
static func style(key: String) -> Dictionary:
	_ensure()
	var styles: Dictionary = _data.get("styles", {})
	return styles.get(key, styles.get("assault", {"name": "", "loot_k": 1.0, "goal_k": 1.0, "archs": ["rival", "rival"]}))


## Память об отряде: {raids, out, wiped, wiped_by_you, loot}.
static func memory(id: String) -> Dictionary:
	_ensure()
	var m: Dictionary = _memory.get(id, {})
	return {"raids": int(m.get("raids", 0)), "out": int(m.get("out", 0)), "wiped": int(m.get("wiped", 0)),
		"wiped_by_you": int(m.get("wiped_by_you", 0)), "loot": int(m.get("loot", 0))}


## Записать исход: key — raids / out / wiped / wiped_by_you / loot, n — на сколько прибавить.
static func note(id: String, key: String, n: int = 1) -> void:
	var m: Dictionary = memory(id)
	m[key] = int(m.get(key, 0)) + n
	_memory[id] = m
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_memory, " "))


## Случайные n разных отрядов; знакомые (с кем уже встречались в бою) — чуть чаще.
static func pick(n: int, rng: RandomNumberGenerator) -> Array:
	var pool: Array = squads().duplicate()
	var out: Array = []
	while out.size() < n and not pool.is_empty():
		var total := 0.0
		var weights: Array[float] = []
		for s: Dictionary in pool:
			var w: float = 1.0 + minf(2.0, float(memory(String(s.id)).wiped_by_you) * 0.5)
			weights.append(w)
			total += w
		var roll := rng.randf() * total
		for i in range(pool.size()):
			roll -= weights[i]
			if roll <= 0.0:
				out.append(pool[i])
				pool.remove_at(i)
				break
	return out
