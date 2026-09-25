extends CanvasLayer
## Общение в коопе (autoload `Chat`): текстовый чат и голос.
##  Чат — Enter: строка ввода, Enter — отправить, Esc — закрыть. Сообщение видят все в сети,
##  у говорящего над головой — реплика (если он рядом, в той же сцене). Пока пишешь, клавиши
##  не уходят персонажу (действия ввода отпускаются).
##  Голос — держать K: микрофон → 16 кГц, µ-law (8 бит) пакетами по 40 мс тем, кто в той же сцене
##  (Net.peer_scene); у слушателя — объёмно, из головы говорящего (AudioStreamPlayer3D на его
##  узле игрока), без узла — просто в уши. Числа — Balance.CHAT_*, Balance.VOICE.

const MIC_BUS := "VoiceMic"

var _log: VBoxContainer
var _line: LineEdit
var _typing: bool = false
var _last_msg_t: float = -100.0
var _speaking_label: Label
## Голос: микрофон, захват, передача.
var _mic: AudioStreamPlayer
var _capture: AudioEffectCapture
var _talking: bool = false
var _mic_off_t: float = 0.0
## Пересэмплирование в 16 кГц: доля шага и накопленное.
var _rs_pos: float = 0.0
var _out: PackedByteArray = PackedByteArray()
## Слушатель: peer → {player: AudioStreamPlayer3D / AudioStreamPlayer, pb: playback, t: когда слышали}.
var _voices: Dictionary = {}
## Для проверок: сколько байт голоса пришло от peer и последние сообщения чата.
var voice_bytes: Dictionary = {}
var messages: Array[String] = []
static var _ulaw: PackedFloat32Array = PackedFloat32Array()


func _ready() -> void:
	layer = 30
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_to_group("esc_windows")
	_build_ui()
	_build_ulaw()


## Пока пишешь — окно открыто (персонаж не стреляет, меню паузы не открывается по Esc).
func is_open() -> bool:
	return _typing


func is_typing() -> bool:
	return _typing


func _build_ui() -> void:
	_log = VBoxContainer.new()
	_log.anchor_top = 1.0
	_log.anchor_bottom = 1.0
	_log.offset_left = 24
	_log.offset_right = 640
	_log.offset_top = -430
	_log.offset_bottom = -250
	_log.alignment = BoxContainer.ALIGNMENT_END
	_log.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_log.add_theme_constant_override("separation", 2)
	add_child(_log)
	_line = LineEdit.new()
	_line.anchor_top = 1.0
	_line.anchor_bottom = 1.0
	_line.offset_left = 24
	_line.offset_right = 640
	_line.offset_top = -244
	_line.offset_bottom = -210
	_line.max_length = 200
	_line.placeholder_text = "Сообщение своим — Enter отправить, Esc закрыть"
	_line.visible = false
	_line.text_submitted.connect(_submit)
	add_child(_line)
	_speaking_label = Label.new()
	_speaking_label.anchor_top = 1.0
	_speaking_label.anchor_bottom = 1.0
	_speaking_label.offset_left = 24
	_speaking_label.offset_top = -470
	_speaking_label.offset_bottom = -440
	_speaking_label.offset_right = 640
	_speaking_label.add_theme_font_size_override("font_size", 16)
	_speaking_label.add_theme_color_override("font_color", Color(0.6, 0.95, 0.6))
	_speaking_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.85))
	_speaking_label.add_theme_constant_override("outline_size", 5)
	_speaking_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_speaking_label)


# ---------------------------------------------------------------- чат

func _unhandled_input(event: InputEvent) -> void:
	if not Net.is_networked() or _typing:
		return
	if event is InputEventKey and (event as InputEventKey).pressed and not (event as InputEventKey).echo \
			and (event as InputEventKey).keycode in [KEY_ENTER, KEY_KP_ENTER]:
		if PauseMenu.shown or get_viewport().gui_get_focus_owner() != null:
			return
		get_viewport().set_input_as_handled()
		open_input()


func open_input() -> void:
	_typing = true
	_line.visible = true
	_line.text = ""
	_line.grab_focus()
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_refresh_log()


func _close_input() -> void:
	_typing = false
	_line.release_focus()
	_line.visible = false
	_refresh_log()


func _submit(text: String) -> void:
	var t := text.strip_edges()
	_close_input()
	if t == "":
		return
	send(t)


## Отправить сообщение всем в сети.
func send(text: String) -> void:
	if Net.is_networked():
		_msg.rpc(text.substr(0, 200))


@rpc("any_peer", "call_local", "reliable")
func _msg(text: String) -> void:
	var from := multiplayer.get_remote_sender_id()
	if from == 0:
		from = multiplayer.get_unique_id()
	var who := String(Net.player_names.get(from, "Игрок %d" % from))
	var mine := String(Net.peer_scene.get(multiplayer.get_unique_id(), ""))
	var theirs := String(Net.peer_scene.get(from, ""))
	var where := ""
	if theirs != mine and theirs != "":
		where = {"hideout": " (в убежище)", "raid": " (в рейде)", "menu": " (в меню)"}.get(theirs, "")
	_add_line("%s%s: %s" % [who, where, text], from == multiplayer.get_unique_id())
	_bubble(from, text)


