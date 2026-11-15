class_name LadderPoint
extends Interactable
## Где взяться за лестницу (Ladder): у низа — «залезть», у верха на площадке — «спуститься». Подсказку
## «F — …» ведёт Raid, как у любого Interactable; лезет свой игрок сам — хост не спрашиваем (движение
## игрока у владельца, как и перелезание).

var ladder: Ladder
var top: bool = false


func can_use() -> bool:
	var pl := Ladder.local_player(get_tree())
	if ladder == null or pl == null or pl.is_climbing() or pl.is_vaulting():
		return false
	if ladder.access_radius <= 0.0:
		return true
	var at := pl.global_position
	if at.distance_to(global_position) > ladder.access_radius:
		return false
	var offset := Vector3.UP * 0.8
	var query := PhysicsRayQueryParameters3D.create(at + offset, global_position + offset,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [pl.get_rid(), ladder.body_rid()])
	return get_world_3d().direct_space_state.intersect_ray(query).is_empty()


func prompt() -> String:
	return "спуститься по лестнице" if top else "залезть по лестнице"


func request_use() -> void:
	if can_use():
		Ladder.local_player(get_tree()).grab_ladder(ladder, top)
