extends Node
## У готового интерьера только звуковой мост: источники расставлены автором в сцене.
## Общий рубильник управляет гулом; улучшения остаются прежним модулем Upgrades.

@onready var _generator: AudioStreamPlayer3D = $GeneratorHum
var _last_power: bool = false

func _ready() -> void:
	# Дополнительные room FX идут в существующую Ambient: настройки громкости сохраняются.
	for spec: Array in [["ShelterLiving","living"],["ShelterUtility","utility"]]:
		var index: int = AudioServer.get_bus_index(String(spec[0]))
		if index < 0:
			AudioServer.add_bus()
			index = AudioServer.bus_count-1
			AudioServer.set_bus_name(index,String(spec[0]))
			AudioServer.set_bus_send(index,"Ambient")
			AudioServer.add_bus_effect(index,load("res://levels/shelter/materials/audio_"+String(spec[1])+".tres") as AudioEffectReverb)
	_generator.bus = &"ShelterUtility"
	_generator.stream = Audio.hum_loop()
	var ventilation: AudioStreamPlayer3D = $VentilationHum
	ventilation.stream = Audio.hum_loop()
	ventilation.bus = &"ShelterUtility"
	ventilation.play()
	for activity: String in ["Tv","Radio"]:
		var source: HideoutActivity = get_node("../../Activities/"+activity) as HideoutActivity
		if source._sound:
			source._sound.bus = &"ShelterLiving"

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
