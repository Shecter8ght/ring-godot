extends Node
## Иконки предметов: модель каждого предмета (ItemModels) снимается ортокамерой в студии ItemStudio на прозрачном
## фоне в assets/icons/<id>.png — размер по клеткам предмета (ItemDb.size × PX). Оружие и обвесы —
## сбоку, дулом вправо; остальное — на три четверти сверху. После прогона — переимпорт:
## tools/godot.cmd --headless --import. Иконок нет — сетки рисуют цветной прямоугольник.
## godot --path . res://tools/icon_bake.tscn [-- id …]

const PX := 96
const OUT := "res://assets/icons"


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUT))
	var only := OS.get_cmdline_user_args()
	var ids: Array = []
	var items: Dictionary = (JSON.parse_string(FileAccess.get_file_as_string(ItemDb.ITEMS_PATH)) as Dictionary).get("items", {}).duplicate()
	# арсенал (data/weapons.json, armor.json) — те же иконки
	items.merge(WeaponDb.items())
	for id in items:
		# наклейки — свои иконки из рисунков (tools/sticker_icons), модель их не заменяет; по имени — можно
		if only.is_empty() and String(id).begins_with("sticker_"):
			continue
		if only.is_empty() or String(id) in only:
			ids.append(String(id))
	var n := 0
	for id in ids:
		await _bake(id)
		n += 1
	print("icon_bake: иконок %d → %s" % [n, OUT])
	get_tree().quit(0)


func _bake(id: String) -> void:
	var cells := ItemDb.size(id)
	var vp := SubViewport.new()
	vp.size = Vector2i(cells.x * PX, cells.y * PX)
	vp.transparent_bg = true
	vp.own_world_3d = true
	vp.msaa_3d = Viewport.MSAA_8X
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	ItemStudio.setup(vp)
	var model := ItemModels.build(id)
	vp.add_child(model)
	# фонарь и лазер обвесов в иконке не светят
	for l in model.find_children("*", "Light3D", true, false):
		(l as Light3D).visible = false
	for b in model.find_children("LaserBeam*", "Node3D", true, false):
		(b as Node3D).visible = false
	await get_tree().process_frame
	var cat := String(ItemDb.item(id).get("cat", ""))
	var side := cat in ["weapon", "mod"]
	var cam := Camera3D.new()
	cam.projection = Camera3D.PROJECTION_ORTHOGONAL
	cam.near = 0.01
	cam.far = 20.0
	vp.add_child(cam)
	var aabb := _aabb(model)
	var c := aabb.get_center()
	var dir := Vector3(-1.0, 0.1, 0.0).normalized() if side else Vector3(0.75, 0.95, 1.0).normalized()
	if id == Metka4Model.ID:
		dir = Vector3(-0.7, 1.2, 1.0).normalized()
	if id == DozorGear.MOUNT:
		dir = Vector3(-0.8, 0.5, 1.0).normalized()
	cam.look_at_from_position(c + dir * 3.0, c, Vector3.UP)
	# вписать: габарит в осях камеры, запас 8 %
	var inv := cam.global_transform.affine_inverse()
	var lo := Vector3(INF, INF, INF)
	var hi := -lo
	for i in range(8):
		var p := inv * aabb.get_endpoint(i)
		lo = lo.min(p)
		hi = hi.max(p)
	var ext := hi - lo
	var aspect := float(vp.size.x) / float(vp.size.y)
	cam.size = maxf(ext.y, ext.x / aspect) * 1.08
	var mid := (lo + hi) * 0.5
	cam.global_position = cam.global_transform * Vector3(mid.x, mid.y, 0.0)
	cam.current = true
	for i in range(4):
		await get_tree().process_frame
	var img := vp.get_texture().get_image()
	img.save_png(ProjectSettings.globalize_path("%s/%s.png" % [OUT, id]))
	vp.queue_free()
	await get_tree().process_frame


## Габарит всех мешей модели в мировых координатах.
func _aabb(root: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for n in root.find_children("*", "MeshInstance3D", true, false):
		var mi := n as MeshInstance3D
		if not mi.is_visible_in_tree() or mi.mesh == null:
			continue
		var box: AABB = mi.global_transform * mi.get_aabb()
		if first:
			out = box
			first = false
		else:
			out = out.merge(box)
	return out
