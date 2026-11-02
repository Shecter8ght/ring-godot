extends Node3D
## Gameplay contract: independent purchases, tree, migrations, light, owner-authored hand hook.

var checks: int = 0
var failures: int = 0


func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok:
		failures += 1
	print("PASS " if ok else "FAIL ", label)


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://dozor_integration_test.json", true)
	RaidEvents.enabled = false
	_data()
	_tree()
	_migrations()
	_purchase()
	await _builder()
	await _models()
	await _hand()
	print("dozor_integration_test: checks=%d failures=%d" % [checks, failures])
	get_tree().quit(1 if failures else 0)


func _base(id: String = "wpn_ar_01") -> Dictionary:
	return ItemDb.make(id, 1)


func _assembly(id: String = "tac_flashlight_01", point: String = "side_right") -> Dictionary:
	var r: Array = WeaponBuild.insert(_base(), point, ItemDb.make(DozorGear.MOUNT, 1))
	check(String(r[2]) == "", "mount fits " + point)
	r = WeaponBuild.insert(r[0], point + "/light", ItemDb.make(id, 1))
	check(String(r[2]) == "", "flashlight fits ring " + id)
	return r[0]


func _data() -> void:
	check((InputMap.action_get_events("flashlight")[0] as InputEventKey).physical_keycode == KEY_T, "T flashlight")
	check((InputMap.action_get_events("laser")[0] as InputEventKey).physical_keycode == KEY_L, "L laser")
	check(Balance.TRADER_BUY_PRICES.tac_flashlight_01 == 15000 and Balance.TRADER_BUY_PRICES.tac_flashlight_hp_01 == 80000, "existing prices preserved")
	var trader: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/trader.json"))
	for id: String in DozorGear.VARIANTS:
		check(ItemDb.item_name(id).begins_with("ДОЗОР Ф-1") and trader.stock.has(id), "named item sold " + id)
	check(trader.stock.has(DozorGear.MOUNT), "separate mount sold")
	for id: String in ["tac_flashlight_01", "tac_flashlight_hp_01"]:
		check(float(WeaponDb.attachment(id).light.range) == (30.0 if id == "tac_flashlight_01" else 60.0), "existing beam range " + id)


func _tree() -> void:
	check(WeaponBuild.block(_base(), "side_right", "tac_flashlight_01") != "", "bare flashlight rejected on rail")
	check(WeaponBuild.block(_base("wpn_hg_02"), "underbarrel", DozorGear.MOUNT) != "", "pistol mount rejected")
	var built: Dictionary = _assembly()
	check(WeaponBuild.block(built, "side_right/light#2", "tac_flashlight_hp_01") != "", "ring holds one flashlight")
	var extracted: Array = WeaponBuild.extract(built, "side_right")
	check((extracted[0].mods as Dictionary).is_empty() and String(extracted[1].mods.light.id) == "tac_flashlight_01", "removing ring carries flashlight")
	var inserted: Array = WeaponBuild.insert(extracted[0], "side_left", extracted[1])
	check(String(inserted[2]) == "" and inserted[0].mods.has("side_left/light"), "assembly reinstalled on other rail")
	var draft: Dictionary = BuildPlan.draft_of(built)
	for key: String in draft:
		draft[key].src = {"from": "shop"}
	var plan: Dictionary = BuildPlan.resolve(_base(), draft, {}, {}, {"shop": true})
	check(String(plan.why) == "" and plan.buy.size() == 2 and plan.buy.has(DozorGear.MOUNT), "shop buys both mount and flashlight")
	var bare: Dictionary = {"side_right": {"id": "tac_flashlight_01", "src": {"from": "shop"}}}
	check(String(BuildPlan.resolve(_base(), bare, {}, {}, {"shop": true}).why) != "", "shop cannot bypass mount")
	for id: String in WeaponDb.presets():
		var weapon: Dictionary = WeaponDb.make_weapon(id, RandomNumberGenerator.new())
		for key: String in weapon.get("mods", {}):
			if DozorGear.is_flashlight(WeaponDb.mod_id(weapon.mods[key])) or WeaponDb.mod_id(weapon.mods[key]) == DozorGear.MOUNT:
				check(WeaponBuild.block(weapon, key, WeaponDb.mod_id(weapon.mods[key])) == "", "preset placement " + id + ":" + key)


