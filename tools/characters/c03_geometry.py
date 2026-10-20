"""Художественная доводка C03: мягкие полотна и низкая треккинговая обувь.

Размеры в метрах. Складки заданы непериодическими линиями натяжения,
геометрия обуви построена самостоятельно, исходное тело не изменяется.
"""
import math
import bpy
import bmesh
from mathutils import Vector
import m02_custom_clothes as G
import wardrobe_geometry as W
import wardrobe_balaclavas as B

PI=math.pi


def mesh(name,verts,faces,col,mat,sub=1,thickness=.0008):
    ob=G.mesh_object(name,verts,faces,col,mat,weld=True,sub=sub,thickness=thickness)
    ob['wardrobe_id']=col['wardrobe_id'];W.metric_uv(ob)
    return ob


def densify(ob):
    G.activate(ob)
    mod=next((m for m in ob.modifiers if m.type=='SUBSURF'),None)
    if mod:
        mod.levels=1;bpy.ops.object.modifier_apply(modifier=mod.name)
    mod=ob.modifiers.new('Editable final surface smoothing','SUBSURF');mod.levels=1;mod.render_levels=1


def relax(ob,steps=4,factor=.30):
    bm=bmesh.new();bm.from_mesh(ob.data)
    verts=[v for v in bm.verts if not v.is_boundary]
    for _ in range(steps):
        bmesh.ops.smooth_vert(bm,verts=verts,factor=factor,use_axis_x=True,use_axis_y=True,use_axis_z=True)
    bm.to_mesh(ob.data);bm.free();ob.data.update()


def ridge(x,z,path,width,amplitude):
    # Отрезок изгибается в одном месте; концы складки затухают в ткани.
    best=1e9;along=0;total=sum((Vector(b)-Vector(a)).length for a,b in zip(path,path[1:]));offset=0
    p=Vector((x,z))
    for a,b in zip(path,path[1:]):
        a,b=Vector(a),Vector(b);d=b-a;length=d.length
        t=G.clamp((p-a).dot(d)/max(d.length_squared,1e-12));q=a+d*t
        dist=(p-q).length
        if dist<best: best=dist;along=(offset+t*length)/max(total,1e-9)
        offset+=length
    end=math.sin(PI*G.clamp(along))**.55
    return amplitude*end*(math.exp(-(best/width)**2)-.38*math.exp(-(best/(width*2.4))**2))


def sculpt_top(ob):
    relax(ob,6,.28);densify(ob)
    ob.shape_key_add(name='Basis | sewn windbreaker pattern')
    key=ob.shape_key_add(name='Artist | cloth tension and elastic gathers');key.value=1
    paths=[([(.032,1.10),(.10,1.14),(.19,1.225)],.015,.012),
           ([(.036,1.265),(.12,1.294),(.204,1.365)],.010,.008),
           ([(.09,1.055),(.12,1.13),(.146,1.19)],.014,.008),
           ([(-.025,1.13),(-.105,1.19),(-.19,1.24)],.014,.010),
           ([(-.06,1.32),(-.13,1.35),(-.211,1.394)],.012,.007),
           ([(-.17,1.04),(-.142,1.13),(-.16,1.21)],.012,.009),
           ([(-.06,1.41),(-.13,1.43),(-.20,1.41)],.016,.006)]
    for v in key.data:
        p=v.co;x,y,z=p
        if abs(x)<.225:
            u=G.clamp(x/.216,-1,1);front=y<-.008
            if z<1.15:
                fade=1-G.smooth(1.10,1.15,z)
                width=G.profile(z,[(.979,.191),(1.02,.207),(1.08,.213),(1.15,.204)])
                p.x=G.mix(x,u*width,fade)
                desired=(-.162 if front else .137)*math.sqrt(max(0,1-u*u))-.008
                p.y=G.mix(y,desired,fade*.80)
            amount=sum(ridge(x,z,path,w,a) for path,w,a in paths)
            if not front: amount=.65*sum(ridge(-x,z+.015,path,w*1.3,a) for path,w,a in paths)
            for anchor in [-.174,-.129,-.075,-.021,.041,.087,.153,.182]:
                line=[(anchor,.985),(anchor*.98+.006,1.025),(anchor*.87+.009,1.075)]
                amount+=ridge(x,z,line,.0045,.0055)
            p.y+=(-1 if front else 1)*amount*(1-abs(u)**8)
        elif abs(x)>.24:
            a=math.atan2(z-1.465,y+.003);s=1 if x>0 else -1
            normal=Vector((0,math.cos(a),math.sin(a)))
            amount=0
            for pos,tilt,width,amp in [(.397,.010,.014,.005),(.447,-.019,.010,.0065),(.489,.016,.017,.005),(.657,-.008,.008,.0045),(.703,.012,.007,.0038)]:
                distance=abs(x)-pos-tilt*math.sin(a+.4*s)
                amount+=amp*(math.exp(-(distance/width)**2)-.32*math.exp(-((distance+.018)/(width*1.7))**2))
            p+=normal*amount
    ob.data.update()


