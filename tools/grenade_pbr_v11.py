"""Task 3 only: native PBR calibration on owner-approved task-2 v10b.

Keep all geometry, stacks, masks, factory maps, markings, deposition density
and rig intact. Every material edit must be separately recorded and verified.
"""
import argparse
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10b_Task2_На_проверку')
SOURCE = BASE / 'Grenade_MkII_Studio_v10b_Task2.blend'
OUT = ROOT / '_asset_src/grenade_codex/materials_v11_stage3'
FILE = OUT / 'Grenade_MkII_Studio_v11_Task3.blend'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


H = module('grenade_pbr_surface_helpers',ROOT/'tools/grenade_surface_v09.py')
Q = module('grenade_pbr_deposition_helpers',ROOT/'tools/grenade_deposition_v10.py')
CHANGES = [('head','10 • Uneven grey-green oxidation','Metallic',0.),
           ('head','12 • Restrained rusty flecks on exposed metal','Metallic',0.),
           ('lever','10 • Uneven grey-green oxidation','Metallic',0.),
           ('lever','12 • Restrained rusty flecks on exposed metal','Metallic',0.),
           ('wire','10 • Uneven grey-green oxidation','Metallic',0.),
           ('wire','12 • Restrained rusty flecks on exposed metal','Metallic',0.),
           ('lever','28 • Darker aged finish on lower lever','Metallic',1.)]


