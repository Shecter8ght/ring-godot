# Blender-сторона review.py: загрузка ассета, постоянная студия, ракурсы владельца и камера игры, рендер Cycles;
# выгрузка развёртки (uvdump) для метрик карт. Ничего не сохраняет в исходный .blend.
#   render <ассет> <папка> [--samples N] [--views a,b] [--channels] [--hide регулярка] [--frame json]
#   uvdump <ассет> <выход.json> [--skip регулярка]
import json
import math
import os
import re

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
HDRI = [os.path.join(ROOT, "_asset_src/vss_m_v8/hdri/studio_small_09_2k.hdr"),
        os.path.join(ROOT, "_asset_src/pm_game/sources/studio_small_09_1k.hdr")]
RES = (1280, 720)
FPS_FOV_V = 54.0                    # Balance.FPS_VIEWMODEL_FOV, «FPS • Camera» рига ВЕРАС
# корень оружия в камере рига ВЕРАС v13: правее 0.14, ниже 0.10, впереди 0.27 (ствол вдоль взгляда);
# ПМ (PM_FPS_Grip_v03): ось канала правее 0.13, ниже 0.09, задний край в 0.31 впереди
FPS_LONG = {"right": 0.14, "down": 0.10, "ahead": 0.27, "anchor": 0.25}
FPS_SHORT = {"right": 0.13, "down": 0.09, "ahead": 0.31, "anchor": 0.0}
DEFAULT_VIEWS = ["r34", "l34", "side_r", "side_l", "top", "sight", "fps", "close_rear", "close_mid", "close_front",
                 "macro_mid", "rake_f", "rake_b"]
CHANNEL_VIEWS = ["side_r", "fps", "close_mid"]
AXES = {"+X": (1, 0, 0), "-X": (-1, 0, 0), "+Y": (0, 1, 0), "-Y": (0, -1, 0), "+Z": (0, 0, 1), "-Z": (0, 0, -1)}


# ---------- загрузка ----------

def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        return
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext in (".gltf", ".glb"):
        bpy.ops.import_scene.gltf(filepath=path)
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise RuntimeError("не знаю формат " + ext)


def excluded(vl):
    res = set()

    def walk(lc):
        if lc.exclude:
            res.add(lc.collection.name)
        for c in lc.children:
            walk(c)
    walk(vl.layer_collection)
    return res


def rendered(o, vl, skip_coll):
    if o.hide_render:
        return False
    return not any(c.hide_render or c.name in skip_coll for c in o.users_collection)


def meshes(hide=""):
    vl = bpy.context.view_layer
    rx = re.compile(hide) if hide else None
    skip_coll = excluded(vl)
    res = []
    for o in bpy.context.scene.objects:
        if o.type not in ("MESH", "CURVE", "FONT"):
            continue
        if rx and rx.search(o.name):
            o.hide_render = True
            continue
        if rendered(o, vl, skip_coll):
            res.append(o)
    return res


