extends SceneTree
## Переносит ключи Mixamo на общий Skeleton3D Persona по именам костей.

const MODEL := "res://assets/models/characters/persona_animated.glb"
const OUTPUT := "res://assets/models/characters/persona_clips.res"
const MANIFEST := "res://tools/character_clips.json"


func _initialize() -> void:
	var file: FileAccess = FileAccess.open(MANIFEST, FileAccess.READ)
	if file == null:
		push_error("Нет списка клипов: " + MANIFEST)
		quit(1)
		return
	var sources: Dictionary = JSON.parse_string(file.get_as_text()) as Dictionary
	var model: PackedScene = load(MODEL) as PackedScene
	var root: Node = model.instantiate()
	get_root().add_child(root)
	var skeletons: Array[Node] = root.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty():
		push_error("У Persona нет Skeleton3D")
		quit(1)
		return
	var skeleton: Skeleton3D = skeletons[0] as Skeleton3D
	var target_path: String = String(root.get_path_to(skeleton))
	var library := AnimationLibrary.new()
	var previous: AnimationLibrary = load(OUTPUT) as AnimationLibrary
	var selected: PackedStringArray = OS.get_cmdline_user_args()
	if not selected.is_empty():
		library = previous.duplicate() as AnimationLibrary
	var failed: int = 0
	for key in sources:
		var name: String = String(key)
		if not selected.is_empty() and not name in selected:
			continue
		var source_path: String = "res://assets/animations/" + String(sources[key])
		var source_scene: PackedScene = load(source_path) as PackedScene
		if source_scene == null:
			push_error("Не найден FBX: " + source_path)
			failed += 1
			continue
		var source_root: Node = source_scene.instantiate()
		var players: Array[Node] = source_root.find_children("*", "AnimationPlayer", true, false)
		var source_skeletons: Array[Node] = source_root.find_children("*", "Skeleton3D", true, false)
		if players.is_empty():
			push_error("Нет анимации: " + source_path)
			failed += 1
			source_root.free()
			continue
		var source_player: AnimationPlayer
		for candidate in players:
			var found: AnimationPlayer = candidate as AnimationPlayer
			if not found.get_animation_list().is_empty():
				source_player = found
				break
		var names: PackedStringArray = source_player.get_animation_list() if source_player != null else PackedStringArray()
		if names.is_empty():
			if previous != null and previous.has_animation(name):
				var saved: Animation = previous.get_animation(name).duplicate(true) as Animation
				for track in range(saved.get_track_count()):
					if saved.track_get_type(track) == Animation.TYPE_POSITION_3D and String(saved.track_get_path(track)).ends_with(":mixamorig_Hips"):
						_offset_hips(saved, track, skeleton.get_bone_rest(skeleton.find_bone("mixamorig_Hips")).origin)
				library.add_animation(name, saved)
				print("REUSED ", name)
			else:
				push_error("Пустой AnimationPlayer: " + source_path)
				failed += 1
			source_root.free()
			continue
		var clip: Animation = source_player.get_animation(names[0]).duplicate(true) as Animation
		var source_skeleton: Skeleton3D = source_skeletons[0] as Skeleton3D if not source_skeletons.is_empty() else null
		var retained: int = 0
		for i in range(clip.get_track_count() - 1, -1, -1):
			var track_path: NodePath = clip.track_get_path(i)
			var bone: String = String(track_path.get_subname(0)) if track_path.get_subname_count() > 0 else ""
			if skeleton.find_bone(bone) < 0:
				clip.remove_track(i)
				continue
			if bone == "mixamorig_Hips" and clip.track_get_type(i) == Animation.TYPE_ROTATION_3D and source_skeleton != null:
				var source_bone: int = source_skeleton.find_bone(bone)
				if source_bone >= 0:
					var from_rest: Quaternion = source_skeleton.get_bone_rest(source_bone).basis.get_rotation_quaternion()
					var to_rest: Quaternion = skeleton.get_bone_rest(skeleton.find_bone(bone)).basis.get_rotation_quaternion()
					_retarget_rotation(clip, i, from_rest, to_rest)
			clip.track_set_path(i, NodePath(target_path + ":" + bone))
			retained += 1
			if clip.track_get_type(i) == Animation.TYPE_POSITION_3D and bone == "mixamorig_Hips":
				if source_skeleton != null and source_skeleton.find_bone(bone) >= 0:
					_retarget_hips(clip, i, source_skeleton, _to_root(source_skeleton, source_root),
						skeleton.get_bone_rest(skeleton.find_bone(bone)).origin, _to_root(skeleton, root))
				else:
					_remove_root_drift(clip, i, skeleton.get_bone_rest(skeleton.find_bone(bone)).origin)
				if name == "jump_loop":
					# Высоту прыжка задаёт физическое тело; клип сгибает ноги без второго root-подскока.
					var rest_y: float = skeleton.get_bone_rest(skeleton.find_bone(bone)).origin.y
					for key_index: int in range(clip.track_get_key_count(i)):
						var value: Vector3 = clip.track_get_key_value(i, key_index) as Vector3
						value.y = rest_y
						clip.track_set_key_value(i, key_index, value)
		if retained == 0:
			push_error("Нет совместимых треков: " + source_path)
			failed += 1
		else:
			clip.loop_mode = Animation.LOOP_LINEAR if _is_cycle(name) else Animation.LOOP_NONE
			if library.has_animation(name):
				library.remove_animation(name)
			library.add_animation(name, clip)
			print("BAKED ", name, " tracks=", retained)
		source_root.free()
	var result: Error = ResourceSaver.save(library, OUTPUT)
	if result != OK:
		push_error("Не удалось сохранить библиотеку: " + str(result))
		failed += 1
	print("CLIPS ", library.get_animation_list().size(), " FAILED ", failed)
	quit(0 if failed == 0 else 1)


