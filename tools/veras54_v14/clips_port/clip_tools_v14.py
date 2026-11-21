"""ВЕРАС-54 — панель клипов рук в Blender (боковая панель 3D-вида, клавиша N, вкладка «ВЕРАС»).

Всё правится в Blender, без скриптов:
  «Позы (хваты)»   — кадры-заготовки хватов: 1 — ХВАТ (всё: обе руки, пальцы, где автомат в кадре); дальше по одной
                     позе на кадр (правая: указательный, спуск, переводчик, рукоятка затвора; левая: магазин, проверка,
                     фонарь, глушитель, рукоятки ВАРН, магазины 45 и 60). Кнопка позы — перейти на её кадр (магазин,
                     рукоятка, глушитель, фонарь — какие нужны для этой позы — появятся сами). Поставил позу — ключ (I / K).
  клип из списка   — открывает клип: ключи на шкале с кадра 1. Двигать ключи во времени, наклонять автомат (кнопка
                     «Автомат»), вести кисти, затвор и магазин — как обычную анимацию. Маркеры фаз (catch, mag_new …)
                     можно двигать: они запоминаются, когда открываешь другой клип.
  «Детали автомата» — ползунки затвора, защёлки, спуска, переводчика, числа патронов: ползунок — положение, ромбик рядом —
                     ключ на этом кадре.
  «Выбрать кость»  — кнопки выделяют нужную кость: дальше G — двигать, R — вращать, K — ключ.
  «Хваты из поз → во все клипы» — переносит поправленные позы в клипы, движение и ваши ключи не трогает:
       пальцы и кости рук — там, где ключ клипа совпадал с прежней позой, ставится новая поза;
       кисть — там, где она стояла «как в позе» (тот же поворот), её место меняется так же, как в позе;
       автомат — если его место на кадре позы (ХВАТ, магазин, рукоятка затвора, проверка, глушитель) изменилось, ключи
       автомата в клипах, стоявшие возле этой позы, сдвигаются на ту же поправку;
       магазин (и глушитель) в левой кисти — его путь у автомата (качок в шахте, удар по защёлке) не меняется, кисть
       встаёт вокруг него так, как вы поставили её в позе «на магазине».
     Потом сама собирает версии.
  «Версия» (рукоятка нет / ВАРН V1 / ВАРН V2, магазин 30 / 45 / 60) — какую версию клипа открыть. Правится только
       основной клип (без рукоятки, магазин 30): версии собирает кнопка «Собрать версии» — левая рука в них берёт позы
       «на рукоятке ВАРН …» и «на магазине 45 / 60», движение — от основного клипа. Ключи версий руками не править —
       кнопка их перепишет.

v02 — автомат v14 (новая игровая сетка, 19.11). Клипы установки обвесов (глушитель, фонарь) на v14 не перенесены: они в
группе «Не перенесено на v14», кнопки панели их не трогают. Сборки клипов заново из таблиц для v02 НЕТ — таблицы генератора
написаны под старую модель и затёрли бы ваши правки (tools/veras54_v14/clips/regenerate.cmd к этому файлу не применять).
Кадр 91 — «большой на защёлке магазина»: всё, кроме большого пальца левой, повторяет позу 41 (кнопка переноса
ставит это сама); в клипах на кадрах нажатия защёлки берётся только большой палец. При хвате позы 41 21.11
палец до лапки не доставал ~2,3 см — кисть на магазине стоит низко.
Быстрые перезарядки (21.11): удар новым магазином по защёлке — фазы aim / strike / old_falls / freeze_end на шкале;
новый магазин повёрнут ~50° и бьёт передним верхним углом в кончик лапки (лапка ниже скобы всего ~4 мм).

Этот текст лежит и в репозитории игры: tools/veras54_v14/clips_port/clip_tools_v14.py (перенос кладёт его в файл v02).
Панель не появилась — нажать «Allow Execution» в полоске вверху окна или здесь, в редакторе текста, кнопку ▶.
"""
import json
import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

POSES = "VERAS54_Poses"
APPLIED = "VERAS54_Poses_applied"                    # снимок поз, уже перенесённых в клипы
PREFIX = "VERAS54_"
SEP = "__"                                            # версия: VERAS54_<Клип>__<рукоятка>_<магазин>
ARMS, GUN, ROOT, MAG = "FPS_ArmsRig", "VERAS54_WeaponRig", "VERAS54", "Magazine"
PANEL_TEXT = "veras54_panel.py"
POSE_FRAMES = dict(grip=1, frame=6, pressed=11, sel_down=16, sel_up=21, r_open=26, hook_pre=31, hook=36,
                   mag=41, pre=46, free=51, check=56, light=61, supp=66, varn_v1=71, varn_v2=76, mag45=81, drum60=86,
                   mag_latch=91)
