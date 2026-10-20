"""Inspect the installed character generator without touching an existing scene."""
import importlib
import json
from pathlib import Path

import addon_utils
import bpy

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "_asset_src" / "npc_m02"
OUT.mkdir(parents=True, exist_ok=True)
MODULE = "bl_ext.blender_org.mpfb"
if MODULE not in bpy.context.preferences.addons:
    bpy.context.preferences.addons.new().module = MODULE
addon_utils.enable(MODULE, default_set=False, persistent=False)
mpfb = importlib.import_module(MODULE)
HumanService = importlib.import_module(MODULE + ".services.humanservice").HumanService
LocationService = importlib.import_module(MODULE + ".services.locationservice").LocationService

data = Path(LocationService.get_mpfb_data())
roots = {
    "user_data": LocationService.get_user_data(),
    "second_root": LocationService.get_second_root(),
    "mh_user_data": LocationService.get_mh_user_data(),
    "addon_data": str(data),
}
assets = []
for name, folder in roots.items():
    if not folder or not Path(folder).is_dir():
        continue
    for path in Path(folder).rglob("*.mhclo"):
        assets.append({"root": name, "file": str(path)})
result = {
    "blender": bpy.app.version_string,
    "mpfb": list(mpfb.VERSION),
    "roots": roots,
    "rigs": [p.name for p in (data / "rigs" / "standard").glob("rig.*.json")],
    "assets": assets,
    "targets": {
        folder: [p.name for p in (data / "targets" / folder).glob("*.target.gz")]
        for folder in ["head", "chin", "jaw", "nose", "mouth", "eyes", "cheek", "ears", "neck", "arms", "torso"]
    },
}
(OUT / "environment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print("NPC_M02_PROBE " + json.dumps({"blender": result["blender"], "mpfb": result["mpfb"], "roots": roots, "asset_count": len(assets), "rigs": result["rigs"]}))
