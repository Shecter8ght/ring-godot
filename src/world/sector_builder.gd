@tool
class_name SectorBuilder
extends RefCounted
## Собирает сектор кольца из данных (data/sectors/*.json) в узлы: полы, стены, проёмы, свет.
## Координаты — полярные от центра кольца: угол a в градусах (от +X к +Z), радиус r в метрах.
## Помещение — кольцевой сектор [a0,a1]×[r0,r1]; стены строятся по границам помещений
## один раз на линию, проёмы вырезают их. Ничего не кладётся руками — только данные.
## Постройки вокруг (паркинг, техкомплекс…) — отдельные сцены в сцене уровня, их двигают руками.
##
## Полоса — прямое помещение вдоль оси (главная аллея от входа к атриуму): поля "axis" (угол оси,
## град), "t" [t0,t1] — поперёк оси, м (плюс — в сторону роста угла), "r" [r0,r1] — пояс радиусов,
## концы полосы — дуги. Полоса главнее кольцевых помещений: где она лежит, их нет (пол, стены,
## пропсы обрезаются). Кольцевое помещение, которое полоса задевает, она режет на всю его глубину
## по радиусу — пояса радиусов полос совпадают с поясами кольца. Стены вдоль полосы — линии
## "along" (параметр — s, м вдоль оси от центра), проёмы в них: {"wall":"along","axis","t","s":[..]}.
##
## Блокаут ("greybox": true в JSON): стены без текстур и декора, толщина — по классу конструкции
## (фасад / противопожарная / несущая / перегородка, числа в блоке "walls", нормы —
## docs/building_standards.md). Скрипт @tool: в редакторе строит превью без дверей и пропсов.

## Длина сегмента дуги, м: чем меньше, тем круглее стены и полы.
const SEG_LEN := 1.0
## Слой отрисовки потолков, купола и светильников: видны только от первого лица (камера
## изометрии его не рисует). Тени они отбрасывают в обоих видах — свет одинаковый.
const CEILING_LAYER := 1 << 19
## Потолочный свет по типу помещения: [цвет, яркость ×]. "" — остальное.
const LAMP_LOOK := {
	"retail": [Color(0.96, 0.93, 0.86), 1.0],
	"gallery": [Color(0.9, 0.93, 0.92), 1.0],
	"corridor": [Color(0.84, 0.92, 0.95), 0.82],
	"office": [Color(1.0, 0.9, 0.78), 0.9],
	"security": [Color(0.86, 0.9, 1.0), 0.8],
	"storage": [Color(0.8, 0.93, 0.9), 0.68],
	"utility": [Color(0.76, 0.95, 0.82), 0.58],
	"": [Color(0.82, 0.92, 0.88), 0.9],
}
## Панель светильника: свечение = цвет экземпляра (его пишет и RaidAtmosphere) × яркость.
const LAMP_SHADER := """
shader_type spatial;
uniform float energy = 3.2;
void fragment() {
	ALBEDO = vec3(0.92);
	ROUGHNESS = 0.4;
	EMISSION = COLOR.rgb * energy;
}
"""
## Углы линий стен хранятся приведёнными к [-180, 180): у полного кольца (ТЦ Ø200) помещения
## по обе стороны «шва» ±180 — одна и та же радиальная линия, а не две.
## Сдвиг от линии стены при поиске помещений по сторонам, м / град.
const EPS_R := 0.05
const EPS_A := 0.05
## Радиальная стена ближе этого к границе сектора — противопожарная (между пожарными отсеками), град.
const FIRE_TOL_DEG := 2.0
## Склейка пропсов: клетка, м, и дальность, дальше которой клетка не рисуется, м (изометрия видит
## ~80 м от камеры; в прицеле дальше всё равно стены и дымка).
const PROP_BATCH_CELL := 24.0
const PROP_VIS_END := 110.0
## Колонны каркаса (блок "columns" в JSON) — только в залах этих типов, не ближе этого к проёму, м,
## и не ближе COLUMN_CLEAR к стене (иначе колонна встала бы в стену или в дверь).
const COLUMN_ROOMS := ["retail", "storage"]
const COLUMN_DOOR_GAP := 2.5
const COLUMN_CLEAR := 0.9
## Серые полы блокаута по текстурным (см. SectorMaterials.GREYBOX).
const GREYBOX_FLOOR := {
	"large_floor_tiles_02": "gbf_tile", "worn_tile_floor": "gbf_tile",
	"concrete_floor_worn_001": "gbf_concrete", "asphalt_02": "gbf_asphalt",
}
## Полы, которые и в блокауте остаются с текстурой (улица — ради погоды).
const OUTDOOR_TEXTURED := ["asphalt_02"]
## Уличные помещения (площадь, дворы, парковка, проезд) — пол с текстурой и в блокауте: на них
## стоят модели (машины), серая сетка под ними выглядит чужой.
const OUTDOOR_ROOMS := ["yard", "parking"]
## Пол закрытой части кольца по поясам (ключи ring.zones).
const ZONE_FLOOR := {
	"atr": "large_floor_tiles_02", "gal": "large_floor_tiles_02", "inn": "worn_tile_floor", "st": "large_floor_tiles_02",
	"out": "worn_tile_floor", "back": "concrete_floor_worn_001", "svc": "concrete_floor_worn_001",
}

var _def: Dictionary
var _rooms: Array = []
var _openings: Array = []
var _wall_h: float = 7.0
var _wall_t: float = 0.3
var _fence_h: float = 2.2
var _barrier_h: float = 2.6
## SurfaceTool на материал — весь сектор одного материала рисуется одним мешем.
var _walls: Dictionary = {}
var _floors: Dictionary = {}
## Перекрытия над помещениями (материал -> SurfaceTool), на высоте стен.
var _ceilings: Dictionary = {}
## Светильники на потолке: [точка, помещение] — корпуса ставит _emit_ceilings.
var _lamps: Array = []
## Цвет панели каждого светильника (как у его огня, с яркостью).
var _lamp_colors: Array[Color] = []
## Стекло — отдельным мешем: без теней и с прозрачностью.
var _glass: Dictionary = {}
## Витринные панели (GlassPanes): каждая отдельно — простреливается и разбивается.
var _panes: Array = []
## Где уже стоит пилястра/колонна — чтобы на стыках стен не было двойных.
var _posts: Dictionary = {}
var _doors: Array[Door] = []
var _labels: Array[Label3D] = []
## Архитектурные размеры (блок "arch" в JSON поверх ARCH_DEFAULT, м).
var _arch: Dictionary = {}
## Блокаут: серые классы стен вместо текстур, без декора (цоколь, карниз, пилястры, баннеры).
var _greybox: bool = false
## Толщина по классу стены (блок "walls"); чего нет — _base_t.
var _thick: Dictionary = {}
var _base_t: float = 0.3
var _ring: Dictionary = {}
var _fire_angles: Array[float] = []
## Превью в редакторе: без дверей-сцен и пропсов (их скрипты работают только в игре).
var _preview: bool = false
## Ключ помещения по одну из сторон текущего отрезка стены — его дверь запирается (_doorway).
var _cur_key: String = ""
## Прямоугольники мировых XZ, где пропсов не ставить (узлы сцены группы "prop_keepout").
var keepouts: Array[Rect2] = []
## Вырезы в земле (узлы группы "ground_holes", их hole_rect): {center: Vector2 (мир XZ),
## half: Vector2 (половины вдоль осей X и Z узла), yaw} — асфальт участка там не кладётся.
var holes: Array = []

const DOOR_SCENE := preload("res://scenes/props/door.tscn")
const LOOT_SCENE := preload("res://scenes/world/loot_container.tscn")
const LOOSE_LOOT_SCENE := preload("res://scenes/world/loose_loot.tscn")
const ARCH_DEFAULT := {
	"plinth_h": 0.4, "cornice_h": 0.35, "pilaster_w": 0.5, "pilaster_spacing": 6.0, "column_spacing": 6.0,
	"storefront_h": 3.6, "door_h": 2.2, "shutter_h": 3.2, "gate_h": 4.5,
	"entrance_w": 3.2, "pane_w": 1.6, "broken_pane_pct": 22, "sign_h": 0.9,
	# роллета, поднятая наполовину (проём "half"): просвет под полотном — пролезть только лёжа
	"half_gap": 0.8,
	# колонна блокаута и там, где проём «open» делят границы соседних помещений (посреди проёма);
	# false — колонны только по краям проёма и по шагу сетки (узкие проходы не перегораживаются)
	"open_split_columns": true,
	# витрина, которую делит граница соседних помещений, строится кусками — у каждого свой вход и
	# вывеска; false — вход и вывеска одни, посередине всей витрины
	"storefront_split_entrances": true,
}


## Открыто всё кольцо (поле "angle" охватывает 360°) — у дуг есть отрезок через шов ±180.
func _ring_full() -> bool:
	var ang: Array = _def.get("angle", [0.0, 0.0])
	return not _ring.is_empty() and float(ang[1]) - float(ang[0]) >= 359.9


static func polar(a_deg: float, r: float) -> Vector3:
	var a := deg_to_rad(a_deg)
	return Vector3(r * cos(a), 0.0, r * sin(a))


# ---------------------------------------------------------------- форма помещения

static func is_strip(room: Dictionary) -> bool:
	return room.has("axis")


## Точка полосы: s — вдоль оси от центра кольца, t — поперёк.
static func strip_point(axis_deg: float, s: float, t: float) -> Vector3:
	return polar(axis_deg, s) + polar(axis_deg + 90.0, t)


## Угол, приведённый к [-180, 180) — ключ радиальной линии и точки разбиения дуг.
static func _wrap(a: float) -> float:
	return wrapf(a, -180.0, 180.0)


## Угол a внутри [a0, a1] с учётом перехода через ±180.
static func angle_in(a: float, a0: float, a1: float, eps: float = 1e-6) -> bool:
	var x := fposmod(a - a0 + eps, 360.0) - eps
	return x <= a1 - a0 + eps


## Точка внутри собственной формы помещения (без учёта того, что его режут полосы).
static func in_shape(room: Dictionary, p: Vector3, eps: float = 1e-6) -> bool:
	if room.has("rect"):
		var rect: Array = room.rect
		return p.x >= float(rect[0]) - eps and p.x <= float(rect[2]) + eps and p.z >= float(rect[1]) - eps and p.z <= float(rect[3]) + eps
	var r := Vector2(p.x, p.z).length()
	if r < float(room.r[0]) - eps or r > float(room.r[1]) + eps:
		return false
	if is_strip(room):
		var ax := float(room.axis)
		var d := polar(ax, 1.0)
		var t := p.dot(polar(ax + 90.0, 1.0))
		return p.dot(d) > 0.0 and t >= float(room.t[0]) - eps and t <= float(room.t[1]) + eps
	return angle_in(rad_to_deg(atan2(p.z, p.x)), float(room.a[0]), float(room.a[1]), eps)


