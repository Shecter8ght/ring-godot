"""Мосин 1891/30 ПУ от первого лица: руки владельца, хват, стойки, клипы затвора и заряжания.

Руки — FPS_ArmsRig из VERAS54_Reload_Full_v05.blend (копия; оригинал не трогается), хват — боевой хват владельца на
ВЕРАСе (действие VERAS54_Grip_Manual_v02): правая кисть с пистолетной рукоятки ВЕРАСа переносится на шейку ложи
(поворот вперёд на GRIP_TILT — прямая шейка лежит в кулаке наискосок), левая — с цевья ВЕРАСа под цевьё Мосина перед
магазином; пальцы дожимаются до дерева по сетке перчатки. Мосин — игровая сетка v03
_asset_src/mosin_pu_game/fp/lp/Mosin_Game_export.blend (оси до перевода glTF: дуло −Y, верх +Z, правая сторона −X,
начало — середина шейки ложи).

Кости винтовки в арматуре рук: Frame (под FPS_Root, несёт винтовку; цели кистей ik_hand.R / ik_hand.L — её дочерние),
Bolt (ход назад по +Y кости, 0…BOLT_TRAVEL), Bolt_Rotor (поворот вокруг Y кости, +90° — рукоять вверх), Bolt_Cocking
(курок: назад на COCK_TRAVEL при подъёме рукояти, остаётся взведённым), Interrupter (отсечка-отражатель: в паз личинки
у конца хода), Trigger, Follower (подаватель), RearSight_Leaf / RearSight_Slider, Scope (кронштейн с прицелом: игра
прячет, когда прицел снят; основание на коробке — на Frame), патроны RoundChamber, Round_1…Round_5 (места в магазине
сверху вниз), RoundHand (патрон в пальцах при заряжании), Case (стреляная гильза).

Стойки — как у ПМ (решения владельца 2026-10-14): по умолчанию наискосок влево-вниз (CARRY), от бедра (READY),
прицел через ПУ (ADS): глаз на оси прицела за окуляром на EYE_RELIEF. Владелец правит позы в Blender.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/mosin_pu/animate_mosin.py -- grip|clips|stills [стойки|клипы] [out=<папка>]
  grip   → <библиотека>/models/07_Анимации/Mosin_PU_FPS_Grip_v01.blend (действие Mosin_Stances, хват без ключей)
  clips  → <библиотека>/models/07_Анимации/Mosin_PU_FPS_Clips_v01.blend (клипы от хвата в файле grip) + clips.json
  stills [carry|ready|ads …] [clip=<имя>:<кадр>,…] out=<папка> → кадры для проверки (глазами, справа, слева, снизу, спереди)
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src/mosin_pu_game"
LIB = Path(r"E:\Models Blender\WEAPONS\Мосин — винтовка и узлы\models\07_Анимации")
ARMS_FILE = Path(r"E:\Models Blender\WEAPONS\ВЕРАС-54 — модель и обвесы\ВЕРАС-54\Игровая версия\Перезарядка v01 (Claude)\VERAS54_Reload_Full_v05.blend")
GUN_FILE = SRC / "fp/lp/Mosin_Game_export.blend"
GRIP_FILE = LIB / "Mosin_PU_FPS_Grip_v01.blend"
CLIPS_FILE = LIB / "Mosin_PU_FPS_Clips_v01.blend"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = ARGS[0] if ARGS else "grip"
FPS = 30
CAM = Vector((0.0, 0.02, 1.8))
EYE_RELIEF = 0.075                   # глаз за окуляром ПУ (вынос зрачка ≈ 7–8 см)

# Хват владельца на ВЕРАСе (кадр 1 его действия, work: probe_veras_grip.py): середина сечения пистолетной рукоятки на
# высоте среднего пальца и низ цевья под средним пальцем левой. ВЕРАС в этой позе стоит ровно (ствол по −Y).
VERAS_GRIP = Vector((-0.140, -0.2755, 1.600))
VERAS_FORE = Vector((-0.140, -0.638, 1.671))
# Куда это ложится на Мосине (оси винтовки): шейка (сечение 35 × 49 мм — как рукоятка ВЕРАСа 34 × 52) и низ цевья
# перед магазином (коробка кончается у y −0,23, кольцо ложи — у −0,42). Точка на шейке — на 20 мм вперёд (к спуску),
# на 6 мм вправо и на 11 мм ниже её середины: так ладонь у правого бока, а не на верху шейки.
WRIST = Vector((-0.006, -0.020, -0.008))
FORE = Vector((0.0, -0.400, 0.0236))
# Прямая шейка поднимается к коробке под ~20°, рукоятка ВЕРАСа — под 75°: кисть поворачивается вперёд не на всю
# разницу, а на 25° — линия костяшек ложится на шейку наискосок, запястье остаётся за шейкой, а не над гребнем
# приклада (при 40° предплечье опускалось на гребень сверху).
GRIP_TILT = 25.0
# Вокруг оси винтовки — ладонью к правому боку шейки (без этого кисть ложилась на верх шейки).
GRIP_ROLL = -15.0
# Приклад за шейкой опускается и расширяется (у ВЕРАСа за рукояткой — тонкая трубка на высоте ствола): запястье и
# предплечье уходят вправо-назад мимо приклада, кисть повёрнута вокруг вертикали (иначе пятка ладони — в прикладе).
GRIP_YAW = 18.0

RIGHT = ["hand.R"] + [f"{f}.{i:02d}.R" for f in ("f_index", "f_middle", "f_ring", "f_pinky", "thumb") for i in (1, 2, 3)] + [f"palm.{i:02d}.R" for i in (1, 2, 3, 4)]
LEFT = [n[:-1] + "L" for n in RIGHT]
FINGERS = ("f_index", "f_middle", "f_ring", "f_pinky")

# Механика (tools/mosin_pu/build_rifle.py, asset-state.md): оси экспорта, метры
BORE_Z = 0.0578                       # ось канала над началом
BREECH_Y = -0.24                      # торец ствола / чашечка личинки (пустышка Bolt)
BOLT_TRAVEL = 0.088                   # ход затвора до упора
BOLT_OPEN = 90.0                      # поворот стебля рукоятью вверх
COCK_TRAVEL = 0.0095                  # курок отходит назад при подъёме рукояти
EJECTOR_IN, EJECTOR_FROM = 0.0028, 0.0564   # отсечка-отражатель: на сколько входит, с какого хода затвора (за 2 мм)
EJECT_AT = 0.0872                     # гильза выбита (ход 87,2 из 88)
# Патроны в магазине: однорядный столбик под окном, закраина верхнего — перед закраиной нижнего; верхний лежит на
# подавателе (пустой магазин: верх подавателя на 12,3 мм ниже оси канала), закраина — сразу перед торцом отведённой
# личинки, чтобы её захватить.
ROUND_R = 0.0062                      # радиус гильзы у донца
SLOT_PITCH = 0.0120                   # шаг столбика
SLOT_STAGGER = 0.0018                 # нижний патрон — на столько дальше назад
SLOT1 = Vector((0.0, BREECH_Y + 0.0865, BORE_Z - 0.0123 + ROUND_R))
CHAMBER = Vector((0.0, BREECH_Y + 0.0002, BORE_Z))
SLOTS = 5

# Узел игровой модели → кость (меши лежат под пустышками деталей)
PART_BONE = {"Frame": "Frame", "Bolt": "Bolt", "Bolt_Rotor": "Bolt_Rotor", "Bolt_Cocking": "Bolt_Cocking",
             "Interrupter": "Interrupter", "Trigger": "Trigger", "Follower": "Follower", "RearSight_Leaf": "RearSight_Leaf",
             "RearSight_Slider": "RearSight_Slider", "Mount_Base": "Frame", "Mount_Bracket": "Scope", "Scope": "Scope"}
MARKERS = {"Muzzle": "Frame", "SightFront": "Frame", "SightRear": "RearSight_Leaf", "ScopeEye": "Scope", "ScopeFront": "Scope"}
ROUND_BONES = ["RoundChamber"] + [f"Round_{k}" for k in range(1, SLOTS + 1)] + ["RoundHand"]
SCALED = tuple(ROUND_BONES) + ("Case",)
HIDDEN = Matrix.Scale(1e-4, 4)       # спрятанная кость патрона (нулевой масштаб ломает разложение матрицы)


def rot(axis: str, deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 4, axis)


def gun_pose(pos: tuple, pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Matrix:
    """Положение винтовки (начало — шейка) в мире: pitch — дуло вверх, yaw — дуло влево, roll — верх влево (градусы)."""
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


def slot(k: int) -> Vector:
    """Донце патрона на k-м месте магазина (1 — верхний)."""
    return SLOT1 + Vector((0.0, SLOT_STAGGER * (k - 1), -SLOT_PITCH * (k - 1)))


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
        dst2.objects = [n for n in src.objects if "_LOD1" not in n and not n.startswith("Col_")]
    for ob in dst2.objects:
        if ob is not None:
            scene.collection.objects.link(ob)
    arms = bpy.data.objects["FPS_ArmsRig"]
    arms.animation_data_clear()
    for pb in arms.pose.bones:
        pb.rotation_mode = "QUATERNION"
    scene.camera = bpy.data.objects["FPS • Camera"]
    bpy.context.view_layer.update()
    return scene, arms


def read_ready(scene, arms) -> dict:
    """Боевой хват владельца на ВЕРАСе (его действие, кадр 1): базисы всех костей и обе кисти в мире."""
    act = bpy.data.actions["VERAS54_Grip_Manual_v02"]
    act.use_fake_user = True                              # клипы читают из него оси сгиба пальцев
    ad = arms.animation_data_create()
    ad.action = act
    if act.slots:
        ad.action_slot = act.slots[0]
    scene.frame_set(1)
    bpy.context.view_layer.update()
    ready = {pb.name: pb.matrix_basis.copy() for pb in arms.pose.bones}
    hand_r = (arms.matrix_world @ arms.pose.bones["hand.R"].matrix).copy()
    hand_l = (arms.matrix_world @ arms.pose.bones["hand.L"].matrix).copy()
    ad.action = None
    for pb in arms.pose.bones:
        pb.matrix_basis = ready[pb.name] if pb.name in BODY else Matrix.Identity(4)
    bpy.context.view_layer.update()
    return {"basis": ready, "hand_r": hand_r, "hand_l": hand_l}


# Кости тела в хвате владельца: он вывел левое плечо вперёд (upper_arm.L) и развёл локти (pole) — без этого левая
# не дотягивается до цевья длинной винтовки. В клипах эти кости стоят как у него (ключи на краях клипа).
BODY = ("upper_arm.L", "upper_arm.R", "pole.L", "pole.R")


def hands_on_rifle(ready: dict) -> tuple:
    """Кисти владельца в осях Мосина: правая — с рукоятки ВЕРАСа на шейку (поворот вперёд на GRIP_TILT вокруг
    середины рукоятки), левая — с цевья ВЕРАСа под цевьё Мосина (сдвиг)."""
    r = Matrix.Translation(WRIST) @ rot("Y", GRIP_ROLL) @ rot("Z", GRIP_YAW) @ rot("X", GRIP_TILT) @ Matrix.Translation(-VERAS_GRIP) @ ready["hand_r"]
    l = Matrix.Translation(FORE - VERAS_FORE) @ ready["hand_l"]
    return r, l


def local_of(name: str) -> Matrix:
    return bpy.data.objects["Mosin_PU"].matrix_world.inverted() @ bpy.data.objects[name].matrix_world


def build_rig(scene, arms, g_rest: Matrix) -> None:
    """Кости винтовки в арматуре рук: Frame под FPS_Root (покой — стойка g_rest), детали — её дочерние в своих
    точках; цели кистей ik_hand.R / ik_hand.L — дочерние Frame. Меши пересаживаются на кости с сохранением мировых
    матриц; патроны — копии сетки патрона на своих костях."""
    at = {k: local_of(k).translation.copy() for k in ("Bolt", "Interrupter", "Trigger", "Follower", "RearSight_Leaf",
                                                      "RearSight_Slider", "Scope")}
    frame_rest = arms.matrix_world.inverted() @ g_rest
    bpy.context.view_layer.objects.active = arms
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = arms.data.edit_bones

    def bone(name: str, parent: str, local: Vector, length: float = 0.015) -> None:
        eb = ebs.new(name)
        eb.head, eb.tail = (0.0, 0.0, 0.0), (0.0, length, 0.0)
        eb.matrix = frame_rest @ Matrix.Translation(local)
        eb.parent = ebs[parent]
        eb.use_deform = False

    bone("Frame", "FPS_Root", Vector(), 0.06)
    bone("Bolt", "Frame", at["Bolt"])
    bone("Bolt_Rotor", "Bolt", at["Bolt"], 0.012)
    bone("Bolt_Cocking", "Bolt", at["Bolt"], 0.01)
    for name in ("Interrupter", "Trigger", "Follower", "RearSight_Leaf", "Scope"):
        bone(name, "Frame", at[name])
    bone("RearSight_Slider", "RearSight_Leaf", at["RearSight_Slider"], 0.01)
    bone("RoundChamber", "Frame", CHAMBER, 0.01)
    for k in range(1, SLOTS + 1):
        bone(f"Round_{k}", "Frame", slot(k), 0.01)
    bone("RoundHand", "Frame", slot(1), 0.01)
    bone("Case", "Frame", CHAMBER, 0.01)
    for n in ("ik_hand.R", "ik_hand.L"):
        ebs[n].parent = ebs["Frame"]
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

    root = bpy.data.objects["Mosin_PU"]
    root.matrix_world = g_rest
    bpy.context.view_layer.update()
    for ob in [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("FPS_")
               and o.name not in ("Round_Mesh", "SpentCase_Mesh")]:
        owner = ob.parent
        while owner is not None and owner.name not in PART_BONE:
            owner = owner.parent
        attach(ob, PART_BONE.get(owner.name, "Frame") if owner is not None else "Frame")
    for name, bone_name in MARKERS.items():
        attach(bpy.data.objects[name], bone_name)
    wf = bpy.data.objects.new("WeaponFrame", None)                  # оси винтовки у шейки: сюда игра ставит обвесы
    wf.empty_display_size = 0.01
    scene.collection.objects.link(wf)
    wf.matrix_world = g_rest.copy()
    attach(wf, "Frame")
    # патроны и гильза: сетка патрона стоит донцем в начале своей пустышки, пулей по −Y — так и кладётся на кость
    rnd, case = bpy.data.objects["Round_Mesh"], bpy.data.objects["SpentCase_Mesh"]
    for n in ROUND_BONES:
        ob = rnd.copy()
        ob.name = "Part_" + n
        scene.collection.objects.link(ob)
        ob.parent = None
        ob.matrix_world = world(arms, n)
        attach(ob, n)
    case.parent = None
    case.name = "Part_Case"
    case.matrix_world = world(arms, "Case")
    attach(case, "Case")
    bpy.data.objects.remove(rnd, do_unlink=True)
    for ob in [o for o in bpy.data.objects if o.type == "EMPTY" and o.name not in MARKERS and o.name != "WeaponFrame"]:
        bpy.data.objects.remove(ob, do_unlink=True)                  # пустышки деталей больше не нужны (меши — на костях)
    bpy.context.view_layer.update()
    cols = arms.data.collections
    parts = cols.get("Мосин — детали") or cols.new("Мосин — детали")
    ctrl = cols.get("Мосин — винтовка") or cols.new("Мосин — винтовка")
    for n in GUN_PARTS + ("Frame",):
        b = arms.data.bones[n]
        for c in list(b.collections):
            c.unassign(b)
        (ctrl if n == "Frame" else parts).assign(b)
    parts.is_visible = False


GUN_PARTS = ("Bolt", "Bolt_Rotor", "Bolt_Cocking", "Interrupter", "Trigger", "Follower", "RearSight_Leaf",
             "RearSight_Slider", "Scope", "Case") + tuple(ROUND_BONES)


# ================================================================ пальцы (как у ПМ)

class Hands:
    """Сгиб пальца правой — вокруг той оси, вокруг которой он согнут в хвате владельца (у правой кисти рига оси костей
    пальцев повёрнуты по-своему); у левой сгиб — локальная X. Сдвиги костей ладони и большого пальца из хвата
    владельца (он двигал костяшки) правая кисть сохраняет всегда."""

    def __init__(self, arms, ready: dict) -> None:
        self.axis: dict = {}
        self.loc: dict = {}
        self.owner: dict = {}
        for n, m in ready["basis"].items():
            loc, q, _scale = m.decompose()
            self.owner[n] = q.copy()
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
    ось кости лежит не по центру пальца (до поверхности 11–15 мм)."""

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

    def inside(self, tree: BVHTree, bones: list, depth: float = 0.002) -> int:
        """Сколько вершин сетки этих костей ушло внутрь поверхности глубже depth (по нормали ближайшей грани)."""
        dg = bpy.context.evaluated_depsgraph_get()
        ev = self.ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ev.matrix_world
        n_in = 0
        for n in bones:
            for i in self.verts.get(n, ()):
                p = mw @ me.vertices[i].co
                loc, nrm, _i, dist = tree.find_nearest(p)
                if loc is not None and (p - loc).dot(nrm) < 0.0 and dist > depth:
                    n_in += 1
        ev.to_mesh_clear()
        return n_in


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
             knuckle: Vector | None = None, out: Vector = Vector((0.0015, 0.0, 0.0))) -> dict:
    """Большой палец: кончик в точку (в осях винтовки); если задан сустав — сначала пясть (thumb.01) концом в него,
    затем две фаланги ведут кончик. Касается предмета — точки отодвигаются наружу (out, оси винтовки) по шагу,
    пока сетка пальца не отойдёт."""
    names = [f"thumb.{i:02d}.{side}" for i in (1, 2, 3)]
    tip, knuckle = tip.copy(), knuckle.copy() if knuckle is not None else None
    for _ in range(14):
        if knuckle is not None:
            reach_tip(arms, names[:1], frame_w @ knuckle)
            reach_tip(arms, names[1:], frame_w @ tip)
        else:
            reach_tip(arms, names, frame_w @ tip)
        if skin.gap(tree, names[1:]) > 0.0015:
            break
        tip += out
        if knuckle is not None:
            knuckle += out
    for n in names:
        pose[n] = arms.pose.bones[n].rotation_quaternion.copy()
    return pose


