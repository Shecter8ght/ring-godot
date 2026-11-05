class_name CharacterAnimator
extends Node
## Тело игрока и любого NPC на модели Persona (скелет Mixamo). Тело ведёт физика, клипы коллизию
## не двигают. Одно дерево анимации (AnimationTree) на всех — у каждого свои параметры:
## - передвижение — набор клипов на стойку и оружие (_set_specs): направления смешиваются (у автомата
##   8, у пистолета и без оружия 4), ходьба, бег и спринт — по скорости. Все клипы набора идут в одной
##   фазе шага (с левой ноги) и с той частотой, при которой ступни не скользят: скорость, число шагов и
##   постановка ноги у каждого клипа замерены (data/character_gait.json, tools/measure_gait.gd);
## - действия (перезарядка, достать оружие, граната) — верх тела поверх ходьбы, ноги идут дальше;
## - позы целиком (лёжа, тяжело ранен, смерть, прыжок) — две цепочки по очереди, переход всегда плавный.
## Поверх клипов — BodyMotion (src/player/body_motion.gd): корпус догоняет поворот, ноги отстают,
## взгляд вверх-вниз, выглядывание, наклон на разгоне, дыхание, отдача, вздрагивание.

const CLIPS := "res://assets/models/characters/persona_clips.res"
const GAIT := "res://data/character_gait.json"
## Оружие в правой руке: кость mixamorig_RightHand → узел Grip со смещением семейства рукояток
## (data/weapon_sockets.json, tools/bake_weapon_sockets.gd). Модель вешают Player / Marauder.
const SOCKETS := "res://data/weapon_sockets.json"
## На время этих клипов оружие прячется: рука занята (бросок, подобрать с пола).
const HIDE_WEAPON := ["grenade_throw", "pickup", "prone_throw"]
## В этих клипах левая рука уходит с цевья (магазин, граната, достать / убрать) — ИК отпускает её.
const FREE_LEFT_HAND := ["pistol_reload", "rifle_reload", "prone_reload", "grenade_throw", "prone_throw", "pickup", "rifle_draw", "pistol_draw", "rifle_holster"]
const DIRS8 := ["f", "fl", "l", "bl", "b", "br", "r", "fr"]
## Действия верхом тела поверх ходьбы и стойки и действия всем телом (стоя на месте).
const UPPER_ACTS := ["rifle_reload", "pistol_reload", "pistol_draw", "rifle_draw", "rifle_holster", "grenade_throw"]
const FULL_ACTS := ["pickup", "grenade_throw"]
## Позы целиком (узлы цепочек поз). prone_crawl_f — ползком вперёд: клип «назад» задом наперёд.
## Последние — застывшие позы для снимков (hold_pose).
const POSES := ["prone_aim", "prone_move_b", "prone_crawl_f", "prone_fire", "prone_reload", "prone_throw",
	"downed_fall", "downed_fall_still", "jump_loop", "death", "death_front", "death_back", "death_right",
	"death_head_front", "death_head_back", "death_crouch", "death_crouch_head", "death_prone", "death_blast",
	"pistol_idle", "rifle_idle", "rifle_aim", "r8_idle", "r8_idle_aim", "unarmed_idle"]
const LOOP_POSES := ["prone_aim", "prone_move_b", "prone_crawl_f", "jump_loop"]
const POSE_CLIP := {"prone_crawl_f": "prone_move_b"}

## Общее на всех персонажей: библиотека клипов, замеры шага, дерево и кольца направлений.
static var _lib: AnimationLibrary
static var _gait: Dictionary = {}
static var _tree_root: AnimationNodeBlendTree
## набор → [кольцо ходьбы, бега, спринта]; кольцо — точки направлений по углу (_ring_entry)
static var _rings: Dictionary = {}
static var _specs: Dictionary = {}
static var _sockets: Dictionary = {}
static var _warned_old_clips: bool = false

var _actor: CharacterBody3D
var _body: Node3D
var _model: Node3D
var _tree: AnimationTree
var _skeleton: Skeleton3D
var _motion: BodyMotion
var _hips_height: HipsHeight
var _last_position: Vector3
## Скорость движения (_physics_process), сглаженная по времени. Работает и для чужих тел.
var _vel: Vector3 = Vector3.ZERO
var _last_event_seq: int = 0
## Действие, которое играет сейчас («» — нет): верх тела, всё тело или поза лёжа (_one_shot_kind).
var _one_shot: String = ""
var _one_shot_kind: String = ""
var _one_shot_t: float = 0.0
## Что видно сейчас (набор и направление или поза) — для тестов и отладки.
var _current: String = ""
var _set: String = ""
## Направление шага в осях ног, рад: 0 — вперёд, + — влево.
var _phi: float = 0.0
var _move: float = 0.0
var _aim: float = 0.0
## Доля спринта в смеси (на спринте ствол опущен — корпус за взглядом почти не идёт).
var _sprint_share: float = 0.0
## Какой вход дерева сейчас: live — передвижение, pose_a / pose_b — позы целиком.
var _mode: String = "live"
var _pose: String = ""
var _pose_t: float = 0.0
var _pose_rate: float = 1.0
## Поза застыла по просьбе снимка (hold_pose) — состояние персонажа её не трогает.
var _held: bool = false
## «Как было» — для стенда сравнения (tools/anim_stand): один клип на направление (вперёд, назад,
## вбок), без подгонки частоты шага, ходьба / бег / спринт порогами скорости, без живости поверх клипов.
var legacy: bool = false
var _grip: Node3D
## Модель в руке и её риг (WeaponRig.find_on обходит всю модель — не каждый кадр).
var _rig_model: Node3D
var _rig: WeaponRig
## Пути параметров дерева по наборам (строка → StringName каждый кадр стоила дорого) и что в них
## уже записано: одинаковое значение дерево не трогаем.
static var _paths: Dictionary = {}
var _sent: Dictionary = {}
## Левая кисть на цевье (SupportHandIK — модификатор скелета после клипа).
var _support: SupportHandIK
var _collision_ik: WeaponCollisionIK
## Клип падения раненым, пока лежит («» — не ранен); после смерти аниматор не управляет моделью.
var _downed_clip: String = ""
## Раненый мародёр: упал (клип падения доигран) — дальше лежит на животе с оружием в сторону врага
## и отстреливается (prone_aim / prone_fire); выстрел пришёл событием — отдача лёжа.
var _downed_lay: bool = false
var _downed_fire: bool = false
var _dead: bool = false
## Живость (BodyMotion): куда смотрят корпус модели и ноги (рад, мир), пружины и сглаживание.
var _torso_yaw: float = 0.0
var _legs_yaw: float = 0.0
var _legs_turning: bool = false
var _pitch: float = 0.0
var _roll: float = 0.0
var _lean: Vector2 = Vector2.ZERO
## Ускорение тела (м/с², сглажено) — для наклона на разгоне и в поворотах.
var _accel: Vector3 = Vector3.ZERO
var _breath_phase: float = 0.0
var _exert: float = 0.0
var _recoil: float = 0.0
var _recoil_v: float = 0.0
var _flinch: Vector2 = Vector2.ZERO
var _flinch_v: Vector2 = Vector2.ZERO
## Дальность: отбрасывает ли тени и рисуется ли (см. _tick_lod).
var _lod_t: float = 0.0
var _lod_shadows: bool = true
var _lod_shown: bool = true
var _lod_ik: bool = true
var _lod_skip: int = 1
## Дальний ярус: клип двигается раз в столько секунд (0 — по кадрам, _lod_skip).
var _lod_interval: float = 0.0
var _lod_acc: float = 0.0
var _logic_acc: float = 0.0
var _lod_frame: int = 0


