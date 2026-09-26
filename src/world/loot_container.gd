@tool
class_name LootContainer
extends Interactable
## То, что обыскивают: касса, шкаф, коробки, сейф, тело. Содержимое бросает хост при первом
## обыске по таблице data/loot.json (тела и выброшенное приходят готовыми) и реплицирует всем.
## Обыск — время search_s рядом (см. InventoryUI), дальше окно: взять по одному или всё.
## Контейнеры на пропсах строит SectorBuilder (одинаково у всех peer), сейф/стойку ставят
## руками в сцену уровня, тела и выброшенное — Raid через спавнер.

enum Look { NONE, SAFE, RACK, BODY, BAG, CRATE }

@export var display_name: String = "Ящик":
	set(v):
		display_name = v
		_rebuild()
## Таблица лута (data/loot.json → tables).
@export var table: String = "storage"
@export var search_s: float = 2.0
## Как выглядит (у контейнеров на пропсах — NONE: вид даёт сам проп).
@export var look: Look = Look.NONE:
	set(v):
		look = v
		_rebuild()

## Содержимое: [{"id", "n", "x", "y", "r"}] — стоит в клетках сетки grid (как рюкзак); rolled —
## брошено ли уже (иначе бросит хост при первом обыске).
var items: Array = []
var rolled: bool = false
## Сетка ящика: Balance.LOOT_GRID_W × рядов по виду (бросок не влез — рядов больше). Задаётся, когда
## появляется содержимое (place_all); у всех peer одинаково.
var grid: Vector2i = Vector2i.ZERO
## Откуда «вываливается» при появлении (смещение от места покоя; ноль — просто стоит): ящик из
## трупа летит с высоты груди и падает на пол, кувыркнувшись. Анимация у каждого peer своя.
var toss_from: Vector3 = Vector3.ZERO


func _ready() -> void:
	super._ready()
	if not Engine.is_editor_hint():
		add_to_group("loot_containers")
		if Net.is_networked():
			var sync := MultiplayerSynchronizer.new()
			sync.name = "Sync"
			var config := SceneReplicationConfig.new()
			for prop in [".:items", ".:rolled", ".:grid"]:
				var path := NodePath(prop)
				config.add_property(path)
				config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
			sync.replication_config = config
			sync.set_multiplayer_authority(get_multiplayer_authority())
			Net.scope_sync(self, sync)
			add_child(sync)
		if toss_from != Vector3.ZERO:
			_toss()


func _toss() -> void:
	var rest := position
	var start := rest + toss_from
	var spin := randf_range(-1.0, 1.0)
	position = start
	var tw := create_tween()
	tw.tween_method(func(t: float) -> void:
		position = start.lerp(rest, t) + Vector3.UP * 0.25 * sin(PI * t)
		rotation = Vector3((1.0 - t) * 1.4, spin * (1.0 - t) * 2.0, 0.0), 0.0, 1.0, Balance.CRATE_TOSS_SEC).set_ease(Tween.EASE_IN)


func can_use() -> bool:
	return not (rolled and items.is_empty())


func prompt() -> String:
	return "обыскать: " + display_name


## F у контейнера: начать обыск (окно откроет InventoryUI, когда пройдёт search_s).
func _use(_peer_id: int) -> void:
	roll()


## Хост: бросить содержимое, если ещё не брошено.
func roll() -> void:
	if rolled:
		return
	var rng := RandomNumberGenerator.new()
	rng.randomize()
	items = ItemDb.roll(table, rng)
	# тяжёлые условия рейда — лут богаче: лишний бросок
	if rng.randf() < RaidConditions.loot_bonus():
		items.append_array(ItemDb.roll(table, rng))
	# магазин на сигнализации — там ещё не грабили
	if is_inside_tree() and AlarmZone.boosts(global_position, get_tree()):
		items.append_array(ItemDb.roll(table, rng))
	place_all()
	rolled = true


## Сетки ещё нет (ящик с содержимым из кода, старое) — разложить (хост).
func ensure_grid() -> void:
	if grid == Vector2i.ZERO:
		place_all()


## Разложить содержимое по клеткам: крупное — первым; не влезает в ряды по виду — рядом больше
## (ничего не теряется). Одинаково у всех peer (тела и выброшенное раскладываются из данных спавна).
func place_all() -> void:
	var rows := int(Balance.LOOT_ROWS.get(String(Look.keys()[look]), 3))
	var list := items.duplicate(true)
	while true:
		var g := Vector2i(Balance.LOOT_GRID_W, rows)
		var probe := list.duplicate(true)
		if ItemDb.pack(probe, g).is_empty() or rows >= 60:
			grid = g
			items = probe
			return
		rows += 1


## Хост: забрать до n штук из записи idx; возвращает, сколько забрал.
func take_at(idx: int, n: int) -> int:
	var list := items.duplicate(true)
	var out := ItemDb.remove_at(list, idx, n)
	if out.is_empty():
		return 0
	items = list
	return int(out.n)


## Хост: забрать до n штук id; возвращает, сколько забрал.
func take(id: String, n: int) -> int:
	var list := items.duplicate(true)
	for i in range(list.size()):
		if String(list[i].id) == id:
			var k := mini(n, int(list[i].n))
			list[i].n = int(list[i].n) - k
			if int(list[i].n) <= 0:
				list.remove_at(i)
			items = list
			return k
	return 0


func _build_visual(parent: Node3D) -> void:
	match look:
		Look.SAFE:
			_box(parent, Vector3(0, 0.6, 0), Vector3(0.8, 1.2, 0.7), Color(0.22, 0.24, 0.26))
			_box(parent, Vector3(0.2, 0.7, -0.36), Vector3(0.12, 0.12, 0.04), Color(0.7, 0.7, 0.72))
		Look.RACK:
			_box(parent, Vector3(0, 1.0, 0), Vector3(0.7, 2.0, 1.0), Color(0.12, 0.13, 0.15))
			_box(parent, Vector3(0, 1.4, -0.51), Vector3(0.5, 0.05, 0.02), Color(0.2, 0.9, 0.4), 2.0)
		Look.BAG:
			_box(parent, Vector3(0, 0.2, 0), Vector3(0.6, 0.4, 0.35), Color(0.25, 0.28, 0.2))
		Look.CRATE:
			# зелёный армейский ящик: корпус, крышка с кромкой, ручки на торцах, защёлки
			_box(parent, Vector3(0, 0.15, 0), Vector3(0.56, 0.28, 0.34), Color(0.24, 0.29, 0.2))
			_box(parent, Vector3(0, 0.305, 0), Vector3(0.58, 0.03, 0.36), Color(0.2, 0.24, 0.17))
			for sx in [-1.0, 1.0]:
				_box(parent, Vector3(sx * 0.29, 0.2, 0), Vector3(0.025, 0.035, 0.16), Color(0.08, 0.08, 0.08))
				_box(parent, Vector3(sx * 0.14, 0.26, -0.172), Vector3(0.05, 0.05, 0.012), Color(0.45, 0.45, 0.44))
		_:
			pass
