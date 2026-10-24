extends Node3D
## Стенд масштаба (вопрос владельца 2026-10-24: «реальные размеры в игре выглядят мелкими»).
## Три одинаковых набора рядом: A — всё 1:1; B — предметы 1:1, проходы и помещения × 1,2 (ширина и высота
## проёмов, комнат, коридора, прохода между стеллажами, тротуара); C — всё × 1,3. В каждом: кусок улицы
## (тротуар с бордюром, фонарь, ларёк, остановка, лавка, бетонный барьер, конус, машина), комната с дверью,
## коридор, два стеллажа супермаркета, лестница и фигура ростом 1,75 м для сравнения.
## Клавиши: F1 / F2 / F3 — поле зрения 75 / 80 / 90° по горизонтали (не сохраняется в настройки),
## F5 / F6 / F7 — перенестись к набору A / B / C. Настоящий игрок, камера и скорость игры.
## godot --windowed --resolution 1600x900 res://tools/scale_probe.tscn
## SCALE_PROBE_SHOTS=1 — снимки каждого набора при 75 и 90° → docs/screens/scale_probe_*.png, выход.

const PITCH := 32.0            # шаг между наборами по X, м
const FOVS := [75.0, 80.0, 90.0]

var _props: Node3D
var _label: Label
var _mats: Dictionary = {}
var _fov_saved: float = 90.0
var _stations: Array[Vector3] = []
var _origins: Array[Vector3] = []


func _ready() -> void:
	_props = $Props
	_fov_saved = Settings.fov_h
	_mats = {
		"wall": _mat(Color(0.62, 0.6, 0.56)), "floor": _mat(Color(0.5, 0.49, 0.46)), "walk": _mat(Color(0.66, 0.64, 0.6)),
		"curb": _mat(Color(0.78, 0.77, 0.73)), "asphalt": _mat(Color(0.3, 0.31, 0.32)), "shelf": _mat(Color(0.48, 0.36, 0.24)),
		"kiosk": _mat(Color(0.75, 0.62, 0.35)), "glass": _mat(Color(0.55, 0.7, 0.8, 0.55), true), "metal": _mat(Color(0.35, 0.37, 0.4)),
		"jersey": _mat(Color(0.7, 0.68, 0.62)), "cone": _mat(Color(0.95, 0.45, 0.15)), "man": _mat(Color(0.25, 0.45, 0.7)),
		"sign": _mat(Color(0.9, 0.85, 0.3)), "bench": _mat(Color(0.4, 0.3, 0.2)),
	}
	# A: всё 1:1; B: предметы 1:1, проходы × 1,2; C: всё × 1,3
	_station(Vector3(-PITCH, 0, 0), 1.0, 1.0, "A — всё 1:1 (реальные размеры)")
	_station(Vector3(0, 0, 0), 1.0, 1.2, "B — предметы 1:1, проходы и помещения × 1,2")
	_station(Vector3(PITCH, 0, 0), 1.3, 1.3, "C — всё × 1,3")
	_hud()
	_set_fov(90.0)
	if OS.get_environment("SCALE_PROBE_SHOTS") == "1":
		_shots()


func _exit_tree() -> void:
	Settings.fov_h = _fov_saved


