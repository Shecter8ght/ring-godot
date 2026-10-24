extends Node
## Движение камеры от первого лица (CameraMotion), при 144 кадрах в секунду и физике 60 тиков:
## стоит — камера ровно в глазах; шаг и бег — покачивание в фазе шагов, бег размашистей и чаще (но без
## тряски: не чаще ~3 шагов в секунду, размах и поворот в пределах);
## остановка — голова «досаживается» и возвращается (ничего не копится); назад, вбок, наискосок,
## разворот, шаг ↔ бег — без рывков; вбок — лёгкий крен в сторону шага; в прицеле точка почти стоит
## и пуля идёт по оси камеры; присед — глаз опускается плавно; прыжок — проседание на приземлении;
## ползунок 0 — камера ровная; вид сверху и обратно — без остатков; на бегу камера не стоит на месте
## между тиками физики (без ступенек).
## tools/godot.cmd --headless res://tools/camera_motion_test.tscn

const FPS := 144
## Рывок — сдвиг или поворот камеры за кадр больше, чем даёт самое быстрое честное покачивание.
const MAX_POS_RATE := 1.5
const MAX_ANG_RATE_DEG := 80.0
const MAX_EYE_STEP := 0.04

var _fails: int = 0
var _me: Player
var _rig: CameraRig
var _fs: Footsteps
var _start: Vector3
var _yaw: float = 0.0
## Рывки по всему прогону: наибольшая скорость сдвига, поворота и шаг высоты глаза за кадр.
var _worst: Dictionary = {"pos": 0.0, "ang": 0.0, "eye": 0.0, "where_pos": "", "where_ang": "", "where_eye": ""}
var _prev_offset: Vector3 = Vector3.ZERO
var _prev_ang: Vector3 = Vector3.ZERO
var _prev_eye_h: float = 0.0
var _have_prev: bool = false


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	Engine.max_fps = FPS
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/mall_map.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for m in level.get_node("Marauders").get_children():
		m.queue_free()
	_me = Raid.current.local_player()
	_me.health.invulnerable = true
	_rig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_fs = _me.get_node("Footsteps") as Footsteps
	await _frames(30)
	_face_open()
	_start = _me.global_position
	await _frames(30)
	var fps := Engine.get_frames_per_second()
	print("   кадров в секунду %.0f, тиков физики %d" % [fps, Engine.physics_ticks_per_second])

	# 1. стоит
	var rest := await _hold(0.6, "стоит")
	_check("стоит — камера ровно в глазах", float(rest.max_pos) < 0.00001 and float(rest.max_ang) < 0.0001,
		"%.5f м, %.4f°" % [rest.max_pos, rest.max_ang])

	# 2. шаг вперёд
	Input.action_press("move_forward")
	await _hold(0.8, "разгон шагом")
	var walk := await _hold(2.0, "шаг вперёд")
	_check("шаг: камера качается (вверх-вниз 3–20 мм)", float(walk.max_up) > 0.003 and float(walk.max_up) < 0.02, "%.1f мм" % (float(walk.max_up) * 1000.0))
	_check("шаг: фаза камеры совпадает с шагами", float(walk.lock_bad) <= 0.05 * float(walk.frames) and int(walk.steps) >= 2,
		"мимо фазы %d из %d кадров, шагов %d" % [walk.lock_bad, walk.frames, walk.steps])
	_check("шаг: удар стопы — камера проседает в кадр шага", int(walk.missed) == 0 and int(walk.dips) >= 2, "просела %d раз из %d шагов, пропущено %d" % [walk.dips, walk.steps, walk.missed])
	# 5. остановка резкая — камера мягко досаживается и возвращается
	Input.action_release("move_forward")
	var stop := await _hold(1.6, "остановка шага")
	_check("остановка: голова уходит вперёд и кивает (досаживается)", float(stop.min_pitch) < -deg_to_rad(0.1), "%.2f°" % rad_to_deg(float(stop.min_pitch)))
	_check("остановка: камера вернулась в глаза, ничего не копится", float(stop.end_pos) < 0.0005 and float(stop.end_ang) < deg_to_rad(0.02),
		"%.2f мм, %.3f°" % [float(stop.end_pos) * 1000.0, rad_to_deg(float(stop.end_ang))])

	# 7. шаг → бег, бег, бег → шаг
	await _back()
	Input.action_press("move_forward")
	await _hold(0.4, "шаг перед бегом")
	Input.action_press("sprint")
	await _hold(0.9, "шаг → бег")
	var run := await _hold(1.5, "бег", true)
	var walk_rate := float(walk.steps) / 2.0
	var run_rate := float(run.steps) / 1.5
	_check("бег: шаги чаще шага, но не чаще ~3 в секунду", run_rate > walk_rate * 1.4 and run_rate < 3.4, "%.1f против %.1f в секунду" % [run_rate, walk_rate])
	_check("бег: покачивание сильнее шага, но не тряска (до 2 см, поворот до 0.6°)", float(run.max_up) > float(walk.max_up) * 1.3 and float(run.max_up) < 0.02 and float(run.max_ang) < deg_to_rad(0.6),
		"%.1f против %.1f мм, поворот %.2f°" % [float(run.max_up) * 1000.0, float(walk.max_up) * 1000.0, rad_to_deg(float(run.max_ang))])
	_check("бег: фаза камеры совпадает с шагами", float(run.lock_bad) <= 0.08 * float(run.frames), "мимо фазы %d из %d" % [run.lock_bad, run.frames])
	if Engine.get_frames_per_second() > float(Engine.physics_ticks_per_second) * 1.4:
		_check("бег: между тиками физики камера не стоит на месте (без ступенек)", float(run.still) <= 0.05 * float(run.frames),
			"стоял %d из %d кадров; без сглаживания стоял бы %d" % [run.still, run.frames, run.raw_still])
	else:
		print("   кадров мало (%.0f) — ступеньки между тиками не проверяются" % Engine.get_frames_per_second())
	# 8. бег → шаг
	Input.action_release("sprint")
	await _hold(1.0, "бег → шаг")
	# 6. разворот на ходу
	Input.action_release("move_forward")
	Input.action_press("move_back")
	await _hold(1.0, "разворот: назад")
	Input.action_release("move_back")
	await _hold(1.0, "стоп после «назад»")

	# 3. шаг вбок — лёгкий крен в сторону шага; 4. наискосок
	await _back()
	Input.action_press("move_right")
	await _hold(0.8, "разгон вбок")
	var strafe := await _hold(1.0, "вбок вправо")
	_check("вбок: камера чуть кренится в сторону шага (0.1–1.5°)", float(strafe.mean_roll) < -deg_to_rad(0.1) and float(strafe.mean_roll) > -deg_to_rad(1.5),
		"%.2f°" % rad_to_deg(float(strafe.mean_roll)))
	Input.action_press("move_forward")
	await _hold(1.0, "наискосок")
	Input.action_release("move_right")
	Input.action_release("move_forward")
	await _hold(1.2, "стоп после наискосок")

	# 9. прицел на ходу и 10. прицел стоя
	await _back()
	Input.action_press("aim")
	await _hold(0.6, "вскинул")
	Input.action_press("move_forward")
	await _hold(0.8, "в прицеле разгон")
	var ads := await _hold(1.5, "в прицеле на ходу")
	_check("в прицеле на ходу: точка прицеливания почти стоит (< 0.05°)", float(ads.max_rot) < deg_to_rad(0.05), "%.3f°" % rad_to_deg(float(ads.max_rot)))
	_check("в прицеле: пуля идёт по оси камеры", float(ads.max_aim_err) < deg_to_rad(0.01), "%.4f°" % rad_to_deg(float(ads.max_aim_err)))
	Input.action_release("move_forward")
	await _hold(1.2, "в прицеле остановка")
	var still_ads := await _hold(0.8, "в прицеле стоя")
	_check("в прицеле стоя: камера не качается", float(still_ads.max_rot) < deg_to_rad(0.002), "%.4f°" % rad_to_deg(float(still_ads.max_rot)))
	Input.action_release("aim")
	await _hold(0.6, "опустил")

	# 11. присед: глаз опускается плавно, вприсядку — мягче
	await _back()
	var h0 := _eye_h()
	Input.action_press("crouch")
	await _frames(2)
	Input.action_release("crouch")
	var down := await _hold(0.7, "присел")
	var h1 := _eye_h()
	_check("присед: глаз опустился плавно и встал на высоту стойки", absf(h1 - float(Balance.ADS_EYE.crouch)) < 0.01 and float(down.max_eye_step) < MAX_EYE_STEP,
		"%.2f → %.2f м, шаг за кадр до %.1f см" % [h0, h1, float(down.max_eye_step) * 100.0])
	Input.action_press("move_forward")
	await _hold(0.8, "вприсядку разгон")
	var crouch := await _hold(1.5, "вприсядку")
	_check("вприсядку: покачивание мягче, чем стоя", float(crouch.max_up) < float(walk.max_up) and float(crouch.max_up) > 0.0005, "%.1f мм" % (float(crouch.max_up) * 1000.0))
	Input.action_release("move_forward")
	await _hold(0.8, "вприсядку стоп")
	Input.action_press("crouch")
	await _frames(2)
	Input.action_release("crouch")
	await _hold(0.8, "встал")

	# прыжок: на приземлении камера проседает
	await _back()
	Input.action_press("vault")
	await _frames(2)
	Input.action_release("vault")
	var jump := await _hold(1.6, "прыжок")
	_check("прыжок: на приземлении камера проседает", float(jump.min_up) < -0.006, "%.1f мм" % (float(jump.min_up) * 1000.0))

	# ползунок «Покачивание камеры» 0 — камера ровная, оружие в руках по-прежнему качается
	await _back()
	Settings.set_camera_motion(0.0)
	Input.action_press("move_forward")
	var off := await _hold(1.5, "ползунок 0")
	Input.action_release("move_forward")
	await _hold(0.8, "ползунок 0, стоп")
	_check("ползунок 0: камера не качается", float(off.max_pos) < 0.000001 and float(off.max_ang) < 0.000001, "%.6f м" % float(off.max_pos))
	_check("ползунок 0: оружие в руках качается как прежде", float(off.max_weapon) > 0.002, "%.1f мм" % (float(off.max_weapon) * 1000.0))
	Settings.set_camera_motion(1.0)

	# 12. вид сверху и обратно — без остатков
	_have_prev = false
	CameraRig.set_first_person_mode(false)
	await _frames(20)
	CameraRig.set_first_person_mode(true)
	await _frames(20)
	_have_prev = false
	var back := await _hold(0.5, "снова из глаз")
	_check("вид сверху и обратно: камера снова в глазах и ровная", _rig.ads_active and float(back.max_pos) < 0.00001 and float(back.max_ang) < 0.0001,
		"%.5f м" % float(back.max_pos))

	_check("за весь прогон без рывков сдвига камеры (< %.1f м/с)" % MAX_POS_RATE, float(_worst.pos) < MAX_POS_RATE, "%.2f м/с (%s)" % [_worst.pos, _worst.where_pos])
	_check("за весь прогон без рывков поворота камеры (< %.0f°/с)" % MAX_ANG_RATE_DEG, float(_worst.ang) < deg_to_rad(MAX_ANG_RATE_DEG), "%.1f°/с (%s)" % [rad_to_deg(float(_worst.ang)), _worst.where_ang])
	_check("за весь прогон высота глаз без скачков (< %.0f см за кадр)" % (MAX_EYE_STEP * 100.0), float(_worst.eye) < MAX_EYE_STEP, "%.1f см (%s)" % [float(_worst.eye) * 100.0, _worst.where_eye])
	print("camera_motion_test: провалено %d" % _fails)
	get_tree().quit(_fails)


