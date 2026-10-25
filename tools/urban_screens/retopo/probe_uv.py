from pathlib import Path
import sys
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import WORK,MODEL,rows,write
from uv_check import audit
for a in rows():
    file=WORK/a['retopo_model']
    if not file.exists():
        continue
    bpy.ops.wm.open_mainfile(filepath=str(file))
    result=audit([o for o in bpy.data.collections[MODEL].objects if o.type=='MESH'])
    write(file.parent.parent/'checks/uv.json',result)
    print('UV_PROBE',a['id'],result,flush=True)