def world_verts(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in objs:
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        n = len(me.vertices)
        if n:
            co = np.empty(n * 3, np.float32)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3).astype(np.float64)
            m = np.array(ev.matrix_world)
            out.append(co @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    return np.concatenate(out) if out else np.zeros((0, 3))


# ---------- оси оружия ----------

def frame_of(objs, pre):
    """Оси ассета: F — к дулу, U — вверх, R = F × U — правая сторона стрелка; ось канала и линия прицеливания."""
    v = world_verts(objs)
    U = Vector(AXES[pre.get("up", "+Z")])
    if "forward" in pre:
        F = Vector(AXES[pre["forward"]])
    else:
        ext = v.max(0) - v.min(0)
        cand = [i for i in range(3) if abs(U[i]) < 0.5]
        ax = max(cand, key=lambda i: ext[i])
        t = v[:, ax]
        lo, hi = t.min(), t.max()
        u = v @ np.array(U)
        tail = 0.08 * (hi - lo)
        h_lo = np.ptp(u[t < lo + tail]) if (t < lo + tail).any() else 0
        h_hi = np.ptp(u[t > hi - tail]) if (t > hi - tail).any() else 0
        F = Vector([0, 0, 0])
        F[ax] = 1.0 if h_hi <= h_lo else -1.0          # дуло — тонкий конец: у приклада и рукояти конец высокий
    R = F.cross(U).normalized()
    Fa, Ua, Ra = np.array(F), np.array(U), np.array(R)
    t, u, r = v @ Fa, v @ Ua, v @ Ra
    L = float(t.max() - t.min())
    rear = float(t.min())
    mk = {o.name.split(".")[0]: o.matrix_world.translation.copy() for o in bpy.context.scene.objects if o.type == "EMPTY"}
    if "Muzzle" in mk:
        bore_u, bore_r = mk["Muzzle"].dot(U), mk["Muzzle"].dot(R)
    else:
        front = t > t.max() - max(0.03 * L, 0.004)
        bore_u, bore_r = float(np.median(u[front])), float(np.median(r[front]))
    sight_t = None
    if "sight" in pre:
        sight_u = pre["sight"]
    elif "SightRear" in mk:
        sight_u, sight_t = mk["SightRear"].dot(U), mk["SightRear"].dot(F)
    else:
        sight_u = bore_u + 0.55 * (float(u.max()) - bore_u)
    if "sight_t" in pre:
        sight_t = pre["sight_t"]
    box = [Vector((tt, uu, rr)) for tt in (t.min(), t.max()) for uu in (u.min(), u.max()) for rr in (r.min(), r.max())]
    corners = [F * b[0] + U * b[1] + R * b[2] for b in box]
    centre = sum(corners, Vector()) / 8
    return {"F": F, "U": U, "R": R, "L": L, "rear": rear, "bore_u": float(bore_u), "bore_r": float(bore_r),
            "sight_u": float(sight_u), "sight_t": sight_t, "u_top": float(u.max()), "corners": corners, "centre": centre,
            "short": L <= pre.get("short_max_m", 0.45)}


def at(fr, frac, u=None, r=None):
    """Точка на оси канала на доле длины от затыльника."""
    return (fr["F"] * (fr["rear"] + frac * fr["L"]) + fr["U"] * (fr["bore_u"] if u is None else u)
            + fr["R"] * (fr["bore_r"] if r is None else r))


# ---------- камера ----------

def basis(d, up):
    z = -d.normalized()
    x = up.cross(z)
    if x.length < 1e-6:
        x = Vector((1, 0, 0)).cross(z)
    x.normalize()
    y = z.cross(x)
    return x, y, z


def fit_distance(target, d, up, pts, fov_h, fov_v, margin=0.9):
    x, y, z = basis(d, up)
    th, tv = math.tan(fov_h / 2) * margin, math.tan(fov_v / 2) * margin
    best = 0.0
    for p in pts:
        q = p - target
        cx, cy, cz = q.dot(x), q.dot(y), -q.dot(z)       # cz > 0 — дальше цели
        best = max(best, abs(cx) / th - cz, abs(cy) / tv - cz)
    return best


def ray_to_surface(origin, target):
    d = (target - origin)
    hit, loc, *_ = bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(), origin, d.normalized(), distance=d.length * 2)
    return loc if hit else None


