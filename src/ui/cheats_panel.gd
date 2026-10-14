extends VBoxContainer
## Единственное игровое окно для дополнительных возможностей, денег и команд разработчика.

var _toggles: Dictionary = {}
var _speed: HBoxContainer
var _world: GridContainer
var _money_rows: GridContainer
var _money_hint: Label
var _command: LineEdit
var _output: Label


func _ready() -> void:
	custom_minimum_size.x = 620
	add_theme_constant_override("separation", 8)
	add_child(Pause._head("Читы"))
	var tabs: TabContainer = TabContainer.new()
	tabs.custom_minimum_size = Vector2(620, 490)
	add_child(tabs)
	var abilities: VBoxContainer = _tab(tabs, "Возможности")
	var grid: GridContainer = _grid(abilities)
	grid.add_child(Pause._label("Всё у Михалыча"))
	var all_items: CheckButton = CheckButton.new()
	all_items.focus_mode = Control.FOCUS_NONE
	all_items.button_pressed = Settings.all_weapons
	all_items.tooltip_text = "Весь ассортимент без доверия. Для покупки нужны деньги и место."
	all_items.toggled.connect(Settings.set_all_weapons)
	grid.add_child(all_items)
	grid.add_child(Pause._label("Бессмертие"))
	var god: CheckButton = CheckButton.new()
	god.focus_mode = Control.FOCUS_NONE
	god.button_pressed = Settings.god
	god.tooltip_text = "Попадания видно, но здоровье не убывает; лёжа — сразу встаёшь. В коопе остальным пишется в чат."
	god.toggled.connect(func(on: bool) -> void: Settings.set_god(on))
	grid.add_child(god)
	grid.add_child(Pause._label("Открыть всё"))
	var unlock: CheckButton = CheckButton.new()
	unlock.focus_mode = Control.FOCUS_NONE
	unlock.button_pressed = Settings.unlock_all
	unlock.tooltip_text = "Для плейтеста: у Михалыча весь товар без доверия, верстак и все модули убежища на максимуме, станок гравировки стоит и запитан. Денег не даёт — они в «Читы → Деньги». Чит хоста действует на всю группу. Выключил — прогресс сохранения прежний; только тайник и карман остаются большими, чтобы вещи не пропали."
	unlock.toggled.connect(func(on: bool) -> void: Settings.set_unlock_all(on))
	grid.add_child(unlock)
	grid.add_child(Pause._label("Лут в продаже"))
	var loot: CheckButton = CheckButton.new()
	loot.focus_mode = Control.FOCUS_NONE
	loot.button_pressed = Settings.shop_loot
	loot.tooltip_text = "Михалыч показывает и продаёт то, что обычно только находят в рейде: головку станка гравировки, сигнал вызова самолёта, ценности, детали."
	loot.toggled.connect(func(on: bool) -> void: Settings.set_shop_loot(on))
	grid.add_child(loot)
	# отладка для аудита уровня: полёт, скорость, переместиться к точке карты
	grid.add_child(Pause._label("Полёт"))
	var fly: CheckButton = CheckButton.new()
	fly.focus_mode = Control.FOCUS_NONE
	fly.button_pressed = Settings.cheat_fly
	fly.tooltip_text = "Сквозь стены и землю: WASD — куда смотришь, пробел — вверх, присесть — вниз, спринт — ×4. Выключить — упадёшь вниз."
	fly.toggled.connect(func(on: bool) -> void: Settings.cheat_fly = on)
	grid.add_child(fly)
	grid.add_child(Pause._label("Скорость"))
	_speed = Pause._slider(0.1, 20.0, 0.1, Settings.cheat_speed, "×%.2f",
		func(v: float) -> void: Settings.cheat_speed = v)
	grid.add_child(_speed)
	_toggles = {"god": god, "unlock_all": unlock, "shop_loot": loot, "cheat_fly": fly, "all_weapons": all_items}

	_world = _grid(_tab(tabs, "Мир"))
	var money: VBoxContainer = _tab(tabs, "Деньги")
	_money_hint = Pause._label("")
	_money_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	money.add_child(_money_hint)
	_money_rows = GridContainer.new()
	_money_rows.columns = 5
	_money_rows.add_theme_constant_override("h_separation", 6)
	_money_rows.add_theme_constant_override("v_separation", 8)
	money.add_child(_money_rows)
	var commands_tab: VBoxContainer = _tab(tabs, "Команды")
	var hint: Label = Pause._label("Выдача предметов, обвесы, износ, модули, задания и события. Введи help — список команд.")
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	commands_tab.add_child(hint)
	_command = LineEdit.new()
	_command.placeholder_text = "Например: give ammo 545_AP 120"
	commands_tab.add_child(_command)
	var execute: Button = Button.new()
	execute.text = "Выполнить"
	execute.pressed.connect(func() -> void: _execute(_command.text))
	commands_tab.add_child(execute)
	_command.text_submitted.connect(_execute)
	_output = Pause._label("")
	_output.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	commands_tab.add_child(_output)
	Settings.changed.connect(_sync)
	Net.player_list_changed.connect(refresh_money)
	_sync()


