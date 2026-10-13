"""Task 2 correction: readable accumulated residue in accepted body grooves.

Never rebuild or edit accepted geometry, UVs, markings, factory surfaces or
the v10 stacks. New native UCUPaint layers are restricted by recessed geometry.
"""
import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('E:/Models Blender/From Scenario/Grenade/Codex_Texture_v10_Task2_На_проверку')
SOURCE = BASE / 'Grenade_MkII_Studio_v10_Task2.blend'
OUT = ROOT / '_asset_src/grenade_codex/materials_v10b_stage2_recess'
FILE = OUT / 'Grenade_MkII_Studio_v10b_Task2.blend'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


D = module('grenade_deposition_v10_helpers', ROOT / 'tools/grenade_deposition_v10.py')
H = D.H
HELPERS = module('recess_native_helpers', Path('C:/Users/Schecter_8ght/.codex/skills/weapon-asset-texturing/scripts/ucupaint_helpers.py'))
ATTRS = ['V10b_RecessBed', 'V10b_DeepPocket', 'V10b_ShelteredShelf']
PREFIX = 'V10b • '
LAYERS = ['78 • Accumulated dry residue in recessed channel beds',
          '79 • Interrupted compact soil in deepest cast pockets',
          '80 • Angular grit retained between cast sectors']


def smooth(a, b, x):
    t = np.clip((x-a)/(b-a), 0, 1)
    return t*t*(3-2*t)


def recess_geometry():
    """Closing the radial outer envelope detects horizontal AND vertical beds.

    Original Wear_Recess only compared angular radii at the same z, so the
    completely recessed horizontal ring rows received almost no deposition.
    A 3.36 mm vertical closing preserves the curved/tapered overall profile.
    """
    mesh = bpy.data.objects['GrenadeBody'].data
    co = H.array(mesh.vertices, 'co', 3)
    assert len(co) == 641*512+1
    grid = co[:-1].reshape(641, 512, 3)
    z = grid[:, 0, 2]
    assert np.max(np.ptp(grid[:, :, 2], axis=1)) < 1e-7
    radius = np.hypot(grid[:, :, 0], grid[:, :, 1])
    outer = np.percentile(radius, 85, axis=1)
    steps = round(.00336/float(np.median(np.diff(z))))
    def filter_1d(values, maximum):
        padded = np.pad(values, (steps, steps), mode='edge')
        reduction = np.maximum if maximum else np.minimum
        result = values.copy()
        for shift in range(-steps, steps+1):
            result = reduction(result, padded[steps+shift:steps+shift+len(values)])
        return result
    envelope = filter_1d(filter_1d(outer, True), False)
    depth = np.maximum(0, envelope[:, None]-radius)
    zone = smooth(.001, .007, z)*(1-smooth(.061, .067, z))
    pocket = smooth(.00024, .00140, depth)*zone[:, None]
    deep = smooth(.00080, .00195, depth)*zone[:, None]
    normals = H.array(mesh.vertices, 'normal', 3)
    up = smooth(-.03, .72, normals[:, 2])
    contact = D.old_attribute(mesh, 'Wear_Contact')
    bed = np.r_[pocket.ravel(), 0]*(1-.42*contact)
    deep = np.r_[deep.ravel(), 0]*(1-.3*contact)
    shelf = bed*(.18+.82*up)
    active, render = mesh.color_attributes.active_color_name, mesh.color_attributes.render_color_index
    for name, field in zip(ATTRS, [bed, deep, shelf]):
        assert not mesh.color_attributes.get(name), 'Patch must start from pristine v10'
        D.add_attribute(mesh, name, field)
    mesh.color_attributes.active_color_name = active
    mesh.color_attributes.render_color_index = render
    mesh.update()
    H.write_json(OUT/'checks/recess_geometry.json', {
        'method':'Radius at each accepted vertex compared to closed outer radial envelope',
        'vertical_closing_half_window_mm':steps*float(np.median(np.diff(z)))*1000,
        'scope':'Body below 67 mm; coating bands and neck excluded',
        'depth_soft_gate_mm':[.24,1.40], 'deep_soft_gate_mm':[.80,1.95],
        'attributes':{name:{'min':float(v.min()),'max':float(v.max()),'mean':float(v.mean()),
                            'nonzero_fraction':float(np.mean(v>0))}
                      for name,v in zip(ATTRS,[bed,deep,shelf])}})
    print('RECESS_GEOMETRY', [(a, float(v.mean())) for a,v in zip(ATTRS,[bed,deep,shelf])], flush=True)