func _ready() -> void:
	_actor = get_parent() as CharacterBody3D
	_body = _actor.get_node("Body") as Node3D
	_model = _body.get_node_or_null("Persona") as Node3D
	if _model == null:
		push_error("CharacterAnimator: Persona is missing")
		set_process(false)
		return
	var skeletons: Array[Node] = _model.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty() or not _prepare():
		push_error("CharacterAnimator: нет скелета Persona или запечённых клипов")
		set_process(false)
		return
	_skeleton = skeletons[0] as Skeleton3D
	# у GLB может быть свой проигрыватель — скелет ведёт только дерево
	for p: Node in _model.find_children("*", "AnimationPlayer", true, false):
		(p as AnimationPlayer).active = false
	if _tree_root == null:
		_tree_root = _build_tree(String(_model.get_path_to(_skeleton)))
	_tree = AnimationTree.new()
	_tree.name = "AnimationTree"
	_model.add_child(_tree)
	_tree.root_node = NodePath("..")
	_tree.add_animation_library("", _lib)
	_tree.tree_root = _tree_root
	_tree.active = true
	for set_name: String in _specs:
		if (_specs[set_name] as Dictionary).has("arms"):
			_tree.set("parameters/set_%s/arms/blend_amount" % set_name, 1.0)
	_motion = BodyMotion.new()
	_motion.name = "BodyMotion"
	_motion.model = _model
	_skeleton.add_child(_motion)
	_skeleton.move_child(_motion, 0)
	# высота таза под рост этого тела (другое тело на скелете Persona) — первым, до живости и ИК
	_hips_height = HipsHeight.new()
	_hips_height.name = "HipsHeight"
	_skeleton.add_child(_hips_height)
	_skeleton.move_child(_hips_height, 0)
	_last_position = _actor.global_position
	_torso_yaw = _body.global_rotation.y
	_legs_yaw = _torso_yaw
	_live("unarmed")


## Библиотека клипов и замеры шага — один раз на всех.
static func _prepare() -> bool:
	if _lib != null:
		return true
	_lib = load(CLIPS) as AnimationLibrary
	if _lib == null:
		return false
	if not _lib.has_animation("r8_walk_f") and not _warned_old_clips:
		_warned_old_clips = true
		push_warning("CharacterAnimator: клипы Persona устарели — tools/godot.cmd --headless -s res://tools/bake_character_clips.gd")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(GAIT)) if FileAccess.file_exists(GAIT) else null
	if parsed is Dictionary:
		_gait = parsed
	_specs = _set_specs()
	return true


## Наборы передвижения: поза на месте (idle; aim — в прицеле), кольца ходьбы / бега / спринта
## (клипы направлений; ring_names — как они зовутся в _current), arms — руки поверх ходьбы (своей
## ходьбы вприсядку у пистолета и без оружия нет: ноги автоматные, руки — свои).
static func _set_specs() -> Dictionary:
	var r8 := func(prefix: String) -> Array:
		var out: Array = []
		for d: String in DIRS8:
			out.append(prefix + d)
		return out
	return {
		"rifle": {"idle": "r8_idle", "aim": "r8_idle_aim", "rings": [r8.call("r8_walk_"), r8.call("r8_run_"), r8.call("r8_sprint_")], "ring_names": ["walk", "run", "sprint"]},
		"rifle_crouch": {"idle": "r8_crouch_idle", "aim": "r8_crouch_idle_aim", "rings": [r8.call("r8_crouch_walk_")], "ring_names": ["crouch_walk"]},
		"pistol": {"idle": "pistol_idle", "rings": [["pistol_walk_f", "pistol_walk_b", "pistol_walk_l", "pistol_walk_r"], ["pistol_run_f", "pistol_run_b", "pistol_walk_l", "pistol_walk_r"]], "ring_names": ["walk", "run"]},
		"pistol_crouch": {"idle": "pistol_crouch_idle", "rings": [r8.call("r8_crouch_walk_")], "ring_names": ["crouch_walk"], "arms": "pistol_idle"},
		"unarmed": {"idle": "unarmed_idle", "rings": [["unarmed_walk_f", "unarmed_walk_b", "unarmed_walk_l", "unarmed_walk_r"], ["unarmed_run_f", "unarmed_walk_b", "unarmed_walk_l", "unarmed_walk_r"]], "ring_names": ["walk", "run"]},
		"unarmed_crouch": {"idle": "unarmed_crouch_idle", "rings": [r8.call("r8_crouch_walk_")], "ring_names": ["crouch_walk"], "arms": "unarmed_crouch_idle"},
		# мало здоровья, шагом вперёд без автомата — прихрамывает (у клипа руки свободны)
		"hurt": {"idle": "unarmed_idle", "rings": [["injured_walk"]], "ring_names": ["walk"]},
	}


static func _has(clip: String) -> bool:
	return _lib != null and _lib.has_animation(clip)


## Клип направления: куда и с какой скоростью идёт тело, длина шага (за полный цикл левой и правой),
## когда левая ступня встаёт на землю. Нет замера — направление по имени, скорость шага.
static func _ring_entry(clip: String) -> Dictionary:
	var g: Dictionary = _gait.get(clip, {})
	var anim: Animation = _lib.get_animation(clip)
	var length: float = float(g.get("length", anim.length))
	var cycles: int = maxi(int(g.get("cycles", 1)), 1)
	var v := Vector2.ZERO
	if g.has("velocity"):
		v = Vector2(float(g.velocity[0]), float(g.velocity[1]))
	if v.length() < 0.05:
		var by_name := {"f": Vector2(0, 1), "b": Vector2(0, -1), "l": Vector2(1, 0), "r": Vector2(-1, 0), "fl": Vector2(1, 1), "fr": Vector2(-1, 1), "bl": Vector2(1, -1), "br": Vector2(-1, -1)}
		v = (by_name.get(clip.get_slice("_", clip.get_slice_count("_") - 1), Vector2(0, 1)) as Vector2).normalized() * 1.5
	return {"clip": clip, "dir": v.normalized(), "angle": atan2(v.x, v.y), "speed": v.length(),
		"stride": v.length() * length / float(cycles), "cycles": cycles, "left_down": float(g.get("left_down", 0.0))}


## Узел клипа. Клип шага растянут на число своих шагов (у всех клипов набора шаг — одна единица
## времени, смесь направлений не путает ноги) и начинается с постановки левой ноги.
static func _clip_node(clip: String, loop: bool, step: Dictionary = {}) -> AnimationNodeAnimation:
	var n := AnimationNodeAnimation.new()
	n.animation = POSE_CLIP.get(clip, clip) if _has(String(POSE_CLIP.get(clip, clip))) else "unarmed_idle"
	n.use_custom_timeline = true
	if not step.is_empty():
		n.timeline_length = float(step.cycles)
		n.stretch_time_scale = true
		n.start_offset = float(step.left_down)
		n.loop_mode = Animation.LOOP_LINEAR
	else:
		n.timeline_length = _lib.get_animation(n.animation).length
		n.stretch_time_scale = false
		n.loop_mode = Animation.LOOP_LINEAR if loop else Animation.LOOP_NONE
	if clip == "prone_crawl_f":
		n.play_mode = AnimationNodeAnimation.PLAY_MODE_BACKWARD
	return n


