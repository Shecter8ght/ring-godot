@tool
extends EditorPlugin
## Кисть земли (решение владельца 2026-11-08: править карты руками в редакторе, docs/level_editing.md).
## Выбрать в дереве сцены узел Terrain (группа "blockout_terrain": «Санаторий», «Пригород»), включить кисть в панели
## «Кисть земли» справа и рисовать левой кнопкой мыши в окне 3D:
##   «Грунт» — грунты масок земли (у каждой карты свои: Terrain.brush_grounds);
##   «Трава» — убрать, густая трава, сорняки (карта густоты травы узла DistrictGrass в сцене);
##   «Высота» — поднять, опустить, сгладить, выровнять по высоте первой точки мазка;
##   «Растительность» — убрать или посадить кусты, подрост, папоротник, пни, коряги, камни (россыпи данными;
##   деревья — узлы TreeSpot, их двигают как дома).
## Shift + колесо — размер кисти. Ctrl+Z — отмена мазка. Ctrl+S — сохранить: маски и трава PNG, высоты .r32,
## растительность — её JSON.

const MODES: Array[String] = ["Грунт", "Трава", "Высота", "Растительность"]
const GRASS_OPS: Array[String] = ["Убрать траву", "Густая трава", "Сорняки"]
const HEIGHT_OPS: Array[String] = ["Поднять", "Опустить", "Сгладить", "Выровнять (по первой точке)"]
const VEG_OPS: Array[String] = ["Убрать", "Посадить"]
## Растительность по началу ключа россыпи → подпись в списке.
const VEG_GROUPS: Array = [
	["ug_bush", "Кусты"], ["ug_sapling", "Подрост"], ["forest_fern", "Папоротник"], ["forest_stump", "Пни"],
	["forest_dry_branches", "Ветки и коряги"], ["forest_dead_trunk", "Ветки и коряги"], ["forest_roots", "Ветки и коряги"],
	["forest_rocks", "Камни"],
]
const VEG_ALL: String = "Вся растительность"
## Сколько квадратных метров на одну посаженную вещь за движение мыши при силе 1.
const PLANT_M2: float = 10.0
const CURSOR_COLORS: Array[Color] = [Color(1.0, 0.6, 0.2), Color(0.35, 0.95, 0.35), Color(0.35, 0.7, 1.0), Color(0.85, 0.4, 0.9)]
## Доля силы за одно движение мыши (движений в секунду много — мазок набирается плавно).
const DAB: float = 0.35
## Подъём за одно движение при силе 1, м.
const RAISE_M: float = 0.12
## Как часто пересобирать плитки земли во время мазка высоты, с.
const REBUILD_SEC: float = 0.12
## Вид травы в редакторе: газон в траве — как издали в игре (Balance.GRASS: lawn_from / lawn_full, far_look).
const GRASS_LOOK: Dictionary = {"grass_density_from": 0.02, "grass_density_full": 0.22, "grass_far_start": 0.0,
	"grass_far_end": 0.01, "grass_far_tint": Vector3(2.75, 2.7, 2.85), "grass_far_flat": 0.6,
	"grass_far_clumps": Vector2(0.85, 1.12)}

var dock: VBoxContainer
var enabled_box: CheckButton
var mode_opt: OptionButton
var ground_opt: OptionButton
var grass_opt: OptionButton
var height_opt: OptionButton
var veg_opt: OptionButton
var veg_op_opt: OptionButton
var radius_slider: HSlider
var strength_slider: HSlider
var radius_label: Label
var strength_label: Label
var status_label: Label

var terrain: Node3D
var grass_node: Node
var grass_path: String = ""
var grass_image: Image
var grass_tex: ImageTexture
var cursor: MeshInstance3D
var cursor_mat: StandardMaterial3D
var painting: bool = false
var stroke_mode: int = 0
var stroke_before: Variant
var stroke_rect: Rect2
var flat_target: float = 0.0
var last_rebuild_ms: int = 0
var rebuild_pending: Rect2 = Rect2()
var dirty: Dictionary = {"heights": false, "splat": false, "grass": false, "veg": false}
## Растительность данными: файл → разобранный JSON; россыпи сцены по подписи группы.
var veg_data: Dictionary = {}
var veg_dirty_files: Dictionary = {}
var veg_rng: RandomNumberGenerator = RandomNumberGenerator.new()
## Щелчок по куску улицы, вещи, дереву выделяет его узел (pick_gizmo.gd).
var pick_gizmo: EditorNode3DGizmoPlugin


