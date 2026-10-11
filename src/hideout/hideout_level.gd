@tool
extends Node3D
## Убежище — отдельный уровень между рейдами (старт игры). Старая котельная в зоне 5, отдельная
## от карты ТЦ локация: тайник со снаряжением, верстак, торговец, выход в рейд, тир в котельном зале. Геометрия — CSG-узлы сцены (двигать
## и менять руками), материал — по meta "mat" (id из SectorMaterials, серые "gb_*" тоже можно)
## или "color" (плоский цвет); meta "cut" = false — не растворять у камеры (пол).
## Игрок ходит тем же персонажем и с оружием обращается так же, как в рейде: стрельба, прицел, фонарь
## и ЛЦУ, перезарядка из рюкзака, проверка магазина, гранаты — со своим снаряжением из профиля
## (Inventory игрока — копия профиля: что изменилось в руках — сразу в профиль, что поменяли в окнах
## тайника — сразу в руки). Здесь не ранят. Всё про деньги и вещи — Profile (у каждого свой).
## Кооп: собираемся здесь. Каждый peer говорит, что он в убежище (Net.enter_scene); у всех, кто
## здесь, — одноимённые узлы игроков (Player_<peer>): свой ведёт владелец, чужие приходят
## синхронизатором (только тем, кто в убежище). Рейд всем начинает хост (окно выхода).

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")
const LOUNGE_SCENE := "res://scenes/world/hideout_lounge.tscn"
## Бутылка пива выветривается за столько секунд.
const TIPSY_SEC := 75.0
const TIPSY_SHADER := """
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float k = 0.0;
void fragment() {
	vec2 uv = SCREEN_UV;
	float t = TIME;
	vec2 wob = vec2(sin(t * 1.3 + uv.y * 3.0), cos(t * 1.1 + uv.x * 2.5)) * 0.004 * k;
	vec2 dbl = vec2(0.006 + 0.004 * sin(t * 0.7), 0.001 * cos(t * 0.9)) * k;
	vec3 a = textureLod(screen_tex, uv + wob, 0.0).rgb;
	vec3 b = textureLod(screen_tex, uv + wob + dbl, 0.0).rgb;
	vec3 c = mix(a, b, 0.4 * clamp(k, 0.0, 1.0));
	float vig = smoothstep(0.95, 0.3, length(uv - 0.5));
	c *= mix(1.0, vig, 0.35 * k);
	c = mix(c, c * vec3(1.06, 1.0, 0.88), 0.3 * k);
	COLOR = vec4(c, 1.0);
}
"""

@onready var _camera_rig: CameraRig = $CameraRig
@onready var _spawn: Marker3D = $Spawn

var _player: Player
## Чужие игроки в убежище: peer → узел.
var _others: Dictionary = {}
## Хост закрепляет место при входе; случайный ENet id и задержка roster его не меняют.
var _spawn_slots: Dictionary = {1:0}
var _already_here: Array[int] = []
## Выпито (досуг): качает в глазах, проходит само.
var _tipsy: float = 0.0
var _tipsy_fx: ColorRect
var _ui: HideoutUI
var _prompt: Label
var _money: Label
var _toast: Label
var _toast_t: float = 0.0
## Каким профиль был, когда его в последний раз переписали в руки игроку (или из рук в профиль).
var _inv_sig: String = ""
## Сброшенные магазины на полу (HideoutFloorItem): в профиле их нет, пока не подобраны.
var _floor_items: Array[HideoutFloorItem] = []


## План рейда принят у стола планирования (в сети — хостом): теперь к воротам во дворе, в зону сбора
## (RaidStartZone). Все, кто в убежище, стоят в зоне — отсчёт Balance.SHELTER_YARD.countdown_sec и рейд.
var raid_plan_accepted: bool = false
var _start_left: float = -1.0
var _start_sync: float = 0.0
var _start_label: Label


## Сколько держат «действие» рядом с напарником (обмен вещами начинается после Balance.TRADE.hold_sec).
var _trade_hold: float = 0.0

