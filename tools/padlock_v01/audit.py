"""Запуск общего аудитора с устойчивой триангуляцией малых граней Blender 5.2."""
import importlib.util
import json
import sys
from pathlib import Path

import bpy


def main():
    source=Path.home()/".codex"/"skills"/"blender-asset-workflow"/"scripts"/"audit_blend.py"
    spec=importlib.util.spec_from_file_location("padlock_skill_audit",source)
    audit=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=audit
    spec.loader.exec_module(audit)
    native_tessellate=audit.tessellate_polygon
    mm_per_unit=1000*bpy.context.scene.unit_settings.scale_length

    def stable_tessellate(polylines):
        # Проверяем те же точки и тот же порог площади. Нормализация нужна только
        # вычислению: в 5.2 малые метрические quads могут давать [(0,0,0)].
        origin=polylines[0][0].copy()
        local=[[(point-origin)*mm_per_unit for point in line] for line in polylines]
        result=native_tessellate(local)
        if result and not isinstance(result[0][0],int):
            return [tuple(point/mm_per_unit+origin for point in triangle) for triangle in result]
        return result

    audit.tessellate_polygon=stable_tessellate
    audit.main()
    report_path=Path(sys.argv[sys.argv.index("--output")+1])
    report=json.loads(report_path.read_text(encoding="utf-8"))
    references=[]
    for image in bpy.data.images:
        if image.name.startswith("reference_"):
            external=Path(bpy.path.abspath(image.filepath))
            references.append({"name":image.name,"packed":image.packed_file is not None,
                               "relative_path":image.filepath,"external_exists":external.is_file()})
    report["reference_images"]=references
    if len(references)!=6 or any(not item["packed"] or not item["external_exists"] or not item["relative_path"].startswith("//") for item in references):
        raise RuntimeError("Packed/relative reference copies are incomplete")
    report["tessellation_adapter"]={
        "reason":"Blender 5.2 tessellate_polygon returns (0,0,0) for some valid small polygons in metre coordinates.",
        "method":"Same world points, translated to polygon origin and scaled to millimetres for tessellation; unchanged physical area threshold and all other criteria.",
        "source":str(source),
        "geometry_changed":False,
    }
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PADLOCK_VERIFIED",report["status"],report["acceptance_check_count"],"packed_references",len(references),flush=True)
    if report["status"]!="PASS" or report["errors"]:
        raise RuntimeError("Read the failed criteria in "+str(report_path))


if __name__=="__main__":
    main()