POSE_RU = dict(grip="ХВАТ", frame="П: указательный вдоль корпуса", pressed="П: спуск выжат",
               sel_down="П: большой на переводчике сверху", sel_up="П: большой под переводчиком",
               r_open="П: кисть раскрыта (в пути)", hook_pre="П: пальцы перед рукояткой затвора",
               hook="П: крюк на рукоятке затвора", mag="Л: на магазине", pre="Л: пальцы раскрываются к магазину",
               free="Л: кисть свободна (в пути)", check="Л: магазин у глаз, хват ниже", light="Л: большой на кнопке фонаря (не перенесено на v14)",
               supp="Л: держит глушитель (не перенесено на v14)", varn_v1="Л: на рукоятке ВАРН V1", varn_v2="Л: на рукоятке ВАРН V2",
               mag45="Л: на магазине 45", drum60="Л: на барабане 60",
               mag_latch="Л: на магазине, большой на защёлке (черновой)")
NOT_PORTED = "not_ported_v14"                         # свойство действия: клип / поза на v14 не перенесены (обвесы)
# что показать на кадре позы (рукоятка, магазин, фонарь)
POSE_VARIANT = dict(light=dict(light=True), varn_v1=dict(grip="varn_v1"), varn_v2=dict(grip="varn_v2"),
                    mag45=dict(mag="45"), drum60=dict(mag="60"))
GUN_REF = ("mag", "hook", "check", "supp")            # кадры поз, где стоит и положение автомата
# Ключ клипа может совпасть сразу с несколькими позами: у «пальцы перед рукояткой» (31) кисть, плечо, локоть и автомат —
# копия «крюка» (36), а генератор ставит их ключи от «крюка». Поэтому при совпадении «крюк» проверяется раньше.
EXACT_ORDER = tuple(sorted(POSE_FRAMES, key=lambda n: (n == "hook_pre", POSE_FRAMES[n])))
ARM_FOLLOW = ("upper_arm", "pole")                    # плечо и локоть берутся из той позы, по которой стоит кисть на кадре
GUN_NEAR_DEG, GUN_NEAR_M = 14.0, 0.05                 # ключ автомата «возле позы»: ближе этого
GRIPS = (("", "без рукоятки"), ("varn_v1", "ВАРН V1"), ("varn_v2", "ВАРН V2"))
MAGS = (("30", "магазин 30"), ("45", "магазин 45"), ("60", "барабан 60"))
COLLS = {"grip:varn_v1": ("Рукоятка ВАРН V1",), "grip:varn_v2": ("Рукоятка ВАРН V2",),
         "mag:30": ("Магазин 30 (штатный)", "Старый магазин 30"), "mag:45": ("Магазин 45", "Старый магазин 45"),
         "mag:60": ("Барабан 60", "Старый магазин 60"), "light": ("Фонарь ДОЗОР (левая планка)",)}
FINGER = ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky")
# Кнопки «выбрать кость»: подпись → (риг, кость). Кости автомата мелкие и сидят внутри модели — мышью их не поймать.
PICK = (("Автомат", ARMS, "Weapon_CTRL"), ("Левая кисть", ARMS, "ik_hand.L"), ("Правая кисть", ARMS, "ik_hand.R"),
        ("Левый локоть", ARMS, "pole.L"), ("Правый локоть", ARMS, "pole.R"), ("Левое плечо", ARMS, "upper_arm.L"),
        ("Правое плечо", ARMS, "upper_arm.R"), ("Магазин", GUN, "Magazine_Control"), ("Старый магазин", GUN, "SpareMag"),
        ("Глушитель", GUN, "Suppressor_Control"), ("Гильза задержки", GUN, "JamCase"), ("Дульное устройство", GUN, "MuzzleAttachment"),
        ("Магазин в кисти", ARMS, "mag.L"), ("Глушитель в кисти", ARMS, "supp.L"))
# Ползунки деталей: (подпись, объект, свойство). Детали ходят драйверами от этих свойств — ключ ставится на свойство.
SLIDERS = (("Затвор (0 — закрыт, 1 — до упора)", ROOT, '["Bolt pull"]'),
           ("Защёлка магазина (1 — нажата)", ROOT, '["Magazine latch press"]'),
           ("Спуск (1 — выжат)", ROOT, '["Trigger pull"]'),
           ("Режим огня: 1 — АВ, 3 — «2», 2 — ОД", ROOT, '["Fire mode"]'),
           ("Переводчик: откуда (режим)", ROOT, '["Selector from mode"]'),
           ("Переводчик: доля перехода", ROOT, '["Selector blend"]'),
           ("Патронов в магазине", MAG, '["Rounds remaining"]'))


# ------------------------------------------------------------------ действия, кривые
def rigs():
    return bpy.data.objects.get(ARMS), bpy.data.objects.get(GUN)


def anim_objects():
    return [o for o in (bpy.data.objects.get(n) for n in (ARMS, GUN, ROOT, MAG)) if o is not None]


def slot_of(act, ob):
    return next((s for s in act.slots if s.name_display == ob.name), None)


def bag_of(act, ob):
    slot = slot_of(act, ob)
    if slot is None:
        return None
    for layer in act.layers:
        for strip in layer.strips:
            bag = strip.channelbag(slot)
            if bag is not None:
                return bag
    return None


