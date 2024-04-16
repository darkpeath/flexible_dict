# -*- coding: utf-8 -*-

"""
extend dict for flexibility
"""

# Same code is copied from dataclasses.

from typing import (
    Any, Callable, Dict, Tuple,
    Iterable, List, Union,
    Optional, Type,
)
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
import sys
import re
import types
import builtins
import warnings
import dataclasses
from .adapter import (
    _ENCODER_TYPE, _DECODER_TYPE,
    get_encoder_func,
    get_decoder_func,
    AdapterDetector,
)

# A sentinel object for default values to signal that a default
# factory will be used.  This is given a nice repr() which will appear
# in the function signature of dataclasses' constructors.
class _HAS_DEFAULT_FACTORY_CLASS:
    def __repr__(self):
        return '<factory>'
_HAS_DEFAULT_FACTORY = _HAS_DEFAULT_FACTORY_CLASS()

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
_FIELD_INITVAR = _FIELD_BASE('_FIELD_INITVAR')

# The name of an attribute on the class where we store the Field
# objects.  Also used to check if a class is a json_object class.
_FIELDS = '__json_object_fields__'

# The name of the function, that if it exists, is called at the end of
# __init__.
_POST_INIT_NAME = '__post_init__'

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
    type: Any = None
    _field_type: _FIELD_BASE = _FIELD_DICTKEY

    # additional metadata
    metadata: Dict[Any, Any] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class ProcessorConfig:
    # default value config on the class for field without init value
    default_field_value: Any = None

    # auto set encoder and decoder for field
    adapter_detector: AdapterDetector = dataclasses.field(default_factory=AdapterDetector)

    # whether to create a new __init__ function
    create_init_func: bool = True

    # whether to create a function to iter all field values
    create_iter_func: bool = True

    # method name for field iter;
    # name can be 'items' therefor supper method wound be overwritten.
    iter_func_name: str = 'field_items'

    # ignore not exists field for the new field iter function
    ignore_not_exists_filed_when_iter: bool = False

DEFAULT_CONFIG = ProcessorConfig()

