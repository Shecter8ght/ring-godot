extends RefCounted
## Ведомость игрового каталога. Общая привязка к набору и копии записей считаются отдельно.


static func scan(slots: Array[Dictionary], notes: ConfigFile) -> Dictionary:
	var by_content: Dictionary = {}
	var fingerprints: Dictionary = {}
	var coverage: PackedStringArray = []
	var gaps: PackedStringArray = []
	var shared: PackedStringArray = []
	var stereo: PackedStringArray = []
	var manual: PackedStringArray = []
	for slot: Dictionary in slots:
		var materials: PackedStringArray = []
		for surface: String in slot.surfaces:
			materials.append(Audio.step_surface_name(surface))
		var label: String = String(slot.name)
		if not materials.is_empty():
			label += " — " + ", ".join(materials)
		var files: Array = slot.files
		var loaded: Dictionary = slot.loaded
		var ready: int = 0
		if files.is_empty():
			gaps.append(label + " · нет назначенных записей")
		for relative: String in files:
			var stream: AudioStream = loaded.get(relative) as AudioStream
			if not stream:
				gaps.append("%s · файл не загрузился — %s" % [label, relative])
				continue
			ready += 1
			if not fingerprints.has(relative):
				fingerprints[relative] = _fingerprint(relative, stream)
			var fingerprint: String = fingerprints[relative]
			if not by_content.has(fingerprint):
				by_content[fingerprint] = PackedStringArray()
			var copies: PackedStringArray = by_content[fingerprint]
			copies.append("%s · %s" % [slot.name, relative])
			by_content[fingerprint] = copies
			if stream is AudioStreamWAV and (stream as AudioStreamWAV).stereo:
				stereo.append("%s · %s" % [slot.name, relative])
		coverage.append("%s · %d из %d" % [label, ready, files.size()])
		if materials.size() > 1:
			shared.append("%s · %s" % [slot.name, ", ".join(materials)])
		var note: String = String(notes.get_value("notes", String(slot.hook), "")).strip_edges()
		if not note.is_empty():
			manual.append("%s · %s" % [slot.name, note])
	var duplicates: PackedStringArray = []
	for copies: PackedStringArray in by_content.values():
		if copies.size() > 1:
			duplicates.append(" ↔ ".join(copies))
	var report: String = "# Ведомость звуков шагов RING\n\n"
	report += "Отдельный набор для бега предусмотрен у плитки. На остальных покрытиях бег использует основной набор.\n\n"
	report += _section("Пропуски в игровом каталоге", gaps)
	report += _section("Точные дубли", duplicates)
	report += _section("Пометки", manual)
	report += _section("Общие наборы по назначению", shared)
	report += _section("Стереозаписи WAV", stereo)
	report += _section("Все назначения", coverage)
	report += "Дубли сверены по содержимому доступных файлов, по данным загруженного WAV или по пути.\n"
	report += "Одинаково звучащие записи после разной обработки требуют проверки на слух.\n"
	return {"text": report, "gaps": gaps.size(), "duplicates": duplicates.size()}


static func _section(title: String, lines: PackedStringArray) -> String:
	var text: String = "## " + title + "\n\n"
	for line: String in lines:
		text += "- " + line + "\n"
	return text + ("Пусто.\n\n" if lines.is_empty() else "\n")


static func _fingerprint(relative: String, stream: AudioStream) -> String:
	var path: String = "res://assets/audio/" + relative
	if FileAccess.file_exists(path):
		var hash: String = FileAccess.get_sha256(path)
		if not hash.is_empty():
			return "file:" + hash
	if stream is AudioStreamWAV:
		# В экспортированной игре доступны импортированные записи, даже если исходный WAV упакован отдельно.
		var wav: AudioStreamWAV = stream as AudioStreamWAV
		var hash: HashingContext = HashingContext.new()
		hash.start(HashingContext.HASH_SHA256)
		hash.update(("%d/%d/%s" % [wav.format, wav.mix_rate, wav.stereo]).to_utf8_buffer())
		hash.update(wav.data)
		return "wav:" + hash.finish().hex_encode()
	return "path:" + path
