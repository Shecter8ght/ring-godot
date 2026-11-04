"""Append saved pose channels without evaluating an old Action on file load."""
import bpy

def load_saved_pose(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    with bpy.data.libraries.load(str(path), link=False) as (source, target):
        target.objects = list(source.objects)
        target.worlds = list(source.worlds)
        target.texts = list(source.texts)
    objects = [o for o in target.objects if o]
    arm = next(o for o in objects if o.type == 'ARMATURE')
    # This has to happen before the rig is linked to an evaluated scene. Ctrl+S stores the
    # edited property values, but open_mainfile evaluates the previous frame-1 Action.
    for ob in objects: ob.animation_data_clear()
    scene = bpy.context.scene
    for ob in objects: scene.collection.objects.link(ob)
    scene.world = next((w for w in target.worlds if w and 'нейтральная' in w.name), None)
    scene.camera = next((o for o in objects if o.type == 'CAMERA' and o.name.startswith('02')), None)
    scene.render.engine = 'CYCLES'; scene.cycles.samples = 24; scene.cycles.use_denoising = True
    scene.render.resolution_x = 1280; scene.render.resolution_y = 900; scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.tool_settings.use_keyframe_insert_auto = False
    bpy.context.view_layer.update()
    return scene, arm, objects
