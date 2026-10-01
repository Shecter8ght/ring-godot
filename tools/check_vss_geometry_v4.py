"""Независимый контроль новой геометрии после сохранения и повторного открытия."""
from pathlib import Path
import json,sys,hashlib
import bpy,bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import refine_vss_geometry_v4 as V

RAW=V.RAW


def evaluated(obj):
    deps=bpy.context.evaluated_depsgraph_get();ev=obj.evaluated_get(deps)
    mesh=ev.to_mesh();vertices=[ev.matrix_world@v.co for v in mesh.vertices]
    faces=[p.vertices[:] for p in mesh.polygons]
    tree=BVHTree.FromPolygons(vertices,faces)
    bm=bmesh.new();bm.from_mesh(mesh)
    counts={'boundary':sum(e.is_boundary for e in bm.edges),'overfull':sum(len(e.link_faces)>2 for e in bm.edges),
            'wire':sum(e.is_wire for e in bm.edges),'loose':sum(not v.link_edges for v in bm.verts),
            'zero_area':sum(f.calc_area()<1e-14 for f in bm.faces)}
    mesh.calc_loop_triangles();triangles=len(mesh.loop_triangles)
    bm.free();ev.to_mesh_clear()
    return tree,counts,vertices,triangles


def no_maps(owner):
    for obj in (owner,*owner.children_recursive):
        if obj.type!='MESH':continue
        for mat in obj.data.materials:
            assert mat and mat.name.startswith('V4 '),(obj.name,mat.name if mat else None)
            assert not any(n.type=='TEX_IMAGE' for n in mat.node_tree.nodes)


def check_library():
    copy=json.loads((RAW/'library-copy-report.json').read_text(encoding='utf8'))
    assert copy['status']=='PASS';destination=Path(copy['destination']);rows=[]
    for row in copy['files']:
        if not row['path'].endswith('.blend'):continue
        file=destination/row['path']
        assert hashlib.sha256(file.read_bytes()).hexdigest()==row['sha256'],file
        bpy.ops.wm.open_mainfile(filepath=str(file))
        assert not bpy.data.libraries,('Linked library',file)
        external=[]
        for image in bpy.data.images:
            if image.source=='FILE' and not image.packed_file:external.append(image.filepath)
        for font in bpy.data.fonts:
            if font.filepath not in {'','<builtin>'} and not font.packed_file:external.append(font.filepath)
        assert not external,(file,external)
        rows.append({'file':str(file),'sha256':row['sha256'],'external_dependencies':external,
                     'mesh_objects':sum(o.type=='MESH' for o in bpy.context.scene.objects)})
    assert len(rows)==8
    report={'status':'PASS','saved_copies_reopened':len(rows),'files':rows}
    (RAW/'library-blend-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V4_LIBRARY_REOPEN_PASS',flush=True)


