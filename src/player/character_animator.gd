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
var _last_event_seq: int = 0
## Предупредить об устаревших клипах один раз, а не у каждого персонажа.
static var _warned_old_clips: bool = false
var _one_shot: String = ""
var _current: String = ""
var _held_prone: bool = false
## Оружие в правой руке: кость mixamorig_RightHand → узел Grip со смещением семейства рукояток
## (data/weapon_sockets.json, tools/bake_weapon_sockets.gd). Модель вешают Player / Marauder.
const SOCKETS := "res://data/weapon_sockets.json"
## На время этих клипов оружие прячется: рука занята (бросок, подобрать с пола).
const HIDE_WEAPON := ["grenade_throw", "pickup"]
## В этих клипах левая рука уходит с цевья (магазин, граната, достать / убрать) — ИК отпускает её.
const FREE_LEFT_HAND := ["pistol_reload", "rifle_reload", "prone_reload", "reload_move", "grenade_throw", "prone_throw", "pickup", "rifle_draw", "pistol_draw", "rifle_holster"]
static var _sockets: Dictionary = {}
var _grip: Node3D
## Левая кисть на цевье (SupportHandIK — модификатор скелета после клипа).
var _support: SupportHandIK
var _collision_ik: WeaponCollisionIK
## Клип падения раненым, пока лежит («» — не ранен); после смерти аниматор не управляет моделью.
var _downed_clip: String = ""
var _dead: bool = false


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
	# старая библиотека: таз на высоте стоя во всех клипах — присевший и мёртвый висят над полом
	if not clips.has_animation("death_prone") and not _warned_old_clips:
		_warned_old_clips = true
		push_warning("CharacterAnimator: клипы Persona устарели — tools/godot.cmd --headless -s res://tools/bake_character_clips.gd")
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
	var downed: bool = false
	var aiming: bool = false
	var hurt: bool = false
	var event_seq: int = 0
	var event_name: String = ""
	if _actor is Player:
		var person: Player = _actor as Player
		var weapon_class: String = String(WeaponDb.weapon(person.weapon_id).get("class", "")) if person.weapon_id != "" else ""
		family = "unarmed" if weapon_class == "" else ("pistol" if weapon_class == "PISTOL" else "rifle")
		crouched = person.stance == Player.Stance.CROUCH
		prone = person.stance == Player.Stance.PRONE
		downed = person.health.downed
		aiming = person.aiming
		hurt = person.health.hp < person.health.max_hp * float(Balance.CHARACTER_ANIM.hurt_below)
		event_seq = person.animation_event_seq
		event_name = person.animation_event
	elif _actor is Marauder:
		var enemy: Marauder = _actor as Marauder
		family = "pistol" if String(enemy._spec.get("class", "")) == "PISTOL" else "rifle"
		crouched = enemy.crouched
		downed = enemy._health.downed
		aiming = enemy.state == Marauder.State.COMBAT
		event_seq = enemy.animation_event_seq
		event_name = enemy.animation_event
	if _grip:
		_grip.visible = not HIDE_WEAPON.has(_one_shot)
	if _collision_ik:
		_collision_ik.enabled_for_pose = not downed and not _dead and family != "unarmed"
	if _support:
		# с пистолетом — вторая рука на рукоятке только в прицеле (на ходу клипы держат одной)
		var hold := _grip != null and _grip.visible and family != "unarmed" and not downed \
			and not FREE_LEFT_HAND.has(_one_shot) and (family != "pistol" or aiming)
		var weapon_rig: WeaponRig = WeaponRig.find_on(_grip.get_child(0) as Node3D) if _grip and _grip.get_child_count() > 0 else null
		var action_weight: float = weapon_rig.get_hand_weight() if weapon_rig and not downed else 0.0
		_support.action_target = weapon_rig.get_hand_target() if action_weight > 0.0 else null
		_support.action_weight = action_weight
		hold = hold or action_weight > 0.0
		_support.influence = move_toward(_support.influence, 1.0 if hold else 0.0, delta / float(Balance.CHARACTER_ANIM.support_blend_sec))
	var move_min: float = float(Balance.CHARACTER_ANIM.move_min)
	var moving: bool = speed > move_min
	if event_seq != _last_event_seq:
		_last_event_seq = event_seq
		# одиночный клип — по стойке (стоячий клип в приседе / лёжа поднимал тело: ноги в полу,
		# у раненого — «вверх ногами»); раненому и лежащему реакция на попадание не играется
		var ev := "" if downed else _event_clip(event_name, family, crouched, prone, moving)
		if ev != "" and _player.has_animation(ev):
			_one_shot = ev
			_play(ev, false)
	# Физическая стойка уже уменьшает Body; компенсируем её для запечённой позы приседа.
	if _actor is Player:
		_model.scale.y = 1.0 / maxf(_body.scale.y, 0.1)
	elif _actor is Marauder:
		var enemy_scale: float = (_actor as Marauder)._base_scale.y
		_model.scale.y = enemy_scale / maxf(_body.scale.y, 0.1)
	# высоту таза (присел, лёг, упал) задаёт сам клип — модель вниз не сдвигаем
	# тяжело ранен: падает (бегом — с разбега) и лежит в последнем кадре; тащат — поза та же
	if downed:
		if _downed_clip == "":
			_one_shot = ""
			_downed_clip = "downed_fall" if speed >= float(Balance.CHARACTER_ANIM.run_from) * 0.6 else "downed_fall_still"
			_player.speed_scale = 1.0
			_play(_downed_clip, false)
		return
	if _downed_clip != "":
		# подняли — обратно к обычным клипам
		_downed_clip = ""
		_current = ""
	if _one_shot != "":
		return
	var clip: String
	var crawl: float = 1.0
	if _actor is Player and (_actor as Player).airborne and not prone and _player.has_animation("jump_loop"):
		clip = "jump_loop"
	elif prone:
		# лёжа с оружием — поза «лёжа с автоматом»; ползком — клип «назад», вперёд — он же обратным ходом
		clip = "prone_aim" if family != "unarmed" and not moving else "prone_move_b"
		if moving and _direction(_vel) == "f":
			crawl = -1.0
	elif crouched:
		if moving:
			clip = family + "_crouch_walk_" + _direction(_vel)
			# своей ходьбы вприсядку у пистолета и без оружия нет — ноги от автоматной (стоячая
			# ходьба, опущенная на присед, уходила ногами в пол)
			if not _player.has_animation(clip):
				clip = "rifle_crouch_walk_" + _direction(_vel)
		else:
			clip = "rifle_crouch_aim" if family == "rifle" and aiming else family + "_crouch_idle"
	elif not moving:
		clip = "rifle_aim" if family == "rifle" and aiming else family + "_idle"
	else:
		var gait: String = "run" if speed >= float(Balance.CHARACTER_ANIM.run_from) else "walk"
		clip = family + "_" + gait + "_" + _direction(_vel)
		if family == "rifle" and gait == "run" and speed >= float(Balance.CHARACTER_ANIM.sprint_from):
			clip = "rifle_sprint"
		# мало здоровья — прихрамывает (без автомата: у клипа руки свободны)
		elif hurt and gait == "walk" and family != "rifle" and _direction(_vel) == "f":
			clip = "injured_walk"
	if not _player.has_animation(clip):
		clip = family + ("_crouch_idle" if crouched and not moving else "_walk_f" if moving else "_idle")
	if not _player.has_animation(clip):
		clip = "unarmed_idle"
	_play(clip)
	if prone and not moving:
		if not _held_prone:
			_player.speed_scale = 1.0
			_player.play(clip, 0.0)
			_player.seek(float(Balance.CHARACTER_ANIM.prone_aim_hold_sec if clip == "prone_aim" else Balance.CHARACTER_ANIM.prone_hold_sec), true)
			_player.advance(0.001)
		_held_prone = true
	else:
		_held_prone = false
	_player.speed_scale = 0.0 if prone and not moving else crawl


