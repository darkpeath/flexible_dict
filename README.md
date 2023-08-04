# Flexible Dict

A flexible way to access dict data instead of built-in dict.

## Installation

```shell
pip install flexible-dict
```

## Usage

### Define a dict class and access value

#### Way 1

Use a decorator `json_object` to make class to be a flexible dict.

```python
from flexible_dict import json_object, MISSING

@json_object
class A:
    i: int = 3
    j: str = "init value"
    s: float
    g: int = MISSING

a = A()
print(a)  # actual is a dict

print(a.i)  # access value via x.y
print(a.j)

a.j = "update value"  # set value

print(a['j'])  # access value via native dict way
```

**There is a bug in init a nested json_object dict  with a non-empty dict, be careful when init a dict or use Way 2 instead.**

#### Way 2 (suggested)

Inherit the `JsonObject` class to define a flexible dict.

```python
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
```

### Build a json_object class from json data

Suppose there is a file named `a.py` with content

```json
{
  "a": 1,
  "b": "two",
  "c": {
    "d": 4,
    "e": "li"
  }
}
```

Run the script bellow
```shell
python -m flexible_dict build_class --name A --file a.json --output a.py
```

Then a file named `a.py` will be generated

```python
from flexible_dict import json_object

@json_object
class A:
    a: int
    b: str
    c: dict
```
