"""Задание Designer: старая масляная краска по штукатурке (образец вида — «Cracked Paint» M. Taylor), тайл 2 × 2 м.
Серые карты; цвет, загнутые края и порог отслоения — в материале (texture_layers.paint_layer).

Выходы:
  crack_mask  — мелкая сетка трещин («крокодиловая кожа»): ячейки ~5 см, а островами ещё мельче ~2,5 см;
  peel_patch  — крупные острова отслоений (поле считает post_cells.py по ячейкам: край идёт по трещинам);
  paint_tone  — неровный тон: выцветание пятнами и вертикальные подтёки;
  paint_height — мазки кисти;
  plaster_tone, plaster_height — штукатурка: пятна и поры (тканевую фактуру добавляет post_cells.py).
Запуск: sd_run.py → sd_cook.py (размер 12 = 4096) → post_cells.py <папка> paint.
"""
exec(open("E:/Games/RING-godot/tools/dorm_modules/sd_lib.py", encoding="utf-8").read())
OUT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/designer/dorm_paint.sbs"
G = Graph("dorm_paint")

# Сетка трещин: основная ~5 см везде, мелкая ~2,5 см — островами.
mid = g_crack_net(G, 40, 0.35, 0.7, 24, 0.12)
fine = g_crack_net(G, 80, 0.4, 0.55, 40, 0.08)
fine_zone = g_levels(G, G.inst("noise_clouds_2.sbs", "clouds_2", scale=3, disorder=0.3), "output", 0.45, 0.6)
fine_part = g_blend(G, fine_zone, "unique_filter_output", fine, "unique_filter_output", MUL, 1.0)
cracks = g_blend(G, fine_part, "unique_filter_output", mid, "unique_filter_output", MAX, 1.0)
crack_mask = g_levels(G, cracks, "unique_filter_output", 0.25, 0.75)

# Острова отслоений: крупные пятна с изрезанным краем.
isl = g_blend(G, G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=10, disorder=0.4), "output",
              G.inst("noise_clouds_2.sbs", "clouds_2", scale=3, disorder=0.3), "output", COPY, 0.3)
patch = G.inst("auto_levels.sbs", "auto_levels")
link(isl, "unique_filter_output", patch, "Input")

# Тон: выцветание пятнами и вертикальные подтёки.
fade = G.inst("noise_clouds_2.sbs", "clouds_2", scale=4, disorder=0.4)
streak_src = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=24, disorder=0.3)
streaks = G.atom("directionalwarp", intensity=40.0, warpangle=0.25)
link(streak_src, "output", streaks, "input1")
link(streak_src, "output", streaks, "inputintensity")
tone = g_blend(G, streaks, "unique_filter_output", fade, "output", COPY, 0.35)

# Мазки кисти (вытянутый шум, лёгкий рельеф).
strokes_src = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=64, disorder=0.5)
strokes = G.atom("directionalwarp", intensity=6.0, warpangle=0.0)
link(strokes_src, "output", strokes, "input1")
link(strokes_src, "output", strokes, "inputintensity")
paint_h = g_levels(G, strokes, "unique_filter_output", 0.0, 1.0, 0.35, 0.65)

# Штукатурка: крупные пятна и поры.
pl_big = G.inst("noise_clouds_2.sbs", "clouds_2", scale=8, disorder=0.6)
pl_pores = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=128, disorder=0.0)
pl_h = g_blend(G, pl_pores, "output", pl_big, "output", COPY, 0.35)
pl_tone = g_blend(G, G.inst("noise_dirt_3.sbs", "dirt_3", scale=2, disorder=0.3), "output",
                  G.inst("noise_clouds_2.sbs", "clouds_2", scale=6, disorder=0.5), "output", COPY, 0.5)

G.output(crack_mask, "unique_filter_output", "crack_mask")
G.output(patch, "Output", "peel_patch")
G.output(tone, "unique_filter_output", "paint_tone")
G.output(paint_h, "unique_filter_output", "paint_height")
G.output(pl_tone, "unique_filter_output", "plaster_tone")
G.output(pl_h, "unique_filter_output", "plaster_height")
print("saved", G.save(OUT))
