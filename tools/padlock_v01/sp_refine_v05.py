"""New editable material on the accepted surface: authored masks and live anchors.

The useful v04 oxide foundation remains active in this separate SPP. Coverage is
refined from that preserved pattern with authored local corrections. Native
height-to-normal conversion is retained; a second conversion would amplify it.
"""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.layerstack as L
import substance_painter.textureset as T
import substance_painter.resource as R
import substance_painter.levels as V
import substance_painter.js as JS
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01');CH=T.ChannelType
assert P.is_in_edition_state() and P.file_path().endswith('padlock_v05_textured.spp') and not P.is_busy()
ts=T.all_texture_sets()[0];st=ts.get_stack();assert ts.name()=='Padlock'
MARKER=WORK/'sp_jobs'/'_v05_saved.txt';MARKER.unlink(missing_ok=True)
C={**S.CHAN,'coat':CH.CoatWeight,'coatrough':CH.CoatRoughness,'coatnormal':CH.CoatNormal,'coatcolor':CH.CoatColor}
resources={};anchors={}

def bitmap(name,source=False):
    key=(name,source)
    if key not in resources:
        path=WORK/'textures'/('authored_v05' if source else 'fields_v05')/name
        resources[key]=R.import_project_resource(path.as_posix(),R.Usage.TEXTURE).identifier()
    return resources[key]
def above(node):return L.InsertPosition.above_node(node)
def inside(group):return L.InsertPosition.inside_node(group,L.NodeStack.Substack)
def fill(title,pos,**values):
    n=L.insert_fill(pos);n.set_name(title);n.active_channels={C[k] for k in values}
    for name,value in values.items():
        source=S.rid(value,'u:procedural') if isinstance(value,str) else (value if isinstance(value,R.ResourceID) else S._val(value,data=name!='color'))
        n.set_source(C[name],source)
    if 'height' in values:n.set_blending_mode(L.BlendingMode.Normal,CH.Height)
    return n
def mask_bitmap(node,name):
    S.mask_black(node);f=L.insert_fill(L.InsertPosition.inside_node(node,L.NodeStack.Mask))
    f.set_source(None,bitmap(name));f.set_projection_mode(L.ProjectionMode.UV);return f
def mask_anchor(node,anchor,channel=None):
    S.mask_black(node);f=L.insert_fill(L.InsertPosition.inside_node(node,L.NodeStack.Mask))
    ref=f.set_source(None,anchor)
    if channel is not None:ref.referenced_channel=channel
    return f
def multiply_bitmap(node,base,name,source=False,scale=None):
    f=L.insert_fill(above(base));f.set_source(None,bitmap(name,source));f.set_blending_mode(L.BlendingMode.Multiply)
    if scale is None:f.set_projection_mode(L.ProjectionMode.UV)
    else:S.triplanar(f,scale)
    return f
def levels(node,base,lo=0.,hi=1.,outlo=0.,outhi=1.):
    f=L.insert_levels_effect(above(base));f.set_parameters(V.LevelsParamsMono(input_min=lo,input_max=hi,output_min=outlo,output_max=outhi,clamp=True));return f
def filter_on(node,base,name,params):
    f=L.insert_filter_effect(above(base),S.rid(name,'u:filter'));f.get_source().set_parameters(params);return f
def anchor_after(base,name):
    a=L.insert_anchor_point_effect(above(base),name);anchors[name]=a;return a
def group(title,pos):
    g=L.insert_group(pos);g.set_name(title);return g