def views_for(fr, names):
    F, U, R, L = fr["F"], fr["U"], fr["R"], fr["L"]
    lens50 = 2 * math.atan(18 / 50)
    vfov = lambda h: 2 * math.atan(math.tan(h / 2) * RES[1] / RES[0])  # noqa: E731
    res = {}
    for n in names:
        v = {"up": U, "fov_h": lens50, "rake": None}
        if n in ("r34", "l34", "side_r", "side_l", "top", "rake_f", "rake_b"):
            e = {"r34": 0.55 * F - 0.80 * R + 0.40 * U, "l34": -0.55 * F + 0.80 * R + 0.35 * U,
                 "side_r": -R, "side_l": R, "top": U, "rake_f": -R, "rake_b": -R}[n].normalized()
            if n == "top":
                v["up"] = -R
            if n.startswith(("side", "rake", "top")):
                v["fov_h"] = 2 * math.atan(18 / 85)
            tgt = fr["centre"]
            dist = fit_distance(tgt, -e, v["up"], fr["corners"], v["fov_h"], vfov(v["fov_h"]))
            v.update(eye=tgt + e * dist, target=tgt)
            if n.startswith("rake"):
                v["rake"] = (0.95 * F if n == "rake_f" else -0.95 * F) - 0.30 * R + 0.10 * U
        elif n == "sight":
            # чуть выше линии прицеливания из-за целика: видны верхние плоскости, уходящие к мушке
            st_ = fr["sight_t"] if fr.get("sight_t") is not None else fr["rear"] + 0.25 * L
            eye = F * (st_ - 0.25 * min(L, 0.8)) + U * (fr["sight_u"] + 0.012) + R * fr["bore_r"]
            v.update(eye=eye, target=eye + F, fov_h=2 * math.atan(18 / 85), lit=at(fr, 0.6))
        elif n == "fps":
            p = FPS_SHORT if fr["short"] else FPS_LONG
            anchor = at(fr, p["anchor"])
            eye = anchor - F * p["ahead"] - R * p["right"] + U * p["down"]
            v.update(eye=eye, target=eye + F, fov_v=math.radians(FPS_FOV_V), lit=at(fr, 0.5))
        elif n.startswith(("close_", "macro_")):
            frac = {"rear": 0.2, "mid": 0.5, "front": 0.8}[n.split("_")[1]]
            if n.startswith("close"):
                e = (0.35 * F - 0.85 * R + 0.40 * U).normalized()
                w = min(max(0.3 * L, 0.05), 0.22)
            else:
                e = (-R + 0.25 * U).normalized()
                frac = 0.45
                w = min(max(0.1 * L, 0.03), 0.08)
            tgt = at(fr, frac)
            hit = ray_to_surface(tgt + e * 2 * L, tgt)
            if hit is not None:
                tgt = hit
            dist = (w / 2) / math.tan(lens50 / 2)
            v.update(eye=tgt + e * dist, target=tgt, field_m=w)
        else:
            raise RuntimeError("нет вида " + n)
        res[n] = v
    return res


# ---------- студия ----------

def studio():
    sc = bpy.context.scene
    for o in sc.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    w = bpy.data.worlds.new("Review • студия")
    w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.45
    hdr = next((p for p in HDRI if os.path.exists(p)), None)
    mp = None
    if hdr:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(hdr, check_existing=True)
        mp = nt.nodes.new("ShaderNodeMapping")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    else:
        bg.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1)
    nt.links.new(bg.outputs[0], out.inputs[0])
    sc.world = w
    lights = {}
    for name, size in (("key", 1.0), ("fill", 1.4), ("rim", 0.6), ("rake", 0.25)):
        d = bpy.data.lights.new("Review_" + name, "AREA")
        d.shape = "DISK"
        d.size = size
        ob = bpy.data.objects.new("Review_" + name, d)
        sc.collection.objects.link(ob)
        lights[name] = ob
    cam_d = bpy.data.cameras.new("Review_cam")
    cam = bpy.data.objects.new("Review_cam", cam_d)
    sc.collection.objects.link(cam)
    sc.camera = cam
    return {"world_bg": bg, "map": mp, "lights": lights, "cam": cam}


