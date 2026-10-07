class_name RangeTarget
extends Target
## Мишень тира убежища на тележке дорожки (RangeLane): бумажный лист на подвесе или манекен.
## Попадание считает Hitscan стрелка (как у поппера): урон над точкой, хитмаркер, звук по
## meta "surface". Бумага — пробоины рисуются прямо в текстуру листа и качают подвес; манекен —
## пробоины декалями. Пробоины видят все в убежище: дорожка рассылает точку попадания.
## Вид — авторские узлы сцены (Paper под Sway или Persona), скрипт только оживляет их.

enum Kind { PAPER, MANNEQUIN }

signal holed(local_point: Vector3)

@export var kind: Kind = Kind.PAPER
## Лист: ширина и высота лицевой стороны (м), как у меша Paper (UV 0..1 по всему листу).
@export var paper_size: Vector2 = Vector2(0.6, 1.0)

var _sway: Node3D
var _paper: MeshInstance3D
## Чистый лист и лист с пробоинами (копия, которую шлёт видеокарте ImageTexture).
var _clean: Image
var _sheet: Image
var _sheet_tex: ImageTexture
var _sheet_dirty: bool = false
var _swing_rate: float = 0.0
var _swing_angle: float = 0.0
## Пробоины по порядку: при переполнении лист перерисовывается без самых старых.
var _holes: Array[Vector2] = []
var _decals: Array[Decal] = []
var _hole_tex: Texture2D


func _ready() -> void:
	add_to_group("shootable")
	collision_layer = Hitscan.LAYER_MARAUDER
	collision_mask = 0
	head_height = float(Balance.RANGE.paper_head_m if kind == Kind.PAPER else Balance.RANGE.mannequin_head_m)
	set_meta("surface", "cardboard" if kind == Kind.PAPER else "plastic")
	_hole_tex = load("res://assets/shelter/textures/range_hole.png") as Texture2D
	if kind == Kind.PAPER:
		_sway = get_node_or_null("Sway") as Node3D
		_paper = get_node_or_null("Sway/Paper") as MeshInstance3D
		_prepare_sheet()
	else:
		_pose_mannequin()


## Лист — своя копия текстуры: пробоины одной мишени не появляются на соседних.
func _prepare_sheet() -> void:
	if _paper == null:
		return
	var mat: StandardMaterial3D = _paper.get_active_material(0) as StandardMaterial3D
	if mat == null or mat.albedo_texture == null:
		return
	var img: Image = mat.albedo_texture.get_image()
	if img == null:
		return
	if img.is_compressed():
		img.decompress()
	img.convert(Image.FORMAT_RGBA8)
	_clean = img
	_sheet = img.duplicate() as Image
	_sheet_tex = ImageTexture.create_from_image(_sheet)
	var own: StandardMaterial3D = mat.duplicate() as StandardMaterial3D
	own.albedo_texture = _sheet_tex
	_paper.material_override = own


## Манекен: тот же человек, что и персонажи, застывший в стойке, в матовом пластике без лица.
func _pose_mannequin() -> void:
	var model: Node3D = get_node_or_null("Persona") as Node3D
	if model == null:
		return
	var plastic: StandardMaterial3D = load("res://levels/shelter/materials/MannequinPlastic.tres") as StandardMaterial3D
	for n: Node in model.find_children("*", "MeshInstance3D", true, false):
		var mi: MeshInstance3D = n as MeshInstance3D
		var nm: String = String(mi.name).to_lower()
		# брови, борода, глаза и волосы у манекена не бывают
		if nm.contains("eye") or nm.contains("brow") or nm.contains("beard") or nm.contains("moustache") or nm.contains("hair") or nm.contains("lash") or nm.contains("teeth") or nm.contains("tongue"):
			mi.visible = false
			continue
		if plastic:
			mi.material_override = plastic
	var players: Array[Node] = model.find_children("*", "AnimationPlayer", true, false)
	var anim: AnimationPlayer
	if players.is_empty():
		anim = AnimationPlayer.new()
		anim.root_node = NodePath("..")
		model.add_child(anim)
	else:
		anim = players[0] as AnimationPlayer
	var clips: AnimationLibrary = load("res://assets/models/characters/persona_clips.res") as AnimationLibrary
	if clips == null:
		return
	if StringName("") in anim.get_animation_library_list():
		anim.remove_animation_library("")
	anim.add_animation_library("", clips)
	if anim.has_animation("unarmed_idle"):
		anim.play("unarmed_idle")
		anim.seek(0.4, true)
		anim.pause()


## Зовёт Hitscan стрелка: урон над точкой, качнуть лист, пробоина, рассылка точки.
func on_hit(point: Vector3, dir: Vector3, damage: float) -> void:
	var local: Vector3 = global_transform.affine_inverse() * point
	var head: bool = local.y >= head_height - 0.25
	var dmg: float = damage * (Balance.TARGET_HEAD_MULT if head else 1.0)
	_spawn_number(point, dmg, head)
	if kind == Kind.PAPER:
		# толчок по ходу пули относительно лица листа (+Z узла)
		var side: float = signf(dir.dot(global_basis.z)) if absf(dir.dot(global_basis.z)) > 0.05 else 1.0
		_swing_rate += side * float(Balance.RANGE.sway)
	add_hole(local)
	holed.emit(local)
	hit.emit(dmg, head)


