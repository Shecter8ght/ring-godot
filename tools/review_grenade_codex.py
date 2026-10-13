"""Final art-source renders, dimensions, saved-file checks and visual demo."""
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

HERE=Path(__file__).resolve().parent
OUT=HERE.parent/'_asset_src/grenade_codex'
spec=importlib.util.spec_from_file_location('grenade_texture',HERE/'texture_grenade_codex.py')
T=importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
MODE=sys.argv[sys.argv.index('--')+1] if '--' in sys.argv else 'render'
PREVIEW=OUT/'Grenade_MkII_PBR_Preview_v06.blend'


def start(path):
    T.P.native()
    bpy.ops.wm.open_mainfile(filepath=str(path))
    T.S.setup_studio((0,0,0))
    bpy.context.scene.cycles.use_denoising=False
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()


def finalize():
    for path in [T.MASTER,PREVIEW]:
        start(path)
        scene=bpy.context.scene
        scene.camera.location=(.17,-.28,.18)
        T.S.aim(scene.camera,(0,0,.057))
        scene.camera.data.ortho_scale=.167
        scene.cycles.samples=128
        scene.render.resolution_x,scene.render.resolution_y=1800,2200
        root=bpy.data.objects['CTRL_Grenade']
        for ob in bpy.context.selected_objects:
            ob.select_set(False)
        root.select_set(True)
        bpy.context.view_layer.objects.active=root
        for screen in bpy.data.screens:
            for area in screen.areas:
                if area.type=='VIEW_3D':
                    space=area.spaces.active
                    space.region_3d.view_location=(0,0,.055)
                    space.region_3d.view_distance=.22
                    space.region_3d.view_rotation=scene.camera.rotation_euler.to_quaternion()
                    space.clip_start=.001
                    space.shading.type='MATERIAL'
                    space.overlay.show_floor=False
                    space.overlay.show_axis_x=False
                    space.overlay.show_axis_y=False
                if area.type=='PROPERTIES':
                    area.spaces.active.context='OBJECT'
        bpy.ops.wm.save_as_mainfile(filepath=str(path),relative_remap=False)
    print('FINAL_STUDIO_SAVED_OK',flush=True)


def measure():
    start(T.MASTER)
    scene=bpy.context.scene
    def dimensions(objects):
        pts=[ob.matrix_world@Vector(p) for ob in objects for p in ob.bound_box]
        mn=[min(p[i] for p in pts) for i in range(3)]
        mx=[max(p[i] for p in pts) for i in range(3)]
        return {'min_m':mn,'max_m':mx,'dimensions_mm':[(mx[i]-mn[i])*1000 for i in range(3)]}
    meshes=[o for o in scene.objects if o.type=='MESH']
    report={'units':'metres; display millimetres','closed_assembly':dimensions(meshes),
            'body':dimensions([bpy.data.objects['GrenadeBody']]),'mesh_topology':[]}
    for ob in meshes:
        bm=bmesh.new()
        bm.from_mesh(ob.data)
        row={'name':ob.name,'vertices':len(bm.verts),'faces':len(bm.faces),
             'boundary_edges':sum(e.is_boundary for e in bm.edges),
             'nonmanifold_edges':sum(not e.is_manifold for e in bm.edges),
             'tiny_faces_below_1e-14_m2':sum(f.calc_area()<1e-14 for f in bm.faces)}
        # Imported split UV/normal vertices can report boundaries without holes.
        # Weld only this disposable audit copy, never the delivered geometry.
        bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=1e-7)
        row['audit_copy_weld_tolerance_m']=1e-7
        row['welded_boundary_edges']=sum(e.is_boundary for e in bm.edges)
        row['welded_nonmanifold_edges']=sum(not e.is_manifold for e in bm.edges)
        report['mesh_topology'].append(row)
        bm.free()
    (OUT/'checks/measurements_and_topology_v06.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('MEASURE_OK',report['closed_assembly']['dimensions_mm'],flush=True)


def render():
    T.render()
    start(T.MASTER)
    scene=bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y=1800,2200
    scene.cycles.samples=256
    T.S.shot('11_size_front',(0,0,0),(0,-.4,.055),(0,0,.055),.175)
    dg=bpy.context.evaluated_depsgraph_get()
    bounds=[ob.evaluated_get(dg).matrix_world@Vector(p) for ob in scene.objects
            if ob.type=='MESH' for p in ob.evaluated_get(dg).bound_box]
    def pixel(p):
        point=world_to_camera_view(scene,scene.camera,Vector(p))
        return [point.x*1800,(1-point.y)*2200]
    body=bpy.data.objects['GrenadeBody']
    bb=[body.matrix_world@Vector(p) for p in body.bound_box]
    points={'height_bottom':pixel((.046,0,min(p.z for p in bounds))),
            'height_top':pixel((.046,0,max(p.z for p in bounds))),
            'body_left':pixel((min(p.x for p in bb),0,-.014)),
            'body_right':pixel((max(p.x for p in bb),0,-.014))}
    (OUT/'checks/size_annotation_points_v06.json').write_text(json.dumps(points,indent=2),encoding='utf8')
    start(PREVIEW)
    scene=bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y=1800,2200
    scene.cycles.samples=256
    T.S.shot('12_baked_comparison',(0,0,0))
    T.S.shot('13_baked_head_comparison',(0,0,0),(.09,-.14,.22),(0,0,.101),.071)
    print('FINAL_V06_VIEWS_OK',flush=True)


def animation():
    start(PREVIEW)
    scene=bpy.context.scene
    scene.render.resolution_x,scene.render.resolution_y=900,1080
    scene.cycles.samples=64
    scene.render.use_persistent_data=True
    scene.camera.location=(.23,-.34,.20)
    T.S.aim(scene.camera,(.025,-.009,.070))
    scene.camera.data.ortho_scale=.205
    directory=OUT/'previews/animation_frames_v06'
    directory.mkdir(parents=True,exist_ok=True)
    for frame in range(1,97):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        scene.render.filepath=str(directory/f'{frame:04}.png')
        bpy.ops.render.render(write_still=True)
        if frame%12==0:
            print('ANIMATION_PROGRESS',frame,'of 96',flush=True)
    print('ANIMATION_FRAMES_OK',flush=True)


def comparison():
    for path,names in [(T.MASTER,['01_textured_overall','04_head_ring_marking']),
                       (PREVIEW,['12_baked_comparison','13_baked_head_comparison'])]:
        start(path)
        scene=bpy.context.scene
        scene.render.resolution_x,scene.render.resolution_y=1800,2200
        scene.cycles.samples=128
        T.S.shot(names[0],(0,0,0))
        T.S.shot(names[1],(0,0,0),(.09,-.14,.22),(0,0,.101),.071)
    print('MATCHED_COMPARISON_READY',flush=True)


if __name__=='__main__':
    {'finalize':finalize,'measure':measure,'render':render,'animation':animation,'comparison':comparison}[MODE]()
