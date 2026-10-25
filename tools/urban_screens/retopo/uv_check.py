"""Exact separating-axis UV-triangle overlap test with spatial bins."""
import math
import numpy as np


def audit(objects, details=False):
    triangles=[]
    owners=[]
    for ob in objects:
        me=ob.data
        me.calc_loop_triangles()
        layer=me.uv_layers.get('BakeUV')
        if not layer:
            return dict(passed=False,errors=['Missing BakeUV: '+ob.name])
        data=np.empty(len(me.loops)*2,np.float64)
        layer.data.foreach_get('uv',data)
        idx=np.array([tuple(t.loops) for t in me.loop_triangles],np.int32)
        triangles.append(data.reshape(-1,2)[idx])
        owners.extend([ob.name]*len(idx))
    uv=np.concatenate(triangles)
    nonfinite=int(np.count_nonzero(~np.isfinite(uv)))
    out=int(np.count_nonzero((uv<-.000001)|(uv>1.000001)))
    area2=np.abs(np.cross(uv[:,1]-uv[:,0],uv[:,2]-uv[:,0]))
    zero=np.flatnonzero(area2<1e-14)
    low=uv.min(axis=1); high=uv.max(axis=1)
    count=max(16,min(256,int(math.sqrt(len(uv)/8))))
    bins={}
    for i,(lo,hi) in enumerate(zip(np.floor(low*count).astype(int),np.floor(high*count).astype(int))):
        if i in zero:
            continue
        for x in range(max(0,lo[0]),min(count-1,hi[0])+1):
            for y in range(max(0,lo[1]),min(count-1,hi[1])+1):
                bins.setdefault((x,y),[]).append(i)
    overlaps=set()
    tested=0
    for ids in bins.values():
        if len(ids)<2:
            continue
        ids=np.array(ids,np.int32)
        i,j=np.triu_indices(len(ids),1)
        aa,bb=ids[i],ids[j]
        box=(np.minimum(high[aa],high[bb])-np.maximum(low[aa],low[bb])>2e-8).all(axis=1)
        aa,bb=aa[box],bb[box]
        if not len(aa):
            continue
        for start in range(0,len(aa),50000):
            ia,ib=aa[start:start+50000],bb[start:start+50000]
            a,b=uv[ia],uv[ib]
            edges=np.concatenate((a[:,[1,2,0]]-a,b[:,[1,2,0]]-b),axis=1)
            axes=np.stack((-edges[:,:,1],edges[:,:,0]),axis=-1)
            pa=np.einsum('pvc,pac->pav',a,axes)
            pb=np.einsum('pvc,pac->pav',b,axes)
            distance=np.minimum(pa.max(axis=2),pb.max(axis=2))-np.maximum(pa.min(axis=2),pb.min(axis=2))
            good=(distance>2e-8*np.linalg.norm(axes,axis=2)).all(axis=1)
            tested+=len(ia)
            for u,v in zip(ia[good],ib[good]):
                overlaps.add((int(min(u,v)),int(max(u,v))))
    result=dict(passed=not nonfinite and not out and not len(zero) and not overlaps,
        triangles=len(uv),nonfinite_values=nonfinite,out_of_bounds_values=out,
        zero_area_triangles=len(zero),overlap_pairs=len(overlaps),tested_pairs=tested,
        overlap_examples=[dict(a=owners[a],b=owners[b],triangles=[a,b]) for a,b in sorted(overlaps)[:12]],
        zero_examples=[owners[i] for i in zero[:12]],
        method='All atlas triangles; spatial bins; six separating axes; shared edges allowed; 2e-8 UV tolerance')
    if details:
        result['repair_triangles']=sorted(set(zero.tolist())|{i for pair in overlaps for i in pair})
    return result
