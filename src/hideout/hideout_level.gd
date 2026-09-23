@tool
extends Node3D
## Убежище — отдельный уровень между рейдами (старт игры). Подвал под торговым центром:
## тайник со снаряжением, верстак, торговец, выход в рейд. Геометрия — CSG-узлы сцены (двигать
## и менять руками), материал — по meta "mat" (id из SectorMaterials, серые "gb_*" тоже можно)
## или "color" (плоский цвет); meta "cut" = false — не растворять у камеры (пол).
## Игрок ходит тем же персонажем, но не стреляет. Всё про деньги и вещи — Profile (оффлайн).

@onready var _camera_rig: CameraRig = $CameraRig
@onready var _spawn: Marker3D = $Spawn

var _player: Player
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
	Profile.from_hideout = false
	_player = (load("res://scenes/player/player.tscn") as PackedScene).instantiate() as Player
	_player.name = "Player_1"
	_player.combat_enabled = false
	add_child(_player)
	_player.global_position = _spawn.global_position
	_player.weapon_id = Profile.equipped_weapon()
	_camera_rig.set_target(_player)
	_camera_rig.rotation.y = _spawn.rotation.y
	_camera_rig.set_distance(Balance.HIDEOUT_CAMERA_DISTANCE)
	_ui = HideoutUI.new()
	add_child(_ui)
	_build_hud()


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


func _process(_delta: float) -> void:
	if Engine.is_editor_hint() or _player == null:
		return
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
