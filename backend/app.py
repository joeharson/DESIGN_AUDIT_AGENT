"""FastAPI application export for deployment tools.

The canonical app is still defined in the root-level ``main.py`` to preserve
the assignment structure and existing commands. This module gives evaluators a
clear backend package entrypoint without duplicating route setup.
"""

from main import app

__all__ = ["app"]