func _enter_tree() -> void:
	pick_gizmo = (load("res://addons/ring_level_tools/pick_gizmo.gd") as GDScript).new() as EditorNode3DGizmoPlugin
	add_node_3d_gizmo_plugin(pick_gizmo)
	dock = VBoxContainer.new()
	dock.name = "Кисть земли"
	enabled_box = CheckButton.new()
	enabled_box.text = "Кисть включена"
	dock.add_child(enabled_box)
	mode_opt = _option("Что рисовать", MODES)
	ground_opt = _option("Грунт", [])
	grass_opt = _option("Трава", GRASS_OPS)
	height_opt = _option("Высота", HEIGHT_OPS)
	veg_opt = _option("Растительность", [])
	veg_op_opt = _option("Действие", VEG_OPS)
	radius_label = Label.new()
	dock.add_child(radius_label)
	radius_slider = _slider(0.5, 30.0, 3.0, 0.5)
	strength_label = Label.new()
	dock.add_child(strength_label)
	strength_slider = _slider(0.05, 1.0, 0.5, 0.05)
	var save: Button = Button.new()
	save.text = "Сохранить землю сейчас"
	save.pressed.connect(_save_all)
	dock.add_child(save)
	status_label = Label.new()
	status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	status_label.custom_minimum_size = Vector2(200, 0)
	dock.add_child(status_label)
	var hint: Label = Label.new()
	hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	hint.custom_minimum_size = Vector2(200, 0)
	hint.text = "Выберите узел Terrain в дереве сцены и включите кисть. ЛКМ — рисовать, Shift + колесо — размер, " \
		+ "Ctrl+Z — отменить мазок, Ctrl+S — сохранить. Пока кисть включена, клик по земле не выделяет объекты — " \
		+ "выключите её, чтобы двигать дома и деревья."
	dock.add_child(hint)
	mode_opt.item_selected.connect(func(_i: int) -> void: _refresh_ui())
	radius_slider.value_changed.connect(func(_v: float) -> void: _refresh_ui())
	strength_slider.value_changed.connect(func(_v: float) -> void: _refresh_ui())
	add_control_to_dock(DOCK_SLOT_RIGHT_UL, dock)
	_refresh_ui()


func _exit_tree() -> void:
	remove_node_3d_gizmo_plugin(pick_gizmo)
	_drop_cursor()
	remove_control_from_docks(dock)
	dock.queue_free()


func _option(title: String, items: Array) -> OptionButton:
	var l: Label = Label.new()
	l.text = title
	dock.add_child(l)
	var o: OptionButton = OptionButton.new()
	for it: Variant in items:
		o.add_item(String(it))
	dock.add_child(o)
	return o


func _slider(lo: float, hi: float, value: float, step: float) -> HSlider:
	var s: HSlider = HSlider.new()
	s.min_value = lo
	s.max_value = hi
	s.step = step
	s.value = value
	dock.add_child(s)
	return s


func _show_option(o: OptionButton, on: bool) -> void:
	o.visible = on
	o.get_parent().get_child(o.get_index() - 1).visible = on


func _refresh_ui() -> void:
	var m: int = mode_opt.selected
	_show_option(ground_opt, m == 0)
	_show_option(grass_opt, m == 1)
	_show_option(height_opt, m == 2)
	_show_option(veg_opt, m == 3)
	_show_option(veg_op_opt, m == 3)
	radius_label.text = "Размер кисти: %.1f м" % radius_slider.value
	strength_label.text = "Сила: %d %%" % int(round(strength_slider.value * 100.0))
	if terrain == null:
		status_label.text = "Земля не выбрана."
	else:
		var unsaved: PackedStringArray = []
		var names: Dictionary = {"heights": "высоты", "splat": "грунт", "grass": "трава", "veg": "растительность"}
		for k: String in dirty:
			if bool(dirty[k]):
				unsaved.append(String(names[k]))
		status_label.text = "Земля: %s. %s" % [terrain.name,
			("Не сохранено: " + ", ".join(unsaved) + ".") if not unsaved.is_empty() else "Всё сохранено."]
	if cursor_mat:
		cursor_mat.albedo_color = CURSOR_COLORS[m]


