extends Node3D
## Стенд высоты подземного паркинга (владелец 2026-10-29: «высота паркинга должна быть раза в 3–4 выше, колонны — как на
## подземном паркинге в Таркове»). Пять одинаковых кусков паркинга −1 «Проспекта» рядом: места 2,5 × 5,3 м, проезды
## 7,8 м, колонны по линии «спина к спине» через три места (tools/build_prospekt.py, PIT / BAY / STALL_D / AISLE).
##   A — как сейчас на карте: 2,8 м в свету, колонны 0,5 м, гладкий потолок;
##   B — те же 2,8 м в свету, но с отделкой как в Таркове: колонны 0,9 м с капителями и разметкой, балки 0,9 м,
##       воздуховод над проездом, трубы, кабельные лотки, лампы (часть не горит);
##   C, D, E — та же отделка, в свету под балками 4,5 / 6 / 9 м.
## Отделить, что даёт «таркованский» вид — высота или отделка: A и B одной высоты, B…E — одной отделки.
## Клавиши: F1 / F2 / F3 — поле зрения 75 / 80 / 90°, F5 … F9 — к залу A … E. Настоящий игрок и камера.
## godot --windowed --resolution 1600x900 res://tools/parking_probe.tscn
## PARKING_PROBE_SHOTS=1 — снимки каждого зала (вдоль проезда, поперёк к линии колонн) → docs/screens/parking_probe_*.png

const PITCH := 50.0            # шаг между залами по X, м
const LEN := 40.0              # длина зала: пять пролётов по 8 м
const BAY := 8.0               # колонна + три места по 2,5
const STALL_D := 5.3
const AISLE := 7.8
const BEAM_D := 0.9            # глубина балки в отделке «как в Таркове»
const WALL_T := 0.4
const CARS := ["res://assets/models/prospekt_vehicles/PV_sedan.gltf", "res://assets/models/prospekt_vehicles/PV_hatch.gltf",
	"res://assets/models/prospekt_vehicles/PV_wagon.gltf", "res://assets/models/prospekt_vehicles/PV_suv.gltf"]

var _props: Node3D
var _label: Label
var _mats: Dictionary = {}
var _fov_saved: float = 90.0
var _stations: Array[Vector3] = []
var _origins: Array[Vector3] = []
var _clears: Array[float] = []
var _cars: Array[PackedScene] = []
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_props = $Props
	_fov_saved = Settings.fov_h
	_rng.seed = 2910
	for path: String in CARS:
		if ResourceLoader.exists(path):
			_cars.append(load(path) as PackedScene)
	_mats = {
		"floor": _mat(Color(0.33, 0.33, 0.32), 0.95), "wall": _mat(Color(0.56, 0.55, 0.52)), "ceiling": _mat(Color(0.45, 0.45, 0.44)),
		"column": _mat(Color(0.6, 0.59, 0.56)), "beam": _mat(Color(0.5, 0.5, 0.48)), "yellow": _mat(Color(0.85, 0.66, 0.08)),
		"black": _mat(Color(0.06, 0.06, 0.06)), "line": _mat(Color(0.82, 0.82, 0.78)), "duct": _mat(Color(0.56, 0.58, 0.6), 0.75, 0.25),
		"pipe_red": _mat(Color(0.62, 0.1, 0.08), 0.6), "tray": _mat(Color(0.4, 0.42, 0.44), 0.5, 0.7), "man": _mat(Color(0.25, 0.45, 0.7)),
		"lamp": _lamp_mat(true), "lamp_off": _lamp_mat(false), "green": _mat(Color(0.1, 0.55, 0.25)),
	}
	_hall(Vector3(-2.0 * PITCH, 0, 0), 2.8, false, "A — как сейчас: 2,8 м в свету, колонны 0,5 м, гладкий потолок")
	_hall(Vector3(-1.0 * PITCH, 0, 0), 2.8, true, "B — 2,8 м в свету под балками, отделка как в Таркове")
	_hall(Vector3(0.0, 0, 0), 4.5, true, "C — 4,5 м в свету под балками (до плиты 5,4)")
	_hall(Vector3(1.0 * PITCH, 0, 0), 6.0, true, "D — 6 м в свету под балками (до плиты 6,9)")
	_hall(Vector3(2.0 * PITCH, 0, 0), 9.0, true, "E — 9 м в свету под балками (до плиты 9,9) — «в 3 раза выше»")
	_hud()
	_set_fov(80.0)
	_teleport(1)
	if OS.get_environment("PARKING_PROBE_SHOTS") == "1":
		_shots()


