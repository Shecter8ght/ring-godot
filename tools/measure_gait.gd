extends SceneTree
## Шаг клипов передвижения Persona: с какой скоростью и куда идёт тело (м/с, в осях модели: +Z —
## вперёд, +X — влево), сколько полных шагов (левая + правая) в клипе и когда левая ступня встаёт на
## землю. CharacterAnimator по этим числам ставит клипы направлений в одну фазу шага (все с левой
## ноги) и крутит их со скоростью, при которой ступни не скользят.
## Перемерять после запекания клипов: godot --headless -s res://tools/measure_gait.gd
## → data/character_gait.json

const MODEL := "res://assets/models/characters/persona_animated.glb"
const CLIPS := "res://assets/models/characters/persona_clips.res"
const OUTPUT := "res://data/character_gait.json"
const SAMPLES := 240
## Опора — ступня не выше самой низкой своей точки за клип больше чем на столько (м) и едет назад.
const STANCE_BAND := 0.07
## Опора или перенос короче этой доли клипа — дрожь замера, а не шаг.
const MIN_PHASE := 0.1


func _initialize() -> void:
	# кости в осях мира — только когда узлы уже в дереве сцены: замер с первого кадра
	process_frame.connect(_measure, CONNECT_ONE_SHOT)


func _measure() -> void:
	var root: Node3D = (load(MODEL) as PackedScene).instantiate() as Node3D
	get_root().add_child(root)
	var sk: Skeleton3D = root.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	var lib: AnimationLibrary = load(CLIPS) as AnimationLibrary
	var player := AnimationPlayer.new()
	root.add_child(player)
	player.root_node = NodePath("..")
	player.add_animation_library("", lib)
	var out: Dictionary = {}
	var names: Array = Array(lib.get_animation_list())
	names.sort()
	for clip_name: StringName in names:
		var name := String(clip_name)
		if not _is_locomotion(name):
			continue
		var anim: Animation = lib.get_animation(clip_name)
		var length: float = anim.length
		var feet: Dictionary = {"L": [], "R": []}
		player.play(clip_name)
		for i in range(SAMPLES):
			player.seek(length * float(i) / float(SAMPLES), true)
			(feet.L as Array).append(_bone(sk, "mixamorig_LeftFoot"))
			(feet.R as Array).append(_bone(sk, "mixamorig_RightFoot"))
		player.stop()
		var dt: float = length / float(SAMPLES)
		# Опора — ступня низко и едет назад относительно тела. Только по высоте нельзя: в некоторых
		# клипах нога при переносе идёт почти над землёй и «опора» по высоте её захватывала.
		var lows: Dictionary = {}
		var speeds: Dictionary = {}
		var guess := Vector2.ZERO
		for side: String in ["L", "R"]:
			var pts: Array = feet[side]
			var low: float = INF
			for p: Vector3 in pts:
				low = minf(low, p.y)
			lows[side] = low
			var u: Array[Vector2] = []
			for i in range(SAMPLES):
				var a: Vector3 = pts[i]
				var b: Vector3 = pts[(i + 1) % SAMPLES]
				u.append(Vector2(b.x - a.x, b.z - a.z) / dt)
			speeds[side] = u
		# куда идёт тело: в каждый момент опирается та ступня, что ниже, — и едет назад
		for i in range(SAMPLES):
			var lower: String = "L" if ((feet.L as Array)[i] as Vector3).y < ((feet.R as Array)[i] as Vector3).y else "R"
			guess -= (speeds[lower] as Array[Vector2])[i]
		var dir: Vector2 = guess.normalized()
		var vel := Vector2.ZERO
		var used: int = 0
		var onsets: Array[int] = []
		for side: String in ["L", "R"]:
			var pts: Array = feet[side]
			var u: Array[Vector2] = speeds[side]
			var stance: Array[bool] = []
			for i in range(SAMPLES):
				stance.append((pts[i] as Vector3).y < float(lows[side]) + STANCE_BAND and u[i].dot(dir) < 0.0)
			stance = _clean(stance, int(SAMPLES * MIN_PHASE))
			for i in range(SAMPLES):
				if stance[i]:
					vel -= u[i]
					used += 1
				if side == "L" and stance[i] and not stance[(i - 1 + SAMPLES) % SAMPLES]:
					onsets.append(i)
		if used > 0:
			vel /= float(used)
		# Шаги считаем по подъёмам левой ступни (сглаженная высота уходит вниз — нога идёт на
		# землю), а постановку — первым кадром опоры после такого спуска: опора по скорости
		# может дробиться на куски, подъём ступни — нет.
		var heights: Array[float] = []
		for p: Vector3 in feet.L:
			heights.append(p.y)
		var h: Array[float] = _smooth(heights, maxi(int(SAMPLES * 0.03), 1))
		var top: float = -INF
		var bottom: float = INF
		for y: float in h:
			top = maxf(top, y)
			bottom = minf(bottom, y)
		# с запасом: шаг — ступня поднялась выше 65 % размаха и опустилась ниже 35 % (маленький
		# горбик при перекате с пятки на носок шагом не считается)
		var hi: float = lerpf(bottom, top, 0.65)
		var lo: float = lerpf(bottom, top, 0.35)
		var start: int = h.find(top)
		var up: bool = true
		var falls: Array[int] = []
		for k in range(1, SAMPLES + 1):
			var i: int = (start + k) % SAMPLES
			if up and h[i] < lo:
				falls.append(i)
				up = false
			elif not up and h[i] > hi:
				up = true
		var cycles: int = maxi(falls.size(), 1)
		var left_down: float = 0.0
		if not falls.is_empty():
			var first: int = falls[0]
			var best: int = SAMPLES
			for o: int in onsets:
				var ahead: int = (o - first + SAMPLES) % SAMPLES
				if ahead < best:
					best = ahead
			left_down = float((first + (best if best < SAMPLES / cycles else 0)) % SAMPLES) / float(SAMPLES) * length
		# Левая ступня должна быть слева (+X): иначе клип развёрнут на 180° — запекание или исходник
		# испорчены, тело в игре развернётся и побежит спиной.
		var side_x: float = 0.0
		for i in range(SAMPLES):
			side_x += ((feet.L as Array)[i] as Vector3).x - ((feet.R as Array)[i] as Vector3).x
		var flipped: bool = side_x < 0.0
		if flipped:
			push_warning("%s: клип развёрнут на 180° (левая ступня справа) — не годится для смешивания" % name)
		out[name] = {
			"length": snappedf(length, 0.001),
			"cycles": cycles,
			"left_down": snappedf(left_down, 0.001),
			"velocity": [snappedf(vel.x, 0.001), snappedf(vel.y, 0.001)],
			"speed": snappedf(vel.length(), 0.001),
			"flipped": flipped,
		}
		print("%-22s L=%.2f cycles=%d left_down=%.2f v=(%.2f, %.2f) |v|=%.2f%s" % [name, length, cycles, left_down, vel.x, vel.y, vel.length(), "  РАЗВЁРНУТ" if flipped else ""])
	var f := FileAccess.open(OUTPUT, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, "  ", true) + "\n")
	f.close()
	print("GAIT ", out.size(), " → ", OUTPUT)
	quit(0)


