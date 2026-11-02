"""Export working100 variants and an OFF control to verify the unchanged factory."""
import substance_painter.project as P
import substance_painter.textureset as TS
import substance_painter.layerstack as L
import pathlib,json,os
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
WORK=pathlib.Path('E:/Games/RING-godot/_asset_src/dozor/wear')
assert pathlib.Path(P.file_path()).resolve()==(OUT/'painter/DOZOR_working100_v01.spp').resolve()
marker=pathlib.Path(os.environ['SP_BRIDGE_DIR'])/'_wear_exports_done.txt';marker.unlink(missing_ok=True)
nodes={t.name():L.get_root_layer_nodes(t.get_stack()) for t in TS.all_texture_sets()}
markings={n.get_name().split(' • ')[1]:n for n in nodes['DOZOR_F1'] if n.get_name().startswith('Маркировка • ')}
groups=[n for ns in nodes.values() for n in ns if n.get_name()=='Этап 2 — износ']
queue=[('F1',True),('F1M',True),('F1S',True),('P',True),('LENS',True),('F1',False),('P',False)]
export_log=[]
def next_variant():
    if not queue:
        for g in groups:g.set_visible(True)
        for v,n in markings.items():n.set_visible(v=='F1')
        def save_final():
            sp_finish.save_as(str(OUT/'painter/DOZOR_working100_v01.spp'))
            (OUT/'checks/working100-export.json').write_text(json.dumps(export_log,ensure_ascii=False,indent=2),encoding='utf-8')
            sp_finish.mark('_wear_exports_done.txt','OK '+str(len(export_log))+' exports')
        P.execute_when_not_busy(save_final);return
    variant,on=queue.pop(0)
    name='DOZOR_F1' if variant in ('F1','F1M','F1S') else 'DOZOR_P' if variant=='P' else 'DOZOR_LENS'
    for g in groups:g.set_visible(on)
    if name=='DOZOR_F1':
        for v,n in markings.items():n.set_visible(v==variant)
    folder=(OUT/'textures/working100'/variant) if on else (WORK/'off_control'/variant)
    folder.mkdir(parents=True,exist_ok=True)
    def export_current():
        status,files=sp_lib.export(str(folder),name)
        export_log.append({'variant':variant,'wear_on':on,'set':name,'status':str(status),'files':{str(k):[str(p) for p in v] for k,v in files.items()}})
        if 'Success' not in str(status):raise RuntimeError(str(status))
        for p in folder.iterdir():
            assert p.resolve().is_relative_to(folder.resolve())
            if p.is_file() and p.stem in ('Untitled','DOZOR_factory_v01','DOZOR_working100_v01') and p.suffix.lower() in ('.gltf','.glb','.bin'):p.unlink()
        next_variant()
    P.execute_when_not_busy(export_current)
next_variant()
print('Seven-export sequence queued: five working variants, two OFF controls')
