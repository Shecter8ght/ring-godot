extends Node3D
## Стенд анимаций персонажа: одни и те же программы движения у двух рядов фигур — ближний ряд с
## новой анимацией (смесь направлений, шаг под скорость, живость поверх клипов), дальний — «как
## было» (один клип на направление, без подгонки шага и без живости). Пол в клетку 0.5 м — по ней
## видно, скользят ли ступни.
## Управление: ЛКМ — вращать, колесо — ближе/дальше, 1–5 — к фигуре программы (ещё раз — к «как было»),
## 0 — обзор, Z — замедление ×4, Пробел — пауза, H — подсказка.
## tools/godot.cmd res://tools/anim_stand.tscn
## Снимки: … --windowed --resolution 1600x900 res://tools/anim_stand.tscn -- shots → docs/screens/anim_stand_*.png
## Замер: … --headless res://tools/anim_stand.tscn -- verify — скольжение опорной ступни по полу у
## новой анимации и «как было», ствол за взглядом.

const PROGRAMS := ["circle", "lines", "strafe", "turns", "shooter"]
const TITLES := {"circle": "по кругу: шаг, бег, спринт", "lines": "прямые: вперёд, назад, вбок, наискосок", "strafe": "8 направлений подряд, присед", "turns": "повороты, старт и стоп", "shooter": "взгляд, выглядывание, огонь"}
const SPACING := 9.0
const ROW_GAP := 9.0
## Лодыжка стоящей на полу ступни Persona — 6–8 см над полом, м.
const PLANTED := 0.085
## Левая кисть на цевье: допустимо мимо метки хвата, м.
const HAND_MAX := 0.06
## Допустимое скольжение опорной ступни у новой анимации, м/с (замер по лодыжке: перекат с пятки на
## носок сам даёт ~0.2). Повороты и остановки ещё скользят — нужны клипы «стоп» или ИК ступней,
## там новая пока не обязана быть лучше прежней.
const SLIDE_MAX := {"circle": 0.35, "lines": 0.35, "strafe": 0.5, "turns": 1.1, "shooter": 0.15}

var _puppets: Dictionary = {}
var _labels: Dictionary = {}
var _cam: Camera3D
var _target: Vector3 = Vector3.ZERO
var _yaw: float = 0.6
var _pitch: float = -0.35
var _dist: float = 30.0
var _drag: bool = false
var _slow: bool = false
var _help: Label
var _focus: String = ""


func _ready() -> void:
	_build_world()
	for i in range(PROGRAMS.size()):
		var prog: String = PROGRAMS[i]
		for legacy: bool in [false, true]:
			var p := AnimPuppet.new()
			p.program = prog
			p.legacy = legacy
			p.name = "%s_%s" % [prog, "old" if legacy else "new"]
			p.position = Vector3((float(i) - 2.0) * SPACING, 0.0, ROW_GAP if legacy else 0.0)
			# лицом к камере (камера со стороны -Z… смотрит на ряды спереди)
			p.rotation.y = PI
			add_child(p)
			_puppets[p.name] = p
			var tag := Label3D.new()
			tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
			tag.no_depth_test = true
			tag.font_size = 48
			tag.pixel_size = 0.004
			tag.outline_size = 10
			tag.modulate = Color(1.0, 0.85, 0.5) if legacy else Color(0.75, 1.0, 0.8)
			tag.text = ("КАК БЫЛО — " if legacy else "НОВАЯ — ") + String(TITLES[prog])
			tag.position = p.position + Vector3(0.0, 2.6, 0.0)
			add_child(tag)
			_labels[p.name] = tag
	_cam = Camera3D.new()
	_cam.fov = 50.0
	_cam.far = 400.0
	add_child(_cam)
	_cam.current = true
	_target = Vector3(0.0, 1.0, ROW_GAP * 0.5)
	_help = Label.new()
	_help.position = Vector2(16, 12)
	_help.add_theme_font_size_override("font_size", 18)
	_help.add_theme_color_override("font_outline_color", Color.BLACK)
	_help.add_theme_constant_override("outline_size", 6)
	_help.text = "ЛКМ — вращать, колесо — ближе/дальше, 1–5 — к фигуре (ещё раз — к «как было»), 0 — обзор\nZ — замедление ×4, Пробел — пауза, H — скрыть подсказку"
	var ui := CanvasLayer.new()
	add_child(ui)
	ui.add_child(_help)
	process_mode = Node.PROCESS_MODE_ALWAYS
	_place_camera()
	if "shots" in OS.get_cmdline_user_args():
		_shots.call_deferred()
	elif "verify" in OS.get_cmdline_user_args():
		_verify.call_deferred()


