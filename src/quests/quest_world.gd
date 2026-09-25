class_name QuestWorld
extends Node
## Сюжет в мире уровня (рейд или убежище): ставит места квестов (QuestSite) по состоянию Quests,
## охрану этапа (просьба к хосту), ведёт раненого NPC, которого несёт игрок, и сообщает Quests
## о конце рейда (эвакуация — с тем, что вынес: предметы и NPC; смерть / уход — без).
## Создают Raid (рейд) и HideoutLevel (убежище). Места — личные: у каждого игрока свои.

## Уровень: имя файла сцены без расширения (f1_ring, hideout) — sites.level в данных.
var level: String = ""
var raid: bool = false

var _sites: Dictionary = {}
## Декорации мест с NPC (ящики, кровь) — отдельно: раненого уносят, сцена остаётся на месте.
var _decor: Dictionary = {}
var _guarded: Dictionary = {}
var _carried: QuestSite = null
var _ended: bool = false
## Корень уровня (сцена .tscn, в которой живём) — места ставятся в него.
var _root: Node


func _ready() -> void:
	_root = get_parent()
	while _root and _root.scene_file_path == "" and _root.get_parent() != get_tree().root:
		_root = _root.get_parent()
	level = _root.scene_file_path.get_file().get_basename() if _root else ""
	if raid:
		Quests.begin_raid()
	Quests.changed.connect(_refresh)
	# коллизии уровня попадают в физику через кадр — пол под местами ищем после
	for i in range(2):
		await get_tree().physics_frame
	_refresh()


func _exit_tree() -> void:
	# ушёл из рейда не эвакуацией (меню, закрыл игру) — найденное не засчитано
	if raid and not _ended:
		_ended = true
		Quests.end_raid(false)
	_set_carrying(false)


func _refresh() -> void:
	if not is_inside_tree():
		return
	var want := {}
	for w in Quests.sites_for(level):
		var sid := String(w.site)
		want[sid] = w
		var s: QuestSite = _sites.get(sid)
		if s == null or not is_instance_valid(s):
			s = _spawn_site(String(w.quest), sid, w.def)
			if s == null:
				continue
			_sites[sid] = s
		s.active = bool(w.active)
	for sid in _sites.keys():
		if not want.has(sid) and _sites[sid] != _carried:
			(_sites[sid] as Node).queue_free()
			_sites.erase(sid)
			if _decor.has(sid):
				(_decor[sid] as Node).queue_free()
				_decor.erase(sid)
	# цель «вынести NPC» — его можно поднять
	for sid in _sites:
		var s: QuestSite = _sites[sid]
		var o := Quests.objective(s.quest_id)
		s.can_carry = String(o.get("type", "")) == "extract_with_npc" and String(o.get("npc", "")) == s.npc_id() and not s.carried
	if raid:
		_spawn_guards()


func _spawn_site(qid: String, sid: String, sd: Dictionary) -> QuestSite:
	var xf: Variant = _resolve(sid, sd, 0)
	if xf == null:
		push_warning("QuestWorld: не найти место %s" % sid)
		return null
	var spec := sd
	if String(sd.get("npc", "")) != "" and not (sd.get("props", []) as Array).is_empty():
		# NPC — сам по себе (его понесут), декорации — отдельным узлом на месте
		var decor := QuestSite.new()
		decor.name = "Quest_%s_decor" % sid
		decor.site_id = sid + "#decor"
		decor.spec = {"props": sd.props}
		_root.add_child(decor)
		decor.global_transform = xf
		_decor[sid] = decor
		spec = sd.duplicate()
		spec.erase("props")
	var s := QuestSite.new()
	s.name = "Quest_" + sid
	s.quest_id = qid
	s.site_id = sid
	s.spec = spec
	s.world = self
	_root.add_child(s)
	s.global_transform = xf
	return s


## Где стоит место: QuestAnchor в сцене (главнее) / anchor из данных (polar, node+local,
## near+offset, pos) + yaw; по высоте — на пол под точкой.
func _resolve(sid: String, sd: Dictionary, depth: int) -> Variant:
	for a in get_tree().get_nodes_in_group("quest_anchors"):
		if (a as QuestAnchor).site_id == sid:
			return (a as Node3D).global_transform
	var an: Dictionary = sd.get("anchor", {})
	var pos := Vector3.INF
	var yaw := deg_to_rad(float(sd.get("yaw", 0.0)))
	if an.has("polar"):
		pos = SectorBuilder.polar(float(an.polar[0]), float(an.polar[1]))
	elif an.has("node"):
		var n := _root.get_node_or_null(NodePath(String(an.node))) as Node3D
		if n:
			var l: Array = an.get("local", [0, 0, 0])
			pos = n.to_global(Vector3(float(l[0]), float(l[1]), float(l[2])))
			yaw += n.global_rotation.y
	elif an.has("near") and depth < 4:
		var other: Dictionary = _site_def(String(an.near))
		var base: Variant = _resolve(String(an.near), other, depth + 1)
		if base != null:
			var off: Array = an.get("offset", [0, 0, 0])
			var bx: Transform3D = base
			pos = bx * Vector3(float(off[0]), float(off[1]), float(off[2]))
			yaw += bx.basis.get_euler().y
	elif an.has("pos"):
		var p: Array = an.pos
		pos = Vector3(float(p[0]), float(p[1]), float(p[2]))
	if pos == Vector3.INF:
		return null
	pos = _floor_under(pos)
	return Transform3D(Basis(Vector3.UP, yaw), pos)