with L.ScopedModification('Padlock v05 — authored wear, enamel edges and protected deposits'):
    for node in L.get_root_layer_nodes(st):
        if node.get_name().startswith('V05 ·'):L.delete_node(node)
    old=L.get_root_layer_nodes(st);assert len(old)==37
    foundation=('01 Стальная','02 Плотная','03 Тёплые','03a Более','04 Питтинг','05 Минеральные','06 Микрофактура','06a Точки','09b Микропоры','V03 · 01','V03 · 02')
    for node in old:node.set_visible(node.get_name().startswith(foundation))
    st.get_channel(CH.Height).edit(channel_format=T.ChannelFormat.L32F)
    JS.evaluate('alg.shaders.setParameters(0, {"coatEnabled":true,"coatIoR":1.5})')
    root=group('V05 · АВТОРСКАЯ ОТДЕЛКА',above(old[0]))
    finish=group('01 · Основание, покрытие и следы контакта',inside(root))
    n=fill('01 Каналы лака и его слабая независимая волнистость',inside(finish),coat=0.,coatrough=.26,coatnormal=bitmap('coat_film_normal.png'),coatcolor=(1.,1.,1.))
    n.set_projection_mode(L.ProjectionMode.UV)
    n=fill('02 Сухой коричневый оксид',above(n),color=(.33,.275,.235),metal=0.,rough=.77,height=.5004)
    n.set_visible(False)
    n=fill('03 Светлые участки патины по образцу',above(n),color=(.43,.36,.295),rough=.82)
    m=mask_bitmap(n,'oxide_tone.png');levels(n,m,.30,.72);S.lop(n,.15)
    n=fill('04 Более тёмные и прохладные участки окислов',above(n),color=(.265,.25,.225),rough=.70)
    m=mask_bitmap(n,'oxide_tone.png');levels(n,m,.28,.70,1.,0.);S.lop(n,.10)
    n=fill('05 Мелкий нерегулярный питтинг',above(n),color=(.26,.23,.20),rough=.87,height=.4978)
    S.mask_black(n);m=L.insert_fill(L.InsertPosition.inside_node(n,L.NodeStack.Mask));m.set_source(None,bitmap('pitting.png',True));S.triplanar(m,2.8)
    n.set_opacity(.60,CH.Height);n.set_opacity(.28,CH.BaseColor);n.set_opacity(.42,CH.SpecularRoughness)
    n.set_visible(False)
    n=fill('06 Тонкое зерно оксида',above(n),rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,2.2);n.set_blending_mode(L.BlendingMode.Overlay,CH.SpecularRoughness)
    n.set_opacity(.10,CH.SpecularRoughness);n.set_opacity(.0008,CH.Height)
    n.set_visible(False)
    n=fill('07 Дужка — тёмный металл под тонким окислом',above(n),color=(.275,.25,.22),rough=.67)
    S.only_meshes(n,['Shackle_forged_closed']);n.set_opacity(.38,CH.BaseColor);n.set_opacity(.55,CH.SpecularRoughness)
    n=fill('08 Дужка — различия патины',above(n),color=(.37,.32,.265),rough=.57)
    mask_bitmap(n,'oxide_tone.png');S.only_meshes(n,['Shackle_forged_closed']);S.lop(n,.17)
    n=fill('09 Голубая эмаль — сохранённая основа и авторские правки',above(n),color=(.43,.565,.59),metal=0.,rough=.27,
           height=bitmap('enamel_brush_height.png'),coat=.85,coatrough=.17)
    n.set_projection_mode(L.ProjectionMode.UV)
    m=mask_bitmap(n,'enamel_coverage.png');coverage=anchor_after(m,'V05 Enamel Coverage')
    n=fill('10 Пятна выцветания в сохранившейся эмали',above(n),color=(.745,.765,.775),rough=.40)
    n.set_blending_mode(L.BlendingMode.SoftLight,CH.BaseColor)
    m=mask_anchor(n,coverage);multiply_bitmap(n,m,'varnish_wear.png');n.set_opacity(.24,CH.BaseColor);n.set_opacity(.45,CH.SpecularRoughness)
    n=fill('11 Затёртые матовые участки лака',above(n),rough=.45,coat=.45,coatrough=.38)
    m=mask_anchor(n,coverage);multiply_bitmap(n,m,'varnish_wear.png');S.lop(n,.86)
    n=fill('12 Очень мелкая фактура эмали',above(n),rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,2.6);mask_anchor(n,coverage);n.set_blending_mode(L.BlendingMode.Overlay,CH.SpecularRoughness)
    n.set_opacity(.07,CH.SpecularRoughness);n.set_opacity(.00022,CH.Height)
    n=fill('13 Приподнятая губа отслаивающейся краски',above(n),color=(.40,.565,.60),rough=.30,height=.5286)
    m=mask_anchor(n,coverage);m=filter_on(n,m,'highpass/highpass',{'Radius':.08})
    m=levels(n,m,.515,.70);m=filter_on(n,m,'warp/warp',{'intensity':.018,'$randomseed':505,'noise_scale':1.4})
    clip=L.insert_fill(above(m));clip.set_source(None,coverage);clip.set_blending_mode(L.BlendingMode.Multiply)
    n.set_opacity(.25,CH.Height);n.set_opacity(.10,CH.BaseColor)
    n=fill('14 Подплёночные окислы у разрыва покрытия',above(n),color=(.28,.225,.175),rough=.86)
    m=mask_anchor(n,coverage);m=filter_on(n,m,'highpass/highpass',{'Radius':.18})
    m=levels(n,m,.32,.49,1.,0.);m=filter_on(n,m,'warp/warp',{'intensity':.025,'$randomseed':506,'noise_scale':1.8})
    clip=L.insert_fill(above(m));ref=clip.set_source(None,coverage);ref.set_levels(V.LevelsParamsMono(output_min=1.,output_max=0.))
    clip.set_blending_mode(L.BlendingMode.Multiply);S.lop(n,.24)
    n=fill('15 Редкие подплёночные очаги',above(n),color=(.31,.425,.44),rough=.48,height=.5310)
    m=mask_anchor(n,coverage);multiply_bitmap(n,m,'blisters.png',True,3.0)
    n.set_opacity(.18,CH.Height);n.set_opacity(.06,CH.BaseColor);n.set_opacity(.15,CH.SpecularRoughness)
    n=fill('16 Сталь на коротких фактических контактах',above(n),color=(.64,.645,.62),metal=1.,rough=.235,height=.5125,coat=0.)
    n.set_opacity(.18,CH.Height)
    m=mask_bitmap(n,'contact_steel.png');contact=anchor_after(m,'V05 Bare Contact Steel')
    n=fill('17 Неодинаковый блеск протёртой стали',above(n),rough='noise_gaussian_noise/gaussian_noise',height='noise_gaussian_noise/gaussian_noise')
    S.triplanar(n,4.2);mask_anchor(n,contact);n.set_blending_mode(L.BlendingMode.Overlay,CH.SpecularRoughness)
    n.set_opacity(.19,CH.SpecularRoughness);n.set_opacity(.00022,CH.Height)
    n=fill('18 Забитые неровные раковины возле скважины',above(n),color=(.33,.325,.295),metal=1.,rough=.39,height=.4995,coat=0.)
    m=mask_bitmap(n,'key_pits.png');pits=anchor_after(m,'V05 Key Impacts')
    n=fill('19 Разорванные края выбоин',above(n),color=(.62,.62,.585),metal=1.,rough=.24,height=.511,coat=0.)
    m=mask_anchor(n,pits);m=filter_on(n,m,'highpass/highpass',{'Radius':.05});m=levels(n,m,.53,.78)
    filter_on(n,m,'warp/warp',{'intensity':.025,'$randomseed':509,'noise_scale':2.3});S.lop(n,.60)
    n=fill('20 Короткие направленные риски ключа',above(n),color=(.62,.63,.60),metal=1.,rough=.22,height=.4990,coat=0.)
    mask_bitmap(n,'key_scratches.png')
    n=fill('21 Условное стёртое заводское клеймо',above(n),color=(.23,.205,.175),rough=.72,height=.4990)
    S.mask_black(n);m=L.insert_fill(L.InsertPosition.inside_node(n,L.NodeStack.Mask))
    m.set_source(None,R.import_project_resource((WORK/'textures'/'padlock_stamp_mask.png').as_posix(),R.Usage.TEXTURE).identifier())
    S.lop(n,.60)
    # A real pass-through paint layer is required: Painter 12.1 drops folder
    # content effects/anchors when reopening, even though insertion succeeds.
    adjust=L.insert_paint(above(n));adjust.set_name('21a Общая доводка — Pass Through')
    adjust.active_channels=set(st.all_channels())
    for channel in st.all_channels():adjust.set_blending_mode(L.BlendingMode.Passthrough,channel)
    sharp=L.insert_filter_effect(L.InsertPosition.inside_node(adjust,L.NodeStack.Content),S.rid('sharpen/sharpen','u:filter'))
    sharp.get_source().set_parameters({'intensity':.28})
    for channel in st.all_channels():sharp.set_opacity(.22 if channel in (CH.BaseColor,CH.SpecularRoughness) else 0.,channel)
    surface=L.insert_anchor_point_effect(above(sharp),'V05 Finished Surface Relief');anchors['V05 Finished Surface Relief']=surface
    deposits=group('02 · Защищённые отложения поверх отделки',above(finish))
    n=fill('22 Грязь в стыках и у крепежа — видит новый рельеф',inside(deposits),color=(.205,.185,.15),metal=0.,rough=.92,coat=0.)
    m=mask_bitmap(n,'corner_grime.png')
    g=S.mask_generator(n,'mg_dirt/mg_dirt',{'dirt_level':.58,'dirt_contrast':.56,'grunge_amount':.30,
                      'Use_Triplanar':1,'Grunge_Scale':3,'Micro_Details_Micro_Normal':0,'Micro_Details_Micro_Height':1,
                      'Micro_Details_Curvature_Intensity':.40},above=m)
    ref=g.get_source().set_source('micro_height',surface);ref.referenced_channel=CH.Height
    g.set_blending_mode(L.BlendingMode.Multiply);S.lop(n,.82)
    n=fill('23 Редкая осевшая пыль',above(n),color=(.42,.39,.335),metal=0.,rough=.95,coat=0.)
    m=mask_bitmap(n,'corner_dust.png');multiply_bitmap(n,m,'dust.png',True,4.0);S.lop(n,.68)
    root.set_collapsed(False);finish.set_collapsed(True);deposits.set_collapsed(True)

