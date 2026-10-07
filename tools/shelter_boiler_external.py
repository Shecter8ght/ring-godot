"""CC0 модели Poly Haven для котельной и замены самодельных предметов убежища: сырьё и лицензии.

Только скачивание в _asset_src/shelter/external/<id>/ и запись external_boiler_sources.json;
интеграция (масштаб, поворот, разворот на +Z, GLB) — integrate_shelter_boiler_external.py в Blender.
python tools/shelter_boiler_external.py
"""
from __future__ import annotations
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UA = {'User-Agent': 'RING-asset-tool/1.0 (github.com/Shecter8ght/ring-godot)'}
DATE = '2026-10-07'
# ассет проекта → (id Poly Haven, разрешение текстур)
MODELS = {
    'PH_Chair': ('painted_wooden_chair_02', '1k'), 'PH_Boots': ('rubber_boots', '1k'),
    'PH_Cans': ('russian_food_cans_01', '1k'), 'PH_JerryCan': ('metal_jerrycan_green', '1k'),
    'PH_MedicalBox': ('medical_box', '1k'), 'PH_Radio': ('vintage_radio_transceiver', '1k'),
    'PH_DeskLamp': ('desk_lamp_arm_01', '1k'), 'PH_MilitaryCrate': ('wooden_military_crate', '1k'),
    'PH_Carton': ('cardboard_box_01', '1k'), 'PH_Bench': ('painted_wooden_bench', '1k'),
    'PH_CoffeeTable': ('industrial_coffee_table', '1k'), 'PH_Binoculars': ('binoculars', '1k'),
    'PH_GasMask': ('old_gas_mask', '1k'), 'PH_Gloves': ('garden_gloves_01', '1k'),
    'PH_Kettle': ('vintage_electric_kettle', '1k'), 'PH_Clipboard': ('clipboard', '1k'),
    'PH_Toolbox': ('metal_toolbox', '1k'), 'PH_ToolChest': ('metal_tool_chest', '1k'),
    'PH_ToolCart': ('tool_cart', '1k'), 'PH_Vice': ('bench_vice_01', '1k'),
    'PH_DrillPress': ('drill_press_01', '1k'), 'PH_Compressor': ('old_military_compressor', '1k'),
    'PH_PropaneTank': ('propane_tank', '1k'), 'PH_PowerBox': ('power_box_01', '1k'),
    'PH_UtilityBox': ('utility_box_01', '1k'), 'PH_HangingLamp': ('hanging_industrial_lamp', '1k'),
    'PH_Thermos': ('modified_thermos', '1k'), 'PH_TrashCan': ('metal_trash_can', '1k'),
    'PH_FoldingStool': ('folding_wooden_stool', '1k'), 'PH_PlasticCrate': ('plastic_crate_01', '1k'),
    'PH_Multimeter': ('retro_multimeter', '1k'), 'PH_OilTin': ('oil_tin', '1k'),
    'PH_Crane': ('overhead_crane', '1k'), 'PH_MetalDesk': ('metal_office_desk', '1k'),
    'PH_WallClock': ('wall_clock', '1k'), 'PH_Stool': ('metal_stool_02', '1k'),
    'PH_LpgTank': ('small_lpg_tank', '1k'), 'PH_PipeWrench': ('pipe_wrench', '1k'),
    'PH_Sledgehammer': ('sledgehammer_01', '1k'),
    # терминал контрактов на столе связи в хабе
    'PH_Laptop': ('classic_laptop', '1k'),
}


def get(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90).read()


if __name__ == '__main__':
    catalog = json.loads(get('https://api.polyhaven.com/assets?t=models'))
    records = []
    for asset, (key, resolution) in MODELS.items():
        folder = ROOT/'_asset_src/shelter/external'/key
        folder.mkdir(parents=True, exist_ok=True)
        files = json.loads(get('https://api.polyhaven.com/files/' + key))
        spec = files['gltf'][resolution]['gltf']
        for path, info in {key + '.gltf': spec, **spec.get('include', {})}.items():
            target = folder/path
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(get(info['url']))
        record = {'id': key, 'asset': asset, 'name': catalog[key]['name'], 'author': ', '.join(catalog[key]['authors']),
                  'url': 'https://polyhaven.com/a/' + key, 'license': 'CC0 1.0',
                  'download_date': DATE, 'modified': True, 'resolution': resolution}
        records.append(record)
        (folder/'license.txt').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
        print('FETCHED', asset, key, flush=True)
    (ROOT/'_asset_src/shelter/external_boiler_sources.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