## Чьё место в точке: полосы главнее кольцевых помещений. Пусто — вне сектора.
static func owner_of(rooms: Array, p: Vector3) -> Dictionary:
	for room in rooms:
		if is_strip(room) and in_shape(room, p):
			return room
	for room in rooms:
		if not is_strip(room) and in_shape(room, p):
			return room
	return {}


## Случайная точка внутри помещения с отступом pad от его границ (и от полос, что его режут).
## Vector3.INF — не нашлось (помещение почти целиком под полосой).
static func random_point(room: Dictionary, rooms: Array, rng: RandomNumberGenerator, pad: float) -> Vector3:
	var id := String(room.get("id", ""))
	if room.has("rect"):
		var rect: Array = room.rect
		if float(rect[2]) - float(rect[0]) <= pad * 2.0 or float(rect[3]) - float(rect[1]) <= pad * 2.0:
			return Vector3.INF
		return Vector3(rng.randf_range(float(rect[0]) + pad, float(rect[2]) - pad), float(room.get("y", 0.0)), rng.randf_range(float(rect[1]) + pad, float(rect[3]) - pad))
	for i in range(16):
		var p: Vector3
		var r := rng.randf_range(float(room.r[0]) + pad, float(room.r[1]) - pad)
		if is_strip(room):
			var t := rng.randf_range(float(room.t[0]) + pad, float(room.t[1]) - pad)
			if absf(t) >= r:
				continue
			p = strip_point(float(room.axis), sqrt(r * r - t * t), t)
		else:
			var da := rad_to_deg(pad / maxf(r, 1.0))
			p = polar(rng.randf_range(float(room.a[0]) + da, float(room.a[1]) - da), r)
		var ok := true
		for off in [Vector3(pad, 0, 0), Vector3(-pad, 0, 0), Vector3(0, 0, pad), Vector3(0, 0, -pad), Vector3.ZERO]:
			if String(owner_of(rooms, p + off).get("id", "")) != id:
				ok = false
				break
		if ok:
			return p
	return Vector3.INF


static func load_def(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var parsed: Variant = JSON.parse_string(text)
	if parsed == null or not (parsed is Dictionary):
		push_error("SectorBuilder: не удалось прочитать " + path)
		return {}
	return parsed


## Строит сектор и возвращает корневой узел. В meta корня: rooms (массив словарей), spawn (Vector3).
func build(path: String) -> Node3D:
	_def = load_def(path)
	var root := Node3D.new()
	root.name = String(_def.get("id", "sector"))
	if _def.is_empty():
		return root
	# Городская планировка хранится в районных сценах; данные нужны общим системам рейда.
	if String(_def.get("layout", "")) == "cartesian_scene":
		root.set_meta("rooms", _def.get("rooms", []))
		root.set_meta("ring", {})
		var xyz: Array = _def.get("spawn", [0, 0, 0])
		root.set_meta("spawn", Vector3(float(xyz[0]), float(xyz[1]), float(xyz[2])))
		root.set_meta("camera_yaw", float(_def.get("camera_yaw", 0.0)))
		return root
	_rooms = _def.get("rooms", [])
	_openings = _def.get("openings", [])
	var walls: Dictionary = _def.get("walls", {})
	_wall_h = float(walls.get("height", 7.0))
	_wall_t = float(walls.get("thickness", 0.3))
	_fence_h = float(walls.get("fence_height", 2.2))
	_barrier_h = float(walls.get("barrier_height", 2.6))
	_base_t = _wall_t
	_thick = walls
	_greybox = bool(_def.get("greybox", false))
	_ring = _def.get("ring", {})
	_preview = Engine.is_editor_hint()
	for sec in _def.get("sectors", []):
		for a in sec.a:
			if not float(a) in _fire_angles:
				_fire_angles.append(float(a))
	_arch = ARCH_DEFAULT.duplicate()
	_arch.merge(_def.get("arch", {}), true)

	_build_floors()
	_build_walls()
	_build_columns()
	_build_surroundings()
	if not _greybox:
		_build_overhead()
	_emit_meshes(root)
	_build_floor_collider(root)
	_build_lights(root)
	_build_beacons(root)
	_emit_ceilings(root)
	_build_markers(root)
	if not _preview:
		_build_props(root)

	root.set_meta("rooms", _rooms)
	root.set_meta("ring", _ring)
	root.set_meta("camera_yaw", float(_def.get("camera_yaw", -45.0)))
	var sp: Dictionary = _def.get("spawn", {})
	root.set_meta("spawn", polar(float(sp.get("a", 0.0)), float(sp.get("r", 100.0))))
	return root


# ---------------------------------------------------------------- геометрия

func _st(store: Dictionary, mat_id: String) -> SurfaceTool:
	if not store.has(mat_id):
		var st := SurfaceTool.new()
		st.begin(Mesh.PRIMITIVE_TRIANGLES)
		store[mat_id] = st
	return store[mat_id]


func _build_floors() -> void:
	for room in _rooms:
		var st := _st(_floors, _floor_mat(String(room.get("floor", "concrete_floor_worn_001")), String(room.get("type", "")) in OUTDOOR_ROOMS))
		var ceil: SurfaceTool = _st(_ceilings, _gb("painted_plaster_wall", "gb_slab")) if _has_ceiling(room) else null
		if is_strip(room):
			_strip_floor(st, room, ceil)
			continue
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		# полосы, что режут это помещение (пояс радиусов пересекается)
		var cuts: Array = []
		for s in _rooms:
			if is_strip(s) and float(s.r[0]) < r1 - 1e-3 and float(s.r[1]) > r0 + 1e-3:
				cuts.append(s)
		var n := maxi(1, int(ceil(deg_to_rad(a1 - a0) * r1 / SEG_LEN)))
		for i in range(n):
			var aa := lerpf(a0, a1, float(i) / n)
			var ab := lerpf(a0, a1, float(i + 1) / n)
			var pieces: Array[PackedVector3Array] = [PackedVector3Array([polar(aa, r0), polar(ab, r0), polar(ab, r1), polar(aa, r1)])]
			for s in cuts:
				pieces = _cut_strip(pieces, s)
			for poly in pieces:
				_poly(st, poly)
				if ceil:
					_ceiling_poly(ceil, poly)


## Потолок — над всем, что под крышей: не двор, не парковка, не атриум (над ним купол).
func _has_ceiling(room: Dictionary) -> bool:
	return not bool(room.get("outdoor", false)) and String(room.get("type", "")) != "atrium"


## Потолок: тот же многоугольник пола на высоте стен, лицом вниз.
func _ceiling_poly(st: SurfaceTool, poly: PackedVector3Array) -> void:
	for i in range(1, poly.size() - 1):
		var a := poly[0]
		var b := poly[i]
		var c := poly[i + 1]
		if (c - a).cross(b - a).y < 0.0:
			var tmp := b
			b = c
			c = tmp
		for p in [a, c, b]:
			st.set_normal(Vector3.DOWN)
			st.set_uv(_uv_xz(p))
			st.add_vertex(p + Vector3.UP * _wall_h)


## Пол полосы: столбцы по 1 м поперёк оси, концы — по дугам r0 и r1.
func _strip_floor(st: SurfaceTool, room: Dictionary, ceil: SurfaceTool = null) -> void:
	var ax := float(room.axis)
	var t0 := float(room.t[0])
	var t1 := float(room.t[1])
	var r0 := float(room.r[0])
	var r1 := float(room.r[1])
	var n := maxi(1, int(ceil((t1 - t0) / SEG_LEN)))
	for i in range(n):
		var ta := lerpf(t0, t1, float(i) / n)
		var tb := lerpf(t0, t1, float(i + 1) / n)
		var sa0 := sqrt(maxf(r0 * r0 - ta * ta, 0.0))
		var sb0 := sqrt(maxf(r0 * r0 - tb * tb, 0.0))
		var sa1 := sqrt(maxf(r1 * r1 - ta * ta, 0.0))
		var sb1 := sqrt(maxf(r1 * r1 - tb * tb, 0.0))
		var quad := PackedVector3Array([strip_point(ax, sa0, ta), strip_point(ax, sb0, tb), strip_point(ax, sb1, tb), strip_point(ax, sa1, ta)])
		_poly(st, quad)
		if ceil:
			_ceiling_poly(ceil, quad)


## Вычитает из выпуклых кусков пола полосу (её поперечный пояс t0..t1 по эту сторону центра).
func _cut_strip(pieces: Array[PackedVector3Array], strip: Dictionary) -> Array[PackedVector3Array]:
	var ax := float(strip.axis)
	var d := polar(ax, 1.0)
	var pn := polar(ax + 90.0, 1.0)
	var out: Array[PackedVector3Array] = []
	for poly in pieces:
		var c := Vector3.ZERO
		for p in poly:
			c += p
		c /= float(poly.size())
		if c.dot(d) <= 1.0:
			out.append(poly)
			continue
		for part in [_clip_half(poly, -pn, -float(strip.t[0])), _clip_half(poly, pn, float(strip.t[1]))]:
			if part.size() >= 3:
				out.append(part)
	return out


## Часть выпуклого многоугольника, где p·n ≥ d (Сазерленд — Ходжмен по одной прямой).
static func _clip_half(poly: PackedVector3Array, n: Vector3, d: float) -> PackedVector3Array:
	var out := PackedVector3Array()
	var m := poly.size()
	for i in range(m):
		var a := poly[i]
		var b := poly[(i + 1) % m]
		var da := a.dot(n) - d
		var db := b.dot(n) - d
		if da >= 0.0:
			out.append(a)
		if (da >= 0.0) != (db >= 0.0):
			out.append(a.lerp(b, da / (da - db)))
	return out


## Выпуклый многоугольник пола веером; обход выправляется так, чтобы лицевая смотрела вверх.
func _poly(st: SurfaceTool, poly: PackedVector3Array) -> void:
	for i in range(1, poly.size() - 1):
		var a := poly[0]
		var b := poly[i]
		var c := poly[i + 1]
		if (c - a).cross(b - a).y > 0.0:
			var tmp := b
			b = c
			c = tmp
		for p in [a, c, b]:
			st.set_normal(Vector3.UP)
			st.set_uv(_uv_xz(p))
			st.add_vertex(p)


func _uv_xz(p: Vector3) -> Vector2:
	return Vector2(p.x, p.z)


## Четырёхугольник против часовой (если смотреть вдоль -normal).
func _quad(st: SurfaceTool, a: Vector3, b: Vector3, c: Vector3, d: Vector3, n: Vector3, ua: Vector2, ub: Vector2, uc: Vector2, ud: Vector2) -> void:
	st.set_normal(n)
	st.set_uv(ua)
	st.add_vertex(a)
	st.set_uv(uc)
	st.add_vertex(c)
	st.set_uv(ub)
	st.add_vertex(b)
	st.set_normal(n)
	st.set_uv(ua)
	st.add_vertex(a)
	st.set_uv(ud)
	st.add_vertex(d)
	st.set_uv(uc)
	st.add_vertex(c)


## Стена-полоса по ломаной points толщиной t, от высоты y0 до y0+h. UV: u — длина вдоль, v — высота (метры).
func _wall_strip(st: SurfaceTool, points: PackedVector3Array, t: float, h: float, y0: float = 0.0) -> void:
	var u := 0.0
	var base := Vector3.UP * y0
	for i in range(points.size() - 1):
		var p0 := points[i] + base
		var p1 := points[i + 1] + base
		var d := (p1 - p0)
		var len := d.length()
		if len < 0.001:
			continue
		d /= len
		var n := Vector3(-d.z, 0.0, d.x)
		var o := n * (t * 0.5)
		var up := Vector3.UP * h
		# левая грань (по нормали n)
		_quad(st, p0 + o, p1 + o, p1 + o + up, p0 + o + up, n, Vector2(u, y0), Vector2(u + len, y0), Vector2(u + len, y0 + h), Vector2(u, y0 + h))
		# правая грань
		_quad(st, p1 - o, p0 - o, p0 - o + up, p1 - o + up, -n, Vector2(u + len, y0), Vector2(u, y0), Vector2(u, y0 + h), Vector2(u + len, y0 + h))
		# верх
		_quad(st, p0 - o + up, p1 - o + up, p1 + o + up, p0 + o + up, Vector3.UP, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, t), Vector2(u, t))
		# низ (виден у карнизов и ригелей снизу)
		if y0 > 0.001:
			_quad(st, p0 + o, p1 + o, p1 - o, p0 - o, Vector3.DOWN, Vector2(u, 0), Vector2(u + len, 0), Vector2(u + len, t), Vector2(u, t))
		u += len
	# торцы
	if points.size() >= 2:
		_cap(st, points[0] + base, points[1] + base, t, h, true)
		_cap(st, points[points.size() - 1] + base, points[points.size() - 2] + base, t, h, false)


