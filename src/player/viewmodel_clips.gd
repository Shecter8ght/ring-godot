class_name ViewmodelClips
extends Node3D
## Руки и оружие от первого лица с заготовленными клипами из Blender (tools/export_veras54.py):
## стойка, тактическая и полная перезарядка, проверка магазина, устранение задержки. Сцена уже в осях
## камеры (камера в начале, взгляд по −Z), поэтому у бедра узел почти не сдвигается — поза та, что в Blender.
## Под рукоятку под цевьём со своим набором клипов (attach.viewmodel_set: ВАРН V1 / V2) берутся клипы
## «<клип>_<набор>»: левая держит рукоятку, в перезарядке отпускает её и берёт снова.
##
## Клипом управляет состояние игрока (опрос каждый кадр, без новых событий в Player): началась
## перезарядка — клип по пустому/непустому магазину, растянутый на её время (стресс удлиняет);
## прервали — плавно в стойку; проверка патронов — клип проверки; выстрел — отвод затвора.
## Проверка магазина с удержанием: пока R держат (Player.mag_inspect), клип стоит на участке «магазин
## перед глазами» (config.check_hold — кадры), кисть с магазином поворачивается мышью
## (Player.inspect_turn); отпустили — клип идёт дальше, магазин возвращается в оружие.
## Быстрая перезарядка (Player._reload_fast, двойное R): клипы reload_fast / reload_fast_empty — новым
## магазином выбивают старый (узлы Part_SpareMag и SpareRounds видны только в этом клипе).
## Задержка (Player.is_jammed): затвор недозакрыт, в окне торчит гильза (узел Part_JamCase); R — клип
## jam_clear: правая отводит затвор, гильза выпадает.
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
## Корпус магазина в сцене рук: вынут (Player.weapon_mag == "") — не виден, кроме перезарядки, где
## клип вставляет новый.
var _mag_parts: Array[Node3D] = []
## Левая кисть клипа держит цевьё в одном месте; рукоятка (или фонарь, сошки) по пазу планки —
## кисть переезжает вдоль цевья к своему месту хвата (IK плечо–предплечье поверх клипа). Куда — z
## запястья в осях рамы (NAN — как в клипе); в перезарядке и проверке поправка плавно уходит.
var _grip_z: float = NAN
var _grip_w: float = 0.0
var _arm_skel: Skeleton3D
var _arm_bones: Array[int] = []
## Поза левой руки клипа до поправки под место хвата ([положение, поворот] трёх костей): в начале
## следующего кадра возвращается. У костей рук в клипах есть не все дорожки (положение не записано),
## и без возврата поправка прибавлялась кадр за кадром — кисть уезжала от оружия.
var _arm_saved: Array = []
## Набор клипов под рукоятку ("" — рука на цевье) и на сколько её место отличается от того, где она
## стояла в Blender (кисть переезжает вместе с ней): вдоль планки по пазам, а на удлинителе — ещё и вниз.
var _set: String = ""
var _grip_shift: Vector3 = Vector3.ZERO
## Гильза задержки и таймер клипа «устранить задержку» на прошлом кадре.
var _jam_case: Node3D
var _last_clear: float = 0.0
## Вставка магазина в оружие без магазина (Player._reload_insert): клип перезарядки идёт с кадра, где
## новый магазин уже в руке; пока руки переходят к этой позе, магазин не виден (иначе он «выезжал»
## бы из шахты в ладонь).
var _insert_hide: float = 0.0
## Старый магазин быстрой перезарядки (корпус и его патроны) и идёт ли сейчас быстрый клип.
var _spare_parts: Array[Node3D] = []
var _spare_rounds: Node3D
var _fast: bool = false
## Проверка с удержанием: клип стоит на участке показа; фаза покачивания; сглаженный поворот кисти.
var _holding: bool = false
var _hold_phase: float = 0.0
var _turn: Vector2 = Vector2.ZERO
var _mag_bone: int = -1
var _signal_props: Dictionary = {}
var _signal_old_type: String = "flare"
var _signal_has_old: bool = false
var _signal_left_arm: Node3D


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
	if String(config.get("mechanism", "")) == "break_action":
		_signal_left_arm = model.find_child("FPS_Arms_Left", true, false) as Node3D
		if _signal_left_arm:
			_signal_left_arm.visible = false
		for prop: String in ["LoadRoundRed", "LoadRoundGreen", "OldRoundRed", "OldRoundGreen"]:
			var node: Node3D = model.find_child(prop, true, false) as Node3D
			if node:
				_signal_props[prop] = node
				node.visible = false
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
	# Стойка идёт по кругу: пока клип играет, он каждый кадр заново ставит кости рук. Иначе, доиграв,
	# он оставлял позу как есть, и поправка кисти под рукоятку (сдвиг относительно клипа) прибавлялась
	# кадр за кадром — рука уезжала от оружия.
	var idle_base: String = String((config.get("clips", {}) as Dictionary).get("idle", "idle"))
	for clip_name: StringName in _anim.get_animation_list():
		if String(clip_name) == idle_base or String(clip_name).begins_with(idle_base + "_"):
			_anim.get_animation(clip_name).loop_mode = Animation.LOOP_LINEAR
	_follower_src = _anim.get_animation("follower_by_rounds") if _anim.has_animation("follower_by_rounds") else null
	_bolt_src = _anim.get_animation("bolt_travel") if _anim.has_animation("bolt_travel") else null
	if _bolt_src:
		# две записи (закрыт / отведён) импортируются «ступенькой» — промежуточный ход затвора нужен плавным
		for i in range(_bolt_src.get_track_count()):
			_bolt_src.track_set_interpolation_type(i, Animation.INTERPOLATION_LINEAR)
	for i in range(1, 31):
		var r: Node3D = model.find_child("Round_%02d" % i, true, false) as Node3D
		if r == null:
			break
		_rounds.append(r)
	for s: Node in model.find_children("*", "Skeleton3D", true, false):
		var arm: Skeleton3D = s as Skeleton3D
		if arm.find_bone("hand.L") >= 0 and arm.find_bone("forearm.L") >= 0 and arm.find_bone("upper_arm.L") >= 0:
			_arm_skel = arm
			_arm_bones = [arm.find_bone("upper_arm.L"), arm.find_bone("forearm.L"), arm.find_bone("hand.L")]
	var model_key: String = String(WeaponDb.weapon(id).get("model", ""))
	_jam_case = model.find_child("Part_JamCase*", true, false) as Node3D
	if _jam_case:
		_jam_case.visible = false
	for raw_spare: Node in model.find_children("Part_SpareMag*", "Node3D", true, false):
		_spare_parts.append(raw_spare as Node3D)
		(raw_spare as Node3D).visible = false
	_spare_rounds = model.find_child("SpareRounds*", true, false) as Node3D
	if _spare_rounds:
		_spare_rounds.visible = false
	# выброшенный магазин и вылетающая гильза — не объём оружия: в быстрой перезарядке магазин падает
	# на землю, и ствол «складывался» бы вслед за ним (WeaponClearance)
	var loose: Array[Node3D] = _spare_parts.duplicate()
	if _spare_rounds: loose.append(_spare_rounds)
	if _jam_case: loose.append(_jam_case)
	for part: Node3D in loose:
		part.set_meta("weapon_clearance_ignore", true)
		for sub: Node in part.find_children("*", "MeshInstance3D", true, false):
			sub.set_meta("weapon_clearance_ignore", true)
	if _weapon_skel:
		_mag_bone = _weapon_skel.find_bone("Magazine_Control")
	for raw_part: Node in model.find_children("Part_Magazine*", "Node3D", true, false):
		_mag_parts.append(raw_part as Node3D)
	frame = model.find_child("WeaponFrame", true, false) as Node3D
	if frame == null:
		frame = Node3D.new()
		model.add_child(frame)
	WeaponModels.apply_markers(frame, model, float(config.get("ads_z", 0.3)))
	WeaponMods.fit(frame, String(WeaponDb.weapon(id).get("model", "rifle")), mods)
	# место хвата — после установки обвеса: у рукоятки на удлинителе оно считается от рамки переходника
	var under: String = WeaponGrips._under_key(mods)
	if under != "":
		var place: Vector3 = WeaponMods.point_frame(frame, model_key, mods, under).origin
		var socket_pos: Vector3 = WeaponMods.socket(model_key, "underbarrel").get("pos", Vector3.ZERO)
		var under_id: String = WeaponDb.mod_id(mods[under])
		_grip_shift = place - socket_pos
		if String(WeaponDb.attachment(under_id).get("look", "")).begins_with("grip_"):
			_grip_z = place.z - float(Balance.SUPPORT_GRIP.behind_grip)
		else:
			_grip_z = place.z - WeaponBuild.clamp_of(under_id) * 0.5 - float(Balance.SUPPORT_GRIP.behind_device)
		var grip_set: String = String(WeaponDb.attachment(under_id).get("viewmodel_set", ""))
		var idle: String = String((config.get("clips", {}) as Dictionary).get("idle", "idle"))
		if grip_set != "" and _anim.has_animation(idle + "_" + grip_set):
			_set = grip_set
	# meta основы — и на корне: CameraRig проверяет прицел (ocular, reticle_illum) у модели в руках
	for k: StringName in frame.get_meta_list():
		set_meta(k, frame.get_meta(k))
	for mi: Node in find_children("*", "GeometryInstance3D", true, false):
		var gi := mi as GeometryInstance3D
		gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# руки и оружие не уходят за дальнюю плоскость при близкой камере
		gi.extra_cull_margin = 0.5
	_play(_clip_name("idle"), 0.0)
	if String(config.get("mechanism", "")) == "break_action":
		_play(_clip_name("draw"), 0.0)


