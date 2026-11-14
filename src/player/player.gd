class_name Player
extends CharacterBody3D
## Игрок: движение по стойкам относительно камеры, корпус смотрит на курсор.
## В прицеле (ПКМ, см. CameraRig) — вид от первого лица: взгляд ведёт мышь, WASD — относительно
## взгляда, выстрел — из глаз по оси взгляда. Оружие: 1–4 пистолет/автомат/дробовик/винтовка, X — режим огня,
## 4 — граната, Y — химсвет в руку, G — ракетница (дважды — фальшфейер в руку). Смерть — регдолл. Тяжело ранен
## (Health.downed) — лежит, ползёт, стреляет только из пистолета, кидает гранаты; его могут поднять (аптечка) и тащить (B);
## B (держать) — сдаться.
## Сеть: узлом владеет тот peer, чей id записан в `peer_id`; чужих игроков двигает синхронизация.

enum Stance { STAND, CROUCH, PRONE }

@export var peer_id: int = 1
## Ник над головой (только у чужих игроков в сети).
var _name_tag: Label3D
## Вид снаряжения на теле: что надето (строка NpcOutfit), когда сверять, от первого ли лица.
var _outfit_spec: String = ""
var _gear_look_t: float = 0.0
var _first_person_on: bool = false

var stance: Stance = Stance.STAND
var aiming: bool = false
## Головка самонаведения ПЗРК «Осока» (только у своего игрока; OsokaSeeker): захват цели, писк, метка.
var osoka: OsokaSeeker = OsokaSeeker.new()
## Канал тепловизора на «Осоке» (ПН-36Т «ПОЛЫНЬ», attach.thermal): true — тепловой, false — дневной; X — переключатель
## (toggle_sight_channel). Свой у игрока, не в записи ствола: новый рейд — снова тепловой.
var sight_thermal: bool = true
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
## Передаётся вместе с позицией: чужие персонажи сами не считают move_and_slide.
var airborne: bool = false
var _jump_cd: float = 0.0
var weapon_slot: String = ""
## Обвес в руках с состоянием фонарей/ЛЦУ (точка → {id, light, laser}): модель на теле у всех.
var weapon_mods: Dictionary = {}
## Магазин в оружии в руках для вида модели (WeaponMods.mag_state): "*" штатный, "" вынут, id — другой.
var weapon_mag: String = "*"
var weapon_condition: float = 100.0
var weapon_engraving: Dictionary = {}
## Горит фонарь / ЛЦУ на оружии в руках (выдаёт, слепит) — видят все.
var light_on: bool = false
var laser_on: bool = false
## DOZOR hand pose is authored by the owner; binding does not alter the FPS rig.
signal handheld_flashlight_requested(id: String, on: bool)
var handheld_light_id: String = ""
var handheld_light_on: bool = false
var handheld_light_condition: float = 1.0
var handheld_flashlight: HandheldFlashlight
var phone_equipped: bool = false

## Песочница: стволы по ключам (пресеты WeaponDb.sandbox()) — записи оружия.
var sandbox_weapons: Dictionary = {}
## Прицеливание «с завалом»: автомат повёрнут на 45° затвором к глазам (СКМ в прицеле, Balance.AIM_CANT).
## Только у своего игрока и только вид и точность — на экземпляре оружия не хранится.
var aim_cant: bool = false
## Оружие убрано (за спину / в кобуру) повторным нажатием его клавиши: руки пусты, бежит быстрее и
## дольше (Balance.HOLSTER); слот в weapon_slot остаётся — та же клавиша достаёт обратно.
var holstered: bool = false
var _ui_blocked_ms: int = -100000
## Тир убежища: ствол стойки тира (запись оружия; пусто — тира нет). Ключ его слота — RANGE_KEY.
var range_weapon: Dictionary = {}
const RANGE_KEY := "range"
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
## Задержка: затвор уже отпущен (звук «вперёд» и гильза сыграны) — один раз за устранение.
var _clear_released: bool = false
var _reload_slot: String = ""
var _reload_rev: int = -1
var _reload_wait: float = 0.0
var _reload_empty: bool = false
## Быстрая перезарядка (двойное R): старый магазин выбит новым и падает на землю. _reload_age — сколько
## идёт текущая перезарядка (второе R считается только в первые Balance.RELOAD_FAST.tap_sec),
## _reload_old_mag — какой магазин стоял ({id, rounds}): его и выбросить из рюкзака в конце.
var _reload_fast: bool = false
## Подсказка «магазин из рюкзака — дольше» — один раз за рейд.
var _rig_hint_shown: bool = false
var _reload_age: float = 0.0
var _reload_audio = preload("res://src/audio/reload_audio.gd").new()
## Липучка подсумка: через сколько секунд от начала перезарядки звучит (−1 — нет: магазин не из подсумка
## или уже прозвучала). Balance.POUCH_VELCRO.
var _velcro_at: float = -1.0
## Сколько раз прозвучала липучка (для проверок).
var velcro_count: int = 0
var _reload_old_mag: Dictionary = {}
## Старый магазин быстрой перезарядки уже вылетел настоящим телом (TossedItem) — в конце перезарядки второй раз
## не роняется, а звук падения звучит при ударе тела о поверхность. mag_body_seen — тело появилось у этого peer
## (ставит само тело): руки больше не рисуют магазин. _toss_at — на какой секунде перезарядки запасной бросок у
## ствола без кадра сброса в клипе (−1 — магазин отпускает клип рук, ViewmodelClips.track_spare).
var _mag_tossed: bool = false
var mag_body_seen: bool = false
var _toss_at: float = -1.0
## Магазин был вынут: перезарядка — только вставить новый (короче: Balance.RELOAD_INSERT.time_k);
## быстрой (двойное R) у неё нет — выбивать нечего.
var _reload_insert: bool = false
## Перезарядка магазином, который игрок сам бросил на оружие в окне рюкзака ({role, idx, id}); пусто — выбирает хост.
var _reload_pick: Dictionary = {}
## Такая перезарядка идёт и при открытом рюкзаке (обычная, начатая клавишей, с открытым окном стоит).
var _reload_ui: bool = false
## Проверка магазина: R ещё держат — магазин перед глазами (вьюмодель ждёт), отпустили — убирает.
## inspect_turn — поворот кисти с магазином мышью, доли −1…1 (вбок, вверх-вниз).
var mag_inspect: bool = false
var inspect_turn: Vector2 = Vector2.ZERO
## Осмотр оружия (клавиша I): сколько ещё идёт клип осмотра (ViewmodelClips, viewmodel.inspect_sec ствола), с.
var weapon_inspect_t: float = 0.0
## Дыхание в прицеле: запас воздуха 0…1, задержано ли сейчас (держат «бег» в прицеле), сколько ещё
## длится одышка после полной задержки, с.
var breath: float = 1.0
var breath_held: bool = false
var _breath_gasp: float = 0.0
## Тир: ствол стойки — копия своего (слот снаряжения; "" — ствол зала): пристрелка пишется в своё.
var range_own_slot: String = ""
## ПМ меняет предметы только после окончания действия. До этого прерывание отменяет лишь позу.
var _pm_action: Dictionary = {}
var _pm_action_seq: int = 0
var _pm_host_seq: int = 0
var _weapon_rig: WeaponRig
## Ответ хоста может прийти раньше снимка Inventory; до его ревизии читаем подтверждённую запись.
var _pm_entries: Dictionary = {}
## The break-action launcher uses the same atomic action protocol as the PM.
var signal_reload_ammo: String = "flare"
var weapon_signal_ammo: String = "flare"
var _signal_host_fire_ms: int = -10000
var _was_downed: bool = false
var _sandbox_picked: bool = false
## Сколько секунд держим прицел — «довод» по эргономике (WeaponStats.aim_time).
var _aim_t: float = 0.0
## Владелец тела передаёт отведение оружия: напарник видит ту же готовую позу.
var weapon_obstruction: float = 0.0
var weapon_ready_up: bool = false
## Как несут оружие от первого лица (не в прицеле): true — «наискосок» вниз-влево (по умолчанию,
## колесо вниз), false — на изготовку от бедра (колесо вверх). Бегом — всегда наискосок; из прицела —
## в ту стойку, из которой вскинул. Выстрел из «наискосок» сначала поднимает оружие (raise_weapon).
var carry_low: bool = true
## Насколько ствол сейчас опущен в «наискосок», 0–1 — ставит CameraRig каждый кадр (только свой игрок).
## Пока больше Balance.WEAPON_CARRY.fire_max — не стреляет: ствол смотрит не туда, куда смотрит игрок.
var weapon_lowered: float = 0.0
## Нажал огонь, пока ствол опущен: выстрел, как только поднимется (не дольше queue_sec), с.
var _fire_queue: float = 0.0
## Режим «2»: сколько выстрелов очереди ещё осталось (Balance.FIRE_MODES.burst на нажатие).
var _burst_left: int = 0
## Переводчик щёлкает большим пальцем (с): клип рук; from → to — индексы положений рычага в fire_modes.
var fire_mode_switch_t: float = 0.0
var fire_mode_from: int = 0
var fire_mode_to: int = 0
var grenades: int = Balance.GRENADES_START
## Выбор гранаты отделён от слотов огнестрельного оружия: состояние магазина сохраняется.
var grenade_equipped: bool = false
## Что в руке вместо оружия, пока grenade_equipped: "grenade" — граната (4), "chemlight" — зелёный химсвет (Y), "flare" — красный
## фальшфейер (двойное G). Всё бросается одинаково: ЛКМ — верхом, ПКМ — снизу, держать — сильнее; расход и бросок — у хоста.
var throwable_id: String = "grenade"
## G: ждём второго нажатия (с): двойное — фальшфейер в руку, одно — ракетница в руки (Balance.LIGHT_KEYS).
var _g_tap_t: float = -1.0
var grenade_in_hand: bool = false
var grenade_pin: float = 0.0
var grenade_charge: float = 0.0
var grenade_underhand: bool = false
var _grenade_hold: float = 0.0
var _grenade_button: String = ""
var _grenade_released: bool = false
var _grenade_input_ready: bool = false
var _grenade_recover: float = 0.0
var _grenade_pending: bool = false
var _grenade_seq: int = 0
var _grenade_host_seq: int = 0
var _grenade_host_ms: int = -10000
var _grenade_result_seq: int = 0
var fire_timer: float = 0.0
## Когда стрелял (мс) — ИИ замечает стреляющего быстрее (Balance.AI_NOTICE.shot).
var last_shot_ms: int = -100000
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
var _weapon_model_cache: Dictionary = {}
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
## Тем же ходом — залезть наверх (Climb.find) и шаг на лестницу или с неё (путь с "pts" — Climb.pos_at).
var _vault: Dictionary = {}
var _vault_t: float = -1.0
## Что сделать, когда путь _vault пройден: "ladder" — повис на лестнице, "off" — сошёл с неё наверх.
var _vault_then: String = ""
## Лестница (Ladder), на которой висит (null — не на лестнице), и высота ног над её низом, м. on_ladder
## видят все peer — стук перекладин у каждого (_tick_rung_sound). Оружие на время подъёма убрано:
## _ladder_slot — какой слот достать, сойдя. Схватиться снова — не раньше _ladder_cd.
var ladder: Ladder = null
var on_ladder: bool = false
var _ladder_y: float = 0.0
var _ladder_slot: String = ""
var _ladder_cd: float = 0.0
var _ladder_noise_y: float = 0.0
var _rung_sound_y: float = 0.0
var _ladder_hint_shown: bool = false
## Ступеньки и кочки для глаза: тело поднимается/опускается рывком (шаг на ступень, снап к полу),
## камера догоняет плавно — смещение глаза по высоте, гаснет за доли секунды.
var _eye_dy: float = 0.0
## Высота глаз своего игрока при смене стойки — плавно к Balance.ADS_EYE (без рывка камеры и прицела),
## м и м/с; меньше нуля — ещё не задана (первый тик встаёт сразу).
var _stance_eye: float = -1.0
var _stance_eye_v: float = 0.0
## Глаз в начале последнего тика физики: камера ведёт глаз между тиками плавно (view_eye).
var _eye_tick_prev: Vector3 = Vector3.ZERO
var _eye_tick_ready: bool = false
## Сколько секунд не на полу (шаг на ступень — и в первые мгновения после отрыва: висит на ребре).
var _ground_t: float = 0.0
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
## Слой рендера своих рук и оружия у лица (CameraRig ставит его модели в руках).
const VIEWMODEL_LAYER := 1 << 1
## Свет только на свои руки (слой 2): от вспышки выстрела и отражённый от фонаря (Balance.VIEWMODEL_LIGHTS).
## Создаются у своего игрока при первой надобности.
var _hands_flash: OmniLight3D
var _hands_bounce: OmniLight3D

@onready var _capsule: CollisionShape3D = $Capsule
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle
@onready var _animator: CharacterAnimator = get_node_or_null("CharacterAnimator") as CharacterAnimator
@onready var health: Health = $Health
@onready var _cart_contact: CartContact = $CartContact
## Рюкзак: меняет хост, видят все (см. Inventory). Создаётся в _ready.
var inventory: Inventory
@onready var _camera_rig: Node3D = get_tree().get_first_node_in_group("camera_rig")


## Called by the owner after Player.ready with an authored socket; +Z follows the beam.
func bind_handheld_flashlight(socket: Node3D) -> void:
	handheld_flashlight.bind(socket)


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
		if is_local():
			_show_hurt(amount, from, global_position)
		elif Net.is_networked() and multiplayer.is_server():
			# Health считает хост; гостю нужно отдельное событие, а не только новое hp.
			_rpc_hurt.rpc_id(peer_id, amount, from, global_position)
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
	handheld_flashlight = HandheldFlashlight.new()
	handheld_flashlight.name = "HandheldFlashlight"
	handheld_flashlight.actor = self
	add_child(handheld_flashlight)
	var phone_world := PhoneWorldModel.new()
	phone_world.actor = self
	add_child(phone_world)
	# шаги слышно у всех: и свои, и напарника (по синхронизированной позиции и стойке)
	var steps := Footsteps.new()
	steps.name = "Footsteps"
	steps.grounded = func() -> bool: return not airborne and _vault_t < 0.0 and not on_ladder
	# свой — скорость по физике: темп шагов (и покачивания камеры) без ступенек кадра
	steps.speed_source = func() -> float: return Vector2(velocity.x, velocity.z).length() if is_local() else -1.0
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
		if not is_local():
			_make_name_tag()
	# чит «бессмертие» из настроек — на каждый рейд (хосту — когда узел у него уже есть)
	if is_local() and Settings.god:
		set_god.call_deferred(true)


## Позицию и позу владелец шлёт всем остальным сам (авторитет = peer_id, см. sector_level.gd —
## отзывчивое движение важнее для игрока, чем для мародёра/двери). Health синхронизируется
## отдельно, со своим (хостовым) авторитетом — урон всегда считает хост.
func _setup_sync() -> void:
	# Спавн гостей ведёт хост, а движение — владелец. Отдельный хостовый фильтр
	# не даёт спавнеру послать гостя рейда тем, кто пока находится в убежище.
	if Net.scene_of(self) == "raid" and get_multiplayer_authority() != 1:
		var gate: MultiplayerSynchronizer = MultiplayerSynchronizer.new()
		gate.name = "SpawnScope"
		gate.replication_config = SceneReplicationConfig.new()
		gate.set_multiplayer_authority(1)
		Net.scope_sync(self, gate)
		add_child(gate)
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", ".:stance", ".:aiming", ".:weapon_id", ".:weapon_mods", ".:weapon_mag", ".:weapon_condition", ".:weapon_engraving", ".:weapon_rounds", ".:weapon_signal_ammo", ".:light_on", ".:laser_on", ".:handheld_light_id", ".:handheld_light_on", ".:handheld_light_condition", ".:phone_equipped", ".:lean", ".:look_pitch", ".:animation_event", ".:animation_event_seq", ".:airborne", ".:on_ladder", ".:weapon_obstruction", ".:weapon_ready_up", ".:grenade_equipped", ".:throwable_id", ".:grenade_in_hand", ".:grenade_pin", ".:grenade_charge", ".:grenade_underhand"]:
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
	# набирают текст (надпись гравировки, ник, чат) — клавиши идут в поле, а не в действия
	if UiTheme.typing():
		return true
	for n in get_tree().get_nodes_in_group("esc_windows"):
		if n.has_method("is_open") and bool(n.call("is_open")):
			return true
	return false


## Клавиши движения и стойки не для персонажа: открыто любое окно (рюкзак и обыск в рейде, торговец,
## тайник, верстак, терминал, обмен, карта, журнал) или набирают текст — иначе, печатая название у
## торговца, игрок уходил от прилавка, а с открытым рюкзаком бегал по рейду (владелец, 2026-10-11).
func keys_blocked() -> bool:
	return PauseMenu.shown or ui_blocked()


func _can_sprint() -> bool:
	return not _winded and stamina > 0.0 and _water_depth() < float(Balance.WATER.no_sprint)


## Держат бег: Shift, не в прицеле и не стреляют — огонь прерывает бег, ствол поднимается к выстрелу.
func sprint_held() -> bool:
	return Input.is_action_pressed("sprint") and not aiming and not Input.is_action_pressed("fire") and _fire_queue <= 0.0


## Поднять оружие из «наискосок» на изготовку от бедра (колесо вверх, выстрел из опущенного).
func raise_weapon() -> void:
	if carry_low and weapon_id != "":
		_play_stance_sound("ads_raise")
	carry_low = false


## Стойка оружия колесом мыши (не в прицеле): вверх — от бедра, вниз — наискосок. false — колесо не наше.
func wheel_carry(direction: int) -> bool:
	if not is_local() or not is_alive() or not ads or aiming or weapon_id == "" or grenade_equipped or ui_blocked():
		return false
	var low := direction < 0
	# один звук «поднял» на любой переход вверх, один «опустил» на любой вниз
	if low != carry_low:
		_play_stance_sound("ads_lower" if low else "ads_raise")
	carry_low = low
	return true


## Глубина воды над ступнями (WaterBody), м; считается раз за кадр физики.
func _water_depth() -> float:
	var frame: int = Engine.get_physics_frames()
	if frame != _water_frame:
		_water_frame = frame
		_water_cached = WaterBody.depth_at(global_position)
	return _water_cached


var _water_frame: int = -1
var _water_cached: float = 0.0


## Бег тратит выносливость (в жару на улице — быстрее), стоишь или идёшь — восстанавливается.
func _tick_stamina(delta: float) -> void:
	var running := _can_sprint() and sprint_held() and stance == Stance.STAND \
		and Vector2(velocity.x, velocity.z).length() > Balance.PLAYER_WALK_SPEED + 0.3
	if running:
		var k := 1.0
		if String(RaidConditions.current.get("weather", "")) == "heat" and RaidAtmosphere.current and not RaidAtmosphere.current.is_indoor(global_position):
			k = Balance.STAMINA_HEAT
		# адреналин: дыхания хватает дольше
		k *= 1.0 - float(Balance.STRESS.adr_stamina) * stress_k()
		# оружие убрано — бежать легче
		if hands_free():
			k *= float(Balance.HOLSTER.stamina_k)
		# рюкзак: чем больше, тем быстрее садится выносливость в спринте (data/items.json sprint_k)
		stamina = maxf(0.0, stamina - Balance.STAMINA_DRAIN * k * carry_stamina_k() * ItemDb.bag_sprint_k(inventory.equipment) * delta)
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
	if handheld_flashlight and handheld_flashlight.emitting():
		k = maxf(k, float((WeaponDb.attachment(handheld_light_id).get("light", {}) as Dictionary).get("view", 1.0)))
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


