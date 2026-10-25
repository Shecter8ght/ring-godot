# Набор текстур «receiver» (коробка с крышкой) в Substance Painter: фосфатированная сталь ВСС-М.
# Выполняется как задание моста: exec(open(...).read()). Стек перестраивается целиком при каждом запуске.
import importlib
import os
import sys

TOOLS = "E:/Games/RING-godot/tools/vss_m_v8"
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
import sp_lib  # noqa: E402
importlib.reload(sp_lib)
from sp_lib import L, fill, mask_generator, mask_proc, only_meshes, proc_params, triplanar  # noqa: E402

OUT = "E:/Games/RING-godot/_asset_src/vss_m_v8/sp_receiver"
st = sp_lib.stack()
sp_lib.clear(st)
top = L.InsertPosition.from_textureset_stack(st)

# 1. основа: фосфат — тёмно-серый, матовый, металл частично под покрытием
base = fill("01 Фосфат основа", top, color=(0.085, 0.085, 0.09), rough=0.6, metal=0.7)
pos = L.InsertPosition.above_node(base)

# 2. зерно фосфата: мелкая шероховатость и микрорельеф
grain = fill("02 Зерно фосфата", pos, rough="noise_gaussian_noise/gaussian_noise", height="noise_gaussian_noise/gaussian_noise")
triplanar(grain, 170.0)
grain.set_blending_mode(L.BlendingMode.Overlay, sp_lib.CH.SpecularRoughness)
grain.set_opacity(0.35, sp_lib.CH.SpecularRoughness)
grain.set_opacity(0.0025, sp_lib.CH.Height)
pos = L.InsertPosition.above_node(grain)

# 3. неравномерность покрытия: крупные пятна светлее/темнее и шероховатее
tone = fill("03 Неровность покрытия", pos, color=(0.125, 0.123, 0.12), rough=0.7)
mask_proc(tone, "3D_perlin_noise_fractal/3D_perlin_noise_fractal", scale=4.0, opacity=0.8)
sp_lib.lop(tone, 0.25)
pos = L.InsertPosition.above_node(tone)

# 3б. пятнистость шероховатости: участки покрытия чуть глаже/матовее (только шероховатость)
mott = fill("03б Пятна шероховатости", pos, rough=0.48)
mask_proc(mott, "grunge_rough_dirty/grunge_rough_dirty", scale=3.0, opacity=1.0)
sp_lib.lop(mott, 0.3)
pos = L.InsertPosition.above_node(mott)

# 4. заполированность от рук и чехла: направленные протирки — меньше шероховатость, чуть ярче металл
wipe = fill("04 Протирки", pos, rough=0.5)
mask_proc(wipe, "grunge_wipe_directional/grunge_wipe_directional", scale=4.0, opacity=0.8)
sp_lib.lop(wipe, 0.3)
pos = L.InsertPosition.above_node(wipe)

# 5. мелкие царапины: до металла, тонкие, редкие
scr = fill("05 Мелкие царапины", pos, color=(0.38, 0.38, 0.39), rough=0.3, metal=1.0)
mask_proc(scr, "grunge_scratches_fine/grunge_scratches_fine", {"scratches_amount": 0.6, "balance": 0.5}, scale=2.6, opacity=1.0)
sp_lib.lop(scr, 0.85)
pos = L.InsertPosition.above_node(scr)

# 5б. потёртости: затёртые места, где фосфат протёрт до металла пятнами и штрихами
scuff = fill("05б Потёртости", pos, color=(0.24, 0.24, 0.245), rough=0.38, metal=0.92)
mask_proc(scuff, "grunge_scratches_rough/grunge_scratches_rough", scale=3.0, opacity=1.0)
sp_lib.lop(scuff, 0.5)
pos = L.InsertPosition.above_node(scuff)

# 6. износ кромок до металла
edge = fill("06 Износ кромок", pos, color=(0.52, 0.52, 0.53), rough=0.28, metal=1.0)
mask_generator(edge, "mg_metal_edge_wear/mg_metal_edge_wear",
               {"Wear_Level": 0.4, "Wear_Contrast": 0.65, "Grunge_Amount": 0.6, "grunge_scale": 4,
                "Use_Triplanar": 1, "Edges_Smoothness": 0.6, "Ambient_Occlusion_Masking": 0.6, "Curvature_Weight": 1.0})
pos = L.InsertPosition.above_node(edge)

# 7. планка: зубья протёрты креплениями прицелов сильнее
rail = fill("07 Износ планки", pos, color=(0.5, 0.5, 0.51), rough=0.28, metal=1.0)
mask_generator(rail, "mg_metal_edge_wear/mg_metal_edge_wear",
               {"Wear_Level": 0.5, "Wear_Contrast": 0.65, "Grunge_Amount": 0.4, "grunge_scale": 10, "Use_Triplanar": 1})
only_meshes(rail, ["Cover_picatinny__sp"])
pos = L.InsertPosition.above_node(rail)

# 8. грязь и нагар в углублениях
dirt = fill("08 Грязь в углах", pos, color=(0.045, 0.04, 0.035), rough=0.85, metal=0.0)
mask_generator(dirt, "mg_dirt/mg_dirt", {"dirt_level": 0.3, "dirt_contrast": 0.8, "grunge_amount": 0.4, "Grunge_Scale": 6,
                                         "Use_Triplanar": 1, "edges_masking": 0.8})
sp_lib.lop(dirt, 0.7)
pos = L.InsertPosition.above_node(dirt)

# 9. лёгкая пыль: редкая, только в мелких порах
dust = fill("09 Пыль", pos, color=(0.30, 0.285, 0.26), rough=0.95, metal=0.0)
mask_proc(dust, "grunge_dust_small/grunge_dust_small", scale=8.0, opacity=1.0)
sp_lib.lop(dust, 0.08)
pos = L.InsertPosition.above_node(dust)

# 10. отпечатки: жировой след — блестит, почти не меняет цвет
fp = fill("10 Отпечатки", pos, rough=0.26)
mask_proc(fp, "grunge_fingerprints_smeared/grunge_fingerprints_smeared", scale=6.0, opacity=1.0)
sp_lib.lop(fp, 0.22)

print("stack:", [n.get_name() for n in L.get_root_layer_nodes(st)])
sp_lib.P.save_as(OUT + "/receiver.spp")
status, tex = sp_lib.export(OUT + "/export", "receiver")
print("export", status, tex)
