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
## У каждого куска свои пропорции: оси растянуты случайно на ± эту долю.
const IMPACT_SHAPE_VAR: float = 0.2
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
## Разогрев шейдеров эффектов под экраном загрузки (ImpactFx.warm_up): сколько кадров показывать, на каком
## расстоянии перед камерой (м) и с каким шагом сетки (м).
const IMPACT_WARM := {"frames": 8, "distance_m": 0.6, "step_m": 0.06}
## Вспышка удара: life (с), color, energy — яркость; свет на миг — light_range (м), light_energy,
## одновременно не больше light_max.
const IMPACT_FLASH := {"life": 0.06, "color": Color(1.0, 0.78, 0.45), "energy": 5.0, "light_range": 2.6, "light_energy": 3.0, "light_max": 4}
## Облако из листа кадров (tools/build_impact_smoke.py): крупнее и реже процедурного (size_k, count_k —
## к size и count профиля), непрозрачность × opacity_k, частица подрастает grow (начало, конец), гаснет
## с fade_start, кадр начала — случайно до offset доли листа; облако вынесено от поверхности по нормали на
## lift_k своего размера, стык со стеной и полом мягкий на soft_m (м).
const IMPACT_FLIPBOOK := {"size_k": 1.7, "count_k": 0.6, "opacity_k": 1.5, "grow": Vector2(0.75, 1.15), "fade_start": 0.75,
	"offset": 0.06, "lift_k": 0.3, "soft_m": 0.3}
## Облако пыли: разлёт (м/с), сопротивление воздуха (доля скорости за с), конус (°).
const IMPACT_DUST := {"speed": Vector2(0.25, 0.85), "drag": Vector2(1.3, 2.4), "spread": 50.0}
## Следы попаданий (ImpactFx): asset — набор декалей в assets/textures/impacts, size — сторона декали, м.
## У hole_* дырка вылеплена в реальном размере на плитке (бетон 16 см, плитка 18, асфальт и дерево 14,
## картон 12, металл и пластик 10 — tools/build_impact_holes.py); в игре — крупнее, в духе Helldivers 2:
## след должен читаться издали. tint — оттенок поверх запечённого цвета.
const IMPACT_DECALS: Dictionary = {
	"concrete": {"asset": "hole_concrete", "size": Vector2(0.21, 0.27), "tint": Color(0.96, 0.94, 0.91, 1.0)},
	"tile": {"asset": "hole_tile", "size": Vector2(0.24, 0.3), "tint": Color(1.0, 1.0, 1.0, 1.0)},
	"asphalt": {"asset": "hole_asphalt", "size": Vector2(0.18, 0.24), "tint": Color(1.0, 1.0, 1.0, 1.0)},
	"metal": {"asset": "hole_metal", "size": Vector2(0.14, 0.18), "tint": Color(1.0, 1.0, 1.0, 1.0)},
	"wood": {"asset": "hole_wood", "size": Vector2(0.18, 0.24), "tint": Color(1.0, 0.97, 0.94, 1.0)},
	"cardboard": {"asset": "hole_cardboard", "size": Vector2(0.15, 0.2), "tint": Color(1.0, 1.0, 1.0, 1.0)},
	"plastic": {"asset": "hole_plastic", "size": Vector2(0.13, 0.17), "tint": Color(1.0, 1.0, 1.0, 1.0)},
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
## dust — медленное облако: count, size — диаметр (м), opacity, rise — подъём (м/с², вниз — минус),
##   look — лист кадров: puff (клуб пыли, один из двух) или wisp (дымок);
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
		"dust": {"count": 2, "size": Vector2(0.08, 0.22), "life": Vector2(0.6, 1.2), "opacity": 0.16, "rise": 0.5, "color": Color(0.5, 0.5, 0.5), "look": "wisp"},
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
	# «Трава издали» (приём Road to Vostok, docs/research/road_to_vostok.md): за кольцом травинок газон рельефа там,
	# где растёт трава, берёт их вид — плоская фотография газона была в 1,6–1,7 раза темнее травинок, и край кольца
	# читался тёмной полосой. tint — множитель альбедо газона (линейный), flat — доля сглаживания нормали (травинки
	# издали не показывают бугры земли), clumps — яркость куртин от и до (пятна ~4 м). Включается там же, где травинки
	# уходят в землю: от far − fade_m до far кольца по качеству графики.
	"far_look": {"tint": Vector3(2.75, 2.7, 2.85), "flat": 0.6, "clumps": Vector2(0.85, 1.12)},
	"wind": Vector4(0.89, 0.45, 1.0, 1.0), "wind_rain_k": 1.7,
	"trample_extent": 48.0, "trample_res": 128, "trample_hz": 30.0, "trample_recover_sec": 9.0,
	"trample_radius": {"stand": 0.36, "crouch": 0.44, "prone": 0.62, "body": 0.3, "blast_k": 0.8},
	"body_bones": ["mixamorig_Hips", "mixamorig_Spine2", "mixamorig_Head", "mixamorig_LeftLeg", "mixamorig_RightLeg", "mixamorig_LeftFoot", "mixamorig_RightFoot"],
}
## Тени деревьев (приём Road to Vostok, docs/research/road_to_vostok.md): видимые модели деревьев тень не
## отбрасывают — их тень рисуют отдельные невидимые копии «только тень»: вблизи — полная модель (пятна от листвы
## под кроной), дальше — скрещённые карточки дальнего вида (две плоскости вместо тысяч листьев в каждом каскаде).
## Порог — по клетке россыпи (дальность видимости в Godot считается от центра клетки): полная тень у клеток,
## чей центр ближе detail_m + полклетки; margin — плавная смена, м. Растения «Проспекта» (MallFiller) — только
## деревья выше min_height, м, у которых последний LOD — карточки (не больше cards_max_tris треугольников);
## кусты и изгородь отбрасывают тень, как раньше. on = false — всё как было (тень от видимых моделей).
const TREE_SHADOWS := {"on": true, "detail_m": 35.0, "margin": 6.0, "min_height": 4.0, "cards_max_tris": 8}
## Тень солнца и Луны по качеству графики (приём Road to Vostok, docs/research/road_to_vostok.md; у них «низко» —
## 100 м и 2 каскада). «Высоко» — как в сцене (одобренный вид: зона 1 и ТЦ — 260 м, 4 каскада); ниже — дальность
## не больше max_m, м, и каскадов не больше splits (2 или 4; только уменьшаем). Размер карты теней по качеству —
## Settings.apply_graphics (2048 на «низко», 4096 выше).
const SHADOW_QUALITY := {"low": {"max_m": 100.0, "splits": 2}, "medium": {"max_m": 160.0, "splits": 4}, "high": {}}

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
## выбора сглажена за speed_smooth_sec, с (иначе на мониторе 144+ клип скачет каждый кадр).
## Дальние персонажи (мародёры, чужие отряды, напарники): дальше shadows_m от камеры не отбрасывают
## тень, дальше hide_m не рисуются (ИИ и звук работают как прежде); дальше ik_m руки не подгоняются к
## оружию и стенам, дальше anim_m[0] клип считается через кадр, дальше anim_m[1] — раз в четыре кадра;
## every — как часто проверять, с; hysteresis — запас в метрах на возврат, чтобы тень не мигала.
## anim_far_m / anim_far_hz — дальний ярус (приём Road to Vostok, владелец 2026-11-05): дальше anim_far_m клип
## двигается anim_far_hz раз в секунду, сколько бы кадров ни было (вдали рывков не видно, процессор свободнее).
const CHARACTER_LOD := {"shadows_m": 55.0, "hide_m": 320.0, "ik_m": 35.0, "anim_m": [45.0, 100.0], "every": 0.4, "hysteresis": 6.0,
	"anim_far_m": 160.0, "anim_far_hz": 5.0,
	"mesh_m": [25.0, 60.0], "mesh_margin_m": 2.0}
## Машина Ильи (src/world/ilya_car.gd): ближняя модель (~150 тыс. треугольников) до lod1_m от камеры, дальше
## LOD1 (~50 тыс.), с lod2_m — LOD2 (~12 тыс.); margin_m — запас на возврат, чтобы сетки не мигали на границе.
const VEHICLE_LOD := {"lod1_m": 15.0, "lod2_m": 40.0, "margin_m": 1.5}
## Дерево анимации (CharacterAnimator): от move_min до move_full, м/с, поза на месте плавно сменяется
## шагом; run_from — с какой скорости падает раненым «с разбега» (и, со sprint_from, пороги бега и
## спринта у «как было» на стенде сравнения); клипы шага крутятся быстрее или
## медленнее, чтобы ступни не скользили, но не медленнее rate_min и не быстрее rate_max (лёжа —
## prone_rate_max); направление шага сглажено за dir_smooth_sec, с; смена стойки и оружия —
## set_blend_sec, поз целиком (лёжа, ранен, смерть) — pose_blend_sec, прицельной позы на месте —
## aim_blend_sec; действие верхом тела входит за act_in и уходит за act_out, с.
const CHARACTER_ANIM := {"move_min": 0.12, "move_full": 0.6, "run_from": 3.1, "sprint_from": 4.8, "prone_hold_sec": 1.0, "prone_aim_hold_sec": 0.3, "hurt_below": 0.35, "support_blend_sec": 0.15, "speed_smooth_sec": 0.1,
	"rate_min": 0.35, "rate_max": 1.8, "prone_rate_max": 2.5, "dir_smooth_sec": 0.12, "move_smooth_sec": 0.08, "set_blend_sec": 0.3, "pose_blend_sec": 0.22, "aim_blend_sec": 0.2, "act_in": 0.12, "act_out": 0.25}
## Живость поверх клипов (BodyMotion), углы в радианах:
## - корпус за взглядом вверх-вниз — не больше pitch_up / pitch_down; лёжа доля pitch_prone, на спринте
##   pitch_sprint, без оружия pitch_unarmed (остальное добирает голова, не больше head_max); сглажено за pitch_sec;
## - тело в игре поворачивается мгновенно (мародёр), корпус модели догоняет за torso_sec; ноги на ходу —
##   за legs_move_sec, на месте ждут, пока корпус не отвернётся больше legs_dead, и доворачиваются за
##   legs_idle_sec до legs_settle; дальше legs_max ноги тянутся за корпусом;
## - выглядывание: наклон вбок lean_roll при полном наклоне (за lean_sec);
## - разгон и поворот: наклон accel_lean на 1 м/с², не больше accel_max, сглажено за accel_sec;
## - дыхание: в покое breath_rest с частотой breath_rest_hz, после бега до breath_hard / breath_hard_hz;
##   запыхался за exert_up_sec бега быстрее exert_speed, отдышался за exert_down_sec; на ходу — доля breath_moving;
## - отдача: толчок recoil_kick (пистолет recoil_pistol, лёжа — доля recoil_prone), пружина recoil_stiff / recoil_damp;
## - попадание: толчок flinch_kick, пружина flinch_stiff / flinch_damp;
## - по костям: spine — доли Spine / Spine1 / Spine2 [взгляд, наклон, дыхание, отдача, вздрагивание,
##   выглядывание, доворот]; голова гасит отдачу и дыхание (head.steady) и держится ровнее при
##   выглядывании (head.roll_keep); плечи на вдохе — shoulder_breath.
const BODY_MOTION := {"pitch_up": 1.0, "pitch_down": 0.9, "pitch_prone": 0.35, "pitch_sprint": 0.3, "pitch_unarmed": 0.45, "head_max": 0.6, "pitch_sec": 0.08,
	"torso_sec": 0.07, "legs_move_sec": 0.12, "legs_idle_sec": 0.2, "legs_dead": 0.75, "legs_settle": 0.06, "legs_max": 1.2,
	"lean_roll": 0.42, "lean_sec": 0.1, "accel_lean": 0.022, "accel_max": 0.16, "accel_sec": 0.18,
	"breath_rest": 0.01, "breath_rest_hz": 0.24, "breath_hard": 0.035, "breath_hard_hz": 0.62, "exert_speed": 3.0, "exert_up_sec": 5.0, "exert_down_sec": 14.0, "breath_moving": 0.4,
	"recoil_kick": 1.6, "recoil_pistol": 1.1, "recoil_prone": 0.4, "recoil_stiff": 260.0, "recoil_damp": 22.0,
	"flinch_kick": 3.2, "flinch_stiff": 120.0, "flinch_damp": 14.0,
	"spine": {"0": [0.2, 0.5, 0.0, 0.0, 0.3, 0.3, 0.3], "1": [0.35, 0.3, 0.5, 0.35, 0.35, 0.35, 0.35], "2": [0.45, 0.2, 0.5, 0.65, 0.35, 0.35, 0.35]},
	"head": {"steady": 0.8, "roll_keep": 0.5}, "shoulder_breath": 0.6}

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
## Выходы по стороне захода (карта включает ключом "exits_by_side" в данных сектора; «Проспект», владелец
## 2026-10-29, docs/design/prospekt_eft_mechanics.md): у группы закрыты выходы ближе near_spawn_m к её заходу.
## Доля рейдов, в которых выход открыт, — у самой точки (ExtractionPoint.chance).
const EXIT_RULES := {"near_spawn_m": 150.0}
## Сколько висит список выходов рейда на экране при старте, с.
const EXIT_NOTE_SEC := 9.0
## Схроны (LootContainer.stash): в рейде открыта случайная часть — от active[0] до active[1] на карту,
## остальные пусты и не видны. Награда за знание карты, а не за удачу.
const STASHES := {"active": [3, 5]}
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
## Третье значение у ствола — обвес по точкам крепления: тактический фонарь на планке автомата (пролог,
## docs/design/prologue.md §9.9 — набор в закладке и в тайнике без пролога одинаковый).
const START_STASH := [["wpn_hg_02", 1], ["wpn_ar_01", 1, {"side_right": "mount_dozor_p", "side_right/light": "tac_flashlight_01"}], ["ammo_919_fmj", 100], ["ammo_545_std", 120],
	["mag_545_30", 1], ["mag_919_17", 1], ["bandage", 4], ["painkillers", 2], ["armor_mid", 1], ["helmet_simple", 1], ["grenade", 2]]
