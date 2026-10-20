"""Нативные слои UCUPaint: фотоструктура ткани и местный износ одежды."""
import importlib
import json
import math
from pathlib import Path
import heapq
import io
from contextlib import redirect_stdout
import sys
import bpy
import numpy as np
from mathutils import Color, Vector
import m02_custom_clothes as G
import wardrobe_geometry as W

ROOT=Path(__file__).resolve().parents[2]
MATERIALS=ROOT/'_asset_src/npc_wardrobe/materials'
U=None

SCAN={'jersey':'jersey_melange','plaid':'stretch_poplin','work_blue':'stretch_poplin',
      'work_grey':'stretch_poplin','nylon_olive':'bi_stretch','track_red':'bi_stretch',
      'combat_knit':'jersey_melange','field_olive':'stretch_poplin','cargo_olive':'stretch_poplin',
      'denim':'denim_fabric_03','leather_brown':'brown_leather','leather_field':'brown_leather',
      'suede':'brown_leather','trek_mesh':'jersey_melange','repair_olive':'stretch_poplin',
      'rib_dark':'jersey_melange','leather_black':'brown_leather'}


def sync(entity,name,value):
    if name=='override_color': value=Color(value)
    setattr(entity,name,value)
    U.common.set_entity_prop_value(entity,name,value)
    actual=U.common.get_entity_prop_value(entity,name)
    a=[actual] if isinstance(actual,(float,int)) else list(actual)
    b=[value] if isinstance(value,(float,int)) else list(value)
    assert all(abs(x-y)<1e-5 for x,y in zip(a,b)),(name,a,b)


def layer(tree,name,source='COLOR',color=None,rough=None,height=None,image=None,amount=1.,blend='MIX',distance=.00008):
    tree.yp.halt_update=True
    result=U.Layer.add_new_layer(tree,name,source,-1,blend,'OVERLAY','BUMP_MAP',
        'UV' if image else 'Object','UV_Fabric_Metres',image=image,use_designated_idx=True,designated_index=0)
    tree.yp.halt_update=False
    values={'Color':color,'Roughness':rough,'Metallic':None,'Normal':height}
    for root,ch in zip(tree.yp.channels,result.channels):
        value=values[root.name]
        ch.enable=value is not None
        if value is None: continue
        if value!='source':
            ch.override=True;ch.override_type='DEFAULT'
            sync(ch,'override_color' if root.type=='RGB' else 'override_value',value)
        if root.type=='NORMAL':
            sync(ch,'bump_distance',distance)
            sync(ch,'bump_midlevel',.5)
    sync(result,'intensity_value',amount)
    return result


def scale_image(entity,value):
    entity.enable_uniform_scale=False
    sync(entity,'scale',Vector((value,value,value)))


def masked(layer_,attribute):
    return U.Mask.add_new_mask(layer_,attribute,'VCOL','Object','UV_Fabric_Metres',vcol_name=attribute)


def fade_noise(layer_,scale=30):
    mask=U.Mask.add_new_mask(layer_,'Irregular contact boundary','NOISE','Object','UV_Fabric_Metres')
    U.common.get_mask_source(mask).inputs['Scale'].default_value=scale
    return mask


def boundary_distances(obj):
    mesh=obj.data
    adjacent=[[] for _ in mesh.vertices]
    edge_faces={tuple(sorted(edge.vertices)):0 for edge in mesh.edges}
    for face in mesh.polygons:
        for a,b in zip(face.vertices,list(face.vertices[1:])+[face.vertices[0]]):
            edge_faces[tuple(sorted((a,b)))]+=1
    distances=[1e6]*len(mesh.vertices)
    heap=[]
    for edge in mesh.edges:
        a,b=edge.vertices
        length=(mesh.vertices[a].co-mesh.vertices[b].co).length
        adjacent[a].append((b,length));adjacent[b].append((a,length))
        if edge_faces[tuple(sorted((a,b)))]==1:
            for index in [a,b]:
                distances[index]=0;heapq.heappush(heap,(0,index))
    while heap:
        d,i=heapq.heappop(heap)
        if d!=distances[i] or d>.025: continue
        for j,step in adjacent[i]:
            nd=d+step
            if nd<distances[j]: distances[j]=nd;heapq.heappush(heap,(nd,j))
    return distances


