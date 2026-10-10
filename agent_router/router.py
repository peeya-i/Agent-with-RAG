import time
import logging
from typing import Dict, List, Optional, Any
import requests

try:
    from .registry import AgentRegistry, AgentInfo
    from .embeddings import EmbeddingEngine
except (ImportError, ValueError):
    from registry import AgentRegistry, AgentInfo
    from embeddings import EmbeddingEngine


logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.50  # 50% threshold specified in requirements

class AgentMatchScore:
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        score: float,
        status: str,
        is_available: bool,
        is_default: bool,
    ):
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.score = float(score)
        self.status = status
        self.is_available = is_available
        self.is_default = is_default

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "score": round(self.score, 4),
            "similarity_percent": f"{round(self.score * 100, 1)}%",
            "status": self.status,
            "is_available": self.is_available,
            "is_default": self.is_default,
        }

class RoutingResult:
    def __init__(
        self,
        query: str,
        selected_agent: Optional[AgentInfo] = None,
        similarity_score: float = 0.0,
        ranked_scores: Optional[List[AgentMatchScore]] = None,
        is_default_fallback: bool = False,
        response_data: Optional[Dict[str, Any]] = None,
        explanation: str = "",
        routing_latency_ms: float = 0.0,
        total_latency_ms: float = 0.0,
        threshold: float = SIMILARITY_THRESHOLD,
    ):
        self.query = query
        self.selected_agent = selected_agent
        self.similarity_score = round(similarity_score, 4)
        self.ranked_scores = ranked_scores or []
        self.is_default_fallback = is_default_fallback
        self.response_data = response_data
        self.explanation = explanation
        self.routing_latency_ms = round(routing_latency_ms, 2)
        self.total_latency_ms = round(total_latency_ms, 2)
        self.threshold = threshold

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "selected_agent": self.selected_agent.to_dict() if self.selected_agent else None,
            "similarity_score": self.similarity_score,
            "similarity_percent": f"{round(self.similarity_score * 100, 1)}%",
            "threshold": self.threshold,
            "is_default_fallback": self.is_default_fallback,
            "ranked_scores": [s.to_dict() for s in self.ranked_scores],
            "response": self.response_data,
            "explanation": self.explanation,
            "routing_latency_ms": self.routing_latency_ms,
            "total_latency_ms": self.total_latency_ms,
        }

