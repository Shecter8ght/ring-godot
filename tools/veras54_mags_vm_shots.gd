extends Node
## ВЕРАС-54 с магазином на 45 и барабаном на 60 от первого лица в настоящей игре (ViewmodelClips, tools/veras54_mags):
## модель магазина на метке вместо штатного, свой набор клипов (хват владельца на этом магазине), патроны и подаватель
## по счёту, тактическая и полная перезарядка, быстрая (новым магазином выбить старый — старый того же вида падает),
## проверка с удержанием R — автомат поворачивается окнами остатка к глазам.
## tools/godot.cmd --windowed --resolution 1600x900 res://tools/veras54_mags_vm_shots.tscn → docs/screens/veras54_mags_vm_*.png
## MAGS_ONLY=mag_545_45 — один магазин. Код выхода 1 — есть провалы.

const ID := "wpn_ar_01"
const OUT := "res://docs/screens/"
const MAGS := {"mag_545_45": "mag45", "mag_545_60": "drum60"}

var _player: Player
var _camera: CameraRig
var _failures: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "day", "weather": "clear", "power": "on"}
	await get_tree().process_frame
	var level: Node = load("res://scenes/levels/f1_market.tscn").instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	while level.get_node("Marauders").get_child_count() == 0:
		await get_tree().process_frame
	for enemy: Node in level.get_node("Marauders").get_children():
		enemy.process_mode = Node.PROCESS_MODE_DISABLED
		(enemy as Node3D).visible = false
	_player = get_tree().get_first_node_in_group("players") as Player
	_camera = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	_player.global_position = Vector3(100.0, 0.1, -5.0)
	_player.health.hp = 100000.0
	CameraRig.load_settings()
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.5).timeout
	_camera._look_yaw = -PI * 0.5
	var only: String = OS.get_environment("MAGS_ONLY")
	for mid: String in MAGS:
		if only != "" and mid != only:
			continue
		await _magazine(mid, String(MAGS[mid]))
	print("veras54_mags_vm_shots: ", "PASS" if _failures == 0 else "FAIL (%d)" % _failures)
	get_tree().quit(0 if _failures == 0 else 1)


func _magazine(mid: String, vset: String) -> void:
	var tag: String = mid.trim_prefix("mag_545_")
	await _equip(mid)
	var vm := _camera._viewmodel as ViewmodelClips
	if vm == null:
		_check(tag + ": в руках вьюмодель с клипами", false)
		return
	await _set_rounds(20)
	await get_tree().create_timer(0.3).timeout
	var look: Dictionary = vm._mag_looks.get(mid, {})
	_check(tag + ": модель магазина есть на метке", not look.is_empty())
	if look.is_empty():
		return
	_check(tag + ": набор клипов " + vset, vm._mag_set == vset, vm._mag_set)
	_check(tag + ": модель видна, штатный корпус скрыт", (look.node as Node3D).is_visible_in_tree()
			and not vm._std_mag_nodes.any(func(n: Node3D) -> bool: return n.is_visible_in_tree()))
	var rounds: Array[Node3D] = look.rounds
	var on: int = rounds.filter(func(r: Node3D) -> bool: return r.visible).size()
	_check(tag + ": видно патронов — min(20, %d)" % rounds.size(), on == mini(20, rounds.size()), str(on))
	if look.has("follower"):
		var y20: float = (look.follower as Node3D).position.y
		await _set_rounds(5)
		await get_tree().create_timer(0.2).timeout
		_check(tag + ": подаватель поднимается, когда патронов меньше", (look.follower as Node3D).position.y > y20 + 0.02,
				"%.3f → %.3f" % [y20, (look.follower as Node3D).position.y])
		await _set_rounds(20)
	await _shot("veras54_mags_vm_%s_hip" % tag)
	await _reload([0.15, 0.32, 0.55, 0.75], "veras54_mags_vm_%s_tactical" % tag, vm, "reload_tactical_" + vset)
	await _set_rounds(0)
	await _reload([0.3, 0.55, 0.8], "veras54_mags_vm_%s_full" % tag, vm, "reload_full_" + vset)
	await _fast(tag, vm, vset)
	await _check_hold(tag, vm, vset)


