"""ПМ от первого лица, хват «в замок» по схеме владельца (docs/assets/pm_fps_grip_scheme.md, серии 1–3).

Руки — те же FPS_ArmsRig (руки владельца из библиотеки ВЕРАС‑54), ПМ — игровая сетка v11; сцена, риг пистолета и подгонка
пальцев по сетке перчатки — из tools/animate_pm_v11.py (импорт). Отличие от хвата v02: положение кисти на рукоятке не
задано числом, а находится касанием — кисть подводится к детали снаружи, пока сетка перчатки не ляжет на неё:
  перепонка (между большим и указательным) — под хвост рамки, ладонь — на правую щёчку, пятка ладони — на заднюю стенку;
  средний / безымянный / мизинец обхватывают рукоятку (средний упирается в скобу снизу, мизинец — на дне магазина);
  указательный: в изготовке — вытянут вдоль рамки над скобой, в прицеле — на спуске;
  левая накрывает пальцы правой снаружи, ладонь на левой щёчке, пальцы в ложбинках между пальцами правой;
  большие пальцы оба слева вдоль рамки: левый — вперёд под затворной задержкой, правый — на основании левого, под затвором.
Каждая поза проверяется: зазор сетки пальца до оружия, проникновение (лучи по чётности на замкнутых сетках), углы суставов.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/pm_grip_lock.py -- build|stills [carry|ready|ads]
  build  → _asset_src/pm_game/anim/PM_FPS_Grip_v03_calc.blend (действие PM_Stances: кадры 1 наискосок / 11 от бедра / 21 прицел;
           указательный ключами — вдоль рамки / на спуске), отчёт anim/grip_v03_report.json
  stills → anim/Кадры_v03/<стойка>_<вид>.png (из глаз, справа, слева, снизу, спереди); -- stills <файл.blend> — кадры чужого файла
  check <файл.blend> → проверка файла без изменений (зазоры, проникновения, суставы) → <файл>_check.json
  reload → от хвата владельца: позы левой по фазам перезарядки anim/PM_FPS_ReloadPoses_v01.blend (создать / прочитать правленные)
           и клипы anim/PM_FPS_Clips_v02.blend; poses_stills → кадры поз anim/Кадры_перезарядка_позы
Файлы владельца (PM_FPS_Grip_v02*.blend) не меняются.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import animate_pm_v11 as A  # noqa: E402  (режим build/stills — у него ничего не запускает)

MODE = A.MODE
STAGE = "right" if "right" in A.ARGS[1:] else "full"       # right — левая убрана, доводится хват правой (предложение владельца)
SUFFIX = "_right" if STAGE == "right" else "_calc"       # PM_FPS_Grip_v03.blend — правка владельца (15:24), сборка её не трогает
OUT = A.SRC / f"anim/PM_FPS_Grip_v03{SUFFIX}.blend"
REPORT = A.SRC / f"anim/grip_v03{SUFFIX}_report.json"
STILLS = A.SRC / f"anim/Кадры_v03{SUFFIX}"
OWNER_GRIP = A.SRC / "anim/PM_FPS_Grip_v03.blend"       # хват с пальцами владельца — база для клипов и поз перезарядки
# большой правой в одноручном хвате (серия 1, под левую не на что опереться): вдоль рамки под затворной задержкой
R_THUMB_SOLO_TIP = Vector((0.026, -0.042, 0.040))
R_THUMB_SOLO_MCP = Vector((0.029, 0.010, 0.036))
LEFT_AWAY = Vector((0.16, 0.02, -0.16))                     # куда убрать левую кисть (оси ПМ): влево‑вниз, вне хвата
GUN_PARTS = ("Frame_Mesh", "Grip_Mesh", "Slide_Mesh", "Part_Magazine", "Trigger_Mesh", "Hammer_Mesh", "SlideStop_Mesh",
             "Safety_Mesh", "MagCatch_Mesh")
CLEAR = 0.0012                                   # «касание»: сетка перчатки в 1,2 мм от детали
STEP = 0.0005
log = lambda *a: print("PM_LOCK", *a, flush=True)

# Точки в осях ПМ (м): +X — левая сторона стрелка, −Y — дуло, +Z — вверх; начало — рукоятка (замеры probe_pm2:
# щёчки x ±14.5…16, передняя стенка y −18 (низ) … −38 (под скобой), задняя y +28 (низ) … +15 (z 20–30), хвост рамки
# y 21–30 / z 35–47, низ скобы z 10–15 при y −40…−32, затвор z ≥ 47.3, x ±13.5, задержка x 10.7–16, y −38…−24, z 40–46).
LEFT_MCP = Vector((0.030, -0.046, -0.004))      # костяшка среднего левой: у левого переднего угла пальцев правой, между её средним и безымянным
LEFT_FINGERS = Vector((-0.40, -0.60, -0.45))    # кисть левой от запястья к костяшкам: вперёд‑вправо‑вниз (запястье согнуто вниз, кисть наклонена вперёд)
LEFT_PALM = Vector((-0.88, 0.40, 0.25))          # ладонь левой смотрит вправо на левую щёчку, чуть назад и вверх — на пальцы правой
L_THUMB_MCP = Vector((0.030, 0.004, 0.026))     # большой левой: сустав у щёчки под большим правой…
R_THUMB_MCP = Vector((0.030, 0.012, 0.034))     # большой правой в замке: сустав у хвоста рамки, над основанием левого
L_THUMB_TIP = Vector((0.021, -0.066, 0.035))    # …кончик вперёд вдоль полосы рамки под затвором, до переда скобы (серия 4)
R_THUMB_TIP = Vector((0.031, -0.026, 0.042))    # большой правой: на основании левого большого, сбоку от затвора (x > 13.5 + перчатка)
WEB_BONES = ["hand.R", "palm.01.R", "thumb.01.R", "f_index.01.R"]
PALM_BONES = ["hand.R", "palm.01.R", "palm.02.R", "palm.03.R", "palm.04.R"]


# ================================================================ поверхности деталей по условию (в осях ПМ)

def faces_where(objects, cond) -> BVHTree:
    """BVH из граней деталей, все вершины которых удовлетворяют условию в осях ПМ (Frame)."""
    arms = bpy.data.objects["FPS_ArmsRig"]
    inv = A.world(arms, "Frame").inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objects:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(verts)
        co = [ev.matrix_world @ v.co for v in me.vertices]
        local = [inv @ c for c in co]
        verts += co
        polys += [[base + i for i in p.vertices] for p in me.polygons if all(cond(local[i]) for i in p.vertices)]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def approach(arms, skin: A.Skin, bones: list, tree: BVHTree, direction: Vector, start: float, limit: float) -> float:
    """Подвести правую кисть к детали: отвести на start (м) против direction (в осях ПМ), затем идти по direction шагами,
    пока сетка перчатки (кости bones) не окажется в CLEAR от детали. Возвращает пройденный путь (м)."""
    frame = A.world(arms, "Frame")
    d_world = (frame.to_3x3() @ direction).normalized()
    h = A.world(arms, "ik_hand.R")
    h.translation -= d_world * start
    A.set_world(arms, "ik_hand.R", h)
    moved = -start
    while moved < limit:
        if skin.gap(tree, bones) <= CLEAR:
            break
        h.translation += d_world * STEP
        A.set_world(arms, "ik_hand.R", h)
        moved += STEP
    return moved


def approach_left(arms, skin: A.Skin, tree: BVHTree, direction: Vector, start: float, limit: float) -> float:
    frame = A.world(arms, "Frame")
    d_world = (frame.to_3x3() @ direction).normalized()
    h = A.world(arms, "ik_hand.L")
    h.translation -= d_world * start
    A.set_world(arms, "ik_hand.L", h)
    moved = -start
    bones = ["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L"] + [f"{f}.01.L" for f in A.FINGERS]
    while moved < limit:
        if skin.gap(tree, bones) <= CLEAR:
            break
        h.translation += d_world * STEP
        A.set_world(arms, "ik_hand.L", h)
        moved += STEP
    return moved


# ================================================================ большой палец шарнирами

THUMB_RANGE = {2: (-10.0, 60.0), 3: (-15.0, 80.0)}        # пределы сгиба средней и ногтевой фаланг большого (градусы)


def hinge_reach(arms, hands: A.Hands, chain: list, target: Vector, iters: int = 60, free_base: bool = True,
                ranges: dict | None = None, free: tuple = (1,)) -> None:
    """Довести кончик цепочки до точки: средняя и ногтевая фаланги — только сгиб вокруг оси сустава (ось хвата владельца),
    основание (пясть) — свободный поворот малыми шагами. Так сустав не выворачивается, как при свободном CCD."""
    inv = arms.matrix_world.inverted()

    def tip() -> Vector:
        return arms.matrix_world @ arms.pose.bones[chain[-1]].tail

    for _ in range(iters):
        for k in reversed(range(len(chain))):
            n = chain[k]
            pb = arms.pose.bones[n]
            idx = int(n.split(".")[1])
            if idx in free and free_base:
                head = arms.matrix_world @ pb.head
                a, b = tip() - head, target - head
                if a.length < 1e-6 or b.length < 1e-6:
                    continue
                q = a.rotation_difference(b)
                if q.angle < 1e-4:
                    continue
                q = Quaternion(q.axis, min(q.angle, math.radians(6.0)))
                m = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
                pb.matrix = inv @ m @ arms.matrix_world @ pb.matrix
                bpy.context.view_layer.update()
                # сустав пясти не крутится вокруг своей оси: убираем twist (вокруг локальной Y) из позы
                ql = pb.rotation_quaternion.copy()
                twist = Quaternion((ql.w, 0.0, ql.y, 0.0)).normalized()
                pb.rotation_quaternion = (ql @ twist.inverted()).normalized()
                bpy.context.view_layer.update()
                continue
            axis, _ = hands.axis[n]
            lo, hi = (ranges or THUMB_RANGE).get(idx, (-20.0, 90.0))
            cur = pb.rotation_quaternion.copy()
            best, best_d = None, (tip() - target).length
            for step in (-6.0, -3.0, -1.0, 1.0, 3.0, 6.0):
                cand = cur @ Quaternion(axis, math.radians(step))
                proj = Vector((cand.x, cand.y, cand.z)).dot(axis)
                flex = math.degrees(2.0 * math.atan2(proj, cand.w))
                if not lo <= flex <= hi:
                    continue
                pb.rotation_quaternion = cand
                bpy.context.view_layer.update()
                d = (tip() - target).length
                if d < best_d - 1e-6:
                    best, best_d = cand, d
            pb.rotation_quaternion = best if best is not None else cur
            bpy.context.view_layer.update()
        if (tip() - target).length < 0.0012:
            break


def thumb_hinge_to(arms, hands: A.Hands, skin: A.Skin, tree: BVHTree, frame_w: Matrix, pose: dict, side: str, tip: Vector,
                   knuckle: Vector | None = None, solids: list | None = None) -> dict:
    """Большой палец кончиком в точку (оси ПМ): пясть и средняя фаланга — свободные суставы без скручивания,
    ногтевая — шарнир. Если задан сустав — сначала пясть концом в него. Палец внутри детали (замкнутые оболочки
    solids) — точки уходят наружу (+X ПМ) по 1 мм; касание не считается проникновением."""
    names = [f"thumb.{i:02d}.{side}" for i in (1, 2, 3)]
    tip, knuckle = tip.copy(), knuckle.copy() if knuckle is not None else None
    for _ in range(14):
        if knuckle is not None:
            A.reach_tip(arms, names[:1], frame_w @ knuckle)
            hinge_reach(arms, hands, names, frame_w @ tip, free=(2,))
        else:
            hinge_reach(arms, hands, names, frame_w @ tip, free=(1, 2))
        if not solids:
            if skin.gap(tree, names[1:]) > CLEAR:
                break
        else:
            dg = bpy.context.evaluated_depsgraph_get()
            ev = skin.ob.evaluated_get(dg)
            me = ev.to_mesh()
            mw = ev.matrix_world
            pts = [mw @ me.vertices[i].co for n in names[1:] for i in skin.verts.get(n, ())]
            ev.to_mesh_clear()
            deep = max((depth_inside(t, p) for _n, t in solids for p in pts), default=0.0)
            if deep < 0.0015:                       # вдавливание перчатки до 1,5 мм — не проникновение
                break
        tip.x += 0.001
        if knuckle is not None:
            knuckle.x += 0.001
    for n in names:
        pose[n] = arms.pose.bones[n].rotation_quaternion.copy()
    return pose


# ================================================================ посадка кисти перебором (жёсткое тело)

import bmesh  # noqa: E402


def hull_tree(objects, cond) -> BVHTree:
    """Замкнутая выпуклая оболочка вершин деталей по условию (в осях ПМ) — для проверки «точка внутри»."""
    arms = bpy.data.objects["FPS_ArmsRig"]
    inv = A.world(arms, "Frame").inverted()
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objects:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        for v in me.vertices:
            w = ev.matrix_world @ v.co
            if cond(inv @ w):
                pts.append(w)
        ev.to_mesh_clear()
    bm = bmesh.new()
    for w in pts:
        bm.verts.new(w)
    bm.verts.ensure_lookup_table()
    bmesh.ops.convex_hull(bm, input=bm.verts)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


RAYS = (Vector((0.37, 0.61, 0.70)).normalized(), Vector((-0.71, 0.21, 0.67)).normalized(), Vector((0.2, -0.9, 0.35)).normalized())


def depth_inside(tree: BVHTree, p: Vector) -> float:
    """Глубина точки внутри замкнутой оболочки (0 — снаружи): чётность трёх лучей, большинство."""
    votes = 0
    for d in RAYS:
        c, origin = 0, p.copy()
        for _ in range(32):
            loc, _n, _i, _d = tree.ray_cast(origin, d)
            if loc is None:
                break
            c += 1
            origin = loc + d * 1e-5
        votes += c % 2
    if votes < 2:
        return 0.0
    _loc, _n, _i, dist = tree.find_nearest(p)
    return dist or 0.0


class Placer:
    """Кисть как жёсткое тело: вершины перчатки (кисть, ладонь, основания пальцев) берутся один раз в осях кости hand,
    кандидаты посадки оцениваются переносом точек — без пересчёта сетки. Штраф: глубина проникновения в замкнутые
    оболочки деталей; награда: касание заданных групп вершин заданных поверхностей."""

    def __init__(self, arms, skin: A.Skin, side: str, bones: list) -> None:
        self.arms, self.side = arms, side
        hand_w = A.world(arms, f"hand.{side}")
        inv = hand_w.inverted()
        dg = bpy.context.evaluated_depsgraph_get()
        ev = skin.ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        self.pts = {}
        for n in bones:
            self.pts[n] = [inv @ (mw @ me.vertices[i].co) for i in skin.verts.get(n, ())]
        ev.to_mesh_clear()
        self.solids: list = []          # (имя, BVH замкнутый)
        self.contacts: list = []        # (имя, список точек в осях кисти, BVH поверхности, вес)

    def local(self, bones: list, cond=None) -> list:
        out = []
        for n in bones:
            out += [p for p in self.pts.get(n, ()) if cond is None or cond(p)]
        return out

    def score(self, H: Matrix) -> tuple:
        pen = 0.0
        for _name, tree in self.solids:
            for n, pts in self.pts.items():
                for p in pts:
                    pen += depth_inside(tree, H @ p)
        touch = 0.0
        detail = {}
        for name, pts, tree, w in self.contacts:
            best = 1e9
            for p in pts:
                _l, _n, _i, d = tree.find_nearest(H @ p)
                if d is not None and d < best:
                    best = d
            detail[name] = round(best * 1000, 2)
            touch += w * max(0.0, best - CLEAR)
        return pen * 1000.0 * 25.0 + touch * 1000.0, pen * 1000.0, detail

    def solve(self, H0: Matrix, pivot_local: Vector, rot_penalty: float = 0.4, log_name: str = "",
              schedule: tuple = ((0.004, 4.0), (0.002, 2.0), (0.001, 1.0), (0.0005, 0.5))) -> Matrix:
        """Координатный спуск: сдвиги по осям ПМ и повороты вокруг точки pivot (в осях кисти), шаг убывает."""
        H = H0.copy()
        arms = self.arms
        frame_w = A.world(arms, "Frame")
        axes = [frame_w.to_3x3() @ Vector(a) for a in ((1, 0, 0), (0, 1, 0), (0, 0, 1))]

        def total(Hc: Matrix) -> tuple:
            sc, pn, dt = self.score(Hc)
            ang = math.degrees((H0.to_3x3().inverted() @ Hc.to_3x3()).to_quaternion().angle)
            return sc + rot_penalty * ang, pn, dt

        best, pen, det = total(H)
        for step_t, step_r in schedule:
            improved = True
            rounds = 0
            while improved and rounds < 12:
                improved = False
                rounds += 1
                for ax in axes:
                    for sgn in (1.0, -1.0):
                        Hc = H.copy()
                        Hc.translation += ax * step_t * sgn
                        sc, pn, dt = total(Hc)
                        if sc < best - 1e-6:
                            H, best, pen, det, improved = Hc, sc, pn, dt, True
                for ax in axes:
                    for sgn in (1.0, -1.0):
                        pv = H @ pivot_local
                        R = Matrix.Rotation(math.radians(step_r * sgn), 4, ax)
                        Hc = Matrix.Translation(pv) @ R @ Matrix.Translation(-pv) @ H
                        sc, pn, dt = total(Hc)
                        if sc < best - 1e-6:
                            H, best, pen, det, improved = Hc, sc, pn, dt, True
            log(log_name, f"шаг {step_t*1000:.1f} мм / {step_r}°: счёт {best:.1f}, проникновение {pen:.2f} мм, касания", det)
        return H


def set_hand(arms, side: str, H: Matrix) -> None:
    """Поставить кисть в мировую матрицу H (ручка ik_hand совпадает с кистью: Copy Rotation + IK)."""
    A.set_world(arms, f"ik_hand.{side}", H)
    bpy.context.view_layer.update()


def index_along_frame(arms, hands: A.Hands, skin: A.Skin, pose: dict, band: BVHTree, frame_w: Matrix) -> dict:
    """Указательный правой вытянут вдоль рамки над скобой (серии 1, 4): фаланги почти прямые; у основания палец
    сначала выравнивается параллельно затвору (чуть вверх), затем подводится к боку рамки / затвора до касания."""
    out = dict(pose)
    for k in (2, 3):
        out[f"f_index.{k:02d}.R"] = hands.scaled(f"f_index.{k:02d}.R", 0.12)
    out["f_index.01.R"] = hands.scaled("f_index.01.R", 0.0)
    A.apply(arms, out)
    pb = arms.pose.bones["f_index.01.R"]
    inv = arms.matrix_world.inverted()
    gun_inv = frame_w.inverted()
    ax_x = (frame_w.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()
    ax_z = (frame_w.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()

    def direction() -> Vector:
        a = gun_inv @ (arms.matrix_world @ pb.head)
        b = gun_inv @ (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail)
        return (b - a).normalized()

    def turn(axis_w: Vector, deg: float) -> None:
        head = arms.matrix_world @ pb.head
        m = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, axis_w) @ Matrix.Translation(-head)
        pb.matrix = inv @ m @ arms.matrix_world @ pb.matrix
        bpy.context.view_layer.update()

    # 1) параллельно затвору, кончик чуть выше основания (+3°)
    want = math.radians(3.0)
    for _ in range(40):
        d = direction()
        pitch = math.atan2(d.z, -d.y)
        if abs(pitch - want) < math.radians(0.5):
            break
        turn(ax_x, -1.0 if pitch < want else 1.0)
        if abs(math.atan2(direction().z, -direction().y) - want) > abs(pitch - want):
            turn(ax_x, 2.0 if pitch < want else -2.0)       # знак оси оказался обратным — шаг в другую сторону
    # 2) к боку рамки, пока сетка пальца не коснётся полосы рамки или затвора
    total = 0.0
    while total < 25.0 and skin.gap(band, ["f_index.02.R", "f_index.03.R"]) > CLEAR:
        x0 = (gun_inv @ (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail)).x
        turn(ax_z, 1.0)
        if (gun_inv @ (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail)).x < x0:
            turn(ax_z, -2.0)                                 # кончик должен идти к пистолету (+X)
        total += 1.0
    for n in ("f_index.01.R", "f_index.02.R", "f_index.03.R"):
        out[n] = arms.pose.bones[n].rotation_quaternion.copy()
    return out



TRIGGER_TIP = Vector((0.007, -0.061, 0.025))     # кончик указательного (конец ногтевой фаланги): чуть левее крючка, нижняя половина
INDEX_RANGE = {2: (0.0, 110.0), 3: (0.0, 80.0)}


def index_on_trigger(arms, hands: A.Hands, skin: A.Skin, pose: dict, frame_w: Matrix, trigger: BVHTree) -> dict:
    """Указательный правой на спуске (серии 2–4): входит в скобу справа, средняя фаланга согнута, подушечка ногтевой
    по центру крючка в его нижней половине. Основание — свободный сустав без скручивания, остальные — шарниры."""
    out = dict(pose)
    out["f_index.01.R"] = hands.scaled("f_index.01.R", 0.35)
    out["f_index.02.R"] = hands.scaled("f_index.02.R", 0.5)
    out["f_index.03.R"] = hands.scaled("f_index.03.R", 0.15)
    A.apply(arms, out)
    chain = ["f_index.01.R", "f_index.02.R", "f_index.03.R"]
    hinge_reach(arms, hands, chain, frame_w @ TRIGGER_TIP, iters=80, ranges=INDEX_RANGE)
    for n in chain:
        out[n] = arms.pose.bones[n].rotation_quaternion.copy()
    tip = frame_w.inverted() @ (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail)
    log("указательный на спуске: кончик (мм)", [round(c * 1000, 1) for c in tip], "зазор до крючка",
        round(skin.gap(trigger, ["f_index.03.R"]) * 1000, 1))
    return out



def fit_hand_to_landmarks(arms, side: str, frame_w: Matrix, targets: dict) -> Matrix:
    """Мировая матрица кисти, при которой её опорные точки (голова hand = запястье, костяшки указательного и мизинца)
    ближе всего к целям (оси ПМ): жёсткая посадка по трём точкам (Кабш). Возвращает матрицу для set_hand."""
    import numpy as np
    hand_w = A.world(arms, f"hand.{side}")
    inv = hand_w.inverted()
    names = {"wrist": f"hand.{side}", "index": f"f_index.01.{side}", "pinky": f"f_pinky.01.{side}"}
    P = np.array([list(inv @ (arms.matrix_world @ arms.pose.bones[names[k]].head)) for k in ("wrist", "index", "pinky")])
    Q = np.array([list(frame_w @ targets[k]) for k in ("wrist", "index", "pinky")])
    pc, qc = P.mean(axis=0), Q.mean(axis=0)
    Hm = (P - pc).T @ (Q - qc)
    U, _S, Vt = np.linalg.svd(Hm)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    t = qc - R @ pc
    M = Matrix(((R[0, 0], R[0, 1], R[0, 2], t[0]), (R[1, 0], R[1, 1], R[1, 2], t[1]), (R[2, 0], R[2, 1], R[2, 2], t[2]), (0, 0, 0, 1)))
    H = M                                                   # точки P — в осях кисти, цели — в мире: M и есть новая матрица кисти
    err = {k: round(float(np.linalg.norm(np.array(list(M @ Vector(P[i]))) - Q[i])) * 1000, 1)
           for i, k in enumerate(("wrist", "index", "pinky"))}
    log(f"посадка {side} по точкам, невязка (мм)", err)
    return H


# опорные точки левой в осях ПМ (м): костяшка указательного — у переднего низа скобы снаружи среднего пальца правой,
# костяшка мизинца — у низа рукоятки снаружи мизинца правой, запястье — снизу‑слева‑сзади (предплечье приходит снизу)
LEFT_LANDMARKS = {"index": Vector((0.030, -0.050, 0.004)), "pinky": Vector((0.036, -0.028, -0.044)),
                  "wrist": Vector((0.076, 0.012, -0.061))}

# ================================================================ проверки

def closed(ob) -> bool:
    me = ob.data
    edges = {}
    for p in me.polygons:
        for e in p.edge_keys:
            edges[e] = edges.get(e, 0) + 1
    return all(n == 2 for n in edges.values())


def inside_count(skin: A.Skin, bones: list, objects) -> dict:
    """Наибольшая глубина (мм) вершин перчатки каждой кости внутри замкнутых деталей (лучи по чётности, две оси)."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = skin.ob.evaluated_get(dg)
    me = ev.to_mesh()
    mw = ev.matrix_world
    pts = [(n, mw @ me.vertices[i].co) for n in bones for i in skin.verts.get(n, ())]
    ev.to_mesh_clear()
    out = {}
    for o in objects:
        if not closed(o):
            continue
        tree = A.bvh_of([o])
        n = {}
        for bone, p in pts:
            hits = []
            for d in (Vector((0.37, 0.61, 0.70)), Vector((-0.71, 0.21, 0.67))):
                c, origin = 0, p.copy()
                for _ in range(64):
                    loc, _nrm, _idx, _dist = tree.ray_cast(origin, d)
                    if loc is None:
                        break
                    c += 1
                    origin = loc + d * 1e-5
                hits.append(c % 2)
            if sum(hits) == 2:
                _l, _nn, _i, dist = tree.find_nearest(p)
                n[bone] = max(n.get(bone, 0.0), round((dist or 0.0) * 1000, 1))
        if n:
            out[o.name] = n
    return out


