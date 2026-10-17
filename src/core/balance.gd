extends Node
## Весь баланс игры — только здесь. Autoload `Balance`.
## Другие скрипты читают значения отсюда и не держат своих чисел.

# --- Попадания: визуальный масштаб в метрах, скорость м/с, время с ---
## Художественные профили для читаемости, не расчёт разрушения или пробития.
const IMPACT_MAX_BURSTS: int = 72
const IMPACT_MAX_DECALS: int = 320
const IMPACT_MAX_DISTANCE: float = 85.0
## Дальше от камеры — без мелочи (травинки, крошка), искр, обломков и веера вдвое меньше, без света.
const IMPACT_LOD_M: float = 30.0
const IMPACT_GRAVITY: float = 9.81
const IMPACT_OFFSET: float = 0.012
const IMPACT_CLEANUP_MARGIN: float = 0.15
## Вращение кусков в полёте, °/с (наибольшее).
const IMPACT_SPIN: float = 420.0
## Куда падают куски (ImpactFx): пол ищем лучом вниз на down_m. Попали в верхнюю грань — смотрим
## опору в стороне на probe_m (луч с высоты lift_m): ниже точки удара больше чем на edge_m — грань
## маленькая (стол, капот, ящик), дальше small_radius_m от удара куски падают с неё на пол.
const IMPACT_FLOOR := {"down_m": 8.0, "probe_m": 0.6, "lift_m": 0.5, "edge_m": 0.35, "small_radius_m": 0.35}
## Искры: speed (м/с), life (с), width — ширина полосы (м), stretch — длина полосы от скорости (с),
## не длиннее stretch_max (м), spread — конус (°), drag — доля скорости за с, bounce / friction —
## отскок от пола, energy — яркость (выше 1 — ярче сцены), aim — вес нормали и отражения пули.
const IMPACT_SPARKS := {"speed": Vector2(4.0, 15.0), "life": Vector2(0.22, 0.75), "width": Vector2(0.004, 0.009),
	"stretch": 0.028, "stretch_max": 0.32, "spread": 34.0, "drag": 1.3, "bounce": 0.42, "friction": 0.6,
	"energy": 3.5, "aim": Vector2(0.4, 1.0)}
## Вспышка удара: life (с), color, energy — яркость; свет на миг — light_range (м), light_energy,
## одновременно не больше light_max.
const IMPACT_FLASH := {"life": 0.06, "color": Color(1.0, 0.78, 0.45), "energy": 5.0, "light_range": 2.6, "light_energy": 3.0, "light_max": 4}
## Облако пыли: разлёт (м/с), сопротивление воздуха (доля скорости за с), конус (°).
const IMPACT_DUST := {"speed": Vector2(0.25, 0.85), "drag": Vector2(1.3, 2.4), "spread": 50.0}
const IMPACT_DECALS: Dictionary = {
	"concrete": {"asset": "concrete", "size": Vector2(0.10, 0.16), "tint": Color(0.82, 0.78, 0.7, 0.92)},
	"tile": {"asset": "concrete", "size": Vector2(0.14, 0.22), "tint": Color(0.95, 0.93, 0.88, 0.9)},
	"asphalt": {"asset": "concrete", "size": Vector2(0.09, 0.14), "tint": Color(0.55, 0.52, 0.48, 0.9)},
	"metal": {"asset": "metal", "size": Vector2(0.07, 0.11), "tint": Color(0.34, 0.3, 0.25, 0.95)},
	"wood": {"asset": "wood", "size": Vector2(0.10, 0.16), "tint": Color(0.86, 0.74, 0.64, 0.95)},
	"cardboard": {"asset": "wood", "size": Vector2(0.08, 0.12), "tint": Color(0.78, 0.62, 0.4, 0.9)},
	"plastic": {"asset": "metal", "size": Vector2(0.07, 0.11), "tint": Color(0.28, 0.28, 0.3, 0.92)},
	"fabric": {"asset": "", "size": Vector2(0.07, 0.10), "tint": Color(0.08, 0.07, 0.06, 0.85)},
	"grass": {"asset": "soil", "size": Vector2(0.14, 0.22), "tint": Color(0.62, 0.55, 0.46, 0.95)},
	"dirt": {"asset": "soil", "size": Vector2(0.16, 0.24), "tint": Color(0.78, 0.7, 0.6, 0.95)},
	"mud": {"asset": "soil", "size": Vector2(0.14, 0.22), "tint": Color(0.42, 0.37, 0.32, 0.95)},
	"gravel": {"asset": "soil", "size": Vector2(0.12, 0.18), "tint": Color(0.86, 0.84, 0.8, 0.85)},
}
## Слои одного попадания (ImpactBurst), любой необязателен. Общие ключи: count — сколько (от–до),
## size — наибольшая сторона (м; у веера — ширина полосы), speed (м/с), life (с, от–до), spread —
## конус (°), drag — доля скорости за с, color, aim — вес нормали и отражения пули в направлении.
## debris / bits — куски с весом: mesh — форма, bounce — упругость отскока, flutter — трепет (м/с²),
##   alt / alt_share — второй цвет и его доля (сухие травинки, светлые сколы);
## spray — веер мелкого материала полосами: gravity — доля тяжести, stretch — длина полосы от
##   скорости (с), size_end — во сколько раз полоса шире к концу (тает облачком);
## dust — медленное облако: count, size — диаметр (м), opacity, rise — подъём (м/с², вниз — минус);
## sparks — искры: count, chance — доля попаданий с искрами (сердечник по камню искрит не всегда);
## flash — вспышка: size — диаметр (м), light — свет на миг; trample — трава вокруг ложится (радиус, м).
const IMPACT_SURFACES: Dictionary = {
	"concrete": {
		"debris": {"mesh": "chip", "count": Vector2i(8, 13), "size": Vector2(0.008, 0.035), "speed": Vector2(2.0, 6.5), "life": Vector2(0.8, 1.5), "spread": 48.0, "drag": 0.4, "bounce": 0.3, "aim": Vector2(1.0, 0.5), "color": Color(0.59, 0.56, 0.5), "alt": Color(0.72, 0.7, 0.65), "alt_share": 0.3},
		"bits": {"mesh": "chip", "count": Vector2i(14, 22), "size": Vector2(0.003, 0.008), "speed": Vector2(3.0, 9.0), "life": Vector2(0.35, 0.8), "spread": 38.0, "drag": 1.6, "bounce": 0.2, "aim": Vector2(1.0, 0.6), "color": Color(0.66, 0.63, 0.57)},
		"spray": {"count": Vector2i(12, 18), "size": Vector2(0.045, 0.1), "speed": Vector2(5.0, 12.0), "life": Vector2(0.25, 0.55), "spread": 20.0, "drag": 6.0, "gravity": 0.2, "stretch": 0.035, "aim": Vector2(1.0, 0.5), "color": Color(0.74, 0.71, 0.65, 0.8)},
		"dust": {"count": 7, "size": Vector2(0.22, 0.6), "life": Vector2(1.2, 2.2), "opacity": 0.36, "rise": 0.04, "color": Color(0.64, 0.62, 0.57)},
		"sparks": {"count": Vector2i(1, 3), "chance": 0.15},
	},
	"tile": {
		"debris": {"mesh": "flake", "count": Vector2i(5, 9), "size": Vector2(0.012, 0.045), "speed": Vector2(2.0, 6.0), "life": Vector2(0.7, 1.3), "spread": 52.0, "drag": 0.3, "bounce": 0.4, "aim": Vector2(1.0, 0.5), "color": Color(0.8, 0.78, 0.71), "alt": Color(0.9, 0.89, 0.85), "alt_share": 0.4},
		"bits": {"mesh": "chip", "count": Vector2i(8, 14), "size": Vector2(0.003, 0.007), "speed": Vector2(3.0, 8.0), "life": Vector2(0.35, 0.7), "spread": 40.0, "drag": 1.6, "bounce": 0.3, "aim": Vector2(1.0, 0.6), "color": Color(0.84, 0.82, 0.77)},
		"spray": {"count": Vector2i(8, 12), "size": Vector2(0.035, 0.075), "speed": Vector2(5.0, 11.0), "life": Vector2(0.2, 0.45), "spread": 22.0, "drag": 6.0, "gravity": 0.2, "stretch": 0.035, "aim": Vector2(1.0, 0.5), "color": Color(0.86, 0.85, 0.81, 0.65)},
		"dust": {"count": 3, "size": Vector2(0.12, 0.3), "life": Vector2(0.8, 1.4), "opacity": 0.2, "rise": 0.04, "color": Color(0.8, 0.78, 0.72)},
		"sparks": {"count": Vector2i(1, 2), "chance": 0.08},
	},
	"asphalt": {
		"debris": {"mesh": "chip", "count": Vector2i(6, 10), "size": Vector2(0.006, 0.028), "speed": Vector2(1.8, 5.5), "life": Vector2(0.7, 1.3), "spread": 50.0, "drag": 0.5, "bounce": 0.3, "aim": Vector2(1.0, 0.5), "color": Color(0.25, 0.24, 0.22), "alt": Color(0.42, 0.41, 0.38), "alt_share": 0.3},
		"bits": {"mesh": "chip", "count": Vector2i(10, 16), "size": Vector2(0.002, 0.006), "speed": Vector2(3.0, 8.0), "life": Vector2(0.35, 0.7), "spread": 40.0, "drag": 1.6, "bounce": 0.2, "aim": Vector2(1.0, 0.6), "color": Color(0.3, 0.29, 0.27)},
		"spray": {"count": Vector2i(10, 14), "size": Vector2(0.04, 0.085), "speed": Vector2(4.0, 10.0), "life": Vector2(0.22, 0.5), "spread": 22.0, "drag": 6.0, "gravity": 0.2, "stretch": 0.035, "aim": Vector2(1.0, 0.5), "color": Color(0.42, 0.4, 0.37, 0.7)},
		"dust": {"count": 4, "size": Vector2(0.15, 0.4), "life": Vector2(1.0, 1.8), "opacity": 0.22, "rise": 0.04, "color": Color(0.42, 0.4, 0.37)},
		"sparks": {"count": Vector2i(1, 3), "chance": 0.12},
	},
	"metal": {
		"debris": {"mesh": "flake", "count": Vector2i(3, 6), "size": Vector2(0.003, 0.012), "speed": Vector2(1.5, 4.5), "life": Vector2(0.5, 1.0), "spread": 40.0, "drag": 0.3, "bounce": 0.4, "aim": Vector2(1.0, 0.6), "color": Color(0.29, 0.3, 0.31), "alt": Color(0.55, 0.52, 0.45), "alt_share": 0.4},
		"dust": {"count": 2, "size": Vector2(0.08, 0.22), "life": Vector2(0.5, 1.0), "opacity": 0.16, "rise": 0.5, "color": Color(0.5, 0.5, 0.5)},
		"sparks": {"count": Vector2i(14, 26), "chance": 1.0},
		"flash": {"size": 0.3, "light": true},
	},
	"glass": {
		"debris": {"mesh": "shard", "count": Vector2i(8, 14), "size": Vector2(0.01, 0.04), "speed": Vector2(1.5, 4.5), "life": Vector2(0.8, 1.4), "spread": 40.0, "drag": 0.2, "bounce": 0.35, "aim": Vector2(1.0, 0.4), "color": Color(0.68, 0.79, 0.81, 0.6)},
		"bits": {"mesh": "shard", "count": Vector2i(10, 18), "size": Vector2(0.003, 0.008), "speed": Vector2(2.0, 6.0), "life": Vector2(0.4, 0.9), "spread": 45.0, "drag": 0.8, "bounce": 0.3, "aim": Vector2(1.0, 0.4), "color": Color(0.8, 0.88, 0.9, 0.7)},
	},
	"wood": {
		"debris": {"mesh": "splinter", "count": Vector2i(6, 11), "size": Vector2(0.02, 0.075), "speed": Vector2(2.0, 6.0), "life": Vector2(0.8, 1.5), "spread": 42.0, "drag": 0.7, "bounce": 0.25, "aim": Vector2(1.0, 0.5), "color": Color(0.54, 0.37, 0.19), "alt": Color(0.72, 0.56, 0.36), "alt_share": 0.4},
		"bits": {"mesh": "chip", "count": Vector2i(10, 16), "size": Vector2(0.003, 0.008), "speed": Vector2(2.5, 7.0), "life": Vector2(0.4, 0.9), "spread": 40.0, "drag": 1.8, "bounce": 0.15, "aim": Vector2(1.0, 0.5), "color": Color(0.66, 0.5, 0.3)},
		"spray": {"count": Vector2i(8, 12), "size": Vector2(0.035, 0.075), "speed": Vector2(4.0, 9.0), "life": Vector2(0.22, 0.45), "spread": 22.0, "drag": 6.0, "gravity": 0.3, "stretch": 0.03, "aim": Vector2(1.0, 0.5), "color": Color(0.7, 0.56, 0.38, 0.6)},
		"dust": {"count": 2, "size": Vector2(0.1, 0.25), "life": Vector2(0.6, 1.1), "opacity": 0.15, "rise": 0.03, "color": Color(0.6, 0.47, 0.3)},
	},
	"cardboard": {
		"debris": {"mesh": "paper", "count": Vector2i(4, 8), "size": Vector2(0.015, 0.05), "speed": Vector2(0.8, 2.5), "life": Vector2(1.0, 1.8), "spread": 50.0, "drag": 2.4, "bounce": 0.0, "flutter": 6.0, "aim": Vector2(1.0, 0.4), "color": Color(0.58, 0.44, 0.27), "alt": Color(0.7, 0.6, 0.45), "alt_share": 0.3},
		"dust": {"count": 1, "size": Vector2(0.08, 0.16), "life": Vector2(0.4, 0.8), "opacity": 0.1, "rise": 0.02, "color": Color(0.58, 0.5, 0.4)},
	},
	"fabric": {
		"debris": {"mesh": "fiber", "count": Vector2i(3, 6), "size": Vector2(0.006, 0.02), "speed": Vector2(0.4, 1.4), "life": Vector2(0.6, 1.2), "spread": 55.0, "drag": 3.0, "bounce": 0.0, "flutter": 3.0, "aim": Vector2(1.0, 0.3), "color": Color(0.28, 0.25, 0.22)},
		"dust": {"count": 1, "size": Vector2(0.05, 0.1), "life": Vector2(0.3, 0.6), "opacity": 0.08, "rise": 0.02, "color": Color(0.4, 0.38, 0.35)},
	},
	"plastic": {
		"debris": {"mesh": "flake", "count": Vector2i(4, 8), "size": Vector2(0.008, 0.032), "speed": Vector2(1.5, 4.0), "life": Vector2(0.6, 1.2), "spread": 48.0, "drag": 0.8, "bounce": 0.45, "aim": Vector2(1.0, 0.5), "color": Color(0.24, 0.25, 0.27)},
	},
	"flesh": {
		"debris": {"mesh": "drop", "count": Vector2i(10, 18), "size": Vector2(0.004, 0.013), "speed": Vector2(1.4, 4.8), "life": Vector2(0.3, 0.6), "spread": 24.0, "drag": 0.8, "bounce": 0.0, "color": Color(0.26, 0.016, 0.012)},
		"dust": {"count": 5, "size": Vector2(0.09, 0.26), "life": Vector2(0.35, 0.6), "opacity": 0.4, "rise": -0.15, "color": Color(0.26, 0.016, 0.012)},
	},
	"snow": {
		"debris": {"mesh": "chip", "count": Vector2i(5, 9), "size": Vector2(0.01, 0.032), "speed": Vector2(0.8, 2.8), "life": Vector2(0.6, 1.0), "spread": 55.0, "drag": 1.4, "bounce": 0.0, "aim": Vector2(1.0, 0.35), "color": Color(0.82, 0.87, 0.9)},
		"spray": {"count": Vector2i(8, 12), "size": Vector2(0.04, 0.08), "speed": Vector2(3.0, 7.0), "life": Vector2(0.3, 0.6), "spread": 22.0, "drag": 4.0, "gravity": 0.5, "stretch": 0.03, "aim": Vector2(1.0, 0.35), "color": Color(0.9, 0.93, 0.95, 0.6)},
		"dust": {"count": 4, "size": Vector2(0.15, 0.35), "life": Vector2(0.8, 1.4), "opacity": 0.25, "rise": 0.02, "color": Color(0.85, 0.88, 0.9)},
	},
	# Грунт: веер земли столбом вверх и чуть по ходу пули, комья падают обратно; по траве ещё
	# взлетают травинки и пятно травы вокруг ложится.
	"grass": {
		"debris": {"mesh": "clod", "count": Vector2i(6, 10), "size": Vector2(0.012, 0.04), "speed": Vector2(1.5, 4.5), "life": Vector2(0.9, 1.6), "spread": 28.0, "drag": 0.5, "bounce": 0.12, "aim": Vector2(1.0, 0.35), "color": Color(0.3, 0.24, 0.17), "alt": Color(0.22, 0.17, 0.12), "alt_share": 0.4},
		"bits": {"mesh": "blade", "count": Vector2i(16, 26), "size": Vector2(0.06, 0.15), "speed": Vector2(2.0, 5.5), "life": Vector2(1.5, 2.6), "spread": 45.0, "drag": 2.6, "bounce": 0.0, "flutter": 5.0, "aim": Vector2(1.0, 0.3), "color": Color(0.42, 0.52, 0.22), "alt": Color(0.62, 0.58, 0.36), "alt_share": 0.35},
		"spray": {"count": Vector2i(14, 22), "size": Vector2(0.05, 0.1), "speed": Vector2(3.5, 7.5), "life": Vector2(0.4, 0.8), "spread": 18.0, "drag": 3.0, "gravity": 1.0, "stretch": 0.04, "aim": Vector2(1.0, 0.35), "color": Color(0.32, 0.27, 0.2, 0.85)},
		"dust": {"count": 4, "size": Vector2(0.2, 0.5), "life": Vector2(1.0, 1.8), "opacity": 0.2, "rise": 0.05, "color": Color(0.45, 0.4, 0.32)},
		"trample": 0.3,
	},
	"dirt": {
		"debris": {"mesh": "clod", "count": Vector2i(8, 13), "size": Vector2(0.012, 0.045), "speed": Vector2(1.5, 5.0), "life": Vector2(0.9, 1.6), "spread": 30.0, "drag": 0.5, "bounce": 0.15, "aim": Vector2(1.0, 0.35), "color": Color(0.42, 0.34, 0.24), "alt": Color(0.33, 0.26, 0.18), "alt_share": 0.4},
		"bits": {"mesh": "chip", "count": Vector2i(12, 20), "size": Vector2(0.003, 0.009), "speed": Vector2(3.0, 8.0), "life": Vector2(0.5, 1.0), "spread": 36.0, "drag": 1.4, "bounce": 0.1, "aim": Vector2(1.0, 0.35), "color": Color(0.45, 0.37, 0.27)},
		"spray": {"count": Vector2i(16, 24), "size": Vector2(0.05, 0.11), "speed": Vector2(3.5, 8.0), "life": Vector2(0.45, 0.85), "spread": 18.0, "drag": 3.0, "gravity": 1.0, "stretch": 0.04, "aim": Vector2(1.0, 0.35), "color": Color(0.45, 0.37, 0.27, 0.85)},
		"dust": {"count": 6, "size": Vector2(0.25, 0.6), "life": Vector2(1.4, 2.4), "opacity": 0.24, "rise": 0.05, "color": Color(0.46, 0.39, 0.3)},
	},
	# Грязь мокрая: комья липнут (без отскока), брызги тяжёлые, пыли почти нет.
	"mud": {
		"debris": {"mesh": "clod", "count": Vector2i(7, 12), "size": Vector2(0.012, 0.04), "speed": Vector2(1.2, 4.0), "life": Vector2(0.7, 1.2), "spread": 30.0, "drag": 0.4, "bounce": 0.0, "aim": Vector2(1.0, 0.35), "color": Color(0.2, 0.16, 0.11), "alt": Color(0.16, 0.13, 0.09), "alt_share": 0.5},
		"spray": {"count": Vector2i(10, 16), "size": Vector2(0.03, 0.06), "speed": Vector2(3.0, 6.5), "life": Vector2(0.35, 0.6), "spread": 20.0, "drag": 2.0, "gravity": 1.0, "stretch": 0.03, "size_end": 1.2, "aim": Vector2(1.0, 0.35), "color": Color(0.22, 0.18, 0.13, 0.85)},
		"dust": {"count": 1, "size": Vector2(0.15, 0.3), "life": Vector2(0.5, 0.9), "opacity": 0.08, "rise": 0.02, "color": Color(0.4, 0.36, 0.3)},
	},
	"gravel": {
		"debris": {"mesh": "pebble", "count": Vector2i(8, 14), "size": Vector2(0.006, 0.025), "speed": Vector2(2.0, 5.5), "life": Vector2(0.8, 1.5), "spread": 42.0, "drag": 0.3, "bounce": 0.45, "aim": Vector2(1.0, 0.45), "color": Color(0.5, 0.49, 0.46), "alt": Color(0.38, 0.36, 0.33), "alt_share": 0.4},
		"bits": {"mesh": "chip", "count": Vector2i(10, 16), "size": Vector2(0.002, 0.006), "speed": Vector2(3.0, 8.0), "life": Vector2(0.4, 0.8), "spread": 40.0, "drag": 1.5, "bounce": 0.3, "aim": Vector2(1.0, 0.5), "color": Color(0.55, 0.53, 0.5)},
		"spray": {"count": Vector2i(8, 12), "size": Vector2(0.03, 0.06), "speed": Vector2(4.0, 10.0), "life": Vector2(0.25, 0.5), "spread": 22.0, "drag": 5.0, "gravity": 0.3, "stretch": 0.035, "aim": Vector2(1.0, 0.45), "color": Color(0.6, 0.57, 0.52, 0.5)},
		"dust": {"count": 4, "size": Vector2(0.18, 0.45), "life": Vector2(1.0, 1.8), "opacity": 0.2, "rise": 0.04, "color": Color(0.54, 0.51, 0.47)},
		"sparks": {"count": Vector2i(1, 3), "chance": 0.2},
	},
}
## Из чего земля района по маске DistrictTerrain (для попаданий и шагов): канал маски сильнее
## mask_min — грязь, камень, щебень или листва, иначе газон; круче rock_slope (y нормали) — камень.
const TERRAIN_SURFACE := {"mask_min": 0.5, "rock_slope": 0.62}

# --- Кровь (BloodFx): размеры в метрах, скорость м/с, время с ---
## Попадание в тело: капель drops; доля exit_share летит по ходу пули (конус exit_spread°, скорость
## exit_speed), остальные — назад к стрелку (back_spread°, back_speed, мельче). gush — тяжёлые капли
## почти вниз (gush_speed, gush_size). drop_size — радиус капли. Полёт: gravity, drag (сопротивление
## воздуха, доля скорости за с), не дольше drop_life; в кадре капля крупнее в drop_visual_k раз и
## вытянута по скорости (stretch_k на м/с); одновременно — не больше max_drops.
## След: капля мельче splat_min_drop следа не оставляет (морось); сторона следа = радиус × splat_k ×
## (1 + скорость/10), в пределах splat_size, проекция не глубже splat_depth (не красить обувь); вскользь — вытянут, не больше max_elong; следов — max_splats
## (Decal движка: с выбоинами ImpactFx их не больше ~512 в кадре). Крупнее drip_min_drop на стене —
## с вероятностью drip_chance подтёк: ширина drip_width, растекается за drip_grow_sec, проекция drip_depth.
## Рана капает ещё bleed_sec, по капле раз в drip_every; таких ран — max_bleeders.
## Лужи (коробки с шейдером, вместе с подтёками — max_boxes, видны до draw_m): под убитым — сторона
## pool_dead, растекается за pool_dead_sec; под раненым — pool_down, pool_down_sec; проекция pool_depth;
## уклон — круче slope_cos (косинус) — течёт языком вниз. Лежащих проверяем раз в scan_sec; лужа — когда
## тело улеглось (settle_dead / settle_down) — под костью body_bone; утащили дальше drag_m — мазок
## следами через smear_step и новая лужа. Сохнет за dry_sec: wet → dried (цвет следов-Decal).
## Рана ближе mist_skip_m к камере (попали в себя) — без облачка мороси.
const BLOOD := {
	"drops": Vector2i(12, 20), "exit_share": 0.72, "exit_spread": 24.0, "back_spread": 40.0,
	"exit_speed": Vector2(2.2, 6.5), "back_speed": Vector2(0.8, 2.6), "drop_size": Vector2(0.0012, 0.0065),
	"gush": Vector2i(2, 4), "gush_speed": Vector2(0.6, 1.8), "gush_size": Vector2(0.005, 0.01),
	"gravity": 9.81, "drag": 0.35, "drop_life": 3.0, "max_drops": 192, "drop_visual_k": 2.8, "stretch_k": 0.18,
	"splat_min_drop": 0.0022, "splat_k": 26.0, "splat_size": Vector2(0.05, 0.42), "splat_depth": 0.12, "max_elong": 3.5, "max_splats": 300,
	"drip_min_drop": 0.004, "drip_chance": 0.6, "drip_width": Vector2(0.3, 0.55), "drip_grow_sec": Vector2(6.0, 16.0), "drip_depth": 0.16,
	"bleed_sec": Vector2(1.5, 4.0), "drip_every": Vector2(0.12, 0.45), "max_bleeders": 24,
	"pool_dead": Vector2(1.5, 2.3), "pool_dead_sec": Vector2(50.0, 90.0), "pool_down": Vector2(1.0, 1.5), "pool_down_sec": Vector2(70.0, 110.0),
	"pool_depth": 0.36, "slope_cos": 0.985, "max_boxes": 64, "draw_m": 90.0,
	"scan_sec": 0.4, "settle_dead": 1.6, "settle_down": 0.8, "body_bone": "mixamorig_Spine", "drag_m": 0.6, "smear_step": 0.22,
	"dry_sec": 420.0, "wet": Color(0.3, 0.012, 0.01, 0.96), "dried": Color(0.12, 0.045, 0.032, 0.93),
	"mist_skip_m": 0.6,
}

