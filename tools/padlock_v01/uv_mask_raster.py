"""Rasterize physical fields to an existing UV atlas, without modifying meshes."""
from pathlib import Path
import bpy
import numpy as np

def rasterize(objects,field,names,out,size=4096):
    masks=np.zeros((len(names),size,size),np.float16)
    for obj in objects:
        mesh=obj.data;mesh.calc_loop_triangles();uv=mesh.uv_layers.active.data
        world=np.asarray([tuple(obj.matrix_world@v.co) for v in mesh.vertices],dtype=np.float32)*1000
        normal_matrix=obj.matrix_world.to_3x3().inverted().transposed()
        for tri in mesh.loop_triangles:
            tex=np.asarray([tuple(uv[i].uv) for i in tri.loops],dtype=np.float64)
            tex[:,0]*=size;tex[:,1]=(1-tex[:,1])*size
            a,b,c=tex;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
            if abs(den)<1e-7:continue
            low=np.maximum(0,np.floor(tex.min(axis=0)).astype(int));high=np.minimum(size-1,np.ceil(tex.max(axis=0)).astype(int))
            if np.any(high<low):continue
            yy,xx=np.mgrid[low[1]:high[1]+1,low[0]:high[0]+1];px=xx.ravel()+.5;py=yy.ravel()+.5
            w0=((b[1]-c[1])*(px-c[0])+(c[0]-b[0])*(py-c[1]))/den
            w1=((c[1]-a[1])*(px-c[0])+(a[0]-c[0])*(py-c[1]))/den
            w2=1-w0-w1;inside=(w0>=-1e-6)&(w1>=-1e-6)&(w2>=-1e-6)
            if not inside.any():continue
            bary=np.column_stack((w0[inside],w1[inside],w2[inside]))
            points=bary@world[list(tri.vertices)]
            normals=np.asarray([tuple(normal_matrix@mesh.corner_normals[i].vector) for i in tri.loops],dtype=np.float32)
            interpolated=bary@normals
            values=field(obj.name,points,interpolated)
            if not np.isfinite(values).all():raise RuntimeError('Nonfinite physical field: '+obj.name)
            rows=yy.ravel()[inside];cols=xx.ravel()[inside]
            for i in range(len(names)):
                masks[i,rows,cols]=np.maximum(masks[i,rows,cols],values[:,i])
        print('PHYSICAL_FIELDS',obj.name,flush=True)
    out=Path(out);out.mkdir(exist_ok=True)
    for i,name in enumerate(names):
        np.save(out/(name+'.npy'),masks[i]);print('MASK_PIXELS',name,int(np.count_nonzero(masks[i]>.1)),flush=True)
