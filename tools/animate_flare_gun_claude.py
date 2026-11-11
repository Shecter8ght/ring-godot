"""Ракетница Claude в руках от первого лица: сцена с руками владельца, хват правой рукой и клипы.

Руки — FPS_ArmsRig из VERAS54_Reload_Full_v05.blend (оригинал не трогается, берётся копия). Ракетница —
игровая сетка с запечёнными картами (FlareGun_Claude_v02_game_textured.blend), форма принятая.
Держит только правая рука; левая появляется лишь в перезарядке.

Перезарядка (30 кадров/с, 150 кадров = 5 с), как описал владелец:
  1–10   правая подводит ракетницу к середине, левая поднимается;
  10–18  левая ложится на ствол сверху, защёлка отпущена;
  20–29  левая переламывает ствол (32°), 30–38 уходит;
  36–46  правая переворачивает ракетницу казённым срезом вниз (дулом вверх);
  48–64  три встряхивания; гильза выходит на втором и падает;
  64–76  правая возвращает ракетницу в положение для заряжания;
  70–92  левая приносит новый патрон и подводит к патроннику;
  92–108 левая вставляет патрон: до половины, перехват, дослать до конца;
  108–118 левая уходит;
  116–126 правая взмахом вверх защёлкивает ствол; 126–150 возврат в стойку.

Кости ракетницы (в арматуре рук): Frame (в правой кисти), Barrel, Hammer, Trigger, Latch; патроны —
OldRound (стреляная гильза) и NewRound (новый патрон). Кисть правой ведёт кость ik_hand.R, левой — ik_hand.L.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1
    --python tools/animate_flare_gun_claude.py -- build | stills | export
  build  → _asset_src/flare_gun_claude/anim/FlareGun_Claude_FPS_v01.blend (править руки и ключи здесь)
  stills → anim/Кадры/*.png (проверочные кадры: вид стрелка и сбоку)
  export → assets/models/weapons/flare_gun_claude/flare_gun_claude_viewmodel.glb (клипы запечены, начало — в камере)
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src/flare_gun_claude"
ARMS_FILE = Path(r"E:\Models Blender\ВЕРАС-54 — модель и обвесы\ВЕРАС-54\Игровая версия\Перезарядка v01 (Claude)\VERAS54_Reload_Full_v05.blend")
GUN_FILE = SRC / "FlareGun_Claude_v02_game_textured.blend"
ANIM = SRC / "anim/FlareGun_Claude_FPS_v01.blend"
STILLS = SRC / "anim/Кадры"
OUT = ROOT / "assets/models/weapons/flare_gun_claude"
PROF = json.loads((SRC / "trace/profiles.json").read_text(encoding="utf-8"))
MODE = sys.argv[sys.argv.index("--") + 1] if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1 else "build"
MM = 0.001
U0, V0 = -62.0, -57.0
LEN = float(PROF["muzzle_u"])
HINGE, HPIV, TPIV = tuple(PROF["pin_hinge"]), tuple(PROF["pin_hammer"]), tuple(PROF["pin_trigger"])
BREECH, R_OUT = 0.3, 14.0
OPEN_DEG, COCK_DEG = 32.0, 40.7
FPS = 30
RELOAD_LEN = 150
RIGHT = ["hand.R"] + [f"{f}.{i:02d}.R" for f in ("f_index", "f_middle", "f_ring", "f_pinky", "thumb") for i in (1, 2, 3)] + [f"palm.{i:02d}.R" for i in (1, 2, 3, 4)]
LEFT = [n[:-1] + "L" for n in RIGHT]
FINGERS = ("f_index", "f_middle", "f_ring", "f_pinky")
# события перезарядки (кадры) — уходят в данные игры
EVENTS = {"open": 29, "chamber_down": 46, "shake_1": 50, "shake_2": 57, "shake_3": 63, "case_free": 58, "upright": 76,
          "insert": 108, "snap": 124, "close": 126}
ROUND_WINDOWS = {"old": [20, 68], "new": [70, 112]}
LEFT_WINDOWS = [[3, 40], [66, 120]]


def P(u: float, v: float, x: float = 0.0) -> Vector:
    """Точка чертежа ракетницы (мм) → её собственные оси (м): дуло по −Y, верх +Z, +X — влево от стрелка."""
    return Vector((x * MM, -(u - U0) * MM, (v - V0) * MM))


def rot(axis: str, deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 4, axis)


def gun_pose(pos: tuple, pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Matrix:
    """Положение ракетницы в мире: pitch — дуло вверх, yaw — дуло влево, roll — завал верха влево (градусы)."""
    return Matrix.Translation(Vector(pos)) @ rot("Z", yaw) @ rot("X", -pitch) @ rot("Y", roll)


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


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
        dst2.objects = list(src.objects)
    for ob in dst2.objects:
        scene.collection.objects.link(ob)
    arms = bpy.data.objects["FPS_ArmsRig"]
    arms.animation_data_clear()
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    scene.camera = bpy.data.objects["FPS • Camera"]
    return scene, arms


def read_ready(scene, arms) -> dict:
    """Боевой хват владельца на ВЕРАСе (его действие, кадр 1): базисы всех костей."""
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


def split_arms(arms) -> None:
    """Одна сетка рук → правая и левая: левую игра показывает только в перезарядке."""
    src = bpy.data.objects["FPS_Arms"]
    side_of = {g.index: ("L" if g.name.endswith(".L") else "R" if g.name.endswith(".R") else "") for g in src.vertex_groups}
    left = set()
    for v in src.data.vertices:
        score = {"L": 0.0, "R": 0.0}
        for g in v.groups:
            s = side_of.get(g.group, "")
            if s:
                score[s] += g.weight
        if score["L"] > score["R"]:
            left.add(v.index)
    for name, keep_left in (("FPS_Arms_Right", False), ("FPS_Arms_Left", True)):
        ob = src.copy()
        ob.data = src.data.copy()
        ob.name = name
        ob.data.name = name
        bpy.context.scene.collection.objects.link(ob)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if (v.index in left) != keep_left], context="VERTS")
        bm.to_mesh(ob.data)
        bm.free()
    bpy.data.objects.remove(src, do_unlink=True)


def build_rig(scene, arms, ready: dict) -> dict:
    """Кости ракетницы в арматуре рук. Frame — дочерняя правой кисти: посадка в руку задаётся здесь."""
    # посадка: в боевом хвате владельца средний палец ложится под скобу, спуск — под указательный
    gun_ready = Matrix.Translation(Vector((-0.1476, -0.3015, 1.6295)))
    grip = ready["hand_r"].inverted() @ gun_ready                    # ракетница в осях кисти
    hand_rest = arms.data.bones["hand.R"].matrix_local.copy()
    frame_rest = hand_rest @ grip
    bpy.context.view_layer.objects.active = arms
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arms.data.edit_bones

    def bone(name: str, parent: str, m: Matrix, length: float = 0.03) -> None:
        eb = ebs.new(name)
        eb.head, eb.tail = (0.0, 0.0, 0.0), (0.0, length, 0.0)
        eb.matrix = m
        eb.parent = ebs[parent]
        eb.use_deform = False

    bone("Frame", "hand.R", frame_rest, 0.04)
    bone("Barrel", "Frame", frame_rest @ Matrix.Translation(P(*HINGE)))
    bone("Hammer", "Frame", frame_rest @ Matrix.Translation(P(*HPIV)), 0.02)
    bone("Trigger", "Frame", frame_rest @ Matrix.Translation(P(*TPIV)), 0.02)
    bone("Latch", "Frame", frame_rest @ Matrix.Translation(P(-6.5, 4.0)), 0.015)
    bone("OldRound", "FPS_Root", frame_rest @ Matrix.Translation(P(BREECH, 0.0)), 0.02)
    bone("NewRound", "FPS_Root", frame_rest @ Matrix.Translation(P(BREECH, 0.0)), 0.02)
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    bpy.context.view_layer.update()

    def attach(ob, bone_name: str, local: Matrix) -> None:
        ob.parent = arms
        ob.parent_type = "BONE"
        ob.parent_bone = bone_name
        bpy.context.view_layer.update()
        ob.matrix_world = arms.matrix_world @ arms.pose.bones[bone_name].matrix @ local

    owner = {"Frame": "Frame", "Pins": "Frame", "GripPad_L": "Frame", "GripPad_R": "Frame", "GripScrews": "Frame",
             "BarrelLatch_L": "Latch", "BarrelLatch_R": "Latch", "Barrel": "Barrel", "Hammer": "Hammer", "Trigger": "Trigger"}
    pivots = {"Frame": Vector((0, 0, 0)), "Latch": P(-6.5, 4.0), "Barrel": P(*HINGE), "Hammer": P(*HPIV), "Trigger": P(*TPIV)}
    root = bpy.data.objects["FlareGun_Claude"]
    for name, bone_name in owner.items():
        ob = bpy.data.objects[name]
        local = Matrix.Translation(-pivots[bone_name]) @ ob.matrix_world          # корень ракетницы стоял в начале координат
        attach(ob, bone_name, local)
    bpy.data.objects.remove(root, do_unlink=True)
    for src, names in (("Flare_Red_Claude", ("LoadRoundRed", "OldRoundRed")), ("Flare_Green_Claude", ("LoadRoundGreen", "OldRoundGreen"))):
        base = bpy.data.objects[src]
        for name in names:
            ob = base.copy()
            ob.name = name
            scene.collection.objects.link(ob)
            attach(ob, "NewRound" if name.startswith("Load") else "OldRound", Matrix.Identity(4))
        bpy.data.objects.remove(base, do_unlink=True)
    for name in ("LoadRoundGreen", "OldRoundGreen"):                 # в Blender по умолчанию показан красный патрон
        bpy.data.objects[name].hide_viewport = True
        bpy.data.objects[name].hide_render = True
    # метки для игры: рама (оси оружия у рукоятки), прицельная линия по планке, дульный срез
    for name, p in (("WeaponFrame", Vector((0, 0, 0))), ("SightRear", P(0.0, 15.05)), ("SightFront", P(LEN - 6.5, 14.95)), ("Muzzle", P(LEN, 0.0))):
        old = bpy.data.objects.get(name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)
        e = bpy.data.objects.new(name, None)
        e.empty_display_size = 0.01
        scene.collection.objects.link(e)
        attach(e, "Frame", Matrix.Translation(p))
    old = bpy.data.objects.get("Chamber")
    if old:
        bpy.data.objects.remove(old, do_unlink=True)
    return {"grip": grip}


# ================================================================ позы пальцев

class Hands:
    """Позы пальцев через сгиб вокруг той оси, вокруг которой палец согнут в хвате владельца
    (у правой и левой руки оси костей разные — «сгиб вокруг X» правую ломает)."""

    def __init__(self, arms, ready: dict) -> None:
        self.arms = arms
        self.ready = {n: m.to_quaternion() for n, m in ready["basis"].items()}
        self.axis: dict = {}
        for n, q in self.ready.items():
            axis, angle = q.to_axis_angle()
            if angle > math.pi:
                axis, angle = -axis, math.tau - angle
            self.axis[n] = (axis.normalized(), angle)

    def scaled(self, bone: str, k: float) -> Quaternion:
        axis, angle = self.axis[bone]
        return Quaternion(axis, angle * k)

    def flex(self, bone: str, deg: float) -> Quaternion:
        """Сгиб кости на deg от её положения в хвате владельца (0 — как у него)."""
        axis, angle = self.axis[bone]
        return Quaternion(axis, angle + math.radians(deg))

    def pose(self, side: str, k: float = 1.0, add: dict | None = None, thumb: float | None = None) -> dict:
        """Поза кисти: хват владельца, умноженный на k; add — добавка сгиба по суставам пальцев {1: °, 2: °, 3: °}."""
        out = {}
        for n in (RIGHT if side == "R" else LEFT):
            if n.startswith("hand"):
                continue
            part = n.split(".")[0]
            idx = int(n.split(".")[1])
            if part == "thumb":
                out[n] = self.scaled(n, k if thumb is None else thumb)
            elif part == "palm":
                out[n] = self.scaled(n, k)
            else:
                axis, angle = self.axis[n]
                out[n] = Quaternion(axis, angle * k + math.radians((add or {}).get(idx, 0.0)))
        return out


def apply(arms, pose: dict) -> None:
    for n, q in pose.items():
        arms.pose.bones[n].rotation_quaternion = q


def set_world(arms, bone: str, m: Matrix) -> None:
    arms.pose.bones[bone].matrix = arms.matrix_world.inverted() @ m
    bpy.context.view_layer.update()


def world(arms, bone: str) -> Matrix:
    return arms.matrix_world @ arms.pose.bones[bone].matrix


def bvh_of(objects) -> BVHTree:
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objects:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        base = len(verts)
        verts += [ev.matrix_world @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def gap(arms, tree: BVHTree, bones: list) -> float:
    """Наименьшее расстояние от оси пальца до поверхности."""
    best = 1e9
    for n in bones:
        pb = arms.pose.bones[n]
        for t in (0.35, 0.7, 1.0):
            p = arms.matrix_world @ (pb.head + (pb.tail - pb.head) * t)
            loc, nrm, _i, dist = tree.find_nearest(p)
            if loc is None:
                continue
            best = min(best, dist)        # без знака: у далёкой точки «внутри/снаружи» по нормали ближайшей грани врёт
    return best


def wrap(arms, hands: Hands, pose: dict, side: str, tree: BVHTree, radius: dict, fingers=FINGERS, start: tuple = (1.0, 1.0, 1.0)) -> dict:
    """Дожать пальцы до поверхности: сустав за суставом от основания, пока палец не ляжет на предмет.
    Начинать с хвата владельца, не разгибая: разогнутые пальцы упираются в скобу и «садятся» на неё."""
    for finger in fingers:
        chain = [f"{finger}.{i:02d}.{side}" for i in (1, 2, 3)]
        angles = []
        base = {}
        for i, n in enumerate(chain):
            axis, angle = hands.axis[n]
            # основание: что уже задано в позе (у указательного оно довёрнуто к спуску) минус сгиб владельца
            base[n] = pose[n] @ Quaternion(axis, angle).inverted() if n in pose else Quaternion()
            angles.append(angle * start[i])
            pose[n] = base[n] @ Quaternion(axis, angles[i])
        apply(arms, pose)
        bpy.context.view_layer.update()
        r = radius[finger]
        for i, n in enumerate(chain):
            axis, _ = hands.axis[n]
            limit = math.radians((95, 115, 85)[i])
            while angles[i] < limit:
                if gap(arms, tree, chain[i:]) <= r:
                    break
                angles[i] += math.radians(1.5)
                pose[n] = base[n] @ Quaternion(axis, angles[i])
                arms.pose.bones[n].rotation_quaternion = pose[n]
                bpy.context.view_layer.update()
    return pose


def lower_index(arms, pose: dict, deg: float) -> None:
    """Указательный палец правой — ближе к среднему (на deg): поворот у основания вокруг оси «из тыльной стороны кисти»."""
    pb = arms.pose.bones["f_index.01.R"]
    head = arms.matrix_world @ pb.head
    tip0 = (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail).z
    axis = (arms.matrix_world @ arms.pose.bones["hand.R"].matrix).to_3x3() @ Vector((1.0, 0.0, 0.0))
    keep = pb.matrix.copy()
    for sign in (1.0, -1.0):
        m = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg) * sign, 4, axis.normalized()) @ Matrix.Translation(-head)
        pb.matrix = arms.matrix_world.inverted() @ m @ arms.matrix_world @ keep
        bpy.context.view_layer.update()
        if (arms.matrix_world @ arms.pose.bones["f_index.03.R"].tail).z < tip0:
            break
    pose["f_index.01.R"] = pb.rotation_quaternion.copy()


def press_thumb(arms, pose: dict, side: str, tree: BVHTree, radius: float = 0.009) -> dict:
    """Большой палец довести до поверхности поворотом у основания (в сторону ближайшей точки предмета)."""
    names = [f"thumb.{i:02d}.{side}" for i in (1, 2, 3)]
    for _ in range(40):
        if gap(arms, tree, names[1:]) <= radius:
            break
        pb = arms.pose.bones[names[0]]
        tip = arms.matrix_world @ arms.pose.bones[names[2]].tail
        loc, _n, _i, _d = tree.find_nearest(tip)
        head = arms.matrix_world @ pb.head
        axis = (tip - head).cross(loc - tip)
        if axis.length < 1e-9:
            break
        m = Matrix.Translation(head) @ Matrix.Rotation(math.radians(1.2), 4, axis.normalized()) @ Matrix.Translation(-head)
        pb.matrix = arms.matrix_world.inverted() @ m @ arms.matrix_world @ pb.matrix
        bpy.context.view_layer.update()
    for n in names:
        pose[n] = arms.pose.bones[n].rotation_quaternion.copy()
    return pose


# ================================================================ ключи

class Clip:
    def __init__(self, arms, name: str, length: int) -> None:
        self.arms, self.length = arms, length
        self.action = bpy.data.actions.new(name)
        self.action.use_fake_user = True
        ad = arms.animation_data or arms.animation_data_create()
        ad.action = self.action
        for pb in arms.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        self.last: dict = {}

    def key_matrix(self, bone: str, frame: float, m_world: Matrix) -> None:
        pb = self.arms.pose.bones[bone]
        bpy.context.scene.frame_set(int(frame))
        pb.matrix = self.arms.matrix_world.inverted() @ m_world
        q = pb.rotation_quaternion.copy()
        prev = self.last.get(bone)
        if prev is not None and prev.dot(q) < 0.0:                   # без переворота через «дальнюю» сторону
            q.negate()
            pb.rotation_quaternion = q
        self.last[bone] = q
        pb.keyframe_insert("location", frame=frame)
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def key_pose(self, frame: float, pose: dict) -> None:
        for n, q in pose.items():
            pb = self.arms.pose.bones[n]
            prev = self.last.get(n)
            q = q.copy()
            if prev is not None and prev.dot(q) < 0.0:
                q.negate()
            self.last[n] = q
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=frame)

    def key_angle(self, bone: str, frame: float, deg: float, axis: str = "X") -> None:
        pb = self.arms.pose.bones[bone]
        pb.rotation_quaternion = Quaternion({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[axis], math.radians(deg))
        pb.keyframe_insert("rotation_quaternion", frame=frame)

    def key_loc(self, bone: str, frame: float, loc: Vector) -> None:
        pb = self.arms.pose.bones[bone]
        pb.location = loc
        pb.keyframe_insert("location", frame=frame)

    def finish(self, linear: tuple = ()) -> None:
        for fc in fcurves(self.action):
            bone = fc.data_path.split('"')[1] if '"' in fc.data_path else ""
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if bone in linear else "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


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


def build() -> None:
    scene, arms = append_scene()
    ready = read_ready(scene, arms)
    split_arms(arms)
    rig = build_rig(scene, arms, ready)
    grip = rig["grip"]
    hands = Hands(arms, ready)
    gun_meshes = [bpy.data.objects[n] for n in ("Frame", "Barrel", "Trigger", "GripPad_L", "GripPad_R", "Hammer")]
    radius = {"f_index": 0.0085, "f_middle": 0.009, "f_ring": 0.0085, "f_pinky": 0.0075}

    # ---- хват правой: поза владельца, пальцы дожаты до тонкой рукоятки
    set_world(arms, "ik_hand.R", ready["hand_r"])
    r_grip = hands.pose("R")
    apply(arms, r_grip)
    bpy.context.view_layer.update()
    tree = bvh_of(gun_meshes)
    lower_index(arms, r_grip, 10.0)
    r_grip = wrap(arms, hands, r_grip, "R", tree, radius)
    r_grip = press_thumb(arms, r_grip, "R", tree)
    print("ANIM right grip fitted; gaps", {f: round(gap(arms, tree, [f"{f}.{i:02d}.R" for i in (1, 2, 3)]) * 1000, 1) for f in FINGERS}, flush=True)

    # ---- позы левой: пальцы дожаты по настоящей поверхности — по патрону и по стволу
    barrel_local = lambda u, v, x=0.0: P(u, v, x) - P(*HINGE)       # точка ствола в осях его кости
    grab = Matrix(((0.0, -1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (-1.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 1.0)))   # кисть в осях ствола: ладонь вниз, пальцы вправо
    grab.translation = barrel_local(LEN - 30.0, R_OUT + 3.0) + Vector((0.05, 0.0, 0.018))
    in_hand = Matrix.Translation(Vector((0.03, 0.078, 0.012))) @ rot("Z", 180.0)             # патрон в осях кисти: вдоль пальцев
    regrip = Matrix.Translation(Vector((0.03, 0.1, 0.012))) @ rot("Z", 180.0)                # перехват: пальцы у донца
    l_open = hands.pose("L", 0.35, thumb=0.4)
    set_world(arms, "ik_hand.L", world(arms, "Barrel") @ grab)
    l_wrap = hands.pose("L", 0.7)
    apply(arms, l_wrap)
    bpy.context.view_layer.update()
    tree_l = bvh_of([bpy.data.objects["Barrel"]])
    l_wrap = wrap(arms, hands, l_wrap, "L", tree_l, radius)
    l_wrap = press_thumb(arms, l_wrap, "L", tree_l)
    held = Matrix.Translation(Vector((0.12, -0.3, 1.6)))
    set_world(arms, "ik_hand.L", held)
    set_world(arms, "NewRound", held @ in_hand)
    l_pinch = hands.pose("L", 0.6, thumb=0.9)
    for f, extra in (("f_ring", 40.0), ("f_pinky", 48.0)):
        for k in (1, 2, 3):
            l_pinch[f"{f}.{k:02d}.L"] = hands.flex(f"{f}.{k:02d}.L", extra * (0.7 if k == 3 else 1.0))
    apply(arms, l_pinch)
    bpy.context.view_layer.update()
    tree_l = bvh_of([bpy.data.objects["LoadRoundRed"]])
    l_pinch = wrap(arms, hands, l_pinch, "L", tree_l, {"f_index": 0.008, "f_middle": 0.0085}, fingers=("f_index", "f_middle"))
    l_pinch = press_thumb(arms, l_pinch, "L", tree_l, 0.0085)
    l_push = dict(l_pinch)
    for k, a in ((1, -24.0), (2, -26.0), (3, -14.0)):                 # указательный выпрямлен: дослать патрон
        l_push[f"f_index.{k:02d}.L"] = hands.flex(f"f_index.{k:02d}.L", a)
    for pb in arms.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()

    hand_of_gun = grip.inverted()                                    # кисть в осях ракетницы
    idle = gun_pose((-0.1, -0.31, 1.69), pitch=2.0, yaw=3.0, roll=6.0)
    park = Matrix.Translation(Vector((0.24, -0.1, 1.33))) @ ready_rot(arms, ready, "ik_hand.L")
    def right(clip: Clip, frame: float, g: Matrix) -> None:
        clip.key_matrix("ik_hand.R", frame, g @ hand_of_gun)

    def static_parts(clip: Clip, frame: float) -> None:
        clip.key_angle("Barrel", frame, 0.0)
        clip.key_angle("Hammer", frame, 0.0)
        clip.key_angle("Trigger", frame, 0.0)
        clip.key_angle("Latch", frame, 0.0)
        clip.key_matrix("ik_hand.L", frame, park)
        clip.key_pose(frame, l_open)
        clip.key_pose(frame, r_grip)

    def hide_rounds(clip: Clip, frames: tuple) -> None:
        far = Matrix.Translation(Vector((0.0, 0.3, 0.9)))
        for f in frames:
            clip.key_matrix("OldRound", f, far)
            clip.key_matrix("NewRound", f, far)

    # ---- стойка, достать, убрать, выстрел
    for name in ("Flare_Claude_idle", "Flare_Claude_idle_empty"):
        clip = Clip(arms, name, 30)
        for f in (1, 30):
            right(clip, f, idle)
            static_parts(clip, f)
        hide_rounds(clip, (1, 30))
        clip.finish()
    low = gun_pose((-0.16, -0.2, 1.36), pitch=-38.0, yaw=8.0, roll=14.0)
    for name, order in (("Flare_Claude_draw", (low, idle)), ("Flare_Claude_holster", (idle, low))):
        clip = Clip(arms, name, 24)
        right(clip, 1, order[0])
        mid = gun_pose((-0.13, -0.3, 1.57), pitch=-10.0 if name.endswith("draw") else -14.0, yaw=4.0, roll=9.0)
        right(clip, 13, mid)
        right(clip, 22 if name.endswith("draw") else 24, order[1])
        right(clip, 24, order[1])
        for f in (1, 24):
            static_parts(clip, f)
        hide_rounds(clip, (1, 24))
        clip.finish()
    clip = Clip(arms, "Flare_Claude_fire", 24)
    right(clip, 1, idle)
    right(clip, 5, idle)
    right(clip, 7, idle @ Matrix.Translation(Vector((0.0, 0.022, 0.008))) @ rot("X", -13.0))      # отдача: назад и дулом вверх
    right(clip, 10, idle @ Matrix.Translation(Vector((0.0, 0.012, 0.006))) @ rot("X", -7.0))
    right(clip, 16, idle @ Matrix.Translation(Vector((0.0, -0.003, -0.002))) @ rot("X", 1.5))
    right(clip, 24, idle)
    for f in (1, 24):
        static_parts(clip, f)
    for f, deg in ((1, 0.0), (5, -COCK_DEG * 0.85), (6, 0.0), (24, 0.0)):                        # курок оттянут спуском и сорвался
        clip.key_angle("Hammer", f, deg)
    for f, deg in ((1, 0.0), (5, 12.0), (9, 12.0), (15, 0.0), (24, 0.0)):
        clip.key_angle("Trigger", f, deg)
    hide_rounds(clip, (1, 24))
    clip.finish()

    # ---- перезарядка
    for name in ("Flare_Claude_reload_empty", "Flare_Claude_reload_live"):
        clip = Clip(arms, name, RELOAD_LEN)
        pre = gun_pose((-0.06, -0.33, 1.7), pitch=6.0, yaw=12.0, roll=14.0)
        opened = gun_pose((-0.06, -0.325, 1.705), pitch=12.0, yaw=12.0, roll=14.0)
        dump = gun_pose((-0.115, -0.3, 1.715), pitch=82.0, yaw=14.0, roll=22.0)
        # заряжание: казённая часть развёрнута к левой руке (дуло вправо), чтобы предплечье не закрывало ракетницу
        load = gun_pose((-0.045, -0.35, 1.69), pitch=14.0, yaw=-28.0, roll=24.0)
        swing_0 = gun_pose((-0.09, -0.335, 1.665), pitch=-8.0, yaw=6.0, roll=8.0)        # замах: дуло вниз
        swing_1 = gun_pose((-0.09, -0.33, 1.705), pitch=24.0, yaw=6.0, roll=8.0)         # взмах: дуло вверх, ствол догоняет раму
        # ось ствола в положении «вытряхнуть»: от дула к казне — вниз
        axis_dump = (dump @ rot("X", OPEN_DEG)).to_3x3() @ Vector((0.0, 1.0, 0.0))
        gun_keys = [(1, idle), (10, pre), (20, pre), (29, opened), (36, opened), (46, dump)]
        for f, k in ((48, 0.0), (51, 1.0), (54, 0.1), (55, 0.1), (58, 1.0), (61, 0.1), (62, 0.25), (64, 0.0)):   # три встряхивания
            gun_keys.append((f, Matrix.Translation(axis_dump * 0.035 * k) @ dump))
        gun_keys += [(76, load), (114, load), (121, swing_0), (125, swing_1),
                     (130, gun_pose((-0.095, -0.325, 1.697), pitch=8.0, yaw=5.0, roll=7.0)), (150, idle)]
        for f, g in gun_keys:
            right(clip, f, g)
        for f, deg in ((1, 0.0), (20, 0.0), (29, OPEN_DEG), (122, OPEN_DEG), (124, OPEN_DEG * 0.85), (126, 0.0), (150, 0.0)):
            clip.key_angle("Barrel", f, deg)
        for f, deg in ((1, 0.0), (16, 0.0), (19, 10.0), (24, 10.0), (28, 0.0), (124, 0.0), (125, 8.0), (127, 0.0), (150, 0.0)):
            clip.key_angle("Latch", f, deg)
        for f in (1, 150):
            clip.key_angle("Hammer", f, 0.0)
            clip.key_angle("Trigger", f, 0.0)
            clip.key_pose(f, r_grip)
        # локоть правой: в стойке — вниз-вправо, при вытряхивании — под кистью
        pole_rest = Vector((0.0, 0.0, 0.0))
        for f, shift in ((1, pole_rest), (36, pole_rest), (46, Vector((0.14, -0.3, -0.05))), (64, Vector((0.14, -0.3, -0.05))), (76, pole_rest), (150, pole_rest)):
            clip.key_loc("pole.R", f, shift)
        clip.finish()
        scene.frame_set(1)
        bpy.context.view_layer.update()

        # -- второй проход: то, что зависит от ствола и рук в каждом кадре
        above = grab.copy()
        above.translation = grab.translation + Vector((0.03, 0.0, 0.05))
        seat = Matrix.Translation(barrel_local(BREECH, 0.0))

        def barrel_at(f: int) -> Matrix:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            return world(arms, "Barrel")

        left_keys: list = [(1, park, l_open), (4, park, l_open)]
        b10 = barrel_at(10)
        left_keys.append((11, b10 @ above, l_open))
        for f in range(17, 31):                                      # левая на стволе: идёт вместе с ним
            left_keys.append((f, barrel_at(f) @ grab, l_wrap))
        b30 = barrel_at(34)
        left_keys.append((34, b30 @ above, l_open))
        left_keys.append((42, park, l_open))
        left_keys.append((66, park, l_pinch))
        # новый патрон: приносят снизу-слева, подводят по оси ствола, вставляют
        b_load = barrel_at(90)
        start = Matrix.Translation(Vector((0.17, -0.2, 1.4))) @ b_load.to_quaternion().to_matrix().to_4x4() @ rot("Z", -25.0) @ rot("X", 30.0)
        approach = b_load @ seat @ Matrix.Translation(Vector((0.004, 0.105, 0.012)))
        mouth = b_load @ seat @ Matrix.Translation(Vector((0.0, 0.066, 0.0)))
        half = b_load @ seat @ Matrix.Translation(Vector((0.0, 0.03, 0.0)))
        near = b_load @ seat @ Matrix.Translation(Vector((0.0, 0.012, 0.0)))
        home = b_load @ seat
        round_keys = [(70, start, in_hand), (84, approach, in_hand), (92, mouth, in_hand), (100, half, in_hand), (104, near, regrip), (108, home, regrip)]
        for f, m, hold in round_keys:
            clip.key_matrix("NewRound", f, m)
            left_keys.append((f, m @ hold.inverted(), l_push if f >= 104 else l_pinch))
        for f in range(109, RELOAD_LEN + 1):                         # патрон в патроннике — идёт со стволом
            clip.key_matrix("NewRound", f, barrel_at(f) @ seat)
        clip.key_matrix("NewRound", 1, start)
        clip.key_matrix("NewRound", 69, start)
        back = home @ regrip.inverted() @ Matrix.Translation(Vector((-0.02, -0.03, 0.0)))
        left_keys += [(112, back, l_open), (120, park, l_open), (RELOAD_LEN, park, l_open)]
        for f, m, pose in left_keys:
            clip.key_matrix("ik_hand.L", f, m)
            clip.key_pose(f, pose)
        # стреляная гильза: в патроннике, на встряхиваниях выходит и падает
        g = Vector((0.0, 0.0, -9.81))
        free_at, free_m, vel = None, None, None
        for f in range(1, RELOAD_LEN + 1):
            if f <= 50:
                slide = 0.0
            elif f <= 54:
                slide = 0.022 * smooth((f - 50) / 3.0)
            elif f <= 58:
                slide = 0.022 + 0.05 * smooth((f - 55) / 3.0)
            else:
                slide = None
            if slide is not None:
                m = barrel_at(f) @ seat @ Matrix.Translation(Vector((0.0, slide, 0.0)))
                if f == 58:
                    prev = barrel_at(57) @ seat @ Matrix.Translation(Vector((0.0, 0.022 + 0.05 * smooth(2.0 / 3.0), 0.0)))
                    free_at, free_m = f, m.copy()
                    vel = (m.translation - prev.translation) * FPS
            else:
                t = (f - free_at) / FPS
                m = Matrix.Translation(free_m.translation + vel * t + 0.5 * g * t * t) @ free_m.to_quaternion().to_matrix().to_4x4() @ rot("X", -260.0 * t)
            clip.key_matrix("OldRound", f, m)
        clip.finish(linear=("OldRound",))

    # ---- сцена для просмотра
    ad = arms.animation_data
    ad.action = bpy.data.actions["Flare_Claude_reload_empty"]
    scene.frame_start, scene.frame_end = 1, RELOAD_LEN
    marks = dict(EVENTS)
    marks.update({"levaya_na_stvole": 17, "levaya_ushla": 42, "patron_podveden": 92, "perehvat": 104, "v_stoike": 150})
    for name, f in marks.items():
        scene.timeline_markers.new(name, frame=f)
    arms["events"] = json.dumps(EVENTS)
    arms["round_windows"] = json.dumps(ROUND_WINDOWS)
    arms["left_hand_windows"] = json.dumps(LEFT_WINDOWS)
    sun = bpy.data.objects.new("Свет", bpy.data.lights.new("Свет", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (math.radians(50), 0, math.radians(120))
    scene.collection.objects.link(sun)
    world_data = bpy.data.worlds.new("Фон")
    world_data.use_nodes = True
    world_data.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.32, 0.35, 1.0)
    scene.world = world_data
    scene.frame_set(1)
    ANIM.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(ANIM))
    print("ANIM build done; actions", sorted(a.name for a in bpy.data.actions if a.name.startswith("Flare_Claude")), flush=True)


def ready_rot(arms, ready: dict, bone: str) -> Matrix:
    """Ориентация кости в боевом хвате владельца (без положения) — исходная для «левая в стороне»."""
    pb = arms.pose.bones[bone]
    keep = pb.matrix_basis.copy()
    pb.matrix_basis = ready["basis"][bone]
    bpy.context.view_layer.update()
    m = (arms.matrix_world @ pb.matrix).to_quaternion().to_matrix().to_4x4()
    pb.matrix_basis = keep
    bpy.context.view_layer.update()
    return m


# ================================================================ проверочные кадры

def stills() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(ANIM))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 1280, 720
    scene.render.image_settings.file_format = "PNG"
    fps_cam = bpy.data.objects["FPS • Camera"]
    side = bpy.data.objects.new("Сбоку", bpy.data.cameras.new("Сбоку"))
    side.data.lens = 50
    side.data.clip_start = 0.01
    scene.collection.objects.link(side)
    STILLS.mkdir(parents=True, exist_ok=True)
    only = [s for s in os.environ.get("FLARE_SHOTS", "").split(",") if s]
    jobs = {"Flare_Claude_idle": [1], "Flare_Claude_fire": [5, 7], "Flare_Claude_draw": [8],
            "Flare_Claude_reload_empty": [10, 18, 24, 29, 38, 46, 51, 58, 62, 76, 84, 92, 100, 106, 112, 121, 125, 128, 140]}
    for action, frames in jobs.items():
        if only and not any(action.endswith(s) for s in only):
            continue
        arms.animation_data.action = bpy.data.actions[action]
        short = action.replace("Flare_Claude_", "")
        for f in frames:
            scene.frame_set(f)
            bpy.context.view_layer.update()
            focus = arms.matrix_world @ arms.pose.bones["Frame"].head + Vector((0.0, 0.0, 0.03))
            views = [("glaz", fps_cam, None), ("sboku", side, Vector((-0.6, 0.16, 0.14)))]
            if short == "idle":
                views += [("sleva", side, Vector((0.4, -0.05, 0.06))), ("sverhu", side, Vector((-0.03, 0.08, 0.42))), ("snizu", side, Vector((-0.12, -0.1, -0.38)))]
            for view, cam, off in views:
                if cam is side:
                    cam.location = focus + off
                    z = off.normalized()
                    x = Vector((0, 0, 1)).cross(z).normalized()
                    m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
                    m.translation = cam.location
                    cam.matrix_world = m
                scene.camera = cam
                scene.render.filepath = str(STILLS / f"{short}_{f:03d}_{view}.png")
                bpy.ops.render.render(write_still=True)
    print("ANIM stills done", flush=True)


CLIPS = {"idle": ("Flare_Claude_idle", 30), "idle_empty": ("Flare_Claude_idle_empty", 30), "draw": ("Flare_Claude_draw", 24),
         "holster": ("Flare_Claude_holster", 24), "fire": ("Flare_Claude_fire", 24),
         "reload_live": ("Flare_Claude_reload_live", RELOAD_LEN), "reload_empty": ("Flare_Claude_reload_empty", RELOAD_LEN)}


def export() -> None:
    """Клипы с учётом IK → запечённые ключи всех костей, начало сцены — в камере, GLB с NLA-дорожками по именам клипов."""
    bpy.ops.wm.open_mainfile(filepath=str(ANIM))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    cam = bpy.data.objects["FPS • Camera"]
    ad = arms.animation_data
    baked: dict = {}
    for clip, (action, length) in CLIPS.items():
        ad.action = bpy.data.actions[action]
        for pb in arms.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        data: dict = {}
        for f in range(1, length + 1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            for pb in arms.pose.bones:
                data.setdefault(pb.name, []).append(arms.convert_space(pose_bone=pb, matrix=pb.matrix, from_space="POSE", to_space="LOCAL").copy())
        baked[clip] = data
        print("ANIM sampled", clip, length, flush=True)
    ad.action = None
    for pb in arms.pose.bones:
        for c in list(pb.constraints):
            pb.constraints.remove(c)
    for clip, data in baked.items():
        act = bpy.data.actions.new("VM_" + clip)
        ad.action = act
        for pb in arms.pose.bones:
            for i, m in enumerate(data[pb.name]):
                loc, q, scl = m.decompose()
                pb.location, pb.rotation_quaternion, pb.scale = loc, q, scl
                for path in ("location", "rotation_quaternion", "scale"):
                    pb.keyframe_insert(path, frame=i + 1)
        for fc in fcurves(act):
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR"
        ad.action = None
        track = ad.nla_tracks.new()
        track.name = clip
        track.strips.new(clip, 1, act)
    for pb in arms.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    scene.frame_set(1)
    bpy.context.view_layer.update()
    # объёмы деталей в осях их костей — игре для «оружие упёрлось в стену»
    clearance: dict = {}
    for bone, names in (("Frame", ("Frame", "GripPad_L", "GripPad_R")), ("Barrel", ("Barrel",)), ("Hammer", ("Hammer",)), ("Trigger", ("Trigger",)), ("Latch", ("BarrelLatch_L", "BarrelLatch_R"))):
        inv = (arms.matrix_world @ arms.pose.bones[bone].matrix).inverted()
        pts = [inv @ (bpy.data.objects[n].matrix_world @ v.co) for n in names for v in bpy.data.objects[n].data.vertices]
        clearance[bone] = {"min": [min(q[i] for q in pts) for i in range(3)], "max": [max(q[i] for q in pts) for i in range(3)]}
    for ob in bpy.data.objects:
        ob.hide_viewport = False
        ob.hide_render = False
        ob.hide_set(False)
    for img in bpy.data.images:                                      # перчатки: 1024 в игре достаточно
        if img.name.lower().startswith("arm") and img.size[0] > 1024:
            img.scale(1024, 1024)
    to_cam = Matrix.Rotation(math.radians(90.0), 4, "X") @ cam.matrix_world.inverted()      # камера — в начале, взгляд по +Y Blender
    arms.matrix_world = to_cam @ arms.matrix_world
    for name in ("FPS • Camera", "Свет"):
        ob = bpy.data.objects.get(name)
        if ob:
            bpy.data.objects.remove(ob, do_unlink=True)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "flare_gun_claude_viewmodel.glb"
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB", export_yup=True, export_animations=True,
                              export_animation_mode="NLA_TRACKS", export_skins=True, export_all_influences=True,
                              export_def_bones=False, export_force_sampling=True, export_materials="EXPORT",
                              export_image_format="AUTO", export_apply=False, export_cameras=False, export_lights=False)
    config = {"scene": "res://assets/models/weapons/flare_gun_claude/flare_gun_claude_viewmodel.glb", "fps": FPS, "mechanism": "break_action",
              "clips": {"idle": "idle", "idle_empty": "idle_empty", "draw": "draw", "reload": "reload_live", "reload_empty": "reload_empty",
                        "shot": "fire", "holster": "holster"},
              "ads_z": 0.32, "hip_offset": [0, 0, 0], "round_windows": ROUND_WINDOWS, "left_hand_windows": LEFT_WINDOWS, "events": EVENTS,
              "clearance_parts": clearance, "reload_sec": RELOAD_LEN / FPS, "barrel_open_deg": OPEN_DEG, "hammer_cocked_deg": -COCK_DEG}
    (OUT / "flare_gun_claude_viewmodel.json").write_text(json.dumps(config, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ANIM export done", round(path.stat().st_size / 1e6, 1), "MB", flush=True)


if MODE == "stills":
    stills()
elif MODE == "export":
    export()
else:
    build()
