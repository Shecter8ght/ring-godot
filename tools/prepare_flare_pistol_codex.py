"""Preserve the native UCUPaint master, correct animation clearances, bake a game mesh.

blender --background --factory-startup --python-exit-code 1 --python
  tools/prepare_flare_pistol_codex.py -- grooves|lowpoly|bake|world|verify
"""
import importlib.util
import json
import math
import sys
from pathlib import Path
import bpy
import bmesh
import addon_utils
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "_asset_src" / "flare_pistol_codex"
WORK = SRC / "integration"
GROOVED = SRC / "models" / "launcher" / "flare_pistol_codex_ucupaint_worn_v02.blend"
HP = SRC / "models" / "launcher" / "flare_pistol_codex_ucupaint_worn_v03.blend"
LP = WORK / "flare_pistol_codex_lowpoly.blend"
OUT = ROOT / "assets" / "models" / "weapons" / "flare_pistol_codex"
TEX = OUT / "textures"
GRIP = Vector((-.039,0,.059))
GAME_TRANSFORM = Matrix.Rotation(-math.pi/2,4,"Z") @ Matrix.Translation(-GRIP)
PIVOTS = {"Frame":Vector((0,0,0)),"Barrel":Vector((.075,0,.094)),
          "Hammer":Vector((-.009,0,.106)),"Trigger":Vector((.009,0,.074)),"Latch":Vector((.019,0,.120)),
          "FiringPin":Vector((.017,0,.112))}
WORK.mkdir(parents=True, exist_ok=True)

def helper():
    spec = importlib.util.spec_from_file_location("flare_builder", ROOT / "tools" / "build_flare_pistol_codex.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def native():
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable("bl_ext.blender_org.ucupaint", default_set=True)

def mesh_eval(obj):
    ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    return bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=bpy.context.evaluated_depsgraph_get())

def bvh(obj):
    me = mesh_eval(obj)
    tree = BVHTree.FromPolygons([obj.matrix_world @ v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])
    bpy.data.meshes.remove(me)
    return tree

