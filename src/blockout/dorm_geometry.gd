@tool
extends Node3D
## Серый объём общежития из данных. Каждый этаж и лестница — отдельный узел сцены.
## Предпросмотр не сохраняет созданные меши в tscn; этап 2 заменит их модулями Blender.

const Geometry = preload("res://src/blockout/study_geometry.gd")
const StudyDoor = preload("res://src/blockout/dorm_study_door.gd")
const ExteriorBatches = preload("res://src/blockout/dorm_exterior_batches.gd")
const DormModules = preload("res://src/blockout/dorm_modules.gd")
const FoundLight = preload("res://src/blockout/dorm_found_light.gd")
## Электричества в заброшенном здании нет: лампы плана из remove_groups не ставятся, вместо них — свет, оставленный
## людьми (dorm_found_light.gd). Без файла — прежние лампы.
const FOUND_LIGHTS_PATH: String = "res://data/blockouts/dorm_found_lights.json"
## Следы (кровь, грязь, пыль, копоть) — декали из масок владельца; без карт assets/textures/dorm_decals их нет.
const DECALS_PATH: String = "res://data/blockouts/dorm_decals.json"
const DECAL_DIR: String = "res://assets/textures/dorm_decals"

@export var section_id: String = "Site"
@export_file("*.json") var plan_path: String = "res://data/blockouts/dorm.json"
@export_tool_button("Пересобрать из JSON") var rebuild_action: Callable = rebuild
var split_gi_batches: bool = true
var floor_levels: Array = []
var gi_footprints: Array[Rect2] = []
## Модули Blender этапа 2 (dorm_modules.gd) — null, если их файлов нет.
var modules: RefCounted = null


func _ready() -> void:
	rebuild()