# --- Трава (DistrictGrass, GrassBlades, GrassTrample): размеры в метрах, время в секундах ---
## Густой нижний ярус: куртина patch×patch м, травинок в ней blades_near (ближнее кольцо, segments_near
## звеньев) и blades_far (дальнее: реже, шире в far_width_k раз, segments_far звеньев); variants раскладок.
## height — высота травинок в куртине; height_k — множитель куртины по пятнам (шум): низко — высоко;
## thatch — доля полёглых сухих травинок (прошлогодний «войлок» у земли).
## Густота куртин — по плотности карты (R + G/2): от lawn_from (нет) до lawn_full (сплошь).
## cell — клетка яруса; max_tilt — круче этого (косинус) куртина наклоняется только наполовину.
## quality — по качеству графики: near/far — радиусы ближнего и дальнего колец, density — доля куртин,
## scan — радиус пучков-сканов, scan_density — их доля; fade_m — у края травинки уходят в землю;
## lod_margin — ширина растворения между кольцами.
## Ветер: wind — направление (x, z), сила (1 — обычный), скорость волн; в дождь сила ×wind_rain_k.
## Примятие: окно trample_extent м вокруг камеры, trample_res клеток, обновление trample_hz раз в с;
## поднимается за trample_recover_sec; радиусы — стоя, присев, лёжа, у кости тела (body),
## взрыв — радиус гранаты × blast_k; body_bones — кости модели лежащего, которыми он мнёт траву.
const GRASS := {
	"patch": 0.6, "blades_near": 80, "segments_near": 4, "blades_far": 24, "segments_far": 2,
	"far_width_k": 2.1, "variants": 4, "thatch": 0.2,
	"height": Vector2(0.16, 0.44), "height_k": Vector2(0.8, 1.3),
	"lawn_from": 0.02, "lawn_full": 0.22, "cell": 8.0, "max_tilt": 0.8,
	"quality": {
		"low": {"near": 5.0, "far": 11.0, "density": 0.55, "scan": 16.0, "scan_density": 0.25},
		"medium": {"near": 7.0, "far": 19.0, "density": 0.8, "scan": 22.0, "scan_density": 0.35},
		"high": {"near": 9.0, "far": 26.0, "density": 1.0, "scan": 26.0, "scan_density": 0.45},
	},
	"fade_m": 6.0, "lod_margin": 2.0,
	"wind": Vector4(0.89, 0.45, 1.0, 1.0), "wind_rain_k": 1.7,
	"trample_extent": 48.0, "trample_res": 128, "trample_hz": 30.0, "trample_recover_sec": 9.0,
	"trample_radius": {"stand": 0.36, "crouch": 0.44, "prone": 0.62, "body": 0.3, "blast_k": 0.8},
	"body_bones": ["mixamorig_Hips", "mixamorig_Spine2", "mixamorig_Head", "mixamorig_LeftLeg", "mixamorig_RightLeg", "mixamorig_LeftFoot", "mixamorig_RightFoot"],
}

# --- Игрок: движение по стойкам, м/с ---
## Шаг медленнее на 30 % (2.6 → 1.82), бег прежний — решение владельца 2026-10-08.
const PLAYER_WALK_SPEED := 1.82
const PLAYER_SPRINT_SPEED := 5.2
const PLAYER_CROUCH_SPEED := 1.4
const PLAYER_PRONE_SPEED := 0.6
const PLAYER_ADS_SPEED_SCALE := 0.55
## Ускорение/торможение, м/с²: шаг набирается примерно за 0.25 с; отпустил клавиши — шаг гаснет
## за ~0.11 с, бег — за ~0.33 с (инерция остановки вдвое меньше прежней, 2026-10-08).
const PLAYER_ACCEL := 7.5
const PLAYER_DECEL := 16.0
## Поворот корпуса к курсору, рад/с.
const PLAYER_TURN_SPEED := 12.0

## Визуальный выбор клипа по реальному перемещению; физику персонажа не меняет. Скорость для
## выбора сглажена за speed_smooth_sec, с (иначе на мониторе 144+ клип скачет каждый кадр);
## с автоматом от sprint_from, м/с, — спринт (бег игрока 5.2, сглаженная скорость к ней снизу).
## Модель опущена под стойку, м: присед на месте, ходьба вприсядку (у клипа таз выше), лёжа.
## Дальние персонажи (мародёры, чужие отряды, напарники): дальше shadows_m от камеры не отбрасывают
## тень, дальше hide_m не рисуются (ИИ и звук работают как прежде); дальше ik_m руки не подгоняются к
## оружию и стенам, дальше anim_m[0] клип считается через кадр, дальше anim_m[1] — раз в четыре кадра;
## every — как часто проверять, с; hysteresis — запас в метрах на возврат, чтобы тень не мигала.
const CHARACTER_LOD := {"shadows_m": 55.0, "hide_m": 320.0, "ik_m": 35.0, "anim_m": [45.0, 100.0], "every": 0.4, "hysteresis": 6.0}
const CHARACTER_ANIM := {"move_min": 0.12, "run_from": 3.1, "sprint_from": 4.8, "blend_sec": 0.16, "prone_hold_sec": 1.0, "prone_aim_hold_sec": 0.3, "hurt_below": 0.35, "support_blend_sec": 0.15, "speed_smooth_sec": 0.1}

# --- Капсула по стойкам: высота, м ---
const STANCE_HEIGHT := {"stand": 1.8, "crouch": 1.2, "prone": 0.5}
const CAPSULE_RADIUS := 0.35

# --- Камера ---
## Наклон изометрии от горизонта (Duckov ≈ 55–60°: видно планировку, а не стены).
const CAMERA_PITCH_DEG := 58.0
const CAMERA_YAW_DEG := 45.0
const CAMERA_DISTANCE := 28.0
const CAMERA_FOV := 32.0
const CAMERA_ZOOM_MIN := 12.0
const CAMERA_ZOOM_MAX := 50.0
const CAMERA_ZOOM_STEP := 2.0
## Камера смещается к курсору: доля расстояния до курсора и предел, м.
const CAMERA_CURSOR_LEAD := 0.28
const CAMERA_CURSOR_LEAD_MAX := 5.0
const CAMERA_FOLLOW_SMOOTH := 8.0
## Скорость вращения камеры по Q/E, град/с.
const CAMERA_TURN_DEG_PER_SEC := 90.0
## Вырез стен у камеры: доли дистанции камеры, ближе near — стена невидима, дальше far — целая.
## Пол на дистанции ~0.85 (высота камеры), стена под камерой ~0.6 — попадает в вырез, игрок (1.0) — нет.
const CAMERA_CUTAWAY_NEAR := 0.62
const CAMERA_CUTAWAY_FAR := 0.96
## Перекрытие (этаж паркинга, крыша навеса) выше ног игрока больше чем на это — прячется, м.
const DECK_HIDE_ABOVE := 1.9
## Взаимодействие (F): ключ, рубильник — ближе этого к предмету, м.
const INTERACT_RADIUS := 1.8
## Несколько точек взаимодействия в досягаемости — берётся та, что на экране ближе этого к курсору, px.
const INTERACT_CURSOR_PICK_PX := 70.0
## Зона эвакуации по высоте от точки (паркинг многоуровневый — не засчитывать этаж выше), м.
const EXTRACT_ZONE_HEIGHT := 2.5
## Эвакуация группой: кто-то встал в открытую зону — общий отсчёт, с. Кончился — кто в зоне, уходит
## со всем; живые не в зоне — в убежище без добычи. Все живые уже в зонах — короткий отсчёт точки.
const EXTRACT_GROUP_SEC := 180.0
## Щелчок рубильника слышно далеко — мародёры идут проверить, м.
const NOISE_SWITCH := 35.0
## Без рюкзака — карманы и руки: сетка CARRY_GRID (20 ячеек). Рюкзак (слот «Рюкзак»,
## data/items.json, cat backpack) даёт свою сетку equip.grid: 30 / 45 / 60 ячеек.
const CARRY_GRID := Vector2i(5, 4)
## Обычный рюкзак (30 ячеек): с ним начинают новый профиль и его получают старые сохранения.
const BACKPACK_GRID := Vector2i(6, 5)
const BACKPACK_START := "bp_daypack"
## Стопки мелочи (предметы 1×1 без состояния и не надеваемые): сколько штук в одной ячейке —
## не меньше этого (в данных может быть больше, как у патронов). Расходники и ценная мелочь
## (категории STACK_BIG_CATS: бинты, еда, гранаты, ювелирка, часы…) — по STACK_BIG, остальное — по STACK_SMALL.
const STACK_SMALL := 5
const STACK_BIG := 10
const STACK_BIG_CATS := ["med", "food", "value", "barter", "throw"]
## Обыск тела / выброшенного, с (у контейнеров на пропсах — data/loot.json).
const SEARCH_BODY_SEC := 2.0
## Контейнер на пропе — на этой высоте над полом (к ней меряется дальность «F»), м.
const LOOT_POINT_HEIGHT := 0.6

# --- Убежище и торговец ---
## Тайник: вместимость в ячейках.
const STASH_CELLS := 300
## Сетка тайника, ш × в (ячеек — STASH_CELLS).
const STASH_GRID := Vector2i(10, 30)
## Новый профиль: деньги и что лежит в тайнике ([id, штук]).
const START_MONEY := 60000
const START_STASH := [["wpn_hg_02", 1], ["wpn_ar_01", 1], ["ammo_919_fmj", 100], ["ammo_545_std", 120],
	["mag_545_30", 1], ["mag_919_17", 1], ["bandage", 4], ["painkillers", 2], ["vest_police", 1], ["helmet_military_old", 1], ["grenade", 2]]
## Выручка Михалыча: остался без огнестрела и без денег на самый дешёвый ствол — бесплатный
## набор, чтобы было с чем идти в рейд (сколько угодно раз, пока снова не встанешь на ноги).
const RESCUE_KIT := [["wpn_hg_01", 1], ["ammo_918_pst", 48], ["bandage", 2]]
## Готовые комплекты у Михалыча (правая колонка окна): полный набор одной кнопкой — стволы с обвесом,
## броня с плитами, разгрузка, шлем, гарнитура, рюкзак, в рюкзаке магазины, патроны, медицина, гранаты
## (снаряжённые магазины на входе в рейд сами переезжают в пустые подсумки — Inventory.prepare_mags). Формат —
## как у своих шаблонов (LoadoutTemplates): что есть в тайнике — берётся оттуда, остальное докупается.
## По одному на ступень снабжения: каталог 1, 2, 3 и 5.
const TRADER_KITS := [
	{"name": "Дворовый", "about": "Ружьё и ПМ, самодельный жилет. С чем выходят в первый рейд.",
		"slots": {
			"primary": {"id": "wpn_sg_03", "mods": {"optic_primary": "optic_rd_01"}},
			"secondary": {"id": "wpn_hg_01"},
			"armor": {"id": "vest_homemade"},
			"rig": {"id": "rig_belt"},
			"helmet": {"id": "helmet_military_old"},
			"ears": {"id": "headset_passive"},
			"backpack": {"id": "bp_daypack"}},
		"backpack": [["ammo_12_buck", 30], ["ammo_12_slug", 10], ["mag_918_8", 2], ["ammo_918_pst", 32], ["bandage", 3], ["medkit", 1], ["water", 1]]},
	{"name": "Патрульный", "about": "ВЕРАС-54 с коллиматором и Glock, плитоносец со стальными плитами.",
		"slots": {
			"primary": {"id": "wpn_ar_01", "mods": {"optic_primary": "optic_holo_01", "muzzle": "muzzle_comp_545_01", "underbarrel": "grip_vertical_01", "side_right": "tac_flashlight_01"}},
			"secondary": {"id": "wpn_hg_02"},
			"armor": {"id": "carrier_simple", "plates": {"front": "plate_steel", "back": "plate_steel"}},
			"rig": {"id": "rig_chest"},
			"helmet": {"id": "helmet_police"},
			"ears": {"id": "headset_active"},
			"backpack": {"id": "bp_tourist"}},
		"backpack": [["mag_545_30", 4], ["ammo_545_std", 150], ["mag_919_17", 2], ["ammo_919_fmj", 51], ["bandage", 4], ["medkit", 2], ["painkillers", 1], ["grenade", 2]]},
	{"name": "Штурмовик", "about": "M4A1 с оптикой 4× и глушителем, керамика, ПНВ. Для ночи и тесных коридоров.",
		"slots": {
			"primary": {"id": "wpn_ar_02", "mods": {"optic_primary": "optic_4x_01", "muzzle": "muzzle_supp_556_01", "underbarrel": "grip_angled_01", "side_right": "tac_combo_01"}},
			"secondary": {"id": "wpn_hg_02", "mods": {"optic_primary": "optic_rmr_01", "underbarrel": "tac_flashlight_01"}},
			"armor": {"id": "carrier_tactical", "plates": {"front": "plate_ceramic", "back": "plate_ceramic"}},
			"rig": {"id": "rig_assault"},
			"helmet": {"id": "helmet_army"},
			"ears": {"id": "headset_tactical"},
			"eyes": {"id": "nvg"},
			"backpack": {"id": "bp_raid"}},
		"backpack": [["mag_556_30", 5], ["ammo_556_std", 180], ["mag_919_17", 2], ["ammo_919_ap", 51], ["bandage", 4], ["medkit", 2], ["painkillers", 2], ["grenade", 3], ["flare", 1]]},
	{"name": "Снайпер", "about": "MR762 с оптикой 8×, глушителем и сошками, Vector на ближний бой, лучшая броня.",
		"slots": {
			"primary": {"id": "wpn_dmr_01", "mods": {"optic_primary": "optic_8x_01", "muzzle": "muzzle_supp_762_01", "underbarrel": "bipod_01"}},
			"secondary": {"id": "wpn_smg_03", "mods": {"optic_primary": "optic_holo_01", "underbarrel": "grip_angled_01"}},
			"armor": {"id": "carrier_tactical", "plates": {"front": "plate_military", "back": "plate_military"}},
			"rig": {"id": "rig_heavy"},
			"helmet": {"id": "helmet_tactical"},
			"ears": {"id": "headset_tactical"},
			"eyes": {"id": "nvg"},
			"backpack": {"id": "bp_raid"}},
		"backpack": [["mag_76251_20", 4], ["ammo_76251_match", 100], ["mag_45_vector30", 2], ["ammo_45_ap", 90], ["bandage", 4], ["medkit", 3], ["painkillers", 2], ["grenade", 2], ["flare", 1]]},
]
## Покупка: согласованная экономика v0, все каталоги и тестовый магазин.
## Штатные магазины и медицина доступны; преимущество стволов и обвеса дорогое.
## Упаковки стоят как содержимое; отсутствие цены запрещает покупку.
const TRADER_BUY_PRICES := {
	"alternator_rebuild": 19000,
	"ammo_12_apslug": 1300,
	"ammo_12_buck": 100,
	"ammo_12_hbuck": 150,
	"ammo_12_slug": 190,
	"ammo_300_sub": 410,
	"ammo_300_sup": 310,
	"ammo_338_ap": 5500,
	"ammo_338_match": 1300,
	"ammo_45_ap": 890,
	"ammo_45_fmj": 120,
	"ammo_45_jhp": 170,
	"ammo_50_api": 11000,
	"ammo_50_ball": 2800,
	"ammo_545_ap": 960,
	"ammo_545_old": 80,
	"ammo_545_std": 120,
	"ammo_556_ap": 1300,
	"ammo_556_civ": 120,
	"ammo_556_std": 150,
	"ammo_57_ap": 1300,
	"ammo_57_std": 190,
	"ammo_68_ap": 3100,
	"ammo_68_std": 640,
	"ammo_76251_ap": 2400,
	"ammo_76251_match": 520,
	"ammo_76251_std": 360,
	"ammo_76254_ap": 2100,
	"ammo_76254_std": 280,
	"ammo_918_ap": 350,
	"ammo_918_pst": 50,
	"ammo_919_ap": 590,
	"ammo_919_exp": 90,
	"ammo_919_fmj": 80,
	"ammo_921_ap": 1200,
	"ammo_921_std": 190,
	"ammo_939_sp5": 410,
	"ammo_939_sp6": 2100,
	"anesthetic_pack": 16000,
	"antibiotics_pack": 13000,
	"antiseptic_pack": 6200,
	"auto_lubricant": 2900,
	"bandage": 600,
	"battery": 3900,
	"bearing_set": 12000,
	"bench_vice": 4700,
	"binoculars": 11000,
	"bipod_01": 40000,
	"bp_daypack": 12000,
	"bp_raid": 180000,
	"bp_tourist": 35000,
	"brake_service_kit": 11000,
	"camera": 12000,
	"canned": 560,
	"car_ecu": 25000,
	"car_rim": 7200,
	"car_tire": 9800,
	"carrier_perimeter_assault": 500000,
	"carrier_perimeter_std": 400000,
	"carrier_simple": 20000,
	"carrier_tactical": 77000,
	"cash": 6500,
	"cassette_player": 4200,
	"cctv_bullet": 19000,
	"cctv_dome": 23000,
	"chemlight": 340,
	"cigarettes": 910,
	"circuit_board": 14000,
	"coffee_pack": 7300,
	"cpu_cooling_kit": 24000,
	"cpu_desktop": 36000,
	"cpu_server": 81000,
	"dental_kit": 20000,
	"desk_lamp": 3400,
	"diagnostic_kit": 17000,
	"diamond_ring": 52000,
	"empty_jerrycan": 2900,
	"energy_bar": 280,
	"engraver_controller": 7800,
	"engraver_frame": 11000,
	"flare": 1800,
	"food_beans": 2000,
	"food_milk": 1800,
	"food_sardines": 2500,
	"food_tomatoes": 1500,
	"freeze_dried_meals": 5000,
	"gold_chain": 20000,
	"gpu": 33000,
	"gpu_compute": 120000,
	"gpu_gaming": 70000,
	"grenade": 10000,
	"grip_angled_01": 35000,
	"grip_compact_01": 17000,
	"grip_handstop_01": 10000,
	"grip_heavy_01": 31000,
	"grip_offset_01": 40000,
	"grip_vertical_01": 20000,
	"hammer": 1400,
	"headphones": 4600,
	"headset_active": 30000,
	"headset_passive": 3900,
	"headset_perimeter": 200000,
	"headset_tactical": 92000,
	"helmet_army": 92000,
	"helmet_hardhat": 2600,
	"helmet_military_old": 12000,
	"helmet_perimeter_combat": 240000,
	"helmet_perimeter_heavy": 350000,
	"helmet_police": 25000,
	"helmet_tactical": 152000,
	"hemostat_kit": 12000,
	"hemostatic_pack": 20000,
	"injector_set": 32000,
	"ink_set": 3400,
	"insulin_pack": 25000,
	"intubation_kit": 24000,
	"iv_solution_pack": 9500,
	"junction_box": 3600,
	"kettle": 3100,
	"laptop": 23000,
	"laptop_business": 49000,
	"laptop_workstation": 99000,
	"laser_head": 60000,
	"laser_rangefinder": 21000,
	"lighter": 260,
	"mag_300_30": 3000,
	"mag_338_awm5": 8000,
	"mag_45_ump25": 2500,
	"mag_45_usp12": 1800,
	"mag_45_vector13": 1800,
	"mag_45_vector30": 5000,
	"mag_50_m82_10": 15000,
	"mag_545_30": 2000,
	"mag_545_45": 3500,
	"mag_545_60": 5500,
	"mag_556_20": 2000,
	"mag_556_30": 2500,
	"mag_556_40": 4500,
	"mag_556_60": 10000,
	"mag_57_p90_50": 5000,
	"mag_68_spear20": 8000,
	"mag_76251_10": 3500,
	"mag_76251_20": 5500,
	"mag_918_8": 800,
	"mag_919_17": 1500,
	"mag_919_33": 4000,
	"mag_919_vityaz30": 2000,
	"mag_921_sr2_20": 2500,
	"mag_921_sr2_30": 3500,
	"mag_939_10": 3500,
	"mag_939_20": 5000,
	"mag_loader": 35000,
	"mag_m249_100": 5000,
	"mag_m249_200": 12000,
	"mag_pkm_100": 6000,
	"mag_pkm_200": 16000,
	"mag_s12_20": 20000,
	"mag_s12_8": 3500,
	"measuring_tape": 1200,
	"medical_case": 2100,
	"medkit": 3000,
	"metal_toolbox": 3600,
	"microscope_digital": 75000,
	"microscope_optical": 47000,
	"motherboard_server": 37000,
	"mount_adjustable_01": 47000,
	"mount_offset45_01": 20000,
	"mount_rail_ext_01": 10000,
	"mount_riser_01": 8500,
	"multimeter": 10000,
	"muzzle_brake_338_01": 218000,
	"muzzle_brake_68_01": 146000,
	"muzzle_brake_762_01": 35000,
	"muzzle_comp_545_01": 30000,
	"muzzle_comp_556_01": 35000,
	"muzzle_comp_9_01": 29000,
	"muzzle_fh_545_01": 10000,
	"muzzle_fh_556_01": 12000,
	"muzzle_supp_12_01": 157000,
	"muzzle_supp_300_01": 291000,
	"muzzle_supp_338_01": 819000,
	"muzzle_supp_45_01": 157000,
	"muzzle_supp_545_01": 172000,
	"muzzle_supp_556_01": 186000,
	"muzzle_supp_57_01": 237000,
	"muzzle_supp_68_01": 592000,
	"muzzle_supp_762_01": 273000,
	"muzzle_supp_9_01": 129000,
	"muzzle_supp_pm_01": 100000,
	"nvg": 300000,
	"nvg_tube": 114000,
	"oil_tin": 1800,
	"optic_12x_01": 650000,
	"optic_2x_01": 80000,
	"optic_4x_01": 150000,
	"optic_8x_01": 450000,
	"optic_holo_01": 80000,
	"optic_lpvo_01": 350000,
	"optic_offset_rd_01": 85000,
	"optic_pso_01": 100000,
	"optic_rd_01": 30000,
	"optic_rd_dt_01": 28000,
	"optic_rmr_01": 55000,
	"orthopedic_kit": 27000,
	"oscilloscope_portable": 44000,
	"pack_12_buck": 2000,
	"pack_45_fmj": 3600,
	"pack_545_ap": 38400,
	"pack_545_std": 7200,
	"pack_556_ap": 52000,
	"pack_556_std": 9000,
	"pack_57_ap": 52000,
	"pack_76251_std": 14400,
	"pack_918_ap": 11200,
	"pack_918_pst": 2000,
	"pack_919_ap": 17700,
	"pack_919_fmj": 4000,
	"pack_921_ap": 36000,
	"pack_939_sp5": 16400,
	"pack_939_sp6": 63000,
	"pack_chemlights": 2040,
	"pack_flares": 7200,
	"pack_frag": 30000,
	"painkillers": 1200,
	"part_glock_barrel": 16000,
	"part_glock_extractor": 5900,
	"part_glock_recoil": 8500,
	"part_glock_slide": 30000,
	"part_glock_trigger": 14000,
	"part_pm_barrel": 8500,
	"part_pm_hammer": 5500,
	"part_pm_safety": 3500,
	"part_pm_slide": 15000,
	"part_pm_trigger": 3900,
	"part_veras_mag_body": 5100,
	"part_veras_muzzle": 6800,
	"part_veras_receiver": 25000,
	"part_veras_stock": 9800,
	"perfume": 3900,
	"phone": 7800,
	"photo_camera_pro": 88000,
	"pipe_wrench": 2500,
	"plate_ceramic": 127000,
	"plate_composite": 84000,
	"plate_military": 233000,
	"plate_perimeter": 350000,
	"plate_steel": 35000,
	"plate_steel_homemade": 9100,
	"pliers": 1600,
	"power_unit": 8300,
	"powerbank": 3300,
	"precision_oiler": 3600,
	"printer_board": 7800,
	"printer_body": 18000,
	"printer_head": 9800,
	"protein_pack": 5400,
	"radio_transceiver": 18000,
	"ram_desktop": 9800,
	"ram_server": 25000,
	"ratchet_socket": 5900,
	"ration_arctic": 9500,
	"ration_daily": 7300,
	"ration_emergency": 5800,
	"ration_patrol": 4700,
	"rig_assault": 75000,
	"rig_belt": 4500,
	"rig_chest": 20000,
	"rig_heavy": 180000,
	"router_industrial": 28000,
	"satellite_modem": 62000,
	"scalpel_kit": 14000,
	"screwdriver": 910,
	"server_drive": 26000,
	"signal_launcher": 150000,
	"smartphone_business": 29000,
	"spray_paint": 1400,
	"ssd_nvme": 31000,
	"ssd_sata": 16000,
	"stencil_kit": 4200,
	"sterile_dressing_kit": 7300,
	"sticker_film": 1200,
	"sticker_perimeter": 12000,
	"sticker_shark": 4600,
	"sticker_skull": 2300,
	"sticker_tally": 2000,
	"stock_fixed_heavy_ak": 14000,
	"stock_fixed_light_ak": 20000,
	"stock_fold_ak_01": 27000,
	"stock_perimeter_01": 200000,
	"stock_tele_ak_01": 53000,
	"stock_tele_ar_01": 49000,
	"sunglasses": 3300,
	"supply_signal": 450000,
	"surgical_tape": 1800,
	"suture_kit": 9500,
	"switch_managed": 34000,
	"tac_combo_01": 126000,
	"tac_flashlight_01": 15000,
	"tac_flashlight_hp_01": 80000,
	"tac_laser_01": 35000,
	"thermal_imager": 101000,
	"thermos": 2200,
	"timing_kit": 16000,
	"tire_pump": 5500,
	"toolset": 7800,
	"vest_army": 134000,
	"vest_homemade": 7800,
	"vest_old": 26000,
	"vest_police": 32000,
	"video_camera": 15000,
	"wall_clock": 2300,
	"watch": 16000,
	"water": 340,
	"water_purification": 6200,
	"weapon_cleaning_kit": 11000,
	"weapon_gauges": 19000,
	"wires": 1000,
	"work_gloves": 650,
	"wpn_ar_01": 180000,
	"wpn_ar_02": 300000,
	"wpn_ar_03": 500000,
	"wpn_ar_04": 550000,
	"wpn_ar_05": 1100000,
	"wpn_dmr_01": 850000,
	"wpn_dmr_02": 600000,
	"wpn_hg_01": 10000,
	"wpn_hg_02": 60000,
	"wpn_hg_03": 85000,
	"wpn_lmg_01": 1150000,
	"wpn_lmg_02": 1250000,
	"wpn_sg_01": 250000,
	"wpn_sg_02": 145000,
	"wpn_sg_03": 35000,
	"wpn_smg_01": 120000,
	"wpn_smg_02": 290000,
	"wpn_smg_03": 450000,
	"wpn_smg_04": 95000,
	"wpn_smg_05": 220000,
	"wpn_sp_01": 620000,
	"wpn_sp_02": 700000,
	"wpn_sr_01": 1350000,
	"wpn_sr_02": 2100000,
}
## Явная цена продажи единицы: переоценены магазины и базовая медицина.
## Остальные находки — прежняя оценка × TRADER_SELL_MULT, с износом и содержимым.
const TRADER_SELL_MULT := 0.55
const TRADER_SELL_PRICES := {
	"bandage": 270,
	"mag_300_30": 1200,
	"mag_338_awm5": 3200,
	"mag_45_ump25": 1000,
	"mag_45_usp12": 720,
	"mag_45_vector13": 720,
	"mag_45_vector30": 2000,
	"mag_50_m82_10": 6000,
	"mag_545_30": 800,
	"mag_545_45": 1400,
	"mag_545_60": 2200,
	"mag_556_20": 800,
	"mag_556_30": 1000,
	"mag_556_40": 1800,
	"mag_556_60": 4000,
	"mag_57_p90_50": 2000,
	"mag_68_spear20": 3200,
	"mag_76251_10": 1400,
	"mag_76251_20": 2200,
	"mag_918_8": 320,
	"mag_919_17": 600,
	"mag_919_33": 1600,
	"mag_919_vityaz30": 800,
	"mag_921_sr2_20": 1000,
	"mag_921_sr2_30": 1400,
	"mag_939_10": 1400,
	"mag_939_20": 2000,
	"mag_m249_100": 2000,
	"mag_m249_200": 4800,
	"mag_pkm_100": 2400,
	"mag_pkm_200": 6400,
	"mag_s12_20": 8000,
	"mag_s12_8": 1400,
	"medkit": 1350,
	"painkillers": 540,
}
## Уровень модуля → денежная часть строительства; детали и доверие — в hideout.json.
const HIDEOUT_MODULE_PRICES := {
	"workbench": {2: 180000}, "generator": {1: 100000},
	"pocket": {1: 150000, 2: 450000}, "stash": {2: 120000, 3: 300000},
	"radio": {1: 100000}, "engraver": {},
}
## Наводка на маршрут и плата за выход; текущие карты бесплатны.
const FLOOR_PRICES := {
	"f1": {"price": 0, "fee": 0}, "zone01": {"price": 0, "fee": 0},
	"f2": {"price": 200000, "fee": 0},
	"f3": {"price": 450000, "fee": 0}, "f4": {"price": 900000, "fee": 25000},
}
## Голограф ЛУМАР: сторона квадрата метки в окне, м; яркость метки под ПНВ на голове (в трубке яркая
## метка заливала всё окно); усиление и дальность собственной ИК-подсветки ночного режима окна.
const LUMAR := {"reticle_m": 0.0125, "nvg_energy": 0.1, "nv_gain": 46.0, "nv_ir_range": 55.0}
## Ник над головой напарника: высота над землёй стоя / сидя / лёжа, размер шрифта и «пикселя»; дальше
## near метров подпись растёт с расстоянием (не больше чем в grow_max раз) — читается и через двор.
const NAME_TAG := {"height": [2.1, 1.55, 0.75], "font": 40, "pixel": 0.004, "near": 12.0, "grow_max": 6.0}
## Покупка расходников: «+» у патронов прибавляет по столько (магазин); больше стольких стопок за раз не взять.
const TRADER_AMMO_STEP := 30
const TRADER_QTY_STACKS := 10
## Доверие торговца: за каждую эвакуацию и сверху — если вынес на сумму не меньше порога, ₽.
## Пороги доверия и цены маршрутов на этажи — в data/floors.json.
const TRUST_PER_EXTRACTION := 1
## Ступени доверия: ступень = очки доверия + 1, до max. Каждые catalog_every ступеней — новый
## каталог Михалыча (1, 10, 20, 30, 40); номер каталога — это и «уровень доверия» для заданий,
## модулей убежища и сюжета (Profile.trust_level).
const TRUST_STEPS := {"max": 50, "catalog_every": 10}
## Модули убежища (data/hideout.json): с какого уровня верстака ставится обвес в слот;
## сетка защищённого кармана по уровню (0 — кармана нет); строк тайника по уровню;
## сколько заданий одновременно — без рации / с рацией.
const WORKBENCH_SLOT_LEVEL := {"muzzle": 1, "underbarrel": 1, "stock": 1, "optic_primary": 2, "top_front": 2, "side_left": 2, "side_right": 2}
const POCKET_GRIDS := [Vector2i(0, 0), Vector2i(2, 2), Vector2i(3, 3)]
const STASH_ROWS := [30, 40, 50]
const MISSION_SLOTS := [1, 3]
const TRUST_BONUS := 1
const TRUST_BONUS_VALUE := 60000
## Сцены: убежище (старт игры, между рейдами) и рейд.
const MAIN_MENU_SCENE := "res://scenes/ui/main_menu.tscn"
const HIDEOUT_SCENE := "res://scenes/levels/hideout.tscn"
## ENet: обычный обрыв определяется быстро; на загрузку тяжёлой карты даём до трёх минут.
const NET_TIMEOUT := {"factor": 32, "min_ms": 5000, "max_ms": 30000, "loading_ms": 180000}
## Доля общего перехода: чтение ресурсов, подготовка сцены и её первого кадра.
const LOADING_PROGRESS: Dictionary = {"prepare": 2.0, "resources_start": 5.0, "resources_end": 65.0,
	"scene": 68.0, "geometry": 72.0, "atmosphere": 78.0, "player": 84.0,
	"equipment": 90.0, "ready": 94.0, "network": 96.0, "image": 98.0}
