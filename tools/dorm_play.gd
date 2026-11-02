extends Node3D
## Общежитие с настоящим игроком (владелец 2026-11-02): персонаж, камера, оружие и скорость игры в стенде общежития
## со светом стенда; боты расставляются в свободном полёте в любом месте (на крыше, на лестницах, в комнатах любого
## этажа), потом — в тело игрока, и боты оживают.
##   tools/dorm_play.cmd
## Расстановка (полёт): WASD и мышь, Shift — быстрее, Space / C — вверх / вниз; ЛКМ — бот в точку под прицелом (смотрит
## туда же, куда камера), ПКМ — убрать бота под прицелом; 1–5 — кого ставить; G — игрок сюда; Del — убрать всех;
## Backspace — заново (боты и игрок на местах расстановки, убитые встают); Enter — в тело игрока, игра.
## Игра: клавиши игры; Tab — окно со всем оружием игры; F — дверь; Enter — обратно в полёт (боты замирают).
## Всегда: Esc — мышь и панель (свет, бессмертие); F1–F8, F9 — свет как в прогулке (tools/dorm_study.cmd); F10 — без интерфейса.
## Проверка: --headless res://tools/dorm_play.tscn -- check (навигация по этажам, крыше и пожарным лестницам, расстановка,
## боты оживают и идут на шум, оружие из окна); с окном -- shots — снимки docs/screens/dorm/play_*.

const LEVEL: String = "res://scenes/levels/dorm_study.tscn"
const PLAYER_SCENE: String = "res://scenes/player/player.tscn"
const RIG_SCENE: String = "res://scenes/player/camera_rig.tscn"
const MARAUDER_SCENE: String = "res://scenes/ai/marauder.tscn"
## Кого ставить (клавиши 1–5): типы Balance.AI_ARCHETYPES; "" — случайный мародёр.
const BOT_TYPES: Array[String] = ["", "gunner", "heavy", "pmc", "rival"]
const START_LOCATION: int = 8
const FLY_SPEED: float = 6.0
const FLY_FAST: float = 18.0
const LOOK_SENS: float = 0.0025
## Бот у закрытой двери открывает её (полотна стенда — не Door игры, сами боты их не трогают).
const DOOR_REACH: float = 1.4

var plan: Dictionary = {}
var world: Node3D
var lighting: Node3D
var mode: String = "fly"
var run_mode: String = "play"
var player: Player
var rig: CameraRig
var fly_cam: Camera3D
var fly_yaw: float = 0.0
var fly_pitch: float = 0.0
var player_start: Vector3
var player_yaw: float = 0.0
## Расстановка: {"at", "yaw", "type", "node"}; node — живой бот этой точки.
var bots: Array[Dictionary] = []
var bot_type: int = 0
var nav_region: NavigationRegion3D
var nav_ready: bool = false
var god: bool = true
var picker: RangeWeaponPicker
var marker: Node3D
var marker_label: Label3D
var marker_mat: StandardMaterial3D
var hud: CanvasLayer
var help: Label
var status: Label
var panel: Control
var hud_hidden: bool = false
var light_attributes: CameraAttributes
var door_timer: float = 0.0
var results: Array[Dictionary] = []
## Слои интерфейса камеры игрока (прицел, патроны, ранения), видимые до полёта: в полёте спрятаны, потом — как были.
var rig_layers: Dictionary = {}


func _enter_tree() -> void:
	Profile.use_file("user://profile_dorm_play_test.json", true)