def save_native():
    P.save_as((WORK/'painter'/'padlock_v05_textured.spp').as_posix(),P.ProjectSaveMode.Full)
    def walk(nodes):
        out=[]
        for n in nodes:
            row={'name':n.get_name(),'type':type(n).__name__,'visible':n.is_visible()}
            if isinstance(n,L.GroupLayerNode):row['children']=walk(n.sub_layers())
            if isinstance(n,L.LayerNode):row['effects']=[{'name':e.get_name(),'type':type(e).__name__} for e in n.content_effects()+n.mask_effects()]
            out.append(row)
        return out
    report={'saved':P.file_path(),'root_layers':walk(L.get_root_layer_nodes(st)),
            'anchors':list(anchors),'height_encoding':{'midpoint':.5,'storage':'L32F','conversion':'Native Painter Height + Normal_OpenGL',
                  'note':'Original oxide foundation preserved; no duplicate Height To Normal filter. Layout dimensions are millimetres.'},
            'original_v04_layers_retained':37,'foundation_preserved':list(foundation),'geometry_changed':False}
    (WORK/'checks'/'v05_native_layers.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'saved':P.file_path(),'anchors':list(anchors),'old_layers_retained':37}
S.when_idle(save_native,'_v05_saved.txt')
print('V05_NATIVE_MATERIAL_BUILT')