const RAID_SCENE := "res://scenes/levels/f1_ring.tscn"
## Камера в убежище ближе — комната тесная.
const HIDEOUT_CAMERA_DISTANCE := 20.0
## Компас вверху экрана: ширина полосы, px, и сколько градусов видно в обе стороны.
const COMPASS_WIDTH := 560.0
const COMPASS_SPAN_DEG := 75.0

# --- Свет и атмосфера ---
const SUN_ENERGY := 1.6
const SUN_ELEVATION_DEG := 34.0
const SUN_AZIMUTH_DEG := -140.0
const AMBIENT_ENERGY := 0.35
const FOG_DENSITY := 0.005

# --- Ощущение выстрела ---
## Тряска камеры от своего выстрела и от попадания по тебе (м смещения), затухание 1/с.
const SHOT_SHAKE := 0.12
const HURT_SHAKE := 0.35
## Дальние выстрелы и взрывы (Audio.play, виды с "far"): скорость звука, м/с (задержка — дальше
## delay_from_m); фильтр 3D-звука — срез верхов, Гц, и его сила, дБ (растёт с расстоянием); тон
## на пределе слышимости ×far_pitch.
const AUDIO_FAR := {"sound_mps": 343.0, "delay_from_m": 25.0, "cutoff_hz": 2200.0, "filter_db": -30.0, "far_pitch": 0.9}
## Попадание по себе (HurtFx и толчок взгляда в CameraRig): виньетка — не меньше min, + per_dmg за
## единицу урона, до max; гаснет за fade_sec, с. Взгляд дёргается на punch_deg (+ per_dmg_deg за
## урон, до punch_max_deg), возвращается за punch_sec, с. Направления нет — только звук.
const HURT_FX := {"min": 0.35, "per_dmg": 0.02, "max": 1.0, "fade_sec": 0.7,
	"punch_deg": 1.6, "per_dmg_deg": 0.06, "punch_max_deg": 4.5, "punch_sec": 0.22}
const SHAKE_DECAY := 9.0
## Отдача: подброс ствола (корпуса) вверх, рад, и возврат, 1/с.
const RECOIL_KICK := 0.12
const RECOIL_RETURN := 6.0
## При удержании ADS отдача вдвое слабее, раскачка прицела — на 90 % слабее. Внутри этой
## отдачи вертикальный подброс линии прицела (RISE) и подскок дула модели (FLIP) мягче,
## горизонтальный увод камеры заметнее, а откат модели оружия в камеру (BACK) сильнее.
## RISE поднят с 0.1275 до 0.5 (владелец, 2026-10-11: «слишком легко, мышь не нужно контролировать»):
## у ВЕРАСа линия прицела уходит вверх на ~0.27° за выстрел (из них 60 % остаётся — тянуть мышью вниз),
## магазин очередью — около 5°; раньше было 1.2° на весь магазин. Сверху ещё RECOIL_GAIN (×1.2 в прицеле).
const ADS_RECOIL_SCALE := 0.5
## Оружие убрано (повторное нажатие клавиши ствола, Player.holstered) или рук ничего не занимает: бег
## быстрее в sprint_k раз, выносливость в беге тратится в stamina_k раз (медленнее).
const HOLSTER := {"sprint_k": 1.1, "stamina_k": 0.75}
## Общая прибавка отдачи поверх всего остального (владелец, 2026-10-11: от бедра +70 %, в прицеле
## +50 %, затем в прицеле −20 % → 1.2): на эту величину растут и уход взгляда, и толчок модели в руках (назад, подброс, вбок), и
## наклон корпуса у персонажа со стороны. Разброс очередью (RECOIL_BLOOM) от неё не зависит.
const RECOIL_GAIN := {"hip": 1.7, "ads": 1.2}
const ADS_SWAY_SCALE := 0.1
const ADS_RECOIL_RISE_SCALE := 0.5
const ADS_RECOIL_FLIP_SCALE := 0.45
const ADS_RECOIL_HORIZONTAL_SCALE := 1.5
const ADS_RECOIL_BACK_SCALE := 2.25
## FPS_FOV — прежнее опорное вертикальное поле зрения, град (калибровка мыши).
## Поле зрения мира всегда из настроек (Settings.fov_h), в том числе при ADS. Оружие у
## бедра — смещение модели от глаза (вправо, вниз, вперёд), м. Близко к камере, как в Road to Vostok:
## коробка крупно справа внизу, правое предплечье уходит за край кадра (дальше — был виден срез рукава).
const FPS_FOV := 74.0
## Оптика на дальней планке (над цевьём): оружие в прицеле подтягивается к глазу, пока рукоять не
## окажется на этом расстоянии перед ним, м (0 — рукоять у самого глаза; дальше приклад прошёл бы сквозь
## голову). Прицел на обычной планке сюда не доходит (у него 0.04–0.13).
const SCOPE_ADS_Z_MIN := 0.0
const FPS_HIP_POSE := Vector3(0.09, -0.12, -0.35)
## Своё поле зрения у рук и оружия перед глазами (вертикальное, град): не зависит от настройки
## поля зрения мира — при 120° руки не съёживаются, при 50° не раздуваются (CameraRig, ViewmodelSpace).
const FPS_VIEWMODEL_FOV := 54.0
## Объём оружия и рукавов у препятствий: раннее отведение, складывание рук и возврат.
const WEAPON_CLEARANCE := {"margin": 0.012, "lead": 0.12, "hand_radius": 0.05,
	"sleeve_radius": 0.055, "retract": 0.24, "action_retract": 0.32, "ready_deg": 78.0, "lift": 0.025,
	"upper_sleeve_radius": 0.10, "high_drop": 0.25, "high_retract": 0.12, "low_drop": 0.20,
	"body_low_lift": 0.08, "view_clear": 0.025,
	"prone_retract": 0.14, "prone_hip_lift": 0.045,
	"enter_sec": 0.10, "return_sec": 0.24, "samples": 12, "refine": 4,
	"fire_threshold": 0.12, "elbow_angles": [0.0, 35.0, -35.0, 70.0, -70.0, 110.0, -110.0, 180.0],
	"shoulder_steps": 6, "shoulder_step": 0.035, "reach_margin": 0.002}
## Левая кисть ВЕРАСа (клипы из Blender) на месте хвата: запястье за рукояткой / за зажимом
## фонаря или сошек, м; дальше max_shift от позы клипа не уводим (рука не вытягивается в нитку).
const SUPPORT_GRIP := {"behind_grip": 0.055, "behind_device": 0.035, "max_shift": 0.12}
## Покачивание оружия от бедра: частота входит и затухает вместе с реальной скоростью.
## Шагом цикл вдвое реже прежнего (5.2 → 2.6); бегом — часто, в темп шагов бега (~2.5 раза в с).
const WEAPON_BOB := {
	"idle_rate": 1.5, "walk_rate": 1.82, "sprint_rate": 8.0,
	"horizontal": 0.006, "idle_vertical": 0.002, "walk_vertical": 0.01,
}
## Наклон из-за угла (Q/E, от первого лица и в прицеле): сдвиг глаза вбок, м; крен, град;
## скорость наклона (доля в секунду); на ходу в наклоне — медленнее.
const LEAN_OFFSET := 0.4
const LEAN_ROLL_DEG := 12.0
const LEAN_SPEED := 5.0
const LEAN_MOVE_SCALE := 0.6
## Раскачка разброса очередью: за выстрел прибавка = подброс × RECOIL_BLOOM, потолок, спад в секунду;
## в прицеле раскачка — эта доля (была 0.4: очередь в прицеле почти не расходилась).
const RECOIL_BLOOM := 10.0
const RECOIL_BLOOM_MAX := 1.5
const RECOIL_BLOOM_DECAY := 2.5
const RECOIL_BLOOM_ADS := 0.75
## Хитмаркер у курсора, с.
const HITMARKER_SEC := 0.14

# --- Мишени-попперы ---
const TARGET_HEAD_MULT := 2.5
const TARGET_KNOCK := 6.0
const TARGET_SPRING := 90.0
const TARGET_DAMP := 9.0
const TARGET_DOWN_SEC := 1.6

# --- Тир убежища (бывший котельный зал) ---
## distances_m — остановки мишени от огневого рубежа: «дальше» / «ближе» везёт к соседней;
## carrier_mps — скорость тележки мишени; holes_max — пробоин на мишени, дальше стираются старые;
## sway — раскачка подвешенной бумажной мишени от попадания (рад/с на выстрел), sway_spring/damp —
## её возврат; *_head_m — высота макушки над низом мишени (голова — верхние 0.25 м).
const RANGE := {
	"distances_m": [3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 25.0, 30.0],
	"start_index": 3, "carrier_mps": 2.6, "holes_max": 90, "hole_size_m": 0.016,
	"sway": 0.35, "sway_spring": 26.0, "sway_damp": 3.2,
	"paper_head_m": 1.97, "mannequin_head_m": 1.95,
}

# --- Двери ---
## Скорость распахивания створки (чем больше, тем резче), 1/с.
const DOOR_SWING_SPEED := 7.0

# --- Здоровье ---
const PLAYER_HP := 100.0

# --- Условия рейда (RaidConditions, выбираются у лестницы в убежище) ---
## Время: риск (очки), солнце/луна (высота°, сила, цвет), небо и окружение (×), выдержка,
## дальность зрения мародёров на улице, м.
const RAID_TIME := {
	"day": {"name": "День", "risk": 0, "sun_elev": 48.0, "sun_energy": 2.2, "sun_color": Color(1.0, 0.95, 0.88), "sky": 1.0, "ambient": 1.0, "exposure": 0.9, "view": 100.0, "start_hour": 11.0},
	"dusk": {"name": "Закат", "risk": 1, "sun_elev": 12.0, "sun_energy": 2.6, "sun_color": Color(1.0, 0.74, 0.5), "sky": 1.0, "ambient": 1.0, "exposure": 1.0, "view": 75.0, "start_hour": 18.0},
	"night": {"name": "Ночь", "risk": 2, "sun_elev": 35.0, "sun_energy": 0.2, "sun_color": Color(0.70, 0.78, 1.0), "sky": 0.03, "ambient": 0.12, "exposure": 1.25, "view": 40.0, "start_hour": 23.0},
}
## Смена суток (DayCycle): секунд на игровой час; широта, °, и день года (солнце — как в средней
## полосе в конце августа: восход ~4:50, закат ~19:10 по солнцу); Луна близка к полной, отстаёт от
## «напротив солнца» на moon_lag часов. Доли «день / закат / ночь» по высоте солнца, °: день — выше
## day_from (с dusk_to начинается), ночь — ниже night_to (с dusk_from начинается). Солнце светит
## выше sun_off (полностью с sun_on); панорамы неба гаснут от sky_on до sky_off и тускнеют до
## twilight_dim к высоте twilight_end (сумерки — не дневное небо). Обновление: свет —
## раз в light_sec, небо — раз в sky_sec (перерисовка отражений неба дорогая), сеть — sync_sec.
const DAY_CYCLE := {"hour_sec": 300.0, "latitude": 55.75, "day_of_year": 235, "moon_lag": 1.5,
	"day_from": 22.0, "dusk_to": 6.0, "dusk_from": -3.0, "night_to": -12.0, "sun_on": 2.0, "sun_off": -3.0,
	"sky_on": 2.0, "sky_off": -10.0, "twilight_dim": 0.18, "twilight_end": -6.0, "light_sec": 0.1, "sky_sec": 2.0, "sync_sec": 10.0}
## Погода: риск, во сколько раз хуже видно на улице (view), слышно (hear — радиус шума).
const RAID_WEATHER := {
	"clear": {"name": "Ясно", "risk": 0, "view": 1.0, "hear": 1.0},
	"rain": {"name": "Дождь", "risk": 1, "view": 0.75, "hear": 0.6},
	"fog": {"name": "Туман", "risk": 1, "view": 0.45, "hear": 1.0},
	"heat": {"name": "Жара", "risk": 1, "view": 1.0, "hear": 1.0},
}
## Небо из HDR-панорамы (HdriSky, карта задаёт "sky_hdri" по времени суток): как погода меняет
## панораму — пасмурность (0 — как снято, 1 — сплошная пелена), экспозиция, оттенок; sun_k —
## множитель силы солнца (за пеленой прямого света меньше).
const HDRI_WEATHER := {
	"clear": {"overcast": 0.0, "exposure": 1.0, "tint": Color(1.0, 1.0, 1.0), "sun_k": 1.0},
	"heat": {"overcast": 0.0, "exposure": 1.15, "tint": Color(1.06, 1.0, 0.92), "sun_k": 1.15},
	"fog": {"overcast": 0.7, "exposure": 0.8, "tint": Color(0.95, 0.97, 1.0), "sun_k": 0.45},
	"rain": {"overcast": 1.0, "exposure": 0.5, "tint": Color(0.8, 0.84, 0.9), "sun_k": 0.0},
}
## Расчётное небо — второй режим неба смены суток (DayCycle; Settings.sky_mode = "calc", переключатель —
## Esc → Читы → Мир): атмосфера считается по положению солнца (atmosphere_sky.gdshader, таблицы —
## data/sky_atmosphere.json). Погода: mie — во сколько раз больше дымки (белёсый горизонт, ореол
## солнца), overcast — доля сплошных туч (пасмурное небо CIE: у горизонта втрое темнее зенита).
## Яркость по высоте солнца сведена к прежнему небу из панорам — свет на земле тот же; ниже match_floor
## усиление растёт на twilight_adapt порядка за градус (привыкание к сумеркам). amb_match — доля
## поправки оттенка рассеянного света и отражений к прежнему небу (0 — синева чистого неба как есть).
## Видимое небо при низком солнце темнее карты отражений (AtmosphereSky.view_k): усиление
## относительно высоты солнца view_ref, ° — в степени view_dim, не ниже view_min (0 — как карта отражений).
## Солнце — диск sun_size, °, не ярче sun_clamp. Правка mie/overcast погоды, match_floor, twilight_adapt
## или cal_from/cal_to — перезапустить python -X utf8 tools/gen_sky_atmosphere.py.
## Облака (тот же шейдер): по погоде — покрытие cover (доля неба, 1 — сплошные тучи), слой base..top, км
## над глазом, свет снизу amb_bottom (доля света неба сверху; overcast — пасмурность для подгонки света,
## саму пелену рисуют облака). clouds: ослабление sigma, 1/км; плитки шумов, км; detail_k — насколько
## детали выедают края; sun — множитель солнца на облаках; дальше far, км, облаков нет, дымка до них —
## haze, км; steps — шагов луча; ветер wind_ms, м/с, откуда — wind_from, ° от севера; солнце за облаком
## тускнеет до sun_floor (sun_tau — доля толщи, что гасит свет: многократное рассеяние светит насквозь).
const SKY_CALC := {"sun_size": 0.53, "sun_clamp": 40.0, "amb_match": 1.0, "ground_blend": 3.0,
	"view_ref": 30, "view_dim": 0.5, "view_min": 0.25,
	"match_floor": -7.0, "twilight_adapt": 0.12, "cal_from": -18, "cal_to": 70,
	"weather": {
		"clear": {"mie": 1.0, "overcast": 0.0, "cover": 0.4, "base": 1.4, "top": 3.6, "amb_bottom": 0.4},
		"heat": {"mie": 1.8, "overcast": 0.0, "cover": 0.2, "base": 2.0, "top": 4.0, "amb_bottom": 0.6},
		"fog": {"mie": 4.0, "overcast": 0.5, "cover": 0.8, "base": 0.5, "top": 1.8, "amb_bottom": 1.1},
		"rain": {"mie": 2.0, "overcast": 1.0, "cover": 1.0, "base": 0.6, "top": 4.0, "amb_bottom": 1.5}},
	"clouds": {"sigma": 30.0, "cover_tile": 30.0, "shape_tile": 9.0, "detail_tile": 1.2, "detail_k": 0.55,
		"sun": 0.3, "far": 70.0, "haze": 35.0, "steps": 96, "wind_ms": 9.0, "wind_from": 250.0,
		"sun_tau": 0.25, "sun_floor": 0.25}}
