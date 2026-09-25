class_name GrenadeAim
extends MeshInstance3D
## Прицел гранаты (G зажата): дуга полёта до первого касания и круг поражения там, где упадёт
## (внешний — радиус осколков Balance.GRENADE.radius, внутренний — насмерть GRENADE_LETHAL_M).
## Считается той же физикой, что бросок (гравитация, затухание), до первого удара о стену или пол;
## дальше граната может откатиться. Виден только бросающему.

const LINE_COLOR := Color(1.0, 0.9, 0.55, 0.9)
const RING_COLOR := Color(1.0, 0.35, 0.25, 0.75)
const LETHAL_COLOR := Color(1.0, 0.2, 0.15, 0.35)

var _mesh := ImmediateMesh.new()
var _mat := StandardMaterial3D.new()


func _init() -> void:
	name = "GrenadeAim"
	top_level = true
	mesh = _mesh
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_mat.vertex_color_use_as_albedo = true
	_mat.no_depth_test = true
	_mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	_mat.render_priority = 10
	material_override = _mat
	visible = false


## Дуга из from со скоростью v; mask — во что граната ударится (как у Grenade). Возвращает точку падения.
func show_arc(from: Vector3, v: Vector3, mask: int, exclude: Array[RID]) -> Vector3:
	var aim: Dictionary = Balance.GRENADE_AIM
	var dt := float(aim.step)
	var g := float(ProjectSettings.get_setting("physics/3d/default_gravity"))
	# затухание гранаты (Grenade.linear_damp) плюс общее по проекту
	var damp := 0.15 + float(ProjectSettings.get_setting("physics/3d/default_linear_damp", 0.1))
	var space := get_world_3d().direct_space_state
	var pts: PackedVector3Array = [from]
	var p := from
	var vel := v
	var land := Vector3.INF
	var t := 0.0
	while t < float(aim.max_t):
		vel.y -= g * dt
		vel *= maxf(1.0 - damp * dt, 0.0)
		var nxt := p + vel * dt
		var q := PhysicsRayQueryParameters3D.create(p, nxt, mask, exclude)
		var hit := space.intersect_ray(q)
		if not hit.is_empty():
			land = hit.position
			pts.append(land)
			break
		pts.append(nxt)
		p = nxt
		t += dt
	if land == Vector3.INF:
		land = p
	_draw(pts, land)
	visible = true
	return land


func hide_arc() -> void:
	visible = false


func _draw(pts: PackedVector3Array, land: Vector3) -> void:
	_mesh.clear_surfaces()
	var cam := get_viewport().get_camera_3d()
	var eye := cam.global_position if cam else land + Vector3.UP * 20.0
	var w := float(Balance.GRENADE_AIM.width)
	_mesh.surface_begin(Mesh.PRIMITIVE_TRIANGLES)
	# дуга — лента, развёрнутая к камере; к концу ярче
	for i in range(pts.size() - 1):
		var a := pts[i]
		var b := pts[i + 1]
		var dir := (b - a).normalized()
		var side := dir.cross((eye - a).normalized()).normalized() * w
		var k := float(i) / maxf(1.0, float(pts.size() - 1))
		var c := Color(LINE_COLOR, LINE_COLOR.a * lerpf(0.35, 1.0, k))
		_quad(a - side, a + side, b + side, b - side, c)
	# круги поражения на месте падения
	var lift := land + Vector3.UP * 0.06
	_ring(lift, float(Balance.GRENADE.radius), 0.09, RING_COLOR)
	_disc(lift, Balance.GRENADE_LETHAL_M, LETHAL_COLOR)
	_ring(lift, Balance.GRENADE_LETHAL_M, 0.05, RING_COLOR)
	_mesh.surface_end()


func _quad(a: Vector3, b: Vector3, c: Vector3, d: Vector3, col: Color) -> void:
	for v in [a, b, c, a, c, d]:
		_mesh.surface_set_color(col)
		_mesh.surface_add_vertex(v)


func _ring(center: Vector3, r: float, width: float, col: Color) -> void:
	var n := 64
	for i in range(n):
		var a0 := TAU * float(i) / n
		var a1 := TAU * float(i + 1) / n
		var o0 := Vector3(cos(a0), 0.0, sin(a0))
		var o1 := Vector3(cos(a1), 0.0, sin(a1))
		_quad(center + o0 * (r - width), center + o0 * (r + width), center + o1 * (r + width), center + o1 * (r - width), col)


func _disc(center: Vector3, r: float, col: Color) -> void:
	var n := 32
	for i in range(n):
		var o0 := Vector3(cos(TAU * float(i) / n), 0.0, sin(TAU * float(i) / n)) * r
		var o1 := Vector3(cos(TAU * float(i + 1) / n), 0.0, sin(TAU * float(i + 1) / n)) * r
		for v in [center, center + o0, center + o1]:
			_mesh.surface_set_color(col)
			_mesh.surface_add_vertex(v)
