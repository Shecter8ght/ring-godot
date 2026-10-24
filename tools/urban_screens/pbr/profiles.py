"""Отделка каждой модели и её функциональных деталей по матрице и фото."""
import re

# Порядок: металл, окрашенный корпус, пластик, камень, дерево, ткань, отражатель.
DEFAULT = ('galvanized', 'paint_grey', 'polymer_black', 'stone_dark', 'wood_aged', 'canvas_olive', 'reflector_white')
PROFILES = {
 'jersey': ('steel_dark', 'paint_grey', None, None, None, None, None),
 'crowd': DEFAULT,
 'crate': ('steel_dark', None, None, None, 'wood_aged', None, None),
 'cone': (None, None, 'polymer_orange', None, None, None, 'reflector_white'),
 'mesh_barrier': ('paint_red', 'paint_red', None, None, None, None, None),
 'canopy': DEFAULT,
 'planter': (None, None, None, 'stone_dark', None, None, None),
 'bench_tube': ('paint_black', None, None, None, 'wood_aged', None, None),
 'bollard': ('steel_dark', 'paint_black', None, None, None, None, 'brass'),
 'bin_faceted': ('stainless', 'paint_black', None, None, None, None, None),
 'lightbox': ('aluminium', None, None, None, None, None, None),
 'sandbags': (None, None, None, None, None, 'canvas_olive', None),
 'parking_sign': ('galvanized', 'enamel_blue', None, None, None, None, None),
 'handrail_slope': ('stainless', None, None, None, None, None, None),
 'street_cabinet': ('galvanized', 'paint_grey', None, None, None, None, None),
 'turnstile': ('stainless', None, None, None, None, None, None),
 'reception_stone': ('aluminium', None, None, 'marble_warm', 'laminate_dark', None, None),
 'sofa': ('paint_black', None, None, None, None, 'woven_olive', None),
 'coffee_table': ('stainless', None, None, 'stone_polished', None, None, None),
 'wall_niche': ('brass', 'paint_black', None, None, None, None, None),
 'guard_booth': ('paint_grey', 'paint_grey', None, None, None, None, None),
 'coffee_kiosk': ('paint_black', 'paint_black', None, None, 'timber_warm', None, None),
 'warning_a': ('galvanized', None, None, None, 'plywood', None, 'reflector_yellow'),
 'basket_bin': ('paint_black', 'paint_black', None, None, None, None, None),
 'tactile': (None, None, None, 'mineral_yellow', None, None, None),
 'speed_bump': (None, None, None, None, None, None, 'reflector_yellow'),
 'crossing_sign': ('galvanized', 'enamel_blue', None, None, None, None, None),
 'guardrail': ('galvanized', None, None, None, None, None, None),
 'curb_corner': (None, None, None, None, None, None, None),
 'drain': ('cast_iron', None, None, None, None, None, None),
 'ticket_machine': ('steel_dark', 'paint_black', 'polymer_black', None, None, None, None),
 'barrier_arm': ('galvanized', 'paint_white', None, None, None, None, 'reflector_red'),
 'guide_board': ('galvanized', 'paint_white', None, None, None, None, 'reflector_red'),
 'tire_delineator': ('steel_dark', None, 'polymer_white', None, None, None, 'reflector_red'),
 'lane_island': (None, None, None, None, None, None, 'reflector_yellow'),
 'revolving_door': ('stainless', None, None, None, None, None, None),
 'glass_doors': ('aluminium', None, None, None, None, None, None),
 'canopy_bracket': DEFAULT,
 'curtainwall': ('aluminium', None, None, None, None, None, None),
 'glass_railing': ('stainless', None, None, None, None, None, None),
 'hedgehog': ('rusted_steel', None, None, None, None, None, None),
 'concrete_cube': ('rusted_steel', None, None, None, None, None, None),
 'logo_pylon': ('aluminium', None, None, 'stone_dark', None, None, None),
 'plaza_seat': ('stainless', None, None, 'granite_light', None, None, None),
 'damaged_slab': ('rusted_steel', None, None, None, None, None, None),
 'tram_track': ('rail_steel', None, None, None, None, None, None),
 'twin_light': ('paint_silver', 'paint_silver', None, None, None, None, None),
 'wayfinding': ('paint_black', 'paint_black', None, None, None, None, None),
 'bench_stone': ('paint_black', None, None, None, 'timber_warm', None, None),
 'billboard': ('paint_grey', 'paint_grey', None, None, None, None, None),
 'sound_fence': ('paint_skyblue', 'paint_skyblue', None, None, None, None, None),
 'site_fence': ('paint_green', 'paint_green', None, None, None, None, None),
 'dump_bed': ('rusted_steel', 'paint_ochre', None, None, None, None, None),
 'privacy_screen': ('paint_black', None, None, None, None, 'tarp_green', None),
 'water_barrier': (None, None, 'polymer_orange', None, None, None, None),
 'wave_facade': ('aluminium', 'paint_silver', None, None, None, None, None),
 'checkpoint_cabinet': ('steel_dark', 'paint_olive', None, None, None, None, None),
 'single_light': ('aluminium', None, None, None, None, None, None),
 'lit_parapet': ('stainless', None, None, 'stone_dark', None, None, None),
 'triangle_panel': ('paint_silver', 'paint_silver', None, None, None, None, None),
 'medical_tent': ('aluminium', None, None, None, None, 'tarp_olive', 'reflector_cyan'),
 'medical_screen': ('stainless', None, None, None, None, 'canvas_cyan', None),
 'wheelchair': ('chrome', None, None, None, None, 'vinyl_black', None),
 'stretcher': ('aluminium', None, None, None, None, 'canvas_olive', None),
 'medical_cart': ('stainless', None, None, None, None, None, None),
 'hatchback': ('aluminium', 'car_blue', 'polymer_black', None, None, 'cloth_dark', None),
 'plywood_case': ('galvanized', None, None, None, 'plywood', None, None),
 'space_canopy': ('aluminium', None, None, None, None, None, None),
 'entry_steps': ('stainless', None, None, 'stone_dark', None, None, None),
 'lattice_barrier': ('paint_black', 'paint_yellow', None, None, None, None, None),
 'checkpoint_cage': ('paint_black', 'paint_black', None, None, None, None, None),
 'traffic_light': ('paint_black', 'paint_black', None, None, None, None, None),
 'generator': ('steel_dark', 'paint_blue', None, None, None, None, None),
 'detour_board': ('galvanized', 'paint_white', None, None, None, None, 'reflector_red'),
 'power_cable': ('brass', None, None, None, None, None, None),
 'atm': ('stainless', 'paint_teal', 'polymer_black', None, None, None, None),
 'bank_kiosk': ('aluminium', 'paint_teal', 'polymer_grey', None, None, None, None),
 'armchair': ('paint_black', None, None, None, None, 'woven_teal', None),
 'breached_wall': ('rusted_steel', None, None, None, None, None, None),
 'teller_desk': ('stainless', 'paint_teal', None, None, 'laminate_dark', None, None),
 'reception_lit': ('bronze', None, None, 'stone_polished', 'laminate_dark', None, None),
 'ring_chandelier': ('bronze', None, None, None, None, None, None),
 'monitor': ('aluminium', None, 'polymer_black', None, None, None, None),
 'credenza': ('aluminium', None, None, None, 'laminate_white', None, None),
 'water_bottle': (None, None, 'polymer_white', None, None, None, None),
 'tank': ('steel_dark', 'paint_ochre', None, None, None, None, None),
 'loading_shutter': ('galvanized', None, None, None, None, None, None),
 'industrial_light': ('paint_grey', 'paint_grey', None, None, None, None, None),
 'service_cage': ('galvanized', None, None, None, None, None, None),
 'concrete_portal': (None, None, None, None, None, None, None),
 'escalator': ('stainless', None, None, None, None, None, None),
 'terrace_stairs': ('stainless', None, None, 'granite_light', None, None, None),
 'relief_wall': (None, None, None, 'marble_warm', None, None, None),
 'square_light': ('aluminium_dark', None, None, None, None, None, None),
 'belt_post': ('stainless', None, None, None, None, 'cloth_dark', None),
 'fence': ('rusted_steel', None, None, None, None, None, None),
 'dumpster': ('paint_green', 'paint_green', None, None, None, None, None),
 'car': ('aluminium', 'car_blue', 'polymer_black', None, None, 'cloth_dark', None),
 'kiosk': ('aluminium', 'paint_cream', None, None, 'timber_warm', 'awning_cream', None),
}