## Клип по роли (idle, reload, reload_empty, check, clear) — из набора под рукоятку, если он есть.
func _clip_name(kind: String) -> String:
	var clip: String = _base_clip(kind)
	if _set != "" and clip != "" and _anim.has_animation(clip + "_" + _set):
		return clip + "_" + _set
	return clip


func _base_clip(kind: String) -> String:
	return String((config.get("clips", {}) as Dictionary).get(kind, ""))


func _play(clip: String, blend: float, duration: float = 0.0) -> void:
	if clip == "" or not _anim.has_animation(clip):
		return
	_anim.play(clip, blend)
	var length: float = _anim.get_animation(clip).length
	_anim.speed_scale = length / duration if duration > 0.0 else 1.0
	_clip = "" if clip in [_clip_name("idle"), _clip_name("idle_empty")] else clip


## Повторно достали готовую модель: старые таймеры не запускают выстрел или чужую перезарядку.
func equip() -> void:
	_last_reload = 0.0
	_last_check = 0.0
	_last_clear = 0.0
	_last_ammo = -1
	_kick = 0.0
	_insert_hide = 0.0
	_holding = false
	_turn = Vector2.ZERO
	_fast = false
	_play(_clip_name("draw") if String(config.get("mechanism", "")) == "break_action" else _clip_name("idle"), 0.0)


