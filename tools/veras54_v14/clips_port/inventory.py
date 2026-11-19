"""ВЕРАС-54, разведка перед переносом клипов на сетку v14: опись файла клипов (только чтение, файл не сохраняется).

blender -b <копия файла клипов.blend> --factory-startup --python tools/veras54_v14/clips_port/inventory.py -- <выход.json> <ключи.json>

<выход.json> — объекты, кости, ограничения, приводы, свойства, действия (свойства, слоты, кадры ключей), NLA, маркеры.
<ключи.json> — все ключи всех действий: {действие: {"слот|путь|индекс": [[кадр, значение, интерп], …]}}.
"""
import json
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
OUT, KEYS = args[0], args[1]


def M(m):
    return [[round(v, 7) for v in row] for row in m]


def V(v):
    return [round(x, 7) for x in v]


def props(idb):
    out = {}
    for k in idb.keys():
        if k.startswith("_"):
            continue
        v = idb[k]
        try:
            json.dumps(v)
            out[k] = v
        except TypeError:
            try:
                out[k] = v.to_dict() if hasattr(v, "to_dict") else list(v)
            except Exception:
                out[k] = str(v)
    return out


def drivers_of(idb):
    ad = getattr(idb, "animation_data", None)
    if not ad:
        return []
    out = []
    for d in ad.drivers:
        out.append(dict(path=d.data_path, index=d.array_index, expr=d.driver.expression, type=d.driver.type,
                        vars=[dict(name=v.name, type=v.type,
                                   targets=[dict(id=t.id.name if t.id else None, path=t.data_path,
                                                 bone=getattr(t, "bone_target", ""), transform=getattr(t, "transform_type", ""))
                                            for t in v.targets]) for v in d.driver.variables]))
    return out


S = bpy.context.scene
bpy.context.view_layer.update()
rec = dict(file=bpy.data.filepath, scene=dict(name=S.name, fps=S.render.fps, frame_start=S.frame_start, frame_end=S.frame_end,
                                             frame_current=S.frame_current, camera=S.camera.name if S.camera else None,
                                             props=props(S),
                                             markers=sorted([(m.name, m.frame) for m in S.timeline_markers], key=lambda x: x[1])))
rec["collections"] = {c.name: dict(objects=[o.name for o in c.objects], children=[ch.name for ch in c.children],
                                   hide_viewport=c.hide_viewport, hide_render=c.hide_render) for c in bpy.data.collections}
objs = {}
dg = bpy.context.evaluated_depsgraph_get()
for o in bpy.data.objects:
    d = dict(type=o.type, parent=o.parent.name if o.parent else None, parent_type=o.parent_type, parent_bone=o.parent_bone,
             collections=[c.name for c in o.users_collection], matrix_world=M(o.matrix_world),
             matrix_parent_inverse=M(o.matrix_parent_inverse), hide_viewport=o.hide_viewport, hide_render=o.hide_render,
             hidden=o.hide_get() if o.name in bpy.context.view_layer.objects else None,
             props=props(o), drivers=drivers_of(o),
             constraints=[dict(name=c.name, type=c.type, target=getattr(c, "target", None) and c.target.name,
                               subtarget=getattr(c, "subtarget", ""), influence=c.influence, enabled=c.enabled)
                          for c in o.constraints],
             modifiers=[dict(name=m.name, type=m.type, object=getattr(m, "object", None) and m.object.name) for m in o.modifiers])
    if o.type == "MESH":
        d["verts"] = len(o.data.vertices)
        d["tris"] = sum(len(p.vertices) - 2 for p in o.data.polygons)
        d["materials"] = [m.name if m else None for m in o.data.materials]
        d["bbox_local"] = [V(c) for c in o.bound_box]
        d["vgroups"] = len(o.vertex_groups)
    if o.animation_data:
        ad = o.animation_data
        d["anim"] = dict(action=ad.action.name if ad.action else None,
                         slot=ad.action_slot.name_display if getattr(ad, "action_slot", None) else None,
                         tweak=ad.use_tweak_mode, use_nla=ad.use_nla,
                         nla=[dict(track=t.name, mute=t.mute, strips=[dict(name=s.name, action=s.action.name if s.action else None,
                                                                         start=s.frame_start, end=s.frame_end) for s in t.strips])
                              for t in ad.nla_tracks])
    if o.type == "ARMATURE":
        bones = {}
        for b in o.data.bones:
            pb = o.pose.bones[b.name]
            bones[b.name] = dict(parent=b.parent.name if b.parent else None, head=V(b.head_local), tail=V(b.tail_local),
                                 matrix_local=M(b.matrix_local), deform=b.use_deform, rot_mode=pb.rotation_mode,
                                 basis=M(pb.matrix_basis), pose=M(pb.matrix),
                                 constraints=[dict(name=c.name, type=c.type, target=getattr(c, "target", None) and c.target.name,
                                                   subtarget=getattr(c, "subtarget", ""), influence=c.influence,
                                                   enabled=c.enabled, chain=getattr(c, "chain_count", None),
                                                   pole=getattr(c, "pole_subtarget", None))
                                              for c in pb.constraints],
                                 children_objects=[ob.name for ob in bpy.data.objects
                                                   if ob.parent == o and ob.parent_type == "BONE" and ob.parent_bone == b.name])
        d["bones"] = bones
        d["arm_drivers"] = drivers_of(o.data)
    objs[o.name] = d
rec["objects"] = objs

acts = {}
keys = {}
for a in bpy.data.actions:
    info = dict(props=props(a), users=a.users, fake=a.use_fake_user, use_frame_range=a.use_frame_range,
                frame_range=V(a.frame_range), slots=[s.name_display for s in a.slots], fcurves=0, frames=[])
    kd = {}
    frames = set()
    for layer in a.layers:
        for st in layer.strips:
            for slot in a.slots:
                bag = st.channelbag(slot)
                if bag is None:
                    continue
                for fc in bag.fcurves:
                    info["fcurves"] += 1
                    pts = [[round(kp.co[0], 4), round(kp.co[1], 7), kp.interpolation,
                            round(kp.handle_left[0], 4), round(kp.handle_left[1], 7),
                            round(kp.handle_right[0], 4), round(kp.handle_right[1], 7)]
                           for kp in fc.keyframe_points]
                    frames.update(p[0] for p in pts)
                    kd[f"{slot.name_display}|{fc.data_path}|{fc.array_index}"] = pts
    info["frames"] = sorted(frames)
    acts[a.name] = info
    keys[a.name] = kd
rec["actions"] = acts
rec["texts"] = {t.name: dict(lines=len(t.lines), module=t.use_module, head=t.as_string()[:400]) for t in bpy.data.texts}
rec["images"] = {i.name: dict(path=i.filepath, packed=bool(i.packed_file), size=list(i.size)) for i in bpy.data.images}
rec["libraries"] = [l.filepath for l in bpy.data.libraries]
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(rec, f, ensure_ascii=False, indent=1)
with open(KEYS, "w", encoding="utf-8", newline="\n") as f:
    json.dump(keys, f, ensure_ascii=False)
print("INV done", len(objs), "objects", len(acts), "actions", flush=True)