## Только владелец пострадавшего видит указатель; урон и броню здесь не пересчитываем.
func _show_hurt(amount: float, from: Vector3, origin: Vector3) -> void:
	if not is_local():
		return
	_last_hit_from = from
	_last_damage = amount
	if _camera_rig is CameraRig:
		# на адреналине попадание почти не сбивает
		(_camera_rig as CameraRig).add_shake(Balance.HURT_SHAKE * (1.0 - float(Balance.STRESS.adr_shake) * stress_k()))
		(_camera_rig as CameraRig).hurt(amount, from, origin)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_hurt(amount: float, from: Vector3, origin: Vector3) -> void:
	if multiplayer.get_remote_sender_id() == 1:
		_show_hurt(amount, from, origin)


## Вызывает зрение врага на хосте после настоящего обнаружения; это только подсказка HUD.
func notify_detected(observer: int, from: Vector3, origin: Vector3) -> void:
	if Net.is_networked() and not multiplayer.is_server():
		return
	if is_local():
		_show_detection(observer, from, origin)
	elif Net.is_networked():
		_rpc_detected.rpc_id(peer_id, observer, from, origin)


func _show_detection(observer: int, from: Vector3, origin: Vector3) -> void:
	if is_local() and is_alive() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).show_detection(observer, from, origin)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_detected(observer: int, from: Vector3, origin: Vector3) -> void:
	if multiplayer.get_remote_sender_id() == 1:
		_show_detection(observer, from, origin)


func is_local() -> bool:
	return peer_id == multiplayer.get_unique_id()


func body_yaw() -> float:
	return _body.rotation.y


## Повернуть корпус (появление на карте — лицом туда, куда идти); вид из глаз берёт его при входе.
func face(yaw: float) -> void:
	_body.rotation.y = yaw


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
		# значение — id или готовая запись с пазом/стороной (путь точки — WeaponBuild)
		var rec: Dictionary = (mods[mount] as Dictionary).duplicate(true) if mods[mount] is Dictionary else {"id": String(mods[mount])}
		rec["id"] = WeaponDb.canonical(String(rec.get("id", "")))
		m[String(mount)] = rec
	e["mods"] = m
	# старая точка «угловой прицел» — кронштейн на планке
	var upgraded: Dictionary = WeaponBuild.upgrade(e)[0]
	e["mods"] = upgraded.mods
	e["sight"] = String(upgraded.get("sight", e.get("sight", "primary")))
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
	e["_condition_shots"] = int(st.get("shots", 0))
	e["sight"] = String(st.sight)
	if WeaponDb.fire_modes(String(e.id)).size() > 1:
		e["fire_mode"] = String(st.get("fire_mode", ""))
	if bool(st.get("cover_open", false)):
		e["cover_open"] = true
	var zc: Array = st.get("zero_c", [0, 0])
	if Gear.zero_clicks(e) != Vector2i(int(zc[0]), int(zc[1])):
		Gear.set_zero_clicks(e, Vector2i(int(zc[0]), int(zc[1])))
	var mods: Dictionary = e.get("mods", {})
	for m in mods:
		var md: Dictionary = mods[m] if mods[m] is Dictionary else {"id": String(mods[m])}
		var t: Dictionary = (st.tac as Dictionary).get(m, {})
		md["light"] = bool(t.get("light", false))
		md["laser"] = bool(t.get("laser", false))
		md["dur"] = float((st.get("mod_dur", {}) as Dictionary).get(m, WeaponCondition.percent(md)))
		mods[m] = md
	e["mods"] = mods
	WeaponStats.apply_scope_zooms(e, st.get("optic_zoom", {}))
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
	var mod_dur: Dictionary = {}
	for m in mods:
		mod_dur[m] = WeaponCondition.percent(WeaponCondition.mod_entry(mods[m]))
		if mods[m] is Dictionary:
			tac[m] = {"light": bool((mods[m] as Dictionary).get("light", false)), "laser": bool((mods[m] as Dictionary).get("laser", false))}
	var jam := bool(_ws[key].get("jam", false)) if _ws.has(key) and String(_ws[key].id) == String(base.id) else false
	var cover := bool(base.get("cover_open", false)) or (_ws.has(key) and String(_ws[key].id) == String(base.id) and bool(_ws[key].get("cover_open", false)))
	# mix — слои патронов магазина (вперемешку, Gear.mag_layers): по ним после выстрела виден следующий тип
	_ws[key] = {"id": String(base.id), "rev": rev, "rounds": int(mag.get("rounds", 0)), "ammo": Gear.mag_top(mag),
		"mix": (mag.get("mix") as Array).duplicate(true) if mag.get("mix") is Array else [],
		"zero_c": [Gear.zero_clicks(base).x, Gear.zero_clicks(base).y],
		"optic_zoom": WeaponStats.scope_zooms(base),
		"dur": WeaponCondition.percent(base), "mod_dur": mod_dur, "shots": int(base.get("_condition_shots", 0)), "sight": String(base.get("sight", "primary")), "tac": tac, "jam": jam,
		"chamber": int(normalized.get("chamber", 0)), "chamber_ammo": String(normalized.get("chamber_ammo", "")),
		"fire_mode": WeaponDb.fire_mode_of(String(base.id), String(base.get("fire_mode", ""))), "cover_open": cover}
	if String(base.id) == "signal_launcher":
		_ws[key].ammo = String(mag.get("ammo", "flare"))


static func _has_chamber(id: String) -> bool:
	return int(WeaponDb.weapon(id).get("chamber_capacity", 0)) > 0


## Верхний патрон магазина ушёл (в ствол или в патронник): его тип. В состоянии — счёт и тип
## следующего: в магазине патроны могут лежать вперемешку.
static func _take_round(st: Dictionary) -> String:
	var took: String = String(st.ammo)
	st.rounds = int(st.rounds) - 1
	st.ammo = Gear.mag_top({"ammo": took, "rounds": int(st.rounds), "mix": st.get("mix", [])})
	return took


## Пристрелка: щелчок барабанчика — попадания сдвигаются на Balance.ZEROING.click_moa вправо (dx) /
## вверх (dy). Щелчки хранятся на экземпляре ствола (хосту уходят с состоянием оружия); ствол стойки
## тира, взятый как «свой», — сразу в запись своего снаряжения.
func zero_click(dx: int, dy: int) -> void:
	if weapon_slot == "" or not _ws.has(weapon_slot):
		return
	var st: Dictionary = _ws[weapon_slot]
	var lim: int = int(Balance.ZEROING.max_clicks)
	var c: Array = st.get("zero_c", [0, 0])
	var now := Vector2i(clampi(int(c[0]) + dx, -lim, lim), clampi(int(c[1]) + dy, -lim, lim))
	st["zero_c"] = [now.x, now.y]
	_ws_dirty = true
	_ws_sync_t = 0.4
	Audio.play_ui("ui_click")
	_say("Пристрелка: %s" % (Gear.zero_text(now) if now != Vector2i.ZERO else "барабанчики на нуле"))
	if in_range_mode() and range_own_slot != "":
		_push_own_sight_state({"zero_c": [now.x, now.y]})


## Сколько накручено на стволе в руках.
func zero_clicks() -> Vector2i:
	var c: Array = (_ws.get(weapon_slot, {}) as Dictionary).get("zero_c", [0, 0])
	return Vector2i(int(c[0]), int(c[1]))


## Тир: поправки и кратность на копии своего ствола со стойки — сразу в своё снаряжение.
func _push_own_sight_state(settings: Dictionary) -> void:
	var own: Dictionary = inventory.equipment.get(range_own_slot, {})
	var h := items_host()
	if own.is_empty() or h == null or String(own.get("uid", "")) != String(range_weapon.get("uid", "")):
		return
	var mag: Dictionary = own.get("mag", {}) if own.get("mag") is Dictionary else {}
	var state: Dictionary = {"id": String(own.id), "rev": int(own.get("rev", 0)),
		"rounds": int(mag.get("rounds", 0)), "dur": WeaponCondition.percent(own), "shots": int(own.get("_condition_shots", 0)),
		"sight": String(own.get("sight", "primary")), "tac": {}, "chamber": int(own.get("chamber", 0)),
		"chamber_ammo": String(own.get("chamber_ammo", ""))}
	state.merge(settings, true)
	h.call("request_weapon_state", range_own_slot, state)


## Дыхание в прицеле: запас воздуха (задержка — «бег» в прицеле) и одышка после неё. Balance.BREATH.
func _tick_breath(delta: float) -> void:
	var cfg: Dictionary = Balance.BREATH
	var want: bool = aiming and ads and weapon_id != "" and Input.is_action_pressed("sprint") and not ui_blocked() \
			and breath > 0.0 and _breath_gasp <= 0.0 and health.alive
	breath_held = want
	if breath_held:
		breath = maxf(0.0, breath - delta / float(cfg.hold_sec))
		if breath <= 0.0:
			# выдохся: одышка, прицел ходит сильнее обычного
			breath_held = false
			_breath_gasp = float(cfg.gasp_sec)
	else:
		breath = minf(1.0, breath + delta / float(cfg.refill_sec))
	_breath_gasp = maxf(0.0, _breath_gasp - delta)


## Во сколько раз сильнее обычного ходит прицел от дыхания: усталость, стресс, задержка, одышка.
func breath_k() -> float:
	var cfg: Dictionary = Balance.BREATH
	var k: float = 1.0 + float(cfg.fatigue_k) * (1.0 - clampf(stamina / Balance.STAMINA_MAX, 0.0, 1.0)) + float(cfg.stress_k) * stress_k()
	if breath_held:
		return k * float(cfg.held_k)
	if _breath_gasp > 0.0:
		k *= lerpf(1.0, float(cfg.gasp_k), _breath_gasp / float(cfg.gasp_sec))
	return k


func breath_gasping() -> bool:
	return _breath_gasp > 0.0


## Отъёмный магазин вынут: в руках оружие без магазина (R — вставить новый).
func mag_out() -> bool:
	return weapon_id != "" and weapon_mag == "" and not WeaponDb.weapon(weapon_id).has("internal_mag")


## Какой магазин вставит перезарядка (руки от первого лица показывают его в руке, пока хост меняет): тот же
## выбор, что у Inventory.reload_slot — из подсумков разгрузки, нет там — из рюкзака. Вид как weapon_mag:
## "*" — штатный; без снаряжения (песочница) и без подходящего — тот же, что в оружии.
func reload_next_mag() -> String:
	if not loadout_mode or inventory == null or weapon_id == "":
		return weapon_mag
	if not _reload_pick.is_empty():
		var picked: String = WeaponDb.canonical(String(_reload_pick.get("id", "")))
		return "*" if picked == WeaponDb.default_mag(weapon_id) else picked
	var e: Dictionary = weapon_entry()
	var pick: String = Gear.next_mag(e, inventory.list_of("rig"))
	if pick == "":
		pick = Gear.next_mag(e, inventory.items)
	if pick == "":
		return weapon_mag
	return "*" if pick == WeaponDb.default_mag(weapon_id) else pick


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


## Поднять / опустить оружие: только запись этого действия у конкретной модели.
func _play_stance_sound(slot: String) -> void:
	var kind := _weapon_sound(spec(), slot)
	if kind != "":
		Audio.play(kind, global_position + Vector3.UP * 1.4)


## Состояние для хоста (Inventory.apply_weapon_state).
func _ws_state(key: String) -> Dictionary:
	var st: Dictionary = _ws.get(key, {})
	return {"id": String(st.get("id", "")), "rev": int(st.get("rev", 0)), "rounds": int(st.get("rounds", 0)), "dur": float(st.get("dur", 100.0)),
		"shots": int(st.get("shots", 0)),
		"sight": String(st.get("sight", "primary")), "tac": (st.get("tac", {}) as Dictionary).duplicate(true),
		"optic_zoom": (st.get("optic_zoom", {}) as Dictionary).duplicate(),
		"chamber": int(st.get("chamber", 0)), "chamber_ammo": String(st.get("chamber_ammo", "")),
		"zero_c": (st.get("zero_c", [0, 0]) as Array).duplicate(), "fire_mode": String(st.get("fire_mode", "")),
		"cover_open": bool(st.get("cover_open", false))}


func _send_ws(key: String) -> void:
	var h := items_host()
	if loadout_mode and h and _ws.has(key):
		h.call("request_weapon_state", key, _ws_state(key))
		_ws_dirty = false
	elif not loadout_mode:
		if _ws.has(key):
			WeaponStats.apply_scope_zooms(_base_entry(key), (_ws[key] as Dictionary).get("optic_zoom", {}))
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
	# Кэш стрельбы существует у владельца. У хоста для гостя свежий источник — Inventory.
	if not is_local():
		return eq
	for key in ItemDb.WEAPON_SLOTS:
		if eq.has(key) and WeaponDb.is_weapon(String((eq[key] as Dictionary).get("id", ""))):
			eq[key] = entry_of(key)
	return eq


## Задержка у оружия в руках (устраняется R).
func is_jammed() -> bool:
	return bool((_ws.get(weapon_slot, {}) as Dictionary).get("jam", false))


## Пылезащитная шторка ствола в руках (models.<ключ>.action.cover, у AR-15) открыта. Закрыта она только у ствола,
## рама которого ещё ни разу не отходила, — каким он попал в руки; отход рамы (выстрел, рукоятка заряжания при
## перезарядке с пустым магазином и при устранении задержки) её откидывает, и открытой она остаётся — сама не
## закрывается. Хранится на экземпляре ствола, хосту — с состоянием оружия, как режим огня.
func dust_cover_open() -> bool:
	return bool((_ws.get(weapon_slot, {}) as Dictionary).get("cover_open", false))


## Рама отошла назад — шторка ствола в слоте откинулась (если она у него есть и ещё закрыта).
func _open_dust_cover(slot: String) -> void:
	if slot == "" or not _ws.has(slot):
		return
	var st: Dictionary = _ws[slot]
	if bool(st.get("cover_open", false)) or WeaponDb.dust_cover(String(st.get("id", ""))) == "":
		return
	st["cover_open"] = true
	if not loadout_mode:
		_base_entry(slot)["cover_open"] = true
	_ws_dirty = true


## Режим огня оружия в руках ("auto" / "burst" / "semi"; Balance.FIRE_MODES).
func fire_mode() -> String:
	if weapon_id == "":
		return ""
	return WeaponDb.fire_mode_of(weapon_id, String((_ws.get(weapon_slot, {}) as Dictionary).get("fire_mode", "")))


## X: переводчик на следующее положение по кругу (у ВЕРАС-54 АВ → 2 → ОД → АВ) — большим пальцем правой руки,
## пока щёлкает, не стрелять. Режим хранится на экземпляре ствола: хосту — с состоянием оружия, как пристрелка.
func cycle_fire_mode() -> void:
	var modes := WeaponDb.fire_modes(weapon_id)
	if modes.size() < 2 or weapon_slot == "" or not _ws.has(weapon_slot) or fire_mode_switch_t > 0.0:
		return
	var cfg: Dictionary = Balance.FIRE_MODES
	var from: int = modes.find(fire_mode())
	var to: int = (from + 1) % modes.size()
	var st: Dictionary = _ws[weapon_slot]
	st["fire_mode"] = modes[to]
	if not loadout_mode:
		_base_entry(weapon_slot)["fire_mode"] = modes[to]
	fire_mode_from = from
	fire_mode_to = to
	fire_mode_switch_t = float(cfg.switch_sec)
	fire_timer = maxf(fire_timer, float(cfg.switch_sec))
	_burst_left = 0
	_ws_dirty = true
	_ws_sync_t = 0.4
	_play_weapon_sound(spec(), "fire_mode", -6.0)
	_say("Режим огня: %s (%s)" % [String((cfg.labels as Dictionary)[modes[to]]), String((cfg.names as Dictionary)[modes[to]])])
	if in_range_mode() and range_own_slot != "":
		_push_own_sight_state({"fire_mode": modes[to]})


func aim_progress() -> float:
	if not ads or not aiming or weapon_id == "" or spec().is_empty():
		return 0.0
	return clampf(_aim_t / float(spec().aim_time), 0.0, 1.0)


func eye_position() -> Vector3:
	return global_position + Vector3.UP * (_eye_height() + _eye_dy) + lean_vector()


## Высота глаз над ногами: у своего игрока после смены стойки — плавно (_tick_stance_eye), у чужих —
## сразу по стойке (их камера не наша).
func _eye_height() -> float:
	if _stance_eye >= 0.0 and is_local():
		return _stance_eye
	return float(Balance.ADS_EYE[_stance_key()])


## Глаз для камеры. Физика считает 60 раз в секунду, кадров бывает больше (144 Гц) — между тиками
## глаз ведётся плавно от прошлого тика к нынешнему, иначе камера ходит ступеньками. Отстаёт от
## физики меньше чем на тик; поворот взгляда мышью этим не задерживается. Телепорт — сразу.
func view_eye() -> Vector3:
	var now := eye_position()
	if not _eye_tick_ready or _eye_tick_prev.distance_squared_to(now) > 1.0:
		return now
	return _eye_tick_prev.lerp(now, clampf(Engine.get_physics_interpolation_fraction(), 0.0, 1.0))


## Смена стойки: глаз переходит на новую высоту критически затухающей пружиной — без рывка
## на старте и без перелёта (Balance.ADS_EYE_SETTLE_SEC).
func _tick_stance_eye(delta: float) -> void:
	var target := float(Balance.ADS_EYE[_stance_key()])
	if _stance_eye < 0.0:
		_stance_eye = target
		_stance_eye_v = 0.0
		return
	var w := 4.75 / maxf(Balance.ADS_EYE_SETTLE_SEC, 0.01)
	var steps: int = clampi(ceili(delta / 0.004), 1, 12)
	var h: float = delta / float(steps)
	for i in steps:
		_stance_eye_v += (-w * w * (_stance_eye - target) - 2.0 * w * _stance_eye_v) * h
		_stance_eye += _stance_eye_v * h


## Куда сдвинут глаз наклоном (вбок от взгляда, чуть ниже).
func lean_vector() -> Vector3:
	if absf(lean) < 0.001:
		return Vector3.ZERO
	# курс — по позе тела (синхронизируется), а не по взгляду: у хоста взгляда клиента нет
	var y := body_yaw()
	var right := Vector3(-cos(y), 0.0, sin(y))
	return right * lean * Balance.LEAN_OFFSET + Vector3.DOWN * absf(lean) * 0.08


## Насколько можно наклониться в сторону side (−1 влево, 1 вправо), доля полного наклона 0–1: шар
## Balance.LEAN_WALL_RADIUS ведётся от глаза без наклона туда же, куда lean_vector() при полном наклоне,
## и останавливается у стены, двери или стекла.
func lean_room(side: float) -> float:
	var y := body_yaw()
	var right := Vector3(-cos(y), 0.0, sin(y))
	var motion := right * side * Balance.LEAN_OFFSET + Vector3.DOWN * 0.08
	var ball := SphereShape3D.new()
	ball.radius = Balance.LEAN_WALL_RADIUS
	var q := PhysicsShapeQueryParameters3D.new()
	q.shape = ball
	q.transform = Transform3D(Basis.IDENTITY, global_position + Vector3.UP * (_eye_height() + _eye_dy))
	q.motion = motion
	q.collision_mask = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	q.exclude = [get_rid()]
	var frac: PackedFloat32Array = get_world_3d().direct_space_state.cast_motion(q)
	return clampf(frac[0], 0.0, 1.0) if frac.size() > 0 else 1.0


## Направление взгляда в прицеле.
func look_dir() -> Vector3:
	return Vector3(sin(look_yaw) * cos(look_pitch), sin(look_pitch), cos(look_yaw) * cos(look_pitch))


