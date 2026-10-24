class_name Marauder
extends CharacterBody3D
## Оружие, оставшееся в этом мире: хост выдаёт реальный экземпляр, не отдельную награду.
var recovered_weapon: Dictionary = {}:
	set(value):
		recovered_weapon = value.duplicate(true)
		if is_inside_tree():
			_accept_recovered.call_deferred()


func _accept_recovered() -> void:
	if recovered_weapon.is_empty() or _body == null:
		return
	_store_mag_rounds()
	equipment["primary"] = recovered_weapon.duplicate(true)
	_main_slot = "primary"
	# Запас соответствует найденному стволу. Патроны и износ самого экземпляра сохраняются.
	spare.clear()
	var mag: Dictionary = recovered_weapon.get("mag", {})
	var capacity: int = WeaponDb.capacity(recovered_weapon)
	if String(mag.get("id", "")) != "":
		spare.append(WeaponDb.make_mag(String(mag.id), String(mag.get("ammo", "")), capacity))
	elif capacity > 0:
		spare.append({"id": String(mag.get("ammo", "")), "n": capacity})
	_use("primary")
## Мародёр: ходит отрядом по контейнерам и грабит их (ведущий роется, отряд прикрывает; сумка
## выпадает с трупа) → расследование шума → бой → поиск, раненый — отход.
## Позицию игрока получает только через Perception.can_see (зрение), NoiseBus.noise (слух) и
## NoiseBus.callout (окрик товарища, который сам видел цель) — никакого прямого чтения.
## Ходит по навмешу сектора, двери открывает сам (см. door.gd). Считает только хост.
##
## Бой — тактики: ENGAGE (стоит и стреляет), COVER_MOVE → COVER_HIDE ↔ COVER_PEEK (укрытие:
## присел, выглянул, дал очередь), FLANK (второй в отряде заходит сбоку), PUSH (идёт к последней
## известной точке), ADVANCE — перебежками от укрытия к укрытию к цели, которую не видно
## (попали издалека — угадал направление, сел за укрытие и двигается к стрелку). Не стреляет, если
## между стволом и целью стена. Не толпится: точки, куда уже идут другие, обходит; поиск —
## прочёсывание дугой от ближних точек к дальним. Тяжело ранен (DOWNED) — лежит, стреляет из
## пистолета, зовёт; ближайший товарищ, который слышал (AI_RESCUE_RADIUS), идёт спасать (RESCUE):
## лежит на виду — тащит за укрытие, потом поднимает (аптечка, AI_REVIVE_SEC). Лежащего игрока
## добивает, только если никто другой не стреляет (AI_FINISH_QUIET_SEC). Оружие — из снаряжения (data/loadouts.json), стреляет по классу (AI_CLASS); магазин и
## перезарядка — в укрытии, если оно есть. Точность садится за AI_AIM_SETTLE_SEC после того, как
## заметил цель; бегущую цель и на бегу — хуже. Цель ушла из виду — с шансом (AI_AMBUSH) не идёт
## за ней, а садится в укрытие стволом на последнюю точку и ждёт (AMBUSH): вышел проверить — уже
## под прицелом; в отряде ждёт один, остальные идут.

enum State { PATROL, INVESTIGATE, COMBAT, SEARCH, RETREAT, DEAD, DOWNED, RESCUE }
enum Tactic { ENGAGE, COVER_MOVE, COVER_HIDE, COVER_PEEK, FLANK, PUSH, ADVANCE, OVERWATCH, AMBUSH }

const EYE_HEIGHT := 1.6
const CROUCH_EYE := 1.05

var state: State = State.PATROL
var animation_event: String = ""
var animation_event_seq: int = 0
var tactic: Tactic = Tactic.ENGAGE
## Снаряжение (id в data/loadouts.json): ставит спавнер до добавления в дерево; пусто — по типу.
var loadout_id: String = ""
## Совместимость (тесты, старые спавнеры): оружие ключом — pistol / rifle / shotgun / bolt или пресет.
var weapon: String = ""
## Что на нём: оружие (primary, secondary — записи с магазином и обвесом), броня с плитами,
## шлем, гарнитура; запасные магазины (россыпь — для встроенных) и аптечки. Выпадает при смерти
## тем, что осталось (патроны тратятся по-настоящему).
var equipment: Dictionary = {}
var spare: Array = []
var meds: Array = []
## Какое оружие в руках: primary / secondary.
var _active: String = "primary"
## Прежнее оружие, пока раненый / в тумане с пистолетом.
var _main_slot: String = ""
## Патроны кончились совсем.
var _dry: bool = false
## Старые ключи оружия → пресеты.
const LEGACY_WEAPON := {"pistol": "HG_02_BASE", "rifle": "AR_03_BASE", "shotgun": "SG_02_BASE", "bolt": "SR_01_BASE"}
## Тип (ключ Balance.AI_ARCHETYPES): разведчик, штурмовик, тяжёлый, снайпер; пусто — случайный.
var archetype: String = ""
var squad: Squad
## Откуда брать точки патруля: Callable() -> Vector3 (даёт сцена сектора).
var patrol_point_provider: Callable
## Приказ плана отряда (RivalSquad): {"kind": "fallback" | "hold", "until": мс[, "face": точка]}.
var _order: Dictionary = {}
var _stuck_t: float = 0.0
var _stuck_n: int = 0
var _side_t: float = 0.0
var _side_sign: float = 1.0
var last_known: Vector3 = Vector3.ZERO
var memory_timer: float = 0.0
var notice_timer: float = 0.0
var pause_timer: float = 0.0
var linger_timer: float = 0.0
## Присел (в укрытии) — ниже силуэт и коллизия; синхронизируется на клиентов.
var crouched: bool = false
## Куда смотрит вверх-вниз (рад, + вверх): корпус модели и ствол идут за ним (CharacterAnimator);
## синхронизируется на клиентов.
var look_pitch: float = 0.0

var _rng := RandomNumberGenerator.new()
var _target_player: Player = null
## Цель — ИИ другой фракции (ЧВК, жильцы, мародёры — кому кто враг).
var _foe: Marauder = null
var _foe_t: float = 0.0
## Фракция (из типа): marauder / pmc / resident.
var faction: String = "marauder"
## Жильцы: враждебны игроку (сразу или после того, как к ним полезли).
var hostile_to_players: bool = true
## Чужой отряд идёт к выходу с добычей: по дороге контейнеры больше не обыскивает (RivalSquad).
var no_loot: bool = false
var _facing: float = 0.0
var _nav_ready: bool = false
## Перелезает через преграду (связка навигации Vault): путь и доля пройденного (-1 — нет).
var _vault: Dictionary = {}
var _vault_t: float = -1.0
var _vault_done_ms: int = -10000
var _ragdoll: Ragdoll
var _last_hit_from: Vector3 = Vector3.ZERO
var _last_damage: float = 0.0
var _spec: Dictionary = {}
## Доступный боезапас: у ПМ магазин плюс патронник, у остальных — прежний счёт магазина.
var _mag: int = 0
var _reload_t: float = 0.0
var _shot_t: float = 0.0
var _burst_left: int = 0
## Прицел «садится»: 1 — точно, AI_AIM_COLD — только что заметил.
var _aim: float = 1.0
var _seen_now: bool = false
var _unseen_t: float = 99.0
var _callout_t: float = 0.0
var _tactic_t: float = 0.0
var _cover_pos: Vector3 = Vector3.ZERO
var _peeks: int = 0
## Засада: сколько ещё ждать, с; у какой точки ждёт; идёт в укрытие, чтобы сесть там; шанс на эту
## потерю цели уже разыгран. ambush_bias — множитель шанса для тестов (0 — никогда, 100 — всегда).
var _ambush_t: float = 0.0
var _ambush_at: Vector3 = Vector3.INF
var _ambush_pending: bool = false
var _ambush_rolled: bool = false
var ambush_bias: float = 1.0
var _hurt_t: float = 0.0
var _suppress_t: float = 0.0
var _search_left: int = 0
var _search_total: int = 0
var _search_ang: float = 0.0
var _repath_t: float = 0.0
## Повторная команда не сбрасывает готовый путь; версия карты отменяет сохранённую проекцию.
var _nav_request: Vector3 = Vector3.INF
var _nav_resolved: Vector3 = Vector3.INF
var _nav_iteration: int = -1
## Безрезультатный поиск укрытия повторяем с короткой паузой при прежней угрозе и позиции.
var _cover_miss: Dictionary = {}
var _say_label: Label3D
var _arch: Dictionary = {}
var _base_scale: Vector3 = Vector3.ONE
## Попадание: «повело» (медленнее, хуже целится) и откинуло корпус назад.
var _stagger_t: float = 0.0
var _flinch: float = 0.0
## Охрана сюжетного места: держится в радиусе home_radius от home, не уходит грабить.
var home: Vector3 = Vector3.INF
var home_radius: float = 0.0
## Гарнизон поста (AIPost): обходит эти точки, а не случайные в радиусе home_radius. Считает хост.
var home_points: PackedVector3Array = PackedVector3Array()
## Патруль по маршруту (AIRoute): точки по порядку; route_loop — по кругу, иначе туда-обратно.
var route: PackedVector3Array = PackedVector3Array()
var route_loop: bool = false
var _route_i: int = -1
var _route_dir: int = 1
## Гнездо (AINest): держащий позицию смотрит вдоль watch_dir в секторе watch_sector_deg и отходит не
## дальше hold_radius (меньше нуля — Balance.AI_HOLD_PATROL_R).
var watch_dir: Vector3 = Vector3.ZERO
var watch_sector_deg: float = 0.0
var hold_radius: float = -1.0
## Насторожен (AI_NOISE_RESPONSE): шум проверяют другие — стоит и смотрит туда до этого времени, мс.
var _alert_until: int = 0
var _alert_at: Vector3 = Vector3.ZERO
## Когда последний раз видел игрока или стрелял по нему, мс (счётчик стычек RaidContacts).
var player_contact_ms: int = 0
## Пост (где появился) — у держащего позицию патруль вокруг него.
var _post: Vector3 = Vector3.INF
## Раненый: кто идёт спасать (null — никто), кто тащит; основное оружие на время пистолета.
var rescuer: Marauder = null
var dragged_by: Marauder = null
var _main_gun: Node3D
var _help_t: float = 0.0
var _shown_down: bool = false
## Смерть уже показана клипом (регдолла нет — CharacterAnimator.die).
var _died_shown: bool = false
var _torch: SpotLight3D
var _torch_t: float = 0.0
var _blind_t: float = 0.0
var _fogged: bool = false
## Гранаты: сколько осталось, когда можно следующую.
var _grenades: int = 0
var _grenade_t: float = 0.0
## Прикрытие: пришёл на позицию.
var _overwatch_ready: bool = false
## Обход (отряд обхода) уже сделан в этом бою.
var _flanked: bool = false
## Спасатель: кого, фаза (0 — бежит, 1 — тащит, 2 — поднимает), сколько поднимает.
var _rescue_target: Marauder = null
var _rescue_phase: int = 0
var _rescue_t: float = 0.0
## Грабёж: куда идёт ведущий, сколько роется, что уже взял (сумка), где уже был.
## Метки «этот контейнер наш» — общие для всех: id контейнера -> [мародёр, время, мс].
static var _loot_claims: Dictionary = {}
var pack: Array = []
var _loot_target: LootContainer = null
var _loot_t: float = -1.0
var _rummage_t: float = 0.0
var _visited: Dictionary = {}
## Слышал выстрел игрока: сколько секунд назад и где (добивать лежащего — только в тишине).
var _shot_heard_t: float = 99.0
var _shot_heard_pos: Vector3 = Vector3.INF
var _capsule: CapsuleShape3D

@onready var _agent: NavigationAgent3D = $NavigationAgent3D
@onready var _health: Health = $Health
@onready var _body: Node3D = $Body
@onready var _muzzle: OmniLight3D = $Body/Muzzle


func _ready() -> void:
	add_to_group("marauders")
	# Первый запрос остаётся сразу; последующие таймеры получают свою фазу без расхода RNG.
	var slots: int = int(Balance.AI_WORK.phase_slots)
	var slot: int = get_tree().get_nodes_in_group("marauders").size() - 1
	var phase: float = float(slot % slots) / float(slots)
	_foe_t = -phase * float(Balance.AI_WORK.foe_scan_sec)
	_blind_t = -phase * float(Balance.AI_WORK.glare_scan_sec)
	_repath_t = -phase * float(Balance.AI_WORK.follow_repath_sec)
	_rng.seed = hash(name) + int(global_position.x * 13.0)
	if not Balance.AI_ARCHETYPES.has(archetype):
		archetype = pick_archetype(_rng)
	_arch = Balance.AI_ARCHETYPES[archetype]
	faction = String(_arch.get("faction", "marauder"))
	if faction == "resident" and not has_meta("hostile"):
		hostile_to_players = false
	if loadout_id == "":
		loadout_id = loadout_for(archetype, _rng)
	_equip_loadout()
	_use("primary" if equipment.has("primary") else "secondary")
	_grenades = int(Balance.AI_GRENADE.count)
	_health.max_hp = Balance.MARAUDER_HP * float(_arch.hp)
	_health.hp = _health.max_hp
	# броня, плиты, шлем — Armor (хост)
	_health.damage_filter = func(a: float, zone: String, from: Vector3, at: Vector3, bullet: Dictionary) -> Array:
		var p := at if at != Vector3.INF else global_position + Vector3.UP * 1.3
		var r := Armor.hit(equipment, a, zone, from, p, Vector3(sin(_facing), 0.0, cos(_facing)), bullet, _rng)
		if String(r.layer) != "":
			equipment = r.equipment
			Audio.play("impact_helmet" if String(r.layer) == "helmet" else "impact_plate", p)
		return [float(r.damage), bool(r.lethal)]
	# тяжело ранен вместо смерти
	_health.can_down = true
	_health.downed_changed.connect(_on_downed_changed)
	# видно, кто перед тобой: цвет куртки; рост у всех натуральный (масштаба по типу нет с 2026-10-24)
	_base_scale = _arch.get("scale", Vector3.ONE)
	_body.scale = _base_scale
	var torso := _body.get_node("Torso") as MeshInstance3D
	var coat := (torso.get_surface_override_material(0) as StandardMaterial3D).duplicate() as StandardMaterial3D
	coat.albedo_color = _arch.color
	torso.set_surface_override_material(0, coat)
	_health.died.connect(_on_died)
	_health.damaged.connect(_on_damaged)
	NoiseBus.noise.connect(_on_noise)
	NoiseBus.callout.connect(_on_callout)
	_agent.path_desired_distance = 0.6
	_agent.target_desired_distance = 0.8
	_agent.radius = 0.4
	# дошёл до связки «перелезть» — перелезает (выбитая витрина — просто проходит)
	_agent.link_reached.connect(_on_link_reached)
	_muzzle.visible = false
	# своя форма коллизии — присев, мародёр ниже (форма в сцене общая для всех)
	var cs := $Capsule as CollisionShape3D
	_capsule = (cs.shape as CapsuleShape3D).duplicate()
	cs.shape = _capsule
	# оружие в правой руке — видно, чем вооружён (с обвесом); при смерти прячется вместе с телом
	_show_gun()
	pause_timer = _rng.randf_range(0.5, 2.0)
	# в темноте — фонарь: мародёр видит, но и себя выдаёт (у каждого peer по условиям рейда)
	_torch = SpotLight3D.new()
	_torch.name = "Torch"
	_torch.position = Vector3(0.15, 1.45, 0.25)
	_torch.rotation.y = PI
	_torch.rotation.x = deg_to_rad(-8.0)
	_torch.light_color = Color(1.0, 0.95, 0.85)
	_torch.light_energy = Balance.AI_TORCH_ENERGY
	_torch.spot_range = Balance.AI_TORCH_RANGE
	_torch.spot_angle = 26.0
	# с тенью: иначе луч светит сквозь стены
	_torch.shadow_enabled = true
	_fade(_torch)
	_torch.visible = false
	_torch.add_to_group("glare_lights")
	LampGlow.attach(_torch)
	_body.add_child(_torch)
	if RaidWeather.current:
		RaidWeather.current.changed.connect(_on_weather)
	_on_weather.call_deferred()
	# шаги слышны у всех peer (AI считает хост, позицию клиенты получают синхронизатором)
	var steps := Footsteps.new()
	steps.name = "Footsteps"
	steps.ai = true
	steps.loud_db = func() -> float: return -5.0 if crouched else 0.0
	add_child(steps)
	# Навмеш печётся после загрузки сектора — пока его нет, стоим (готовность проверяем в
	# _physics_process: появившийся позже сигнала map_changed не должен стоять вечно).
	NavigationServer3D.map_changed.connect(func(_m: RID) -> void: _nav_ready = true)
	if Net.is_networked():
		_setup_sync()