def is_version(act):
    return SEP in act.name


def clip_actions(versions=False):
    acts = [a for a in bpy.data.actions if a.name.startswith(PREFIX) and a.name not in (POSES, APPLIED)
            and (versions or not is_version(a))]
    return sorted(acts, key=lambda a: (a.get("order", 999), a.name))


def version_name(base, grip, mag):
    return f"{base}{SEP}{grip or 'nogrip'}_{mag}"


def variant_of(act):
    try:
        return json.loads(act.get("variant", "{}"))
    except ValueError:
        return {}


def bone_curves(bag):
    out = {}
    for fc in bag.fcurves if bag else ():
        dp = fc.data_path
        if dp.startswith('pose.bones["') and "]." in dp:
            prop = dp.rsplit(".", 1)[1]
            if prop in ("location", "rotation_quaternion", "rotation_euler"):
                out.setdefault(dp.split('"')[1], {})[(prop, fc.array_index)] = fc
    return out


def rot_prop(pb):
    return "rotation_quaternion" if pb.rotation_mode == "QUATERNION" else "rotation_euler"


def read(cv, pb, f):
    """Поза кости (место, поворот) на кадре f по кривым действия → матрица."""
    def val(prop, i, default):
        fc = cv.get((prop, i))
        return fc.evaluate(f) if fc is not None else default
    loc = Vector([val("location", i, 0.0) for i in range(3)])
    if pb.rotation_mode == "QUATERNION":
        rot = Quaternion([val("rotation_quaternion", i, 1.0 if i == 0 else 0.0) for i in range(4)])
        rot.normalize()
    else:
        rot = Euler([val("rotation_euler", i, 0.0) for i in range(3)], pb.rotation_mode)
    return Matrix.LocRotScale(loc, rot, None)


def write(cv, pb, f, M, bag=None, insert=False):
    """Записать позу кости в ключи на кадре f (ручки кривых едут вместе с ключом). insert — ставить ключ, если его нет."""
    loc = M.translation
    rp = rot_prop(pb)
    if rp == "rotation_quaternion":
        old = Quaternion([cv[(rp, i)].evaluate(f) if (rp, i) in cv else (1.0 if i == 0 else 0.0) for i in range(4)])
        rot = M.to_quaternion()
        if rot.dot(old) < 0.0:
            rot.negate()
        vals = {("location", i): loc[i] for i in range(3)} | {(rp, i): rot[i] for i in range(4)}
    else:
        old = Euler([cv[(rp, i)].evaluate(f) if (rp, i) in cv else 0.0 for i in range(3)], pb.rotation_mode)
        rot = M.to_euler(pb.rotation_mode, old)
        vals = {("location", i): loc[i] for i in range(3)} | {(rp, i): rot[i] for i in range(3)}
    for key, v in vals.items():
        fc = cv.get(key)
        if fc is None:
            if not (insert and bag is not None):
                continue
            fc = bag.fcurves.new(f'pose.bones["{pb.name}"].{key[0]}', index=key[1], group_name=pb.name)
            cv[key] = fc
        kp = next((k for k in fc.keyframe_points if abs(k.co[0] - f) < 1e-3), None)
        if kp is None:
            if insert:                                # без options: «REPLACE» только заменяет имеющиеся ключи, новых не ставит
                fc.keyframe_points.insert(f, v)
                fc.update()
            continue
        d = v - kp.co[1]
        kp.co[1] = v
        kp.handle_left[1] += d
        kp.handle_right[1] += d
        fc.update()


def close(a, b, eps=2e-4):
    return max(abs(x - y) for ra, rb in zip(a, b) for x, y in zip(ra, rb)) < eps


def apart(a, b):
    """Насколько две позы далеки: (угол°, расстояние м)."""
    return math.degrees(a.to_quaternion().rotation_difference(b.to_quaternion()).angle), (a.translation - b.translation).length


# ------------------------------------------------------------------ позы
def bone_sets(arms):
    names = [pb.name for pb in arms.pose.bones]
    fing = lambda n: n.split(".")[0] in FINGER  # noqa: E731
    r_index = {n for n in names if n.startswith("f_index") and n.endswith(".R")}
    right = {n for n in names if n.endswith(".R")}
    left = {n for n in names if n.endswith(".L")}
    wc = {"Weapon_CTRL"}
    own = dict(frame=r_index, pressed=r_index, sel_down=right, sel_up=right, r_open=right, hook_pre=right | wc,
               hook=right | wc, mag=left | wc, pre=left, free=left, check=left | wc, light=left, supp=left | wc,
               varn_v1=left, varn_v2=left, mag45=left, drum60=left, mag_latch={n for n in left if n.startswith("thumb")})
    return own, {n for n in names if fing(n)}, left, right


def pose_table(act, arms):
    cv = bone_curves(bag_of(act, arms))
    return {name: {pb.name: read(cv.get(pb.name, {}), pb, f) for pb in arms.pose.bones} for name, f in POSE_FRAMES.items()}


