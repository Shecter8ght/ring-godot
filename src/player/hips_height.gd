class_name HipsHeight
extends SkeletonModifier3D
## Высота таза под рост тела. Клипы Persona (persona_clips.res) ставят таз на её высоту в метрах; у другого
## тела на том же скелете mixamorig_* (мародёр v03 выше) положение таза из клипа умножается на отношение
## rest-высот таза — ступни остаются на полу стоя, в приседе и лёжа. Работает всегда (вдали, после смерти),
## поэтому отдельно от BodyMotion; первый модификатор скелета (CharacterAnimator ставит его в _ready).

## Высота таза Persona в rest, м (assets/models/characters/persona_animated.glb).
const PERSONA_HIPS_REST := 0.938

var _hips: int = -1
var _scale: float = 1.0
## Что записали в прошлый раз: дерево пишет положение каждый кадр, но если не записало (застыл для снимка,
## умер), повторно умножать нельзя.
var _written: Vector3 = Vector3.INF


func _ready() -> void:
	var sk := get_skeleton()
	if sk == null:
		return
	_hips = sk.find_bone("mixamorig_Hips")
	if _hips < 0:
		return
	var rest: float = sk.get_bone_global_rest(_hips).origin.length()
	_scale = rest / PERSONA_HIPS_REST if rest > 0.5 else 1.0


func scale_factor() -> float:
	return _scale


func _process_modification() -> void:
	var sk := get_skeleton()
	if sk == null or _hips < 0 or is_equal_approx(_scale, 1.0):
		return
	var p: Vector3 = sk.get_bone_pose_position(_hips)
	if p.is_equal_approx(_written):
		return
	p *= _scale
	_written = p
	sk.set_bone_pose_position(_hips, p)
