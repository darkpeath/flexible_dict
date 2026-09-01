# -*- coding: utf-8 -*-

from typing import List
import flexible_dict as fd

@fd.json_object
class Inner:
    x: int = fd.Field(getter_default=0)

@fd.json_object
class Outer:
    one: Inner
    many: List[Inner]

def test_copy_as_builtin_json():
    o = Outer(one={'x': 1}, many=[{'x': 2}, {'x': 3}])
    assert type(o['one']) is Inner
    copied = fd.copy_as_builtin_json(o)
    assert copied == {'one': {'x': 1}, 'many': [{'x': 2}, {'x': 3}]}
    # all json object classes are converted to built-in dict
    assert type(copied) is dict
    assert type(copied['one']) is dict
    assert [type(e) for e in copied['many']] == [dict, dict]

def test_copy_nested_containers():
    data = {'a': [({'b': 1},)], 'c': (1, [2, {'d': 3}])}
    copied = fd.copy_as_builtin_json(data)
    assert copied == data
    # scalars are returned unchanged
    assert fd.copy_as_builtin_json(5) == 5
    assert fd.copy_as_builtin_json("s") == "s"
    assert fd.copy_as_builtin_json(None) is None
