"""Verify OFF exports pixel-for-pixel and guard the accepted binary factory sources."""
import pathlib,json,hashlib
import numpy as np
from PIL import Image
OUT=pathlib.Path('E:/Models Blender/WEAPONS/ДОЗОР — фонари и крепёж')
WORK=pathlib.Path(__file__).resolve().parents[2]/'_asset_src/dozor/wear'
spec=json.loads((OUT/'finish-spec.json').read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(OUT/'models/DOZOR_Factory_Painter_v01.blend')==spec['acceptance']['model_sha256']
assert sha(OUT/'painter/DOZOR_factory_v01.spp')==spec['acceptance']['painter_sha256']
report={'factory_blend_bytes_unchanged':True,'factory_spp_bytes_unchanged':True,'off_control':{},'working_delta':{}}
for key,texset in [('F1','DOZOR_F1'),('P','DOZOR_P')]:
    report['off_control'][key]={};report['working_delta'][key]={}
    for suffix in ('baseColor','occlusionRoughnessMetallic','normal'):
        name=texset+'_'+suffix+'.png'
        base=np.asarray(Image.open(OUT/'textures/factory'/key/name)).astype(np.int16)
        off=np.asarray(Image.open(WORK/'off_control'/key/name)).astype(np.int16)
        work=np.asarray(Image.open(OUT/'textures/working100'/key/name)).astype(np.int16)
        off_delta=np.abs(base-off)
        if np.any(off_delta):
            # The original factory SPP itself reproduces five borderline roughness
            # texels differently after reopening. Record the measured exception;
            # do not claim bit-identical maps or hide it with an image threshold.
            assert key=='F1' and suffix=='occlusionRoughnessMetallic'
            fresh=np.asarray(Image.open(WORK/'factory_reopen_control'/name)).astype(np.int16)
            fresh_delta=np.abs(base-fresh)
            assert np.any(fresh_delta),'A fresh immutable-factory control is required'
            assert not off_delta[...,0].any() and not off_delta[...,2].any()
            assert np.any(off_delta,axis=-1).sum()<=5 and off_delta.max()<=3
            assert np.any(fresh_delta,axis=-1).sum()<=5 and fresh_delta.max()<=3
            report['off_control'][key][suffix]={'pixel_identical':False,'changed_pixels':int(np.any(off_delta,axis=-1).sum()),'max_8bit_delta':int(off_delta.max()),'fresh_unchanged_factory_changed_pixels':int(np.any(fresh_delta,axis=-1).sum()),'fresh_unchanged_factory_max_8bit_delta':int(fresh_delta.max()),'note':'Five roughness texels differ after recomputation; same issue reproduced from unchanged factory SPP. All other channels exact.'}
        else:report['off_control'][key][suffix]='pixel-identical'
        delta=np.abs(work-base)
        if suffix=='normal':assert delta.max()==0,'Wear must not change surface relief'
        report['working_delta'][key][suffix]={'changed_pixel_fraction':float(np.any(delta>0,axis=-1).mean()),'max_8bit_delta':int(delta.max()),'mean_8bit_delta':float(delta.mean())}
for suffix in ('baseColor','occlusionRoughnessMetallic','normal'):
    name='DOZOR_LENS_'+suffix+'.png'
    assert np.array_equal(np.asarray(Image.open(OUT/'textures/factory/LENS'/name)),np.asarray(Image.open(OUT/'textures/working100/LENS'/name)))
report['protected_lens_unchanged']=True
(OUT/'checks/working100-preservation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