SUSPENDED = {'wall_niche', 'canopy_bracket', 'curtainwall', 'wave_facade', 'triangle_panel',
 'ring_chandelier', 'industrial_light', 'square_light', 'relief_wall'}
INDOOR = {'turnstile', 'reception_stone', 'sofa', 'coffee_table', 'wall_niche', 'revolving_door',
 'glass_doors', 'medical_screen', 'wheelchair', 'stretcher', 'medical_cart', 'atm', 'bank_kiosk',
 'armchair', 'teller_desk', 'reception_lit', 'ring_chandelier', 'monitor', 'credenza', 'water_bottle',
 'escalator', 'terrace_stairs', 'relief_wall', 'square_light', 'belt_post'}


def number(name):
    m = re.search(r'\.(\d+)$', name)
    return int(m[1]) if m else 0


def surface(a, ob):
    key, aid = a['key'], a['id']
    name = ob.name.lower()
    role = ob.get('finish_role', '')
    config = PROFILES[key]
    values = [v or DEFAULT[i] for i, v in enumerate(config)]
    mapped = dict(zip(('metal', 'paint', 'plastic', 'stone', 'wood', 'fabric', 'reflector'), values))
    mapped.update(concrete='concrete_cast', interior='interior_dark', glass='glass_clear',
        diffuser='lamp_opal', screen='screen_off', chrome='chrome', rubber='rubber',
        enamel=mapped['paint'], soil='soil')
    if ob.type == 'FONT':
        return 'ink_black' if key in ('crate','reception_lit') else 'ink_ivory'
    if role not in mapped:
        raise ValueError((aid, ob.name, role))
    result = mapped[role]
    if key=='lightbox' and role=='diffuser':
        return 'print_poster'
    if key=='billboard' and role=='reflector':
        return 'print_billboard'
    if key=='warning_a' and role=='reflector':
        return 'print_warning'
    # Specific photo-based rebuilt items take precedence over generic old slots.
    if aid == 'R03':
        if role in ('paint', 'plastic'):
            result = 'paint_graphite' if role == 'paint' else 'polymer_graphite'
        if role == 'screen':
            result = 'screen_atm'
        if 'steel_cross_plate' in name:
            return 'paint_graphite'
        if 'card_reader_nose' in name or 'card_entry_indicator' in name:
            return 'optic_green'
    if aid == 'R02':
        if 'weld' in name:
            return 'rust_weld'
        if 'floor' in name or 'runner' in name:
            return 'skip_floor'
        if 'pin' in name and 'gusset' not in name:
            return 'steel_dark'
    if aid == 'R05':
        if role == 'fabric':
            return 'awning_burgundy' if number(ob.name) % 2 == 0 else 'awning_cream'
        if any(t in name for t in ('fascia', 'food_sign')):
            return 'paint_burgundy'
        if any(t in name for t in ('counter', 'worktop', 'refrigerator', 'food_display_tray')) and role == 'metal':
            return 'stainless'
        if 'roof' in name and 'duct' not in name and 'vent' not in name:
            return 'roof_bitumen'
        if 'folded_corner_cladding' in name or 'welded_corner' in name:
            return 'paint_cream'
    if key in ('car', 'hatchback'):
        if any(t in name for t in ('rear_outer_lamp_cover', 'rear_reflector', 'rear_lamp_round_optic')):
            return 'optic_red'
        if 'indicator' in name:
            return 'optic_amber'
        if 'headlamp' in name or 'fog_lamp_lens' in name:
            return 'chrome' if role == 'chrome' else 'glass_clear' if role == 'glass' else result
        if any(t in name for t in ('tyre', 'tread', 'tire')):
            return 'tyre_rubber'
        if 'seat' in name and role == 'interior' or 'headrest' in name and role == 'interior':
            return 'vinyl_black'
        if 'registration_plate' in name or 'number_plate' in name and 'back' not in name:
            return 'paint_white'
        if role == 'glass':
            return 'glass_smoke'
        if 'brake_' in name:
            return 'steel_dark' if 'caliper' in name else 'rail_steel'
    if key == 'crossing_sign':
        if 'protective_border' in name:
            return 'reflector_lime'
        if role == 'enamel':
            return 'enamel_blue'
    if key == 'guide_board':
        if 'round_direction' in name:
            return 'enamel_blue'
        if 'arrow_symbol' in name:
            return 'reflector_white'
        if 'rectangular_direction' in name:
            return 'paint_white'
    if key in ('lattice_barrier', 'lane_island') and role in ('paint', 'reflector'):
        return result if number(ob.name) % 2 == 0 else 'paint_black'
    if key == 'traffic_light' and role == 'glass':
        return ('optic_red', 'optic_amber', 'optic_green')[number(ob.name) % 3]
    if key == 'water_bottle' and role == 'glass':
        return 'pet_blue'
    if key == 'curtainwall' and role == 'glass':
        return 'glass_green'
    if key in ('turnstile', 'revolving_door') and role == 'glass':
        return 'glass_smoke'
    if key == 'medical_tent' and role == 'reflector':
        return 'reflector_cyan'
    if key in ('ticket_machine', 'bank_kiosk', 'atm', 'monitor') and role == 'screen':
        return 'screen_ticket' if key == 'ticket_machine' else 'screen_atm' if key == 'atm' else 'screen_monitor'
    if any(t in name for t in ('roof_felt', 'bitumen', 'roof_deck')):
        return 'roof_bitumen'
    if 'coping' in name and key in ('plaza_seat', 'planter'):
        return 'stone_polished'
    if 'fractur' in name or 'broken_concrete' in name:
        return 'concrete_fracture' if role == 'concrete' else result
    if 'rebar' in name:
        return 'rusted_steel'
    if 'rubber' in name or 'caster' in name and role == 'plastic':
        return 'rubber'
    if role in ('metal', 'chrome') and any(t in name for t in ('bolt', 'screw', 'fastener', 'rivet', 'lock', 'latch', 'hinge')):
        return 'galvanized' if result not in ('stainless', 'chrome', 'brass', 'bronze') else result
    return result
