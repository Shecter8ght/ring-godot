extends Node
## Проверка загруженного художественного слоя, анимаций и общего рубильника.

var _fails: int = 0
var _checks: int = 0

func _ready() -> void:
	await get_tree().process_frame
	get_tree().current_scene = null
	Profile.use_file("user://shelter_dressing_test.json", true)
	Profile.hideout_media = {"power":true,"tv":0,"radio":0}
	get_tree().change_scene_to_file("res://levels/shelter/Shelter_Interior.tscn")
	for frame: int in range(40): await get_tree().process_frame
	var level: Node = get_tree().current_scene
	var dressing: Node = level.get_node("Dressing")
	_check("authored room dressing loaded",dressing.get_child_count()==81)
	_check("no runtime particle emitters",level.find_children("*","GPUParticles3D",true,false).is_empty() and level.find_children("*","CPUParticles3D",true,false).is_empty())
	var source: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://assets/shelter/dressing/manifest.json")) as Dictionary
	for id: String in source:
		var asset: Node3D = (load("res://levels/shelter/dressing/"+id+".tscn") as PackedScene).instantiate() as Node3D
		var meshes: Array[Node] = asset.find_children("*","MeshInstance3D",true,false)
		_check(id+" saved mesh with painted maps",not meshes.is_empty() and ((meshes[0] as MeshInstance3D).mesh.surface_get_material(0) as StandardMaterial3D).albedo_texture!=null)
		asset.free()
	var effects: Node = level.get_node("Atmosphere")
	_check("five authored effects",effects.get_child_count()==5)
	for effect: Node in effects.get_children():
		var player: AnimationPlayer = effect.get_node(effect.get("animation_path") as NodePath) as AnimationPlayer
		var mesh: MeshInstance3D = effect.find_children("*","MeshInstance3D",true,false)[0] as MeshInstance3D
		_check(String(effect.name)+" saved material and clip",mesh.material_override is ShaderMaterial and player.is_playing())
		var clip: Animation = player.get_animation(player.current_animation)
		_check(String(effect.name)+" looping authored poses",clip.loop_mode==Animation.LOOP_LINEAR and mesh.mesh.get_blend_shape_count()==5)
		player.seek(.1,true)
		var before: float = mesh.get_blend_shape_value(0)
		player.seek(2.0,true)
		_check(String(effect.name)+" mesh actually moves",absf(mesh.get_blend_shape_value(0)-before)>.03)
	var power: ShelterPower = level.get_node("Gameplay/GeneratorPower") as ShelterPower
	power.request_use()
	for frame: int in range(3): await get_tree().process_frame
	for effect: Node in effects.get_children():
		var player: AnimationPlayer = effect.get_node(effect.get("animation_path") as NodePath) as AnimationPlayer
		_check(String(effect.name)+" power off",not (effect as Node3D).visible and not player.is_playing())
	power.request_use()
	for frame: int in range(3): await get_tree().process_frame
	for effect: Node in effects.get_children():
		var player: AnimationPlayer = effect.get_node(effect.get("animation_path") as NodePath) as AnimationPlayer
		_check(String(effect.name)+" power restored",(effect as Node3D).visible and player.is_playing())
	for label: String in ["TeaCorner","StorageHandTruck"]:
		_check(label+" has static collision",dressing.get_node(label).has_node("SimplifiedCollision"))
	print("DRESSING_ACCEPTANCE checks=%d failures=%d" % [_checks,_fails])
	get_tree().quit(0 if _fails==0 else 1)

func _check(label: String, valid: bool) -> void:
	_checks += 1
	if not valid: _fails += 1
	print("PASS " if valid else "FAIL ",label)
