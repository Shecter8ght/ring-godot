"""Author an isolated flare FPS rig using the unchanged VERAS-54 arms and weights.

The authoring scene keeps hand IK. Only the separate GLB export bakes constraints.
Usage: blender --background --factory-startup --python-exit-code 1 --python
  tools/animate_flare_pistol_codex.py -- author|render|export
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector, Quaternion

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/"_asset_src"/"flare_pistol_codex"/"integration"
OUT=ROOT/"assets"/"models"/"weapons"/"flare_pistol_codex"
BASE=Path("E:/Models Blender/ВЕРАС-54 — модель и обвесы/ВЕРАС-54/Игровая версия/Перезарядка v01 (Claude)/VERAS54_Reload_Full_v05.blend")
MASTER=WORK/"flare_pistol_codex_fps_animations.blend"
AUTHOR_GRIP=Vector((-.14,-.295,1.643))
LOCAL_GRIP=Vector((-.039,0,.059))
GUN=Matrix.Translation(AUTHOR_GRIP) @ Matrix.Rotation(-math.pi/2,4,"Z") @ Matrix.Translation(-LOCAL_GRIP)
PIVOTS={"Frame":LOCAL_GRIP,"Barrel":Vector((.075,0,.094)),"Hammer":Vector((-.009,0,.106)),
        "Trigger":Vector((.009,0,.074)),"Latch":Vector((.019,0,.120)),
        "FiringPin":Vector((.017,0,.112)),
        "NewRound":Vector((.022,0,.112)),"OldRound":Vector((.022,0,.112))}
CLIPS={"idle":30,"idle_empty":30,"draw":24,"reload_empty":156,"reload_live":156,
       "fire":24,"break_open":30,"insert_cartridge":64,"close_breech":22,
       "cock_hammer":24,"trigger_pull":24,"holster":24}
RELOAD_KEYS=[1,9,14,16,22,28,30,33,36,42,45,48,50,53,56,58,60,65,70,76,80,
             89,91,106,110,112,117,119,123,128,131,133,140,144,150,156]

def key_frames(clip,length):
    if clip in {"idle","idle_empty"}: return [1,length]
    if clip in {"fire","trigger_pull"}: return [1,5,6,7,8,10,22,length]
    if clip in {"draw","holster"}: return [1,8,16,length]
    offset={"insert_cartridge":48,"close_breech":107,"cock_hammer":126}.get(clip,0)
    return sorted({1,length}|{f-offset for f in RELOAD_KEYS if 1<=f-offset<=length})

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def ramp(f,a,b):
    t=max(0.,min(1.,(f-a)/max(.001,b-a)))
    return t*t*(3-2*t)

def spin(pivot,axis,angle):
    return Matrix.Translation(pivot) @ Matrix.Rotation(angle,4,axis) @ Matrix.Translation(-pivot)

def reload_motion(f):
    """Right hand turns the open chamber down, shakes twice, then snaps it shut."""
    weight=ramp(f,1,16)*(1-ramp(f,144,156))
    inverted=ramp(f,33,42)*(1-ramp(f,60,70))
    first=ramp(f,45,48)*(1-ramp(f,48,50))
    second=ramp(f,53,56)*(1-ramp(f,56,60))
    windup=ramp(f,112,117)*(1-ramp(f,117,123))
    snap=ramp(f,117,123)*(1-ramp(f,123,131))
    pitch=-42*inverted-8*first-9*second-8*windup+18*snap
    roll=180*inverted
    offset=Vector((.022,-.008,.018))*weight
    offset.z+=-.026*first-.031*second+.008*windup-.015*snap
    delta=Matrix.Translation(offset) @ spin(AUTHOR_GRIP,"Z",math.radians(-12)*weight) \
          @ spin(AUTHOR_GRIP,"X",math.radians(pitch)) @ spin(AUTHOR_GRIP,"Y",math.radians(roll))
    return delta,{"roll_deg":roll,"pitch_deg":pitch,"shake_1":first,"shake_2":second,"snap_close":snap}

def pose_set(pb,matrix):
    pb.matrix=matrix

def finger_tip(rig,name,fraction=1.):
    pb=rig.pose.bones[name]
    return pb.matrix @ Vector((0,pb.bone.length*fraction,0))

def finger_ccd(rig,stem,side,target,iterations=5):
    end=stem+".03."+side
    for _ in range(iterations):
        for i in (3,2,1):
            pb=rig.pose.bones[f"{stem}.{i:02d}.{side}"]
            a=finger_tip(rig,end,.82)-pb.head
            b=target-pb.head
            if min(a.length,b.length)<1e-6: continue
            q=a.normalized().rotation_difference(b.normalized())
            q=Quaternion().slerp(q,min(1.,.18/max(1e-5,q.angle)))
            pb.matrix=spin(pb.head,q.axis,q.angle) @ pb.matrix
            bpy.context.view_layer.update()

def native_pose(rig,base,rest,clip,f):
    for name,m in base.items(): rig.pose.bones[name].matrix_basis=m.copy()
    bpy.context.view_layer.update()
    rf=f
    reloading=clip in {"reload_empty","reload_live","break_open","insert_cartridge","close_breech","cock_hammer"}
    if clip=="insert_cartridge": rf=48+f
    elif clip=="close_breech": rf=107+f
    elif clip=="cock_hammer": rf=126+f
    rig["left_hand_active"]=1. if reloading and (rf<=36 or 70<=rf<=117) else 0.
    sway=0.
    delta=Matrix.Identity(4)
    motion={}
    if reloading:
        delta,motion=reload_motion(rf)
    elif clip in {"draw","holster"}:
        weight=1-ramp(f,1,24) if clip=="draw" else ramp(f,1,24)
        delta=Matrix.Translation((0,.05*weight,-.24*weight)) @ spin(AUTHOR_GRIP,"X",math.radians(28)*weight)
    elif clip in {"fire","trigger_pull"}:
        sway=ramp(f,5,8)*(1-ramp(f,8,24))
        delta=Matrix.Translation((0,.008*sway,.005*sway)) @ spin(AUTHOR_GRIP,"X",math.radians(-3)*sway)
    opening=48*ramp(rf,16,30)*(1-ramp(rf,119,128)) if reloading else 0.
    latch=ramp(rf,9,16)*(1-ramp(rf,22,32)) if reloading else 0.
    cock=0. if clip=="idle_empty" else 1.
    press=0.
    if reloading:
        cock=ramp(rf,131,144)
    elif clip in {"fire","trigger_pull"}:
        press=ramp(f,1,6)*(1-ramp(f,10,22))
        cock=1-ramp(f,6,8)
    axis=GUN.to_3x3() @ Vector((0,1,0))
    transformed={}
    for name,angle in (("Frame",0.),("Barrel",math.radians(opening)),("Hammer",-.34*cock),
                       ("Trigger",-.17*press),("Latch",.16*latch)):
        transform=delta @ spin(GUN@PIVOTS[name],axis,angle)
        transformed[name]=transform
        pose_set(rig.pose.bones[name],transform @ rest[name])
        bpy.context.view_layer.update()
    pulse=ramp(f,6,7)*(1-ramp(f,8,10)) if clip in {"fire","trigger_pull"} else 0.
    pin=delta @ rest["FiringPin"]
    pin.translation+=delta.to_3x3() @ (GUN.to_3x3() @ Vector((.00055*pulse,0,0)))
    pose_set(rig.pose.bones["FiringPin"],pin)
    bpy.context.view_layer.update()
    # Gun and dominant hand share one rigid frame throughout the full action.
    right=delta @ rest["ik_hand.R"]
    pose_set(rig.pose.bones["ik_hand.R"],right)
    bpy.context.view_layer.update()
    trigger_contact=transformed["Trigger"] @ (GUN @ Vector((.014,.003,.060)))
    if reloading:
        trigger_contact=delta @ (GUN @ Vector((.050,.018,.073)))
    finger_ccd(rig,"f_index","R",trigger_contact,iterations=4)
    if reloading:
        cock_contact=transformed["Hammer"] @ (GUN @ Vector((-.030,-.002,.120)))
        thumb_weight=ramp(rf,128,133)*(1-ramp(rf,144,150))
        thumb_target=finger_tip(rig,"thumb.03.R",.82).lerp(cock_contact,thumb_weight)
        finger_ccd(rig,"thumb","R",thumb_target,iterations=3)
    barrel=transformed["Barrel"]
    axis_forward=(barrel.to_3x3() @ (GUN.to_3x3() @ Vector((1,0,0)))).normalized()
    new=barrel @ rest["NewRound"]
    old=barrel @ rest["OldRound"]
    if reloading:
        # First shake loosens the case; the second clears the chamber. Once free,
        # it keeps its own downward trajectory while the right hand turns back.
        withdrawal=.012*ramp(rf,45,48)+.073*ramp(rf,53,58)
        old_delta,_=reload_motion(min(rf,58))
        old_barrel=old_delta @ spin(GUN@PIVOTS["Barrel"],axis,math.radians(48*ramp(rf,16,30)))
        old=old_barrel @ rest["OldRound"]
        old_forward=(old_barrel.to_3x3() @ (GUN.to_3x3() @ Vector((1,0,0)))).normalized()
        old.translation-=old_forward*withdrawal
        old.translation.z-=.22*ramp(rf,58,65)
        back=.078*(1-ramp(rf,91,110))
        new.translation-=axis_forward*back
        fetch=1-ramp(rf,67,89)
        new.translation+=Vector((.13,.08,-.22))*fetch
    pose_set(rig.pose.bones["NewRound"],new)
    pose_set(rig.pose.bones["OldRound"],old)
    bpy.context.view_layer.update()
    # Touch targets are in the same coordinate space as the shell/barrel bones.
    touch=Vector((.09,-.16,1.32))
    left_rotation=rest["left_orientation"].copy()
    if reloading:
        latch_touch=delta @ (GUN @ Vector((.018,.017,.122)))
        open_touch=barrel @ (GUN @ Vector((.056,.017,.098)))
        new_touch=new @ (rest["NewRound"].inverted() @ (GUN @ Vector((.043,.013,.112))))
        phases=[(1,touch),(14,latch_touch),(28,open_touch),(30,open_touch),(36,touch),
                (65,touch),(70,Vector((.10,-.23,1.46))),(80,new_touch),(110,new_touch),
                (117,touch),(156,touch)]
        for (a,pa),(b,pb) in zip(phases,phases[1:]):
            if a<=rf<=b:
                touch=pa.lerp(pb,ramp(rf,a,b))
                break
        if rf<1: touch=phases[0][1]
    wrist=Matrix.Translation(touch-left_rotation.to_3x3() @ rest["pinch_center"]) @ left_rotation
    pose_set(rig.pose.bones["ik_hand.L"],wrist)
    bpy.context.view_layer.update()
    if reloading and 76<=rf<=112:
        center=new @ (rest["NewRound"].inverted() @ (GUN @ Vector((.046,0,.112))))
        across=(delta.to_3x3() @ Vector((1,0,0))).normalized()
        finger_ccd(rig,"f_index","L",center+across*.013,iterations=3)
        finger_ccd(rig,"thumb","L",center-across*.013,iterations=3)
    return {"open_deg":opening,"hammer_cock":cock,"trigger_press":press,"frame":rf,**motion}

def split_arms(prep,rig,arms):
    copies=[]
    for side in ("Right","Left"):
        ob=arms.copy()
        ob.data=arms.data.copy()
        bpy.context.scene.collection.objects.link(ob)
        ob.name="FPS_Arms_"+side
        group=ob.vertex_groups.new(name="_Side_mask")
        chosen=[]
        for v in ob.data.vertices:
            scores={"L":0.,"R":0.}
            for weight in v.groups:
                name=ob.vertex_groups[weight.group].name
                if name.endswith(".L"): scores["L"]+=weight.weight
                if name.endswith(".R"): scores["R"]+=weight.weight
            left=scores["L"]>scores["R"]
            if left==(side=="Left"): chosen.append(v.index)
        group.add(chosen,1.,"REPLACE")
        prep.selected([ob])
        mask=ob.modifiers.new("Separate arm, unchanged source weights", "MASK")
        mask.vertex_group=group.name
        ob.modifiers.move(len(ob.modifiers)-1,0)
        bpy.ops.object.modifier_apply(modifier=mask.name)
        ob.vertex_groups.remove(ob.vertex_groups.get("_Side_mask"))
        ob["source_mesh"]="FPS_Arms from VERAS54_Reload_Full_v05; geometry separated by existing side weights"
        if side=="Left":
            rig["left_hand_active"]=0.
            curve=ob.driver_add("hide_render")
            var=curve.driver.variables.new()
            var.name="active"
            var.type="SINGLE_PROP"
            var.targets[0].id=rig
            var.targets[0].data_path='["left_hand_active"]'
            curve.driver.expression="active < 0.5"
        copies.append(ob)
    bpy.data.objects.remove(arms,do_unlink=True)
    return copies

def author():
    prep=load_module("flare_prepare",ROOT/"tools"/"prepare_flare_pistol_codex.py")
    vx=load_module("veras_export_helpers",ROOT/"tools"/"export_veras54.py")
    bpy.ops.wm.open_mainfile(filepath=str(BASE))
    scene=bpy.context.scene
    scene.frame_set(1)
    rig=bpy.data.objects["FPS_ArmsRig"]
    arms=bpy.data.objects["FPS_Arms"]
    cam=bpy.data.objects["FPS • Camera"]
    # Capture the existing corrected arm pose before removing VERAS controllers.
    base={pb.name:pb.matrix_basis.copy() for pb in rig.pose.bones}
    rest={name:rig.pose.bones[name].matrix.copy() for name in ("ik_hand.R","ik_hand.L")}
    left=rig.pose.bones["hand.L"].matrix.copy()
    pinch=(finger_tip(rig,"f_index.03.L",.82)+finger_tip(rig,"thumb.03.L",.82))*.5
    rest["pinch_center"]=left.inverted() @ pinch
    rest["left_orientation"]=(Matrix.Rotation(math.radians(-24),4,"Z") @ left).to_3x3().to_4x4()
    rig.animation_data_clear()
    for ob in list(bpy.data.objects):
        if ob not in {rig,arms,cam}: bpy.data.objects.remove(ob,do_unlink=True)
    arms_parts=split_arms(prep,rig,arms)
    for pb in rig.pose.bones:
        if pb.name in base: pb.matrix_basis=base[pb.name]
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active=rig
    prep.selected([rig])
    bpy.ops.object.mode_set(mode="EDIT")
    for name,pivot in PIVOTS.items():
        bone=rig.data.edit_bones.new(name)
        bone.head=GUN @ pivot
        bone.tail=bone.head+Vector((0,0,.025))
        bone.parent=rig.data.edit_bones["FPS_Root"] if name=="Frame" else rig.data.edit_bones["Frame"]
        bone.use_deform=True
    bpy.ops.object.mode_set(mode="OBJECT")
    for name in PIVOTS:
        rest[name]=rig.data.bones[name].matrix_local.copy()
        base[name]=Matrix.Identity(4)
    with bpy.data.libraries.load(str(prep.LP),link=False) as (data,loaded):
        loaded.objects=["GAME_gun_paint","GAME_gun_steel","GAME_gun_grip","GAME_ammo_red","GAME_ammo_green"]
    gun=[]
    props=[]
    for ob in loaded.objects:
        scene.collection.objects.link(ob)
        ob.hide_set(False)
        ob.hide_render=False
        ob.parent=rig
        ob.matrix_parent_inverse=Matrix.Identity(4)
        ob.matrix_basis=Matrix.Identity(4)
        if ob.name.startswith("GAME_gun_"):
            ob.data.transform(GUN)
            ob.name=ob.name.replace("GAME_","Flare_")
            gun.append(ob)
        else:
            red="red" in ob.name
            center=Vector((.143,-.002,0)) if red else Vector((.181,0,0))
            ammo=GUN @ Matrix.Translation(PIVOTS["NewRound"]) @ Matrix.Rotation(math.pi/2,4,"Y") @ Matrix.Translation(-center)
            ob.data.transform(ammo)
            ob.vertex_groups.clear()
            ob.name="LoadRoundRed" if red else "LoadRoundGreen"
            g=ob.vertex_groups.new(name="NewRound")
            g.add(list(range(len(ob.data.vertices))),1.,"REPLACE")
            old=ob.copy()
            old.data=ob.data.copy()
            scene.collection.objects.link(old)
            old.name="OldRoundRed" if red else "OldRoundGreen"
            old.vertex_groups.clear()
            group=old.vertex_groups.new(name="OldRound")
            group.add(list(range(len(old.data.vertices))),1.,"REPLACE")
            props.extend((ob,old))
    for ob in gun+props:
        modifier=ob.modifiers.new("FPS Arms and flare mechanism","ARMATURE")
        modifier.object=rig
        for attr in list(ob.data.color_attributes): ob.data.color_attributes.remove(attr)
        ob.data.validate(clean_customdata=False)
    scene.render.fps=30
    scene.frame_start,scene.frame_end=1,156
    actions={}
    for ob in arms_parts: ob.data.calc_loop_triangles()
    audit={"source":str(BASE),"hands_mesh":[ob.name for ob in arms_parts],"hands_triangles":sum(len(ob.data.loop_triangles) for ob in arms_parts),
           "rig":"FPS_ArmsRig","clips":{}}
    audit["reload_sequence"]={"open":30,"chamber_down":42,"shake_1":48,"shake_2":56,"case_free":58,
                              "upright":70,"insert":110,"right_hand_snap":123,"closed":128,"cocked":144,"ready":156}
    for clip,length in CLIPS.items():
        action=bpy.data.actions.new("Flare_Codex_"+clip)
        action.use_fake_user=True
        vx.assign(rig,action)
        for f in key_frames(clip,length):
            scene.frame_set(f)
            state=native_pose(rig,base,rest,clip,f)
            for pb in rig.pose.bones:
                pb.rotation_mode="QUATERNION"
                for path in ("location","rotation_quaternion","scale"):
                    pb.keyframe_insert(path,frame=f)
            rig.keyframe_insert(data_path='["left_hand_active"]',frame=f)
        for fc in vx.fcurves(action):
            for kp in fc.keyframe_points: kp.interpolation="LINEAR"
        actions[clip]=action
        audit["clips"][clip]={"frames":length,"seconds":(length-1)/30,"editable_keyframes":key_frames(clip,length)}
        print("FLARE_CLIP_AUTHORED",clip,length,flush=True)
    vx.assign(rig,actions["idle"])
    scene.frame_set(1)
    for name,point,parent in [("WeaponFrame",tuple(LOCAL_GRIP),"Frame"),("Muzzle",(.1148,0,.112),"Barrel"),
                              ("SightRear",(.026,0,.130),"Frame"),("SightFront",(.105,0,.130),"Barrel")]:
        mark=bpy.data.objects.new(name,None)
        scene.collection.objects.link(mark)
        mark.parent=rig
        mark.parent_type="BONE"
        mark.parent_bone=parent
        bpy.context.view_layer.update()
        mark.matrix_world=Matrix.Translation(GUN @ Vector(point))
    for ob in props: ob.hide_render=True
    cam.data.lens=24
    cam.location.z-=.055
    cam.data.clip_start=.01
    scene.camera=cam
    scene.world.use_nodes=True
    bg=next(n for n in scene.world.node_tree.nodes if n.type=="BACKGROUND")
    bg.inputs[0].default_value=(.15,.16,.18,1)
    bg.inputs[1].default_value=.5
    for name,point,power,size in [("Flare FPS Key",(-.6,-.5,2.5),40,.7),("Flare FPS Fill",(.6,-.1,2.1),20,.9),
                                 ("Flare FPS Rim",(.1,-1.,2.3),45,.7)]:
        data=bpy.data.lights.new(name,"AREA")
        data.energy,data.size=power,size
        ob=bpy.data.objects.new(name,data)
        scene.collection.objects.link(ob)
        ob.location=point
        ob.rotation_euler=(AUTHOR_GRIP-ob.location).to_track_quat("-Z","Y").to_euler()
    scene.render.engine="CYCLES"
    scene.cycles.samples=24
    scene.cycles.use_denoising=True
    scene.render.resolution_x,scene.render.resolution_y=1600,900
    scene.render.resolution_percentage=100
    scene.view_settings.view_transform="AgX"
    for marker in list(scene.timeline_markers): scene.timeline_markers.remove(marker)
    for f,name in [(1,"01 Right hand / left out"),(14,"02 Left releases latch"),(30,"03 Left opens barrel"),
                   (42,"04 Right turns chamber down"),(48,"05 Shake 1"),(56,"06 Shake 2 / case falls"),
                   (70,"07 Right returns upright"),(80,"08 Left brings new round"),(91,"09 Align round"),
                   (110,"10 Round seated"),(117,"11 Left releases barrel"),(123,"12 Right snaps down"),
                   (128,"13 Barrel locked"),(140,"14 Right thumb cocks hammer"),(156,"15 Right hand ready")]:
        scene.timeline_markers.new(name,frame=f)
    rig["flare_source"]="Codex worn v03; separate copy of VERAS54 arms, original mesh and weights"
    rig["reload_events_frames"]="30 open, 42 inverted, 48 shake 1, 56 shake 2, 58 case free, 70 upright, 110 insert, 123 snap, 128 close, 144 cock"
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    (WORK/"animation_audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding="utf-8")

def render():
    vx=load_module("veras_export_helpers",ROOT/"tools"/"export_veras54.py")
    prep=load_module("flare_prepare",ROOT/"tools"/"prepare_flare_pistol_codex.py")
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    prep.helper().set_gpu()
    scene=bpy.context.scene
    rig=bpy.data.objects["FPS_ArmsRig"]
    props=[bpy.data.objects[n] for n in ("LoadRoundRed","LoadRoundGreen","OldRoundRed","OldRoundGreen")]
    previews=WORK/"previews"
    for clip,f,name in [("idle",1,"06_fps_idle"),("reload_empty",30,"07_fps_open"),
                        ("reload_empty",56,"08_fps_extract"),("reload_empty",91,"09_fps_insert"),
                        ("reload_empty",109,"10_fps_seated"),("reload_empty",140,"11_fps_cock"),
                        ("fire",7,"12_fps_trigger"),("reload_empty",42,"16_fps_chamber_down"),
                        ("reload_empty",48,"17_fps_shake_1"),("reload_empty",123,"18_fps_snap_close")]:
        vx.assign(rig,bpy.data.actions["Flare_Codex_"+clip])
        scene.frame_set(f)
        for ob in props: ob.hide_render=True
        if clip.startswith("reload"):
            bpy.data.objects["OldRoundRed"].hide_render=not 1<=f<=65
            bpy.data.objects["LoadRoundGreen"].hide_render=not 73<=f<=156
        scene.render.filepath=str(previews/(name+".png"))
        bpy.ops.render.render(write_still=True)
        print("FLARE_FPS_RENDER",name,flush=True)
    vx.assign(rig,bpy.data.actions["Flare_Codex_idle"])
    scene.frame_set(1)
    for ob in props: ob.hide_render=True
    cam=scene.camera
    cam.data.type="ORTHO"
    cam.data.ortho_scale=.38
    cam.location=(.16,-.46,1.80)
    cam.rotation_euler=(Vector((-.13,-.29,1.63))-cam.location).to_track_quat("-Z","Y").to_euler()
    scene.render.filepath=str(previews/"13_grip_side_check.png")
    bpy.ops.render.render(write_still=True)

def edit_setup():
    """Only prepare the saved authoring scene for the owner's bone editing."""
    vx=load_module("veras_export_helpers",ROOT/"tools/export_veras54.py")
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    scene=bpy.context.scene
    rig=bpy.data.objects["FPS_ArmsRig"]
    rig["preview_new_green"]=1.
    rig["preview_old_green"]=0.
    rig["preview_has_old"]=1.
    for clip,length in CLIPS.items():
        vx.assign(rig,bpy.data.actions["Flare_Codex_"+clip])
        reload=clip in {"reload_empty","reload_live","break_open","insert_cartridge","close_breech","cock_hammer"}
        offset={"insert_cartridge":48,"close_breech":107,"cock_hammer":126}.get(clip,0)
        for f in key_frames(clip,length):
            rig["preview_reload_frame"]=float(f+offset) if reload else 0.
            rig.keyframe_insert(data_path='["preview_reload_frame"]',frame=f)
        for fc in vx.fcurves(rig.animation_data.action):
            if "preview_reload_frame" in fc.data_path:
                for kp in fc.keyframe_points: kp.interpolation="LINEAR"
    for name in ("LoadRoundRed","LoadRoundGreen","OldRoundRed","OldRoundGreen"):
        ob=bpy.data.objects[name]
        old=name.startswith("Old")
        green=name.endswith("Green")
        window=(1,65) if old else (73,156)
        for path in ("hide_viewport","hide_render"):
            ob.driver_remove(path)
            fc=ob.driver_add(path)
            for variable,prop in [("frame","preview_reload_frame"),("green","preview_old_green" if old else "preview_new_green"),("has_old","preview_has_old")]:
                v=fc.driver.variables.new()
                v.name=variable
                v.type="SINGLE_PROP"
                v.targets[0].id=rig
                v.targets[0].data_path='["'+prop+'"]'
            fc.driver.expression=f"not ({window[0]} <= frame <= {window[1]} and {'green > .5' if green else 'green < .5'}{' and has_old > .5' if old else ''})"
    vx.assign(rig,bpy.data.actions["Flare_Codex_reload_empty"])
    scene.frame_set(1)
    for ob in bpy.context.selected_objects: ob.select_set(False)
    rig.select_set(True)
    bpy.context.view_layer.objects.active=rig
    rig.show_in_front=True
    bpy.ops.object.mode_set(mode="POSE")
    for bone in rig.pose.bones: bone.select=bone.name in {"ik_hand.R","ik_hand.L"}
    if hasattr(rig.pose.bones,"active"): rig.pose.bones.active=rig.pose.bones["ik_hand.R"]
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D": area.spaces.active.region_3d.view_perspective="CAMERA"
            if area.type=="DOPESHEET_EDITOR" and area.ui_type!="TIMELINE": area.ui_type="DOPESHEET"
    bpy.ops.wm.save_as_mainfile(filepath=str(MASTER))
    print("HAND_EDIT_SETUP_PASS: reload action, wrist controls, automatic cartridge previews")

