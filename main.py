#!/usr/bin/env python3
"""Compatibility entry point.

The dash lives in the digifiz package now. This shim stays so `python main.py`
keeps working, including from any old service file or shortcut.
"""

from digifiz.app import main

if __name__ == "__main__":
    raise SystemExit(main())