func _ready() -> void:
	_apply_materials(self)
	if Engine.is_editor_hint():
		return
	add_to_group("hideout_level")
	Profile.ensure()
	Profile.pending_raid = false
	# в рейд — отсюда: со снаряжением профиля (и когда рейд начнёт хост)
	Profile.from_hideout = true
	if Net.is_networked():
		for peer: int in Net.peer_scene:
			if peer != multiplayer.get_unique_id() and Net.visible_in(peer,"hideout"):
				_already_here.append(peer)
	get_tree().node_added.connect(_on_node_added)
	var me := multiplayer.get_unique_id() if Net.is_networked() else 1
	_player = PLAYER_SCENE.instantiate() as Player
	_player.name = "Player_%d" % me
	_player.peer_id = me
	# оружие — как в рейде, со снаряжением профиля
	_player.loadout_mode = true
	if Net.is_networked():
		_player.set_multiplayer_authority(me)
	add_child(_player)
	_player.global_position = _spawn_for(me)
	# в убежище не ранят (граната в тесноте, выстрел в напарника)
	_player.health.invulnerable = true
	_from_profile()
	_camera_rig.set_target(_player)
	_camera_rig.rotation.y = _spawn.rotation.y
	_camera_rig.set_distance(Balance.HIDEOUT_CAMERA_DISTANCE)
	_ui = HideoutUI.new()
	add_child(_ui)
	_build_hud()
	if Net.disconnect_message != "":
		notify(Net.disconnect_message)
		Net.disconnect_message = ""
	# сюжет в убежище: кто вернулся, что изменилось (по флагам)
	var qw := QuestWorld.new()
	qw.name = "QuestWorld"
	add_child(qw)
	# досуг: телевизор, магнитола, пиво, диван (своя сцена — правится в редакторе отдельно)
	if not has_node("Activities") and ResourceLoader.exists(LOUNGE_SCENE):
		add_child((load(LOUNGE_SCENE) as PackedScene).instantiate())
	_build_tipsy()
	Net.scenes_changed.connect(_sync_others)
	Net.enter_scene("hideout")


# ---------------------------------------------------------------- выход в рейд пешком

## Принять или отменить план рейда (окно стола планирования): соло — сам, в сети — только хост.
func accept_raid_plan(on: bool) -> void:
	if Net.is_networked() and not Net.is_host():
		return
	raid_plan_accepted = on
	_start_left = -1.0
	_start_sync = 0.0
	notify("План принят — к воротам во дворе" if on else "План рейда отменён")


## Хост считает, кто стоит в зоне сбора, ведёт отсчёт и начинает рейд; остальным — состояние 4 раза в с.
## true — рейд начат: сцена уже снята с дерева, дальше в этом кадре ничего делать нельзя.
func _tick_raid_start(delta: float) -> bool:
	var zone: RaidStartZone = get_tree().get_first_node_in_group("raid_start_zones") as RaidStartZone
	if zone == null or _player == null:
		return false
	if Net.is_networked() and not Net.is_host():
		return false
	var total: int = 1
	var inside: int = 1 if zone.contains(_player.global_position) else 0
	for id: Variant in _others:
		var other: Player = _others[id] as Player
		if other == null or not is_instance_valid(other):
			continue
		total += 1
		if zone.contains(other.global_position):
			inside += 1
	if raid_plan_accepted and inside == total:
		if _start_left < 0.0:
			_start_left = float(Balance.SHELTER_YARD.countdown_sec)
		_start_left -= delta
		if _start_left <= 0.0:
			return _launch_raid()
	else:
		_start_left = -1.0
	_start_sync -= delta
	if _start_sync <= 0.0:
		_start_sync = 0.25
		Net.broadcast_scene(self, &"_rpc_start_state", [raid_plan_accepted, inside, total, _start_left], false)
	_show_start(raid_plan_accepted, inside, total, _start_left)
	return false


@rpc("authority", "call_remote", "unreliable_ordered")
func _rpc_start_state(accepted: bool, inside: int, total: int, left: float) -> void:
	if accepted != raid_plan_accepted:
		notify("План принят — к воротам во дворе" if accepted else "План рейда отменён")
	raid_plan_accepted = accepted
	_show_start(accepted, inside, total, left)


