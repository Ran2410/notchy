#!/usr/bin/env python3
"""notchy — Dynamic Island untuk Linux & Windows.

Linux:   python3 run.py          (atau ./.venv/bin/python run.py)
Windows: py run.py

Keluar:  klik kanan pada island → Quit notchy.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    from notchy.ui.island import run_qt

    return run_qt()


if __name__ == "__main__":
    raise SystemExit(main())
