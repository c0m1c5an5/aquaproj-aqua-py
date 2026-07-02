#!/usr/bin/env python3
from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib

if __name__ == '__main__':
    with open('pyproject.toml', 'rb') as f:
        pyproject = tomllib.load(f)

    version: str = pyproject['project']['version']
    print(
        'v' + version.removeprefix('v'),
    )
