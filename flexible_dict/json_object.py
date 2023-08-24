# -*- coding: utf-8 -*-

# Same code is copied from dataclasses.
# Code of dataclasses is pretty.

from typing import Any, Callable, Dict, Tuple, Iterable, List
try:
    from types import GenericAlias
except ImportError:
    try:
        from types import _GenericAlias as GenericAlias
    except ImportError:
        from typing import GenericMeta as GenericAlias
import sys
import re
import warnings
import dataclasses
import types

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
        if isinstance(self.type, type) and not isinstance(self.type, GenericAlias):
            type_name = self.type.__name__
        else:
            # typing objects, e.g. List[int]
            type_name = repr(self.type)
        return f'flexible_dict.ObjectVar[{type_name}]'
    def __class_getitem__(cls, type):
        return ObjectVar(type)

@dataclasses.dataclass
class Field:
    key: str = MISSING     # the key stored in the dict; same as name if set as MISSING
    readable: bool = True
    writeable: bool = True
    deletable: bool = True
    default: Any = None     # default value when the key not exists
    default_factory: Callable[[dict], Any] = MISSING     # a function to get a value from the dict
    static: bool = False    # a class property
    exclude: bool = False   # exclude from dict key and mark as object property
    check_exist_before_delete: bool = True  # if set as false, an exception will be raised when the key not exists
    adapt_data_type: bool = None    # whether adapt data value as specified type; determined by the tool if set None
    name: str = None
    type: type = None
    _field_type: _FIELD_BASE = _FIELD_DICTKEY
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

    @staticmethod
    def _is_classvar(a_type, typing):
        # This test uses a typing internal class, but it's the best way to
        # test if this is a ClassVar.
        return (a_type is typing.ClassVar
                or (type(a_type) is GenericAlias
                    and a_type.__origin__ is typing.ClassVar))

    @staticmethod
    def _is_objectvar(a_type, module):
        # The module we're checking against is the module we're currently in.
        return (a_type is module.ObjectVar or type(a_type) is module.ObjectVar)

    @staticmethod
    def _is_type(annotation, cls, a_module, a_type, is_type_predicate):
        # Given a type annotation string, does it refer to a_type in
        # a_module?  For example, when checking that annotation denotes a
        # ClassVar, then a_module is typing, and a_type is
        # typing.ClassVar.

        # It's possible to look up a_module given a_type, but it involves
        # looking in sys.modules (again!), and seems like a waste since
        # the caller already knows a_module.

        # - annotation is a string type annotation
        # - cls is the class that this annotation was found in
        # - a_module is the module we want to match
        # - a_type is the type in that module we want to match
        # - is_type_predicate is a function called with (obj, a_module)
        #   that determines if obj is of the desired type.

        # Since this test does not do a local namespace lookup (and
        # instead only a module (global) lookup), there are some things it
        # gets wrong.

        # With string annotations, cv0 will be detected as a ClassVar:
        #   CV = ClassVar
        #   @dataclass
        #   class C0:
        #     cv0: CV

        # But in this example cv1 will not be detected as a ClassVar:
        #   @dataclass
        #   class C1:
        #     CV = ClassVar
        #     cv1: CV

        # In C1, the code in this function (_is_type) will look up "CV" in
        # the module and not find it, so it will not consider cv1 as a
        # ClassVar.  This is a fairly obscure corner case, and the best
        # way to fix it would be to eval() the string "CV" with the
        # correct global and local namespaces.  However that would involve
        # a eval() penalty for every single field of every dataclass
        # that's defined.  It was judged not worth it.

        match = _MODULE_IDENTIFIER_RE.match(annotation)
        if match:
            ns = None
            module_name = match.group(1)
            if not module_name:
                # No module name, assume the class's module did
                # "from dataclasses import InitVar".
                ns = sys.modules.get(cls.__module__).__dict__
            else:
                # Look up module_name in the class's module.
                module = sys.modules.get(cls.__module__)
                if module and module.__dict__.get(module_name) is a_module:
                    ns = sys.modules.get(a_type.__module__).__dict__
            if ns and is_type_predicate(ns.get(match.group(2)), a_module):
                return True
        return False

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
