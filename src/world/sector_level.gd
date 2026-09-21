extends Node3D
## Сцена сектора: строит геометрию из данных и ставит игрока на точку спавна.
## Свет и атмосферу задаёт WorldEnvironment/Sun в самой сцене — их можно крутить руками в редакторе.

@export_file("*.json") var sector_path: String = "res://data/sectors/f1_market.json"

@onready var _player: Node3D = $Player
@onready var _camera_rig: CameraRig = $CameraRig


func _ready() -> void:
	var builder := SectorBuilder.new()
	var sector := builder.build(sector_path)
	add_child(sector)
	move_child(sector, 0)
	# Камера смотрит от атриума наружу: так витрины галереи обращены к камере, а не спиной.
	if _camera_rig and sector.has_meta("camera_yaw"):
		_camera_rig.rotation_degrees.y = float(sector.get_meta("camera_yaw"))
	if _player and sector.has_meta("spawn"):
		_player.global_position = (sector.get_meta("spawn") as Vector3) + Vector3(0, 0.05, 0)
