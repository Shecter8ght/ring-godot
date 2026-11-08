@tool
extends EditorPlugin
## Кисть земли (решение владельца 2026-11-08: править карты руками в редакторе, docs/level_editing.md).
## Выбрать в дереве сцены узел Terrain (группа "blockout_terrain": рельеф из карты высот — «Санаторий»), включить
## кисть в панели «Кисть земли» справа и рисовать левой кнопкой мыши в окне 3D:
##   «Грунт» — газон, вытоптанный газон, хвоя, мох, тропа (грунтовка), гранит, щебень, песок (маски splat / splat2);
##   «Трава» — убрать, густая трава, сорняки (карта густоты травы узла Grass);
##   «Высота» — поднять, опустить, сгладить, выровнять по высоте первой точки мазка.
## Shift + колесо — размер кисти. Ctrl+Z — отмена мазка. Ctrl+S — сохранить: PNG масок и травы, карта высот .r32.

const MODES: Array[String] = ["Грунт", "Трава", "Высота"]
const GROUNDS: Array[String] = ["Газон", "Вытоптанный газон", "Хвоя", "Мох", "Тропа, грунтовка", "Гранит", "Щебень", "Песок"]
const GRASS_OPS: Array[String] = ["Убрать траву", "Густая трава", "Сорняки"]
const HEIGHT_OPS: Array[String] = ["Поднять", "Опустить", "Сгладить", "Выровнять (по первой точке)"]
const CURSOR_COLORS: Array[Color] = [Color(1.0, 0.6, 0.2), Color(0.35, 0.95, 0.35), Color(0.35, 0.7, 1.0)]
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
var splat_tex: ImageTexture
var splat2_tex: ImageTexture
var tex_material: Material
var cursor: MeshInstance3D
var cursor_mat: StandardMaterial3D
var painting: bool = false
var stroke_mode: int = 0
var stroke_before: Variant
var stroke_rect: Rect2
var flat_target: float = 0.0
var last_rebuild_ms: int = 0
var rebuild_pending: Rect2 = Rect2()
var dirty: Dictionary = {"heights": false, "splat": false, "grass": false}


func _enter_tree() -> void:
	dock = VBoxContainer.new()
	dock.name = "Кисть земли"
	enabled_box = CheckButton.new()
	enabled_box.text = "Кисть включена"
	dock.add_child(enabled_box)
	mode_opt = _option("Что рисовать", MODES)
	ground_opt = _option("Грунт", GROUNDS)
	ground_opt.select(4)
	grass_opt = _option("Трава", GRASS_OPS)
	height_opt = _option("Высота", HEIGHT_OPS)
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
	_drop_cursor()
	remove_control_from_docks(dock)
	dock.queue_free()


func _option(title: String, items: Array[String]) -> OptionButton:
	var l: Label = Label.new()
	l.text = title
	dock.add_child(l)
	var o: OptionButton = OptionButton.new()
	for it: String in items:
		o.add_item(it)
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


func _refresh_ui() -> void:
	var m: int = mode_opt.selected
	ground_opt.get_parent().get_child(ground_opt.get_index() - 1).visible = m == 0
	ground_opt.visible = m == 0
	grass_opt.get_parent().get_child(grass_opt.get_index() - 1).visible = m == 1
	grass_opt.visible = m == 1
	height_opt.get_parent().get_child(height_opt.get_index() - 1).visible = m == 2
	height_opt.visible = m == 2
	radius_label.text = "Размер кисти: %.1f м" % radius_slider.value
	strength_label.text = "Сила: %d %%" % int(round(strength_slider.value * 100.0))
	if terrain == null:
		status_label.text = "Земля не выбрана."
	else:
		var unsaved: PackedStringArray = []
		for k: String in dirty:
			if bool(dirty[k]):
				unsaved.append({"heights": "высоты", "splat": "грунт", "grass": "трава"}[k])
		status_label.text = "Земля: %s. %s" % [terrain.name,
			("Не сохранено: " + ", ".join(unsaved) + ".") if not unsaved.is_empty() else "Всё сохранено."]
	if cursor_mat:
		cursor_mat.albedo_color = CURSOR_COLORS[m]


# ---------------------------------------------------------------- выбор узла

