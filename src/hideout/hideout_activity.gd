@tool
class_name HideoutActivity
extends Interactable
## Досуг в убежище (F рядом): телевизор — каналы (новости, футбол, помехи, выкл.), экран светит
## в комнату; магнитола — станции (лоуфай, рок-н-ролл, вальс под баян), звук синтезируется тут же;
## ящик пива — выпил: в глазах качает (у себя), своим — «открыл пиво»; место на диване — сесть.
## Состояние ТВ и магнитолы общее для всех в убежище (кооп): переключил — у всех, пришёл позже —
## передадут. Всё локально, без хоста (в убежище его может и не быть).

enum Kind { TV, RADIO, BEER, SEAT }

const TV_CHANNELS := ["выкл.", "новости", "футбол", "помехи"]
const RADIO_STATIONS := ["выкл.", "лоуфай", "рок-н-ролл", "вальс под баян"]
## Цвет, которым экран светит в комнату, по каналу.
const TV_GLOW := [Color(0, 0, 0), Color(0.35, 0.5, 1.0), Color(0.45, 0.95, 0.5), Color(0.8, 0.82, 0.85)]
const MIX := 22050.0

@export var kind: Kind = Kind.TV:
	set(v):
		kind = v
		_rebuild()
## ТВ: свет от экрана в комнату (OmniLight3D сцены).
@export var glow_light: NodePath
## Место: куда смотрит сидящий (курс, градусы).
@export var seat_yaw: float = 180.0
## ТВ: размер экрана (м) — квад перед корпусом.
@export var screen_size: Vector2 = Vector2(1.8, 0.95)
## Готовый меш вместо блокаутного корпуса; экран получает прежний shader и каналы.
@export var authored_visual: bool = false
@export var screen_path: NodePath

var state: int = 0
var _screen_mat: ShaderMaterial
var _sound: AudioStreamPlayer3D
var _known: Array[int] = []
## Какой луп должен играть (строится в фоне — вдруг уже переключили).
var _want: String = ""
var _audio_tasks: Array[int] = []
var _shared_ready: bool = false
static var _cache: Dictionary = {}


func _exit_tree() -> void:
	# Worker использует методы activity: не освобождаем её посреди синтеза при смене сцены.
	for task: int in _audio_tasks:
		WorkerThreadPool.wait_for_task_completion(task)
	_audio_tasks.clear()
	if is_instance_valid(_sound):
		_sound.stop()


func _ready() -> void:
	super._ready()
	if Engine.is_editor_hint():
		return
	Profile.ensure()
	if kind in [Kind.TV, Kind.RADIO]:
		# Пришедший в уже занятую комнату получает общий канал от прежнего участника.
		var occupied: bool = false
		if Net.is_networked():
			for id: int in Net.peer_scene:
				if id != multiplayer.get_unique_id() and Net.visible_in(id, "hideout"):
					occupied = true
					_known.append(id)
		if not occupied:
			state = clampi(int(Profile.hideout_media.get("tv" if kind == Kind.TV else "radio", 0)), 0, 3)
		_sound = AudioStreamPlayer3D.new()
		_sound.bus = &"Ambient"
		_sound.unit_size = 3.0
		_sound.max_distance = 24.0
		add_child(_sound)
		Net.scenes_changed.connect(_share_state)
		_shared_ready = not Net.is_networked()
		if Net.is_networked():
			_initialize_shared.call_deferred()
	_apply()


func prompt() -> String:
	match kind:
		Kind.TV:
			return "телевизор: %s → %s" % [TV_CHANNELS[state], TV_CHANNELS[(state + 1) % TV_CHANNELS.size()]]
		Kind.RADIO:
			return "магнитола: %s → %s" % [RADIO_STATIONS[state], RADIO_STATIONS[(state + 1) % RADIO_STATIONS.size()]]
		Kind.BEER:
			return "открыть пиво"
	return "сесть"