func _ready() -> void:
	get_node("/root/Pause").set_process_input(false)
	get_node("/root/Quests").process_mode = Node.PROCESS_MODE_DISABLED
	get_node("/root/Contracts").process_mode = Node.PROCESS_MODE_DISABLED
	for arg: String in OS.get_cmdline_user_args():
		if arg in ["check", "shots"]:
			run_mode = arg
	plan = JSON.parse_string(FileAccess.get_file_as_string("res://data/blockouts/dorm.json")) as Dictionary
	DisplayServer.window_set_title("RING · Общежитие · игрок и боты")
	world = (load(LEVEL) as PackedScene).instantiate() as Node3D
	add_child(world)
	lighting = world.get_node_or_null("Lighting") as Node3D
	var location: Dictionary = plan.locations[START_LOCATION-1]
	player_start = _vec(location.foot)
	var look: Vector3 = _vec(location.look)-player_start
	player_yaw = atan2(look.x, look.z)
	fly_cam = Camera3D.new()
	fly_cam.name = "FlyCamera"
	fly_cam.near = 0.05
	add_child(fly_cam)
	_ui()
	_build_marker()
	_spawn_player()
	await _frames(6)
	_bake_navigation()
	if lighting!=null and run_mode!="check":
		for index: int in range(plan.environment.cases.size()):
			if String(plan.environment.cases[index].id)==String(plan.environment.default):
				await lighting.call("set_case",index)
	_set_mode("fly")
	fly_cam.global_position = player_start+Vector3(0, 6.0, 8.0)
	_fly_look_at(player_start+Vector3.UP*1.5)
	if run_mode=="check":
		await _check_run()
	elif run_mode=="shots":
		await _shots()


# ---------------------------------------------------------------- игрок, камера, свет

func _spawn_player() -> void:
	player = (load(PLAYER_SCENE) as PackedScene).instantiate() as Player
	player.name = "Player_1"
	add_child(player)
	player.global_position = player_start+Vector3.UP*0.05
	player.face(player_yaw)
	rig = (load(RIG_SCENE) as PackedScene).instantiate() as CameraRig
	rig.name = "CameraRig"
	rig.target_path = NodePath("../Player_1")
	add_child(rig)
	rig.set("_look_yaw", player_yaw)
	player.set_god(god)


func _despawn_player() -> void:
	if is_instance_valid(picker) and picker.is_open():
		picker.close_ui()
	for node: Node in [rig, player]:
		if is_instance_valid(node):
			remove_child(node)
			node.queue_free()
	rig = null
	player = null
	rig_layers.clear()


func _play_camera() -> Camera3D:
	return rig.get("_ads_cam") as Camera3D if is_instance_valid(rig) else null


## Свет стенда смотрит из этой камеры: пробы отражений и оконные источники — у её этажа, своя экспозиция.
func _light_camera(cam: Camera3D) -> void:
	if lighting==null or cam==null:
		return
	if light_attributes==null:
		lighting.call("attach_camera",cam)
		light_attributes = cam.attributes
	else:
		cam.attributes = light_attributes
		lighting.set("camera",cam)
		lighting.call("update_active_probes")


func _set_mode(value: String) -> void:
	mode = value
	var play: bool = mode=="play"
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node):
			(bot.node as Node).process_mode = Node.PROCESS_MODE_INHERIT if play else Node.PROCESS_MODE_DISABLED
			_bot_label(bot).visible = not play
	if is_instance_valid(player):
		player.process_mode = Node.PROCESS_MODE_INHERIT if play else Node.PROCESS_MODE_DISABLED
		rig.process_mode = player.process_mode
		for layer: Node in rig.find_children("*","CanvasLayer",true,false):
			if play:
				if rig_layers.has(layer):
					(layer as CanvasLayer).visible = bool(rig_layers[layer])
			elif not rig_layers.has(layer):
				rig_layers[layer] = (layer as CanvasLayer).visible
				(layer as CanvasLayer).visible = false
		if play:
			rig_layers.clear()
	marker.visible = not play
	if play:
		var cam: Camera3D = _play_camera()
		if cam!=null:
			cam.current = true
			_light_camera(cam)
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	else:
		var cam: Camera3D = _play_camera()
		if cam!=null and cam.current:
			fly_cam.global_transform = cam.global_transform
			fly_yaw = cam.global_rotation.y+PI
			fly_pitch = -cam.global_rotation.x
		fly_cam.current = true
		_light_camera(fly_cam)
		if run_mode=="play":
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if panel.visible else Input.MOUSE_MODE_CAPTURED
	_update_help()


# ---------------------------------------------------------------- навигация ботов

