"""Check source preservation, the LP bore clearance and complete exported triangle counts."""
import bpy,bmesh,pathlib,json,hashlib,sys,math
import numpy as np
from mathutils import Matrix,Vector
sys.path.insert(0,str(pathlib.Path(__file__).parent))
from game_common import *
spec=json.loads((ASSET/'finish-spec.json').read_text(encoding='utf-8'))
for file,expected in [(SOURCE,spec['wear']['model_sha256']),(ASSET/'painter/DOZOR_working100_v01.spp',spec['wear']['painter_sha256'])]:
    assert hashlib.sha256(file.read_bytes()).hexdigest()==expected
bpy.ops.wm.open_mainfile(filepath=str(WORK/'dozor_lp.blend'))
matrix=Matrix.Translation(Vector((0,-.064,.035)))@Matrix.Rotation(math.pi/2,4,'Y')
inverse=matrix.inverted();report={'source_bytes_preserved':True,'bore_clearance_mm':{},'export_triangles':{},'mesh_open_edges':{}}
for ob in bpy.data.objects:
    if ob.type!='MESH':continue
    bm=bmesh.new();bm.from_mesh(ob.data)
    bad=sum(not e.is_manifold for e in bm.edges)
    report['mesh_open_edges'][ob.name]=bad
    assert bad==0,(ob.name,bad)
    assert bm.calc_volume(signed=True)>0,(ob.name,'inward winding')
    assert not any(e.smooth and e.is_manifold and e.calc_face_angle()>math.radians(60)+1e-5 for e in bm.edges),(ob.name,'soft edge over 60 degrees')
    bm.free()
    if not ob.name.startswith(('LP__P.Ring.','LP__P.Liner.')):continue
    p=np.array([tuple(inverse@(ob.matrix_world@v.co)) for v in ob.data.vertices])
    radius=np.linalg.norm(p[:,:2],axis=1)
    inner=radius.min();values=[]
    for e in ob.data.edges:
        a,b=e.vertices
        if radius[a]>inner+.00002 or radius[b]>inner+.00002:continue
        # Closest point of the actual edge chord to the flashlight axis.
        q=p[a,:2];d=p[b,:2]-q;t=np.clip(-q.dot(d)/max(d.dot(d),1e-18),0,1)
        values.append(np.linalg.norm(q+t*d))
    r=min(values)
    assert r>.0127,(ob.name,r)
    report['bore_clearance_mm'][ob.name]=float((r-.0127)*1000)
for key in ['f1','f1m','f1s','p']:
    gltf=json.loads((OUT/('dozor_'+key+'.gltf')).read_text(encoding='utf-8'))
    assert gltf['asset']['extras']['ring_binary_sha256']==hashlib.sha256((OUT/gltf['buffers'][0]['uri']).read_bytes()).hexdigest()
    count=sum(gltf['accessors'][p['indices']]['count']//3 for m in gltf['meshes'] for p in m['primitives'])
    report['export_triangles'][key]=count
    for im in gltf.get('images',[]):assert (OUT/im['uri']).exists()
assert report['export_triangles']['f1']+report['export_triangles']['p']<=TRIANGLE_LIMIT
(WORK/'geometry-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS exported budget and closed LP meshes; bore minimum clearance mm',min(report['bore_clearance_mm'].values()),flush=True)