## Одиночный клип события с учётом стойки и оружия; "" — в этой стойке не играть.
func _event_clip(ev: String, family: String, crouched: bool, prone: bool, moving: bool) -> String:
	match ev:
		"pistol_reload":
			# Штатного Mixamo-клипа пистолета нет: позу сохраняем, левую кисть ведёт риг ПМ.
			# Чужим игрокам приходит само событие, а детали и цель ИК — отдельным событием рига.
			if _player and _player.has_animation("pistol_reload"):
				return "pistol_reload"
			return ""
		"rifle_fire":
			# у пистолета поза и так «в прицеле»; автоматная отдача дёргала бы его руки
			if family == "pistol":
				return ""
			if prone:
				return "prone_fire"
			if crouched:
				return "crouch_fire"
		"rifle_reload":
			if prone:
				return "prone_reload"
			if moving and not crouched:
				return "reload_move"
			if crouched:
				return ""
		"pistol_draw", "rifle_draw":
			if crouched or prone:
				return ""
			return "pistol_draw" if family == "pistol" else ("rifle_draw" if family == "rifle" else "")
		"grenade_throw":
			if prone:
				return "prone_throw"
			if crouched:
				return ""
		"hit", "pickup":
			if crouched or prone:
				return ""
	return ev


## Смерть: клип по обстоятельствам — выстрел в голову, со стороны, в приседе, лёжа, взрыв
## (Player / Marauder выбирают death_clip и зовут один раз). Модель остаётся лежать в последнем
## кадре — это тот же персонаж, без манекена.
func die(clip: String) -> void:
	if _player == null:
		return
	_dead = true
	_one_shot = ""
	_downed_clip = ""
	if not _player.has_animation(clip):
		clip = "death_front" if _player.has_animation("death_front") else "death"
	_player.speed_scale = 1.0
	_current = ""
	_play(clip, false)
	if _grip:
		_grip.visible = true
	# мёртвая рука цевьё не держит
	if _support:
		_support.influence = 0.0
	set_process(false)


