"""Опись исходных Blender-кандидатов перед созданием игровых LOD.

    blender --background --factory-startup --python-exit-code 1 --python tools/prospekt_grass/inspect_assets.py
"""
from __future__ import annotations

import json
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "_asset_src" / "prospekt_grass"
ASSETS = ("grass_bermuda_01", "weed_plant_02", "grass_medium_01")


def main() -> None:
    report: dict = {}
    for asset in ASSETS:
        path = SRC / asset / f"{asset}_8k.blend"
        bpy.ops.wm.open_mainfile(filepath=str(path))
        depsgraph = bpy.context.evaluated_depsgraph_get()
        entry: dict = {"file": str(path), "objects": [], "node_groups": [], "images": []}
        for ob in bpy.context.scene.objects:
            row: dict = {"name": ob.name, "type": ob.type, "hide_render": ob.hide_render,
                "hide_viewport": ob.hide_viewport, "location": list(ob.location), "scale": list(ob.scale),
                "dimensions": list(ob.dimensions), "modifiers": []}
            for modifier in ob.modifiers:
                row["modifiers"].append({"name": modifier.name, "type": modifier.type,
                    "node_group": modifier.node_group.name if modifier.type == "NODES" and modifier.node_group else ""})
            if ob.type == "MESH":
                row["base_vertices"] = len(ob.data.vertices)
                row["base_polygons"] = len(ob.data.polygons)
                evaluated = ob.evaluated_get(depsgraph)
                mesh = evaluated.to_mesh()
                if mesh is not None:
                    mesh.calc_loop_triangles()
                    row["eval_vertices"] = len(mesh.vertices)
                    row["eval_triangles"] = len(mesh.loop_triangles)
                    row["materials"] = [material.name if material else "" for material in mesh.materials]
                    evaluated.to_mesh_clear()
            entry["objects"].append(row)
        for group in bpy.data.node_groups:
            entry["node_groups"].append({"name": group.name, "type": group.bl_idname,
                "nodes": [{"name": node.name, "type": node.bl_idname} for node in group.nodes]})
        for image in bpy.data.images:
            if image.source == "FILE":
                entry["images"].append({"name": image.name, "path": image.filepath, "size": list(image.size),
                    "colorspace": image.colorspace_settings.name})
        report[asset] = entry
        print(f"ОПИСЬ {asset}: объектов {len(entry['objects'])}, групп узлов {len(entry['node_groups'])}", flush=True)
    out = SRC / "source_inspection.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out, flush=True)


if __name__ == "__main__":
    main()
