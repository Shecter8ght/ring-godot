extends Node
## «Проспект»: обзор с полотна Объездной (эстакады) наружу — на восток. Из центра каждого окна в шумозащитном
## экране (RING_WINDOWS: Z 160…166 и 228…234, глаз X −221, высота пола полотна + 1,62) и с верхних площадок обоих
## сходов веер лучей по физике (слой мира): по горизонтали ±60° от востока через 2°, по вертикали −35…+5° через 2,5°.
## Печатает доли лучей длиннее 90 / 120 / 150 м (всего и только вниз-горизонт: без лучей выше горизонта — они уходят
## в небо), самый длинный луч с точкой, дальность видимой земли (лучи в y < 0,5): минимум, медиана, максимум.
## Только замер, окна не меняет. Код выхода 0.
##   tools/godot.cmd --headless res://tools/prospekt_ring_view.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
const MAX_M := 800.0
const EYE_H := 1.62
## (подпись, x, z центра окна / площадки)
const POINTS: Array = [
	["окно Z 160…166", -221.0, 163.0],
	["окно Z 228…234", -221.0, 231.0],
	["верх схода Z 190…200", -218.5, 195.0],
	["верх схода Z 214…224", -218.5, 219.0],
]


func _ring_h(z: float) -> float:
	return minf(15.5, 9.0 + maxf(0.0, z - 150.0) * (15.5 - 9.0) / 100.0)


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_ring_view.json", true)
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	for i in range(30):
		await get_tree().physics_frame
	var space: PhysicsDirectSpaceState3D = (level as Node3D).get_world_3d().direct_space_state
	for pt: Array in POINTS:
		var z: float = float(pt[2])
		var eye := Vector3(float(pt[1]), _ring_h(z) + EYE_H, z)
		_fan(space, String(pt[0]), eye)
	get_tree().quit(0)


func _fan(space: PhysicsDirectSpaceState3D, label: String, eye: Vector3) -> void:
	var dists: Array[float] = []      # все лучи (небо = MAX_M)
	var down: Array[float] = []       # лучи не выше горизонта
	var ground: Array[float] = []
	var far: float = -1.0
	var far_pt := Vector3.ZERO
	var far_sky: int = 0
	var rays: int = 0
	var az: float = -60.0
	while az <= 60.001:
		var el: float = -35.0
		while el <= 5.001:
			var d := Vector3(cos(deg_to_rad(el)) * cos(deg_to_rad(az)), sin(deg_to_rad(el)), cos(deg_to_rad(el)) * sin(deg_to_rad(az)))
			var q := PhysicsRayQueryParameters3D.create(eye, eye + d * MAX_M, 1)
			var h: Dictionary = space.intersect_ray(q)
			var dist: float = MAX_M
			var sky: bool = h.is_empty()
			if not sky:
				dist = eye.distance_to(h.position as Vector3)
				if (h.position as Vector3).y < 0.5:
					ground.append(dist)
			dists.append(dist)
			if el <= 0.001:
				down.append(dist)
			rays += 1
			if sky and el <= 0.001:
				far_sky += 1
			if not sky and dist > far:
				far = dist
				far_pt = h.position as Vector3
			el += 2.5
		az += 2.0
	ground.sort()
	var g_txt: String = "земля не видна"
	if not ground.is_empty():
		g_txt = "земля: лучей %d, дальность мин %.0f, медиана %.0f, макс %.0f м" % [ground.size(), ground[0], ground[ground.size() / 2], ground[ground.size() - 1]]
	print("RING | %s | глаз %s | лучей %d | >90 м: %.1f %% (вниз-горизонт %.1f %%) | >120 м: %.1f %% (%.1f %%) | >150 м: %.1f %% (%.1f %%) | самый длинный по попаданию %.0f м → %s; ушло в небо ниже горизонта %d | %s" % [
		label, eye.snapped(Vector3(0.01, 0.01, 0.01)), rays,
		_share(dists, 90.0), _share(down, 90.0), _share(dists, 120.0), _share(down, 120.0), _share(dists, 150.0), _share(down, 150.0),
		far, far_pt.snapped(Vector3(0.1, 0.1, 0.1)), far_sky, g_txt])


func _share(list: Array[float], m: float) -> float:
	if list.is_empty():
		return 0.0
	var n: int = 0
	for v in list:
		if v > m:
			n += 1
	return 100.0 * float(n) / float(list.size())