func _migrations() -> void:
	var old: Dictionary = _base()
	old.mods = {"side_right": {"id": "tac_flashlight_01", "dur": 43.0, "light": true, "slot": 0}}
	var r: Array = WeaponDb.migrate(old)
	check(r[0].mods.has("side_right/light") and (r[1] as Array).is_empty(), "legacy rifle gains complete mount")
	check(float(r[0].mods["side_right/light"].dur) == 43.0 and bool(r[0].mods["side_right/light"].light), "legacy condition and on-state retained")
	check(int(r[0].mods.side_right.slot) == 0 and not r[0].mods["side_right/light"].has("slot"), "placement stays on mount")
	var again: Array = WeaponDb.migrate(r[0])
	check(again[0] == r[0] and (again[1] as Array).is_empty(), "migration idempotent")
	old = _base("wpn_hg_02")
	old.mods = {"underbarrel": {"id": "tac_flashlight_hp_01", "dur": 61.0}}
	r = WeaponDb.migrate(old)
	check((r[0].mods as Dictionary).is_empty() and r[1].size() == 1 and float(r[1][0].dur) == 61.0, "old pistol flashlight returned intact")
	var roundtrip: Dictionary = JSON.parse_string(JSON.stringify(again[0]))
	var loaded: Dictionary = WeaponDb.migrate(roundtrip)[0]
	check(loaded.mods.keys() == roundtrip.mods.keys() and WeaponDb.mod_id(loaded.mods.side_right) == DozorGear.MOUNT
		and int(loaded.mods.side_right.slot) == int(roundtrip.mods.side_right.slot)
		and float(loaded.mods["side_right/light"].dur) == 43.0 and bool(loaded.mods["side_right/light"].light), "save/load roundtrip retains mounted branch")


func _purchase() -> void:
	Profile.equipment = {"primary": _base()}
	Profile.money = 100000
	Profile.trust = 40
	Profile.modules["workbench"] = 3
	var e: Dictionary = _assembly()
	var draft: Dictionary = BuildPlan.draft_of(e)
	for key: String in draft:
		draft[key].src = {"from": "shop"}
	var why: String = Profile.apply_build("equip:primary", -1, draft)
	if why != "":
		print("purchase rejected: ", why)
	check(why == "" and Profile.money == 79000, "real purchase deducts 15000 + 6000")
	check(Profile.equipment.primary.mods.has("side_right/light"), "real purchase installs complete assembly")
	Profile.save()
	Profile._loaded = false
	Profile.ensure()
	check(Profile.equipment.primary.mods.has("side_right/light") and Profile.money == 79000, "profile reload preserves purchase and money")
	var money: int = Profile.money
	var invalid: Dictionary = {"side_right": {"id": "tac_flashlight_hp_01", "src": {"from": "shop"}}}
	check(Profile.apply_build("equip:primary", -1, invalid) != "" and Profile.money == money, "invalid purchase spends nothing")


func _models() -> void:
	for point: String in ["side_left", "side_right", "underbarrel", "optic_primary"]:
		var e: Dictionary = _assembly("tac_flashlight_strobe_01", point)
		var root: Node3D = Node3D.new()
		add_child(root)
		WeaponMods.fit(root, "veras54", e.mods)
		var lights: Array[Node] = root.find_children("Flashlight*", "SpotLight3D", true, false)
		var light: SpotLight3D = lights[0] as SpotLight3D if not lights.is_empty() else null
		check(light != null and light.has_node("Pulse"), "strobe beam exists " + point)
		if light:
			check((-light.global_basis.z).dot(Vector3(0, 0, 1)) > 0.999, "beam faces muzzle " + point)
			var socket: Node3D = root.find_child("FlashlightSocket*", true, false) as Node3D
			check(socket != null and light.global_position.distance_to(socket.global_position + Vector3(0, 0, 0.0805)) < 0.0001, "emitter aligned with ring " + point)
			check(Player.tac_on(e.mods, light, "light") == false, "new flashlight starts off")
			e.mods[point + "/light"].light = true
			check(Player.tac_on(e.mods, light, "light"), "mounted flashlight on-state")
			var pulse: FlashlightPulse = light.get_node("Pulse") as FlashlightPulse
			pulse.set_process(false)
			pulse.apply_at(0.01)
			check(is_equal_approx(light.light_energy, 3.2), "strobe bright phase")
			pulse.apply_at(0.1)
			check(is_zero_approx(light.light_energy) and not (light.get_node("Glow") as Node3D).visible, "strobe dark phase incl glow")
			e.mods[point + "/light"].dur = 0.0
			WeaponMods.update_condition(root, e.mods)
			pulse.apply_at(0.01)
			check(not Player.tac_on(e.mods, light, "light") and is_zero_approx(light.light_energy), "broken strobe stays dark")
		root.free()
	for id: String in DozorGear.VARIANTS.keys() + [DozorGear.MOUNT]:
		var item: Node3D = ItemModels.build(id)
		check(ItemModels.bounds(item).size.length() > 0.02, "standalone model " + id)
		item.free()
	await get_tree().process_frame