# ---------------------------------------------------------------- выбор узла

func _handles(object: Object) -> bool:
	return object is Node3D and (object as Node).is_in_group("blockout_terrain") and object.has_method("brush_masks")


func _edit(object: Object) -> void:
	if object == null:
		_drop_cursor()
		return
	if object == terrain:
		return
	if terrain != null and is_instance_valid(terrain) and _any_dirty():
		_save_all()
	terrain = object as Node3D
	ground_opt.clear()
	for g: String in terrain.call("brush_grounds"):
		ground_opt.add_item(g)
	ground_opt.select(mini(4, ground_opt.item_count - 1) if ground_opt.item_count > 5 else mini(1, ground_opt.item_count - 1))
	_find_grass()
	_show_grass()
	_fill_veg_groups()
	_refresh_ui()


func _make_visible(visible: bool) -> void:
	if not visible:
		_drop_cursor()


## Трава: первый узел DistrictGrass сцены с картой густоты.
func _find_grass() -> void:
	grass_node = null
	grass_image = null
	grass_path = ""
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return
	for n: Node in [root] + root.find_children("*", "Node3D", true, false):
		if n is DistrictGrass and String(n.get("density_map")) != "":
			grass_node = n
			grass_path = String(n.get("density_map"))
			grass_image = Image.load_from_file(ProjectSettings.globalize_path(grass_path))
			if grass_image != null and grass_image.get_format() != Image.FORMAT_RGB8:
				grass_image.convert(Image.FORMAT_RGB8)
			return


## Трава в редакторе — видом газона «в траве» (как издали в игре), по карте густоты; правки кисти видны сразу.
func _show_grass() -> void:
	if terrain == null or grass_image == null or not terrain.has_method("set_far_grass"):
		return
	if grass_tex == null or Vector2i(grass_tex.get_size()) != grass_image.get_size():
		grass_tex = ImageTexture.create_from_image(grass_image)
	else:
		grass_tex.update(grass_image)
	var params: Dictionary = GRASS_LOOK.duplicate()
	params["grass_density"] = grass_tex
	params["grass_origin"] = grass_node.get("origin")
	params["grass_size"] = Vector2(grass_image.get_size())
	terrain.call("set_far_grass", params)


## Растительность данными в сцене: россыпи DistrictScatter не из узлов, по группам ключей.
func _veg_scatters() -> Array[Node]:
	var out: Array[Node] = []
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return out
	for n: Node in root.find_children("*", "Node3D", true, false):
		if n is DistrictScatter and not bool(n.get("from_nodes")) and String(n.get("data_path")) != "" \
				and String(n.get("key")) != "" and _veg_group(String(n.get("key"))) != "":
			out.append(n)
	return out


func _veg_group(key: String) -> String:
	for g: Array in VEG_GROUPS:
		if key.begins_with(String(g[0])):
			return String(g[1])
	return ""


func _fill_veg_groups() -> void:
	veg_opt.clear()
	var seen: Array[String] = []
	for s: Node in _veg_scatters():
		var g: String = _veg_group(String(s.get("key")))
		if not g in seen:
			seen.append(g)
	for g: String in seen:
		veg_opt.add_item(g)
	if not seen.is_empty():
		veg_opt.add_item(VEG_ALL)


# ---------------------------------------------------------------- мышь

func _forward_3d_gui_input(camera: Camera3D, event: InputEvent) -> int:
	if terrain == null or not enabled_box.button_pressed or not is_instance_valid(terrain):
		_drop_cursor()
		return AFTER_GUI_INPUT_PASS
	if event is InputEventMouseMotion:
		var hit: Vector3 = _hit(camera, (event as InputEventMouseMotion).position)
		_cursor_at(hit)
		if painting and hit != Vector3.INF:
			_dab(hit)
		return AFTER_GUI_INPUT_STOP if painting else AFTER_GUI_INPUT_PASS
	if event is InputEventMouseButton:
		var mb: InputEventMouseButton = event as InputEventMouseButton
		if mb.shift_pressed and mb.pressed and mb.button_index in [MOUSE_BUTTON_WHEEL_UP, MOUSE_BUTTON_WHEEL_DOWN]:
			var k: float = 1.12 if mb.button_index == MOUSE_BUTTON_WHEEL_UP else 1.0 / 1.12
			radius_slider.value = clampf(radius_slider.value * k, radius_slider.min_value, radius_slider.max_value)
			_cursor_at(_hit(camera, mb.position))
			return AFTER_GUI_INPUT_STOP
		if mb.button_index == MOUSE_BUTTON_LEFT:
			if mb.pressed:
				var hit2: Vector3 = _hit(camera, mb.position)
				if hit2 == Vector3.INF:
					return AFTER_GUI_INPUT_PASS
				_begin(hit2)
				_dab(hit2)
				return AFTER_GUI_INPUT_STOP
			if painting:
				_end()
				return AFTER_GUI_INPUT_STOP
	return AFTER_GUI_INPUT_PASS