def attributes(obj,code):
    mesh=obj.data
    distances=boundary_distances(obj)
    attrs={name:mesh.color_attributes.get(name) or mesh.color_attributes.new(name,'FLOAT_COLOR','CORNER')
           for name in ['WardrobeEdge','WardrobeWear','WardrobeDust','WardrobeContact']}
    values={key:[] for key in attrs}
    cfg=W.TOPS.get(code) or W.PANTS.get(code) or W.SHOES.get(code)
    for index,vertex in enumerate(mesh.vertices):
        x,y,z=vertex.co
        front=G.smooth(.01,-.075,y)
        irregular=.60+.20*math.sin(91*x+57*z+11*y)+.12*math.sin(157*z-89*x)
        edge=math.exp(-(distances[index]/.0038)**2) if distances[index]<.025 else 0
        if code.startswith('T'):
            wear=.17*edge+.26*math.exp(-((abs(x)-.46)/.055)**2)*math.exp(-((z-1.45)/.05)**2)
            dust=(1-G.smooth(cfg['length']+.015,cfg['length']+.10,z))*.60
            contact=math.exp(-((z-1.52)/.03)**2)*math.exp(-(x/.10)**2)
        elif code.startswith('P'):
            knee=math.exp(-((z-.52)/.085)**2)*front
            thighs=.45*math.exp(-((z-.795)/.105)**2)*front
            whiskers=.28*math.exp(-((z-(.94-.35*abs(x)))/.05)**2)*(.5+.5*math.sin(235*z+34*abs(x)))**2*front
            seat=.35*math.exp(-((z-.93)/.07)**2)*(1-front)
            wear=G.clamp(.20*edge+.65*knee+thighs+whiskers+seat)
            dust=(1-G.smooth(cfg['hem']+.025,cfg['hem']+.16,z))*.78+.13*knee
            contact=.18*edge+.24*math.exp(-((z-1.035)/.025)**2)
        elif code.startswith('B'):
            wear=.12*edge+.13*math.exp(-((z-1.66)/.018)**2)*front
            dust=.18*(1-G.smooth(1.49,1.54,z))
            contact=.48*math.exp(-((z-1.53)/.034)**2)+.25*math.exp(-((z-1.61)/.022)**2)*front
        else:
            toe=G.smooth(-.11,-.215,y)*(1-G.smooth(.065,.12,z))
            wear=.30*edge+.45*toe
            dust=(1-G.smooth(.025,.095,z))*(.40+.32*G.smooth(-.04,-.22,y))
            contact=.20*edge+.35*G.smooth(-.105,-.185,y)*math.exp(-((z-.060)/.024)**2)
        values['WardrobeEdge'].append(G.clamp(edge*irregular))
        values['WardrobeWear'].append(G.clamp(wear*irregular))
        values['WardrobeDust'].append(G.clamp(dust*irregular))
        values['WardrobeContact'].append(G.clamp(contact*irregular))
    for name,attribute in attrs.items():
        flat=np.array([(*([values[name][loop.vertex_index]]*3),1) for loop in mesh.loops],dtype=np.float32).ravel()
        attribute.data.foreach_set('color',flat)


def plaid_image(out):
    # Собственный математический раппорт клетки; CC0-фото волокон отдельным слоем.
    size=1024
    yy,xx=np.mgrid[0:size,0:size]/size
    phase_x=(xx*4)%1;phase_y=(yy*4)%1
    fabric=np.zeros((size,size,4),dtype=np.float32)
    fabric[:,:,:3]=(.31,.355,.385)
    fabric[:,:,3]=1
    def over(mask,color,amount):
        a=(mask*amount)[:,:,None]
        fabric[:,:,:3]=fabric[:,:,:3]*(1-a)+np.array(color)[None,None,:]*a
    over((abs(phase_x-.5)<.16).astype(float),(.48,.425,.335),.40)
    over((abs(phase_y-.5)<.16).astype(float),(.48,.425,.335),.40)
    for phase in [phase_x,phase_y]:
        over((abs(phase-.07)<.038).astype(float),(.15,.195,.23),.65)
        over((abs(phase-.32)<.010).astype(float),(.61,.55,.43),.55)
        over((abs(phase-.72)<.012).astype(float),(.21,.255,.28),.55)
    image=bpy.data.images.new('RING | original blue grey plaid',width=size,height=size,alpha=True)
    image.colorspace_settings.name='sRGB'
    rgb=fabric[:,:,:3]
    fabric[:,:,:3]=np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4)
    image.pixels.foreach_set(fabric.ravel())
    image.filepath_raw=str(out/'original_plaid_repeat.png');image.file_format='PNG';image.save()
    image.pack()
    return image