def layer(U, tree, name, color, rough, height, amount, distance, noise_scale=None):
    kind = 'NOISE' if noise_scale else 'COLOR'
    tree.yp.halt_update = True
    item = U.Layer.add_new_layer(tree, name, kind, -1, 'MIX', 'OVERLAY', 'BUMP_MAP',
                                'Object', 'UVMap', use_designated_idx=True, designated_index=0)
    tree.yp.halt_update = False
    values = {'Color':color, 'Metallic':0., 'Roughness':rough, 'Normal':height}
    for root, ch in zip(tree.yp.channels, item.channels):
        val = values[root.name]
        ch.enable = val is not None
        if not ch.enable:
            continue
        if val != 'source':
            ch.override = True
            ch.override_type = 'DEFAULT'
            HELPERS.sync_property(U, ch, 'override_color' if root.type=='RGB' else 'override_value', val)
        if root.type=='NORMAL':
            HELPERS.sync_property(U, ch, 'bump_distance', distance)
            HELPERS.sync_property(U, ch, 'bump_midlevel', .5)
    if noise_scale:
        source = U.common.get_layer_source(item)
        source.inputs['Scale'].default_value = noise_scale
        source.inputs['Detail'].default_value = 2.0
        source.inputs['Roughness'].default_value = .65
    HELPERS.sync_property(U, item, 'intensity_value', amount)
    return item


def geometry_mask(U, item, attribute):
    return U.Mask.add_new_mask(item, PREFIX+'Actual channel bed, cleaned convex grip',
                               'VCOL', 'Object', 'UVMap', vcol_name=attribute)


def noise_mask(U, item, name, scale, lo, hi, translation):
    mask = U.Mask.add_new_mask(item, PREFIX+name, 'NOISE', 'Object', 'UVMap')
    source = U.common.get_mask_source(mask)
    source.inputs['Scale'].default_value = scale
    source.inputs['Detail'].default_value = 2.2
    source.inputs['Roughness'].default_value = .66
    mask.translation = translation
    HELPERS.local_noise_ramp(U, mask, lo, hi)
    return mask


def image_mask(U, item, image, name, height):
    mask = U.Mask.add_new_mask(item, PREFIX+name, 'IMAGE', height.texcoord_type,
                               height.uv_name, image=image)
    mask.scale, mask.translation, mask.rotation = height.scale, height.translation, height.rotation
    source = U.common.get_mask_source(mask)
    origin = U.common.get_layer_source(height)
    source.projection, source.projection_blend = origin.projection, origin.projection_blend
    source.interpolation = 'Linear'
    return mask


def valley(U, item, height, floor):
    image = bpy.data.images['body_local_valley_retention_16.png']
    mask = image_mask(U, item, image, 'Accepted microvalleys retain fine residue', height)
    modifier = importlib.import_module(U.__name__+'.MaskModifier')
    modifier.add_new_mask_modifier(mask, 'RAMP')
    ramp = U.common.get_mask_tree(mask).nodes[mask.modifiers[-1].ramp].color_ramp
    ramp.elements[0].color = (floor,floor,floor,1)
    ramp.elements[1].color = (1,1,1,1)
    return mask