def export():
    vx=load_module("veras_export_helpers",ROOT/"tools"/"export_veras54.py")
    prep=load_module("flare_prepare",ROOT/"tools"/"prepare_flare_pistol_codex.py")
    bpy.ops.wm.open_mainfile(filepath=str(MASTER))
    if bpy.context.object and bpy.context.object.mode!="OBJECT": bpy.ops.object.mode_set(mode="OBJECT")
    scene=bpy.context.scene
    rig=bpy.data.objects["FPS_ArmsRig"]
    cam=scene.camera
    baked={}
    for clip,length in CLIPS.items():
        vx.assign(rig,bpy.data.actions["Flare_Codex_"+clip])
        mats={}
        for f in range(1,length+1):
            scene.frame_set(f)
            bpy.context.view_layer.update()
            for pb in rig.pose.bones:
                m=rig.convert_space(pose_bone=pb,matrix=pb.matrix,from_space="POSE",to_space="LOCAL")
                mats.setdefault(pb.name,[]).append(m.copy())
        baked[clip]=(list(range(1,length+1)),mats)
    rig.animation_data_clear()
    for pb in rig.pose.bones:
        for c in list(pb.constraints): pb.constraints.remove(c)
        pb.matrix_basis=Matrix.Identity(4)
    for clip,(frames,mats) in baked.items():
        vx.push_track(rig,clip,vx.bake_action(rig,"VM_Flare_"+clip,frames,mats))
    scene.frame_set(1)
    for track in rig.animation_data.nla_tracks: track.mute=True
    rig.animation_data.nla_tracks[0].mute=False
    # Keep authored native rig untouched: camera conversion exists only in this export.
    to_cam=Matrix.Rotation(math.pi/2,4,"X") @ cam.matrix_world.inverted()
    rig.matrix_world=to_cam @ rig.matrix_world
    objects=[rig]+[o for o in scene.objects if o.parent==rig]
    for ob in objects:
        if ob.animation_data:
            for curve in list(ob.animation_data.drivers):
                if curve.data_path in {"hide_render","hide_viewport"}: ob.driver_remove(curve.data_path)
        ob.hide_render=False
        ob.hide_viewport=False
        ob.hide_set(False)
    for img in bpy.data.images:
        if img.users and img.size[0]>2048: img.scale(2048,max(1,2048*img.size[1]//img.size[0]))
    for track in rig.animation_data.nla_tracks: track.mute=False
    prep.export_glb(OUT/"flare_pistol_codex_viewmodel.glb",objects,animations=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/"flare_pistol_codex_fps_export.blend"))
    print("FLARE_FPS_EXPORT_PASS",len(CLIPS),"clips",flush=True)

if __name__=="__main__":
    args=sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else ["author"]
    mode=args[0]
    if len(args)>1:
        MASTER=Path(args[1])
    {"author":author,"render":render,"export":export,"edit_setup":edit_setup}[mode]()
