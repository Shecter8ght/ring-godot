@tool
extends Node3D
## Только стенд общежития: реальное полотно на петле. Полотно — модуль Blender M01 (module_leaf, dorm_modules.gd),
## без него — черновое из брусков; петля, открывание и коллизия те же.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const DormModules = preload("res://src/blockout/dorm_modules.gd")
## Полотно модуля от оси петель: толщина у модуля смещена на 26 мм от оси, у черновика — по оси.
const LEAF_CENTER_Z: float = 0.026

var data: Dictionary = {}
var materials: Dictionary = {}
var module_leaf: Mesh = null
var angle: float = 0.0
var is_open: bool = false
var motion: Tween


func _ready() -> void:
	if data.is_empty():
		return
	position = Vector3(float(data.at[0]),float(data.at[1]),float(data.at[2]))
	add_to_group("dorm_study_doors")
	var width: float = float(data.width)
	var height: float = float(data.height)
	var builder: RefCounted = Geometry.new(self,materials)
	if module_leaf!=null:
		var leaf: MeshInstance3D = MeshInstance3D.new()
		leaf.name = "Leaf"
		leaf.mesh = module_leaf
		leaf.position = Vector3(0,0,LEAF_CENTER_Z)
		leaf.gi_mode = GeometryInstance3D.GI_MODE_DYNAMIC
		DormModules.apply_materials(leaf)
		add_child(leaf)
		builder.call("collision_box",Vector3(width/2,height/2,0),Vector3(width,height,float(data.thickness)))
		_grille(builder,width,height)
		builder.call("finish")
		reset_pose()
		return
	# Филёнки и обвязка укладываются в общую толщину 40 мм.
	builder.call("box",Vector3(width/2,height/2,0),Vector3(width,height,0.032),String(data.mat),false)
	for x: float in [0.05,width-0.05]:
		builder.call("box",Vector3(x,height/2,0),Vector3(0.10,height,0.04),String(data.mat),false)
	for y: float in [0.06,height*0.46,height-0.06]:
		builder.call("box",Vector3(width/2,y,0),Vector3(width-0.2,0.12,0.04),String(data.mat),false)
	builder.call("collision_box",Vector3(width/2,height/2,0),Vector3(width,height,float(data.thickness)))
	for face: float in [-1.0,1.0]:
		builder.call("box",Vector3(width-0.13,1.05,face*0.025),Vector3(0.055,0.20,0.014),"rail",false)
		builder.call("box",Vector3(width-0.13,1.05,face*0.055),Vector3(0.025,0.025,0.06),"rail",false)
		builder.call("box",Vector3(width-0.18,1.05,face*0.078),Vector3(0.12,0.022,0.025),"rail",false)
	for y: float in [0.22,height/2,height-0.22]:
		builder.call("box",Vector3(0.0,y,0.0),Vector3(0.035,0.105,0.055),"rail",false)
	_grille(builder,width,height)
	builder.call("finish")
	reset_pose()


func _grille(builder: RefCounted, width: float, height: float) -> void:
	if bool(data.grille):
		var front: float = float(data.front)*0.065
		for i: int in range(6):
			var x: float = 0.025+(width-0.05)*i/5.0
			builder.call("box",Vector3(x,height/2,front),Vector3(0.022,height-0.04,0.025),"rail",false)
		for i: int in range(8):
			var y: float = 0.025+(height-0.05)*i/7.0
			builder.call("box",Vector3(width/2,y,front),Vector3(width-0.04,0.022,0.025),"rail",false)


func _apply_angle(value: float) -> void:
	angle = value
	rotation.y = deg_to_rad(float(data.yaw_closed)+float(data.swing_sign)*angle)


func set_open(value: bool, animated: bool = true) -> void:
	if is_instance_valid(motion):
		motion.kill()
	is_open = value
	var target: float = float(data.open_angle) if value else 0.0
	if animated and not Engine.is_editor_hint():
		motion = create_tween()
		motion.tween_method(_apply_angle,angle,target,0.28).set_trans(Tween.TRANS_SINE)
	else:
		_apply_angle(target)


func reset_pose() -> void:
	if is_instance_valid(motion):
		motion.kill()
	_apply_angle(float(data.angle))
	is_open = angle >= float(data.open_angle)-0.1


func toggle() -> void:
	set_open(not is_open)