def held_in_hand(context, arms, wr, poses, pose, bone_hand, bone_held):
    """Как деталь (магазин / глушитель) лежит в левой кисти (кость mag.L / supp.L) — по кадру позы: деталь стоит на месте,
    кисть вокруг неё; кисть берётся на цели IK (в клипах она до неё дотягивается)."""
    if bone_hand not in arms.pose.bones or wr is None:
        return None
    S = context.scene
    keep = [(ob, ob.animation_data.action, ob.animation_data.action_slot) for ob in (arms, wr) if ob.animation_data]
    frame = S.frame_current
    cons = [pb.constraints.get("В левой кисти") for pb in wr.pose.bones]
    was = [c.enabled if c else None for c in cons]
    try:
        for ob in (arms, wr):
            ad = ob.animation_data or ob.animation_data_create()
            ad.action = poses
            ad.action_slot = slot_of(poses, ob)
        for c in cons:
            if c:
                c.enabled = False
        S.frame_set(POSE_FRAMES[pose])
        context.view_layer.update()
        hand, ikt = arms.pose.bones["hand.L"], arms.pose.bones["ik_hand.L"]
        reached = hand.matrix.copy()
        reached.translation = ikt.matrix.translation
        rel = arms.data.bones["hand.L"].matrix_local.inverted() @ arms.data.bones[bone_hand].matrix_local
        return ((reached @ rel).inverted() @ arms.matrix_world.inverted() @ wr.matrix_world
                @ wr.pose.bones[bone_held].matrix)
    finally:
        for c, w in zip(cons, was):
            if c:
                c.enabled = w
        for ob, act, slot in keep:
            ob.animation_data.action = act
            if act is not None and slot is not None:
                ob.animation_data.action_slot = slot
        S.frame_set(frame)
        context.view_layer.update()


# поза, от которой берётся всё, кроме «своего»: «большой на защёлке» (91) — та же кисть, что «на магазине» (41),
# свой у неё только большой палец левой (в клипах на кадрах нажатия защёлки ставится только он)
POSE_BASE = dict(mag_latch="mag")
MAG_POSES = ("mag", "check", "mag45", "drum60")       # позы, где своё место магазина в кисти (mag.L)


def tidy_poses(context, arms, wr, poses, say):
    """Позы владельца → таблица; на кадрах поз всё, кроме «своего» в этой позе, приводится к хвату кадра 1; место
    магазина и глушителя в кисти снимается с кадров поз «на магазине» и «держит глушитель»."""
    own, _, _, _ = bone_sets(arms)
    bag = bag_of(poses, arms)
    cv = bone_curves(bag)
    T = pose_table(poses, arms)
    held = {p: held_in_hand(context, arms, wr, poses, p, "mag.L", "Magazine_Control") for p in MAG_POSES}
    supp = held_in_hand(context, arms, wr, poses, "supp", "supp.L", "Suppressor_Control")
    for name, f in POSE_FRAMES.items():
        for pb in arms.pose.bones:
            n = pb.name
            want = T[name][n]
            if n == "mag.L" and held.get("mag") is not None:
                want = held.get(name) if held.get(name) is not None else held["mag"]
            elif n == "supp.L" and supp is not None:
                want = supp
            elif name != "grip" and n not in own[name]:
                want = T[POSE_BASE.get(name, "grip")][n]
            if not close(want, T[name][n], 1e-6):
                write(cv.setdefault(n, {}), pb, f, want, bag, insert=True)
                T[name][n] = want.copy()
    return T


# ------------------------------------------------------------------ перенос поз в клипы
SHIFTABLE = {"ik_hand.L": ("grip", "mag", "pre", "free", "check", "light", "supp", "varn_v1", "varn_v2", "mag45", "drum60",
                          "mag_latch"),
             "ik_hand.R": ("grip", "hook", "hook_pre", "r_open", "sel_down", "sel_up")}


def reference(bone, K, OLD, hand=None):
    """К какой позе относится ключ клипа: имя позы или None (ключ свой — не трогать). hand — поза, по которой на этом
    кадре стоит кисть той же руки (для плеча и локтя: в «крюке» они те же, что в «хвате», и без подсказки ушли бы
    к «хвату» — правка локтя в позе на кадрах клипа не появилась бы)."""
    if hand is not None:
        if close(K, OLD[hand][bone]):
            return hand, True
        if bone.split(".")[0] in ARM_FOLLOW:         # плечо подано ключом (рука не дотягивалась) — едет вслед за позой
            return hand, False
    for name in EXACT_ORDER:
        if close(K, OLD[name][bone]):
            return name, True
    if bone in SHIFTABLE:                             # кисть стоит «как в позе», но сдвинута (магазин идёт в шахте и т. п.)
        for name in SHIFTABLE[bone]:
            if apart(K, OLD[name][bone])[0] < 0.2:
                return name, False
    if bone == "Weapon_CTRL":                         # автомат: возле позы с положением автомата, иначе считается от хвата
        best = None
        for name in GUN_REF:
            ang, dist = apart(K, OLD[name][bone])
            if ang < GUN_NEAR_DEG and dist < GUN_NEAR_M and (best is None or ang + dist * 300 < best[0]):
                best = (ang + dist * 300, name)
        return (best[1] if best else "grip"), False
    return None, False