def baseline(U):
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    record = {'source': str(SOURCE), 'sha256': H.sha(SOURCE),
              'geometry': H.geometry_snapshot(), 'paint': H.paint_snapshot(U),
              'studio': H.studio_snapshot(), 'rig': H.rig_snapshot()}
    H.write_json(OUT / 'checks/baseline_v10.json', record)
    obj = bpy.data.objects['GrenadeBody']
    mesh = obj.data
    fields = {'co': H.array(mesh.vertices, 'co', 3),
              'normal': H.array(mesh.vertices, 'normal', 3)}
    for name in ['Wear_Recess', 'Wear_Contact', 'Wear_Dust', *D.ATTRS[:2]]:
        fields[name] = D.old_attribute(mesh, name)
    np.savez_compressed(OUT / 'checks/body_fields.npz', **fields)
    tree = D.tree_for(obj)
    for layer in tree.yp.layers:
        if layer.name[:2] in {'70', '72', '74', '76'}:
            data = record['paint'][obj.active_material.name]['layers'][layer.name]
            H.write_json(OUT / 'checks' / ('layer_' + layer.name[:2] + '.json'), data)
            print('LAYER', layer.name, 'amount', layer.intensity_value,
                  'channels', [(c.enable, c.override, c.override_value, c.bump_distance)
                               for c in layer.channels], flush=True)
    print('BASELINE_OK', record['sha256'], 'body', len(mesh.vertices), flush=True)


def patch(U):
    original = json.loads((OUT/'checks/baseline_v10.json').read_text(encoding='utf8'))
    assert H.sha(SOURCE) == original['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    obj = bpy.data.objects['GrenadeBody']
    bpy.context.view_layer.objects.active = obj
    tree = D.tree_for(obj)
    assert not any(l.name in LAYERS for l in tree.yp.layers)
    recess_geometry()
    casting = next(l for l in tree.yp.layers if l.name.startswith('03 • Casting'))
    # Thin dry residue sits over the accepted relief. It has a subtle own fine
    # tooth; the full cast surface remains beneath and is not globally changed.
    item = layer(U,tree,LAYERS[0],(.13,.10,.059),.83,'source',.62,.000006,27000)
    geometry_mask(U,item,ATTRS[2])
    noise_mask(U,item,'Interrupted residue patches, about 1 mm',1100,.30,.62,(.011,.023,.017))
    valley(U,item,casting,.65)
    # Compacted small patches use deeper shelter and millimetre breakup only.
    item = layer(U,tree,LAYERS[1],(.059,.042,.023),.89,'source',.72,.000018,7500)
    geometry_mask(U,item,ATTRS[1])
    noise_mask(U,item,'Separated compact-soil patches',950,.45,.68,(.043,.015,.031))
    # Individual pale/dry grains contrast with the olive substrate in macro.
    # The positive height (45 um maximum before opacity) shares its footprint.
    image = bpy.data.images.load(str(OUT/'textures/deposition/recess_angular_grit_8k.png'),check_existing=True)
    image.colorspace_settings.name = 'Non-Color'
    image.pack()
    item = layer(U,tree,LAYERS[2],(.20,.155,.090),.87,.95,.96,.00010)
    geometry_mask(U,item,ATTRS[2])
    image_mask(U,item,image,'Angular grouped grit, 0.065–0.35 mm',casting)
    valley(U,item,casting,.75)
    H.reconnect(U,tree)
    tree['task2_recess_correction'] = 'Three additive native residue layers; actual horizontal and vertical channel depth'
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        absolute = Path(bpy.path.abspath(image.filepath)).resolve()
        if absolute.is_relative_to(BASE.resolve()):
            destination = OUT/absolute.relative_to(BASE.resolve())
            destination.parent.mkdir(parents=True,exist_ok=True)
            if not destination.exists():
                import shutil
                shutil.copy2(absolute,destination)
        elif absolute.is_relative_to(OUT.resolve()):
            destination = absolute
        else:
            raise RuntimeError(('Unexpected image path',absolute))
        image.filepath = '//'+destination.relative_to(OUT).as_posix()
        for packed in image.packed_files:
            packed.filepath = image.filepath
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False,compress=True)
    print('TASK2_CORRECTION_SAVED',FILE,flush=True)