func _equip(mid: String) -> void:
	var slot: String = String(WeaponDb.sandbox()[0])
	_player.sandbox_weapons[slot] = {"id": ID, "n": 1, "dur": 100.0, "mods": {},
		"mag": {"id": mid, "ammo": WeaponDb.default_ammo("545x39"), "rounds": WeaponDb.magazine(mid).get("capacity", 30)},
		"sight": "primary", "rev": randi()}
	_player.weapon_slot = ""
	_player._switch(slot, false)
	await get_tree().create_timer(0.5).timeout


func _set_rounds(n: int) -> void:
	_player.ammo = n
	if _player._ws.has(_player.weapon_slot):
		_player._ws[_player.weapon_slot]["rounds"] = n
	await get_tree().physics_frame


func _reload(fractions: Array, prefix: String, vm: ViewmodelClips, clip: String) -> void:
	Input.action_press("reload")
	await get_tree().physics_frame
	await get_tree().physics_frame
	Input.action_release("reload")
	for i in range(30):
		if _player.reload_timer > 0.0:
			break
		await get_tree().physics_frame
	await get_tree().process_frame
	await get_tree().process_frame
	_check(prefix + ": клип " + clip, vm._clip == clip, vm._clip)
	var total: float = _player.reload_timer
	var elapsed: float = 0.0
	for f: float in fractions:
		await get_tree().create_timer(maxf(0.0, total * f - elapsed)).timeout
		elapsed = total * f
		await _shot("%s_%02d" % [prefix, int(f * 100)])
	await get_tree().create_timer(maxf(0.0, total - elapsed) + 0.5).timeout


func _fast(tag: String, vm: ViewmodelClips, vset: String) -> void:
	await _set_rounds(12)
	for i in range(2):
		Input.action_press("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
		Input.action_release("reload")
		await get_tree().physics_frame
		await get_tree().physics_frame
	await get_tree().process_frame
	await get_tree().process_frame
	_check(tag + ": быстрая — свой клип", vm._fast and vm._clip == "reload_fast_" + vset, vm._clip)
	var total: float = _player.reload_timer
	var elapsed: float = 0.0
	var old_seen: bool = false
	var old: Dictionary = vm._spare_looks.get("mag_545_" + tag, {})
	for f: float in [0.3, 0.42, 0.47, 0.55]:
		await get_tree().create_timer(maxf(0.0, total * f - elapsed)).timeout
		elapsed = total * f
		old_seen = old_seen or (not old.is_empty() and (old.node as Node3D).is_visible_in_tree())
		await _shot("veras54_mags_vm_%s_fast_%02d" % [tag, int(f * 100)])
	_check(tag + ": быстрая — старый магазин того же вида выбит и виден", old_seen)
	_check(tag + ": быстрая — штатный старый магазин не виден", not vm._spare_parts.any(func(n: Node3D) -> bool: return n.visible))
	await get_tree().create_timer(total - elapsed + 0.6).timeout
	_check(tag + ": быстрая — закончена, старый скрыт", vm._clip == "" and (old.is_empty() or not (old.node as Node3D).visible), vm._clip)


func _check_hold(tag: String, vm: ViewmodelClips, vset: String) -> void:
	await _set_rounds(17)
	Input.action_press("reload")
	await get_tree().create_timer(float(Balance.AMMO_CHECK.hold_sec) + 1.4).timeout
	_check(tag + ": проверка — клип поворота " + vset, vm._clip == "mag_check_" + vset, vm._clip)
	_check(tag + ": проверка — стоит на показе, пока держат R", _player.mag_inspect and vm._holding)
	await _shot("veras54_mags_vm_%s_check" % tag)
	Input.action_release("reload")
	await get_tree().create_timer(2.5).timeout
	_check(tag + ": проверка — магазин в оружии, руки на месте", vm._clip == "" and _player.ammo == 17, vm._clip)


func _check(label: String, ok: bool, detail: String = "") -> void:
	if not ok:
		_failures += 1
	print("veras54_mags_vm_shots: ", "ok   " if ok else "ПРОВАЛ ", label, "  (" + detail + ")" if detail != "" and not ok else "")


func _shot(label: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path(OUT + label + ".png"))
	print("veras54_mags_vm_shots: ", label)
