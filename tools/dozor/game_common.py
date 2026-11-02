"""Accepted DOZOR source and game derivative configuration; axes in manifest."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ASSET=Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
SOURCE=ASSET/'models/DOZOR_Working100_Painter_v01.blend'
WORK=ROOT/'_asset_src/dozor/game'
OUT=ROOT/'assets/models/attachments/dozor'
SIZES={'F1':2048,'P':1024}
TRIANGLE_LIMIT=5000 # owner: flashlight plus independent mount, one complete LOD0 assembly
WORK.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)

def role(name):
    if name.startswith('F1.'):
        if '.Optics.solid_glass' in name:return 'Lens'
        if '.Button.dot' in name or '.Button.primary' in name:return 'PrimaryButton'
        if '.Button.' in name:return 'ModeButton'
        if '.Clip.' in name:return 'Clip'
        if '.Bezel.' in name:return 'Bezel'
        if '.Optics.' in name:return 'Optics'
        if '.Tail.' in name:return 'TailCap'
        return 'Housing'
    if name in ('P.Ring.upper_cap','P.Liner.upper','P.Hinge.cap_knuckle','P.Lock.upper_lug'):return 'CapHinge'
    if name=='P.Clamp.moving_jaw':return 'MovingJaw'
    if name.startswith('P.Lock.') and ('shank' in name or 'socket_head' in name):return 'LockScrew'
    if '.press_pad' in name or '.pad_rib' in name:return 'ClampPads'
    return 'MountBody'

def select(objs):
    import bpy
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:o.hide_set(False);o.select_set(True)
    bpy.context.view_layer.objects.active=objs[-1]