## Туман по расстоянию (карты, у которых в окружении fog_mode = depth): вблизи чисто, дальше — дымка,
## плотнее к горизонту (кривая). begin/end — метры, density — сколько дымки на end (0..1), curve > 1 —
## дольше прозрачно, потом быстрее густеет. Вместо «дыма одной плотности» — воздушная перспектива.
const DEPTH_FOG := {
	"clear": {"begin": 25.0, "end": 900.0, "density": 0.55, "curve": 1.35},
	"heat": {"begin": 40.0, "end": 1100.0, "density": 0.45, "curve": 1.2},
	"rain": {"begin": 10.0, "end": 420.0, "density": 0.8, "curve": 1.0},
	"fog": {"begin": 4.0, "end": 170.0, "density": 0.97, "curve": 0.8},
}
## Дымка по времени суток (объёмный туман карты): множитель плотности и сила солнца в ней — на закате
## воздух гуще и солнце низко: лучи между стволами и ветками.
## Жара: пересвет и марево по времени суток (ночью жара есть, а солнца — нет).
const HEAT_TIME := {"day": 1.0, "dusk": 0.5, "night": 0.0}
const VOLUMETRIC_TIME := {"day": {"density": 1.0, "sun": 1.4}, "dusk": {"density": 1.6, "sun": 2.6}, "night": {"density": 1.0, "sun": 0.6}}
## Погода за окнами убежища (ShelterWeather) — та, что ждёт в следующем рейде (Profile.next_conditions).
## Котельная стоит на открытой местности с настоящими окнами, свет уличный, запечённого нет. Солнце: азимут,
## град от юга к востоку (окна зала смотрят на юг), сила — доля от RAID_TIME.sun_energy, свечение в пыли
## (лучи из окон). ambient — сила рассеянного света неба по виду («<время>_sun» — ясно и жара,
## «<время>_grey» — дождь и туман; ночью — ровный цвет NIGHT_ENV); gi — сила отражённого света (SDFGI) по
## виду; overcast — «свет облаков» в дождь вместо солнца: высота, доля силы дневного солнца (× time_k по времени суток),
## цвет, размытость тени, град; exposure — выдержка по времени; fog — доля пыли в воздухе по виду.
const SHELTER_WEATHER := {"poll_sec": 1.0, "sun_k": 1.0, "sun_fog": 3.0,
	"sun_azimuth": {"day": 20.0, "dusk": 55.0, "night": -30.0},
	"ambient": {"day_sun": 1.5, "day_grey": 2.4, "dusk_sun": 1.5, "dusk_grey": 2.2, "night": 0.5},
	"gi": {"day_sun": 1.0, "day_grey": 1.6, "dusk_sun": 1.0, "dusk_grey": 1.6, "night_sun": 1.0, "night_grey": 1.0},
	"overcast": {"elev": 72.0, "energy_k": 0.5, "time_k": {"day": 1.0, "dusk": 0.45, "night": 0.04}, "color": Color(0.78, 0.84, 0.92), "soft_deg": 6.0},
	"exposure": {"day": 1.0, "dusk": 1.05, "night": 1.2},
	"fog": {"day_sun": 1.2, "day_grey": 1.0, "dusk_sun": 1.3, "dusk_grey": 1.0, "night_sun": 0.9, "night_grey": 0.9},
	"fog_weather_k": 1.7, "rain_db": -10.0}
## Небо над двором убежища по времени и погоде — те же панорамы, что у района ТЦ (RaidAtmosphere.hdri_sky).
const SHELTER_SKY := {
	"day": {"a": "res://assets/sky/kloppenheim_03_puresky.hdr", "exposure": 1.0, "sun_k": 0.9, "haze": 0.35},
	"day_rain": {"a": "res://assets/sky/kloofendal_overcast_puresky.hdr", "exposure": 0.9, "sun_k": 0.0, "veil": 0.8, "haze": 0.55},
	"day_fog": {"a": "res://assets/sky/kloofendal_overcast_puresky.hdr", "exposure": 1.05, "sun_k": 0.2, "veil": 0.4, "haze": 0.6},
	"dusk": {"a": "res://assets/sky/kloppenheim_06_puresky.hdr", "exposure": 1.0, "sun_k": 1.0, "haze": 0.4},
	"dusk_rain": {"a": "res://assets/sky/kloppenheim_01_puresky.hdr", "exposure": 0.9, "sun_k": 0.0, "veil": 0.8, "haze": 0.55},
	"dusk_fog": {"a": "res://assets/sky/kloppenheim_01_puresky.hdr", "exposure": 1.05, "sun_k": 0.22, "veil": 0.4, "haze": 0.6}}
## Двор котельной (убежище полуподвальное): отметка земли над полом; где кончается ровное место и с какого
## расстояния идут бугры леса, их размах и подъём, м. Дверь выхода: угол и время открывания. Сбор перед
## рейдом (RaidStartZone): план принят и все, кто в убежище, стоят в зоне — отсчёт countdown_sec, рейд.
const SHELTER_YARD := {"ground": 1.2, "flat_margin_m": 4.0, "hills_from_m": 46.0, "hill_m": 2.4, "hill_lift_m": 0.5,
	"door_open_deg": 100.0, "door_sec": 1.8, "start_radius": 4.0, "countdown_sec": 5.0}
const RAID_POWER := {
	"on": {"name": "Свет есть", "risk": 0},
	"emergency": {"name": "Аварийное освещение", "risk": 1},
	"off": {"name": "Электричества нет", "risk": 2},
}
## Погода меняется в рейде: ясно → дождь (шанс, через сколько секунд, гром за столько до него),
## туман → рассеется (шанс, через сколько).
const WEATHER_CHANGE := {"rain_chance": 0.3, "rain_after": [180.0, 600.0], "thunder_lead": 50.0,
	"fog_lift_chance": 0.4, "fog_lift_after": [300.0, 720.0]}
## Мокрая земля (асфальт, шейдер wet_asphalt): за сколько секунд дождя намокает плёнкой и
## наливаются лужи, за сколько после дождя сохнет плёнка и уходят лужи; лужи наливаются не
## выше puddle_max; рейд начался в дождь — уже мокро (start: [плёнка, лужи]).
const WET_GROUND := {"film_up_sec": 45.0, "puddle_up_sec": 200.0, "film_dry_sec": 300.0, "puddle_dry_sec": 900.0,
	"puddle_max": 0.85, "start": [1.0, 0.7]}
## Выносливость: запас, расход на бег в секунду, восстановление в секунду (после паузы, с);
## выдохся — бег снова с порога. В жару на улице расход × STAMINA_HEAT.
const STAMINA_MAX := 100.0
## Бега хватает вдвое дольше прежнего (было 11 в секунду).
## Спринта хватает вдвое дольше (5.5 → 2.75) — решение владельца 2026-10-08.
const STAMINA_DRAIN := 2.75
const STAMINA_REGEN := 16.0
const STAMINA_REGEN_DELAY := 1.0
const STAMINA_RESUME := 25.0
const STAMINA_HEAT := 1.7
## За очко риска: шанс лишнего броска в контейнере, доплата Михалыча (доля вынесенного).
const RISK_LOOT_BONUS := 0.12
## Вес редкости в выборке лута по тегам ("pick:" в data/loot.json).
const LOOT_RARITY_W := {"common": 6.0, "uncommon": 2.5, "rare": 0.7}
const RISK_PAY_BONUS := 0.05

# --- Тяжёлое ранение («лежит») ---
## Здоровье кончилось от попадания в корпус (или по касательной) — не смерть, а тяжёлое ранение:
## лежит, стреляет из пистолета, кидает гранаты, истекает кровью. Сразу смерть: в голову без
## шлема, граната ближе GRENADE_LETHAL_M, добили лежащего (кончился запас DOWN_HP — 1–3
## попадания), истёк кровью, третье ранение за рейд (больше DOWN_MAX).
const DOWN_HP := 30.0
## Пуля с уроном от стольких единиц (.50 BMG) убивает мародёра сразу, если за раз сняла всё его здоровье
## (после брони): он не ложится раненым и не отстреливается. На игроков не действует.
const OVERKILL_DAMAGE := 180.0
## До смерти от кровотечения, с: первое ранение, второе.
const DOWN_BLEED_SEC := [60.0, 35.0]
const DOWN_MAX := 2
## Игрок не умирает сразу: смертельное попадание (голова без шлема, граната в упор) — тоже
## тяжёлое ранение, но кровь уходит быстрее (время × DOWN_LETHAL_BLEED_K).
const DOWN_LETHAL_BLEED_K := 0.5
const DOWN_CRAWL_SPEED := 0.3
## Раскачка прицела лёжа раненым ×, разброс ×.
const DOWN_SWAY := 3.0
const DOWN_SPREAD := 2.0
## Бинт лёжа: + секунд к кровотечению (подняться — только аптечкой).
const DOWN_BANDAGE_SEC := 20.0
## Поднять: напарник (держит F, аптечка из его рюкзака), сам себя (аптечка, дольше), с;
## встаёт с долей здоровья REVIVE_HP.
const REVIVE_SEC := 5.0
const REVIVE_SELF_SEC := 10.0
const REVIVE_HP := 0.3
const REVIVE_RADIUS := 1.8
## Тащить раненого (X): скорость того, кто тащит, м/с; на каком расстоянии тело за ним, м.
const DRAG_SPEED := 1.2
## Несёт раненого NPC на плече (сюжет): скорость, м/с (бег невозможен).
const CARRY_SPEED := 1.7
const DRAG_DIST := 0.95
## Лежит — держать X столько секунд: сдаться (умереть сразу).
const GIVE_UP_SEC := 3.0
## Голова: попадание выше стольких метров над ногами (по стойке). Лёжа — голову не выделяем.
const HEAD_ZONE := {"stand": 1.47, "crouch": 0.97}
## Граната ближе — насмерть (подорвался на ней).
const GRENADE_LETHAL_M := 1.6
const MARAUDER_HP := 100.0

# --- Оружие игрока ---
## Сами стволы, патроны, магазины, обвес — data/weapons.json (характеристики — WeaponStats).
## Отдача (натуральная): kick — подброс ствола за выстрел, рад; kick_h — увод вбок (случайно ±,
## со сдвигом kick_bias: плюс — вправо, у АК ствол уходит вправо-вверх); recover — какую долю
## подброса руки возвращают сами (остальное остаётся — очередь «ползёт», её тянут мышью вниз).
## Эргономика (0–100, WeaponStats): время «довода» в прицел и раскачка прицела, от худшей к лучшей.
const AIM_TIME_SLOW := 0.5
const AIM_TIME_FAST := 0.12
## Опускание оружия из ADS, с; боевая точность возвращается к бедру сразу по отпусканию ПКМ.
const ADS_LOWER_TIME := 0.2
## Готовые модели тела и вида из глаз на игрока: два ствола и недавние варианты сборки.
const WEAPON_VISUAL_CACHE := 4
## Раскачка в прицеле: амплитуда, рад (стоя; сидя ×0.6, лёжа ×0.3, на сошках ещё ×0.4).
const SWAY_MAX := 0.012
const SWAY_MIN := 0.0015
const SWAY_STANCE := {"stand": 1.0, "crouch": 0.6, "prone": 0.3}
## Оптика отдельным рендером: разрешение картинки в окуляре, px. Кратность меняет только линзу.
const SCOPE_RT_SIZE := 768
## Переменная кратность: увеличение на один шаг колеса и задержка отправки состояния хосту, с.
const SCOPE_ZOOM := {"step": 1.0, "sync_sec": 0.2}

# --- Вид «как с камеры» (CameraLook, настройки «Эффекты камеры», «Размытие в движении») ---
## Глаз привыкает к свету: средняя яркость кадра ведётся к scale, но поправка к экспозиции сцены не
## больше adapt_up (тёмный угол светлее) и не меньше adapt_down (окно, фонарь в лицо); speed — за сек.
## Объектив: бочка (distortion; 0 — пересчёт кадра давал «мыло», владелец 2026-10-07), цветная кайма к краям (aberration, доля экрана), виньетка, зерно
## (сильнее в тенях), резкость, грейд — насыщенность, контраст, холодные тени и тёплые света.
## В прицеле бочка и кайма уходят (aim), а оружие у лица чуть размыто (dof_*: ближе near_m — размыто).
## «Зайчики» объектива (LensFlare): flare_ref — яркость источника (энергия × свет, с расстоянием) для полных.
## Размытие в движении — по векторам движения кадра: доля кадра «выдержки» и предел длины мазка;
## ближе blur_keep_m (руки, оружие) не размывается. По умолчанию выключено (Settings.motion_blur).
const LOOK := {"exposure_scale": 0.3, "adapt_up": 1.6, "adapt_down": 0.6, "adapt_speed": 1.6,
	"distortion": 0.0, "aberration": 0.0018, "vignette": 0.36, "grain": 0.032, "sharpen": 0.3,
	"saturation": 0.9, "contrast": 1.06, "shadow_tint": Color(0.94, 1.0, 1.05), "high_tint": Color(1.04, 1.0, 0.95),
	"dof_near_m": 0.45, "dof_transition_m": 0.3, "dof_amount": 0.08, "dof_iron_k": 0.35,
	"flare_ref": 1.0,
	"blur_shutter": 0.5, "blur_max": 0.03, "blur_samples": 12, "blur_cut_m": 2.5, "blur_cut_deg": 40.0, "blur_keep_m": 1.2}

# --- Прицел от первого лица (ПКМ) ---
## Чувствительность мыши в прицеле, рад на пиксель; у оптики — медленнее пропорционально FOV.
const ADS_SENS := 0.0024
## Высота глаз по стойке, м.
const ADS_EYE := {"stand": 1.62, "crouch": 1.05, "prone": 0.4}
## Предел наклона взгляда вверх/вниз, рад.
const ADS_PITCH_LIMIT := 1.35
## Вращение изометрической камеры средней кнопкой мыши, рад на пиксель.
const CAMERA_MMB_SENS := 0.006

# --- Гранаты ---
const GRENADES_START := 3
## fuse — запал, с; radius — радиус поражения, м; damage — урон в центре (падает к краю);
## throw_speed — скорость броска, м/с; max_range — дальше не докинуть; push — толчок телам.
const GRENADE := {"fuse": 2.6, "radius": 7.0, "damage": 140.0, "throw_speed": 13.0, "max_range": 18.0,
	"noise_m": 130.0, "push": 28.0, "shake_radius": 28.0}
## Огонёк на гранате: мигает всё чаще к взрыву (период от slow до fast, с), свет вокруг и ореол.
const GRENADE_LED := {"slow": 0.6, "fast": 0.07, "light_range": 2.5, "light_energy": 2.2, "halo_m": 0.5}
## Старый расчёт дуги оставлен для технических стендов; игроку подсказка на земле не рисуется.
const GRENADE_AIM := {"step": 0.03, "max_t": 3.0, "width": 0.05}
## Граната в руках: удержание увеличивает силу, запал начинается только после броска.
const GRENADE_HAND := {"equip_sec": 0.35, "prepare_sec": 0.28, "charge_sec": 1.2,
	"recover_sec": 0.65, "over_min": 6.0, "over_max": 15.0, "over_lift": 0.35,
	"under_min": 4.5, "under_max": 9.8, "under_lift": 0.72,
	"over_drop": 0.08, "under_drop": 0.25, "release_forward": 0.28,
	"spawn_radius": 0.036, "wall_margin": 0.06,
	"pose": Vector3(0.13, -0.10, -0.38), "pose_charge": Vector3(0.035, 0.025, 0.02),
	"pose_under": Vector3(0.0, -0.04, 0.025)}

# --- Регдолл ---
## Через сколько секунд покоя тела замирают (экономия физики).
const RAGDOLL_FREEZE_SEC := 8.0
## Толчок тела пулей: импульс = урон × коэффициент, Н·с (пуля не сдвигает тело — только вздрагивает).
const BULLET_PUSH := 0.12
## Толчок при смерти: база + за единицу последнего урона, Н·с — без подброса: подстреленный
## оседает и валится от стрелявшего, а не отлетает.
const RAGDOLL_DEATH_PUSH := {"base": 4.0, "per_damage": 0.1}
## Ящик с лутом, что вываливается из трупа мародёра: на сколько откатывается к стрелявшему, м,
## и за сколько падает, с.
const CRATE_TOSS_DIST := 0.8
const CRATE_TOSS_SEC := 0.5
## Какая доля скорости бега переходит в падение и демпфирование тел (вязкость «тяжёлого» тела).
const RAGDOLL_CARRY := 0.45
const RAGDOLL_DAMP := {"linear": 1.4, "angular": 6.0}

# --- Шум игрока: радиус слышимости шагов по стойке, м ---
const NOISE_STEP := {"stand": 7.0, "sprint": 14.0, "crouch": 3.0, "prone": 1.5}
const NOISE_STEP_INTERVAL := 0.45
## Звук шагов (Footsteps): между шагами — STEP_STRIDE / скорость, но в пределах STEP_INTERVAL, с;
## быстрее STEP_RUN_SPEED, м/с — бег (свои записи). Стена между ушами и шагами — глуше на
## AUDIO_OCCLUDED_DB и без верхов (срез AUDIO_OCCLUDED_CUTOFF, Гц): за стеной слышно, но не ясно.
const STEP_STRIDE := 1.2
const STEP_INTERVAL := [0.26, 0.75]
const STEP_RUN_SPEED := 3.8
const STEP_STANCE_DB := {"stand": 0.0, "crouch": -8.0, "prone": -14.0}
## Источник у стопы даёт мягкое чередование панорамы, включая поворот персонажа.
const STEP_FOOT_SIDE_M := 0.12
## Свои записи владельца — только ходьба по мокрому асфальту; бег пока отдельным старым набором.
## Плёнка сохнет раньше луж, поэтому вода под ногами остаётся слышна после дождя.
const WET_STEPS := {"film_min": 0.35, "puddle_min": 0.2, "roof_lift": 0.35, "roof_height": 128.0,
	"sound": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true}}
const AUDIO_OCCLUDED_DB := 8.0
const AUDIO_OCCLUDED_CUTOFF := 700.0

## Акустика мест — стенд звуков (tools/sound_bench), дальше — зоны реверберации в игре: параметры
## AudioEffectReverb (размер, затухание верхов, доля эха, задержка первого отражения, мс, и её
## повтор) и чей «хвост» выстрела из каталога (data/sound_catalog.json) звучит в этом месте.
const AUDIO_SPACES := {
	"dry": {"name": "сухо — без места"},
	"outdoor": {"name": "улица", "room": 0.35, "damping": 0.7, "wet": 0.12, "predelay": 70.0, "feedback": 0.25, "tail": "tail_outdoor"},
	"room": {"name": "магазин, подсобка", "room": 0.22, "damping": 0.5, "wet": 0.28, "predelay": 6.0, "feedback": 0.0, "tail": "tail_room"},
	"hall": {"name": "кольцевая улица ТЦ", "room": 0.7, "damping": 0.35, "wet": 0.38, "predelay": 22.0, "feedback": 0.1, "tail": "tail_hall"},
	"atrium": {"name": "атриум под куполом", "room": 0.92, "damping": 0.22, "wet": 0.5, "predelay": 45.0, "feedback": 0.15, "tail": "tail_hall"},
}
## Стенд звуков: «вдали» — срез верхов (Гц) и тише (дБ); очередь по умолчанию — выстрелов и темп
## (выстр./мин); разброс тона и громкости у каждого выстрела; как часто искать новые файлы, с.
const AUDIO_BENCH := {"far_cutoff": 2200.0, "far_db": -14.0, "burst": 5, "rpm": 650, "pitch_jitter": 0.03,
	"db_jitter": 1.0, "rescan_sec": 2.0}

# --- Мародёр ---
## Кольцо (3 сектора): 24 мародёра отрядами по 1–3 — встречи часто, но не на каждом углу.
const MARAUDER_COUNT := 24
const MARAUDER_WALK := 1.5
const MARAUDER_RUN := 3.4
## Ближе этого до точки спавна игрока мародёры не появляются, м.
const MARAUDER_SPAWN_MIN_DIST := 45.0
## Безопасный старт: мародёр не появляется в прямой видимости точки появления ближе los_m;
## первые sec секунд рейда маршруты патруля обходят круг radius вокруг неё.
const SPAWN_SAFE := {"radius": 40.0, "sec": 150.0, "los_m": 90.0}
## Население рейда слоями (AIPopulation, docs/design/enemy_population.md) — если на карте стоят точки
## AIPost / AIRoute / AINest / AIArrival; без них — прежний спавн MARAUDER_COUNT по ai_spawn_points.
## Карта может переопределить любой ключ словарём "ai" в своих данных (как "birds").
## party_k — множитель числа групп для 1, 2, 3 игроков (дробное округляется); posts / routes / nests /
## arrivals — групп слоя у троих [от, до]; post_group / route_group / arrive_group — человек в группе
## [от, до] (у поста может быть свой размер в точке); arrive_at — окна входа подхода, с от начала рейда
## (i-я группа — в i-е окно, лишние — в последнее); arrive_min_m — вход не ближе к игрокам, м, и не на
## виду; arrive_retry_sec — все входы заняты, пробуем снова через столько, с; arrive_noise_sec — подход
## идёт к выстрелам не старше стольких секунд, иначе — за добычей; snap_m — точка дальше стольких
## метров по горизонтали от навигации не годится; post_points — сколько точек обхода набрать вокруг
## поста, у которого своих нет; pmc — бойцов ЧВК для 1, 2, 3 игроков (решение владельца 2026-10-14);
## nav_wait_sec — навигация из кэша синхронизируется сервером не сразу: ждём, пока все точки населения
## встанут на неё, не дольше стольких секунд.
const AI_POPULATION := {
	"party_k": [0.6, 0.8, 1.0],
	"posts": [5, 6], "routes": [2, 2], "nests": [0, 1], "arrivals": [2, 3],
	"post_group": [2, 3], "route_group": [2, 2], "arrive_group": [2, 2],
	"arrive_at": [[480.0, 720.0], [960.0, 1320.0]], "arrive_min_m": 120.0, "arrive_retry_sec": 20.0,
	"arrive_noise_sec": 90.0, "snap_m": 4.0, "post_points": 5, "nav_wait_sec": 10.0,
	"pmc": [3, 4, 4],
}
## Отклик на шум (только мародёры): проверять идут не больше groups групп — сначала те, что уже заняты
## этим местом (их цель ближе same_m к шуму), потом ближайшие из услышавших; остальные настораживаются
## на месте на alert_sec, с [от, до]: стоят, смотрят на шум. Шум под самым носом (AI_INVESTIGATE_NEAR)
## проверяют всегда.
const AI_NOISE_RESPONSE := {"groups": 2, "same_m": 40.0, "alert_sec": [12.0, 20.0]}
## Счётчик стычек рейда (RaidContacts; итог — в лог по окончании рейда, метрики — enemy_population.md §2):
## стычка — кто-то из врагов видит игрока или стреляет по нему, кончилась после calm_sec без этого;
## боец в стычке ещё hold_sec после последнего взгляда/выстрела. Тяжёлая — врагов heavy_enemies и больше,
## или чужой отряд / ЧВК, или игрок упал либо потерял долю heavy_hp здоровья; tick_sec — шаг проверки.
const RAID_CONTACTS := {"calm_sec": 30.0, "hold_sec": 1.5, "heavy_enemies": 4, "heavy_hp": 0.5, "tick_sec": 0.5}

# --- Перелезание и бросок на землю ---
## Перелезание (Пробел у преграды; мародёры — по связкам навигации): высота преграды от min_h до
## max_h, м; дотянуться — reach от ног; толщина до max_thick; время, с (с перегрузом — дольше на
## weight_k); шум, м; выносливость.
## max_h поднят на 30 % (1.3 → 1.7) — решение владельца 2026-10-08.
## Шаг на ступень без прыжка (бордюр, порожек, ступени подъезда): не выше max_h, м (выше —
## перелезание, VAULT.min_h); reach — сколько вперёд можно «дошагнуть», м. Камера: смещение глаза
## по высоте не больше eye_max, м, гаснет со скоростью eye_rate, 1/с (больше — быстрее догоняет).
const STEP_UP := {"max_h": 0.34, "reach": 0.24, "eye_max": 0.4, "eye_rate": 11.0}
## Полёт для аудита уровня (Esc → Настройки → Отладка): скорость, м/с; × со спринтом.
const DEBUG_FLY := {"speed": 8.0, "boost": 4.0}
const VAULT := {"min_h": 0.35, "max_h": 1.7, "reach": 1.0, "max_thick": 1.6, "sec": 0.75, "weight_k": 0.6,
	"noise_m": 16.0, "stamina": 12.0}
