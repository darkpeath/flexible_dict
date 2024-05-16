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
import types
import builtins
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

# The name of an attribute on the class where we store the Field
# objects.  Also used to check if a class is a json_object class.
_FIELDS = '__json_object_fields__'

@dataclasses.dataclass
class Field:
    # the key stored in the dict; same as name if set as MISSING
    key: str = MISSING

    # access control
    readable: bool = True
    writeable: bool = True
    deletable: bool = True

    # default value when init the dict
    init_default: Any = MISSING
    # a function to build default value when init the dict
    init_default_factory: Callable[[], Any] = MISSING

    # default value when access an absent key
    getter_default: Any = MISSING
    # a function to build default value when access an absent key
    getter_default_factory0: Callable[[], Any] = MISSING
    # a function to get value for the dict when access an absent key
    getter_default_factory1: Callable[[dict], Any] = MISSING
    
    # functions to cast value type when write or read dict
    encoder: Union[_ENCODER_TYPE, Literal['auto'], None] = 'auto'    # cast value type when write to dict
    decoder: Union[_DECODER_TYPE, None] = 'auto'    # cast value type when read from dict

    # if set as false, an exception will be raised when the key not exists
    check_exist_before_delete: bool = True

    # auto detect value
    name: str = dataclasses.field(init=False, default=None)
    type: Any = dataclasses.field(init=False, default=None)
    _field_type: _FIELD_BASE = dataclasses.field(init=False, default=_FIELD_DICTKEY)

    # additional metadata
    metadata: Dict[Any, Any] = dataclasses.field(default_factory=dict)

class DefaultScope:
    GETTER = 1
    INIT = 2

