# -*- coding: utf-8 -*-

# Same code is copied from dataclasses.
# Code of dataclasses is pretty.

from typing import Any, Callable, Dict, Tuple, Iterable
import warnings
import dataclasses
import types

# A sentinel object to detect if a parameter is supplied or not.  Use
# a class to give it a better repr.
class _MISSING_TYPE:
    pass
MISSING = _MISSING_TYPE()

# The name of an attribute on the class where we store the Field
# objects.  Also used to check if a class is a json_object class.
_FIELDS = '__json_object_fields__'

@dataclasses.dataclass
class Field:
    name: str = None
    type: type = None
    static: bool = False    # a class property
    exclude: bool = False   # exclude from dict key and mark as object property
    key: str = MISSING     # the key stored in the dict; same as name if set as MISSING
    readable: bool = True
    writeable: bool = True
    deletable: bool = True
    default: Any = None     # default value when the key not exists
    default_factory: Callable[[dict], Any] = MISSING     # a function to get a value from the dict
    check_exist_before_delete: bool = True  # if set as false, an exception will be raised when the key not exists
    adapt_data_type: bool = None        # whether adapt data value as specified type; determined by the tool if set None
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

    @staticmethod
    def is_missing(value: Any) -> bool:
        return value is MISSING

    def get_field(self, cls, a_name, a_type) -> Field:
        """
        Return a Field object for this field name and type.
        """
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

        # If missing key, set as name.
        if self.is_missing(f.key):
            f.key = a_name

        return f

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
        adapt_data_type = field.adapt_data_type
        if adapt_data_type is None:
            adapt_data_type = isinstance(field.type, type) and hasattr(field.type, _FIELDS)
        if adapt_data_type:
            def setter(d, value):
                if not isinstance(value, field.type) and isinstance(value, dict):
                    value = field.type(value)
                d[field.key] = value
        else:
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
        add dict as base if cls is not a subclass of dict
        """
        if not issubclass(cls, dict):
            d = dict(cls.__dict__)
            d.pop('__dict__')
            bases = tuple(b for b in cls.__bases__ if b != object) + (dict,)
            cls = type(cls.__name__, bases, d)
        return cls

    def set_fields(self, cls: type):
        """
        set fields in annotations as property
        """
        fields = {}

        # Find our base classes in reverse MRO order, and exclude
        # ourselves.  In reversed order so that more derived classes
        # override earlier field definitions in base classes.  As long as
        # we're iterating over them, see if any are frozen.
        for b in cls.__mro__[-1:0:-1]:
            # Only process classes that have been processed by our
            # decorator.  That is, they have a _FIELDS attribute.
            base_fields = getattr(b, _FIELDS, None)
            if base_fields is not None:
                for f in base_fields.values():
                    fields[f.name] = f

        # Annotations that are defined in this class (not in base
        # classes).  If __annotations__ isn't present, then this class
        # adds no new annotations.  We use this to compute fields that are
        # added by this class.
        #
        # Fields are found from cls_annotations, which is guaranteed to be
        # ordered.  Default values are from class attributes, if a field
        # has a default.  If the default value is a Field(), then it
        # contains additional info beyond (and possibly including) the
        # actual default value.
        cls_annotations = cls.__dict__.get('__annotations__', {})

        # Now find fields in our class.  While doing so, validate some
        # things, and set the default values (as class attributes) where
        # we can.
        for name, a_type in cls_annotations.items():
            field = self.get_field(cls, name, a_type)
            if field.static:
                # It's not suggested to define a class field in this way.
                if self.is_missing(field.default):
                    delattr(cls, name)
                else:
                    setattr(cls, name, field.default)
            elif field.exclude:
                if self.is_missing(field.default) and self.is_missing(field.default):
                    delattr(cls, name)
                elif not self.is_missing(field.default):
                    # Actually it should be set to the obj when init,
                    # this is a temp way to set as a class value.
                    setattr(cls, name, field.default)
                else:
                    # Rare situation should set a dynamic default value.
                    raise ValueError("not allowed to specify a factory.")
            else:
                setattr(cls, name, self.build_property(field))
                fields[name] = field

        # Do we have any Field members that don't also have annotations?
        for name, value in cls.__dict__.items():
            if isinstance(value, Field) and name not in cls_annotations:
                raise TypeError(f'{name!r} is a field but has no type annotation')

        # Remember all of the fields on our class (including bases).  This
        # also marks this class as being a dataclass.
        setattr(cls, _FIELDS, fields)

    @staticmethod
    def add_class_methods(cls: type):
        """
        add some class methods
        """

    def process_class(self, cls: type) -> type:
        cls = self.add_base(cls)
        self.set_fields(cls)
        self.add_class_methods(cls)
        return cls

    def process_cls(self, cls: type) -> type:
        warnings.warn("deprecated, please use self.process_class() instead.", DeprecationWarning)
        return self.process_class(cls)

    def __call__(self, cls: type) -> type:
        return self.process_class(cls)

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

# Another way to define a json_object class, just inherit this class.
class JsonObject(dict):
    def __init_subclass__(cls):
        super().__init_subclass__()
        JsonObjectClassProcessor()(cls)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fields = getattr(self, _FIELDS, {})
        for f in fields.values():
            f: Field
            value = self.get(f.key)
            if value is None or not isinstance(f.type, type) or isinstance(value, f.type):
                continue
            adapt_data_type = f.adapt_data_type
            if adapt_data_type is None or adapt_data_type:
                adapt_data_type = hasattr(f.type, _FIELDS)
            if adapt_data_type and isinstance(value, dict):
                self[f.key] = f.type(value)

    def field_items(self) -> Iterable[Tuple[str, Any]]:
        """
        iter of defined field values
        """
        fields = getattr(type(self), _FIELDS, {})
        for name, field in fields.items():
            if field.key in self:
                yield name, self[field.key]

    @staticmethod
    def _iter_field_items_only() -> bool:
        """
        determine output of method items(): if `True`, same as field_items(); else same as dict.items()
        """
        return False

    def items(self) -> Iterable[Tuple[str, Any]]:
        if self._iter_field_items_only():
            return self.field_items()
        return super().items()


