extends SceneTree
## Как оружие лежит в правой руке Persona (вид от третьего лица) — для каждого семейства рукояток
## data/weapon_grips.json (pistol / rifle / shotgun / bolt). Персонаж ставится в позу прицеливания
## (клип REF), запястье правой руки совмещается с точкой рукоятки (right.pos), ствол смотрит от
## правой руки к левой (у пистолета — вдоль предплечья), верх оружия — к небу. Результат —
## положение и поворот оружия в осях кости mixamorig_RightHand — пишется в data/weapon_sockets.json;
## Player и Marauder вешают модель оружия на эту кость (WeaponSocket).
## Запуск: tools/godot.cmd --headless -s res://tools/bake_weapon_sockets.gd

const MODEL := "res://assets/models/characters/persona_animated.glb"
const CLIPS := "res://assets/models/characters/persona_clips.res"
const GRIPS := "res://data/weapon_grips.json"
const OUTPUT := "res://data/weapon_sockets.json"
## Поза прицеливания и момент клипа для каждого семейства.
const REF := {"pistol": ["pistol_idle", 0.4], "rifle": ["rifle_aim", 0.4], "shotgun": ["rifle_aim", 0.4], "bolt": ["rifle_aim", 0.4]}


var _done: bool = false


## Считать на первом кадре: в _initialize модель ещё не в дереве, глобальных трансформ у костей нет.
func _process(_delta: float) -> bool:
	if not _done:
		_done = true
		_bake()
	return true


func _bake() -> void:
	var grips: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(GRIPS))
	var root: Node3D = (load(MODEL) as PackedScene).instantiate() as Node3D
	get_root().add_child(root)
	var sk := root.find_children("*", "Skeleton3D", true, false)[0] as Skeleton3D
	var ap := AnimationPlayer.new()
	root.add_child(ap)
	ap.root_node = NodePath("..")
	ap.add_animation_library("", load(CLIPS) as AnimationLibrary)
	var rh := sk.find_bone("mixamorig_RightHand")
	var lh := sk.find_bone("mixamorig_LeftHand")
	var rf := sk.find_bone("mixamorig_RightForeArm")
	var out: Dictionary = {"_comment": "Сгенерировано tools/bake_weapon_sockets.gd: оружие в осях кости mixamorig_RightHand (origin, basis — столбцы x, y, z). Не править руками — перезапустить инструмент."}
	for family in REF:
		var clip := String(REF[family][0])
		ap.play(clip)
		ap.seek(float(REF[family][1]), true)
		ap.advance(0.0)
		var hand: Transform3D = sk.global_transform * sk.get_bone_global_pose(rh)
		var left: Transform3D = sk.global_transform * sk.get_bone_global_pose(lh)
		var fore: Transform3D = sk.global_transform * sk.get_bone_global_pose(rf)
		var forward: Vector3 = (left.origin - hand.origin) if family != "pistol" else (hand.origin - fore.origin)
		forward = forward.normalized()
		var up := (Vector3.UP - forward * Vector3.UP.dot(forward)).normalized()
		# оси модели оружия: +Z — ствол, +Y — верх, -X — правая сторона стрелка
		var basis := Basis(up.cross(forward).normalized(), up, forward)
		var grip: Array = ((grips[family] as Dictionary).right as Dictionary).pos
		var grip_local := Vector3(float(grip[0]), float(grip[1]), float(grip[2]))
		var gun := Transform3D(basis, hand.origin - basis * grip_local)
		var socket: Transform3D = hand.affine_inverse() * gun
		# левая рука: насколько запястье далеко от своей точки на цевье (проверка позы)
		var miss := -1.0
		if family != "pistol" and (grips[family] as Dictionary).has("left"):
			var lp: Array = ((grips[family] as Dictionary).left as Dictionary).pos
			miss = left.origin.distance_to(gun * Vector3(float(lp[0]), float(lp[1]), float(lp[2])))
		out[family] = {"clip": clip, "at": float(REF[family][1]),
			"origin": [snappedf(socket.origin.x, 0.0001), snappedf(socket.origin.y, 0.0001), snappedf(socket.origin.z, 0.0001)],
			"basis": [_v(socket.basis.x), _v(socket.basis.y), _v(socket.basis.z)]}
		print("%s: клип %s, масштаб кости %.3f, левая рука мимо цевья на %.3f м" % [family, clip, hand.basis.get_scale().x, miss])
	var f := FileAccess.open(OUTPUT, FileAccess.WRITE)
	f.store_string(JSON.stringify(out, "  ", false))
	print("записано: ", OUTPUT)


func _v(v: Vector3) -> Array:
	return [snappedf(v.x, 0.0001), snappedf(v.y, 0.0001), snappedf(v.z, 0.0001)]
