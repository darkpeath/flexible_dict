# -*- coding: utf-8 -*-

import logging
from .script.class_builder import build_class_from_json

logger = logging.getLogger(__file__)

commands = {
    'build_class': build_class_from_json,
}

def main():
    import sys
    if len(sys.argv) < 2:
        logger.error(f"Usage: python -m flexible_dict {'|'.join(commands.keys())} [arg ...]")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd not in commands:
        raise ValueError(f"Unexpected cmd: {cmd}")
    commands[cmd](sys.argv[2:])

if __name__ == '__main__':
    main()