func _cap(st: SurfaceTool, p: Vector3, towards: Vector3, t: float, h: float, start: bool) -> void:
	var d := (towards - p).normalized()
	var n := Vector3(-d.z, 0.0, d.x)
	var o := n * (t * 0.5)
	var up := Vector3.UP * h
	var out := -d
	if start:
		_quad(st, p - o, p + o, p + o + up, p - o + up, out, Vector2(0, 0), Vector2(t, 0), Vector2(t, h), Vector2(0, h))
	else:
		_quad(st, p + o, p - o, p - o + up, p + o + up, out, Vector2(0, 0), Vector2(t, 0), Vector2(t, h), Vector2(0, h))


## Столб/пилястра: короткая стена длиной w поперёк линии в точке p, вдоль направления dir.
func _post(st: SurfaceTool, p: Vector3, dir: Vector3, w: float, t: float, h: float, y0: float = 0.0) -> void:
	var half := dir.normalized() * (w * 0.5)
	_wall_strip(st, PackedVector3Array([p - half, p + half]), t, h, y0)


# ---------------------------------------------------------------- линии стен
# Линия — дуга (kind "arc", fixed = r, параметр = угол), радиус (kind "radial", fixed = a, параметр = r)
# или прямая вдоль оси полосы (kind "along", axis, fixed = t, параметр = s).

func _line_point(line: Dictionary, p: float) -> Vector3:
	match String(line.kind):
		"arc":
			return polar(p, float(line.fixed))
		"along":
			return strip_point(float(line.axis), p, float(line.fixed))
	return polar(float(line.fixed), p)


## Длина отрезка линии в метрах между параметрами p0 и p1.
func _line_len(line: Dictionary, p0: float, p1: float) -> float:
	if String(line.kind) == "arc":
		return deg_to_rad(absf(p1 - p0)) * float(line.fixed)
	return absf(p1 - p0)


## Параметр, отстоящий от p0 на dist метров в сторону роста параметра.
func _line_advance(line: Dictionary, p0: float, dist: float) -> float:
	if String(line.kind) == "arc":
		return p0 + rad_to_deg(dist / float(line.fixed))
	return p0 + dist


func _line_points(line: Dictionary, p0: float, p1: float) -> PackedVector3Array:
	if String(line.kind) == "arc":
		return _arc_points(float(line.fixed), p0, p1)
	return PackedVector3Array([_line_point(line, p0), _line_point(line, p1)])


func _line_dir(line: Dictionary, p: float) -> Vector3:
	var eps := 0.01
	return (_line_point(line, p + eps) - _line_point(line, p - eps)).normalized()


func _arc_points(r: float, a0: float, a1: float) -> PackedVector3Array:
	var pts := PackedVector3Array()
	var n := maxi(1, int(ceil(deg_to_rad(absf(a1 - a0)) * r / SEG_LEN)))
	for i in range(n + 1):
		pts.append(polar(lerpf(a0, a1, float(i) / n), r))
	return pts


# ---------------------------------------------------------------- стены по линиям

func _room_at(a: float, r: float) -> Dictionary:
	return owner_of(_rooms, polar(a, r))


func _opening_at(kind_wall: String, fixed: float, along: float, axis: float = 0.0) -> Dictionary:
	for op in _openings:
		if String(op.wall) != kind_wall:
			continue
		match kind_wall:
			"arc":
				# дуга проёма может переходить через ±180
				if absf(float(op.r) - fixed) <= 0.01 and angle_in(along, float(op.a[0]), float(op.a[1])):
					return op
			"along":
				if absf(float(op.axis) - axis) > 0.01 or absf(float(op.t) - fixed) > 0.01:
					continue
				if along >= float(op.s[0]) - 1e-6 and along <= float(op.s[1]) + 1e-6:
					return op
			_:
				if absf(wrapf(float(op.a) - fixed, -180.0, 180.0)) > 0.01:
					continue
				if along >= float(op.r[0]) - 1e-6 and along <= float(op.r[1]) + 1e-6:
					return op
	return {}


func _build_walls() -> void:
	# Линии: дуги по радиусу и радиальные по углу; на каждой — точки разбиения.
	var arcs: Dictionary = {}
	var rads: Dictionary = {}
	var alongs: Dictionary = {}
	for room in _rooms:
		if is_strip(room):
			continue
		for r in [float(room.r[0]), float(room.r[1])]:
			_add_breaks(arcs, r, [_wrap(float(room.a[0])), _wrap(float(room.a[1]))])
		for a in [float(room.a[0]), float(room.a[1])]:
			_add_breaks(rads, _wrap(a), [float(room.r[0]), float(room.r[1])])
	# полосы: торцы — дуги, бока — прямые вдоль оси
	for room in _rooms:
		if not is_strip(room):
			continue
		var ax := float(room.axis)
		for r in [float(room.r[0]), float(room.r[1])]:
			_add_breaks(arcs, r, [_wrap(ax + rad_to_deg(asin(float(room.t[0]) / r))), _wrap(ax + rad_to_deg(asin(float(room.t[1]) / r)))])
		for t in [float(room.t[0]), float(room.t[1])]:
			var key := "%.2f@%.2f" % [t, ax]
			if not alongs.has(key):
				alongs[key] = {"fixed": t, "axis": ax, "breaks": []}
			_add_breaks(alongs, t, [_strip_s(float(room.r[0]), t), _strip_s(float(room.r[1]), t)], key)
	for op in _openings:
		match String(op.wall):
			"arc":
				_add_breaks(arcs, float(op.r), [_wrap(float(op.a[0])), _wrap(float(op.a[1]))])
			"along":
				var key := "%.2f@%.2f" % [float(op.t), float(op.axis)]
				if alongs.has(key):
					_add_breaks(alongs, float(op.t), [float(op.s[0]), float(op.s[1])], key)
			_:
				_add_breaks(rads, _wrap(float(op.a)), [float(op.r[0]), float(op.r[1])])
	# пересечения прямых полос с дугами и радиусами — чтобы по обе стороны каждого отрезка
	# было ровно по одному помещению
	for key in alongs:
		var ln: Dictionary = alongs[key]
		var t: float = ln.fixed
		var ax: float = ln.axis
		var s_min: float = (ln.breaks as Array).min()
		var s_max: float = (ln.breaks as Array).max()
		for ak in arcs:
			var r: float = arcs[ak].fixed
			if absf(t) < r:
				var s := _strip_s(r, t)
				if s > s_min and s < s_max:
					_add_breaks(alongs, t, [s], key)
				# точка разбиения только внутри уже существующей дуги — иначе она бы её удлинила
				var ab := _wrap(ax + rad_to_deg(asin(t / r)))
				if ab > (arcs[ak].breaks as Array).min() and ab < (arcs[ak].breaks as Array).max():
					_add_breaks(arcs, r, [ab])
				elif _ring_full():
					_add_breaks(arcs, r, [ab])
		for rk in rads:
			var a: float = rads[rk].fixed
			var da := deg_to_rad(wrapf(a - ax, -180.0, 180.0))
			if absf(sin(da)) < 1e-4 or signf(sin(da)) != signf(t) or cos(da) <= 0.0:
				continue
			var rr := t / sin(da)
			var s2 := rr * cos(da)
			if s2 > s_min and s2 < s_max:
				_add_breaks(alongs, t, [s2], key)
			if rr > (rads[rk].breaks as Array).min() and rr < (rads[rk].breaks as Array).max():
				_add_breaks(rads, a, [rr])

	for key in arcs:
		var line := {"kind": "arc", "fixed": arcs[key].fixed}
		var r: float = arcs[key].fixed
		var br: Array = arcs[key].breaks
		br.sort()
		if _ring_full() and br.size() >= 1:
			br.append(float(br[0]) + 360.0)
		for i in range(br.size() - 1):
			var a0: float = br[i]
			var a1: float = br[i + 1]
			if a1 - a0 < 1e-4:
				continue
			var mid := (a0 + a1) * 0.5
			_emit_wall_segment(line, a0, a1, _room_at(mid, r - EPS_R), _room_at(mid, r + EPS_R), _opening_at("arc", r, mid))
	for key in rads:
		var line := {"kind": "radial", "fixed": rads[key].fixed}
		var a: float = rads[key].fixed
		var br: Array = rads[key].breaks
		br.sort()
		for i in range(br.size() - 1):
			var r0: float = br[i]
			var r1: float = br[i + 1]
			if r1 - r0 < 1e-4:
				continue
			var mid := (r0 + r1) * 0.5
			_emit_wall_segment(line, r0, r1, _room_at(a - EPS_A, mid), _room_at(a + EPS_A, mid), _opening_at("radial", a, mid))
	for key in alongs:
		var ln: Dictionary = alongs[key]
		var line := {"kind": "along", "fixed": ln.fixed, "axis": ln.axis}
		var t: float = ln.fixed
		var ax: float = ln.axis
		var br: Array = ln.breaks
		br.sort()
		for i in range(br.size() - 1):
			var s0: float = br[i]
			var s1: float = br[i + 1]
			if s1 - s0 < 1e-4:
				continue
			var mid := (s0 + s1) * 0.5
			var side_a := owner_of(_rooms, strip_point(ax, mid, t - EPS_R))
			var side_b := owner_of(_rooms, strip_point(ax, mid, t + EPS_R))
			_emit_wall_segment(line, s0, s1, side_a, side_b, _opening_at("along", t, mid, ax))