## Надпись над зоной и подсказка тому, кто в ней стоит.
func _show_start(accepted: bool, inside: int, total: int, left: float) -> void:
	var zone: RaidStartZone = get_tree().get_first_node_in_group("raid_start_zones") as RaidStartZone
	if zone == null or _start_label == null:
		return
	var here: bool = _player != null and zone.contains(_player.global_position)
	var text: String = ""
	if not accepted:
		zone.show_state(false, "СБОР ПЕРЕД РЕЙДОМ")
		if here:
			text = "Сначала примите план рейда у стола планирования" if not Net.is_networked() or Net.is_host() else "План рейда принимает хост — у стола планирования"
	elif left >= 0.0:
		zone.show_state(true, "РЕЙД ЧЕРЕЗ %d" % int(ceil(left)))
		text = "Рейд через %d…" % int(ceil(left))
	else:
		zone.show_state(true, "СБОР: %d / %d" % [inside, total])
		if here or total > 1:
			text = "Сбор у ворот: %d из %d. Ждём остальных." % [inside, total] if total > 1 else ""
	_start_label.text = text
	_start_label.visible = text != ""


func _launch_raid() -> bool:
	_start_left = -1.0
	var block: String = Floors.start_block(Profile.floor)
	if block != "":
		raid_plan_accepted = false
		notify(block)
		return false
	raid_plan_accepted = false
	Floors.pay_fee(Profile.floor)
	if Net.is_networked():
		# все, кто в сети, идут по маршруту хоста (плата — с хоста)
		Net.start_level.rpc(Floors.scene(Profile.floor), RaidConditions.next_own())
	else:
		Profile.pending_raid = true
		get_tree().change_scene_to_file(Floors.scene(Profile.floor))
	return true


## Пиво: чем больше выпито, тем сильнее качает (до 5 бутылок), проходит за TIPSY_SEC на бутылку.
func drink() -> void:
	_tipsy = minf(_tipsy + 1.0, 5.0)


func _build_tipsy() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 4
	add_child(layer)
	_tipsy_fx = ColorRect.new()
	_tipsy_fx.set_anchors_preset(Control.PRESET_FULL_RECT)
	_tipsy_fx.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var sh := Shader.new()
	sh.code = TIPSY_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	_tipsy_fx.material = m
	_tipsy_fx.visible = false
	layer.add_child(_tipsy_fx)


## Раньше детей: их синхронизаторы (Net.scope_sync) сразу знают, что они — в убежище.
func _enter_tree() -> void:
	if not Engine.is_editor_hint():
		set_meta(Net.SCENE_META, "hideout")


func _exit_tree() -> void:
	if Engine.is_editor_hint():
		return
	_floor_to_stash()
	if get_tree().node_added.is_connected(_on_node_added):
		get_tree().node_added.disconnect(_on_node_added)


## Синхронизаторы убежища — только тем, кто тоже в убежище (страховка для созданных без
## Net.scope_sync — фильтр с опозданием на кадр).
func _on_node_added(n: Node) -> void:
	if n is MultiplayerSynchronizer and is_ancestor_of(n):
		Net.filter_sync(n as MultiplayerSynchronizer, "hideout")


## Кто из своих в убежище — тот и стоит здесь; ушёл (в рейд, в меню, отключился) — пропал.
func _sync_others() -> void:
	if not is_inside_tree():
		return
	var me := multiplayer.get_unique_id()
	var want: Array[int] = []
	if Net.is_networked():
		for id in Net.peer_scene:
			if int(id) != me and Net.visible_in(int(id), "hideout"):
				want.append(int(id))
	for id in _others.keys():
		if not int(id) in want:
			if is_instance_valid(_others[id]):
				(_others[id] as Node).queue_free()
			_others.erase(id)
			_spawn_slots.erase(id)
			_already_here.erase(int(id))
	for id in want:
		if _others.has(id):
			continue
		var p := PLAYER_SCENE.instantiate() as Player
		p.name = "Player_%d" % id
		p.peer_id = id
		p.combat_enabled = false
		p.set_multiplayer_authority(id)
		add_child(p)
		p.health.invulnerable = true
		p.global_position = _spawn_for(id)
		if Net.is_host() and has_node("Gameplay/SpawnPoints") and not id in _already_here:
			_assign_spawn.rpc_id(id,int(_spawn_slots[id]))
		# ник над головой игрок ставит себе сам (Player._make_name_tag) — и здесь, и в рейде
		_others[id] = p


