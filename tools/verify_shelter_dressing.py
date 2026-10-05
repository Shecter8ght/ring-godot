"""Повторно открыть Blender-исходники, проверить размеры и сохранить удобный вид библиотеки."""
import bpy, sys, json, hashlib
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,r'C:/Users/Schecter_8ght/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org')
bpy.ops.preferences.addon_enable(module='ucupaint')
source=ROOT/'_asset_src/shelter/dressing/shelter_dressing.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
manifest=json.loads((ROOT/'assets/shelter/dressing/manifest.json').read_text(encoding='utf-8'))
audit={};deps=bpy.context.evaluated_depsgraph_get()
for name,info in manifest.items():
    obj=bpy.data.objects[name];evaluated=obj.evaluated_get(deps);mesh=evaluated.to_mesh()
    coords=[evaluated.matrix_world@v.co for v in mesh.vertices]
    dims=[max(v[i] for v in coords)-min(v[i] for v in coords) for i in (0,2,1)]
    evaluated.to_mesh_clear()
    assert max(abs(a-b) for a,b in zip(dims,info['bounds_m']))<.001,name
    nodes=[n for n in obj.active_material.node_tree.nodes if n.type=='GROUP' and n.node_tree.yp.is_ypaint_node]
    assert len(nodes)==1 and len(nodes[0].node_tree.yp.layers)==4,name
    assert all(layer.type=='IMAGE' for layer in nodes[0].node_tree.yp.layers),name
    collection=bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if collection.name not in bpy.context.scene.collection.children:bpy.context.scene.collection.children.link(collection)
    if obj.name not in collection.objects:collection.objects.link(obj)
    for old in list(obj.users_collection):
        if old!=collection:old.objects.unlink(obj)
    obj.hide_set(name!='TeaSet');obj.hide_render=name!='TeaSet'
    audit[name]={'evaluated_bounds_m':[round(v,4) for v in dims],'uv':len(obj.data.uv_layers),'ucupaint_image_layers':4}
obj=bpy.data.objects['TeaSet'];bpy.context.view_layer.objects.active=obj
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=1.05
        area.spaces.active.region_3d.view_location=Vector((.15,0,.12))
bpy.ops.wm.save_as_mainfile(filepath=str(source))
report={'source':'_asset_src/shelter/dressing/shelter_dressing.blend','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'assets':audit,'verification':'fresh Blender process reopened saved candidate; evaluated world geometry including accessories','runtime_simulation':False}
(ROOT/'docs/shelter/validation/dressing_source_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'_asset_src/shelter/dressing/license.txt').write_text('Own RING meshes and painted layers, Blender / Ucupaint. Reuses existing CC0 Poly Haven photo textures: see assets/ASSET_CREDITS.md.\n',encoding='utf-8')
print('DRESSING_SOURCE_VERIFIED',len(audit),flush=True)

source=ROOT/'_asset_src/shelter/atmosphere/shelter_atmosphere.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
audit={}
for name in ('DustMotes','KettleVapor'):
    obj=bpy.data.objects[name]
    assert len(obj.data.shape_keys.key_blocks)==6,name
    assert obj.data.shape_keys.animation_data.action is not None,name
    nodes=[n for n in obj.active_material.node_tree.nodes if n.type=='GROUP' and n.node_tree.yp.is_ypaint_node]
    assert len(nodes)==1 and len(nodes[0].node_tree.yp.layers)==1,name
    assert nodes[0].node_tree.yp.layers[0].type=='IMAGE',name
    obj.hide_set(name!='KettleVapor');obj.hide_render=name!='KettleVapor'
    audit[name]={'vertices':len(obj.data.vertices),'shape_poses':5,'ucupaint_image_layers':1,'animation_action':obj.data.shape_keys.animation_data.action.name}
obj=bpy.data.objects['KettleVapor'];bpy.context.view_layer.objects.active=obj
bpy.ops.object.select_all(action='DESELECT');obj.select_set(True)
bpy.context.scene.frame_set(1)
for area in bpy.context.screen.areas:
    if area.type=='VIEW_3D':
        area.spaces.active.region_3d.view_distance=.8
        area.spaces.active.region_3d.view_location=Vector((0,0,.15))
bpy.ops.wm.save_as_mainfile(filepath=str(source))
report={'source':'_asset_src/shelter/atmosphere/shelter_atmosphere.blend','sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'assets':audit,'verification':'fresh Blender process reopened saved candidate; editable painted layers and shape-key animation actions','runtime_simulation':False}
(ROOT/'docs/shelter/validation/atmosphere_source_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('ATMOSPHERE_SOURCE_VERIFIED',len(audit),flush=True)
