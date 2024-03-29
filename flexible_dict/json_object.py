# -*- coding: utf-8 -*-

"""
extend dict for flexibility
"""

# Same code is copied from dataclasses.

from typing import (
    Any, Callable, Dict, Tuple,
    Iterable, List, Union,
)
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
import sys
import re
import dataclasses
import types
from .adapter import (
    _ENCODER_TYPE, _DECODER_TYPE,
    get_encoder_func,
    get_decoder_func,
    AdapterDetector,
)

# A sentinel object to detect if a parameter is supplied or not.  Use
# a class to give it a better repr.
class _MISSING_TYPE:
    pass
MISSING = _MISSING_TYPE()

# Markers for the various kinds of fields and pseudo-fields.
class _FIELD_BASE:
    def __init__(self, name):
        self.name = name
    def __repr__(self):
        return self.name
_FIELD_DICTKEY = _FIELD_BASE('_FIELD_DICTKEY')
_FIELD_CLASSVAR = _FIELD_BASE('_FIELD_CLASSVAR')
_FIELD_OBJECTVAR = _FIELD_BASE('_FIELD_OBJECTVAR')

# The name of an attribute on the class where we store the Field
# objects.  Also used to check if a class is a json_object class.
_FIELDS = '__json_object_fields__'

# String regex that string annotations for ClassVar or InitVar must match.
# Allows "identifier.identifier[" or "identifier[".
# https://bugs.python.org/issue33453 for details.
_MODULE_IDENTIFIER_RE = re.compile(r'^(?:\s*(\w+)\s*\.)?\s*(\w+)')

class ObjectVar:
    __slots__ = ('type', )
    def __init__(self, type):
        self.type = type
    def __repr__(self):
        is_type = isinstance(self.type, type)
        if is_type and sys.version_info >= (3, 9):
            is_type = not isinstance(self.type, types.GenericAlias)
        if is_type:
            type_name = self.type.__name__
        else:
            # typing objects, e.g. List[int]
            type_name = repr(self.type)
        return f'flexible_dict.ObjectVar[{type_name}]'
    def __class_getitem__(cls, type):
        return ObjectVar(type)

@dataclasses.dataclass
class Field:
    # the key stored in the dict; same as name if set as MISSING
    key: str = MISSING

    # access control
    readable: bool = True
    writeable: bool = True
    deletable: bool = True

    # default value setting
    default: Any = None     # default value when the key not exists
    default_factory: Callable[[dict], Any] = MISSING     # a function to get a value from the dict

    # decide what scope the field belong to
    static: bool = False    # a class property
    exclude: bool = False   # exclude from dict key and mark as object property

    # # if set as false, an exception will be raised when the key not exists
    check_exist_before_delete: bool = True

    # functions to cast value type when write or read dict
    encoder: Union[_ENCODER_TYPE, Literal['auto'], None] = 'auto'    # cast value type when write to dict
    decoder: Union[_DECODER_TYPE, None] = 'auto'    # cast value type when read from dict

    # auto detect value
    name: str = None
    type: type = None
    _field_type: _FIELD_BASE = _FIELD_DICTKEY

    # additional metadata
    metadata: Dict[Any, Any] = dataclasses.field(default_factory=dict)