func _handles(object: Object) -> bool:
	return object is Node3D and (object as Node).is_in_group("blockout_terrain") and object.has_method("heights_data")


func _edit(object: Object) -> void:
	if object == null:
		_drop_cursor()
		return
	if object == terrain:
		return
	if terrain != null and _any_dirty():
		_save_all()
	terrain = object as Node3D
	grass_node = terrain.get_parent().get_node_or_null("Grass") if terrain.get_parent() else null
	grass_image = null
	grass_path = ""
	if grass_node != null and String(grass_node.get("density_map")) != "":
		grass_path = String(grass_node.get("density_map"))
		grass_image = Image.load_from_file(ProjectSettings.globalize_path(grass_path))
	_show_grass()
	_refresh_ui()


func _make_visible(visible: bool) -> void:
	if not visible:
		_drop_cursor()


## Трава в редакторе — видом газона «в траве» (как издали в игре), по карте густоты; правки кисти видны сразу.
func _show_grass() -> void:
	if terrain == null or grass_image == null or not terrain.has_method("set_far_grass"):
		return
	if grass_tex == null or grass_tex.get_size() != Vector2(grass_image.get_size()):
		grass_tex = ImageTexture.create_from_image(grass_image)
	else:
		grass_tex.update(grass_image)
	var params: Dictionary = GRASS_LOOK.duplicate()
	params["grass_density"] = grass_tex
	params["grass_origin"] = grass_node.get("origin")
	params["grass_size"] = Vector2(grass_image.get_size())
	terrain.call("set_far_grass", params)


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
	var prev_d: float = from.y - _h(from.x, from.z)
	if prev_d <= 0.0:
		return Vector3.INF
	var t: float = 0.0
	while t < 4000.0:
		t += clampf(t * 0.01, 0.5, 4.0)
		var p: Vector3 = from + dir * t
		var d: float = p.y - _h(p.x, p.z)
		if d <= 0.0:
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
		prev_d = d
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
	if stroke_mode == 2:
		_rebuild(stroke_rect.grow(radius_slider.value + 1.0))
		_snap_trees(stroke_rect.grow(radius_slider.value + 1.0))
	var after: Variant = _snapshot(stroke_mode)
	var ur: EditorUndoRedoManager = get_undo_redo()
	ur.create_action("Кисть земли — " + MODES[stroke_mode].to_lower(), UndoRedo.MERGE_DISABLE, terrain)
	ur.add_do_method(self, "_restore", stroke_mode, after, stroke_rect.grow(radius_slider.value + 1.0))
	ur.add_undo_method(self, "_restore", stroke_mode, stroke_before, stroke_rect.grow(radius_slider.value + 1.0))
	ur.commit_action(false)
	stroke_before = null
	EditorInterface.mark_scene_as_unsaved()
	_refresh_ui()


func _snapshot(mode: int) -> Variant:
	match mode:
		0:
			var a: Image = terrain.get("_splat") as Image
			var b: Image = terrain.get("_splat2") as Image
			return [a.duplicate() if a else null, b.duplicate() if b else null]
		1:
			return grass_image.duplicate() if grass_image else null
		_:
			return (terrain.call("heights_data") as PackedFloat32Array).duplicate()


func _restore(mode: int, state: Variant, area: Rect2) -> void:
	if terrain == null or state == null:
		return
	match mode:
		0:
			var a: Image = terrain.get("_splat") as Image
			var b: Image = terrain.get("_splat2") as Image
			if a and state[0]:
				a.copy_from(state[0] as Image)
			if b and state[1]:
				b.copy_from(state[1] as Image)
			_push_splat()
			dirty.splat = true
		1:
			if grass_image:
				grass_image.copy_from(state as Image)
				_show_grass()
				dirty.grass = true
		_:
			terrain.call("set_heights_data", (state as PackedFloat32Array).duplicate())
			_rebuild(area)
			_snap_trees(area)
			dirty.heights = true
	_refresh_ui()


## Одно движение мыши: клетки карты в круге кисти, сила спадает к краю.
func _dab(hit: Vector3) -> void:
	var r: float = radius_slider.value
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
	stroke_rect = stroke_rect.expand(Vector2(hit.x - r, hit.z - r)).expand(Vector2(hit.x + r, hit.z + r))
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