func _build_world() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	var sky := Sky.new()
	sky.sky_material = ProceduralSkyMaterial.new()
	e.background_mode = Environment.BG_SKY
	e.sky = sky
	e.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	e.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.environment = e
	add_child(env)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50.0, 35.0, 0.0)
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 80.0
	add_child(sun)
	var floor := MeshInstance3D.new()
	var plane := PlaneMesh.new()
	plane.size = Vector2(80.0, 60.0)
	floor.mesh = plane
	var mat := ShaderMaterial.new()
	var sh := Shader.new()
	# клетка 0.5 м, метр — темнее: по ней видно, стоит ли опорная ступня
	sh.code = """shader_type spatial;
varying vec3 wp;
void vertex() { wp = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment() {
	vec2 c = floor(wp.xz / 0.5);
	float chk = mod(c.x + c.y, 2.0);
	vec2 g = abs(fract(wp.xz) - 0.5);
	float line = step(0.488, max(g.x, g.y));
	ALBEDO = mix(vec3(0.52), vec3(0.44), chk) * (1.0 - line * 0.45);
	ROUGHNESS = 0.9;
}"""
	mat.shader = sh
	floor.material_override = mat
	floor.position = Vector3(0.0, 0.0, ROW_GAP * 0.5)
	add_child(floor)


func _place_camera() -> void:
	# камера сзади-сверху цели: _pitch < 0 — смотрит вниз
	var off := Vector3(sin(_yaw) * cos(_pitch), sin(_pitch), cos(_yaw) * cos(_pitch)) * _dist
	_cam.global_position = _target - off
	_cam.look_at(_target, Vector3.UP)


func _process(delta: float) -> void:
	for n: String in _puppets:
		var p: AnimPuppet = _puppets[n]
		var tag: Label3D = _labels[n]
		tag.global_position = p.global_position + Vector3(0.0, 2.6, 0.0)
	if _focus != "" and _puppets.has(_focus):
		_target = _target.lerp((_puppets[_focus] as AnimPuppet).global_position + Vector3(0.0, 1.0, 0.0), 1.0 - exp(-delta / 0.25))
	_place_camera()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var mb := event as InputEventMouseButton
		if mb.button_index == MOUSE_BUTTON_LEFT:
			_drag = mb.pressed
		elif mb.button_index == MOUSE_BUTTON_WHEEL_UP and mb.pressed:
			_dist = maxf(_dist * 0.88, 2.0)
		elif mb.button_index == MOUSE_BUTTON_WHEEL_DOWN and mb.pressed:
			_dist = minf(_dist / 0.88, 120.0)
	elif event is InputEventMouseMotion and _drag:
		var mm := event as InputEventMouseMotion
		_yaw -= mm.relative.x * 0.006
		_pitch = clampf(_pitch - mm.relative.y * 0.006, -1.45, 0.3)
	elif event is InputEventKey and (event as InputEventKey).pressed and not (event as InputEventKey).echo:
		var key := (event as InputEventKey).keycode
		if key >= KEY_1 and key <= KEY_5:
			var prog: String = PROGRAMS[key - KEY_1]
			var new_name := prog + "_new"
			_focus = prog + "_old" if _focus == new_name else new_name
			_dist = 6.0
		elif key == KEY_0:
			_focus = ""
			_target = Vector3(0.0, 1.0, ROW_GAP * 0.5)
			_dist = 30.0
		elif key == KEY_Z:
			_slow = not _slow
			Engine.time_scale = 0.25 if _slow else 1.0
		elif key == KEY_SPACE:
			get_tree().paused = not get_tree().paused
		elif key == KEY_H:
			_help.visible = not _help.visible


