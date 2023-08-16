# -*- coding: utf-8 -*-

from importlib.metadata import version, PackageNotFoundError

try:
    import setuptools_scm
    __version__ = version("flexible_dict")
except PackageNotFoundError:
    # package is not installed
    __version__ = "UNKNOWN"
