"""Save and close only this task's Painter project to release render memory."""
from pathlib import Path
import substance_painter.project as P

target = Path('E:/Games/RING-godot/_asset_src/padlock_v01/painter/padlock_v02_textured.spp')
if P.is_open():
    current = P.file_path().replace('\\', '/').casefold()
    if current != target.as_posix().casefold():
        raise RuntimeError('Refusing to close a different project: ' + P.file_path())
    P.save()
    P.close()
print('PADLOCK_PROJECT_SAVED_AND_CLOSED', not P.is_open())