# пределы суставов (градусы): сгиб (основание, средний, ногтевой) и отклонение оси сгиба от оси хвата владельца
FLEX_LIMIT = {"f": (95.0, 115.0, 90.0), "t": (70.0, 70.0, 95.0)}


def joint_report(arms, hands: A.Hands, side: str) -> dict:
    """Углы суставов пальцев относительно покоя: сгиб вокруг оси хвата владельца и остаток (разворот/отведение)."""
    out = {}
    for finger in A.FINGERS + ("thumb",):
        for i in (1, 2, 3):
            n = f"{finger}.{i:02d}.{side}"
            q = arms.pose.bones[n].rotation_quaternion
            axis, _ = hands.axis[n]
            # разложение swing/twist вокруг оси сгиба: проекция вектора кватерниона на ось
            proj = Vector((q.x, q.y, q.z)).dot(axis)
            flex = Quaternion((q.w, *(axis * proj))).normalized()
            rest = (flex.inverted() @ q).normalized()
            flex_deg = math.degrees(2.0 * math.atan2(proj, q.w))
            if flex_deg > 180.0:
                flex_deg -= 360.0
            lim = FLEX_LIMIT["t" if finger == "thumb" else "f"][i - 1]
            flags = []
            if flex_deg > lim + 1e-3:
                flags.append("сгиб выше предела")
            if flex_deg < -25.0:
                flags.append("переразгиб")
            if math.degrees(rest.angle) > (60.0 if (finger == "thumb" and i == 1) else 30.0):
                flags.append("выворот")
            out[n] = {"flex_deg": round(flex_deg, 1), "off_axis_deg": round(math.degrees(rest.angle), 1), "flags": flags}
    return out


