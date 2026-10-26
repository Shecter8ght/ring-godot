"""Checkpoint the separate v05 project and inspect native filter/anchor facilities."""
import json
from pathlib import Path
import substance_painter.project as P
import substance_painter.resource as R
import substance_painter.textureset as T
import substance_painter.display as D
import sp_lib as S

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
allowed={(WORK/'painter'/('padlock_'+v+'_textured.spp')).as_posix().casefold() for v in ('v04','v05')}
assert P.is_in_edition_state() and P.file_path().replace('\\','/').casefold() in allowed
def probe():
    if not P.file_path().endswith('padlock_v05_textured.spp'):
        P.save_as((WORK/'painter'/'padlock_v05_textured.spp').as_posix(),P.ProjectSaveMode.Full)
    names=[r.identifier().name for r in R.search('u:filter')]
    picked=[s for s in names if any(w in s.lower() for w in ('high','blur','warp','sharp','histogram','normal'))]
    report={'filters':picked,'stack_height_api':[n for n in dir(T.all_texture_sets()[0].get_stack()) if 'height' in n or 'normal' in n],
            'display_api':[n for n in dir(D) if n.startswith('set_')],'saved':P.file_path()}
    (WORK/'checks'/'v05_native_api.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
S.when_idle(probe,'_v05_initialized.txt')
