class_name FlashlightPulse
extends Node
## Modulates energy, leaving visibility to Player/CameraRig. Condition remains independent.

var hz: float = 6.0
var duty: float = 0.5


static func factor_at(seconds: float, frequency: float = 6.0, on_fraction: float = 0.5) -> float:
	return 1.0 if fposmod(seconds * frequency, 1.0) < clampf(on_fraction, 0.0, 1.0) else 0.0


func _ready() -> void:
	process_priority = 100


func _process(_delta: float) -> void:
	apply_at(Time.get_ticks_msec() * 0.001)


func apply_at(seconds: float) -> void:
	var light: SpotLight3D = get_parent() as SpotLight3D
	if not light:
		return
	var phase: float = factor_at(seconds, hz, duty)
	light.light_energy = float(light.get_meta("condition_energy", 3.2)) * float(light.get_meta("condition_k", 1.0)) * phase
	var glow: Node3D = light.get_node_or_null("Glow") as Node3D
	if glow:
		glow.visible = phase > 0.0 and float(light.get_meta("condition_k", 1.0)) > 0.0
	for child: Node in light.get_children():
		if child is WetBounce:
			(child as WetBounce).visible = phase > 0.0
