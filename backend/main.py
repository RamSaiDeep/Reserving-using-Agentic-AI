"""Compatibility entrypoint for existing deployments.

The application is composed in app.backend.main; this file remains a thin
import shim rather than a monolithic app module.
"""

from app.backend.main import app, create_app

__all__ = ["app", "create_app"]
