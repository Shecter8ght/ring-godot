# ПП по мотивам KRISS Vector: складной приклад (как у Gen I / Gen II до 2017 со встроенным шарниром на коробке, по
# снимкам владельца 02/04/06/08 и снимку товара KVA-FSBL00): ложе — контур со снимка (trace_stock.py →
# data/stock_profile.json), затыльник с резиновой накладкой, шарнир справа на заднем торце коробки (вертикальная
# ось), защёлка-кнопка с рифлением слева у шарнира, антабка снизу ложа (в контуре). Складывается вправо на 180°.
import json
import math
import os
import bpy
from lib import (MM, HALF_W, REAR_X, HERE, rounded_prism, prism_xz, prism_xy, prism_yz, cyl, box, lathe, boolean, fillet,
                 finish_small, set_origin, apply_transform, v)
from part_receiver import rounded_rect_xz, side_recess, pill_xz

SP = json.load(open(os.path.join(HERE, "data", "stock_profile.json"), encoding="utf-8"))
HINGE_X = SP["hinge_x"]           # −271
HINGE_Y = -21.6                   # ось на правом борту: сложенный затыльник (±19) проходит мимо борта и кнопок
HINGE_Z = (19.0, 51.0)            # по высоте коробки над рукоятью
STOCK_HALF_W = 11.0               # ложе 22 мм (оценка по снимкам владельца)
PAD_HALF_W = 19.0                 # затыльник 38 мм


def hinge_block(C):
    """Шарнир на правом заднем углу коробки: верхний и нижний кулаки — цилиндры Ø13 на оси (вместе с кулаком приклада —
    один высокий цилиндр, как у настоящего), утоплены в торец коробки на 1.5 мм."""
    z0, z1 = HINGE_Z
    plate = None
    for za, zb in ((z0, z0 + 8.5), (z1 - 8.5, z1)):
        k = lathe("Stock_hinge_block" if plate is None else "_lug",
                  [(za, 2.7), (za, 5.7), (za + 0.8, 6.5), (zb - 0.8, 6.5), (zb, 5.7), (zb, 2.7)], C, "Alu_anodized", seg=64)
        k.rotation_euler = (0, -math.pi / 2, 0)
        k.location = v(HINGE_X, HINGE_Y, 0)
        apply_transform(k)
        web = rounded_prism("_web", rounded_rect_xz(HINGE_X - 1.0, REAR_X + 2.0, za, zb, 1.5), HINGE_Y - 5.5,
                            HINGE_Y + 6.5, 1.2, C, seg=4)
        boolean(k, web, op="UNION")
        if plate is None:
            plate = k
        else:
            boolean(plate, k, op="UNION")
    plate["owner"] = "Receiver"
    plate["_fin"] = 1
    pin = cyl("Stock_hinge_pin", z0 - 0.6, z1 + 0.6, 2.5, C, "Steel_black", seg=40, cy=HINGE_X, cz=HINGE_Y, axis="Z")
    cap = lathe("_cap", [(z1 + 0.6, 0.0), (z1 + 0.6, 4.2), (z1 + 2.0, 4.2), (z1 + 2.4, 3.6), (z1 + 2.4, 0.0)], C, seg=48)
    cap.rotation_euler = (0, -math.pi / 2, 0)
    cap.location = v(HINGE_X, HINGE_Y, 0)
    apply_transform(cap)
    boolean(pin, cap, op="UNION")
    finish_small(pin, w=0.15, seg=2)
    pin["owner"] = "Stock_hinge_block,Stock_body"
    return plate, pin