## Навмеш из коллизий общежития и двора (как у рейдов — STATIC_COLLIDERS слоя мира); полотна дверей не входят,
## чтобы закрытая дверь не резала путь — боты открывают её сами (_open_doors_near_bots).
func _bake_navigation() -> void:
	for body: Node in world.find_children("*","StaticBody3D",true,false):
		var door: bool = false
		var node: Node = body.get_parent()
		while node!=null and node!=world:
			if node.is_in_group("dorm_study_doors"):
				door = true
				break
			node = node.get_parent()
		if not door:
			body.add_to_group("dorm_nav_source")
	nav_region = NavigationRegion3D.new()
	nav_region.name = "Navigation"
	var mesh: NavigationMesh = NavigationMesh.new()
	mesh.geometry_parsed_geometry_type = NavigationMesh.PARSED_GEOMETRY_STATIC_COLLIDERS
	mesh.geometry_collision_mask = Hitscan.LAYER_WORLD
	mesh.geometry_source_geometry_mode = NavigationMesh.SOURCE_GEOMETRY_GROUPS_WITH_CHILDREN
	mesh.geometry_source_group_name = "dorm_nav_source"
	# клетка мельче, чем у рейдов: марш 1,5 м между стеной и поручнем при клетке 0,25 и радиусе 0,4 съедался целиком
	mesh.cell_size = 0.1
	mesh.cell_height = 0.1
	mesh.agent_height = 1.8
	mesh.agent_radius = 0.3
	mesh.agent_max_climb = 0.3
	mesh.agent_max_slope = 46.0
	nav_region.navigation_mesh = mesh
	var map: RID = get_world_3d().navigation_map
	NavigationServer3D.map_set_cell_size(map,mesh.cell_size)
	NavigationServer3D.map_set_cell_height(map,mesh.cell_height)
	add_child(nav_region)
	var started: int = Time.get_ticks_msec()
	nav_region.bake_finished.connect(func() -> void:
		nav_ready = true
		print("dorm_play: навмеш готов за %.1f с, %d многоугольников" % [(Time.get_ticks_msec()-started)/1000.0,nav_region.navigation_mesh.get_polygon_count()])
		_update_help(), CONNECT_ONE_SHOT)
	nav_region.bake_navigation_mesh(true)


func _nav_point(at: Vector3) -> Vector3:
	if not nav_ready:
		return Vector3.INF
	var map: RID = get_world_3d().navigation_map
	var snapped: Vector3 = NavigationServer3D.map_get_closest_point(map,at)
	return snapped if snapped.distance_to(at)<0.8 else Vector3.INF


func _open_doors_near_bots() -> void:
	var walkers: Array[Vector3] = []
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node) and ((bot.node as Node).get_node("Health") as Health).alive:
			walkers.append((bot.node as Node3D).global_position)
	if walkers.is_empty():
		return
	for door: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
		if bool(door.get("is_open")):
			continue
		var data: Dictionary = door.get("data") as Dictionary
		var center: Vector3 = (door as Node3D).to_global(Vector3(float(data.width)*0.5,1.0,0.0))
		for at: Vector3 in walkers:
			if absf(at.y+1.0-center.y)<1.2 and Vector2(at.x-center.x,at.z-center.z).length()<DOOR_REACH:
				door.call("set_open",true)
				break


# ---------------------------------------------------------------- боты

func _place_bot(at: Vector3, yaw: float, type: String) -> Dictionary:
	var bot: Dictionary = {"at": at, "yaw": yaw, "type": type, "node": null}
	bots.append(bot)
	_spawn_bot(bot)
	return bot


func _spawn_bot(bot: Dictionary) -> void:
	var m: Marauder = (load(MARAUDER_SCENE) as PackedScene).instantiate() as Marauder
	m.name = "Bot_%d" % (bots.find(bot)+1)
	if String(bot.type)!="":
		m.archetype = String(bot.type)
	var dir: Vector3 = Vector3(sin(float(bot.yaw)),0.0,cos(float(bot.yaw)))
	# держит место расстановки и смотрит туда, куда смотрела камера; шум и бой — как у всех, потом обратно
	m.home = bot.at
	m.home_radius = 1.0
	m.stay = true
	m.watch_dir = dir
	m.watch_sector_deg = 90.0
	m.process_mode = Node.PROCESS_MODE_DISABLED if mode=="fly" else Node.PROCESS_MODE_INHERIT
	add_child(m)
	m.global_position = (bot.at as Vector3)+Vector3.UP*0.05
	m.set("_facing",float(bot.yaw))
	var label: Label3D = Label3D.new()
	label.name = "PlaceLabel"
	label.text = String((Balance.AI_ARCHETYPES[m.archetype] as Dictionary).get("name",m.archetype))
	label.position = Vector3(0,2.15,0)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 40
	label.pixel_size = 0.004
	label.outline_size = 6
	label.no_depth_test = true
	label.visible = mode=="fly"
	m.add_child(label)
	bot.node = m


