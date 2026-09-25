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
	var failed: int = 0
	for key in sources:
		var name: String = String(key)
		var source_path: String = "res://assets/animations/" + String(sources[key])
		var source_scene: PackedScene = load(source_path) as PackedScene
		if source_scene == null:
			push_error("Не найден FBX: " + source_path)
			failed += 1
			continue
		var source_root: Node = source_scene.instantiate()
		var players: Array[Node] = source_root.find_children("*", "AnimationPlayer", true, false)
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
			push_error("Пустой AnimationPlayer: " + source_path)
			failed += 1
			source_root.free()
			continue
		var clip: Animation = source_player.get_animation(names[0]).duplicate(true) as Animation
		var retained: int = 0
		for i in range(clip.get_track_count() - 1, -1, -1):
			var track_path: NodePath = clip.track_get_path(i)
			var bone: String = String(track_path.get_subname(0)) if track_path.get_subname_count() > 0 else ""
			if skeleton.find_bone(bone) < 0:
				clip.remove_track(i)
				continue
			if bone == "mixamorig_Hips" and clip.track_get_type(i) == Animation.TYPE_ROTATION_3D:
				clip.remove_track(i)
				continue
			clip.track_set_path(i, NodePath(target_path + ":" + bone))
			retained += 1
			if clip.track_get_type(i) == Animation.TYPE_POSITION_3D and bone == "mixamorig_Hips":
				_remove_root_drift(clip, i)
		if retained == 0:
			push_error("Нет совместимых треков: " + source_path)
			failed += 1
		else:
			clip.loop_mode = Animation.LOOP_LINEAR if _is_cycle(name) else Animation.LOOP_NONE
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
	return "idle" in name or "walk" in name or "run" in name or "sprint" in name or "prone_move" in name


func _remove_root_drift(clip: Animation, track: int) -> void:
	var count: int = clip.track_get_key_count(track)
	if count < 2:
		return
	var start: float = clip.track_get_key_time(track, 0)
	var finish: float = clip.track_get_key_time(track, count - 1)
	var span: float = maxf(finish - start, 0.001)
	var first: Vector3 = clip.track_get_key_value(track, 0) as Vector3
	var last: Vector3 = clip.track_get_key_value(track, count - 1) as Vector3
	var drift: Vector3 = last - first
	for i in range(count):
		var t: float = (clip.track_get_key_time(track, i) - start) / span
		var value: Vector3 = clip.track_get_key_value(track, i) as Vector3
		clip.track_set_key_value(track, i, value - drift * t)
