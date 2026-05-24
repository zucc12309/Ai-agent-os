from __future__ import annotations

from abc import ABC


class BaseConnector(ABC):
    """Common base class for connector implementations."""

    connector_type: str = "base"

