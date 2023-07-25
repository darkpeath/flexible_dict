# -*- coding: utf-8 -*-

from typing import List, Any
import dataclasses
import argparse
import collections
import json
import re

def line2camel(name: str, capitalized=False) -> str:
    if not name:
        return name
    contents = re.findall('_[a-z]+', name)
    for content in set(contents):
        name = name.replace(content, content[1:].title())
    if capitalized:
        name = name[0].upper() + name[1:]
    return name

@dataclasses.dataclass
class FieldDef:
    name: str
    type: str
    default: str = None

@dataclasses.dataclass
class ClassDef:
    name: str
    fields: List[FieldDef] = dataclasses.field(default_factory=list)

class ClassBuilder:
    def __init__(self, indent=' ' * 4, dict_as_class=True, list_with_generic=True):
        self.indent = indent
        self.dict_as_class = dict_as_class
        self.list_with_generic = list_with_generic
        self.classes = collections.OrderedDict()
        self.types = set()
        self.module = "flexible_dict"
        self.decorator_func = "json_object"
        self.word_parser = None

    def get_singular_word(self, word: str) -> str:
        if word.endswith('_list'):
            return word[-5:]
        if word.endswith('List'):
            return word[-4:]
        if self.word_parser is None:
            import inflect
            self.word_parser = inflect.engine()
        res = self.word_parser.singular_noun(word)
        if not res:
            return word
        return res

    def get_type(self, key: str, value: Any) -> str:
        t = type(value).__name__
        if t == 'dict' and self.dict_as_class:
            t = line2camel(key, capitalized=True)
            self.build(t, value)
        elif t == 'list' and value and value[0] and self.list_with_generic:
            elem_type = self.get_type(self.get_singular_word(key), value[0])
            t = f"List[{elem_type}]"
            self.types.add('List')
        return t

    def build(self, name: str, d: dict) -> ClassDef:
        """
        build python class, walk dfs
        :param name:    class name
        :param d:       dict value
        """
        if name in self.classes:
            return self.classes[name]
        cls = ClassDef(name)
        for k, v in d.items():
            field = FieldDef(k, self.get_type(k, v))
            cls.fields.append(field)
        self.classes[name] = cls
        return cls

    def get_class_code_lines(self, cls: ClassDef) -> List[str]:
        lines = [
            f"@{self.decorator_func}",
            f"class {cls.name}(dict):",
        ]
        if cls.fields:
            for field in cls.fields:
                line = f"{self.indent}{field.name}: {field.type}"
                if field.default is not None:
                    line += f" {repr(field.default)}"
                lines.append(line)
        else:
            lines.append(self.indent + "pass")
        return lines

    def get_code_text(self) -> str:
        lines = []
        if self.types:
            lines.append(f"from typing import {', '.join(self.types)}")
        lines.append(f"from {self.module} import {self.decorator_func}")
        lines.append("")
        for cls in self.classes.values():
            lines.extend(self.get_class_code_lines(cls))
            lines.append("")
        return '\n'.join(lines)

    def __str__(self) -> str:
        return self.get_code_text()

def parse_args(args=None):
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
    # parser.add_argument('--file_class_name_format', default='camel_case',
    #                     choices=['camel_case'], help='field class name format')
    return parser.parse_args(args)

def build_class_from_json(args=None):
    args = parse_args(args)
    indent = ' ' * args.indent
    if args.str:
        d = json.loads(args.str)
    else:
        with open(args.file, encoding=args.encoding) as f:
            d = json.load(f)

    builder = ClassBuilder(indent=indent, dict_as_class=args.dict_as_class, list_with_generic=args.list_with_generic)
    builder.build(args.name, d)
    code = builder.get_code_text()
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(code)
    else:
        print(code)

if __name__ == '__main__':
    build_class_from_json()
