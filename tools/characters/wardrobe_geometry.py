"""Собственный раскрой одежды без импорта геометрии из наборов.

Размеры в метрах. Раскрой редактируется до сглаживания и толщины;
нашивные детали строятся на поверхности после посадки ткани.
"""
import math
import bpy
import bmesh
from mathutils import Vector
import m02_custom_clothes as G

PI=math.pi
smooth=G.smooth
mix=G.mix
profile=G.profile
clamp=G.clamp

TOPS={
    'T00':dict(title='Grey cotton T-shirt',length=.950,sleeve=.375,width=.191,front=-.159,back=.129,opening=False,collar='rib',fabric='jersey',color=(.17,.18,.18)),
    'T01':dict(title='Checked everyday shirt',length=.936,sleeve=.735,width=.188,front=-.157,back=.131,opening=True,collar='fold',fabric='plaid',color=(.13,.16,.185)),
    'T02':dict(title='Blue work jacket',length=.969,sleeve=.740,width=.205,front=-.179,back=.148,opening=True,collar='fold',fabric='work_blue',color=(.035,.065,.105)),
    'T03':dict(title='Olive hooded windbreaker',length=.979,sleeve=.741,width=.203,front=-.176,back=.147,opening=True,collar='hood',fabric='nylon_olive',color=(.115,.128,.105)),
    'T04':dict(title='Burgundy track jacket',length=.979,sleeve=.739,width=.199,front=-.177,back=.142,opening=True,collar='stand',fabric='track_red',color=(.19,.035,.047)),
    'T05':dict(title='Combat shirt',length=.966,sleeve=.738,width=.188,front=-.159,back=.128,opening=False,collar='stand',fabric='combat_knit',color=(.075,.083,.066)),
    'T06':dict(title='Summer field jacket',length=.960,sleeve=.742,width=.195,front=-.170,back=.140,opening=True,collar='fold',fabric='field_olive',color=(.15,.16,.115)),
}
PANTS={
    'P01':dict(title='Straight five-pocket jeans',fabric='denim',hem=.107,width=.059,thigh=.190,color=(.035,.074,.106)),
    'P02':dict(title='Reinforced grey work trousers',fabric='work_grey',hem=.115,width=.064,thigh=.198,color=(.105,.109,.106)),
    'P03':dict(title='Olive cargo trousers',fabric='cargo_olive',hem=.112,width=.066,thigh=.199,color=(.16,.163,.117)),
    'P04':dict(title='Articulated field trousers',fabric='field_olive',hem=.169,width=.052,thigh=.198,color=(.15,.16,.115)),
}
SHOES={
    'F01':dict(title='Low trekking shoes',height=.105,fabric='suede',color=(.070,.055,.037)),
    'F02':dict(title='Brown leather work boots',height=.186,fabric='leather_brown',color=(.095,.051,.028)),
    'F03':dict(title='Tall brown field boots',height=.257,fabric='leather_field',color=(.16,.103,.055)),
}


def object_mesh(name,verts,faces,col,mat,sub=1,thickness=.0011,weld=False):
    obj=G.mesh_object(name,verts,faces,col,mat,weld=weld,sub=sub,thickness=thickness)
    obj['wardrobe_id']=col['wardrobe_id']
    return obj


def metric_uv(obj,kind='detail'):
    mesh=obj.data
    uv=mesh.uv_layers.get('UV_Fabric_Metres') or mesh.uv_layers.new(name='UV_Fabric_Metres')
    for face in mesh.polygons:
        centre=face.center
        for index in face.loop_indices:
            p=mesh.vertices[mesh.loops[index].vertex_index].co
            if kind=='top' and abs(centre.x)>.245:
                u=abs(p.x)-.24
                v=math.atan2(p.z-1.468,p.y+.005)*.052
            elif abs(face.normal.y)>=abs(face.normal.x):
                u=p.x
                v=p.z
            else:
                u=p.y
                v=p.z
            uv.data[index].uv=(u,v)
    mesh.uv_layers.active=uv
    return uv.name


