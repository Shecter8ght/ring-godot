"""Read-only reopen verification of the working100 high-poly, no game conversion."""
import bpy,hashlib,pathlib,json
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
h=hashlib.sha256();count=mods=0
for o in sorted(bpy.data.objects,key=lambda o:o.name):
    if o.type!='MESH' or o.name.startswith('Review.'):continue
    count+=1;h.update(o.name.encode())
    for v in o.data.vertices:h.update(repr(tuple(v.co)).encode())
    for p in o.data.polygons:h.update(repr(tuple(p.vertices)).encode())
    h.update(repr(tuple(tuple(r) for r in o.matrix_local)).encode())
    for m in o.modifiers:mods+=1;h.update((m.name+m.type).encode())
snapshot={'sha256':h.hexdigest(),'objects':count,'modifiers':mods}
baseline=json.loads((OUT/'checks/factory-reopen.json').read_text(encoding='utf-8'))['snapshot']
assert baseline==snapshot,(baseline,snapshot)
images=[]
for m in bpy.data.materials:
    if 'Painter working100' not in m.name:continue
    bs=next(n for n in m.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    assert all(bs.inputs[s].is_linked for s in ['Base Color','Metallic','Roughness','Normal'])
    for n in m.node_tree.nodes:
        if n.type=='TEX_IMAGE':
            assert n.image.packed_file
            images.append({'material':m.name,'image':n.image.name,'size':list(n.image.size),'colorspace':n.image.colorspace_settings.name})
assert len(images)==15
assert not any(o.type=='FONT' for o in bpy.data.objects)
assert bpy.context.scene.world.node_tree.nodes.get('Environment Texture').image.packed_file
(OUT/'checks/working100-reopen.json').write_text(json.dumps({'status':'PASS','snapshot':snapshot,'geometry_modifiers_transforms_unchanged':True,'packed_texture_nodes':images,'font_geometry_count':0,'game_export':False},ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS working100: source geometry unchanged; 15 packed map nodes, packed studio; no FONT')