## Случайный тип по долям AI_ARCHETYPES.
static func pick_archetype(rng: RandomNumberGenerator) -> String:
	var total := 0.0
	for k in Balance.AI_ARCHETYPES:
		total += float(Balance.AI_ARCHETYPES[k].weight)
	var pick := rng.randf() * total
	for k in Balance.AI_ARCHETYPES:
		pick -= float(Balance.AI_ARCHETYPES[k].weight)
		if pick <= 0.0:
			return String(k)
	return "gunner"


## Снаряжение для типа (с шансом — главарь).
static func loadout_for(arch: String, rng: RandomNumberGenerator) -> String:
	var a: Dictionary = Balance.AI_ARCHETYPES.get(arch, Balance.AI_ARCHETYPES.gunner)
	var lead: Dictionary = a.get("leader", {})
	if not lead.is_empty() and rng.randf() < float(lead.chance):
		return String(lead.loadout)
	return String(a.get("loadout", "scav_standard"))


## Совместимость со старыми спавнерами.
static func weapon_for(arch: String, rng: RandomNumberGenerator) -> String:
	return loadout_for(arch, rng)


## Снаряжение из data/loadouts.json: оружие по пресетам, запасные магазины тем же патроном,
## броня с плитами, шлем, гарнитура, аптечки; износ — dur снаряжения.
func _equip_loadout() -> void:
	var lo := WeaponDb.loadout(loadout_id)
	if lo.is_empty():
		lo = WeaponDb.loadout("scav_standard")
	var dr: Array = lo.get("dur", [])
	var p1 := _pick(lo.get("primary", []))
	if weapon != "":
		p1 = String(LEGACY_WEAPON.get(weapon, weapon)) if not WeaponDb.preset(String(LEGACY_WEAPON.get(weapon, weapon))).is_empty() else p1
	if p1 != "":
		equipment["primary"] = WeaponDb.make_weapon(p1, _rng, dr)
	var p2 := _pick(lo.get("secondary", []))
	if p2 != "":
		equipment["secondary"] = WeaponDb.make_weapon(p2, _rng, dr)
	# снятый с тела ствол пристрелян не под игрока: ноль сбит (самому мародёру это не мешает).
	# Случайность — общая, не _rng мародёра: его броски (поведение, выкладка) не сдвигаются.
	for slot_key: String in ["primary", "secondary"]:
		if equipment.has(slot_key):
			Gear.knock_zero(equipment[slot_key], Balance.ZEROING.found_moa)
	var sm: Array = lo.get("spare_mags", [1, 2])
	for slot in ["primary", "secondary"]:
		if not equipment.has(slot):
			continue
		var e: Dictionary = equipment[slot]
		var mag: Dictionary = e.mag
		var n := _rng.randi_range(int(sm[0]), int(sm[1])) if slot == "primary" else 1
		var pr := WeaponDb.preset(p1 if slot == "primary" else p2)
		var cap := WeaponDb.capacity(e)
		if String(mag.get("id", "")) == "":
			spare.append({"id": String(mag.ammo), "n": cap * n})
		else:
			for k in range(n):
				var aid := WeaponDb.pick_ammo(pr.get("ammo", []), _rng, String(WeaponDb.weapon(String(e.id)).caliber))
				spare.append(WeaponDb.make_mag(String(mag.id), aid, cap))
	var wear := _rng.randf_range(float(dr[0]), float(dr[1])) / 100.0 if dr.size() == 2 else 1.0
	var vid := _pick(lo.get("armor", []))
	if vid != "":
		var ps := {}
		for side in ["front", "back"]:
			var pid := _pick(lo.get("plates", []))
			if pid != "":
				ps[side] = pid
		equipment["armor"] = WeaponDb.make_vest(vid, ps, wear)
	var hid := _pick(lo.get("helmet", []))
	if hid != "":
		var h := ItemDb.make(hid, 1)
		h.dur = roundf(float(h.dur) * wear)
		equipment["helmet"] = h
	var ear := _pick(lo.get("headset", []))
	if ear != "":
		equipment["ears"] = ItemDb.make(ear, 1)
	# рюкзак — у части мародёров (data/loadouts.json "backpack"), выпадает в ящик с тела
	var bpk := _pick(lo.get("backpack", []))
	if bpk != "":
		equipment["backpack"] = ItemDb.make(bpk, 1)
	for m in lo.get("meds", []):
		if _rng.randf() < float(m[1]):
			meds.append({"id": String(m[0]), "n": _rng.randi_range(int(m[2][0]), int(m[2][1]))})


## Взвешенный выбор из [[id, вес], …]; "" — ничего.
func _pick(list: Array) -> String:
	var total := 0.0
	for e in list:
		total += float(e[1])
	if total <= 0.0:
		return ""
	var r := _rng.randf() * total
	for e in list:
		r -= float(e[1])
		if r <= 0.0:
			return String(e[0])
	return String(list[0][0])


## Взять в руки оружие slot: патроны прежнего остаются в его магазине.
func _use(slot: String) -> void:
	if not equipment.has(slot):
		return
	if equipment.has(_active) and _active != slot and not _spec.is_empty():
		_store_mag_rounds()
	_active = slot
	var e: Dictionary = Gear.normalize_chamber(equipment[slot])
	Gear.chamber_round(e)
	equipment[slot] = e
	_spec = _ai_spec(e)
	_mag = Gear.total_rounds(e)
	_reload_t = 0.0
	_burst_left = 0
	if _body and is_inside_tree():
		_show_gun()


## _mag включает патронник: его нельзя записать целиком в магазин при смене оружия или смерти.
func _store_mag_rounds() -> void:
	if not equipment.has(_active):
		return
	var entry: Dictionary = equipment[_active]
	(entry.mag as Dictionary)["rounds"] = maxi(0, _mag - int(entry.get("chamber", 0)))


## Характеристики для ИИ: оружие и патрон (WeaponStats) + как ИИ стреляет этим классом (AI_CLASS).
func _ai_spec(e: Dictionary) -> Dictionary:
	var ws := WeaponStats.compute(e)
	var c: Dictionary = Balance.AI_CLASS.get(String(ws["class"]), Balance.AI_CLASS.ASSAULT_RIFLE)
	var skill := float(WeaponDb.loadout(loadout_id).get("skill", 1.0))
	var worn: float = 1.0 - WeaponCondition.effectiveness(e)
	var wear_spread: float = 1.0 + worn * worn * float(Balance.WEAPON_WEAR.spread)
	return {"class": String(ws["class"]), "mag": int(ws.mag) + int(WeaponDb.weapon(String(e.id)).get("chamber_capacity", 0)), "reload": float(ws.reload) * Balance.AI_RELOAD_K,
		"interval": maxf(float(ws.interval), float(c.interval_min)), "burst": int(c.burst) if bool(ws.auto) else 1,
		"burst_pause": float(c.burst_pause), "damage": float(ws.damage) * Balance.AI_DAMAGE_K, "pellets": int(ws.pellets),
		"spread": float(c.spread) * wear_spread / maxf(skill, 0.3), "range": float(c.range), "noise_m": float(ws.noise_m),
		"db": float(ws.db), "sound": String(ws.sound), "reload_sound": String(ws.reload_sound), "cycle_sound": String(ws.cycle_sound),
		"sounds": (ws.sounds as Dictionary).duplicate(), "pen": float(ws.pen), "armor_dmg": float(ws.armor_dmg),
		"flash": float(ws.flash), "falloff": ws.get("falloff", []), "point_blank": ws.get("point_blank", []), "range_m": float(ws.range_m)}


func _weapon_sound(slot: String) -> String:
	return String((_spec.get("sounds", {}) as Dictionary).get(slot, ""))


func _play_weapon_sound(slot: String, extra_db: float = 0.0) -> void:
	var kind := _weapon_sound(slot)
	if kind != "":
		Audio.play(kind, global_position, extra_db)


## Модель оружия в руке — по тому, что в руках.
func _show_gun() -> void:
	if _main_gun:
		_main_gun.queue_free()
		_main_gun = null
	if not equipment.has(_active):
		return
	var e: Dictionary = equipment[_active]
	var gun := WeaponModels.build(String(e.id), e.get("mods", {}), 1, WeaponCondition.percent(e), WeaponMods.mag_state(e), WeaponMark.marks(e))
	for l in gun.find_children("Flashlight_*", "SpotLight3D", true, false):
		_fade(l as Light3D)
	# в правой руке модели (кость руки): идёт за руками в любой позе; без Persona — у груди
	var anim := get_node_or_null("CharacterAnimator") as CharacterAnimator
	var grip: Node3D = anim.weapon_grip(String(WeaponDb.weapon(String(e.id)).get("model", "rifle")), String(e.id)) if anim else null
	if grip:
		grip.add_child(gun)
	else:
		var pistol := String(WeaponDb.weapon(String(e.id)).get("class", "")) == "PISTOL"
		gun.position = Vector3(-0.17, 1.24, 0.3 if pistol else 0.22) / _base_scale
		_body.add_child(gun)
	_main_gun = gun


## Фонарь ИИ далеко от камеры гаснет, тень — только вблизи (Balance.AI_LIGHT_FADE).
static func _fade(l: Light3D) -> void:
	var f: Dictionary = Balance.AI_LIGHT_FADE
	l.distance_fade_enabled = true
	l.distance_fade_begin = float(f.begin)
	l.distance_fade_length = float(f.length)
	l.distance_fade_shadow = float(f.shadow)


## Куда попала пуля: голова (присел — ниже), ноги, руки (сбоку от оси корпуса), грудь; лежащий —
## голова или грудь.
func hit_zone(point: Vector3) -> String:
	var hz := float(Balance.HEAD_ZONE["crouch" if crouched else "stand"]) * _base_scale.y
	var dy := point.y - global_position.y
	if dy >= hz and not _health.downed:
		return "head"
	if _health.downed:
		return "thorax"
	if dy < hz * float(Balance.ZONE_SHAPE.legs):
		return "legs"
	var d := point - global_position
	d.y = 0.0
	var f := Vector3(sin(_facing), 0.0, cos(_facing))
	return "arms" if (d - f * d.dot(f)).length() > float(Balance.ZONE_SHAPE.arms_w) * _base_scale.x else "thorax"


## Держит позицию (снайпер): не сближается, ищет глазами. В тумане снайпер — обычный боец.
func _holds() -> bool:
	return bool(_arch.get("holds", false)) and not _fogged


## Погода сменилась (или рейд начался): в тумане снайпер убирает винтовку и воюет с пистолетом;
## туман ушёл — снова винтовка.
func _on_weather() -> void:
	var fog := String(RaidConditions.current.get("weather", "")) == "fog"
	if not bool(_arch.get("holds", false)) or fog == _fogged or _health.downed:
		return
	_fogged = fog
	if not equipment.has("secondary"):
		_fogged = false
		return
	_use("secondary" if fog else "primary")
	say("Ничего не видно — ближе работаем" if fog else "Туман ушёл. На позицию.")


## Память о цели по типу (разведчик забывает быстро, снайпер помнит долго).
func _mem() -> float:
	return Balance.AI_MEMORY_SEC * float(_arch.get("memory", 1.0)) * Balance.lab_number("perception", "memory")


## Мародёр целиком авторитет хоста (умалчиваемый multiplayer authority узла — 1). AI и движение
## считает только хост; остальные peer просто получают позицию/позу синхронизатором.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:global_position", "Body:rotation", "Body:position", "Body:scale", ".:state", ".:crouched", ".:look_pitch", ".:recovered_weapon", ".:animation_event", ".:animation_event_seq"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	Net.scope_sync(self, sync)
	add_child(sync)


static var work_profile_enabled: bool = false
static var work_profile: Dictionary = {}


static func _record_work(key: String, started: int) -> void:
	var row: Dictionary = work_profile.get(key, {"us": 0, "count": 0, "max_us": 0})
	var elapsed: int = Time.get_ticks_usec() - started
	row.us = int(row.us) + elapsed
	row.count = int(row.count) + 1
	row.max_us = maxi(int(row.max_us), elapsed)
	work_profile[key] = row


func _physics_process(delta: float) -> void:
	if Net.is_networked() and not is_multiplayer_authority():
		return
	if state == State.DEAD:
		return
	if not _nav_ready:
		var map := get_world_3d().navigation_map
		_nav_ready = NavigationServer3D.map_get_iteration_id(map) > 0 and not NavigationServer3D.map_get_regions(map).is_empty()
	_hurt_t = maxf(0.0, _hurt_t - delta)
	_stagger_t = maxf(0.0, _stagger_t - delta)
	_flinch = move_toward(_flinch, 0.0, delta * 3.0)
	if _post == Vector3.INF:
		_post = global_position
	_suppress_t = maxf(0.0, _suppress_t - delta)
	_shot_heard_t += delta
	_repath_t -= delta
	var work_started: int = Time.get_ticks_usec() if work_profile_enabled else 0
	_perceive(delta)
	if work_profile_enabled:
		_record_work("perception", work_started)
	work_started = Time.get_ticks_usec() if work_profile_enabled else 0
	_tick_weapon(delta)
	if work_profile_enabled:
		_record_work("weapon", work_started)
	work_started = Time.get_ticks_usec() if work_profile_enabled else 0
	match state:
		State.DOWNED:
			_downed(delta)
		State.RESCUE:
			_rescue(delta)
		State.PATROL:
			_patrol(delta)
		State.INVESTIGATE:
			_investigate(delta)
		State.COMBAT:
			_combat(delta)
		State.SEARCH:
			_search(delta)
		State.RETREAT:
			_retreat(delta)
	if work_profile_enabled:
		_record_work("decision", work_started)
	work_started = Time.get_ticks_usec() if work_profile_enabled else 0
	_move(delta)
	if work_profile_enabled:
		_record_work("move", work_started)


func _eye() -> Vector3:
	return global_position + Vector3.UP * (CROUCH_EYE if crouched else EYE_HEIGHT)


# ---------------------------------------------------------------- восприятие