## Опрос состояния игрока: перезарядка (начало по фронту таймера, отмена — в стойку), проверка
## магазина, выстрелы (затвор), счёт патронов на виду. Затем шаг клипа и затвор/подаватель поверх.
func update(pl: Player, delta: float) -> void:
	if String(config.get("mechanism", "")) == "break_action":
		_update_signal(pl, delta)
		return
	var mag: int = int(pl.spec().get("mag", 30))
	var reloading: bool = pl.reload_timer > 0.0 and pl._reload_kind != "clear"
	if reloading and _last_reload <= 0.0:
		var empty: bool = pl._reload_empty
		var role: String = "reload_empty" if empty else "reload"
		_rounds_before = 0 if empty else clampi(pl.ammo, 0, _rounds.size())
		_rounds_after = clampi(mag, 0, _rounds.size())
		_swap_frame = int((config.get("swap_frame", {}) as Dictionary).get(_base_clip(role), -1))
		_fast = false
		_play(_clip_name(role), BLEND_IN, pl.reload_timer)
		if pl._reload_insert and _swap_frame >= 0:
			# магазина в оружии нет: вынимать нечего — клип с кадра, где новый магазин уже в руке
			var from: float = float(_swap_frame) / float(config.get("fps", 30))
			var length: float = _anim.get_animation(_clip_name(role)).length
			if from < length - 0.05:
				_anim.seek(from, true)
				_anim.speed_scale = (length - from) / maxf(pl.reload_timer, 0.05)
				_insert_hide = BLEND_IN
	elif reloading and pl._reload_fast and not _fast and _clip_name("reload_fast") != "":
		# второе R: перезарядка стала быстрой — её клип с начала, на оставшееся время
		_fast = true
		var fast_role: String = "reload_fast_empty" if pl._reload_empty else "reload_fast"
		_swap_frame = int((config.get("swap_frame", {}) as Dictionary).get(_base_clip(fast_role), -1))
		_play(_clip_name(fast_role), BLEND_IN, pl.reload_timer)
	elif not reloading and _last_reload > 0.0 and _clip != "" and _clip != _clip_name("check"):
		# закончилась или прервана — в стойку (досылка уже показана клипом)
		_play(_clip_name("idle"), BLEND_OUT)
	_last_reload = pl.reload_timer if reloading else 0.0
	if not reloading:
		_fast = false
	# задержка: R — передёрнуть затвор (клип на время устранения); прервали — в стойку
	var clearing: bool = pl.reload_timer > 0.0 and pl._reload_kind == "clear"
	if clearing and _last_clear <= 0.0:
		_rounds_before = clampi(pl.ammo, 0, _rounds.size())
		_rounds_after = _rounds_before
		_swap_frame = -1
		_play(_clip_name("clear"), BLEND_IN, pl.reload_timer)
	elif not clearing and _last_clear > 0.0 and _clip != "" and _clip == _clip_name("clear"):
		_play(_clip_name("idle"), BLEND_OUT)
	_last_clear = pl.reload_timer if clearing else 0.0
	var jammed: bool = pl.is_jammed()
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
	_restore_arm()
	_advance(pl, delta)
	if _clip != "" and not _anim.is_playing():
		_play(_clip_name("idle"), BLEND_OUT)
	var shown: int = clampi(pl.ammo, 0, _rounds.size())
	if _clip != "":
		var f: float = _anim.current_animation_position * float(config.get("fps", 30))
		shown = _rounds_after if _swap_frame >= 0 and f >= _swap_frame else _rounds_before
	for i in range(_rounds.size()):
		_rounds[i].visible = i < shown
	_insert_hide = maxf(0.0, _insert_hide - delta) if reloading else 0.0
	if _insert_hide > 0.0:
		for round_node: Node3D in _rounds:
			round_node.visible = false
	var mag_in: bool = (pl.weapon_mag != "" or reloading) and _insert_hide <= 0.0
	for part: Node3D in _mag_parts:
		part.visible = mag_in
	# старый магазин быстрой перезарядки: виден с кадра, когда новый уже в руке, до конца клипа
	var spare_on: bool = _fast and _clip != "" and _swap_frame >= 0 \
			and _anim.current_animation_position * float(config.get("fps", 30)) >= _swap_frame
	for spare: Node3D in _spare_parts:
		spare.visible = spare_on
	if _spare_rounds:
		_spare_rounds.visible = spare_on and _rounds_before > 0
	var clear_clip: bool = _clip != "" and _clip == _clip_name("clear")
	if _jam_case:
		# гильза в окне — пока задержка не устранена; в клипе её выбрасывает сам клип
		_jam_case.visible = jammed or clear_clip
	_pose_overrides(shown, delta, jammed and not clear_clip)
	_inspect_turn(pl, delta)
	_grip_w = move_toward(_grip_w, 0.0 if is_busy() or is_nan(_grip_z) else 1.0, delta / BLEND_IN)
	_support_hand(_grip_w)