## Всё локально: переключил — всем в убежище; пиво и диван — себе.
func request_use() -> void:
	match kind:
		Kind.TV:
			_switch((state + 1) % TV_CHANNELS.size())
		Kind.RADIO:
			_switch((state + 1) % RADIO_STATIONS.size())
		Kind.BEER:
			var lvl := get_tree().get_first_node_in_group("hideout_level")
			if lvl and lvl.has_method("drink"):
				lvl.call("drink")
			_sound_once(_fizz())
			if Net.is_networked():
				for peer: int in Net.peer_scene:
					if peer != multiplayer.get_unique_id() and Net.visible_in(peer,"hideout"):
						_said.rpc_id(peer,"%s открыл пиво" % String(Net.player_names.get(multiplayer.get_unique_id(), "Кто-то")))
		Kind.SEAT:
			var me := _local_player()
			if me:
				me.sit(global_position, deg_to_rad(seat_yaw))


func _local_player() -> Player:
	for p in get_tree().get_nodes_in_group("players"):
		if (p as Player).is_local():
			return p as Player
	return null


func _switch(v: int) -> void:
	if Net.is_networked():
		for peer: int in Net.peer_scene:
			if peer != multiplayer.get_unique_id() and Net.visible_in(peer,"hideout"):
				_set_state.rpc_id(peer,v)
	_set_state(v)


@rpc("any_peer", "call_local", "reliable")
func _set_state(v: int) -> void:
	_shared_ready = true
	_known = _here()
	state = clampi(v, 0, 3)
	Profile.hideout_media["tv" if kind == Kind.TV else "radio"] = state
	Profile.save()
	_apply()


@rpc("any_peer", "call_remote", "reliable")
func _said(text: String) -> void:
	if Quests.hud:
		Quests.hud.toast(text)


## Пришёл кто-то новый в убежище — передать ему, что включено (передаёт тот из уже бывших тут,
## у кого наименьший id, — один раз).
func _share_state() -> void:
	if not Net.is_networked() or not _shared_ready:
		return
	var me := multiplayer.get_unique_id()
	var here: Array[int] = _here()
	for id in here:
		if id == me or id in _known:
			continue
		var senders := here.filter(func(x: int) -> bool: return x != id and (x in _known or x == me))
		senders.sort()
		if not senders.is_empty() and int(senders[0]) == me:
			_set_state.rpc_id(id, state)
	_known = here


func _here() -> Array[int]:
	var result: Array[int] = []
	for peer: int in Net.peer_scene:
		if Net.visible_in(peer,"hideout"):
			result.append(peer)
	return result


func _initialize_shared() -> void:
	# Дать сценам/roster прийти: только уже бывший в комнате передаёт новичку канал.
	# Так же работает, когда хост ещё в рейде или возвращается после двух клиентов.
	await get_tree().create_timer(.15).timeout
	if _shared_ready:
		return
	var here: Array[int] = _here()
	var me: int = multiplayer.get_unique_id()
	for peer: int in here:
		if peer != me:
			_request_media.rpc_id(peer)
	await get_tree().create_timer(.35).timeout
	if _shared_ready:
		return
	here = _here()
	here.sort()
	# Все вошли одновременно: один участник начинает с сохранённого канала.
	if here.is_empty() or here[0] == me:
		_shared_ready = true
		_switch(clampi(int(Profile.hideout_media.get("tv" if kind==Kind.TV else "radio",0)),0,3))


@rpc("any_peer", "call_remote", "reliable")
func _request_media() -> void:
	var peer: int = multiplayer.get_remote_sender_id()
	if _shared_ready and Net.visible_in(peer,"hideout"):
		_set_state.rpc_id(peer,state)


func _apply() -> void:
	match kind:
		Kind.TV:
			if _screen_mat:
				_screen_mat.set_shader_parameter("channel", state)
			var gl := get_node_or_null(glow_light) as Light3D
			if gl:
				if not gl.has_meta("energy"):
					gl.set_meta("energy", gl.light_energy)
				gl.visible = state != 0
				gl.light_color = TV_GLOW[state]
				gl.light_energy = float(gl.get_meta("energy")) * (1.2 if state == 3 else 1.0)
			_loop(["", "news", "crowd", "static"][state])
		Kind.RADIO:
			_loop(["", "lofi", "rock", "waltz"][state])


# ---------------------------------------------------------------- вид

