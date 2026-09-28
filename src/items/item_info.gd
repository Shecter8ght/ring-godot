class_name ItemInfo
extends Control
## Описание предмета простыми словами — отдельным окошком (кнопка «i» на плашке, «Описание» в меню
## правой кнопки). Текст разделён на смысл, технические характеристики и короткую фразу «В деле»;
## числа берутся из живых данных, поэтому карточка не расходится с балансом. Закрыть — кнопкой,
## кликом мимо или Esc.

## Сколько окон описания открыто и когда закрылось последнее (кадр): окна-хозяева не закрываются
## тем же Esc, что закрыл описание.
static var _open: int = 0
static var _closed_frame: int = -10

const TYPE_TEXT := {
	"OPTIC_RED_DOT": "Коллиматор: красная точка без увеличения. Целиться быстро, с открытыми глазами — для ближнего и среднего боя.",
	"OFFSET_RED_DOT": "Угловой коллиматор на кронштейне 45°: второй прицел рядом с основным. От первого лица переключается средней кнопкой мыши — для близких целей, когда на стволе оптика.",
	"OPTIC_HOLOGRAPHIC": "Голографический прицел: крупная метка, широкое окно — быстрее всего навестись вблизи.",
	"OPTIC_2X": "Прицел с увеличением 2×: чуть ближе, но ещё быстрый. Середина между коллиматором и оптикой.",
	"OPTIC_4X": "Оптика 4×: для стрельбы на 100 м и дальше. Вблизи мешает — узкое поле зрения.",
	"OPTIC_LPVO": "Переменная кратность 1–6×: и вблизи, и далеко. Тяжелее и дороже обычных.",
	"OPTIC_8X": "Оптика 8×: для дальней стрельбы с марксманской или снайперской винтовки.",
	"OPTIC_12X": "Оптика 12×: самая сильная. Только для дальних выстрелов с упора.",
	"FLASH_HIDER": "Пламегаситель: прячет вспышку выстрела — ночью труднее понять, откуда стреляют.",
	"COMPENSATOR": "Компенсатор: гасит увод ствола вверх — очередью попадать проще.",
	"MUZZLE_BRAKE": "Дульный тормоз: заметно снижает отдачу, но выстрел громче.",
	"SUPPRESSOR": "Глушитель: выстрел слышно гораздо ближе — мародёры издалека не поймут, где ты. Добавляет длину и вес.",
	"VERTICAL_GRIP": "Вертикальная рукоятка под цевьё: меньше отдача, ствол держится ровнее.",
	"ANGLED_GRIP": "Угловая рукоятка: быстрее вскидываешь оружие в прицел.",
	"COMPACT_GRIP": "Короткая рукоятка: немного помогает с отдачей, почти ничего не весит.",
	"HEAVY_GRIP": "Массивная рукоятка: сильно гасит отдачу, но оружие тяжелее и медленнее в прицел.",
	"HAND_STOP": "Упор для руки: рука не соскальзывает — чуть меньше отдача и раскачка.",
	"BIPOD": "Сошки: лёжа или сидя у упора разброс и отдача резко падают.",
	"FIXED_HEAVY": "Тяжёлый приклад: оружие устойчивее, отдача меньше, но вскидывать медленнее.",
	"FIXED_LIGHT": "Лёгкий приклад: оружие ловчее, отдача чуть больше.",
	"TELESCOPIC": "Телескопический приклад: удобная середина между устойчивостью и весом.",
	"FOLDING": "Складной приклад: оружие короче и легче, но отдача сильнее.",
	"PERIMETER_TACTICAL": "Тактический приклад «Периметра»: лучший баланс отдачи и удобства.",
	"FLASHLIGHT": "Фонарь на оружие (T — включить): светит туда, куда смотрит ствол. Светящего видно издалека.",
	"LASER": "ЛЦУ — лазерная точка (L): точнее стрельба от бедра. Луч видят и мародёры.",
	"FLASHLIGHT_LASER_COMBO": "Фонарь и лазер в одном блоке: T — свет, L — лазер. Занимает одно место на планке.",
}
const CAT_NAMES := {"weapon": "Оружие", "ammo": "Патроны", "mag": "Магазин", "mod": "Обвес", "armor": "Снаряжение",
	"plate": "Бронеплита", "med": "Медицина", "food": "Еда и вода", "tech": "Электроника", "value": "Ценное",
	"barter": "Бартер", "tools": "Инструменты и детали", "intel": "Документы", "key": "Ключ", "throw": "Гранаты и свет", "misc": "Разное"}