func _bot_label(bot: Dictionary) -> Label3D:
	return (bot.node as Node).get_node("PlaceLabel") as Label3D


func _remove_bot(bot: Dictionary) -> void:
	if is_instance_valid(bot.node):
		(bot.node as Node).queue_free()
	bots.erase(bot)


func _clear_bots() -> void:
	for bot: Dictionary in bots.duplicate():
		_remove_bot(bot)


## Заново: боты встают на места расстановки живыми, игрок — на старт с полным здоровьем и патронами.
func _restart() -> void:
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node):
			(bot.node as Node).queue_free()
		bot.node = null
	for node: Node in get_children():
		if node is Marauder:
			node.queue_free()
	for bot: Dictionary in bots:
		_spawn_bot(bot)
	_despawn_player()
	_spawn_player()
	await _frames(2)
	_set_mode(mode)


# ---------------------------------------------------------------- полёт и прицел расстановки

func _fly_look_at(target: Vector3) -> void:
	var d: Vector3 = target-fly_cam.global_position
	fly_yaw = atan2(-d.x,-d.z)
	fly_pitch = atan2(d.y,Vector2(d.x,d.z).length())
	_apply_fly_rotation()


func _apply_fly_rotation() -> void:
	fly_cam.global_rotation = Vector3(fly_pitch,fly_yaw,0.0)


func _aim_ray(mask: int) -> Dictionary:
	var from: Vector3 = fly_cam.global_position
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(from,from-fly_cam.global_basis.z*250.0,mask)
	return get_world_3d().direct_space_state.intersect_ray(query)


## Куда встанет бот: на пол под прицелом; прицел в стену — на пол у стены.
func _aim_floor() -> Vector3:
	var hit: Dictionary = _aim_ray(Hitscan.LAYER_WORLD)
	if hit.is_empty():
		return Vector3.INF
	var at: Vector3 = hit.position
	if (hit.normal as Vector3).y<0.6:
		at += (hit.normal as Vector3)*0.45
		var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(at+Vector3.UP*0.2,at+Vector3.DOWN*4.0,Hitscan.LAYER_WORLD)
		var down: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
		if down.is_empty():
			return Vector3.INF
		at = down.position
	return at


func _fly_yaw_dir() -> float:
	var f: Vector3 = -fly_cam.global_basis.z
	return atan2(f.x,f.z)


func _build_marker() -> void:
	marker = Node3D.new()
	marker.name = "BotMarker"
	add_child(marker)
	marker_mat = StandardMaterial3D.new()
	marker_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	marker_mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	marker_mat.no_depth_test = true
	var body: MeshInstance3D = MeshInstance3D.new()
	var capsule: CapsuleMesh = CapsuleMesh.new()
	capsule.radius = 0.32
	capsule.height = 1.8
	body.mesh = capsule
	body.position = Vector3(0,0.9,0)
	body.material_override = marker_mat
	marker.add_child(body)
	var nose: MeshInstance3D = MeshInstance3D.new()
	var box: BoxMesh = BoxMesh.new()
	box.size = Vector3(0.12,0.12,0.7)
	nose.mesh = box
	nose.position = Vector3(0,1.5,0.5)
	nose.material_override = marker_mat
	marker.add_child(nose)
	marker_label = Label3D.new()
	marker_label.position = Vector3(0,2.2,0)
	marker_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	marker_label.font_size = 40
	marker_label.pixel_size = 0.004
	marker_label.outline_size = 6
	marker_label.no_depth_test = true
	marker.add_child(marker_label)


func _update_marker() -> void:
	var at: Vector3 = _aim_floor()
	marker.visible = at!=Vector3.INF and not panel.visible
	if not marker.visible:
		return
	var on_nav: bool = _nav_point(at)!=Vector3.INF
	marker.global_position = at
	marker.global_rotation = Vector3(0,_fly_yaw_dir(),0)
	marker_mat.albedo_color = Color(0.35,1.0,0.45,0.45) if on_nav else Color(1.0,0.6,0.2,0.45)
	marker_label.text = _type_name(BOT_TYPES[bot_type])+("" if on_nav or not nav_ready else " · вне навмеша")


