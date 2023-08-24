# -*- coding: utf-8 -*-

from typing import (
    List, Any, Dict, Set, Iterable,
)
try:
    from typing import Literal
except ImportError:
    from typing_extensions import Literal
import dataclasses
import collections
import json
import re
import logging

logger = logging.getLogger('__file__')

def line2camel(name: str, capitalized=False) -> str:
    if not name:
        return name
    contents = re.findall('_[a-z]+', name)
    for content in set(contents):
        name = name.replace(content, content[1:].title())
    if capitalized:
        name = name[0].upper() + name[1:]
    return name

def camel2line(name: str, upper=False) -> str:
    if not name:
        return name
    name = re.sub('(?<=[a-z])[A-Z]|(?<!^)[A-Z](?=[a-z])', '_\\g<0>', name)
    return name.upper() if upper else name.lower()

@dataclasses.dataclass
class FieldDef:
    name: str
    type: str
    key: str = None
    default: str = None

@dataclasses.dataclass
class ClassDef:
    name: str
    _fields: List[FieldDef] = dataclasses.field(init=False, default_factory=list)
    @property
    def filed_num(self) -> int:
        return len(self._fields)
    @property
    def fields(self) -> Iterable[FieldDef]:
        return self._fields
    def update_filed(self, name: str, v_type: str, key: str) -> int:
        """
        update a field definition
        :param name:    field name
        :param v_type:  value type
        :param key:     dict key
        :return:    this field index in field list
        """
        for i, filed in enumerate(self._fields):
            filed: FieldDef
            if filed.name == name:
                if key != filed.key:
                    logger.error(f"conflict key {filed.name} {filed.key} {key}")
                if filed.type != v_type:
                    logger.error(f"conflict value type {filed.name} {filed.type} {v_type}")
                return i
        self._fields.append(FieldDef(name, type=v_type, key=key))
        return len(self._fields) - 1

NAME_STYLES = Literal['upper_camel', 'lower_camel', 'upper_line', 'lower_line', 'unchanged']
NAME_FORMS = Literal['singular', 'plural', 'unchanged']

def get_literal_values(literal):
    try:
        return literal.__args__
    except AttributeError:
        return literal.__values__

@dataclasses.dataclass(init=True, repr=False, eq=False, order=False, unsafe_hash=False, frozen=False)
class ClassBuilder:
    indent: str = ' ' * 4
    dict_as_class: bool = True
    list_with_generic: bool = True
    class_name_style: NAME_STYLES = "upper_camel"
    field_name_style: NAME_STYLES = "lower_line"
    class_name_form: NAME_FORMS = "singular"
    list_filed_name_form: NAME_FORMS = "plural"

    # use `xx = Field(key='xx')` to define a field even if field name is same as key
    always_specify_key_explicitly: bool = False

    # if `True`, inherit class `JsonObject` instead of using decorator `@json_object`
    inherit_json_object_class: bool = True

    classes: Dict[str, ClassDef] = dataclasses.field(init=False, default_factory=collections.OrderedDict)
    types: Set[str] = dataclasses.field(init=False, default_factory=set)    # typing.xx which should be imported
    word_parser: Any = dataclasses.field(init=False, default=None)

    # class var
    module = "flexible_dict"
    decorator_func_name = "json_object"
    base_class_name = 'JsonObject'
    field_class_name = 'Field'

    def __post_init__(self):
        if isinstance(self.indent, int):
            self.indent = ' ' * self.indent

    def convert_word_form(self, word: str, form: Literal['singular', 'plural']) -> str:
        res = None
        if self.word_parser is None:
            import inflect
            self.word_parser = inflect.engine()
        if form == 'singular':
            res = self.word_parser.singular_noun(word)
        elif form == 'plural':
            singular = self.get_singular_word(word)
            if singular == word:
                res = self.word_parser.plural_noun(word)
        else:
            raise ValueError(f"Unexpected form: {form}")
        return res or word

    def get_plural_word(self, word: str) -> str:
        return self.convert_word_form(word, form='plural')

    def get_singular_word(self, word: str) -> str:
        if word.endswith('_list'):
            return word[-5:]
        if word.endswith('List'):
            return word[-4:]
        return self.convert_word_form(word, form='singular')

    def get_name_by_style_and_form(self, name: str, style: NAME_STYLES = 'unchanged',
                                   form: NAME_FORMS = 'unchanged') -> str:
        if form == 'singular':
            name = self.get_singular_word(name)
        elif form == 'plural':
            name = self.get_plural_word(name)
        if style == 'upper_camel':
            name = line2camel(name, capitalized=True)
        elif style == 'lower_camel':
            name = line2camel(name, capitalized=False)
            name = name[0].lower() + name[1:]
        elif style == 'upper_line':
            name = camel2line(name, upper=True)
        elif style == 'lower_line':
            name = camel2line(name, upper=False)
        return name

    def gen_field_name(self, key: str, value: Any = None) -> str:
        """
        gen field name by json key and value
        """
        name_form = 'unchanged'
        if isinstance(value, list):
            name_form = self.list_filed_name_form
        return self.get_name_by_style_and_form(key, style=self.field_name_style, form=name_form)

    def gen_class_name(self, key: str) -> str:
        """
        gen class name by json key and value
        """
        return self.get_name_by_style_and_form(key, style=self.class_name_style, form=self.class_name_form)

    def get_type(self, key: str, value: Any) -> str:
        """
        get field value type base on json value
        this method may create new classes recursively
        """
        t = type(value)
        type_name = t.__name__
        if t == dict and self.dict_as_class:
            type_name = self.gen_class_name(key)
            self.build(type_name, value)
        elif t == list and value and value[0] and self.list_with_generic:
            elem_type = self.get_type(self.get_singular_word(key), value[0])
            type_name = f"List[{elem_type}]"
            self.types.add('List')
        return type_name

    def build(self, name: str, d: dict) -> ClassDef:
        """
        build python class, walk dfs
        :param name:    class name
        :param d:       dict value
        """
        if name in self.classes:
            cls = self.classes[name]
        else:
            cls = self.classes[name] = ClassDef(name)
        for key, value in d.items():
            v_type = self.get_type(key, value)
            field_name = self.gen_field_name(key, value=value)
            cls.update_filed(name=field_name, v_type=v_type, key=key)
        return cls

    def get_class_code_lines(self, cls: ClassDef) -> List[str]:
        if self.inherit_json_object_class:
            lines = [
                f"class {cls.name}({self.base_class_name}):"
            ]
        else:
            lines = [
                f"@{self.decorator_func_name}",
                f"class {cls.name}(dict):",
            ]
        if cls.filed_num > 0:
            for field in cls.fields:
                line = f"{self.indent}{field.name}: {field.type}"
                if self.always_specify_key_explicitly or field.name != field.key:
                    args = {'key': field.key}
                    if field.default is not None:
                        args['default'] = field.default
                    line += f" = {self.field_class_name}({', '.join(f'{k}={json.dumps(v)}' for k, v in args.items())})"
                elif field.default is not None:
                    line += f" {repr(field.default)}"
                lines.append(line)
        else:
            lines.append(self.indent + "pass")
        return lines

    def get_import_lines(self) -> List[str]:
        lines = []

        # elem should be imported in typing
        if self.types:
            lines.append(f"from typing import {', '.join(self.types)}")

        # elem should be imported in this module
        cur_module = []
        if self.inherit_json_object_class:
            cur_module.append(self.base_class_name)
        else:
            cur_module.append(self.decorator_func_name)
        if (self.always_specify_key_explicitly
                or any(any(f.name != f.key for f in cls.fields) for cls in self.classes.values())):
            cur_module.append(self.field_class_name)
        lines.append(f"from {self.module} import {', '.join(cur_module)}")

        return lines

    def get_code_text(self) -> str:
        params = [
            '\n'.join(self.get_import_lines()),
        ]
        for cls in reversed(self.classes.values()):
            params.append('\n'.join(self.get_class_code_lines(cls)))
        return '\n\n'.join(param for param in params if param) + "\n"

    def __str__(self) -> str:
        return self.get_code_text()

