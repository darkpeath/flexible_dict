# Flexible Dict

A flexible way to access dict data instead of built-in dict.

## Installation

```shell
pip install flexible-dict
```

## Usage

### Define a dict class and access value

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