func rebuild() -> void:
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()
	if not FileAccess.file_exists(plan_path):
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(plan_path))
	if not parsed is Dictionary:
		push_error("dorm: не прочитан " + plan_path)
		return
	var plan: Dictionary = parsed as Dictionary
	floor_levels = plan.scale.floor_y
	gi_footprints.clear()
	for volume: Dictionary in plan.environment.voxel.volumes:
		var footprint: Rect2 = Rect2(float(volume.at[0])-float(volume.size[0])*.5,float(volume.at[2])-float(volume.size[2])*.5,float(volume.size[0]),float(volume.size[2]))
		if footprint not in gi_footprints:gi_footprints.append(footprint)
	var section: Dictionary = (plan.get("sections", {}) as Dictionary).get(section_id, {})
	if section.is_empty():
		return
	var palette: Dictionary = _palette(plan)
	modules = DormModules.new(plan,section_id,palette) if DormModules.available() else null
	_build_geometry(self,section,palette)
	for group_name: String in section.get("groups",{}):
		var group: Node3D = Node3D.new()
		group.name = group_name
		group.add_to_group("dorm_detail_"+group_name)
		add_child(group)
		_build_geometry(group,section.groups[group_name],palette)
	if modules!=null:
		modules.call("place",self)
	var found: Dictionary = _found_lights()
	for item: Dictionary in section.get("lights", []):
		if String(item.get("group","legacy")) in found.get("remove_groups",[]):
			continue
		var lamp: Light3D = SpotLight3D.new() if String(item.get("type","omni"))=="spot" else OmniLight3D.new()
		lamp.name = String(item.get("id","StudyFill"))
		lamp.position = _vec(item.at)
		lamp.light_color = Color(String(item.get("color","eef5ff")))
		lamp.light_energy = float(item.energy)
		lamp.light_bake_mode = Light3D.BAKE_DYNAMIC
		lamp.shadow_enabled = bool(item.get("shadow",true))
		lamp.visible = bool(item.get("on",true))
		lamp.shadow_bias = float(item.get("shadow_bias",.025))
		lamp.light_size = float(item.get("source_size",0.0))
		lamp.shadow_blur = float(item.get("shadow_blur",1.0))
		lamp.set_meta("light_group",String(item.get("group","legacy")))
		lamp.add_to_group("dorm_lamps")
		if bool(item.get("sky_fill",false)):
			lamp.add_to_group("dorm_window_sky")
			lamp.shadow_blur = 2.0
		if lamp is SpotLight3D:
			var spot: SpotLight3D = lamp as SpotLight3D
			spot.rotation_degrees.x = -90.0
			if item.has("rotation"):
				spot.rotation_degrees = _vec(item.rotation)
			spot.spot_range = float(item.range)
			spot.spot_angle = float(item.get("angle",68.0))
			spot.spot_attenuation = float(item.get("attenuation",1.7))
		else:
			var omni: OmniLight3D = lamp as OmniLight3D
			omni.omni_range = float(item.range)
			omni.omni_attenuation = float(item.get("falloff",1.0))
			omni.omni_shadow_mode = OmniLight3D.SHADOW_DUAL_PARABOLOID
		add_child(lamp)
		# Settings.soften runs on node_added; the authored window bias must survive it.
		lamp.shadow_bias = float(item.get("shadow_bias",.025))
		if item.has("specular"):lamp.light_specular = float(item.specular)
		if item.has("angle_attenuation"):(lamp as SpotLight3D).spot_angle_attenuation = float(item.angle_attenuation)
	for item: Dictionary in found.get("lights",[]):
		if String(item.get("section",""))!=section_id:
			continue
		var source: Node3D = FoundLight.new() as Node3D
		source.name = String(item.id)
		source.set("kind",String(item.kind))
		source.set("charge",float(item.get("charge",0.6)))
		source.set("seed_value",String(item.id).hash())
		source.position = _vec(item.at)
		source.rotation_degrees.y = float(item.get("yaw",0.0))
		add_child(source)
	for item: Dictionary in _read_json(DECALS_PATH).get("decals",[]):
		if String(item.get("section",""))==section_id:
			_add_decal(item)
	for item: Dictionary in section.get("probes", []):
		var probe: ReflectionProbe = ReflectionProbe.new()
		probe.name = String(item.get("id","BathroomReflection"))
		probe.position = _vec(item.at)
		probe.size = _vec(item.size)+Vector3(0.1,0.1,0.1)
		probe.blend_distance = float(item.get("blend",0.05))
		probe.interior = true
		probe.box_projection = true
		probe.update_mode = ReflectionProbe.UPDATE_ONCE
		probe.max_distance = float(item.get("max_distance",12.0))
		probe.intensity = float(item.get("intensity",1.0))
		probe.enable_shadows = bool(item.get("shadows",true))
		probe.ambient_mode = ReflectionProbe.AMBIENT_DISABLED
		probe.add_to_group("dorm_reflections")
		add_child(probe)