# ================================================================ сборка

def both_hands(arms, hands, skin, gun, frame_w, open_r, r_rest, r_fire, F, G, solids) -> tuple:
    """Стадия «обе руки»: левая замком и большой правой на основании левого большого. Хват правой не меняется."""
    # левая: пальцы поперёк пальцев правой (справа‑налево спереди), ладонь к левой щёчке; посадка перебором
    A.apply(arms, hands.pose("L", 0.25, thumb=0.2))
    l_open = hands.pose("L", 0.25, thumb=0.2)
    set_hand(arms, "L", fit_hand_to_landmarks(arms, "L", frame_w, LEFT_LANDMARKS))
    right_glove = A.surface([(bpy.data.objects["FPS_Arms"], "R")])
    left_panel = faces_where([F, G], lambda p: p.x > 0.006 and p.z < 0.040 and p.y > -0.034)
    pl = Placer(arms, skin, "L", ["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L", "thumb.01.L",
                                  "f_index.01.L", "f_middle.01.L", "f_ring.01.L", "f_pinky.01.L"])
    pl.solids = solids
    hand_inv_l = A.world(arms, "hand.L").inverted()
    lpalm_pts = pl.local(["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L"], lambda p: p.x > 0.004)
    lfing_pts = pl.local(["f_index.01.L", "f_middle.01.L", "f_ring.01.L", "f_pinky.01.L"])
    pl.contacts = [("palm→left panel", lpalm_pts, left_panel, 2.0), ("fingers→right hand", lfing_pts, right_glove, 1.0),
                   ("palm→right hand", lpalm_pts, right_glove, 0.5)]
    H0l = A.world(arms, "hand.L")
    Hl = pl.solve(H0l, hand_inv_l @ A.world(arms, "f_middle.01.L").translation, rot_penalty=3.0, log_name="левая",
                  schedule=((0.002, 2.0), (0.001, 1.0), (0.0005, 0.5)))
    set_hand(arms, "L", Hl)
    report_left = {"shift_mm": [round(c * 1000, 1) for c in (frame_w.inverted() @ Hl).translation - (frame_w.inverted() @ H0l).translation]}
    log("левая: сдвиг перебором (мм)", report_left["shift_mm"])
    tree_l = A.surface([(o, "") for o in gun] + [(bpy.data.objects["FPS_Arms"], "R")])
    l_full = hands.pose("L", 1.0, thumb=1.0)
    A.apply(arms, {n: l_open[n] for n in l_open if n.startswith("thumb")})
    l_pose = thumb_hinge_to(arms, hands, skin, tree_l, frame_w, l_full, "L", L_THUMB_TIP, L_THUMB_MCP, solids=solids)
    l_pose = A.wrap(arms, hands, skin, l_pose, "L", tree_l, start=(0.25, 0.2, 0.2), clear=CLEAR)
    l_in_gun = frame_w.inverted() @ A.world(arms, "ik_hand.L")

    # ---- большой правой — на основании левого большого, сбоку от затвора
    tree_lt = A.surface([(o, "") for o in gun] + [(bpy.data.objects["FPS_Arms"], "L")])
    A.apply(arms, {n: open_r[n] for n in open_r if n.startswith("thumb")})
    r_rest = thumb_hinge_to(arms, hands, skin, tree_lt, frame_w, r_rest, "R", R_THUMB_TIP, R_THUMB_MCP, solids=solids)
    for n in ("thumb.01.R", "thumb.02.R", "thumb.03.R"):
        r_fire[n] = r_rest[n]

    return l_pose, l_in_gun, tree_l, tree_lt, r_rest, r_fire