## Вид от первого лица: своё тело и оружие в руках не рисуем (камера внутри капсулы),
## но тень оставляем — на полу видно, где стоишь.
func set_first_person(on: bool) -> void:
	_first_person_on = on
	var mode := GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY if on else GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	# своё тело от первого лица — на отдельном слое: тень от солнца и ламп есть, а свет «из глаз»
	# (ИК-подсветка ПНВ, фонарь в руках) его в тенях не видит — иначе перед камерой тень-прямоугольник
	var layer := OWN_BODY_LAYER if on and is_local() else 1
	for mi in _body.find_children("*", "MeshInstance3D", true, false):
		# свечение фонаря (LampGlow) тени не отбрасывает
		(mi as MeshInstance3D).cast_shadow = mode if not mi.has_meta("no_shadow") else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		(mi as MeshInstance3D).layers = layer
	if _weapon_model:
		for mi in _weapon_model.find_children("*", "MeshInstance3D", true, false):
			(mi as MeshInstance3D).cast_shadow = mode if not mi.has_meta("no_shadow") else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			(mi as MeshInstance3D).layers = layer


## Снаряжение на теле (броня, шлем, рюкзак, подсумки — NpcOutfit) и убранное оружие (SlungWeapons): у каждого
## peer из синхронизированного снаряжения (Inventory) и того, что в руках; раз в Balance.SLUNG.every с.
func _tick_gear_look(delta: float) -> void:
	_gear_look_t -= delta
	if _gear_look_t > 0.0:
		return
	_gear_look_t = float(Balance.SLUNG.every)
	var eq: Dictionary = inventory.equipment if inventory else {}
	var changed := false
	var outfit := get_node_or_null("NpcOutfit") as NpcOutfit
	if outfit:
		var spec := NpcOutfit.describe(eq, false)
		if spec != _outfit_spec:
			_outfit_spec = spec
			outfit.apply(spec)
			changed = true
	var slung := get_node_or_null("SlungWeapons") as SlungWeapons
	if slung:
		if health.alive:
			changed = slung.show_list(slung_list(eq)) or changed
		elif not slung.anchors().is_empty():
			slung.clear()
	# новые сетки на теле — в том же режиме: от первого лица своё тело только отбрасывает тень
	if changed:
		set_first_person(_first_person_on)


## Что висит на теле: оружие из слотов, кроме того, что в руках (первое совпадение по id).
func slung_list(eq: Dictionary) -> Array:
	var held := held_model_id()
	var list: Array = []
	var skipped := false
	for slot: String in ItemDb.WEAPON_SLOTS:
		var e: Dictionary = eq.get(slot, {})
		if e.is_empty():
			continue
		if not skipped and held != "" and String(e.get("id", "")) == held:
			skipped = true
			continue
		list.append(SlungWeapons.entry(slot, e))
	return list


## Ник над головой напарника (убежище и рейд): виден сквозь стены — своих не путать с чужими.
func _make_name_tag() -> void:
	_name_tag = Label3D.new()
	_name_tag.name = "NameTag"
	_name_tag.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_tag.font_size = int(Balance.NAME_TAG.font)
	_name_tag.pixel_size = float(Balance.NAME_TAG.pixel)
	_name_tag.modulate = Color(1.0, 0.9, 0.7)
	_name_tag.outline_size = 8
	_name_tag.no_depth_test = true
	_name_tag.position = Vector3(0, float(Balance.NAME_TAG.height[0]), 0)
	add_child(_name_tag)


## Ник держится над головой в любой стойке; лежит раненым — помечен; ушёл или убит — пропадает.
func _tick_name_tag(delta: float) -> void:
	var nick := String(Net.player_names.get(peer_id, "Игрок %d" % peer_id))
	if health.downed:
		nick += "  ✚"
	if _name_tag.text != nick:
		_name_tag.text = nick
	_name_tag.visible = health.alive and visible
	var h: Array = Balance.NAME_TAG.height
	var want: float = float(h[2]) if stance == Stance.PRONE or health.downed else (float(h[1]) if stance == Stance.CROUCH else float(h[0]))
	_name_tag.position.y = lerpf(_name_tag.position.y, want, clampf(delta * 8.0, 0.0, 1.0))
	# вдали подпись не мельчает до нечитаемой: растёт с расстоянием до камеры
	var cam := get_viewport().get_camera_3d()
	if cam:
		var d := cam.global_position.distance_to(_name_tag.global_position)
		_name_tag.pixel_size = float(Balance.NAME_TAG.pixel) * clampf(d / float(Balance.NAME_TAG.near), 1.0, float(Balance.NAME_TAG.grow_max))


func _process(delta: float) -> void:
	if _name_tag:
		_tick_name_tag(delta)
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
	_tick_gear_look(delta)
	_tick_rung_sound()
	_tick_hands_bounce(delta)
	# смерть видна у всех peer: у хоста — по сигналу, у клиентов — по синхронизированному alive
	if not health.alive and _ragdoll == null and not _died_shown:
		_die()


func _physics_process(delta: float) -> void:
	if not is_local() or not is_alive():
		return
	# глаз до этого тика — от него камера ведёт глаз к новому положению (view_eye)
	_eye_tick_prev = eye_position()
	_eye_tick_ready = true
	_eye_dy *= exp(-float(Balance.STEP_UP.eye_rate) * delta)
	_tick_stance_eye(delta)
	# отладка (аудит уровня): полёт сквозь всё
	if Settings.cheat_fly:
		_fly(delta)
		return
	if seated:
		var mv := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		if (mv.length() > 0.2 or Input.is_action_just_pressed("crouch") or Input.is_action_just_pressed("vault")) and not ui_blocked():
			seated = false
			stance = Stance.STAND
			_apply_stance()
		else:
			velocity = Vector3.ZERO
			return
	_ladder_cd = maxf(0.0, _ladder_cd - delta)
	# перелезает, залезает наверх, шагает на лестницу или с неё: тело идёт по пути, ни стрельбы, ни шагов
	if _vault_t >= 0.0:
		_vault_t += delta / _vault_sec
		var vt := minf(_vault_t, 1.0)
		global_position = Climb.pos_at(_vault, vt) if _vault.has("pts") else Vault.pos_at(_vault, vt)
		velocity = Vector3.ZERO
		if _vault.has("yaw"):
			_body.rotation.y = lerp_angle(_body.rotation.y, float(_vault.yaw), minf(1.0, 10.0 * delta))
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
			_end_scripted_move()
		return
	if ladder != null:
		_tick_ladder(delta)
		return
	_dive_cd = maxf(0.0, _dive_cd - delta)
	_jump_cd = maxf(0.0, _jump_cd - delta)
	# обвес в руках с фонарями/лазерами — модель у всех; горит ли — выдаёт
	if weapon_slot != "":
		var we := weapon_entry()
		weapon_condition = WeaponCondition.percent(we)
		# гравировка и наклейки вместе: по этому словарю модель строится у всех игроков
		weapon_engraving = WeaponMark.marks(we)
		if _pm_action.is_empty():
			ammo = _state_rounds(weapon_slot)
			weapon_rounds = ammo
		if is_signal_launcher():
			weapon_signal_ammo = String(spec().get("ammo", "flare"))
		var mods: Dictionary = we.get("mods", {})
		if mods != weapon_mods:
			weapon_mods = mods
		var mag_look: String = WeaponMods.mag_state(we)
		if mag_look != weapon_mag:
			weapon_mag = mag_look
		var lit: bool = handheld_flashlight.emitting()
		var las := false
		for m in mods:
			lit = lit or (not WeaponCondition.broken(mods[m]) and bool((mods[m] as Dictionary).get("light", false)))
			las = las or (not WeaponCondition.broken(mods[m]) and bool((mods[m] as Dictionary).get("laser", false)))
		if lit != light_on:
			light_on = lit
		if las != laser_on:
			laser_on = las
	_aim_t = _aim_t + delta if aiming and weapon_id != "" else 0.0
	# наклон: Q/E только когда камера в глазах; в изометрии Q/E крутят камеру
	var lean_to := Input.get_axis("camera_left", "camera_right") if ads and not PauseMenu.shown else 0.0
	lean = move_toward(lean, lean_to, Balance.LEAN_SPEED * delta)
	# у стены — не дальше, чем пускает стена (подошёл к стене в наклоне — глаз отходит вместе с ней)
	if absf(lean) > 0.001:
		lean = signf(lean) * minf(absf(lean), lean_room(signf(lean)))
	var down := is_downed()
	if down:
		# раненый лежит; X (держать) — сдаться
		if stance != Stance.PRONE:
			stance = Stance.PRONE
			_apply_stance()
		aiming = Input.is_action_pressed("aim") and not grenade_equipped and not ui_blocked()
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
				_try_jump()
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
	elif velocity.y <= 0.0 and not (_dive_t >= 0.0 and _dive_t < 0.1):
		# в начале броска — подскок (иначе пол тут же гасит его)
		velocity.y = 0.0
	var was_airborne: bool = airborne
	var pre_pos := global_position
	var pre_floor := is_on_floor()
	var pre_vel := velocity
	_cart_contact.move_character(delta)
	# низкая ступень, бордюр, порожек — шагнуть без прыжка (и если капсула уже повисла на ребре)
	_ground_t = 0.0 if pre_floor else _ground_t + delta
	if _ground_t < 0.2 and velocity.y <= 0.3 and _dive_t < 0.0:
		_step_up(delta, pre_pos, pre_vel)
	airborne = not is_on_floor()
	# по земле: подъём и спуск тела глаз проходит плавно (ступенька не дёргает камеру)
	if _ground_t < 0.25 and not airborne:
		_eye_dy = clampf(_eye_dy - (global_position.y - pre_pos.y), -float(Balance.STEP_UP.eye_max), float(Balance.STEP_UP.eye_max))
	if was_airborne and not airborne:
		_jump_cd = float(Balance.JUMP.cooldown)
		NoiseBus.emit(global_position, float(Balance.JUMP.land_noise_m) * carry_stamina_k(), "step")
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


## Разброс выстрела, град (полуугол конуса, Hitscan). От бедра — полный (ЛЦУ включён — меньше,
## hip_spread); пока ствол доводят к глазу — спадает к прицельному. Через прицел одной пулей — доля
## Balance.ADS_SPREAD_K (0 — пуля идёт точно по линии прицеливания: промах только от отдачи, раскачки и
## дыхания, их держит игрок). Дробь в прицеле расходится по-прежнему — это сноп, а не ошибка стрелка;
## с завалом целятся по точке ЛЦУ, не через прицел, — точность между прицельной и «от бедра».
func shot_spread(spec: Dictionary, braced: bool) -> float:
	var hip := float(spec.hip_spread)
	var mult := hip
	var in_ads := ads and aiming
	if in_ads:
		var aimed := float(spec.ads_spread)
		if aim_cant:
			aimed = lerpf(aimed, hip, float(Balance.AIM_CANT.spread_k))
		elif int(spec.pellets) <= 1:
			aimed *= Balance.ADS_SPREAD_K
		mult = lerpf(hip, aimed, aim_progress())
	elif not ads:
		# изометрия, от бедра: угловой коллиматор — навскидку точнее, крупная оптика мешает
		if String(spec.sight) != "primary" and not bool(spec.scoped):
			mult *= float(Balance.ISO_AIM.offset_hip)
		elif bool(spec.scoped):
			mult *= float(Balance.ISO_AIM.scope_hip)
	var spread: float = float(spec.spread_deg) * mult * (float(spec.braced_spread) if braced else 1.0)
	if is_downed():
		spread *= Balance.DOWN_SPREAD
	# очередь раскачивает: от бедра сильно, в прицеле — меньше (ствол ведут глазами)
	return spread * (1.0 + minf(_bloom, Balance.RECOIL_BLOOM_MAX) * (Balance.RECOIL_BLOOM_ADS if in_ads else 1.0))


## Отдача выстрела: подброс и увод вбок. В прицеле невозвращаемая доля уходит во взгляд навсегда
## (очередь ползёт вверх — тяни вниз), возвращаемая — временно; от бедра — раскачка разброса.
func _apply_recoil(spec: Dictionary, braced: bool, rig: CameraRig) -> void:
	var k := float(spec.braced_kick) if braced else 1.0
	var in_ads := ads and aiming
	if in_ads:
		k *= Balance.ADS_RECOIL_SCALE
	# общая прибавка отдачи: на неё растут и взгляд, и толчок модели в руках; разброс — по прежней величине
	var gain: float = float(Balance.RECOIL_GAIN.ads if in_ads else Balance.RECOIL_GAIN.hip)
	var kv_base := float(spec.kick) * k * _rng.randf_range(0.85, 1.15)
	var kv := kv_base * gain
	k *= gain
	var rise := kv * (Balance.ADS_RECOIL_RISE_SCALE if in_ads else 1.0)
	var kh := float(spec.get("kick_h", 0.0)) * k * (_rng.randf_range(-1.0, 1.0) + float(spec.get("kick_bias", 0.0)))
	if in_ads:
		kh *= Balance.ADS_RECOIL_HORIZONTAL_SCALE
	var back := float(spec.get("recover", 0.5))
	if ads and rig:
		if not in_ads:
			# от бедра оружие гуляет в руках, взгляд почти стоит (подброс ствола — у модели, HAND_RECOIL)
			rise *= float(Balance.HAND_RECOIL.hip_cam_k)
			kh *= float(Balance.HAND_RECOIL.hip_cam_k)
		rig.add_recoil(rise * (1.0 - back), kh * (1.0 - back))
		_recoil += rise * back
		_recoil_h += kh * back
	else:
		_recoil += rise
	_bloom += kv_base * Balance.RECOIL_BLOOM
	# толчок модели в руках; в прицеле подскок и откат масштабирует CameraRig (ADS_RECOIL_FLIP / BACK).
	# Прибавка — после границ: у слабых стволов толчок упирался в нижнюю границу и не вырос бы
	kick_vis += clampf(kv_base / 0.05, 0.3, 1.8) * gain


## Подготовка при входе на уровень: тяжёлая сборка не приходится на нажатие клавиши ствола.
func prepare_weapon_model(entry: Dictionary) -> void:
	_cached_weapon_model(String(entry.id), entry.get("mods", {}), WeaponCondition.percent(entry), WeaponMods.mag_state(entry), WeaponMark.marks(entry))


func _cached_weapon_model(id: String, mods: Dictionary, dur: float, mag: String, marks: Dictionary) -> Node3D:
	var key: String = WeaponCondition.model_key(id, mods, dur, mag) + "|" + WeaponMark.key(marks)
	var model: Node3D = _weapon_model_cache.get(key) as Node3D
	if model == null:
		if (Balance.THROWN_LIGHTS as Dictionary).has(id):
			model = ThrownLight.held_model(id, true)
		else:
			model = WeaponModels.build(id, mods, 1, dur, mag, marks) if id != "" else Node3D.new()
		model.visible = false
		model.process_mode = Node.PROCESS_MODE_DISABLED
		_hand.add_child(model)
	_weapon_model_cache.erase(key)
	_weapon_model_cache[key] = model
	while _weapon_model_cache.size() > Balance.WEAPON_VISUAL_CACHE:
		var oldest: String = String(_weapon_model_cache.keys()[0])
		(_weapon_model_cache[oldest] as Node3D).queue_free()
		_weapon_model_cache.erase(oldest)
	return model


## Оружие следует за правой кистью Persona в любой стойке; без Persona — у груди.
func _update_hand() -> void:
	var shown_id: String = held_model_id()
	var key := WeaponCondition.model_key(shown_id, weapon_mods, weapon_condition, weapon_mag) + "|" + WeaponMark.key(weapon_engraving)
	var h := float(Balance.STANCE_HEIGHT[_stance_key()]) / float(Balance.STANCE_HEIGHT.stand)
	var yaw := _body.rotation.y
	if _weapon_model_id != key:
		if _weapon_model:
			_weapon_model.visible = false
			_weapon_model.process_mode = Node.PROCESS_MODE_DISABLED
		_weapon_model = _cached_weapon_model(shown_id, weapon_mods, weapon_condition, weapon_mag, weapon_engraving)
		_weapon_model.process_mode = Node.PROCESS_MODE_INHERIT
		var family: String = "pistol" if grenade_equipped else (String(WeaponDb.weapon(weapon_id).get("model", "rifle")) if weapon_id != "" else "rifle")
		var grip: Node3D = _animator.weapon_grip(family, weapon_id) if _animator else null
		var parent: Node3D = grip if grip else _hand
		if _weapon_model.get_parent() != parent:
			_weapon_model.reparent(parent, false)
		_weapon_rig = WeaponRig.find_on(_weapon_model)
		if _weapon_rig:
			_weapon_rig.set_ammo_state(weapon_rounds)
			# модель взята из кэша и помнит свою прежнюю пометку глушителя: сняли глушитель — у наблюдателей (и у
			# себя после смены оружия) он оставался виден. Пометка — по обвесу, с которым модель показана.
			if _weapon_rig.has_suppressor_part():
				var muzzle_mod: String = WeaponDb.mod_id(weapon_mods.get("muzzle", {}))
				_weapon_rig.set_suppressed(bool((WeaponDb.attachment(muzzle_mod).get("fx", {}) as Dictionary).get("suppressed", false)))
			if not _weapon_rig.sound_event.is_connected(_rig_sound):
				_weapon_rig.sound_event.connect(_rig_sound)
		_weapon_model_id = key
		# фонари и лазеры смотрят туда, куда целится игрок, а не куда анимация повернула ствол:
		# запоминаем их поворот внутри модели оружия
		_aimed.clear()
		for n in _weapon_model.find_children("*", "Node3D", true, false):
			if n is SpotLight3D or String(n.name).begins_with("LaserBeam"):
				if not n.has_meta("aim_rel"):
					n.set_meta("aim_rel", _weapon_model.global_basis.orthonormalized().inverse() * (n as Node3D).global_basis)
				_aimed.append(n as Node3D)
		if ads:
			set_first_person(true)
	_hand.visible = health.alive
	if _weapon_model:
		WeaponMods.update_condition(_weapon_model, weapon_mods)
	_weapon_model.visible = health.alive and (not grenade_equipped or grenade_in_hand)
	if _weapon_model is GrenadeModel:
		(_weapon_model as GrenadeModel).prepare(grenade_pin)
	ThrownLight.prepare_held(_weapon_model, grenade_pin)
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
	return mods.has(m) and mods[m] is Dictionary and not WeaponCondition.broken(mods[m]) and bool((mods[m] as Dictionary).get(kind, false))


## Шаги слышны AI: радиус по стойке и бегу, только пока реально движемся.
func _footsteps(delta: float) -> void:
	if airborne:
		_step_timer = 0.0
		return
	var moving := Vector2(velocity.x, velocity.z).length() > 0.3
	if not moving:
		_step_timer = 0.0
		return
	_step_timer -= delta
	if _step_timer > 0.0:
		return
	_step_timer = Balance.NOISE_STEP_INTERVAL
	var key := _stance_key()
	if key == "stand" and sprint_held():
		key = "sprint"
	# звук шагов — Footsteps (слышен у всех peer); здесь — шум, по которому слышат мародёры; вброд — громче
	var water_k: float = float(Balance.WATER.noise_k) if _water_depth() > float(Balance.WATER.ankle) else 1.0
	NoiseBus.emit(global_position, float(Balance.NOISE_STEP[key]) * water_k, "step")


## Хост сообщил: мародёр убит моей пулей — метка убийства (у клиента смерть видна позже выстрела).
func show_kill_marker() -> void:
	if is_local() and _camera_rig is CameraRig:
		(_camera_rig as CameraRig).show_hitmarker(true)


