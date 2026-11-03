extends Node
## Полевой модем: выдача после первой находки, старые сохранения, передача в рейде,
## сохранение полученного ответа после гибели, изоляция других находок, журнал и кооп-снимок.

const Q := "car_recovery"
var _fails: int = 0
var _checks: int = 0
var _world: QuestWorld
var _player: Player


class TestWorld extends QuestWorld:
	func _ready() -> void:
		pass
	func _process(_delta: float) -> void:
		pass
	func _exit_tree() -> void:
		pass


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	Profile.use_file("user://car_field_link_test.json", true)
	Quests.dev_start(Q)
	_check("до находки модем не выдан", not Quests.field_link_unlocked(Q))
	Quests.dev_stage(Q, 4)
	Quests.dev_complete_objective(Q)
	_check("в районе поиска модема ещё нет", not Quests.field_link_unlocked(Q))
	# Старый профиль на последней цели этапа дворов: первые фото уже сделаны.
	Profile.quests[Q]["obj"] = 4
	Quests.finish_talk(Q, "ilya", "report_car")
	_check("фото машины подтверждены: сначала подключается Кирилл", String(Quests.objective(Q).get("id", "")) == "kirill_task" and not Quests.field_link_unlocked(Q))
	var battery := Profile.stash_count("battery")
	Quests.finish_talk(Q, "kirill", "kirill_task")
	_check("в убежище вместе с аккумулятором выдан модем", Profile.stash_count("battery") == battery + 1 and Quests.field_link_unlocked(Q))
	_check("в переписке объяснены телефон и отдельный канал", str(Quests.thread_log(Q)).contains("сети оператора") and str(Quests.thread_log(Q)).contains("ретранслятор"))
	_check("дома полевого действия нет", Quests.field_action(Q).is_empty())
	# Игрок и мир без тяжёлой сборки уровня. Авторитет и инвентарь — настоящие.
	_player = load("res://scenes/player/player.tscn").instantiate() as Player
	add_child(_player)
	_player.set_physics_process(false)
	_player.set_process(false)
	_world = TestWorld.new()
	_world.level = "zone01_mall"
	_world.raid = true
	add_child(_world)
	Quests.world = _world
	Quests.begin_raid()
	_check("до установки и снимков отправка закрыта", Quests.field_action(Q).is_empty() and not Quests._send_field_report(1, Q))
	Quests._durable_add(Q, "battery")
	Quests._auto_all()
	for sid: String in ["car_belt_photo_engine", "car_belt_photo_radiator", "car_belt_photo_wheel"]:
		Quests.request_site(sid)
	_check("трёх снимков недостаточно", Quests.field_action(Q).is_empty())
	Quests.request_site("car_belt_photo_wiring")
	_check("все четыре снимка открывают отправку в рейде", not Quests.field_action(Q).is_empty())
	_world.level = "mall_map"
	_check("с другой карты пакет не отправить", Quests.field_action(Q).is_empty() and not Quests._send_field_report(1, Q))
	_world.level = "zone01_mall"
	_player.health.alive = false
	_check("мёртвый игрок отправить не может", not Quests._send_field_report(1, Q))
	_player.health.alive = true
	_player.health.downed = true
	_check("тяжелораненый игрок отправить не может", not Quests._send_field_report(1, Q))
	_player.health.downed = false
	_check("простой вызов переписки не обходит полевой канал", _terminal_does_not_send())
	# Неподтверждённая находка другого заказа не должна сохраниться вместе с передачей.
	Quests.dev_add_def("tst_field_other", {"id": "tst_field_other", "title": "Другая находка", "requires": {}, "stages": []})
	Profile.quests["tst_field_other"] = {"state": "ACTIVE", "facts": []}
	Quests._live.quests["tst_field_other"] = {"state": "ACTIVE", "facts": ["unconfirmed"]}
	# Журнал доступен и в изолированном стенде.
	add_to_group("hideout_level")
	Quests.hud._journal.visible = true
	Quests.hud._fill_journal()
	var send: Button = _button(Quests.hud._field_box)
	_check("в журнале есть кнопка отправки", send != null and send.text.contains("Кириллу"))
	if OS.get_environment("FIELD_LINK_SHOTS") == "1":
		await _shot("ready")
	if send:
		if OS.get_environment("FIELD_LINK_SHOTS") == "1":
			var at := send.get_global_rect().get_center()
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
			var motion := InputEventMouseMotion.new()
			motion.position = at
			Input.parse_input_event(motion)
			for pressed: bool in [true, false]:
				var click := InputEventMouseButton.new()
				click.position = at
				click.button_index = MOUSE_BUTTON_LEFT
				click.pressed = pressed
				Input.parse_input_event(click)
				await get_tree().process_frame
		else:
			send.pressed.emit()
	_check("кнопка отправляет пакет и открывает детали в том же рейде", String(Quests.objective(Q).get("id", "")) == "wheel" and Quests.supply_available(Q, "car_belt_parts_radiator"))
	_check("ответ показан в журнале и сохранён в переписке", _text(Quests.hud._field_box).contains("Ответ мастерской") and str(Quests.thread_log(Q)).contains("Радиатор"))
	_check("отправленный пакет сразу сохранён хостом", int(Profile.quests[Q].get("stage", -1)) == 5)
	_check("другие находки не подтверждаются", (Profile.quests["tst_field_other"].get("facts", []) as Array).is_empty())
	var size := Quests.thread_log(Q).size()
	_check("повторная отправка не дублирует ответ", not Quests._send_field_report(1, Q) and Quests.thread_log(Q).size() == size)
	if OS.get_environment("FIELD_LINK_SHOTS") == "1":
		await _shot("reply")
	# Гость сохраняет только подтверждённый заказ, сохраняя остальные записи своей кампании.
	Profile.guest_campaigns[Profile.own_campaign()] = {"quests": {"keep": {"state": "ACTIVE"}}, "flags": {"keep_flag": true}, "rewarded": []}
	Quests._commit_guest_field_reports(Quests._snapshot())
	var guest: Dictionary = Profile.guest_campaigns[Profile.own_campaign()]
	_check("гость сохранил ответ, сохранив остальные записи", guest.quests.has(Q) and guest.quests.has("keep") and bool(guest.flags.keep_flag) and not guest.quests.has("tst_field_other"))
	Quests.hud._journal.visible = false
	Quests.end_raid()
	_check("без эвакуации ответ и список деталей остаются", String(Quests.objective(Q).get("id", "")) == "wheel" and Quests.thread_log(Q).size() == size)
	Quests.begin_raid()
	_check("в новом рейде повторять диагностику не нужно", Quests.supply_available(Q, "car_belt_parts_radiator") and Quests.field_action(Q).is_empty())
	Quests.end_raid()
	# Старые записи не нуждаются в добавлении флага или выдаче повторной награды.
	var money := Profile.money
	var old_battery := Profile.stash_count("battery")
	Quests.dev_stage(Q, 5)
	Profile.quests[Q]["obj"] = 5
	_check("старое сохранение на отчёте получает модем без отката", Quests.field_link_unlocked(Q) and String(Quests.objective(Q).get("id", "")) == "report_kirill" and Profile.money == money and Profile.stash_count("battery") == old_battery)
	Quests.begin_raid()
	Quests._live.quests[Q]["stage"] = 5
	Quests._live.quests[Q]["obj"] = 2
	Quests.finish_talk(Q, "ilya", "final")
	_check("финальный отчёт остаётся только в убежище", String(Quests.objective(Q).get("id", "")) == "final" and Quests.state(Q) == "ACTIVE")
	Quests.end_raid()
	Quests.world = null
	print("car_field_link_test: %d проверок, провалов %d" % [_checks, _fails])
	get_tree().quit(1 if _fails else 0)


func _terminal_does_not_send() -> bool:
	Quests.finish_talk(Q, "kirill", "report_kirill")
	return String(Quests.objective(Q).get("id", "")) == "report_kirill" and Quests.terminal_action(Q).is_empty()


func _button(root: Node) -> Button:
	for child in root.get_children():
		if child is Button:
			return child as Button
	return null


func _text(root: Node) -> String:
	var out := ""
	for child in root.get_children():
		if child is Label:
			out += (child as Label).text
	return out


func _shot(tag: String) -> void:
	for frame in range(3):
		await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png("res://docs/screens/car_field_link_%s.png" % tag)


func _check(what: String, ok: bool) -> void:
	_checks += 1
	print(("  [ok] " if ok else "  [FAIL] ") + what)
	if not ok:
		_fails += 1