## Открыть окно описания предмета entry ({id, …}) поверх parent (Control или CanvasLayer).
static func open(parent: Node, entry: Dictionary) -> ItemInfo:
	var w := ItemInfo.new()
	w._build(entry)
	parent.add_child(w)
	_open += 1
	return w


## Идёт ли показ описания (или только что закрыли): Esc — окну описания, не хозяину.
static func blocking() -> bool:
	return _open > 0 or Engine.get_process_frames() - _closed_frame <= 1


func _exit_tree() -> void:
	_open = maxi(0, _open - 1)
	_closed_frame = Engine.get_process_frames()


func _close() -> void:
	_closed_frame = Engine.get_process_frames()
	queue_free()


func _input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		get_viewport().set_input_as_handled()
		_close()


func _build(entry: Dictionary) -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	# клик мимо окна — закрыть
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.35)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	dim.gui_input.connect(func(e: InputEvent) -> void:
		if e is InputEventMouseButton and (e as InputEventMouseButton).pressed:
			_close())
	add_child(dim)
	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.custom_minimum_size = Vector2(620, 0)
	panel.grow_horizontal = Control.GROW_DIRECTION_BOTH
	panel.grow_vertical = Control.GROW_DIRECTION_BOTH
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0.085, 0.08, 0.075, 0.98)
	sb.border_color = Color(0.95, 0.78, 0.5, 0.45)
	sb.set_border_width_all(1)
	sb.set_corner_radius_all(4)
	sb.set_content_margin_all(18)
	panel.add_theme_stylebox_override("panel", sb)
	add_child(panel)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 10)
	panel.add_child(v)
	var id := String(entry.get("id", ""))
	var head := HBoxContainer.new()
	head.add_theme_constant_override("separation", 14)
	v.add_child(head)
	var icon := ItemCard.IconBox.new()
	icon.id = id
	icon.custom_minimum_size = Vector2(150, 96)
	head.add_child(icon)
	var hv := VBoxContainer.new()
	hv.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	head.add_child(hv)
	var title := Label.new()
	title.text = ItemDb.item_name(id)
	title.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	title.add_theme_font_size_override("font_size", 24)
	title.add_theme_color_override("font_color", Color(1.0, 0.86, 0.6))
	hv.add_child(title)
	var facts := Label.new()
	facts.text = facts_line(id)
	facts.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	facts.add_theme_font_size_override("font_size", 14)
	facts.add_theme_color_override("font_color", Color(0.68, 0.7, 0.66))
	hv.add_child(facts)
	var text := RichTextLabel.new()
	text.bbcode_enabled = true
	text.fit_content = true
	text.scroll_active = false
	text.custom_minimum_size = Vector2(584, 0)
	text.add_theme_font_size_override("normal_font_size", 16)
	text.add_theme_font_size_override("bold_font_size", 16)
	text.add_theme_color_override("default_color", Color(0.9, 0.89, 0.85))
	text.text = describe(id)
	v.add_child(text)
	var close := Button.new()
	close.text = "Понятно"
	close.focus_mode = Control.FOCUS_NONE
	close.size_flags_horizontal = Control.SIZE_SHRINK_END
	close.pressed.connect(_close)
	v.add_child(close)