def open_neck(ob):
    # Разделить застёжку по центральному шву и раскрыть верх в V.
    bm=bmesh.new();bm.from_mesh(ob.data)
    seam=[e for e in bm.edges if all(abs(v.co.x)<.00003 and v.co.y<-.018 and v.co.z>1.429 for v in e.verts)]
    bmesh.ops.split_edges(bm,edges=seam)
    for v in bm.verts:
        p=v.co
        if p.y<-.022 and p.z>1.429 and abs(p.x)<.115:
            faces=list(v.link_faces)
            sx=sum(f.calc_center_median().x for f in faces)
            side=1 if sx>=0 else -1
            gap=.050*G.smooth(1.435,1.545,p.z)
            influence=1-G.smooth(.04,.115,abs(p.x))
            p.x+=side*gap*influence
            p.y-=.009*influence*G.smooth(1.435,1.53,p.z)
    bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000012)
    bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update()


def top_details(ob,col,m):
    surface=W.outer_surface(ob)
    def path(coords,front=-1,offset=.0015): return W.path_on(surface,coords,front,offset)
    # Центральная застёжка заканчивается ниже расстёгнутого ворота.
    zipper=path([(0,G.mix(.986,1.438,i/95)) for i in range(96)])
    W.zipper('T03 | fine central zip',zipper,col,m,width=.006)
    for side in [-1,1]:
        pocket=path([(side*(.121+.039*t),1.027+.130*t) for t in [i/40 for i in range(41)]],offset=.002)
        W.zipper('T03 | recessed pocket zip '+str(side),pocket,col,m,width=.0045)
        for offset in [-.006,.006]:
            stitch=path([(side*(.121+.039*t)+offset,1.027+.130*t) for t in [i/50 for i in range(51)]],offset=.0016)
            G.stitches('T03 | pocket sewing '+str(side),[stitch],col,m['thread_dark'],radius=.00013)
    # Эластичный низ: тонкая широкая полоса по фактической окружности.
    hem=[];verts=[];faces=[];n=192
    for row in range(5):
        z=.979+.022*row/4
        for i in range(n):
            a=2*PI*i/n;x=.188*math.sin(a)
            point,*_=surface.tree.ray_cast(Vector((x,-1 if math.cos(a)>0 else 1,z)),Vector((0,1 if math.cos(a)>0 else -1,0)))
            y=point.y if point else -.008-.155*math.cos(a)
            p=Vector((x,y,z));radial=Vector((x,y+.008,0)).normalized();p+=radial*(.001+.0007*math.cos(a*75))
            verts.append(p)
            if row==3: hem.append(p+radial*.0008)
    for j in range(4):
        for i in range(n): k=(i+1)%n;faces.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    mesh('T03 | gathered elastic hem',verts,faces,col,m['nylon_olive'],1,.00065)
    G.stitches('T03 | hem fine topstitch',[hem+[hem[0]]],col,m['thread_dark'],radius=.00013)
    # Манжеты и открытые швы проймы.
    for boundary in B.boundary_paths(ob):
        centre=sum(boundary,Vector())/len(boundary)
        if abs(centre.x)>.65:
            side=1 if centre.x>0 else -1;v=[];f=[];n=len(boundary)
            for row in range(5):
                t=row/4
                for q in boundary:
                    r=Vector((0,q.y-centre.y,q.z-centre.z));v.append(centre+r*(1.02-.035*t)+Vector((-side*.023*(1-t),0,0)))
            for row in range(4):
                for j in range(n): k=(j+1)%n;f.append((row*n+j,row*n+k,(row+1)*n+k,(row+1)*n+j))
            mesh('T03 | elastic cuff '+str(side),v,f,col,m['nylon_olive'],1,.0007)
    # Настоящая футболка под V, повторяющая анатомию; горловина круглая.
    body=G.BodySurface(bpy.data.objects['M02_Body_Head']);v=[];f=[];nx=36;nz=28
    for j in range(nz+1):
        t=j/nz
        for i in range(nx+1):
            x=G.mix(-.079,.079,i/nx);neck=1.503+.035*(abs(x)/.079)**2;z=G.mix(1.400,neck,t)
            y=body.ys(x,z,fallback=(-.104,.05))[0]-.005;v.append((x,y,z))
    for j in range(nz):
        for i in range(nx): a=j*(nx+1)+i;f.append((a,a+1,a+nx+2,a+nx+1))
    tee=mesh('T03 | grey jersey under the open neck',v,f,col,m['jersey'],1,.0007)
    neck=[Vector(v[nz*(nx+1)+i])+Vector((0,-.0007,.001)) for i in range(nx+1)]
    G.line_mesh('T03 | jersey crew neck binding',[neck],.0025,col,m['jersey'])
    # Спущенный капюшон с мягкой полостью и двумя швами раскроя.
    v=[];f=[];n=112;rows=40
    for j in range(rows+1):
        t=j/rows
        for i in range(n):
            a=2*PI*i/n;r=math.cos(t*PI/2)
            x=.108*r*math.sin(a);y=.075+.040*math.sin(PI*t)+.037*r*math.cos(a)
            z=1.539-.135*t+.014*math.cos(a)*(1-t)
            # Разная глубина мягких заломов на свисающем полотне.
            y+=.004*math.sin(3*a+1.3)*math.sin(PI*t)**2
            z+=.004*math.cos(2*a-.7)*math.sin(PI*t)
            v.append((x,y,z))
    for j in range(rows):
        for i in range(n): k=(i+1)%n;f.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
    hood=mesh('T03 | softly collapsed hood',v,f,col,m['nylon_olive'],1,.00065)
    hood.data.materials.append(m['combat_knit']);next(mod for mod in hood.modifiers if mod.type=='SOLIDIFY').material_offset=1
    rim=[Vector(v[i]) for i in range(n)];G.line_mesh('T03 | hood sewn lip',[rim],.0013,col,m['nylon_olive'],True)
    for angle in [int(n*.22),int(n*.78)]:
        line=[Vector(v[j*n+angle])+Vector((0,.0009,0)) for j in range(rows-2)]
        G.stitches('T03 | hood panel stitch',[line],col,m['thread_dark'],radius=.00012)
    # Небольшие боковые стойки ворота соединяют V и спущенный капюшон.
    for side in [-1,1]:
        points=[]
        for i in range(40):
            t=i/39;x=side*G.mix(.050,.098,math.sin(t*PI/2));y=G.mix(-.105,.074,t);z=1.542+.006*math.sin(PI*t)
            points.append(Vector((x,y,z)))
        vv=[];ff=[]
        for j in range(5):
            for p in points: vv.append(p+Vector((0,0,-.023*(1-j/4))))
        for j in range(4):
            for i in range(39): a=j*40+i;ff.append((a,a+1,a+41,a+40))
        mesh('T03 | soft neckline facing '+str(side),vv,ff,col,m['nylon_olive'],1,.0008)
        G.stitches('T03 | neckline stitch '+str(side),[points],col,m['thread_dark'],radius=.00012)