## Один набор. ok — множитель предметов, sp — множитель проходов и помещений.
func _station(o: Vector3, ok: float, sp: float, title: String) -> void:
	_stations.append(o + Vector3(0, 0, 6.0))
	_origins.append(o)
	# --- улица (z от 0 к −8): проезжая часть, бордюр, тротуар
	_box("asphalt", o + Vector3(0, -0.05, -2.5 * sp), Vector3(26, 0.1, 7.0))
	_box("walk", o + Vector3(0, 0.0, 2.0 * sp), Vector3(26, 0.15 * ok, 3.0 * sp))
	_box("curb", o + Vector3(0, 0.0, 0.5 * sp), Vector3(26, 0.15 * ok, 0.2 * ok))
	# фонарь 9 м, ларёк 2×3×2,5, остановка 4×1,5×2,6, лавка, барьер 0,8, конус 0,7, машина
	_box("metal", o + Vector3(-12.5, 4.5 * ok, 0.9 * sp), Vector3(0.18 * ok, 9.0 * ok, 0.18 * ok))
	_box("metal", o + Vector3(-11.8, 8.9 * ok, 0.9 * sp), Vector3(1.6 * ok, 0.12 * ok, 0.25 * ok))
	_box("kiosk", o + Vector3(-10, 1.25 * ok, 2.4 * sp), Vector3(3.0 * ok, 2.5 * ok, 2.0 * ok))
	_box("glass", o + Vector3(-2, 1.3 * ok, 2.6 * sp), Vector3(4.0 * ok, 2.6 * ok, 0.06 * ok))
	_box("metal", o + Vector3(-2, 2.6 * ok, 2.0 * sp), Vector3(4.2 * ok, 0.08 * ok, 1.6 * ok))
	_box("bench", o + Vector3(-2, 0.45 * ok, 1.6 * sp), Vector3(1.8 * ok, 0.05 * ok, 0.45 * ok))
	_box("jersey", o + Vector3(3, 0.4 * ok, -1.2 * sp), Vector3(2.0 * ok, 0.8 * ok, 0.5 * ok))
	_box("cone", o + Vector3(5, 0.35 * ok, -1.5 * sp), Vector3(0.35 * ok, 0.7 * ok, 0.35 * ok))
	_car(o + Vector3(9, 0, -2.5 * sp), ok)
	# фигура 1,75 м — рост человека, для сравнения
	_box("man", o + Vector3(1, 0.875, 2.2 * sp), Vector3(0.45, 1.75, 0.3))
	_box("man", o + Vector3(1, 1.63, 2.2 * sp), Vector3(0.22, 0.24, 0.22))
	# --- комната 4×5, потолок 2,7, дверь 0,9×2,1 в стене к улице (z 4…9)
	var rw := 4.0 * sp
	var rd := 5.0 * sp
	var rh := 2.7 * (sp if sp < 1.25 else 1.3) if sp > 1.0 else 2.7
	if sp > 1.0 and ok == 1.0:
		rh = 2.7 * 1.1          # у B потолок × 1,1, не × 1,2
	var rc := o + Vector3(-6, 0, 4.0 * sp + rd * 0.5)
	var t := 0.15
	_box("floor", rc + Vector3(0, -0.02, 0), Vector3(rw + 2 * t, 0.04, rd + 2 * t))
	_box("wall", rc + Vector3(0, rh + t * 0.5, 0), Vector3(rw + 2 * t, t, rd + 2 * t))          # потолок
	_box("wall", rc + Vector3(-rw * 0.5 - t * 0.5, rh * 0.5, 0), Vector3(t, rh, rd + 2 * t))
	_box("wall", rc + Vector3(rw * 0.5 + t * 0.5, rh * 0.5, 0), Vector3(t, rh, rd + 2 * t))
	_box("wall", rc + Vector3(0, rh * 0.5, rd * 0.5 + t * 0.5), Vector3(rw + 2 * t, rh, t))
	# стена к улице с дверью: ширина 0,9 × высота 2,1 (у B × 1,2 — 1,08 × 2,3; у C — 1,17 × 2,73)
	var dw := 0.9 * sp
	var dh := 2.1 * (sp if sp > 1.0 else 1.0)
	if sp > 1.0 and ok == 1.0:
		dh = 2.3
	_wall_with_door(rc + Vector3(0, 0, -rd * 0.5 - t * 0.5), rw + 2 * t, rh, t, dw, dh)
	_lamp(rc + Vector3(0, rh - 0.3, 0))
	# внутри: стол и шкаф в реальных размерах
	_box("shelf", rc + Vector3(rw * 0.5 - 0.3 * ok, 1.0 * ok, 0.5), Vector3(0.6 * ok, 2.0 * ok, 1.2 * ok))
	_box("bench", rc + Vector3(-rw * 0.5 + 0.8 * ok, 0.75 * ok, -1.0), Vector3(1.4 * ok, 0.04 * ok, 0.7 * ok))
	# --- коридор 1,5 × 2,7, длина 6 (от комнаты вглубь по z)
	var cw := 1.5 * sp
	var cc := rc + Vector3(rw * 0.5 + t + cw * 0.5 + 0.5, 0, 0)
	_box("floor", cc + Vector3(0, -0.02, 0), Vector3(cw + 2 * t, 0.04, 6.0))
	_box("wall", cc + Vector3(-cw * 0.5 - t * 0.5, rh * 0.5, 0), Vector3(t, rh, 6.0))
	_box("wall", cc + Vector3(cw * 0.5 + t * 0.5, rh * 0.5, 0), Vector3(t, rh, 6.0))
	_box("wall", cc + Vector3(0, rh + t * 0.5, 0), Vector3(cw + 2 * t, t, 6.0))
	_lamp(cc + Vector3(0, rh - 0.3, 0))
	# --- стеллажи супермаркета: 0,6 × 4 × 1,8 (у B проход 1,6 × 1,3 = 2,1 — как в магазинах с широкими рядами)
	var aisle := 1.6 * (1.3 if sp > 1.0 and ok == 1.0 else sp)
	var sc := o + Vector3(5, 0, 7.0 * sp)
	_box("shelf", sc + Vector3(-aisle * 0.5 - 0.3 * ok, 0.9 * ok, 0), Vector3(0.6 * ok, 1.8 * ok, 4.0 * ok))
	_box("shelf", sc + Vector3(aisle * 0.5 + 0.3 * ok, 0.9 * ok, 0), Vector3(0.6 * ok, 1.8 * ok, 4.0 * ok))
	# --- лестница: 8 ступеней 0,15 × 0,3 (× ok), ширина 1,2 (× sp)
	var lc := o + Vector3(10, 0, 5.0 * sp)
	for i in range(8):
		_box("floor", lc + Vector3(0, 0.15 * ok * (i + 0.5), 0.3 * ok * i), Vector3(1.2 * sp, 0.15 * ok, 0.3 * ok))
	# подпись набора
	_sign(o + Vector3(0, 3.2, 3.6 * sp), title)


