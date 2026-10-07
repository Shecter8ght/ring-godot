class_name QuestWorld
extends Node
## Сюжет в мире уровня (рейд или убежище): ставит места квестов (QuestSite) по состоянию Quests,
## охрану этапа (хост), раненых NPC, которых несут игроки. Создают Raid (рейд) и HideoutLevel
## (убежище).
##
## Группа (кооп): места общие — у всех одни и те же (состояние сюжета одно, у хоста; см. Quests).
## Свой игрок осматривает / обыскивает / входит в зону — просьба хосту (Quests.request_site); хост
## сверяет здесь, рядом ли просящий (near_site). Раненого поднимает и кладёт любой — тоже через
## хост (Quests.request_carry); несут его на плече у того, кто поднял, — видно всем. Убийства,
## «предмет в рюкзаке» и эвакуацию считает хост за любого участника (extraction_payload).

## Уровень: имя файла сцены без расширения (f1_ring, hideout) — sites.level в данных.
var level: String = ""
var raid: bool = false

var _sites: Dictionary = {}
## Декорации мест с NPC (ящики, кровь) — отдельно: раненого уносят, сцена остаётся на месте.
var _decor: Dictionary = {}
var _guarded: Dictionary = {}
## Раненые на плече: site -> узел картинки (у всех peer).
var _carry_vis: Dictionary = {}
## Корень уровня (сцена .tscn, в которой живём) — места ставятся в него.
var _root: Node


func _ready() -> void:
	_root = get_parent()
	while _root and _root.scene_file_path == "" and _root.get_parent() != get_tree().root:
		_root = _root.get_parent()
	level = _root.scene_file_path.get_file().get_basename() if _root else ""
	# Ремейк открывается и напрямую, а квесты по-прежнему относятся к логическому hideout.
	if _root and _root.is_in_group("hideout_level"):
		level = "hideout"
	Quests.world = self
	if raid:
		Quests.begin_raid()
	Quests.changed.connect(_refresh)
	# коллизии уровня попадают в физику через кадр — пол под местами ищем после
	for i in range(2):
		await get_tree().physics_frame
	_refresh()


func _exit_tree() -> void:
	if Quests.world == self:
		Quests.world = null
	# хост (соло) уходит из рейда — итог сюжета за рейд: вынес кто-то — засчитано, нет — нет
	if raid:
		Quests.end_raid()
	var me := _me()
	if me:
		me.carrying = false
	Quests.hud.carry_hint("")


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
		if not want.has(sid) and Quests.carrier_of(String(sid)) == 0:
			(_sites[sid] as Node).queue_free()
			_sites.erase(sid)
			if _decor.has(sid):
				(_decor[sid] as Node).queue_free()
				_decor.erase(sid)
	# раненый: несут ли его, где положили; цель «вынести NPC» — его можно поднять
	for sid in _sites:
		var s: QuestSite = _sites[sid]
		s.carried = Quests.carrier_of(String(sid)) != 0
		var at := Quests.npc_pos(String(sid))
		if not s.carried and at != Vector3.INF:
			s.global_position = at
		var o := Quests.objective(s.quest_id)
		s.can_carry = String(o.get("type", "")) == "extract_with_npc" and String(o.get("npc", "")) == s.npc_id() and not s.carried
	if raid and not Quests.is_client():
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


## Охрана этапа (мародёры у места) — один раз за рейд; ставит хост.
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


# ---------------------------------------------------------------- хост: проверки и эвакуация

## Хост: игрок peer рядом с местом sid (осмотр, обыск, зона, поднять раненого).
func near_site(peer: int, sid: String) -> bool:
	var s: QuestSite = _sites.get(sid)
	var pl := _player(peer)
	if s == null or pl == null or not pl.is_alive():
		return false
	var reach := maxf(Balance.INTERACT_RADIUS, maxf(float(s.spec.get("radius", 2.0)), float(s.spec.get("zone", 0.0))))
	return pl.global_position.distance_to(s.global_position) <= reach + 2.5


