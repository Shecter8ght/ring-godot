class_name OsokaHud
extends Control
## Метка цели ПЗРК «Осока» на экране (владелец, docs/design/mission_helicopter.md: «удержание цели несколько секунд,
## метка зеленеет, пуск»). Головка ведёт цель — кольцо вокруг неё: жёлтое, дуга по кругу показывает долю захвата;
## захват — кольцо зелёное с уголками, подпись «ЗАХВАТ — ЛКМ пуск». Внизу — строка состояния головки: готовится,
## поиск, сопровождение, захват. Ставит CameraRig (_tick_osoka_view); состояние берёт у головки своего игрока.

const YELLOW := Color(1.0, 0.82, 0.25, 0.95)
const GREEN := Color(0.35, 1.0, 0.45, 1.0)
const GREY := Color(0.85, 0.85, 0.85, 0.75)

var player: Player
var cam: Camera3D
var state: int = OsokaSeeker.State.OFF
var screen: Vector2 = Vector2.ZERO
var on_screen: bool = false
var progress: float = 0.0
var _t: float = 0.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	_t += delta
	state = OsokaSeeker.State.OFF
	on_screen = false
	if player != null and is_instance_valid(player) and player.is_manpads() and cam != null and cam.current:
		var seeker: OsokaSeeker = player.osoka
		state = seeker.state
		progress = seeker.progress
		if seeker.target != null and is_instance_valid(seeker.target):
			var tp: Vector3 = seeker.target.call("heat_point") if seeker.target.has_method("heat_point") else seeker.target.global_position
			if not cam.is_position_behind(tp):
				screen = cam.unproject_position(tp)
				on_screen = true
	queue_redraw()


func _draw() -> void:
	if state == OsokaSeeker.State.OFF:
		return
	var font: Font = get_theme_default_font()
	var line: String = ""
	var col: Color = GREY
	match state:
		OsokaSeeker.State.WARMUP:
			line = "ГСН: готовится…"
		OsokaSeeker.State.SEARCH:
			line = "ГСН: поиск — поймай цель в кольцо мушки"
		OsokaSeeker.State.TRACK:
			line = "ГСН: сопровождение %d %%" % int(progress * 100.0)
			col = YELLOW
		OsokaSeeker.State.LOCK:
			line = "ЗАХВАТ — ЛКМ пуск"
			col = GREEN
	var fs: int = 18
	var w: float = font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	var base := Vector2(size.x * 0.5 - w * 0.5, size.y * 0.78)
	draw_string(font, base + Vector2(1, 1), line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, Color(0, 0, 0, 0.6))
	draw_string(font, base, line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, col)
	if not on_screen or (state != OsokaSeeker.State.TRACK and state != OsokaSeeker.State.LOCK):
		return
	# шире кольца мушки на 80° поля зрения — мушка с точкой видна внутри метки
	var r: float = 46.0
	if state == OsokaSeeker.State.TRACK:
		# кольцо мерцает в такт писку, дуга — доля захвата
		var a: float = 0.55 + 0.45 * absf(sin(_t * PI * lerpf(3.0, 9.0, progress)))
		draw_arc(screen, r, 0.0, TAU, 48, Color(YELLOW, 0.35 * a), 1.5, true)
		draw_arc(screen, r, -PI * 0.5, -PI * 0.5 + TAU * progress, 48, Color(YELLOW, a), 3.0, true)
	else:
		draw_arc(screen, r, 0.0, TAU, 48, GREEN, 2.5, true)
		var c: float = r + 8.0
		for s: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			var corner: Vector2 = screen + s * c
			draw_line(corner, corner - Vector2(s.x * 9.0, 0.0), GREEN, 2.5, true)
			draw_line(corner, corner - Vector2(0.0, s.y * 9.0), GREEN, 2.5, true)