## Клип смерти: from — откуда стреляли (мир), zone — куда попали (Health.last_zone),
## стойка — где застало. Взрыв рядом — отлёт назад; в голову — свои клипы спереди / сзади.
func death_clip(from: Vector3, zone: String, crouched: bool, prone: bool) -> String:
	if prone or (_downed_clip != ""):
		return "death_prone"
	if zone.begins_with("blast"):
		return "death_blast"
	var local := Basis(Vector3.UP, -_body.rotation.y) * (from - _actor.global_position)
	local.y = 0.0
	var front := local.length() < 0.01 or local.z >= absf(local.x)
	if crouched:
		return "death_crouch_head" if zone == "head" else "death_crouch"
	if zone == "head":
		return "death_head_front" if front or local.z > -absf(local.x) else "death_head_back"
	if front:
		return "death_front"
	if local.z < -absf(local.x):
		return "death_back"
	return "death_right"


## Есть ли модель Persona с клипами (иначе смерть — прежним манекеном-регдоллом).
func has_model() -> bool:
	return _model != null and _player != null


## Узел на кости модели (камера погибшего игрока следит за грудью).
func bone_node(bone: String) -> Node3D:
	if _model == null:
		return null
	var skeletons: Array[Node] = _model.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty():
		return null
	var sk := skeletons[0] as Skeleton3D
	var existing := sk.get_node_or_null("Bone_" + bone) as Node3D
	if existing:
		return existing
	var att := BoneAttachment3D.new()
	att.name = "Bone_" + bone
	att.bone_name = bone
	sk.add_child(att)
	return att


func weapon_grip(family: String, weapon_id: String = "") -> Node3D:
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
		_collision_ik = WeaponCollisionIK.new()
		_collision_ik.name = "WeaponCollisionIK"
		_collision_ik.grip = _grip
		_collision_ik.actor = _actor
		(skeletons[0] as Skeleton3D).add_child(_collision_ik)
		_support = SupportHandIK.new()
		_support.name = "SupportHandIK"
		_support.grip = _grip
		_support.influence = 0.0
		(skeletons[0] as Skeleton3D).add_child(_support)
	_grip.transform = socket_transform(family)
	# У собственного ассета запястье может отличаться от семейства; кость остаётся той же.
	_grip.position += _grip.basis * WeaponGrips.socket_offset(family, WeaponDb.weapon(weapon_id))
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
