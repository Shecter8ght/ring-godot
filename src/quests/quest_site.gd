class_name QuestSite
extends Interactable
## Место сюжетного квеста в мире (data/quests → sites): сцена-заглушка (QuestProps) и то, что
## с ней делает игрок. Ставит QuestWorld — у всей группы места одни и те же (сюжет общий, у хоста).
## Осмотреть можно, только если место — текущая цель (active); иначе это декорация этапа. Осмотр,
## обыск, зона — у себя (реплики видит тот, кто осматривает), засчитывает хост (Quests.request_site).
##   prompt + lines  — F: осмотреть (lines — реплики на экране)
##   search_s        — обыск: держаться рядом столько секунд
##   zone            — войти в радиус — цель засчитана (место встречи, ворота)
##   npc             — раненый NPC (сидит / лежит; его несут — см. QuestWorld)

var quest_id: String = ""
var site_id: String = ""
var spec: Dictionary = {}
var active: bool = false
## NPC несут (скрыт на месте) / можно поднять (цель «вынести»).
var carried: bool = false
var can_carry: bool = false
var world: QuestWorld

var _search_t: float = -1.0
var _npc_vis: Node3D


func _build_visual(parent: Node3D) -> void:
	var cargo: String = String(spec.get("cargo", ""))
	if cargo != "":
		var model: Node3D = ItemModels.build(cargo)
		model.name = "QuestCargo"
		parent.add_child(model)
		var minimum_y: float = 0.0
		for child: Node in model.find_children("*", "MeshInstance3D", true, false):
			var mesh: MeshInstance3D = child as MeshInstance3D
			var box: AABB = ItemModels._xf_to(model, mesh) * mesh.get_aabb()
			minimum_y = minf(minimum_y, box.position.y)
		model.position.y = -minimum_y + 0.02
	var rng := RandomNumberGenerator.new()
	rng.seed = hash(site_id)
	for p in spec.get("props", []):
		parent.add_child(QuestProps.build(p, rng))
	var npc := String(spec.get("npc", ""))
	if npc != "":
		_npc_vis = Node3D.new()
		_npc_vis.name = "Npc"
		var on_cot := npc.ends_with("_resting")
		_npc_vis.position.y = 0.43 if on_cot else 0.0
		QuestProps.build_person(_npc_vis, "lying" if on_cot else "sitting", Color(0.28, 0.3, 0.24))
		parent.add_child(_npc_vis)


func npc_id() -> String:
	return String(spec.get("npc", ""))


func can_use() -> bool:
	if carried:
		return false
	if can_carry:
		return true
	return (active or npc_id().ends_with("_resting")) and String(spec.get("prompt", "")) != "" and _search_t < 0.0


func prompt() -> String:
	if can_carry:
		return "поднять раненого"
	var s := float(spec.get("search_s", 0.0))
	return String(spec.prompt) + (" (%.0f с)" % s if s > 0.0 else "")


## F своим игроком: поднять раненого / начать обыск / осмотреть — засчитывает хост.
func request_use() -> void:
	if can_carry and world:
		world.pick_up(self)
		return
	if float(spec.get("search_s", 0.0)) > 0.0 and active:
		_search_t = 0.0
		return
	_done()


func _done() -> void:
	_search_t = -1.0
	var lines: Array = spec.get("lines", [])
	if not lines.is_empty():
		Quests.subtitles.emit(lines)
	if active:
		if String(Quests.objective(quest_id).get("type", "")) != "extract_cargo":
			active = false
		Quests.request_site(site_id)


func _process(delta: float) -> void:
	if Engine.is_editor_hint():
		return
	var cargo: Node3D = _vis.get_node_or_null("QuestCargo") as Node3D if _vis != null else null
	if cargo != null:
		cargo.visible = not Quests.cargo_claimed(site_id)
	var me := _local_player()
	if me == null:
		return
	var d := me.global_position.distance_to(global_position)
	if _search_t >= 0.0:
		# обыск: отошёл — сначала
		if d > float(spec.get("radius", 2.0)) + 1.0:
			_search_t = -1.0
			Quests.hud.progress("", 0.0)
		else:
			_search_t += delta
			var total := float(spec.search_s)
			Quests.hud.progress("Осматриваю…", _search_t / total)
			if _search_t >= total:
				Quests.hud.progress("", 0.0)
				_done()
	if active and float(spec.get("zone", 0.0)) > 0.0 and d <= float(spec.zone):
		_done()
	if _npc_vis:
		_npc_vis.visible = not carried


func _local_player() -> Player:
	if Raid.current:
		return Raid.current.local_player()
	return get_tree().get_first_node_in_group("players") as Player
