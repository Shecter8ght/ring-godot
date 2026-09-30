class_name CharacterAnimator
extends Node
## Один набор Persona для игрока и любого NPC; тело ведёт физика, клипы не двигают коллизию.

var _actor: CharacterBody3D
var _body: Node3D
var _model: Node3D
var _player: AnimationPlayer
var _last_position: Vector3
## Скорость движения, сглаженная по времени: тело двигает физика (60 раз в с), а _process идёт
## с частотой кадров — на мониторе 144+ сдвиг между кадрами то ноль, то двойной, и клип
## прыгал «стоит» ↔ «спринт» каждый кадр. Работает и для чужих тел (позиция приходит по сети).
var _vel: Vector3 = Vector3.ZERO
## Насколько модель опущена под стойку (сейчас, м) — к нужной высоте идёт плавно.
var _drop: float = 0.0
var _last_event_seq: int = 0
var _one_shot: String = ""
var _current: String = ""
var _held_prone: bool = false
## Оружие в правой руке: кость mixamorig_RightHand → узел Grip со смещением семейства рукояток
## (data/weapon_sockets.json, tools/bake_weapon_sockets.gd). Модель вешают Player / Marauder.
const SOCKETS := "res://data/weapon_sockets.json"
## На время этих клипов оружие прячется: рука занята (бросок, подобрать с пола).
const HIDE_WEAPON := ["grenade_throw", "pickup"]
static var _sockets: Dictionary = {}
var _grip: Node3D


func _ready() -> void:
	_actor = get_parent() as CharacterBody3D
	_body = _actor.get_node("Body") as Node3D
	_model = _body.get_node_or_null("Persona") as Node3D
	if _model == null:
		push_error("CharacterAnimator: Persona is missing")
		set_process(false)
		return
	var players: Array[Node] = _model.find_children("*", "AnimationPlayer", true, false)
	if players.is_empty():
		_player = AnimationPlayer.new()
		_player.name = "AnimationPlayer"
		_player.root_node = NodePath("..")
		_model.add_child(_player)
	else:
		_player = players[0] as AnimationPlayer
	var clips: AnimationLibrary = load("res://assets/models/characters/persona_clips.res") as AnimationLibrary
	if clips == null:
		push_error("CharacterAnimator: нет запечённых клипов Persona")
		set_process(false)
		return
	if StringName("") in _player.get_animation_library_list():
		_player.remove_animation_library("")
	_player.add_animation_library("", clips)
	_player.animation_finished.connect(_on_animation_finished)
	_last_position = _actor.global_position
	_play("unarmed_idle")


