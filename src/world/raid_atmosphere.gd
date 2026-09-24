class_name RaidAtmosphere
extends Node
## Условия рейда на уровне (RaidConditions.current): солнце или луна, небо, окружение; режим
## электричества ТЦ — огни и светильники (группы mall_lights, mall_lamps), прожекторы дворов.
## И видимость для мародёров: как далеко видно того, кто стоит в точке (освещённость места —
## улица/помещение, есть ли свет, и его собственный фонарь). Создаёт SectorLevel.

static var current: RaidAtmosphere

var _indoor_cache: Dictionary = {}


func _enter_tree() -> void:
	current = self


func _exit_tree() -> void:
	if current == self:
		current = null


func apply() -> void:
	var c := RaidConditions.current
	var t := RaidConditions.spec("time")
	var level := get_parent()
	var sun := level.get_node_or_null("Sun") as DirectionalLight3D
	if sun:
		# курс солнца — как в сцене; высота, цвет и сила — по времени
		var yaw := sun.global_rotation.y
		sun.global_rotation = Vector3(-deg_to_rad(float(t.sun_elev)), yaw, 0.0)
		sun.light_energy = float(t.sun_energy)
		sun.light_color = t.sun_color
		sun.light_volumetric_fog_energy = 1.6 if String(c.time) != "night" else 0.4
	var we := level.find_child("WorldEnvironment", false, false) as WorldEnvironment
	if we and we.environment:
		var e := we.environment
		e.ambient_light_energy = 0.8 * float(t.ambient)
		e.background_energy_multiplier = float(t.sky)
		if e.sky and e.sky.sky_material is PhysicalSkyMaterial:
			(e.sky.sky_material as PhysicalSkyMaterial).energy_multiplier = float(t.sky)
		e.tonemap_exposure = float(t.get("exposure", 1.0))
	_apply_power(String(c.power))


## Электричество ТЦ: есть — всё горит; нет — темно; аварийное — каждый третий огонь, красный,
## тусклый, часть мигает. Можно менять по ходу рейда (события) — исходное запоминается.
func apply_power(power: String) -> void:
	_apply_power(power)


func _apply_power(power: String) -> void:
	var i := 0
	for n in get_tree().get_nodes_in_group("mall_lights"):
		var l := n as Light3D
		if not l.has_meta("orig"):
			l.set_meta("orig", [l.visible, l.light_color, l.light_energy, (l as OmniLight3D).omni_range if l is OmniLight3D else 0.0])
		var o: Array = l.get_meta("orig")
		l.visible = bool(o[0])
		l.light_color = o[1]
		l.light_energy = float(o[2])
		if l is OmniLight3D:
			(l as OmniLight3D).omni_range = float(o[3])
		l.remove_meta("flicker")
		match power:
			"off":
				l.visible = false
			"emergency":
				l.visible = i % 3 == 0
				l.light_color = Color(1.0, 0.18, 0.12)
				l.light_energy = 1.1
				if l is OmniLight3D:
					(l as OmniLight3D).omni_range = 9.0
				if i % 9 == 0:
					l.set_meta("flicker", true)
		i += 1
	_sync_panels()
	for n in get_tree().get_nodes_in_group("mall_lamps"):
		if n.has_meta("base_colors"):
			continue
		var mm := n as GeometryInstance3D
		if not mm.has_meta("orig_mat"):
			mm.set_meta("orig_mat", mm.material_override)
		var base := mm.get_meta("orig_mat") as StandardMaterial3D
		if base == null:
			continue
		var m := base.duplicate() as StandardMaterial3D
		match power:
			"off":
				m.emission_enabled = false
			"emergency":
				m.emission = Color(0.9, 0.15, 0.1)
				m.emission_energy_multiplier = 0.6
		mm.material_override = m
	# прожекторы дворов и вывески — тоже от сети ТЦ
	var lights := get_parent().find_child("Lights", true, false)
	if lights:
		for n in lights.get_children():
			if n is SpotLight3D:
				(n as SpotLight3D).visible = power == "on"
	for sign in get_parent().find_children("Signs", "Node3D", true, false):
		for l in sign.find_children("*", "Label3D", true, false):
			var lb := l as Label3D
			if not lb.has_meta("orig"):
				lb.set_meta("orig", lb.modulate)
			var om: Color = lb.get_meta("orig")
			lb.modulate = om if power == "on" else om.darkened(0.8 if power == "off" else 0.6)


