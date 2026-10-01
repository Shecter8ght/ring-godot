"""Открытый продольный канал глушителя в художественном ассете ВСС."""
from pathlib import Path
import hashlib,json,sys
import bpy

sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import refine_vss_geometry_v4 as V
import refine_vss_shoulder_stock as S

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'_asset_src/vss_bore_v6'
SOURCE=RAW/'Live_Source.blend'
FILE=RAW/'VSS_Bore_v6.blend'
DETACHED=RAW/'Suppressor_Through_Bore.blend'


def main():
    RAW.mkdir(parents=True,exist_ok=True)
    source_digest=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE));V.sync()
    root=bpy.data.objects['VSS_Vintorez_Picatinny']
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update();before=S.snapshot(root)
    changed={'Suppressor_front_recess','Tapered_polymer_handguard'}
    V.remove(bpy.data.objects['Suppressor_front_recess'])
    owner=bpy.data.objects['Suppressor']
    tube=B.lathe('Suppressor_barrel_through_tube',
                 [(557.8,6.2),(888.8,6.2),(889,6.0),(889,5.15),
                  (888.8,5),(558,5),(557.8,5.2)],
                 'V4 steel','03_Front',parent=owner)
    for face in tube.data.polygons:face.use_smooth=abs(face.normal.x)<.98
    # При соединении оболочек внутренний канал не перекрывается торцом цевья.
    handguard=bpy.data.objects['Tapered_polymer_handguard']
    cut=B.cylinder('Handguard_passage_tool',(559,0,10),5.1,6,
                   'V4 recess','03_Front',axis='X',edge=0)
    B.difference(handguard,cut)
    tube['asset_role']='continuous open-ended visual barrel liner inside suppressor'
    tube['source_shape']='coaxial with the existing muzzle opening; visually estimated wall'
    owner['bore_role']='open longitudinal channel; no internal operating mechanism'
    after=S.snapshot(root);unchanged=[]
    for name,data in before.items():
        if name in changed:continue
        assert data==after[name],('Unrelated geometry changed',name)
        unchanged.append(name)
    for name,location,target,scale in (
        ('Camera_V6_Muzzle',(.94,-.012,.023),(.887,0,.010),.055),
        ('Camera_V6_Front_Through',(.960,0,.010),(.725,0,.010),.052),
        ('Camera_V6_Rear_Through',(.500,0,.010),(.725,0,.010),.056),
        ('Camera_V6_Suppressor',(.970,-.40,.14),(.725,0,.010),.385)):
        B.camera(name,location,target,scale)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera_V6_Muzzle']
    scene.render.resolution_x=1100;scene.render.resolution_y=1000
    V.configure_view(root,'Camera_V6_Muzzle');B.save_scene(FILE)
    keep={owner,*owner.children_recursive}
    world=owner.matrix_world.copy();owner.parent=None;owner.matrix_world=world
    for obj in list(bpy.data.objects):
        if obj in keep or obj.type in {'CAMERA','LIGHT'}:continue
        V.remove(obj)
    bpy.context.view_layer.update();V.configure_view(owner,'Camera_V6_Front_Through')
    scene.camera=bpy.data.objects['Camera_V6_Front_Through'];B.save_scene(DETACHED)
    report={'status':'BUILT','source_sha256':source_digest,
            'source_unchanged':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_digest,
            'changed_names':sorted(changed),'new_names':[tube.name],
            'unchanged_mesh_parts':len(unchanged),'unchanged_names':unchanged,
            'new_texture_maps':False,'game_exports':False}
    (RAW/'build-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('VSS_V6_BORE_BUILT',flush=True)


if __name__=='__main__':main()
