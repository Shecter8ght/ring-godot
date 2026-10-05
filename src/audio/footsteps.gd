class_name Footsteps
extends Node
## Шаги — звук у каждого peer: по перемещению родителя (своего игрока, чужого — по синхронизации,
## мародёра — тоже), поэтому в коопе слышно и напарника, и мародёров, которых считает хост.
## Темп — от скорости (Balance.STEP_*), бег — отдельными записями, поверхность — под ногами
## (Audio.step: плитка/бетон, асфальт, металл, снег), левая/правая — чуть разным тоном.
## Шум для слуха AI сюда не относится — его шлёт Player._footsteps (только свой игрок).

## () -> float: насколько тише/громче шаг сейчас (присел, лёг), дБ. Пусто — 0.
var loud_db: Callable
## () -> String: особое движение игрока (ползком / вприсядку); пусто — обычный шаг по поверхности.
var movement_kind: Callable
## Игрок сообщает состояние пола, в том числе по сети: в воздухе шагов нет.
var grounded: Callable
var _was_airborne: bool = false
## Мародёр: тяжёлые ботинки — ниже и чуть громче.
var ai: bool = false

var _last: Vector3
var _t: float = 0.0
var _speed: float = 0.0
var _left: bool = false


func _ready() -> void:
	_last = (get_parent() as Node3D).global_position


func _process(delta: float) -> void:
	if delta <= 0.0:
		return
	var pos := (get_parent() as Node3D).global_position
	var v := Vector2(pos.x - _last.x, pos.z - _last.z).length() / delta
	_last = pos
	if grounded.is_valid():
		if not bool(grounded.call()):
			_was_airborne = true
			_t = 0.0
			return
		if _was_airborne:
			_was_airborne = false
			Audio.play("land", pos, float(Balance.JUMP.land_db))
	# телепорт (спавн, тест) — не шаги
	if v > 20.0:
		return
	# у чужих позиция приходит рывками — скорость сглаживаем
	_speed = lerpf(_speed, v, minf(1.0, delta * 8.0))
	if _speed < 0.35:
		# встал — следующий шаг сразу, как тронется
		_t = minf(_t, 0.12)
		return
	_t -= delta
	if _t > 0.0:
		return
	_t = clampf(Balance.STEP_STRIDE / _speed, float(Balance.STEP_INTERVAL[0]), float(Balance.STEP_INTERVAL[1]))
	_left = not _left
	var extra := float(loud_db.call()) if loud_db.is_valid() else 0.0
	var special := String(movement_kind.call()) if movement_kind.is_valid() else ""
	if special != "":
		Audio.play(special, pos, extra)
		return
	Audio.step(pos, _speed > Balance.STEP_RUN_SPEED, ai, extra, _left)