## Снимки для проверки: обзор и крупные планы в выбранные моменты программ.
func _shots() -> void:
	_help.visible = false
	var out := "res://docs/screens/"
	var views: Array = [
		# [имя, время программы, с (по возрастанию: снимки идут друг за другом), фигура, расстояние, курс, наклон]
		["turns_twist", 1.9, "turns_new", 4.5, 0.9, -0.25],
		["overview", 2.2, "", 38.0, 0.6, -0.42],
		["shooter_up", 3.8, "shooter_new", 4.5, 1.2, -0.1],
		["shooter_up_old", 3.8, "shooter_old", 4.5, 1.2, -0.1],
		["strafe_diag", 9.2, "strafe_new", 5.0, 0.4, -0.12],
		["strafe_diag_old", 9.2, "strafe_old", 5.0, 0.4, -0.12],
		["shooter_lean", 9.9, "shooter_new", 4.5, 0.2, -0.1],
		["circle_run", 12.0, "circle_new", 6.0, 0.6, -0.2],
	]
	var clock: AnimPuppet = _puppets["circle_new"]
	for v: Array in views:
		# по времени программы, а не часов: первые кадры тормозят на сборке шейдеров
		while clock.clock < float(v[1]):
			await get_tree().process_frame
		_focus = String(v[2])
		_dist = float(v[3])
		_yaw = float(v[4])
		_pitch = float(v[5])
		if _focus != "":
			_target = (_puppets[_focus] as AnimPuppet).global_position + Vector3(0.0, 1.0, 0.0)
		else:
			_target = Vector3(0.0, 1.0, ROW_GAP * 0.5)
		_place_camera()
		# дальность (тени, ИК рук) — сразу по новой камере, не через полсекунды
		for n: String in _puppets:
			(_puppets[n] as AnimPuppet).animator()._lod_t = 0.0
		await get_tree().process_frame
		await get_tree().process_frame
		await get_tree().process_frame
		var img: Image = get_viewport().get_texture().get_image()
		img.save_png(ProjectSettings.globalize_path(out + "anim_stand_%s.png" % String(v[0])))
		print("SHOT ", v[0])
	get_tree().quit(0)


## Скольжение ступней: опорная (ниже другой и у пола) ступня должна стоять на месте — её скорость по
## полу за кадр, средняя на ходу, по каждой программе у новой анимации и у «как было». И ствол за взглядом.
func _verify() -> void:
	_help.visible = false
	# камера — у стрелка: ИК рук работает только вблизи (Balance.CHARACTER_LOD.ik_m)
	_focus = "shooter_new"
	_dist = 5.0
	var feet: Dictionary = {}
	var sums: Dictionary = {}
	for n: String in _puppets:
		var p: AnimPuppet = _puppets[n]
		var sk: Skeleton3D = p.get_node("Body/Persona").find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
		feet[n] = {"sk": sk, "l": sk.find_bone("mixamorig_LeftFoot"), "r": sk.find_bone("mixamorig_RightFoot"), "prev": "", "start": Vector3.ZERO, "held": 0.0, "pos": p.global_position}
		sums[n] = {"slide": 0.0, "time": 0.0}
	# левая кисть на цевье, пока стрелок смотрит вверх-вниз и выглядывает (после ИК, в момент его работы)
	var shooter: AnimPuppet = _puppets["shooter_new"]
	var sh_an: CharacterAnimator = shooter.animator()
	var sh_sk: Skeleton3D = sh_an._support.get_skeleton()
	var hand_err: Dictionary = {"pitch": 0.0, "lean": 0.0, "pitch_n": 0, "lean_n": 0}
	sh_an._support.modification_processed.connect(func() -> void:
		var seg: int = shooter._segment
		var key: String = "pitch" if seg in [1, 2, 3] else ("lean" if seg in [4, 5, 6] else "")
		var gun: Node3D = CharacterAnimator.held_model(sh_an._grip)
		if key == "" or gun == null or sh_an._support.influence < 0.99:
			return
		var mark := gun.find_child("LeftGrip", true, false) as Marker3D
		if mark == null:
			return
		var in_grip: Transform3D = sh_an._grip.global_transform.affine_inverse() * mark.global_transform
		var target: Transform3D = sh_sk.global_transform * sh_sk.get_bone_global_pose(sh_sk.find_bone("mixamorig_RightHand")) * sh_an._grip.transform * in_grip
		target.basis = target.basis.orthonormalized()
		var want: Vector3 = target.origin - target.basis * (mark.get_meta("palm_offset", Vector3.ZERO) as Vector3)
		var lh: Vector3 = (sh_sk.global_transform * sh_sk.get_bone_global_pose(sh_sk.find_bone("mixamorig_LeftHand"))).origin
		hand_err[key] = maxf(float(hand_err[key]), lh.distance_to(want))
		hand_err[key + "_n"] = int(hand_err[key + "_n"]) + 1)
	var clock: AnimPuppet = _puppets["circle_new"]
	# по шагам физики: тело двигается только в них, а клип — каждый кадр; между шагами ступня «едет»
	# вперёд и откатывается назад, и покадровый замер складывал это колебание как скольжение
	while clock.clock < 26.0:
		await get_tree().physics_frame
		for n: String in _puppets:
			_sample(n, feet, sums)
	var fails: int = 0
	print("скольжение опорной ступни на ходу — сдвиг за опору / время опоры, м/с (новая / как было):")
	for prog: String in PROGRAMS:
		var a: Dictionary = sums[prog + "_new"]
		var b: Dictionary = sums[prog + "_old"]
		var new_v: float = float(a.slide) / maxf(float(a.time), 0.001)
		var old_v: float = float(b.slide) / maxf(float(b.time), 0.001)
		var ok: bool = new_v < float(SLIDE_MAX[prog]) and (new_v < old_v or prog == "turns")
		if not ok:
			fails += 1
		print("  [%s] %-8s %.2f / %.2f  (опора %.1f с)" % ["ok" if ok else "FAIL", prog, new_v, old_v, float(a.time)])
		var parts: PackedStringArray = []
		var by_new: Dictionary = a.get("by", {})
		var by_old: Dictionary = b.get("by", {})
		for seg: String in by_new:
			var cn: Array = by_new[seg]
			var co: Array = by_old.get(seg, [0.0, 1.0])
			parts.append("%s: %.2f/%.2f" % [seg, float(cn[0]) / maxf(float(cn[1]), 0.001), float(co[0]) / maxf(float(co[1]), 0.001)])
		print("SEG ", prog, " ", ", ".join(parts))
	for key: String in ["pitch", "lean"]:
		var ok: bool = float(hand_err[key]) < HAND_MAX and int(hand_err[key + "_n"]) > 30
		if not ok:
			fails += 1
		print("  [%s] левая кисть на цевье — %s: мимо метки хвата до %.3f м (замеров %d)" % ["ok" if ok else "FAIL", "взгляд вверх-вниз" if key == "pitch" else "выглядывание", float(hand_err[key]), int(hand_err[key + "_n"])])
	print("anim_stand verify: провалено %d" % fails)
	get_tree().quit(1 if fails > 0 else 0)


