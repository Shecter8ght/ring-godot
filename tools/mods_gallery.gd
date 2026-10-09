extends Node3D
## Витрина обвесов: стволы со сборками из data/weapons.json (presets) — сбоку, в три четверти и
## крупные планы узлов крепления (прицел, дульное, под цевьём, приклад), вид из глаза по основному
## и угловому прицелу. Для проверки посадки глазами.
## godot --path . res://tools/mods_gallery.tscn → docs/screens/mods_*.png

## Витрина → сборка (оружие и обвес по точкам крепления).
const KITS := {
	"pistol": "HG_03_TAC",
	"rifle": "AR_04_TAC",
	"rifle_b": "AR_06_MARKSMAN",
	"rifle_c": "AR_06_PATROL",
	"shotgun": "SG_04_BREACH",
	"bolt": "DMR_01_BASE",
}
## Крупные планы: точка на модели, куда смотреть, и отступ камеры.
const CLOSEUPS := {
	"pistol": [["optic", Vector3(0, 0.08, 0.0)], ["muzzle", Vector3(0, 0.06, 0.2)], ["under", Vector3(0, 0.0, 0.1)]],
	"rifle": [["optic", Vector3(0, 0.1, 0.05)], ["muzzle", Vector3(0, 0.052, 0.66)], ["under", Vector3(0, 0.0, 0.36)], ["stock", Vector3(0, 0.03, -0.2)]],
	"rifle_b": [["optic", Vector3(0, 0.11, 0.05)], ["muzzle", Vector3(0, 0.052, 0.61)], ["under", Vector3(0, 0.0, 0.36)]],
	"rifle_c": [["optic", Vector3(0, 0.11, 0.05)]],
	"shotgun": [["optic", Vector3(0, 0.1, 0.07)], ["muzzle", Vector3(0, 0.064, 0.78)], ["under", Vector3(0, 0.0, 0.35)]],
	"bolt": [["muzzle", Vector3(0, 0.062, 0.9)], ["under", Vector3(0, 0.0, 0.5)]],
}


func _ready() -> void:
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.09, 0.095, 0.1)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.55, 0.57, 0.6)
	e.ambient_light_energy = 0.5
	e.tonemap_mode = Environment.TONE_MAPPER_ACES
	e.ssao_enabled = true
	e.ssao_radius = 0.03
	e.glow_enabled = true
	env.environment = e
	add_child(env)
	var key := DirectionalLight3D.new()
	key.rotation_degrees = Vector3(-35, 60, 0)
	key.light_energy = 2.4
	key.shadow_enabled = true
	add_child(key)
	var rim := DirectionalLight3D.new()
	rim.rotation_degrees = Vector3(-20, -120, 0)
	rim.light_color = Color(0.7, 0.8, 1.0)
	rim.light_energy = 1.2
	add_child(rim)
	var cam := Camera3D.new()
	cam.near = 0.005
	add_child(cam)
	cam.current = true
	for kit in KITS:
		var weapon := String(kit).split("_")[0]
		var pr := WeaponDb.preset(String(KITS[kit]))
		var mods: Dictionary = pr.get("mods", {})
		var w := WeaponModels.build(String(pr.weapon), mods)
		add_child(w)
		for n in w.find_children("Flashlight*", "SpotLight3D", true, false):
			(n as SpotLight3D).visible = true
		for n in w.find_children("LaserBeam*", "Node3D", true, false):
			(n as Node3D).visible = true
		# вид справа (+X), целиком
		var len := 1.25 if weapon == "bolt" else (0.4 if weapon == "pistol" else 1.1)
		var mid := Vector3(0, 0.03, 0.05 if weapon == "pistol" else 0.22)
		cam.fov = 30.0
		cam.position = mid + Vector3(len * 1.7, 0.02, 0)
		cam.look_at(mid)
		await _frames(6)
		_save("mods_%s_side" % kit)
		# три четверти сверху-сзади-слева — видно линию прицеливания
		cam.position = mid + Vector3(-len * 0.9, len * 0.55, -len * 0.9)
		cam.look_at(mid)
		await _frames(4)
		_save("mods_%s_34" % kit)
		for c in CLOSEUPS.get(kit, []):
			var at: Vector3 = c[1]
			cam.fov = 26.0
			cam.position = at + Vector3(0.22, 0.06, -0.12)
			cam.look_at(at)
			await _frames(4)
			_save("mods_%s_%s" % [kit, c[0]])
		# вид из глаза вдоль линии прицеливания — для прицелов
		if mods.has("optic_primary"):
			var sh: float = w.get_meta("sight_h")
			cam.fov = 40.0
			cam.position = Vector3(0, sh, -0.3)
			cam.look_at(Vector3(0, sh, 1.0))
			await _frames(4)
			_save("mods_%s_eye" % kit)
		# угловой: ствол завален на крен кронштейна — глаз по линии углового прицела
		var so: Dictionary = {}
		for line: Variant in (w.get_meta("sights", {}) as Dictionary).values():
			if not is_zero_approx(float((line as Dictionary).get("roll", 0.0))):
				so = line
		if not so.is_empty():
			# точка линии — уже в осях модели; «верх» прицела — повёрнут кронштейном
			var cant := Basis(Vector3(0, 0, 1), float(so.roll))
			var eye := Vector3(float(so.x), float(so.h), 0.0)
			cam.fov = 40.0
			cam.position = eye + Vector3(0, 0, -0.3)
			cam.look_at(eye + Vector3(0, 0, 1.0), cant * Vector3.UP)
			await _frames(4)
			_save("mods_%s_eye_offset" % kit)
		w.queue_free()
		await _frames(2)
	get_tree().quit(0)


func _frames(n: int) -> void:
	for i in range(n):
		await get_tree().process_frame


func _save(n: String) -> void:
	get_viewport().get_texture().get_image().save_png(ProjectSettings.globalize_path("res://docs/screens/%s.png" % n))
	print("mods_gallery: ", n)
