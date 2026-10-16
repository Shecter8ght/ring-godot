extends Node
## Регрессия чёрного экрана: запуск каждой точки входа без посторонней камеры стенда.

func _enter_tree() -> void:
	Profile.use_file("user://profile_urban_belt_launch_test.json",true)

func _ready() -> void:
	var tree: SceneTree = get_tree()
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var target: String = args[0] if not args.is_empty() else "res://scenes/levels/urban_belt_study.tscn"
	var scene: Node = (load(target) as PackedScene).instantiate()
	tree.root.add_child.call_deferred(scene)
	await tree.process_frame
	tree.current_scene = scene
	for i: int in range(12):
		await tree.physics_frame
	var camera: Camera3D = tree.root.get_camera_3d()
	var walkers: int = scene.find_children("StudyWalker","CharacterBody3D",true,false).size()
	var worlds: int = scene.find_children("UrbanBeltStudy","Node3D",true,false).size()
	worlds += int(scene.name == "UrbanBeltStudy")
	var cameras: int = scene.find_children("*","Camera3D",true,false).size()
	var hud: Node = scene.find_child("StudyUI",true,false)
	var passed: bool = camera!=null and walkers==1 and worlds==1 and cameras==1 and hud!=null
	print("urban_belt_launch_test: ",JSON.stringify({"entry":target,"pass":passed,"active_camera":str(camera.get_path()) if camera else "NONE","walkers":walkers,"worlds":worlds,"cameras":cameras,"hud":hud!=null}))
	tree.quit(0 if passed else 1)
