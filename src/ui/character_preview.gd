class_name CharacterPreview
extends SubViewportContainer
## Фигура персонажа в окне снаряжения: настоящая модель игрока (Persona) в своём маленьком мире
## (SubViewport) — стоит, дышит (клип покоя), студийный свет, прозрачный фон. Так сделано в играх жанра
## (Tarkov, Arena Breakout): в середине — человек, а не схема, слоты — по бокам от него. Нет файла
## модели — окно остаётся пустым (слоты работают и без фигуры).

const MODEL := "res://assets/models/characters/persona_animated.glb"
const CLIPS := "res://assets/models/characters/persona_clips.res"

var _vp: SubViewport
var _model: Node3D
var _cam: Camera3D


func _ready() -> void:
	stretch = true
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	_vp = SubViewport.new()
	_vp.own_world_3d = true
	_vp.transparent_bg = true
	_vp.msaa_3d = Viewport.MSAA_4X
	_vp.render_target_update_mode = SubViewport.UPDATE_WHEN_VISIBLE
	add_child(_vp)
	var env := Environment.new()
	env.background_mode = Environment.BG_CLEAR_COLOR
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color(0.5, 0.52, 0.56)
	env.ambient_light_energy = 0.7
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	var we := WorldEnvironment.new()
	we.environment = env
	_vp.add_child(we)
	# ключевой тёплый спереди-сверху, холодный контровой сзади — фигура читается на тёмном окне
	var key := DirectionalLight3D.new()
	key.light_color = Color(1.0, 0.92, 0.8)
	key.light_energy = 1.9
	key.rotation_degrees = Vector3(-32, -28, 0)
	_vp.add_child(key)
	var rim := DirectionalLight3D.new()
	rim.light_color = Color(0.6, 0.75, 1.0)
	rim.light_energy = 1.4
	rim.rotation_degrees = Vector3(-12, 152, 0)
	_vp.add_child(rim)
	_cam = Camera3D.new()
	_cam.fov = 24.0
	_cam.near = 0.05
	_vp.add_child(_cam)
	# рост 1.8 м: камера на уровне груди, чуть сбоку — фигура целиком с запасом
	_cam.position = Vector3(0.55, 1.0, 4.9)
	_cam.look_at_from_position(_cam.position, Vector3(0.0, 0.93, 0.0))
	if not ResourceLoader.exists(MODEL):
		return
	var scene := load(MODEL) as PackedScene
	if scene == null:
		return
	_model = scene.instantiate() as Node3D
	_vp.add_child(_model)
	for n: Node in _model.find_children("*", "GeometryInstance3D", true, false):
		(n as GeometryInstance3D).cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# клип покоя из общей библиотеки клипов Persona
	var clips := load(CLIPS) as AnimationLibrary if ResourceLoader.exists(CLIPS) else null
	if clips == null or not clips.has_animation("unarmed_idle"):
		return
	var players: Array[Node] = _model.find_children("*", "AnimationPlayer", true, false)
	var player: AnimationPlayer = players[0] as AnimationPlayer if not players.is_empty() else null
	if player == null:
		player = AnimationPlayer.new()
		player.root_node = NodePath("..")
		_model.add_child(player)
	if StringName("") in player.get_animation_library_list():
		player.remove_animation_library("")
	player.add_animation_library("", clips)
	player.get_animation("unarmed_idle").loop_mode = Animation.LOOP_LINEAR
	player.play("unarmed_idle")
