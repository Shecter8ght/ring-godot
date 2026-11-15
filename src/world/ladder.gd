@tool
class_name Ladder
extends Node3D
## Вертикальная лестница: скобы на стене, пожарная на крышу, на контейнер, на площадку обслуживания.
## Игрок: F у низа или у верха (или Пробел у низа) — схватиться; W / S — вверх и вниз, Shift — быстрее,
## Пробел — спрыгнуть; наверху W — шаг на площадку (Climb), внизу S — сойти. Оружие на время подъёма
## убрано. Мародёры — по связке навигации (группа LINK_GROUP, ведёт их marauder.gd).
## Оси: начало узла — низ лестницы на полу; лестница в плоскости XY; лезут со стороны +Z лицом к −Z
## (к стене); площадка наверху — за лестницей, по −Z, на высоте height. Вид (стойки, перекладины,
## кронштейны) и коллизия стоек строятся из параметров и в сцену не сохраняются — двигать и менять
## размеры в инспекторе (scenes/world/ladder.tscn). Размеры — 1:1: за лестницу берутся руками.

const GROUP := "ladders"
const LINK_GROUP := "ladder_links"
## Сечение стоек и перекладин, м; кронштейны к стене — не реже чем через BRACKET_STEP, м.
const STILE := Vector2(0.05, 0.06)
const RUNG_R := 0.013
const BRACKET_STEP := 1.8

## Высота площадки наверху над низом лестницы, м (куда сходят с верхней ступени).
@export var height: float = 4.0:
	set(v):
		height = clampf(v, 1.0, 30.0)
		queue_build()
## Между стойками, м.
@export var width: float = 0.45:
	set(v):
		width = clampf(v, 0.3, 0.8)
		queue_build()
## Шаг перекладин, м.
@export var rung_step: float = 0.3:
	set(v):
		rung_step = clampf(v, 0.2, 0.45)
		queue_build()
## Стойки выше площадки — поручни, за которые держатся, сходя наверх, м.
@export var extend: float = 1.0:
	set(v):
		extend = clampf(v, 0.0, 1.5)
		queue_build()
## От лестницы до стены, м (кронштейны); 0 — без кронштейнов (стоит сама).
@export var standoff: float = 0.2:
	set(v):
		standoff = clampf(v, 0.0, 0.6)
		queue_build()
## У лестницы с готовой моделью остаются те же точки подъёма и коллизия стоек.
@export var generate_visual: bool = true:
	set(v):
		generate_visual = v
		queue_build()
## При ненулевом значении точки F требуют прямого доступа и подхода ближе этого радиуса.
@export_range(0.0, 1.8) var access_radius: float = 0.0
@export var color: Color = Color(0.3, 0.34, 0.29):
	set(v):
		color = v
		queue_build()

var _gen: Node3D
var _body: StaticBody3D
var _pending: bool = false


func _ready() -> void:
	_build()
	if Engine.is_editor_hint():
		return
	add_to_group(GROUP)
	# где взяться: у низа и у верха — подсказка «F — …» (имена постоянные, у всех peer одинаковые)
	for top: bool in [false, true]:
		var at := LadderPoint.new()
		at.name = "Top" if top else "Bottom"
		at.ladder = self
		at.top = top
		add_child(at)
		at.position = Vector3(0.0, height, -0.7) if top else Vector3(0.0, 0.0, float(Balance.LADDER.body_off) + 0.15)
	# мародёрам — связка навигации снизу на площадку; без площадки наверху — выключена
	var link := NavigationLink3D.new()
	link.name = "NavLink"
	link.bidirectional = true
	link.travel_cost = float(Balance.LADDER.travel_cost)
	link.add_to_group(LINK_GROUP)
	add_child(link)
	link.start_position = Vector3(0.0, 0.0, float(Balance.LADDER.body_off) + 0.3)
	link.end_position = Vector3(0.0, height, -0.75)
	link.enabled = false
	# площадку видно физике только после первых кадров (уровень достраивается)
	await get_tree().physics_frame
	await get_tree().physics_frame
	if is_instance_valid(link) and is_inside_tree():
		link.enabled = not top_exit(get_world_3d().direct_space_state, []).is_empty()


func queue_build() -> void:
	if not is_inside_tree() or _pending:
		return
	_pending = true
	_build.call_deferred()


func _build() -> void:
	_pending = false
	if _gen:
		_gen.free()
	_gen = Node3D.new()
	_gen.name = "_Generated"
	# без owner — сгенерированное не попадает в сохранённую сцену
	add_child(_gen)
	var total := height + extend
	var sx := width * 0.5 + STILE.x * 0.5
	var stile_size := Vector3(STILE.x, total, STILE.y)
	if generate_visual:
		_build_mesh(stile_size, sx)
	# стойки — препятствие для тела и пуль; перекладины не мешают
	_body = StaticBody3D.new()
	_body.name = "Body"
	_body.collision_layer = Hitscan.LAYER_WORLD
	_body.collision_mask = 0
	_gen.add_child(_body)
	for side: float in [-1.0, 1.0]:
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = stile_size
		cs.shape = box
		cs.position = Vector3(side * sx, total * 0.5, 0.0)
		_body.add_child(cs)


