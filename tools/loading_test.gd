extends Node
## Настоящие переходы меню → убежище → рейд → эвакуация, только с тестовым профилем.
## Для проверки меню (Saves) запускать с отдельным APPDATA; с -- capture сохраняет экран загрузки.

const WAIT_MS: int = 120000
var _fails: int = 0
var _stages: Array[String] = []
var _last_progress: float = -1.0
var _frames_visible: int = 0
var _capture: bool = false
var _captured: Dictionary = {}


func _ready() -> void:
	if name != "LoadingTestRunner":
		Profile.use_file("res://tools/_probe/loading_boot_profile.json", true)
		var runner: Node = Node.new()
		runner.name = "LoadingTestRunner"
		runner.set_script(get_script())
		get_tree().root.add_child.call_deferred(runner)
		return
	_run()


func _run() -> void:
	print("loading_test: user data ", OS.get_user_data_dir())
	if not OS.get_user_data_dir().replace("\\", "/").begins_with(ProjectSettings.globalize_path("res://tools/_probe/").replace("\\", "/")):
		push_error("loading_test: для проверки Saves нужен отдельный APPDATA в tools/_probe.")
		get_tree().quit(1)
		return
	Profile.use_file("user://loading_test.json", true)
	RaidEvents.enabled = false
	_capture = "capture" in OS.get_cmdline_user_args() and DisplayServer.get_name() != "headless"
	Loading.stage_changed.connect(_on_stage)
	Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню")
	await _done(Balance.MAIN_MENU_SCENE)
	var menu: Control = get_tree().current_scene as Control
	menu.call("_show_new")
	await get_tree().process_frame
	var side: VBoxContainer = menu.get("_side") as VBoxContainer
	var name_edit: LineEdit = side.find_children("*", "LineEdit", true, false)[0] as LineEdit
	name_edit.text = "Загрузка — тест"
	var start: Button = null
	for node: Node in side.get_children():
		if node is Button and (node as Button).text == "Начать":
			start = node as Button
	var saves_before: int = Saves.list().size()
	_reset()
	start.pressed.emit()
	start.pressed.emit()
	_check("новая игра сразу показывает загрузку", Loading.active and Loading.visible)
	_check("профиль готовится после появления экрана", Saves.list().size() == saves_before)
	await _done(Balance.HIDEOUT_SCENE)
	_check("двойное нажатие создаёт одно сохранение", Saves.list().size() == saves_before + 1)
	_check("вид из глаз готов до закрытия экрана", _rig().ads_active)
	var save: String = Saves.last()
	_reset()
	Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню")
	await _done(Balance.MAIN_MENU_SCENE)
	menu = get_tree().current_scene as Control
	_reset()
	menu.call("_play", save)
	_check("продолжить сразу показывает загрузку", Loading.active and Loading.visible)
	await _done(Balance.HIDEOUT_SCENE)
	_check("продолжить открывает выбранное сохранение", Profile.path == save)
	# В рейд идём штатным выходом убежища; оружие должно уйти из профиля и вернуться при эвакуации.
	for index: int in range(Profile.stash.size()):
		if String((Profile.stash[index] as Dictionary).id) == WeaponDb.canonical("w_rifle"):
			Profile.equip_from_stash(index)
			break
	Profile.floor = "f1"
	var equipment_count: int = Profile.equipment.size()
	_reset()
	get_tree().current_scene.call("_launch_raid")
	_check("рейд сразу показывает загрузку", Loading.active and Loading.visible)
	await _done(Floors.scene("f1"))
	var player: Player = Raid.current.local_player()
	player.health.invulnerable = true
	_check("игрок получил снаряжение до закрытия экрана", player.loadout_mode and player.inventory.loadout_ready and Profile.equipment.is_empty())
	var extraction: ExtractionPoint = get_tree().get_first_node_in_group("extractions") as ExtractionPoint
	Raid.current._extract(player, extraction)
	for frame: int in range(3):
		await get_tree().process_frame
	_check("эвакуация вернула снаряжение в профиль", Raid.current.is_extracted(1) and Profile.equipment.size() == equipment_count)
	_reset()
	Raid.current.go_hideout()
	_check("возврат после эвакуации сразу показывает загрузку", Loading.active and Loading.visible)
	await _done(Balance.HIDEOUT_SCENE)
	_check("возвращённое снаряжение остаётся в убежище", Profile.equipment.size() == equipment_count)
	# Ошибка чтения оставляет исходную сцену и понятный выход, затем можно повторить переход.
	var source: Node = get_tree().current_scene
	_reset()
	Net.change_scene("res://tools/_probe/loading_missing_scene.tscn")
	await _wait_finished()
	_check("ошибка загрузки оставляет исходную сцену", get_tree().current_scene == source and Loading.visible and not Loading.active)
	_check("при ошибке мир остаётся закрыт экраном", source.process_mode == Node.PROCESS_MODE_DISABLED)
	Loading.dismiss()
	_check("назад после ошибки возвращает управление", not Loading.visible and source.process_mode != Node.PROCESS_MODE_DISABLED)
	_reset()
	Net.change_scene(Balance.MAIN_MENU_SCENE, "Главное меню")
	await _done(Balance.MAIN_MENU_SCENE)
	print("loading_test: провалов %d" % _fails)
	get_tree().quit(_fails)


