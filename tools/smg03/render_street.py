"""ИЗЛОМ-45: «тактические» рендеры на улице для владельца (2026-11-05: «классный рендер, какой-нибудь тактикульный,
с естественным уличным освещением, 3–5 изображений 2К: в статике, с отведённым затвором, со сложенным прикладом,
во время стрельбы и ещё на своё усмотрение»).

Ствол — игровая сетка с картами износа v3 (файл просмотра ПП-Vector_износ_этап2_v3.blend), позы подвижных деталей —
с органов управления исходника (render_poses.py → _asset_src/smg03/render/poses.json). Двор за бетонным забором ПО-2 —
свои модели игры (urban95, prospekt_city, prospekt_vehicles, растения «Проспекта»), асфальт и бетон — фото Poly Haven
(CC0, assets/textures), небо — панорама Poly Haven (CC0, assets/sky) с солнцем лампой: низкое предвечернее солнце.
Патроны и гильзы .45 — точением по размерам патрона.

"D:/ПРОГРАММЫ/Blender 5/blender.exe" -b --factory-startup --python-exit-code 1 --python tools/smg03/render_street.py -- <папка> [кадр,кадр] [ширина высота выборки] [сцена.blend]
кадры: 1_static, 2_bolt, 3_folded, 4_firing, 5_ground
"""
import json
import math
import os
import random
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree

ROOT = Path(__file__).resolve().parents[2]
SRC = os.environ.get('SMG03_RENDER_SRC', 'E:/Models Blender/WEAPONS/Vector — модель/ПП-Vector_износ_этап2_v3.blend')
POSES = ROOT / '_asset_src/smg03/render/poses.json'
SKY = ROOT / 'assets/sky/kloofendal_48d_partly_cloudy_puresky.hdr'
TEX = ROOT / 'assets/textures'
CATALOG = ROOT / 'data/urban95_models.json'
SKY_SUN_AZ = 145.8            # азимут солнца панорамы в координатах Blender (замер яркого пикселя)
SUN_AZ, SUN_EL = 128.0, 30.0  # своё солнце: предвечернее, длинные тени
SUN_POWER = 5.0
# экспозиция по кадрам: белый капот полицейской машины — ниже
EXPOSURE = {'1_static': 0.2, '3_folded': -0.2, '4_firing': 0.0}
# окно выброса (правый борт, мм — wear_zones.PORT_X/Z), полуширина корпуса
PORT = Vector((-0.0195, -0.02175, 0.030))


def log(*a):
    print('STREET', *a, flush=True)


# ---------------------------------------------------------------- материалы

def _img(path, noncolor=False):
    im = bpy.data.images.load(str(path), check_existing=True)
    im.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    return im


def mat_photo(name, folder, tile_m, box=False, value=1.0, bump=1.0):
    """Фотоматериал Poly Haven (albedo / arm / normal): плитка tile_m метров; box — проекция с трёх сторон по объекту
    (для блоков), иначе по координатам объекта сверху. Крупная пятнистость тона — чтобы не читался повтор плитки."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0 / tile_m,) * 3
    L.new(tc.outputs['Object'], mp.inputs['Vector'])

    def tex(fn, nc):
        t = N.new('ShaderNodeTexImage')
        t.image = _img(TEX / folder / fn, nc)
        t.interpolation = 'Cubic'
        if box:
            t.projection = 'BOX'
            t.projection_blend = 0.25
        L.new(mp.outputs[0], t.inputs['Vector'])
        return t
    al, arm, nm = tex('albedo.jpg', False), tex('arm.jpg', True), tex('normal.jpg', True)
    # пятна тона ~3 м
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 0.35
    nz.inputs['Detail'].default_value = 3.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    ramp = N.new('ShaderNodeMapRange')
    ramp.inputs[1].default_value, ramp.inputs[2].default_value = 0.3, 0.7
    ramp.inputs[3].default_value, ramp.inputs[4].default_value = 0.82 * value, 1.12 * value
    L.new(nz.outputs['Fac'], ramp.inputs[0])
    mul = N.new('ShaderNodeMixRGB')
    mul.blend_type = 'MULTIPLY'
    mul.inputs[0].default_value = 1.0
    L.new(al.outputs[0], mul.inputs[1])
    L.new(ramp.outputs[0], mul.inputs[2])
    L.new(mul.outputs[0], b.inputs['Base Color'])
    sp = N.new('ShaderNodeSeparateColor')
    L.new(arm.outputs[0], sp.inputs[0])
    L.new(sp.outputs['Green'], b.inputs['Roughness'])
    nmap = N.new('ShaderNodeNormalMap')
    nmap.inputs['Strength'].default_value = bump
    L.new(nm.outputs[0], nmap.inputs['Color'])
    L.new(nmap.outputs[0], b.inputs['Normal'])
    return m


LINEN = ROOT / '_asset_src/npc_kit/tex/rough_linen/rough_linen_'


def mat_bags(name, tint, tile_m):
    """Мешки с песком: тканое полотно (rough_linen, Poly Haven CC0) проекцией с трёх сторон по объекту, тон — хаки;
    у модели игры мешки гладкие, как подушки."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N['Principled BSDF']
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (1.0 / tile_m,) * 3
    L.new(tc.outputs['Object'], mp.inputs['Vector'])

    def tex(fn, nc):
        t = N.new('ShaderNodeTexImage')
        t.image = _img(str(LINEN) + fn, nc)
        t.projection = 'BOX'
        t.projection_blend = 0.3
        L.new(mp.outputs[0], t.inputs['Vector'])
        return t
    diff, rough, nor = tex('diff_2k.jpg', False), tex('rough_2k.png', True), tex('nor_gl_2k.png', True)
    bw = N.new('ShaderNodeRGBToBW')
    L.new(diff.outputs[0], bw.inputs[0])
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 4.0
    nz.inputs['Detail'].default_value = 4.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    dirt = N.new('ShaderNodeMapRange')
    dirt.inputs[1].default_value, dirt.inputs[2].default_value = 0.35, 0.7
    dirt.inputs[3].default_value, dirt.inputs[4].default_value = 1.15, 0.7
    L.new(nz.outputs['Fac'], dirt.inputs[0])
    m1 = N.new('ShaderNodeMath')
    m1.operation = 'MULTIPLY'
    L.new(bw.outputs[0], m1.inputs[0])
    L.new(dirt.outputs[0], m1.inputs[1])
    mix = N.new('ShaderNodeMixRGB')
    mix.blend_type = 'MULTIPLY'
    mix.inputs[0].default_value = 1.0
    L.new(m1.outputs[0], mix.inputs[1])
    mix.inputs[2].default_value = (*tint, 1.0)
    L.new(mix.outputs[0], b.inputs['Base Color'])
    L.new(rough.outputs[0], b.inputs['Roughness'])
    nm = N.new('ShaderNodeNormalMap')
    nm.inputs['Strength'].default_value = 1.2
    L.new(nor.outputs[0], nm.inputs['Color'])
    L.new(nm.outputs[0], b.inputs['Normal'])
    b.inputs['Specular IOR Level'].default_value = 0.3
    return m


