@tool
class_name ContractTerminal
extends Interactable
## Терминал связи в убежище (старый ноутбук на столе связи): F — переписка и доска заказов
## (TerminalUI, Quests, Contracts). Подсказка показывает, есть ли новое сообщение или что сдать.

var _ui: TerminalUI


func prompt() -> String:
	if Engine.is_editor_hint():
		return "Терминал связи"
	for qid in Quests.terminal_threads():
		if not Quests.terminal_action(qid).is_empty():
			return "Терминал связи — новое сообщение"
	for e: Dictionary in Contracts.board():
		if Contracts.can_turn_in(String(e.id)):
			return "Терминал связи — есть что сдать"
	return "Терминал связи — заказы"


func request_use() -> void:
	if _ui == null:
		_ui = TerminalUI.new()
		add_child(_ui)
	_ui.open()


func _build_visual(_parent: Node3D) -> void:
	pass