func _build_mesh(stile_size: Vector3, sx: float) -> void:
	var total := stile_size.y
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var stile := BoxMesh.new()
	stile.size = stile_size
	for side: float in [-1.0, 1.0]:
		st.append_from(stile, 0, Transform3D(Basis(), Vector3(side * sx, total * 0.5, 0.0)))
	var rung := CylinderMesh.new()
	rung.top_radius = RUNG_R
	rung.bottom_radius = RUNG_R
	rung.height = width
	rung.radial_segments = 8
	rung.rings = 1
	var y := rung_step
	while y <= height + 0.01:
		st.append_from(rung, 0, Transform3D(Basis(Vector3.BACK, PI * 0.5), Vector3(0.0, y, 0.0)))
		y += rung_step
	if standoff > 0.01:
		var bracket := BoxMesh.new()
		bracket.size = Vector3(0.04, 0.05, standoff)
		var n := maxi(2, ceili(total / BRACKET_STEP) + 1)
		for i in range(n):
			var by := lerpf(0.4, minf(height, total - 0.2), float(i) / float(n - 1))
			for side: float in [-1.0, 1.0]:
				st.append_from(bracket, 0, Transform3D(Basis(), Vector3(side * sx, by, -standoff * 0.5 - STILE.y * 0.5)))
	var mi := MeshInstance3D.new()
	mi.name = "Mesh"
	mi.mesh = st.commit()
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.metallic = 0.5
	mat.roughness = 0.6
	mi.material_override = mat
	_gen.add_child(mi)


## Куда смотрит лезущий (к лестнице), по горизонтали.
func facing() -> Vector3:
	var f := -global_basis.z
	f.y = 0.0
	return f.normalized()


## Поворот корпуса лицом к лестнице (как Body.rotation.y у игрока и мародёра).
func facing_yaw() -> float:
	var f := facing()
	return atan2(f.x, f.z)


## Где ноги лезущего на высоте y над низом лестницы.
func line_point(y: float) -> Vector3:
	return to_global(Vector3(0.0, y, float(Balance.LADDER.body_off)))


## Выше ноги не встают: верхняя ступень под площадкой.
func feet_top() -> float:
	return maxf(0.0, height - float(Balance.LADDER.top_gap))


## Высота ног p над низом лестницы.
func feet_at(p: Vector3) -> float:
	return to_local(p).y


func body_rid() -> RID:
	return _body.get_rid() if _body else RID()


## Сойти наверх с верхней ступени: путь Climb на площадку; {} — площадки нет (лестница в никуда, люк).
func top_exit(space: PhysicsDirectSpaceState3D, exclude: Array[RID]) -> Dictionary:
	var ex := exclude.duplicate()
	ex.append(body_rid())
	return Climb.find(space, line_point(feet_top()), facing(), ex, -1.0, 1.4)


## Можно ли схватиться снизу (Пробел): стоит перед лестницей, рядом и лицом к ней.
func can_grab(p: Vector3, look: Vector3) -> bool:
	var local := to_local(p)
	if local.z < 0.0 or local.y < -0.4 or local.y > feet_top():
		return false
	var line := line_point(clampf(local.y, 0.0, feet_top()))
	look.y = 0.0
	return Vector2(p.x - line.x, p.z - line.z).length() <= float(Balance.LADDER.grab_m) \
		and look.normalized().dot(facing()) > 0.5


## Мародёр по связке навигации: шаги [{path, sec}] — подойти, лезть, сойти (вверх) или наоборот.
## Пусто — площадки нет, пройти нельзя.
func ai_steps(up: bool, from: Vector3, space: PhysicsDirectSpaceState3D, exclude: Array[RID]) -> Array:
	var cfg: Dictionary = Balance.LADDER
	var exit := top_exit(space, exclude)
	if exit.is_empty():
		return []
	var lo := line_point(0.0)
	var hi := line_point(feet_top())
	var enter := float(cfg.enter_sec)
	var over := float(Balance.CLIMB.sec_low) * 1.3
	if up:
		return [{"path": {"pts": PackedVector3Array([from, lo])}, "sec": enter},
			{"path": {"pts": PackedVector3Array([lo, hi]), "linear": true}, "sec": feet_top() / float(cfg.ai_mps)},
			{"path": exit, "sec": over}]
	var down := PackedVector3Array([from])
	var back: PackedVector3Array = (exit.pts as PackedVector3Array).duplicate()
	back.reverse()
	down.append_array(back)
	var down_mps := float(cfg.ai_mps) * float(cfg.down_mps) / float(cfg.up_mps)
	return [{"path": {"pts": down}, "sec": over + enter},
		{"path": {"pts": PackedVector3Array([hi, lo]), "linear": true}, "sec": feet_top() / down_mps},
		{"path": {"pts": PackedVector3Array([lo, lo - facing() * 0.35])}, "sec": enter}]


## Свой игрок на этом peer (у него клавиши).
static func local_player(tree: SceneTree) -> Player:
	for n in tree.get_nodes_in_group("players"):
		var pl := n as Player
		if pl and pl.is_local():
			return pl
	return null
