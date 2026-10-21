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
		check(String(player_spec.sound) == id + "_shot" or bool(player_spec.suppressed), id + ": свой выстрел")
		check(String(player_spec.sound) == String(enemy_spec.sound), id + ": тот же звук у игрока и ИИ")
		check(is_equal_approx(float(player_spec.db), float(enemy_spec.db)), id + ": то же усиление экземпляра")
		var actions: Dictionary = WeaponDb.weapon_sound_map(id)
		check(String(actions.get("ads_raise", "")) == id + "_ads_raise", id + ": свои действия")
	actor.free()
	check(Audio._pick("shot_pistol", Vector3.ZERO) == null, "Нет общего пистолетного набора")
	check(Audio._pick("fam_pistol_mag_out", Vector3.ZERO) == null, "Нет семейного набора")
	check(Audio._pick("wpn_hg_03_shot", Vector3.ZERO) == null, "Неназначенная модель молчит")
	check(Audio._pick("wpn_hg_01_shot", Vector3.ZERO, "room") != null, "Комнатные записи ПМ сохранены")
	check(Audio.resolve_event("wpn_hg_01_shot", "room") == "wpn_hg_01_shot_room", "Комната выбирается у этой модели")
	check(Audio.resolve_event("wpn_hg_01_shot@far") == "", "Дистанционных записей нет")
	check(not is_instance_valid(Audio._ambient), "Автоматический ветер отсутствует")
	print("SONORA_WEAPON_CONTRACT: checked=%d failed=%d" % [checked, failed])
	get_tree().quit(1 if failed else 0)
