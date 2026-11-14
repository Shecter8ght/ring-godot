extends Node
## АСТЕН-919 (wpn_hg_02, своя модель вместо прежнего Glock 17 Gen5 из GLB): детали без курка/предохранителя/глушителя,
## метки, 17 патронов, LOD1, гайка резьбы прячется под насадкой, процедурные насадки на срезе модели и запасной
## процедурный пистолет; ПМ рядом не сломан.

const GLOCK_ID: String = "wpn_hg_02"
const PM_ID: String = "wpn_hg_01"
const SUP_ID: String = "muzzle_supp_9_01"
const MAG_CAPACITY: int = 17
const EPS: float = 0.0015
const MUZZLE_AT: Vector3 = Vector3(0.0, 0.0652, 0.1692)
const SIGHT_H: float = 0.0803
var _fails: int = 0
var _checks: int = 0


func _ready() -> void:
	_run.call_deferred()


func _check(label: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	print("  [%s] %s %s" % ["ok" if ok else "FAIL", label, detail])
	if not ok:
		_fails += 1


func _visible_rounds(rig: WeaponRig) -> int:
	var rounds: Node3D = rig.part("Magazine").find_child("Rounds", true, false) as Node3D if rig.part("Magazine") else null
	var count: int = 0
	if rounds:
		for child: Node in rounds.get_children():
			if child is Node3D and (child as Node3D).visible:
				count += 1
	return count


func _triangles(node: Node) -> int:
	var count: int = 0
	if node is MeshInstance3D and (node as MeshInstance3D).mesh:
		var mesh: Mesh = (node as MeshInstance3D).mesh
		for surface: int in range(mesh.get_surface_count()):
			var arrays: Array = mesh.surface_get_arrays(surface)
			var indices: PackedInt32Array = arrays[Mesh.ARRAY_INDEX] if arrays[Mesh.ARRAY_INDEX] is PackedInt32Array else PackedInt32Array()
			var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
			count += (indices.size() if not indices.is_empty() else vertices.size()) / 3
	for child: Node in node.get_children():
		count += _triangles(child)
	return count


func _common(rig: WeaponRig, model: Node3D, label: String, rounds_total: int) -> void:
	_check(label + ": WeaponRig с деталями", rig != null and rig.has_parts())
	if rig == null:
		return
	for name_: String in ["Frame", "Slide", "Barrel", "Trigger", "SlideStop", "MagCatch", "Magazine"]:
		_check(label + ": деталь " + name_, rig.part(name_) != null)
	for name_: String in ["Hammer", "Safety", "Suppressor"]:
		_check(label + ": детали нет и не нужна — " + name_, rig.part(name_) == null)
	_check(label + ": своего глушителя нет", not rig.has_suppressor_part())
	var muzzle: Vector3 = model.get_meta("muzzle", Vector3.ZERO)
	_check(label + ": meta muzzle на срезе ствола", muzzle.distance_to(MUZZLE_AT) < EPS, str(muzzle))
	_check(label + ": meta sight_h по мушке и целику", absf(float(model.get_meta("sight_h", 0.0)) - SIGHT_H) < EPS, str(model.get_meta("sight_h", 0.0)))
	_check(label + ": ads_z из данных", is_equal_approx(float(model.get_meta("ads_z", 0.0)), 0.36))
	_check(label + ": метки хвата", model.find_child("RightGrip", true, false) != null and model.find_child("LeftGrip", true, false) != null)
	_check(label + ": магазин распознаётся игрой", rig.part("Magazine").get_meta("part", "") == "mag")
	rig.set_ammo_state(MAG_CAPACITY)
	_check(label + ": 17 в оружии — в магазине видно 16 (один в патроннике)", _visible_rounds(rig) == mini(rounds_total, MAG_CAPACITY - 1), str(_visible_rounds(rig)))
	rig.set_ammo_state(MAG_CAPACITY + 1)
	_check(label + ": 17+1 — магазин полный", _visible_rounds(rig) == mini(rounds_total, MAG_CAPACITY), str(_visible_rounds(rig)))
	rig.set_ammo_state(1)
	_check(label + ": один в патроннике — магазин пуст", _visible_rounds(rig) == 0)
	rig.set_ammo_state(0)
	_check(label + ": на нуле затвор на задержке", rig.is_slide_locked())
	rig.set_ammo_state(MAG_CAPACITY + 1)
	var slide_rest: Vector3 = rig.part("Slide").position
	var trigger_rest: Basis = rig.part("Trigger").basis
	rig.pose_action("shot", 0.42)
	var travel: float = slide_rest.z - rig.part("Slide").position.z
	_check(label + ": затвор откатывается назад на ход", absf(travel - 0.043) < 0.001, str(travel))
	_check(label + ": спуск поворачивается", not rig.part("Trigger").basis.is_equal_approx(trigger_rest))
	_check(label + ": дульный срез едет с затвором и не теряется", model.has_meta("muzzle"))
	rig.cancel_action()
	_check(label + ": затвор вернулся", rig.part("Slide").position.is_equal_approx(slide_rest))
	var mag_rest: Vector3 = rig.part("Magazine").position
	rig.pose_action("reload", 0.3, true)
	_check(label + ": магазин уходит вниз по оси рукояти", rig.part("Magazine").position.y < mag_rest.y - 0.05, str(rig.part("Magazine").position))
	rig.cancel_action()
	_check(label + ": отмена возвращает магазин", rig.part("Magazine").position.is_equal_approx(mag_rest) and rig.part("Magazine").visible)
	# Без своей детали подтверждённый глушитель не уводит срез и не ломает действие.
	rig.set_suppressed(true)
	_check(label + ": set_suppressed без детали — срез на месте", (model.get_meta("muzzle", Vector3.ZERO) as Vector3).distance_to(MUZZLE_AT) < EPS)
	rig.play_suppressor(false, 0.2)
	rig.advance_action(0.25)
	rig.cancel_action()
	rig.set_suppressed(false)
	_check(label + ": действие глушителя без детали не застревает", not rig.is_busy())


## Руки от первого лица — клипы владельца (tools/asten919/clips/export_viewmodel.py, ViewmodelClips): метки в тех же
## осях, что у модели в мире, все роли клипов есть, патрон в стволе не виден в магазине, затвор на задержке, глушитель.
func _viewmodel() -> void:
	_check("клипы рук: сцена есть", ViewmodelClips.available(GLOCK_ID))
	if not ViewmodelClips.available(GLOCK_ID):
		return
	var vm: ViewmodelClips = ViewmodelClips.create(GLOCK_ID, {})
	add_child(vm)
	var muzzle: Vector3 = vm.frame.get_meta("muzzle", Vector3.ZERO)
	_check("клипы рук: срез в осях рукояти как у модели в мире", muzzle.distance_to(MUZZLE_AT) < 0.004, str(muzzle))
	_check("клипы рук: высота прицельной линии", absf(float(vm.frame.get_meta("sight_h", 0.0)) - SIGHT_H) < 0.004, str(vm.frame.get_meta("sight_h", 0.0)))
	var anim: AnimationPlayer = vm.find_children("*", "AnimationPlayer", true, false)[0] as AnimationPlayer
	var missing: Array[String] = []
	for role: Variant in (vm.config.get("clips", {}) as Dictionary).values():
		if not anim.has_animation(String(role)):
			missing.append(String(role))
	for spare: Variant in vm.config.get("spare_clips", []):
		if not anim.has_animation(String(spare)):
			missing.append(String(spare))
	for service: String in ["follower_by_rounds", "bolt_travel", "slide_hold"]:
		if not anim.has_animation(service):
			missing.append(service)
	_check("клипы рук: все роли и служебные таблицы", missing.is_empty(), str(missing))
	var swap: float = vm.swap_fraction("reload")
	var swap_empty: float = vm.swap_fraction("reload_empty")
	_check("клипы рук: кадр подмены магазина внутри клипа", swap > 0.2 and swap < 0.6 and swap_empty > 0.2 and swap_empty < 0.6, "%.3f / %.3f" % [swap, swap_empty])
	_check("клипы рук: сброс старого магазина у быстрой", int((vm.config.get("drop_frame", {}) as Dictionary).get("reload_fast", -1)) > 0)
	var rounds: int = 0
	while vm.find_child("Round_%02d" % (rounds + 1), true, false) != null:
		rounds += 1
	_check("клипы рук: патронов в магазине модели", rounds == MAG_CAPACITY, str(rounds))
	_check("клипы рук: 17+1 — в магазине видно 17, один в стволе — пусто", vm._in_mag(MAG_CAPACITY + 1) == MAG_CAPACITY and vm._in_mag(1) == 0 and vm._in_mag(0) == 0)
	var skel: Skeleton3D = vm._weapon_skel
	var slide: int = skel.find_bone("Slide") if skel else -1
	_check("клипы рук: затвор ведёт таблица bolt_travel", slide >= 0 and vm._bolt_bones.has(slide))
	if slide >= 0:
		vm.preview_reload("idle", 0.0, "*")
		var closed: Vector3 = skel.get_bone_pose_position(slide)
		vm._pose_overrides(0, 0.0, false, true)
		var travel: float = skel.get_bone_pose_position(slide).distance_to(closed)
		_check("клипы рук: пусто — затвор на задержке", travel > 0.03 and travel < 0.06, "%.4f м" % travel)
	var cap: MeshInstance3D = vm.find_child("MuzzleDevice", true, false) as MeshInstance3D
	_check("клипы рук: заглушка резьбы видна без обвеса", cap != null and cap.visible)
	vm.free()
	var vm_sup: ViewmodelClips = ViewmodelClips.create(GLOCK_ID, {"muzzle": {"id": SUP_ID}})
	add_child(vm_sup)
	var sup_cap: MeshInstance3D = vm_sup.find_child("MuzzleDevice", true, false) as MeshInstance3D
	_check("клипы рук: глушитель прячет заглушку резьбы", sup_cap != null and not sup_cap.visible)
	var sup_muzzle: Vector3 = vm_sup.frame.get_meta("muzzle", Vector3.ZERO)
	_check("клипы рук: срез с глушителем вынесен вперёд", sup_muzzle.z > MUZZLE_AT.z + 0.1 and absf(sup_muzzle.y - MUZZLE_AT.y) < 0.004, str(sup_muzzle))
	vm_sup.free()


func _run() -> void:
	print("glock_test:")
	var model: Node3D = WeaponModels.build(GLOCK_ID)
	add_child(model)
	var rig: WeaponRig = WeaponRig.find_on(model)
	_common(rig, model, "LOD0", MAG_CAPACITY)
	_check("LOD0: бюджет треугольников", _triangles(model) <= 40000, str(_triangles(model)))
	model.free()
	var low: Node3D = WeaponModels.build(GLOCK_ID, {}, 1)
	add_child(low)
	var low_rig: WeaponRig = WeaponRig.find_on(low)
	_check("LOD1: в модели нет деталей LOD0", low.find_child("ASTEN919_LOD1", true, false) != null and low.find_child("Round_02", true, false) == null)
	_common(low_rig, low, "LOD1", 1)
	_check("LOD1: бюджет треугольников", _triangles(low) <= 5000, str(_triangles(low)))
	low.free()
	# Процедурный глушитель 9 мм встаёт на срез модели, и риг не возвращает срез на голый ствол.
	var suppressed: Node3D = WeaponModels.build(GLOCK_ID, {"muzzle": {"id": SUP_ID}})
	add_child(suppressed)
	var sup_rig: WeaponRig = WeaponRig.find_on(suppressed)
	var sup_muzzle: Vector3 = suppressed.get_meta("muzzle", Vector3.ZERO)
	_check("глушитель 9 мм: срез вынесен вперёд по оси ствола", sup_muzzle.z > MUZZLE_AT.z + 0.1 and absf(sup_muzzle.y - MUZZLE_AT.y) < EPS, str(sup_muzzle))
	var cap: MeshInstance3D = suppressed.find_child("MuzzleDevice_Mesh", true, false) as MeshInstance3D
	_check("глушитель 9 мм: гайка резьбы ствола спрятана", cap != null and not cap.visible)
	if sup_rig:
		sup_rig.set_suppressed(true)
		sup_rig.pose_action("shot", 0.42)
		sup_rig.cancel_action()
		_check("глушитель 9 мм: поза рига не сбрасывает срез", (suppressed.get_meta("muzzle", Vector3.ZERO) as Vector3).is_equal_approx(sup_muzzle))
	suppressed.free()
	# Отсутствующий файл — процедурный пистолет, как требует правило ассетов.
	var definition: Dictionary = WeaponDb.weapon(GLOCK_ID)
	var asset_path: String = String(definition.get("asset", ""))
	definition["asset"] = "res://assets/models/weapons/asten919/absent_for_glock_test.glb"
	var fallback: Node3D = WeaponModels.build(GLOCK_ID, {"muzzle": {"id": SUP_ID}})
	definition["asset"] = asset_path
	_check("без GLB работает процедурный запасной вариант", fallback != null and fallback.has_meta("muzzle") and WeaponRig.find_on(fallback) == null)
	fallback.free()
	_viewmodel()
	# ПМ: своя ветка PM_LOD1 и свой глушитель по-прежнему находятся.
	var pm: Node3D = WeaponModels.build(PM_ID, {}, 1)
	add_child(pm)
	var pm_rig: WeaponRig = WeaponRig.find_on(pm)
	_check("ПМ LOD1: риг, курок, предохранитель, глушитель", pm_rig != null and pm_rig.has_parts() and pm_rig.part("Hammer") != null and pm_rig.part("Safety") != null and pm_rig.has_suppressor_part())
	pm.free()
	print("glock_test: проверок %d, провалено %d" % [_checks, _fails])
	get_tree().quit(1 if _fails > 0 else 0)
