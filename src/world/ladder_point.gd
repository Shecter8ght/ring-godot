class_name LadderPoint
extends Interactable
## Где взяться за лестницу (Ladder): у низа — «залезть», у верха на площадке — «спуститься». Подсказку
## «F — …» ведёт Raid, как у любого Interactable; лезет свой игрок сам — хост не спрашиваем (движение
## игрока у владельца, как и перелезание).

var ladder: Ladder
var top: bool = false


func can_use() -> bool:
	var pl := Ladder.local_player(get_tree())
	return ladder != null and pl != null and not pl.is_climbing() and not pl.is_vaulting()


func prompt() -> String:
	return "спуститься по лестнице" if top else "залезть по лестнице"


func request_use() -> void:
	var pl := Ladder.local_player(get_tree())
	if pl and ladder:
		pl.grab_ladder(ladder, top)