func _build_geometry(target: Node3D, data: Dictionary, palette: Dictionary) -> void:
	var builder: RefCounted = Geometry.new(target,palette)
	for item: Dictionary in data.get("boxes",[]):
		if String(item.mat)=="mirror":
			# Отдельная поверхность получает пробу своей комнаты, а не всего этажа.
			var surface: MeshInstance3D = MeshInstance3D.new()
			surface.name = "StudyMirror"
			surface.add_to_group("dorm_mirrors")
			var shape: BoxMesh = BoxMesh.new()
			shape.size = _vec(item.size)
			surface.mesh = shape
			surface.material_override = palette["mirror"] as Material
			surface.position = _vec(item.at)
			target.add_child(surface)
		elif modules!=null and bool(modules.call("skip",item,builder)):
			continue
		else:
			var pieces: Array = [item] if modules==null else modules.call("trim",item,builder)
			for piece: Dictionary in pieces:
				builder.call("box",_vec(piece.at),_vec(piece.size),_batch_material(String(piece.mat),float(item.at[1]),palette),bool(item.solid),deg_to_rad(float(item.yaw)))
			if String(item.mat)=="glass" and bool(item.solid):
				# Glass blocks walking but transmits light; visibility probes must skip it.
				var body: StaticBody3D = builder.get("body") as StaticBody3D
				body.get_child(body.get_child_count()-1).set_meta("dorm_light_transparent",true)
	for item: Dictionary in data.get("beams",[]):
		var start: Vector3 = _vec(item.start)
		var end: Vector3 = _vec(item.end)
		# перила лестницы с маршами-модулями — модулем ограждения (dorm_modules.gd), здесь остаётся коллизия
		var visual: bool = modules==null or not bool(modules.call("rail_beam",item))
		if absf(start.x-end.x)<0.001 and absf(start.z-end.z)<0.001:
			var size: Vector3 = Vector3(float(item.width),absf(end.y-start.y),float(item.depth))
			if visual:
				builder.call("box",(start+end)*0.5,size,_batch_material(String(item.mat),(start.y+end.y)*.5,palette),bool(item.solid))
			elif bool(item.solid):
				builder.call("collision_box",(start+end)*0.5,size)
		else:
			builder.call("beam",start,end,float(item.width),float(item.depth),_batch_material(String(item.mat),(start.y+end.y)*.5,palette),bool(item.solid),visual)
	for item: Dictionary in data.get("stairs",[]):
		var visual: bool = modules==null or not bool(modules.call("flight",item))
		builder.call("stairs",_vec(item.start),_vec(item.end),float(item.width),int(item.count),_batch_material(String(item.mat),(float(item.start[1])+float(item.end[1]))*.5,palette),visual)
	builder.call("finish")
	if split_gi_batches:ExteriorBatches.separate(target,gi_footprints)
	for item: Dictionary in data.get("labels",[]):
		var plaque: Label3D = Label3D.new()
		plaque.name = "RoomNumber" if bool(item.get("permanent",false)) else "StudyLabel"
		plaque.text = String(item.text)
		plaque.position = _vec(item.at)
		plaque.rotation_degrees.y = float(item.yaw)
		plaque.font_size = 36
		plaque.pixel_size = 0.005
		plaque.modulate = Color("24282b")
		plaque.outline_size = 2
		plaque.outline_modulate = Color("c9cdd0")
		plaque.no_depth_test = false
		plaque.add_to_group("dorm_door_numbers" if bool(item.get("permanent",false)) else "dorm_study_labels")
		target.add_child(plaque)
	for item: Dictionary in data.get("doors",[]):
		var leaf: Node3D = StudyDoor.new() as Node3D
		leaf.name = String(item.id)
		leaf.set("data",item)
		leaf.set("materials",palette)
		if modules!=null:leaf.set("module_leaf",modules.call("leaf_mesh",item))
		target.add_child(leaf)

func _batch_material(key: String, height: float, palette: Dictionary) -> String:
	# Only regroup existing triangles. No changed vertices, UVs, materials or collisions.
	# A single annex mesh spanning three floors can only receive the first two GI probes.
	if not split_gi_batches or section_id not in ["NorthAnnex","CentralStair"]:return key
	var floor_index: int = 0
	for i: int in range(floor_levels.size()):
		if height>=float(floor_levels[i])-.001:floor_index = i
	var alias: String = key+"__floor_"+str(floor_index+1)
	palette[alias] = palette[key]
	return alias


static func _found_lights() -> Dictionary:
	return _read_json(FOUND_LIGHTS_PATH)


static func _read_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	return parsed as Dictionary if parsed is Dictionary else {}