func _add_line(t: String, mine: bool) -> void:
	messages.append(t)
	if messages.size() > 50:
		messages.remove_at(0)
	var l := Label.new()
	l.text = t
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.add_theme_font_size_override("font_size", 17)
	l.add_theme_color_override("font_color", Color(0.85, 0.95, 1.0) if mine else Color(1.0, 0.93, 0.75))
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.9))
	l.add_theme_constant_override("outline_size", 6)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_log.add_child(l)
	while _log.get_child_count() > Balance.CHAT_LINES:
		var old := _log.get_child(0)
		_log.remove_child(old)
		old.queue_free()
	_last_msg_t = Time.get_ticks_msec() / 1000.0
	_refresh_log()


## Реплика над головой говорящего (если он здесь же).
func _bubble(peer: int, text: String) -> void:
	var pl := _player_of(peer)
	if pl == null:
		return
	var old := pl.get_node_or_null("ChatBubble")
	if old:
		old.queue_free()
	var b := Label3D.new()
	b.name = "ChatBubble"
	b.text = text if text.length() <= 60 else text.substr(0, 57) + "…"
	b.position = Vector3(0, 2.45, 0)
	b.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	b.font_size = 36
	b.pixel_size = 0.004
	b.outline_size = 8
	b.no_depth_test = true
	b.modulate = Color(1.0, 1.0, 0.92)
	b.width = 600.0
	b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	pl.add_child(b)
	# слабая ссылка: игрок мог уйти со сцены раньше таймера
	var wb: WeakRef = weakref(b)
	get_tree().create_timer(Balance.CHAT_BUBBLE_SEC).timeout.connect(func() -> void:
		var node := wb.get_ref() as Node
		if node:
			node.queue_free())


func _refresh_log() -> void:
	var age := Time.get_ticks_msec() / 1000.0 - _last_msg_t
	_log.modulate.a = 1.0 if _typing else clampf((Balance.CHAT_FADE_SEC - age) / 2.0, 0.0, 1.0)


## Пока пишешь, клавиши не должны доходить до персонажа: состояние действий отпускается
## (опрос Input.is_action_pressed в _process иначе видел бы «W» из текста).
func _input(event: InputEvent) -> void:
	if not _typing:
		return
	if event is InputEventKey:
		var k := event as InputEventKey
		if k.pressed and k.keycode == KEY_ESCAPE:
			get_viewport().set_input_as_handled()
			_close_input()
		for a in InputMap.get_actions():
			if event.is_action(a):
				Input.action_release(a)


func _process(delta: float) -> void:
	if not Net.is_networked():
		if _typing:
			_close_input()
		if _log.get_child_count() > 0:
			for c in _log.get_children():
				c.queue_free()
		_speaking_label.text = ""
		_stop_mic()
		return
	_refresh_log()
	_tick_voice(delta)


# ---------------------------------------------------------------- голос

func _ensure_mic() -> bool:
	if _capture:
		return true
	var idx := AudioServer.get_bus_index(MIC_BUS)
	if idx < 0:
		AudioServer.add_bus()
		idx = AudioServer.bus_count - 1
		AudioServer.set_bus_name(idx, MIC_BUS)
		# себя не слышать: шина заглушена, захват всё равно получает звук
		AudioServer.set_bus_mute(idx, true)
		AudioServer.add_bus_effect(idx, AudioEffectCapture.new())
	_capture = AudioServer.get_bus_effect(idx, 0) as AudioEffectCapture
	_mic = AudioStreamPlayer.new()
	_mic.stream = AudioStreamMicrophone.new()
	_mic.bus = MIC_BUS
	add_child(_mic)
	return _capture != null


func _stop_mic() -> void:
	_talking = false
	if _mic and _mic.playing:
		_mic.stop()


func _tick_voice(delta: float) -> void:
	var want := Input.is_action_pressed("voice") and not _typing and not PauseMenu.shown
	if want and not _talking and _ensure_mic():
		_talking = true
		_capture.clear_buffer()
		_rs_pos = 0.0
		if not _mic.playing:
			_mic.play()
	elif not want and _talking:
		# хвост фразы — ещё чуть-чуть
		_mic_off_t += delta
		if _mic_off_t > 0.25:
			_mic_off_t = 0.0
			_flush_packet(true)
			_stop_mic()
	if want:
		_mic_off_t = 0.0
	if _talking and _capture:
		var n := _capture.get_frames_available()
		if n > 0:
			_feed(_capture.get_buffer(n), AudioServer.get_mix_rate())
	# кто говорит (и я)
	var now := Time.get_ticks_msec() / 1000.0
	var names: Array[String] = []
	if _talking:
		names.append("ты")
	for peer in _voices:
		if now - float(_voices[peer].t) < 0.4:
			names.append(String(Net.player_names.get(peer, "Игрок")))
	_speaking_label.text = ("🎙 говорит: " + ", ".join(names)) if not names.is_empty() else ""


