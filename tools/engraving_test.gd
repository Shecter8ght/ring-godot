extends Node
## Полный ресурс головки, миграция, запись с отказом диска, груз и журнал возврата.
var fails: int = 0


func check(label: String, value: bool) -> void:
	print("%s: %s" % ["PASS" if value else "FAIL", label])
	if not value:
		fails += 1


func _ready() -> void:
	await get_tree().process_frame
	Profile.use_file("user://engraving_test.json", true)
	check("станок закрыт до установки", Engraver.block() != "")
	Profile.flags["engraver_installed"] = true
	check("станку нужен генератор", Engraver.block() != "")
	Profile.modules["generator"] = 1
	Profile.stash = []
	var head: Dictionary = ItemDb.make("laser_head", 1)
	ItemDb.add_to(Profile.stash, head, Profile.stash_grid())
	for index: int in range(4):
		ItemDb.add_to(Profile.stash, ItemDb.make("wpn_ar_05", 1), Profile.stash_grid())
	check("головки не складываются", not ItemDb.can_merge(head, ItemDb.make("laser_head", 1)))
	var uid: String = String(Profile.stash[1].uid)
	check("10 мест на двуручном и 6 на пистолетах", WeaponMark.positions("wpn_ar_01").size() == 10 and WeaponMark.positions("wpn_hg_01").size() == 6 and WeaponMark.positions("wpn_hg_02").size() == 6)
	for pistol_id: String in ["wpn_hg_01", "wpn_hg_02"]:
		var grips: int = 0
		var slides: int = 0
		for site: Dictionary in WeaponMark.positions(pistol_id):
			if String(site.part) == "slide":
				slides += 1
			elif String(site.part) == "grip":
				grips += 1
		check("у %s есть рукоятка и затвор с обеих сторон" % pistol_id, grips == 4 and slides == 2)
	var mark: Dictionary = WeaponMark.make(Profile.stash[1], "Иван [b]")
	check("предпросмотр ничего не списал", int(Profile.stash[0].charges) == 3 and not Profile.stash[1].has("engraving"))
	var original_path: String = Profile.path
	Profile.path = "user://missing_directory/denied.json"
	var refused: String = Engraver.apply("stash", 1, uid, "stash", 0, String(head.uid), "Иван [b]", mark)
	check("отказ записи откатывает оружие и головку", refused != "" and not Profile.stash[1].has("engraving") and int(Profile.stash[0].charges) == 3)
	Profile.path = original_path
	var stale: String = Engraver.apply("stash", 1, "wrong_uid", "stash", 0, String(head.uid), "Иван [b]", mark)
	check("перемещение предмета отменяет нанесение", stale != "" and int(Profile.stash[0].charges) == 3)
	for index: int in range(1, 4):
		var entry: Dictionary = Profile.stash[index]
		var text: String = "Иван %d" % index
		check("нанесение %d" % index, Engraver.apply("stash", index, String(entry.uid), "stash", 0, String(head.uid), text, WeaponMark.make(entry, text, "left_2")) == "")
	check("ровно три использования", int(Profile.stash[0].charges) == 0)
	check("выбранная сторона и место записаны", String(Profile.stash[1].engraving.site) == "left_2")
	var fourth: Dictionary = Profile.stash[4]
	check("четвёртая надпись запрещена", Engraver.apply("stash", 4, String(fourth.uid), "stash", 0, String(head.uid), "Четвёртая", WeaponMark.make(fourth, "Четвёртая")) != "")
	var spare_head: Dictionary = ItemDb.make("laser_head", 1)
	Profile.stash.append(spare_head)
	check("сменить надпись нельзя и с новой головкой", Engraver.apply("stash", 1, uid, "stash", 5, String(spare_head.uid), "Замена", WeaponMark.make(Profile.stash[1], "Замена")) != "" and int(spare_head.charges) == 3)
	var saved_id: String = Profile.profile_id
	Profile.save()
	Profile._loaded = false
	Profile.ensure()
	var saved_gun: Dictionary = {}
	var saved_head: Dictionary = {}
	for e: Dictionary in Profile.stash:
		if String(e.get("uid", "")) == uid:
			saved_gun = e
		if String(e.get("uid", "")) == String(head.uid):
			saved_head = e
	check("перезагрузка сохраняет дату, номер, владельца и ресурс", Profile.profile_id == saved_id and not saved_gun.is_empty() and String(saved_gun.engraving.date) == String(WeaponMark.make(saved_gun, "").date) and int(saved_head.charges) == 0)
	var gun: Dictionary = saved_gun.duplicate(true)
	gun.mods = {"optic": {"id": "optic_rd_01", "dur": 63.0}}
	var book: Dictionary = {"lost": {}, "pending": {uid: {"owner": "friend", "zone": "f1_ring", "weapon": gun, "returning": false}}}
	WeaponRecovery.settle(book)
	check("потеря даёт пять рейдов и полную сборку", int(book.lost[uid].remaining) == 5 and book.lost[uid].weapon.mods == gun.mods)
	check("другая зона и отсутствие владельца не расходуют окно", WeaponRecovery.eligible(book, "host", "f1_ring").is_empty() and WeaponRecovery.eligible(book, "friend", "f2").is_empty() and int(book.lost[uid].remaining) == 5)
	book.lost[uid].remaining = 2
	book.pending[uid] = {"owner": "friend", "zone": "f1_ring", "weapon": gun, "returning": true}
	WeaponRecovery.settle(book)
	check("поднял и погиб — окно не сбрасывается", int(book.lost[uid].remaining) == 2)
	var window: Dictionary = {"lost": {uid: {"owner": "friend", "zone": "f1_ring", "weapon": gun, "remaining": 5}}, "pending": {}}
	var rng: RandomNumberGenerator = RandomNumberGenerator.new()
	rng.seed = 37
	for attempt: int in range(5):
		WeaponRecovery.draw(window, "absent", "f1_ring", rng)
		check("чужой рейд %d не старит окно" % attempt, int(window.lost[uid].remaining) == 5 - attempt)
		WeaponRecovery.draw(window, "friend", "f1_ring", rng)
		WeaponRecovery.settle(window)
	check("пять попыток — запись истекла", window.lost.is_empty())
	var hits: int = 0
	for attempt: int in range(1000):
		var trial: Dictionary = {"lost": {uid: {"owner": "friend", "zone": "f1_ring", "weapon": gun, "remaining": 5}}, "pending": {}}
		if not WeaponRecovery.draw(trial, "friend", "f1_ring", rng).is_empty():
			hits += 1
	check("шанс около 25 процентов, возврат не гарантирован", hits > 180 and hits < 320)
	var recovery: WeaponRecovery = WeaponRecovery.new()
	add_child(recovery)
	recovery.journal = book
	recovery.escaped([gun])
	recovery.finish()
	check("вынос любым напарником закрывает потерю", recovery.journal.lost.is_empty() and recovery.journal.pending.is_empty())
	recovery.queue_free()
	Profile.quests = {}
	Profile.flags = {}
	Quests.start("own_mark")
	Quests.finish_talk("own_mark", "trader", "intro")
	Quests.begin_raid()
	check("рама из обычного ящика подходит", Quests.cargo_site_for({"id": "engraver_frame", "n": 1, "fir": true}) == "engraver_frame")
	check("покупка / один id не подменяет груз", Quests.cargo_site_for({"id": "engraver_frame", "n": 1}) == "")
	Quests.event("extracted", {"items": ["engraver_frame"], "cargo": []})
	check("просто id без физического груза не засчитывает цель", String(Quests.objective("own_mark").type) == "extract_cargo")
	Quests.on_extracted({"cargo": ["engraver_frame"]})
	Quests.end_raid()
	Quests.finish_talk("own_mark", "trader", "frame")
	Quests.begin_raid()
	Quests.on_extracted({"cargo": ["engraver_controller"]})
	Quests.end_raid()
	Quests.finish_talk("own_mark", "trader", "installed")
	check("станок установлен после двух грузов", bool(Quests.flag("engraver_installed")) and Upgrades.level("engraver") == 1)
	Quests.begin_raid()
	Quests.on_extracted({"cargo": ["engraver_head"]})
	Quests.end_raid()
	Quests.finish_talk("own_mark", "trader", "ready")
	check("квест завершён без обязательной надписи", Quests.state("own_mark") == "COMPLETED")
	check("редкая головка не продаётся торговцем", TraderStock.catalog_of("laser_head") == 0)
	check("головку нельзя докупить через шаблон", not Profile.buy("laser_head", 1))
	var loot_counts: Dictionary = {"laser_head": 0, "engraver_frame": 0, "engraver_controller": 0}
	for trial: int in range(2000):
		for table: String in ["tools", "electronics"]:
			for entry: Dictionary in ItemDb.roll(table, rng):
				if loot_counts.has(String(entry.id)):
					loot_counts[String(entry.id)] += 1
	check("в ящиках редкие головки и оба узла", int(loot_counts.laser_head) > 10 and int(loot_counts.engraver_frame) > 10 and int(loot_counts.engraver_controller) > 10)
	print("engraving_test: failures=%d" % fails)
	get_tree().quit(1 if fails else 0)