## Декаль проецируется вдоль −Y на поверхность с нормалью normal; на стене низ картинки (+Z декали) — вниз,
## на полу картинка повёрнута на rot.
func _add_decal(item: Dictionary) -> void:
	var name_id: String = String(item.name)
	var albedo_path: String = "%s/%s_albedo.png" % [DECAL_DIR,name_id]
	if not ResourceLoader.exists(albedo_path):
		return
	var n: Vector3 = _vec(item.normal).normalized()
	var down: Vector3
	if absf(n.y)>0.9:
		var rot: float = deg_to_rad(float(item.get("rot",0.0)))
		down = Vector3(sin(rot),0,cos(rot))
	else:
		down = (Vector3.DOWN-n*n.dot(Vector3.DOWN)).normalized()
	var decal: Decal = Decal.new()
	decal.name = String(item.id)
	decal.transform = Transform3D(Basis(n.cross(down),n,down),_vec(item.at))
	decal.size = Vector3(float(item.size[0]),float(item.get("depth",0.3)),float(item.size[1]))
	decal.texture_albedo = load(albedo_path) as Texture2D
	decal.texture_normal = load("%s/%s_normal.png" % [DECAL_DIR,name_id]) as Texture2D
	decal.texture_orm = load("%s/%s_orm.png" % [DECAL_DIR,name_id]) as Texture2D
	decal.normal_fade = 0.5
	decal.upper_fade = 0.2
	decal.lower_fade = 0.2
	decal.distance_fade_enabled = true
	decal.distance_fade_begin = 30.0
	decal.distance_fade_length = 10.0
	decal.add_to_group("dorm_decals")
	add_child(decal)


static func _vec(values: Array) -> Vector3:
	return Vector3(float(values[0]), float(values[1]), float(values[2]))


static func _palette(plan: Dictionary) -> Dictionary:
	var result: Dictionary = {}
	var colors: Dictionary = {"wall": "a9adb0", "floor": "777d83", "slab": "8c9195", "frame": "626970",
		"rail": "444a50", "sealed": "555b60", "ground": "656b66", "paving": "85898b", "tree": "646b67", "glass": "88969e",
		"mattress": "a39d89", "wood": "766449", "ceramic": "d5d9ce", "basin": "8d9996", "mirror": "f0f0ed",
		"ceiling":"777d83", "skirting":"4d554d", "reveal":"dfe1d9", "radiator":"c0c6bc",
		"door_green":"596350", "door_wood":"75634f", "panel":"656a65", "fire_cabinet":"824b43"}
	for key: String in colors:
		var material: StandardMaterial3D = StandardMaterial3D.new()
		material.albedo_color = Color(String(colors[key]))
		material.roughness = 0.95
		if key == "glass":
			material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			material.albedo_color.a = 0.07
			material.cull_mode = BaseMaterial3D.CULL_DISABLED
			material.shading_mode = BaseMaterial3D.SHADING_MODE_PER_PIXEL
		if key == "mirror":
			material.metallic = 1.0
			material.roughness = 0.025
		result[key] = material
	var levels: Array = plan.scale.floor_y
	var heights: Array = plan.scale.ceiling_clear
	for key: String in ["wall", "tile", "tile_floor"]:
		var finish: ShaderMaterial = ShaderMaterial.new()
		finish.shader = preload("res://src/blockout/dorm_finish.gdshader")
		finish.set_shader_parameter("finish_mode", 0 if key=="wall" else 1)
		finish.set_shader_parameter("floors", Vector4(float(levels[0]),float(levels[1]),float(levels[2]),float(levels[3])))
		finish.set_shader_parameter("fifth_floor", float(levels[4]))
		finish.set_shader_parameter("heights", Vector4(float(heights[0]),float(heights[1]),float(heights[2]),float(heights[3])))
		finish.set_shader_parameter("green", Color(String(plan.finish.green)))
		finish.set_shader_parameter("white", Color(String(plan.finish.white)))
		var main_rect: Array = plan.main_rect
		var annex_rect: Array = plan.annex_rect
		finish.set_shader_parameter("main_bounds",Vector4(float(main_rect[0]),float(main_rect[1]),float(main_rect[2]),float(main_rect[3])))
		finish.set_shader_parameter("annex_bounds",Vector4(float(annex_rect[0]),float(annex_rect[1]),float(annex_rect[2]),float(annex_rect[3])))
		if key=="tile_floor":
			finish.set_shader_parameter("tile_color",Color("939d94"))
		result[key] = finish
	_apply_v3(result,plan)
	return result


