class_name BlockoutChecks
extends Node3D
## Данные проверки пешком для постройки или участка (tools/sanatorium_study.gd -- verify): помещения и обходы
## в координатах этого узла — едут вместе с постройкой, когда её двигают или поворачивают руками.
## rooms: {uid, building, name, floor, at: [x, y, z]}; routes: {id, label, kind, points: [[x, y, z]…], checks, …}.

@export var rooms: Array = []
@export var routes: Array = []


## Помещения в мировых координатах.
func world_rooms() -> Array:
	var out: Array = []
	for r: Dictionary in rooms:
		var w: Dictionary = r.duplicate(true)
		w.at = _world(r.at as Array)
		out.append(w)
	return out


## Обходы в мировых координатах (точки и высоты проверок — по положению узла).
func world_routes() -> Array:
	var out: Array = []
	var lift: float = global_position.y
	for r: Dictionary in routes:
		var w: Dictionary = r.duplicate(true)
		var pts: Array = []
		for p: Array in r.points:
			pts.append(_world(p))
		w.points = pts
		var checks: Array = []
		for c: Array in r.get("checks", []):
			var cc: Array = c.duplicate()
			cc[2] = float(c[2]) + lift
			checks.append(cc)
		w.checks = checks
		out.append(w)
	return out


func _world(p: Array) -> Array:
	var v: Vector3 = global_transform * Vector3(float(p[0]), float(p[1]), float(p[2]))
	return [v.x, v.y, v.z]
