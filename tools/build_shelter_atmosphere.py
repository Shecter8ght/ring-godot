"""Запечённые циклы пыли и пара: фиксированная геометрия + shape-key анимация.

Не использует ParticleSystem, Geometry Nodes, GPUParticles или runtime random.
"""
import bpy, math, json, sys
from pathlib import Path
import numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'assets/shelter/atmosphere';OUT.mkdir(parents=True,exist_ok=True)
SRC=ROOT/'_asset_src/shelter/atmosphere';SRC.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,r'C:/Users/Schecter_8ght/AppData/Roaming/Blender Foundation/Blender/5.2/extensions/blender_org')
bpy.ops.preferences.addon_enable(module='ucupaint')
import ucupaint
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.scene.unit_settings.system='METRIC';bpy.context.scene.render.fps=24

def stamp(buf,cx,cy,rx,ry,alpha):
    h,w=buf.shape[:2];y,x=np.mgrid[0:h,0:w]
    q=((x-cx)/rx)**2+((y-cy)/ry)**2
    influence=np.maximum(0,1-q)**3*alpha
    buf[:,:,3]=np.maximum(buf[:,:,3],influence)

def mask_material(name,stamps):
    bpy.ops.mesh.primitive_plane_add();plane=bpy.context.object
    mat=bpy.data.materials.new(name);mat.use_nodes=True;plane.data.materials.append(mat)
    bpy.ops.wm.y_quick_ypaint_node_setup(tree_name=name+' — painted layers',color=True,alpha=True,metallic=False,roughness=False,normal=False,ao=False,switch_to_material_view=False)
    node=next(n for n in mat.node_tree.nodes if n.type=='GROUP' and n.node_tree.yp.is_ypaint_node)
    mat.node_tree.nodes.active=node
    bpy.ops.wm.y_new_layer(name=name+' — soft brush strokes',type='IMAGE',width=256,height=256,use_custom_resolution=True,channel_idx='0',uv_map='UVMap')
    layer=node.node_tree.yp.layers[node.node_tree.yp.active_layer_index]
    img=ucupaint.common.get_layer_source(layer).image
    pixels=np.ones((256,256,4),dtype=np.float32);pixels[:,:,3]=0
    for args in stamps:stamp(pixels,*args)
    img.pixels.foreach_set(pixels.reshape(-1));img.update();img.filepath_raw=str(OUT/(name+'.png'));img.file_format='PNG';img.save();img.pack()
    bpy.data.objects.remove(plane,do_unlink=True)
    return mat

dustmat=mask_material('DustSoft',[(128,128,110,110,.32)])
vapormat=mask_material('VaporSoft',[(112,62,50,60,.17),(131,91,67,75,.22),(108,131,72,79,.19),(148,173,59,64,.14),(128,214,49,39,.09)])

def xyz(p):return (p[0],-p[2],p[1])

def clip(name,centers,size,material,seconds,motion):
    verts=[];faces=[]
    for c in centers:
        base=len(verts)
        for dx,dy in [(-size,-size),(size,-size),(size,size),(-size,size)]:verts.append(xyz((c[0]+dx,c[1]+dy,c[2])))
        faces.append((base,base+1,base+2,base+3))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(verts,[],faces);mesh.update()
    ob=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(ob);ob.data.materials.append(material)
    uv=mesh.uv_layers.new(name='UVMap')
    for f in mesh.polygons:
        for li,coord in zip(f.loop_indices,[(0,0),(1,0),(1,1),(0,1)]):uv.data[li].uv=coord
    ob.shape_key_add(name='Basis')
    end=1+int(seconds*24);step=(end-1)//6
    for k in range(1,6):
        key=ob.shape_key_add(name='AuthoredPose_%d'%k)
        for i,c in enumerate(centers):
            delta=motion(i,k/6)
            for v in range(4):key.data[i*4+v].co+=Vector(xyz(delta))
        for frame,value in [(1,0),(1+(k-1)*step,0),(1+k*step,1),(1+(k+1)*step,0),(end,0)]:
            key.value=value;key.keyframe_insert(data_path='value',frame=frame)
    bpy.context.scene.frame_start=1;bpy.context.scene.frame_end=end;bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
    bpy.ops.export_scene.gltf(filepath=str(OUT/(name+'.glb')),export_format='GLB',use_selection=True,export_yup=True,export_animations=True,export_frame_range=True,export_force_sampling=True,export_materials='EXPORT')
    ob.hide_set(True);ob.hide_render=True
    return {'planes':len(centers),'seconds':seconds,'shape_poses':5,'runtime_simulation':False}

# Зафиксированная композиция 24 пылинок, записанная в blend и GLB.
centers=[(-.70,0,-.13),(-.51,.16,.11),(-.29,-.18,.07),(-.06,.23,-.03),(.19,-.08,.14),(.42,.14,-.09),(.65,-.21,.04),
         (-.64,.43,.06),(-.38,.57,-.11),(-.13,.44,.10),(.12,.59,-.06),(.37,.41,.07),(.61,.54,-.12),
         (-.55,.80,-.03),(-.26,.88,.13),(.02,.76,-.09),(.28,.95,.02),(.55,.85,.12),
         (-.62,1.17,.08),(-.35,1.29,-.05),(-.08,1.10,.04),(.18,1.33,-.10),(.43,1.15,.09),(.68,1.26,-.03)]
def dustmotion(i,t):
    a=t*math.tau;phase=(i%5)*.75
    return (.07*(math.sin(a+phase)-math.sin(phase)),.10*(math.sin(a+(i%3)) - math.sin(i%3)),.035*math.sin(a))
def vapormotion(i,t):
    a=t*math.tau
    return (.025*math.sin(a+i),.045*math.sin(a-i*.6),.012*math.sin(a+i*.3))
info={}
info['DustMotes']=clip('DustMotes',centers,.013,dustmat,18,dustmotion)
info['KettleVapor']=clip('KettleVapor',[(-.012,.09,0),(.015,.19,.025),(-.01,.29,-.015)],.12,vapormat,8,vapormotion)
for ob in bpy.context.scene.objects:ob.hide_set(False)
bpy.ops.wm.save_as_mainfile(filepath=str(SRC/'shelter_atmosphere.blend'))
(OUT/'manifest.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
(SRC/'license.txt').write_text('Own RING artwork. Painted masks and baked mesh animations authored in Blender / Ucupaint.\n',encoding='utf-8')
print('ATMOSPHERE_DONE',json.dumps(info),flush=True)
