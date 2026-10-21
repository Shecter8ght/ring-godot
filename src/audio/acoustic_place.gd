extends RefCounted
## Где стоит стрелок — для хвоста выстрела (Audio): улица, помещение или большое помещение (ангар, зал,
## арена, атриум). Размечать карту не нужно: только лучи физики по миру от ствола (Balance.SHOT_PLACE).
## Подключается через preload (class_name не нужен): const AcousticPlace := preload("res://src/audio/acoustic_place.gd").

const OUTDOOR := "outdoor"
const ROOM := "room"
const HALL := "hall"


## at — точка у ствола (грудь стрелка). Возвращает OUTDOOR / ROOM / HALL.
static func classify(world: World3D, at: Vector3) -> String:
	return String(measure(world, at).place)


## То же с цифрами, по которым принято решение (консоль «place»): place, up (до потолка, −1 — неба ничто не
## закрывает), covered (сколько из 4 косых лучей попало), median (медиана 8 лучей по сторонам, м).
static func measure(world: World3D, at: Vector3) -> Dictionary:
	var cfg: Dictionary = Balance.SHOT_PLACE
	var space: PhysicsDirectSpaceState3D = world.direct_space_state
	var up := _reach(space, at, Vector3.UP, float(cfg.ceiling_max_m))
	if up < 0.0:
		return {"place": OUTDOOR, "up": up, "covered": 0, "median": 0.0}
	# навес или козырёк: плита над головой есть, а вбок под 45° она не продолжается — стен нет, это улица
	var diag_len := clampf(up * 2.0, 6.0, float(cfg.ceiling_max_m) * 2.0)
	var covered := 0
	for i in 4:
		var a := TAU * float(i) / 4.0
		if _reach(space, at, Vector3(cos(a), 1.0, sin(a)).normalized(), diag_len) >= 0.0:
			covered += 1
	if covered < int(cfg.side_hits_min):
		return {"place": OUTDOOR, "up": up, "covered": covered, "median": 0.0}
	var wall_max := float(cfg.wall_max_m)
	var walls: Array[float] = []
	for i in 8:
		var a := TAU * float(i) / 8.0
		var d := _reach(space, at, Vector3(cos(a), 0.0, sin(a)), wall_max)
		walls.append(wall_max if d < 0.0 else d)
	walls.sort()
	var median := (walls[3] + walls[4]) * 0.5
	var place := ROOM if median < float(cfg.room_median_m) and up < float(cfg.hall_up_m) else HALL
	return {"place": place, "up": up, "covered": covered, "median": median}


## Расстояние до первой преграды мира по лучу; −1 — луч ушёл свободно.
static func _reach(space: PhysicsDirectSpaceState3D, from: Vector3, dir: Vector3, length: float) -> float:
	var query := PhysicsRayQueryParameters3D.create(from, from + dir * length, Hitscan.LAYER_WORLD)
	var hit := space.intersect_ray(query)
	return -1.0 if hit.is_empty() else from.distance_to(hit.position as Vector3)