func _perceive(delta: float) -> void:
	var seen: Player = null
	var seen_down: Player = null
	var fwd := Vector3(sin(_facing), 0.0, cos(_facing))
	var exclude: Array[RID] = [get_rid()]
	for p in get_tree().get_nodes_in_group("players"):
		var player := p as Player
		if player == null or not player.is_alive():
			continue
		# жилец не трогает игрока, пока тот к ним не полез
		if not hostile_to_players and not _trespass(player):
			continue
		if Perception.can_see(get_world_3d(), _eye(), fwd, player, exclude, float(_arch.get("view", 1.0))):
			if player.is_downed():
				if seen_down == null:
					seen_down = player
			else:
				seen = player
				break
	# лежащий — не угроза, пока стреляют другие; стреляет сам или тихо — добить
	if seen == null and seen_down != null and _may_finish(seen_down):
		seen = seen_down
	# игроков не видно — может, видно врага другой фракции
	var foe: Marauder = null
	if seen == null:
		foe = _scan_foes(delta, fwd, exclude)
	var was_seen := _seen_now
	_seen_now = false
	if seen == null and foe:
		_foe = foe
		_target_player = null
		_seen_now = true
		_unseen_t = 0.0
		last_known = foe.global_position
		memory_timer = _mem()
		if not was_seen:
			_aim = _fresh_aim(foe.global_position)
		_ambush_rolled = false
		if state != State.COMBAT and state != State.RETREAT and state != State.DOWNED and state != State.RESCUE:
			_enter_combat(Tactic.ENGAGE)
			say(_foe_shout(foe))
			_shout()
	elif seen:
		_foe = null
		# Заметить — не мгновенно: вблизи — за доли секунды, на сотне метров — секунды; лёжа и
		# присев — дольше, бегущего и стреляющего — быстрее (Balance.AI_NOTICE)
		var dist := global_position.distance_to(seen.global_position)
		notice_timer += delta / _notice_sec(seen, dist)
		if notice_timer >= 1.0 or state == State.COMBAT:
			_seen_now = true
			_unseen_t = 0.0
			_target_player = seen
			player_contact_ms = Time.get_ticks_msec()
			last_known = seen.global_position
			memory_timer = _mem()
			if not was_seen:
				# только что поймал в поле зрения — первые выстрелы мимо (из засады — почти сразу в цель)
				_aim = _fresh_aim(seen.global_position)
			_ambush_rolled = false
			if state != State.COMBAT and state != State.RETREAT and state != State.DOWNED and state != State.RESCUE:
				_enter_combat(Tactic.ENGAGE)
				say("Контакт!")
				_shout()
			_callout_t -= delta
			if _callout_t <= 0.0:
				_shout()
	else:
		notice_timer = maxf(0.0, notice_timer - delta * 0.5 / float(Balance.AI_NOTICE.far_sec))
		_unseen_t += delta
		if state == State.COMBAT:
			memory_timer -= delta
			if memory_timer <= 0.0:
				_start_search()
	# горящая ракета рядом, смотрит на неё — слепит: целится как только что заметивший
	_blind_t -= delta
	if _blind_t <= 0.0:
		_blind_t = _next_work_delay(_blind_t, float(Balance.AI_WORK.glare_scan_sec))
		for f in get_tree().get_nodes_in_group("flares"):
			var to := (f as Node3D).global_position - global_position
			if to.length() < Balance.FLARE_BLIND_M and fwd.dot(Vector3(to.x, 0.0, to.z).normalized()) > 0.8:
				_aim = maxf(_aim, Balance.AI_AIM_COLD)
				break
		# фонарь светит в глаза (видно сам фонарь, луч на мне, смотрю на него) — слепит так же
		if _flashlight_glare():
			_aim = maxf(_aim, Balance.AI_AIM_COLD)
	# прицел садится, пока цель на виду; на дальней — дольше
	if _seen_now:
		var sf: Dictionary = Balance.AI_AIM_SETTLE_FAR
		var settle := lerpf(Balance.AI_AIM_SETTLE_SEC, float(sf.far_sec), smoothstep(float(sf.near_m), float(sf.far_m), global_position.distance_to(last_known)))
		_aim = move_toward(_aim, 1.0, delta * (Balance.AI_AIM_COLD - 1.0) / settle)


## Фонарь на оружии светит мне в лицо: близко (FLASHLIGHT_BLIND_M), я в луче, смотрю в его
## сторону и между нами нет стены. Это то, что видит глаз, а не знание, где игрок.
func _flashlight_glare() -> bool:
	var eye := _eye()
	var fwd := Vector3(sin(_facing), 0.0, cos(_facing))
	for n in get_tree().get_nodes_in_group("glare_lights"):
		var l := n as SpotLight3D
		if l == null or not l.is_visible_in_tree() or is_ancestor_of(l):
			continue
		# свои не слепят: свой фонарь товарищ в лицо не наводит
		var holder := l.get_parent()
		while holder and not (holder is Marauder or holder is Player):
			holder = holder.get_parent()
		if holder is Marauder and (holder as Marauder).faction == faction:
			continue
		var to_me := eye - l.global_position
		var d := to_me.length()
		if d > Balance.FLASHLIGHT_BLIND_M or d < 0.1:
			continue
		if (-l.global_basis.z).dot(to_me / d) < cos(deg_to_rad(l.spot_angle * 0.8)):
			continue
		if fwd.dot(Vector3(-to_me.x, 0.0, -to_me.z).normalized()) < 0.6:
			continue
		var q := PhysicsRayQueryParameters3D.create(eye, l.global_position, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
		if get_world_3d().direct_space_state.intersect_ray(q).is_empty():
			return true
	return false


## Враг другой фракции в поле зрения (раз в 0.3 с; цель держим, пока видна).
func _scan_foes(delta: float, fwd: Vector3, exclude: Array[RID]) -> Marauder:
	var hostile: Array = Balance.AI_HOSTILE.get(faction, [])
	if hostile.is_empty():
		return null
	var view := float(_arch.get("view", 1.0))
	if _foe and is_instance_valid(_foe) and _foe.state != State.DEAD:
		if Perception.can_see_body(get_world_3d(), _eye(), fwd, _foe, exclude, view, _foe.state == State.DOWNED):
			return _foe
	_foe_t -= delta
	if _foe_t > 0.0:
		return null
	_foe_t = _next_work_delay(_foe_t, float(Balance.AI_WORK.foe_scan_sec))
	var best: Marauder = null
	var best_d := INF
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == null or m == self or m.state == State.DEAD or not m.faction in hostile:
			continue
		# чужие отряды враждуют и между собой, но не внутри своего отряда
		if m.faction == faction and m.squad == squad:
			continue
		var d := m.global_position.distance_to(global_position)
		if d < best_d and Perception.can_see_body(get_world_3d(), _eye(), fwd, m, exclude, view, m.state == State.DOWNED):
			best = m
			best_d = d
	return best


func _foe_shout(foe: Marauder) -> String:
	match foe.faction:
		"pmc":
			return "Периметр! Наёмники!"
		"resident":
			return "Тут крысы засели!"
		"rival":
			return "Чужая группа! Контакт!"
	return "Мародёры!"


## Жильцы: игрок полез к ним — зашёл близко к их магазину (дом) или стрелял рядом / попал.
func _trespass(p: Player) -> bool:
	return home != Vector3.INF and p.global_position.distance_to(home) < float(Balance.RESIDENTS.trespass_m) + home_radius * 0.5


## Жильцы: вся группа стала враждебной игрокам.
func provoke() -> void:
	if faction != "resident" or hostile_to_players:
		return
	for m in (squad.alive() if squad else [self]):
		(m as Marauder).hostile_to_players = true
	say("Пошли вон отсюда!")


## Добить лежащего игрока можно, если давно никто не стрелял — или стреляет он сам.
func _may_finish(p: Player) -> bool:
	return _shot_heard_t >= Balance.AI_FINISH_QUIET_SEC or _shot_heard_pos.distance_to(p.global_position) < 2.5


## Окрик: товарищи в радиусе узнают, где цель (сами её могут и не видеть).
func _shout() -> void:
	_callout_t = Balance.AI_CALLOUT_EVERY
	NoiseBus.shout(global_position, Balance.AI_CALLOUT_RADIUS, last_known, self)


func _on_callout(from: Vector3, radius_m: float, target: Vector3, speaker: Node) -> void:
	if speaker == self or state in [State.DEAD, State.RETREAT, State.DOWNED, State.RESCUE]:
		return
	# окрик — только своим
	if speaker is Marauder and (speaker as Marauder).faction != faction:
		return
	# у чужих отрядов «свои» — только свой отряд
	if speaker is Marauder and faction == "rival" and (speaker as Marauder).squad != squad:
		return
	if global_position.distance_to(from) > radius_m:
		return
	if _seen_now:
		return
	last_known = target
	memory_timer = maxf(memory_timer, _mem() * 0.6)
	if state != State.COMBAT:
		# сам не видел — идёт туда, куда крикнули (второй в отряде — в обход, далеко — перебежками)
		_enter_combat(Tactic.FLANK if _rank() == 1 else _closing_tactic())


func _on_noise(pos: Vector3, radius_m: float, kind: String) -> void:
	radius_m *= Balance.lab_number("perception", "hearing")
	if state == State.DEAD:
		return
	if kind == "shot" and global_position.distance_to(pos) <= radius_m:
		_shot_heard_t = 0.0
		_shot_heard_pos = pos
		# жильцы: стреляют у самого их магазина — значит, к ним
		if faction == "resident" and home != Vector3.INF and pos.distance_to(home) < float(Balance.RESIDENTS.trespass_m) + home_radius:
			provoke()
	if state == State.DOWNED or state == State.RESCUE:
		return
	var d := global_position.distance_to(pos)
	if d > radius_m:
		return
	if state == State.COMBAT:
		# стреляет цель, которую мы и так ищем, — пули свистят рядом: пора в укрытие
		if kind == "shot" and pos.distance_to(last_known) < 8.0 and d < Balance.AI_ENGAGE_RANGE:
			_suppress_t = 2.0
			if not _seen_now:
				last_known = pos
		return
	if state == State.RETREAT:
		return
	# проверять идут не больше AI_NOISE_RESPONSE.groups групп — остальные настороже на месте
	if faction == "marauder" and d > Balance.AI_INVESTIGATE_NEAR and not _may_respond(pos, radius_m):
		var head := squad.leader() if squad else self
		if head != null:
			head.alert_at(pos)
		return
	# ведомый: шёпотом ведущему — проверяют отрядом, строем за ним
	var lead := squad.leader() if squad else null
	if lead != null and lead != self and lead.state in [State.PATROL, State.INVESTIGATE] \
			and lead.global_position.distance_to(global_position) < 15.0:
		lead.investigate_at(pos)
		return
	# другой отряд уже идёт смотреть это место — не толпимся (если шум не под самым носом)
	if d > Balance.AI_INVESTIGATE_NEAR and _someone_checking(pos):
		return
	investigate_at(pos)


## Проверить шум: идти к месту, постоять, осмотреться; потом прочесать рядом.
func investigate_at(pos: Vector3) -> void:
	if state in [State.COMBAT, State.RETREAT, State.DEAD, State.DOWNED, State.RESCUE]:
		return
	last_known = pos
	state = State.INVESTIGATE
	linger_timer = Balance.AI_INVESTIGATE_LINGER
	# держащий позицию — не идёт, только поворачивается на шум
	_set_move_target(global_position if _holds() else _snap(pos))
	if _holds():
		_face(pos)


## Может ли отряд пойти проверять шум в pos (Balance.AI_NOISE_RESPONSE): места хватает, если отрядов,
## уже занятых этим местом, и услышавших шум свободных отрядов ближе нашего меньше groups. Расстояние
## отряда — его ближайший боец, поэтому все бойцы одного отряда решают одинаково, а порядок, в котором
## бойцы услышали шум, не важен: идут ближайшие.
func _may_respond(pos: Vector3, radius_m: float) -> bool:
	if squad == null:
		return true
	var cfg: Dictionary = Balance.AI_NOISE_RESPONSE
	var same_m: float = float(cfg.same_m)
	var busy: Dictionary = {}
	var free_d: Dictionary = {}
	var mine := INF
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == null or m.faction != faction or m.squad == null or m.state in [State.DEAD, State.DOWNED, State.RESCUE, State.RETREAT]:
			continue
		# занят этим местом: идёт сюда / ищет здесь / воюет здесь (шум — его же выстрелы)
		var engaged := m.state in [State.INVESTIGATE, State.SEARCH, State.COMBAT] and m.last_known.distance_to(pos) < same_m
		engaged = engaged or (m.state == State.COMBAT and m.global_position.distance_to(pos) < same_m)
		if m.squad == squad:
			# свой отряд уже занят этим местом — продолжаем
			if engaged:
				return true
			mine = minf(mine, m.global_position.distance_to(pos))
			continue
		if engaged:
			busy[m.squad] = true
		elif m.state in [State.PATROL, State.INVESTIGATE, State.SEARCH]:
			var d := m.global_position.distance_to(pos)
			if d <= radius_m:
				free_d[m.squad] = minf(d, float(free_d.get(m.squad, INF)))
	var nearer := 0
	for s in free_d:
		if not busy.has(s) and float(free_d[s]) < mine:
			nearer += 1
	return busy.size() + nearer < int(cfg.groups)


## Насторожиться: шум слышал, но проверяют другие (AI_NOISE_RESPONSE) — стоит и смотрит туда. Увидит
## цель сам — бой как обычно.
func alert_at(pos: Vector3) -> void:
	if state != State.PATROL:
		return
	var sec: Array = Balance.AI_NOISE_RESPONSE.alert_sec
	_alert_until = Time.get_ticks_msec() + int(_rng.randf_range(float(sec[0]), float(sec[1])) * 1000.0)
	_alert_at = pos
	_drop_loot_claim()
	_set_crouch(false)
	_set_move_target(global_position)


func is_alert() -> bool:
	return Time.get_ticks_msec() < _alert_until and state == State.PATROL


## Другой отряд уже проверяет / прочёсывает место рядом с pos.
func _someone_checking(pos: Vector3) -> bool:
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.squad == squad or not (m.state in [State.INVESTIGATE, State.SEARCH]):
			continue
		if m.last_known.distance_to(pos) < Balance.AI_INVESTIGATE_SHARE_M:
			return true
	return false


## Куда сейчас идёт (для «не толпиться»): цель навигации.
func move_target() -> Vector3:
	return _agent.target_position


## Кто-то другой (жив, в бою/поиске/проверке) уже идёт к точке или стоит ближе r.
func _claimed_near(p: Vector3, r: float) -> bool:
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.state in [State.DEAD, State.PATROL]:
			continue
		if m.move_target().distance_to(p) < r or m.global_position.distance_to(p) < r * 0.6:
			return true
	return false


## Точка рядом с center, куда никто не идёт: сам center, если свободен, иначе в стороне.
func _spread_point(center: Vector3) -> Vector3:
	var c := _snap(center)
	if not _claimed_near(c, Balance.AI_SPREAD_CLAIM_M):
		return c
	for i in range(8):
		var a := _rng.randf() * TAU
		var r := _rng.randf_range(float(Balance.AI_SPREAD_RADIUS[0]), float(Balance.AI_SPREAD_RADIUS[1]))
		var p := _snap(center + Vector3(cos(a), 0.0, sin(a)) * r)
		if absf(p.y - c.y) < 0.5 and not _claimed_near(p, Balance.AI_SPREAD_CLAIM_M):
			return p
	return c


func _on_damaged(amount: float, from: Vector3) -> void:
	_animation_event("hit")
	Audio.play("pain_ai", global_position + Vector3.UP * 1.2)
	_last_hit_from = from
	_last_damage = amount
	if state == State.DEAD:
		return
	# хроника рейда: урон от игрока — стрелявшему
	if Raid.current and _health.last_attacker > 0:
		Raid.current.story_dealt(_health.last_attacker, amount)
	_hurt_t = 2.5
	# в жильца попал игрок — вся группа враждебна
	if faction == "resident" and _health.last_attacker > 0:
		provoke()
	# повело: медленнее, целится хуже, следующий выстрел позже; корпус откинуло (тяжёлого — меньше)
	_stagger_t = Balance.AI_HIT_STAGGER_SEC
	_flinch = clampf(amount / 25.0, 0.4, 1.0) / float(_arch.get("hp", 1.0))
	_shot_t = maxf(_shot_t, Balance.AI_HIT_FLINCH_DELAY)
	# Попадание — улика: откуда прилетело, понятно примерно (направление ± AI_HIT_DIR_ERR_DEG,
	# дальность ± AI_HIT_DIST_ERR); кого видит — того и так знает
	if not _seen_now:
		var to := from - global_position
		to.y = 0.0
		var guess := to.rotated(Vector3.UP, deg_to_rad(_rng.randf_range(-1.0, 1.0) * Balance.AI_HIT_DIR_ERR_DEG))
		guess *= 1.0 + _rng.randf_range(-1.0, 1.0) * Balance.AI_HIT_DIST_ERR
		last_known = global_position + guess
	memory_timer = maxf(memory_timer, _mem() * 1.5)
	_facing = atan2(last_known.x - global_position.x, last_known.z - global_position.z)
	if state == State.DOWNED or state == State.RESCUE or _health.downed:
		return
	if state != State.COMBAT and state != State.RETREAT:
		state = State.COMBAT
		say("По нам стреляют!")
		_shout()
		# стрелка не видно — сначала за укрытие, потом перебежками к нему
		if _seen_now or not _try_cover(Balance.AI_COVER_RADIUS, false):
			_set_tactic(Tactic.ENGAGE if _seen_now else Tactic.ADVANCE)
	elif not _seen_now and tactic in [Tactic.ENGAGE, Tactic.PUSH, Tactic.FLANK, Tactic.ADVANCE]:
		_try_cover(Balance.AI_COVER_RADIUS, false)
	# тяжело ранен, товарищей рядом нет — отход
	if _health.hp < _health.max_hp * Balance.AI_RETREAT_HP and _mates_near(15.0) == 0 and state != State.RETREAT:
		_start_retreat()


# ---------------------------------------------------------------- состояния

func _rank() -> int:
	return squad.rank_of(self) if squad else 0


func _mates_near(r: float) -> int:
	if squad == null:
		return 0
	var n := 0
	for m in squad.alive():
		if m != self and m.global_position.distance_to(global_position) <= r:
			n += 1
	return n


func _patrol(delta: float) -> void:
	if _loot_t < 0.0:
		_set_crouch(false)
	if not _nav_ready:
		return
	if String(_order.get("kind", "")) == "hold":
		# прикрывает, пока товарищ обыскивает тела: стоит на месте, смотрит наружу
		if Time.get_ticks_msec() >= int(_order.until):
			_order = {}
		else:
			if _agent.is_navigation_finished():
				_set_crouch(true)
				_face(_order.face)
			return
	var lead := squad.leader() if squad else null
	if lead != null and lead != self:
		# ведомый: строем за ведущим, чуть в стороне
		if _repath_t <= 0.0:
			_repath_t = _next_work_delay(_repath_t, float(Balance.AI_WORK.follow_repath_sec))
			var lf := Vector3(sin(lead._facing), 0.0, cos(lead._facing))
			var side := Vector3(lf.z, 0.0, -lf.x) * (1.0 if _rank() % 2 == 1 else -1.0)
			_set_move_target(lead.global_position - lf * Balance.AI_FOLLOW_DIST * _rank() + side * 1.0, true)
		return
	if is_alert():
		# насторожен: шум проверяют другие — стоит, смотрит туда
		_facing = lerp_angle(_facing, atan2(_alert_at.x - global_position.x, _alert_at.z - global_position.z), minf(1.0, 4.0 * delta))
		return
	if _agent.is_navigation_finished():
		pause_timer -= delta
		if _loot_tick(delta):
			return
		if _holds() and watch_dir != Vector3.ZERO:
			_watch_sector(delta)
		if pause_timer <= 0.0 and _holds() and _post != Vector3.INF:
			# держит позицию: пара шагов у поста, долго смотрит
			var a := _rng.randf() * TAU
			var hr: float = hold_radius if hold_radius >= 0.0 else Balance.AI_HOLD_PATROL_R
			_set_move_target(_post + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(0.0, hr), true)
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1])) * 3.0
		elif pause_timer <= 0.0 and home_radius > 0.0 and home != Vector3.INF:
			# охраняет место: ходит вокруг (гарнизон поста — по его точкам), смотрит
			var ha := _rng.randf() * TAU
			var to := home + Vector3(cos(ha), 0.0, sin(ha)) * _rng.randf_range(1.0, home_radius)
			if not home_points.is_empty():
				to = home_points[_rng.randi_range(0, home_points.size() - 1)]
			_set_move_target(to, true)
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1])) * 1.5
		elif pause_timer <= 0.0 and not route.is_empty():
			# патруль: следующая точка маршрута
			_set_move_target(_next_route_point(), true)
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1]))
		elif pause_timer <= 0.0 and not _holds() and not no_loot and bool(_arch.get("loots", true)) and _pick_loot():
			pass
		elif pause_timer <= 0.0 and patrol_point_provider.is_valid():
			_set_move_target(patrol_point_provider.call(), true)
			pause_timer = _rng.randf_range(float(Balance.AI_PATROL_PAUSE[0]), float(Balance.AI_PATROL_PAUSE[1]))


