"""АСТЕН-919 — панель клипов рук в Blender (боковая панель 3D-вида, клавиша N, вкладка «АСТЕН»).

Всё правится в Blender, без скриптов:
  «Позы (хваты)»   — кадры-заготовки хватов (1 — хват, 11 / 16 — палец на спуске, 21 / 26 / 31 — большой правой,
                     41 / 46 / 51 / 61 — левая рука). Поставил позу на её кадре — ключ (I / K).
  клип из списка   — открывает клип: его ключи на шкале с кадра 1. Двигать ключи во времени, наклонять пистолет
                     (Weapon_CTRL), вести левую кисть (ik_hand.L), затвор и магазин — как обычную анимацию.
                     Маркеры фаз (mag_out, insert …) можно двигать: они запоминаются при переходе в другой клип.
  «Хваты из поз → во все клипы» — переносит поправленные позы в клипы, движение и ваши ключи не трогает:
       пальцы и кости рук — там, где ключ клипа совпадал с прежней позой, ставится новая поза;
       левая кисть — там, где она стояла «как в позе» (тот же поворот), её место меняется так же, как в позе;
       пистолет — если его место на кадре 1 (хват) или на кадрах 41 / 46 / 51 изменилось, ключи пистолета в клипах,
       стоявшие возле этой позы, сдвигаются на ту же поправку.
     Ключи, которые вы поставили в клипе по-своему, ни с какой позой не совпадают и остаются как есть.

Этот текст лежит и в репозитории игры: tools/asten919/clips/clip_tools.py (сборщик кладёт его в файл клипов).
Панель не появилась — нажать «Allow Execution» в полоске вверху окна или здесь, в редакторе текста, кнопку ▶.
"""
import json
import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

POSES = "ASTEN919_Poses"
APPLIED = "ASTEN919_Poses_applied"                   # снимок поз, уже перенесённых в клипы
PREFIX = "ASTEN919_"
ARMS, GUN = "FPS_ArmsRig", "ASTEN919_WeaponRig"
PANEL_TEXT = "asten919_panel.py"
POSE_FRAMES = dict(grip=1, trigger=11, pressed=16, catch=21, stop=26, up=31, mag=41, seat=46, pinch=51, free=61)
POSE_RU = dict(grip="ХВАТ", trigger="палец на спуске", pressed="спуск выжат", catch="большой: кнопка магазина",
               stop="большой: рычаг задержки", up="большой вверх", mag="магазин в левой", seat="ладонь досылает",
               pinch="щепоть на затворе", free="левая свободна")
FINGER = ("thumb", "palm", "f_index", "f_middle", "f_ring", "f_pinky")
GUN_REF = ("mag", "seat", "pinch")                    # кадры поз, где стоит и положение пистолета
GUN_NEAR_DEG, GUN_NEAR_M = 12.0, 0.035                # ключ пистолета «возле позы»: ближе этого


# ------------------------------------------------------------------ действия, кривые
def rigs():
    return bpy.data.objects.get(ARMS), bpy.data.objects.get(GUN)


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


def clip_actions():
    acts = [a for a in bpy.data.actions if a.name.startswith(PREFIX) and a.name not in (POSES, APPLIED)]
    return sorted(acts, key=lambda a: (a.get("order", 999), a.name))


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
            if insert:
                fc.keyframe_points.insert(f, v, options={"REPLACE"})
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
def own_sets(arms):
    names = [pb.name for pb in arms.pose.bones]
    fing = lambda n: n.split(".")[0] in FINGER  # noqa: E731
    r_thumb = {n for n in names if n.startswith("thumb") and n.endswith(".R")}
    r_index = {n for n in names if n.startswith("f_index") and n.endswith(".R")}
    left = {n for n in names if n.endswith(".L")} | {"Weapon_CTRL"}
    return dict(trigger=r_index, pressed=r_index, catch=r_thumb, stop=r_thumb, up=r_thumb,
                mag=left, seat=left, pinch=left, free=left), {n for n in names if fing(n)}


def pose_table(act, arms):
    cv = bone_curves(bag_of(act, arms))
    return {name: {pb.name: read(cv.get(pb.name, {}), pb, f) for pb in arms.pose.bones} for name, f in POSE_FRAMES.items()}


