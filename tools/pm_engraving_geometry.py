"""Native, fresh-file engraving measurements and in-memory render caching."""
import bpy, bmesh
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def engraving_report(record,optic_only=False):
    if optic_only:record=dict(markings=[r for r in record['markings'] if r['host'].startswith('Reflex |')],expected_markings=18)
    dg=bpy.context.evaluated_depsgraph_get();trees={};rows=[]
    for row in record['markings']:
        root=bpy.data.objects[row.get('reference_root','PM_ReflexSight • asset root')];mw=root.matrix_world
        host=bpy.data.objects[row['host']];cutter=bpy.data.objects[row['cutter']]
        if host.name not in trees:
            eo=host.evaluated_get(dg);me=eo.to_mesh()
            trees[host.name]=BVHTree.FromPolygons([eo.matrix_world@v.co for v in me.vertices],[tuple(p.vertices) for p in me.polygons]);eo.to_mesh_clear()
        normal=(mw.to_3x3().inverted().transposed()@Vector(row['normal_local'])).normalized()
        plane=(mw@Vector(row['plane_point_local'])).dot(normal);measurements=[]
        for sample in row['samples_local']:
            p=mw@Vector(sample);hit,_,_,_=trees[host.name].ray_cast(p+normal*.004,-normal,.015)
            depth=(plane-hit.dot(normal))*1000 if hit else None
            measurements.append(dict(depth_mm=depth,pass_depth=depth is not None and .60*row['depth_mm']<=depth<=1.40*row['depth_mm']))
        operands=[m for m in host.modifiers if m.type=='BOOLEAN' and m.name.startswith('ENGRAVE |') and m.object==cutter]
        bm=bmesh.new();bm.from_mesh(cutter.data)
        solid=all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True)>0;bm.free()
        valid=bool(operands) and all(m.operation=='DIFFERENCE' and m.show_render and m.show_viewport for m in operands)
        hidden=cutter.hide_render and cutter.hide_get() and bool(cutter.get('PM engraving helper'))
        rows.append(dict(text=row['text'],host=host.name,cutter=cutter.name,measurements=measurements,
            depth_target_mm=row['depth_mm'],solid_operand=solid,hidden_operand=hidden,
            native_difference=valid,pass_engraving=solid and hidden and valid and all(m['pass_depth'] for m in measurements)))
    visible_sources=[o.name for o in bpy.data.objects if o.get('Engraving role') in {'Editable lettering master','Editable symbol master'} and not o.hide_render]
    return dict(markings=rows,visible_sources=visible_sources,pass_engraving=len(rows)==record.get('expected_markings',18) and not visible_sources and all(r['pass_engraving'] for r in rows))


def cache_engraving_preview():
    """Freeze evaluated cuts only in this unsaved inspection process."""
    dg=bpy.context.evaluated_depsgraph_get()
    hosts=[o for o in bpy.data.objects if any(m.type=='BOOLEAN' and m.name.startswith('ENGRAVE |') for m in o.modifiers)]
    cached=[(o,bpy.data.meshes.new_from_object(o.evaluated_get(dg),depsgraph=dg)) for o in hosts]
    for host,mesh in cached:
        host.data=mesh;host.modifiers.clear()
    bpy.context.view_layer.update()
    return [o.name for o in hosts]


def paint_fill_report():
    import importlib
    U=importlib.import_module('bl_ext.blender_org.ucupaint')
    material=bpy.data.materials['КОРС-9 • светлая краска в клеймах']
    bsdf=next(n for n in material.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
    group=next(n for n in material.node_tree.nodes if n.type=='GROUP' and getattr(n.node_tree,'yp',None) and n.node_tree.yp.is_ypaint_node)
    tree=group.node_tree;layers=[]
    for layer in tree.yp.layers:
        channels={root.name:dict(enabled=ch.enable,override=ch.override,
            actual=list(U.common.get_entity_prop_value(ch,'override_color')) if root.type=='RGB' else U.common.get_entity_prop_value(ch,'override_value')) for root,ch in zip(tree.yp.channels,layer.channels)}
        layers.append(dict(name=layer.name,enabled=layer.enable,channels=channels,masks=[dict(name=m.name,type=m.type,modifiers=[x.type for x in m.modifiers]) for m in layer.masks]))
    wired={name:bool(bsdf.inputs[name].links) and bsdf.inputs[name].links[0].from_node==group for name in ('Base Color','Metallic','Roughness','Normal')}
    noise_layers=[r for r in layers if any(m['type']=='NOISE' and 'RAMP' in m['modifiers'] for m in r['masks'])]
    return dict(material=material.name,native_version=U.common.get_current_version_str(),layers=layers,wired=wired,
        pass_paint=len(layers)==2 and all(x['enabled'] for x in layers) and len(noise_layers)==1 and all(wired.values()))


def solid_from_cap(vertices,faces,normal,depth):
    """Extrude a clean, planar cap; FONT's native extrude leaves open seams."""
    triangles=[]
    for face in faces:
        if len(face)<3:continue
        cross=(vertices[face[1]]-vertices[face[0]]).cross(vertices[face[2]]-vertices[face[0]])
        if cross.length<1e-16:continue
        triangles.append(tuple(face if cross.dot(normal)>0 else reversed(face)))
    edges={}
    for face in triangles:
        for a,b in zip(face,face[1:]+face[:1]):
            key=tuple(sorted((a,b)))
            if key not in edges:edges[key]=[0,a,b]
            edges[key][0]+=1
    if any(count>2 for count,_,_ in edges.values()):raise RuntimeError('Overlapping planar engraving cap')
    n=len(vertices);solid=vertices+[p+normal*(depth+.00025) for p in vertices]
    walls=[(a,b,b+n,a+n) for count,a,b in edges.values() if count==1]
    return solid,[tuple(reversed(f)) for f in triangles]+[tuple(i+n for i in f) for f in triangles]+walls

def stroke_cap(source,normal,plane,depth):
    """Continuous mitered ribbon: no overlapping tubular end caps."""
    points=[source.matrix_world@Vector(p.co[:3]) for p in source.data.splines[0].points]
    closed=(points[0]-points[-1]).length<1e-7 or source.data.splines[0].use_cyclic_u
    if closed and (points[0]-points[-1]).length<1e-7:points.pop()
    points=[p+normal*(plane-depth-p.dot(normal)) for p in points]
    radius=source.data.bevel_depth*abs(source.matrix_world.determinant())**(1/3)
    tangents=[(points[(j+1)%len(points)]-p).normalized() for j,p in enumerate(points) if closed or j<len(points)-1]
    sides=[normal.cross(t).normalized() for t in tangents];vertices=[]
    for j,p in enumerate(points):
        if not closed and j==0:offset=sides[0]*radius
        elif not closed and j==len(points)-1:offset=sides[-1]*radius
        else:
            a=sides[(j-1)%len(sides)];b=sides[j%len(sides)];m=(a+b).normalized()
            offset=m*min(3*radius,radius/max(.1,m.dot(b)))
        vertices.extend((p+offset,p-offset))
    faces=[(2*j,2*j+1,2*((j+1)%len(points))+1,2*((j+1)%len(points))) for j in range(len(tangents))]
    return vertices,faces
