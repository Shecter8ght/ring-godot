"""Нативные редактируемые слои Painter: старая голубая краска и коррозия замка."""
from pathlib import Path
import substance_painter.layerstack as L
import substance_painter.resource as R
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')

def bitmap(name):
    path=WORK/'textures'/name
    return R.import_project_resource(str(path).replace('\\','/'),R.Usage.TEXTURE).identifier()

def mask(layer,image,tri=False,scale=1.0):
    S.mask_black(layer)
    node=L.insert_fill(L.InsertPosition.inside_node(layer,L.NodeStack.Mask))
    node.set_source(None,image)
    if tri:S.triplanar(node,scale)
    else:node.set_projection_mode(L.ProjectionMode.UV)
    return node

def above(layer):return L.InsertPosition.above_node(layer)

def apply(stack):
    S.clear(stack)
    coverage=bitmap('padlock_paint_mask.png')
    pits=bitmap('sources/pitting.png')
    fine=bitmap('sources/fine_pitting.png')
    stamp=bitmap('padlock_stamp_mask.png')
    n=S.fill('01 Стальная основа',L.InsertPosition.from_textureset_stack(stack),
             color=(.40,.38,.35),metal=1.0,rough=.63,height=.5)
    n=S.fill('02 Плотная тёмная коррозия',above(n),color=(.34,.285,.26),metal=0.0,rough=.76,height=.5)
    n=S.fill('03 Тёплые и холодные участки окислов',above(n),color=(.43,.355,.30),metal=0.0,rough=.82)
    S.mask_proc(n,'noise_grunge_map_013/grunge_map_013',{'balance':.52,'contrast':.55},scale=1.3)
    S.lop(n,.65)
    n=S.fill('03a Более тёмные окислы дужки',above(n),color=(.26,.235,.21),rough=.82)
    S.only_meshes(n,['Shackle_forged_closed'])
    n=S.fill('04 Питтинг — альфа из библиотеки владельца',above(n),color=(.25,.215,.20),rough=.91,height=.44)
    mask(n,pits,True,2.5);S.lop(n,.70)
    n=S.fill('05 Минеральные зёрна и выступающие окислы',above(n),color=(.50,.425,.35),rough=.83,metal=0.0,height=.54)
    mask(n,fine,True,3.5);S.lop(n,.65)
    n=S.fill('06 Микрофактура металла',above(n),rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,1.2)
    n.set_blending_mode(L.BlendingMode.Overlay,S.CH.SpecularRoughness)
    n.set_opacity(.24,S.CH.SpecularRoughness);n.set_opacity(.025,S.CH.Height)
    n=S.fill('06a Точки открытой стали между окислами',above(n),color=(.58,.54,.49),metal=1.0,rough=.38,height=.498)
    mask(n,fine,True,6.0);S.lop(n,.48)
    n=S.fill('07 Сохранившаяся голубая краска',above(n),color=(.39,.56,.59),metal=0.0,rough=.64,height=.53)
    mask(n,coverage)
    n=S.fill('08 Неравномерное выцветание краски',above(n),color=(.56,.70,.70),rough=.77)
    base=mask(n,coverage)
    S.mask_proc(n,'noise_grunge_map_013/grunge_map_013',{'balance':.50,'contrast':.22},scale=1.1,above=base,blend=L.BlendingMode.Multiply)
    S.lop(n,.24)
    n=S.fill('09 Мелкая фактура слоя краски',above(n),rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,1.0);mask(n,coverage)
    n.set_blending_mode(L.BlendingMode.Overlay,S.CH.SpecularRoughness)
    n.set_opacity(.13,S.CH.SpecularRoughness);n.set_opacity(.006,S.CH.Height)
    n=S.fill('09a Мелкие окислы поверх старого покрытия',above(n),color=(.54,.49,.42),rough=.87,metal=0.0,height=.54)
    mask(n,fine,True,7.0);S.lop(n,.48)
    n=S.fill('09b Микропоры и неоднородный блеск',above(n),color='noise_gaussian_noise/gaussian_noise',rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,2.0)
    n.set_blending_mode(L.BlendingMode.SoftLight,S.CH.BaseColor);n.set_opacity(.16,S.CH.BaseColor)
    n.set_blending_mode(L.BlendingMode.Overlay,S.CH.SpecularRoughness);n.set_opacity(.15,S.CH.SpecularRoughness)
    n.set_opacity(.014,S.CH.Height)
    n=S.fill('09c Стёртое условное клеймо — без читаемой марки',above(n),color=(.20,.18,.16),rough=.83,height=.465)
    mask(n,stamp);S.lop(n,.72)
    n=S.fill('10 Коррозия на открытых кромках',above(n),color=(.39,.335,.285),metal=0.0,rough=.82,height=.50002)
    S.mask_generator(n,'mg_metal_edge_wear/mg_metal_edge_wear',
                     {'Wear_Level':.085,'Wear_Contrast':.75,'Grunge_Amount':.8,'grunge_scale':5,
                      'Use_Triplanar':1,'Edges_Smoothness':.5,'Ambient_Occlusion_Masking':.5,'Curvature_Weight':1.0})
    n=S.fill('11 Короткие старые риски',above(n),color=(.43,.395,.35),rough=.72,height=.4998)
    S.mask_proc(n,'grunge_scratches_fine/grunge_scratches_fine',{'invert':0,'balance':.36,'contrast':.55},scale=1.7)
    S.lop(n,.16)
    n=S.fill('12 Редкие открытые металлические контакты',above(n),color=(.35,.33,.30),metal=1.0,rough=.70,height=.50001)
    S.mask_generator(n,'mg_metal_edge_wear/mg_metal_edge_wear',
                     {'Wear_Level':.022,'Wear_Contrast':.88,'Grunge_Amount':.85,'grunge_scale':7,
                      'Use_Triplanar':1,'Edges_Smoothness':.4,'Ambient_Occlusion_Masking':.7,'Curvature_Weight':1.0})
    S.lop(n,.25)
    n=S.fill('13 Сухие отложения в защищённых щелях',above(n),color=(.285,.26,.225),rough=.92,metal=0.0)
    S.mask_generator(n,'mg_dirt/mg_dirt',{'dirt_level':.24,'dirt_contrast':.85,'grunge_amount':.55,
                     'Grunge_Scale':4,'Use_Triplanar':1,'edges_masking':.8})
    S.lop(n,.45)
    return n
