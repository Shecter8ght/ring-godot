"""Проверочные виды из повторно открытого .blend; исходник не перезаписывается."""
from pathlib import Path
import sys,argparse,json,math
sys.path.insert(0,str(Path(__file__).resolve().parent))
import bpy
from common import ROOT
from build import fit
from generate import bounds

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--key',default='car')
    parser.add_argument('--resolution',type=int,default=1000)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    folder=next((ROOT/'assets').glob('R??_'+args.key))
    path=next((folder/'model').glob('*.blend'))
    bpy.ops.wm.open_mainfile(filepath=str(path))
    sc=bpy.context.scene
    sc.render.engine='CYCLES'; sc.cycles.samples=24; sc.cycles.use_denoising=True
    sc.render.resolution_x=args.resolution; sc.render.resolution_y=round(args.resolution*.75)
    sc.render.resolution_percentage=100
    for ob in bpy.data.collections['STUDIO | neutral lights, no export'].objects:
        if ob.type=='LIGHT': ob.data.energy*=.15
    parts=[o for o in bpy.data.collections['MODEL | editable components'].objects if o.type in ('MESH','FONT','CURVE')]
    low,high=bounds(parts)
    for name,direction in [('front34',(3.6,-6,2.5)),('rear34',(-3.6,6,2.5))]:
        fit(sc.camera,low,high,direction)
        sc.render.filepath=str(folder/'previews'/('inspection_'+name+'.png'))
        bpy.ops.render.render(write_still=True)
    print('INSPECTION_OK',args.key,flush=True)

if __name__=='__main__': main()
