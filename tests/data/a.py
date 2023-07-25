from typing import List
from flexible_dict import json_object

@json_object
class C(dict):
    d: int
    e: str

@json_object
class L(dict):
    k1: int
    k2: str

@json_object
class A(dict):
    a: int
    b: str
    c: C
    l: List[L]