## Пролог «Первый выход» (docs/design/prologue.md): квест и его рейд; что игрок несёт с собой через кордон
## (carry — из стартового набора, остальное ждёт в закладке: сумка в подсобке кофейни); подпись сумки (бирка —
## имя профиля); пакет Михалычу — один на группу; условия рейда (§2: закат, ясно); сумка опоздавшего, если
## группа уже прошла кофейню, — у рампы склада (§6).
const PROLOGUE := {
	"quest": "prologue",
	"scene": "res://scenes/levels/prospekt.tscn",
	"carry": [["bandage", 2], ["painkillers", 1]],
	"bag_name": "Сумка",
	"packet": "tutorial_packet",
	"conditions": {"time": "dusk", "weather": "clear", "power": "on"},
}
## Ворота кордона (GateWarden, §8 пролога — и в обычных рейдах): ЧВК не трогают игроков, пока те не подошли
## к воротам ближе zone_m; подошёл — окрик, через shout_sec — предупредительный в воздух, ещё через warn_sec — огонь.
## Ушёл от ворот до огня — через reset_sec всё сначала. Попал в бойца — огонь сразу.
const GATE_WARDEN := {"zone_m": 7.0, "shout_sec": 3.0, "warn_sec": 4.0, "reset_sec": 6.0}
## Выручка Михалыча: остался без огнестрела и без денег на самый дешёвый ствол — бесплатный
## набор, чтобы было с чем идти в рейд (сколько угодно раз, пока снова не встанешь на ноги).
const RESCUE_KIT := [["wpn_hg_01", 1], ["ammo_918_pst", 48], ["bandage", 2]]
## Готовые комплекты у Михалыча (правая колонка окна): полный набор одной кнопкой — стволы с обвесом,
## броня с плитами и подсумками, шлем, гарнитура, рюкзак, в рюкзаке магазины, патроны, медицина, гранаты
## (снаряжённые магазины на входе в рейд сами переезжают в пустые подсумки — Inventory.prepare_mags). Формат —
## как у своих шаблонов (LoadoutTemplates): что есть в тайнике — берётся оттуда, остальное докупается.
## По одному на ступень снабжения: каталог 1, 2, 3 и 5.
const TRADER_KITS := [
	{"name": "Дворовый", "about": "Ружьё и ПМ, самодельный жилет. С чем выходят в первый рейд.",
		"slots": {
			"primary": {"id": "wpn_sg_03", "mods": {"optic_primary": "optic_rd_01"}},
			"sidearm": {"id": "wpn_hg_01"},
			"armor": {"id": "armor_poor", "pouches": ["pouch_pistol", "pouch_pistol"]},
			"helmet": {"id": "helmet_simple"},
			"ears": {"id": "headset_passive"},
			"backpack": {"id": "bp_daypack"}},
		"backpack": [["ammo_12_buck", 30], ["ammo_12_slug", 10], ["mag_918_8", 2], ["ammo_918_pst", 32], ["bandage", 3], ["medkit", 1], ["water", 1]]},
	{"name": "Патрульный", "about": "ВЕРАС-54 с коллиматором и Glock, плитоносец со стальными плитами.",
		"slots": {
			"primary": {"id": "wpn_ar_01", "mods": {"optic_primary": "optic_holo_01", "muzzle": "muzzle_comp_545_01", "underbarrel": "grip_vertical_01", "side_right": "mount_dozor_p", "side_right/light": "tac_flashlight_01"}},
			"sidearm": {"id": "wpn_hg_02"},
			"armor": {"id": "armor_mid", "plates": {"front": "plate_steel", "back": "plate_steel"}, "pouches": ["pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle"]},
			"helmet": {"id": "helmet_mid"},
			"ears": {"id": "headset_active"},
			"backpack": {"id": "bp_tourist"}},
		"backpack": [["mag_545_30", 4], ["ammo_545_std", 150], ["mag_919_17", 2], ["ammo_919_fmj", 51], ["bandage", 4], ["medkit", 2], ["painkillers", 1], ["grenade", 2]]},
	{"name": "Штурмовик", "about": "ГРАНЬ-15 с оптикой 4× и глушителем, керамика, ПНВ. Для ночи и тесных коридоров.",
		"slots": {
			"primary": {"id": "wpn_ar_09", "mods": {"optic_primary": "optic_4x_01", "muzzle": "muzzle_supp_gran_01", "underbarrel": "grip_offset_01", "side_right": "tac_combo_01"}},
			"sidearm": {"id": "wpn_hg_02"},
			"armor": {"id": "armor_top", "plates": {"front": "plate_ceramic", "back": "plate_ceramic"}, "pouches": ["pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle"]},
			"helmet": {"id": "helmet_mid"},
			"ears": {"id": "headset_tactical"},
			"eyes": {"id": "nvg"},
			"backpack": {"id": "bp_raid"}},
		"backpack": [["tac_flashlight_01", 1], ["mag_556_30_gran", 5], ["ammo_556_std", 180], ["mag_919_17", 2], ["ammo_919_ap", 51], ["bandage", 4], ["medkit", 2], ["painkillers", 2], ["grenade", 3], ["flare", 1]]},
	{"name": "Снайпер", "about": "MR762 с оптикой 8× и глушителем, Vector на ближний бой, лучшая броня.",
		"slots": {
			"primary": {"id": "wpn_dmr_01", "mods": {"optic_primary": "optic_8x_01", "muzzle": "muzzle_supp_762_01"}},
			"secondary": {"id": "wpn_smg_03", "mods": {"optic_primary": "optic_holo_01", "underbarrel": "grip_offset_01"}},
			"armor": {"id": "armor_top", "plates": {"front": "plate_military", "back": "plate_military"}, "pouches": ["pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle", "pouch_rifle"]},
			"helmet": {"id": "helmet_top"},
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
	"ammo_338_ap": 5500,
	"ammo_338_match": 1300,
	"ammo_45_ap": 890,
	"ammo_45_fmj": 120,
	"ammo_45_jhp": 170,
	"ammo_545_ap": 960,
	"ammo_545_old": 80,
	"ammo_545_std": 120,
	"ammo_556_ap": 1300,
	"ammo_556_civ": 120,
	"ammo_556_std": 150,
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
	"bp_daypack": 12000,
	"bp_raid": 180000,
	"bp_tourist": 35000,
	"brake_service_kit": 11000,
	"camera": 12000,
	"canned": 560,
	"car_ecu": 25000,
	"car_rim": 7200,
	"car_tire": 9800,
	"armor_poor": 14000,
	"armor_mid": 46000,
	"armor_top": 160000,
	"belt_pouches": 5000,
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
	"grip_offset_01": 40000,
	"grip_vertical_01": 20000,
	"hammer": 1400,
	"headphones": 4600,
	"headset_active": 30000,
	"headset_passive": 3900,
	"headset_perimeter": 200000,
	"headset_tactical": 92000,
	"helmet_simple": 12000,
	"helmet_mid": 60000,
	"helmet_top": 190000,
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
	"mag_338_awm5": 8000,
	"mag_45_vector13": 1800,
	"mag_45_vector30": 5000,
	"mag_545_30": 2000,
	"mag_545_45": 3500,
	"mag_545_60": 5500,
	"mag_556_30_gran": 3000,
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
	"mag_939_30": 7000,
	"mag_loader": 35000,
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
	"mount_pm_k1": 15000,
	"mount_rail_ext_01": 10000,
	"mount_riser_01": 8500,
	"multimeter": 10000,
	"muzzle_brake_338_01": 218000,
	"muzzle_brake_68_01": 146000,
	"muzzle_brake_762_01": 35000,
	"muzzle_comp_545_01": 30000,
	"muzzle_comp_9_01": 29000,
	"muzzle_fh_545_01": 10000,
	"muzzle_supp_12_01": 157000,
	"muzzle_supp_338_01": 819000,
	"muzzle_supp_45_01": 157000,
	"muzzle_supp_545_01": 172000,
	"muzzle_supp_68_01": 592000,
	"muzzle_supp_762_01": 273000,
	"muzzle_supp_9_01": 129000,
	"muzzle_supp_gran_01": 195000,
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
	"optic_pso_01": 100000,
	"optic_pu_01": 100000,
	"optic_rd_01": 30000,
	"optic_rd_dt_01": 28000,
	"optic_zorin_k1": 55000,
	"orthopedic_kit": 27000,
	"oscilloscope_portable": 44000,
	"pack_12_buck": 2000,
	"pack_45_fmj": 3600,
	"pack_545_ap": 38400,
	"pack_545_std": 7200,
	"pack_556_ap": 52000,
	"pack_556_std": 9000,
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
	"tac_flashlight_strobe_01": 55000,
	"mount_dozor_p": 6000,
	"tac_laser_01": 35000,
	"thermal_imager": 101000,
	"thermos": 2200,
	"timing_kit": 16000,
	"tire_pump": 5500,
	"toolset": 7800,
	"pouch_rifle": 4000,
	"pouch_pistol": 2500,
	"pouch_big": 7500,
	"video_camera": 15000,
	"wall_clock": 2300,
	"watch": 16000,
	"water": 340,
	"water_purification": 6200,
	"weapon_cleaning_kit": 11000,
	"weapon_gauges": 19000,
	"msl_zr36": 450000,
	"wires": 1000,
	"work_gloves": 650,
	"wpn_ar_01": 180000,
	"wpn_ar_09": 315000,
	"wpn_ar_05": 1100000,
	"wpn_dmr_01": 850000,
	"wpn_hg_01": 10000,
	"wpn_hg_02": 60000,
	"wpn_lmg_01": 1150000,
	"wpn_mp_01": 1900000,
	"wpn_sg_02": 145000,
	"wpn_sg_03": 35000,
	"wpn_smg_03": 450000,
	"wpn_smg_04": 95000,
	"wpn_smg_05": 220000,
	"wpn_sp_02": 700000,
	"wpn_sr_03": 220000,
	"wpn_sr_01": 1350000,
}
## Явная цена продажи единицы: переоценены магазины и базовая медицина.
## Остальные находки — прежняя оценка × TRADER_SELL_MULT, с износом и содержимым.
const TRADER_SELL_MULT := 0.55
const TRADER_SELL_PRICES := {
	"bandage": 270,
	"mag_338_awm5": 3200,
	"mag_45_vector13": 720,
	"mag_45_vector30": 2000,
	"mag_545_30": 800,
	"mag_545_45": 1400,
	"mag_545_60": 2200,
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
	"mag_939_30": 2800,
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
	"mall": {"price": 0, "fee": 0}, "zone01": {"price": 0, "fee": 0},
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
## Основное прицельное крепление доступно сразу: найденная оптика не требует улучшения верстака.
const WORKBENCH_SLOT_LEVEL := {"muzzle": 1, "underbarrel": 1, "stock": 1, "optic_primary": 1, "top_front": 2, "side_left": 2, "side_right": 2}
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
const RAID_SCENE := "res://scenes/levels/mall_map.tscn"
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
## Скорость распространения записанного звука: задержка до слушателя на дальней дистанции.
const AUDIO_FAR := {"sound_mps": 343.0, "delay_from_m": 25.0}
## Очередь: выстрелы одного стрелка (ближе radius_m друг к другу, не реже window_sec) звучат хвостами
## внахлёст; одновременно — не больше voices выстрелов, самый старый хвост гаснет за fade_sec, с.
const AUDIO_BURST := {"radius_m": 1.5, "window_sec": 0.6, "voices": 6, "fade_sec": 0.08}
## Попадание по себе (HurtFx и толчок взгляда в CameraRig): виньетка — не меньше min, + per_dmg за
## единицу урона, до max; гаснет за fade_sec, с. Взгляд дёргается на punch_deg (+ per_dmg_deg за
## урон, до punch_max_deg), возвращается за punch_sec, с.
const HURT_FX := {"min": 0.35, "per_dmg": 0.02, "max": 1.0, "fade_sec": 0.7,
	"punch_deg": 1.6, "per_dmg_deg": 0.06, "punch_max_deg": 4.5, "punch_sec": 0.22}
## Направление входящего попадания: дуга вокруг центра, сверху — спереди, снизу — сзади.
## Размеры — доли короткой стороны экрана; очередь с одной стороны обновляет ту же дугу,
## разные стороны остаются до hold_sec + fade_sec, с. Направление запоминается в момент удара.
const HURT_DIRECTION := {"hold_sec": 0.25, "fade_sec": 1.1, "max_hits": 6, "merge_deg": 25.0,
	"radius": 0.15, "arc_deg": 50.0, "width": 0.008, "outline": 0.004, "highlight": 0.002,
	"min_alpha": 0.65, "per_dmg_alpha": 0.015, "segments": 32,
	"color": Color(0.95, 0.12, 0.07), "highlight_color": Color(1.0, 0.65, 0.5), "outline_color": Color(0.08, 0.01, 0.005)}
## Враг действительно заметил игрока: обновление от его зрения не чаще refresh_sec, с;
## после потери контакта указатель держится hold_sec и гаснет за fade_sec. Геометрия — доли
## короткой стороны кадра; жёлтые стрелки дальше от центра, чем красные дуги попаданий.
const DETECTION_INDICATOR := {"refresh_sec": 0.25, "hold_sec": 0.45, "fade_sec": 0.75, "max_sources": 6,
	"radius": 0.21, "arrow_depth": 0.013, "arrow_half_width": 0.012, "merge_deg": 22.0,
	"line_width": 0.003, "outline_width": 0.006, "status_offset": 0.29,
	"font_size": 0.021, "font_min": 16, "font_max": 28, "text_outline": 6,
	"eye_width": 0.016, "eye_height": 0.007, "pupil": 0.003, "eye_gap": 0.012, "eye_segments": 20,
	"color": Color(1.0, 0.77, 0.2), "outline_color": Color(0.045, 0.03, 0.005)}
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
## Наглазник оптики (сетка с meta near_hide) прячется, когда ближе к глазу, чем ближняя плоскость камеры плюс
## этот запас, м: иначе камера режет резину и та «проходит в голову»; в прицеливании глаз — в наглазнике.
const SCOPE_EYECUP_MARGIN := 0.012
const FPS_HIP_POSE := Vector3(0.09, -0.12, -0.35)
## Своё поле зрения у рук и оружия перед глазами (вертикальное, град): не зависит от настройки
## поля зрения мира — при 120° руки не съёживаются, при 50° не раздуваются (CameraRig, ViewmodelSpace).
const FPS_VIEWMODEL_FOV := 54.0
## Кисти рук от первого лица (общие руки и клипы ВЕРАСа): масштаб вокруг точки хвата на ладони вместе с
## предплечьем, запястье подаётся к ней, локоть пересчитывается (HandGripPose.scale_hand). Выбранные владельцем
## 80% действуют по умолчанию в игре и стендах, включая гранату; k 1.0 — исходная модель для сравнения.
## После замены геометрии на исправленные кисти вернуть k 1.0. FPS_HAND_SCALE — явная проба другого размера.
## forward — доля пути запястье → костяшка среднего,
## palm — от оси кисти до поверхности ладони, м.
const FPS_HAND_SCALE := {"k": 0.8, "forward": 0.89, "palm": 0.035}
## Руки и оружие у лица — свой слабый свет (DirectionalLight3D при камере, только слой 2: мир им не освещён,
## это не фонарь). Днём рядом с солнцем и небом его не видно, в темноте (глаз привык) силуэт ствола и
## перчаток читается (владелец 2026-10-19: ночью в доме рук и оружия не видно). Сила — energy в темноте
## (ночь, помещение без света), днём — × day_k (было 0.35: против солнца ствол в черноте, владелец 2026-10-19);
## внутри здания — слабее во столько, во сколько глаз там
## привыкает сильнее (CameraLook). pitch/yaw — откуда, ° от взгляда; energy 0 — выключен.
const VIEWMODEL_FILL := {"energy": 0.15, "day_k": 1.0, "color": Color(0.82, 0.87, 1.0), "specular": 0.6,
	"pitch": -40.0, "yaw": 25.0}
## Свет на свои руки и оружие у лица (слой 2) — отдельно от мира, приём Road to Vostok
## (docs/research/road_to_vostok.md). Своя вспышка выстрела в мир руки не освещает (стояла у самого дула
## модели в руках и пересвечивала ствол в упор) — их освещает flash: сила × flash патрона, дальность, м, цвет;
## точка — от дула к глазу на долю toward_eye и выше на up, м (у самого дула свет ложился на грани, смотрящие
## вперёд, и оружие оставалось чёрным силуэтом).
## Фонарь светит вперёд, руки за ним тёмные — bounce: отражённый от того, что перед стволом, свет, пока
## фонарь включён. Луч по взгляду до far_m; стена ближе near_m — полная energy, дальше спадает как
## (near_m / d)². Точка света — вперёд на forward_k расстояния до стены (не дальше max_m) и сдвиг offset
## в осях камеры (x вправо, y вверх); дальность света range, м; сглаживание sec, с.
const VIEWMODEL_LIGHTS := {
	"flash": {"energy": 1.5, "range": 1.6, "toward_eye": 0.4, "up": 0.15, "color": Color(1.0, 0.8, 0.5)},
	"bounce": {"energy": 0.5, "near_m": 1.5, "far_m": 12.0, "forward_k": 0.6, "max_m": 1.2,
		"offset": Vector3(-0.2, 0.15, 0.0), "range": 2.0, "sec": 0.12, "color": Color(0.96, 0.98, 1.0)},
}
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
## Покачивание оружия у бедра относительно глаз, м. В покое — медленное (idle_rate — темп, horizontal и
## idle_vertical — размах); на ходу — в темп шагов, в той же фазе, что камера (CameraMotion): вверх-вниз
## размахом *_vertical (от низа до верха) и вбок *_side за пару шагов; lag — на какую долю шага руки
## запаздывают за головой. Размах входит и затухает вместе с реальной скоростью.
const WEAPON_BOB := {
	"idle_rate": 1.5, "horizontal": 0.006, "idle_vertical": 0.002,
	"walk_vertical": 0.01, "walk_side": 0.004, "sprint_vertical": 0.013, "sprint_side": 0.007, "lag": 0.12,
}
## Руки в прицеле на ходу: оружие у глаза не каменное, а ходит ходуном относительно головы в темп шагов
## (владелец 2026-10-22). Размах, м: вверх-вниз и вбок (за пару шагов) на ходьбе и беге; roll_deg — лёгкий
## завал ствола; lag — запаздывание рук за головой, доля шага. Стоя на месте не работает (там дыхание и сway).
const WEAPON_BOB_ADS := {
	"walk_vertical": 0.012, "walk_side": 0.008, "sprint_vertical": 0.018, "sprint_side": 0.013,
	"roll_deg": 1.2, "lag": 0.15,
}
## Движение камеры от первого лица (CameraMotion) — вес тела, как в Tarkov: шаг тяжёлый и неторопливый,
## бег — размашистей и чаще. Своей частоты у покачивания нет: его темп — темп шагов (Footsteps,
## STEP_STRIDE / скорость), поэтому камера проседает ровно тогда, когда слышен шаг.
## CAMERA_MOTION_INTENSITY — общий множитель всех эффектов камеры; поверх него — ползунок игрока
## «Покачивание камеры» (Settings.camera_motion). Остановка персонажа резкая (PLAYER_DECEL) — мягкость
## остановки только у камеры (inertia_*).
const CAMERA_MOTION_INTENSITY := 1.0
const CAMERA_MOTION := {
	# покачивание шагом и бегом: вверх-вниз, м (ниже всего — сразу после удара стопы, через low долю
	# шага); вбок к опорной ноге за пару шагов, м; крен, кивок и поворот головы, град
	"walk": {"up_m": 0.007, "side_m": 0.005, "roll_deg": 0.22, "pitch_deg": 0.12, "yaw_deg": 0.08},
	# бег — вдвое спокойнее первой пробы (владелец 2026-10-19: «слишком сильная тряска»), повороты — сильнее всего
	"sprint": {"up_m": 0.013, "side_m": 0.007, "roll_deg": 0.3, "pitch_deg": 0.2, "yaw_deg": 0.08},
	"low": 0.1,
	# удар стопы — короткое проседание и кивок на каждый шаг (затухающая пружина): глубина, м и град;
	# частота пружины, Гц, и её демпфирование (1 — без отскока)
	"impact_walk_m": 0.0025, "impact_sprint_m": 0.0035, "impact_walk_deg": 0.12, "impact_sprint_deg": 0.18,
	"impact_hz": 3.0, "impact_damp": 0.7,
	# инерция головы: насколько голова отстаёт на разгоне и уходит вперёд на остановке при резкой смене
	# скорости на 1 м/с, м; кивок и крен от этого сдвига, град на сантиметр; предел сдвига, м;
	# пружина возврата (Гц, демпфирование: меньше 1 — мягко «досаживается» с лёгким перелётом)
	"inertia_m": 0.003, "inertia_pitch_deg_cm": 0.75, "inertia_roll_deg_cm": 0.55, "inertia_max_m": 0.03,
	"inertia_hz": 1.6, "inertia_damp": 0.55,
	# шаг вбок — едва заметный крен в сторону движения, град на 1 м/с; сглаживание, 1/с
	"strafe_roll_deg": 0.2, "strafe_rate": 6.0,
	# приземление: проседание на 1 м/с скорости падения, м; предел, м; кивок, град на сантиметр проседания
	"land_m": 0.006, "land_max_m": 0.04, "land_nod_deg_cm": 0.3,
	# Камера чуть отстаёт от тела в полёте, затем пружина отдельно отрабатывает приземление.
	"air_m": 0.0018, "air_deg": 0.045, "air_follow": 12.0,
	# как быстро размах следует за скоростью (шаг ↔ бег, остановка), 1/с; подстройка фазы к шагам, 1/с
	"amp_rate": 6.0, "lock_rate": 8.0,
	# в прицеле — доля сдвигов (в т.ч. высоты глаз) и поворотов; на ходу прицел заметно «дышит» шагом
	"ads_pos_k": 1.0, "ads_rot_k": 0.8,
	# по стойке: вприсядку мягче, ползком почти нет
	"stance": {"stand": 1.0, "crouch": 0.7, "prone": 0.35},
}
## Стойка «наискосок» от первого лица (Player.carry_low; бегом — всегда, колесо вниз — на ходу и стоя,
## колесо вверх — на изготовку от бедра): ствол поворачивается вокруг точки на pivot_back, м, позади правой
## кисти (у длинных — у затыльника приклада: приклад остаётся у плеча) — дулом влево (yaw)
## и вниз (pitch), с завалом (roll), град; shift — сдвиг в осях камеры, м (x — вправо, y — вверх, z — назад).
## У вьюмодели с клипами (руки — одно целое с оружием, ВЕРАС-54) поверх — clips: поворот всей сцены вокруг
## clips_pivot (оси камеры, м) и мягче, иначе плечи и рукава въезжают в камеру; до хвата из Blender.
## Опускается за lower_sec, поднимается за raise_sec, с. Стрелять можно, когда опущено не больше fire_max;
## нажатие огня в опущенном — подъём и выстрел, как только встало (ждёт до queue_sec, с). Лёжа и раненым —
## не опускается. Своё у класса (rifle, pistol) и у ствола — "carry" в data/weapons.json поверх этих чисел;
## "carry": false — без позы. Хват из Blender для ствола позже заменит эту позу.
const WEAPON_CARRY := {
	"rifle": {"yaw_deg": 35.0, "pitch_deg": 22.0, "roll_deg": -8.0, "shift": Vector3(0.0, 0.04, 0.0), "pivot_back": 0.15},
	"pistol": {"yaw_deg": 25.0, "pitch_deg": 40.0, "roll_deg": -8.0, "shift": Vector3(-0.03, -0.02, 0.03), "pivot_back": 0.0},
	"clips": {"yaw_deg": 20.0, "pitch_deg": 15.0, "roll_deg": -8.0, "shift": Vector3(0.0, 0.0, 0.0), "clips_pivot": Vector3(-0.2, -0.3, 0.05)},
	"lower_sec": 0.32, "raise_sec": 0.2, "fire_max": 0.15, "queue_sec": 0.4,
}
## Наклон из-за угла (Q/E, от первого лица и в прицеле): сдвиг глаза вбок, м; крен, град;
## скорость наклона (доля в секунду); на ходу в наклоне — медленнее.
const LEAN_OFFSET := 0.4
const LEAN_ROLL_DEG := 12.0
const LEAN_SPEED := 5.0
const LEAN_MOVE_SCALE := 0.6
## Наклон не заходит в стену: от глаза без наклона вбок ведётся шар этого радиуса, м, — глаз останавливается,
## где шар коснулся стены, двери или стекла (раньше голова уходила в стену на всю LEAN_OFFSET — в коопе
## подглядывали сквозь неё; приём Road to Vostok, docs/research/road_to_vostok.md).
const LEAN_WALL_RADIUS := 0.15
## Раскачка разброса очередью: за выстрел прибавка = подброс × RECOIL_BLOOM, потолок, спад в секунду;
## в прицеле раскачка — эта доля (была 0.4: очередь в прицеле почти не расходилась).
const RECOIL_BLOOM := 10.0
const RECOIL_BLOOM_MAX := 1.5
const RECOIL_BLOOM_DECAY := 2.5
const RECOIL_BLOOM_ADS := 0.75
## Разброс через прицел (решение владельца 2026-10-19): одна пуля идёт точно туда, куда смотрит линия
## прицеливания, — промахи только от отдачи, раскачки и дыхания, которые держит сам игрок. Доля прицельного
## разброса ствола (ads_spread), 0 — разброса нет. Дробь расходится по-прежнему; от бедра и с завалом
## (AIM_CANT, по точке ЛЦУ) разброс прежний (Player.shot_spread, WeaponStats.ads_spread_deg).
const ADS_SPREAD_K := 0.0
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
## Пасмурно — сплошные тучи без дождя: сыро, лужи после дождя, солнце едва пробивается, тени мягкие
## (сырой вечер с картинки зоны 1 — один из вариантов, не единственный; владелец 2026-10-19).
const RAID_WEATHER := {
	"clear": {"name": "Ясно", "risk": 0, "view": 1.0, "hear": 1.0},
	"overcast": {"name": "Пасмурно", "risk": 0, "view": 0.9, "hear": 1.0},
	"rain": {"name": "Дождь", "risk": 1, "view": 0.75, "hear": 0.6},
	"fog": {"name": "Туман", "risk": 1, "view": 0.45, "hear": 1.0},
	"heat": {"name": "Жара", "risk": 1, "view": 1.0, "hear": 1.0},
}
## Небо из HDR-панорамы (HdriSky, карта задаёт "sky_hdri" по времени суток): как погода меняет
## панораму — пасмурность (0 — как снято, 1 — сплошная пелена), экспозиция, оттенок; sun_k —
## множитель силы солнца (за пеленой прямого света меньше).
const HDRI_WEATHER := {
	"clear": {"overcast": 0.0, "exposure": 1.0, "tint": Color(1.0, 1.0, 1.0), "sun_k": 1.0},
	"overcast": {"overcast": 0.85, "exposure": 0.7, "tint": Color(0.88, 0.91, 0.95), "sun_k": 0.18},
	"heat": {"overcast": 0.0, "exposure": 1.15, "tint": Color(1.06, 1.0, 0.92), "sun_k": 1.15},
	"fog": {"overcast": 0.7, "exposure": 0.8, "tint": Color(0.95, 0.97, 1.0), "sun_k": 0.45},
	"rain": {"overcast": 1.0, "exposure": 0.5, "tint": Color(0.8, 0.84, 0.9), "sun_k": 0.0},
}
## Погода карт со своим процедурным небом (Проспект). Сплошные тучи освещают землю
## рассеянно: прямого солнечного луча и его жёсткой тени нет. Ночной свет задаётся отдельно.
const PROCEDURAL_WEATHER := {
	"overcast": {"sun_k": 0.0, "sky_k": 0.85},
	"rain": {"sun_k": 0.0, "sky_k": 0.65},
	"fog": {"sun_k": 0.15, "sky_k": 0.8},
}
const PROCEDURAL_CLOUD_SKY := {
	"top": Color(0.58, 0.62, 0.66), "horizon": Color(0.68, 0.70, 0.72),
	"ground": Color(0.22, 0.24, 0.25), "ground_horizon": Color(0.45, 0.47, 0.48),
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
## haze, км; steps — шагов луча (не меньше; в толстом слое — по шагу step_km, до steps_max); ветер wind_ms, м/с, откуда — wind_from, ° от севера; солнце за облаком
## тускнеет до sun_floor (sun_tau — доля толщи, что гасит свет: многократное рассеяние светит насквозь; было 0.25 —
## в ясную погоду облако на солнце «выключало» день: земля тусклая, без теней, владелец 2026-10-19).
## Непогода по погоде: deck_var — насколько неровна толщина сплошных туч (тоньше — светлее, солнце
## угадывается), base_rag — рваный низ, км; scud — доля неба под низкими клочьями (слой scud.base..top км,
## ветер ×wind_k и повёрнут на turn °, шагов steps), shafts — плотность полос дождя вдали. Смена погоды —
## небо перетекает за change_sec, с; перед дождём тучи собираются за rain_build_sec до него (гром —
## WEATHER_CHANGE.thunder_lead). Молния (flash): ядро core в радиусе radius_km, общий отсвет неба amb,
## пульсы pulses — [с от начала, сила], каждый гаснет за fade_sec; вспышка за dist_km от игрока. Канал до
## земли (flash.bolt) — у доли chance вспышек, ближе (dist_km): от низа туч (уходит в тучу на into_cloud_km,
## гаснет к низу туч за fade_km) до земли с наклоном до lean высоты; ломаная — depth делений пополам, середина
## сдвигается на ~rough длины; ветвей branches (сила branch_k, толщина branch_width, только в первом ударе);
## толщина width_m и ореол glow_m, м; яркость ядра core и ореола halo; гаснет за fade_sec; вспышка в туче — над
## верхом канала на flash_above_km. Шагов клочьев steps — не меньше 48 (при 24 по краям пятен полосы).
const SKY_CALC := {"sun_size": 0.53, "sun_clamp": 40.0, "amb_match": 1.0, "ground_blend": 3.0,
	"view_ref": 30, "view_dim": 0.5, "view_min": 0.25,
	"match_floor": -7.0, "twilight_adapt": 0.12, "cal_from": -18, "cal_to": 70,
	"weather": {
		"clear": {"mie": 1.0, "overcast": 0.0, "cover": 0.4, "base": 1.4, "top": 3.6, "amb_bottom": 0.4,
			"deck_var": 0.0, "base_rag": 0.0, "scud": 0.0, "shafts": 0.0},
		"overcast": {"mie": 1.6, "overcast": 0.85, "cover": 0.95, "base": 0.9, "top": 3.0, "amb_bottom": 1.1,
			"deck_var": 0.55, "base_rag": 0.2, "scud": 0.25, "shafts": 0.0},
		"heat": {"mie": 1.8, "overcast": 0.0, "cover": 0.2, "base": 2.0, "top": 4.0, "amb_bottom": 0.6,
			"deck_var": 0.0, "base_rag": 0.0, "scud": 0.0, "shafts": 0.0},
		"fog": {"mie": 4.0, "overcast": 0.5, "cover": 0.8, "base": 0.5, "top": 1.8, "amb_bottom": 0.85,
			"deck_var": 0.5, "base_rag": 0.15, "scud": 0.3, "shafts": 0.0},
		"rain": {"mie": 2.0, "overcast": 1.0, "cover": 1.0, "base": 0.6, "top": 4.0, "amb_bottom": 1.4,
			"deck_var": 0.6, "base_rag": 0.35, "scud": 0.45, "shafts": 0.5}},
	"change_sec": 45.0, "rain_build_sec": 150.0,
	"scud": {"base": 0.25, "top": 0.6, "wind_k": 2.2, "turn": -35.0, "steps": 64},
	"flash": {"core": 25.0, "radius_km": 0.9, "amb": 0.25, "color": Color(0.75, 0.82, 1.0),
		"pulses": [[0.0, 1.0], [0.08, 0.45], [0.2, 0.8]], "fade_sec": 0.06, "dist_km": [3.0, 12.0],
		"bolt": {"chance": 0.5, "dist_km": [2.0, 7.0], "into_cloud_km": 0.12, "fade_km": 0.06, "lean": 0.35,
			"depth": 5, "rough": 0.26, "branches": [1, 3], "branch_k": 0.5, "branch_width": 0.55,
			"width_m": 3.0, "glow_m": 30.0, "core": 60.0, "halo": 3.0, "fade_sec": 0.1, "flash_above_km": 0.15}},
	"clouds": {"sigma": 30.0, "cover_tile": 30.0, "shape_tile": 9.0, "detail_tile": 1.2, "detail_k": 0.55,
		"sun": 0.3, "far": 70.0, "haze": 35.0, "steps": 96, "step_km": 0.023, "steps_max": 160, "wind_ms": 9.0, "wind_from": 250.0,
		"sun_tau": 0.25, "sun_floor": 0.55}}
## Туман по расстоянию (карты, у которых в окружении fog_mode = depth): вблизи чисто, дальше — дымка,
## плотнее к горизонту (кривая). begin/end — метры, density — сколько дымки на end (0..1), curve > 1 —
## дольше прозрачно, потом быстрее густеет. Вместо «дыма одной плотности» — воздушная перспектива.
const DEPTH_FOG := {
	"clear": {"begin": 25.0, "end": 900.0, "density": 0.55, "curve": 1.35},
	"overcast": {"begin": 15.0, "end": 650.0, "density": 0.68, "curve": 1.15},
	"heat": {"begin": 40.0, "end": 1100.0, "density": 0.45, "curve": 1.2},
	"rain": {"begin": 10.0, "end": 420.0, "density": 0.8, "curve": 1.0},
	"fog": {"begin": 4.0, "end": 170.0, "density": 0.97, "curve": 0.8},
}
## Дымка по времени суток (объёмный туман карты): множитель плотности и сила солнца в ней — на закате
## воздух гуще и солнце низко: лучи между стволами и ветками.
## Жара: пересвет и марево по времени суток (ночью жара есть, а солнца — нет).
const HEAT_TIME := {"day": 1.0, "dusk": 0.5, "night": 0.0}
const VOLUMETRIC_TIME := {"day": {"density": 1.0, "sun": 1.4}, "dusk": {"density": 1.6, "sun": 2.6}, "night": {"density": 1.0, "sun": 0.6}}
## Лампы котельного зала: перекрывающиеся блики не должны превращать сухие руки и оружие в масляные.
const SHELTER_LIGHTING: Dictionary = {"hall_specular": 0.12}
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
	"dusk_fog": {"a": "res://assets/sky/kloppenheim_01_puresky.hdr", "exposure": 1.05, "sun_k": 0.22, "veil": 0.4, "haze": 0.6},
	"day_overcast": {"a": "res://assets/sky/kloofendal_overcast_puresky.hdr", "exposure": 1.0, "sun_k": 0.0, "veil": 0.6, "haze": 0.45},
	"dusk_overcast": {"a": "res://assets/sky/kloppenheim_01_puresky.hdr", "exposure": 1.0, "sun_k": 0.0, "veil": 0.6, "haze": 0.45}}
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
## пасмурно → дождь (шанс overcast_rain_chance, сроки те же), туман → рассеется (шанс, через сколько).
const WEATHER_CHANGE := {"rain_chance": 0.3, "overcast_rain_chance": 0.45, "rain_after": [180.0, 600.0], "thunder_lead": 50.0,
	"fog_lift_chance": 0.4, "fog_lift_after": [300.0, 720.0]}
## Мокрая земля (асфальт, шейдер wet_asphalt): за сколько секунд дождя намокает плёнкой и
## наливаются лужи, за сколько после дождя сохнет плёнка и уходят лужи; лужи наливаются не
## выше puddle_max; рейд начался в дождь — уже мокро (start: [плёнка, лужи]). Пасмурно — сыро
## после дождя (damp: [плёнка, лужи, сырость фасадов, коры, травы и рельефа — global rain_wet]),
## ниже этого не сохнет.
const WET_GROUND := {"film_up_sec": 45.0, "puddle_up_sec": 200.0, "film_dry_sec": 300.0, "puddle_dry_sec": 900.0,
	"puddle_max": 0.85, "start": [1.0, 0.7], "damp": [0.7, 0.45, 0.4]}
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
## Тащить раненого (B): скорость того, кто тащит, м/с; на каком расстоянии тело за ним, м.
const DRAG_SPEED := 1.2
## Несёт раненого NPC на плече (сюжет): скорость, м/с (бег невозможен).
const CARRY_SPEED := 1.7
const DRAG_DIST := 0.95
## Лежит — держать B столько секунд: сдаться (умереть сразу).
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
## Убранное оружие на теле (SlungWeapons; владелец 2026-10-29: «надо, чтобы было видно»), у игроков и ботов.
## Длинное — за спиной наискосок: приклад над правым плечом, ствол к левому бедру, back_tilt_deg от вертикали;
## центр — на back_y м от позвонка Spine2, вплотную к самому дальнему назад, что надето (тело, броня, рюкзак),
## с зазором back_gap_m (меньше нуля — внахлёст с тканью рюкзака); второе длинное — накрест, ещё на second_gap_m дальше. Пистолет — стволом вниз в кобуре
## на правом бедре (ракетница — на левом): thigh_out_m вбок от оси бедра, thigh_down_m ниже тазобедренного,
## thigh_fwd_m вперёд; кобура — коробка по модели: holster_k длины от дула, holster_h высоты от верха затвора
## (рукоять снаружи), holster_pad_m запас.
## Дальше draw_m от камеры не рисуется; вид игрока (снаряжение и убранное) сверяется раз в every с.
const SLUNG := {"every": 0.25, "back_tilt_deg": 32.0, "back_y": -0.06, "back_gap_m": -0.035, "second_gap_m": 0.02,
	"thigh_out_m": 0.105, "thigh_down_m": 0.3, "thigh_fwd_m": 0.0, "holster_k": 0.75, "holster_h": 0.55, "holster_pad_m": 0.012,
	"holster_color": Color(0.08, 0.085, 0.07), "draw_m": 70.0}
## Раскачка в прицеле: амплитуда, рад (стоя; сидя ×0.6, лёжа ×0.3, на сошках ещё ×0.4).
const SWAY_MAX := 0.012
const SWAY_MIN := 0.0015
const SWAY_STANCE := {"stand": 1.0, "crouch": 0.6, "prone": 0.3}
## Оптика отдельным рендером: разрешение картинки в окуляре, px. Кратность меняет только линзу.
const SCOPE_RT_SIZE := 768
## Переменная кратность: увеличение на один шаг колеса и задержка отправки состояния хосту, с.
const SCOPE_ZOOM := {"step": 1.0, "sync_sec": 0.2}

# --- Вид «как с камеры» (CameraLook, настройки «Эффекты камеры», «Размытие в движении») ---
## Глаз привыкает к свету: средняя яркость кадра ведётся к scale (в рейде — exposure_scale_raid: при 0.3 день
## был вдвое темнее, чем в Таркове, Far Cry, Battlefield — средняя яркость кадра ~55 из 255 против ~110;
## владелец 2026-10-19: «всё тусклое, выцветшее»; 0.6 — против солнца тени и оружие всё ещё в черноте, 0.9 — средняя
## яркость дня 108–112, как у образцов; в темноте не влияет — там предел adapt_up), но поправка к экспозиции сцены не
## больше adapt_up (тёмный угол, лес и ночь светлее; было 1.6 — в темноте не было видно ни очертаний, ни
## своего оружия, владелец 2026-10-19) и не меньше adapt_down (окно, фонарь в лицо); speed — за сек.
## В убежище — adapt_up_shelter и без ночного зрения: его свет настроен и одобрен владельцем. Внутри здания
## в рейде — adapt_up_indoor (тёмная квартира на порядок темнее ночного двора); где игрок — раз в context_sec.
## Ночное зрение: темнее scotopic_l (яркость на экране) цвет уходит и холодеет (scotopic_tint) на долю
## scotopic — ночь видна ночью и при поднятой экспозиции; только в темноте (ночь, помещение без света —
## RaidAtmosphere.is_dark), включается и уходит за scotopic_sec: днём тёмная листва не серела. Контраст не трогает тени темнее black_keep
## (прежде всё темнее ~7/255 становилось чёрным).
## Объектив: бочка (distortion; 0 — пересчёт кадра давал «мыло», владелец 2026-10-07), цветная кайма к краям (aberration, доля экрана), виньетка, зерно
## (сильнее в тенях), резкость, грейд — насыщенность, контраст, холодные тени и тёплые света.
## В прицеле бочка и кайма уходят (aim), а оружие у лица чуть размыто (dof_*: ближе near_m — размыто).
## «Зайчики» объектива (LensFlare): flare_ref — яркость источника (энергия × свет, с расстоянием) для полных.
## Размытие в движении — по векторам движения кадра: доля кадра «выдержки» и предел длины мазка;
## ближе blur_keep_m (руки, оружие) не размывается. По умолчанию выключено (Settings.motion_blur).
const LOOK := {"exposure_scale": 0.3, "exposure_scale_raid": 0.9, "adapt_up": 5.0, "adapt_up_indoor": 12.0, "adapt_up_shelter": 1.6, "adapt_down": 0.6,
	"adapt_speed": 1.6, "context_sec": 0.25,
	"scotopic": 0.55, "scotopic_l": 0.22, "scotopic_tint": Color(0.86, 0.95, 1.12), "scotopic_sec": 1.5, "black_keep": 0.12,
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
## Смена стойки: глаз переходит на новую высоту плавно, без рывка, примерно за столько секунд.
const ADS_EYE_SETTLE_SEC := 0.3
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
## AUDIO_OCCLUDED_DB: преграда уменьшает только громкость готовой записи.
## Бегом не чаще ~3 шагов в секунду, как у настоящего бегуна (было 0.26 с — почти 4 в секунду: камера
## на бегу тряслась мелко и «хаотично», владелец 2026-10-19).
const STEP_STRIDE := 1.2
const STEP_WALK_SEC: float = STEP_STRIDE / PLAYER_WALK_SPEED
const STEP_RUN_SEC: float = 0.33
const STEP_INTERVAL := [STEP_RUN_SEC, 0.75]
## Встал — следующий шаг готов: тронулся — первый шаг не позже STEP_START_SEC, с. Фаза шага идёт к этой
## точке плавно, со скоростью STEP_READY_RATE долей шага в секунду (камера в той же фазе — без рывка).
const STEP_START_SEC := 0.12
const STEP_READY_RATE := 2.0
const STEP_RUN_SPEED := 3.8
const STEP_STANCE_DB := {"stand": 0.0, "crouch": -8.0, "prone": -14.0}
## Источник у стопы даёт мягкое чередование панорамы, включая поворот персонажа.
const STEP_FOOT_SIDE_M := 0.12
## Слой поверх пола тише основного удара подошвы. Высота области нужна, чтобы слой не слышался этажом выше.
const STEP_LAYERS: Dictionary = {
	"glass": "Битое стекло",
	"leaves": "Листья",
	"trash": "Мусор",
}
const STEP_LAYER_HEIGHT: float = 0.65
const STEP_GLASS_SPREAD: float = 1.1
## Свои записи владельца — только ходьба по мокрому асфальту; бег пока отдельным старым набором.
## Плёнка сохнет раньше луж, поэтому вода под ногами остаётся слышна после дождя.
const WET_STEPS := {"film_min": 0.35, "puddle_min": 0.2, "roof_lift": 0.35, "roof_height": 128.0,
	"sound": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true}}
## Вода вброд (болото зоны 1 — по пояс, ручей в овраге; владелец 2026-10-18): глубина над ступнями, м.
## speed / ai_speed — множитель скорости по щиколотку, по колено, по пояс (между — плавно);
## глубже no_sprint — бежать нельзя, глубже no_prone — лечь нельзя (встаёт на колено);
## шаги в воде слышнее (noise_k), брызги и круги — ближе fx_distance к камере.
const WATER := {"ankle": 0.12, "knee": 0.45, "waist": 0.9, "speed": [1.0, 0.78, 0.55], "ai_speed": [1.0, 0.8, 0.6],
	"no_sprint": 0.5, "no_prone": 0.25, "noise_k": 1.6, "fx_distance": 45.0}
const AUDIO_OCCLUDED_DB := 8.0

## Место выстрела (AcousticPlace, лучи физики от ствола): ceiling_max_m — выше потолка нет (небо — улица);
## четыре луча вверх-вбок под 45° (длина — высота потолка × 2): попали меньше side_hits_min — это навес без
## стен, улица; восемь лучей по сторонам до wall_max_m, их медиана и высота потолка над стволом: меньше
## room_median_m и ниже hall_up_m — помещение, иначе большое (ангар, зал, арена, атриум). Результат
## запоминается на ttl_sec для клетки cell_m (мародёры стреляют часто).
const SHOT_PLACE := {"ceiling_max_m": 40.0, "wall_max_m": 30.0, "side_hits_min": 2, "room_median_m": 9.0,
	"hall_up_m": 5.5, "cell_m": 3.0, "ttl_sec": 4.0}
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
## Карта может переопределить любой ключ словарём "ai" в своих данных.
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
## Залезть наверх (Пробел у того, на что можно встать: машина, ящик, край платформы; Climb): высота
## от VAULT.min_h до max_h, м, с полным перегрузом — до max_h_loaded; дотянуться — reach от ног, м.
## Тоньше vault_thick, м (пол сразу за преградой), — перелезает через (VAULT), толще — залезает на неё.
## Время на min_h и на max_h, с (с перегрузом — дольше на VAULT.weight_k); шум, м; выносливость на min_h
## и на max_h. Наверху место только сидя — залезает в присед.
const CLIMB := {"max_h": 2.0, "max_h_loaded": 1.5, "reach": 0.9, "vault_thick": 1.0, "sec_low": 0.6,
	"sec_high": 1.5, "noise_m": 14.0, "stamina_low": 8.0, "stamina_high": 18.0}
## Вертикальная лестница (Ladder, scenes/world/ladder.tscn). Скорость вверх и вниз, м/с; бегом (Shift) —
## × hurry_k, выдохся — × winded_k, с полным перегрузом — × loaded_k. Тело от плоскости лестницы, м; ноги
## на верхней ступени — на top_gap, м, ниже площадки. Выносливость за метр подъёма; шум на перекладину
## (каждые rung_m, м) — радиус, м. Схватиться Пробелом — не дальше grab_m, м; снова — не раньше
## cooldown, с; спрыгнуть — толчок от лестницы, м/с. Подойти к лестнице снизу, с. Мародёры — скорость, м/с;
## цена связки навигации (обход по лестнице дороже ходьбы).
const LADDER := {"up_mps": 1.0, "down_mps": 1.3, "hurry_k": 1.4, "winded_k": 0.5, "loaded_k": 0.6,
	"body_off": 0.42, "top_gap": 0.45, "stamina_per_m": 2.5, "rung_m": 0.3, "noise_m": 9.0, "grab_m": 0.9,
	"cooldown": 0.5, "push_mps": 1.2, "enter_sec": 0.3, "ai_mps": 0.8, "travel_cost": 3.0}

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
## ПЗРК «Осока» (wpn_mp_01; OsokaSeeker, OsokaMissile). Головка самонаведения включается, когда комплекс вскинут
## к прицелу: рычаг «НАКОЛ», через power_sec батарея и гироскоп готовы. Тепловая цель (группа "heat_targets") в конусе
## cone_deg от линии прицела ближе lock_range_m и на виду — поиск: прерывистый писк, жёлтая метка; продержал lock_sec —
## захват: ровный писк, лампа на целике, метка зелёная; захват держится, пока цель в track_deg от линии. Без захвата
## пуска нет (need_lock). Ракета выходит из трубы со скоростью eject_mps, двигатель — через ignite_m (рули и
## стабилизаторы раскрываются за fins_sec), разгон до speed_mps за boost_sec, двигатель горит burn_sec (дымный след),
## через life_sec — самоликвидация. Наведение пропорциональное (nav_k) с пределом перегрузки max_g; взрыватель —
## ближе fuse_m к цели или удар. Боевая часть: урон damage в радиусе radius_m (с прямой видимостью, как у гранаты),
## толчок push. roll_hz — вращение ракеты в полёте (вид). Пуск слышно на noise_m; тряска камеры — shake.
## След (trail_*): частица на каждые step_m, живёт life_sec, растёт от size[0] до size[1] м.
## Писк ГСН (tone_*): частота поиска / захвата, Гц; громкость, дБ; прерывистый — beep_hz в секунду в начале захвата
## и beep_fast_hz к его концу.
const OSOKA := {"power_sec": 0.9, "cone_deg": 3.0, "lock_sec": 1.6, "track_deg": 9.0, "lock_range_m": 5500.0,
	"need_lock": true, "eject_mps": 28.0, "ignite_m": 5.5, "fins_sec": 0.12, "speed_mps": 570.0, "boost_sec": 1.8,
	"burn_sec": 8.0, "life_sec": 14.0, "nav_k": 4.0, "max_g": 28.0, "fuse_m": 4.0, "damage": 650.0, "radius_m": 7.0,
	"push": 9.0, "roll_hz": 2.5, "noise_m": 220.0, "shake": 0.55,
	"trail_step_m": 1.6, "trail_life_sec": 9.0, "trail_size": [0.35, 2.6],
	"tone_hz": [760.0, 1180.0], "tone_db": -9.0, "beep_hz": 3.0, "beep_fast_hz": 9.0}
## Учебная цель для ПЗРК (HeliTarget, стенд tools/osoka_range.tscn): процедурный вертолёт кружит над точкой стенда —
## радиус radius_m, высота alt_m над землёй (± alt_wave_m), скорость speed_mps, крен в вираже bank_deg; несущий винт —
## rotor_hz оборотов в секунду (лопастей blades), рулевой — tail_hz. Звук винтов — процедурный: слышен издалека
## (unit_m — расстояние, на котором громкость полная; до max_m), громкость db. Подбили — горит и падает
## (fall_spin — оборотов в секунду к земле), на земле — взрыв; через respawn_sec — новый заход.
const HELI_TARGET := {"radius_m": 380.0, "alt_m": 120.0, "alt_wave_m": 18.0, "speed_mps": 42.0, "bank_deg": 12.0,
	"rotor_hz": 4.3, "blades": 4, "tail_hz": 19.0, "unit_m": 70.0, "max_m": 4500.0, "db": 4.0, "fall_spin": 0.7,
	"respawn_sec": 12.0}
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
## объёмный туман слабее (× fog_k). Под SDFGI ровный цвет не действует — рассеянный ночью идёт «полом»
## в карту неба: тот же цвет × sky_floor, в любую погоду (DayCycle → amb_floor шейдеров неба; видимое небо
## то же) — лес, руки и оружие ночью не в черноте. Ясной ночью светлее — от Луны.
const NIGHT_ENV := {"ambient_color": Color(0.09, 0.11, 0.16), "glow_threshold": 1.3, "glow_intensity": 0.4, "glow_bloom": 0.0,
	"fog_k": 0.55, "fog_sky": 0.08, "moon_fog": 0.12, "sky_floor": 0.36}
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
## jam_base × (1 + износ² × jam_worn) (износ = (100 − прочность)/100); устранить — clear_sec, затвор
## отпускают на доле clear_release_at этого времени (звук «вперёд» и выпавшая гильза).
const WEAPON_WEAR := {"spread": 0.8, "jam_base": 0.012, "jam_worn": 25.0, "clear_sec": 1.5, "clear_release_at": 0.6}
## Гильза после выстрела (Audio.shell_drop): падает рядом со стрелком через delay_* с; в сторону side_* м
## и чуть назад; звук по полу — hard (плитка, бетон), metal, остальное мягкое; на твёрдом иногда катится.
## Дальше hear_m от слушателя гильзу не считаем (мародёры стреляют часто).
const SHELL_DROP := {"delay_min": 0.22, "delay_max": 0.42, "side_min": 0.45, "side_max": 0.9, "back": 0.15, "db": -3.0,
	"roll_chance": 0.3, "roll_delay": 0.16, "hear_m": 30.0, "hard": ["tile", "concrete"], "metal": ["metal"]}
## Ресурс оружия/обвесов в процентах; пороги ступеней (подписи, цвет в окнах — вид модели один), расход на
## выстрел и ремонт.
const CONDITION := {"full": 100.0, "used": 60.0, "worn": 20.0,
	"weapon_wear": 0.02, "mod_wear": 0.002,
	"shot_wear": {"OPTIC_RED_DOT": 0.001, "OPTIC_HOLOGRAPHIC": 0.001,
		"OFFSET_RED_DOT": 0.001, "SUPPRESSOR": 0.025},
	"repair_weapon": 0.35, "repair_mod": 0.45, "repair_min": 50,
	"reticle_min": 0.45, "cache_entries": 256}
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
## Свет в руку (решение владельца 2026-10-19): Y — зелёный химсвет, G — ракетница, двойное G (второе нажатие не позже
## double_tap_sec) — красный фальшфейер; химсвет и фальшфейер бросают как гранату (Balance.GRENADE_HAND).
const LIGHT_KEYS := {"double_tap_sec": 0.3}
## Режимы огня (решение владельца 2026-10-19): X переводит по кругу в порядке "fire_modes" ствола (у ВЕРАС-54
## АВ → 2 → ОД → АВ; предохранителя нет), по умолчанию первый. burst — патронов за нажатие в режиме «2» (очередь
## доходит до конца, даже если спуск отпустили); switch_sec — переводчик большим пальцем (клип рук 18 кадров), пока он
## щёлкает, не стрелять.
const FIRE_MODES := {"burst": 2, "switch_sec": 0.6,
	"labels": {"auto": "АВ", "burst": "2", "semi": "ОД"},
	"names": {"auto": "автоматический", "burst": "очередь по 2", "semi": "одиночный"}}
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
## После подтверждения цели — довести оружие, затем открыть огонь (отдельно от разброса).
## В упор быстрее; короткий повторный выход не сбрасывает готовность. Новая цель, большой
## скачок направления или долгая потеря — новое доведение. Подготовленная засада держит угол.
const AI_FIRE_REACTION := {
	"profiles": {"scav": [0.55, 0.9], "veteran": [0.35, 0.6], "pmc": [0.22, 0.4]},
	"archetypes": {"heavy": "veteran", "sniper": "veteran", "bank_boss": "veteran",
		"bank_guard": "veteran", "pmc": "pmc", "rival": "veteran", "rival_scout": "veteran", "rival_sniper": "veteran"},
	"close_m": 5.0, "full_m": 25.0, "close_sec": [0.15, 0.25], "prepared_sec": [0.15, 0.3],
	"reset_sec": 1.2, "turn_deg": 40.0,
}
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
## позицию: не сближается, патруль у своего поста, ищет глазами, а не ногами (снайпер ходит один);
## ambush — склонность к засаде (× AI_AMBUSH.chance; нет — 1): разведчик рвётся вперёд, бывалый и ЧВК ждут.
## Рост и сложение у всех ботов натуральные — масштаба по типу нет (решение владельца 2026-10-24: разные
## сложения — разными телами, docs/design/npc_appearance_catalog.md).
const AI_ARCHETYPES := {
	"scout": {"name": "Разведчик", "weight": 0.4, "loadout": "scav_poor", "speed": 1.3, "hp": 0.85,
		"memory": 0.5, "view": 1.1, "color": Color(0.46, 0.4, 0.28), "holds": false, "ambush": 0.5},
	"gunner": {"name": "Штурмовик", "weight": 0.42, "loadout": "scav_standard", "leader": {"chance": 0.1, "loadout": "scav_leader"}, "speed": 1.0, "hp": 1.0,
		"memory": 1.0, "view": 1.0, "color": Color(0.36, 0.2, 0.16), "holds": false},
	"heavy": {"name": "Бывалый", "weight": 0.1, "loadout": "scav_veteran", "speed": 0.85, "hp": 1.2,
		"memory": 1.3, "view": 0.95, "color": Color(0.18, 0.22, 0.2), "holds": false, "ambush": 1.5},
	"sniper": {"name": "Снайпер", "weight": 0.08, "loadout": "scav_sniper", "speed": 0.9, "hp": 0.9,
		"memory": 1.5, "view": 2.2, "color": Color(0.3, 0.33, 0.24), "holds": true},
	# главарь с охраной — пост «не каждый рейд» (AIPost.lead_arch, chance; «Проспект» — банк). Имя, вид и
	# предыстория — текстом на согласование владельцу; пока только роль. С главаря — ключ-карта хранилища.
	"bank_boss": {"name": "Главарь в банке", "weight": 0.0, "loadout": "bank_boss", "speed": 0.9, "hp": 1.6,
		"memory": 1.6, "view": 1.1, "color": Color(0.12, 0.1, 0.1), "holds": false, "ambush": 1.6},
	"bank_guard": {"name": "Охрана главаря", "weight": 0.0, "loadout": "scav_veteran", "speed": 1.0, "hp": 1.15,
		"memory": 1.4, "view": 1.05, "color": Color(0.16, 0.15, 0.14), "holds": false, "ambush": 1.3},
	# третья сторона — не выпадают случайно (weight 0): ставят события и уровень
	# «Периметр» — не толще людей: опасны снаряжением (броня, патроны), меткостью и слаженностью
	"pmc": {"name": "ЧВК «Периметр»", "weight": 0.0, "loadout": "perimeter_rifleman", "speed": 1.05, "hp": 1.0,
		"memory": 1.4, "view": 1.2, "color": Color(0.1, 0.12, 0.15), "holds": false,
		"faction": "pmc", "loots": false, "ambush": 1.4},
	"resident": {"name": "Жилец", "weight": 0.0, "loadout": "civilian", "speed": 0.95, "hp": 1.0,
		"memory": 1.0, "view": 0.9, "color": Color(0.55, 0.48, 0.38), "holds": false,
		"faction": "resident", "loots": false, "ambush": 0.4},
	# чужие отряды (RivalRaids): пришли за добычей, как и игроки, — обыскивают, уносят, воюют со всеми
	"rival": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_veteran", "leader": {"chance": 0.0, "loadout": "scav_leader"},
		"speed": 1.08, "hp": 1.0, "memory": 1.3, "view": 1.15, "color": Color(0.2, 0.24, 0.3),
		"scale": Vector3(1.02, 1.0, 1.02), "holds": false, "faction": "rival", "ambush": 1.2},
	"rival_scout": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_standard", "speed": 1.25, "hp": 0.9,
		"memory": 0.9, "view": 1.2, "color": Color(0.26, 0.28, 0.22), "holds": false,
		"faction": "rival", "ambush": 0.6},
	"rival_sniper": {"name": "Чужой отряд", "weight": 0.0, "loadout": "scav_sniper", "speed": 0.95, "hp": 0.9,
		"memory": 1.5, "view": 2.0, "color": Color(0.24, 0.27, 0.2), "holds": false,
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
## Спасатель не идёт и сдаётся, если не дойти: путь по сетке кончается дальше path_end_m от раненого
## (раненый за стеной на несвязанном участке; между участками — стена и два радиуса агента, ≥ 0,9 м),
## при выборе — сразу, на бегу — если это держится no_path_sec; или остаток пути не сократился
## на progress_m за stall_sec. Сдавшегося раненый за это ранение больше не зовёт.
const AI_RESCUE_GIVE_UP := {"path_end_m": 0.75, "no_path_sec": 1.0, "progress_m": 1.0, "stall_sec": 8.0}
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
## Точки укрытия карты с направлением (src/ai/cover_points.gd, запекает tools/bake_cover_points.tscn; приём Road to
## Vostok): мародёр сначала смотрит их в радиусе AI_COVER_RADIUS × radius_k — угроза в конусе направления точки
## (скалярное не меньше cone_dot), точка ближе к нему, чем к угрозе, не занята другим (его укрытие ближе claim_m),
## присевшего за ней не видно с угрозы; лучше случайной на bonus метров оценки. grid_m — клетка поиска, м.
## bake — запекание: шаг выборки по навигации step, м; лучи на высоте low_h / crouch_h (пояс, глаза присевшего) должны
## упереться ближе reach, на высоте глаз стоящего over_h — быть свободны на over_reach (низкое укрытие); угол — стена
## ближе reach на over_h, шаг вбок corner_side свободен и оттуда вперёд corner_reach; найденная точка придвигается к
## препятствию до hug (навигация отстоит от стен на радиус бойца); точки не ближе min_gap друг к другу.
const AI_POINTS := {"on": true, "radius_k": 1.5, "cone_dot": 0.6, "bonus": 6.0, "claim_m": 1.2, "grid_m": 16.0,
	"bake": {"step": 1.5, "low_h": 0.6, "crouch_h": 1.0, "over_h": 1.65, "reach": 1.6, "over_reach": 2.5, "hug": 0.65,
		"corner_side": 0.8, "corner_reach": 3.0, "min_gap": 2.0}}
const AI_COVER_HIDE := [0.8, 1.8]
const AI_COVER_PEEK := [1.2, 2.4]
## Засада («держит угол», как боты Таркова — docs/design/ai_tarkov_principles.md): цель ушла из виду —
## с шансом chance (× ambush архетипа) не идёт вперёд, а садится в укрытие стволом на последнюю точку
## и ждёт hold_sec [от, до]; в отряде так делает не больше одного. Цель показалась у той же точки
## (ближе near_m) — прицел уже «сидит»: разброс × aim вместо AI_AIM_COLD. Шум цели дальше break_m
## от точки — засада снята; цель ближе min_dist — не садится (уже в упор).
const AI_AMBUSH := {"chance": 0.45, "hold_sec": [10.0, 25.0], "near_m": 8.0, "aim": 1.15, "break_m": 15.0, "min_dist": 6.0}
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
## Идёт медленнее slow_k от желаемого дольше door_sec и впереди (до door_reach м) открытая створка — толкает её
## на другую сторону проёма (Door.push_from: сетка путей створок не знает).
const AI_UNSTUCK := {"stuck_sec": 2.0, "side_sec": 0.7, "tries": 3, "min_speed": 0.25, "slow_k": 0.5, "door_sec": 0.6, "door_reach": 1.0}
const AI_FOLLOW_DIST := 2.6
## Отряды: сколько в отряде (от и до).
const AI_SQUAD_SIZE := [1, 3]
## Патруль: пауза на точке, с.
const AI_PATROL_PAUSE := [1.5, 4.0]
## Расследование: сколько стоять на месте шума, прежде чем вернуться к патрулю, с.
const AI_INVESTIGATE_LINGER := 5.0

## Большая городская карта: бюджеты отрисовки и точность заранее выпеченной навигации.
## publish_sec — сколько ждать очередной итерации карты, пока тайлы не опубликованы: одна синхронизация карты ТЦ
## (58 тыс. полигонов, 45 тыс. свободных рёбер сервер сверяет попарно) — 6,5–12 с; без кэша с окном итераций
## несколько, готово к ~29 с (замер 2026-10-29).
const URBAN_WORLD := {
	"batch_cell": 64.0, "prop_distance": 650.0, "view_distance": 2400.0,
	"deck_margin": 0.25,
	"nav_tile": 250.0, "nav_cell": 0.5, "nav_height": 0.25, "nav_border": 2.0, "publish_sec": 30.0,
	"nav_radius": 0.5, "nav_agent_height": 1.8, "nav_climb": 0.4, "nav_slope": 40.0,
	"nav_merge_scale": 0.125,
	"nav_detail_error": 2.0,
	# полоса у шва тайлов, м: её многоугольники — отдельный регион со связями по краю (UrbanNavigation);
	# не меньше запаса связей карты (navigation/3d/default_edge_connection_margin, 0,25 м)
	"nav_seam_band": 1.0,
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
		["spray_paint", 0.8, [1, 1]], ["sticker_film", 0.7, [1, 2]], ["printer_body", 0.12, [1, 1]], ["pouch_pistol", 0.3, [1, 1]]
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
		["water", 2, [1, 1]], ["binoculars", 0.6, [1, 1]], ["thermos", 1, [1, 1]],
		["work_gloves", 1, [1, 1]], ["nothing", 4, [0, 0]], ["pouch_pistol", 0.6, [1, 1]], ["pouch_rifle", 0.3, [1, 1]]
	]},
	"home": {"rolls": [1, 2], "entries": [
		["thermos", 2, [1, 1]], ["kettle", 2, [1, 1]], ["wall_clock", 2, [1, 1]], ["cassette_player", 1.5, [1, 1]],
		["work_gloves", 1, [1, 1]], ["desk_lamp", 1.5, [1, 1]], ["video_camera", 0.3, [1, 1]], ["binoculars", 0.4, [1, 1]],
		["nothing", 4, [1, 1]], ["pouch_pistol", 0.25, [1, 1]]
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
	"sport": [["pouch_pistol", 0.3], ["pouch_rifle", 0.15]],
	"security": [["pouch_pistol", 0.4], ["pouch_rifle", 0.25], ["tac_laser_01", 0.2]],
	"storage": [["pouch_pistol", 0.12]],
	"home": [["pouch_pistol", 0.12]],
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
	"armor_tier": 3, "extras": [["medkit", 1, 2], ["painkillers", 1, 2], ["grenade", 2, 3], ["pouch_rifle", 0, 1]]}
const SUPPLY_PLANE_SOUND := {"db": 12.0, "unit": 60.0, "max": 600.0}

## Свет в зданиях блокаутов Пригорода (левел-дизайн 2026-10-19): в залах — вдоль оси (по одной на 14 м, не больше
## четырёх), на лестничной площадке каждого этажа, в доме — по одной на этаж; без теней, гаснут вдали
## (fade_begin + fade_length, м); в зале радиус не меньше wide_k ширины. Питание — как у света ТЦ (группа mall_lights): нет — темно, аварийное — красные.
const BLOCKOUT_LIGHTS := {"energy": 1.1, "range": 9.0, "fade_begin": 30.0, "fade_length": 8.0, "step_m": 14.0, "max": 4, "wide_k": 0.75,
	"color": Color(1.0, 0.8, 0.58)}

## Узкие жилые двери и лестницы зоны 1: отдельная точность кэша, остальные карты прежние;
## publish_sec — сколько ждать, пока сервер опубликует тайлы (с интерьерами и укрытиями блокаутов навмеш подробнее,
## публикация ≈ 5 с — левел-дизайн 2026-10-19).
const ZONE01_INTERIOR_NAV := {
	"nav_tile": 240.0, "nav_cell": 0.125, "nav_height": 0.0625, "nav_border": 2.0,
	"nav_radius": 0.375, "nav_detail_error": 1.0, "nav_merge_scale": 0.0078125, "publish_sec": 30.0,
}

## Тестовое прохождение заданий (владелец, 2026-10-17): у целей с test_hint — всплывающая
## инструкция «что делать» на экране и в журнале (J). К релизу — false (тексты test_hint можно
## оставить в данных: при false они не показываются нигде).
const QUEST_TEST_HINTS := true
## Сколько секунд инструкция видна после смены цели (дальше — в журнале).
const QUEST_TEST_HINT_SEC := 25.0

## Подписи сдачи радиатора: читаются около машины, через стены не видны.
const CAR_DELIVERY_LABEL := {"crate_range_m": 12.0, "hood_range_m": 4.5}


## Sonora: единые параметры слышимости, никаких чужих записей или дистанционных слоёв.
## Липучка подсумка при перезарядке (звук pouch_velcro): обычная — когда старый магазин скрылся из вида
## (у ВЕРАС — кадр подмены клипа рук, у ПМ / Glock — фаза mag_hidden, у остальных — доля hidden_k
## от времени перезарядки), быстрая — сразу; height_m — где звучит над ногами (подсумки на груди).
const POUCH_VELCRO := {"hidden_k": 0.34, "height_m": 1.25}

const AUDIO_EVENT_PROFILES: Dictionary = {
	"osoka_launch": {"db": 0.0, "unit": 6.0, "max": 500.0, "occlude": true, "far": true},
	"osoka_motor": {"db": 6.0, "unit": 35.0, "max": 4000.0, "occlude": true},
	"osoka_seeker_track": {"db": -12.0, "unit": 1.0, "max": 10.0},
	"osoka_seeker_lock": {"db": -12.0, "unit": 1.0, "max": 10.0},
	# выстрелы слышно далеко (бой на сотни метров): дальше — тише, глуше (фильтр) и позже (звук
	# идёт 343 м/с — Audio.play задерживает); по расстоянию сменяются слои записей (LAYERS)
	"shot_pistol": {"db": 2.0, "unit": 10.0, "max": 450.0, "far": true},
	"shot_ai": {"db": 1.0, "unit": 10.0, "max": 600.0, "far": true},
	# прицеливание и патрон в магазин — синтез (записи отвлекали)
	# поднять / опустить оружие: записи (gear/ads_, gear/ads_lower_), без них — синтез ads_in / ads_out
	"ads_raise": {"db": -14.0, "unit": 2.0, "max": 12.0},
	"ads_lower": {"db": -15.0, "unit": 2.0, "max": 12.0},
	"ads_in": {"db": -21.0, "unit": 2.0, "max": 8.0},
	"ads_out": {"db": -23.0, "unit": 2.0, "max": 8.0},
	"mag_round": {"db": -12.0, "unit": 2.0, "max": 10.0},
	# липучка подсумка: магазин достают из подсумка на броне (Player._plan_velcro)
	"pouch_velcro": {"db": -10.0, "unit": 2.5, "max": 14.0},
	"step": {"db": -16.0, "unit": 3.0, "max": 22.0},
	"step_ai": {"db": -14.0, "unit": 3.0, "max": 26.0},
	# шаги по поверхностям (Audio.step): occlude — за стеной глуше
	"step_stone": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true},
	"step_stone_run": {"db": -12.0, "unit": 3.0, "max": 34.0, "occlude": true},
	"step_dirt": {"db": -15.0, "unit": 3.0, "max": 28.0, "occlude": true},
	"step_dirt_run": {"db": -12.0, "unit": 3.0, "max": 34.0, "occlude": true},
	"step_asphalt_wet": WET_STEPS.sound,
	"step_snow": {"db": -16.0, "unit": 3.0, "max": 24.0, "occlude": true},
	"step_snow_run": {"db": -13.0, "unit": 3.0, "max": 30.0, "occlude": true},
	"step_metal": {"db": -17.0, "unit": 3.0, "max": 30.0, "occlude": true},
	"heartbeat": {"db": -4.0, "unit": 3.0, "max": 6.0},
	"thunder": {"db": 6.0, "unit": 60.0, "max": 400.0},
	"breaker": {"db": 2.0, "unit": 10.0, "max": 80.0},
	"heli": {"db": 10.0, "unit": 60.0, "max": 500.0},
	"supply_plane": SUPPLY_PLANE_SOUND,
	"engine": {"db": 2.0, "unit": 15.0, "max": 160.0},
	# мародёр роется в контейнере — слышно за стеной
	"rummage": {"db": -13.0, "unit": 3.0, "max": 22.0, "occlude": true},
	"door": {"db": -6.0, "unit": 4.0, "max": 30.0},
	"hit": {"db": -4.0, "unit": 5.0, "max": 30.0},
	"reload": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"impact_hard": {"db": -6.0, "unit": 5.0, "max": 40.0},
	"impact_metal": {"db": -5.0, "unit": 6.0, "max": 45.0},
	"impact_glass": {"db": -4.0, "unit": 6.0, "max": 45.0},
	# витрина осыпалась: звон и шорох осколков
	"glass_break": {"db": 1.0, "unit": 8.0, "max": 70.0},
	"impact_soft": {"db": -10.0, "unit": 4.0, "max": 30.0},
	"shot_rifle": {"db": 2.0, "unit": 12.0, "max": 900.0, "far": true},
	"shot_shotgun": {"db": 4.0, "unit": 12.0, "max": 450.0, "far": true},
	"shot_bolt": {"db": 5.0, "unit": 16.0, "max": 1300.0, "far": true},
	# гильза падает и катится (shell_drop): слышно рядом, за стеной глуше
	"shell_hard": {"db": -9.0, "unit": 3.0, "max": 28.0, "occlude": true},
	"shell_metal": {"db": -8.0, "unit": 3.0, "max": 30.0, "occlude": true},
	"shell_soft": {"db": -12.0, "unit": 3.0, "max": 20.0, "occlude": true},
	"shell_roll": {"db": -12.0, "unit": 3.0, "max": 22.0, "occlude": true},
	"mech_pistol": {"db": -8.0, "unit": 3.0, "max": 16.0},
	"mech_rifle": {"db": -7.0, "unit": 3.0, "max": 18.0},
	"step_run": {"db": -12.0, "unit": 3.0, "max": 28.0},
	"death": {"db": -2.0, "unit": 5.0, "max": 35.0},
	"fall": {"db": -6.0, "unit": 4.0, "max": 25.0},
	"reload_pistol": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"reload_rifle": {"db": -8.0, "unit": 3.0, "max": 15.0},
	"reload_shotgun": {"db": -6.0, "unit": 3.0, "max": 18.0},
	"bolt": {"db": -6.0, "unit": 3.0, "max": 18.0},
	"pin": {"db": -10.0, "unit": 2.0, "max": 10.0},
	"debris": {"db": -4.0, "unit": 6.0, "max": 40.0},
	"explosion": {"db": 8.0, "unit": 20.0, "max": 1200.0, "far": true},
}

const SONORA_AUDIO: Dictionary = {
 "shot": {"db": 2.0, "unit": 10.0, "max": 900.0, "far": true, "occlude": true},
 "weapon_action": {"db": -8.0, "unit": 3.0, "max": 24.0, "occlude": true},
 "world": {"db": -6.0, "unit": 4.0, "max": 40.0, "occlude": true},
 "ambient_db": -22.0,
 "max_db": 0.0,
 "unfiltered_hz": 20500.0
}

## Общий свет всех рейдовых карт — выбранный владельцем профиль «Проспекта».
## Индивидуальные поля света в данных старых карт оставлены только для истории.
const WORLD_LIGHT := {
 "sun_k": 0.81, "sun_angular_distance": 0.53, "sun_soft_min_elev": 20.0, "sun_hard_blur": 1.5,
 "ambient_k": 0.4, "ambient_k_night": 1.8,
 "ambient_k_day_rain": 0.8, "ambient_k_dusk_rain": 0.8, "ambient_k_night_rain": 3.2,
 "ambient_k_day_overcast": 0.8, "ambient_k_dusk_overcast": 0.8, "ambient_k_night_overcast": 2.6,
}
const WORLD_FOG := {"clear": {"begin": 50.0, "end": 900.0, "density": 0.55, "curve": 0.6, "sky": 0.1}}
## Свет по времени суток по схеме Road to Vostok (решение владельца 2026-11-05: их свет на все рейдовые карты; стенд
## сравнения — tools/rtv_look.tscn). Таблица по часам (цвет неба, солнца, луны, рассеянного, дымки; сила солнца,
## отражения неба, плотность дымки) — data/lighting/time_of_day.json, ведёт TodLight; наш час переводится в их по
## высоте солнца. on = false — прежний свет (WORLD_LIGHT, панорамы, расчётное небо). Привыкание глаза — наше (CameraLook).
const TOD_LIGHT := {
	"on": true,
	"table": "res://data/lighting/time_of_day.json",
	## их солнце светит, пока их часы между day_from и day_to (выше горизонта), иначе — луна напротив солнца
	"day_from": 600.0, "day_to": 1800.0,
	## сила луны (сила солнца и луны под тучами, даль тени, тональная кривая, дымка — ползунки стенда света,
	## LAB_RULES.atmosphere_tod)
	"moon_energy": 2.0,
	## плотность объёмной дымки = кривая fogDensity × туман погоды / fog_div
	"fog_div": 100.0,
	## погода (их World.gd): к чему идут тучи, ветер, туман и дождь
	"weather": {
		"clear": {"overcast": 0.0, "wind": 0.2, "fog": 1.0, "rain": 0.0},
		"heat": {"overcast": 0.0, "wind": 0.2, "fog": 1.0, "rain": 0.0},
		"overcast": {"overcast": 1.0, "wind": 1.0, "fog": 1.0, "rain": 0.0},
		"rain": {"overcast": 1.0, "wind": 0.2, "fog": 1.0, "rain": 1.0},
		"fog": {"overcast": 1.0, "wind": 1.0, "fog": 4.0, "rain": 0.0},
	},
	## облака неба — наши панорамы (sky.json: tod_clouds — кучевые на голубом, day_overcast), приведённые к средней яркости их облачного неба
	## (их картинки облаков в среднем 0,765 и 0,528 в sRGB; в шейдере — линейные 0,546 и 0,241)
	"clouds_clear": "tod_clouds", "clouds_overcast": "day_overcast",
	"clear_mean": 0.546, "overcast_mean": 0.241,
	## разброс яркости их облаков (от просвета до облака, линейно): ясно 0,165…0,931, пасмурно 0,104…0,447
	"clear_spread": 0.766, "overcast_spread": 0.343,
	## облака плывут: доля оборота панорамы за игровой час (небо обновляется раз в DAY_CYCLE.sky_sec)
	"clouds_drift": 0.03,
}


# --- Интерактивные стенды: нейтральные множители и допустимые пределы ---
## Подпись, исходное значение, минимум, максимум, шаг. По умолчанию поведение игры прежнее.
const LAB_RULES: Dictionary = {
	## свет по схеме Road to Vostok (TodLight): исходные числа — их; стенд «Свет и атмосфера» при этом свете
	"atmosphere_tod": {
		"sun": ["Солнце · сила ×", 1.0, 0.0, 4.0, 0.05],
		"moon": ["Луна · сила ×", 1.0, 0.0, 4.0, 0.05],
		"overcast_light": ["Солнце и луна под тучами · сила", 0.5, 0.0, 2.0, 0.05],
		"ambient": ["Рассеянный свет · сила ×", 1.0, 0.0, 4.0, 0.05],
		"sky_share": ["Рассеянный свет · доля от неба", 0.5, 0.0, 1.0, 0.05],
		"sky": ["Небо · яркость ×", 1.0, 0.1, 4.0, 0.05],
		"reflection": ["Небо · отражения и свет от неба ×", 1.0, 0.0, 4.0, 0.05],
		"clouds_bright": ["Облака · яркость ×", 1.0, 0.3, 2.0, 0.05],
		"clouds_contrast": ["Облака · контраст ×", 1.0, 0.3, 3.0, 0.05],
		"fog": ["Дымка · плотность ×", 1.0, 0.0, 6.0, 0.05],
		"fog_glow": ["Дымка · свечение", 0.2, 0.0, 2.0, 0.01],
		"fog_forward": ["Дымка · свет вперёд, к солнцу", 0.9, 0.0, 0.99, 0.01],
		"agx_white": ["Тональная кривая AgX · белая точка", 2.0, 1.0, 8.0, 0.1],
		"agx_contrast": ["Тональная кривая AgX · контраст", 1.5, 0.5, 2.5, 0.05],
		"saturation": ["Насыщенность", 1.0, 0.0, 2.0, 0.01],
		"shadow_m": ["Тень солнца · даль, м", 200.0, 50.0, 400.0, 10.0],
		"adapt_scale": ["Глаз · целевая экспозиция", 0.35, 0.05, 2.0, 0.01],
		"adapt_up": ["Глаз · осветление на улице до ×", 2.0, 1.0, 8.0, 0.1],
		"adapt_indoor": ["Глаз · осветление в помещении до ×", 2.5, 1.0, 12.0, 0.1],
		"sun_tint": ["Оттенок солнечного / лунного света", Color.WHITE],
		"fog_tint": ["Оттенок дымки", Color.WHITE],
	},
	"atmosphere": {
		"sun": ["Солнце / Луна · яркость ×", 1.0, 0.0, 4.0, 0.05],
		"ambient": ["Рассеянный свет · яркость ×", 1.0, 0.0, 4.0, 0.05],
		"sky": ["Яркость неба ×", 1.0, 0.1, 4.0, 0.05],
		"exposure": ["Экспозиция ×", 1.0, 0.1, 4.0, 0.05],
		"fog": ["Плотность тумана ×", 1.0, 0.0, 4.0, 0.05],
		"volume": ["Объёмная дымка ×", 1.0, 0.0, 4.0, 0.05],
		"sun_day": ["Солнце · день ×", 1.0, 0.0, 4.0, 0.05],
		"sun_dusk": ["Солнце · закат ×", 1.0, 0.0, 4.0, 0.05],
		"sun_night": ["Луна · ночь ×", 1.0, 0.0, 4.0, 0.05],
		"ambient_day": ["Рассеянный · день ×", 1.0, 0.0, 4.0, 0.05],
		"ambient_dusk": ["Рассеянный · закат ×", 1.0, 0.0, 4.0, 0.05],
		"ambient_night": ["Рассеянный · ночь ×", 1.0, 0.0, 4.0, 0.05],
		"ambient_overcast": ["Рассеянный · пасмурно ×", 1.0, 0.0, 4.0, 0.05],
		"ambient_rain": ["Рассеянный · дождь ×", 1.0, 0.0, 4.0, 0.05],
		"shadow_angle": ["Размер солнца · мягкость теней, °", 0.53, 0.0, 3.0, 0.01],
		"shadow_min_elev": ["Мягкие тени выше солнца, °", 20.0, 20.0, 80.0, 1.0],
		"shadow_blur": ["Размытие теней низкого солнца / Луны", 1.5, 0.1, 4.0, 0.1],
		"tonemap": ["Тональная кривая", 2.0, 0.0, 4.0, 1.0, ["Линейная", "Reinhard", "Filmic · Проспект", "ACES", "AgX"]],
		"contrast": ["Контраст", 1.0, 0.5, 1.5, 0.01],
		"saturation": ["Насыщенность", 0.9, 0.0, 2.0, 0.01],
		"ssao_intensity": ["Тени в углах · сила SSAO", 4.0, 0.0, 8.0, 0.1],
		"ssao_radius": ["Тени в углах · радиус, м", 2.5, 0.1, 6.0, 0.1],
		"ssao_power": ["Тени в углах · контраст SSAO", 2.0, 0.1, 6.0, 0.1],
		"gi_energy": ["Отражённый свет · энергия SDFGI ×", 1.0, 0.0, 3.0, 0.05],
		"fog_distance": ["Дальность начала / конца дымки ×", 1.0, 0.1, 3.0, 0.05],
		"fog_curve": ["Кривая дымки по расстоянию ×", 1.0, 0.1, 3.0, 0.05],
		"volume_density": ["Объёмная дымка · плотность", 0.0, 0.0, 0.01, 0.0001],
		"adapt_scale": ["Глаз · целевая экспозиция", 0.35, 0.05, 2.0, 0.01],
		"adapt_up": ["Глаз · осветление на улице до ×", 2.0, 1.0, 8.0, 0.1],
		"adapt_indoor": ["Глаз · осветление в помещении до ×", 2.5, 1.0, 12.0, 0.1],
		"sun_tint": ["Оттенок солнечного / лунного света", Color.WHITE],
		"fog_tint": ["Оттенок тумана", Color.WHITE],
	},
	"impact": {
		"debris_count": ["Крупные обломки · количество ×", 1.0, 0.0, 3.0, 0.1],
		"debris_size": ["Размер обломков ×", 1.0, 0.1, 3.0, 0.1],
		"bits_count": ["Мелкая крошка · количество ×", 1.0, 0.0, 3.0, 0.1],
		"spray_count": ["Веер материала · количество ×", 1.0, 0.0, 3.0, 0.1],
		"dust_count": ["Пыль / дым · количество ×", 1.0, 0.0, 3.0, 0.1],
		"dust_size": ["Размер облака пыли ×", 1.0, 0.1, 3.0, 0.1],
		"dust_life": ["Длительность облака пыли ×", 1.0, 0.1, 4.0, 0.1],
		"sparks_count": ["Искры · количество ×", 1.0, 0.0, 3.0, 0.1],
		"sparks_size": ["Толщина искр ×", 1.0, 0.1, 3.0, 0.1],
		"sparks_life": ["Длительность искр ×", 1.0, 0.1, 4.0, 0.1],
		"speed": ["Скорость разлёта ×", 1.0, 0.1, 3.0, 0.1],
		"life": ["Длительность обломков и веера ×", 1.0, 0.1, 4.0, 0.1],
		"decal_size": ["Размер следа попадания ×", 1.0, 0.1, 3.0, 0.1],
		"decal_life": ["След · секунд (0 — обычный лимит)", 0.0, 0.0, 180.0, 1.0],
	},
	"perception": {
		"view": ["Дальность зрения ×", 1.0, 0.1, 3.0, 0.05],
		"half_angle": ["Половина угла обзора · градусы", AI_VIEW_HALF_ANGLE_DEG, 5.0, 175.0, 1.0],
		"notice": ["Время обнаружения ×", 1.0, 0.1, 4.0, 0.05],
		"hearing": ["Дальность слуха ×", 1.0, 0.1, 3.0, 0.05],
		"memory": ["Время памяти о цели ×", 1.0, 0.1, 4.0, 0.1],
	},
	"enemy": {
		"clip_speed": ["Скорость просмотра клипа ×", 1.0, 0.1, 2.0, 0.05],
		"reload_speed": ["Темп перезарядки и её анимации ×", 1.0, 0.5, 2.0, 0.05],
		"death_push": ["Сила толчка при падении ×", 1.0, 0.0, 2.0, 0.05],
		"ragdoll_damp": ["Затухание движения тела ×", 1.0, 0.25, 3.0, 0.05],
		"ragdoll_joints": ["Свобода суставов тела ×", 1.0, 0.25, 1.5, 0.05],
		"shot_spread": ["Разброс огня ×", 1.0, 0.1, 3.0, 0.05],
		"burst_pause": ["Пауза между очередями ×", 1.0, 0.0, 3.0, 0.05],
		"recoil": ["Отдача в позе стрелка ×", 1.0, 0.0, 3.0, 0.05],
	},
	"motion": {
		"head": ["Голова · размах при шагах и беге ×", 1.0, 0.0, 2.5, 0.05],
		"jump": ["Камера · размах в прыжке и на приземлении ×", 1.0, 0.0, 2.5, 0.05],
		"weapon_speed": ["Оружие · скорость качания ×", 1.0, 0.25, 2.5, 0.05],
		"walk_angle": ["Оружие · направление на шаге, °", 0.0, -90.0, 90.0, 1.0],
		"run_angle": ["Оружие · направление на беге, °", 0.0, -90.0, 90.0, 1.0],
		"idle_amp": ["Оружие · размах дыхания стоя на месте ×", 1.0, 0.0, 3.0, 0.05],
	},
	"step_layers": {
		"glass_on": ["Битое стекло", 1.0, 0.0, 1.0, 1.0],
		"glass_db": ["Битое стекло · дБ", -10.0, -36.0, 0.0, 1.0],
		"glass_files": ["", []],
		"leaves_on": ["Листья", 1.0, 0.0, 1.0, 1.0],
		"leaves_db": ["Листья · дБ", -13.0, -36.0, 0.0, 1.0],
		"leaves_files": ["", []],
		"trash_on": ["Мусор", 1.0, 0.0, 1.0, 1.0],
		"trash_db": ["Мусор · дБ", -12.0, -36.0, 0.0, 1.0],
		"trash_files": ["", []],
	},
	"step_timing": {
		"walk_sec": ["Ходьба · секунды между шагами", STEP_WALK_SEC, 0.24, 1.20, 0.01],
		"run_sec": ["Бег · секунды между шагами", STEP_RUN_SEC, 0.20, 0.90, 0.01],
		"start_custom": ["Своя пауза после полной остановки", 0.0, 0.0, 1.0, 1.0],
		"start_sec": ["Пауза перед первым шагом, с", STEP_START_SEC, 0.0, 0.60, 0.01],
		"pan_pct": ["Разнос левой и правой стопы, %", 100.0, 0.0, 150.0, 5.0],
	},
}


func lab_rules(domain: String) -> Dictionary:
	return LAB_RULES.get(domain.get_slice(":", 0), {})


func lab_number(domain: String, key: String) -> float:
	return float(LabTuning.value(domain, key))


## Нейтральная поправка применяется к заново рассчитанному свету, поэтому не накапливается.
func lab_atmosphere(sun: DirectionalLight3D, environment: Environment) -> void:
	if sun:
		sun.light_energy *= lab_number("atmosphere", "sun")
		sun.light_color *= LabTuning.value("atmosphere", "sun_tint") as Color
	if environment:
		environment.ambient_light_energy *= lab_number("atmosphere", "ambient")
		environment.background_energy_multiplier *= lab_number("atmosphere", "sky")
		environment.tonemap_exposure *= lab_number("atmosphere", "exposure")
		environment.fog_light_color *= LabTuning.value("atmosphere", "fog_tint") as Color
		# свет по схеме Road to Vostok (TodLight) ставит тональную кривую, дымку и эффекты сам — стенд света их не трогает
		if environment.has_meta("shared_lighting") and not environment.has_meta("tod"):
			environment.tonemap_mode = int(lab_number("atmosphere", "tonemap"))
			environment.adjustment_contrast = lab_number("atmosphere", "contrast")
			environment.adjustment_saturation = lab_number("atmosphere", "saturation")
			environment.ssao_intensity = lab_number("atmosphere", "ssao_intensity")
			environment.ssao_radius = lab_number("atmosphere", "ssao_radius")
			environment.ssao_power = lab_number("atmosphere", "ssao_power")
			environment.sdfgi_energy = lab_number("atmosphere", "gi_energy")
			environment.volumetric_fog_density = lab_number("atmosphere", "volume_density")
			environment.volumetric_fog_enabled = environment.volumetric_fog_density > 0.000001 and Settings.quality != "low"
		environment.volumetric_fog_density *= lab_number("atmosphere", "volume")


func lab_impact(kind: String) -> Dictionary:
	var spec: Dictionary = (IMPACT_SURFACES.get(kind, IMPACT_SURFACES.concrete) as Dictionary).duplicate(true)
	var domain: String = "impact:" + kind
	for layer: String in ["debris", "bits", "spray", "dust", "sparks"]:
		if not spec.has(layer):
			continue
		var config: Dictionary = spec[layer]
		var amount: float = lab_number(domain, layer + "_count")
		if is_zero_approx(amount):
			spec.erase(layer)
			continue
		if config.count is Vector2i:
			var count: Vector2i = config.count
			config.count = Vector2i(maxi(1, roundi(count.x * amount)), maxi(1, roundi(count.y * amount)))
		else:
			config.count = maxi(1, roundi(float(config.count) * amount))
		if config.has("speed"):
			config.speed = (config.speed as Vector2) * lab_number(domain, "speed")
		if config.has("life"):
			config.life = (config.life as Vector2) * lab_number(domain, "dust_life" if layer == "dust" else "life")
		if config.has("size") and layer in ["debris", "dust"]:
			config.size = (config.size as Vector2) * lab_number(domain, layer + "_size")
	return spec


func lab_sparks(kind: String) -> Dictionary:
	var config: Dictionary = IMPACT_SPARKS.duplicate(true)
	config.width = (config.width as Vector2) * lab_number("impact:" + kind, "sparks_size")
	config.life = (config.life as Vector2) * lab_number("impact:" + kind, "sparks_life")
	config.speed = (config.speed as Vector2) * lab_number("impact:" + kind, "speed")
	return config