## Стрельба и перезарядка; гранату сначала выбирают отдельной клавишей, затем бросают мышью.
func _combat(delta: float) -> void:
	if Phone.blocks_combat(self):
		aiming = false
		_fire_queue = 0.0
		return
	if PauseMenu.shown:
		_cancel_grenade_prepare()
		return
	fire_timer -= delta
	fire_mode_switch_t = maxf(0.0, fire_mode_switch_t - delta)
	# обойма из окна рюкзака: руки вынимают / вставляют её и при открытом окне
	if not _pm_action.is_empty() and String(_pm_action.kind) in ["mag_out", "mag_in"]:
		_tick_hand_mag(delta)
		return
	if _reload_ui and reload_timer > 0.0:
		_tick_reload(delta, spec(), false)
		return
	_reload_ui = false
	# открыт рюкзак/обыск — клики идут в кнопки, не в спуск
	if not combat_enabled or ui_blocked():
		_cancel_grenade_prepare()
		_ui_blocked_ms = Time.get_ticks_msec()
		return
	if loadout_mode:
		_loadout_tick()
	var keys := weapon_keys()
	# цифра, которой только что выбрали пункт в окне (лечение: «1 — бинт»), — не команда оружию
	var fresh_ui: bool = Time.get_ticks_msec() - _ui_blocked_ms < 200
	for i in range(keys.size()):
		if Input.is_action_just_pressed("weapon_%d" % (i + 1)) and not fresh_ui and String(keys[i]) != "" and String(keys[i]) in allowed_weapons():
			# клавиша ствола, который уже в руках, — убрать его; ещё раз — достать
			if String(keys[i]) == weapon_slot and weapon_id != "":
				_holster()
			else:
				_switch(String(keys[i]))
	if Input.is_action_just_pressed("grenade") and not fresh_ui:
		_equip_throwable("grenade")
	# Y — зелёный химсвет в руку; G — ракетница в руки, двойное G — красный фальшфейер в руку (бросок — как граната)
	if Input.is_action_just_pressed("throw_chem") and not fresh_ui:
		_equip_throwable("chemlight")
	_tick_light_key(delta, fresh_ui)
	# лёжа раненым и таща раненого — только пистолет (нет — руки пусты, гранаты можно)
	if not loadout_mode and weapon_slot == "" and not _sandbox_picked and not grenade_equipped:
		# песочница: сразу в руках пистолет (клавиша 2), как было всегда
		_sandbox_picked = true
		_switch(sidearm_key() if sidearm_key() != "" else String(keys[0]), false)
	if not weapon_slot in allowed_weapons() and weapon_slot != "":
		var pistol := String(allowed_weapons()[0]) if not allowed_weapons().is_empty() else ""
		_switch(pistol, pistol != "")
	if grenade_equipped:
		_tick_grenade(delta)
		_tick_nvg(delta)
		_tick_breath(delta)
		return
	_tick_nvg(delta)
	_tick_breath(delta)
	_tick_osoka(delta)
	if weapon_id == "":
		return
	if Input.is_action_just_pressed("flashlight"):
		_toggle_tac("light")
	if Input.is_action_just_pressed("laser"):
		_toggle_tac("laser")
	if Input.is_action_just_pressed("toggle_sight"):
		_toggle_sight()
	if InputMap.has_action("fire_mode") and Input.is_action_just_pressed("fire_mode") and not ui_blocked() and bool(spec().get("thermal", false)):
		toggle_sight_channel()
	# пристрелка: в прицеле стрелки — щелчки барабанчиков
	if aiming and ads and not ui_blocked():
		for z: Array in [["zero_up", 0, 1], ["zero_down", 0, -1], ["zero_left", -1, 0], ["zero_right", 1, 0]]:
			if InputMap.has_action(String(z[0])) and Input.is_action_just_pressed(String(z[0])):
				zero_click(int(z[1]), int(z[2]))
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
		_tick_reload(delta, spec, true)
		return
	ammo_check_t = maxf(0.0, ammo_check_t - delta)
	# осмотр оружия (I): у ствола со своими клипами рук — клип осмотра; прицел, бег, выстрел, перезарядка — прерывают
	weapon_inspect_t = maxf(0.0, weapon_inspect_t - delta)
	if weapon_inspect_t > 0.0 and (aiming or sprint_held() or Input.is_action_pressed("fire") or Input.is_action_just_pressed("reload")):
		weapon_inspect_t = 0.0
	if InputMap.has_action("inspect_weapon") and Input.is_action_just_pressed("inspect_weapon") and weapon_inspect_t <= 0.0 			and not aiming and not mag_inspect and ViewmodelClips.available(weapon_id):
		weapon_inspect_t = float((WeaponDb.weapon(weapon_id).get("viewmodel", {}) as Dictionary).get("inspect_sec", 0.0))
	# проверка магазина: пока R держат — магазин в руке перед глазами; отпустили (или выстрел) — убрать
	if mag_inspect:
		if Input.is_action_pressed("reload") and not Input.is_action_pressed("fire"):
			ammo_check_t = maxf(ammo_check_t, 0.6)
			return
		mag_inspect = false
		inspect_turn = Vector2.ZERO
		# магазин вернулся в оружие — тот же звук, что в перезарядке
		_play_weapon_sound(spec, "mag_in", -6.0)
	# R: коротко — перезарядка (или устранить задержку), держать — проверить патроны
	if Input.is_action_just_pressed("reload"):
		if is_signal_launcher():
			_start_signal_reload(spec)
			return
		if mag_out() and not is_jammed():
			# магазин вынут: R сразу вставляет новый; держать R и нажимать дважды — без особых действий
			_reload_hold = -1.0
			_start_reload(spec)
			return
		_reload_hold = 0.0
	if _reload_hold >= 0.0:
		if Input.is_action_pressed("reload"):
			_reload_hold += delta
			if _reload_hold >= float(Balance.AMMO_CHECK.hold_sec):
				_reload_hold = -1.0
				if mag_out():
					return
				_check_ammo(spec)
				# у ствола с клипом проверки магазин остаётся в руке, пока держат R
				mag_inspect = ViewmodelClips.available(weapon_id)
			return
		_reload_hold = -1.0
		if is_jammed():
			_start_clear(spec)
		elif ammo < int(spec.mag) + (1 if _has_chamber(weapon_id) else 0):
			_start_reload(spec)
		return
	if InputMap.has_action("fire_mode") and Input.is_action_just_pressed("fire_mode"):
		cycle_fire_mode()
	# режим огня: АВ — пока держат спуск; ОД — по нажатию; «2» — нажатие даёт очередь из двух
	var mode := fire_mode()
	var trigger := Input.is_action_pressed("fire") if mode == "auto" else Input.is_action_just_pressed("fire")
	# ствол опущен «наискосок» (стойка или бег): нажатие поднимает оружие, выстрел — когда поднялось
	_fire_queue = maxf(0.0, _fire_queue - delta)
	if weapon_lowered > float(Balance.WEAPON_CARRY.fire_max):
		_burst_left = 0
		if trigger:
			raise_weapon()
			_fire_queue = float(Balance.WEAPON_CARRY.queue_sec)
		return
	if _fire_queue > 0.0:
		# короткое нажатие, пока ствол поднимался, — не теряется
		trigger = true
	_fire_queue = 0.0
	if mode == "burst":
		if trigger and _burst_left <= 0 and fire_timer <= 0.0:
			_burst_left = int(Balance.FIRE_MODES.burst)
		# очередь доходит до конца, даже если спуск уже отпустили
		trigger = _burst_left > 0
	else:
		_burst_left = 0
	if trigger and fire_timer <= 0.0:
		if is_jammed():
			fire_timer = 0.3
			_burst_left = 0
			_play_weapon_sound(spec, "jam", -8.0)
			return
		if ammo <= 0:
			# пусто — только сухой щелчок (по нажатию, не очередью); перезарядка — только по R
			fire_timer = float(spec.interval)
			_burst_left = 0
			if Input.is_action_just_pressed("fire"):
				_play_weapon_sound(spec, "dry_fire", -8.0)
			return
		_burst_left = maxi(0, _burst_left - 1)
		_fire(spec)


## Кадр идущей перезарядки (и устранения задержки): звуки по меткам, липучка подсумка, конец. keys — клавиши
## слушаются (второе быстрое R); при открытом рюкзаке — нет.
func _tick_reload(delta: float, spec: Dictionary, keys: bool) -> void:
	_reload_age += delta
	# второе быстрое R — быстрая перезарядка: старый магазин на землю
	if keys and Input.is_action_just_pressed("reload"):
		_try_fast_reload()
	if _velcro_at >= 0.0 and _reload_age >= _velcro_at:
		_velcro_at = -1.0
		_play_velcro()
	# быстрая перезарядка без кадра сброса в клипе: старый магазин вылетает запасным броском (пока хост не
	# убрал его в рюкзак — повтор на следующем кадре)
	if _reload_fast and not _mag_tossed and _toss_at >= 0.0 and _reload_age >= _toss_at:
		toss_old_mag({})
	reload_timer -= delta
	if _reload_kind != "clear":
		_play_reload_marks(spec)
	if _reload_kind == "clear" and not _clear_released and reload_timer <= float(Balance.WEAPON_WEAR.clear_sec) * (1.0 - float(Balance.WEAPON_WEAR.clear_release_at)):
		_clear_released = true
		_play_weapon_sound(spec, "clear_jam_release", -4.0)
		Audio.shell_drop(global_position, _side_dir(), 0.0, weapon_id)
	if reload_timer <= 0.0:
		_finish_reload(spec)