## Колонны каркаса внутри больших залов: кольца {"r", "step", "offset"} (град) из блока "columns".
## На линиях перегородок колонны не ставятся — там их роль играет стена (блокаут).
func _build_columns() -> void:
	var rings: Array = _def.get("columns", [])
	if rings.is_empty():
		return
	var col := float(_thick.get("column", 0.6))
	var st := _st(_walls, _gb("painted_plaster_wall", "gb_structural"))
	var near_ops: Array[Vector3] = []
	for op in _openings:
		match String(op.wall):
			"arc":
				near_ops.append(polar((float(op.a[0]) + float(op.a[1])) * 0.5, float(op.r)))
			"along":
				near_ops.append(strip_point(float(op.axis), (float(op.s[0]) + float(op.s[1])) * 0.5, float(op.t)))
			_:
				near_ops.append(polar(float(op.a), (float(op.r[0]) + float(op.r[1])) * 0.5))
	for ring in rings:
		var r := float(ring.r)
		var step := float(ring.step)
		for k in range(int(round(360.0 / step))):
			var a := float(ring.get("offset", 0.0)) + step * float(k)
			var pos := polar(a, r)
			var room := owner_of(_rooms, pos)
			if room.is_empty() or is_strip(room) or bool(room.get("locked", false)) or bool(room.get("outdoor", false)):
				continue
			if not String(room.get("type", "")) in COLUMN_ROOMS:
				continue
			var tdir := polar(a + 90.0, 1.0)
			var rdir := polar(a, 1.0)
			var ok := true
			for off in [tdir * COLUMN_CLEAR, -tdir * COLUMN_CLEAR, rdir * COLUMN_CLEAR, -rdir * COLUMN_CLEAR]:
				if String(owner_of(_rooms, pos + off).get("id", "")) != String(room.get("id", "")):
					ok = false
					break
			for q in near_ops:
				if ok and q.distance_to(pos) < COLUMN_DOOR_GAP:
					ok = false
			if ok:
				_post(st, pos, tdir, col, col, _wall_h)


## Где прямая t полосы пересекает дугу r (по эту сторону центра), м вдоль оси.
static func _strip_s(r: float, t: float) -> float:
	return sqrt(maxf(r * r - t * t, 0.0))


func _add_breaks(lines: Dictionary, fixed: float, ends: Array, key: String = "") -> void:
	if key == "":
		key = "%.2f" % fixed
	if not lines.has(key):
		lines[key] = {"fixed": fixed, "breaks": []}
	for e in ends:
		var found := false
		for b in lines[key].breaks:
			if absf(float(b) - float(e)) < 1e-4:
				found = true
				break
		if not found:
			lines[key].breaks.append(float(e))


func _emit_wall_segment(line: Dictionary, p0: float, p1: float, side_a: Dictionary, side_b: Dictionary, op: Dictionary) -> void:
	if side_a.is_empty() and side_b.is_empty():
		return
	# линия проходит внутри одного помещения (кольцевую стену перекрыла полоса) — стены нет
	if not side_a.is_empty() and String(side_a.get("id", "")) == String(side_b.get("id", "")):
		return
	var a_out: bool = side_a.is_empty() or bool(side_a.get("outdoor", false))
	var b_out: bool = side_b.is_empty() or bool(side_b.get("outdoor", false))
	var indoor := side_b if a_out else side_a
	var other := side_a if a_out else side_b
	var facade := other.is_empty() or bool(other.get("outdoor", false))
	var cls := _wall_class(line, side_a, side_b, facade)
	_cur_key = String(side_a.get("key", side_b.get("key", "")))
	# толщина — на отрезок: все помощники ниже (ригели, роллеты, косяки) берут её из _wall_t
	_wall_t = float(_thick.get(cls, _base_t))
	var mat := "concrete_panels" if facade else String(indoor.get("wall", "painted_plaster_wall"))
	if _greybox:
		mat = "gb_" + cls
	var pts := _line_points(line, p0, p1)

	if not op.is_empty():
		match String(op.kind):
			"open":
				_colonnade(line, p0, p1, mat, float(op.get("height", float(_arch.storefront_h))), op)
			"storefront":
				_storefront(line, p0, p1, mat, side_a, side_b, op)
			"door":
				_doorway(line, p0, p1, mat, float(op.get("height", float(_arch.door_h))))
			"shutter":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.shutter_h))), false)
			"half":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.shutter_h))), false, float(_arch.half_gap))
			"gate":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.gate_h))), false)
			"locked":
				_rolling_gate(line, p0, p1, mat, float(op.get("height", float(_arch.shutter_h))), true)
			"barrier":
				_wall_strip(_st(_walls, _gb("concrete_block_wall_02", "gb_fence")), pts, _wall_t * 2.0, _barrier_h)
		return

	if a_out and b_out:
		# двор–двор: границы нет; двор–пустота: ограда периметра. У кольца территорию
		# ограничивает забор участка (см. _build_ring_surroundings), дворы между собой открыты.
		if (side_a.is_empty() or side_b.is_empty()) and _ring.is_empty():
			_wall_strip(_st(_walls, "concrete_block_wall_02"), pts, _wall_t, _fence_h)
		return
	_solid_wall(line, p0, p1, mat)


## Класс конструкции стены — от него толщина и серый тон в блокауте.
## facade — наружная; fire — радиальная на границе сектора (пожарный отсек, REI 150);
## structural — дуги между поясами кольца и стены коридоров/техядер; остальное — перегородки арендаторов.
func _wall_class(line: Dictionary, side_a: Dictionary, side_b: Dictionary, facade: bool) -> String:
	if facade:
		return "facade"
	if String(line.kind) == "arc":
		return "structural"
	if String(line.kind) == "radial":
		for fa in _fire_angles:
			if absf(wrapf(float(line.fixed) - fa, -180.0, 180.0)) <= FIRE_TOL_DEG:
				return "fire"
	for side in [side_a, side_b]:
		if bool(side.get("core", false)) or String(side.get("type", "")) in ["corridor", "gallery", "atrium"]:
			return "structural"
	return "partition"


## Пол: в блокауте — серый по типу покрытия (плитка / бетон — тоном различимы). Асфальт улицы
## и в блокауте настоящий: на нём мокрый шейдер (лужи, отражения в дождь).
func _floor_mat(textured: String, outdoor: bool = false) -> String:
	if not _greybox or outdoor or textured in OUTDOOR_TEXTURED:
		return textured
	return String(GREYBOX_FLOOR.get(textured, "gbf_concrete"))


## Текстурный материал или его серая замена в блокауте.
func _gb(textured: String, grey: String) -> String:
	return grey if _greybox else textured


## Глухая стена с цоколем, карнизом и пилястрами по концам и через шаг.
func _solid_wall(line: Dictionary, p0: float, p1: float, mat: String) -> void:
	var pts := _line_points(line, p0, p1)
	_wall_strip(_st(_walls, mat), pts, _wall_t, _wall_h)
	if _greybox:
		return
	_wall_strip(_st(_walls, "concrete_wall_006"), pts, _wall_t + 0.12, float(_arch.plinth_h))
	_wall_strip(_st(_walls, mat), pts, _wall_t + 0.16, float(_arch.cornice_h), _wall_h - float(_arch.cornice_h))
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var n := int(floor(len / float(_arch.pilaster_spacing)))
	for i in range(1, n + 1):
		var p := _line_advance(line, p0, len * float(i) / float(n + 1))
		_pilaster(line, p, mat)


func _pilaster(line: Dictionary, p: float, mat: String) -> void:
	if _greybox:
		return
	var pos := _line_point(line, p)
	var key := "%.1f,%.1f" % [pos.x, pos.z]
	if _posts.has(key):
		return
	_posts[key] = true
	_post(_st(_walls, mat), pos, _line_dir(line, p), float(_arch.pilaster_w), _wall_t + 0.4, _wall_h)


## Ригель над проёмом: стена от высоты y до верха, с карнизом.
func _lintel(line: Dictionary, p0: float, p1: float, mat: String, y: float) -> void:
	var pts := _line_points(line, p0, p1)
	_wall_strip(_st(_walls, mat), pts, _wall_t, _wall_h - y, y)
	if _greybox:
		return
	_wall_strip(_st(_walls, mat), pts, _wall_t + 0.16, float(_arch.cornice_h), _wall_h - float(_arch.cornice_h))


## Колоннада: проход без стены, балка только под перекрытием, колонны по концам и через шаг.
func _colonnade(line: Dictionary, p0: float, p1: float, mat: String, _y: float, op: Dictionary = {}) -> void:
	if _greybox:
		# балка перекрытия и колонны по сетке каркаса (квадратные, шаг column_grid)
		_lintel(line, p0, p1, mat, _wall_h - 0.7)
		var col := float(_thick.get("column", 0.6))
		var clen := _line_len(line, p0, p1)
		var cn := maxi(1, int(round(clen / float(_thick.get("column_grid", 9.0)))))
		for i in range(cn + 1):
			var cp := _line_advance(line, p0, clen * float(i) / float(cn))
			if (i == 0 or i == cn) and not bool(_arch.open_split_columns) and _inside_opening(line, op, cp):
				continue
			var pos := _line_point(line, cp)
			var key := "%.1f,%.1f" % [pos.x, pos.z]
			if _posts.has(key):
				continue
			_posts[key] = true
			_post(_st(_walls, "gb_structural"), pos, _line_dir(line, cp), col, col, _wall_h)
		return
	_lintel(line, p0, p1, mat, _wall_h - float(_arch.cornice_h) * 2.0)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var n := int(floor(len / float(_arch.column_spacing)))
	for i in range(1, n + 1):
		_pilaster(line, _line_advance(line, p0, len * float(i) / float(n + 1)), mat)


## Точка p линии лежит внутри проёма op, а не на его краю: отрезок проёма разделён границей
## соседних помещений, колонна тут встала бы посреди прохода.
func _inside_opening(line: Dictionary, op: Dictionary, p: float) -> bool:
	if op.is_empty():
		return false
	var tol := 0.05
	match String(line.kind):
		"arc":
			var a0 := float(op.a[0])
			var span := float(op.a[1]) - a0
			var x := fposmod(p - a0, 360.0)
			var tol_deg := rad_to_deg(tol / float(line.fixed))
			return x > tol_deg and x < span - tol_deg
		"along":
			return p > float(op.s[0]) + tol and p < float(op.s[1]) - tol
	return p > float(op.r[0]) + tol and p < float(op.r[1]) - tol