func _exit_tree() -> void:
	Settings.fov_h = _fov_saved


## Один зал. clear — высота в свету (у A — до гладкого потолка, у остальных — под балками); styled — отделка как в Таркове.
## Местные оси: X — вдоль зала (0…LEN), Z — поперёк: ряд A у стены, проезд, ряд B | линия колонн | ряд C, проезд, ряд D.
func _hall(o: Vector3, clear: float, styled: bool, title: String) -> void:
	var depth := STALL_D * 4.0 + AISLE * 2.0
	var slab_h := clear + (BEAM_D if styled else 0.0)
	var col_z := STALL_D * 2.0 + AISLE
	var aisles := [STALL_D + AISLE * 0.5, depth - STALL_D - AISLE * 0.5]
	_origins.append(o)
	_clears.append(clear)
	_stations.append(o + Vector3(3.0, 0.1, aisles[0]))
	# пол, плита, стены
	_box("floor", o + Vector3(LEN * 0.5, -0.1, depth * 0.5), Vector3(LEN + WALL_T * 2.0, 0.2, depth + WALL_T * 2.0))
	_box("ceiling", o + Vector3(LEN * 0.5, slab_h + 0.15, depth * 0.5), Vector3(LEN + WALL_T * 2.0, 0.3, depth + WALL_T * 2.0))
	for z: float in [-WALL_T * 0.5, depth + WALL_T * 0.5]:
		_box("wall", o + Vector3(LEN * 0.5, slab_h * 0.5, z), Vector3(LEN + WALL_T * 2.0, slab_h, WALL_T))
	for x: float in [-WALL_T * 0.5, LEN + WALL_T * 0.5]:
		_box("wall", o + Vector3(x, slab_h * 0.5, depth * 0.5), Vector3(WALL_T, slab_h, depth))
	# разметка: места поперёк рядов, линии кромки проездов
	for row_z: Array in [[0.0, STALL_D], [STALL_D + AISLE, col_z], [col_z, col_z + STALL_D], [depth - STALL_D, depth]]:
		var z0: float = row_z[0]
		var z1: float = row_z[1]
		# между колоннами (через 8 м, первая — на 4 м) три места по 2,5: линии на 4,25 + 8k + 2,5j
		for bay: int in range(int(LEN / BAY)):
			for j: int in range(4):
				var x := 4.25 + bay * BAY + j * 2.5
				if x < LEN - 0.2:
					_box("line", o + Vector3(x, 0.01, (z0 + z1) * 0.5), Vector3(0.1, 0.02, z1 - z0 - 0.3), false)
	for az: float in aisles:
		_box("line", o + Vector3(LEN * 0.5, 0.01, az), Vector3(LEN - 2.0, 0.02, 0.12), false)
	# колонны по линии «спина к спине» через три места
	var k := 0
	var cx := 4.0
	while cx < LEN:
		_column(o + Vector3(cx, 0, col_z), slab_h, styled, "B%d" % (k + 1))
		cx += BAY
		k += 1
	if styled:
		# балки: поперёк зала на линиях колонн (до стен) и вдоль по линии колонн; капители под плитой
		cx = 4.0
		while cx < LEN:
			_box("beam", o + Vector3(cx, slab_h - BEAM_D * 0.5, depth * 0.5), Vector3(0.6, BEAM_D, depth), false)
			cx += BAY
		_box("beam", o + Vector3(LEN * 0.5, slab_h - BEAM_D * 0.5, col_z), Vector3(LEN, BEAM_D, 0.6), false)
		for wz: float in [0.3, depth - 0.3]:
			_box("beam", o + Vector3(LEN * 0.5, slab_h - BEAM_D * 0.5, wz), Vector3(LEN, BEAM_D, 0.6), false)
		# воздуховод у кромки первого проезда над носами машин (под балками, в стороне от ламп), красная труба
		# спринклеров над каждым рядом, лотки у стен
		_box("duct", o + Vector3(LEN * 0.5, clear - 0.3, STALL_D + AISLE - 0.9), Vector3(LEN, 0.5, 1.2), false)
		for pz: float in [STALL_D * 0.5, col_z - STALL_D * 0.5, col_z + STALL_D * 0.5, depth - STALL_D * 0.5]:
			_pipe(o + Vector3(LEN * 0.5, clear - 0.12, pz), LEN, 0.07, "pipe_red")
		for tz: float in [0.35, depth - 0.35]:
			_box("tray", o + Vector3(LEN * 0.5, clear - 0.25, tz + (0.3 if tz < 1.0 else -0.3)), Vector3(LEN, 0.08, 0.45), false)
		# указатель выезда — зелёный короб над проездом
		_box("green", o + Vector3(LEN - 6.0, clear - 0.35, aisles[1]), Vector3(1.6, 0.4, 0.12), false)
		_text(o + Vector3(LEN - 6.0, clear - 0.35, aisles[1] - 0.08), "ВЫЕЗД →", 48, false)
	# свет: полосы над проездами через пролёт; каждая третья не горит
	var n := 0
	for az: float in aisles:
		var lx := 4.0
		while lx < LEN:
			var lit := n % 3 != 2
			var ly := clear - 0.06                                 # у низа балок (или потолка), рядом с воздуховодом
			_box("lamp" if lit else "lamp_off", o + Vector3(lx, ly, az), Vector3(1.4, 0.07, 0.22), false)
			if lit:
				var l := OmniLight3D.new()
				l.light_energy = 1.4
				l.omni_range = 9.0 + clear
				l.light_color = Color(0.92, 0.97, 1.0)
				l.shadow_enabled = n % 4 == 0
				_props.add_child(l)
				l.global_position = o + Vector3(lx, ly - 0.2, az)
			lx += BAY
			n += 1
	# машины на половине мест — носом к стене или к линии колонн
	for row: Array in [[0.0, STALL_D, 0.0], [STALL_D + AISLE, col_z, PI], [col_z, col_z + STALL_D, 0.0], [depth - STALL_D, depth, PI]]:
		for bay: int in range(int(LEN / BAY)):
			for j: int in range(3):
				var x := 5.5 + bay * BAY + j * 2.5
				if x < LEN - 1.3 and _rng.randf() < 0.55:
					_car(o + Vector3(x, 0.0, (float(row[0]) + float(row[1])) * 0.5), float(row[2]) + _rng.randf_range(-0.06, 0.06))
	# фигура 1,75 м у края проезда — для сравнения; подпись зала
	_box("man", o + Vector3(10.0, 0.875, aisles[0] - 2.2), Vector3(0.5, 1.75, 0.3))
	_text(o + Vector3(LEN - 1.5, minf(clear - 0.4, 2.4), aisles[0]), title, 40, true)


