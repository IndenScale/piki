"""AQL QuerySet — re-exported from piki's vendored engine.

The canonical implementation lives in piki.core.engine._query_engine.
This module exists so that ``pip install aql`` works as a standalone package.
"""

from piki.core.engine._query_engine import (  # noqa: F401
    _KEY_UNRESOLVED,
    QuerySet,
    _KeyUnresolved,
)