def remap(act, arms, OLD, NEW):
    """Ключи действия, стоящие «по позам» OLD, переводятся на позы NEW. → сколько ключей поправлено."""
    cv_all = bone_curves(bag_of(act, arms))

    def key_frames(cv, pb):
        rp = rot_prop(pb)
        return sorted({round(kp.co[0], 3) for (prop, _i), fc in cv.items() if prop in ("location", rp)
                       for kp in fc.keyframe_points})

    hand_ref = {}                                     # по какой позе стоит кисть на каждом её ключе (до любой записи)
    for s in ("L", "R"):
        pb, cv = arms.pose.bones.get(f"ik_hand.{s}"), cv_all.get(f"ik_hand.{s}")
        hand_ref[s] = {f: reference(pb.name, read(cv, pb, f), OLD)[0] for f in key_frames(cv, pb)} if pb and cv else {}

    def hand_at(side, f):
        """Поза кисти на кадре; ключа кисти на нём нет — по ближайшему её ключу."""
        refs = hand_ref.get(side) or {}
        if f in refs or not refs:
            return refs.get(f)
        return refs[min(refs, key=lambda k: (abs(k - f), k))]

    # Кадры, где левая держит деталь (магазин, старый магазин, глушитель): путь детали у автомата задан клипом
    # (качок у шахты, глушитель на резьбе), меняется только то, как её держит кисть. Запомнить кисть и место детали
    # в кисти до переноса, после — поставить кисть вокруг детали.
    ikL, cv_ik = arms.pose.bones.get("ik_hand.L"), cv_all.get("ik_hand.L")
    held = held_frames(act, key_frames(cv_ik, ikL)) if ikL and cv_ik else {}
    before = {f: (read(cv_ik, ikL, f), read(cv_all.get(h, {}), arms.pose.bones[h], f)) for f, h in held.items()}

    n = 0
    for pb in arms.pose.bones:
        cv = cv_all.get(pb.name)
        if not cv:
            continue
        side = pb.name.rsplit(".", 1)[-1] if pb.name.split(".")[0] in ARM_FOLLOW else None
        plan = []                                     # сначала всё прочитать, потом писать: запись сдвигает кривые
        for f in key_frames(cv, pb):
            K = read(cv, pb, f)
            ref, exact = reference(pb.name, K, OLD, hand_at(side, f) if side else None)
            if ref is None:
                continue
            Po, Pn = OLD[ref][pb.name], NEW[ref][pb.name]
            if close(Po, Pn, 1e-6):
                continue
            plan.append((f, Pn.copy() if exact else K @ Po.inverted() @ Pn))
        for f, M in plan:
            write(cv, pb, f, M)
        n += len(plan)
    if held:
        cv_all = bone_curves(bag_of(act, arms))
        for f, h in held.items():
            k_o, m_o = before[f]
            m_n = read(cv_all.get(h, {}), arms.pose.bones[h], f)
            B = hold_link(arms, h)
            K = k_o @ B @ m_o @ m_n.inverted() @ B.inverted()
            if close(K, read(cv_all["ik_hand.L"], ikL, f), 1e-6):
                continue
            write(cv_all["ik_hand.L"], ikL, f, K)
            n += 1
    return n


HELD = (("Magazine_Control", "mag.L"), ("SpareMag", "mag.L"), ("Suppressor_Control", "supp.L"))


def held_frames(act, frames):
    """Кадры (из frames), где левая держит деталь — ограничение «В левой кисти» включено: → {кадр: кость места в кисти}."""
    _arms, wr = rigs()
    bag = bag_of(act, wr) if wr is not None else None
    if bag is None:
        return {}
    out = {}
    for part, hold in HELD:
        fc = bag.fcurves.find(f'pose.bones["{part}"].constraints["В левой кисти"].influence')
        if fc is None:
            continue
        for f in frames:
            if f not in out and fc.evaluate(f) >= 0.5:
                out[f] = hold
    return out


def hold_link(arms, hold):
    """Место детали в кисти против цели кисти: кисть (hand.L) стоит на цели ik_hand.L (поворот — Copy Rotation),
    кость места (mag.L / supp.L) — дочерняя кисти: деталь = цель · link · ключ кости места."""
    b = arms.data.bones
    return b["hand.L"].matrix_local.inverted() @ b[hold].matrix_local