def sculpt_pants(ob):
    relax(ob,10,.36);densify(ob)
    ob.shape_key_add(name='Basis | five pocket jeans sewing draft')
    key=ob.shape_key_add(name='Artist | denim drape and worn creases');key.value=1
    for v in key.data:
        p=v.co;x,y,z=p;side=1 if x>0 else -1;u=abs(x);front=y<-.012
        normal=Vector((x-side*.102,y+.012,0)).normalized();amount=0
        paths=[([(.025,.935),(.074,.895),(.151,.875)],.007,.006),
               ([(.023,.902),(.078,.858),(.173,.838)],.009,.0065),
               ([(.036,.85),(.102,.816),(.178,.802)],.009,.004),
               ([(.043,.587),(.104,.559),(.164,.553)],.010,.005),
               ([(.049,.519),(.110,.506),(.163,.482)],.012,.006),
               ([(.048,.442),(.104,.459),(.163,.466)],.014,.004),
               ([(.048,.197),(.102,.172),(.155,.160)],.008,.007),
               ([(.045,.147),(.095,.139),(.151,.126)],.009,.005)]
        for path,w,a in paths:
            shift=.012 if side<0 else -.006
            amount+=ridge(u,z,[(px,pz+shift) for px,pz in path],w,a)
        if not front: amount*=.55
        p+=normal*amount
    ob.data.update()


