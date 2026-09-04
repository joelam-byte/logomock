"""Compatibility test entry: verify physical behavior instead of source identifiers.

The old AST rule required a 96dpi factor in a millimeter viewport, which
locked in a scaling bug. Real geometry/export tests supersede that rule.
"""
import subprocess
import sys
from pathlib import Path

if __name__ == '__main__':
    raise SystemExit(subprocess.call([sys.executable,'-m','pytest','tests/test_geometry.py','tests/test_exports.py','-q'],
                                    cwd=Path(__file__).resolve().parent))