func _is_cycle(name: String) -> bool:
	return "idle" in name or "walk" in name or "run" in name or "sprint" in name or "prone_move" in name or name == "jump_loop"


func _remove_root_drift(clip: Animation, track: int, rest: Vector3) -> void:
	var count: int = clip.track_get_key_count(track)
	if count == 0:
		return
	if count == 1:
		_offset_hips(clip, track, rest)
		return
	var start: float = clip.track_get_key_time(track, 0)
	var finish: float = clip.track_get_key_time(track, count - 1)
	var span: float = maxf(finish - start, 0.001)
	var first: Vector3 = clip.track_get_key_value(track, 0) as Vector3
	var last: Vector3 = clip.track_get_key_value(track, count - 1) as Vector3
	# снос убираем только по горизонтали: клип не уводит тело от коллизии, но падение (смерть,
	# нокаут) опускает таз к полу — вертикаль оставляем
	var drift: Vector3 = last - first
	drift.y = 0.0
	for i in range(count):
		var t: float = (clip.track_get_key_time(track, i) - start) / span
		var value: Vector3 = clip.track_get_key_value(track, i) as Vector3
		clip.track_set_key_value(track, i, value - drift * t + rest)


## Скелет → корень сцены: у FBX Mixamo скелет лежит под узлом с масштабом 100 и осью Z вверх,
## ключи таза — в осях скелета. Без этого перевода вертикаль таза терялась: падение, присед и лёжа
## оставляли таз на высоте стоя (мёртвый «висел» над полом).
func _to_root(node: Node3D, root: Node) -> Transform3D:
	var xf := Transform3D.IDENTITY
	var n: Node = node
	while n != null and n != root:
		if n is Node3D:
			xf = (n as Node3D).transform * xf
		n = n.get_parent()
	return xf


## Путь таза из исходника — на Persona: смещение от позы покоя в осях сцены, масштаб по росту
## (высоте таза), горизонтальный снос за клип убран (тело не уходит от капсулы), вертикаль —
## как в клипе: присел, лёг, упал — таз у пола.
func _retarget_hips(clip: Animation, track: int, source: Skeleton3D, source_xf: Transform3D, rest: Vector3, target_xf: Transform3D) -> void:
	var count: int = clip.track_get_key_count(track)
	if count == 0:
		return
	var source_rest: Vector3 = source_xf * source.get_bone_rest(source.find_bone("mixamorig_Hips")).origin
	var target_rest: Vector3 = target_xf * rest
	var k: float = target_rest.y / source_rest.y if absf(source_rest.y) > 0.001 else 1.0
	var start: float = clip.track_get_key_time(track, 0)
	var span: float = maxf(clip.track_get_key_time(track, count - 1) - start, 0.001)
	var first: Vector3 = source_xf * (clip.track_get_key_value(track, 0) as Vector3)
	var drift: Vector3 = source_xf * (clip.track_get_key_value(track, count - 1) as Vector3) - first
	drift.y = 0.0
	var inv: Transform3D = target_xf.affine_inverse()
	for i in range(count):
		var t: float = (clip.track_get_key_time(track, i) - start) / span
		var value: Vector3 = source_xf * (clip.track_get_key_value(track, i) as Vector3)
		var delta: Vector3 = (value - source_rest - drift * t) * k
		clip.track_set_key_value(track, i, inv * (target_rest + delta))


func _offset_hips(clip: Animation, track: int, rest: Vector3) -> void:
	if clip.track_get_key_count(track) == 0 or (clip.track_get_key_value(track, 0) as Vector3).y > rest.y * 0.5:
		return
	for i in range(clip.track_get_key_count(track)):
		var value: Vector3 = clip.track_get_key_value(track, i) as Vector3
		clip.track_set_key_value(track, i, value + rest)


func _retarget_rotation(clip: Animation, track: int, source_rest: Quaternion, target_rest: Quaternion) -> void:
	for i in range(clip.track_get_key_count(track)):
		var source_pose: Quaternion = clip.track_get_key_value(track, i) as Quaternion
		clip.track_set_key_value(track, i, target_rest * source_rest.inverse() * source_pose)