func weapon_action(action: String, _flag: bool = false, _duration: float = 0.0, _rounds_left: int = -1) -> void:
	if String(config.get("mechanism", "")) != "break_action":
		return
	if action == "shot":
		_play(_clip_name("shot"), 0.03)
	elif action == "cancel":
		_last_reload = 0.0
		_play(_clip_name("idle_empty") if _rounds_left <= 0 else _clip_name("idle"), BLEND_OUT)


## Ракетница деформируется жёсткими костями: AABB покоя всего меша не описывает открытый ствол.
func clearance_boxes() -> Array[AABB]:
	var boxes: Array[AABB] = []
	if _arm_skel == null:
		return boxes
	var parts: Dictionary = config.get("clearance_parts", {})
	var skeleton_at: Transform3D = WeaponRig._relative_transform(_arm_skel, self)
	for part_name: String in parts:
		var bone: int = _arm_skel.find_bone(part_name)
		if bone < 0:
			continue
		var low: Array = (parts[part_name] as Dictionary).min
		var high: Array = (parts[part_name] as Dictionary).max
		var point := Vector3(float(low[0]), float(low[1]), float(low[2]))
		var end := Vector3(float(high[0]), float(high[1]), float(high[2]))
		var bone_at: Transform3D = skeleton_at * _arm_skel.get_bone_global_pose(bone)
		boxes.append(bone_at * AABB(point, end - point).grow(0.001))
	return boxes


