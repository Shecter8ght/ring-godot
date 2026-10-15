class_name GrassBlades
extends RefCounted
## Сетка «куртины» густого яруса травы: квадрат patch×patch м с травинками, собранными в кочки.
## Травинка — узкая лента из segments звеньев (без прозрачности: видеокарта не перерисует пиксели
## по многу раз, как у карточек-сканов), сужается к острию, изогнута в свою сторону.
## Данные вершин для шейдера grass_blades: UV — поперёк/вдоль травинки, UV2 — её корень (xz куртины),
## COLOR — r своя вариация, g высота травинки, м, b фаза ветра, a склонность к сухости; TANGENT — ширина.


## blades — сколько травинок; segments — звеньев у травинки; width_k — множитель ширины (дальний
## ярус реже и шире, чтобы издали поле было таким же плотным); height — травинки, м (мин, макс);
## thatch — доля полёглых сухих травинок.
static func patch_mesh(seed_value: int, blades: int, segments: int, patch: float, width_k: float, height: Vector2, thatch: float) -> ArrayMesh:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value
	var verts := PackedVector3Array()
	var normals := PackedVector3Array()
	var tangents := PackedFloat32Array()
	var colors := PackedColorArray()
	var uvs := PackedVector2Array()
	var uv2s := PackedVector2Array()
	var index := PackedInt32Array()
	var half := patch * 0.5
	# кочки: травинки растут пучками, между ними — реже
	var tufts: Array[Vector3] = []
	for i in range(rng.randi_range(4, 7)):
		tufts.append(Vector3(rng.randf_range(-half, half), rng.randf_range(0.05, 0.13), rng.randf_range(-half, half)))
	for b in range(blades):
		var root: Vector2
		if rng.randf() < 0.62:
			var t: Vector3 = tufts[rng.randi() % tufts.size()]
			var a := rng.randf() * TAU
			var r := absf(rng.randfn(0.0, t.y))
			root = Vector2(t.x + cos(a) * r, t.z + sin(a) * r)
		else:
			root = Vector2(rng.randf_range(-half, half), rng.randf_range(-half, half))
		root.x = clampf(root.x, -half, half)
		root.y = clampf(root.y, -half, half)
		var h := rng.randf_range(height.x, height.y)
		var w := rng.randf_range(0.009, 0.0165) * width_k
		var lean := h * rng.randf_range(0.1, 0.55)
		var dry := rng.randf()
		# часть травинок — прошлогодняя полёглая солома («войлок»): низко, почти плашмя, сухая;
		# закрывает землю между стеблями, если смотреть сверху
		if rng.randf() < thatch:
			h = rng.randf_range(height.x * 0.7, height.x + (height.y - height.x) * 0.45)
			lean = h * rng.randf_range(0.78, 0.95)
			w *= 1.25
			dry = rng.randf_range(0.85, 1.0)
		var yaw := rng.randf() * TAU
		var lean_a := rng.randf() * TAU
		var lean_dir := Vector3(cos(lean_a), 0.0, sin(lean_a))
		var across := Vector3(cos(yaw), 0.0, sin(yaw))
		# лежащая лента — плашмя: ширина поперёк направления наклона
		if lean > h * 0.7:
			across = Vector3(-lean_dir.z, 0.0, lean_dir.x)
		var face := across.cross(Vector3.UP).normalized()
		var col := Color(rng.randf(), h, rng.randf(), dry)
		var base := verts.size()
		for s in range(segments + 1):
			var f := float(s) / float(segments)
			# дуга: верх уходит вбок квадратично, высота чуть теряется на наклоне
			var c := Vector3(root.x, 0.0, root.y) + lean_dir * lean * f * f + Vector3.UP * h * f * (1.0 - 0.18 * (lean / h) * f)
			var half_w := w * 0.5 * (1.0 - pow(f, 1.35)) + 0.0004
			for side: float in [-1.0, 1.0]:
				verts.append(c + across * half_w * side)
				# лента повёрнута лицом чуть вверх по ходу изгиба
				var n := (face + lean_dir * 0.25 * f + Vector3.UP * 0.15).normalized()
				normals.append(n)
				tangents.append_array(PackedFloat32Array([across.x, across.y, across.z, 1.0]))
				colors.append(col)
				uvs.append(Vector2(0.0 if side < 0.0 else 1.0, f))
				uv2s.append(root)
		for s in range(segments):
			var i0 := base + s * 2
			index.append_array(PackedInt32Array([i0, i0 + 2, i0 + 1, i0 + 1, i0 + 2, i0 + 3]))
	var arrays: Array = []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = normals
	arrays[Mesh.ARRAY_TANGENT] = tangents
	arrays[Mesh.ARRAY_COLOR] = colors
	arrays[Mesh.ARRAY_TEX_UV] = uvs
	arrays[Mesh.ARRAY_TEX_UV2] = uv2s
	arrays[Mesh.ARRAY_INDEX] = index
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	# изгиб ветром и примятие уводят вершины за пределы покоя — запас рамки, чтобы не отсекало
	mesh.custom_aabb = AABB(Vector3(-half - height.y, -0.05, -half - height.y), Vector3(patch + height.y * 2.0, height.y * 1.6, patch + height.y * 2.0))
	return mesh
