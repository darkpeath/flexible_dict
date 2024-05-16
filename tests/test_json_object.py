# -*- coding: utf-8 -*-

from typing import List
import flexible_dict as fd

@fd.json_object
class A:
    t: str
    k: int = 4

@fd.json_object
class B:
    i: int = 3
    j: str
    s: float
    s2: str = fd.Field(key="k2")
    g: int
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
    assert b.g is None
    assert type(b.a) == A

def test_iter_fields():
    b = B(i=3, s2='hello', a=dict(t='a2', k=7), g=4)
    b['j'] = 'we'
    actual = list(b.field_items())
    expected = [
        ('i', 3),
        ('j', 'we'),
        ('s', None),
        ('s2', 'hello'),
        ('g', 4),
        ('l', None),
        ('a', A(dict(t='a2', k=7))),
    ]
    assert len(actual) == len(expected)
    for y, y0 in zip(actual, expected):
        assert y == y0, f"{y} {y0}"

def test_iter_items():
    b = B(i=3, s2='hello', a=dict(t='a2', k=7), g=4)
    b['j'] = 'we'
    actual = list(b.items())
    expected = [
        ('i', 3),
        ('k2', 'hello'),
        ('g', 4),
        ('a', A(dict(t='a2', k=7))),
        ('j', 'we'),
    ]
    assert len(actual) == len(expected)
    for y, y0 in zip(actual, expected):
        assert y == y0, f"{y} {y0}"

def test_overwrite_items():
    @fd.json_object(iter_func_name='items')
    class C:
        i: int = 3
        j: str = None
        s: float
        s2: str = fd.Field(key="k2")
        g: int
        l: List[int]
        a: A
    c = C(i=3, s2='hello', a=dict(t='a2', k=7), g=4)
    c['j'] = 'we'
    actual = list(c.items())
    expected = [
        ('i', 3),
        ('j', 'we'),
        ('s', None),
        ('s2', 'hello'),
        ('g', 4),
        ('l', None),
        ('a', A(dict(t='a2', k=7))),
    ]
    assert len(actual) == len(expected)
    for y, y0 in zip(actual, expected):
        assert y == y0, f"{y} {y0}"

def test_ignore_field():
    @fd.json_object(ignore_not_exists_filed_when_iter=True)
    class C:
        i: int = 3
        j: str = None
        s: float
        s2: str = fd.Field(key="k2")
        g: int
        l: List[int]
        a: A
    c = C(i=3, s2='hello', a=dict(t='a2', k=7), g=4)
    c['j'] = 'we'
    actual = list(c.field_items())
    expected = [
        ('i', 3),
        ('j', 'we'),
        ('s2', 'hello'),
        ('g', 4),
        ('a', A(dict(t='a2', k=7))),
    ]
    assert len(actual) == len(expected)
    for y, y0 in zip(actual, expected):
        assert y == y0, f"{y} {y0}"

def test_json_object():
    @fd.json_object
    class A:
        i: int = fd.Field(getter_default=3)
        j: str = None
        s: float
        g: int
    a = A()
    assert a.i == 3
    assert a.j is None
    assert a.s is None
    assert a.g is None
    a.j = 10
    assert a.j == 10
    assert a['j'] == 10

def test_inherit():
    @fd.json_object
    class C(A):
        t: int
        k: str = "s"
    c = C(t=1, k='w')
    assert c.t == 1
    assert c.k == 'w'