func _build_visual(parent: Node3D) -> void:
	if authored_visual:
		if kind == Kind.TV:
			var screen: MeshInstance3D = get_node_or_null(screen_path) as MeshInstance3D
			if screen:
				var shader: Shader = Shader.new()
				shader.code = TV_SHADER
				_screen_mat = ShaderMaterial.new()
				_screen_mat.shader = shader
				_screen_mat.set_shader_parameter("channel", state)
				screen.material_override = _screen_mat
		return
	match kind:
		Kind.TV:
			var q := MeshInstance3D.new()
			var qm := QuadMesh.new()
			qm.size = screen_size
			q.mesh = qm
			var sh := Shader.new()
			sh.code = TV_SHADER
			_screen_mat = ShaderMaterial.new()
			_screen_mat.shader = sh
			_screen_mat.set_shader_parameter("channel", state)
			q.material_override = _screen_mat
			q.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			parent.add_child(q)
		Kind.RADIO:
			_box(parent, Vector3(0, 0.13, 0), Vector3(0.52, 0.26, 0.16), Color(0.12, 0.12, 0.13))
			for sx in [-0.16, 0.16]:
				var sp := MeshInstance3D.new()
				var cm := CylinderMesh.new()
				cm.top_radius = 0.075
				cm.bottom_radius = 0.075
				cm.height = 0.02
				sp.mesh = cm
				sp.rotation.x = PI * 0.5
				sp.position = Vector3(sx, 0.12, 0.085)
				var m := StandardMaterial3D.new()
				m.albedo_color = Color(0.05, 0.05, 0.05)
				m.roughness = 0.9
				sp.material_override = m
				parent.add_child(sp)
			_box(parent, Vector3(0, 0.22, 0.082), Vector3(0.12, 0.04, 0.01), Color(0.9, 0.6, 0.2), 2.0)
			_box(parent, Vector3(0, 0.3, 0), Vector3(0.36, 0.03, 0.03), Color(0.2, 0.2, 0.2))
		Kind.BEER:
			_box(parent, Vector3(0, 0.14, 0), Vector3(0.42, 0.28, 0.32), Color(0.45, 0.32, 0.12))
			var glass := StandardMaterial3D.new()
			glass.albedo_color = Color(0.35, 0.2, 0.05, 0.85)
			glass.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
			glass.roughness = 0.1
			glass.metallic_specular = 0.8
			for i in range(6):
				var b := MeshInstance3D.new()
				var bm := CylinderMesh.new()
				bm.top_radius = 0.012
				bm.bottom_radius = 0.03
				bm.height = 0.26
				b.mesh = bm
				b.material_override = glass
				b.position = Vector3(-0.13 + (i % 3) * 0.13, 0.4, -0.07 + (i / 3) * 0.14)
				parent.add_child(b)
			_label(parent, "Пиво", 0.75, Color(1.0, 0.85, 0.5))
		Kind.SEAT:
			pass


# ---------------------------------------------------------------- звук (синтез, без файлов)

func _loop(key: String) -> void:
	if _sound == null:
		return
	_want = key
	if key == "":
		_sound.stop()
		return
	if _cache.has(key):
		_play_loop(key)
		return
	# луп строится в фоне (синтез — секунды) и играет, как готов
	var task: int = WorkerThreadPool.add_task(func() -> void:
		var w := _clip(key)
		_built.call_deferred(key, w))
	_audio_tasks.append(task)


func _built(key: String, w: AudioStreamWAV) -> void:
	_cache[key] = w
	if is_inside_tree() and _want == key:
		_play_loop(key)


func _play_loop(key: String) -> void:
	_sound.stream = _cache[key]
	_sound.volume_db = -6.0 if kind == Kind.RADIO else -10.0
	_sound.play()


func _sound_once(stream: AudioStream) -> void:
	var p := AudioStreamPlayer3D.new()
	p.stream = stream
	p.bus = &"World"
	p.finished.connect(p.queue_free)
	add_child(p)
	p.play()


## Готовый луп по ключу (строится один раз за игру).
func _clip(key: String) -> AudioStreamWAV:
	var s: PackedFloat32Array
	match key:
		"lofi":
			s = _music_lofi()
		"rock":
			s = _music_rock()
		"waltz":
			s = _music_waltz()
		"news":
			s = _noise_talk()
		"crowd":
			s = _noise_crowd()
		_:
			s = _noise_static()
	return _wav(s, true)