## Точка земли под курсором: шаги по лучу, затем деление пополам (по карте высот, без физики).
func _hit(camera: Camera3D, pos: Vector2) -> Vector3:
	var from: Vector3 = camera.project_ray_origin(pos)
	var dir: Vector3 = camera.project_ray_normal(pos)
	var prev_t: float = 0.0
	if from.y - _h(from.x, from.z) <= 0.0:
		return Vector3.INF
	var t: float = 0.0
	while t < 4000.0:
		t += clampf(t * 0.01, 0.5, 4.0)
		var p: Vector3 = from + dir * t
		if p.y - _h(p.x, p.z) <= 0.0:
			var a: float = prev_t
			var b: float = t
			for i: int in range(14):
				var m: float = (a + b) * 0.5
				var q: Vector3 = from + dir * m
				if q.y - _h(q.x, q.z) > 0.0:
					a = m
				else:
					b = m
			var hit: Vector3 = from + dir * b
			return Vector3(hit.x, _h(hit.x, hit.z), hit.z)
		prev_t = t
	return Vector3.INF


func _h(x: float, z: float) -> float:
	return float(terrain.call("height_at", x, z))


func _cursor_at(hit: Vector3) -> void:
	if hit == Vector3.INF:
		if cursor:
			cursor.visible = false
		return
	if cursor == null or not is_instance_valid(cursor):
		cursor = MeshInstance3D.new()
		cursor.name = "_BrushCursor"
		cursor_mat = StandardMaterial3D.new()
		cursor_mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
		cursor_mat.no_depth_test = true
		cursor_mat.albedo_color = CURSOR_COLORS[mode_opt.selected]
		cursor.material_override = cursor_mat
		cursor.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		terrain.add_child(cursor)
	cursor.visible = true
	var im: ImmediateMesh = ImmediateMesh.new()
	im.surface_begin(Mesh.PRIMITIVE_LINE_STRIP)
	var r: float = radius_slider.value
	for k: int in range(49):
		var a: float = TAU * float(k) / 48.0
		var x: float = hit.x + cos(a) * r
		var z: float = hit.z + sin(a) * r
		im.surface_add_vertex(terrain.to_local(Vector3(x, _h(x, z) + 0.15, z)))
	im.surface_end()
	im.surface_begin(Mesh.PRIMITIVE_LINES)
	im.surface_add_vertex(terrain.to_local(hit))
	im.surface_add_vertex(terrain.to_local(hit + Vector3.UP * 1.5))
	im.surface_end()
	cursor.mesh = im


func _drop_cursor() -> void:
	if cursor and is_instance_valid(cursor):
		cursor.queue_free()
	cursor = null


# ---------------------------------------------------------------- мазок

func _begin(hit: Vector3) -> void:
	painting = true
	stroke_mode = mode_opt.selected
	stroke_before = _snapshot(stroke_mode)
	stroke_rect = Rect2(hit.x, hit.z, 0.0, 0.0)
	flat_target = hit.y


func _end() -> void:
	painting = false
	var area: Rect2 = stroke_rect.grow(radius_slider.value + 1.0)
	if stroke_mode == 2:
		_rebuild(area)
		_snap_trees(area)
	var after: Variant = _snapshot(stroke_mode)
	var ur: EditorUndoRedoManager = get_undo_redo()
	ur.create_action("Кисть земли — " + MODES[stroke_mode].to_lower(), UndoRedo.MERGE_DISABLE, terrain)
	ur.add_do_method(self, "_restore", stroke_mode, after, area)
	ur.add_undo_method(self, "_restore", stroke_mode, stroke_before, area)
	ur.commit_action(false)
	stroke_before = null
	EditorInterface.mark_scene_as_unsaved()
	_refresh_ui()


