"""Use the skill audit with stable tessellation for a small metre-scale object.

Blender's tessellate_polygon drops valid small faces at metre coordinates. Only its
triangulation input is translated to a local origin and scaled to mm. Returned indices
still address the original world coordinates; all audit criteria and area thresholds stay
unchanged. This does not modify the blend or the shared skill.
"""
import pathlib
import runpy
from mathutils.geometry import tessellate_polygon as native_tessellate

def stable_tessellate(polygons):
    # Blender 5.2 returns index triples (verified by inspect_dozor.py).
    origin=polygons[0][0]
    local=[[(point-origin)*1000 for point in polygon] for polygon in polygons]
    return native_tessellate(local)

source=pathlib.Path('C:/Users/Schecter_8ght/.agents/skills/blender-asset-workflow/scripts/audit_blend.py')
code=source.read_text(encoding='utf-8').replace(
    'from mathutils.geometry import tessellate_polygon',
    'from mathutils.geometry import tessellate_polygon\ntessellate_polygon = stable_tessellate')
exec(compile(code,str(source),'exec'),{'__name__':'__main__','__file__':str(source),'stable_tessellate':stable_tessellate})
