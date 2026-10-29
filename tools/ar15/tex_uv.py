# AR-15 «ГРАНЬ-15», производственная развёртка через RizomUV (решение владельца: развёртка — в RizomUV).
# Геометрия не меняется: в OBJ уходят вершины и грани сеток (порядок вершин сохраняется), обратно берутся только UV.
# Подвижные детали, родители, драйверы и AR15_Controls не трогаются.
#   export — наборы tex_sets.SETS → <WORK>/rz/<набор>_in.obj (мм, по одной копии общей сетки), <набор>_in_map.json
#   import — <WORK>/rz/<набор>_out.obj (из rz_unwrap.py) → слой развёртки «UVMap» во всех сетках, файл tex_sets.UV_BLEND
# blender --background <AR-15_геометрия_v06.blend> --factory-startup --python-exit-code 1 --python tools/ar15/tex_uv.py -- export
# ... -- import [out.blend] [набор,набор]
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bpy  # noqa: E402
import tex_sets as T  # noqa: E402

RZ = T.WORK + "/rz"


def set_objects():
    """{набор: [объекты]} и детали без набора (их быть не должно)."""
    out = {s: [] for s in T.SETS}
    loose = []
    cart = bpy.data.objects["Cartridge_556"].data.name
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        s = T.set_of(o.name)
        if s is None:
            if o.data.name == cart:      # копии патрона в магазине: общая сетка с Cartridge_556
                continue
            loose.append(o.name)
        else:
            out[s].append(o)
    return out, loose


def unique_meshes(objs):
    seen, out = set(), []
    for o in objs:
        if o.data.name not in seen:
            seen.add(o.data.name)
            out.append(o)
    return out