func _type_name(type: String) -> String:
	if type=="":
		return "Мародёр (случайный)"
	return String((Balance.AI_ARCHETYPES[type] as Dictionary).get("name",type))


func _bot_under_aim() -> Dictionary:
	var hit: Dictionary = _aim_ray(Hitscan.LAYER_WORLD|Hitscan.LAYER_MARAUDER)
	if hit.is_empty():
		return {}
	var best: Dictionary = {}
	var best_d: float = 1.3
	for bot: Dictionary in bots:
		if not is_instance_valid(bot.node):
			continue
		var p: Vector3 = (bot.node as Node3D).global_position
		var d: float = Vector2(p.x-(hit.position as Vector3).x,p.z-(hit.position as Vector3).z).length()
		if d<best_d and absf((hit.position as Vector3).y-p.y-0.9)<1.4:
			best = bot
			best_d = d
	return best


func _process(delta: float) -> void:
	if not is_instance_valid(fly_cam) or plan.is_empty():
		return
	if mode=="fly":
		if run_mode=="play" and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
			var move: Vector3 = Vector3.ZERO
			move.x = float(Input.is_physical_key_pressed(KEY_D))-float(Input.is_physical_key_pressed(KEY_A))
			move.z = float(Input.is_physical_key_pressed(KEY_S))-float(Input.is_physical_key_pressed(KEY_W))
			move.y = float(Input.is_physical_key_pressed(KEY_SPACE))-float(Input.is_physical_key_pressed(KEY_C))
			var speed: float = FLY_FAST if Input.is_physical_key_pressed(KEY_SHIFT) else FLY_SPEED
			var basis: Basis = fly_cam.global_basis
			fly_cam.global_position += (basis.x*move.x+basis.z*move.z+Vector3.UP*move.y).limit_length(1.0)*speed*delta
		_update_marker()
	else:
		if is_instance_valid(player):
			# окно оружия: «сдать ствол» возвращает снаряжение профиля, а в стенде его нет — обратно песочница
			if player.loadout_mode and not player.in_range_mode():
				player.loadout_mode = false
			if Input.is_action_just_pressed("interact") and not player.ui_blocked():
				_toggle_door_ahead()
		door_timer -= delta
		if door_timer<=0.0:
			door_timer = 0.2
			_open_doors_near_bots()
	_update_status()


func _toggle_door_ahead() -> void:
	var cam: Camera3D = get_viewport().get_camera_3d()
	var query: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(cam.global_position,cam.global_position-cam.global_basis.z*2.6,Hitscan.LAYER_WORLD)
	query.exclude = [player.get_rid()]
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(query)
	var node: Node = hit.collider as Node if not hit.is_empty() else null
	while node!=null and node!=world:
		if node.is_in_group("dorm_study_doors"):
			node.call("toggle")
			return
		node = node.get_parent()


# ---------------------------------------------------------------- клавиши