def _apply(items,mats,out):
    global U
    U=importlib.import_module('bl_ext.blender_org.ucupaint')
    assert U.common.get_current_version_str()=='2.4.9'
    sources=json.loads((MATERIALS/'sources.json').read_text(encoding='utf-8'))
    by_id={item['id']:item for item in sources}
    users={}
    for code,col in items.items():
        for obj in col.objects:
            if obj.type!='MESH': continue
            attributes(obj,code[:3])
            for slot in obj.material_slots:
                if slot.material: users.setdefault(slot.material,[]).append(obj)
    plaid=plaid_image(out) if 'T01' in items else None
    report=[]
    for key,mat in mats.items():
        if mat not in users: continue
        print('WARDROBE_PAINT '+key,file=sys.__stdout__,flush=True)
        target=users[mat][0]
        G.activate(target)
        target.active_material_index=next(i for i,slot in enumerate(target.material_slots) if slot.material==mat)
        bsdf=next(node for node in mat.node_tree.nodes if node.type=='BSDF_PRINCIPLED')
        base=tuple(mat.diffuse_color[:3])
        bsdf.inputs['IOR'].default_value=1.46
        bsdf.inputs['Specular IOR Level'].default_value=.28
        bsdf.inputs['Sheen Weight'].default_value=.16 if key in SCAN and not key.startswith('leather') else .03
        bsdf.inputs['Sheen Roughness'].default_value=.70
        bpy.ops.wm.y_quick_ypaint_node_setup(tree_name='RING | '+key+' | editable layers',
            color=True,metallic=True,roughness=True,normal=True,ao=False,
            switch_to_material_view=False,target_bsdf_name=bsdf.name)
        group=next(node for node in mat.node_tree.nodes if node.type=='GROUP' and getattr(node.node_tree,'yp',None) and node.node_tree.yp.is_ypaint_node)
        tree=group.node_tree
        normal=next(channel for channel in tree.yp.channels if channel.type=='NORMAL')
        normal.enable_smooth_bump=False;normal.main_uv='UV_Fabric_Metres'
        leather=key.startswith('leather') or key=='suede'
        rough=.56 if leather else .81 if key=='rubber' else .72
        base_layer=layer(tree,'01 | material dye and base roughness',color=base,rough=rough)
        if key=='hardware':
            channel=next(channel for root,channel in zip(tree.yp.channels,base_layer.channels) if root.name=='Metallic')
            channel.enable=True;channel.override=True;channel.override_type='DEFAULT';sync(channel,'override_value',.72)
        if key=='plaid':
            ly=layer(tree,'02 | original woven check repeat',source='IMAGE',image=plaid,color='source',amount=.96)
            scale_image(ly,1/.24)
        if key in SCAN:
            info=by_id[SCAN[key]]
            scale=1000/info['dimensions'][0]
            files={entry['kind']:entry for entry in info['files']}
            diffuse=bpy.data.images.load(files['diff']['file'],check_existing=True);diffuse.colorspace_settings.name='sRGB'
            ly=layer(tree,'03 | CC0 photographed fibre colour',source='IMAGE',image=diffuse,color='source',amount=.30,blend='MULTIPLY')
            scale_image(ly,scale)
            importlib.import_module(U.__name__+'.Modifier').add_new_modifier(ly,'HUE_SATURATION')
            modifier=ly.modifiers[0]
            huesat=U.common.get_mod_tree(ly).nodes[modifier.huesat]
            huesat.inputs['Saturation'].default_value=.12
            huesat.inputs['Value'].default_value=2.0
            height=bpy.data.images.load(files['disp']['file'],check_existing=True);height.colorspace_settings.name='Non-Color'
            ly=layer(tree,'04 | photographed material microrelief',source='IMAGE',image=height,height='source',distance=.00014 if leather else .000075)
            scale_image(ly,scale)
            roughness=bpy.data.images.load(files['rough']['file'],check_existing=True);roughness.colorspace_settings.name='Non-Color'
            ly=layer(tree,'05 | photographed roughness variation',source='IMAGE',image=roughness,rough='source',amount=.32)
            scale_image(ly,scale)
        else:
            ly=layer(tree,'04 | moulded or spun microstructure',source='NOISE',height='source',distance=.00005,amount=.5)
            source=U.common.get_layer_source(ly);source.inputs['Scale'].default_value=1800
        worn=(.23,.27,.29) if key=='denim' else tuple(min(.65,component*1.60+.050) for component in base)
        ly=layer(tree,'06 | local contact fading',color=worn,rough=.53 if leather else .68,amount=.85 if key=='denim' else .48)
        masked(ly,'WardrobeWear');fade_noise(ly,45)
        ly=layer(tree,'07 | rubbed edges and seam ridges',color=tuple(min(.72,x*1.25+.028) for x in base),rough=.49 if leather else .70,amount=.30)
        masked(ly,'WardrobeEdge')
        ly=layer(tree,'08 | contact polishing',rough=.40 if leather else .64,amount=.40)
        masked(ly,'WardrobeContact')
        ly=layer(tree,'09 | dry dust at hems and toes',color=(.19,.157,.110),rough=.87,amount=.26)
        masked(ly,'WardrobeDust');fade_noise(ly,58)
        U.input_outputs.check_all_channel_ios(tree.yp,reconnect=True)
        U.input_outputs.check_start_end_root_ch_nodes(tree)
        for ly in tree.yp.layers: U.node_connections.reconnect_layer_nodes(ly)
        U.node_connections.reconnect_yp_nodes(tree)
        mat['authoring']='Native UCUPaint 2.4.9; photographed CC0 material structure, original dye/pattern and spatially localized wear.'
        report.append({'material':key,'layers':len(tree.yp.layers),'scan':SCAN.get(key),'uv':'UV_Fabric_Metres'})
    (out/'materials_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report


def apply(items,mats,out):
    with redirect_stdout(io.StringIO()):
        return _apply(items,mats,out)