func _snapshot(mode: int) -> Variant:
	match mode:
		0:
			var copies: Array = []
			for img: Image in terrain.call("brush_masks"):
				copies.append(img.duplicate())
			return copies
		1:
			return grass_image.duplicate() if grass_image else null
		2:
			return (terrain.call("heights_data") as PackedFloat32Array).duplicate()
		_:
			var state: Dictionary = {}
			for s: Node in _veg_scatters():
				state[s] = (_veg_points(s) as Array).duplicate(true)
			return state


func _restore(mode: int, state: Variant, area: Rect2) -> void:
	if terrain == null or state == null:
		return
	match mode:
		0:
			var masks: Array = terrain.call("brush_masks")
			for i: int in range(mini(masks.size(), (state as Array).size())):
				(masks[i] as Image).copy_from(state[i] as Image)
			terrain.call("brush_push_masks")
			dirty.splat = true
		1:
			if grass_image:
				grass_image.copy_from(state as Image)
				_show_grass()
				dirty.grass = true
		2:
			terrain.call("set_heights_data", (state as PackedFloat32Array).duplicate())
			_rebuild(area)
			_snap_trees(area)
			dirty.heights = true
		_:
			for s: Variant in (state as Dictionary):
				if is_instance_valid(s):
					var list: Array = _veg_points(s as Node)
					list.clear()
					list.append_array((state[s] as Array).duplicate(true))
					_veg_mark(s as Node)
					_veg_refresh(s as Node)
			dirty.veg = true
	_refresh_ui()


## Одно движение мыши: клетки карты в круге кисти, сила спадает к краю.
func _dab(hit: Vector3) -> void:
	var r: float = radius_slider.value
	stroke_rect = stroke_rect.expand(Vector2(hit.x - r, hit.z - r)).expand(Vector2(hit.x + r, hit.z + r))
	if stroke_mode == 3:
		_paint_veg(hit, r)
		return
	var step: float = float(terrain.call("cell_step"))
	var origin: Vector2 = terrain.call("cell_origin")
	var cells: Vector2i = terrain.call("cells")
	var ci: float = (hit.x - origin.x) / step
	var cj: float = (hit.z - origin.y) / step
	var rc: float = r / step
	var i0: int = maxi(0, int(floor(ci - rc)))
	var i1: int = mini(cells.x - 1, int(ceil(ci + rc)))
	var j0: int = maxi(0, int(floor(cj - rc)))
	var j1: int = mini(cells.y - 1, int(ceil(cj + rc)))
	if i0 > i1 or j0 > j1:
		return
	var s: float = strength_slider.value * DAB
	match stroke_mode:
		0:
			_paint_ground(i0, i1, j0, j1, ci, cj, rc, s, cells)
		1:
			_paint_grass(i0, i1, j0, j1, ci, cj, rc, s, cells)
		_:
			_paint_height(i0, i1, j0, j1, ci, cj, rc, s, cells, hit, r)


func _falloff(i: int, j: int, ci: float, cj: float, rc: float) -> float:
	var d: float = Vector2(float(i) - ci, float(j) - cj).length() / maxf(rc, 0.001)
	if d >= 1.0:
		return 0.0
	var f: float = 1.0 - d
	return f * f * (3.0 - 2.0 * f)


## Грунт: каналы всех масок подряд (0 — основа, все вниз; k — свой канал вверх, остальные вниз).
func _paint_ground(i0: int, i1: int, j0: int, j1: int, ci: float, cj: float, rc: float, s: float, cells: Vector2i) -> void:
	var masks: Array = terrain.call("brush_masks")
	var channels: PackedInt32Array = terrain.call("brush_mask_channels")
	if masks.is_empty():
		return
	var target: int = ground_opt.selected
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var w: float = _falloff(i, j, ci, cj, rc) * s
			if w <= 0.0:
				continue
			var k: int = 0
			for mi: int in range(masks.size()):
				var img: Image = masks[mi]
				var px: Vector2i = Vector2i(i * img.get_width() / cells.x, j * img.get_height() / cells.y)
				var c: Color = img.get_pixelv(px)
				for ch: int in range(channels[mi] if mi < channels.size() else 4):
					k += 1
					c[ch] = lerpf(c[ch], 1.0 if k == target else 0.0, w)
				img.set_pixelv(px, c)
	dirty.splat = true
	terrain.call("brush_push_masks")