var _flick_t: float = 0.0


func _process(delta: float) -> void:
	if String(RaidConditions.current.power) != "emergency":
		return
	_flick_t += delta
	if _flick_t < 0.07:
		return
	_flick_t = 0.0
	for n in get_tree().get_nodes_in_group("mall_lights"):
		var l := n as Light3D
		if l.visible and l.has_meta("flicker"):
			l.light_energy = 1.1 if randf() > 0.25 else randf_range(0.0, 0.4)
	_sync_panels()


## Панели светильников повторяют свой огонь: погас — тёмная, аварийный — красная, мигает вместе
## с ним (у огня meta "lamp" — номер панели в MultiMesh).
func _sync_panels() -> void:
	var panels: Array = []
	for n in get_tree().get_nodes_in_group("mall_lamps"):
		if n is MultiMeshInstance3D and n.has_meta("base_colors"):
			panels.append(n)
	if panels.is_empty():
		return
	for n in get_tree().get_nodes_in_group("mall_lights"):
		var l := n as Light3D
		if not l.has_meta("lamp"):
			continue
		var i := int(l.get_meta("lamp"))
		for p in panels:
			var mmi := p as MultiMeshInstance3D
			var base: Array = mmi.get_meta("base_colors")
			if i >= base.size():
				continue
			var c := Color.BLACK
			if l.visible:
				var o: Array = l.get_meta("orig", [true, l.light_color, l.light_energy])
				var k := l.light_energy / maxf(float(o[2]), 0.001)
				c = (Color(base[i]) if l.light_color == o[1] else l.light_color * 0.55) * clampf(k, 0.0, 1.5)
			mmi.multimesh.set_instance_color(i, c)


# ---------------------------------------------------------------- видимость

## Под крышей (над точкой — перекрытие ТЦ).
func is_indoor(p: Vector3) -> bool:
	var key := Vector3i(int(floor(p.x / 2.0)), int(floor(p.y / 2.0)), int(floor(p.z / 2.0)))
	if _indoor_cache.has(key):
		return bool(_indoor_cache[key])
	var world := get_viewport().find_world_3d()
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 1.6, p + Vector3.UP * 14.0, Hitscan.LAYER_WORLD)
	var hit := not world.direct_space_state.intersect_ray(q).is_empty()
	_indoor_cache[key] = hit
	return hit


## Темно ли в точке (фонари мародёров, ПНВ): ночь на улице или помещение без нормального света.
func is_dark(p: Vector3) -> bool:
	var c := RaidConditions.current
	if is_indoor(p):
		return String(c.power) != "on"
	return String(c.time) == "night"


## Дальше скольких метров мародёр не разглядит того, кто стоит в точке p; own_light — у него
## включён фонарь (выдаёт издалека).
func view_distance(p: Vector3, own_light: bool, light_k: float = 1.0, laser: bool = false) -> float:
	var c := RaidConditions.current
	var d := float(RaidConditions.spec("time").view)
	if is_indoor(p):
		var ind: Dictionary = Balance.AI_VIEW_INDOOR
		match String(c.power):
			"on":
				d = float(ind.lit)
			"emergency":
				d = float(ind.emergency)
			_:
				d = float(ind.dark_day if String(c.time) != "night" else ind.dark_night)
	d *= float(RaidConditions.spec("weather").get("view", 1.0)) if not is_indoor(p) else 1.0
	# в свете ракеты видно всех, кто рядом с ней
	for f in get_tree().get_nodes_in_group("flares"):
		var fl := f as ThrownLight
		if fl and fl.global_position.distance_to(p) <= fl.radius():
			d = maxf(d, Balance.FLARE_LIT_VIEW)
			break
	if own_light:
		d = maxf(d, Balance.AI_VIEW_FLASHLIGHT * light_k)
	elif laser and d < Balance.AI_VIEW_LASER:
		d = Balance.AI_VIEW_LASER
	return d
