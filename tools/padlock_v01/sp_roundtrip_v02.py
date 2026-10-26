"""Read-only baseline export to separate 8-bit recomputation from material changes."""
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.export as X

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
assert P.is_in_edition_state()
assert P.file_path().replace('\\','/').casefold()==(WORK/'painter'/'padlock_v02_textured.spp').as_posix().casefold()
st=T.all_texture_sets()[0].get_stack()
original=next(p for p in X.list_predefined_export_presets() if p.name=='glTF PBR Metal Roughness')
maps=[m for m in original.list_output_maps(st) if m['fileName'].endswith('baseColor')]
assert len(maps)==1
out=WORK/'checks'/'v02_roundtrip';out.mkdir(exist_ok=True)
preset={'name':'Padlock read-only reference','maps':maps}
result=X.export_project_textures({'exportShaderParams':False,'exportPath':out.as_posix(),
    'defaultExportPreset':preset['name'],'exportPresets':[preset],
    'exportList':[{'rootPath':'Padlock'}],
    'exportParameters':[{'parameters':{'fileFormat':'png','paddingAlgorithm':'infinite'}}]})
assert result.status==X.ExportStatus.Success
P.close()
print('V02_REFERENCE_EXPORTED_WITHOUT_SAVING',result.textures)
