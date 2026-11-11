extends Door
## The authored frame determines the direction of the leaf and the clear space it needs.

var swing_degrees := 90.0


func _ready() -> void:
	super._ready()
	_mesh.hide()
	_shape.set_meta("surface", "metal")


func toggle(from_world: Vector3) -> void:
	super.toggle(from_world)
	if is_multiplayer_authority() and is_open:
		_target_angle = deg_to_rad(swing_degrees)


func push_from(_from_world: Vector3) -> bool:
	return false
