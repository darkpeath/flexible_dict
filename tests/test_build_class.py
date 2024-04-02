# -*- coding: utf-8 -*-

import os
import json
from flexible_dict.script.class_builder import build_class_from_json, ClassBuilder

data_dir = os.path.join(os.path.dirname(__file__), 'data')
json_file = os.path.join(data_dir, "a.json")
py_file = os.path.join(data_dir, "a.py")

def test_class_builder():
    with open(json_file, encoding="utf-8") as f:
        d = json.load(f)
    builder = ClassBuilder()
    builder.build("A", d)
    actual_code = builder.get_code_text()
    with open(py_file, encoding='utf-8') as f:
        expected_code = f.read()
    assert actual_code == expected_code, actual_code

def test_build_class():
    build_class_from_json(["--name", "A", "--file", json_file, "--output", py_file])
