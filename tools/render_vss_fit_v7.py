"""Актуальная демонстрация более пологого крючка ВСС и его упора."""
from pathlib import Path
import sys,json
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
import refine_vss_fit_v7 as F
import refine_vss_geometry_v4 as V
import build_vss_blender as B


def main():
    assert json.loads((F.RAW/'fit-audit.json').read_text(encoding='utf8'))['status']=='PASS'
    bpy.ops.wm.open_mainfile(filepath=str(F.FILE));V.sync()
    B.camera('Camera_Demo_Render',(.51,-.65,.14),(.408,-.020,.007),.205)
    scene=bpy.context.scene;scene.camera=bpy.data.objects['Camera_Demo_Render']
    scene.render.resolution_x=1280;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    B.enum_set(scene.render.image_settings,'file_format','PNG')
    folder=F.RAW/'_frames';folder.mkdir(exist_ok=True)
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame);bpy.context.view_layer.update()
        scene.render.filepath=str(folder/f'{frame:04d}.png');bpy.ops.render.render(write_still=True)
    print('VSS_V7_DEMO_FRAMES_READY',flush=True)


if __name__=='__main__':main()
