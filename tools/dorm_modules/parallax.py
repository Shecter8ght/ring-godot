"""Глубина ям в плоском материале: выбитая планка паркета, выбитая плитка, штукатурка, отвалившаяся до кирпича.

Карта нормалей перепада высот не показывает: дно ямы смотрелось бы на уровне пола. Здесь луч от глаза идёт внутрь
ямы шагами до глубины слоя; если по пути он упирается в место, где материал есть, — мы видим боковую грань соседа
(дальнюю стенку ямы) на глубине t, иначе — дно ямы, сдвинутое вдаль по взгляду. Ближняя стенка сама собой не видна.
Расчёт — в мировых координатах от точки поверхности (Geometry: Position, Normal, Incoming), так же переносится
в шейдер Godot циклом.
"""


def vmath(g, op: str, a, b=None, scale=None):
    nd = g.node("ShaderNodeVectorMath", operation=op)
    for i, x in enumerate((a, b)):
        if x is None:
            continue
        if isinstance(x, tuple):
            nd.inputs[i].default_value = x
        else:
            g.link(x, nd.inputs[i])
    if scale is not None:
        if isinstance(scale, (int, float)):
            nd.inputs["Scale"].default_value = scale
        else:
            g.link(scale, nd.inputs["Scale"])
    return nd.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs["Vector"]


def march(g, depth_m: float, steps: int, hole_at):
    """hole_at(позиция) → (1 там, где на поверхности ямы, а не материала; словарь выборок).
    Возвращает: wall — луч упёрся в стенку (0…1), t_wall — глубина упора (доля от depth_m),
    pos_floor — точка дна, extra — выборки последнего шага (на дне), n_wall — нормаль стенки (к глазу)."""
    f_pos = g.geo.outputs["Position"]
    nrm = g.geo.outputs["Normal"]
    inc = g.geo.outputs["Incoming"]
    idn = g.math("MAXIMUM", vmath(g, "DOT_PRODUCT", inc, nrm), 0.08)
    ih = vmath(g, "SUBTRACT", inc, vmath(g, "SCALE", nrm, scale=vmath(g, "DOT_PRODUCT", inc, nrm)))
    # Сдвиг по поверхности на метр глубины: от глаза, тем больше, чем острее угол.
    dvec = vmath(g, "SCALE", ih, scale=g.math("DIVIDE", -1.0, idn))
    hit = None
    t_wall = None
    extra = None
    pos_floor = None
    for k in range(1, steps + 1):
        tk = k / steps
        pk = vmath(g, "ADD", f_pos, vmath(g, "SCALE", dvec, scale=depth_m * tk))
        h, extra = hole_at(pk)
        solid = g.math("SUBTRACT", 1.0, h)
        if hit is None:
            hit = solid
            t_wall = g.mixf(solid, 1.0, tk)
        else:
            new = g.math("MULTIPLY", solid, g.math("SUBTRACT", 1.0, hit))
            t_wall = g.mixf(new, t_wall, tk)
            hit = g.math("MAXIMUM", hit, solid)
        pos_floor = pk
    n_wall = vmath(g, "NORMALIZE", ih)
    return hit, t_wall, pos_floor, extra, n_wall