def clearance(name, part, prop, width):
    ctrl = bpy.data.objects["CTRL_Launcher"]
    bm = bmesh.new()
    # The editable cutter encloses the complete visual sweep, including bevels.
    # It opens a central groove; the exterior sides and approved grip contour stay intact.
    for i in range(17):
        ctrl[prop] = i / 16
        ctrl.update_tag()
        bpy.context.view_layer.update()
        me = mesh_eval(part)
        for v in me.vertices:
            p = part.matrix_world @ v.co
            for dx, dz in ((-.00065, -.00065), (-.00065, .00065), (.00065, -.00065), (.00065, .00065)):
                for y in (-width, width):
                    bm.verts.new((p.x + dx, y, p.z + dz))
        bpy.data.meshes.remove(me)
    ctrl[prop] = 0.0
    ctrl.update_tag()
    bpy.context.view_layer.update()
    hull = bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
    bmesh.ops.delete(bm, geom=hull["geom_interior"], context="VERTS")
    me = bpy.data.meshes.new(name + "_editable_sweep")
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.data.collections["90_Construction_cutters"].objects.link(ob)
    ob.parent = ctrl
    ob.hide_render = True
    ob.display_type = "WIRE"
    ob["purpose"] = "Artistic animation clearance, sampled at 17 poses; not a manufacturing specification"
    frame = bpy.data.objects["Frame_continuous_metal_casting"]
    mod = frame.modifiers.new(name, "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", ob
    index = next((i for i, m in enumerate(frame.modifiers) if m.type in {"BEVEL", "WEIGHTED_NORMAL"}), len(frame.modifiers)-1)
    frame.modifiers.move(len(frame.modifiers)-1, index)
    ob.hide_set(True)
    return ob

def verify_clearance():
    ctrl = bpy.data.objects["CTRL_Launcher"]
    report = {}
    for prop, name in (("hammer_cock", "Hammer_exterior_profile"), ("trigger_press", "Trigger_curved_metal")):
        samples = []
        for i in range(17):
            ctrl[prop] = i / 16
            ctrl.update_tag()
            bpy.context.view_layer.update()
            pairs = bvh(bpy.data.objects[name]).overlap(bvh(bpy.data.objects["Frame_continuous_metal_casting"]))
            samples.append(len(pairs))
        report[prop] = samples
        ctrl[prop] = 0.0
        ctrl.update_tag()
        bpy.context.view_layer.update()
    report["pass"] = all(not n for a in report.values() if isinstance(a, list) for n in a)
    (WORK / "clearance_audit.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["pass"]:
        raise RuntimeError("Mechanism intersects frame: " + str(report))
    print("CLEARANCE_PASS", report, flush=True)
    return report

def grooves():
    native()
    source = SRC / "models" / "launcher" / "flare_pistol_codex_ucupaint_worn_v01.blend"
    bpy.ops.wm.open_mainfile(filepath=str(source))
    clearance("Hammer_travel_groove_source", bpy.data.objects["Hammer_exterior_profile"], "hammer_cock", .0049)
    clearance("Trigger_travel_groove_source", bpy.data.objects["Trigger_curved_metal"], "trigger_press", .00395)
    # Rim remains at the breech; the narrower cartridge body passes through the bore.
    h = helper()
    cutter = h.lathe("Cartridge_rim_seat_source", [(22.5,13.8),(23.8,13.8),(23.8,0),(22.5,0)],
                     "X", (0,0,112), bpy.data.collections["90_Construction_cutters"], None, segments=96)
    cutter.hide_render = True
    cutter.display_type = "WIRE"
    barrel = bpy.data.objects["Barrel_true_open_wall"]
    mod = barrel.modifiers.new("Visible cartridge rim recess", "BOOLEAN")
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    index = next((i for i,m in enumerate(barrel.modifiers) if m.type in {"BEVEL","WEIGHTED_NORMAL"}), len(barrel.modifiers)-1)
    barrel.modifiers.move(len(barrel.modifiers)-1, index)
    cutter.hide_set(True)
    bpy.data.objects["CTRL_Launcher"]["revision"] = "UCUPaint worn v02: hammer/trigger travel grooves and visible cartridge rim seat"
    verify_clearance()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(GROOVED))
    print("GROOVES_SAVED", GROOVED, flush=True)

def probe():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(GROOVED))
    ctrl=bpy.data.objects["CTRL_Launcher"]
    for key in ("open_degrees", "hammer_cock", "trigger_press", "latch_release"): ctrl[key]=0.
    ctrl.update_tag()
    bpy.context.view_layer.update()
    for name in ("Frame_continuous_metal_casting", "Hammer_exterior_profile", "Breech_face"):
        ob=bpy.data.objects.get(name)
        if not ob: continue
        tree=bvh(ob)
        for z in (.110,.112,.114,.116):
            hit=tree.ray_cast(Vector((-.15,0,z)),Vector((1,0,0)))
            print("VISUAL_PROBE",name,z,tuple(hit[0]) if hit[0] else None,flush=True)