## Три сохранённых в сцене спавна; распределение peer одинаково у всех участников.
func _spawn_for(peer: int) -> Vector3:
	if not has_node("Gameplay/SpawnPoints"):
		return _spawn.global_position
	if Net.is_host():
		if not _spawn_slots.has(peer):
			for slot: int in range(3):
				if not slot in _spawn_slots.values():
					_spawn_slots[peer] = slot
					break
		return (get_node("Gameplay/SpawnPoints/PlayerSpawn_%02d" % (int(_spawn_slots.get(peer,0))+1)) as Marker3D).global_position
	var ids: Array[int] = [1]
	if Net.is_networked():
		for id: int in Net.player_names:
			if not id in ids:
				ids.append(id)
		if not peer in ids:
			ids.append(peer)
	# Имена приходят в порядке подключения из roster хоста. Сортировка случайных
	# ENet id меняла место первого гостя при подключении второго.
	var index: int = clampi(ids.find(peer), 0, 2)
	var marker: Marker3D = get_node("Gameplay/SpawnPoints/PlayerSpawn_%02d" % (index + 1)) as Marker3D
	return marker.global_position


@rpc("authority", "call_remote", "reliable")
func _assign_spawn(slot: int) -> void:
	if _player and has_node("Gameplay/SpawnPoints"):
		var marker: Marker3D = get_node("Gameplay/SpawnPoints/PlayerSpawn_%02d" % (clampi(slot,0,2)+1)) as Marker3D
		_player.global_position = marker.global_position


## CSG и меши сцены: материал из meta — чтобы сцену можно было собирать и править руками.
func _apply_materials(n: Node) -> void:
	for c in n.get_children():
		if c is MeshInstance3D and c.has_meta("shelter_cut"):
			var mesh: Mesh = (c as MeshInstance3D).mesh
			for surface: int in range(mesh.get_surface_count()):
				var material: BaseMaterial3D = mesh.surface_get_material(surface) as BaseMaterial3D
				if material:
					SectorMaterials.register_cutaway(material)
		if c is GeometryInstance3D and (c.has_meta("mat") or c.has_meta("color") or c.has_meta("emit")):
			var cut := bool(c.get_meta("cut", true))
			var m: Material
			if c.has_meta("emit"):
				# светящееся: лампы, экран, вывески
				var em := StandardMaterial3D.new()
				var ec: Color = c.get_meta("emit")
				em.albedo_color = ec
				em.emission_enabled = true
				em.emission = ec
				em.emission_energy_multiplier = float(c.get_meta("emit_energy", 3.0))
				m = em
			elif c.has_meta("mat"):
				m = SectorMaterials.get_material(String(c.get_meta("mat")), cut)
			else:
				var col: Color = c.get_meta("color")
				m = SectorMaterials.flat(col, float(c.get_meta("rough", 0.8)), float(c.get_meta("metal", 0.0)))
			if c is CSGShape3D:
				(c as CSGShape3D).set("material", m)
			else:
				(c as GeometryInstance3D).material_override = m
		_apply_materials(c)


func open_station(st: HideoutStation) -> void:
	# в окне видно то, что в руках сейчас (патроны, фонари)
	_player.flush_weapon_state()
	_ui.open(st.kind)


# ---------------------------------------------------------------- оружие в руках (как в рейде)

## Сообщение внизу экрана (как у рейда).
func notify(text: String) -> void:
	_toast.text = text
	_toast_t = 2.5


func ui_open() -> bool:
	return _ui != null and _ui.is_open()


## Перезарядка: смена магазина из рюкзака или досыпка россыпью (Inventory.reload_slot); выпавший
## магазин, которому нет места в рюкзаке, — в тайник.
func request_reload(slot: String, state: Dictionary) -> void:
	var r := _player.inventory.reload_slot(slot, state)
	var out: Dictionary = r[1]
	if not out.is_empty():
		ItemDb.add_to(Profile.stash, out, Profile.stash_grid())
	_to_profile()


