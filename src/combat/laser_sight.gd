class_name LaserSight
extends Node3D
## ЛЦУ на оружии — узел «LaserBeam_<точка>» в модели (WeaponMods._laser / блок фонарь+ЛЦУ; meta
## "mount"). Включён (узел виден) — луч по оси ствола (+Z узла) до первой преграды:
##  • точка на поверхности видна всем и без ПНВ — яркая, с отсветом, чем дальше, тем крупнее
##    (иначе сверху, в изометрии, её не разглядеть); дальность — Balance.LASER.range_m;
##  • сам луч — только тому, кто смотрит в ПНВ (viewer_nvg — свой игрок): в воздухе его видно
##    лишь в ночник, как у настоящих ЛЦУ.
## Сквозь стекло витрин идёт (слой стекла не проверяется), по игрокам — нет (своя капсула).

## ПНВ у того, кто смотрит (свой игрок): ставит WeaponModels.set_night_vision.
static var viewer_nvg: bool = false

var _beam: MeshInstance3D
var _dot: MeshInstance3D
var _glow: OmniLight3D


func _init() -> void:
	_beam = MeshInstance3D.new()
	_beam.name = "Beam"
	# Луч и пятно — световые эффекты, а не твёрдые части оружия для проверки препятствий.
	_beam.set_meta("weapon_clearance_ignore", true)
	var bm := BoxMesh.new()
	bm.size = Vector3(0.0024, 0.0024, 1.0)
	_beam.mesh = bm
	_beam.material_override = WeaponModels._mat("laser_beam")
	_beam.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(_beam)
	# и линией в пиксель: издалека (изометрия) тонкий брусок рвётся на пунктир, линия — нет
	var line := MeshInstance3D.new()
	line.name = "Line"
	line.set_meta("weapon_clearance_ignore", true)
	var lm := ArrayMesh.new()
	var arr := []
	arr.resize(Mesh.ARRAY_MAX)
	arr[Mesh.ARRAY_VERTEX] = PackedVector3Array([Vector3(0, 0, -0.5), Vector3(0, 0, 0.5)])
	lm.add_surface_from_arrays(Mesh.PRIMITIVE_LINES, arr)
	line.mesh = lm
	line.material_override = WeaponModels._mat("laser_beam")
	line.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_beam.add_child(line)
	_dot = MeshInstance3D.new()
	_dot.name = "Dot"
	_dot.set_meta("weapon_clearance_ignore", true)
	var sm := SphereMesh.new()
	sm.radius = 1.0
	sm.height = 2.0
	sm.radial_segments = 10
	sm.rings = 5
	_dot.mesh = sm
	_dot.material_override = WeaponModels._mat("laser_dot")
	_dot.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_dot.top_level = true
	add_child(_dot)
	_glow = OmniLight3D.new()
	_glow.name = "Glow"
	_glow.light_color = Color(1.0, 0.12, 0.08)
	_glow.light_energy = float(Balance.LASER.light_energy)
	_glow.omni_range = float(Balance.LASER.light_range)
	_glow.light_specular = 0.0
	_glow.set_meta("crisp", true)
	_glow.top_level = true
	add_child(_glow)


func _process(_delta: float) -> void:
	if not is_visible_in_tree() or not is_inside_tree():
		return
	var cfg: Dictionary = Balance.LASER
	var from := global_position
	var axis := global_basis.z
	var k := maxf(axis.length(), 0.0001)
	var dir := axis / k
	var reach := float(cfg.range_m)
	var q := PhysicsRayQueryParameters3D.create(from, from + dir * reach, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DEBRIS)
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	var dist := reach
	var hit_any := not hit.is_empty()
	if hit_any:
		dist = from.distance_to(hit.position)
		var n: Vector3 = hit.normal
		var r := float(cfg.dot_radius) + dist * float(cfg.dot_grow)
		_dot.global_transform = Transform3D(Basis.from_scale(Vector3.ONE * r), hit.position + n * 0.004)
		_glow.global_position = hit.position + n * 0.06
	_dot.visible = hit_any
	_glow.visible = hit_any
	# луч — в локальных единицах узла (модель в руках может быть масштабирована)
	_beam.visible = viewer_nvg
	_beam.scale = Vector3(1.0, 1.0, dist / k)
	_beam.position = Vector3(0.0, 0.0, dist / k * 0.5)
