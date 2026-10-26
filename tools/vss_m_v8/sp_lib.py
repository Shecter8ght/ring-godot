# Помощники для заданий Substance 3D Painter (выполняются внутри Painter через мост sp_bridge).
# Слой = заливка с однотонными каналами или процедурными источниками, маска — генераторы/процедурные заливки.
import substance_painter.colormanagement as CM
import substance_painter.export as X
import substance_painter.layerstack as L
import substance_painter.project as P
import substance_painter.resource as R
import substance_painter.textureset as TS
from substance_painter.textureset import ChannelType as CH

CHAN = {"color": CH.BaseColor, "rough": CH.SpecularRoughness, "metal": CH.BaseMetalness, "height": CH.Height}
_RID = {}


def rid(name, usage):
    key = (name, usage)
    if key not in _RID:
        for r in R.search(usage):
            if r.identifier().name == name:
                _RID[key] = r.identifier()
                break
        else:
            raise RuntimeError("нет ресурса " + name)
    return _RID[key]


def stack(i=0):
    return TS.all_texture_sets()[i].get_stack()


def stack_by_name(name):
    for t in TS.all_texture_sets():
        if t.name() == name:
            return t.get_stack()
    raise RuntimeError("нет набора текстур " + name)


def clear(st):
    for n in L.get_root_layer_nodes(st):
        L.delete_node(n)


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _val(v, data=False):
    """Цвет задаётся в sRGB и передаётся в рабочее (линейное) пространство проекта; данные — как есть (Raw)."""
    if data:
        vv = v if isinstance(v, (tuple, list)) else (v, v, v)
        return CM.Color(*vv, color_space=CM.GenericColorSpace.Raw)
    vv = v if isinstance(v, (tuple, list)) else (v, v, v)
    return CM.Color(*[_lin(c) for c in vv], color_space=CM.GenericColorSpace.Working)


def triplanar(layer, scale, rot=0.0, hardness=0.6):
    layer.set_projection_mode(L.ProjectionMode.Triplanar)
    p = layer.get_projection_parameters()
    p.hardness = hardness
    p.uv_transformation.scale_mode = L.ScaleMode.Factors
    p.uv_transformation.scale = [scale, scale]
    p.uv_transformation.rotation = rot
    layer.set_projection_parameters(p)


def uvscale(layer, scale, rot=0.0):
    layer.set_projection_mode(L.ProjectionMode.UV)
    p = layer.get_projection_parameters()
    p.uv_transformation.scale_mode = L.ScaleMode.Factors
    p.uv_transformation.scale = [scale, scale]
    p.uv_transformation.rotation = rot
    layer.set_projection_parameters(p)


def fill(name, pos, **ch):
    """Заливка: ch = color=(r,g,b)|v, rough=v, metal=v, height=v; значение-строка — процедурный ресурс."""
    f = L.insert_fill(pos)
    f.set_name(name)
    f.active_channels = {CHAN[k] for k in ch}
    for k, v in ch.items():
        if isinstance(v, str):
            f.set_source(CHAN[k], rid(v, "u:procedural"))
        else:
            f.set_source(CHAN[k], _val(v, data=(k != "color")))
    if "height" in ch and not isinstance(ch["height"], str):
        # высота числом — уровень поверхности, а не прибавка: по умолчанию канал высоты складывается (Linear Dodge),
        # и слой «0.499» по маске поднимал поверхность почти на полединицы — рельеф «корой»
        f.set_blending_mode(L.BlendingMode.Normal, CH.Height)
    return f


def lop(layer, value, chans=None):
    """Непрозрачность слоя по всем его каналам (или по указанным)."""
    for ch in (chans or layer.active_channels):
        layer.set_opacity(value, ch)


def proc_params(layer, channel_key, params):
    src = layer.get_source(CHAN[channel_key]) if channel_key else layer.get_source(None)
    if params:
        src.set_parameters(params)
    return src


def mask_black(layer):
    if not layer.has_mask():
        layer.add_mask(L.MaskBackground.Black)


def mask_generator(layer, gen, params=None, above=None):
    mask_black(layer)
    pos = L.InsertPosition.above_node(above) if above else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    g = L.insert_generator_effect(pos, rid(gen, "u:generator"))
    if params:
        g.get_source().set_parameters(params)
    return g


def mask_proc(layer, proc, params=None, scale=1.0, tri=True, rot=0.0, blend=None, opacity=1.0, above=None):
    """Процедурная заливка в маске (ч/б); blend — смешение с тем, что ниже в маске (Multiply и т. п.)."""
    mask_black(layer)
    pos = L.InsertPosition.above_node(above) if above else L.InsertPosition.inside_node(layer, L.NodeStack.Mask)
    f = L.insert_fill(pos)
    src = f.set_source(None, rid(proc, "u:procedural"))
    if params:
        src.set_parameters(params)
    if tri:
        triplanar(f, scale, rot)
    else:
        uvscale(f, scale, rot)
    if blend is not None:
        f.set_blending_mode(blend)
    f.set_opacity(opacity)
    return f


def mask_levels(layer, above):
    return L.insert_levels_effect(L.InsertPosition.above_node(above))


def only_meshes(layer, names):
    layer.set_geometry_mask_type(L.GeometryMaskType.Mesh)
    layer.set_geometry_mask_enabled_meshes(names)


def when_idle(fn, marker="_stack_done.txt"):
    """Сохранение и выгрузка — когда Painter досчитает стек: сразу после сборки слоёв save_as давал «Painter is busy»,
    а следующее задание поверх занятого Painter роняло его (2026-10-26). Итог — в файл-метку в папке заданий."""
    import os
    import traceback
    path = os.path.join(os.environ.get("SP_BRIDGE_DIR", ""), marker)

    def run():
        try:
            text = "OK " + str(fn())
        except Exception:
            text = "ERROR " + traceback.format_exc()
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    P.execute_when_not_busy(run)


def export(out_dir, texset):
    pr = [p for p in X.list_predefined_export_presets() if p.name == "glTF PBR Metal Roughness"][0]
    cfg = {"exportShaderParams": False, "exportPath": out_dir, "defaultExportPreset": pr.url,
           "exportList": [{"rootPath": texset}],
           "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8", "paddingAlgorithm": "infinite"}}]}
    r = X.export_project_textures(cfg)
    return r.status, {k: v for k, v in r.textures.items()}
