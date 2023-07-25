# -*- coding: utf-8 -*-

import json
from flexible_dict.script.class_builder import build_class_from_json, ClassBuilder

def test_class_builder():
    json_file = "data/a.json"
    py_file = "data/a.py"
    with open(json_file, encoding="utf-8") as f:
        d = json.load(f)
    builder = ClassBuilder()
    builder.build("A", d)
    actual_code = builder.get_code_text()
    with open(py_file, encoding='utf-8') as f:
        expected_code = f.read()
    assert actual_code == expected_code, actual_code

def test_build_class():
    build_class_from_json(["--name", "A", "--file", "data/a.json", "--output", "data/a.py"])
