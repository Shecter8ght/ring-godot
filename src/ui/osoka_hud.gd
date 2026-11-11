class_name OsokaHud
extends Control
## Метка цели ПЗРК «Осока» на экране (владелец, docs/design/mission_helicopter.md: «удержание цели несколько секунд,
## метка зеленеет, пуск»). Головка ведёт цель — кольцо вокруг неё: жёлтое, дуга по кругу показывает долю захвата;
## захват — кольцо зелёное с уголками, подпись «ЗАХВАТ — ЛКМ пуск». Внизу — строка состояния головки: готовится,
## поиск, сопровождение, захват. Ставит CameraRig (_tick_osoka_view); состояние берёт у головки своего игрока.
## С тепловизором ПН-36Т «ПОЛЫНЬ» и взглядом в окуляр (CameraRig._update_display даёт display_rect) метки на экране
## игры нет — знаки рисуются на экране прицела (задание владельца 2026-11-06: «рамка захвата, дальность»; «сетка /
## интерфейс одинаковые в обоих режимах с поправкой на контрастность»): кольцо поля головки с рисками и точкой,
## рамка цели (сопровождение — уголки мигают в такт писку, под рамкой полоса доли захвата; захват — рамка целиком),
## дальность до цели, канал и состояние головки. Знаки одни и те же: в тепловом канале светлые с тёмной обводкой, в
## дневном при свете — тёмные со светлой (на светлом небе белое не читается), в дневном в темноте — снова светлые.

const YELLOW := Color(1.0, 0.82, 0.25, 0.95)
const GREEN := Color(0.35, 1.0, 0.45, 1.0)
const GREY := Color(0.85, 0.85, 0.85, 0.75)

var player: Player
var cam: Camera3D
var state: int = OsokaSeeker.State.OFF
var screen: Vector2 = Vector2.ZERO
var on_screen: bool = false
var progress: float = 0.0
## Экран тепловизора на экране игры (пусто — в окуляр не смотрят); его камера, размер её картинки, тангенс половины
## поля зрения по горизонтали, канал и «экран гаснет» при переключении — ставит CameraRig каждый кадр.
var display_rect: Rect2 = Rect2()
var scope_cam: Camera3D
var scope_px: Vector2 = Vector2.ONE
var display_tan_h: float = 0.2
var display_thermal: bool = true
## Знаки светлые (тепловой канал; дневной в темноте) или тёмные (дневной при свете) — ставит CameraRig.
var display_light_ink: bool = true
var display_blank: bool = false
var _t: float = 0.0
var _disp_pos: Vector2 = Vector2.ZERO
var _disp_on: bool = false
var _range_m: float = -1.0


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _process(delta: float) -> void:
	_t += delta
	state = OsokaSeeker.State.OFF
	on_screen = false
	_disp_on = false
	_range_m = -1.0
	if player != null and is_instance_valid(player) and player.is_manpads() and cam != null and cam.current:
		var seeker: OsokaSeeker = player.osoka
		state = seeker.state
		progress = seeker.progress
		if seeker.target != null and is_instance_valid(seeker.target):
			var tp: Vector3 = seeker.target.call("heat_point") if seeker.target.has_method("heat_point") else seeker.target.global_position
			if not cam.is_position_behind(tp):
				screen = cam.unproject_position(tp)
				on_screen = true
			_range_m = player.eye_position().distance_to(tp)
			if in_display() and scope_cam != null and is_instance_valid(scope_cam) and not scope_cam.is_position_behind(tp):
				var uv: Vector2 = scope_cam.unproject_position(tp) / scope_px
				_disp_pos = display_rect.position + uv * display_rect.size
				_disp_on = uv.x >= 0.0 and uv.x <= 1.0 and uv.y >= 0.0 and uv.y <= 1.0
	queue_redraw()


## Смотрят в окуляр тепловизора: знаки — на его экране.
func in_display() -> bool:
	return display_rect.size.x > 1.0


func _draw() -> void:
	if in_display():
		if player != null and is_instance_valid(player) and player.is_manpads():
			_draw_display()
		return
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


# ---------------------------------------------------------------- экран тепловизора