## Строка фактов: вид, размер, вес, цена, стопка.
static func facts_line(id: String) -> String:
	var it := ItemDb.item(id)
	var s := ItemDb.size(id)
	var parts: Array[String] = [String(CAT_NAMES.get(String(it.get("cat", "misc")), "Разное"))]
	parts.append("%d×%d клет." % [s.x, s.y])
	parts.append("%.2f кг" % ItemDb.weight(id) if ItemDb.weight(id) < 1.0 else "%.1f кг" % ItemDb.weight(id))
	parts.append("цена %s ₽" % InventoryUI.money(ItemDb.value(id)))
	if ItemDb.stack(id) > 1:
		parts.append("в стопке до %d" % ItemDb.stack(id))
	return "  ·  ".join(parts)


## Описание простыми словами (BBCode).
static func describe(id: String) -> String:
	var it := ItemDb.item(id)
	var out: Array[String] = []
	var desc := String(it.get("desc", ""))
	var flavor := _flavor_text(it)
	var w := WeaponDb.weapon(id)
	if not w.is_empty():
		out.append(desc if desc != "" else "Оружие.")
		out.append("[b]Технические характеристики[/b]\n" + _weapon_text(id, w))
		if flavor != "":
			out.append(flavor)
		return "\n\n".join(out)
	var a := WeaponDb.ammo(id)
	if not a.is_empty():
		if desc != "":
			out.append(desc)
		out.append("[b]Технические характеристики[/b]\n" + _ammo_text(id, a))
		if flavor != "":
			out.append(flavor)
		return "\n\n".join(out)
	var mg := WeaponDb.magazine(id)
	if not mg.is_empty():
		out.append("[b]Технические характеристики[/b]\n" + _mag_text(id, mg))
		if flavor != "":
			out.append(flavor)
		return "\n\n".join(out)
	var at := WeaponDb.attachment(id)
	if not at.is_empty():
		var t := String(at.get("desc", ""))
		var blurb := String(TYPE_TEXT.get(String(at.get("type", "")), ""))
		out.append(blurb if t == "" else (blurb + " " + t if blurb != "" else t))
		out.append("[b]Технические характеристики[/b]\n" + _mod_text(id, at))
		if flavor != "":
			out.append(flavor)
		return "\n\n".join(out)
	var pl := WeaponDb.plate(id)
	if not pl.is_empty():
		out.append("Бронеплита класса %d. Вставляется в плитоносец (перетащи на надетый жилет или в слот). Держит пули, пока цела — каждое попадание её изнашивает." % int(pl["class"]))
		out.append(_protects(int(pl["class"])))
		out.append("Материал: %s. Прочность %d." % [{"steel": "сталь — тяжёлая, но живучая", "composite": "композит — легче стали", "ceramic": "керамика — лёгкая, но быстро крошится"}.get(String(pl.get("material", "")), String(pl.get("material", ""))), int(pl.durability)])
		return "\n\n".join(out)
	var v := WeaponDb.vest(id)
	if not v.is_empty():
		var soft: Variant = v.get("soft")
		var plates: Array = v.get("plates", [])
		if soft is Dictionary:
			out.append("Надевается в слот «Броня». Своя мягкая защита класса %d, закрывает %d%% корпуса." % [int(soft["class"]), int(float(soft.coverage) * 100.0)])
			out.append(_protects(int(soft["class"])))
		else:
			out.append("Надевается в слот «Броня». Сам по себе не защищает — только вставленные плиты.")
		if not plates.is_empty():
			out.append("Карманы под плиты: %s. Плиту — перетащить на жилет." % ", ".join(plates.map(func(p: String) -> String: return "спереди" if p == "front" else "сзади")))
		return "\n\n".join(out)
	var h := WeaponDb.helmet(id)
	if not h.is_empty():
		out.append("Надевается в слот «Шлем». Класс %d, закрывает %d%% головы — попадание в голову без шлема почти всегда кладёт." % [int(h["class"]), int(float(h.coverage) * 100.0)])
		out.append(_protects(int(h["class"])))
		return "\n\n".join(out)
	var hs := WeaponDb.headset(id)
	if not hs.is_empty():
		out.append("Надеваются в слот «Уши». Приглушают грохот выстрелов на %d дБ — в перестрелке не глохнешь и лучше слышишь остальное." % int(absf(float(hs.get("shots_db", 0.0)))))
		return "\n\n".join(out)
	out.append(desc if desc != "" else "Товар: продать Михалычу.")
	var use: Dictionary = it.get("use", {})
	if not use.is_empty() and desc == "":
		out.append("Лечит: +%d здоровья за %.1f с (H — выбрать лекарство, двойной клик в рюкзаке)." % [int(use.get("heal", 0)), float(use.get("time", 0.0))])
	return "\n\n".join(out)