def parse_args(args=None):
    import argparse
    parser = argparse.ArgumentParser('build_class')
    parser.add_argument('--name', required=True, help='class name')
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--str', default=None, help='json format string')
    g.add_argument('--file', default=None, help='a json format file')
    parser.add_argument('--encoding', default='utf-8', help='file encoding, default is utf-8')
    parser.add_argument('--output', default=None,
                        help='output file to save generated python code, print result on the console if not set')
    parser.add_argument('--indent', type=int, default=4, help='indent for python code')
    parser.add_argument('--dict_as_class', type=bool, default=True,
                        help='new class will be generate for dict value if true, '
                             'otherwise the field type with dict value will be a native dict')
    parser.add_argument('--list_with_generic', type=bool, default=True,
                        help='the field type with list value will be Type[T] if true, '
                             'otherwise will be a native list')
    parser.add_argument('--class_name_style', default='upper_camel', choices=get_literal_values(NAME_STYLES),
                        help='class name style when auto generate a new class')
    parser.add_argument('--field_name_style', default='lower_line', choices=get_literal_values(NAME_STYLES),
                        help='field name style for all generated class')
    parser.add_argument('--always_specify_key_explicitly', default=False, action='store_true',
                        help="use `xx = Field(key='xx')` to define a field even if field name is same as key")
    parser.add_argument('--use_decorator', dest='inherit_json_object_class', default=True,
                        action='store_false', help='use decorator or inherit to define the json object class')
    return parser.parse_args(args)

def build_class_from_json(args=None):
    args = parse_args(args).__dict__

    root_cls_name = args.pop('name')
    input_file = args.pop('file')
    output_file = args.pop('output')
    encoding = args.pop('encoding')
    content = args.pop('str')

    # get json value
    if content:
        data = json.loads(content)
    else:
        with open(input_file, encoding=encoding) as f:
            data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    assert data, f"no data given"
    assert isinstance(data, list), data
    assert isinstance(data[0], dict), data

    # build class
    builder = ClassBuilder(**args)
    for d in data:
        builder.build(root_cls_name, d)
    code = builder.get_code_text()

    # save or print
    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(code)
    else:
        print(code)

if __name__ == '__main__':
    build_class_from_json()
