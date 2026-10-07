class_name ShelterSave
extends RefCounted
## Запись ресурсов авторских инструментов убежища с повтором: на Windows только что записанный файл
## кратко держит антивирус или индексатор, и повторная запись того же пути падает «Cannot save file».

const ATTEMPTS: int = 12
const PAUSE_MSEC: int = 150


static func save(resource: Resource, path: String) -> Error:
	var result: Error = ResourceSaver.save(resource, path)
	var attempt: int = 1
	while result != OK and attempt < ATTEMPTS:
		OS.delay_msec(PAUSE_MSEC * attempt)
		result = ResourceSaver.save(resource, path)
		attempt += 1
	if result != OK:
		push_error("ShelterSave: не записан %s (%s)" % [path, error_string(result)])
	return result