static func _flavor_text(item: Dictionary) -> String:
	var phrase := String(item.get("flavor", "")).strip_edges()
	if phrase == "":
		return ""
	return "[color=#d7bd91][i]В деле: %s[/i][/color]" % phrase


static func _weapon_text(id: String, w: Dictionary) -> String:
	var spec := WeaponStats.compute(ItemDb.make(id, 1))
	var lines: Array[String] = []
	lines.append("[b]%s[/b], калибр [b]%s[/b], слот «%s»." % [String(WeaponDb.CLASS_NAMES.get(String(w["class"]), "")), WeaponDb.caliber_name(String(w.caliber)),
		"Пистолет" if String(w.slot) == "secondary" else "Основное"])
	if w.has("internal_mag"):
		lines.append("Магазин встроенный на %d — заряжается патронами прямо из рюкзака (R)." % int(w.internal_mag))
	else:
		var mags: Array[String] = []
		for mid in WeaponDb.ids("magazines"):
			if WeaponDb.mag_fits(id, String(mid)):
				mags.append("%d" % int(WeaponDb.magazine(String(mid)).capacity))
		lines.append("Магазины: на %s патронов. Продаётся без патронов — купи патроны калибра %s и снаряди магазин." % [", ".join(mags), WeaponDb.caliber_name(String(w.caliber))])
	var st: Dictionary = w.get("stats", {})
	lines.append("Огонь: %s, %d выстрелов в минуту. Бьёт прицельно примерно до %d м." % ["очередями" if bool(st.get("auto", false)) else "одиночными", int(st.get("rpm", 0)), int(spec.get("range_m", st.get("range", 0)))])
	var ergo := float(spec.get("ergo", 50))
	lines.append("Перезарядка %.1f с. Надёжность %.1f%%. Эргономика %d/100." % [float(spec.get("reload", st.get("reload", 0.0))), float(spec.get("reliability", st.get("reliability", 1.0))) * 100.0, int(ergo)])
	lines.append("В руке: %s. Выстрел слышно на %d м." % ["лёгкое и быстрое" if ergo >= 70 else ("среднее по удобству" if ergo >= 45 else "тяжёлое, в прицел вскидывается медленно"), int(spec.get("noise_m", 0))])
	var mounts: Dictionary = w.get("mounts", {})
	if not mounts.is_empty():
		var names: Array[String] = []
		for m in WeaponDb.MOUNTS:
			if mounts.has(m):
				names.append(String(WeaponDb.MOUNT_NAMES[m]).to_lower())
		lines.append("Обвес ставится: %s. У Михалыча нажми «Что подходит» — подсветит патроны, магазины и обвес к нему." % ", ".join(names))
	return "\n".join(lines)