def mat_metal(name, color, rough, tarnish=0.25, soot=None):
    """Латунь / томпак: металл с пятнами потускнения; soot — (z0, z1) в мм объекта: копоть к дульцу стреляной гильзы."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    b = N['Principled BSDF']
    b.inputs['Metallic'].default_value = 1.0
    tc = N.new('ShaderNodeTexCoord')
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 180.0
    nz.inputs['Detail'].default_value = 6.0
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    mr = N.new('ShaderNodeMapRange')
    mr.inputs[1].default_value, mr.inputs[2].default_value = 0.35, 0.75
    L.new(nz.outputs['Fac'], mr.inputs[0])
    mix = N.new('ShaderNodeMixRGB')
    mix.inputs[1].default_value = (*color, 1.0)
    mix.inputs[2].default_value = (color[0] * 0.62, color[1] * 0.58, color[2] * 0.52, 1.0)
    mt = N.new('ShaderNodeMath')
    mt.operation = 'MULTIPLY'
    mt.inputs[1].default_value = tarnish
    L.new(mr.outputs[0], mt.inputs[0])
    L.new(mt.outputs[0], mix.inputs[0])
    col = mix.outputs[0]
    if soot:
        sep = N.new('ShaderNodeSeparateXYZ')
        L.new(tc.outputs['Object'], sep.inputs[0])
        sr = N.new('ShaderNodeMapRange')
        sr.inputs[1].default_value, sr.inputs[2].default_value = soot[0] * 0.001, soot[1] * 0.001
        sr.inputs[3].default_value, sr.inputs[4].default_value = 0.0, 0.75
        L.new(sep.outputs['Z'], sr.inputs[0])
        m2 = N.new('ShaderNodeMixRGB')
        m2.inputs[2].default_value = (0.05, 0.045, 0.04, 1.0)
        L.new(sr.outputs[0], m2.inputs[0])
        L.new(col, m2.inputs[1])
        col = m2.outputs[0]
    L.new(col, b.inputs['Base Color'])
    rr = N.new('ShaderNodeMapRange')
    rr.inputs[3].default_value, rr.inputs[4].default_value = rough * 0.75, rough * 1.5
    L.new(nz.outputs['Fac'], rr.inputs[0])
    L.new(rr.outputs[0], b.inputs['Roughness'])
    return m


def mat_plain(name, color, rough, metal=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    return m


# ---------------------------------------------------------------- патроны .45

def lathe(name, prof, mats, seg=40):
    """Тело вращения вокруг Z: prof — [(r мм, z мм, слот материала)]; начало — центр донца."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = []
    for r, z, _ in prof:
        if r < 1e-4:
            rings.append([bm.verts.new((0.0, 0.0, z * 0.001))])
        else:
            rings.append([bm.verts.new((r * 0.001 * math.cos(2 * math.pi * k / seg),
                                        r * 0.001 * math.sin(2 * math.pi * k / seg), z * 0.001)) for k in range(seg)])
    for i in range(len(prof) - 1):
        a, c = rings[i], rings[i + 1]
        slot = prof[i + 1][2]
        if len(a) == 1 and len(c) == 1:
            continue
        for k in range(seg):
            if len(a) == 1:
                f = bm.faces.new((a[0], c[k], c[(k + 1) % seg]))
            elif len(c) == 1:
                f = bm.faces.new((a[k], a[(k + 1) % seg], c[0]))
            else:
                f = bm.faces.new((a[k], a[(k + 1) % seg], c[(k + 1) % seg], c[k]))
            f.material_index = slot
            f.smooth = True
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for mt in mats:
        me.materials.append(mt)
    o = bpy.data.objects.new(name, me)
    return o


