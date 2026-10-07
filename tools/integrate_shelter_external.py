"""Blender integration: метры, ground pivot, применённый scale, PBR, decimation, GLB."""
import bpy, json
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'assets/shelter/models'
records = json.loads((ROOT / '_asset_src/shelter/external_sources.json').read_text(encoding='utf-8'))
manifest = json.loads((OUT / 'manifest.json').read_text(encoding='utf-8'))
for info in records:
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    folder = ROOT / '_asset_src/shelter/external' / info['id']
    bpy.ops.import_scene.gltf(filepath=str(folder / (info['id'] + '.gltf')))
    objects = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if info['asset'] == 'PH_Crate': objects = [o for o in objects if o.name.endswith('_a')]
    bounds = [o.matrix_world @ Vector(v) for o in objects for v in o.bound_box]
    lo = Vector([min(v[i] for v in bounds) for i in range(3)])
    hi = Vector([max(v[i] for v in bounds) for i in range(3)])
    size = hi-lo
    scale = {'PH_Sofa': 2.25/size.x, 'PH_Armchair': .92/size.x,
             'PH_Crate': .92/max(size.x,size.y), 'PH_Barrel': .9/size.z, 'PH_AmmoBox': .48/max(size.x,size.y)}[info['asset']]
    offset = Vector(((lo.x+hi.x)*.5, (lo.y+hi.y)*.5, lo.z))
    for o in objects:
        o.data = o.data.copy()
        matrix = o.matrix_world.copy(); o.parent = None; o.matrix_world = matrix
        for v in o.data.vertices: v.co = (matrix @ v.co-offset)*scale
        o.matrix_world.identity()
        bpy.context.view_layer.objects.active = o
        triangles = sum(len(p.vertices)-2 for p in o.data.polygons)
        if triangles > 9000:
            mod = o.modifiers.new('Interior triangle budget', 'DECIMATE'); mod.ratio = 9000/triangles
            bpy.ops.object.modifier_apply(modifier=mod.name)
    for o in list(bpy.context.scene.objects):
        if o not in objects: bpy.data.objects.remove(o, do_unlink=True)
    size *= scale
    bpy.ops.object.select_all(action='SELECT')
    bpy.context.scene.unit_settings.system = 'METRIC'
    bpy.ops.wm.save_as_mainfile(filepath=str(folder / 'integrated.blend'))
    bpy.ops.export_scene.gltf(filepath=str(OUT / (info['asset']+'.glb')), export_format='GLB',
                              use_selection=True, export_yup=True, export_animations=False)
    tris = sum(len(p.vertices)-2 for o in objects for p in o.data.polygons)
    manifest[info['asset']] = {'external': True, 'triangles': tris,
          'bounds_m': [round(size.x,4), round(size.z,4), round(size.y,4)],
          'collisions': [{'pos':[0,size.z*.5,0], 'size':[size.x,size.z,size.y], 'yaw':0}]}
    print('INTEGRATED', info['asset'], manifest[info['asset']], flush=True)
(OUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
