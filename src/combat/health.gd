class_name Health
extends Node
## Здоровье сущности. Узел-компонент: вешается на игрока и мародёра.
## Состояния: жив → тяжело ранен (downed: лежит, свой запас down_hp, истекает кровью bleed_t) →
## мёртв. Ранение вместо смерти — только у can_down и только если удар не смертельный
## (zone: "head" без шлема, "blast_close" — насмерть) и ранений за рейд меньше DOWN_MAX.
## Всё считает авторитет (хост), остальным — синхронизатором.

signal damaged(amount: float, from: Vector3)
signal died
## Лёг раненым (true) / подняли (false).
signal downed_changed(on: bool)

@export var max_hp: float = 100.0

var hp: float
var alive: bool = true
## Может лечь раненым вместо смерти (игрок, мародёр; мишени — нет).
var can_down: bool = false
## Смертельное попадание — сначала тоже ранение (игрок): мгновенной смерти нет, пока есть
## ранения в запасе (DOWN_MAX); уже лежащего — добивает.
var always_down_first: bool = false
var downed: bool = false
var down_hp: float = 0.0
var bleed_t: float = 0.0
## Сколько раз ложился за рейд.
var downs: int = 0
## () -> bool: голова защищена всегда (тесты) — попадание в голову не насмерть.
var head_protected: Callable
## Хост: урон до вычета здоровья проходит через фильтр брони (Armor):
## (amount, zone, from, at, bullet) -> [урон, насмерть?]. Нет фильтра — голова насмерть.
var damage_filter: Callable
## Хост: чей был последний урон (peer id стрелявшего игрока; 1 — хост или соло) — кому
## засчитать убийство.
var last_attacker: int = 0
## Чит «бессмертие» (хост): попадания видно и слышно, но здоровье не убывает; лежащего — поднимает.
var invulnerable: bool = false


func _ready() -> void:
	hp = max_hp
	if Net.is_networked():
		_setup_sync()


## hp/alive реплицируются от того, кто авторитет ИМЕННО для Health (у Marauder это тот же хост,
## что и для всего узла; у Player — хост, хотя сам Player отдан во владение своему peer,
## см. sector_level._spawn_player_node). Без этого урон применяется, но остальные его не видят.
func _setup_sync() -> void:
	var sync := MultiplayerSynchronizer.new()
	# постоянное имя: синхронизатор адресуется по пути, а автоимя (@MultiplayerSynchronizer@N)
	# у каждого peer своё — пакеты хоста не находили узел у клиента
	sync.name = "Sync"
	var config := SceneReplicationConfig.new()
	for prop in [".:hp", ".:alive", ".:downed", ".:down_hp", ".:bleed_t", ".:downs"]:
		var path := NodePath(prop)
		config.add_property(path)
		config.property_set_replication_mode(path, SceneReplicationConfig.REPLICATION_MODE_ON_CHANGE)
	sync.replication_config = config
	# У свежего узла своё умалчиваемое authority (1) — не наследуется от родителя автоматически.
	# Ставить его нужно ДО add_child: иначе спавнер путает pending-спавн с уже вошедшим в дерево узлом.
	sync.set_multiplayer_authority(get_multiplayer_authority())
	Net.scope_sync(self, sync)
	add_child(sync)


## zone: "" (неизвестно), "head", "thorax", "arms", "legs", "blast", "blast_close"; at — куда
## попали; bullet — {pen, armor_dmg} пули (пусто — осколки). Броня (damage_filter) решает, сколько
## прошло и насмерть ли голова.
func take_damage(amount: float, from: Vector3, zone: String = "", at: Vector3 = Vector3.INF, bullet: Dictionary = {}) -> void:
	if not alive:
		return
	if invulnerable:
		damaged.emit(amount, from)
		return
	var lethal := zone == "blast_close" or (zone == "head" and not damage_filter.is_valid())
	if damage_filter.is_valid():
		var r: Array = damage_filter.call(amount, zone, from, at, bullet)
		amount = float(r[0])
		lethal = lethal or bool(r[1])
	if lethal and zone == "head" and head_protected.is_valid() and bool(head_protected.call()):
		lethal = false
	# игрок: смертельное — тяжёлое ранение с быстрым кровотечением
	if lethal and always_down_first and can_down and not downed and downs < Balance.DOWN_MAX:
		damaged.emit(amount, from)
		_go_down()
		bleed_t *= Balance.DOWN_LETHAL_BLEED_K
		return
	# в голову без шлема, подорвался на гранате — смерть сразу, сколько бы ни было здоровья
	if lethal:
		hp = 0.0
		damaged.emit(amount, from)
		_die()
		return
	if downed:
		# лежащего добивают: свой запас на 1–3 попадания
		down_hp = maxf(0.0, down_hp - amount)
		damaged.emit(amount, from)
		if down_hp <= 0.0:
			_die()
		return
	hp = maxf(0.0, hp - amount)
	damaged.emit(amount, from)
	if hp <= 0.0:
		if can_down and downs < Balance.DOWN_MAX:
			_go_down()
		else:
			_die()


func _go_down() -> void:
	var bleed: Array = Balance.DOWN_BLEED_SEC
	bleed_t = float(bleed[mini(downs, bleed.size() - 1)])
	downs += 1
	hp = 0.0
	down_hp = Balance.DOWN_HP
	downed = true
	downed_changed.emit(true)


func _die() -> void:
	downed = false
	alive = false
	died.emit()


## Кровотечение (авторитет): кончилось время — смерть.
func _process(delta: float) -> void:
	if not downed or not alive:
		return
	if Net.is_networked() and not is_multiplayer_authority():
		return
	if invulnerable:
		revive(1.0)
		return
	bleed_t -= delta
	if bleed_t <= 0.0:
		_die()


## Поднять раненого (хост): встаёт с долей здоровья frac.
func revive(frac: float) -> void:
	if not alive or not downed:
		return
	downed = false
	hp = maxf(1.0, max_hp * frac)
	downed_changed.emit(false)


## Перевязка лёжа (хост): + секунд до смерти.
func add_bleed(sec: float) -> void:
	if downed and alive:
		bleed_t += sec


## Сдаться лёжа (хост): смерть сразу.
func give_up() -> void:
	if downed and alive:
		_die()


## Лечение (хост): не выше max_hp, мёртвых и лежащих не поднимает (лежащего — revive).
func heal(amount: float) -> void:
	if alive and not downed:
		hp = minf(max_hp, hp + amount)


## Точка входа для Hitscan: применяет урон сама, если мы авторитет по этому узлу (сингл/хост),
## иначе просит хост — так урон всегда считается один раз и в одном месте (правило AGENTS.md).
func apply_or_request_damage(amount: float, from: Vector3, zone: String = "", attacker: int = -1, at: Vector3 = Vector3.INF, bullet: Dictionary = {}) -> void:
	if not Net.is_networked() or is_multiplayer_authority():
		last_attacker = multiplayer.get_unique_id() if attacker < 0 else attacker
		take_damage(amount, from, zone, at, bullet)
	else:
		request_damage.rpc_id(1, amount, from, zone, at, bullet)


@rpc("any_peer", "call_remote", "reliable")
func request_damage(amount: float, from: Vector3, zone: String = "", at: Vector3 = Vector3.INF, bullet: Dictionary = {}) -> void:
	if is_multiplayer_authority():
		last_attacker = multiplayer.get_remote_sender_id()
		take_damage(amount, from, zone, at, bullet)