static func _build_tree(skel_path: String) -> AnimationNodeBlendTree:
	var a: Dictionary = Balance.CHARACTER_ANIM
	var root := AnimationNodeBlendTree.new()
	# передвижение: наборы по стойке и оружию
	var specs: Dictionary = _specs
	var live := AnimationNodeTransition.new()
	live.xfade_time = float(a.set_blend_sec)
	live.input_count = specs.size()
	var i: int = 0
	for set_name: String in specs:
		live.set_input_name(i, set_name)
		root.add_node("set_" + set_name, _build_set(set_name, specs[set_name], skel_path))
		i += 1
	root.add_node("live", live)
	i = 0
	for set_name: String in specs:
		root.connect_node("live", i, "set_" + set_name)
		i += 1
	# действия: верх тела поверх передвижения, затем всем телом
	var upper := _acts_node(root, "act", UPPER_ACTS)
	_filter(upper, skel_path, true)
	root.add_node("act", upper)
	root.connect_node("act", 0, "live")
	root.connect_node("act", 1, "act_clip")
	var full := _acts_node(root, "full", FULL_ACTS)
	root.add_node("full", full)
	root.connect_node("full", 0, "act")
	root.connect_node("full", 1, "full_clip")
	# позы целиком: две одинаковые цепочки — новая поза идёт на свободную, переход плавный
	var mode := AnimationNodeTransition.new()
	mode.xfade_time = float(a.pose_blend_sec)
	mode.input_count = 3
	mode.set_input_name(0, "live")
	mode.set_input_name(1, "pose_a")
	mode.set_input_name(2, "pose_b")
	root.add_node("mode", mode)
	root.connect_node("mode", 0, "full")
	for chain: String in ["pose_a", "pose_b"]:
		var pose := AnimationNodeTransition.new()
		pose.xfade_time = 0.0
		pose.allow_transition_to_self = true
		pose.input_count = POSES.size()
		for k in range(POSES.size()):
			pose.set_input_name(k, POSES[k])
			root.add_node("%s_%s" % [chain, POSES[k]], _clip_node(POSES[k], POSES[k] in LOOP_POSES))
		root.add_node(chain, pose)
		for k in range(POSES.size()):
			root.connect_node(chain, k, "%s_%s" % [chain, POSES[k]])
		root.add_node(chain + "_seek", AnimationNodeTimeSeek.new())
		root.connect_node(chain + "_seek", 0, chain)
		root.add_node(chain + "_rate", AnimationNodeTimeScale.new())
		root.connect_node(chain + "_rate", 0, chain + "_seek")
	root.connect_node("mode", 1, "pose_a_rate")
	root.connect_node("mode", 2, "pose_b_rate")
	root.connect_node("output", 0, "mode")
	return root


## Одиночное действие: выбор клипа (переход без смешивания) и OneShot с плавным входом и выходом.
static func _acts_node(root: AnimationNodeBlendTree, prefix: String, clips: Array) -> AnimationNodeOneShot:
	var pick := AnimationNodeTransition.new()
	pick.xfade_time = 0.0
	pick.allow_transition_to_self = true
	pick.input_count = clips.size()
	for k in range(clips.size()):
		pick.set_input_name(k, clips[k])
		root.add_node("%s_%s" % [prefix, clips[k]], _clip_node(clips[k], false))
	root.add_node(prefix + "_clip", pick)
	for k in range(clips.size()):
		root.connect_node(prefix + "_clip", k, "%s_%s" % [prefix, clips[k]])
	var shot := AnimationNodeOneShot.new()
	shot.fadein_time = float(Balance.CHARACTER_ANIM.act_in)
	shot.fadeout_time = float(Balance.CHARACTER_ANIM.act_out)
	return shot


## Набор передвижения: поза на месте (и в прицеле) ↔ кольца направлений с подгонкой частоты шага.
static func _build_set(set_name: String, spec: Dictionary, skel_path: String) -> AnimationNodeBlendTree:
	var bt := AnimationNodeBlendTree.new()
	bt.add_node("idle", _clip_node(spec.idle, true))
	var still := "idle"
	if spec.has("aim"):
		bt.add_node("aim", _clip_node(spec.aim, true))
		bt.add_node("still", AnimationNodeBlend2.new())
		bt.connect_node("still", 0, "idle")
		bt.connect_node("still", 1, "aim")
		still = "still"
	# Кольца ходьбы, бега и спринта — точки одного пространства смешивания: направление шага и
	# радиус по скорости (ходьба 1, бег 2, спринт 3). Синхронизация циклическая: все клипы в одной фазе
	# шага (клип растянут на длину шага, начало — постановка левой ноги), клипы с нулевым весом не
	# крутятся — так дёшево, а при смене ходьбы на бег нога не «перескакивает».
	var rings: Array = []
	var points: int = 0
	for k in range((spec.rings as Array).size()):
		var ring: Array = []
		for clip: String in spec.rings[k]:
			# развёрнутый на 180° клип (замер нашёл) в смесь не берём
			if _has(clip) and not bool((_gait.get(clip, {}) as Dictionary).get("flipped", false)):
				ring.append(_ring_entry(clip))
		ring.sort_custom(func(x: Dictionary, y: Dictionary) -> bool: return float(x.angle) < float(y.angle))
		rings.append(ring)
		points += ring.size()
	if points == 1:
		var only: Dictionary = rings[0][0]
		bt.add_node("ring", _clip_node(only.clip, true, only))
	else:
		var bs := AnimationNodeBlendSpace2D.new()
		bs.sync_mode = AnimationNodeBlendSpace2D.SYNC_MODE_CYCLIC_CONSTANT
		bs.cyclic_length = 1.0
		bs.blend_mode = AnimationNodeBlendSpace2D.BLEND_MODE_INTERPOLATED
		bs.min_space = Vector2(-4.0, -4.0)
		bs.max_space = Vector2(4.0, 4.0)
		for k in range(rings.size()):
			for e: Dictionary in rings[k]:
				bs.add_blend_point(_clip_node(e.clip, true, e), (e.dir as Vector2) * float(k + 1), -1, StringName("%s_%d" % [e.clip, k]))
		bt.add_node("ring", bs)
	var last := "ring"
	_rings[set_name] = rings
	bt.add_node("rate", AnimationNodeTimeScale.new())
	bt.connect_node("rate", 0, last)
	var moving := "rate"
	if spec.has("arms"):
		bt.add_node("arms_pose", _clip_node(spec.arms, true))
		var arms := AnimationNodeBlend2.new()
		_filter(arms, skel_path, false)
		bt.add_node("arms", arms)
		bt.connect_node("arms", 0, "rate")
		bt.connect_node("arms", 1, "arms_pose")
		moving = "arms"
	bt.add_node("move", AnimationNodeBlend2.new())
	bt.connect_node("move", 0, still)
	bt.connect_node("move", 1, moving)
	bt.connect_node("output", 0, "move")
	return bt


