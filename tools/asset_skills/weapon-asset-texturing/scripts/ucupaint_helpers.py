"""Narrow native UCUPaint 2.4.9 helpers, for import inside Blender.

No file writes, material replacement, automatic graph migration or preference save.
"""
import importlib
import math


def load_ucupaint(module='bl_ext.blender_org.ucupaint', enable=False):
    if enable:
        import bpy
        import addon_utils
        bpy.context.preferences.use_preferences_save = False
        addon_utils.enable(module, default_set=True)
    ucup = importlib.import_module(module)
    version = ucup.common.get_current_version_str()
    if str(version) != '2.4.9':
        raise RuntimeError(f'Helpers validated for UCUPaint 2.4.9; found {version}. Inspect installed API first.')
    return ucup


def _numbers(value):
    if isinstance(value, (int, float)):
        return [float(value)]
    return [float(v) for v in value]


def sync_property(ucup, entity, prop, value, tolerance=1e-6):
    """Set RNA plus native input and check actual socket; RGB permits returned alpha."""
    requested = _numbers(value)
    if not all(math.isfinite(v) for v in requested):
        raise ValueError('Property must be finite')
    if prop == 'override_color':
        from mathutils import Color
        if len(requested) != 3:
            raise ValueError('override_color requires three linear RGB values')
        value = Color(requested)
    setattr(entity, prop, value)
    ucup.common.set_entity_prop_value(entity, prop, getattr(entity, prop))
    actual = ucup.common.get_entity_prop_value(entity, prop)
    read = _numbers(actual)
    if prop == 'override_color':
        read = read[:3]
    if len(read) != len(requested) or any(
        not math.isfinite(a) or abs(a-b) > tolerance for a, b in zip(read, requested)
    ):
        raise RuntimeError(f'Native input mismatch for {prop}: requested={requested}, actual={read}')
    return actual


def local_noise_ramp(ucup, noise_mask, lo, hi):
    """Threshold only this NOISE mask. Reuse an existing local RAMP if unique."""
    if noise_mask.type != 'NOISE':
        raise ValueError('Expected a native NOISE mask, not accumulated MODIFIER')
    if not (0 <= lo < hi <= 1):
        raise ValueError('Require 0 <= lo < hi <= 1')
    modifiers = [m for m in noise_mask.modifiers if m.type == 'RAMP']
    if len(modifiers) > 1:
        raise ValueError('Multiple local RAMP modifiers: inspect the intended chain')
    if not modifiers:
        mm = importlib.import_module(ucup.__name__ + '.MaskModifier')
        mm.add_new_mask_modifier(noise_mask, 'RAMP')
        modifiers = [noise_mask.modifiers[-1]]
    ramp = ucup.common.get_mask_tree(noise_mask).nodes[modifiers[0].ramp]
    elements = ramp.color_ramp.elements
    if len(elements) != 2:
        raise ValueError('Existing multistop ramp requires explicit review')
    elements[0].position, elements[1].position = lo, hi
    elements[0].color = (0, 0, 0, 1)
    elements[1].color = (1, 1, 1, 1)
    ramp.color_ramp.interpolation = 'LINEAR'
    return ramp


def reconnect(ucup, tree):
    if not tree.yp.is_ypaint_node:
        raise ValueError('Expected a native UCUPaint node tree')
    ucup.input_outputs.check_all_channel_ios(tree.yp, reconnect=True)
    ucup.input_outputs.check_start_end_root_ch_nodes(tree)
    for layer in tree.yp.layers:
        ucup.node_connections.reconnect_layer_nodes(layer)
    ucup.node_connections.reconnect_yp_nodes(tree)