# ================================================================ стойки

def stances(scope_eye: Vector) -> dict:
    """Где стоит винтовка (начало — шейка) в каждой стойке; камера в CAM, взгляд по −Y, правая сторона кадра — −X.
    Камера рук — 54° по вертикали (FPS_VIEWMODEL_FOV игры): точка на глубине d и смещении s видна в s/d·707 px от
    центра кадра 1280×720."""
    return {
        # от бедра: приклад у плеча, винтовка ниже глаза и правее, дуло чуть внутрь, лёгкий завал к центру
        "READY": gun_pose((-0.15, -0.27, 1.645), pitch=0.5, yaw=4.0, roll=3.0),
        # наискосок влево-вниз: цевьё и ствол — внизу слева, коробка у нижнего края кадра
        "CARRY": gun_pose((-0.12, -0.25, 1.668), pitch=-12.0, yaw=20.0, roll=22.0),
        # прицел: глаз на оси ПУ за окуляром на вынос зрачка
        "ADS": Matrix.Translation(Vector((CAM.x, CAM.y - EYE_RELIEF, CAM.z)) - scope_eye),
    }


STANCE_FRAMES = {"CARRY": 1, "READY": 11, "ADS": 21}
STANCE_NAMES = {"CARRY": "Наискосок", "READY": "От бедра", "ADS": "Прицел"}
# Точки в осях винтовки (сечения ложи — work: probe_mosin_sections.py): шейка x ±17,5, верх z 24, низ −25 (y 0);
# хвостовик коробки над шейкой с y −0,03; цевьё перед магазином x ±18,5, низ z 20 (y −0,37).
R_THUMB_TIP = Vector((0.016, -0.040, 0.026))     # большой правой — через верх шейки на левую сторону, к хвостовику
L_THUMB_TIP = Vector((0.019, -0.445, 0.042))     # большой левой — по левой стороне цевья вперёд
L_THUMB_MCP = Vector((0.026, -0.385, 0.018))     # … от основания под левой кромкой цевья


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