## Фильтр костей: руки (плечо, рука, предплечье, кисть, пальцы), с upper — ещё грудь, шея и голова.
static func _filter(node: AnimationNode, skel_path: String, upper: bool) -> void:
	node.filter_enabled = true
	var anim: Animation = _lib.get_animation("r8_idle" if _has("r8_idle") else "unarmed_idle")
	for t in range(anim.get_track_count()):
		var path: NodePath = anim.track_get_path(t)
		if path.get_subname_count() == 0:
			continue
		var bone := String(path.get_subname(0)).trim_prefix("mixamorig_")
		var arm := (bone.begins_with("Left") or bone.begins_with("Right")) and not ("Leg" in bone or "Foot" in bone or "Toe" in bone)
		var chest := bone in ["Spine1", "Spine2", "Neck", "Head", "HeadTop_End"]
		if arm or (upper and chest):
			node.set_filter_path(NodePath(skel_path + ":" + String(path.get_subname(0))), true)


## «Как было»: ближайший из клипов вперёд / назад / вбок, без смеси.
static func _ring_snap(ring: Array, phi: float) -> Dictionary:
	var best: Dictionary = ring[0]
	var gap: float = INF
	for e: Dictionary in ring:
		var clip: String = e.clip
		if not clip.get_slice("_", clip.get_slice_count("_") - 1) in ["f", "b", "l", "r"] and ring.size() > 4:
			continue
		var d: float = absf(wrapf(phi - float(e.angle), -PI, PI))
		if d < gap:
			gap = d
			best = e
	return {"pos": best.dir, "speed": best.speed, "stride": best.stride, "clip": best.clip}


## Точка кольца для направления phi: смесь двух соседних клипов на ребре (позиция в пространстве
## смешивания), их скорость и длина шага; clip — какой из двух ближе.
static func _ring_at(ring: Array, phi: float) -> Dictionary:
	if ring.size() == 1:
		var e: Dictionary = ring[0]
		return {"pos": Vector2.ZERO, "speed": e.speed, "stride": e.stride, "clip": e.clip}
	var n: int = ring.size()
	for k in range(n):
		var p: Dictionary = ring[k]
		var q: Dictionary = ring[(k + 1) % n]
		var span: float = wrapf(float(q.angle) - float(p.angle), 0.0, TAU)
		var off: float = wrapf(phi - float(p.angle), 0.0, TAU)
		if off <= span + 0.0001:
			var w: float = off / maxf(span, 0.0001)
			return {"pos": (p.dir as Vector2).lerp(q.dir, w), "speed": lerpf(p.speed, q.speed, w),
				"stride": lerpf(p.stride, q.stride, w), "clip": p.clip if w < 0.5 else q.clip}
	var f: Dictionary = ring[0]
	return {"pos": f.dir, "speed": f.speed, "stride": f.stride, "clip": f.clip}


## Дальний персонаж дешевле (Balance.CHARACTER_LOD): модель подробная (170 тыс. треугольников), а солнце
## рисует тени на сотни метров — два десятка мародёров по всей карте давали миллионы треугольников в
## каждом проходе теней. Дальше shadows_m персонаж теней не отбрасывает, дальше hide_m — не рисуется.
## Процессор: дальше ik_m руки не подгоняются к оружию и стенам (IK с лучами физики), дальше anim_m[0]
## клип считается через кадр, дальше anim_m[1] — раз в четыре кадра (вдали этого не видно), дальше anim_far_m —
## anim_far_hz раз в секунду при любой частоте кадров; живость поверх клипов (BodyMotion) тогда не считается.
## Проверка — раз в every секунд, у каждого в свой момент; своё тело игрока не трогаем.
func _tick_lod(delta: float) -> void:
	_lod_t -= delta
	if _lod_t > 0.0:
		return
	var lod: Dictionary = Balance.CHARACTER_LOD
	_lod_t = float(lod.every) * randf_range(0.8, 1.2)
	if _actor is Player and (_actor as Player).is_local():
		return
	var cam: Camera3D = get_viewport().get_camera_3d()
	if cam == null:
		return
	var d: float = cam.global_position.distance_to(_actor.global_position)
	# запас на возврат: на границе тень не мигает
	var keep: float = float(lod.hysteresis)
	var shadows: bool = d < float(lod.shadows_m) - (keep if not _lod_shadows else 0.0)
	var shown: bool = d < float(lod.hide_m) - (keep if not _lod_shown else 0.0)
	if shown != _lod_shown:
		_lod_shown = shown
		_model.visible = shown
	var ik: bool = d < float(lod.ik_m)
	if ik != _lod_ik and not _dead:
		_lod_ik = ik
		if _support:
			_support.active = ik
		if _collision_ik:
			_collision_ik.active = ik
	var steps: Array = lod.anim_m
	var skip: int = 4 if d > float(steps[1]) else (2 if d > float(steps[0]) else 1)
	var far_m: float = float(lod.get("anim_far_m", INF))
	_lod_interval = 1.0 / float(lod.anim_far_hz) if d > far_m - (keep if _lod_interval > 0.0 else 0.0) else 0.0
	if skip != _lod_skip:
		_lod_skip = skip
		# вдали клип двигаем сами, реже; вблизи — снова каждый кадр
		_tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL if skip > 1 else AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_IDLE
		if skip == 1 and _lod_acc > 0.0:
			_tree.advance(_lod_acc)
			_lod_acc = 0.0
			_logic_acc = 0.0
	# пока теней нет — проходим каждый раз: оружие в руках могли сменить, новая модель тоже без тени
	if shadows == _lod_shadows and shadows:
		return
	_lod_shadows = shadows
	for n: Node in _actor.find_children("*", "GeometryInstance3D", true, false):
		var gi: GeometryInstance3D = n as GeometryInstance3D
		if shadows:
			if gi.has_meta("lod_cast"):
				gi.cast_shadow = int(gi.get_meta("lod_cast")) as GeometryInstance3D.ShadowCastingSetting
				gi.remove_meta("lod_cast")
		elif gi.cast_shadow != GeometryInstance3D.SHADOW_CASTING_SETTING_OFF:
			gi.set_meta("lod_cast", int(gi.cast_shadow))
			gi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF


## Скорость тела — по смещению за шаг физики: тело двигает физика, и за шаг смещение точное (за кадр
## при 144 к/с оно то ноль, то двойное — скорость скакала, а с ней частота шага). Чужие тела (позиция
## приходит по сети) — тем же смещением, сглаженным за speed_smooth_sec.
func _physics_process(delta: float) -> void:
	if _tree == null or delta <= 0.0 or _dead:
		return
	var travel: Vector3 = _actor.global_position - _last_position
	_last_position = _actor.global_position
	travel.y = 0.0
	var before: Vector3 = _vel
	_vel = _vel.lerp(travel / delta, 1.0 - exp(-delta / float(Balance.CHARACTER_ANIM.speed_smooth_sec)))
	_accel = _accel.lerp((_vel - before) / delta, 1.0 - exp(-delta / float(Balance.BODY_MOTION.accel_sec)))


