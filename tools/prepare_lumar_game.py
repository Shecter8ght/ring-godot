"""ЛУМАР H1: отдельная игровая сетка, проекция материалов исходника 100 и GLB.
Вид в игре один при любой прочности (решение владельца 2026-10-19): карты 60 / 20 и трещины стекла удалены.

blender --background --factory-startup --python-exit-code 1 --python tools/prepare_lumar_game.py -- geometry|bake 100|export
Исходники библиотеки только читаются. Промежуточные файлы остаются в _asset_src.
"""
from pathlib import Path
import sys
import json
import math
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('E:/Models Blender/ВЕРАС-54 — модель и обвесы/ЛУМАР H1/Актуальное')
WORK = ROOT / '_asset_src/lumar_h1_game'
OUT = ROOT / 'assets/models/attachments/lumar_h1'
SOURCES = {100:'LUMAR_H1_State100_New_v9.blend'}
RES = 2048
WORK.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)

def activate(objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.hide_set(False)
        o.select_set(True)
    bpy.context.view_layer.objects.active = objects[-1]

def configure_imports():
    # Вызывать после первого --import Godot: 3D-карты с mipmaps и сжатием видеопамяти.
    for path in OUT.glob('*.png.import'):
        settings=path.read_text(encoding='utf-8')
        settings=settings.replace('compress/mode=0','compress/mode=2')
        settings=settings.replace('mipmaps/generate=false','mipmaps/generate=true')
        settings=settings.replace('detect_3d/compress_to=1','detect_3d/compress_to=0')
        if '_normal.png.import' in path.name:
            settings=settings.replace('compress/normal_map=0','compress/normal_map=1')
        path.write_text(settings,encoding='utf-8')
    print('LUMAR_IMPORT_SETTINGS_OK',flush=True)

def source_objects():
    return [o for o in bpy.data.objects if o.type in ('MESH','FONT') and not o.hide_render and o.name not in ('Sight_Lens','Sight_Reticle')]

def geometry():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/SOURCES[100]))
    dg=bpy.context.evaluated_depsgraph_get()
    pieces=[]
    for src in source_objects():
        # Буквы проецируются в цвет, геометрия надписей в игровую сетку не входит.
        if src.type == 'FONT':
            continue
        mesh=bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        low=bpy.data.objects.new('LP_'+src.name,mesh)
        bpy.context.collection.objects.link(low)
        low.matrix_world=src.matrix_world.copy()
        activate([low])
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        weld=low.modifiers.new('Restore evaluated seams','WELD')
        weld.merge_threshold=0.000001
        bpy.ops.object.modifier_apply(modifier=weld.name)
        mesh.calc_loop_triangles()
        count=len(mesh.loop_triangles)
        limit=2800 if src.name=='Sight_Body' else 550 if 'window gasket' in src.name else 320 if 'cap' in src.name else 160
        if count>limit:
            mod=low.modifiers.new('Game reduction','DECIMATE')
            mod.ratio=limit/count
            bpy.ops.object.modifier_apply(modifier=mod.name)
        low.data.materials.clear()
        pieces.append(low)
    activate(pieces)
    bpy.ops.object.join()
    body=bpy.context.object
    body.name='Body'
    while body.data.uv_layers:
        body.data.uv_layers.remove(body.data.uv_layers[0])
    body.data.uv_layers.new(name='GameUV')
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66),island_margin=0.004,area_weight=0.5)
    bpy.ops.object.mode_set(mode='OBJECT')
    # Источник и игровые оси: (X вперёд,Y влево,Z вверх) → (X влево,Y вверх,Z вперёд).
    xf=Matrix(((0,1,0,0),(0,0,1,0),(1,0,0,0),(0,0,0,1)))
    body['source_to_game']=[list(r) for r in xf]
    keep={body}
    for name in ('Sight_Lens','Sight_Reticle'):
        src=bpy.data.objects.get(name)
        mesh=bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        low=bpy.data.objects.new('Lens' if name=='Sight_Lens' else 'Reticle',mesh)
        bpy.context.collection.objects.link(low)
        low.matrix_world=src.matrix_world.copy()
        activate([low])
        bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
        if name=='Sight_Lens':
            mod=low.modifiers.new('Game glass','DECIMATE')
            mod.ratio=0.25
            bpy.ops.object.modifier_apply(modifier=mod.name)
        keep.add(low)
    for obj in list(bpy.data.objects):
        if obj not in keep:
            bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'low_source_axes.blend'))
    body.data.calc_loop_triangles()
    print('LUMAR_GEOMETRY_OK',len(body.data.loop_triangles))