## Перезарядка: в снаряжении — смена магазина из рюкзака или досыпка россыпью (делает хост,
## Inventory.reload_slot); в песочнице — полный магазин. pick — магазин выбрал игрок в окне рюкзака
## ({role, idx, id}): меняется именно он, и перезарядка идёт при открытом окне.
func _start_reload(spec: Dictionary, pick: Dictionary = {}) -> void:
	if is_signal_launcher():
		_start_signal_reload(spec)
		return
	if not _pm_action.is_empty() or reload_timer > 0.0 or weapon_id == "":
		return
	_reload_pick = pick.duplicate(true)
	_reload_ui = not pick.is_empty()
	_reload_kind = "full"
	_reload_slot = weapon_slot
	_reload_empty = ammo <= 0
	_reload_fast = false
	_reload_age = 0.0
	_reload_old_mag = {}
	_mag_tossed = false
	_toss_at = -1.0
	_velcro_at = -1.0
	var from_pouch: bool = false
	_reload_insert = mag_out()
	var t: float = float(spec.get("reload_empty", spec.reload)) if _reload_empty else float(spec.reload)
	var chambered: bool = _has_chamber(weapon_id)
	if _reload_insert and not chambered:
		# старый магазин вынимать не надо — только вставить новый и дослать
		t *= float(Balance.RELOAD_INSERT.time_k)
	# Потраченные выстрелами патроны сохраняем до анимации: её отмена не возвращает боезапас.
	if chambered and _ws_dirty:
		_send_ws(weapon_slot)
	if loadout_mode:
		var e := weapon_entry()
		# магазин — из подсумков разгрузки или из рюкзака (Inventory.reload_slot берёт в том же порядке)
		var kind := "swap" if not _reload_pick.is_empty() else Gear.reload_kind(e, inventory.list_of("rig") + inventory.items)
		# новый магазин под рукой, в подсумке на броне, а не в рюкзаке за спиной
		var pouch_mag: bool = String(_reload_pick.role) == "rig" if not _reload_pick.is_empty() else inventory.rig_has_mag(weapon_slot)
		if kind == "":
			_say("Нет магазина к оружию" if _reload_insert else "Нечем зарядить: " + WeaponDb.caliber_name(String(spec.caliber)))
			_reload_insert = false
			return
		_reload_kind = kind
		_reload_rev = int(e.get("rev", 0))
		# новый магазин — из подсумка на броне (тогда звучит липучка), а не из рюкзака
		from_pouch = kind == "swap" and pouch_mag
		var standing: Dictionary = e.get("mag", {}) if e.get("mag") is Dictionary else {}
		if kind == "swap" and String(standing.get("id", "")) != "":
			# у ствола с патронником патрон в стволе остаётся — в старом магазине на один меньше
			var in_mag: int = ammo - (int(_ws_state(weapon_slot).get("chamber", 0)) if chambered else 0)
			_reload_old_mag = {"id": String(standing.id), "rounds": in_mag}
		_reload_wait = 1.5
		var st := _ws_state(weapon_slot)
		if not _reload_pick.is_empty():
			st["pick"] = _reload_pick.duplicate(true)
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
			_say("Заряженных магазинов нет — снаряжаю магазин патронами")
		# магазин не в подсумке, а в рюкзаке за спиной — доставать дольше
		elif kind == "swap" and not pouch_mag:
			t *= float(Balance.RIG.backpack_reload_k)
			if not _rig_hint_shown and is_local():
				_rig_hint_shown = true
				_say("Магазин из рюкзака — дольше. Держи магазины в подсумках разгрузки")
	# руки дрожат — дольше
	reload_timer = t * (1.0 + float(Balance.STRESS.reload_k) * stress_k())
	_plan_velcro(from_pouch)
	_animation_event("pistol_reload" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_reload")
	if chambered:
		_pm_action_seq += 1
		_pm_action = {"kind": "reload", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
			"state": _ws_state(weapon_slot), "empty": _reload_empty, "sent": false}
		_weapon_action("reload", _reload_empty, reload_timer)
	if _weapon_rig:
		return
	var clip_start: float = 0.0
	if _reload_insert and _camera_rig is CameraRig:
		clip_start = (_camera_rig as CameraRig).reload_swap_fraction(_reload_empty)
	_reload_audio.start(weapon_id, _reload_audio.mode(_reload_empty), reload_timer, _reload_insert, clip_start)
	if not _reload_audio.marks.is_empty():
		_play_reload_marks(spec)
		return
	Audio.play(String(spec.reload_sound), global_position)
	if _weapon_sound(spec, "breech_open") != "":
		_play_weapon_sound(spec, "breech_open", -4.0)
	elif _weapon_sound(spec, "mag_out") != "":
		_play_weapon_sound(spec, "mag_out", -4.0)
		_reload_audio.mark_played("mag_out")
	else:
		_play_weapon_sound(spec, "round_insert", -4.0)


## Второе R сразу после первого: перезарядка становится быстрой — короче в Balance.RELOAD_FAST.time_k раз,
## старый магазин падает на землю. Только смена отъёмного магазина (со снаряжением — когда есть запасной), при любом
## остатке в нём. У ствола с патронником (пистолеты) смена ещё не отправлена хосту — её запрос тот же, хост кладёт
## старый магазин в рюкзак, а по ответу он падает на землю (_accept_pm_result → _drop_old_mag).
func _try_fast_reload() -> void:
	var cfg: Dictionary = Balance.RELOAD_FAST
	var pm_reload: bool = not _pm_action.is_empty() and String(_pm_action.kind) == "reload" and not bool(_pm_action.get("sent", false))
	if _reload_fast or _reload_insert or _reload_age > float(cfg.tap_sec) or _reload_kind == "clear" or (not _pm_action.is_empty() and not pm_reload):
		return
	if loadout_mode and _reload_kind != "swap":
		return
	if WeaponDb.weapon(weapon_id).has("internal_mag"):
		return
	_reload_fast = true
	reload_timer = maxf(0.2, (reload_timer + _reload_age) * float(cfg.time_k) - _reload_age)
	if pm_reload:
		# модель в руках персонажа (и у напарников) — та же смена на оставшееся время
		_weapon_action("reload", _reload_empty, reload_timer)
	_mag_tossed = false
	# когда магазин вылетит: по кадру сброса клипа рук, а нет его — на доле перезарядки из Balance
	var by_clip: bool = is_local() and _camera_rig is CameraRig and (_camera_rig as CameraRig).reload_drop_by_clip(_reload_empty)
	_toss_at = -1.0 if by_clip else (reload_timer + _reload_age) * float(Balance.MAG_TOSS.fallback_at)
	_reload_audio.switch_to(weapon_id, _reload_audio.mode(_reload_empty, true), reload_timer, _reload_age)
	# быстрая: сначала берут новый магазин из подсумка (им же выбивают старый) — липучка сразу
	if _velcro_at >= 0.0:
		_velcro_at = -1.0
		_play_velcro()
	_say("Быстрая перезарядка — старый магазин на землю")


## Когда звучит липучка подсумка (from_pouch — новый магазин из подсумка): вставить в пустую шахту — сразу
## (вынимать нечего), иначе — когда старый магазин скрылся из вида: кадр подмены клипа рук (ВЕРАС), фаза
## mag_hidden ствола с механикой (ПМ, Glock), у остальных — Balance.POUCH_VELCRO.hidden_k.
func _plan_velcro(from_pouch: bool) -> void:
	_velcro_at = -1.0
	if not from_pouch:
		return
	if _reload_insert:
		_velcro_at = 0.0
		return
	_velcro_at = reload_timer * velcro_fraction()


## Доля перезарядки до момента, когда старый магазин скрылся из вида (см. _plan_velcro).
func velcro_fraction() -> float:
	if is_local() and _camera_rig is CameraRig:
		var f: float = (_camera_rig as CameraRig).reload_swap_fraction(_reload_empty)
		if f >= 0.0:
			return f
	var phases: Dictionary = (WeaponDb.weapon(weapon_id).get("rig", {}) as Dictionary).get("reload", {}) as Dictionary
	if phases.has("mag_hidden"):
		return float(phases.mag_hidden)
	return float(Balance.POUCH_VELCRO.hidden_k)


## Отрыв липучки подсумка — у себя и у напарников (звук pouch_velcro, запись назначает владелец в Sonora).
func _play_velcro() -> void:
	velcro_count += 1
	Audio.play("pouch_velcro", global_position + Vector3.UP * float(Balance.POUCH_VELCRO.height_m))
	if Net.is_networked() and is_multiplayer_authority():
		Net.broadcast_scene(self, &"_rpc_velcro", [], false)


@rpc("authority", "call_remote", "unreliable_ordered")
func _rpc_velcro() -> void:
	Audio.play("pouch_velcro", global_position + Vector3.UP * float(Balance.POUCH_VELCRO.height_m))


## Быстрая перезарядка закончена. Обычно старый магазин к этому времени уже вылетел настоящим телом
## (toss_old_mag — по кадру сброса клипа рук или запасным броском); не вылетел — бросается сейчас, а если и это
## невозможно — по-старому ложится под ноги (Raid.spawn_loose; в убежище — HideoutLevel.request_drop_entry).
func _drop_old_mag() -> void:
	if not _reload_fast:
		return
	# магазин уже вылетел телом (по клипу рук или запасным броском) — звук прозвучит при его ударе о пол
	if _mag_tossed or toss_old_mag({}):
		_reload_fast = false
		_mag_tossed = false
		return
	_reload_fast = false
	_play_weapon_sound(spec(), "mag_drop")
	if not loadout_mode or _reload_old_mag.is_empty():
		return
	var h := items_host()
	if h == null or not h.has_method("request_drop_entry"):
		return
	var at: Dictionary = _old_mag_place()
	if not at.is_empty():
		h.call("request_drop_entry", String(at.where), int(at.idx), true)


## Где у игрока лежит старый магазин этой перезарядки: хост убрал его в сумку сброса разгрузки или в рюкзак.
## {where, idx}; пусто — ещё не убрал (ответ хоста в пути) или его нет.
func _old_mag_place() -> Dictionary:
	if _reload_old_mag.is_empty():
		return {}
	for where: String in ["dump", "backpack", "rig"]:
		var list: Array = inventory.list_of(where)
		for i in range(list.size()):
			var it: Dictionary = list[i]
			if String(it.get("id", "")) == String(_reload_old_mag.id) and it.has("rounds") and int(it.rounds) == int(_reload_old_mag.rounds):
				return {"where": where, "idx": i}
	return {}


## Старый магазин быстрой перезарядки покидает оружие настоящим телом: хост забирает его из рюкзака и пускает
## TossedItem (Raid / HideoutLevel.request_toss_entry). launch — {pos, rot, vel, spin} в мире: где магазин виден
## в руках и как двигался в клипе (ViewmodelClips.track_spare); пусто — запасной бросок вправо числами
## Balance.MAG_TOSS. false — вылетать нечему (песочница) или хост магазин ещё не убрал: позвать снова.
func toss_old_mag(launch: Dictionary) -> bool:
	if not _reload_fast or _mag_tossed or not loadout_mode:
		return false
	var h := items_host()
	if h == null or not h.has_method("request_toss_entry"):
		return false
	# у ствола с патронником смена уходит хосту в конце перезарядки: пока он не сменил магазин (ревизия записи
	# ствола прежняя), в рюкзаке лежат только запасные — такой же по виду и остатку вылетел бы вместо старого
	if _has_chamber(weapon_id) and int(_base_entry(_reload_slot).get("rev", 0)) == _reload_rev:
		return false
	var at: Dictionary = _old_mag_place()
	if at.is_empty():
		return false
	var data: Dictionary = launch.duplicate() if not launch.is_empty() else _fallback_toss()
	data["sound"] = _weapon_sound(spec(), "mag_drop")
	_mag_tossed = true
	mag_body_seen = false
	h.call("request_toss_entry", String(at.where), int(at.idx), data)
	return true


## Запасной бросок старого магазина — у ствола без клипа рук или без кадра сброса в нём: от оружия перед
## стрелком вправо (оси камеры; у чужого игрока — оси корпуса на высоте глаз).
func _fallback_toss() -> Dictionary:
	var cfg: Dictionary = Balance.MAG_TOSS
	var cam: Camera3D = get_viewport().get_camera_3d() if is_local() and is_inside_tree() else null
	var view: Transform3D = cam.global_transform.orthonormalized() if cam != null \
			else Transform3D(Basis(Vector3.UP, body_yaw() + PI), eye_position())
	var p: Array = cfg.fallback_pos
	var v: Array = cfg.fallback_vel
	var s: Array = cfg.fallback_spin
	# оружие в руках развёрнуто на 180° относительно осей камеры
	return {"pos": view * Vector3(float(p[0]), float(p[1]), float(p[2])), "rot": Quaternion(view.basis * Basis(Vector3.UP, PI)),
		"vel": view.basis * Vector3(float(v[0]), float(v[1]), float(v[2])) + velocity,
		"spin": view.basis * Vector3(float(s[0]), float(s[1]), float(s[2]))}


## Задержка: передёрнуть (R) — патроны не тратятся.
func _start_clear(spec: Dictionary) -> void:
	_reload_kind = "clear"
	_reload_slot = weapon_slot
	reload_timer = float(Balance.WEAPON_WEAR.clear_sec)
	_clear_released = false
	_play_weapon_sound(spec, "clear_jam", -4.0)


func _finish_reload(spec: Dictionary) -> void:
	_reload_pick = {}
	# с пустым магазином и на задержке рукоятку заряжания оттягивают — рама откидывает шторку
	if _reload_kind == "clear" or _reload_empty:
		_open_dust_cover(_reload_slot)
	if (_has_chamber(weapon_id) or is_signal_launcher()) and _reload_kind != "clear":
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
		_drop_old_mag()
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
	_drop_old_mag()


func _finish_reload_sounds(specification: Dictionary) -> void:
	if not _reload_audio.marks.is_empty():
		_reload_audio.clear()
		return
	if _weapon_sound(specification, "breech_close") != "":
		_play_weapon_sound(specification, "breech_close", -4.0)
		return
	_play_weapon_sound(specification, "mag_in", -4.0)
	_play_weapon_sound(specification, "charge", -5.0)


func _play_reload_marks(specification: Dictionary) -> void:
	for slot: String in _reload_audio.due(reload_timer):
		var hook: String = _weapon_sound(specification, slot)
		var stream: AudioStream = _reload_audio.recording(_reload_audio.marks[slot])
		Audio.play(hook, global_position, _reload_audio.gain(slot), 0.0, null, stream)


## Только единственный риг модели на теле озвучивает действие — модель перед камерой молчит.
func _rig_sound(slot: String) -> void:
	if not health.alive or weapon_id == "":
		return
	var specification: Dictionary = spec() if is_local() else WeaponStats.compute({"id": weapon_id, "mods": weapon_mods})
	var recording: AudioStream = _weapon_rig.reload_recording(slot) if is_instance_valid(_weapon_rig) else null
	Audio.play(_weapon_sound(specification, slot), global_position, float(Balance.PM_ACTION.sound_db),
		0.0, null, recording)


## Одно событие приводит обе модели к одинаковой фазе; у чужого игрока работает тот же WeaponRig.
func _weapon_action(action: String, flag: bool = false, duration: float = 0.0, rounds: int = -1, replicate: bool = true) -> void:
	if _weapon_rig:
		match action:
			"shot":
				_weapon_rig.play_shot(rounds)
			"reload":
				_weapon_rig.play_reload(flag, duration)
			"mag_out":
				_weapon_rig.play_reload(false, duration, "out")
			"mag_in":
				_weapon_rig.play_reload(flag, duration, "in")
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
		Net.broadcast_scene(self, &"_rpc_weapon_action", [action, flag, duration, rounds], false)


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


## Магазин оружия в слоте slot можно вынимать и вставлять руками прямо из окна рюкзака: оно в руках у своего игрока,
## со снаряжением, магазин отъёмный. Пистолеты с ригом и патронником (ПМ, АСТЕН-919) — частями фаз рига
## (_hand_mag_rig), остальное — по таймеру перезарядки: клипы рук, у кого они есть, звук и подпись.
func hand_mag_ready(slot: String) -> bool:
	var weapon: Dictionary = WeaponDb.weapon(weapon_id)
	return is_local() and loadout_mode and slot != "" and slot == weapon_slot and weapon_id != "" and not grenade_equipped \
		and not is_signal_launcher() and weapon.has("mag_if") and not weapon.has("internal_mag")


## Действия с магазином показывает риг модели (части фаз перезарядки), предметы меняются по окончании движения.
func _hand_mag_rig() -> bool:
	return _has_chamber(weapon_id) and (WeaponDb.weapon(weapon_id).get("rig", {}) as Dictionary).has("reload")


func _hand_mag_busy() -> bool:
	return not health.alive or is_downed() or reload_timer > 0.0 or not _pm_action.is_empty()


## «Вынуть обойму» у оружия в руках: руки вынимают магазин, по окончании хост кладёт его в рюкзак. "" — начато,
## иначе — почему нет.
func hand_mag_eject() -> String:
	if not hand_mag_ready(weapon_slot):
		return "Оружие не в руках"
	if _hand_mag_busy():
		return "Руки заняты"
	if mag_out():
		return "Магазина в оружии нет"
	if _ws_dirty:
		_send_ws(weapon_slot)
	var specification: Dictionary = spec()
	var duration: float = float(specification.reload) * float(Balance.HAND_MAG.out_k)
	var by_rig: bool = _hand_mag_rig()
	_pm_action_seq += 1
	_pm_action = {"kind": "mag_out", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
		"state": _ws_state(weapon_slot), "remaining": duration, "timer": not by_rig, "sent": false}
	mag_inspect = false
	_animation_event("pistol_reload" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_reload")
	if by_rig:
		_weapon_action("mag_out", false, duration)
	else:
		# без рига: руки (клипы) и подпись идут по таймеру перезарядки, вид — «вынуть»
		_reload_kind = "eject"
		_reload_slot = weapon_slot
		_reload_empty = false
		_reload_insert = false
		_reload_fast = false
		_reload_audio.clear()
		reload_timer = duration
		_play_weapon_sound(specification, "mag_out", -4.0)
	return ""


## Магазин из сетки role[idx] своего инвентаря — в оружие в руках: в пустую шахту — вставить, вместо стоящего —
## перезарядка этим магазином (старый уходит в рюкзак). Патронник пуст — с досылом. "" — начато, иначе — почему нет.
func hand_mag_insert(role: String, idx: int) -> String:
	if not hand_mag_ready(weapon_slot):
		return "Оружие не в руках"
	if _hand_mag_busy():
		return "Руки заняты"
	var list: Array = inventory.list_of(role)
	if not role in ["backpack", "pocket", "buffer", "rig", "dump"] or idx < 0 or idx >= list.size():
		return "Отсюда магазин в оружие не вставить"
	var item: Dictionary = list[idx]
	if not item.has("rounds") or not WeaponDb.mag_fits(weapon_id, String(item.id)):
		return "Магазин не подходит"
	var specification: Dictionary = spec()
	if not _hand_mag_rig():
		# без рига: обычная перезарядка выбранным магазином (в пустую шахту — только вставить), идёт при открытом окне
		_start_reload(specification, {"role": role, "idx": idx, "id": String(item.id)})
		return "" if reload_timer > 0.0 else "Не получилось начать перезарядку"
	if _ws_dirty:
		_send_ws(weapon_slot)
	var state: Dictionary = _ws_state(weapon_slot)
	var swap: bool = not mag_out()
	# патронов нет ни в стволе, ни в магазине — затвор на задержке: новый магазин досылают
	var charge: bool = ammo <= 0 and int(item.get("rounds", 0)) > 0
	var duration: float = float(specification.get("reload_empty", specification.reload)) if charge else float(specification.reload)
	if not swap:
		duration *= float(Balance.HAND_MAG.in_k)
	_pm_action_seq += 1
	_pm_action = {"kind": "mag_in", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id, "state": state,
		"role": role, "idx": idx, "mag_id": String(item.id), "remaining": duration, "sent": false}
	mag_inspect = false
	_animation_event("pistol_reload" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_reload")
	_weapon_action("reload" if swap else "mag_in", charge, duration)
	return ""


## Движение рук с обоймой идёт своим временем (и при открытом рюкзаке); кончилось — перенос предметов у хоста.
func _tick_hand_mag(delta: float) -> void:
	_pm_action.remaining = float(_pm_action.remaining) - delta
	var by_timer: bool = bool(_pm_action.get("timer", false))
	if by_timer and not bool(_pm_action.get("sent", false)):
		reload_timer = maxf(0.0, float(_pm_action.remaining))
	if float(_pm_action.remaining) <= 0.0 and not bool(_pm_action.get("sent", false)):
		if by_timer:
			reload_timer = 0.0
			_reload_kind = ""
		_commit_pm_action()


func _tick_suppressor(delta: float) -> void:
	_pm_action.remaining = float(_pm_action.remaining) - delta
	if float(_pm_action.remaining) <= 0.0:
		_commit_pm_action()


## Прерывание до подтверждения не трогает инвентарь; уже подтверждённый перенос остаётся целым.
func cancel_weapon_action() -> void:
	_cancel_grenade_prepare()
	var had_action: bool = not _pm_action.is_empty() or reload_timer > 0.0 or (_weapon_rig and _weapon_rig.is_busy())
	_pm_action.clear()
	_reload_audio.clear()
	reload_timer = 0.0
	_reload_hold = -1.0
	_reload_fast = false
	_reload_insert = false
	_reload_pick = {}
	_reload_ui = false
	mag_inspect = false
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
		if not _has_chamber(wid) and wid != "signal_launcher":
			return {"error": "У оружия другая схема перезарядки"}
		if wid == "signal_launcher" and not WeaponDb.ammo_fits(wid, String(state.get("reload_ammo", "flare"))):
			return {"error": "Неверный патрон для ракетницы"}
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
						Raid.current.spawn_drop(global_position, Raid.DROP_NAME, [spill], LootContainer.Look.BAG)
					else:
						# Стенд без мира рейда сохраняет вынутый магазин в буфере.
						inventory.buffer = inventory.buffer + [spill]
		else:
			var fresh: Dictionary = Gear.normalize_chamber(base)
			var mag: Dictionary = fresh.get("mag", {})
			mag["rounds"] = WeaponDb.capacity(fresh)
			fresh["mag"] = mag
			if wid == "signal_launcher":
				mag["ammo"] = String(state.get("reload_ammo", "flare"))
				fresh["signal_spent"] = false
			else:
				fresh["chamber"] = int(state.get("chamber", 0))
				fresh["chamber_ammo"] = String(state.get("chamber_ammo", ""))
				Gear.chamber_round(fresh)
			Gear._bump(fresh)
			sandbox_weapons[slot] = fresh
	elif kind == "mag_out":
		if not loadout_mode or WeaponDb.weapon(wid).has("internal_mag") or wid == "signal_launcher":
			return {"error": "Магазин этого оружия так не вынимают"}
		inventory.apply_weapon_state(slot, state)
		if not inventory.strip_equipped(slot, "mag"):
			return {"error": "Некуда положить магазин — освободи место в рюкзаке"}
	elif kind == "mag_in":
		if not loadout_mode or not _has_chamber(wid):
			return {"error": "Магазин в это оружие так не вставляют"}
		var mag_error: String = inventory.hand_mag_insert(slot, state, String(request.get("role", "")),
			int(request.get("idx", -1)), String(request.get("mag_id", "")))
		if mag_error != "":
			return {"error": mag_error}
	elif kind == "signal_shot":
		return _host_signal_shot(slot, base, request)
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
	# в тире рюкзак — копия профиля: глушитель из него не ставим, иначе вещь задвоится или пропадёт
	if in_range_mode():
		return "В тире насадки не меняют"
	var entry: Dictionary = sandbox_weapons[slot]
	var list: Array = inventory.items.duplicate(true)
	var updated: Dictionary
	if not install:
		var removed: Array = Gear.strip(entry, "mod:muzzle")
		if (removed[1] as Dictionary).is_empty() or ItemDb.add_to(list, removed[1], inventory.backpack_grid()) == 0:
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
	if action in ["reload", "mag_out", "mag_in"]:
		_weapon_action("finish_reload", false, 0.0, ammo)
	if action == "reload":
		# быстрая перезарядка ствола с патронником: хост убрал старый магазин в рюкзак — он падает на землю
		_drop_old_mag()
	elif action == "signal_shot":
		# The host broadcasts the accepted visual shot once to all scene peers.
		pass
	else:
		_weapon_action("suppressed", bool(spec().get("suppressed", false)))
		_weapon_action("cancel", false, 0.0, ammo)
	_send_ws(weapon_slot)


## T / L: все фонари (kind light) или лазеры (laser) на оружии в руках — вкл/выкл разом.
func _toggle_tac(kind: String) -> void:
	if kind == "light" and String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL":
		var result: String = handheld_flashlight.toggle()
		if result == "нет":
			_say("Нет фонаря в вещах")
		else:
			Audio.play("tac_click", global_position, -14.0)
		return
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


## O или СКМ от первого лица: основной / угловой / боковые прицелы. Прицеливание не
## сбрасывается — камера переводит линию прицеливания прямо (CameraRig, SIGHT_SWITCH_SEC).
## Последняя ступень круга — «с завалом» (aim_cant): есть и у ствола с одним прицелом.
func toggle_sight() -> void:
	if weapon_id == "":
		return
	var e := weapon_entry()
	var sights := WeaponStats.sights_of(e)
	if aim_cant:
		# с завала — снова к основному прицелу
		aim_cant = false
		if sights.size() > 1 and _ws.has(weapon_slot):
			_ws[weapon_slot].sight = String(sights[0])
			_send_ws(weapon_slot)
		_say(WeaponStats.sight_name(String(sights[0]), e) + " прицел")
		Audio.play("sight_switch", global_position, -16.0)
	elif sights.size() < 2 or WeaponStats.active_sight(e) == String(sights[sights.size() - 1]):
		aim_cant = true
		_say("С завалом: автомат на бок, огонь по точке ЛЦУ")
		Audio.play("sight_switch", global_position, -16.0)
	else:
		_toggle_sight()


## X с тепловизором на оружии: рычажок переключателя «ДЕНЬ / ТЕПЛО» — экран окуляра гаснет на миг и показывает
## другой канал (CameraRig._update_display); звук — действие sight_channel модели, без записи — тишина.
func toggle_sight_channel() -> void:
	sight_thermal = not sight_thermal
	_play_weapon_sound(spec(), "sight_channel", -6.0)
	_say("Тепловизор: %s" % ("ТЕПЛО — тепловой канал" if sight_thermal else "ДЕНЬ — дневной канал"))


func _toggle_sight() -> void:
	var e := weapon_entry()
	var sights := WeaponStats.sights_of(e)
	if sights.size() < 2:
		return
	var cur := WeaponStats.active_sight(e)
	var nxt := String(sights[(sights.find(cur) + 1) % sights.size()])
	_ws[weapon_slot].sight = nxt
	var mount: String = WeaponStats.sight_mount(nxt, e)
	var name := ItemDb.item_name(WeaponDb.mod_id((e.mods as Dictionary).get(mount, ""))) if (e.mods as Dictionary).has(mount) else "штатный"
	_say(WeaponStats.sight_name(nxt, e) + ": " + name)
	Audio.play("sight_switch", global_position, -16.0)
	_send_ws(weapon_slot)


## Колесо при ADS: только активная регулируемая оптика. Выбор переживает отпускание ПКМ,
## смену оружия, перезарядку и сохранение; хост получает его вместе с состоянием оружия.
func adjust_scope_zoom(direction: int) -> bool:
	if not is_local() or not is_alive() or not ads or not aiming or aim_cant or weapon_id == "" or ui_blocked():
		return false
	var stats: Dictionary = spec()
	if not bool(stats.get("scoped", false)) or float(stats.zoom_max) <= float(stats.zoom_min):
		return false
	var selected: float = clampf(float(stats.zoom) + direction * float(Balance.SCOPE_ZOOM.step), float(stats.zoom_min), float(stats.zoom_max))
	if is_equal_approx(selected, float(stats.zoom)):
		return true
	var mount: String = WeaponStats.sight_mount(String(stats.sight), weapon_entry())
	var st: Dictionary = _ws[weapon_slot]
	(st.optic_zoom as Dictionary)[mount] = selected
	_ws_dirty = true
	_ws_sync_t = float(Balance.SCOPE_ZOOM.sync_sec)
	Audio.play_ui("ui_click")
	if in_range_mode() and range_own_slot != "":
		_push_own_sight_state({"optic_zoom": {mount: selected}})
	return true


## Клавиши 1/2/3/5: в песочнице — автомат, пистолет, дробовик, винтовка; со
## снаряжением — [основное, пистолет] (слоты; "" — пусто).
func weapon_keys() -> Array:
	if not loadout_mode:
		return [RANGE_KEY] if in_range_mode() else WeaponDb.sandbox()
	# клавиши weapon_1…4 (1, 2, 3, 5): оружие 1, оружие 2, пистолет, ракетница (граната — своя клавиша 4)
	var keys: Array = []
	for slot: String in ItemDb.WEAPON_SLOTS:
		keys.append(slot if inventory.slot_weapon(slot) != "" else "")
	return keys


## Ключ пистолета (клавиша 2): раненым и таща раненого — только он; "" — пистолета нет.
func sidearm_key() -> String:
	if loadout_mode:
		return "sidearm" if inventory.slot_weapon("sidearm") != "" else ""
	if in_range_mode():
		return RANGE_KEY if String(WeaponDb.weapon(String(range_weapon.get("id", ""))).get("class", "")) == "PISTOL" else ""
	for k in WeaponDb.sandbox():
		if String(WeaponDb.weapon(String(k)).get("class", "")) == "PISTOL":
			return String(k)
	return ""


func grenade_count() -> int:
	if in_range_mode():
		return 0
	return inventory.count("grenade") if loadout_mode else grenades


## Тир убежища: выдан ли ствол стойки тира (в руках только он, патроны без счёта).
func in_range_mode() -> bool:
	return not range_weapon.is_empty()


## Тир: взять ствол стойки (запись оружия из пресета). Своё снаряжение остаётся в профиле нетронутым:
## состояние оружия в руках сначала уходит в профиль, затем игрок переходит на «песочницу» с одним
## этим стволом — вещи и патроны рюкзака тир не расходует.
func set_range_weapon(entry: Dictionary, own_slot: String = "") -> void:
	if entry.is_empty():
		return
	range_own_slot = own_slot
	cancel_weapon_action()
	if loadout_mode:
		flush_weapon_state()
	range_weapon = entry.duplicate(true)
	loadout_mode = false
	sandbox_weapons = {RANGE_KEY: range_weapon.duplicate(true)}
	_ws.erase(RANGE_KEY)
	_pm_entries.erase(RANGE_KEY)
	weapon_slot = ""
	_switch(RANGE_KEY)


## Тир: сдать ствол стойки — в руки возвращается своё снаряжение из профиля.
func clear_range_weapon() -> void:
	if not in_range_mode():
		return
	cancel_weapon_action()
	_cancel_grenade_prepare()
	range_weapon = {}
	range_own_slot = ""
	sandbox_weapons = {}
	_ws.erase(RANGE_KEY)
	_pm_entries.erase(RANGE_KEY)
	loadout_mode = true
	if weapon_id != "":
		_play_weapon_sound(spec(), "holster", -6.0)
	weapon_slot = ""
	weapon_id = ""


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
	# с клипом проверки магазин вынимают из оружия — звук вытаскивания, как в перезарядке; без клипа — одиночный щелчок
	if ViewmodelClips.available(weapon_id) and _weapon_sound(spec, "mag_out") != "":
		_play_weapon_sound(spec, "mag_out", -6.0)
	else:
		_play_weapon_sound(spec, "mag_check", -12.0)
	if is_local():
		# патроны вперемешку — видно и какие сверху
		var mag: Dictionary = weapon_entry().get("mag", {}) if weapon_entry().get("mag") is Dictionary else {}
		var types: String = Gear.mag_types_text(mag)
		_say("Магазин: " + ammo_check_text + (" · " + types if types != "" else ""))


## Запасных магазинов к оружию в руках в рюкзаке (сколько в них патронов — не видно).
func spare_mags() -> int:
	var n := 0
	for it in inventory.list_of("rig") + inventory.items:
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
	if grenade_equipped:
		return
	if holstered:
		# убранный ствол сам в руки не возвращается, пока он есть в слоте
		if weapon_slot != "" and not _base_entry(weapon_slot).is_empty():
			return
		holstered = false
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


## Убрать оружие из рук (за спину / в кобуру): состояние уходит хосту, как при смене; слот остаётся.
func _holster() -> void:
	handheld_flashlight.stow()
	if weapon_id == "":
		return
	cancel_weapon_action()
	_cancel_grenade_prepare()
	aim_cant = false
	if weapon_slot != "" and _ws.has(weapon_slot):
		_send_ws(weapon_slot)
	_play_weapon_sound(spec(), "holster", -6.0)
	holstered = true
	weapon_id = ""
	reload_timer = 0.0
	_aim_t = 0.0


## Руки пусты (оружие убрано или его нет): бежит быстрее и дольше.
func hands_free() -> bool:
	return weapon_id == "" and not grenade_equipped and not is_downed() and not is_burdened()


## Смена оружия: состояние прежнего уходит хосту, перезарядка прерывается.
func _switch(key: String, sound: bool = true) -> void:
	if key == weapon_slot and weapon_id != "" and not _base_entry(key).is_empty():
		return
	handheld_flashlight.stow()
	grenade_equipped = false
	grenade_in_hand = false
	_cancel_grenade_prepare()
	holstered = false
	cancel_weapon_action()
	aim_cant = false
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
	_burst_left = 0
	fire_mode_switch_t = 0.0
	if is_signal_launcher():
		fire_timer = 23.0 / 30.0
		weapon_signal_ammo = String((e.get("mag", {}) as Dictionary).get("ammo", "flare"))
	if sound and weapon_id != "":
		_play_weapon_sound(spec(), "draw", -6.0)
		_animation_event("pistol_draw" if String(WeaponDb.weapon(weapon_id).get("class", "")) == "PISTOL" else "rifle_draw")


func _fire(spec: Dictionary) -> void:
	if is_signal_launcher():
		_fire_signal(spec)
		return
	if is_manpads():
		_fire_osoka(spec)
		return
	if bool(spec.get("broken", false)):
		fire_timer = float(spec.interval)
		_say("Оружие сломано — нужен ремонт на верстаке")
		return
	# Ствол отведён от преграды: не расходовать патрон и не стрелять из камеры сквозь неё.
	if weapon_obstruction > float(Balance.WEAPON_CLEARANCE.fire_threshold):
		return
	if String(WeaponDb.weapon(weapon_id).get("class", "")) != "PISTOL":
		_animation_event("rifle_fire")
	var st: Dictionary = _ws[weapon_slot]
	if _has_chamber(weapon_id):
		# После вставки или снаряжения магазина патронник может ещё быть пустым.
		# Перед выстрелом переносим патрон из магазина, сохраняя общий боезапас.
		if int(st.get("chamber", 0)) <= 0:
			if int(st.rounds) <= 0:
				return
			st["chamber_ammo"] = _take_round(st)
			st["chamber"] = 1
		st["chamber"] = 0
		st["chamber_ammo"] = ""
		if int(st.rounds) > 0:
			st["chamber_ammo"] = _take_round(st)
			st["chamber"] = 1
	else:
		_take_round(st)
	_open_dust_cover(weapon_slot)
	ammo = _state_rounds(weapon_slot)
	weapon_rounds = ammo
	_weapon_action("shot", ammo <= 0, 0.0, ammo, false)
	var worn_entry: Dictionary = entry_of(weapon_slot)
	WeaponCondition.wear_shots(worn_entry, 1)
	st.dur = WeaponCondition.percent(worn_entry)
	st["shots"] = int(st.get("shots", 0)) + 1
	for mount: Variant in worn_entry.get("mods", {}):
		(st.mod_dur as Dictionary)[mount] = WeaponCondition.percent(worn_entry.mods[mount])
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
	# пристрелка: ноль сбит — пули уходят от точки прицеливания на поправку экземпляра (Gear.zero_offset)
	var zero_moa: Vector2 = Gear.zero_offset(worn_entry)
	if zero_moa != Vector2.ZERO:
		var z_right: Vector3 = dir.cross(Vector3.UP)
		if z_right.length() > 0.001:
			z_right = z_right.normalized()
			var z_up: Vector3 = z_right.cross(dir).normalized()
			dir = (dir + z_right * tan(deg_to_rad(zero_moa.x / 60.0)) + z_up * tan(deg_to_rad(zero_moa.y / 60.0))).normalized()
	var exclude: Array[RID] = [get_rid()]
	# сидя/лёжа на сошках — разброс и отдача меньше
	var braced := stance != Stance.STAND
	var spread: float = shot_spread(spec, braced)
	var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DEBRIS
	var muzzle := _muzzle_world()
	var rig := _camera_rig as CameraRig
	var marked := false
	last_shot_ms = Time.get_ticks_msec()
	var bullet := {"pen": float(spec.pen), "armor_dmg": float(spec.armor_dmg), "src": {"kind": "player", "peer": peer_id},
		"falloff": spec.get("falloff", []), "point_blank": spec.get("point_blank", []), "overkill": float(spec.damage) >= Balance.OVERKILL_DAMAGE}
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
	if ammo <= 0 and _weapon_rig == null:
		_play_weapon_sound(spec, "bolt_lock", -5.0)
	# остальным — то же (пули и урон уже посчитаны здесь и у хоста)
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_shot_fx", [muzzle, String(spec.sound), float(spec.db), float(spec.flash), String(spec.cycle_sound), _weapon_sound(spec, "mechanism"), ammo], false)


## ПЗРК в руках («manpads» у ствола в data/weapons.json — «Осока»).
func is_manpads() -> bool:
	return weapon_id != "" and bool(WeaponDb.weapon(weapon_id).get("manpads", false))


## Головка «Осоки»: работает, пока комплекс вскинут к прицелу и в трубе ракета (OsokaSeeker).
func _tick_osoka(delta: float) -> void:
	if not is_manpads() or not is_local():
		if osoka.powered or osoka.state != OsokaSeeker.State.OFF:
			osoka.reset(false)
		return
	var on: bool = aiming and aim_progress() > 0.8 and ammo > 0 and reload_timer <= 0.0 and not is_downed() \
		and weapon_obstruction <= float(Balance.WEAPON_CLEARANCE.fire_threshold)
	osoka.tick(self, delta, on)


## Пуск «Осоки»: только с захватом (Balance.OSOKA.need_lock). Труба одноразовая на выстрел — в ней одна ракета
## (internal_mag 1), R ставит пусковой механизм на новую трубу из рюкзака. Ракета летит у всех peer одинаково,
## урон считает стрелок (OsokaMissile).
func _fire_osoka(spec: Dictionary) -> void:
	fire_timer = 0.4
	if bool(spec.get("broken", false)):
		_say("Комплекс неисправен — нужен ремонт на верстаке")
		return
	# под крышей не пускают (реактивная струя назад; тир убежища — тоже под крышей); стойка тира на открытой карте
	# (стенды tools/dam_play, tools/osoka_range) — можно
	var roof := PhysicsRayQueryParameters3D.create(eye_position(), eye_position() + Vector3.UP * 30.0,
		Hitscan.LAYER_WORLD | Hitscan.LAYER_ROOF, [get_rid()])
	if not get_world_3d().direct_space_state.intersect_ray(roof).is_empty():
		_say("Под крышей ракеты не пускают — выйди на открытое место")
		return
	if weapon_obstruction > float(Balance.WEAPON_CLEARANCE.fire_threshold):
		return
	var locked: bool = osoka.locked()
	if bool(Balance.OSOKA.need_lock) and not locked:
		if not aiming:
			_say("Вскинь комплекс к прицелу (ПКМ) и поймай цель в кольцо мушки")
		elif osoka.state == OsokaSeeker.State.WARMUP:
			_say("Головка ещё не готова — подожди писка")
		else:
			_say("Нет захвата — держи цель в кольце мушки, пока писк не станет ровным")
		return
	var st: Dictionary = _ws[weapon_slot]
	_take_round(st)
	ammo = _state_rounds(weapon_slot)
	weapon_rounds = ammo
	_weapon_action("shot", true, 0.0, ammo, false)
	var worn_entry: Dictionary = entry_of(weapon_slot)
	WeaponCondition.wear_shots(worn_entry, 1)
	st.dur = WeaponCondition.percent(worn_entry)
	st["shots"] = int(st.get("shots", 0)) + 1
	_ws_dirty = true
	_ws_sync_t = 0.6
	fire_timer = float(spec.interval)
	last_shot_ms = Time.get_ticks_msec()
	var line: Array = _osoka_launch_line()
	var target: Node3D = osoka.target if locked else null
	var path: String = String(get_tree().current_scene.get_path_to(target)) if target else ""
	osoka.reset(true)
	_launch_osoka(line[0], line[1], target, true)
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_osoka_launch", [line[0], line[1], path], false)
	if Raid.current and is_local():
		Raid.current.analytics.on_shot(false)
	_apply_recoil(spec, stance != Stance.STAND, _camera_rig as CameraRig)
	if _camera_rig is CameraRig:
		(_camera_rig as CameraRig).add_shake(float(Balance.OSOKA.shake))


## Откуда и куда уходит ракета: сопло ракеты в трубе и ось трубы (метки MissileMount, Breech → Muzzle) — у модели
## в руках, иначе у модели на теле; нет меток — от глаза по взгляду.
func _osoka_launch_line() -> Array:
	var model: Node3D = null
	if ads and _camera_rig is CameraRig:
		model = (_camera_rig as CameraRig)._vm_frame()
	elif _weapon_model:
		model = _weapon_model
	if model and model.has_meta("missile_mount") and model.has_meta("breech"):
		var a: Vector3 = model.to_global(model.get_meta("breech"))
		var b: Vector3 = model.to_global(model.get_meta("muzzle", Vector3.ZERO))
		return [model.to_global(model.get_meta("missile_mount")), (b - a).normalized()]
	return [eye_position() + look_dir() * 0.3, look_dir()]


func _launch_osoka(from: Vector3, dir: Vector3, target: Node3D, own: bool) -> void:
	var on_hit: Callable = _osoka_hit if own and is_local() else Callable()
	OsokaMissile.launch(get_tree().current_scene, from, dir, target, get_rid(), own, -1 if own else 0, on_hit)


## Ракета напарника: та же точка, направление и цель (путь узла цели в сцене; не нашлась — летит без неё).
@rpc("authority", "call_remote", "reliable")
func _rpc_osoka_launch(from: Vector3, dir: Vector3, target_path: String) -> void:
	var target: Node3D = get_tree().current_scene.get_node_or_null(NodePath(target_path)) as Node3D if target_path != "" else null
	weapon_rounds = 0
	_weapon_action("shot", true, 0.0, 0, false)
	_launch_osoka(from, dir, target, false)


func _osoka_hit(_target: Node3D) -> void:
	if _camera_rig is CameraRig:
		(_camera_rig as CameraRig).show_hitmarker(true)
	_say("Попадание!")


func is_signal_launcher() -> bool:
	return weapon_id == "signal_launcher"


func has_signal_launcher() -> bool:
	if inventory.has("signal_launcher"):
		return true
	for entry: Dictionary in inventory.equipment.values():
		if String(entry.get("id", "")) == "signal_launcher":
			return true
	return false


func select_signal_ammo(aid: String) -> bool:
	if not WeaponDb.ammo_fits("signal_launcher", aid):
		return false
	if reload_timer > 0.0 or not _pm_action.is_empty():
		_say("Дождись окончания действия ракетницы")
		return false
	signal_reload_ammo = aid
	_say(("Зелёный: вызов снабжения" if aid == "supply_signal" else "Красный: освещение") + ". R — зарядить ракетницу")
	return true


func _start_signal_reload(specification: Dictionary) -> void:
	if not is_signal_launcher() or reload_timer > 0.0 or not _pm_action.is_empty():
		return
	if ammo > 0 and String(specification.ammo) == signal_reload_ammo:
		_say("Этот патрон уже заряжен")
		return
	if loadout_mode and not inventory.has(signal_reload_ammo):
		_say("Нет патрона: " + ItemDb.item_name(signal_reload_ammo))
		return
	_reload_kind = "signal"
	_reload_slot = weapon_slot
	_reload_empty = ammo <= 0
	_reload_age = 0.0
	_reload_fast = false
	_reload_insert = false
	_reload_hold = -1.0
	var state: Dictionary = _ws_state(weapon_slot)
	state["reload_ammo"] = signal_reload_ammo
	_pm_action_seq += 1
	_pm_action = {"kind": "reload", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
		"state": state, "empty": _reload_empty, "sent": false}
	reload_timer = float(specification.reload) * (1.0 + float(Balance.STRESS.reload_k) * stress_k())
	_animation_event("pistol_reload")
	_weapon_action("reload", _reload_empty, reload_timer)


## Expensive signals use a host transaction rather than predicting ammo locally.
func _fire_signal(specification: Dictionary) -> bool:
	if not _pm_action.is_empty() or reload_timer > 0.0 or ammo <= 0 or not health.alive or is_downed():
		return false
	if weapon_obstruction > float(Balance.WEAPON_CLEARANCE.fire_threshold):
		return false
	if in_range_mode():
		_say("В тире сигналы не запускают")
		return false
	_pm_action_seq += 1
	_pm_action = {"kind": "signal_shot", "seq": _pm_action_seq, "slot": weapon_slot, "id": weapon_id,
		"state": _ws_state(weapon_slot), "sent": false, "muzzle": _muzzle_world()}
	fire_timer = float(specification.interval)
	_commit_pm_action()
	return true


func _host_signal_shot(slot: String, base: Dictionary, request: Dictionary) -> Dictionary:
	if String(base.get("id", "")) != "signal_launcher" or WeaponCondition.broken(base):
		return {"error": "Ракетница недоступна"}
	if Time.get_ticks_msec() - _signal_host_fire_ms < 850:
		return {"error": "Дождись окончания выстрела"}
	if Raid.current and (Raid.current.over or Raid.current.has_left(peer_id)):
		return {"error": "Рейд уже окончен"}
	var entry: Dictionary = base.duplicate(true)
	var mag: Dictionary = entry.get("mag", {})
	if int(mag.get("rounds", 0)) != 1:
		return {"error": "Ракетница не заряжена"}
	var aid: String = Gear.mag_top(mag)
	if not WeaponDb.ammo_fits("signal_launcher", aid):
		return {"error": "Неверный сигнальный патрон"}
	var supply: bool = aid == "supply_signal"
	if supply:
		if Raid.current == null:
			return {"error": "Снабжение вызывают только в рейде"}
		var error: String = Raid.current.start_loaded_supply_signal(self)
		if error != "":
			return {"error": error}
	Gear.mag_pop(mag)
	entry["mag"] = mag
	entry["signal_spent"] = true
	WeaponCondition.wear_shots(entry, 1)
	entry["_condition_shots"] = int(base.get("_condition_shots", 0)) + 1
	Gear._bump(entry)
	if loadout_mode:
		var eq: Dictionary = inventory.equipment.duplicate(true)
		eq[slot] = entry
		inventory.equipment = eq
	else:
		sandbox_weapons[slot] = entry
	_signal_host_fire_ms = Time.get_ticks_msec()
	var flat := Vector3(sin(body_yaw()), 0, cos(body_yaw()))
	var direction: Vector3 = (Vector3.UP + flat * float(Balance.SKY_FLARE.drift)).normalized()
	var origin: Vector3 = eye_position() + flat * 0.3
	var requested: Vector3 = request.get("muzzle", origin)
	if requested.is_finite() and requested.distance_to(eye_position()) < 0.8:
		var q := PhysicsRayQueryParameters3D.create(eye_position(), requested, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS, [get_rid()])
		if get_world_3d().direct_space_state.intersect_ray(q).is_empty():
			origin = requested
	if not supply:
		NoiseBus.emit(global_position, float(Balance.SKY_FLARE.noise_m), "shot")
	Net.broadcast_scene(self, &"_rpc_signal_effect", [origin, direction, supply], false)
	_apply_signal_effect(origin, direction, supply)
	return {"error": "", "entry": entry, "slot": slot, "kind": "signal_shot"}


@rpc("any_peer", "call_remote", "reliable")
func _rpc_signal_effect(origin: Vector3, direction: Vector3, supply: bool) -> void:
	var sender: int = multiplayer.get_remote_sender_id()
	if Net.is_networked() and sender != 0 and sender != 1:
		return
	_apply_signal_effect(origin, direction, supply)


func _apply_signal_effect(origin: Vector3, direction: Vector3, supply: bool) -> void:
	weapon_rounds = 0
	weapon_signal_ammo = "supply_signal" if supply else "flare"
	_weapon_action("shot", true, 0.0, 0, false)
	_shot_fx(origin, "shot_pistol", -2.0, 0.35, "", "")
	SkyFlare.launch(get_tree().current_scene, origin, direction, supply, false)
	last_shot_ms = Time.get_ticks_msec()
	if is_local() and is_signal_launcher():
		var specification: Dictionary = spec()
		_apply_recoil(specification, stance != Stance.STAND, _camera_rig as CameraRig)
		if _camera_rig is CameraRig:
			(_camera_rig as CameraRig).add_shake(float(specification.shake))


## Что видно и слышно от выстрела: вспышка у дула, звук, щелчок помпы/затвора. След пули
## обозначают только эффекты попадания, созданные Hitscan. У стрелявшего — из _fire, у остальных
## — по сети (_rpc_shot_fx).
func _shot_fx(muzzle: Vector3, sound: String, db: float, flash: float, cycle_sound: String, mechanism_sound: String) -> void:
	# вспышка: пламегаситель гасит, глушитель — почти нет
	if flash > 0.05:
		_muzzle.global_position = muzzle
		_muzzle.light_energy = 3.0 * flash
		# своя вспышка стоит у дула модели в руках — свои руки она не освещает (пересвет ствола в упор),
		# им — свой свет; вспышка напарника рядом руки освещает как обычно
		_muzzle.light_cull_mask = (0xFFFFF & ~VIEWMODEL_LAYER) if is_local() else 0xFFFFF
		_muzzle.visible = true
		get_tree().create_timer(0.05).timeout.connect(func() -> void: _muzzle.visible = false)
		if is_local() and ads:
			var hands := _hands_light("flash")
			hands.global_position = hands_flash_at(muzzle)
			hands.light_energy = float(Balance.VIEWMODEL_LIGHTS.flash.energy) * flash
			hands.visible = true
			get_tree().create_timer(0.05).timeout.connect(func() -> void:
				if is_instance_valid(hands):
					hands.visible = false)
	Audio.play(sound, muzzle, db)
	if mechanism_sound != "":
		Audio.play(mechanism_sound, muzzle, db - 5.0)
	var firing_weapon: String = sound.get_slice("_shot", 0) if sound != "" else weapon_id
	# У помпы и болтовки гильза вылетает при передёргивании.
	if cycle_sound != "":
		get_tree().create_timer(0.35).timeout.connect(func() -> void:
			if is_inside_tree():
				Audio.play(cycle_sound, global_position)
				Audio.shell_drop(global_position, _side_dir(), 0.0, firing_weapon))
	else:
		Audio.shell_drop(global_position, _side_dir(), 0.0, firing_weapon)


## Вправо от стрелка (по телу) — куда вылетает гильза.
func _side_dir() -> Vector3:
	return _body.global_basis.x if _body else global_basis.x


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


## Свет только на свои руки и оружие у лица (kind: flash — от вспышки, bounce — отражённый от фонаря):
## сам по себе в мире (top_level), без теней и тумана; Settings.soften его не трогает.
func _hands_light(kind: String) -> OmniLight3D:
	var have: OmniLight3D = _hands_flash if kind == "flash" else _hands_bounce
	if have:
		return have
	var cfg: Dictionary = Balance.VIEWMODEL_LIGHTS[kind]
	var l := OmniLight3D.new()
	l.name = "HandsFlash" if kind == "flash" else "HandsBounce"
	l.set_meta("own", true)
	l.set_meta("soft", true)
	l.top_level = true
	l.light_cull_mask = VIEWMODEL_LAYER
	l.shadow_enabled = false
	l.light_color = cfg.color
	l.omni_range = float(cfg.range)
	l.light_indirect_energy = 0.0
	l.light_volumetric_fog_energy = 0.0
	l.light_energy = 0.0
	l.visible = false
	add_child(l)
	if kind == "flash":
		_hands_flash = l
	else:
		_hands_bounce = l
	return l


## Где свет рук от вспышки: от дула к глазу и чуть выше (Balance.VIEWMODEL_LIGHTS.flash) — на верх оружия и руки.
func hands_flash_at(muzzle: Vector3) -> Vector3:
	var cfg: Dictionary = Balance.VIEWMODEL_LIGHTS.flash
	var cam := get_viewport().get_camera_3d()
	if cam == null:
		return muzzle
	return muzzle.lerp(cam.global_position, float(cfg.toward_eye)) + cam.global_basis.y * float(cfg.up)


## Отражённый свет фонаря на свои руки (Balance.VIEWMODEL_LIGHTS.bounce): фонарь светит вперёд, и руки за
## ним видны только от того, что перед стволом, — у стены светло, в открытом поле почти ничего.
func _tick_hands_bounce(delta: float) -> void:
	var on := is_local() and ads and light_on and is_alive()
	if not on and (_hands_bounce == null or not _hands_bounce.visible):
		return
	var cfg: Dictionary = Balance.VIEWMODEL_LIGHTS.bounce
	var l := _hands_light("bounce")
	var target := 0.0
	var cam := get_viewport().get_camera_3d()
	if on and cam:
		var from := cam.global_position
		var fwd := -cam.global_basis.z
		var d := float(cfg.far_m)
		var q := PhysicsRayQueryParameters3D.create(from, from + fwd * d,
			Hitscan.LAYER_WORLD | Hitscan.LAYER_PLAYER | Hitscan.LAYER_MARAUDER | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS)
		q.exclude = [get_rid()]
		var hit := get_world_3d().direct_space_state.intersect_ray(q)
		if not hit.is_empty():
			d = from.distance_to(hit.position as Vector3)
		target = float(cfg.energy) * minf(1.0, pow(float(cfg.near_m) / maxf(d, 0.01), 2.0))
		l.global_position = from + fwd * minf(d * float(cfg.forward_k), float(cfg.max_m)) \
			+ cam.global_basis * (cfg.offset as Vector3)
	l.light_energy = lerpf(l.light_energy, target, 1.0 - exp(-delta / float(cfg.sec)))
	l.visible = l.light_energy > 0.002


## Что надето на глаза: ПНВ / очки / "".
func eyes_item() -> String:
	return String((inventory.equipment.get("eyes", {}) as Dictionary).get("id", "")) if inventory else ""


func _tick_nvg(delta: float) -> void:
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


## Осветительная ракета из сигнального пистолета: вверх (с небольшим уклоном по взгляду), высоко, на
## Balance.SKY_FLARE.air_sec — освещает большой участок и медленно опускается (SkyFlare). Нужны
## пистолет и ракета в рюкзаке (в песочнице — без счёта). Выстрел слышат NPC, видят все peer.
func launch_sky_flare() -> bool:
	if is_signal_launcher():
		return _fire_signal(spec())
	if in_range_mode():
		_say("В тире — только стрельба")
		return false
	if not health.alive or is_downed():
		return false
	if loadout_mode:
		if not has_signal_launcher():
			_say("Нужен сигнальный пистолет в рюкзаке")
			return false
		if inventory.count("flare") <= 0:
			_say("Нет: " + ItemDb.item_name("flare"))
			return false
		items_host().call("request_consume", "flare", 1)
	fire_timer = 0.6
	var aim: Vector3 = look_dir() if ads else Vector3(sin(_body.rotation.y), 0.0, cos(_body.rotation.y))
	var flat: Vector3 = Vector3(aim.x, 0.0, aim.z)
	var dir: Vector3 = (Vector3.UP + (flat.normalized() if flat.length() > 0.05 else Vector3.ZERO) * float(Balance.SKY_FLARE.drift)).normalized()
	var from: Vector3 = eye_position() + Vector3.UP * 0.25 + flat.normalized() * 0.3 if flat.length() > 0.05 else eye_position() + Vector3.UP * 0.25
	NoiseBus.emit(global_position, float(Balance.SKY_FLARE.noise_m), "shot")
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_sky_flare", [from, dir])
	else:
		_rpc_sky_flare(from, dir)
	return true


@rpc("authority", "call_local", "reliable")
func _rpc_sky_flare(from: Vector3, dir: Vector3) -> void:
	SkyFlare.launch(get_tree().current_scene, from, dir)


## Свет, брошенный рукой (ракета / химсвет): у каждого peer свой (ThrownLight). Бросок своего игрока — хост
## (_server_grenade_throw) и _rpc_light_spawn; этот вызов — для тестов и сцен, которые ставят свет сами.
@rpc("authority", "call_local", "reliable")
func _rpc_throw_light(k: String, from: Vector3, v: Vector3) -> void:
	ThrownLight.throw(get_tree().current_scene, k, from, v)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_light_spawn(k: String, from: Vector3, v: Vector3) -> void:
	if multiplayer.get_remote_sender_id() != 1 or not (Balance.THROWN_LIGHTS as Dictionary).has(k):
		return
	ThrownLight.throw(get_tree().current_scene, k, from, v)


## Идентификатор для обеих моделей — в руках игрока и у его напарников.
func held_model_id() -> String:
	return throwable_id if grenade_equipped else weapon_id


## Сколько бросаемого kind ("" — того, что в руке): граната — запас гранат; свет — из рюкзака (в песочнице — без счёта).
func throwable_count(kind: String = "") -> int:
	var k: String = throwable_id if kind == "" else kind
	if k == "grenade":
		return grenade_count()
	if in_range_mode():
		return 0
	return inventory.count(k) if loadout_mode else 99


func throwable_name(kind: String = "") -> String:
	var k: String = throwable_id if kind == "" else kind
	return "Граната" if k == "grenade" else ItemDb.item_name(k)


func _equip_grenade() -> void:
	_equip_throwable("grenade")


## Взять в руку бросаемое kind; оно уже в руке — убрать (прежнее оружие обратно), другое бросаемое — сменить.
func _equip_throwable(kind: String) -> void:
	if grenade_equipped and throwable_id == kind:
		_return_from_grenade()
		return
	if in_range_mode() and kind != "grenade":
		_say("В тире — только стрельба")
		return
	if throwable_count(kind) <= 0:
		_say("Гранат нет" if kind == "grenade" else "Нет: " + throwable_name(kind))
		return
	if grenade_equipped:
		if _grenade_pending:
			return
		throwable_id = kind
		grenade_in_hand = true
		_cancel_grenade_prepare()
		fire_timer = float(Balance.GRENADE_HAND.equip_sec)
		return
	throwable_id = kind
	cancel_weapon_action()
	if weapon_slot != "" and _ws.has(weapon_slot):
		_send_ws(weapon_slot)
	if weapon_id != "":
		_play_weapon_sound(spec(), "holster", -6.0)
	weapon_id = ""
	holstered = false
	aiming = false
	aim_cant = false
	grenade_equipped = true
	grenade_in_hand = true
	_cancel_grenade_prepare()
	fire_timer = float(Balance.GRENADE_HAND.equip_sec)


func _return_from_grenade() -> void:
	grenade_equipped = false
	grenade_in_hand = false
	_cancel_grenade_prepare()
	if weapon_slot in allowed_weapons() and not _base_entry(weapon_slot).is_empty():
		_switch(weapon_slot)
	else:
		weapon_id = ""


## Клики, зажатые до выбора гранаты или под окном, должны сначала отпуститься.
func _tick_grenade(delta: float) -> void:
	aiming = false
	if _grenade_pending:
		return
	if _grenade_recover > 0.0:
		_grenade_recover = maxf(0.0, _grenade_recover - delta)
		if _grenade_recover > 0.0:
			return
		if throwable_count() <= 0:
			_return_from_grenade()
			return
		grenade_in_hand = true
	if throwable_count() <= 0:
		_return_from_grenade()
		return
	if not _grenade_input_ready:
		_grenade_input_ready = not Input.is_action_pressed("fire") and not Input.is_action_pressed("aim")
		return
	if _grenade_button == "":
		if fire_timer > 0.0:
			return
		if Input.is_action_just_pressed("fire"):
			_grenade_button = "fire"
		elif Input.is_action_just_pressed("aim"):
			_grenade_button = "aim"
		else:
			return
		grenade_underhand = _grenade_button == "aim"
		# граната — кольцо; химсвет — переломить палочку, фальшфейер — чиркнуть тёркой
		Audio.play("pin", eye_position(), -5.0 if throwable_id == "grenade" else -9.0)
	_grenade_hold += delta
	grenade_charge = clampf(_grenade_hold / float(Balance.GRENADE_HAND.charge_sec), 0.0, 1.0)
	grenade_pin = clampf(_grenade_hold / float(Balance.GRENADE_HAND.prepare_sec), 0.0, 1.0)
	_grenade_released = _grenade_released or not Input.is_action_pressed(_grenade_button)
	if _grenade_released and grenade_pin >= 1.0:
		_throw_grenade()


## Дальность задаётся силой и направлением взгляда. Начальная точка не перескакивает сквозь стену.
func _grenade_launch(power: float = 1.0, underhand: bool = false, direction: Vector3 = Vector3.ZERO) -> Array:
	var cfg: Dictionary = Balance.GRENADE_HAND
	var forward: Vector3 = direction
	if forward.is_zero_approx():
		forward = look_dir() if ads else (cursor_ground - eye_position()).normalized()
	if forward.is_zero_approx():
		forward = Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))
	forward = forward.normalized()
	var origin: Vector3 = eye_position()
	var from: Vector3 = origin - Vector3.UP * float(cfg.under_drop if underhand else cfg.over_drop)
	from += forward * float(cfg.release_forward)
	var mask: int = Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_GLASS
	var ray: PhysicsRayQueryParameters3D = PhysicsRayQueryParameters3D.create(origin, from, mask, [get_rid()])
	var hit: Dictionary = get_world_3d().direct_space_state.intersect_ray(ray)
	if not hit.is_empty():
		from = (hit.position as Vector3) + (hit.normal as Vector3) * float(cfg.wall_margin)
	var lift: float = float(cfg.under_lift if underhand else cfg.over_lift)
	var speed: float = lerpf(float(cfg.under_min if underhand else cfg.over_min), float(cfg.under_max if underhand else cfg.over_max), clampf(power, 0.0, 1.0))
	var velocity: Vector3 = (forward + Vector3.UP * lift).normalized() * speed
	return [from, velocity]


func _cancel_grenade_prepare() -> void:
	_grenade_button = ""
	_grenade_hold = 0.0
	_grenade_released = false
	_grenade_input_ready = false
	grenade_pin = 0.0
	grenade_charge = 0.0


func _throw_grenade() -> void:
	if not grenade_equipped or _grenade_pending or throwable_count() <= 0:
		return
	var power: float = grenade_charge
	var under: bool = grenade_underhand
	var direction: Vector3 = look_dir() if ads else (cursor_ground - eye_position()).normalized()
	_animation_event("grenade_throw")
	_grenade_seq += 1
	_grenade_pending = true
	grenade_in_hand = false
	_cancel_grenade_prepare()
	if Net.is_networked() and not multiplayer.is_server():
		_rpc_grenade_request.rpc_id(1, _grenade_seq, power, under, direction, throwable_id)
	else:
		_server_grenade_throw(_grenade_seq, power, under, direction, throwable_id)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_grenade_request(sequence: int, power: float, under: bool, direction: Vector3, kind: String) -> void:
	if multiplayer.is_server() and multiplayer.get_remote_sender_id() == peer_id:
		_server_grenade_throw(sequence, power, under, direction, kind)


## Расход и создание снаряда — одна операция хоста; повтор пакета не создаёт вторую гранату. kind — что бросают:
## граната (снаряд Grenade) или свет (ThrownLight у каждого peer).
func _server_grenade_throw(sequence: int, power: float, under: bool, direction: Vector3, kind: String = "grenade") -> void:
	if sequence <= _grenade_host_seq:
		return
	_grenade_host_seq = sequence
	var now: int = Time.get_ticks_msec()
	var known: bool = kind == "grenade" or (Balance.THROWN_LIGHTS as Dictionary).has(kind)
	var accepted: bool = known and is_alive() and combat_enabled and not in_range_mode() and direction.is_finite() and is_finite(power) and direction.length_squared() > 0.01 \
		and now - _grenade_host_ms >= int(float(Balance.GRENADE_HAND.recover_sec) * 1000.0) and throwable_count(kind) > 0
	if accepted and loadout_mode:
		accepted = inventory.remove(kind, 1) == 1
	elif accepted and kind == "grenade":
		grenades -= 1
	if accepted:
		_grenade_host_ms = now
		var launch: Array = _grenade_launch(clampf(power, 0.0, 1.0), under, direction.normalized())
		# Локальное создание не проходит через RPC-обработчик: вложенный вызов ещё несёт sender гостя.
		if kind == "grenade":
			_spawn_grenade_local(launch[0], launch[1])
			Net.broadcast_scene(self, &"_rpc_grenade_spawn", [launch[0], launch[1]], false)
		else:
			ThrownLight.throw(get_tree().current_scene, kind, launch[0], launch[1])
			Net.broadcast_scene(self, &"_rpc_light_spawn", [kind, launch[0], launch[1]], false)
	if is_local():
		_grenade_result(sequence, accepted, throwable_count(kind), kind)
	else:
		_rpc_grenade_result.rpc_id(peer_id, sequence, accepted, throwable_count(kind), kind)


@rpc("any_peer", "call_remote", "reliable")
func _rpc_grenade_result(sequence: int, accepted: bool, remaining: int, kind: String) -> void:
	if multiplayer.get_remote_sender_id() == 1:
		_grenade_result(sequence, accepted, remaining, kind)


func _grenade_result(sequence: int, accepted: bool, remaining: int, kind: String = "grenade") -> void:
	if sequence != _grenade_seq or sequence <= _grenade_result_seq:
		return
	_grenade_result_seq = sequence
	_grenade_pending = false
	if not loadout_mode and kind == "grenade":
		grenades = remaining
	_grenade_recover = float(Balance.GRENADE_HAND.recover_sec)
	fire_timer = _grenade_recover
	if not accepted:
		_say("Бросок отменён: %s не израсходован%s" % [throwable_name(kind).to_lower(), "а" if kind == "grenade" else ""])
	elif remaining <= 0 and grenade_equipped:
		_return_from_grenade()


## G: одно нажатие — ракетница в руки (уже в руках — тип следующего патрона: красный / зелёный), двойное
## (Balance.LIGHT_KEYS.double_tap_sec) — красный фальшфейер в руку, бросок как граната. Одно нажатие срабатывает, когда
## окно второго прошло.
func _tick_light_key(delta: float, fresh_ui: bool) -> void:
	if not InputMap.has_action("throw_flare"):
		return
	if Input.is_action_just_pressed("throw_flare") and not fresh_ui:
		if _g_tap_t > 0.0:
			_g_tap_t = -1.0
			_equip_throwable("flare")
		else:
			_g_tap_t = float(Balance.LIGHT_KEYS.double_tap_sec)
		return
	if _g_tap_t > 0.0:
		_g_tap_t -= delta
		if _g_tap_t <= 0.0:
			_g_tap_t = -1.0
			draw_signal_launcher()


## Ракетница в руки из слота оружия (1 / 2). Уже в руках — выбрать тип следующего патрона. В рюкзаке — подсказка: в
## руки берут из слота.
func draw_signal_launcher() -> void:
	if is_signal_launcher():
		select_signal_ammo("supply_signal" if signal_reload_ammo == "flare" else "flare")
		return
	for key: Variant in allowed_weapons():
		if String(_base_entry(String(key)).get("id", "")) == "signal_launcher":
			_switch(String(key))
			return
	if loadout_mode and inventory.has("signal_launcher"):
		_say("Ракетница в рюкзаке — положи её в слот оружия, тогда G достаёт её")
	else:
		_say("Ракетницы нет")


@rpc("any_peer", "call_remote", "reliable")
func _rpc_grenade_spawn(from: Vector3, velocity: Vector3) -> void:
	if multiplayer.get_remote_sender_id() != 1:
		return
	_spawn_grenade_local(from, velocity)


func _spawn_grenade_local(from: Vector3, velocity: Vector3) -> void:
	var grenade: Grenade = Grenade.throw(get_tree().current_scene, from, velocity, get_rid(), multiplayer.is_server(), peer_id)
	grenade.src = {"kind": "grenade", "by": "player", "peer": peer_id}


## Куда: по нажатым WASD, иначе — куда смотрит корпус.
func _action_dir() -> Vector3:
	var w := _wish_direction()
	if w.length_squared() > 0.01:
		return w
	if ads:
		return Vector3(sin(look_yaw), 0.0, cos(look_yaw))
	return Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))


