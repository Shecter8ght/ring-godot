# «Осока», тепловизор ПН-36Т «ПОЛЫНЬ»: игровая сетка той же сборкой, что и принятая форма (sight_build.py), с подменами
# на время прогона — приём «Осоки» (game_retopo.py; её помощники берутся оттуда без изменений):
# - тела вращения — сегменты по прогибу хорды 0.12 мм, профиль упрощается с допуском TOL_PROFILE;
# - контуры призм и скругления углов — по допуску 0.1 мм, кромка — 2 сегмента или фаска;
# - фаски-модификаторы уже 2 мм — ребром (скругление придёт картой нормалей), шире (корпус) — 2 сегмента;
# - рифление колец (фокус, диоптрии, крышка отсека, крышка разъёма, головки винтов) — гладкое кольцо, рельеф — в карту
#   нормалей с принятой формы; нормали — по площади граней, рёбра круче 60° жёсткие.
# Имена объектов, риг (THERMAL_Controls: mode, cap) и сборка на «Осоке» — как у формы.
# "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/osoka/sight_game.py
#     -- <Осока_геометрия_v07.blend> <сборка.blend> <прицел.blend>
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402

# помощники ретопологии «Осоки» — исходник game_retopo.py без запуска сборки (хвост «patch(); build.main()…»)
_src = open(os.path.join(HERE, "game_retopo.py"), encoding="utf8").read()
_cut = _src.index("\npatch()\nbuild.main()")
G = {"__name__": "game_retopo_helpers", "__file__": os.path.join(HERE, "game_retopo.py")}
exec(compile(_src[:_cut], "game_retopo.py", "exec"), G)
lib = G["lib"]
MM = lib.MM
TOL_PROFILE = 0.08    # мм: упрощение профиля тел вращения (наглазник — гладкая кривая из 138 точек)
TOL_PROFILE_CUP = 0.3  # мм: наглазник — резина, плавная кривая из 138 точек; 0.08 давало 3.2 тыс. треугольников
TOL_ROUND = 0.16       # мм: прогиб хорды тел вращения (у «Осоки» 0.12 — 44 сегмента на Ø 87; здесь 36): бюджет
                       # владельца — до 12 тыс. на прицел
SHARP_DEG = G["SHARP_DEG"]


def lathe_game(name, prof, coll, mat=None, seg=64, cy=0.0, cz=lib.BORE_Z, smooth=True, closed=True):
    on_axis = abs(prof[0][1]) < 1e-9 and abs(prof[-1][1]) < 1e-9
    tol = TOL_PROFILE_CUP if name == "Thermal_eyecup" else TOL_PROFILE
    if closed and not on_axis and len(prof) > 8:
        prof = G["dp_closed"](prof, tol)
    elif len(prof) > 4:
        prof = G["_rdp"](prof, tol)
    rmax = max(abs(r) for _, r in prof)
    return G["_lathe"](name, prof, coll, mat, G["seg_for"](rmax, seg, tol=TOL_ROUND), cy, cz, smooth, closed)


lib.lathe = lathe_game
lib.rounded_prism = G["rounded_prism_g"]
lib.fillet = G["fillet_g"]
lib.finish = G["finish_g"]
lib.finish_small = G["finish_small_g"]
lib.grid_split = G["grid_split_g"]

import part_launcher  # noqa: E402  винты со шлицем — через lib.lathe (уже игровой)
import sight_build as SB  # noqa: E402  импорт после подмен: «from lib import …» берёт игровые функции


def knurl_ring_game(name, x0, x1, R, Ri, depth, n_around, coll, mat, cy, cz, rows=0, spp=4, ch=0.8, seg_min=0):
    """Рифлёное кольцо в игре — гладкое кольцо по середине глубины рифления, рельеф — карта нормалей."""
    r = R - depth * 0.5
    c = min(ch, (x1 - x0) * 0.3)
    prof = [(x0, Ri), (x0, r - c), (x0 + c, r), (x1 - c, r), (x1, r - c), (x1, Ri)]
    return lathe_game(name, prof, coll, mat, seg=128, cy=cy, cz=cz)


SB.knurl_ring = knurl_ring_game


def slotted_screw_game(name, center, normal, d, coll, mat="Steel_black", slot_ang=0.0):
    """Винт в игре — головка без шлица (шлиц — в карту нормалей с принятой формы): булево шлица давало 130 треугольников
    на винт."""
    from mathutils import Matrix, Vector
    r = d / 2
    h = r * 0.55
    prof = [(-0.6, 0.0), (-0.6, r), (0.0, r), (h * 0.35, r * 0.93), (h * 0.7, r * 0.72), (h, 0.0)]
    o = lathe_game(name, prof, coll, mat, seg=32)
    n = Vector(normal).normalized()
    o.data.transform(Vector((1, 0, 0)).rotation_difference(n).to_matrix().to_4x4())
    o.data.transform(Matrix.Translation(Vector(center) * MM))
    return o


part_launcher.slotted_screw = slotted_screw_game


def game_normals(objs):
    """Нормали как у «Осоки» (game_retopo.game_normals), только у деталей прицела."""
    for o in objs:
        if o.type != "MESH":
            continue
        bm = bmesh.new(); bm.from_mesh(o.data)
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002 * MM)
        bmesh.ops.dissolve_degenerate(bm, dist=0.002 * MM, edges=bm.edges)
        big = [f for f in bm.faces if len(f.verts) > 4]
        if big:
            bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="EAR_CLIP")
        loose = [vv for vv in bm.verts if not vv.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context="VERTS")
        bm.normal_update()
        for f in bm.faces:
            f.smooth = True
        lim = math.radians(SHARP_DEG)
        for e in bm.edges:
            e.smooth = e.smooth and len(e.link_faces) == 2 and e.calc_face_angle(0.0) <= lim
        bm.to_mesh(o.data); bm.free()
        o.modifiers.clear()
        lib.weighted(o)
        lib.apply_all(o)
    rows = sorted(((len(o.data.polygons) and sum(len(p.vertices) - 2 for p in o.data.polygons), o.name)
                   for o in objs if o.type == "MESH"), reverse=True)
    for n, name in rows:
        print("GAME_OBJ", n, name)
    print("GAME_TRIS", sum(r[0] for r in rows))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:]
    SB.build(*argv[:3], post=game_normals)
