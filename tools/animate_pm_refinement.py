"""Editable inspection action and a refreshed clip of PM v06 controls."""
from pathlib import Path
import argparse, json, subprocess, sys
import bpy
from mathutils import Vector

ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','render']);args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
ROOT=Path(__file__).resolve().parents[1]/'_asset_src/pm_refinement';OUT=ROOT/'review_v06'
S=bpy.context.scene;rig=bpy.data.objects['PM_CONTROLS • select me']
keys=('Slide','Hammer','Safety','Trigger','Magazine','MagCatch')
def desc(o,root):
    while o:
        if o==root:return True
        o=o.parent
    return False

if args.mode=='prepare':
    previous=rig.animation_data.action if rig.animation_data else None
    if previous:previous.use_fake_user=True
    rig.animation_data_clear()
    poses=[(1,{}),(18,{'Slide':1,'Hammer':1}),(32,{'Slide':1,'Hammer':1}),
        (45,{'Hammer':1}),(55,{'Hammer':1,'Trigger':1}),(60,{}),(70,{'Safety':1}),
        (80,{}),(86,{'MagCatch':1}),(98,{'Magazine':1,'MagCatch':1}),
        (108,{'Magazine':1,'MagCatch':1}),(120,{})]
    for frame,values in poses:
        for key in keys:
            rig[key]=float(values.get(key,0));rig.keyframe_insert(data_path='["'+key+'"]',frame=frame)
    action=rig.animation_data.action;action.name='Geometry inspection v06';action.use_fake_user=True
    for layer in action.layers:
        for strip in layer.strips:
            bag=strip.channelbag(rig.animation_data.action_slot)
            if bag:
                for curve in bag.fcurves:
                    for key in curve.keyframe_points:
                        key.interpolation='BEZIER';key.handle_left_type='AUTO_CLAMPED';key.handle_right_type='AUTO_CLAMPED'
    S.frame_start=1;S.frame_end=120;S.render.fps=24;S.render.fps_base=1
    for marker in list(S.timeline_markers):S.timeline_markers.remove(marker)
    for frame,label in ((1,'Сборка'),(18,'Затвор и курок'),(55,'Спуск'),(70,'Флажок'),(98,'Магазин и отдельная защёлка'),(120,'Исходная поза')):
        S.timeline_markers.new(label,frame=frame)
    props=[o for o in bpy.data.objects if o.type=='EMPTY' and o.name.startswith('Animation |')]
    for o in bpy.data.objects:
        if any(desc(o,p) for p in props):o.hide_render=True;o.hide_set(True)
    S.frame_set(1);bpy.context.view_layer.update()
    text=bpy.data.texts.new('v06 • управление демонстрацией')
    text.write('Geometry inspection v06: 1–120, 24 fps. Ключевая демонстрация художественной геометрии.\nДля ручного изменения свойств Slide/Hammer/Safety/Trigger/Magazine/MagCatch отключить Action у PM_CONTROLS.\nПрежняя Demo v5 сохранена в Actions (её диапазон 1–240).\n')
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'01_ПМ/PM_Geometry_v06.blend'))
    print('PM_INSPECTION_ACTION_SAVED',flush=True)
    sys.exit(0)

S.render.engine='CYCLES';S.cycles.samples=12;S.cycles.use_denoising=True
stage=bpy.data.objects.get('Studio | matte charcoal stage')
if stage:stage.hide_render=True
pref=bpy.context.preferences.addons['cycles'].preferences
try:
    pref.compute_device_type='OPTIX';pref.get_devices()
    for d in pref.devices:d.use=d.type!='CPU'
    if any(d.use for d in pref.devices):S.cycles.device='GPU'
except Exception:S.cycles.device='CPU'
for m in S.timeline_markers:m.camera=None
cam=bpy.data.objects['CHECK 01 | Complete PM and separate sight'];cam.location=(-.24,-.34,.235)
cam.rotation_euler=(Vector((.012,0,.054))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=.342;cam.data.clip_start=.0001;S.camera=cam
S.render.resolution_x=1000;S.render.resolution_y=700;S.render.resolution_percentage=100
S.render.image_settings.file_format='PNG';S.view_settings.exposure=-1.25
frames=ROOT/'work/motion_frames';frames.mkdir(exist_ok=True)
for i,frame in enumerate(range(1,121,2)):
    S.frame_set(frame);bpy.context.view_layer.update();S.camera=cam
    S.render.filepath=str(frames/f'{i:04d}.png');bpy.ops.render.render(write_still=True)
    if i%10==0:print('PM_MOTION_FRAME',i,frame,flush=True)
ffmpeg=Path('D:/whisper/ffmpeg/bin/ffmpeg.exe');video=OUT/'Превью/22_Движение_контролов.mp4'
subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-y','-framerate','12','-i',str(frames/'%04d.png'),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
ffprobe=ffmpeg.with_name('ffprobe.exe')
metadata=json.loads(subprocess.check_output([str(ffprobe),'-v','error','-show_streams','-show_format','-of','json',str(video)],text=True))
(OUT/'Проверки/motion_preview.json').write_text(json.dumps(dict(video=str(video),frames=60,fps=12,source_fps=24,source_action='Geometry inspection v06',kind='Keyframed inspection, not a physical simulation',metadata=metadata),ensure_ascii=False,indent=2),encoding='utf-8')
for seconds,name in ((0,'start'),(2.1,'middle'),(4.8,'end')):
    subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-y','-ss',str(seconds),'-i',str(video),'-frames:v','1',str(ROOT/'work'/f'encoded_{name}.png')],check=True)
print('PM_MOTION_VIDEO_SAVED',str(video),flush=True)