def sync(context, say=print):
    """Позы → клипы, потом версии. → (сколько ключей поправлено, в скольких клипах) или None, если нечем сравнивать."""
    arms, wr = rigs()
    poses, applied = bpy.data.actions.get(POSES), bpy.data.actions.get(APPLIED)
    if arms is None or poses is None:
        say("Нет рига рук или действия поз")
        return None
    if applied is None:
        say("В файле нет снимка прежних поз — один раз запустите tools\\veras54_v14\\clips\\rebuild.cmd")
        return None
    OLD = pose_table(applied, arms)
    NEW = tidy_poses(context, arms, wr, poses, say)
    changed = sorted({f"{POSE_FRAMES[name]} ({POSE_RU[name]})" for name in POSE_FRAMES for n in NEW[name]
                      if not close(OLD[name][n], NEW[name][n])}, key=lambda s: int(s.split()[0]))
    total, clips_hit = 0, 0
    for act in clip_actions():
        if act.get(NOT_PORTED):
            continue
        n = remap(act, arms, OLD, NEW)
        if n:
            clips_hit += 1
            total += n
            say(f"{act.name[len(PREFIX):]}: поправлено ключей {n}")
    bpy.data.actions.remove(applied)
    snap = poses.copy()
    snap.name = APPLIED
    snap.use_fake_user = True
    if changed:
        say("Изменённые позы, кадры: " + ", ".join(changed))
    nv = build_versions(context, say, NEW)
    say(f"версий собрано: {nv}")
    return total, clips_hit


# ------------------------------------------------------------------ версии (рукоятки ВАРН, магазины 45 / 60)
def variant_table(T, grip, mag, left):
    """Позы для версии: «ХВАТ» левой — на рукоятке; «на магазине» — на магазине 45 / 60; место магазина в кисти — его."""
    V = {p: dict(bones) for p, bones in T.items()}
    if grip:
        for n in left:
            V["grip"][n] = T[grip][n]
    mp = {"45": "mag45", "60": "drum60"}.get(mag)
    if mp:
        for n in left:
            V["mag"][n] = T[mp][n]
        for p in V:
            V[p]["mag.L"] = T[mp]["mag.L"]
    return V


def build_versions(context, say=print, T=None):
    """Версии каждого основного клипа по его списку (свойство versions: grip — рукоятки, mag — магазины)."""
    arms, _wr = rigs()
    poses = bpy.data.actions.get(POSES)
    if arms is None or poses is None:
        return 0
    T = T or pose_table(poses, arms)
    _own, _fing, left, _right = bone_sets(arms)
    left = left - {"mag.L", "supp.L"}
    for a in [a for a in bpy.data.actions if is_version(a)]:
        b = bpy.data.actions.get(a.get("base", ""))
        if b is not None and b.get(NOT_PORTED):
            continue                                  # версии не перенесённых клипов остаются как были
        bpy.data.actions.remove(a)
    count = 0
    for base in clip_actions():
        if base.get(NOT_PORTED):
            continue
        kinds = base.get("versions", "")
        base_var = variant_of(base)
        grips = [g for g, _ in GRIPS] if "grip" in kinds else [""]
        mags = [m for m, _ in MAGS] if "mag" in kinds else [base_var.get("mag", "30")]
        for g in grips:
            for m in mags:
                if g == base_var.get("grip", "") and m == base_var.get("mag", "30"):
                    continue
                act = base.copy()
                act.name = version_name(base.name, g, m)
                act.use_fake_user = True
                act["variant"] = json.dumps(dict(base_var, grip=g, mag=m))
                act["base"] = base.name
                act["order"] = base.get("order", 999)
                act["group"] = base.get("group", "")
                remap(act, arms, T, variant_table(T, g, m, left))
                count += 1
    return count


# ------------------------------------------------------------------ видимость вариантов
def show_variant(grip="", mag="30", light=False):
    want = {f"grip:{grip}" if grip else "", f"mag:{mag}"} | ({"light"} if light else set())
    for key, names in COLLS.items():
        on = key in want
        for n in names:
            c = bpy.data.collections.get(n)
            if c is not None:
                c.hide_viewport = c.hide_render = not on
                for lc in _layer_colls(bpy.context.view_layer.layer_collection, n):
                    lc.hide_viewport = not on


def _layer_colls(lc, name):
    if lc.collection.name == name:
        yield lc
    for ch in lc.children:
        yield from _layer_colls(ch, name)


# ------------------------------------------------------------------ открыть позы / клип
def last_key(act, ob):
    bag = bag_of(act, ob)
    return max((kp.co[0] for fc in (bag.fcurves if bag else ()) for kp in fc.keyframe_points), default=1.0)


def save_marks(act, scene):
    if act is not None and act.name.startswith(PREFIX) and act.name not in (POSES, APPLIED) and not is_version(act):
        act["marks"] = json.dumps({m.name: m.frame for m in scene.timeline_markers}, ensure_ascii=False)


def load_marks(act, scene):
    for m in list(scene.timeline_markers):
        scene.timeline_markers.remove(m)
    if act.name == POSES:
        marks = {f"ПОЗА {POSE_RU[name]}": f for name, f in POSE_FRAMES.items()}
    else:
        marks = json.loads(act.get("marks", "{}"))
    for name, f in marks.items():
        scene.timeline_markers.new(name, frame=int(f))