## Дверной проём: ригель, косяки и створка (сцена door.tscn) на петле у p0.
func _doorway(line: Dictionary, p0: float, p1: float, mat: String, y: float) -> void:
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	# в блокауте пилястр нет — створка на весь проём
	var jamb := 0.1 if _greybox else float(_arch.pilaster_w)
	var width := _line_len(line, p0, p1) - jamb
	var hinge := _line_point(line, _line_advance(line, p0, jamb * 0.5))
	var dir := _line_dir(line, p0)
	if _preview:
		return
	var door := DOOR_SCENE.instantiate() as Door
	door.width = width
	door.height = y - 0.05
	door.required_key = _cur_key
	door.transform = Transform3D(Basis(dir, Vector3.UP, dir.cross(Vector3.UP).normalized()), hinge)
	_doors.append(door)


## Роллета: рулон под ригелем; closed — полотно опущено до пола (непроходимо); gap > 0 — полотно
## опущено до этой высоты над полом (поднята наполовину: под ней пролезают лёжа, ИИ не проходит).
func _rolling_gate(line: Dictionary, p0: float, p1: float, mat: String, y: float, closed: bool, gap: float = 0.0) -> void:
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var pts := _line_points(line, p0, p1)
	var shutter := _gb("painted_metal_shutter", "steel_dark")
	_wall_strip(_st(_walls, shutter), pts, _wall_t + 0.3, 0.45, y - 0.45)
	if closed:
		_wall_strip(_st(_walls, shutter), pts, 0.06, y - 0.45)
	elif gap > 0.0:
		_wall_strip(_st(_walls, shutter), pts, 0.06, y - 0.45 - gap, gap)


## Витрина: стекло в стальных рамах по бокам, вход посередине с рулоном роллеты и вывеской.
func _storefront(line: Dictionary, p0: float, p1: float, mat: String, side_a: Dictionary, side_b: Dictionary, op: Dictionary = {}) -> void:
	var y: float = float(_arch.storefront_h)
	_lintel(line, p0, p1, mat, y)
	_pilaster(line, p0, mat)
	_pilaster(line, p1, mat)
	var len := _line_len(line, p0, p1)
	var entrance := minf(float(_arch.entrance_w), len * 0.6)
	var e0 := _line_advance(line, p0, (len - entrance) * 0.5)
	var e1 := _line_advance(line, p0, (len + entrance) * 0.5)
	if not bool(_arch.storefront_split_entrances) and not op.is_empty():
		# кусок разделённой витрины: вход один — посередине всей витрины, остальное стекло
		var mid := _op_mid(line, op, p0)
		if mid < p0 - 1e-4 or mid > p1 + 1e-4:
			_glass_run(line, p0, p1, y)
			return
		entrance = minf(float(_arch.entrance_w), minf(_op_len(line, op) * 0.6, len))
		e0 = _line_advance(line, mid, -entrance * 0.5)
		e1 = _line_advance(line, mid, entrance * 0.5)
		if e0 < p0:
			e0 = p0
			e1 = _line_advance(line, p0, entrance)
		elif e1 > p1:
			e1 = p1
			e0 = _line_advance(line, p1, -entrance)
	_glass_run(line, p0, e0, y)
	_glass_run(line, e1, p1, y)
	# вход: рулон роллеты и вывеска над ним
	var ent := _line_points(line, e0, e1)
	_wall_strip(_st(_walls, _gb("painted_metal_shutter", "steel_dark")), ent, _wall_t + 0.3, 0.45, y - 0.45)
	var shop := side_a if String(side_a.get("type", "")) == "retail" else side_b
	var gallery_side := side_b if shop == side_a else side_a
	if shop.is_empty():
		return
	var s0 := _line_advance(line, e0, -1.0)
	var s1 := _line_advance(line, e1, 1.0)
	var sign_pts := _line_points(line, s0, s1)
	if not _greybox:
		_wall_strip(_st(_walls, "sign_panel"), sign_pts, _wall_t + 0.24, float(_arch.sign_h), y + 0.5)
	# подпись — в сторону галереи
	var mid := _line_advance(line, e0, entrance * 0.5)
	var pos := _line_point(line, mid)
	var toward_gallery := _side_normal(line, mid, gallery_side)
	var label := Label3D.new()
	label.text = String(shop.get("name", "")).to_upper()
	label.font_size = 64
	label.pixel_size = 0.01
	label.modulate = Color.from_string(String(shop.get("sign_color", "")), Color(1.0, 0.86, 0.6))
	label.shaded = false
	label.outline_size = 0
	label.position = pos + toward_gallery * (_wall_t * 0.5 + 0.5) + Vector3.UP * (y + 0.5 + float(_arch.sign_h) * 0.5)
	label.basis = Basis.looking_at(-toward_gallery, Vector3.UP)
	_labels.append(label)


## Середина проёма op в параметре линии (у дуги — угол рядом с near, через шов ±180).
func _op_mid(line: Dictionary, op: Dictionary, near: float) -> float:
	match String(line.kind):
		"arc":
			var m := (float(op.a[0]) + float(op.a[1])) * 0.5
			return near + wrapf(m - near, -180.0, 180.0)
		"along":
			return (float(op.s[0]) + float(op.s[1])) * 0.5
	return (float(op.r[0]) + float(op.r[1])) * 0.5


## Длина проёма op, м.
func _op_len(line: Dictionary, op: Dictionary) -> float:
	match String(line.kind):
		"arc":
			return deg_to_rad(float(op.a[1]) - float(op.a[0])) * float(line.fixed)
		"along":
			return float(op.s[1]) - float(op.s[0])
	return float(op.r[1]) - float(op.r[0])


## Единичная нормаль линии в точке p, направленная в сторону помещения room.
func _side_normal(line: Dictionary, p: float, room: Dictionary) -> Vector3:
	var d := _line_dir(line, p)
	var n := Vector3(-d.z, 0.0, d.x)
	if room.is_empty():
		return n
	var probe := _line_point(line, p) + n * 0.5
	return n if in_shape(room, probe) else -n


## Стеклянные панели между стойками; часть панелей выбита (детерминированно по позиции).
func _glass_run(line: Dictionary, p0: float, p1: float, y: float) -> void:
	var len := _line_len(line, p0, p1)
	if len < 0.3:
		return
	var n := maxi(1, int(round(len / float(_arch.pane_w))))
	var steel := _st(_walls, "steel_dark")
	# верхняя рейка рамы; нижняя (подоконник) — у каждой панели своя (GlassPanes: выбили — проходим)
	var pts := _line_points(line, p0, p1)
	_wall_strip(steel, pts, 0.12, 0.12, y - 0.12)
	for i in range(n + 1):
		var p := _line_advance(line, p0, len * float(i) / float(n))
		_post(steel, _line_point(line, p), _line_dir(line, p), 0.08, 0.1, y)
	for i in range(n):
		var q0 := _line_advance(line, p0, len * float(i) / float(n))
		var q1 := _line_advance(line, p0, len * float(i + 1) / float(n))
		var c := _line_point(line, (q0 + q1) * 0.5)
		var broken := (hash("%.1f:%.1f" % [c.x, c.z]) % 100) < int(_arch.broken_pane_pct)
		var a := _line_point(line, q0)
		var b := _line_point(line, q1)
		var x := b - a
		var w := x.length()
		x = x.normalized()
		var plinth := float(_arch.plinth_h)
		var h := y - plinth - 0.12
		_panes.append({"xf": Transform3D(Basis(x, Vector3.UP, x.cross(Vector3.UP).normalized()), (a + b) * 0.5 + Vector3.UP * (plinth + h * 0.5)),
			"size": Vector2(w, h), "floor_y": 0.0, "sill": Vector3(w, plinth, 0.12), "broken": broken})


## Окружение: кольцо продолжается за пределами сектора — полы, фасад и стена галереи без проёмов,
## асфальт вокруг здания. Каждый пояс радиусов достраивается там, где в нём нет помещений сектора.
func _build_surroundings() -> void:
	if not _ring.is_empty():
		_build_ring_surroundings()
		return
	var bands := [
		{"r": [0.5, 25.0], "floor": "large_floor_tiles_02"},
		{"r": [25.0, 33.0], "floor": "large_floor_tiles_02", "wall_r": 33.0, "wall": "painted_plaster_wall", "wall_h": _wall_h},
		{"r": [33.0, 84.0], "floor": "worn_tile_floor"},
		{"r": [84.0, 90.0], "floor": "concrete_floor_worn_001", "wall_r": 90.0, "wall": "concrete_panels", "wall_h": _wall_h},
		{"r": [90.0, 125.0], "floor": "asphalt_02", "wall_r": 125.0, "wall": "concrete_block_wall_02", "wall_h": _fence_h},
	]
	for band in bands:
		var r0: float = band.r[0]
		var r1: float = band.r[1]
		var a_min := 1e9
		var a_max := -1e9
		for room in _rooms:
			if is_strip(room) or float(room.r[1]) <= r0 + 1e-3 or float(room.r[0]) >= r1 - 1e-3:
				continue
			a_min = minf(a_min, float(room.a[0]))
			a_max = maxf(a_max, float(room.a[1]))
		var c0 := a_max if a_max > -1e8 else 0.0
		var c1 := (a_min + 360.0) if a_min < 1e8 else 360.0
		if c1 - c0 < 1.0:
			continue
		_annulus(_st(_floors, _floor_mat(String(band.floor))), c0, c1, r0, r1, 0.0)
		if band.has("wall_r"):
			_wall_strip(_st(_walls, String(band.wall)), _arc_points(float(band.wall_r), c0, c1), _wall_t, float(band.wall_h))
	_annulus(_st(_floors, _floor_mat("asphalt_02")), 0.0, 360.0, 90.0, 420.0, -0.03)