class JsonObjectClassProcessor(object):
    """
    parse flexible_dict class, set property and function
    """
    def __init__(self, default_field_value=None, adapter_detector: AdapterDetector = None):
        """
        :param default_field_value:     default value config on the class for field without init value
        :param adapter_detector:        auto set encoder and decoder for field
        """
        self.default_field_value = default_field_value
        self.adapter_detector = adapter_detector or AdapterDetector()

    @staticmethod
    def is_missing(value: Any) -> bool:
        return value is MISSING

    @staticmethod
    def _is_classvar(a_type, typing):
        return dataclasses._is_classvar(a_type, typing)

    @staticmethod
    def _is_objectvar(a_type, module):
        # The module we're checking against is the module we're currently in.
        return (a_type is module.ObjectVar or type(a_type) is module.ObjectVar)

    @staticmethod
    def _is_type(annotation, cls, a_module, a_type, is_type_predicate):
        return dataclasses._is_type(annotation, cls, a_module, a_type, is_type_predicate)

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

        # Assume it's a normal field until proven otherwise.  We're next
        # going to decide if it's a ClassVar or InitVar, everything else
        # is just a normal field.
        f._field_type = _FIELD_DICTKEY

        # In addition to checking for actual types here, also check for
        # string annotations.  get_type_hints() won't always work for us
        # (see https://github.com/python/typing/issues/508 for example),
        # plus it's expensive and would require an eval for every string
        # annotation.  So, make a best effort to see if this is a ClassVar
        # or InitVar using regex's and checking that the thing referenced
        # is actually of the correct type.

        # For the complete discussion, see https://bugs.python.org/issue33453

        # If typing has not been imported, then it's impossible for any
        # annotation to be a ClassVar.  So, only look for ClassVar if
        # typing has been imported by any module (not necessarily cls's
        # module).
        typing = sys.modules.get('typing')
        if typing:
            if (self._is_classvar(a_type, typing)
                    or (isinstance(f.type, str)
                        and self._is_type(f.type, cls, typing, typing.ClassVar, self._is_classvar))):
                f._field_type = _FIELD_CLASSVAR

        # If the type is ObjectVar, or if it's a matching string annotation,
        # then it's an ObjectVar.
        if f._field_type is _FIELD_DICTKEY:
            # The module we're checking against is the module we're currently in.
            module = sys.modules[__name__]
            if (self._is_objectvar(a_type, module)
                    or (isinstance(f.type, str)
                        and self._is_type(f.type, cls, dataclasses, dataclasses.InitVar, self._is_objectvar))):
                f._field_type = _FIELD_OBJECTVAR

        # Validations for individual fields.  This is delayed until now,
        # instead of in the Field() constructor, since only here do we
        # know the field name, which allows for better error reporting.

        # Special restrictions for ClassVar.
        if f._field_type is _FIELD_CLASSVAR:
            if not self.is_missing(f.default_factory):
                raise TypeError(f'field {f.name} cannot have a default factory')
            # Should I check for other field settings? default_factory
            # seems the most serious to check for.  Maybe add others.  For
            # example, how about init=False (or really,
            # init=<not-the-default-init-value>)?  It makes no sense for
            # ClassVar and InitVar to specify init=<anything>.

        # For real fields, disallow mutable defaults for known types.
        if (f._field_type in (_FIELD_DICTKEY, _FIELD_OBJECTVAR)
                and isinstance(f.default, (list, dict, set))):
            raise ValueError(f'mutable default {type(f.default)} for field '
                             f'{f.name} is not allowed: use default_factory')

        # Set value if f is ClassVar or ObjectVar.
        if f._field_type is _FIELD_CLASSVAR:
            f.static = True
        if f._field_type is _FIELD_OBJECTVAR:
            f.exclude = True

        # if encoder/decoder set auto, detect whether an encoder/decoder is needed
        if f.encoder == 'auto':
            f.encoder = self.adapter_detector.detect_encoder(f.type)
        if f.decoder == 'auto':
            f.decoder = self.adapter_detector.detect_decoder(f.type)

        # in case some classes are both encoder and decoder,
        # and method __call__ not set properly,
        # specify encoder or decoder as the exact function
        if f.encoder:
            f.encoder = get_encoder_func(f.encoder)
        if f.decoder:
            f.decoder = get_decoder_func(f.decoder)

        return f

    def build_getter(self, field: Field) -> Callable[[dict], Any]:
        if not self.is_missing(field.default):
            if callable(field.decoder):
                def getter(d):
                    if field.key in d:
                        return field.decoder(d[field.key])
                    return field.default
            else:
                def getter(d):
                    return d.get(field.key, field.default)
        elif not self.is_missing(field.default_factory):
            if callable(field.decoder):
                def getter(d):
                    if field.key in d:
                        return field.decoder(d[field.key])
                    return field.default_factory(d)
            else:
                def getter(d):
                    if field.key in d:
                        return d[field.key]
                    return field.default_factory(d)
        else:
            if callable(field.decoder):
                def getter(d):
                    return field.decoder(d[field.key])
            else:
                def getter(d):
                    return d[field.key]
        return getter

    def build_setter(self, field: Field) -> Callable[[dict, Any], Any]:
        if callable(field.encoder):
            def setter(d, value):
                d[field.key] = field.encoder(value)
        else:
            def setter(d, value):
                d[field.key] = value
        return setter

    def build_deleter(self, field: Field) -> Callable[[dict], Any]:
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

    def add_base(self, cls: type):
        """
        add dict as base if cls is not a subclass of dict
        """
        if not issubclass(cls, dict):
            d = dict(cls.__dict__)
            d.pop('__dict__')
            bases = tuple(b for b in cls.__bases__ if b != object) + (dict,)
            cls = type(cls.__name__, bases, d)
        return cls

    def process_fields(self, cls: type):
        """
        process fields in annotations as property
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
                if self.is_missing(field.default) and self.is_missing(field.default_factory):
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
        # also marks this class as being a json_object.
        setattr(cls, _FIELDS, fields)

    def add_class_methods(self, cls: type):
        """
        add some class methods
        """

    def process_class(self, cls: type) -> type:
        """
        entry point to process a class as json object
        """
        # first, ensure the class be a subclass of dict
        cls = self.add_base(cls)

        # then, process fields to access them in a flexible way
        self.process_fields(cls)

        # finally, add some flexible methods
        self.add_class_methods(cls)

        return cls

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
            if callable(f.encoder):
                value = self.get(f.key)
                self[f.key] = f.encoder(value)

    def field_items(self) -> Iterable[Tuple[str, Any]]:
        """
        iter of defined field values
        """
        # one should not define a field use the reserved name
        fields = getattr(self, _FIELDS, {})
        for name, field in fields.items():
            if field.key in self:
                yield name, self[field.key]

    @property
    def _iter_field_items_only(self) -> bool:
        """
        determine output of method items(): if `True`, same as field_items(); else same as dict.items()
        """
        return False

    def items(self) -> Iterable[Tuple[str, Any]]:
        if self._iter_field_items_only:
            return self.field_items()
        return super().items()

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'JsonObject':
        """
        This method can be overwritten for custom use.
        """
        return cls(d)

    @classmethod
    def from_list(cls, li: List[Dict[str, Any]]) -> List['JsonObject']:
        return [cls.from_dict(x) for x in li]