static func _ammo_text(id: String, a: Dictionary) -> String:
	var lines: Array[String] = []
	var name := ItemDb.item_name(id).to_lower()
	var kind := "Обычные патроны — середина по урону и пробитию."
	if "бронебой" in name:
		kind = "Бронебойные: пробивают броню и плиты, но по голому телу бьют чуть слабее. Дороже."
	elif "экспансив" in name:
		kind = "Экспансивные: сильный урон по незащищённому, но броню почти не берут."
	elif "картечь" in name:
		kind = "Картечь: сразу %d дробин — страшно вблизи, бесполезна издалека и против брони." % int(a.get("pellets", 1))
	elif "пуля" in name:
		kind = "Пуля для ружья: одна тяжёлая пуля — бьёт далеко и сильно."
	elif "снайпер" in name:
		kind = "Точные патроны: меньше разброс, чуть сильнее обычных."
	elif "стар" in name or "гражд" in name or "пст" in name:
		kind = "Дешёвые патроны: слабо против брони."
	lines.append(kind)
	lines.append("Калибр [b]%s[/b]. Урон %d%s, пробитие %d." % [WeaponDb.caliber_name(String(a.caliber)), int(a.damage), (" × %d" % int(a.pellets)) if int(a.get("pellets", 1)) > 1 else "", int(a.pen)])
	lines.append("Скорость %d м/с. Урон броне %d. Множитель дальности %.2f, точности %.2f." % [int(a.get("velocity", 0)), int(a.get("armor_dmg", 0)), float(a.get("range_k", 1.0)), float(a.get("accuracy", 1.0))])
	var guns: Array[String] = []
	for wid in WeaponDb.ids("weapons"):
		if WeaponDb.ammo_fits(String(wid), id):
			guns.append(ItemDb.item_name(String(wid)))
	if not guns.is_empty():
		lines.append("Подходят к: %s." % ", ".join(guns))
	lines.append("Против брони (новой): %s." % _pen_table(float(a.pen)))
	lines.append("Патроны заряжают в магазин: правой кнопкой по патронам — «Снарядить магазины» (или R в рейде — досыпать в пустой).")
	return "\n".join(lines)


## «класс 2 — почти всегда, класс 3 — иногда …» — шанс пробить новый слой брони.
static func _pen_table(pen: float) -> String:
	var parts: Array[String] = []
	for cls in range(1, 6):
		var p := Armor.pen_chance(pen, cls)
		var w := "почти всегда" if p > 0.9 else ("чаще да" if p > 0.6 else ("через раз" if p > 0.4 else ("редко" if p > 0.1 else "нет")))
		parts.append("кл. %d — %s" % [cls, w])
	return ", ".join(parts)


## Что держит броня класса cls: обычные патроны по калибрам (шанс пробить новую).
static func _protects(cls: int) -> String:
	var stops: Array[String] = []
	var not_stops: Array[String] = []
	var seen: Dictionary = {}
	for aid in WeaponDb.ids("ammo"):
		var a := WeaponDb.ammo(String(aid))
		var cal := String(a.caliber)
		var name := ItemDb.item_name(String(aid)).to_lower()
		# по калибру — обычный патрон (не бронебойный, не экспансивный) и отдельно бронебойный
		var ap := "бронебой" in name
		if not ap and ("экспансив" in name or "стар" in name or "гражд" in name or "картечь" in name or "снайпер" in name):
			continue
		var key := cal + ("ap" if ap else "")
		if seen.has(key):
			continue
		seen[key] = true
		var label := WeaponDb.caliber_name(cal) + (" бронебойные" if ap else "")
		if Armor.pen_chance(float(a.pen), cls) < 0.4:
			stops.append(label)
		else:
			not_stops.append(label)
	# короче — перечислить меньшую часть
	var t := ""
	if stops.is_empty():
		t = "Не держит ничего серьёзного — только осколки и дробь издалека."
	elif not_stops.is_empty():
		t = "Держит все обычные патроны, даже бронебойные."
	elif stops.size() <= not_stops.size():
		t = "Держит: %s. Остальное пробивает." % ", ".join(stops)
	else:
		t = "Держит почти всё. Пробивают: %s." % ", ".join(not_stops)
	return t + " Изношенная броня держит хуже."


