extends Node
## Шина шума — единственный способ для AI «услышать» игрока. Autoload `NoiseBus`.
## Кто шумит — зовёт emit; кто слушает — подписан на сигнал и сам сравнивает дистанцию с радиусом.

## pos — где, radius_m — до какого расстояния слышно, kind — "step" / "shot" / "door".
signal noise(pos: Vector3, radius_m: float, kind: String)


func emit(pos: Vector3, radius_m: float, kind: String) -> void:
	noise.emit(pos, radius_m, kind)