## Кольцо целиком: закрытая часть (полы поясов, несущие дуги), фасад на всю высоту здания по кругу,
## асфальт участка и забор территории — проходима только открытая часть участка.
func _build_ring_surroundings() -> void:
	var outer := float(_ring.get("outer_r", 200.0))
	var site := float(_ring.get("site_r", 300.0))
	var a0 := float(_def.angle[0])
	var a1 := float(_def.angle[1])
	var c0 := a1
	var c1 := a0 + 360.0
	var zones: Dictionary = _ring.get("zones", {})
	var inner_arcs: Array[float] = []
	# полное кольцо (открыто всё здание) — закрытой части нет
	if c1 - c0 < 0.5:
		zones = {}
	for key in zones:
		var z: Array = zones[key]
		_annulus(_st(_floors, _floor_mat(String(ZONE_FLOOR.get(key, "concrete_floor_worn_001")))), c0, c1, float(z[0]), float(z[1]), 0.0)
		if key != "atr" and float(z[0]) > 1.0:
			inner_arcs.append(float(z[0]))
	# несущие дуги закрытой части — за роллетами видно, что кольцо продолжается
	var t_str := float(_thick.get("structural", _base_t))
	for r in inner_arcs:
		if r >= outer - 0.01:
			continue
		_wall_strip(_st(_walls, _gb("painted_plaster_wall", "gb_structural")), _arc_points(r, c0, c1), t_str, _wall_h)
	# фасад: закрытая часть — во всю высоту здания; над открытой — верхние этажи поверх стен 1F
	var t_fac := float(_thick.get("facade", _base_t))
	var bh := float(_thick.get("building_height", _wall_h))
	var fmat := _gb("concrete_panels", "gb_facade")
	if c1 - c0 >= 0.5:
		_wall_strip(_st(_walls, fmat), _arc_points(outer, c0, c1), t_fac, bh)
	if bh > _wall_h:
		_wall_strip(_st(_walls, fmat), _arc_points(outer, a0, a1), t_fac, bh - _wall_h, _wall_h)
	# участок: асфальт вокруг и забор — дуга по краю открытой части и две радиальные отсечки
	_annulus(_st(_floors, _floor_mat("asphalt_02")), 0.0, 360.0, outer, site + 40.0, -0.03)
	var fence_h := float(_thick.get("site_fence_height", _fence_h))
	var t_fence := float(_thick.get("fence", _base_t))
	var fence := _st(_walls, _gb("concrete_block_wall_02", "gb_fence"))
	_wall_strip(fence, _arc_points(site, a0, a1), t_fence, fence_h)
	if _ring_full():
		return
	for a in [a0, a1]:
		_wall_strip(fence, PackedVector3Array([polar(a, outer), polar(a, site)]), t_fence, fence_h)


func _annulus(st: SurfaceTool, a0: float, a1: float, r0: float, r1: float, y: float) -> void:
	var n := maxi(1, int(ceil(deg_to_rad(a1 - a0) * r1 / (SEG_LEN * 2.0))))
	var lift := Vector3.UP * y
	for i in range(n):
		var aa := lerpf(a0, a1, float(i) / n)
		var ab := lerpf(a0, a1, float(i + 1) / n)
		var p00 := polar(aa, r0) + lift
		var p01 := polar(aa, r1) + lift
		var p10 := polar(ab, r0) + lift
		var p11 := polar(ab, r1) + lift
		var quad := PackedVector2Array([Vector2(p00.x, p00.z), Vector2(p10.x, p10.z), Vector2(p11.x, p11.z), Vector2(p01.x, p01.z)])
		if _touches_hole(quad):
			_holed_floor(st, quad, y)
			continue
		_quad(st, p00, p10, p11, p01, Vector3.UP, _uv_xz(p00), _uv_xz(p10), _uv_xz(p11), _uv_xz(p01))


## Контур выреза в мире (XZ): прямоугольник half, повёрнутый на yaw вокруг center.
static func hole_poly(h: Dictionary) -> PackedVector2Array:
	var c: Vector2 = h.center
	var hf: Vector2 = h.half
	var yaw := float(h.yaw)
	var ax := Vector2(cos(yaw), -sin(yaw))
	var az := Vector2(sin(yaw), cos(yaw))
	return PackedVector2Array([c - ax * hf.x - az * hf.y, c + ax * hf.x - az * hf.y, c + ax * hf.x + az * hf.y, c - ax * hf.x + az * hf.y])


func _touches_hole(poly: PackedVector2Array) -> bool:
	if holes.is_empty():
		return false
	var box := Rect2(poly[0], Vector2.ZERO)
	for p in poly:
		box = box.expand(p)
	for h in holes:
		var hp := hole_poly(h)
		var hb := Rect2(hp[0], Vector2.ZERO)
		for p in hp:
			hb = hb.expand(p)
		if box.intersects(hb) and not Geometry2D.intersect_polygons(poly, hp).is_empty():
			return true
	return false


## Кусок пола poly (выпуклый, мир XZ) без вырезов: вычитание контуров и триангуляция. Вырез целиком
## внутри куска — кусок сперва режется пополам через центр выреза (иначе вышел бы «бублик»).
func _holed_floor(st: SurfaceTool, poly: PackedVector2Array, y: float) -> void:
	var parts: Array = [poly]
	for h in holes:
		var hp := hole_poly(h)
		var next: Array = []
		for part in parts:
			var pp: PackedVector2Array = part
			var res := Geometry2D.clip_polygons(pp, hp)
			var outer_cw := Geometry2D.is_polygon_clockwise(pp)
			var ring := false
			for r in res:
				if Geometry2D.is_polygon_clockwise(r) != outer_cw:
					ring = true
			if not ring:
				next.append_array(res)
				continue
			var c: Vector2 = h.center
			var big := 1e5
			for half in [PackedVector2Array([Vector2(c.x, -big), Vector2(big, -big), Vector2(big, big), Vector2(c.x, big)]),
					PackedVector2Array([Vector2(-big, -big), Vector2(c.x, -big), Vector2(c.x, big), Vector2(-big, big)])]:
				for piece in Geometry2D.intersect_polygons(pp, half):
					next.append_array(Geometry2D.clip_polygons(piece, hp))
		parts = next
	for part in parts:
		var pp: PackedVector2Array = part
		var tris := Geometry2D.triangulate_polygon(pp)
		for i in range(0, tris.size(), 3):
			var a := Vector3(pp[tris[i]].x, y, pp[tris[i]].y)
			var b := Vector3(pp[tris[i + 1]].x, y, pp[tris[i + 1]].y)
			var d := Vector3(pp[tris[i + 2]].x, y, pp[tris[i + 2]].y)
			# лицом вверх — как у _quad: по часовой, если смотреть сверху
			if (b - a).cross(d - a).y > 0.0:
				var t := b
				b = d
				d = t
			for v in [a, b, d]:
				st.set_normal(Vector3.UP)
				st.set_uv(_uv_xz(v))
				st.add_vertex(v)


# ---------------------------------------------------------------- потолки, купол, светильники

## Узел «Ceilings»: перекрытия (с коллизией — ловят пули и солнце), стеклянный купол над
## атриумом с рёбрами, корпуса светильников. Всё — на CEILING_LAYER (только от первого лица).
## SectorLevel выносит узел из источников навмеша: крыша не должна стать «проходимой».
func _emit_ceilings(root: Node3D) -> void:
	if _ceilings.is_empty() and _ring.is_empty():
		return
	var body := StaticBody3D.new()
	body.name = "Ceilings"
	root.add_child(body)
	for mat_id in _ceilings:
		var mi := _mesh_node(_ceilings[mat_id], String(mat_id), true)
		mi.name = "Ceiling_" + String(mat_id)
		mi.layers = CEILING_LAYER
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		# потолок смотрит вниз — сверху его не видно; дождю нужен двусторонний двойник
		mi.add_to_group("rain_block", true)
		body.add_child(mi)
		_shadow_twin(body, mi)
		var cs := CollisionShape3D.new()
		cs.name = String(mat_id) + "_col"
		cs.shape = (mi.mesh as ArrayMesh).create_trimesh_shape()
		body.add_child(cs)
	if not _ring.is_empty():
		var floors := int(_ring.get("floors", 4))
		_build_atrium_shaft(body, float(_ring.get("atrium_r", 30.0)), floors)
		_build_dome(body, float(_ring.get("atrium_r", 30.0)), _wall_h * floors)
	# корпуса светильников — белые панели на потолке над каждым огнём
	var lamp_mesh := BoxMesh.new()
	lamp_mesh.size = Vector3(1.4, 0.08, 0.36)
	var lamp_sh := Shader.new()
	lamp_sh.code = LAMP_SHADER
	var lamp_mat := ShaderMaterial.new()
	lamp_mat.shader = lamp_sh
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.use_colors = true
	mm.mesh = lamp_mesh
	mm.instance_count = _lamps.size()
	for i in range(_lamps.size()):
		var p: Vector3 = _lamps[i]
		var yaw := atan2(p.x, p.z) + PI * 0.5
		mm.set_instance_transform(i, Transform3D(Basis(Vector3.UP, yaw), p + Vector3.UP * (_wall_h - 0.05)))
		mm.set_instance_color(i, _lamp_colors[i])
	var lamps := MultiMeshInstance3D.new()
	lamps.name = "Lamps"
	lamps.multimesh = mm
	lamps.material_override = lamp_mat
	lamps.layers = CEILING_LAYER
	lamps.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	lamps.add_to_group("mall_lamps")
	lamps.set_meta("base_colors", _lamp_colors.duplicate())
	body.add_child(lamps)


## Атриум — общий на все этажи ТЦ: шахта от 1F до крыши над последним этажом. Над 1F видно
## галереи верхних этажей (перекрытия с краем и стеклянным ограждением), фасады их магазинов по
## кругу галереи, кольцо крыши у купола. Декорация (туда не попасть — этажи отдельными картами);
## тень от неё — как от настоящих перекрытий.
func _build_atrium_shaft(parent: Node3D, atrium_r: float, floors: int) -> void:
	var zones: Dictionary = _ring.get("zones", {})
	var gal_r := float((zones.get("gal", [atrium_r, atrium_r + 10.0]) as Array)[1])
	var store := {}
	var slab := _gb("concrete_panels", "gb_slab")
	var facade := _gb("painted_plaster_wall", "gb_partition")
	var steel := _gb("steel_dark", "gb_structural")
	for k in range(1, floors + 1):
		var y := _wall_h * float(k)
		var t := 0.45
		# перекрытие галереи: верх, низ, торец у атриума (на крыше — просто кольцо)
		_annulus(_st(store, slab), -180.0, 180.0, atrium_r, gal_r + 0.2, y)
		_annulus_down(_st(store, slab), atrium_r, gal_r + 0.2, y - t)
		_wall_strip(_st(store, slab), _arc_points(atrium_r, -180.0, 180.0), 0.3, t, y - t)
		if k < floors:
			# ограждение: стекло и поручень
			_wall_strip(_st(store, "glass"), _arc_points(atrium_r + 0.2, -180.0, 180.0), 0.03, 1.0, y)
			_wall_strip(_st(store, steel), _arc_points(atrium_r + 0.2, -180.0, 180.0), 0.08, 0.06, y + 1.0)
			# витрины верхнего этажа по кругу галереи
			_wall_strip(_st(store, "glass"), _arc_points(gal_r - 0.05, -180.0, 180.0), 0.04, _wall_h * 0.5, y + 0.4)
	# стена-фасад верхних этажей по краю галереи (от потолка 1F до крыши)
	_wall_strip(_st(store, facade), _arc_points(gal_r + 0.2, -180.0, 180.0), 0.3, _wall_h * float(floors - 1), _wall_h)
	for mat_id in store:
		var mi := _mesh_node(store[mat_id], String(mat_id), false)
		mi.name = "Shaft_" + String(mat_id)
		mi.layers = CEILING_LAYER
		mi.add_to_group("rain_block", true)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		parent.add_child(mi)
		if String(mat_id) != "glass":
			_shadow_twin(parent, mi)