func uses_left_hand() -> bool:
	return String(config.get("mechanism", "")) != "break_action" or (_signal_left_arm != null and _signal_left_arm.visible)


func _update_signal(pl: Player, delta: float) -> void:
	var reloading: bool = pl.reload_timer > 0.0
	var resting: String = _clip_name("idle") if pl.ammo > 0 else _clip_name("idle_empty")
	if reloading and _last_reload <= 0.0:
		_signal_old_type = pl.weapon_signal_ammo
		_signal_has_old = pl.ammo > 0 or bool(pl.weapon_entry().get("signal_spent", false))
		_play(_clip_name("reload_empty" if pl._reload_empty else "reload"), BLEND_IN, pl.reload_timer)
	elif not reloading and _last_reload > 0.0:
		_play(resting, BLEND_OUT)
	_last_reload = pl.reload_timer if reloading else 0.0
	_anim.advance(delta)
	if not reloading and (_clip == "" or not _anim.is_playing()) and String(_anim.current_animation) != resting:
		_play(resting, BLEND_OUT)
	var f: float = 1.0 + _anim.current_animation_position * float(config.get("fps", 30))
	if _signal_left_arm:
		var assisting: bool = false
		for window: Array in config.get("left_hand_windows", [[1,36],[70,117]]):
			assisting = assisting or (f >= float(window[0]) and f <= float(window[1]))
		_signal_left_arm.visible = reloading and assisting
	var windows: Dictionary = config.get("round_windows", {})
	var old_window: Array = windows.get("old", [1, 65])
	var new_window: Array = windows.get("new", [73, 156])
	for name: String in _signal_props:
		var old: bool = name.begins_with("Old")
		var green: bool = name.ends_with("Green")
		var type: String = (_signal_old_type if old else pl.signal_reload_ammo) if reloading else pl.weapon_signal_ammo
		var window: Array = old_window if old else new_window
		var shown: bool = reloading and f >= float(window[0]) and f <= float(window[1])
		if reloading:
			shown = shown and (not old or _signal_has_old)
		else:
			shown = pl.ammo == 0 and bool(pl.weapon_entry().get("signal_spent", false)) if old else pl.ammo > 0
		(_signal_props[name] as Node3D).visible = shown and green == (type == "supply_signal")


