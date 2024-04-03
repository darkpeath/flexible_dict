# -*- coding: utf-8 -*-

from typing import List, Optional
from flexible_dict import json_object, MISSING, Field

@json_object
class A:
    t: str
    k: int = 4

@json_object
class B:
    i: int = 3
    j: str = None
    s: float
    s2: str = Field(key="k2")
    g: int = MISSING
    l: List[int]
    a: A

def test_read():
    b = B(dict(i=3, k2='hello', a=dict(t='a2', k=7)))
    assert b.i == b['i'] == 3
    assert b.j is None
    assert 'j' not in b
    assert b.s is None
    assert 's' not in b
    assert b.s2 == b['k2'] == 'hello'
    try:
        b.g
    except KeyError:
        pass
    else:
        assert False
    assert type(b.a) == A

def test_json_object():
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

    import os
    import sys
    print(f"interpreter: {sys.executable}")
    with open(os.path.expanduser('~/Downloads/t.txt'), 'w') as f:
        f.write(sys.executable)
    # raise RuntimeError(sys.executable)

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
        t: List[A]
        w: Optional[A]

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

    b = B({
        "a": {"i": 7, "j": 21},
        "t": [{"i": 8, "j": "t1"}, {"i": 3, "j": "t2"}],
        "w": {"i": 15, "s": 1.2, "g": 10},
    })
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

    assert b.t[0].i == 8
    assert b.t[1].j == "t2"

    assert b.w.i == 15