## Заградительные огни (временно — пока ТЦ не собран в редакторе, там их ставят руками):
## по верху фасада кольца через ~30 м, по краю шахты атриума, на вершине купола — мигающий.
func _build_beacons(root: Node3D) -> void:
	if _ring.is_empty():
		return
	var folder := Node3D.new()
	folder.name = "ObstructionLights"
	root.add_child(folder)
	var outer := float(_ring.get("outer_r", 200.0))
	var bh := float(_thick.get("building_height", _wall_h))
	var n := maxi(8, int(TAU * outer / 30.0))
	for i in range(n):
		# чуть снаружи фасада — свет ложится на стену
		_beacon(folder, polar(360.0 * float(i) / n - 180.0, outer + 0.45) + Vector3.UP * (bh + 0.1), false)
	var floors := int(_ring.get("floors", 4))
	var atr := float(_ring.get("atrium_r", 30.0))
	var gal_r := float((_ring.get("zones", {}).get("gal", [atr, atr + 10.0]) as Array)[1])
	var top := _wall_h * float(floors)
	for i in range(4):
		_beacon(folder, polar(45.0 + 90.0 * i, gal_r + 0.2) + Vector3.UP * (top + 0.15), false)
	_beacon(folder, Vector3(0.0, top + atr * 0.32 + 0.35, 0.0), true)


func _beacon(parent: Node3D, at: Vector3, flashing: bool) -> void:
	var b := ObstructionLight.new()
	b.name = "Beacon_%d" % parent.get_child_count()
	b.flashing = flashing
	b.position = at
	parent.add_child(b)


## Кольцо лицом вниз (низ перекрытия).
func _annulus_down(st: SurfaceTool, r0: float, r1: float, y: float) -> void:
	var n := maxi(1, int(ceil(TAU * r1 / (SEG_LEN * 2.0))))
	var lift := Vector3.UP * y
	for i in range(n):
		var aa := lerpf(-180.0, 180.0, float(i) / n)
		var ab := lerpf(-180.0, 180.0, float(i + 1) / n)
		var p00 := polar(aa, r0) + lift
		var p01 := polar(aa, r1) + lift
		var p10 := polar(ab, r0) + lift
		var p11 := polar(ab, r1) + lift
		_quad(st, p00, p01, p11, p10, Vector3.DOWN, _uv_xz(p00), _uv_xz(p01), _uv_xz(p11), _uv_xz(p10))


## Стеклянный купол атриума: сферический сегмент от стен (высота стен) к зениту, стальные
## рёбра-меридианы и кольца. Стекло тень не отбрасывает (солнце проходит), рёбра — да.
func _build_dome(parent: Node3D, radius: float, base_y: float) -> void:
	var rise := radius * 0.32
	var glass_st := SurfaceTool.new()
	glass_st.begin(Mesh.PRIMITIVE_TRIANGLES)
	var rings := 10
	var segs := 64
	for i in range(rings):
		for j in range(segs):
			var t0 := float(i) / rings
			var t1 := float(i + 1) / rings
			var a0 := TAU * float(j) / segs
			var a1 := TAU * float(j + 1) / segs
			var q := [_dome_pt(radius, rise, base_y, t0, a0), _dome_pt(radius, rise, base_y, t0, a1), _dome_pt(radius, rise, base_y, t1, a1), _dome_pt(radius, rise, base_y, t1, a0)]
			for k in [0, 2, 1, 0, 3, 2]:
				var p: Vector3 = q[k]
				glass_st.set_normal(Vector3(-p.x, radius, -p.z).normalized())
				glass_st.add_vertex(p)
	var glass := MeshInstance3D.new()
	glass.name = "DomeGlass"
	glass.mesh = glass_st.commit()
	var gm := StandardMaterial3D.new()
	gm.albedo_color = Color(0.75, 0.86, 0.92, 0.14)
	gm.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	gm.roughness = 0.05
	gm.metallic = 0.4
	gm.cull_mode = BaseMaterial3D.CULL_DISABLED
	glass.material_override = gm
	glass.layers = CEILING_LAYER
	glass.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	# стекло глубину не пишет — дождю нужен его непрозрачный двойник (RainOcclusion)
	glass.add_to_group("rain_block", true)
	parent.add_child(glass)
	var steel := SectorMaterials.get_material(_gb("steel_dark", "gb_structural"), true)
	var ribs := SurfaceTool.new()
	ribs.begin(Mesh.PRIMITIVE_TRIANGLES)
	# меридианы
	for j in range(16):
		var a := TAU * float(j) / 16.0
		for i in range(rings):
			_beam(ribs, _dome_pt(radius, rise, base_y, float(i) / rings, a), _dome_pt(radius, rise, base_y, float(i + 1) / rings, a), 0.22)
	# кольца
	for i in [0, 3, 6, 9]:
		for j in range(segs):
			_beam(ribs, _dome_pt(radius, rise, base_y, float(i) / rings, TAU * float(j) / segs), _dome_pt(radius, rise, base_y, float(i) / rings, TAU * float(j + 1) / segs), 0.2)
	var rib := MeshInstance3D.new()
	rib.name = "DomeRibs"
	rib.mesh = ribs.commit()
	rib.material_override = steel
	rib.layers = CEILING_LAYER
	rib.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(rib)
	_shadow_twin(parent, rib)


## Тень потолка в обоих видах: Godot не строит тень от того, что камера не рисует (слой
## CEILING_LAYER изометрия не видит) — рядом двойник «только тень» на обычном слое.
func _shadow_twin(parent: Node3D, mi: MeshInstance3D) -> void:
	var twin := MeshInstance3D.new()
	twin.name = mi.name + "_shadow"
	twin.mesh = mi.mesh
	twin.transform = mi.transform
	twin.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_SHADOWS_ONLY
	twin.material_override = _shadow_mat()
	parent.add_child(twin)


static var _shadow_material: StandardMaterial3D


## Материал теневых двойников: непрозрачный, двусторонний, без растворения у камеры.
static func _shadow_mat() -> StandardMaterial3D:
	if _shadow_material == null:
		_shadow_material = StandardMaterial3D.new()
		_shadow_material.cull_mode = BaseMaterial3D.CULL_DISABLED
	return _shadow_material


## Точка купола: t — от края (0) к зениту (1), a — азимут; base_y — высота опоры.
func _dome_pt(radius: float, rise: float, base_y: float, t: float, a: float) -> Vector3:
	var r := radius * cos(t * PI * 0.5)
	var y := base_y + rise * sin(t * PI * 0.5)
	return Vector3(cos(a) * r, y, sin(a) * r)


## Балка квадратного сечения w между точками (для рёбер купола).
func _beam(st: SurfaceTool, p0: Vector3, p1: Vector3, w: float) -> void:
	var d := (p1 - p0).normalized()
	var side := d.cross(Vector3.UP).normalized() if absf(d.y) < 0.99 else Vector3.RIGHT
	var up := side.cross(d).normalized()
	var h := w * 0.5
	var corners := [side * h + up * h, -side * h + up * h, -side * h - up * h, side * h - up * h]
	for k in range(4):
		var c0: Vector3 = corners[k]
		var c1: Vector3 = corners[(k + 1) % 4]
		var n := (c0 + c1).normalized()
		for p in [p0 + c0, p1 + c0, p1 + c1, p0 + c0, p1 + c1, p0 + c1]:
			st.set_normal(n)
			st.add_vertex(p)


# ---------------------------------------------------------------- узлы

func _emit_meshes(root: Node3D) -> void:
	# Полы — с коллайдерами: по ним печётся навмеш (визуальные меши для этого не читаем — дорого).
	var floors := StaticBody3D.new()
	floors.name = "Floors"
	root.add_child(floors)
	for mat_id in _floors:
		var fi := _mesh_node(_floors[mat_id], String(mat_id), false)
		floors.add_child(fi)
		var fcs := CollisionShape3D.new()
		fcs.name = fi.name + "_col"
		fcs.shape = (fi.mesh as ArrayMesh).create_trimesh_shape()
		floors.add_child(fcs)
	var walls := StaticBody3D.new()
	walls.name = "Walls"
	root.add_child(walls)
	for mat_id in _walls:
		var mi := _mesh_node(_walls[mat_id], String(mat_id), true)
		# стена растворяется у камеры (изометрия), а в проходе теней «камера» — сам свет: у ракеты
		# и фонаря стены были бы дырявыми и свет шёл насквозь. Тень — от двойника без растворения,
		# двустороннего (иначе у тонких перемычек и по стыку с полом свет подтекает)
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		walls.add_child(mi)
		_shadow_twin(walls, mi)
		var cs := CollisionShape3D.new()
		cs.name = mi.name + "_col"
		cs.shape = (mi.mesh as ArrayMesh).create_trimesh_shape()
		walls.add_child(cs)
	_add_occluder(root, walls)
	if not _panes.is_empty():
		var gp := GlassPanes.new()
		# имя одно у всех peer — по нему RPC попаданий и состояния стёкол
		gp.name = "GlassPanes"
		gp.setup(_panes)
		root.add_child(gp)
	for mat_id in _glass:
		var gi := _mesh_node(_glass[mat_id], String(mat_id), false)
		walls.add_child(gi)
		var gcs := CollisionShape3D.new()
		gcs.name = gi.name + "_col"
		gcs.shape = (gi.mesh as ArrayMesh).create_trimesh_shape()
		walls.add_child(gcs)
	var doors := Node3D.new()
	doors.name = "Doors"
	root.add_child(doors)
	# одинаковые имена у всех peer (порядок сборки один): по пути к двери идут просьба клиента
	# открыть и её синхронизатор — с автоименем (@Node3D@N, у каждого процесса своё) не доходили
	for i in range(_doors.size()):
		_doors[i].name = "Door_%d" % i
		doors.add_child(_doors[i])
	var signs := Node3D.new()
	signs.name = "Signs"
	root.add_child(signs)
	for l in _labels:
		signs.add_child(l)


## Глухие стены — окклюдеры: что целиком за ними, не рисуется. Нужно в прицеле, где камера видит
## на сотни метров. Рамы, стекло, вывески и баннеры не закрывают обзор — их не берём.
func _add_occluder(root: Node3D, walls: Node3D) -> void:
	var meshes: Array[Mesh] = []
	for c in walls.get_children():
		var mi := c as MeshInstance3D
		if mi == null or String(mi.name) in ["steel_dark", "sign_panel"] or String(mi.name).begins_with("banner_"):
			continue
		meshes.append(mi.mesh)
	var oi := BlockoutMesh.make_occluder(meshes)
	if oi:
		root.add_child(oi)


