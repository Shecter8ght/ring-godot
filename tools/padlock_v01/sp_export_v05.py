"""Export the saved/reopened SPP separately, publishing only a complete five-map set."""
import json
import time
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.export as X
import substance_painter.js as JS
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
expected=(WORK/'painter'/'padlock_v05_textured.spp').as_posix()
if not P.is_in_edition_state() or P.file_path().replace('\\','/').casefold()!=expected.casefold():
    raise RuntimeError('Unexpected or unready project')
ts=T.all_texture_sets()[0];st=ts.get_stack()
assert ts.name()=='Padlock' and len(L.get_root_layer_nodes(st))==38
marker=WORK/'sp_jobs'/'_v05_ready.txt';marker.unlink(missing_ok=True)

def export_saved():
    # A failed exporter cannot replace any of the five current maps with a partial PNG.
    stage=WORK/'textures'/('export_v05_stage_'+str(time.time_ns()));stage.mkdir()
    original=next(p for p in X.list_predefined_export_presets() if p.name=='glTF PBR Metal Roughness')
    maps=original.list_output_maps(st)
    for item in maps:
        if 'normal' in item['fileName'].lower():item['parameters'].update(bitDepth='16',dithering=False)
    def channel(dst,src,name):return {'destChannel':dst,'srcChannel':src,'srcMapName':name,'srcMapType':'documentMap'}
    maps.append({'fileName':'Padlock_coat','channels':[channel('R','L','coatOpacity'),channel('G','L','coatRoughness'),channel('B','L','coatOpacity')],
                 'parameters':{'fileFormat':'png','bitDepth':'8','dithering':False}})
    maps.append({'fileName':'Padlock_coatNormal','channels':[channel(c,c,'coatNormal') for c in ('R','G','B')],
                 'parameters':{'fileFormat':'png','bitDepth':'16','dithering':False}})
    preset={'name':'Padlock v05 coat maps','maps':maps}
    config={'exportShaderParams':False,'exportPath':stage.as_posix(),'defaultExportPreset':preset['name'],
            'exportPresets':[preset],'exportList':[{'rootPath':'Padlock'}],
            'exportParameters':[{'parameters':{'fileFormat':'png','paddingAlgorithm':'infinite'}}]}
    result=X.export_project_textures(config)
    if result.status!=X.ExportStatus.Success:raise RuntimeError(str(result))
    names=['Padlock_'+n+'.png' for n in ('baseColor','occlusionRoughnessMetallic','normal','coat','coatNormal')]
    payloads={name:(stage/name).read_bytes() for name in names}
    for name,data in payloads.items():
        assert data[:8]==b'\x89PNG\r\n\x1a\n' and data[-8:]==b'IEND\xaeB`\x82',name
    out=WORK/'textures'/'export_v05';out.mkdir(exist_ok=True)
    for name,data in payloads.items():
        temporary=out/(name+'.complete');temporary.write_bytes(data);temporary.replace(out/name)
    report={'channels':{str(k):str(v.format()) for k,v in st.all_channels().items()},
            'shader':JS.evaluate('alg.shaders.shaderInstancesToObject()'),'export':config,
            'published_maps':[str(out/n) for n in names],
            'layers':[(n.get_name(),n.is_visible()) for n in L.get_root_layer_nodes(st)]}
    (WORK/'checks'/'painter_v05_channels.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'saved':P.file_path(),'export':str(result.status),'maps':[str(out/n) for n in names],'root_layers':38}

S.when_idle(export_saved,'_v05_ready.txt')
