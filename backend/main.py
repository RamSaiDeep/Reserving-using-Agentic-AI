"""Compatibility entrypoint for existing deployments.

The application is composed in backend.app.main; this file remains a thin
import shim rather than a monolithic app module.
"""

from backend.app.main import app, create_app

__all__ = ["app", "create_app"]