## Колонна: тонкая (как сейчас) или 0,9 м с капителью, разметкой низа и номером на гранях.
func _column(at: Vector3, slab_h: float, styled: bool, tag: String) -> void:
	if not styled:
		_box("column", at + Vector3(0, slab_h * 0.5, 0), Vector3(0.5, slab_h, 0.5))
		return
	_box("column", at + Vector3(0, slab_h * 0.5, 0), Vector3(0.9, slab_h, 0.9))
	_box("ceiling", at + Vector3(0, slab_h - 0.2, 0), Vector3(2.4, 0.4, 2.4), false)
	# нижний метр — жёлто-чёрная разметка от бамперов
	for i in range(6):
		_box("yellow" if i % 2 == 0 else "black", at + Vector3(0, 0.1 + i * 0.2, 0), Vector3(0.92, 0.2, 0.92), false)
	for f: Vector3 in [Vector3(0, 0, 0.47), Vector3(0, 0, -0.47), Vector3(0.47, 0, 0), Vector3(-0.47, 0, 0)]:
		var t := Label3D.new()
		t.text = tag
		t.font_size = 96
		t.pixel_size = 0.004
		t.modulate = Color(0.08, 0.08, 0.08)
		_props.add_child(t)
		t.global_position = at + f + Vector3(0, 2.0, 0)
		t.look_at(t.global_position + f, Vector3.UP)
		t.rotate_object_local(Vector3.UP, PI)


func _car(at: Vector3, yaw: float) -> void:
	if _cars.is_empty():
		_box("duct", at + Vector3(0, 0.75, 0), Vector3(1.9, 1.5, 4.5))
		return
	var car := _cars[_rng.randi_range(0, _cars.size() - 1)].instantiate() as Node3D
	_props.add_child(car)
	car.global_position = at
	car.rotation.y = yaw


