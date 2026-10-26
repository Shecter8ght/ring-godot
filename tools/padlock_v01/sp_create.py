from pathlib import Path
import substance_painter.event as E
import substance_painter.project as P
import substance_painter.application as A

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
if P.is_open():raise RuntimeError('Unexpected open project in the padlock-only session')
def _padlock_created(event):
    (WORK/'sp_jobs'/'_project_ready.txt').write_text('ready',encoding='utf-8')
E.DISPATCHER.connect_strong(E.ProjectEditionEntered,_padlock_created)
settings=P.Settings(default_texture_resolution=4096,normal_map_format=P.NormalMapFormat.OpenGL,
                    tangent_space_mode=P.TangentSpace.PerFragment)
P.create(str(WORK/'painter'/'padlock_highpoly_uv.fbx').replace('\\','/'),settings=settings)
print('CREATE_STARTED',A.version_info())
