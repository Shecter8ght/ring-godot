"""Поле META генератора без импорта bpy: python -X utf8 tools/prospekt_city/meta.py <модуль> <поле>."""
import ast
import sys
from pathlib import Path

tree = ast.parse((Path(__file__).resolve().parent / f"{sys.argv[1]}.py").read_text(encoding="utf-8"))
meta = [ast.literal_eval(n.value) for n in tree.body
        if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "META"][0]
sys.stdout.write(str(meta[sys.argv[2]]))