def mechanism():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(GROOVED))
    h=helper()
    cutters=bpy.data.collections["90_Construction_cutters"]
    ctrl=bpy.data.objects["CTRL_Launcher"]
    steel=bpy.data.materials["CHECK_Exposed_steel"]
    face=bpy.data.objects["Breech_face"]
    col=face.users_collection[0]
    # The impact pad is fitted to the existing artistic hammer, not a real firearm specification.
    rear=3.9
    hammer=bpy.data.objects["Hammer_exterior_profile"]
    points=[(-12,109),(-6,108),(rear,110.3),(rear,113.7),(-6,115),(-12,115)]
    n=len(points)
    verts=[(x,y,z) for y in (-2.8,2.8) for x,z in points]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    nose=h.mesh("Hammer_striking_nose_source",verts,faces,cutters,None,hammer.parent,True)
    nose.hide_render=True
    nose.display_type="WIRE"
    union=hammer.modifiers.new("Artistic hammer striking nose", "BOOLEAN")
    union.operation,union.solver,union.object="UNION","EXACT",nose
    hammer.modifiers.move(len(hammer.modifiers)-1,0)
    nose.hide_set(True)
    tunnel=h.lathe("Visual_firing_pin_tunnel_source",[(rear-1,1.9),(22.5,1.9),(22.5,0),(rear-1,0)],
                   "X",(0,0,112),cutters,None,segments=64)
    tunnel.hide_render=True
    tunnel.display_type="WIRE"
    for ob in (bpy.data.objects["Frame_continuous_metal_casting"],face):
        mod=ob.modifiers.new("Visible striker aperture", "BOOLEAN")
        mod.operation,mod.solver,mod.object="DIFFERENCE","EXACT",tunnel
        index=next((i for i,m in enumerate(ob.modifiers) if m.type in {"BEVEL","WEIGHTED_NORMAL"}),len(ob.modifiers)-1)
        ob.modifiers.move(len(ob.modifiers)-1,index)
    tunnel.hide_set(True)
    rear_seat=h.lathe("Visual_impact_pad_seat_source",[(3.5,3.0),(5.2,3.0),(5.2,0),(3.5,0)],
                      "X",(0,0,112),cutters,None,segments=64)
    rear_seat.hide_render=True
    rear_seat.display_type="WIRE"
    frame=bpy.data.objects["Frame_continuous_metal_casting"]
    mod=frame.modifiers.new("Visible impact pad seat", "BOOLEAN")
    mod.operation,mod.solver,mod.object="DIFFERENCE","EXACT",rear_seat
    frame.modifiers.move(len(frame.modifiers)-1,0)
    rear_seat.hide_set(True)
    ring=h.lathe("Firing_pin_breech_bushing",[(21.20,2.9),(21.55,2.9),(21.55,1.65),(21.20,1.65)],
                 "X",(0,0,112),col,steel,ctrl,segments=64)
    h.bevel(ring,.12)
    sleeve=h.lathe("Firing_pin_rear_guide",[(5.3,1.8),(7.,1.8),(7.,1.1),(5.3,1.1)],
                   "X",(0,0,112),col,steel,ctrl,segments=64)
    h.bevel(sleeve,.10)
    pivot=bpy.data.objects.new("PIVOT_FiringPin",None)
    col.objects.link(pivot)
    pivot.parent=ctrl
    pivot.location=PIVOTS["FiringPin"]
    ctrl["firing_pin"]=0.
    ctrl.id_properties_ui("firing_pin").update(min=0.,max=1.)
    curve=pivot.driver_add("location",0)
    var=curve.driver.variables.new()
    var.name="travel"
    var.type="SINGLE_PROP"
    var.targets[0].id=ctrl
    var.targets[0].data_path='["firing_pin"]'
    curve.driver.expression="0.017 + 0.00055 * travel"
    bpy.context.view_layer.update()
    for name,profile in [
        ("Firing_pin_visible_tip",[(rear+.4,.75),(21.55,.75),(21.65,.5),(21.65,0),(rear+.4,0)]),
        ("Hammer_impact_pad",[(rear,2.6),(rear+.55,2.6),(rear+.55,0),(rear,0)])]:
        ob=h.lathe(name,profile,"X",(0,0,112),col,steel,pivot,segments=64)
        h.bevel(ob,.10)
        ob["purpose"]="Visible artistic ignition detail for game animation"
    ctrl["revision"]="UCUPaint worn v03: lever grooves, rim seat, visible breech bushing, impact pad and animated firing pin"
    verify_clearance()
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(HP))
    print("MECHANISM_SAVED",HP,flush=True)