def reach(arms, bone: str, target: Matrix) -> float:
    """Насколько кисть не дотянулась до цели IK (мм)."""
    return round((world(arms, bone).translation - target.translation).length * 1000.0, 1)


def grip() -> None:
    scene, arms = append_scene()
    scope_eye = bpy.data.objects["ScopeEye"].matrix_world.translation.copy()   # винтовка ещё в начале координат
    ready = read_ready(scene, arms)
    r_in_gun, l_in_gun = hands_on_rifle(ready)
    all_stances = stances(scope_eye)
    g = all_stances["READY"]
    build_rig(scene, arms, g)
    hands = Hands(arms, ready)
    hands.place(arms)
    for n in ("RoundHand", "Case"):                                      # в покое: патрона в пальцах и гильзы нет
        arms.pose.bones[n].matrix_basis = HIDDEN
    obj = bpy.data.objects
    wood, steel = obj["Frame_Wood"], obj["Frame_Steel"]
    skin = Skin(obj["FPS_Arms"])

    # ---- правая: хват владельца на шейке
    set_world(arms, "Frame", g)
    set_world(arms, "ik_hand.R", g @ r_in_gun)
    r_pose = hands.pose("R")
    apply(arms, r_pose)
    tree = bvh_of([wood, steel])
    r_pose = wrap(arms, hands, skin, r_pose, "R", tree, fingers=("f_middle", "f_ring", "f_pinky"), start=(1.0, 0.7, 0.7),
                  joints=(1, 2))
    r_pose = thumb_to(arms, skin, tree, g, r_pose, "R", R_THUMB_TIP)
    r_fire = wrap(arms, hands, skin, dict(r_pose), "R", bvh_of([obj["Trigger_Mesh"]]), fingers=("f_index",),
                  start=(0.8, 1.0, 1.0), joints=(0,))
    apply(arms, r_fire)
    # ---- левая: ладонь под цевьём перед магазином, пальцы по правой стороне, большой — по левой
    set_world(arms, "ik_hand.L", g @ l_in_gun)
    l_pose = {n: hands.owner[n].copy() for n in LEFT if not n.startswith("hand")}
    apply(arms, l_pose)
    tree_l = bvh_of([wood, steel])
    l_pose = thumb_to(arms, skin, tree_l, g, l_pose, "L", L_THUMB_TIP, L_THUMB_MCP, out=Vector((0.0015, 0.0, -0.0005)))
    l_pose = wrap(arms, hands, skin, l_pose, "L", tree_l, start=(0.6, 0.6, 0.6))
    fit = {"right_mm": {f: round(skin.gap(tree, [f"{f}.{i:02d}.R" for i in (1, 2, 3)]) * 1000, 1) for f in FINGERS + ("thumb",)},
           "left_mm": {f: round(skin.gap(tree_l, [f"{f}.{i:02d}.L" for i in (1, 2, 3)]) * 1000, 1) for f in FINGERS + ("thumb",)},
           "right_inside": skin.inside(tree, [n for n in RIGHT]),
           "left_inside": skin.inside(tree_l, [n for n in LEFT])}

    # ---- стойки: только положение Frame (кадр = стойка), хват без ключей — общий для всех стоек
    clip = Clip(arms, "Mosin_Stances")
    for stance, frame in STANCE_FRAMES.items():
        clip.key_matrix("Frame", frame, all_stances[stance])
        scene.timeline_markers.new(STANCE_NAMES[stance], frame=frame)
    for fc in fcurves(clip.action):
        for kp in fc.keyframe_points:
            kp.interpolation = "CONSTANT"
    scene.frame_start, scene.frame_end = 1, STANCE_FRAMES["ADS"] + 9
    scene.frame_set(STANCE_FRAMES["READY"])
    set_world(arms, "ik_hand.R", g @ r_in_gun)
    set_world(arms, "ik_hand.L", g @ l_in_gun)
    apply(arms, r_fire)
    apply(arms, l_pose)
    hands.place(arms)
    report = {"fit": fit, "reach_mm": {}}
    for stance, frame in STANCE_FRAMES.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        gs = all_stances[stance]
        report["reach_mm"][stance] = {"R": reach(arms, "hand.R", gs @ r_in_gun), "L": reach(arms, "hand.L", gs @ l_in_gun)}
    scene.frame_set(STANCE_FRAMES["READY"])
    LIB.mkdir(parents=True, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0                # без .blend1 рядом: папку модели держим чистой
    bpy.ops.wm.save_as_mainfile(filepath=str(GRIP_FILE))
    (LIB / "grip_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("MOSIN_GRIP saved", GRIP_FILE, json.dumps(report, ensure_ascii=False), flush=True)


# ================================================================ кадры для проверки

def stills() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(CLIPS_FILE if any(a.startswith("clip=") for a in ARGS) else GRIP_FILE))
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
    out = next((Path(a[4:]) for a in ARGS[1:] if a.startswith("out=")), LIB / "Кадры")
    out.mkdir(parents=True, exist_ok=True)
    only = [a for a in ARGS[1:] if "=" not in a]
    views = (("glaz", None), ("sprava", Vector((-0.55, 0.10, 0.10))), ("sleva", Vector((0.55, -0.15, 0.08))),
             ("snizu", Vector((-0.15, -0.30, -0.45))), ("speredi", Vector((-0.10, -0.60, 0.06))))
    shots = []
    clip_arg = next((a[5:] for a in ARGS[1:] if a.startswith("clip=")), "")
    if clip_arg:
        for item in clip_arg.split(","):
            name, frame = item.rsplit(":", 1)
            shots.append((f"{name}_{frame}", name, int(frame)))
    else:
        for stance, frame in STANCE_FRAMES.items():
            if not only or stance.lower() in only:
                shots.append((stance.lower(), None, frame))
    for label, action, frame in shots:
        if action:
            arms.animation_data.action = bpy.data.actions[action]
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        focus = world(arms, "Frame") @ Vector((0.0, -0.15, 0.03))       # над коробкой: туда смотрят боковые камеры
        for view, off in views:
            if off is None:
                scene.camera = fps_cam
            else:
                z = off.normalized()
                x = Vector((0.0, 0.0, 1.0)).cross(z).normalized()
                m = Matrix((x, z.cross(x), z)).transposed().to_4x4()
                m.translation = focus + off
                side.matrix_world = m
                scene.camera = side
            scene.render.filepath = str(out / f"{label}_{view}.png")
            bpy.ops.render.render(write_still=True)
    print("MOSIN_STILLS done", out, flush=True)


# ================================================================ клипы (от хвата в файле grip)

GRIP_BONES = ["ik_hand.R", "ik_hand.L"] + list(BODY) + RIGHT + LEFT
CLIP_INFO: dict = {}
BOLT_PIVOT = Vector((0.0, BREECH_Y, BORE_Z))
BALL = Vector((-0.034, -0.1547, 0.0147)) - BOLT_PIVOT     # шар рукояти в осях стебля (закрыт; work: probe_mosin_sections.py)
POUCH = Matrix.Translation(Vector((-0.30, -0.06, 1.36))) @ rot("X", -30.0) @ rot("Z", -20.0)   # за кадром: подсумок справа


def cam_offset(gun: Matrix, d: Vector = Vector(), pitch: float = 0.0, yaw: float = 0.0, roll: float = 0.0) -> Matrix:
    """Сдвиг и поворот винтовки в осях камеры вокруг её шейки: pitch — дуло вверх, yaw — дуло влево, roll — верх
    влево (градусы); d — в мире сцены (−X — вправо по кадру, +Z — вверх, −Y — от глаз)."""
    r = rot("Z", yaw) @ rot("X", -pitch) @ rot("Y", roll)
    return Matrix.Translation(gun.translation + d) @ r @ gun.to_3x3().to_4x4()


def blend(a: Matrix, b: Matrix, t: float) -> Matrix:
    q = a.to_quaternion().slerp(b.to_quaternion(), t)
    return Matrix.Translation(a.translation.lerp(b.translation, t)) @ q.to_matrix().to_4x4()


def ease(t: float) -> float:
    """Разгон и торможение без рывка на краях (квинтика: нулевые скорость и ускорение)."""
    t = min(1.0, max(0.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def clamp01(t: float) -> float:
    return min(1.0, max(0.0, t))


def bolt(rot_deg: float, travel: float, cocked: float) -> dict:
    """Затвор: поворот стебля (+ — рукоять вверх), ход назад, курок (взведён ли уже); отсечка-отражатель — от хода."""
    eject = clamp01((travel - EJECTOR_FROM) / 0.002)
    return {"Bolt": Matrix.Translation((0.0, travel, 0.0)),
            "Bolt_Rotor": rot("Y", rot_deg),
            "Bolt_Cocking": Matrix.Translation((0.0, COCK_TRAVEL * max(clamp01(rot_deg / BOLT_OPEN), cocked), 0.0)),
            "Interrupter": Matrix.Translation((-EJECTOR_IN * eject, 0.0, 0.0))}


def rotor(rot_deg: float, travel: float) -> Matrix:
    """Стебель в осях винтовки (начало — ось канала у торца ствола)."""
    return Matrix.Translation(BOLT_PIVOT + Vector((0.0, travel, 0.0))) @ rot("Y", rot_deg)


def mag(k: int, chamber: bool = False, case: bool = False, hand: bool = False) -> dict:
    """Патроны: k в магазине (места 1…k), патрон в патроннике, стреляная гильза в патроннике, патрон в пальцах;
    подаватель под нижним патроном. Игра потом ставит видимость по счёту сама — здесь показ для просмотра."""
    out = {"RoundChamber": Matrix() if chamber else HIDDEN, "Case": Matrix() if case else HIDDEN,
           "RoundHand": Matrix() if hand else HIDDEN,
           "Follower": Matrix.Translation((0.0, 0.0, -SLOT_PITCH * max(k - 1, 0)))}
    for i in range(1, SLOTS + 1):
        out[f"Round_{i}"] = Matrix() if i <= k else HIDDEN
    return out


def to_slot(i: int, j: float) -> Matrix:
    """Патрон Round_i — на место j (дробное — между местами)."""
    lo = int(math.floor(j))
    return Matrix.Translation(slot(lo).lerp(slot(lo + 1), j - lo) - slot(i))


def follower(n: float) -> Matrix:
    """Подаватель под n-м местом (n патронов в магазине; дробное — между)."""
    return Matrix.Translation((0.0, 0.0, -SLOT_PITCH * max(n - 1.0, 0.0)))


def fed(t: float) -> Matrix:
    """Верхний патрон (Round_1), который затвор досылает: t — ход затвора (от отведённого к закрытому). Торец личинки
    подхватывает закраину на ходе 86,5 мм, патрон идёт вперёд с ним, поднимаясь в патронник с кивком пулей вверх."""
    reach_y = SLOT1.y - BREECH_Y
    base_y = BREECH_Y + min(t, reach_y)
    u = clamp01((reach_y - t) / (reach_y - 0.020))          # 0 — на губах магазина, 1 — на оси канала
    z = SLOT1.z + (BORE_Z - SLOT1.z) * ease(u)
    nod = 7.0 * math.sin(math.pi * u)
    return Matrix.Translation(Vector((0.0, base_y, z)) - SLOT1) @ rot("X", -nod)


class Keyer:
    """Клип: на первом и последнем кадре ключи всех костей хвата и деталей (иначе кость без ключей осталась бы там,
    где её бросил прошлый клип), между ними — только то, что движется.
    over — matrix_basis поверх покоя; place — мировые матрицы детей Frame (кисти)."""

    def __init__(self, arms, rest: dict, name: str, length: int, loop: bool = False) -> None:
        self.arms, self.rest, self.length = arms, rest, length
        self.action = bpy.data.actions.new(name)
        self.action.use_fake_user = True
        self.action.use_frame_range = True
        self.action.frame_start, self.action.frame_end = 0, length
        self.action.use_cyclic = loop
        arms.animation_data.action = self.action
        self.last: dict = {}
        self.events: dict = {}
        CLIP_INFO[name] = {"frames": length, "loop": loop, "events": self.events}

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
        if name in SCALED:
            pb.keyframe_insert("scale", frame=frame)

    def pose(self, frame: float, gun: Matrix, over: dict | None = None, place: dict | None = None,
             all_bones: bool = False) -> None:
        over, place = dict(over or {}), place or {}
        inv = self.arms.matrix_world.inverted()
        for n, m in self.rest.items():
            self.arms.pose.bones[n].matrix_basis = over.get(n, m)
        self.arms.pose.bones["Frame"].matrix = inv @ gun
        for n, m in place.items():
            pb = self.arms.pose.bones[n]
            rel = pb.parent.bone.matrix_local.inverted() @ pb.bone.matrix_local
            pb.matrix_basis = (inv @ gun @ rel).inverted() @ (inv @ m)      # родитель — Frame (поставлен выше)
            over[n] = pb.matrix_basis.copy()
        edge = all_bones or frame in (0, self.length)
        for n in (list(self.rest) if edge else list(over)) + ["Frame"]:
            self._key(n, frame)

    def event(self, name: str, frame: int) -> None:
        self.events[name] = frame

    def finish(self) -> None:
        for fc in fcurves(self.action):
            for kp in fc.keyframe_points:
                if fc.data_path.endswith("scale"):
                    kp.interpolation = "CONSTANT"              # патрон появляется и пропадает ступенькой
                else:
                    kp.interpolation = "BEZIER"
                    kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()


def cycle(phase: float, a: float, b: float, c: float, e: float, p: float) -> tuple:
    """Два шага на цикл: на каждом ударе стопы винтовка проседает (a, м), раз за цикл уходит вбок (b, м)
    с креном (c, °) и поворотом (e, °); кивок p (°) — вместе с проседанием."""
    w = math.tau * phase
    bounce = 0.5 + 0.5 * math.cos(2.0 * w)
    d = Vector((-b * math.sin(w), 0.0, -a * bounce))
    return d, -p * bounce, e * math.sin(w + 0.35), c * math.sin(w)


def right_pose(arms, mcp: Vector, fingers: Vector, palm: Vector) -> Matrix:
    """Кисть правой в осях винтовки: костяшка среднего пальца в точке mcp, пясть и ладонь — по направлениям."""
    m = basis(fingers, palm, "R")
    hand_rest = arms.data.bones["hand.R"].matrix_local
    mcp_local = hand_rest.inverted() @ arms.data.bones["f_middle.01.R"].head_local
    m.translation = mcp - m.to_3x3() @ mcp_local
    return m


# Хват за шар рукояти — щепоть: шар между средней фалангой согнутого указательного (спереди) и подушкой большого
# (сзади), остальные пальцы в кулаке. Обхватить шар кулаком нельзя: у ПУ рукоять отогнута вниз к ложе, до дерева
# слева 4–5 мм. Кулак — хват владельца на рукоятке ВЕРАСа; кисть ставится так, чтобы фаланга и кончик большого
# легли на эти точки (оси стебля при закрытом затворе; от оси кости до перчатки 11–15 мм), тыльной стороной
# вправо-вверх. При подъёме рукояти кисть поворачивается вместе с ней не целиком (KNOB_FOLLOW): докручивается запястье.
KNOB_FRONT = Vector((0.0, -0.018, -0.002))       # ось средней фаланги указательного — перед шаром
KNOB_BACK = Vector((0.0, 0.016, 0.004))          # конец кости большого — за шаром
KNOB_THUMB = Vector((0.0, 0.009, 0.004))         # куда дотягивается кончик большого (касание — по перчатке)
KNOB_DORSAL = Vector((-0.8, 0.0, -0.6))           # тыльная сторона кисти
KNOB_FOLLOW = 0.55
# Досылка патрона в окно (ПУ закрывает обойму): кисть справа от коробки, пясть вперёд вдоль неё, ладонью к правой
# стенке; средний, безымянный, мизинец — в кулак, указательный лежит на стенке, большой через стенку окна давит на
# патрон сверху у донца. Запястье — сзади справа чуть ниже: предплечье не перед глазами. Точки — от донца патрона на
# месте 1 (оси винтовки).
PRESS_AT = Vector((0.0, -0.010, ROUND_R))                  # куда давит кончик большого
PRESS_MCP = Vector((-0.052, 0.045, -0.008))                # костяшка среднего — справа сзади
PRESS_FINGERS = Vector((0.25, -0.92, 0.30))
PRESS_PALM = Vector((0.85, 0.0, -0.5))
PRESS_FIST = 1.15                                          # средний, безымянный, мизинец — плотнее, чем на рукоятке


def clips() -> None:
    """Клипы от хвата в файле grip: покой в двух стойках, переходы, прицел, ходьба, бег; цикл затвора (от бедра и
    в прицеле); заряжание по одному: открыть затвор, патрон (повторяется), закрыть."""
    bpy.ops.wm.open_mainfile(filepath=str(GRIP_FILE))
    scene = bpy.context.scene
    arms = bpy.data.objects["FPS_ArmsRig"]
    st = {}
    for name, frame in STANCE_FRAMES.items():
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        st[name] = world(arms, "Frame")
    carry, ready, ads = st["CARRY"], st["READY"], st["ADS"]
    scene.frame_set(STANCE_FRAMES["READY"])
    bpy.context.view_layer.update()
    r_grip = ready.inverted() @ world(arms, "ik_hand.R")                 # хват правой на шейке в осях винтовки
    rest = {n: arms.pose.bones[n].matrix_basis.copy() for n in GRIP_BONES + list(GUN_PARTS) if n in arms.pose.bones}
    arms.animation_data.action = None
    hands = Hands(arms, read_ready(scene, arms))
    rest.update(bolt(0.0, 0.0, 1.0))                                     # покой: затвор закрыт, курок взведён
    rest.update(mag(4, chamber=True))                                    # 4 в магазине и патрон в патроннике
    skin = Skin(bpy.data.objects["FPS_Arms"])
    obj = bpy.data.objects
    # шар рукояти действительно поднимается при +90° (проверка знака поворота стебля)
    up0, up90 = (rotor(0.0, 0.0) @ BALL).z, (rotor(BOLT_OPEN, 0.0) @ BALL).z
    assert up90 > up0 + 0.03, (up0, up90)

    def reset(gun: Matrix, extra: dict | None = None) -> None:
        for n, m in rest.items():
            arms.pose.bones[n].matrix_basis = m
        for n, m in (extra or {}).items():
            arms.pose.bones[n].matrix_basis = m
        arms.pose.bones["Frame"].matrix = arms.matrix_world.inverted() @ gun
        bpy.context.view_layer.update()

    def as_basis(pose: dict) -> dict:
        return {n: Matrix.LocRotScale(rest[n].to_translation() if n in rest else Vector(), q, None) for n, q in pose.items()}

    def pinch(curl: float, front: Vector, back: Vector, want: Vector, local: Vector = Vector((1.0, 0.0, 0.0))) -> Matrix:
        """Кисть, у которой в кулаке владельца (сгиб curl) средняя фаланга указательного — в точке front, конец
        большого — в back, а ось кисти local (по умолчанию X — тыльная сторона; −Y — к запястью) повёрнута к want
        (оси, в которых заданы точки)."""
        reset(ready)
        apply(arms, hands.pose("R", curl))
        hands.place(arms)
        inv = world(arms, "hand.R").inverted()
        pb, mw = arms.pose.bones, arms.matrix_world
        a = inv @ (mw @ ((pb["f_index.02.R"].head + pb["f_index.02.R"].tail) * 0.5))
        b = inv @ (mw @ pb["thumb.03.R"].tail)
        axis = (back - front).normalized()
        q1 = (b - a).normalized().rotation_difference(axis)

        def flat(v: Vector) -> Vector:
            return (v - axis * v.dot(axis)).normalized()

        x1, w = flat(q1 @ local), flat(want)
        turn = x1.angle(w) * (1.0 if x1.cross(w).dot(axis) > 0.0 else -1.0)
        r = (Quaternion(axis, turn) @ q1).to_matrix()
        m = r.to_4x4()
        m.translation = (front + back) * 0.5 - r @ ((a + b) * 0.5)
        return m

    grasp = pinch(1.0, BALL + KNOB_FRONT, BALL + KNOB_BACK, KNOB_DORSAL)

    def knob_hand(rot_deg: float, travel: float) -> Matrix:
        """Кисть на шаре рукояти (оси винтовки): идёт за шаром, поворачивается на долю поворота стебля."""
        turn = Matrix.Translation(BALL) @ rot("Y", -rot_deg * (1.0 - KNOB_FOLLOW)) @ Matrix.Translation(-BALL)
        return rotor(rot_deg, travel) @ turn @ grasp

    def fit_knob(rot_deg: float) -> dict:
        """Пальцы правой на шаре при повороте стебля rot_deg (затвор у торца): кулак владельца, большой — на шар
        сзади, указательный и средний дожаты до шара."""
        reset(ready, bolt(rot_deg, 0.0, 1.0))
        set_world(arms, "ik_hand.R", ready @ knob_hand(rot_deg, 0.0))
        pose = hands.pose("R", 1.0)
        apply(arms, pose)
        hands.place(arms)
        ball = bvh_of([obj["Bolt_Rotor_Mesh"]])
        pose = thumb_to(arms, skin, ball, ready @ rotor(rot_deg, 0.0), pose, "R", BALL + KNOB_THUMB,
                        out=Vector((0.0, 0.0015, 0.0005)))
        pose = wrap(arms, hands, skin, pose, "R", ball, fingers=("f_index", "f_middle"), start=(1.0, 0.6, 0.6), joints=(1, 2))
        return as_basis(pose)

    f_knob0 = fit_knob(0.0)
    f_knob90 = fit_knob(BOLT_OPEN)

    # ---- досылка в магазин: щепоть над окном справа, большой палец — на патрон сверху у донца
    press_pt = SLOT1 + PRESS_AT
    press = right_pose(arms, press_pt + PRESS_MCP, PRESS_FINGERS, PRESS_PALM)
    reset(ready, {**bolt(BOLT_OPEN, BOLT_TRAVEL, 1.0), **mag(0, hand=True)})
    set_world(arms, "ik_hand.R", ready @ press)
    pose = hands.pose("R", 1.0)
    for f in ("f_middle", "f_ring", "f_pinky"):                          # остальные — в кулак, мимо стенки коробки
        for i in (1, 2, 3):
            pose[f"{f}.{i:02d}.R"] = hands.scaled(f"{f}.{i:02d}.R", PRESS_FIST)
    apply(arms, pose)
    hands.place(arms)
    rnd = bvh_of([obj["Part_RoundHand"]])
    pose = thumb_to(arms, skin, rnd, ready, pose, "R", press_pt, out=Vector((0.0, 0.0, 0.0015)))
    pose = wrap(arms, hands, skin, pose, "R", bvh_of([obj["Frame_Steel"], obj["Frame_Wood"]]), fingers=("f_index",),
                start=(0.6, 0.4, 0.4), joints=(1, 2))
    f_press = as_basis(pose)
    round_in_hand = world(arms, "hand.R").inverted() @ world(arms, "RoundHand")   # патрон относительно кисти у окна
    press_reach = reach(arms, "hand.R", ready @ press)
    reset(ready)

    # подача: заряжающий поворачивает винтовку окном к себе — верх влево, дуло вверх, ближе к глазам
    present = cam_offset(ready, Vector((0.05, 0.0, 0.03)), pitch=8.0, yaw=10.0, roll=28.0)

    def idle(name: str, gun: Matrix) -> None:
        k = Keyer(arms, rest, name, 60, loop=True)
        for f in range(0, 61, 3):
            w = math.tau * f / 60.0
            k.pose(f, cam_offset(gun, Vector((0.0006 * math.sin(w * 0.5), 0.0, 0.0014 * math.sin(w))), pitch=0.35 * math.sin(w + 0.5)))
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

    def lerp_pose(a: dict, b: dict, t: float) -> dict:
        """Пальцы между двумя позами (пустая — покой хвата)."""
        out = {}
        for n in set(a) | set(b):
            ma, mb = a.get(n, rest.get(n, Matrix())), b.get(n, rest.get(n, Matrix()))
            q = ma.to_quaternion().slerp(mb.to_quaternion(), t)
            out[n] = Matrix.LocRotScale(ma.to_translation().lerp(mb.to_translation(), t), q, None)
        return out

    def track(keys: list):
        """Положение винтовки по кадрам из опорных (кадр, матрица) — плавно между ними."""
        def at(f: float) -> Matrix:
            for (fa, ma), (fb, mb) in zip(keys, keys[1:]):
                if fa <= f <= fb:
                    return blend(ma, mb, ease((f - fa) / max(fb - fa, 1e-6)))
            return keys[-1][1] if f > keys[-1][0] else keys[0][1]
        return at

    def hand_path(k: Keyer, f0: int, f1: int, gun_at, a_hand, b_hand, over_at, arc: Vector = Vector()) -> None:
        """Кисть правой от a к b (матрицы в осях винтовки или функции кадра) по дуге, ключ на каждом кадре."""
        for f in range(f0, f1 + 1):
            t = ease((f - f0 + 1) / (f1 - f0 + 1))
            g = gun_at(f)
            a = a_hand(f) if callable(a_hand) else a_hand
            b = b_hand(f) if callable(b_hand) else b_hand
            m = blend(a, b, t)
            m.translation += arc * math.sin(math.pi * t)
            k.pose(f, g, over_at(f, t), {"ik_hand.R": g @ m})

    def case_flight(f: float, f_eject: float, travel_at) -> Matrix:
        """Гильза: до выброса едет с личинкой, потом вылетает вправо-вверх с вращением."""
        if f <= f_eject:
            return Matrix.Translation((0.0, travel_at(f), 0.0))
        dt = (f - f_eject) / FPS
        p = Vector((-1.6 * dt, EJECT_AT + 0.35 * dt, 1.1 * dt - 4.9 * dt * dt))
        return Matrix.Translation(p) @ rot("Z", -900.0 * dt) @ rot("X", 300.0 * dt)

    def stripped(k_in: int, t: float, rise: float) -> dict:
        """Затвор идёт вперёд (ход t): верхний патрон досылается, остальные поднимаются на место выше (rise 0…1)."""
        out = {"Round_1": fed(t) if k_in >= 1 else HIDDEN, "Follower": follower(k_in - rise)}
        for i in range(2, k_in + 1):
            out[f"Round_{i}"] = to_slot(i, i - rise)
        return out

    def bolt_work(name: str, base: Matrix, lift: Matrix, mag_k: int) -> None:
        """Цикл затвора после выстрела: правая с шейки на шар, поворот вверх (взвод), назад до упора — гильза
        вылетает, вперёд — верхний патрон в патронник, поворот вниз, правая на шейку. Винтовка на время работы
        отходит в lift и возвращается в base."""
        f_reach, f_up, f_back, f_rear, f_fwd, f_down, f_ret, length = 7, 11, 17, 18, 23, 26, 32, 36
        gun = track([(0, base), (f_reach, lift), (f_back, cam_offset(lift, Vector((0.0, 0.006, 0.0)), pitch=0.8)),
                     (f_rear, lift), (f_fwd, cam_offset(lift, Vector((0.0, -0.004, 0.0)), pitch=-0.5)),
                     (f_down, lift), (f_ret, base), (length, base)])

        def travel_at(f: float) -> float:
            if f <= f_up:
                return 0.0
            if f <= f_back:
                return BOLT_TRAVEL * ease((f - f_up) / (f_back - f_up))
            if f <= f_rear:
                return BOLT_TRAVEL
            if f <= f_fwd:
                return BOLT_TRAVEL * (1.0 - ease((f - f_rear) / (f_fwd - f_rear)))
            return 0.0

        def rot_at(f: float) -> float:
            if f <= f_reach:
                return 0.0
            if f <= f_up:
                return BOLT_OPEN * ease((f - f_reach) / (f_up - f_reach))
            if f <= f_fwd:
                return BOLT_OPEN
            if f <= f_down:
                return BOLT_OPEN * (1.0 - ease((f - f_fwd) / (f_down - f_fwd)))
            return 0.0

        f_eject = f_up + (f_back - f_up) * 0.93                      # ход 87,2 из 88 — почти у упора

        def state(f: float) -> dict:
            r, t = rot_at(f), travel_at(f)
            out = {**bolt(r, t, 1.0 if f > f_up else 0.0), **mag(mag_k)}
            out["Case"] = case_flight(f, f_eject, travel_at) if f < f_eject + 9 else HIDDEN
            if f > f_rear:
                out.update(stripped(mag_k, t, ease(clamp01((f - f_rear) / 3.0))))
            return out

        k = Keyer(arms, rest, name, length)
        k.pose(0, base, state(0))
        hand_path(k, 1, f_reach, gun, r_grip, knob_hand(0.0, 0.0), lambda f, t: {**state(f), **lerp_pose({}, f_knob0, t)},
                  arc=Vector((0.0, 0.0, 0.025)))
        for f in range(f_reach + 1, f_ret + 1):
            r, t, g = rot_at(f), travel_at(f), gun(f)
            if f <= f_down:
                k.pose(f, g, {**state(f), **lerp_pose(f_knob0, f_knob90, clamp01(r / BOLT_OPEN))}, {"ik_hand.R": g @ knob_hand(r, t)})
            else:
                u = ease((f - f_down) / (f_ret - f_down))
                m = blend(knob_hand(0.0, 0.0), r_grip, u)
                m.translation += Vector((0.0, 0.0, 0.02)) * math.sin(math.pi * u)
                k.pose(f, g, {**state(f), **lerp_pose(f_knob0, {}, u)}, {"ik_hand.R": g @ m})
        k.event("hand_on_bolt", f_reach)
        k.event("bolt_up", f_reach + 2)
        k.event("bolt_back", f_back)
        k.event("eject", int(f_eject))
        k.event("bolt_forward", f_fwd)
        k.event("bolt_down", f_down)
        k.pose(length, base, {**bolt(0.0, 0.0, 1.0), **mag(mag_k), **stripped(mag_k, 0.0, 1.0)})
        k.finish()

    # ---- стойки, переходы, ходьба (как у ПМ)
    run_base = cam_offset(carry, Vector((0.0, 0.03, 0.0)), pitch=-6.0, roll=8.0)
    idle("Mosin_Idle_Ready", ready)
    idle("Mosin_Idle_Carry", carry)
    go("Mosin_Carry_To_Ready", carry, ready, 12, Vector((0.0, -0.01, 0.012)))
    go("Mosin_Ready_To_Carry", ready, carry, 14, Vector((0.0, 0.0, -0.008)), settle=0.5)
    go("Mosin_Ready_To_ADS", ready, ads, 11, Vector((0.004, 0.006, 0.004)))
    go("Mosin_ADS_To_Ready", ads, ready, 11, Vector((0.0, 0.0, -0.004)), settle=0.5)
    go("Mosin_Carry_To_ADS", carry, ads, 14, Vector((-0.01, -0.012, 0.015)))
    go("Mosin_ADS_To_Carry", ads, carry, 15, Vector((0.0, 0.0, -0.01)), settle=0.5)
    move("Mosin_Walk_Ready", ready, 40, 0.004, 0.006, 1.4, 0.8, 0.6, 2)
    move("Mosin_Walk_Carry", carry, 40, 0.005, 0.008, 1.8, 1.0, 0.8, 2)
    move("Mosin_Run", run_base, 16, 0.013, 0.015, 4.5, 2.6, 2.6, 1)
    go("Mosin_Carry_To_Run", carry, run_base, 9)
    go("Mosin_Run_To_Carry", run_base, carry, 11, settle=0.5)

    # ---- цикл затвора: от бедра винтовка чуть заваливается влево и опускается; в прицеле — сходит с глаза на полпути к бедру
    # (у глаза отведённый шар рукояти с кистью — в 9 см от него) и возвращается
    bolt_work("Mosin_Bolt_Cycle", ready, cam_offset(ready, Vector((0.02, 0.0, -0.012)), pitch=1.5, yaw=2.0, roll=9.0), 4)
    bolt_work("Mosin_Bolt_Cycle_ADS", ads, cam_offset(blend(ads, ready, 0.55), Vector((0.01, 0.0, 0.0)), pitch=1.0, yaw=1.0, roll=8.0), 4)

    # ---- заряжание по одному (с ПУ): открыть затвор и к подсумку / патрон в окно (повторяется) / закрыть затвор
    open_bolt = bolt(BOLT_OPEN, BOLT_TRAVEL, 1.0)
    k = Keyer(arms, rest, "Mosin_Load_Start", 28)
    gun = track([(0, ready), (9, present), (28, present)])
    k.pose(0, ready, {**bolt(0.0, 0.0, 1.0), **mag(0)})
    hand_path(k, 1, 6, gun, r_grip, knob_hand(0.0, 0.0), lambda f, t: {**bolt(0.0, 0.0, 1.0), **mag(0), **lerp_pose({}, f_knob0, t)},
              arc=Vector((0.0, 0.0, 0.025)))
    for f in range(7, 17):
        r = BOLT_OPEN * ease((f - 6) / 4.0)
        t = BOLT_TRAVEL * ease((f - 10) / 6.0) if f > 10 else 0.0
        g = gun(f)
        k.pose(f, g, {**bolt(r, t, 1.0), **mag(0), **lerp_pose(f_knob0, f_knob90, r / BOLT_OPEN)}, {"ik_hand.R": g @ knob_hand(r, t)})
    k.event("bolt_up", 8)
    k.event("bolt_back", 16)
    hand_path(k, 17, 26, gun, knob_hand(BOLT_OPEN, BOLT_TRAVEL), lambda f: gun(f).inverted() @ POUCH,
              lambda f, t: {**open_bolt, **mag(0), **lerp_pose(f_knob90, {}, t)})
    k.pose(28, present, {**open_bolt, **mag(0)}, {"ik_hand.R": POUCH})
    k.finish()

    # патрон: кисть от подсумка с патроном к окну, кладёт сверху на столбик, давит большим (столбик уходит на место
    # вниз), отпускает, обратно к подсумку. Показ — в магазине уже 2.
    have = 2
    at_pouch = present.inverted() @ POUCH
    above = Matrix.Translation(Vector((-0.004, -0.004, 0.016))) @ press        # патрон над окном
    placed = Matrix.Translation(Vector((0.0, 0.0, 0.004))) @ press             # лёг на верхний патрон
    pushed = Matrix.Translation(Vector((0.0, 0.0, -0.002))) @ press            # дожат чуть глубже места
    lifted = Matrix.Translation(Vector((-0.006, 0.006, 0.020))) @ press        # большой палец отпустил
    k = Keyer(arms, rest, "Mosin_Load_Round", 36, loop=True)

    def round_basis(hand_m: Matrix) -> Matrix:
        """Патрон в пальцах (matrix_basis RoundHand, покой — место 1) при кисти hand_m (оси винтовки)."""
        return Matrix.Translation(slot(1)).inverted() @ hand_m @ round_in_hand

    def stack(t: float) -> dict:
        """Столбик из have патронов уходит вниз на место под новым патроном (t 0…1)."""
        return {**{f"Round_{i}": to_slot(i, i + t) for i in range(1, have + 1)}, "Follower": follower(have + t)}

    base_mag = {**open_bolt, **mag(have, hand=True)}
    k.pose(0, present, {**base_mag, "RoundHand": round_basis(at_pouch)}, {"ik_hand.R": POUCH})
    k.event("grab", 0)
    seq = [(0, at_pouch), (11, above), (14, placed), (17, pushed), (19, press), (22, lifted), (33, at_pouch), (36, at_pouch)]
    for (fa, ma), (fb, mb) in zip(seq, seq[1:]):
        for f in range(fa + 1, fb + 1):
            t = ease((f - fa) / (fb - fa))
            m = blend(ma, mb, t)
            if fa in (0, 22):
                m.translation += Vector((0.0, 0.0, 0.03)) * math.sin(math.pi * t)
            over = dict(base_mag)
            if f <= 19:
                over["RoundHand"] = round_basis(m)
                over.update(lerp_pose({}, f_press, clamp01(f / 11.0)))
            else:
                over["RoundHand"] = Matrix()                         # патрон лёг на место 1
                over.update(lerp_pose(f_press, {}, clamp01((f - 19) / 8.0)))
            if f >= 14:
                over.update(stack(ease(clamp01((f - 14) / 3.0))))
            k.pose(f, present, over, {"ik_hand.R": present @ m})
    k.event("round_in", 17)
    k.event("release", 20)
    k.finish()

    # закрыть: от подсумка к шару, вперёд — верхний патрон в патронник, поворот вниз, правая на шейку. Показ — 5.
    k = Keyer(arms, rest, "Mosin_Load_End", 34)
    half = blend(present, ready, 0.6)                                # досылает, уже возвращая винтовку из подачи
    gun = track([(0, present), (9, half), (18, half), (27, ready), (34, ready)])
    k.pose(0, present, {**open_bolt, **mag(5)}, {"ik_hand.R": POUCH})
    hand_path(k, 1, 9, gun, lambda f: gun(f).inverted() @ POUCH, knob_hand(BOLT_OPEN, BOLT_TRAVEL),
              lambda f, t: {**open_bolt, **mag(5), **lerp_pose({}, f_knob90, t)}, arc=Vector((0.0, 0.0, 0.03)))
    for f in range(10, 19):
        t = BOLT_TRAVEL * (1.0 - ease((f - 9) / 5.0))
        r = BOLT_OPEN * (1.0 - ease((f - 14) / 4.0)) if f > 14 else BOLT_OPEN
        g = gun(f)
        over = {**bolt(r, t, 1.0), **mag(5), **lerp_pose(f_knob0, f_knob90, r / BOLT_OPEN),
                **stripped(5, t, ease(clamp01((f - 9) / 3.0)))}
        k.pose(f, g, over, {"ik_hand.R": g @ knob_hand(r, t)})
    k.event("bolt_forward", 12)
    k.event("bolt_down", 17)
    closed = {**bolt(0.0, 0.0, 1.0), **mag(5), **stripped(5, 0.0, 1.0)}
    hand_path(k, 19, 29, gun, knob_hand(0.0, 0.0), r_grip, lambda f, t: {**closed, **lerp_pose(f_knob0, {}, t)},
              arc=Vector((0.0, 0.0, 0.02)))
    k.pose(34, ready, closed)
    k.finish()
    CLIP_INFO["_meta"] = {"fps": FPS, "bolt_travel_m": BOLT_TRAVEL, "bolt_open_deg": BOLT_OPEN, "cock_travel_m": COCK_TRAVEL,
                          "slot1": list(SLOT1), "slot_pitch_m": SLOT_PITCH, "slot_stagger_m": SLOT_STAGGER,
                          "chamber": list(CHAMBER), "eye_relief_m": EYE_RELIEF, "press_reach_mm": press_reach,
                          "preview": "видимость патронов в клипах — для просмотра (цикл: 4 в магазине; патрон: 2; закрыть: 5); "
                                     "игра ставит её по счёту, Round_i сдвигаются клипом на соседнее место"}
    arms.animation_data.action = bpy.data.actions["Mosin_Idle_Ready"]
    scene.frame_start, scene.frame_end = 0, 36
    scene.frame_set(0)
    for m in list(scene.timeline_markers):
        scene.timeline_markers.remove(m)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(CLIPS_FILE))
    (LIB / "clips.json").write_text(json.dumps(CLIP_INFO, ensure_ascii=False, indent=1), encoding="utf-8")
    print("MOSIN_CLIPS saved", CLIPS_FILE, json.dumps({n: v["frames"] for n, v in CLIP_INFO.items() if n != "_meta"}),
          "press_reach_mm", press_reach, flush=True)


if MODE == "stills":
    stills()
elif MODE == "clips":
    clips()
else:
    grip()