## Шаг клипа. Проверка магазина с удержанием: пока R держат, клип дошёл до участка показа и стоит на
## нём (медленно покачиваясь между его кадрами); отпустили — продолжается с конца участка.
func _advance(pl: Player, delta: float) -> void:
	var hold: Array = config.get("check_hold", [])
	var fps: float = float(config.get("fps", 30))
	if hold.size() == 2 and _clip != "" and _clip == _clip_name("check"):
		var from: float = float(hold[0]) / fps
		var to: float = float(hold[1]) / fps
		var pos: float = _anim.current_animation_position
		if pl.mag_inspect and (_holding or pos >= from):
			if not _holding:
				_holding = true
				_hold_phase = 0.0
			_hold_phase += delta * 0.9
			_anim.seek(lerpf(from, to, 0.5 - 0.5 * cos(_hold_phase)), true)
			return
		if _holding:
			_holding = false
			_anim.seek(to, true)
	else:
		_holding = false
	_anim.advance(delta)


## Поворот кисти с магазином мышью, пока магазин держат перед глазами: как рукой — предплечье на месте,
## кисть проворачивается вокруг его оси (мышь вбок: магазин показывает то один бок, то другой) и
## сгибается в запястье (мышь вверх-вниз). Ось — запястье, магазин едет вместе с кистью.
## Отпустили — плавно назад.
func _inspect_turn(pl: Player, delta: float) -> void:
	var want: Vector2 = pl.inspect_turn if _holding else Vector2.ZERO
	_turn = _turn.lerp(want, minf(1.0, delta * 10.0))
	if _turn.length() < 0.004 or _arm_skel == null or _mag_bone < 0 or _weapon_skel != _arm_skel:
		return
	var sk: Skeleton3D = _arm_skel
	var cam: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	if cam == null:
		return
	var limits: Array = Balance.AMMO_CHECK.turn_deg
	var mag: Transform3D = sk.get_bone_global_pose(_mag_bone)
	var hand: Transform3D = sk.get_bone_global_pose(_arm_bones[2])
	var fore: Transform3D = sk.get_bone_global_pose(_arm_bones[1])
	var along: Vector3 = (hand.origin - fore.origin).normalized()
	var right: Vector3 = (sk.global_basis.inverse().orthonormalized() * cam.global_basis.x).normalized()
	var rot := Basis(along, deg_to_rad(float(limits[0])) * _turn.x) * Basis(right, deg_to_rad(float(limits[1])) * _turn.y)
	var pivot: Vector3 = hand.origin
	var turn := Transform3D(rot, pivot - rot * pivot)
	_pose_bone(sk, _arm_bones[2], turn * hand)
	_pose_bone(sk, _mag_bone, turn * mag)


## jam_hold — задержка не устранена: затвор стоит недозакрытым на зажатой гильзе (config.jam_open — доля хода).
func _pose_overrides(shown: int, delta: float, jam_hold: bool = false) -> void:
	if _weapon_skel == null:
		return
	if _follower >= 0 and _follower_src:
		_apply_sample(_follower_src, "MagazineFollower", _follower, _table_time(_follower_src, float(shown), 31))
	var open: float = float(config.get("jam_open", 0.4)) if jam_hold else 0.0
	if _kick > 0.0:
		_kick = maxf(0.0, _kick - delta)
		open = maxf(open, sin(PI * (1.0 - _kick / BOLT_KICK_SEC)))
	if open > 0.0 and _bolt >= 0 and _bolt_src:
		_apply_sample(_bolt_src, "Bolt", _bolt, _table_time(_bolt_src, open, 2))


## Время записи index в служебном клипе-таблице из count записей по кадру на запись. Отсчёт — от конца
## клипа: экспорт glTF начинает дорожку на кадр раньше первой записи (счёт от начала давал сдвиг на
## кадр — затвор при выстреле стоял закрытым).
func _table_time(src: Animation, index: float, count: int) -> float:
	return maxf(0.0, src.length - (float(count - 1) - index) / float(config.get("fps", 30)))


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


