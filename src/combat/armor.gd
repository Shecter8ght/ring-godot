class_name Armor
extends RefCounted
## Попадание по снаряжению — одно место для игрока и ИИ (считает хост). Броня — не HP: слой
## (плита своей стороны, мягкая часть жилета, шлем) сравнивает пробитие пули (pen) со своей
## защитой (класс × состояние). Не пробила — тупая травма, слой изнашивается; пробила — проходит
## часть урона, слой тоже изнашивается. Руки и ноги без брони (урон × зона). Голова: шлем
## остановил — травма; без шлема, мимо шлема или сквозь него — насмерть (решает Health).
## Сторона груди — по тому, откуда стреляли относительно корпуса (перед / спина).
## Числа — Balance.ARMOR, ARMOR_CLASS_PROT, ZONE_DAMAGE; определения — data/armor.json.

## Осколки гранаты — как слабая пуля.
const BLAST_BULLET := {"pen": 16.0, "armor_dmg": 12.0}


## equipment — снаряжение (armor, helmet — записи с прочностью и плитами); forward — куда смотрит
## корпус; from — откуда выстрел. Возвращает {damage, lethal, equipment (новое, если износ),
## layer — что приняло пулю ("" — ничего), stopped}.
static func hit(equipment: Dictionary, amount: float, zone: String, from: Vector3, at: Vector3, forward: Vector3, bullet: Dictionary, rng: RandomNumberGenerator) -> Dictionary:
	var eq := equipment.duplicate(true)
	var out := {"damage": amount, "lethal": false, "equipment": eq, "layer": "", "stopped": false}
	var b: Dictionary = bullet if not bullet.is_empty() else BLAST_BULLET
	match zone:
		"head":
			var h: Dictionary = eq.get("helmet", {})
			var hd := WeaponDb.helmet(String(h.get("id", "")))
			if hd.is_empty() or float(h.get("dur", 0.0)) <= 0.0 or rng.randf() > float(hd.coverage):
				out.lethal = true
				return out
			var r := _layer(float(hd["class"]), float(h.dur), float(hd.durability), float(hd.blunt), 1.0, amount, b, rng)
			h.dur = r.dur
			out.layer = "helmet"
			out.stopped = r.stopped
			out.damage = r.damage
			out.lethal = not bool(r.stopped)
			return out
		"arms", "legs":
			out.damage = amount * float(Balance.ZONE_DAMAGE.get(zone, 1.0))
			return out
	# грудь (и неизвестно куда, и осколки): плита своей стороны, потом мягкая часть
	var v: Dictionary = eq.get("armor", {})
	var vd := WeaponDb.vest(String(v.get("id", "")))
	if vd.is_empty():
		return out
	var side := "front"
	var to := from - at
	to.y = 0.0
	if to.length_squared() > 0.0001 and forward.dot(to.normalized()) < 0.0:
		side = "back"
	var plates: Dictionary = v.get("plates", {})
	if plates.has(side) and float(plates[side].dur) > 0.0:
		var pd := WeaponDb.plate(String(plates[side].id))
		if not pd.is_empty() and rng.randf() <= float(pd.coverage):
			var r := _layer(float(pd["class"]), float(plates[side].dur), float(pd.durability), float(pd.blunt), float(pd.wear), amount, b, rng)
			plates[side].dur = r.dur
			out.layer = "plate:" + side
			out.stopped = r.stopped
			out.damage = r.damage
			return out
	var soft = vd.get("soft")
	if soft is Dictionary and float(v.get("dur", 0.0)) > 0.0 and rng.randf() <= float(soft.coverage):
		var r := _layer(float(soft["class"]), float(v.dur), float(soft.durability), float(vd.blunt), 1.0, amount, b, rng)
		v.dur = r.dur
		out.layer = "soft"
		out.stopped = r.stopped
		out.damage = r.damage
	return out


## Один слой: пробила ли, сколько урона прошло, новая прочность.
static func _layer(cls: float, dur: float, max_dur: float, blunt: float, wear: float, amount: float, b: Dictionary, rng: RandomNumberGenerator) -> Dictionary:
	var a: Dictionary = Balance.ARMOR
	var prot_table: Array = Balance.ARMOR_CLASS_PROT
	var prot := float(prot_table[clampi(int(cls), 0, prot_table.size() - 1)])
	var frac := clampf(dur / maxf(max_dur, 1.0), 0.0, 1.0)
	var e := prot * (float(a.dur_floor) + (1.0 - float(a.dur_floor)) * frac)
	var pen := float(b.get("pen", 10.0))
	var p := smoothstep(e - float(a.window), e + float(a.window), pen)
	var through := rng.randf() < p
	var ad := float(b.get("armor_dmg", 10.0)) * wear * (float(a.wear_pen) if through else float(a.wear_stopped))
	var dmg := blunt * amount
	if through:
		dmg = amount * lerpf(float(a.through_min), 1.0, clampf((pen - e) / float(a.full_over), 0.0, 1.0))
	return {"stopped": not through, "damage": dmg, "dur": maxf(0.0, dur - ad)}


## Шанс пробить слой класса cls в состоянии frac (0–1) пулей с пробитием pen — для UI.
static func pen_chance(pen: float, cls: int, frac: float = 1.0) -> float:
	var a: Dictionary = Balance.ARMOR
	var prot_table: Array = Balance.ARMOR_CLASS_PROT
	var e := float(prot_table[clampi(cls, 0, prot_table.size() - 1)]) * (float(a.dur_floor) + (1.0 - float(a.dur_floor)) * frac)
	return smoothstep(e - float(a.window), e + float(a.window), pen)
