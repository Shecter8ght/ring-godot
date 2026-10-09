class_name ViewmodelClips
extends Node3D
## Руки и оружие от первого лица с заготовленными клипами из Blender (tools/export_veras54.py):
## стойка, тактическая и полная перезарядка, проверка магазина. Сцена уже в осях камеры (камера в
## начале, взгляд по −Z), поэтому у бедра узел почти не сдвигается — поза та, что в Blender.
##
## Клипом управляет состояние игрока (опрос каждый кадр, без новых событий в Player): началась
## перезарядка — клип по пустому/непустому магазину, растянутый на её время (стресс удлиняет);
## прервали — плавно в стойку; проверка патронов — клип проверки; выстрел — отвод затвора.
## Патроны в магазине — узлы Round_NN (1 — верхний), подаватель — по счёту (служебный клип
## follower_by_rounds). Обвесы и метки — у узла WeaponFrame (оси игры у пистолетной рукоятки).

const BLEND_IN := 0.15
const BLEND_OUT := 0.25
## Ход затвора при выстреле, с: туда-обратно.
const BOLT_KICK_SEC := 0.07

var weapon_id: String = ""
## Оси игры у пистолетной рукоятки: сюда встают обвесы, тут meta основы (muzzle, sight_h, ocular…).
var frame: Node3D
var config: Dictionary = {}
var _anim: AnimationPlayer
var _weapon_skel: Skeleton3D
var _follower: int = -1
var _bolt: int = -1
var _follower_src: Animation
var _bolt_src: Animation
var _rounds: Array[Node3D] = []
var _clip: String = ""
var _rounds_before: int = 0
var _rounds_after: int = 0
var _swap_frame: int = -1
var _last_reload: float = 0.0
var _last_check: float = 0.0
var _last_ammo: int = -1
var _kick: float = 0.0
var _sight_cache: Array = []


static func available(id: String) -> bool:
	var vm: Dictionary = WeaponDb.weapon(id).get("viewmodel", {}) if id != "" else {}
	return not vm.is_empty() and ResourceLoader.exists(String(vm.get("scene", "")), "PackedScene")


static func create(id: String, mods: Dictionary) -> ViewmodelClips:
	var vm := ViewmodelClips.new()
	vm.name = "Viewmodel_" + id
	vm._setup(id, mods)
	return vm


func _setup(id: String, mods: Dictionary) -> void:
	weapon_id = id
	config = WeaponDb.weapon(id).get("viewmodel", {})
	var model: Node3D = (load(String(config.scene)) as PackedScene).instantiate() as Node3D
	model.name = "Model"
	add_child(model)
	_anim = model.find_children("*", "AnimationPlayer", true, false)[0] as AnimationPlayer
	# клип ведём сами (advance), чтобы подаватель и затвор ставить поверх клипа в том же кадре
	_anim.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	for s: Node in model.find_children("*", "Skeleton3D", true, false):
		var sk := s as Skeleton3D
		if sk.find_bone("MagazineFollower") >= 0:
			_weapon_skel = sk
	if _weapon_skel:
		_follower = _weapon_skel.find_bone("MagazineFollower")
		_bolt = _weapon_skel.find_bone("Bolt")
	_follower_src = _anim.get_animation("follower_by_rounds") if _anim.has_animation("follower_by_rounds") else null
	_bolt_src = _anim.get_animation("bolt_travel") if _anim.has_animation("bolt_travel") else null
	for i in range(1, 31):
		var r: Node3D = model.find_child("Round_%02d" % i, true, false) as Node3D
		if r == null:
			break
		_rounds.append(r)
	frame = model.find_child("WeaponFrame", true, false) as Node3D
	if frame == null:
		frame = Node3D.new()
		model.add_child(frame)
	WeaponModels.apply_markers(frame, model, float(config.get("ads_z", 0.3)))
	WeaponMods.fit(frame, String(WeaponDb.weapon(id).get("model", "rifle")), mods)
	# meta основы — и на корне: CameraRig проверяет прицел (ocular, reticle_illum) у модели в руках
	for k: StringName in frame.get_meta_list():
		set_meta(k, frame.get_meta(k))
	for mi: Node in find_children("*", "GeometryInstance3D", true, false):
		var gi := mi as GeometryInstance3D
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# руки и оружие не уходят за дальнюю плоскость при близкой камере
		gi.extra_cull_margin = 0.5
	_play(String((config.get("clips", {}) as Dictionary).get("idle", "idle")), 0.0)


func _clip_name(kind: String) -> String:
	return String((config.get("clips", {}) as Dictionary).get(kind, ""))


func _play(clip: String, blend: float, duration: float = 0.0) -> void:
	if clip == "" or not _anim.has_animation(clip):
		return
	_anim.play(clip, blend)
	var length: float = _anim.get_animation(clip).length
	_anim.speed_scale = length / duration if duration > 0.0 else 1.0
	_clip = "" if clip == _clip_name("idle") else clip