def place(st, v, dist):
    """Свет привязан к камере (как Environment alignment Camera в Painter): у каждого вида одинаковый,
    сила растёт с квадратом расстояния — экспозиция не зависит от крупности."""
    x, y, z = basis(v["target"] - v["eye"], v["up"])
    tgt = v.get("lit", v["target"])
    k = max(dist, 0.05)
    # сила подобрана так, что серое альбедо 0.18 выходит около середины шкалы AgX (ВЕРАС: полимер ~0.3, сталь ~0.15)
    spec = {"key": ((-0.55 * x + 0.65 * y + 0.55 * z), 1.4, 22.0),
            "fill": ((0.85 * x + 0.10 * y + 0.50 * z), 1.6, 8.0),
            "rim": ((0.25 * x + 0.75 * y - 0.65 * z), 1.2, 15.0)}
    for name, (dirv, rel, energy) in spec.items():
        ob = st["lights"][name]
        p = tgt + dirv.normalized() * k * rel
        ob.location = p
        ob.rotation_euler = (tgt - p).to_track_quat("-Z", "Y").to_euler()
        ob.data.size = 0.9 * k
        ob.data.energy = energy * (k * rel) ** 2
        ob.hide_render = v["rake"] is not None
    rk = st["lights"]["rake"]
    rk.hide_render = v["rake"] is None
    if v["rake"] is not None:
        p = tgt + v["rake"].normalized() * k
        rk.location = p
        rk.rotation_euler = (tgt - p).to_track_quat("-Z", "Y").to_euler()
        rk.data.size = 0.08 * k
        rk.data.energy = 35.0 * k * k
    st["world_bg"].inputs["Strength"].default_value = 0.05 if v["rake"] is not None else 0.3
    if st["map"] is not None:                       # отражения студии тоже поворачиваются за камерой
        st["map"].inputs["Rotation"].default_value = (0, 0, math.atan2(z.y, z.x) + 2.2)


