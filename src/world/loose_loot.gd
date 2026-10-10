@tool
class_name LooseLoot
extends LootContainer
## Точка одной физической находки. Корень стоит на поверхности, модель — в метрах.
## У всех peer одинаковый путь точки; только хост решает, появилась ли вещь и какая.
## Список и его опустошение реплицируются штатным Sync контейнера; подбор — штатной
## атомарной операцией Raid (расстояние, живой игрок, место в рюкзаке).

## Пусто — случайная вещь из темы table; задан id — эта вещь с тем же шансом.
@export var item_id: String = "":
	set(value):
		item_id = value
		_rebuild()
## -1 — общий шанс Balance.LOOSE_LOOT.chance. 1 — гарантированная находка.
@export_range(-1.0, 1.0) var spawn_chance: float = -1.0


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	add_to_group("loose_loot")
	if not Net.is_networked() or multiplayer.is_server():
		var rng: RandomNumberGenerator = RandomNumberGenerator.new()
		rng.randomize()
		populate(rng)


## Пустая точка остаётся в дереве: повторный запрос и поздний клиент не создадут копию.
func populate(rng: RandomNumberGenerator) -> void:
	if rolled:
		return
	var chance: float = float(Balance.LOOSE_LOOT.chance) if spawn_chance < 0.0 else spawn_chance
	var id: String = item_id if item_id != "" else ItemDb.loose_item(table, rng)
	rolled = true
	if ItemDb.exists(id) and rng.randf() < chance:
		var entry: Dictionary = ItemDb.make(id, 1)
		entry["fir"] = true
		items = [entry]
		place_all()
	else:
		items = []


func prompt() -> String:
	return "подобрать: " + ItemDb.item_name(String(items[0].id)) if not items.is_empty() else ""


func can_use() -> bool:
	return not items.is_empty()


func _use(peer_id: int) -> void:
	if not can_use() or items.is_empty() or Raid.current == null:
		return
	Raid.current._take(peer_id, Raid.current.get_path_to(self), String(items[0].id), 1)
	if not items.is_empty():
		Raid.current._tell(peer_id, "В рюкзаке нет места для этой находки")


func _contents_changed() -> void:
	_rebuild()


func _build_visual(parent: Node3D) -> void:
	var id: String = ""
	if Engine.is_editor_hint():
		id = item_id
		if id == "":
			var rng: RandomNumberGenerator = RandomNumberGenerator.new()
			rng.seed = hash(table)
			id = ItemDb.loose_item(table, rng)
	elif not items.is_empty():
		id = String(items[0].id)
	if id == "":
		return
	var model: Node3D = ItemModels.build(id)
	parent.add_child(model)
	var angles: Array = ItemDb.item(id).get("loot_rotation", [0, 0, 0])
	model.rotation_degrees = Vector3(float(angles[0]), float(angles[1]), float(angles[2]))
	var box: AABB = ItemModels.bounds(model)
	model.position.y = -box.position.y + float(Balance.LOOSE_LOOT.surface_gap)
	for node: Node in model.find_children("*", "GeometryInstance3D", true, false):
		(node as GeometryInstance3D).visibility_range_end = float(Balance.LOOSE_LOOT.distance)
