# -*- coding: utf-8 -*-

# Same code is copied from dataclasses.
# Code of dataclasses is pretty.

from typing import Any, Callable, Dict
import dataclasses
import types

# A sentinel object to detect if a parameter is supplied or not.  Use
# a class to give it a better repr.
class _MISSING_TYPE:
    pass
MISSING = _MISSING_TYPE()

@dataclasses.dataclass
class Field:
    name: str = None
    type: str = None
    static: bool = False    # a class property
    key: str = MISSING     # the key stored in the dict; if set as MISSING, same as name
    readable: bool = True
    writeable: bool = True
    deletable: bool = True
    default: Any = None     # default value when the key not exists
    default_factory: Callable[[dict], Any] = MISSING     # a function to get a value from the dict
    check_exist_before_delete: bool = True  # if set as false, an exception will be raised when the key not exists
    metadata: Dict[Any, Any] = dataclasses.field(default_factory=dict)

class JsonObjectClassProcessor(object):
    """
    parse flexible_dict class, set property and function
    """
    def __init__(self, default_field_value=None):
        """
        :param default_field_value:     default value config on the class for field without init value
        """
        self.default_field_value = default_field_value

    def get_field(self, cls, a_name, a_type) -> Field:
        # Return a Field object for this field name and type.

        # If the default value isn't derived from Field, then it's only a
        # normal default value.  Convert it to a Field().
        default = getattr(cls, a_name, self.default_field_value)
        if isinstance(default, Field):
            f = default
        else:
            if isinstance(default, types.MemberDescriptorType):
                # This is a field in __slots__, so it has no default value.
                default = self.default_field_value
            f = Field(default=default)

        # Only at this point do we know the name and the type.  Set them.
        f.name = a_name
        f.type = a_type

        if self.is_missing(f.key):
            f.key = a_name

        return f

    @staticmethod
    def is_missing(value: Any) -> bool:
        return value is MISSING

    def build_getter(self, field: Field) -> Callable[[dict], Any]:
        if not self.is_missing(field.default):
            def getter(d):
                return d.get(field.key, field.default)
        elif not self.is_missing(field.default_factory):
            def getter(d):
                if field.key in d:
                    return d[field.key]
                return field.default_factory(d)
        else:
            def getter(d):
                return d[field.key]
        return getter

    @staticmethod
    def build_setter(field: Field) -> Callable[[dict, Any], Any]:
        def setter(d, value):
            d[field.key] = value
        return setter

    @staticmethod
    def build_deleter(field: Field) -> Callable[[dict], Any]:
        if field.check_exist_before_delete:
            def deleter(d):
                if field.key in d:
                    d.pop(field.key)
        else:
            def deleter(d):
                d.pop(field.key)
        return deleter

    def build_property(self, field: Field) -> property:
        return property(fget=self.build_getter(field) if field.readable else None,
                        fset=self.build_setter(field) if field.writeable else None,
                        fdel=self.build_deleter(field) if field.deletable else None)

    @staticmethod
    def add_base(cls: type):
        """
        添加dict基类
        """
        if not issubclass(cls, dict):
            d = dict(cls.__dict__)
            d.pop('__dict__')
            bases = tuple(b for b in cls.__bases__ if b != object) + (dict,)
            cls = type(cls.__name__, bases, d)
        return cls

    def process_cls(self, cls: type) -> type:
        annotations = cls.__dict__.get('__annotations__', {})
        if not annotations:
            return cls
        cls = self.add_base(cls)
        for name, a_type in annotations.items():
            field = self.get_field(cls, name, a_type)
            if field.static:
                if field.default is MISSING:
                    delattr(cls, name)
                else:
                    setattr(cls, name, field.default)
            else:
                setattr(cls, name, self.build_property(field))
        return cls

    def __call__(self, cls: type) -> type:
        return self.process_cls(cls)

def json_object(cls=None, processor: JsonObjectClassProcessor = None, processor_cls=JsonObjectClassProcessor, **kwargs):
    """
    a decorator to mark a class as json format
    """
    if processor is None:
        processor = processor_cls(**kwargs)

    def wrap(cls):
        if cls is None:
            # without this line, pycharm code hints would disappear.
            return cls
        return processor(cls)

    # See if we're being called as @flexible_dict or @flexible_dict().
    if cls is None:
        # We're called with parens.
        return wrap

    # We're called as @flexible_dict without parens.
    return wrap(cls)