def open_action(context, name):
    arms, wr = rigs()
    act = bpy.data.actions.get(name)
    if arms is None or act is None:
        return False
    S = context.scene
    save_marks(arms.animation_data.action if arms.animation_data else None, S)
    for ob in anim_objects():
        ad = ob.animation_data or ob.animation_data_create()
        if ad.use_tweak_mode:
            ad.use_tweak_mode = False
        slot = slot_of(act, ob)
        if slot is None:                              # у действия нет слота этого объекта — свойства как в покое
            ad.action = None
            continue
        ad.action = act
        ad.action_slot = slot
        ad.action_extrapolation = "HOLD"
        ad.action_blend_type = "REPLACE"
        ad.action_influence = 1.0
    load_marks(act, S)
    S.frame_start = 1
    if name == POSES:
        S.frame_end = max(POSE_FRAMES.values())
        show_variant()
    else:
        S.frame_end = int(math.ceil(max(last_key(act, arms), 2.0)))
        v = variant_of(act)
        show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    S["veras_open"] = name
    S.frame_set(1)
    return True


def goto_pose(context, pose):
    if context.scene.get("veras_open") != POSES:
        open_action(context, POSES)
    v = POSE_VARIANT.get(pose, {})
    show_variant(v.get("grip", ""), v.get("mag", "30"), bool(v.get("light")))
    context.scene.frame_set(POSE_FRAMES[pose])


def set_bone_select(pb, on):
    if hasattr(pb, "select"):                         # Blender 5: выделение хранится у кости позы
        pb.select = on
    else:
        pb.bone.select = on


def pick_bone(context, rig_name, bone):
    """Выделить одну кость (оба рига — в режиме поз, чтобы ключи рук и автомата были видны на шкале вместе)."""
    arms, wr = rigs()
    ob = bpy.data.objects.get(rig_name)
    if ob is None or bone not in ob.pose.bones:
        return False
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in (arms, wr):
        if o is not None:
            o.hide_set(False)
            o.select_set(True)
    context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="POSE")
    for o in (arms, wr):
        for pb in (o.pose.bones if o is not None else ()):
            set_bone_select(pb, False)
    set_bone_select(ob.pose.bones[bone], True)
    ob.data.bones.active = ob.data.bones[bone]
    return True


# ------------------------------------------------------------------ интерфейс
class VERAS_OT_pick(bpy.types.Operator):
    bl_idname = "veras.pick"
    bl_label = "Выбрать кость"
    bl_description = "Выделить эту кость: дальше G — двигать, R — вращать, K — ключ"
    bl_options = {"REGISTER", "UNDO"}
    rig: bpy.props.StringProperty()
    bone: bpy.props.StringProperty()

    def execute(self, context):
        if not pick_bone(context, self.rig, self.bone):
            self.report({"WARNING"}, "Нет такой кости: " + self.bone)
            return {"CANCELLED"}
        return {"FINISHED"}


class VERAS_OT_open(bpy.types.Operator):
    bl_idname = "veras.open"
    bl_label = "Открыть"
    bl_description = "Открыть позы или клип: его ключи встают на шкалу с кадра 1"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        name = self.name
        S = context.scene
        g, m = S.get("veras_grip", ""), S.get("veras_mag", "30")
        base = bpy.data.actions.get(name)
        if base is not None and name != POSES and (g or m != variant_of(base).get("mag", "30")):
            vn = version_name(name, g, m)
            if vn in bpy.data.actions:
                name = vn
            else:
                self.report({"INFO"}, "У этого клипа нет такой версии — открыт основной")
        if not open_action(context, name):
            self.report({"WARNING"}, "Нет такого действия: " + name)
            return {"CANCELLED"}
        if is_version(bpy.data.actions[name]):
            self.report({"INFO"}, "Это версия: ключи в ней не править — правьте основной клип, потом «Собрать версии»")
        return {"FINISHED"}


class VERAS_OT_pose(bpy.types.Operator):
    bl_idname = "veras.pose"
    bl_label = "Поза"
    bl_description = "Перейти на кадр этой позы (нужные рукоятка, магазин, фонарь появятся сами)"
    bl_options = {"REGISTER", "UNDO"}
    pose: bpy.props.StringProperty()

    def execute(self, context):
        goto_pose(context, self.pose)
        return {"FINISHED"}


class VERAS_OT_variant(bpy.types.Operator):
    bl_idname = "veras.variant"
    bl_label = "Версия"
    bl_description = "Какую версию клипа открывать: рукоятка и магазин"
    bl_options = {"REGISTER", "UNDO"}
    grip: bpy.props.StringProperty(default="-")
    mag: bpy.props.StringProperty(default="-")

    def execute(self, context):
        S = context.scene
        if self.grip != "-":
            S["veras_grip"] = self.grip
        if self.mag != "-":
            S["veras_mag"] = self.mag
        cur = S.get("veras_open", "")
        act = bpy.data.actions.get(cur)
        if act is not None and cur != POSES:
            base = act.get("base", cur)
            bpy.ops.veras.open(name=base)
        return {"FINISHED"}