func _sample(n: String, feet: Dictionary, sums: Dictionary) -> void:
	var f: Dictionary = feet[n]
	var p: AnimPuppet = _puppets[n]
	var sk: Skeleton3D = f.sk
	var dt: float = get_physics_process_delta_time()
	var moved: float = Vector2(p.global_position.x - (f.pos as Vector3).x, p.global_position.z - (f.pos as Vector3).z).length() / maxf(dt, 0.0001)
	f.pos = p.global_position
	var lp: Vector3 = (sk.global_transform * sk.get_bone_global_pose(int(f.l))).origin
	var rp: Vector3 = (sk.global_transform * sk.get_bone_global_pose(int(f.r))).origin
	var side: String = "l" if lp.y < rp.y else "r"
	var foot: Vector3 = lp if side == "l" else rp
	# Опора — лодыжка не выше PLANTED (поднялась пятка — уже перенос). Скольжение — насколько ступня
	# сдвинулась по полу от постановки до отрыва, делённое на время опоры: покадровые сдвиги тут не
	# годятся — клип идёт каждый кадр, тело только на шагах физики, и ступня дрожит на полсантиметра.
	if moved > 8.0:
		# фигура вернулась в начало программы — не шаг
		f.prev = ""
		return
	var planted: bool = foot.y < PLANTED and moved > 0.3
	if planted and side == String(f.prev):
		f.held = float(f.held) + dt
		return
	_close_stance(f, sums[n])
	if planted:
		f.prev = side
		f.start = foot
		f.held = 0.0
		f.seg = p._segment
	else:
		f.prev = ""


func _close_stance(f: Dictionary, sum: Dictionary) -> void:
	if String(f.get("prev", "")) == "" or float(f.get("held", 0.0)) < 0.1:
		return
	var sk: Skeleton3D = f.sk
	var bone: int = int(f.l) if String(f.prev) == "l" else int(f.r)
	var end: Vector3 = (sk.global_transform * sk.get_bone_global_pose(bone)).origin
	var start_at: Vector3 = f.start
	var d: float = Vector2(end.x - start_at.x, end.z - start_at.z).length()
	sum.slide = float(sum.slide) + d
	sum.time = float(sum.time) + float(f.held)
	# по отрезкам программы — где скользит
	var seg: String = str(f.get("seg", -1))
	var by: Dictionary = sum.get("by", {})
	var cell: Array = by.get(seg, [0.0, 0.0])
	by[seg] = [float(cell[0]) + d, float(cell[1]) + float(f.held)]
	sum.by = by
