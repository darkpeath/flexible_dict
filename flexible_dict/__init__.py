# -*- coding: utf-8 -*-

from .json_object import json_object, Field, MISSING, JsonObject, ObjectVar

try:
    from ._version import __version__
except ImportError:
    try:
        from setuptools_scm import get_version
        __version__ = get_version(root='..', relative_to=__file__)
    except (ImportError, LookupError):
        __version__ = "UNKNOWN"

__all__ = [
    'json_object', 'Field', 'MISSING', 'JsonObject', 'ObjectVar',
    '__version__',
]
