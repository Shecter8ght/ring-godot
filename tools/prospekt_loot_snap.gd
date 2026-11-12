extends Node
## «Проспект», вторая очередь, этап 5б: подгонка новых мест лута по физике и навигации рейдовой карты.
## Вход — JSON со списком кандидатов [{x, z, y, id}] (LOOT_SNAP_IN), выход — LOOT_SNAP_OUT: для каждого лучом вниз
## найден пол, ящик 0,9 м не пересекает коллизию мира, над ним есть проём в 1,7 м, до навигации не дальше 1,6 м;
## если место занято — ближайшее свободное в круге до 3 м.
##   LOOT_SNAP_IN=… LOOT_SNAP_OUT=… tools/godot.cmd --headless res://tools/prospekt_loot_snap.tscn

const LEVEL := "res://scenes/levels/prospekt.tscn"
const BOX := Vector3(0.9, 0.9, 0.9)
const MAX_NAV := 1.6


func _ready() -> void:
	RaidEvents.enabled = false
	RaidConditions.from_host = {"time": "dusk", "weather": "clear", "power": "on"}
	Profile.use_file("user://profile_prospekt_loot_snap.json", true)
	await get_tree().process_frame
	var level: Node = load(LEVEL).instantiate()
	get_tree().root.add_child(level)
	get_tree().current_scene = level
	var t0: int = Time.get_ticks_msec()
	while int(level.get("_marauders_spawned")) <= 0 and Time.get_ticks_msec() - t0 < 180000:
		await get_tree().process_frame
	for i in range(30):
		await get_tree().physics_frame
	var path_in: String = OS.get_environment("LOOT_SNAP_IN")
	var path_out: String = OS.get_environment("LOOT_SNAP_OUT")
	var cands: Array = JSON.parse_string(FileAccess.get_file_as_string(path_in)) as Array
	var space: PhysicsDirectSpaceState3D = (level as Node3D).get_world_3d().direct_space_state
	var map: RID = (level as Node3D).get_world_3d().navigation_map
	var out: Array = []
	var bad: int = 0
	for c: Dictionary in cands:
		var res: Dictionary = _snap(space, map, float(c.x), float(c.z), float(c.y))
		res["id"] = c.id
		if not bool(res.ok):
			bad += 1
		out.append(res)
	var f := FileAccess.open(path_out, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, "\t"))
	f.close()
	print("кандидатов %d, не подошло %d" % [cands.size(), bad])
	get_tree().quit(0)


## Пол под точкой: луч вниз от fy+2 до fy−1,5.
func _floor(space: PhysicsDirectSpaceState3D, x: float, z: float, fy: float) -> float:
	var q := PhysicsRayQueryParameters3D.create(Vector3(x, fy + 2.0, z), Vector3(x, fy - 1.5, z), 1)
	var h: Dictionary = space.intersect_ray(q)
	if h.is_empty() or (h.normal as Vector3).y < 0.7:
		return INF
	return (h.position as Vector3).y


func _valid(space: PhysicsDirectSpaceState3D, map: RID, x: float, z: float, fy: float) -> Dictionary:
	var y: float = _floor(space, x, z, fy)
	if y == INF:
		return {"ok": false, "why": "нет пола"}
	if absf(y - fy) > 1.2:
		return {"ok": false, "why": "пол на %.2f, ждали %.2f" % [y, fy]}
	var sq := PhysicsShapeQueryParameters3D.new()
	var sh := BoxShape3D.new()
	sh.size = BOX
	sq.shape = sh
	sq.collision_mask = 1
	sq.transform = Transform3D(Basis.IDENTITY, Vector3(x, y + 0.1 + BOX.y * 0.5, z))
	if not space.intersect_shape(sq, 1).is_empty():
		return {"ok": false, "why": "занято"}
	var up := PhysicsRayQueryParameters3D.create(Vector3(x, y + 0.6, z), Vector3(x, y + 2.3, z), 1)
	if not space.intersect_ray(up).is_empty():
		return {"ok": false, "why": "низко"}
	var p: Vector3 = Vector3(x, y, z)
	var n: Vector3 = NavigationServer3D.map_get_closest_point(map, p)
	var d: float = n.distance_to(p)
	if d > MAX_NAV:
		return {"ok": false, "why": "до навигации %.1f" % d}
	return {"ok": true, "y": y, "nav": d}


func _snap(space: PhysicsDirectSpaceState3D, map: RID, x: float, z: float, fy: float) -> Dictionary:
	var r: Dictionary = _valid(space, map, x, z, fy)
	if bool(r.ok):
		r["x"] = x
		r["z"] = z
		r["moved"] = 0.0
		return r
	var first: String = String(r.why)
	for ring in range(1, 7):
		var rad: float = 0.5 * ring
		var best: Dictionary = {}
		for k in range(16):
			var a: float = TAU * float(k) / 16.0
			var px: float = x + cos(a) * rad
			var pz: float = z + sin(a) * rad
			var v: Dictionary = _valid(space, map, px, pz, fy)
			if bool(v.ok) and (best.is_empty() or float(v.nav) < float(best.nav)):
				best = v
				best["x"] = px
				best["z"] = pz
		if not best.is_empty():
			best["moved"] = rad
			best["why"] = first
			return best
	return {"ok": false, "why": first, "x": x, "z": z, "y": fy, "moved": 0.0}