func _rig() -> CameraRig:
	return get_tree().get_first_node_in_group("camera_rig") as CameraRig


func _reset() -> void:
	_stages.clear()
	_last_progress = -1.0
	_frames_visible = 0


func _done(path: String) -> void:
	await _wait_finished()
	_check("переход завершён: " + path.get_file(), not Loading.visible and get_tree().current_scene != null and get_tree().current_scene.scene_file_path == path)
	_check("прогресс дошёл до 100%", is_equal_approx(Loading.progress, 100.0))
	_check("экран пережил несколько кадров и этапов", _frames_visible >= 2 and _stages.size() >= 4)
	_check("сцена снова обрабатывает игру", get_tree().current_scene.process_mode != Node.PROCESS_MODE_DISABLED)
	if path == Balance.MAIN_MENU_SCENE:
		_check("в меню курсор свободен после возврата из игры", Input.mouse_mode == Input.MOUSE_MODE_VISIBLE)
	elif DisplayServer.get_name() != "headless":
		_check("в игре мышь снова управляет взглядом", Input.mouse_mode == Input.MOUSE_MODE_CAPTURED)


func _wait_finished() -> void:
	var began: int = Time.get_ticks_msec()
	while Loading.active and Time.get_ticks_msec() - began < WAIT_MS:
		await get_tree().process_frame
	if Loading.active:
		_check("загрузка закончилась вовремя", false)
		get_tree().quit(1)


func _process(_delta: float) -> void:
	if name == "LoadingTestRunner" and Loading.active and Loading.visible:
		_frames_visible += 1


func _on_stage(text: String, percent: float) -> void:
	if percent < _last_progress:
		_check("прогресс не идёт назад", false)
	_last_progress = percent
	if text not in _stages:
		_stages.append(text)
	var title: String = (Loading.get("_title") as Label).text
	var shot: String = ""
	if text == "Подготовка персонажа" and title == "Новая игра":
		shot = "hideout"
	elif text == "Подготовка света и погоды":
		shot = "raid"
	elif text == "Подготовка персонажа" and title == "Возвращение в убежище":
		shot = "return"
	if _capture and shot != "" and not _captured.has(shot):
		_captured[shot] = true
		_save_shot(shot)


func _save_shot(shot: String) -> void:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var path: String = "res://docs/screens/loading_%s.png" % shot
	var error: Error = get_viewport().get_texture().get_image().save_png(path)
	_check("снимок " + path, error == OK)


func _check(label: String, okay: bool) -> void:
	if not okay:
		_fails += 1
	print("%s loading: %s" % ["OK" if okay else "FAIL", label])
