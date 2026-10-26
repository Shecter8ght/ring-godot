from pathlib import Path
import substance_painter.baking as B
import substance_painter.event as E
import substance_painter.textureset as T
from substance_painter.textureset import MeshMapUsage as U

WORK=Path('E:/Games/RING-godot/_asset_src/padlock_v01')
sets=T.all_texture_sets()
if len(sets)!=1 or sets[0].name()!='Padlock':raise RuntimeError('Unexpected texture sets '+str([t.name() for t in sets]))
t=sets[0]
bp=B.BakingParameters.from_texture_set(t)
bp.set_enabled_bakers([U.Normal,U.WorldSpaceNormal,U.AO,U.Curvature,U.Position,U.Thickness])
common=bp.common()
B.BakingParameters.set({common['OutputSize']:(12,12),common['LowAsHigh']:True,
                        common['SubSampling']:1,common['RelativeScale']:True,
                        common['MaxHeight']:.002,common['MaxDepth']:.002,common['IgnoreBackface']:True})
def _padlock_baked(event):
    (WORK/'sp_jobs'/'_bake_ready.txt').write_text(str(event.status),encoding='utf-8')
E.DISPATCHER.connect_strong(E.BakingProcessEnded,_padlock_baked)
B.bake_async(t)
print('BAKE_STARTED',t.name())
