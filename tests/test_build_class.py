# -*- coding: utf-8 -*-

from flexible_dict.script.class_builder import build_class_from_json

def test_build_class():
    build_class_from_json(["--name", "A", "--file", "data/a.json", "--output", "data/a.py"])