const V3_DIR: String = "res://assets/textures/dorm_v3"
## stair_landing — площадки лестницы (верх — мозаика), stair_tread — ступени маршей-модулей (dorm_modules.gd).
const V3_SHADERS: Dictionary = {"wall":"dorm_wall_v3","reveal":"dorm_wall_v3","ceiling":"dorm_wall_v3",
	"floor":"dorm_parquet_v3","tile":"dorm_tiles_v3","tile_floor":"dorm_tiles_v3",
	"stair_landing":"dorm_wall_v3","stair_tread":"dorm_wall_v3"}
const V3_MODES: Dictionary = {"wall":0,"reveal":1,"ceiling":2,"tile":0,"tile_floor":1,"stair_landing":3,"stair_tread":4}


## Материалы v03 (краска, побелка, паркет, плитка — tools/dorm_modules, docs/design/dorm_modules.md) вместо
## черновых. Без карт assets/textures/dorm_v3 остаются черновые — проект запускается и без внешних текстур.
static func _apply_v3(result: Dictionary, plan: Dictionary) -> void:
	var textures: Dictionary = _v3_textures()
	if textures.is_empty():
		return
	var levels: Array = plan.scale.floor_y
	var heights: Array = plan.scale.ceiling_clear
	var main_rect: Array = plan.main_rect
	var annex_rect: Array = plan.annex_rect
	for key: String in V3_SHADERS:
		var material: ShaderMaterial = ShaderMaterial.new()
		material.shader = load("res://src/blockout/dorm_v3/%s.gdshader" % V3_SHADERS[key]) as Shader
		for uniform: Dictionary in material.shader.get_shader_uniform_list():
			var name: String = String(uniform.name)
			if int(uniform.type)!=TYPE_OBJECT:
				continue
			# Копия карты с выборкой без сглаживания — суффикс _n; шум износа — dorm_wear_noise.
			var file: String = "dorm_wear_noise" if name=="wear_noise" else name.trim_suffix("_n")
			if not textures.has(file):
				push_warning("dorm v3: нет карты "+file)
				continue
			material.set_shader_parameter(name,textures[file])
		if V3_MODES.has(key):
			material.set_shader_parameter("mode",int(V3_MODES[key]))
		material.set_shader_parameter("floors",Vector4(float(levels[0]),float(levels[1]),float(levels[2]),float(levels[3])))
		material.set_shader_parameter("fifth_floor",float(levels[4]))
		material.set_shader_parameter("heights",Vector4(float(heights[0]),float(heights[1]),float(heights[2]),float(heights[3])))
		material.set_shader_parameter("main_bounds",Vector4(float(main_rect[0]),float(main_rect[1]),float(main_rect[2]),float(main_rect[3])))
		material.set_shader_parameter("annex_bounds",Vector4(float(annex_rect[0]),float(annex_rect[1]),float(annex_rect[2]),float(annex_rect[3])))
		material.set_shader_parameter("paint_fraction",float(plan.finish.get("paint_lower_fraction",0.6667)))
		# Чем заменить материал при запекании VoxelGI (CPU не считает шейдер) — dorm_voxel_bake.gd.
		material.set_meta("dorm_gi",key)
		result[key] = material


static func _v3_textures() -> Dictionary:
	var found: Dictionary = {}
	var dir: DirAccess = DirAccess.open(V3_DIR)
	if dir==null:
		return found
	for file: String in dir.get_files():
		var path: String = V3_DIR+"/"+file.trim_suffix(".import").trim_suffix(".remap")
		var stem: String = path.get_file().get_basename()
		if found.has(stem) or not ResourceLoader.exists(path):
			continue
		found[stem] = load(path) as Texture2D
	for required: String in ["paint_peel_e","wash_peel_e","floor_wood","tile_masks","dorm_wear_noise"]:
		if not found.has(required):
			return {}
	return found