func _wall_with_door(c: Vector3, w: float, h: float, t: float, dw: float, dh: float) -> void:
	var side := (w - dw) * 0.5
	_box("wall", c + Vector3(-dw * 0.5 - side * 0.5, h * 0.5, 0), Vector3(side, h, t))
	_box("wall", c + Vector3(dw * 0.5 + side * 0.5, h * 0.5, 0), Vector3(side, h, t))
	_box("wall", c + Vector3(0, dh + (h - dh) * 0.5, 0), Vector3(dw, h - dh, t))
	# коробка двери — чтобы проём читался
	_box("bench", c + Vector3(-dw * 0.5 - 0.03, dh * 0.5, 0), Vector3(0.06, dh, t + 0.02))
	_box("bench", c + Vector3(dw * 0.5 + 0.03, dh * 0.5, 0), Vector3(0.06, dh, t + 0.02))
	_box("bench", c + Vector3(0, dh + 0.03, 0), Vector3(dw + 0.12, 0.06, t + 0.02))


func _car(at: Vector3, k: float) -> void:
	var sc: PackedScene = load("res://scenes/props/coupe_ilya.tscn")
	if sc == null:
		_box("metal", at + Vector3(0, 0.7 * k, 0), Vector3(4.9 * k, 1.4 * k, 1.9 * k))
		return
	var car: Node3D = sc.instantiate()
	_props.add_child(car)
	car.global_position = at
	car.rotation.y = PI * 0.5
	car.scale = Vector3.ONE * k
	if car.has_method("set") and "hood_open" in car:
		car.set("hood_open", false)


func _lamp(at: Vector3) -> void:
	var l := OmniLight3D.new()
	l.light_energy = 2.0
	l.omni_range = 7.0
	l.light_color = Color(1.0, 0.93, 0.8)
	l.shadow_enabled = true
	_props.add_child(l)
	l.global_position = at


func _sign(at: Vector3, text: String) -> void:
	var l := Label3D.new()
	l.text = text
	l.font_size = 64
	l.pixel_size = 0.01
	l.modulate = Color(1.0, 0.95, 0.6)
	l.outline_size = 12
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = true
	_props.add_child(l)
	l.global_position = at


func _mat(c: Color, transparent: bool = false) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = 0.9
	if transparent:
		m.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	return m


func _box(mat: String, at: Vector3, size: Vector3) -> void:
	var body := StaticBody3D.new()
	var mi := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mi.mesh = mesh
	mi.material_override = _mats[mat]
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
		_label.text = ("Стенд масштаба · поле зрения %d° по горизонтали (F1 — 75°, F2 — 80°, F3 — 90°)\n"
			+ "F5 / F6 / F7 — к набору A / B / C · A — всё 1:1 · B — предметы 1:1, проходы × 1,2 · C — всё × 1,3\n"
			+ "глаз %.2f м, шаг %.2f м/с, бег %.1f м/с") % [int(Settings.fov_h), Balance.ADS_EYE["stand"],
			Balance.PLAYER_WALK_SPEED, Balance.PLAYER_SPRINT_SPEED]


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


func _teleport(i: int) -> void:
	var pl := get_tree().get_first_node_in_group("players") as Node3D
	if pl and i < _stations.size():
		pl.global_position = _stations[i] + Vector3(0, 0.1, 0)


func _shots() -> void:
	for i in range(30):
		await get_tree().process_frame
	var pl := get_tree().get_first_node_in_group("players") as Player
	var rig := get_tree().get_first_node_in_group("camera_rig") as CameraRig
	for i in range(3):
		var tag: String = ["a", "b", "c"][i]
		var o := _origins[i]
		for fov: float in [75.0, 90.0]:
			_set_fov(fov)
			# от тротуара к двери комнаты (вид в комнату мимо фигуры)
			pl.global_position = o + Vector3(-6, 0.1, -1.5)
			var look := o + Vector3(-6, 1.3, 6.0)
			for k in range(5):
				await get_tree().process_frame
			var d := look - pl.eye_position()
			rig._look_yaw = atan2(d.x, d.z)
			rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
			for k in range(40):
				await get_tree().process_frame
			_save("scale_probe_%s_%d_door" % [tag, int(fov)])
			# вдоль улицы: ларёк, остановка, машина
			pl.global_position = o + Vector3(-13, 0.1, -4.0)
			look = o + Vector3(9, 1.0, 0.0)
			for k in range(5):
				await get_tree().process_frame
			d = look - pl.eye_position()
			rig._look_yaw = atan2(d.x, d.z)
			rig._look_pitch = atan2(d.y, Vector2(d.x, d.z).length())
			for k in range(40):
				await get_tree().process_frame
			_save("scale_probe_%s_%d_street" % [tag, int(fov)])
	get_tree().quit(0)


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("scale_probe: ", n)
