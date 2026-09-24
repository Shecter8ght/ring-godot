extends Node
## Шина шума — единственный способ для AI «услышать» игрока. Autoload `NoiseBus`.
## Кто шумит — зовёт emit; кто слушает — подписан на сигнал и сам сравнивает дистанцию с радиусом.
## Сеть: мародёры живут и слушают только на хосте (см. marauder.gd), поэтому шум с клиента
## пересылается туда RPC'ом, а не летит локальным сигналом — там его слушать некому.

## pos — где, radius_m — до какого расстояния слышно, kind — "step" / "shot" / "door" / "death".
signal noise(pos: Vector3, radius_m: float, kind: String)
## Окрик мародёра: from — где кричал, radius_m — докуда слышно, target — где он видел цель.
## Так (и только так) товарищи узнают о цели, которую сами не видят. Только на хосте.
signal callout(from: Vector3, radius_m: float, target: Vector3, speaker: Node)


func shout(from: Vector3, radius_m: float, target: Vector3, speaker: Node) -> void:
	callout.emit(from, radius_m, target, speaker)


func emit(pos: Vector3, radius_m: float, kind: String) -> void:
	# в дождь слышно хуже — шум доносится ближе
	radius_m *= float(RaidConditions.spec("weather").get("hear", 1.0))
	if Net.is_networked() and not multiplayer.is_server():
		_report.rpc_id(1, pos, radius_m, kind)
	else:
		noise.emit(pos, radius_m, kind)


@rpc("any_peer", "call_remote", "reliable")
func _report(pos: Vector3, radius_m: float, kind: String) -> void:
	if multiplayer.is_server():
		noise.emit(pos, radius_m, kind)