def setup_render(samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    prefs = bpy.context.preferences.addons["cycles"].preferences
    sc.cycles.device = "CPU"
    for dev in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev
            prefs.get_devices()
            if any(d.type == dev for d in prefs.devices):
                for d in prefs.devices:
                    d.use = d.type == dev
                sc.cycles.device = "GPU"
                break
        except Exception:
            continue
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.denoising_use_gpu = False          # видеопамять может держать Substance Painter
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = RES
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.exposure = 0.0
    sc.view_settings.gamma = 1.0
    sc.render.use_motion_blur = False
    sc.render.use_simplify = False


def set_look(channel):
    vs = bpy.context.scene.view_settings
    try:
        vs.view_transform = "Standard" if channel else "AgX"
        vs.look = "None"
    except TypeError:
        pass


# ---------- каналы излучением ----------

def channel_swap(objs, channel):
    """Цвет / шероховатость / металличность как излучение на выходе материала; возврат — функция отката."""
    undo = []
    done = set()
    for o in objs:
        for s in getattr(o, "material_slots", []):
            m = s.material
            if m is None or m.name in done or not m.use_nodes:
                continue
            done.add(m.name)
            nt = m.node_tree
            outn = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
            if outn is None:
                continue
            bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
            old = [l.from_socket for l in outn.inputs["Surface"].links]
            em = nt.nodes.new("ShaderNodeEmission")
            em.inputs["Strength"].default_value = 1.0
            extra = [em]
            sock = {"color": "Base Color", "rough": "Roughness", "metal": "Metallic"}[channel]
            if bsdf is None:
                em.inputs["Color"].default_value = (0.18, 0.18, 0.18, 1)
            else:
                inp = bsdf.inputs[sock]
                if channel == "color":
                    if inp.links:
                        nt.links.new(inp.links[0].from_socket, em.inputs["Color"])
                    else:
                        em.inputs["Color"].default_value = inp.default_value
                else:
                    pw = nt.nodes.new("ShaderNodeMath")      # данные 0–1 → пиксель 0–255 при Standard
                    pw.operation = "POWER"
                    pw.inputs[1].default_value = 2.2
                    extra.append(pw)
                    if inp.links:
                        nt.links.new(inp.links[0].from_socket, pw.inputs[0])
                    else:
                        pw.inputs[0].default_value = inp.default_value
                    nt.links.new(pw.outputs[0], em.inputs["Color"])
            nt.links.new(em.outputs[0], outn.inputs["Surface"])
            undo.append((nt, outn, old, extra))

    def restore():
        for nt, outn, old, extra in undo:
            for n in extra:
                nt.nodes.remove(n)
            for s in old:
                nt.links.new(s, outn.inputs["Surface"])
    return restore


# ---------- команды ----------

def render(asset, out, samples=64, views=None, channels=False, hide="", pre=None):
    pre = pre or {}
    load(asset)
    objs = meshes(hide)
    if not objs:
        raise RuntimeError("нечего рендерить: видимых сеток нет")
    fr = frame_of(objs, pre)
    names = views or DEFAULT_VIEWS
    vs = views_for(fr, names)
    st = studio()
    setup_render(samples)
    sc = bpy.context.scene
    cam = st["cam"]
    meta = {"asset": asset, "length_m": round(fr["L"], 4), "short": fr["short"],
            "forward": list(round(c, 3) for c in fr["F"]), "up": list(round(c, 3) for c in fr["U"]),
            "right": list(round(c, 3) for c in fr["R"]), "views": {}}
    os.makedirs(out, exist_ok=True)

    def shoot(n, v, path):
        tgt = v["target"]
        x, y, z = basis(tgt - v["eye"], v["up"])
        cam.matrix_world = Matrix((x, y, z)).transposed().to_4x4()
        cam.location = v["eye"]
        cd = cam.data
        cd.clip_start = 0.002
        cd.clip_end = 50.0
        if "fov_v" in v:
            cd.sensor_fit = "VERTICAL"
            cd.angle_y = v["fov_v"]
        else:
            cd.sensor_fit = "HORIZONTAL"
            cd.angle_x = v["fov_h"]
        dist = (tgt - v["eye"]).length
        place(st, v, (v["lit"] - v["eye"]).length if "lit" in v else dist)
        sc.render.filepath = path
        bpy.ops.render.render(write_still=True)
        return dist, cd

    for n, v in vs.items():
        set_look(None)
        dist, cd = shoot(n, v, os.path.join(out, n + ".png"))
        if "fov_v" in v:                             # камера игры: масштаб — на середине оружия, а не в точке взгляда
            p = FPS_SHORT if fr["short"] else FPS_LONG
            dist = p["ahead"] + (0.5 - p["anchor"]) * fr["L"]
        fov_h = cd.angle_x if cd.sensor_fit == "HORIZONTAL" else 2 * math.atan(math.tan(cd.angle_y / 2) * RES[0] / RES[1])
        field = 2 * dist * math.tan(fov_h / 2)
        meta["views"][n] = {"eye": [round(c, 4) for c in v["eye"]], "target": [round(c, 4) for c in v["target"]],
                            "fov_h_deg": round(math.degrees(fov_h), 2), "distance_m": round(dist, 4),
                            "px_per_cm_at_target": round(RES[0] / (field * 100), 2), "rake": v["rake"] is not None}
        print("VIEW", n, flush=True)
    if channels:
        sc.cycles.samples = 16
        sc.cycles.use_denoising = False
        for ch in ("color", "rough", "metal"):
            restore = channel_swap(objs, ch)
            set_look(ch)
            for n in CHANNEL_VIEWS:
                if n in vs:
                    shoot(n, vs[n], os.path.join(out, f"{n}__{ch}.png"))
                    meta["views"][n].setdefault("channels", []).append(ch)
            restore()
    with open(os.path.join(out, "views.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)


def material_images(m):
    names = []
    if m is None or not m.use_nodes:
        return names
    seen = set()

    def walk(nt):
        if nt is None or nt.name in seen:
            return
        seen.add(nt.name)
        for n in nt.nodes:
            if n.type == "TEX_IMAGE" and n.image:
                names.append(os.path.basename(n.image.filepath) or n.image.name)
            elif n.type == "GROUP":
                walk(n.node_tree)
    walk(m.node_tree)
    return names


def uvdump(asset, out_json, skip=""):
    load(asset)
    rx = re.compile(skip) if skip else None
    dg = bpy.context.evaluated_depsgraph_get()
    unit = bpy.context.scene.unit_settings.scale_length or 1.0
    per = {}
    for o in bpy.context.scene.objects:
        if o.type != "MESH" or (rx and rx.search(o.name)):
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        uvl = me.uv_layers.active_render or me.uv_layers.active
        if uvl is None or not len(me.polygons):
            ev.to_mesh_clear()
            continue
        me.calc_loop_triangles()
        nt = len(me.loop_triangles)
        loops = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("loops", loops)
        verts = np.empty(nt * 3, np.int32)
        me.loop_triangles.foreach_get("vertices", verts)
        mi = np.empty(nt, np.int32)
        me.loop_triangles.foreach_get("material_index", mi)
        uv = np.empty(len(me.loops) * 2, np.float32)
        uvl.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)[loops].reshape(nt, 3, 2)
        uv[..., 1] = 1.0 - uv[..., 1]                    # в Blender v снизу вверх, в карте — сверху вниз
        co = np.empty(len(me.vertices) * 3, np.float32)
        me.vertices.foreach_get("co", co)
        m = np.array(ev.matrix_world)
        co = co.reshape(-1, 3).astype(np.float64) @ m[:3, :3].T + m[:3, 3]
        tri = co[verts].reshape(nt, 3, 3)
        area = 0.5 * np.linalg.norm(np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0]), axis=1) * (unit * 100) ** 2
        slots = [s.material for s in o.material_slots] or [None]
        for idx in np.unique(mi):
            mat = slots[idx] if idx < len(slots) else None
            name = mat.name if mat else "(нет)"
            rec = per.setdefault(name, {"name": name, "images": material_images(mat), "objects": [], "uv": [], "area": [], "obj": []})
            if o.name not in rec["objects"]:
                rec["objects"].append(o.name)
            sel = mi == idx
            rec["uv"].append(uv[sel])
            rec["area"].append(area[sel].astype(np.float32))
            rec["obj"].append(np.full(int(sel.sum()), rec["objects"].index(o.name), np.int32))
        ev.to_mesh_clear()
    arrays = {}
    meta = {"asset": asset, "materials": []}
    for i, rec in enumerate(per.values()):
        arrays[f"m{i}_uv"] = np.concatenate(rec["uv"])
        arrays[f"m{i}_area"] = np.concatenate(rec["area"])
        arrays[f"m{i}_obj"] = np.concatenate(rec["obj"])
        meta["materials"].append({"name": rec["name"], "images": rec["images"], "objects": rec["objects"]})
    np.savez_compressed(os.path.splitext(out_json)[0] + ".npz", **arrays)
    with open(out_json, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print("UVDUMP", len(meta["materials"]), "материалов", flush=True)


def main(argv):
    cmd = argv[0]
    opt = {}
    pos = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a in ("--channels",):
            opt[a[2:]] = True
            i += 1
        elif a.startswith("--"):
            opt[a[2:]] = argv[i + 1]
            i += 2
        else:
            pos.append(a)
            i += 1
    if cmd == "render":
        render(pos[0], pos[1], int(opt.get("samples", 64)),
               [s for s in opt.get("views", "").split(",") if s] or None, bool(opt.get("channels")),
               opt.get("hide", ""), json.loads(opt["frame"]) if "frame" in opt else None)
    elif cmd == "uvdump":
        uvdump(pos[0], pos[1], opt.get("skip", ""))
    else:
        raise RuntimeError("команда: render | uvdump")
