"""Скругление корпуса v07; геометрия предъявляется до нового текстурирования."""
import bpy,bmesh,numpy as np,math,json,hashlib,importlib.util,sys,os,re
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"_asset_src/grenade_codex/geometry_review_v07"
SOURCE=Path("E:/Models Blender/From Scenario/Grenade/Codex_Geometry_v05/Grenade_MkII_geometry_review_v05.blend")
SOURCE_SHA="0c8a359c081355b889e0bd6ea77b2f40fc8faaac5eeb96aacc04ce9b84c14c03"
FILE=Path(os.environ.get("GRENADE_ROUNDING_FILE",str(OUT/"Grenade_MkII_geometry_review_v07.blend")))
NAMES=["GrenadeBody","BottomPlug","FuzeCasting","SafetyLever","PinEyelet","PullRing","SafetyPin"]
SIGMA=.00045
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
S=module("rounding_studio",ROOT/"tools/grenade_codex_blender.py")
def digest_mesh(me):
    chunks=[]
    for seq,prop,n,dtype in [(me.vertices,"co",3,np.float32),(me.edges,"vertices",2,np.int32),(me.loops,"vertex_index",1,np.int32),(me.polygons,"loop_start",1,np.int32),(me.polygons,"loop_total",1,np.int32)]:
        a=np.empty(len(seq)*n,dtype);seq.foreach_get(prop,a);chunks.append(a.tobytes())
    return hashlib.sha256(b"".join(chunks)).hexdigest()
def snapshot():
    result={}
    for name in NAMES:
        ob=bpy.data.objects[name];me=ob.data
        keys={}
        if me.shape_keys:
            for key in me.shape_keys.key_blocks:
                a=np.empty(len(key.data)*3,np.float32);key.data.foreach_get("co",a);keys[key.name]=hashlib.sha256(a.tobytes()).hexdigest()
        result[name]={"mesh":digest_mesh(me),"matrix":list(map(list,ob.matrix_world)),"parent":ob.parent.name if ob.parent else None,"keys":keys,"modifiers":[[m.name,m.type,getattr(m,"levels",None),getattr(m,"render_levels",None)] for m in ob.modifiers]}
    return result