## Следующая точка маршрута: первая — ближайшая, дальше по порядку (по кругу или туда-обратно).
func _next_route_point() -> Vector3:
	var n := route.size()
	if _route_i < 0 or _route_i >= n:
		var best := INF
		for i in range(n):
			var d := route[i].distance_to(global_position)
			if d < best:
				best = d
				_route_i = i
		return route[_route_i]
	if n == 1:
		return route[0]
	if route_loop:
		_route_i = (_route_i + 1) % n
	else:
		if _route_i + _route_dir < 0 or _route_i + _route_dir >= n:
			_route_dir = -_route_dir
		_route_i += _route_dir
	return route[_route_i]


## Гнездо: медленно водит взглядом по своему сектору.
func _watch_sector(delta: float) -> void:
	var base := atan2(watch_dir.x, watch_dir.z)
	var sweep := sin(Time.get_ticks_msec() / 1000.0 * 0.35 + float(get_instance_id() % 7)) * deg_to_rad(watch_sector_deg * 0.5)
	_facing = lerp_angle(_facing, base + sweep, minf(1.0, 1.5 * delta))


# ---------------------------------------------------------------- приказы плана отряда (RivalSquad)

## Разорвать контакт: бегом в точку to; дошёл или прошло sec секунд — бой для него окончен.
func break_contact(to: Vector3, sec: float) -> void:
	if state in [State.DEAD, State.DOWNED, State.RESCUE]:
		return
	_drop_loot_claim()
	_order = {"kind": "fallback", "since": Time.get_ticks_msec(), "until": Time.get_ticks_msec() + int(sec * 1000.0)}
	state = State.RETREAT
	_set_crouch(false)
	_set_move_target(to, true)
	linger_timer = sec


## Бой для бойца окончен: цель забыта, он снова идёт по плану отряда (увидит врага — вступит заново).
func stand_down() -> void:
	if state in [State.DEAD, State.DOWNED, State.RESCUE]:
		return
	_order = {}
	state = State.PATROL
	memory_timer = 0.0
	pause_timer = 0.0
	_set_crouch(false)


## Встать в точке pos и смотреть на face, пока не пройдёт sec секунд (или не начнётся бой).
func hold_post(pos: Vector3, face: Vector3, sec: float) -> void:
	if state != State.PATROL:
		return
	_order = {"kind": "hold", "until": Time.get_ticks_msec() + int(sec * 1000.0), "face": face}
	_set_move_target(pos, true)


## Снять приказ «стоять» (обыск окончен).
func release_post() -> void:
	if String(_order.get("kind", "")) == "hold":
		_order = {}


## Обыскать именно этот контейнер (ящик с убитого). false — не до того или сумка полна.
func order_loot(c: LootContainer) -> bool:
	if state != State.PATROL or c == null or pack.size() >= Balance.AI_LOOT_PACK_MAX:
		return false
	_drop_loot_claim()
	_visited.erase(c.get_instance_id())
	_loot_target = c
	_loot_t = -1.0
	_loot_claims[c.get_instance_id()] = [self, Time.get_ticks_msec()]
	_set_move_target(c.global_position, true)
	return true


func is_looting() -> bool:
	return _loot_target != null


# ---------------------------------------------------------------- грабёж

## Выбрать контейнер: ближний (с разбросом), не пустой, не занятый другими, где ещё не был.
func _pick_loot() -> bool:
	if pack.size() >= Balance.AI_LOOT_PACK_MAX:
		return false
	var now := Time.get_ticks_msec()
	var best: LootContainer = null
	var best_s := INF
	for n in get_tree().get_nodes_in_group("loot_containers"):
		var c := n as LootContainer
		if c == null or (c.rolled and c.items.is_empty()) or _visited.has(c.get_instance_id()):
			continue
		var claim: Array = _loot_claims.get(c.get_instance_id(), [])
		if not claim.is_empty() and is_instance_valid(claim[0]) and claim[0] != self and now - int(claim[1]) < int(Balance.AI_LOOT_CLAIM_SEC * 1000.0):
			continue
		var d := c.global_position.distance_to(global_position)
		if d > Balance.AI_LOOT_RANGE:
			continue
		# в дождь — под крышей
		if RaidWeather.current and RaidWeather.current.is_raining() and RaidAtmosphere.current and not RaidAtmosphere.current.is_indoor(c.global_position):
			continue
		var s := d + _rng.randf() * 20.0
		if s < best_s:
			best = c
			best_s = s
	if best == null:
		return false
	_drop_loot_claim()
	_loot_target = best
	_loot_t = -1.0
	_loot_claims[best.get_instance_id()] = [self, now]
	_set_move_target(best.global_position, true)
	return true


func _drop_loot_claim() -> void:
	if _loot_target and is_instance_valid(_loot_target):
		var claim: Array = _loot_claims.get(_loot_target.get_instance_id(), [])
		if not claim.is_empty() and claim[0] == self:
			_loot_claims.erase(_loot_target.get_instance_id())
	_loot_target = null
	_loot_t = -1.0


## Ведущий у контейнера: присел, роется (слышно), забрал ценное. true — занят грабежом.
func _loot_tick(delta: float) -> bool:
	if _loot_target == null:
		return false
	if not is_instance_valid(_loot_target) or (_loot_target.rolled and _loot_target.items.is_empty() and _loot_t < 0.0):
		_drop_loot_claim()
		return false
	if _loot_t < 0.0:
		var to_c := _loot_target.global_position - global_position
		if Vector2(to_c.x, to_c.z).length() > 2.4:
			# ещё идёт; застрял (дошёл, а не рядом) — бросить
			if _agent.is_navigation_finished():
				_visited[_loot_target.get_instance_id()] = true
				_drop_loot_claim()
				return false
			return true
		_loot_t = maxf(Balance.AI_LOOT_SEARCH_MIN, _loot_target.search_s * Balance.AI_LOOT_SEARCH_MULT)
		_set_move_target(global_position)
	_set_crouch(true)
	_face(_loot_target.global_position)
	_loot_t -= delta
	_rummage_t -= delta
	if _rummage_t <= 0.0:
		_rummage_t = _rng.randf_range(0.5, 1.1)
		Audio.play("rummage", _loot_target.global_position, _rng.randf_range(-3.0, 0.0))
	if _loot_t > 0.0:
		return true
	_take_loot(_loot_target)
	_visited[_loot_target.get_instance_id()] = true
	_drop_loot_claim()
	_set_crouch(false)
	# разбирает, что взял, осматривается — и дальше
	pause_timer = _rng.randf_range(2.0, 5.0)
	return true


## Забрать из контейнера самое ценное (до AI_LOOT_TAKE записей) в сумку.
func _take_loot(c: LootContainer) -> void:
	c.roll()
	var list := c.items.duplicate(true)
	list.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return ItemDb.entry_value(a) > ItemDb.entry_value(b))
	var took := 0
	for e in list:
		if took >= Balance.AI_LOOT_TAKE or pack.size() >= Balance.AI_LOOT_PACK_MAX:
			break
		var n := c.take(String(e.id), int(e.n))
		if n <= 0:
			continue
		var got: Dictionary = (e as Dictionary).duplicate(true)
		got.n = n
		pack.append(got)
		took += 1
	if took > 0 and _rng.randf() < 0.3:
		say("Есть кое-что")


func _investigate(delta: float) -> void:
	_set_crouch(false)
	if _agent.is_navigation_finished():
		linger_timer -= delta
		# осматриваемся
		_facing += delta * 1.2
		if linger_timer <= 0.0:
			_start_search(Balance.AI_INVESTIGATE_SEARCH)


func _enter_combat(t: Tactic) -> void:
	_drop_loot_claim()
	state = State.COMBAT
	_ambush_rolled = false
	# отряд вступил в бой — роль (штурм / обход / прикрытие); сам — по роли, если не видит цель
	if squad and not _holds():
		var r := squad.engage(last_known)
		if not _seen_now and t != Tactic.ENGAGE:
			t = _closing_tactic()
		if r == Squad.Role.COVER and not _seen_now:
			t = Tactic.OVERWATCH
	_set_tactic(t)


func _role() -> Squad.Role:
	return squad.role if squad else Squad.Role.NONE


func _set_tactic(t: Tactic) -> void:
	tactic = t
	_tactic_t = 0.0
	if t != Tactic.AMBUSH and t != Tactic.COVER_MOVE:
		_ambush_pending = false
	match t:
		Tactic.FLANK:
			# заходим сбоку: точка в стороне от линии «мы — цель»; отряд обхода — широко и все
			# в одну сторону (своим маршрутом), иначе — второй в отряде, недалеко
			var to := last_known - global_position
			to.y = 0.0
			var wide := _role() == Squad.Role.FLANK
			var sgn := squad.flank_side if wide and squad else (1.0 if _rng.randf() < 0.5 else -1.0)
			var side := Vector3(to.z, 0.0, -to.x).normalized() * sgn
			var off := Balance.AI_ROLE_FLANK_OFFSET if wide else Balance.AI_FLANK_OFFSET
			_set_move_target(_spread_point(last_known + side * off - to.normalized() * (2.0 if wide else 4.0)))
			say("Обхожу!")
		Tactic.OVERWATCH:
			_overwatch_ready = false
			var ow := _overwatch_point()
			if ow == Vector3.INF:
				tactic = Tactic.ADVANCE
				if not _try_advance():
					tactic = Tactic.PUSH
					_set_move_target(_spread_point(last_known))
			else:
				_set_move_target(ow)
				say("Прикрываю!")
		Tactic.PUSH:
			_set_move_target(_spread_point(last_known))
		Tactic.ADVANCE:
			if not _try_advance():
				tactic = Tactic.PUSH
				_set_move_target(_spread_point(last_known))
		Tactic.ENGAGE:
			_set_move_target(global_position)
		Tactic.AMBUSH:
			_ambush_pending = false
			_ambush_at = last_known
			_ambush_t = _rng.randf_range(float(Balance.AI_AMBUSH.hold_sec[0]), float(Balance.AI_AMBUSH.hold_sec[1]))
			if squad:
				squad.ambusher = self
			_set_move_target(global_position)
		_:
			pass