class VERAS_OT_sync(bpy.types.Operator):
    bl_idname = "veras.sync"
    bl_label = "Хваты из поз → во все клипы"
    bl_description = "Перенести поправленные позы во все клипы и собрать версии. Движение и ваши ключи в клипах не меняются"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lines = []
        cur = context.scene.get("veras_open", "")
        res = sync(context, lines.append)
        for ln in lines:
            print("ВЕРАС:", ln)
        if res is None:
            self.report({"WARNING"}, lines[-1] if lines else "Не получилось")
            return {"CANCELLED"}
        if cur in bpy.data.actions:
            open_action(context, cur)
        total, hit = res
        self.report({"INFO"}, f"Поправлено ключей: {total}, клипов: {hit}" if total else "Позы не менялись — клипы как были")
        return {"FINISHED"}


class VERAS_OT_versions(bpy.types.Operator):
    bl_idname = "veras.versions"
    bl_label = "Собрать версии"
    bl_description = "Версии клипов под рукоятки ВАРН и магазины 45 / 60 — заново из основных клипов и поз"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        n = build_versions(context)
        self.report({"INFO"}, f"Версий собрано: {n}")
        return {"FINISHED"}


class VERAS_PT_clips(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ВЕРАС"
    bl_label = "ВЕРАС-54: клипы рук"

    def draw(self, context):
        lay = self.layout
        S = context.scene
        arms, _wr = rigs()
        if arms is None or POSES not in bpy.data.actions:
            lay.label(text="В файле нет рига рук ВЕРАС-54")
            return
        cur = S.get("veras_open", "")
        col = lay.column(align=True)
        col.operator("veras.open", text="Позы (хваты), кадры 1–91", depress=cur == POSES, icon="ARMATURE_DATA").name = POSES
        if cur == POSES:
            box = col.box().column(align=True)
            for name, f in POSE_FRAMES.items():
                op = box.operator("veras.pose", text=f"{f:>2}  {POSE_RU[name]}", depress=S.frame_current == f, emboss=True)
                op.pose = name
        col.separator()
        vrow = lay.row(align=True)
        g = S.get("veras_grip", "")
        for key, label in GRIPS:
            op = vrow.operator("veras.variant", text=label, depress=g == key)
            op.grip, op.mag = key, "-"
        vrow = lay.row(align=True)
        m = S.get("veras_mag", "30")
        for key, label in MAGS:
            op = vrow.operator("veras.variant", text=label, depress=m == key)
            op.grip, op.mag = "-", key
        col = lay.column(align=True)
        group = None
        for act in clip_actions():
            if act.get("group", "") != group:
                group = act.get("group", "")
                col.separator()
                col.label(text=group)
            n = int(math.ceil(last_key(act, arms)))
            here = cur == act.name or bpy.data.actions.get(cur) is not None and bpy.data.actions[cur].get("base") == act.name
            col.operator("veras.open", text=f"{act.get('title', act.name[len(PREFIX):])}   ·   {n} к", depress=here).name = act.name
        if cur and SEP in cur:
            lay.label(text="Открыта версия: правьте основной клип", icon="INFO")
        lay.separator()
        root = bpy.data.objects.get(ROOT)
        box = lay.box().column(align=True)
        box.label(text="Детали автомата (ромбик — ключ):")
        for label, obn, prop in SLIDERS:
            ob = bpy.data.objects.get(obn)
            if ob is not None and prop[2:-2] in ob.keys():
                box.prop(ob, prop, text=label)
        wr = bpy.data.objects.get(GUN)
        if wr is not None:
            for bn, label in (("Magazine_Control", "Магазин в левой кисти"), ("Suppressor_Control", "Глушитель в левой кисти")):
                c = wr.pose.bones[bn].constraints.get("В левой кисти") if bn in wr.pose.bones else None
                if c is not None:
                    box.prop(c, "influence", text=label + " (1 — в кисти)")
        lay.separator()
        lay.label(text="Выбрать кость:")
        grid = lay.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for label, rig, bone in PICK:
            op = grid.operator("veras.pick", text=label)
            op.rig, op.bone = rig, bone
        lay.separator()
        lay.operator("veras.sync", icon="FILE_REFRESH")
        lay.operator("veras.versions", icon="DUPLICATE")
        box = lay.box().column(align=True)
        box.scale_y = 0.8
        for ln in ("Позы: поставить на кадре позы, ключ.", "Клип: ключи двигать и менять как угодно,",
                   "ключ — только на ту кость, что двигали.", "Кнопка выше переносит позы в клипы,",
                   "ваши ключи в клипах не трогает.", "v02 (автомат v14): клипы обвесов не перенесены,",
                   "сборки заново из таблиц нет (regenerate не применять)."):
            box.label(text=ln)


CLASSES = (VERAS_OT_open, VERAS_OT_pose, VERAS_OT_variant, VERAS_OT_pick, VERAS_OT_sync, VERAS_OT_versions, VERAS_PT_clips)


def register():
    for cls in CLASSES:
        old = getattr(bpy.types, cls.__name__, None)
        if old is not None:
            try:
                bpy.utils.unregister_class(old)
            except RuntimeError:
                pass
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