func _site_def(sid: String) -> Dictionary:
	for qid in Quests.ids():
		var sites: Dictionary = Quests.def(qid).get("sites", {})
		if sites.has(sid):
			return sites[sid]
	return {}


## Пол под точкой (перекрытие паркинга, двор) — луч сверху вниз по миру.
func _floor_under(p: Vector3) -> Vector3:
	var world := get_viewport().find_world_3d()
	var q := PhysicsRayQueryParameters3D.create(p + Vector3.UP * 1.5, p + Vector3.DOWN * 4.0, Hitscan.LAYER_WORLD)
	var hit := world.direct_space_state.intersect_ray(q)
	return hit.position if not hit.is_empty() else p


## Охрана этапа (мародёры у места) — один раз за рейд; ставит хост (у клиента — просьба).
func _spawn_guards() -> void:
	for g in Quests.guards_for(level):
		var key := String(g.quest) + ":" + String(g.site)
		if _guarded.has(key):
			continue
		var s: QuestSite = _sites.get(String(g.site))
		if s == null:
			continue
		_guarded[key] = true
		Raid.current.request_quest_guards(s.global_position, int(g.n), float(g.radius))


# ---------------------------------------------------------------- раненого несут

func pick_up(s: QuestSite) -> void:
	_carried = s
	s.carried = true
	s.can_carry = false
	_set_carrying(true)


func put_down() -> void:
	var me := _me()
	if _carried == null or me == null:
		return
	# кладём рядом, на пол (сидит, привалившись)
	_carried.global_position = _floor_under(me.global_position + Vector3(sin(me.body_yaw()), 0, cos(me.body_yaw())) * 0.9)
	_carried.carried = false
	_carried = null
	_set_carrying(false)
	_refresh()


func carrying() -> QuestSite:
	return _carried


func _set_carrying(on: bool) -> void:
	var me := _me()
	if me:
		me.carrying = on


func _me() -> Player:
	if Raid.current:
		return Raid.current.local_player()
	return get_tree().get_first_node_in_group("players") as Player


var _carry_vis: Node3D


func _process(_delta: float) -> void:
	var me := _me()
	if _carried and me:
		if not me.is_alive() or me.is_downed():
			# упал — раненого уронил рядом
			put_down()
		elif Input.is_action_just_pressed("drag") and not PauseMenu.shown and not me.is_downed():
			put_down()
		else:
			_carried.global_position = me.global_position
	# на плече — видно в изометрии; от первого лица не мешает обзору
	if _carried and me:
		if _carry_vis == null:
			_carry_vis = Node3D.new()
			QuestProps.build_person(_carry_vis, "carried", Color(0.28, 0.3, 0.24))
			_root.add_child(_carry_vis)
		_carry_vis.visible = not me.ads
		_carry_vis.global_transform = Transform3D(Basis(Vector3.UP, me.body_yaw() + PI * 0.5), me.global_position + Vector3.UP * 1.45)
		Quests.hud.carry_hint("Несёшь раненого — X: положить")
	elif _carry_vis:
		_carry_vis.queue_free()
		_carry_vis = null
		Quests.hud.carry_hint("")
	# «предмет в рюкзаке» — если такая цель есть
	if raid and me and me.inventory:
		for qid in Quests.ids():
			var o := Quests.objective(qid)
			if Quests.state(qid) == "ACTIVE" and String(o.get("type", "")) == "pickup_item" and me.inventory.has(String(o.item)):
				Quests.event("have_item", {"item": String(o.item)})


# ---------------------------------------------------------------- конец рейда (свой игрок)

## Эвакуировался: что вынес — предметы из рюкзака и NPC (несёт или рядом, ≤ 5 м).
func on_local_extracted() -> void:
	if _ended:
		return
	_ended = true
	var me := _me()
	var items: Array = []
	var npcs: Array = []
	if me:
		for e in me.inventory.items:
			items.append(String(e.id))
		for sid in _sites:
			var s: QuestSite = _sites[sid]
			if s.npc_id() != "" and (s == _carried or s.global_position.distance_to(me.global_position) <= 5.0):
				npcs.append(s.npc_id())
	Quests.end_raid(true, {"items": items, "npcs": npcs})


## Погиб: всё найденное в этом рейде — не в счёт (раненый NPC остался ждать).
func on_local_lost() -> void:
	if _ended:
		return
	_ended = true
	Quests.end_raid(false)
