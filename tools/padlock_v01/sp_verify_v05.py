"""Verify saved v05 has actual anchor references, editable layers and native relief inputs."""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.source as O
import substance_painter.js as JS

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
assert P.is_in_edition_state() and P.file_path().endswith('padlock_v05_textured.spp')
sets=T.all_texture_sets();assert [s.name() for s in sets]==['Padlock']
ts=sets[0];st=ts.get_stack();assert len(ts.all_mesh_names())==24
roots=L.get_root_layer_nodes(st);assert len(roots)==38
old=[n for n in roots if not n.get_name().startswith('V05 ·')]
assert len(old)==37
assert sum(n.is_visible() for n in old)==11
assert st.get_channel(T.ChannelType.Height).format()==T.ChannelFormat.L32F
anchors=[];references=[];layers=[];filters=[];implicit_inputs=[]
def reference(src,owner):
    if isinstance(src,O.SourceReference):
        target=src.anchor
        if target is None:
            # Native filter/baker inputs also use SourceReference, without a custom anchor.
            assert ':' in owner and not owner.endswith((':micro_normal',':micro_height')),owner
            implicit_inputs.append(owner)
        else:references.append({'layer':owner,'anchor':target.get_name(),'uid':target.uid()})
def walk(nodes):
    for n in nodes:
        layers.append({'name':n.get_name(),'type':type(n).__name__,'visible':n.is_visible()})
        if isinstance(n,L.GroupLayerNode):walk(n.sub_layers())
        for e in n.content_effects()+n.mask_effects():
            if isinstance(e,L.AnchorPointEffectNode):anchors.append(e.get_name())
            elif isinstance(e,L.FillEffectNode):reference(e.get_source(None),n.get_name())
            elif isinstance(e,(L.GeneratorEffectNode,L.FilterEffectNode)):
                src=e.get_source();filters.append({'layer':n.get_name(),'name':e.get_name(),'parameters':src.get_parameters()})
                for key in src.image_inputs:reference(src.get_source(key),n.get_name()+':'+key)
walk([n for n in roots if n.get_name().startswith('V05 ·')])
assert len(anchors)==4 and len(references)>=8,(anchors,references)
assert len([n for n in layers if n['type']=='FillLayerNode'])==23
shader=JS.evaluate('alg.shaders.shaderInstancesToObject()')
assert shader['shaders']['Main shader']['parameters']['Coat']['coatEnabled'] is True
report={'status':'PASS','saved_reopened_project':P.file_path(),'mesh_count':24,'resolution':str(ts.get_resolution()),
        'original_layers_retained':37,'active_foundation_layers':11,'layers':layers,'anchors':anchors,'references':references,'filters':filters,
        'height_format':'L32F','editable_not_flattened':True,'implicit_filter_inputs':implicit_inputs,'shader':shader}
(WORK/'checks'/'painter_reopen_v05.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('V05_REOPEN_PASS',len(layers),'new layers/groups;',len(anchors),'anchors;',len(references),'live references')
P.close()
print('PADLOCK_V05_CLOSED_WITHOUT_RESAVE')