def render(U, version, shot, samples, pilot):
    path = SOURCE if version=='before' else FILE
    bpy.ops.wm.open_mainfile(filepath=str(path))
    scene = bpy.context.scene
    scene.frame_set(1)
    H.configure_render(scene,samples)
    pos,target,lens = {'body':((.10,-.17,.089),(.002,-.005,.043),105),
                      'macro':((.060,-.110,.078),(.003,-.024,.040),105)}[shot]
    scene.camera.location = pos
    scene.camera.rotation_euler = (Vector(target)-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.lens = lens
    scene.render.resolution_x = scene.render.resolution_y = 960 if pilot else 1920
    # Explicit update before recording evaluated camera, not only before render.
    bpy.context.view_layer.update()
    output = OUT/('pilot' if pilot else 'comparisons')/f'{shot}_{version}.png'
    output.parent.mkdir(parents=True,exist_ok=True)
    scene.render.filepath = str(output)
    spec = H.studio_snapshot()
    spec['render'] = {p:H.value(getattr(scene.render,p)) for p in
                      ['resolution_x','resolution_y','resolution_percentage','filter_size']}
    spec['cycles'] = {p:H.value(getattr(scene.cycles,p)) for p in
                      ['samples','seed','use_denoising','adaptive_threshold','max_bounces',
                       'diffuse_bounces','glossy_bounces']}
    spec['dof'] = scene.camera.data.dof.use_dof
    H.write_json(output.with_suffix('.json'),{'source_file':str(path),'source_sha256':H.sha(path),
                                             'comparison_spec':spec})
    print('RENDER_BEGIN',shot,version,samples,flush=True)
    bpy.ops.render.render(write_still=True)
    print('RENDER_OK',output,H.sha(output),flush=True)


def verify(U, path=FILE):
    original = json.loads((OUT/'checks/baseline_v10.json').read_text(encoding='utf8'))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    geometry = H.geometry_snapshot()
    added_attributes = {}
    for name, old in original['geometry'].items():
        current = geometry[name]
        extra = {key:value for key,value in current['colors'].items() if key not in old['colors']}
        assert set(extra)==(set(ATTRS) if name=='GrenadeBody' else set()), ('Unexpected attributes',name,extra)
        added_attributes[name] = extra
        for key in extra:
            del current['colors'][key]
    geom_diff = H.differences(original['geometry'],geometry)
    paint = H.paint_snapshot(U)
    paint_diff = []
    old_count, mask_count = 0, 0
    for name, old in original['paint'].items():
        current = paint[name]
        current_layers = dict(current['layers'])
        extras = [key for key in current_layers if key not in old['layers']]
        assert set(extras)==(set(LAYERS) if name=='UCUPaint_v08_CastBody' else set())
        for key in extras:
            del current_layers[key]
        assert list(old['layers'])==list(current_layers), 'Original layer ordering changed'
        current = {**current,'layers':current_layers}
        paint_diff += H.differences(D.strip_ui(old),D.strip_ui(current),name)
        old_count += len(old['layers'])
        mask_count += sum(len(l['props']['masks']) for l in old['layers'].values())
    rig_diff = H.differences(original['rig'],H.rig_snapshot())
    studio_diff = H.differences(original['studio'],H.studio_snapshot())
    images = []
    for image in bpy.data.images:
        if image.type in {'RENDER_RESULT','COMPOSITING'}:
            continue
        external = Path(bpy.path.abspath(image.filepath))
        assert image.packed_file and external.is_file(), ('Missing image',image.name)
        digest = __import__('hashlib').sha256(bytes(image.packed_file.data)).hexdigest()
        assert digest==H.sha(external), ('External/packed image differs',image.name)
        images.append({'name':image.name,'file':image.filepath,'sha256':digest,
                       'color_space':image.colorspace_settings.name})
    tree = D.tree_for(bpy.data.objects['GrenadeBody'])
    added_layers = []
    for item in tree.yp.layers:
        if item.name not in LAYERS:
            continue
        actual = {}
        for root,channel in zip(tree.yp.channels,item.channels):
            props = ['intensity_value']
            if channel.override:
                props.append('override_color' if root.type=='RGB' else 'override_value')
            if root.type=='NORMAL':
                props.extend(['bump_distance','bump_midlevel'])
            actual[root.name] = {prop:H.value(U.common.get_entity_prop_value(channel,prop)) for prop in props}
            for prop in props:
                requested = H.value(getattr(channel,prop))
                received = actual[root.name][prop]
                if prop=='override_color':received=received[:3]
                assert np.allclose(requested,received,rtol=0,atol=1e-6), ('Native input mismatch',item.name,prop)
        amount = U.common.get_entity_prop_value(item,'intensity_value')
        assert abs(amount-item.intensity_value)<1e-6
        for mask in item.masks:
            assert mask.enable and mask.blend_type=='MULTIPLY'
        metal = next(c for r,c in zip(tree.yp.channels,item.channels) if r.name=='Metallic')
        assert metal.enable and metal.override and U.common.get_entity_prop_value(metal,'override_value')==0
        added_layers.append({'name':item.name,'amount':amount,'channels_actual':actual,
                             'native_masks':[{'name':m.name,'type':m.type,
                                              'attribute':getattr(m,'vcol_name','')} for m in item.masks]})
    result = {'file':str(path),'sha256':H.sha(path),
              'geometry_differences':geom_diff,'old_material_differences':paint_diff,
              'rig_differences':rig_diff,'studio_differences':studio_diff,
              'new_attributes':added_attributes,'retained_layers':old_count,'retained_masks':mask_count,
              'new_layers':added_layers,'native_stacks':len(paint),
              'native_layers':sum(len(p['layers']) for p in paint.values()),
              'images':images,'pass':not geom_diff and not paint_diff and not rig_diff and not studio_diff}
    H.write_json(OUT/'checks/verify_task2_correction.json',result)
    print('CORRECTION_VERIFY',result['pass'],'geometry',len(geom_diff),'old_layers',len(paint_diff),
          'rig',len(rig_diff),'studio',len(studio_diff),'images',len(images),flush=True)
    for difference in (geom_diff+paint_diff+rig_diff+studio_diff)[:16]:
        print('DIFFERENCE',difference,flush=True)
    if not result['pass']:
        raise RuntimeError('Protected v10 data differs')


def raking_check():
    """Two temporary directed-light checks; never save these scene settings."""
    bpy.ops.wm.open_mainfile(filepath=str(FILE))
    scene = bpy.context.scene
    scene.frame_set(1)
    H.configure_render(scene,96)
    scene.render.resolution_x = scene.render.resolution_y = 960
    scene.camera.location = (.060,-.110,.078)
    scene.camera.rotation_euler = (Vector((.003,-.024,.040))-scene.camera.location).to_track_quat('-Z','Y').to_euler()
    scene.camera.data.lens = 105
    key = next(o for o in scene.objects if o.type=='LIGHT' and 'KEY' in o.name.upper())
    for obj in scene.objects:
        if obj.type=='LIGHT':obj.data.energy=0
    key.data.energy = .42
    key.data.size, key.data.size_y = .018, .055
    key.data.color = (1,1,1)
    for side,pos in [('left',(-.09,-.06,.045)),('right',(.10,-.025,.055))]:
        key.location = pos
        key.rotation_euler = (Vector((.003,-.024,.040))-key.location).to_track_quat('-Z','Y').to_euler()
        bpy.context.view_layer.update()
        output = OUT/'checks'/f'raking_{side}.png'
        scene.render.filepath = str(output)
        H.write_json(output.with_suffix('.json'), {'purpose':'Unsaved candidate check under opposing raking light',
            'source_sha256':H.sha(FILE),'positive_particle_height_um_before_opacity':45,
            'spec':H.studio_snapshot(),'render_samples':96,'dof':False,'denoise':False})
        bpy.ops.render.render(write_still=True)
        print('RAKING_CHECK',side,output,flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['baseline','patch','verify','render','compare','raking-check'])
    parser.add_argument('--file',type=Path,default=FILE)
    parser.add_argument('--version',choices=['before','after'],default='after')
    parser.add_argument('--shot',choices=['body','macro'],default='body')
    parser.add_argument('--samples',type=int,default=256)
    parser.add_argument('--pilot',action='store_true')
    args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    OUT.mkdir(parents=True, exist_ok=True)
    U = H.native()
    if args.mode=='baseline':baseline(U)
    elif args.mode=='patch':patch(U)
    elif args.mode=='verify':verify(U,args.file)
    elif args.mode=='raking-check':raking_check()
    elif args.mode=='render':render(U,args.version,args.shot,args.samples,args.pilot)
    elif args.mode=='compare':
        for shot in ['body','macro']:
            for version in ['before','after']:
                render(U,version,shot,args.samples,args.pilot)


if __name__ == '__main__':
    main()