class JsonObjectClassProcessor(object):
    """
    parse flexible_dict class, set property and function
    """
    def __init__(self, config=DEFAULT_CONFIG, cls=None):
        self.config = config
        self.cls = cls
        self.fields = {}
        self.globals = {}
        if cls is not None:
            self._reset(cls)

    def _reset(self, cls):
        self.cls = cls
        self.fields = {}
        if cls.__module__ in sys.modules:
            self.globals = sys.modules[cls.__module__].__dict__
        else:
            # Theoretically this can happen if someone writes
            # a custom string to cls.__module__.  In which case
            # such dataclass won't be fully introspectable
            # (w.r.t. typing.get_type_hints) but will still function
            # correctly.
            self.globals = {}

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
        default = getattr(cls, a_name, self.config.default_field_value)
        if isinstance(default, Field):
            f = default
        else:
            if isinstance(default, types.MemberDescriptorType):
                # This is a field in __slots__, so it has no default value.
                default = self.config.default_field_value
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
            f.encoder = self.config.adapter_detector.detect_encoder(f.type)
        if f.decoder == 'auto':
            f.decoder = self.config.adapter_detector.detect_decoder(f.type)

        # in case some classes are both encoder and decoder,
        # and method __call__ not set properly,
        # specify encoder or decoder as the exact function
        if f.encoder:
            f.encoder = get_encoder_func(f.encoder)
        if f.decoder:
            f.decoder = get_decoder_func(f.decoder)

        return f

    @staticmethod
    def _set_new_attribute(cls, name, value):
        # Never overwrites an existing attribute.  Returns True if the
        # attribute already exists.
        if name in cls.__dict__:
            return True
        setattr(cls, name, value)
        return False

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

    def add_base(self):
        """
        add dict as base if cls is not a subclass of dict
        """
        cls = self.cls
        if not issubclass(cls, dict):
            d = dict(cls.__dict__)
            d.pop('__dict__')
            bases = tuple(b for b in cls.__bases__ if b != object) + (dict,)
            cls = type(cls.__name__, bases, d)
        self.cls = cls
        return cls

    def process_fields(self):
        """
        process fields in annotations as property
        """
        cls = self.cls

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

        self.fields = fields

    @staticmethod
    def _create_fn(name: str, args: List[str], body: List[str], *,
                   _globals: Dict[str, Any] = None,
                   _locals: Dict[str, Any] = None,
                   return_type: Optional[Type] = MISSING):
        # Note that we mutate locals when exec() is called.  Caller
        # beware!  The only callers are internal to this module, so no
        # worries about external callers.
        if _locals is None:
            _locals = {}
        if 'BUILTINS' not in _locals:
            _locals['BUILTINS'] = builtins
        return_annotation = ''
        if return_type is not MISSING:
            _locals['_return_type'] = return_type
            return_annotation = '->_return_type'
        args = ','.join(args)
        body = '\n'.join(f'  {b}' for b in body)

        # Compute the text of the entire function.
        txt = f' def {name}({args}){return_annotation}:\n{body}'

        local_vars = ', '.join(_locals.keys())
        txt = f"def __create_fn__({local_vars}):\n{txt}\n return {name}"

        ns = {}
        exec(txt, _globals, ns)
        return ns['__create_fn__'](**_locals)

    @staticmethod
    def _field_assign(frozen, name, value, self_name):
        # If we're a frozen class, then assign to our fields in __init__
        # via object.__setattr__.  Otherwise, just use a simple
        # assignment.
        #
        # self_name is what "self" is called in this function: don't
        # hard-code "self", since that might be a field name.
        if frozen:
            return f'BUILTINS.object.__setattr__({self_name},{name!r},{value})'
        return f'{self_name}.{name}={value}'

    def _init_fn(self, fields: List[Field], self_name: str, d_name='_', ds_name='__', kwargs_name='___'):
        # fields contains both real fields and InitVar pseudo-fields.

        locals: dict = {
            'MISSING': MISSING,
            'dict': dict,
        }
        locals.update((f'_type_{f.name}', f.type) for f in fields)
        locals.update((f'_key_{f.name}', f.key) for f in fields)

        # all args
        args = [self_name, f'*{ds_name}:dict'] + [f'{f.name}:_type_{f.name}=MISSING' for f in fields]
        if kwargs_name:
            args.append(f'**{kwargs_name}')

        # update by given dicts
        body_lines = [
            f"for {d_name} in {ds_name}:",
            f" {self_name}.update({d_name})",
        ]

        # update by kwargs
        if kwargs_name:
            body_lines.append(f"{self_name}.update({kwargs_name})")

        # update by name
        for f in fields:
            if f._field_type is _FIELD_DICTKEY:
                # value stored in dict would be correctly encoded by setting with `.`
                body_lines.extend([
                    f"if {f.name} is not MISSING:",
                    f" {self_name}.{f.name} = {f.name}",
                    f"elif _key_{f.name} in {self_name}:",
                    f" {self_name}.{f.name} = {self_name}[_key_{f.name}]"
                ])
            elif f._field_type is _FIELD_CLASSVAR:
                body_lines.extend([
                    f"if {f.name} is not MISSING:",
                    f" {self_name}.{f.name} = {f.name}",
                ])

        # body lines would not be empty
        # If no body lines, use 'pass'.
        # if not body_lines:
        #     body_lines = ['pass']

        return self._create_fn('__init__', args, body_lines,
                               _locals=locals, _globals=self.globals, return_type=None)

    def add_init_func(self):
        """
        add __init__ function
        """
        # Include InitVars and regular fields (so, not ClassVars).
        allowed_field_types = (
            _FIELD_DICTKEY,
            _FIELD_OBJECTVAR,
            _FIELD_INITVAR,
        )
        fields = [f for f in self.fields.values() if f._field_type in allowed_field_types]
        self._set_new_attribute(self.cls, '__init__', self._init_fn(
            fields,
            'self',
            '_',
            '__',
            '___',
        ))

    def _iter_fields_fn(self, fields: List[Field], func_name: str, self_name: str):
        _locals = {
            f'_name_{f.name}': f.name
            for f in fields
        }
        _locals.update((f'_key_{f.name}', f.key) for f in fields)

        args = [self_name]
        return_type = Iterable[Tuple[str, Any]]

        body_lines = []

        # update by name
        for f in fields:
            if f._field_type is _FIELD_DICTKEY:
                if self.config.ignore_not_exists_filed_when_iter:
                    body_lines.extend([
                        f"if _key_{f.name} in {self_name}:",
                        f" yield (_name_{f.name}, {self_name}.{f.name})",
                    ])
                else:
                    body_lines.extend([
                        f"try:",
                        f" yield (_name_{f.name}, {self_name}.{f.name})",
                        f"except:"
                        f" pass"
                    ])

        # If no body lines, return empty tuple.
        if not body_lines:
            body_lines = ['return ()']

        return self._create_fn(func_name, args, body_lines,
                               _locals=_locals, _globals=self.globals,
                               return_type=return_type)

    def add_iter_fields_func(self):
        # Include only field for dict key
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        func_name = self.config.iter_func_name
        self._set_new_attribute(self.cls, func_name, self._iter_fields_fn(
            fields,
            func_name,
            'self',
        ))

    def add_class_methods(self):
        """
        add some class methods
        """
        if self.config.create_init_func:
            self.add_init_func()

        if self.config.create_iter_func:
            self.add_iter_fields_func()
            # TODO 2024/4/16  if function name is `items`, overwrite method `keys()` and method `values()`

    def _process(self):
        """
        process pipeline
        """
        if self.cls is None:
            raise ValueError("Class not given.")

        # first, ensure the class be a subclass of dict
        self.add_base()

        # then, process fields to access them in a flexible way
        self.process_fields()

        # finally, add some flexible methods
        self.add_class_methods()

    def __call__(self, cls: type = None) -> Type[dict]:
        if cls is not None:
            self._reset(cls)
        self._process()
        return self.cls

def json_object(_cls=None, processor=JsonObjectClassProcessor, config=None,
                default_field_value=None, adapter_detector: AdapterDetector = None,
                create_init_func=True, create_iter_func=True, iter_func_name='field_items',
                **kwargs):
    """
    a decorator to mark a class as json format
    """
    if config is None:
        config = ProcessorConfig(
            default_field_value=default_field_value,
            adapter_detector=adapter_detector or AdapterDetector(),
            create_init_func=create_init_func,
            create_iter_func=create_iter_func,
            iter_func_name=iter_func_name,
            **kwargs
        )

    def wrap(cls):
        if cls is None:
            # without this line, pycharm code hints would disappear.
            return cls
        return processor(config)(cls)

    # See if we're being called as @json_object or @json_object().
    if _cls is None:
        # We're called with parens.
        return wrap

    # We're called as @json_object without parens.
    return wrap(_cls)

# Another way to define a json_object class, just inherit this class.
class JsonObject(dict):
    def __init_subclass__(cls):
        warnings.warn("Use decorator `json_object()` instead", DeprecationWarning)
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
