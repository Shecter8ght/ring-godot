extends Node
## Шина шума — единственный способ для AI «услышать» игрока. Autoload `NoiseBus`.
## Кто шумит — зовёт emit; кто слушает — подписан на сигнал и сам сравнивает дистанцию с радиусом.
## Сеть: мародёры живут и слушают только на хосте (см. marauder.gd), поэтому шум с клиента
## пересылается туда RPC'ом, а не летит локальным сигналом — там его слушать некому.

## pos — где, radius_m — до какого расстояния слышно, kind — "step" / "shot" / "door".
signal noise(pos: Vector3, radius_m: float, kind: String)


func emit(pos: Vector3, radius_m: float, kind: String) -> void:
	if Net.is_networked() and not multiplayer.is_server():
		_report.rpc_id(1, pos, radius_m, kind)
	else:
		noise.emit(pos, radius_m, kind)


@rpc("any_peer", "call_remote", "reliable")
func _report(pos: Vector3, radius_m: float, kind: String) -> void:
	if multiplayer.is_server():
		noise.emit(pos, radius_m, kind)