func _tab(tabs: TabContainer, title: String) -> VBoxContainer:
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.name = title
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	tabs.add_child(scroll)
	var content: VBoxContainer = VBoxContainer.new()
	content.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_theme_constant_override("separation", 10)
	scroll.add_child(content)
	return content


func _grid(parent: Control) -> GridContainer:
	var grid: GridContainer = GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 16)
	grid.add_theme_constant_override("v_separation", 8)
	parent.add_child(grid)
	return grid


func refresh() -> void:
	_sync()
	refresh_money()
	for child: Node in _world.get_children():
		_world.remove_child(child)
		child.queue_free()
	_world.add_child(Pause._label("Время суток"))
	_world.add_child(_cond_option(Balance.RAID_TIME, true))
	_world.add_child(Pause._label("Точное время"))
	_world.add_child(_hour_row())
	_world.add_child(Pause._label("Погода"))
	_world.add_child(_cond_option(Balance.RAID_WEATHER, false))
	_world.add_child(Pause._label("Переместиться"))
	_world.add_child(_teleport_option())


func _sync() -> void:
	for key: String in _toggles:
		(_toggles[key] as CheckButton).set_pressed_no_signal(bool(Settings.get(key)))
	if _speed:
		(_speed.get_child(0) as HSlider).set_value_no_signal(Settings.cheat_speed)
		(_speed.get_child(1) as Label).text = "×%.2f" % Settings.cheat_speed


func _execute(command: String) -> void:
	_output.text = run_command(command)
	_command.clear()


func refresh_money() -> void:
	var allowed: bool = not Net.is_networked() or Net.is_host()
	_money_rows.visible = allowed
	_money_hint.text = "Сумма сразу меняет счёт игрока (минус — списать)." if allowed else "Деньги игрокам выдаёт хост."
	if not allowed:
		return
	for c: Node in _money_rows.get_children():
		_money_rows.remove_child(c)
		c.queue_free()
	var names: Dictionary = Net.player_names if Net.is_networked() else {multiplayer.get_unique_id(): "Ты"}
	var ids: Array = names.keys()
	ids.sort()
	for id in ids:
		var peer: int = int(id)
		var name: Label = Label.new()
		name.text = String(names[id]) + (" (ты)" if Net.is_networked() and peer == multiplayer.get_unique_id() else "")
		name.add_theme_font_size_override("font_size", 17)
		name.custom_minimum_size.x = 150
		_money_rows.add_child(name)
		var amount: SpinBox = SpinBox.new()
		amount.min_value = -10000000
		amount.max_value = 10000000
		amount.step = 1000
		amount.value = 100000
		amount.suffix = "₽"
		amount.custom_minimum_size.x = 150
		_money_rows.add_child(amount)
		var give: Button = Button.new()
		give.text = "Начислить"
		give.focus_mode = Control.FOCUS_NONE
		_money_rows.add_child(give)
		for quick in [100000, 1000000]:
			var q: Button = Button.new()
			q.text = "+%s" % ("1 млн" if quick == 1000000 else "100 тыс")
			q.focus_mode = Control.FOCUS_NONE
			q.pressed.connect(func() -> void: _grant(peer, int(quick), q))
			_money_rows.add_child(q)
		give.pressed.connect(func() -> void: _grant(peer, int(amount.value), give))


