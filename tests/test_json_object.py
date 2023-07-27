# -*- coding: utf-8 -*-

def test_json_object():
    from flexible_dict import json_object, MISSING
    @json_object
    class A:
        i: int = 3
        j: str = None
        s: float
        g: int = MISSING
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

def test_JsonObject():
    from flexible_dict import JsonObject, MISSING
    class A(JsonObject):
        i: int = 3
        j: str = None
        s: float
        g: int = MISSING
    class B(JsonObject):
        a: A
        k: int = 5

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

    b = B({"a": {"i": 7, "j": 21}})
    assert b.k == 5
    assert b.a.i == 7
    assert b.a.j == 21
    assert b.a.s is None
    try:
        b.a.g
    except KeyError:
        pass
    else:
        assert False
