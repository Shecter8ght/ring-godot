class_name ShelterGround
extends Node3D
## Земля вокруг котельной (убежище): одна формула высоты для сетки земли, травы и расстановки
## растительности (tools/author_shelter_exterior.gd). У здания и во дворе — ровно, на отметке
## Balance.SHELTER_YARD.ground над полом котельной; дальше — пологие бугры леса.
## Узел — в группе «district_terrain»: травяной покров (DistrictGrass) берёт у него высоту.

## Где ровно: здание с двором и запасом (x0, z0, x1, z1), м.
const FLAT := Rect2(-26.0, -15.0, 92.0, 69.0)

static var _noise: FastNoiseLite


func _ready() -> void:
	add_to_group("district_terrain")


func height_at(x: float, z: float) -> float:
	return height(x, z)


static func height(x: float, z: float) -> float:
	if _noise == null:
		_noise = FastNoiseLite.new()
		_noise.seed = 5051
		_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
		_noise.frequency = 0.012
		_noise.fractal_octaves = 3
	var cfg: Dictionary = Balance.SHELTER_YARD
	var c: Vector2 = FLAT.get_center()
	var half: Vector2 = FLAT.size * 0.5
	var away: float = Vector2(maxf(absf(x - c.x) - half.x, 0.0), maxf(absf(z - c.y) - half.y, 0.0)).length()
	var k: float = smoothstep(float(cfg.flat_margin_m), float(cfg.hills_from_m), away)
	return float(cfg.ground) + k * (_noise.get_noise_2d(x, z) * float(cfg.hill_m) + float(cfg.hill_lift_m))
