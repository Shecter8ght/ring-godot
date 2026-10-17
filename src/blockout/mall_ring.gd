extends Node3D
## Серый 1-й этаж ТЦ Ø200 в черновике территории: тот же data/sectors/mall_1f.json, что у
## scenes/levels/mall_1f.tscn, но без своего асфальта и забора по site_r — землю вокруг кладёт
## MallLandscape. Собирается только при запуске (около 13 с), в редакторе — пусто; дочерние узлы
## Escalators и Rubble — те же эскалаторы и завалы входов, что у 1-го этажа.

@export_file("*.json") var sector_path: String = "res://data/sectors/mall_1f.json"

var sector: Node3D


func _ready() -> void:
	if Engine.is_editor_hint():
		return
	var builder: SectorBuilder = SectorBuilder.new()
	builder.site_ground = false
	sector = builder.build(sector_path)
	sector.name = "Sector"
	add_child(sector)
