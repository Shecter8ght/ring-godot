"""Задание Designer: побелка по штукатурке по кирпичу, тайл 2 × 2 м (серые карты, цвет — в материале).

Выходы:
  wash_crack     — мелкая сетка трещин побелки (поле облетания считает post_cells.py → wash_field);
  wash_patch, wash_ragged — крупные зоны и рваность облетания побелки;
  wash_tone      — пятна и подтёки побелки;
  loss_patch     — где штукатурка отвалилась до кирпича (крупные куски), crumble — осыпающийся край;
  plaster_crack  — редкие длинные трещины по штукатурке;
  plaster_tone, plaster_height — сама штукатурка: затирка и поры.
"""
exec(open("E:/Games/RING-godot/tools/dorm_modules/sd_lib.py", encoding="utf-8").read())
OUT = "E:/Models Blender/ENVIRONMENT/RING_Dorm_Modules/designer/dorm_plaster.sbs"
G = Graph("dorm_plaster")

wash = g_crack_net(G, 22, 0.35, 0.8, 9, 0.3)
wash_mask = g_levels(G, wash, "unique_filter_output", 0.2, 0.8)
wash_patch = g_levels(G, G.inst("noise_clouds_2.sbs", "clouds_2", scale=3, disorder=0.5), "output", 0.2, 0.8)
wash_ragged = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=96, disorder=0.3)
wash_tone = g_blend(G, G.inst("noise_dirt_3.sbs", "dirt_3", scale=2, disorder=0.2), "output",
                    G.inst("noise_clouds_2.sbs", "clouds_2", scale=5, disorder=0.4), "output", COPY, 0.45)

# Длинные трещины штукатурки: крупные ячейки с сильным изгибом, только местами.
pc = g_crack_net(G, 3, 0.7, 0.7, 4, 1.4)
pc_zone = g_levels(G, G.inst("noise_clouds_2.sbs", "clouds_2", scale=2, disorder=0.6), "output", 0.5, 0.62)
plaster_crack = g_blend(G, pc_zone, "unique_filter_output", pc, "unique_filter_output", MUL, 1.0)

# Куски штукатурки: плавные крупные пятна; край — средней частоты «крошка» без зерна.
loss = g_blend(G, G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=5, disorder=0.4), "output",
               G.inst("noise_clouds_2.sbs", "clouds_2", scale=2, disorder=0.3), "output", COPY, 0.3)
loss_patch = G.inst("auto_levels.sbs", "auto_levels")
link(loss, "unique_filter_output", loss_patch, "Input")
crumble = g_blend(G, G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=28, disorder=0.5), "output",
                  G.inst("noise_clouds_2.sbs", "clouds_2", scale=14, disorder=0.4), "output", COPY, 0.5)

pl_big = G.inst("noise_clouds_2.sbs", "clouds_2", scale=8, disorder=0.6)
pl_pores = G.inst("noise_perlin_noise.sbs", "perlin_noise", scale=96, disorder=0.0)
pl_h = g_blend(G, pl_pores, "output", pl_big, "output", COPY, 0.35)
pl_tone = g_blend(G, pl_pores, "output", G.inst("noise_clouds_2.sbs", "clouds_2", scale=6, disorder=0.5), "output", COPY, 0.25)

G.output(wash_mask, "unique_filter_output", "wash_crack")
G.output(wash_patch, "unique_filter_output", "wash_patch")
G.output(wash_ragged, "output", "wash_ragged")
G.output(wash_tone, "unique_filter_output", "wash_tone")
G.output(loss_patch, "Output", "loss_patch")
G.output(crumble, "unique_filter_output", "crumble")
G.output(plaster_crack, "unique_filter_output", "plaster_crack")
G.output(pl_tone, "unique_filter_output", "plaster_tone")
G.output(pl_h, "unique_filter_output", "plaster_height")
print("saved", G.save(OUT))