# .45 ACP: гильза 22,8 мм, донце 12,2, проточка, пуля 11,48, длина патрона 32,4 (оболочечная, круглоносая)
CASE = [(0.0, 0.12, 1), (2.3, 0.12, 1), (2.3, 0.0, 1), (2.45, 0.0, 0), (5.6, 0.0, 0), (6.05, 0.35, 0),
        (6.1, 1.15, 0), (5.95, 1.35, 0), (5.15, 1.75, 0), (5.15, 2.35, 0), (6.04, 3.0, 0), (6.03, 12.0, 0),
        (6.0, 22.6, 0), (5.92, 22.8, 0)]
LIVE = CASE + [(5.74, 22.8, 0), (5.74, 23.0, 2), (5.74, 25.4, 2), (5.55, 27.2, 2), (4.95, 29.0, 2), (3.9, 30.6, 2),
               (2.4, 31.8, 2), (0.0, 32.4, 2)]
SPENT = CASE + [(5.72, 22.8, 0), (5.72, 21.0, 3), (5.6, 6.0, 3), (0.0, 5.5, 3)]


class Ammo:
    def __init__(self, coll):
        self.coll = coll
        self.brass = mat_metal('Латунь', (0.80, 0.56, 0.22), 0.26, 0.3)
        self.brass_spent = mat_metal('Латунь стреляная', (0.74, 0.50, 0.19), 0.32, 0.45, soot=(16.0, 23.0))
        self.primer = mat_plain('Капсюль', (0.62, 0.60, 0.57), 0.3, 1.0)
        self.copper = mat_metal('Томпак', (0.66, 0.30, 0.15), 0.24, 0.25)
        self.dark = mat_plain('Нагар внутри', (0.03, 0.028, 0.025), 0.7)
        self.live_me = lathe('патрон', LIVE, [self.brass, self.primer, self.copper]).data
        self.spent_me = lathe('гильза', SPENT, [self.brass_spent, self.primer, self.copper, self.dark]).data

    def add(self, spent, loc, rot):
        o = bpy.data.objects.new('гильза' if spent else 'патрон', self.spent_me if spent else self.live_me)
        self.coll.objects.link(o)
        o.location = loc
        o.rotation_euler = rot
        return o


# ---------------------------------------------------------------- модели окружения

