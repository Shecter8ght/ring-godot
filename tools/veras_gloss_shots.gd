extends Node
## ВЕРАС-54 под лампами тира: автомат матовый — по крышке и коробке не скользят блики, блестят
## только затворная группа, трубка приклада и следы рук (v13: tools/veras54_v13/game_finish.py).
## tools/godot.cmd res://tools/veras_gloss_shots.tscn
## → docs/screens/veras_gloss_*.png. GLOSS_TAG=имя — приставка к файлам; GLOSS_MODS=точка:обвес,… — обвесы;
## GLOSS_DUR=60 — ресурс ствола и обвесов (карты состояний 100 / 60 / 20); GLOSS_ONLY=имя,имя — выборочно;
## GLOSS_CANT=1 — в прицеле «с завалом» (автомат боком к лампам, как на снимке владельца 2026-10-19).

const ID := "wpn_ar_01"
## Курс вдоль дорожки тира (к мишеням, +X).
const YAW := PI * 0.5
## Взгляд: [имя, курс°, наклон°] — вдоль дорожки, вверх к лампам, вбок-вверх.
const LOOKS: Array = [["level", 0.0, 0.0], ["up20", 0.0, 20.0], ["up40", 0.0, 40.0], ["up60", 0.0, 60.0],
	["side_up30", 55.0, 30.0], ["side_up50", -60.0, 50.0], ["back_up40", 150.0, 40.0]]


func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://veras_gloss_test.json", true)
	Profile.modules.generator = 1
	get_tree().change_scene_to_file("res://scenes/levels/hideout.tscn")
	for i: int in range(200):
		await get_tree().process_frame
	var level: Node = get_tree().current_scene
	for canvas: Node in level.find_children("*", "CanvasLayer", true, false):
		(canvas as CanvasLayer).visible = false
	var pl: Player = level.get("_player") as Player
	var cam: CameraRig = get_tree().get_first_node_in_group("camera_rig") as CameraRig
	pl.global_position = Vector3(23.2, 0.1, 0.6)
	for i: int in range(10):
		await get_tree().process_frame
	var rng := RandomNumberGenerator.new()
	var entry: Dictionary = WeaponDb.bare_weapon(ID, rng, [100, 100])
	entry["mods"] = _mods()
	entry["dur"] = _dur()
	pl.set_range_weapon(entry)
	CameraRig.first_person_mode = true
	await get_tree().create_timer(0.8).timeout
	if OS.get_environment("GLOSS_CANT") == "1":
		Input.action_press("aim")
		await get_tree().create_timer(float(pl.spec().aim_time) + 0.3).timeout
		pl.aim_cant = true
		await get_tree().create_timer(0.6).timeout
	var tag: String = OS.get_environment("GLOSS_TAG")
	var only: PackedStringArray = OS.get_environment("GLOSS_ONLY").split(",", false)
	for look: Array in LOOKS:
		if not only.is_empty() and not String(look[0]) in only:
			continue
		cam._look_yaw = YAW + deg_to_rad(float(look[1]))
		cam._look_pitch = deg_to_rad(float(look[2]))
		await get_tree().create_timer(0.6).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/veras_gloss_%s%s.png" % [tag, String(look[0])])
		print("veras_gloss_shots: ", look[0], " в руках ", pl.weapon_id, " взгляд ", -get_viewport().get_camera_3d().global_basis.z)
	get_tree().quit()


## Обвесы для снимка: GLOSS_MODS="точка:обвес,точка:обвес" (пусто — голый автомат).
func _mods() -> Dictionary:
	var out: Dictionary = {}
	for pair: String in OS.get_environment("GLOSS_MODS").split(",", false):
		var kv: PackedStringArray = pair.split(":")
		out[kv[0]] = {"id": kv[1], "dur": _dur()}
	return out


## Ресурс ствола и обвесов для снимка: GLOSS_DUR=60 (по умолчанию 100).
func _dur() -> float:
	var raw: String = OS.get_environment("GLOSS_DUR")
	return float(raw) if raw != "" else 100.0
