class_name Inventory
extends Node
## Рюкзак игрока: список {"id", "n"} и вместимость в ячейках (Balance.BACKPACK_CELLS).
## Меняет только хост (авторитет узла — 1, как у Health); у всех peer список реплицируется.
## Список всегда переприсваивается копией — синхронизатор сравнивает значения.

var items: Array = []


func _ready() -> void:
	if Net.is_networked():
		var sync := MultiplayerSynchronizer.new()
		sync.name = "Sync"
		var config := SceneReplicationConfig.new()
		var path := NodePath(".:items")
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
		sync.replication_config = config
		sync.set_multiplayer_authority(get_multiplayer_authority())
		add_child(sync)


func cells_used() -> int:
	return ItemDb.cells_of(items)


func value() -> int:
	return ItemDb.value_of(items)


func has(id: String) -> bool:
	for it in items:
		if String(it.id) == id and int(it.n) > 0:
			return true
	return false


func count(id: String) -> int:
	for it in items:
		if String(it.id) == id:
			return int(it.n)
	return 0


## Сколько штук id влезет (с учётом неполной стопки).
func room_for(id: String) -> int:
	var st := ItemDb.stack(id)
	var have := count(id)
	var free_in_stack := (st - have % st) % st if have > 0 else 0
	var free_cells := Balance.BACKPACK_CELLS - cells_used()
	return free_in_stack + int(floor(float(free_cells) / float(ItemDb.cells(id)))) * st


## Кладёт до n штук; возвращает, сколько положил (хост).
func add(id: String, n: int) -> int:
	var k := mini(n, room_for(id))
	if k <= 0:
		return 0
	var list := items.duplicate(true)
	ItemDb._merge(list, id, k)
	items = list
	return k


## Забирает до n штук; возвращает, сколько забрал (хост).
func remove(id: String, n: int) -> int:
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


## Всё содержимое наружу (смерть — рюкзак в тело), рюкзак пуст (хост).
func take_all() -> Array:
	var all := items.duplicate(true)
	items = []
	return all