def build() -> None:
    scene, arms = A.append_scene()
    bpy.context.view_layer.update()
    rear_sight = bpy.data.objects["SightRear"].matrix_world.translation.copy()
    ready = A.read_ready(scene, arms)
    rig = A.build_rig(scene, arms, ready)
    hand_of_gun = rig["grip"].inverted()
    for name in ("Suppressor_Mesh",):
        bpy.data.objects[name].hide_viewport = bpy.data.objects[name].hide_render = True
    hands = A.Hands(arms, ready)
    hands.place(arms)
    skin = A.Skin(bpy.data.objects["FPS_Arms"])
    gun = [bpy.data.objects[n] for n in GUN_PARTS if n in bpy.data.objects]
    report: dict = {"closed": {o.name: closed(o) for o in gun}}

    # пистолет — главный, стойка «от бедра» для подгонки
    A.regrip_rig(arms)
    all_stances = A.stances(rear_sight)
    g = all_stances["READY"]
    A.set_world(arms, "Frame", g)
    A.set_world(arms, "ik_hand.R", g @ hand_of_gun)
    hands.place(arms)
    frame_w = A.world(arms, "Frame")
    F = bpy.data.objects["Frame_Mesh"]
    G = bpy.data.objects["Grip_Mesh"]
    SL = bpy.data.objects["Slide_Mesh"]

    # ---- правая: пальцы полураскрыты, кисть — жёсткое тело, посадка перебором
    open_r = hands.pose("R", 0.55, thumb=0.2)
    open_r["f_index.01.R"] = hands.scaled("f_index.01.R", 0.0)
    open_r["f_index.02.R"] = hands.scaled("f_index.02.R", 0.1)
    open_r["f_index.03.R"] = hands.scaled("f_index.03.R", 0.1)
    A.apply(arms, open_r)
    tang = faces_where([F], lambda p: p.y > 0.012 and 0.028 < p.z < 0.047)
    right_panel = faces_where([F, G], lambda p: p.x < -0.006 and p.z < 0.040 and p.y > -0.030)
    backstrap = faces_where([F, G], lambda p: p.y > 0.013 and p.z < 0.038 and abs(p.x) < 0.013)
    solids = [("grip", A.bvh_of([G])),
              ("tang", hull_tree([F], lambda p: p.y > 0.010 and 0.026 < p.z < 0.0475)),
              ("front_strap", hull_tree([F], lambda p: -0.042 < p.y < -0.012 and -0.048 < p.z < 0.036)),
              ("back_frame", hull_tree([F], lambda p: p.y > 0.012 and -0.048 < p.z < 0.030)),
              ("guard_bow", hull_tree([F], lambda p: -0.076 < p.y < -0.041 and p.z < 0.030)),
              ("slide", hull_tree([SL], lambda p: True))]
    pr = Placer(arms, skin, "R", ["hand.R", "palm.01.R", "palm.02.R", "palm.03.R", "palm.04.R", "thumb.01.R"])
    pr.solids = solids
    # перепонка — у середины между суставом большого (конец thumb.01) и костяшкой указательного
    hand_inv = A.world(arms, "hand.R").inverted()
    web_c = hand_inv @ ((arms.matrix_world @ arms.pose.bones["thumb.01.R"].tail + arms.matrix_world @ arms.pose.bones["f_index.01.R"].head) * 0.5)
    web_pts = pr.local(["hand.R", "thumb.01.R", "f_index.01.R", "palm.01.R"], lambda p: (p - web_c).length < 0.022)
    palm_pts = pr.local(["hand.R", "palm.01.R", "palm.02.R", "palm.03.R", "palm.04.R"], lambda p: p.x < -0.004)
    heel_pts = pr.local(["hand.R"], lambda p: p.x < -0.004 and p.y < 0.030)
    report["placer_points"] = {"web": len(web_pts), "palm": len(palm_pts), "heel": len(heel_pts)}
    pr.contacts = [("web→tang", web_pts, tang, 3.0), ("palm→panel", palm_pts, right_panel, 1.0), ("heel→back", heel_pts, backstrap, 1.0)]
    H0 = A.world(arms, "hand.R")
    H = pr.solve(H0, web_c, log_name="правая")
    set_hand(arms, "R", H)
    hand_in_gun = frame_w.inverted() @ A.world(arms, "hand.R")
    report["hand_R_in_gun_mm"] = [round(c * 1000, 1) for c in hand_in_gun.translation]
    report["hand_R_shift_mm"] = [round(c * 1000, 1) for c in (frame_w.inverted() @ H).translation - (frame_w.inverted() @ H0).translation]
    report["hand_R_rot_deg"] = round(math.degrees((H0.to_3x3().inverted() @ H.to_3x3()).to_quaternion().angle), 1)

    # ---- пальцы правой вокруг рукоятки (полные углы хвата владельца — база, start — доля)
    tree = A.bvh_of(gun)
    full_r = hands.pose("R", 1.0, thumb=1.0)
    full_r.update({n: open_r[n] for n in ("f_index.01.R", "f_index.02.R", "f_index.03.R")})
    r_pose = A.wrap(arms, hands, skin, dict(full_r), "R", tree, fingers=("f_middle", "f_ring", "f_pinky"),
                    start=(0.7, 0.45, 0.45), joints=(0, 1, 2), clear=CLEAR)
    r_fire = index_on_trigger(arms, hands, skin, dict(r_pose), frame_w, A.bvh_of([bpy.data.objects["Trigger_Mesh"]]))
    band = faces_where([F, SL], lambda p: p.z > 0.036 and p.y < -0.030)      # полоса рамки под затвором и кромка затвора
    r_rest = index_along_frame(arms, hands, skin, dict(r_pose), band, frame_w)
    A.apply(arms, r_rest)

    if STAGE == "right":
        # левая убрана; большой правой — вдоль рамки под затворной задержкой, как в одноручном хвате
        away = A.left_pose(arms, LEFT_AWAY, Vector((-0.3, -0.9, -0.3)), Vector((-1.0, 0.0, 0.0)))
        A.set_world(arms, "ik_hand.L", frame_w @ away)
        A.apply(arms, hands.pose("L", 0.5, thumb=0.4))
        l_pose = hands.pose("L", 0.5, thumb=0.4)
        l_in_gun = frame_w.inverted() @ A.world(arms, "ik_hand.L")
        tree_l = tree
        tree_lt = tree
        A.apply(arms, {n: open_r[n] for n in open_r if n.startswith("thumb")})
        r_rest = thumb_hinge_to(arms, hands, skin, tree, frame_w, r_rest, "R", R_THUMB_SOLO_TIP, R_THUMB_SOLO_MCP, solids=solids)
        for n in ("thumb.01.R", "thumb.02.R", "thumb.03.R"):
            r_fire[n] = r_rest[n]
    else:
        l_pose, l_in_gun, tree_l, tree_lt, r_rest, r_fire = both_hands(arms, hands, skin, gun, frame_w, open_r, r_rest, r_fire, F, G, solids)

    # ---- отчёт о касаниях и проникновениях
    gi = frame_w.inverted()
    report["thumb_R_mm"] = {"mcp": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.01.R"].tail)],
                            "ip": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.02.R"].tail)],
                            "tip": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.03.R"].tail)]}
    log("большой правой (мм)", report["thumb_R_mm"])
    report["thumb_L_mm"] = {"mcp": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.01.L"].tail)],
                            "ip": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.02.L"].tail)],
                            "tip": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.03.L"].tail)],
                            "cmc": [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones["thumb.01.L"].head)]}
    log("большой левой (мм)", report["thumb_L_mm"])
    report["hand_L_in_gun_mm"] = [round(c * 1000, 1) for c in (gi @ A.world(arms, "hand.L")).translation]
    log("кисть левой (мм)", report["hand_L_in_gun_mm"])
    fit = {}
    for label, pose in (("rest", r_rest), ("fire", r_fire)):
        A.apply(arms, pose)
        fit[label] = {
            "right_gap_mm": {f: round(skin.gap(tree, [f"{f}.{i:02d}.R" for i in (1, 2, 3)]) * 1000, 1) for f in A.FINGERS},
            "right_thumb_gap_mm": round(skin.gap(tree_lt, ["thumb.02.R", "thumb.03.R"]) * 1000, 1),
            "web_gap_mm": round(skin.gap(tang, WEB_BONES) * 1000, 1),
            "palm_gap_mm": round(skin.gap(right_panel, PALM_BONES) * 1000, 1),
            "left_gap_mm": {f: round(skin.gap(tree_l, [f"{f}.{i:02d}.L" for i in (1, 2, 3)]) * 1000, 1) for f in A.FINGERS + ("thumb",)},
            "inside_right": inside_count(skin, A.RIGHT, gun),
            "inside_left": inside_count(skin, A.LEFT, gun),
            "joints_right": joint_report(arms, hands, "R"),
            "joints_left": joint_report(arms, hands, "L"),
        }
    report["fit"] = fit

    # ---- стойки: Frame ключами, хват общий, указательный — по стойке
    clip = A.Clip(arms, "PM_Stances")
    for stance, frame in A.STANCE_FRAMES.items():
        clip.key_matrix("Frame", frame, all_stances[stance])
        bpy.context.scene.timeline_markers.new(A.STANCE_NAMES[stance], frame=frame)
        src = r_fire if stance == "ADS" else r_rest
        clip.key_pose(frame, {n: src[n] for n in ("f_index.01.R", "f_index.02.R", "f_index.03.R")})
    for fc in A.fcurves(clip.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    scene.frame_start, scene.frame_end = 1, A.STANCE_FRAMES["ADS"] + 9
    scene.frame_set(A.STANCE_FRAMES["READY"])
    A.apply(arms, r_rest)
    A.apply(arms, l_pose)
    hands.place(arms)
    report["reach_mm"] = {}
    for stance, frame in A.STANCE_FRAMES.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        gs = all_stances[stance]
        report["reach_mm"][stance] = {"R": A.reach(arms, "hand.R", gs @ hand_in_gun), "L": A.reach(arms, "ik_hand.L", gs @ l_in_gun)}
    scene.frame_set(A.STANCE_FRAMES["READY"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT))
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log("saved", OUT)
    log(json.dumps({k: report[k] for k in ("hand_R_in_gun_mm", "hand_R_shift_mm", "hand_R_rot_deg", "reach_mm", "placer_points")}, ensure_ascii=False))
    for label in ("rest", "fire"):
        f = fit[label]
        log(label, "R gaps", f["right_gap_mm"], "thumbR", f["right_thumb_gap_mm"], "web", f["web_gap_mm"], "palm", f["palm_gap_mm"])
        log(label, "L gaps", f["left_gap_mm"], "inside R", f["inside_right"], "inside L", f["inside_left"])
        bad = {n: j for side in ("joints_right", "joints_left") for n, j in f[side].items() if j["flags"]}
        log(label, "joints flagged", json.dumps(bad, ensure_ascii=False))


def check(path: Path) -> None:
    """Проверка готового файла хвата (например, правленного владельцем) без изменений: зазоры сетки перчатки до деталей,
    глубина проникновений по костям, углы суставов — для кадров «от бедра» (11) и «прицел» (21); отчёт рядом с файлом."""
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    scene.frame_set(A.STANCE_FRAMES["READY"])
    bpy.context.view_layer.update()
    skin = A.Skin(bpy.data.objects["FPS_Arms"])
    gun = [bpy.data.objects[n] for n in GUN_PARTS if n in bpy.data.objects]
    F, G = bpy.data.objects["Frame_Mesh"], bpy.data.objects["Grip_Mesh"]
    # «оси хвата владельца» для углов суставов — из его действия на ВЕРАСе, если оно в файле; иначе из текущей позы
    class _Ready:
        pass
    ready = {"basis": {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}}
    if "VERAS54_Grip_Manual_v02" in bpy.data.actions:
        act = bpy.data.actions["VERAS54_Grip_Manual_v02"]
        cur = arms.animation_data.action if arms.animation_data else None
        ad = arms.animation_data or arms.animation_data_create()
        saved = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
        ad.action = act
        if act.slots:
            ad.action_slot = act.slots[0]
        scene.frame_set(1)
        bpy.context.view_layer.update()
        ready = {"basis": {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}}
        ad.action = cur
        for n, m in saved.items():
            arms.pose.bones[n].matrix_basis = m
        scene.frame_set(A.STANCE_FRAMES["READY"])
        bpy.context.view_layer.update()
    hands = A.Hands(arms, ready)
    out = {"file": str(path)}
    for label, frame in (("rest", A.STANCE_FRAMES["READY"]), ("fire", A.STANCE_FRAMES["ADS"])):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        frame_w = A.world(arms, "Frame")
        tang = faces_where([F], lambda p: p.y > 0.012 and 0.028 < p.z < 0.047)
        right_panel = faces_where([F, G], lambda p: p.x < -0.006 and p.z < 0.040 and p.y > -0.030)
        left_panel = faces_where([F, G], lambda p: p.x > 0.006 and p.z < 0.040 and p.y > -0.034)
        tree = A.bvh_of(gun)
        tree_l = A.surface([(o, "") for o in gun] + [(bpy.data.objects["FPS_Arms"], "R")])
        tree_lt = A.surface([(o, "") for o in gun] + [(bpy.data.objects["FPS_Arms"], "L")])
        gi = frame_w.inverted()
        out[label] = {
            "right_gap_mm": {f: round(skin.gap(tree, [f"{f}.{i:02d}.R" for i in (1, 2, 3)]) * 1000, 1) for f in A.FINGERS},
            "right_thumb_gap_mm": round(skin.gap(tree_lt, ["thumb.02.R", "thumb.03.R"]) * 1000, 1),
            "web_gap_mm": round(skin.gap(tang, WEB_BONES) * 1000, 1),
            "palm_gap_mm": round(skin.gap(right_panel, PALM_BONES) * 1000, 1),
            "left_palm_gap_mm": round(skin.gap(left_panel, ["hand.L", "palm.01.L", "palm.02.L", "palm.03.L", "palm.04.L"]) * 1000, 1),
            "left_gap_mm": {f: round(skin.gap(tree_l, [f"{f}.{i:02d}.L" for i in (1, 2, 3)]) * 1000, 1) for f in A.FINGERS + ("thumb",)},
            "inside_right": inside_count(skin, A.RIGHT, gun),
            "inside_left": inside_count(skin, A.LEFT, gun),
            "joints_right": joint_report(arms, hands, "R"),
            "joints_left": joint_report(arms, hands, "L"),
            "hand_R_in_gun_mm": [round(c * 1000, 1) for c in (gi @ A.world(arms, "hand.R")).translation],
            "hand_L_in_gun_mm": [round(c * 1000, 1) for c in (gi @ A.world(arms, "hand.L")).translation],
            "tips_mm": {n: [round(c * 1000, 1) for c in gi @ (arms.matrix_world @ arms.pose.bones[n].tail)]
                        for n in [f"{f}.03.{sd}" for sd in ("R", "L") for f in A.FINGERS + ("thumb",)]},
        }
        f = out[label]
        log(label, "R gaps", f["right_gap_mm"], "thumbR", f["right_thumb_gap_mm"], "web", f["web_gap_mm"], "palm", f["palm_gap_mm"])
        log(label, "L gaps", f["left_gap_mm"], "L palm", f["left_palm_gap_mm"])
        log(label, "inside R", f["inside_right"], "inside L", f["inside_left"])
        bad = {n: j for side in ("joints_right", "joints_left") for n, j in f[side].items() if j["flags"]}
        log(label, "joints flagged", json.dumps(bad, ensure_ascii=False))
    rep = path.with_name(path.stem + "_check.json")
    rep.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    log("report", rep)


if MODE == "build":
    build()
elif MODE == "check":
    check(Path(A.ARGS[1]))
elif MODE == "reload":
    # клипы и позы перезарядки от хвата владельца: позы левой по фазам — в PM_FPS_ReloadPoses_v01.blend (нет — создаётся из расчёта,
    # есть — читается, в т.ч. с его правками), клипы — PM_FPS_Clips_v02.blend
    A.GRIP_FILE = OWNER_GRIP
    A.CLIPS_FILE = A.SRC / "anim/PM_FPS_Clips_v02.blend"
    A.POSES_FILE = A.SRC / "anim/PM_FPS_ReloadPoses_v01.blend"
    A.clips()
elif MODE == "poses_stills":
    A.GRIP_FILE = A.SRC / "anim/PM_FPS_ReloadPoses_v01.blend"
    A.STILLS = A.SRC / "anim/Кадры_перезарядка_позы"
    A.STANCE_FRAMES = dict(A.POSE_FRAMES)
    A.ARGS = [a for a in A.ARGS if a != "right"]
    A.stills()
elif MODE == "stills":
    extra = [a for a in A.ARGS[1:] if a.endswith(".blend")]
    if extra:                                              # кадры чужого файла: -- stills <файл.blend> [стойки]
        A.GRIP_FILE = Path(extra[0])
        A.STILLS = Path(extra[0]).with_name("Кадры_" + Path(extra[0]).stem)
        A.ARGS = [a for a in A.ARGS if a != extra[0]]
    else:
        A.GRIP_FILE = OUT
        A.STILLS = STILLS
    A.ARGS = [a for a in A.ARGS if a != "right"]        # иначе «right» примут за имя стойки
    A.stills()
else:
    log("режим: build | stills")
