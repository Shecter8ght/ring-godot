"""Независимый контроль сохранённой выемки, посадки затыльника и сетки."""
from pathlib import Path
import hashlib,json,sys
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_stock_v3'

def lookup(obj):
    mesh=obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh()
    verts=[obj.matrix_world @ v.co for v in mesh.vertices]
    tree=BVHTree.FromPolygons(verts,[p.vertices[:] for p in mesh.polygons])
    bm=bmesh.new();bm.from_mesh(mesh)
    topology={'boundary':sum(e.is_boundary for e in bm.edges),'overfull':sum(len(e.link_faces)>2 for e in bm.edges),
        'wire':sum(e.is_wire for e in bm.edges),'loose':sum(not v.link_edges for v in bm.verts),
        'zero_area':sum(f.calc_area()<1e-16 for f in bm.faces)}
    bm.free();obj.evaluated_get(bpy.context.evaluated_depsgraph_get()).to_mesh_clear()
    return tree,topology

def main():
    source=ROOT/'_asset_src/vss_picatinny/VSS_Vintorez_Picatinny_v3.blend'
    (RAW/'shoulder-audit.json').write_text(json.dumps({'status':'RUNNING'}),encoding='utf8')
    bpy.ops.wm.open_mainfile(filepath=str(source))
    wood,wood_topology=lookup(bpy.data.objects['Wood_stock_with_integral_grip'])
    pad,pad_topology=lookup(bpy.data.objects['Ventilated_rubber_butt_pad'])
    assert not any(wood_topology.values()) and not any(pad_topology.values())
    profile=[]
    for z in (-.025,-.035,-.05,-.0675,-.085,-.10,-.11):
        origin=Vector((-.05,0,z));direction=Vector((1,0,0))
        p=pad.ray_cast(origin,direction);w=wood.ray_cast(origin,direction)
        front=pad.ray_cast(Vector((.055,0,z)),Vector((-1,0,0)))
        assert p[0] and w[0] and front[0]
        gap=(w[0].x-front[0].x)*1000
        assert -.00025<gap/1000<.00025,('seat_gap',z,gap)
        profile.append({'z_mm':z*1000,'rubber_back_x_mm':p[0].x*1000,'wood_seat_x_mm':w[0].x*1000,'seat_gap_mm':gap})
    center=profile[3]['rubber_back_x_mm']
    edge=(profile[0]['rubber_back_x_mm']+profile[-1]['rubber_back_x_mm'])/2
    assert center-edge>5,'No shoulder concavity'
    transverse=[]
    for y in (-.0175,-.008,0,.008,.0175):
        for z in (-.035,-.0675,-.1):
            w=wood.ray_cast(Vector((-.05,y,z)),Vector((1,0,0)))
            front=pad.ray_cast(Vector((.055,y,z)),Vector((-1,0,0)))
            assert w[0] and front[0]
            gap=(w[0].x-front[0].x)*1000
            assert abs(gap)<.25,('transverse_fit',y,z,gap)
            transverse.append({'y_mm':y*1000,'z_mm':z*1000,'seat_gap_mm':gap})
    openings=[]
    for x,z in ((.09,-.06),(.12,-.06),(.145,-.07),(.09,-.085),(.13,-.085),
                (.23,-.06),(.265,-.06),(.275,-.08),(.24,-.085)):
        clear=wood.ray_cast(Vector((x,-.09,z)),Vector((0,1,0)))[0] is None
        assert clear,('Blocked stock window',x,z)
        openings.append({'x_mm':x*1000,'z_mm':z*1000,'clear':True})
    pins=[]
    for name in ('Wood_pin_-1_28','Wood_pin_1_28'):
        point=bpy.data.objects[name].matrix_world.translation;sign=-1 if point.y<0 else 1
        hit=wood.ray_cast(Vector((point.x,sign*.06,point.z)),Vector((0,-sign,0)))
        assert hit[0] and abs(abs(point.y)-abs(hit[0].y))<.0005,('Floating pin',name)
        pins.append({'part':name,'seated':True})
    B.COLLECTIONS.clear();B.COLLECTIONS.update({c.name:c for c in bpy.data.collections})
    result={'status':'PASS','reopened':True,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'wood_topology':wood_topology,'pad_topology':pad_topology,'transverse_fit':transverse,
        'profile':profile,'concavity_from_sample_chord_mm':center-edge,'stock_openings':openings,'pins':pins,
        'bounds':B.report_bounds('VSS_Assembly')}
    (RAW/'shoulder-audit.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    # Нейтральный материал показывает саму кривизну и стык без влияния текстуры дерева.
    clay=B.material('Shoulder shape inspection',(.16,.18,.20),0,.48)
    bpy.context.view_layer.material_override=clay
    B.render_views(RAW,'clay',[('profile','Camera_Shoulder_Profile',1150,1000),('rear','Camera_Shoulder_Rear',1150,1000)])
    print('VSS_SHOULDER_AUDIT_PASS',json.dumps(result),flush=True)

if __name__=='__main__':main()