## Быстрая перезарядка: старый магазин — из рюкзака на пол, лежать моделью магазина (как в рейде).
## Подобрать — F; не подобранное при уходе из убежища возвращается в тайник.
func request_drop_entry(where: String, idx: int, _loose: bool = false) -> void:
	var entry: Dictionary = _player.inventory.take_entry(where, idx)
	if entry.is_empty():
		return
	_to_profile()
	var item := HideoutFloorItem.new()
	item.entry = entry
	item.lay_yaw = randf() * TAU
	add_child(item)
	item.global_position = LooseLoot.floor_near(_player)
	item.picked.connect(_pick_floor.bind(item))
	_floor_items.append(item)


func _pick_floor(item: HideoutFloorItem) -> void:
	if not item in _floor_items:
		return
	_floor_items.erase(item)
	if _player.inventory.add_entry(item.entry.duplicate(true)) <= 0:
		ItemDb.add_to(Profile.stash, item.entry.duplicate(true), Profile.stash_grid())
		notify("В рюкзаке нет места — убрано в тайник")
	_to_profile()
	Audio.play("pick_ammo", item.global_position, -8.0)
	item.queue_free()


## Уходим из убежища: что осталось лежать на полу — в тайник.
func _floor_to_stash() -> void:
	if _floor_items.is_empty():
		return
	for item: HideoutFloorItem in _floor_items:
		ItemDb.add_to(Profile.stash, item.entry.duplicate(true), Profile.stash_grid())
	_floor_items.clear()
	Profile.save()


## Патроны в магазине, износ, прицел, фонари — в профиль.
func request_weapon_state(slot: String, state: Dictionary) -> void:
	_player.inventory.apply_weapon_state(slot, state)
	_to_profile()


## Граната, ракета, химсвет — из рюкзака.
func request_consume(id: String, n: int) -> void:
	_player.inventory.remove(id, n)
	_to_profile()


func _profile_sig() -> String:
	return str(Profile.equipment) + str(Profile.backpack) + str(Profile.pocket)


## Профиль — в руки: снаряжение, рюкзак, карман.
func _from_profile() -> void:
	var inv := _player.inventory
	inv.equipment = Profile.equipment.duplicate(true)
	inv.items = Profile.backpack.duplicate(true)
	inv.pocket_grid = Profile.pocket_grid()
	inv.pocket = Profile.pocket.duplicate(true)
	inv.loadout_ready = true
	_inv_sig = _profile_sig()


## Из рук — в профиль (и сохранить).
func _to_profile() -> void:
	var inv := _player.inventory
	Profile.equipment = inv.equipment.duplicate(true)
	Profile.backpack = inv.items.duplicate(true)
	Profile.pocket = inv.pocket.duplicate(true)
	Profile.save()
	_inv_sig = _profile_sig()


func _process(delta: float) -> void:
	if Engine.is_editor_hint() or _player == null:
		return
	if _tipsy_fx:
		_tipsy = maxf(0.0, _tipsy - delta / TIPSY_SEC)
		_tipsy_fx.visible = _tipsy > 0.01
		(_tipsy_fx.material as ShaderMaterial).set_shader_parameter("k", minf(_tipsy / 3.0, 1.2))
	_money.text = "%s ₽" % InventoryUI.money(Profile.money)
	_toast_t -= delta
	_toast.visible = _toast_t > 0.0
	# в окне тайника поменяли снаряжение, рюкзак — в руки
	if _profile_sig() != _inv_sig:
		_from_profile()
	_prompt.visible = false
	if _tick_raid_start(delta):
		return
	if _ui.is_open():
		return
	# Tab — рюкзак и снаряжение (окно тайника) где угодно в убежище
	if Input.is_action_just_pressed("inventory") and not _player.ui_blocked() and not UiTheme.typing():
		_player.flush_weapon_state()
		_ui.open(HideoutStation.Kind.STASH)
		return
	if _player.ui_blocked():
		return
	var best: Interactable = null
	var best_d := INF
	var reach: Array[Interactable] = []
	for n in get_tree().get_nodes_in_group("interactables"):
		var it := n as Interactable
		var d := it.global_position.distance_to(_player.global_position)
		if d < Balance.INTERACT_RADIUS + 0.6:
			reach.append(it)
			if d < best_d:
				best = it
				best_d = d
	# напарник рядом (ближе любой станции) — подержать «действие»: обмен вещами
	var mate: Player = null
	var mate_d: float = Balance.TRADE.reach_m
	for id: Variant in _others:
		var other := _others[id] as Player
		if other == null or not is_instance_valid(other) or not Trade.can_trade(other.peer_id):
			continue
		var d2 := other.global_position.distance_to(_player.global_position)
		if d2 < mate_d:
			mate_d = d2
			mate = other
	if mate != null and mate_d < best_d:
		_prompt.visible = true
		_prompt.text = "%s (держать) — обмен вещами: %s" % [PauseMenu.key_name("interact"), String(Net.player_names.get(mate.peer_id, "напарник"))]
		_trade_hold = _trade_hold + get_process_delta_time() if Input.is_action_pressed("interact") else 0.0
		if _trade_hold >= float(Balance.TRADE.hold_sec):
			_trade_hold = 0.0
			Trade.request(mate.peer_id)
		return
	_trade_hold = 0.0
	if best == null:
		return
	# несколько рядом (кнопки пульта тира) — та, что под курсором, если курсор на одной из них
	var cam := get_viewport().get_camera_3d()
	if reach.size() > 1 and cam:
		# от первого лица мышь захвачена — «курсор» в центре экрана
		var mouse := get_viewport().get_mouse_position()
		if Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
			mouse = get_viewport().get_visible_rect().size * 0.5
		var aim_d: float = Balance.INTERACT_CURSOR_PICK_PX
		for it: Interactable in reach:
			if cam.is_position_behind(it.global_position):
				continue
			var px: float = cam.unproject_position(it.global_position).distance_to(mouse)
			if px < aim_d:
				aim_d = px
				best = it
	_prompt.visible = true
	_prompt.text = PauseMenu.key_name("interact") + " — " + best.prompt()
	if Input.is_action_just_pressed("interact"):
		best.request_use()