func _grant(peer: int, amount: int, btn: Button) -> void:
	if Net.is_networked() and not Net.is_host():
		return
	Net.grant_money(peer, amount)
	var was: String = btn.text
	btn.text = "✓ отправлено"
	btn.disabled = true
	get_tree().create_timer(1.0, true, false, true).timeout.connect(func() -> void:
		if is_instance_valid(btn):
			btn.text = was
			btn.disabled = false)


## Время суток / погода рейда: «как в убежище» или любой вариант; в рейде меняется сразу.
func _cond_option(table: Dictionary, is_time: bool) -> OptionButton:
	var ob: OptionButton = OptionButton.new()
	ob.focus_mode = Control.FOCUS_NONE
	ob.disabled = Net.is_networked() and not Net.is_host()
	ob.tooltip_text = "Сразу в текущем рейде (в одиночной игре и у хоста) и в следующих; в коопе гости получат со следующего рейда. «Как в убежище» — по выбору у лестницы."
	var keys: Array = [""]
	ob.add_item("Как в убежище")
	for k in table:
		keys.append(String(k))
		ob.add_item(String((table[k] as Dictionary).name))
	var cur: String = Settings.raid_time if is_time else Settings.raid_weather
	ob.selected = maxi(0, keys.find(cur))
	ob.item_selected.connect(func(i: int) -> void:
		if is_time:
			Settings.set_raid_conditions(String(keys[i]), Settings.raid_weather)
		else:
			Settings.set_raid_conditions(Settings.raid_time, String(keys[i])))
	return ob


## Точки карты для аудита: старт, точки входа (группа spawn_points), центры районов из данных
## сектора. Выбор — сразу переносит своего игрока (на землю под точкой).
func _teleport_option() -> OptionButton:
	var ob: OptionButton = OptionButton.new()
	ob.focus_mode = Control.FOCUS_NONE
	ob.tooltip_text = "Перенести себя к точке карты (для осмотра уровня)."
	ob.add_item("— выбрать точку —")
	var pts: Array = [null]
	var level: Node = get_tree().current_scene
	var path: Variant = level.get("sector_path") if level else null
	var def: Dictionary = SectorBuilder.load_def(String(path)) if path != null and String(path) != "" else {}
	if def.has("spawn"):
		var sp: Array = def.spawn
		ob.add_item("Старт карты")
		pts.append(Vector3(float(sp[0]), float(sp[1]), float(sp[2])))
	var i: int = 0
	for n in get_tree().get_nodes_in_group("spawn_points"):
		i += 1
		ob.add_item("Вход %d (%s)" % [i, String(n.name)])
		pts.append((n as Node3D).global_position)
	for d in def.get("districts", []):
		var r: Array = (d as Dictionary).get("rect", [])
		if r.size() < 4:
			continue
		ob.add_item(String(d.get("name", d.get("id", "?"))))
		pts.append(Vector3((float(r[0]) + float(r[2])) * 0.5, NAN, (float(r[1]) + float(r[3])) * 0.5))
	ob.item_selected.connect(func(idx: int) -> void:
		if idx <= 0 or idx >= pts.size():
			return
		_teleport_to(pts[idx] as Vector3)
		ob.select(0))
	return ob


func _teleport_to(p: Vector3) -> void:
	var me: Player = null
	for node: Node in get_tree().get_nodes_in_group("players"):
		if (node as Player).is_local():
			me = node as Player
			break
	if me == null:
		return
	var y: float = p.y
	var t: Node = get_tree().get_first_node_in_group("district_terrain")
	if is_nan(y) and t and t.has_method("height_at"):
		y = float(t.call("height_at", p.x, p.z))
	# сверху вниз: на крышу, крыльцо, а не внутрь
	var q: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(Vector3(p.x, (0.0 if is_nan(y) else y) + 120.0, p.z), Vector3(p.x, (0.0 if is_nan(y) else y) - 50.0, p.z))
	q.exclude = [me.get_rid()]
	var hit: Dictionary = me.get_world_3d().direct_space_state.intersect_ray(q)
	if not hit.is_empty():
		y = (hit.position as Vector3).y
	me.global_position = Vector3(p.x, (0.0 if is_nan(y) else y) + 0.1, p.z)
	me.velocity = Vector3.ZERO


