"""Задание Designer: масляная краска по штукатурке, тайл 2 × 2 м (серые карты, цвет — в материале).

Выходы:
  crack_mask  — сетка трещин краски (1 — трещина);
  peel_field  — порядок отслоения: где поле ниже износа, краски нет; ячейки между трещинами отпадают целиком,
                от трещин отслоение ползёт внутрь ячейки — кромка идёт по сетке, как у настоящей краски;
  paint_tone  — неровность тона краски (кисть, выцветание);
  paint_height — рельеф краски: мазки и вдавленные трещины;
  plaster_tone, plaster_height — штукатурка под краской: поры и неровная затирка.
Запуск: python -X utf8 tools/dorm_modules/sd_run.py tools/dorm_modules/sd_paint.py, затем sd_cook.py.
"""
exec(open("E:/Games/RING-godot/tools/dorm_modules/sd_lib.py", encoding="utf-8").read())
OUT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/designer/dorm_paint.sbs"
COPY, ADD, SUB, MUL, MAX, MIN = 0, 1, 2, 3, 5, 6

G = Graph("dorm_paint")


def blend(src, src_out, dst, dst_out, mode, opacity=1.0):
    b = G.atom("blend", blendingmode=mode, opacitymult=opacity)
    link(src, src_out, b, "source")
    link(dst, dst_out, b, "destination")
    return b


def levels(node, out, lo=0.0, hi=1.0, olo=0.0, ohi=1.0):
    lv = G.atom("levels", levelinlow=(lo, lo, lo, lo), levelinhigh=(hi, hi, hi, hi),
                leveloutlow=(olo, olo, olo, olo), levelouthigh=(ohi, ohi, ohi, ohi))
    link(node, out, lv, "input1")
    return lv


def crack_net(scale, disorder, width, warp_scale, warp_amount):
    """Сетка трещин: границы ячеек Вороного (1 — трещина), слегка изогнутые шумом."""
    cells = G.inst("noise_cells_4.sbs", "cells_4", scale=scale, disorder=disorder)
    edges = G.inst("edge_detect.sbs", "edge_detect", edge_width=width, edge_roundness=1.0, tolerance=0.0)
    link(cells, "output", edges, "input")
    inv = G.inst("invert.sbs", "invert_grayscale")
    link(edges, "output", inv, "Source")
    noise = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=warp_scale, disorder=0.3)
    w = G.atom("warp", intensity=warp_amount)
    link(inv, "Invert_Grayscale", w, "input1")
    link(noise, "output", w, "inputgradient")
    return w


big = crack_net(7, 0.25, 1.3, 5, 0.35)
fine = crack_net(19, 0.4, 0.8, 10, 0.25)
# Мелкие трещины — не везде, а островами.
fine_zone = G.inst("noise_clouds_2.sbs", "clouds_2", scale=2, disorder=0.3)
fine_part = G.atom("blend", blendingmode=MUL, opacitymult=1.0)
link(fine, "unique_filter_output", fine_part, "destination")
link(levels(fine_zone, "output", 0.45, 0.65), "unique_filter_output", fine_part, "source")
cracks = blend(fine_part, "unique_filter_output", big, "unique_filter_output", MAX, 1.0)
crack_mask = levels(cracks, "unique_filter_output", 0.2, 0.8)

# Поле отслоений собирается по готовой маске трещин вне Designer (tools/dorm_modules/post_cells.py):
# заливка областей Designer на крупных ячейках даёт полосы, а случайная яркость ячеек шума не совпадает
# с изогнутой сеткой. Отсюда — только крупные зоны износа (где стену чаще задевали и мочили).
patch = G.inst("noise_clouds_2.sbs", "clouds_2", scale=3, disorder=0.2)
patch_lv = levels(patch, "output", 0.2, 0.8)
ragged = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=72, disorder=0.2)

# Краска: мазки кисти (вытянутый шум) и вдавленные трещины.
strokes_src = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=48, disorder=0.5)
strokes = G.atom("directionalwarp", intensity=6.0, warpangle=0.25)
link(strokes_src, "output", strokes, "input1")
link(strokes_src, "output", strokes, "inputintensity")
strokes_lv = levels(strokes, "unique_filter_output", 0.0, 1.0, 0.45, 0.6)
paint_h = blend(crack_mask, "unique_filter_output", strokes_lv, "unique_filter_output", SUB, 0.45)
tone_a = G.inst("noise_clouds_2.sbs", "clouds_2", scale=4, disorder=0.4)
tone_b = G.inst("noise_dirt_3.sbs", "dirt_3", scale=2, disorder=0.1)
tone = blend(tone_b, "output", tone_a, "output", COPY, 0.4)
tone = blend(crack_mask, "unique_filter_output", tone, "unique_filter_output", MUL, 0.35)

# Штукатурка: крупная неровность затирки и мелкие поры.
pl_big = G.inst("noise_clouds_2.sbs", "clouds_2", scale=8, disorder=0.6)
pl_pores = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=96, disorder=0.0)
pl_h = blend(pl_pores, "output", pl_big, "output", COPY, 0.35)
pl_tone_src = G.inst("noise_clouds_2.sbs", "clouds_2", scale=6, disorder=0.5)
pl_tone = blend(pl_pores, "output", pl_tone_src, "output", COPY, 0.25)

G.output(crack_mask, "unique_filter_output", "crack_mask")
G.output(patch_lv, "unique_filter_output", "peel_patch")
G.output(ragged, "output", "peel_ragged")
G.output(tone, "unique_filter_output", "paint_tone")
G.output(paint_h, "unique_filter_output", "paint_height")
G.output(pl_tone, "unique_filter_output", "plaster_tone")
G.output(pl_h, "unique_filter_output", "plaster_height")
print("saved", G.save(OUT))