## Кадры микрофона (стерео, mix_rate) → моно 16 кГц → µ-law в очередь пакета.
func _feed(frames: PackedVector2Array, mix_rate: float) -> void:
	var rate := float(Balance.VOICE.rate)
	var step := mix_rate / rate
	var i := _rs_pos
	var n := frames.size()
	while i < n - 1:
		var i0 := int(i)
		var f := i - float(i0)
		var a := (frames[i0].x + frames[i0].y) * 0.5
		var b := (frames[i0 + 1].x + frames[i0 + 1].y) * 0.5
		_out.append(ulaw_encode(lerpf(a, b, f)))
		i += step
	_rs_pos = i - float(n)
	_flush_packet(false)


## Для проверок без микрофона: моно-сэмплы 16 кГц как будто сказаны в микрофон.
func debug_say(samples: PackedFloat32Array) -> void:
	for x in samples:
		_out.append(ulaw_encode(x))
	_flush_packet(true)


func _flush_packet(all: bool) -> void:
	var size := int(float(Balance.VOICE.rate) * float(Balance.VOICE.packet_sec))
	while _out.size() >= size or (all and _out.size() > 0):
		var k := mini(size, _out.size())
		var pkt := _out.slice(0, k)
		_out = _out.slice(k)
		_send_voice(pkt)


func _send_voice(pkt: PackedByteArray) -> void:
	var me := multiplayer.get_unique_id()
	var here := String(Net.peer_scene.get(me, ""))
	for peer in Net.peer_scene:
		if int(peer) != me and String(Net.peer_scene[peer]) == here:
			_voice.rpc_id(int(peer), pkt)


@rpc("any_peer", "call_remote", "unreliable_ordered", 2)
func _voice(pkt: PackedByteArray) -> void:
	var from := multiplayer.get_remote_sender_id()
	voice_bytes[from] = int(voice_bytes.get(from, 0)) + pkt.size()
	var v := _voice_of(from)
	if v.is_empty():
		return
	v.t = Time.get_ticks_msec() / 1000.0
	var pb := v.pb as AudioStreamGeneratorPlayback
	if pb == null:
		return
	var frames := PackedVector2Array()
	frames.resize(pkt.size())
	for i in range(pkt.size()):
		var s := _ulaw[pkt[i]]
		frames[i] = Vector2(s, s)
	if pb.can_push_buffer(frames.size()):
		pb.push_buffer(frames)


## Проигрыватель голоса peer: на его узле игрока (объёмно) или просто в уши. Узел игрока сменился
## (убежище → рейд) — создаётся заново.
func _voice_of(peer: int) -> Dictionary:
	var pl := _player_of(peer)
	var v: Dictionary = _voices.get(peer, {})
	var host: Node = pl if pl else self
	if not v.is_empty() and is_instance_valid(v.player) and (v.player as Node).get_parent() == host:
		return v
	if not v.is_empty() and is_instance_valid(v.player):
		(v.player as Node).queue_free()
	var gen := AudioStreamGenerator.new()
	gen.mix_rate = float(Balance.VOICE.rate)
	gen.buffer_length = float(Balance.VOICE.buffer_sec)
	var player: Node
	if pl:
		var p3 := AudioStreamPlayer3D.new()
		p3.stream = gen
		p3.position = Vector3(0, 1.6, 0)
		p3.max_distance = float(Balance.VOICE.max_m)
		p3.unit_size = 6.0
		p3.volume_db = float(Balance.VOICE.db)
		p3.name = "Voice"
		pl.add_child(p3)
		p3.play()
		player = p3
	else:
		var p2 := AudioStreamPlayer.new()
		p2.stream = gen
		p2.volume_db = float(Balance.VOICE.db)
		add_child(p2)
		p2.play()
		player = p2
	var pb: Variant = player.call("get_stream_playback")
	v = {"player": player, "pb": pb, "t": 0.0}
	_voices[peer] = v
	return v


func _player_of(peer: int) -> Player:
	for n in get_tree().get_nodes_in_group("all_players"):
		var p := n as Player
		if p and p.peer_id == peer and p.is_inside_tree():
			return p
	return null


# ---------------------------------------------------------------- µ-law (G.711)

static func ulaw_encode(x: float) -> int:
	var s := clampi(int(x * 32767.0), -32767, 32767)
	var sign := 0
	if s < 0:
		sign = 0x80
		s = -s
	s = mini(s + 132, 32635)
	var e := 7
	var mask := 0x4000
	while e > 0 and (s & mask) == 0:
		e -= 1
		mask >>= 1
	var mant := (s >> (e + 3)) & 0x0F
	return (~(sign | (e << 4) | mant)) & 0xFF


static func _build_ulaw() -> void:
	if not _ulaw.is_empty():
		return
	_ulaw.resize(256)
	for i in range(256):
		var u := (~i) & 0xFF
		var sign := u & 0x80
		var e := (u >> 4) & 0x07
		var mant := u & 0x0F
		var s := (((mant << 3) + 132) << e) - 132
		_ulaw[i] = (-float(s) if sign != 0 else float(s)) / 32768.0


static func ulaw_decode(b: int) -> float:
	_build_ulaw()
	return _ulaw[b & 0xFF]