def bake(state):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE/SOURCES[state]))
    high=source_objects()
    # Только геометрия из отдельного low-poly файла; исходный стек UCUPaint не меняется.
    with bpy.data.libraries.load(str(WORK/'low_source_axes.blend'),link=False) as (available,target):
        target.objects=['Body']
    body=target.objects[0]
    bpy.context.collection.objects.link(body)
    body.name='BakeTarget'
    mat=bpy.data.materials.new('BakeTargetMaterial')
    mat.use_nodes=True
    body.data.materials.clear()
    body.data.materials.append(mat)
    node=mat.node_tree.nodes.new('ShaderNodeTexImage')
    mat.node_tree.nodes.active=node
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.samples=1
    scene.render.bake.use_selected_to_active=True
    scene.render.bake.use_cage=False
    scene.render.bake.cage_extrusion=0.00065
    scene.render.bake.max_ray_distance=0.0013
    scene.render.bake.margin=12
    try:
        prefs=bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type='OPTIX'
        prefs.get_devices()
        for device in prefs.devices:
            device.use=device.type!='CPU'
        if any(d.use for d in prefs.devices):
            scene.cycles.device='GPU'
    except Exception as error:
        print('GPU_FALLBACK',error)
    # В каждом исходном материале сохраняем фактические входы Principled.
    original={}
    for obj in high:
        for material in obj.data.materials:
            if not material or material in original or not material.use_nodes:
                continue
            bsdf=next((n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)
            output=next((n for n in material.node_tree.nodes if n.type=='OUTPUT_MATERIAL'),None)
            if bsdf and output:
                original[material]=(bsdf,output)
    for channel,socket in [('base_color','Base Color'),('roughness','Roughness'),('metallic','Metallic'),('normal',None)]:
        for material,(bsdf,output) in original.items():
            tree=material.node_tree
            if socket:
                emission=tree.nodes.get('GameBakeEmission') or tree.nodes.new('ShaderNodeEmission')
                emission.name='GameBakeEmission'
                source=bsdf.inputs[socket]
                for link in list(emission.inputs['Color'].links):
                    tree.links.remove(link)
                if source.is_linked:
                    tree.links.new(source.links[0].from_socket,emission.inputs['Color'])
                else:
                    value=source.default_value
                    emission.inputs['Color'].default_value=value if hasattr(value,'__len__') else (value,value,value,1)
                tree.links.new(emission.outputs[0],output.inputs['Surface'])
            else:
                tree.links.new(bsdf.outputs[0],output.inputs['Surface'])
        image=bpy.data.images.new(f'lumar_{state}_{channel}',width=RES,height=RES,alpha=False)
        image.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
        node.image=image
        activate(high+[body])
        print('LUMAR_BAKE_START',state,channel,flush=True)
        bpy.ops.object.bake(type='NORMAL' if channel=='normal' else 'EMIT')
        image.filepath_raw=str(OUT/f'lumar_{state}_{channel}.png')
        image.file_format='PNG'
        image.save()
        print('LUMAR_BAKE_DONE',state,channel,flush=True)
    print('LUMAR_BAKE_OK',state,flush=True)

def export():
    bpy.ops.wm.open_mainfile(filepath=str(WORK/'low_source_axes.blend'))
    xf=Matrix(((0,1,0,0),(0,0,1,0),(1,0,0,0),(0,0,0,1)))
    for obj in bpy.data.objects:
        obj.data.transform(xf)
        obj.data.update()
    reticle=bpy.data.objects['Reticle']
    center=Vector((0,0.056,0.01798))
    reticle.data.transform(Matrix.Translation(-center))
    reticle.location=center
    root=bpy.data.objects.new('LUMAR_H1',None)
    bpy.context.collection.objects.link(root)
    for obj in list(bpy.data.objects):
        if obj!=root:
            obj.parent=root
    marker=bpy.data.objects.new('SightAxis',None)
    bpy.context.collection.objects.link(marker)
    marker.parent=root
    marker.location=(0,0.056,0.019)
    body=bpy.data.objects['Body']
    mat=bpy.data.materials.new('LumarBody')
    mat.use_nodes=True
    bsdf=mat.node_tree.nodes.get('Principled BSDF')
    for channel,socket in [('base_color','Base Color'),('roughness','Roughness'),('metallic','Metallic'),('normal','Normal')]:
        image=bpy.data.images.load(str(OUT/f'lumar_100_{channel}.png'))
        image.colorspace_settings.name='sRGB' if channel=='base_color' else 'Non-Color'
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage');tex.image=image
        if channel=='normal':
            normal=mat.node_tree.nodes.new('ShaderNodeNormalMap')
            mat.node_tree.links.new(tex.outputs['Color'],normal.inputs['Color'])
            mat.node_tree.links.new(normal.outputs['Normal'],bsdf.inputs[socket])
        else:
            mat.node_tree.links.new(tex.outputs['Color'],bsdf.inputs[socket])
    body.data.materials.clear();body.data.materials.append(mat)
    # Стекло и марка в Godot используют собственные материалы, без графов UCUPaint.
    for name,color in [('Lens',(0.9,0.98,0.94,0.12)),('Reticle',(1,0.04,0.005,1))]:
        m=bpy.data.materials.new('Lumar'+name);m.use_nodes=True
        b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=color
        b.inputs['Roughness'].default_value=0.03
        if name=='Reticle':
            b.inputs['Emission Color'].default_value=color;b.inputs['Emission Strength'].default_value=2
        else:
            b.inputs['Alpha'].default_value=color[3];m.surface_render_method='DITHERED'
            lens=bpy.data.objects['Lens']
            source_uv=lens.data.uv_layers.get('LensUV')
            if source_uv:
                coords=[tuple(v.uv) for v in source_uv.data]
                while lens.data.uv_layers:
                    lens.data.uv_layers.remove(lens.data.uv_layers[0])
                game_uv=lens.data.uv_layers.new(name='GameLensUV')
                for loop,coord in zip(game_uv.data,coords):loop.uv=coord
        o=bpy.data.objects[name];o.data.materials.clear();o.data.materials.append(m)
    # LOD тела — независимый узел, скрытый по умолчанию и выбираемый кодом.
    world=body.copy();world.data=body.data.copy();world.name='Body_LOD1'
    bpy.context.collection.objects.link(world);world.parent=root
    activate([world]);mod=world.modifiers.new('World reduction','DECIMATE');mod.ratio=0.24
    bpy.ops.object.modifier_apply(modifier=mod.name)
    # Явные треугольники нужны экспорту tangent-space normal map на бывших n-gon.
    for obj in (body,world,bpy.data.objects['Lens'],reticle):
        activate([obj])
        mod=obj.modifiers.new('Export triangles','TRIANGULATE')
        bpy.ops.object.modifier_apply(modifier=mod.name)
        for attr in list(obj.data.color_attributes):
            obj.data.color_attributes.remove(attr)
    activate(list(bpy.data.objects))
    bpy.ops.export_scene.gltf(filepath=str(OUT/'lumar_h1.glb'),export_format='GLB',use_selection=True,
        export_yup=False,export_animations=False,export_texcoords=True,export_normals=True,export_tangents=True,export_extras=True)
    counts={}
    for name in ('Body','Body_LOD1','Lens','Reticle'):
        mesh=bpy.data.objects[name].data;mesh.calc_loop_triangles();counts[name]=len(mesh.loop_triangles)
    report=dict(source={str(k):v for k,v in SOURCES.items()},triangles=counts,axis='X left, Y up, Z forward',
                mount_origin_m=[0,0,0],sight_axis_m=[0,0.056,0.019],states=[100],texture_size=RES)
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    bpy.ops.file.pack_all()
    bpy.ops.wm.save_as_mainfile(filepath=str(WORK/'lumar_h1_game.blend'))
    print('LUMAR_EXPORT_OK',counts)

args=sys.argv[sys.argv.index('--')+1:]
if args[0]=='geometry':geometry()
elif args[0]=='bake':bake(int(args[1]))
elif args[0]=='export':export()
elif args[0]=='imports':configure_imports()
else:raise ValueError(args)