func _process(delta: float) -> void:
	if _player == null or delta <= 0.0:
		return
	var travel: Vector3 = _actor.global_position - _last_position
	_last_position = _actor.global_position
	travel.y = 0.0
	_vel = _vel.lerp(travel / delta, 1.0 - exp(-delta / float(Balance.CHARACTER_ANIM.speed_smooth_sec)))
	var speed: float = _vel.length()
	var family: String = "unarmed"
	var crouched: bool = false
	var prone: bool = false
	var aiming: bool = false
	var event_seq: int = 0
	var event_name: String = ""
	if _actor is Player:
		var person: Player = _actor as Player
		var weapon_class: String = String(WeaponDb.weapon(person.weapon_id).get("class", "")) if person.weapon_id != "" else ""
		family = "unarmed" if weapon_class == "" else ("pistol" if weapon_class == "PISTOL" else "rifle")
		crouched = person.stance == Player.Stance.CROUCH
		prone = person.stance == Player.Stance.PRONE or person.health.downed
		aiming = person.aiming
		event_seq = person.animation_event_seq
		event_name = person.animation_event
	elif _actor is Marauder:
		var enemy: Marauder = _actor as Marauder
		family = "pistol" if String(enemy._spec.get("class", "")) == "PISTOL" else "rifle"
		crouched = enemy.crouched
		prone = enemy._health.downed
		aiming = enemy.state == Marauder.State.COMBAT
		event_seq = enemy.animation_event_seq
		event_name = enemy.animation_event
	if _grip:
		_grip.visible = not HIDE_WEAPON.has(_one_shot)
	if event_seq != _last_event_seq:
		_last_event_seq = event_seq
		if _player.has_animation(event_name):
			_one_shot = event_name
			_play(event_name, false)
	# Физическая стойка уже уменьшает Body; компенсируем её для запечённой позы приседа.
	if _actor is Player:
		_model.scale.y = 1.0 / maxf(_body.scale.y, 0.1)
	elif _actor is Marauder:
		var enemy_scale: float = (_actor as Marauder)._base_scale.y
		_model.scale.y = enemy_scale / maxf(_body.scale.y, 0.1)
	var move_min: float = float(Balance.CHARACTER_ANIM.move_min)
	var moving: bool = speed > move_min
	# ходьба вприсядку ниже не опускается: у клипа таз выше, чем в приседе на месте (ноги уходили в пол)
	var crouch_drop: float = float(Balance.CHARACTER_ANIM.crouch_walk_drop if moving else Balance.CHARACTER_ANIM.crouch_drop)
	var stance_drop: float = float(Balance.CHARACTER_ANIM.prone_drop) if prone else (crouch_drop if crouched else 0.0)
	_drop = lerpf(_drop, stance_drop, 1.0 - exp(-delta / float(Balance.CHARACTER_ANIM.blend_sec)))
	_model.position.y = -_drop / maxf(_body.scale.y, 0.1)
	if _one_shot != "":
		return
	var clip: String
	if prone:
		clip = "prone_move_b"
	elif crouched:
		clip = family + "_crouch_walk_" + _direction(_vel) if moving else "unarmed_crouch_idle"
		# своей ходьбы вприсядку у пистолета и без оружия нет — ноги от автоматной (стоячая
		# ходьба, опущенная на присед, уходила ногами в пол)
		if moving and not _player.has_animation(clip):
			clip = "rifle_crouch_walk_" + _direction(_vel)
	elif not moving:
		clip = "rifle_aim" if family == "rifle" and aiming else family + "_idle"
	else:
		var gait: String = "run" if speed >= float(Balance.CHARACTER_ANIM.run_from) else "walk"
		clip = family + "_" + gait + "_" + _direction(_vel)
		if family == "rifle" and gait == "run" and speed >= float(Balance.CHARACTER_ANIM.sprint_from):
			clip = "rifle_sprint"
	if not _player.has_animation(clip):
		clip = family + ("_crouch_idle" if crouched and not moving else "_walk_f" if moving else "_idle")
	if not _player.has_animation(clip):
		clip = "unarmed_idle"
	_play(clip)
	if prone and not moving:
		if not _held_prone:
			_player.speed_scale = 1.0
			_player.play(clip, 0.0)
			_player.seek(float(Balance.CHARACTER_ANIM.prone_hold_sec), true)
			_player.advance(0.001)
		_held_prone = true
	else:
		_held_prone = false
	_player.speed_scale = 0.0 if prone and not moving else 1.0


## Узел в правой руке для модели оружия (семейство рукояток: pistol / rifle / shotgun / bolt —
## поле model оружия). Заводится при первом вызове; null — модели Persona нет.
func weapon_grip(family: String) -> Node3D:
	if _grip == null:
		if _model == null:
			return null
		var skeletons: Array[Node] = _model.find_children("*", "Skeleton3D", true, false)
		if skeletons.is_empty():
			return null
		var socket := BoneAttachment3D.new()
		socket.name = "WeaponSocket"
		socket.bone_name = "mixamorig_RightHand"
		(skeletons[0] as Skeleton3D).add_child(socket)
		_grip = Node3D.new()
		_grip.name = "Grip"
		socket.add_child(_grip)
	_grip.transform = socket_transform(family)
	return _grip


## Как оружие семейства лежит в ладони (в осях кости правой руки).
static func socket_transform(family: String) -> Transform3D:
	if _sockets.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SOCKETS))
		if parsed is Dictionary:
			_sockets = parsed
	var s: Dictionary = _sockets.get(family, _sockets.get("rifle", {}))
	if s.is_empty():
		return Transform3D.IDENTITY
	var b: Array = s.basis
	return Transform3D(Basis(_vec(b[0]), _vec(b[1]), _vec(b[2])), _vec(s.origin))


static func _vec(a: Variant) -> Vector3:
	var v: Array = a
	return Vector3(float(v[0]), float(v[1]), float(v[2]))


func _direction(travel: Vector3) -> String:
	var local: Vector3 = Basis(Vector3.UP, -_body.rotation.y) * travel
	if absf(local.x) > absf(local.z):
		return "l" if local.x > 0.0 else "r"
	return "f" if local.z >= 0.0 else "b"


func _play(clip: String, loop: bool = true) -> void:
	if clip == _current:
		return
	var animation: Animation = _player.get_animation(clip)
	animation.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
	_player.speed_scale = 1.0
	_player.play(clip, float(Balance.CHARACTER_ANIM.blend_sec))
	_current = clip


func _on_animation_finished(name: StringName) -> void:
	if String(name) == _one_shot:
		_one_shot = ""
		_current = ""