## Связки навигации «перелезть» для ИИ: образцы вдоль края навмеша через step м; не ставить, если
## обойти не дольше detour_m; связки не ближе spacing_m друг к другу; цена пути по связке.
const VAULT_LINKS := {"step": 1.5, "detour_m": 7.0, "spacing_m": 2.5, "travel_cost": 2.0}

## Обычный прыжок на пробел, если перед игроком нет преграды для перелезания.
## Скорость вверх даёт подъём тела примерно на 0.55 м при гравитации 9.8 м/с².
const JUMP := {"speed": 3.3, "stamina": 10.0, "cooldown": 0.25, "takeoff_noise_m": 3.0,
	"land_noise_m": 12.0, "land_db": -10.0}
## Бросок на землю (Alt + направление, в любую сторону): скорость рывка, м/с; подскок, м/с; сколько
## летит, с; сколько приходит в себя (не стреляет), с; шум, м; выносливость; повтор не чаще, с.
const DIVE := {"speed": 5.0, "hop": 1.6, "sec": 0.42, "recover": 0.55, "noise_m": 20.0, "stamina": 15.0, "cooldown": 1.0}

# --- Стресс ---
## Стресс 0–100 (свой у каждого игрока). Растёт от того, что пугает: пули рядом (near_miss за пулю,
## не чаще раза в near_gap с, ближе near_m), попадание (hit + hit_per_dmg за единицу урона), взрыв
## рядом (blast у самой гранаты, к краю тряски — ноль), тяжёлое ранение (сразу не ниже downed),
## напарник упал рядом (ally_down, в ally_down_m). Не ниже: low_hp — мало здоровья (< 35%),
## winded — выдохся. Спадает через calm_delay с тишины на calm в секунду; сидя/лёжа на месте —
## ×calm_cover_k, напарник в ally_m — ×calm_ally_k. Обезболивающее — минус painkillers.
## Последствия — только выше effects_from и плавно до 100: перезарядка дольше (×1+reload_k),
## прицел гуляет сильнее (×1+sway_k); редко, с перерывом — запнулся на перелезании (от
## stumble_from, шанс до stumble_chance, не чаще stumble_cd), выронил отстёгнутый магазин при
## смене (от fumble_from, шанс до fumble_chance, не чаще fumble_cd, +fumble_sec к перезарядке).
## Сердце слышно от heart_from. Адреналин (та же шкала stress_k): бег быстрее на ×1+adr_speed,
## выносливость тратится медленнее (×1−adr_stamina), попадание трясёт слабее (×1−adr_shake).
const STRESS := {"adr_speed": 0.1, "adr_stamina": 0.35, "adr_shake": 0.5, "near_miss": 6.0, "near_gap": 0.25, "near_m": 2.0, "hit": 10.0, "hit_per_dmg": 0.35, "blast": 25.0,
	"downed": 85.0, "ally_down": 22.0, "ally_down_m": 25.0, "low_hp": 35.0, "winded": 20.0,
	"calm_delay": 3.0, "calm": 5.0, "calm_cover_k": 2.0, "calm_ally_k": 1.5, "ally_m": 8.0, "painkillers": 35.0,
	"effects_from": 50.0, "reload_k": 0.4, "sway_k": 1.2,
	"stumble_from": 65.0, "stumble_chance": 0.3, "stumble_cd": 40.0,
	"fumble_from": 70.0, "fumble_chance": 0.25, "fumble_cd": 45.0, "fumble_sec": 0.8, "heart_from": 70.0}

# --- Общение в коопе ---
## Чат (Enter): сколько строк видно и сколько секунд строка висит после последнего сообщения;
## реплика над головой, с.
const CHAT_LINES := 8
const CHAT_FADE_SEC := 12.0
const CHAT_BUBBLE_SEC := 6.0
## Голос (зажать K): частота передачи, Гц; пакет, с; буфер у слушателя, с; слышно до, м (в
## убежище и рейде — объёмно, как голос рядом; по рации — нет); громкость, дБ.
const VOICE := {"rate": 16000, "packet_sec": 0.04, "buffer_sec": 0.5, "max_m": 40.0, "db": 4.0}
## Зрение: дальность (без уровня — запасная; в рейде — RaidAtmosphere по условиям), полуугол
## конуса, и во сколько раз дальность меньше для сидящего/лежащего.
const AI_VIEW_DISTANCE := 45.0
## В помещении видно на столько, м: свет есть, аварийный, темно днём (свет с улицы), темно ночью.
const AI_VIEW_INDOOR := {"lit": 50.0, "emergency": 25.0, "dark_day": 28.0, "dark_night": 12.0}
## С включённым фонарём тебя видно минимум на столько, м (× view фонаря: мощный — дальше).
const AI_VIEW_FLASHLIGHT := 70.0
## Включённый ЛЦУ в темноте (луч в дыму и пыли, точка на стене) — видно минимум на столько, м.
const AI_VIEW_LASER := 35.0
## В ПНВ точка коллиматора и голографа в руках — во столько раз крупнее (тонкая теряется в трубке).
const NVG_RETICLE_SCALE := 2.5
## Хроника рейда (src/story): когда событие считается событием. Здоровье ниже доли low_hp —
## критический момент; комплект дороже expensive_kit ₽ — дорогой, дешевле cheap_kit — дешёвый;
## убийств от high_kills — «много»; streak_n убийств за streak_sec с — серия; weak_kills убийств
## пистолетом — «слабым оружием»; точность — от accuracy_min_shots выстрелов (accurate / inaccurate);
## без урона — если рейд дольше no_damage_min_sec; находка от big_find ₽; вынес от valuable_loot ₽
## (меньше empty_handed — пустой); долгий рейд — от long_raid_sec; у выхода дольше camped_exit_sec;
## смерть быстрая — до fast_death_sec, у выхода — ближе near_exit_m; серия рейдов — от streak_raids.
## В рассказе events_min…events_max событий; история — history_n рейдов, recent_lines фраз не
## повторять. Ранг класса оружия — «лучше / хуже» (нашёл получше, убил слабым). Отбор: к интересности
## события — случайная прибавка до pick_jitter (похожие рейды звучат по-разному); событий в рассказе —
## сколько интереснее interesting, +0…1, в пределах events_min…events_max; связка между абзацами —
## с шансом transition_chance.
const RAID_STORY := {
	"low_hp": 0.25, "cheap_kit": 25000, "expensive_kit": 150000, "high_kills": 8, "streak_sec": 30.0, "streak_n": 3,
	"weak_kills": 2, "many_switches": 4, "accuracy_min_shots": 20, "accurate": 0.55, "inaccurate": 0.2,
	"trigger_happy": 250, "many_heals": 3, "no_damage_min_sec": 240.0, "big_find": 30000, "valuable_loot": 80000,
	"empty_handed": 5000, "long_raid_sec": 1500.0, "camped_exit_sec": 90.0, "fast_death_sec": 90.0, "near_exit_m": 25.0,
	"streak_raids": 3, "events_min": 3, "events_max": 6, "history_n": 10, "recent_lines": 80,
	"pick_jitter": 0.25, "interesting": 0.6, "transition_chance": 0.6,
	"class_rank": {"PISTOL": 1, "SMG": 2, "PDW": 2, "SHOTGUN": 2, "CARBINE": 3, "ASSAULT_RIFLE": 3, "BATTLE_RIFLE": 4, "DMR": 4, "SNIPER": 4, "SPECIAL": 4, "LMG": 4},
}
## Буфер посередине окна лута (рейд), клеток: ширина × высота.
const BUFFER_GRID := Vector2i(3, 3)
## Проверка патронов (держать R): сколько держать, с; сколько виден ответ, с; «на глаз» — от какой
## доли магазина какое слово (пустой и полный — отдельно). Точно — у пистолетов и болтовок.
## Пока R держат, магазин остаётся перед глазами, и кисть с ним можно повернуть мышью: turn_deg —
## насколько (проворот кисти вокруг предплечья, сгиб в запястье), turn_sens — доля полного поворота
## на пиксель движения мыши.
const AMMO_CHECK := {"hold_sec": 0.4, "show_sec": 3.0, "turn_deg": [45.0, 18.0], "turn_sens": 0.006,
	"words": [[0.85, "почти полный"], [0.6, "больше половины"], [0.4, "половина"], [0.15, "меньше половины"], [0.0, "почти пустой"]],
	# метка на магазине в сетке: полный / пустой видно всегда, остальное — после проверки
	"short": {"полный": "ПОЛН", "почти полный": "~ПОЛН", "больше половины": ">½", "половина": "½",
		"меньше половины": "<½", "почти пустой": "~ПУСТ", "пустой": "ПУСТ"}}
## Обмен вещами (Trade — убежище и рейд): на каком расстоянии от напарника начинается, м, и сколько
## держать «действие», с; grid — сетка одной половины буфера; в рейде обмен рвётся, если разошлись
## дальше break_m.
const TRADE := {"reach_m": 2.2, "hold_sec": 0.5, "grid": [8, 5], "break_m": 5.0}
## Разгрузка (слот снаряжения "rig", предметы с полем rig в data/items.json): подсумки — сетка
## «подсумков × rows» только под магазины, сумка сброса — «dump × rows», тоже только магазины.
## Перезарядка берёт магазин из подсумков; нет там — из рюкзака, но дольше в backpack_reload_k раз.
## Старый магазин — в сумку сброса, нет места — в рюкзак, потом в подсумки, иначе на землю.
const RIG := {"rows": 2, "backpack_reload_k": 1.35}
## Поштучно (MagOps): снарядить магазин — с на патрон, разрядить — с на патрон, вынуть плиту из
## жилета — с на плиту. Игровой темп, не армейский норматив: 30 патронов — около 8 с.
## С ускорителем снаряжения (предмет loader_item в рюкзаке, кармане, буфере; в убежище — и в тайнике) —
## патроны идут пачками: loader_batch штук каждые loader_sec секунд (10 за полсекунды, магазин на 30 —
## за полторы секунды), и снаряжение, и разрядка. Без ускорителя — по одному, как раньше.
const MAG_OPS := {"load_sec": 0.26, "unload_sec": 0.14, "plate_sec": 1.2, "loader_item": "mag_loader", "loader_sec": 0.5, "loader_batch": 10}
## Ящики и тела — сетка: ширина и сколько рядов минимум по виду (LootContainer.Look; бросок не
## влез — рядов больше, чтобы ничего не терялось).
const LOOT_GRID_W := 6
## Выброшенное в рейде в пределах стольких метров от лежащего мешка «Выброшено» — в тот же мешок.
const DROP_MERGE_M := 3.0
const LOOT_ROWS := {"NONE": 3, "SAFE": 3, "RACK": 4, "BODY": 4, "BAG": 3, "CRATE": 3}
## ЛЦУ (LaserSight): докуда видна точка, м; её радиус вблизи и прирост на метр дистанции (чтобы
## разглядеть сверху). Цветного отсвета вокруг точки нет.
const LASER := {"range_m": 150.0, "dot_radius": 0.012, "dot_grow": 0.0012}
## Брошенный свет: осветительная ракета и химсвет — цвет, сила, радиус, сколько горит, с.
const THROWN_LIGHTS := {
	"flare": {"color": Color(1.0, 0.32, 0.22), "energy": 9.0, "range": 20.0, "sec": 60.0, "shadow": true},
	"chemlight": {"color": Color(0.35, 1.0, 0.45), "energy": 1.0, "range": 9.0, "sec": 600.0, "shadow": true,
		"indirect": 2.6, "blur": 2.5},
}
## Осветительная ракета из сигнального пистолета (SkyFlare; решение владельца 2026-10-10): в воздухе
## air_sec — взлёт на rise_m за rise_sec, дальше спуск fall_speed м/с с покачиванием sway_m; гаснет за
## fade_sec до конца. Свет — прожектор вниз: energy, range, угол конуса angle°, спад по расстоянию
## attenuation (малый — ровно заливает), размытие края конуса edge и тени blur, отражённый свет
## indirect, свечение в тумане fog. lit_radius — круг на земле, где на улице видно всех (как у ручной
## ракеты FLARE_LIT_VIEW). drift — уклон выстрела по взгляду (0 — строго вверх). core_m / halo_m —
## размеры звезды и ореола. noise_m — выстрел слышат NPC.
const SKY_FLARE := {"air_sec": 15.0, "rise_m": 75.0, "rise_sec": 2.4, "fall_speed": 2.6, "sway_m": 1.5, "fade_sec": 2.5,
	"color": Color(1.0, 0.24, 0.16), "energy": 5.0, "range": 240.0, "angle": 74.0, "attenuation": 0.35,
	"edge": 0.5, "blur": 4.0, "indirect": 1.6, "fog": 2.2, "lit_radius": 110.0, "drift": 0.28,
	"core_m": 2.2, "halo_m": 18.0, "noise_m": 110.0}
## Брошенный свет после приземления: медленнее settle_speed м/с дольше settle_sec — замирает
## (не катается, свет не скачет); не позже max_roll_sec после первого касания.
## Наружный свет — одна система (RaidWeather): темно (не день) — горят уличные фонари и заградительные
## огни; днём заградительные зажигаются, когда видимость по туману ниже fog_on_m, и гаснут, только когда
## она поднимется выше fog_off_m (гистерезис — у порога не мигают). fade_sec — плавное включение и
## выключение; fog_change_sec — за сколько туман сгущается / рассеивается; beacon_light_m — дальше
## этого у заградительного огня остаётся только свечение (лампа и ореол), без источника света.
## Под крышей ТЦ (у своего игрока, только картинка): туман — доля fog_k уличного (затягивает в двери
## и витрины, но не стена). Переход — за sec, когда игрок входит или выходит.
const INDOOR := {"fog_k": 0.2, "sec": 2.5}

const OUTDOOR_LIGHTS := {"fade_sec": 3.0, "fog_on_m": 300.0, "fog_off_m": 450.0, "fog_change_sec": 30.0,
	"beacon_light_m": 70.0, "beacon_fade_m": 20.0}

## Уличный фонарь (StreetLamp, LampHead): цвет, сила, дальность и угол конуса, отражённый свет,
## свечение в тумане, яркость рассеивателя; дальше fade_begin м от камеры гаснет, тень — ближе
## shadow_m. edge — спад к краю конуса (меньше — мягче: свет гаснет от середины, без круга с
## резкой границей), falloff — спад с расстоянием.
const STREET_LAMP := {"color": Color(1.0, 0.84, 0.62), "energy": 6.0, "range": 24.0, "angle": 88.0, "indirect": 1.6,
	"fog": 0.9, "lens": 4.0, "fade_begin": 110.0, "shadow_m": 45.0, "edge": 1.2, "falloff": 2.2}
## Отражённый от мокрой земли луч фонаря (WetBounce): вклад плёнки и луж в отражение, доля
## отражения в упор (к касательной — до 1), общий множитель яркости, во сколько раз шире конус;
## считается раз в tick с, если фонарь ближе max_cam_m к камере.
const WET_BOUNCE := {"film": 0.35, "puddle": 0.65, "base": 0.08, "energy": 0.9, "spread": 1.35, "tick": 0.05, "max_cam_m": 45.0}
## Свечение (блум) днём на картах рейда: решение владельца 2026-10-17 — ореолы от бликов на оружии и
## засвет у горизонта против солнца «противные», днём их нет. Ночью — NIGHT_ENV (фонари, ракеты); в смене
## суток — плавно по доле ночи. Сила 0 — свечение выключено.
const DAY_GLOW := {"intensity": 0.0, "bloom": 0.0}
## Ночное окружение (небо — шейдер night_sky, Луна — свет «Sun»): рассеянный свет ровным
## тёмно-холодным цветом (звёзды не светят), свечение — только от очень яркого (диск Луны, маяки),
## объёмный туман слабее (× fog_k).
const NIGHT_ENV := {"ambient_color": Color(0.09, 0.11, 0.16), "glow_threshold": 1.3, "glow_intensity": 0.4, "glow_bloom": 0.0,
	"fog_k": 0.55, "fog_sky": 0.08, "moon_fog": 0.12}
const THROWN_SETTLE := {"settle_speed": 0.35, "settle_sec": 0.25, "max_roll_sec": 2.0, "roll_damp": 9.0}
## Ракета: кто в радиусе горит — виден минимум на столько, м; мародёр ближе FLARE_BLIND_M,
## глядя на неё, целится как только что заметивший (слепит).
const FLARE_LIT_VIEW := 45.0
const FLARE_BLIND_M := 12.0
## Фонарь на оружии в лицо ближе стольких метров — слепит мародёра (целится как только что
## заметивший), как ракета.
const FLASHLIGHT_BLIND_M := 15.0

# --- Арсенал (data/weapons.json, data/armor.json; docs/design/weapons.md) ---
## Износ оружия: разброс × (1 + износ² × spread); задержка за выстрел = (1 − надёжность) ×
## jam_base × (1 + износ² × jam_worn) (износ = (100 − прочность)/100); устранить — clear_sec.
const WEAPON_WEAR := {"spread": 0.8, "jam_base": 0.012, "jam_worn": 25.0, "clear_sec": 1.5}
## Ресурс оружия/обвесов в процентах; пороги материалов, расход на выстрел и ремонт.
const CONDITION := {"full": 100.0, "used": 60.0, "worn": 20.0,
	"weapon_wear": 0.02, "mod_wear": 0.002,
	"shot_wear": {"OPTIC_RED_DOT": 0.001, "OPTIC_HOLOGRAPHIC": 0.001,
		"OFFSET_RED_DOT": 0.001, "SUPPRESSOR": 0.025},
	"repair_weapon": 0.35, "repair_mod": 0.45, "repair_min": 50,
	"reticle_min": 0.45, "grime_used": 0.08, "grime_worn": 0.18, "cache_entries": 256}
## Досыпать россыпь в отстёгиваемый магазин (снаряжённых нет) — дольше смены магазина во столько.
## Переключение основного / углового / бокового прицела от первого лица, с (без опускания оружия).
const SIGHT_SWITCH_SEC := 0.22
## Стрельба «с завалом» (СКМ в прицеле, последняя ступень после прицелов сборки): автомат повёрнут на
## roll_deg правым боком (затвором) к глазам и опущен под линию взгляда — вести огонь по точке ЛЦУ в
## упор, когда на планке только оптика. right / up — где проходит взгляд в осях оружия, м (правее и
## выше прицельной линии); spread_k — доля пути от точности в прицеле к точности от бедра.
## Люфт оружия в прицеле (решение владельца, 2026-10-10): оружие чуть отстаёт от взгляда при движении
## мыши и отдаче — метка коллиматора плывёт в окне, видны стенки прицела, мушка с целиком на миг
## расходятся. share — какая доля поворота взгляда уходит в отставание; follow — как быстро оружие
## догоняет взгляд, 1/с; max_deg — предел отставания; hip_k — доля люфта от бедра (в прицеле — 1).
## Оптика при полном отставании: scope_shift — на какую долю поля сдвигается картинка в окуляре,
## scope_shadow — насколько с края наползает тень (глаз ушёл с оси), scope_warp — добавка к искажению.
const AIM_LAG := {"share": 0.55, "follow": 13.0, "max_deg": 1.6, "hip_k": 0.5,
	"scope_shift": 0.07, "scope_shadow": 0.42, "scope_warp": 0.3, "dot_k": 0.3}
## dot_k (выше) — своя инерция метки коллиматора: корпус прицела отстаёт от взгляда на весь люфт, а
## светящаяся метка — только на эту долю (0 — стоит на цели, 1 — едет вместе с корпусом): метка
## плавает в окне, а не уезжает с цели вместе с ним.
## Дыхание в прицеле (решение владельца 2026-10-10): линия прицеливания медленно ходит вверх-вниз
## (deg — размах, град; period — вдох-выдох, с) с дрейфом вбок (side — доля от вертикали). Устал
## (выносливость на нуле) — × (1 + fatigue_k), стресс — × (1 + stress_k); сидя и лёжа — как раскачка
## (SWAY_STANCE). Задержка дыхания — «бег» (Shift) в прицеле: покачивание × held_k, воздуха хватает на
## hold_sec; выдохся — одышка gasp_sec с покачиванием × gasp_k; запас возвращается за refill_sec.
const BREATH := {"deg": 0.16, "period": 3.8, "side": 0.35, "fatigue_k": 1.6, "stress_k": 0.9,
	"held_k": 0.15, "hold_sec": 4.5, "refill_sec": 6.0, "gasp_sec": 3.0, "gasp_k": 2.2}
## Отдача в руках (модель от первого лица): три пружины с перелётом — толчок назад в плечо (back),
## подброс ствола (rise), увод вбок (side): [жёсткость, доля затухания (меньше 1 — с перелётом)].
## side_deg — увод вбок на единицу толчка, град. От бедра оружие гуляет в руках сильнее (hip_k), а
## взгляд почти стоит (hip_cam_k — доля подброса взгляда); в прицеле оружие и взгляд идут вместе.
const HAND_RECOIL := {"back": [520.0, 0.5], "rise": [300.0, 0.42], "side": [200.0, 0.4],
	"side_deg": 0.9, "hip_k": 1.45, "hip_cam_k": 0.4}
