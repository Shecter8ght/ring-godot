class_name HandheldFlashlight
extends Node
## No pose or guessed socket. The owner's hand rig binds an authored +Z holder explicitly.
## Player.handheld_flashlight_requested(id, on) requests the owner's equip/stow animation.

var actor: Player
var holder: Node3D
var model: Node3D
var _built_id: String = ""


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
	if not is_instance_valid(holder):
		_clear_model()
		return
	if _built_id != actor.handheld_light_id:
		_clear_model()
		_built_id = actor.handheld_light_id
		model = DozorAsset.flashlight(String(DozorGear.VARIANTS[_built_id]))
		holder.add_child(model)
		WeaponMods._light_node(model, {"mount": "handheld"}, WeaponDb.attachment(_built_id), Vector3(0, 0, 0.0805))
	model.visible = actor.reload_timer <= 0.0 and holder.is_visible_in_tree()
	var light: SpotLight3D = model.find_child("Flashlight*", true, false) as SpotLight3D
	if light:
		light.visible = model.visible
		var k: float = WeaponCondition.effectiveness(rec) if not rec.is_empty() else actor.handheld_light_condition
		light.set_meta("condition_k", k)
		if not light.has_node("Pulse"):
			light.light_energy = float(light.get_meta("condition_energy")) * k
		if actor.is_local():
			actor.handheld_light_condition = k


func _exit_tree() -> void:
	_clear_model()