static func _mag_text(id: String, mg: Dictionary) -> String:
	var lines: Array[String] = []
	lines.append("Магазин на [b]%d[/b] патронов калибра %s. Продаётся пустым." % [int(mg.capacity), WeaponDb.caliber_name(WeaponDb.mag_caliber(id))])
	var reload_delta := int(round((float(mg.get("reload_k", 1.0)) - 1.0) * 100.0))
	var reliability_delta := int(round((float(mg.get("reliability", 1.0)) - 1.0) * 100.0))
	var effects: Array[String] = []
	if reload_delta != 0:
		effects.append("перезарядка %s" % _signed_percent(reload_delta))
	if int(mg.get("ergo", 0)) != 0:
		effects.append("эргономика %+d" % int(mg.ergo))
	if reliability_delta != 0:
		effects.append("надёжность %s" % _signed_percent(reliability_delta))
	lines.append("Влияние: %s." % ", ".join(effects) if not effects.is_empty() else "Штатная геометрия: без штрафов к перезарядке, эргономике и надёжности.")
	var guns: Array[String] = []
	for wid in WeaponDb.ids("weapons"):
		if WeaponDb.mag_fits(String(wid), id):
			guns.append(ItemDb.item_name(String(wid)))
	if not guns.is_empty():
		lines.append("Подходит к: %s." % ", ".join(guns))
	lines.append("Зачем запасные: в рейде R меняет пустой магазин на полный из рюкзака — быстро. Без полного магазина патроны досыпаются по одному — долго.")
	lines.append("Снарядить: правой кнопкой по магазину или патронам — «Снарядить магазины». Магазин можно перетащить прямо на оружие.")
	return "\n".join(lines)


static func _mod_text(id: String, attachment: Dictionary) -> String:
	var lines: Array[String] = []
	var effects := _mod_effects(attachment)
	lines.append("Эффекты: %s." % ", ".join(effects) if not effects.is_empty() else "Числовых модификаторов нет.")
	var fits: Array[String] = []
	for wid in WeaponDb.ids("weapons"):
		if not WeaponDb.mounts_for({"id": String(wid), "n": 1, "mods": {}}, id).is_empty():
			fits.append(ItemDb.item_name(String(wid)))
	var t := "Ставится на верстаке в убежище или у Михалыча («Обвес оружия»), в рейде — перетащить на оружие."
	if fits.is_empty():
		lines.append(t)
	else:
		lines.append("Подходит к: %s." % ", ".join(fits))
		lines.append(t)
	return "\n".join(lines)


static func _mod_effects(attachment: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var fx: Dictionary = attachment.get("fx", {})
	var multipliers := {
		"kick": "вертикальная отдача", "kick_h": "горизонтальная отдача", "shake": "раскачка",
		"spread": "разброс", "ads_spread": "разброс в прицеле", "noise": "дальность звука",
		"damage": "урон", "flash": "вспышка", "aim": "скорость прицеливания",
		"braced_kick": "отдача с упора", "braced_spread": "разброс с упора",
	}
	for key: String in multipliers:
		if fx.has(key):
			var delta := int(round((float(fx[key]) - 1.0) * 100.0))
			out.append("%s %s" % [String(multipliers[key]), _signed_percent(delta)])
	if fx.has("ergo"):
		out.append("эргономика %+d" % int(fx.ergo))
	if fx.has("db"):
		out.append("громкость %+d дБ" % int(fx.db))
	var zoom := float(attachment.get("zoom", 0.0))
	if zoom > 0.0:
		out.append("увеличение %.0f×" % zoom)
	var aim_k := float(attachment.get("aim_k", 1.0))
	if not is_equal_approx(aim_k, 1.0):
		out.append("скорость прицеливания %s" % _signed_percent(int(round((aim_k - 1.0) * 100.0))))
	var light: Dictionary = attachment.get("light", {})
	if not light.is_empty():
		out.append("дальность света %d м" % int(light.get("range", 0)))
	var laser: Dictionary = attachment.get("laser", {})
	if not laser.is_empty():
		out.append("разброс от бедра %s" % _signed_percent(int(round((float(laser.get("hip_spread", 1.0)) - 1.0) * 100.0))))
	return out


static func _signed_percent(value: int) -> String:
	return "%+d%%" % value if value != 0 else "без изменения"
