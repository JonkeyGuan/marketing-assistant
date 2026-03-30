"""
Google A2A (Agent-to-Agent) protocol data models.

Implements the core types from the A2A specification:
- Agent Card (capability discovery)
- Task lifecycle (send, status, artifacts)
- Message/Part (communication payload)
- JSON-RPC request/response envelope
"""
from typing import List, Optional, Any, Literal, Union, Annotated
from enum import Enum

from pydantic import BaseModel, Field


# ── Parts ──────────────────────────────────────────────────────────

class TextPart(BaseModel):
    kind: Literal["text"] = "text"
    text: str


class DataPart(BaseModel):
    kind: Literal["data"] = "data"
    data: dict


Part = Annotated[Union[TextPart, DataPart], Field(discriminator="kind")]


# ── Messages & Artifacts ──────────────────────────────────────────

class Message(BaseModel):
    role: Literal["user", "agent"]
    parts: List[Part]
    kind: Literal["message"] = "message"
    messageId: Optional[str] = None


class Artifact(BaseModel):
    artifact_id: Optional[str] = None
    name: Optional[str] = None
    parts: List[Part]


# ── Task ──────────────────────────────────────────────────────────

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[Message] = None


class Task(BaseModel):
    id: str
    status: TaskStatus
    contextId: Optional[str] = None
    kind: Literal["task"] = "task"
    history: Optional[List[Message]] = None
    artifacts: Optional[List[Artifact]] = None


# ── Agent Card ────────────────────────────────────────────────────

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: Optional[List[str]] = None


class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False


class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    capabilities: AgentCapabilities = AgentCapabilities()
    skills: List[AgentSkill] = []
