class_name LampGlow
## Видимый источник фонаря: у SpotLight3D свечения нет — луч по земле виден, а сам фонарь нет
## (особенно издали и в оптике). Квадрат-«спрайт» с шейдером lamp_glow — дочерний узел света:
## гаснет вместе с ним, тени не отбрасывает.

static var _mat: ShaderMaterial


static func attach(light: Light3D, size: float = 0.22, energy: float = 5.0) -> MeshInstance3D:
	if _mat == null:
		_mat = ShaderMaterial.new()
		_mat.shader = load("res://src/combat/lamp_glow.gdshader")
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	var mi := MeshInstance3D.new()
	mi.name = "Glow"
	mi.mesh = q
	mi.material_override = _mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	mi.set_meta("no_shadow", true)
	if energy != 5.0:
		var m := _mat.duplicate() as ShaderMaterial
		m.set_shader_parameter("energy", energy)
		mi.material_override = m
	light.add_child(mi)
	return mi