def main_top(code,col,mats):
    cfg=TOPS[code]
    low=cfg['length']
    nx=64
    armrow=44
    heights=[mix(low,1.376,i/armrow) for i in range(armrow)]
    heights += [1.455+.080*math.sin(-PI/2+PI*i/16) for i in range(17)]
    nr=len(heights)
    verts=[]
    faces=[]
    panels={}
    material_faces=[]
    def xy(front,row,column):
        z=heights[row]
        u=2*column/nx-1
        width=profile(z,[(low,cfg['width']),(1.16,cfg['width']+.005),(1.34,.224),(1.46,.226),(1.54,.220)])
        x=u*width
        if row==0:
            # Закруглённый низ рубашки; прямой низ курток под резинку.
            if code in ['T01','T06']:
                z+=.021*abs(u)**4-.012*(1-u*u)
            z+=.0019*math.sin(27*x+.4)
        cut=10
        if row==nr-1:
            if abs(column-nx//2)<=cut:
                t=abs(column-nx//2)/cut
                base=1.467 if code=='T01' else 1.486 if code=='T06' else 1.512 if code in ['T00','T02'] else 1.527
                z=(base+(1.541-base)*t*t) if front else 1.537+.004*t*t
            else:
                z=1.542-.007*smooth(.07,.22,abs(x))
        fy=profile(z,[(low,cfg['front']),(1.10,cfg['front']),(1.29,-.160 if code in ['T00','T01','T05'] else -.180),(1.44,-.122),(1.54,-.088)])
        by=profile(z,[(low,cfg['back']),(1.10,cfg['back']),(1.30,.112),(1.44,.085),(1.54,.059)])
        cy=(fy+by)/2
        radius=(by-fy)/2
        shoulder=.065*math.sqrt(max(0,1-((heights[row]-1.455)/.08)**2)) if row>=armrow else 0
        sideblend=abs(u)**10
        cy=mix(cy,-.009,sideblend)
        y=cy+(-1 if front else 1)*(radius*math.sqrt(max(0,1-u*u))+sideblend*shoulder)
        # Крупные складки идут от плеча и проймы, нижние имеют другую фазу.
        hanging=(1-smooth(1.20,1.42,z))*(.0042*math.sin(38*x+3*z)+.0013*math.sin(76*x-7*z))
        diagonal=z-(1.33-.50*(.21-abs(x)))
        tension=.0025*math.exp(-(diagonal/.07)**2)*math.sin(85*diagonal+.8*x)
        y+=(-1 if front else 1)*(hanging+tension)*(1-abs(u)**10)
        if row==nr-1 and abs(column-nx//2)<=cut:
            t=abs(column-nx//2)/cut
            y=(-.078 if front else .051)*math.sqrt(max(0,1-t*t))-.008*t*t
        if front and cfg['opening'] and column==nx//2:
            # Кромки застёжки принадлежат своим половинам переда.
            x=0
        return Vector((x,y,z))
    for label,front,columns in [('back',False,list(range(nx+1))),
        ('frontR',True,list(range(nx//2+1))),('frontL',True,list(range(nx//2,nx+1)))]:
        ids=[]
        for row in range(nr):
            entries=[]
            for column in columns:
                p=xy(front,row,column)
                # Под застёжкой сохраняется сшитая основа: застёгнутая вещь
                # не должна распахиваться при расчёте посадки.
                entries.append(len(verts))
                verts.append(p)
            ids.append(entries)
        panels[label]=(ids,columns)
        for row in range(nr-1):
            for c in range(len(columns)-1):
                a,b=ids[row][c],ids[row][c+1]
                faces.append((a,b,ids[row+1][c+1],ids[row+1][c]))
                material_faces.append(0)
    def front_at(row,column):
        key='frontR' if column<=nx//2 else 'frontL'
        ids,columns=panels[key]
        return ids[row][columns.index(column)]
    back=panels['back'][0]
    # Узкие полосы плеча позволяют ткани изгибаться по пройме.
    for column in range(nx):
        if nx//2-10<=column<nx//2+10: continue
        a,b=front_at(nr-1,column),front_at(nr-1,column+1)
        last=[a,b]
        for strip in range(1,7):
            t=strip/6
            if strip==6: nxt=[back[-1][column],back[-1][column+1]]
            else:
                nxt=[]
                for front_index,back_index in [(a,back[-1][column]),(b,back[-1][column+1])]:
                    p=verts[front_index].lerp(verts[back_index],t)
                    p.z+=.006*math.sin(PI*t)
                    nxt.append(len(verts)); verts.append(p)
            faces.append((last[0],last[1],nxt[1],nxt[0])); material_faces.append(0)
            last=nxt
    for side,column in [(-1,0),(1,nx)]:
        ring=[front_at(r,column) for r in range(armrow,nr)]
        ring += [back[r][column] for r in range(nr-2,armrow,-1)]
        original=ring[:]
        n=len(ring)
        end=cfg['sleeve']
        steps=17 if code=='T00' else 48
        for row in range(1,steps+1):
            t=row/steps
            x=mix(.222,end,t)
            elbow=math.exp(-((x-.452)/.065)**2)
            cuff=math.exp(-((x-(end-.035))/.04)**2)
            radius=profile(x,[(.22,.064),(.34,.055),(.45,.050),(.57,.045),(end,.033 if code!='T00' else .052)])
            nxt=[]
            for j,old_index in enumerate(original):
                theta=-PI/2+2*PI*j/n
                target=Vector((side*end,-.005-.052*math.cos(theta),1.465+.055*math.sin(theta)))
                p=verts[old_index].lerp(target,t)
                p.x=side*x
                if code!='T00':
                    centre_z=mix(1.455,1.469,t)
                    fold=.0035*math.sin(127*x+3*theta)*elbow+.0030*math.sin(153*x-2*theta)*cuff
                    ry=radius+fold
                    p.y=-.003-ry*math.cos(theta)
                    p.z=centre_z+(radius+.002)*math.sin(theta)+.0018*math.sin(72*x+theta)*elbow
                else:
                    p.y+=.0022*math.sin(3*theta+4*t)*math.sin(PI*t)
                nxt.append(len(verts));verts.append(p)
            for j in range(n):
                k=(j+1)%n
                faces.append((ring[j],ring[k],nxt[k],nxt[j]))
                material_faces.append(1 if code=='T05' else 0)
            ring=nxt
    obj=object_mesh(code+' | sewn main surface',verts,faces,col,mats[cfg['fabric']],sub=2,weld=True)
    if code=='T05':
        obj.data.materials.append(mats['field_olive'])
        for index,face in enumerate(obj.data.polygons):
            # Центры рукавов однозначно отделяют тканый материал от трикотажа.
            if abs(face.center.x)>.215: face.material_index=1
    metric_uv(obj,'top')
    obj['pattern']='Original sewn front, back, shoulder and sleeve panels; metres-based grain UV.'
    return obj


def garment_drape(obj,collider,frames=20):
    """Сохранить раскрой и записать посадку ткани отдельной формой."""
    hidden=[(modifier,modifier.show_viewport,modifier.show_render) for modifier in obj.modifiers]
    for modifier,_,_ in hidden: modifier.show_viewport=False;modifier.show_render=False
    pins=obj.vertex_groups.new(name='Construction | garment support')
    code=obj['wardrobe_id']
    for vertex in obj.data.vertices:
        p=vertex.co
        weight=0
        if code.startswith('T'):
            if p.z>1.526 and abs(p.x)<.125: weight=1
            if abs(p.x)<.078 and p.z>1.51: weight=1
            if abs(p.x)>.70 and p.z>1.47: weight=.85
        else:
            if p.z>1.035: weight=1
        if weight: pins.add([vertex.index],weight,'REPLACE')
    cloth=obj.modifiers.new('Gravity drape | construction cache','CLOTH')
    settings=cloth.settings
    settings.quality=7
    settings.mass=.20
    settings.tension_stiffness=30
    settings.compression_stiffness=30
    settings.shear_stiffness=18
    settings.bending_stiffness=.28 if code in ['T00','T03','T04'] else .55
    settings.vertex_group_mass=pins.name
    settings.pin_stiffness=1
    settings.air_damping=4
    cloth.collision_settings.use_collision=True
    cloth.collision_settings.distance_min=.0045
    cloth.collision_settings.collision_quality=4
    cloth.collision_settings.use_self_collision=False
    cloth.point_cache.frame_start=1
    cloth.point_cache.frame_end=frames
    scene=bpy.context.scene
    scene.frame_set(1)
    for frame in range(2,frames+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        _=len(evaluated.data.vertices)
    evaluated=obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    result=[vertex.co.copy() for vertex in evaluated.data.vertices]
    assert len(result)==len(obj.data.vertices)
    obj.modifiers.remove(cloth)
    if not obj.data.shape_keys: obj.shape_key_add(name='Basis | original sewing draft')
    shape=obj.shape_key_add(name='Gravity drape | editable settled form')
    for point,co in zip(shape.data,result): point.co=co
    shape.value=1
    for modifier,viewport,render in hidden: modifier.show_viewport=viewport;modifier.show_render=render
    scene.frame_set(1)
    bpy.context.view_layer.update()
    return max((a.co-b.co).length for a,b in zip(obj.data.vertices,shape.data))


def resolve_layers(obj,under,clearance=.010):
    """Развести тонкие слои после посадки без нестабильных двусторонних коллизий."""
    surface=outer_surface(under)
    shape=obj.data.shape_keys.key_blocks[-1] if obj.data.shape_keys else None
    points=shape.data if shape else obj.data.vertices
    adjusted=0
    for vertex in points:
        p=vertex.co.copy()
        if p.z>1.10: continue
        fy,by=surface.ys(p.x,p.z,fallback=(10,-10))
        if fy>by: continue
        near,normal,_,distance=surface.nearest(p)
        if near is None: continue
        radial=Vector((near.x,near.y+.02,0))
        if normal.dot(radial)<0: normal=-normal
        inside=fy<=p.y<=by
        if inside or distance<clearance:
            # Наружная нормаль разводит также боковые швы, сохраняя сваренный
            # стык передней и задней половин верхней вещи.
            if normal.dot(p-near)<0 or inside:
                vertex.co=near+normal*clearance;adjusted+=1
            elif distance<clearance:
                vertex.co=near+normal*clearance;adjusted+=1
    bpy.context.view_layer.update()
    return adjusted


def outer_surface(obj):
    modifiers=[modifier for modifier in obj.modifiers if modifier.type=='SOLIDIFY' and modifier.show_viewport]
    for modifier in modifiers: modifier.show_viewport=False
    bpy.context.view_layer.update()
    surface=G.BodySurface(obj)
    for modifier in modifiers: modifier.show_viewport=True
    bpy.context.view_layer.update()
    return surface


def path_on(surface,coordinates,front=-1,offset=.002):
    result=[]
    for x,z in coordinates:
        y=surface.ys(x,z)[0 if front<0 else 1]+front*offset
        result.append(Vector((x,y,z)))
    return result


def patch(name,col,surface,mat,thread,x0,x1,z0,z1,front=-1,flap=False):
    obj=G.front_patch(name,surface,col,mat,thread,x0,x1,z0,z1,front=front,bulge=.0009,taper=.025)
    obj['wardrobe_id']=col['wardrobe_id']
    metric_uv(obj)
    if flap:
        flap_obj=G.front_patch(name+' | folded flap',surface,col,mat,thread,x0-.003,x1+.003,z1-.022,z1+.012,front=front,bulge=.0014,taper=.05)
        flap_obj['wardrobe_id']=col['wardrobe_id'];metric_uv(flap_obj)
    return obj


def strip(name,path,width,col,mat):
    verts=[]
    for p in path:
        for dx in [-width/2,-width/2+.0008,width/2-.0008,width/2]: verts.append(Vector(p)+Vector((dx,0,0)))
    faces=[(4*i+j,4*i+j+1,4*i+j+5,4*i+j+4) for i in range(len(path)-1) for j in range(3)]
    obj=object_mesh(name,verts,faces,col,mat,sub=1,thickness=.0010)
    metric_uv(obj)
    return obj


def button(name,p,col,mat,radius=.0037,normal=(0,-1,0)):
    p=Vector(p);n=Vector(normal).normalized()
    across=n.cross(Vector((0,0,1))).normalized()
    up=across.cross(n).normalized()
    verts=[];faces=[]
    for depth,r in [(0,.85*radius),(.0012,radius),(.0018,.91*radius)]:
        for i in range(24):
            t=2*PI*i/24
            verts.append(p+across*(r*math.cos(t))+up*(r*math.sin(t))+n*depth)
    for row in range(2):
        for i in range(24):
            j=(i+1)%24;faces.append((row*24+i,row*24+j,(row+1)*24+j,(row+1)*24+i))
    faces.append(tuple(48+i for i in range(24)))
    obj=object_mesh(name,verts,faces,col,mat,sub=0,thickness=0)
    metric_uv(obj)
    holes=[]
    for sign in [-1,1]:
        a=p+across*sign*.0012+up*.0010+n*.0020
        b=p+across*(-sign)*.0012-up*.0010+n*.0020
        holes.append([a,b])
    G.line_mesh(name+' | crossing thread',holes,.00019,col,mat)
    return obj


def zipper(name,path,col,mats,width=.009):
    tape=strip(name+' | woven tape',path,width,col,mats['zip_tape'])
    teeth=[];faces=[]
    for i in range(len(path)-1):
        a,b=Vector(path[i]),Vector(path[i+1])
        length=(b-a).length
        count=max(1,int(length/.0028))
        for j in range(count):
            p=a.lerp(b,(j+.5)/count)+Vector((0,-.0014,0))
            for side in [-1,1]:
                base=len(teeth)
                for dz in [-.00075,.00075]:
                    for dx,dy in [(-.0012,0),(.0012,0),(.0012,-.0013),(-.0012,-.0013)]:
                        teeth.append(p+Vector((side*.0018+dx,dy,dz+side*.0005)))
                faces += [tuple(base+k for k in q) for q in [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)]]
    object_mesh(name+' | interlocking teeth',teeth,faces,col,mats['hardware'],sub=0,thickness=0)
    p=Vector(path[-1])+Vector((0,-.003,-.012))
    loop=[p+Vector((.0034*math.cos(2*PI*i/24),0,.0064*math.sin(2*PI*i/24))) for i in range(25)]
    G.line_mesh(name+' | pull tab',[loop],.0009,col,mats['hardware'])
    return tape


def collar(code,col,main,mats):
    cfg=TOPS[code]
    mat=mats['field_olive'] if code=='T05' else mats[cfg['fabric']]
    if cfg['collar']=='hood':
        verts=[];faces=[]
        n=48;rows=16
        for row in range(rows+1):
            t=row/rows
            for i in range(n+1):
                theta=PI*i/n
                x=mix(.074,.147,t)*math.cos(theta)
                y=mix(.001,.050,t)+mix(.040,.135,t)*math.sin(theta)
                z=mix(1.548,1.500-.075*math.sin(theta),t)+.016*math.sin(PI*t)
                z+=.0024*math.sin(5*theta+7*t)*math.sin(PI*t)
                verts.append((x,y,z))
        for row in range(rows):
            for i in range(n):
                a=row*(n+1)+i;faces.append((a,a+1,a+n+2,a+n+1))
        hood=object_mesh(code+' | folded hood shell',verts,faces,col,mat,sub=2,thickness=.002)
        metric_uv(hood)
        return
    verts=[];faces=[]
    n=64
    opening=cfg['opening'] or code=='T05'
    collar_rows=[0,.04,.25,.5,.75,.96,1]
    for row,t in enumerate(collar_rows):
        for i in range(n+1):
            opening_angle=.62 if cfg['collar']=='fold' else .075
            theta=-PI/2+(2*PI-2*opening_angle)*i/n+opening_angle if opening else 2*PI*i/n
            x=.069*math.cos(theta)
            y=-.010+.066*math.sin(theta)
            if cfg['collar']=='rib':
                p=Vector((x*(1+.065*t),y*(1+.065*t),1.539-.025*max(0,-math.sin(theta))-.004*t))
            elif cfg['collar']=='stand':
                p=Vector((x*(1-.045*t),y*(1-.045*t),1.538-.010*max(0,-math.sin(theta))+.028*t))
            else:
                flare=math.sin(PI*t/2)
                p=Vector((x*(1+.62*flare),y+math.sin(theta)*.026*flare,1.54+.023*math.sin(PI*t)-.014*flare))
                if math.sin(theta)<-.50:
                    p.z-=.038*flare
                    p.y-=.047*flare
            verts.append(p)
    for row in range(len(collar_rows)-1):
        for i in range(n):
            a=row*(n+1)+i;faces.append((a,a+1,a+n+2,a+n+1))
    obj=object_mesh(code+' | '+cfg['collar']+' collar',verts,faces,col,mat,sub=2,thickness=.0013)
    metric_uv(obj)


def lower_boundary(main,height):
    thickness=[modifier for modifier in main.modifiers if modifier.type=='SOLIDIFY']
    for modifier in thickness: modifier.show_viewport=False
    bpy.context.view_layer.update()
    evaluated=main.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh=evaluated.to_mesh()
    bm=bmesh.new();bm.from_mesh(mesh)
    edges={edge for edge in bm.edges if edge.is_boundary}
    paths=[]
    while edges:
        first=edges.pop();start=first.verts[0];current=first.verts[1]
        loop=[start,current]
        while current!=start:
            nxt=next((edge for edge in current.link_edges if edge in edges),None)
            if nxt is None: break
            edges.remove(nxt);current=nxt.other_vert(current);loop.append(current)
        if max(vertex.co.z for vertex in loop)<height+.07:
            paths.append([vertex.co+vertex.normal*.0008 for vertex in loop])
    bm.free();evaluated.to_mesh_clear()
    for modifier in thickness: modifier.show_viewport=True
    bpy.context.view_layer.update()
    return paths


def top_details(code,col,main,mats):
    cfg=TOPS[code]
    surface=G.BodySurface(main)
    mat=mats[cfg['fabric']]
    thread=mats['thread_dark']
    # Манжеты и низ следуют рассчитанной поверхности ткани.
    hem_paths=lower_boundary(main,cfg['length'])
    if code in ['T02','T03','T04']:
        z0=cfg['length']+.002
        for face in main.data.polygons:
            if face.center.z<z0+.027: face.material_index=0
        cuffmat=mats['rib_dark'] if code=='T04' else mat
        G.stitches(code+' | waist twin needle',[[p+Vector((0,0,.006)) for p in path] for path in hem_paths],col,thread)
    else:
        G.stitches(code+' | turned hem seam',[[p+Vector((0,0,.004)) for p in path] for path in hem_paths],col,thread)
    if code!='T00':
        for side in [-1,1]:
            end=cfg['sleeve']
            verts=[];faces=[]
            length=.034 if code in ['T01','T02','T06'] else .027
            cuffmat=mats['rib_dark'] if code=='T04' else mats['field_olive'] if code=='T05' else mat
            for row in range(5):
                x=side*(end-length*row/4)
                for i in range(40):
                    theta=2*PI*i/40
                    ry=.033+.0015*math.cos(3*theta)
                    verts.append((x,-.003+ry*math.cos(theta),1.469+(.034+.001*math.cos(2*theta))*math.sin(theta)))
            for row in range(4):
                for i in range(40):
                    j=(i+1)%40;faces.append((row*40+i,row*40+j,(row+1)*40+j,(row+1)*40+i))
            cuff=object_mesh(code+' | sleeve cuff '+str(side),verts,faces,col,cuffmat,sub=1,thickness=.0017)
            metric_uv(cuff)
            if code in ['T01','T02','T06']:
                button(code+' | cuff button '+str(side),(side*(end-.015),-.036,1.469),col,mats['button'])
    collar(code,col,main,mats)
    if code in ['T01','T06']:
        path=path_on(surface,[(.0,mix(cfg['length']+.015,1.505,i/60)) for i in range(61)],offset=.003)
        strip(code+' | button placket',path,.023,col,mat)
        for i in range(7):
            z=mix(cfg['length']+.042,1.46,i/6)
            button(code+' | front button '+str(i),path_on(surface,[(.002,z)],offset=.005)[0],col,mats['button'])
    elif code in ['T02','T03','T04']:
        path=path_on(surface,[(0,mix(cfg['length']+.006,1.525,i/100)) for i in range(101)],offset=.004)
        zipper(code+' | front zip',path,col,mats)
    elif code=='T05':
        path=path_on(surface,[(0,mix(1.387,1.547,i/40)) for i in range(41)],offset=.004)
        zipper(code+' | quarter zip',path,col,mats,width=.008)
    if code=='T01':
        patch(code+' | chest pocket',col,surface,mat,thread,.055,.135,1.267,1.367)
    if code in ['T02','T06']:
        for side in [-1,1]:
            x0,x1=sorted([side*.043,side*.143])
            patch(code+' | chest pocket '+str(side),col,surface,mat,thread,x0,x1,1.262,1.377,flap=True)
            button(code+' | pocket snap '+str(side),path_on(surface,[(side*.092,1.373)],offset=.006)[0],col,mats['hardware'],radius=.0032)
        # Кокетка спины с двойной строчкой.
        yoke=path_on(surface,[(mix(-.18,.18,i/60),1.392+.010*math.cos(PI*mix(-1,1,i/60))) for i in range(61)],front=1,offset=.002)
        G.stitches(code+' | back yoke stitching',[yoke,[p+Vector((0,0,.003)) for p in yoke]],col,thread)
    if code in ['T02','T03','T04']:
        for side in [-1,1]:
            coords=[(side*mix(.135,.106,t),mix(1.190,1.068,t)) for t in [i/30 for i in range(31)]]
            path=path_on(surface,coords,offset=.003)
            if code=='T02': strip(code+' | welt pocket '+str(side),path,.010,col,mat)
            else: zipper(code+' | pocket zip '+str(side),path,col,mats,width=.006)
    if code in ['T05','T06']:
        for side in [-1,1]:
            x0,x1=sorted([side*.278,side*.378])
            patch(code+' | upper sleeve pocket '+str(side),col,surface,mats['field_olive'],thread,x0,x1,1.430,1.514)
            # Усиление локтя прилегает к поверхности рукава.
            x0,x1=sorted([side*.418,side*.535])
            patch(code+' | elbow reinforcement '+str(side),col,surface,mats['field_olive'],thread,x0,x1,1.423,1.490,front=1)
    if code=='T04':
        for side in [-1,1]:
            points=[]
            for i in range(80):
                x=side*mix(.087,.714,i/79)
                z=1.522 if abs(x)>.23 else 1.534
                points.append(Vector((x,-.023,z)))
            G.line_mesh(code+' | cream shoulder piping '+str(side),[points],.0014,col,mats['piping'])
    return surface


def main_pants(code,col,mats,body):
    cfg=PANTS[code]
    verts=[];faces=[]
    nx=32
    crotch=.805
    heights=sorted(set([mix(cfg['hem'],1.067,i/92) for i in range(93)]+[crotch]))
    for side in [-1,1]:
        for front in [-1,1]:
            ids=[]
            for z in heights:
                row=[]
                centre=profile(z,[(.1,.09),(.50,.104),(.78,.105),(.90,.102),(1.067,.092)])
                radius=profile(z,[(.10,cfg['width']),(.34,.061),(.52,.066),(.70,.080),(.805,.101),(1.067,.092)])
                hip=smooth(crotch,crotch+.065,z)
                inner=mix(max(.007,centre-radius),0,smooth(.77,crotch,z))
                outer=profile(z,[(.10,centre+cfg['width']),(.50,.171),(.78,cfg['thigh']),(.91,.202),(1.067,.180)])
                fy,by=body.ys(side*centre,min(z,1.04),fallback=(-.085,.055))
                cy=(fy+by)/2
                ry=(by-fy)/2+.013+.020*(1-smooth(.10,.28,z))
                for i in range(nx+1):
                    u=i/nx
                    x=side*mix(inner,outer,u)
                    leg=math.sqrt(max(0,1-(2*u-1)**2))
                    full=math.sqrt(max(0,1-(abs(x)/outer)**2))
                    y=cy+front*ry*mix(leg,full,hip)
                    if z>crotch and u<.98:
                        a,b=body.ys(x,z,fallback=(y,y))
                        y=min(y,a-.011*hip) if front<0 else max(y,b+.011*hip)
                    if i==0 and z>=crotch:
                        a,b=body.ys(0,z)
                        y=(a+b)/2+front*((b-a)/2+.013)*hip
                    knee=math.exp(-((z-.53)/.075)**2)
                    ankle=math.exp(-((z-(cfg['hem']+.06))/.06)**2)
                    groin=math.exp(-((z-(.88-.23*u))/.045)**2)
                    # Веер складок сжатия заканчивается у швов штанины.
                    fold=(.0060*math.sin(105*z+4.3*u+side)*knee+
                          .0060*math.sin(135*z-6*u+side)*ankle+
                          .0045*math.sin(145*z+10*u)*groin)*math.sin(PI*u)
                    y+=front*fold
                    x+=side*.35*fold
                    row.append(len(verts));verts.append((x,y,z))
                ids.append(row)
            for row in range(len(heights)-1):
                for i in range(nx):
                    faces.append((ids[row][i],ids[row][i+1],ids[row+1][i+1],ids[row+1][i]))
    obj=object_mesh(code+' | sewn trouser panels',verts,faces,col,mats[cfg['fabric']],sub=2,weld=True,thickness=.0014)
    metric_uv(obj,'pants')
    return obj


def side_cargo(code,col,surface,mats,side,z0,z1,mat):
    verts=[];faces=[]
    n,m=16,16
    for row in range(m+1):
        v=row/m;z=mix(z0,z1,v)
        for i in range(n+1):
            u=i/n;y=mix(-.116,.045,u)
            point,*_=surface.tree.ray_cast(Vector((side*1,y,z)),Vector((-side,0,0)))
            x=point.x if point else side*.183
            x+=side*(.003+.009*math.sin(PI*u)*math.sin(PI*v))
            # Боковые складки и небольшое расширение объёма кармана.
            x+=side*.003*math.sin(4*PI*u)**2*math.sin(PI*v)
            verts.append(Vector((x,y,z)))
    for row in range(m):
        for i in range(n):
            a=row*(n+1)+i;faces.append((a,a+1,a+n+2,a+n+1))
    obj=object_mesh(code+' | bellows cargo pocket '+str(side),verts,faces,col,mat,sub=1,thickness=.0013)
    metric_uv(obj)
    flap=[];ff=[]
    for row in range(5):
        v=row/4;z=z1+.012-.038*v
        for i in range(n+1):
            y=mix(-.122,.049,i/n)
            point,*_=surface.tree.ray_cast(Vector((side*1,y,z)),Vector((-side,0,0)))
            x=point.x if point else side*.183
            flap.append(Vector((x+side*(.006+.002*math.sin(PI*v)),y,z)))
    for row in range(4):
        for i in range(n):
            a=row*(n+1)+i;ff.append((a,a+1,a+n+2,a+n+1))
    obj=object_mesh(code+' | cargo flap '+str(side),flap,ff,col,mat,sub=1,thickness=.0015)
    metric_uv(obj)
    paths=[[verts[row*(n+1)]+Vector((side*.001,0,0)) for row in range(m+1)],
           [verts[row*(n+1)+n]+Vector((side*.001,0,0)) for row in range(m+1)],
           [verts[i]+Vector((side*.001,0,0)) for i in range(n+1)]]
    G.stitches(code+' | cargo pocket stitches '+str(side),paths,col,mats['thread_dark'])


def pants_details(code,col,main,mats):
    cfg=PANTS[code]
    mat=mats[cfg['fabric']]
    thread=mats['thread_jeans'] if code=='P01' else mats['thread_dark']
    surface=G.BodySurface(main)
    for side in [-1,1]:
        x0,x1=sorted([side*.051,side*.149])
        patch(code+' | rear pocket '+str(side),col,surface,mat,thread,x0,x1,.902,1.015,front=1,flap=code in ['P03','P04'])
        curve=[]
        for i in range(35):
            t=i/34;x=side*mix(.157,.066,t);z=1.050-.083*math.sin(PI*t/2)
            curve.append((x,z))
        entry=path_on(surface,curve,offset=.0025)
        G.line_mesh(code+' | front pocket welt '+str(side),[entry],.0009,col,mat)
        G.stitches(code+' | pocket entry stitches '+str(side),[entry],col,thread)
        if code in ['P02','P04']:
            x0,x1=sorted([side*.036,side*.159])
            patch(code+' | double knee '+str(side),col,surface,mat,thread,x0,x1,.392,.706)
        if code in ['P02','P03','P04']:
            side_cargo(code,col,surface,mats,side,.626,.820,mat)
        if code=='P01':
            path=path_on(surface,[(side*mix(.064,.137,i/30),.946-.016*math.sin(PI*i/30)) for i in range(31)],front=1,offset=.004)
            G.stitches(code+' | rear pocket V stitch '+str(side),[path],col,thread)
        # Две боковые строчки и настоящий открытый подогнутый низ.
        line=[]
        for i in range(85):
            z=mix(cfg['hem']+.005,1.049,i/84)
            target,*_=surface.tree.ray_cast(Vector((side*1,-.02,z)),Vector((-side,0,0)))
            if target: line.append(target+Vector((side*.0018,0,0)))
        G.stitches(code+' | outer leg seam '+str(side),[line],col,thread)
    if code=='P01':
        patch(code+' | coin pocket',col,surface,mat,thread,.095,.139,1.010,1.049)
    if code=='P03':
        patch(code+' | repaired knee',col,surface,mats['repair_olive'],thread,-.158,-.047,.460,.617)
    path=path_on(surface,[(.004,mix(.904,1.065,i/45)) for i in range(46)],offset=.003)
    strip(code+' | fly placket',path,.024,col,mat)
    button(code+' | waistband button',path_on(surface,[(.004,1.061)],offset=.005)[0],col,mats['hardware'],radius=.0040)
    for x,front in [(-.145,-1),(.145,-1),(-.144,1),(.144,1),(0,1)]:
        path=path_on(surface,[(x,mix(1.023,1.070,i/10)) for i in range(11)],front=front,offset=.003)
        strip(code+' | belt loop',path,.008,col,mat)
    return surface


def make_collider(body,col,extras=None):
    verts=[];faces=[]
    for source in [body]+list(extras or []):
        if source.type!='MESH': continue
        evaluated=source.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh=evaluated.to_mesh()
        base=len(verts)
        verts.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        faces.extend(tuple(base+index for index in face.vertices) for face in mesh.polygons)
        evaluated.to_mesh_clear()
    mesh=bpy.data.meshes.new('Layered anatomical garment collider')
    mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new('Construction | anatomical collision surface',mesh)
    col.objects.link(obj)
    obj.hide_render=True
    obj.display_type='WIRE'
    obj.modifiers.new('Static garment fitting collision','COLLISION')
    obj.collision.thickness_outer=.003
    obj.collision.thickness_inner=.002
    obj.collision.cloth_friction=6
    return obj


def linear_profile(z,keys):
    if z<=keys[0][0]: return keys[0][1]
    for (a,x),(b,y) in zip(keys,keys[1:]):
        if z<=b: return mix(x,y,(z-a)/(b-a))
    return keys[-1][1]


def shoe_height(z,code):
    return linear_profile(z,[(0,0),(.006,.006),(.045,.040),(.075,.060 if code=='F01' else .072),
        (.120,.083 if code=='F01' else .145 if code=='F03' else .125),(.178,SHOES[code]['height'])]) if z>=.006 else z


def shoe_point(side,u,theta,code,offset=0):
    fy=linear_profile(u,[(0,-.228),(.08,-.226),(.18,-.215),(.27,-.190),(.36,-.149),(.46,-.108),(.58,-.077),(.75,-.065),(1,-.062)])
    by=linear_profile(u,[(0,.068),(.20,.062),(.45,.051),(.75,.048),(1,.055)])
    y=mix((fy+by)/2,fy if math.sin(theta)<0 else by,abs(math.sin(theta)))
    width=profile(y,[(-.230,.044),(-.160,.058),(-.080,.049),(.015,.043),(.070,.039)])
    width=mix(width,.050,smooth(.35,.80,u))
    cx=mix(side*.083,side*.096,smooth(.22,.7,u))
    p=Vector((cx+width*math.cos(theta),y,shoe_height(.006+.172*u,code)))
    normal=Vector((p.x-cx,p.y-(fy+by)/2,.15*math.sin(PI*u))).normalized()
    return p+normal*offset


def shoe_overlay(code,col,mats,side,title,u0,u1,t0,t1,material):
    verts=[];faces=[]
    nx,nz=30,12
    for row in range(nz+1):
        v=row/nz
        for i in range(nx+1):
            t=i/nx
            u=mix(u0,u1,v)
            theta=mix(t0,t1,t)
            u+=.022*math.sin(PI*t)*math.sin(PI*v)
            p=shoe_point(side,u,theta,code,.0027)
            label='L' if side>0 else 'R'
            upper=next(obj for obj in col.objects if 'Boot '+label+' | leather quarters and vamp' in obj.name)
            surface=G.BodySurface(upper) if row==0 and i==0 else surface
            point,normal,_,_=surface.nearest(p)
            verts.append(point+normal*.0024 if point is not None else p)
    for row in range(nz):
        for i in range(nx):
            a=row*(nx+1)+i;faces.append((a,a+1,a+nx+2,a+nx+1))
    obj=object_mesh(code+' | '+title+' '+str(side),verts,faces,col,mats[material],sub=1,thickness=.0015)
    metric_uv(obj)
    boundary=[verts[i]+Vector((0,0,.0005)) for i in range(nx+1)]
    boundary += [verts[row*(nx+1)+nx]+Vector((0,0,.0005)) for row in range(1,nz+1)]
    boundary += [verts[nz*(nx+1)+i]+Vector((0,0,.0005)) for i in range(nx-1,-1,-1)]
    boundary += [verts[row*(nx+1)]+Vector((0,0,.0005)) for row in range(nz-1,0,-1)]
    G.stitches(code+' | '+title+' stitch '+str(side),[boundary+[boundary[0]]],col,mats['thread_boot'],radius=.00021)
    return obj


def footwear(code,col,mats):
    cfg=SHOES[code]
    base_mats={'rubber':mats['rubber'],'leather':mats['trek_mesh'] if code=='F01' else mats[cfg['fabric']],
        'thread':mats['thread_boot'],'metal':mats['hardware'],'rib':mats['rib_dark']}
    saved_profile=G.profile
    G.profile=linear_profile
    try: G.boots(col,base_mats,None)
    finally: G.profile=saved_profile
    for obj in list(col.objects):
        obj.name=code+' | '+obj.name
        obj['wardrobe_id']=code
        for vertex in obj.data.vertices:
            vertex.co.z=shoe_height(vertex.co.z,code)
        metric_uv(obj)
    for side in [-1,1]:
        mat='suede' if code=='F01' else cfg['fabric']
        shoe_overlay(code,col,mats,side,'toe reinforcement',.025,.255,PI*.94,PI*2.06,mat)
        shoe_overlay(code,col,mats,side,'heel counter',.06,.67,-.05,PI+.05,mat)
        for i,(a,b) in enumerate([(-.35,.52),(PI-.52,PI+.35)]):
            shoe_overlay(code,col,mats,side,'side overlay '+str(i),.25,.84,a,b,mat)
        if code=='F03':
            for i,(a,b) in enumerate([(-.10,1.18),(PI-1.18,PI+.10)]):
                shoe_overlay(code,col,mats,side,'woven shaft panel '+str(i),.66,.99,a,b,'field_olive')
        # Светлая промежуточная подошва треккингового ботинка — отдельная деталь.
        if code=='F01':
            contour=[shoe_point(side,.005,2*PI*i/80,code,.002)+Vector((0,0,-.004)) for i in range(81)]
            G.line_mesh(code+' | sand midsole perimeter '+str(side),[contour],.0040,col,mats['midsole'])
        # Задняя петля повторяет форму мягкого края обуви.
        height=cfg['height']
        tab=[];faces=[]
        for row in range(13):
            t=row/12
            for x in [-.006,.006]:
                tab.append((side*.096+x,.050+.010*math.sin(PI*t),height-.020+.032*t))
        faces=[(2*i,2*i+1,2*i+3,2*i+2) for i in range(12)]
        obj=object_mesh(code+' | heel pull tab '+str(side),tab,faces,col,mats['rib_dark'],sub=1,thickness=.0015)
        metric_uv(obj)
    return list(col.objects)
