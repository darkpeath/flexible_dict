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

def test_diamond_inherit():
    # all classes decorated
    @fd.json_object
    class A:
        a: int = 1
        x: int = 1
    @fd.json_object
    class B(A):
        b: int = 2
    @fd.json_object
    class C(A):
        c: int = 3
        x: int = 300
    @fd.json_object
    class D(B, C):
        d: int = 4
    v = D()
    assert (v.a, v.b, v.c, v.d) == (1, 2, 3, 4)
    # field x is redefined only in C;
    # same as attribute lookup, value should follow the MRO (D, B, C, A)
    assert v.x == 300

def test_diamond_inherit_undecorated_root():
    # the common base class is not decorated and not a subclass of dict
    class A:
        a: int = 1
    @fd.json_object
    class B(A):
        b: int = 2
    @fd.json_object
    class C(A):
        c: int = 3
    @fd.json_object
    class D(B, C):
        d: int = 4
    v = D()
    assert (v.b, v.c, v.d) == (2, 3, 4)
    assert isinstance(v, A)
    assert isinstance(v, dict)
    assert [t.__name__ for t in D.__mro__] == ['D', 'B', 'C', 'A', 'dict', 'object']

def test_diamond_inherit_BaseDict():
    class A(fd.BaseDict):
        x: int = 1
        y: str = "a"
    class B(A):
        x: int = 2
    class C(A):
        y: str = "c"
    class D(B, C):
        z: float = 0.5
    v = D()
    assert v.x == 2
    assert v.y == "c"
    assert v.z == 0.5

def test_process_twice():
    # processing a class twice should be a no-op;
    # it must not degrade the field metadata inherited by subclasses
    @fd.json_object
    @fd.json_object
    class A:
        i: int = 3
        s: str = fd.Field(key="s2", getter_default="hello")
    a = A()
    assert a.i == 3
    assert a.s == "hello"

    # redundant decoration on a BaseDict subclass (already processed
    # by __init_subclass__) is a realistic way to process twice
    @fd.json_object
    class X(fd.BaseDict):
        i: int = 3
        s: str = fd.Field(key="s2", getter_default="hello")

    class Y(X):
        t: int = 1
    y = Y()
    assert (y.i, y.s, y.t) == (3, "hello", 1)
    # the custom key must be kept for subclasses
    y.s = "world"
    assert dict(y) == {"s2": "world"}

def test_process_via_user_init_subclass_hook():
    # a user-defined __init_subclass__ hook on a plain base class;
    # rebuilding the class in add_base triggers the hook again,
    # which must not lead to a harmful second pass
    class AutoJson:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            fd.json_object(cls)

    @fd.json_object
    class B(AutoJson):
        i: int = 3
        s: str = fd.Field(key="s2", getter_default="hello")

    class C(B):
        t: int = 1
    c = C()
    assert (c.i, c.s, c.t) == (3, "hello", 1)
    c.s = "world"
    assert dict(c) == {"s2": "world"}

def test_init_subclass():
    @fd.json_object(create_init_subclass_func=True)
    class C:
        t: int
        k: str = "s"
    # @fd.json_object
    class D(C):
        b: int = 5
        i: int
    d = D(i=8)
    assert d.k == "s"
    assert d.b == 5
    assert d.i == 8

def test_BaseDict():
    class C(fd.BaseDict):
        t: int
        k: str = "s"
    c = C(t=2, k="ti")
    assert c.t == 2
    assert c.k == "ti"

def test_dataclass():
    # work with dataclass, for hint
    import dataclasses
    @dataclasses.dataclass(eq=False, repr=False)
    @fd.json_object
    class A:
        i: int
    @dataclasses.dataclass(eq=False, repr=False)
    @fd.json_object
    class B(A):
        s: str
    b = B()
    assert b.i is None

    @fd.json_object
    @fd.json_object
    @fd.json_object
    class C(B):
        pass

    c = C(s="to")
    assert c.s == "to"
