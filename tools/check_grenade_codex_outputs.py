"""Проверка PNG, видов с одинаковой камерой и демонстрационного ролика."""
import hashlib
import json
import struct
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

OUT=Path(__file__).resolve().parents[1]/'_asset_src/grenade_codex'
CHECKS=OUT/'checks'
FFPROBE=Path('D:/whisper/ffmpeg/bin/ffprobe.exe')


def maps():
    manifest=json.loads((OUT/'textures/pbr_v06/manifest.json').read_text())
    assert len(manifest)==16
    rows=[]
    for row in manifest:
        path=OUT/'textures/pbr_v06'/row['file']
        with path.open('rb') as stream:
            head=stream.read(33)
            stream.seek(0)
            sha=hashlib.file_digest(stream,'sha256').hexdigest()
        assert head[:8]==b'\x89PNG\r\n\x1a\n' and head[24]==16,row['file']
        assert list(struct.unpack('>II',head[16:24]))==row['size'],row['file']
        assert sha==row['sha256'],row['file']
        assert row['color_space']==('sRGB' if row['channel']=='BaseColor' else 'Non-Color')
        rows.append({'file':row['file'],'size':row['size'],'bit_depth':16,'sha256':sha})
    (CHECKS/'pbr_png_encoding_v06.json').write_text(json.dumps(rows,indent=2))
    print('PBR_HEADERS_AND_HASHES_OK',len(rows),flush=True)


def compare():
    rows=[]
    for native,baked in [('01_textured_overall','12_baked_comparison'),
                         ('04_head_ring_marking','13_baked_head_comparison')]:
        paths=[OUT/'previews'/(name+'.png') for name in [native,baked]]
        ims=[Image.open(path).convert('RGB') for path in paths]
        assert ims[0].size==ims[1].size==(1800,2200)
        a,b=[np.asarray(im.resize((450,550),Image.Resampling.LANCZOS),np.float32)/255 for im in ims]
        background=a[0,0]
        mask=np.max(np.abs(a-background),axis=2)>.065
        assert mask.mean()>.12
        av,bv=a[mask],b[mask]
        delta=np.abs(av-bv)
        mu_a,mu_b=av.mean(axis=0),bv.mean(axis=0)
        va,vb=av.var(axis=0),bv.var(axis=0)
        covariance=((av-mu_a)*(bv-mu_b)).mean(axis=0)
        ssim=((2*mu_a*mu_b+.01**2)*(2*covariance+.03**2)/
              ((mu_a**2+mu_b**2+.01**2)*(va+vb+.03**2)))
        rows.append({'native':paths[0].name,'baked':paths[1].name,'same_camera_and_lighting':True,
                     'metric_size':[450,550],'foreground_fraction':float(mask.mean()),
                     'mean_absolute_srgb_difference':float(delta.mean()),
                     'p95_absolute_srgb_difference':float(np.quantile(delta,.95)),
                     'global_foreground_ssim_rgb_mean':float(ssim.mean()),
                     'metric_note':'Downsampled foreground diagnostic; does not replace full resolution visual review.'})
        print('COMPARISON',native,json.dumps(rows[-1]),flush=True)
    (CHECKS/'native_baked_comparison_v06.json').write_text(json.dumps({'comparisons':rows},indent=2))


def video():
    path=OUT/'previews/pin_lever_demo_v06.mp4'
    probe=json.loads(subprocess.check_output([str(FFPROBE),'-v','error','-count_frames',
        '-show_streams','-show_format','-of','json',str(path)]))
    stream=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert stream['codec_name']=='h264'
    assert [stream['width'],stream['height']]==[900,1080]
    assert int(stream['nb_read_frames'])==96
    assert abs(float(probe['format']['duration'])-4.0)<.05
    with path.open('rb') as handle: sha=hashlib.file_digest(handle,'sha256').hexdigest()
    result={'file':path.name,'sha256':sha,'size':[900,1080],'frames':96,'fps':24,
            'duration_seconds':float(probe['format']['duration']),'codec':'h264',
            'visual_only':True,'geometry':'owner-approved v05'}
    (CHECKS/'video_validation_v06.json').write_text(json.dumps(result,indent=2))
    print('VIDEO_CHECK_OK',result,flush=True)


if __name__=='__main__':
    import sys
    {'maps':maps,'compare':compare,'video':video}[sys.argv[1]]()
