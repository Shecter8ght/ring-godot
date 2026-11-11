extends "res://src/world/sector_level.gd"
## Test the replacement against the raid map, its terrain, atmosphere and prologue data.

const CAFE := preload("res://scenes/levels/prospekt/zerno/zerno.tscn")

var zerno: Node3D
var zerno_glass: GlassPanes


func _enter_tree() -> void:
	if Engine.is_editor_hint():
		super._enter_tree()
		return
	# Move the existing prop markers before the inherited level bakes its street dressing.
	var props := get_node("World/Filler/Наполнение/Модели города")
	var sedan := props.get_node("Седан, двери открыты 0001") as PropSpot
	sedan.position.x = -174.35
	var lightbox := props.get_node("Рекламный световой пилон 0001") as PropSpot
	lightbox.position.x = -186.30
	super._enter_tree()
	var placeholder := get_node("World/West/Coffee") as Node3D
	var street := placeholder.get_parent() as Node3D
	var location := placeholder.transform
	street.remove_child(placeholder)
	placeholder.free()
	zerno = CAFE.instantiate() as Node3D
	zerno.name = "Coffee"
	zerno.transform = location
	zerno.set_meta("enterable", true)
	zerno.set_meta("height_m", 4.0)
	street.add_child(zerno)
	zerno_glass = zerno.call("install_glass", self, location) as GlassPanes
