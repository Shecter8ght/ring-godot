extends Node3D
## Перелезание и бросок на землю на пустом полигоне: игрок перелезает через преграду по пояс (Пробел),
## через стену выше роста — нет; Alt вбок — рывок и лёжа; мародёр идёт за звуком за длинную
## преграду — перелезает по связке навигации, а не обходит. С окном — снимки vault_*.png.
## godot --path . res://tools/vault_test.tscn

var _fails: int = 0


func _ready() -> void:
	RaidEvents.enabled = false
	await get_tree().process_frame
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-50, 30, 0)
	add_child(sun)
	var env := WorldEnvironment.new()
	env.environment = Environment.new()
	env.environment.ambient_light_color = Color(0.5, 0.5, 0.55)
	env.environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	add_child(env)
	var geo := StaticBody3D.new()
	geo.add_to_group("nav_source")
	add_child(geo)
	_box(geo, Vector3(0, -0.5, 0), Vector3(80, 1, 80), Color(0.4, 0.4, 0.38))
	# длинная преграда по пояс (1 м, обход — 30 м), низкий забор и стена выше роста
	_box(geo, Vector3(0, 0.5, 0), Vector3(40, 1.0, 0.4), Color(0.6, 0.5, 0.4))
	_box(geo, Vector3(0, 0.55, -6), Vector3(8, 1.1, 0.1), Color(0.35, 0.55, 0.3))
	_box(geo, Vector3(0, 1.25, 12), Vector3(8, 2.5, 0.4), Color(0.5, 0.5, 0.6))
	# крыша с парапетом: за ним нет пола — перелез и падаешь уже обычной физикой
	_box(geo, Vector3(-16, 2, 12), Vector3(6, 4, 6), Color(0.5, 0.55, 0.6))
	_box(geo, Vector3(-16, 4.5, 9.1), Vector3(6, 1.0, 0.2), Color(0.6, 0.55, 0.45))
	var cam := Camera3D.new()
	add_child(cam)
	cam.look_at_from_position(Vector3(9, 11, -9), Vector3(0, 0, 0))
	var region := NavigationRegion3D.new()
	var nm := NavigationMesh.new()
	nm.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	nm.geometry_collision_mask = Hitscan.LAYER_WORLD
	nm.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	nm.geometry_source_group_name = "nav_source"
	nm.cell_size = 0.25
	nm.cell_height = 0.25
	nm.agent_height = 1.8
	nm.agent_radius = 0.5
	nm.agent_max_climb = 0.4
	region.navigation_mesh = nm
	add_child(region)
	region.bake_navigation_mesh(false)
	# испечённый меш попадает в карту не сразу — дождаться, пока он там появится
	var map := get_world_3d().navigation_map
	for i in range(120):
		await get_tree().physics_frame
		if NavigationServer3D.map_get_iteration_id(map) > 0 and NavigationServer3D.map_get_closest_point(map, Vector3(5, 0, -5)).distance_to(Vector3(5, 0, -5)) < 1.0:
			break
	var links: int = await Vault.build_links(region, region)
	_check("связки «перелезть» через длинную преграду", links > 0, "%d" % links)
	if links > 0:
		await NavigationServer3D.map_changed
	# игрок
	var pl := (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	pl.name = "Player_1"
	add_child(pl)
	pl.global_position = Vector3(3, 0.05, -1.0)
	pl.health.hp = 1e9
	await _frames(10)
	var armed := pl.weapon_id
	_face(pl, Vector3(0, 0, 1))
	await _press("vault", 3)
	await get_tree().create_timer(0.3).timeout
	_check("клип перелезания у персонажа, оружие убрано", String((pl.get("_animator") as CharacterAnimator).get("_current")) == "vault" and pl.weapon_id == "", pl.weapon_id)
	_save("vault_mid")
	await get_tree().create_timer(0.9).timeout
	_check("перелез через преграду по пояс", pl.global_position.z > 0.5 and pl.global_position.y < 0.3, str(pl.global_position))
	_check("после перелезания оружие снова в руках", pl.weapon_id == armed, pl.weapon_id)
	# стена выше роста
	pl.global_position = Vector3(0, 0.05, 11.0)
	await _frames(5)
	_face(pl, Vector3(0, 0, 1))
	await _press("vault", 3)
	await get_tree().create_timer(1.2).timeout
	_check("через стену выше роста — нет", pl.global_position.z < 11.8, str(pl.global_position))
	# забор 1,1 м: центр тела стоит чуть дальше прежней досягаемости 1,0 м
	pl.global_position = Vector3(3, 0.05, -7.1)
	await _frames(5)
	_face(pl, Vector3(0, 0, 1))
	await _press("vault", 3)
	await get_tree().create_timer(1.2).timeout
	_check("низкий забор — перелез с фактической дистанции тела", pl.global_position.z > -6.0, str(pl.global_position))
	# парапет крыши: за ним воздух, после перелезания начинается обычное падение
	pl.global_position = Vector3(-16, 4.05, 9.9)
	await _frames(5)
	_face(pl, Vector3(0, 0, -1))
	await _press("vault", 3)
	await get_tree().create_timer(1.5).timeout
	_check("парапет крыши — перелез наружу и падает", pl.global_position.z < 9.0 and pl.global_position.y < 4.0, str(pl.global_position))
	# Alt на месте — не бросается (бросок только в сторону движения)
	pl.global_position = Vector3(-6, 0.05, 5.0)
	await _frames(5)
	await _press("dive", 2)
	await get_tree().create_timer(0.3).timeout
	_check("Alt на месте — броска нет", pl.stance == Player.Stance.STAND, "стойка %d" % pl.stance)
	# бросок вбок: Alt + вправо
	pl.global_position = Vector3(-6, 0.05, 5.0)
	await _frames(5)
	var x0 := pl.global_position.x
	Input.action_press("move_right")
	await _frames(3)
	await _press("dive", 2)
	Input.action_release("move_right")
	await get_tree().create_timer(0.15).timeout
	_save("vault_dive")
	await get_tree().create_timer(0.6).timeout
	var moved := pl.global_position.x - x0
	_check("бросок вбок — лёжа, отлетел", pl.stance == Player.Stance.PRONE and moved > 1.0, "стойка %d, сдвиг %.2f" % [pl.stance, moved])
	pl.global_position = Vector3(30, 0.05, 30)
	# мародёр: идёт на звук за преграду
	var m := (load("res://scenes/ai/marauder.tscn") as PackedScene).instantiate() as Marauder
	m.name = "M1"
	add_child(m)
	m.global_position = Vector3(2, 0.1, -4)
	await get_tree().create_timer(1.0).timeout
	m.investigate_at(Vector3(2, 0, 5))
	var t := 0.0
	var used := false
	var animated := false
	while t < 9.0:
		await get_tree().physics_frame
		t += get_physics_process_delta_time()
		used = used or float(m.get("_vault_t")) >= 0.0
		animated = animated or (float(m.get("_vault_t")) >= 0.0 and String((m.get_node("CharacterAnimator") as CharacterAnimator).get("_current")) == "vault")
		if m.global_position.z > 3.0:
			break
	_check("мародёр перелез по связке с клипом, а не обошёл", used and animated and m.global_position.z > 1.0 and t < 8.0, "%.1f с, %s" % [t, str(m.global_position)])
	print("vault_test: провалено %d" % _fails)
	get_tree().quit(1 if _fails > 0 else 0)


func _face(pl: Player, dir: Vector3) -> void:
	pl.get_node("Body").rotation.y = atan2(dir.x, dir.z)
	pl.cursor_ground = pl.global_position + dir * 5.0


func _box(body: StaticBody3D, c: Vector3, size: Vector3, col: Color) -> void:
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	cs.position = c
	body.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	var mat := StandardMaterial3D.new()
	mat.albedo_color = col
	mi.material_override = mat
	mi.position = c
	body.add_child(mi)


func _press(a: String, frames: int) -> void:
	Input.action_press(a)
	await _frames(frames)
	Input.action_release(a)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().physics_frame


func _check(what: String, ok: bool, info: String) -> void:
	if not ok:
		_fails += 1
	print("  [%s] %s  %s" % ["ok" if ok else "FAIL", what, info])


func _save(n: String) -> void:
	if DisplayServer.get_name() != "headless":
		get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
