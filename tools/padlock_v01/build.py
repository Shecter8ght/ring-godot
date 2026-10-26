"""Редактируемый замок по шести ракурсам владельца; этап проверки формы."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import bpy
import bmesh
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "_asset_src" / "padlock_v01"
MM = 0.001
PARTS: list[bpy.types.Object] = []
CAMERAS: dict[str, bpy.types.Object] = {}


def collection(name: str) -> bpy.types.Collection:
    value = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(value)
    return value


def move_to(obj: bpy.types.Object, target: bpy.types.Collection) -> None:
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    target.objects.link(obj)


def material(name: str, value: float) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    node = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    node.inputs["Base Color"].default_value = (value, value, value, 1)
    node.inputs["Metallic"].default_value = 0
    node.inputs["Roughness"].default_value = 0.43
    mat.diffuse_color = (value, value, value, 1)
    return mat


def mesh_object(name, vertices, faces, target, mat=None, part=True):
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    if bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    if mat:
        mesh.materials.append(mat)
    if part:
        PARTS.append(obj)
    return obj


def bevel(obj, width, segments=4, angle=0.45):
    mod = obj.modifiers.new("Радиус кромки", "BEVEL")
    mod.width = width * MM
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = angle
    mod.harden_normals = True
    for face in obj.data.polygons:
        face.use_smooth = True


def difference(obj, cutter, name):
    mod = obj.modifiers.new(name, "BOOLEAN")
    mod.operation = "DIFFERENCE"
    available = [v.identifier for v in mod.bl_rna.properties["solver"].enum_items]
    mod.solver = "EXACT" if "EXACT" in available else available[0]
    mod.object = cutter
    cutter.hide_render = True
    cutter.hide_set(True)
    cutter.display_type = "WIRE"


def cubic(points, a, b, c, d, count=12):
    for i in range(count):
        t = i / count
        u = 1 - t
        points.append((u**3*a[0] + 3*u*u*t*b[0] + 3*u*t*t*c[0] + t**3*d[0],
                       u**3*a[1] + 3*u*u*t*b[1] + 3*u*t*t*c[1] + t**3*d[1]))


def body_profile():
    p = []
    cubic(p, (-36.4, 69), (-31, 69.2), (-18, 69.1), (-11.1, 69), 14)
    cubic(p, (-11.1, 69), (-7.6, 63.8), (-3.6, 61.8), (0, 61.8), 12)
    cubic(p, (0, 61.8), (4.2, 61.9), (8.2, 65.3), (11.1, 69.8), 12)
    cubic(p, (11.1, 69.8), (18, 70.0), (31, 70.4), (36.1, 70.2), 14)
    cubic(p, (36.1, 70.2), (37.7, 70.1), (38.1, 69.4), (38.5, 67.5), 5)
    cubic(p, (38.5, 67.5), (42.6, 50.5), (41.1, 37), (37.3, 26.8), 24)
    cubic(p, (37.3, 26.8), (31.9, 10.3), (18.3, 0.1), (1.4, 0), 28)
    cubic(p, (1.4, 0), (-17.0, -0.2), (-31.7, 10.1), (-37.0, 26.1), 28)
    cubic(p, (-37.0, 26.1), (-41.7, 39.5), (-41.4, 53.3), (-38.1, 67.0), 24)
    cubic(p, (-38.1, 67.0), (-37.7, 68.6), (-37.2, 69.0), (-36.4, 69), 5)
    xmin, xmax = min(x for x, _ in p), max(x for x, _ in p)
    zmin = min(z for _, z in p)
    return [((x - (xmin+xmax)/2)*80/(xmax-xmin), z-zmin) for x,z in p]


def scaled_profile(profile, factor):
    return [(x*factor, 35 + (z-35)*factor) for x,z in profile]


def prism(name, profile, y0, y1, target, mat=None, part=True):
    n = len(profile)
    vertices = [(x*MM, y*MM, z*MM) for y in (y0,y1) for x,z in profile]
    faces = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh_object(name, vertices, faces, target, mat, part)


def cheek(name, profile, side, target, mat):
    n = len(profile)
    vertices, faces = [], []
    rings = 13
    for depth in (9.05,11.15):
        for ring in range(rings):
            scale = 1-ring/rings
            bow = 0.38*(1-scale*scale)
            for x,z in profile:
                vertices.append((x*scale*MM, side*(depth+bow)*MM,
                                 (35+(z-35)*scale)*MM))
    for half in range(2):
        start=half*rings*n
        for ring in range(rings-1):
            for i in range(n):
                a=start+ring*n+i
                b=start+ring*n+(i+1)%n
                faces.append((a,b,b+n,a+n))
        faces.append(tuple(start+(rings-1)*n+i for i in range(n)))
    offset=rings*n
    for i in range(n):
        faces.append((i,(i+1)%n,(i+1)%n+offset,i+offset))
    return mesh_object(name, vertices, faces, target, mat)


def cylinder(name, radius, depth, location, target, mat=None, axis="Z", part=False):
    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=radius*MM,
                                      depth=depth*MM, location=tuple(v*MM for v in location))
    obj=bpy.context.object
    obj.name=name
    if axis=="Y":
        obj.rotation_euler[0]=math.pi/2
    bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    move_to(obj,target)
    if mat:
        obj.data.materials.append(mat)
    if part:
        PARTS.append(obj)
    return obj


def key_profile():
    cx,cz,r=0.8,21.1,4.45
    result=[(cx+r*math.cos(math.radians(-45+i*270/64)),
             cz+r*math.sin(math.radians(-45+i*270/64))) for i in range(65)]
    result += [(cx-2.0,16.8),(cx-1.9,8.0)]
    for i in range(13):
        a=math.pi+i*math.pi/12
        result.append((cx+1.9*math.cos(a),8.0+1.1*math.sin(a)))
    result += [(cx+2.05,16.8)]
    return result


def shackle(target, mat):
    path=[]
    for i in range(25):
        path.append(Vector((-25,0,59.8+(88.8-59.8)*i/24)))
    for i in range(1,97):
        a=math.pi-math.pi*i/96
        path.append(Vector((25*math.cos(a),0,88.8+25*math.sin(a))))
    for i in range(1,25):
        path.append(Vector((25,0,88.8-(88.8-59.8)*i/24)))
    vertices,faces=[],[]
    cross=64
    for i,p in enumerate(path):
        tangent=(path[min(i+1,len(path)-1)]-path[max(0,i-1)]).normalized()
        side=Vector((0,1,0))
        radial=tangent.cross(side).normalized()
        radius=6.2*(1+0.004*math.sin(i*0.071))
        for j in range(cross):
            a=2*math.pi*j/cross
            v=p+radius*(math.cos(a)*side+math.sin(a)*radial)
            vertices.append(tuple(v*MM))
    for i in range(len(path)-1):
        for j in range(cross):
            a=i*cross+j
            b=i*cross+(j+1)%cross
            faces.append((a,b,b+cross,a+cross))
    faces += [tuple(range(cross-1,-1,-1)),
              tuple((len(path)-1)*cross+j for j in range(cross))]
    obj=mesh_object("Shackle_forged_closed",vertices,faces,target,mat)
    for face in obj.data.polygons:
        face.use_smooth=True
    obj["section_diameter_mm"]=12.4
    return obj


def rivet(name,x,z,side,radius,height,target,mat,phase):
    # Расклёпанные головки с небольшим отклонением окружности, без текстурного шума.
    profile=[(0,0),(0.83,0),(1,0.12),(1.025,0.30),(0.94,0.66),(0.65,0.91),(0,1)]
    vertices,faces=[],[]
    count=48
    mount=11.15+0.38*(1-min(1,(x/42)**2+((z-35)/40)**2))
    for radius_factor,h in profile:
        for j in range(count):
            a=2*math.pi*j/count
            rr=radius*radius_factor*(1+0.018*math.cos(3*a+phase)+0.012*math.sin(5*a-phase))
            vertices.append(((x+rr*math.cos(a))*MM,
                             side*(mount+h*height)*MM,
                             (z+rr*math.sin(a))*MM))
    for ring in range(len(profile)-1):
        for j in range(count):
            faces.append((ring*count+j,ring*count+(j+1)%count,
                          (ring+1)*count+(j+1)%count,(ring+1)*count+j))
    obj=mesh_object(name,vertices,faces,target,mat)
    # У осевых колец схлопываем совпадающие вершины: головки остаются замкнутыми.
    bm=bmesh.new(); bm.from_mesh(obj.data)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=0.0000001)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
    bm.to_mesh(obj.data); bm.free()
    for face in obj.data.polygons:
        face.use_smooth=True
    return obj


def aim(obj, point):
    obj.rotation_euler=(Vector(point)-obj.location).to_track_quat("-Z","Y").to_euler()


def camera(name, location, point, ortho, studio):
    data=bpy.data.cameras.new(name)
    obj=bpy.data.objects.new(name,data)
    studio.objects.link(obj)
    obj.location=location
    aim(obj,point)
    data.type="ORTHO"
    data.ortho_scale=ortho
    data.lens=70
    data.clip_start=0.001
    data.clip_end=10
    CAMERAS[name]=obj
    return obj


def area(name, location, power, size, studio):
    data=bpy.data.lights.new(name,"AREA")
    data.energy=power
    data.shape="DISK"
    data.size=size
    obj=bpy.data.objects.new(name,data)
    studio.objects.link(obj)
    obj.location=location
    aim(obj,(0,0,0.057))


def build():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for old in list(bpy.data.collections):
        if old.name=="Collection":
            bpy.data.collections.remove(old)
    asset=collection("PADLOCK | geometry candidate")
    cutters=collection("Construction | editable cutters")
    studio=collection("Studio | review cameras")
    root=bpy.data.objects.new("Padlock_ROOT",None)
    asset.objects.link(root)
    root["status"]="Geometry candidate: owner review before UV / Painter"
    root["reference"]="Fab e727af62-9320-4f28-aa0e-1e796e4231cb; six owner screenshots"
    root["agreed_width_mm"]=80.0
    root["axes"]="X width; Y thickness (front -Y); Z height; metres"
    grey=material("Geometry_only_neutral_grey",0.24)
    dark=material("Geometry_only_recesses",0.18)
    profile=body_profile()
    front=cheek("Front_cheek_2p1mm",profile,-1,asset,grey)
    back=cheek("Rear_cheek_2p1mm",profile,1,asset,grey)
    key=prism("CUT_keyhole",key_profile(),-30,30,cutters,part=False)
    difference(front,key,"Настоящая замочная скважина")
    hole=cylinder("CUT_front_small_hole",1.65,60,(34.1,0,48.5),cutters,axis="Y")
    difference(front,hole,"Малое отверстие лицевой щеки")
    bevel(front,0.27,5)
    bevel(back,0.27,5)
    band=prism("Body_perimeter_band_2p4mm",scaled_profile(profile,0.961),-9.2,9.2,asset,grey)
    cavity=prism("CUT_inner_cavity",scaled_profile(profile,0.895),-20,20,cutters,part=False)
    difference(band,cavity,"Полость корпуса")
    for x in (-25,25):
        bore=cylinder(f"CUT_shackle_bore_{x:+}",6.6,38,(x,0,66),cutters)
        difference(band,bore,"Отверстие под дужку")
    bevel(band,0.28,4)
    shackle(asset,grey)
    post=cylinder("Visible_key_guide_post",2.1,17.7,(0.8,0.35,21.1),asset,dark,"Y",True)
    bevel(post,0.22,5)
    positions=[(-29.3,60.8,3.1),(-10.1,59.0,3.2),(29.4,64.8,3.1),
               (-21.2,10.4,2.65),(22.1,11.2,2.65)]
    for i,(x,z,r) in enumerate(positions,1):
        shaft=cylinder(f"Rivet_{i:02}_shaft",1.65,22.5,(x,0,z),asset,grey,"Y",True)
        rivet(f"Rivet_{i:02}_front_pressed",x,z,-1,r,0.65,asset,grey,i*1.7)
        rivet(f"Rivet_{i:02}_rear_peened",x,z,1,r*0.84,1.15,asset,grey,i*1.3)
    for i,(x,z,r) in enumerate(((16.0,33.6,2.4),(-1.2,17.3,2.7)),6):
        rivet(f"Rear_internal_pin_{i:02}_head",x,z,1,r,0.85,asset,grey,i*1.7)
        cylinder(f"Rear_internal_pin_{i:02}_seat",1.5,2.5,(x,10.0,z),asset,grey,"Y",True)
    for obj in PARTS:
        obj.parent=root
        obj["stage"]="untextured_geometry"
    for obj in cutters.objects:
        obj.parent=root
    scene=bpy.context.scene
    scene.unit_settings.system="METRIC"
    scene.unit_settings.scale_length=1
    scene.unit_settings.length_unit="MILLIMETERS"
    scene.render.engine="CYCLES"
    scene.cycles.samples=32
    scene.cycles.use_denoising=True
    scene.render.resolution_x=1000
    scene.render.resolution_y=1000
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG"
    scene.view_settings.view_transform="AgX"
    world=bpy.data.worlds.new("Neutral_studio")
    world.use_nodes=True
    bg=next(n for n in world.node_tree.nodes if n.type=="BACKGROUND")
    bg.inputs["Color"].default_value=(0.20,0.20,0.20,1)
    bg.inputs["Strength"].default_value=0.4
    scene.world=world
    floor=mesh_object("Studio_ground",[(-2,-2,-0.0004),(2,-2,-0.0004),(2,2,-0.0004),(-2,2,-0.0004)],[(0,1,2,3)],studio,material("Studio_ground_grey",0.085),False)
    area("Large_key",(-0.18,-0.22,0.30),7.0,0.19,studio)
    area("Broad_fill",(0.22,-0.10,0.14),3.4,0.18,studio)
    area("Rear_rim",(0.06,0.20,0.23),6.2,0.16,studio)
    area("Rear_fill",(-0.19,0.15,0.09),2.6,0.16,studio)
    target=(0,0,0.0595)
    camera("front_34",(-0.145,-0.38,0.16),target,0.151,studio)
    camera("rear_34",(0.16,0.38,0.16),target,0.151,studio)
    camera("front",(0,-0.4,0.0595),target,0.148,studio)
    camera("side",(-0.4,-0.045,0.105),target,0.151,studio)
    camera("top_joint",(-0.12,-0.24,0.22),(0,0,0.064),0.104,studio)
    camera("keyhole_close",(-0.065,-0.23,0.06),(0.002,0,0.022),0.067,studio)
    scene.camera=CAMERAS["front_34"]
    for area_ui in (area for screen in bpy.data.screens for area in screen.areas):
        if area_ui.type=="VIEW_3D":
            area_ui.spaces.active.region_3d.view_distance=0.20
            area_ui.spaces.active.region_3d.view_location=(0,0,0.060)
            area_ui.spaces.active.clip_start=0.001
            area_ui.spaces.active.overlay.show_floor=False
            area_ui.spaces.active.overlay.show_axis_x=False
            area_ui.spaces.active.overlay.show_axis_y=False
            area_ui.spaces.active.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
            area_ui.spaces.active.shading.color_type="MATERIAL"
    bpy.ops.object.select_all(action="DESELECT")
    root.select_set(True)
    bpy.context.view_layer.objects.active=root
    for image_path in sorted((WORK/"references").glob("*.png")):
        img=bpy.data.images.load(str(image_path),check_existing=True)
        img.use_fake_user=True
        img.pack()
        img.filepath="//../references/"+image_path.name
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/"models"/"padlock_v01_geometry.blend"),relative_remap=False)


def audit():
    deps=bpy.context.evaluated_depsgraph_get()
    objects=[o for o in bpy.data.objects if o.get("stage")=="untextured_geometry"]
    points=[]; report=[]
    for obj in objects:
        evaluated=obj.evaluated_get(deps)
        mesh=evaluated.to_mesh()
        bm=bmesh.new(); bm.from_mesh(mesh)
        points.extend(evaluated.matrix_world@v.co for v in mesh.vertices)
        report.append({"name":obj.name,"vertices":len(mesh.vertices),
                       "triangles":sum(max(0,len(p.vertices)-2) for p in mesh.polygons),
                       "boundary_edges":sum(e.is_boundary for e in bm.edges),
                       "nonmanifold_edges":sum(not e.is_manifold for e in bm.edges),
                       "volume_mm3":round(abs(bm.calc_volume())/MM**3,3)})
        bm.free(); evaluated.to_mesh_clear()
    bounds={axis:round((max(p[i] for p in points)-min(p[i] for p in points))/MM,3) for i,axis in enumerate(("width_mm","depth_mm","height_mm"))}
    front=bpy.data.objects.get("Front_cheek_2p1mm")
    holes={}
    for name,(x,z) in {"keyhole_neck":(0.8,10),"keyhole_round":(3.5,22),"small_hole":(34.1,48.5)}.items():
        hit,*_=front.evaluated_get(deps).ray_cast(Vector((x*MM,-0.040,z*MM)),Vector((0,1,0)),distance=0.031)
        holes[name+"_open_through_front_plate"]=not hit
    result={"file":bpy.data.filepath,"bounds":bounds,"objects":len(report),"parts":report,"hole_checks":holes,
            "limitations":["Geometry candidate; no production UV, maps, Painter project or game export.","80 mm body width approved by owner; thickness and secondary dimensions estimated from views.","Hidden working lock mechanism not reconstructed."]}
    (WORK/"checks"/"geometry_audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print("PADLOCK_AUDIT "+json.dumps({"bounds":bounds,"objects":len(report),"nonmanifold":sum(p["nonmanifold_edges"] for p in report),"holes":holes}))
    if abs(bounds["width_mm"]-80)>0.5 or not all(holes.values()) or any(p["nonmanifold_edges"] for p in report):
        raise RuntimeError("Geometry audit failed; inspect the report")


def main():
    import sys
    parser=argparse.ArgumentParser()
    parser.add_argument("mode",choices=("build","review"))
    parser.add_argument("--views",default="front_34,rear_34,front,side,top_joint,keyhole_close")
    parser.add_argument("--size",type=int,default=1000)
    args=parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    for folder in ("models","references","previews","checks"):
        (WORK/folder).mkdir(parents=True,exist_ok=True)
    if args.mode=="build":
        build()
    else:
        bpy.ops.wm.open_mainfile(filepath=str(WORK/"models"/"padlock_v01_geometry.blend"))
    audit()
    if args.mode=="review":
        scene=bpy.context.scene
        scene.render.resolution_x=scene.render.resolution_y=args.size
        for name in args.views.split(","):
            scene.camera=bpy.data.objects[name]
            scene.render.filepath=str(WORK/"previews"/(name+".png"))
            bpy.ops.render.render(write_still=True)
            print("PADLOCK_RENDER "+name,flush=True)


if __name__=="__main__":
    main()