func _process(delta: float) -> void:
	if _tree == null or delta <= 0.0:
		return
	_tick_lod(delta)
	if _lod_skip > 1:
		_lod_acc += delta
		_logic_acc += delta
		_lod_frame += 1
		# вдали и логика аниматора — в кадр, когда двигается дерево, со всем накопленным временем
		if _lod_interval > 0.0:
			if _lod_acc < _lod_interval:
				return
		elif _lod_frame % _lod_skip != 0:
			return
		_tree.advance(_lod_acc)
		_lod_acc = 0.0
		delta = _logic_acc
		_logic_acc = 0.0
	if _mode != "live":
		_pose_t += delta * absf(_pose_rate)
	_one_shot_t += delta
	if _dead or _held:
		_settle_motion(delta)
		return
	var speed: float = _vel.length()
	var family: String = "unarmed"
	var crouched: bool = false
	var prone: bool = false
	var downed: bool = false
	var aiming: bool = false
	var hurt: bool = false
	var airborne: bool = false
	var look_pitch: float = 0.0
	var lean: float = 0.0
	var event_seq: int = 0
	var event_name: String = ""
	if _actor is Player:
		var person: Player = _actor as Player
		var weapon_class: String = String(WeaponDb.weapon(person.weapon_id).get("class", "")) if person.weapon_id != "" else ""
		family = "unarmed" if weapon_class == "" else ("pistol" if weapon_class == "PISTOL" else "rifle")
		if person.grenade_equipped:
			family = "pistol"
		crouched = person.stance == Player.Stance.CROUCH
		prone = person.stance == Player.Stance.PRONE
		downed = person.health.downed
		aiming = person.aiming
		hurt = person.health.hp < person.health.max_hp * float(Balance.CHARACTER_ANIM.hurt_below)
		airborne = person.airborne
		look_pitch = person.look_pitch
		lean = person.lean
		event_seq = person.animation_event_seq
		event_name = person.animation_event
	elif _actor is Marauder:
		var enemy: Marauder = _actor as Marauder
		family = "pistol" if String(enemy._spec.get("class", "")) == "PISTOL" else "rifle"
		crouched = enemy.crouched
		downed = enemy._health.downed
		aiming = enemy.state == Marauder.State.COMBAT
		# вверх-вниз смотрит, пока целится; в патруле — прямо
		look_pitch = enemy.look_pitch if aiming else 0.0
		event_seq = enemy.animation_event_seq
		event_name = enemy.animation_event
	elif _actor.has_method("anim_state"):
		# любое другое тело (стенд, будущие NPC): состояние словарём с теми же полями
		var st: Dictionary = _actor.call("anim_state")
		family = String(st.get("family", "unarmed"))
		crouched = bool(st.get("crouched", false))
		prone = bool(st.get("prone", false))
		downed = bool(st.get("downed", false))
		aiming = bool(st.get("aiming", false))
		hurt = bool(st.get("hurt", false))
		airborne = bool(st.get("airborne", false))
		look_pitch = float(st.get("look_pitch", 0.0))
		lean = float(st.get("lean", 0.0))
		event_seq = int(st.get("event_seq", 0))
		event_name = String(st.get("event", ""))
	var move_min: float = float(Balance.CHARACTER_ANIM.move_min)
	var moving: bool = speed > move_min
	# одиночное действие доиграно
	if _one_shot != "" and _one_shot_t >= _act_length(_one_shot):
		_one_shot = ""
		_one_shot_kind = ""
	if _grip:
		_grip.visible = not HIDE_WEAPON.has(_one_shot)
	if _collision_ik:
		_collision_ik.enabled_for_pose = not downed and not _dead and family != "unarmed"
	if _support:
		# с пистолетом — вторая рука на рукоятке только в прицеле (на ходу клипы держат одной)
		var hold := _grip != null and _grip.visible and family != "unarmed" and not downed \
			and not FREE_LEFT_HAND.has(_one_shot) and (family != "pistol" or aiming or (_actor is Player and (_actor as Player).handheld_light_on))
		var held: Node3D = held_model(_grip)
		# риг ищется обходом всей модели ствола — только когда в руке другая модель
		if held != _rig_model:
			_rig_model = held
			_rig = WeaponRig.find_on(held) if held else null
		var weapon_rig: WeaponRig = _rig if is_instance_valid(_rig) else null
		var action_weight: float = weapon_rig.get_hand_weight() if weapon_rig and not downed else 0.0
		_support.action_target = weapon_rig.get_hand_target() if action_weight > 0.0 else null
		_support.action_weight = action_weight
		hold = hold or action_weight > 0.0
		_support.influence = move_toward(_support.influence, 1.0 if hold else 0.0, delta / float(Balance.CHARACTER_ANIM.support_blend_sec))
	if event_seq != _last_event_seq:
		_last_event_seq = event_seq
		if event_name.ends_with("fire"):
			if downed:
				_downed_fire = true
			else:
				var b: Dictionary = Balance.BODY_MOTION
				_recoil_v += float(b.recoil_pistol if family == "pistol" else b.recoil_kick) * (float(b.recoil_prone) if prone else 1.0)
		elif event_name == "hit":
			# вздрагивание поверх любой стойки; раненому и лежащему — нет
			if not downed and not prone:
				_flinch_v += Vector2(randf_range(-0.6, 0.6), 1.0) * float(Balance.BODY_MOTION.flinch_kick)
		elif not downed:
			var act: Array = _event_action(event_name, family, crouched, prone, moving)
			if not act.is_empty():
				_start_act(String(act[0]), String(act[1]))
	# Физическая стойка уже уменьшает Body; компенсируем её для запечённой позы приседа.
	if _actor is Player:
		_model.scale.y = 1.0 / maxf(_body.scale.y, 0.1)
	elif _actor is Marauder:
		var enemy_scale: float = (_actor as Marauder)._base_scale.y
		_model.scale.y = enemy_scale / maxf(_body.scale.y, 0.1)
	_update_motion(delta, family, speed, prone or downed, airborne, look_pitch, lean)
	# высоту таза (присел, лёг, упал) задаёт сам клип — модель вниз не сдвигаем
	# тяжело ранен: падает (бегом — с разбега) и лежит в последнем кадре; тащат — поза та же
	if downed:
		_tick_downed(family, speed)
		return
	if _downed_clip != "":
		# подняли — обратно к обычным клипам
		_downed_clip = ""
		_downed_lay = false
	if prone:
		# лёжа: перезарядка и бросок — позой целиком, пока доигрывают
		if _one_shot_kind == "pose":
			return
		var local: Vector3 = Basis(Vector3.UP, -_legs_yaw) * _vel
		if moving:
			var crawl: String = "prone_crawl_f" if local.z >= 0.0 else "prone_move_b"
			var crawl_speed: float = maxf(float((_gait.get("prone_move_b", {}) as Dictionary).get("speed", 0.3)), 0.1)
			var rate: float = clampf(speed / crawl_speed, 0.5, float(Balance.CHARACTER_ANIM.prone_rate_max))
			if _pose != crawl:
				_pose_to(crawl, rate)
			else:
				_set_pose_rate(rate)
		else:
			# лёжа с оружием — поза «лёжа с автоматом»; без — стоп-кадр ползания
			var still: String = "prone_aim" if family != "unarmed" else "prone_move_b"
			var at: float = float(Balance.CHARACTER_ANIM.prone_aim_hold_sec if still == "prone_aim" else Balance.CHARACTER_ANIM.prone_hold_sec)
			if _pose != still or _pose_rate != 0.0:
				_pose_to(still, 0.0, at)
		return
	if _one_shot_kind == "pose":
		# встал, не доиграв позу лёжа
		_one_shot = ""
		_one_shot_kind = ""
	if airborne and _has("jump_loop"):
		if _pose != "jump_loop":
			_pose_to("jump_loop")
		return
	_update_live(delta, family, crouched, aiming, hurt, speed)


