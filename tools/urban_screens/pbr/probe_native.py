"""Read actual native inputs of a saved material during visual QA."""
from pathlib import Path
import sys
import json
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import materials as M
from plan import ROOT
M.native()
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'assets/U06_05_drain/model/U06_05_drain_pbr_v01.blend'))
for mat in bpy.data.materials:
    if not mat.node_tree or not mat.get('surface_recipe'):
        continue
    print('NATIVE_PROBE',mat.name,mat['surface_recipe'])
    for node in mat.node_tree.nodes:
        if node.type!='GROUP' or not getattr(node.node_tree,'yp',None) or not node.node_tree.yp.is_ypaint_node:
            continue
        for l in node.node_tree.yp.layers:
            data=dict(name=l.name,rna_intensity=l.intensity_value,socket_intensity=M.U.common.get_entity_prop_value(l,'intensity_value'),channels=[])
            for root,ch in zip(node.node_tree.yp.channels,l.channels):
                if ch.enable:
                    value=M.U.common.get_entity_prop_value(ch,'override_color' if root.type=='RGB' else 'override_value') if ch.override else 'source'
                    data['channels'].append(dict(channel=root.name,override=ch.override,value=list(value) if root.type=='RGB' and value!='source' else value))
            print('NATIVE_PROBE_LAYER',json.dumps(data))
