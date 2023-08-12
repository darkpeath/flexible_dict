#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from argparse import ArgumentParser
from importlib.metadata import version

def entry_point():
    parser = ArgumentParser()
    parser.add_argument("-v", "--version", action="store_true")

    args = parser.parse_args()

    if args.version:
        print(version("flexible_dict"))
        sys.exit()