func _unhandled_input(event: InputEvent) -> void:
	if run_mode!="play":
		return
	if mode=="fly" and event is InputEventMouseMotion and Input.mouse_mode==Input.MOUSE_MODE_CAPTURED:
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		fly_yaw -= motion.relative.x*LOOK_SENS
		fly_pitch = clampf(fly_pitch-motion.relative.y*LOOK_SENS,-1.5,1.5)
		_apply_fly_rotation()
		return
	if mode=="fly" and event is InputEventMouseButton and (event as InputEventMouseButton).pressed and not panel.visible:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if Input.mouse_mode!=Input.MOUSE_MODE_CAPTURED:
			Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		elif button.button_index==MOUSE_BUTTON_LEFT:
			var at: Vector3 = _aim_floor()
			if at!=Vector3.INF:
				var snapped: Vector3 = _nav_point(at)
				_place_bot(snapped if snapped!=Vector3.INF else at,_fly_yaw_dir(),BOT_TYPES[bot_type])
		elif button.button_index==MOUSE_BUTTON_RIGHT:
			var bot: Dictionary = _bot_under_aim()
			if not bot.is_empty():
				_remove_bot(bot)
		return
	if not (event is InputEventKey and (event as InputEventKey).pressed and not event.is_echo()):
		return
	var key: Key = (event as InputEventKey).physical_keycode
	if is_instance_valid(picker) and picker.is_open():
		return
	match key:
		KEY_ESCAPE:
			_toggle_panel()
			return
		KEY_F1, KEY_F2, KEY_F3, KEY_F4:
			lighting.call("set_case",key-KEY_F1)
		KEY_F5:
			lighting.call("set_cool_corridors",not bool(lighting.get("cool_corridors")))
		KEY_F6, KEY_F7:
			lighting.call("set_case",4+key-KEY_F6)
		KEY_F8:
			lighting.call("set_night_exterior",not bool(lighting.get("night_exterior")))
		KEY_F9:
			lighting.call("set_tarkov",not bool(lighting.get("tarkov")))
		KEY_F10:
			hud_hidden = not hud_hidden
			hud.visible = not hud_hidden
		KEY_ENTER, KEY_KP_ENTER:
			_set_mode("play" if mode=="fly" else "fly")
	if mode=="fly":
		match key:
			KEY_1, KEY_2, KEY_3, KEY_4, KEY_5:
				bot_type = key-KEY_1
				_update_help()
			KEY_G:
				var at: Vector3 = _aim_floor()
				if at!=Vector3.INF:
					player_start = at
					player_yaw = _fly_yaw_dir()
					player.global_position = at+Vector3.UP*0.05
					player.face(player_yaw)
					rig.set("_look_yaw",player_yaw)
			KEY_DELETE:
				_clear_bots()
			KEY_BACKSPACE:
				_restart()
	elif key==KEY_TAB and is_instance_valid(player) and not player.ui_blocked():
		if picker==null:
			picker = RangeWeaponPicker.new()
			picker.name = "WeaponPicker"
			add_child(picker)
		picker.open_for(player)


# ---------------------------------------------------------------- интерфейс

func _ui() -> void:
	hud = CanvasLayer.new()
	hud.name = "DormPlayUI"
	hud.layer = 5
	add_child(hud)
	var root: Control = Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	hud.add_child(root)
	help = Label.new()
	help.position = Vector2(24,18)
	help.add_theme_font_size_override("font_size",17)
	help.add_theme_color_override("font_outline_color",Color(0,0,0,0.9))
	help.add_theme_constant_override("outline_size",6)
	root.add_child(help)
	status = Label.new()
	status.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	status.offset_left = 24
	status.offset_top = -44
	status.add_theme_font_size_override("font_size",17)
	status.add_theme_color_override("font_outline_color",Color(0,0,0,0.9))
	status.add_theme_constant_override("outline_size",6)
	root.add_child(status)
	# Esc: панель света и бессмертия; пока открыта — персонаж стоит, мышь свободна (группа esc_windows)
	var layer: CanvasLayer = CanvasLayer.new()
	layer.name = "DormPlayPanel"
	layer.layer = 15
	layer.set_script(preload("res://tools/dorm_play_panel.gd"))
	add_child(layer)
	panel = Control.new()
	panel.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	panel.visible = false
	layer.add_child(panel)
	layer.set("panel",panel)
	var shade: ColorRect = ColorRect.new()
	shade.color = Color(0.03,0.04,0.05,0.82)
	shade.position = Vector2(18,140)
	shade.size = Vector2(1440,200)
	panel.add_child(shade)
	if lighting!=null:
		lighting.call("create_controls",panel)
	var god_toggle: CheckButton = CheckButton.new()
	god_toggle.text = "Бессмертие игрока"
	god_toggle.position = Vector2(30,290)
	god_toggle.button_pressed = god
	god_toggle.focus_mode = Control.FOCUS_NONE
	god_toggle.toggled.connect(func(on: bool) -> void:
		god = on
		if is_instance_valid(player):
			player.set_god(on))
	panel.add_child(god_toggle)


func _toggle_panel() -> void:
	panel.visible = not panel.visible
	if mode=="fly":
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE if panel.visible else Input.MOUSE_MODE_CAPTURED
	_update_help()


