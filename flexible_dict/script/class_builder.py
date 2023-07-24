# -*- coding: utf-8 -*-

import argparse
import json

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
    return parser.parse_args(args)

def build_class_from_json(args=None):
    args = parse_args(args)
    indent = ' ' * args.indent
    if args.str:
        d = json.loads(args.str)
    else:
        with open(args.file, encoding=args.encoding) as f:
            d = json.load(f)
    package = 'flexible_dict'
    decorator = 'json_object'
    lines = [
        f"from {package} import {decorator}",
        "",
        f"@{decorator}",
        f"class {args.name}:",
    ]
    for k, v in d.items():
        lines.append(f"{indent}{k}: {type(v).__name__}")
    code = '\n'.join(lines) + "\n"
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(code)
    else:
        print(code)

if __name__ == '__main__':
    build_class_from_json()
