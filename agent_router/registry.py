import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import requests
import numpy as np
try:
    from .embeddings import EmbeddingEngine
except (ImportError, ValueError):
    from embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)

class AgentInfo:
    """Represents a registered agent in the router."""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        url: str,
        sample_prompts: Optional[List[str]] = None,
        status: str = "up",
        is_default: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.url = url.rstrip("/")
        self.sample_prompts = sample_prompts or []
        self.status = status.lower()
        self.is_default = is_default
        self.metadata = metadata or {}
        self.embedding: Optional[np.ndarray] = None
        self.sample_embeddings: List[np.ndarray] = []
        self.queries_handled: int = 0
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.last_status_change = self.created_at
        self.last_health_check = None
        self.health_status = "unknown"

    @property
    def is_available(self) -> bool:
        return self.status == "up"

    def turn_up(self) -> "AgentInfo":
        self.status = "up"
        self.last_status_change = datetime.now(timezone.utc).isoformat()
        return self

    def turn_down(self) -> "AgentInfo":
        self.status = "down"
        self.last_status_change = datetime.now(timezone.utc).isoformat()
        return self

    def get_embedding_text(self) -> str:
        samples_joined = ". ".join(self.sample_prompts)
        return (
            f"Agent Name: {self.name}. "
            f"Description: {self.description}. "
            f"Capabilities & Typical Queries: {samples_joined}."
        )

    def to_dict(self, include_embedding: bool = False) -> Dict[str, Any]:
        data = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "sample_prompts": self.sample_prompts,
            "status": self.status,
            "is_available": self.is_available,
            "is_default": self.is_default,
            "queries_handled": self.queries_handled,
            "created_at": self.created_at,
            "last_status_change": self.last_status_change,
            "last_health_check": self.last_health_check,
            "health_status": self.health_status,
            "metadata": self.metadata,
            "has_embedding": self.embedding is not None,
        }
        if include_embedding and self.embedding is not None:
            data["embedding"] = self.embedding.tolist()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentInfo":
        agent = cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            url=data.get("url", ""),
            sample_prompts=data.get("sample_prompts", []),
            status=data.get("status", "up"),
            is_default=bool(data.get("is_default", False)),
            metadata=data.get("metadata", {}),
        )
        agent.queries_handled = data.get("queries_handled", 0)
        agent.created_at = data.get("created_at", agent.created_at)
        agent.last_status_change = data.get("last_status_change", agent.last_status_change)
        agent.last_health_check = data.get("last_health_check")
        agent.health_status = data.get("health_status", "unknown")
        if "embedding" in data and data["embedding"] is not None:
            agent.embedding = np.array(data["embedding"], dtype=np.float32)
        return agent


class AgentRegistry:
    """Thread-safe dynamic registry managing agents, their health, status, and embeddings."""

    def __init__(self, embedding_engine: Optional[EmbeddingEngine] = None):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = threading.RLock()
        self.embedding_engine = embedding_engine or EmbeddingEngine()

    def register(self, agent: AgentInfo, auto_embed: bool = True) -> AgentInfo:
        with self._lock:
            if auto_embed:
                if agent.embedding is None:
                    text_to_embed = agent.get_embedding_text()
                    logger.info(f"Computing vector embedding for agent '{agent.id}' ({agent.name})...")
                    agent.embedding = self.embedding_engine.embed_text(text_to_embed)
                if not agent.sample_embeddings and agent.sample_prompts:
                    agent.sample_embeddings = [self.embedding_engine.embed_text(p) for p in agent.sample_prompts]

            # Preserve queries_handled if re-registering
            if agent.id in self._agents:
                agent.queries_handled = self._agents[agent.id].queries_handled
                agent.created_at = self._agents[agent.id].created_at

            self._agents[agent.id] = agent
            logger.info(f"Agent '{agent.id}' successfully registered (URL: {agent.url}, Status: {agent.status}).")
            return agent

    def unregister(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self._agents:
                # Do not allow unregistering the default fallback agent
                if self._agents[agent_id].is_default:
                    raise ValueError(f"Cannot unregister default fallback agent '{agent_id}'.")
                del self._agents[agent_id]
                logger.info(f"Agent '{agent_id}' unregistered.")
                return True
            return False

    def turn_up(self, agent_id: str) -> AgentInfo:
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"Agent '{agent_id}' is not registered.")
            agent = self._agents[agent_id]
            agent.turn_up()
            logger.info(f"Agent '{agent_id}' turned UP.")
            return agent

    def turn_down(self, agent_id: str) -> AgentInfo:
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"Agent '{agent_id}' is not registered.")
            agent = self._agents[agent_id]
            agent.turn_down()
            logger.info(f"Agent '{agent_id}' turned DOWN.")
            return agent

    def set_status(self, agent_id: str, status: str) -> AgentInfo:
        with self._lock:
            if status.lower() == "up":
                return self.turn_up(agent_id)
            else:
                return self.turn_down(agent_id)

    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        with self._lock:
            return self._agents.get(agent_id)

    def get_default_agent(self) -> Optional[AgentInfo]:
        with self._lock:
            for a in self._agents.values():
                if a.is_default:
                    return a
            # Fallback to agents:8002 if marked
            for a in self._agents.values():
                if "8002" in a.url or a.id in ["agents", "agents-default"]:
                    return a
            return list(self._agents.values())[0] if self._agents else None

    def list_all_agents(self) -> List[AgentInfo]:
        with self._lock:
            return list(self._agents.values())

    def list_available_agents(self) -> List[AgentInfo]:
        with self._lock:
            return [a for a in self._agents.values() if a.is_available]

    def list_offline_agents(self) -> List[AgentInfo]:
        with self._lock:
            return [a for a in self._agents.values() if not a.is_available]

    def refresh_embedding(self, agent_id: str) -> AgentInfo:
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"Agent '{agent_id}' not found.")
            agent = self._agents[agent_id]
            agent.embedding = self.embedding_engine.embed_text(agent.get_embedding_text())
            return agent

    def check_health(self, agent_id: str) -> Dict[str, Any]:
        with self._lock:
            if agent_id not in self._agents:
                raise KeyError(f"Agent '{agent_id}' not found.")
            agent = self._agents[agent_id]

        url = f"{agent.url}/health"
        agent.last_health_check = datetime.now(timezone.utc).isoformat()
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                agent.health_status = "healthy"
                return {"agent_id": agent_id, "status": "healthy", "code": 200, "data": resp.json()}
            else:
                agent.health_status = f"unhealthy ({resp.status_code})"
                return {"agent_id": agent_id, "status": "unhealthy", "code": resp.status_code}
        except Exception as e:
            agent.health_status = f"unreachable: {e}"
            return {"agent_id": agent_id, "status": "unreachable", "error": str(e)}