func _update_help() -> void:
	if help==null:
		return
	var lines: PackedStringArray = []
	if mode=="fly":
		lines.append("РАССТАНОВКА · полёт: WASD и мышь, Shift быстрее, Space / C — вверх / вниз")
		lines.append("ЛКМ — поставить «%s» под прицел (смотрит туда же, куда ты) · ПКМ — убрать · 1–5 — кого ставить" % _type_name(BOT_TYPES[bot_type]))
		lines.append("G — игрок сюда · Del — убрать всех · Backspace — заново (все на местах) · Enter — в тело игрока, игра")
		if not nav_ready:
			lines.append("навигация ботов печётся…")
	else:
		lines.append("ИГРА · клавиши игры · Tab — любое оружие · F — дверь · Enter — обратно в полёт (боты замрут)")
	lines.append("Esc — мышь, свет, бессмертие · F1–F8, F9 — свет · F10 — без интерфейса")
	help.text = "\n".join(lines)


func _update_status() -> void:
	var alive: int = 0
	for bot: Dictionary in bots:
		if is_instance_valid(bot.node) and ((bot.node as Node).get_node("Health") as Health).alive:
			alive += 1
	var text: String = "Ботов: %d (живы %d)" % [bots.size(),alive]
	if is_instance_valid(player):
		text += "   ·   HP %d%s" % [int(player.health.hp)," · бессмертие" if god else ""]
		if player.weapon_id!="":
			text += "   ·   в руках: "+ItemDb.item_name(player.weapon_id)
		if not player.is_alive():
			text += "   ·   убит — Enter, затем Backspace: заново"
	status.text = text


# ---------------------------------------------------------------- проверка и снимки

func _check(label: String, passed: bool, details: Variant = "") -> void:
	results.append({"check": label, "pass": passed})
	print("dorm_play: %s · %s %s" % ["PASS" if passed else "FAIL",label,str(details)])


func _path(from: Vector3, to: Vector3) -> PackedVector3Array:
	var map: RID = get_world_3d().navigation_map
	return NavigationServer3D.map_get_path(map,NavigationServer3D.map_get_closest_point(map,from),NavigationServer3D.map_get_closest_point(map,to),true)