func _build_hud() -> void:
	var layer := CanvasLayer.new()
	layer.layer = 11
	add_child(layer)
	_prompt = Label.new()
	_prompt.anchor_left = 0.5
	_prompt.anchor_right = 0.5
	_prompt.anchor_top = 1.0
	_prompt.anchor_bottom = 1.0
	_prompt.offset_left = -400
	_prompt.offset_right = 400
	_prompt.offset_top = -110
	_prompt.offset_bottom = -80
	_prompt.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_prompt.add_theme_font_size_override("font_size", 22)
	_prompt.add_theme_color_override("font_color", Color(1.0, 0.92, 0.7))
	_prompt.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_prompt.add_theme_constant_override("outline_size", 6)
	layer.add_child(_prompt)
	_start_label = Label.new()
	_start_label.anchor_left = 0.5
	_start_label.anchor_right = 0.5
	_start_label.offset_left = -500
	_start_label.offset_right = 500
	_start_label.offset_top = 96
	_start_label.offset_bottom = 132
	_start_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_start_label.add_theme_font_size_override("font_size", 24)
	_start_label.add_theme_color_override("font_color", Color(0.75, 1.0, 0.75))
	_start_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_start_label.add_theme_constant_override("outline_size", 6)
	_start_label.visible = false
	layer.add_child(_start_label)
	_money = Label.new()
	_money.offset_left = 24
	_money.offset_top = 18
	_money.offset_right = 600
	_money.add_theme_font_size_override("font_size", 24)
	_money.add_theme_color_override("font_color", Color(0.8, 0.95, 0.7))
	_money.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	_money.add_theme_constant_override("outline_size", 6)
	layer.add_child(_money)
	_toast = Label.new()
	_toast.anchor_left = 0.5
	_toast.anchor_right = 0.5
	_toast.anchor_top = 1.0
	_toast.anchor_bottom = 1.0
	_toast.offset_left = -500
	_toast.offset_right = 500
	_toast.offset_top = -160
	_toast.offset_bottom = -126
	_toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_toast.add_theme_font_size_override("font_size", 20)
	_toast.add_theme_color_override("font_color", Color(1.0, 0.75, 0.55))
	_toast.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_toast.add_theme_constant_override("outline_size", 6)
	_toast.visible = false
	layer.add_child(_toast)
	var hint := Label.new()
	hint.text = "УБЕЖИЩЕ"
	hint.offset_left = 24
	hint.offset_top = 52
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(0.85, 0.8, 0.7, 0.7))
	layer.add_child(hint)