## Знаки экрана ПН-36Т: одни и те же в обоих каналах, цвет — по контрасту картинки (тепловой и дневной в темноте — светлые,
## дневной при свете — тёмные).
func _draw_display() -> void:
	if display_blank:
		return
	var d: Rect2 = display_rect
	var ink: Color = Color(0.94, 0.94, 0.92) if display_light_ink else Color(0.05, 0.05, 0.05)
	var halo: Color = Color(0.0, 0.0, 0.0, 0.55) if display_light_ink else Color(1.0, 1.0, 1.0, 0.5)
	var px: float = d.size.x / 320.0          # «точка» экрана — по ширине матрицы
	var w: float = maxf(1.5, px * 0.9)
	var center: Vector2 = d.get_center()
	var font: Font = get_theme_default_font()
	var fs: int = clampi(int(d.size.y * 0.042), 11, 30)
	# кольцо поля зрения головки (cone_deg) с рисками по четырём сторонам и точка в центре
	var rc: float = d.size.x * 0.5 * tan(deg_to_rad(float(Balance.OSOKA.cone_deg))) / display_tan_h
	_ring(center, rc, w, ink, halo)
	for s: Vector2 in [Vector2.RIGHT, Vector2.LEFT, Vector2.UP, Vector2.DOWN]:
		_line(center + s * rc * 1.35, center + s * rc * 2.6, w, ink, halo)
	_dot(center, w * 1.1, ink, halo)
	# канал, состояние головки — по углам экрана
	var pad: Vector2 = Vector2(px * 10.0, px * 8.0)
	_text(font, d.position + pad + Vector2(0, fs), "ТЕПЛО" if display_thermal else "ДЕНЬ", fs, ink, halo)
	var line: String = ""
	match state:
		OsokaSeeker.State.WARMUP:
			line = "ГСН ГОТОВ…"
		OsokaSeeker.State.SEARCH:
			line = "ПОИСК"
		OsokaSeeker.State.TRACK:
			line = "СОПР %d %%" % int(progress * 100.0)
		OsokaSeeker.State.LOCK:
			line = "ЗАХВАТ"
	if line != "":
		var lw: float = font.get_string_size(line, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
		_text(font, Vector2(center.x - lw * 0.5, d.end.y - pad.y), line, fs, ink, halo)
	# дальность до цели головки — в правом верхнем углу, пока цель есть
	var rng: String = "Д ----" if _range_m < 0.0 else "Д %d м" % int(roundf(_range_m / 10.0) * 10.0)
	var rw: float = font.get_string_size(rng, HORIZONTAL_ALIGNMENT_LEFT, -1, fs).x
	_text(font, Vector2(d.end.x - pad.x - rw, d.position.y + pad.y + fs), rng, fs, ink, halo)
	if not _disp_on or (state != OsokaSeeker.State.TRACK and state != OsokaSeeker.State.LOCK):
		return
	# рамка цели: сопровождение — уголки мигают в такт писку, под рамкой — полоса доли захвата; захват — рамка целиком
	var h: float = maxf(px * 14.0, rc * 0.55)
	var p: Vector2 = _disp_pos
	if state == OsokaSeeker.State.TRACK:
		var blink: bool = fmod(_t * lerpf(3.0, 9.0, progress), 1.0) < 0.62
		if blink:
			var arm: float = h * 0.45
			for s2: Vector2 in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
				var corner: Vector2 = p + s2 * h
				_line(corner, corner - Vector2(s2.x * arm, 0.0), w, ink, halo)
				_line(corner, corner - Vector2(0.0, s2.y * arm), w, ink, halo)
		var bar_y: float = p.y + h + px * 5.0
		_line(Vector2(p.x - h, bar_y), Vector2(p.x + h, bar_y), w * 0.6, Color(ink, 0.45), halo)
		_line(Vector2(p.x - h, bar_y), Vector2(p.x - h + 2.0 * h * progress, bar_y), w * 1.6, ink, halo)
	else:
		var box := Rect2(p - Vector2(h, h), Vector2(h, h) * 2.0)
		draw_rect(box, halo, false, w * 1.4 + 2.0)
		draw_rect(box, ink, false, w * 1.4)
		_dot(p, w * 1.2, ink, halo)


func _line(a: Vector2, b: Vector2, w: float, ink: Color, halo: Color) -> void:
	draw_line(a, b, halo, w + 2.0, true)
	draw_line(a, b, ink, w, true)


func _ring(c: Vector2, r: float, w: float, ink: Color, halo: Color) -> void:
	draw_arc(c, r, 0.0, TAU, 64, halo, w + 2.0, true)
	draw_arc(c, r, 0.0, TAU, 64, ink, w, true)


func _dot(c: Vector2, r: float, ink: Color, halo: Color) -> void:
	draw_circle(c, r + 1.0, halo)
	draw_circle(c, r, ink)


func _text(font: Font, at: Vector2, text: String, fs: int, ink: Color, halo: Color) -> void:
	draw_string_outline(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, 3, halo)
	draw_string(font, at, text, HORIZONTAL_ALIGNMENT_LEFT, -1, fs, ink)