## Пристрелка (решение владельца 2026-10-10): у экземпляра ствола ноль сбит на found_moa угловых минут
## (найден в рейде, снят с тела), после смены прицела — на sight_moa; купленный у Михалыча — точен.
## Пули уходят на эту поправку от точки прицеливания. Правка — щелчками барабанчиков в прицеле
## (стрелки): щелчок двигает попадания на click_moa (1 угл. мин ≈ 3 см на 100 м), не больше max_clicks
## в каждую сторону. Ошибку игрок не видит — только свои щелчки; сверять по листу в тире.
const ZEROING := {"click_moa": 1.0, "max_clicks": 40, "found_moa": [3.0, 9.0], "sight_moa": [2.0, 5.0]}
const AIM_CANT := {"roll_deg": 45.0, "right": 0.05, "up": 0.02, "spread_k": 0.45}
const RELOAD_TOPUP_K := 1.6
## Быстрая перезарядка (второе R не позже tap_sec после первого): новым магазином выбивают старый — тот
## падает на землю; занимает time_k от обычной (на 25–30 % быстрее — решение владельца, 2026-10-10).
const RELOAD_FAST := {"tap_sec": 0.3, "time_k": 0.72}
## Сброшенный магазин лежит на земле сам по себе (моделью магазина, не мешком): падает в radius м
## от ног, с высоты fall м; подобрать — подойти и нажать F.
const DROPPED_MAG := {"radius": [0.25, 0.7], "fall": 0.9}
## Магазин вынут из оружия: R только вставляет новый (и досылает патрон) — time_k от полной перезарядки:
## старый магазин вынимать не надо. Держать R и двойное R в этом случае ничего не делают.
const RELOAD_INSERT := {"time_k": 0.63}
## Действия с ПМ: время установки обвеса и ожидание подтверждения авторитетного хоста.
const PM_ACTION := {"suppressor_sec": 2.5, "host_reply_sec": 1.5, "host_poll_sec": 0.1, "sound_db": -4.0}
## Изометрия (ПКМ переводит в прицел от первого лица — там выбранный прицел и работает), от бедра:
## угловой коллиматор выбран — разброс × offset_hip (навскидку), крупная оптика — × scope_hip;
## zoom_per_x — на будущее: приближение камеры за кратность.
const ISO_AIM := {"offset_hip": 0.88, "scope_hip": 1.1, "zoom_per_x": 0.035}
## Защита класса брони (0–5): против пробития патрона (pen).
const ARMOR_CLASS_PROT := [0.0, 12.0, 22.0, 34.0, 46.0, 56.0]
## Пробитие: защита = класс × (dur_floor + (1 − dur_floor) × доля прочности); шанс пробить —
## плавная ступень pen в окне ±window вокруг защиты. Пробила — проходит урон × от through_min
## до 1 (на full_over сверх защиты — весь); не пробила — тупая травма (blunt слоя), износ слоя —
## armor_dmg × wear_stopped (пробила — × wear_pen) × износ материала.
const ARMOR := {"dur_floor": 0.55, "window": 10.0, "through_min": 0.6, "full_over": 20.0, "wear_stopped": 1.0, "wear_pen": 0.6}
## Зоны попадания: множитель урона. Голова без шлема или сквозь шлем — насмерть (Health).
const ZONE_DAMAGE := {"thorax": 1.0, "arms": 0.6, "legs": 0.7}
## Высоты зон (доля роста): ниже legs — ноги; руки — дальше arms_w от оси корпуса.
const ZONE_SHAPE := {"legs": 0.5, "arms_w": 0.2}
## Вес: до free_kg — без штрафа; к max_kg — скорость × speed_min, расход выносливости × stamina_max.
const CARRY := {"free_kg": 22.0, "max_kg": 50.0, "speed_min": 0.72, "stamina_max": 1.8}
## Витринное стекло: урон пули по нему = урон × bullet_k (прочность панели 100); треснувшее
## ниже collapse_below — осыпается само через collapse_sec; пуля за стеклом — урон × pass_k;
## звон осколков слышно на noise_m.
## Закалённое (доля tempered_share, двери): от первой пули — сетка мелких кубиков, через tempered_sec с
## осыпается волной от точки удара tempered_wave_mps м/с; кубиков cubes_per_m2 (не больше cubes_max).
## Трещины (GlassCracks): crack_ppm — пикселей на метр (не больше crack_px_max по длинной стороне),
## rays — лучей у попадания, ray_len_m — длина (слабый удар — сильный), arcs — дуг между лучами,
## frost_m — радиус белой крошки, hole_m — дырки; ослабленная потрескивает каждые creep_sec с,
## лучи ползут на creep_px.
## Куски (GlassShatter): shards_max всего, shards_per_m2 — крупных вдали от дырок, shard_thick (м),
## fall_speed — от панели по ходу пуль (м/с), fall_spin (рад/с), wave_s_per_m — волна от места удара,
## teeth_per_m — мелких ячеек вдоль рамы на метр её длины, teeth_share — доля кусков у рамы, что
## остаются торчать (если меньше teeth_max_m2), land_bursts — сколько крупных бьются о пол блёстками.
const GLASS := {"bullet_k": 1.4, "collapse_below": 0.45, "collapse_sec": [1.2, 3.5], "pass_k": 0.85, "noise_m": 35.0,
	"tempered_share": 0.3, "tempered_sec": [0.15, 0.9], "tempered_wave_mps": 3.5, "cubes_per_m2": 220.0, "cubes_max": 900,
	"crack_ppm": 256.0, "crack_px_max": 896, "rays": Vector2i(6, 14), "ray_len_m": Vector2(0.12, 0.5), "arcs": Vector2i(1, 3),
	"frost_m": Vector2(0.012, 0.026), "hole_m": Vector2(0.004, 0.007), "creep_sec": Vector2(0.18, 0.5), "creep_px": Vector2(14.0, 48.0),
	"shards_max": 96, "shards_per_m2": 4.0, "shard_thick": 0.008, "fall_speed": Vector2(0.3, 1.4), "fall_spin": Vector2(2.0, 9.0),
	"wave_s_per_m": 0.12, "teeth_per_m": 4.0, "teeth_share": 0.65, "teeth_max_m2": 0.08, "land_bursts": 6}
## Пустая магазинная тележка: масса, сопротивление колёс и контакт с человеком (СИ).
## Стекло и травма зависят от энергии по нормали; прижатие — от силы и стены за человеком.
const CART: Dictionary = {
	"mass_kg": 15.0, "person_kg": 80.0, "center_y": 0.40,
	"friction": 0.012, "tipped_friction": 0.55, "bounce": 0.16,
	"linear_damp": 0.025, "angular_damp": 0.65, "rolling_decel": 0.13,
	# медленнее — тележка стоит: сопротивление качению не прикладывается, и тело засыпает (физика
	# сотни тележек ТЦ иначе ест кадр)
	"rest_mps": 0.02,
	"wheel_ground_dot": 0.65, "upright_dot": 0.55, "contacts": 24,
	"caster_response": 9.0,
	"push_restitution": 0.05, "push_min_speed": 0.04, "push_reach_m": 1.6,
	"push_net_sec": 0.05, "push_speed_margin": 1.2, "attribution_sec": 8.0,
	"glass_break_j": 18.0, "glass_min_j": 2.0,
	"wheel_vault_min_mps": 4.2,
	"injury_min_j": 38.0, "injury_hp_per_j": 0.12, "injury_max_hp": 55.0,
	"injury_cooldown_sec": 0.65, "shove_max_mps": 3.5, "shove_decel": 6.0,
	"crush_probe_m": 0.18, "crush_min_n": 260.0, "crush_hp_per_ns": 0.012,
	"sound_min_speed": 0.7, "sound_cooldown_sec": 0.3, "noise_m": 14.0,
	"net_sec": 0.05, "net_smooth": 18.0, "net_snap_m": 3.0,
}
## ПНВ: заряда на столько секунд работы за рейд.
const NVG_BATTERY_SEC := 1200.0
## Фонарь мародёра в темноте: сила и дальность луча.
const AI_TORCH_ENERGY := 4.0
const AI_TORCH_RANGE := 24.0
## Фонари ИИ (налобный и на оружии) дальше begin м от камеры плавно гаснут (за length м), тень —
## только ближе shadow м: много мародёров с фонарями ночью не роняют кадр.
const AI_LIGHT_FADE := {"begin": 70.0, "length": 20.0, "shadow": 28.0}
## Раскладка периодических проверок ИИ по времени и повторные одинаковые запросы.
## Зрение игрока, движение тела и стрельба остаются на каждом физическом шаге.
const AI_WORK := {"phase_slots": 16, "foe_scan_sec": 0.3, "glare_scan_sec": 0.5,
	"follow_repath_sec": 0.5, "target_epsilon_m": 0.05, "cover_retry_sec": 0.2}
const AI_VIEW_HALF_ANGLE_DEG := 60.0
const AI_VIEW_STANCE_SCALE := {"stand": 1.0, "crouch": 0.7, "prone": 0.4}
## Сколько секунд непрерывной видимости нужно, чтобы заметить (ближе — быстрее).
const AI_NOTICE_SEC := 0.35
## Заметить игрока (в поле зрения, не за стеной): сколько секунд смотреть — от near_sec (ближе near_m)
## до far_sec (дальше far_m); × stance (лёжа, присев — дольше), × sprint (бежит), × shot (стрелял
## последние shot_sec с) — быстрее. Отвёл взгляд — «забывает» вдвое медленнее, чем замечал.
const AI_NOTICE := {"near_m": 8.0, "far_m": 100.0, "near_sec": 0.25, "far_sec": 2.6,
	"stance": {"stand": 1.0, "crouch": 1.25, "prone": 1.7}, "sprint": 0.55, "shot": 0.45, "shot_sec": 2.0}
## Очередь на огонь: по одной цели прицельно стреляют не больше tokens мародёров (остальные — на
## подавление: разброс × untoken_spread, реже); право держат hold_sec, с, потом отдают и ждут
## cooldown_sec, с, — по игроку стреляют по очереди, а не все разом.
const AI_FIRE_TOKENS := {"tokens": 2, "hold_sec": 3.0, "cooldown_sec": 1.6, "untoken_spread": 3.0, "untoken_pause": 0.5}
## Состав отрядов: веса для 1, 2, 3 человек.
const AI_SQUAD_WEIGHTS := [0.3, 0.4, 0.3]
## Память о цели после потери из виду, с.
const AI_MEMORY_SEC := 12.0
## Бой: дистанция открытия огня, интервал выстрелов, разброс, урон (старые — для ai_test/сектора).
const AI_ENGAGE_RANGE := 32.0
const AI_FIRE_INTERVAL := 0.75
const AI_SPREAD_DEG := 7.0
const AI_DAMAGE := 9.0
## Оружие мародёров: доля в отряде (weight), магазин, перезарядка (с), интервал выстрелов (с),
## очередь (выстрелов) и пауза между очередями (с), урон за пулю/дробину, дробин, разброс (град),
## дальность боя (м), шум выстрела (м), звук, модель; item/ammo — что выпадает с трупа (ствол и патроны).
## Как ИИ стреляет по классу оружия (само оружие, магазины и патроны — из снаряжения ИИ,
## data/loadouts.json): очередь, пауза между очередями, не чаще interval_min, разброс, дальность
## боя. Урон — от патрона × AI_DAMAGE_K (пробитие брони — как у патрона).
const AI_CLASS := {
	"PISTOL": {"burst": 1, "burst_pause": 0.0, "interval_min": 0.42, "spread": 3.5, "range": 60.0},
	"SMG": {"burst": 4, "burst_pause": 0.6, "interval_min": 0.08, "spread": 3.2, "range": 70.0},
	"PDW": {"burst": 4, "burst_pause": 0.6, "interval_min": 0.07, "spread": 3.0, "range": 80.0},
	"SHOTGUN": {"burst": 1, "burst_pause": 0.0, "interval_min": 0.6, "spread": 3.5, "range": 40.0},
	"ASSAULT_RIFLE": {"burst": 3, "burst_pause": 0.75, "interval_min": 0.11, "spread": 2.2, "range": 120.0},
	"CARBINE": {"burst": 3, "burst_pause": 0.7, "interval_min": 0.1, "spread": 2.0, "range": 120.0},
	"BATTLE_RIFLE": {"burst": 2, "burst_pause": 0.85, "interval_min": 0.12, "spread": 1.8, "range": 150.0},
	"DMR": {"burst": 1, "burst_pause": 0.5, "interval_min": 0.9, "spread": 0.7, "range": 250.0},
	"SNIPER": {"burst": 1, "burst_pause": 0.0, "interval_min": 1.7, "spread": 0.4, "range": 400.0},
	"SPECIAL": {"burst": 3, "burst_pause": 0.7, "interval_min": 0.11, "spread": 2.4, "range": 100.0},
	"LMG": {"burst": 6, "burst_pause": 1.0, "interval_min": 0.075, "spread": 2.8, "range": 150.0},
}
## Патроны у мародёров не кончаются: перезарядка (с анимацией и временем) берёт полный магазин,
## запасные не тратятся — «Пустой!» и отход без патронов не бывает.
const AI_INFINITE_AMMO := true
## Урон пуль ИИ по игроку — доля урона патрона (ИИ стреляет часто и много, но бьёт ощутимо).
const AI_DAMAGE_K := 0.6
## Баллистика по классу оружия (у всех — игрок и ИИ, Hitscan): range — куда долетает пуля, м
## (× range_k патрона); с eff, м, урон и пробитие падают к концу дальности до dmg_min / pen_min.
## Дробь слабеет быстро; пуля из ружья — SHOTGUN_SLUG.
const BALLISTICS := {
	"PISTOL": {"range": 100.0, "eff": 25.0, "dmg_min": 0.5, "pen_min": 0.6},
	"SMG": {"range": 150.0, "eff": 40.0, "dmg_min": 0.5, "pen_min": 0.6},
	"PDW": {"range": 150.0, "eff": 50.0, "dmg_min": 0.55, "pen_min": 0.7},
	"SPECIAL": {"range": 250.0, "eff": 80.0, "dmg_min": 0.55, "pen_min": 0.7},
	"ASSAULT_RIFLE": {"range": 300.0, "eff": 100.0, "dmg_min": 0.6, "pen_min": 0.7},
	"CARBINE": {"range": 300.0, "eff": 100.0, "dmg_min": 0.6, "pen_min": 0.7},
	"BATTLE_RIFLE": {"range": 500.0, "eff": 150.0, "dmg_min": 0.65, "pen_min": 0.75},
	"LMG": {"range": 500.0, "eff": 150.0, "dmg_min": 0.65, "pen_min": 0.75},
	"DMR": {"range": 800.0, "eff": 250.0, "dmg_min": 0.7, "pen_min": 0.8},
	"SNIPER": {"range": 1000.0, "eff": 300.0, "dmg_min": 0.75, "pen_min": 0.85},
	"SHOTGUN": {"range": 100.0, "eff": 8.0, "dmg_min": 0.12, "pen_min": 0.15},
}
const SHOTGUN_SLUG := {"eff": 30.0, "dmg_min": 0.45, "pen_min": 0.55}
## Дробь в упор: ближе pb_m, м, урон дробины × pb_k — в упор дробовик валит с одного выстрела.
const SHOTGUN_POINT_BLANK := {"pb_m": 4.0, "pb_k": 2.2}
## Сколько ИИ перезаряжается, с: время оружия × это.
const AI_RELOAD_K := 1.1
## Типы мародёров: доля среди всех (weight), снаряжение (loadout — data/loadouts.json: оружие,
## магазины, броня, шлем, гарнитура, аптечки; leader — с этим шансом главарь), скорость ×,
## здоровье ×, память ×, дальность зрения ×, цвет куртки, фигура (масштаб), holds — держит
## позицию: не сближается, патруль у своего поста, ищет глазами, а не ногами (снайпер ходит один).
const AI_ARCHETYPES := {
	"scout": {"name": "Разведчик", "weight": 0.4, "loadout": "scav_poor", "speed": 1.3, "hp": 0.85,
		"memory": 0.5, "view": 1.1, "color": Color(0.46, 0.4, 0.28), "scale": Vector3(0.9, 1.0, 0.9), "holds": false},
	"gunner": {"name": "Штурмовик", "weight": 0.42, "loadout": "scav_standard", "leader": {"chance": 0.1, "loadout": "scav_leader"}, "speed": 1.0, "hp": 1.0,
		"memory": 1.0, "view": 1.0, "color": Color(0.36, 0.2, 0.16), "scale": Vector3(1.0, 1.0, 1.0), "holds": false},
	"heavy": {"name": "Бывалый", "weight": 0.1, "loadout": "scav_veteran", "speed": 0.85, "hp": 1.2,
		"memory": 1.3, "view": 0.95, "color": Color(0.18, 0.22, 0.2), "scale": Vector3(1.18, 1.03, 1.18), "holds": false},
	"sniper": {"name": "Снайпер", "weight": 0.08, "loadout": "scav_sniper", "speed": 0.9, "hp": 0.9,
		"memory": 1.5, "view": 2.2, "color": Color(0.3, 0.33, 0.24), "scale": Vector3(0.95, 1.0, 0.95), "holds": true},
	# третья сторона — не выпадают случайно (weight 0): ставят события и уровень
	# «Периметр» — не толще людей: опасны снаряжением (броня, патроны), меткостью и слаженностью
	"pmc": {"name": "ЧВК «Периметр»", "weight": 0.0, "loadout": "perimeter_rifleman", "speed": 1.05, "hp": 1.0,
		"memory": 1.4, "view": 1.2, "color": Color(0.1, 0.12, 0.15), "scale": Vector3(1.08, 1.02, 1.08), "holds": false,
		"faction": "pmc", "loots": false},
	"resident": {"name": "Жилец", "weight": 0.0, "loadout": "civilian", "speed": 0.95, "hp": 1.0,
		"memory": 1.0, "view": 0.9, "color": Color(0.55, 0.48, 0.38), "scale": Vector3(0.96, 0.98, 0.96), "holds": false,
		"faction": "resident", "loots": false},
	# чужие отряды (RivalRaids): пришли за добычей, как и игроки, — обыскивают, уносят, воюют со всеми
	"rival": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_veteran", "leader": {"chance": 0.0, "loadout": "scav_leader"},
		"speed": 1.08, "hp": 1.0, "memory": 1.3, "view": 1.15, "color": Color(0.2, 0.24, 0.3),
		"scale": Vector3(1.02, 1.0, 1.02), "holds": false, "faction": "rival"},
	"rival_scout": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_standard", "speed": 1.25, "hp": 0.9,
		"memory": 0.9, "view": 1.2, "color": Color(0.26, 0.28, 0.22), "scale": Vector3(0.94, 1.0, 0.94), "holds": false,
		"faction": "rival"},
	"rival_sniper": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_sniper", "speed": 0.95, "hp": 0.9,
		"memory": 1.5, "view": 2.0, "color": Color(0.24, 0.27, 0.2), "scale": Vector3(0.96, 1.0, 0.96), "holds": false,
		"faction": "rival"},
}
## Кто кому враг (фракции ИИ). Игрок — враг мародёрам и ЧВК; жильцам — только если к ним полез
## (зашёл к ним, стрелял рядом, попал) или группа враждебная с самого начала.
## Чужие отряды («rival») враждуют со всеми, и друг с другом тоже — свои только в своём отряде.
const AI_HOSTILE := {"marauder": ["pmc", "resident", "rival"], "pmc": ["marauder", "resident", "rival"],
	"resident": ["marauder", "pmc", "rival"], "rival": ["marauder", "pmc", "resident", "rival"]}
## Чужие отряды в рейде (RivalRaids, docs/design/rival_raids.md): сколько отрядов (squads — для 1, 2, 3
## игроков, [от, до]; решение владельца 2026-10-14: у троих 2–3) и бойцов; когда входят
## (с от начала рейда); не ближе стольких метров к игрокам; сколько грабят, прежде чем идти к выходу, с;
## уходят раньше, если в сумках набралось столько записей или отряд потерял такую долю состава;
## у выхода стоят столько секунд в зоне такого радиуса (без боя) — и уходят с добычей; шанс, что
## отряд первым делом пойдёт за ключом, который лежит на карте (за запертой дверью добыча лучше).
## О входе и выходе отрядов по рации говорят всем и всегда (решение владельца, 2026-10-10).
const RIVALS := {"squads": [[1, 1], [1, 2], [2, 3]], "size": [2, 3], "enter_sec": [15.0, 260.0], "spawn_min_m": 55.0,
	"loot_sec": [200.0, 380.0], "pack_goal": 5, "loss_share": 0.5, "extract_sec": 18.0, "extract_m": 7.0,
	"key_chance": 0.5,
	# бой между группами (владелец, 2026-10-09 / 2026-10-11). Отряд, потерявший в бою бойца (убит или лежит),
	# разрывает контакт: бегом к своему выходу retreat_sec секунд и уходит из рейда; «крысы» отходят при
	# первом же контакте, если в сумках уже есть flee_packed записей. Повторно отступать — не раньше
	# rearm_sec (прижали — дерутся). Победители не гонятся дальше pursuit_m от места боя. Бой стих на
	# calm_sec — ведущий обыскивает тела (не больше sweep_bodies, не дальше sweep_m от места боя, не дольше
	# sweep_sec), остальные встают вокруг на cover_m лицом наружу.
	"retreat_sec": 14.0, "rearm_sec": 25.0, "flee_packed": 2, "pursuit_m": 40.0, "calm_sec": 6.0,
	"sweep_m": 30.0, "sweep_sec": 50.0, "sweep_bodies": 3, "cover_m": 5.0}
## Птицы на открытой карте (BirdFlocks; число стай можно переопределить в данных карты, ключ "birds"):
## sitting / circling — сидящих стай и кружащих в небе; flock — птиц в стае; crow_share — доля вороньих стай
## (остальные — голуби, они не каркают); perches_per_district — мест посадки на район; sit_spread_m —
## разброс сидящих. Взлетают: от шума — на расстоянии радиус шума × noise_k, но не дальше noise_cap_m;
## от шагов по шине шума — не дальше step_m; кто идёт быстрее walk_speed ближе near_m или подошёл на
## touch_m — тоже (проверка раз в scan_sec). Взлёт: разом за takeoff_spread_sec, набор высоты climb_sec,
## кружат air_sec, садятся land_sec; circle_r / circle_h — радиус и высота круга, м; speed — м/с.
## В дождь остаётся доля rain_k стай, ночью птиц нет. idle_caw_sec — как часто каркают кружащие.
## ai_noise_m — слышат ли взлёт мародёры (0 — нет). Звук: громкость, «единица» и предел слышимости.
const BIRDS := {"sitting": 14, "circling": 3, "flock": [5, 11], "crow_share": 0.6, "perches_per_district": 5, "sit_spread_m": 2.6,
	"noise_k": 0.8, "noise_cap_m": 90.0, "step_m": 7.0, "near_m": 9.0, "touch_m": 3.5, "walk_speed": 2.2, "scan_sec": 0.4,
	"takeoff_spread_sec": 0.7, "climb_sec": 4.0, "air_sec": [35.0, 80.0], "land_sec": 6.0,
	"circle_r": [7.0, 15.0], "circle_h": [16.0, 30.0], "speed": 9.0, "rain_k": 0.4, "idle_caw_sec": [9.0, 26.0],
	"ai_noise_m": 0.0, "start_sec": 2.0, "sound_db": 2.0, "sound_unit": 22.0, "sound_max_m": 260.0}
