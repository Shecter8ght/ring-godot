"""Клёны и тополя зоны 1 — PBR на принятой форме v01 (нативный UCUPaint 2.4.9), bpy:

    "D:/ПРОГРАММЫ/Blender 5/blender.exe" --background --factory-startup --python-exit-code 1 --python tools/zone01_trees/pbr.py -- [maple negundo poplar] [preview]

Форма та же (forms.build_set, принята владельцем 2026-10-29: «Да, делай дальше»); лист клёна в режиме «alpha» — сетка с запасом,
край листа — альфа настоящего листа (species_z1.LEAF_MODE). Материалы — стеки UCUPaint (функции растений «Проспекта»):
  кора    — фото CC0 (цвет + нормаль), тон модификатором; у тополя внизу — старая бороздчатая (ambientCG Bark001) по атрибуту
            высоты, у всех — мох с севера у земли и почва у комля;
  ветви   — гладкая кора своего вида; сухие сучья и обломки — серая выветренная древесина;
  побеги  — свой цвет вида (клён — красновато-бурые, ясенелистный — сизо-зелёные, тополь — серо-жёлтые); крылатки — соломенные;
  листья  — три осенних тона (зелёный / жёлтый / оранжевый или бурый), каждый — своё фото CC0 (leaf_textures.py), жилки
            нормалью, светлее / темнее по листьям (цвет вершин r); изнанка светлее, тонкий лист на просвет, вырез — альфа фото.
Картинки встроены. → models/0N_<Вид>_PBR_v01.blend (по виду), снимки previews/<вид>_*_pbr_v01.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import bpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "prospekt_plants"))
import build_pbr as BPP  # noqa: E402  (стеки UCUPaint растений «Проспекта»)
import plib  # noqa: E402
import species_z1 as S  # noqa: E402
import forms as F  # noqa: E402

ROOT = HERE.parents[1]
LEAVES = ROOT / "_asset_src/zone01_trees/leaves"
PT = ROOT / "_asset_src/prospekt_plants/textures"
VERSION = "v01"
ORDER = ["maple", "negundo", "poplar"]

BROWN = dict(albedo=ROOT / "assets/textures/bark_brown_02/albedo.jpg", normal=ROOT / "assets/textures/bark_brown_02/normal.jpg")
SHRUB = dict(albedo=PT / "shrub_bark_albedo.png", normal=PT / "shrub_bark_normal.png")
POPLAR_YOUNG = dict(albedo=PT / "poplar_bark_young_albedo.png", normal=PT / "poplar_bark_young_normal.png")
# кора ствола: фото, шероховатость, тон (насыщенность, яркость), плитка, м (u, v)
BARK_TEX = {
    # клён остролистный: серо-бурая с частыми продольными бороздками
    "maple": dict(**BROWN, rough=0.88, sat=0.5, val=0.82, tile=(0.8, 0.8)),
    # ясенелистный: светлее, серо-бурая, мелкие гребни
    "negundo": dict(**BROWN, rough=0.86, sat=0.42, val=1.08, tile=(0.6, 0.6)),
    # тополь: серо-зелёная гладкая (внизу — старая бороздчатая слоем)
    "poplar": dict(**POPLAR_YOUNG, rough=0.7, sat=1.0, val=1.0, tile=(1.0, 1.0)),
}
BRANCH_TEX = {
    "maple": dict(**SHRUB, rough=0.75, sat=1.05, val=0.78, tile=(0.5, 0.5)),
    "negundo": dict(**SHRUB, rough=0.72, sat=1.0, val=1.0, tile=(0.5, 0.5)),
    "poplar": dict(**POPLAR_YOUNG, rough=0.7, sat=1.0, val=1.0, tile=(1.0, 1.0)),
}
# ясенелистный: молодые ветви с зеленцой (сизый налёт)
BRANCH_TINT = {"negundo": ((0.36, 0.42, 0.32), 0.45)}
TWIG = {"maple": (0.34, 0.22, 0.15), "negundo": (0.36, 0.44, 0.3), "poplar": (0.42, 0.38, 0.26)}
SEED = {"maple": (0.56, 0.43, 0.26), "negundo": (0.47, 0.35, 0.21), "poplar": (0.5, 0.4, 0.25)}
# высота старой бороздчатой коры у тополей зоны 1, м
OLD_H = {"tree_poplar_0": 8.0, "tree_poplar_1": 7.0, "tree_poplar_2": 2.2}
# лист: (насыщенность, яркость) фото; светлее/темнее по листьям; пыль (пригород — меньше, чем на проспекте)
LEAF_TONE = {"maple": (0.95, 0.92), "negundo": (0.92, 0.9), "poplar": (0.92, 0.88)}
LIGHT = {"leaf_g": (0.5, 0.48, 0.12), "leaf_y": (0.72, 0.6, 0.16), "leaf_o": (0.62, 0.36, 0.1)}
DARK = {"leaf_g": (0.08, 0.12, 0.03), "leaf_y": (0.22, 0.15, 0.04), "leaf_o": (0.16, 0.08, 0.03)}
RIPE = {"leaf_g": ("g", "лист_зелёный"), "leaf_y": ("y", "лист_жёлтый"), "leaf_o": ("o", "лист_осенний")}
UNDER = {"maple": (0.7, 1.25), "negundo": (0.7, 1.25), "poplar": (0.5, 1.45)}


def relabel() -> None:
    """Подпись авторства у стеков (make_stack «Проспекта» пишет свою)."""
    for mat in bpy.data.materials:
        if mat.get("authoring", "").startswith("Нативный UCUPaint 2.4.9; Claude; растения «Проспекта»"):
            mat["authoring"] = "Нативный UCUPaint 2.4.9; Claude; клёны и тополя зоны 1, PBR v01 на форме v01"


def bark_stack(mat, kind: str, tex: dict, base: bool) -> None:
    tree = BPP.make_stack(mat, f"{S.LABEL[kind]} • {'кора ствола' if base else 'кора ветвей'}")
    lay = BPP.layer(tree, "01 • Кора — фото CC0", "IMAGE", color="source", rough=tex["rough"], img=BPP.image(tex["albedo"], True))
    if tex["sat"] != 1.0 or tex["val"] != 1.0:
        BPP.huesat(lay, 0.5, tex["sat"], tex["val"])
    BPP.layer(tree, "02 • Рельеф коры — нормаль фото", "IMAGE", normal="map", normal_type="NORMAL_MAP",
              img=BPP.image(tex["normal"], False))
    if not base and kind in BRANCH_TINT:
        c, k = BRANCH_TINT[kind]
        lay = BPP.layer(tree, "03 • Сизо-зелёный налёт молодых ветвей", color=c, amount=k)
        BPP.noise(lay, "Неровно", 18.0, 0.3, 0.75)
    if base and kind == "poplar":
        lay = BPP.layer(tree, "03 • Старая бороздчатая кора внизу ствола", "IMAGE", color="source", rough=0.92,
                        img=BPP.image(BPP.OLD_BARK["albedo"], True))
        BPP.huesat(lay, 0.5, 0.45, 0.78)
        BPP.vcol(lay, "Старая_кора", "Граница старой коры")
        lay = BPP.layer(tree, "04 • Рельеф борозд", "IMAGE", normal="map", normal_type="NORMAL_MAP",
                        img=BPP.image(BPP.OLD_BARK["normal"], False))
        BPP.vcol(lay, "Старая_кора", "Граница старой коры")
    if base:
        lay = BPP.layer(tree, "05 • Мох с севера у земли", color=(0.12, 0.17, 0.05), rough=0.95, amount=0.85)
        BPP.vcol(lay, "Мох_север", "Север и низ")
        BPP.noise(lay, "Пятна мха", 9.0, 0.35, 0.7)
        lay = BPP.layer(tree, "06 • Почва у комля (брызги, пыль)", color=(0.16, 0.12, 0.08), rough=0.95, amount=0.7)
        BPP.vcol(lay, "Почва", "Самый низ")
        BPP.noise(lay, "Неровный край", 14.0, 0.3, 0.7)
    BPP.reconnect(tree)


def dead_stack(mat, kind: str) -> None:
    """Сухие сучья и обломанные ветви: кора облезла пятнами, древесина серая выветренная."""
    tree = BPP.make_stack(mat, f"{S.LABEL[kind]} • сухие сучья")
    lay = BPP.layer(tree, "01 • Кора ветвей — фото", "IMAGE", color="source", rough=0.85, img=BPP.image(SHRUB["albedo"], True))
    BPP.huesat(lay, 0.5, 0.45, 1.05)
    BPP.layer(tree, "02 • Рельеф", "IMAGE", normal="map", normal_type="NORMAL_MAP", img=BPP.image(SHRUB["normal"], False))
    lay = BPP.layer(tree, "03 • Голая серая древесина (кора облезла)", color=(0.5, 0.47, 0.42), rough=0.9, amount=0.85)
    BPP.noise(lay, "Облезлые пятна", 7.0, 0.42, 0.62)
    BPP.reconnect(tree)


def twig_stack(mat, kind: str) -> None:
    tree = BPP.make_stack(mat, f"{S.LABEL[kind]} • побеги и черешки")
    BPP.layer(tree, "01 • Побег — свой цвет", color=TWIG[kind], rough=0.7)
    lay = BPP.layer(tree, "02 • Неровность цвета", color=tuple(c * 0.7 for c in TWIG[kind]), amount=0.6)
    BPP.noise(lay, "Пятна", 60.0, 0.4, 0.75)
    BPP.reconnect(tree)


def seed_stack(mat, kind: str) -> None:
    tree = BPP.make_stack(mat, f"{S.LABEL[kind]} • крылатки")
    BPP.layer(tree, "01 • Сухие крылатки", color=SEED[kind], rough=0.75)
    lay = BPP.layer(tree, "02 • Темнее у орешка и жилок", color=tuple(c * 0.55 for c in SEED[kind]), amount=0.55)
    BPP.noise(lay, "Пятна", 90.0, 0.45, 0.75)
    BPP.reconnect(tree)


def leaf_stack(mat, kind: str, slot: str) -> None:
    ripe, name = RIPE[slot]
    sat, val = LEAF_TONE[kind]
    tree = BPP.make_stack(mat, f"{S.LABEL[kind]} • {name.replace('_', ' ')}")
    col_img = BPP.image(LEAVES / f"{kind}_{ripe}_leaf_color.png", True)
    lay = BPP.layer(tree, "01 • Лист — фото CC0 (ambientCG), осенний", "IMAGE", color="source",
                    rough=0.6 if kind != "poplar" else 0.48, img=col_img)
    BPP.huesat(lay, 0.5, sat, val)
    BPP.layer(tree, "02 • Жилки — нормаль скана", "IMAGE", normal="map", normal_type="NORMAL_MAP",
              img=BPP.image(LEAVES / f"{kind}_{ripe}_leaf_normal.png", False))
    lay = BPP.layer(tree, "03 • Светлее и желтее — часть листьев", color=LIGHT[slot], amount=0.25)
    BPP.vcol(lay, "Col", "Оттенок листа (r)", 0.66, 1.0)
    lay = BPP.layer(tree, "04 • Темнее — часть листьев", color=DARK[slot], amount=0.25)
    BPP.vcol(lay, "Col", "Оттенок листа (r)", 0.0, 0.3, invert=True)
    lay = BPP.layer(tree, "05 • Пыль", color=(0.45, 0.43, 0.36), rough=0.8, amount=0.06)
    BPP.noise(lay, "Пятна пыли", 6.0, 0.35, 0.75)
    BPP.reconnect(tree)
    BPP.leaf_sides(mat, kind, col_img)


def apply(kind: str, entries: list) -> None:
    for e in entries:
        BPP.bark_attrs(e["wood"], kind, e["key"])
    lab = S.LABEL[kind]
    mats = bpy.data.materials

    def used(name: str) -> bool:
        return any(name in [m.name for m in o.data.materials if m] for o in bpy.data.objects if o.type == "MESH")

    if used(f"{lab}_кора"):
        bark_stack(mats[f"{lab}_кора"], kind, BARK_TEX[kind], True)
    if used(f"{lab}_ветви"):
        bark_stack(mats[f"{lab}_ветви"], kind, BRANCH_TEX[kind], False)
    if used(f"{lab}_сухие"):
        dead_stack(mats[f"{lab}_сухие"], kind)
    twig_stack(mats[f"{lab}_побеги"], kind)
    if used(f"{lab}_крылатки"):
        seed_stack(mats[f"{lab}_крылатки"], kind)
    for slot, (_, name) in RIPE.items():
        if used(f"{lab}_{name}"):
            leaf_stack(mats[f"{lab}_{name}"], kind, slot)
    relabel()


def pbr_path(kind: str) -> Path:
    return F.LIB / "models" / f"{ORDER.index(kind) + 1:02d}_{S.LABEL[kind]}_PBR_{VERSION}.blend"


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    kinds = [k for k in ORDER if k in argv] or ORDER
    S.LEAF_MODE = "alpha"
    BPP.UNDER.update(UNDER)
    BPP.OLD_H.update(OLD_H)
    for kind in kinds:
        plib.BARK.update(tile_u=BARK_TEX[kind]["tile"][0], tile_v=BARK_TEX[kind]["tile"][1])
        entries, mods, row = F.build_set(S.LABEL[kind].replace("_", " "), [kind])
        BPP.native()
        apply(kind, entries)
        bpy.context.view_layer.update()
        res = F.measure(entries)
        for e, r in zip(entries, res):
            e["res"] = r
        bpy.ops.file.pack_all()
        path = pbr_path(kind)
        bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
        print("TREES PBR", path.name, flush=True)
        if "preview" in argv:
            F.VERSION = "pbr_" + VERSION
            F.previews(kind, entries, mods, row)


if __name__ == "__main__":
    main()