## Точное время рейда: ползунок по 15 минут (сдвинул — время задано: в рейде сразу, у хоста — у
## всех, следующие рейды начнутся с него) и «Авто» — снова по времени суток из убежища. Пока
## ползунок тащат — меняется только подпись, часы переводятся, когда его отпустили.
func _hour_row() -> HBoxContainer:
	var row: HBoxContainer = HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var s: HSlider = HSlider.new()
	s.editable = not Net.is_networked() or Net.is_host()
	s.min_value = 0.0
	s.max_value = 23.75
	s.step = 0.25
	s.value = Settings.raid_hour if Settings.raid_hour >= 0.0 else (DayCycle.current.hour if DayCycle.current else 12.0)
	s.custom_minimum_size = Vector2(200, 24)
	s.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	s.focus_mode = Control.FOCUS_NONE
	var v: Label = Label.new()
	v.custom_minimum_size.x = 92
	var auto: Button = Button.new()
	auto.text = "Авто"
	auto.disabled = Net.is_networked() and not Net.is_host()
	auto.focus_mode = Control.FOCUS_NONE
	auto.tooltip_text = "Время — как выбрано у стола в убежище (день 11:00, закат 18:00, ночь 23:00)."
	var show: Callable = func(h: float) -> void:
		var m: int = int(round(h * 60.0)) % (24 * 60)
		v.text = "%02d:%02d" % [m / 60, m % 60] if Settings.raid_hour >= 0.0 or s.has_meta("touched") else "%02d:%02d авто" % [m / 60, m % 60]
	show.call(s.value)
	# меню строится до рейда — при каждом открытии ползунок встаёт на нынешнее время рейда
	s.visibility_changed.connect(func() -> void:
		if s.is_visible_in_tree() and DayCycle.current and Settings.raid_hour < 0.0:
			s.set_value_no_signal(snappedf(DayCycle.current.hour, 0.25))
			show.call(s.value))
	var dragging: Array = [false]
	s.drag_started.connect(func() -> void: dragging[0] = true)
	s.drag_ended.connect(func(_changed: bool) -> void:
		dragging[0] = false
		s.set_meta("touched", true)
		Settings.set_raid_hour(s.value)
		show.call(s.value))
	s.value_changed.connect(func(x: float) -> void:
		s.set_meta("touched", true)
		show.call(x)
		# щелчок по полосе / колесо — сразу; перетаскивание — когда отпустят
		if not dragging[0]:
			Settings.set_raid_hour(x))
	auto.pressed.connect(func() -> void:
		s.remove_meta("touched")
		Settings.set_raid_hour(-1.0)
		show.call(s.value))
	row.add_child(s)
	row.add_child(v)
	row.add_child(auto)
	return row



