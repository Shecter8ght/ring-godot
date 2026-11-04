class_name PhoneGear
extends RefCounted
## One personal phone. Its profile copy is retained while the raid loadout is on the actor.
const ID := "quest_phone"
const FLAG := "personal_phone"

static func personal(entry: Dictionary) -> bool:
	return String(entry.get("id", "")) == ID

static func without_phone(list: Array) -> Array:
	return list.filter(func(e: Dictionary) -> bool: return not personal(e)).duplicate(true)

static func phone_first(list: Array) -> Array:
	var out: Array = []
	for e: Dictionary in list:
		if personal(e): out.append(e.duplicate(true))
	out.append_array(without_phone(list))
	return out

static func ensure_profile() -> void:
	var car: Dictionary = Profile.quests.get("car_recovery", {})
	if not bool(Profile.flags.get(FLAG, false)) and car.is_empty():
		return
	Profile.flags[FLAG] = true
	var phone: Dictionary = ItemDb.make(ID, 1)
	for e: Dictionary in Profile.backpack:
		if personal(e): phone = e.duplicate(true); break
	phone.n = 1
	Profile.stash = without_phone(Profile.stash)
	Profile.pocket = without_phone(Profile.pocket)
	var list: Array = [phone]
	list.append_array(without_phone(Profile.backpack))
	var result := ItemDb.refit(list, Profile.grid_of("backpack"))
	Profile.backpack = result[0]
	for e: Dictionary in result[1]:
		# Migration never destroys an old player's loot when reserving the phone's two cells.
		var moved := ItemDb.add_to(Profile.stash, e, Profile.stash_grid())
		if moved < int(e.n):
			var remainder := e.duplicate(true)
			remainder.n = int(e.n) - moved
			ItemDb.add_to(Profile.stash, remainder, Vector2i.ZERO)

static func retained_profile() -> Array:
	return [ItemDb.make(ID, 1)] if bool(Profile.flags.get(FLAG, false)) else []
