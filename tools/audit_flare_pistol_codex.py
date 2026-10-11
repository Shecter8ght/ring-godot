"""Validate final GLBs, attributes and PBR wiring without opening Blender."""
import json
import struct
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/models/weapons/flare_pistol_codex"
COMP = {5126: "<f4", 5125: "<u4", 5123: "<u2", 5121: "u1"}
WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def inspect(path):
    raw = path.read_bytes()
    magic, version, size = struct.unpack_from("<III", raw)
    assert magic == 0x46546C67 and version == 2 and size == len(raw)
    n, tag = struct.unpack_from("<II", raw, 12)
    doc = json.loads(raw[20:20+n])
    binary = raw[28+n:]

    def accessor(i):
        a = doc["accessors"][i]
        v = doc["bufferViews"][a["bufferView"]]
        dtype = np.dtype(COMP[a["componentType"]])
        columns = WIDTH[a["type"]]
        offset = a.get("byteOffset", 0) + v.get("byteOffset", 0)
        stride = v.get("byteStride", dtype.itemsize * columns)
        return np.ndarray((a["count"], columns), dtype, binary, offset,
                          strides=(stride, dtype.itemsize)).copy()

    triangles = 0
    skin_weights = []
    for mesh in doc.get("meshes", []):
        for p in mesh["primitives"]:
            attrs = p["attributes"]
            pos = accessor(attrs["POSITION"])
            assert np.isfinite(pos).all(), mesh["name"]
            inds = accessor(p["indices"])
            assert inds.max() < len(pos) and len(inds) % 3 == 0
            triangles += len(inds) // 3
            uv = accessor(attrs["TEXCOORD_0"])
            assert np.isfinite(uv).all()
            normals = accessor(attrs["NORMAL"])
            assert np.max(np.abs(np.linalg.norm(normals, axis=1) - 1)) < .01
            material = doc["materials"][p["material"]]
            if material.get("name", "").startswith("Codex_"):
                assert "TANGENT" in attrs and "normalTexture" in material
                assert "baseColorTexture" in material["pbrMetallicRoughness"]
                assert "metallicRoughnessTexture" in material["pbrMetallicRoughness"]
                assert uv.min() >= -.001 and uv.max() <= 1.001
            if "WEIGHTS_0" in attrs:
                weights = accessor(attrs["WEIGHTS_0"])
                if "WEIGHTS_1" in attrs:
                    weights = np.concatenate((weights, accessor(attrs["WEIGHTS_1"])), axis=1)
                assert np.max(np.abs(weights.sum(axis=1) - 1)) < .001
                skin_weights.append(weights.shape[1])
    clips = [a["name"] for a in doc.get("animations", [])]
    if "viewmodel" in path.stem:
        assert set(clips) >= {"idle", "idle_empty", "draw", "reload_empty", "reload_live",
                              "fire", "break_open", "insert_cartridge", "close_breech",
                              "cock_hammer", "trigger_pull", "holster"}
        nodes = {n.get("name", "") for n in doc["nodes"]}
        assert {"FPS_Arms_Right", "FPS_Arms_Left", "LoadRoundRed", "LoadRoundGreen", "OldRoundRed", "OldRoundGreen"} <= nodes
    elif path.stem == "flare_pistol_codex":
        assert 11000 <= triangles <= 14000, triangles
        assert {"Frame", "Barrel", "Hammer", "Trigger", "Latch", "Muzzle"} <= {
            n.get("name", "") for n in doc["nodes"]}
    result = {"file": path.name, "triangles": triangles, "clips": clips,
              "images": len(doc.get("images", [])), "influences": skin_weights,
              "materials": [m.get("name", "") for m in doc.get("materials", [])], "pass": True}
    if "viewmodel" in path.stem:
        boxes = {}
        for node in doc["nodes"]:
            if "mesh" not in node or "skin" not in node:
                continue
            skin = doc["skins"][node["skin"]]
            inverses = accessor(skin["inverseBindMatrices"])
            for primitive in doc["meshes"][node["mesh"]]["primitives"]:
                if not doc["materials"][primitive["material"]].get("name", "").startswith("Codex_gun_"):
                    continue
                attrs = primitive["attributes"]
                points = accessor(attrs["POSITION"])
                joint_ids = accessor(attrs["JOINTS_0"])
                weights = accessor(attrs["WEIGHTS_0"])
                for j, index in enumerate(skin["joints"]):
                    name = doc["nodes"][index].get("name", "")
                    if name not in {"Frame", "Barrel", "Hammer", "Trigger", "Latch", "FiringPin"}:
                        continue
                    selected = np.any((joint_ids == j) & (weights > .99), axis=1)
                    if not selected.any():
                        continue
                    hom = np.column_stack((points[selected], np.ones(selected.sum())))
                    local = (inverses[j].reshape(4, 4).T @ hom.T).T[:, :3]
                    low, high = local.min(axis=0), local.max(axis=0)
                    if name in boxes:
                        low = np.minimum(low, boxes[name]["min"])
                        high = np.maximum(high, boxes[name]["max"])
                    boxes[name] = {"min": low.tolist(), "max": high.tolist()}
        assert set(boxes) == {"Frame", "Barrel", "Hammer", "Trigger", "Latch", "FiringPin"}, boxes
        result["clearance_parts"] = boxes
        (OUT / "clearance_boxes.json").write_text(json.dumps(boxes, indent=2)+"\n", encoding="utf-8")
    print(path.name, "PASS", triangles, "triangles", len(clips), "clips")
    return result


if __name__ == "__main__":
    reports = [inspect(p) for p in sorted(OUT.glob("*.glb"))]
    (OUT / "glb_audit.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
