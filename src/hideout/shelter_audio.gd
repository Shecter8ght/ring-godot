extends Node
## У готового интерьера только звуковой мост: источники расставлены автором в сцене.
## Общий рубильник управляет гулом; улучшения остаются прежним модулем Upgrades.

@onready var _generator: AudioStreamPlayer3D = $GeneratorHum
var _last_power: bool = false

func _ready() -> void:
	_generator.bus = &"Ambient"
	_generator.stream = Audio.hum_loop()
	var ventilation: AudioStreamPlayer3D = $VentilationHum
	ventilation.stream = Audio.hum_loop()
	ventilation.bus = &"Ambient"
	ventilation.play()
	for activity: String in ["Tv","Radio"]:
		var source: HideoutActivity = get_node("../../Activities/"+activity) as HideoutActivity
		if source._sound:
			source._sound.bus = &"Ambient"

func _exit_tree() -> void:
	_generator.stop()
	($VentilationHum as AudioStreamPlayer3D).stop()

func _process(_delta: float) -> void:
	var power: ShelterPower = get_node_or_null("../../Gameplay/GeneratorPower") as ShelterPower
	var powered: bool = power.enabled if power else Upgrades.level("generator") > 0
	if powered != _last_power:
		_last_power = powered
		if powered:
			_generator.play()
		else:
			_generator.stop()
