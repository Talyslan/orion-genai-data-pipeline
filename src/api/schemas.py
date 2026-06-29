"""Shared API request and response schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthComponentStatus(BaseModel):
    status: Literal["ok", "error"]
    message: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    checks: dict[str, HealthComponentStatus]


class AcceptedResponse(BaseModel):
    status: Literal["accepted"] = "accepted"
    enqueued: Literal[True] = True
    message: str
    job_id: str
    type: Literal["pdf", "site"]
    poll: str
    input: dict[str, Any] = Field(default_factory=dict)


class RejectedResponse(BaseModel):
    status: Literal["rejected"] = "rejected"
    enqueued: Literal[False] = False
    error: str
    message: str
    help: dict[str, Any] = Field(default_factory=dict)
