"""Калибровка фаланг по геометрии оружия (после hand_fit_dump.tscn)."""
import json
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import numpy as np
from scipy.spatial import ConvexHull
from scipy.spatial.transform import Rotation
from scipy.optimize import minimize, differential_evolution

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "tools/hand_fit/input.json").read_text(encoding="utf-8"))


def matrix(value):
    m = np.eye(4)
    m[:3, :] = np.asarray(value).T
    return m


names = [b["name"] for b in DATA["bones"]]
parents = np.array([b["parent"] for b in DATA["bones"]])
rest = np.array([matrix(b["rest"]) for b in DATA["bones"]])
mesh = DATA["meshes"][0]
points = np.c_[mesh["points"], np.ones(len(mesh["points"]))]
weights = np.array(mesh["weights"]).reshape(len(points), -1)
indices = np.array(mesh["bones"]).reshape(weights.shape)
binds = np.array([matrix(b["pose"]) for b in mesh["binds"]])
bone_map = np.array([b["bone"] for b in mesh["binds"]])
bone_ids = bone_map[indices]
local_points = np.einsum("nvij,nj->nvi", binds[indices], points)
dominant = bone_ids[np.arange(len(points)), weights.argmax(axis=1)]


def skin(pose, selection):
    return np.einsum("nv,nvij,nvj->ni", weights[selection], pose[bone_ids[selection]], local_points[selection])[:, :3]