## Опрос состояния игрока: перезарядка (начало по фронту таймера, отмена — в стойку), проверка
## магазина, выстрелы (затвор), счёт патронов на виду. Затем шаг клипа и затвор/подаватель поверх.
func update(pl: Player, delta: float) -> void:
	var mag: int = int(pl.spec().get("mag", 30))
	var reloading: bool = pl.reload_timer > 0.0 and pl._reload_kind != "clear"
	if reloading and _last_reload <= 0.0:
		var empty: bool = pl._reload_empty
		var clip := _clip_name("reload_empty" if empty else "reload")
		_rounds_before = 0 if empty else clampi(pl.ammo, 0, _rounds.size())
		_rounds_after = clampi(mag, 0, _rounds.size())
		_swap_frame = int((config.get("swap_frame", {}) as Dictionary).get(clip, -1))
		_play(clip, BLEND_IN, pl.reload_timer)
	elif not reloading and _last_reload > 0.0 and _clip != "" and _clip != _clip_name("check"):
		# закончилась или прервана — в стойку (досылка уже показана клипом)
		_play(_clip_name("idle"), BLEND_OUT)
	_last_reload = pl.reload_timer if reloading else 0.0
	if pl.ammo_check_t > _last_check + 0.5 and _clip == "":
		_rounds_before = clampi(pl.ammo, 0, _rounds.size())
		_rounds_after = _rounds_before
		_swap_frame = -1
		_play(_clip_name("check"), BLEND_IN)
	_last_check = pl.ammo_check_t
	if _last_ammo >= 0 and pl.ammo < _last_ammo:
		_kick = BOLT_KICK_SEC
		if _clip == _clip_name("check"):
			# выстрел посреди проверки — руки сразу на оружие
			_play(_clip_name("idle"), 0.1)
	_last_ammo = pl.ammo
	_anim.advance(delta)
	if _clip != "" and not _anim.is_playing():
		_play(_clip_name("idle"), BLEND_OUT)
	var shown: int = clampi(pl.ammo, 0, _rounds.size())
	if _clip != "":
		var f: float = _anim.current_animation_position * float(config.get("fps", 30))
		shown = _rounds_after if _swap_frame >= 0 and f >= _swap_frame else _rounds_before
	for i in range(_rounds.size()):
		_rounds[i].visible = i < shown
	_pose_overrides(shown, delta)


func _pose_overrides(shown: int, delta: float) -> void:
	if _weapon_skel == null:
		return
	if _follower >= 0 and _follower_src:
		_apply_sample(_follower_src, "MagazineFollower", _follower, float(shown) / 30.0)
	if _kick > 0.0 and _bolt >= 0 and _bolt_src:
		_kick = maxf(0.0, _kick - delta)
		var k: float = sin(PI * (1.0 - _kick / BOLT_KICK_SEC))
		_apply_sample(_bolt_src, "Bolt", _bolt, k / 30.0)


## Поза одной кости из служебного клипа в момент t (с): клип — таблица «счёт → поза».
func _apply_sample(src: Animation, bone_name: String, bone: int, t: float) -> void:
	for i in range(src.get_track_count()):
		var path: String = String(src.track_get_path(i))
		if not path.ends_with(":" + bone_name):
			continue
		match src.track_get_type(i):
			Animation.TYPE_POSITION_3D:
				_weapon_skel.set_bone_pose_position(bone, src.position_track_interpolate(i, t))
			Animation.TYPE_ROTATION_3D:
				_weapon_skel.set_bone_pose_rotation(bone, src.rotation_track_interpolate(i, t))


func is_busy() -> bool:
	return _clip != ""


## Положение у бедра в осях ViewmodelSpace: поза Blender + небольшая подгонка из данных.
func hip_transform() -> Transform3D:
	var o: Array = config.get("hip_offset", [0, 0, 0])
	return Transform3D(Basis.IDENTITY, Vector3(float(o[0]), float(o[1]), float(o[2])))


## В прицеле: линия прицеливания (у рамы: высота sight_h, вдоль её +Z) — на оси взгляда, рукоятка —
## на ads_z перед глазом. Считается по стойке (кэш), чтобы клип не тянул прицел за собой.
func ads_transform() -> Transform3D:
	if _sight_cache.is_empty():
		if not is_inside_tree():
			return hip_transform()
		# рама в осях этого узла по глобальным трансформам: узел кости обновляет скелет, а не родитель
		var f: Transform3D = global_transform.affine_inverse() * frame.global_transform
		_sight_cache = [f]
	var fr: Transform3D = _sight_cache[0]
	var sh: float = float(frame.get_meta("sight_h", 0.12))
	var p: Vector3 = fr * Vector3(0.0, sh, 0.0)
	var dir: Vector3 = (fr.basis * Vector3(0, 0, 1)).normalized()
	var up: Vector3 = (fr.basis * Vector3(0, 1, 0)).normalized()
	# повернуть так, чтобы линия смотрела по −Z камеры, а верх рамы — вверх
	var src := Basis(up.cross(dir).normalized(), up, dir).orthonormalized()
	var dst := Basis(Vector3(-1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, -1))
	var r: Basis = dst * src.inverse()
	var az: float = float(frame.get_meta("ads_z", 0.3))
	return Transform3D(r, Vector3(0, 0, -az) - r * p)


## Сбросить кэш линии прицеливания (сменили обвес — пересобирается весь узел, но на всякий случай).
func reset_sight() -> void:
	_sight_cache.clear()