class Kit:
    """Свои модели игры (glTF из каталога data/urban95_models.json): одна загрузка — в скрытую коллекцию, на сцене —
    экземпляры коллекции; опоры, на которые кладётся ствол, — настоящими объектами (для лучей)."""

    def __init__(self, coll):
        self.cat = json.loads(CATALOG.read_text(encoding='utf-8'))['models']
        self.lib = bpy.data.collections.new('библиотека моделей')
        bpy.context.scene.collection.children.link(self.lib)
        for lc in bpy.context.view_layer.layer_collection.children:
            if lc.collection == self.lib:
                lc.exclude = True
        self.loaded = {}
        self.coll = coll

    def _path(self, mid):
        f = self.cat[mid]['file']
        return str(ROOT / f.replace('res://', ''))

    def _import(self, mid, coll):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=self._path(mid))
        new = [o for o in bpy.data.objects if o not in before]
        for o in new:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
        return new

    def inst(self, mid, loc, rot=0.0, scale=1.0):
        if mid not in self.loaded:
            c = bpy.data.collections.new(mid)
            self.lib.children.link(c)
            self._import(mid, c)
            self.loaded[mid] = c
        e = bpy.data.objects.new(mid, None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = self.loaded[mid]
        e.location = loc
        e.rotation_euler = (0.0, 0.0, math.radians(rot))
        e.scale = (scale,) * 3
        self.coll.objects.link(e)
        return e

    def real(self, mid, loc, rot=0.0):
        root = bpy.data.objects.new(mid, None)
        self.coll.objects.link(root)
        new = self._import(mid, self.coll)
        for o in new:
            if o.parent is None:
                o.parent = root
        root.location = loc
        root.rotation_euler = (0.0, 0.0, math.radians(rot))
        bpy.context.view_layer.update()
        return root, [o for o in new if o.type == 'MESH']


PLANT_TEX = ROOT / 'assets/models/plants/textures'
PLANT_BARK = {'Birch': ROOT / 'assets/zone01/textures/bark_birch.png',
              'Linden': TEX / 'bark_brown_02/albedo.jpg',
              'Poplar': PLANT_TEX / 'poplar_bark_young_albedo.webp'}


def plant_materials():
    """Листва и ветви — атлас вида с прозрачностью, кора — фото коры; цвет вершин (данные ветра Godot) не берётся."""
    done = {}
    for m in list(bpy.data.materials):
        if not m.name.startswith('Plant') or m.name in done:
            continue
        sp = next((k for k in PLANT_BARK if m.name.startswith('Plant' + k)), None)
        if sp is None:
            continue
        m.use_nodes = True
        nt = m.node_tree
        N, L = nt.nodes, nt.links
        N.clear()
        out = N.new('ShaderNodeOutputMaterial')
        b = N.new('ShaderNodeBsdfPrincipled')
        L.new(b.outputs[0], out.inputs[0])
        t = N.new('ShaderNodeTexImage')
        if 'Bark' in m.name:
            t.image = _img(PLANT_BARK[sp])
            L.new(t.outputs['Color'], b.inputs['Base Color'])
            b.inputs['Roughness'].default_value = 0.85
        else:
            t.image = _img(PLANT_TEX / f'{sp.lower()}_atlas_albedo.webp')
            t.interpolation = 'Cubic'
            L.new(t.outputs['Color'], b.inputs['Base Color'])
            L.new(t.outputs['Alpha'], b.inputs['Alpha'])
            b.inputs['Roughness'].default_value = 0.6
            b.inputs['Subsurface Weight'].default_value = 0.15
        done[m.name] = True
    log('растения', sorted(done))


def bvh(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    verts, polys = [], []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        base = len(verts)
        verts += [mw @ v.co for v in me.vertices]
        polys += [[base + i for i in p.vertices] for p in me.polygons]
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def surface(tree, x, y, top=20.0):
    hit = tree.ray_cast(Vector((x, y, top)), Vector((0, 0, -1)))
    return hit[0].z if hit[0] is not None else None, hit[1]


# ---------------------------------------------------------------- ствол

class Gun:
    def __init__(self):
        self.meshes = [o for o in bpy.data.objects if o.type == 'MESH' and 'atlas' in o]
        self.root = bpy.data.objects.new('ИЗЛОМ-45', None)
        bpy.context.scene.collection.objects.link(self.root)
        for o in self.meshes:
            o.parent = self.root
            o.matrix_parent_inverse = Matrix.Identity(4)
        self.rest = {o.name: o.matrix_basis.copy() for o in self.meshes}
        self.poses = json.loads(POSES.read_text(encoding='utf-8'))
        self.mag13 = bpy.data.objects['Mag13']
        self.mag30 = bpy.data.objects['Mag30']
        st = bpy.data.objects['Receiver_Steel']
        xs = [v.co.x for v in st.data.vertices]
        x1 = max(xs)
        near = [v.co for v in st.data.vertices if v.co.x > x1 - 0.004]
        self.muzzle = Vector((x1, sum(v.y for v in near) / len(near), (max(v.z for v in near) + min(v.z for v in near)) / 2))
        log('дуло', [round(c * 1000, 1) for c in self.muzzle])

    def pose(self, name, mag='13'):
        for o in self.meshes:
            o.matrix_basis = self.rest[o.name]
            d = self.poses.get(name, {}).get(o['node'])
            if d is not None:
                o.matrix_basis = Matrix(d) @ self.rest[o.name]
        self.mag13.hide_render = mag != '13'
        self.mag30.hide_render = mag != '30'
        self.mag13.hide_viewport = self.mag13.hide_render
        self.mag30.hide_viewport = self.mag30.hide_render

    def place(self, loc, yaw, roll, tree=None, pitch=0.0, gap=0.0004, center=None):
        """Ствол: поворот (рыскание, крен, тангаж), точка center (в координатах ствола) — над loc, затем опускание на
        опору лучами сверху — касание в ближайшей точке."""
        self.root.matrix_world = (Matrix.Translation(Vector(loc)) @ Matrix.Rotation(math.radians(yaw), 4, 'Z')
                                  @ Matrix.Rotation(math.radians(pitch), 4, 'Y') @ Matrix.Rotation(math.radians(roll), 4, 'X'))
        bpy.context.view_layer.update()
        if center is not None:
            c = self.root.matrix_world @ Vector(center)
            self.root.location.x += loc[0] - c.x
            self.root.location.y += loc[1] - c.y
            bpy.context.view_layer.update()
        if tree is None:
            return
        best = 1e9
        for o in self.meshes:
            if o.hide_render:
                continue
            mw = o.matrix_world
            for v in list(o.data.vertices)[::3]:
                p = mw @ v.co
                z, _ = surface(tree, p.x, p.y)
                if z is not None:
                    best = min(best, p.z - z)
        self.root.location.z -= best - gap
        bpy.context.view_layer.update()
        log('опущен на', round(best, 4))

    def world(self, p):
        return self.root.matrix_world @ p


# ---------------------------------------------------------------- выстрел: вспышка, дымок, гильзы

def mat_flash(name, color, strength, falloff_pow, noise_scale):
    """Объёмное свечение: сила — от центра к краю (сфера объекта), рвано шумом."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL':
            N.remove(n)
    out = [n for n in N if n.type == 'OUTPUT_MATERIAL'][0]
    vol = N.new('ShaderNodeVolumePrincipled')
    vol.inputs['Density'].default_value = 0.0
    vol.inputs['Emission Color'].default_value = (*color, 1.0)
    tc = N.new('ShaderNodeTexCoord')
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    L.new(tc.outputs['Object'], ln.inputs[0])
    inv = N.new('ShaderNodeMapRange')
    inv.inputs[1].default_value, inv.inputs[2].default_value = 1.0, 0.0
    L.new(ln.outputs['Value'], inv.inputs[0])
    pw = N.new('ShaderNodeMath')
    pw.operation = 'POWER'
    pw.inputs[1].default_value = falloff_pow
    L.new(inv.outputs[0], pw.inputs[0])
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = noise_scale
    nz.inputs['Detail'].default_value = 8.0
    nz.inputs['Roughness'].default_value = 0.65
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    nr = N.new('ShaderNodeMapRange')
    nr.inputs[1].default_value, nr.inputs[2].default_value = 0.42, 0.72
    L.new(nz.outputs['Fac'], nr.inputs[0])
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    L.new(pw.outputs[0], mul.inputs[0])
    L.new(nr.outputs[0], mul.inputs[1])
    st = N.new('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    st.inputs[1].default_value = strength
    L.new(mul.outputs[0], st.inputs[0])
    L.new(st.outputs[0], vol.inputs['Emission Strength'])
    L.new(vol.outputs[0], out.inputs['Volume'])
    return m


def mat_smoke(name, density):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, L = nt.nodes, nt.links
    for n in list(N):
        if n.type != 'OUTPUT_MATERIAL':
            N.remove(n)
    out = [n for n in N if n.type == 'OUTPUT_MATERIAL'][0]
    vol = N.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.62, 0.60, 0.57, 1.0)
    tc = N.new('ShaderNodeTexCoord')
    ln = N.new('ShaderNodeVectorMath')
    ln.operation = 'LENGTH'
    L.new(tc.outputs['Object'], ln.inputs[0])
    inv = N.new('ShaderNodeMapRange')
    inv.inputs[1].default_value, inv.inputs[2].default_value = 1.0, 0.2
    L.new(ln.outputs['Value'], inv.inputs[0])
    nz = N.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 3.5
    nz.inputs['Detail'].default_value = 10.0
    nz.inputs['Distortion'].default_value = 0.6
    L.new(tc.outputs['Object'], nz.inputs['Vector'])
    nr = N.new('ShaderNodeMapRange')
    nr.inputs[1].default_value, nr.inputs[2].default_value = 0.48, 0.75
    L.new(nz.outputs['Fac'], nr.inputs[0])
    mul = N.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    L.new(inv.outputs[0], mul.inputs[0])
    L.new(nr.outputs[0], mul.inputs[1])
    st = N.new('ShaderNodeMath')
    st.operation = 'MULTIPLY'
    st.inputs[1].default_value = density
    L.new(mul.outputs[0], st.inputs[0])
    L.new(st.outputs[0], vol.inputs['Density'])
    L.new(vol.outputs[0], out.inputs['Volume'])
    return m


def blob(coll, name, mat, loc, scale, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    o = bpy.data.objects.new(name, me)
    coll.objects.link(o)
    o.location = loc
    o.scale = scale
    o.rotation_euler = rot
    return o


def build_fire(coll, gun, ammo):
    """Вспышка у дула (горячее ядро, оранжевый шар, боковые языки), дымок у дула и у окна, гильзы в воздухе; всё —
    дочерние ствола (в его координатах). Гильзы — с ключами на кадрах 1–2: размытие движения."""
    root = bpy.data.objects.new('выстрел', None)
    coll.objects.link(root)
    root.parent = gun.root
    mz = gun.muzzle
    core = mat_flash('вспышка — ядро', (1.0, 0.78, 0.42), 3000.0, 2.4, 6.0)
    ball = mat_flash('вспышка — шар', (1.0, 0.40, 0.09), 600.0, 1.8, 4.0)
    jets = mat_flash('вспышка — языки', (1.0, 0.34, 0.07), 450.0, 1.5, 3.0)
    parts = [blob(coll, 'вспышка ядро', core, mz + Vector((0.016, 0, 0)), (0.020, 0.009, 0.009)),
             blob(coll, 'вспышка шар', ball, mz + Vector((0.040, 0, 0)), (0.040, 0.020, 0.020))]
    for k, a in enumerate((20, 95, 160, 230, 300)):
        r = math.radians(a)
        d = Vector((0.55, math.cos(r) * 0.85, math.sin(r) * 0.85)).normalized()
        q = Vector((1, 0, 0)).rotation_difference(d).to_euler()
        ln = 0.020 + 0.008 * ((k * 7) % 3)
        parts.append(blob(coll, f'вспышка язык {k}', jets, mz + Vector((0.004, 0, 0)) + d * ln, (ln, 0.0045, 0.0045), q))
    smoke = mat_smoke('дымок', 0.8)
    parts.append(blob(coll, 'дымок у дула', smoke, mz + Vector((0.075, 0.0, 0.008)), (0.07, 0.035, 0.03)))
    parts.append(blob(coll, 'дымок у окна', mat_smoke('дымок у окна', 1.0), PORT + Vector((0.0, -0.04, 0.025)),
                      (0.05, 0.035, 0.03)))
    for o in parts:
        o.parent = root
    light = bpy.data.lights.new('вспышка — свет', 'POINT')
    light.energy = 22.0
    light.color = (1.0, 0.52, 0.20)
    light.shadow_soft_size = 0.03
    lo = bpy.data.objects.new('вспышка — свет', light)
    coll.objects.link(lo)
    lo.parent = root
    lo.location = mz + Vector((0.07, 0, 0))
    # гильзы: только что выброшенная у окна (летит вправо-вверх, кувыркается) и предыдущая — дальше, ниже
    cs = []
    for loc, vel, rot, spin in ((PORT + Vector((0.004, -0.048, 0.030)), Vector((0.004, -0.040, 0.018)),
                                 (0.4, 1.35, 0.6), (0.0, 0.9, 0.5)),
                                (PORT + Vector((-0.03, -0.26, 0.05)), Vector((0.0, -0.035, -0.012)),
                                 (1.9, 0.3, 2.4), (0.8, 0.0, 0.9))):
        c = ammo.add(True, loc, rot)
        c.parent = root
        c.keyframe_insert('location', frame=1)
        c.keyframe_insert('rotation_euler', frame=1)
        c.location = loc + vel
        c.rotation_euler = Euler([r + s for r, s in zip(rot, spin)])
        c.keyframe_insert('location', frame=2)
        c.keyframe_insert('rotation_euler', frame=2)
        cs.append(c)
    return [root, lo] + parts + cs


# ---------------------------------------------------------------- сцена

def world_and_sun():
    S = bpy.context.scene
    w = bpy.data.worlds.new('небо')
    S.world = w
    w.use_nodes = True
    nt = w.node_tree
    N, L = nt.nodes, nt.links
    bg = N['Background']
    env = N.new('ShaderNodeTexEnvironment')
    env.image = _img(SKY)
    tc = N.new('ShaderNodeTexCoord')
    mp = N.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(SUN_AZ - SKY_SUN_AZ))
    L.new(tc.outputs['Generated'], mp.inputs['Vector'])
    L.new(mp.outputs[0], env.inputs['Vector'])
    # солнце панорамы срезано — его заменяет лампа ниже (направление и высота свои)
    mn = N.new('ShaderNodeVectorMath')
    mn.operation = 'MINIMUM'
    mn.inputs[1].default_value = (6.0, 6.0, 6.0)
    L.new(env.outputs[0], mn.inputs[0])
    L.new(mn.outputs[0], bg.inputs['Color'])
    bg.inputs['Strength'].default_value = 0.85
    sun = bpy.data.lights.new('солнце', 'SUN')
    sun.energy = SUN_POWER
    sun.angle = math.radians(0.6)
    sun.color = (1.0, 0.86, 0.70)
    so = bpy.data.objects.new('солнце', sun)
    S.collection.objects.link(so)
    az, el = math.radians(SUN_AZ), math.radians(SUN_EL)
    d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
    so.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    return so


def ground(coll):
    me = bpy.data.meshes.new('асфальт')
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=200.0)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat_photo('асфальт двора', 'worn_asphalt', 1.6, value=0.95, bump=1.2))
    o = bpy.data.objects.new('асфальт', me)
    coll.objects.link(o)
    return o


def layout(kit):
    """Двор: бетонный забор ПО-2 с колючкой по северу и западу, гаражи, контейнеры, опоры с фонарями, битые машины,
    ежи и щиты, деревья за забором; станции кадров — блок «Джерси», фанерный ящик, полицейская машина, мешки."""
    for i in range(-9, 10):
        kit.inst('PC01_PO2' if i % 5 else 'PC01_PO2_BREACH', (i * 2.82, 16.0, 0.0), 90.0)
    for j in range(-4, 6):
        kit.inst('PC01_PO2', (-25.0, j * 2.82 + 2.0, 0.0), 0.0)
    for j in range(4):
        kit.inst('PC02_GARAGE_OPEN' if j == 2 else 'PC02_GARAGE', (24.0, 9.0 - j * 3.5, 0.0), -90.0)
    kit.inst('PC03_C20_GREEN', (-14.0, 9.0, 0.0), 78.0)
    kit.inst('PC03_C40_BLUE', (-18.0, -6.0, 0.0), 4.0)
    kit.inst('PC03_C20_OPEN', (14.0, -14.0, 0.0), 30.0)
    for x, y, r in ((-9.0, 14.6, 180.0), (5.0, 14.6, 180.0), (18.0, 14.6, 180.0), (-23.6, -6.0, 90.0)):
        kit.inst('PC04_POLE04_LAMP', (x, y, 0.0), r)
    kit.inst('PV_sedan_burnt', (-7.0, 9.5, 0.0), 63.0)
    kit.inst('PV_hatch_wreck', (13.0, 5.0, 0.0), -18.0)
    kit.inst('PV_sedan_wreck', (-3.0, -13.0, 0.0), 101.0)
    kit.inst('PV_gazel_open', (6.0, -17.0, 0.0), 8.0)
    for x, y, r in ((-3.5, 6.0, 15.0), (-2.0, 7.2, 40.0), (9.0, -6.0, 20.0)):
        kit.inst('U09_01', (x, y, 0.0), r)
    kit.inst('U15_04', (3.0, 8.5, 0.0), -10.0)
    kit.inst('R02', (-20.0, 3.0, 0.0), 90.0)
    kit.inst('U01_05', (8.0, 9.5, 0.0), 5.0)
    kit.inst('U01_04', (1.6, -2.4, 0.0), 0.0)
    kit.inst('U01_04', (2.2, -2.9, 0.0), 30.0)
    kit.inst('U11_02', (-10.0, -10.0, 0.0), 30.0)
    for x, y, mid in ((10.0, 22.0, 'P_birch_a'), (16.0, 24.0, 'P_linden_a'), (23.0, 20.0, 'P_poplar_a'),
                      (30.0, 12.0, 'P_birch_b'), (-34.0, -6.0, 'P_linden_b'), (-33.0, -17.0, 'P_poplar_b'),
                      (4.0, -30.0, 'P_birch_a'), (-12.0, -28.0, 'P_linden_a'), (18.0, -26.0, 'P_birch_b')):
        kit.inst(mid, (x, y, 0.0), (x * 37.0) % 360.0)


def camera(name, loc, target, lens, fstop, focus=None):
    cam = bpy.data.cameras.new(name)
    cam.lens = lens
    cam.sensor_width = 36.0
    cam.dof.use_dof = True
    cam.dof.aperture_fstop = fstop
    o = bpy.data.objects.new(name, cam)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.dof.focus_distance = ((Vector(focus) if focus else Vector(target)) - Vector(loc)).length
    return o


def render_settings(w, h, samples):
    S = bpy.context.scene
    S.render.engine = 'CYCLES'
    S.cycles.device = 'GPU'
    try:
        prefs = bpy.context.preferences.addons['cycles'].preferences
        prefs.compute_device_type = 'OPTIX'
        prefs.get_devices()
        for d in prefs.devices:
            d.use = d.type != 'CPU'
    except Exception as ex:  # noqa: BLE001
        log('видеокарта:', ex)
    S.cycles.samples = samples
    S.cycles.use_denoising = True
    S.cycles.denoiser = 'OPENIMAGEDENOISE'
    S.cycles.max_bounces = 8
    S.cycles.volume_bounces = 1
    S.cycles.volume_step_rate = 0.5
    S.render.resolution_x, S.render.resolution_y = w, h
    S.render.resolution_percentage = 100
    S.render.film_transparent = False
    S.render.use_motion_blur = True
    S.render.motion_blur_shutter = 0.22
    S.view_settings.view_transform = 'AgX'
    S.view_settings.look = 'AgX - Medium High Contrast'
    S.view_settings.exposure = 0.0
    S.frame_set(1)


def main():
    a = sys.argv[sys.argv.index('--') + 1:]
    out = os.path.abspath(a[0])
    only = a[1].split(',') if len(a) > 1 and a[1] not in ('', 'all') else None
    w, h, samples = (int(a[2]), int(a[3]), int(a[4])) if len(a) > 4 else (2560, 1440, 256)
    save = a[5] if len(a) > 5 else None
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=SRC)
    for o in list(bpy.data.objects):
        if any(c.name == 'Студия просмотра' for c in o.users_collection):
            bpy.data.objects.remove(o)
    for c in list(bpy.data.collections):
        if c.name == 'Студия просмотра':
            bpy.data.collections.remove(c)
    for c in bpy.data.collections:
        if c.name.startswith('Магазин на 30'):
            c.hide_render = False
            c.hide_viewport = False
    S = bpy.context.scene
    S.unit_settings.length_unit = 'METERS'
    S.frame_start, S.frame_end = 1, 2
    env = bpy.data.collections.new('двор')
    S.collection.children.link(env)
    props = bpy.data.collections.new('мелочь у ствола')
    S.collection.children.link(props)
    gun = Gun()
    world_and_sun()
    gnd = ground(env)
    kit = Kit(env)
    layout(kit)
    plant_materials()
    ammo = Ammo(props)
    # станции
    jersey, jm = kit.real('U01_01', (0.0, 0.0, 0.0), 0.0)
    conc = mat_photo('бетон блока', 'rough_concrete', 0.9, box=True, value=1.05, bump=1.4)
    for o in jm:
        o.data.materials.clear()
        o.data.materials.append(conc)
    crate, cm = kit.real('U14_02', (5.0, -3.0, 0.0), 12.0)
    car, carm = kit.real('PV_police_open', (-8.0, -1.5, 0.0), -62.0)
    bags, bm_ = kit.real('U03_02', (4.0, 4.0, 0.0), 8.0)
    _, bm2 = kit.real('U03_02', (6.0, 4.3, 0.0), -6.0)
    slab, sm = kit.real('PC01_PO2_FALLEN', (-2.0, -4.0, 0.0), -45.0)
    slab_mat = mat_photo('бетон плиты', 'concrete_floor_worn_001', 1.1, box=True, value=0.9, bump=1.5)
    for o in sm:
        o.data.materials.clear()
        o.data.materials.append(slab_mat)
    sack = mat_bags('мешки с песком', (0.50, 0.44, 0.30), 0.22)
    for o in bm_ + bm2:
        o.data.materials.clear()
        o.data.materials.append(sack)
    t_crate, t_car, t_bags, t_slab = bvh(cm), bvh(carm), bvh(bm_), bvh(sm)
    t_ground = bvh([gnd])
    fire = build_fire(props, gun, ammo)
    extras = {k: [] for k in ('2_bolt', '5_ground')}
    render_settings(w, h, samples)

    def show(objs, on):
        for o in objs:
            o.hide_render = not on
            o.hide_viewport = not on

    def lcam(name, cam_l, tgt_l, lens, fstop, focus_l=None):
        """Камера в координатах ствола (после позы и укладки): x — вдоль ствола, y — левый борт, z — верх."""
        return camera(name, gun.world(Vector(cam_l)), gun.world(Vector(tgt_l)), lens, fstop,
                      gun.world(Vector(focus_l)) if focus_l else None)

    def on_surface(tree, p_local, lift):
        p = gun.world(Vector(p_local))
        z, _ = surface(tree, p.x, p.y)
        return Vector((p.x, p.y, z + lift))

    shots = {}

    # 1. в статике: на поваленной плите забора ПО-2, на правом боку (левый борт вверх), магазином на 30 к камере
    def s1():
        gun.pose('static', '30')
        pts = [o.matrix_world @ Vector(c) for o in sm for c in o.bound_box]
        c = sum(pts, Vector()) / len(pts)
        z, _ = surface(t_slab, c.x, c.y)
        gun.place((c.x, c.y, z + 0.3), -45.0, 90.0, t_slab, center=(-0.14, 0.0, -0.09))
        return lcam('кадр 1', (-0.06, 0.25, -1.14), (-0.15, 0.075, -0.06), 55.0, 6.3, focus_l=(-0.15, 0.0, -0.06))
    shots['1_static'] = s1

    # 2. затвор на задержке: на фанерном ящике правым бортом вверх (окно выброса открыто), магазин вынут — рядом,
    # патроны россыпью, один стоит
    def s2():
        gun.pose('bolt_back', 'none')
        c = crate.matrix_world.translation
        cz, _ = surface(t_crate, c.x, c.y)
        gun.place((c.x + 0.02, c.y + 0.05, cz + 0.3), 196.0, -90.0, t_crate, center=(-0.12, 0.0, -0.02))
        if not extras['2_bolt']:
            mag = gun.mag13.copy()
            mag.parent = None
            props.objects.link(mag)
            mag.hide_render = mag.hide_viewport = False
            mag.matrix_world = gun.root.matrix_world @ Matrix.Rotation(math.radians(-128.0), 4, 'Y') @ gun.rest['Mag13']
            bpy.context.view_layer.update()
            pts = [mag.matrix_world @ v.co for v in mag.data.vertices]
            mc = sum(pts, Vector()) / len(pts)
            want = gun.world(Vector((0.07, 0.0, -0.14)))
            mag.location.x += want.x - mc.x
            mag.location.y += want.y - mc.y
            bpy.context.view_layer.update()
            dz = min((mag.matrix_world @ v.co).z for v in mag.data.vertices) - cz
            mag.location.z -= dz - 0.0004
            rs = []
            for (lx, lz, yaw) in ((0.19, -0.05, 30.0), (0.225, -0.08, 75.0), (0.17, -0.105, 112.0)):
                rs.append(ammo.add(False, on_surface(t_crate, (lx, 0.0, lz), 0.00605),
                                   (0.0, math.radians(90.0), math.radians(yaw))))
            rs.append(ammo.add(False, on_surface(t_crate, (0.245, 0.0, -0.03), 0.0002), (0.0, 0.0, 0.0)))
            extras['2_bolt'] = [mag] + rs
        show(extras['2_bolt'], True)
        return lcam('кадр 2', (0.13, -0.56, -0.36), (0.01, 0.0, -0.07), 50.0, 8.0, focus_l=(-0.02, 0.0, 0.0))
    shots['2_bolt'] = s2

    # 3. приклад сложен: на капоте полицейской машины, правым бортом вверх — приклад лежит вдоль правого борта
    def s3():
        gun.pose('folded', '30')
        hood = car.matrix_world @ Vector((0.0, -1.55, 0.0))
        hz, n = surface(t_car, hood.x, hood.y)
        gun.place((hood.x, hood.y, hz + 0.2), -62.0 + 70.0, -90.0, t_car)
        tgt = gun.world(Vector((-0.08, 0.0, 0.0)))
        return camera('кадр 3', tgt + Vector((0.62, -0.72, 0.40)), tgt, 55.0, 5.6)
    shots['3_folded'] = s3

    # 4. во время стрельбы: упор магазином в мешки, очередь — затвор на ходу, вспышка, гильзы в воздухе
    def s4():
        gun.pose('firing', '30')
        bz, _ = surface(t_bags, 4.0, 4.0)
        gun.place((4.0, 3.93, bz + 0.25), 90.0 + 8.0, 0.0, t_bags, pitch=-3.0)
        tgt = gun.world(Vector((0.03, 0.0, 0.02)))
        return camera('кадр 4', tgt + Vector((0.56, 0.30, 0.03)), tgt, 50.0, 7.1, focus=gun.world(PORT))
    shots['4_firing'] = s4

    # 5. на моё усмотрение: с асфальта — ствол на земле среди стреляных гильз, низкое солнце сбоку
    def s5():
        gun.pose('static', '30')
        gz, _ = surface(t_ground, 1.5, -6.0)
        gun.place((1.5, -6.0, gz + 0.2), -45.0, 90.0, t_ground, center=(-0.14, 0.0, -0.09))
        if not extras['5_ground']:
            rnd = random.Random(45)
            cs = []
            # гильзы: впереди (не в резкости), у магазина, справа у дула, за стволом, у приклада; две стоят
            for i, (lx, lz) in enumerate(((-0.30, -0.44), (0.03, -0.52), (-0.07, -0.38), (0.09, -0.31), (-0.26, -0.33),
                                          (0.22, -0.12), (0.31, 0.03), (-0.36, 0.15), (-0.05, 0.19), (0.13, 0.24),
                                          (-0.52, 0.06), (-0.57, -0.17), (0.25, -0.24), (0.42, -0.36))):
                upright = i in (4, 12)
                cs.append(ammo.add(True, on_surface(t_ground, (lx, 0.0, lz), 0.0002 if upright else 0.0061),
                                   (0.0, 0.0 if upright else math.radians(90.0), rnd.uniform(0, 6.28))))
            extras['5_ground'] = cs
        show(extras['5_ground'], True)
        return lcam('кадр 5', (-0.17, 0.13, -1.0), (-0.17, 0.0, -0.08), 50.0, 4.0)
    shots['5_ground'] = s5

    for name, fn in shots.items():
        if only and name not in only:
            continue
        for objs in extras.values():
            show(objs, False)
        show(fire, name == '4_firing')
        cam = fn()
        S.camera = cam
        S.frame_set(1)
        S.render.use_motion_blur = name == '4_firing'
        S.view_settings.exposure = EXPOSURE.get(name, 0.3)
        S.render.filepath = os.path.join(out, f'ИЗЛОМ-45_{name}.png')
        if save is None or only:
            bpy.ops.render.render(write_still=True)
            log('SHOT', S.render.filepath)
    if save:
        bpy.ops.wm.save_as_mainfile(filepath=save, compress=True)
        log('SAVED', save)


if __name__ == '__main__':
    main()