def fit(case, side, fitted=None, audit_only=False):
    initial = np.array([matrix(x) for x in case["poses"]])
    pose = initial.copy()
    hand = names.index("mixamorig_" + side + "Hand")
    descendants = [i for i, n in enumerate(names) if n.startswith("mixamorig_" + side + "Hand")]
    local = np.array([np.linalg.inv(initial[parents[i]]) @ initial[i] if parents[i] >= 0 else initial[i] for i in range(len(names))])
    # Равномерная выборка вершин кожи; плотность Subdivision не меняет вес цели.
    selection = np.where(np.isin(dominant, descendants))[0]
    selection = selection[::max(1, len(selection) // 650)]
    palm = np.where(dominant == hand)[0]
    palm = palm[::max(1, len(palm) // 160)]
    bounds = skin(initial, selection)
    lo, hi = bounds.min(axis=0) - .05, bounds.max(axis=0) + .05
    equations = []
    convex_parts = []
    for hull in case["hulls"]:
        raw = np.asarray(hull)
        # _sweep: 48 вершин на пару восьмиугольных сечений и два торца по 18.
        # Разделяем изгибы: общая выпуклая оболочка заполнила бы пустоту под шейкой.
        pieces = [raw[i:i + 48] for i in range(0, len(raw) - 36, 48)]
        sweep = ((len(raw) - 36) % 48 == 0 and pieces
                 and all(len(np.unique(p, axis=0)) == 16 for p in pieces)
                 and len(np.unique(raw[-36:-18], axis=0)) == 8
                 and len(np.unique(raw[-18:], axis=0)) == 8)
        convex_parts.extend(pieces if sweep else [raw])
    for hull in convex_parts:
        vertices = np.unique(np.asarray(hull), axis=0)
        if len(vertices) < 4 or np.any(vertices.max(axis=0) < lo) or np.any(vertices.min(axis=0) > hi):
            continue
        try:
            eq = ConvexHull(vertices).equations
            eq = np.unique(np.round(eq, 7), axis=0)
            equations.append(eq)
        except Exception:
            pass
    # Плоскости упакованы: одно умножение вместо Python-цикла на каждую деталь.
    starts = np.cumsum([0] + [len(e) for e in equations[:-1]])
    planes = np.concatenate(equations)
    normals = planes[:, :3].T.copy()
    offsets = planes[:, 3]

    def sdf(p):
        return np.maximum.reduceat(p @ normals + offsets, starts, axis=1).min(axis=1)

    def update():
        for i in descendants:
            if i != hand:
                pose[i] = pose[parents[i]] @ local[i]

    def collision(selected):
        d = sdf(skin(pose, selected))
        penetration = np.minimum(d - .0004, 0)
        return np.mean(penetration ** 2) * 4e7 + np.min(penetration) ** 2 * 1e7, d

    def measure():
        measured = {}
        for finger in ["Index", "Middle", "Ring", "Pinky", "Thumb"]:
            chain = [names.index("mixamorig_" + side + "Hand" + finger + str(j)) for j in range(1, 4)]
            selected = np.where(np.isin(dominant, chain))[0]
            tip = np.where(dominant == chain[-1])[0]
            d = sdf(skin(pose, selected))
            measured[finger] = {"penetration_mm": round(float(max(0, -d.min())) * 1000, 2), "gap_mm": round(float(max(0, sdf(skin(pose, tip)).min())) * 1000, 2)}
        return measured

    if fitted:
        for joint, quat in fitted["joints"].items():
            bone = names.index("mixamorig_" + side + "Hand" + joint)
            local[bone, :3, :3] = Rotation.from_quat(quat).as_matrix()
        pose[hand, :3, 3] = initial[hand, :3, 3] + fitted["shift"]
        update()
    if audit_only:
        return {**fitted, "metrics": measure()}

    # Подводим основание ладони к поверхности, не пряча её внутрь рукояти.
    use_all = bool(fitted)
    def wrist_cost(x):
        pose[hand, :3, 3] = initial[hand, :3, 3] + x
        update()
        penalty, d = collision(selection if use_all else palm)
        contact = np.sort(np.maximum(d, 0))[:max(4, len(d) // 8)]
        finger_contact = 0.0
        if use_all:
            for name in ["Index", "Middle", "Ring", "Pinky", "Thumb"]:
                tip_bone = names.index("mixamorig_" + side + "Hand" + name + "3")
                tip_selection = np.where(dominant == tip_bone)[0][::4]
                finger_contact += max(0, sdf(skin(pose, tip_selection)).min()) ** 2
        return penalty + np.mean(contact ** 2) * 2e5 + finger_contact * 4e5 + np.dot(x, x) * 100

    wrist = minimize(wrist_cost, fitted["shift"] if fitted else np.zeros(3), method="Powell", bounds=[(-.035, .035)] * 3,
                     options={"maxiter": 35, "xtol": .00005}).x
    wrist_cost(wrist)
    seed_local = local.copy()
    for refinement in range(3):
        contact_results = {}
        for finger in ["Index", "Middle", "Ring", "Pinky", "Thumb"]:
            chain = [names.index("mixamorig_" + side + "Hand" + finger + str(j)) for j in range(1, 4)]
            selected = np.where((np.isin(bone_ids, chain) & (weights > .15)).any(axis=1))[0]
            selected = selected[::max(1, len(selected) // 180)]
            tip = np.where(dominant == chain[-1])[0]
            tip = tip[::max(1, len(tip) // 60)]
            original = seed_local[chain].copy()
            frame_y = (rest[names.index("mixamorig_" + side + "HandMiddle1"), :3, 3] - rest[hand, :3, 3])
            frame_y /= np.linalg.norm(frame_y)
            across = rest[names.index("mixamorig_" + side + "HandIndex1"), :3, 3] - rest[names.index("mixamorig_" + side + "HandPinky1"), :3, 3]
            across -= frame_y * np.dot(across, frame_y)
            across /= np.linalg.norm(across)
            palm_direction = np.cross(across, frame_y) * (1 if side == "Right" else -1)
            axes = []
            for bone in chain:
                axis = np.cross(rest[bone, :3, 1], palm_direction)
                axis = np.linalg.inv(rest[bone, :3, :3]) @ axis
                axes.append(axis / np.linalg.norm(axis))
    
            def set_angles(x):
                for j, bone in enumerate(chain):
                    local[bone] = original[j].copy()
                    local[bone, :3, :3] = original[j, :3, :3] @ Rotation.from_rotvec(axes[j] * np.deg2rad(x[j])).as_matrix()
                if finger == "Thumb":
                    local[chain[0], :3, :3] = original[0, :3, :3] @ Rotation.from_rotvec(np.deg2rad(x[3:6])).as_matrix() @ Rotation.from_rotvec(axes[0] * np.deg2rad(x[0])).as_matrix()
                else:
                    spread_axis = np.linalg.inv(rest[chain[0], :3, :3]) @ palm_direction
                    local[chain[0], :3, :3] = local[chain[0], :3, :3] @ Rotation.from_rotvec(spread_axis * np.deg2rad(x[3])).as_matrix()
                update()
    
            def cost(x):
                set_angles(x)
                penalty, d = collision(selected)
                dt = sdf(skin(pose, tip))
                contact = np.sort(np.maximum(dt, 0))[:max(4, len(dt) // 5)]
                # Сильнее штрафуем пересечение всей фаланги, чем зазор у подушечки.
                return penalty + np.mean(contact ** 2) * 2e5 + np.dot(x, x) * .000003
    
            limits = [(-10, 85), (-75, 10), (-50, 40)]
            if finger == "Index" and side == "Right":
                limits = [(-10, 85), (-45, 50), (-30, 60)]
            if finger == "Thumb":
                limits = [(-20, 60), (-40, 60), (-30, 60)] + [(-70, 70)] * 3
            else:
                limits.append((-20, 20))
            if fitted:
                limits = [(-25, 25)] * 3 + ([(-35, 35)] * 3 if finger == "Thumb" else [(-15, 15)])
            best = None
            for seed in [np.zeros(len(limits)), np.array([20, -20, 0] + ([0, 0, 0] if finger == "Thumb" else [0]))]:
                result = minimize(cost, seed, method="Powell", bounds=limits, options={"maxiter": 25, "xtol": .15, "ftol": .0001})
                if best is None or result.fun < best.fun:
                    best = result
            set_angles(best.x)
            d = sdf(skin(pose, selected))
            if refinement == 2 and (d.min() < -.0005 or sdf(skin(pose, tip)).min() > .0025):
                broad = differential_evolution(cost, limits, maxiter=60, popsize=8, seed=42, polish=False, tol=.001)
                refined = minimize(cost, broad.x, method="Powell", bounds=limits, options={"maxiter": 30, "xtol": .05})
                if refined.fun < best.fun:
                    best = refined
                set_angles(best.x)
                d = sdf(skin(pose, selected))
            contact_results[finger] = {"penetration_mm": round(float(max(0, -d.min())) * 1000, 2), "gap_mm": round(float(max(0, sdf(skin(pose, tip)).min())) * 1000, 2)}
        if refinement < 2:
            use_all = True
            wrist = minimize(wrist_cost, wrist, method="Powell", bounds=[(-.035, .035)] * 3,
                             options={"maxiter": 25, "xtol": .00002}).x
            wrist_cost(wrist)
    joints = {names[b].removeprefix("mixamorig_" + side + "Hand"): Rotation.from_matrix(local[b, :3, :3]).as_quat().tolist() for b in descendants if b != hand}
    return {"shift": wrist.tolist(), "joints": joints, "metrics": measure()}


def main():
    output = ROOT / "data/hand_contacts.json"
    results = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    cases = [c for c in DATA["cases"] if not os.environ.get("HAND_FIT_ONLY") or os.environ["HAND_FIT_ONLY"] in c["key"]]
    right_cases = {}
    for case in cases:
        base = case["key"].split("_", 2)[:2]
        right_cases.setdefault("_".join(base), case)
    right_results = {}
    left_results = {}
    refine = os.environ.get("HAND_FIT_REFINE") == "1"
    audit = os.environ.get("HAND_FIT_AUDIT") == "1"
    def previous(c, side):
        return results.get(c["key"], {}).get(side) if refine or audit else None
    def needs_work(c, side):
        old = previous(c, side)
        return audit or old is None or any(m["penetration_mm"] > .5 or m["gap_mm"] > 2 for m in old["metrics"].values())
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs = {}
        for c in cases:
            if needs_work(c, "Left"):
                jobs[pool.submit(fit, c, "Left", previous(c, "Left"), audit)] = (c["key"], "Left")
            else:
                left_results[c["key"]] = previous(c, "Left")
        for key, c in right_cases.items():
            if needs_work(c, "Right"):
                jobs[pool.submit(fit, c, "Right", previous(c, "Right"), audit)] = (key, "Right")
            else:
                right_results[key] = previous(c, "Right")
        for future in as_completed(jobs):
            key, side = jobs[future]
            fitted = future.result()
            (right_results if side == "Right" else left_results)[key] = fitted
            print(key, side, fitted["metrics"], flush=True)
            (ROOT / "tools/hand_fit/checkpoint.json").write_text(json.dumps({"right": right_results, "left": left_results}), encoding="utf-8")
    for case in cases:
        base = "_".join(case["key"].split("_", 2)[:2])
        results[case["key"]] = {"Right": right_results[base], "Left": left_results[case["key"]]}
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
