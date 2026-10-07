"""Снаряжение на стойках и столах убежища: шлем, бронежилет, рюкзак. bpy → GLB вместо грубых прежних.

У прежних моделей не было сглаживания и подразделения — полусфера-шлем и коробки-подсумки. Здесь
мягкие формы: подразделённые поверхности, сглаживание по углу, фаски, стежки и фурнитура; материалы
и метрические UV — те же, что у всего убежища (kit из build_shelter_assets.py).
"D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python tools/build_shelter_gear.py
"""
from __future__ import annotations
import json, math, sys
from pathlib import Path
import bpy, bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_shelter_assets as kit

OUT = kit.OUT
box, cyl, curve, begin, collision, export, xyz = kit.box, kit.cyl, kit.curve, kit.begin, kit.collision, kit.export, kit.xyz


def soften(o, levels: int = 2, angle: float = 40.0) -> None:
    # Подразделение и сглаживание: ткань и литая сталь без граней многогранника.
    bpy.context.view_layer.objects.active = o
    mod = o.modifiers.new('Soft form', 'SUBSURF'); mod.levels = levels; mod.render_levels = levels
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.ops.object.shade_smooth()
    if hasattr(bpy.ops.object, 'shade_auto_smooth'):
        try:
            bpy.ops.object.shade_auto_smooth(angle=math.radians(angle))
        except Exception:
            pass


def soft_box(name, pos, size, m, levels=2, round_k=.18):
    # Коробка ткани: фаска перед подразделением задаёт мягкий, но не надутый край.
    o = box(name, pos, size, m, min(size) * round_k)
    soften(o, levels)
    return o


def helmet() -> None:
    # СШ-68: купол с отгибом поля назад и по бокам, гребень краски, подтулейник, подбородочный ремень.
    begin()
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=1, location=xyz((0, .0, 0)))
    o = bpy.context.object
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -.22], context='VERTS')
    for v in bm.verts:
        x, y, z = v.co
        # купол: ширина 0.25, длина 0.29, высота 0.155 над краем
        sx, sy, sz = .125, .145, .175
        flare = max(0.0, (.15 - z)) / .37
        back = max(0.0, y) / 1.0
        k = 1.0 + .28 * flare * (.55 + .45 * back)
        v.co = Vector((x * sx * k, y * sy * k, (z + .22) * sz * .82))
    bm.to_mesh(o.data); bm.free()
    mod = o.modifiers.new('Shell', 'SOLIDIFY'); mod.thickness = .004; mod.offset = -1
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier=mod.name)
    kit.finish(o, 'Steel shell', 'PaintedSteel')
    soften(o, 1)
    # закатанный край по нижней кромке
    rim = []
    for i in range(65):
        a = i * math.tau / 64
        r = 1.0 + .28 * .4 * (.55 + .45 * max(0.0, -math.cos(a)))
        rim.append((math.sin(a) * .125 * r * 1.02, .0, math.cos(a) * .145 * r * 1.02))
    edge = curve('Rolled edge', rim, .0035, 'PaintedSteel')
    bpy.ops.object.shade_smooth()
    # подтулейное устройство: ремни и кожаные лепестки внутри
    for a in (0, 60, 120, 180, 240, 300):
        r = math.radians(a)
        curve('Liner strap', [(math.sin(r) * .105, .035, math.cos(r) * .12), (math.sin(r) * .06, .1, math.cos(r) * .07), (0, .118, 0)], .006, 'Leatherette')
    for side in (-1, 1):
        cyl('Liner rivet', (side * .123, .055, .0), (side * .128, .055, .0), .007, 'BareSteel', verts=12)
        # ремень лежит на столе перед шлемом, а не висит сквозь столешницу
        curve('Chinstrap', [(side * .118, .045, .01), (side * .125, .008, .06), (side * .07, .006, .16), (0, .006, .175)], .007, 'Canvas')
    bpy.ops.object.shade_smooth()
    collision((0, .06, 0), (.27, .13, .31))
    export('Helmet')


