@tool
class_name RangeWeaponRack
extends Interactable
## Стойка тира: F — окно со всем оружием игры (RangeWeaponPicker). Выбранный ствол выдаётся
## только на зал тира (Player.set_range_weapon): патроны без счёта, рюкзак и тайник не трогаются.

var _picker: RangeWeaponPicker


func prompt() -> String:
	var pl: Player = _local_player()
	if pl and pl.in_range_mode():
		return "Стойка тира — сменить или сдать ствол"
	return "Стойка тира — взять любой ствол"


func request_use() -> void:
	var pl: Player = _local_player()
	if pl == null:
		return
	if _picker == null:
		_picker = RangeWeaponPicker.new()
		add_child(_picker)
	_picker.open_for(pl)


func _local_player() -> Player:
	if not is_inside_tree():
		return null
	for n: Node in get_tree().get_nodes_in_group("all_players"):
		var p: Player = n as Player
		if p and p.is_local():
			return p
	return null


func _build_visual(_parent: Node3D) -> void:
	pass