## Тяжело ранен: упал клипом и лежит; мародёр с оружием, которого не тащат, — лёжа отстреливается.
func _tick_downed(family: String, speed: float) -> void:
	if _downed_clip == "":
		_one_shot = ""
		_one_shot_kind = ""
		_downed_lay = false
		_downed_fire = false
		_downed_clip = "downed_fall" if speed >= float(Balance.CHARACTER_ANIM.run_from) * 0.6 else "downed_fall_still"
		_pose_to(_downed_clip)
		return
	if _pose == _downed_clip and _pose_t >= _act_length(_downed_clip):
		_downed_lay = true
	var enemy := _actor as Marauder
	if enemy and _downed_lay and family != "unarmed" and enemy.dragged_by == null:
		if _downed_fire:
			_downed_fire = false
			_pose_to("prone_fire")
		elif _pose != "prone_aim" and (_pose != "prone_fire" or _pose_t >= _act_length("prone_fire")):
			_pose_to("prone_aim")
	elif enemy and _downed_lay and enemy.dragged_by != null and _pose != _downed_clip:
		# тащат — снова как упал
		_pose_to(_downed_clip, 1.0, _act_length(_downed_clip))


## Передвижение: набор по стойке и оружию, направление и частота шага, поза на месте и в прицеле.
func _update_live(delta: float, family: String, crouched: bool, aiming: bool, hurt: bool, speed: float) -> void:
	var a: Dictionary = Balance.CHARACTER_ANIM
	var local3: Vector3 = Basis(Vector3.UP, -_legs_yaw) * _vel
	var local := Vector2(local3.x, local3.z)
	if speed > 0.15:
		var want: float = atan2(local.x, local.y)
		# Сглаживание направления — только на ходу (от дрожи скорости чужих тел). Медленно или
		# развернулся в обратную сторону — сразу: иначе ноги полсекунды шагают вбок, а тело идёт назад.
		var turn: float = absf(wrapf(want - _phi, -PI, PI))
		if legacy or (turn > PI * 0.6 and speed < float(a.move_full) * 2.0):
			_phi = want
		else:
			var smooth: float = float(a.dir_smooth_sec) * clampf(speed / 1.5, 0.15, 1.0)
			_phi = lerp_angle(_phi, want, 1.0 - exp(-delta / smooth))
	var set_name: String = family + ("_crouch" if crouched else "")
	if hurt and family != "rifle" and not crouched and speed > float(a.move_min) and absf(_phi) < PI * 0.25 and _has("injured_walk"):
		set_name = "hurt"
	if _mode != "live":
		_tree.set("parameters/mode/transition_request", "live")
		_mode = "live"
		_pose = ""
	if set_name != _set:
		_set = set_name
		_tree.set("parameters/live/transition_request", set_name)
	_move = lerpf(_move, smoothstep(float(a.move_min), float(a.move_full), speed), 1.0 - exp(-delta / float(a.move_smooth_sec)))
	_aim = move_toward(_aim, 1.0 if aiming else 0.0, delta / float(a.aim_blend_sec))
	var path: Dictionary = _set_paths(set_name)
	var spec: Dictionary = _specs[set_name]
	var rings: Array = _rings[set_name]
	var infos: Array = []
	for ring: Array in rings:
		infos.append(_ring_snap(ring, _phi) if legacy else _ring_at(ring, _phi))
	# ходьба → бег → спринт по скорости; веса колец — для длины шага
	var weights: Array[float] = []
	weights.resize(infos.size())
	weights.fill(0.0)
	weights[0] = 1.0
	var level: float = 1.0
	for k in range(1, infos.size()):
		var lo: float = float(infos[k - 1].speed)
		var g: float = clampf((speed - lo) / maxf(float(infos[k].speed) - lo, 0.5), 0.0, 1.0)
		if legacy:
			g = 1.0 if speed >= float(a.run_from if k == 1 else a.sprint_from) else 0.0
		level += g
		for j in range(k):
			weights[j] *= 1.0 - g
		weights[k] = g
	var stride: float = 0.0
	var top: int = 0
	for k in range(infos.size()):
		stride += weights[k] * float(infos[k].stride)
		if weights[k] > weights[top]:
			top = k
	if (rings[0] as Array).size() > 1 or rings.size() > 1:
		_put(path.ring, (infos[0].pos as Vector2) * level)
	var rate: float = 1.0 if legacy else clampf(speed / maxf(stride, 0.05), float(a.rate_min), float(a.rate_max))
	_put(path.rate, rate)
	_put(path.move, _move)
	if spec.has("aim"):
		_put(path.still, _aim)
	_sprint_share = weights[2] if set_name == "rifle" and weights.size() > 2 else 0.0
	# как это назвать (тесты, отладка): прежние имена клипов
	if _move < 0.5:
		_current = ("rifle_crouch_aim" if crouched else "rifle_aim") if family == "rifle" and _aim > 0.5 else family + ("_crouch_idle" if crouched else "_idle")
	elif set_name == "hurt":
		_current = "injured_walk"
	else:
		var clip: String = infos[top].clip
		var dir: String = clip.get_slice("_", clip.get_slice_count("_") - 1)
		var ring_name: String = spec.ring_names[top]
		_current = "rifle_sprint" if ring_name == "sprint" else "%s_%s_%s" % [family, ring_name, dir]



static func _set_paths(set_name: String) -> Dictionary:
	var path: Dictionary = _paths.get(set_name, {})
	if path.is_empty():
		var base: String = "parameters/set_%s/" % set_name
		path = {"ring": StringName(base + "ring/blend_position"), "rate": StringName(base + "rate/scale"),
			"move": StringName(base + "move/blend_amount"), "still": StringName(base + "still/blend_amount")}
		_paths[set_name] = path
	return path


## Параметр дерева, если значение заметно изменилось.
func _put(path: StringName, value: Variant) -> void:
	var was: Variant = _sent.get(path)
	if was != null:
		if value is float and absf(float(was) - float(value)) < 0.002:
			return
		if value is Vector2 and (was as Vector2).distance_squared_to(value as Vector2) < 0.000004:
			return
	_sent[path] = value
	_tree.set(path, value)


## Что сыграть по событию: [вид, клип] — upper (верх тела), full (всё тело), pose (лёжа); [] — ничего.
func _event_action(ev: String, family: String, crouched: bool, prone: bool, moving: bool) -> Array:
	match ev:
		"rifle_reload":
			return ["pose", "prone_reload"] if prone else ["upper", "rifle_reload"]
		"pistol_reload":
			# Штатного Mixamo-клипа пистолета нет: позу сохраняем, левую кисть ведёт риг ПМ.
			# Чужим игрокам приходит само событие, а детали и цель ИК — отдельным событием рига.
			return ["upper", "pistol_reload"] if _has("pistol_reload") and not prone else []
		"pistol_draw", "rifle_draw":
			if prone:
				return []
			var clip := "pistol_draw" if family == "pistol" else ("rifle_draw" if family == "rifle" else "")
			return ["upper", clip] if clip != "" else []
		"rifle_holster":
			return [] if prone else ["upper", "rifle_holster"]
		"grenade_throw":
			if prone:
				return ["pose", "prone_throw"]
			# на ходу и в приседе бросает верхом тела — ноги идут своим клипом
			return ["upper", "grenade_throw"] if crouched or moving else ["full", "grenade_throw"]
		"pickup":
			return [] if crouched or prone or moving else ["full", "pickup"]
	return ["upper", ev] if ev in UPPER_ACTS and not prone else []


