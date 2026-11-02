class_name DozorGear
extends RefCounted
## Shared item identities and lossless upgrade of previously installed flashlights.

const MOUNT := "mount_dozor_p"
const VARIANTS := {"tac_flashlight_01": "f1", "tac_flashlight_hp_01": "f1m", "tac_flashlight_strobe_01": "f1s"}


static func is_flashlight(id: String) -> bool:
	return VARIANTS.has(id)


static func upgrade(entry: Dictionary) -> Array:
	var out: Dictionary = entry.duplicate(true)
	var spill: Array = []
	var mods: Dictionary = out.get("mods", {})
	var pistol: bool = String(WeaponDb.weapon(String(out.get("id", ""))).get("class", "")) == "PISTOL"
	for key: String in WeaponBuild.sorted_keys(mods):
		var rec: Dictionary = WeaponCondition.mod_entry(mods[key])
		if not is_flashlight(String(rec.get("id", ""))):
			continue
		var parent: String = WeaponBuild.parent_key(key)
		if not pistol and parent != "" and WeaponDb.mod_id(mods.get(parent, {})) == MOUNT:
			continue
		mods.erase(key)
		if pistol:
			for field: String in ["slot", "flip", "angle"]:
				rec.erase(field)
			rec["n"] = 1
			spill.append(rec)
			continue
		# Only old, already installed lights receive their missing mount during migration.
		# New purchases/installation always require two independently owned items.
		var ring: Dictionary = {"id": MOUNT, "dur": float(rec.get("dur", 100.0))}
		for field: String in ["slot", "flip", "angle"]:
			if rec.has(field):
				ring[field] = rec[field]
				rec.erase(field)
		mods[key] = ring
		mods[key + "/light"] = rec
	out["mods"] = mods
	return [out, spill]


## Standalone inventory items only; lights inside another item are not available to the hand.
static func carried(items: Array, preferred: String = "") -> Dictionary:
	var first: Dictionary = {}
	for raw: Variant in items:
		if not raw is Dictionary:
			continue
		var rec: Dictionary = raw
		if not is_flashlight(String(rec.get("id", ""))) or WeaponCondition.broken(rec) or int(rec.get("n", 1)) < 1:
			continue
		if String(rec.id) == preferred:
			return rec
		if first.is_empty():
			first = rec
	return first
