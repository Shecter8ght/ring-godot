"""АСТЕН-919 (wpn_hg_02): хват рук на риге tools/asten919/clips/rig.py — заготовка для правки владельцем.

Основа — хват пистолета владельца с ПМ (PM_FPS_Grip_v03.blend → tools/asten919/clips/pm_grip_dump.py): поза костей
переносится на мастер v14 с пересчётом осей покоя (у концевых фаланг v14 кость смотрит иначе — до 42°), сдвиги костей
кисти — с поправкой на меньшую кисть. Кисть ставится на рукоять АСТЕН-919 по опорным местам (перепонка — в выемку спинки
под хвостом рамки, ось рукояти — к оси рукояти ПМ), потом подгоняется по полю расстояний пистолета
(tools/asten919/clips/hand_sdf.py): ладонь жёстким телом — до касания без проникновения; пальцы по фалангам от основания —
до касания; указательный — вдоль рамки и на спуске; большой — вдоль рамки слева под рычагом задержки.

  right — этап 1 (как принимали хват ПМ): только правая, левая убрана вниз-влево;
  both  — этап 2: левая «в замок» поверх пальцев правой (правая берётся из принятого файла, не меняется).

Действие ASTEN919_Grip_v01: кадр 1 — указательный вдоль рамки, кадр 11 — на спуске.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b "<ASTEN919_Rig_v01.blend>" --python-exit-code 1 --python tools/asten919/clips/grip.py -- right <выход.blend>
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from sdf_grid import Grid  # noqa: E402

ARGS = sys.argv[sys.argv.index("--") + 1:]
STAGE, OUT = ARGS[0], Path(ARGS[1])
PM = json.loads((ROOT / "_asset_src/asten919/anim/pm_grip.json").read_text(encoding="utf-8"))
ACTION = "ASTEN919_Grip_v01"
log = lambda *a: print("ASTEN_GRIP", *a, flush=True)  # noqa: E731

S = bpy.context.scene
arms = bpy.data.objects["FPS_ArmsRig"]
skin_ob = bpy.data.objects["FPS_Arms"]
root = bpy.data.objects["ASTEN919"]
wr = bpy.data.objects["ASTEN919_WeaponRig"]
AW = arms.matrix_world.copy()
AWI = AW.inverted()
TW = root.matrix_world.copy()                 # исходник (м) → мир
TWI = TW.inverted()
WHOLE = Grid.load("whole")

# ---- опорные места (исходник пистолета, м)
GRIP_UP = Vector((math.sin(math.radians(22.0)), 0.0, math.cos(math.radians(22.0))))
WEB = Vector((-0.0592, 0.0, -0.0325))         # выемка спинки под хвостом рамки (поле: −58,4 при z −34)
THUMB_TIP = Vector((-0.021, 0.0165, -0.0262))  # подушечка большого: слева на рамке под рычагом задержки
TRIGGER_PAD = Vector((0.0138, 0.0005, -0.0375))
INDEX_REST = Vector((0.027, -0.0145, -0.0245))   # подушечка указательного «вдоль рамки»: правый бок рамки над скобой  # подушечка указательного на спуске (перед лицом крючка)
# ПМ (оси кости Frame: +X влево, −Y дуло, +Z вверх; м): выемка под хвостом рамки и ось рукояти (clips.json mag_axis)
PM_WEB = Vector((0.0, 0.0155, 0.031))
PM_UP = Vector((0.0, -0.19612, 0.98058))
PALM_OPEN = 0.45
PALM_K, FINGER_K = 0.72, 0.74                # кисти v14 против прежних (ладонь × 0,70 / 0,76, пальцы × 0,74)
RIGHT_FINGERS = [b.name for b in arms.pose.bones if b.name.endswith(".R") and b.name.split(".")[0] in
                 ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky")]
LEFT_FINGERS = [n[:-2] + ".L" for n in RIGHT_FINGERS]


def update():
    bpy.context.view_layer.update()


def frame(origin, up, left):
    ez = up.normalized()
    ex = (left - ez * left.dot(ez)).normalized()
    ey = ez.cross(ex)
    m = Matrix((ex, ey, ez)).transposed().to_4x4()
    m.translation = origin
    return m


# ================================================================ кожа: вершины перчатки по главной кости
class Skin:
    def __init__(self):
        me = skin_ob.data
        names = [g.name for g in skin_ob.vertex_groups]
        to_arm = AWI @ skin_ob.matrix_world
        rest_inv = {b.name: b.matrix_local.inverted() for b in arms.data.bones}
        self.local = {}
        for v in me.vertices:
            best, w = None, 0.0
            for g in v.groups:
                if g.weight > w and names[g.group] in rest_inv:
                    best, w = names[g.group], g.weight
            if best and w > 0.45:
                self.local.setdefault(best, []).append(rest_inv[best] @ (to_arm @ v.co))
        self.local = {k: np.array([list(p) for p in v]) for k, v in self.local.items()}

    def world(self, name):
        """Точки кожи кости в мире (жёстко с костью), (N, 3)."""
        if name not in self.local:
            return np.zeros((0, 3))
        m = np.array(AW @ arms.pose.bones[name].matrix)
        return self.local[name] @ m[:3, :3].T + m[:3, 3]

    def src_mm(self, name):
        p = self.world(name)
        m = np.array(TWI)
        return (p @ m[:3, :3].T + m[:3, 3]) * 1000.0

    def pen2(self, names, tol):
        """Сумма квадратов проникновения кожи костей глубже tol, мм² — гладкая мера для подбора."""
        out = 0.0
        for n in names:
            if n in self.local and len(self.local[n]):
                out += float((np.maximum(0.0, -WHOLE.dist(self.src_mm(n)) - tol) ** 2).sum())
        return out

    def depth(self, names):
        """Наименьшее расстояние кожи костей до пистолета, мм (< 0 — внутри)."""
        d = [WHOLE.dist(self.src_mm(n)).min() for n in names if n in self.local and len(self.local[n])]
        return float(min(d)) if d else 99.0


SKIN = Skin()


# ================================================================ поза владельца с ПМ
def rest_c(n):
    """Поворот осей покоя кости: прежние руки → мастер v14."""
    return (Matrix(PM["rest"][n]["m"]).to_3x3().normalized().transposed() @ arms.data.bones[n].matrix_local.to_3x3().normalized())


def apply_pm(stance, names, loc_scale=True):
    """Поза владельца на кости v14: тот же поворот фаланги от покоя (B' = C⁻¹·B·C), сдвиги — в осях новой кости и
    с поправкой на меньшую кисть."""
    basis = PM["frames"][stance]["basis"]
    for n in names:
        if n not in basis or n not in arms.pose.bones:
            continue
        m = Matrix(basis[n])
        c = rest_c(n)
        r = (c.transposed() @ m.to_3x3() @ c).to_4x4()
        t = c.transposed() @ m.translation
        if loc_scale:
            t = t * (PALM_K if n.startswith(("palm", "hand")) else FINGER_K)
        r.translation = t
        arms.pose.bones[n].matrix_basis = r


def rest_check():
    worst = max((math.degrees(rest_c(n).to_quaternion().angle), n) for n in RIGHT_FINGERS + LEFT_FINGERS + ["hand.R", "hand.L"])
    log("покой костей v14 против прежних рук: наибольшая разница осей, °", round(worst[0], 1), worst[1], "(учтена при переносе позы)")


# ---- оси суставов по геометрии покоя: сгиб — вокруг линии костяшек, к ладони — плюс
def palm_normal(side):
    h = arms.data.bones[f"hand.{side}"].head_local
    i = arms.data.bones[f"f_index.01.{side}"].head_local
    k = arms.data.bones[f"f_pinky.01.{side}"].head_local
    n = (i - h).cross(k - h).normalized()
    # знак: в покое пальцы чуть согнуты к ладони — средняя фаланга отклонена от пясти в сторону ладони
    palm_dir = (arms.data.bones[f"f_middle.01.{side}"].head_local - h).normalized()
    acc = Vector()
    for f in ("f_index", "f_middle", "f_ring", "f_pinky"):
        d = arms.data.bones[f"{f}.03.{side}"].head_local - arms.data.bones[f"{f}.01.{side}"].head_local
        acc += d - palm_dir * d.dot(palm_dir)
    if acc.dot(n) < 0:
        n = -n
    return n


PALM_N = {s_: palm_normal(s_) for s_ in ("R", "L")}


def flex_axis(bone, side):
    """Ось сгиба сустава кости в её локальных осях (покой): d × n, d — направление фаланги."""
    finger, j = bone.split(".")[0], int(bone.split(".")[1])
    heads = [arms.data.bones[f"{finger}.{k:02d}.{side}"].head_local for k in (1, 2, 3)]
    d = (heads[2] - heads[1]).normalized() if j > 1 else (heads[1] - heads[0]).normalized()
    a = d.cross(PALM_N[side]).normalized()
    return (arms.data.bones[bone].matrix_local.to_3x3().transposed() @ a).normalized()


def set_hand(side, world_m):
    """Кисть в мировую матрицу: цель IK (поворот кисть берёт у неё же), остаток положения добирается сдвигом цели."""
    ik = arms.pose.bones[f"ik_hand.{side}"]
    hand = arms.pose.bones[f"hand.{side}"]
    ik.matrix = AWI @ world_m
    update()
    for _ in range(4):
        gap = world_m.translation - (AW @ hand.matrix).translation
        if gap.length < 2e-5:
            break
        m = AW @ ik.matrix
        m.translation += gap
        ik.matrix = AWI @ m
        update()
    return (world_m.translation - (AW @ hand.matrix).translation).length


def hand_world(side):
    return AW @ arms.pose.bones[f"hand.{side}"].matrix


# ================================================================ этап 1: ладонь жёстким телом по полю расстояний
PALM_BONES = ["hand.R", "palm.01.R", "palm.02.R", "palm.03.R", "palm.04.R", "thumb.01.R"]


def rot_vec(v):
    a = np.linalg.norm(v)
    if a < 1e-12:
        return np.eye(3)
    k = v / a
    K = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + math.sin(a) * K + (1 - math.cos(a)) * K @ K


# куда на пистолете ложатся опорные места правой кисти (исходник, мм): перепонка — в выемку спинки; костяшки (центры
# суставов, на полпальца от правого бока рукояти) — позади переднего угла на длину основной фаланги (она лежит на боку,
# средняя — поперёк передней стенки): среднего — под скобой, мизинца — ниже по оси рукояти, указательного — над скобой
MARKS_GUN = {"web": (-63.0, -8.0, -31.5), "f_index.01.R": (-36.0, -23.5, -41.0), "f_middle.01.R": (-41.0, -23.0, -65.0),
             "f_pinky.01.R": (-53.5, -23.0, -97.0)}
MARKS_W = {"web": 1.0, "f_index.01.R": 0.6, "f_middle.01.R": 1.2, "f_pinky.01.R": 1.0}
PALM_FACES = (0.10, 1.0, 0.0)   # куда смотрит ладонь правой (исходник): влево и чуть вперёд
PALM_SKIN_N = 13.0       # мм: на какой «высоте» над плоскостью костяшек кожа ладони ложится на бок рукояти
WEB_AHEAD = 3.0          # мм: развилка большого и указательного — впереди сустава большого (вдоль кисти)
MIDDLE_MCP_Z = -66.0     # мм: высота костяшки среднего — палец под скобой
PALM_SOFT = 4.0          # мм: мякоть ладони (у основания большого) обминается о спинку рукояти


def src_mm(p_world):
    return np.array(TWI @ p_world) * 1000.0


def hand_marks(pts):
    """Опорные места кисти в осях пистолета, мм: перепонка (кожа у «развилки» большого и указательного), костяшки."""
    a = src_mm(AW @ arms.pose.bones["thumb.02.R"].head)
    b = src_mm(AW @ arms.pose.bones["f_index.01.R"].head)
    web_i = np.argsort(np.linalg.norm(pts - (a * 0.4 + b * 0.6), axis=1))[:20]
    out = {"web": pts[web_i].mean(axis=0)}
    for n in ("f_index.01.R", "f_middle.01.R", "f_pinky.01.R"):
        out[n] = src_mm(AW @ arms.pose.bones[n].head)
    return out


def kabsch(P, Q, w):
    """Жёсткое тело: P → Q (взвешенно). → R (3×3), t."""
    w = np.asarray(w, float) / np.sum(w)
    pc, qc = (P * w[:, None]).sum(0), (Q * w[:, None]).sum(0)
    H = ((P - pc) * w[:, None]).T @ (Q - qc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, 1.0, d]) @ U.T
    return R, qc - R @ pc


def src_delta(R, t_mm):
    """Поворот и сдвиг в осях пистолета (мм) → поправка в мире."""
    m = Matrix(R.tolist()).to_4x4()
    m.translation = Vector(t_mm / 1000.0)
    return TW @ m @ TWI


def fit_palm():
    """Кисть жёстким телом по её собственной геометрии (замер tools: оси кисти — вдоль e, к ладони n, поперёк c = n × e,
    «+» — к мизинцу). Ладонь смотрит на правый бок рукояти; кожа ладони (n ≈ PALM_SKIN_N) — на боку, значит середина
    рукояти — на n = PALM_SKIN_N + полуширина; развилка большого и указательного (чуть впереди сустава большого, у верхнего
    края кисти) — в выемке спинки под хвостом рамки; наклон кисти в плоскости ладони — такой, чтобы костяшка среднего
    встала под скобу. Потом наружу от бока — если ладонь входит в пистолет глубже мякоти. → мировая матрица кисти."""
    hw = hand_world("R")
    hwi = np.array(hw.inverted())
    rest = arms.data.bones["hand.R"].matrix_local.to_3x3().transposed()
    n_l = np.array(rest @ PALM_N["R"])
    e_l = np.array(rest @ (arms.data.bones["f_middle.01.R"].head_local - arms.data.bones["hand.R"].head_local).normalized())
    e_l = e_l - n_l * (e_l @ n_l)
    e_l /= np.linalg.norm(e_l)
    A = np.stack([e_l, n_l, np.cross(n_l, e_l)], axis=1)          # столбцы: e, n, c в осях кости

    def hf(p_world):                                              # мир → (e, n, c), мм
        return (A.T @ (hwi[:3, :3] @ np.array(p_world) + hwi[:3, 3])) * 1000.0
    # мякоть у большого (thumb.01, palm.01) обнимает спинку рукояти и хвост рамки — в «не входить в бок» не участвует
    pts_w = np.concatenate([SKIN.world(n) for n in ("hand.R", "palm.02.R", "palm.03.R", "palm.04.R")])
    pts_f = (pts_w @ hwi[:3, :3].T + hwi[:3, 3]) @ A * 1000.0     # кожа ладони в (e, n, c), мм
    th_f = (SKIN.world("thumb.01.R") @ hwi[:3, :3].T + hwi[:3, 3]) @ A * 1000.0
    mcp = hf(AW @ arms.pose.bones["f_middle.01.R"].head)
    n_mid = PALM_SKIN_N + 14.7
    web = np.array([hf(AW @ arms.pose.bones["thumb.02.R"].head)[0] + WEB_AHEAD, n_mid, th_f[:, 2].min() + 4.0])
    web_t = np.array(WEB) * 1000.0 + np.array([-1.0, 0.0, 0.0])
    Nn = np.array(PALM_FACES) / np.linalg.norm(PALM_FACES)
    best = None
    for deg in np.arange(-15.0, 45.0, 0.25):
        th = math.radians(deg)
        D1 = np.array([math.cos(th), 0.0, math.sin(th)])
        D1 = D1 - Nn * (D1 @ Nn)
        D1 /= np.linalg.norm(D1)
        B = np.stack([D1, Nn, np.cross(Nn, D1)], axis=1)          # (e, n, c) → исходник
        t = web_t - B @ web
        z = (B @ mcp + t)[2]
        if best is None or abs(z - MIDDLE_MCP_Z) < best[0]:
            best = (abs(z - MIDDLE_MCP_Z), deg, B, t)
    err, deg, B, t = best
    out = 0.0
    g = pts_f @ B.T + t
    while out < 12.0:
        d = WHOLE.dist(g + np.array([0.0, -out, 0.0]))
        if int((d < -PALM_SOFT).sum()) <= 2:
            break
        out += 0.25
    t = t + np.array([0.0, -out, 0.0])
    d = WHOLE.dist(pts_f @ B.T + t)
    log("ладонь: кисть вверх от ствола, °", deg, "костяшка среднего, мм", (B @ mcp + t).round(1).tolist(), "развилка, мм", (B @ web + t).round(1).tolist(),
        "наружу от бока, мм", out, "ладонь: глубже всего, мм", round(float(d.min()), 1), "точек ближе 1,5 мм", int((d < 1.5).sum()), "из", len(d))
    R = B @ A.T                                                    # оси кости → исходник
    m = Matrix(R.tolist()).to_4x4()
    m.translation = Vector(t / 1000.0)
    return TW @ m


# ================================================================ этап 2: пальцы по фалангам
STEP = math.radians(1.0)
TOUCH = 0.25                                     # мм: «касание»
SINK = -0.7                                      # мм: мягкая перчатка может войти не глубже


def close_finger(finger, side="R", limits=((-12.0, 75.0), (0.0, 110.0), (0.0, 85.0)), spread_deg=0.0):
    """Палец обхватывает рукоять: от прямого пальца (покой кости, развод — spread_deg) суставы по очереди от основания
    сгибаются вокруг своей оси, пока кожа фаланги не коснётся пистолета; дальние суставы в это время прямые. Так палец
    не может «начать изнутри» (поза владельца с ПМ под узкую рукоять начинала)."""
    names = [f"{finger}.{j:02d}.{side}" for j in (1, 2, 3)]
    axis = {n: flex_axis(n, side) for n in names}
    sp_axis = (arms.data.bones[names[0]].matrix_local.to_3x3().transposed() @ PALM_N[side]).normalized()
    ang = {n: 0.0 for n in names}

    def put():
        for i, n in enumerate(names):
            m = Matrix.Rotation(ang[n], 4, axis[n])
            if i == 0:
                m = Matrix.Rotation(math.radians(spread_deg), 4, sp_axis) @ m
            arms.pose.bones[n].matrix_basis = m
        update()
    note = []
    for j, n in enumerate(names):
        lo, hi = (math.radians(v) for v in limits[j])

        def at(th):
            ang[n] = th
            put()
            return SKIN.depth([n])
        th = lo
        d = at(th)
        touched = d <= TOUCH
        while not touched and th + STEP <= hi:
            d2 = at(th + STEP)
            if d2 < SINK:
                break
            th += STEP
            d = d2
            touched = d <= TOUCH
        ang[n] = th
        if j == 1:
            # концевая прямая, а уже в пистолете — средняя согнута лишнего: приоткрыть, пока концевая не выйдет
            ang[names[2]] = 0.0
            put()
            g = 0
            while SKIN.depth([names[2]]) < SINK and g < 30 and ang[n] - STEP >= lo:
                ang[n] -= STEP
                put()
                g += 1
            th = ang[n]
            d = SKIN.depth([n])
        note.append(f"{math.degrees(th):.0f}°{'' if touched else '∅'} {d:+.1f}")
    put()
    log(f"палец {finger}.{side}: сгибы и зазор, мм:", " | ".join(note), "итог", round(SKIN.depth(names), 2))


def index_pose(target, stance, label, tol):
    """Указательный: поза владельца с ПМ (stance), довороты в пределах — сгиб и развод основания, сгибы средней и
    концевой — подушечка к заданному месту, без проникновения глубже tol."""
    names = [f"f_index.{j:02d}.R" for j in (1, 2, 3)]
    apply_pm(stance, names)
    update()
    owner = {n: arms.pose.bones[n].matrix_basis.copy() for n in names}
    axis = {n: flex_axis(n, "R") for n in names}
    spread = (arms.data.bones[names[0]].matrix_local.to_3x3().transposed() @ PALM_N["R"]).normalized()
    goal = TW @ target
    lim = [(-22.0, 40.0), (-25.0, 25.0), (-12.0, 45.0), (-10.0, 40.0)]

    def put(x):
        x = [min(max(v, math.radians(lo)), math.radians(hi)) for v, (lo, hi) in zip(x, lim)]
        arms.pose.bones[names[0]].matrix_basis = owner[names[0]] @ Matrix.Rotation(x[1], 4, spread) @ Matrix.Rotation(x[0], 4, axis[names[0]])
        arms.pose.bones[names[1]].matrix_basis = owner[names[1]] @ Matrix.Rotation(x[2], 4, axis[names[1]])
        arms.pose.bones[names[2]].matrix_basis = owner[names[2]] @ Matrix.Rotation(x[3], 4, axis[names[2]])
        update()
        return x
    state = [0.0] * 4

    def put2(x):
        state[:] = put(x)

    def cost():
        gap = (pad_point(names[2]) - goal).length * 1000.0
        return gap + 6.0 * SKIN.pen2(names, tol) + 0.03 * sum(abs(math.degrees(v)) for v in state)
    x, best = descend([0.0] * 4, put2, cost, [math.radians(a) for a in (8, 3, 1, 0.4)])
    put2(x)
    log(f"указательный {label}: довороты от позы владельца (сгиб, развод, средняя, концевая), °", [round(math.degrees(a)) for a in state],
        "подушечка от цели, мм", round((pad_point(names[2]) - goal).length * 1000, 1), "до пистолета, мм", round(SKIN.depth(names), 2))


def index_ready():
    index_pose(INDEX_REST, "ready", "вдоль рамки", 0.7)


def pad_point(bone, side="R"):
    """Подушечка концевой фаланги (мир): кожа ладонной стороны на 40–85 % длины фаланги (ось — главная ось облака)."""
    p = SKIN.local[bone]
    c = p.mean(axis=0)
    u = np.linalg.svd(p - c, full_matrices=False)[2][0]
    if (c @ u) < 0:
        u = -u
    t = (p @ u)
    t = (t - t.min()) / max(t.max() - t.min(), 1e-9)
    n = np.array(arms.data.bones[bone].matrix_local.to_3x3().transposed() @ PALM_N[side])
    s_ = (p - c) @ n
    sel = (t > 0.40) & (t < 0.85) & (s_ > np.percentile(s_, 60))
    m = AW @ arms.pose.bones[bone].matrix
    return m @ Vector(p[sel].mean(axis=0))


def search(ranges, put, cost, steps):
    """Подбор чисел в границах: перебор по сетке (ranges: (от, до, шаг) в градусах), потом покоординатный спуск шагами
    steps (градусы) в тех же границах. put(список радиан), cost() → число. → (лучшие числа в радианах, цена)."""
    import itertools
    lo = [math.radians(r[0]) for r in ranges]
    hi = [math.radians(r[1]) for r in ranges]
    grids = [[math.radians(v) for v in np.arange(r[0], r[1] + 1e-6, r[2])] if r[2] > 0 else [math.radians(r[0])] for r in ranges]
    best, x = None, None
    for cand in itertools.product(*grids):
        put(list(cand))
        c = cost()
        if best is None or c < best:
            best, x = c, list(cand)
    for st in (math.radians(v) for v in steps):
        moved = True
        while moved:
            moved = False
            for i in range(len(x)):
                for sgn in (1, -1):
                    y = list(x)
                    y[i] = min(max(y[i] + sgn * st, lo[i]), hi[i])
                    if y[i] == x[i]:
                        continue
                    put(y)
                    c = cost()
                    if c < best - 1e-6:
                        x, best, moved = y, c, True
    put(x)
    return x, best


def phalanx_axis(bone):
    """Направление фаланги в осях её кости: у .01 / .02 — ось кости; у концевой кость мастера v14 смотрит мимо фаланги
    (до 42°) — берётся главная ось облака кожи."""
    if not bone.split(".")[1] == "03":
        return Vector((0.0, 1.0, 0.0))
    p = SKIN.local[bone]
    c = p.mean(axis=0)
    u = np.linalg.svd(p - c, full_matrices=False)[2][0]
    if (c @ u) < 0:
        u = -u
    return Vector(u.tolist()).normalized()


def aim(bone, to_src_mm):
    """Повернуть кость кратчайшим поворотом так, чтобы её фаланга смотрела из головы кости в точку (исходник, мм)."""
    pb = arms.pose.bones[bone]
    goal = AWI @ (TW @ (Vector(to_src_mm) / 1000.0))
    d = (goal - pb.matrix.translation).normalized()
    cur = (pb.matrix.to_3x3() @ phalanx_axis(bone)).normalized()
    m = (cur.rotation_difference(d).to_matrix() @ pb.matrix.to_3x3()).to_4x4()
    m.translation = pb.matrix.translation
    pb.matrix = m
    update()


def aim_dir(bone, dir_src):
    pb = arms.pose.bones[bone]
    head = TWI @ (AW @ pb.matrix.translation) * 1000.0
    aim(bone, head + Vector(dir_src).normalized() * 50.0)


def head_mm(bone):
    return TWI @ (AW @ arms.pose.bones[bone].matrix.translation) * 1000.0


def reset(names):
    for n in names:
        arms.pose.bones[n].matrix_basis = Matrix.Identity(4)
    update()


def swing_out(names, pivot_bone, tol, step_deg=1.0, limit=40):
    """Пока кожа костей входит в пистолет глубже tol — отводить палец от оружия: поворот основания вокруг вертикали
    пистолета (правая сторона — наружу к −Y, левая — к +Y)."""
    pb = arms.pose.bones[pivot_bone]
    side = -1.0 if head_mm(pivot_bone).y < 0 else 1.0
    up = (AWI.to_3x3() @ (TW.to_3x3() @ Vector((0, 0, 1)))).normalized()
    n = 0
    while SKIN.depth(names) < -tol and n < limit:
        # палец смотрит к дулу (+X): наружу вправо — поворот вокруг «вверх» по часовой (−), влево — против (+)
        m = (Matrix.Rotation(math.radians(step_deg) * side, 3, up) @ pb.matrix.to_3x3()).to_4x4()
        m.translation = pb.matrix.translation
        pb.matrix = m
        update()
        n += 1
    return n


def index_ready():
    """Указательный вдоль рамки над скобой: прямой палец из костяшки — в точку у правого бока рамки (INDEX_REST, на
    полпальца от поверхности), суставы чуть согнуты; входит в рамку — отвести наружу."""
    names = [f"f_index.{j:02d}.R" for j in (1, 2, 3)]
    reset(names)
    t = Vector(INDEX_REST) * 1000.0 + Vector((6.0, -8.5, 0.0))
    aim(names[0], t)
    aim(names[1], t)
    aim(names[2], t + Vector((14.0, 2.0, 1.0)))
    n = swing_out(names[1:], names[0], 0.6)
    log("указательный вдоль рамки: костяшка, мм", [round(v, 1) for v in head_mm(names[0])], "отведён наружу, °", n,
        "подушечка от места, мм", round((pad_point(names[2]) - TW @ INDEX_REST).length * 1000, 1), "до пистолета, мм", round(SKIN.depth(names), 2))


def index_trigger():
    """Указательный на спуске: основная и средняя фаланги — от костяшки к суставу перед крючком (изгиб наружу, мимо
    скобы), концевая — поперёк лица крючка, подушечкой на него."""
    names = [f"f_index.{j:02d}.R" for j in (1, 2, 3)]
    reset(names)
    H = head_mm(names[0])
    pad = Vector(TRIGGER_PAD) * 1000.0
    dip = pad + Vector((6.5, -11.0, -0.5))                 # сустав концевой: перед крючком, справа от него
    L1 = arms.data.bones[names[0]].length * 1000.0
    L2 = arms.data.bones[names[1]].length * 1000.0
    v = dip - H
    dist = min(v.length, L1 + L2 - 0.5)
    a = (L1 * L1 - L2 * L2 + dist * dist) / (2.0 * dist)
    h = math.sqrt(max(L1 * L1 - a * a, 0.0))
    out = Vector((0.0, -1.0, 0.0))
    out = (out - v.normalized() * out.dot(v.normalized())).normalized()
    pip = H + v.normalized() * a + out * h
    aim(names[0], pip)
    aim(names[1], dip)
    aim(names[2], pad + Vector((6.5, 12.0, 0.0)))
    log("указательный на спуске: костяшка, мм", [round(v_, 1) for v_ in H], "сустав средней", [round(v_, 1) for v_ in pip],
        "подушечка от места, мм", round((pad_point(names[2]) - TW @ TRIGGER_PAD).length * 1000, 1), "до пистолета, мм", round(SKIN.depth(names), 2))


def thumb_fit(tip_target, label):
    """Большой правой: прямой палец вдоль левого бока рамки к заданному месту (на полпальца от поверхности). Кисть на
    широкой рукояти: сустав большого оказывается в ней — основание (thumb.01) отводится от ладони сдвигом (так владелец
    ставит большой в своих хватах), пока палец не выйдет из пистолета."""
    names = ["thumb.01.R", "thumb.02.R", "thumb.03.R"]
    base = arms.pose.bones[names[0]].matrix_basis.copy()
    hand_rest = arms.data.bones["hand.R"].matrix_local.to_3x3()
    hp = arms.pose.bones["hand.R"].matrix.to_3x3() @ hand_rest.transposed()        # покой → поза кисти (арматура)
    par = arms.pose.bones[names[0]].parent
    n_loc = (arms.data.bones[names[0]].matrix_local.to_3x3().transposed()
             @ (par.bone.matrix_local.to_3x3() @ (par.matrix.to_3x3().transposed() @ (hp @ PALM_N["R"])))).normalized()
    t = Vector(tip_target) * 1000.0 + Vector((0.0, 8.5, 0.0))

    def pose(shift):
        m = base.copy()
        m.translation = base.translation + n_loc * shift
        arms.pose.bones[names[0]].matrix_basis = m
        reset(names[1:])
        aim(names[1], t)
        aim(names[2], t + Vector((16.0, -1.0, 1.0)))
    shift = 0.0
    pose(shift)
    while SKIN.depth(names[1:]) < -0.7 and shift < 0.024:
        shift += 0.001
        pose(shift)
    log(f"большой правой ({label}): основание отведено от ладони на, мм", round(shift * 1000), "сустав, мм", [round(v, 1) for v in head_mm(names[1])],
        "подушечка от места, мм", round((pad_point('thumb.03.R') - TW @ Vector(tip_target)).length * 1000, 1), "до пистолета, мм", round(SKIN.depth(names[1:]), 2))


def report(side="R"):
    out = {}
    for n in sorted(SKIN.local):
        if not n.endswith("." + side) or n.startswith(("upper_arm", "forearm")):
            continue
        d = WHOLE.dist(SKIN.src_mm(n))
        out[n] = (round(float(d.min()), 2), int((d < 1.0).sum()), len(d))
    worst = min(v[0] for v in out.values())
    log(f"кисть {side}: глубже 2 мм:", {k: v[0] for k, v in out.items() if v[0] < -2.0})
    log(f"кисть {side}: наименьшее расстояние по костям (мм, точек ближе 1 мм / всего):",
        {k: v for k, v in out.items() if v[1] or v[0] < 3})
    log(f"кисть {side}: глубже всего, мм", worst)
    return worst


def key_all(frame_no):
    for pb in arms.pose.bones:
        pb.keyframe_insert("location", frame=frame_no)
        pb.keyframe_insert("rotation_euler", frame=frame_no)
        pb.keyframe_insert("scale", frame=frame_no)


# ================================================================ сборка
def right_hand():
    rest_check()
    arm_names = [n for n in PM["frames"]["ready"]["basis"] if n in arms.pose.bones and n not in ("Weapon_CTRL", "ik_hand.R", "ik_hand.L")]
    apply_pm("ready", [n for n in arm_names if not n.endswith(".L") or n in ("upper_arm.L", "pole.L")])
    # ладонь владельца сложена «лодочкой» под узкую рукоять ПМ — под широкую рукоять АСТЕН-919 раскрыть наполовину
    for n in ("palm.01.R", "palm.02.R", "palm.03.R", "palm.04.R"):
        pb = arms.pose.bones[n]
        loc, rot, _ = pb.matrix_basis.decompose()
        m = Matrix.Identity(3).to_quaternion().slerp(rot, 1.0 - (1.0 if n == "palm.01.R" else PALM_OPEN)).to_matrix().to_4x4()
        m.translation = loc
        pb.matrix_basis = m
    update()
    fr = PM["frames"]["ready"]["pose"]
    pm_frame = Matrix(fr["Frame"])
    hand_pm = pm_frame.inverted() @ Matrix(fr["hand.R"])
    log("ПМ: кисть в осях ПМ, мм", [round(v * 1000, 1) for v in hand_pm.translation],
        "ладонь правой в покое смотрит (арматура)", [round(v, 2) for v in PALM_N["R"]],
        "оси сгиба f_middle .01/.02/.03 (локальные)", [[round(v, 2) for v in flex_axis(f"f_middle.{j:02d}.R", "R")] for j in (1, 2, 3)])
    F_pm = frame(PM_WEB, PM_UP, Vector((1, 0, 0)))
    F_as = frame(WEB, GRIP_UP, Vector((0, 1, 0)))
    H = F_pm.inverted() @ hand_pm
    H.translation = H.translation * PALM_K
    world = TW @ F_as @ H
    left = set_hand("R", world)
    log("кисть по опорным местам: запястье в осях пистолета, мм", [round(v * 1000, 1) for v in (TWI @ hand_world('R')).translation],
        "IK не дотянулась, мм", round(left * 1000, 2))
    left = set_hand("R", fit_palm())
    if left > 0.001:
        ua = arms.pose.bones["upper_arm.R"]                 # плечо к кисти ровно настолько, чтобы дотянуться
        for _ in range(6):
            gap = arms.pose.bones["ik_hand.R"].head - arms.pose.bones["hand.R"].head
            if gap.length < 0.0005:
                break
            ua.matrix = Matrix.Translation(gap * 1.05) @ ua.matrix
            update()
        log("плечо подано к кисти; остаток, мм", round((arms.pose.bones['ik_hand.R'].head - arms.pose.bones['hand.R'].head).length * 1000, 2))
    if "raw" not in ARGS:
        for f in ("f_middle", "f_ring", "f_pinky"):
            close_finger(f)
        thumb_fit(THUMB_TIP, "вдоль рамки")
        index_ready()


def left_away():
    """Левая убрана: вниз-влево, за кадр; пальцы — как в позе мастера."""
    ik = arms.pose.bones["ik_hand.L"]
    m = AW @ ik.matrix
    m.translation = Vector((0.20, -0.16, 1.36))
    ik.matrix = AWI @ m
    update()


def main():
    S.render.fps = 30
    if STAGE != "right":
        raise SystemExit("этап: right (левая — после приёмки правой)")
    for pb in arms.pose.bones:
        pb.rotation_mode = "XYZ"
    right_hand()
    left_away()
    act = bpy.data.actions.new(ACTION)
    act.use_fake_user = True
    ad = arms.animation_data or arms.animation_data_create()
    ad.action = act
    key_all(1)
    w1 = report()
    if "raw" not in ARGS:
        index_trigger()
    key_all(11)
    w2 = report()
    for fc in [fc for layer in act.layers for strip in layer.strips for bag in strip.channelbags for fc in bag.fcurves]:
        for kp in fc.keyframe_points:
            kp.interpolation = "BEZIER"
            kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
    for m in list(S.timeline_markers):
        S.timeline_markers.remove(m)
    S.timeline_markers.new("Хват: палец вдоль рамки", frame=1)
    S.timeline_markers.new("Палец на спуске", frame=11)
    S.frame_start, S.frame_end = 1, 11
    S.frame_set(1)
    txt = bpy.data.texts.new("АСТЕН-919 — хват (читать)")
    txt.from_string(
        "АСТЕН-919 (wpn_hg_02): хват рук от первого лица — этап 1, только правая (левая убрана вниз-влево).\n\n"
        "Действие ASTEN919_Grip_v01 (FPS_ArmsRig): кадр 1 — указательный вдоль рамки, кадр 11 — на спуске.\n"
        "Правка: Pose Mode, нужный кадр, кости пальцев — повороты; кисть целиком — цель ik_hand.R (дочерняя Weapon_CTRL);\n"
        "ключ — I. Камера «FPS • Camera» — вид из глаз (54° по вертикали, как в игре).\n"
        "Пистолет — игровая сетка на костях ASTEN919_WeaponRig (затвор, спуск, рычаг задержки, кнопка и магазин).\n"
        "Клипы строятся от этого действия скриптом tools/asten919/clips — после приёмки хвата.\n")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT), compress=True)
    log("сохранено", OUT, "глубже всего, мм: кадр 1", w1, "кадр 11", w2)


main()