## Пробел: у низа лестницы — схватиться; перелезть через преграду по пояс впереди или залезть на то,
## на чём можно стоять (машина, ящик, край платформы — Climb): тонкое — через, толстое — на него
## (Balance.CLIMB.vault_thick). Стоя или сидя; не лёжа, не с раненым на руках.
func _try_vault() -> void:
	var v: Dictionary = Balance.VAULT
	if stance == Stance.PRONE or is_burdened() or is_downed() or not is_on_floor():
		return
	if _try_grab_ladder():
		return
	if _winded or stamina < float(v.stamina) * 0.5:
		return
	var space := get_world_3d().direct_space_state
	var dir := _action_dir()
	var path := Vault.find(space, global_position, dir, [get_rid()])
	var onto := Climb.find(space, global_position, dir, [get_rid()], _climb_max_h())
	if path.is_empty() and onto.is_empty() and _wish_direction().length_squared() > 0.01:
		# жмёт вбок, а преграда прямо перед ним
		dir = Vector3(sin(body_yaw()), 0.0, cos(body_yaw()))
		path = Vault.find(space, global_position, dir, [get_rid()])
		onto = Climb.find(space, global_position, dir, [get_rid()], _climb_max_h())
	if not onto.is_empty() and (path.is_empty() or float(path.thick) > float(Balance.CLIMB.vault_thick)):
		_start_climb(onto)
		return
	if path.is_empty():
		return
	_vault = path
	_vault_t = 0.0
	_vault_then = ""
	_vault_sec = float(v.sec) * (1.0 + _over() * float(v.weight_k))
	# высокая преграда (по грудь) — дольше: подтянуться и перекинуть ноги
	_vault_sec *= lerpf(1.0, 1.4, clampf((float(path.get("top", 1.0)) - 1.0) / 0.7, 0.0, 1.0))
	# под сильным стрессом можно запнуться (редко, не чаще раза в stumble_cd)
	var sc: Dictionary = Balance.STRESS
	if _stumble_cd <= 0.0 and stress >= float(sc.stumble_from) and _rng.randf() < float(sc.stumble_chance) * _stress_over(float(sc.stumble_from)):
		_vault_stumble = true
		_vault_sec *= 1.6
		_stumble_cd = float(sc.stumble_cd)
		_say("Запнулся — руки не слушаются")
	stamina = maxf(0.0, stamina - float(v.stamina) * carry_stamina_k())
	_rest_t = Balance.STAMINA_REGEN_DELAY
	_cancel_grenade_prepare()
	var d: Vector3 = (path.land as Vector3) - global_position
	if not ads:
		_body.rotation.y = atan2(d.x, d.z)
	NoiseBus.emit(global_position, float(v.noise_m), "step")
	Audio.play("vault", global_position + Vector3.UP * 0.8, -14.0)