@dataclasses.dataclass
class ProcessorConfig:
    # default value when access an absent key in class scope
    getter_default: Any = MISSING

    # if set a default value but not a field, determine which scope should the value be used
    # scope can be getter or init, and can all set active
    default_scopes: int = DefaultScope.GETTER

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

    def _create_fn(self, name: str, args: List[str], body: List[str], *,
                   _globals: Dict[str, Any] = None,
                   _locals: Dict[str, Any] = None,
                   return_type: Optional[Type] = MISSING):
        _globals = _globals or self.globals or {}

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
    def is_missing(value: Any) -> bool:
        return value is MISSING

    @staticmethod
    def _is_classvar(a_type, typing):
        return dataclasses._is_classvar(a_type, typing)

    @staticmethod
    def _is_type(annotation, cls, a_module, a_type, is_type_predicate):
        return dataclasses._is_type(annotation, cls, a_module, a_type, is_type_predicate)

    def get_field(self, cls, a_name, a_type) -> Field:
        """
        Return a Field object for this field name and type.
        """
        # If the default value isn't derived from Field, then it's only a
        # normal default value.  Convert it to a Field().
        default = getattr(cls, a_name, MISSING)
        if isinstance(default, Field):
            f = default
        else:
            if isinstance(default, types.MemberDescriptorType):
                # This is a field in __slots__, so it has no default value.
                default = MISSING
            getter_default = init_default = MISSING
            if self.config.default_scopes & DefaultScope.GETTER:
                getter_default = default
            if self.config.default_scopes & DefaultScope.INIT:
                init_default = default
            f = Field(init_default=init_default, getter_default=getter_default)

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

        # Validations for individual fields.  This is delayed until now,
        # instead of in the Field() constructor, since only here do we
        # know the field name, which allows for better error reporting.

        # Special restrictions for ClassVar.
        if f._field_type is _FIELD_CLASSVAR:
            if not self.is_missing(f.init_default_factory):
                raise TypeError(f'field {f.name} cannot have a default factory')
            # Should I check for other field settings? default_factory
            # seems the most serious to check for.  Maybe add others.  For
            # example, how about init=False (or really,
            # init=<not-the-default-init-value>)?  It makes no sense for
            # ClassVar and InitVar to specify init=<anything>.

        # For real fields, disallow mutable defaults for known types.
        if f._field_type is _FIELD_DICTKEY:
            if isinstance(f.getter_default, (list, dict, set)):
                raise ValueError(f'mutable getter_default {type(f.getter_default)} for field '
                                 f'{f.name} is not allowed: use getter_default_factory0 or getter_default_factory1')
            if isinstance(f.init_default, (list, dict, set)):
                raise ValueError(f'mutable init_default {type(f.init_default)} for field '
                                 f'{f.name} is not allowed: use init_default_factory')

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

    def build_getter(self, field: Field, *, method_name='getter', var_dict='_d', var_key='_key',
                     var_decoder='_decoder', var_default='_default') -> Callable[[dict], Any]:
        _locals: dict = {
            var_key: field.key,
        }

        should_decode = callable(field.decoder)
        if should_decode:
            _locals[var_decoder] = field.decoder

        if field.getter_default is not MISSING:
            default_type, default_value = 0, field.getter_default
        elif field.getter_default_factory0 is not MISSING:
            default_type, default_value = 1, field.getter_default_factory0
        elif field.getter_default_factory1 is not MISSING:
            default_type, default_value = 2, field.getter_default_factory1
        elif self.config.getter_default is not MISSING:
            default_type, default_value = 0, self.config.getter_default
        else:
            default_type, default_value = -2, None

        def gen_body_lines() -> List[str]:
            if default_type == -2:
                # if no default defined, just get key value and decode
                if should_decode:
                    return [f"return {var_decoder}({var_dict}[{var_key}])"]
                return [f"return {var_dict}[{var_key}]"]
            lines = [f"if {var_key} in {var_dict}:"]
            if should_decode:
                lines.append(f" return {var_decoder}({var_dict}[{var_key}])")
            else:
                lines.append(f" return {var_dict}[{var_key}]")
            _locals[var_default] = default_value
            if default_type == 0:
                lines.append(f"return {var_default}")
            elif default_type == 1:
                lines.append(f"return {var_default}()")
            else:
                assert default_type == 2
                lines.append(f"return {var_default}({var_dict})")
            return lines

        body_lines = gen_body_lines()

        return self._create_fn(method_name, [var_dict], body_lines, _locals=_locals)

    def build_setter(self, field: Field, *, method_name='setter', var_dict='_d', var_value='_value',
                     var_key='_key', var_encoder='_encoder') -> Callable[[dict, Any], Any]:
        _locals: dict = {
            var_key: field.key,
        }

        should_encode = callable(field.encoder)
        if should_encode:
            _locals[var_encoder] = field.encoder

        if should_encode:
            body_lines = [f"{var_dict}[{var_key}] = {var_encoder}({var_value})"]
        else:
            body_lines = [f"{var_dict}[{var_key}] = {var_value}"]

        return self._create_fn(method_name, [var_dict, var_value], body_lines, _locals=_locals)

    def build_deleter(self, field: Field, *, method_name='deleter', var_dict='_d',
                      var_key='_key') -> Callable[[dict], Any]:
        _locals: dict = {
            var_key: field.key,
        }

        if field.check_exist_before_delete:
            body_lines = [
                f"if {var_key} in {var_dict}:",
                f" {var_dict}.pop({var_key})",
            ]
        else:
            body_lines = [
                f"{var_dict}.pop({var_key})",
            ]

        return self._create_fn(method_name, [var_dict], body_lines, _locals=_locals)

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
            if field._field_type is _FIELD_CLASSVAR:
                # It's not suggested to define a class field like `a: ClassVar[int] = Field(init_default=1)`.
                # better to define like `a: ClassVar[int] = 1`.
                # But deal field here just in case.
                if isinstance(getattr(cls, field.name, None), Field):
                    if self.is_missing(field.init_default):
                        delattr(cls, name)
                    else:
                        setattr(cls, name, field.init_default)
            else:
                if name in cls.__dict__:
                    delattr(cls, name)
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

    def _init_fn(self, fields: List[Field], self_name: str, d_name='_', ds_name='__',
                 k_name='__k', v_name='__v', kwargs_name='___'):
        _locals: dict = {
            'MISSING': MISSING,
            'dict': dict,
        }
        _locals.update((f'_type_{f.name}', f.type) for f in fields)
        _locals.update((f'_key_{f.name}', f.key) for f in fields)

        # all args
        args = [self_name, f'*{ds_name}:dict'] + [f'{f.name}:_type_{f.name}=MISSING' for f in fields]
        if kwargs_name:
            args.append(f'**{kwargs_name}')

        body_lines = []

        # update by given dicts, value would be encoded since it's set before walking fields
        body_lines.extend([
            f"for {d_name} in {ds_name}:",
            f" {self_name}.update({d_name})",
        ])

        # walk fields to update and encode
        for f in fields:
            if f._field_type is _FIELD_DICTKEY:
                should_encode = callable(f.encoder)
                if should_encode:
                    _locals[f'_encoder_{f.name}'] = f.encoder

                # value stored in dict would be correctly encoded by setting with `.`

                # if value given, stored in the dict
                body_lines.append(f"if {f.name} is not MISSING:")
                if should_encode:
                    body_lines.append(f" {f.name} = _encoder_{f.name}({f.name})")
                body_lines.append(f" {self_name}[_key_{f.name}] = {f.name}")

                # if value not given but key already in the dict, that means the values is passed in a dict
                # encode the value if necessary
                if should_encode:
                    body_lines.append(f"elif _key_{f.name} in {self_name}:")
                    body_lines.append(f" {self_name}[_key_{f.name}] = _encoder_{f.name}({self_name}[_key_{f.name}])")
                    
                # set default value
                if not self.is_missing(f.init_default):
                    _locals[f'_default_{f.name}'] = f.init_default
                    body_lines.extend([
                        f"else:",
                        f" {self_name}[_key_{f.name}] = _default_{f.name}",
                    ])
                elif not self.is_missing(f.init_default_factory):
                    _locals[f'_default_{f.name}'] = f.init_default_factory
                    body_lines.extend([
                        f"else:",
                        f" {self_name}[_key_{f.name}] = _default_{f.name}()"
                    ])
            elif f._field_type is _FIELD_CLASSVAR:
                body_lines.extend([
                    f"if {f.name} is not MISSING:",
                    f" {self_name}.{f.name} = {f.name}",
                ])

        # update by kwargs, value would not be encoded since it's set after walking fields
        if kwargs_name:
            body_lines.append(f"{self_name}.update({kwargs_name})")

        return self._create_fn('__init__', args, body_lines, _locals=_locals)

    def add_init_func(self):
        """
        add __init__ function
        """
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        self._set_new_attribute(self.cls, '__init__', self._init_fn(
            fields,
            'self',
            '_',
            '__',
            '___',
        ))

    def _iter_field_items_fn(self, fields: List[Field], func_name: str, self_name: str, res_name='res'):
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

        return self._create_fn(func_name, args, body_lines, _locals=_locals, return_type=return_type)

    def _iter_field_keys_fn(self, func_name: str, self_name: str, k_name='k', v_name='v'):
        args = [self_name]
        return_type = Iterable[str]

        body_lines = [
            f"for {k_name}, {v_name} in {self_name}.{self.config.iter_func_name}:",
            f" yield {k_name}"
        ]

        return self._create_fn(func_name, args, body_lines, return_type=return_type)

    def _iter_field_values_fn(self, func_name: str, self_name: str, k_name='k', v_name='v'):
        args = [self_name]
        return_type = Iterable[str]

        body_lines = [
            f"for {k_name}, {v_name} in {self_name}.{self.config.iter_func_name}:",
            f" yield {v_name}"
        ]

        return self._create_fn(func_name, args, body_lines, return_type=return_type)

    def add_iter_fields_func(self):
        # Include only field for dict key
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        func_name = self.config.iter_func_name
        self._set_new_attribute(self.cls, func_name, self._iter_field_items_fn(
            fields,
            func_name,
            'self',
        ))

        # if function name is `items`, overwrite method `keys()` and method `values()`
        if func_name == 'items':
            self._set_new_attribute(self.cls, 'keys', self._iter_field_keys_fn('keys', 'self'))
            self._set_new_attribute(self.cls, 'values', self._iter_field_values_fn('values', 'self'))

    def _getattr_fn(self, fields: List[Field], self_name='self', item_name='item', funcs_name='funcs'):
        funcs = {f.name: self.build_getter(f) for f in fields}
        _locals = {
            funcs_name: funcs,
            'AttributeError': AttributeError,
        }
        args = [self_name, item_name]
        body_lines = [
            f"if {item_name} in {funcs_name}:",
            f" return {funcs_name}[{item_name}]({self_name})",
            f"raise AttributeError()",
        ]
        return self._create_fn('__getattr__', args, body_lines, _locals=_locals)

    def add_getattr_func(self):
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        self._set_new_attribute(self.cls, '__getattr__', self._getattr_fn(fields))

    def _getattribute_fn(self, fields: List[Field], self_name='self', item_name='item', funcs_name='funcs'):
        funcs = {f.name: self.build_getter(f) for f in fields}
        _locals = {
            funcs_name: funcs,
        }
        args = [self_name, item_name]
        body_lines = [
            f"if {item_name} in {funcs_name}:",
            f" return {funcs_name}[{item_name}]({self_name})",
            f"return super(object, {self_name}).__getattribute__({item_name})",
        ]
        return self._create_fn('__getattribute__', args, body_lines, _locals=_locals)

    def add_getattribute_func(self):
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        self._set_new_attribute(self.cls, '__getattribute__', self._getattribute_fn(fields))

    def _setattr_fn(self, fields: List[Field], self_name='self', key_name='key',
                    value_name='value', funcs_name='funcs'):
        funcs = {f.name: self.build_setter(f) for f in fields}
        _locals = {
            funcs_name: funcs,
        }
        args = [self_name, key_name, value_name]
        body_lines = [
            f"if {key_name} in {funcs_name}:",
            f" {funcs_name}[{key_name}]({self_name}, {key_name}, {value_name})",
            f"return super().__setattr__({key_name}, {value_name})",
        ]
        return self._create_fn('__setattr__', args, body_lines, _locals=_locals)

    def add_setattr_func(self):
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        self._set_new_attribute(self.cls, '__setattr__', self._setattr_fn(fields))

    def _delattr_fn(self, fields: List[Field], self_name='self', item_name='item', funcs_name='funcs'):
        funcs = {f.name: self.build_deleter(f) for f in fields}
        _locals = {
            funcs_name: funcs,
        }
        args = [self_name, item_name]
        body_lines = [
            f"if {item_name} in {funcs_name}:",
            f" return {funcs_name}[{item_name}]({self_name}, {item_name})",
            f"return super().__delattr__({item_name})",
        ]
        return self._create_fn('__delattr__', args, body_lines, _locals=_locals)

    def add_delattr_func(self):
        fields = [f for f in self.fields.values() if f._field_type is _FIELD_DICTKEY]
        self._set_new_attribute(self.cls, '__delattr__', self._delattr_fn(fields))

    def add_class_methods(self):
        """
        add some class methods
        """
        self.add_getattr_func()
        # self.add_getattribute_func()
        self.add_setattr_func()
        self.add_delattr_func()

        if self.config.create_init_func:
            self.add_init_func()

        if self.config.create_iter_func:
            self.add_iter_fields_func()

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

def json_object(_cls=None, processor=JsonObjectClassProcessor, *, config=None,
                getter_default=None, adapter_detector: AdapterDetector = None,
                create_init_func=True, create_iter_func=True, iter_func_name='field_items',
                **kwargs):
    """
    a decorator to mark a class as json format
    """
    if config is None:
        config = ProcessorConfig(
            getter_default=getter_default,
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