## Жильцы: сколько групп, по сколько, доля враждебных сразу; ближе стольких метров к их
## магазину — «полез к ним»; враждебные стреляют с такого расстояния.
const RESIDENTS := {"groups": [1, 2], "size": [2, 3], "hostile_share": 0.3, "trespass_m": 7.0, "hostile_m": 22.0}
## События рейда (RaidEvents): шансы и когда (от и до, с). Отключение / авария генератора — только
## если свет был; сирена: сколько воет, докуда слышно, сколько отключать у пульта, с; задание по рации: какие вещи, во сколько
## раз дороже цены платит Михалыч; починка генератора, с.
const RAID_EVENTS := {
	"outage_chance": 0.25, "outage_at": [180.0, 720.0],
	"generator_chance": 0.25, "generator_at": [180.0, 720.0], "repair_sec": 8.0,
	"drop_chance": 0.35, "drop_at": [240.0, 780.0], "drop_noise_m": 160.0, "drop_smoke_sec": 90.0,
	"pmc_chance": 0.35, "pmc_at": [300.0, 900.0],
	"alarm_shops": 2, "alarm_sec": 120.0, "alarm_noise_m": 70.0, "alarm_off_sec": 3.0,
	"radio_items": ["laptop", "gpu", "server_drive", "camera", "documents", "diamond_ring"], "radio_at": [120.0, 360.0], "radio_mult": 3,
}
## Генератор ТЦ (MallGenerator): гул работающего (громкость, дБ; 1:1 до, слышно до, м), лязг
## ремонта раз в clank_sec — мародёры слышат на clank_noise_m; мигание лампы сломанного, Гц;
## проход вокруг корпуса без пропсов, м.
const MALL_GENERATOR := {"hum_db": -6.0, "hum_unit_m": 5.0, "hum_max_m": 40.0, "clank_sec": 1.2, "clank_noise_m": 45.0, "blink_hz": 1.5, "keepout_m": 1.2}
## Раненый мародёр кричит — товарищи в радиусе, м, идут спасать: тащат за укрытие (до
## AI_DRAG_COVER_M), поднимают за AI_REVIVE_SEC. Лёжа стреляет из пистолета.
const AI_RESCUE_RADIUS := 28.0
const AI_DRAG_COVER_M := 12.0
const AI_DRAG_SPEED := 1.4
const AI_REVIVE_SEC := 6.0
## Добивают лежащего игрока, только если другие не стреляют столько секунд (лежащий сам
## стреляет — его и добивают).
const AI_FINISH_QUIET_SEC := 4.0
## Мародёры тоже ищут припасы: ведущий отряда идёт к ближайшему неразграбленному контейнеру
## (не дальше AI_LOOT_RANGE, не занятому другим отрядом — метка на AI_LOOT_CLAIM_SEC), роется
## (обыск контейнера × AI_LOOT_SEARCH_MULT, не меньше AI_LOOT_SEARCH_MIN, слышно), забирает самое
## ценное (до AI_LOOT_TAKE записей, всего в сумке до AI_LOOT_PACK_MAX) и идёт дальше. Сумка
## выпадает с трупа.
const AI_LOOT_RANGE := 60.0
const AI_LOOT_CLAIM_SEC := 90.0
const AI_LOOT_SEARCH_MULT := 4.0
const AI_LOOT_SEARCH_MIN := 3.0
const AI_LOOT_TAKE := 2
const AI_LOOT_PACK_MAX := 6
## Роли отрядов в бою (по порядку вступления в бой у одной цели, в радиусе AI_ROLE_RADIUS):
## штурм (давит, гранаты), обход (широко, на AI_ROLE_FLANK_OFFSET в сторону), прикрытие
## (позиция с обзором цели в AI_OVERWATCH_DIST, держит место огнём). Роль гаснет, когда отряд
## AI_ROLE_FORGET_SEC не в бою.
const AI_ROLE_RADIUS := 60.0
const AI_ROLE_FLANK_OFFSET := 20.0
const AI_OVERWATCH_DIST := [15.0, 35.0]
const AI_ROLE_FORGET_SEC := 25.0
## Гранаты мародёров: дальность броска (от и до, м), перезарядка, с, сколько у каждого, цель не
## видна хотя бы столько, с; своих ближе AI_GRENADE_SAFE_M к точке — не кидает.
const AI_GRENADE := {"range": [8.0, 22.0], "cooldown": 18.0, "count": 1, "min_unseen": 1.5, "safe_m": 7.0}
## Держит позицию: патрульные точки — не дальше стольких метров от поста, м.
const AI_HOLD_PATROL_R := 12.0
## Реакция на попадание: сколько секунд «ведёт» (скорость ×, разброс ×), задержка следующего выстрела, с.
const AI_HIT_STAGGER_SEC := 0.45
const AI_HIT_STAGGER_SPEED := 0.3
const AI_HIT_STAGGER_SPREAD := 1.8
const AI_HIT_FLINCH_DELAY := 0.3
## Точность: только что замеченная цель — разброс × AI_AIM_COLD, за AI_AIM_SETTLE_SEC сходится к 1.
## Цель бежит — × AI_TARGET_MOVING; сам на ходу — × AI_SELF_MOVING.
const AI_AIM_COLD := 2.4
const AI_AIM_SETTLE_SEC := 1.4
## Прицел садится дольше на дальней цели: AI_AIM_SETTLE_SEC вблизи (до near_m) → far_sec (с far_m).
const AI_AIM_SETTLE_FAR := {"near_m": 10.0, "far_m": 120.0, "far_sec": 4.0}
const AI_TARGET_MOVING := 1.5
const AI_SELF_MOVING := 1.7
## Окрик «контакт»: докуда слышно, м, и как часто повторять, пока видит цель, с.
const AI_CALLOUT_RADIUS := 32.0
## Реплика мародёра текстом над головой видна только ближе этого, м (и не сквозь стены): издали
## надпись висела в воздухе мелкой строчкой.
const AI_SAY_TEXT_M := 14.0
const AI_CALLOUT_EVERY := 3.0
## Укрытие: поиск в радиусе, м; сколько сидеть, прежде чем выглянуть, и сколько стрелять, выглянув, с.
const AI_COVER_RADIUS := 10.0
const AI_COVER_HIDE := [0.8, 1.8]
const AI_COVER_PEEK := [1.2, 2.4]
## В укрытие — после попадания или если рядом свистят пули (слышал выстрел цели ближе, м).
const AI_SUPPRESS_RADIUS := 12.0
## Раненый (меньше этой доли HP) без товарищей рядом — отходит в дальнее укрытие.
const AI_RETREAT_HP := 0.35
const AI_RETREAT_HOLD := [6.0, 10.0]
## Обход: на сколько метров в сторону от цели заходит второй в отряде.
const AI_FLANK_OFFSET := 11.0
## Поиск после потери цели: сколько точек осмотреть вокруг последней известной, до какого радиуса, м
## (прочёсывание: от ближних к дальним, дугой; точки, которые уже смотрит другой, — пропускаются
## ближе AI_SEARCH_CLAIM_M). После проверки шума — AI_INVESTIGATE_SEARCH точек.
const AI_SEARCH_POINTS := 6
const AI_SEARCH_RADIUS := 18.0
const AI_SEARCH_CLAIM_M := 5.0
const AI_INVESTIGATE_SEARCH := 2
## Попадание от невидимого стрелка: направление угадывается с ошибкой (град), дальность — ± доля.
const AI_HIT_DIR_ERR_DEG := 15.0
const AI_HIT_DIST_ERR := 0.3
## Продвижение перебежками к цели, которую не видно: шаг от и до, м; ближе AI_ADVANCE_MIN_DIST — идёт прямо.
const AI_ADVANCE_STEP := [5.0, 12.0]
const AI_ADVANCE_MIN_DIST := 10.0
## Не толпиться: куда идёт другой мародёр ближе стольких метров — туда не идём, точка сдвигается
## на AI_SPREAD_RADIUS в сторону. Шум, который уже проверяет другой отряд (AI_INVESTIGATE_SHARE_M
## от него), не проверяем — если только он не ближе AI_INVESTIGATE_NEAR.
const AI_SPREAD_CLAIM_M := 2.5
const AI_SPREAD_RADIUS := [2.5, 6.0]
const AI_INVESTIGATE_SHARE_M := 12.0
const AI_INVESTIGATE_NEAR := 15.0
## Слух: падение тела товарища слышно в радиусе, м.
const AI_DEATH_NOISE := 22.0
## Строй патруля: ведомые держатся на таком расстоянии за ведущим, м.
## Сетка путей на рельефе лежит не точно по земле (на городской карте — до пары метров выше или ниже):
## на сколько метров по высоте точка пути может отстоять от ног мародёра и всё равно считаться достигнутой.
## Без этого бот вставал под точкой пути и стоял: по горизонтали дошёл, по высоте «не достал».
const AI_PATH_HEIGHT_FIX := 2.2
## Мародёр упёрся (хочет идти, а стоит): через stuck_sec — шаг вбок на side_sec; не помогло tries раз
## подряд в обходе — берёт другую точку обхода. Скорость ниже min_speed считается «стоит».
const AI_UNSTUCK := {"stuck_sec": 2.0, "side_sec": 0.7, "tries": 3, "min_speed": 0.25}
const AI_FOLLOW_DIST := 2.6
## Отряды: сколько в отряде (от и до).
const AI_SQUAD_SIZE := [1, 3]
## Патруль: пауза на точке, с.
const AI_PATROL_PAUSE := [1.5, 4.0]
## Расследование: сколько стоять на месте шума, прежде чем вернуться к патрулю, с.
const AI_INVESTIGATE_LINGER := 5.0

## Большая городская карта: бюджеты отрисовки и точность заранее выпеченной навигации.
const URBAN_WORLD := {
	"batch_cell": 64.0, "prop_distance": 650.0, "view_distance": 2400.0,
	"deck_margin": 0.25,
	"nav_tile": 250.0, "nav_cell": 0.5, "nav_height": 0.25, "nav_border": 2.0,
	"nav_radius": 0.5, "nav_agent_height": 1.8, "nav_climb": 0.4, "nav_slope": 40.0,
	"nav_merge_scale": 0.125,
	"nav_detail_error": 2.0,
	"extract_seconds": 8.0,
}

## Лазерная метка: ресурс головки — единственное ограничение частоты нанесения.
const ENGRAVING := {"charges": 3, "max_text": 24, "width": 0.065, "pistol_width": 0.045,
	"fade_begin": 3.0, "fade_length": 5.0, "cache": 32, "head_chance": 0.012,
	"head_tables": ["electronics", "tools"], "cargo_search_s": 8.0,
	"head_value": 12000, "spent_value": 500, "guards": 3, "guard_radius": 8.0,
	"parts_loot": {"engraver_frame": {"tables": ["tools"], "chance": 0.025, "value": 8500},
		"engraver_controller": {"tables": ["electronics"], "chance": 0.025, "value": 6000}}}
## Наклейки на оружии (Stickers, решения владельца 2026-10-11): не больше max на стволе; «Счёт» (tally)
## получает зарубку за эвакуацию со стволом, до tally_max; сторона наклейки на длинном стволе и на
## пистолете, м (× размер по выбору, WeaponMark.SCALES); aspect — ширина к высоте, если не квадрат.
const STICKERS := {"max": 3, "tally": "sticker_tally", "tally_max": 25, "size_m": 0.034, "pistol_size_m": 0.022,
	"ids": ["sticker_skull", "sticker_tally", "sticker_shark", "sticker_perimeter"], "aspect": {"sticker_tally": 2.0},
	# принтер наклеек (задание «Фирменный знак»): что печатает (эмблему ЧВК — нет, её только находят), на одну
	# наклейку — лист film и доля комплекта ink (комплекта хватает на ink_sheets листов); после задания
	# Михалыч продаёт film; первая печать — из его остатков (free_prints)
	"printable": ["sticker_skull", "sticker_tally", "sticker_shark"], "film": "sticker_film", "ink": "ink_set", "ink_sheets": 4,
	"printer_flag": "printer_ready", "free_prints": 1}
## Возврат оставленного оружия в следующих рейдах владельца в той же зоне кампании.
const WEAPON_RECOVERY := {"raids": 5, "chance": 0.25, "checkpoint_sec": 1.0}

## Гражданский лут: базовая оценка. Михалыч покупает с TRADER_SELL_MULT.
const CIVILIAN_LOOT_VALUES := {
	"circuit_board": 10500,
	"pliers": 1200,
	"screwdriver": 700,
	"measuring_tape": 900,
	"hammer": 1100,
	"pipe_wrench": 1900,
	"multimeter": 7800,
	"oil_tin": 1400,
	"thermos": 1700,
	"kettle": 2400,
	"radio_transceiver": 14000,
	"cassette_player": 3200,
	"video_camera": 11500,
	"binoculars": 8500,
	"wall_clock": 1800,
	"work_gloves": 500,
	"clipboard": 600,
	"empty_jerrycan": 2200,
	"medical_case": 1600,
	"metal_toolbox": 2800,
	"bench_vice": 3600,
	"desk_lamp": 2600,
	"junction_box": 2800,
	"power_unit": 6400
}
## Тематические матрицы: [минимум, максимум] бросков, затем [предмет, вес, количество].
const CIVILIAN_LOOT := {
	"register": {"rolls": [1, 2], "entries": [
		["cash", 5, [1, 3]], ["cigarettes", 2, [1, 2]], ["lighter", 1, [1, 1]], ["measuring_tape", 0.3, [1, 1]],
		["nothing", 2, [0, 0]]
	]},
	"shelf": {"rolls": [1, 1], "entries": [
		["water", 3, [1, 1]], ["energy_bar", 3, [1, 2]], ["lighter", 2, [1, 1]], ["perfume", 1, [1, 1]],
		["thermos", 1.5, [1, 1]], ["wall_clock", 0.8, [1, 1]], ["work_gloves", 2, [1, 1]], ["kettle", 0.8, [1, 1]],
		["nothing", 5, [0, 0]]
	]},
	"grocery": {"rolls": [1, 2], "entries": [
		["water", 4, [1, 1]], ["canned", 4, [1, 1]], ["energy_bar", 3, [1, 2]], ["cigarettes", 1, [1, 2]],
		["thermos", 0.8, [1, 1]], ["kettle", 0.5, [1, 1]], ["work_gloves", 0.7, [1, 1]], ["nothing", 2, [0, 0]]
	]},
	"pharmacy": {"rolls": [1, 2], "entries": [
		["bandage", 5, [1, 3]], ["painkillers", 4, [1, 2]], ["medkit", 1, [1, 1]], ["medical_case", 0.8, [1, 1]],
		["clipboard", 0.7, [1, 1]], ["nothing", 2, [0, 0]]
	]},
	"electronics": {"rolls": [1, 2], "entries": [
		["phone", 3, [1, 1]], ["headphones", 3, [1, 1]], ["powerbank", 3, [1, 1]], ["camera", 1, [1, 1]],
		["laptop", 1, [1, 1]], ["wires", 2, [1, 2]], ["circuit_board", 0.65, [1, 1]], ["multimeter", 0.5, [1, 1]],
		["radio_transceiver", 0.2, [1, 1]], ["cassette_player", 1.5, [1, 1]], ["video_camera", 0.4, [1, 1]], ["power_unit", 0.4, [1, 1]],
		["junction_box", 1, [1, 1]], ["desk_lamp", 1.2, [1, 1]], ["nothing", 4, [0, 0]]
	]},
	"tools": {"rolls": [1, 2], "entries": [
		["wires", 4, [1, 2]], ["battery", 2, [1, 1]], ["toolset", 1, [1, 1]], ["screwdriver", 3, [1, 1]],
		["pliers", 2, [1, 1]], ["hammer", 2, [1, 1]], ["pipe_wrench", 1.5, [1, 1]], ["measuring_tape", 2, [1, 1]],
		["work_gloves", 2, [1, 1]], ["oil_tin", 1.5, [1, 1]], ["metal_toolbox", 1, [1, 1]], ["bench_vice", 0.5, [1, 1]],
		["multimeter", 0.4, [1, 1]], ["junction_box", 1, [1, 1]], ["empty_jerrycan", 0.8, [1, 1]], ["nothing", 5, [0, 0]],
		["spray_paint", 1.2, [1, 2]], ["stencil_kit", 0.5, [1, 1]]
	]},
	"storage": {"rolls": [1, 2], "entries": [
		["water", 3, [1, 1]], ["canned", 3, [1, 1]], ["wires", 2, [1, 2]], ["battery", 1, [1, 1]],
		["cigarettes", 1, [1, 2]], ["work_gloves", 1.5, [1, 1]], ["oil_tin", 1, [1, 1]], ["metal_toolbox", 0.6, [1, 1]],
		["empty_jerrycan", 0.6, [1, 1]], ["junction_box", 0.7, [1, 1]], ["screwdriver", 1, [1, 1]], ["nothing", 6, [0, 0]],
		["spray_paint", 0.8, [1, 1]], ["sticker_film", 0.7, [1, 2]], ["printer_body", 0.12, [1, 1]], ["rig_belt", 0.3, [1, 1]]
	]},
	"office": {"rolls": [1, 2], "entries": [
		["documents", 1, [1, 1]], ["cash", 2, [1, 1]], ["phone", 1, [1, 1]], ["powerbank", 2, [1, 1]],
		["painkillers", 1, [1, 1]], ["lighter", 2, [1, 1]], ["clipboard", 2, [1, 1]], ["desk_lamp", 1, [1, 1]],
		["wall_clock", 1, [1, 1]], ["thermos", 1, [1, 1]], ["cassette_player", 0.7, [1, 1]], ["nothing", 4, [0, 0]],
		["sticker_film", 1.2, [1, 2]], ["ink_set", 0.8, [1, 1]], ["stencil_kit", 0.3, [1, 1]], ["printer_body", 0.2, [1, 1]],
		["printer_board", 0.15, [1, 1]], ["sticker_tally", 0.4, [1, 2]]
	]},
	"bank": {"rolls": [1, 2], "entries": [
		["cash", 5, [2, 5]], ["documents", 2, [1, 1]], ["clipboard", 1, [1, 1]], ["desk_lamp", 0.5, [1, 1]],
		["nothing", 2, [0, 0]]
	]},
	"kiosk": {"rolls": [1, 2], "entries": [
		["cigarettes", 4, [1, 3]], ["lighter", 3, [1, 2]], ["energy_bar", 3, [1, 2]], ["cash", 1, [1, 1]],
		["thermos", 0.5, [1, 1]], ["cassette_player", 0.4, [1, 1]], ["measuring_tape", 0.5, [1, 1]],
		["sticker_skull", 0.5, [1, 2]], ["sticker_tally", 0.5, [1, 2]], ["sticker_shark", 0.12, [1, 1]]
	]},
	"server_rack": {"rolls": [1, 2], "entries": [
		["server_drive", 3, [1, 1]], ["gpu", 2, [1, 1]], ["wires", 2, [1, 2]], ["circuit_board", 2, [1, 1]],
		["power_unit", 1, [1, 1]], ["multimeter", 0.3, [1, 1]], ["junction_box", 1, [1, 1]],
		["printer_head", 0.3, [1, 1]], ["printer_board", 0.4, [1, 1]]
	]},
	"sport": {"rolls": [1, 1], "entries": [
		["ammo_12_buck", 2, [5, 15]], ["ammo_12_slug", 1, [5, 10]], ["ammo_556_civ", 0.5, [10, 20]], ["headset_passive", 0.5, [1, 1]],
		["bipod_01", 0.2, [1, 1]], ["water", 2, [1, 1]], ["binoculars", 0.6, [1, 1]], ["thermos", 1, [1, 1]],
		["work_gloves", 1, [1, 1]], ["nothing", 4, [0, 0]], ["rig_belt", 0.6, [1, 1]], ["rig_chest", 0.3, [1, 1]]
	]},
	"home": {"rolls": [1, 2], "entries": [
		["thermos", 2, [1, 1]], ["kettle", 2, [1, 1]], ["wall_clock", 2, [1, 1]], ["cassette_player", 1.5, [1, 1]],
		["work_gloves", 1, [1, 1]], ["desk_lamp", 1.5, [1, 1]], ["video_camera", 0.3, [1, 1]], ["binoculars", 0.4, [1, 1]],
		["nothing", 4, [1, 1]], ["rig_belt", 0.25, [1, 1]]
	]},
	"components": {"rolls": [1, 2], "entries": [
		["wires", 4, [1, 1]], ["battery", 2, [1, 1]], ["junction_box", 3, [1, 1]], ["power_unit", 1.5, [1, 1]],
		["circuit_board", 0.8, [1, 1]], ["multimeter", 0.5, [1, 1]], ["nothing", 5, [1, 1]]
	]},
	"workshop": {"rolls": [1, 2], "entries": [
		["pliers", 2, [1, 1]], ["screwdriver", 3, [1, 1]], ["measuring_tape", 2, [1, 1]], ["hammer", 2, [1, 1]],
		["pipe_wrench", 1.5, [1, 1]], ["oil_tin", 2, [1, 1]], ["work_gloves", 2, [1, 1]], ["metal_toolbox", 1, [1, 1]],
		["bench_vice", 0.6, [1, 1]], ["empty_jerrycan", 1, [1, 1]], ["multimeter", 0.35, [1, 1]], ["power_unit", 0.6, [1, 1]],
		["nothing", 5, [1, 1]]
	]},
}
## Свет от экрана телевизора в убежище (живая лампа TvGlow, в запечённый свет не входит): яркость,
## дальность и спад; static_k — «помехи» ярче; flicker — доля, на которую картинка «дышит», и как
## часто (раз в секунду); white — насколько цвет канала разбавлен белым (экран светит не чистым синим). С тенями — свет не проходит в соседние помещения. Было 0.28 на 2.6 м:
## в тёмной комнате экран горел, а комнату не было видно совсем.
const TV_LIGHT := {"energy": 1.5, "range": 9.0, "attenuation": 1.0, "static_k": 1.2, "flicker": 0.14, "flicker_hz": 2.2, "shadows": true, "white": 0.35}
## Снаряжение, которое может лежать на виду (точки LooseLoot) в теме, кроме гражданских находок:
## [предмет, вес] — вес в одном ряду с весами темы. Разгрузки — в спорттоварах, у охраны, на складе, дома.
const LOOSE_GEAR := {
	"sport": [["rig_belt", 0.3], ["rig_chest", 0.15]],
	"security": [["rig_belt", 0.4], ["rig_chest", 0.25]],
	"storage": [["rig_belt", 0.12]],
	"home": [["rig_belt", 0.12]],
}
## Отдельный предмет на опоре: шанс на точку, отсечение вдали, зазор от поверхности.
const LOOSE_LOOT := {"chance": 0.42, "distance": 65.0, "surface_gap": 0.002, "floor_points": 0.16}