## Кольцевое скользящее среднее окном 2·half+1.
func _smooth(values: Array[float], half: int) -> Array[float]:
	var n: int = values.size()
	var out: Array[float] = []
	for i in range(n):
		var acc: float = 0.0
		for k in range(-half, half + 1):
			acc += values[(i + k + n) % n]
		out.append(acc / float(2 * half + 1))
	return out


## Убрать короткие острова (короче min_len отсчётов) в кольцевом ряду «опора / перенос».
func _clean(flags: Array[bool], min_len: int) -> Array[bool]:
	var n: int = flags.size()
	var out: Array[bool] = flags.duplicate()
	for pass_i in range(2):
		var start: int = -1
		for i in range(n):
			if out[i] != out[(i - 1 + n) % n]:
				start = i
				break
		if start < 0:
			return out
		var i: int = 0
		while i < n:
			var a: int = (start + i) % n
			var run: int = 1
			while run < n and out[(a + run) % n] == out[a]:
				run += 1
			if run < min_len:
				for k in range(run):
					out[(a + k) % n] = not out[a]
			i += run
	return out


func _is_locomotion(name: String) -> bool:
	return ("walk" in name or "run" in name or "sprint" in name or "prone_move" in name) and not "turn" in name


## Кость в осях модели, м.
func _bone(sk: Skeleton3D, bone: String) -> Vector3:
	return (sk.global_transform * sk.get_bone_global_pose(sk.find_bone(bone))).origin