def jeans_details(ob,col,m):
    # Тонкий гульфик и пятиугольные накладные карманы вместо толстых прямоугольников.
    surface=W.outer_surface(ob)
    def path(coords,front=-1,offset=.001): return W.path_on(surface,coords,front,offset)
    for side in [-1,1]:
        outline=[(side*.047,1.010),(side*.143,1.010),(side*.145,.938),(side*.100,.906),(side*.048,.931)]
        center=Vector((side*.097,.964));vv=[];ff=[];n=len(outline);rings=12
        for j in range(rings):
            t=.0001+(1-.0001)*j/(rings-1)
            for x,z in outline:
                q=center.lerp(Vector((x,z)),t);p=path([(q.x,q.y)],1,offset=.0015+.0006*math.sin(PI*t))[0];vv.append(p)
        for j in range(rings-1):
            for i in range(n): k=(i+1)%n;ff.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
        mesh('P01 | pointed rear pocket '+str(side),vv,ff,col,m['denim'],1,.0008)
        edge=path(outline+[outline[0]],1,offset=.0028)
        G.stitches('P01 | rear pocket double sewing '+str(side),[edge],col,m['thread_jeans'],radius=.00013)
        inner=path([(side*.050,1.004),(side*.139,1.004),(side*.140,.940),(side*.100,.912),(side*.053,.934)],1,offset=.0028)
        G.stitches('P01 | rear pocket inner sewing '+str(side),[inner],col,m['thread_jeans'],radius=.00012)
        entry=path([(side*G.mix(.169,.066,t),1.049-.080*math.sin(PI*t/2)) for t in [i/45 for i in range(46)]],offset=.0017)
        G.line_mesh('P01 | curved front pocket lip '+str(side),[entry],.0007,col,m['denim'])
        G.stitches('P01 | front pocket fine sewing '+str(side),[entry],col,m['thread_jeans'],radius=.00013)
        backv=path([(side*G.mix(.060,.134,t),.966-.016*math.sin(PI*t)) for t in [i/40 for i in range(41)]],1,.0028)
        G.stitches('P01 | pocket chevron '+str(side),[backv],col,m['thread_jeans'],radius=.00012)
        seam=[]
        for i in range(120):
            z=G.mix(.113,1.044,i/119);p,*_=surface.tree.ray_cast(Vector((side*1,-.015,z)),Vector((-side,0,0)))
            if p: seam.append(p+Vector((side*.001,0,0)))
        G.stitches('P01 | outer seam '+str(side),[seam],col,m['thread_jeans'],radius=.00014)
    fly=path([(.013,1.052),(.014,1.019),(.014,.980),(.010,.950),(0,.937)],offset=.0014)
    G.stitches('P01 | fly J stitch',[fly],col,m['thread_jeans'],radius=.00013)
    W.button('P01 | small jeans button',path([(.001,1.058)],offset=.003)[0],col,m['hardware'],radius=.0036)
    for x,front in [(-.145,-1),(.145,-1),(-.144,1),(.144,1),(0,1)]:
        line=path([(x,G.mix(1.027,1.069,i/14)) for i in range(15)],front,offset=.0017)
        W.strip('P01 | belt loop',line,.0065,col,m['denim'])