func _paint_grass(i0: int, i1: int, j0: int, j1: int, ci: float, cj: float, rc: float, s: float, cells: Vector2i) -> void:
	if grass_image == null:
		return
	var op: int = grass_opt.selected
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var w: float = _falloff(i, j, ci, cj, rc) * s
			if w <= 0.0:
				continue
			var p: Vector2i = Vector2i(i * grass_image.get_width() / cells.x, j * grass_image.get_height() / cells.y)
			var c: Color = grass_image.get_pixelv(p)
			match op:
				0:
					c = Color(c.r * (1.0 - w), c.g * (1.0 - w), c.b * (1.0 - w), c.a)
				1:
					c.r = lerpf(c.r, 1.0, w)
				_:
					c.g = lerpf(c.g, 1.0, w)
			grass_image.set_pixelv(p, c)
	dirty.grass = true
	_show_grass()


func _paint_height(i0: int, i1: int, j0: int, j1: int, ci: float, cj: float, rc: float, s: float, cells: Vector2i,
		hit: Vector3, r: float) -> void:
	var data: PackedFloat32Array = (terrain.call("heights_data") as PackedFloat32Array).duplicate()
	var src: PackedFloat32Array = data.duplicate()
	var op: int = height_opt.selected
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var w: float = _falloff(i, j, ci, cj, rc) * s
			if w <= 0.0:
				continue
			var idx: int = j * cells.x + i
			match op:
				0:
					data[idx] = src[idx] + RAISE_M * w / DAB
				1:
					data[idx] = src[idx] - RAISE_M * w / DAB
				2:
					var sum: float = 0.0
					var n: int = 0
					for dj: int in range(-1, 2):
						for di: int in range(-1, 2):
							var ii: int = clampi(i + di, 0, cells.x - 1)
							var jj: int = clampi(j + dj, 0, cells.y - 1)
							sum += src[jj * cells.x + ii]
							n += 1
					data[idx] = lerpf(src[idx], sum / float(n), w)
				_:
					data[idx] = lerpf(src[idx], flat_target, w)
	terrain.call("set_heights_data", data)
	dirty.heights = true
	var area: Rect2 = Rect2(hit.x - r, hit.z - r, r * 2.0, r * 2.0)
	rebuild_pending = area if rebuild_pending.size == Vector2.ZERO else rebuild_pending.merge(area)
	if Time.get_ticks_msec() - last_rebuild_ms > int(REBUILD_SEC * 1000.0):
		_rebuild(rebuild_pending)


func _rebuild(area: Rect2) -> void:
	if terrain.has_method("rebuild_area"):
		terrain.call("rebuild_area", area)
	rebuild_pending = Rect2()
	last_rebuild_ms = Time.get_ticks_msec()


## Деревья (TreeSpot) в прямоугольнике — снова на землю после правки высот.
func _snap_trees(area: Rect2) -> void:
	var root: Node = EditorInterface.get_edited_scene_root()
	if root == null:
		return
	for n: Node in get_tree().get_nodes_in_group("tree_spot"):
		if not root.is_ancestor_of(n) or not bool(n.get("on_ground")):
			continue
		var p: Vector3 = (n as Node3D).global_position
		if area.has_point(Vector2(p.x, p.z)):
			n.call("_snap")


# ---------------------------------------------------------------- растительность данными

## Список точек россыпи (тот же массив, что в разобранном JSON её файла — правка сразу в данных).
func _veg_points(s: Node) -> Array:
	var path: String = String(s.get("data_path"))
	if not veg_data.has(path):
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
		veg_data[path] = parsed if parsed is Dictionary else {}
	var data: Dictionary = veg_data[path]
	var key: String = String(s.get("key"))
	if not data.has(key):
		data[key] = []
	return data[key]


func _veg_mark(s: Node) -> void:
	veg_dirty_files[String(s.get("data_path"))] = true


func _veg_refresh(s: Node) -> void:
	s.set("points_override", _veg_points(s))
	s.set("use_override", true)
	s.call("_build")