class VectorRouter:
    """Routes incoming queries to the most semantically relevant agent using vector embeddings.
    
    If no specialized agent has a similarity score higher than 50% (0.50),
    or if the best matching specialized agent is offline (DOWN),
    the router falls back to the default agents container.
    """

    def __init__(
        self,
        registry: AgentRegistry,
        embedding_engine: Optional[EmbeddingEngine] = None,
        threshold: float = SIMILARITY_THRESHOLD,
    ):
        self.registry = registry
        self.embedding_engine = embedding_engine or registry.embedding_engine
        self.threshold = threshold

    def decide_route(self, query: str) -> (AgentInfo, float, List[AgentMatchScore], bool, str, float):
        """Calculates embeddings, scores active agents, and selects either a specialized agent or fallback."""
        start_time = time.time()
        query_vec = self.embedding_engine.embed_text(query)

        all_agents = self.registry.list_all_agents()
        default_agent = self.registry.get_default_agent()

        if not all_agents:
            routing_latency = (time.time() - start_time) * 1000.0
            return None, 0.0, [], True, "No agents registered in system.", routing_latency

        scored: List[AgentMatchScore] = []

        # Score every registered agent
        for agent in all_agents:
            if agent.embedding is None:
                agent.embedding = self.embedding_engine.embed_text(agent.get_embedding_text())
            if not getattr(agent, "sample_embeddings", None) and agent.sample_prompts:
                agent.sample_embeddings = [self.embedding_engine.embed_text(p) for p in agent.sample_prompts]

            sims = [self.embedding_engine.compute_similarity(query_vec, agent.embedding)]
            for s_emb in getattr(agent, "sample_embeddings", []):
                sims.append(self.embedding_engine.compute_similarity(query_vec, s_emb))
            sim = max(sims) if sims else 0.0

            scored.append(AgentMatchScore(
                agent_id=agent.id,
                agent_name=agent.name,
                score=sim,
                status=agent.status,
                is_available=agent.is_available,
                is_default=agent.is_default,
            ))

        # Sort specialized agents descending by similarity
        specialized_scored = [s for s in scored if not s.is_default]
        specialized_scored.sort(key=lambda x: x.score, reverse=True)

        routing_latency = (time.time() - start_time) * 1000.0

        # Check if we have a specialized candidate
        if specialized_scored:
            top_match = specialized_scored[0]
            # Rule: Match must be HIGHER than 50% (0.50)
            if top_match.score > self.threshold:
                if top_match.is_available:
                    target_agent = self.registry.get_agent(top_match.agent_id)
                    explanation = (
                        f"Specialized match '{top_match.agent_name}' exceeded {int(self.threshold * 100)}% threshold "
                        f"with score {top_match.score:.4f} ({top_match.score * 100:.1f}%)."
                    )
                    return target_agent, top_match.score, scored, False, explanation, routing_latency
                else:
                    explanation = (
                        f"Top specialized agent '{top_match.agent_name}' matched at {top_match.score * 100:.1f}%, "
                        f"but status is DOWN. Falling back to default agents container."
                    )
                    return default_agent, top_match.score, scored, True, explanation, routing_latency
            else:
                explanation = (
                    f"No specialized agent matched above {int(self.threshold * 100)}% threshold "
                    f"(best candidate '{top_match.agent_name}' scored {top_match.score * 100:.1f}%). "
                    f"Defaulting to primary agents container."
                )
                return default_agent, top_match.score, scored, True, explanation, routing_latency

        # If no specialized agent is registered, use default
        explanation = "No specialized agents registered. Defaulting to primary agents container."
        return default_agent, 0.0, scored, True, explanation, routing_latency

    def forward_request(
        self,
        agent: AgentInfo,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 60,
    ) -> Dict[str, Any]:
        """Dispatches chat request to agent container over HTTP REST protocol."""
        url = f"{agent.url}/api/agent/chat"
        req_headers = {"Content-Type": "application/json"}
        if headers:
            for k, v in headers.items():
                if k.lower() in ["authorization", "x-user-id", "x-domain"]:
                    req_headers[k] = v

        logger.info(f"Forwarding prompt to agent '{agent.id}' at {url}...")
        resp = requests.post(url, json=payload, headers=req_headers, timeout=timeout)
        agent.queries_handled += 1
        return resp.json(), resp.status_code

    def route_and_execute(
        self,
        query: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ) -> RoutingResult:
        """Decides agent route based on vector embedding and executes prompt via HTTP REST."""
        total_start = time.time()
        agent, top_score, ranked, is_fallback, explanation, route_ms = self.decide_route(query)

        if not agent:
            return RoutingResult(
                query=query,
                explanation=explanation,
                routing_latency_ms=route_ms,
                total_latency_ms=(time.time() - total_start) * 1000.0,
            )

        resp_data = None
        status_code = 200
        try:
            resp_data, status_code = self.forward_request(agent, payload, headers=headers)
        except Exception as e:
            logger.error(f"Failed to communicate with agent '{agent.id}' at {agent.url}: {e}")
            # If specialized agent failed, try fallback to default agent if not already default
            default_agent = self.registry.get_default_agent()
            if agent.id != default_agent.id and default_agent:
                logger.warning(f"Specialized agent failed; falling back to default agent '{default_agent.id}'...")
                try:
                    resp_data, status_code = self.forward_request(default_agent, payload, headers=headers)
                    explanation += f" (Specialized agent unreachable; recovered via default agent)."
                    agent = default_agent
                    is_fallback = True
                except Exception as ex2:
                    resp_data = {"error": f"Failed reaching both specialized ({e}) and default agent ({ex2})"}
                    status_code = 502
            else:
                resp_data = {"error": f"Agent communication failure: {str(e)}"}
                status_code = 502

        total_latency = (time.time() - total_start) * 1000.0

        # Inject routing metadata into the response
        if isinstance(resp_data, dict):
            resp_data["router_metadata"] = {
                "routed_agent_id": agent.id,
                "routed_agent_name": agent.name,
                "routed_agent_url": agent.url,
                "similarity_score": round(top_score, 4),
                "threshold": self.threshold,
                "is_default_fallback": is_fallback,
                "routing_latency_ms": round(route_ms, 2),
                "total_latency_ms": round(total_latency, 2),
                "explanation": explanation,
            }

        return RoutingResult(
            query=query,
            selected_agent=agent,
            similarity_score=top_score,
            ranked_scores=ranked,
            is_default_fallback=is_fallback,
            response_data=resp_data,
            explanation=explanation,
            routing_latency_ms=route_ms,
            total_latency_ms=total_latency,
            threshold=self.threshold,
        )