def magazine_in_hand(context, arms, wr, poses):
    """Как магазин лежит в левой кисти (кость mag.L) — по кадру 41: магазин стоит в пистолете, кисть вокруг него."""
    if "mag.L" not in arms.pose.bones or wr is None:
        return None
    S = context.scene
    keep = [(ob, ob.animation_data.action, ob.animation_data.action_slot) for ob in (arms, wr)]
    frame = S.frame_current
    con = wr.pose.bones["Magazine_Control"].constraints.get("В левой кисти")
    was = con.enabled if con else True
    try:
        for ob in (arms, wr):
            ob.animation_data.action = poses
            ob.animation_data.action_slot = slot_of(poses, ob)
        if con:
            con.enabled = False
        S.frame_set(POSE_FRAMES["mag"])
        context.view_layer.update()
        hand, ikt = arms.pose.bones["hand.L"], arms.pose.bones["ik_hand.L"]
        reached = hand.matrix.copy()                  # кисть — на цели IK (в клипах она до неё дотягивается)
        reached.translation = ikt.matrix.translation
        rel = arms.data.bones["hand.L"].matrix_local.inverted() @ arms.data.bones["mag.L"].matrix_local
        return ((reached @ rel).inverted() @ arms.matrix_world.inverted() @ wr.matrix_world
                @ wr.pose.bones["Magazine_Control"].matrix)
    finally:
        if con:
            con.enabled = was
        for ob, act, slot in keep:
            ob.animation_data.action = act
            if act is not None and slot is not None:
                ob.animation_data.action_slot = slot
        S.frame_set(frame)
        context.view_layer.update()


def tidy_poses(context, arms, wr, poses, say):
    """Позы владельца → таблица; на кадрах 11–61 всё, кроме «своего» в этой позе, приводится к хвату кадра 1."""
    own, _ = own_sets(arms)
    bag = bag_of(poses, arms)
    cv = bone_curves(bag)
    T = pose_table(poses, arms)
    mag = magazine_in_hand(context, arms, wr, poses)
    for name, f in POSE_FRAMES.items():
        for pb in arms.pose.bones:
            n = pb.name
            want = T[name][n]
            if n == "mag.L" and mag is not None:
                want = mag
            elif name != "grip" and n not in own[name]:
                want = T["grip"][n]
            if not close(want, T[name][n], 1e-6):
                write(cv.setdefault(n, {}), pb, f, want, bag, insert=True)
                T[name][n] = want.copy()
    return T


# ------------------------------------------------------------------ перенос поз в клипы
def reference(bone, K, OLD):
    """К какой позе относится ключ клипа: имя позы или None (ключ свой — не трогать)."""
    for name in POSE_FRAMES:
        if close(K, OLD[name][bone]):
            return name, True
    if bone == "ik_hand.L":                           # кисть стоит «как в позе», но сдвинута (магазин идёт в шахте и т. п.)
        for name in ("grip", "mag", "seat", "pinch", "free"):
            if apart(K, OLD[name][bone])[0] < 0.2:
                return name, False
    if bone == "Weapon_CTRL":                         # пистолет: возле позы кадра 41 / 46 / 51, иначе считается от хвата
        best = None
        for name in GUN_REF:
            ang, dist = apart(K, OLD[name][bone])
            if ang < GUN_NEAR_DEG and dist < GUN_NEAR_M and (best is None or ang + dist * 300 < best[0]):
                best = (ang + dist * 300, name)
        return (best[1] if best else "grip"), False
    return None, False


def sync(context, say=print):
    """Позы → клипы. → (сколько ключей поправлено, в скольких клипах) или None, если нечем сравнивать."""
    arms, wr = rigs()
    poses, applied = bpy.data.actions.get(POSES), bpy.data.actions.get(APPLIED)
    if arms is None or poses is None:
        say("Нет рига рук или действия поз")
        return None
    if applied is None:
        say("В файле нет снимка прежних поз — один раз запустите tools\\asten919\\clips\\rebuild.cmd")
        return None
    OLD = pose_table(applied, arms)
    NEW = tidy_poses(context, arms, wr, poses, say)
    changed = sorted({f"{POSE_FRAMES[name]} ({POSE_RU[name]})" for name in POSE_FRAMES for n in NEW[name]
                      if not close(OLD[name][n], NEW[name][n])}, key=lambda s: int(s.split()[0]))
    total, clips_hit = 0, 0
    for act in clip_actions():
        cv_all = bone_curves(bag_of(act, arms))
        n = 0
        for pb in arms.pose.bones:
            cv = cv_all.get(pb.name)
            if not cv:
                continue
            rp = rot_prop(pb)
            frames = sorted({round(kp.co[0], 3) for (prop, _i), fc in cv.items() if prop in ("location", rp)
                             for kp in fc.keyframe_points})
            plan = []                                 # сначала всё прочитать, потом писать: запись сдвигает кривые
            for f in frames:
                K = read(cv, pb, f)
                ref, exact = reference(pb.name, K, OLD)
                if ref is None:
                    continue
                Po, Pn = OLD[ref][pb.name], NEW[ref][pb.name]
                if close(Po, Pn, 1e-6):
                    continue
                plan.append((f, Pn.copy() if exact else K @ Po.inverted() @ Pn))
            for f, M in plan:
                write(cv, pb, f, M)
            n += len(plan)
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
    return total, clips_hit