def setup():
    S.setup_studio((0,0,0));sc=bpy.context.scene
    sc.cycles.samples=192;sc.cycles.use_denoising=False
    sc.render.resolution_x=sc.render.resolution_y=1800
    sc.render.image_settings.color_mode="RGB";sc.render.image_settings.color_depth="8"
    mat=bpy.data.materials.get("Neutral cast geometry v07") or bpy.data.materials.new("Neutral cast geometry v07")
    mat.use_nodes=True
    p=next(n for n in mat.node_tree.nodes if n.type=="BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value=(.17,.18,.19,1);p.inputs["Metallic"].default_value=.2;p.inputs["Roughness"].default_value=.40
    for ob in sc.objects:
        if ob.type=="MESH":ob.data.materials.clear();ob.data.materials.append(mat)
    return mat
def camera(pos=(.17,-.28,.18),target=(0,0,.057),scale=.155):
    sc=bpy.context.scene;sc.camera.location=pos;S.aim(sc.camera,target);sc.camera.data.ortho_scale=scale
def ray_field(mesh):
    tree=BVHTree.FromPolygons([v.co.copy() for v in mesh.vertices],[list(p.vertices) for p in mesh.polygons])
    nt,nz=512,641;phi=np.arange(nt)*math.tau/nt;z=np.linspace(0,.086,nz)
    r=np.empty((nz,nt),np.float64)
    for i,zz in enumerate(z):
        qz=min(.085999,max(.000001,zz))
        for j,pp in enumerate(phi):
            d=Vector((math.cos(pp),math.sin(pp),0))
            hit=tree.ray_cast(d*.055+Vector((0,0,qz)),-d,.06)[0]
            assert hit is not None,(i,j)
            r[i,j]=math.hypot(hit.x,hit.y)
    return r,z,phi
def round_field(r,z,phi):
    result=r.copy();nz,nt=r.shape
    for axis,ss in [(0,SIGMA/(z[1]-z[0])),(1,SIGMA/(.027*math.tau/nt))]:
        half=math.ceil(3*ss);offsets=np.arange(-half,half+1)
        weights=np.exp(-.5*(offsets/ss)**2);weights/=weights.sum()
        if axis==0:
            padded=np.pad(result,((half,half),(0,0)),mode="edge")
            result=sum(w*padded[k:k+nz] for k,w in enumerate(weights))
        else:result=sum(w*np.roll(result,int(k),axis=1) for k,w in zip(offsets,weights))
    blend=np.clip(z/.002,0,1)*np.clip((.083-z)/.005,0,1);blend=blend*blend*(3-2*blend)
    return r*(1-blend[:,None])+result*blend[:,None]
def make_body(r,z,phi):
    nt=len(phi);nz=len(z)
    vs=[(float(rr*math.cos(pp)),float(rr*math.sin(pp)),float(zz)) for row,zz in zip(r,z) for rr,pp in zip(row,phi)]
    bottom=len(vs);vs.append((0,0,0))
    fs=[(i*nt+j,i*nt+(j+1)%nt,(i+1)*nt+(j+1)%nt,(i+1)*nt+j) for i in range(nz-1) for j in range(nt)]
    fs.extend((bottom,(j+1)%nt,j) for j in range(nt))
    me=bpy.data.meshes.new("GrenadeBody • continuous rounded casting v07")
    me.from_pydata(vs,[],fs);me.update()
    for p in me.polygons:p.use_smooth=True
    return me
def build():
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA
    bpy.context.preferences.use_preferences_save=False
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update()
    previous=snapshot();body=bpy.data.objects["GrenadeBody"]
    old=body.data;old.name="ARCHIVE • Body v05 with original UV";old.use_fake_user=True
    r,z,phi=ray_field(old);rounded=round_field(r,z,phi);body.data=make_body(rounded,z,phi)
    body["geometry_revision"]="v07: rounded corners and continuous sector-to-shell junctions"
    OUT.mkdir(parents=True,exist_ok=True)
    setup();camera()
    layer=sc.view_layers[0]
    for ob in layer.objects:ob.select_set(False,view_layer=layer)
    body.select_set(True,view_layer=layer);layer.objects.active=body
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                sp=area.spaces.active;sp.shading.type="MATERIAL";sp.clip_start=.001
                sp.overlay.show_overlays=False;sp.region_3d.view_perspective="CAMERA"
    # Старые изображения сохраняются встроенными и рядом с геометрией.
    images=[]
    for i,im in enumerate(bpy.data.images):
        if im.type in {"RENDER_RESULT","COMPOSITING"}:continue
        assert im.packed_file,im.name
        data=bytes(im.packed_file.data);suffix=".png" if data.startswith(b"\x89PNG") else Path(im.filepath).suffix or ".bin"
        name=f"{i:02d}_"+re.sub(r"[^A-Za-z0-9_.-]","_",im.name)
        if not name.lower().endswith(suffix.lower()):name+=suffix
        path=OUT/"textures/reference"/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        im.filepath="//textures/reference/"+name
        images.append({"name":im.name,"path":im.filepath,"sha256":hashlib.sha256(data).hexdigest()})
    record={"stage":"geometry_v07_pending_owner_review","source":str(SOURCE),"source_sha256":SOURCE_SHA,"previous":previous,"body_hash":digest_mesh(body.data),"source_uv_archive":old.name,"sigma_mm":SIGMA*1000,"max_radial_change_mm":float(np.max(np.abs(rounded-r))*1000),"source_dimensions_mm":[63.4011887,63.4011887,85.9999657],"images":images}
    text=bpy.data.texts.new("00 • V07 GEOMETRY REVIEW")
    text.write("Rounded body casting v07. Awaiting owner review before UV and revised UCUPaint.\nOriginal v05 body with its UV is preserved as a fake-user mesh archive.\nSix other meshes and visual pin/lever rig are retained.\nNeutral inspection material only.\n")
    sc.render.filepath="//previews/01_overall.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False)
    (OUT/"build.json").write_text(json.dumps(record,indent=2),encoding="utf8")
    print("BODY_ROUNDING_V07_SAVED",FILE,flush=True)
def world_tree(name):
    ev=bpy.data.objects[name].evaluated_get(bpy.context.evaluated_depsgraph_get());me=ev.to_mesh()
    tree=BVHTree.FromPolygons([ev.matrix_world@v.co for v in me.vertices],[list(p.vertices) for p in me.polygons])
    ev.to_mesh_clear();return tree
def audit():
    bpy.context.preferences.use_preferences_save=False
    bpy.ops.wm.open_mainfile(filepath=str(FILE));sc=bpy.context.scene;sc.frame_set(1);bpy.context.view_layer.update()
    record=json.loads((OUT/"build.json").read_text(encoding="utf8"));current=snapshot()
    assert set(o.name for o in sc.objects if o.type=="MESH")==set(NAMES)
    for name in NAMES:
        if name!="GrenadeBody":assert current[name]==record["previous"][name],name
    body=bpy.data.objects["GrenadeBody"];assert digest_mesh(body.data)==record["body_hash"]
    assert digest_mesh(bpy.data.meshes[record["source_uv_archive"]])==record["previous"]["GrenadeBody"]["mesh"]
    bm=bmesh.new();bm.from_mesh(body.data)
    boundary=[e for e in bm.edges if e.is_boundary]
    assert len(boundary)==512 and all(abs(v.co.z-.086)<1e-7 for e in boundary for v in e.verts)
    assert not [e for e in bm.edges if len(e.link_faces)>2 or not e.link_faces]
    assert min(f.calc_area() for f in bm.faces)>1e-13
    assert all(f.normal.dot(Vector((f.calc_center_median().x,f.calc_center_median().y,0)))>0 for f in bm.faces if len(f.verts)==4)
    topo={"vertices":len(bm.verts),"faces":len(bm.faces),"neck_boundary_edges":len(boundary),"overfull_or_wire_edges":0}
    bm.free()
    points=[o.evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world@Vector(p) for o in sc.objects if o.type=="MESH" for p in o.evaluated_get(bpy.context.evaluated_depsgraph_get()).bound_box]
    dims=[(max(v[i] for v in points)-min(v[i] for v in points))*1000 for i in range(3)]
    assert abs(dims[2]-114.510903)<.01
    assert abs(body.dimensions.z-.086)<1e-6 and 62.9<body.dimensions.x*1000<63.5
    for row in record["images"]:
        im=bpy.data.images[row["name"]];path=Path(bpy.path.abspath(im.filepath))
        assert im.packed_file and hashlib.sha256(bytes(im.packed_file.data)).hexdigest()==row["sha256"]
        assert path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==row["sha256"]
    tree=world_tree("GrenadeBody");poses=[]
    for frame in [1,17,25,30,36,45,54,59,65,75,83,90,96]:
        sc.frame_set(frame);bpy.context.view_layer.update()
        root=bpy.data.objects["CTRL_Grenade"];p=float(root["pin_pull"]);l=float(root["lever_open"])
        off=float(bpy.data.objects["CTRL_PinAssembly"].location.y)
        expected=-.0006*min(1,p/.16)-.0514*max(0,(p-.16)/.84)
        assert abs(off-expected)<1e-6
        compression=bpy.data.objects["SafetyPin"].data.shape_keys.key_blocks["SplitTips_Compress"].value
        assert abs(compression-min(1,max(0,p/.16))*min(1,max(0,(.74-p)/.14)))<1e-6
        assert not tree.overlap(world_tree("SafetyLever")),frame
        poses.append({"frame":frame,"pin_pull":p,"lever_open":l,"body_lever_intersections":0})
    report={"pass":True,"candidate":str(FILE),"sha256":hashlib.sha256(FILE.read_bytes()).hexdigest(),"source_sha256":SOURCE_SHA,"body_dimensions_mm":list(body.dimensions*1000),"closed_dimensions_mm":dims,"topology":topo,"six_other_meshes_unchanged":True,"preserved_v05_body_uv_archive":True,"poses":poses,"packed_images":len(record["images"]),"status":"awaiting geometry review"}
    path=Path(os.environ.get("GRENADE_ROUNDING_AUDIT",str(OUT/"audit.json")))
    path.write_text(json.dumps(report,indent=2),encoding="utf8")
    print("BODY_ROUNDING_AUDIT_OK",dims,flush=True)
VIEWS=[("01_overall",(.17,-.28,.18),(0,0,.057),.155,1),
       ("02_cast_macro",(.11,-.19,.105),(.001,0,.043),.079,1),
       ("03_cast_reverse",(-.11,.19,.105),(0,0,.043),.079,1),
       ("04_cast_low",(.12,-.19,.025),(0,0,.044),.077,1),
       ("05_cast_shoulder",(.09,-.17,.15),(0,0,.066),.066,1),
       ("06_motion",(.20,-.30,.19),(.025,-.009,.074),.175,54)]
def render():
    bpy.context.preferences.use_preferences_save=False
    for source,prefix in [(SOURCE,"before"),(FILE,"after")]:
        bpy.ops.wm.open_mainfile(filepath=str(source));setup();sc=bpy.context.scene
        for name,pos,target,scale,frame in VIEWS:
            if prefix=="before" and name not in {"01_overall","02_cast_macro","05_cast_shoulder"}:continue
            sc.frame_set(frame);bpy.context.view_layer.update();camera(pos,target,scale)
            sc.render.filepath=str(OUT/"previews"/(prefix+"_"+name+".png"));Path(sc.render.filepath).parent.mkdir(parents=True,exist_ok=True)
            print("ROUNDING_RENDER_BEGIN",prefix,name,flush=True);bpy.ops.render.render(write_still=True);print("ROUNDING_RENDER_OK",prefix,name,flush=True)
if __name__=="__main__":
    mode=sys.argv[sys.argv.index("--")+1] if "--" in sys.argv else "build"
    {"build":build,"audit":audit,"render":render}[mode]()

