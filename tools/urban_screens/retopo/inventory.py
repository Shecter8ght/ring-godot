"""Исходные бюджеты и устройство сеток, без записи Blender-источников."""
from pathlib import Path
import json
import sys
import time
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from config import MODEL,WORK,rows,write


def main():
    result=[]
    for a in rows():
        bpy.ops.wm.open_mainfile(filepath=a['source_pbr'])
        dg=bpy.context.evaluated_depsgraph_get()
        parts=[]
        for ob in bpy.data.collections[MODEL].objects:
            if ob.type not in ('MESH','FONT','CURVE'):
                continue
            ev=ob.evaluated_get(dg)
            me=ev.to_mesh(preserve_all_data_layers=True,depsgraph=dg)
            me.calc_loop_triangles()
            rec=dict(name=ob.name,type=ob.type,role=ob.get('finish_role',''),vertices=len(me.vertices),
                triangles=len(me.loop_triangles),quads=sum(len(p.vertices)==4 for p in me.polygons),
                ngons=sum(len(p.vertices)>4 for p in me.polygons),faces=len(me.polygons),
                base_vertices=len(ob.data.vertices) if ob.type=='MESH' else None,
                base_triangles=sum(len(f.vertices)-2 for f in ob.data.polygons) if ob.type=='MESH' else None,
                size=list(ob.dimensions),uvs=[u.name for u in me.uv_layers],
                modifiers=[dict(type=m.type,name=m.name,segments=getattr(m,'segments',None),levels=getattr(m,'levels',None)) for m in ob.modifiers],
                materials=[m.get('surface_recipe',m.name) for m in me.materials if m])
            parts.append(rec)
            ev.to_mesh_clear()
        tri=sum(p['triangles'] for p in parts)
        result.append(dict(id=a['id'],key=a['key'],folder=a['folder'],name=a['name'],source=a['source_pbr'],triangles=tri,
            parts=parts,objects=len(parts)))
        print('RETOPO_INSPECTED',a['id'],tri,len(parts),flush=True)
    write(WORK/'inspection.json',result)
    print('RETOPO_INSPECTION_TOTAL',sum(a['triangles'] for a in result),flush=True)


if __name__=='__main__':
    main()
