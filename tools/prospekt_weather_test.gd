extends "res://tools/mall_light_test.gd"
## Проспект теперь использует общий свет и настоящую смену суток, как остальные карты.


func _ready() -> void:
	sector_path = "res://data/sectors/prospekt.json"
	await super._ready()