def linear(t,keys):
    return W.linear_profile(t,keys)


def shoes(col,m):
    for side in [-1,1]:
        cx=side*.093
        width_keys=[(-.248,.001),(-.240,.030),(-.225,.048),(-.195,.057),(-.15,.056),(-.09,.050),(-.025,.044),(.045,.041),(.074,.029),(.083,.001)]
        height_keys=[(-.248,.038),(-.23,.060),(-.195,.072),(-.15,.084),(-.105,.096),(-.06,.116),(-.01,.127),(.045,.126),(.073,.092),(.083,.040)]
        def upper(x,y,offset=.0):
            w=max(.001,linear(y,width_keys));roof=.033+(linear(y,height_keys)-.033)*max(0,1-(x/w)**2)**.55
            return Vector((cx+x,y,roof+offset))
        vv=[];ff=[];ny=90;nx=64
        for j in range(ny+1):
            y=G.mix(-.2479,.0829,j/ny);w=linear(y,width_keys)
            for i in range(nx+1):
                t=G.mix(-PI/2,PI/2,i/nx);vv.append(upper(w*math.sin(t),y))
        for j in range(ny):
            for i in range(nx):
                a=j*(nx+1)+i;ids=(a,a+1,a+nx+2,a+nx+1);p=sum((vv[k] for k in ids),Vector())/4
                # Овальный низкий вырез вокруг лодыжки; язык закрывает переднюю часть.
                hole=((p.x-cx)/.033)**2+((p.y-.006)/.055)**2<1 and p.z>.095
                if not hole: ff.append(ids)
        upper_ob=mesh('F01 | woven low upper '+str(side),vv,ff,col,m['trek_mesh'],1,.0020)
        bm=bmesh.new();bm.from_mesh(upper_ob.data)
        rim=[v for v in bm.verts if v.is_boundary and v.co.z>.092 and -.055<v.co.y<.065]
        for _ in range(9):
            positions={v:v.co.lerp(sum((e.other_vert(v).co for e in v.link_edges if e.is_boundary),Vector())/2,.35) for v in rim if sum(e.is_boundary for e in v.link_edges)==2}
            for v,p in positions.items(): v.co=p
        bm.to_mesh(upper_ob.data);bm.free();upper_ob.data.update()
        surface=W.outer_surface(upper_ob)
        def fitted(x,y,offset=.0018):
            q,normal,_,_=surface.nearest(upper(x,y))
            if q is None:return upper(x,y,offset)
            if normal.z<0:normal=-normal
            return q+normal*offset
        for loop in B.boundary_paths(upper_ob):
            if sum(p.z for p in loop)/len(loop)>.09:
                G.line_mesh('F01 | padded low ankle rim '+str(side),[loop],.0033,col,m['suede'],True)
        # Каждая накладка лежит по форме колодки и имеет тонкую кромку.
        def panel(name,polygon,mat,thick=.0014):
            # Частые вершины кромки не дают накладке срезать кривизну носка.
            polygon=[tuple(Vector(a).lerp(Vector(b),i/10)) for a,b in zip(polygon,polygon[1:]+polygon[:1]) for i in range(10)]
            center=sum((Vector(p) for p in polygon),Vector((0,0)))/len(polygon);verts=[];faces=[];n=len(polygon);rings=9
            for row in range(rings):
                t=.001+.999*row/(rings-1)
                for pp in polygon:
                    q=center.lerp(Vector(pp),t);verts.append(fitted(q.x,q.y,.0022+.0004*math.sin(PI*t)))
            for row in range(rings-1):
                for i in range(n): k=(i+1)%n;faces.append((row*n+i,row*n+k,(row+1)*n+k,(row+1)*n+i))
            ob=mesh('F01 | '+name+' '+str(side),verts,faces,col,mat,1,thick)
            outline=[fitted(x,y,.0033) for x,y in polygon];outline+=[outline[0]]
            G.stitches('F01 | '+name+' fine seam '+str(side),[outline],col,m['thread_boot'],radius=.00015)
            return ob
        panel('suede toe guard',[(-.047,-.221),(-.025,-.242),(.025,-.242),(.047,-.221),(.052,-.199),(.036,-.184),(0,-.200),(-.036,-.184),(-.052,-.199)],m['suede'])
        for flank in [-1,1]:
            panel('curved quarter',[(flank*.047,-.184),(flank*.051,-.163),(flank*.037,-.130),(flank*.028,-.105),(flank*.027,-.045),(flank*.040,-.029),(flank*.041,-.084),(flank*.050,-.126)],m['suede'])
            panel('heel support',[(flank*.042,-.021),(flank*.040,.049),(flank*.025,.072),(flank*.017,.052),(flank*.029,.029),(flank*.030,-.011)],m['suede'])
            panel('lace stay',[(flank*.019,-.157),(flank*.033,-.158),(flank*.030,-.100),(flank*.025,-.060),(flank*.017,-.045),(flank*.012,-.065)],m['suede'])
        # Отдельный язык под шнуровкой.
        v=[];f=[]
        for j in range(35):
            t=j/34;y=G.mix(-.185,-.060,t);w=G.mix(.023,.027,t)
            for i in range(19):
                x=G.mix(-w,w,i/18);p=fitted(x,y,.003);p.z+=.006*G.smooth(.65,1,t);v.append(p)
        for j in range(34):
            for i in range(18): a=j*19+i;f.append((a,a+1,a+20,a+19))
        mesh('F01 | padded mesh tongue '+str(side),v,f,col,m['trek_mesh'],1,.002)
        # Горизонтальная подошва со скошенным носком и сужением талии.
        n=192
        def sole_ring(z,expand):
            pts=[]
            for i in range(n):
                a=2*PI*i/n;y=-.0825-.165*math.cos(a);w=linear(y,width_keys)+expand
                x=w*(1 if math.sin(a)>=0 else -1)
                # Ширина контура берётся по продольной координате колодки.
                p=Vector((cx+x,y,z+.006*G.smooth(-.185,-.242,y)))
                pts.append(p)
            return pts
        for name,levels,mat in [('sculpted foam midsole',[(.013,.001),(.017,.004),(.033,.004),(.039,.0015)],m['midsole']),('rubber outsole',[(.008,.002),(.011,.004),(.018,.0045),(.021,.003)],m['rubber'])]:
            v=[];f=[]
            for z,expand in levels: v.extend(sole_ring(z,expand))
            for j in range(len(levels)-1):
                for i in range(n): k=(i+1)%n;f.append((j*n+i,j*n+k,(j+1)*n+k,(j+1)*n+i))
            f+=[tuple(reversed(range(n))),tuple((len(levels)-1)*n+i for i in range(n))]
            mesh('F01 | '+name+' '+str(side),v,f,col,mat,1,0)
        # Раздельные протекторные островки с фасками вместо сплошной чёрной плиты.
        for j,y in enumerate([-.219,-.188,-.154,-.120,-.084,-.046,-.008,.030,.059]):
            w=linear(y,width_keys)
            for flank in [-1,1]:
                x=cx+flank*w*.63;v=[];f=[];poly=[(-.014,-.012),(.011,-.010),(.014,.006),(.002,.013),(-.013,.009)]
                for z in [.004,.011]:
                    for xx,yy in poly:v.append((x+xx,y+yy,z+.004*G.smooth(-.19,-.24,y)))
                f=[(4,3,2,1,0),(5,6,7,8,9)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)]
                lug=mesh('F01 | outsole grip '+str(side)+' '+str(j)+' '+str(flank),v,f,col,m['rubber'],0,0)
                bevel=lug.modifiers.new('Moulded grip edge radius','BEVEL');bevel.width=.0016;bevel.segments=2
        # Пять пар люверсов, настоящие перекрёстные шнурки и узел.
        lace=[]
        ys=[-.175,-.152,-.129,-.106,-.084]
        for j,y in enumerate(ys):
            for flank in [-1,1]:
                p=fitted(flank*.024,y,.005)
                bpy.ops.mesh.primitive_torus_add(major_radius=.0026,minor_radius=.0006,major_segments=12,minor_segments=5,location=p)
                ob=bpy.context.object;ob.name='F01 | metal eyelet '+str(side);ob.data.materials.append(m['hardware'])
                for cc in list(ob.users_collection):cc.objects.unlink(ob)
                col.objects.link(ob)
            if j<len(ys)-1:
                for flank in [-1,1]:
                    pts=[]
                    for i in range(23):
                        t=i/22;x=G.mix(flank*.024,-flank*.024,t);yy=G.mix(y,ys[j+1],t)
                        pts.append(fitted(x,yy,.006+.003*math.sin(PI*t)))
                    lace.append(pts)
        G.line_mesh('F01 | crossing round laces '+str(side),lace,.00085,col,m['thread_boot'])
        knot=fitted(0,-.084,.012)
        paths=[]
        for flank in [-1,1]:
            paths.append([fitted(flank*.022*math.sin(PI*t),-.084+.012*math.sin(2*PI*t),.010+.003*math.sin(PI*t)) for t in [i/40 for i in range(41)]])
            paths.append([fitted(flank*.012*t,-.084-.045*t,.007+.004*(1-t)) for t in [i/25 for i in range(26)]])
        G.line_mesh('F01 | lace bow and loose ends '+str(side),paths,.00085,col,m['thread_boot'])
        # Небольшой мягкий задник и петля, читаемые над низким вырезом.
        loop=[(cx,.058, .096),(cx,.066,.132),(cx,.063,.144),(cx,.051,.138),(cx,.050,.115)]
        W.strip('F01 | heel pull tab '+str(side),[Vector(p) for p in loop],.011,col,m['suede'])
    for ob in col.objects:
        ob['wardrobe_id']='F01'
        if ob.type=='MESH' and not ob.data.uv_layers:W.metric_uv(ob)


def balaclava(col,body):
    main=next(ob for ob in col.objects if 'tailored hood shell' in ob.name)
    surface=G.BodySurface(body)
    for vertex in main.data.vertices:
        p=vertex.co
        if p.z>1.710:
            q,normal,_,_=surface.nearest(p)
            if q is not None:
                desired=q+normal*.0055;blend=G.smooth(1.710,1.746,p.z);p[:]=p.lerp(desired,blend)
        if p.y<-.11 and 1.575<p.z<1.631:
            # Ткань проходит над губами единым мягким полотном.
            target=-.170+.012*G.smooth(1.600,1.631,p.z)
            blend=(1-G.smooth(.040,.073,abs(p.x)))*G.smooth(1.575,1.588,p.z)*(1-G.smooth(1.621,1.631,p.z))
            p.y=G.mix(p.y,min(p.y,target),blend*.75)
    main.data.update()
    for ob in list(col.objects):
        if ob!=main:bpy.data.objects.remove(ob,do_unlink=True)
    return main
