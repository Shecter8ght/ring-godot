"""Matched native/baked renders, in memory only; no accepted file is saved."""
import math,sys
from pathlib import Path
import bpy
from mathutils import Matrix
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import game,factory

ROOT=HERE.parents[1]
for mode,path in [('native',game.MASTER),('baked',game.WORK/'QuestPhone_Game.blend')]:
    bpy.ops.wm.open_mainfile(filepath=str(path))
    factory.load_ucup()
    if mode=='baked':
        inverse=Matrix.Rotation(-math.pi/2,4,'X')
        for ob in bpy.context.scene.objects:
            if ob.type=='MESH':ob.data.transform(inverse);ob.data.update()
            ob.location=inverse@ob.location
    for ob in list(bpy.context.scene.objects):
        if ob.type=='LIGHT':bpy.data.objects.remove(ob,do_unlink=True)
    if bpy.context.scene.camera is None:
        data=bpy.data.cameras.new('Comparison');ob=bpy.data.objects.new('Comparison',data)
        bpy.context.scene.collection.objects.link(ob);bpy.context.scene.camera=ob
    factory.studio()
    sc=bpy.context.scene;sc.cycles.samples=32
    sc.render.resolution_x=900;sc.render.resolution_y=1100
    for side,eye in [('back',(-.075,.04,-.30)),('front',(.06,-.04,.30))]:
        sc.camera.location=eye;factory.point(sc.camera,(0,0,0));sc.camera.data.ortho_scale=.197
        sc.render.filepath=str(ROOT/f'docs/screens/quest_phone_compare_{mode}_{side}.png')
        bpy.ops.render.render(write_still=True)
        print('COMPARE',mode,side,flush=True)
