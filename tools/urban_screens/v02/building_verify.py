"""Read-only verification of a reopened R06 native PBR file and its dependencies."""
from pathlib import Path
import hashlib
import importlib
import json
import math
import sys

import addon_utils
import bpy

PROJECT = Path(__file__).resolve().parents[3]
WORK = PROJECT / '_asset_src/urban_realrefs_v02/assets/R06_building/pbr_v01'
LIB = Path('E:/Models Blender/ENVIRONMENT/RING_Urban_95/revisions/v02_real_references/assets/R06_building/pbr_v01')


def verify(root):
    path = root / 'model/R06_building_pbr_v01.blend'
    bpy.context.preferences.use_preferences_save = False
    addon_utils.enable('bl_ext.blender_org.ucupaint', default_set=True)
    U = importlib.import_module('bl_ext.blender_org.ucupaint')
    bpy.ops.wm.open_mainfile(filepath=str(path))
    problems = []
    images = json.loads((root / 'checks/image_manifest.json').read_text(encoding='utf-8'))
    for rec in images:
        im = bpy.data.images.get(rec['datablock'])
        if not im or not im.packed_file:
            problems.append('Missing packed image: ' + rec['datablock'])
            continue
        if hashlib.sha256(bytes(im.packed_file.data)).hexdigest() != rec['sha256']:
            problems.append('Packed bytes changed: ' + im.name)
        external = Path(bpy.path.abspath(im.filepath))
        if not external.is_file() or hashlib.sha256(external.read_bytes()).hexdigest() != rec['sha256']:
            problems.append('External image missing/different: ' + im.name)
        if im.colorspace_settings.name != rec['colorspace']:
            problems.append('Colorspace changed: ' + im.name)
        if list(im.size) != rec['size'] or min(im.size) == 0:
            problems.append('Invalid image dimensions: ' + im.name)
        kind = rec['source_path'].replace('\\', '/').lower()
        if any(s in kind for s in ('/weather/', 'normal.', 'roughness.', '/owner_')) and im.colorspace_settings.name != 'Non-Color':
            problems.append('Data image is not Non-Color: ' + im.name)
    materials, layers, masks = [], 0, 0
    col = bpy.data.collections['MODEL | editable components']
    used = {m for ob in col.objects if ob.type in ('MESH', 'FONT', 'CURVE') for m in ob.data.materials if m}
    for mat in sorted(used, key=lambda m: m.name):
        groups = [n for n in mat.node_tree.nodes if n.type == 'GROUP' and getattr(n.node_tree, 'yp', None) and n.node_tree.yp.is_ypaint_node]
        if len(groups) != 1:
            problems.append('Expected one native stack: ' + mat.name)
            continue
        group = groups[0]
        tree = group.node_tree
        if tree.yp.version != '2.4.9':
            problems.append('Wrong native version: ' + mat.name)
        connected = {link.to_socket.name for link in mat.node_tree.links
            if link.from_node == group and link.to_node.type == 'BSDF_PRINCIPLED'}
        if not {'Base Color', 'Metallic', 'Roughness', 'Normal'}.issubset(connected):
            problems.append('Incomplete BSDF connection: ' + mat.name)
        for lay in tree.yp.layers:
            if not lay.enable:
                problems.append('Unexpected disabled production layer: ' + lay.name)
            intensity = U.common.get_entity_prop_value(lay, 'intensity_value')
            if intensity is None or not math.isfinite(float(intensity)):
                problems.append('Invalid native layer intensity: ' + lay.name)
            for mask in lay.masks:
                if mask.type == 'IMAGE':
                    src = U.common.get_mask_tree(mask).nodes.get(mask.source)
                    if not src or not src.image or not src.image.packed_file:
                        problems.append('Broken image mask: ' + lay.name + ' / ' + mask.name)
            for root_ch, ch in zip(tree.yp.channels, lay.channels):
                if ch.enable and ch.override:
                    actual = U.common.get_entity_prop_value(ch, 'override_color' if root_ch.type == 'RGB' else 'override_value')
                    vals = list(actual) if root_ch.type == 'RGB' else [actual]
                    if any(v is None or not math.isfinite(float(v)) for v in vals):
                        problems.append('Invalid native channel input: ' + lay.name)
            layers += 1
            masks += len(lay.masks)
        materials.append(dict(material=mat.name, stack=tree.name, version=tree.yp.version,
            layers=len(tree.yp.layers), connected_to_bsdf=sorted(connected)))
    meshes = [o for o in col.objects if o.type == 'MESH']
    for ob in meshes:
        for uv in ('MetricUV', 'WeatherUV', 'PartUV'):
            if uv not in ob.data.uv_layers or len(ob.data.uv_layers[uv].data) != len(ob.data.loops):
                problems.append('Missing/incomplete UV: ' + ob.name + ' / ' + uv)
    root_ob = next(o for o in col.objects if o.type == 'EMPTY' and o.name.startswith('R06 |'))
    if not root_ob.get('geometry_approved') or root_ob.get('texture_approved'):
        problems.append('Incorrect approval state')
    report = dict(file=str(path), blend_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        saved_file_reopened=True, blender=bpy.app.version_string, ucupaint=U.common.get_current_version_str(),
        native_materials=len(materials), native_layers=layers, native_masks=masks,
        image_datablocks_checked=len(images), external_hashes_verified=True,
        model_meshes_with_three_uvs=len(meshes), geometry_approved=True, texture_approved=False,
        game_export=False, problems=problems, materials=materials)
    (root / 'checks/native_validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if problems:
        raise RuntimeError(json.dumps(problems, ensure_ascii=False))
    print('R06_REOPEN_NATIVE_OK', len(materials), 'materials', layers, 'layers', masks, 'masks', len(images), 'packed images', flush=True)


if __name__ == '__main__':
    verify(LIB if '--delivery' in sys.argv else WORK)