def render_grooves():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(HP))
    h = helper()
    h.set_gpu()
    out = WORK / "previews"
    out.mkdir(parents=True, exist_ok=True)
    for col in ("02_Cartridge_Red_Illumination", "03_Cartridge_Green_Airdrop"):
        bpy.data.collections[col].hide_render = True
    scene = bpy.context.scene
    ctrl = bpy.data.objects["CTRL_Launcher"]
    for name, cam, target, scale, cock, trigger, opening in [
        ("01_grooves_overview",(.22,-.32,.205),(.026,0,.071),.244,0,0,0),
        ("02_hammer_groove",(-.12,-.07,.25),(-.018,0,.108),.10,1,0,0),
        ("03_trigger_groove",(.08,-.09,.027),(.012,0,.074),.087,0,1,0),
        ("04_open_breech",(.17,-.2,.26),(.022,0,.088),.231,0,0,48),
        ("14_breech_firing_pin",(.11,-.10,.18),(.022,0,.111),.069,1,0,48),
        ("15_hammer_impact_pad",(-.05,-.07,.17),(.006,0,.112),.076,1,0,48)]:
        ctrl["hammer_cock"], ctrl["trigger_press"], ctrl["open_degrees"] = cock, trigger, opening
        ctrl.update_tag()
        bpy.context.view_layer.update()
        scene.camera.location = cam
        h.aim(scene.camera, target)
        scene.camera.data.ortho_scale = scale
        scene.cycles.samples = 32
        scene.render.resolution_x, scene.render.resolution_y = 1200, 1000
        scene.render.filepath = str(out / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        print("GROOVE_RENDER", name, flush=True)

def selected(objects, active=None):
    for ob in bpy.context.selected_objects:
        ob.select_set(False)
    for ob in objects:
        ob.hide_set(False)
        ob.select_set(True)
    bpy.context.view_layer.objects.active = active or objects[0]

def part_of(ob):
    parent = ob.parent.name if ob.parent else ""
    return {"PIVOT_Barrel_hinge":"Barrel", "PIVOT_Hammer":"Hammer", "PIVOT_FiringPin":"FiringPin",
            "PIVOT_Trigger":"Trigger", "PIVOT_Breech_latch":"Latch"}.get(parent, "Frame")

def set_of(ob):
    if ob.name.startswith("02_Cartridge_"): return "ammo_red"
    if ob.name.startswith("03_Cartridge_"): return "ammo_green"
    mat = ob.data.materials[0].name
    return {"CHECK_Metal_body_unpainted":"gun_paint", "CHECK_Exposed_steel":"gun_steel",
            "CHECK_Thin_black_plastic":"gun_grip"}[mat]

def target_budget(ob):
    name = ob.name
    if name == "Frame_continuous_metal_casting": return 4200
    if name == "Barrel_true_open_wall": return 2300
    if name.startswith("Grip_panel"): return 1050
    if name == "Hammer_exterior_profile": return 650
    if name == "Trigger_curved_metal": return 300
    if name == "Barrel_underlug": return 360
    if name.endswith("colored_sleeve"): return 320
    if name.endswith("metal_head_rim"): return 320
    if "primer" in name: return 64
    if "crimp_fold" in name: return 16
    if "head_face" in name or "mouth_closure" in name: return 96
    if "Breech_face" == name: return 140
    return 112

def lowpoly():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(HP))
    ctrl = bpy.data.objects["CTRL_Launcher"]
    for key in ("open_degrees", "hammer_cock", "trigger_press", "latch_release", "firing_pin"):
        ctrl[key] = 0.0
    ctrl.update_tag()
    bpy.context.view_layer.update()
    col = bpy.data.collections.new("10_Game_meshes_Codex")
    bpy.context.scene.collection.children.link(col)
    high = [o for o in bpy.context.scene.objects if o.type == "MESH" and not o.hide_render]
    sets = {}
    source_names = {}
    for ob in high:
        key = set_of(ob)
        source_names.setdefault(key, []).append(ob.name)
        if "Grip_fine_relief" in ob.name:
            continue  # Its thousands of pebbles become baked tangent normals.
        me = mesh_eval(ob)
        me.transform(ob.matrix_world)
        # Boolean and lathe poles can leave coincident vertices and zero-area faces.
        # Remove those before reducing the silhouette; baked UVs are created afterwards.
        bm=bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.0000001)
        bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=0.0000001)
        bm.to_mesh(me)
        bm.free()
        for attr in list(me.color_attributes): me.color_attributes.remove(attr)
        me.validate(clean_customdata=True)
        me.update()
        low = bpy.data.objects.new("LOW_"+ob.name, me)
        col.objects.link(low)
        selected([low])
        me.calc_loop_triangles()
        ratio = min(1.0, target_budget(ob) / max(1,len(me.loop_triangles)))
        if ratio < 1:
            mod = low.modifiers.new("Game silhouette reduction", "DECIMATE")
            mod.ratio = ratio
            mod.use_collapse_triangulate = True
            bpy.ops.object.modifier_apply(modifier=mod.name)
        tri = low.modifiers.new("Stable bake triangulation", "TRIANGULATE")
        tri.keep_custom_normals = True
        bpy.ops.object.modifier_apply(modifier=tri.name)
        print("LOW_SOURCE",ob.name,len(low.data.polygons),"budget",target_budget(ob),flush=True)
        group = low.vertex_groups.new(name="Cartridge" if key.startswith("ammo_") else part_of(ob))
        group.add(list(range(len(low.data.vertices))), 1., "REPLACE")
        sets.setdefault(key, []).append(low)
    report = {"high_source":str(HP), "sets":{}}
    for key, group in sets.items():
        selected(group)
        bpy.ops.object.join()
        low = bpy.context.object
        low.name = "GAME_"+key
        low["high_sources"] = json.dumps(source_names[key])
        for layer in list(low.data.uv_layers):
            low.data.uv_layers.remove(layer)
        low.data.uv_layers.new(name="GameUV")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=.012,
                                area_weight=.8, correct_aspect=True, scale_to_bounds=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        low.data.uv_layers.active.name = "GameUV"
        low.data.uv_layers.active.active_render = True
        low.data.calc_loop_triangles()
        if any(not math.isfinite(c) for uv in low.data.uv_layers.active.data for c in uv.uv):
            raise RuntimeError("Non-finite GameUV on "+key)
        mat = bpy.data.materials.new("Codex_"+key+"_game_PBR")
        mat.use_nodes = True
        low.data.materials.clear()
        low.data.materials.append(mat)
        for poly in low.data.polygons:
            poly.material_index = 0
        report["sets"][key] = {"triangles":len(low.data.loop_triangles), "vertices":len(low.data.vertices),
                               "source_objects":source_names[key], "uv":"GameUV"}
    for ob in high:
        ob.hide_render = True
        ob.hide_set(True)
    bpy.ops.wm.save_as_mainfile(filepath=str(LP))
    (WORK / "lowpoly_audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("LOWPOLY_SAVED", {k:v["triangles"] for k,v in report["sets"].items()}, flush=True)

def source_emission(materials, channel):
    keep = []
    for mat in materials:
        tree = mat.node_tree
        out = next(n for n in tree.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        p = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        socket = p.inputs[{"base_color":"Base Color","roughness":"Roughness","metallic":"Metallic"}[channel]]
        old = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].links else None
        emit = tree.nodes.new("ShaderNodeEmission")
        if socket.is_linked: tree.links.new(socket.links[0].from_socket,emit.inputs["Color"])
        else:
            v = socket.default_value
            emit.inputs["Color"].default_value = tuple(v) if hasattr(v,"__len__") else (v,v,v,1)
        tree.links.new(emit.outputs[0],out.inputs["Surface"])
        keep.append((mat,old,emit))
    return keep

def restore_emission(keep):
    for mat,old,emit in keep:
        tree=mat.node_tree
        out=next(n for n in tree.nodes if n.type=="OUTPUT_MATERIAL" and n.is_active_output)
        tree.nodes.remove(emit)
        if old: tree.links.new(old,out.inputs["Surface"])

def connect_game_material(low, images):
    tree = low.data.materials[0].node_tree
    tree.nodes.clear()
    out = tree.nodes.new("ShaderNodeOutputMaterial")
    p = tree.nodes.new("ShaderNodeBsdfPrincipled")
    tree.links.new(p.outputs[0],out.inputs["Surface"])
    uv = tree.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "GameUV"
    for channel,img in images.items():
        node = tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.label = channel
        tree.links.new(uv.outputs[0],node.inputs["Vector"])
        if channel == "normal":
            normal = tree.nodes.new("ShaderNodeNormalMap")
            normal.uv_map="GameUV"
            tree.links.new(node.outputs["Color"],normal.inputs["Color"])
            tree.links.new(normal.outputs["Normal"],p.inputs["Normal"])
        elif channel == "orm":
            sep = tree.nodes.new("ShaderNodeSeparateColor")
            tree.links.new(node.outputs["Color"],sep.inputs[0])
            tree.links.new(sep.outputs["Green"],p.inputs["Roughness"])
            tree.links.new(sep.outputs["Blue"],p.inputs["Metallic"])
        elif channel == "base_color":
            tree.links.new(node.outputs["Color"],p.inputs["Base Color"])

def bake():
    import numpy as np
    native()
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    helper().set_gpu()
    scene=bpy.context.scene
    scene.render.engine="CYCLES"
    scene.cycles.samples=12
    scene.render.bake.use_selected_to_active=True
    scene.render.bake.cage_extrusion=.00065
    scene.render.bake.max_ray_distance=.0015
    scene.render.bake.margin=12
    scene.render.bake.use_clear=True
    scene.render.bake.normal_space="TANGENT"
    TEX.mkdir(parents=True,exist_ok=True)
    report={}
    for low in [o for o in scene.objects if o.name.startswith("GAME_")]:
        key=low.name[5:]
        resolution=1024 if key.startswith("ammo_") else 2048
        highs=[bpy.data.objects[n] for n in json.loads(low["high_sources"])]
        mats=set(m for o in highs for m in o.data.materials if m)
        for ob in highs: ob.hide_render=False
        images={}
        for channel in ("base_color","roughness","metallic","normal"):
            print("BAKE_BEGIN",key,channel,flush=True)
            img=bpy.data.images.new("Flare_Codex_"+key+"_"+channel,resolution,resolution,alpha=False)
            img.colorspace_settings.name="sRGB" if channel=="base_color" else "Non-Color"
            node=low.data.materials[0].node_tree.nodes.new("ShaderNodeTexImage")
            node.image=img
            low.data.materials[0].node_tree.nodes.active=node
            selected(highs+[low],low)
            keep=source_emission(mats,channel) if channel!="normal" else []
            try: bpy.ops.object.bake(type="NORMAL" if channel=="normal" else "EMIT")
            finally: restore_emission(keep)
            if channel in ("base_color","normal"):
                img.filepath_raw=str(TEX/(key+"_"+channel+".png"))
                img.file_format="PNG"
                img.save()
            images[channel]=img
            print("BAKE_DONE",key,channel,flush=True)
        data={}
        for channel in ("roughness","metallic","normal"):
            px=np.empty(resolution*resolution*4,dtype=np.float32)
            images[channel].pixels.foreach_get(px)
            data[channel]=px.reshape((-1,4))
        orm=np.ones((resolution*resolution,4),dtype=np.float32)
        orm[:,1]=data["roughness"][:,0]
        orm[:,2]=data["metallic"][:,0]
        img=bpy.data.images.new("Flare_Codex_"+key+"_orm",resolution,resolution,alpha=False)
        img.colorspace_settings.name="Non-Color"
        img.pixels.foreach_set(orm.ravel())
        img.filepath_raw=str(TEX/(key+"_orm.png"))
        img.file_format="PNG"
        img.save()
        report[key]={"resolution":resolution,"normal_range":[float(data["normal"][:,:3].min()),float(data["normal"][:,:3].max())],
                     "roughness_range":[float(orm[:,1].min()),float(orm[:,1].max())],
                     "metallic_range":[float(orm[:,2].min()),float(orm[:,2].max())]}
        connect_game_material(low,{"base_color":images["base_color"],"normal":images["normal"],"orm":img})
        for ob in highs:
            ob.hide_render=True
            ob.hide_set(True)
        bpy.ops.wm.save_as_mainfile(filepath=str(LP))
    (WORK/"bake_audit.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("BAKE_PASS",report,flush=True)

def copy_group(source, name, collection):
    ob = source.copy()
    ob.data = source.data.copy()
    collection.objects.link(ob)
    ob.name = name
    selected([ob])
    group = name.split("_")[0]
    mod = ob.modifiers.new("Isolate rigid part", "MASK")
    mod.vertex_group = group
    bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.vertex_groups.clear()
    return ob

def export_glb(path, objects, animations=False):
    selected(objects)
    bpy.ops.export_scene.gltf(filepath=str(path),export_format="GLB",use_selection=True,
                              export_yup=True,export_animations=animations,export_skins=animations,
                              export_normals=True,export_tangents=True,
                              export_all_influences=True,export_def_bones=False,
                              export_animation_mode="NLA_TRACKS",export_force_sampling=True,
                              export_materials="EXPORT",export_image_format="AUTO",
                              export_apply=False,export_cameras=False,export_lights=False)
    print("GLB_SAVED",path,flush=True)

def world():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    col=bpy.data.collections.new("20_World_export_Codex")
    bpy.context.scene.collection.children.link(col)
    root=bpy.data.objects.new("FlarePistolCodex",None)
    col.objects.link(root)
    objects=[root]
    parts={}
    for key,pivot in PIVOTS.items():
        ob=bpy.data.objects.new(key,None)
        col.objects.link(ob)
        ob.parent=root
        ob.location=GAME_TRANSFORM @ pivot
        parts[key]=ob
        objects.append(ob)
    bpy.context.view_layer.update()
    for key in ("gun_paint","gun_steel","gun_grip"):
        source=bpy.data.objects["GAME_"+key]
        for group in source.vertex_groups:
            ob=copy_group(source,group.name+"_"+key,col)
            ob.data.transform(GAME_TRANSFORM)
            ob.parent=parts[group.name]
            ob.matrix_parent_inverse=ob.parent.matrix_world.inverted()
            ob.matrix_world=Matrix.Identity(4)
            for attr in list(ob.data.color_attributes): ob.data.color_attributes.remove(attr)
            ob.data.validate(verbose=True,clean_customdata=False)
            objects.append(ob)
    for name,point,parent in [("Muzzle",(.1148,0,.112),"Barrel"),("SightRear",(.026,0,.130),"Frame"),
                              ("SightFront",(.105,0,.130),"Barrel"),("GripR",tuple(GRIP),"Frame"),
                              ("GripL",(-.045,.020,.030),"Frame")]:
        mark=bpy.data.objects.new(name,None)
        col.objects.link(mark)
        mark.parent=parts[parent]
        mark.location=(GAME_TRANSFORM @ Vector(point))-mark.parent.location
        objects.append(mark)
    bpy.context.view_layer.update()
    OUT.mkdir(parents=True,exist_ok=True)
    export_glb(OUT/"flare_pistol_codex.glb",objects)
    report={"world_triangles":sum(len(o.data.polygons) for o in objects if o.type=="MESH"),
            "axes":"+Z muzzle, +Y up, origin at grip", "parts":list(parts),"source":str(LP)}
    for key,center in (("ammo_red",(.143,-.002,0)),("ammo_green",(.181,0,0))):
        source=bpy.data.objects["GAME_"+key]
        ob=source.copy()
        ob.data=source.data.copy()
        col.objects.link(ob)
        ob.name="CartridgeRed" if key=="ammo_red" else "CartridgeGreen"
        ob.data.transform(Matrix.Translation(-Vector(center)))
        ob.vertex_groups.clear()
        export_glb(OUT/("flare_red_codex.glb" if key=="ammo_red" else "flare_green_codex.glb"),[ob])
    (OUT/"asset_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    # Keep a reviewable export scene without overwriting the low-poly bake source.
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/"flare_pistol_codex_world.blend"))

def render_lowpoly():
    native()
    bpy.ops.wm.open_mainfile(filepath=str(LP))
    h=helper()
    h.set_gpu()
    scene=bpy.context.scene
    for ob in scene.objects:
        if ob.type=="MESH": ob.hide_render=not ob.name.startswith("GAME_gun_")
    scene.camera.location=(.22,-.32,.205)
    h.aim(scene.camera,(.026,0,.071))
    scene.camera.data.ortho_scale=.244
    scene.cycles.samples=32
    scene.render.resolution_x,scene.render.resolution_y=1200,1000
    scene.render.filepath=str(WORK/"previews"/"05_lowpoly_baked.png")
    bpy.ops.render.render(write_still=True)

if __name__ == "__main__":
    mode = sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "grooves"
    if mode == "grooves": grooves()
    elif mode == "probe": probe()
    elif mode == "mechanism": mechanism()
    elif mode == "render": render_grooves()
    elif mode == "lowpoly": lowpoly()
    elif mode == "bake": bake()
    elif mode == "world": world()
    elif mode == "render_lowpoly": render_lowpoly()
    elif mode == "verify":
        native()
        bpy.ops.wm.open_mainfile(filepath=str(HP))
        verify_clearance()