func _paint_ground(i0: int, i1: int, j0: int, j1: int, ci: float, cj: float, rc: float, s: float, cells: Vector2i) -> void:
	var a: Image = terrain.get("_splat") as Image
	var b: Image = terrain.get("_splat2") as Image
	if a == null:
		return
	var target: int = ground_opt.selected      # 0 — газон (все маски вниз), 1…7 — свой канал
	for j: int in range(j0, j1 + 1):
		for i: int in range(i0, i1 + 1):
			var w: float = _falloff(i, j, ci, cj, rc) * s
			if w <= 0.0:
				continue
			var pa: Vector2i = Vector2i(i * a.get_width() / cells.x, j * a.get_height() / cells.y)
			var ca: Color = a.get_pixelv(pa)
			var cb: Color = b.get_pixelv(pa) if b else Color(0, 0, 0, 0)
			var v: Array[float] = [ca.r, ca.g, ca.b, ca.a, cb.r, cb.g, cb.b]
			for k: int in range(7):
				v[k] = lerpf(v[k], 1.0 if k + 1 == target else 0.0, w)
			a.set_pixelv(pa, Color(v[0], v[1], v[2], v[3]))
			if b:
				b.set_pixelv(pa, Color(v[4], v[5], v[6], cb.a))
	dirty.splat = true
	_push_splat()


func _push_splat() -> void:
	var mat: Material = terrain.get("_material") as Material
	var a: Image = terrain.get("_splat") as Image
	var b: Image = terrain.get("_splat2") as Image
	if mat == null or a == null:
		return
	if tex_material != mat or splat_tex == null:
		splat_tex = ImageTexture.create_from_image(a)
		splat2_tex = ImageTexture.create_from_image(b) if b else null
		tex_material = mat
		(mat as ShaderMaterial).set_shader_parameter("splat", splat_tex)
		if splat2_tex:
			(mat as ShaderMaterial).set_shader_parameter("splat2", splat2_tex)
		return
	splat_tex.update(a)
	if splat2_tex and b:
		splat2_tex.update(b)


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
	var data: PackedFloat32Array = terrain.call("heights_data")
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
	for n: Node in root.find_children("*", "Node3D", true, false):
		if n.has_method("ground_y") and bool(n.get("on_ground")):
			var p: Vector3 = (n as Node3D).global_position
			if area.has_point(Vector2(p.x, p.z)):
				n.call("_snap")


# ---------------------------------------------------------------- сохранение

func _any_dirty() -> bool:
	return bool(dirty.heights) or bool(dirty.splat) or bool(dirty.grass)


func _save_external_data() -> void:
	if terrain != null and is_instance_valid(terrain) and _any_dirty():
		_save_all()


func _save_all() -> void:
	if terrain == null or not is_instance_valid(terrain):
		return
	var cfg: Variant = JSON.parse_string(FileAccess.get_file_as_string(String(terrain.get("data_path"))))
	var t: Dictionary = (cfg as Dictionary).get("terrain", {}) if cfg is Dictionary else {}
	var reimport: PackedStringArray = []
	if bool(dirty.heights) and String(t.get("heights", "")) != "":
		var f: FileAccess = FileAccess.open(ProjectSettings.globalize_path(String(t.heights)), FileAccess.WRITE)
		f.store_buffer((terrain.call("heights_data") as PackedFloat32Array).to_byte_array())
		f.close()
		dirty.heights = false
	if bool(dirty.splat):
		for pair: Array in [["splat_file", "_splat"], ["splat2_file", "_splat2"]]:
			var path: String = String(t.get(pair[0], ""))
			var img: Image = terrain.get(pair[1]) as Image
			if path != "" and img:
				img.save_png(ProjectSettings.globalize_path(path))
				reimport.append(path)
		dirty.splat = false
	if bool(dirty.grass) and grass_image and grass_path != "":
		grass_image.save_png(ProjectSettings.globalize_path(grass_path))
		reimport.append(grass_path)
		dirty.grass = false
	if not reimport.is_empty():
		EditorInterface.get_resource_filesystem().reimport_files(reimport)
	_refresh_ui()