## Взгляд — туда, где больше всего свободного места (идти, бежать и прыгать без стен).
func _face_open() -> void:
	var space := _me.get_world_3d().direct_space_state
	var from := _me.global_position + Vector3.UP * 1.0
	var best := 0.0
	for i in 24:
		var a := TAU * float(i) / 24.0
		var dir := Vector3(sin(a), 0.0, cos(a))
		var q := PhysicsRayQueryParameters3D.create(from, from + dir * 60.0, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [_me.get_rid()])
		var hit := space.intersect_ray(q)
		var d := 60.0 if hit.is_empty() else from.distance_to(hit.position)
		if d > best:
			best = d
			_yaw = a
	_rig._look_yaw = _yaw
	print("   свободно вперёд %.0f м" % best)


## Обратно на старт (стоя, взгляд прежний) — следующий кусок не упрётся в стену.
func _back() -> void:
	for a in ["move_forward", "move_back", "move_left", "move_right", "sprint", "aim"]:
		Input.action_release(a)
	await _frames(40)
	_have_prev = false
	_me.global_position = _start
	_me.velocity = Vector3.ZERO
	_rig._look_yaw = _yaw
	await _frames(40)
	_have_prev = false


func _eye_h() -> float:
	return _me.view_eye().y - _me.global_position.y