## Ценные находки: цены, тематические веса и содержимое вскрываемых комплектов.
const VALUABLE_LOOT_VALUES := {
	"gpu_compute": 92000,
	"gpu_gaming": 54000,
	"ssd_sata": 12500,
	"ssd_nvme": 24000,
	"ram_desktop": 7500,
	"ram_server": 19000,
	"cpu_desktop": 28000,
	"cpu_server": 62000,
	"switch_managed": 26000,
	"router_industrial": 21500,
	"thermal_imager": 78000,
	"nvg_tube": 88000,
	"laser_rangefinder": 16500,
	"satellite_modem": 48000,
	"oscilloscope_portable": 34000,
	"laptop_business": 38000,
	"laptop_workstation": 76000,
	"smartphone_business": 22000,
	"photo_camera_pro": 68000,
	"motherboard_server": 28500,
	"cctv_bullet": 14500,
	"cctv_dome": 17500,
	"microscope_digital": 58000,
	"cpu_cooling_kit": 18500,
	"part_pm_barrel": 6500,
	"part_pm_slide": 11500,
	"part_pm_hammer": 4200,
	"part_pm_trigger": 3000,
	"part_pm_safety": 2700,
	"part_glock_barrel": 12000,
	"part_glock_slide": 23000,
	"part_glock_recoil": 6500,
	"part_glock_trigger": 10500,
	"part_glock_extractor": 4500,
	"part_veras_receiver": 19500,
	"part_veras_stock": 7500,
	"part_veras_muzzle": 5200,
	"part_veras_mag_body": 3900,
	"weapon_cleaning_kit": 8500,
	"weapon_gauges": 14500,
	"microscope_optical": 42000,
	"surgical_tape": 1600,
	"suture_kit": 8500,
	"scalpel_kit": 12500,
	"hemostat_kit": 10500,
	"dental_kit": 18000,
	"orthopedic_kit": 24000,
	"intubation_kit": 21000,
	"diagnostic_kit": 15500,
	"sterile_dressing_kit": 6500,
	"antibiotics_pack": 11500,
	"anesthetic_pack": 14500,
	"insulin_pack": 22000,
	"antiseptic_pack": 5500,
	"hemostatic_pack": 17500,
	"iv_solution_pack": 8500,
	"car_tire": 7500,
	"car_rim": 5500,
	"tire_pump": 4200,
	"auto_lubricant": 2200,
	"precision_oiler": 2800,
	"ratchet_socket": 4500,
	"alternator_rebuild": 14500,
	"injector_set": 24500,
	"car_ecu": 19500,
	"timing_kit": 12500,
	"brake_service_kit": 8500,
	"bearing_set": 9500,
	"food_milk": 1600,
	"food_tomatoes": 1300,
	"food_beans": 1800,
	"food_sardines": 2200,
	"ration_daily": 6500,
	"ration_patrol": 4200,
	"ration_arctic": 8500,
	"ration_emergency": 5200,
	"freeze_dried_meals": 4500,
	"coffee_pack": 6500,
	"protein_pack": 4800,
	"water_purification": 5500,
	"pack_918_pst": 1800,
	"pack_918_ap": 3520,
	"pack_919_fmj": 3000,
	"pack_919_ap": 4800,
	"pack_45_fmj": 2700,
	"pack_57_ap": 12000,
	"pack_921_ap": 8400,
	"pack_545_std": 5400,
	"pack_545_ap": 10400,
	"pack_939_sp5": 9600,
	"pack_939_sp6": 12600,
	"pack_556_std": 6000,
	"pack_556_ap": 12000,
	"pack_76251_std": 7200,
	"pack_12_buck": 1800,
	"pack_frag": 13500,
	"pack_flares": 6400,
	"pack_chemlights": 3600,
	"signal_launcher": 38000,
	"supply_signal": 28000
}
const LOOT_PACKS := {
	"pack_918_pst": [
		[
			"ammo_918_pst",
			40
		]
	],
	"pack_918_ap": [
		[
			"ammo_918_ap",
			32
		]
	],
	"pack_919_fmj": [
		[
			"ammo_919_fmj",
			50
		]
	],
	"pack_919_ap": [
		[
			"ammo_919_ap",
			30
		]
	],
	"pack_45_fmj": [
		[
			"ammo_45_fmj",
			30
		]
	],
	"pack_57_ap": [
		[
			"ammo_57_ap",
			40
		]
	],
	"pack_921_ap": [
		[
			"ammo_921_ap",
			30
		]
	],
	"pack_545_std": [
		[
			"ammo_545_std",
			60
		]
	],
	"pack_545_ap": [
		[
			"ammo_545_ap",
			40
		]
	],
	"pack_939_sp5": [
		[
			"ammo_939_sp5",
			40
		]
	],
	"pack_939_sp6": [
		[
			"ammo_939_sp6",
			30
		]
	],
	"pack_556_std": [
		[
			"ammo_556_std",
			60
		]
	],
	"pack_556_ap": [
		[
			"ammo_556_ap",
			40
		]
	],
	"pack_76251_std": [
		[
			"ammo_76251_std",
			40
		]
	],
	"pack_12_buck": [
		[
			"ammo_12_buck",
			20
		]
	],
	"pack_frag": [
		[
			"grenade",
			3
		]
	],
	"pack_flares": [
		[
			"flare",
			4
		]
	],
	"pack_chemlights": [
		[
			"chemlight",
			6
		]
	]
}
const VALUABLE_LOOT := {
	"electronics": [
		[
			"gpu_compute",
			0.07
		],
		[
			"gpu_gaming",
			0.18
		],
		[
			"ssd_sata",
			0.5
		],
		[
			"ssd_nvme",
			0.5
		],
		[
			"ram_desktop",
			1
		],
		[
			"ram_server",
			0.5
		],
		[
			"cpu_desktop",
			0.5
		],
		[
			"cpu_server",
			0.07
		],
		[
			"switch_managed",
			0.5
		],
		[
			"router_industrial",
			0.5
		],
		[
			"thermal_imager",
			0.07
		],
		[
			"nvg_tube",
			0.07
		],
		[
			"laser_rangefinder",
			0.5
		],
		[
			"satellite_modem",
			0.18
		],
		[
			"oscilloscope_portable",
			0.18
		],
		[
			"laptop_business",
			0.18
		],
		[
			"laptop_workstation",
			0.07
		],
		[
			"smartphone_business",
			0.5
		],
		[
			"photo_camera_pro",
			0.07
		],
		[
			"motherboard_server",
			0.5
		],
		[
			"cctv_bullet",
			0.5
		],
		[
			"cctv_dome",
			0.5
		],
		[
			"microscope_digital",
			0.18
		],
		[
			"cpu_cooling_kit",
			0.5
		]
	],
	"office": [
		[
			"gpu_compute",
			0.07
		],
		[
			"gpu_gaming",
			0.18
		],
		[
			"ssd_sata",
			0.5
		],
		[
			"ssd_nvme",
			0.5
		],
		[
			"ram_desktop",
			1
		],
		[
			"ram_server",
			0.5
		],
		[
			"cpu_desktop",
			0.5
		],
		[
			"cpu_server",
			0.07
		],
		[
			"switch_managed",
			0.5
		],
		[
			"router_industrial",
			0.5
		],
		[
			"thermal_imager",
			0.07
		],
		[
			"nvg_tube",
			0.07
		],
		[
			"laser_rangefinder",
			0.5
		],
		[
			"satellite_modem",
			0.18
		],
		[
			"oscilloscope_portable",
			0.18
		],
		[
			"laptop_business",
			0.18
		],
		[
			"laptop_workstation",
			0.07
		],
		[
			"smartphone_business",
			0.5
		],
		[
			"photo_camera_pro",
			0.07
		],
		[
			"motherboard_server",
			0.5
		],
		[
			"cctv_bullet",
			0.5
		],
		[
			"cctv_dome",
			0.5
		],
		[
			"microscope_digital",
			0.18
		],
		[
			"cpu_cooling_kit",
			0.5
		]
	],
	"server_rack": [
		[
			"gpu_compute",
			0.07
		],
		[
			"gpu_gaming",
			0.18
		],
		[
			"ssd_sata",
			0.5
		],
		[
			"ssd_nvme",
			0.5
		],
		[
			"ram_desktop",
			1
		],
		[
			"ram_server",
			0.5
		],
		[
			"cpu_desktop",
			0.5
		],
		[
			"cpu_server",
			0.07
		],
		[
			"switch_managed",
			0.5
		],
		[
			"router_industrial",
			0.5
		],
		[
			"thermal_imager",
			0.07
		],
		[
			"nvg_tube",
			0.07
		],
		[
			"laser_rangefinder",
			0.5
		],
		[
			"satellite_modem",
			0.18
		],
		[
			"oscilloscope_portable",
			0.18
		],
		[
			"laptop_business",
			0.18
		],
		[
			"laptop_workstation",
			0.07
		],
		[
			"smartphone_business",
			0.5
		],
		[
			"photo_camera_pro",
			0.07
		],
		[
			"motherboard_server",
			0.5
		],
		[
			"cctv_bullet",
			0.5
		],
		[
			"cctv_dome",
			0.5
		],
		[
			"microscope_digital",
			0.18
		],
		[
			"cpu_cooling_kit",
			0.5
		]
	],
	"components": [
		[
			"gpu_compute",
			0.07
		],
		[
			"gpu_gaming",
			0.18
		],
		[
			"ssd_sata",
			0.5
		],
		[
			"ssd_nvme",
			0.5
		],
		[
			"ram_desktop",
			1
		],
		[
			"ram_server",
			0.5
		],
		[
			"cpu_desktop",
			0.5
		],
		[
			"cpu_server",
			0.07
		],
		[
			"switch_managed",
			0.5
		],
		[
			"router_industrial",
			0.5
		],
		[
			"thermal_imager",
			0.07
		],
		[
			"nvg_tube",
			0.07
		],
		[
			"laser_rangefinder",
			0.5
		],
		[
			"satellite_modem",
			0.18
		],
		[
			"oscilloscope_portable",
			0.18
		],
		[
			"laptop_business",
			0.18
		],
		[
			"laptop_workstation",
			0.07
		],
		[
			"smartphone_business",
			0.5
		],
		[
			"photo_camera_pro",
			0.07
		],
		[
			"motherboard_server",
			0.5
		],
		[
			"cctv_bullet",
			0.5
		],
		[
			"cctv_dome",
			0.5
		],
		[
			"microscope_digital",
			0.18
		],
		[
			"cpu_cooling_kit",
			0.5
		]
	],
	"home": [
		[
			"gpu_compute",
			0.07
		],
		[
			"gpu_gaming",
			0.18
		],
		[
			"ssd_sata",
			0.5
		],
		[
			"ssd_nvme",
			0.5
		],
		[
			"ram_desktop",
			1
		],
		[
			"ram_server",
			0.5
		],
		[
			"cpu_desktop",
			0.5
		],
		[
			"cpu_server",
			0.07
		],
		[
			"switch_managed",
			0.5
		],
		[
			"router_industrial",
			0.5
		],
		[
			"thermal_imager",
			0.07
		],
		[
			"nvg_tube",
			0.07
		],
		[
			"laser_rangefinder",
			0.5
		],
		[
			"satellite_modem",
			0.18
		],
		[
			"oscilloscope_portable",
			0.18
		],
		[
			"laptop_business",
			0.18
		],
		[
			"laptop_workstation",
			0.07
		],
		[
			"smartphone_business",
			0.5
		],
		[
			"photo_camera_pro",
			0.07
		],
		[
			"motherboard_server",
			0.5
		],
		[
			"cctv_bullet",
			0.5
		],
		[
			"cctv_dome",
			0.5
		],
		[
			"microscope_digital",
			0.18
		],
		[
			"cpu_cooling_kit",
			0.5
		]
	],
	"security": [
		[
			"part_pm_barrel",
			1
		],
		[
			"part_pm_slide",
			0.5
		],
		[
			"part_pm_hammer",
			1
		],
		[
			"part_pm_trigger",
			1
		],
		[
			"part_pm_safety",
			1
		],
		[
			"part_glock_barrel",
			0.5
		],
		[
			"part_glock_slide",
			0.5
		],
		[
			"part_glock_recoil",
			1
		],
		[
			"part_glock_trigger",
			0.5
		],
		[
			"part_glock_extractor",
			1
		],
		[
			"part_veras_receiver",
			0.5
		],
		[
			"part_veras_stock",
			1
		],
		[
			"part_veras_muzzle",
			1
		],
		[
			"part_veras_mag_body",
			1
		],
		[
			"weapon_cleaning_kit",
			1
		],
		[
			"weapon_gauges",
			0.5
		],
		[
			"pack_918_pst",
			1
		],
		[
			"pack_918_ap",
			1
		],
		[
			"pack_919_fmj",
			1
		],
		[
			"pack_919_ap",
			1
		],
		[
			"pack_45_fmj",
			1
		],
		[
			"pack_57_ap",
			0.5
		],
		[
			"pack_921_ap",
			1
		],
		[
			"pack_545_std",
			1
		],
		[
			"pack_545_ap",
			0.5
		],
		[
			"pack_939_sp5",
			1
		],
		[
			"pack_939_sp6",
			0.5
		],
		[
			"pack_556_std",
			1
		],
		[
			"pack_556_ap",
			0.5
		],
		[
			"pack_76251_std",
			1
		],
		[
			"pack_12_buck",
			1
		],
		[
			"pack_frag",
			0.5
		],
		[
			"pack_flares",
			1
		],
		[
			"pack_chemlights",
			1
		],
		[
			"signal_launcher",
			0.18
		],
		[
			"supply_signal",
			0.5
		]
	],
	"sport": [
		[
			"part_pm_barrel",
			1
		],
		[
			"part_pm_slide",
			0.5
		],
		[
			"part_pm_hammer",
			1
		],
		[
			"part_pm_trigger",
			1
		],
		[
			"part_pm_safety",
			1
		],
		[
			"part_glock_barrel",
			0.5
		],
		[
			"part_glock_slide",
			0.5
		],
		[
			"part_glock_recoil",
			1
		],
		[
			"part_glock_trigger",
			0.5
		],
		[
			"part_glock_extractor",
			1
		],
		[
			"part_veras_receiver",
			0.5
		],
		[
			"part_veras_stock",
			1
		],
		[
			"part_veras_muzzle",
			1
		],
		[
			"part_veras_mag_body",
			1
		],
		[
			"weapon_cleaning_kit",
			1
		],
		[
			"weapon_gauges",
			0.5
		],
		[
			"pack_918_pst",
			1
		],
		[
			"pack_918_ap",
			1
		],
		[
			"pack_919_fmj",
			1
		],
		[
			"pack_919_ap",
			1
		],
		[
			"pack_45_fmj",
			1
		],
		[
			"pack_57_ap",
			0.5
		],
		[
			"pack_921_ap",
			1
		],
		[
			"pack_545_std",
			1
		],
		[
			"pack_545_ap",
			0.5
		],
		[
			"pack_939_sp5",
			1
		],
		[
			"pack_939_sp6",
			0.5
		],
		[
			"pack_556_std",
			1
		],
		[
			"pack_556_ap",
			0.5
		],
		[
			"pack_76251_std",
			1
		],
		[
			"pack_12_buck",
			1
		],
		[
			"pack_frag",
			0.5
		],
		[
			"pack_flares",
			1
		],
		[
			"pack_chemlights",
			1
		]
	],
	"workshop": [
		[
			"part_pm_barrel",
			1
		],
		[
			"part_pm_slide",
			0.5
		],
		[
			"part_pm_hammer",
			1
		],
		[
			"part_pm_trigger",
			1
		],
		[
			"part_pm_safety",
			1
		],
		[
			"part_glock_barrel",
			0.5
		],
		[
			"part_glock_slide",
			0.5
		],
		[
			"part_glock_recoil",
			1
		],
		[
			"part_glock_trigger",
			0.5
		],
		[
			"part_glock_extractor",
			1
		],
		[
			"part_veras_receiver",
			0.5
		],
		[
			"part_veras_stock",
			1
		],
		[
			"part_veras_muzzle",
			1
		],
		[
			"part_veras_mag_body",
			1
		],
		[
			"weapon_cleaning_kit",
			1
		],
		[
			"weapon_gauges",
			0.5
		],
		[
			"car_tire",
			1
		],
		[
			"car_rim",
			1
		],
		[
			"tire_pump",
			1
		],
		[
			"auto_lubricant",
			1
		],
		[
			"precision_oiler",
			1
		],
		[
			"ratchet_socket",
			1
		],
		[
			"alternator_rebuild",
			0.5
		],
		[
			"injector_set",
			0.5
		],
		[
			"car_ecu",
			0.5
		],
		[
			"timing_kit",
			0.5
		],
		[
			"brake_service_kit",
			1
		],
		[
			"bearing_set",
			1
		]
	],
	"storage": [
		[
			"part_pm_barrel",
			1
		],
		[
			"part_pm_slide",
			0.5
		],
		[
			"part_pm_hammer",
			1
		],
		[
			"part_pm_trigger",
			1
		],
		[
			"part_pm_safety",
			1
		],
		[
			"part_glock_barrel",
			0.5
		],
		[
			"part_glock_slide",
			0.5
		],
		[
			"part_glock_recoil",
			1
		],
		[
			"part_glock_trigger",
			0.5
		],
		[
			"part_glock_extractor",
			1
		],
		[
			"part_veras_receiver",
			0.5
		],
		[
			"part_veras_stock",
			1
		],
		[
			"part_veras_muzzle",
			1
		],
		[
			"part_veras_mag_body",
			1
		],
		[
			"weapon_cleaning_kit",
			1
		],
		[
			"weapon_gauges",
			0.5
		],
		[
			"microscope_optical",
			0.18
		],
		[
			"surgical_tape",
			1
		],
		[
			"suture_kit",
			1
		],
		[
			"scalpel_kit",
			0.5
		],
		[
			"hemostat_kit",
			0.5
		],
		[
			"dental_kit",
			0.5
		],
		[
			"orthopedic_kit",
			0.5
		],
		[
			"intubation_kit",
			0.5
		],
		[
			"diagnostic_kit",
			0.5
		],
		[
			"sterile_dressing_kit",
			1
		],
		[
			"antibiotics_pack",
			0.5
		],
		[
			"anesthetic_pack",
			0.5
		],
		[
			"insulin_pack",
			0.5
		],
		[
			"antiseptic_pack",
			1
		],
		[
			"hemostatic_pack",
			0.5
		],
		[
			"iv_solution_pack",
			1
		],
		[
			"car_tire",
			1
		],
		[
			"car_rim",
			1
		],
		[
			"tire_pump",
			1
		],
		[
			"auto_lubricant",
			1
		],
		[
			"precision_oiler",
			1
		],
		[
			"ratchet_socket",
			1
		],
		[
			"alternator_rebuild",
			0.5
		],
		[
			"injector_set",
			0.5
		],
		[
			"car_ecu",
			0.5
		],
		[
			"timing_kit",
			0.5
		],
		[
			"brake_service_kit",
			1
		],
		[
			"bearing_set",
			1
		],
		[
			"food_milk",
			1
		],
		[
			"food_tomatoes",
			1
		],
		[
			"food_beans",
			1
		],
		[
			"food_sardines",
			1
		],
		[
			"ration_daily",
			1
		],
		[
			"ration_patrol",
			1
		],
		[
			"ration_arctic",
			1
		],
		[
			"ration_emergency",
			1
		],
		[
			"freeze_dried_meals",
			1
		],
		[
			"coffee_pack",
			1
		],
		[
			"protein_pack",
			1
		],
		[
			"water_purification",
			1
		],
		[
			"pack_918_pst",
			1
		],
		[
			"pack_918_ap",
			1
		],
		[
			"pack_919_fmj",
			1
		],
		[
			"pack_919_ap",
			1
		],
		[
			"pack_45_fmj",
			1
		],
		[
			"pack_57_ap",
			0.5
		],
		[
			"pack_921_ap",
			1
		],
		[
			"pack_545_std",
			1
		],
		[
			"pack_545_ap",
			0.5
		],
		[
			"pack_939_sp5",
			1
		],
		[
			"pack_939_sp6",
			0.5
		],
		[
			"pack_556_std",
			1
		],
		[
			"pack_556_ap",
			0.5
		],
		[
			"pack_76251_std",
			1
		],
		[
			"pack_12_buck",
			1
		],
		[
			"pack_frag",
			0.5
		],
		[
			"pack_flares",
			1
		],
		[
			"pack_chemlights",
			1
		]
	],
	"pmc": [
		[
			"part_pm_barrel",
			1
		],
		[
			"part_pm_slide",
			0.5
		],
		[
			"part_pm_hammer",
			1
		],
		[
			"part_pm_trigger",
			1
		],
		[
			"part_pm_safety",
			1
		],
		[
			"part_glock_barrel",
			0.5
		],
		[
			"part_glock_slide",
			0.5
		],
		[
			"part_glock_recoil",
			1
		],
		[
			"part_glock_trigger",
			0.5
		],
		[
			"part_glock_extractor",
			1
		],
		[
			"part_veras_receiver",
			0.5
		],
		[
			"part_veras_stock",
			1
		],
		[
			"part_veras_muzzle",
			1
		],
		[
			"part_veras_mag_body",
			1
		],
		[
			"weapon_cleaning_kit",
			1
		],
		[
			"weapon_gauges",
			0.5
		],
		[
			"pack_918_pst",
			1
		],
		[
			"pack_918_ap",
			1
		],
		[
			"pack_919_fmj",
			1
		],
		[
			"pack_919_ap",
			1
		],
		[
			"pack_45_fmj",
			1
		],
		[
			"pack_57_ap",
			0.5
		],
		[
			"pack_921_ap",
			1
		],
		[
			"pack_545_std",
			1
		],
		[
			"pack_545_ap",
			0.5
		],
		[
			"pack_939_sp5",
			1
		],
		[
			"pack_939_sp6",
			0.5
		],
		[
			"pack_556_std",
			1
		],
		[
			"pack_556_ap",
			0.5
		],
		[
			"pack_76251_std",
			1
		],
		[
			"pack_12_buck",
			1
		],
		[
			"pack_frag",
			0.5
		],
		[
			"pack_flares",
			1
		],
		[
			"pack_chemlights",
			1
		],
		[
			"signal_launcher",
			0.18
		],
		[
			"supply_signal",
			0.5
		]
	],
	"pharmacy": [
		[
			"microscope_optical",
			0.18
		],
		[
			"surgical_tape",
			1
		],
		[
			"suture_kit",
			1
		],
		[
			"scalpel_kit",
			0.5
		],
		[
			"hemostat_kit",
			0.5
		],
		[
			"dental_kit",
			0.5
		],
		[
			"orthopedic_kit",
			0.5
		],
		[
			"intubation_kit",
			0.5
		],
		[
			"diagnostic_kit",
			0.5
		],
		[
			"sterile_dressing_kit",
			1
		],
		[
			"antibiotics_pack",
			0.5
		],
		[
			"anesthetic_pack",
			0.5
		],
		[
			"insulin_pack",
			0.5
		],
		[
			"antiseptic_pack",
			1
		],
		[
			"hemostatic_pack",
			0.5
		],
		[
			"iv_solution_pack",
			1
		]
	],
	"resident": [
		[
			"microscope_optical",
			0.18
		],
		[
			"surgical_tape",
			1
		],
		[
			"suture_kit",
			1
		],
		[
			"scalpel_kit",
			0.5
		],
		[
			"hemostat_kit",
			0.5
		],
		[
			"dental_kit",
			0.5
		],
		[
			"orthopedic_kit",
			0.5
		],
		[
			"intubation_kit",
			0.5
		],
		[
			"diagnostic_kit",
			0.5
		],
		[
			"sterile_dressing_kit",
			1
		],
		[
			"antibiotics_pack",
			0.5
		],
		[
			"anesthetic_pack",
			0.5
		],
		[
			"insulin_pack",
			0.5
		],
		[
			"antiseptic_pack",
			1
		],
		[
			"hemostatic_pack",
			0.5
		],
		[
			"iv_solution_pack",
			1
		],
		[
			"food_milk",
			1
		],
		[
			"food_tomatoes",
			1
		],
		[
			"food_beans",
			1
		],
		[
			"food_sardines",
			1
		],
		[
			"ration_daily",
			1
		],
		[
			"ration_patrol",
			1
		],
		[
			"ration_arctic",
			1
		],
		[
			"ration_emergency",
			1
		],
		[
			"freeze_dried_meals",
			1
		],
		[
			"coffee_pack",
			1
		],
		[
			"protein_pack",
			1
		],
		[
			"water_purification",
			1
		]
	],
	"tools": [
		[
			"car_tire",
			1
		],
		[
			"car_rim",
			1
		],
		[
			"tire_pump",
			1
		],
		[
			"auto_lubricant",
			1
		],
		[
			"precision_oiler",
			1
		],
		[
			"ratchet_socket",
			1
		],
		[
			"alternator_rebuild",
			0.5
		],
		[
			"injector_set",
			0.5
		],
		[
			"car_ecu",
			0.5
		],
		[
			"timing_kit",
			0.5
		],
		[
			"brake_service_kit",
			1
		],
		[
			"bearing_set",
			1
		]
	],
	"grocery": [
		[
			"food_milk",
			1
		],
		[
			"food_tomatoes",
			1
		],
		[
			"food_beans",
			1
		],
		[
			"food_sardines",
			1
		],
		[
			"ration_daily",
			1
		],
		[
			"ration_patrol",
			1
		],
		[
			"ration_arctic",
			1
		],
		[
			"ration_emergency",
			1
		],
		[
			"freeze_dried_meals",
			1
		],
		[
			"coffee_pack",
			1
		],
		[
			"protein_pack",
			1
		],
		[
			"water_purification",
			1
		]
	],
	"kiosk": [
		[
			"food_milk",
			1
		],
		[
			"food_tomatoes",
			1
		],
		[
			"food_beans",
			1
		],
		[
			"food_sardines",
			1
		],
		[
			"ration_daily",
			1
		],
		[
			"ration_patrol",
			1
		],
		[
			"ration_arctic",
			1
		],
		[
			"ration_emergency",
			1
		],
		[
			"freeze_dried_meals",
			1
		],
		[
			"coffee_pack",
			1
		],
		[
			"protein_pack",
			1
		],
		[
			"water_purification",
			1
		]
	],
	"shelf": [
		[
			"food_milk",
			1
		],
		[
			"food_tomatoes",
			1
		],
		[
			"food_beans",
			1
		],
		[
			"food_sardines",
			1
		],
		[
			"ration_daily",
			1
		],
		[
			"ration_patrol",
			1
		],
		[
			"ration_arctic",
			1
		],
		[
			"ration_emergency",
			1
		],
		[
			"freeze_dried_meals",
			1
		],
		[
			"coffee_pack",
			1
		],
		[
			"protein_pack",
			1
		],
		[
			"water_purification",
			1
		]
	],
	"marauder": [
		[
			"pack_918_pst",
			1
		],
		[
			"pack_918_ap",
			1
		],
		[
			"pack_919_fmj",
			1
		],
		[
			"pack_919_ap",
			1
		],
		[
			"pack_45_fmj",
			1
		],
		[
			"pack_57_ap",
			0.5
		],
		[
			"pack_921_ap",
			1
		],
		[
			"pack_545_std",
			1
		],
		[
			"pack_545_ap",
			0.5
		],
		[
			"pack_939_sp5",
			1
		],
		[
			"pack_939_sp6",
			0.5
		],
		[
			"pack_556_std",
			1
		],
		[
			"pack_556_ap",
			0.5
		],
		[
			"pack_76251_std",
			1
		],
		[
			"pack_12_buck",
			1
		],
		[
			"pack_frag",
			0.5
		],
		[
			"pack_flares",
			1
		],
		[
			"pack_chemlights",
			1
		]
	],
	"supply_drop": [
		[
			"signal_launcher",
			0.18
		],
		[
			"supply_signal",
			0.5
		]
	]
}
const VALUABLE_LOOT_CHANCE := {"electronics": 0.24, "office": 0.14, "server_rack": 0.32, "components": 0.18, "home": 0.1, "security": 0.22, "sport": 0.18, "workshop": 0.26, "storage": 0.14, "pmc": 0.22, "pharmacy": 0.28, "resident": 0.15, "tools": 0.2, "grocery": 0.22, "kiosk": 0.12, "shelf": 0.14, "marauder": 0.06, "supply_drop": 0.6}
const SUPPLY_SIGNAL := {"delay": 45.0, "altitude": 170.0, "speed": 70.0, "flight": 18.0, "drop_height": 40.0, "fall_sec": 8.0, "roof_check": 180.0, "ground_check": 4.0, "clear_radius": 3.5, "site_half": 1.0, "site_height": 0.5, "terrain_tolerance": 0.15, "normal_min": 0.85, "flare_height": 65.0, "flare_sec": 18.0, "loot_count": [4, 6], "minimum_value": 28000, "noise_m": 180.0}
## Что лежит в грузе, вызванном сигналом: боевое, а не ценности на продажу. weapons — сколько готовых
## стволов (сборки тира weapon_tier и выше, состояние dur %), к каждому mags снаряжённых магазинов и
## патронов ещё на ammo_mags магазинов (лучший по пробитию патрон калибра), mods деталей обвеса тира
## mod_tier и выше, которые на него встают; броня и шлем тира armor_tier и выше; extras — [id, от, до].
const SUPPLY_LOOT := {"weapons": [1, 2], "weapon_tier": 3, "dur": [85, 100], "mags": 3, "ammo_mags": 3, "mods": 2, "mod_tier": 2,
	"armor_tier": 3, "extras": [["medkit", 1, 2], ["painkillers", 1, 2], ["grenade", 2, 3], ["rig_assault", 0, 1]]}
const SUPPLY_PLANE_SOUND := {"db": 12.0, "unit": 60.0, "max": 600.0}

## Узкие жилые двери и лестницы зоны 1: отдельная точность кэша, остальные карты прежние.
const ZONE01_INTERIOR_NAV := {
	"nav_tile": 240.0, "nav_cell": 0.125, "nav_height": 0.0625, "nav_border": 2.0,
	"nav_radius": 0.375, "nav_detail_error": 1.0, "nav_merge_scale": 0.0078125,
}

## Тестовое прохождение заданий (владелец, 2026-10-17): у целей с test_hint — всплывающая
## инструкция «что делать» на экране и в журнале (J). К релизу — false (тексты test_hint можно
## оставить в данных: при false они не показываются нигде).
const QUEST_TEST_HINTS := true
## Сколько секунд инструкция видна после смены цели (дальше — в журнале).
const QUEST_TEST_HINT_SEC := 25.0