func run_command(cmd: String) -> String:
	var a: PackedStringArray = cmd.strip_edges().split(" ", false)
	var out: String = ""
	if a.size() >= 2 and a[0] == "quest":
		if Net.is_networked() and not Net.is_host() and not a[1] in ["list", "state"]:
			return "задания изменяет хост"
		var fallback: String = Quests.tracked() if Quests.tracked() != "" else (Quests.ids()[0] if not Quests.ids().is_empty() else "")
		var qid: String = a[2] if a.size() > 2 and not a[2].is_valid_int() else fallback
		match a[1]:
			"start":
				out = Quests.dev_start(qid)
			"stage":
				out = Quests.dev_stage(qid, int(a[a.size() - 1]))
			"reset":
				out = Quests.dev_reset(qid)
			"completeObjective", "obj":
				out = Quests.dev_complete_objective(a[2] if a.size() > 2 else "")
			"list", "state":
				out = Quests.dev_describe()
			_:
				out = "quest start|stage|reset|completeObjective|list <id> [n]"
	elif a.size() >= 1 and a[0] in ["give", "mount", "unmount", "sight", "light", "laser", "spawn", "plate", "dur", "stats", "list", "arsenal", "equip", "toggle", "damage", "set"]:
		# арсенал: выдать, обвес, прицел / фонарь / ЛЦУ, ИИ с выкладкой, плиты, износ
		out = ArsenalDev.run(get_tree(), a.slice(1) if a[0] == "arsenal" else a)
	elif a.size() >= 1 and a[0] == "god":
		# чит: бессмертие вкл/выкл (как в меню Esc → Читы)
		Settings.set_god(not Settings.god if a.size() < 2 else a[1] in ["1", "on", "вкл"])
		out = "бессмертие: " + ("включено" if Settings.god else "выключено")
	elif a.size() >= 1 and a[0] == "unlock":
		# чит плейтеста: весь товар Михалыча и все модули убежища (как в меню Esc → Читы)
		Settings.set_unlock_all(not Settings.unlock_all if a.size() < 2 else a[1] in ["1", "on", "вкл"])
		out = "всё открыто (Михалыч, верстак, модули, гравировка): " + ("да" if Settings.unlock_all else "нет")
	elif a.size() >= 1 and a[0] == "shoploot":
		# чит: находимое в рейде — в продаже у Михалыча
		Settings.set_shop_loot(not Settings.shop_loot if a.size() < 2 else a[1] in ["1", "on", "вкл"])
		out = "лут в продаже у Михалыча: " + ("да" if Settings.shop_loot else "нет")
	elif a.size() >= 1 and a[0] == "fly":
		# отладка: полёт сквозь всё (как в меню Esc → Читы)
		Settings.cheat_fly = not Settings.cheat_fly if a.size() < 2 else a[1] in ["1", "on", "вкл"]
		out = "полёт: " + ("включён" if Settings.cheat_fly else "выключен")
	elif a.size() >= 1 and a[0] == "speed":
		Settings.cheat_speed = clampf(float(a[1]) if a.size() > 1 else 1.0, 0.1, 20.0)
		out = "скорость ×%.2f" % Settings.cheat_speed
	elif a.size() >= 1 and a[0] == "upgrade":
		out = _dev_upgrade(a)
	elif a.size() >= 1 and a[0] == "event":
		# событие рейда сейчас: свет погас, генератор встал, сброс груза, ЧВК (решает хост)
		out = _dev_event(a[1] if a.size() > 1 else "")
	elif a.size() >= 1 and a[0] == "help":
		out = "god — бессмертие вкл/выкл · fly — полёт · speed 3 — скорость ×3 · unlock — открыть всё: товар Михалыча, верстак, модули убежища, гравировка · shoploot — лут в продаже у Михалыча · upgrade workbench 2 — уровень модуля без затрат (в убежище) · event outage|generator|drop|pmc — событие рейда сейчас · quest start missing_anton · quest stage missing_anton 3 · quest completeObjective · quest reset missing_anton · quest list
" + ArsenalDev.HELP
	else:
		out = "неизвестно: " + cmd + " (help)"
	Settings.changed.emit()
	return out


## Для плейтеста: поднять модуль своего профиля без денег, деталей и доверия.
## Понижать уровень нельзя: уменьшение тайника или кармана может вытеснить предметы.
func _dev_upgrade(a: PackedStringArray) -> String:
	var usage: String = "upgrade <workbench|generator|pocket|stash|radio> <уровень>; пример: upgrade workbench 2"
	if a.size() != 3 or not a[2].is_valid_int():
		return usage
	var id: String = a[1]
	var module: Dictionary = Upgrades.find(id)
	if module.is_empty():
		return "нет такого модуля: " + id + " · " + usage
	var level: int = int(a[2])
	var maximum: int = Upgrades.max_level(id)
	if level < 1 or level > maximum:
		return "уровень %s: 1–%d" % [String(module.name), maximum]
	if Net.is_networked() and not multiplayer.is_server():
		return "только на хосте"
	if Raid.current != null or get_tree().get_first_node_in_group("hideout_level") == null:
		return "модули повышаются в убежище"
	Profile.ensure()
	var current: int = Upgrades.level(id)
	if level < current:
		return "%s уже уровня %d; понижение отключено" % [String(module.name), current]
	Profile.modules[id] = level
	Profile.save()
	return "%s: уровень %d, сохранено. Переоткрой окно модуля или конструктор." % [String(module.name), level]


func _dev_event(kind: String) -> String:
	if not kind in ["outage", "generator", "drop", "pmc"]:
		return "event outage|generator|drop|pmc"
	if RaidEvents.current == null:
		return "не в рейде"
	if Net.is_networked() and not multiplayer.is_server():
		return "события рейда решает хост"
	RaidEvents.current.trigger(kind)
	return "событие: " + kind