## Держит текущие клавиши sec секунд и собирает, как шла камера.
func _hold(sec: float, label: String, measure_steps: bool = false) -> Dictionary:
	var st := {"frames": 0, "max_pos": 0.0, "max_ang": 0.0, "max_up": 0.0, "min_up": 0.0, "min_pitch": 0.0,
		"max_rot": 0.0, "max_aim_err": 0.0, "lock_bad": 0, "steps": 0, "dips": 0, "missed": 0, "sum_roll": 0.0, "mean_roll": 0.0,
		"max_eye_step": 0.0, "still": 0, "raw_still": 0, "max_weapon": 0.0, "end_pos": 0.0, "end_ang": 0.0}
	var t := 0.0
	var steps0 := _fs.steps_taken
	var seen := _fs.steps_taken
	var dip_wait := 0
	var prev_view := _me.view_eye()
	var prev_raw := _me.eye_position()
	while t < sec:
		await get_tree().process_frame
		var dt := get_process_delta_time()
		t += dt
		var m: CameraMotion = _rig._motion
		var ang := Vector3(m.pitch, m.yaw, m.roll)
		st.frames = int(st.frames) + 1
		st.max_pos = maxf(float(st.max_pos), m.offset.length())
		st.max_ang = maxf(float(st.max_ang), ang.length())
		st.max_up = maxf(float(st.max_up), absf(m.offset.y))
		st.min_up = minf(float(st.min_up), m.offset.y)
		st.min_pitch = minf(float(st.min_pitch), m.pitch)
		st.max_rot = maxf(float(st.max_rot), Vector2(m.pitch, m.yaw).length())
		st.sum_roll = float(st.sum_roll) + m.roll
		st.max_weapon = maxf(float(st.max_weapon), m.weapon_bob.length())
		# пуля в прицеле — по взгляду игрока; он должен совпадать с осью камеры
		if _me.ads and _rig.ads_active:
			var cam_fwd := -_rig._ads_cam.global_basis.z
			st.max_aim_err = maxf(float(st.max_aim_err), cam_fwd.angle_to(_me.look_dir()))
		if _fs.walking() and t > 0.2:
			if absf(wrapf(_fs.stride_phase() - m._phase, -0.5, 0.5)) > 0.06:
				st.lock_bad = int(st.lock_bad) + 1
		# удар стопы: камера узнаёт шаг в тот же кадр или следующий (порядок узлов) — ждём до 3 кадров
		if _fs.steps_taken != seen:
			seen = _fs.steps_taken
			dip_wait = 3
		if dip_wait > 0:
			dip_wait -= 1
			if m._impact_v.x < -0.01:
				st.dips = int(st.dips) + 1
				dip_wait = 0
			elif dip_wait == 0:
				# 3 кадра прошли, а камера не просела — шаг пропущен (шаг у самого конца замера не считается)
				st.missed = int(st.missed) + 1
		# камера на бегу: стояла ли на месте этот кадр (ступенька между тиками физики)
		var view := _me.view_eye()
		var raw := _me.eye_position()
		if measure_steps:
			var v := Vector2(view.x - prev_view.x, view.z - prev_view.z).length() / maxf(dt, 0.0001)
			var vr := Vector2(raw.x - prev_raw.x, raw.z - prev_raw.z).length() / maxf(dt, 0.0001)
			var expect := Vector2(_me.velocity.x, _me.velocity.z).length()
			if expect > 1.0 and v < expect * 0.35:
				st.still = int(st.still) + 1
			if expect > 1.0 and vr < expect * 0.35:
				st.raw_still = int(st.raw_still) + 1
		prev_view = view
		prev_raw = raw
		var eye_h := view.y - _me.global_position.y
		if _have_prev:
			st.max_eye_step = maxf(float(st.max_eye_step), absf(eye_h - _prev_eye_h))
			var pr := (m.offset - _prev_offset).length() / maxf(dt, 0.0001)
			var ar := (ang - _prev_ang).length() / maxf(dt, 0.0001)
			if pr > float(_worst.pos):
				_worst.pos = pr
				_worst.where_pos = label
			if ar > float(_worst.ang):
				_worst.ang = ar
				_worst.where_ang = label
			if absf(eye_h - _prev_eye_h) > float(_worst.eye):
				_worst.eye = absf(eye_h - _prev_eye_h)
				_worst.where_eye = label
		_prev_offset = m.offset
		_prev_ang = ang
		_prev_eye_h = eye_h
		_have_prev = true
		st.end_pos = m.offset.length()
		st.end_ang = ang.length()
	st.steps = _fs.steps_taken - steps0
	st.mean_roll = float(st.sum_roll) / maxf(float(st.frames), 1.0)
	print("   %s: %d кадров, шагов %d, вверх-вниз до %.1f мм, поворот до %.2f°" % [label, st.frames, st.steps, float(st.max_up) * 1000.0, rad_to_deg(float(st.max_ang))])
	return st


func _check(what: String, ok: bool, note: String = "") -> void:
	print("[%s] %s %s" % ["ok" if ok else "ПРОВАЛ", what, note])
	if not ok:
		_fails += 1


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame
