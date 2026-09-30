class_name Player
extends CharacterBody3D
## Игрок: движение по стойкам относительно камеры, корпус смотрит на курсор.
## В прицеле (ПКМ, см. CameraRig) — вид от первого лица: взгляд ведёт мышь, WASD — относительно
## взгляда, выстрел — из глаз по оси взгляда. Оружие: 1–4 пистолет/автомат/дробовик/винтовка,
## G — граната. Смерть — регдолл. Тяжело ранен (Health.downed) — лежит, ползёт, стреляет только
## из пистолета, кидает гранаты; его могут поднять (аптечка) и тащить (X); X (держать) — сдаться.
## Сеть: узлом владеет тот peer, чей id записан в `peer_id`; чужих игроков двигает синхронизация.

enum Stance { STAND, CROUCH, PRONE }

@export var peer_id: int = 1

var stance: Stance = Stance.STAND
var aiming: bool = false
## Прицел от первого лица включён — ставит CameraRig.
var ads: bool = false
## Наклон (Q/E) от первого лица: -1 — влево, 1 — вправо; синхронизируется (AI видит высунувшегося).
var lean: float = 0.0
## Слой своего тела от первого лица (свет «из глаз» его не затеняет).
const OWN_BODY_LAYER := 1 << 17
## Направление взгляда в прицеле, рад (курс от +Z, тангаж вверх) — ставит CameraRig.
var look_yaw: float = 0.0
var look_pitch: float = 0.0
## Точка на земле под курсором — ставит камера/уровень; корпус поворачивается к ней.
var cursor_ground: Vector3 = Vector3.ZERO
## Точка на теле противника под курсором (Vector3.ZERO — под курсором никого): выстрел идёт в неё.
var cursor_body: Vector3 = Vector3.ZERO

## Рейд из убежища: оружие только из снаряжения (1 — основное, 2 — пистолет), магазины, патроны и
## гранаты — из рюкзака. false — «песочница» (тесты, запуск уровня напрямую): стволы из
## WeaponDb.sandbox(), патроны без счёта.
var loadout_mode: bool = false
## false — оружие в руках не работает (чужие игроки у себя; раньше — и убежище).
var combat_enabled: bool = true
## Оружие в руках: id предмета ("" — руки пусты) и откуда оно (слот снаряжения / ключ песочницы).
var weapon_id: String = ""
## Счётчик одноразовых анимаций синхронизируется вместе с персонажем.
var animation_event: String = ""
var animation_event_seq: int = 0
var weapon_slot: String = ""
## Обвес в руках с состоянием фонарей/ЛЦУ (точка → {id, light, laser}): модель на теле у всех.
var weapon_mods: Dictionary = {}
## Горит фонарь / ЛЦУ на оружии в руках (выдаёт, слепит) — видят все.
var light_on: bool = false
var laser_on: bool = false
## Песочница: стволы по ключам (пресеты WeaponDb.sandbox()) — записи оружия.
var sandbox_weapons: Dictionary = {}
## Состояние оружия у владельца (патроны, износ, прицел, фонари/ЛЦУ, задержка) — слот → словарь;
## хосту уходит при перезарядке, смене оружия, переключениях и паузе в стрельбе.
var _ws: Dictionary = {}
var _ws_dirty: bool = false
var _ws_sync_t: float = 0.0
## Боезапас оружия в руках (HUD): магазин и, если поддерживается, патронник.
var ammo: int = 0
## Боезапас для позы затвора у напарников; у ПМ включает отдельно учтённый патрон в патроннике.
var weapon_rounds: int = 0
## Перезарядка: что делаем ("swap", "topup", "clear" — устранить задержку), для какого слота, какую
## ревизию записи ждём от хоста.
var _reload_kind: String = ""
var _reload_slot: String = ""
var _reload_rev: int = -1
var _reload_wait: float = 0.0
var _reload_empty: bool = false
## ПМ меняет предметы только после окончания действия. До этого прерывание отменяет лишь позу.
var _pm_action: Dictionary = {}
var _pm_action_seq: int = 0
var _pm_host_seq: int = 0
var _weapon_rig: WeaponRig
## Ответ хоста может прийти раньше снимка Inventory; до его ревизии читаем подтверждённую запись.
var _pm_entries: Dictionary = {}
var _was_downed: bool = false
var _sandbox_picked: bool = false
## Сколько секунд держим прицел — «довод» по эргономике (WeaponStats.aim_time).
var _aim_t: float = 0.0
var grenades: int = Balance.GRENADES_START
var fire_timer: float = 0.0
var reload_timer: float = 0.0
## Сколько держат R (≥ 0 — держат): коротко — перезарядка, дольше Balance.AMMO_CHECK.hold_sec —
## проверка патронов в магазине.
var _reload_hold: float = -1.0
## Итог последней проверки («почти полный», «7 из 17») и сколько ещё его показывать, с.
var ammo_check_text: String = ""
var ammo_check_t: float = 0.0
var _step_timer: float = 0.0
## Текущий подброс ствола от отдачи, рад — гаснет к нулю.
var _recoil: float = 0.0
## Отдача: уход вбок (временный, рад), раскачка разброса, толчок модели в руках (0…, пружина).
var _recoil_h: float = 0.0
var _bloom: float = 0.0
var kick_vis: float = 0.0
var _rng := RandomNumberGenerator.new()
var _hand: Node3D
## Фонари и лазеры модели оружия — их светит по прицельной оси (_update_hand).
var _aimed: Array[Node3D] = []
var _weapon_model: Node3D
var _weapon_model_id: String = ""
var _ragdoll: Ragdoll
## Смерть показана клипом (CharacterAnimator.die), регдолла нет.
var _died_shown: bool = false
var _last_hit_from: Vector3 = Vector3.ZERO
var _last_damage: float = 0.0
## Лёжа держит X — сколько секунд (сдаться).
var _give_up_t: float = 0.0
## Несёт раненого NPC (сюжет, QuestWorld): медленно, только пистолет.
var carrying: bool = false
## Сидит (диван в убежище): не ходит, пока не шагнёт или не нажмёт C.
var seated: bool = false
## Выносливость: бег тратит, отдых восстанавливает; выдохся — не бежит до порога.
var stamina: float = Balance.STAMINA_MAX
var _winded: bool = false
var _breath_sound: AudioStreamPlayer3D
var _rest_t: float = 0.0
## ПНВ включён (N; нужен ПНВ в слоте «глаза») и сколько заряда осталось, с.
var nvg_on: bool = false
var nvg_charge: float = Balance.NVG_BATTERY_SEC
## Перелезает (Пробел у преграды): путь (Vault.find), доля пройденного (-1 — нет), длительность.
var _vault: Dictionary = {}
var _vault_t: float = -1.0
var _vault_sec: float = 0.75
## Стресс 0–100 (Balance.STRESS): считает владелец; события от хоста (пули рядом) — по RPC.
var stress: float = 0.0
var _stress_quiet: float = 0.0
var _near_t: float = 0.0
var _stumble_cd: float = 0.0
var _fumble_cd: float = 0.0
var _vault_stumble: bool = false
## Напарники, которых я видел лежащими раненными (peer → true) — упал новый рядом: стресс.
var _allies_down: Dictionary = {}
## Бросок на землю (Alt): сколько уже летит (-1 — нет), куда, когда можно снова.
var _dive_t: float = -1.0
var _dive_dir: Vector3 = Vector3.ZERO
var _dive_cd: float = 0.0
## G зажата — прицел гранаты (дуга и круг поражения), отпустил — бросок.
var _nade_aiming: bool = false
var _nade_aim: GrenadeAim

@onready var _capsule: CollisionShape3D = $Capsule
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle
@onready var _animator: CharacterAnimator = get_node_or_null("CharacterAnimator") as CharacterAnimator
@onready var health: Health = $Health
## Рюкзак: меняет хост, видят все (см. Inventory). Создаётся в _ready.
var inventory: Inventory
@onready var _camera_rig: Node3D = get_tree().get_first_node_in_group("camera_rig")


func _ready() -> void:
	add_to_group("players")
	# "players" — кто сейчас в мире (его видят мародёры); "all_players" — все, включая ушедших
	add_to_group("all_players")
	_rng.randomize()
	health.max_hp = Balance.PLAYER_HP
	health.hp = health.max_hp
	# смерть учитывает рейд (сигнал died приходит только у хоста — он и считает итог)
	health.died.connect(func() -> void:
		if Raid.current:
			Raid.current.mark_dead(peer_id))
	health.damaged.connect(func(amount: float, from: Vector3) -> void:
		# хост: кто и чем попал — в хронику того, в кого попали
		if Raid.current and (not Net.is_networked() or multiplayer.is_server()):
			Raid.current.story_hit(peer_id, amount, health.last_attacker, health.last_src)
		_animation_event("hit")
		_last_hit_from = from
		_last_damage = amount
		Audio.play("pain_player", global_position + Vector3.UP * 1.2)
		if is_local() and _camera_rig is CameraRig:
			# на адреналине попадание почти не сбивает
			(_camera_rig as CameraRig).add_shake(Balance.HURT_SHAKE * (1.0 - float(Balance.STRESS.adr_shake) * stress_k()))
		add_stress(float(Balance.STRESS.hit) + amount * float(Balance.STRESS.hit_per_dmg)))
	health.downed_changed.connect(func(on: bool) -> void:
		Audio.play("downed" if on else "revive", global_position + Vector3.UP)
		if on:
			cancel_weapon_action())
	_muzzle.visible = false
	# рюкзак — авторитет хоста (узел создан после выдачи авторитета Player — умалчиваемый 1)
	inventory = Inventory.new()
	inventory.name = "Inventory"
	add_child(inventory)
	# шаги слышно у всех: и свои, и напарника (по синхронизированной позиции и стойке)
	var steps := Footsteps.new()
	steps.name = "Footsteps"
	steps.loud_db = func() -> float: return float(Balance.STEP_STANCE_DB.get(_stance_key(), 0.0))
	steps.movement_kind = func() -> String:
		if stance == Stance.PRONE or is_downed():
			return "crawl"
		return "step_crouch" if stance == Stance.CROUCH else ""
	add_child(steps)
	# броня, плиты, шлем — Armor (считается там же, где урон, — на хосте)
	health.damage_filter = func(amount: float, zone: String, from: Vector3, at: Vector3, bullet: Dictionary) -> Array:
		var p := at if at != Vector3.INF else global_position + Vector3.UP * 1.3
		var result := inventory.absorb(amount, zone, from, p, Vector3(sin(body_yaw()), 0.0, cos(body_yaw())), bullet, _rng)
		if inventory.last_armor_layer != "":
			Audio.play("impact_helmet" if inventory.last_armor_layer == "helmet" else "impact_plate", p)
		return result
	# тяжело ранен вместо смерти
	health.can_down = true
	health.always_down_first = true
	# рука с оружием — не внутри Body: Body сжимается по стойке, оружие сжиматься не должно
	_hand = Node3D.new()
	_hand.name = "Hand"
	add_child(_hand)
	_apply_stance()
	# Слушаем мир из своей позиции, а не из камеры в 28 м над головой.
	if is_local():
		var listener := AudioListener3D.new()
		add_child(listener)
		listener.position = Vector3(0, 1.5, 0)
		listener.make_current()
	if Net.is_networked():
		_setup_sync()
	# чит «бессмертие» из настроек — на каждый рейд (хосту — когда узел у него уже есть)
	if is_local() and Settings.god:
		set_god.call_deferred(true)


## Позицию и позу владелец шлёт всем остальным сам (авторитет = peer_id, см. sector_level.gd —
## отзывчивое движение важнее для игрока, чем для мародёра/двери). Health синхронизируется
## отдельно, со своим (хостовым) авторитетом — урон всегда считает хост.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", ".:stance", ".:aiming", ".:weapon_id", ".:weapon_mods", ".:weapon_rounds", ".:light_on", ".:laser_on", ".:lean", ".:look_pitch", ".:animation_event", ".:animation_event_seq"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	Net.scope_sync(self, sync)
	add_child(sync)


func is_alive() -> bool:
	return health.alive


## Куда попала пуля: голова — выше HEAD_ZONE по стойке; ноги — ниже доли роста; руки — дальше
## от оси корпуса; остальное — грудь. Лёжа (и раненым) — голова или грудь.
func hit_zone(point: Vector3) -> String:
	var hz := float(Balance.HEAD_ZONE.get(_stance_key(), 99.0))
	var dy := point.y - global_position.y
	if dy >= hz:
		return "head"
	if health.downed or stance == Stance.PRONE:
		return "thorax"
	if dy < hz * float(Balance.ZONE_SHAPE.legs):
		return "legs"
	var d := point - global_position
	d.y = 0.0
	var f := Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))
	return "arms" if (d - f * d.dot(f)).length() > float(Balance.ZONE_SHAPE.arms_w) else "thorax"


## Что на себе, кг: рюкзак, карман, снаряжение (с обвесом, магазинами, плитами).
func carried_kg() -> float:
	if not loadout_mode or inventory == null:
		return 0.0
	var w := ItemDb.weight_of(inventory.items) + ItemDb.weight_of(inventory.pocket)
	for slot in inventory.equipment:
		w += ItemDb.entry_weight(inventory.equipment[slot])
	return w


## Перегруз: 0 до free_kg, 1 на max_kg.
func _over() -> float:
	var c: Dictionary = Balance.CARRY
	return clampf((carried_kg() - float(c.free_kg)) / (float(c.max_kg) - float(c.free_kg)), 0.0, 1.0)


func carry_speed_k() -> float:
	return lerpf(1.0, float(Balance.CARRY.speed_min), _over())


func carry_stamina_k() -> float:
	return lerpf(1.0, float(Balance.CARRY.stamina_max), _over())


## Открыто окно (рюкзак, лут, убежище, меню) — мышь и клавиши у окна, не у персонажа.
func ui_blocked() -> bool:
	if PauseMenu.shown or (Raid.current and Raid.current.ui_open()):
		return true
	for n in get_tree().get_nodes_in_group("esc_windows"):
		if n.has_method("is_open") and bool(n.call("is_open")):
			return true
	return false


func _can_sprint() -> bool:
	return not _winded and stamina > 0.0


## Бег тратит выносливость (в жару на улице — быстрее), стоишь или идёшь — восстанавливается.
func _tick_stamina(delta: float) -> void:
	var running := _can_sprint() and Input.is_action_pressed("sprint") and not aiming and stance == Stance.STAND \
		and Vector2(velocity.x, velocity.z).length() > Balance.PLAYER_WALK_SPEED + 0.3
	if running:
		var k := 1.0
		if String(RaidConditions.current.get("weather", "")) == "heat" and RaidAtmosphere.current and not RaidAtmosphere.current.is_indoor(global_position):
			k = Balance.STAMINA_HEAT
		# адреналин: дыхания хватает дольше
		k *= 1.0 - float(Balance.STRESS.adr_stamina) * stress_k()
		stamina = maxf(0.0, stamina - Balance.STAMINA_DRAIN * k * carry_stamina_k() * delta)
		_rest_t = Balance.STAMINA_REGEN_DELAY
		if stamina <= 0.0:
			_winded = true
			if _breath_sound == null:
				_breath_sound = Audio.start_loop("breath", self, -5.0)
	else:
		_rest_t -= delta
		if _rest_t <= 0.0:
			stamina = minf(Balance.STAMINA_MAX, stamina + Balance.STAMINA_REGEN * delta)
		if _winded and stamina >= Balance.STAMINA_RESUME:
			_winded = false
			if _breath_sound != null:
				_breath_sound.queue_free()
				_breath_sound = null


## Светит фонарём (фонарь на оружии в руках включён) — выдаёт издалека.
func has_light_on() -> bool:
	return light_on


## Насколько дальше видно светящего (мощный фонарь — дальше): наибольшее у включённых.
func light_view() -> float:
	var k := 1.0
	for m in weapon_mods:
		var md: Dictionary = weapon_mods[m] if weapon_mods[m] is Dictionary else {}
		if bool(md.get("light", false)):
			k = maxf(k, float((WeaponDb.attachment(String(md.get("id", ""))).get("light", {}) as Dictionary).get("view", 1.0)))
	return k


## Лежит раненым.
func is_downed() -> bool:
	return health.alive and health.downed


## Тащит раненого (стреляет только из пистолета, идёт медленно).
func is_dragging() -> bool:
	return Raid.current != null and Raid.current.drag_target_of(peer_id) != 0


## Тащит напарника или несёт раненого NPC — руки заняты.
func is_burdened() -> bool:
	return carrying or is_dragging()


func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()


func body_yaw() -> float:
	return _body.rotation.y


## Сесть (убежище): встать на место, повернуться, присесть; шаг или C — встать.
func sit(at: Vector3, yaw: float) -> void:
	seated = true
	global_position = at
	velocity = Vector3.ZERO
	_body.rotation.y = yaw
	stance = Stance.CROUCH
	_apply_stance()


func recoil() -> float:
	return _recoil


func recoil_h() -> float:
	return _recoil_h


func stance_key() -> String:
	return _stance_key()


## Запись оружия в слоте key (как есть у хоста / в песочнице, без состояния владельца).
func _base_entry(key: String) -> Dictionary:
	if key == "":
		return {}
	if loadout_mode:
		var e: Dictionary = inventory.equipment.get(key, {})
		if _pm_entries.has(key):
			var confirmed: Dictionary = _pm_entries[key]
			if String(e.get("id", "")) == String(confirmed.get("id", "")) and int(e.get("rev", 0)) < int(confirmed.get("rev", 0)):
				return confirmed
			_pm_entries.erase(key)
		return e if WeaponDb.is_weapon(String(e.get("id", ""))) else {}
	_ensure_sandbox()
	return sandbox_weapons.get(key, {})


func _ensure_sandbox() -> void:
	if not sandbox_weapons.is_empty():
		return
	var rng := RandomNumberGenerator.new()
	rng.seed = 1
	for p in WeaponDb.sandbox():
		sandbox_weapons[String(p)] = WeaponDb.make_weapon(String(p), rng, [100, 100])


## Песочница (тесты, витрина): обвес на ствол по ключу, точка → id.
func set_sandbox_mods(key: String, mods: Dictionary) -> void:
	_ensure_sandbox()
	if not sandbox_weapons.has(key):
		return
	var e: Dictionary = sandbox_weapons[key]
	var m := {}
	for mount in mods:
		m[String(mount)] = {"id": WeaponDb.canonical(String(mods[mount]))}
	e["mods"] = m
	Gear._bump(e)


## Запись оружия с состоянием владельца (патроны, износ, прицел, фонари и лазеры).
func entry_of(key: String) -> Dictionary:
	var base := _base_entry(key)
	if base.is_empty():
		return {}
	_ws_sync(key, base)
	var st: Dictionary = _ws[key]
	var e := base.duplicate(true)
	var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
	mag["rounds"] = int(st.rounds)
	mag["ammo"] = String(st.ammo)
	e["mag"] = mag
	if _has_chamber(String(e.id)):
		e["chamber"] = int(st.get("chamber", 0))
		e["chamber_ammo"] = String(st.get("chamber_ammo", ""))
	e["dur"] = float(st.dur)
	e["sight"] = String(st.sight)
	var mods: Dictionary = e.get("mods", {})
	for m in mods:
		var md: Dictionary = mods[m] if mods[m] is Dictionary else {"id": String(mods[m])}
		var t: Dictionary = (st.tac as Dictionary).get(m, {})
		md["light"] = bool(t.get("light", false))
		md["laser"] = bool(t.get("laser", false))
		mods[m] = md
	e["mods"] = mods
	return e


## Состояние владельца заводится из записи и перечитывается, если хозяин её поменял (ревизия:
## сменили магазин, обвес).
func _ws_sync(key: String, base: Dictionary) -> void:
	var rev := int(base.get("rev", 0))
	if _ws.has(key) and int(_ws[key].rev) == rev and String(_ws[key].id) == String(base.id):
		return
	var normalized: Dictionary = Gear.normalize_chamber(base)
	var mag: Dictionary = normalized.get("mag", {}) if normalized.get("mag") is Dictionary else {}
	var tac := {}
	var mods: Dictionary = base.get("mods", {})
	for m in mods:
		if mods[m] is Dictionary:
			tac[m] = {"light": bool((mods[m] as Dictionary).get("light", false)), "laser": bool((mods[m] as Dictionary).get("laser", false))}
	var jam := bool(_ws[key].get("jam", false)) if _ws.has(key) and String(_ws[key].id) == String(base.id) else false
	_ws[key] = {"id": String(base.id), "rev": rev, "rounds": int(mag.get("rounds", 0)), "ammo": String(mag.get("ammo", "")),
		"dur": float(base.get("dur", 100.0)), "sight": String(base.get("sight", "primary")), "tac": tac, "jam": jam,
		"chamber": int(normalized.get("chamber", 0)), "chamber_ammo": String(normalized.get("chamber_ammo", ""))}


static func _has_chamber(id: String) -> bool:
	return int(WeaponDb.weapon(id).get("chamber_capacity", 0)) > 0


func _state_rounds(key: String) -> int:
	var state: Dictionary = _ws.get(key, {})
	return int(state.get("rounds", 0)) + int(state.get("chamber", 0))


## Оружие в руках со своим состоянием.
func weapon_entry() -> Dictionary:
	return entry_of(weapon_slot)


## Характеристики оружия в руках (WeaponStats от экземпляра).
func spec() -> Dictionary:
	var entry: Dictionary = weapon_entry()
	return WeaponStats.compute(entry, String(entry.get("chamber_ammo", "")) if int(entry.get("chamber", 0)) > 0 else "")


func _weapon_sound(specification: Dictionary, slot: String) -> String:
	return String((specification.get("sounds", {}) as Dictionary).get(slot, ""))


func _play_weapon_sound(specification: Dictionary, slot: String, extra_db: float = 0.0) -> void:
	var kind := _weapon_sound(specification, slot)
	if kind != "":
		Audio.play(kind, global_position, extra_db)


## Состояние для хоста (Inventory.apply_weapon_state).
func _ws_state(key: String) -> Dictionary:
	var st: Dictionary = _ws.get(key, {})
	return {"id": String(st.get("id", "")), "rev": int(st.get("rev", 0)), "rounds": int(st.get("rounds", 0)), "dur": float(st.get("dur", 100.0)),
		"sight": String(st.get("sight", "primary")), "tac": (st.get("tac", {}) as Dictionary).duplicate(true),
		"chamber": int(st.get("chamber", 0)), "chamber_ammo": String(st.get("chamber_ammo", ""))}


func _send_ws(key: String) -> void:
	var h := items_host()
	if loadout_mode and h and _ws.has(key):
		h.call("request_weapon_state", key, _ws_state(key))
		_ws_dirty = false
	elif not loadout_mode:
		_ws_dirty = false


## Состояние оружия в руках — сразу тому, кто ведёт вещи (убежище: перед окном тайника).
func flush_weapon_state() -> void:
	if weapon_slot != "" and _ws.has(weapon_slot):
		_send_ws(weapon_slot)


## Кто ведёт вещи игрока: рейд (хост) или убежище (профиль) — одни и те же просьбы: перезарядка,
## состояние оружия, расход, сообщение (notify, request_reload, request_weapon_state, request_consume).
func items_host() -> Node:
	if Raid.current:
		return Raid.current
	return get_tree().get_first_node_in_group("hideout_level") if is_inside_tree() else null


## Сообщение внизу экрана — в рейде и в убежище.
func _say(text: String) -> void:
	var h := items_host()
	if h and h.has_method("notify"):
		h.call("notify", text)


## Снаряжение с состоянием оружия владельца — для профиля при эвакуации.
func equipment_state() -> Dictionary:
	var eq := inventory.equipment.duplicate(true)
	for key in ["primary", "secondary"]:
		if eq.has(key) and WeaponDb.is_weapon(String((eq[key] as Dictionary).get("id", ""))):
			eq[key] = entry_of(key)
	return eq


## Задержка у оружия в руках (устраняется R).
func is_jammed() -> bool:
	return bool((_ws.get(weapon_slot, {}) as Dictionary).get("jam", false))


func aim_progress() -> float:
	if not ads or not aiming or weapon_id == "" or spec().is_empty():
		return 0.0
	return clampf(_aim_t / float(spec().aim_time), 0.0, 1.0)


func eye_position() -> Vector3:
	return global_position + Vector3.UP * float(Balance.ADS_EYE[_stance_key()]) + lean_vector()


## Куда сдвинут глаз наклоном (вбок от взгляда, чуть ниже).
func lean_vector() -> Vector3:
	if absf(lean) < 0.001:
		return Vector3.ZERO
	# курс — по позе тела (синхронизируется), а не по взгляду: у хоста взгляда клиента нет
	var y := body_yaw()
	var right := Vector3(-cos(y), 0.0, sin(y))
	return right * lean * Balance.LEAN_OFFSET + Vector3.DOWN * absf(lean) * 0.08


## Направление взгляда в прицеле.
func look_dir() -> Vector3:
	return Vector3(sin(look_yaw) * cos(look_pitch), sin(look_pitch), cos(look_yaw) * cos(look_pitch))


## Вид от первого лица: своё тело и оружие в руках не рисуем (камера внутри капсулы),
## но тень оставляем — на полу видно, где стоишь.
func set_first_person(on: bool) -> void:
	var mode := GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if on else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	# своё тело от первого лица — на отдельном слое: тень от солнца и ламп есть, а свет «из глаз»
	# (ИК-подсветка ПНВ, фонарь в руках) его в тенях не видит — иначе перед камерой тень-прямоугольник
	var layer := OWN_BODY_LAYER if on and is_local() else 1
	for mi in _body.find_children("*", "MeshInstance3D", true, false):
		(mi as MeshInstance3D).cast_shadow = mode
		(mi as MeshInstance3D).layers = layer
	if _weapon_model:
		for mi in _weapon_model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).cast_shadow = mode
			(mi as MeshInstance3D).layers = layer


func _process(_delta: float) -> void:
	# эвакуирован (решает хост, видят все) — уходит из мира
	# ушёл из рейда (эвакуирован / не успел) — уходит из мира; дальше его здесь нет (раненый, которого
	# вынесли, не «умирает» у всех на виду, если у хоста его кровотечение ещё идёт)
	if Raid.current and Raid.current.has_left(peer_id):
		if is_in_group("players"):
			_leave_raid()
		return
	# взгляд вверх-вниз есть только от первого лица; в изометрии ствол — по горизонту
	if is_local() and not ads:
		look_pitch = 0.0
	if health.downed and not _was_downed:
		cancel_weapon_action()
	_was_downed = health.downed
	_update_hand()
	# смерть видна у всех peer: у хоста — по сигналу, у клиентов — по синхронизированному alive
	if not health.alive and _ragdoll == null and not _died_shown:
		_die()


func _physics_process(delta: float) -> void:
	if not is_local() or not is_alive():
		return
	if seated:
		var mv := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		if (mv.length() > 0.2 or Input.is_action_just_pressed("crouch")) and not ui_blocked():
			seated = false
			stance = Stance.STAND
			_apply_stance()
		else:
			velocity = Vector3.ZERO
			return
	# перелезает: тело идёт по дуге через преграду, ни стрельбы, ни шагов
	if _vault_t >= 0.0:
		_vault_t += delta / _vault_sec
		global_position = Vault.pos_at(_vault, minf(_vault_t, 1.0))
		velocity = Vector3.ZERO
		if _vault_t >= 1.0:
			_vault_t = -1.0
			if _vault_stumble:
				# запнулся: перевалился и растянулся за преградой
				_vault_stumble = false
				stance = Stance.PRONE
				_apply_stance()
				fire_timer = maxf(fire_timer, 0.8)
				NoiseBus.emit(global_position, float(Balance.VAULT.noise_m) * 1.5, "step")
				Audio.play("land", global_position, -6.0)
		return
	_dive_cd = maxf(0.0, _dive_cd - delta)
	# обвес в руках с фонарями/лазерами — модель у всех; горит ли — выдаёт
	if weapon_slot != "":
		var we := weapon_entry()
		if _pm_action.is_empty():
			ammo = _state_rounds(weapon_slot)
			weapon_rounds = ammo
		var mods: Dictionary = we.get("mods", {})
		if mods != weapon_mods:
			weapon_mods = mods
		var lit := false
		var las := false
		for m in mods:
			lit = lit or bool((mods[m] as Dictionary).get("light", false))
			las = las or bool((mods[m] as Dictionary).get("laser", false))
		if lit != light_on:
			light_on = lit
		if las != laser_on:
			laser_on = las
	_aim_t = _aim_t + delta if aiming and weapon_id != "" else 0.0
	# наклон: Q/E только когда камера в глазах; в изометрии Q/E крутят камеру
	var lean_to := Input.get_axis("camera_left", "camera_right") if ads and not PauseMenu.shown else 0.0
	lean = move_toward(lean, lean_to, Balance.LEAN_SPEED * delta)
	var down := is_downed()
	if down:
		# раненый лежит; X (держать) — сдаться
		if stance != Stance.PRONE:
			stance = Stance.PRONE
			_apply_stance()
		aiming = Input.is_action_pressed("aim") and not ui_blocked()
		_give_up_t = _give_up_t + delta if Input.is_action_pressed("drag") and not PauseMenu.shown else 0.0
		if _give_up_t >= Balance.GIVE_UP_SEC and Raid.current:
			_give_up_t = -INF
			Raid.current.request_give_up()
	else:
		_give_up_t = 0.0
		_read_stance()
		if not ui_blocked() and not PauseMenu.shown:
			if Input.is_action_just_pressed("vault"):
				_try_vault()
				if _vault_t >= 0.0:
					return
			if Input.is_action_just_pressed("dive"):
				_try_dive()
	_combat(delta)
	var dragger: Player = Raid.current.dragger_of(peer_id) if down and Raid.current else null
	if dragger:
		# тащат: тело — на «верёвке» за тем, кто тащит
		var off := global_position - dragger.global_position
		off.y = 0.0
		if off.length() < 0.05:
			off = -Vector3(sin(dragger.body_yaw()), 0.0, cos(dragger.body_yaw()))
		var goal := dragger.global_position + off.normalized() * Balance.DRAG_DIST
		var pull := (goal - global_position) / maxf(delta, 0.001)
		velocity.x = clampf(pull.x, -6.0, 6.0)
		velocity.z = clampf(pull.z, -6.0, 6.0)
	elif _dive_t >= 0.0:
		# бросок: рывок в сторону, к концу гаснет
		var dv: Dictionary = Balance.DIVE
		_dive_t += delta
		var k := 1.0 - 0.6 * clampf(_dive_t / float(dv.sec), 0.0, 1.0)
		velocity.x = _dive_dir.x * float(dv.speed) * k
		velocity.z = _dive_dir.z * float(dv.speed) * k
		if _dive_t >= float(dv.sec):
			_dive_t = -1.0
	else:
		var wish := _wish_direction()
		var speed := _stance_speed()
		var target := wish * speed
		var horizontal := Vector2(velocity.x, velocity.z)
		var target_horizontal := Vector2(target.x, target.z)
		# Тормозим отдельным темпом не только без ввода, но и при сбросе спринта или развороте.
		# Векторное приближение даёт одинаковый разгон по прямой и диагонали.
		var has_input := target_horizontal.length_squared() > 0.0001
		var reversing := has_input and horizontal.length_squared() > 0.0001 \
			and horizontal.dot(target_horizontal) < 0.0
		var slowing := has_input and horizontal.length() > target_horizontal.length() + 0.01
		var rate := Balance.PLAYER_DECEL if not has_input or reversing or slowing else Balance.PLAYER_ACCEL
		horizontal = horizontal.move_toward(target_horizontal, rate * delta)
		velocity.x = horizontal.x
		velocity.z = horizontal.y
	if not is_on_floor():
		velocity.y -= ProjectSettings.get_setting("physics/3d/default_gravity") * delta
	elif not (_dive_t >= 0.0 and _dive_t < 0.1):
		# в начале броска — подскок (иначе пол тут же гасит его)
		velocity.y = 0.0
	move_and_slide()
	if ads:
		_body.rotation.y = look_yaw
	elif _dive_t >= 0.0:
		_body.rotation.y = atan2(_dive_dir.x, _dive_dir.z)
	else:
		_face_cursor(delta)
	_footsteps(delta)
	_tick_stamina(delta)
	_tick_stress(delta)
	_recoil = move_toward(_recoil, 0.0, Balance.RECOIL_RETURN * _recoil * delta + 0.02 * delta)
	_recoil_h = move_toward(_recoil_h, 0.0, Balance.RECOIL_RETURN * absf(_recoil_h) * delta + 0.01 * delta)
	_bloom = move_toward(_bloom, 0.0, Balance.RECOIL_BLOOM_DECAY * delta)
	kick_vis = move_toward(kick_vis, 0.0, 9.0 * kick_vis * delta + 0.2 * delta)
	_body.rotation.x = -_recoil * 0.4


## Отдача выстрела: подброс и увод вбок. В прицеле невозвращаемая доля уходит во взгляд навсегда
## (очередь ползёт вверх — тяни вниз), возвращаемая — временно; от бедра — раскачка разброса.
func _apply_recoil(spec: Dictionary, braced: bool, rig: CameraRig) -> void:
	var k := float(spec.braced_kick) if braced else 1.0
	var in_ads := ads and aiming
	if in_ads:
		k *= Balance.ADS_RECOIL_SCALE
	var kv := float(spec.kick) * k * _rng.randf_range(0.85, 1.15)
	var rise := kv * (Balance.ADS_RECOIL_RISE_SCALE if in_ads else 1.0)
	var kh := float(spec.get("kick_h", 0.0)) * k * (_rng.randf_range(-1.0, 1.0) + float(spec.get("kick_bias", 0.0)))
	if in_ads:
		kh *= Balance.ADS_RECOIL_HORIZONTAL_SCALE
	var back := float(spec.get("recover", 0.5))
	if ads and rig:
		rig.add_recoil(rise * (1.0 - back), kh * (1.0 - back))
		_recoil += rise * back
		_recoil_h += kh * back
	else:
		_recoil += rise
	_bloom += kv * Balance.RECOIL_BLOOM
	# толчок модели в руках; в прицеле подскок и откат масштабирует CameraRig (ADS_RECOIL_FLIP / BACK)
	kick_vis += clampf(kv / 0.05, 0.3, 1.8)


## Оружие — в правой руке модели (кость руки, CharacterAnimator.weapon_grip): идёт за руками
## в любой позе — ходьба, бег, присед, лёжа, перезарядка. Без модели Persona — у груди, как раньше.
func _update_hand() -> void:
	var key := weapon_id + str(weapon_mods)
	var h := float(Balance.STANCE_HEIGHT[_stance_key()]) / float(Balance.STANCE_HEIGHT.stand)
	var yaw := _body.rotation.y
	if _weapon_model_id != key:
		if _weapon_model:
			_weapon_model.queue_free()
		_weapon_model = WeaponModels.build(weapon_id, weapon_mods, 1) if weapon_id != "" else Node3D.new()
		var family := String(WeaponDb.weapon(weapon_id).get("model", "rifle")) if weapon_id != "" else "rifle"
		var grip: Node3D = _animator.weapon_grip(family, weapon_id) if _animator else null
		(grip if grip else _hand).add_child(_weapon_model)
		_weapon_rig = WeaponRig.find_on(_weapon_model)
		if _weapon_rig:
			_weapon_rig.set_ammo_state(weapon_rounds)
			_weapon_rig.sound_event.connect(_rig_sound)
		_weapon_model_id = key
		# фонари и лазеры смотрят туда, куда целится игрок, а не куда анимация повернула ствол:
		# запоминаем их поворот внутри модели оружия
		_aimed.clear()
		for n in _weapon_model.find_children("*", "Node3D", true, false):
			if n is SpotLight3D or String(n.name).begins_with("LaserBeam"):
				n.set_meta("aim_rel", _weapon_model.global_basis.orthonormalized().inverse() * (n as Node3D).global_basis)
				_aimed.append(n as Node3D)
		if ads:
			set_first_person(true)
	_hand.visible = health.alive
	_weapon_model.visible = health.alive
	if _weapon_rig and not _weapon_rig.is_busy():
		_weapon_rig.set_ammo_state(weapon_rounds)
	# фонари и лазеры — каждый по своему состоянию; от первого лица у себя светит модель в руках
	# (CameraRig) — там, куда смотрит ствол
	for n in _weapon_model.find_children("Flashlight*", "SpotLight3D", true, false):
		(n as SpotLight3D).visible = tac_on(weapon_mods, n, "light") and not (ads and is_local())
	for n in _weapon_model.find_children("LaserBeam*", "Node3D", true, false):
		(n as Node3D).visible = tac_on(weapon_mods, n, "laser") and not (ads and is_local())
	_hand.position = Basis(Vector3.UP, yaw) * Vector3(-0.17, 1.24 * h, 0.24)
	# прицельная ось: куда смотрит игрок, и вверх-вниз (look_pitch синхронизируется)
	_hand.rotation = Vector3(-_recoil - look_pitch, yaw, 0.0)
	var aim := _hand.global_basis.orthonormalized()
	for n in _aimed:
		if is_instance_valid(n):
			n.global_basis = aim * (n.get_meta("aim_rel") as Basis)


## Включён ли фонарь / лазер (kind: light / laser) того узла модели (meta "mount") по обвесу mods.
static func tac_on(mods: Dictionary, node: Node, kind: String) -> bool:
	var m := String(node.get_meta("mount", ""))
	return mods.has(m) and mods[m] is Dictionary and bool((mods[m] as Dictionary).get(kind, false))


## Шаги слышны AI: радиус по стойке и бегу, только пока реально движемся.
func _footsteps(delta: float) -> void:
	var moving := Vector2(velocity.x, velocity.z).length() > 0.3
	if not moving:
		_step_timer = 0.0
		return
	_step_timer -= delta
	if _step_timer > 0.0:
		return
	_step_timer = Balance.NOISE_STEP_INTERVAL
	var key := _stance_key()
	if key == "stand" and Input.is_action_pressed("sprint") and not aiming:
		key = "sprint"
	# звук шагов — Footsteps (слышен у всех peer); здесь — шум, по которому слышат мародёры
	NoiseBus.emit(global_position, float(Balance.NOISE_STEP[key]), "step")


## Хост сообщил: мародёр убит моей пулей — метка убийства (у клиента смерть видна позже выстрела).
func show_kill_marker() -> void:
	if is_local() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).show_hitmarker(true)


## Стрельба, перезарядка на R, смена оружия 1–4, граната G.
func _combat(delta: float) -> void:
	if PauseMenu.shown:
		return
	fire_timer -= delta
	# открыт рюкзак/обыск — клики идут в кнопки, не в спуск
	if not combat_enabled or ui_blocked():
		_cancel_nade_aim()
		return
	if loadout_mode:
		_loadout_tick()
	var keys := weapon_keys()
	for i in range(keys.size()):
		if Input.is_action_just_pressed("weapon_%d" % (i + 1)) and String(keys[i]) != "" and String(keys[i]) in allowed_weapons():
			_switch(String(keys[i]))
	# лёжа раненым и таща раненого — только пистолет (нет — руки пусты, гранаты можно)
	if not loadout_mode and weapon_slot == "" and not _sandbox_picked:
		# песочница: сразу в руках пистолет (клавиша 2), как было всегда
		_sandbox_picked = true
		_switch(sidearm_key() if sidearm_key() != "" else String(keys[0]), false)
	if not weapon_slot in allowed_weapons() and weapon_slot != "":
		var pistol := String(allowed_weapons()[0]) if not allowed_weapons().is_empty() else ""
		_switch(pistol, pistol != "")
	# граната: держишь G — видно, куда упадёт и где достанет; отпустил — бросок
	if Input.is_action_just_pressed("grenade"):
		if grenade_count() > 0:
			_nade_aiming = true
		elif loadout_mode:
			_say("Гранат нет")
	if _nade_aiming:
		if Input.is_action_pressed("grenade"):
			_show_nade_aim()
		else:
			_cancel_nade_aim()
			if grenade_count() > 0 and fire_timer <= 0.0:
				_throw_grenade()
	for pair in [["throw_flare", "flare"], ["throw_chem", "chemlight"]]:
		if Input.is_action_just_pressed(String(pair[0])) and fire_timer <= 0.0:
			_throw_light(String(pair[1]))
	_tick_nvg(delta)
	if weapon_id == "":
		return
	if Input.is_action_just_pressed("flashlight"):
		_toggle_tac("light")
	if Input.is_action_just_pressed("laser"):
		_toggle_tac("laser")
	if Input.is_action_just_pressed("toggle_sight"):
		_toggle_sight()
	var spec := spec()
	if InputMap.has_action("toggle_suppressor") and Input.is_action_just_pressed("toggle_suppressor"):
		toggle_suppressor()
	if not _pm_action.is_empty() and String(_pm_action.kind) == "suppressor":
		_tick_suppressor(delta)
		return
	_ws_sync_t -= delta
	if _ws_dirty and _ws_sync_t <= 0.0:
		_send_ws(weapon_slot)
	if reload_timer > 0.0:
		reload_timer -= delta
		if reload_timer <= 0.0:
			_finish_reload(spec)
		return
	ammo_check_t = maxf(0.0, ammo_check_t - delta)
	# R: коротко — перезарядка (или устранить задержку), держать — проверить патроны
	if Input.is_action_just_pressed("reload"):
		_reload_hold = 0.0
	if _reload_hold >= 0.0:
		if Input.is_action_pressed("reload"):
			_reload_hold += delta
			if _reload_hold >= float(Balance.AMMO_CHECK.hold_sec):
				_reload_hold = -1.0
				_check_ammo(spec)
			return
		_reload_hold = -1.0
		if is_jammed():
			_start_clear(spec)
		elif ammo < int(spec.mag) + (1 if _has_chamber(weapon_id) else 0):
			_start_reload(spec)
		return
	var trigger := Input.is_action_pressed("fire") if bool(spec.auto) else Input.is_action_just_pressed("fire")
	if trigger and fire_timer <= 0.0:
		if is_jammed():
			fire_timer = 0.3
			_play_weapon_sound(spec, "jam", -8.0)
			return
		if ammo <= 0:
			fire_timer = float(spec.interval)
			_play_weapon_sound(spec, "dry_fire", -8.0)
			_start_reload(spec)
			return
		_fire(spec)


## Перезарядка: в снаряжении — смена магазина из рюкзака или досыпка россыпью (делает хост,
## Inventory.reload_slot); в песочнице — полный магазин.
func _start_reload(spec: Dictionary) -> void:
	if not _pm_action.is_empty() or reload_timer > 0.0 or weapon_id == "":
		return
	_reload_kind = "full"
	_reload_slot = weapon_slot
	_reload_empty = ammo <= 0
	var t: float = float(spec.get("reload_empty", spec.reload)) if _reload_empty else float(spec.reload)
	var chambered: bool = _has_chamber(weapon_id)
	# Потраченные выстрелами патроны сохраняем до анимации: её отмена не возвращает боезапас.
	if chambered and _ws_dirty:
		_send_ws(weapon_slot)
	if loadout_mode:
		var e := weapon_entry()
		var kind := Gear.reload_kind(e, inventory.items)
		if kind == "":
			_say("Нечем зарядить: " + WeaponDb.caliber_name(String(spec.caliber)))
			return
		_reload_kind = kind
		_reload_rev = int(e.get("rev", 0))
		_reload_wait = 1.5
		var st := _ws_state(weapon_slot)
		# под сильным стрессом старый магазин выскальзывает на землю (редко)
		var sc: Dictionary = Balance.STRESS
		var mag: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
		if not chambered and kind == "swap" and String(mag.get("id", "")) != "" and _fumble_cd <= 0.0 and stress >= float(sc.fumble_from) 				and _rng.randf() < float(sc.fumble_chance) * _stress_over(float(sc.fumble_from)):
			st["fumble"] = true
			_fumble_cd = float(sc.fumble_cd)
			t += float(sc.fumble_sec)
			_say("Магазин выскользнул из рук — лежит под ногами")
			_play_weapon_sound(spec, "mag_drop")
		var h := items_host()
		if h and not chambered:
			h.call("request_reload", weapon_slot, st)
			_ws_dirty = false
		# досыпать россыпью в отстёгиваемый магазин — дольше, чем сменить
		if kind == "topup" and not WeaponDb.weapon(weapon_id).has("internal_mag"):
			t *= Balance.RELOAD_TOPUP_K
	# руки дрожат — дольше
	reload_timer = t * (1.0 + float(Balance.STRESS.reload_k) * stress_k())
	_animation_event("pistol_reload" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_reload")
	if chambered:
		_pm_action_seq += 1
		_pm_action = {"kind": "reload", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
			"state": _ws_state(weapon_slot), "empty": _reload_empty, "sent": false}
		_weapon_action("reload", _reload_empty, reload_timer)
	if _weapon_rig:
		return
	Audio.play(String(spec.reload_sound), global_position)
	if _weapon_sound(spec, "breech_open") != "":
		_play_weapon_sound(spec, "breech_open", -4.0)
	elif _weapon_sound(spec, "mag_out") != "":
		_play_weapon_sound(spec, "mag_out", -4.0)
	else:
		_play_weapon_sound(spec, "round_insert", -4.0)


## Задержка: передёрнуть (R) — патроны не тратятся.
func _start_clear(spec: Dictionary) -> void:
	_reload_kind = "clear"
	_reload_slot = weapon_slot
	reload_timer = float(Balance.WEAPON_WEAR.clear_sec)
	_play_weapon_sound(spec, "clear_jam", -4.0)


func _finish_reload(spec: Dictionary) -> void:
	if _has_chamber(weapon_id) and _reload_kind != "clear":
		_commit_pm_action()
		return
	if _reload_kind == "clear":
		if _ws.has(_reload_slot):
			_ws[_reload_slot].jam = false
		_ws_dirty = true
		return
	if not loadout_mode:
		if _ws.has(_reload_slot):
			_ws[_reload_slot].rounds = int(spec.mag)
			_ws[_reload_slot].jam = false
		ammo = int(spec.mag)
		_finish_reload_sounds(spec)
		return
	# хост поменял запись (ревизия выросла) — состояние перечитается; ответ ещё в пути — подождать
	var base := _base_entry(_reload_slot)
	if int(base.get("rev", 0)) == _reload_rev and _reload_wait > 0.0:
		_reload_wait -= 0.1
		reload_timer = 0.1
		return
	entry_of(_reload_slot)
	if _ws.has(_reload_slot):
		_ws[_reload_slot].jam = false
	if _reload_slot == weapon_slot:
		ammo = _state_rounds(weapon_slot)
	_finish_reload_sounds(spec)


func _finish_reload_sounds(specification: Dictionary) -> void:
	if _weapon_sound(specification, "breech_close") != "":
		_play_weapon_sound(specification, "breech_close", -4.0)
		return
	_play_weapon_sound(specification, "mag_in", -4.0)
	_play_weapon_sound(specification, "charge", -5.0)


## Только единственный риг модели на теле озвучивает действие — модель перед камерой молчит.
func _rig_sound(slot: String) -> void:
	if not health.alive or weapon_id == "":
		return
	_play_weapon_sound(spec() if is_local() else WeaponStats.compute({"id": weapon_id, "mods": weapon_mods}), slot, float(Balance.PM_ACTION.sound_db))


## Одно событие приводит обе модели к одинаковой фазе; у чужого игрока работает тот же WeaponRig.
func _weapon_action(action: String, flag: bool = false, duration: float = 0.0, rounds: int = -1, replicate: bool = true) -> void:
	if _weapon_rig:
		match action:
			"shot":
				_weapon_rig.play_shot(rounds)
			"reload":
				_weapon_rig.play_reload(flag, duration)
			"finish_reload":
				_weapon_rig.finish_reload(rounds)
			"suppressor":
				_weapon_rig.play_suppressor(flag, duration)
			"suppressed":
				_weapon_rig.set_suppressed(flag)
			"cancel":
				_weapon_rig.cancel_action()
	if is_local() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).weapon_action(action, flag, duration, rounds)
	if replicate and Net.is_networked() and is_multiplayer_authority():
		_rpc_weapon_action.rpc(action, flag, duration, rounds)


@rpc("authority", "call_remote", "reliable")
func _rpc_weapon_action(action: String, flag: bool, duration: float, rounds: int) -> void:
	_update_hand()
	if rounds >= 0:
		weapon_rounds = rounds
	_weapon_action(action, flag, duration, rounds, false)


## Клавиша K (переназначается): в ходе действия оружие занято, предметы пока остаются на месте.
func toggle_suppressor() -> bool:
	if weapon_id == "" or not health.alive or is_downed() or reload_timer > 0.0 or not _pm_action.is_empty():
		return false
	var entry: Dictionary = weapon_entry()
	if not WeaponDb.mounts_of(weapon_id).has("muzzle"):
		_say("На оружии нет крепления глушителя")
		return false
	var mods: Dictionary = entry.get("mods", {})
	var mounted: String = WeaponDb.mod_id(mods.get("muzzle", {}))
	var remove: bool = bool((WeaponDb.attachment(mounted).get("fx", {}) as Dictionary).get("suppressed", false))
	if mounted != "" and not remove:
		_say("Сначала снимите дульную насадку")
		return false
	if not remove:
		var found: bool = false
		for rec: Dictionary in inventory.items:
			var iid: String = String(rec.id)
			if bool((WeaponDb.attachment(iid).get("fx", {}) as Dictionary).get("suppressed", false)) and WeaponDb.attach_block(entry, "muzzle", iid) == "":
				found = true
				break
		if not found:
			_say("В рюкзаке нет подходящего глушителя")
			return false
	if _ws_dirty:
		_send_ws(weapon_slot)
	_pm_action_seq += 1
	var duration: float = float(Balance.PM_ACTION.suppressor_sec)
	_pm_action = {"kind": "suppressor", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
		"state": _ws_state(weapon_slot), "install": not remove, "remaining": duration, "sent": false}
	_weapon_action("suppressor", not remove, duration)
	return true


func _tick_suppressor(delta: float) -> void:
	_pm_action.remaining = float(_pm_action.remaining) - delta
	if float(_pm_action.remaining) <= 0.0:
		_commit_pm_action()


## Прерывание до подтверждения не трогает инвентарь; уже подтверждённый перенос остаётся целым.
func cancel_weapon_action() -> void:
	var had_action: bool = not _pm_action.is_empty() or reload_timer > 0.0 or (_weapon_rig and _weapon_rig.is_busy())
	_pm_action.clear()
	reload_timer = 0.0
	_reload_hold = -1.0
	_reload_kind = ""
	_reload_slot = ""
	if _weapon_rig:
		_weapon_rig.set_ammo_state(weapon_rounds)
	if had_action:
		_weapon_action("cancel", false, 0.0, weapon_rounds)


func _commit_pm_action() -> void:
	if _pm_action.is_empty():
		return
	if bool(_pm_action.get("sent", false)):
		reload_timer = float(Balance.PM_ACTION.host_poll_sec) if String(_pm_action.kind) == "reload" else 0.0
		return
	_pm_action.sent = true
	var request: Dictionary = _pm_action.duplicate(true)
	if Net.is_networked() and not multiplayer.is_server() and Net.scene_of(self) != "hideout":
		_rpc_pm_commit.rpc_id(1, request)
		# Остальные игроки продолжают видеть последний кадр действия до атомарного ответа хоста.
		if String(request.kind) == "reload":
			reload_timer = float(Balance.PM_ACTION.host_poll_sec)
	else:
		var result: Dictionary = _host_pm_commit(request)
		_accept_pm_result(int(request.seq), result)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_pm_commit(request: Dictionary) -> void:
	if not multiplayer.is_server() or multiplayer.get_remote_sender_id() != peer_id:
		return
	var result: Dictionary = _host_pm_commit(request)
	_rpc_pm_result.rpc_id(peer_id, int(request.get("seq", -1)), result)


## Проверяем намерение и ревизию на хосте: повторное или устаревшее действие ничего не расходует.
func _host_pm_commit(request: Dictionary) -> Dictionary:
	if Net.is_networked() and not multiplayer.is_server() and Net.scene_of(self) != "hideout":
		return {"error": "Операция доступна только хосту"}
	var sequence: int = int(request.get("seq", -1))
	if sequence <= _pm_host_seq:
		return {"error": "Действие уже обработано"}
	_pm_host_seq = sequence
	if not health.alive or is_downed():
		return {"error": "Действие прервано ранением"}
	var slot: String = String(request.get("slot", ""))
	var wid: String = String(request.get("id", ""))
	var state: Dictionary = request.get("state", {})
	var base: Dictionary = _base_entry(slot)
	if String(base.get("id", "")) != wid or int(base.get("rev", 0)) != int(state.get("rev", -1)):
		return {"error": "Оружие уже изменилось"}
	var kind: String = String(request.get("kind", ""))
	if kind == "reload":
		if not _has_chamber(wid):
			return {"error": "У оружия другая схема перезарядки"}
		if loadout_mode:
			var h: Node = items_host()
			if Net.scene_of(self) == "hideout" and h and h.has_method("request_reload"):
				h.call("request_reload", slot, state)
			else:
				var result: Array = inventory.reload_slot(slot, state)
				if String(result[0]) == "":
					return {"error": "Нечем перезарядить"}
				var spill: Dictionary = result[1]
				if not spill.is_empty():
					if Raid.current:
						Raid.current.spawn_drop(global_position, "Выброшено", [spill], LootContainer.Look.BAG)
					else:
						# Стенд без мира рейда сохраняет вынутый магазин в буфере.
						inventory.buffer = inventory.buffer + [spill]
		else:
			var fresh: Dictionary = Gear.normalize_chamber(base)
			var mag: Dictionary = fresh.get("mag", {})
			mag["rounds"] = WeaponDb.capacity(fresh)
			fresh["mag"] = mag
			fresh["chamber"] = int(state.get("chamber", 0))
			fresh["chamber_ammo"] = String(state.get("chamber_ammo", ""))
			Gear.chamber_round(fresh)
			Gear._bump(fresh)
			sandbox_weapons[slot] = fresh
	elif kind == "suppressor":
		var error: String
		if loadout_mode:
			error = inventory.toggle_suppressor(slot, state, bool(request.get("install", false)), wid)
		else:
			error = _sandbox_suppressor(slot, bool(request.get("install", false)))
		if error != "":
			return {"error": error}
	else:
		return {"error": "Неизвестное действие"}
	return {"error": "", "entry": _base_entry(slot).duplicate(true), "slot": slot, "kind": kind}


func _sandbox_suppressor(slot: String, install: bool) -> String:
	var entry: Dictionary = sandbox_weapons[slot]
	var list: Array = inventory.items.duplicate(true)
	var updated: Dictionary
	if not install:
		var removed: Array = Gear.strip(entry, "mod:muzzle")
		if (removed[1] as Dictionary).is_empty() or ItemDb.add_to(list, removed[1], Balance.BACKPACK_GRID) == 0:
			return "В рюкзаке нет места для глушителя"
		updated = removed[0]
	else:
		var chosen: int = -1
		for idx: int in range(list.size()):
			var iid: String = String((list[idx] as Dictionary).id)
			if bool((WeaponDb.attachment(iid).get("fx", {}) as Dictionary).get("suppressed", false)) and WeaponDb.attach_block(entry, "muzzle", iid) == "":
				chosen = idx
				break
		if chosen < 0:
			return "В рюкзаке нет подходящего глушителя"
		var fitted: Array = Gear.fit(entry, list[chosen], "muzzle")
		if String(fitted[2]) != "" or not (fitted[1] as Dictionary).is_empty():
			return "Дульная насадка уже установлена"
		ItemDb.remove_at(list, chosen, 1)
		updated = fitted[0]
	sandbox_weapons[slot] = updated
	inventory.items = list
	return ""


@rpc("any_peer", "call_remote", "reliable")
func _rpc_pm_result(sequence: int, result: Dictionary) -> void:
	if multiplayer.get_remote_sender_id() == 1:
		_accept_pm_result(sequence, result)


func _accept_pm_result(sequence: int, result: Dictionary) -> void:
	# Даже если владелец уже сменил оружие, подтверждённая запись нужна при следующем выборе.
	var entry: Dictionary = result.get("entry", {})
	var slot: String = String(result.get("slot", ""))
	if not entry.is_empty():
		if loadout_mode:
			_pm_entries[slot] = entry
		else:
			sandbox_weapons[slot] = entry
		_ws.erase(slot)
		entry_of(slot)
	if _pm_action.is_empty() or int(_pm_action.seq) != sequence:
		return
	var action: String = String(_pm_action.kind)
	_pm_action.clear()
	reload_timer = 0.0
	var error: String = String(result.get("error", ""))
	if error != "":
		_say(error)
		_weapon_action("cancel", false, 0.0, weapon_rounds)
		return
	ammo = _state_rounds(weapon_slot)
	weapon_rounds = ammo
	weapon_mods = (weapon_entry().get("mods", {}) as Dictionary).duplicate(true)
	if _ws.has(weapon_slot):
		_ws[weapon_slot].jam = false
	if action == "reload":
		_weapon_action("finish_reload", false, 0.0, ammo)
	else:
		_weapon_action("suppressed", bool(spec().get("suppressed", false)))
		_weapon_action("cancel", false, 0.0, ammo)
	_send_ws(weapon_slot)


## T / L: все фонари (kind light) или лазеры (laser) на оружии в руках — вкл/выкл разом.
func _toggle_tac(kind: String) -> void:
	var e := weapon_entry()
	var mods: Dictionary = e.get("mods", {})
	var mounts: Array = []
	var any_on := false
	for m in mods:
		if WeaponDb.attachment(WeaponDb.mod_id(mods[m])).has(kind):
			mounts.append(m)
			any_on = any_on or bool((mods[m] as Dictionary).get(kind, false))
	if mounts.is_empty():
		_say("Нет фонаря на оружии" if kind == "light" else "Нет ЛЦУ на оружии")
		return
	var st: Dictionary = _ws[weapon_slot]
	for m in mounts:
		var t: Dictionary = (st.tac as Dictionary).get(m, {})
		t[kind] = not any_on
		st.tac[m] = t
	Audio.play("tac_click", global_position, -14.0)
	_say(("Фонарь: " if kind == "light" else "ЛЦУ: ") + ("выкл" if any_on else "вкл"))
	_send_ws(weapon_slot)


## O или СКМ от первого лица: основной ↔ угловой прицел (если стоят оба). Прицеливание не
## сбрасывается — камера переводит линию прицеливания прямо (CameraRig, SIGHT_SWITCH_SEC).
func toggle_sight() -> void:
	_toggle_sight()


func _toggle_sight() -> void:
	var e := weapon_entry()
	var sights := WeaponStats.sights_of(e)
	if sights.size() < 2:
		return
	var cur := WeaponStats.active_sight(e)
	var nxt := String(sights[(sights.find(cur) + 1) % sights.size()])
	_ws[weapon_slot].sight = nxt
	var mount := "optic_" + nxt
	var name := ItemDb.item_name(WeaponDb.mod_id((e.mods as Dictionary).get(mount, ""))) if (e.mods as Dictionary).has(mount) else "штатный"
	_say(("Основной: " if nxt == "primary" else "Угловой: ") + name)
	Audio.play("sight_switch", global_position, -16.0)
	_send_ws(weapon_slot)


## Клавиши 1…: в песочнице — стволы песочницы (автомат, пистолет, дробовик, винтовка), со
## снаряжением — [основное, пистолет] (слоты; "" — пусто).
func weapon_keys() -> Array:
	if not loadout_mode:
		return WeaponDb.sandbox()
	return ["primary" if inventory.slot_weapon("primary") != "" else "", "secondary" if inventory.slot_weapon("secondary") != "" else ""]


## Ключ пистолета (клавиша 2): раненым и таща раненого — только он; "" — пистолета нет.
func sidearm_key() -> String:
	if loadout_mode:
		return "secondary" if inventory.slot_weapon("secondary") != "" else ""
	for k in WeaponDb.sandbox():
		if String(WeaponDb.weapon(String(k)).get("class", "")) == "PISTOL":
			return String(k)
	return ""


func grenade_count() -> int:
	return inventory.count("grenade") if loadout_mode else grenades


## Что можно держать сейчас: раненым и таща раненого — только пистолет.
func allowed_weapons() -> Array:
	var keys := weapon_keys()
	if is_downed() or is_burdened():
		return [sidearm_key()] if sidearm_key() != "" else []
	return keys.filter(func(k: Variant) -> bool: return String(k) != "")


## Россыпь патронов к оружию в руках в рюкзаке + патроны в снаряжённых магазинах (HUD); -1 — без счёта.
## Проверка патронов (держать R): у пистолетов и болтовок — точно, у остальных — словами.
func _check_ammo(spec: Dictionary) -> void:
	ammo_check_text = Gear.ammo_estimate(ammo, int(spec.mag), Gear.exact_count(weapon_id))
	ammo_check_t = float(Balance.AMMO_CHECK.show_sec)
	_play_weapon_sound(spec, "mag_check", -12.0)
	if is_local():
		_say("Магазин: " + ammo_check_text)


## Запасных магазинов к оружию в руках в рюкзаке (сколько в них патронов — не видно).
func spare_mags() -> int:
	var n := 0
	for it in inventory.items:
		if it.has("rounds") and WeaponDb.mag_fits(weapon_id, String(it.id)):
			n += 1
	return n


## Россыпью в рюкзаке патронов этого калибра.
func loose_rounds() -> int:
	var cal := String(WeaponDb.weapon(weapon_id).get("caliber", ""))
	var n := 0
	for it in inventory.items:
		if not it.has("rounds") and String(WeaponDb.ammo(String(it.id)).get("caliber", "")) == cal:
			n += int(it.n)
	return n


func ammo_reserve() -> int:
	if not loadout_mode or weapon_id == "":
		return -1
	var cal := String(WeaponDb.weapon(weapon_id).get("caliber", ""))
	var n := 0
	for it in inventory.items:
		if it.has("rounds") and WeaponDb.mag_fits(weapon_id, String(it.id)):
			n += int(it.rounds)
		elif String(WeaponDb.ammo(String(it.id)).get("caliber", "")) == cal:
			n += int(it.n)
	return n


## Снаряжение: в руках только то, что надето (основное, иначе пистолет).
func _loadout_tick() -> void:
	if not inventory.loadout_ready:
		return
	# в слоте теперь другое оружие (сменили в окне) — взять его в руки
	if weapon_slot != "" and weapon_id != String(_base_entry(weapon_slot).get("id", "")) and not _base_entry(weapon_slot).is_empty():
		var k := weapon_slot
		weapon_slot = ""
		_switch(k, false)
	var keys := weapon_keys()
	if is_downed() or is_burdened():
		# раненым / таща раненого — только пистолет (выбирает _combat)
		return
	if weapon_slot == "" or not weapon_slot in keys or _base_entry(weapon_slot).is_empty():
		# оружие пропало из рук (сменил/не было) — берём основное, иначе пистолет
		var pick := String(keys[0]) if String(keys[0]) != "" else String(keys[1])
		if pick != weapon_slot or _base_entry(weapon_slot).is_empty():
			_switch(pick, false)


## Смена оружия: состояние прежнего уходит хосту, перезарядка прерывается.
func _switch(key: String, sound: bool = true) -> void:
	if key == weapon_slot and weapon_id != "" and not _base_entry(key).is_empty():
		return
	cancel_weapon_action()
	if weapon_slot != "" and _ws.has(weapon_slot):
		_send_ws(weapon_slot)
	if sound and weapon_id != "":
		_play_weapon_sound(spec(), "holster", -6.0)
	weapon_slot = key
	var e := entry_of(key)
	weapon_id = String(e.get("id", ""))
	ammo = Gear.total_rounds(e)
	weapon_rounds = ammo
	reload_timer = 0.0
	_aim_t = 0.0
	fire_timer = 0.35
	if sound and weapon_id != "":
		_play_weapon_sound(spec(), "draw", -6.0)
		_animation_event("pistol_draw" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_draw")


func _fire(spec: Dictionary) -> void:
	if String(WeaponDb.weapon(weapon_id).get("class", "")) != "PISTOL":
		_animation_event("rifle_fire")
	var st: Dictionary = _ws[weapon_slot]
	if _has_chamber(weapon_id):
		# После вставки или снаряжения магазина патронник может ещё быть пустым.
		# Перед выстрелом переносим патрон из магазина, сохраняя общий боезапас.
		if int(st.get("chamber", 0)) <= 0:
			if int(st.rounds) <= 0:
				return
			st.rounds = int(st.rounds) - 1
			st["chamber"] = 1
			st["chamber_ammo"] = String(st.ammo)
		st["chamber"] = 0
		st["chamber_ammo"] = ""
		if int(st.rounds) > 0:
			st.rounds = int(st.rounds) - 1
			st["chamber"] = 1
			st["chamber_ammo"] = String(st.ammo)
	else:
		st.rounds = int(st.rounds) - 1
	ammo = _state_rounds(weapon_slot)
	weapon_rounds = ammo
	_weapon_action("shot", ammo <= 0, 0.0, ammo, false)
	st.dur = maxf(0.0, float(st.dur) - float(spec.wear))
	_ws_dirty = true
	_ws_sync_t = 0.6
	fire_timer = float(spec.interval)
	# задержка — редко; на изношенном чаще
	if _rng.randf() < float(spec.jam):
		st.jam = true
		_say("Задержка! R — устранить")
	var from: Vector3
	var dir: Vector3
	if ads:
		from = eye_position()
		dir = look_dir()
		# у бедра (не вскинул к прицелу) пуля идёт по стволу — модель в руках смещена и довёрнута,
		# в наклоне ещё и с креном; в прицеле линия прицеливания на оси взгляда
		var rig0 := _camera_rig as CameraRig
		if rig0 and aim_progress() < 0.9:
			var ray := rig0.barrel_ray()
			if not ray.is_empty():
				dir = ray[1]
				# дуло за стеной (упёрся) — стреляем от глаза, но по стволу
				var q := PhysicsRayQueryParameters3D.create(from, ray[0], Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [get_rid()])
				if get_world_3d().direct_space_state.intersect_ray(q).is_empty():
					from = ray[0]
	else:
		from = global_position + Vector3.UP * 1.3
		var target := cursor_body if cursor_body != Vector3.ZERO else cursor_ground + Vector3.UP * 1.3
		dir = target - from
		if dir.length_squared() < 0.01:
			dir = Vector3(sin(_body.rotation.y), 0.0, cos(_body.rotation.y))
		dir = dir.normalized()
	var exclude: Array[RID] = [get_rid()]
	# разброс: от бедра (ЛЦУ включён — меньше, hip_spread), в прицеле — по мере «довода» к
	# прицельному (выбранный прицел: у углового — свой довод и точность); сидя/лёжа на сошках —
	# ещё меньше, и отдача тоже
	var hip := float(spec.hip_spread)
	var mult := hip
	if ads and aiming:
		mult = lerpf(hip, float(spec.ads_spread), aim_progress())
	elif not ads:
		# изометрия, от бедра: угловой коллиматор — навскидку точнее, крупная оптика мешает
		if String(spec.sight) == "offset":
			mult *= float(Balance.ISO_AIM.offset_hip)
		elif bool(spec.scoped):
			mult *= float(Balance.ISO_AIM.scope_hip)
	var braced := stance != Stance.STAND
	var spread: float = float(spec.spread_deg) * mult * (float(spec.braced_spread) if braced else 1.0)
	if is_downed():
		spread *= Balance.DOWN_SPREAD
	# очередь раскачивает: от бедра сильно, в прицеле — меньше (ствол ведут глазами)
	spread *= 1.0 + minf(_bloom, Balance.RECOIL_BLOOM_MAX) * (Balance.RECOIL_BLOOM_ADS if ads and aiming else 1.0)
	var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DEBRIS
	var muzzle := _muzzle_world()
	var rig := _camera_rig as CameraRig
	var marked := false
	var bullet := {"pen": float(spec.pen), "armor_dmg": float(spec.armor_dmg), "src": {"kind": "player", "peer": peer_id}}
	var hit_person := false
	for i in range(int(spec.pellets)):
		var hit := Hitscan.fire(get_world_3d(), from, dir, spread, float(spec.range_m), mask, float(spec.damage), exclude, _rng, -1, bullet)
		var c: Object = hit.get("collider")
		hit_person = hit_person or c is Marauder
		if rig and not marked:
			if c is Target:
				rig.show_hitmarker(hit.position.y - (c as Target).global_position.y >= (c as Target).head_height - 0.25)
				marked = true
			elif c is Marauder:
				var killed := not ((c as Marauder).get_node("Health") as Health).alive
				rig.show_hitmarker(killed)
				marked = true
	# хроника рейда: выстрел и попал ли (дробь — один выстрел)
	if Raid.current and is_local():
		Raid.current.analytics.on_shot(hit_person)
	_apply_recoil(spec, braced, rig)
	if rig:
		rig.add_shake(float(spec.shake))
	NoiseBus.emit(global_position, float(spec.noise_m), "shot")
	_shot_fx(muzzle, String(spec.sound), float(spec.db), float(spec.flash), String(spec.cycle_sound), _weapon_sound(spec, "mechanism"))
	if ammo <= 0:
		_play_weapon_sound(spec, "bolt_lock", -5.0)
	# остальным — то же (пули и урон уже посчитаны здесь и у хоста)
	if Net.is_networked():
		_rpc_shot_fx.rpc(muzzle, String(spec.sound), float(spec.db), float(spec.flash), String(spec.cycle_sound), _weapon_sound(spec, "mechanism"), ammo)


## Что видно и слышно от выстрела: вспышка у дула, звук, щелчок помпы/затвора. След пули
## обозначают только эффекты попадания, созданные Hitscan. У стрелявшего — из _fire, у остальных
## — по сети (_rpc_shot_fx).
func _shot_fx(muzzle: Vector3, sound: String, db: float, flash: float, cycle_sound: String, mechanism_sound: String) -> void:
	# вспышка: пламегаситель гасит, глушитель — почти нет
	if flash > 0.05:
		_muzzle.global_position = muzzle
		_muzzle.light_energy = 3.0 * flash
		_muzzle.visible = true
		get_tree().create_timer(0.05).timeout.connect(func() -> void: _muzzle.visible = false)
	Audio.play(sound, muzzle, db)
	if mechanism_sound != "":
		Audio.play(mechanism_sound, muzzle, db - 5.0)
	# помпа/затвор — щелчок после выстрела
	if cycle_sound != "":
		get_tree().create_timer(0.35).timeout.connect(func() -> void:
			if is_inside_tree():
				Audio.play(cycle_sound, global_position))


## Выстрел напарника: раньше его видел и слышал только он сам.
@rpc("authority", "call_remote", "unreliable_ordered")
func _rpc_shot_fx(muzzle: Vector3, sound: String, db: float, flash: float, cycle_sound: String, mechanism_sound: String, rounds_left: int = -1) -> void:
	_shot_fx(muzzle, sound, db, flash, cycle_sound, mechanism_sound)
	if rounds_left >= 0:
		weapon_rounds = rounds_left
		_weapon_action("shot", rounds_left <= 0, 0.0, rounds_left, false)


## Дуло: в прицеле — у модели в руках перед камерой, иначе — у модели на теле.
func _muzzle_world() -> Vector3:
	if ads and _camera_rig is CameraRig:
		return (_camera_rig as CameraRig).viewmodel_muzzle()
	if _weapon_model:
		return _weapon_model.to_global(_weapon_model.get_meta("muzzle", Vector3.ZERO))
	return global_position + Vector3.UP * 1.3


## Ушёл со сцены (конец рейда, убежище) — поправки гарнитуры снимаются; свой игрок, пока жив,
## ставит их заново каждый кадр.
func _exit_tree() -> void:
	Settings.set_headset({})


## Что надето на глаза: ПНВ / очки / "".
func eyes_item() -> String:
	return String((inventory.equipment.get("eyes", {}) as Dictionary).get("id", "")) if inventory else ""


func _tick_nvg(delta: float) -> void:
	# гарнитура на ушах — поправки звука (своему игроку)
	Settings.set_headset(WeaponDb.headset(String((inventory.equipment.get("ears", {}) as Dictionary).get("id", ""))) if inventory and health.alive else {})
	var has := bool(ItemDb.equip(eyes_item()).get("nvg", false))
	if Input.is_action_just_pressed("nvg") and not PauseMenu.shown:
		if not has:
			_say("ПНВ нет — надень его в слот «Глаза»")
		elif nvg_charge <= 0.0:
			_say("ПНВ: батарея села")
		else:
			nvg_on = not nvg_on
			Audio.play("nvg_on" if nvg_on else "nvg_off", global_position, -14.0)
	if not has:
		nvg_on = false
	if nvg_on:
		nvg_charge -= delta
		if nvg_charge <= 0.0:
			nvg_on = false
			_say("ПНВ: батарея села")


## Ракета / химсвет: из рюкзака (в песочнице — без счёта); бросок видят все peer.
func _throw_light(k: String) -> void:
	if loadout_mode:
		if inventory.count(k) <= 0:
			_say("Нет: " + ItemDb.item_name(k))
			return
		items_host().call("request_consume", k, 1)
	fire_timer = 0.5
	var from := eye_position() + Vector3.UP * 0.1
	var v: Vector3
	if ads:
		from += look_dir() * 0.4
		v = look_dir() * 11.0 + Vector3.UP * 2.0
	else:
		var to := cursor_ground - global_position
		to.y = 0.0
		to = to.limit_length(16.0)
		var t := clampf(to.length() / 11.0, 0.4, 1.2)
		v = (global_position + to - from) / t + Vector3.UP * 0.5 * 9.8 * t
	if Net.is_networked():
		_rpc_throw_light.rpc(k, from, v)
	else:
		_rpc_throw_light(k, from, v)


@rpc("authority", "call_local", "reliable")
func _rpc_throw_light(k: String, from: Vector3, v: Vector3) -> void:
	ThrownLight.throw(get_tree().current_scene, k, from, v)


## Откуда и с какой скоростью полетит граната: [from, v] — из глаз в прицеле, к курсору в изометрии.
func _grenade_launch() -> Array:
	var g: Dictionary = Balance.GRENADE
	var from := eye_position() + Vector3.UP * 0.1
	var v: Vector3
	if ads:
		from += look_dir() * 0.4
		v = look_dir() * float(g.throw_speed) + Vector3.UP * 2.0
	else:
		var to := cursor_ground - global_position
		to.y = 0.0
		if to.length() > float(g.max_range):
			to = to.normalized() * float(g.max_range)
		var target := global_position + to
		from += to.normalized() * 0.4 if to.length() > 0.1 else Vector3.ZERO
		var t := clampf(to.length() / float(g.throw_speed), 0.45, 1.3)
		v = (target - from) / t + Vector3.UP * 0.5 * 9.8 * t
	return [from, v]


func _show_nade_aim() -> void:
	if _nade_aim == null:
		_nade_aim = GrenadeAim.new()
		add_child(_nade_aim)
	var l := _grenade_launch()
	_nade_aim.show_arc(l[0], l[1], Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS, [get_rid()])


func _cancel_nade_aim() -> void:
	_nade_aiming = false
	if _nade_aim:
		_nade_aim.hide_arc()


func _throw_grenade() -> void:
	_animation_event("grenade_throw")
	if loadout_mode:
		items_host().call("request_consume", "grenade", 1)
	else:
		grenades -= 1
	fire_timer = 0.6
	var l := _grenade_launch()
	var g := Grenade.throw(get_tree().current_scene, l[0], l[1], get_rid())
	g.src = {"kind": "grenade", "by": "player", "peer": peer_id}


## Куда: по нажатым WASD, иначе — куда смотрит корпус.
func _action_dir() -> Vector3:
	var w := _wish_direction()
	if w.length_squared() > 0.01:
		return w
	if ads:
		return Vector3(sin(look_yaw), 0.0, cos(look_yaw))
	return Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))


## Пробел: перелезть через преграду по пояс впереди (стоя или сидя; не лёжа, не с раненым на руках).
func _try_vault() -> void:
	var v: Dictionary = Balance.VAULT
	if stance == Stance.PRONE or is_burdened() or is_downed() or _winded or stamina < float(v.stamina) * 0.5 or not is_on_floor():
		return
	var space := get_world_3d().direct_space_state
	var path := Vault.find(space, global_position, _action_dir(), [get_rid()])
	if path.is_empty() and _wish_direction().length_squared() > 0.01:
		# жмёт вбок, а преграда прямо перед ним
		path = Vault.find(space, global_position, Vector3(sin(body_yaw()), 0.0, cos(body_yaw())), [get_rid()])
	if path.is_empty():
		return
	_vault = path
	_vault_t = 0.0
	_vault_sec = float(v.sec) * (1.0 + _over() * float(v.weight_k))
	# под сильным стрессом можно запнуться (редко, не чаще раза в stumble_cd)
	var sc: Dictionary = Balance.STRESS
	if _stumble_cd <= 0.0 and stress >= float(sc.stumble_from) and _rng.randf() < float(sc.stumble_chance) * _stress_over(float(sc.stumble_from)):
		_vault_stumble = true
		_vault_sec *= 1.6
		_stumble_cd = float(sc.stumble_cd)
		_say("Запнулся — руки не слушаются")
	stamina = maxf(0.0, stamina - float(v.stamina) * carry_stamina_k())
	_rest_t = Balance.STAMINA_REGEN_DELAY
	_cancel_nade_aim()
	var d: Vector3 = (path.land as Vector3) - global_position
	if not ads:
		_body.rotation.y = atan2(d.x, d.z)
	NoiseBus.emit(global_position, float(v.noise_m), "step")
	Audio.play("vault", global_position + Vector3.UP * 0.8, -14.0)


## Alt: бросок на землю в сторону движения (любую), дальше — лёжа. Шумно, пару мгновений не стреляет.
func _try_dive() -> void:
	var dv: Dictionary = Balance.DIVE
	if stance == Stance.PRONE or is_burdened() or is_downed() or _dive_cd > 0.0 or _dive_t >= 0.0 or stamina < float(dv.stamina) * 0.5:
		return
	# только в сторону движения: Alt на месте — ничего (раньше бросал вперёд и сбивал с толку)
	var wish := _wish_direction()
	if wish.length_squared() < 0.01:
		return
	_dive_dir = wish.normalized()
	_dive_t = 0.0
	_dive_cd = float(dv.cooldown)
	velocity = _dive_dir * float(dv.speed) + Vector3.UP * float(dv.hop)
	stance = Stance.PRONE
	_apply_stance()
	stamina = maxf(0.0, stamina - float(dv.stamina) * carry_stamina_k())
	_rest_t = Balance.STAMINA_REGEN_DELAY
	fire_timer = maxf(fire_timer, float(dv.sec) + float(dv.recover))
	_cancel_nade_aim()
	NoiseBus.emit(global_position, float(dv.noise_m), "step")
	get_tree().create_timer(float(dv.sec)).timeout.connect(func() -> void:
		if is_inside_tree():
			Audio.play("dive", global_position, -8.0))


## Стресс: прибавить (минус — успокоить). Вызвать можно где угодно (хост — про любого игрока):
## считает владелец, чужому — по RPC.
func add_stress(amount: float) -> void:
	if is_local():
		_add_stress_local(amount)
	elif Net.is_networked() and multiplayer.is_server():
		_rpc_stress.rpc_id(peer_id, amount)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_stress(amount: float) -> void:
	if multiplayer.get_remote_sender_id() == 1:
		_add_stress_local(amount)


func _add_stress_local(amount: float) -> void:
	stress = clampf(stress + amount, 0.0, 100.0)
	if amount > 0.0:
		_stress_quiet = 0.0


## Пуля прошла рядом (хост, по выстрелам мародёров): не чаще раза в near_gap с.
func near_miss() -> void:
	if is_local():
		if _near_t > 0.0:
			return
		_near_t = float(Balance.STRESS.near_gap)
		_add_stress_local(float(Balance.STRESS.near_miss))
		Audio.play("flyby", global_position + Vector3.UP * 1.2)
	elif Net.is_networked() and multiplayer.is_server():
		_rpc_near.rpc_id(peer_id)


@rpc("any_peer", "call_remote", "unreliable")
func _rpc_near() -> void:
	if multiplayer.get_remote_sender_id() == 1:
		near_miss()


## Насколько стресс уже мешает (0 — ниже effects_from, 1 — на пределе).
func stress_k() -> float:
	return _stress_over(float(Balance.STRESS.effects_from))


func _stress_over(from: float) -> float:
	return smoothstep(from, 100.0, stress)


## Стресс сам по себе: нижняя граница (ранен, мало здоровья, выдохся), напарник упал рядом,
## успокоение в тишине (сидя/лёжа на месте и рядом со своими — быстрее).
func _tick_stress(delta: float) -> void:
	var sc: Dictionary = Balance.STRESS
	_near_t = maxf(0.0, _near_t - delta)
	_stumble_cd = maxf(0.0, _stumble_cd - delta)
	_fumble_cd = maxf(0.0, _fumble_cd - delta)
	if not combat_enabled:
		stress = move_toward(stress, 0.0, delta * 20.0)
		return
	var floor_v := 0.0
	if is_downed():
		floor_v = float(sc.downed)
	elif health.hp < health.max_hp * 0.35:
		floor_v = float(sc.low_hp)
	if _winded:
		floor_v = maxf(floor_v, float(sc.winded))
	var ally_near := false
	for n in get_tree().get_nodes_in_group("players"):
		var o := n as Player
		if o == null or o == self:
			continue
		var d := o.global_position.distance_to(global_position)
		if d < float(sc.ally_m) and not o.is_downed():
			ally_near = true
		var down := o.is_downed()
		if down and not _allies_down.has(o.peer_id) and d < float(sc.ally_down_m):
			_add_stress_local(float(sc.ally_down))
		if down:
			_allies_down[o.peer_id] = true
		else:
			_allies_down.erase(o.peer_id)
	_stress_quiet += delta
	if _stress_quiet > float(sc.calm_delay):
		var rate := float(sc.calm)
		if stance != Stance.STAND and Vector2(velocity.x, velocity.z).length() < 0.5:
			rate *= float(sc.calm_cover_k)
		if ally_near:
			rate *= float(sc.calm_ally_k)
		stress = maxf(0.0, stress - rate * delta)
	stress = maxf(stress, floor_v)


## Чит «бессмертие» (Settings.god): здоровье — у хоста, поэтому клиент просит хост. В коопе
## остальным — строчка в чат, чтобы было честно.
func set_god(on: bool) -> void:
	if not is_local():
		return
	if Net.is_networked() and not multiplayer.is_server():
		_rpc_god.rpc_id(1, on)
	else:
		_apply_god(on)
	if Net.is_networked() and combat_enabled:
		Chat.send("[чит] бессмертие " + ("включено" if on else "выключено"))


@rpc("any_peer", "call_remote", "reliable")
func _rpc_god(on: bool) -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == peer_id:
		_apply_god(on)


func _apply_god(on: bool) -> void:
	health.invulnerable = on
	if on and health.alive and not health.downed:
		health.hp = health.max_hp


func is_vaulting() -> bool:
	return _vault_t >= 0.0


func _read_stance() -> void:
	if Input.is_action_just_pressed("crouch"):
		stance = Stance.STAND if stance == Stance.CROUCH else Stance.CROUCH
		_apply_stance()
	if Input.is_action_just_pressed("prone"):
		stance = Stance.STAND if stance == Stance.PRONE else Stance.PRONE
		_apply_stance()
	var was_aiming := aiming
	aiming = Input.is_action_pressed("aim") and not ui_blocked()
	if aiming and not was_aiming and weapon_id != "":
		_play_weapon_sound(spec(), "ads_raise", -8.0)
	elif was_aiming and not aiming and weapon_id != "":
		_play_weapon_sound(spec(), "ads_lower", -8.0)


func _stance_key() -> String:
	match stance:
		Stance.CROUCH:
			return "crouch"
		Stance.PRONE:
			return "prone"
	return "stand"


func _stance_speed() -> float:
	if is_downed():
		return Balance.DOWN_CRAWL_SPEED
	var s: float
	match stance:
		Stance.CROUCH:
			s = Balance.PLAYER_CROUCH_SPEED
		Stance.PRONE:
			s = Balance.PLAYER_PRONE_SPEED
		_:
			s = Balance.PLAYER_SPRINT_SPEED if _can_sprint() and Input.is_action_pressed("sprint") and not aiming else Balance.PLAYER_WALK_SPEED
			# адреналин: бежит быстрее
			if s == Balance.PLAYER_SPRINT_SPEED:
				s *= 1.0 + float(Balance.STRESS.adr_speed) * stress_k()
	if aiming:
		s *= Balance.PLAYER_ADS_SPEED_SCALE
	# перегруз: тяжелее free_kg — медленнее
	s *= carry_speed_k()
	if absf(lean) > 0.3:
		s *= Balance.LEAN_MOVE_SCALE
	if is_dragging():
		s = minf(s, Balance.DRAG_SPEED)
	if carrying:
		s = minf(s, Balance.CARRY_SPEED)
	return s


## WASD: в прицеле — относительно взгляда (вперёд — куда смотришь), иначе — относительно камеры
## («вверх» на экране — от камеры вглубь).
func _wish_direction() -> Vector3:
	if PauseMenu.shown:
		return Vector3.ZERO
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	if input.length_squared() == 0.0:
		return Vector3.ZERO
	var forward: Vector3
	var right: Vector3
	if ads:
		forward = Vector3(sin(look_yaw), 0.0, cos(look_yaw))
		right = forward.cross(Vector3.UP)
	else:
		var yaw := _camera_rig.rotation.y if _camera_rig else 0.0
		forward = Vector3(-sin(yaw), 0.0, -cos(yaw))
		right = Vector3(cos(yaw), 0.0, -sin(yaw))
	return (right * input.x + forward * -input.y).normalized()


func _face_cursor(delta: float) -> void:
	var to := cursor_ground - global_position
	to.y = 0.0
	if to.length_squared() < 0.04:
		return
	var want := atan2(to.x, to.z)
	_body.rotation.y = lerp_angle(_body.rotation.y, want, minf(1.0, Balance.PLAYER_TURN_SPEED * delta))


func _apply_stance() -> void:
	var key := _stance_key()
	var h: float = Balance.STANCE_HEIGHT[key]
	var shape := _capsule.shape as CapsuleShape3D
	shape.height = h
	shape.radius = minf(Balance.CAPSULE_RADIUS, h * 0.5)
	_capsule.position.y = h * 0.5
	_body.scale.y = h / Balance.STANCE_HEIGHT["stand"]


## Смерть: капсула прячется, падает регдолл, толкнутый от того, кто попал; камера — за телом.
## Эвакуация: тело пропадает, коллизий нет, мародёры больше не видят (не в группе "players").
func _leave_raid() -> void:
	cancel_weapon_action()
	remove_from_group("players")
	visible = false
	collision_layer = 0
	collision_mask = 0
	velocity = Vector3.ZERO
	set_physics_process(false)
	Audio.play("door", global_position)


func _die() -> void:
	cancel_weapon_action()
	if _died_shown:
		return
	# модель падает клипом смерти и остаётся лежать (не манекен); без модели — прежний регдолл
	if _animator and _animator.has_model():
		_died_shown = true
		_animator.die(_animator.death_clip(_last_hit_from, health.last_zone, stance == Stance.CROUCH, stance == Stance.PRONE))
		_hand.visible = false
		if _weapon_model:
			_weapon_model.visible = false
		collision_layer = 0
		Audio.play("fall", global_position)
		if is_local() and _camera_rig is CameraRig:
			(_camera_rig as CameraRig).set_target(_animator.bone_node("mixamorig_Spine2"))
		return
	var torso := _body.get_node("Torso") as MeshInstance3D
	var mat := torso.get_surface_override_material(0)
	var away := global_position - _last_hit_from
	away.y = 0.0
	away = away.normalized() if away.length() > 0.01 else -Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))
	var push: Dictionary = Balance.RAGDOLL_DEATH_PUSH
	var imp := away * (float(push.base) + float(push.per_damage) * _last_damage)
	var xf := Transform3D(Basis(Vector3.UP, body_yaw()), global_position)
	_ragdoll = Ragdoll.spawn(get_tree().current_scene, xf, velocity, imp, global_position + Vector3.UP * 1.25, mat, mat)
	_body.visible = false
	_hand.visible = false
	collision_layer = 0
	Audio.play("fall", global_position)
	if is_local() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).set_target(_ragdoll.chest())


func _animation_event(clip: String) -> void:
	animation_event = clip
	animation_event_seq += 1
