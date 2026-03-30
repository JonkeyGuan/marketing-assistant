"""
A2A Client for calling remote A2A agent services.

Provides synchronous methods (suitable for LangGraph nodes):
  - get_agent_card()  → fetch the remote agent's card
  - send_task()       → send a message and wait for the result
"""
import uuid

import httpx

from .models import AgentCard, Message, Task


class A2AClient:
    """Synchronous A2A client."""

    def __init__(self, base_url: str, timeout: float = 300):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._request_id = 0

    def get_agent_card(self) -> AgentCard:
        with httpx.Client(timeout=10) as client:
            resp = client.get(f"{self.base_url}/.well-known/agent-card.json")
            resp.raise_for_status()
            return AgentCard(**resp.json())

    def send_task(self, message: Message, task_id: str | None = None) -> Task:
        self._request_id += 1

        # Ensure message has a messageId
        if not message.messageId:
            message.messageId = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": "message/send",
            "id": self._request_id,
            "params": {
                "message": message.model_dump(),
            },
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(f"{self.base_url}/", json=payload)
            resp.raise_for_status()
            result = resp.json()

        if result.get("error"):
            raise Exception(f"A2A error: {result['error']}")

        return Task(**result["result"])