def stock(C):
    body = [tuple(p) for p in SP["body"]["outer"]]
    o = rounded_prism("Stock_body", body, -STOCK_HALF_W, STOCK_HALF_W, 3.0, C, "Polymer", seg=5)
    # кулак шарнира: цилиндр по оси между проушинами коробки (с зазором 0.3)
    z0, z1 = HINGE_Z
    # вырезы ложа под проушины коробки — в контуре (trace_stock.py)
    # кулак приклада — цилиндр Ø13 между кулаками коробки (зазоры 0.3) и перемычка к ложу (только внутрь от оси:
    # сложенный приклад не заходит в борт)
    k = lathe("_kn", [(z0 + 8.8, 2.7), (z0 + 8.8, 5.7), (z0 + 9.6, 6.5), (z1 - 9.6, 6.5), (z1 - 8.8, 5.7), (z1 - 8.8, 2.7)],
              C, seg=64)
    k.rotation_euler = (0, -math.pi / 2, 0)
    k.location = v(HINGE_X, HINGE_Y, 0)
    apply_transform(k)
    arm = rounded_prism("_arm", rounded_rect_xz(HINGE_X - 16.0, HINGE_X + 2.0, z0 + 9.2, z1 - 9.2, 3.0), HINGE_Y + 2.0,
                        STOCK_HALF_W - 1.0, 2.0, C, seg=4)
    boolean(k, arm, op="UNION")
    boolean(o, k, op="UNION")
    # выемки на боках ложа (снимок товара): параллелограмм и длинная — на верхней перекладине; длинная — на стойке
    # (сняты со снимка товара в масштабе 5.43 пикс/мм)
    for pts in ([(-322.3, 28.9), (-334.7, 28.9), (-342.5, 19.2), (-328.6, 19.2)],
                [(-350.0, 29.5), (-401.0, 29.5), (-415.0, -8.0), (-408.0, -8.0), (-396.0, 20.0), (-353.0, 20.0)],
                [(-404.0, -18.0), (-412.0, -18.0), (-428.0, -58.0), (-420.0, -58.0)]):
        side_recess(o, fillet(pts, 1.6, 4), 1.2, C, half=STOCK_HALF_W)
    finish_small(o, w=0.4, seg=3)
    # затыльник: жёсткое основание и резиновая накладка с поперечными рёбрами
    pad = [tuple(p) for p in SP["pad"]["outer"]]
    p = rounded_prism("Stock_buttplate", pad, -PAD_HALF_W, PAD_HALF_W, 2.0, C, "Rubber", seg=5)  # углы контура R 3.4 — запас 1.4
    # рифление тыльной грани резины: канавки вдоль кромки, только по плоской части (до скруглений боков R 3)
    from part_receiver import ribs, edge_run
    xr = min(q[0] for q in pad)
    zs = [q[1] for q in pad]
    ribs(p, pad, edge_run(pad, (xr, max(zs) - 6.0), (xr, min(zs) + 6.0), (xr, (max(zs) + min(zs)) / 2)), 6.4, 2.4, 1.2,
         PAD_HALF_W - 2.4, C, "_padribs")
    finish_small(p, w=0.3, seg=3)
    # винты затыльника — по два с каждой стороны: в середине верхней (Z −24…0) и нижней (Z −99…−67) перекладин ложа у X −448
    for zc in (-7.5, -83.0):
        for sgn in (1, -1):
            sc = lathe("Stock_screw", [(-0.3, 0.0), (-0.3, 4.0), (0.6, 4.0), (1.1, 3.4), (1.1, 0.0)], C, "Steel_bare", seg=48)
            sc.rotation_euler = (0, 0, math.pi / 2 if sgn > 0 else -math.pi / 2)
            sc.location = v(-444.0, STOCK_HALF_W * sgn, zc)
            apply_transform(sc)
            hexp = [(-444.0 + 1.8 * math.cos(math.pi / 3 * k), zc + 1.8 * math.sin(math.pi / 3 * k)) for k in range(6)]
            y_out = (STOCK_HALF_W + 0.5) * sgn
            hx = prism_xz("_hex", hexp, min(y_out - 0.8 * sgn, y_out + 2 * sgn), max(y_out - 0.8 * sgn, y_out + 2 * sgn), C)
            boolean(sc, hx)
            finish_small(sc, w=0.1, seg=2)
            sc["owner"] = "Stock_body"
    # защёлка: кнопка с рифлением слева у шарнира (на ложе)
    lt = rounded_prism("Stock_latch", rounded_rect_xz(HINGE_X - 22.0, HINGE_X - 6.0, 35.5, 46.5, 2.0),
                       STOCK_HALF_W - 0.6, STOCK_HALF_W + 2.4, 0.8, C, "Polymer", seg=4)
    for i in range(7):
        xc = HINGE_X - 8.5 - i * 1.9
        g = prism_xz("_lt", rounded_rect_xz(xc - 0.4, xc + 0.4, 37.5, 44.5, 0.4), STOCK_HALF_W + 1.6, STOCK_HALF_W + 4, C)
        boolean(lt, g)
    finish_small(lt, w=0.2, seg=2)
    lt["owner"] = "Stock_body"
    p["owner"] = "Stock_body"
    return o, p, lt


def build(ctx):
    C = ctx["coll"]["Stock"]
    plate, pin = hinge_block(C)
    body, pad, latch = stock(C)
    return {"hinge": plate, "body": body, "pad": pad, "latch": latch}
