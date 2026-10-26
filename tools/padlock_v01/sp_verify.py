"""Read back the saved, reopened native SPP, then release its memory."""
import json
from pathlib import Path
import substance_painter.application as A
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L

work=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
revision=globals().get('PADLOCK_REVISION','v02')
expected=(work/'painter'/('padlock_'+revision+'_textured.spp')).as_posix()
if not P.is_in_edition_state() or P.file_path().replace('\\','/').casefold()!=expected.casefold():
    raise RuntimeError('Unexpected or unready project')
sets=T.all_texture_sets()
assert [s.name() for s in sets]==['Padlock']
ts=sets[0];layers=L.get_root_layer_nodes(ts.get_stack());resolution=ts.get_resolution()
assert len(layers)==(18 if revision=='v02' else 25) and all(isinstance(layer,L.FillLayerNode) for layer in layers)
if revision=='v03':assert sum(layer.get_name().startswith('V03 ·') for layer in layers)==7
assert len(ts.all_mesh_names())==24
report={'status':'PASS','project':P.file_path(),'reopened_from_disk':True,
        'painter_version':A.version(),'last_saved_version':P.last_saved_substance_painter_version(),
        'resolution':str(resolution),'mesh_count':len(ts.all_mesh_names()),
        'layers':[{'name':layer.get_name(),'type':type(layer).__name__,
                   'visible':layer.is_visible(),'mask':layer.has_mask(),
                   'channels':[str(c) for c in layer.active_channels]} for layer in layers],
        'baked_maps':{name:(resource.url() if (resource:=ts.get_mesh_map_resource(usage)) else None)
                      for name,usage in T.MeshMapUsage.__members__.items()},
        'normal_convention':'Normal_OpenGL virtual map combines painted height and normal',
        'editable_not_flattened':True}
(work/'checks'/('painter_reopen.json' if revision=='v02' else 'painter_reopen_v03.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PAINTER_REOPEN_PASS',len(layers),'editable layers;',len(ts.all_mesh_names()),'meshes;',resolution)
P.close()
print('PADLOCK_PROJECT_CLOSED')