func _fizz() -> AudioStreamWAV:
	if _cache.has("fizz"):
		return _cache["fizz"]
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	var n := int(MIX * 0.9)
	var s := PackedFloat32Array()
	s.resize(n)
	for i in range(n):
		var t := float(i) / MIX
		var pop := exp(-t * 60.0) * sin(TAU * 420.0 * t) * 0.8
		var hiss := rng.randf_range(-1.0, 1.0) * 0.25 * exp(-t * 3.0) * clampf(t * 20.0, 0.0, 1.0)
		s[i] = pop + hiss
	var w := _wav(s, false)
	_cache["fizz"] = w
	return w


func _wav(s: PackedFloat32Array, loop: bool) -> AudioStreamWAV:
	var bytes := PackedByteArray()
	bytes.resize(s.size() * 2)
	for i in range(s.size()):
		bytes.encode_s16(i * 2, int(clampf(s[i], -1.0, 1.0) * 30000.0))
	var w := AudioStreamWAV.new()
	w.format = AudioStreamWAV.FORMAT_16_BITS
	w.mix_rate = int(MIX)
	w.stereo = false
	w.data = bytes
	if loop:
		w.loop_mode = AudioStreamWAV.LOOP_FORWARD
		w.loop_end = s.size()
	return w


static func _hz(midi: float) -> float:
	return 440.0 * pow(2.0, (midi - 69.0) / 12.0)


## Лоуфай: 72 уд/мин, Am7 — Dm7 — G7 — Cmaj7, мягкое электропиано, бас, шорох пластинки.
func _music_lofi() -> PackedFloat32Array:
	var bpm := 72.0
	var beat := 60.0 / bpm
	var chords := [[57, 60, 64, 67], [50, 57, 60, 65], [55, 59, 62, 65], [48, 55, 59, 64]]
	var bars := 4
	var n := int(MIX * beat * 4.0 * bars)
	var s := PackedFloat32Array()
	s.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	for i in range(n):
		var t := float(i) / MIX
		var b := t / beat
		var bar := int(b / 4.0) % bars
		var in_bar := fmod(b, 4.0)
		var ch: Array = chords[bar]
		var v := 0.0
		# аккорд — на 1 и на «и» 3-й доли, затухает
		var hit := minf(in_bar, absf(in_bar - 2.5) if in_bar >= 2.5 else 9.0)
		var env := exp(-hit * 1.6)
		for note in ch:
			var f := _hz(float(note))
			v += sin(TAU * f * t) * 0.07 * env + sin(TAU * f * 2.0 * t) * 0.015 * env
		# бас: корень на 1 и 3
		var bb := fmod(in_bar, 2.0)
		v += sin(TAU * _hz(float(ch[0]) - 12.0) * t) * 0.22 * exp(-bb * 2.5)
		# тихий хэт на «и»
		var hb := fmod(b + 0.5, 1.0)
		v += rng.randf_range(-1.0, 1.0) * 0.05 * exp(-hb * 40.0)
		# бочка на 1 и 3
		v += sin(TAU * (50.0 + 60.0 * exp(-bb * 30.0)) * t) * 0.35 * exp(-bb * 9.0)
		# шорох пластинки
		v += rng.randf_range(-1.0, 1.0) * 0.012 + (0.15 if rng.randf() < 0.0004 else 0.0)
		s[i] = v * 0.8
	return s


