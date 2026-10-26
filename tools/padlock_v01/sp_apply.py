import importlib
import sys
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.export as X
import sp_lib

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
sys.path.insert(0,'E:/Games/RING-godot/tools/padlock_v01')
if not P.is_open():raise RuntimeError('Padlock project is not open')
if P.file_path() and P.file_path().replace('\\','/').casefold()!=(WORK/'painter'/'padlock_v02_textured.spp').as_posix().casefold():
    raise RuntimeError('Refusing to edit a different project: '+P.file_path())
sets=T.all_texture_sets()
if [t.name() for t in sets]!=['Padlock']:raise RuntimeError('Unexpected texture sets')
import sp_layers
importlib.reload(sp_layers)
sp_layers.apply(sets[0].get_stack())
P.save_as(str(WORK/'painter'/'padlock_v02_textured.spp').replace('\\','/'),P.ProjectSaveMode.Full)
out=WORK/'textures'/'export';out.mkdir(exist_ok=True)
original=next(p for p in X.list_predefined_export_presets() if p.name=='glTF PBR Metal Roughness')
maps=original.list_output_maps(sets[0].get_stack())
for item in maps:
    if 'normal' in item['fileName'].lower():
        item['parameters']['bitDepth']='16';item['parameters']['dithering']=False
preset={'name':'Padlock editable source maps','maps':maps}
config={'exportShaderParams':False,'exportPath':out.as_posix(),
        'defaultExportPreset':preset['name'],'exportPresets':[preset],
        'exportList':[{'rootPath':'Padlock'}],
        'exportParameters':[{'parameters':{'fileFormat':'png','paddingAlgorithm':'infinite'}}]}
result=X.export_project_textures(config)
if result.status!=X.ExportStatus.Success:raise RuntimeError(str(result))
print('EXPORT',result.status,result.textures)
print('LAYERS',[(n.get_name(),type(n).__name__) for n in L.get_root_layer_nodes(sets[0].get_stack())])