## Залезть на преграду по пути Climb.find: чем выше, тем дольше и тяжелее; наверху место только сидя —
## сразу в присед.
func _start_climb(onto: Dictionary) -> void:
	var c: Dictionary = Balance.CLIMB
	var top := float(onto.top)
	if bool(onto.crouch) and stance != Stance.CROUCH:
		stance = Stance.CROUCH
		_apply_stance()
	var d: Vector3 = (onto.land as Vector3) - global_position
	if not ads:
		_body.rotation.y = atan2(d.x, d.z)
	_start_scripted_move(onto, _climb_sec(top), "")
	stamina = maxf(0.0, stamina - lerpf(float(c.stamina_low), float(c.stamina_high), _climb_k(top)) * carry_stamina_k())
	_rest_t = Balance.STAMINA_REGEN_DELAY
	NoiseBus.emit(global_position, float(c.noise_m), "step")
	Audio.play("climb", global_position + Vector3.UP * 0.8, -14.0)


## Насколько высоко залезать: 0 — по колено (VAULT.min_h), 1 — предел CLIMB.max_h.
func _climb_k(top: float) -> float:
	var lo := float(Balance.VAULT.min_h)
	return clampf((top - lo) / (float(Balance.CLIMB.max_h) - lo), 0.0, 1.0)


