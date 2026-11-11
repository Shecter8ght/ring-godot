extends Node3D
## The surface lists, map lifecycle and saved mix go through production Audio.

var checked: int = 0
var failed: int = 0
var heard: Array[String] = []


func check(ok: bool, label: String) -> void:
	checked += 1
	if not ok:
		failed += 1
		push_error(label)


func _ready() -> void:
	var camera: Camera3D = Camera3D.new()
	add_child(camera)
	camera.current = true
	get_tree().current_scene = self
	Audio.event_played.connect(func(id: String, _hook: String, _pos: Vector3) -> void: heard.append(id))
	var surfaces: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/audio_surfaces.json")) as Dictionary
	check(surfaces.footsteps.size() == 13, "13 step surfaces from the owner's screenshot")
	check(surfaces.casings.size() == 8, "8 casing surfaces from the owner's screenshot")
	for entry: Dictionary in surfaces.footsteps:
		check(Audio._bindings.has(entry.hook), "step card: " + String(entry.hook))
		for surface: String in entry.surfaces:
			check(Audio.step_hook(surface) == entry.hook, "step route: " + surface)
	for id: String in WeaponDb.weapon_ids():
		var count: int = 0
		for event: Dictionary in Audio._events.values():
			if event.get("weapon", "") == id:
				count += 1
		check(count > 0, "model has actions: " + id)
	for hook: String in ["osoka_launch", "osoka_motor", "osoka_seeker_track", "osoka_seeker_lock"]:
		check(Audio._bindings.has(hook), "Osoka wired action: " + hook)
	for hook: String in ["step_snow", "step_snow_run", "step_rubble", "step_cardboard", "step_crouch", "step_asphalt_wet"]:
		check(not Audio._bindings.has(hook), "obsolete surface removed: " + hook)
	var probe: AudioStreamWAV = AudioStreamWAV.new()
	probe.mix_rate = 48000
	probe.format = AudioStreamWAV.FORMAT_16_BITS
	probe.data.resize(48000)
	var previews: Dictionary = {}
	for entry: Dictionary in surfaces.casings:
		var hook: String = String(entry.hook)
		var hook_12: String = "shell_12_" + hook.trim_prefix("shell_")
		check(Audio._bindings.has(hook_12), "12-gauge card: " + hook_12)
		for id: String in WeaponDb.weapon_ids():
			var weapon: Dictionary = WeaponDb.weapon(id)
			var expected: String = hook_12 if weapon.caliber == "12x76" else hook
			if weapon["class"] == "SPECIAL":
				expected = ""
			for surface: String in entry.surfaces:
				check(Audio.shell_hook(surface, id) == expected, id + " casing on " + surface)
		previews[hook] = [probe]
		previews[hook_12] = [probe]
	check(Audio._kind_spec("shell_metal") == Audio._kind_spec("shell_12_metal"), "both metal cards use the metal profile")
	Audio.set_preview(previews)
	var x: float = 0.0
	for entry: Dictionary in surfaces.casings:
		var body: StaticBody3D = StaticBody3D.new()
		body.collision_layer = Hitscan.LAYER_WORLD
		body.set_meta("surface", entry.surfaces[0])
		var shape: CollisionShape3D = CollisionShape3D.new()
		var box: BoxShape3D = BoxShape3D.new()
		box.size = Vector3(3, 0.2, 3)
		shape.shape = box
		body.add_child(shape)
		add_child(body)
		body.position = Vector3(x, -0.1, 0)
		x += 4.0
	await get_tree().physics_frame
	await get_tree().physics_frame
	x = 0.0
	for entry: Dictionary in surfaces.casings:
		var pos: Vector3 = Vector3(x, 0, 0)
		camera.position = pos + Vector3(0, 1.6, 1)
		check(Audio._surface_under(pos) == entry.surfaces[0], "physics surface: " + String(entry.hook))
		Audio._shell_land(pos, 0.0, "wpn_hg_01")
		check(not heard.is_empty() and heard.back() == entry.hook, "casing hits the requested surface: " + String(entry.hook))
		var hook_12: String = "shell_12_" + String(entry.hook).trim_prefix("shell_")
		for id: String in ["wpn_sg_02", "wpn_sg_03"]:
			var played: int = heard.size()
			Audio._shell_land(pos, 0.0, id)
			check(heard.size() == played + 1 and heard.back() == hook_12, id + " plays its 12-gauge surface")
		x += 4.0
	Audio.set_preview({})
	var original_12: Array = Audio._samples.shell_12_concrete
	Audio._samples.shell_12_concrete = []
	check(Audio._pick(Audio.shell_hook("concrete", "wpn_sg_02"), Vector3.ZERO) == null, "empty 12-gauge card stays silent")
	Audio._samples.shell_12_concrete = original_12
	# Compare a selected variant on the bench with ordinary gameplay and a live gain edit.
	var originals: Array = Audio._samples.step_wood
	Audio._samples.step_wood = [probe]
	var old_mix: Dictionary = Audio._mix.duplicate(true)
	var file: String = "_test/wood.wav"
	Audio._stream_files[probe.get_instance_id()] = file
	Audio.set_mix_gain("step_wood", -7.0)
	Audio.set_mix_gain("step_wood", -3.0, file)
	var bench: AudioStreamPlayer3D = Audio.preview_event("step_wood", camera.position + Vector3(0, 0, -1), 0) as AudioStreamPlayer3D
	check(is_equal_approx(bench.volume_db, float(Audio._kind_spec("step_wood").db) - 10.0), "bench applies event and individual recording gain")
	Audio.play("step_wood", camera.position + Vector3(0, 0, -1))
	var mixed: Array[Node] = get_tree().get_nodes_in_group("sonora_mixed_players")
	var game: AudioStreamPlayer3D = mixed.back() as AudioStreamPlayer3D
	check(is_equal_approx(bench.volume_db, game.volume_db), "game and bench have exactly the same gain")
	Audio.set_mix_gain("step_wood", -9.0)
	check(is_equal_approx(game.volume_db, float(Audio._kind_spec("step_wood").db) - 12.0), "live players follow gain changes")
	var save_path: String = Audio.mix_save_path
	Audio.mix_save_path = "user://audio_mix_test.json"
	check(Audio.save_mix() == OK, "mix saves")
	var saved: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(Audio.mix_save_path)) as Dictionary
	check(float(saved.events.step_wood) == -9.0 and float(saved.files[file]) == -3.0, "both gain levels persist")
	Audio.mix_save_path = save_path
	Audio._mix = old_mix
	Audio._samples.step_wood = originals
	# A map bed follows map lifecycle, not listener distance, and disappears with that map.
	var map_id: String = "ambient_prospekt"
	Audio._samples[map_id] = [probe]
	var anchor: Node3D = Node3D.new()
	anchor.scene_file_path = "res://scenes/levels/prospekt.tscn"
	add_child(anchor)
	Audio._update_map_ambient()
	check(is_instance_valid(Audio._map_ambient) and Audio._map_ambient.get_parent() == anchor, "map ambience starts on the actual map root")
	check(Audio._map_ambient.bus == &"Ambient", "map ambience uses the Ambient bus")
	var ambient: AudioStreamPlayer = Audio._map_ambient
	anchor.queue_free()
	await get_tree().process_frame
	await get_tree().process_frame
	Audio._update_map_ambient()
	check(not is_instance_valid(ambient), "map ambience stops on unload")
	# Build the actual overlay to catch UI script errors even with a headless renderer.
	var overlay: CanvasLayer = (load("res://src/ui/audio_bench.gd") as Script).new()
	add_child(overlay)
	# The overlay refreshes the registry. Inject an in-memory fixture, never an owner's recording.
	Audio._samples.step_wood = [probe]
	Audio._stream_files[probe.get_instance_id()] = file
	Audio._events.step_wood.files = [file]
	overlay.call("_fill_list")
	check(overlay.get("_list").item_count > 0, "in-game bench builds and lists assigned recordings")
	var list: ItemList = overlay.get("_list") as ItemList
	var last_id: String = ""
	var headers: int = 0
	var sorted: bool = true
	for index: int in range(list.item_count):
		var id: String = String(list.get_item_metadata(index))
		if id == "":
			headers += 1
			check(not list.is_item_selectable(index), "category and model headers cannot be played")
			continue
		if last_id != "":
			sorted = sorted and not bool(overlay.call("_event_less", id, last_id))
		last_id = id
	check(headers >= 6 and sorted, "categories, models and their sounds are alphabetically grouped")
	overlay.call("_select", "step_wood")
	check(overlay.get("_title").text == "Шаг по дереву", "selected row updates the recording details")
	get_tree().paused = true
	overlay.call("_play")
	check((overlay.get("_players") as Array).size() == 1, "in-game bench starts selected recording")
	check((overlay.get("_players") as Array)[0].can_process(), "bench audio also works from the paused game")
	get_tree().paused = false
	if DisplayServer.get_name() != "headless":
		overlay.call("_refresh")
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png("res://docs/screens/audio_bench_20261106.png")
	overlay.call("_stop")
	overlay.queue_free()
	print("AUDIO_CATALOG_TEST checked=%d failed=%d" % [checked, failed])
	get_tree().quit(1 if failed else 0)
