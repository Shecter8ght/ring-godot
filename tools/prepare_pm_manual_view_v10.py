"""Save a clean manual inspection view. No presentation, movie or new action."""
from pathlib import Path
import bpy,addon_utils
from mathutils import Vector
path=Path(bpy.data.filepath);bpy.context.preferences.use_preferences_save=False
revision=path.stem.rsplit('_',1)[-1]
addon_utils.enable('bl_ext.blender_org.ucupaint',default_set=True);bpy.ops.wm.open_mainfile(filepath=str(path))
S=bpy.context.scene;S.frame_set(1);rig=bpy.data.objects['PM_CONTROLS • select me'];rig.animation_data_clear()
for action in list(bpy.data.actions):
 if action.name=='Geometry inspection '+revision:bpy.data.actions.remove(action)
for key in ('Slide','Hammer','Trigger','Safety','Magazine','MagCatch','SlideStop','Suppressor'):rig[key]=0.
rig.update_tag();bpy.context.view_layer.update()
for o in bpy.context.selected_objects:o.select_set(False)
rig.hide_set(False);rig.select_set(True);bpy.context.view_layer.objects.active=rig
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type!='VIEW_3D':continue
  space=area.spaces.active;space.overlay.show_extras=False;space.overlay.show_relationship_lines=False
  space.shading.type='SOLID';space.shading.light='STUDIO';space.clip_start=.0001;space.clip_end=20.
  space.region_3d.view_perspective='PERSP';space.region_3d.view_location=Vector((.01,0,.066));space.region_3d.view_distance=.38
  space.region_3d.view_rotation=Vector((-.24,-.34,.17)).to_track_quat('Z','Y')
note=bpy.data.texts.get(revision+' • открыть и проверить вручную') or bpy.data.texts.new(revision+' • открыть и проверить вручную')
note.clear();note.write('По поручению владельца: без роликов, галерей и демонстрационных анимаций.\nКонтролы корня PM_CONTROLS свободны от Action и меняются вручную. Прежние Actions сохранены.\nВыдача — .blend; рабочие скриншоты показываются в чате.\n')
bpy.ops.wm.save_as_mainfile(filepath=str(path));print('PM_MANUAL_VIEW_SAVED',flush=True)
