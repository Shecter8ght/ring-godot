"""ПМ v11 от первого лица: сцена с руками владельца, двуручный хват, стойки (позже — клипы и экспорт).

Руки — FPS_ArmsRig из VERAS54_Reload_Full_v05.blend (копия; оригинал не трогается), хват правой — боевой хват
владельца на ВЕРАСе (действие VERAS54_Grip_Manual_v02). ПМ — игровая сетка _asset_src/pm_game/lp/PM_Game_export_v01.blend
(оси игры до перевода glTF: дуло −Y, верх +Z, правая сторона стрелка −X, начало — рукоятка; карты 100, износ ставит игра).
Кости ПМ в арматуре рук: Frame (в правой кисти), Bolt (затвор), Hammer, Trigger, SlideStop, MagCatch, Safety (на затворе),
Magazine_Control (в позах — на Frame, в перезарядке её ведут ключи), MagazineFollower, RoundChamber, JamCase (гильза в окне), Suppressor.

Решения владельца 2026-10-14: во всех стойках две руки; по умолчанию — наискосок влево-вниз (CARRY), колесо вверх —
от бедра (READY), ПКМ — прицел (ADS); хват ставит агент, владелец правит позы в Blender.
Пистолет — главный: кость Frame (под корнем рук) несёт ПМ, цели кистей ik_hand.R / ik_hand.L — её дочерние.
Стойка — только положение Frame (действие PM_Stances: кадр 1 — наискосок, 11 — от бедра, 21 — прицел), хват — положение
кистей на пистолете и пальцы, общее для всех стоек (без ключей). Пальцы подгоняются по сетке перчатки один раз.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/animate_pm_v11.py -- grip|stills [стойки]
  grip   → _asset_src/pm_game/anim/PM_FPS_Grip_v02.blend (действие PM_Stances, хват без ключей)
  clips  → _asset_src/pm_game/anim/PM_FPS_Clips_v01.blend (от хвата владельца в v02; его файл не меняется)
  stills [carry|ready|ads …] [out=<папка>] → _asset_src/pm_game/anim/Кадры/<стойка>_<вид>.png (глазами, справа, слева, снизу, спереди)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/pm_game"
ARMS_FILE = Path(r"E:\Models Blender\WEAPONS\ВЕРАС-54 — модель и обвесы\ВЕРАС-54\Игровая версия\Перезарядка v01 (Claude)\VERAS54_Reload_Full_v05.blend")
GUN_FILE = SRC / "lp/PM_Game_export_v01.blend"
GRIP_FILE = SRC / "anim/PM_FPS_Grip_v02.blend"
STILLS = SRC / "anim/Кадры"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "grip"
FPS = 30
CAM = Vector((0.0, 0.02, 1.8))
# Где стоит рукоятка ПМ в кисти владельца (его хват на ВЕРАСе, автомат в покое). Подобрано по замерам обеих рукояток
# (work/probe_rifle_grip.py, probe_grip_fit.py): средний палец под скобой (у ПМ она длиннее вперёд — ПМ на 6 мм выше, чем
# у ВЕРАСа, иначе палец ложится на низ скобы и не прижимается к рукоятке), передняя стенка ПМ там же, где у ВЕРАСа,
# правая щёчка — у ладони (ПМ на 5 мм тоньше).
PM_IN_RIFLE_HAND = Vector((-0.1425, -0.279, 1.622))
RIGHT = ["hand.R"] + [f"{f}.{i:02d}.R" for f in ("f_index", "f_middle", "f_ring", "f_pinky", "thumb") for i in (1, 2, 3)] + [f"palm.{i:02d}.R" for i in (1, 2, 3, 4)]
LEFT = [n[:-1] + "L" for n in RIGHT]
FINGERS = ("f_index", "f_middle", "f_ring", "f_pinky")
# Узел игровой модели → кость (меши лежат под пустышками деталей). Suppressor виден только с обвесом — решает игра.
PART_BONE = {"Frame": "Frame", "Slide": "Bolt", "Barrel": "Frame", "Hammer": "Hammer", "Trigger": "Trigger",
             "SlideStop": "SlideStop", "MagCatch": "MagCatch", "Safety": "Safety", "Magazine": "Magazine_Control",
             "Suppressor": "Suppressor"}
MARKERS = {"Muzzle": "Frame", "MuzzleSuppressed": "Frame", "SightFront": "Bolt", "SightRear": "Bolt"}


def rot(axis: str, deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 4, axis)


def gun_pose(pos: tuple, pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Matrix:
    """Положение ПМ в мире: pitch — дуло вверх, yaw — дуло влево, roll — завал верха влево (градусы)."""
    return Matrix.Translation(Vector(pos)) @ rot("Z", yaw) @ rot("X", -pitch) @ rot("Y", roll)


def basis(fingers: Vector, palm: Vector, side: str) -> Matrix:
    """Ориентация кисти: ось Y кости — от запястья к костяшкам; X — к ладони у левой, к тыльной стороне у правой;
    Z тогда смотрит в сторону большого пальца (так у обеих кистей рига в хвате владельца)."""
    y = fingers.normalized()
    x = (palm - y * palm.dot(y)).normalized()
    if side == "R":
        x = -x
    z = x.cross(y)
    return Matrix((x, y, z)).transposed().to_4x4()


# ================================================================ сцена

def append_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.unit_settings.system = "METRIC"
    with bpy.data.libraries.load(str(ARMS_FILE), link=False) as (src, dst):
        dst.objects = [n for n in ("FPS_ArmsRig", "FPS_Arms", "FPS • Camera") if n in src.objects]
        dst.actions = [n for n in ("VERAS54_Grip_Manual_v02",) if n in src.actions]
    for ob in dst.objects:
        scene.collection.objects.link(ob)
    with bpy.data.libraries.load(str(GUN_FILE), link=False) as (src, dst2):
        dst2.objects = [n for n in src.objects if not n.endswith("_LOD1")]
    for ob in dst2.objects:
        if ob is not None:
            scene.collection.objects.link(ob)
    arms = bpy.data.objects["FPS_ArmsRig"]
    arms.animation_data_clear()
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    scene.camera = bpy.data.objects["FPS • Camera"]
    return scene, arms


def read_ready(scene, arms) -> dict:
    """Боевой хват владельца на ВЕРАСе (его действие, кадр 1): базисы всех костей и правая кисть."""
    act = bpy.data.actions["VERAS54_Grip_Manual_v02"]
    ad = arms.animation_data_create()
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    scene.frame_set(1)
    bpy.context.view_layer.update()
    ready = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
    hand = (arms.matrix_world @ arms.pose.bones["hand.R"].matrix).copy()
    ad.action = None
    for pb in arms.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return {"basis": ready, "hand_r": hand}


def gun_local(name: str) -> Matrix:
    return bpy.data.objects["PM"].matrix_world.inverted() @ bpy.data.objects[name].matrix_world


def build_rig(scene, arms, ready: dict) -> dict:
    """Кости ПМ в арматуре рук. Frame — дочерняя правой кисти: посадка в руку задаётся здесь."""
    grip = ready["hand_r"].inverted() @ Matrix.Translation(PM_IN_RIFLE_HAND)   # ПМ в осях правой кисти
    frame_rest = arms.data.bones["hand.R"].matrix_local @ grip
    at = {k: gun_local(k).translation.copy() for k in ("Slide", "Hammer", "Trigger", "SlideStop", "MagCatch", "Safety",
                                                       "Magazine", "Suppressor", "Barrel")}
    bpy.context.view_layer.objects.active = arms
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arms.data.edit_bones

    def bone(name: str, parent: str, local: Vector, length: float = 0.015) -> None:
        eb = ebs.new(name)
        eb.head, eb.tail = (0.0, 0.0, 0.0), (0.0, length, 0.0)
        eb.matrix = frame_rest @ Matrix.Translation(local)
        eb.parent = ebs[parent]
        eb.use_deform = False

    bone("Frame", "hand.R", Vector(), 0.04)
    for name, key in (("Bolt", "Slide"), ("Hammer", "Hammer"), ("Trigger", "Trigger"), ("SlideStop", "SlideStop"),
                      ("MagCatch", "MagCatch"), ("Suppressor", "Suppressor")):
        bone(name, "Frame", at[key])
    bone("Safety", "Bolt", at["Safety"], 0.012)
    bone("Magazine_Control", "Frame", at["Magazine"], 0.02)       # для перезарядки клипы поведут его ключами
    bone("MagazineFollower", "Magazine_Control", at["Magazine"], 0.01)
    bone("RoundChamber", "Frame", at["Barrel"], 0.01)
    bone("JamCase", "Bolt", at["Slide"], 0.01)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    bpy.context.view_layer.update()

    def attach(ob, bone_name: str) -> None:
        w = ob.matrix_world.copy()
        ob.parent = arms
        ob.parent_type = "BONE"
        ob.parent_bone = bone_name
        ob.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        ob.matrix_world = w

    # корень ПМ — туда, где Frame стоит сейчас (в «покое» кисть повёрнута ограничением COPY_ROTATION от ik_hand,
    # точка покоя кости не годится); детали пересаживаются на кости с сохранением мировых матриц
    root = bpy.data.objects["PM"]
    root.matrix_world = arms.matrix_world @ arms.pose.bones["Frame"].matrix
    bpy.context.view_layer.update()
    for ob in [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("FPS_")]:
        owner = ob.parent
        while owner is not None and owner.name not in PART_BONE:
            owner = owner.parent
        bone_name = PART_BONE.get(owner.name, "Frame") if owner is not None else "Frame"
        if ob.name == "Follower_Mesh":
            bone_name = "MagazineFollower"
        attach(ob, bone_name)
    for name, bone_name in MARKERS.items():
        attach(bpy.data.objects[name], bone_name)
    wf = bpy.data.objects.new("WeaponFrame", None)                  # оси оружия у рукоятки: сюда игра ставит обвесы
    wf.empty_display_size = 0.01
    scene.collection.objects.link(wf)
    wf.matrix_world = root.matrix_world.copy()
    attach(wf, "Frame")
    for ob in [o for o in bpy.data.objects if o.type == "EMPTY" and o.parent is not None and o.parent.type != "ARMATURE"]:
        bpy.data.objects.remove(ob, do_unlink=True)                  # пустышки деталей больше не нужны (меши — на костях)
    for name in ("PM", "PM_LOD1"):
        if name in bpy.data.objects:
            bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    bpy.data.objects["Magazine_Mesh"].name = "Part_Magazine"         # имена, которые ищет игра
    return {"grip": grip}


# ================================================================ пальцы (как у ракетницы)

class Hands:
    """Сгиб пальца правой — вокруг той оси, вокруг которой он согнут в хвате владельца (у правой кисти рига оси костей
    пальцев повёрнуты по-своему); у левой сгиб — локальная X (её хват на цевье смешивает сгиб с разворотом пальцев).
    Сдвиги костей ладони и большого пальца из хвата владельца (он двигал костяшки) правая кисть сохраняет всегда."""

    def __init__(self, arms, ready: dict) -> None:
        self.axis: dict = {}
        self.loc: dict = {}
        for n, m in ready["basis"].items():
            loc, q, _scale = m.decompose()
            if n.endswith(".L") and n.split(".")[0] in FINGERS:
                self.axis[n] = (Vector((1.0, 0.0, 0.0)), max(q.to_euler().x, 0.0))
            else:
                axis, angle = q.to_axis_angle()
                if angle > math.pi:
                    axis, angle = -axis, math.tau - angle
                self.axis[n] = (axis.normalized(), angle)
            if n in RIGHT and loc.length > 1e-5:
                self.loc[n] = loc.copy()

    def scaled(self, bone: str, k: float) -> Quaternion:
        axis, angle = self.axis[bone]
        return Quaternion(axis, angle * k)

    def pose(self, side: str, k: float = 1.0, thumb: float | None = None) -> dict:
        out = {}
        for n in (RIGHT if side == "R" else LEFT):
            if n.startswith("hand"):
                continue
            out[n] = self.scaled(n, (k if thumb is None else thumb) if n.startswith("thumb") else k)
        return out

    def place(self, arms) -> None:
        """Костяшки правой — как у владельца, левой — как в риге."""
        for n in RIGHT + LEFT:
            arms.pose.bones[n].location = self.loc.get(n, Vector())
        bpy.context.view_layer.update()


def apply(arms, pose: dict) -> None:
    for n, q in pose.items():
        arms.pose.bones[n].rotation_quaternion = q
    bpy.context.view_layer.update()


def set_world(arms, bone: str, m: Matrix) -> None:
    arms.pose.bones[bone].matrix = arms.matrix_world.inverted() @ m
    bpy.context.view_layer.update()


def world(arms, bone: str) -> Matrix:
    return arms.matrix_world @ arms.pose.bones[bone].matrix


def surface(parts: list) -> BVHTree:
    """Поверхность в мире из пар (объект, сторона): сторона "L"/"R" — только грани этой руки из сетки рук (по весам)."""
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o, side in parts:
        keep = None
        if side:
            mark = {g.index: g.name[-1] for g in o.vertex_groups if g.name[-2:] in (".L", ".R")}
            keep = set()
            for v in o.data.vertices:
                w = {"L": 0.0, "R": 0.0}
                for g in v.groups:
                    if g.group in mark:
                        w[mark[g.group]] += g.weight
                if w[side] > w["L" if side == "R" else "R"]:
                    keep.add(v.index)
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(verts)
        verts += [ev.matrix_world @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons if keep is None or all(i in keep for i in p.vertices)]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def bvh_of(objects) -> BVHTree:
    return surface([(o, "") for o in objects])


class Skin:
    """Поверхность перчатки по костям: вершины сетки рук, где кость главная. Касание считается по самой сетке —
    ось кости лежит не по центру пальца (до поверхности 11–15 мм, work/probe_finger_radius.py)."""

    def __init__(self, ob) -> None:
        self.ob = ob
        names = {g.index: g.name for g in ob.vertex_groups}
        self.verts: dict = {}
        for v in ob.data.vertices:
            if v.groups:
                g = max(v.groups, key=lambda g: g.weight)
                self.verts.setdefault(names[g.group], []).append(v.index)

    def gap(self, tree: BVHTree, bones: list) -> float:
        """Наименьшее расстояние от сетки этих костей до поверхности (без знака: пальцы подходят снаружи)."""
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        best = 1e9
        for n in bones:
            for i in self.verts.get(n, ()):
                loc, _nrm, _i, dist = tree.find_nearest(mw @ me.vertices[i].co)
                if loc is not None and dist < best:
                    best = dist
        ev.to_mesh_clear()
        return best


def wrap(arms, hands: Hands, skin: Skin, pose: dict, side: str, tree: BVHTree, fingers=FINGERS, start=(1.0, 1.0, 1.0),
         joints=(0, 1, 2), clear: float = 0.0015) -> dict:
    """Дожать пальцы до поверхности: сустав за суставом от основания, пока сетка пальца не коснётся предмета.
    joints — какие суставы сгибать (у правой основание оставляем как у владельца: его ось там смешана с разворотом)."""
    for finger in fingers:
        chain = [f"{finger}.{i:02d}.{side}" for i in (1, 2, 3)]
        angles, base = [], {}
        for i, n in enumerate(chain):
            axis, angle = hands.axis[n]
            base[n] = pose[n] @ Quaternion(axis, angle).inverted()
            angles.append(angle * start[i])
            pose[n] = base[n] @ Quaternion(axis, angles[i])
        apply(arms, pose)
        for i, n in enumerate(chain):
            if i not in joints:
                continue
            axis, _ = hands.axis[n]
            limit = math.radians((95, 115, 85)[i])
            while angles[i] < limit:
                if skin.gap(tree, chain[i:]) <= clear:
                    break
                angles[i] += math.radians(1.5)
                pose[n] = base[n] @ Quaternion(axis, angles[i])
                arms.pose.bones[n].rotation_quaternion = pose[n]
                bpy.context.view_layer.update()
    return pose


def reach_tip(arms, chain: list, target: Vector, iters: int = 40) -> None:
    """Довести кончик цепочки (последняя кость) до точки: поворот каждой кости у её основания, от кончика к основанию."""
    inv = arms.matrix_world.inverted()
    for _ in range(iters):
        for n in reversed(chain):
            pb = arms.pose.bones[n]
            tip = arms.matrix_world @ arms.pose.bones[chain[-1]].tail
            head = arms.matrix_world @ pb.head
            a, b = tip - head, target - head
            if a.length < 1e-6 or b.length < 1e-6:
                continue
            q = a.rotation_difference(b)
            if q.angle < 1e-4:
                continue
            q = Quaternion(q.axis, min(q.angle, math.radians(8.0)))
            m = Matrix.Translation(head) @ q.to_matrix().to_4x4() @ Matrix.Translation(-head)
            pb.matrix = inv @ m @ arms.matrix_world @ pb.matrix
            bpy.context.view_layer.update()
        if ((arms.matrix_world @ arms.pose.bones[chain[-1]].tail) - target).length < 0.0015:
            break


def thumb_to(arms, skin: Skin, tree: BVHTree, frame_w: Matrix, pose: dict, side: str, tip: Vector,
             knuckle: Vector | None = None) -> dict:
    """Большой палец: кончик в точку (в осях ПМ); если задан сустав — сначала пясть (thumb.01) концом в него, затем
    две фаланги ведут кончик (иначе средний сустав срезает путь сквозь рамку). Касается рамки — точки отодвигаются
    наружу (+X ПМ — от левой щёчки) по 1.5 мм, пока сетка пальца не отойдёт."""
    names = [f"thumb.{i:02d}.{side}" for i in (1, 2, 3)]
    tip, knuckle = tip.copy(), knuckle.copy() if knuckle is not None else None
    for _ in range(12):
        if knuckle is not None:
            reach_tip(arms, names[:1], frame_w @ knuckle)
            reach_tip(arms, names[1:], frame_w @ tip)
        else:
            reach_tip(arms, names, frame_w @ tip)
        if skin.gap(tree, names[1:]) > 0.0015:
            break
        tip.x += 0.0015
        if knuckle is not None:
            knuckle.x += 0.0015
    for n in names:
        pose[n] = arms.pose.bones[n].rotation_quaternion.copy()
    return pose


def index_on_frame(arms, hands: Hands, skin: Skin, pose: dict, tree: BVHTree) -> dict:
    """Указательный правой — прямой вдоль рамки над скобой (палец снят со спуска): средняя и ногтевая фаланги
    почти прямые, у основания сгиб, пока палец не ляжет на рамку."""
    out = dict(pose)
    for k in (2, 3):
        out[f"f_index.{k:02d}.R"] = hands.scaled(f"f_index.{k:02d}.R", 0.12)
    out["f_index.01.R"] = hands.scaled("f_index.01.R", 0.0)
    apply(arms, out)
    axis, _ = hands.axis["f_index.01.R"]
    a = 0.0
    while a < math.radians(70) and skin.gap(tree, ["f_index.02.R", "f_index.03.R"]) > 0.0015:
        a += math.radians(1.5)
        out["f_index.01.R"] = Quaternion(axis, a)
        apply(arms, out)
    return out


# ================================================================ стойки

def stances(rear_sight: Vector) -> dict:
    """Где стоит ПМ (корень — рукоятка) в каждой стойке; камера в CAM, взгляд по −Y, правая сторона кадра — −X.
    Камера рук — 75° по вертикали (как в игре): точка на глубине d и смещении s видна в s/d·470 px от центра кадра 1280×720."""
    return {
        # от бедра: справа внизу, руки полусогнуты, дуло чуть внутрь, лёгкий завал к центру
        "READY": gun_pose((-0.14, -0.321, 1.646), pitch=0.5, yaw=4.0, roll=3.0),
        # наискосок влево-вниз: внизу кадра ближе к центру, дуло вниз-влево, верх завален влево
        "CARRY": gun_pose((-0.06, -0.30, 1.655), pitch=-15.0, yaw=15.0, roll=40.0),
        # прицел: целик на оси взгляда в 33 см от глаза (мушка и целик на одной высоте)
        "ADS": Matrix.Translation(Vector((CAM.x, CAM.y - 0.33, CAM.z)) - rear_sight),
    }


# Точки в осях ПМ (замеры рукоятки — work/probe_grip_fit.py: щёчки x ±14.5 мм, передняя стенка y −24 мм, низ скобы z 10 мм,
# рамка над скобой z 35–45 мм, затвор выше 42 мм). Пальцы правой вокруг рукоятки — до y ≈ −42 мм спереди, x ≈ +30 мм слева.
LEFT_MCP = Vector((0.040, -0.046, -0.031))       # костяшка среднего пальца левой (указательный — вплотную под скобой)
R_THUMB_TIP = Vector((0.028, -0.036, 0.038))     # большой правой — вдоль рамки у нижней кромки затвора, кончик над спуском
L_THUMB_MCP = Vector((0.031, 0.004, 0.024))      # большой левой — снаружи рамки, под большим правой
L_THUMB_TIP = Vector((0.030, -0.060, 0.020))     # … и вперёд вдоль рамки над скобой


def left_in_gun(arms) -> Matrix:
    """Опорная левая, большие пальцы вперёд (в осях ПМ): запястье рядом с правым, кисть «заломлена» вниз — пясть
    вперёд-вниз, ладонь вправо-вниз (основание ладони на левой щёчке, под большим пальцем правой); костяшки — у левого
    переднего угла пальцев правой, пальцы обхватывают их спереди; большой палец вдоль рамки под большим правой."""
    m = basis(Vector((-0.12, -0.97, -0.20)), Vector((-1.0, 0.10, -0.15)), "L")
    hand_rest = arms.data.bones["hand.L"].matrix_local
    mcp_local = hand_rest.inverted() @ arms.data.bones["f_middle.01.L"].head_local   # костяшка среднего в осях кисти
    m.translation = LEFT_MCP - m.to_3x3() @ mcp_local
    return m


# ================================================================ ключи

class Clip:
    def __init__(self, arms, name: str) -> None:
        self.arms = arms
        self.action = bpy.data.actions.new(name)
        self.action.use_fake_user = True
        ad = arms.animation_data or arms.animation_data_create()
        ad.action = self.action
        self.last: dict = {}

    def key_matrix(self, bone: str, frame: float, m_world: Matrix) -> None:
        pb = self.arms.pose.bones[bone]
        bpy.context.scene.frame_set(int(frame))
        pb.matrix = self.arms.matrix_world.inverted() @ m_world
        q = pb.rotation_quaternion.copy()
        prev = self.last.get(bone)
        if prev is not None and prev.dot(q) < 0.0:
            q.negate()
            pb.rotation_quaternion = q
        self.last[bone] = q
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def key_locs(self, frame: float, locs: dict) -> None:
        for n, loc in locs.items():
            pb = self.arms.pose.bones[n]
            pb.location = loc
            pb.keyframe_insert("location", frame=frame)

    def key_pose(self, frame: float, pose: dict) -> None:
        for n, q in pose.items():
            pb = self.arms.pose.bones[n]
            q = q.copy()
            prev = self.last.get(n)
            if prev is not None and prev.dot(q) < 0.0:
                q.negate()
            self.last[n] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=frame)


def reach(arms, bone: str, target: Matrix) -> float:
    """Насколько кисть не дотянулась до цели IK (мм)."""
    return round((world(arms, bone).translation - target.translation).length * 1000.0, 1)


def grip() -> None:
    scene, arms = append_scene()
    bpy.context.view_layer.update()                                      # мировые матрицы присоединённых узлов
    rear_sight = bpy.data.objects["SightRear"].matrix_world.translation.copy()      # ПМ ещё в начале координат
    ready = read_ready(scene, arms)
    rig = build_rig(scene, arms, ready)
    hand_of_gun = rig["grip"].inverted()                                 # правая кисть в осях ПМ
    for name in ("Suppressor_Mesh",):                                    # глушитель показывает игра, когда он надет
        bpy.data.objects[name].hide_viewport = bpy.data.objects[name].hide_render = True
    hands = Hands(arms, ready)
    hands.place(arms)
    gun = [bpy.data.objects[n] for n in ("Frame_Mesh", "Grip_Mesh", "Slide_Mesh", "Part_Magazine")]

    # ---- правая: хват владельца на рукоятке ПМ (ПМ стоит там, где была рукоятка автомата)
    skin = Skin(bpy.data.objects["FPS_Arms"])
    set_world(arms, "ik_hand.R", ready["hand_r"])
    r_pose = hands.pose("R")
    apply(arms, r_pose)
    tree = bvh_of(gun)
    frame_w = world(arms, "Frame")
    r_pose = wrap(arms, hands, skin, r_pose, "R", tree, fingers=("f_middle", "f_ring", "f_pinky"), start=(1.0, 0.7, 0.7),
                  joints=(1, 2))
    r_pose = thumb_to(arms, skin, tree, frame_w, r_pose, "R", R_THUMB_TIP)
    r_fire = wrap(arms, hands, skin, dict(r_pose), "R", bvh_of([bpy.data.objects["Trigger_Mesh"]]), fingers=("f_index",),
                  start=(0.8, 1.0, 1.0), joints=(0,))
    r_carry = index_on_frame(arms, hands, skin, dict(r_fire), bvh_of([bpy.data.objects["Frame_Mesh"], bpy.data.objects["Slide_Mesh"]]))
    apply(arms, r_fire)
    # ---- левая: пальцы обхватывают пальцы правой спереди, ладонь на левой щёчке, большой палец вдоль рамки
    l_in_gun = left_in_gun(arms)
    set_world(arms, "ik_hand.L", frame_w @ l_in_gun)
    l_pose = hands.pose("L", 0.2, thumb=0.3)
    apply(arms, l_pose)
    tree_l = surface([(o, "") for o in gun] + [(bpy.data.objects["FPS_Arms"], "R")])
    l_pose = thumb_to(arms, skin, tree_l, frame_w, l_pose, "L", L_THUMB_TIP, L_THUMB_MCP)
    l_pose = wrap(arms, hands, skin, l_pose, "L", tree_l, start=(0.15, 0.15, 0.15))
    fit = {"right_mm": {f: round(skin.gap(tree, [f"{f}.{i:02d}.R" for i in (1, 2, 3)]) * 1000, 1) for f in FINGERS + ("thumb",)},
           "left_mm": {f: round(skin.gap(tree_l, [f"{f}.{i:02d}.L" for i in (1, 2, 3)]) * 1000, 1) for f in FINGERS + ("thumb",)},
           "left_hand_error_mm": reach(arms, "hand.L", frame_w @ l_in_gun)}

    # ---- пистолет — главный: Frame отцепляется от кисти, цели кистей становятся его дочерними. Тогда стойка — это
    # только положение пистолета (одна кость), а хват — положение кистей на пистолете, общее для всех стоек.
    regrip_rig(arms)
    clip = Clip(arms, "PM_Stances")
    all_stances = stances(rear_sight)
    for stance, frame in STANCE_FRAMES.items():
        clip.key_matrix("Frame", frame, all_stances[stance])
        bpy.context.scene.timeline_markers.new(STANCE_NAMES[stance], frame=frame)
    for fc in fcurves(clip.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"                            # кадр = стойка, без промежуточных положений
    scene.frame_start, scene.frame_end = 1, STANCE_FRAMES["ADS"] + 9
    scene.frame_set(STANCE_FRAMES["READY"])
    g = all_stances["READY"]
    set_world(arms, "ik_hand.R", g @ hand_of_gun)                    # без ключей: хват общий для всех стоек
    set_world(arms, "ik_hand.L", g @ l_in_gun)
    apply(arms, r_fire)
    apply(arms, l_pose)
    hands.place(arms)
    report = {"fit": fit, "reach_mm": {}}
    for stance, frame in STANCE_FRAMES.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        gs = all_stances[stance]
        report["reach_mm"][stance] = {"R": reach(arms, "hand.R", gs @ hand_of_gun), "L": reach(arms, "hand.L", gs @ l_in_gun)}
    scene.frame_set(STANCE_FRAMES["READY"])
    GRIP_FILE.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(GRIP_FILE))
    (SRC / "anim/grip_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PM_GRIP saved", GRIP_FILE, json.dumps(report, ensure_ascii=False), flush=True)


STANCE_FRAMES = {"CARRY": 1, "READY": 11, "ADS": 21}
STANCE_NAMES = {"CARRY": "Наискосок", "READY": "От бедра", "ADS": "Прицел"}
GUN_PARTS = ("Bolt", "Hammer", "Trigger", "SlideStop", "MagCatch", "Safety", "Magazine_Control", "MagazineFollower",
             "RoundChamber", "JamCase", "Suppressor")


def regrip_rig(arms) -> None:
    """Frame — под корнем рук, ik_hand.R / ik_hand.L — под Frame: двигаешь Frame — едет пистолет и обе кисти с ним;
    двигаешь ik_hand.R — кисть скользит по рукоятке, пистолет стоит. Кости деталей ПМ — в скрытой коллекции."""
    keep = {n: world(arms, n) for n in ("Frame", "ik_hand.R", "ik_hand.L")}
    bpy.context.view_layer.objects.active = arms
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arms.data.edit_bones
    ebs["Frame"].parent = ebs["FPS_Root"]                           # длину не трогать: детали висят на её конце
    for n in ("ik_hand.R", "ik_hand.L"):
        ebs[n].parent = ebs["Frame"]
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    for n, m in keep.items():                                       # сначала родитель, потом кисти
        set_world(arms, n, m)
    cols = arms.data.collections
    parts = cols.get("ПМ — детали") or cols.new("ПМ — детали")
    ctrl = cols.get("ПМ — пистолет") or cols.new("ПМ — пистолет")
    for n in GUN_PARTS + ("Frame",):
        bone = arms.data.bones[n]
        for c in list(bone.collections):
            c.unassign(bone)
        (ctrl if n == "Frame" else parts).assign(bone)
    parts.is_visible = False


def fcurves(action) -> list:
    """Кривые действия: в Blender 5 они лежат в слоях и полосах, в старых — прямо в действии."""
    if hasattr(action, "layers") and len(action.layers):
        out = []
        for layer in action.layers:
            for strip in layer.strips:
                for bag in strip.channelbags:
                    out += list(bag.fcurves)
        return out
    return list(action.fcurves)


# ================================================================ клипы (от хвата владельца)

CLIPS_FILE = SRC / "anim/PM_FPS_Clips_v01.blend"
GRIP_BONES = ["ik_hand.R", "ik_hand.L", "pole.R", "pole.L"] + RIGHT + LEFT
CLIP_INFO: dict = {}


def cam_offset(gun: Matrix, d: Vector = Vector(), pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Matrix:
    """Сдвиг и поворот пистолета в осях камеры вокруг его рукоятки: pitch — дуло вверх, yaw — дуло влево,
    roll — верх влево (градусы); d — в мире сцены (−X — вправо по кадру, +Z — вверх, −Y — от глаз)."""
    r = rot("Z", yaw) @ rot("X", -pitch) @ rot("Y", roll)
    return Matrix.Translation(gun.translation + d) @ r @ gun.to_3x3().to_4x4()


def blend(a: Matrix, b: Matrix, t: float) -> Matrix:
    q = a.to_quaternion().slerp(b.to_quaternion(), t)
    return Matrix.Translation(a.translation.lerp(b.translation, t)) @ q.to_matrix().to_4x4()


def ease(t: float) -> float:
    """Разгон и торможение без рывка на краях (квинтика: нулевые скорость и ускорение)."""
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


class Keyer:
    """Клип: на первом и последнем кадре ключи всех костей хвата и деталей (иначе кость без ключей осталась бы там,
    где её бросил прошлый клип), между ними — только то, что движется."""

    def __init__(self, arms, rest: dict, name: str, length: int, loop: bool = False) -> None:
        self.arms, self.rest, self.length = arms, rest, length
        self.action = bpy.data.actions.new(name)
        self.action.use_fake_user = True
        self.action.use_frame_range = True
        self.action.frame_start, self.action.frame_end = 0, length
        self.action.use_cyclic = loop
        arms.animation_data.action = self.action
        self.last: dict = {}
        CLIP_INFO[name] = {"frames": length, "loop": loop}

    def _key(self, name: str, frame: float) -> None:
        pb = self.arms.pose.bones[name]
        q = pb.rotation_quaternion.copy()
        prev = self.last.get(name)
        if prev is not None and prev.dot(q) < 0.0:
            q.negate()
            pb.rotation_quaternion = q
        self.last[name] = q
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def pose(self, frame: float, gun: Matrix, over: dict | None = None, all_bones: bool = False) -> None:
        """Поставить пистолет (мир) и кости (over: имя → matrix_basis поверх хвата) и ключи."""
        over = over or {}
        for n, m in self.rest.items():
            self.arms.pose.bones[n].matrix_basis = over.get(n, m)
        self.arms.pose.bones["Frame"].matrix = self.arms.matrix_world.inverted() @ gun
        names = list(self.rest) if all_bones or frame in (0, self.length) else list(over)
        for n in names + ["Frame"]:
            self._key(n, frame)

    def finish(self) -> None:
        for fc in fcurves(self.action):
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


def cycle(phase: float, a: float, b: float, c: float, e: float, p: float) -> tuple:
    """Два шага на цикл: на каждом ударе стопы пистолет проседает (a, м), раз за цикл уходит вбок (b, м)
    с креном (c, °) и поворотом (e, °); кивок p (°) — вместе с проседанием."""
    w = math.tau * phase
    bounce = 0.5 + 0.5 * math.cos(2.0 * w)            # 1 — удар стопы (фаза 0 и 0.5), 0 — середина шага
    d = Vector((-b * math.sin(w), 0.0, -a * bounce))
    return d, -p * bounce, e * math.sin(w + 0.35), c * math.sin(w)


def clips() -> None:
    """Первая партия: покой в обеих стойках, переходы между ними и в прицел, ходьба и бег (бег всегда наискосок)."""
    bpy.ops.wm.open_mainfile(filepath=str(GRIP_FILE))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    st = {}
    for name, frame in STANCE_FRAMES.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        st[name] = world(arms, "Frame")
    rest = {n: arms.pose.bones[n].matrix_basis.copy() for n in GRIP_BONES + list(GUN_PARTS) if n in arms.pose.bones}
    arms.animation_data.action = None
    carry, ready, ads = st["CARRY"], st["READY"], st["ADS"]
    run_base = cam_offset(carry, Vector((0.0, 0.025, 0.012)), pitch=-6.0, roll=8.0)     # на бегу ближе к телу, сильнее завален

    def idle(name: str, gun: Matrix) -> None:
        k = Keyer(arms, rest, name, 60, loop=True)
        for f in range(0, 61, 3):
            w = math.tau * f / 60.0
            k.pose(f, cam_offset(gun, Vector((0.0005 * math.sin(w * 0.5), 0.0, 0.0012 * math.sin(w))), pitch=0.3 * math.sin(w + 0.5)))
        k.finish()

    def move(name: str, gun: Matrix, frames: int, a: float, b: float, c: float, e: float, p: float, step: int) -> None:
        k = Keyer(arms, rest, name, frames, loop=True)
        for f in range(0, frames + 1, step):
            d, pitch, yaw, roll = cycle(f / frames, a, b, c, e, p)
            k.pose(f, cam_offset(gun, d, pitch, yaw, roll))
        k.finish()

    def go(name: str, a: Matrix, b: Matrix, frames: int, arc: Vector = Vector(), settle: float = 1.0) -> None:
        """Переход стойки: плавный путь с дугой arc (м, в середине пути) и лёгким дотягом в конце."""
        k = Keyer(arms, rest, name, frames)
        main = frames - 3
        for f in range(0, main + 1):
            t = ease(f / main)
            m = blend(a, b, t)
            m.translation += arc * math.sin(math.pi * t)
            k.pose(f, m)
        d = (b.translation - a.translation).normalized() * 0.002 * settle
        k.pose(main + 2, cam_offset(b, d, pitch=0.6 * settle))
        k.pose(frames, b)
        k.finish()

    idle("PM_Idle_Ready", ready)
    idle("PM_Idle_Carry", carry)
    go("PM_Carry_To_Ready", carry, ready, 10, Vector((0.0, -0.01, 0.012)))
    go("PM_Ready_To_Carry", ready, carry, 12, Vector((0.0, 0.0, -0.008)), settle=0.5)
    go("PM_Ready_To_ADS", ready, ads, 9, Vector((0.004, 0.006, 0.004)))
    go("PM_ADS_To_Ready", ads, ready, 9, Vector((0.0, 0.0, -0.004)), settle=0.5)
    go("PM_Carry_To_ADS", carry, ads, 12, Vector((-0.01, -0.012, 0.015)))
    go("PM_ADS_To_Carry", ads, carry, 13, Vector((0.0, 0.0, -0.01)), settle=0.5)
    move("PM_Walk_Ready", ready, 40, 0.004, 0.006, 1.5, 0.8, 0.6, 2)
    move("PM_Walk_Carry", carry, 40, 0.005, 0.008, 2.0, 1.0, 0.8, 2)
    move("PM_Run", run_base, 16, 0.014, 0.016, 5.0, 3.0, 3.0, 1)
    go("PM_Carry_To_Run", carry, run_base, 8)
    go("PM_Run_To_Carry", run_base, carry, 10, settle=0.5)
    arms.animation_data.action = bpy.data.actions["PM_Idle_Carry"]
    scene.frame_start, scene.frame_end = 0, 60
    scene.frame_set(0)
    for m in list(scene.timeline_markers):
        scene.timeline_markers.remove(m)
    bpy.ops.wm.save_as_mainfile(filepath=str(CLIPS_FILE))
    (SRC / "anim/clips.json").write_text(json.dumps(CLIP_INFO, ensure_ascii=False, indent=1), encoding="utf-8")
    print("PM_CLIPS saved", CLIPS_FILE, json.dumps(CLIP_INFO, ensure_ascii=False), flush=True)


def stills() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(GRIP_FILE))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    world_ = scene.world or bpy.data.worlds.new("Студия")
    scene.world = world_
    world_.use_nodes = True
    bg = next(n for n in world_.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.32, 0.33, 0.35, 1.0)
    bg.inputs["Strength"].default_value = 1.2
    for name, energy, rx, rz in (("Ключ", 3.5, 55, 35), ("Контр", 1.2, 60, -150)):
        sun = bpy.data.objects.new(name, bpy.data.lights.new(name, "SUN"))
        sun.data.energy = energy
        sun.rotation_euler = (math.radians(rx), 0.0, math.radians(rz))
        scene.collection.objects.link(sun)
    fps_cam = bpy.data.objects["FPS • Camera"]
    side = bpy.data.objects.new("Сбоку", bpy.data.cameras.new("Сбоку"))
    side.data.lens = 40
    side.data.clip_start = 0.01
    scene.collection.objects.link(side)
    out = next((Path(a[4:]) for a in ARGS[1:] if a.startswith("out=")), STILLS)
    out.mkdir(parents=True, exist_ok=True)
    only = [a for a in ARGS[1:] if not a.startswith("out=")]
    for stance, frame in STANCE_FRAMES.items():
        short = stance.lower()
        if only and short not in only:
            continue
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        focus = arms.matrix_world @ arms.pose.bones["Frame"].head
        for view, off in (("glaz", None), ("sprava", Vector((-0.42, 0.06, 0.08))), ("sleva", Vector((0.40, -0.12, 0.06))),
                          ("snizu", Vector((-0.12, -0.22, -0.34))), ("speredi", Vector((-0.06, -0.40, 0.05)))):
            if off is None:
                scene.camera = fps_cam
            else:
                z = off.normalized()
                x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
                m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
                m.translation = focus + off
                side.matrix_world = m
                scene.camera = side
            scene.render.filepath = str(out / f"{short}_{view}.png")
            bpy.ops.render.render(write_still=True)
    print("PM_STILLS done", flush=True)


if MODE == "stills":
    stills()
elif MODE == "clips":
    clips()
else:
    grip()
