"""Read-only reopen verification of the Painter preview against accepted v02 geometry."""
import bpy,hashlib,pathlib,json
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
def geometry():
    h=hashlib.sha256();count=0;mods=0
    for o in sorted(bpy.data.objects,key=lambda o:o.name):
        if o.type!='MESH' or o.name.startswith('Review.'):continue
        count+=1;h.update(o.name.encode())
        for v in o.data.vertices:h.update(repr(tuple(v.co)).encode())
        for p in o.data.polygons:h.update(repr(tuple(p.vertices)).encode())
        h.update(repr(tuple(tuple(r) for r in o.matrix_local)).encode())
        for m in o.modifiers:
            mods+=1;h.update((m.name+m.type).encode())
    return {'sha256':h.hexdigest(),'objects':count,'modifiers':mods}
assert pathlib.Path(bpy.data.filepath).name=='DOZOR_Factory_Painter_v01.blend'
current=geometry()
images=[]
for m in bpy.data.materials:
    if 'Painter factory' not in m.name:continue
    p=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    assert all(p.inputs[s].is_linked for s in ['Base Color','Metallic','Roughness','Normal'])
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE':
            assert n.image.packed_file is not None
            images.append({'material':m.name,'image':n.image.name,'size':list(n.image.size),'space':n.image.colorspace_settings.name})
assert len(images)==15,len(images)
assert not any(o.type=='FONT' for o in bpy.data.objects)
assert bpy.context.scene.world.node_tree.nodes.get('Environment Texture').image.packed_file
bpy.ops.wm.open_mainfile(filepath=str(OUT/'models/DOZOR_Family_form_v02.blend'),load_ui=False)
source=geometry()
assert source==current,(source,current)
report={'status':'PASS','accepted_source':'DOZOR_Family_form_v02.blend','geometry_unchanged':True,
        'snapshot':current,'packed_texture_nodes':images,'native_painter_project_exists':(OUT/'painter/DOZOR_factory_v01.spp').exists(),
        'font_geometry_count':0,'production_game_mesh':False,'factory_finish_accepted':False}
(OUT/'checks/factory-reopen.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS factory preview reopened: 15 packed texture nodes, packed HDRI, geometry/modifiers/transforms unchanged; no FONT.')
