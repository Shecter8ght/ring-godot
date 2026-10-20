"""ЗОРИН К-1: арочная защита заново — ножки до палубы и отдельный мелкий мостик под окном.

Было: один ленточный лофт внешней и внутренней арок, где нижний ряд внешнего контура (глубокие
стенки) спаривался с нижним рядом внутреннего (мелкий мостик) — у нижних углов окна получались
скошенные крученые грани («поехавшие стойки» с глаза стрелка). Стало: U-лента (две ножки + арка)
полной глубины и мостик x −23…−21 с радиусом 2 мм к ножкам, объединённые Exact-булевой.
Силуэт, окно, линза, уплотнитель и клейма не менялись.
"""
import sys, math, bpy, bmesh
from mathutils import Vector
args = sys.argv[sys.argv.index('--')+1:]
src, dst = args[0], args[1]
bpy.ops.wm.open_mainfile(filepath=src)
hood = bpy.data.objects['Reflex | K1 deep arched protective hood']
M = hood.matrix_world.copy(); Minv = M.inverted()
# геометрия задаётся в мм относительно корня прицела (в сборке ПМ корень стоит на креплении)
R = bpy.data.objects['PM_ReflexSight • asset root'].matrix_world.copy()
old = hood.data

def front_x(z): return -23.0 + max(0, z - 26.0) * .22
def rear_x(z):
    if z < 25.1:
        if z <= 18.4: return 1.8
        lo, hi = 0.0, 1.0
        for _ in range(28):
            t = (lo + hi) / 2; u = 1 - t; zz = u**3*25.1 + 3*u*u*t*21.1 + 3*u*t*t*18.4 + t**3*18.4
            if zz > z: lo = t
            else: hi = t
        t = (lo + hi) / 2; u = 1 - t
        return u**3*(-5.3) + 3*u*u*t*(-3.0) + 3*u*t*t*(-3.0) + t**3*1.8
    if z < 33.5: return -5.3 - (z - 25.1) * 5.2 / (33.5 - 25.1)
    return -10.5 + (z - 33.5) * .5 / 7.9

def outer_u(w=16.6, bottom=17.8, shoulder=33.5, rise=7.9, r=0.8):
    pts = []
    for j in range(16):               # правый нижний угол, снизу вверх
        a = -math.pi/2 + j*(math.pi/2)/16; pts.append((w - r + r*math.cos(a), bottom + r + r*math.sin(a)))
    for j in range(40):               # правая стенка вверх
        pts.append((w, bottom + r + (shoulder - bottom - r)*j/40))
    for j in range(129):              # арка справа налево (включая обе опоры)
        a = j*math.pi/128; pts.append((w*math.cos(a), shoulder + rise*math.sin(a)))
    for j in range(1, 41):            # левая стенка вниз
        pts.append((-w, shoulder - (shoulder - bottom - r)*j/40))
    for j in range(1, 17):            # левый нижний угол
        a = math.pi + j*(math.pi/2)/16; pts.append((-w + r + r*math.cos(a), bottom + r + r*math.sin(a)))
    return pts

def inner_u(outer, wi=12.85, shoulder=33.4, rise=5.5):
    # ножки — по тем же z, что у внешнего контура (пары горизонтальны), арка — своя
    pts = []
    for y, z in outer[:56]: pts.append((wi, z))
    for j in range(129):
        a = j*math.pi/128; pts.append((wi*math.cos(a), shoulder + rise*math.sin(a)))
    for y, z in outer[185:]: pts.append((-wi, z))
    return pts

O = outer_u(); I = inner_u(O); assert len(O) == len(I), (len(O), len(I))
n = len(O)
verts = []
for xf in (True, False):
    for loop in (O, I):
        for y, z in loop:
            verts.append(((front_x(z) if xf else rear_x(z)), y, z))