func _pipe(at: Vector3, length: float, r: float, mat: String) -> void:
	var mi := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = r
	mesh.bottom_radius = r
	mesh.height = length
	mesh.radial_segments = 10
	mi.mesh = mesh
	mi.material_override = _mats[mat]
	_props.add_child(mi)
	mi.global_position = at
	mi.rotation.z = PI * 0.5


func _text(at: Vector3, text: String, size: int, billboard: bool) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = size
	l.pixel_size = 0.006
	l.modulate = Color(1.0, 0.95, 0.6) if billboard else Color(0.9, 1.0, 0.9)
	l.outline_size = 10
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED if billboard else BaseMaterial3D.BILLBOARD_DISABLED
	_props.add_child(l)
	l.global_position = at


func _mat(c: Color, rough: float = 0.9, metal: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	return m


func _lamp_mat(lit: bool) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = Color(0.9, 0.93, 0.95)
	if lit:
		m.emission_enabled = true
		m.emission = Color(0.92, 0.97, 1.0)
		m.emission_energy_multiplier = 4.0
	return m


func _box(mat: String, at: Vector3, size: Vector3, solid: bool = true) -> void:
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = _mats[mat]
	if not solid:
		_props.add_child(mi)
		mi.global_position = at
		return
	var body := StaticBody3D.new()
	var cs := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	cs.shape = shape
	body.add_child(mi)
	body.add_child(cs)
	_props.add_child(body)
	body.global_position = at


func _hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 50
	add_child(layer)
	_label = Label.new()
	_label.position = Vector2(16, 16)
	_label.add_theme_font_size_override("font_size", 18)
	_label.add_theme_color_override("font_color", Color(1.0, 0.95, 0.7))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0))
	_label.add_theme_constant_override("outline_size", 4)
	layer.add_child(_label)
	_update_label()


func _set_fov(h: float) -> void:
	Settings.fov_h = h          # без save(): настройки игрока не трогаем
	_update_label()


func _update_label() -> void:
	if _label:
		_label.text = ("Стенд высоты паркинга · поле зрения %d° (F1 — 75°, F2 — 80°, F3 — 90°) · F5 … F9 — к залу A … E\n"
			+ "A как сейчас 2,8 м · B 2,8 м с отделкой как в Таркове · C 4,5 м · D 6 м · E 9 м (в свету под балками)") % int(Settings.fov_h)


func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey and event.pressed and not event.echo):
		return
	match (event as InputEventKey).keycode:
		KEY_F1:
			_set_fov(75.0)
		KEY_F2:
			_set_fov(80.0)
		KEY_F3:
			_set_fov(90.0)
		KEY_F5:
			_teleport(0)
		KEY_F6:
			_teleport(1)
		KEY_F7:
			_teleport(2)
		KEY_F8:
			_teleport(3)
		KEY_F9:
			_teleport(4)


func _teleport(i: int) -> void:
	var pl := get_tree().get_first_node_in_group("players") as Node3D
	if pl and i < _stations.size():
		pl.global_position = _stations[i]


func _shots() -> void:
	for i in range(60):
		await get_tree().process_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	var depth := STALL_D * 4.0 + AISLE * 2.0
	var col_z := STALL_D * 2.0 + AISLE
	for i in range(_origins.size()):
		var tag: String = ["a", "b", "c", "d", "e"][i]
		var o := _origins[i]
		var a0 := STALL_D + AISLE * 0.5
		# вдоль проезда — до дальней стены; поперёк — от проезда к линии колонн и второму проезду
		for view: Array in [["aisle", Vector3(1.5, 0.1, a0), Vector3(LEN, 1.4, a0)],
				["across", Vector3(18.0, 0.1, 2.5), Vector3(22.0, _clears[i] * 0.45, depth - 2.0)],
				["column", Vector3(9.0, 0.1, a0 + 1.5), Vector3(12.0, _clears[i] * 0.6, col_z)]]:
			pl.global_position = o + (view[1] as Vector3)
			for k in range(5):
				await get_tree().process_frame
			var d := o + (view[2] as Vector3) - pl.eye_position()
			rig._look_yaw = atan2(d.x, d.z)
			rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
			for k in range(60):
				await get_tree().process_frame
			_save("parking_probe_%s_%s" % [tag, String(view[0])])
	get_tree().quit(0)


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("parking_probe: ", n)
