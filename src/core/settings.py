"""Runtime settings."""

from pydantic import BaseModel


class Settings(BaseModel):
    app_name: str = "Agentic Reserving System"
