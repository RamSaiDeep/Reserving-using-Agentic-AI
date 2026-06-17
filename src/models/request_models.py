"""Pydantic request models for API routes."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    csv_text: str
    api_key: Optional[str] = None


class ExecuteRequest(BaseModel):
    csv_text: str
    method_code: str
    params: dict[str, Any] = Field(default_factory=dict)
    custom_ldfs: list[float] = Field(default_factory=list)
    api_key: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    history: list = Field(default_factory=list)
    context_data: dict = Field(default_factory=dict)
    api_key: Optional[str] = None