## Цель ушла из виду — сесть в засаду? Шанс AI_AMBUSH.chance × ambush архетипа × ambush_bias, один
## раз на потерю цели; держащий позицию и так ждёт; в упор не садится; в отряде ждёт один. Укрытие
## от последней точки есть на месте — сел сразу, иначе идёт к ближайшему (COVER_MOVE → AMBUSH);
## укрытия нет — засады нет. true — тактика назначена.
func _try_ambush() -> bool:
	if _ambush_rolled or _holds() or state != State.COMBAT:
		return false
	_ambush_rolled = true
	if global_position.distance_to(last_known) < float(Balance.AI_AMBUSH.min_dist):
		return false
	if squad:
		var a := squad.ambusher
		if a != null and is_instance_valid(a) and a != self and a.state == State.COMBAT and a.tactic == Tactic.AMBUSH:
			return false
	var chance := float(Balance.AI_AMBUSH.chance) * float(_arch.get("ambush", 1.0)) * ambush_bias
	if _rng.randf() >= chance:
		return false
	var p := _ambush_point()
	if p == Vector3.INF:
		return false
	if p.distance_to(global_position) < 0.9:
		_set_tactic(Tactic.AMBUSH)
		return true
	_set_tactic(Tactic.COVER_MOVE)
	_cover_pos = p
	_set_move_target(p)
	_ambush_pending = true
	return true


## Место для засады: оттуда присевшему видно последнюю точку (укрытие «от неё» её бы и не видело),
## лучше у стены сбоку (угол, из-за которого выглядывают), недалеко от себя; не в упор к точке и не
## там, куда уже идёт другой. Vector3.INF — нет такого.
func _ambush_point() -> Vector3:
	var space := get_world_3d().direct_space_state
	var target := last_known + Vector3.UP * 1.2
	var to := last_known - global_position
	to.y = 0.0
	var side := Vector3(to.z, 0.0, -to.x).normalized()
	var cands: Array[Vector3] = [global_position]
	for i in range(16):
		var a := TAU * float(i) / 16.0
		cands.append(_snap(global_position + Vector3(cos(a), 0.0, sin(a)) * _rng.randf_range(1.5, Balance.AI_COVER_RADIUS)))
	var best := Vector3.INF
	var best_s := INF
	for c in cands:
		if c.distance_to(last_known) < float(Balance.AI_AMBUSH.min_dist) or (c != global_position and _claimed_near(c, 3.0)):
			continue
		var eye := c + Vector3.UP * CROUCH_EYE
		var q := PhysicsRayQueryParameters3D.create(eye, target, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [get_rid()])
		if not space.intersect_ray(q).is_empty():
			continue
		var wall := false
		for sgn in [1.0, -1.0]:
			var qs := PhysicsRayQueryParameters3D.create(eye, eye + side * sgn * 1.5, Hitscan.LAYER_WORLD)
			if not space.intersect_ray(qs).is_empty():
				wall = true
				break
		var s := c.distance_to(global_position) + (0.0 if wall else 6.0)
		if s < best_s:
			best_s = s
			best = c
	return best


## Разброс в момент, когда цель только что попала в поле зрения: обычно AI_AIM_COLD (первые выстрелы
## мимо); из засады, если цель вышла у той точки, которую держал под прицелом, — почти севший.
func _fresh_aim(at: Vector3) -> float:
	if state == State.COMBAT and tactic == Tactic.AMBUSH and at.distance_to(_ambush_at) < float(Balance.AI_AMBUSH.near_m):
		return float(Balance.AI_AMBUSH.aim)
	return Balance.AI_AIM_COLD


func _combat(delta: float) -> void:
	_tactic_t += delta
	if squad and _rank() == 0:
		squad.tick_calm()
	_try_grenade(delta)
	var dist := global_position.distance_to(last_known)
	var rng_m := float(_spec.range)
	var want_cover := _hurt_t > 0.0 or _suppress_t > 0.0 or (_mag == 0 and _reload_t > 0.0)
	match tactic:
		Tactic.ENGAGE:
			_set_crouch(false)
			_face(last_known)
			if _seen_now and dist <= rng_m:
				_set_move_target(global_position)
				_try_fire()
				if want_cover and _tactic_t > 0.4 and _try_cover(Balance.AI_COVER_RADIUS, false):
					return
			elif _seen_now and not _holds():
				# далеко — подходим на дальность своего оружия (дробовик — вплотную)
				_set_move_target(last_known, true)
			elif _unseen_t < 1.5 and _mag > 0:
				# только что ушёл из виду — подавляющий огонь туда, где был
				_try_fire(true)
			elif not _try_ambush():
				_set_tactic(Tactic.FLANK if _rank() == 1 and _mates_near(30.0) > 0 else _closing_tactic())
		Tactic.COVER_MOVE:
			_set_crouch(false)
			if _agent.is_navigation_finished() or global_position.distance_to(_cover_pos) < 0.9:
				if _ambush_pending:
					_set_tactic(Tactic.AMBUSH)
				else:
					_set_tactic(Tactic.COVER_HIDE)
					_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_HIDE[0]), float(Balance.AI_COVER_HIDE[1]))
			elif _seen_now and dist <= rng_m and _tactic_t > 0.6:
				_try_fire()
		Tactic.COVER_HIDE:
			_set_crouch(true)
			_face(last_known)
			if _reload_t <= 0.0 and _mag == 0:
				_start_reload()
			if _tactic_t >= 0.0 and _reload_t <= 0.0:
				_peeks += 1
				_set_tactic(Tactic.COVER_PEEK)
				_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_PEEK[0]), float(Balance.AI_COVER_PEEK[1]))
		Tactic.COVER_PEEK:
			# выглянул (встал): стреляет, если видит; потом снова вниз
			_set_crouch(false)
			_face(last_known)
			if _seen_now and dist <= rng_m:
				_try_fire()
			if _tactic_t >= 0.0:
				if not _cover_still_good() or _peeks >= 4 or (not _seen_now and _unseen_t > 3.0):
					_peeks = 0
					if _seen_now:
						_set_tactic(Tactic.ENGAGE)
					elif not _try_ambush():
						_set_tactic(_closing_tactic())
				else:
					_set_tactic(Tactic.COVER_HIDE)
					_tactic_t = -_rng.randf_range(float(Balance.AI_COVER_HIDE[0]), float(Balance.AI_COVER_HIDE[1]))
		Tactic.ADVANCE:
			# перебежка не нашлась (иначе была бы COVER_MOVE) — идём как PUSH
			_set_tactic(Tactic.PUSH)
		Tactic.OVERWATCH:
			# прикрытие: дошёл до позиции — держит место: видит — стреляет, не видит — поливает
			# туда, где цель была, если есть линия огня
			if not _overwatch_ready:
				_set_crouch(false)
				if _agent.is_navigation_finished():
					_overwatch_ready = true
			else:
				_face(last_known)
				_set_crouch(_hurt_t > 0.0)
				if _seen_now and dist <= rng_m:
					_try_fire()
				elif _unseen_t < 10.0 and dist <= rng_m:
					_try_fire(true)
				if _mag == 0 and _reload_t <= 0.0:
					_start_reload()
		Tactic.AMBUSH:
			# засада: присел в укрытии стволом на последнюю точку, молчит и ждёт; показалась — огонь
			# с уже севшим прицелом (_fresh_aim); память не истекает, пока ждёт
			_set_crouch(true)
			_face(last_known)
			memory_timer = maxf(memory_timer, 1.0)
			if _reload_t <= 0.0 and _mag < int(_spec.mag) / 2:
				_start_reload()
			if _seen_now:
				_set_tactic(Tactic.ENGAGE)
				return
			_ambush_t -= delta
			var moved := last_known.distance_to(_ambush_at) > float(Balance.AI_AMBUSH.break_m)
			if _hurt_t > 0.0 or _suppress_t > 0.0:
				# засаду раскрыли (попали, пули рядом) — за укрытие, нет его — вперёд
				if not _try_cover(Balance.AI_COVER_RADIUS, false):
					_set_tactic(_closing_tactic())
			elif _ambush_t <= 0.0 or moved:
				_set_tactic(_closing_tactic())
		Tactic.FLANK, Tactic.PUSH:
			_set_crouch(false)
			if _seen_now:
				_set_tactic(Tactic.ENGAGE)
			elif _agent.is_navigation_finished():
				if tactic == Tactic.FLANK:
					_flanked = true
					_set_tactic(Tactic.PUSH)
				else:
					# дошли, а там пусто — осматриваемся, дальше поиск по памяти
					_facing += delta * 1.5
			elif _mag < int(_spec.mag) / 3 and _reload_t <= 0.0:
				_start_reload()


## Цель не видно: далеко — перебежками по укрытиям, близко — прямо (каждый в свою точку).
func _closing_tactic() -> Tactic:
	if _holds():
		return Tactic.ENGAGE
	match _role():
		Squad.Role.COVER:
			return Tactic.OVERWATCH
		Squad.Role.FLANK:
			# отряд обхода: сначала широкий обход, потом — как все
			if not _flanked:
				return Tactic.FLANK
	return Tactic.ADVANCE if global_position.distance_to(last_known) > Balance.AI_ADVANCE_MIN_DIST else Tactic.PUSH


