class_name HandheldFlashlight
extends Node
## Explicit owner socket takes precedence; an editable starter grip supplies the default.
## Player.handheld_flashlight_requested(id, on) requests the owner's equip/stow animation.

var actor: Player
var holder: Node3D
var model: Node3D
var _built_id: String = ""
var _fps_weapon: Node3D
var _world_weapon: Node3D
var _pose_busy: bool = false


func prepare_fps(weapon: Node3D, arms: FirstPersonArms) -> void:
	if is_instance_valid(_fps_weapon) and _fps_weapon != weapon:
		DozorHandGrip.apply(_fps_weapon, false, actor.weapon_id)
	_fps_weapon = weapon
	var action: Dictionary = arms._actions.get("Left", {})
	_pose_busy = float(action.get("weight", 0.0)) > 0.01 or actor.reload_timer > 0.0
	var active: bool = actor.handheld_light_on and String(WeaponDb.weapon(actor.weapon_id).get("class", "")) == "PISTOL" and not _pose_busy
	if is_instance_valid(holder) and not holder.has_meta("dozor_starter"):
		return # The owner's later custom grip owns its socket.
	var socket: Node3D = DozorHandGrip.apply(weapon, active, actor.weapon_id)
	if socket:
		socket.set_meta("first_person", true)
		DozorHandGrip.follow_edits(weapon, arms, socket)
		if holder != socket: bind(socket)
	elif is_instance_valid(model):
		model.visible = false


func bind(socket: Node3D) -> void:
	_clear_model()
	holder = socket


func toggle() -> String:
	if actor.handheld_light_on:
		stow()
		return "выкл"
	var rec: Dictionary = DozorGear.carried(actor.inventory.items + actor.inventory.pocket, actor.handheld_light_id)
	if rec.is_empty():
		return "нет"
	actor.handheld_light_id = String(rec.id)
	actor.handheld_light_on = true
	actor.handheld_flashlight_requested.emit(actor.handheld_light_id, true)
	return "вкл"


func stow() -> void:
	if actor.handheld_light_on:
		actor.handheld_light_on = false
		actor.handheld_flashlight_requested.emit(actor.handheld_light_id, false)
	_clear_model()
	for weapon: Node3D in [_fps_weapon, _world_weapon]:
		if is_instance_valid(weapon): DozorHandGrip.apply(weapon, false, actor.weapon_id)


func emitting() -> bool:
	return is_instance_valid(model) and model.is_visible_in_tree() and actor.handheld_light_on


func _clear_model() -> void:
	if is_instance_valid(model):
		model.free()
	model = null
	_built_id = ""


func _process(_delta: float) -> void:
	var pistol: bool = String(WeaponDb.weapon(actor.weapon_id).get("class", "")) == "PISTOL"
	var active: bool = pistol and actor.is_alive() and not actor.grenade_equipped and not actor.on_ladder
	var rec: Dictionary = {}
	if actor.is_local():
		rec = DozorGear.carried(actor.inventory.items + actor.inventory.pocket, actor.handheld_light_id)
		if not active or rec.is_empty() or String(rec.get("id", "")) != actor.handheld_light_id:
			stow()
			return
	if not active or not actor.handheld_light_on or not DozorGear.is_flashlight(actor.handheld_light_id):
		_clear_model()
		return
	var world: Node3D = actor._weapon_model
	if is_instance_valid(_world_weapon) and _world_weapon != world:
		DozorHandGrip.apply(_world_weapon, false, actor.weapon_id)
	_world_weapon = world
	if is_instance_valid(world):
		var socket: Node3D = DozorHandGrip.apply(world, true, actor.weapon_id)
		if socket and (not actor.is_local() or not actor.ads) and (not is_instance_valid(holder) or holder.has_meta("dozor_starter")) and holder != socket:
			bind(socket)
	if not is_instance_valid(holder):
		_clear_model()
		return
	if _built_id != actor.handheld_light_id:
		_clear_model()
		_built_id = actor.handheld_light_id
		model = DozorAsset.flashlight(String(DozorGear.VARIANTS[_built_id]))
		holder.add_child(model)
		if bool(holder.get_meta("first_person", false)):
			for node: Node in model.find_children("*", "MeshInstance3D", true, false):
				var mesh: MeshInstance3D = node as MeshInstance3D
				mesh.layers = 2
				mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		WeaponMods._light_node(model, {"mount": "handheld"}, WeaponDb.attachment(_built_id), Vector3(0, 0, 0.0805))
	model.visible = actor.reload_timer <= 0.0 and not _pose_busy and holder.is_visible_in_tree()
	var light: SpotLight3D = model.find_child("Flashlight*", true, false) as SpotLight3D
	if light:
		if bool(holder.get_meta("first_person", false)) and not light.has_meta("vm_local"):
			light.set_meta("vm_local", light.transform)
			light.set_meta("own", true)
			light.shadow_caster_mask = 0xFFFFF & ~Player.OWN_BODY_LAYER
		light.visible = model.visible
		var k: float = WeaponCondition.effectiveness(rec) if not rec.is_empty() else actor.handheld_light_condition
		light.set_meta("condition_k", k)
		if not light.has_node("Pulse"):
			light.light_energy = float(light.get_meta("condition_energy")) * k
		if actor.is_local():
			actor.handheld_light_condition = k


func _exit_tree() -> void:
	_clear_model()
