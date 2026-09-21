class_name Tracer
extends MeshInstance3D
## Трассер выстрела: светящаяся линия от ствола до точки попадания, гаснет за доли секунды.

const LIFE := 0.09

var _t: float = 0.0


static func spawn(parent: Node, from: Vector3, to: Vector3, color: Color) -> void:
	var tr := Tracer.new()
	var im := ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINES)
	im.surface_add_vertex(from)
	im.surface_add_vertex(to)
	im.surface_end()
	tr.mesh = im
	var m := StandardMaterial3D.new()
	m.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	m.albedo_color = color
	m.emission_enabled = true
	m.emission = color
	m.emission_energy_multiplier = 4.0
	tr.material_override = m
	tr.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(tr)


func _process(delta: float) -> void:
	_t += delta
	if _t >= LIFE:
		queue_free()
