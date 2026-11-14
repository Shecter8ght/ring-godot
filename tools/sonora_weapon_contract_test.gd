extends Node3D
## Договор назначений: все модели используют один маршрут у игрока и противников.
var failed: int = 0
var checked: int = 0

func check(condition: bool, label: String) -> void:
	checked += 1
	if not condition:
		failed += 1
		push_error(label)

func _ready() -> void:
	var actor: Marauder = Marauder.new()
	for id: String in WeaponDb.weapon_ids():
		var entry: Dictionary = {"id": id, "n": 1, "dur": 100.0, "mods": {}}
		var player_spec: Dictionary = WeaponStats.compute(entry)
		var enemy_spec: Dictionary = actor._ai_spec(entry)
		var weapon: Dictionary = WeaponDb.weapon(id)
		var integral: bool = bool((weapon.get("integral", {}) as Dictionary).get("suppressed", false))
		var suppressible: bool = integral or (weapon.get("mounts", {}) as Dictionary).has("muzzle")
		check(String(player_spec.sound) == id + ("_shot_sup" if integral else "_shot"), id + ": свой выстрел")
		check(String(player_spec.sound) == String(enemy_spec.sound), id + ": тот же звук у игрока и ИИ")
		check(is_equal_approx(float(player_spec.db), float(enemy_spec.db)), id + ": то же усиление экземпляра")
		var actions: Dictionary = WeaponDb.weapon_sound_map(id)
		check(String(actions.get("ads_raise", "")) == id + "_ads_raise", id + ": свои действия")
		var shots: Array[String] = []
		if not integral:
			shots.append_array(["shot_room", "shot_outdoor"])
		if suppressible:
			shots.append_array(["shot_sup_room", "shot_sup_outdoor"])
		var actual: Array = actions.keys().filter(func(action: String) -> bool: return action.begins_with("shot"))
		check(actual == shots, id + ": четыре типа по месту и глушителю, если доступны")
	actor.free()
	var pm_suppressed: Dictionary = WeaponStats.compute({"id": "wpn_hg_01", "mods": {"muzzle": "muzzle_supp_pm_01"}})
	check(String(pm_suppressed.sound) == "wpn_hg_01_shot_sup", "Съёмный глушитель выбирает заглушённый набор")
	for hook: String in ["wpn_ar_01_shot", "wpn_ar_01_shot_room", "wpn_ar_01_shot_outdoor"]:
		check(float(Audio._kind_spec(hook)["max"]) == 900.0, hook + ": общий профиль без глушителя")
	for hook: String in ["wpn_ar_01_shot_sup", "wpn_ar_01_shot_sup_room", "wpn_ar_01_shot_sup_outdoor", "wpn_sp_02_shot_sup"]:
		check(float(Audio._kind_spec(hook)["max"]) == 250.0, hook + ": общий профиль с глушителем")
	var camera: Camera3D = Camera3D.new()
	add_child(camera)
	camera.current = true
	check(Audio.preview_event("wpn_ar_01_shot_sup_outdoor", Vector3.FORWARD * 251.0) == null,
		"Стенд соблюдает предел заглушённого выстрела")
	var far_shot := Audio.preview_event("wpn_ar_01_shot_outdoor", Vector3.FORWARD * 625.0) as AudioStreamPlayer3D
	check(far_shot != null and far_shot.unit_size > 40.0, "Стенд воспроизводит обычный выстрел с дальней кривой")
	var played: Array[String] = []
	Audio.event_played.connect(func(id: String, _hook: String, _pos: Vector3) -> void: played.append(id))
	Audio.play("wpn_ar_01_shot_sup", Vector3.FORWARD * 150.0)
	Audio.play("wpn_ar_01_shot_sup", Vector3.FORWARD * 251.0)
	Audio.play("wpn_ar_01_shot", Vector3.FORWARD * 625.0)
	await get_tree().create_timer(625.0 / float(Balance.AUDIO_FAR.sound_mps) + 0.15).timeout
	check(played.count("wpn_ar_01_shot_sup_outdoor") == 1, "В рейде заглушённый выстрел звучит на 150 м и молчит за 250 м")
	check(played.count("wpn_ar_01_shot_outdoor") == 1, "В рейде обычный выстрел доходит с 625 м")
	check(Audio._pick("shot_pistol", Vector3.ZERO) == null, "Нет общего пистолетного набора")
	check(Audio._pick("fam_pistol_mag_out", Vector3.ZERO) == null, "Нет семейного набора")
	check(Audio._pick("wpn_smg_04_shot", Vector3.ZERO) == null, "Неназначенная модель молчит")
	check(Audio._pick("wpn_hg_01_shot", Vector3.ZERO, "room") != null, "Комнатные записи ПМ сохранены")
	check(Audio.resolve_event("wpn_hg_01_shot", "room") == "wpn_hg_01_shot_room", "Комната выбирается у этой модели")
	check(Audio.resolve_event("wpn_hg_01_shot", "hall") == "wpn_hg_01_shot_room", "Зал использует тот же набор помещения")
	check(Audio.resolve_event("wpn_hg_01_shot", "outdoor") == "wpn_hg_01_shot_outdoor", "Улица использует свой набор")
	check(Audio.resolve_event("wpn_sp_02_shot_sup", "hall") == "wpn_sp_02_shot_sup_room", "Встроенный глушитель в помещении")
	check(Audio.resolve_event("wpn_sp_02_shot_sup", "outdoor") == "wpn_sp_02_shot_sup_outdoor", "Встроенный глушитель на улице")
	check(Audio.resolve_event("wpn_sp_02_shot", "outdoor") == "", "У встроенного глушителя только заглушённый выстрел")
	check(Audio._pick("wpn_smg_03_shot_sup", Vector3.ZERO, "room") == null, "Пустой заглушённый слот молчит")
	check(Audio.resolve_event("wpn_hg_01_shot@far") == "", "Дистанционных записей нет")
	check(not is_instance_valid(Audio._ambient), "Автоматический ветер отсутствует")
	print("SONORA_WEAPON_CONTRACT: checked=%d failed=%d" % [checked, failed])
	get_tree().quit(1 if failed else 0)
