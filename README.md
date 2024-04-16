# Flexible Dict

A flexible way to access dict data instead of built-in dict.

## Installation

```shell
pip install flexible-dict
```

## Usage

### Define a dict class and access value

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