func _start_act(kind: String, clip: String) -> void:
	if not _has(String(POSE_CLIP.get(clip, clip))):
		return
	match kind:
		"upper":
			_tree.set("parameters/act_clip/transition_request", clip)
			_tree.set("parameters/act/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)
		"full":
			_tree.set("parameters/full_clip/transition_request", clip)
			_tree.set("parameters/full/request", AnimationNodeOneShot.ONE_SHOT_REQUEST_FIRE)
		"pose":
			_pose_to(clip)
	_one_shot = clip
	_one_shot_kind = kind
	_one_shot_t = 0.0


func _act_length(clip: String) -> float:
	var name := String(POSE_CLIP.get(clip, clip))
	return _lib.get_animation(name).length if _has(name) else 0.0


## Поза целиком на свободной цепочке: переход с того, что видно сейчас (передвижение или прежняя поза),
## всегда плавный. rate — скорость клипа (0 — стоп-кадр), at — с какого места.
func _pose_to(node: String, rate: float = 1.0, at: float = 0.0) -> void:
	var chain := "pose_b" if _mode == "pose_a" else "pose_a"
	_tree.set("parameters/%s/transition_request" % chain, node)
	_tree.set("parameters/%s_seek/seek_request" % chain, at)
	_tree.set("parameters/%s_rate/scale" % chain, rate)
	_tree.set("parameters/mode/transition_request", chain)
	_mode = chain
	_pose = node
	_pose_t = at
	_pose_rate = rate
	_current = node


func _set_pose_rate(rate: float) -> void:
	_pose_rate = rate
	_tree.set("parameters/%s_rate/scale" % _mode, rate)


## Возврат к передвижению набором set_name (без смешивания с прежним — при появлении).
func _live(set_name: String) -> void:
	_set = set_name
	_tree.set("parameters/live/transition_request", set_name)
	_tree.set("parameters/mode/transition_request", "live")
	_mode = "live"
	_current = set_name + "_idle"


## Застывшая поза для снимков: клип clip (из POSES) на времени at, состояние персонажа её не меняет.
## Работает и с выключенным _process (инструменты снимков так и делают).
func hold_pose(clip: String, at: float) -> void:
	if _tree == null:
		return
	_held = true
	_pose_to(clip, 0.0, at)
	_tree.advance(0.0)
	_tree.advance(float(Balance.CHARACTER_ANIM.pose_blend_sec) + 0.01)


## Живость поверх клипов: корпус догоняет поворот тела, ноги отстают, корпус смотрит за прицелом,
## наклоны, дыхание и пружины отдачи / вздрагивания. lying — лёжа или ранен: без поворотов корпуса.
func _update_motion(delta: float, family: String, speed: float, lying: bool, airborne: bool, look_pitch: float, lean: float) -> void:
	var b: Dictionary = Balance.BODY_MOTION
	_motion.active = _lod_skip == 1 and not legacy
	var yaw: float = _body.global_rotation.y
	_torso_yaw = _approach_angle(_torso_yaw, yaw, delta, float(b.torso_sec))
	var moving: bool = speed > 0.3
	if lying or airborne:
		_legs_yaw = _torso_yaw
		_legs_turning = false
	elif moving:
		_legs_yaw = _approach_angle(_legs_yaw, _torso_yaw, delta, float(b.legs_move_sec))
		_legs_turning = false
	else:
		# на месте ноги ждут, пока корпус не отвернётся далеко, и доворачиваются шагом
		if absf(wrapf(_legs_yaw - _torso_yaw, -PI, PI)) > float(b.legs_dead):
			_legs_turning = true
		if _legs_turning:
			_legs_yaw = _approach_angle(_legs_yaw, _torso_yaw, delta, float(b.legs_idle_sec))
			if absf(wrapf(_legs_yaw - _torso_yaw, -PI, PI)) < float(b.legs_settle):
				_legs_turning = false
	var twist: float = clampf(wrapf(_legs_yaw - _torso_yaw, -PI, PI), -float(b.legs_max), float(b.legs_max))
	_legs_yaw = _torso_yaw + twist
	_motion.hips_yaw = wrapf(_legs_yaw - yaw, -PI, PI)
	_motion.torso_yaw = twist
	# взгляд вверх-вниз: корпус (ствол идёт за ним), остальное — голова
	var want: float = clampf(look_pitch, -float(b.pitch_down), float(b.pitch_up))
	var share: float = 1.0
	if lying:
		share = float(b.pitch_prone)
	elif family == "unarmed":
		share = float(b.pitch_unarmed)
	share = lerpf(share, float(b.pitch_sprint), _sprint_share)
	_pitch = lerpf(_pitch, want, 1.0 - exp(-delta / float(b.pitch_sec)))
	_motion.pitch = _pitch * share
	if _collision_ik:
		_collision_ik.aim_pitch = _motion.pitch if _motion.active else 0.0
	_motion.head_pitch = clampf(_pitch * (1.0 - share), -float(b.head_max), float(b.head_max)) * (0.0 if lying else 1.0)
	_roll = lerpf(_roll, lean * float(b.lean_roll), 1.0 - exp(-delta / float(b.lean_sec)))
	_motion.roll = _roll
	# разгон, торможение и поворот: корпус наклоняется по ускорению (в осях корпуса)
	var local_a: Vector3 = Basis(Vector3.UP, -_torso_yaw) * _accel
	var want_lean := Vector2(-local_a.x, local_a.z) * float(b.accel_lean)
	if lying or airborne:
		want_lean = Vector2.ZERO
	want_lean = want_lean.limit_length(float(b.accel_max))
	_lean = _lean.lerp(want_lean, 1.0 - exp(-delta / float(b.lean_sec)))
	_motion.lean_side = _lean.x
	_motion.lean_fwd = _lean.y
	# дыхание: после бега чаще и глубже, на ходу — слабее (клип и так качает)
	var hard: bool = speed > float(b.exert_speed)
	_exert = move_toward(_exert, 1.0 if hard else 0.0, delta / float(b.exert_up_sec if hard else b.exert_down_sec))
	_breath_phase = fmod(_breath_phase + TAU * lerpf(float(b.breath_rest_hz), float(b.breath_hard_hz), _exert) * delta, TAU)
	var depth: float = lerpf(float(b.breath_rest), float(b.breath_hard), _exert) * lerpf(1.0, float(b.breath_moving), _move)
	_motion.breath = sin(_breath_phase) * depth
	# пружины: отдача и вздрагивание
	var k_r: float = float(b.recoil_stiff)
	var c_r: float = float(b.recoil_damp)
	var k_f: float = float(b.flinch_stiff)
	var c_f: float = float(b.flinch_damp)
	var left: float = delta
	while left > 0.0:
		var h: float = minf(left, 1.0 / 120.0)
		left -= h
		_recoil_v += (-k_r * _recoil - c_r * _recoil_v) * h
		_recoil += _recoil_v * h
		_flinch_v += (-k_f * _flinch - c_f * _flinch_v) * h
		_flinch += _flinch_v * h
	_motion.recoil = _recoil
	_motion.flinch = _flinch


## Умер или застыл для снимка: живость плавно уходит (без рывка к позе клипа), потом выключается.
func _settle_motion(delta: float) -> void:
	if _motion == null or not _motion.active:
		return
	var k: float = 1.0 - exp(-delta / 0.12)
	_motion.hips_yaw = lerpf(_motion.hips_yaw, 0.0, k)
	_motion.torso_yaw = lerpf(_motion.torso_yaw, 0.0, k)
	_motion.pitch = lerpf(_motion.pitch, 0.0, k)
	_motion.head_pitch = lerpf(_motion.head_pitch, 0.0, k)
	_motion.roll = lerpf(_motion.roll, 0.0, k)
	_motion.lean_fwd = lerpf(_motion.lean_fwd, 0.0, k)
	_motion.lean_side = lerpf(_motion.lean_side, 0.0, k)
	_motion.breath = lerpf(_motion.breath, 0.0, k)
	_motion.recoil = lerpf(_motion.recoil, 0.0, k)
	_motion.flinch = _motion.flinch.lerp(Vector2.ZERO, k)
	if absf(_motion.pitch) + absf(_motion.hips_yaw) + absf(_motion.torso_yaw) + absf(_motion.roll) < 0.002:
		_motion.active = false


static func _approach_angle(from: float, to: float, delta: float, sec: float) -> float:
	return from + wrapf(to - from, -PI, PI) * (1.0 - exp(-delta / maxf(sec, 0.001)))


## Смерть: клип по обстоятельствам — выстрел в голову, со стороны, в приседе, лёжа, взрыв
## (Player выбирает death_clip и зовёт один раз; враги используют ragdoll). Модель остаётся лежать
## в последнем кадре — это тот же персонаж, без манекена.
func die(clip: String) -> void:
	if _tree == null:
		return
	_dead = true
	_one_shot = ""
	_one_shot_kind = ""
	_downed_clip = ""
	if not _has(clip):
		clip = "death_front" if _has("death_front") else "death"
	_pose_to(clip)
	if _grip:
		_grip.visible = true
	# мёртвая рука цевьё не держит
	if _support:
		_support.influence = 0.0
	# обработка остаётся ради дальности (_tick_lod): тело вдали тоже перестаёт отбрасывать тень, а клип
	# смерти вдали доигрывается реже; живость уходит плавно (_settle_motion)


## Клип смерти: from — откуда стреляли (мир), zone — куда попали (Health.last_zone),
## стойка — где застало. Взрыв рядом — отлёт назад; в голову — свои клипы спереди / сзади.
func death_clip(from: Vector3, zone: String, crouched: bool, prone: bool) -> String:
	if prone or (_downed_clip != ""):
		return "death_prone"
	if zone.begins_with("blast"):
		return "death_blast"
	var local := Basis(Vector3.UP, -_body.rotation.y) * (from - _actor.global_position)
	local.y = 0.0
	var front := local.length() < 0.01 or local.z >= absf(local.x)
	if crouched:
		return "death_crouch_head" if zone == "head" else "death_crouch"
	if zone == "head":
		return "death_head_front" if front or local.z > -absf(local.x) else "death_head_back"
	if front:
		return "death_front"
	if local.z < -absf(local.x):
		return "death_back"
	return "death_right"


## Есть ли модель Persona с клипами (иначе смерть — прежним манекеном-регдоллом).
func has_model() -> bool:
	return _model != null and _tree != null


## Узел на кости модели (камера погибшего игрока следит за грудью).
func bone_node(bone: String) -> Node3D:
	if _model == null:
		return null
	var skeletons: Array[Node] = _model.find_children("*", "Skeleton3D", true, false)
	if skeletons.is_empty():
		return null
	var sk := skeletons[0] as Skeleton3D
	var existing := sk.get_node_or_null("Bone_" + bone) as Node3D
	if existing:
		return existing
	var att := BoneAttachment3D.new()
	att.name = "Bone_" + bone
	att.bone_name = bone
	sk.add_child(att)
	return att


func weapon_grip(family: String, weapon_id: String = "") -> Node3D:
	if _grip == null:
		if _model == null:
			return null
		var skeletons: Array[Node] = _model.find_children("*", "Skeleton3D", true, false)
		if skeletons.is_empty():
			return null
		var sk := skeletons[0] as Skeleton3D
		var socket := BoneAttachment3D.new()
		socket.name = "WeaponSocket"
		socket.bone_name = "mixamorig_RightHand"
		sk.add_child(socket)
		_grip = Node3D.new()
		_grip.name = "Grip"
		socket.add_child(_grip)
		_collision_ik = WeaponCollisionIK.new()
		_collision_ik.name = "WeaponCollisionIK"
		_collision_ik.grip = _grip
		_collision_ik.actor = _actor
		sk.add_child(_collision_ik)
		_support = SupportHandIK.new()
		_support.name = "SupportHandIK"
		_support.grip = _grip
		_support.influence = 0.0
		sk.add_child(_support)
		# живость — до рук у оружия: кисти ставятся к уже повёрнутому корпусу
		if _motion and _motion.get_parent() == sk:
			sk.move_child(_motion, 0)
	_grip.transform = socket_transform(family)
	# У собственного ассета запястье может отличаться от семейства; кость остаётся той же.
	_grip.position += _grip.basis * WeaponGrips.socket_offset(family, WeaponDb.weapon(weapon_id))
	return _grip


## Модель оружия в руке: видимый ребёнок узла Grip. Первым ребёнком брать нельзя — Player держит там же
## спрятанные модели из кэша (и пустую «без оружия»), и ИК левой руки не находил метку хвата.
static func held_model(grip: Node3D) -> Node3D:
	if not is_instance_valid(grip):
		return null
	for child: Node in grip.get_children():
		var model := child as Node3D
		if model and model.visible and not model.is_queued_for_deletion():
			return model
	return null


## Как оружие семейства лежит в ладони (в осях кости правой руки).
static func socket_transform(family: String) -> Transform3D:
	if _sockets.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(SOCKETS))
		if parsed is Dictionary:
			_sockets = parsed
	var s: Dictionary = _sockets.get(family, _sockets.get("rifle", {}))
	if s.is_empty():
		return Transform3D.IDENTITY
	var b: Array = s.basis
	return Transform3D(Basis(_vec(b[0]), _vec(b[1]), _vec(b[2])), _vec(s.origin))


static func _vec(a: Variant) -> Vector3:
	var v: Array = a
	return Vector3(float(v[0]), float(v[1]), float(v[2]))


## Смерть регдоллом на этой модели (SkinRagdoll): анимация и ИК стоят, поза — текущая. false — не вышло.
func ragdoll(velocity: Vector3, impulse: Vector3, at: Vector3) -> bool:
	if _model == null:
		return false
	var skel := _model.find_children("*", "Skeleton3D", true, false)
	if skel.is_empty():
		return false
	_dead = true
	_model.scale = Vector3.ONE
	if _tree:
		# дерево больше не двигает скелет: регдолл берёт текущую позу
		_tree.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_MANUAL
	if _motion:
		_motion.active = false
	if _support:
		_support.influence = 0.0
		_support.active = false
	if _collision_ik:
		_collision_ik.active = false
	if _grip:
		_grip.visible = false
	set_process(false)
	return SkinRagdoll.start(skel[0] as Skeleton3D, velocity, impulse, at) != null
