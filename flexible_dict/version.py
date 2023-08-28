# -*- coding: utf-8 -*-

try:
    from ._dist_ver import VERSION, __version__
except ImportError:
    from importlib_metadata import version, PackageNotFoundError
    try:
        __version__ = version('flexible_dict')
    except PackageNotFoundError:
        # package is not installed
        __version__ = "UNKNOWN"
    VERSION = __version__.split('.')