## Рок-н-ролл: 150 уд/мин, буги-бас по I — IV — I — V, малый барабан на 2 и 4.
func _music_rock() -> PackedFloat32Array:
	var bpm := 150.0
	var beat := 60.0 / bpm
	var roots := [45, 50, 45, 52]
	var boogie := [0, 4, 7, 9, 10, 9, 7, 4]
	var n := int(MIX * beat * 4.0 * roots.size())
	var s := PackedFloat32Array()
	s.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = 21
	var ph := 0.0
	for i in range(n):
		var t := float(i) / MIX
		var b := t / beat
		var bar := int(b / 4.0) % roots.size()
		var eighth := int(b * 2.0) % 8
		var f := _hz(float(roots[bar] + boogie[eighth]))
		ph = fmod(ph + f / MIX, 1.0)
		var e8 := fmod(b * 2.0, 1.0)
		var v := (ph * 2.0 - 1.0) * 0.16 * exp(-e8 * 2.0)
		# гитара: квинта аккорда, «рубит» восьмыми
		var g := _hz(float(roots[bar] + 12))
		v += (sign(sin(TAU * g * t)) * 0.05 + sign(sin(TAU * g * 1.5 * t)) * 0.04) * exp(-e8 * 5.0)
		var q := fmod(b, 1.0)
		var beat_i := int(b) % 4
		if beat_i == 1 or beat_i == 3:
			v += rng.randf_range(-1.0, 1.0) * 0.28 * exp(-q * 14.0)
		else:
			v += sin(TAU * (45.0 + 80.0 * exp(-q * 35.0)) * t) * 0.45 * exp(-q * 10.0)
		v += rng.randf_range(-1.0, 1.0) * 0.04 * exp(-fmod(b * 2.0, 1.0) * 50.0)
		s[i] = v * 0.8
	return s


## Вальс под баян: 3/4, «умпа-па»: бас на раз, аккорд на два-три, простая мелодия сверху.
func _music_waltz() -> PackedFloat32Array:
	var bpm := 120.0
	var beat := 60.0 / bpm
	var chords := [[57, 60, 64], [52, 56, 59], [57, 60, 64], [52, 56, 59], [50, 53, 57], [57, 60, 64], [52, 56, 59], [57, 60, 64]]
	var melody := [76, 74, 72, 71, 72, 74, 76, 77, 76, 74, 72, 71, 69, 71, 72, 71, 69, 68, 69, 71, 72, 74, 72, 71]
	var n := int(MIX * beat * 3.0 * chords.size())
	var s := PackedFloat32Array()
	s.resize(n)
	for i in range(n):
		var t := float(i) / MIX
		var b := t / beat
		var bar := int(b / 3.0) % chords.size()
		var in_bar := fmod(b, 3.0)
		var q := fmod(b, 1.0)
		var ch: Array = chords[bar]
		var v := 0.0
		# баян: несколько гармоник с лёгкой расстройкой (тремоло)
		var trem := 1.0 + 0.004 * sin(TAU * 5.5 * t)
		if in_bar < 1.0:
			var fb := _hz(float(ch[0]) - 12.0)
			v += _reed(fb, t, trem) * 0.2 * exp(-q * 1.5)
		else:
			for note in ch:
				v += _reed(_hz(float(note)), t, trem) * 0.06 * exp(-q * 3.0)
		var m := _hz(float(melody[int(b) % melody.size()]))
		v += _reed(m, t, trem) * 0.07 * (0.6 + 0.4 * exp(-q * 2.0))
		s[i] = v * 0.9
	return s


static func _reed(f: float, t: float, trem: float) -> float:
	return sin(TAU * f * t) + 0.5 * sin(TAU * f * 2.0 * t * trem) + 0.25 * sin(TAU * f * 3.0 * t) + 0.12 * sin(TAU * f * 4.0 * t * trem)


## Новости: «речь» — полосовой шум с переменной громкостью слогов.
func _noise_talk() -> PackedFloat32Array:
	var n := int(MIX * 6.0)
	var s := PackedFloat32Array()
	s.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = 31
	var lp := 0.0
	var lp2 := 0.0
	for i in range(n):
		var t := float(i) / MIX
		var syll := maxf(0.0, sin(TAU * 4.3 * t + sin(TAU * 0.7 * t) * 3.0)) * (0.5 + 0.5 * sin(TAU * 0.33 * t))
		var x := rng.randf_range(-1.0, 1.0)
		lp += (x - lp) * 0.25
		lp2 += (lp - lp2) * 0.25
		var voice := (lp - lp2) * 3.0 + sin(TAU * (130.0 + 20.0 * sin(TAU * 1.3 * t)) * t) * 0.25
		s[i] = voice * syll * 0.5
	return s


