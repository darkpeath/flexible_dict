from typing import List
from flexible_dict import JsonObject, Field

class L(JsonObject):
    k1: int
    k2: str

class C(JsonObject):
    d: int
    e: str

class A(JsonObject):
    a: int
    b: str
    c: C
    ls: List[L] = Field(key="l")
    keys: List[str]
