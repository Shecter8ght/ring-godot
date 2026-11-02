import pathlib,json
import substance_painter.project as P
import substance_painter.textureset as TS
import substance_painter.event as E
assert not P.is_open(),'Dedicated project unexpectedly occupied'
path='E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж/painter/DOZOR_authoring.fbx'
settings=P.Settings(default_texture_resolution=2048,normal_map_format=P.NormalMapFormat.OpenGL,
                    tangent_space_mode=P.TangentSpace.PerFragment)
def ready(e):
    E.DISPATCHER.disconnect(E.ProjectEditionEntered,ready)
    for t in TS.all_texture_sets():
        res=4096 if t.name()=='DOZOR_F1' else 2048 if t.name()=='DOZOR_P' else 512
        t.set_resolution(TS.Resolution(res,res))
    sp_finish.mark('_project_ready.txt','OK '+','.join(t.name() for t in TS.all_texture_sets()))
E.DISPATCHER.connect(E.ProjectEditionEntered,ready)
P.create(path,settings=settings)
print('creating DOZOR Painter project')