# индексы: Fo = 0.., Fi = n.., Bo = 2n.., Bi = 3n..
faces = []
for j in range(n - 1):
    k = j + 1
    faces.append((j, k, n + k, n + j))                      # передняя кольцевая
    faces.append((2*n + j, 3*n + j, 3*n + k, 2*n + k))      # задняя кольцевая
    faces.append((j, 2*n + j, 2*n + k, k))                  # наружная обшивка
    faces.append((n + j, n + k, 3*n + k, 3*n + j))          # внутренняя обшивка (ножки, свод)
faces.append((0, n, 3*n, 2*n))                              # пятка правой ножки
faces.append((n - 1, 2*n + n - 1, 3*n + n - 1, n + n - 1))  # пятка левой ножки

def make(name, v_mm, f):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(Minv @ (R @ (Vector(v) * 0.001))) for v in v_mm], [], f)
    bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
    me.update(); ob = bpy.data.objects.new(name, me); bpy.context.scene.collection.objects.link(ob)
    ob.matrix_world = M
    return ob

band = make('TMP hood band', verts, faces)

# мостик: профиль YZ, радиус 2 мм к ножкам, заходит в ножки на 0.65 мм
prof = [(13.5, 17.85), (13.5, 23.4), (12.85, 23.4)]
for j in range(1, 17):
    a = -j*(math.pi/2)/16; prof.append((10.85 + 2.0*math.cos(a), 23.4 + 2.0*math.sin(a)))
prof.append((-10.85, 21.4))
for j in range(1, 17):
    a = -math.pi/2 - j*(math.pi/2)/16; prof.append((-10.85 + 2.0*math.cos(a), 23.4 + 2.0*math.sin(a)))
prof += [(-13.5, 23.4), (-13.5, 17.85)]
m = len(prof)
bv = [(-23.0, y, z) for y, z in prof] + [(-21.0, y, z) for y, z in prof]
bf = [tuple(range(m)), tuple(range(2*m - 1, m - 1, -1))] + [(j, (j+1) % m, (j+1) % m + m, j + m) for j in range(m)]
bridge = make('TMP hood bridge', bv, bf)

mod = band.modifiers.new('UNION bridge', 'BOOLEAN'); mod.operation = 'UNION'; mod.solver = 'EXACT'; mod.object = bridge
with bpy.context.temp_override(object=band, active_object=band, selected_objects=[band]):
    bpy.ops.object.modifier_apply(modifier=mod.name)
new = band.data
# булева добавила пустой слот операнда — убрать; материалы и сглаживание — как у прежней сетки
while len(new.materials) and new.materials[0] is None: new.materials.pop(index=0)
for mat in old.materials: new.materials.append(mat)
assert list(new.materials) == list(old.materials), [m.name if m else None for m in new.materials]
smooth = sum(1 for p in old.polygons if p.use_smooth) * 2 > len(old.polygons)
for p in new.polygons: p.use_smooth = smooth; p.material_index = 0
new.name = old.name + ' v07'
hood.data = new
bpy.data.objects.remove(band, do_unlink=True); bpy.data.objects.remove(bridge, do_unlink=True)
bpy.data.meshes.remove(bridge_me) if (bridge_me := bpy.data.meshes.get('TMP hood bridge')) else None
hood['Geometry revision'] = 'v07: legs to the deck, separate shallow bridge with r2 fillets'
# проверка
bm = bmesh.new(); bm.from_mesh(new)
nonman = [e for e in bm.edges if not e.is_manifold]
print('HOOD verts/faces', len(new.vertices), len(new.polygons), 'non-manifold', len(nonman), 'smooth', smooth, flush=True)
bm.free()
hood.update_tag(); bpy.context.view_layer.update()
dg = bpy.context.evaluated_depsgraph_get(); eo = hood.evaluated_get(dg); em = eo.to_mesh()
pts = [R.inverted() @ (M @ v.co) for v in em.vertices]
print('HOOD eval bbox mm', [round(min(p[i] for p in pts)*1000,2) for i in range(3)], [round(max(p[i] for p in pts)*1000,2) for i in range(3)], 'tris', len(em.polygons), flush=True)
eo.to_mesh_clear()
assert not nonman
bpy.ops.wm.save_as_mainfile(filepath=dst)
print('HOOD_FIXED_SAVED', dst, flush=True)