def beauty_triangles(me):
    """{исходная грань: [(v0, v1, v2), ...]} для многоугольников больше четырёх вершин — разбиение BEAUTY (без
    треугольников-иголок у вершин на прямой: тесселяция Blender давала их ~1100 на нижний ресивер, решатель RizomUV
    на них падал). Вершины те же, новых не добавляется."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    lay = bm.faces.layers.int.new("ar15_src")
    for f in bm.faces:
        f[lay] = f.index
    big = [f for f in bm.faces if len(f.verts) > 4]
    out = {}
    if big:
        bmesh.ops.triangulate(bm, faces=big, quad_method="BEAUTY", ngon_method="BEAUTY")
        for f in bm.faces:
            src = f[lay]
            if len(me.polygons[src].vertices) > 4:
                out.setdefault(src, []).append(tuple(v.index for v in f.verts))
    bm.free()
    return out


def write_obj(path, objs):
    """OBJ в мм: «o <имя сетки>», вершины сетки (масштаб объекта учтён). Грани до четырёх вершин — как есть,
    многоугольники больше — треугольниками Blender (RizomUV режет сложные вогнутые многоугольники неверно: плоская
    грань в 200 вершин раздувалась в развёртке втрое по площади). Внутренние диагонали — в список «не резать»
    (пары «грань, сторона», сквозная нумерация граней) для rz_unwrap.py; обратно UV ложатся на исходные грани."""
    base = 1
    area = 0.0
    face_id = 0
    diag = []
    src = {}
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("# AR-15 tex_uv export\n")
        for o in objs:
            me = o.data
            tri_of = beauty_triangles(me)
            s = o.matrix_world.to_scale()
            k = 1000.0 * (s.x + s.y + s.z) / 3.0
            if abs(s.x - s.y) > 1e-4 or abs(s.x - s.z) > 1e-4:
                print("WARN неравный масштаб", o.name, tuple(s))
            f.write(f"o {me.name}\n")
            for v in me.vertices:
                c = v.co
                f.write(f"v {c.x * k:.5f} {c.y * k:.5f} {c.z * k:.5f}\n")
            fmap = []
            for p in me.polygons:
                area += p.area * k * k
                if len(p.vertices) <= 4:
                    f.write("f " + " ".join(str(base + i) for i in p.vertices) + "\n")
                    fmap.append(p.index)
                    face_id += 1
                    continue
                ring = list(p.vertices)
                border = {frozenset((ring[i], ring[(i + 1) % len(ring)])) for i in range(len(ring))}
                for tv in tri_of[p.index]:
                    f.write("f " + " ".join(str(base + i) for i in tv) + "\n")
                    for side in range(3):
                        if frozenset((tv[side], tv[(side + 1) % 3])) not in border:
                            diag += [face_id, side]
                    fmap.append(p.index)
                    face_id += 1
            src[me.name] = fmap
            base += len(me.vertices)
    with open(path[:-4] + "_map.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump({"diag": diag, "src": src}, f)
    return area


def export(only=None):
    os.makedirs(RZ, exist_ok=True)
    sets, loose = set_objects()
    if loose:
        raise RuntimeError("детали без набора: " + ", ".join(loose))
    stats = {}
    for s, objs in sets.items():
        if only and s not in only:
            continue
        um = unique_meshes(objs)
        a = write_obj(f"{RZ}/{s}_in.obj", um)
        tris = sum(len(p.vertices) - 2 for o in um for p in o.data.polygons)
        stats[s] = {"objects": len(objs), "meshes": [o.data.name for o in um], "area_mm2": round(a), "tris": tris,
                    "res": T.SETS[s][0]}
        print(f"EXPORT {s:11} объектов {len(objs):3} сеток {len(um):3} треуг. {tris:7} площадь {a / 100:9.0f} см²")
    with open(f"{RZ}/stats.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)


def read_obj(path):
    """[(имя, [[вершины грани], ...], [(u, v) на углы граней по порядку])] из OBJ RizomUV (имена «a:003» → «a.003»)."""
    objs, vts = [], []
    cur = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("vt "):
                p = line.split()
                vts.append((float(p[1]), float(p[2])))
            elif line.startswith("o ") or line.startswith("g "):
                name = line[2:].strip().replace(":", ".")
                if cur is None or cur[0] != name:
                    cur = (name, [], [])
                    objs.append(cur)
            elif line.startswith("f "):
                vs, uv = [], []
                for tok in line.split()[1:]:
                    a = tok.split("/")
                    vs.append(int(a[0]))
                    uv.append(vts[int(a[1]) - 1])
                cur[1].append(vs)
                cur[2].extend(uv)
    return objs


def import_uv(out, only=None):
    """UV из <набор>_out.obj на исходные грани: угол грани берёт UV своей вершины из записанных граней этой исходной
    грани; расхождение (шов прошёл по диагонали многоугольника) — предупреждение с числом таких углов."""
    sets, _ = set_objects()
    total_bad = 0
    for s, objs in sets.items():
        if only and s not in only:
            continue
        path = f"{RZ}/{s}_out.obj"
        um = unique_meshes(objs)
        by_name = {d[0]: d for d in read_obj(path)}
        fmap = json.load(open(f"{RZ}/{s}_in_map.json", encoding="utf-8"))["src"]
        for o in um:
            me = o.data
            d = by_name.get(me.name)
            if d is None:
                raise RuntimeError(f"{s}: в {path} нет сетки {me.name} (есть {list(by_name)[:8]})")
            faces, uvs = d[1], d[2]
            src = fmap[me.name]
            if len(faces) != len(src):
                raise RuntimeError(f"{me.name}: граней {len(faces)} вместо {len(src)}")
            off = min(min(f_) for f_ in faces)
            corner = {}
            bad = 0
            k = 0
            for f_, pi in zip(faces, src):
                for vi in f_:
                    uv = uvs[k]
                    k += 1
                    key = (pi, vi - off)
                    old = corner.get(key)
                    if old is None:
                        corner[key] = uv
                    elif abs(old[0] - uv[0]) + abs(old[1] - uv[1]) > 1e-5:
                        bad += 1
            if bad:
                print(f"WARN {me.name}: {bad} углов с разными UV в одной грани (шов по диагонали)")
                total_bad += bad
            flat = []
            for p in me.polygons:
                for vi in p.vertices:
                    flat += corner[(p.index, vi)]
            while me.uv_layers:
                me.uv_layers.remove(me.uv_layers[0])
            lay = me.uv_layers.new(name="UVMap")
            lay.data.foreach_set("uv", flat)
        for o in objs:
            o["ar15_set"] = s
            o["ar15_mat"] = o.material_slots[0].material.name if o.material_slots and o.material_slots[0].material else ""
        print(f"IMPORT {s:11} сеток {len(um)}")
    cart = bpy.data.objects["Cartridge_556"]
    for o in bpy.data.objects:
        if o.type == "MESH" and "ar15_set" not in o and o.data == cart.data:
            o["ar15_set"] = "rounds"
            o["ar15_mat"] = cart.get("ar15_mat", "Brass")
    print("DIAG_SEAM_CORNERS", total_bad)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("SAVED", out)


if __name__ == "__main__":
    a = sys.argv[sys.argv.index("--") + 1:]
    if a[0] == "export":
        export(a[1].split(",") if len(a) > 1 else None)
    elif a[0] == "import":
        import_uv(a[1] if len(a) > 1 else T.UV_BLEND, a[2].split(",") if len(a) > 2 else None)