## Хост: с чем эвакуировался игрок peer — предметы рюкзака и раненые (несёт или рядом, ≤ 5 м).
func extraction_payload(peer: int) -> Dictionary:
	var pl := _player(peer)
	var items: Array = []
	var npcs: Array = []
	if pl:
		for e in pl.inventory.items:
			items.append(String(e.id))
		for sid in _sites:
			var s: QuestSite = _sites[sid]
			if s.npc_id() == "":
				continue
			if Quests.carrier_of(String(sid)) == peer or (not s.carried and s.global_position.distance_to(pl.global_position) <= 5.0):
				npcs.append(s.npc_id())
	return {"items": items, "npcs": npcs, "peer": peer}


# ---------------------------------------------------------------- раненого несут

func pick_up(s: QuestSite) -> void:
	Quests.request_carry(s.site_id, true)


func put_down() -> void:
	var me := _me()
	var sid := _my_carried()
	if sid == "" or me == null:
		return
	# кладём рядом, на пол (сидит, привалившись)
	var at := _floor_under(me.global_position + Vector3(sin(me.body_yaw()), 0, cos(me.body_yaw())) * 0.9)
	Quests.request_carry(sid, false, at)


## Место раненого, которого несёт свой игрок ("" — никого).
func _my_carried() -> String:
	var mine := _my_id()
	for sid in _sites:
		if Quests.carrier_of(String(sid)) == mine:
			return String(sid)
	return ""


## Совместимость: место, которое несёт свой игрок (null — никого).
func carrying() -> QuestSite:
	var sid := _my_carried()
	return _sites.get(sid) if sid != "" else null


func _my_id() -> int:
	return multiplayer.get_unique_id() if Net.is_networked() else 1


func _me() -> Player:
	if Raid.current:
		return Raid.current.local_player()
	return get_tree().get_first_node_in_group("players") as Player


func _player(peer: int) -> Player:
	if not Net.is_networked():
		peer = 1
	for n in get_tree().get_nodes_in_group("all_players"):
		var p := n as Player
		if p and p.peer_id == peer and p.is_inside_tree():
			return p
	return null


func _process(_delta: float) -> void:
	var me := _me()
	var mine := _my_carried()
	if me:
		me.carrying = mine != ""
		if mine != "":
			if not me.is_alive() or me.is_downed():
				# упал — раненого уронил рядом
				put_down()
			elif Input.is_action_just_pressed("drag") and not PauseMenu.shown:
				put_down()
	# раненые на плече — у того, кто несёт (видно всем); от первого лица свой не мешает обзору
	for sid in _sites.keys():
		var carrier := Quests.carrier_of(String(sid))
		var pl := _player(carrier) if carrier != 0 else null
		if pl == null:
			if _carry_vis.has(sid):
				(_carry_vis[sid] as Node).queue_free()
				_carry_vis.erase(sid)
			continue
		var s: QuestSite = _sites[sid]
		s.global_position = pl.global_position
		if not _carry_vis.has(sid):
			var vis := Node3D.new()
			QuestProps.build_person(vis, "carried", Color(0.28, 0.3, 0.24))
			_root.add_child(vis)
			_carry_vis[sid] = vis
		var v := _carry_vis[sid] as Node3D
		v.visible = not (pl == me and me.ads)
		v.global_transform = Transform3D(Basis(Vector3.UP, pl.body_yaw() + PI * 0.5), pl.global_position + Vector3.UP * 1.45)
	Quests.hud.carry_hint("Несёшь раненого — X: положить" if mine != "" else "")
	if Quests.is_client():
		return
	# хост: несущий упал, погиб или ушёл — раненый остаётся там, где он был
	for sid in _sites.keys():
		var carrier := Quests.carrier_of(String(sid))
		if carrier == 0 or carrier == _my_id():
			continue
		var pl := _player(carrier)
		if pl == null or not pl.is_alive() or pl.is_downed() or not pl.is_in_group("players"):
			var at := (_sites[sid] as Node3D).global_position
			Quests.drop_carried(String(sid), _floor_under(at))
	# хост: «предмет в рюкзаке» — у любого участника
	if raid:
		for qid in Quests.ids():
			var o := Quests.objective(qid)
			if Quests.state(qid) != "ACTIVE" or String(o.get("type", "")) != "pickup_item":
				continue
			for n in get_tree().get_nodes_in_group("players"):
				var p := n as Player
				if p and p.inventory and p.inventory.has(String(o.item)):
					Quests.event("have_item", {"item": String(o.item)})
					break
