"""Reopen the saved padlock in this task's isolated Painter session."""
from pathlib import Path
import substance_painter.event as E
import substance_painter.project as P

work=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
if P.is_open():
    raise RuntimeError('Unexpected project in padlock session: '+str(P.file_path()))
ready=work/'sp_jobs'/'_reopened.txt'
ready.unlink(missing_ok=True)
def _padlock_reopened(event):
    ready.write_text(P.file_path(),encoding='utf-8')
E.DISPATCHER.connect_strong(E.ProjectEditionEntered,_padlock_reopened)
P.open((work/'painter'/'padlock_v02_textured.spp').as_posix())
print('PADLOCK_OPEN_STARTED')
