class_name AIPost
extends Marker3D
## Пост гарнизона (слой «гарнизоны мест», docs/design/enemy_population.md): группа мародёров живёт у
## объекта — обходит точки поста, на шум рядом выходит, после боя возвращается; добычу не грабит.
## Дочерние Marker3D — точки обхода (этажи, антресоли, вид на главный подход); нет их — набираются
## по навигации в радиусе radius. В рейд занимается часть постов карты (AIPopulation), по весу.

## Район поста. Карта с настройкой spread_posts_by_district сначала заполняет менее занятые районы.
@export var district: String = ""
## Насколько чаще других занимается: горячие места — больше, тихие — меньше.
@export_range(0.0, 10.0, 0.1) var weight: float = 1.0
## Занят в каждом рейде, начиная с такого числа игроков (0 — как все, по весу). Решение владельца
## 2026-10-14: рынок — постоянная горячая точка.
@export_range(0, 3) var always_from: int = 0
## Посты с одной непустой меткой взаимоисключающие: в рейд занимается не больше одного из них.
@export var exclusive: String = ""
## Радиус поста, м: в нём держатся; точки обхода без своих набираются в нём же.
@export_range(4.0, 60.0, 0.5) var radius: float = 14.0
## Свой размер группы [от, до]; (0, 0) — по Balance.AI_POPULATION.post_group.
@export var group_size: Vector2i = Vector2i.ZERO
## Кто держит пост: тип из Balance.AI_ARCHETYPES для всей группы (кордон ЧВК — «pmc»); пусто — мародёры,
## ведущий и состав случайные, как у всех постов.
@export var arch: String = ""
## Тип ведущего группы (первый боец) — главарь с охраной: ведущий своего типа, остальные — arch; пусто — как все.
@export var lead_arch: String = ""
## Шанс, что пост вообще занят в этом рейде (главарь — не каждый рейд); 1 — как обычно, по весу.
@export_range(0.0, 1.0, 0.05) var chance: float = 1.0


func _ready() -> void:
	add_to_group("ai_posts")


## Точки обхода, поставленные руками (дочерние Marker3D).
func patrol_points() -> PackedVector3Array:
	var out := PackedVector3Array()
	for c in get_children():
		if c is Marker3D:
			out.append((c as Marker3D).global_position)
	return out