def vest() -> None:
    # Плитник: передняя и задняя панели по форме корпуса, плечи, камербанд, ряды строп MOLLE,
    # три магазинных подсумка с клапанами, подсумок-«админка», пряжки.
    begin()
    soft_box('Front panel', (0, .33, .06), (.36, .5, .055), 'MilitaryFabric', 2, .3)
    soft_box('Back panel', (0, .35, -.13), (.37, .54, .05), 'MilitaryFabric', 2, .3)
    for x in (-.13, .13):
        # плечевая лямка — плоская полоса через плечо, а не трубка
        soft_box('Shoulder strap front', (x, .6, .045), (.07, .06, .03), 'MilitaryFabric', 1, .25)
        soft_box('Shoulder strap top', (x, .63, -.035), (.07, .025, .15), 'MilitaryFabric', 1, .25)
        soft_box('Shoulder strap back', (x, .6, -.115), (.07, .06, .03), 'MilitaryFabric', 1, .25)
    for side in (-1, 1):
        # камербанд — плоская боковая панель между передом и спиной
        soft_box('Cummerbund', (side * .195, .23, -.035), (.025, .17, .17), 'MilitaryFabric', 1, .25)
    for y in (.16, .22, .28, .34, .40):
        box('MOLLE webbing', (0, y, .091), (.34, .018, .006), 'Canvas', .002)
        box('MOLLE webbing back', (0, y + .02, -.157), (.34, .018, .006), 'Canvas', .002)
    for x in (-.11, 0, .11):
        soft_box('Magazine pouch', (x, .25, .115), (.095, .19, .07), 'MilitaryFabric', 2, .2)
        soft_box('Pouch flap', (x, .335, .128), (.098, .05, .06), 'MilitaryFabric', 1, .2)
        box('Flap buckle', (x, .32, .162), (.03, .025, .008), 'Rubber', .003)
    soft_box('Admin pouch', (0, .46, .1), (.22, .11, .04), 'MilitaryFabric', 2, .2)
    box('Admin zipper', (0, .505, .121), (.2, .008, .004), 'BareSteel', .001)
    box('Name tape loop', (0, .53, .093), (.12, .035, .004), 'Canvas', .001)
    for x in (-.17, .17):
        box('Side release buckle', (x, .22, .07), (.035, .05, .012), 'Rubber', .004)
    export('TacticalVest')


def backpack() -> None:
    # Рюкзак 30–40 л: мягкий корпус, клапан с пряжками, фронтальный и боковые карманы,
    # лямки с подкладкой, поясной ремень, ручка для переноски, стяжки.
    begin()
    soft_box('Pack body', (0, .29, 0), (.34, .52, .22), 'MilitaryFabric', 2, .3)
    soft_box('Top lid', (0, .555, .01), (.35, .07, .24), 'MilitaryFabric', 2, .3)
    soft_box('Front pocket', (0, .22, .128), (.27, .25, .07), 'Canvas', 2, .25)
    for side in (-1, 1):
        soft_box('Side pocket', (side * .185, .2, 0), (.06, .2, .15), 'MilitaryFabric', 2, .25)
        curve('Compression strap', [(side * .17, .38, .11), (side * .175, .38, -.11)], .008, 'Rubber')
        curve('Shoulder harness', [(side * .09, .5, -.12), (side * .11, .4, -.16), (side * .1, .15, -.15), (side * .14, .07, -.11)], .022, 'Canvas')
        bpy.ops.object.shade_smooth()
    for x in (-.08, .08):
        curve('Lid strap', [(x, .58, .1), (x, .48, .13), (x, .41, .13)], .009, 'Rubber')
        box('Lid buckle', (x, .42, .137), (.035, .045, .012), 'Rubber', .004)
    curve('Haul loop', [(-.04, .59, -.1), (0, .62, -.1), (.04, .59, -.1)], .008, 'Rubber')
    box('Front zipper', (0, .33, .165), (.22, .008, .005), 'BareSteel', .001)
    collision((0, .3, 0), (.42, .6, .3))
    export('Backpack')


if __name__ == '__main__':
    previous = json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
    helmet()
    vest()
    backpack()
    previous.update(kit.ASSETS)
    (OUT/'manifest.json').write_text(json.dumps(previous, ensure_ascii=False, indent=2), encoding='utf-8')
    print('GEAR_DONE', {k: v['triangles'] for k, v in kit.ASSETS.items()}, flush=True)