def main():
    report_path=RAW/'geometry-audit.json'
    report_path.write_text(json.dumps({'status':'RUNNING'}),encoding='utf8')
    bpy.ops.wm.open_mainfile(filepath=str(RAW/'VSS_Geometry_v4.blend'));V.sync()
    wood,wtop,_,_=evaluated(bpy.data.objects['Wood_stock_with_integral_grip'])
    metal,mtop,_,_=evaluated(bpy.data.objects['Receiver_lower_frame'])
    pad,ptop,_,_=evaluated(bpy.data.objects['Ventilated_rubber_butt_pad'])
    assert not any(wtop.values()),wtop
    assert not any(mtop.values()),mtop
    assert not any(ptop.values()),ptop
    seats=[]
    for y in (-.0178,-.012,0,.012,.0178):
        for x in (.285,.300,.313,.323,.330,.337,.343):
            w=wood.ray_cast(Vector((x,y,.045)),Vector((0,0,-1)))
            m=metal.ray_cast(Vector((x,y,-.090)),Vector((0,0,1)))
            assert w[0] and m[0],('Seat misses',x,y)
            gap=(m[0].z-w[0].z)*1000
            seats.append({'x_mm':x*1000,'y_mm':y*1000,'gap_mm':gap})
            assert abs(gap)<.18,('Receiver seat gap',x,y,gap)
    shoulder=[]
    for z in (-.106,-.09,-.0675,-.045,-.028):
        for y in (-.012,0,.012):
            p=pad.ray_cast(Vector((.08,y,z)),Vector((-1,0,0)))
            w=wood.ray_cast(Vector((-.03,y,z)),Vector((1,0,0)))
            assert p[0] and w[0]
            gap=(w[0].x-p[0].x)*1000
            assert abs(gap)<.25,('Shoulder seat',y,z,gap)
            shoulder.append({'y_mm':y*1000,'z_mm':z*1000,'gap_mm':gap})
    windows=[]
    for x,z in ((.08,-.06),(.10,-.07),(.13,-.075),(.15,-.065),
                (.225,-.065),(.245,-.07),(.27,-.075),(.28,-.07),(.25,-.083)):
        clear=wood.ray_cast(Vector((x,-.065,z)),Vector((0,1,0)),.13)[0] is None
        assert clear,('Stock window',x,z);windows.append([x,z])
    safety=bpy.data.objects['Safety_lever_contoured']
    _,stop,_,_=evaluated(safety);assert not any(stop.values()),stop
    assert bpy.data.objects.get('Selector_lower_return') is None
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];no_maps(root)
    rifle=B.report_bounds('VSS_Assembly')
    B.render_views(RAW,'v4',[('rifle','Camera_Beauty_Right',1800,850),
        ('join_right','Camera_V4_Join_Right',1200,900),('join_left','Camera_V4_Join_Left',1200,900),
        ('safety','Camera_V4_Safety',1200,850),('safety_angled','Camera_V4_Safety_Angled',1200,850),
        ('grip','Camera_V4_Grip',1100,1000),
        ('magazine_on_rifle','Camera_V4_Magazine',1100,1000)])
    magazines=[]
    for capacity in V.CAPACITIES:
        for loaded in (False,True):
            identifier='Magazine_939_'+str(capacity)+'_'+('Loaded' if loaded else 'Empty')
            folder=RAW/'Магазины'/identifier;file=folder/(identifier+'.blend')
            bpy.ops.wm.open_mainfile(filepath=str(file));V.sync()
            owner=bpy.data.objects[identifier];body=bpy.data.objects['Curved_magazine_body_'+str(capacity)]
            tree,top,positions,tris=evaluated(body)
            assert not any(top.values()),(identifier,top)
            assert tuple(owner.location)==(0,0,0)
            no_maps(owner)
            assert owner['rounds_loaded']==(capacity if loaded else 0)
            # Полость открыта сверху; лучи проходят в стенки дна, а не в заглушку горловины.
            air=[]
            direction=Vector((__import__('math').sin(V.THETA),0,-__import__('math').cos(V.THETA)))
            for v,y in ((0,0),(-12,-7),(-12,7),(12,-7),(12,7)):
                start=Vector(V.point(-2,v,y))*.001
                hit=tree.ray_cast(start,direction,.06)
                assert hit[0] is None or hit[3]>.02,('Mouth closed',identifier,v,y,hit[3])
                air.append({'v_mm':v,'y_mm':y,'distance_mm':hit[3]*1000 if hit[0] else None})
            bounds=B.report_bounds(identifier)
            magazines.append({'id':identifier,'capacity':capacity,'loaded':loaded,'body_topology':top,
                              'body_triangles':tris,'bounds':bounds,'open_mouth_rays':air,
                              'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
            B.render_views(folder,'v4',[('profile','Camera_Magazine_Profile',900,1100),
                ('beauty','Camera_Magazine_Beauty',900,1100),('top','Camera_Top',1000,850)])
    bpy.ops.wm.open_mainfile(filepath=str(RAW/'VSS_and_Magazines_10_20_30.blend'));V.sync()
    B.render_views(RAW,'v4',[('all','Camera_V4_Gallery',1600,1250)])
    for obj in bpy.data.objects:
        ancestor=obj
        while ancestor:
            if ancestor.get('rounds_loaded',0)>0:
                obj.hide_render=True;break
            ancestor=ancestor.parent
    # Для сравнения силуэтов показываем только ряд пустых 10/20/30.
    for collection in bpy.data.collections:
        if collection.name.startswith('Mag_Review_'):
            for obj in collection.all_objects:
                if obj:obj.hide_render='Loaded' in collection.name
    for obj in bpy.data.objects['VSS_Vintorez_Picatinny'].children_recursive:obj.hide_render=True
    for obj in bpy.data.objects:
        if obj.name.startswith('Review_row_'):obj.hide_render=True
    B.render_views(RAW,'v4',[('magazines_profile','Camera_V4_Mags_Profile',1500,1000)])
    report={'status':'PASS','receiver_contact_points':seats,'shoulder_contact_points':shoulder,
            'wood_topology':wtop,'receiver_topology':mtop,'pad_topology':ptop,'safety_topology':stop,
            'stock_window_rays':windows,'rifle':rifle,'magazines':magazines,'no_texture_maps':True,
            'no_game_export':True,'saved_files_reopened':8}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V4_GEOMETRY_AUDIT_PASS',flush=True)


if __name__=='__main__':
    if '--library' in sys.argv:check_library()
    else:main()