## Сдвинуть левую кисть клипа к месту хвата: запястье переезжает (вдоль цевья; за рукояткой на
## удлинителе — ещё и вниз), поворот кисти — клиповый, плечо и предплечье — двухзвенным IK (длины
## костей сохраняются). Без своих клипов (_grip_z): рукоятка — ладонь сразу за ней, фонарь, сошки —
## кисть позади их зажима. Рукоятка со своими клипами: кисть уже на ней — едет ровно на её сдвиг от
## места, где она стояла в Blender.
func _support_hand(weight: float) -> void:
	if _arm_skel == null or weight <= 0.001 or is_nan(_grip_z) or frame == null:
		return
	var sk: Skeleton3D = _arm_skel
	var up: Transform3D = sk.get_bone_global_pose(_arm_bones[0])
	var fore: Transform3D = sk.get_bone_global_pose(_arm_bones[1])
	var hand: Transform3D = sk.get_bone_global_pose(_arm_bones[2])
	# ось цевья (+Z рамы) в осях скелета; на сколько ехать — по текущему запястью клипа
	var to_frame: Transform3D = frame.global_transform.affine_inverse() * sk.global_transform
	var wrist_z: float = (to_frame * hand.origin).z
	var shift: Vector3 = _grip_shift if _set != "" else Vector3(_grip_shift.x, _grip_shift.y, _grip_z - wrist_z)
	shift = shift.limit_length(float(Balance.SUPPORT_GRIP.max_shift)) * weight
	if shift.length() < 0.0005:
		return
	var to_skel: Basis = (sk.global_transform.affine_inverse().basis * frame.global_basis).orthonormalized()
	var target: Vector3 = hand.origin + to_skel * shift
	var upper_len: float = up.origin.distance_to(fore.origin)
	var lower_len: float = fore.origin.distance_to(hand.origin)
	var pole: Vector3 = fore.origin - (up.origin + hand.origin) * 0.5
	var ik: Dictionary = ArmIKSolver.solve(up.origin, target, upper_len, lower_len, pole, sk.global_transform)
	var elbow: Vector3 = ik.elbow
	var wrist: Vector3 = ik.wrist
	_arm_saved.clear()
	for bone: int in _arm_bones:
		_arm_saved.append([sk.get_bone_pose_position(bone), sk.get_bone_pose_rotation(bone)])
	var up_rot := Basis(Quaternion((fore.origin - up.origin).normalized(), (elbow - up.origin).normalized()))
	var new_up := Transform3D(up_rot * up.basis, up.origin)
	_pose_bone(sk, _arm_bones[0], new_up)
	var fore_now: Transform3D = new_up * (up.affine_inverse() * fore)
	# предплечье уже повёрнуто вместе с плечом — доворачиваем от нового направления, а не от клипового
	var fore_rot := Basis(Quaternion((up_rot * (hand.origin - fore.origin)).normalized(), (wrist - elbow).normalized()))
	_pose_bone(sk, _arm_bones[1], Transform3D(fore_rot * fore_now.basis, elbow))
	_pose_bone(sk, _arm_bones[2], Transform3D(hand.basis, wrist))


## Поставить кость в позу в осях скелета, не трогая её масштаб. set_bone_global_pose раскладывает позу
## на положение, поворот и масштаб; масштаб выходит с погрешностью, клипы его не пишут и не возвращают —
## погрешность копилась кадр за кадром всё быстрее, и левая кисть на рукоятке раздувалась.
func _pose_bone(sk: Skeleton3D, bone: int, pose: Transform3D) -> void:
	var keep: Vector3 = sk.get_bone_pose_scale(bone)
	sk.set_bone_global_pose(bone, pose)
	sk.set_bone_pose_scale(bone, keep)


## Вернуть кости левой руки к позе клипа (до прошлой поправки) — перед шагом клипа.
func _restore_arm() -> void:
	if _arm_saved.is_empty() or _arm_skel == null:
		return
	for i: int in range(_arm_bones.size()):
		_arm_skel.set_bone_pose_position(_arm_bones[i], _arm_saved[i][0])
		_arm_skel.set_bone_pose_rotation(_arm_bones[i], _arm_saved[i][1])
	_arm_saved.clear()


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
