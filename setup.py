# -*- coding: utf-8 -*-

import os
import io
from setuptools import setup, find_packages

packages = find_packages(exclude=['test'])

here = os.path.abspath(os.path.dirname(__file__))

name = "flexible_dict"
description = "A flexible way to access dict data instead of built-in dict."
try:
    with io.open(os.path.join(here, "README.md"), encoding="utf-8") as f:
        long_description = "\n" + f.read()
except IOError:
    long_description = description

about = {}
with io.open(os.path.join(here, name, "about.py")) as f:
    exec(f.read(), about)

setup(
    name=name,
    version=about['__version__'],
    description=description,
    long_description=long_description,
    long_description_content_type='markdown',
    author='darkpeath',
    author_email='darkpeath@gmail.com',
    url="https://github.com/darkpeath/flexible_dict",
    packages=packages,
    include_package_data=True,
    platforms="any",
    tests_require=["pytest"],
    scripts=[],
)
