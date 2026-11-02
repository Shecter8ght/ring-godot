"""Export each marking variant from native Painter layers, then restore F1 and save."""
import substance_painter.project as P
import substance_painter.textureset as TS
import pathlib,json,os
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
(pathlib.Path(os.environ['SP_BRIDGE_DIR'])/'_dozor_exports_done.txt').unlink(missing_ok=True)
queue=['F1','F1M','F1S','P','LENS']
export_log=[]
def next_variant():
    if not queue:
        for v,layer in layers['DOZOR_F1'].items():layer.set_visible(v=='F1')
        def save_final():
            sp_finish.save_as(str(OUT/'painter/DOZOR_factory_v01.spp'))
            (OUT/'checks/painter-export.json').write_text(json.dumps(export_log,ensure_ascii=False,indent=2),encoding='utf-8')
            sp_finish.mark('_dozor_exports_done.txt','OK '+str(len(export_log))+' texture sets exported')
        P.execute_when_not_busy(save_final)
        return
    variant=queue.pop(0)
    name='DOZOR_F1' if variant in ('F1','F1M','F1S') else 'DOZOR_P' if variant=='P' else 'DOZOR_LENS'
    if name=='DOZOR_F1':
        for v,layer in layers[name].items():layer.set_visible(v==variant)
    folder=OUT/'textures/factory'/variant;folder.mkdir(parents=True,exist_ok=True)
    def export_current():
        status,files=sp_lib.export(str(folder),name)
        export_log.append({'variant':variant,'set':name,'status':str(status),'files':{str(k):[str(p) for p in v] for k,v in files.items()}})
        if 'Success' not in str(status):raise RuntimeError(str(status))
        # glTF preset also emits a temporary mesh. These are authoring side products only.
        for p in folder.iterdir():
            assert p.resolve().is_relative_to(folder.resolve())
            if p.is_file() and p.stem in ('Untitled','DOZOR_factory_v01') and p.suffix.lower() in ('.gltf','.glb','.bin'):p.unlink()
        next_variant()
    P.execute_when_not_busy(export_current)
next_variant()
print('Export sequence queued')