## Футбол: гул трибун с накатами.
func _noise_crowd() -> PackedFloat32Array:
	var n := int(MIX * 8.0)
	var s := PackedFloat32Array()
	s.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = 41
	var lp := 0.0
	for i in range(n):
		var t := float(i) / MIX
		lp += (rng.randf_range(-1.0, 1.0) - lp) * 0.08
		var swell := 0.5 + 0.35 * sin(TAU * 0.12 * t) + 0.25 * maxf(0.0, sin(TAU * 0.05 * t + 1.0)) ** 8.0
		s[i] = lp * 1.6 * swell
	return s


func _noise_static() -> PackedFloat32Array:
	var n := int(MIX * 2.0)
	var s := PackedFloat32Array()
	s.resize(n)
	var rng := RandomNumberGenerator.new()
	rng.seed = 51
	for i in range(n):
		s[i] = rng.randf_range(-1.0, 1.0) * 0.3
	return s


const TV_SHADER := """
shader_type spatial;
render_mode unshaded, cull_back, shadows_disabled;
uniform int channel = 0;
float hash(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
float box(vec2 p, vec2 c, vec2 h) { vec2 d = abs(p - c) - h; return step(max(d.x, d.y), 0.0); }
void fragment() {
	vec2 uv = UV;
	float t = TIME;
	vec3 c = vec3(0.012, 0.014, 0.016);
	if (channel == 1) {
		// новости: студия, ведущий, бегущая строка, логотип
		c = mix(vec3(0.05, 0.1, 0.3), vec3(0.12, 0.22, 0.55), uv.y);
		vec2 hp = (uv - vec2(0.38, 0.42)) * vec2(1.8, 1.0);
		c = mix(c, vec3(0.75, 0.6, 0.5), step(length(hp), 0.09));
		c = mix(c, vec3(0.1, 0.1, 0.14), step(length((uv - vec2(0.38, 0.8)) * vec2(1.0, 1.6)), 0.25) * step(0.55, uv.y));
		c = mix(c, vec3(0.75, 0.08, 0.08), box(uv, vec2(0.5, 0.86), vec2(0.5, 0.06)));
		float tick = step(0.5, fract((uv.x + t * 0.25) * 18.0)) * box(uv, vec2(0.5, 0.86), vec2(0.5, 0.02));
		c = mix(c, vec3(0.95), tick * 0.8);
		c = mix(c, vec3(0.9, 0.9, 0.95), box(uv, vec2(0.86, 0.12), vec2(0.07, 0.05)) * (0.7 + 0.3 * step(0.5, fract(t * 0.5))));
	} else if (channel == 2) {
		// футбол: полосы газона, разметка, мяч и игроки
		c = mix(vec3(0.1, 0.42, 0.14), vec3(0.14, 0.5, 0.18), step(0.5, fract(uv.x * 8.0)));
		float line = step(abs(uv.x - 0.5), 0.004) + step(abs(length((uv - 0.5) * vec2(1.8, 1.0)) - 0.18), 0.006);
		c = mix(c, vec3(0.9), clamp(line, 0.0, 1.0));
		vec2 ball = vec2(0.5 + 0.35 * sin(t * 0.7), 0.5 + 0.3 * sin(t * 1.1 + 1.0));
		c = mix(c, vec3(1.0), step(length((uv - ball) * vec2(1.8, 1.0)), 0.012));
		for (int i = 0; i < 10; i++) {
			float fi = float(i);
			vec2 p = ball + vec2(sin(t * 0.5 + fi * 2.1) * 0.25, cos(t * 0.6 + fi * 1.3) * 0.25);
			vec3 team = i < 5 ? vec3(0.85, 0.15, 0.12) : vec3(0.15, 0.3, 0.9);
			c = mix(c, team, step(length((uv - p) * vec2(1.8, 1.0)), 0.016));
		}
		c = mix(c, vec3(0.95), box(uv, vec2(0.14, 0.08), vec2(0.11, 0.035)) * 0.85);
	} else if (channel == 3) {
		float n = hash(floor(uv * vec2(320.0, 180.0)) + floor(t * 30.0));
		c = vec3(n * 0.85);
	}
	if (channel > 0) {
		c *= 0.9 + 0.1 * sin(uv.y * 520.0);
		c *= 0.94 + 0.06 * sin(t * 50.0);
		c *= 1.6;
	}
	ALBEDO = c;
}
"""
