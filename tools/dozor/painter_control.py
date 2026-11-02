"""Send jobs only to the dedicated DOZOR Painter bridge; bounded per-call waits."""
import os,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
os.environ['FINISH_SP_JOBS']=str(ROOT/'_asset_src/dozor/painter_jobs')
sys.path.insert(0,str(ROOT/'tools/asset_kit/finish'))
import sp_run
if sys.argv[1]=='wait':
 print(sp_run.wait(sp_run.SP_JOBS/sys.argv[2],50))
else:
 path=pathlib.Path(sys.argv[1])
 code=path.read_text(encoding='utf-8') if path.is_file() else sys.argv[1]
 print(sp_run.run(code,50,path.stem if path.is_file() else 'probe'))