func _climb_sec(top: float) -> float:
	var c: Dictionary = Balance.CLIMB
	return lerpf(float(c.sec_low), float(c.sec_high), _climb_k(top)) * (1.0 + _over() * float(Balance.VAULT.weight_k))


## С перегрузом высоко не подтянуться.
func _climb_max_h() -> float:
	return lerpf(float(Balance.CLIMB.max_h), float(Balance.CLIMB.max_h_loaded), _over())


## Тело идёт по пути (Climb.pos_at или Vault.pos_at) sec секунд; then — что сделать в конце (_end_scripted_move).
func _start_scripted_move(path: Dictionary, sec: float, then: String) -> void:
	_vault = path
	_vault_t = 0.0
	_vault_sec = maxf(sec, 0.05)
	_vault_then = then
	_vault_stumble = false
	_cancel_grenade_prepare()


func _end_scripted_move() -> void:
	var then := _vault_then
	_vault_then = ""
	if then == "ladder" and ladder != null:
		_ladder_y = clampf(ladder.feet_at(global_position), 0.0, ladder.feet_top())
		_ladder_noise_y = _ladder_y
	elif then == "off":
		_draw_after_ladder()


## Пробел у низа лестницы, лицом к ней — схватиться.
func _try_grab_ladder() -> bool:
	if _ladder_cd > 0.0:
		return false
	var look := _action_dir()
	for n in get_tree().get_nodes_in_group(Ladder.GROUP):
		var l := n as Ladder
		if l and l.can_grab(global_position, look) and grab_ladder(l, false):
			return true
	return false


## Схватиться за лестницу (F у низа или у верха — LadderPoint, Пробел у низа): оружие убрать, шаг на
## лестницу — снизу к перекладинам, сверху — через край на верхнюю ступень. false — нельзя сейчас.
func grab_ladder(l: Ladder, from_top: bool) -> bool:
	var cfg: Dictionary = Balance.LADDER
	if l == null or ladder != null or _vault_t >= 0.0 or _ladder_cd > 0.0 or not is_alive() or is_downed() \
		or is_burdened() or seated or _grenade_pending or _dive_t >= 0.0 or Settings.cheat_fly:
		return false
	var path: Dictionary
	var sec := float(cfg.enter_sec)
	if from_top:
		var exit := l.top_exit(get_world_3d().direct_space_state, [get_rid()])
		if exit.is_empty():
			_say("Отсюда на лестницу не встать")
			return false
		var pts := PackedVector3Array([global_position])
		var back: PackedVector3Array = (exit.pts as PackedVector3Array).duplicate()
		back.reverse()
		pts.append_array(back)
		path = {"pts": pts}
		sec += _climb_sec(float(exit.top))
	else:
		var y := clampf(l.feet_at(global_position), 0.0, l.feet_top())
		path = {"pts": PackedVector3Array([global_position, l.line_point(y)])}
	path["yaw"] = l.facing_yaw()
	_stow_for_ladder()
	if stance != Stance.STAND:
		stance = Stance.STAND
		_apply_stance()
	lean = 0.0
	ladder = l
	on_ladder = true
	_ladder_y = l.feet_top() if from_top else 0.0
	_start_scripted_move(path, sec, "ladder")
	NoiseBus.emit(global_position, float(cfg.noise_m), "step")
	if not _ladder_hint_shown:
		_ladder_hint_shown = true
		_say("%s / %s — вверх и вниз, %s — спрыгнуть" % [PauseMenu.key_name("move_forward"), PauseMenu.key_name("move_back"), PauseMenu.key_name("vault")])
	return true


func is_climbing() -> bool:
	return ladder != null


## На лестнице: W / S — вверх и вниз (Shift — быстрее и громче; выдохся, с перегрузом — медленнее),
## наверху W — шаг на площадку, внизу S — сойти, Пробел — спрыгнуть. Перекладины слышат мародёры.
func _tick_ladder(delta: float) -> void:
	var cfg: Dictionary = Balance.LADDER
	if is_downed() or not is_instance_valid(ladder):
		_release_ladder(Vector3.ZERO)
		return
	aiming = false
	lean = move_toward(lean, 0.0, Balance.LEAN_SPEED * delta)
	var free := not keys_blocked()
	if free and Input.is_action_just_pressed("vault"):
		# отпустить: оттолкнуться от лестницы — и вниз
		_release_ladder(-ladder.facing() * float(cfg.push_mps))
		return
	var mv := Input.get_axis("move_back", "move_forward") if free else 0.0
	var top := ladder.feet_top()
	if mv > 0.5 and _ladder_y >= top - 0.01 and _leave_ladder_top():
		return
	if mv < -0.5 and _ladder_y <= 0.01:
		_release_ladder(Vector3.ZERO)
		return
	var hurry := free and Input.is_action_pressed("sprint") and not _winded
	var sp := float(cfg.up_mps) if mv > 0.0 else float(cfg.down_mps)
	if hurry:
		sp *= float(cfg.hurry_k)
	if _winded:
		sp *= float(cfg.winded_k)
	sp *= lerpf(1.0, float(cfg.loaded_k), _over()) * Settings.cheat_speed
	var was := _ladder_y
	_ladder_y = clampf(_ladder_y + mv * sp * delta, 0.0, top)
	var rise := _ladder_y - was
	if rise > 0.0:
		stamina = maxf(0.0, stamina - rise * float(cfg.stamina_per_m) * carry_stamina_k() * (float(cfg.hurry_k) if hurry else 1.0))
		if stamina <= 0.0 and not _winded:
			_winded = true
			if _breath_sound == null:
				_breath_sound = Audio.start_loop("breath", self, -5.0)
	if absf(rise) > 0.0:
		# лезет — не отдыхает
		_rest_t = Balance.STAMINA_REGEN_DELAY
	if absf(_ladder_y - _ladder_noise_y) >= float(cfg.rung_m):
		_ladder_noise_y = _ladder_y
		NoiseBus.emit(global_position + Vector3.UP, float(cfg.noise_m) * (float(cfg.hurry_k) if hurry else 1.0), "step")
	global_position = ladder.line_point(_ladder_y)
	velocity = Vector3.ZERO
	airborne = false
	_body.rotation = Vector3(0.0, ladder.facing_yaw(), 0.0)
	_tick_stamina(delta)
	_tick_stress(delta)
	if not ui_blocked():
		_tick_nvg(delta)


## Наверху W: через край на площадку (Climb), как залезть на преграду. false — площадки нет.
func _leave_ladder_top() -> bool:
	var exit := ladder.top_exit(get_world_3d().direct_space_state, [get_rid()])
	if exit.is_empty():
		return false
	exit["yaw"] = ladder.facing_yaw()
	ladder = null
	on_ladder = false
	if bool(exit.crouch):
		stance = Stance.CROUCH
		_apply_stance()
	_start_scripted_move(exit, _climb_sec(float(exit.top)), "off")
	NoiseBus.emit(global_position, float(Balance.LADDER.noise_m), "step")
	return true


## Отпустить лестницу (внизу сошёл, спрыгнул, упал раненым): толчок push, оружие — обратно в руки.
func _release_ladder(push: Vector3) -> void:
	ladder = null
	on_ladder = false
	_ladder_cd = float(Balance.LADDER.cooldown)
	velocity = push
	_draw_after_ladder()


## Лезть — обе руки на перекладинах: оружие и бросаемое убрать (слот запомнить).
func _stow_for_ladder() -> void:
	_ladder_slot = ""
	aiming = false
	aim_cant = false
	if grenade_equipped:
		grenade_equipped = false
		grenade_in_hand = false
		_cancel_grenade_prepare()
		_ladder_slot = weapon_slot
	elif weapon_id != "":
		_ladder_slot = weapon_slot
		_holster()


## Сошёл с лестницы — убранное на время подъёма оружие снова в руки.
func _draw_after_ladder() -> void:
	var slot := _ladder_slot
	_ladder_slot = ""
	if slot == "" or weapon_id != "" or grenade_equipped or is_downed() or not slot in allowed_weapons():
		return
	if loadout_mode and _base_entry(slot).is_empty():
		return
	_switch(slot)


## Стук перекладин: у каждого peer по синхронизированной высоте того, кто на лестнице.
func _tick_rung_sound() -> void:
	if not on_ladder:
		_rung_sound_y = global_position.y
		return
	if absf(global_position.y - _rung_sound_y) >= float(Balance.LADDER.rung_m):
		_rung_sound_y = global_position.y
		Audio.play("ladder_step", global_position + Vector3.UP * 0.9, -4.0)


## Прыжок считает владелец тела. В воздухе повторный пробел не даёт второго импульса.
func _try_jump() -> void:
	var jump: Dictionary = Balance.JUMP
	var cost: float = float(jump.stamina) * carry_stamina_k()
	if not is_alive() or is_downed() or stance != Stance.STAND or seated or ui_blocked() or PauseMenu.shown \
		or not is_on_floor() or airborne or is_burdened() or _winded or _jump_cd > 0.0 \
		or _vault_t >= 0.0 or _dive_t >= 0.0 or carrying or is_dragging() or stamina < cost:
		return
	velocity.y = float(jump.speed)
	airborne = true
	stamina -= cost
	_rest_t = Balance.STAMINA_REGEN_DELAY
	NoiseBus.emit(global_position, float(jump.takeoff_noise_m), "step")


## Alt: бросок на землю в сторону движения (любую), дальше — лёжа. Шумно, пару мгновений не стреляет.
func _try_dive() -> void:
	var dv: Dictionary = Balance.DIVE
	if stance == Stance.PRONE or is_burdened() or is_downed() or not is_on_floor() or airborne or _dive_cd > 0.0 or _dive_t >= 0.0 or stamina < float(dv.stamina) * 0.5:
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
	_cancel_grenade_prepare()
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
	if keys_blocked():
		aiming = false
		return
	if Input.is_action_just_pressed("crouch"):
		stance = Stance.STAND if stance == Stance.CROUCH else Stance.CROUCH
		_apply_stance()
	if Input.is_action_just_pressed("prone"):
		stance = Stance.STAND if stance == Stance.PRONE else Stance.PRONE
		_apply_stance()
	var was_aiming := aiming
	aiming = Input.is_action_pressed("aim") and not grenade_equipped and not ui_blocked()
	if aiming and not was_aiming and weapon_id != "":
		# вскинул в прицел — «поднял»; нет записей — синтетический шорох (Audio: ads_raise → ads_in)
		_play_stance_sound("ads_raise")
	elif was_aiming and not aiming and weapon_id != "":
		_play_stance_sound("ads_lower")


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
			s = Balance.PLAYER_SPRINT_SPEED if _can_sprint() and sprint_held() else Balance.PLAYER_WALK_SPEED
			# адреналин: бежит быстрее; руки пусты (оружие убрано) — тоже
			if s == Balance.PLAYER_SPRINT_SPEED:
				s *= 1.0 + float(Balance.STRESS.adr_speed) * stress_k()
				if hands_free():
					s *= float(Balance.HOLSTER.sprint_k)
	if aiming:
		s *= Balance.PLAYER_ADS_SPEED_SCALE
	# перегруз: тяжелее free_kg — медленнее
	s *= carry_speed_k()
	# вброд — медленнее, по пояс почти вдвое
	s *= WaterBody.depth_k(_water_depth(), Balance.WATER.speed)
	# отладка: множитель скорости (меню Esc → Настройки, консоль speed)
	s *= Settings.cheat_speed
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
	if keys_blocked():
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
	# в воде глубже щиколотки лечь нельзя — только на колено (раненый лежит всё равно)
	if stance == Stance.PRONE and not is_downed() and _water_depth() > float(Balance.WATER.no_prone):
		stance = Stance.CROUCH
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
	# с лестницы — падает
	ladder = null
	on_ladder = false
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


## Шаг на ступень: упёрлись в низкий уступ (ниже Balance.STEP_UP.max_h) — пробуем «вверх, вперёд,
## вниз»; встаём, если внизу пол (не ребро и не склон круче floor_max_angle). Вперёд — сколько
## хотели пройти, иначе чуть больше: скруглённый низ капсулы должен встать на ступень, а не на ребро.
func _step_up(delta: float, from: Vector3, vel: Vector3) -> void:
	var su: Dictionary = Balance.STEP_UP
	# куда идём — по клавишам: скорость в подступёнок гасится первым же упором, дальше разгон даёт
	# в кадр доли миллиметра, и шаг не срабатывал (стоял у порожка, пока не прыгнешь); без ввода —
	# скорость до столкновения
	var want := Vector3(vel.x, 0.0, vel.z) * delta
	var wish := _wish_direction()
	if wish.length_squared() > 0.0001:
		want = wish * maxf(_stance_speed(), want.length() / delta) * delta
	if want.length_squared() < 0.000001:
		return
	var dir := want.normalized()
	# упёрся: прошёл заметно меньше, чем хотел
	var moved := global_position - from
	moved.y = 0.0
	if moved.dot(dir) > want.length() * 0.6:
		return
	var max_h := float(su.max_h)
	var t := global_transform
	var r := KinematicCollision3D.new()
	var up := Vector3.UP * max_h
	if test_move(t, up, r):
		up = r.get_travel()
	if up.y < 0.05:
		return
	for fwd_len in [want.length(), float(su.reach) * 0.5, float(su.reach)]:
		var t1 := t.translated(up)
		var fwd := dir * maxf(float(fwd_len), 0.02)
		if test_move(t1, fwd, r):
			continue
		var t2 := t1.translated(fwd)
		var down := Vector3.DOWN * (up.y + 0.05)
		if not test_move(t2, down, r):
			continue
		var rise := t2.origin.y + r.get_travel().y - from.y
		if rise < 0.01 or rise > max_h or r.get_normal().y < cos(floor_max_angle):
			continue
		global_position = t2.origin + r.get_travel()
		apply_floor_snap()
		return


## Полёт (отладка, аудит уровня): WASD — куда смотрит камера, пробел — вверх, присесть — вниз,
## спринт — быстрее; сквозь стены и землю, без тяжести. Скорость × Settings.cheat_speed.
func _fly(delta: float) -> void:
	var f: Dictionary = Balance.DEBUG_FLY
	var dir := Vector3.ZERO
	if not PauseMenu.shown and not ui_blocked():
		var mv := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
		var cam := get_viewport().get_camera_3d()
		var fwd := -cam.global_basis.z if cam else look_dir()
		if not ads:
			fwd.y = 0.0
		fwd = fwd.normalized()
		var right := fwd.cross(Vector3.UP).normalized()
		dir = fwd * -mv.y + right * mv.x
		if Input.is_action_pressed("vault"):
			dir.y += 1.0
		if Input.is_action_pressed("crouch"):
			dir.y -= 1.0
	var sp := float(f.speed) * Settings.cheat_speed * (float(f.boost) if Input.is_action_pressed("sprint") else 1.0)
	velocity = dir.limit_length(1.0) * sp
	global_position += velocity * delta
	airborne = false
	_vault_t = -1.0
	if ladder != null:
		_release_ladder(Vector3.ZERO)
	if ads:
		_body.rotation.y = look_yaw
	else:
		_face_cursor(delta)
