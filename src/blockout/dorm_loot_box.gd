@tool
extends Node3D
## Мебель общежития, которую обыскивают (партия 3: ящики под патроны и ЗИП, сундук, ящик для инструментов, чемодан,
## сумка, коробка — владелец 2026-11-02). Закрытая модель и, если у открытого своя (ящики, коробка), — открытая, скрытая
## до обыска. Обыск (LootContainer рядом, сигнал opened) или клавиша в стенде — open(): закрытая прячется, открытая
## показывается, крышка и створка (index movers с углом open) доводятся от закрытого положения до открытого.

const OPEN_SEC: float = 0.6

var closed: Node3D
## Своя модель открытого; null — открывается та же (лежащий чемодан: створка из позы «закрыто»).
var opened_model: Node3D
## Подвижное открытого: [{node, axis, rest (базис узла в открытом), from (угол закрытого, градусы)}].
var movers: Array[Dictionary] = []
var is_open: bool = false


## Открытое прячется, подвижное — в закрытое положение (у той же модели оно уже стоит позой из расстановки).
func setup(closed_node: Node3D, open_node: Node3D, info: Dictionary, pose: Dictionary) -> void:
	closed = closed_node
	opened_model = open_node
	var target: Node3D = open_node if open_node!=null else closed_node
	for mover: Dictionary in info.get("movers",[]):
		if not mover.has("open"):
			continue
		var part: Node3D = target.find_child(String(mover.node),true,false) as Node3D
		if part==null:
			continue
		var axis: Vector3 = Vector3(float(mover.axis[0]),float(mover.axis[1]),float(mover.axis[2])).normalized()
		var from: float = float(pose.get(String(mover.node),-float(mover.open)))
		var rest: Basis = part.basis
		if open_node==null:
			# поза «закрыто» уже применена расстановкой: открытый базис — обратно на её угол
			rest = Basis(axis,deg_to_rad(-from))*part.basis
		else:
			part.basis = Basis(axis,deg_to_rad(from))*rest
		movers.append({"node": part, "axis": axis, "rest": rest, "from": from})
	if open_node!=null:
		open_node.visible = false


func open() -> void:
	if is_open:
		return
	is_open = true
	if opened_model!=null:
		closed.visible = false
		opened_model.visible = true
	if movers.is_empty():
		return
	var tween: Tween = create_tween()
	tween.tween_method(_swing,0.0,1.0,OPEN_SEC).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT)


func _swing(t: float) -> void:
	for m: Dictionary in movers:
		var part: Node3D = m.node as Node3D
		part.basis = Basis(m.axis as Vector3,deg_to_rad(float(m.from)*(1.0-t)))*(m.rest as Basis)