func _check_run() -> void:
	var waited: float = 0.0
	while not nav_ready and waited<120.0:
		await get_tree().process_frame
		waited += get_process_delta_time()
	_check("Навмеш общежития и двора испечён",nav_ready,"%.1f с" % waited)
	for i: int in range(30):
		await get_tree().physics_frame
	var roof_y: float = float(plan.scale.floor_y[4])+3.0+0.24
	var ground: Vector3 = player_start
	var targets: Dictionary = {"крыша (через будку или пожарную лестницу)": Vector3(10.0,roof_y,3.0),
		"5 этаж, техэтаж": Vector3(3.95,float(plan.scale.floor_y[4]),0.0),
		"4 этаж, торец хозкрыла": Vector3(41.71,float(plan.scale.floor_y[3]),-38.0),
		"площадка пожарной лестницы А на 3 этаже": Vector3(-1.79,float(plan.scale.floor_y[2]),0.0)}
	for label: String in targets:
		var to: Vector3 = targets[label]
		var path: PackedVector3Array = _path(ground,to)
		var ok: bool = path.size()>1 and path[path.size()-1].distance_to(to)<1.0
		_check("Путь ботов от входа: "+label,ok,"%d точек, конец %s" % [path.size(),str(path[path.size()-1]) if path.size()>0 else "—"])
	# расстановка в полёте: бот на крыше, на техэтаже и в комнате 2 этажа замерли, в игре — живут
	fly_cam.global_position = Vector3(10.0,roof_y+6.0,8.0)
	_fly_look_at(Vector3(10.0,roof_y,3.0))
	await get_tree().process_frame
	var aimed: Vector3 = _aim_floor()
	_check("Прицел полёта сверху попадает на крышу",aimed!=Vector3.INF and absf(aimed.y-roof_y)<0.1,str(aimed))
	var roof_bot: Dictionary = _place_bot(_nav_point(aimed) if _nav_point(aimed)!=Vector3.INF else aimed,0.0,"")
	_place_bot(Vector3(3.95,float(plan.scale.floor_y[4]),0.0),PI*0.5,"pmc")
	var room_bot: Dictionary = _place_bot(Vector3(10.6,float(plan.scale.floor_y[1]),-5.0),PI,"gunner")
	var frozen_at: Vector3 = (room_bot.node as Node3D).global_position
	for i: int in range(60):
		await get_tree().physics_frame
	_check("В полёте боты замерли",(room_bot.node as Node3D).global_position.distance_to(frozen_at)<0.05 and (room_bot.node as Node).process_mode==Node.PROCESS_MODE_DISABLED)
	_set_mode("play")
	(room_bot.node as Marauder).investigate_at(Vector3(20.73,float(plan.scale.floor_y[1]),0.0))
	var moved: float = 0.0
	var noise: Vector3 = Vector3(20.73,float(plan.scale.floor_y[1]),0.0)
	var closest: float = INF
	for i: int in range(900):
		await get_tree().physics_frame
		moved = maxf(moved,(room_bot.node as Node3D).global_position.distance_to(frozen_at))
		closest = minf(closest,(room_bot.node as Node3D).global_position.distance_to(noise))
	_check("В игре бот ожил и пошёл на шум к лестнице",moved>2.0 and closest<4.0,"отошёл на %.1f м, до места шума %.1f м" % [moved,closest])
	_check("Бот на крыше стоит на крыше",absf((roof_bot.node as Node3D).global_position.y-roof_y)<0.3,str((roof_bot.node as Node3D).global_position))
	var opened: int = 0
	for door: Node in get_tree().get_nodes_in_group("dorm_study_doors"):
		opened += 1 if bool(door.get("is_open")) else 0
	_check("Двери на пути бота открываются",opened>0,"%d открыто" % opened)
	var entry: Dictionary = WeaponDb.make_weapon("AK12_BASE",RandomNumberGenerator.new(),[100,100])
	player.set_range_weapon(entry)
	for i: int in range(30):
		await get_tree().physics_frame
	_check("Оружие из окна в руках",player.weapon_id!="" and player.in_range_mode(),player.weapon_id)
	_set_mode("fly")
	_restart()
	for i: int in range(10):
		await get_tree().physics_frame
	var restored: bool = true
	for bot: Dictionary in bots:
		restored = restored and is_instance_valid(bot.node) and (bot.node as Node3D).global_position.distance_to(bot.at)<0.2
	_check("Заново: боты на местах расстановки, игрок на старте",restored and player.global_position.distance_to(player_start)<0.3)
	var fails: int = results.filter(func(r: Dictionary) -> bool: return not bool(r.pass)).size()
	print("dorm_play: проверок %d, провалов %d" % [results.size(),fails])
	get_tree().quit(mini(fails,255))


func _shots() -> void:
	while not nav_ready:
		await get_tree().process_frame
	var y2: float = float(plan.scale.floor_y[1])
	_place_bot(Vector3(30.0,y2,0.0),-PI*0.5,"gunner")
	_place_bot(Vector3(25.6,y2,-5.5),0.0,"pmc")
	_place_bot(Vector3(10.0,float(plan.scale.floor_y[4])+3.24,3.0),PI,"heavy")
	fly_cam.global_position = Vector3(12.0,y2+1.7,0.0)
	_fly_look_at(Vector3(30.0,y2+1.2,0.0))
	await _frames(40)
	_save("play_fly_corridor")
	fly_cam.global_position = Vector3(-6.0,24.0,14.0)
	_fly_look_at(Vector3(10.0,17.4,3.0))
	await _frames(30)
	_save("play_fly_roof")
	player_start = Vector3(14.0,y2,0.0)
	player_yaw = atan2(1.0,0.0)
	_restart()
	await _frames(10)
	_set_mode("play")
	player.set_range_weapon(WeaponDb.make_weapon("AK12_BASE",RandomNumberGenerator.new(),[100,100]))
	await _frames(90)
	_save("play_body")
	get_tree().quit(0)


func _save(name: String) -> void:
	var path: String = ProjectSettings.globalize_path("res://docs/screens/dorm/%s.png" % name)
	get_viewport().get_texture().get_image().save_png(path)
	print("dorm_play: снимок ",path)


func _frames(count: int) -> void:
	for i: int in range(count):
		await get_tree().physics_frame


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]),float(values[1]),float(values[2]))
