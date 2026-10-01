"""Общая редактируемая сцена и свежие ракурсы фактических GLB из Krita."""
from pathlib import Path
import sys,bpy
from mathutils import Vector
sys.path.insert(0,str(Path(__file__).resolve().parent))
import build_vss_blender as B
import export_vss_optic as E
from import_vss_textured import IDS,RAW

def fit_camera(camera, roots, width, height):
    # Кадр считаем по фактической геометрии, включая длинный наглазник ПСО.
    inverse=camera.matrix_world.inverted()
    points=[inverse @ obj.matrix_world @ Vector(corner)
            for root in roots for obj in root.children_recursive
            if obj.type=='MESH' for corner in obj.bound_box]
    xmin,xmax=min(p.x for p in points),max(p.x for p in points)
    ymin,ymax=min(p.y for p in points),max(p.y for p in points)
    camera.location+=camera.rotation_euler.to_matrix() @ Vector(((xmin+xmax)/2,(ymin+ymax)/2,0))
    camera.data.ortho_scale=max(xmax-xmin,(ymax-ymin)*width/height)*1.18


def main():
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    B.COLLECTIONS.clear()
    studio=B.collection('90_Studio');B.studio()
    positions={
      'VSS_Vintorez_Picatinny':(0,0,.12),
      'PSO_VSS_4x24':(.07,0,-.27),
      'Rail_4x32':(.59,0,-.25),
      'Magazine_939_10_Empty':(.15,0,-.50),
      'Magazine_939_10_Loaded':(.36,0,-.50),
      'Cartridge_939_SP5':(.64,0,-.52),
    }
    for identifier in IDS:
        bpy.ops.import_scene.gltf(filepath=str(RAW/identifier/(identifier+'.glb')))
        root=bpy.data.objects[identifier]
        root.matrix_world=E.MAP.inverted() @ root.matrix_world
        root.location+=Vector(positions[identifier]);root['gallery_only_offset']=list(positions[identifier])
        if identifier.startswith('Cartridge'):
            for number,dz in enumerate((.025,-.025),2):
                old=[root,*root.children_recursive];copies={o:o.copy() for o in old}
                for source,copy in copies.items():
                    bpy.context.scene.collection.objects.link(copy)
                    if source.parent in copies:copy.parent=copies[source.parent]
                    copy.matrix_basis=source.matrix_basis.copy()
                copies[root].name='Cartridge_SP5_Preview_'+str(number)
                copies[root].location.z+=dz
    bpy.context.view_layer.update()
    for lamp in bpy.data.objects:
        if lamp.type=='LIGHT':
            lamp.location.z-=.10
            lamp.data.energy*=.70
            lamp.rotation_euler=(Vector((.44,0,-.16))-lamp.location).to_track_quat('-Z','Y').to_euler()
    camera=B.camera('Camera_Textured_Kit',(.88,-1.8,.43),(.43,0,-.20),1.14)
    B.camera('Camera_Textured_Rifle',(.88,-1.6,.49),(.44,0,.08),1.04)
    B.camera('Camera_Optics_Materials',(.57,-.80,.06),(.43,0,-.25),.88)
    B.camera('Camera_Mag_Ammo_Materials',(.62,-.65,-.24),(.40,0,-.535),.64)
    roots={identifier:bpy.data.objects[identifier] for identifier in IDS}
    ammo_copies=[obj for obj in bpy.data.objects if obj.name.startswith('Cartridge_SP5_Preview_') and obj.parent is None]
    views=[('all','Camera_Textured_Kit',1800,1350,list(roots.values())+ammo_copies),
        ('rifle','Camera_Textured_Rifle',1800,800,[roots['VSS_Vintorez_Picatinny']]),
        ('optics','Camera_Optics_Materials',1650,820,[roots['PSO_VSS_4x24'],roots['Rail_4x32']]),
        ('mag_ammo','Camera_Mag_Ammo_Materials',1500,800,[roots['Magazine_939_10_Empty'],roots['Magazine_939_10_Loaded'],roots['Cartridge_939_SP5']]+ammo_copies)]
    bpy.context.view_layer.update()
    render_views=[]
    for suffix,name,width,height,shown in views:
        fit_camera(bpy.data.objects[name],shown,width,height)
        names={part.name for owner in shown for part in [owner,*owner.children_recursive]}
        render_views.append((suffix,name,width,height,names))
    bpy.context.scene.camera=camera
    bpy.context.scene.render.resolution_x=1800
    bpy.context.scene.render.resolution_y=1350
    bpy.context.scene.render.engine='BLENDER_EEVEE'
    bpy.context.scene.view_settings.exposure=-.25
    bpy.ops.object.select_all(action='DESELECT')
    root=bpy.data.objects['VSS_Vintorez_Picatinny'];bpy.context.view_layer.objects.active=root
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA';area.spaces.active.region_3d.view_camera_zoom=10
                area.spaces.active.shading.type='MATERIAL'
                area.spaces.active.overlay.show_overlays=False
                area.spaces.active.show_gizmo=False
    B.save_scene(RAW/'VSS_Textured_Kit.blend')
    # Проверяем сохранённый файл; другие предметы не лезут в крупные планы.
    bpy.ops.wm.open_mainfile(filepath=str(RAW/'VSS_Textured_Kit.blend'))
    for suffix,name,width,height,names in render_views:
        for obj in bpy.context.scene.objects:
            if obj.type=='MESH':obj.hide_render=obj.name not in names
        B.render_views(RAW,'kit',[(suffix,name,width,height)])
    print('VSS_TEXTURED_KIT_SAVED',flush=True)
if __name__=='__main__':main()
