"""Add only the owner's requested finish/contact refinements above the intact v02 stack."""
from pathlib import Path
import substance_painter.project as P
import substance_painter.textureset as T
import substance_painter.layerstack as L
import substance_painter.resource as R
import substance_painter.export as X
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
allowed={(WORK/'painter'/('padlock_'+v+'_textured.spp')).as_posix().casefold() for v in ('v02','v03')}
if not P.is_in_edition_state() or P.file_path().replace('\\','/').casefold() not in allowed:
    raise RuntimeError('Unexpected or unready project')
sets=T.all_texture_sets()
if [s.name() for s in sets]!=['Padlock']:raise RuntimeError('Unexpected texture set')
stack=sets[0].get_stack()
for node in L.get_root_layer_nodes(stack):
    if node.get_name().startswith('V03 ·'):L.delete_node(node)
assert len(L.get_root_layer_nodes(stack))==18,'Original v02 layers must remain intact'
marker=WORK/'sp_jobs'/'_v03_ready.txt';marker.unlink(missing_ok=True)

def bitmap(name):
    return R.import_project_resource((WORK/'textures'/'contact_v03'/name).as_posix(),R.Usage.TEXTURE).identifier()

def mask(layer,resource):
    S.mask_black(layer)
    node=L.insert_fill(L.InsertPosition.inside_node(layer,L.NodeStack.Mask))
    node.set_source(None,resource);node.set_projection_mode(L.ProjectionMode.UV)
    return node

def above(node):return L.InsertPosition.above_node(node)

top=L.get_root_layer_nodes(stack)[0]
n=S.fill('V03 · 01 Чёткий средний рельеф дужки',above(top),height='noise_grunge_map_013/grunge_map_013')
S.proc_params(n,'height',{'balance':.5,'contrast':.64});S.triplanar(n,5.0)
n.set_opacity(.035,S.CH.Height);S.only_meshes(n,['Shackle_forged_closed'])
n=S.fill('V03 · 02 Различия тона и блеска окислов дужки',above(n),color=(.40,.335,.285),rough=.58)
S.mask_proc(n,'noise_grunge_map_013/grunge_map_013',{'balance':.5,'contrast':.64},scale=5.0)
S.only_meshes(n,['Shackle_forged_closed']);S.lop(n,.40)
n=S.fill('V03 · 03 Сохранившийся полуматовый блеск краски',above(n),rough=.32)
finish=bitmap('paint_finish.png');mask(n,finish)
n=S.fill('V03 · 04 Неоднородно подстёртый лак',above(n),rough=.55)
base=mask(n,finish)
S.mask_proc(n,'noise_grunge_map_013/grunge_map_013',{'balance':.51,'contrast':.30},scale=1.2,
            above=base,blend=L.BlendingMode.Multiply)
S.lop(n,.75)
for title,image,rough in (
    ('05 Дужка — трение обеих ножек у входов','shackle.png',.30),
    ('06 Скважина — следы ключа до стали','keyhole.png',.28),
    ('07 Кромки корпуса — сколы и риски до стали','body_edges.png',.29),
):
    n=S.fill('V03 · '+title,above(n),color=(.67,.66,.63),metal=1.0,rough=rough,height=.5002)
    mask(n,bitmap(image))
print('V03_ADDITIONS_COMPLETE',len(L.get_root_layer_nodes(stack)))

def _save_v03_export():
    P.save_as((WORK/'painter'/'padlock_v03_textured.spp').as_posix(),P.ProjectSaveMode.Full)
    out=WORK/'textures'/'export_v03';out.mkdir(exist_ok=True)
    original=next(p for p in X.list_predefined_export_presets() if p.name=='glTF PBR Metal Roughness')
    maps=original.list_output_maps(stack)
    for item in maps:
        if 'normal' in item['fileName'].lower():
            item['parameters']['bitDepth']='16';item['parameters']['dithering']=False
    preset={'name':'Padlock v03 texture maps','maps':maps}
    result=X.export_project_textures({'exportShaderParams':False,'exportPath':out.as_posix(),
        'defaultExportPreset':preset['name'],'exportPresets':[preset],
        'exportList':[{'rootPath':'Padlock'}],
        'exportParameters':[{'parameters':{'fileFormat':'png','paddingAlgorithm':'infinite'}}]})
    if result.status!=X.ExportStatus.Success:raise RuntimeError(str(result))
    return {'saved':P.file_path(),'export':str(result.status),'layers':len(L.get_root_layer_nodes(stack))}

S.when_idle(_save_v03_export,'_v03_ready.txt')
