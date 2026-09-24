class_name LightGlare
extends CanvasLayer
## Засвет от чужого фонаря: луч смотрит тебе в глаза — вокруг фонаря на экране ореол (гало) и
## лучики, весь кадр высветлен (вуаль), в ПНВ — вдвое сильнее. Источники — SpotLight3D в группе
## "glare_lights" (фонари на оружии, фонари мародёров); свой фонарь (meta "own" или на своём
## теле) не слепит. Стена между — не слепит. Только от первого лица: в изометрии камера — не глаза.
## Создаёт CameraRig.

const MAX_SPOTS := 6

var _veil: ColorRect
var _spots: Array[TextureRect] = []


func _ready() -> void:
	layer = 8
	var add := CanvasItemMaterial.new()
	add.blend_mode = CanvasItemMaterial.BLEND_MODE_ADD
	_veil = ColorRect.new()
	_veil.set_anchors_preset(Control.PRESET_FULL_RECT)
	_veil.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_veil.color = Color(0, 0, 0, 0)
	_veil.material = add
	add_child(_veil)
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.06, 0.22, 0.55, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 0.98, 0.92, 0.9), Color(1, 0.93, 0.8, 0.32), Color(0.9, 0.85, 0.75, 0.08), Color(0, 0, 0, 0)])
	var tex := GradientTexture2D.new()
	tex.gradient = g
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.5)
	tex.fill_to = Vector2(1.0, 0.5)
	tex.width = 256
	tex.height = 256
	for i in range(MAX_SPOTS):
		var t := TextureRect.new()
		t.texture = tex
		t.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		t.stretch_mode = TextureRect.STRETCH_SCALE
		t.mouse_filter = Control.MOUSE_FILTER_IGNORE
		t.material = add
		t.visible = false
		add_child(t)
		_spots.append(t)


## Каждый кадр: cam — камера глаз, me — свой игрок, first_person — вид из глаз, nvg — в ПНВ.
func tick(cam: Camera3D, me: Player, first_person: bool, nvg: bool, delta: float) -> void:
	var found: Array = []
	if first_person and cam and me:
		var eye := cam.global_position
		var fwd := -cam.global_basis.z
		var space := cam.get_world_3d().direct_space_state
		for n in cam.get_tree().get_nodes_in_group("glare_lights"):
			var l := n as SpotLight3D
			if l == null or not l.is_visible_in_tree() or l.has_meta("own") or me.is_ancestor_of(l):
				continue
			var to_eye := eye - l.global_position
			var d := to_eye.length()
			if d < 0.05 or d > l.spot_range:
				continue
			var dir := to_eye / d
			# насколько луч смотрит в глаза: внутри конуса, ярче к оси
			var cone := cos(deg_to_rad(l.spot_angle))
			var aim := smoothstep(cone, lerpf(cone, 1.0, 0.55), (-l.global_basis.z).dot(dir))
			# и насколько смотришь на фонарь ты
			var look := smoothstep(0.3, 0.95, fwd.dot(-dir))
			var k := aim * look * (1.0 - smoothstep(l.spot_range * 0.45, l.spot_range, d)) * clampf(8.0 / maxf(d, 1.0), 0.25, 1.0)
			if k < 0.02 or cam.is_position_behind(l.global_position):
				continue
			var q := PhysicsRayQueryParameters3D.create(eye, l.global_position, Hitscan.LAYER_WORLD | Hitscan.LAYER_DOOR)
			if not space.intersect_ray(q).is_empty():
				continue
			found.append([l, k, cam.unproject_position(l.global_position)])
	found.sort_custom(func(a: Array, b: Array) -> bool: return float(a[1]) > float(b[1]))
	var total := 0.0
	var vp := get_viewport().get_visible_rect().size
	for i in range(MAX_SPOTS):
		var t := _spots[i]
		if i >= found.size():
			t.visible = false
			continue
		var k := float(found[i][1]) * (2.0 if nvg else 1.0)
		total += k
		var s := vp.y * lerpf(0.12, 0.9, clampf(k, 0.0, 1.0))
		var p: Vector2 = found[i][2]
		t.visible = true
		t.size = Vector2(s, s)
		t.position = p - t.size * 0.5
		t.modulate = Color(1.0, 1.0, 1.0, clampf(k, 0.0, 1.0)) if not nvg else Color(0.6, 1.0, 0.6, clampf(k, 0.0, 1.0))
	# вуаль: весь кадр высветлен, плавно (глаз не мгновенно)
	var want := clampf(total * 0.3, 0.0, 0.45)
	var cur := _veil.color.a
	cur = move_toward(cur, want, delta * (4.0 if want > cur else 1.5))
	_veil.color = Color(0.9, 0.88, 0.82, cur) if not nvg else Color(0.5, 0.9, 0.5, cur)
