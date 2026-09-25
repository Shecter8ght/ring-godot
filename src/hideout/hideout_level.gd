@tool
extends Node3D
## Убежище — отдельный уровень между рейдами (старт игры). Подвал под торговым центром:
## тайник со снаряжением, верстак, торговец, выход в рейд. Геометрия — CSG-узлы сцены (двигать
## и менять руками), материал — по meta "mat" (id из SectorMaterials, серые "gb_*" тоже можно)
## или "color" (плоский цвет); meta "cut" = false — не растворять у камеры (пол).
## Игрок ходит тем же персонажем, но не стреляет. Всё про деньги и вещи — Profile (у каждого свой).
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
## Выпито (досуг): качает в глазах, проходит само.
var _tipsy: float = 0.0
var _tipsy_fx: ColorRect
var _ui: HideoutUI
var _prompt: Label
var _money: Label


func _ready() -> void:
	_apply_materials(self)
	if Engine.is_editor_hint():
		return
	add_to_group("hideout_level")
	Profile.ensure()
	Profile.pending_raid = false
	# в рейд — отсюда: со снаряжением профиля (и когда рейд начнёт хост)
	Profile.from_hideout = true
	get_tree().node_added.connect(_on_node_added)
	var me := multiplayer.get_unique_id() if Net.is_networked() else 1
	_player = PLAYER_SCENE.instantiate() as Player
	_player.name = "Player_%d" % me
	_player.peer_id = me
	_player.combat_enabled = false
	if Net.is_networked():
		_player.set_multiplayer_authority(me)
	add_child(_player)
	_player.global_position = _spawn.global_position
	# в руках — основное из снаряжения (как выглядит, с обвесом)
	var we := Profile.equipped_entry()
	_player.weapon_id = String(we.get("id", ""))
	_player.weapon_mods = we.get("mods", {})
	_camera_rig.set_target(_player)
	_camera_rig.rotation.y = _spawn.rotation.y
	_camera_rig.set_distance(Balance.HIDEOUT_CAMERA_DISTANCE)
	_ui = HideoutUI.new()
	add_child(_ui)
	_build_hud()
	# сюжет в убежище: кто вернулся, что изменилось (по флагам)
	var qw := QuestWorld.new()
	qw.name = "QuestWorld"
	add_child(qw)
	# досуг: телевизор, магнитола, пиво, диван (своя сцена — правится в редакторе отдельно)
	if ResourceLoader.exists(LOUNGE_SCENE):
		add_child((load(LOUNGE_SCENE) as PackedScene).instantiate())
	_build_tipsy()
	Net.scenes_changed.connect(_sync_others)
	Net.enter_scene("hideout")


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


func _exit_tree() -> void:
	if Engine.is_editor_hint():
		return
	if get_tree().node_added.is_connected(_on_node_added):
		get_tree().node_added.disconnect(_on_node_added)


## Синхронизаторы убежища — только тем, кто тоже в убежище.
func _on_node_added(n: Node) -> void:
	if n is MultiplayerSynchronizer and is_ancestor_of(n):
		Net.filter_sync(n as MultiplayerSynchronizer, "hideout")


## Кто из своих в убежище — тот и стоит здесь; ушёл (в рейд, в меню, отключился) — пропал.
func _sync_others() -> void:
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
	for id in want:
		if _others.has(id):
			continue
		var p := PLAYER_SCENE.instantiate() as Player
		p.name = "Player_%d" % id
		p.peer_id = id
		p.combat_enabled = false
		p.set_multiplayer_authority(id)
		add_child(p)
		p.global_position = _spawn.global_position + Vector3(cos(id * 1.7), 0.0, sin(id * 1.7)) * 1.4
		# над головой — ник
		var tag := Label3D.new()
		tag.text = String(Net.player_names.get(id, "Игрок %d" % id))
		tag.position = Vector3(0, 2.15, 0)
		tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		tag.font_size = 40
		tag.pixel_size = 0.004
		tag.modulate = Color(1.0, 0.9, 0.7)
		tag.outline_size = 8
		tag.no_depth_test = true
		p.add_child(tag)
		_others[id] = p


## CSG и меши сцены: материал из meta — чтобы сцену можно было собирать и править руками.
func _apply_materials(n: Node) -> void:
	for c in n.get_children():
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
	_ui.open(st.kind)


func _process(delta: float) -> void:
	if Engine.is_editor_hint() or _player == null:
		return
	if _tipsy_fx:
		_tipsy = maxf(0.0, _tipsy - delta / TIPSY_SEC)
		_tipsy_fx.visible = _tipsy > 0.01
		(_tipsy_fx.material as ShaderMaterial).set_shader_parameter("k", minf(_tipsy / 3.0, 1.2))
	_money.text = "%s ₽" % InventoryUI.money(Profile.money)
	_prompt.visible = false
	if _ui.is_open():
		return
	var best: Interactable = null
	var best_d := INF
	for n in get_tree().get_nodes_in_group("interactables"):
		var it := n as Interactable
		var d := it.global_position.distance_to(_player.global_position)
		if d < Balance.INTERACT_RADIUS + 0.6 and d < best_d:
			best = it
			best_d = d
	if best == null:
		return
	_prompt.visible = true
	_prompt.text = "F — " + best.prompt()
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
	_money = Label.new()
	_money.offset_left = 24
	_money.offset_top = 18
	_money.offset_right = 600
	_money.add_theme_font_size_override("font_size", 24)
	_money.add_theme_color_override("font_color", Color(0.8, 0.95, 0.7))
	_money.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.8))
	_money.add_theme_constant_override("outline_size", 6)
	layer.add_child(_money)
	var hint := Label.new()
	hint.text = "УБЕЖИЩЕ"
	hint.offset_left = 24
	hint.offset_top = 52
	hint.add_theme_font_size_override("font_size", 14)
	hint.add_theme_color_override("font_color", Color(0.85, 0.8, 0.7, 0.7))
	layer.add_child(hint)
