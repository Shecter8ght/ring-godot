"""Предметный свет и десять кадров высокого разрешения для гранаты v08."""
import bpy,hashlib,importlib.util,json,os,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'_asset_src/grenade_codex/texture_v08'
FILE=OUT/'Grenade_MkII_Studio_v08.blend'
RENDERS=OUT/'previews/studio'
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=module('v08_product_studio_base',ROOT/'tools/studio_grenade_codex.py')
M.OUT=OUT;M.FILE=FILE;M.RENDERS=RENDERS;M.T.MASTER=OUT/'Grenade_MkII_UCUPaint_v08.blend'
SHOTS=M.SHOTS
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'build'
def build():
    bpy.context.preferences.filepaths.save_version=0
    M.build()
    scene=bpy.context.scene
    # Тёплый основной свет и холодный скользящий контур показывают фактуру.
    bpy.data.objects['KEY • large warm softbox'].data.color=(1,.935,.85)
    bpy.data.objects['RIM • cool vertical strip'].data.color=(.72,.85,1)
    bpy.data.objects['FILL • restrained neutral'].data.energy=1.25
    scene.render.filepath='//previews/studio/01_hero.png'
    bpy.ops.wm.save_as_mainfile(filepath=str(FILE),relative_remap=False,compress=True)
    legacy=OUT/'checks/studio_setup_v06.json'
    data=json.loads(legacy.read_text(encoding='utf8'));data['file']=str(FILE);data['approved_geometry']='v07';data['textures']='v08'
    (OUT/'checks/studio_setup_v08.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
    print('V08_STUDIO_SAVED',FILE,flush=True)
def render(pilot=False):
    M.T.P.native();bpy.ops.wm.open_mainfile(filepath=str(FILE));scene=bpy.context.scene;M.configure(scene)
    scene.cycles.samples=128 if pilot else 512
    manifest=OUT/'checks/studio_renders_v08.json'
    rows=json.loads(manifest.read_text(encoding='utf8')) if manifest.is_file() and not pilot else []
    selected=sys.argv[sys.argv.index('--')+2:] if '--' in sys.argv else []
    for row in SHOTS:
        if selected and row[0] not in selected:continue
        name=row[0];path=RENDERS/(name+'.png')
        previous=next((r for r in rows if r['file']==path.name),None)
        if previous and path.is_file() and previous['samples']==512 and previous['sha256']==hashlib.file_digest(path.open('rb'),'sha256').hexdigest():continue
        M.set_shot(scene,row)
        if pilot:
            scene.render.resolution_percentage=45;scene.render.filepath=str(OUT/'previews'/('studio_pilot_'+name+'.png'))
        print('V08_RENDER_BEGIN',name,scene.cycles.samples,flush=True)
        bpy.ops.render.render(write_still=True)
        if not pilot:
            rows=[r for r in rows if r['file']!=path.name]
            rows.append({'file':path.name,'size':[row[4],row[5]],'samples':512,'sha256':hashlib.file_digest(path.open('rb'),'sha256').hexdigest(),'frame':row[6]})
            manifest.write_text(json.dumps(rows,indent=2),encoding='utf8')
        print('V08_RENDER_OK',name,flush=True)
if __name__=='__main__':
    if MODE=='build':build()
    elif MODE=='pilot':render(True)
    elif MODE=='render':render()
