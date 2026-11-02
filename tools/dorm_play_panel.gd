extends CanvasLayer
## Панель Esc режима «Общежитие · игрок» (tools/dorm_play.gd): пока открыта — персонаж стоит, мышь свободна
## (группа esc_windows, как окна игры).

var panel: Control


func _ready() -> void:
	add_to_group("esc_windows")


func is_open() -> bool:
	return panel!=null and panel.visible