def inspect(U):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    record = {'source':str(SOURCE),'sha256':H.sha(SOURCE),
              'geometry':H.geometry_snapshot(),'paint':H.paint_snapshot(U),
              'studio':H.studio_snapshot(),'rig':H.rig_snapshot()}
    H.write_json(OUT/'checks/baseline_v10b.json',record)
    settings = {}
    for material in bpy.data.materials:
        if not material.name.startswith('UCUPaint_v08_'):
            continue
        group = next(n for n in material.node_tree.nodes if n.type=='GROUP' and
                     getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
        tree = group.node_tree
        info = {'root_inputs':{s.name:H.value(s.default_value) for s in group.inputs
                               if hasattr(s,'default_value')}, 'layers':[]}
        print('MATERIAL',material.name,'ROOT',info['root_inputs'],flush=True)
        for layer in tree.yp.layers:
            row = {'name':layer.name,'type':layer.type,'amount':U.common.get_entity_prop_value(layer,'intensity_value'),
                   'channels':{},'masks':[m.name for m in layer.masks]}
            for root,channel in zip(tree.yp.channels,layer.channels):
                if not channel.enable:
                    continue
                values = {'override':channel.override,'intensity':U.common.get_entity_prop_value(channel,'intensity_value')}
                if channel.override:
                    prop = 'override_color' if root.type=='RGB' else 'override_value'
                    values[prop] = H.value(U.common.get_entity_prop_value(channel,prop))
                if root.type=='NORMAL':
                    values['distance'] = U.common.get_entity_prop_value(channel,'bump_distance')
                    values['midlevel'] = U.common.get_entity_prop_value(channel,'bump_midlevel')
                    values['blend'] = channel.height_blend_type
                row['channels'][root.name] = values
            info['layers'].append(row)
            print('LAYER',layer.name,'amount',round(row['amount'],3),
                  json.dumps(row['channels'],ensure_ascii=False),flush=True)
        settings[material.name] = info
    H.write_json(OUT/'checks/actual_pbr_v10b.json',settings)
    print('PBR_INSPECT_OK',record['sha256'],flush=True)


def patch(U):
    baseline = json.loads((OUT/'checks/baseline_v10b.json').read_text(encoding='utf8'))
    assert H.sha(SOURCE)==baseline['sha256'], 'Accepted source changed'
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    changes = []
    for family, name, channel, value in CHANGES:
        material = bpy.data.materials['UCUPaint_v08_'+family]
        group = next(n for n in material.node_tree.nodes if n.type=='GROUP' and
                     getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
        tree = group.node_tree
        item = next(l for l in tree.yp.layers if l.name==name)
        ch = next(c for r,c in zip(tree.yp.channels,item.channels) if r.name==channel)
        assert ch.enable and ch.override, 'Scalar correction requires the existing override'
        old = U.common.get_entity_prop_value(ch,'override_value')
        H.synchronize(U,ch,'override_value',value)
        changes.append({'material':material.name,'layer':name,'channel':channel,
                        'property':'override_value','before':old,'after':value,
                        'reason':'Owner confirmed darkened exposed metal on lower lever; color and roughness retained'
                        if name.startswith('28') else 'Nonmetallic oxide layer; coverage stays in original alpha masks'})
    # No graph, layer, mask, UV, mesh, texture pixel or Bump change is needed.
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:continue
        absolute = Path(bpy.path.abspath(image.filepath)).resolve()
        assert absolute.is_relative_to(BASE.resolve()), ('Unexpected source image path',absolute)
        destination = OUT/absolute.relative_to(BASE.resolve())
        destination.parent.mkdir(parents=True,exist_ok=True)
        if not destination.exists():shutil.copy2(absolute,destination)
        image.filepath = '//'+destination.relative_to(OUT).as_posix()
        for packed in image.packed_files:packed.filepath=image.filepath
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False,compress=True)
    H.write_json(OUT/'checks/pbr_changes.json',changes)
    print('TASK3_PBR_SAVED',FILE,'scalar_changes',len(changes),flush=True)


def verify(U,path=FILE):
    base = json.loads((OUT/'checks/baseline_v10b.json').read_text(encoding='utf8'))
    changes = json.loads((OUT/'checks/pbr_changes.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    paint = H.paint_snapshot(U)
    actual = []
    for change in changes:
        material = change['material'];name=change['layer'];channel=change['channel']
        tree = next(n.node_tree for n in bpy.data.materials[material].node_tree.nodes if n.type=='GROUP'
                    and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
        index = next(i for i,r in enumerate(tree.yp.channels) if r.name==channel)
        item = next(l for l in tree.yp.layers if l.name==name)
        value = U.common.get_entity_prop_value(item.channels[index],change['property'])
        assert abs(value-change['after'])<1e-6
        assert abs(paint[material]['layers'][name]['props']['channels'][index][change['property']]-value)<1e-6
        actual.append({**change,'actual_after_reopen':value})
        # Only the explicit corrected scalar is excluded from protected-state comparison.
        paint[material]['layers'][name]['props']['channels'][index][change['property']] = \
            base['paint'][material]['layers'][name]['props']['channels'][index][change['property']]
    geometry_diff=H.differences(base['geometry'],H.geometry_snapshot())
    paint_diff=H.differences(Q.strip_ui(base['paint']),Q.strip_ui(paint))
    rig_diff=H.differences(base['rig'],H.rig_snapshot())
    studio_diff=H.differences(base['studio'],H.studio_snapshot())
    # Preserve every old image including retained authoring/reference datablocks.
    original_images=json.loads((BASE/'checks/verify_task2_correction.json').read_text(encoding='utf8'))['images']
    previous={row['name']:(row['sha256'],row['color_space']) for row in original_images}
    images=[]
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:continue
        external=Path(bpy.path.abspath(image.filepath))
        assert image.packed_file and external.is_file(),('Missing texture',image.name)
        digest=__import__('hashlib').sha256(bytes(image.packed_file.data)).hexdigest()
        assert digest==H.sha(external)
        assert previous.pop(image.name)==(digest,image.colorspace_settings.name)
        images.append({'name':image.name,'file':image.filepath,'sha256':digest,'color_space':image.colorspace_settings.name})
    assert not previous, 'Image datablocks removed'
    result={'file':str(path),'sha256':H.sha(path),'verified_changes':actual,
            'geometry_differences':geometry_diff,'protected_material_differences':paint_diff,
            'rig_differences':rig_diff,'studio_differences':studio_diff,'images':images,
            'native_stacks':len(paint),'native_layers':sum(len(m['layers']) for m in paint.values()),
            'native_masks':sum(len(l['props']['masks']) for m in paint.values() for l in m['layers'].values()),
            'pass':not geometry_diff and not paint_diff and not rig_diff and not studio_diff}
    H.write_json(OUT/'checks/verify_task3.json',result)
    print('TASK3_VERIFY',result['pass'],'protected_diffs',len(geometry_diff+paint_diff+rig_diff+studio_diff),flush=True)
    for diff in (geometry_diff+paint_diff+rig_diff+studio_diff)[:12]:print('DIFFERENCE',diff,flush=True)
    if not result['pass']:raise RuntimeError('Unexpected protected-state edit')


def render(version,shot,samples,pilot):
    path=SOURCE if version=='before' else FILE
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene=bpy.context.scene;scene.frame_set(1);H.configure_render(scene,samples)
    pos,target,lens,width,height={'body':((.10,-.17,.089),(.002,-.005,.043),105,1920,1920),
                                 'lower_lever':((.14,-.07,.061),(.029,-.003,.033),105,1920,1920),
                                 **H.SHOTS}[shot]
    scene.camera.location=pos
    scene.camera.rotation_euler=(Vector(target)-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.lens=lens
    scene.render.resolution_x=width//2 if pilot else width
    scene.render.resolution_y=height//2 if pilot else height
    bpy.context.view_layer.update()
    output=OUT/('pilot' if pilot else 'comparisons')/f'{shot}_{version}.png'
    output.parent.mkdir(parents=True,exist_ok=True);scene.render.filepath=str(output)
    spec=H.studio_snapshot()
    spec['render']={p:H.value(getattr(scene.render,p)) for p in ['resolution_x','resolution_y','resolution_percentage','filter_size']}
    spec['cycles']={p:H.value(getattr(scene.cycles,p)) for p in ['samples','seed','use_denoising','adaptive_threshold','max_bounces','diffuse_bounces','glossy_bounces']}
    spec['dof']=False
    H.write_json(output.with_suffix('.json'),{'source_file':str(path),'source_sha256':H.sha(path),'comparison_spec':spec})
    print('RENDER_BEGIN',shot,version,samples,flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK',output,H.sha(output),flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['inspect','patch','verify','render','compare'])
    parser.add_argument('--file',type=Path,default=FILE)
    parser.add_argument('--version',choices=['before','after'],default='after')
    parser.add_argument('--shot',choices=['body','head','lever','lower_lever','wire','overview'],default='head')
    parser.add_argument('--samples',type=int,default=256)
    parser.add_argument('--pilot',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    OUT.mkdir(parents=True,exist_ok=True)
    U = H.native()
    if args.mode=='inspect':inspect(U)
    elif args.mode=='patch':patch(U)
    elif args.mode=='verify':verify(U,args.file)
    elif args.mode=='render':render(args.version,args.shot,args.samples,args.pilot)
    elif args.mode=='compare':
        for shot in ['head','lower_lever','wire']:
            for version in ['before','after']:render(version,shot,args.samples,args.pilot)


if __name__=='__main__':main()