# ------------------------------------------------------------------ открыть позы / клип
def last_key(act, ob):
    bag = bag_of(act, ob)
    return max((kp.co[0] for fc in (bag.fcurves if bag else ()) for kp in fc.keyframe_points), default=1.0)


def save_marks(act, scene):
    if act is not None and act.name.startswith(PREFIX) and act.name not in (POSES, APPLIED):
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
    for ob in (arms, wr):
        if ob is None:
            continue
        ad = ob.animation_data or ob.animation_data_create()
        if ad.use_tweak_mode:
            ad.use_tweak_mode = False
        ad.action = act
        slot = slot_of(act, ob)
        if slot is not None:
            ad.action_slot = slot
        ad.action_extrapolation = "HOLD"
        ad.action_blend_type = "REPLACE"
        ad.action_influence = 1.0
    load_marks(act, S)
    S.frame_start = 1
    S.frame_end = max(POSE_FRAMES.values()) if name == POSES else int(math.ceil(max(last_key(act, arms), 2.0)))
    S.frame_set(1)
    return True


# ------------------------------------------------------------------ интерфейс
class ASTEN_OT_open(bpy.types.Operator):
    bl_idname = "asten.open"
    bl_label = "Открыть"
    bl_description = "Открыть позы или клип: его ключи встают на шкалу с кадра 1"
    bl_options = {"REGISTER", "UNDO"}
    name: bpy.props.StringProperty()

    def execute(self, context):
        if not open_action(context, self.name):
            self.report({"WARNING"}, "Нет такого действия: " + self.name)
            return {"CANCELLED"}
        return {"FINISHED"}


class ASTEN_OT_sync(bpy.types.Operator):
    bl_idname = "asten.sync"
    bl_label = "Хваты из поз → во все клипы"
    bl_description = "Перенести поправленные позы (кадры 1–61) во все клипы. Движение и ваши ключи в клипах не меняются"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        lines = []
        res = sync(context, lines.append)
        for ln in lines:
            print("АСТЕН:", ln)
        if res is None:
            self.report({"WARNING"}, lines[-1] if lines else "Не получилось")
            return {"CANCELLED"}
        total, hit = res
        self.report({"INFO"}, f"Поправлено ключей: {total}, клипов: {hit}" if total else "Позы не менялись — клипы как были")
        return {"FINISHED"}


class ASTEN_PT_clips(bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "АСТЕН"
    bl_label = "АСТЕН-919: клипы рук"

    def draw(self, context):
        lay = self.layout
        arms, _wr = rigs()
        if arms is None or POSES not in bpy.data.actions:
            lay.label(text="В файле нет рига рук АСТЕН-919")
            return
        cur = arms.animation_data.action.name if arms.animation_data and arms.animation_data.action else ""
        col = lay.column(align=True)
        col.operator("asten.open", text="Позы (хваты), кадры 1–61", depress=cur == POSES, icon="ARMATURE_DATA").name = POSES
        col.separator()
        for act in clip_actions():
            n = int(math.ceil(last_key(act, arms)))
            col.operator("asten.open", text=f"{act.name[len(PREFIX):]}   ·   {n} к", depress=cur == act.name).name = act.name
        lay.separator()
        lay.operator("asten.sync", icon="FILE_REFRESH")
        box = lay.box().column(align=True)
        box.scale_y = 0.8
        for ln in ("Позы: поставить на кадре позы, ключ.", "Клип: ключи двигать и менять как угодно.",
                   "Кнопка выше переносит позы в клипы,", "ваши ключи в клипах не трогает."):
            box.label(text=ln)


CLASSES = (ASTEN_OT_open, ASTEN_OT_sync, ASTEN_PT_clips)


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