## Пробоина в точке (локальные координаты мишени) — своя или пришедшая от напарника.
func add_hole(local: Vector3) -> void:
	if kind == Kind.PAPER:
		var uv: Vector2 = _paper_uv(local)
		if uv.x < 0.0 or uv.x > 1.0 or uv.y < 0.0 or uv.y > 1.0:
			return
		_holes.append(uv)
		if _holes.size() > int(Balance.RANGE.holes_max):
			_holes.remove_at(0)
			_redraw_sheet()
		else:
			_stamp(uv)
		_sheet_dirty = true
	else:
		_add_decal(local)


## Сменить лист / стереть следы с манекена.
func clear_holes() -> void:
	_holes.clear()
	if _sheet and _clean:
		_sheet.copy_from(_clean)
		_sheet_dirty = true
	for d: Decal in _decals:
		d.queue_free()
	_decals.clear()


func hole_count() -> int:
	return _holes.size() if kind == Kind.PAPER else _decals.size()


func _paper_uv(local: Vector3) -> Vector2:
	if _paper == null:
		return Vector2(-1, -1)
	# точка в осях листа: лист висит на подвесе и может быть качнут
	var p: Vector3 = _paper.transform.affine_inverse() * (_sway.transform.affine_inverse() * local)
	return Vector2(p.x / paper_size.x + 0.5, 1.0 - p.y / paper_size.y)


## Пробоина в бумаге: тёмное отверстие с рваной светлой кромкой.
func _stamp(uv: Vector2) -> void:
	if _sheet == null:
		return
	var w: int = _sheet.get_width()
	var h: int = _sheet.get_height()
	var r: float = float(Balance.RANGE.hole_size_m) * 0.5 / paper_size.x * float(w)
	var cx: float = uv.x * float(w)
	var cy: float = uv.y * float(h)
	var reach: int = int(ceil(r * 1.9))
	# у каждой пробоины своя рваность, но одинаковая у всех peer (от координат)
	var seed_angle: float = fposmod(uv.x * 97.31 + uv.y * 53.17, TAU)
	for y: int in range(maxi(0, int(cy) - reach), mini(h, int(cy) + reach + 1)):
		for x: int in range(maxi(0, int(cx) - reach), mini(w, int(cx) + reach + 1)):
			var dx: float = float(x) + 0.5 - cx
			var dy: float = float(y) + 0.5 - cy
			var d: float = sqrt(dx * dx + dy * dy)
			var a: float = atan2(dy, dx)
			var ragged: float = r * (1.0 + 0.22 * sin(a * 5.0 + seed_angle) + 0.12 * sin(a * 11.0 - seed_angle * 2.0))
			if d <= ragged * 0.72:
				_sheet.set_pixel(x, y, Color(0.03, 0.025, 0.02, 1.0))
			elif d <= ragged * 1.25:
				# задир бумаги вокруг — светлее и шероховатее
				var c: Color = _sheet.get_pixel(x, y)
				_sheet.set_pixel(x, y, c.lerp(Color(0.86, 0.83, 0.74, 1.0), 0.45))
			elif d <= ragged * 1.8:
				var c2: Color = _sheet.get_pixel(x, y)
				_sheet.set_pixel(x, y, c2.darkened(0.12))


func _redraw_sheet() -> void:
	if _sheet == null or _clean == null:
		return
	_sheet.copy_from(_clean)
	for uv: Vector2 in _holes:
		_stamp(uv)


func _add_decal(local: Vector3) -> void:
	var d: Decal = Decal.new()
	d.texture_albedo = _hole_tex
	var s: float = float(Balance.RANGE.hole_size_m) * 1.6
	d.size = Vector3(s, 0.12, s)
	d.cull_mask = 1
	add_child(d)
	d.position = local
	# проекция вдоль оси Y декали — поворачиваем её к оси мишени (+Z — лицо)
	d.rotation_degrees = Vector3(90, 0, 0)
	_decals.append(d)
	if _decals.size() > int(Balance.RANGE.holes_max) / 3:
		_decals.pop_front().queue_free()


func _physics_process(delta: float) -> void:
	if kind != Kind.PAPER or _sway == null:
		return
	var acc: float = -_swing_angle * float(Balance.RANGE.sway_spring) - _swing_rate * float(Balance.RANGE.sway_damp)
	_swing_rate += acc * delta
	_swing_angle = clampf(_swing_angle + _swing_rate * delta, -0.6, 0.6)
	_sway.rotation.x = _swing_angle


func _process(_delta: float) -> void:
	if _sheet_dirty and _sheet_tex:
		_sheet_tex.update(_sheet)
		_sheet_dirty = false