func _mesh_node(st: SurfaceTool, mat_id: String, shadows: bool) -> MeshInstance3D:
	st.generate_tangents()
	var mesh := st.commit()
	var mi := MeshInstance3D.new()
	mi.name = mat_id
	mi.mesh = mesh
	# Всё, что не пол, растворяется у камеры, чтобы стена между камерой и игроком не закрывала обзор.
	mi.material_override = SectorMaterials.get_material(mat_id, shadows)
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi


func _build_floor_collider(root: Node3D) -> void:
	var body := StaticBody3D.new()
	body.name = "Ground"
	# узлы с вырезом в земле могут снимать с неё столкновение того, кто внутри выреза
	body.add_to_group("ground_plane")
	var cs := CollisionShape3D.new()
	cs.shape = WorldBoundaryShape3D.new()
	body.add_child(cs)
	root.add_child(body)


## Аварийный свет внутри и прожекторы на дворах. Закрытые помещения — тёмные.
func _build_lights(root: Node3D) -> void:
	var lights := Node3D.new()
	lights.name = "Lights"
	root.add_child(lights)
	for room in _rooms:
		if bool(room.get("locked", false)):
			continue
		var outdoor := bool(room.get("outdoor", false))
		if is_strip(room):
			_strip_lights(lights, room)
			continue
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		var rm := (r0 + r1) * 0.5
		var arc_len := deg_to_rad(a1 - a0) * rm
		var depth := r1 - r0
		# атриум освещён через купол; у большого кольца шаг реже — иначе сотни точечных огней
		if not _ring.is_empty() and String(room.get("type", "")) == "atrium":
			continue
		var step := 22.0 if outdoor else 11.0
		if not _ring.is_empty():
			step = 32.0 if outdoor else 15.0
		var na := maxi(1, int(round(arc_len / step)))
		var nr := maxi(1, int(round(depth / step)))
		for i in range(na):
			for j in range(nr):
				var a := lerpf(a0, a1, (i + 0.5) / na)
				var r := lerpf(r0, r1, (j + 0.5) / nr)
				var pos := polar(a, r)
				if String(owner_of(_rooms, pos).get("id", "")) != String(room.get("id", "")):
					continue
				if outdoor:
					var spot := SpotLight3D.new()
					spot.position = pos + Vector3(0, 8.0, 0)
					spot.rotation_degrees.x = -90.0
					spot.light_color = Color(1.0, 0.74, 0.45)
					spot.light_energy = 9.0
					spot.spot_range = 30.0
					spot.spot_angle = 55.0
					spot.shadow_enabled = _ring.is_empty()
					lights.add_child(spot)
				else:
					_lamp(lights, pos, room)


## Свет полосы — сеткой по её прямоугольнику (шаг как у помещений кольца).
func _strip_lights(lights: Node3D, room: Dictionary) -> void:
	var ax := float(room.axis)
	var t0 := float(room.t[0])
	var t1 := float(room.t[1])
	var s0 := _strip_s(float(room.r[0]), 0.0)
	var s1 := _strip_s(float(room.r[1]), 0.0)
	var nt := maxi(1, int(round((t1 - t0) / 15.0)))
	var ns := maxi(1, int(round((s1 - s0) / 15.0)))
	for i in range(nt):
		for j in range(ns):
			var pos := strip_point(ax, lerpf(s0, s1, (j + 0.5) / ns), lerpf(t0, t1, (i + 0.5) / nt))
			if String(owner_of(_rooms, pos).get("id", "")) != String(room.get("id", "")):
				continue
			_lamp(lights, pos, room)


## Потолочный светильник: огонь + панель (в MultiMesh ламп, её цвет — _lamp_colors). Свет по
## типу помещения (LAMP_LOOK: магазин тёплый и яркий, склад и техника — холодный и тусклый) и
## с разбросом ±12 % от места (одинаково у всех peer) — помещения залиты по-разному. Огонь знает
## номер своей панели (meta "lamp"): RaidAtmosphere гасит / красит / мигает их вместе.
func _lamp(lights: Node3D, pos: Vector3, room: Dictionary) -> void:
	var look: Array = LAMP_LOOK.get(String(room.get("type", "")), LAMP_LOOK[""])
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(Vector2i(int(pos.x * 10.0), int(pos.z * 10.0)))
	var k := float(look[1]) * rng.randf_range(0.88, 1.12)
	var omni := OmniLight3D.new()
	omni.position = pos + Vector3(0, minf(_wall_h - 1.0, 5.5), 0)
	omni.light_color = look[0]
	omni.light_energy = 3.5 * k
	omni.omni_range = 14.0
	omni.omni_attenuation = 1.4
	omni.set_meta("lamp", _lamps.size())
	omni.add_to_group("mall_lights")
	lights.add_child(omni)
	_lamps.append(pos)
	_lamp_colors.append(Color(look[0]) * clampf(k, 0.4, 1.3))


## Пропсы по правилам помещений (см. PropPlacement). Сид — из id сектора: расстановка воспроизводима.
## Контейнеры лута на пропсах: одинаковые имена у всех peer (Loot/Loot_N) — по ним RPC и
## синхронизация. Таблица — по теме помещения (data/loot.json → rooms), иначе по типу пропа.
func _build_loot(root: Node3D, lootables: Array[Dictionary]) -> void:
	var folder := Node3D.new()
	folder.name = "Loot"
	root.add_child(folder)
	var theme_of := {}
	for room in _rooms:
		if room.has("theme"):
			theme_of[String(room.id)] = String(room.theme)
	var i := 0
	for l in lootables:
		var spec := ItemDb.container(String(l.kind))
		var c := LOOT_SCENE.instantiate() as LootContainer
		c.name = "Loot_%d" % i
		i += 1
		c.display_name = String(spec.name)
		var themed := ItemDb.room_table(String(theme_of.get(String(l.room), String(l.room))))
		# стеллажи, кассы и киоски берут тему магазина; шкафы/коробки — своё
		c.table = themed if themed != "" and String(l.kind) in ["shelf_retail", "checkout", "kiosk", "shelf_warehouse"] else String(spec.table)
		c.search_s = float(spec.search)
		c.position = (l.pos as Vector3) + Vector3.UP * Balance.LOOT_POINT_HEIGHT
		folder.add_child(c)
	root.set_meta("loot_count", i)


func _build_props(root: Node3D) -> void:
	var props := Node3D.new()
	props.name = "Props"
	root.add_child(props)
	var placement := PropPlacement.new()
	placement.place(props, _rooms, _openings, root.get_meta("spawn", Vector3.ZERO), hash(String(_def.get("id", ""))), keepouts)
	root.set_meta("prop_count", placement.count)
	_build_loot(root, placement.lootables)
	var loose: Node3D = Node3D.new()
	loose.name = "LooseLoot"
	root.add_child(loose)
	for index: int in range(placement.loose_points.size()):
		var point: Dictionary = placement.loose_points[index]
		var found: LooseLoot = LOOSE_LOOT_SCENE.instantiate() as LooseLoot
		found.name = "Found_%d" % index
		found.position = point.pos
		found.rotation.y = float(point.yaw)
		found.table = String(point.table)
		loose.add_child(found)
	root.set_meta("loose_loot_points", placement.loose_points.size())
	# меши пропсов склеиваются по клеткам — иначе каждая коробка на стеллаже отдельный вызов отрисовки
	root.set_meta("prop_batches", PropBatcher.batch(props, PROP_BATCH_CELL, PROP_VIS_END))


## Верхний слой: балки перекрытия поперёк помещений, вентиляционный короб вдоль коридора,
## баннеры на колоннаде атриума — то, что делает коробки зданием при взгляде сверху.
func _build_overhead() -> void:
	var steel := _st(_walls, "steel_dark")
	var duct := _st(_walls, "metal_plate")
	for room in _rooms:
		if bool(room.get("outdoor", false)) or bool(room.get("locked", false)) or is_strip(room):
			continue
		var a0 := float(room.a[0])
		var a1 := float(room.a[1])
		var r0 := float(room.r[0])
		var r1 := float(room.r[1])
		var t := String(room.get("type", ""))
		if t == "atrium":
			continue
		if t == "corridor":
			var rm := (r0 + r1) * 0.5
			_wall_strip(duct, _arc_points(rm, a0, a1), 0.7, 0.5, _wall_h - 1.5)
			continue
		var rm2 := (r0 + r1) * 0.5
		var len := deg_to_rad(a1 - a0) * rm2
		var n := int(floor(len / 4.0))
		for i in range(1, n + 1):
			var a := lerpf(a0, a1, float(i) / float(n + 1))
			_wall_strip(steel, PackedVector3Array([polar(a, r0 + 0.3), polar(a, r1 - 0.3)]), 0.25, 0.5, _wall_h - 0.6)
	# баннеры: на каждой второй колонне колоннады
	var banner_colors := [Color(0.12, 0.14, 0.36), Color(0.3, 0.12, 0.36), Color(0.45, 0.1, 0.1), Color(0.1, 0.25, 0.3)]
	var k := 0
	for op in _openings:
		if String(op.kind) != "open" or String(op.wall) != "arc":
			continue
		var r := float(op.r)
		var len := deg_to_rad(float(op.a[1]) - float(op.a[0])) * r
		var n := int(floor(len / float(_arch.column_spacing)))
		for i in range(1, n + 1, 2):
			var a := float(op.a[0]) + rad_to_deg(len * float(i) / float(n + 1) / r)
			var c: Color = banner_colors[k % banner_colors.size()]
			k += 1
			var st := _st(_walls, "banner_%d" % (k % banner_colors.size()))
			var half := rad_to_deg(0.6 / r)
			var pts := _arc_points(r + 0.45, a - half, a + half)
			_wall_strip(st, pts, 0.04, 3.2, _wall_h - float(_arch.cornice_h) * 2.0 - 3.4)


## Точки эвакуации из проёмов kind=gate с полем extraction.
func _build_markers(root: Node3D) -> void:
	var marks := Node3D.new()
	marks.name = "Markers"
	root.add_child(marks)
	for op in _openings:
		if not op.has("extraction"):
			continue
		var m := Node3D.new()
		m.name = String(op.extraction)
		if String(op.wall) == "arc":
			m.position = polar((float(op.a[0]) + float(op.a[1])) * 0.5, float(op.r))
		elif String(op.wall) == "along":
			m.position = strip_point(float(op.axis), (float(op.s[0]) + float(op.s[1])) * 0.5, float(op.t))
		else:
			m.position = polar(float(op.a), (float(op.r[0]) + float(op.r[1])) * 0.5)
		# старые маркеры из JSON (f1_market) — не ExtractionPoint, своя группа
		m.add_to_group("extraction_markers")
		marks.add_child(m)
