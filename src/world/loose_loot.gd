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
## Вещь уронил игрок (магазин при быстрой перезарядке): лежит плашмя, повёрнута на lay_yaw; пришла
## готовой от Raid (items, rolled), точка ничего не бросает сама.
var dropped: bool = false
var lay_yaw: float = 0.0
## Вещь прилетела физическим телом (TossedItem): лежит так, как оно успокоилось, — lay_pose, положение модели
## относительно точки (точка — на поверхности под ней).
var posed: bool = false
var lay_pose: Transform3D = Transform3D.IDENTITY


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
	if dropped:
		if posed:
			pose_item(parent, id, lay_pose)
		else:
			lay_item(parent, id, lay_yaw)
		return
	var model: Node3D = ItemModels.build(id)
	parent.add_child(model)
	var angles: Array = ItemDb.item(id).get("loot_rotation", [0, 0, 0])
	model.rotation_degrees = Vector3(float(angles[0]), float(angles[1]), float(angles[2]))
	var box: AABB = ItemModels.bounds(model)
	model.position.y = -box.position.y + float(Balance.LOOSE_LOOT.surface_gap)
	for node: Node in model.find_children("*", "GeometryInstance3D", true, false):
		(node as GeometryInstance3D).visibility_range_end = float(Balance.LOOSE_LOOT.distance)


## Куда падает вещь, выпавшая из рук игрока: рядом с ногами (Balance.DROPPED_MAG.radius), на пол под
## этой точкой (ступени, склон, край перекрытия).
static func floor_near(pl: Player) -> Vector3:
	var cfg: Dictionary = Balance.DROPPED_MAG
	var angle: float = randf() * TAU
	var pos: Vector3 = pl.global_position + Vector3(sin(angle), 0.0, cos(angle)) * randf_range(float(cfg.radius[0]), float(cfg.radius[1]))
	var query := PhysicsRayQueryParameters3D.create(pos + Vector3.UP * 0.8, pos + Vector3.DOWN * 2.5, Hitscan.LAYER_WORLD)
	var hit: Dictionary = pl.get_world_3d().direct_space_state.intersect_ray(query)
	return hit.position if not hit.is_empty() else pos


## Вещь лежит так, как успокоилось её летевшее тело (TossedItem): та же модель с началом в центре габарита,
## pose — её положение относительно точки. Подмена тела на лежащую вещь не видна.
static func pose_item(parent: Node3D, id: String, pose: Transform3D) -> void:
	var holder: Node3D = TossedItem.centered_model(id)
	holder.name = "Laid"
	holder.transform = pose
	parent.add_child(holder)


## Точка лежащей вещи и поза модели относительно неё по месту, где успокоилось тело (pose — мир): точка — на
## поверхности под телом (floor — попадание луча вниз; пусто — в центре тела).
static func rest_place(pose: Transform3D, floor: Dictionary) -> Array:
	var root: Vector3 = floor.position if not floor.is_empty() else pose.origin
	return [root, Transform3D(pose.basis, pose.origin - root)]


## Положить вещь на пол плашмя (самой тонкой стороной вверх) и повернуть на yaw: уроненный магазин
## лежит как упал, а не стоит столбиком. Магазин — тот, что в оружии (ItemModels.weapon_magazine).
static func lay_item(parent: Node3D, id: String, yaw: float) -> void:
	var holder := Node3D.new()
	holder.name = "Laid"
	holder.rotation.y = yaw
	parent.add_child(holder)
	var model: Node3D = ItemModels.weapon_magazine(id) if not WeaponDb.magazine(id).is_empty() else null
	if model == null:
		model = ItemModels.build(id)
	holder.add_child(model)
	var size: Vector3 = ItemModels.bounds(model).size
	if size.x <= size.y and size.x <= size.z:
		model.rotation.z = PI * 0.5
	elif size.z <= size.y:
		model.rotation.x = PI * 0.5
	var box: AABB = ItemModels.bounds(model)
	model.position -= Vector3(box.get_center().x, box.position.y - float(Balance.LOOSE_LOOT.surface_gap), box.get_center().z)
	for node: Node in model.find_children("*", "GeometryInstance3D", true, false):
		(node as GeometryInstance3D).visibility_range_end = float(Balance.LOOSE_LOOT.distance)
