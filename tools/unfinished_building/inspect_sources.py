import bpy
import json
import sys
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "_asset_src" / "unfinished_building" / "high"
OUT = ROOT / "_asset_src" / "unfinished_building" / "inventory.json"

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
records = []
for path in sorted(SOURCE.glob("*/*.fbx")):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    imported = [obj for obj in bpy.data.objects if obj not in before]
    meshes = [obj for obj in imported if obj.type == "MESH"]
    points = [obj.matrix_world @ Vector(corner) for obj in meshes for corner in obj.bound_box]
    low = [min(p[i] for p in points) for i in range(3)] if points else [0.0, 0.0, 0.0]
    high = [max(p[i] for p in points) for i in range(3)] if points else [0.0, 0.0, 0.0]
    records.append({
        "id": path.stem,
        "objects": [obj.name for obj in imported],
        "mesh_objects": [obj.name for obj in meshes],
        "materials": sorted({mat.name for obj in meshes for mat in obj.data.materials if mat}),
        "dimensions": [high[i] - low[i] for i in range(3)],
        "bounds": [low, high],
        "vertices": sum(len(obj.data.vertices) for obj in meshes),
        "polygons": sum(len(obj.data.polygons) for obj in meshes),
    })
    for obj in imported:
        bpy.data.objects.remove(obj, do_unlink=True)
OUT.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
for record in records:
    dims = " × ".join(f"{value:.3f}" for value in record["dimensions"])
    print(f"{record['id']}: {dims} m | {record['polygons']} polys | {', '.join(record['objects'])} | {', '.join(record['materials'])}")
print(f"INVENTORY {OUT}")
