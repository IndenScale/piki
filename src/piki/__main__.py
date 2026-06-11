"""piki CLI 入口点 — python -m piki"""

from __future__ import annotations

import sys

from piki.cli import main

if __name__ == "__main__":
    sys.exit(main())