## Точки россыпи в её координатах: мировые или от корня её сцены (local_points — готовые куски на новом месте).
func _veg_frame(s: Node) -> Transform3D:
	if bool(s.get("local_points")):
		var frame: Node3D = s.owner as Node3D if s.owner is Node3D else (s as Node3D).get_parent_node_3d()
		if frame:
			return frame.global_transform
	return Transform3D.IDENTITY


func _paint_veg(hit: Vector3, r: float) -> void:
	var group: String = veg_opt.get_item_text(veg_opt.selected) if veg_opt.selected >= 0 else ""
	if group == "":
		return
	var targets: Array[Node] = []
	for s: Node in _veg_scatters():
		if group == VEG_ALL or _veg_group(String(s.get("key"))) == group:
			targets.append(s)
	if targets.is_empty():
		return
	var strength: float = strength_slider.value
	if veg_op_opt.selected == 0:
		for s: Node in targets:
			var frame: Transform3D = _veg_frame(s)
			var list: Array = _veg_points(s)
			var keep: Array = []
			var removed: bool = false
			for p: Array in list:
				var w: Vector3 = frame * Vector3(float(p[0]), float(p[1]), float(p[2]))
				if Vector2(w.x - hit.x, w.z - hit.z).length() < r and veg_rng.randf() < strength:
					removed = true
					continue
				keep.append(p)
			if removed:
				list.clear()
				list.append_array(keep)
				_veg_mark(s)
				_veg_refresh(s)
		dirty.veg = true
		return
	# посадить: случайно в круге, порода — случайная из выбранной группы, высота — по земле
	var n: int = maxi(1, int(round(strength * PI * r * r / PLANT_M2 * DAB)))
	var touched: Dictionary = {}
	for k: int in range(n):
		var a: float = veg_rng.randf() * TAU
		var d: float = sqrt(veg_rng.randf()) * r
		var x: float = hit.x + cos(a) * d
		var z: float = hit.z + sin(a) * d
		var s: Node = targets[veg_rng.randi() % targets.size()]
		var local: Vector3 = _veg_frame(s).affine_inverse() * Vector3(x, _h(x, z), z)
		_veg_points(s).append([snappedf(local.x, 0.01), snappedf(local.y, 0.01), snappedf(local.z, 0.01),
			snappedf(veg_rng.randf() * 360.0, 0.1), snappedf(veg_rng.randf_range(0.8, 1.2), 0.01)])
		touched[s] = true
	for s: Variant in touched:
		_veg_mark(s as Node)
		_veg_refresh(s as Node)
	dirty.veg = true


# ---------------------------------------------------------------- сохранение

func _any_dirty() -> bool:
	for k: String in dirty:
		if bool(dirty[k]):
			return true
	return false


func _save_external_data() -> void:
	if terrain != null and is_instance_valid(terrain) and _any_dirty():
		_save_all()


func _save_all() -> void:
	if terrain == null or not is_instance_valid(terrain):
		return
	var reimport: PackedStringArray = []
	if bool(dirty.heights) and String(terrain.call("heights_path")) != "":
		var f: FileAccess = FileAccess.open(ProjectSettings.globalize_path(String(terrain.call("heights_path"))), FileAccess.WRITE)
		f.store_buffer((terrain.call("heights_for_save") as PackedFloat32Array).to_byte_array())
		f.close()
		dirty.heights = false
	if bool(dirty.splat):
		var masks: Array = terrain.call("brush_masks")
		var paths: PackedStringArray = terrain.call("brush_mask_paths")
		for i: int in range(mini(masks.size(), paths.size())):
			if paths[i] != "":
				(masks[i] as Image).save_png(ProjectSettings.globalize_path(paths[i]))
				reimport.append(paths[i])
		dirty.splat = false
	if bool(dirty.grass) and grass_image and grass_path != "":
		grass_image.save_png(ProjectSettings.globalize_path(grass_path))
		reimport.append(grass_path)
		dirty.grass = false
	if bool(dirty.veg):
		for path: String in veg_dirty_files:
			var f2: FileAccess = FileAccess.open(path, FileAccess.WRITE)
			f2.store_string(JSON.stringify(veg_data[path], "", false) + "\n")
			f2.close()
		veg_dirty_files.clear()
		dirty.veg = false
	var fs: EditorFileSystem = EditorInterface.get_resource_filesystem()
	for p: String in reimport:
		if FileAccess.file_exists(p + ".import"):
			fs.reimport_files(PackedStringArray([p]))
	_refresh_ui()