## Позиция прикрытия: в AI_OVERWATCH_DIST от цели, с линией взгляда на неё, недалеко от себя
## (путь без большого обхода). Vector3.INF — нет такой.
func _overwatch_point() -> Vector3:
	var space := get_world_3d().direct_space_state
	var map := get_world_3d().navigation_map
	var target := last_known + Vector3.UP * 1.2
	var to_me := global_position - last_known
	to_me.y = 0.0
	var base := atan2(to_me.z, to_me.x)
	var best := Vector3.INF
	var best_s := INF
	for i in range(24):
		var a := base + _rng.randf_range(-1.2, 1.2)
		var r := _rng.randf_range(float(Balance.AI_OVERWATCH_DIST[0]), float(Balance.AI_OVERWATCH_DIST[1]))
		var cand := _snap(last_known + Vector3(cos(a), 0.0, sin(a)) * r)
		if cand.distance_to(last_known) < float(Balance.AI_OVERWATCH_DIST[0]) * 0.8 or _claimed_near(cand, 3.0):
			continue
		var q := PhysicsRayQueryParameters3D.create(cand + Vector3.UP * EYE_HEIGHT, target, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
		if not space.intersect_ray(q).is_empty():
			continue
		var travel := cand.distance_to(global_position)
		if travel >= best_s:
			continue
		var path := _profile_path(map, cand)
		var plen := 0.0
		for k in range(1, path.size()):
			plen += path[k - 1].distance_to(path[k])
		if path.size() < 2 or plen > travel * 1.6 + 10.0:
			continue
		best = cand
		best_s = travel
	return best


## Граната: штурм (и изредка любой), цель не видна недолго, но память свежая; дальность броска;
## своих у точки нет. Бросок видят все peer, урон считает хост.
func _try_grenade(delta: float) -> void:
	_grenade_t -= delta
	if _grenades <= 0 or _grenade_t > 0.0 or _health.downed or _seen_now:
		return
	var g: Dictionary = Balance.AI_GRENADE
	if _unseen_t < float(g.min_unseen) or _unseen_t > 8.0:
		return
	if _role() != Squad.Role.ASSAULT and _rng.randf() > 0.15:
		_grenade_t = 4.0
		return
	var d := global_position.distance_to(last_known)
	if d < float(g.range[0]) or d > float(g.range[1]):
		return
	for n in get_tree().get_nodes_in_group("marauders"):
		if n != self and (n as Node3D).global_position.distance_to(last_known) < float(g.safe_m):
			_grenade_t = 3.0
			return
	_grenades -= 1
	_grenade_t = float(g.cooldown)
	_animation_event("grenade_throw")
	var from := global_position + Vector3.UP * 1.6
	var t := clampf(d / 13.0, 0.5, 1.3)
	var v := (last_known - from) / t + Vector3.UP * 0.5 * 9.8 * t
	say("Граната!")
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_grenade", [from, v])
	else:
		_rpc_grenade(from, v)


@rpc("authority", "call_local", "reliable")
func _rpc_grenade(from: Vector3, v: Vector3) -> void:
	# у всех — видно и слышно; урон — только у хоста (он и бросал)
	var g := Grenade.throw(get_tree().current_scene, from, v, get_rid(), multiplayer.is_server() or not Net.is_networked(), 0)
	g.src = {"kind": "grenade", "by": "ai", "faction": faction, "arch": archetype, "name": String(name)}


## Перебежка: точка на AI_ADVANCE_STEP ближе к цели, лучше — закрытая от неё стеной; дошёл —
## присел, выглянул, дальше. false — некуда (тогда PUSH).
func _try_advance() -> bool:
	var to := last_known - global_position
	to.y = 0.0
	var dist := to.length()
	if dist < Balance.AI_ADVANCE_MIN_DIST:
		return false
	var dir := to / dist
	var threat := last_known + Vector3.UP * 1.3
	var space := get_world_3d().direct_space_state
	var own_y := _snap(global_position).y
	var map := get_world_3d().navigation_map
	var best := Vector3.INF
	var best_s := INF
	for i in range(18):
		var ang := _rng.randf_range(-0.9, 0.9)
		var step := _rng.randf_range(float(Balance.AI_ADVANCE_STEP[0]), float(Balance.AI_ADVANCE_STEP[1]))
		var cand := _snap(global_position + dir.rotated(Vector3.UP, ang) * step)
		if absf(cand.y - own_y) > 0.3 or cand.distance_to(global_position) < 3.0:
			continue
		var nd := cand.distance_to(last_known)
		if nd > dist - 2.5 or _claimed_near(cand, Balance.AI_SPREAD_CLAIM_M):
			continue
		var q := PhysicsRayQueryParameters3D.create(threat, cand + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
		var hidden := not space.intersect_ray(q).is_empty()
		var score := nd + (0.0 if hidden else 7.0) + absf(ang) * 3.0
		if score >= best_s:
			continue
		# и дойти туда можно без обхода через полкарты
		var path := _profile_path(map, cand)
		var plen := 0.0
		for k in range(1, path.size()):
			plen += path[k - 1].distance_to(path[k])
		if path.size() < 2 or plen > cand.distance_to(global_position) * 1.6 + 3.0:
			continue
		best = cand
		best_s = score
	if best == Vector3.INF:
		return false
	_cover_pos = best
	_set_move_target(best)
	# дошёл — одно «присел-выглянул» и дальше
	_peeks = 3
	memory_timer = maxf(memory_timer, _mem() * 0.6)
	tactic = Tactic.COVER_MOVE
	_tactic_t = 0.0
	if _rng.randf() < 0.35:
		say("Двигаюсь!")
	return true


func _start_search(points: int = Balance.AI_SEARCH_POINTS) -> void:
	_flanked = false
	state = State.SEARCH
	_set_crouch(false)
	_search_left = points
	_search_total = points
	# прочёсывание дугой — от той стороны, откуда пришли, каждый в свою сторону
	_search_ang = atan2(global_position.z - last_known.z, global_position.x - last_known.x) + (0.8 if hash(name) % 2 == 0 else -0.8)
	_set_move_target(global_position if _holds() else _spread_point(last_known))
	linger_timer = 1.5
	say("Ушёл…" if points == Balance.AI_SEARCH_POINTS else "Проверю тут…")


## Поиск: к последней точке, потом прочёсывание вокруг — от ближних мест к дальним, дугой,
## в стороне от тех, кого уже смотрят другие; на каждой — постоять, осмотреться.
func _search(delta: float) -> void:
	if _reload_t <= 0.0 and _mag < int(_spec.mag):
		_start_reload()
	if not _agent.is_navigation_finished():
		return
	linger_timer -= delta
	_facing += delta * 1.4
	if linger_timer > 0.0:
		return
	if _search_left <= 0:
		state = State.PATROL
		pause_timer = 1.0
		return
	_search_left -= 1
	if _holds():
		# ищет глазами с места
		linger_timer = _rng.randf_range(2.0, 3.5)
		return
	var done := float(_search_total - _search_left) / float(maxi(_search_total, 1))
	var r := lerpf(4.0, Balance.AI_SEARCH_RADIUS, done)
	var sweep := 1.1 if hash(name) % 2 == 0 else -1.1
	var target := last_known
	for attempt in range(8):
		var a := _search_ang + _rng.randf_range(-0.35, 0.35)
		_search_ang += sweep
		var p := _snap(last_known + Vector3(cos(a), 0.0, sin(a)) * r * _rng.randf_range(0.8, 1.1))
		if p.distance_to(global_position) > 2.0 and not _claimed_near(p, Balance.AI_SEARCH_CLAIM_M):
			target = p
			break
	_set_move_target(target)
	linger_timer = _rng.randf_range(1.2, 2.4)


func _start_retreat() -> void:
	state = State.RETREAT
	say("Отхожу!")
	if not _try_cover(Balance.AI_COVER_RADIUS * 1.8, true):
		# укрытия нет — просто прочь от угрозы
		var away := global_position - last_known
		away.y = 0.0
		_set_move_target(global_position + away.normalized() * 12.0, true)
	linger_timer = _rng.randf_range(float(Balance.AI_RETREAT_HOLD[0]), float(Balance.AI_RETREAT_HOLD[1]))


func _retreat(delta: float) -> void:
	if String(_order.get("kind", "")) == "fallback":
		# отряд разрывает контакт: бежит, за укрытием не отсиживается; дошёл или вышло время — по плану
		_set_crouch(false)
		# «дошёл» — не раньше, чем путь проложен (в первый кадр агент ещё считает прежний путь законченным)
		var now_ms: int = Time.get_ticks_msec()
		if now_ms >= int(_order.until) or (now_ms - int(_order.since) > 800 and _agent.is_navigation_finished()):
			stand_down()
		return
	if not _agent.is_navigation_finished():
		_set_crouch(false)
		return
	_set_crouch(true)
	_face(last_known)
	if _reload_t <= 0.0 and _mag < int(_spec.mag):
		_start_reload()
	# отсиделся — или стреляет по тому, кто пришёл, или снова ищет
	if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
		_try_fire()
	linger_timer -= delta
	if linger_timer <= 0.0:
		_start_search()


# ---------------------------------------------------------------- тяжело ранен, спасение

## Лёг раненым (хост): пистолет вместо основного, зовёт; поднялся — обратно в бой.
func _on_downed_changed(on: bool) -> void:
	if on:
		Audio.play("downed", global_position + Vector3.UP)
		_release_rescue()
		state = State.DOWNED
		crouched = false
		_apply_shape()
		# лёжа — пистолет (если есть)
		_main_slot = _active
		if equipment.has("secondary"):
			_use("secondary")
		_reload_t = 0.0
		_burst_left = 0
		_set_move_target(global_position)
		say("Меня зацепило!")
		NoiseBus.emit(global_position, Balance.AI_RESCUE_RADIUS, "death")
		_help_t = 0.0
		_call_for_help()
	else:
		Audio.play("revive", global_position + Vector3.UP)
		rescuer = null
		dragged_by = null
		if _main_slot != "" and _main_slot != _active:
			_use(_main_slot)
		_main_slot = ""
		_apply_shape()
		say("Живой!")
		memory_timer = maxf(memory_timer, _mem())
		_enter_combat(Tactic.ENGAGE)
		_try_cover(Balance.AI_COVER_RADIUS, false)


## Раненый зовёт: ближайший живой товарищ, который слышит (свой отряд — в первую очередь), идёт спасать.
func _call_for_help() -> void:
	var best: Marauder = null
	var best_s := INF
	for n in get_tree().get_nodes_in_group("marauders"):
		var m := n as Marauder
		if m == self or m.state in [State.DEAD, State.DOWNED, State.RESCUE, State.RETREAT]:
			continue
		var d := m.global_position.distance_to(global_position)
		if d > Balance.AI_RESCUE_RADIUS:
			continue
		if m.faction != faction:
			continue
		var s := d * (1.0 if m.squad == squad else 1.8)
		if s < best_s:
			best = m
			best_s = s
	if best:
		best.start_rescue(self)


func start_rescue(who: Marauder) -> void:
	who.rescuer = self
	_rescue_target = who
	_rescue_phase = 0
	_rescue_t = 0.0
	state = State.RESCUE
	crouched = false
	_apply_shape()
	_set_move_target(who.global_position, true)
	say("Держись, иду!")


## Бросить спасение (сам ранен / умер / тот умер): раненого — отпустить.
func _release_rescue() -> void:
	var t := _rescue_target
	_rescue_target = null
	if t and is_instance_valid(t):
		if t.rescuer == self:
			t.rescuer = null
		if t.dragged_by == self:
			t.dragged_by = null


## Лежит: отстреливается из пистолета, ждёт помощи; никто не идёт — зовёт снова.
func _downed(delta: float) -> void:
	_face(last_known)
	if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
		_try_fire()
	if rescuer == null or not is_instance_valid(rescuer) or rescuer.state != State.RESCUE:
		rescuer = null
		_help_t += delta
		if _help_t >= 4.0:
			_help_t = 0.0
			_call_for_help()


## Раненого тащат — тело на «верёвке» за тем, кто тащит; иначе лежит на месте.
func _move_downed(delta: float) -> void:
	velocity = Vector3.ZERO
	if dragged_by and is_instance_valid(dragged_by) and dragged_by.state == State.RESCUE:
		var off := global_position - dragged_by.global_position
		off.y = 0.0
		if off.length() < 0.05:
			off = -Vector3(sin(dragged_by._facing), 0.0, cos(dragged_by._facing))
		var goal := dragged_by.global_position + off.normalized() * Balance.DRAG_DIST
		var pull := (goal - global_position) / maxf(delta, 0.001)
		velocity.x = clampf(pull.x, -6.0, 6.0)
		velocity.z = clampf(pull.z, -6.0, 6.0)
	if not is_on_floor():
		velocity.y -= 9.8
	($CartContact as CartContact).move_character(delta)
	_body.rotation.y = _facing
	# лежит: модель Persona кладёт клип падения (наклон корпуса сверху ставил её ногами вверх),
	# запасной манекен — наклоном лицом вниз (Body:rotation синхронизируется)
	var anim := get_node_or_null("CharacterAnimator") as CharacterAnimator
	_body.rotation.x = 0.0 if anim and anim.has_model() else 1.35


## Спасатель: добежать, лежит на виду — утащить за укрытие, поднять.
func _rescue(delta: float) -> void:
	var t := _rescue_target
	if t == null or not is_instance_valid(t) or t.state != State.DOWNED:
		_end_rescue()
		return
	var d := global_position.distance_to(t.global_position)
	match _rescue_phase:
		0:
			_set_crouch(false)
			if _repath_t <= 0.0:
				_repath_t = _next_work_delay(_repath_t, float(Balance.AI_WORK.follow_repath_sec))
				_set_move_target(t.global_position, true)
			# по пути отвечает огнём, если видит
			if _seen_now and global_position.distance_to(last_known) <= float(_spec.range):
				_try_fire()
			if d <= 1.4:
				last_known = t.last_known
				var threat := t.last_known + Vector3.UP * 1.3
				var q := PhysicsRayQueryParameters3D.create(threat, t.global_position + Vector3.UP * 0.5, Hitscan.LAYER_WORLD)
				var exposed := get_world_3d().direct_space_state.intersect_ray(q).is_empty()
				var cover := _cover_point(Balance.AI_DRAG_COVER_M, false) if exposed else Vector3.INF
				if cover != Vector3.INF:
					_rescue_phase = 1
					t.dragged_by = self
					_set_move_target(cover)
					say("Тащу! Прикрой!")
				else:
					_rescue_phase = 2
					_rescue_t = 0.0
		1:
			if _agent.is_navigation_finished() or d > 3.0:
				t.dragged_by = null
				_rescue_phase = 2
				_rescue_t = 0.0
		2:
			_set_move_target(global_position)
			_set_crouch(true)
			_face(t.global_position)
			_rescue_t += delta
			if _rescue_t >= Balance.AI_REVIVE_SEC:
				t._health.revive(Balance.REVIVE_HP)
				_end_rescue()


func _end_rescue() -> void:
	_release_rescue()
	if state != State.RESCUE:
		return
	_set_crouch(false)
	if memory_timer > 0.0:
		_enter_combat(_closing_tactic())
	else:
		state = State.PATROL
		pause_timer = 1.0


# ---------------------------------------------------------------- укрытие

## Ищет рядом место, которое стена закрывает от угрозы (last_known), и идёт туда.
## far — отход: чем дальше от угрозы, тем лучше.
func _try_cover(radius: float, far: bool) -> bool:
	var iteration: int = NavigationServer3D.map_get_iteration_id(get_world_3d().navigation_map)
	var now: int = Engine.get_physics_frames()
	if not far and not _cover_miss.is_empty() and now < int(_cover_miss.until) \
			and _cover_miss.origin == global_position and _cover_miss.threat == last_known \
			and float(_cover_miss.radius) == radius and int(_cover_miss.iteration) == iteration:
		return false
	var best := _cover_point(radius, far)
	if best == Vector3.INF:
		# У отхода другой порядок кандидатов: его неудача не заменяет обычный поиск.
		if far:
			_cover_miss.clear()
		else:
			_cover_miss = {"origin": global_position, "threat": last_known, "radius": radius, "iteration": iteration,
				"until": now + maxi(1, ceili(float(Balance.AI_WORK.cover_retry_sec) * Engine.physics_ticks_per_second))}
		return false
	_cover_miss.clear()
	_cover_pos = best
	_set_move_target(best)
	if state == State.COMBAT:
		_set_tactic(Tactic.COVER_MOVE)
	return true


## Точка укрытия от last_known в радиусе (Vector3.INF — нет): стена закрывает присевшего,
## дойти можно без большого обхода.
func _cover_point(radius: float, far: bool) -> Vector3:
	var threat := last_known + Vector3.UP * 1.3
	var space := get_world_3d().direct_space_state
	var cands: Array = []
	# высота навмеша под собой — он лежит чуть выше пола
	var own_y := _snap(global_position).y
	for ring in [0.35, 0.65, 1.0]:
		for i in range(12):
			var a := TAU * float(i) / 12.0 + _rng.randf() * 0.3
			var cand := _snap(global_position + Vector3(cos(a), 0.0, sin(a)) * radius * float(ring))
			# на уровне своего пола (не на лавке и не на ящике)
			if cand.distance_to(global_position) < 1.0 or absf(cand.y - own_y) > 0.3:
				continue
			# присевший за этой точкой не виден с угрозы
			var q := PhysicsRayQueryParameters3D.create(threat, cand + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
			if space.intersect_ray(q).is_empty():
				continue
			var travel := cand.distance_to(global_position)
			var to_threat := cand.distance_to(last_known)
			var score := travel - (to_threat * 0.8 if far else 0.0)
			# не лезть ближе к угрозе (кроме дробовика — ему вблизи и надо)
			if not far and String(_spec.get("class", "")) != "SHOTGUN" and to_threat < global_position.distance_to(last_known) - 3.0:
				score += 6.0
			cands.append([score, cand, travel])
	cands.sort_custom(func(x: Array, y: Array) -> bool: return float(x[0]) < float(y[0]))
	# идти до укрытия — не в обход через полкарты: путь не длиннее полутора прямых + 4 м
	var map := get_world_3d().navigation_map
	var best := Vector3.INF
	for c in cands.slice(0, 6):
		var path := _profile_path(map, c[1])
		var plen := 0.0
		for k in range(1, path.size()):
			plen += path[k - 1].distance_to(path[k])
		if path.size() >= 2 and plen <= float(c[2]) * 1.5 + 4.0:
			best = c[1]
			break
	return best


## Укрытие всё ещё закрывает от того места, где цель сейчас (по памяти)?
func _cover_still_good() -> bool:
	var q := PhysicsRayQueryParameters3D.create(last_known + Vector3.UP * 1.3, global_position + Vector3.UP * CROUCH_EYE, Hitscan.LAYER_WORLD)
	return not get_world_3d().direct_space_state.intersect_ray(q).is_empty()


func _set_crouch(on: bool) -> void:
	if crouched == on:
		return
	crouched = on
	_apply_shape()


## Фигура и коллизия по позе: стоит, присел, лежит раненым.
func _apply_shape() -> void:
	_body.scale = _base_scale * Vector3(1.0, 0.68 if crouched else 1.0, 1.0)
	_capsule.height = 0.8 if _health.downed else (1.25 if crouched else 1.8)
	($Capsule as CollisionShape3D).position.y = _capsule.height * 0.5


func _face(p: Vector3) -> void:
	_facing = atan2(p.x - global_position.x, p.z - global_position.z)
	# взгляд — на грудь стоящего в этой точке (p — где цель стоит, у ног), от своей груди
	var flat := Vector2(p.x - global_position.x, p.z - global_position.z).length()
	var eye := 0.9 if crouched else 1.35
	look_pitch = atan2(p.y + 1.2 - (global_position.y + eye), maxf(flat, 0.5)) if flat > 0.3 else look_pitch


# ---------------------------------------------------------------- стрельба

func _tick_weapon(delta: float) -> void:
	_shot_t -= delta
	if _reload_t > 0.0:
		_reload_t -= delta
		if _reload_t <= 0.0:
			_finish_reload()


## Перезарядка — своими запасными магазинами (россыпью — у ружья и болтовки). Нечем — второе
## оружие; и там пусто — «Пустой!» (дальше только отходит).
func _start_reload() -> void:
	if _reload_t > 0.0 or _mag >= int(_spec.mag) or _dry:
		return
	if not _can_reload(_active):
		var other := "secondary" if _active == "primary" else "primary"
		if equipment.has(other) and (Gear.total_rounds(equipment[other]) > 0 or _can_reload(other)):
			_use(other)
			say("Перехожу на запасное!" if other == "secondary" else "Основное!")
			return
		if _mag <= 0:
			_dry = true
			say("Пустой!")
			_play_weapon_sound("dry_fire", -8.0)
			if state == State.COMBAT:
				_start_retreat()
		return
	_reload_t = float(_spec.reload)
	_burst_left = 0
	if String(_spec.get("class", "")) != "PISTOL":
		_animation_event("rifle_reload")
	Audio.play(String(_spec.get("reload_sound", "reload_rifle")), global_position)
	if _weapon_sound("breech_open") != "":
		_play_weapon_sound("breech_open", -4.0)
	elif _weapon_sound("mag_out") != "":
		_play_weapon_sound("mag_out", -4.0)
	else:
		_play_weapon_sound("round_insert", -4.0)
	if state == State.COMBAT:
		say("Перезаряжаюсь!")


## Есть чем зарядить оружие slot.
func _can_reload(slot: String) -> bool:
	if not equipment.has(slot):
		return false
	if Balance.AI_INFINITE_AMMO:
		return true
	var e: Dictionary = equipment[slot]
	var mag: Dictionary = e.mag
	for it in spare:
		if String(mag.get("id", "")) == "":
			if WeaponDb.ammo_fits(String(e.id), String(it.id)) and not it.has("rounds") and int(it.n) > 0:
				return true
		elif WeaponDb.mag_fits(String(e.id), String(it.id)) and int(it.get("rounds", 0)) > 0:
			return true
	return false


func _finish_reload() -> void:
	var e: Dictionary = equipment.get(_active, {})
	if e.is_empty():
		return
	var mag: Dictionary = e.mag
	var magazine_rounds: int = maxi(0, _mag - int(e.get("chamber", 0)))
	mag["rounds"] = magazine_rounds
	if Balance.AI_INFINITE_AMMO:
		# патроны не кончаются: тот же магазин (та же пачка) — снова полный
		magazine_rounds = WeaponDb.capacity(e)
	elif String(mag.get("id", "")) == "":
		# россыпью в ружьё / болтовку
		var cap := WeaponDb.capacity(e)
		for it in spare:
			if magazine_rounds >= cap:
				break
			if WeaponDb.ammo_fits(String(e.id), String(it.id)) and not it.has("rounds") and int(it.n) > 0 and (magazine_rounds == 0 or String(it.id) == String(mag.ammo)):
				var k := mini(cap - magazine_rounds, int(it.n))
				it.n = int(it.n) - k
				magazine_rounds += k
				mag["ammo"] = String(it.id)
		spare = spare.filter(func(it: Dictionary) -> bool: return it.has("rounds") or int(it.n) > 0)
	else:
		# сменить магазин: самый полный подходящий; пустой старый — в подсумок (выпадет с тела)
		var best := -1
		for i in range(spare.size()):
			var it: Dictionary = spare[i]
			if WeaponDb.mag_fits(String(e.id), String(it.id)) and int(it.get("rounds", 0)) > 0 and (best < 0 or int(it.rounds) > int(spare[best].rounds)):
				best = i
		if best < 0:
			return
		var fresh: Dictionary = spare[best]
		spare.remove_at(best)
		spare.append(Gear.mag_item(mag))
		mag["id"] = String(fresh.id)
		mag["ammo"] = String(fresh.get("ammo", ""))
		# патроны вперемешку (магазин игрока): слои переезжают вместе с магазином
		if fresh.get("mix") is Array:
			mag["mix"] = (fresh.mix as Array).duplicate(true)
		else:
			mag.erase("mix")
		magazine_rounds = int(fresh.rounds)
	mag["rounds"] = magazine_rounds
	Gear.chamber_round(e)
	_mag = Gear.total_rounds(e)
	# патрон мог смениться — характеристики тоже
	_spec = _ai_spec(e)
	if _weapon_sound("breech_close") != "":
		_play_weapon_sound("breech_close", -4.0)
	else:
		_play_weapon_sound("mag_in", -4.0)
		_play_weapon_sound("charge", -5.0)


## Выстрел, если готов: очередь, пауза между очередями, магазин. suppress — по памяти, реже и хуже.
func _try_fire(suppress: bool = false) -> void:
	if equipment.has(_active) and WeaponCondition.broken(equipment[_active]):
		_drop_fire_token()
		return
	if _reload_t > 0.0:
		_drop_fire_token()
		return
	if _mag <= 0:
		_start_reload()
		return
	if _target_player and is_instance_valid(_target_player) and _target_player.is_downed() and not _may_finish(_target_player):
		# лежащего не добивает, пока стреляет кто-то другой
		return
	if _shot_t > 0.0:
		return
	if not _line_of_fire():
		# перед каждым выстрелом заново проверяем стену и дверь
		return
	# по игроку — по очереди: без права на прицельный огонь — на подавление (мимо, но рядом)
	_untoken = _target_player != null and _foe == null and not _fire_token()
	_shoot(suppress or _untoken)
	if String(_spec.get("class", "")) != "PISTOL":
		_animation_event("rifle_fire")
	if equipment.has(_active):
		var entry: Dictionary = equipment[_active]
		if int(WeaponDb.weapon(String(entry.id)).get("chamber_capacity", 0)) > 0:
			entry["chamber"] = 0
			entry["chamber_ammo"] = ""
			Gear.chamber_round(entry)
			_mag = Gear.total_rounds(entry)
			# Следующий патрон после смены магазина может иметь другой тип.
			_spec = _ai_spec(entry)
		else:
			_mag -= 1
			(entry.mag as Dictionary)["rounds"] = _mag
	else:
		_mag -= 1
	if _burst_left <= 0:
		_burst_left = int(_spec.burst)
	_burst_left -= 1
	if _burst_left > 0:
		_shot_t = float(_spec.interval)
	else:
		_shot_t = float(_spec.interval) + float(_spec.burst_pause) + (0.6 if suppress else 0.0) \
			+ (float(Balance.AI_FIRE_TOKENS.untoken_pause) if _untoken else 0.0)


## Сколько секунд смотреть, чтобы заметить игрока p на расстоянии dist (Balance.AI_NOTICE).
func _notice_sec(p: Player, dist: float) -> float:
	var n: Dictionary = Balance.AI_NOTICE
	var sec := lerpf(float(n.near_sec), float(n.far_sec), smoothstep(float(n.near_m), float(n.far_m), dist))
	sec *= float((n.stance as Dictionary).get(p.stance_key(), 1.0))
	if Vector2(p.velocity.x, p.velocity.z).length() > Balance.PLAYER_WALK_SPEED * 1.6:
		sec *= float(n.sprint)
	if Time.get_ticks_msec() - p.last_shot_ms < int(float(n.shot_sec) * 1000.0):
		sec *= float(n.shot)
	return maxf(sec * Balance.lab_number("perception", "notice"), 0.05)


## Право на прицельный огонь по своей цели (Balance.AI_FIRE_TOKENS): держит hold_sec, отдаёт и ждёт
## cooldown_sec; занято — false. Общие на всех мародёров (по цели).
static var _tokens: Dictionary = {}
var _token_until: int = 0
var _token_wait: int = 0
var _untoken: bool = false


func _fire_token() -> bool:
	if _target_player == null or not is_instance_valid(_target_player):
		return true
	var t: Dictionary = Balance.AI_FIRE_TOKENS
	var now := Time.get_ticks_msec()
	var key := _target_player.get_instance_id()
	var holders: Array = _tokens.get(key, [])
	# живые держатели, у которых срок не вышел
	var keep: Array = []
	for h in holders:
		# освобождённый мародёр (тесты, конец рейда) — не приводить, просто выбросить
		if not is_instance_valid(h):
			continue
		var m := h as Marauder
		if m != null and m.state != State.DEAD and m._token_until > now and m._target_player == _target_player:
			keep.append(m)
	_tokens[key] = keep
	if self in keep:
		return true
	if now < _token_wait or keep.size() >= int(t.tokens):
		return false
	keep.append(self)
	_token_until = now + int(float(t.hold_sec) * 1000.0)
	_token_wait = _token_until + int(float(t.cooldown_sec) * 1000.0)
	return true


func _drop_fire_token() -> void:
	if _token_until > Time.get_ticks_msec():
		_token_until = 0


## Ствол → точка цели (по памяти) не упирается в стену / дверь раньше, чем за метр до неё.
func _line_of_fire() -> bool:
	var from := _gun_pos()
	var target := last_known + Vector3.UP * 1.1
	var q := PhysicsRayQueryParameters3D.create(from, target, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR, [get_rid()])
	var hit := get_world_3d().direct_space_state.intersect_ray(q)
	return hit.is_empty() or from.distance_to(hit.position) > from.distance_to(target) - 1.0


## Откуда стреляет: стоя, присев, лёжа.
func _gun_pos() -> Vector3:
	return global_position + Vector3.UP * (0.35 if _health.downed else (1.0 if crouched else 1.4))


func _shoot(suppress: bool) -> void:
	if equipment.has(_active):
		var entry: Dictionary = equipment[_active]
		WeaponCondition.wear_shots(equipment[_active], 1)
		_spec = _ai_spec(equipment[_active])
		# вид модели от прочности не зависит — меняются только марка и фонарь обвесов
		if _main_gun:
			WeaponMods.update_condition(_main_gun, entry.get("mods", {}))
	var from := _gun_pos()
	var h := 1.1
	var at_ai := _foe != null and is_instance_valid(_foe) and _target_player == null
	if not at_ai and _target_player != null and is_instance_valid(_target_player):
		player_contact_ms = Time.get_ticks_msec()
	if _target_player and is_instance_valid(_target_player):
		h = float(Perception.TARGET_HEIGHT[Perception.stance_key(_target_player)])
	elif at_ai:
		h = 0.35 if _foe.state == State.DOWNED else 1.2
	var target := last_known + Vector3.UP * h
	var spread := float(_spec.spread) * _aim
	if _target_player and is_instance_valid(_target_player) and _target_player.velocity.length() > 2.0:
		spread *= Balance.AI_TARGET_MOVING
	if Vector2(velocity.x, velocity.z).length() > 0.5:
		spread *= Balance.AI_SELF_MOVING
	if suppress:
		spread *= 2.0
	if _stagger_t > 0.0:
		spread *= Balance.AI_HIT_STAGGER_SPREAD
	if _health.downed:
		spread *= Balance.DOWN_SPREAD
	if _untoken:
		spread *= float(Balance.AI_FIRE_TOKENS.untoken_spread)
	var exclude: Array[RID] = [get_rid()]
	var dir := (target - from).normalized()
	# ствол модели — туда же, куда пуля (лежащая цель ниже груди)
	look_pitch = asin(clampf(dir.y, -1.0, 1.0))
	for i in range(int(_spec.pellets)):
		# по ИИ другой фракции — пули бьют и ИИ; урон от ИИ никому из игроков не засчитывается
		var mask := Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR | Hitscan.LAYER_PLAYER | (Hitscan.LAYER_MARAUDER if at_ai else 0)
		var hit := Hitscan.fire(get_world_3d(), from, dir, spread, float(_spec.range) * 1.5,
			mask, float(_spec.damage), exclude, _rng, 0, {"pen": float(_spec.pen), "armor_dmg": float(_spec.armor_dmg), "src": _story_src(),
				"falloff": _spec.get("falloff", []), "point_blank": _spec.get("point_blank", []), "range": float(_spec.get("range_m", 0.0))})
		_near_miss(from, hit)
	# свои выстрелы товарищи слышат как «бой» — не как свист пуль у себя
	NoiseBus.emit(global_position, float(_spec.noise_m), "shot_ai")
	var flash := float(_spec.get("flash", 1.0))
	_shot_fx(from, String(_spec.sound), flash, _weapon_sound("mechanism"), String(_spec.cycle_sound), float(_spec.get("db", 0.0)))
	# стреляет хост — клиентам видно и слышно то же (раньше мародёр у них стрелял беззвучно)
	if Net.is_networked():
		Net.broadcast_scene(self, &"_rpc_shot_fx", [from, String(_spec.sound), flash, _weapon_sound("mechanism"), String(_spec.cycle_sound), float(_spec.get("db", 0.0))], false)


## Вспышка и звук выстрела — у хоста из _shoot, у клиентов — по сети. След пули виден только
## по эффекту попадания, который создаёт Hitscan.
func _shot_fx(from: Vector3, sound: String, flash: float, mechanism_sound: String, cycle_sound: String, extra_db: float = 0.0) -> void:
	if flash > 0.05:
		_muzzle.visible = true
		get_tree().create_timer(0.06).timeout.connect(func() -> void: _muzzle.visible = false)
	Audio.play(sound, from, extra_db)
	if mechanism_sound != "":
		Audio.play(mechanism_sound, from, extra_db - 5.0)
	if cycle_sound != "":
		get_tree().create_timer(0.35).timeout.connect(func() -> void:
			if is_inside_tree():
				Audio.play(cycle_sound, global_position))
	else:
		Audio.shell_drop(global_position, global_basis.x, 0.0, sound.get_slice("_shot", 0))


@rpc("authority", "call_remote", "unreliable_ordered")
func _rpc_shot_fx(from: Vector3, sound: String, flash: float, mechanism_sound: String, cycle_sound: String, extra_db: float = 0.0) -> void:
	_shot_fx(from, sound, flash, mechanism_sound, cycle_sound, extra_db)


## Чем стреляет — для хроники рейда игрока, в которого попали (Health.last_src).
func _story_src() -> Dictionary:
	return {"kind": "ai", "faction": faction, "arch": archetype, "weapon": String((equipment.get(_active, {}) as Dictionary).get("id", ""))}


## Пуля прошла рядом с игроком (не в него) — ему страшно (Player.near_miss, стресс).
func _near_miss(from: Vector3, hit: Dictionary) -> void:
	var end: Vector3 = hit.get("position", hit.get("end", from))
	var near := float(Balance.STRESS.near_m)
	for n in get_tree().get_nodes_in_group("players"):
		var pl := n as Player
		if pl == null or hit.get("collider") == pl:
			continue
		var chest := pl.global_position + Vector3.UP * 1.2
		var q := Geometry3D.get_closest_point_to_segment(chest, from, end)
		if q.distance_to(chest) < near:
			pl.near_miss()


# ---------------------------------------------------------------- реплики

## Реплика над головой («Контакт!», «Перезаряжаюсь!») — видна всем игрокам.
func say(text: String) -> void:
	if Net.is_networked():
		Net.broadcast_scene(self, &"_say_rpc", [text])
	else:
		_show_say(text)


@rpc("authority", "call_local", "unreliable")
func _say_rpc(text: String) -> void:
	_show_say(text)


func _show_say(text: String) -> void:
	var voice := ""
	if faction == "pmc":
		voice = "pmc_radio"
	elif faction == "resident":
		voice = "resident"
	elif "Граната" in text:
		voice = "ai_nade"
	elif "Перезаряжаюсь" in text or "Пустой" in text:
		voice = "ai_reload"
	elif "Контакт" in text or "стреляют" in text or "вон" in text.to_lower():
		voice = "ai_spot"
	elif "зацепило" in text:
		voice = "ai_hurt"
	elif "Проверю" in text or "Ушёл" in text or "Обхожу" in text or "Двигаюсь" in text:
		voice = "ai_search"
	if voice != "":
		Audio.play(voice, global_position + Vector3.UP * 1.5)
	# Надпись над головой — только вблизи и не сквозь стены: издали она висела в воздухе мелкой
	# строчкой и выдавала мародёра за стеной (голос слышно и так).
	var viewer: Camera3D = get_viewport().get_camera_3d() if is_inside_tree() else null
	if viewer == null or viewer.global_position.distance_to(global_position) > Balance.AI_SAY_TEXT_M:
		if _say_label:
			_say_label.visible = false
		return
	if _say_label == null:
		_say_label = Label3D.new()
		_say_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		_say_label.pixel_size = 0.006
		_say_label.font_size = 48
		_say_label.outline_size = 12
		_say_label.modulate = Color(1.0, 0.85, 0.6)
		_say_label.position = Vector3(0, 2.25, 0)
		add_child(_say_label)
	_say_label.text = text
	_say_label.visible = true
	var shown := text
	get_tree().create_timer(1.6).timeout.connect(func() -> void:
		if is_instance_valid(_say_label) and _say_label.text == shown:
			_say_label.visible = false)


# ---------------------------------------------------------------- движение

## Связка навигации: «перелезть» — найти путь через преграду и перелезть (шумно).
func _on_link_reached(details: Dictionary) -> void:
	var owner_node: Object = details.get("owner")
	if _vault_t >= 0.0 or not (owner_node is Node and (owner_node as Node).is_in_group(Vault.GROUP)):
		return
	var from: Vector3 = details.get("link_entry_position", global_position)
	var to: Vector3 = details.get("link_exit_position", global_position)
	# сигнал приходит и на выходе связки (уже перелез) — лезть, только если стоим у входа
	if _flat(global_position - from) > _flat(global_position - to) or Time.get_ticks_msec() < _vault_done_ms + 600:
		return
	var dir := to - from
	dir.y = 0.0
	var path := Vault.find(get_world_3d().direct_space_state, global_position, dir, [get_rid()], 1.4)
	# приземлиться надо у конца связки, а не где-то ещё
	if path.is_empty() or _flat((path.land as Vector3) - to) > 1.2:
		return
	_vault = path
	_vault_t = 0.0
	_facing = atan2(dir.x, dir.z)
	# слышно — звуком (как шаги мародёров); в NoiseBus не пишем: услышал бы сам себя и полез обратно
	Audio.play("vault", global_position + Vector3.UP * 0.8, -14.0)


static func _flat(v: Vector3) -> float:
	return Vector2(v.x, v.z).length()


func _move(delta: float) -> void:
	if state == State.DOWNED:
		_vault_t = -1.0
		_move_downed(delta)
		return
	if _vault_t >= 0.0:
		_vault_t += delta / float(Balance.VAULT.sec)
		global_position = Vault.pos_at(_vault, minf(_vault_t, 1.0))
		velocity = Vector3.ZERO
		_body.rotation.y = _facing
		if _vault_t >= 1.0:
			_vault_t = -1.0
			_vault_done_ms = Time.get_ticks_msec()
		return
	var speed := Balance.MARAUDER_WALK if state == State.PATROL else Balance.MARAUDER_RUN
	if state == State.RESCUE:
		speed = Balance.AI_DRAG_SPEED if _rescue_phase == 1 else (Balance.MARAUDER_RUN if _rescue_phase == 0 else 0.0)
	if state == State.SEARCH or state == State.INVESTIGATE:
		speed = lerpf(Balance.MARAUDER_WALK, Balance.MARAUDER_RUN, 0.55)
	if crouched:
		speed = Balance.MARAUDER_WALK * 0.7
	speed *= float(_arch.get("speed", 1.0))
	# вброд мародёр тоже медленнее
	speed *= WaterBody.depth_k(WaterBody.depth_at(global_position), Balance.WATER.ai_speed)
	if _stagger_t > 0.0:
		speed *= Balance.AI_HIT_STAGGER_SPEED
	var wish := Vector3.ZERO
	if _nav_ready and not _agent.is_navigation_finished():
		var path_started: int = Time.get_ticks_usec() if work_profile_enabled else 0
		var next := _agent.get_next_path_position()
		if work_profile_enabled:
			_record_work("agent_path", path_started)
		# точка пути подгоняется по высоте под ноги: достигнутой её делает расстояние по земле
		var fix: float = float(Balance.AI_PATH_HEIGHT_FIX)
		_agent.path_height_offset = clampf(next.y + _agent.path_height_offset - global_position.y, -fix, fix)
		var to := next - global_position
		to.y = 0.0
		if to.length() > 0.05:
			wish = to.normalized() * speed
			# в бою смотрит на цель, а не под ноги
			if state != State.COMBAT or not _seen_now:
				_facing = lerp_angle(_facing, atan2(to.x, to.z), minf(1.0, 8.0 * delta))
	# упёрся в то, чего нет в сетке путей (ствол дерева, край пропса): шаг вбок, потом — другая точка
	if _side_t > 0.0 and wish.length_squared() > 0.01:
		_side_t -= delta
		wish = Vector3(wish.z, 0.0, -wish.x) * _side_sign
	velocity.x = move_toward(velocity.x, wish.x, 14.0 * delta)
	velocity.z = move_toward(velocity.z, wish.z, 14.0 * delta)
	if not is_on_floor():
		velocity.y -= 9.8 * delta
	else:
		velocity.y = 0.0
	var from := global_position
	($CartContact as CartContact).move_character(delta)
	if wish.length_squared() > 0.01:
		_step_up(from, wish * delta)
		_tick_stuck(from, delta)
	else:
		_stuck_t = 0.0
	_body.rotation.y = _facing
	# попадание откидывает корпус назад (Body:rotation синхронизируется — видно всем)
	_body.rotation.x = -0.35 * _flinch
	# шаги (их слышно — так мародёра можно засечь раньше, чем он тебя) — Footsteps


func _tick_stuck(from: Vector3, delta: float) -> void:
	var cfg: Dictionary = Balance.AI_UNSTUCK
	var step := global_position - from
	step.y = 0.0
	if step.length() > float(cfg.min_speed) * delta:
		_stuck_t = 0.0
		if _side_t <= 0.0:
			_stuck_n = 0
		return
	_stuck_t += delta
	if _stuck_t < float(cfg.stuck_sec) or _side_t > 0.0:
		return
	_stuck_t = 0.0
	_stuck_n += 1
	_side_t = float(cfg.side_sec)
	_side_sign = 1.0 if _rng.randf() < 0.5 else -1.0
	if _stuck_n >= int(cfg.tries) and state == State.PATROL:
		_stuck_n = 0
		# патруль и гарнизон — к другой своей точке, не в случайное место карты
		if not route.is_empty():
			_set_move_target(_next_route_point(), true)
		elif not home_points.is_empty():
			_set_move_target(home_points[_rng.randi_range(0, home_points.size() - 1)], true)
		elif patrol_point_provider.is_valid():
			_set_move_target(patrol_point_provider.call(), true)


## Шаг на ступень (бордюр, порожек): упёрся — пробуем встать выше, как игрок (Balance.STEP_UP).
## Навигация через бордюр пускает (он ниже nav_climb), а тело без этого шага упиралось в него и стояло:
## на дорогах района ТЦ так застревали и мародёры, и чужие отряды.
func _step_up(from: Vector3, want: Vector3) -> void:
	if not is_on_floor() or want.length_squared() < 0.000001:
		return
	var dir := want.normalized()
	var moved := global_position - from
	moved.y = 0.0
	if moved.dot(dir) > want.length() * 0.6:
		return
	var su: Dictionary = Balance.STEP_UP
	var max_h := float(su.max_h)
	var t := global_transform
	var r := KinematicCollision3D.new()
	var up := Vector3.UP * max_h
	if test_move(t, up, r):
		up = r.get_travel()
	if up.y < 0.05:
		return
	for fwd_len: float in [want.length(), float(su.reach) * 0.5, float(su.reach)]:
		var t1 := t.translated(up)
		var fwd := dir * maxf(fwd_len, 0.02)
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


## Вспышка на теле при попадании — видно, что пуля дошла.
func hit_flash() -> void:
	var overlay := StandardMaterial3D.new()
	overlay.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	overlay.albedo_color = Color(1.0, 0.25, 0.2, 0.55)
	overlay.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	for child in _body.get_children():
		if child is MeshInstance3D:
			(child as MeshInstance3D).material_overlay = overlay
	get_tree().create_timer(0.09).timeout.connect(func() -> void:
		for child in _body.get_children():
			if child is MeshInstance3D:
				(child as MeshInstance3D).material_overlay = null)


func _snap(p: Vector3) -> Vector3:
	var map := get_world_3d().navigation_map
	return NavigationServer3D.map_get_closest_point(map, p)


func _on_died() -> void:
	_release_rescue()
	_drop_loot_claim()
	if rescuer and is_instance_valid(rescuer):
		rescuer._rescue_target = null
	state = State.DEAD
	_set_crouch(false)
	# падение тела слышат соседи — придут смотреть
	NoiseBus.emit(global_position, Balance.AI_DEATH_NOISE, "death")
	# задание «убить N» — тому, чья пуля добила; хронике — кого и чем
	if Raid.current:
		var by_nade := String(_health.last_src.get("kind", "")) == "grenade"
		Raid.current.credit_kill(_health.last_attacker, archetype, {"faction": faction, "grenade": by_nade, "leader": loadout_id == "scav_leader"})
		# своя граната мародёров — себя или товарища (для хроники всех игроков)
		if by_nade and String(_health.last_src.get("by", "")) == "ai" and String(_health.last_src.get("faction", "")) == faction:
			Raid.current.story_world("enemy_self_grenade", {"self": String(_health.last_src.get("name", "")) == String(name), "arch": archetype})
	# хост: тело можно обыскать (содержимое — по таблице «marauder»)
	if Raid.current:
		var rng := RandomNumberGenerator.new()
		rng.randomize()
		# ящик вываливается из трупа в сторону стрелявшего (там точно свободно — его было видно)
		var to_shooter := _last_hit_from - global_position
		to_shooter.y = 0.0
		to_shooter = to_shooter.normalized() if to_shooter.length() > 0.01 else Vector3(sin(_facing), 0.0, cos(_facing))
		var rest := global_position + to_shooter * Balance.CRATE_TOSS_DIST
		# что было на нём — как есть: оружие с обвесом, износом и остатком в магазине, запасные
		# магазины (сколько не расстрелял), броня с плитами (как её побили), шлем, аптечки
		if equipment.has(_active):
			_store_mag_rounds()
		var drop: Array = []
		for slot in ["primary", "secondary", "armor", "helmet", "ears", "backpack"]:
			if equipment.has(slot):
				drop.append((equipment[slot] as Dictionary).duplicate(true))
		for it in spare:
			if it.has("rounds") or int(it.n) > 0:
				drop.append((it as Dictionary).duplicate(true))
		for it in meds:
			drop.append((it as Dictionary).duplicate(true))
		var lt := String(WeaponDb.loadout(loadout_id).get("loot_table", ""))
		if lt != "":
			drop.append_array(ItemDb.roll(lt, rng))
		# всё с тела — найдено в рейде (награбленное помечено ещё в ящике)
		for e in drop:
			(e as Dictionary)["fir"] = true
		# награбленное — тоже здесь
		drop.append_array(pack)
		pack = []
		Raid.current.spawn_drop(rest, "Ящик мародёра", drop, LootContainer.Look.CRATE,
			global_position + Vector3.UP * 1.1 - rest)
	collision_layer = 0
	collision_mask = 0
	set_physics_process(false)
	_spawn_ragdoll()


## У клиентов сигнала died нет (урон считает хост) — смерть видна по синхронизированному alive.
func _process(delta: float) -> void:
	# фонарь — раз в секунду: темно ли там, где он стоит
	_torch_t -= delta
	if _torch_t <= 0.0 and _torch:
		_torch_t = 1.0
		var dark := _health.alive and not _health.downed and RaidAtmosphere.current != null and RaidAtmosphere.current.is_dark(global_position)
		# фонарь на оружии — светит он (куда ствол), налобный не нужен
		var gun_light := false
		if _main_gun:
			for l in _main_gun.find_children("Flashlight_*", "SpotLight3D", true, false):
				(l as Light3D).visible = dark
				gun_light = true
		_torch.visible = dark and not gun_light
	# раненый (видно у всех по синхронизированному downed): основное оружие убрано
	if _health.downed != _shown_down:
		_shown_down = _health.downed
		if _main_gun:
			_main_gun.visible = not _shown_down
		# у клиентов пули ищут тело своей физикой — коллизия лежащего тоже низкая
		_apply_shape()
	if not _health.alive and _ragdoll == null:
		collision_layer = 0
		collision_mask = 0
		_spawn_ragdoll()


## Смерть: капсула прячется, модель падает клипом смерти по обстоятельствам (откуда стреляли,
## в голову, в приседе, раненым, взрыв) и остаётся лежать — тот же персонаж, не манекен. Без модели
## Persona — прежний регдолл, толкнутый от стрелявшего.
func _spawn_ragdoll() -> void:
	if _ragdoll != null or _died_shown:
		return
	var anim := get_node_or_null("CharacterAnimator") as CharacterAnimator
	if anim and anim.has_model():
		_died_shown = true
		# корпус ровно; масштаб — как у типа (присед сжимал тело по высоте — физике нужен ровный)
		_body.rotation.x = 0.0
		_body.scale = _base_scale
		# умер — умер: тело падает регдоллом той же модели (поза — с последнего кадра), толчок — от
		# стрелявшего (у клиента направления нет — падает само); нет физкостей — клип смерти
		var away := global_position - _last_hit_from if _last_hit_from != Vector3.ZERO else Vector3.ZERO
		away.y = 0.0
		var push: Dictionary = Balance.RAGDOLL_DEATH_PUSH
		var imp := away.normalized() * (float(push.base) + float(push.per_damage) * _last_damage) if away.length() > 0.01 else Vector3.ZERO
		if not anim.ragdoll(velocity, imp * 4.0, global_position + Vector3.UP * 1.2):
			anim.die(anim.death_clip(_last_hit_from, _health.last_zone, crouched, false))
		# оружие ушло в ящик с телом — в мёртвой руке его не рисуем
		if _main_gun:
			_main_gun.visible = false
		velocity = Vector3.ZERO
		if _say_label:
			_say_label.visible = false
		Audio.play("death", global_position + Vector3.UP * 1.5)
		Audio.play("fall", global_position, -4.0)
		return
	var mat := (_body.get_node("Torso") as MeshInstance3D).get_surface_override_material(0)
	var away := global_position - _last_hit_from
	away.y = 0.0
	away = away.normalized() if away.length() > 0.01 else -Vector3(sin(_facing), 0.0, cos(_facing))
	var push: Dictionary = Balance.RAGDOLL_DEATH_PUSH
	var imp := away * (float(push.base) + float(push.per_damage) * _last_damage)
	var xf := Transform3D(Basis(Vector3.UP, _body.rotation.y), global_position)
	_ragdoll = Ragdoll.spawn(get_tree().current_scene, xf, velocity, imp, global_position + Vector3.UP * 1.25, mat, mat)
	velocity = Vector3.ZERO
	_body.visible = false
	if _say_label:
		_say_label.visible = false
	Audio.play("death", global_position + Vector3.UP * 1.5)
	Audio.play("fall", global_position, -4.0)


func _animation_event(clip: String) -> void:
	animation_event = clip
	animation_event_seq += 1


func _profile_path(map: RID, target: Vector3) -> PackedVector3Array:
	var began: int = Time.get_ticks_usec() if work_profile_enabled else 0
	var path: PackedVector3Array = NavigationServer3D.map_get_path(map, global_position, target, true)
	if work_profile_enabled:
		_record_work("tactical_path", began)
	return path


## Остаток сохраняет фазу, чтобы периодические проверки не съезжались на один кадр.
func _next_work_delay(remaining: float, period: float) -> float:
	return period - fposmod(-remaining, period)


## Уже выданный путь не сбрасывается от одинаковой команды на каждом физическом шаге.
func _set_move_target(target: Vector3, snap: bool = false) -> void:
	var epsilon_sq: float = pow(float(Balance.AI_WORK.target_epsilon_m), 2.0)
	var resolved: Vector3 = target
	if snap:
		var map: RID = get_world_3d().navigation_map
		var iteration: int = NavigationServer3D.map_get_iteration_id(map)
		if _nav_request != Vector3.INF and target.distance_squared_to(_nav_request) <= epsilon_sq \
				and iteration == _nav_iteration and _agent.target_position.distance_squared_to(_nav_resolved) <= epsilon_sq:
			return
		resolved = _snap(target)
		_nav_request = target
		_nav_resolved = resolved
		_nav_iteration = iteration
	else:
		_nav_request = Vector3.INF
	if _agent.target_position.distance_squared_to(resolved) > epsilon_sq:
		_agent.target_position = resolved
		if work_profile_enabled:
			_record_work("target_set", Time.get_ticks_usec())
