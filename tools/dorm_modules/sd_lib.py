"""Общая часть заданий Substance Designer для материалов общежития (выполняется внутри Designer через мост).

В задании: exec(open(<путь к sd_lib.py>, encoding="utf-8").read()) — дальше доступны функции ниже.
Граф строится узлами библиотеки Designer (sbs://…) и атомарными узлами; сохраняется в .sbs,
затем sbscooker → .sbsar и sbsrender → карты (tools/dorm_modules/sd_cook.py).
"""
import os

import sd
from sd.api.sdapplication import SDApplicationPath
from sd.api.sdbasetypes import float2, float3, float4, int2
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluebool import SDValueBool
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdvaluefloat2 import SDValueFloat2
from sd.api.sdvaluefloat3 import SDValueFloat3
from sd.api.sdvaluefloat4 import SDValueFloat4
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvalueint2 import SDValueInt2
from sd.api.sdvaluestring import SDValueString
from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph

LIB_DIR = os.path.join(app.getPath(SDApplicationPath.DefaultResourcesDir), "packages")
_LOADED = {}


def lib_graph(pkg_file, graph_id):
    """Граф из библиотеки Designer по файлу пакета и идентификатору."""
    if pkg_file not in _LOADED:
        path = os.path.join(LIB_DIR, pkg_file)
        pkg = next((p for p in pkg_mgr.getUserPackages() if p.getFilePath().replace("\\", "/") == path.replace("\\", "/")), None)
        _LOADED[pkg_file] = pkg or pkg_mgr.loadUserPackage(path)
    for r in _LOADED[pkg_file].getChildrenResources(True):
        if r.getIdentifier() == graph_id:
            return r
    raise KeyError(f"{pkg_file}:{graph_id}")


class Graph:
    """Граф материала: узлы раскладываются по сетке, чтобы его можно было открыть и читать в Designer."""

    def __init__(self, name):
        self.pkg = pkg_mgr.newUserPackage()
        self.g = SDSBSCompGraph.sNew(self.pkg)
        self.g.setIdentifier(name)
        self.col = 0
        self.row = 0

    def _place(self, node):
        node.setPosition(float2(self.col * 170.0, self.row * 140.0))
        self.row += 1
        if self.row > 8:
            self.row = 0
            self.col += 1
        return node

    def inst(self, pkg_file, graph_id, **params):
        node = self._place(self.g.newInstanceNode(lib_graph(pkg_file, graph_id)))
        for k, v in params.items():
            setp(node, k, v)
        return node

    def atom(self, kind, **params):
        node = self._place(self.g.newNode(f"sbs::compositing::{kind}"))
        for k, v in params.items():
            setp(node, k, v)
        return node

    def output(self, src, out_id, identifier, usage=None):
        node = self._place(self.g.newNode("sbs::compositing::output"))
        node.setAnnotationPropertyValueFromId("identifier", SDValueString.sNew(identifier))
        node.setAnnotationPropertyValueFromId("label", SDValueString.sNew(identifier))
        if usage:
            from sd.api.sdusage import SDUsage
            from sd.api.sdvalueusage import SDValueUsage
            from sd.api.sdvaluearray import SDValueArray
            from sd.api.sdtypeusage import SDTypeUsage
            arr = SDValueArray.sNew(SDTypeUsage.sNew(), 0)
            arr.pushBack(SDValueUsage.sNew(SDUsage.sNew(usage, "RGBA", "")))
            node.setAnnotationPropertyValueFromId("usages", arr)
        link(src, out_id, node, "inputNodeOutput")
        return node

    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        pkg_mgr.savePackageAs(self.pkg, path)
        return path


def link(a, a_out, b, b_in):
    a.newPropertyConnectionFromId(a_out, b, b_in)


def out_id(node):
    """Единственный выход узла (у экземпляров библиотеки обычно output / Output)."""
    outs = node.getProperties(SDPropertyCategory.Output)
    return outs[0].getId()


def setp(node, pid, v):
    if isinstance(v, bool):
        val = SDValueBool.sNew(v)
    elif isinstance(v, int):
        val = SDValueInt.sNew(v)
    elif isinstance(v, float):
        val = SDValueFloat.sNew(v)
    elif isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, int) for x in v):
        val = SDValueInt2.sNew(int2(*v))
    elif isinstance(v, tuple) and len(v) == 2:
        val = SDValueFloat2.sNew(float2(*v))
    elif isinstance(v, tuple) and len(v) == 3:
        val = SDValueFloat3.sNew(float3(*v))
    elif isinstance(v, tuple) and len(v) == 4:
        val = SDValueFloat4.sNew(float4(*v))
    else:
        raise TypeError(f"{pid}: {v!r}")
    node.setInputPropertyValueFromId(pid, val)


COPY, ADD, SUB, MUL, MAX, MIN = 0, 1, 2, 3, 5, 6


def g_blend(G, src, src_out, dst, dst_out, mode, opacity=1.0):
    b = G.atom("blend", blendingmode=mode, opacitymult=opacity)
    link(src, src_out, b, "source")
    link(dst, dst_out, b, "destination")
    return b


def g_levels(G, node, out, lo=0.0, hi=1.0, olo=0.0, ohi=1.0):
    lv = G.atom("levels", levelinlow=(lo, lo, lo, lo), levelinhigh=(hi, hi, hi, hi),
                leveloutlow=(olo, olo, olo, olo), levelouthigh=(ohi, ohi, ohi, ohi))
    link(node, out, lv, "input1")
    return lv


def g_crack_net(G, scale, disorder, width, warp_scale, warp_amount):
    """Сетка трещин: границы ячеек Вороного (1 — трещина), изогнутые шумом. Выход — unique_filter_output."""
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


def describe(node):
    ins = [p.getId() for p in node.getProperties(SDPropertyCategory.Input) if p.isConnectable()]
    outs = [p.getId() for p in node.getProperties(SDPropertyCategory.Output)]
    return f"in={ins} out={outs}"