func _builder() -> void:
	var builder: WeaponBuilder = WeaponBuilder.open_hideout(self, "equip:primary", -1)
	await get_tree().process_frame
	check(builder._draft.has("side_right/light"), "builder displays nested flashlight")
	builder._remove("side_right")
	check(not builder._draft.has("side_right") and not builder._draft.has("side_right/light"), "builder removes whole mount branch")
	builder.queue_free()
	await get_tree().process_frame


func _hand() -> void:
	var actor: Player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	add_child(actor)
	actor.set_physics_process(false)
	actor.inventory.equipment = {"primary": _base(), "backpack": ItemDb.make(Balance.BACKPACK_START, 1)}
	actor.inventory.items = [ItemDb.make("tac_flashlight_01", 1), ItemDb.make(DozorGear.MOUNT, 1)]
	check(actor.inventory.install_mod("primary", "backpack", 0, "side_right") != "" and actor.inventory.items.size() == 2, "raid rejects bare flashlight without consuming it")
	check(actor.inventory.install_mod("primary", "backpack", 1, "side_right") == "", "raid installs mount from backpack")
	check(actor.inventory.install_mod("primary", "backpack", 0, "side_right/light") == "" and actor.inventory.items.is_empty(), "raid installs flashlight from backpack")
	actor.weapon_slot = "primary"
	actor.weapon_id = "wpn_ar_01"
	actor.loadout_mode = true
	actor._ws_sync("primary", actor.inventory.equipment.primary)
	actor._toggle_tac("light")
	check(bool(actor.weapon_entry().mods["side_right/light"].light), "rifle T toggles nested flashlight")
	actor._toggle_tac("light")
	check(not bool(actor.weapon_entry().mods["side_right/light"].light), "rifle T toggles back off")
	check(actor.inventory.strip_equipped("primary", "mod:side_right") and actor.inventory.items.size() == 1
		and actor.inventory.items[0].mods.has("light"), "raid removal returns ring with flashlight")
	check(actor.inventory.install_mod("primary", "backpack", 0, "side_left") == ""
		and actor.inventory.equipment.primary.mods.has("side_left/light"), "raid reinstall retains complete assembly")
	actor.weapon_id = "wpn_hg_02"
	actor.inventory.items = [{"id": "tac_flashlight_hp_01", "n": 1, "dur": 100.0}]
	var requests: Array = []
	actor.handheld_flashlight_requested.connect(func(id: String, on: bool) -> void: requests.append([id, on]))
	actor._toggle_tac("light")
	actor.handheld_flashlight._process(0.0)
	check(actor.handheld_light_on and requests.size() == 1, "pistol T requests owner hand pose")
	check(actor.handheld_flashlight.model == null, "no guessed holder or floating model")
	check(is_equal_approx(actor.light_view(), 1.0), "unbound handheld does not increase AI visibility")
	var holder: Node3D = Node3D.new()
	add_child(holder)
	actor.bind_handheld_flashlight(holder)
	actor.handheld_flashlight._process(0.0)
	check(actor.handheld_flashlight.emitting(), "authored holder enables model and beam")
	check(is_equal_approx(actor.light_view(), 1.6), "bound high power handheld increases AI visibility")
	actor._toggle_tac("light")
	check(not actor.handheld_light_on and not actor.handheld_flashlight.emitting(), "pistol T stows flashlight")
	actor._toggle_tac("light")
	actor.handheld_flashlight._process(0.0)
	actor.inventory.items = []
	actor.handheld_flashlight._process(0.0)
	check(not actor.handheld_light_on and actor.handheld_flashlight.model == null, "dropped flashlight cannot stay in hand")
	actor.inventory.items = [{"id": "tac_flashlight_01", "dur": 0.0}]
	check(actor.handheld_flashlight.toggle() == "нет", "broken carried flashlight rejected")
	actor.inventory.items = [{"id": "tac_flashlight_01", "dur": 100.0}]
	actor.handheld_flashlight.toggle()
	actor.weapon_id = "wpn_ar_01"
	actor.handheld_flashlight._process(0.0)
	check(not actor.handheld_light_on, "switch to rifle stows handheld flashlight")
	actor.queue_free()
	holder.queue_free()
	await get_tree().process_frame
