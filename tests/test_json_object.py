# -*- coding: utf-8 -*-

from flexible_dict import json_object, MISSING

@json_object
class A:
    i: int = 3
    j: str = None
    s: float
    g: int = MISSING


def test_json_object():
    a = A()
    assert a.i == 3
    assert a.j is None
    assert a.s is None
    try:
        a.g
    except KeyError:
        pass
    else:
        assert False
    a.j = 10
    assert a.j == 10
    assert a['j'] == 10
